"""Trend Pullback V1 Multi의 순수 전략 계산입니다."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite


class StrategyStatus(StrEnum):
    WAIT = "WAIT"
    TREND_BLOCKED = "TREND_BLOCKED"
    PULLBACK = "PULLBACK"
    BUY_SIGNAL = "BUY_SIGNAL"
    HOLD = "HOLD"
    TAKE_PROFIT = "TAKE_PROFIT"
    STOP_LOSS = "STOP_LOSS"
    TREND_EXIT = "TREND_EXIT"
    COOLDOWN = "COOLDOWN"
    RISK_BLOCKED = "RISK_BLOCKED"
    ORDER_PENDING = "ORDER_PENDING"
    ERROR = "ERROR"


@dataclass(frozen=True)
class Candle:
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: int = 0


@dataclass(frozen=True)
class StrategyConfig:
    ema_fast: int = 20
    ema_slow: int = 60
    rsi_period: int = 14
    rsi_min: float = 30
    rsi_max: float = 70
    pullback_distance_pct: float = 0.5
    atr_period: int = 14
    atr_stop_multiplier: float = 1.5
    risk_reward_ratio: float = 2.0
    reentry_cooldown_bars: int = 2


@dataclass
class SymbolState:
    symbol: str
    status: StrategyStatus = StrategyStatus.WAIT
    reason: str = "초기 대기"
    last_bar_timestamp: str | None = None
    pullback_seen: bool = False
    holding: bool = False
    average_price: float | None = None
    quantity: int = 0
    stop_price: float | None = None
    target_price: float | None = None
    cooldown_remaining: int = 0
    order_pending: bool = False
    entries_today: int = 0


@dataclass(frozen=True)
class Decision:
    status: StrategyStatus
    reason: str
    signal: str | None = None
    score: float = 0.0
    ema_fast: float | None = None
    ema_slow: float | None = None
    rsi: float | None = None
    atr: float | None = None
    stop_price: float | None = None
    target_price: float | None = None


def _ema(values: list[float], period: int) -> float | None:
    if len(values) < period: return None
    value = sum(values[:period]) / period
    factor = 2 / (period + 1)
    for price in values[period:]: value = price * factor + value * (1 - factor)
    return value


def _rsi(values: list[float], period: int) -> float | None:
    if len(values) <= period: return None
    changes = [values[i] - values[i - 1] for i in range(1, len(values))]
    gains = [max(v, 0) for v in changes[-period:]]; losses = [max(-v, 0) for v in changes[-period:]]
    avg_gain, avg_loss = sum(gains) / period, sum(losses) / period
    if avg_loss == 0: return 100.0
    return 100 - (100 / (1 + avg_gain / avg_loss))


def _atr(candles: list[Candle], period: int) -> float | None:
    if len(candles) <= period: return None
    ranges = [max(c.high - c.low, abs(c.high - candles[i-1].close), abs(c.low - candles[i-1].close)) for i, c in enumerate(candles[1:], 1)]
    value = sum(ranges[-period:]) / period
    return value if isfinite(value) and value > 0 else None


class TrendPullbackV1:
    """완료된 봉 목록만 받는 순수 전략 엔진; 네트워크·주문 호출이 없습니다."""
    def __init__(self, config: StrategyConfig | None = None) -> None: self.config = config or StrategyConfig()

    def evaluate(self, candles: list[Candle], state: SymbolState) -> Decision:
        c = self.config
        if len(candles) < c.ema_slow + 1: return Decision(StrategyStatus.WAIT, "지표 계산용 완료 봉 부족")
        bar = candles[-1]
        if state.last_bar_timestamp == bar.timestamp: return Decision(state.status, "동일 완료 봉 재처리 차단")
        state.last_bar_timestamp = bar.timestamp
        if state.cooldown_remaining:
            state.cooldown_remaining -= 1; state.status = StrategyStatus.COOLDOWN
            return Decision(state.status, "재진입 쿨다운")
        closes = [x.close for x in candles]; fast, slow, rsi, atr = _ema(closes, c.ema_fast), _ema(closes, c.ema_slow), _rsi(closes, c.rsi_period), _atr(candles, c.atr_period)
        if None in (fast, slow, rsi, atr): return Decision(StrategyStatus.WAIT, "지표 계산용 완료 봉 부족")
        assert fast is not None and slow is not None and rsi is not None and atr is not None
        if state.holding:
            if bar.close <= state.stop_price: return Decision(StrategyStatus.STOP_LOSS, "ATR 손절", "SELL", ema_fast=fast, ema_slow=slow, rsi=rsi, atr=atr)
            if bar.close >= state.target_price: return Decision(StrategyStatus.TAKE_PROFIT, "목표 익절", "SELL", ema_fast=fast, ema_slow=slow, rsi=rsi, atr=atr)
            if bar.close < slow: return Decision(StrategyStatus.TREND_EXIT, "EMA60 하향 이탈", "SELL", ema_fast=fast, ema_slow=slow, rsi=rsi, atr=atr)
            return Decision(StrategyStatus.HOLD, "보유 유지", ema_fast=fast, ema_slow=slow, rsi=rsi, atr=atr)
        if not (bar.close > slow and fast > slow):
            state.pullback_seen = False; return Decision(StrategyStatus.TREND_BLOCKED, "상승 추세 조건 미충족", ema_fast=fast, ema_slow=slow, rsi=rsi, atr=atr)
        distance = abs(bar.close - fast) / fast * 100
        if distance <= c.pullback_distance_pct:
            state.pullback_seen = True; return Decision(StrategyStatus.PULLBACK, "EMA20 부근 눌림", ema_fast=fast, ema_slow=slow, rsi=rsi, atr=atr)
        if state.pullback_seen and bar.close > fast and bar.close > candles[-2].close and c.rsi_min <= rsi <= c.rsi_max:
            risk = atr * c.atr_stop_multiplier; stop, target = bar.close-risk, bar.close+risk*c.risk_reward_ratio
            score = ((fast-slow)/slow*100) + ((bar.close-candles[-2].close)/bar.close*100) + (50-abs(50-rsi))/100
            return Decision(StrategyStatus.BUY_SIGNAL, "상승 추세·눌림·반등 확인", "BUY", score, fast, slow, rsi, atr, stop, target)
        return Decision(StrategyStatus.WAIT, "반등 확인 대기", ema_fast=fast, ema_slow=slow, rsi=rsi, atr=atr)
