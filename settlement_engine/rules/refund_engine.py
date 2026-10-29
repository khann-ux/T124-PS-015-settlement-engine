from dataclasses import dataclass
from datetime import datetime, date
from decimal import Decimal
from settlement_engine.models.transaction import Transaction, LifecycleEvent, EventType
from settlement_engine.rules.lifecycle_validator import LifecycleValidator


@dataclass(frozen=True)
class QueuedRefund:
    refund_id: str
    txn_id: str
    merchant_id: str
    amount: Decimal
    timestamp: datetime
    effective_date: date


class RefundEngine:
    @staticmethod
    def process_refund(txn: Transaction, event: LifecycleEvent) -> QueuedRefund:
        LifecycleValidator.validate_refund(txn, event)

        txn.refunded_amount += event.amount
        txn.events.append(event)

        return QueuedRefund(
            refund_id=event.event_id,
            txn_id=txn.txn_id,
            merchant_id=txn.merchant_id,
            amount=event.amount,
            timestamp=event.timestamp,
            effective_date=event.timestamp.date(),
        )
