"""
app.py
======
Streamlit chat UI — entry point for the application.

Run with:
    streamlit run app.py

Layout:
    - Header bar: store name "Fashion Store 🛍️" + "Benny" bot avatar
    - Chat message area: scrollable, WhatsApp-inspired bubbles
      (user right-aligned, bot left-aligned with Benny avatar)
    - Collapsible "📎 Source" section below each bot response (NFR-05 auditability)
    - Escalation responses shown with a distinct 🔴 visual indicator
    - Text input + Send button at the bottom

State management:
    - st.session_state["messages"]   — list of {role, content, metadata} dicts (FR-06)
    - st.session_state["session_id"] — UUID generated once per browser session (for FR-07 logging)

Environment variables: loaded from .env via python-dotenv at startup.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env")

# Add src/ to path so chat_engine can import its siblings (vector_store, embeddings, logger)
sys.path.insert(0, str(ROOT_DIR / "src"))
from src.chat_engine import chat  # noqa: E402 — after sys.path fix


# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Fashion Store — Customer Service",
    page_icon="🛍️",
    layout="centered",
)


# ---------------------------------------------------------------------------
# Custom CSS — WhatsApp-inspired chat bubbles
# ---------------------------------------------------------------------------

st.markdown(
    """
    <style>
    /* ── Global ── */
    body, [data-testid="stAppViewContainer"] {
        background-color: #ECE5DD;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }

    /* ── Header ── */
    .chat-header {
        background: linear-gradient(135deg, #075E54, #128C7E);
        color: white;
        padding: 14px 20px;
        border-radius: 12px;
        display: flex;
        align-items: center;
        gap: 14px;
        margin-bottom: 20px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
    }
    .chat-header .avatar {
        background: #25D366;
        border-radius: 50%;
        width: 46px;
        height: 46px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 22px;
        flex-shrink: 0;
    }
    .chat-header .store-name {
        font-size: 18px;
        font-weight: 700;
        letter-spacing: 0.3px;
    }
    .chat-header .store-sub {
        font-size: 12px;
        opacity: 0.85;
        margin-top: 2px;
    }

    /* ── Message bubbles ── */
    .bubble-row {
        display: flex;
        margin-bottom: 8px;
    }
    .bubble-row.user   { justify-content: flex-end; }
    .bubble-row.bot    { justify-content: flex-start; }

    .bubble {
        max-width: 72%;
        padding: 10px 14px;
        border-radius: 12px;
        font-size: 14.5px;
        line-height: 1.5;
        position: relative;
        word-wrap: break-word;
    }
    .bubble.user {
        background: #DCF8C6;
        border-bottom-right-radius: 3px;
        color: #111;
    }
    .bubble.bot {
        background: #ffffff;
        border-bottom-left-radius: 3px;
        color: #111;
        box-shadow: 0 1px 2px rgba(0,0,0,0.08);
    }
    .bubble.escalated {
        border-left: 4px solid #e53935;
    }

    /* ── Intent badge ── */
    .intent-badge {
        display: inline-block;
        font-size: 10.5px;
        font-weight: 600;
        padding: 2px 7px;
        border-radius: 10px;
        margin-bottom: 5px;
        letter-spacing: 0.5px;
        text-transform: uppercase;
    }
    .badge-PRODUCT_INQUIRY  { background:#E3F2FD; color:#1565C0; }
    .badge-FAQ               { background:#E8F5E9; color:#2E7D32; }
    .badge-ORDER_TRACKING    { background:#FFF3E0; color:#E65100; }
    .badge-ESCALATION        { background:#FFEBEE; color:#C62828; }
    .badge-CLARIFICATION     { background:#F3E5F5; color:#6A1B9A; }
    .badge-OUT_OF_SCOPE      { background:#ECEFF1; color:#37474F; }

    /* ── Hide default Streamlit elements we don't need ── */
    #MainMenu, footer, [data-testid="stToolbar"] { visibility: hidden; }
    [data-testid="stSidebar"] { display: none; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------

if "session_id" not in st.session_state:
    st.session_state["session_id"] = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state["messages"] = []  # list of {role, content, metadata}


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.markdown(
    """
    <div class="chat-header">
        <div class="avatar">🛍️</div>
        <div>
            <div class="store-name">Fashion Store</div>
            <div class="store-sub">🟢 Benny — Customer Service · Online now</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Clear conversation button
# ---------------------------------------------------------------------------

if st.button("🗑️ Clear conversation", key="clear_btn"):
    st.session_state["messages"] = []
    st.session_state["session_id"] = str(uuid.uuid4())
    st.rerun()


# ---------------------------------------------------------------------------
# Chat message rendering
# ---------------------------------------------------------------------------

def _render_messages() -> None:
    for msg in st.session_state["messages"]:
        role = msg["role"]
        content = msg["content"]
        meta = msg.get("metadata", {})

        if role == "user":
            st.markdown(
                f'<div class="bubble-row user">'
                f'<div class="bubble user">{content}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            intent = meta.get("intent", "")
            escalated = meta.get("escalated", False)
            sources = meta.get("sources", [])

            escalated_class = " escalated" if escalated else ""
            escalated_prefix = "🔴 " if escalated else ""

            badge_html = ""
            if intent:
                badge_class = f"badge-{intent}"
                badge_html = (
                    f'<div><span class="intent-badge {badge_class}">{intent.replace("_", " ")}</span></div>'
                )

            st.markdown(
                f'<div class="bubble-row bot">'
                f'<div class="bubble bot{escalated_class}">'
                f'{badge_html}'
                f'{escalated_prefix}{content}'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            # NFR-05 auditability: collapsible source expander
            if sources:
                with st.expander("📎 Source", expanded=False):
                    for src in sources:
                        st.markdown(f"- `{src}`")


_render_messages()


# ---------------------------------------------------------------------------
# Chat input
# ---------------------------------------------------------------------------

user_input: str | None = st.chat_input(
    placeholder="Type your question here… e.g. Is the navy blue shirt M available?",
    key="chat_input",
)

if user_input and user_input.strip():
    user_text = user_input.strip()

    # Append user message immediately
    st.session_state["messages"].append({
        "role": "user",
        "content": user_text,
        "metadata": {},
    })

    # Build history list (role + content only, no metadata — for the LLM)
    history = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state["messages"][:-1]  # exclude the message we just added
    ]

    # Call the RAG pipeline
    with st.spinner("Benny is typing…"):
        try:
            result = chat(
                user_message=user_text,
                history=history,
                session_id=st.session_state["session_id"],
            )
            bot_response = result["response"]
            metadata = {
                "intent": result["intent"],
                "sources": result["sources"],
                "escalated": result["escalated"],
            }
        except Exception as exc:
            bot_response = (
                "Sorry, something went wrong on our end. 🙏 "
                "Please try again in a moment, or contact our admin directly."
            )
            metadata = {"intent": "ERROR", "sources": [], "escalated": False}

    # Append bot response
    st.session_state["messages"].append({
        "role": "assistant",
        "content": bot_response,
        "metadata": metadata,
    })

    st.rerun()
