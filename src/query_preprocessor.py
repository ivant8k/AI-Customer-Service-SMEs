"""
src/query_preprocessor.py
=========================
Normalize a raw user query before it is embedded for retrieval.

This does NOT change the text sent to the LLM — only the retrieval query.
The goal is to give the English-dominant embedding model (all-MiniLM-L6-v2)
the best possible signal even when the user types:
  - Indonesian fashion/FAQ vocabulary  (harga → price, stok → stock, …)
  - Common typos                       (shrit → shirt, avalaible → available, …)
  - Mixed Bahasa-Indonesia / English   (berapa harga linen shirt size M?)
  - Extra whitespace or unicode noise

Design constraints:
  - Zero extra dependencies (stdlib + re only).
  - Substitution table is explicit and auditable — no black-box spell-checker.
  - All substitutions are word-boundary anchored to avoid partial-word corruption.

Public API:
    normalize(raw: str) -> str
"""

from __future__ import annotations

import re
import unicodedata


# ---------------------------------------------------------------------------
# Substitution table
# Each entry: (compiled regex pattern, replacement string)
# Order matters — patterns are applied sequentially.
# ---------------------------------------------------------------------------

# Indonesian → English (domain vocabulary)
_ID_TO_EN: list[tuple[re.Pattern, str]] = [
    # Products / categories
    (re.compile(r"\bkaos\b", re.I), "t-shirt"),
    (re.compile(r"\bbaju\b", re.I), "shirt"),
    (re.compile(r"\bcelana\b", re.I), "pants"),
    (re.compile(r"\btas\b", re.I), "bag"),
    (re.compile(r"\btote\s?bag\b", re.I), "tote bag"),
    (re.compile(r"\bsepatu\b", re.I), "shoes"),
    (re.compile(r"\bjaket\b", re.I), "jacket"),
    (re.compile(r"\bkemeja\b", re.I), "shirt"),
    # Attributes
    (re.compile(r"\bharga\b", re.I), "price"),
    (re.compile(r"\bhrga\b", re.I), "price"), 
    (re.compile(r"\bstok\b", re.I), "stock"),
    (re.compile(r"\bwarna\b", re.I), "color"),
    (re.compile(r"\bukuran\b", re.I), "size"),
    (re.compile(r"\bukran\b", re.I), "size"), 
    (re.compile(r"\bvarian\b", re.I), "variant"),
    (re.compile(r"\btersedia\b", re.I), "available"),
    (re.compile(r"\bada\b", re.I), "available"),
    (re.compile(r"\bgak?\b", re.I), ""),
    (re.compile(r"\bngga[kh]?\b", re.I), ""),
    (re.compile(r"\b(min|kak|gan|bro|sis)\b", re.I), ""),
    # Colors
    (re.compile(r"\bhitam\b", re.I), "black"),
    (re.compile(r"\bputih\b", re.I), "white"),
    (re.compile(r"\bbiru\b", re.I), "blue"), 
    (re.compile(r"\bmerah\b", re.I), "red"),
    (re.compile(r"\bcoklat\b", re.I), "brown"),
    (re.compile(r"\babu[-. ]?abu\b", re.I), "grey"),
    (re.compile(r"\bhijau\b", re.I), "green"),
    (re.compile(r"\bkuning\b", re.I), "yellow"),
    # FAQ / store ops / verbs
    (re.compile(r"\bpengiriman\b", re.I), "shipping"),
    (re.compile(r"\bkirim\b", re.I), "shipping"),
    (re.compile(r"\bongkir\b", re.I), "shipping fee"), 
    (re.compile(r"\bpembayaran\b", re.I), "payment"),
    (re.compile(r"\bbayar\b", re.I), "payment"),
    (re.compile(r"\bpengembalian\b", re.I), "return"),
    (re.compile(r"\bretur\b", re.I), "return"),
    (re.compile(r"\bjam\s+buka\b", re.I), "operating hours"),
    (re.compile(r"\bbuka\b", re.I), "open"),
    (re.compile(r"\btutup\b", re.I), "close"),
    (re.compile(r"\balamat\b", re.I), "address"),
    (re.compile(r"\blokasi|tempat\b", re.I), "location"),
    (re.compile(r"\bgaransi\b", re.I), "warranty"),
    (re.compile(r"\bberapa\b", re.I), "how much"),
    (re.compile(r"\bbrp\b", re.I), "how much"), 
    (re.compile(r"\bkapan\b", re.I), "when"),
    (re.compile(r"\bdimana\b", re.I), "where"),
    (re.compile(r"\bbisa\b", re.I), "can"),
    (re.compile(r"\bboleh\b", re.I), "can"),
    (re.compile(r"\btolong\b", re.I), "please"),
    (re.compile(r"\bmau|peng[e|i]n\b", re.I), "want"),
    (re.compile(r"\bbantu\b", re.I), "help"),
    (re.compile(r"\bbeli|pesan\b", re.I), "buy"), 
]

# Common English typo corrections (domain-specific)
_TYPO_FIXES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bshrit\b", re.I), "shirt"),
    (re.compile(r"\bsirt\b", re.I), "shirt"),
    (re.compile(r"\bshirt's\b", re.I), "shirt"),
    (re.compile(r"\bpant's\b", re.I), "pants"),
    (re.compile(r"\bavalaible\b", re.I), "available"),
    (re.compile(r"\bavaible\b", re.I), "available"),
    (re.compile(r"\bdeliverry\b", re.I), "delivery"),
    (re.compile(r"\bpayement\b", re.I), "payment"),
    (re.compile(r"\brefudn\b", re.I), "refund"),
    (re.compile(r"\bretrun\b", re.I), "return"),
    (re.compile(r"\bcanvass\b", re.I), "canvas"),
    (re.compile(r"\bchiino\b", re.I), "chino"),
    (re.compile(r"\bchiinos\b", re.I), "chino"),
    (re.compile(r"\blinne?n\b", re.I), "linen"),
    (re.compile(r"\bwharehouse\b", re.I), "warehouse"),
    (re.compile(r"\bprce\b", re.I), "price"),
    (re.compile(r"\bpirce\b", re.I), "price"),
    (re.compile(r"\bstoc?k\b", re.I), "stock"),
    (re.compile(r"\bpls\b", re.I), "please"),
    (re.compile(r"\bu\b", re.I), "you"),
    (re.compile(r"\bur\b", re.I), "your"),
    (re.compile(r"\btmrw\b", re.I), "tomorrow"),
    (re.compile(r"\bsnd\b", re.I), "send"),
    (re.compile(r"\bbt\b", re.I), "but"),
    (re.compile(r"\bw/\b", re.I), "with"),
]

# Collapse multiple spaces that arise after substitutions
_MULTI_SPACE = re.compile(r" {2,}")

# "item" is Indonesian slang for "black" (hitam) but also a common English word.
# Only substitute it when the raw text contains another unambiguous Indonesian
# product signal, which makes it safe to treat "item" as a color.
_ITEM_IS_BLACK = re.compile(r"\bitem\b", re.I)
_ID_PRODUCT_SIGNALS = re.compile(
    r"\b(kaos|baju|celana|kemeja|hitam|ukuran|ukran|warna|varian|stok|harga|hrga|ada|berapa)\b",
    re.I,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def normalize(raw: str) -> str:
    """
    Return a retrieval-optimized version of *raw*.

    Steps:
        1. Unicode NFKC normalization (half-width → full-width, accents, etc.)
        2. Strip leading/trailing whitespace
        3. Apply Indonesian→English vocabulary substitutions
        4. Conditional: "item" → "black" only when other Indonesian signals present
        5. Apply common typo corrections
        6. Collapse multiple spaces

    The result is used ONLY for embedding / vector search.
    """
    # 1. Unicode normalization
    text = unicodedata.normalize("NFKC", raw)

    # 2. Strip
    text = text.strip()

    # 3. Indonesian → English
    for pattern, replacement in _ID_TO_EN:
        text = pattern.sub(replacement, text)

    # 4. Conditional "item" → "black"
    #    Only apply when the ORIGINAL raw text contains another clear Indonesian
    #    product signal so English queries ("Can I return the item?") are unaffected.
    if _ID_PRODUCT_SIGNALS.search(raw):
        text = _ITEM_IS_BLACK.sub("black", text)

    # 5. Typo fixes
    for pattern, replacement in _TYPO_FIXES:
        text = pattern.sub(replacement, text)

    # 6. Collapse whitespace
    text = _MULTI_SPACE.sub(" ", text).strip()

    return text
