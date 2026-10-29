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
        if eligible_captured_net <= Decimal("0.00") or merchant.reserve_percentage == Decimal("0.00"):
            return Decimal("0.00"), []

        reserve_amount = quantize_amount(eligible_captured_net * merchant.reserve_percentage)
        hold_days = merchant.reserve_holding_days

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
        if is_merchant_negative:
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
