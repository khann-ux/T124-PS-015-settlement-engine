"""
Test Suite for Placement Viva Stretch Goals: Marketplace Split Settlement & Instant Payouts.
"""

import pytest
from datetime import date
from decimal import Decimal
from settlement_engine.rules.stretch_goals import (
    MarketplaceSplitEngine,
    InstantSettlementService,
)


class TestStretchGoals:

    def test_marketplace_split_settlement(self, low_risk_merchant):
        # Order amount = Rs 10,000
        # Platform commission = 10% = Rs 1,000
        # Vendor pool = Rs 9,000 split between Vendor A (60%) and Vendor B (40%)
        # Aggregator fee = Rs 180 MDR + Rs 32.40 GST = Rs 212.40 absorbed by platform
        ratios = {
            "VENDOR_A": Decimal("0.60"),
            "VENDOR_B": Decimal("0.40"),
        }

        result = MarketplaceSplitEngine.calculate_split(
            order_id="ORD-MARKET-001",
            marketplace_merchant=low_risk_merchant,
            order_amount=Decimal("10000.00"),
            platform_commission_pct=Decimal("0.10"),
            sub_merchant_ratios=ratios,
            total_mdr=Decimal("180.00"),
            total_gst=Decimal("32.40"),
        )

        assert result.platform_commission_amount == Decimal("1000.00")
        assert result.net_platform_revenue == Decimal("1000.00") - Decimal("212.40")  # 787.60
        assert len(result.sub_merchant_splits) == 2

        # Vendor A: 60% of 9000 = 5400
        vendor_a = next(s for s in result.sub_merchant_splits if s.sub_merchant_id == "VENDOR_A")
        assert vendor_a.net_allocated == Decimal("5400.00")

        # Vendor B: 40% of 9000 = 3600
        vendor_b = next(s for s in result.sub_merchant_splits if s.sub_merchant_id == "VENDOR_B")
        assert vendor_b.net_allocated == Decimal("3600.00")

    def test_instant_settlement_service(self, low_risk_merchant):
        service = InstantSettlementService(default_daily_cap=Decimal("100000.00"))
        req_date = date(2026, 9, 15)

        # 1. Request Rs 50,000 instant payout (0.10% fee = Rs 50.00, GST = Rs 9.00 -> total fee Rs 59.00)
        res1 = service.request_instant_payout(
            merchant=low_risk_merchant,
            request_date=req_date,
            amount=Decimal("50000.00")
        )

        assert res1.status == "APPROVED_DISBURSED"
        assert res1.instant_fee == Decimal("50.00")
        assert res1.gst_on_fee == Decimal("9.00")
        assert res1.total_instant_charge == Decimal("59.00")
        assert res1.disbursed_amount == Decimal("49941.00")
        assert res1.daily_cap_remaining == Decimal("50000.00")

        # 2. Request Rs 60,000 instant payout (exceeds remaining cap of 50,000)
        res2 = service.request_instant_payout(
            merchant=low_risk_merchant,
            request_date=req_date,
            amount=Decimal("60000.00")
        )
        assert res2.status == "REJECTED_CAP_EXCEEDED"
        assert res2.disbursed_amount == Decimal("0.00")
