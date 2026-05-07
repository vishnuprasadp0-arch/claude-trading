from __future__ import annotations

import pandas as pd

from trading_bot.backtest.models import StrategyConfig


def build_feature_frame(df: pd.DataFrame, config: StrategyConfig) -> pd.DataFrame:
    frame = df.copy().sort_values("date").reset_index(drop=True)
    frame["ema_signal_fast"] = frame["close"].ewm(span=config.signal_fast_ema, adjust=False).mean()
    frame["ema_signal_slow"] = frame["close"].ewm(span=config.signal_slow_ema, adjust=False).mean()
    frame["ema_trend_fast"] = frame["close"].ewm(span=config.trend_fast_ema, adjust=False).mean()
    frame["ema_trend_slow"] = frame["close"].ewm(span=config.trend_slow_ema, adjust=False).mean()

    macd_fast = frame["close"].ewm(span=config.macd_fast, adjust=False).mean()
    macd_slow = frame["close"].ewm(span=config.macd_slow, adjust=False).mean()
    frame["macd_line"] = macd_fast - macd_slow
    frame["macd_signal"] = frame["macd_line"].ewm(span=config.macd_signal, adjust=False).mean()
    frame["macd_hist"] = frame["macd_line"] - frame["macd_signal"]
    frame["macd_hist_prev"] = frame["macd_hist"].shift(1)

    frame["avg_volume"] = frame["volume"].rolling(config.volume_window).mean()
    frame["volume_ratio"] = frame["volume"] / frame["avg_volume"].replace(0, pd.NA)
    frame["rolling_low"] = frame["low"].rolling(config.support_window).min()
    frame["rolling_high"] = frame["high"].rolling(config.support_window).max()
    frame["rolling_52w_high"] = frame["high"].rolling(252).max().shift(1)
    frame["rolling_52w_low"] = frame["low"].rolling(252).min().shift(1)
    frame["return_126"] = frame["close"] / frame["close"].shift(126) - 1.0
    frame["return_252"] = frame["close"] / frame["close"].shift(252) - 1.0
    frame["volatility_126"] = frame["close"].pct_change().rolling(126).std() * (126 ** 0.5)
    frame["momentum_score"] = (frame["return_126"] + frame["return_252"]) / frame["volatility_126"].replace(0, pd.NA)
    frame["momentum_score_ma"] = frame["momentum_score"].rolling(20).mean()
    frame["rsi_14"] = _rsi(frame["close"], 14)
    rolling_mean = frame["close"].rolling(20).mean()
    rolling_std = frame["close"].rolling(20).std()
    frame["bb_mid"] = rolling_mean
    frame["bb_upper"] = rolling_mean + (2 * rolling_std)
    frame["bb_lower"] = rolling_mean - (2 * rolling_std)
    frame["prev_open"] = frame["open"].shift(1)
    frame["prev_close"] = frame["close"].shift(1)
    frame["prev_low"] = frame["low"].shift(1)
    frame["prev_high"] = frame["high"].shift(1)
    frame["gap_pct"] = (frame["open"] / frame["prev_close"] - 1.0) * 100.0
    frame["breakout_level"] = frame["rolling_high"].shift(1)

    frame["bullish_engulfing"] = (
        (frame["prev_close"] < frame["prev_open"]) &
        (frame["close"] > frame["open"]) &
        (frame["close"] >= frame["prev_open"]) &
        (frame["open"] <= frame["prev_close"])
    )
    frame["hammer"] = (
        ((frame["high"] - frame["low"]) > 0) &
        ((frame["close"] - frame["open"]).abs() <= (frame["high"] - frame["low"]) * 0.35) &
        ((frame[["open", "close"]].min(axis=1) - frame["low"]) >= (frame["high"] - frame["low"]) * 0.45)
    )
    frame["bullish_reversal"] = frame["bullish_engulfing"] | frame["hammer"]

    # ── Extended candlestick patterns (used by Vishnu Trading Strategy) ──────
    body = (frame["close"] - frame["open"]).abs()
    candle_range = frame["high"] - frame["low"]
    upper_wick = frame["high"] - frame[["open", "close"]].max(axis=1)
    lower_wick = frame[["open", "close"]].min(axis=1) - frame["low"]

    frame["inverted_hammer"] = (
        (frame["prev_close"] < frame["prev_open"]) &   # prior candle bearish
        (candle_range > 0) &
        (body <= candle_range * 0.35) &                # small real body
        (upper_wick >= body * 2.0) &                   # long upper wick
        (lower_wick <= body * 0.1)                     # minimal lower wick
    )

    # Morning Star: 3-candle — needs prev-2 data via double shift
    prev2_open = frame["open"].shift(2)
    prev2_close = frame["close"].shift(2)
    prev2_body = (prev2_close - prev2_open).abs()
    prev_body = (frame["prev_close"] - frame["prev_open"]).abs()
    prev_candle_range = (frame["prev_high"] - frame["prev_low"])
    frame["morning_star"] = (
        (prev2_close < prev2_open) &                               # candle-2 bearish
        (prev_body <= prev_candle_range * 0.3) &                   # candle-1 small (indecision)
        (frame["close"] > frame["open"]) &                         # today bullish
        (frame["close"] > (prev2_open + prev2_close) / 2)          # closes above midpoint of candle-2
    )

    frame["piercing_line"] = (
        (frame["prev_close"] < frame["prev_open"]) &               # prior bearish
        (frame["open"] < frame["prev_low"]) &                      # gap down open
        (frame["close"] > frame["open"]) &                         # today bullish
        (frame["close"] > (frame["prev_open"] + frame["prev_close"]) / 2) &  # closes above midpoint
        (frame["close"] < frame["prev_open"])                      # but not full engulf
    )

    prev2_close_bull = frame["close"].shift(2)
    prev2_open_bull = frame["open"].shift(2)
    frame["three_white_soldiers"] = (
        (prev2_close_bull > prev2_open_bull) &                     # candle-2 bullish
        (frame["prev_close"] > frame["prev_open"]) &               # candle-1 bullish
        (frame["close"] > frame["open"]) &                         # today bullish
        (frame["close"] > frame["prev_close"]) &                   # each higher than last
        (frame["prev_close"] > prev2_close_bull) &
        # each closes in upper half of its range
        (frame["close"] >= frame["low"] + (frame["high"] - frame["low"]) * 0.6) &
        (frame["prev_close"] >= frame["prev_low"] + (frame["prev_high"] - frame["prev_low"]) * 0.6)
    )

    frame["double_bottom"] = (
        (frame["low"] <= frame["rolling_low"] * 1.01) &            # near prior rolling low
        (frame["close"] > frame["prev_close"]) &                   # bouncing up
        (frame["close"] > frame["open"])                           # bullish candle
    )

    frame["strong_bullish_pattern"] = (
        frame["morning_star"] |
        frame["piercing_line"] |
        frame["three_white_soldiers"] |
        frame["bullish_engulfing"] |
        frame["double_bottom"]
    )

    frame["rsi_2"] = _rsi(frame["close"], 2)
    frame["atr_14"] = _atr(frame["high"], frame["low"], frame["close"], 14)
    # Narrow range: 10-day close range relative to 20-day average — used for consolidation detection
    frame["range_10d"] = frame["close"].rolling(10).max() - frame["close"].rolling(10).min()
    frame["range_20d_avg"] = (frame["high"] - frame["low"]).rolling(20).mean()
    frame["is_consolidating"] = (
        frame["range_10d"] <= frame["range_20d_avg"] * 2.5
    ) & (
        frame["range_10d"] / frame["close"] * 100 <= 8.0
    )

    return frame


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


def resample_to_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """Resample daily OHLCV to weekly (week ending Friday). Drops incomplete weeks."""
    w = df.copy()
    w["date"] = pd.to_datetime(w["date"])
    w = w.set_index("date")
    weekly = w.resample("W-FRI").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).dropna(subset=["close"]).reset_index()
    return weekly


def _rsi(series: pd.Series, period: int) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    return 100 - (100 / (1 + rs))
