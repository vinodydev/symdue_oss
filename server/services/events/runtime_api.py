"""
RuntimeAPI — script context object injected into every event script.
"""
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class RuntimeAPI:
    """
    Provides methods accessible as `runtime.*` inside event scripts.
    All calls are recorded in _runtime_calls for auditing.
    """

    def __init__(self, db, temporal_client, event_id: str):
        self._db = db
        self._temporal_client = temporal_client
        self._event_id = event_id
        self._new_state: Optional[Dict] = None
        self._runtime_calls = []

    def _record(self, method: str, args: Dict, result: Any = None) -> None:
        self._runtime_calls.append({"method": method, "args": args, "result": result})

    def emit_to_channel(self, channel: str, data: dict = None) -> int:
        """Broadcast a signal to all workflow runs currently waiting on this channel."""
        import asyncio
        from services.signals.channel_router import emit_to_channel as _emit

        try:
            loop = asyncio.get_event_loop()
            delivered = loop.run_until_complete(
                _emit(channel=channel, signal="event", data=data, db=self._db, temporal_client=self._temporal_client)
            )
        except RuntimeError:
            # We're already inside an event loop — use asyncio.ensure_future
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(
                    asyncio.run,
                    _emit(channel=channel, signal="event", data=data, db=self._db, temporal_client=self._temporal_client),
                )
                delivered = future.result()

        self._record("emit_to_channel", {"channel": channel, "data": data}, delivered)
        return delivered

    def _resolve_workspace(self, name_or_id: str):
        """Resolve a workspace/workflow by UUID or by name."""
        from database.models.workflow import Workflow
        from uuid import UUID as _UUID

        # Try UUID first
        try:
            wid = _UUID(name_or_id)
            wf = self._db.query(Workflow).filter(
                Workflow.id == wid, Workflow.deleted_at.is_(None)
            ).first()
            if wf:
                return wf
        except (ValueError, AttributeError):
            pass

        # Fallback: lookup by name (case-insensitive)
        from sqlalchemy import func
        wf = self._db.query(Workflow).filter(
            func.lower(Workflow.name) == name_or_id.lower(),
            Workflow.deleted_at.is_(None),
        ).first()
        return wf

    def run_workflow(self, name_or_id: str, input: dict = None) -> str:
        """Start a new workflow run. Returns run_id."""
        import asyncio
        from database.models.run import RunHistory
        from api.runs import start_temporal_workflow

        workflow = self._resolve_workspace(name_or_id)
        if not workflow:
            logger.error(f"RuntimeAPI.run_workflow: workflow not found for '{name_or_id}'")
            self._record("run_workflow", {"name_or_id": name_or_id, "input": input}, "")
            return ""

        # Create run record
        db_run = RunHistory(
            workflow_id=workflow.id,
            status="queued",
            snapshot={},
        )
        self._db.add(db_run)
        self._db.commit()
        self._db.refresh(db_run)

        run_id = str(db_run.id)
        workflow_id = str(workflow.id)
        final_input = dict(input or {})

        # Start Temporal workflow (async bridge)
        try:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(
                start_temporal_workflow(run_id, workflow_id, final_input)
            )
        except RuntimeError:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(
                    asyncio.run,
                    start_temporal_workflow(run_id, workflow_id, final_input),
                )
                future.result()

        self._record("run_workflow", {"name_or_id": name_or_id, "input": input}, run_id)
        return run_id

    def get_workflow(self, run_id: str) -> dict:
        """Return the run's current status and output snapshot."""
        from database.models import RunHistory
        from uuid import UUID
        try:
            run = self._db.query(RunHistory).filter(RunHistory.id == UUID(run_id)).first()
            if run:
                result = {"status": run.status, "output": run.snapshot}
            else:
                result = {"status": "not_found", "output": None}
        except Exception as exc:
            result = {"status": "error", "output": None, "error": str(exc)}
        self._record("get_workflow", {"run_id": run_id}, result)
        return result

    def get_state(self) -> dict:
        """Read this event's persistent JSON state."""
        from database.models import Event
        from uuid import UUID
        try:
            event = self._db.query(Event).filter(Event.id == UUID(self._event_id)).first()
            state = dict(event.state or {}) if event else {}
        except Exception:
            state = {}
        self._record("get_state", {}, state)
        return state

    def set_state(self, data: dict) -> None:
        """Write back to this event's persistent state."""
        self._new_state = data
        self._record("set_state", {"data": data})

    def stop_event(self, event_id: str = None) -> None:
        """Disable an event (can stop itself or another event)."""
        from database.models import Event
        from uuid import UUID
        target_id = event_id or self._event_id
        try:
            event = self._db.query(Event).filter(Event.id == UUID(target_id)).first()
            if event:
                event.enabled = False
                self._db.commit()
        except Exception as exc:
            logger.error(f"RuntimeAPI.stop_event failed: {exc}")
        self._record("stop_event", {"event_id": target_id})

    def create_event(self, spec: dict) -> str:
        """Dynamically create and start a new event. Returns event_id."""
        from database.models import Event
        try:
            event = Event(
                name=spec.get("name", "Dynamic Event"),
                type=spec.get("type", "interval"),
                schedule=spec.get("schedule"),
                script=spec.get("script", ""),
                state=spec.get("state"),
                enabled=spec.get("enabled", True),
                queue_name=spec.get("queue_name"),
                webhook_secret=spec.get("webhook_secret"),
            )
            self._db.add(event)
            self._db.commit()
            self._db.refresh(event)
            event_id = str(event.id)
        except Exception as exc:
            logger.error(f"RuntimeAPI.create_event failed: {exc}")
            event_id = ""
        self._record("create_event", {"spec": spec}, event_id)
        return event_id

    def send_signal(self, run_id: str, signal: str, data: dict = None) -> bool:
        """Point-to-point signal to a specific run."""
        import asyncio
        from services.signals.channel_router import resolve_run_signal

        try:
            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(
                resolve_run_signal(run_id=run_id, signal=signal, data=data, db=self._db, temporal_client=self._temporal_client)
            )
        except RuntimeError:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(
                    asyncio.run,
                    resolve_run_signal(run_id=run_id, signal=signal, data=data, db=self._db, temporal_client=self._temporal_client),
                )
                result = future.result()

        self._record("send_signal", {"run_id": run_id, "signal": signal, "data": data}, result)
        return result
