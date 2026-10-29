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

    gross_captured: Decimal = Decimal("0.00")
    total_mdr: Decimal = Decimal("0.00")
    total_gst: Decimal = Decimal("0.00")

    total_refunds: Decimal = Decimal("0.00")
    total_chargeback_debits: Decimal = Decimal("0.00")
    total_representment_credits: Decimal = Decimal("0.00")

    reserve_withheld: Decimal = Decimal("0.00")
    reserve_released: Decimal = Decimal("0.00")

    opening_balance: Decimal = Decimal("0.00")
    calculated_settlement: Decimal = Decimal("0.00")
    actual_payout: Decimal = Decimal("0.00")
    closing_balance: Decimal = Decimal("0.00")

    payout_status: str = "SETTLED"
    aging_override_applied: bool = False
    note: str = ""

    @property
    def net_captured(self) -> Decimal:
        return self.gross_captured - self.total_mdr - self.total_gst

    @property
    def net_chargebacks(self) -> Decimal:
        return self.total_chargeback_debits - self.total_representment_credits


@dataclass
class DailySettlementBatch:
    batch_date: date
    payout_records: List[PayoutRecord] = field(default_factory=list)
    total_disbursed: Decimal = Decimal("0.00")
    total_merchants_settled: int = 0
