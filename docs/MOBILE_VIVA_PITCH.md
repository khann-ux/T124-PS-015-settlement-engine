# 📱 PLACEMENT VIVA & INTERVIEW MASTER PITCH (MOBILE CHEATSHEET)
**Project**: T124-PS-015 · Payment Aggregator Merchant Settlement Engine  
**Domain**: BFSI — Payments & Merchant Settlement  
**Keep this open on your phone right before entering the viva!**

---

## ⚡ 1. THE 60-SECOND INTRO ("TELL ME ABOUT YOUR PROJECT")
*(Speak slowly, clearly, with confidence)*

"Sir/Ma'am, I have built **PS-015: Payment Aggregator Merchant Settlement Engine**.

In fintech, when consumers pay on e-commerce platforms using UPI, Cards, or Net Banking, aggregators like Razorpay or Cashfree cannot immediately transfer money to merchants. They must calculate **MDR and 18% GST**, follow **T+1 to T+3 business day settlement cycles**, hold back **rolling reserves for risky merchants**, net **refunds and chargebacks**, and generate audited payout files and statutory tax invoices.

I designed and engineered a production-grade, command-file-driven settlement engine in **Python 3.14**:
1. **Zero-Float Financial Precision**: Built entirely using `decimal.Decimal` with `ROUND_HALF_UP` banking quantization—zero floating-point numbers.
2. **Finite State Machine**: Strict transaction lifecycle validation (`AUTH` ➔ `CAPTURE` ➔ `REFUND` ➔ `CHARGEBACK` ➔ `REPRESENTMENT`) with 7-day auth expiry.
3. **Daily Settlement Waterfall**: An 8-step pipeline that manages risk-based rolling reserves (up to 10% for 90 days), holiday rollovers, deficit carry-forward, and dynamic risk downgrades.
4. **Tested to Perfection**: Verified by **42 automated unit & integration tests** covering all 8 mandatory edge cases and stretch goals like Marketplace splits and Instant settlements."

---

## 🧠 2. THE 4 BIG QUESTIONS EVALUATORS WILL ASK (WORD-FOR-WORD ANSWERS)

### Q1: "Why is MDR NOT refunded when a customer initiates a refund?"
⭐ **THE GOLDEN ANSWER**:
"In payment systems, MDR covers three components: **Interchange** paid to the customer's card-issuing bank, **Scheme Fees** paid to Visa/Mastercard/NPCI, and the **Aggregator's processing margin**.
When a refund is initiated, card networks **never refund the interchange fee**. On top of that, the aggregator incurs bandwidth, gateway, and fraud screening costs to process the refund transaction itself.
If the aggregator refunded the MDR, it would suffer a direct operational loss on every customer return. Therefore, standard BFSI practices and RBI guidelines mandate that the aggregator retains the original MDR."

---

### Q2: "How does holdback / rolling reserve release work, and what if the release falls on a holiday?"
⭐ **THE GOLDEN ANSWER**:
"Under **BR-07**:
- **HIGH-risk merchants**: 10% of each settlement is held for 90 days.
- **MEDIUM-risk merchants**: 5% is held for 45 days.
- **LOW-risk merchants**: Nil (0%).
The release date target is calculated as: `Settlement Date + Hold Days + 1 Day`.
If that date falls on a weekend or a declared bank holiday, my `CalendarService.roll_to_business_day()` rolls the release forward to the next working business day. This ensures disbursements align with active RBI clearing rails (NEFT/RTGS)."

---

### Q3: "What happens if a chargeback creates a negative balance? Does the merchant still receive matured reserves?"
⭐ **THE GOLDEN ANSWER**:
"No, sir. Under **BR-08**:
1. If nettings (refunds + chargeback debits) exceed today's settlement, the engine settles **₹0.00** and carries the negative deficit forward.
2. **A negative balance completely blocks reserve release**. Even if a 90-day reserve has matured, funds remain frozen in escrow until the merchant offsets their deficit through subsequent positive sales. This eliminates credit risk and prevents defaulting merchants from withdrawing reserve funds while in debt."

---

### Q4: "How does dynamic risk grading work, and how does a merchant recover?"
⭐ **THE GOLDEN ANSWER**:
"Under **BR-09**, the engine analyzes a trailing 30-day window:
$$\text{Chargeback Ratio} = \frac{\text{Count of Chargebacks in trailing 30 days}}{\text{Count of Captures in trailing 30 days}}$$
- If this ratio **strictly exceeds 1.00%** (> 0.0100), the merchant's risk tier worsens by one level the very next day (e.g., LOW ➔ MEDIUM, or MEDIUM ➔ HIGH). Note: exactly 1.00% does NOT trigger a downgrade.
- To recover, the merchant must maintain **60 consecutive clean calendar days** with zero chargebacks. After 60 clean days, their risk grade improves by one tier."

---

## 🎯 3. THE 8 MANDATORY EDGE CASES (CHEAT SHEET)

1. **UPI ₹2,000 vs ₹2,000.01**:
   - Up to ₹2,000.00: 0% MDR (₹0 MDR, ₹0 GST).
   - ₹2,000.01: 0.3% MDR = ₹6.00 MDR, ₹1.08 GST.
2. **Cut-off at 23:00:00 exactly vs 23:00:01**:
   - Exactly 23:00:00 counts as same day (Day T).
   - 23:00:01 counts as next day (Day T+1).
3. **Refund Day 180 vs Day 181**:
   - Day 180: Allowed.
   - Day 181: Rejected (`REFUND_WINDOW_EXPIRED`).
4. **Capture Day 7 after AUTH**:
   - Day 7 (within $7 \times 86,400\text{ s}$): Valid.
   - After Day 7: Rejected with `AUTH_EXPIRED`.
5. **Chargeback larger than payout**:
   - Disburses ₹0.00, carries negative balance forward, freezes reserves.
6. **Reserve release on a holiday**:
   - Rolls forward to next working business day (e.g., Oct 2 Gandhi Jayanti rolls to Oct 5 Monday).
7. **Chargeback ratio exactly 1.00%**:
   - Exactly 1.00% does NOT downgrade; strictly > 1.00% downgrades.
8. **₹99.99 pending for 30 days**:
   - Days 1 to 29: Carried forward (< ₹100 minimum).
   - Day 30: 30-day aging override triggers and disburses ₹99.99 in full.

---

## 🛠️ 4. LIVE CODE MODIFICATION CHEATCODES
*(If evaluator asks: "Change this rule live in front of me")*

1. **Change UPI MDR Rate or Slab**:
   - Open: `settlement_engine/rules/mdr_calculator.py`
   - Line: `UPI_SLAB_LIMIT = Decimal("2000.00")`
2. **Change Cut-Off Time from 23:00 to 22:00**:
   - Open: `settlement_engine/rules/calendar_service.py`
   - Line: `CUTOFF_TIME = time(22, 0, 0)`
3. **Change Chargeback Fee from ₹250 to ₹300**:
   - Open: `settlement_engine/rules/chargeback_engine.py`
   - Line: `CHARGEBACK_FEE = Decimal("300.00")`
4. **Change Minimum Payout from ₹100 to ₹500**:
   - Open: `settlement_engine/rules/payout_calculator.py`
   - Line: `MINIMUM_PAYOUT = Decimal("500.00")`
5. **Change Rolling Reserve Percentages**:
   - Open: `settlement_engine/models/merchant.py`
   - Property: `reserve_percentage` (HIGH: 0.10, MEDIUM: 0.05)

---

## 🌟 5. BONUS STRETCH GOALS (MENTION AT THE END FOR EXTRA MARKS!)

"Additionally, I built two enterprise-grade stretch goals in `stretch_goals.py`:
1. **Marketplace Split Settlement**: Automatically splits customer order payments between marketplace platform commission and multiple vendors, absorbing aggregator fees.
2. **Instant Settlement Service (T+0)**: Enables on-demand same-day payouts for merchants at a 0.10% instant processing fee with daily risk caps."

---

## 🚀 6. QUICK COMMANDS (COPY & PASTE IN TERMINAL)
```bash
# Run All 42 Tests:
python -m pytest -v

# Run 8 Mandatory Edge Cases:
python -m pytest -v tests/test_all_explicit_edge_cases.py

# Run Full 45-Day Settlement Simulation:
python run.py
```
