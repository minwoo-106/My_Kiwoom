"""국내 정규시장 시간 판단(휴일 목록은 별도 갱신 전에는 보수적으로 차단)."""
from __future__ import annotations
from datetime import datetime, time, timedelta, timezone

KST = timezone(timedelta(hours=9), name="KST")
MARKET_OPEN, BUY_CUTOFF, MARKET_CLOSE = time(9, 0), time(15, 10), time(15, 30)

def market_phase(now: datetime | None = None) -> str:
    current = (now or datetime.now(KST)).astimezone(KST)
    if current.weekday() >= 5: return "CLOSED"
    if current.time() < MARKET_OPEN or current.time() >= MARKET_CLOSE: return "CLOSED"
    return "BUY_CLOSED" if current.time() >= BUY_CUTOFF else "OPEN"
