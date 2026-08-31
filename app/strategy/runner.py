"""DRY RUN 멀티종목 전략 실행 어댑터. 주문 호출을 포함하지 않습니다."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from time import sleep
from app.kiwoom.market import MarketService
from app.market_hours import market_phase
from app.risk.manager import RiskManager
from app.storage.sqlite import TradingStore
from app.strategy.core import Decision, StrategyStatus, SymbolState, TrendPullbackV1
from app.strategy.settings import TradingSettings

@dataclass(frozen=True)
class SymbolResult:
    symbol: str; decision: Decision

class DryRunStrategyRunner:
    def __init__(self, market: MarketService, settings: TradingSettings, store: TradingStore, strategy: TrendPullbackV1 | None = None, risk: RiskManager | None = None) -> None:
        self.market, self.settings, self.store = market, settings, store
        self.strategy, self.risk = strategy or TrendPullbackV1(), risk or RiskManager()
        self.states = {symbol: SymbolState(symbol) for symbol in settings.watchlist}
    def run_once(self) -> list[SymbolResult]:
        phase = market_phase(); results=[]
        for index, (symbol, state) in enumerate(self.states.items()):
            if index:
                # 키움 모의투자는 동일 국내 조회 TR을 초당 1회로 제한합니다.
                sleep(1.05)
            try:
                decision = self.strategy.evaluate(self.market.completed_15m_candles(symbol), state)
                if decision.signal == "BUY":
                    reason = self.risk.buy_block_reason(state, open_positions=sum(s.holding for s in self.states.values()), daily_entries=sum(s.entries_today for s in self.states.values()), consecutive_losses=0, daily_loss_pct=0, api_ok=True, market_open=phase == "OPEN")
                    if reason: decision = Decision(StrategyStatus.RISK_BLOCKED, reason, ema_fast=decision.ema_fast, ema_slow=decision.ema_slow, rsi=decision.rsi, atr=decision.atr)
                state.status, state.reason = decision.status, decision.reason
                self.store.record_signal(timestamp=datetime.now().isoformat(timespec="seconds"), symbol=symbol, strategy="Trend Pullback V1 Multi", state=decision.status, signal=decision.signal, score=decision.score, price=None, ema20=decision.ema_fast, ema60=decision.ema_slow, rsi=decision.rsi, atr=decision.atr, reason=decision.reason, mock_order_enabled=False)
            except Exception as exc:
                decision = Decision(StrategyStatus.ERROR, str(exc)); state.status, state.reason = decision.status, decision.reason
            results.append(SymbolResult(symbol, decision))
        return results

    def run_forever(self, interval_seconds: float, on_cycle=None) -> None:
        """장중에는 반복 분석하고, 장외에는 주문 없이 대기합니다."""
        while True:
            results = self.run_once()
            if on_cycle: on_cycle(results)
            sleep(interval_seconds)
