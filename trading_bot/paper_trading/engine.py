from __future__ import annotations

from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional

from trading_bot.paper_trading import storage as db
from trading_bot.paper_trading.models import Order, Portfolio, Position, Trade
from trading_bot.utils.logging import get_logger

logger = get_logger(__name__)

_DEFAULT_DB = Path(__file__).resolve().parents[2] / "trading_bot" / "data" / "paper_trading.db"


class PaperTradingEngine:
    """
    Self-contained paper trading engine backed by SQLite.
    No dependency on Excel or Streamlit session state.
    """

    def __init__(self, db_path: Path = _DEFAULT_DB):
        self.db_path = db_path
        db.init_db(db_path)

    # ── Settings ──────────────────────────────────────────────────────────

    def get_setting(self, key: str) -> str:
        return db.get_setting(key, self.db_path)

    def set_setting(self, key: str, value: str) -> None:
        db.set_setting(key, value, self.db_path)
        logger.info("Setting updated: %s = %s", key, value)

    @property
    def initial_capital(self) -> float:
        return float(self.get_setting("initial_capital") or 100000)

    @property
    def cash(self) -> float:
        return float(self.get_setting("cash") or self.initial_capital)

    @property
    def risk_pct(self) -> float:
        return float(self.get_setting("risk_pct") or 2.0)

    @property
    def max_open_positions(self) -> int:
        return int(self.get_setting("max_open_positions") or 5)

    # ── Portfolio ─────────────────────────────────────────────────────────

    def get_portfolio(self) -> Portfolio:
        positions = db.get_positions(self.db_path)
        positions_value = sum(p.market_value for p in positions)
        unrealized_pnl = sum(p.unrealized_pnl for p in positions)
        realized_pnl = float(self.get_setting("realized_pnl") or 0)
        return Portfolio(
            initial_capital=self.initial_capital,
            cash=self.cash,
            positions_value=round(positions_value, 2),
            realized_pnl=round(realized_pnl, 2),
            unrealized_pnl=round(unrealized_pnl, 2),
        )

    # ── Positions ─────────────────────────────────────────────────────────

    def get_positions(self) -> list[Position]:
        return db.get_positions(self.db_path)

    def get_position(self, symbol: str) -> Optional[Position]:
        return db.get_position(symbol, self.db_path)

    # ── Orders ────────────────────────────────────────────────────────────

    def get_open_orders(self) -> list[Order]:
        return db.get_orders("PENDING", self.db_path)

    def get_all_orders(self) -> list[Order]:
        return db.get_orders(None, self.db_path)

    def cancel_order(self, order_id: str) -> Optional[Order]:
        order = db.get_order(order_id, self.db_path)
        if order and order.status == "PENDING":
            db.update_order_status(order_id, "CANCELLED", db_path=self.db_path)
            logger.info("Order cancelled: %s %s", order.symbol, order_id)
        return db.get_order(order_id, self.db_path)

    # ── Trade History ─────────────────────────────────────────────────────

    def get_trade_history(self) -> list[Trade]:
        return db.get_trades(self.db_path)

    def get_equity_history(self):
        import pandas as pd
        rows = db.get_equity_history(self.db_path)
        if not rows:
            return pd.DataFrame(columns=["snapshot_at", "equity", "cash"])
        df = pd.DataFrame(rows)
        df["snapshot_at"] = pd.to_datetime(df["snapshot_at"])
        return df

    # ── Place Order ───────────────────────────────────────────────────────

    def place_order(
        self,
        symbol: str,
        side: str,
        qty: int,
        order_type: str = "MARKET",
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        target_price: Optional[float] = None,
        strategy: str = "",
        notes: str = "",
    ) -> Order:
        if qty <= 0:
            raise ValueError(f"Quantity must be positive, got {qty}")
        if side not in ("BUY", "SELL"):
            raise ValueError(f"Side must be BUY or SELL, got {side}")

        open_positions = self.get_positions()
        if side == "BUY" and len(open_positions) >= self.max_open_positions:
            raise ValueError(
                f"Max open positions ({self.max_open_positions}) reached. Close a position first."
            )

        order = Order(
            id=db.new_id(),
            symbol=symbol.upper(),
            side=side,
            qty=qty,
            order_type=order_type,
            status="PENDING",
            limit_price=limit_price,
            stop_price=stop_price,
            stop_loss=stop_loss,
            target_price=target_price,
            strategy=strategy,
            created_at=datetime.now(),
            filled_at=None,
            filled_price=None,
            filled_qty=0,
            notes=notes,
        )
        db.insert_order(order, self.db_path)
        logger.info("Order placed: %s %s %s x%d", order.id, side, symbol, qty)
        return order

    # ── Fill Market Order (using latest Bhavcopy close) ───────────────────

    def fill_market_order(self, order_id: str, fill_price: float) -> Order:
        """Fill a pending order at the given price (latest Bhavcopy close)."""
        order = db.get_order(order_id, self.db_path)
        if not order:
            raise ValueError(f"Order {order_id} not found")
        if order.status != "PENDING":
            raise ValueError(f"Order {order_id} is {order.status}, not PENDING")

        now = datetime.now()
        db.update_order_status(
            order_id, "FILLED",
            filled_at=now, filled_price=fill_price, filled_qty=order.qty,
            db_path=self.db_path,
        )
        order.status = "FILLED"
        order.filled_at = now
        order.filled_price = fill_price
        order.filled_qty = order.qty

        if order.side == "BUY":
            self._process_buy(order, fill_price)
        else:
            self._process_sell(order, fill_price)

        self._snapshot_equity()
        logger.info("Order filled: %s %s %s x%d @ ₹%.2f", order.id, order.side, order.symbol, order.qty, fill_price)
        return order

    def _process_buy(self, order: Order, fill_price: float) -> None:
        cost = fill_price * order.qty
        new_cash = self.cash - cost
        if new_cash < 0:
            raise ValueError(
                f"Insufficient cash. Need ₹{cost:,.2f}, have ₹{self.cash:,.2f}"
            )

        existing = db.get_position(order.symbol, self.db_path)
        if existing:
            total_qty = existing.qty + order.qty
            avg_entry = (existing.avg_entry_price * existing.qty + fill_price * order.qty) / total_qty
            pos = Position(
                symbol=order.symbol, qty=total_qty,
                avg_entry_price=round(avg_entry, 4),
                current_price=fill_price,
                stop_loss=order.stop_loss or existing.stop_loss,
                target_price=order.target_price or existing.target_price,
                strategy=order.strategy or existing.strategy,
                opened_at=existing.opened_at,
                order_id=existing.order_id,
            )
        else:
            pos = Position(
                symbol=order.symbol, qty=order.qty,
                avg_entry_price=fill_price,
                current_price=fill_price,
                stop_loss=order.stop_loss,
                target_price=order.target_price,
                strategy=order.strategy,
                opened_at=datetime.now(),
                order_id=order.id,
            )

        db.upsert_position(pos, self.db_path)
        self.set_setting("cash", str(round(new_cash, 4)))

    def _process_sell(self, order: Order, fill_price: float, exit_reason: str = "MANUAL") -> None:
        pos = db.get_position(order.symbol, self.db_path)
        if not pos:
            raise ValueError(f"No open position for {order.symbol}")
        if order.qty > pos.qty:
            raise ValueError(f"Cannot sell {order.qty} shares, only {pos.qty} held")

        proceeds = fill_price * order.qty
        realized_pnl = round((fill_price - pos.avg_entry_price) * order.qty, 2)
        pnl_pct = round((fill_price - pos.avg_entry_price) / pos.avg_entry_price * 100, 2) if pos.avg_entry_price else 0
        holding_days = max(0, (datetime.now().date() - pos.opened_at.date()).days)

        trade = Trade(
            id=db.new_id(),
            symbol=order.symbol,
            qty=order.qty,
            entry_price=pos.avg_entry_price,
            exit_price=fill_price,
            realized_pnl=realized_pnl,
            pnl_pct=pnl_pct,
            holding_days=holding_days,
            opened_at=pos.opened_at,
            closed_at=datetime.now(),
            exit_reason=exit_reason,
            strategy=pos.strategy,
            entry_order_id=pos.order_id,
            exit_order_id=order.id,
        )
        db.insert_trade(trade, self.db_path)

        remaining_qty = pos.qty - order.qty
        if remaining_qty <= 0:
            db.delete_position(order.symbol, self.db_path)
        else:
            pos.qty = remaining_qty
            db.upsert_position(pos, self.db_path)

        new_cash = round(self.cash + proceeds, 4)
        self.set_setting("cash", str(new_cash))
        new_realized = round(float(self.get_setting("realized_pnl") or 0) + realized_pnl, 4)
        self.set_setting("realized_pnl", str(new_realized))

    # ── Price update + auto-exit ───────────────────────────────────────────

    def update_prices(self, price_dict: dict[str, float], today: date | None = None) -> list[str]:
        """
        Update current_price for all positions. Auto-exit on SL/target hit.
        Returns list of symbols that were auto-exited.
        """
        if today is None:
            today = date.today()
        auto_exited: list[str] = []

        for pos in db.get_positions(self.db_path):
            price = price_dict.get(pos.symbol)
            if price is None:
                continue
            db.update_position_price(pos.symbol, price, self.db_path)
            pos.current_price = price

            exit_reason = None
            if pos.stop_loss and price <= pos.stop_loss:
                exit_reason = "STOP_LOSS"
            elif pos.target_price and price >= pos.target_price:
                exit_reason = "TARGET"

            if exit_reason:
                try:
                    sell_order = self.place_order(
                        pos.symbol, "SELL", pos.qty,
                        strategy=pos.strategy,
                        notes=f"Auto-exit: {exit_reason}",
                    )
                    self.fill_market_order(sell_order.id, price)
                    self._process_sell.__func__  # ensure called already in fill
                    auto_exited.append(pos.symbol)
                    logger.info("Auto-exit %s: %s @ ₹%.2f", exit_reason, pos.symbol, price)
                except Exception as exc:
                    logger.warning("Auto-exit failed for %s: %s", pos.symbol, exc)

        return auto_exited

    def _snapshot_equity(self) -> None:
        portfolio = self.get_portfolio()
        db.insert_equity_snapshot(
            cash=portfolio.cash,
            equity=portfolio.equity,
            realized_pnl=portfolio.realized_pnl,
            unrealized_pnl=portfolio.unrealized_pnl,
            db_path=self.db_path,
        )

    # ── Account reset ─────────────────────────────────────────────────────

    def reset_account(self, new_capital: Optional[float] = None) -> None:
        """Wipe all orders, positions, trades and reset cash to initial_capital."""
        cap = new_capital or self.initial_capital
        with db._conn(self.db_path) as con:
            con.execute("DELETE FROM orders")
            con.execute("DELETE FROM positions")
            con.execute("DELETE FROM trades")
            con.execute("DELETE FROM equity_snapshots")
        self.set_setting("initial_capital", str(cap))
        self.set_setting("cash", str(cap))
        self.set_setting("realized_pnl", "0.0")
        logger.info("Account reset. Capital: ₹%.2f", cap)
