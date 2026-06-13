"""
Thin retrieval wrapper around the persisted ChromaDB index.
"""

from __future__ import annotations

import os
from pathlib import Path

import chromadb
from chromadb.config import Settings
from dotenv import load_dotenv

from embeddings import active_embedding_model, embed_texts


ROOT_DIR = Path(__file__).resolve().parents[1]
VALID_COLLECTIONS = {"catalog", "faq"}

load_dotenv(ROOT_DIR / ".env")


def _persist_dir() -> Path:
    configured_dir = Path(os.getenv("CHROMA_PERSIST_DIR", ROOT_DIR / "vector_index"))
    if configured_dir.is_absolute():
        return configured_dir
    return ROOT_DIR / configured_dir


def _client() -> chromadb.PersistentClient:
    persist_dir = _persist_dir()
    if not persist_dir.exists():
        raise RuntimeError(
            f"Vector index not found at {persist_dir}. "
            "Build it first with: python src/build_index.py"
        )
    return chromadb.PersistentClient(
        path=str(persist_dir),
        settings=Settings(anonymized_telemetry=False),
    )


def search(query: str, collection: str, top_k: int | None = None) -> list[dict]:
    if collection not in VALID_COLLECTIONS:
        raise ValueError(f"Unknown collection '{collection}'. Use one of: {sorted(VALID_COLLECTIONS)}")

    query = query.strip()
    if not query:
        return []

    top_k = top_k or int(os.getenv("RETRIEVAL_TOP_K", "4"))
    client = _client()

    try:
        chroma_collection = client.get_collection(collection)
    except ValueError as exc:
        raise RuntimeError(
            f"Collection '{collection}' does not exist in {_persist_dir()}. "
            "Rebuild the index with: python src/build_index.py"
        ) from exc

    stored_model = chroma_collection.metadata.get("embedding_model")
    current_model = active_embedding_model()
    if stored_model and stored_model != current_model:
        raise RuntimeError(
            f"Index was built with '{stored_model}', but current embedding model is "
            f"'{current_model}'. Rebuild with: python src/build_index.py"
        )

    results = chroma_collection.query(
        query_embeddings=embed_texts([query]),
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    matches = []
    for content, metadata, distance in zip(documents, metadatas, distances):
        matches.append(
            {
                "content": content,
                "metadata": metadata,
                "score": round(1 - float(distance), 4),
            }
        )
    return matches
