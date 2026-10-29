import pytest
from datetime import datetime, date, timedelta, time
from decimal import Decimal

from settlement_engine.models.merchant import Merchant, RiskGrade, MDRPlan, BankAccount
from settlement_engine.models.transaction import (
    Transaction,
    PaymentInstrument,
    EventType,
    TransactionState,
    LifecycleEvent,
)
from settlement_engine.models.holiday import CalendarService
from settlement_engine.models.settlement import ReserveEntry
from settlement_engine.rules.mdr_calculator import calculate_mdr_and_gst
from settlement_engine.rules.lifecycle_validator import LifecycleValidator, LifecycleValidationError
from settlement_engine.rules.calendar_service import get_effective_capture_date, compute_settlement_date
from settlement_engine.rules.refund_engine import RefundEngine
from settlement_engine.rules.chargeback_engine import (
    ChargebackEngine,
    QueuedChargeback,
    CHARGEBACK_FEE,
)
from settlement_engine.rules.reserve_engine import ReserveEngine
from settlement_engine.rules.payout_calculator import PayoutCalculator


class TestExplicitEdgeCases:

    def test_edge_case_1_upi_slabs(self, low_risk_merchant):
        mdr_2000, gst_2000 = calculate_mdr_and_gst(
            merchant=low_risk_merchant,
            instrument=PaymentInstrument.UPI,
            captured_amount=Decimal("2000.00")
        )
        assert mdr_2000 == Decimal("0.00"), "MDR on UPI <= 2000 must be 0.00"
        assert gst_2000 == Decimal("0.00"), "GST on 0 MDR must be 0.00"

        mdr_2001, gst_2001 = calculate_mdr_and_gst(
            merchant=low_risk_merchant,
            instrument=PaymentInstrument.UPI,
            captured_amount=Decimal("2000.01")
        )
        assert mdr_2001 == Decimal("6.00"), "MDR on UPI Rs 2000.01 must be Rs 6.00"
        assert gst_2001 == Decimal("1.08"), "GST on Rs 6.00 MDR must be Rs 1.08"

    def test_edge_case_2_cutoff_boundary(self, calendar):
        t_capture_exact = datetime(2026, 9, 7, 23, 0, 0)
        eff_date_exact = get_effective_capture_date(t_capture_exact)
        assert eff_date_exact == date(2026, 9, 7), "Capture at 23:00:00 exactly counts as same day"

        settlement_exact = compute_settlement_date(t_capture_exact, RiskGrade.LOW, calendar)
        assert settlement_exact == date(2026, 9, 8)

        t_capture_after = datetime(2026, 9, 7, 23, 0, 1)
        eff_date_after = get_effective_capture_date(t_capture_after)
        assert eff_date_after == date(2026, 9, 8), "Capture after 23:00 counts as next day"

        settlement_after = compute_settlement_date(t_capture_after, RiskGrade.LOW, calendar)
        assert settlement_after == date(2026, 9, 9)

    def test_edge_case_3_refund_180_vs_181(self, low_risk_merchant):
        cap_time = datetime(2026, 1, 1, 12, 0, 0)
        txn = Transaction(
            txn_id="TXN-REFUND-EDGE",
            merchant_id=low_risk_merchant.merchant_id,
            instrument=PaymentInstrument.CREDIT_CARD,
            authorized_amount=Decimal("5000.00"),
            auth_timestamp=cap_time - timedelta(hours=1),
            captured_amount=Decimal("5000.00"),
            capture_timestamp=cap_time,
            state=TransactionState.CAPTURED,
        )

        day_180_time = cap_time + timedelta(days=180)
        ev_180 = LifecycleEvent(
            event_id="EV-REF-180",
            txn_id=txn.txn_id,
            merchant_id=txn.merchant_id,
            event_type=EventType.REFUND,
            amount=Decimal("1000.00"),
            timestamp=day_180_time,
        )
        LifecycleValidator.validate_refund(txn, ev_180)

        day_181_time = cap_time + timedelta(days=181)
        ev_181 = LifecycleEvent(
            event_id="EV-REF-181",
            txn_id=txn.txn_id,
            merchant_id=txn.merchant_id,
            event_type=EventType.REFUND,
            amount=Decimal("1000.00"),
            timestamp=day_181_time,
        )
        with pytest.raises(LifecycleValidationError) as exc:
            LifecycleValidator.validate_refund(txn, ev_181)
        assert exc.value.code == "REFUND_WINDOW_EXPIRED"

    def test_edge_case_4_capture_day_7_expiry(self, low_risk_merchant):
        auth_time = datetime(2026, 9, 1, 10, 0, 0)
        txn = Transaction(
            txn_id="TXN-AUTH-EDGE",
            merchant_id=low_risk_merchant.merchant_id,
            instrument=PaymentInstrument.UPI,
            authorized_amount=Decimal("3000.00"),
            auth_timestamp=auth_time,
            state=TransactionState.AUTHORIZED,
        )

        cap_day_7_time = auth_time + timedelta(days=7)
        ev_valid_cap = LifecycleEvent(
            event_id="EV-CAP-D7",
            txn_id=txn.txn_id,
            merchant_id=txn.merchant_id,
            event_type=EventType.CAPTURE,
            amount=Decimal("3000.00"),
            timestamp=cap_day_7_time,
        )
        LifecycleValidator.validate_capture(txn, ev_valid_cap)

        cap_expired_time = auth_time + timedelta(days=7, seconds=1)
        ev_expired_cap = LifecycleEvent(
            event_id="EV-CAP-EXP",
            txn_id=txn.txn_id,
            merchant_id=txn.merchant_id,
            event_type=EventType.CAPTURE,
            amount=Decimal("3000.00"),
            timestamp=cap_expired_time,
        )
        with pytest.raises(LifecycleValidationError) as exc:
            LifecycleValidator.validate_capture(txn, ev_expired_cap)
        assert exc.value.code == "AUTH_EXPIRED"
        assert txn.state == TransactionState.EXPIRED

    def test_edge_case_5_negative_balance_carry_forward(self, low_risk_merchant, calendar):
        settlement_date = date(2026, 9, 10)
        cb = QueuedChargeback(
            chargeback_id="CB-001",
            txn_id="TXN-CB-001",
            merchant_id=low_risk_merchant.merchant_id,
            amount=Decimal("2500.00"),
            fee=Decimal("250.00"),
            timestamp=datetime(2026, 9, 10, 10, 0),
            effective_date=settlement_date,
        )
        payout_rec, _ = PayoutCalculator.compute_daily_merchant_payout(
            merchant=low_risk_merchant,
            settlement_date=settlement_date,
            eligible_captures=[],
            eligible_refunds=[],
            eligible_chargebacks=[cb],
            eligible_representments=[],
            active_reserves=[],
            calendar=calendar,
        )

        assert payout_rec.actual_payout == Decimal("0.00"), "Must disburse Rs 0 on negative balance"
        assert payout_rec.closing_balance == Decimal("-2750.00"), "Deficit must be carried forward"
        assert payout_rec.payout_status == "NEGATIVE_CARRIED_FORWARD"
        assert low_risk_merchant.carried_balance == Decimal("-2750.00")

    def test_edge_case_6_reserve_release_on_holiday(self, calendar):
        holiday_date = date(2026, 10, 2)
        assert not calendar.is_business_day(holiday_date), "Oct 2 must be recognized as holiday"

        effective_release = calendar.roll_to_business_day(holiday_date)
        assert effective_release == date(2026, 10, 5), "Holiday must roll forward to Monday Oct 5"

    def test_edge_case_7_chargeback_ratio_exactly_1_percent(self, low_risk_merchant):
        as_of = date(2026, 9, 20)
        captures = []
        for i in range(100):
            t = Transaction(
                txn_id=f"T-{i}",
                merchant_id=low_risk_merchant.merchant_id,
                instrument=PaymentInstrument.UPI,
                authorized_amount=Decimal("100.00"),
                auth_timestamp=datetime(2026, 9, 5, 10, 0),
                captured_amount=Decimal("100.00"),
                capture_timestamp=datetime(2026, 9, 5, 12, 0),
            )
            captures.append(t)

        cb_list = [
            QueuedChargeback(
                chargeback_id="CB-EXACT",
                txn_id="T-0",
                merchant_id=low_risk_merchant.merchant_id,
                amount=Decimal("100.00"),
                fee=CHARGEBACK_FEE,
                timestamp=datetime(2026, 9, 10, 10, 0),
                effective_date=date(2026, 9, 10),
            )
        ]

        ChargebackEngine.evaluate_risk_grade(
            merchant=low_risk_merchant,
            as_of_date=as_of,
            all_captures=captures,
            all_chargebacks=cb_list
        )
        assert low_risk_merchant.current_risk_grade == RiskGrade.LOW, "Exactly 1.00% should NOT downgrade risk"

        cb_list.append(
            QueuedChargeback(
                chargeback_id="CB-OVER",
                txn_id="T-1",
                merchant_id=low_risk_merchant.merchant_id,
                amount=Decimal("100.00"),
                fee=CHARGEBACK_FEE,
                timestamp=datetime(2026, 9, 12, 10, 0),
                effective_date=date(2026, 9, 12),
            )
        )
        ChargebackEngine.evaluate_risk_grade(
            merchant=low_risk_merchant,
            as_of_date=as_of,
            all_captures=captures,
            all_chargebacks=cb_list
        )
        assert low_risk_merchant.current_risk_grade == RiskGrade.MEDIUM, "Ratio > 1.00% must downgrade risk grade"

    def test_edge_case_8_payout_99_99_aging_30_days(self, low_risk_merchant, calendar):
        day_0 = date(2026, 9, 1)
        low_risk_merchant.carried_balance = Decimal("99.99")
        low_risk_merchant.pending_since_date = day_0

        day_29 = day_0 + timedelta(days=29)
        payout_d29, _ = PayoutCalculator.compute_daily_merchant_payout(
            merchant=low_risk_merchant,
            settlement_date=day_29,
            eligible_captures=[],
            eligible_refunds=[],
            eligible_chargebacks=[],
            eligible_representments=[],
            active_reserves=[],
            calendar=calendar,
        )
        assert payout_d29.actual_payout == Decimal("0.00")
        assert payout_d29.payout_status == "CARRIED_BELOW_MINIMUM"
        assert low_risk_merchant.carried_balance == Decimal("99.99")

        day_30 = day_0 + timedelta(days=30)
        payout_d30, _ = PayoutCalculator.compute_daily_merchant_payout(
            merchant=low_risk_merchant,
            settlement_date=day_30,
            eligible_captures=[],
            eligible_refunds=[],
            eligible_chargebacks=[],
            eligible_representments=[],
            active_reserves=[],
            calendar=calendar,
        )
        assert payout_d30.actual_payout == Decimal("99.99"), "Must disburse full pending amount under 30-day rule"
        assert payout_d30.closing_balance == Decimal("0.00")
        assert payout_d30.aging_override_applied is True
        assert payout_d30.payout_status == "SETTLED_AGING_OVERRIDE"
        assert low_risk_merchant.carried_balance == Decimal("0.00")
