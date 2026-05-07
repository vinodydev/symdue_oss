# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Docker executor for Python node execution.

Uses `docker cp` instead of volume mounts to avoid the classic DooD
path-mismatch issue: when the backend/worker runs inside a container,
`tempfile.TemporaryDirectory()` produces a path local to *that*
container, which the host Docker daemon cannot resolve.
"""
import asyncio
import docker
import json
import logging
import tempfile
import os
from pathlib import Path
from typing import Dict, Any, Optional, Callable

from config.settings import get_settings

logger = logging.getLogger(__name__)


class DockerExecutor:
    """
    Executes Python nodes in isolated Docker containers.

    Strategy:
    1. Create container (without starting it)
    2. `docker cp` the workspace files into /workspace
    3. Start container
    4. Wait, collect logs, parse JSON output
    """

    def __init__(self):
        self.settings = get_settings()
        try:
            # Create Docker client with increased timeouts (5 minutes instead of default 60s)
            self.client = docker.from_env(timeout=300)
            logger.info("Docker client connected successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Docker: {e}")
            raise

        self.image = "python:3.11-slim"
        self._last_cancelled_logs: Optional[str] = None  # Logs captured when cancelled (for caller)

    # ──────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────

    async def execute_python_node(
        self,
        code: str,
        requirements: str = "",
        inputs: Dict[str, Any] = None,
        storage_configs: Optional[Dict[str, Dict[str, Any]]] = None,
        environment_variables: Optional[Dict[str, str]] = None,
        timeout: int = 60,
        heartbeat_callback: Optional[Callable[[str], None]] = None,
        log_callback: Optional[Callable[[str], None]] = None,
        workspace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute user Python code inside a disposable Docker container.

        The user code is expected to define a ``main(inputs, storages)`` function.
        If it doesn't, the raw ``inputs`` dict is returned.

        Args:
            storage_configs: Dict mapping alias to {storage_type, config}
                Example: {"main_db": {"storage_type": "postgresql", "config": {...}}}
            heartbeat_callback: Optional callback function to call periodically
                with status messages during execution. Should be non-blocking.
            log_callback: Optional callback function to call with new log lines
                as they are fetched during execution. Should be non-blocking.

        Returns
        -------
        dict  ``{"output": ..., "output_type": "text", "error": None | str, "logs": str}``
        """
        inputs = inputs or {}
        storage_configs = storage_configs or {}
        environment_variables = environment_variables or {}
        logger.info(f"Executing Python node: code_len={len(code)}, reqs='{requirements[:60]}', timeout={timeout}, storages={list(storage_configs.keys())}, env_vars={len(environment_variables)}")

        # Ensure image exists
        await self._ensure_image()

        # Build files on disk (local to *this* container – that's fine, we'll cp them)
        with tempfile.TemporaryDirectory() as temp_dir:
            self._write_workspace_files(temp_dir, code, requirements, inputs, storage_configs)

            container = None
            logs_buffer = []  # Buffer logs for real-time streaming
            try:
                # 1. Create (don't start) a container
                cmd = self._build_command(requirements)

                # Connect to the same Docker network as docker-compose
                # services so hostnames like "minio" resolve correctly.
                # issue16: to_thread — networks.list() + reload() are sync docker-py
                network_name = await asyncio.to_thread(self._get_docker_network)

                create_kwargs: Dict[str, Any] = {
                    "image": self.image,
                    "command": cmd,
                    "detach": True,
                    "network_disabled": False,
                    "mem_limit": "512m",
                    "cpu_period": 100000,
                    "cpu_quota": 50000,
                    "working_dir": "/workspace",
                }

                # Bind-mount the substrate's data world into the sandbox so the
                # FilesHelper (zero-config local-FS reads) and local_file_storage
                # backend share the same on-disk view. Uses host paths from the
                # HOST_*_ROOT settings to side-step the DooD path-mismatch issue.
                # See flowgraph/issues/issue3 for rationale.
                volumes = self._build_sandbox_volumes(workspace_id)
                if volumes:
                    create_kwargs["volumes"] = volumes
                    logger.debug(f"Mounting {len(volumes)} host paths into sandbox")

                if network_name:
                    create_kwargs["network"] = network_name
                    logger.info(f"Connecting worker container to network: {network_name}")
                
                # Add environment variables if provided
                if environment_variables:
                    create_kwargs["environment"] = environment_variables
                    logger.debug(f"Setting {len(environment_variables)} environment variables")

                # issue16: wrap blocking docker-py calls in asyncio.to_thread so
                # the event loop stays free — sibling fan-out actually runs in
                # parallel and Temporal heartbeats can fire on schedule.
                container = await asyncio.to_thread(
                    self.client.containers.create, **create_kwargs
                )
                logger.debug(f"Container created: {container.short_id}")
                if heartbeat_callback:
                    heartbeat_callback("Container created, copying files...")

                # 2. Copy workspace into container via `docker cp`
                await asyncio.to_thread(
                    self._copy_to_container, container, temp_dir, "/workspace"
                )
                logger.debug("Workspace files copied into container")
                if heartbeat_callback:
                    heartbeat_callback("Files copied, starting container...")

                # 3. Start
                await asyncio.to_thread(container.start)
                logger.debug("Container started")
                if heartbeat_callback:
                    heartbeat_callback("Container started, executing code...")

                # 4. Wait for exit with periodic heartbeats and log fetching
                from datetime import datetime
                
                # Wait with periodic heartbeats and log fetching
                start_time = datetime.now()
                heartbeat_interval = 30  # Send heartbeat every 30 seconds
                log_fetch_interval = 3  # Fetch logs every 3 seconds (was 10)
                last_heartbeat = start_time
                last_log_fetch = start_time
                last_log_length = 0  # Byte-offset for new log content (no duplicate lines dropped)
                
                # Calculate timeout deadline
                timeout_deadline = start_time.timestamp() + timeout
                
                while True:
                    # Check timeout
                    if datetime.now().timestamp() > timeout_deadline:
                        logger.warning(f"Container execution timeout after {timeout} seconds")
                        if heartbeat_callback:
                            heartbeat_callback(f"Execution timeout after {timeout}s, stopping container...")
                        try:
                            await asyncio.to_thread(container.stop, timeout=5)
                        except Exception as e:
                            logger.warning(f"Error stopping container: {e}")
                        raise TimeoutError(f"Container execution exceeded {timeout} second timeout")

                    # Check if container has exited (issue16: wrap docker-py blocking calls)
                    try:
                        await asyncio.to_thread(container.reload)
                        if container.status == "exited":
                            break
                    except Exception as e:
                        logger.warning(f"Error reloading container status: {e}")
                        # Continue anyway - will check on next iteration

                    # Periodically fetch new logs (byte-offset to avoid dropping duplicate lines)
                    now = datetime.now()
                    if (now - last_log_fetch).total_seconds() >= log_fetch_interval:
                        try:
                            current_logs_bytes = await asyncio.to_thread(
                                container.logs, stdout=True, stderr=True
                            )
                            current_logs = current_logs_bytes.decode("utf-8", errors="replace")
                            if len(current_logs) > last_log_length:
                                new_portion = current_logs[last_log_length:]
                                last_log_length = len(current_logs)
                                logs_buffer.append(new_portion)
                                if log_callback and new_portion.strip():
                                    try:
                                        log_callback(new_portion.strip())
                                    except Exception as e:
                                        logger.warning(f"Error in log callback: {e}")
                                for line in new_portion.strip().splitlines():
                                    if line.strip():
                                        logger.info(f"[container] {line.strip()}")
                        except Exception as e:
                            logger.warning(f"Error fetching logs: {e}")

                        last_log_fetch = now
                    
                    # Send periodic heartbeat
                    if heartbeat_callback and (now - last_heartbeat).total_seconds() >= heartbeat_interval:
                        elapsed = (now - start_time).total_seconds()
                        log_preview = "\n".join(logs_buffer[-5:]) if logs_buffer else "No logs yet"
                        heartbeat_callback(f"Running... ({int(elapsed)}s elapsed)\nLast logs:\n{log_preview}")
                        last_heartbeat = now
                    
                    await asyncio.sleep(2)  # Check every 2 seconds
                
                # Get final logs with timeout handling (issue16: to_thread)
                try:
                    result = await asyncio.to_thread(container.wait, timeout=10)
                    exit_code = result.get("StatusCode", 1)
                except Exception as e:
                    logger.warning(f"Error waiting for container: {e}, checking status directly")
                    try:
                        await asyncio.to_thread(container.reload)
                        exit_code = 1 if container.status != "exited" else 0
                    except Exception:
                        exit_code = 1

                # Combine streamed logs with final logs
                final_logs_bytes = await asyncio.to_thread(
                    container.logs, stdout=True, stderr=True
                )
                final_logs = final_logs_bytes.decode("utf-8", errors="replace")
                if logs_buffer:
                    # Prefer streamed logs if available
                    all_logs = "\n".join(logs_buffer) + "\n" + final_logs
                else:
                    all_logs = final_logs
                
                logger.info(f"Container exited: code={exit_code}, log_bytes={len(all_logs)}")
                
                if exit_code != 0:
                    logger.warning(f"Container exited with error:\n{all_logs[-500:]}")
                    if heartbeat_callback:
                        heartbeat_callback(f"Execution failed with exit code {exit_code}")
                    return {"output": None, "output_type": "text", "error": all_logs, "logs": all_logs}

                if heartbeat_callback:
                    heartbeat_callback("Execution completed successfully")
                
                parsed = self._parse_output(all_logs)
                parsed["logs"] = all_logs  # Include full logs in response
                return parsed

            except asyncio.CancelledError:
                # Capture buffered logs so caller can publish them; re-raise for Temporal
                self._last_cancelled_logs = "\n".join(logs_buffer) if logs_buffer else ""
                logger.warning(
                    f"Docker execution cancelled. Captured {len(self._last_cancelled_logs)} bytes of logs"
                )
                raise
            except Exception as e:
                logger.error(f"Docker execution error: {e}", exc_info=True)
                error_msg = str(e)
                if heartbeat_callback:
                    heartbeat_callback(f"Execution error: {error_msg}")
                # Include any captured logs in error response
                logs = "\n".join(logs_buffer) if logs_buffer else ""
                return {
                    "output": None, 
                    "output_type": "text", 
                    "error": error_msg,
                    "logs": logs
                }

            finally:
                if container:
                    try:
                        # Capture final logs before destroying container (Fix 1: survive cancel/crash)
                        # issue16: to_thread to keep the event loop free during cleanup
                        final_logs_bytes = await asyncio.to_thread(
                            container.logs, stdout=True, stderr=True
                        )
                        final_logs = final_logs_bytes.decode("utf-8", errors="replace")
                        if final_logs and log_callback:
                            try:
                                log_callback(final_logs)
                            except Exception:
                                pass
                    except Exception:
                        pass
                    try:
                        await asyncio.to_thread(container.remove, force=True)
                    except Exception:
                        pass

    # ──────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────

    def _get_docker_network(self) -> Optional[str]:
        """
        Find the Docker network that contains the docker-compose services
        (e.g. minio, postgres, redis) so that worker containers can resolve
        service hostnames like ``minio:9000``.

        Returns the network name, or ``None`` to fall back to the default bridge.
        """
        try:
            networks = self.client.networks.list()

            # 1. Look for a network that contains the MinIO container
            for network in networks:
                try:
                    network.reload()
                    containers = network.attrs.get("Containers", {})
                    for _cid, info in containers.items():
                        name = info.get("Name", "")
                        if "graphmind-minio" in name or "minio" in name.lower():
                            logger.debug(f"Found docker-compose network via minio container: {network.name}")
                            return network.name
                except Exception:
                    continue

            # 2. Fallback – match by docker-compose naming convention (<project>_default)
            for network in networks:
                if "setup_default" in network.name or (
                    "default" in network.name and "bridge" not in network.name
                ):
                    logger.debug(f"Using network by naming convention: {network.name}")
                    return network.name

            logger.warning("Could not find docker-compose network, using default bridge")
            return None
        except Exception as e:
            logger.warning(f"Error finding Docker network: {e}, using default bridge")
            return None

    def _write_workspace_files(
        self, temp_dir: str, code: str, requirements: str, inputs: Dict[str, Any], storage_configs: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> None:
        """Write script, wrapper, inputs, and optional requirements into *temp_dir*."""
        storage_configs = storage_configs or {}
        Path(temp_dir, "script.py").write_text(code)
        Path(temp_dir, "inputs.json").write_text(json.dumps(inputs))
        Path(temp_dir, "wrapper.py").write_text(self._create_wrapper_script(storage_configs))
        
        # Write storage_client.py for Python nodes to use
        self._write_storage_client(temp_dir)

        # Write files_helper.py so the sandbox can import FilesHelper
        # (zero-config helper for ad-hoc local-FS reads inside Custom Python nodes)
        self._write_files_helper(temp_dir)

        if requirements.strip():
            Path(temp_dir, "requirements.txt").write_text(requirements)

    def _create_wrapper_script(self, storage_configs: Optional[Dict[str, Dict[str, Any]]] = None) -> str:
        """
        A self-contained Python script that:
        1. Reads ``inputs.json``
        2. Initializes storage clients from configs
        3. ``exec``s ``script.py`` in a fresh namespace
        4. Calls ``main(inputs, storages)`` if present
        5. Prints the result as a single JSON line on stdout
        """
        storage_configs = storage_configs or {}
        
        # Build storage client initialization code
        storage_init_code = []
        storage_dict_entries = []
        
        for alias, storage_info in storage_configs.items():
            storage_type = storage_info["storage_type"]
            config = storage_info["config"]
            var_name = alias.replace("-", "_").replace(" ", "_")
            
            # Initialize StorageClient with type and config
            storage_init_code.append(
                f"    {var_name} = StorageClient("
                f'storage_type="{storage_type}", '
                f"config={repr(config)}"
                f")"
            )
            storage_dict_entries.append(f'    "{alias}": {var_name}')
        
        # Ensure proper indentation (4 spaces for function body)
        if storage_init_code:
            storage_init_str = "\n".join(storage_init_code)
        else:
            storage_init_str = "    # No storages configured"
        
        storage_dict_str = "{\n" + ",\n".join(storage_dict_entries) + "\n    }" if storage_dict_entries else "{}"
        
        return f'''\
import json, sys, traceback, os
from storage_client import StorageClient
from files_helper import FilesHelper

def run():
    # Load inputs
    inputs_path = os.path.join(os.path.dirname(__file__), "inputs.json")
    with open(inputs_path, "r") as f:
        inputs = json.load(f)

    # Initialize storage clients from configs
{storage_init_str}

    # Storage clients dictionary (keys are aliases, values are StorageClient instances)
    storages = {storage_dict_str}

    # Zero-config local-FS helper. Reads from sandbox-mounted directories
    # (/workspace/files, /storage, /cache, /tmp). For Drive/S3/etc. use storages[alias].
    files = FilesHelper()

    # Read user code
    script_path = os.path.join(os.path.dirname(__file__), "script.py")
    with open(script_path, "r") as f:
        user_code = f.read()

    # Execute in isolated namespace
    namespace = {{"inputs": inputs, "storages": storages, "files": files, "__builtins__": __builtins__}}
    exec(compile(user_code, "script.py", "exec"), namespace)

    # Call main() if defined, otherwise pass inputs through.
    # Supports four signatures (in priority order):
    #   def main(inputs, storages, files)  ← v0.2+, opt-in
    #   def main(inputs, storages)         ← legacy, still works unchanged
    #   def main(inputs)
    #   def main()
    if "main" in namespace and callable(namespace["main"]):
        import inspect
        sig = inspect.signature(namespace["main"])
        param_count = len(sig.parameters)
        if param_count >= 3:
            result = namespace["main"](inputs, storages, files)
        elif param_count == 2:
            result = namespace["main"](inputs, storages)
        elif param_count == 1:
            result = namespace["main"](inputs)
        else:
            # main() takes no arguments
            result = namespace["main"]()
    elif "output" in namespace:
        result = namespace["output"]
    else:
        result = inputs

    return result

try:
    result = run()
    # Ensure result is JSON-serialisable
    output = {{"output": result, "output_type": "text"}}
    print(json.dumps(output, default=str))
except Exception as e:
    err = {{"output": None, "output_type": "text", "error": str(e), "traceback": traceback.format_exc()}}
    print(json.dumps(err, default=str), file=sys.stderr)
    sys.exit(1)
'''
    
    def _write_storage_client(self, temp_dir: str) -> None:
        """Write storage_client.py to temp_dir for Python nodes to use"""
        # Read the actual storage_client.py file content
        import pathlib
        storage_client_path = pathlib.Path(__file__).parent.parent / "storage" / "storage_client.py"
        
        if storage_client_path.exists():
            # Copy the actual file
            import shutil
            shutil.copy(storage_client_path, pathlib.Path(temp_dir) / "storage_client.py")
        else:
            # Fallback: write minimal version (should not happen)
            logger.warning("storage_client.py not found, writing minimal version")
            minimal_client = '''\
class StorageClient:
    def __init__(self, storage_type, config):
        raise NotImplementedError("Storage client not properly installed")
'''
            Path(temp_dir, "storage_client.py").write_text(minimal_client)

    def _build_sandbox_volumes(self, workspace_id: Optional[str]) -> Dict[str, Dict[str, str]]:
        """Build the bind-mount dict for a Custom Python sandbox.

        Three mount points (sandbox-realm paths on the right):
            ${HOST_WORKSPACE_ROOT}/<wid>/files → /workspace/files (rw, per-workspace)
            ${HOST_STORAGE_ROOT}              → /storage         (ro, shared)
            ${HOST_CACHE_ROOT}                → /cache           (rw, transient)

        The /workspace/files mount is added only when workspace_id is provided
        (legacy callers that don't pass it get the other two mounts only).

        Returns an empty dict if config doesn't have host_*_root settings — keeps
        backward compatibility with deployments that don't have HOST_* env vars.
        """
        try:
            from config.settings import get_settings
            s = get_settings()
        except Exception as e:
            logger.warning(f"Could not load settings for sandbox volumes: {e}")
            return {}

        volumes: Dict[str, Dict[str, str]] = {}

        host_storage = getattr(s, "host_storage_root", None)
        if host_storage:
            volumes[host_storage] = {"bind": "/storage", "mode": "ro"}

        host_cache = getattr(s, "host_cache_root", None)
        if host_cache:
            volumes[host_cache] = {"bind": "/cache", "mode": "rw"}

        host_workspace = getattr(s, "host_workspace_root", None)
        if host_workspace and workspace_id:
            ws_files_path = f"{host_workspace}/{workspace_id}/files"
            volumes[ws_files_path] = {"bind": "/workspace/files", "mode": "rw"}

        return volumes

    def _write_files_helper(self, temp_dir: str) -> None:
        """Write files_helper.py to temp_dir so the sandbox can import FilesHelper.

        Mirrors the storage_client copy pattern: reads the canonical file from
        the backend's source tree and copies it next to script.py + wrapper.py.
        """
        import pathlib
        files_helper_path = pathlib.Path(__file__).parent / "files_helper.py"

        if files_helper_path.exists():
            import shutil
            shutil.copy(files_helper_path, pathlib.Path(temp_dir) / "files_helper.py")
        else:
            # Fallback: write a minimal version with the same SAFE_ROOTS contract.
            logger.warning("files_helper.py not found, writing minimal version")
            minimal_helper = '''\
class FilesHelper:
    def __init__(self):
        raise NotImplementedError("FilesHelper not properly installed")
'''
            Path(temp_dir, "files_helper.py").write_text(minimal_helper)

    def _build_command(self, requirements: str) -> list:
        """Build the shell command to run inside the container."""
        if requirements.strip():
            # Check if playwright is in requirements (case-insensitive)
            requirements_lower = requirements.lower()
            has_playwright = "playwright" in requirements_lower
            
            # Build pip install command
            pip_cmd = "pip install --quiet --no-cache-dir -r /workspace/requirements.txt"
            
            # Add playwright install if needed
            post_install_cmd = ""
            if has_playwright:
                post_install_cmd = " && playwright install --with-deps"
            
            # Install deps, run post-install commands (if any), then run wrapper
            return [
                "sh", "-c",
                f"{pip_cmd}{post_install_cmd} && python /workspace/wrapper.py"
            ]
        return ["python", "/workspace/wrapper.py"]

    def _copy_to_container(self, container, src_dir: str, dst_path: str) -> None:
        """
        Use ``container.put_archive`` to copy *src_dir* contents into *dst_path*.

        This avoids the DooD volume-mount path mismatch entirely because
        the archive is streamed via the Docker API, not the filesystem.
        
        Also copies storage backend implementations to services/storage/ in container.
        """
        import tarfile
        import io
        import pathlib

        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            # Add workspace files (script.py, wrapper.py, inputs.json, requirements.txt, storage_client.py)
            for entry in os.listdir(src_dir):
                full = os.path.join(src_dir, entry)
                tar.add(full, arcname=entry)
            
            # Add storage backend implementations to services/storage/ in container
            # These are needed by storage_client.py
            storage_dir = pathlib.Path(__file__).parent.parent / "storage"
            if storage_dir.exists():
                # Create services/storage directory structure
                for storage_file in storage_dir.glob("*.py"):
                    if storage_file.name not in ["__init__.py", "manager.py", "storage_client.py"]:
                        # Add as services/storage/filename.py
                        tar.add(str(storage_file), arcname=f"services/storage/{storage_file.name}")
                
                # Also add base.py which is needed by all backends
                base_file = storage_dir.parent / "storage" / "base.py"
                if base_file.exists():
                    tar.add(str(base_file), arcname="services/storage/base.py")
        
        buf.seek(0)
        container.put_archive(dst_path, buf)

    def _parse_output(self, logs: str) -> Dict[str, Any]:
        """Parse the last line of stdout as JSON; fall back to raw text."""
        lines = logs.strip().split("\n")
        # Walk backwards to find the JSON output line
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                return {
                    "output": data.get("output", data),
                    "output_type": data.get("output_type", "text"),
                    "error": data.get("error"),
                }
            except json.JSONDecodeError:
                continue

        # No JSON found – return raw logs
        return {"output": logs, "output_type": "text", "error": None}

    async def _ensure_image(self) -> None:
        """Pull the base image if not already present.

        issue16: docker-py is sync; wrap in to_thread so the event loop and
        Temporal heartbeats stay live during the (potentially long) pull.
        """
        try:
            await asyncio.to_thread(self.client.images.get, self.image)
        except docker.errors.ImageNotFound:
            logger.info(f"Pulling image {self.image} …")
            await asyncio.to_thread(self.client.images.pull, self.image)
            logger.info(f"Image {self.image} pulled successfully")
