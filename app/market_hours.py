"""국내 정규시장 시간 판단(휴일 목록은 별도 갱신 전에는 보수적으로 차단)."""
from __future__ import annotations
from datetime import date, datetime, time, timedelta, timezone
import os

KST = timezone(timedelta(hours=9), name="KST")
MARKET_OPEN, BUY_CUTOFF, MARKET_CLOSE = time(9, 0), time(15, 10), time(15, 30)

def configured_holidays() -> frozenset[date]:
    """`.env`의 MARKET_HOLIDAYS=YYYY-MM-DD,... 를 KRX 휴장일 목록으로 읽습니다."""
    values = (part.strip() for part in os.getenv("MARKET_HOLIDAYS", "").split(","))
    try:
        return frozenset(date.fromisoformat(value) for value in values if value)
    except ValueError as exc:
        raise ValueError("MARKET_HOLIDAYS는 YYYY-MM-DD 형식의 쉼표 목록이어야 합니다.") from exc


def market_phase(now: datetime | None = None, *, holidays: frozenset[date] | None = None) -> str:
    current = (now or datetime.now(KST)).astimezone(KST)
    closed_dates = configured_holidays() if holidays is None else holidays
    if current.weekday() >= 5 or current.date() in closed_dates: return "CLOSED"
    if current.time() < MARKET_OPEN or current.time() >= MARKET_CLOSE: return "CLOSED"
    return "BUY_CLOSED" if current.time() >= BUY_CUTOFF else "OPEN"
