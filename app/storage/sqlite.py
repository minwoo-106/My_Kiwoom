from __future__ import annotations
import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from app.versioning import ExecutionVersion, current_execution_version

@dataclass(frozen=True)
class DailySummary:
    date: str; signals: int; buys: int; sells: int; blocked: int; realized_profit: int


@dataclass(frozen=True)
class RecordedOrder:
    order_number: str; timestamp: str; symbol: str; side: str; quantity: int; status: str; filled_quantity: int; filled_price: int; stop_price: float | None; target_price: float | None


@dataclass(frozen=True)
class RecordedTrade:
    timestamp: str; symbol: str; side: str; price: float; quantity: int; realized_profit: int; status: str


@dataclass(frozen=True)
class SymbolWeeklySummary:
    symbol: str; trades: int; wins: int; losses: int; win_rate: float | None; realized_profit: int


@dataclass(frozen=True)
class WeeklySummary:
    start_date: str; end_date: str; filled_orders: int; closed_trades: int; wins: int; losses: int
    win_rate: float | None; realized_profit: int; average_profit: float | None; average_loss: float | None
    profit_factor: float | None; max_consecutive_losses: int; buy_signals: int; actual_entries: int
    risk_blocked: int; block_reasons: tuple[tuple[str, int], ...]; api_errors: int; restarts: int
    symbols: tuple[SymbolWeeklySummary, ...]

class TradingStore:
    def __init__(self, path: Path | str = "data/trading.sqlite3") -> None:
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.version: ExecutionVersion = current_execution_version()
        self.connection.execute("CREATE TABLE IF NOT EXISTS signals (timestamp TEXT, symbol TEXT, strategy TEXT, state TEXT, signal TEXT, score REAL, price REAL, ema20 REAL, ema60 REAL, rsi REAL, atr REAL, reason TEXT, mock_order_enabled INTEGER, strategy_version TEXT, config_version TEXT, git_commit TEXT)")
        self.connection.execute("CREATE TABLE IF NOT EXISTS trades (timestamp TEXT, symbol TEXT, side TEXT, price REAL, quantity INTEGER, realized_profit INTEGER DEFAULT 0, status TEXT, strategy TEXT, strategy_version TEXT, config_version TEXT, git_commit TEXT)")
        self.connection.execute("CREATE TABLE IF NOT EXISTS orders (order_number TEXT PRIMARY KEY, timestamp TEXT NOT NULL, symbol TEXT NOT NULL, side TEXT NOT NULL, quantity INTEGER NOT NULL, status TEXT NOT NULL, filled_quantity INTEGER NOT NULL DEFAULT 0, filled_price INTEGER NOT NULL DEFAULT 0, stop_price REAL, target_price REAL, updated_at TEXT NOT NULL)")
        self.connection.execute("CREATE TABLE IF NOT EXISTS runtime_sessions (started_at TEXT NOT NULL, mode TEXT NOT NULL, strategy_version TEXT NOT NULL, config_version TEXT NOT NULL, git_commit TEXT NOT NULL)")
        self._ensure_columns("orders", {"stop_price": "REAL", "target_price": "REAL"})
        self._ensure_columns("signals", {"strategy_version": "TEXT", "config_version": "TEXT", "git_commit": "TEXT"})
        self._ensure_columns("trades", {"strategy_version": "TEXT", "config_version": "TEXT", "git_commit": "TEXT"})
        self.connection.commit()

    def _ensure_columns(self, table: str, columns: dict[str, str]) -> None:
        existing = {row[1] for row in self.connection.execute(f"PRAGMA table_info({table})")}
        for name, column_type in columns.items():
            if name not in existing:
                self.connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {column_type}")

    def close(self) -> None: self.connection.close()
    def record_signal(self, **row: object) -> None:
        keys = ("timestamp","symbol","strategy","state","signal","score","price","ema20","ema60","rsi","atr","reason","mock_order_enabled","strategy_version","config_version","git_commit")
        versioned = {**row, "strategy_version": row.get("strategy_version", self.version.strategy_version), "config_version": row.get("config_version", self.version.config_version), "git_commit": row.get("git_commit", self.version.git_commit)}
        self.connection.execute(f"INSERT INTO signals ({','.join(keys)}) VALUES ({','.join('?' for _ in keys)})", [versioned.get(k) for k in keys]); self.connection.commit()
    def record_order(self, *, order_number: str, timestamp: str, symbol: str, side: str, quantity: int, status: str = "SUBMITTED", stop_price: float | None = None, target_price: float | None = None) -> None:
        self.connection.execute("INSERT OR IGNORE INTO orders (order_number,timestamp,symbol,side,quantity,status,stop_price,target_price,updated_at) VALUES (?,?,?,?,?,?,?,?,?)", (order_number, timestamp, symbol, side, quantity, status, stop_price, target_price, timestamp)); self.connection.commit()
    def update_order(self, *, order_number: str, status: str, filled_quantity: int, filled_price: int, updated_at: str) -> None:
        self.connection.execute("UPDATE orders SET status=?, filled_quantity=?, filled_price=?, updated_at=? WHERE order_number=?", (status, filled_quantity, filled_price, updated_at, order_number)); self.connection.commit()
    def record_trade(self, *, timestamp: str, symbol: str, side: str, price: float, quantity: int, realized_profit: int, status: str = "FILLED") -> None:
        self.connection.execute("INSERT INTO trades (timestamp,symbol,side,price,quantity,realized_profit,status,strategy,strategy_version,config_version,git_commit) VALUES (?,?,?,?,?,?,?,?,?,?,?)", (timestamp, symbol, side, price, quantity, realized_profit, status, self.version.strategy_version, self.version.strategy_version, self.version.config_version, self.version.git_commit)); self.connection.commit()

    def record_program_start(self, *, timestamp: str, mode: str) -> None:
        self.connection.execute("INSERT INTO runtime_sessions (started_at,mode,strategy_version,config_version,git_commit) VALUES (?,?,?,?,?)", (timestamp, mode, self.version.strategy_version, self.version.config_version, self.version.git_commit)); self.connection.commit()
    def pending_orders(self) -> list[RecordedOrder]:
        rows = self.connection.execute("SELECT order_number,timestamp,symbol,side,quantity,status,filled_quantity,filled_price,stop_price,target_price FROM orders WHERE status IN ('SUBMITTED','PARTIAL') ORDER BY timestamp").fetchall()
        return [RecordedOrder(*row) for row in rows]
    def last_filled_buy(self, symbol: str) -> RecordedOrder | None:
        row = self.connection.execute("SELECT order_number,timestamp,symbol,side,quantity,status,filled_quantity,filled_price,stop_price,target_price FROM orders WHERE symbol=? AND side='BUY' AND status='FILLED' ORDER BY updated_at DESC LIMIT 1", (symbol,)).fetchone()
        return RecordedOrder(*row) if row else None
    def today_entries(self, date: str) -> int:
        return self.connection.execute("SELECT count(*) FROM trades WHERE substr(timestamp,1,10)=? AND side='BUY' AND status='FILLED'", (date,)).fetchone()[0]
    def today_realized_profit(self, date: str) -> int:
        return self.connection.execute("SELECT coalesce(sum(realized_profit),0) FROM trades WHERE substr(timestamp,1,10)=? AND status='FILLED'", (date,)).fetchone()[0]
    def consecutive_losses(self) -> int:
        rows = self.connection.execute("SELECT realized_profit FROM trades WHERE side='SELL' AND status='FILLED' ORDER BY timestamp DESC").fetchall()
        count = 0
        for (profit,) in rows:
            if profit < 0: count += 1
            else: break
        return count
    def recent_trades(self, limit: int = 5) -> list[RecordedTrade]:
        rows = self.connection.execute("SELECT timestamp,symbol,side,price,quantity,realized_profit,status FROM trades ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
        return [RecordedTrade(*row) for row in rows]
    def daily_summary(self, date: str) -> DailySummary:
        q = "WHERE substr(timestamp,1,10)=?"; args=(date,)
        signals=self.connection.execute(f"SELECT count(*) FROM signals {q}",args).fetchone()[0]
        blocked=self.connection.execute(f"SELECT count(*) FROM signals {q} AND state='RISK_BLOCKED'",args).fetchone()[0]
        buys=self.connection.execute(f"SELECT count(*) FROM trades {q} AND side='BUY'",args).fetchone()[0]
        sells=self.connection.execute(f"SELECT count(*) FROM trades {q} AND side='SELL'",args).fetchone()[0]
        pnl=self.connection.execute(f"SELECT coalesce(sum(realized_profit),0) FROM trades {q}",args).fetchone()[0]
        return DailySummary(date,signals,buys,sells,blocked,pnl)

    def weekly_summary(self, end_date: str) -> WeeklySummary:
        end = date.fromisoformat(end_date); start = end - timedelta(days=6)
        start_text, end_text = start.isoformat(), end.isoformat()
        range_sql = "substr(timestamp,1,10) BETWEEN ? AND ?"
        args = (start_text, end_text)
        fills = self.connection.execute(f"SELECT count(*) FROM trades WHERE {range_sql} AND status='FILLED'", args).fetchone()[0]
        outcomes = self.connection.execute(f"SELECT symbol,realized_profit FROM trades WHERE {range_sql} AND side='SELL' AND status='FILLED' ORDER BY timestamp", args).fetchall()
        wins = sum(profit > 0 for _, profit in outcomes); losses = sum(profit < 0 for _, profit in outcomes)
        profits = [profit for _, profit in outcomes if profit > 0]; loss_values = [profit for _, profit in outcomes if profit < 0]
        pnl = sum(profit for _, profit in outcomes)
        gross_profit, gross_loss = sum(profits), abs(sum(loss_values))
        streak = maximum_streak = 0
        for _, profit in outcomes:
            streak = streak + 1 if profit < 0 else 0
            maximum_streak = max(maximum_streak, streak)
        signal_rows = self.connection.execute(f"SELECT state,reason FROM signals WHERE {range_sql}", args).fetchall()
        buy_signals = sum(state == "BUY_SIGNAL" for state, _ in signal_rows)
        blocks: dict[str, int] = {}
        for state, reason in signal_rows:
            if state == "RISK_BLOCKED": blocks[reason] = blocks.get(reason, 0) + 1
        actual_entries = self.connection.execute(f"SELECT count(*) FROM trades WHERE {range_sql} AND side='BUY' AND status='FILLED'", args).fetchone()[0]
        api_errors = self.connection.execute(f"SELECT count(*) FROM signals WHERE {range_sql} AND state='ERROR'", args).fetchone()[0]
        restarts = self.connection.execute("SELECT count(*) FROM runtime_sessions WHERE substr(started_at,1,10) BETWEEN ? AND ?", args).fetchone()[0]
        symbols: list[SymbolWeeklySummary] = []
        for symbol in sorted({symbol for symbol, _ in outcomes}):
            values = [profit for value_symbol, profit in outcomes if value_symbol == symbol]
            symbol_wins, symbol_losses = sum(value > 0 for value in values), sum(value < 0 for value in values)
            decided = symbol_wins + symbol_losses
            symbols.append(SymbolWeeklySummary(symbol, len(values), symbol_wins, symbol_losses, symbol_wins / decided * 100 if decided else None, sum(values)))
        decided = wins + losses
        return WeeklySummary(start_text, end_text, fills, len(outcomes), wins, losses, wins / decided * 100 if decided else None, pnl, sum(profits) / len(profits) if profits else None, sum(loss_values) / len(loss_values) if loss_values else None, gross_profit / gross_loss if gross_loss else None, maximum_streak, buy_signals, actual_entries, sum(blocks.values()), tuple(sorted(blocks.items())), api_errors, restarts, tuple(symbols))
