"""
Event script runner — executes an event's Python script and records the invocation.
"""
import io
import logging
import signal as signal_mod
import sys
import traceback as tb
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def run_event_script(event, triggered_by: str, input_data: Optional[Dict], db) -> Any:
    """
    Execute the event's Python script in a sandboxed local namespace.

    Returns the newly created EventInvocation row.
    """
    from database.models.event_invocation import EventInvocation
    from services.events.runtime_api import RuntimeAPI
    from services.temporal.client import TemporalClient

    started_at = _utcnow()
    state_before = dict(event.state or {})
    log_buffer = io.StringIO()

    # Try to get a Temporal client (may fail if not connected)
    try:
        temporal_client = await TemporalClient.get_client()
    except Exception:
        temporal_client = None

    runtime = RuntimeAPI(db=db, temporal_client=temporal_client, event_id=str(event.id))

    # Redirect stdout to capture print() calls
    old_stdout = sys.stdout
    sys.stdout = log_buffer

    error_msg = None
    traceback_str = None
    state_after = None

    try:
        from config.settings import get_settings
        timeout_sec = get_settings().event_script_timeout_seconds

        # Single namespace so top-level and function bodies both see runtime, logger, etc.
        exec_namespace: Dict[str, Any] = {
            "runtime": runtime,
            "logger": logging.getLogger(f"event.{event.id}"),
            "storage": None,
            "state": dict(event.state or {}),
            "event": {"id": str(event.id), "name": event.name},
            "input": input_data,
        }

        # Enforce script timeout via SIGALRM (Unix only)
        def _timeout_handler(signum, frame):
            raise TimeoutError(f"Event script exceeded {timeout_sec}s timeout")

        prev_handler = signal_mod.signal(signal_mod.SIGALRM, _timeout_handler)
        signal_mod.alarm(timeout_sec)
        try:
            exec(event.script, exec_namespace, exec_namespace)  # noqa: S102
        finally:
            signal_mod.alarm(0)
            signal_mod.signal(signal_mod.SIGALRM, prev_handler)

        state_after = runtime._new_state if runtime._new_state is not None else dict(event.state or {})
    except Exception as exc:
        error_msg = str(exc)
        traceback_str = tb.format_exc()
        logger.error(f"Event {event.id} script error: {error_msg}")
    finally:
        sys.stdout = old_stdout

    completed_at = _utcnow()
    duration_ms = int((completed_at - started_at).total_seconds() * 1000)
    log_output = log_buffer.getvalue()

    # Create invocation record
    invocation = EventInvocation(
        event_id=event.id,
        triggered_by=triggered_by,
        input=input_data,
        state_before=state_before,
        state_after=state_after,
        log_output=log_output or None,
        runtime_calls=runtime._runtime_calls or None,
        error=error_msg,
        traceback=traceback_str,
        duration_ms=duration_ms,
        started_at=started_at,
        completed_at=completed_at,
    )
    db.add(invocation)

    # Update event metadata
    event.last_run_at = completed_at
    if runtime._new_state is not None:
        event.state = runtime._new_state

    db.commit()
    db.refresh(invocation)
    return invocation
