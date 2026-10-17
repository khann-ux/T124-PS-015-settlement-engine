"""
Test Suite for BR-04 (Settlement Cycles, 23:00 Cut-off, and Calendar Services).
"""

import pytest
from datetime import datetime, date, timedelta
from settlement_engine.models.merchant import RiskGrade
from settlement_engine.rules.calendar_service import (
    get_effective_capture_date,
    compute_settlement_date,
)


class TestBR04SettlementCutoff:

    def test_low_risk_t_plus_1(self, calendar):
        # Monday 10:00 AM -> Tuesday settlement
        cap_time = datetime(2026, 9, 7, 10, 0, 0)
        settle_date = compute_settlement_date(cap_time, RiskGrade.LOW, calendar)
        assert settle_date == date(2026, 9, 8)

    def test_medium_risk_t_plus_2(self, calendar):
        # Monday 10:00 AM -> Wednesday settlement
        cap_time = datetime(2026, 9, 7, 10, 0, 0)
        settle_date = compute_settlement_date(cap_time, RiskGrade.MEDIUM, calendar)
        assert settle_date == date(2026, 9, 9)

    def test_high_risk_t_plus_3(self, calendar):
        # Monday 10:00 AM -> Thursday settlement
        cap_time = datetime(2026, 9, 7, 10, 0, 0)
        settle_date = compute_settlement_date(cap_time, RiskGrade.HIGH, calendar)
        assert settle_date == date(2026, 9, 10)

    def test_weekend_skipping(self, calendar):
        # Friday capture (LOW risk T+1)
        # Saturday and Sunday are skipped, settles on Monday!
        cap_time = datetime(2026, 9, 11, 15, 0, 0)
        settle_date = compute_settlement_date(cap_time, RiskGrade.LOW, calendar)
        assert settle_date == date(2026, 9, 14)  # Monday

    def test_holiday_skipping(self, calendar):
        # Gandhi Jayanti is Friday 2026-10-02
        # Thursday 2026-10-01 capture (LOW risk T+1)
        # Friday 10-02 is a holiday, Sat/Sun are weekends -> rolls to Monday 2026-10-05!
        cap_time = datetime(2026, 10, 1, 14, 0, 0)
        settle_date = compute_settlement_date(cap_time, RiskGrade.LOW, calendar)
        assert settle_date == date(2026, 10, 5)

    def test_cutoff_on_friday_rolls_to_tuesday(self, calendar):
        # Friday after 23:00 (e.g. 23:15:00)
        # Effective date = Saturday 2026-09-12
        # Low risk T+1 business day from Saturday = Monday 2026-09-14
        cap_time = datetime(2026, 9, 11, 23, 15, 0)
        settle_date = compute_settlement_date(cap_time, RiskGrade.LOW, calendar)
        assert settle_date == date(2026, 9, 14)
