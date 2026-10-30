"""Embeddings: Voyage AI when VOYAGE_API_KEY is set, otherwise a deterministic local hashing embedder.

The local embedder (signed feature hashing of word unigrams and bigrams, L2-normalised) keeps hybrid search
and the memory store working offline. Vectors from the two backends are not comparable, so every stored
vector records its model name and search only compares vectors from the active model.
"""

import hashlib
import math
import re

import voyageai

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
        _voyage = voyageai.AsyncClient(api_key=s.voyage_api_key)
    out: list[list[float]] = []
    for i in range(0, len(texts), 64):
        batch = texts[i : i + 64]
        result = await _voyage.embed(batch, model=s.embed_model, input_type=input_type, output_dimension=s.embed_dims)
        out.extend(result.embeddings)
    return out


async def embed_query(text: str) -> list[float]:
    return (await embed([text], input_type="query"))[0]


async def store_embed(texts: list[str]) -> list[list[float]]:
    """Embedding function handed to LangGraph's AsyncPostgresStore."""
    return await embed(texts, input_type="document")
