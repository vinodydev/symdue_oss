# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Event scheduler — background asyncio task that fires interval/cron events on schedule.
"""
import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_scheduler_task: Optional[asyncio.Task] = None

POLL_INTERVAL_SECONDS = 15


def _parse_interval(schedule: str) -> Optional[timedelta]:
    """Parse duration strings like '30s', '5m', '2h' into timedelta."""
    if not schedule:
        return None
    match = re.match(r"^(\d+)(s|m|h)$", schedule.strip())
    if not match:
        return None
    val, unit = int(match.group(1)), match.group(2)
    seconds = val if unit == "s" else val * 60 if unit == "m" else val * 3600
    return timedelta(seconds=seconds)


def _cron_is_due(cron_expr: str, now: datetime, last_run_at: Optional[datetime]) -> bool:
    """Check if a cron expression is due to fire."""
    try:
        from croniter import croniter
    except ImportError:
        logger.warning("croniter not installed — cron events cannot fire")
        return False

    try:
        # Get the next fire time starting from 1 minute before now
        base = now - timedelta(minutes=1)
        c = croniter(cron_expr, base)
        next_time = c.get_next(datetime)
        is_due = next_time <= now

        # Guard against double-fire within the same minute
        if is_due and last_run_at:
            elapsed = (now - last_run_at).total_seconds()
            if elapsed < 55:
                return False

        return is_due
    except Exception as exc:
        logger.error(f"Invalid cron expression '{cron_expr}': {exc}")
        return False


async def _scheduler_loop():
    """Main scheduler loop — polls enabled interval/cron events and fires them."""
    from database.connection import SessionLocal
    from database.models.event import Event
    from api.event_runner import run_event_script

    logger.info("Event scheduler loop started")

    while True:
        try:
            db = SessionLocal()
            try:
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                events = (
                    db.query(Event)
                    .filter(Event.enabled.is_(True), Event.type.in_(["interval", "cron"]))
                    .all()
                )

                for event in events:
                    should_fire = False

                    if event.type == "interval":
                        interval = _parse_interval(event.schedule or "")
                        if interval:
                            if event.last_run_at:
                                elapsed = now - event.last_run_at
                                should_fire = elapsed >= interval
                            else:
                                should_fire = True  # Never run before

                    elif event.type == "cron":
                        if event.schedule:
                            should_fire = _cron_is_due(event.schedule, now, event.last_run_at)

                    if should_fire:
                        try:
                            logger.info(f"Scheduler firing event {event.id} ({event.name})")
                            await run_event_script(
                                event, triggered_by="scheduled", input_data=None, db=db
                            )
                            # Update next_run_at
                            if event.type == "interval":
                                interval = _parse_interval(event.schedule or "")
                                if interval:
                                    event.next_run_at = now + interval
                            elif event.type == "cron":
                                try:
                                    from croniter import croniter

                                    c = croniter(event.schedule, now)
                                    event.next_run_at = c.get_next(datetime)
                                except Exception:
                                    pass
                            db.commit()
                        except Exception as exc:
                            logger.error(
                                f"Scheduler: failed to run event {event.id}: {exc}",
                                exc_info=True,
                            )
            finally:
                db.close()
        except Exception as exc:
            logger.error(f"Scheduler loop error: {exc}", exc_info=True)

        # Sync queue listeners
        try:
            from services.events.queue_listener import sync_listeners
            await sync_listeners()
        except Exception as exc:
            logger.error(f"Queue listener sync error: {exc}", exc_info=True)

        await asyncio.sleep(POLL_INTERVAL_SECONDS)


async def start_scheduler():
    """Start the event scheduler background task."""
    global _scheduler_task
    if _scheduler_task is None or _scheduler_task.done():
        _scheduler_task = asyncio.create_task(_scheduler_loop())
        logger.info("Event scheduler started")


async def stop_scheduler():
    """Stop the event scheduler background task and all queue listeners."""
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
        try:
            await _scheduler_task
        except asyncio.CancelledError:
            pass
        logger.info("Event scheduler stopped")
    _scheduler_task = None

    # Also stop queue listeners
    try:
        from services.events.queue_listener import stop_all_listeners
        await stop_all_listeners()
    except Exception:
        pass
