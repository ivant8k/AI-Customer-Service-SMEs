# Product Requirements Document (PRD)
## AI-Powered Customer Support for Indonesian SMEs (UMKM) — MVP

**Project:** AI-Powered UMKM Customer Support Prototype  
**Context:** WIZ.AI Builder Challenge  
**Timeline:** 3 days  
**Document owner:** Ivant Samuel Silaban  
**Version:** 1.0  

---

## 1. Executive Summary

Indonesian SMEs (UMKM) typically receive hundreds of WhatsApp messages per day covering product inquiries, pricing, order/delivery status, and payment questions. Most of this volume is repetitive and can be safely automated, but customers still expect a fast, warm, and "human-feeling" response.

This project delivers a working AI chatbot prototype that automates the most common categories of customer inquiries while preserving the friendly, conversational tone Indonesian customers expect from small-business sellers ("Kak/Min" style). The system is built with strict guardrails so it never invents products, prices, discounts, or policies, and it knows when to hand off to a human agent.

The goal of this MVP is not full production deployment, but a credible, demoable proof of concept that clearly shows: (1) the AI can correctly handle realistic, messy, real-world inputs, and (2) the business value of automating this layer of support is significant and measurable.

---

## 2. Problem Statement & Goals

### 2.1 Problem
- Customer service for UMKM is largely manual (1 admin handling WhatsApp chats), creating slow response times, inconsistent answers, and limited availability (business hours only).
- A large share of incoming messages are repetitive (stock, price, hours, delivery status), taking time away from high-value tasks like closing sales or handling complaints.
- Admins may give inconsistent or inaccurate answers about stock/price under time pressure, hurting trust.

### 2.2 Goals for the MVP
- Automate the top recurring inquiry types (product info, FAQ, order tracking, cross-sell) with high accuracy.
- Maintain a tone and persona consistent with how Indonesian UMKM sellers communicate.
- Prevent hallucination of products, prices, discounts, or policies (a critical trust and legal risk for any business).
- Detect situations the AI should not handle (complaints, negative sentiment, out-of-scope topics, manipulation attempts) and escalate gracefully to a human.
- Demonstrate a clear, honest business case for adoption — without inflating numbers.

### 2.3 Non-Goals (Out of Scope for this MVP)
- Real payment processing or order placement (simulated only).
- Real WhatsApp Business API integration (a sandbox/web simulation is acceptable given the 2-day timeline).
- Multi-language support beyond Bahasa Indonesia (and Indonesian-English code-switching, which is common in casual chat).
- Multi-tenant support for multiple stores (single demo store is sufficient).

---

## 3. Scope of Work

### 3.1 Functional Requirements

| ID | Requirement | Description |
|---|---|---|
| **FR-01** | Product Inquiry (Catalog & Stock) | Understands questions about products and returns accurate info on availability, price, variants, and short description, sourced only from the product catalog (no invented data). |
| **FR-02** | FAQ Handling | Answers standard operational questions: business hours, payment methods, store location, shipping options, and return/refund policy, sourced from a FAQ knowledge base. |
| **FR-03** | Order Tracking (Simulated) | Detects a tracking/receipt number (resi) in the user's message and returns the corresponding delivery status from a mock dataset. |
| **FR-04** | Cross-Selling | When the requested product/variant is out of stock, automatically suggests a relevant in-stock alternative from the catalog. |
| **FR-05** | Human Handoff / Escalation | Detects complaints, negative sentiment, requests outside the bot's scope, or repeated failed attempts, and responds with a clear handoff message indicating a human agent will follow up. |
| **FR-06** (new) | Multi-turn Context | Maintains context across a short conversation (e.g., "Ada warna lain?" referring to the product mentioned two messages earlier), not just single-turn Q&A. |
| **FR-07** (new) | Conversation Logging | Logs each conversation (intent detected, response given, escalation flag) to support the business-impact analysis and future fine-tuning. |

### 3.2 Non-Functional Requirements

| ID | Requirement | Description |
|---|---|---|
| **NFR-01** | Tone & Persona | Responses use a warm, polite Indonesian SME customer-service style ("Kak", "Min", emoji used sparingly), consistent across all answers. |
| **NFR-02** | Guardrails / Anti-Hallucination | The system must never invent products, prices, discounts, stock levels, or policies. All factual claims must trace back to the provided catalog/FAQ/order data. Out-of-scope topics (politics, general knowledge, unrelated requests) are politely declined. |
| **NFR-03** | Latency | Target response time under 5 seconds from message received to response generated, under normal load for the demo. |
| **NFR-04** (new) | Transparency of Escalation | When handing off to a human, the bot clearly tells the customer this is happening (no silent failures or vague non-answers). |
| **NFR-05** (new) | Auditability | For the demo, it should be possible to show *why* the bot gave a particular answer (e.g., which catalog/FAQ entry was retrieved), to build trust with stakeholders evaluating the prototype. |

---

## 4. Data Requirements

Small, mock datasets are sufficient for the MVP, in `.csv` or `.json` format:

1. **Product Catalog** — Product ID, Name, Variant/Size, Price, Stock Quantity, Short Description, (optional) Category — used for cross-sell matching.
2. **FAQ Knowledge Base** — Question/topic, Answer, (optional) Category (e.g., shipping, payment, store info, returns).
3. **Order/Shipping Status** — Mock mapping of tracking numbers to statuses (e.g., `RESI123 → "Sedang dikirim oleh kurir, estimasi tiba besok"`).
4. **Conversation Log (output)** — Generated during testing/demo: timestamp, user message, detected intent, bot response, escalated (Y/N).

*Recommendation:* keep each dataset small but realistic (10–20 products, 10–15 FAQ entries, 5–10 mock tracking numbers) — enough to demonstrate range without slowing down development.

---

## 5. Technology Stack

| Component | Suggested Option(s) | Notes |
|---|---|---|
| User Interface | Streamlit or Gradio (web chat UI), or a WhatsApp sandbox (e.g., Twilio) | A simple chat UI styled to resemble WhatsApp is usually faster to build and demo than a real WhatsApp sandbox integration within 2 days. |
| Orchestration / RAG | LangChain or LlamaIndex | Either is fine for a small MVP; pick whichever you're more comfortable with to save time. |
| Vector Store | ChromaDB or FAISS (local) | Local, no extra infrastructure needed. |
| LLM | An instruction-tuned model via API (e.g., from OpenAI, Anthropic, or Groq) | I'm not certain which specific model versions/pricing tiers are currently available or cheapest — check current provider documentation before committing, since model lineups and pricing change frequently. |
| Embeddings | A standard embedding model (e.g., OpenAI's embedding API or an open-source HuggingFace sentence-embedding model) | Choose based on whichever LLM provider you're already using, to simplify API key management. |

**Suggested architecture (high-level):**
1. User message → Intent/router layer (classify: product inquiry, FAQ, tracking, complaint/escalation, out-of-scope).
2. Based on intent → retrieve relevant context (catalog entry, FAQ entry, or tracking record).
3. LLM generates the final response using retrieved context + persona/style instructions + guardrail instructions.
4. Response + metadata logged for the business-impact report.

This separation (intent routing → retrieval → constrained generation) is what makes the anti-hallucination guarantee credible — the LLM is always grounded in retrieved data rather than answering from "memory."

---

## 6. Example Conversation Flows (for demo script)

It's worth scripting 4–6 short example conversations to use in the demo video, covering both "happy path" and edge cases:

1. **Product inquiry (happy path):** "Kak, baju ukuran M warna biru masih ada?" → bot returns stock, price, short description.
2. **Cross-sell:** Customer asks about an out-of-stock variant → bot informs it's out of stock and suggests an in-stock alternative.
3. **FAQ:** "Kalau order hari ini, sampe kapan ya?" → bot answers from shipping FAQ.
4. **Order tracking:** Customer sends a resi number → bot returns mock status.
5. **Escalation (complaint):** "Barang saya rusak nih, kecewa banget" → bot acknowledges, apologizes, and hands off to a human agent.
6. **Guardrail test:** Customer asks for a discount not in the catalog, or asks an off-topic question (e.g., politics), or attempts a prompt injection → bot politely declines per the rules in Section 7.

---

## 7. Edge Case Handling

| Scenario | Expected Behavior |
|---|---|
| **Slang / typos / abbreviations** | The LLM should infer intent despite typos or informal abbreviations (e.g., "bsk dkirim pke gosend bs?" → understood as "Can it be shipped via GoSend tomorrow?"). |
| **Ambiguous query (missing context)** | The bot does not guess. It asks for clarification, e.g., *"Boleh sebutkan nama/varian produk yang Kakak maksud, ya Kak?"* |
| **Prompt injection** | The bot ignores instructions embedded in user messages that attempt to override its persona or rules, and responds with something like: *"Maaf Kak, aku cuma bisa bantu soal produk dan pesanan di toko ini ya."* |
| **Pressure for unlisted discounts** | The bot politely holds the line: *"Mohon maaf Kak, untuk harga sudah net sesuai yang tertera ya."* |
| **Negative sentiment / complaint** | The bot acknowledges the feeling, apologizes briefly, and escalates to a human — it does not attempt to resolve complaints itself. |
| **Out-of-scope topics** (politics, general knowledge, unrelated requests) | The bot politely declines and redirects to store-related topics. |

---

## 8. Two-Day Implementation Plan (Suggested)

This is a suggested breakdown — adjust based on your actual pace. The main risk in a 2-day build is usually scope creep, so the priority order matters more than exact timing.

**Day 1**
- Set up project structure, prepare mock datasets (catalog, FAQ, tracking).
- Build the retrieval layer (vector store for catalog + FAQ).
- Build the basic chat UI (Streamlit/Gradio) with a simple persona prompt.
- Implement FR-01 and FR-02 (product inquiry + FAQ) end-to-end and test with realistic messy inputs.

**Day 2**
- Implement FR-03 (order tracking), FR-04 (cross-sell), FR-05 (escalation detection).
- Implement guardrails (NFR-02) and test against the edge cases in Section 7.
- Add conversation logging (FR-07) for the business-impact analysis.
- Record the demo video and finalize the business impact document.
- Buffer time for bug fixes and polish.

---

## 9. Deliverables

1. **Working Prototype** — A web-based chat application (or sandbox chat) that can be tested live, demonstrating FR-01 through FR-07.
2. **Demo Video / Presentation** (3–5 minutes) — A screen recording showing both normal use cases and edge cases (Section 6), narrated to explain what's happening and why it matters for an UMKM owner.
3. **Business Impact Document** — A short explanation of the expected operational benefits (Section 10), framed honestly as estimates to be validated with real data.

---

## 10. Business Impact (Framing Notes)

This section should explain *why* this matters to an UMKM owner, but the numbers used should be presented as estimates/assumptions, not as proven facts — both because this is a prototype (no production data yet) and because real impact varies a lot by business size, message volume, and how many inquiries are actually automatable.

Suggested structure for the Business Impact Document:

- **Time savings:** Estimate the proportion of daily messages that fall into the automatable categories (product info, FAQ, tracking) based on the demo's intent-classification logs, and frame the time saved as "X out of Y messages no longer require manual typing by an admin" — using your own demo data rather than an invented industry-wide percentage.
- **Response availability:** The bot can respond outside business hours (24/7), which is a qualitative benefit that's easy to state honestly without needing a specific statistic.
- **Consistency & error reduction:** Because answers are grounded in the catalog/FAQ data (not memory), pricing/stock answers should be more consistent than a busy human admin under pressure — this is a reasoning-based claim, not something you need a citation for.
- **Lead retention:** Faster responses likely reduce the number of customers who give up waiting and buy elsewhere — but I'd avoid quoting a specific "% of customers who churn after N minutes" type statistic unless you can point to a specific, verifiable source for it; if you don't have one, describe this qualitatively instead.
- **Cost:** If you want to compare against the cost of hiring additional admin staff, use real, locally-sourced wage figures (e.g., regional minimum wage data from BPS/local government sources) rather than estimated numbers, and cite where the figure came from.

---

## 11. Risks & Limitations (to mention in the presentation)

- The prototype uses mock data; real deployment requires integration with the seller's actual inventory system (which may update frequently).
- A 3-day MVP cannot fully validate guardrails against all adversarial inputs — this should be framed as "initial guardrails demonstrated, further red-teaming recommended before production."
- Real WhatsApp Business API integration involves Meta's approval process and costs that are out of scope for this prototype, but should be mentioned as a "next step."

---

## 12. Future Enhancements (Optional)

- Real WhatsApp Business API integration.
- Connection to live inventory/order management systems.
- Order placement (not just tracking) within the chat.
- Analytics dashboard summarizing common inquiry types over time.
- Fine-tuning persona/tone based on real conversation logs.