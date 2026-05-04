"""
Graph execution workflow (Temporal)
Orchestrates graph execution via activities. The workflow itself does NO heavy
imports (no langgraph, no langchain, etc.) — all heavy work happens in activities
which run outside the Temporal sandbox.
"""
from temporalio import workflow
from temporalio.common import RetryPolicy
from typing import Dict, Any, Optional
from datetime import timedelta


@workflow.defn
class GraphExecutorWorkflow:
    """
    Temporal workflow that orchestrates graph execution.

    Architecture:
    - Workflow: lightweight orchestrator (no heavy imports)
    - Activities: all I/O, graph compilation, and node execution
    """

    def __init__(self):
        """Initialize workflow state."""
        # Workflow state variables (Temporal handles these correctly)
        self._is_paused = False
        self._pause_requested = False
        self._resume_requested = False
        self._current_run_id = None
        # Wait node support
        self._pending_waits: Dict[str, bool] = {}
        self._pending_signal_data: Dict[str, Any] = {}
        self._saved_graph_state: Optional[Dict] = None

    @workflow.signal
    def pause_signal(self) -> None:
        """Signal to pause the workflow execution."""
        self._pause_requested = True
        workflow.logger.info("Pause signal received")

    @workflow.signal
    def resume_signal(self) -> None:
        """Signal to resume the workflow execution."""
        self._resume_requested = True
        workflow.logger.info("Resume signal received")

    @workflow.signal
    def receive_signal(self, node_id: str, signal: str, data: Any) -> None:
        """Signal received for a wait node — marks the wait as satisfied."""
        self._pending_waits[node_id] = True
        self._pending_signal_data[node_id] = {"signal": signal, "data": data}
        workflow.logger.info(f"Received signal '{signal}' for wait node {node_id}")

    async def _wait_if_paused(self, run_id: str) -> None:
        """Wait if workflow is paused, checking for resume signal."""
        if self._is_paused or self._pause_requested:
            self._is_paused = True
            self._pause_requested = False
            
            # Publish paused status
            await workflow.execute_activity(
                "publish_workflow_status_activity",
                args=[run_id, "paused", {}],
                start_to_close_timeout=timedelta(seconds=10),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=1), maximum_attempts=3
                ),
            )
            
            # Wait for resume signal
            while self._is_paused and not self._resume_requested:
                await workflow.wait_condition(lambda: self._resume_requested, timeout=timedelta(seconds=1))
            
            if self._resume_requested:
                self._is_paused = False
                self._resume_requested = False
                
                # Publish resumed status
                await workflow.execute_activity(
                    "publish_workflow_status_activity",
                    args=[run_id, "running", {}],
                    start_to_close_timeout=timedelta(seconds=10),
                    retry_policy=RetryPolicy(
                        initial_interval=timedelta(seconds=1), maximum_attempts=3
                    ),
                )
                workflow.logger.info("Workflow resumed")

    @workflow.run
    async def run(
        self,
        workflow_id: str,
        graph_json: Dict[str, Any],
        inputs: Dict[str, Any],
        run_id: str,
        initial_state: Optional[Dict[str, Any]] = None,
        execution_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute graph workflow by delegating everything to activities.

        Args:
            workflow_id: Database workflow ID (same as workspace_id)
            graph_json: Graph structure (nodes + edges) from database
            inputs: Input values for input nodes
            run_id: Run history ID for tracking
            initial_state: Optional pre-filled state for resume-from-checkpoint (node_outputs, inputs, node_name_map)
            execution_config: Optional per-workflow timeouts (graph_activity_timeout_minutes, heartbeat_timeout_minutes, etc.)

        Returns:
            Final graph state with all node outputs
        """
        self._current_run_id = run_id
        cfg = execution_config or {}
        graph_timeout_min = int(cfg.get("graph_activity_timeout_minutes", 30))
        heartbeat_timeout_min = int(cfg.get("heartbeat_timeout_minutes", 5))
        
        # 1. Publish "started" status
        await workflow.execute_activity(
            "publish_workflow_status_activity",
            args=[run_id, "started", {}],
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=1), maximum_attempts=3
            ),
        )

        try:
            # Check for pause before execution
            await self._wait_if_paused(run_id)
            
            # 2. Execute the entire graph (with optional initial_state for resume)
            activity_args: list = [workflow_id, graph_json, inputs, run_id]
            if initial_state is not None:
                activity_args.append(initial_state)
            else:
                activity_args.append(None)
            activity_args.append(execution_config)

            final_state = await workflow.execute_activity(
                "execute_graph_activity",
                args=activity_args,
                start_to_close_timeout=timedelta(minutes=graph_timeout_min),
                heartbeat_timeout=timedelta(minutes=heartbeat_timeout_min),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=2),
                    maximum_attempts=2,
                ),
            )
            
            # Check for pause after execution
            await self._wait_if_paused(run_id)

            # 3. Handle suspended state (wait nodes)
            if final_state.get("__suspended__"):
                pending_waits = final_state.get("pending_waits", {})  # {node_id: channel}
                resume_after = final_state.get("resume_after", {})    # {node_id: [target_ids]}

                # Save snapshot with "waiting" status
                await workflow.execute_activity(
                    "save_run_results_activity",
                    args=[run_id, final_state.get("state", {}), "waiting"],
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=RetryPolicy(
                        initial_interval=timedelta(seconds=1), maximum_attempts=3
                    ),
                )
                await workflow.execute_activity(
                    "publish_workflow_status_activity",
                    args=[run_id, "waiting", {}],
                    start_to_close_timeout=timedelta(seconds=10),
                    retry_policy=RetryPolicy(
                        initial_interval=timedelta(seconds=1), maximum_attempts=3
                    ),
                )

                # Set up pending waits dict
                self._pending_waits = {node_id: False for node_id in pending_waits}
                self._pending_signal_data = {}

                # Compute timeout from pending_timeouts (use minimum non-None value)
                pending_timeouts = final_state.get("pending_timeouts", {})
                timeout_values = [v for v in pending_timeouts.values() if v is not None]
                wait_timeout = timedelta(seconds=min(timeout_values)) if timeout_values else None

                # Wait until all pending waits are satisfied (or timeout)
                all_satisfied = await workflow.wait_condition(
                    lambda: all(self._pending_waits.values()),
                    timeout=wait_timeout,
                )

                # If timed out, resolve unsatisfied waits with __timeout__
                if not all_satisfied:
                    for node_id_t, satisfied in self._pending_waits.items():
                        if not satisfied:
                            self._pending_waits[node_id_t] = True
                            self._pending_signal_data[node_id_t] = {
                                "signal": "__timeout__",
                                "data": {"timed_out": True},
                            }
                            workflow.logger.info(
                                f"Wait node {node_id_t} timed out"
                            )

                # Build resume state
                saved_state = final_state.get("state", {})
                node_outputs = dict(saved_state.get("node_outputs", {}))

                # Replace each wait node's suspended marker with its signal payload
                for node_id_w in pending_waits:
                    signal_payload = self._pending_signal_data.get(node_id_w, {})
                    node_outputs[node_id_w] = signal_payload
                    # Also update any name-keyed entry if present
                    node_name_map = saved_state.get("node_name_map", {})
                    node_name = node_name_map.get(node_id_w)
                    if node_name:
                        node_outputs[node_name] = signal_payload

                # Collect all resume entry nodes (downstream of each wait node)
                resume_after_list = []
                for targets in resume_after.values():
                    for t in targets:
                        if t not in resume_after_list:
                            resume_after_list.append(t)

                resume_initial_state = {
                    **saved_state,
                    "node_outputs": node_outputs,
                    "_resume_after_waits": resume_after_list,
                }

                # Reset wait state
                self._pending_waits = {}
                self._pending_signal_data = {}

                # Re-execute from resume point
                activity_args_resume: list = [workflow_id, graph_json, inputs, run_id]
                activity_args_resume.append(resume_initial_state)
                activity_args_resume.append(execution_config)

                final_state = await workflow.execute_activity(
                    "execute_graph_activity",
                    args=activity_args_resume,
                    start_to_close_timeout=timedelta(minutes=graph_timeout_min),
                    heartbeat_timeout=timedelta(minutes=heartbeat_timeout_min),
                    retry_policy=RetryPolicy(
                        initial_interval=timedelta(seconds=2),
                        maximum_attempts=2,
                    ),
                )

                # Check for pause after resume execution
                await self._wait_if_paused(run_id)

            # Save results (activity may return partial state with "error" key on failure or cancellation)
            if final_state.get("error"):
                save_status = "cancelled" if final_state.get("error_type") == "CancelledError" else "error"
                await workflow.execute_activity(
                    "save_run_results_activity",
                    args=[run_id, final_state, save_status],
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=RetryPolicy(
                        initial_interval=timedelta(seconds=1), maximum_attempts=3
                    ),
                )
                await workflow.execute_activity(
                    "publish_workflow_status_activity",
                    args=[run_id, save_status, {"error": final_state.get("error")}],
                    start_to_close_timeout=timedelta(seconds=10),
                    retry_policy=RetryPolicy(
                        initial_interval=timedelta(seconds=1), maximum_attempts=3
                    ),
                )
                return final_state

            # Save final results (success)
            await workflow.execute_activity(
                "save_run_results_activity",
                args=[run_id, final_state, "success"],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=1), maximum_attempts=3
                ),
            )

            # 5. Publish "completed" status
            await workflow.execute_activity(
                "publish_workflow_status_activity",
                args=[run_id, "completed", final_state],
                start_to_close_timeout=timedelta(seconds=10),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=1), maximum_attempts=3
                ),
            )

            return final_state

        except Exception as e:
            # Save error state with detailed info
            error_detail = str(e)
            # Try to extract the root cause from chained exceptions
            cause = getattr(e, "__cause__", None) or getattr(e, "__context__", None)
            if cause:
                error_detail = f"{error_detail} | Caused by: {type(cause).__name__}: {cause}"

            error_state = {
                "inputs": inputs,
                "node_outputs": {},
                "error": error_detail,
                "error_type": type(e).__name__,
                "run_id": run_id,
                "workflow_id": workflow_id,
            }
            await workflow.execute_activity(
                "save_run_results_activity",
                args=[run_id, error_state, "error"],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=1), maximum_attempts=3
                ),
            )
            await workflow.execute_activity(
                "publish_workflow_status_activity",
                args=[run_id, "error", {"error": error_detail}],
                start_to_close_timeout=timedelta(seconds=10),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=1), maximum_attempts=3
                ),
            )
            raise
