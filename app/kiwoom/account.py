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


@dataclass(frozen=True)
class OrderFill:
    """공식 ka10076 체결조회에서 정규화한 단일 주문 상태입니다."""

    order_number: str
    code: str
    side: str
    order_quantity: int
    filled_quantity: int
    unfilled_quantity: int
    filled_price: int
    status: str
    order_time: str


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

    def unfilled_symbols(self) -> set[str]:
        """공식 ka10075 미체결 조회; 자동 주문 전 중복 차단에 사용합니다."""
        payload = self._client.post(path=ACCOUNT_PATH, tr_id="ka10075", body={"all_stk_tp": "0", "trde_tp": "0", "stex_tp": "0", "stk_cd": ""})
        return {str(row.get("stk_cd", "")).lstrip("A") for row in payload.get("oso", []) if isinstance(row, dict) and str(row.get("oso_qty", "0")).replace("-", "").isdigit() and int(str(row.get("oso_qty", "0"))) > 0}

    def filled_orders(self, code: str | None = None) -> list[OrderFill]:
        """공식 ka10076 체결요청으로 주문 접수 뒤의 상태를 조회합니다."""
        normalized = (code or "").strip()
        if normalized and not (normalized.isdigit() and len(normalized) == 6):
            raise ValueError("종목코드는 6자리 숫자여야 합니다.")
        payload = self._client.post(
            path=ACCOUNT_PATH,
            tr_id="ka10076",
            body={"qry_tp": "1" if normalized else "0", "sell_tp": "0", "stex_tp": "0", "stk_cd": normalized, "ord_no": ""},
        )
        fills: list[OrderFill] = []
        for row in payload.get("cntr", []):
            if not isinstance(row, dict):
                continue
            fills.append(OrderFill(
                order_number=str(row.get("ord_no", "")),
                code=str(row.get("stk_cd", "")).lstrip("A"),
                side=str(row.get("trde_tp", "")),
                order_quantity=_integer(row.get("ord_qty")),
                filled_quantity=_integer(row.get("cntr_qty")),
                unfilled_quantity=_integer(row.get("oso_qty")),
                filled_price=_integer(row.get("cntr_pric")),
                status=str(row.get("ord_stt", "")),
                order_time=str(row.get("ord_tm", "")),
            ))
        return fills
