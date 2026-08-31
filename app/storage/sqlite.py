from __future__ import annotations
import sqlite3
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class DailySummary:
    date: str; signals: int; buys: int; sells: int; blocked: int; realized_profit: int

class TradingStore:
    def __init__(self, path: Path | str = "data/trading.sqlite3") -> None:
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.execute("CREATE TABLE IF NOT EXISTS signals (timestamp TEXT, symbol TEXT, strategy TEXT, state TEXT, signal TEXT, score REAL, price REAL, ema20 REAL, ema60 REAL, rsi REAL, atr REAL, reason TEXT, mock_order_enabled INTEGER)")
        self.connection.execute("CREATE TABLE IF NOT EXISTS trades (timestamp TEXT, symbol TEXT, side TEXT, price REAL, quantity INTEGER, realized_profit INTEGER DEFAULT 0, status TEXT, strategy TEXT)")
        self.connection.commit()
    def close(self) -> None: self.connection.close()
    def record_signal(self, **row: object) -> None:
        keys = ("timestamp","symbol","strategy","state","signal","score","price","ema20","ema60","rsi","atr","reason","mock_order_enabled")
        self.connection.execute(f"INSERT INTO signals ({','.join(keys)}) VALUES ({','.join('?' for _ in keys)})", [row.get(k) for k in keys]); self.connection.commit()
    def daily_summary(self, date: str) -> DailySummary:
        q = "WHERE substr(timestamp,1,10)=?"; args=(date,)
        signals=self.connection.execute(f"SELECT count(*) FROM signals {q}",args).fetchone()[0]
        blocked=self.connection.execute(f"SELECT count(*) FROM signals {q} AND state='RISK_BLOCKED'",args).fetchone()[0]
        buys=self.connection.execute(f"SELECT count(*) FROM trades {q} AND side='BUY'",args).fetchone()[0]
        sells=self.connection.execute(f"SELECT count(*) FROM trades {q} AND side='SELL'",args).fetchone()[0]
        pnl=self.connection.execute(f"SELECT coalesce(sum(realized_profit),0) FROM trades {q}",args).fetchone()[0]
        return DailySummary(date,signals,buys,sells,blocked,pnl)
