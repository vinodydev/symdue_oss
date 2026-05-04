"""
Tests for issue14 — backend-side embedding service.
"""
import pytest


def test_parse_spec_valid():
    from services.embeddings import EmbeddingService
    svc = EmbeddingService()
    assert svc.parse_spec("sentence-transformers:BAAI/bge-small-en-v1.5") == (
        "sentence-transformers", "BAAI/bge-small-en-v1.5"
    )
    assert svc.parse_spec("openai:text-embedding-3-small") == (
        "openai", "text-embedding-3-small"
    )


def test_parse_spec_invalid():
    from services.embeddings import EmbeddingService
    svc = EmbeddingService()
    with pytest.raises(ValueError):
        svc.parse_spec("")
    with pytest.raises(ValueError):
        svc.parse_spec("no-colon-model")
    with pytest.raises(ValueError):
        svc.parse_spec(":model-only")
    with pytest.raises(ValueError):
        svc.parse_spec("provider:")


def test_unknown_provider():
    from services.embeddings import EmbeddingService
    svc = EmbeddingService()
    with pytest.raises(ValueError, match="Unsupported embedding provider"):
        svc.embed_batch(["hello"], "nonexistent:foo")


def test_openai_not_implemented():
    from services.embeddings import EmbeddingService
    svc = EmbeddingService()
    with pytest.raises(NotImplementedError):
        svc.embed_batch(["hello"], "openai:text-embedding-3-small")


def test_ollama_not_implemented():
    from services.embeddings import EmbeddingService
    svc = EmbeddingService()
    with pytest.raises(NotImplementedError):
        svc.embed_batch(["hello"], "ollama:nomic-embed-text")


def test_singleton():
    from services.embeddings import get_embedding_service, EmbeddingService
    a = get_embedding_service()
    b = get_embedding_service()
    assert a is b
    assert isinstance(a, EmbeddingService)


# Marked slow because it actually loads sentence-transformers and downloads
# the model on first run. ~3-5s. Run with: pytest -m slow
@pytest.mark.slow
def test_sentence_transformers_real_call():
    from services.embeddings import get_embedding_service
    svc = get_embedding_service()
    spec = "sentence-transformers:BAAI/bge-small-en-v1.5"
    vectors = svc.embed_batch(["hello world", "another sentence"], spec)
    assert len(vectors) == 2
    assert len(vectors[0]) == 384  # bge-small dim
    # Cosine similarity self-check: same string twice should give identical vectors
    same = svc.embed_batch(["hello world"], spec)
    assert same[0] == vectors[0]
