"""
src/logger.py
=============
Appends one row per conversation turn to logs/conversations.csv (FR-07).

Schema (CSV columns):
    timestamp       — ISO-8601 UTC
    session_id      — random UUID per browser session
    user_message    — raw user input
    detected_intent — one of: PRODUCT_INQUIRY | FAQ | ORDER_TRACKING |
                      CROSS_SELL | ESCALATION | OUT_OF_SCOPE | CLARIFICATION
    bot_response    — the full response string sent to the user
    escalated       — Y or N
    retrieved_source — pipe-separated list of source identifiers
                       e.g. "product_catalog.csv›P004|product_catalog.csv›P009"

Used by: src/chat_engine.py

Environment variables required (see .env.example):
    CONVERSATION_LOG_PATH  (default: ./logs/conversations.csv)
"""

# TODO (Story 3.1): implement logger
#   1. On first call, check if CONVERSATION_LOG_PATH exists.
#      If not, create the file and write the CSV header row.
#   2. Append one row per call — never overwrite, always append.
#   3. Thread-safe write (use a file lock or queue) in case of future async use.
#
# Public interface:
#   log_turn(session_id, user_message, intent, bot_response, escalated, sources) -> None
