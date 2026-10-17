"""
Monthly MDR & GST Invoicing Generator.
Complies with BR-10.

BR-10:
- Generated on the 1st of each month for the preceding calendar month.
- Per-instrument breakdown: Volume, Gross Volume, MDR, GST (18%), Total Fee.
- GST Registered Merchants: Itemized GST line, ITC eligible with merchant GSTIN reference.
- Non-GST Registered Merchants: Invoiced inclusive of GST with NO ITC line and B2C disclaimer.
"""

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import List, Dict
from settlement_engine.models.merchant import Merchant
from settlement_engine.models.transaction import Transaction
from settlement_engine.models.invoice import MonthlyInvoice, InvoiceLineItem
from settlement_engine.rules.mdr_calculator import quantize_amount


class InvoiceGenerator:
    @staticmethod
    def generate_monthly_invoice(
        merchant: Merchant,
        billing_year: int,
        billing_month: int,
        month_captures: List[Transaction]
    ) -> MonthlyInvoice:
        """
        Compiles the monthly invoice for transactions captured in billing_year-billing_month.
        Invoice date is the 1st of the subsequent month.
        """
        # Determine 1st of next month for invoice date
        if billing_month == 12:
            invoice_date = date(billing_year + 1, 1, 1)
        else:
            invoice_date = date(billing_year, billing_month + 1, 1)

        billing_period_str = f"{billing_year:04d}-{billing_month:02d}"
        invoice_number = f"INV-{billing_year:04d}{billing_month:02d}-{merchant.merchant_id}"

        # Group by instrument
        instrument_stats: Dict[str, Dict[str, Decimal]] = defaultdict(lambda: {
            "count": Decimal("0"),
            "gross": Decimal("0.00"),
            "mdr": Decimal("0.00"),
            "gst": Decimal("0.00"),
        })

        for txn in month_captures:
            if txn.merchant_id == merchant.merchant_id and txn.capture_timestamp:
                ct = txn.capture_timestamp
                if ct.year == billing_year and ct.month == billing_month:
                    inst = txn.instrument.value
                    instrument_stats[inst]["count"] += Decimal("1")
                    instrument_stats[inst]["gross"] += txn.captured_amount
                    instrument_stats[inst]["mdr"] += txn.mdr_amount
                    instrument_stats[inst]["gst"] += txn.gst_amount

        line_items: List[InvoiceLineItem] = []
        total_txns = 0
        total_gross = Decimal("0.00")
        total_mdr = Decimal("0.00")
        total_gst = Decimal("0.00")

        for inst, data in sorted(instrument_stats.items()):
            tx_count = int(data["count"])
            gross = quantize_amount(data["gross"])
            mdr = quantize_amount(data["mdr"])
            gst = quantize_amount(data["gst"])
            total_charged = quantize_amount(mdr + gst)

            total_txns += tx_count
            total_gross += gross
            total_mdr += mdr
            total_gst += gst

            line_items.append(
                InvoiceLineItem(
                    instrument=inst,
                    transaction_count=tx_count,
                    gross_volume=gross,
                    mdr_amount=mdr,
                    gst_amount=gst,
                    total_charged=total_charged,
                )
            )

        grand_total = quantize_amount(total_mdr + total_gst)

        if merchant.is_gst_registered:
            itc_eligible = True
            itc_disclaimer = (
                f"Eligible for Input Tax Credit (ITC) under Section 16(1) CGST Act. "
                f"Recipient GSTIN: {merchant.gstin}. Tax invoice for B2B supply."
            )
        else:
            itc_eligible = False
            itc_disclaimer = (
                "B2C / Unregistered recipient supply. Invoiced inclusive of 18% GST. "
                "No Input Tax Credit (ITC) line provided."
            )

        return MonthlyInvoice(
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            billing_period=billing_period_str,
            merchant_id=merchant.merchant_id,
            business_name=merchant.business_name,
            gstin=merchant.gstin,
            is_gst_registered=merchant.is_gst_registered,
            line_items=line_items,
            total_transactions=total_txns,
            total_gross_volume=total_gross,
            total_mdr=total_mdr,
            total_gst=total_gst,
            grand_total=grand_total,
            itc_eligible=itc_eligible,
            itc_disclaimer=itc_disclaimer,
        )

    @staticmethod
    def format_invoice_text(invoice: MonthlyInvoice) -> str:
        """Renders a formatted text invoice."""
        lines = []
        lines.append("=" * 80)
        lines.append(f"TAX INVOICE: {invoice.invoice_number}")
        lines.append(f"Invoice Date: {invoice.invoice_date.strftime('%Y-%m-%d')} | Billing Period: {invoice.billing_period}")
        lines.append("-" * 80)
        lines.append(f"Merchant ID:   {invoice.merchant_id}")
        lines.append(f"Business Name: {invoice.business_name}")
        lines.append(f"GSTIN:         {invoice.gstin or 'UNREGISTERED'}")
        lines.append(f"GST Registered: {'YES' if invoice.is_gst_registered else 'NO'}")
        lines.append(f"ITC Status:     {'ELIGIBLE (B2B)' if invoice.itc_eligible else 'INELIGIBLE (B2C / No ITC Line)'}")
        lines.append("-" * 80)
        lines.append(f"{'Instrument':<20} {'Count':>8} {'Gross Volume (Rs)':>18} {'MDR (Rs)':>12} {'GST (Rs)':>10} {'Total Fee':>10}")
        lines.append("-" * 80)
        for item in invoice.line_items:
            lines.append(
                f"{item.instrument:<20} {item.transaction_count:>8d} {item.gross_volume:>18.2f} "
                f"{item.mdr_amount:>12.2f} {item.gst_amount:>10.2f} {item.total_charged:>10.2f}"
            )
        lines.append("-" * 80)
        lines.append(
            f"{'TOTALS':<20} {invoice.total_transactions:>8d} {invoice.total_gross_volume:>18.2f} "
            f"{invoice.total_mdr:>12.2f} {invoice.total_gst:>10.2f} {invoice.grand_total:>10.2f}"
        )
        lines.append("=" * 80)
        lines.append(f"Compliance Note: {invoice.itc_disclaimer}")
        lines.append("=" * 80)
        return "\n".join(lines)
