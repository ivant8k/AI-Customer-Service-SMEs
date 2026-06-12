"""
src/vector_store.py
===================
Thin wrapper around ChromaDB.

Responsibilities:
    - Load the persisted index from CHROMA_PERSIST_DIR (built by build_index.py).
    - Expose a single search(query, collection, top_k) function that returns
      the top-k most relevant Document chunks with their metadata.

Used by: src/chat_engine.py

Environment variables required (see .env.example):
    CHROMA_PERSIST_DIR
    RETRIEVAL_TOP_K  (default: 4)
"""

# TODO (Story 1.3 / Story 1.5): implement vector store wrapper
#   1. On import, open the ChromaDB client at CHROMA_PERSIST_DIR (read-only — do NOT rebuild)
#   2. Expose: search(query: str, collection: str, top_k: int) -> list[dict]
#      - Returns list of {content, metadata, score} dicts
#   3. Raise a clear RuntimeError if the index has not been built yet
#      (i.e., CHROMA_PERSIST_DIR does not exist), guiding the user to run build_index.py
