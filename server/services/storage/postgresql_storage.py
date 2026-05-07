# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
PostgreSQL storage backend with pgvector support.
"""
from typing import Dict, Any, List, Optional, Union
from sqlalchemy import create_engine, text, Column, String
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func
import json
import uuid
import logging

from services.storage.base import StorageBackend

logger = logging.getLogger(__name__)

Base = declarative_base()


class StorageTable(Base):
    """Generic storage table for PostgreSQL"""
    __tablename__ = "storage_data"
    
    key = Column(String(500), primary_key=True)
    value = Column(JSONB, nullable=False)
    meta_data = Column("metadata", JSONB, nullable=True)  # Use "metadata" as DB column name, "meta_data" as Python attr
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


class PostgreSQLStorage(StorageBackend):
    """PostgreSQL storage with pgvector support"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.connection_string = config.get("connection_string")
        self.table_name = config.get("table", "storage_data")
        self.enable_vector = config.get("enable_vector", True)
        self.embedding_dimension = config.get("embedding_dimension", 1536)
        self.engine = None
        self.Session = None
    
    def initialize(self) -> None:
        """Initialize PostgreSQL connection and create table"""
        if self._initialized:
            return
        
        if not self.connection_string:
            raise ValueError("PostgreSQL connection_string is required")
        
        self.engine = create_engine(self.connection_string)
        self.Session = sessionmaker(bind=self.engine)
        
        # Enable pgvector extension if needed (only if enable_vector is True)
        if self.enable_vector:
            try:
                with self.engine.connect() as conn:
                    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                    conn.commit()
            except Exception as e:
                # If vector extension is not available, log warning and continue without it
                logger.warning(
                    f"Could not create vector extension: {e}. "
                    "Continuing without vector support. Set 'enable_vector': false in config to suppress this warning."
                )
                self.enable_vector = False  # Disable vector features if extension unavailable
        
        # Create table if not exists
        # Note: We'll use raw SQL since we need to handle the vector column dynamically
        with self.engine.connect() as conn:
            # Check if table exists
            result = conn.execute(text(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = '{self.table_name}'
                )
            """))
            table_exists = result.scalar()
            
            if not table_exists:
                # Create table with vector column if enabled
                if self.enable_vector:
                    conn.execute(text(f"""
                        CREATE TABLE {self.table_name} (
                            key VARCHAR(500) PRIMARY KEY,
                            value JSONB NOT NULL,
                            metadata JSONB,
                            embedding vector({self.embedding_dimension}),
                            created_at TIMESTAMP DEFAULT NOW(),
                            updated_at TIMESTAMP DEFAULT NOW()
                        )
                    """))
                    # Create index for vector search
                    conn.execute(text(f"""
                        CREATE INDEX IF NOT EXISTS {self.table_name}_embedding_idx 
                        ON {self.table_name} 
                        USING ivfflat (embedding vector_cosine_ops)
                    """))
                else:
                    conn.execute(text(f"""
                        CREATE TABLE {self.table_name} (
                            key VARCHAR(500) PRIMARY KEY,
                            value JSONB NOT NULL,
                            metadata JSONB,
                            created_at TIMESTAMP DEFAULT NOW(),
                            updated_at TIMESTAMP DEFAULT NOW()
                        )
                    """))
                conn.commit()
        
        self._initialized = True
    
    def store(
        self, 
        key: str, 
        value: Any, 
        metadata: Optional[Dict[str, Any]] = None,
        embedding: Optional[List[float]] = None
    ) -> str:
        """Store value in PostgreSQL"""
        if not self._initialized:
            self.initialize()
        
        session = self.Session()
        try:
            # Convert value to JSON-serializable format
            if isinstance(value, (dict, list)):
                json_value = value
            else:
                json_value = {"_value": str(value)}
            
            # Prepare embedding if provided
            embedding_vector = None
            if embedding and self.enable_vector:
                embedding_vector = embedding
            
            # Upsert
            if embedding_vector and self.enable_vector:
                stmt = text(f"""
                    INSERT INTO {self.table_name} (key, value, metadata, embedding, updated_at)
                    VALUES (:key, :value::jsonb, :metadata::jsonb, :embedding::vector, NOW())
                    ON CONFLICT (key) 
                    DO UPDATE SET 
                        value = EXCLUDED.value,
                        metadata = EXCLUDED.metadata,
                        embedding = EXCLUDED.embedding,
                        updated_at = NOW()
                """)
                session.execute(stmt, {
                    "key": key,
                    "value": json.dumps(json_value),
                    "metadata": json.dumps(metadata or {}),
                    "embedding": str(embedding_vector)  # Convert list to string for vector type
                })
            else:
                stmt = text(f"""
                    INSERT INTO {self.table_name} (key, value, metadata, updated_at)
                    VALUES (:key, :value::jsonb, :metadata::jsonb, NOW())
                    ON CONFLICT (key) 
                    DO UPDATE SET 
                        value = EXCLUDED.value,
                        metadata = EXCLUDED.metadata,
                        updated_at = NOW()
                """)
                session.execute(stmt, {
                    "key": key,
                    "value": json.dumps(json_value),
                    "metadata": json.dumps(metadata or {})
                })
            session.commit()
            return key
        finally:
            session.close()
    
    def retrieve(self, key: str) -> Optional[Any]:
        """Retrieve value from PostgreSQL"""
        if not self._initialized:
            self.initialize()
        
        session = self.Session()
        try:
            stmt = text(f"SELECT value FROM {self.table_name} WHERE key = :key")
            result = session.execute(stmt, {"key": key}).fetchone()
            if result:
                value = result[0]
                # Unwrap if stored as {"_value": "..."}
                if isinstance(value, dict) and "_value" in value and len(value) == 1:
                    return value["_value"]
                return value
            return None
        finally:
            session.close()
    
    def search(
        self, 
        query: Union[str, List[float]], 
        limit: int = 10,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search in PostgreSQL (vector or full-text)"""
        if not self._initialized:
            self.initialize()
        
        session = self.Session()
        try:
            if isinstance(query, list) and self.enable_vector:
                # Vector similarity search
                embedding = query
                stmt = text(f"""
                    SELECT key, value, metadata, 
                           1 - (embedding <=> :embedding::vector) as score
                    FROM {self.table_name}
                    WHERE embedding IS NOT NULL
                    ORDER BY embedding <=> :embedding::vector
                    LIMIT :limit
                """)
                results = session.execute(stmt, {
                    "embedding": str(embedding),  # Convert list to string for vector type
                    "limit": limit
                }).fetchall()
            else:
                # Full-text search (simple LIKE for now, can use tsvector later)
                query_str = str(query)
                stmt = text(f"""
                    SELECT key, value, metadata, 1.0 as score
                    FROM {self.table_name}
                    WHERE value::text ILIKE :query
                    LIMIT :limit
                """)
                results = session.execute(stmt, {
                    "query": f"%{query_str}%",
                    "limit": limit
                }).fetchall()
            
            return [
                {
                    "key": row[0],
                    "value": row[1],
                    "metadata": row[2] or {},
                    "score": float(row[3])
                }
                for row in results
            ]
        finally:
            session.close()
    
    def delete(self, key: str) -> bool:
        """Delete value from PostgreSQL"""
        if not self._initialized:
            self.initialize()
        
        session = self.Session()
        try:
            stmt = text(f"DELETE FROM {self.table_name} WHERE key = :key")
            result = session.execute(stmt, {"key": key})
            session.commit()
            return result.rowcount > 0
        finally:
            session.close()
    
    def list_keys(self, prefix: Optional[str] = None) -> List[str]:
        """List all keys (optionally filtered by prefix)"""
        if not self._initialized:
            self.initialize()
        
        session = self.Session()
        try:
            if prefix:
                stmt = text(f"SELECT key FROM {self.table_name} WHERE key LIKE :prefix")
                results = session.execute(stmt, {"prefix": f"{prefix}%"}).fetchall()
            else:
                stmt = text(f"SELECT key FROM {self.table_name}")
                results = session.execute(stmt).fetchall()
            return [row[0] for row in results]
        finally:
            session.close()
    
    def get_connection(self):
        """
        Get a raw psycopg2 connection from the SQLAlchemy engine.
        This allows direct SQL execution for custom table operations.
        
        Returns:
            psycopg2 connection object
        """
        if not self._initialized:
            self.initialize()
        
        # Get the underlying psycopg2 connection from SQLAlchemy engine
        return self.engine.raw_connection()
    
    def close(self) -> None:
        """Close PostgreSQL connection"""
        if self.engine:
            self.engine.dispose()
        self._initialized = False

