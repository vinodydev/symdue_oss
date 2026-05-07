# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Symdue contributors
"""
Zero-config helper for ad-hoc local-filesystem reads inside a Custom Python node.

This class is *embedded* into the run-script template generated for each
sandbox spawn (see executor.py). It is also imported directly here so it can
be unit-tested without spawning a container.

Path semantics are sandbox-realm: SAFE_ROOTS lists the four mount points
that the executor bind-mounts into every sandbox. Reading or writing outside
those roots raises PermissionError.

For Google Drive, S3, etc. use storages[alias] (configured backends).
"""
import csv
import io
import json
from pathlib import Path
from typing import Any, List


# Sandbox-realm safe roots. These match the bind-mounts the executor adds
# when spawning a Custom Python sandbox:
#   /workspace/files  ← per-workspace files dir, read-write, persists
#   /storage          ← shared storage (local_file_storage backend), read-only
#   /cache            ← pip + intermediate cache, read-write
#   /tmp              ← per-run scratch, dies with the container
SAFE_ROOTS = ("/workspace/files", "/storage", "/cache", "/tmp")


class FilesHelper:
    """Stateless helper for reading files from sandbox-mounted directories."""

    def _resolve(self, p: str) -> Path:
        """Resolve a path and assert it falls under SAFE_ROOTS.

        Raises:
            PermissionError: path resolves outside the allowed roots.
        """
        path = Path(p).resolve()
        s = str(path)
        if not any(s == root or s.startswith(root + "/") for root in SAFE_ROOTS):
            raise PermissionError(
                f"path outside allowed roots: {p} "
                f"(allowed: {', '.join(SAFE_ROOTS)})"
            )
        return path

    def exists(self, p: str) -> bool:
        """True if the path exists and is under a safe root."""
        try:
            return self._resolve(p).exists()
        except PermissionError:
            return False

    def read_text(self, p: str, encoding: str = "utf-8") -> str:
        """Return the file's contents as text."""
        return self._resolve(p).read_text(encoding=encoding)

    def read_bytes(self, p: str) -> bytes:
        """Return the file's contents as bytes."""
        return self._resolve(p).read_bytes()

    def read_json(self, p: str) -> Any:
        """Parse the file as JSON and return the deserialized object."""
        return json.loads(self.read_text(p))

    def read_csv(self, p: str) -> List[dict]:
        """Parse the file as CSV with a header row, return list of dicts."""
        return list(csv.DictReader(io.StringIO(self.read_text(p))))

    def list_dir(self, p: str, suffix: str = "") -> List[str]:
        """List files in a directory.

        Args:
            p: directory path (must resolve under SAFE_ROOTS).
            suffix: optional filename-suffix filter (e.g. ".json").

        Returns:
            Sorted list of absolute file paths (directories excluded).
        """
        d = self._resolve(p)
        if not d.is_dir():
            raise NotADirectoryError(f"not a directory: {p}")
        return sorted(
            str(f) for f in d.iterdir()
            if f.is_file() and (not suffix or f.name.endswith(suffix))
        )
