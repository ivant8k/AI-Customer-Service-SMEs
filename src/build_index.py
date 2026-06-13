"""
One-time CLI script for building the catalog and FAQ vector index.

Usage:
    python src/build_index.py

Run it again whenever data/product_catalog.csv or data/faq.csv changes.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

import chromadb
from chromadb.config import Settings
from dotenv import load_dotenv

from embeddings import active_embedding_model, embed_texts
    
ROOT_DIR = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT_DIR / "data" / "product_catalog.csv"
FAQ_PATH = ROOT_DIR / "data" / "faq.csv"

def load_catalog_documents(path: Path = CATALOG_PATH) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))

    documents = []
    for row in rows:
        product_id = row["product_id"].strip()
        content = (
            f"Product: {row['name'].strip()}\n"
            f"Variant: {row['variant'].strip()}\n"
            f"Category: {row['category'].strip()}\n"
            f"Price: Rp {row['price'].strip()}\n"
            f"Stock quantity: {row['stock'].strip()}\n"
            f"Description: {row['description'].strip()}"
        )
        documents.append(
            {
                "id": f"catalog:{product_id}",
                "content": content,
                "metadata": {
                    "source": "product_catalog.csv",
                    "doc_type": "catalog",
                    "product_id": product_id,
                    "name": row["name"].strip(),
                    "variant": row["variant"].strip(),
                    "category": row["category"].strip(),
                    "price": int(row["price"]),
                    "stock": int(row["stock"]),
                },
            }
        )
    return documents

def load_faq_documents(path: Path = FAQ_PATH) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))

    documents = []
    for row in rows:
        faq_id = row["faq_id"].strip()
        content = (
            f"FAQ topic: {row['category'].strip()}\n"
            f"Question: {row['question'].strip()}\n"
            f"Answer: {row['answer'].strip()}"
        )
        documents.append(
            {
                "id": f"faq:{faq_id}",
                "content": content,
                "metadata": {
                    "source": "faq.csv",
                    "doc_type": "faq",
                    "faq_id": faq_id,
                    "category": row["category"].strip(),
                    "question": row["question"].strip(),
                },
            }
        )
    return documents

def rebuild_collection(client: chromadb.PersistentClient, name: str, documents: list[dict]) -> None:
    try:
        client.delete_collection(name)
    except ValueError:
        pass

    collection = client.get_or_create_collection(
        name=name,
        metadata={
            "hnsw:space": "cosine",
            "embedding_model": active_embedding_model(),
        },
    )
    collection.add(
        ids=[doc["id"] for doc in documents],
        documents=[doc["content"] for doc in documents],
        metadatas=[doc["metadata"] for doc in documents],
        embeddings=embed_texts(doc["content"] for doc in documents),
    )

def main() -> None:
    load_dotenv(ROOT_DIR / ".env")

    persist_dir = Path(os.getenv("CHROMA_PERSIST_DIR", ROOT_DIR / "vector_index"))
    if not persist_dir.is_absolute():
        persist_dir = ROOT_DIR / persist_dir

    catalog_documents = load_catalog_documents()
    faq_documents = load_faq_documents()

    client = chromadb.PersistentClient(
        path=str(persist_dir),
        settings=Settings(anonymized_telemetry=False),
    )
    rebuild_collection(client, "catalog", catalog_documents)
    rebuild_collection(client, "faq", faq_documents)

    print(
        f"Indexed {len(catalog_documents)} catalog docs, "
        f"{len(faq_documents)} faq docs -> {persist_dir}"
    )
    print(f"Embedding model: {active_embedding_model()}")

if __name__ == "__main__":
    main()
