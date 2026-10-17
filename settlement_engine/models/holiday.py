"""
Holiday and Business Calendar Management.
Complies with BR-04 and BR-07.
"""

from datetime import date, timedelta
from typing import Set


class CalendarService:
    def __init__(self, holidays: Set[date] = None):
        self.holidays: Set[date] = holidays if holidays is not None else set()

    def add_holiday(self, holiday_date: date) -> None:
        self.holidays.add(holiday_date)

    def is_business_day(self, check_date: date) -> bool:
        """
        A business day is Monday to Friday (weekday 0 to 4),
        excluding dates present in the holiday registry.
        """
        # 5 is Saturday, 6 is Sunday
        if check_date.weekday() >= 5:
            return False
        return check_date not in self.holidays

    def next_business_day(self, current_date: date) -> date:
        """Returns the immediate next business day following current_date."""
        target = current_date + timedelta(days=1)
        while not self.is_business_day(target):
            target += timedelta(days=1)
        return target

    def add_business_days(self, start_date: date, n: int) -> date:
        """
        Adds `n` business days to `start_date`.
        If n=1: returns T+1 business day.
        If n=2: returns T+2 business days.
        """
        current = start_date
        added = 0
        while added < n:
            current += timedelta(days=1)
            if self.is_business_day(current):
                added += 1
        return current

    def roll_to_business_day(self, target_date: date) -> date:
        """
        If target_date is a business day, returns it.
        Otherwise rolls forward to the nearest upcoming business day.
        """
        current = target_date
        while not self.is_business_day(current):
            current += timedelta(days=1)
        return current
