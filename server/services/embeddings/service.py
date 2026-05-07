# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Embedding service — runs in the backend, lazy-loads sentence-transformers
models on first use, caches them process-wide so subsequent calls are fast.

Sandbox-side StorageClient calls this via the
POST /api/storage-configs/{id}/embed endpoint. The model never runs in the
sandbox itself.

See flowgraph/issues/issue14 for full design.
"""
from __future__ import annotations

import logging
import threading
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Lazy-loading multi-provider embedding service.

    Provider format: ``"<provider>:<model_id>"``, e.g.
    ``"sentence-transformers:BAAI/bge-small-en-v1.5"``.

    Currently supported providers:
      - ``sentence-transformers``  — local, offline-capable

    Not yet supported (placeholders):
      - ``openai``    — requires OPENAI_API_KEY in env
      - ``ollama``    — requires OLLAMA_HOST
    """

    def __init__(self) -> None:
        # Cache of loaded models: (provider, model_id) -> instance
        self._models: Dict[Tuple[str, str], object] = {}
        self._lock = threading.Lock()

    def parse_spec(self, spec: str) -> Tuple[str, str]:
        """Parse ``provider:model_id`` into a tuple. Raises ValueError on bad input."""
        if not spec or ":" not in spec:
            raise ValueError(
                f"Invalid embedding_function spec: {spec!r}. "
                "Expected '<provider>:<model_id>', e.g. "
                "'sentence-transformers:BAAI/bge-small-en-v1.5'."
            )
        provider, _, model_id = spec.partition(":")
        provider = provider.strip().lower()
        model_id = model_id.strip()
        if not provider or not model_id:
            raise ValueError(f"Invalid embedding_function spec: {spec!r}")
        return provider, model_id

    def embed(self, text: str, spec: str) -> List[float]:
        """Embed a single text. Convenience wrapper around ``embed_batch``."""
        return self.embed_batch([text], spec)[0]

    def embed_batch(self, texts: List[str], spec: str) -> List[List[float]]:
        """Embed a list of texts using the configured provider+model.

        Lazily loads the model on first call; subsequent calls reuse the
        cached instance for the lifetime of the backend process.
        """
        provider, model_id = self.parse_spec(spec)
        if provider == "sentence-transformers":
            return self._embed_sentence_transformers(texts, model_id)
        if provider == "openai":
            return self._embed_openai(texts, model_id)
        if provider == "ollama":
            return self._embed_ollama(texts, model_id)
        raise ValueError(f"Unsupported embedding provider: {provider!r}")

    # ──────────────────────────────────────────────────────────────────
    # sentence-transformers (local)
    # ──────────────────────────────────────────────────────────────────

    def _embed_sentence_transformers(
        self, texts: List[str], model_id: str
    ) -> List[List[float]]:
        key = ("sentence-transformers", model_id)
        with self._lock:
            model = self._models.get(key)
            if model is None:
                logger.info(f"Loading sentence-transformers model: {model_id}")
                from sentence_transformers import SentenceTransformer
                model = SentenceTransformer(model_id)
                self._models[key] = model
                logger.info(
                    f"Loaded {model_id}: dim={model.get_sentence_embedding_dimension()}"
                )
        # encode is thread-safe enough for our usage; release lock before encoding
        # to avoid serializing concurrent requests.
        embeddings = model.encode(texts, normalize_embeddings=True)
        return [v.tolist() for v in embeddings]

    def get_dimension(self, spec: str) -> Optional[int]:
        """Return the model's embedding dimension if known. Loads lazily."""
        provider, model_id = self.parse_spec(spec)
        if provider == "sentence-transformers":
            key = ("sentence-transformers", model_id)
            with self._lock:
                model = self._models.get(key)
                if model is None:
                    from sentence_transformers import SentenceTransformer
                    model = SentenceTransformer(model_id)
                    self._models[key] = model
                return model.get_sentence_embedding_dimension()
        # Other providers: known fixed sizes for common models, or None.
        return None

    # ──────────────────────────────────────────────────────────────────
    # Placeholders (not yet implemented)
    # ──────────────────────────────────────────────────────────────────

    def _embed_openai(self, texts: List[str], model_id: str) -> List[List[float]]:
        raise NotImplementedError(
            "openai provider not implemented yet. Use sentence-transformers."
        )

    def _embed_ollama(self, texts: List[str], model_id: str) -> List[List[float]]:
        raise NotImplementedError(
            "ollama provider not implemented yet. Use sentence-transformers."
        )


_singleton: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Get the process-wide singleton EmbeddingService."""
    global _singleton
    if _singleton is None:
        _singleton = EmbeddingService()
    return _singleton
