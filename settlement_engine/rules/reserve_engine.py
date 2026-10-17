"""
Rolling Reserve (Holdback) and Release Engine.
Complies with BR-07 and BR-08.

BR-07:
- HIGH risk: 10% of settlement held for 90 days.
- MEDIUM risk: 5% held for 45 days.
- LOW risk: Nil (0%).
- Reserve released on the business day AFTER the hold period:
  Release Target = settlement_date + hold_days + 1 day.
  If this date falls on a holiday or weekend, it rolls to the NEXT business day.

BR-08:
- The negative balance must be cleared before ANY reserve release!
  If the merchant has an uncleared negative balance from prior cycles or from today's nettings,
  matured reserves are held in escrow and cannot be released until the merchant returns to non-negative equity.
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import List, Tuple
from settlement_engine.models.merchant import Merchant, RiskGrade
from settlement_engine.models.settlement import ReserveEntry
from settlement_engine.models.holiday import CalendarService
from settlement_engine.rules.mdr_calculator import quantize_amount


class ReserveEngine:
    @staticmethod
    def calculate_reserve_deduction(
        merchant: Merchant,
        eligible_captured_net: Decimal,
        settlement_date: date,
        calendar: CalendarService,
        batch_seq: int
    ) -> Tuple[Decimal, List[ReserveEntry]]:
        """
        Deducts rolling reserve on net captured volume according to risk grade.
        Returns (deduction_amount, new_reserve_entries).
        """
        if eligible_captured_net <= Decimal("0.00") or merchant.reserve_percentage == Decimal("0.00"):
            return Decimal("0.00"), []

        reserve_amount = quantize_amount(eligible_captured_net * merchant.reserve_percentage)
        hold_days = merchant.reserve_holding_days

        # BR-07: released on the business day after the hold period
        unadjusted_target = settlement_date + timedelta(days=hold_days + 1)
        effective_release_date = calendar.roll_to_business_day(unadjusted_target)

        entry = ReserveEntry(
            reserve_id=f"RES-{merchant.merchant_id}-{settlement_date.strftime('%Y%m%d')}-{batch_seq}",
            merchant_id=merchant.merchant_id,
            originated_date=settlement_date,
            amount=reserve_amount,
            hold_days=hold_days,
            release_due_date=effective_release_date,
            is_released=False,
            released_date=None,
        )

        return reserve_amount, [entry]

    @staticmethod
    def get_eligible_releases(
        merchant: Merchant,
        as_of_date: date,
        active_reserves: List[ReserveEntry],
        is_merchant_negative: bool
    ) -> Tuple[Decimal, List[ReserveEntry]]:
        """
        Determines matured reserves due for release on or before as_of_date.
        If is_merchant_negative is True (BR-08), matured reserves are FROZEN and not released.
        """
        if is_merchant_negative:
            # Negative balance blocks reserve releases
            return Decimal("0.00"), []

        releasable_entries: List[ReserveEntry] = []
        total_release = Decimal("0.00")

        for entry in active_reserves:
            if not entry.is_released and entry.release_due_date <= as_of_date:
                total_release += entry.amount
                entry.is_released = True
                entry.released_date = as_of_date
                releasable_entries.append(entry)

        return total_release, releasable_entries
