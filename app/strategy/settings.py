"""전략 환경설정; 비밀값과 분리되어 Git에 저장해도 안전합니다."""
from __future__ import annotations
import os
from dataclasses import dataclass

DEFAULT_WATCHLIST = ("005930", "000660", "005380", "105560", "004410")

@dataclass(frozen=True)
class TradingSettings:
    watchlist: tuple[str, ...] = DEFAULT_WATCHLIST
    enable_mock_order: bool = False
    order_quantity: int = 1
    market_open: str = "09:00"
    new_buy_cutoff: str = "15:10"
    market_close: str = "15:30"
    market_holidays: tuple[str, ...] = ()
    @classmethod
    def load(cls) -> "TradingSettings":
        raw = os.getenv("WATCHLIST", ",".join(DEFAULT_WATCHLIST))
        symbols = tuple(x.strip() for x in raw.replace("\n", ",").split(",") if x.strip())
        if not symbols or any(not (x.isdigit() and len(x) == 6) for x in symbols): raise ValueError("WATCHLIST는 6자리 종목코드 목록이어야 합니다.")
        holidays = tuple(value.strip() for value in os.getenv("MARKET_HOLIDAYS", "").split(",") if value.strip())
        return cls(watchlist=symbols, enable_mock_order=os.getenv("ENABLE_MOCK_ORDER", "false").lower() == "true", market_holidays=holidays)
