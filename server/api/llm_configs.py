# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
LLM Configuration API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from uuid import UUID
from database.connection import get_db
from database.models import LLMConfig
from schemas.llm_config import LLMConfigCreate, LLMConfigUpdate, LLMConfigResponse

router = APIRouter()


@router.post("", response_model=LLMConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_llm_config(
    llm_config_create: LLMConfigCreate,
    db: Session = Depends(get_db)
):
    """Create a new LLM configuration"""
    db_llm_config = LLMConfig(
        name=llm_config_create.name,
        provider=llm_config_create.provider,
        model=llm_config_create.model,
        api_key=llm_config_create.api_key,
        base_url=llm_config_create.base_url,
        config=llm_config_create.config or {}
    )
    db.add(db_llm_config)
    db.commit()
    db.refresh(db_llm_config)
    return db_llm_config


@router.get("", response_model=List[LLMConfigResponse])
async def list_llm_configs(
    include_deleted: bool = False,
    db: Session = Depends(get_db)
):
    """List all LLM configurations"""
    query = db.query(LLMConfig)
    if not include_deleted:
        query = query.filter(LLMConfig.deleted_at.is_(None))
    return query.order_by(LLMConfig.created_at.desc()).all()


@router.get("/{llm_config_id}", response_model=LLMConfigResponse)
async def get_llm_config(
    llm_config_id: UUID,
    db: Session = Depends(get_db)
):
    """Get an LLM configuration by ID"""
    llm_config = db.query(LLMConfig).filter(
        LLMConfig.id == llm_config_id,
        LLMConfig.deleted_at.is_(None)
    ).first()
    
    if not llm_config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="LLM configuration not found")
    
    return llm_config


@router.put("/{llm_config_id}", response_model=LLMConfigResponse)
async def update_llm_config(
    llm_config_id: UUID,
    llm_config_update: LLMConfigUpdate,
    db: Session = Depends(get_db)
):
    """Update an LLM configuration"""
    db_llm_config = db.query(LLMConfig).filter(
        LLMConfig.id == llm_config_id,
        LLMConfig.deleted_at.is_(None)
    ).first()
    
    if not db_llm_config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="LLM configuration not found")
    
    update_data = llm_config_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_llm_config, key, value)
    
    db.add(db_llm_config)
    db.commit()
    db.refresh(db_llm_config)
    return db_llm_config


@router.delete("/{llm_config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_llm_config(
    llm_config_id: UUID,
    db: Session = Depends(get_db)
):
    """Soft delete an LLM configuration"""
    db_llm_config = db.query(LLMConfig).filter(
        LLMConfig.id == llm_config_id,
        LLMConfig.deleted_at.is_(None)
    ).first()
    
    if not db_llm_config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="LLM configuration not found")
    
    db_llm_config.deleted_at = func.now()
    db.add(db_llm_config)
    db.commit()
    return None


@router.post("/{llm_config_id}/restore", response_model=LLMConfigResponse)
async def restore_llm_config(
    llm_config_id: UUID,
    db: Session = Depends(get_db)
):
    """Restore a soft-deleted LLM configuration"""
    db_llm_config = db.query(LLMConfig).filter(
        LLMConfig.id == llm_config_id,
        LLMConfig.deleted_at.isnot(None)
    ).first()
    
    if not db_llm_config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deleted LLM configuration not found")
    
    db_llm_config.deleted_at = None
    db.add(db_llm_config)
    db.commit()
    db.refresh(db_llm_config)
    return db_llm_config

