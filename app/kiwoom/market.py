"""Domestic KRX market-data queries for the mock environment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.kiwoom.account import _integer
from app.kiwoom.client import KiwoomReadClient


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

    def quote(self, code: str) -> Quote:
        normalized = code.strip()
        if not (normalized.isdigit() and len(normalized) == 6):
            raise ValueError("Stock code must be exactly six digits, for example 005930.")
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
