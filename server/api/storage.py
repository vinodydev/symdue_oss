# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Storage API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.sql import func
from typing import List, Optional
from uuid import UUID

from database.connection import get_db
from database.models.storage import StorageConfig
from database.models.node import WorkflowNode
from schemas.storage import (
    StorageConfigCreate,
    StorageConfigUpdate,
    StorageConfigResponse
)
from services.storage.manager import StorageManager

router = APIRouter(prefix="/api/storage", tags=["storage"])


@router.post("/", response_model=StorageConfigResponse)
async def create_storage_config(
    config: StorageConfigCreate,
    db: Session = Depends(get_db)
):
    """Create a new storage configuration"""
    # Check name uniqueness
    existing = db.query(StorageConfig).filter_by(
        name=config.name,
        deleted_at=None
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Storage name already exists")
    
    storage_config = StorageConfig(
        name=config.name,
        storage_type=config.storage_type,
        config=config.config,
        enabled=config.enabled
    )
    db.add(storage_config)
    db.commit()
    db.refresh(storage_config)
    
    return storage_config


@router.get("/", response_model=List[StorageConfigResponse])
async def list_storage_configs(
    db: Session = Depends(get_db)
):
    """List all storage configurations"""
    configs = db.query(StorageConfig).filter_by(deleted_at=None).all()
    return configs


@router.get("/{storage_id}", response_model=StorageConfigResponse)
async def get_storage_config(
    storage_id: UUID,
    db: Session = Depends(get_db)
):
    """Get storage configuration by ID"""
    config = db.query(StorageConfig).filter_by(
        id=storage_id,
        deleted_at=None
    ).first()
    if not config:
        raise HTTPException(status_code=404, detail="Storage config not found")
    return config


@router.put("/{storage_id}", response_model=StorageConfigResponse)
async def update_storage_config(
    storage_id: UUID,
    config: StorageConfigUpdate,
    db: Session = Depends(get_db)
):
    """Update storage configuration"""
    storage_config = db.query(StorageConfig).filter_by(
        id=storage_id,
        deleted_at=None
    ).first()
    if not storage_config:
        raise HTTPException(status_code=404, detail="Storage config not found")
    
    if config.name and config.name != storage_config.name:
        # Check name uniqueness
        existing = db.query(StorageConfig).filter_by(
            name=config.name,
            deleted_at=None
        ).filter(StorageConfig.id != storage_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Storage name already exists")
        storage_config.name = config.name
    
    if config.config:
        storage_config.config = config.config
    if config.enabled is not None:
        storage_config.enabled = config.enabled
    
    db.commit()
    db.refresh(storage_config)
    
    # Invalidate cache
    StorageManager.close_storage(str(storage_id))
    
    return storage_config


@router.post("/{storage_id}/embed")
async def embed_for_storage(
    storage_id: UUID,
    payload: dict,
    db: Session = Depends(get_db),
):
    """Embed text(s) using the storage config's `embedding_function`.

    Body: ``{"texts": ["text 1", "text 2"]}``
    Response: ``{"embeddings": [[...], [...]], "model": "<model_id>", "dimension": 384}``

    Used by sandbox-side StorageClient to auto-embed text queries before
    vector search. See flowgraph/issues/issue14.
    """
    storage_config = (
        db.query(StorageConfig)
        .filter(StorageConfig.id == storage_id, StorageConfig.deleted_at.is_(None))
        .first()
    )
    if not storage_config:
        raise HTTPException(status_code=404, detail="Storage config not found")

    spec = (storage_config.config or {}).get("embedding_function")
    if not spec:
        raise HTTPException(
            status_code=400,
            detail="Storage has no embedding_function configured",
        )

    texts = payload.get("texts")
    if not isinstance(texts, list) or not texts:
        raise HTTPException(status_code=400, detail="Body must include non-empty 'texts' list")
    if not all(isinstance(t, str) for t in texts):
        raise HTTPException(status_code=400, detail="All 'texts' must be strings")

    from services.embeddings import get_embedding_service
    svc = get_embedding_service()
    try:
        vectors = svc.embed_batch(texts, spec)
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding failed: {e}")

    _, model_id = spec.partition(":")[0], spec.split(":", 1)[1]
    return {
        "embeddings": vectors,
        "model": model_id,
        "dimension": len(vectors[0]) if vectors else 0,
    }


@router.delete("/{storage_id}")
async def delete_storage_config(
    storage_id: UUID,
    db: Session = Depends(get_db)
):
    """Soft delete storage configuration"""
    storage_config = db.query(StorageConfig).filter_by(
        id=storage_id,
        deleted_at=None
    ).first()
    if not storage_config:
        raise HTTPException(status_code=404, detail="Storage config not found")
    
    storage_config.deleted_at = func.now()
    db.commit()
    
    # Close and remove from cache
    StorageManager.close_storage(str(storage_id))
    
    return {"message": "Storage config deleted"}


# Node-Storage Management (via Node Config)

@router.post("/nodes/{node_id}/storages")
async def attach_storage_to_node(
    node_id: UUID,
    storage_id: UUID = Query(..., description="Storage configuration ID"),
    alias: Optional[str] = Query(None, description="Optional alias for the storage"),
    db: Session = Depends(get_db)
):
    """Attach a storage to a node (adds to node.config["storages"])"""
    # Verify node exists
    node = db.query(WorkflowNode).filter_by(id=node_id, deleted_at=None).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    
    # Verify storage exists
    storage = db.query(StorageConfig).filter_by(id=storage_id, deleted_at=None, enabled=True).first()
    if not storage:
        raise HTTPException(status_code=404, detail="Storage config not found or disabled")
    
    # Get current config
    config = node.config or {}
    storages = config.get("storages", [])
    
    # Check if storage already attached
    if any(s.get("storage_id") == str(storage_id) for s in storages):
        raise HTTPException(status_code=400, detail="Storage already attached to this node")
    
    # Check alias uniqueness for this node
    if alias:
        if any(s.get("alias") == alias for s in storages):
            raise HTTPException(status_code=400, detail=f"Alias '{alias}' already used for this node")
    
    # Add storage reference
    storages.append({
        "storage_id": str(storage_id),
        "alias": alias
    })
    config["storages"] = storages
    node.config = config
    
    # IMPORTANT: Tell SQLAlchemy that the JSONB column has changed
    flag_modified(node, 'config')
    
    db.commit()
    db.refresh(node)
    
    return {"message": "Storage attached to node", "config": config}


@router.get("/nodes/{node_id}/storages")
async def get_node_storages(
    node_id: UUID,
    db: Session = Depends(get_db)
):
    """Get all storages attached to a node (from node.config["storages"])"""
    node = db.query(WorkflowNode).filter_by(id=node_id, deleted_at=None).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    
    config = node.config or {}
    storage_refs = config.get("storages", [])
    
    storages = []
    for ref in storage_refs:
        storage_id_str = ref.get("storage_id")
        if not storage_id_str:
            continue
        try:
            storage_id = UUID(storage_id_str) if isinstance(storage_id_str, str) else storage_id_str
        except (ValueError, TypeError):
            continue
        storage = db.query(StorageConfig).filter_by(id=storage_id, deleted_at=None).first()
        if storage:
            storages.append({
                "storage_id": str(storage.id),
                "storage_name": storage.name,
                "storage_type": storage.storage_type,
                "alias": ref.get("alias")
            })
    
    return storages


@router.delete("/nodes/{node_id}/storages/{storage_id}")
async def detach_storage_from_node(
    node_id: UUID,
    storage_id: UUID,
    db: Session = Depends(get_db)
):
    """Detach a storage from a node (removes from node.config["storages"])"""
    node = db.query(WorkflowNode).filter_by(id=node_id, deleted_at=None).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    
    config = node.config or {}
    storages = config.get("storages", [])
    
    # Remove storage reference
    original_count = len(storages)
    storages = [s for s in storages if s.get("storage_id") != str(storage_id)]
    
    if len(storages) == original_count:
        raise HTTPException(status_code=404, detail="Storage not attached to this node")
    
    config["storages"] = storages
    node.config = config
    
    # IMPORTANT: Tell SQLAlchemy that the JSONB column has changed
    flag_modified(node, 'config')
    
    db.commit()
    db.refresh(node)
    
    return {"message": "Storage detached from node", "config": config}

