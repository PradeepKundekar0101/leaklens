"""Embeddings: Voyage AI when VOYAGE_API_KEY is set, otherwise a deterministic local hashing embedder.

The local embedder (signed feature hashing of word unigrams and bigrams, L2-normalised) keeps hybrid search
and the memory store working offline. Vectors from the two backends are not comparable, so every stored
vector records its model name and search only compares vectors from the active model.
"""

import asyncio
import hashlib
import math
import re

import voyageai
import voyageai.error

from app.core.config import get_settings

LOCAL_MODEL = "local-hash-1024"
_TOKEN = re.compile(r"[a-z0-9]+")
_voyage: voyageai.AsyncClient | None = None


def active_model() -> str:
    s = get_settings()
    return s.embed_model if s.embeddings_enabled else LOCAL_MODEL


def _tokens(text: str) -> list[str]:
    words = _TOKEN.findall(text.lower())
    return words + [f"{a}_{b}" for a, b in zip(words, words[1:], strict=False)]


def local_embed(text: str, dims: int | None = None) -> list[float]:
    dims = dims or get_settings().embed_dims
    vec = [0.0] * dims
    for tok in _tokens(text):
        digest = hashlib.blake2b(tok.encode(), digest_size=8).digest()
        h = int.from_bytes(digest, "little")
        vec[h % dims] += 1.0 if (h >> 63) & 1 else -1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


async def embed(texts: list[str], input_type: str = "document") -> list[list[float]]:
    s = get_settings()
    if not s.embeddings_enabled:
        return [local_embed(t) for t in texts]
    global _voyage
    if _voyage is None:
        _voyage = voyageai.AsyncClient(api_key=s.voyage_api_key, max_retries=0)
    out: list[list[float]] = []
    for batch in _batches(texts):
        out.extend(await _embed_with_backoff(batch, input_type))
    return out


MAX_BATCH_TOKENS = 8000  # stays under the lowest Voyage tier (10K tokens/minute) per request
MAX_BATCH_ITEMS = 64


def _estimate_tokens(text: str) -> int:
    return len(text) // 3 + 1


def _batches(texts: list[str]):
    batch: list[str] = []
    tokens = 0
    for text in texts:
        n = _estimate_tokens(text)
        if batch and (tokens + n > MAX_BATCH_TOKENS or len(batch) >= MAX_BATCH_ITEMS):
            yield batch
            batch, tokens = [], 0
        batch.append(text)
        tokens += n
    if batch:
        yield batch


async def _embed_with_backoff(batch: list[str], input_type: str, attempts: int = 8) -> list[list[float]]:
    """Retries rate-limit errors with backoff (up to ~4 minutes), so low-tier accounts still complete."""
    s = get_settings()
    delay = 20.0
    for attempt in range(attempts):
        try:
            result = await _voyage.embed(
                batch, model=s.embed_model, input_type=input_type, output_dimension=s.embed_dims
            )
            return result.embeddings
        except voyageai.error.RateLimitError:
            if attempt == attempts - 1:
                raise
            await asyncio.sleep(delay)
            delay = min(delay * 1.5, 60.0)
    raise RuntimeError("unreachable")


_query_cache: dict[tuple[str, str], list[float]] = {}
QUERY_CACHE_SIZE = 2048


async def embed_query(text: str) -> list[float]:
    """Query embeddings are cached in-process: agents repeat the same policy searches across claims."""
    key = (active_model(), " ".join(text.lower().split()))
    if key not in _query_cache:
        if len(_query_cache) >= QUERY_CACHE_SIZE:
            _query_cache.pop(next(iter(_query_cache)))
        _query_cache[key] = (await embed([text], input_type="query"))[0]
    return _query_cache[key]


async def store_embed(texts: list[str]) -> list[list[float]]:
    """Embedding function handed to LangGraph's AsyncPostgresStore."""
    return await embed(texts, input_type="document")
