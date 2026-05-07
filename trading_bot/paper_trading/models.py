from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Order:
    id: str
    symbol: str
    side: str                    # BUY | SELL
    qty: int
    order_type: str              # MARKET | LIMIT | STOP
    status: str                  # PENDING | FILLED | CANCELLED | REJECTED
    limit_price: Optional[float]
    stop_price: Optional[float]
    stop_loss: Optional[float]
    target_price: Optional[float]
    strategy: str
    created_at: datetime
    filled_at: Optional[datetime]
    filled_price: Optional[float]
    filled_qty: int
    notes: str


@dataclass
class Position:
    symbol: str
    qty: int
    avg_entry_price: float
    current_price: float
    stop_loss: Optional[float]
    target_price: Optional[float]
    strategy: str
    opened_at: datetime
    order_id: str

    @property
    def market_value(self) -> float:
        return self.qty * self.current_price

    @property
    def cost_basis(self) -> float:
        return self.qty * self.avg_entry_price

    @property
    def unrealized_pnl(self) -> float:
        return round((self.current_price - self.avg_entry_price) * self.qty, 2)

    @property
    def unrealized_pnl_pct(self) -> float:
        if self.avg_entry_price == 0:
            return 0.0
        return round((self.current_price - self.avg_entry_price) / self.avg_entry_price * 100, 2)


@dataclass
class Trade:
    id: str
    symbol: str
    qty: int
    entry_price: float
    exit_price: float
    realized_pnl: float
    pnl_pct: float
    holding_days: int
    opened_at: datetime
    closed_at: datetime
    exit_reason: str             # TARGET | STOP_LOSS | MANUAL | MAX_DAYS
    strategy: str
    entry_order_id: str
    exit_order_id: str


@dataclass
class Portfolio:
    initial_capital: float
    cash: float
    positions_value: float       # sum of all position market values
    realized_pnl: float
    unrealized_pnl: float

    @property
    def equity(self) -> float:
        return round(self.cash + self.positions_value, 2)

    @property
    def buying_power(self) -> float:
        return round(self.cash, 2)

    @property
    def total_pnl(self) -> float:
        return round(self.equity - self.initial_capital, 2)

    @property
    def total_pnl_pct(self) -> float:
        if self.initial_capital == 0:
            return 0.0
        return round(self.total_pnl / self.initial_capital * 100, 2)
