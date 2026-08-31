from __future__ import annotations
import sqlite3
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class DailySummary:
    date: str; signals: int; buys: int; sells: int; blocked: int; realized_profit: int


@dataclass(frozen=True)
class RecordedOrder:
    order_number: str; timestamp: str; symbol: str; side: str; quantity: int; status: str; filled_quantity: int; filled_price: int; stop_price: float | None; target_price: float | None


@dataclass(frozen=True)
class RecordedTrade:
    timestamp: str; symbol: str; side: str; price: float; quantity: int; realized_profit: int; status: str

class TradingStore:
    def __init__(self, path: Path | str = "data/trading.sqlite3") -> None:
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.execute("CREATE TABLE IF NOT EXISTS signals (timestamp TEXT, symbol TEXT, strategy TEXT, state TEXT, signal TEXT, score REAL, price REAL, ema20 REAL, ema60 REAL, rsi REAL, atr REAL, reason TEXT, mock_order_enabled INTEGER)")
        self.connection.execute("CREATE TABLE IF NOT EXISTS trades (timestamp TEXT, symbol TEXT, side TEXT, price REAL, quantity INTEGER, realized_profit INTEGER DEFAULT 0, status TEXT, strategy TEXT)")
        self.connection.execute("CREATE TABLE IF NOT EXISTS orders (order_number TEXT PRIMARY KEY, timestamp TEXT NOT NULL, symbol TEXT NOT NULL, side TEXT NOT NULL, quantity INTEGER NOT NULL, status TEXT NOT NULL, filled_quantity INTEGER NOT NULL DEFAULT 0, filled_price INTEGER NOT NULL DEFAULT 0, stop_price REAL, target_price REAL, updated_at TEXT NOT NULL)")
        columns = {row[1] for row in self.connection.execute("PRAGMA table_info(orders)")}
        if "stop_price" not in columns: self.connection.execute("ALTER TABLE orders ADD COLUMN stop_price REAL")
        if "target_price" not in columns: self.connection.execute("ALTER TABLE orders ADD COLUMN target_price REAL")
        self.connection.commit()
    def close(self) -> None: self.connection.close()
    def record_signal(self, **row: object) -> None:
        keys = ("timestamp","symbol","strategy","state","signal","score","price","ema20","ema60","rsi","atr","reason","mock_order_enabled")
        self.connection.execute(f"INSERT INTO signals ({','.join(keys)}) VALUES ({','.join('?' for _ in keys)})", [row.get(k) for k in keys]); self.connection.commit()
    def record_order(self, *, order_number: str, timestamp: str, symbol: str, side: str, quantity: int, status: str = "SUBMITTED", stop_price: float | None = None, target_price: float | None = None) -> None:
        self.connection.execute("INSERT OR IGNORE INTO orders (order_number,timestamp,symbol,side,quantity,status,stop_price,target_price,updated_at) VALUES (?,?,?,?,?,?,?,?,?)", (order_number, timestamp, symbol, side, quantity, status, stop_price, target_price, timestamp)); self.connection.commit()
    def update_order(self, *, order_number: str, status: str, filled_quantity: int, filled_price: int, updated_at: str) -> None:
        self.connection.execute("UPDATE orders SET status=?, filled_quantity=?, filled_price=?, updated_at=? WHERE order_number=?", (status, filled_quantity, filled_price, updated_at, order_number)); self.connection.commit()
    def record_trade(self, *, timestamp: str, symbol: str, side: str, price: float, quantity: int, realized_profit: int, status: str = "FILLED") -> None:
        self.connection.execute("INSERT INTO trades (timestamp,symbol,side,price,quantity,realized_profit,status,strategy) VALUES (?,?,?,?,?,?,?,?)", (timestamp, symbol, side, price, quantity, realized_profit, status, "Trend Pullback V1 Multi")); self.connection.commit()
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
