from dataclasses import dataclass
from app.strategy.core import SymbolState

@dataclass(frozen=True)
class RiskConfig:
    max_open_positions: int = 2
    max_daily_entries: int = 3
    max_daily_entries_per_symbol: int = 1
    max_consecutive_losses: int = 3
    max_daily_loss_pct: float = 1.0

class RiskManager:
    def __init__(self, config: RiskConfig | None = None) -> None: self.config = config or RiskConfig()
    def buy_block_reason(self, state: SymbolState, *, open_positions: int, daily_entries: int, consecutive_losses: int, daily_loss_pct: float, api_ok: bool, market_open: bool, market_data_fresh: bool = True, emergency_stop: bool = False) -> str | None:
        if emergency_stop: return "EMERGENCY_STOP"
        if not api_ok: return "API_ERROR"
        if not market_data_fresh: return "STALE_DATA"
        if not market_open: return "MARKET_CLOSED"
        if state.holding: return "ALREADY_HOLDING"
        if state.order_pending: return "ORDER_PENDING"
        if state.cooldown_remaining: return "COOLDOWN"
        if open_positions >= self.config.max_open_positions: return "MAX_OPEN_POSITIONS"
        if daily_entries >= self.config.max_daily_entries: return "DAILY_ENTRY_LIMIT"
        if state.entries_today >= self.config.max_daily_entries_per_symbol: return "SYMBOL_DAILY_ENTRY_LIMIT"
        if consecutive_losses >= self.config.max_consecutive_losses: return "CONSECUTIVE_LOSSES"
        if daily_loss_pct <= -self.config.max_daily_loss_pct: return "DAILY_LOSS_LIMIT"
        return None
