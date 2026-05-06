import re
from datetime import date

from trading_bot.data.models import Signal
from trading_bot.strategy.models import TradeDecision
from trading_bot.execution.models import TradeRow
from trading_bot.utils.logging import get_logger

logger = get_logger(__name__)


def compute_position_size(
    capital: float,
    entry: float,
    stop_loss: float,
    risk_pct: float = 2.0,
    num_trades: int = 5,
) -> dict:
    if entry <= stop_loss:
        raise ValueError(f"Entry ({entry}) must be above stop loss ({stop_loss})")
    sl_per_share = entry - stop_loss
    max_qty = (capital * risk_pct / 100) / sl_per_share
    ideal_capital = min(capital / num_trades, max_qty * entry)
    ideal_qty = max(1, int(ideal_capital / entry))
    return {
        "sl_pct": sl_per_share / entry,
        "max_qty": max_qty,
        "ideal_capital": ideal_capital,
        "ideal_qty": ideal_qty,
    }


def parse_stop_loss(rule: str, entry: float, signal: Signal | None = None) -> float:
    rule_l = rule.lower()
    m = re.search(r"(\d+(?:\.\d+)?)\s*%\s*below", rule_l)
    if m:
        return round(entry * (1 - float(m.group(1)) / 100), 2)
    if "ema50" in rule_l and signal and signal.ema50:
        return round(signal.ema50 * 0.99, 2)
    if "ema20" in rule_l and signal and signal.ema20:
        return round(signal.ema20 * 0.99, 2)
    if "swing low" in rule_l or "recent low" in rule_l:
        return round(entry * 0.97, 2)
    return round(entry * 0.98, 2)  # default 2% below entry


def parse_target(rule: str, entry: float, stop_loss: float) -> float:
    rule_l = rule.lower()
    m = re.search(r"(\d+(?:\.\d+)?)\s*:\s*1", rule_l)
    if m:
        return round(entry + float(m.group(1)) * (entry - stop_loss), 2)
    m = re.search(r"(\d+(?:\.\d+)?)\s*%\s*above", rule_l)
    if m:
        return round(entry * (1 + float(m.group(1)) / 100), 2)
    return round(entry * 1.06, 2)  # default 6% target


def build_trade_row(
    signal: Signal,
    decision: TradeDecision,
    strategy: dict,
    capital: float,
    risk_pct: float = 2.0,
    num_trades: int = 5,
) -> TradeRow:
    entry = signal.close or 0.0
    stop_loss = parse_stop_loss(strategy.get("stop_loss_rule", "2% below entry"), entry, signal)
    target = parse_target(strategy.get("take_profit_rule", "2:1 RR"), entry, stop_loss)
    sizing = compute_position_size(capital, entry, stop_loss, risk_pct, num_trades)

    volume_above_avg = bool(
        signal.volume and signal.avg_volume and signal.volume > signal.avg_volume
    )
    low_volume = bool(
        signal.volume and signal.avg_volume and signal.volume < 0.5 * signal.avg_volume
    )
    red_flag = "Yes" if (low_volume or signal.recommendation in ("SELL", "STRONG_SELL")) else "No"

    return TradeRow(
        market_trend=signal.trend,
        stock=signal.symbol,
        red_flag=red_flag,
        entry_point="Good" if signal.price_position in ("Near support", "Breakout") else "Bad",
        promoter_holding="N/A",
        institutional_holdings="N/A",
        avg_volume="Good" if volume_above_avg else "Bad",
        macd_crossover="Yes" if signal.macd_crossover else "No",
        ema_crossover="Yes" if signal.ema_crossover else "No",
        price_position=signal.price_position,
        bullish_reversal="Yes" if signal.bullish_reversal else "No",
        entry_date=date.today().isoformat(),
        stop_loss=stop_loss,
        entry=round(entry, 2),
        target=target,
        quantity=sizing["ideal_qty"],
        confidence=decision.confidence,
        reasoning=decision.reasoning,
    )
