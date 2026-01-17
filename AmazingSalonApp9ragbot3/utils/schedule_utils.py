
from datetime import datetime, timedelta

def generate_recurring_schedule(start_date, end_date, days, start_time, end_time):
    """Generate recurring schedule between dates for specified days"""
    schedule = {}
    current = start_date
    while current <= end_date:
        if current.strftime('%A') in days:
            schedule[current.strftime('%Y-%m-%d')] = {
                'start': start_time,
                'end': end_time
            }
        current += timedelta(days=1)
    return schedule
