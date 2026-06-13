"""
src/chat_engine.py
==================
Core RAG pipeline — the main entry point for each user message.

Pipeline (per message):
    1. Intent router  — classify via keyword heuristics + regex
                        PRODUCT_INQUIRY | FAQ | ORDER_TRACKING |
                        ESCALATION | OUT_OF_SCOPE | CLARIFICATION
    2. Retrieval      — search catalog/faq vector store, or exact-match
                        lookup in order_tracking.csv
    3. Generation     — build prompt (system_prompt.txt + context + history),
                        call Groq LLM, return response
    4. Logging        — append turn to conversations.csv (FR-07)

Public interface:
    chat(user_message, history, session_id) -> dict
        Returns: {response: str, intent: str, sources: list[str], escalated: bool}
"""

from __future__ import annotations

import csv
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")

# Ensure src/ is importable when run directly or via Streamlit
if str(Path(__file__).parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent))

from logger import log_turn  # noqa: E402 — after sys.path fix
from query_preprocessor import normalize as preprocess  # noqa: E402
from vector_store import search  # noqa: E402 — after sys.path fix


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_PATH = ROOT_DIR / "prompts" / "system_prompt.txt"
ORDER_TRACKING_PATH = ROOT_DIR / "data" / "order_tracking.csv"

_SYSTEM_PROMPT: str | None = None  # loaded once at first call

INTENTS = {
    "PRODUCT_INQUIRY",
    "FAQ",
    "ORDER_TRACKING",
    "ESCALATION",
    "OUT_OF_SCOPE",
    "CLARIFICATION",
}

# Minimum cosine-similarity score for a retrieval hit to be included in
# the LLM context. Hits below this threshold are still logged in sources
# for auditability but are excluded from the context block so the LLM
# does not hallucinate from weak matches.
_LOW_CONFIDENCE_THRESHOLD = float(os.getenv("RETRIEVAL_MIN_SCORE", "0.25"))

# Sentinel injected into the context block when ALL hits fail the threshold.
# The system prompt already instructs the LLM to ask for clarification when
# it lacks context — this sentinel makes that trigger explicit.
_NO_CONTEXT_SENTINEL = (
    "SYSTEM NOTE: No sufficiently relevant product or FAQ information was found "
    "for this query. Do NOT invent any facts. Politely ask the customer to "
    "rephrase or provide more details about what they are looking for."
)

# Escalation trigger keywords (FR-05)
_ESCALATION_KEYWORDS = re.compile(
    r"\b(broken|damaged|defective|complaint|refund|angry|upset|disappointed|"
    r"wrong item|never arrived|scam|fraud|terrible|horrible|awful|rude|"
    r"worst|unacceptable|return my money|worst service|i want to complain)\b",
    re.IGNORECASE,
)

# Tracking number pattern: RESI followed by alphanumeric chars
_TRACKING_PATTERN = re.compile(r"\bRESI\w+\b", re.IGNORECASE)

# FAQ trigger phrases
_FAQ_KEYWORDS = re.compile(
    r"\b(shipping|delivery|payment|return|refund policy|business hour|"
    r"open|close|location|address|cod|transfer|whatsapp|contact|"
    r"how long|when will|same.?day|warranty|exchange|method|"
    r"gosend|grabexpress|gojek|grab|jne|j.?t|sicepat|courier|kurir)\b",
    re.IGNORECASE,
)

# Product inquiry trigger phrases
_PRODUCT_KEYWORDS = re.compile(
    r"\b(product|shirt|pants|chino|tote|bag|t.?shirt|linen|oversized|"
    r"price|stock|available|in stock|size|variant|color|colour|"
    r"buy|purchase|order|catalog|catalogue|how much|berapa)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _system_prompt() -> str:
    global _SYSTEM_PROMPT
    if _SYSTEM_PROMPT is None:
        _SYSTEM_PROMPT = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    return _SYSTEM_PROMPT


def _load_order_tracking() -> dict[str, dict]:
    """Return mapping of uppercase resi_number -> row dict."""
    result: dict[str, dict] = {}
    with ORDER_TRACKING_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            key = row["resi_number"].strip().upper()
            result[key] = {k.strip(): v.strip() for k, v in row.items()}
    return result


def _detect_intent(user_message: str) -> tuple[str, str | None]:
    """
    Returns (intent, tracking_number | None).
    Uses keyword heuristics — fast and free, no extra LLM call.

    The raw message is normalized before regex matching so that Indonesian
    vocabulary (e.g. "harga", "stok", "pengiriman") and common typos
    are handled correctly by the intent router.
    """
    normalized = preprocess(user_message)

    # 1. Escalation — highest priority (check raw too — strong sentiment words
    #    are usually English and don't need normalization)
    if _ESCALATION_KEYWORDS.search(user_message) or _ESCALATION_KEYWORDS.search(normalized):
        return "ESCALATION", None

    # 2. Order tracking — regex for RESI pattern (raw, resi numbers are not translated)
    tracking_match = _TRACKING_PATTERN.search(user_message)
    if tracking_match:
        return "ORDER_TRACKING", tracking_match.group(0).upper()

    # 3. Very short / vague query → ask for clarification BEFORE keyword checks.
    #    A single word like "shirt?" is ambiguous (size? color? price?) and
    #    cannot be answered without more context.
    if len(user_message.split()) <= 2:
        return "CLARIFICATION", None

    # 4. FAQ signals — check normalized version so Indonesian FAQ terms match
    if _FAQ_KEYWORDS.search(normalized) or _FAQ_KEYWORDS.search(user_message):
        return "FAQ", None

    # 5. Product inquiry signals — check normalized so Indonesian product terms match
    if _PRODUCT_KEYWORDS.search(normalized) or _PRODUCT_KEYWORDS.search(user_message):
        return "PRODUCT_INQUIRY", None

    # 6. 3-word borderline query (e.g. "blue shirt please") — still clarify
    if len(user_message.split()) <= 3:
        return "CLARIFICATION", None

    # 7. Default: try product catalog first
    return "PRODUCT_INQUIRY", None


def _retrieve(intent: str, user_message: str) -> tuple[str, list[str], float]:
    """
    Returns (context_block_str, list_of_source_ids, max_confidence_score).

    Resilience strategy:
      1. Normalize the query before embedding (typos / Indonesian vocab).
      2. Run primary search against the intent-appropriate collection.
      3. Filter hits below _LOW_CONFIDENCE_THRESHOLD from the context block
         (they are still recorded in sources for auditability).
      4. If ALL primary hits are below threshold, cross-search the other
         collection. If that also yields nothing above threshold, inject
         _NO_CONTEXT_SENTINEL so the LLM asks for clarification instead of
         hallucinating.
    """
    top_k = int(os.getenv("RETRIEVAL_TOP_K", "4"))
    normalized_query = preprocess(user_message)

    primary_collection = "faq" if intent == "FAQ" else "catalog"
    fallback_collection = "catalog" if intent == "FAQ" else "faq"

    # Primary search
    hits = search(normalized_query, primary_collection, top_k)
    all_sources = _source_ids(hits)

    confident_hits = [h for h in hits if h["score"] >= _LOW_CONFIDENCE_THRESHOLD]
    max_score = max((h["score"] for h in hits), default=0.0)

    if confident_hits:
        return _format_hits(confident_hits), all_sources, max_score

    # Fallback: cross-search the other collection
    fallback_hits = search(normalized_query, fallback_collection, top_k)
    all_sources += _source_ids(fallback_hits)
    confident_fallback = [h for h in fallback_hits if h["score"] >= _LOW_CONFIDENCE_THRESHOLD]
    fallback_max = max((h["score"] for h in fallback_hits), default=0.0)
    max_score = max(max_score, fallback_max)

    if confident_fallback:
        return _format_hits(confident_fallback), all_sources, max_score

    # Nothing above threshold in either collection → clarification sentinel
    return _NO_CONTEXT_SENTINEL, all_sources, max_score


def _lookup_tracking(resi: str) -> tuple[str, list[str]]:
    """Returns (context_block, sources) for an order tracking query."""
    tracking_db = _load_order_tracking()
    row = tracking_db.get(resi.upper())

    if row is None:
        context = (
            f"SYSTEM NOTE: Tracking number {resi} was NOT found in the order database. "
            "Inform the customer it was not found and ask them to double-check the number."
        )
        return context, []

    context = (
        f"ORDER TRACKING RESULT:\n"
        f"  Tracking Number : {resi.upper()}\n"
        f"  Carrier         : {row.get('carrier', 'N/A')}\n"
        f"  Status          : {row.get('status', 'N/A')}\n"
        f"  Detail          : {row.get('detail', 'N/A')}\n"
        f"  Est. Arrival    : {row.get('estimated_arrival', 'N/A')}"
    )
    sources = [f"order_tracking.csv›{resi.upper()}"]
    return context, sources


def _format_hits(hits: list[dict]) -> str:
    if not hits:
        return ""
    blocks = []
    for i, hit in enumerate(hits, 1):
        blocks.append(f"[Result {i} | score={hit['score']}]\n{hit['content']}")
    return "\n\n".join(blocks)


def _source_ids(hits: list[dict]) -> list[str]:
    ids = []
    for hit in hits:
        meta = hit.get("metadata", {})
        source = meta.get("source", "unknown")
        doc_id = meta.get("product_id") or meta.get("faq_id") or "?"
        ids.append(f"{source}›{doc_id}")
    return ids


def _build_messages(
    system_prompt: str,
    context_block: str,
    history: list[dict],
    user_message: str,
    max_turns: int,
) -> list[dict]:
    """
    Assemble the messages list for the Groq API call.
    History format: list of {role: "user"|"assistant", content: str}
    """
    messages: list[dict] = [{"role": "system", "content": system_prompt}]

    # Inject retrieved context as a system-level note before the conversation
    if context_block:
        messages.append({
            "role": "system",
            "content": (
                "RETRIEVED CONTEXT (use this to answer the customer's question — "
                "do not invent any information beyond what is shown here):\n\n"
                + context_block
            ),
        })

    # Append truncated history (FR-06 multi-turn)
    recent = history[-(max_turns * 2):]  # each turn = 2 messages (user + assistant)
    for turn in recent:
        messages.append({"role": turn["role"], "content": turn["content"]})

    messages.append({"role": "user", "content": user_message})
    return messages


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def chat(
    user_message: str,
    history: list[dict],
    session_id: str,
) -> dict:
    """
    Main entry point for each user message.

    Args:
        user_message: The raw user input string.
        history:      List of previous turns as {role, content} dicts.
        session_id:   UUID string identifying this browser session.

    Returns:
        {
            "response":  str,        # The bot's reply text
            "intent":    str,        # Detected intent label
            "sources":   list[str],  # Source identifiers for audit (NFR-05)
            "escalated": bool,       # True if this was an escalation response
        }
    """
    max_turns = int(os.getenv("MAX_HISTORY_TURNS", "5"))

    # Step 1: Intent routing
    intent, tracking_number = _detect_intent(user_message)

    # Step 2: Retrieval
    retrieval_confidence = 1.0  # non-vector intents are always "confident"
    if intent == "ORDER_TRACKING" and tracking_number:
        context_block, sources = _lookup_tracking(tracking_number)
    elif intent in ("ESCALATION", "OUT_OF_SCOPE", "CLARIFICATION"):
        context_block, sources = "", []
    else:
        context_block, sources, retrieval_confidence = _retrieve(intent, user_message)

    # When preprocessing significantly changed the query (e.g. Indonesian/mixed-language),
    # send the normalized English text as the LLM user message so the model can process
    # it cleanly. The raw message is preserved for logging (FR-07).
    # A context note informs Benny of the original phrasing.
    llm_user_message = user_message
    if intent not in ("ESCALATION", "OUT_OF_SCOPE", "CLARIFICATION", "ORDER_TRACKING"):
        normalized = preprocess(user_message)
        if normalized.strip().lower() != user_message.strip().lower():
            llm_user_message = normalized
            if context_block:
                context_block = (
                    f"NOTE: The customer's message was in Indonesian/mixed language. "
                    f"Original: \"{user_message}\"\n\n"
                    + context_block
                )

    escalated = intent == "ESCALATION"

    # Step 3: Generation
    system_prompt = _system_prompt()
    messages = _build_messages(system_prompt, context_block, history, llm_user_message, max_turns)

    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    completion = client.chat.completions.create(
        model=os.getenv("LLM_MODEL", "llama-3.1-8b-instant"),
        messages=messages,
        temperature=0.3,
        max_tokens=512,
    )
    response_text = completion.choices[0].message.content.strip()

    # Step 4: Logging (FR-07)
    try:
        log_turn(
            session_id=session_id,
            user_message=user_message,
            intent=intent,
            bot_response=response_text,
            escalated=escalated,
            sources=sources,
        )
    except Exception:
        pass  # Logging failure must never crash the chat

    return {
        "response": response_text,
        "intent": intent,
        "sources": sources,
        "escalated": escalated,
        "retrieval_confidence": round(retrieval_confidence, 3),
    }
