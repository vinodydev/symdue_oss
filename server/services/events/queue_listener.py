# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Queue listener — manages per-event Redis stream listeners for queue-type events.
"""
import asyncio
import logging
from typing import Dict, Optional

import redis.asyncio as aioredis

from config.settings import get_settings

logger = logging.getLogger(__name__)

_listener_tasks: Dict[str, asyncio.Task] = {}


async def _listen_queue(event_id: str, queue_name: str):
    """Listen to a Redis stream for a specific queue-type event."""
    settings = get_settings()
    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    last_id = "$"  # Only new messages (skip backlog)

    logger.info(f"Queue listener started: event={event_id} queue={queue_name}")

    try:
        while True:
            try:
                results = await r.xread({queue_name: last_id}, count=1, block=5000)
                if not results:
                    continue  # Timeout — loop and check again

                for stream_name, messages in results:
                    for msg_id, data in messages:
                        last_id = msg_id
                        logger.info(
                            f"Queue message received: event={event_id} queue={queue_name} msg_id={msg_id}"
                        )
                        # Fire event script with message data as input
                        from database.connection import SessionLocal
                        from database.models.event import Event
                        from api.event_runner import run_event_script

                        db = SessionLocal()
                        try:
                            event = db.query(Event).filter(
                                Event.id == event_id
                            ).first()
                            if event and event.enabled:
                                await run_event_script(
                                    event,
                                    triggered_by="queue",
                                    input_data=dict(data),
                                    db=db,
                                )
                            elif event and not event.enabled:
                                logger.info(
                                    f"Queue event {event_id} is disabled, stopping listener"
                                )
                                return
                        finally:
                            db.close()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error(
                    f"Queue listener error for event={event_id} queue={queue_name}: {exc}",
                    exc_info=True,
                )
                await asyncio.sleep(5)
    except asyncio.CancelledError:
        pass
    finally:
        await r.close()
        logger.info(f"Queue listener stopped: event={event_id} queue={queue_name}")


async def sync_listeners():
    """
    Reconcile running listeners with current enabled queue events.
    Start listeners for new/re-enabled events, stop listeners for disabled/deleted ones.
    """
    from database.connection import SessionLocal
    from database.models.event import Event

    db = SessionLocal()
    try:
        events = (
            db.query(Event)
            .filter(Event.type == "queue", Event.enabled.is_(True))
            .all()
        )
        wanted = {str(e.id): e.queue_name for e in events if e.queue_name}
    finally:
        db.close()

    # Stop listeners for events no longer active
    for eid in list(_listener_tasks):
        if eid not in wanted or _listener_tasks[eid].done():
            task = _listener_tasks.pop(eid)
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    # Start new listeners
    for eid, qname in wanted.items():
        if eid not in _listener_tasks or _listener_tasks[eid].done():
            _listener_tasks[eid] = asyncio.create_task(_listen_queue(eid, qname))


async def stop_all_listeners():
    """Stop all running queue listeners."""
    for eid, task in list(_listener_tasks.items()):
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    _listener_tasks.clear()
