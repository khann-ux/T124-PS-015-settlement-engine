"""
Master Settlement Engine Orchestrator.
Coordinates ingest of Merchants, Calendar, Lifecycle Events, and Daily Payout Batches.
"""

from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Set
from settlement_engine.models.merchant import Merchant, RiskGrade, MDRPlan, BankAccount
from settlement_engine.models.transaction import (
    Transaction,
    PaymentInstrument,
    EventType,
    TransactionState,
    LifecycleEvent,
)
from settlement_engine.models.holiday import CalendarService
from settlement_engine.models.settlement import (
    DailySettlementBatch,
    PayoutRecord,
    ReserveEntry,
)
from settlement_engine.models.invoice import MonthlyInvoice
from settlement_engine.rules.mdr_calculator import calculate_mdr_and_gst
from settlement_engine.rules.lifecycle_validator import LifecycleValidator, LifecycleValidationError
from settlement_engine.rules.calendar_service import compute_settlement_date
from settlement_engine.rules.refund_engine import RefundEngine, QueuedRefund
from settlement_engine.rules.chargeback_engine import (
    ChargebackEngine,
    QueuedChargeback,
    QueuedRepresentmentCredit,
)
from settlement_engine.rules.payout_calculator import PayoutCalculator
from settlement_engine.rules.invoice_generator import InvoiceGenerator


class SettlementEngine:
    def __init__(self):
        self.merchants: Dict[str, Merchant] = {}
        self.calendar: CalendarService = CalendarService()
        self.transactions: Dict[str, Transaction] = {}
        
        # Queues for settlement batching
        self.captured_transactions: List[Transaction] = []
        self.queued_refunds: List[QueuedRefund] = []
        self.queued_chargebacks: List[QueuedChargeback] = []
        self.queued_representments: List[QueuedRepresentmentCredit] = []
        
        # Active rolling reserves
        self.active_reserves: List[ReserveEntry] = []
        
        # Historical settlement output records
        self.settlement_batches: Dict[date, DailySettlementBatch] = {}
        self.event_log: List[LifecycleEvent] = []
        self.rejection_log: List[Dict[str, str]] = []

    def register_merchant(self, merchant: Merchant) -> None:
        self.merchants[merchant.merchant_id] = merchant

    def register_holiday(self, holiday_date: date) -> None:
        self.calendar.add_holiday(holiday_date)

    def process_event(self, event: LifecycleEvent) -> bool:
        """
        Processes a single lifecycle event through the validation & accounting pipeline.
        Returns True if accepted, False if rejected.
        """
        self.event_log.append(event)
        
        try:
            merchant = self.merchants.get(event.merchant_id)
            if not merchant:
                raise LifecycleValidationError("UNKNOWN_MERCHANT", f"Merchant '{event.merchant_id}' is not registered.")

            if event.event_type == EventType.AUTH:
                if event.txn_id in self.transactions:
                    raise LifecycleValidationError("DUPLICATE_AUTH", f"Transaction '{event.txn_id}' already initialized.")
                
                # Default instrument fallback or read from metadata
                instrument_str = (event.notes or "UPI").upper()
                try:
                    instrument = PaymentInstrument[instrument_str]
                except KeyError:
                    instrument = PaymentInstrument.UPI

                txn = Transaction(
                    txn_id=event.txn_id,
                    merchant_id=event.merchant_id,
                    instrument=instrument,
                    authorized_amount=event.amount,
                    auth_timestamp=event.timestamp,
                    state=TransactionState.AUTHORIZED,
                )
                LifecycleValidator.validate_auth(txn, event)
                txn.events.append(event)
                self.transactions[event.txn_id] = txn
                return True

            txn = self.transactions.get(event.txn_id)
            if not txn:
                raise LifecycleValidationError("TXN_NOT_FOUND", f"Transaction '{event.txn_id}' not found for event {event.event_type}.")

            if event.event_type == EventType.CAPTURE:
                LifecycleValidator.validate_capture(txn, event)
                txn.captured_amount = event.amount
                txn.capture_timestamp = event.timestamp
                
                # Compute MDR and GST (BR-01, BR-02)
                mdr, gst = calculate_mdr_and_gst(merchant, txn.instrument, txn.captured_amount)
                txn.mdr_amount = mdr
                txn.gst_amount = gst
                txn.net_captured_amount = txn.captured_amount - (mdr + gst)
                
                # Settlement date assignment (BR-04)
                txn.settlement_date = compute_settlement_date(
                    capture_timestamp=txn.capture_timestamp,
                    risk_grade=merchant.current_risk_grade,
                    calendar=self.calendar
                )
                
                txn.state = (
                    TransactionState.CAPTURED
                    if txn.captured_amount == txn.authorized_amount
                    else TransactionState.PARTIALLY_CAPTURED
                )
                txn.events.append(event)
                self.captured_transactions.append(txn)
                return True

            elif event.event_type == EventType.REFUND:
                refund_entry = RefundEngine.process_refund(txn, event)
                self.queued_refunds.append(refund_entry)
                return True

            elif event.event_type == EventType.CHARGEBACK:
                cb_entry = ChargebackEngine.process_chargeback(txn, event)
                self.queued_chargebacks.append(cb_entry)
                return True

            elif event.event_type == EventType.REPRESENTMENT:
                rep_entry = ChargebackEngine.process_representment(txn, event)
                if rep_entry:
                    self.queued_representments.append(rep_entry)
                return True

            else:
                raise LifecycleValidationError("UNSUPPORTED_EVENT", f"Event type {event.event_type} not supported.")

        except LifecycleValidationError as err:
            self.rejection_log.append({
                "event_id": event.event_id,
                "txn_id": event.txn_id,
                "merchant_id": event.merchant_id,
                "event_type": event.event_type.value,
                "error_code": err.code,
                "error_message": err.message,
                "timestamp": event.timestamp.isoformat(),
            })
            return False

    def run_daily_settlement(self, settlement_date: date) -> DailySettlementBatch:
        """
        Executes daily settlement job for all merchants on settlement_date.
        Only runs on business days (BR-04).
        """
        batch = DailySettlementBatch(batch_date=settlement_date)

        # Check if settlement_date is a business day
        if not self.calendar.is_business_day(settlement_date):
            self.settlement_batches[settlement_date] = batch
            return batch

        # 1. Evaluate Dynamic Risk Grades across all merchants first (BR-09)
        for merchant in self.merchants.values():
            ChargebackEngine.evaluate_risk_grade(
                merchant=merchant,
                as_of_date=settlement_date,
                all_captures=self.captured_transactions,
                all_chargebacks=self.queued_chargebacks
            )

        # 2. Process settlement for each merchant
        for merchant_id, merchant in self.merchants.items():
            # Identify captures eligible for settlement on this date
            eligible_captures = [
                t for t in self.captured_transactions
                if t.merchant_id == merchant_id
                and not t.is_settled
                and t.settlement_date == settlement_date
            ]

            # Identify queued refunds due for netting on or before settlement_date
            eligible_refunds = [
                r for r in self.queued_refunds
                if r.merchant_id == merchant_id
                and r.effective_date <= settlement_date
            ]

            # Identify queued chargebacks due for debit
            eligible_chargebacks = [
                c for c in self.queued_chargebacks
                if c.merchant_id == merchant_id
                and c.effective_date <= settlement_date
            ]

            # Identify won representment credits
            eligible_reps = [
                rep for rep in self.queued_representments
                if rep.merchant_id == merchant_id
                and rep.effective_date <= settlement_date
            ]

            # Execute waterfall payout computation (BR-08, BR-10)
            payout_rec, new_reserves = PayoutCalculator.compute_daily_merchant_payout(
                merchant=merchant,
                settlement_date=settlement_date,
                eligible_captures=eligible_captures,
                eligible_refunds=eligible_refunds,
                eligible_chargebacks=eligible_chargebacks,
                eligible_representments=eligible_reps,
                active_reserves=self.active_reserves,
                calendar=self.calendar,
                batch_seq=len(batch.payout_records) + 1
            )

            # Mark processed items
            for t in eligible_captures:
                t.is_settled = True

            # Remove consumed netting items from active queues
            self.queued_refunds = [r for r in self.queued_refunds if r not in eligible_refunds]
            self.queued_chargebacks = [c for c in self.queued_chargebacks if c not in eligible_chargebacks]
            self.queued_representments = [rep for rep in self.queued_representments if rep not in eligible_reps]

            # Store new rolling reserves
            self.active_reserves.extend(new_reserves)

            batch.payout_records.append(payout_rec)
            batch.total_disbursed += payout_rec.actual_payout
            if payout_rec.actual_payout > Decimal("0.00"):
                batch.total_merchants_settled += 1

        self.settlement_batches[settlement_date] = batch
        return batch

    def generate_monthly_invoices(self, year: int, month: int) -> List[MonthlyInvoice]:
        """Generates monthly MDR and GST invoices for all registered merchants (BR-10)."""
        invoices: List[MonthlyInvoice] = []
        for merchant in self.merchants.values():
            inv = InvoiceGenerator.generate_monthly_invoice(
                merchant=merchant,
                billing_year=year,
                billing_month=month,
                month_captures=self.captured_transactions
            )
            invoices.append(inv)
        return invoices
