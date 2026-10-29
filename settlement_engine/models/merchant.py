from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Optional
from datetime import date


class RiskGrade(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

    def worsen(self) -> "RiskGrade":
        if self == RiskGrade.LOW:
            return RiskGrade.MEDIUM
        return RiskGrade.HIGH

    def recover(self) -> "RiskGrade":
        if self == RiskGrade.HIGH:
            return RiskGrade.MEDIUM
        return RiskGrade.LOW


class MDRPlan(str, Enum):
    STANDARD = "STANDARD"
    FLAT_PLAN = "FLAT_PLAN"
    NEGOTIATED = "NEGOTIATED"


@dataclass(frozen=True)
class BankAccount:
    account_number: str
    ifsc_code: str
    bank_name: str
    account_holder: str


@dataclass
class Merchant:
    merchant_id: str
    business_name: str
    mcc: str
    base_risk_grade: RiskGrade
    current_risk_grade: RiskGrade
    mdr_plan: MDRPlan
    bank_account: BankAccount
    gstin: Optional[str] = None
    negotiated_rate: Optional[Decimal] = None

    carried_balance: Decimal = field(default_factory=lambda: Decimal("0.00"))
    last_payout_date: Optional[date] = None
    pending_since_date: Optional[date] = None
    consecutive_clean_days: int = 0

    @property
    def is_gst_registered(self) -> bool:
        return bool(self.gstin and self.gstin.strip())

    @property
    def settlement_cycle_days(self) -> int:
        if self.current_risk_grade == RiskGrade.LOW:
            return 1
        elif self.current_risk_grade == RiskGrade.MEDIUM:
            return 2
        else:
            return 3

    @property
    def reserve_percentage(self) -> Decimal:
        if self.current_risk_grade == RiskGrade.HIGH:
            return Decimal("0.10")
        elif self.current_risk_grade == RiskGrade.MEDIUM:
            return Decimal("0.05")
        return Decimal("0.00")

    @property
    def reserve_holding_days(self) -> int:
        if self.current_risk_grade == RiskGrade.HIGH:
            return 90
        elif self.current_risk_grade == RiskGrade.MEDIUM:
            return 45
        return 0
