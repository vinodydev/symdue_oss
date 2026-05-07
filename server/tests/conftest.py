# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Pytest configuration and fixtures for GraphMind Orchestrator tests.
"""
import pytest
import asyncio
from typing import AsyncGenerator, Generator
from sqlalchemy import create_engine, event, String
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import TypeDecorator, CHAR
import uuid

# Import database components
from sqlalchemy import text
from database.connection import SessionLocal, get_db
from database.base import Base


# Test database URL
# Use PostgreSQL from docker-compose for tests (supports UUID natively)
import os
TEST_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://graphmind:your_password@postgres:5432/graphmind_db"
)

# Tables to truncate, in dependency order (children first to satisfy FK constraints)
# node_types and workflows have a circular FK so we disable triggers temporarily
_TRUNCATE_TABLES = [
    "event_invocations",
    "events",
    "workflow_waits",
    "run_history",
    "workflow_nodes",
    "workflow_edges",
    "workflows",
    "node_types",
    "llm_configs",
    "storage_configs",
]


def _truncate_test_data(engine):
    """
    Truncate all application tables to clean test data while preserving the schema.
    Uses TRUNCATE ... CASCADE to handle FK relationships without needing topological sort.
    """
    with engine.connect() as conn:
        # Disable triggers to bypass FK checks, truncate all tables, re-enable
        conn.execute(text("SET session_replication_role = 'replica'"))
        for table in _TRUNCATE_TABLES:
            conn.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))
        conn.execute(text("SET session_replication_role = 'origin'"))
        conn.commit()


class GUID(TypeDecorator):
    """Platform-independent GUID type for SQLite compatibility"""
    impl = CHAR
    cache_ok = True
    length = 36

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            from sqlalchemy.dialects.postgresql import UUID
            return dialect.type_descriptor(UUID())
        else:
            return dialect.type_descriptor(CHAR(self.length))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return str(value)
        else:
            if not isinstance(value, str):
                return str(value)
            return value

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            return str(value)


def _set_sqlite_pragma(dbapi_conn, connection_record):
    """Enable foreign keys for SQLite"""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


def _make_engine():
    """Create a SQLAlchemy engine for the test database."""
    if "sqlite" in TEST_DATABASE_URL:
        engine = create_engine(
            TEST_DATABASE_URL,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        event.listen(engine, "connect", _set_sqlite_pragma)
    else:
        engine = create_engine(TEST_DATABASE_URL)
    return engine


def _seed_node_types(session):
    """Seed the minimum required node types for tests."""
    from database.models import NodeType

    base_types = [
        {
            "id": "input",
            "category": "input",
            "name": "Input Node",
            "description": "Entry point for data",
            "icon": "database",
            "is_builtin": True,
            "default_config": {"name": "Input", "inputType": "text", "value": ""}
        },
        {
            "id": "custom-python",
            "category": "python",
            "name": "Python Script",
            "description": "Custom code execution",
            "icon": "code",
            "is_builtin": True,
            "default_config": {"name": "Python Node", "code": "", "requirements": ""}
        },
        {
            "id": "custom-llm",
            "category": "llm",
            "name": "LLM Node",
            "description": "Connect to AI model endpoints",
            "icon": "cpu",
            "is_builtin": True,
            "default_config": {"name": "LLM Node", "prompt": "", "configId": None}
        },
        {
            "id": "memory",
            "category": "memory",
            "name": "Memory Node",
            "description": "Context retrieval",
            "icon": "history",
            "is_builtin": True,
            "default_config": {"name": "Memory Node"}
        },
        {
            "id": "wait",
            "category": "Control",
            "name": "Wait",
            "description": "Pause execution until a signal is received",
            "icon": "clock",
            "is_builtin": True,
            "default_config": {"channel": "", "mode": "signal", "signals": [], "timeout": None}
        },
    ]

    for node_type_data in base_types:
        existing = session.query(NodeType).filter(
            NodeType.id == node_type_data["id"]
        ).first()
        if not existing:
            node_type = NodeType(**node_type_data)
            session.add(node_type)
    session.commit()


@pytest.fixture(scope="function")
def test_db_session() -> Generator:
    """
    Create a test database session.
    Each test gets a fresh database with seeded node types.
    Uses TRUNCATE to clean data without destroying the schema.
    """
    engine = _make_engine()

    # Ensure tables exist (idempotent - skips if already present)
    Base.metadata.create_all(bind=engine)

    # Clean all test data from previous run
    _truncate_test_data(engine)

    # Create session
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=engine
    )
    session = TestingSessionLocal()

    # Seed base node types
    _seed_node_types(session)

    try:
        yield session
    finally:
        session.close()
        _truncate_test_data(engine)
        engine.dispose()


@pytest.fixture(scope="function")
def test_db() -> Generator:
    """
    Dependency override for get_db() to use test database.
    Uses PostgreSQL from docker-compose (supports UUID natively).
    Uses TRUNCATE to clean data without destroying the schema.
    """
    engine = _make_engine()

    # Ensure tables exist (idempotent)
    Base.metadata.create_all(bind=engine)

    # Clean all test data from previous run
    _truncate_test_data(engine)

    # Create session
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=engine
    )
    session = TestingSessionLocal()

    # Seed base node types
    _seed_node_types(session)

    def override_get_db():
        try:
            yield session
        finally:
            session.rollback()

    # Override get_db dependency
    from main import app
    app.dependency_overrides[get_db] = override_get_db

    yield session

    # Cleanup
    app.dependency_overrides.clear()
    session.close()
    _truncate_test_data(engine)
    engine.dispose()


@pytest.fixture
def client(test_db):
    """
    Create a test client for FastAPI.
    """
    from fastapi.testclient import TestClient
    from main import app
    return TestClient(app)


@pytest.fixture
def mock_redis():
    """
    Mock Redis client for tests.
    """
    from unittest.mock import MagicMock
    mock_redis = MagicMock()
    mock_redis.ping.return_value = True
    mock_redis.get.return_value = None
    mock_redis.set.return_value = True
    mock_redis.publish.return_value = 1
    return mock_redis


@pytest.fixture
def mock_temporal_client():
    """
    Mock Temporal client for tests.
    """
    from unittest.mock import MagicMock, AsyncMock
    mock_client = MagicMock()
    mock_client.start_workflow = AsyncMock()
    mock_client.get_workflow_handle = MagicMock()
    return mock_client


@pytest.fixture
def mock_docker_client():
    """
    Mock Docker client for tests.
    """
    from unittest.mock import MagicMock
    mock_docker = MagicMock()
    mock_docker.containers.run = MagicMock()
    mock_docker.images.pull = MagicMock()
    return mock_docker
