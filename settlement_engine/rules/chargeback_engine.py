from dataclasses import dataclass
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Optional
from settlement_engine.models.merchant import Merchant, RiskGrade
from settlement_engine.models.transaction import Transaction, LifecycleEvent, TransactionState
from settlement_engine.rules.lifecycle_validator import LifecycleValidator

CHARGEBACK_FEE = Decimal("250.00")
RATIO_THRESHOLD = Decimal("0.01")


@dataclass(frozen=True)
class QueuedChargeback:
    chargeback_id: str
    txn_id: str
    merchant_id: str
    amount: Decimal
    fee: Decimal
    timestamp: datetime
    effective_date: date

    @property
    def total_debit(self) -> Decimal:
        return self.amount + self.fee


@dataclass(frozen=True)
class QueuedRepresentmentCredit:
    representment_id: str
    txn_id: str
    merchant_id: str
    credit_amount: Decimal
    timestamp: datetime
    effective_date: date


class ChargebackEngine:
    @staticmethod
    def process_chargeback(txn: Transaction, event: LifecycleEvent) -> QueuedChargeback:
        LifecycleValidator.validate_chargeback(txn, event)

        txn.has_chargeback = True
        txn.chargeback_fee = CHARGEBACK_FEE
        txn.state = TransactionState.CHARGEBACK_FILED
        txn.events.append(event)

        return QueuedChargeback(
            chargeback_id=event.event_id,
            txn_id=txn.txn_id,
            merchant_id=txn.merchant_id,
            amount=txn.captured_amount,
            fee=CHARGEBACK_FEE,
            timestamp=event.timestamp,
            effective_date=event.timestamp.date(),
        )

    @staticmethod
    def process_representment(txn: Transaction, event: LifecycleEvent) -> Optional[QueuedRepresentmentCredit]:
        LifecycleValidator.validate_representment(txn, event)

        txn.representment_won = event.representment_success
        txn.events.append(event)

        if event.representment_success:
            return QueuedRepresentmentCredit(
                representment_id=event.event_id,
                txn_id=txn.txn_id,
                merchant_id=txn.merchant_id,
                credit_amount=txn.captured_amount,
                timestamp=event.timestamp,
                effective_date=event.timestamp.date(),
            )
        return None

    @staticmethod
    def evaluate_risk_grade(
        merchant: Merchant,
        as_of_date: date,
        all_captures: List[Transaction],
        all_chargebacks: List[QueuedChargeback]
    ) -> None:
        window_start = as_of_date - timedelta(days=30)

        captures_in_window = sum(
            1 for t in all_captures
            if t.merchant_id == merchant.merchant_id
            and t.capture_timestamp is not None
            and window_start <= t.capture_timestamp.date() < as_of_date
        )

        chargebacks_in_window = sum(
            1 for c in all_chargebacks
            if c.merchant_id == merchant.merchant_id
            and window_start <= c.effective_date < as_of_date
        )

        if captures_in_window > 0:
            ratio = Decimal(chargebacks_in_window) / Decimal(captures_in_window)
            if ratio > RATIO_THRESHOLD:
                new_grade = merchant.current_risk_grade.worsen()
                merchant.current_risk_grade = new_grade
                merchant.consecutive_clean_days = 0
                return

        had_chargeback_today = any(
            c.merchant_id == merchant.merchant_id and c.effective_date == as_of_date
            for c in all_chargebacks
        )

        if had_chargeback_today:
            merchant.consecutive_clean_days = 0
        else:
            merchant.consecutive_clean_days += 1
            if merchant.consecutive_clean_days >= 60:
                merchant.current_risk_grade = merchant.current_risk_grade.recover()
                merchant.consecutive_clean_days = 0
