"""
Refund Processing and Netting Engine.
Complies with BR-05.

BR-05:
- Full or partial refunds allowed up to (captured_amount - prior_refunds).
- Allowed strictly within 180 days from the capture timestamp.
- MDR on refunded portion is NOT returned (Payment Aggregator retains MDR).
- Refund amount is queued for netting from the merchant's upcoming settlement batch.

Placement Viva Concept Note:
"Why is MDR not refunded on refunds?"
When a transaction is captured, the aggregator pays non-refundable interchange
and network assessment fees to the card networks (Visa/Mastercard/NPCI) and
processing costs to the acquiring bank. Card networks do not refund interchange
on charge/refund reversal. Aggregators absorb operational costs and fraud risk,
so the MDR and GST charged on the original capture are retained.
"""

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
        """
        Validates and records a refund against a transaction.
        Returns a QueuedRefund to be deducted in the next settlement run.
        """
        # Validate lifecycle constraints & 180-day window
        LifecycleValidator.validate_refund(txn, event)

        # Update transaction accounting
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
