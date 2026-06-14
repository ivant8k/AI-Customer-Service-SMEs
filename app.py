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
        background-color: #F9FAFB;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }

    /* ── Header ── */
    .chat-header {
        background: rgba(255, 255, 255, 0.8);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        color: #111827;
        padding: 16px 24px;
        border-radius: 16px;
        display: flex;
        align-items: center;
        gap: 16px;
        margin-bottom: 24px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.3);
    }
    .chat-header .avatar {
        background: linear-gradient(135deg, #6366F1, #8B5CF6);
        color: white;
        border-radius: 50%;
        width: 50px;
        height: 50px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 24px;
        flex-shrink: 0;
        box-shadow: 0 4px 10px rgba(99, 102, 241, 0.3);
    }
    .chat-header .store-name {
        font-size: 19px;
        font-weight: 700;
        letter-spacing: -0.02em;
    }
    .chat-header .store-sub {
        font-size: 13px;
        color: #6B7280;
        margin-top: 3px;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .chat-header .status-dot {
        width: 8px;
        height: 8px;
        background-color: #10B981;
        border-radius: 50%;
        display: inline-block;
        box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.2);
    }

    /* ── Message bubbles ── */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }

    .bubble-row {
        display: flex;
        margin-bottom: 16px;
        animation: fadeIn 0.3s ease-out forwards;
    }
    .bubble-row.user   { justify-content: flex-end; }
    .bubble-row.bot    { justify-content: flex-start; }

    .bubble {
        max-width: 75%;
        padding: 12px 16px;
        border-radius: 18px;
        font-size: 15px;
        line-height: 1.5;
        position: relative;
        word-wrap: break-word;
        box-shadow: 0 2px 5px rgba(0,0,0,0.04);
    }
    .bubble.user {
        background: linear-gradient(135deg, #3B82F6, #2563EB);
        color: white;
        border-bottom-right-radius: 4px;
    }
    .bubble.bot {
        background: white;
        color: #1F2937;
        border-bottom-left-radius: 4px;
        border: 1px solid #E5E7EB;
    }
    .bubble.escalated {
        border-left: 4px solid #EF4444;
    }

    /* ── Intent badge ── */
    .intent-badge {
        display: inline-block;
        font-size: 11px;
        font-weight: 600;
        padding: 4px 8px;
        border-radius: 12px;
        margin-bottom: 8px;
        letter-spacing: 0.05em;
        text-transform: uppercase;
    }
    .badge-PRODUCT_INQUIRY  { background:#E0F2FE; color:#0369A1; }
    .badge-FAQ               { background:#DCFCE7; color:#15803D; }
    .badge-ORDER_TRACKING    { background:#FFEDD5; color:#C2410C; }
    .badge-ESCALATION        { background:#FEE2E2; color:#B91C1C; }
    .badge-CLARIFICATION     { background:#F3E8FF; color:#7E22CE; }
    .badge-OUT_OF_SCOPE      { background:#F3F4F6; color:#374151; }

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
        <div class="avatar">✨</div>
        <div>
            <div class="store-name">Fashion Store</div>
            <div class="store-sub"><span class="status-dot"></span> Benny — Customer Service · Online now</div>
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
                    conf = meta.get("retrieval_confidence")
                    if conf is not None:
                        conf_color = "#2E7D32" if conf >= 0.5 else ("#E65100" if conf >= 0.25 else "#C62828")
                        st.markdown(
                            f'<span style="font-size:11px;color:{conf_color};font-weight:600;">'
                            f'Retrieval confidence: {conf:.0%}</span>',
                            unsafe_allow_html=True,
                        )
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

    # Render the user message immediately so it's visible before the bot replies
    st.markdown(
        f'<div class="bubble-row user">'
        f'<div class="bubble user">{user_text}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

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
                "retrieval_confidence": result.get("retrieval_confidence"),
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
