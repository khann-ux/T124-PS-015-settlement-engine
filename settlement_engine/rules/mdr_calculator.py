from decimal import Decimal, ROUND_HALF_UP
from typing import Tuple
from settlement_engine.models.merchant import Merchant, MDRPlan
from settlement_engine.models.transaction import PaymentInstrument

TWO_PLACES = Decimal("0.01")
GST_RATE = Decimal("0.18")
UPI_SLAB_LIMIT = Decimal("2000.00")
DEBIT_SLAB_LIMIT = Decimal("2000.00")


def quantize_amount(val: Decimal) -> Decimal:
    return val.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def calculate_standard_mdr(instrument: PaymentInstrument, amount: Decimal) -> Decimal:
    if instrument == PaymentInstrument.UPI:
        if amount <= UPI_SLAB_LIMIT:
            return Decimal("0.00")
        else:
            return quantize_amount(amount * Decimal("0.003"))

    elif instrument == PaymentInstrument.DEBIT_CARD:
        if amount <= DEBIT_SLAB_LIMIT:
            return quantize_amount(amount * Decimal("0.004"))
        else:
            return quantize_amount(amount * Decimal("0.009"))

    elif instrument == PaymentInstrument.CREDIT_CARD:
        return quantize_amount(amount * Decimal("0.018"))

    elif instrument == PaymentInstrument.NET_BANKING:
        return quantize_amount(Decimal("10.00"))

    elif instrument == PaymentInstrument.WALLET:
        return quantize_amount(amount * Decimal("0.020"))

    elif instrument == PaymentInstrument.INTERNATIONAL_CARD:
        variable_fee = amount * Decimal("0.035")
        return quantize_amount(variable_fee + Decimal("7.00"))

    else:
        raise ValueError(f"Unsupported payment instrument: {instrument}")


def calculate_mdr_and_gst(merchant: Merchant, instrument: PaymentInstrument, captured_amount: Decimal) -> Tuple[Decimal, Decimal]:
    if captured_amount <= Decimal("0.00"):
        return Decimal("0.00"), Decimal("0.00")

    if merchant.negotiated_rate is not None:
        raw_mdr = quantize_amount(captured_amount * merchant.negotiated_rate)
        raw_gst = quantize_amount(raw_mdr * GST_RATE)
        return raw_mdr, raw_gst

    if merchant.mdr_plan == MDRPlan.FLAT_PLAN:
        if instrument == PaymentInstrument.UPI:
            raw_mdr = calculate_standard_mdr(PaymentInstrument.UPI, captured_amount)
        else:
            raw_mdr = quantize_amount(captured_amount * Decimal("0.015"))
        raw_gst = quantize_amount(raw_mdr * GST_RATE)
        return raw_mdr, raw_gst

    raw_mdr = calculate_standard_mdr(instrument, captured_amount)
    raw_gst = quantize_amount(raw_mdr * GST_RATE)
    return raw_mdr, raw_gst
