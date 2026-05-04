"""
LLM Configuration model
"""
from sqlalchemy import Column, String
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from sqlalchemy.sql import func
import uuid
from database.base import Base


class LLMConfig(Base):
    """
    LLM provider configuration (OpenAI, Anthropic, etc.)
    """
    __tablename__ = "llm_configs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    provider = Column(String(50), nullable=False)  # 'openai', 'anthropic', 'google', 'perplexity', 'local'
    model = Column(String(100), nullable=False)
    api_key = Column(String(500), nullable=True)  # Encrypted in future
    base_url = Column(String(500), nullable=True)  # For custom endpoints
    config = Column(JSONB, default={})  # Additional provider-specific config
    
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    deleted_at = Column(TIMESTAMP, nullable=True)  # Soft delete

