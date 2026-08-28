"""읽기 전용 국내주식 모의계좌 조회 기능입니다."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.kiwoom.client import KiwoomReadClient


ACCOUNT_PATH = "/api/dostk/acnt"


@dataclass(frozen=True)
class Holding:
    code: str
    name: str
    quantity: int
    average_price: int
    current_price: int
    evaluation_amount: int
    profit_loss: int


def _integer(value: Any) -> int:
    try:
        return abs(int(str(value or "0").replace(",", "")))
    except (TypeError, ValueError):
        return 0


class AccountService:
    def __init__(self, client: KiwoomReadClient) -> None:
        self._client = client

    def list_accounts(self) -> list[str]:
        payload = self._client.post(path=ACCOUNT_PATH, tr_id="ka00001", body={})
        account = payload.get("acctNo")
        return [str(account)] if account else []

    def portfolio(self) -> tuple[dict[str, int], list[Holding]]:
        payload = self._client.post(
            path=ACCOUNT_PATH,
            tr_id="kt00004",
            body={"qry_tp": "0", "dmst_stex_tp": "KRX"},
        )
        summary = {
            "deposit": _integer(payload.get("entr")),
            "estimated_assets": _integer(payload.get("prsm_dpst_aset_amt")),
            "total_purchase": _integer(payload.get("tot_pur_amt")),
            "total_profit_loss": _integer(payload.get("lspft")),
        }
        holdings = []
        for row in payload.get("stk_acnt_evlt_prst", []):
            if not isinstance(row, dict):
                continue
            holdings.append(
                Holding(
                    code=str(row.get("stk_cd", "")),
                    name=str(row.get("stk_nm", "")),
                    quantity=_integer(row.get("rmnd_qty")),
                    average_price=_integer(row.get("avg_prc")),
                    current_price=_integer(row.get("cur_prc")),
                    evaluation_amount=_integer(row.get("evlt_amt")),
                    profit_loss=_integer(row.get("pl_amt")),
                )
            )
        return summary, holdings
