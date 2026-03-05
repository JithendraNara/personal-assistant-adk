"""
UnifiedMemory — Gemini Embedding Layer.

Uses Google's text-embedding-004 model for high-quality semantic embeddings.
Supports batching and caching for efficiency.
"""

import os
import logging
import hashlib

logger = logging.getLogger(__name__)

# Embedding cache to avoid redundant API calls
_embedding_cache: dict[str, list[float]] = {}
_MAX_CACHE_SIZE = 5000

EMBEDDING_MODEL = "models/text-embedding-004"
EMBEDDING_DIMENSION = 768  # text-embedding-004 output dimension


async def embed_text(text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> list[float]:
    """
    Generate embedding for a single text using Gemini.

    Args:
        text: The text to embed.
        task_type: One of RETRIEVAL_DOCUMENT, RETRIEVAL_QUERY, SEMANTIC_SIMILARITY,
                   CLASSIFICATION, CLUSTERING.

    Returns:
        List of floats (768-dimensional embedding vector).
    """
    cache_key = _cache_key(text, task_type)
    if cache_key in _embedding_cache:
        return _embedding_cache[cache_key]

    try:
        import google.generativeai as genai

        api_key = os.getenv("GOOGLE_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)

        result = genai.embed_content(
            model=EMBEDDING_MODEL,
            content=text,
            task_type=task_type,
        )
        embedding = result["embedding"]

        # Cache it
        if len(_embedding_cache) < _MAX_CACHE_SIZE:
            _embedding_cache[cache_key] = embedding

        return embedding

    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        # Return zero vector as fallback (will have low similarity to everything)
        return [0.0] * EMBEDDING_DIMENSION


async def embed_query(query: str) -> list[float]:
    """Embed a search query (uses RETRIEVAL_QUERY task type for better search)."""
    return await embed_text(query, task_type="RETRIEVAL_QUERY")


async def embed_batch(texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    """
    Embed multiple texts efficiently.

    Uses Gemini's batch embedding endpoint when available,
    falls back to sequential calls.
    """
    results = []
    uncached_indices = []
    uncached_texts = []

    # Check cache first
    for i, text in enumerate(texts):
        cache_key = _cache_key(text, task_type)
        if cache_key in _embedding_cache:
            results.append(_embedding_cache[cache_key])
        else:
            results.append(None)
            uncached_indices.append(i)
            uncached_texts.append(text)

    if not uncached_texts:
        return results

    # Batch embed uncached texts
    try:
        import google.generativeai as genai

        api_key = os.getenv("GOOGLE_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)

        # Gemini supports batch embedding
        batch_result = genai.embed_content(
            model=EMBEDDING_MODEL,
            content=uncached_texts,
            task_type=task_type,
        )

        embeddings = batch_result["embedding"]
        for idx, embedding in zip(uncached_indices, embeddings):
            results[idx] = embedding
            cache_key = _cache_key(texts[idx], task_type)
            if len(_embedding_cache) < _MAX_CACHE_SIZE:
                _embedding_cache[cache_key] = embedding

    except Exception as e:
        logger.error(f"Batch embedding failed: {e}")
        for idx in uncached_indices:
            if results[idx] is None:
                results[idx] = [0.0] * EMBEDDING_DIMENSION

    return results


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot_product = sum(x * y for x, y in zip(a, b))
    magnitude_a = sum(x * x for x in a) ** 0.5
    magnitude_b = sum(x * x for x in b) ** 0.5
    if magnitude_a == 0 or magnitude_b == 0:
        return 0.0
    return dot_product / (magnitude_a * magnitude_b)


def _cache_key(text: str, task_type: str) -> str:
    """Generate a cache key for text + task_type."""
    h = hashlib.sha256(f"{task_type}:{text}".encode()).hexdigest()[:16]
    return h


def clear_cache():
    """Clear the embedding cache."""
    _embedding_cache.clear()
