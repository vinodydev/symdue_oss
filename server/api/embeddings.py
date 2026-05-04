"""
Stateless embedding endpoint — used by sandbox-side StorageClient to
auto-embed text queries before vector search. See flowgraph/issues/issue14.
"""
from fastapi import APIRouter, HTTPException
from typing import List

from services.embeddings import get_embedding_service


router = APIRouter()


@router.post("/api/embed")
async def embed(payload: dict):
    """Embed text(s) using the given embedding-function spec.

    Body: ``{"spec": "<provider>:<model_id>", "texts": ["a", "b"]}``
    Response: ``{"embeddings": [[...], [...]], "model": "...", "dimension": 384}``

    Stateless — does not need a storage row; sandbox passes the spec from
    its locally-cached storage config.
    """
    spec = payload.get("spec")
    texts = payload.get("texts")
    if not isinstance(spec, str) or not spec.strip():
        raise HTTPException(status_code=400, detail="'spec' must be a non-empty string")
    if not isinstance(texts, list) or not texts:
        raise HTTPException(status_code=400, detail="'texts' must be a non-empty list")
    if not all(isinstance(t, str) for t in texts):
        raise HTTPException(status_code=400, detail="All 'texts' must be strings")

    svc = get_embedding_service()
    try:
        vectors: List[List[float]] = svc.embed_batch(texts, spec)
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding failed: {e}")

    _, _, model_id = spec.partition(":")
    return {
        "embeddings": vectors,
        "model": model_id,
        "dimension": len(vectors[0]) if vectors else 0,
    }
