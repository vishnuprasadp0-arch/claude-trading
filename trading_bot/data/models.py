from dataclasses import dataclass
from typing import Optional


@dataclass
class Bar:
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Signal:
    symbol: str
    rsi: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_hist: Optional[float] = None
    ema10: Optional[float] = None
    ema20: Optional[float] = None
    ema50: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[float] = None
    avg_volume: Optional[float] = None
    recommendation: str = "NEUTRAL"
    trend: str = "Neutral"
    macd_crossover: bool = False
    ema_crossover: bool = False
    price_position: str = "Unknown"
    bullish_reversal: bool = False
