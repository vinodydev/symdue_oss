# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Temporal client setup
"""
from temporalio.client import Client
from typing import Any, Optional
from config.settings import get_settings
import logging

logger = logging.getLogger(__name__)


class TemporalClient:
    """Singleton Temporal client"""
    _instance: Optional[Client] = None

    @classmethod
    async def get_client(cls) -> Client:
        """Get or create Temporal client"""
        if cls._instance is None:
            settings = get_settings()
            target = f"{settings.temporal_host}:{settings.temporal_port}"
            logger.info(f"Connecting to Temporal at {target} (namespace={settings.temporal_namespace})")
            cls._instance = await Client.connect(
                target,
                namespace=settings.temporal_namespace
            )
            logger.info("Temporal client connected successfully")
        return cls._instance

    @classmethod
    async def send_receive_signal(
        cls,
        run_id: str,
        node_id: str,
        signal: str,
        data: Any,
        db=None,
    ) -> bool:
        """
        Send a receive_signal Temporal signal to the workflow identified by run_id.
        Returns True on success, False if the run is not found or has no workflow ID.
        """
        from database.models import RunHistory
        from uuid import UUID

        if db is None:
            from database.connection import SessionLocal
            db_local = SessionLocal()
            close_db = True
        else:
            db_local = db
            close_db = False

        try:
            run = db_local.query(RunHistory).filter(RunHistory.id == UUID(run_id)).first()
            if not run or not run.temporal_workflow_id:
                logger.warning(f"send_receive_signal: run={run_id} not found or has no workflow ID")
                return False

            client = await cls.get_client()
            handle = client.get_workflow_handle(run.temporal_workflow_id)
            await handle.signal(
                "receive_signal",
                args=[node_id, signal, data],
            )
            logger.info(
                f"Sent receive_signal to run={run_id} workflow={run.temporal_workflow_id} "
                f"node={node_id} signal={signal}"
            )
            return True
        except Exception as exc:
            logger.error(f"send_receive_signal failed for run={run_id}: {exc}", exc_info=True)
            return False
        finally:
            if close_db:
                db_local.close()

    @classmethod
    async def close(cls):
        """Close Temporal client (cleanup singleton)"""
        if cls._instance is not None:
            # Temporal Python SDK Client doesn't have an explicit close() —
            # dropping the reference is enough. We just reset the singleton.
            cls._instance = None
            logger.info("Temporal client reference cleared")
