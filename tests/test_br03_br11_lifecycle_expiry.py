import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from settlement_engine.models.transaction import (
    Transaction,
    PaymentInstrument,
    EventType,
    TransactionState,
    LifecycleEvent,
)
from settlement_engine.rules.lifecycle_validator import (
    LifecycleValidator,
    LifecycleValidationError,
)


class TestBR03AndBR11Lifecycle:

    def test_full_capture_transition(self, low_risk_merchant):
        auth_time = datetime(2026, 9, 1, 10, 0, 0)
        txn = Transaction(
            txn_id="TXN-LIFECYCLE-1",
            merchant_id=low_risk_merchant.merchant_id,
            instrument=PaymentInstrument.UPI,
            authorized_amount=Decimal("1500.00"),
            auth_timestamp=auth_time,
            state=TransactionState.AUTHORIZED,
        )

        cap_time = auth_time + timedelta(hours=2)
        ev_cap = LifecycleEvent(
            event_id="EV-CAP-1",
            txn_id=txn.txn_id,
            merchant_id=txn.merchant_id,
            event_type=EventType.CAPTURE,
            amount=Decimal("1500.00"),
            timestamp=cap_time,
        )
        LifecycleValidator.validate_capture(txn, ev_cap)
        txn.captured_amount = ev_cap.amount
        txn.state = TransactionState.CAPTURED
        assert txn.state == TransactionState.CAPTURED

    def test_partial_capture_validation(self, low_risk_merchant):
        auth_time = datetime(2026, 9, 1, 10, 0, 0)
        txn = Transaction(
            txn_id="TXN-PARTIAL-1",
            merchant_id=low_risk_merchant.merchant_id,
            instrument=PaymentInstrument.DEBIT_CARD,
            authorized_amount=Decimal("5000.00"),
            auth_timestamp=auth_time,
            state=TransactionState.AUTHORIZED,
        )

        cap_time = auth_time + timedelta(hours=4)
        ev_cap = LifecycleEvent(
            event_id="EV-PARTIAL-1",
            txn_id=txn.txn_id,
            merchant_id=txn.merchant_id,
            event_type=EventType.CAPTURE,
            amount=Decimal("3500.00"),
            timestamp=cap_time,
        )
        LifecycleValidator.validate_capture(txn, ev_cap)
        txn.captured_amount = ev_cap.amount
        txn.state = TransactionState.PARTIALLY_CAPTURED
        assert txn.state == TransactionState.PARTIALLY_CAPTURED
        assert txn.remaining_refundable_amount == Decimal("3500.00")

    def test_capture_exceeds_auth_rejected(self, low_risk_merchant):
        auth_time = datetime(2026, 9, 1, 10, 0, 0)
        txn = Transaction(
            txn_id="TXN-OVER-1",
            merchant_id=low_risk_merchant.merchant_id,
            instrument=PaymentInstrument.CREDIT_CARD,
            authorized_amount=Decimal("2000.00"),
            auth_timestamp=auth_time,
            state=TransactionState.AUTHORIZED,
        )

        ev_over = LifecycleEvent(
            event_id="EV-OVER-1",
            txn_id=txn.txn_id,
            merchant_id=txn.merchant_id,
            event_type=EventType.CAPTURE,
            amount=Decimal("2000.01"),
            timestamp=auth_time + timedelta(hours=1),
        )
        with pytest.raises(LifecycleValidationError) as exc:
            LifecycleValidator.validate_capture(txn, ev_over)
        assert exc.value.code == "CAPTURE_EXCEEDS_AUTH"

    def test_illegal_refund_before_capture(self, low_risk_merchant):
        auth_time = datetime(2026, 9, 1, 10, 0, 0)
        txn = Transaction(
            txn_id="TXN-ILLEGAL-REF",
            merchant_id=low_risk_merchant.merchant_id,
            instrument=PaymentInstrument.UPI,
            authorized_amount=Decimal("1000.00"),
            auth_timestamp=auth_time,
            state=TransactionState.AUTHORIZED,
        )

        ev_refund = LifecycleEvent(
            event_id="EV-ILLEGAL-REF",
            txn_id=txn.txn_id,
            merchant_id=txn.merchant_id,
            event_type=EventType.REFUND,
            amount=Decimal("500.00"),
            timestamp=auth_time + timedelta(minutes=30),
        )
        with pytest.raises(LifecycleValidationError) as exc:
            LifecycleValidator.validate_refund(txn, ev_refund)
        assert exc.value.code == "ILLEGAL_TRANSITION_REFUND"

    def test_illegal_chargeback_on_auth(self, low_risk_merchant):
        auth_time = datetime(2026, 9, 1, 10, 0, 0)
        txn = Transaction(
            txn_id="TXN-ILLEGAL-CB",
            merchant_id=low_risk_merchant.merchant_id,
            instrument=PaymentInstrument.UPI,
            authorized_amount=Decimal("1000.00"),
            auth_timestamp=auth_time,
            state=TransactionState.AUTHORIZED,
        )

        ev_cb = LifecycleEvent(
            event_id="EV-ILLEGAL-CB",
            txn_id=txn.txn_id,
            merchant_id=txn.merchant_id,
            event_type=EventType.CHARGEBACK,
            amount=Decimal("1000.00"),
            timestamp=auth_time + timedelta(minutes=45),
        )
        with pytest.raises(LifecycleValidationError) as exc:
            LifecycleValidator.validate_chargeback(txn, ev_cb)
        assert exc.value.code == "ILLEGAL_TRANSITION_CHARGEBACK"
