"""
Settlement Cycle and Cut-off Computation Engine.
Complies with BR-04.

BR-04:
- LOW risk: T+1 business days
- MEDIUM risk: T+2 business days
- HIGH risk: T+3 business days
- Cut-off Rule: Captures AFTER 23:00:00 count as next day (T becomes T+1).
- Edge Case: Capture at 23:00:00 exactly counts as same day; 23:00:01 counts as next day.
- Weekends (Sat/Sun) and declared bank holidays are skipped.
"""

from datetime import datetime, date, time, timedelta
from settlement_engine.models.merchant import RiskGrade
from settlement_engine.models.holiday import CalendarService

CUTOFF_TIME = time(23, 0, 0)


def get_effective_capture_date(capture_timestamp: datetime) -> date:
    """
    Computes the effective capture date considering the 23:00 cut-off.
    Captures AFTER 23:00:00 are shifted to the next calendar date.
    Capture at 23:00:00 exactly is retained on the same day.
    """
    if capture_timestamp.time() > CUTOFF_TIME:
        return capture_timestamp.date() + timedelta(days=1)
    return capture_timestamp.date()


def compute_settlement_date(
    capture_timestamp: datetime,
    risk_grade: RiskGrade,
    calendar: CalendarService
) -> date:
    """
    Calculates the exact date when the capture is eligible for merchant settlement.
    """
    effective_date = get_effective_capture_date(capture_timestamp)
    
    if risk_grade == RiskGrade.LOW:
        cycle_days = 1
    elif risk_grade == RiskGrade.MEDIUM:
        cycle_days = 2
    elif risk_grade == RiskGrade.HIGH:
        cycle_days = 3
    else:
        cycle_days = 1

    return calendar.add_business_days(effective_date, cycle_days)
