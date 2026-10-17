"""
Stretch Goals: Marketplace Split Settlement & Instant Payouts.
Provides advanced capabilities for extra credit during evaluation and viva.

Feature 1: Marketplace Split Settlement
- Automatically splits captured order volume between marketplace platform (commission)
  and multiple sub-merchants.
- Aggregator MDR & GST are deducted from the commission or prorated.

Feature 2: Instant Settlement Option
- Disburses captured funds on the same day (T+0) instead of waiting for T+N.
- Charges a 0.10% instant processing fee (+ 18% GST).
- Enforces a configurable daily volume cap per merchant (e.g., Rs 5,00,000/day).
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import List, Dict
from settlement_engine.models.merchant import Merchant
from settlement_engine.rules.mdr_calculator import quantize_amount, GST_RATE

INSTANT_SETTLEMENT_FEE_RATE = Decimal("0.0010")  # 0.10%


@dataclass(frozen=True)
class SplitShare:
    sub_merchant_id: str
    share_ratio: Decimal  # e.g., Decimal("0.85") for 85%
    gross_allocated: Decimal
    net_allocated: Decimal


@dataclass
class MarketplaceSplitResult:
    order_id: str
    marketplace_merchant_id: str
    total_order_amount: Decimal
    platform_commission_amount: Decimal
    total_mdr: Decimal
    total_gst: Decimal
    net_platform_revenue: Decimal
    sub_merchant_splits: List[SplitShare]


class MarketplaceSplitEngine:
    @staticmethod
    def calculate_split(
        order_id: str,
        marketplace_merchant: Merchant,
        order_amount: Decimal,
        platform_commission_pct: Decimal,  # e.g. Decimal("0.10") for 10%
        sub_merchant_ratios: Dict[str, Decimal],  # sub_merchant_id -> ratio of remaining (sums to 1.0)
        total_mdr: Decimal,
        total_gst: Decimal
    ) -> MarketplaceSplitResult:
        """
        Calculates marketplace split settlement with commission netting.
        """
        commission = quantize_amount(order_amount * platform_commission_pct)
        merchant_pool = order_amount - commission

        # In BFSI marketplace models, the platform absorbs the MDR+GST from its commission
        net_platform_revenue = commission - (total_mdr + total_gst)

        splits: List[SplitShare] = []
        for sub_id, ratio in sub_merchant_ratios.items():
            sub_gross = quantize_amount(merchant_pool * ratio)
            splits.append(
                SplitShare(
                    sub_merchant_id=sub_id,
                    share_ratio=ratio,
                    gross_allocated=sub_gross,
                    net_allocated=sub_gross,  # clean vendor payout
                )
            )

        return MarketplaceSplitResult(
            order_id=order_id,
            marketplace_merchant_id=marketplace_merchant.merchant_id,
            total_order_amount=order_amount,
            platform_commission_amount=commission,
            total_mdr=total_mdr,
            total_gst=total_gst,
            net_platform_revenue=net_platform_revenue,
            sub_merchant_splits=splits,
        )


@dataclass
class InstantPayoutResult:
    merchant_id: str
    requested_amount: Decimal
    instant_fee: Decimal  # 0.10%
    gst_on_fee: Decimal  # 18% of instant fee
    total_instant_charge: Decimal
    disbursed_amount: Decimal
    daily_cap_remaining: Decimal
    status: str
    message: str


class InstantSettlementService:
    def __init__(self, default_daily_cap: Decimal = Decimal("500000.00")):
        self.default_daily_cap = default_daily_cap
        self.daily_utilized: Dict[str, Dict[date, Decimal]] = {}

    def request_instant_payout(
        self,
        merchant: Merchant,
        request_date: date,
        amount: Decimal
    ) -> InstantPayoutResult:
        """
        Executes instant settlement on-demand for eligible merchants.
        Fee: 0.10% + 18% GST.
        Enforces daily limit.
        """
        if merchant.merchant_id not in self.daily_utilized:
            self.daily_utilized[merchant.merchant_id] = {}

        utilized_today = self.daily_utilized[merchant.merchant_id].get(request_date, Decimal("0.00"))
        remaining_cap = max(Decimal("0.00"), self.default_daily_cap - utilized_today)

        if amount > remaining_cap:
            return InstantPayoutResult(
                merchant_id=merchant.merchant_id,
                requested_amount=amount,
                instant_fee=Decimal("0.00"),
                gst_on_fee=Decimal("0.00"),
                total_instant_charge=Decimal("0.00"),
                disbursed_amount=Decimal("0.00"),
                daily_cap_remaining=remaining_cap,
                status="REJECTED_CAP_EXCEEDED",
                message=f"Requested Rs {amount} exceeds remaining daily instant cap of Rs {remaining_cap}.",
            )

        # Compute 0.1% instant fee + 18% GST
        instant_fee = quantize_amount(amount * INSTANT_SETTLEMENT_FEE_RATE)
        gst_on_fee = quantize_amount(instant_fee * GST_RATE)
        total_fee = instant_fee + gst_on_fee
        disbursed = amount - total_fee

        self.daily_utilized[merchant.merchant_id][request_date] = utilized_today + amount
        new_remaining = self.default_daily_cap - (utilized_today + amount)

        return InstantPayoutResult(
            merchant_id=merchant.merchant_id,
            requested_amount=amount,
            instant_fee=instant_fee,
            gst_on_fee=gst_on_fee,
            total_instant_charge=total_fee,
            disbursed_amount=disbursed,
            daily_cap_remaining=new_remaining,
            status="APPROVED_DISBURSED",
            message=f"Instant settlement of Rs {disbursed} approved and queued for IMPS/RTGS transfer.",
        )
