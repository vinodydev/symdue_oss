"""
Channel signal routing — fan-out to waiting runs.
"""
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from database.models.wait import WorkflowWait
from services.signals.wait_service import (
    get_waits_for_channel,
    get_active_waits,
    mark_wait_satisfied,
)

logger = logging.getLogger(__name__)


def _evaluate_signal(wait: WorkflowWait, signal: str, data: Optional[Dict]) -> bool:
    """
    Determine whether *signal* satisfies the given wait.

    Modes:
      signal  — True if signal matches signals_needed[0] (or any signal if list is empty).
      any     — True if signal is in signals_needed.
      all     — Accumulates signals; True once all needed signals have been received.
      time    — Always False (resolved by a timer, not by signal name).
      until   — Always False (resolved by a timer, not by signal name).
      default — True (any signal satisfies).
    """
    mode = wait.mode or "signal"
    needed = list(wait.signals_needed or [])

    if mode == "signal":
        if not needed:
            return True
        return signal == needed[0]

    elif mode == "any":
        if not needed:
            return True
        return signal in needed

    elif mode == "all":
        received = list(wait.signals_received or [])
        if signal not in received:
            received.append(signal)
            wait.signals_received = received
        return all(s in received for s in needed)

    elif mode in ("time", "until"):
        return False

    else:
        # Unknown mode: any signal satisfies
        return True


async def emit_to_channel(
    channel: str,
    signal: str,
    data: Optional[Dict],
    db: Session,
    temporal_client,
) -> int:
    """
    Emit a signal to all active waits on the given channel.
    Returns the count of runs that were notified.
    """
    from config.settings import get_settings
    max_fanout = get_settings().signal_channel_max_fanout

    waits = await get_waits_for_channel(channel, db)
    if len(waits) > max_fanout:
        logger.warning(
            f"Channel {channel} has {len(waits)} waiting runs, exceeding max_fanout={max_fanout}. "
            f"Only first {max_fanout} will be notified."
        )
        waits = waits[:max_fanout]
    notified = 0

    for wait in waits:
        satisfied = _evaluate_signal(wait, signal, data)
        if not satisfied:
            continue

        # Commit any mutations to signals_received before marking satisfied
        db.flush()

        run_id = str(wait.run_id)
        node_id = wait.node_id
        wait_id = str(wait.id)

        await mark_wait_satisfied(wait_id, db)

        # Send Temporal signal to the waiting workflow
        try:
            await temporal_client.send_receive_signal(
                run_id=run_id,
                node_id=node_id,
                signal=signal,
                data=data,
                db=db,
            )
            notified += 1
            logger.info(
                f"Notified run={run_id} node={node_id} via channel={channel} signal={signal}"
            )
        except Exception as exc:
            logger.error(
                f"Failed to send Temporal signal to run={run_id}: {exc}", exc_info=True
            )

    return notified


async def resolve_run_signal(
    run_id: str,
    signal: str,
    data: Optional[Dict],
    db: Session,
    temporal_client,
) -> bool:
    """
    Point-to-point signal resolution: find the matching wait for this run and resolve it.
    Returns True if a wait was found and resolved, False otherwise.
    """
    waits = await get_active_waits(run_id, db)

    for wait in waits:
        satisfied = _evaluate_signal(wait, signal, data)
        if not satisfied:
            continue

        db.flush()

        node_id = wait.node_id
        wait_id = str(wait.id)

        await mark_wait_satisfied(wait_id, db)

        try:
            await temporal_client.send_receive_signal(
                run_id=run_id,
                node_id=node_id,
                signal=signal,
                data=data,
                db=db,
            )
            logger.info(f"Resolved signal for run={run_id} node={node_id} signal={signal}")
            return True
        except Exception as exc:
            logger.error(
                f"Failed to send Temporal signal to run={run_id}: {exc}", exc_info=True
            )
            return False

    logger.info(f"No matching wait found for run={run_id} signal={signal}")
    return False
