"""Lazy, validated local embedding generation with no persistence concerns."""

from __future__ import annotations

from functools import lru_cache
from typing import Sequence

from langchain_huggingface import HuggingFaceEmbeddings

from app.core.config import settings


class EmbeddingError(Exception):
    """Controlled error for invalid text or embedding-model failures."""


@lru_cache(maxsize=1)
def get_embedding_model() -> HuggingFaceEmbeddings:
    """Build the configured local model once, on the first embedding request."""
    try:
        return HuggingFaceEmbeddings(
            model_name=settings.EMBEDDING_MODEL_NAME,
            model_kwargs={"device": settings.EMBEDDING_DEVICE},
            encode_kwargs={"normalize_embeddings": settings.EMBEDDING_NORMALIZE},
        )
    except Exception as error:
        raise EmbeddingError("Unable to initialize embedding model") from error


def _validate_text(value: str, *, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise EmbeddingError(f"{label} must not be blank")


def _validate_vector(vector: Sequence[object]) -> list[float]:
    try:
        normalized_vector = [float(value) for value in vector]
    except (TypeError, ValueError) as error:
        raise EmbeddingError("Embedding model returned an invalid vector") from error
    if len(normalized_vector) != settings.EMBEDDING_DIMENSION:
        raise EmbeddingError(
            f"Embedding model returned {len(normalized_vector)} dimensions; "
            f"expected {settings.EMBEDDING_DIMENSION}"
        )
    return normalized_vector


def embed_documents(texts: list[str]) -> list[list[float]]:
    """Embed document texts in input order, validating all inputs and vector dimensions."""
    if not texts:
        return []
    for text in texts:
        _validate_text(text, label="Document text")
    try:
        vectors = get_embedding_model().embed_documents(texts)
    except EmbeddingError:
        raise
    except Exception as error:
        raise EmbeddingError("Unable to generate document embeddings") from error
    if len(vectors) != len(texts):
        raise EmbeddingError("Embedding model returned an unexpected number of vectors")
    return [_validate_vector(vector) for vector in vectors]


def embed_query(text: str) -> list[float]:
    """Embed one non-blank query and return plain Python float values."""
    _validate_text(text, label="Query text")
    try:
        vector = get_embedding_model().embed_query(text)
    except EmbeddingError:
        raise
    except Exception as error:
        raise EmbeddingError("Unable to generate query embedding") from error
    return _validate_vector(vector)
