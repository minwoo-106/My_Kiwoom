from app.risk.manager import RiskManager
from app.strategy.core import Candle, StrategyStatus, SymbolState, TrendPullbackV1
from app.strategy.settings import DEFAULT_WATCHLIST, TradingSettings

def test_default_watchlist_has_five_symbols(): assert len(DEFAULT_WATCHLIST) == 5
def test_risk_blocks_existing_holding():
    assert RiskManager().buy_block_reason(SymbolState("005930", holding=True), open_positions=0, daily_entries=0, consecutive_losses=0, daily_loss_pct=0, api_ok=True, market_open=True) == "ALREADY_HOLDING"
def test_same_completed_bar_is_not_processed_twice():
    candles=[Candle(str(i), 100+i, 101+i, 99+i, 100+i) for i in range(61)]
    state=SymbolState("005930"); strategy=TrendPullbackV1()
    strategy.evaluate(candles,state)
    assert strategy.evaluate(candles,state).reason == "동일 완료 봉 재처리 차단"
