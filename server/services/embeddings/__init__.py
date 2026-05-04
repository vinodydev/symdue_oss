"""Embedding service — auto-embed text for vector storage backends.

See flowgraph/issues/issue14 for the design.
"""
from services.embeddings.service import EmbeddingService, get_embedding_service

__all__ = ["EmbeddingService", "get_embedding_service"]
