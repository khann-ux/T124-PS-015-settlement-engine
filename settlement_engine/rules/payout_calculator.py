"""
Daily Payout and Netting Calculator Engine.
Complies with BR-04, BR-05, BR-06, BR-07, BR-08, and BR-10.

Cycle Ordering (BR-10):
1. Eligible Captures: Gross Captured - (MDR + GST) = Net Captures
2. Net Refunds: - Total Refunds
3. Net Chargebacks: - Chargeback Debits + Won Representment Credits
4. Rolling Reserve Withholding: - Reserve Withheld on Net Captures
5. Negative Balance Check: If balance < 0, freeze reserve releases, settle Rs 0, carry negative forward
6. Reserve Release: + Matured Reserves (only if merchant balance is non-negative)
7. Minimum Payout Check:
   - If balance >= Rs 100: Settle in full.
   - If 0 < balance < Rs 100:
     - Check 30-day aging: If pending for >= 30 days, disburse pending balance in full.
     - Otherwise: Carry forward to next cycle and disburse Rs 0.
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import List, Tuple
from settlement_engine.models.merchant import Merchant
from settlement_engine.models.transaction import Transaction
from settlement_engine.models.settlement import PayoutRecord, ReserveEntry
from settlement_engine.models.holiday import CalendarService
from settlement_engine.rules.refund_engine import QueuedRefund
from settlement_engine.rules.chargeback_engine import QueuedChargeback, QueuedRepresentmentCredit
from settlement_engine.rules.reserve_engine import ReserveEngine

MINIMUM_PAYOUT = Decimal("100.00")
AGING_THRESHOLD_DAYS = 30


class PayoutCalculator:
    @staticmethod
    def compute_daily_merchant_payout(
        merchant: Merchant,
        settlement_date: date,
        eligible_captures: List[Transaction],
        eligible_refunds: List[QueuedRefund],
        eligible_chargebacks: List[QueuedChargeback],
        eligible_representments: List[QueuedRepresentmentCredit],
        active_reserves: List[ReserveEntry],
        calendar: CalendarService,
        batch_seq: int = 1
    ) -> Tuple[PayoutRecord, List[ReserveEntry]]:
        """
        Executes the exact daily settlement waterfall for a single merchant.
        Returns (PayoutRecord, newly_created_reserves).
        """
        opening_balance = merchant.carried_balance

        # 1. Captures aggregation
        gross_captured = sum((t.captured_amount for t in eligible_captures), Decimal("0.00"))
        total_mdr = sum((t.mdr_amount for t in eligible_captures), Decimal("0.00"))
        total_gst = sum((t.gst_amount for t in eligible_captures), Decimal("0.00"))
        net_captures = gross_captured - total_mdr - total_gst

        # 2. Refunds aggregation
        total_refunds = sum((r.amount for r in eligible_refunds), Decimal("0.00"))

        # 3. Chargebacks & Representments aggregation
        total_chargeback_debits = sum((c.total_debit for c in eligible_chargebacks), Decimal("0.00"))
        total_representment_credits = sum((rep.credit_amount for rep in eligible_representments), Decimal("0.00"))

        # 4. Reserve Withholding on positive net captures
        reserve_withheld, new_reserves = ReserveEngine.calculate_reserve_deduction(
            merchant=merchant,
            eligible_captured_net=net_captures,
            settlement_date=settlement_date,
            calendar=calendar,
            batch_seq=batch_seq
        )

        # 5. Pre-release balance
        pre_release_balance = (
            opening_balance
            + net_captures
            - total_refunds
            - total_chargeback_debits
            + total_representment_credits
            - reserve_withheld
        )

        # 6. Reserve Release (BR-08: Negative balance blocks release)
        is_negative = pre_release_balance < Decimal("0.00")
        reserve_released, released_entries = ReserveEngine.get_eligible_releases(
            merchant=merchant,
            as_of_date=settlement_date,
            active_reserves=active_reserves,
            is_merchant_negative=is_negative
        )

        calculated_settlement = pre_release_balance + reserve_released

        # 7. Waterfall Settlement & Aging Evaluation
        actual_payout = Decimal("0.00")
        closing_balance = Decimal("0.00")
        payout_status = "SETTLED"
        aging_applied = False
        note = ""

        if calculated_settlement < Decimal("0.00"):
            # BR-08: Negative balance carry-forward
            actual_payout = Decimal("0.00")
            closing_balance = calculated_settlement
            payout_status = "NEGATIVE_CARRIED_FORWARD"
            note = f"Deficit carried forward: Rs {abs(closing_balance)}. Settle Rs 0."
            # Reset pending timer when in deficit
            merchant.pending_since_date = None

        elif calculated_settlement == Decimal("0.00"):
            actual_payout = Decimal("0.00")
            closing_balance = Decimal("0.00")
            payout_status = "ZERO_BALANCE"
            note = "Zero balance for current cycle."

        elif calculated_settlement < MINIMUM_PAYOUT:
            # Below minimum payout (Rs 100)
            if merchant.pending_since_date is None:
                merchant.pending_since_date = settlement_date

            days_pending = (settlement_date - merchant.pending_since_date).days

            if days_pending >= AGING_THRESHOLD_DAYS:
                # BR-08: 30-day aging override -> disburse regardless of minimum
                actual_payout = calculated_settlement
                closing_balance = Decimal("0.00")
                payout_status = "SETTLED_AGING_OVERRIDE"
                aging_applied = True
                note = f"Disbursed under 30-day aging rule (pending for {days_pending} days)."
                merchant.last_payout_date = settlement_date
                merchant.pending_since_date = None
            else:
                actual_payout = Decimal("0.00")
                closing_balance = calculated_settlement
                payout_status = "CARRIED_BELOW_MINIMUM"
                note = f"Amount (Rs {calculated_settlement}) below Rs 100 minimum. Carried forward (Day {days_pending}/30)."

        else:
            # Normal settlement (>= Rs 100)
            actual_payout = calculated_settlement
            closing_balance = Decimal("0.00")
            payout_status = "SETTLED"
            note = f"Normal disbursement of Rs {actual_payout}."
            merchant.last_payout_date = settlement_date
            merchant.pending_since_date = None

        # Update merchant carried balance
        merchant.carried_balance = closing_balance

        payout_record = PayoutRecord(
            merchant_id=merchant.merchant_id,
            settlement_date=settlement_date,
            gross_captured=gross_captured,
            total_mdr=total_mdr,
            total_gst=total_gst,
            total_refunds=total_refunds,
            total_chargeback_debits=total_chargeback_debits,
            total_representment_credits=total_representment_credits,
            reserve_withheld=reserve_withheld,
            reserve_released=reserve_released,
            opening_balance=opening_balance,
            calculated_settlement=calculated_settlement,
            actual_payout=actual_payout,
            closing_balance=closing_balance,
            payout_status=payout_status,
            aging_override_applied=aging_applied,
            note=note,
        )

        return payout_record, new_reserves
