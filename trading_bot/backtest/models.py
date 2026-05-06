from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date


@dataclass
class StrategyConfig:
    name: str = "PDF Swing Strategy"
    strategy_style: str = "breakout_52w"
    timeframe: str = "day"
    direction: str = "LONG"
    benchmark_universe: str = "NIFTY50"
    trend_fast_ema: int = 50
    trend_slow_ema: int = 200
    signal_fast_ema: int = 20
    signal_slow_ema: int = 50
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    volume_window: int = 20
    volume_multiplier: float = 1.2
    support_window: int = 20
    support_threshold_pct: float = 3.0
    resistance_threshold_pct: float = 3.0
    stop_loss_pct: float = 8.0
    risk_reward_ratio: float = 2.0
    max_holding_days: int = 20
    minimum_confidence: int = 4
    require_macd_crossover: bool = True
    require_ema_alignment: bool = True
    require_support_bounce: bool = True
    require_bullish_reversal: bool = True
    require_volume_confirmation: bool = True
    notes: str = ""
    raw_source_excerpt: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BacktestConfig:
    start_date: date
    end_date: date
    initial_capital: float
    risk_pct: float
    max_open_positions: int


@dataclass
class TradeRecord:
    symbol: str
    signal_date: date
    entry_date: date
    exit_date: date
    side: str
    entry_price: float
    exit_price: float
    stop_loss: float
    target_price: float
    quantity: int
    pnl: float
    pnl_pct: float
    holding_days: int
    confidence: str
    score: int
    market_trend: str
    entry_point: str
    avg_volume: str
    macd_crossover: str
    ema_crossover: str
    price_position: str
    bullish_reversal: str
    comments: str

    def to_dict(self) -> dict:
        return asdict(self)
