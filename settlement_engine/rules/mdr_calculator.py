"""
MDR and GST Calculation Engine.
Complies with BR-01 and BR-02.

BR-01 (MDR by Instrument & Amount Slab):
- UPI: 0% up to Rs 2,000; 0.3% above Rs 2,000.
- Debit Card: 0.4% up to Rs 2,000; 0.9% above Rs 2,000.
- Credit Card: 1.8% flat.
- Net Banking: Rs 10 flat.
- Wallet: 2.0% flat.
- International Card: 3.5% + Rs 7 flat.
- GST: 18% on MDR.

BR-02 (MDR Plan Override):
- Merchants on FLAT_PLAN pay 1.5% on every instrument except UPI (UPI keeps standard slab).
- A merchant-specific negotiated rate (if present) beats both.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Tuple
from settlement_engine.models.merchant import Merchant, MDRPlan
from settlement_engine.models.transaction import PaymentInstrument

TWO_PLACES = Decimal("0.01")
GST_RATE = Decimal("0.18")
UPI_SLAB_LIMIT = Decimal("2000.00")
DEBIT_SLAB_LIMIT = Decimal("2000.00")


def quantize_amount(val: Decimal) -> Decimal:
    """Standard banking half-up rounding to 2 decimal places (paise precision)."""
    return val.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def calculate_standard_mdr(instrument: PaymentInstrument, amount: Decimal) -> Decimal:
    """Calculates standard MDR according to BR-01 instrument rules."""
    if instrument == PaymentInstrument.UPI:
        if amount <= UPI_SLAB_LIMIT:
            return Decimal("0.00")
        else:
            return quantize_amount(amount * Decimal("0.003"))  # 0.3%
            
    elif instrument == PaymentInstrument.DEBIT_CARD:
        if amount <= DEBIT_SLAB_LIMIT:
            return quantize_amount(amount * Decimal("0.004"))  # 0.4%
        else:
            return quantize_amount(amount * Decimal("0.009"))  # 0.9%
            
    elif instrument == PaymentInstrument.CREDIT_CARD:
        return quantize_amount(amount * Decimal("0.018"))  # 1.8%
        
    elif instrument == PaymentInstrument.NET_BANKING:
        return quantize_amount(Decimal("10.00"))  # Flat Rs 10
        
    elif instrument == PaymentInstrument.WALLET:
        return quantize_amount(amount * Decimal("0.020"))  # 2.0%
        
    elif instrument == PaymentInstrument.INTERNATIONAL_CARD:
        # 3.5% + Rs 7
        variable_fee = amount * Decimal("0.035")
        return quantize_amount(variable_fee + Decimal("7.00"))
        
    else:
        raise ValueError(f"Unsupported payment instrument: {instrument}")


def calculate_mdr_and_gst(merchant: Merchant, instrument: PaymentInstrument, captured_amount: Decimal) -> Tuple[Decimal, Decimal]:
    """
    Computes (MDR, GST) for a captured transaction amount.
    Implements BR-01 and BR-02 rate hierarchy:
    Negotiated Rate > Flat Plan > Standard Plan.
    """
    if captured_amount <= Decimal("0.00"):
        return Decimal("0.00"), Decimal("0.00")

    # Tier 1: Merchant-specific negotiated rate beats both
    if merchant.negotiated_rate is not None:
        raw_mdr = quantize_amount(captured_amount * merchant.negotiated_rate)
        raw_gst = quantize_amount(raw_mdr * GST_RATE)
        return raw_mdr, raw_gst

    # Tier 2: FLAT_PLAN (1.5% on all instruments EXCEPT UPI)
    if merchant.mdr_plan == MDRPlan.FLAT_PLAN:
        if instrument == PaymentInstrument.UPI:
            raw_mdr = calculate_standard_mdr(PaymentInstrument.UPI, captured_amount)
        else:
            raw_mdr = quantize_amount(captured_amount * Decimal("0.015"))  # 1.5%
        raw_gst = quantize_amount(raw_mdr * GST_RATE)
        return raw_mdr, raw_gst

    # Tier 3: STANDARD plan by instrument slab
    raw_mdr = calculate_standard_mdr(instrument, captured_amount)
    raw_gst = quantize_amount(raw_mdr * GST_RATE)
    return raw_mdr, raw_gst
