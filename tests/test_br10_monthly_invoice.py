"""
Test Suite for BR-10 (Monthly MDR Invoicing, GST/ITC Rules, and Text Rendering).
"""

import pytest
from datetime import datetime, date
from decimal import Decimal
from settlement_engine.models.transaction import Transaction, PaymentInstrument
from settlement_engine.rules.invoice_generator import InvoiceGenerator


class TestBR10MonthlyInvoice:

    def test_gst_registered_merchant_invoice(self, low_risk_merchant):
        # Merchant has gstin="27AAACA1234A1Z5"
        captures = [
            Transaction(
                txn_id="TXN-INV-1",
                merchant_id=low_risk_merchant.merchant_id,
                instrument=PaymentInstrument.CREDIT_CARD,
                authorized_amount=Decimal("10000.00"),
                auth_timestamp=datetime(2026, 9, 10, 10, 0),
                captured_amount=Decimal("10000.00"),
                capture_timestamp=datetime(2026, 9, 10, 12, 0),
                mdr_amount=Decimal("180.00"),
                gst_amount=Decimal("32.40"),
            ),
            Transaction(
                txn_id="TXN-INV-2",
                merchant_id=low_risk_merchant.merchant_id,
                instrument=PaymentInstrument.NET_BANKING,
                authorized_amount=Decimal("5000.00"),
                auth_timestamp=datetime(2026, 9, 15, 10, 0),
                captured_amount=Decimal("5000.00"),
                capture_timestamp=datetime(2026, 9, 15, 12, 0),
                mdr_amount=Decimal("10.00"),
                gst_amount=Decimal("1.80"),
            )
        ]

        invoice = InvoiceGenerator.generate_monthly_invoice(
            merchant=low_risk_merchant,
            billing_year=2026,
            billing_month=9,
            month_captures=captures
        )

        assert invoice.invoice_date == date(2026, 10, 1)
        assert invoice.billing_period == "2026-09"
        assert invoice.total_transactions == 2
        assert invoice.total_gross_volume == Decimal("15000.00")
        assert invoice.total_mdr == Decimal("190.00")
        assert invoice.total_gst == Decimal("34.20")
        assert invoice.grand_total == Decimal("224.20")
        assert invoice.is_gst_registered is True
        assert invoice.itc_eligible is True
        assert "Section 16(1)" in invoice.itc_disclaimer

        text_rep = InvoiceGenerator.format_invoice_text(invoice)
        assert "TAX INVOICE" in text_rep
        assert "ELIGIBLE (B2B)" in text_rep

    def test_unregistered_merchant_invoice(self, unregistered_merchant):
        captures = [
            Transaction(
                txn_id="TXN-INV-UNREG",
                merchant_id=unregistered_merchant.merchant_id,
                instrument=PaymentInstrument.WALLET,
                authorized_amount=Decimal("5000.00"),
                auth_timestamp=datetime(2026, 9, 10, 10, 0),
                captured_amount=Decimal("5000.00"),
                capture_timestamp=datetime(2026, 9, 10, 12, 0),
                mdr_amount=Decimal("100.00"),
                gst_amount=Decimal("18.00"),
            )
        ]

        invoice = InvoiceGenerator.generate_monthly_invoice(
            merchant=unregistered_merchant,
            billing_year=2026,
            billing_month=9,
            month_captures=captures
        )

        assert invoice.is_gst_registered is False
        assert invoice.itc_eligible is False
        assert "No Input Tax Credit (ITC)" in invoice.itc_disclaimer

        text_rep = InvoiceGenerator.format_invoice_text(invoice)
        assert "INELIGIBLE (B2C / No ITC Line)" in text_rep
