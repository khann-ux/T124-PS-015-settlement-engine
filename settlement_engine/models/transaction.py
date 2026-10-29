from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Optional, List
from datetime import datetime


class PaymentInstrument(str, Enum):
    UPI = "UPI"
    DEBIT_CARD = "DEBIT_CARD"
    CREDIT_CARD = "CREDIT_CARD"
    NET_BANKING = "NET_BANKING"
    WALLET = "WALLET"
    INTERNATIONAL_CARD = "INTERNATIONAL_CARD"


class EventType(str, Enum):
    AUTH = "AUTH"
    CAPTURE = "CAPTURE"
    REFUND = "REFUND"
    CHARGEBACK = "CHARGEBACK"
    REPRESENTMENT = "REPRESENTMENT"


class TransactionState(str, Enum):
    INITIATED = "INITIATED"
    AUTHORIZED = "AUTHORIZED"
    CAPTURED = "CAPTURED"
    PARTIALLY_CAPTURED = "PARTIALLY_CAPTURED"
    EXPIRED = "EXPIRED"
    CHARGEBACK_FILED = "CHARGEBACK_FILED"
    SETTLED = "SETTLED"


@dataclass(frozen=True)
class LifecycleEvent:
    event_id: str
    txn_id: str
    merchant_id: str
    event_type: EventType
    amount: Decimal
    timestamp: datetime
    representment_success: Optional[bool] = None
    notes: Optional[str] = None


@dataclass
class Transaction:
    txn_id: str
    merchant_id: str
    instrument: PaymentInstrument
    authorized_amount: Decimal
    auth_timestamp: datetime

    captured_amount: Decimal = Decimal("0.00")
    capture_timestamp: Optional[datetime] = None

    mdr_amount: Decimal = Decimal("0.00")
    gst_amount: Decimal = Decimal("0.00")
    net_captured_amount: Decimal = Decimal("0.00")

    refunded_amount: Decimal = Decimal("0.00")
    has_chargeback: bool = False
    chargeback_fee: Decimal = Decimal("0.00")
    representment_won: Optional[bool] = None

    state: TransactionState = TransactionState.AUTHORIZED
    events: List[LifecycleEvent] = field(default_factory=list)
    is_settled: bool = False
    settlement_date: Optional[datetime] = None

    @property
    def remaining_refundable_amount(self) -> Decimal:
        return max(Decimal("0.00"), self.captured_amount - self.refunded_amount)
