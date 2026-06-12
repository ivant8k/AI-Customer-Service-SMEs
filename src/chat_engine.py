"""
src/chat_engine.py
==================
Core RAG pipeline — the main entry point for each user message.

Pipeline (per message):
    1. Intent router  — classify the user message into one of:
                        PRODUCT_INQUIRY | FAQ | ORDER_TRACKING | ESCALATION | OUT_OF_SCOPE
    2. Retrieval      — based on intent, search the appropriate collection(s) via vector_store.py
                        or do an exact-match lookup in order_tracking.csv
    3. Generation     — build the prompt (system_prompt.txt + retrieved context + history),
                        call the LLM, return the response string
    4. Logging        — call src/logger.py to append the turn to conversations.csv (FR-07)

Handles FR-01 through FR-06 and NFR-01 through NFR-05.

Environment variables required (see .env.example):
    OPENAI_API_KEY (or GROQ_API_KEY if LLM_PROVIDER=groq)
    LLM_PROVIDER, LLM_MODEL
    MAX_HISTORY_TURNS  (default: 5)
"""

# TODO (Story 1.5): implement the full RAG pipeline
#   Step 1 — Intent router
#       - Lightweight classification: keyword heuristics first (fast, free),
#         fall back to a short LLM call only if ambiguous.
#       - Resi pattern detection (FR-03): regex for RESI\w+ or similar numeric patterns.
#       - Escalation signals (FR-05): keywords for complaint/frustration + sentiment check.
#
#   Step 2 — Retrieval (per intent)
#       - PRODUCT_INQUIRY / FAQ → vector_store.search() against "catalog" / "faq" collection
#       - ORDER_TRACKING        → exact resi lookup in data/order_tracking.csv (no vector needed)
#       - ESCALATION / OUT_OF_SCOPE → no retrieval, use hardcoded response template from prompt
#
#   Step 3 — Generation
#       - Load system_prompt.txt once at module import (not per call)
#       - Build messages list: [system, ...history[-MAX_HISTORY_TURNS:], user]
#       - Inject retrieved context as an assistant-facing block before the user message
#       - Call LLM (OpenAI or Groq based on LLM_PROVIDER)
#       - Return response string + metadata dict {intent, sources, escalated}
#
#   Step 4 — Logging
#       - Call logger.log_turn(session_id, user_msg, intent, response, escalated, sources)
#
# Public interface:
#   chat(user_message: str, history: list[dict], session_id: str) -> dict
#       Returns: {response: str, intent: str, sources: list[str], escalated: bool}
