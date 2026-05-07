# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Symdue contributors
"""
LLM Configuration schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID


class LLMConfigCreate(BaseModel):
    """Schema for creating a new LLM configuration"""
    name: str = Field(..., min_length=1, max_length=255)
    provider: str = Field(..., min_length=1, max_length=50)  # 'openai', 'anthropic', 'google', 'perplexity', 'local'
    model: str = Field(..., min_length=1, max_length=100)
    api_key: Optional[str] = Field(None, max_length=500)
    base_url: Optional[str] = Field(None, max_length=500)
    config: Optional[Dict[str, Any]] = Field(default_factory=dict)


class LLMConfigUpdate(BaseModel):
    """Schema for updating an LLM configuration"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    provider: Optional[str] = Field(None, min_length=1, max_length=50)
    model: Optional[str] = Field(None, min_length=1, max_length=100)
    api_key: Optional[str] = Field(None, max_length=500)
    base_url: Optional[str] = Field(None, max_length=500)
    config: Optional[Dict[str, Any]] = None


class LLMConfigResponse(BaseModel):
    """Schema for LLM configuration response"""
    id: UUID
    name: str
    provider: str
    model: str
    base_url: Optional[str]
    config: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

