"""
Transaction Lifecycle Finite State Machine (FSM) and Validation Engine.
Complies with BR-03 and BR-11.

Finite State Transitions:
- [INITIATED] --AUTH--> [AUTHORIZED]
- [AUTHORIZED] --CAPTURE (amount <= auth, <= 7 days)--> [CAPTURED / PARTIALLY_CAPTURED]
- [AUTHORIZED] --(> 7 days)--> [EXPIRED]
- [CAPTURED / PARTIALLY_CAPTURED] --REFUND (<= remaining, <= 180 days)--> [REFUNDED]
- [CAPTURED / PARTIALLY_CAPTURED] --CHARGEBACK--> [CHARGEBACK_FILED]
- [CHARGEBACK_FILED] --REPRESENTMENT--> [REPRESENTMENT_WON / REPRESENTMENT_LOST]

Rejects all illegal transitions (e.g., Refund before Capture, Chargeback on Auth, Exceeded Capture).
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Tuple
from settlement_engine.models.transaction import (
    Transaction,
    TransactionState,
    EventType,
    LifecycleEvent,
)

AUTH_EXPIRY_DAYS = 7
REFUND_EXPIRY_DAYS = 180


class LifecycleValidationError(Exception):
    """Raised when an illegal lifecycle state transition or limit violation occurs."""
    def __init__(self, code: str, message: str):
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message


class LifecycleValidator:
    @staticmethod
    def validate_auth(txn: Transaction, event: LifecycleEvent) -> None:
        """Validates AUTH event."""
        if event.amount <= Decimal("0.00"):
            raise LifecycleValidationError("INVALID_AUTH_AMOUNT", "Authorized amount must be positive.")

    @staticmethod
    def validate_capture(txn: Transaction, event: LifecycleEvent) -> None:
        """
        Validates CAPTURE event (BR-03 & BR-11).
        - Must be in AUTHORIZED state.
        - Must be within 7 days from auth_timestamp.
        - Captured amount must be <= authorized amount.
        """
        if txn.state != TransactionState.AUTHORIZED:
            raise LifecycleValidationError(
                "ILLEGAL_TRANSITION_CAPTURE",
                f"Cannot capture transaction in state '{txn.state.value}'. Must be AUTHORIZED."
            )

        # Check 7-day expiry
        time_elapsed = event.timestamp - txn.auth_timestamp
        if time_elapsed > timedelta(days=AUTH_EXPIRY_DAYS):
            txn.state = TransactionState.EXPIRED
            raise LifecycleValidationError(
                "AUTH_EXPIRED",
                f"Authorization expired! Elapsed time ({time_elapsed.days} days, {time_elapsed.seconds}s) exceeds {AUTH_EXPIRY_DAYS} days."
            )

        if event.amount <= Decimal("0.00"):
            raise LifecycleValidationError(
                "INVALID_CAPTURE_AMOUNT",
                "Captured amount must be greater than zero."
            )

        if event.amount > txn.authorized_amount:
            raise LifecycleValidationError(
                "CAPTURE_EXCEEDS_AUTH",
                f"Captured amount (Rs {event.amount}) exceeds authorized amount (Rs {txn.authorized_amount})."
            )

    @staticmethod
    def validate_refund(txn: Transaction, event: LifecycleEvent) -> None:
        """
        Validates REFUND event (BR-05 & BR-11).
        - Must be in CAPTURED or PARTIALLY_CAPTURED state.
        - Must be within 180 days from capture_timestamp.
        - Refund amount <= captured_amount - prior refunds.
        """
        if txn.state not in (TransactionState.CAPTURED, TransactionState.PARTIALLY_CAPTURED, TransactionState.CHARGEBACK_FILED):
            raise LifecycleValidationError(
                "ILLEGAL_TRANSITION_REFUND",
                f"Cannot refund transaction in state '{txn.state.value}'. Transaction must be captured."
            )

        if txn.capture_timestamp is None:
            raise LifecycleValidationError(
                "MISSING_CAPTURE_RECORD",
                "Cannot refund transaction without a valid capture timestamp."
            )

        # Check 180-day refund window (Edge case: day 180 is valid, day 181 is rejected)
        time_elapsed = event.timestamp - txn.capture_timestamp
        if time_elapsed > timedelta(days=REFUND_EXPIRY_DAYS):
            raise LifecycleValidationError(
                "REFUND_WINDOW_EXPIRED",
                f"Refund requested after {time_elapsed.days} days, exceeding the 180-day regulatory window."
            )

        if event.amount <= Decimal("0.00"):
            raise LifecycleValidationError(
                "INVALID_REFUND_AMOUNT",
                "Refund amount must be greater than zero."
            )

        available_to_refund = txn.remaining_refundable_amount
        if event.amount > available_to_refund:
            raise LifecycleValidationError(
                "EXCESSIVE_REFUND",
                f"Requested refund (Rs {event.amount}) exceeds available refundable balance (Rs {available_to_refund})."
            )

    @staticmethod
    def validate_chargeback(txn: Transaction, event: LifecycleEvent) -> None:
        """
        Validates CHARGEBACK event (BR-06 & BR-11).
        - Must be in CAPTURED or PARTIALLY_CAPTURED state.
        - Cannot chargeback twice.
        """
        if txn.state not in (TransactionState.CAPTURED, TransactionState.PARTIALLY_CAPTURED):
            raise LifecycleValidationError(
                "ILLEGAL_TRANSITION_CHARGEBACK",
                f"Cannot file chargeback on transaction in state '{txn.state.value}'."
            )

        if txn.has_chargeback:
            raise LifecycleValidationError(
                "DUPLICATE_CHARGEBACK",
                "Chargeback already filed on this transaction."
            )

    @staticmethod
    def validate_representment(txn: Transaction, event: LifecycleEvent) -> None:
        """
        Validates REPRESENTMENT event (BR-06).
        - Transaction must currently have a filed chargeback.
        """
        if not txn.has_chargeback or txn.state != TransactionState.CHARGEBACK_FILED:
            raise LifecycleValidationError(
                "ILLEGAL_TRANSITION_REPRESENTMENT",
                "Cannot represent a transaction that has no active chargeback."
            )
        if event.representment_success is None:
            raise LifecycleValidationError(
                "INVALID_REPRESENTMENT_DATA",
                "Representment event must specify representment_success (won=True / lost=False)."
            )
