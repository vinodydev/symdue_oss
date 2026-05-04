"""
EventInvocation model — execution log for a single event run.
"""
from sqlalchemy import Column, String, Integer, Text, Index, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from sqlalchemy.sql import func
import uuid
from database.base import Base


class EventInvocation(Base):
    """
    Records one execution of an Event script.
    """
    __tablename__ = "event_invocations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=False)

    # What triggered this run: scheduled | manual | webhook | queue
    triggered_by = Column(String, nullable=True)

    # Input payload (from webhook / queue body, or manual trigger)
    input = Column(JSONB, nullable=True)

    # Snapshot of event.state before and after execution
    state_before = Column(JSONB, nullable=True)
    state_after = Column(JSONB, nullable=True)

    # Captured stdout / logging output
    log_output = Column(Text, nullable=True)

    # List of {method, args, result} dicts from the RuntimeAPI
    runtime_calls = Column(JSONB, nullable=True)

    # Error information
    error = Column(Text, nullable=True)
    traceback = Column(Text, nullable=True)

    duration_ms = Column(Integer, nullable=True)

    started_at = Column(TIMESTAMP, server_default=func.now())
    completed_at = Column(TIMESTAMP, nullable=True)

    __table_args__ = (
        Index("ix_event_invocations_event_id", "event_id"),
    )
