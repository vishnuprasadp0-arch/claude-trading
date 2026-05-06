from dataclasses import dataclass


@dataclass
class TradeRow:
    market_trend: str            # Col A
    stock: str                   # Col B
    red_flag: str                # Col C: No / Yes
    entry_point: str             # Col D: Good / Bad
    promoter_holding: str        # Col E: Good / Avg / Bad / N/A
    institutional_holdings: str  # Col F: Good / Avg / Bad / N/A
    avg_volume: str              # Col G: Good / Bad
    macd_crossover: str          # Col H: Yes / No
    ema_crossover: str           # Col I: Yes / No
    price_position: str          # Col J
    bullish_reversal: str        # Col K: Yes / No
    entry_date: str              # Col L: ISO date string
    stop_loss: float             # Col M
    entry: float                 # Col N
    target: float                # Col O
    quantity: int                # Col P
    confidence: str              # Col Q: High / Medium / Low
    reasoning: str               # Col V: LLM reasoning
