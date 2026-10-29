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
from settlement_engine.rules.lifecycle_validator import LifecycleValidationError
from settlement_engine.rules.refund_engine import RefundEngine


class TestBR05RefundNetting:

    def test_partial_and_full_refund_sequence(self, low_risk_merchant):
        cap_time = datetime(2026, 9, 1, 12, 0, 0)
        txn = Transaction(
            txn_id="TXN-REF-SEQ",
            merchant_id=low_risk_merchant.merchant_id,
            instrument=PaymentInstrument.CREDIT_CARD,
            authorized_amount=Decimal("4000.00"),
            auth_timestamp=cap_time - timedelta(hours=1),
            captured_amount=Decimal("4000.00"),
            capture_timestamp=cap_time,
            mdr_amount=Decimal("72.00"),
            gst_amount=Decimal("12.96"),
            state=TransactionState.CAPTURED,
        )

        ev_ref1 = LifecycleEvent(
            event_id="EV-R1",
            txn_id=txn.txn_id,
            merchant_id=txn.merchant_id,
            event_type=EventType.REFUND,
            amount=Decimal("1500.00"),
            timestamp=cap_time + timedelta(days=2),
        )
        q_ref1 = RefundEngine.process_refund(txn, ev_ref1)
        assert q_ref1.amount == Decimal("1500.00")
        assert txn.refunded_amount == Decimal("1500.00")
        assert txn.remaining_refundable_amount == Decimal("2500.00")

        ev_ref2 = LifecycleEvent(
            event_id="EV-R2",
            txn_id=txn.txn_id,
            merchant_id=txn.merchant_id,
            event_type=EventType.REFUND,
            amount=Decimal("2500.00"),
            timestamp=cap_time + timedelta(days=5),
        )
        q_ref2 = RefundEngine.process_refund(txn, ev_ref2)
        assert q_ref2.amount == Decimal("2500.00")
        assert txn.refunded_amount == Decimal("4000.00")
        assert txn.remaining_refundable_amount == Decimal("0.00")

        ev_ref3 = LifecycleEvent(
            event_id="EV-R3",
            txn_id=txn.txn_id,
            merchant_id=txn.merchant_id,
            event_type=EventType.REFUND,
            amount=Decimal("1.00"),
            timestamp=cap_time + timedelta(days=6),
        )
        with pytest.raises(LifecycleValidationError) as exc:
            RefundEngine.process_refund(txn, ev_ref3)
        assert exc.value.code == "EXCESSIVE_REFUND"

    def test_mdr_retention_on_refund(self, low_risk_merchant):
        cap_time = datetime(2026, 9, 1, 12, 0, 0)
        txn = Transaction(
            txn_id="TXN-MDR-RETAIN",
            merchant_id=low_risk_merchant.merchant_id,
            instrument=PaymentInstrument.WALLET,
            authorized_amount=Decimal("1000.00"),
            auth_timestamp=cap_time - timedelta(hours=1),
            captured_amount=Decimal("1000.00"),
            capture_timestamp=cap_time,
            mdr_amount=Decimal("20.00"),
            gst_amount=Decimal("3.60"),
            state=TransactionState.CAPTURED,
        )

        ev_ref = LifecycleEvent(
            event_id="EV-R-FULL",
            txn_id=txn.txn_id,
            merchant_id=txn.merchant_id,
            event_type=EventType.REFUND,
            amount=Decimal("1000.00"),
            timestamp=cap_time + timedelta(days=1),
        )
        RefundEngine.process_refund(txn, ev_ref)

        assert txn.mdr_amount == Decimal("20.00"), "MDR must be retained on refund"
        assert txn.gst_amount == Decimal("3.60"), "GST must be retained on refund"
