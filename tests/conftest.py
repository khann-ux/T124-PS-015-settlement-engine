import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from datetime import date, datetime
from decimal import Decimal
from settlement_engine.models.merchant import Merchant, RiskGrade, MDRPlan, BankAccount
from settlement_engine.models.holiday import CalendarService


@pytest.fixture
def bank_account():
    return BankAccount(
        account_number="1234567890",
        ifsc_code="HDFC0001234",
        bank_name="HDFC Bank",
        account_holder="Test Merchant Pvt Ltd",
    )


@pytest.fixture
def low_risk_merchant(bank_account):
    return Merchant(
        merchant_id="M_LOW",
        business_name="Low Risk Mart",
        mcc="5411",
        base_risk_grade=RiskGrade.LOW,
        current_risk_grade=RiskGrade.LOW,
        mdr_plan=MDRPlan.STANDARD,
        bank_account=bank_account,
        gstin="27AAACA1234A1Z5",
    )


@pytest.fixture
def medium_risk_merchant(bank_account):
    return Merchant(
        merchant_id="M_MED",
        business_name="Medium Risk Tech",
        mcc="5732",
        base_risk_grade=RiskGrade.MEDIUM,
        current_risk_grade=RiskGrade.MEDIUM,
        mdr_plan=MDRPlan.STANDARD,
        bank_account=bank_account,
        gstin="27AAACB5678B1Z2",
    )


@pytest.fixture
def high_risk_merchant(bank_account):
    return Merchant(
        merchant_id="M_HIGH",
        business_name="High Risk Gaming",
        mcc="7995",
        base_risk_grade=RiskGrade.HIGH,
        current_risk_grade=RiskGrade.HIGH,
        mdr_plan=MDRPlan.STANDARD,
        bank_account=bank_account,
        gstin="27AAACC9988C1Z9",
    )


@pytest.fixture
def flat_plan_merchant(bank_account):
    return Merchant(
        merchant_id="M_FLAT",
        business_name="Flat Plan Retailer",
        mcc="5311",
        base_risk_grade=RiskGrade.LOW,
        current_risk_grade=RiskGrade.LOW,
        mdr_plan=MDRPlan.FLAT_PLAN,
        bank_account=bank_account,
        gstin="27AAACD1122D1Z1",
    )


@pytest.fixture
def negotiated_merchant(bank_account):
    return Merchant(
        merchant_id="M_NEG",
        business_name="Negotiated Rate Enterprise",
        mcc="5311",
        base_risk_grade=RiskGrade.LOW,
        current_risk_grade=RiskGrade.LOW,
        mdr_plan=MDRPlan.NEGOTIATED,
        negotiated_rate=Decimal("0.0120"),
        bank_account=bank_account,
        gstin="27AAACE3344E1Z3",
    )


@pytest.fixture
def unregistered_merchant(bank_account):
    return Merchant(
        merchant_id="M_UNREG",
        business_name="Small Unregistered Shop",
        mcc="5499",
        base_risk_grade=RiskGrade.LOW,
        current_risk_grade=RiskGrade.LOW,
        mdr_plan=MDRPlan.STANDARD,
        bank_account=bank_account,
        gstin=None,
    )


@pytest.fixture
def calendar():
    cal = CalendarService()
    cal.add_holiday(date(2026, 9, 4))
    cal.add_holiday(date(2026, 10, 2))
    return cal
