"""
Temporal worker for graph execution
Registers workflows and activities with Temporal server
"""
import asyncio
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio.worker.workflow_sandbox import SandboxedWorkflowRunner, SandboxRestrictions
from services.temporal.workflows.graph_executor import GraphExecutorWorkflow
from services.temporal.activities.node_executor import (
    execute_graph_activity,
    execute_python_node_activity,
    execute_llm_node_activity,
    execute_input_node_activity,
    execute_memory_node_activity,
    save_run_results_activity,
    publish_workflow_status_activity,
)
from config.settings import get_settings


async def main():
    """Run Temporal worker"""
    settings = get_settings()

    # Connect to Temporal
    client = await Client.connect(
        f"{settings.temporal_host}:{settings.temporal_port}",
        namespace=settings.temporal_namespace,
    )

    # Create worker — pass typing_extensions through the sandbox to prevent
    # it from corrupting the shared typing module's PEP 696 state.
    worker = Worker(
        client,
        task_queue="graph-execution",
        workflows=[GraphExecutorWorkflow],
        activities=[
            execute_graph_activity,
            execute_python_node_activity,
            execute_llm_node_activity,
            execute_input_node_activity,
            execute_memory_node_activity,
            save_run_results_activity,
            publish_workflow_status_activity,
        ],
        workflow_runner=SandboxedWorkflowRunner(
            restrictions=SandboxRestrictions.default.with_passthrough_modules(
                "typing_extensions",
            )
        ),
    )

    print(f"🚀 Temporal worker started on task queue: graph-execution")
    print(f"   Namespace: {settings.temporal_namespace}")
    print(f"   Host: {settings.temporal_host}:{settings.temporal_port}")

    # Run worker (blocks until shutdown)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
