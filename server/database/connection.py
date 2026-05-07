# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Database connection and session management
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
import os
from typing import Generator

# Get database URL from environment
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://graphmind:your_password@localhost:5433/graphmind_db"
)

# Create engine
# For development, use pool_pre_ping to handle connection issues
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    echo=os.getenv("SQL_ECHO", "false").lower() == "true",  # Set SQL_ECHO=true for SQL logging
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency for getting database session.
    Use in FastAPI route dependencies.
    
    Usage:
        @app.get("/items")
        def get_items(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize database - create all tables.
    Should be called after Alembic migrations are set up.
    """
    from database.base import Base
    try:
        Base.metadata.create_all(bind=engine, checkfirst=True)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"init_db: create_all raised (tables may already exist): {e}")

