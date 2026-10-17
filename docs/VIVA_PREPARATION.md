# Placement Viva Cheatsheet & Technical Q&A Guide
## Problem Statement: PS-015 · Payment Aggregator Merchant Settlement Engine

This cheatsheet equips you with deep conceptual answers, mathematical proofs, and code locations to answer questions from placement evaluators with confidence.

---

### Key Questions You MUST Prepare For

#### Q1: "Why is MDR NOT refunded to merchants when a customer requests a refund?"
**Your Answer**:
> "Sir/Ma'am, in payment systems, MDR is composed of three primary parts: **Interchange** (paid to the card-issuing bank), **Scheme/Network Fees** (paid to Visa/Mastercard/NPCI), and the **Aggregator's Margin**.  
> When a customer initiates a refund, the card networks and issuing banks **do not reverse the interchange fee** charged during the original transaction. Furthermore, the aggregator incurs additional compute, gateway bandwidth, and fraud screening costs to process the refund event itself.  
> If the aggregator were to refund the MDR, the aggregator would suffer a direct operational loss on every refund. Hence, under standard BFSI practices and RBI aggregator norms, the merchant absorbs the MDR and GST originally paid on the transaction."

---

#### Q2: "How does your rolling reserve release timing work, and what happens if the release date falls on a bank holiday or weekend?"
**Your Answer**:
> "Under **BR-07**, rolling reserves protect the aggregator from delayed chargebacks:
> - **HIGH risk merchants**: 10% held for 90 days.
> - **MEDIUM risk merchants**: 5% held for 45 days.
> - **LOW risk merchants**: Nil (0%).
> 
> The release target date is calculated as $\text{Settlement Date} + \text{Hold Days} + 1\text{ Day}$.  
> If this calculated date falls on a Saturday, Sunday, or a declared bank holiday in our `CalendarService`, the engine rolls the release forward to the immediate next active business day using `calendar.roll_to_business_day()`. This ensures disbursements align strictly with RBI clearing windows (NEFT/RTGS)."

---

#### Q3: "What happens if a chargeback creates a negative balance for a merchant? Does the merchant still get their rolling reserve released?"
**Your Answer**:
> "No, absolutely not. Under **BR-08**, we enforce a strict credit protection rule:
> 1. If nettings (refunds + chargeback debits) exceed the merchant's positive payout for the day, the merchant enters a **negative carried balance**, and the engine disburses ₹0.00.
> 2. Per **BR-08**, **a negative balance must be cleared before any reserve release can occur**.
> 3. Even if a prior reserve entry has matured, the engine freezes the release until the merchant's operational balance returns to non-negative equity through subsequent captured volume. This prevents defaulting merchants from taking money out while owing a deficit to the aggregator."

---

#### Q4: "Explain the cut-off rule at 23:00:00."
**Your Answer**:
> "The rule states: 'Captures after 23:00 count as next day'.  
> In our `calendar_service.py`, we implement:
> ```python
> if capture_timestamp.time() > time(23, 0, 0):
>     effective_date = capture_date + timedelta(days=1)
> else:
>     effective_date = capture_date
> ```
> Therefore:
> - A capture at **23:00:00 exactly** belongs to Day $T$.
> - A capture at **23:00:01** belongs to Day $T+1$.
> 
> We have an automated test specifically validating this boundary in `test_all_explicit_edge_cases.py::test_edge_case_2_cutoff_boundary`."

---

#### Q5: "How does the dynamic risk grading work, and how does a merchant recover?"
**Your Answer**:
> "Under **BR-09**, the engine continuously analyzes a trailing 30-day window:
> $$\text{Chargeback Ratio} = \frac{\text{Count of Chargebacks in trailing 30 days}}{\text{Count of Captures in trailing 30 days}}$$
> - If this ratio **strictly exceeds 1.00%** (> 0.0100), the merchant's risk grade worsens by one tier the next day (e.g. LOW $\to$ MEDIUM, or MEDIUM $\to$ HIGH). Note that exactly 1.00% does NOT trigger a downgrade.
> - To recover, the merchant must maintain **60 consecutive clean calendar days** with zero chargebacks. Once 60 clean days are logged, the risk grade recovers by one tier."

---

#### Q6: "How do your monthly invoices handle GST and Input Tax Credit (ITC)?"
**Your Answer**:
> "Under **BR-10**:
> - For **GST-registered merchants** (with a valid GSTIN): The invoice clearly itemizes the MDR and 18% GST, marks `itc_eligible = True`, and prints the statutory note referencing Section 16(1) of the CGST Act for B2B input tax credit.
> - For **Unregistered merchants**: The invoice is generated inclusive of 18% GST with `itc_eligible = False`, omitting the ITC claim line and providing a B2C unregistered supply disclaimer."

---

### How to Modify Code Live in the Viva

If the evaluator asks you to change a rule live, here is where each rule is located:

1. **Change UPI MDR Rate or Slab**:
   - File: `settlement_engine/rules/mdr_calculator.py`
   - Function: `calculate_standard_mdr()`
   - Variables: `UPI_SLAB_LIMIT = Decimal("2000.00")`, rate `Decimal("0.003")`.

2. **Change Cut-Off Time from 23:00 to 22:00**:
   - File: `settlement_engine/rules/calendar_service.py`
   - Variable: `CUTOFF_TIME = time(22, 0, 0)`.

3. **Change Chargeback Fee from ₹250 to ₹300**:
   - File: `settlement_engine/rules/chargeback_engine.py`
   - Variable: `CHARGEBACK_FEE = Decimal("300.00")`.

4. **Change Minimum Payout from ₹100 to ₹500**:
   - File: `settlement_engine/rules/payout_calculator.py`
   - Variable: `MINIMUM_PAYOUT = Decimal("500.00")`.

5. **Change Rolling Reserve Percentage**:
   - File: `settlement_engine/models/merchant.py`
   - Property: `reserve_percentage` and `reserve_holding_days`.

---

### Demonstration Commands for Evaluation

1. **Run Full Test Suite (42 tests)**:
   ```bash
   python -m pytest -v
   ```

2. **Run Mandatory 8 Edge Cases**:
   ```bash
   python -m pytest -v tests/test_all_explicit_edge_cases.py
   ```

3. **Run Master CLI Simulation**:
   ```bash
   python run.py
   ```
