"""
Event model — standalone scheduled/triggered scripts.
"""
from sqlalchemy import Column, String, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from sqlalchemy.sql import func
import uuid
from database.base import Base


class Event(Base):
    """
    A standalone event: interval, cron, webhook, or queue triggered script.
    """
    __tablename__ = "events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    name = Column(String, nullable=False)

    # Type: interval | cron | webhook | queue
    type = Column(String, nullable=False)

    # Duration string for interval (e.g. "5m"), cron expression for cron
    schedule = Column(String, nullable=True)

    # Python script body
    script = Column(Text, nullable=False, default="")

    # Persistent JSON state survives restarts
    state = Column(JSONB, nullable=True, default=dict)

    enabled = Column(Boolean, nullable=False, default=True)

    # For queue type: name of queue / stream
    queue_name = Column(String, nullable=True)

    # For webhook type: optional HMAC secret
    webhook_secret = Column(String, nullable=True)

    last_run_at = Column(TIMESTAMP, nullable=True)
    next_run_at = Column(TIMESTAMP, nullable=True)

    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
