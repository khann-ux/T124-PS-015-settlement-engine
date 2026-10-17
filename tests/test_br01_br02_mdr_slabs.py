"""
Test Suite for BR-01 (MDR by Instrument and Amount Slab) and BR-02 (MDR Plan Overrides).
"""

import pytest
from decimal import Decimal
from settlement_engine.models.merchant import Merchant, RiskGrade, MDRPlan, BankAccount
from settlement_engine.models.transaction import PaymentInstrument
from settlement_engine.rules.mdr_calculator import (
    calculate_standard_mdr,
    calculate_mdr_and_gst,
)


class TestBR01AndBR02MDRCalculator:

    # -------------------------------------------------------------------------
    # BR-01: Standard MDR by Instrument & Slab
    # -------------------------------------------------------------------------
    def test_upi_slabs(self):
        # UPI <= Rs 2000 -> 0%
        assert calculate_standard_mdr(PaymentInstrument.UPI, Decimal("500.00")) == Decimal("0.00")
        assert calculate_standard_mdr(PaymentInstrument.UPI, Decimal("2000.00")) == Decimal("0.00")

        # UPI > Rs 2000 -> 0.3%
        # 3000 * 0.003 = 9.00
        assert calculate_standard_mdr(PaymentInstrument.UPI, Decimal("3000.00")) == Decimal("9.00")
        # 10000 * 0.003 = 30.00
        assert calculate_standard_mdr(PaymentInstrument.UPI, Decimal("10000.00")) == Decimal("30.00")

    def test_debit_card_slabs(self):
        # Debit Card <= Rs 2000 -> 0.4%
        # 1000 * 0.004 = 4.00
        assert calculate_standard_mdr(PaymentInstrument.DEBIT_CARD, Decimal("1000.00")) == Decimal("4.00")
        # 2000 * 0.004 = 8.00
        assert calculate_standard_mdr(PaymentInstrument.DEBIT_CARD, Decimal("2000.00")) == Decimal("8.00")

        # Debit Card > Rs 2000 -> 0.9%
        # 2500 * 0.009 = 22.50
        assert calculate_standard_mdr(PaymentInstrument.DEBIT_CARD, Decimal("2500.00")) == Decimal("22.50")
        # 5000 * 0.009 = 45.00
        assert calculate_standard_mdr(PaymentInstrument.DEBIT_CARD, Decimal("5000.00")) == Decimal("45.00")

    def test_credit_card_rate(self):
        # Credit Card 1.8% flat
        # 5000 * 0.018 = 90.00
        assert calculate_standard_mdr(PaymentInstrument.CREDIT_CARD, Decimal("5000.00")) == Decimal("90.00")
        # 1000 * 0.018 = 18.00
        assert calculate_standard_mdr(PaymentInstrument.CREDIT_CARD, Decimal("1000.00")) == Decimal("18.00")

    def test_net_banking_flat_fee(self):
        # Net Banking Rs 10 flat regardless of amount
        assert calculate_standard_mdr(PaymentInstrument.NET_BANKING, Decimal("250.00")) == Decimal("10.00")
        assert calculate_standard_mdr(PaymentInstrument.NET_BANKING, Decimal("50000.00")) == Decimal("10.00")

    def test_wallet_rate(self):
        # Wallet 2.0% flat
        # 2000 * 0.02 = 40.00
        assert calculate_standard_mdr(PaymentInstrument.WALLET, Decimal("2000.00")) == Decimal("40.00")

    def test_international_card_rate(self):
        # International 3.5% + Rs 7
        # 10000 * 0.035 + 7 = 350 + 7 = 357.00
        assert calculate_standard_mdr(PaymentInstrument.INTERNATIONAL_CARD, Decimal("10000.00")) == Decimal("357.00")
        # 1000 * 0.035 + 7 = 35 + 7 = 42.00
        assert calculate_standard_mdr(PaymentInstrument.INTERNATIONAL_CARD, Decimal("1000.00")) == Decimal("42.00")

    def test_gst_rate_18_percent(self, low_risk_merchant):
        # Credit card Rs 10,000 -> MDR = 180.00, GST = 18% of 180 = 32.40
        mdr, gst = calculate_mdr_and_gst(low_risk_merchant, PaymentInstrument.CREDIT_CARD, Decimal("10000.00"))
        assert mdr == Decimal("180.00")
        assert gst == Decimal("32.40")

    # -------------------------------------------------------------------------
    # BR-02: MDR Plan Overrides
    # -------------------------------------------------------------------------
    def test_flat_plan_override(self, flat_plan_merchant):
        # FLAT_PLAN: 1.5% on every instrument EXCEPT UPI
        # Credit Card: 10,000 * 1.5% = 150.00 (standard was 180.00)
        mdr_cc, gst_cc = calculate_mdr_and_gst(flat_plan_merchant, PaymentInstrument.CREDIT_CARD, Decimal("10000.00"))
        assert mdr_cc == Decimal("150.00")
        assert gst_cc == Decimal("27.00")

        # Debit Card: 10,000 * 1.5% = 150.00 (standard was 90.00)
        mdr_dc, _ = calculate_mdr_and_gst(flat_plan_merchant, PaymentInstrument.DEBIT_CARD, Decimal("10000.00"))
        assert mdr_dc == Decimal("150.00")

        # UPI exception on FLAT_PLAN: must retain standard UPI rules!
        # UPI <= 2000 -> 0%
        mdr_upi_small, _ = calculate_mdr_and_gst(flat_plan_merchant, PaymentInstrument.UPI, Decimal("1500.00"))
        assert mdr_upi_small == Decimal("0.00")
        # UPI > 2000 -> 0.3%
        mdr_upi_large, _ = calculate_mdr_and_gst(flat_plan_merchant, PaymentInstrument.UPI, Decimal("5000.00"))
        assert mdr_upi_large == Decimal("15.00")

    def test_negotiated_rate_beats_all(self, negotiated_merchant):
        # Negotiated rate = 1.20% (0.0120)
        # Beats both standard and flat plan across instruments
        # 10,000 * 1.2% = 120.00
        mdr_cc, gst_cc = calculate_mdr_and_gst(negotiated_merchant, PaymentInstrument.CREDIT_CARD, Decimal("10000.00"))
        assert mdr_cc == Decimal("120.00")
        assert gst_cc == Decimal("21.60")

        mdr_dc, _ = calculate_mdr_and_gst(negotiated_merchant, PaymentInstrument.DEBIT_CARD, Decimal("10000.00"))
        assert mdr_dc == Decimal("120.00")
