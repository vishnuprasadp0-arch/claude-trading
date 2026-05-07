from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Callable

import pandas as pd

from trading_bot.backtest.data import NseBhavcopyDataProvider
from trading_bot.backtest.engine import evaluate_checks
from trading_bot.backtest.indicators import build_feature_frame
from trading_bot.backtest.models import StrategyConfig
from trading_bot.backtest.universe import NIFTY_50_SYMBOLS
from trading_bot.paper_trading.engine import PaperTradingEngine
from trading_bot.utils.logging import get_logger

logger = get_logger(__name__)

_CACHE_DIR = Path(__file__).resolve().parents[2] / "trading_bot" / "data" / "cache"


def get_latest_price(symbol: str, provider: NseBhavcopyDataProvider | None = None) -> float | None:
    """Fetch the latest close price for a symbol from Bhavcopy cache."""
    if provider is None:
        provider = NseBhavcopyDataProvider(cache_dir=_CACHE_DIR)
    try:
        df = provider.get_daily_history(symbol, date.today() - timedelta(days=10), date.today())
        if df is not None and not df.empty:
            return float(df.iloc[-1]["close"])
    except Exception as exc:
        logger.debug("Could not fetch price for %s: %s", symbol, exc)
    return None


def get_latest_prices(symbols: list[str], provider: NseBhavcopyDataProvider | None = None) -> dict[str, float]:
    """Fetch latest close prices for a list of symbols."""
    if provider is None:
        provider = NseBhavcopyDataProvider(cache_dir=_CACHE_DIR)
    prices: dict[str, float] = {}
    for sym in symbols:
        p = get_latest_price(sym, provider)
        if p is not None:
            prices[sym] = p
    return prices


def scan_signals(
    strategy: StrategyConfig,
    provider: NseBhavcopyDataProvider | None = None,
    lookback_days: int = 300,
    on_progress: Callable | None = None,
) -> list[dict]:
    """
    Scan NIFTY 50 for strategy signals on the latest available candle.
    Returns a list of signal dicts with entry, stop_loss, target, qty, score, confidence.
    """
    if provider is None:
        provider = NseBhavcopyDataProvider(cache_dir=_CACHE_DIR)

    scan_start = date.today() - timedelta(days=lookback_days)
    scan_end = date.today()
    signals = []

    for i, symbol in enumerate(NIFTY_50_SYMBOLS):
        try:
            df = provider.get_daily_history(symbol, scan_start, scan_end)
            if df is None or len(df) < max(strategy.trend_slow_ema, 50):
                continue

            if strategy.timeframe == "week":
                from trading_bot.backtest.indicators import resample_to_weekly
                df = resample_to_weekly(df)

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
            target = round(entry + risk_per_share * strategy.risk_reward_ratio, 2)
            signal_date = row["date"].date() if hasattr(row["date"], "date") else row["date"]

            confidence = "High" if score >= 6 else ("Medium" if score >= 4 else "Low")
            signals.append({
                "symbol": symbol,
                "signal_date": str(signal_date),
                "entry": entry,
                "stop_loss": stop_loss,
                "target": target,
                "score": score,
                "confidence": confidence,
                "market_trend": checks["market_trend"]["label"],
                "macd": checks["macd"]["label"],
                "ema": checks["ema"]["label"],
                "volume": checks["avg_volume"]["label"],
                "reversal": checks["reversal"]["label"],
            })

        except Exception as exc:
            logger.debug("Scan error %s: %s", symbol, exc)

        finally:
            if on_progress:
                on_progress(i + 1, len(NIFTY_50_SYMBOLS), symbol)

    signals.sort(key=lambda s: (-s["score"], s["symbol"]))
    return signals


def enter_signal_trade(
    engine: PaperTradingEngine,
    signal: dict,
    provider: NseBhavcopyDataProvider | None = None,
    strategy_name: str = "",
) -> dict:
    """
    Place and immediately fill a MARKET BUY order for a signal.
    Fill price = latest Bhavcopy close.
    Returns a result dict with status and details.
    """
    symbol = signal["symbol"]
    fill_price = get_latest_price(symbol, provider)
    if fill_price is None:
        return {"status": "error", "message": f"No price data available for {symbol}"}

    portfolio = engine.get_portfolio()
    stop_loss = signal.get("stop_loss", fill_price * 0.95)
    risk_per_share = fill_price - stop_loss
    if risk_per_share <= 0:
        return {"status": "error", "message": f"Invalid stop loss for {symbol}"}

    max_risk = portfolio.cash * (engine.risk_pct / 100.0)
    qty = int(max_risk // risk_per_share)
    if qty <= 0:
        return {"status": "error", "message": f"Insufficient capital for {symbol} (need at least ₹{fill_price * 1:,.0f})"}

    cost = qty * fill_price
    if cost > portfolio.cash:
        qty = int(portfolio.cash // fill_price)
        if qty <= 0:
            return {"status": "error", "message": f"Insufficient cash (₹{portfolio.cash:,.0f}) to buy {symbol}"}

    try:
        order = engine.place_order(
            symbol=symbol,
            side="BUY",
            qty=qty,
            order_type="MARKET",
            stop_loss=signal.get("stop_loss"),
            target_price=signal.get("target"),
            strategy=strategy_name,
            notes=f"Signal score {signal.get('score', 0)}/7",
        )
        engine.fill_market_order(order.id, fill_price)
        return {
            "status": "ok",
            "message": f"Bought {qty} × {symbol} @ ₹{fill_price:,.2f}",
            "symbol": symbol, "qty": qty, "fill_price": fill_price,
        }
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def close_position(
    engine: PaperTradingEngine,
    symbol: str,
    provider: NseBhavcopyDataProvider | None = None,
    exit_reason: str = "MANUAL",
) -> dict:
    """Close an open position at the latest Bhavcopy close price."""
    pos = engine.get_position(symbol)
    if not pos:
        return {"status": "error", "message": f"No open position for {symbol}"}

    fill_price = get_latest_price(symbol, provider)
    if fill_price is None:
        return {"status": "error", "message": f"No price data for {symbol}"}

    try:
        order = engine.place_order(
            symbol=symbol, side="SELL", qty=pos.qty,
            order_type="MARKET",
            notes=f"Manual close via dashboard",
        )
        engine.fill_market_order(order.id, fill_price)
        pnl = round((fill_price - pos.avg_entry_price) * pos.qty, 2)
        return {
            "status": "ok",
            "message": f"Closed {pos.qty} × {symbol} @ ₹{fill_price:,.2f} | P&L: ₹{pnl:+,.0f}",
            "pnl": pnl,
        }
    except Exception as exc:
        return {"status": "error", "message": str(exc)}
