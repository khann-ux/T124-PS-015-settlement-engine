"""
Test Suite for BR-07 (Rolling Reserves) and BR-08 Reserve Holdback Restrictions.
"""

import pytest
from datetime import date, timedelta
from decimal import Decimal
from settlement_engine.models.settlement import ReserveEntry
from settlement_engine.rules.reserve_engine import ReserveEngine


class TestBR07RollingReserve:

    def test_reserve_withholding_by_risk_tier(self, low_risk_merchant, medium_risk_merchant, high_risk_merchant, calendar):
        settlement_date = date(2026, 9, 10)
        net_captured = Decimal("100000.00")  # 1 Lakh net volume

        # LOW risk: 0% reserve
        amt_low, entries_low = ReserveEngine.calculate_reserve_deduction(
            low_risk_merchant, net_captured, settlement_date, calendar, 1
        )
        assert amt_low == Decimal("0.00")
        assert len(entries_low) == 0

        # MEDIUM risk: 5% held for 45 days
        amt_med, entries_med = ReserveEngine.calculate_reserve_deduction(
            medium_risk_merchant, net_captured, settlement_date, calendar, 1
        )
        assert amt_med == Decimal("5000.00")
        assert len(entries_med) == 1
        assert entries_med[0].hold_days == 45
        assert entries_med[0].release_due_date >= settlement_date + timedelta(days=46)

        # HIGH risk: 10% held for 90 days
        amt_high, entries_high = ReserveEngine.calculate_reserve_deduction(
            high_risk_merchant, net_captured, settlement_date, calendar, 1
        )
        assert amt_high == Decimal("10000.00")
        assert len(entries_high) == 1
        assert entries_high[0].hold_days == 90
        assert entries_high[0].release_due_date >= settlement_date + timedelta(days=91)

    def test_negative_balance_freezes_reserve_release(self, high_risk_merchant):
        # Matured reserve entry ready for release
        matured_entry = ReserveEntry(
            reserve_id="RES-001",
            merchant_id=high_risk_merchant.merchant_id,
            originated_date=date(2026, 6, 1),
            amount=Decimal("10000.00"),
            hold_days=90,
            release_due_date=date(2026, 9, 1),
            is_released=False,
        )

        as_of = date(2026, 9, 10)

        # Scenario A: Merchant is in negative balance -> release is FROZEN
        released_amt, released_entries = ReserveEngine.get_eligible_releases(
            merchant=high_risk_merchant,
            as_of_date=as_of,
            active_reserves=[matured_entry],
            is_merchant_negative=True
        )
        assert released_amt == Decimal("0.00")
        assert len(released_entries) == 0
        assert matured_entry.is_released is False

        # Scenario B: Merchant clears negative balance -> reserve is released
        released_amt_clear, released_entries_clear = ReserveEngine.get_eligible_releases(
            merchant=high_risk_merchant,
            as_of_date=as_of,
            active_reserves=[matured_entry],
            is_merchant_negative=False
        )
        assert released_amt_clear == Decimal("10000.00")
        assert len(released_entries_clear) == 1
        assert matured_entry.is_released is True
