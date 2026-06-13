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

from __future__ import annotations

import csv
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")

_CSV_COLUMNS = [
    "timestamp",
    "session_id",
    "user_message",
    "detected_intent",
    "bot_response",
    "escalated",
    "retrieved_source",
]

_write_lock = threading.Lock()


def _log_path() -> Path:
    raw = os.getenv("CONVERSATION_LOG_PATH", "./logs/conversations.csv")
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT_DIR / path
    return path


def log_turn(
    session_id: str,
    user_message: str,
    intent: str,
    bot_response: str,
    escalated: bool,
    sources: list[str],
) -> None:
    log_file = _log_path()
    log_file.parent.mkdir(parents=True, exist_ok=True)

    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "user_message": user_message,
        "detected_intent": intent,
        "bot_response": bot_response,
        "escalated": "Y" if escalated else "N",
        "retrieved_source": "|".join(sources),
    }

    write_header = not log_file.exists() or log_file.stat().st_size == 0

    with _write_lock:
        with log_file.open("a", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=_CSV_COLUMNS)
            if write_header:
                writer.writeheader()
            writer.writerow(row)
