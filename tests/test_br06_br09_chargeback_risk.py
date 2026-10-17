"""
Test Suite for BR-06 (Chargebacks, Representments) and BR-09 (Dynamic Risk Grading).
"""

import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal
from settlement_engine.models.merchant import RiskGrade
from settlement_engine.models.transaction import (
    Transaction,
    PaymentInstrument,
    EventType,
    TransactionState,
    LifecycleEvent,
)
from settlement_engine.rules.chargeback_engine import (
    ChargebackEngine,
    QueuedChargeback,
    CHARGEBACK_FEE,
)


class TestBR06AndBR09ChargebackRisk:

    def test_chargeback_and_representment_flow(self, low_risk_merchant):
        cap_time = datetime(2026, 9, 1, 10, 0, 0)
        txn = Transaction(
            txn_id="TXN-CB-REP",
            merchant_id=low_risk_merchant.merchant_id,
            instrument=PaymentInstrument.CREDIT_CARD,
            authorized_amount=Decimal("3000.00"),
            auth_timestamp=cap_time - timedelta(hours=1),
            captured_amount=Decimal("3000.00"),
            capture_timestamp=cap_time,
            state=TransactionState.CAPTURED,
        )

        # 1. File Chargeback
        ev_cb = LifecycleEvent(
            event_id="EV-CB-1",
            txn_id=txn.txn_id,
            merchant_id=txn.merchant_id,
            event_type=EventType.CHARGEBACK,
            amount=Decimal("3000.00"),
            timestamp=cap_time + timedelta(days=5),
        )
        q_cb = ChargebackEngine.process_chargeback(txn, ev_cb)
        assert q_cb.amount == Decimal("3000.00")
        assert q_cb.fee == Decimal("250.00")
        assert q_cb.total_debit == Decimal("3250.00")
        assert txn.state == TransactionState.CHARGEBACK_FILED

        # 2. Representment Won
        ev_rep_won = LifecycleEvent(
            event_id="EV-REP-1",
            txn_id=txn.txn_id,
            merchant_id=txn.merchant_id,
            event_type=EventType.REPRESENTMENT,
            amount=Decimal("3000.00"),
            timestamp=cap_time + timedelta(days=12),
            representment_success=True,
        )
        rep_credit = ChargebackEngine.process_representment(txn, ev_rep_won)
        assert rep_credit is not None
        assert rep_credit.credit_amount == Decimal("3000.00"), "Only transaction amount is credited back, not the fee"

    def test_representment_lost(self, low_risk_merchant):
        cap_time = datetime(2026, 9, 1, 10, 0, 0)
        txn = Transaction(
            txn_id="TXN-CB-LOST",
            merchant_id=low_risk_merchant.merchant_id,
            instrument=PaymentInstrument.CREDIT_CARD,
            authorized_amount=Decimal("2000.00"),
            auth_timestamp=cap_time - timedelta(hours=1),
            captured_amount=Decimal("2000.00"),
            capture_timestamp=cap_time,
            state=TransactionState.CAPTURED,
        )

        ev_cb = LifecycleEvent(
            event_id="EV-CB-2",
            txn_id=txn.txn_id,
            merchant_id=txn.merchant_id,
            event_type=EventType.CHARGEBACK,
            amount=Decimal("2000.00"),
            timestamp=cap_time + timedelta(days=2),
        )
        ChargebackEngine.process_chargeback(txn, ev_cb)

        ev_rep_lost = LifecycleEvent(
            event_id="EV-REP-LOST",
            txn_id=txn.txn_id,
            merchant_id=txn.merchant_id,
            event_type=EventType.REPRESENTMENT,
            amount=Decimal("2000.00"),
            timestamp=cap_time + timedelta(days=8),
            representment_success=False,
        )
        rep_credit = ChargebackEngine.process_representment(txn, ev_rep_lost)
        assert rep_credit is None, "No credit should be returned when representment is lost"

    def test_dynamic_downgrade_and_60_days_clean_recovery(self, low_risk_merchant):
        # Starts at LOW
        assert low_risk_merchant.current_risk_grade == RiskGrade.LOW

        as_of = date(2026, 9, 20)
        # 10 captures and 1 chargeback in trailing 30 days -> 10% ratio > 1.00%
        captures = [
            Transaction(
                txn_id=f"T-{i}",
                merchant_id=low_risk_merchant.merchant_id,
                instrument=PaymentInstrument.UPI,
                authorized_amount=Decimal("500.00"),
                auth_timestamp=datetime(2026, 9, 5, 10, 0),
                captured_amount=Decimal("500.00"),
                capture_timestamp=datetime(2026, 9, 5, 12, 0),
            )
            for i in range(10)
        ]
        chargebacks = [
            QueuedChargeback(
                chargeback_id="CB-DOWN",
                txn_id="T-0",
                merchant_id=low_risk_merchant.merchant_id,
                amount=Decimal("500.00"),
                fee=CHARGEBACK_FEE,
                timestamp=datetime(2026, 9, 10, 10, 0),
                effective_date=date(2026, 9, 10),
            )
        ]

        # Trigger evaluation -> Downgrade LOW -> MEDIUM
        ChargebackEngine.evaluate_risk_grade(low_risk_merchant, as_of, captures, chargebacks)
        assert low_risk_merchant.current_risk_grade == RiskGrade.MEDIUM
        assert low_risk_merchant.consecutive_clean_days == 0

        # Simulate 60 clean days with zero chargebacks
        curr_date = as_of
        for _ in range(60):
            curr_date += timedelta(days=1)
            # No chargebacks in trailing window now
            ChargebackEngine.evaluate_risk_grade(low_risk_merchant, curr_date, captures, [])

        # After 60 clean days, recovers from MEDIUM back to LOW!
        assert low_risk_merchant.current_risk_grade == RiskGrade.LOW
