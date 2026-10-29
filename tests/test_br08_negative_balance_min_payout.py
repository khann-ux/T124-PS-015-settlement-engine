import pytest
from datetime import date, timedelta, datetime
from decimal import Decimal
from settlement_engine.models.transaction import Transaction, PaymentInstrument
from settlement_engine.rules.chargeback_engine import QueuedChargeback, CHARGEBACK_FEE
from settlement_engine.rules.payout_calculator import PayoutCalculator


class TestBR08NegativeBalanceAndMinimumPayout:

    def test_clearing_negative_balance_with_subsequent_captures(self, low_risk_merchant, calendar):
        settle_day_1 = date(2026, 9, 10)
        low_risk_merchant.carried_balance = Decimal("-500.00")

        t_capture = Transaction(
            txn_id="TXN-REC-1",
            merchant_id=low_risk_merchant.merchant_id,
            instrument=PaymentInstrument.UPI,
            authorized_amount=Decimal("2000.00"),
            auth_timestamp=datetime(2026, 9, 9, 10, 0),
            captured_amount=Decimal("2000.00"),
            capture_timestamp=datetime(2026, 9, 9, 11, 0),
            mdr_amount=Decimal("0.00"),
            gst_amount=Decimal("0.00"),
        )

        settle_day_2 = date(2026, 9, 11)
        payout_rec, _ = PayoutCalculator.compute_daily_merchant_payout(
            merchant=low_risk_merchant,
            settlement_date=settle_day_2,
            eligible_captures=[t_capture],
            eligible_refunds=[],
            eligible_chargebacks=[],
            eligible_representments=[],
            active_reserves=[],
            calendar=calendar,
        )

        assert payout_rec.opening_balance == Decimal("-500.00")
        assert payout_rec.calculated_settlement == Decimal("1500.00")
        assert payout_rec.actual_payout == Decimal("1500.00")
        assert payout_rec.closing_balance == Decimal("0.00")
        assert low_risk_merchant.carried_balance == Decimal("0.00")
        assert payout_rec.payout_status == "SETTLED"

    def test_cumulative_balance_below_100_carried_forward(self, low_risk_merchant, calendar):
        day_1 = date(2026, 9, 1)
        t_small = Transaction(
            txn_id="TXN-SMALL-1",
            merchant_id=low_risk_merchant.merchant_id,
            instrument=PaymentInstrument.UPI,
            authorized_amount=Decimal("50.00"),
            auth_timestamp=datetime(2026, 8, 31, 10, 0),
            captured_amount=Decimal("50.00"),
            capture_timestamp=datetime(2026, 8, 31, 11, 0),
            mdr_amount=Decimal("0.00"),
            gst_amount=Decimal("0.00"),
        )

        payout_d1, _ = PayoutCalculator.compute_daily_merchant_payout(
            merchant=low_risk_merchant,
            settlement_date=day_1,
            eligible_captures=[t_small],
            eligible_refunds=[],
            eligible_chargebacks=[],
            eligible_representments=[],
            active_reserves=[],
            calendar=calendar,
        )

        assert payout_d1.actual_payout == Decimal("0.00")
        assert payout_d1.closing_balance == Decimal("50.00")
        assert payout_d1.payout_status == "CARRIED_BELOW_MINIMUM"
        assert low_risk_merchant.carried_balance == Decimal("50.00")

        t_small_2 = Transaction(
            txn_id="TXN-SMALL-2",
            merchant_id=low_risk_merchant.merchant_id,
            instrument=PaymentInstrument.UPI,
            authorized_amount=Decimal("60.00"),
            auth_timestamp=datetime(2026, 9, 1, 10, 0),
            captured_amount=Decimal("60.00"),
            capture_timestamp=datetime(2026, 9, 1, 11, 0),
            mdr_amount=Decimal("0.00"),
            gst_amount=Decimal("0.00"),
        )
        day_2 = date(2026, 9, 2)
        payout_d2, _ = PayoutCalculator.compute_daily_merchant_payout(
            merchant=low_risk_merchant,
            settlement_date=day_2,
            eligible_captures=[t_small_2],
            eligible_refunds=[],
            eligible_chargebacks=[],
            eligible_representments=[],
            active_reserves=[],
            calendar=calendar,
        )

        assert payout_d2.opening_balance == Decimal("50.00")
        assert payout_d2.calculated_settlement == Decimal("110.00")
        assert payout_d2.actual_payout == Decimal("110.00")
        assert payout_d2.closing_balance == Decimal("0.00")
        assert low_risk_merchant.carried_balance == Decimal("0.00")
        assert payout_d2.payout_status == "SETTLED"
