# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""Embedding service — auto-embed text for vector storage backends.

See flowgraph/issues/issue14 for the design.
"""
from services.embeddings.service import EmbeddingService, get_embedding_service

__all__ = ["EmbeddingService", "get_embedding_service"]
