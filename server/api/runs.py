# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Run execution API endpoints (with Temporal integration)
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from uuid import UUID
import logging

from database.connection import get_db, SessionLocal
from database.models import Workflow, RunHistory
from schemas.run import RunCreate, RunResponse, ResumeRunCreate
from services.workspace.graph_builder import build_graph_json
from services.temporal.client import TemporalClient
from services.temporal.workflows.graph_executor import GraphExecutorWorkflow

logger = logging.getLogger(__name__)
router = APIRouter()


async def start_temporal_workflow(
    run_id: str,
    workflow_id: str,
    inputs: Dict[str, Any],
):
    """
    Start Temporal workflow for graph execution.

    Runs as a FastAPI background task.  Uses its own DB session
    so it is independent of the request lifecycle.
    """
    db = SessionLocal()
    try:
        logger.info(f"Starting Temporal workflow for run {run_id}")

        # Build graph JSON from database
        graph_json = build_graph_json(UUID(workflow_id), db)
        logger.info(
            f"Graph built: {len(graph_json.get('nodes', []))} nodes, "
            f"{len(graph_json.get('edges', []))} edges"
        )

        if not graph_json.get("nodes"):
            raise ValueError("Graph has no nodes — nothing to execute")

        # Load per-workflow execution config (timeouts)
        workflow_row = db.query(Workflow).filter(
            Workflow.id == UUID(workflow_id),
            Workflow.deleted_at.is_(None),
        ).first()
        execution_config = (workflow_row.execution_config or {}) if workflow_row else {}

        # Get Temporal client
        client = await TemporalClient.get_client()

        # Start workflow — use `args=` for multiple positional params
        workflow_handle = await client.start_workflow(
            GraphExecutorWorkflow.run,
            args=[workflow_id, graph_json, inputs, run_id, None, execution_config],
            id=f"graph-execution-{run_id}",
            task_queue="graph-execution",
        )

        logger.info(f"Workflow started: {workflow_handle.id}")

        # Update run record with Temporal workflow ID and status
        run = db.query(RunHistory).filter(RunHistory.id == UUID(run_id)).first()
        if run:
            run.temporal_workflow_id = workflow_handle.id
            run.status = "running"
            db.commit()
            logger.info(f"Run {run_id} updated: temporal_workflow_id={workflow_handle.id}")

    except Exception as e:
        logger.error(f"Failed to start Temporal workflow for run {run_id}: {e}", exc_info=True)
        # Update run status to error
        try:
            run = db.query(RunHistory).filter(RunHistory.id == UUID(run_id)).first()
            if run:
                run.status = "error"
                run.error_message = str(e)
                db.commit()
        except Exception as db_err:
            logger.error(f"Failed to update run error status: {db_err}")
    finally:
        db.close()


def _downstream_node_ids(graph_json: Dict[str, Any], from_node_id: str) -> set:
    """Return set of node ids reachable from from_node_id (including from_node_id)."""
    edges = graph_json.get("edges", [])
    children_map: Dict[str, list] = {}
    for e in edges:
        src, tgt = str(e.get("source")), str(e.get("target"))
        children_map.setdefault(src, []).append(tgt)
    out = {from_node_id}
    queue = [from_node_id]
    while queue:
        nid = queue.pop()
        for c in children_map.get(nid, []):
            if c not in out:
                out.add(c)
                queue.append(c)
    return out


def _parent_workflow_id(run: RunHistory, db: Session) -> Optional[UUID]:
    """Return workflow_id of the parent run when run.parent_run_id is set."""
    if not run.parent_run_id:
        return None
    parent = db.query(RunHistory).filter(RunHistory.id == run.parent_run_id).first()
    return parent.workflow_id if parent else None


async def start_temporal_workflow_resume(
    new_run_id: str,
    workflow_id: str,
    from_run_id: str,
    inputs_override: Optional[Dict[str, Any]] = None,
    start_from_node_id: Optional[str] = None,
):
    """
    Start Temporal workflow for a run that resumes from a previous run's checkpoint.
    Uses snapshot from from_run_id as initial_state; optionally clears from a node onward.
    """
    db = SessionLocal()
    try:
        from_run = db.query(RunHistory).filter(
            RunHistory.id == UUID(from_run_id),
            RunHistory.workflow_id == UUID(workflow_id),
        ).first()
        if not from_run or not from_run.snapshot:
            raise ValueError("Source run not found or has no snapshot")
        snapshot = from_run.snapshot if isinstance(from_run.snapshot, dict) else {}
        node_outputs = dict(snapshot.get("node_outputs") or {})
        inputs = inputs_override if inputs_override is not None else snapshot.get("inputs") or {}
        node_name_map = dict(snapshot.get("node_name_map") or {})

        graph_json = build_graph_json(UUID(workflow_id), db)
        if start_from_node_id:
            to_remove = _downstream_node_ids(graph_json, start_from_node_id)
            names_to_remove = {node_name_map.get(nid, nid) for nid in to_remove}
            for nid in to_remove:
                node_outputs.pop(nid, None)
            for name in names_to_remove:
                node_outputs.pop(name, None)

        initial_state = {
            "inputs": inputs,
            "node_outputs": node_outputs,
            "node_name_map": node_name_map,
            "node_inputs": snapshot.get("node_inputs") or {},
        }
        if snapshot.get("next_node_id"):
            initial_state["_resume_next_node"] = snapshot["next_node_id"]
        if snapshot.get("_step_count") is not None:
            initial_state["_step_count"] = snapshot["_step_count"]

        workflow_row = db.query(Workflow).filter(
            Workflow.id == UUID(workflow_id),
            Workflow.deleted_at.is_(None),
        ).first()
        execution_config = (workflow_row.execution_config or {}) if workflow_row else {}

        client = await TemporalClient.get_client()
        workflow_handle = await client.start_workflow(
            GraphExecutorWorkflow.run,
            args=[workflow_id, graph_json, inputs, new_run_id, initial_state, execution_config],
            id=f"graph-execution-{new_run_id}",
            task_queue="graph-execution",
        )
        run = db.query(RunHistory).filter(RunHistory.id == UUID(new_run_id)).first()
        if run:
            run.temporal_workflow_id = workflow_handle.id
            run.status = "running"
            db.commit()
        logger.info(f"Resume workflow started: {workflow_handle.id} from run {from_run_id}")
    except Exception as e:
        logger.error(f"Failed to start resume workflow for run {new_run_id}: {e}", exc_info=True)
        try:
            r = db.query(RunHistory).filter(RunHistory.id == UUID(new_run_id)).first()
            if r:
                r.status = "error"
                r.error_message = str(e)
                db.commit()
        except Exception as db_err:
            logger.error(f"Failed to update run error status: {db_err}")
    finally:
        db.close()


@router.post("/runs/{workspace_id}", response_model=RunResponse, status_code=201)
async def create_run(
    workspace_id: UUID,
    run: RunCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Create a new run for a workspace (starts Temporal workflow)"""
    # Verify workspace exists
    workflow = (
        db.query(Workflow)
        .filter(Workflow.id == workspace_id, Workflow.deleted_at.is_(None))
        .first()
    )

    if not workflow:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Create run record
    db_run = RunHistory(
        workflow_id=workspace_id,
        status="queued",
        snapshot={},  # Will be populated during execution
    )
    db.add(db_run)
    db.commit()
    db.refresh(db_run)

    # Merge inputs and external_input (same contract as sub-workflow; edge nodes use keys from this dict)
    final_inputs = dict(run.inputs or {})
    if run.external_input:
        final_inputs = {**final_inputs, **run.external_input}

    # Start Temporal workflow in background (pass serialisable IDs, not ORM objects)
    background_tasks.add_task(
        start_temporal_workflow,
        str(db_run.id),
        str(workspace_id),
        final_inputs,
    )

    return RunResponse(
        run_id=db_run.id,
        status=db_run.status,
        workflow_id=db_run.workflow_id,
        temporal_workflow_id=db_run.temporal_workflow_id,
        parent_run_id=db_run.parent_run_id,
        parent_workflow_id=None,
        snapshot=db_run.snapshot,
    )


@router.post("/runs/{workspace_id}/resume-from", response_model=RunResponse, status_code=201)
async def create_run_resume_from(
    workspace_id: UUID,
    body: ResumeRunCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Create a new run that resumes from a previous run's checkpoint (without re-running completed nodes)."""
    workflow = (
        db.query(Workflow)
        .filter(Workflow.id == workspace_id, Workflow.deleted_at.is_(None))
        .first()
    )
    if not workflow:
        raise HTTPException(status_code=404, detail="Workspace not found")

    from_run = (
        db.query(RunHistory)
        .filter(
            RunHistory.id == body.from_run_id,
            RunHistory.workflow_id == workspace_id,
        )
        .first()
    )
    if not from_run:
        raise HTTPException(status_code=404, detail="Source run not found")
    if from_run.status not in ("error", "cancelled", "partial"):
        raise HTTPException(
            status_code=400,
            detail=f"Can only resume from runs with status error, cancelled, or partial (got {from_run.status})",
        )
    snapshot = from_run.snapshot if isinstance(from_run.snapshot, dict) else {}
    if not snapshot.get("node_outputs"):
        raise HTTPException(
            status_code=400,
            detail="Source run has no node outputs to resume from (partial state not saved)",
        )

    db_run = RunHistory(
        workflow_id=workspace_id,
        status="queued",
        snapshot={},
        parent_run_id=body.from_run_id,
    )
    db.add(db_run)
    db.commit()
    db.refresh(db_run)

    inputs_override = body.inputs if body.inputs is not None else None
    background_tasks.add_task(
        start_temporal_workflow_resume,
        str(db_run.id),
        str(workspace_id),
        str(body.from_run_id),
        inputs_override,
        body.start_from_node_id,
    )

    return RunResponse(
        run_id=db_run.id,
        status=db_run.status,
        workflow_id=db_run.workflow_id,
        temporal_workflow_id=db_run.temporal_workflow_id,
        parent_run_id=db_run.parent_run_id,
        parent_workflow_id=None,
        snapshot=db_run.snapshot,
    )


@router.get("/runs/{workspace_id}", response_model=List[RunResponse])
async def list_runs(
    workspace_id: UUID,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """List all runs for a workspace"""
    workflow = (
        db.query(Workflow)
        .filter(Workflow.id == workspace_id, Workflow.deleted_at.is_(None))
        .first()
    )

    if not workflow:
        raise HTTPException(status_code=404, detail="Workspace not found")

    runs = (
        db.query(RunHistory)
        .filter(RunHistory.workflow_id == workspace_id)
        .order_by(RunHistory.started_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )

    return [
        RunResponse(
            run_id=run.id,
            status=run.status,
            workflow_id=run.workflow_id,
            temporal_workflow_id=run.temporal_workflow_id,
            parent_run_id=run.parent_run_id,
            parent_workflow_id=_parent_workflow_id(run, db),
            started_at=run.started_at.isoformat() if run.started_at else None,
            completed_at=run.completed_at.isoformat() if run.completed_at else None,
            duration=run.duration,
            error_message=run.error_message,
            snapshot=run.snapshot,
        )
        for run in runs
    ]


@router.get("/runs/{workspace_id}/{run_id}", response_model=RunResponse)
async def get_run(
    workspace_id: UUID,
    run_id: UUID,
    db: Session = Depends(get_db),
):
    """Get a run by ID"""
    run = (
        db.query(RunHistory)
        .filter(RunHistory.id == run_id, RunHistory.workflow_id == workspace_id)
        .first()
    )

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    parent_workflow_id = None
    if run.parent_run_id:
        parent_run = (
            db.query(RunHistory)
            .filter(RunHistory.id == run.parent_run_id)
            .first()
        )
        if parent_run:
            parent_workflow_id = parent_run.workflow_id

    return RunResponse(
        run_id=run.id,
        status=run.status,
        workflow_id=run.workflow_id,
        temporal_workflow_id=run.temporal_workflow_id,
        parent_run_id=run.parent_run_id,
        parent_workflow_id=parent_workflow_id,
        started_at=run.started_at.isoformat() if run.started_at else None,
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
        duration=run.duration,
        error_message=run.error_message,
        snapshot=run.snapshot,
    )


@router.get("/runs/{workspace_id}/{run_id}/temporal-status")
async def get_temporal_workflow_status(
    workspace_id: UUID,
    run_id: UUID,
    db: Session = Depends(get_db),
):
    """Get Temporal workflow status for a run (for debugging)"""
    run = (
        db.query(RunHistory)
        .filter(RunHistory.id == run_id, RunHistory.workflow_id == workspace_id)
        .first()
    )

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    if not run.temporal_workflow_id:
        return {
            "temporal_workflow_id": None,
            "temporal_status": "not_started",
            "db_status": run.status,
            "error_message": run.error_message,
        }

    try:
        client = await TemporalClient.get_client()
        handle = client.get_workflow_handle(run.temporal_workflow_id)
        desc = await handle.describe()

        return {
            "temporal_workflow_id": run.temporal_workflow_id,
            "temporal_status": desc.status.name,
            "db_status": run.status,
            "run_id": str(desc.run_id) if desc.run_id else None,
            "start_time": desc.start_time.isoformat() if desc.start_time else None,
            "close_time": desc.close_time.isoformat() if desc.close_time else None,
        }
    except Exception as e:
        return {
            "temporal_workflow_id": run.temporal_workflow_id,
            "temporal_status": "query_error",
            "db_status": run.status,
            "error": str(e),
        }


@router.get("/runs/{workspace_id}/{run_id}/nodes/{node_id}/logs")
async def get_node_logs(
    workspace_id: UUID,
    run_id: UUID,
    node_id: str,
    db: Session = Depends(get_db),
):
    """Get logs for a specific node in a run"""
    run = (
        db.query(RunHistory)
        .filter(RunHistory.id == run_id, RunHistory.workflow_id == workspace_id)
        .first()
    )

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Extract logs from snapshot
    snapshot = run.snapshot or {}
    node_outputs = snapshot.get("node_outputs", {})
    
    # Try to get logs from node output (by node_id or node_name)
    node_output = node_outputs.get(node_id, {})
    
    # If not found by ID, try to find by name (node outputs are stored by both)
    if not node_output or not isinstance(node_output, dict):
        # Search through all outputs to find matching node
        for key, value in node_outputs.items():
            if isinstance(value, dict) and value.get("node_id") == node_id:
                node_output = value
                break
    
    # Extract logs
    logs = ""
    if isinstance(node_output, dict):
        logs = node_output.get("logs", "")
        # If no logs in output, check if there's an error with logs
        if not logs and node_output.get("error"):
            error_data = node_output.get("error", {})
            if isinstance(error_data, dict):
                logs = error_data.get("logs", "")
    
    return {
        "node_id": node_id,
        "run_id": str(run_id),
        "logs": logs or "No logs available for this node",
        "has_logs": bool(logs)
    }


@router.post("/runs/{workspace_id}/{run_id}/cancel", status_code=200)
async def cancel_run(
    workspace_id: UUID,
    run_id: UUID,
    db: Session = Depends(get_db),
):
    """Cancel a running workflow"""
    run = (
        db.query(RunHistory)
        .filter(RunHistory.id == run_id, RunHistory.workflow_id == workspace_id)
        .first()
    )

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    if run.status not in ["running", "partial", "queued", "paused", "waiting"]:
        raise HTTPException(status_code=400, detail="Run is not in a cancellable state")

    # Cancel Temporal workflow
    if run.temporal_workflow_id:
        try:
            client = await TemporalClient.get_client()
            workflow_handle = client.get_workflow_handle(run.temporal_workflow_id)
            await workflow_handle.cancel()
        except Exception as e:
            logger.error(f"Failed to cancel Temporal workflow: {e}")

    # Update status
    from sqlalchemy.sql import func

    run.status = "cancelled"
    run.cancellation_requested_at = func.now()
    db.commit()

    # Broadcast WORKFLOW_STATUS so other clients update without a refresh.
    try:
        from services.temporal.activities.node_executor import publish_node_status
        await publish_node_status(str(run_id), "__workflow__", "cancelled")
    except Exception as e:
        logger.warning(f"Failed to publish cancel status: {e}")

    return {"message": "Run cancellation requested"}


@router.post("/runs/{workspace_id}/{run_id}/pause", status_code=200)
async def pause_run(
    workspace_id: UUID,
    run_id: UUID,
    db: Session = Depends(get_db),
):
    """Pause a running workflow"""
    run = (
        db.query(RunHistory)
        .filter(RunHistory.id == run_id, RunHistory.workflow_id == workspace_id)
        .first()
    )

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    if run.status not in ["running", "queued"]:
        raise HTTPException(status_code=400, detail="Run is not in a pausable state")

    # Send pause signal to Temporal workflow
    if run.temporal_workflow_id:
        try:
            client = await TemporalClient.get_client()
            workflow_handle = client.get_workflow_handle(run.temporal_workflow_id)
            await workflow_handle.signal("pause_signal")
            logger.info(f"Pause signal sent to workflow {run.temporal_workflow_id}")
        except Exception as e:
            logger.error(f"Failed to pause Temporal workflow: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to pause workflow: {e}")

    # Update status to paused (will be confirmed by workflow status update)
    run.status = "paused"
    db.commit()

    try:
        from services.temporal.activities.node_executor import publish_node_status
        await publish_node_status(str(run_id), "__workflow__", "paused")
    except Exception as e:
        logger.warning(f"Failed to publish pause status: {e}")

    return {"message": "Run pause requested", "status": "paused"}


@router.post("/runs/{workspace_id}/{run_id}/resume", status_code=200)
async def resume_run(
    workspace_id: UUID,
    run_id: UUID,
    db: Session = Depends(get_db),
):
    """Resume a paused workflow"""
    run = (
        db.query(RunHistory)
        .filter(RunHistory.id == run_id, RunHistory.workflow_id == workspace_id)
        .first()
    )

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    if run.status != "paused":
        raise HTTPException(status_code=400, detail="Run is not in a paused state")

    # Send resume signal to Temporal workflow
    if run.temporal_workflow_id:
        try:
            client = await TemporalClient.get_client()
            workflow_handle = client.get_workflow_handle(run.temporal_workflow_id)
            await workflow_handle.signal("resume_signal")
            logger.info(f"Resume signal sent to workflow {run.temporal_workflow_id}")
        except Exception as e:
            logger.error(f"Failed to resume Temporal workflow: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to resume workflow: {e}")

    # Update status to running (will be confirmed by workflow status update)
    run.status = "running"
    db.commit()

    try:
        from services.temporal.activities.node_executor import publish_node_status
        await publish_node_status(str(run_id), "__workflow__", "running")
    except Exception as e:
        logger.warning(f"Failed to publish resume status: {e}")

    return {"message": "Run resume requested", "status": "running"}
