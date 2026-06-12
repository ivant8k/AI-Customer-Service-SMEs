"""
src/build_index.py
==================
One-time CLI script: reads product_catalog.csv and faq.csv, embeds them,
and persists the ChromaDB vector index to CHROMA_PERSIST_DIR.

Usage:
    python src/build_index.py

Run this once after cloning, and again whenever the data files change.
Do NOT import this module in app.py — it is a standalone script.

Environment variables required (see .env.example):
    OPENAI_API_KEY
    EMBEDDING_MODEL
    CHROMA_PERSIST_DIR
"""

# TODO (Story 1.3): implement index build logic
#   1. Load .env
#   2. Read data/product_catalog.csv  → format each row as a Document with metadata
#   3. Read data/faq.csv              → format each row as a Document with metadata
#   4. Initialise the embedding model from EMBEDDING_MODEL env var
#   5. Create ChromaDB client with persist_directory=CHROMA_PERSIST_DIR
#   6. Embed and upsert all documents into two collections: "catalog" and "faq"
#   7. Print a summary: "Indexed N catalog docs, M faq docs → <path>"
