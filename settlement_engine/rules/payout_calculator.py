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
        opening_balance = merchant.carried_balance

        gross_captured = sum((t.captured_amount for t in eligible_captures), Decimal("0.00"))
        total_mdr = sum((t.mdr_amount for t in eligible_captures), Decimal("0.00"))
        total_gst = sum((t.gst_amount for t in eligible_captures), Decimal("0.00"))
        net_captures = gross_captured - total_mdr - total_gst

        total_refunds = sum((r.amount for r in eligible_refunds), Decimal("0.00"))

        total_chargeback_debits = sum((c.total_debit for c in eligible_chargebacks), Decimal("0.00"))
        total_representment_credits = sum((rep.credit_amount for rep in eligible_representments), Decimal("0.00"))

        reserve_withheld, new_reserves = ReserveEngine.calculate_reserve_deduction(
            merchant=merchant,
            eligible_captured_net=net_captures,
            settlement_date=settlement_date,
            calendar=calendar,
            batch_seq=batch_seq
        )

        pre_release_balance = (
            opening_balance
            + net_captures
            - total_refunds
            - total_chargeback_debits
            + total_representment_credits
            - reserve_withheld
        )

        is_negative = pre_release_balance < Decimal("0.00")
        reserve_released, released_entries = ReserveEngine.get_eligible_releases(
            merchant=merchant,
            as_of_date=settlement_date,
            active_reserves=active_reserves,
            is_merchant_negative=is_negative
        )

        calculated_settlement = pre_release_balance + reserve_released

        actual_payout = Decimal("0.00")
        closing_balance = Decimal("0.00")
        payout_status = "SETTLED"
        aging_applied = False
        note = ""

        if calculated_settlement < Decimal("0.00"):
            actual_payout = Decimal("0.00")
            closing_balance = calculated_settlement
            payout_status = "NEGATIVE_CARRIED_FORWARD"
            note = f"Deficit carried forward: Rs {abs(closing_balance)}. Settle Rs 0."
            merchant.pending_since_date = None

        elif calculated_settlement == Decimal("0.00"):
            actual_payout = Decimal("0.00")
            closing_balance = Decimal("0.00")
            payout_status = "ZERO_BALANCE"
            note = "Zero balance for current cycle."

        elif calculated_settlement < MINIMUM_PAYOUT:
            if merchant.pending_since_date is None:
                merchant.pending_since_date = settlement_date

            days_pending = (settlement_date - merchant.pending_since_date).days

            if days_pending >= AGING_THRESHOLD_DAYS:
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
            actual_payout = calculated_settlement
            closing_balance = Decimal("0.00")
            payout_status = "SETTLED"
            note = f"Normal disbursement of Rs {actual_payout}."
            merchant.last_payout_date = settlement_date
            merchant.pending_since_date = None

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
