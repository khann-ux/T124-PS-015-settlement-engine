import pytest
from datetime import datetime, date, timedelta
from settlement_engine.models.merchant import RiskGrade
from settlement_engine.rules.calendar_service import (
    get_effective_capture_date,
    compute_settlement_date,
)


class TestBR04SettlementCutoff:

    def test_low_risk_t_plus_1(self, calendar):
        cap_time = datetime(2026, 9, 7, 10, 0, 0)
        settle_date = compute_settlement_date(cap_time, RiskGrade.LOW, calendar)
        assert settle_date == date(2026, 9, 8)

    def test_medium_risk_t_plus_2(self, calendar):
        cap_time = datetime(2026, 9, 7, 10, 0, 0)
        settle_date = compute_settlement_date(cap_time, RiskGrade.MEDIUM, calendar)
        assert settle_date == date(2026, 9, 9)

    def test_high_risk_t_plus_3(self, calendar):
        cap_time = datetime(2026, 9, 7, 10, 0, 0)
        settle_date = compute_settlement_date(cap_time, RiskGrade.HIGH, calendar)
        assert settle_date == date(2026, 9, 10)

    def test_weekend_skipping(self, calendar):
        cap_time = datetime(2026, 9, 11, 15, 0, 0)
        settle_date = compute_settlement_date(cap_time, RiskGrade.LOW, calendar)
        assert settle_date == date(2026, 9, 14)

    def test_holiday_skipping(self, calendar):
        cap_time = datetime(2026, 10, 1, 14, 0, 0)
        settle_date = compute_settlement_date(cap_time, RiskGrade.LOW, calendar)
        assert settle_date == date(2026, 10, 5)

    def test_cutoff_on_friday_rolls_to_tuesday(self, calendar):
        cap_time = datetime(2026, 9, 11, 23, 15, 0)
        settle_date = compute_settlement_date(cap_time, RiskGrade.LOW, calendar)
        assert settle_date == date(2026, 9, 14)
