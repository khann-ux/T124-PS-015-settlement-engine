"""
Chargeback Management and Dynamic Risk Grading Engine.
Complies with BR-06 and BR-09.

BR-06:
- Chargeback debits (captured amount + Rs 250 fee) from the next settlement batch.
- Representment: If merchant wins, the transaction amount (NOT the Rs 250 fee) is credited back.
- If merchant loses, no credit is provided.

BR-09:
- Trailing 30 days: If count(chargebacks) / count(captures) > 1.00%, merchant risk grade worsens
  by one level (LOW -> MEDIUM, MEDIUM -> HIGH) starting from the NEXT DAY.
- Edge case: Exactly 1.00% (ratio == 0.0100) does NOT trigger a downgrade.
- Recovery rule: If the merchant maintains 60 consecutive clean days with ZERO chargebacks,
  the risk grade recovers by one level (HIGH -> MEDIUM, MEDIUM -> LOW).
"""

from dataclasses import dataclass
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Optional
from settlement_engine.models.merchant import Merchant, RiskGrade
from settlement_engine.models.transaction import Transaction, LifecycleEvent, TransactionState
from settlement_engine.rules.lifecycle_validator import LifecycleValidator

CHARGEBACK_FEE = Decimal("250.00")
RATIO_THRESHOLD = Decimal("0.01")  # 1.00%


@dataclass(frozen=True)
class QueuedChargeback:
    chargeback_id: str
    txn_id: str
    merchant_id: str
    amount: Decimal  # captured transaction amount
    fee: Decimal  # Rs 250
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
    credit_amount: Decimal  # only the transaction amount, fee is retained
    timestamp: datetime
    effective_date: date


class ChargebackEngine:
    @staticmethod
    def process_chargeback(txn: Transaction, event: LifecycleEvent) -> QueuedChargeback:
        """
        Validates and processes a chargeback on a captured transaction.
        Debits captured amount + Rs 250 fee.
        """
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
        """
        Processes a representment decision.
        If won (representment_success=True), returns a credit for the transaction amount.
        Fee is NEVER credited back.
        """
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
        """
        Evaluates dynamic risk grade based on trailing 30 days window (BR-09).
        Window: [as_of_date - 30 days, as_of_date).
        """
        window_start = as_of_date - timedelta(days=30)

        # Count captures in trailing 30 days
        captures_in_window = sum(
            1 for t in all_captures
            if t.merchant_id == merchant.merchant_id
            and t.capture_timestamp is not None
            and window_start <= t.capture_timestamp.date() < as_of_date
        )

        # Count chargebacks in trailing 30 days
        chargebacks_in_window = sum(
            1 for c in all_chargebacks
            if c.merchant_id == merchant.merchant_id
            and window_start <= c.effective_date < as_of_date
        )

        # Downgrade check
        if captures_in_window > 0:
            ratio = Decimal(chargebacks_in_window) / Decimal(captures_in_window)
            if ratio > RATIO_THRESHOLD:
                # Strictly greater than 1%
                new_grade = merchant.current_risk_grade.worsen()
                merchant.current_risk_grade = new_grade
                merchant.consecutive_clean_days = 0
                return

        # Recovery check (60 consecutive clean days)
        # Check if any chargebacks occurred today
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
                merchant.consecutive_clean_days = 0  # reset for next tier recovery
