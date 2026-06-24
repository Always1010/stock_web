"""Date/time utilities for China Standard Time (UTC+8)."""
from datetime import date, datetime, timedelta, timezone

CST = timezone(timedelta(hours=8))


def now_cst() -> datetime:
    """Get current datetime in China Standard Time."""
    return datetime.now(CST)


def today_cst() -> date:
    """Get current date in China Standard Time."""
    return now_cst().date()


def today_str() -> str:
    """Get current date as ISO string in CST."""
    return today_cst().isoformat()


def is_after_3pm() -> bool:
    """Check if current CST time is at or after 15:00."""
    return now_cst().hour >= 15


def format_date(d: date) -> str:
    """Format a date as ISO string."""
    return d.isoformat()
