"""DRY RUN 멀티종목 전략 실행 어댑터. 주문 호출을 포함하지 않습니다."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from time import sleep
from app.kiwoom.market import MarketService
from app.kiwoom.account import AccountService
from app.market_hours import market_phase
from app.risk.manager import RiskManager
from app.storage.sqlite import TradingStore
from app.strategy.core import Decision, StrategyStatus, SymbolState, TrendPullbackV1
from app.strategy.settings import TradingSettings
from app.kiwoom.orders import AutoMockOrderService

@dataclass(frozen=True)
class SymbolResult:
    symbol: str
    decision: Decision
    completed_bar_price: float | None = None
    market_phase: str = "CLOSED"

class DryRunStrategyRunner:
    def __init__(self, market: MarketService, settings: TradingSettings, store: TradingStore, strategy: TrendPullbackV1 | None = None, risk: RiskManager | None = None, order_service: AutoMockOrderService | None = None) -> None:
        self.market, self.settings, self.store = market, settings, store
        self.strategy, self.risk = strategy or TrendPullbackV1(), risk or RiskManager()
        self.order_service = order_service
        self.states = {symbol: SymbolState(symbol) for symbol in settings.watchlist}
        self.estimated_assets: int | None = None
        self.last_reconcile_error: str | None = None
        self._trading_date = datetime.now().date()
    def restore_from_account(self) -> None:
        account = AccountService(self.market.client)
        summary, holdings = account.portfolio()
        self.estimated_assets = summary["estimated_assets"]
        pending = account.unfilled_symbols()
        for holding in holdings:
            symbol = holding.code.lstrip("A")
            if symbol in self.states:
                state=self.states[symbol]; state.holding=True; state.quantity=holding.quantity; state.average_price=holding.average_price
                previous = self.store.last_filled_buy(symbol)
                if previous:
                    state.stop_price, state.target_price = previous.stop_price, previous.target_price
        for symbol in pending:
            if symbol in self.states: self.states[symbol].order_pending=True

    def reconcile_orders(self) -> None:
        """기록된 미결 주문을 공식 체결 조회와 대조합니다. 재주문은 절대 하지 않습니다."""
        pending = {order.order_number: order for order in self.store.pending_orders()}
        if not pending:
            return
        broker_orders = {fill.order_number: fill for fill in AccountService(self.market.client).filled_orders()}
        now = datetime.now().isoformat(timespec="seconds")
        for number, recorded in pending.items():
            fill = broker_orders.get(number)
            if fill is None:
                continue
            status = "FILLED" if fill.filled_quantity >= recorded.quantity and fill.unfilled_quantity == 0 else "PARTIAL" if fill.filled_quantity else "SUBMITTED"
            self.store.update_order(order_number=number, status=status, filled_quantity=fill.filled_quantity, filled_price=fill.filled_price, updated_at=now)
            state = self.states.get(recorded.symbol)
            if state is None:
                continue
            state.order_pending = status != "FILLED"
            if status != "FILLED":
                continue
            if recorded.side == "BUY":
                state.holding, state.quantity, state.average_price = True, fill.filled_quantity, fill.filled_price
                state.stop_price, state.target_price = recorded.stop_price, recorded.target_price
                state.entries_today += 1
                self.store.record_trade(timestamp=now, symbol=recorded.symbol, side="BUY", price=fill.filled_price, quantity=fill.filled_quantity, realized_profit=0)
            else:
                realized = int((fill.filled_price - (state.average_price or fill.filled_price)) * fill.filled_quantity)
                self.store.record_trade(timestamp=now, symbol=recorded.symbol, side="SELL", price=fill.filled_price, quantity=fill.filled_quantity, realized_profit=realized)
                state.holding, state.quantity, state.average_price = False, 0, None
                state.stop_price, state.target_price = None, None
                state.cooldown_remaining = self.strategy.config.reentry_cooldown_bars

    def _submit_signal(self, symbol: str, state: SymbolState, decision: Decision) -> Decision:
        if self.order_service is None or decision.signal not in {"BUY", "SELL"}:
            return decision
        submitted = self.order_service.buy_market(code=symbol, quantity=self.settings.order_quantity) if decision.signal == "BUY" else self.order_service.sell_market(code=symbol, quantity=self.settings.order_quantity)
        now = datetime.now().isoformat(timespec="seconds")
        self.store.record_order(order_number=submitted.order_number, timestamp=now, symbol=symbol, side=decision.signal, quantity=self.settings.order_quantity, stop_price=decision.stop_price if decision.signal == "BUY" else None, target_price=decision.target_price if decision.signal == "BUY" else None)
        state.order_pending = True
        return Decision(StrategyStatus.ORDER_PENDING, f"모의 주문 접수 {submitted.order_number}: 체결 확인 대기", decision.signal, decision.score, decision.ema_fast, decision.ema_slow, decision.rsi, decision.atr, decision.stop_price, decision.target_price)
    def run_once(self) -> list[SymbolResult]:
        today_date = datetime.now().date()
        if today_date != self._trading_date:
            # 일일 진입 한도는 새 거래일에만 초기화합니다. 보유·미체결 상태는 유지합니다.
            for state in self.states.values():
                state.entries_today = 0
            self._trading_date = today_date
        phase = market_phase(); results=[]
        self.last_reconcile_error = None
        try:
            self.reconcile_orders()
        except Exception as exc:
            # 상태를 알 수 없는 상황에서 신규 주문을 만드는 것보다 한 주기를 건너뛰는 편이 안전합니다.
            self.last_reconcile_error = str(exc)
        if phase == "CLOSED":
            for symbol, state in self.states.items():
                decision = Decision(StrategyStatus.WAIT, "장 마감: 다음 개장 전까지 분석 대기")
                state.status, state.reason = decision.status, decision.reason
                results.append(SymbolResult(symbol, decision, market_phase=phase))
            return results
        for index, (symbol, state) in enumerate(self.states.items()):
            if index:
                # 키움 모의투자는 동일 국내 조회 TR을 초당 1회로 제한합니다.
                sleep(1.05)
            try:
                candles = self.market.completed_15m_candles(symbol)
                completed_price = candles[-1].close if candles else None
                decision = self.strategy.evaluate(candles, state)
                if decision.signal == "BUY":
                    today = datetime.now().strftime("%Y-%m-%d")
                    realized = self.store.today_realized_profit(today)
                    daily_loss_pct = (realized / self.estimated_assets * 100) if self.estimated_assets else 0.0
                    reason = self.risk.buy_block_reason(state, open_positions=sum(s.holding for s in self.states.values()), daily_entries=self.store.today_entries(today), consecutive_losses=self.store.consecutive_losses(), daily_loss_pct=daily_loss_pct, api_ok=self.last_reconcile_error is None, market_open=phase == "OPEN")
                    if reason: decision = Decision(StrategyStatus.RISK_BLOCKED, reason, ema_fast=decision.ema_fast, ema_slow=decision.ema_slow, rsi=decision.rsi, atr=decision.atr)
                if self.last_reconcile_error is None:
                    decision = self._submit_signal(symbol, state, decision)
                state.status, state.reason = decision.status, decision.reason
                self.store.record_signal(timestamp=datetime.now().isoformat(timespec="seconds"), symbol=symbol, strategy="Trend Pullback V1 Multi", state=decision.status, signal=decision.signal, score=decision.score, price=None, ema20=decision.ema_fast, ema60=decision.ema_slow, rsi=decision.rsi, atr=decision.atr, reason=decision.reason, mock_order_enabled=False)
            except Exception as exc:
                decision = Decision(StrategyStatus.ERROR, str(exc)); state.status, state.reason = decision.status, decision.reason
                completed_price = None
            results.append(SymbolResult(symbol, decision, completed_price, phase))
        return results

    def run_forever(self, interval_seconds: float, on_cycle=None) -> None:
        """장중에는 반복 분석하고, 장외에는 주문 없이 대기합니다."""
        while True:
            results = self.run_once()
            if on_cycle: on_cycle(results)
            sleep(interval_seconds)
