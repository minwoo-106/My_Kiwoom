from datetime import datetime, timedelta
from pathlib import Path

from app.risk.manager import RiskManager
from app.storage.sqlite import TradingStore
from app.strategy.core import StrategyStatus, SymbolState
from app.strategy.runner import DryRunStrategyRunner
from app.strategy.settings import TradingSettings


def _signal(store: TradingStore, timestamp: str, state: str, reason: str = "") -> None:
    store.record_signal(timestamp=timestamp, symbol="005930", strategy="Trend Pullback V1 Multi", state=state, signal="BUY" if state == "BUY_SIGNAL" else None, score=1.0, price=None, ema20=None, ema60=None, rsi=None, atr=None, reason=reason, mock_order_enabled=False)


def test_store_versions_every_signal_and_trade(tmp_path: Path):
    store = TradingStore(tmp_path / "operations.sqlite3")
    try:
        _signal(store, "2026-09-01T09:00:00", "BUY_SIGNAL")
        store.record_trade(timestamp="2026-09-01T09:01:00", symbol="005930", side="BUY", price=70_000, quantity=1, realized_profit=0)
        signal = store.connection.execute("SELECT strategy_version,config_version,git_commit FROM signals").fetchone()
        trade = store.connection.execute("SELECT strategy_version,config_version,git_commit FROM trades").fetchone()
        assert all(signal) and all(trade)
    finally:
        store.close()


def test_weekly_report_calculates_performance_and_operational_counts(tmp_path: Path):
    store = TradingStore(tmp_path / "weekly.sqlite3")
    try:
        store.record_program_start(timestamp="2026-08-30T08:00:00", mode="MOCK_AUTO")
        _signal(store, "2026-08-31T09:00:00", "BUY_SIGNAL")
        _signal(store, "2026-08-31T09:15:00", "RISK_BLOCKED", "MAX_OPEN_POSITIONS")
        _signal(store, "2026-08-31T09:30:00", "ERROR", "HTTP 429")
        store.record_trade(timestamp="2026-08-31T09:01:00", symbol="005930", side="BUY", price=100, quantity=1, realized_profit=0)
        store.record_trade(timestamp="2026-08-31T10:00:00", symbol="005930", side="SELL", price=120, quantity=1, realized_profit=20)
        store.record_trade(timestamp="2026-09-01T09:01:00", symbol="000660", side="BUY", price=100, quantity=1, realized_profit=0)
        store.record_trade(timestamp="2026-09-01T10:00:00", symbol="000660", side="SELL", price=90, quantity=1, realized_profit=-10)
        summary = store.weekly_summary("2026-09-01")
        assert (summary.filled_orders, summary.closed_trades, summary.wins, summary.losses) == (4, 2, 1, 1)
        assert summary.realized_profit == 10
        assert summary.profit_factor == 2
        assert summary.buy_signals == 1 and summary.actual_entries == 2
        assert summary.risk_blocked == 1 and summary.block_reasons == (("MAX_OPEN_POSITIONS", 1),)
        assert summary.api_errors == 1 and summary.restarts == 1
        assert {item.symbol for item in summary.symbols} == {"000660", "005930"}
    finally:
        store.close()


def test_emergency_stop_and_stale_data_block_new_buys_only():
    state = SymbolState("005930")
    risk = RiskManager()
    shared = dict(open_positions=0, daily_entries=0, consecutive_losses=0, daily_loss_pct=0, api_ok=True, market_open=True)
    assert risk.buy_block_reason(state, **shared, emergency_stop=True) == "EMERGENCY_STOP"
    assert risk.buy_block_reason(state, **shared, market_data_fresh=False) == "STALE_DATA"


def test_runner_records_each_program_start(tmp_path: Path):
    class Market:
        client = object()
    store = TradingStore(tmp_path / "sessions.sqlite3")
    try:
        DryRunStrategyRunner(Market(), TradingSettings(), store)
        assert store.connection.execute("SELECT count(*) FROM runtime_sessions").fetchone()[0] == 1
    finally:
        store.close()


def test_stale_market_data_is_displayed_when_refresh_keeps_failing(tmp_path: Path):
    class Market:
        client = object()
        def completed_15m_candles(self, symbol):
            raise RuntimeError("시세 조회 실패")
    now = datetime(2026, 9, 1, 10, 0, 0)
    store = TradingStore(tmp_path / "stale.sqlite3")
    try:
        runner = DryRunStrategyRunner(Market(), TradingSettings(stale_data_seconds=180), store, phase_provider=lambda: "OPEN", sleep_fn=lambda _: None, now_provider=lambda: now)
        runner.last_market_data_at = now - timedelta(seconds=181)
        assert all(item.decision.status == StrategyStatus.STALE_DATA for item in runner.run_once())
    finally:
        store.close()
