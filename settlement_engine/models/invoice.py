from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional
from datetime import date


@dataclass
class InvoiceLineItem:
    instrument: str
    transaction_count: int
    gross_volume: Decimal
    mdr_amount: Decimal
    gst_amount: Decimal
    total_charged: Decimal


@dataclass
class MonthlyInvoice:
    invoice_number: str
    invoice_date: date
    billing_period: str
    merchant_id: str
    business_name: str
    gstin: Optional[str]
    is_gst_registered: bool

    line_items: List[InvoiceLineItem] = field(default_factory=list)
    total_transactions: int = 0
    total_gross_volume: Decimal = Decimal("0.00")
    total_mdr: Decimal = Decimal("0.00")
    total_gst: Decimal = Decimal("0.00")
    grand_total: Decimal = Decimal("0.00")

    itc_eligible: bool = False
    itc_disclaimer: str = ""
