"""
app.py
======
Streamlit chat UI — entry point for the application.

Run with:
    streamlit run app.py

Layout:
    - Header bar: store name "Fashion Store 🛍️" + "Alex" bot avatar
    - Chat message area: scrollable, WhatsApp-inspired bubbles
      (user right-aligned, bot left-aligned with Alex avatar)
    - Collapsible "📎 Source" section below each bot response (NFR-05 auditability)
    - Escalation responses shown with a distinct 🔴 visual indicator
    - Text input + Send button at the bottom

State management:
    - st.session_state["messages"]   — list of {role, content, metadata} dicts (FR-06)
    - st.session_state["session_id"] — UUID generated once per browser session (for FR-07 logging)

Environment variables: loaded from .env via python-dotenv at startup.
"""

# TODO (Story 1.6): implement Streamlit UI
#   1. Load .env with python-dotenv
#   2. Initialise session_state on first load (empty messages list, generate session_id)
#   3. Render header with store branding
#   4. Render existing messages from session_state (bot vs user bubble styling)
#   5. For each bot message, render a st.expander("📎 Source") showing retrieved_source
#   6. Chat input widget — on submit:
#       a. Append user message to session_state
#       b. Call src.chat_engine.chat(user_message, history, session_id)
#       c. Append bot response + metadata to session_state
#       d. Rerun to update UI
#   7. Escalated responses: render with a 🔴 icon or distinct background color
