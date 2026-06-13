"""
Manual retrieval-quality smoke test for the catalog and FAQ vector index.

Usage:
    python src/evaluate_retrieval.py

This is intentionally not a pytest test. It is a quick Day-1 script for checking
whether the top retrieval result points to the expected mock-data document.
"""

from __future__ import annotations

from vector_store import search


MOCK_QUERIES = [
    {
        "query": "is the men's linen shirt M white available?",
        "collection": "catalog",
        "expected_id": "P002",
        "metadata_key": "product_id",
    },
    {
        "query": "do you have same day delivery with gosend?",
        "collection": "faq",
        "expected_id": "F007",
        "metadata_key": "faq_id",
    },
    {
        "query": "what payment methods are accepted?",
        "collection": "faq",
        "expected_id": "F003",
        "metadata_key": "faq_id",
    },
    {
        "query": "black canvas tote bag price and stock",
        "collection": "catalog",
        "expected_id": "P015",
        "metadata_key": "product_id",
    },
]


def main() -> None:
    passed = 0

    for case in MOCK_QUERIES:
        matches = search(case["query"], case["collection"], top_k=3)
        top_match = matches[0] if matches else None
        actual_id = top_match["metadata"].get(case["metadata_key"]) if top_match else None
        status = "PASS" if actual_id == case["expected_id"] else "CHECK"

        if status == "PASS":
            passed += 1

        print(f"[{status}] {case['collection']} query: {case['query']}")
        print(f"  expected top id: {case['expected_id']}")
        print(f"  actual top id:   {actual_id}")
        if top_match:
            print(f"  score:           {top_match['score']}")
            print(f"  top content:     {top_match['content'].splitlines()[0]}")
        print()

    print(f"Passed {passed}/{len(MOCK_QUERIES)} top-1 checks.")
    print("If a CHECK result is still semantically correct in the top 3, inspect scores before changing code.")


if __name__ == "__main__":
    main()
