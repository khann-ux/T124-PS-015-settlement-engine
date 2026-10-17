"""
Domain models for Settlement Batches, Payout Records, and Rolling Reserves.
Complies with BR-04, BR-06, BR-07, and BR-08.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional
from datetime import date


@dataclass
class ReserveEntry:
    reserve_id: str
    merchant_id: str
    originated_date: date
    amount: Decimal
    hold_days: int
    release_due_date: date
    is_released: bool = False
    released_date: Optional[date] = None


@dataclass
class PayoutRecord:
    merchant_id: str
    settlement_date: date
    
    # Captures
    gross_captured: Decimal = Decimal("0.00")
    total_mdr: Decimal = Decimal("0.00")
    total_gst: Decimal = Decimal("0.00")
    
    # Netting items
    total_refunds: Decimal = Decimal("0.00")
    total_chargeback_debits: Decimal = Decimal("0.00")  # txn amount + Rs 250 fee
    total_representment_credits: Decimal = Decimal("0.00")  # txn amount refunded upon won representment
    
    # Rolling reserve
    reserve_withheld: Decimal = Decimal("0.00")
    reserve_released: Decimal = Decimal("0.00")
    
    # Ledger balance tracking
    opening_balance: Decimal = Decimal("0.00")  # carried forward from previous cycle
    calculated_settlement: Decimal = Decimal("0.00")  # raw computation before min-payout/negative check
    actual_payout: Decimal = Decimal("0.00")  # final amount credited to merchant's bank
    closing_balance: Decimal = Decimal("0.00")  # carried forward to next cycle
    
    # Status and diagnostics
    payout_status: str = "SETTLED"  # SETTLED, CARRIED_BELOW_MINIMUM, NEGATIVE_CARRIED_FORWARD
    aging_override_applied: bool = False
    note: str = ""

    @property
    def net_captured(self) -> Decimal:
        """Net captured = Gross Captured - (MDR + GST)"""
        return self.gross_captured - self.total_mdr - self.total_gst

    @property
    def net_chargebacks(self) -> Decimal:
        """Net chargeback deduction = Debits - Won Representment Credits"""
        return self.total_chargeback_debits - self.total_representment_credits


@dataclass
class DailySettlementBatch:
    batch_date: date
    payout_records: List[PayoutRecord] = field(default_factory=list)
    total_disbursed: Decimal = Decimal("0.00")
    total_merchants_settled: int = 0
