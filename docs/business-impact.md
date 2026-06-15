# Business Impact Explanation
## Benny Bot: AI-Powered Customer Support for SMEs

**Purpose**: Business Impact Explanation for WIZ.AI Builder Challenge  
**Author**: Ivant Samuel Silaban  
**Date**: June 2026  

---
## 1. Overview
Benny Bot is a prototype AI customer service assistant built for small and medium fashion retailers. It is designed to automate the most common and repetitive tier of WhatsApp customer inquiries such as product questions, shipping FAQs, order tracking, and cross-selling, while cleanly escalating complaints and blocking out-of-scope or adversarial inputs.  
This document presents the business case for automating this layer of customer support, grounded in data from the prototype's conversation logs. All figures are derived from demo/test sessions and should be treated as directional estimates, not production-validated metrics. A real deployment with live traffic would be required to confirm these numbers.

---
## 2. The Problems
A typical SME seller managing WhatsApp customer service faces three compounding pressures:  
- **Volume:** A large share of daily messages are repetitive, the same questions about stock, price, shipping, and order status asked by different customers.
- **Availability:** Human admins work business hours. Customers who message at night or on weekends either wait or buy elsewhere.
- **Consistency:** Under time pressure, a human admin may give inconsistent or inaccurate answers about pricing or stock, which erodes customer trust.  

Benny Bot addresses all three: it handles repetitive inquiries instantly, operates 24/7, and grounds every factual answer in the product catalog and FAQ data rather than relying on human memory.

---

## 3. Prototype Test Results
### 3.1 Session Overview
As I shown on Demo, the conversation log covers 3 sessions and 32 total messages, generated during demo testing on June 15, 2026.  
### 3.2 Intent Distribution (All Session)
 
| Detected Intent | Message Count | % of Total |
|---|---|---|
| PRODUCT_INQUIRY | 12 | 35.3% |
| CLARIFICATION | 8 | 23.5% |
| ORDER_TRACKING | 4 | 11.8% |
| ESCALATION | 4 | 11.8% |
| OUT_OF_SCOPE | 4 | 11.8% |
| FAQ | 2 | 5.9% |
| **Total** | **34** | **100%** |

### 3.3 Automation Rate  
Of 34 total turns, 4 were escalated to a human agent (all correctly identified complaints or deeply negative-sentiment messages). The remaining 30 turns were handled by the bot without human intervention.
 
Observed automation rate (demo data): 30 / 34 = 88.2%
 
This figure should be interpreted carefully:
- It is based on scripted test cases, not organic customer traffic.
- The escalation rate (11.8%) may be higher or lower in production depending on the real complaint volume for a given business.
- A realistic production automation rate for a business with similar inquiry patterns is likely somewhere in the 70–85% range, once messier real-world inputs are accounted for.
As a directional estimate: if a real store receives ~100 messages per day with a similar intent mix, approximately 88 of those would not require manual admin typing, based on the demo session automation rate. This should be validated against live traffic before being used for any business decision.

### 3.4 Guardrail Effectiveness
 
All 4 adversarial inputs in the demo were handled correctly:
 
| Input Type | Bot Behavior | Correct? |
|---|---|---|
| Prompt injection ("Ignore your previous instructions...") | Stayed in persona, declined | ✅ |
| Off-topic question (president of Indonesia) | Politely redirected to store scope | ✅ |
| Discount pressure (20% off, loyal customer claim) | Held the listed price, no invented discount | ✅ |
| Invalid tracking number (RESI999) | Honestly reported not found, asked to verify | ✅ |
 
No hallucinated products, prices, discounts, or policies were observed in the demo session.

### 3.5 Honest Limitation Observed
In Session 1, the query "kaos item ukran L ada ga?" (Indonesian slang with a typo, meaning "do you have a black t-shirt size L?") returned a response saying the product could not be found. The same query in Session 3 correctly returned the Oversized T-Shirt L / Black at Rp 120,000. This inconsistency suggests the intent parsing and retrieval pipeline is not fully deterministic across sessions, likely due to embedding similarity score variation. This is expected in a 3-day prototype and should be addressed before production deployment through more robust retrieval tuning.

---

## 4. Estimated Business Value
 
The following estimates are based on the demo data and reasonable assumptions. Each assumption is stated explicitly so an SME owner can substitute their own numbers. 

### 4.1 Time Savings
 
**Assumption:** Each substantive inquiry (product, FAQ, tracking) takes a human admin an average of 2–3 minutes to read, look up, and reply to manually.
 
From the demo data, 18 out of 34 turns were substantive inquiries (PRODUCT_INQUIRY + FAQ + ORDER_TRACKING) that were handled automatically (12 product + 2 FAQ + 4 tracking). Applying the 2–3 minute estimate:
 
- Low estimate: 18 × 2 min = **36 minutes saved** per equivalent real session
- High estimate: 18 × 3 min = **54 minutes saved** per equivalent real session
For an SME receiving 100 similar messages per day with a comparable intent distribution, the estimated daily time saving would be in the range of **3–5 hours of admin work**, based on the demo automation rate of 88.2%. This is an extrapolation from demo data, it should be validated against real traffic logs after deployment. 

### 4.2 Availability
 
Benny Bot can respond to customer inquiries at any hour, including outside business hours and on weekends. This is a qualitative benefit that does not require a specific statistic to make the case: a customer who messages at 10pm and receives an instant, accurate response about stock and shipping is more likely to complete a purchase than one who is told to wait until morning.


### 4.3 Consistency and Error Reduction
 
Because Benny Bot answers are grounded exclusively in the product catalog and FAQ data, pricing and stock answers are consistent regardless of time of day, admin workload, or how many customers are messaging simultaneously. A human admin under pressure may misremember a price, give an incorrect stock count, or accidentally promise a discount that doesn't exist. The bot cannot do any of these things, it either retrieves the correct data or says it doesn't know.

### 4.4 Escalation Quality
 
The bot correctly identified and escalated all 4 complaint messages in the demo (including one in Indonesian) with an empathetic acknowledgment and a clear handoff message. This matters because a complaint that is ignored or mishandled by a bot would be worse than no bot at all. Transparent escalation preserves customer trust. 
### 4.5 Cost Comparison
 
A precise cost comparison against human admin staffing is intentionally omitted here, as hourly wage figures vary significantly by region and role. If an SME owner wants to estimate this:
 
1. Take the estimated hours saved per day (Section 4.1).
2. Multiply by the admin's effective hourly cost (salary + overhead).
3. Compare against the actual API usage cost of running the bot for the same volume.
For reference, regional wage data for Indonesia can be sourced from BPS (Badan Pusat Statistik) or the relevant provincial minimum wage regulation. API costs depend on the provider and model used, current pricing should be checked directly with the provider, as it changes frequently. 

---

## 5. What This Prototype Demonstrates
 
| Capability | Status |
|---|---|
| Product inquiry with catalog grounding | ✅ Working |
| Cross-sell on out-of-stock variants | ✅ Working |
| FAQ retrieval (shipping, payment, hours) | ✅ Working |
| Order tracking (valid and invalid numbers) | ✅ Working |
| Escalation on complaints and negative sentiment | ✅ Working (EN + ID) |
| Guardrails: prompt injection, off-topic, discount pressure | ✅ Working |
| Multi-turn context within a session | ✅ Working |
| Conversation logging with intent labels | ✅ Working |
| Retrieval source auditability | ✅ Working |

---
 
## 6. Risks and Honest Limitations
 
The following limitations should be disclosed to any evaluator or prospective adopter:
 
- **Mock data only.** The prototype uses a static product catalog, FAQ list, and mock tracking numbers. Real deployment requires integration with a live inventory system that updates when stock changes.
- **Retrieval consistency is not guaranteed.** As observed in Session 1 vs Session 3, the same query can produce different retrieval results. This is a known characteristic of embedding-based retrieval at small scale and requires tuning before production use.
- **Guardrails are initial, not exhaustive.** The guardrails demonstrated cover the most common attack patterns (prompt injection, discount pressure, off-topic), but have not been red-teamed at scale. Further adversarial testing is recommended before production deployment.
- **No real WhatsApp integration.** The prototype runs as a web UI. Real WhatsApp Business API integration involves Meta's approval process and additional infrastructure costs that are out of scope for this prototype.
- **Language coverage.** The bot handles English and basic Indonesian inputs. Broader Bahasa Indonesia coverage, regional dialects, or mixed-language (Jaksel-style) inputs would require additional testing and possibly fine-tuning. 

## 7. Recommended Next Steps

1. **Connect to a live inventory system** so stock levels and prices stay current without manual data refresh.
2. **Improve retrieval consistency** by evaluating chunking strategy, embedding model choice, and similarity score thresholds.
3. **Expand red-teaming** to cover a wider range of adversarial inputs before going to production.
4. **Add an analytics dashboard** summarizing intent trends over time to help the SME owner understand what customers ask most and where gaps exist.