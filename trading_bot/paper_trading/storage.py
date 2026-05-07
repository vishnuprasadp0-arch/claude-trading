from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from trading_bot.paper_trading.models import Order, Position, Trade

_DB_PATH = Path(__file__).resolve().parents[2] / "trading_bot" / "data" / "paper_trading.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    id           TEXT PRIMARY KEY,
    symbol       TEXT NOT NULL,
    side         TEXT NOT NULL,
    qty          INTEGER NOT NULL,
    order_type   TEXT NOT NULL,
    status       TEXT NOT NULL,
    limit_price  REAL,
    stop_price   REAL,
    stop_loss    REAL,
    target_price REAL,
    strategy     TEXT DEFAULT '',
    created_at   TEXT NOT NULL,
    filled_at    TEXT,
    filled_price REAL,
    filled_qty   INTEGER DEFAULT 0,
    notes        TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS positions (
    symbol           TEXT PRIMARY KEY,
    qty              INTEGER NOT NULL,
    avg_entry_price  REAL NOT NULL,
    current_price    REAL NOT NULL,
    stop_loss        REAL,
    target_price     REAL,
    strategy         TEXT DEFAULT '',
    opened_at        TEXT NOT NULL,
    order_id         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trades (
    id               TEXT PRIMARY KEY,
    symbol           TEXT NOT NULL,
    qty              INTEGER NOT NULL,
    entry_price      REAL NOT NULL,
    exit_price       REAL NOT NULL,
    realized_pnl     REAL NOT NULL,
    pnl_pct          REAL NOT NULL,
    holding_days     INTEGER DEFAULT 0,
    opened_at        TEXT NOT NULL,
    closed_at        TEXT NOT NULL,
    exit_reason      TEXT DEFAULT 'MANUAL',
    strategy         TEXT DEFAULT '',
    entry_order_id   TEXT DEFAULT '',
    exit_order_id    TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS equity_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_at     TEXT NOT NULL,
    cash            REAL NOT NULL,
    equity          REAL NOT NULL,
    realized_pnl    REAL NOT NULL,
    unrealized_pnl  REAL NOT NULL
);
"""

_DEFAULTS = {
    "initial_capital": "100000.0",
    "risk_pct": "2.0",
    "max_open_positions": "5",
    "cash": "100000.0",
    "realized_pnl": "0.0",
}


@contextmanager
def _conn(db_path: Path = _DB_PATH):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db(db_path: Path = _DB_PATH) -> None:
    with _conn(db_path) as con:
        con.executescript(_SCHEMA)
        for key, value in _DEFAULTS.items():
            con.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))


# ── Settings ──────────────────────────────────────────────────────────────

def get_setting(key: str, db_path: Path = _DB_PATH) -> str:
    with _conn(db_path) as con:
        row = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else _DEFAULTS.get(key, "")


def set_setting(key: str, value: str, db_path: Path = _DB_PATH) -> None:
    with _conn(db_path) as con:
        con.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))


# ── Orders ────────────────────────────────────────────────────────────────

def insert_order(order: Order, db_path: Path = _DB_PATH) -> None:
    with _conn(db_path) as con:
        con.execute("""
            INSERT INTO orders
            (id, symbol, side, qty, order_type, status, limit_price, stop_price,
             stop_loss, target_price, strategy, created_at, filled_at, filled_price,
             filled_qty, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            order.id, order.symbol, order.side, order.qty, order.order_type,
            order.status, order.limit_price, order.stop_price, order.stop_loss,
            order.target_price, order.strategy,
            order.created_at.isoformat(),
            order.filled_at.isoformat() if order.filled_at else None,
            order.filled_price, order.filled_qty, order.notes,
        ))


def update_order_status(order_id: str, status: str, filled_at: Optional[datetime] = None,
                        filled_price: Optional[float] = None, filled_qty: Optional[int] = None,
                        db_path: Path = _DB_PATH) -> None:
    with _conn(db_path) as con:
        con.execute("""
            UPDATE orders SET status=?, filled_at=?, filled_price=?, filled_qty=?
            WHERE id=?
        """, (
            status,
            filled_at.isoformat() if filled_at else None,
            filled_price, filled_qty, order_id,
        ))


def get_orders(status: Optional[str] = None, db_path: Path = _DB_PATH) -> list[Order]:
    with _conn(db_path) as con:
        if status:
            rows = con.execute("SELECT * FROM orders WHERE status=? ORDER BY created_at DESC", (status,)).fetchall()
        else:
            rows = con.execute("SELECT * FROM orders ORDER BY created_at DESC").fetchall()
    return [_row_to_order(r) for r in rows]


def get_order(order_id: str, db_path: Path = _DB_PATH) -> Optional[Order]:
    with _conn(db_path) as con:
        row = con.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    return _row_to_order(row) if row else None


def _row_to_order(r) -> Order:
    return Order(
        id=r["id"], symbol=r["symbol"], side=r["side"], qty=r["qty"],
        order_type=r["order_type"], status=r["status"],
        limit_price=r["limit_price"], stop_price=r["stop_price"],
        stop_loss=r["stop_loss"], target_price=r["target_price"],
        strategy=r["strategy"] or "",
        created_at=datetime.fromisoformat(r["created_at"]),
        filled_at=datetime.fromisoformat(r["filled_at"]) if r["filled_at"] else None,
        filled_price=r["filled_price"], filled_qty=r["filled_qty"] or 0,
        notes=r["notes"] or "",
    )


# ── Positions ──────────────────────────────────────────────────────────────

def upsert_position(pos: Position, db_path: Path = _DB_PATH) -> None:
    with _conn(db_path) as con:
        con.execute("""
            INSERT OR REPLACE INTO positions
            (symbol, qty, avg_entry_price, current_price, stop_loss, target_price,
             strategy, opened_at, order_id)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (
            pos.symbol, pos.qty, pos.avg_entry_price, pos.current_price,
            pos.stop_loss, pos.target_price, pos.strategy,
            pos.opened_at.isoformat(), pos.order_id,
        ))


def update_position_price(symbol: str, current_price: float, db_path: Path = _DB_PATH) -> None:
    with _conn(db_path) as con:
        con.execute("UPDATE positions SET current_price=? WHERE symbol=?", (current_price, symbol))


def delete_position(symbol: str, db_path: Path = _DB_PATH) -> None:
    with _conn(db_path) as con:
        con.execute("DELETE FROM positions WHERE symbol=?", (symbol,))


def get_positions(db_path: Path = _DB_PATH) -> list[Position]:
    with _conn(db_path) as con:
        rows = con.execute("SELECT * FROM positions ORDER BY opened_at DESC").fetchall()
    return [_row_to_position(r) for r in rows]


def get_position(symbol: str, db_path: Path = _DB_PATH) -> Optional[Position]:
    with _conn(db_path) as con:
        row = con.execute("SELECT * FROM positions WHERE symbol=?", (symbol,)).fetchone()
    return _row_to_position(row) if row else None


def _row_to_position(r) -> Position:
    return Position(
        symbol=r["symbol"], qty=r["qty"],
        avg_entry_price=r["avg_entry_price"], current_price=r["current_price"],
        stop_loss=r["stop_loss"], target_price=r["target_price"],
        strategy=r["strategy"] or "",
        opened_at=datetime.fromisoformat(r["opened_at"]),
        order_id=r["order_id"],
    )


# ── Trades ─────────────────────────────────────────────────────────────────

def insert_trade(trade: Trade, db_path: Path = _DB_PATH) -> None:
    with _conn(db_path) as con:
        con.execute("""
            INSERT INTO trades
            (id, symbol, qty, entry_price, exit_price, realized_pnl, pnl_pct,
             holding_days, opened_at, closed_at, exit_reason, strategy,
             entry_order_id, exit_order_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            trade.id, trade.symbol, trade.qty, trade.entry_price, trade.exit_price,
            trade.realized_pnl, trade.pnl_pct, trade.holding_days,
            trade.opened_at.isoformat(), trade.closed_at.isoformat(),
            trade.exit_reason, trade.strategy,
            trade.entry_order_id, trade.exit_order_id,
        ))


def get_trades(db_path: Path = _DB_PATH) -> list[Trade]:
    with _conn(db_path) as con:
        rows = con.execute("SELECT * FROM trades ORDER BY closed_at DESC").fetchall()
    return [_row_to_trade(r) for r in rows]


def _row_to_trade(r) -> Trade:
    return Trade(
        id=r["id"], symbol=r["symbol"], qty=r["qty"],
        entry_price=r["entry_price"], exit_price=r["exit_price"],
        realized_pnl=r["realized_pnl"], pnl_pct=r["pnl_pct"],
        holding_days=r["holding_days"] or 0,
        opened_at=datetime.fromisoformat(r["opened_at"]),
        closed_at=datetime.fromisoformat(r["closed_at"]),
        exit_reason=r["exit_reason"] or "MANUAL",
        strategy=r["strategy"] or "",
        entry_order_id=r["entry_order_id"] or "",
        exit_order_id=r["exit_order_id"] or "",
    )


# ── Equity snapshots ───────────────────────────────────────────────────────

def insert_equity_snapshot(cash: float, equity: float, realized_pnl: float,
                            unrealized_pnl: float, db_path: Path = _DB_PATH) -> None:
    with _conn(db_path) as con:
        con.execute("""
            INSERT INTO equity_snapshots (snapshot_at, cash, equity, realized_pnl, unrealized_pnl)
            VALUES (?, ?, ?, ?, ?)
        """, (datetime.now().isoformat(), cash, equity, realized_pnl, unrealized_pnl))


def get_equity_history(db_path: Path = _DB_PATH) -> list[dict]:
    with _conn(db_path) as con:
        rows = con.execute(
            "SELECT snapshot_at, equity, cash, realized_pnl, unrealized_pnl "
            "FROM equity_snapshots ORDER BY snapshot_at"
        ).fetchall()
    return [dict(r) for r in rows]


def new_id() -> str:
    return str(uuid.uuid4())[:8].upper()
