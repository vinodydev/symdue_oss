# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
WorkflowWait model — tracks wait node subscriptions.
"""
from sqlalchemy import Column, String, Boolean, UniqueConstraint, Index, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from sqlalchemy.sql import func
import uuid
from database.base import Base


class WorkflowWait(Base):
    """
    Tracks a wait node's subscription to a signal channel within a run.
    A row exists for every wait node that has been reached but not yet satisfied.
    """
    __tablename__ = "workflow_waits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("run_history.id"), nullable=False)
    node_id = Column(String, nullable=False)

    # Channel name this wait is subscribed to
    channel = Column(String, nullable=False)

    # Wait mode: signal | any | all | time | until
    mode = Column(String, nullable=False, default="signal")

    # Signal name(s) to match (used for signal / any / all modes)
    signals_needed = Column(JSONB, nullable=True)

    # Signal names that have been received so far (used for "all" mode)
    signals_received = Column(JSONB, nullable=True, default=list)

    # Optional wall-clock timeout
    timeout_at = Column(TIMESTAMP, nullable=True)

    # Whether this wait has been satisfied
    satisfied = Column(Boolean, nullable=False, default=False)
    satisfied_at = Column(TIMESTAMP, nullable=True)

    created_at = Column(TIMESTAMP, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("run_id", "node_id", name="uq_workflow_wait_run_node"),
        Index("ix_workflow_waits_channel", "channel"),
    )
