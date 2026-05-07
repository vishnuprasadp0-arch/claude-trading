from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Callable

import pandas as pd

from trading_bot.backtest.engine import evaluate_checks
from trading_bot.backtest.indicators import build_feature_frame
from trading_bot.backtest.models import StrategyConfig
from trading_bot.execution.models import TradeRow
from trading_bot.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PaperSignal:
    symbol: str
    signal_date: date
    close: float
    stop_loss: float
    target: float
    quantity: int
    score: int
    confidence: str
    market_trend: str
    entry_point: str
    avg_volume: str
    macd_crossover: str
    ema_crossover: str
    price_position: str
    bullish_reversal: str
    check_labels: dict


@dataclass
class ExitRecommendation:
    row: int              # Excel row number
    symbol: str
    entry: float
    stop_loss: float
    target: float
    quantity: int
    latest_close: float
    latest_date: date
    holding_days: int
    reason: str           # "HOLD" | "STOP_LOSS" | "TARGET" | "MAX_DAYS"
    pnl: float
    pnl_pct: float


def scan_signals(
    price_frames: dict[str, pd.DataFrame],
    strategy: StrategyConfig,
    capital: float,
    risk_pct: float,
    open_slots: int,
    on_progress: Callable | None = None,
) -> list[PaperSignal]:
    """
    Evaluate the strategy on the latest candle of each symbol.
    Returns up to open_slots signals, sorted by score descending.
    Pass open_slots=-1 to return all signals regardless of available slots.
    """
    signals: list[PaperSignal] = []
    symbols = list(price_frames.keys())

    for i, symbol in enumerate(symbols):
        try:
            df = price_frames.get(symbol)
            if df is None or len(df) < max(strategy.trend_slow_ema, 50):
                continue

            features = build_feature_frame(df, strategy)
            if features.empty:
                continue

            row = features.iloc[-1]
            checks = evaluate_checks(row, strategy)
            score = sum(c["passed"] for c in checks.values())

            if score < strategy.minimum_confidence:
                continue
            if strategy.direction == "LONG" and not checks["market_trend"]["passed"]:
                continue
            if not checks["entry_point"]["passed"]:
                continue

            entry = float(row["close"])
            stop_loss = round(entry * (1 - strategy.stop_loss_pct / 100.0), 2)
            risk_per_share = entry - stop_loss
            if risk_per_share <= 0:
                continue
            quantity = int((capital * risk_pct / 100.0) // risk_per_share)
            if quantity <= 0:
                continue
            target = round(entry + risk_per_share * strategy.risk_reward_ratio, 2)
            signal_date = row["date"].date() if hasattr(row["date"], "date") else row["date"]

            signals.append(PaperSignal(
                symbol=symbol,
                signal_date=signal_date,
                close=entry,
                stop_loss=stop_loss,
                target=target,
                quantity=quantity,
                score=score,
                confidence=_confidence_label(score),
                market_trend=checks["market_trend"]["label"],
                entry_point=checks["entry_point"]["label"],
                avg_volume=checks["avg_volume"]["label"],
                macd_crossover=checks["macd"]["label"],
                ema_crossover=checks["ema"]["label"],
                price_position=checks["support"]["label"],
                bullish_reversal=checks["reversal"]["label"],
                check_labels={k: v["label"] for k, v in checks.items()},
            ))

        except Exception as exc:
            logger.debug("Signal scan error %s: %s", symbol, exc)

        finally:
            if on_progress:
                on_progress(i + 1, len(symbols), symbol)

    signals.sort(key=lambda s: (-s.score, s.symbol))
    if open_slots >= 0:
        return signals[:open_slots]
    return signals


def evaluate_exits(
    open_trades: list[dict],
    price_frames: dict[str, pd.DataFrame],
    strategy: StrategyConfig,
    today: date,
) -> list[ExitRecommendation]:
    """Check each open trade against the latest available price."""
    recs: list[ExitRecommendation] = []

    for trade in open_trades:
        symbol = trade["stock"]
        df = price_frames.get(symbol)
        if df is None or df.empty:
            continue

        latest = df.iloc[-1]
        latest_close = float(latest["close"])
        latest_date = latest["date"].date() if hasattr(latest["date"], "date") else latest["date"]

        entry = float(trade.get("entry") or 0)
        stop_loss = float(trade.get("stop_loss") or 0)
        target = float(trade.get("target") or 0)
        quantity = int(trade.get("quantity") or 0)

        entry_date = trade.get("entry_date")
        if isinstance(entry_date, str):
            try:
                entry_date = datetime.fromisoformat(entry_date).date()
            except Exception:
                entry_date = today
        elif not isinstance(entry_date, date):
            entry_date = today

        holding_days = (today - entry_date).days

        if entry > 0 and latest_close <= stop_loss:
            reason = "STOP_LOSS"
        elif target > 0 and latest_close >= target:
            reason = "TARGET"
        elif holding_days >= strategy.max_holding_days:
            reason = "MAX_DAYS"
        else:
            reason = "HOLD"

        pnl = round((latest_close - entry) * quantity, 2) if entry else 0
        pnl_pct = round(((latest_close - entry) / entry) * 100, 2) if entry else 0

        recs.append(ExitRecommendation(
            row=trade["row"],
            symbol=symbol,
            entry=entry,
            stop_loss=stop_loss,
            target=target,
            quantity=quantity,
            latest_close=latest_close,
            latest_date=latest_date,
            holding_days=holding_days,
            reason=reason,
            pnl=pnl,
            pnl_pct=pnl_pct,
        ))

    return recs


def signal_to_trade_row(signal: PaperSignal) -> TradeRow:
    return TradeRow(
        market_trend=signal.market_trend,
        stock=signal.symbol,
        red_flag="No",
        entry_point=signal.entry_point,
        promoter_holding="N/A",
        institutional_holdings="N/A",
        avg_volume=signal.avg_volume,
        macd_crossover=signal.macd_crossover,
        ema_crossover=signal.ema_crossover,
        price_position=signal.price_position,
        bullish_reversal=signal.bullish_reversal,
        entry_date=signal.signal_date.isoformat(),
        stop_loss=signal.stop_loss,
        entry=signal.close,
        target=signal.target,
        quantity=signal.quantity,
        confidence=signal.confidence,
        reasoning=f"Paper trade | Score {signal.score}/7 | Signal {signal.signal_date}",
    )


def _confidence_label(score: int) -> str:
    if score >= 6:
        return "High"
    if score >= 4:
        return "Medium"
    return "Low"
