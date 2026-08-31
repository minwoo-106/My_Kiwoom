"""모의투자 환경의 국내 KRX 시세 조회 기능입니다."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.kiwoom.account import _integer
from app.kiwoom.client import KiwoomReadClient
from app.strategy.core import Candle


@dataclass(frozen=True)
class Quote:
    code: str
    name: str
    current_price: int
    change: int
    change_rate: str
    volume: int


class MarketService:
    def __init__(self, client: KiwoomReadClient) -> None:
        self._client = client

    @property
    def client(self) -> KiwoomReadClient:
        """계좌 복구처럼 같은 읽기 전용 세션을 써야 하는 경우의 명시적 접근점입니다."""
        return self._client

    def quote(self, code: str) -> Quote:
        normalized = code.strip()
        if not (normalized.isdigit() and len(normalized) == 6):
            raise ValueError("종목코드는 005930처럼 정확히 여섯 자리 숫자여야 합니다.")
        payload: dict[str, Any] = self._client.post(
            path="/api/dostk/stkinfo", tr_id="ka10001", body={"stk_cd": normalized}
        )
        return Quote(
            code=str(payload.get("stk_cd", normalized)),
            name=str(payload.get("stk_nm", "")),
            current_price=_integer(payload.get("cur_prc")),
            change=_integer(payload.get("pred_pre")),
            change_rate=str(payload.get("flu_rt", "")),
            volume=_integer(payload.get("trde_qty")),
        )

    def completed_15m_candles(self, code: str) -> list[Candle]:
        """키움 공식 ka10080 응답에서 아직 진행 중인 마지막 15분봉을 제외합니다."""
        normalized = code.strip()
        if not (normalized.isdigit() and len(normalized) == 6):
            raise ValueError("종목코드는 005930처럼 정확히 여섯 자리 숫자여야 합니다.")
        payload = self._client.post(path="/api/dostk/chart", tr_id="ka10080", body={"stk_cd": normalized, "tic_scope": "15", "upd_stkpc_tp": "1"})
        rows = payload.get("stk_min_pole_chart_qry", [])
        candles = [Candle(timestamp=str(row.get("cntr_tm", "")), open=float(_integer(row.get("open_pric"))), high=float(_integer(row.get("high_pric"))), low=float(_integer(row.get("low_pric"))), close=float(_integer(row.get("cur_prc"))), volume=_integer(row.get("trde_qty"))) for row in rows if isinstance(row, dict)]
        # API는 최신 순일 수 있으므로 시간 오름차순으로 정렬하며, 마지막 진행 봉은 전략에 넘기지 않습니다.
        candles.sort(key=lambda candle: candle.timestamp)
        return candles[:-1] if len(candles) > 1 else []
