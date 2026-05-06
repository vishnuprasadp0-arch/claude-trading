from dataclasses import dataclass
from typing import Optional


@dataclass
class TradeDecision:
    symbol: str
    action: str = "SKIP"        # BUY / HOLD / SKIP
    confidence: str = "Low"     # High / Medium / Low
    stop_loss: Optional[float] = None
    target: Optional[float] = None
    reasoning: str = ""
