"""Settlement rules. Pure functions, no network."""
import math
from datetime import datetime, timedelta, timezone

def kalshi_taker_fee(contracts: int, price: float, rate: float = 0.07) -> float:
    """round up to next cent of rate*C*P*(1-P)."""
    raw = rate * contracts * price * (1 - price)
    return math.ceil(round(raw * 100, 9)) / 100

def lst_day_window_utc(date_str: str, lst_offset_hours: int):
    """UTC [start, end) of the local-STANDARD-time calendar day (no DST shift)."""
    d = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    start = d - timedelta(hours=lst_offset_hours)
    return start, start + timedelta(days=1)

def c_to_f_whole(c: float) -> int:
    return int(round(c * 9 / 5 + 32))
