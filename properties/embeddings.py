from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


_model = None

MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384


def _get_model():
    """Load (or return cached) SentenceTransformer model."""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading SentenceTransformer model '%s'...", MODEL_NAME)
            _model = SentenceTransformer(MODEL_NAME)
            logger.info("Model loaded successfully.")
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is not installed. "
                "Run: pip install sentence-transformers"
            ) from exc
    return _model


def get_embedding(text: str) -> Optional[list[float]]:
    """
    Return a 384-dimensional embedding for a single text string.
    Returns None on empty input so callers can skip DB writes.
    """
    text = (text or "").strip()
    if not text:
        return None
    model = _get_model()
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()


def get_embeddings_batch(texts: list[str]) -> list[Optional[list[float]]]:
    """
    Batch version of get_embedding — more efficient for bulk generation.
    Preserves order; empty/None texts produce None entries.
    """
    if not texts:
        return []

    # Separate valid texts from blanks, track original indices
    indexed = [(i, t.strip()) for i, t in enumerate(texts) if t and t.strip()]
    results: list[Optional[list[float]]] = [None] * len(texts)

    if not indexed:
        return results

    indices, valid_texts = zip(*indexed)
    model = _get_model()
    vectors = model.encode(list(valid_texts), normalize_embeddings=True, show_progress_bar=False)

    for idx, vec in zip(indices, vectors):
        results[idx] = vec.tolist()

    return results


def build_query_embedding(query: str) -> Optional[list[float]]:
    """
    Convenience wrapper: encode a user search query for similarity lookup.
    Identical to get_embedding but named separately for clarity at call sites.
    """
    return get_embedding(query)
