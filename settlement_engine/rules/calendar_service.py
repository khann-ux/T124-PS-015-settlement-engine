from datetime import datetime, date, time, timedelta
from settlement_engine.models.merchant import RiskGrade
from settlement_engine.models.holiday import CalendarService

CUTOFF_TIME = time(23, 0, 0)


def get_effective_capture_date(capture_timestamp: datetime) -> date:
    if capture_timestamp.time() > CUTOFF_TIME:
        return capture_timestamp.date() + timedelta(days=1)
    return capture_timestamp.date()


def compute_settlement_date(
    capture_timestamp: datetime,
    risk_grade: RiskGrade,
    calendar: CalendarService
) -> date:
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
