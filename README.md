# AI-Powered Customer Support for SMEs

WIZ.AI Builder Challenge — MVP prototype of an AI chatbot that automates the most
common WhatsApp customer-service inquiries for a fashion SME, while
maintaining an authentic friendly conversational tone and preventing hallucination.

---

## Features (MVP)

| Feature | Status |
|---|---|
| FR-01 Product inquiry (catalog + stock) | ✅ Done |
| FR-02 FAQ handling (hours, payment, shipping, returns) | ✅ Done |
| FR-03 Order tracking (simulated tracking lookup) | ✅ Done |
| FR-04 Cross-sell on out-of-stock variants | ✅ Done |
| FR-05 Human handoff / escalation | ✅ Done |
| FR-06 Multi-turn conversation context | ✅ Done |
| FR-07 Conversation logging | ✅ Done |

---

## Project Structure

```
AI-Customer-Service-UMKM/
├── app.py                    # Streamlit chat UI (entry point)
├── requirements.txt
├── .env.example              # Copy to .env and fill in API keys
│
├── data/
│   ├── product_catalog.csv   # 15 mock products with variants and stock
│   ├── faq.csv               # 12 FAQ entries (hours, payment, shipping, returns)
│   └── order_tracking.csv    # 7 mock tracking numbers with delivery statuses
│
├── prompts/
│   └── system_prompt.txt     # Benny persona + guardrail rules
│
├── src/
│   ├── build_index.py        # ONE-TIME script: embed catalog+FAQ → ChromaDB
│   ├── vector_store.py       # ChromaDB search wrapper
│   ├── chat_engine.py        # Core RAG pipeline (intent → retrieval → LLM)
│   └── logger.py             # Conversation logger (FR-07)
│
├── tests/
│   ├── test_chat_engine.py   # FR-01 through FR-06 tests
│   └── test_edge_cases.py    # Section 7 edge-case & guardrail tests
│
├── logs/                     # Runtime conversation logs (git-ignored)
└── docs/
    ├── requirement.md        # Full PRD + implementation plan
    └── business_impact.md    # Business case document
```

---

## Setup

### 1. Clone & create virtual environment
```bash
git clone https://github.com/ivant8k/AI-Customer-Service-UMKM.git
cd AI-Customer-Service-UMKM
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment variables
```bash
cp .env.example .env
# Edit .env and add your GROQ_API_KEY
```

### 4. Build the vector index (one-time)
```bash
python src/build_index.py
```
This reads `data/product_catalog.csv` and `data/faq.csv`, embeds them, and
persists the index to `./vector_index/`. Re-run if the data files change.

### 5. Run the app
```bash
streamlit run app.py
```
Open your browser at `http://localhost:8501`.

---

## Running Tests
```bash
pytest tests/ -v
```

---

## Tech Stack

| Layer | Choice | Reason |
|---|---|---|
| UI | Streamlit | Fast to build, easy to demo |
| Orchestration | LangChain | Flexible RAG pipeline |
| Vector store | ChromaDB (local) | No extra infra needed |
| LLM | Groq llama-3.1-8b-instant | Fast, low-cost chat model for the MVP |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 | Local semantic retrieval without OpenAI |

---