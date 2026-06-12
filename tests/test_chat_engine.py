"""
tests/test_chat_engine.py
=========================
Happy-path and standard FR tests for the chat engine.

Covers: FR-01, FR-02, FR-03, FR-04, FR-05, FR-06

Run with:
    pytest tests/test_chat_engine.py -v
"""

# TODO (Story 1.5 / Sprint 2): implement tests
#
# Test structure (one test function per acceptance criterion):
#
# FR-01 — Product Inquiry
#   test_product_found_in_stock()
#       Input:  "Is the men's linen shirt M white still available?"
#       Assert: response contains "185000" and "12" (price + stock from catalog row P002)
#       Assert: response does NOT contain any product name not in catalog
#
#   test_product_not_found_asks_clarification()
#       Input:  "Do you have a red shirt?"
#       Assert: response asks for clarification (no product named "red" in catalog)
#
# FR-02 — FAQ
#   test_faq_shipping_today()
#       Input:  "If I order today, when will it arrive?"
#       Assert: response contains "02:00 PM" and "JNE" (from faq row F006)
#
#   test_faq_payment_methods()
#       Input:  "What payment methods do you accept?"
#       Assert: response contains "GoPay" and "transfer" (from faq row F003)
#
# FR-03 — Order Tracking
#   test_order_tracking_found()
#       Input:  "My tracking number is RESI001"
#       Assert: response contains "In Transit" (exact status from tracking CSV)
#
#   test_order_tracking_not_found()
#       Input:  "Check tracking number RESI999"
#       Assert: response contains "not found" (not-found message from prompt)
#
# FR-04 — Cross-sell
#   test_crosssell_on_out_of_stock()
#       Input:  "Is the men's linen shirt L white still available?"  (P003 → stock=0)
#       Assert: response acknowledges out of stock
#       Assert: response suggests an in-stock linen shirt variant (P001 or P002 or P004)
#
# FR-05 — Escalation
#   test_escalation_on_complaint()
#       Input:  "My item is broken, I am very disappointed"
#       Assert: result["escalated"] == True
#       Assert: response contains handoff language ("admin" or "connect")
#
# FR-06 — Multi-turn context
#   test_multiterm_followup()
#       Turn 1: "How much is the men's linen shirt M white?"
#       Turn 2: "Are there other colors?"
#       Assert: turn 2 response refers to linen shirt variants (not an unrelated product)
