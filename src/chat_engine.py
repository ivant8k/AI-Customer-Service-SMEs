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
    3. Cross-sell     — inject in-stock alternatives when top hit is OOS (FR-04)
    4. Generation     — build prompt (system_prompt.txt + context + history),
                        call Groq LLM, return response
                        NOTE: ESCALATION and OUT_OF_SCOPE short-circuit step 4
                        with a deterministic message — no LLM call needed.
    5. Logging        — append turn to conversations.csv (FR-07)

Public interface:
    chat(user_message, history, session_id) -> dict
        Returns: {response: str, intent: str, sources: list[str],
                  escalated: bool, retrieval_confidence: float}
"""

from __future__ import annotations

import csv
import os
import re
import sys
from functools import lru_cache
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
PRODUCT_CATALOG_PATH = ROOT_DIR / "data" / "product_catalog.csv"

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

# ---------------------------------------------------------------------------
# Deterministic response messages (no LLM call needed)
# ---------------------------------------------------------------------------

# FR-05: fixed handoff message — matches the requirement verbatim
_ESCALATION_RESPONSE = (
    "I apologize for the unpleasant experience. 🙏 "
    "I will connect you with our admin right away. "
    "Please wait a moment, our team will assist you shortly."
)

# NFR-02: fixed decline for out-of-scope / prompt-injection attempts
_OUT_OF_SCOPE_RESPONSE = (
    "I'm sorry, I can only help with questions about products and orders "
    "at this store. 😊 Is there anything related to our products or services "
    "I can help you with?"
)

# ---------------------------------------------------------------------------
# Intent classification patterns
# ---------------------------------------------------------------------------

# Escalation trigger keywords (FR-05) — checked first (highest priority)
_ESCALATION_KEYWORDS = re.compile(
    r"\b(broken|damaged|defective|complaint|refund|angry|upset|disappointed|"
    r"wrong item|never arrived|scam|fraud|terrible|horrible|awful|rude|"
    r"worst|unacceptable|return my money|worst service|i want to complain|"
    r"very disappointed|sangat kecewa|komplain|kecewa|rusak|barang salah|"
    r"tidak sampai|penipuan|menipu)\b",
    re.IGNORECASE,
)

# Prompt injection / jailbreak attempts (NFR-02) — treated as OUT_OF_SCOPE
_PROMPT_INJECTION_PATTERN = re.compile(
    r"(ignore\s+(previous|all|above)\s+instruction|forget\s+(your\s+)?(rule|instruction)|"
    r"you\s+are\s+now\s+|pretend\s+(to\s+be|you\s+are)|act\s+as\s+(a\s+)?(DAN|GPT|AI\b|robot)|"
    r"jailbreak|new\s+persona|override\s+(your\s+)?(instruction|rule|prompt)|"
    r"disregard\s+(your|all)\s+(rule|instruction)|system\s+prompt\s+(is|says)|"
    r"reveal\s+(your\s+)?(prompt|instruction))",
    re.IGNORECASE,
)

# Out-of-scope topic signals (NFR-02) — politely declined without RAG
_OUT_OF_SCOPE_PATTERN = re.compile(
    r"\b(weather|forecast|politics|election|president|prime\s+minister|"
    r"football|soccer|basketball|sport|crypto|bitcoin|ethereum|stock\s+market|"
    r"recipe|cook\s+food|bake\s+a|homework|essay|thesis|translate\s+(this\s+)?text|"
    r"tell\s+(me\s+)?a\s+joke|who\s+is\s+(the\s+)?(king|president|prime)|"
    r"capital\s+of|history\s+of|geography|science\s+fact|mathematics|"
    r"write\s+(\w+\s+){0,3}(code|program|script|song|poem|essay)|"
    r"debug\s+(my\s+)?code|"
    r"programming\s+help|recommend\s+(a\s+)?(movie|film|book|restaurant)|"
    r"what\s+is\s+the\s+meaning\s+of\s+life)\b",
    re.IGNORECASE,
)

# FR-03: tracking number detection — tolerates separators and Indonesian prefixes.
# Strategy: find any token that starts with "RESI" followed by digits/alphanum,
# optionally preceded by an Indonesian label ("nomor resi", "no resi", etc.)
# or a separator. We do NOT use a single combined pattern to avoid "resi is RESI001"
# matching "RESIIS" — instead we require the captured token to be RESI+digit/alnum.
_TRACKING_PATTERN = re.compile(
    r"\b(RESI[\-\s]?\d[\w\-]*)\b",   # RESI immediately followed by a digit then word chars
    re.IGNORECASE,
)

# FAQ trigger phrases
_FAQ_KEYWORDS = re.compile(
    r"\b(shipping|delivery|payment|return|refund policy|business\s+hours?|"
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


@lru_cache(maxsize=1)
def _load_product_catalog() -> list[dict]:
    """
    Load product_catalog.csv once and cache it for the process lifetime.
    Returns a list of row dicts with stripped keys/values.
    Used exclusively by the cross-sell logic (FR-04) — not for RAG retrieval.
    """
    rows: list[dict] = []
    with PRODUCT_CATALOG_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            rows.append({k.strip(): v.strip() for k, v in row.items()})
    return rows


def _normalize_resi(raw_resi: str) -> str:
    """
    Strip separators (spaces, hyphens) from a raw RESI token and uppercase it,
    so 'RESI 001', 'RESI-001', and 'RESI001' all resolve to 'RESI001'.
    """
    return re.sub(r"[\s\-]", "", raw_resi).upper()


def _detect_intent(user_message: str) -> tuple[str, str | None]:
    """
    Returns (intent, tracking_number | None).
    Uses keyword heuristics — fast and free, no extra LLM call.

    Priority order (highest to lowest):
      1. ESCALATION      — complaints / strong negative sentiment
      2. OUT_OF_SCOPE    — prompt injection or clearly off-topic
      3. ORDER_TRACKING  — RESI pattern detected
      4. CLARIFICATION   — very short / vague query (≤2 words)
      5. FAQ             — operational FAQ signals
      6. PRODUCT_INQUIRY — product catalog signals
      7. CLARIFICATION   — borderline short (≤3 words)
      8. PRODUCT_INQUIRY — default fallback
    """
    normalized = preprocess(user_message)

    # 1. Escalation — highest priority
    if _ESCALATION_KEYWORDS.search(user_message) or _ESCALATION_KEYWORDS.search(normalized):
        return "ESCALATION", None

    # 2. Prompt injection / out-of-scope (NFR-02)
    if _PROMPT_INJECTION_PATTERN.search(user_message):
        return "OUT_OF_SCOPE", None
    if _OUT_OF_SCOPE_PATTERN.search(user_message) or _OUT_OF_SCOPE_PATTERN.search(normalized):
        return "OUT_OF_SCOPE", None

    # 3. Order tracking — RESI pattern (raw; RESI numbers are not translated)
    tracking_match = _TRACKING_PATTERN.search(user_message)
    if tracking_match:
        raw_resi = tracking_match.group(1)
        return "ORDER_TRACKING", _normalize_resi(raw_resi)

    # 4. Very short / vague query → ask for clarification BEFORE keyword checks
    if len(user_message.split()) <= 2:
        return "CLARIFICATION", None

    # 5. FAQ signals — check normalized version so Indonesian FAQ terms match
    if _FAQ_KEYWORDS.search(normalized) or _FAQ_KEYWORDS.search(user_message):
        return "FAQ", None

    # 6. Product inquiry signals
    if _PRODUCT_KEYWORDS.search(normalized) or _PRODUCT_KEYWORDS.search(user_message):
        return "PRODUCT_INQUIRY", None

    # 7. 3-word borderline query (e.g. "blue shirt please") — still clarify
    if len(user_message.split()) <= 3:
        return "CLARIFICATION", None

    # 8. Default: try product catalog
    return "PRODUCT_INQUIRY", None


def _count_consecutive_clarifications(history: list[dict]) -> int:
    """
    Count how many of the most-recent bot turns had CLARIFICATION intent.
    Used to auto-escalate after repeated failed attempts (FR-05).
    History entries are {role, content} — intent is not stored here, so we
    detect clarification responses heuristically by their opening phrases.
    """
    clarification_phrases = (
        "could you please",
        "could you tell me",
        "could you specify",
        "please provide more details",
        "please tell me more",
        "could you clarify",
        "i need a bit more",
    )
    count = 0
    for turn in reversed(history):
        if turn["role"] != "assistant":
            continue
        content_lower = turn["content"].lower()
        if any(phrase in content_lower for phrase in clarification_phrases):
            count += 1
        else:
            break  # stop at first non-clarification bot turn
    return count


# ---------------------------------------------------------------------------
# FR-04: Cross-sell context injection
# ---------------------------------------------------------------------------

def _find_cross_sell_alternatives(
    top_hit_content: str,
    top_hit_metadata: dict,
) -> str | None:
    """
    Inspect the top retrieval hit. If its stock is 0, find in-stock alternatives
    from the catalog CSV and return a formatted context block for the LLM.

    Search strategy (in order):
      1. Same product name, different variant, stock > 0  (up to 2 results)
      2. Same category, different product name, stock > 0 (up to 2 results, fallback)

    Returns None if the top hit is in-stock (no cross-sell needed).
    Returns a formatted string if alternatives were found.
    Returns a "no alternatives" note if the top hit is OOS but nothing else is available.
    """
    # Determine stock from the hit metadata (catalog rows have stock in the doc text)
    # The document text format is: "... stock: <n> ..." (from build_index.py)
    # We parse the product_id from metadata to look up authoritative CSV data.
    product_id = top_hit_metadata.get("product_id", "")
    if not product_id:
        return None

    catalog = _load_product_catalog()
    # Find the matching row to get authoritative stock level
    matched_row: dict | None = None
    for row in catalog:
        if row.get("product_id", "").upper() == product_id.upper():
            matched_row = row
            break

    if matched_row is None:
        return None

    try:
        stock = int(matched_row.get("stock", "0"))
    except ValueError:
        return None

    if stock > 0:
        return None  # In stock — no cross-sell needed

    # Out of stock — find alternatives
    product_name = matched_row.get("name", "").strip()
    category = matched_row.get("category", "").strip()

    alternatives: list[dict] = []

    # Strategy 1: same product name, different variant, in-stock
    for row in catalog:
        if (
            row.get("name", "").strip() == product_name
            and row.get("product_id", "") != product_id
        ):
            try:
                alt_stock = int(row.get("stock", "0"))
            except ValueError:
                alt_stock = 0
            if alt_stock > 0:
                alternatives.append(row)
            if len(alternatives) >= 2:
                break

    # Strategy 2: same category, different product name, in-stock (fallback)
    if not alternatives and category:
        for row in catalog:
            if (
                row.get("category", "").strip() == category
                and row.get("name", "").strip() != product_name
            ):
                try:
                    alt_stock = int(row.get("stock", "0"))
                except ValueError:
                    alt_stock = 0
                if alt_stock > 0:
                    alternatives.append(row)
            if len(alternatives) >= 2:
                break

    if not alternatives:
        return (
            f"\nCROSS-SELL NOTE: The requested variant ({matched_row.get('variant', '')}) "
            f"is out of stock and no in-stock alternatives are currently available for "
            f"\"{product_name}\". Inform the customer politely."
        )

    lines = [
        f"\nCROSS-SELL NOTE: The requested variant ({matched_row.get('variant', '')}) "
        f"of \"{product_name}\" is OUT OF STOCK (stock=0). "
        f"Suggest the following in-stock alternative(s) from the catalog — "
        f"DO NOT mention any product not listed here:"
    ]
    for alt in alternatives:
        lines.append(
            f"  - {alt.get('name')} | Variant: {alt.get('variant')} | "
            f"Price: Rp {int(alt.get('price', 0)):,} | "
            f"Stock: {alt.get('stock')} | "
            f"Description: {alt.get('description', '')}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def _retrieve(intent: str, user_message: str) -> tuple[str, list[str], float, dict | None]:
    """
    Returns (context_block_str, list_of_source_ids, max_confidence_score,
             top_hit_metadata | None).

    top_hit_metadata is passed to the cross-sell check (FR-04).

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
        top_meta = confident_hits[0].get("metadata", {}) if confident_hits else None
        return _format_hits(confident_hits), all_sources, max_score, top_meta

    # Fallback: cross-search the other collection
    fallback_hits = search(normalized_query, fallback_collection, top_k)
    all_sources += _source_ids(fallback_hits)
    confident_fallback = [h for h in fallback_hits if h["score"] >= _LOW_CONFIDENCE_THRESHOLD]
    fallback_max = max((h["score"] for h in fallback_hits), default=0.0)
    max_score = max(max_score, fallback_max)

    if confident_fallback:
        top_meta = confident_fallback[0].get("metadata", {}) if confident_fallback else None
        return _format_hits(confident_fallback), all_sources, max_score, top_meta

    # Nothing above threshold in either collection → clarification sentinel
    return _NO_CONTEXT_SENTINEL, all_sources, max_score, None


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
            "response":             str,        # The bot's reply text
            "intent":               str,        # Detected intent label
            "sources":              list[str],  # Source identifiers for audit (NFR-05)
            "escalated":            bool,       # True if this was an escalation response
            "retrieval_confidence": float,      # Confidence score (0–1)
        }
    """
    max_turns = int(os.getenv("MAX_HISTORY_TURNS", "5"))

    # -----------------------------------------------------------------------
    # Step 1: Intent routing
    # -----------------------------------------------------------------------
    intent, tracking_number = _detect_intent(user_message)

    # FR-05: auto-escalate after ≥3 consecutive clarification failures
    if intent == "CLARIFICATION":
        if _count_consecutive_clarifications(history) >= 2:
            # 2 prior clarification bot turns + this new one = 3rd attempt
            intent = "ESCALATION"

    # -----------------------------------------------------------------------
    # Step 2: Short-circuit for deterministic intents (no LLM call needed)
    # -----------------------------------------------------------------------

    if intent == "ESCALATION":
        _safe_log(session_id, user_message, intent, _ESCALATION_RESPONSE, escalated=True, sources=[])
        return {
            "response": _ESCALATION_RESPONSE,
            "intent": intent,
            "sources": [],
            "escalated": True,
            "retrieval_confidence": 1.0,
        }

    if intent == "OUT_OF_SCOPE":
        _safe_log(session_id, user_message, intent, _OUT_OF_SCOPE_RESPONSE, escalated=False, sources=[])
        return {
            "response": _OUT_OF_SCOPE_RESPONSE,
            "intent": intent,
            "sources": [],
            "escalated": False,
            "retrieval_confidence": 1.0,
        }

    # -----------------------------------------------------------------------
    # Step 3: Retrieval
    # -----------------------------------------------------------------------
    retrieval_confidence = 1.0  # non-vector intents are always "confident"
    top_hit_metadata: dict | None = None

    if intent == "ORDER_TRACKING" and tracking_number:
        context_block, sources = _lookup_tracking(tracking_number)
    elif intent == "CLARIFICATION":
        context_block, sources = "", []
    else:
        context_block, sources, retrieval_confidence, top_hit_metadata = _retrieve(
            intent, user_message
        )

    # -----------------------------------------------------------------------
    # Step 4: FR-04 — Cross-sell injection (PRODUCT_INQUIRY only)
    # -----------------------------------------------------------------------
    if intent == "PRODUCT_INQUIRY" and top_hit_metadata:
        cross_sell_note = _find_cross_sell_alternatives(
            top_hit_content="",  # unused — metadata lookup is authoritative
            top_hit_metadata=top_hit_metadata,
        )
        if cross_sell_note:
            context_block = context_block + cross_sell_note

    # -----------------------------------------------------------------------
    # Step 5: Normalize LLM user message for non-English inputs
    # -----------------------------------------------------------------------
    # When preprocessing significantly changed the query (e.g. Indonesian/mixed-language),
    # send the normalized English text as the LLM user message so the model can process
    # it cleanly. The raw message is preserved for logging (FR-07).
    llm_user_message = user_message
    if intent not in ("CLARIFICATION", "ORDER_TRACKING"):
        normalized = preprocess(user_message)
        if normalized.strip().lower() != user_message.strip().lower():
            llm_user_message = normalized
            if context_block and not context_block.startswith("SYSTEM NOTE"):
                context_block = (
                    f"NOTE: The customer's message was in Indonesian/mixed language. "
                    f"Original: \"{user_message}\"\n\n"
                    + context_block
                )

    # -----------------------------------------------------------------------
    # Step 6: LLM generation
    # -----------------------------------------------------------------------
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

    # -----------------------------------------------------------------------
    # Step 7: Logging (FR-07)
    # -----------------------------------------------------------------------
    _safe_log(session_id, user_message, intent, response_text, escalated=False, sources=sources)

    return {
        "response": response_text,
        "intent": intent,
        "sources": sources,
        "escalated": False,
        "retrieval_confidence": round(retrieval_confidence, 3),
    }


def _safe_log(
    session_id: str,
    user_message: str,
    intent: str,
    bot_response: str,
    escalated: bool,
    sources: list[str],
) -> None:
    """Wrap log_turn so logging failures never crash the chat pipeline."""
    try:
        log_turn(
            session_id=session_id,
            user_message=user_message,
            intent=intent,
            bot_response=bot_response,
            escalated=escalated,
            sources=sources,
        )
    except Exception:
        pass
