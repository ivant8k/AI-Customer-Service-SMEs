"""
Embedding helpers shared by indexing and retrieval.

Llama 3.1 8B is used for chat generation through Groq. It is not an embedding
model, so catalog/FAQ retrieval uses local sentence-transformers embeddings.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
from typing import Iterable


DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_EMBEDDING_PROVIDER = "sentence_transformers"
LOCAL_HASH_MODEL = "local-hash-embedding"
LOCAL_HASH_DIMENSIONS = 384
_MODEL = None


def active_embedding_model() -> str:
    provider = os.getenv("EMBEDDING_PROVIDER", DEFAULT_EMBEDDING_PROVIDER)
    if provider == "local_hash":
        return LOCAL_HASH_MODEL
    return os.getenv("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)


def embed_texts(texts: Iterable[str]) -> list[list[float]]:
    texts = list(texts)
    if not texts:
        return []

    provider = os.getenv("EMBEDDING_PROVIDER", DEFAULT_EMBEDDING_PROVIDER)
    if provider == "local_hash":
        return [_embed_with_hashing(text) for text in texts]

    return _embed_with_sentence_transformers(texts)


def _embed_with_sentence_transformers(texts: list[str]) -> list[list[float]]:
    global _MODEL

    try:
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError(
            "sentence-transformers is required for local semantic embeddings. "
            "Install requirements.txt, or set EMBEDDING_PROVIDER=local_hash for a basic smoke test."
        ) from exc

    if _MODEL is None:
        _MODEL = SentenceTransformer(os.getenv("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL))

    embeddings = _MODEL.encode(texts, normalize_embeddings=True)
    return embeddings.tolist()


def _embed_with_hashing(text: str) -> list[float]:
    vector = [0.0] * LOCAL_HASH_DIMENSIONS
    tokens = re.findall(r"[a-z0-9]+", text.lower())

    for token in tokens:
        digest = hashlib.md5(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % LOCAL_HASH_DIMENSIONS
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector

    return [value / norm for value in vector]
