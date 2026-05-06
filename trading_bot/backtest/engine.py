from __future__ import annotations

from dataclasses import asdict

import pandas as pd

from trading_bot.backtest.indicators import build_feature_frame
from trading_bot.backtest.models import BacktestConfig, StrategyConfig, TradeRecord


def run_backtest(price_frames: dict[str, pd.DataFrame], strategy: StrategyConfig, config: BacktestConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    trades: list[TradeRecord] = []
    equity_points = []
    available_capital = config.initial_capital

    for symbol, df in price_frames.items():
        features = build_feature_frame(df, strategy)
        symbol_trades = _backtest_symbol(features, symbol, strategy, config, available_capital)
        trades.extend(symbol_trades)

    trades.sort(key=lambda trade: (trade.entry_date, -trade.score, trade.symbol))
    trades = _limit_open_positions(trades, config.max_open_positions)
    running_equity = config.initial_capital
    for trade in trades:
        running_equity += trade.pnl
        equity_points.append({"date": trade.exit_date, "equity": running_equity})

    trades_df = pd.DataFrame([asdict(trade) for trade in trades])
    equity_df = pd.DataFrame(equity_points or [{"date": config.start_date, "equity": config.initial_capital}])
    return trades_df, equity_df


def _backtest_symbol(features: pd.DataFrame, symbol: str, strategy: StrategyConfig, config: BacktestConfig, available_capital: float) -> list[TradeRecord]:
    trades: list[TradeRecord] = []
    last_exit_idx = -1

    for idx in range(max(strategy.trend_slow_ema, strategy.support_window), len(features) - 1):
        if idx <= last_exit_idx:
            continue
        row = features.iloc[idx]
        next_row = features.iloc[idx + 1]
        checks = _evaluate_checks(row, strategy)
        score = sum(item["passed"] for item in checks.values())
        if score < strategy.minimum_confidence:
            continue

        if strategy.direction == "LONG" and not checks["market_trend"]["passed"]:
            continue

        entry_price = float(next_row["open"])
        stop_loss = round(entry_price * (1 - strategy.stop_loss_pct / 100.0), 2)
        risk_per_share = entry_price - stop_loss
        if risk_per_share <= 0:
            continue
        max_position_risk = available_capital * (config.risk_pct / 100.0)
        quantity = int(max_position_risk // risk_per_share)
        if quantity <= 0:
            continue
        target_price = round(entry_price + risk_per_share * strategy.risk_reward_ratio, 2)

        exit_idx, exit_price = _resolve_exit(features, idx + 1, stop_loss, target_price, strategy.max_holding_days)
        last_exit_idx = exit_idx
        pnl = round((exit_price - entry_price) * quantity, 2)
        pnl_pct = round(((exit_price - entry_price) / entry_price) * 100.0, 2)
        confidence_label = _confidence_label(score)

        trades.append(TradeRecord(
            symbol=symbol,
            signal_date=row["date"].date(),
            entry_date=next_row["date"].date(),
            exit_date=features.iloc[exit_idx]["date"].date(),
            side="LONG",
            entry_price=round(entry_price, 2),
            exit_price=round(exit_price, 2),
            stop_loss=stop_loss,
            target_price=target_price,
            quantity=quantity,
            pnl=pnl,
            pnl_pct=pnl_pct,
            holding_days=max(1, exit_idx - (idx + 1) + 1),
            confidence=confidence_label,
            score=score,
            market_trend=checks["market_trend"]["label"],
            entry_point=checks["entry_point"]["label"],
            avg_volume=checks["avg_volume"]["label"],
            macd_crossover=checks["macd"]["label"],
            ema_crossover=checks["ema"]["label"],
            price_position=checks["support"]["label"],
            bullish_reversal=checks["reversal"]["label"],
            comments=f"Signal score {score}/{len(checks)}",
        ))
    return trades


def _evaluate_checks(row: pd.Series, strategy: StrategyConfig) -> dict[str, dict]:
    ema_cross = row["ema_signal_fast"] > row["ema_signal_slow"]
    macd_cross = row["macd_line"] > row["macd_signal"]
    trend = row["ema_trend_fast"] > row["ema_trend_slow"]
    near_support = abs((row["close"] - row["rolling_low"]) / row["close"]) * 100.0 <= strategy.support_threshold_pct
    good_volume = bool(row["avg_volume"]) and row["volume"] >= row["avg_volume"] * strategy.volume_multiplier
    bullish_reversal = bool(row["bullish_reversal"])
    breakout_52w = bool(row["rolling_52w_high"]) and row["close"] >= row["rolling_52w_high"]
    pullback_20dma = bool(row["ema_signal_fast"]) and row["low"] <= row["ema_signal_fast"] and row["close"] >= row["ema_signal_fast"]
    ema_trend_entry = ema_cross and trend and row["close"] > row["ema_signal_fast"]
    macd_trend_entry = macd_cross and trend
    rsi_reversal = pd.notna(row["rsi_14"]) and row["rsi_14"] <= 35 and bullish_reversal
    bollinger_reversion = pd.notna(row["bb_lower"]) and row["low"] <= row["bb_lower"] and row["close"] >= row["bb_lower"]
    support_breakout = pd.notna(row["breakout_level"]) and row["close"] > row["breakout_level"]
    volume_spike = pd.notna(row["volume_ratio"]) and row["volume_ratio"] >= 1.5
    gap_continuation = pd.notna(row["gap_pct"]) and row["gap_pct"] >= 1.0 and row["close"] > row["prev_high"]

    momentum_positive = bool(row["return_126"]) and bool(row["return_252"]) and row["return_126"] > 0 and row["return_252"] > 0
    momentum_strong = (
        momentum_positive and
        pd.notna(row["momentum_score"]) and
        pd.notna(row["momentum_score_ma"]) and
        row["momentum_score"] >= row["momentum_score_ma"]
    )

    if strategy.strategy_style in {"intraday_ma_crossover", "options_hedge"}:
        raise NotImplementedError(
            f"{strategy.strategy_style} is not supported by this daily stock backtester."
        )
    elif strategy.strategy_style in {"momentum_trend_following", "momentum_30"}:
        entry_point = momentum_strong and trend
        macd_label = "N/A"
        ema_label = "Trend OK" if trend else "Trend weak"
        support_label = "6M/12M momentum" if momentum_positive else "Momentum weak"
        reversal_label = "N/A"
        macd_passed = True
        ema_passed = trend
        support_passed = momentum_positive
        reversal_passed = True
    elif strategy.strategy_style == "swing_technical_indicators":
        entry_point = trend and good_volume and (near_support or pullback_20dma) and (macd_cross or bullish_reversal)
        macd_label = "MACD cross" if macd_cross else "No MACD cross"
        ema_label = "Trend OK" if trend else "Trend weak"
        support_label = "Support bounce" if (near_support or pullback_20dma) else "No bounce"
        reversal_label = "Bullish reversal" if bullish_reversal else "No reversal"
        macd_passed = macd_cross or not strategy.require_macd_crossover
        ema_passed = trend and ema_cross
        support_passed = near_support or pullback_20dma
        reversal_passed = bullish_reversal or not strategy.require_bullish_reversal
    elif strategy.strategy_style == "positional_44ema":
        ema_44 = pd.notna(row["ema_trend_fast"])
        entry_point = trend and ema_44 and row["close"] > row["ema_trend_fast"]
        macd_label = "N/A"
        ema_label = "Above 44 EMA" if ema_44 and row["close"] > row["ema_trend_fast"] else "Below 44 EMA"
        support_label = "Trend intact" if trend else "Trend weak"
        reversal_label = "N/A"
        macd_passed = True
        ema_passed = entry_point
        support_passed = trend
        reversal_passed = True
    elif strategy.strategy_style == "breakout_52w":
        entry_point = breakout_52w and good_volume and trend
        macd_label = "N/A"
        ema_label = "Trend OK" if trend else "Trend weak"
        support_label = "52-week breakout" if breakout_52w else "Below breakout"
        reversal_label = "N/A"
        macd_passed = True
        ema_passed = trend
        support_passed = breakout_52w
        reversal_passed = True
    elif strategy.strategy_style == "pullback_20dma":
        entry_point = pullback_20dma and trend and bullish_reversal
        macd_label = "Yes" if macd_cross else "No"
        ema_label = "Trend OK" if trend else "Trend weak"
        support_label = "20 DMA pullback" if pullback_20dma else "Away from 20 DMA"
        reversal_label = "Yes" if bullish_reversal else "No"
        macd_passed = macd_cross or not strategy.require_macd_crossover
        ema_passed = trend
        support_passed = pullback_20dma
        reversal_passed = bullish_reversal or not strategy.require_bullish_reversal
    elif strategy.strategy_style == "ema_crossover":
        entry_point = ema_trend_entry and good_volume
        macd_label = "N/A"
        ema_label = "Bullish crossover" if ema_cross else "No crossover"
        support_label = "Above fast EMA" if row["close"] > row["ema_signal_fast"] else "Below fast EMA"
        reversal_label = "N/A"
        macd_passed = True
        ema_passed = ema_trend_entry
        support_passed = row["close"] > row["ema_signal_fast"]
        reversal_passed = True
    elif strategy.strategy_style == "macd_crossover":
        entry_point = macd_trend_entry and good_volume
        macd_label = "Bullish cross" if macd_cross else "No cross"
        ema_label = "Trend OK" if trend else "Trend weak"
        support_label = "MACD confirmation"
        reversal_label = "N/A"
        macd_passed = macd_trend_entry
        ema_passed = trend
        support_passed = True
        reversal_passed = True
    elif strategy.strategy_style == "rsi_reversal":
        # Refined: RSI ≤ 40 (less strict than original 35) for more signals
        rsi_oversold_refined = pd.notna(row["rsi_14"]) and row["rsi_14"] <= 40
        entry_point = rsi_oversold_refined and bullish_reversal and trend
        macd_label = "N/A"
        ema_label = "Trend OK" if trend else "Trend weak"
        support_label = "RSI oversold" if rsi_oversold_refined else "RSI not oversold"
        reversal_label = "Bullish reversal" if bullish_reversal else "No reversal"
        macd_passed = True
        ema_passed = trend
        support_passed = rsi_oversold_refined
        reversal_passed = bullish_reversal
    elif strategy.strategy_style == "bollinger_reversion":
        entry_point = bollinger_reversion and bullish_reversal
        macd_label = "N/A"
        ema_label = "Mean reversion"
        support_label = "Lower band tag" if bollinger_reversion else "Inside bands"
        reversal_label = "Bullish reversal" if bullish_reversal else "No reversal"
        macd_passed = True
        ema_passed = True
        support_passed = bollinger_reversion
        reversal_passed = bullish_reversal
    elif strategy.strategy_style == "support_resistance_breakout":
        entry_point = support_breakout and good_volume and trend
        macd_label = "N/A"
        ema_label = "Trend OK" if trend else "Trend weak"
        support_label = "Resistance broken" if support_breakout else "Below resistance"
        reversal_label = "N/A"
        macd_passed = True
        ema_passed = trend
        support_passed = support_breakout
        reversal_passed = True
    elif strategy.strategy_style == "volume_spike_breakout":
        entry_point = support_breakout and volume_spike and trend
        macd_label = "N/A"
        ema_label = "Trend OK" if trend else "Trend weak"
        support_label = "Volume spike" if volume_spike else "Volume normal"
        reversal_label = "N/A"
        macd_passed = True
        ema_passed = trend
        support_passed = support_breakout and volume_spike
        reversal_passed = True
    elif strategy.strategy_style == "gap_up_continuation":
        entry_point = gap_continuation and good_volume and trend
        macd_label = "N/A"
        ema_label = "Trend OK" if trend else "Trend weak"
        support_label = "Gap-up continuation" if gap_continuation else "No gap confirmation"
        reversal_label = "N/A"
        macd_passed = True
        ema_passed = trend
        support_passed = gap_continuation
        reversal_passed = True
    elif strategy.strategy_style == "rsi_2_mean_reversion":
        # RSI(2) drops below 10 with price above 200 EMA — Larry Connors, ~76-79% win rate
        rsi2_oversold = pd.notna(row["rsi_2"]) and row["rsi_2"] < 10
        above_200ema = pd.notna(row["ema_trend_slow"]) and row["close"] > row["ema_trend_slow"]
        entry_point = rsi2_oversold and above_200ema and bullish_reversal
        macd_label = "N/A"
        ema_label = "Above 200 EMA" if above_200ema else "Below 200 EMA"
        support_label = f"RSI(2)={row['rsi_2']:.1f}" if pd.notna(row["rsi_2"]) else "N/A"
        reversal_label = "Bullish reversal" if bullish_reversal else "No reversal"
        macd_passed = True
        ema_passed = above_200ema
        support_passed = rsi2_oversold
        reversal_passed = bullish_reversal
    elif strategy.strategy_style == "rsi_pullback_uptrend":
        # RSI cools to 40-55 zone while price is in uptrend — 65-70% win rate
        rsi_cooling_zone = pd.notna(row["rsi_14"]) and 38 <= row["rsi_14"] <= 55
        above_50ema = pd.notna(row["ema_trend_fast"]) and row["close"] > row["ema_trend_fast"]
        near_20ema_pt = pullback_20dma or (
            pd.notna(row["ema_signal_fast"]) and
            abs(row["close"] - row["ema_signal_fast"]) / row["close"] * 100 <= 4.0
        )
        entry_point = rsi_cooling_zone and above_50ema and near_20ema_pt and bullish_reversal
        macd_label = "MACD cross" if macd_cross else "No MACD cross"
        ema_label = "Above 50 EMA" if above_50ema else "Below 50 EMA"
        support_label = f"RSI cooling ({row['rsi_14']:.0f})" if pd.notna(row["rsi_14"]) else "N/A"
        reversal_label = "Bullish reversal" if bullish_reversal else "No reversal"
        macd_passed = macd_cross or not strategy.require_macd_crossover
        ema_passed = above_50ema and near_20ema_pt
        support_passed = rsi_cooling_zone
        reversal_passed = bullish_reversal
    elif strategy.strategy_style == "consolidation_breakout":
        # Narrow-range consolidation breakout on above-average volume — 55-58% win rate
        was_consolidating = pd.notna(row["is_consolidating"]) and bool(row["is_consolidating"])
        breaking_out = support_breakout
        entry_point = was_consolidating and breaking_out and good_volume and trend
        macd_label = "N/A"
        ema_label = "Trend OK" if trend else "Trend weak"
        support_label = "Consolidation breakout" if (was_consolidating and breaking_out) else "No consolidation"
        reversal_label = "N/A"
        macd_passed = True
        ema_passed = trend
        support_passed = was_consolidating and breaking_out
        reversal_passed = True
    elif strategy.strategy_style == "pullback_50ema":
        # Pullback to 50 EMA in uptrend (price above 200 EMA) + reversal candle — 55-60% win rate
        above_200ema_p50 = pd.notna(row["ema_trend_slow"]) and row["close"] > row["ema_trend_slow"]
        at_50ema = pullback_20dma or (
            pd.notna(row["ema_trend_fast"]) and
            abs(row["close"] - row["ema_trend_fast"]) / row["close"] * 100 <= 3.0
        )
        entry_point = above_200ema_p50 and at_50ema and bullish_reversal
        macd_label = "MACD cross" if macd_cross else "No MACD cross"
        ema_label = "At 50 EMA" if at_50ema else "Away from 50 EMA"
        support_label = "Above 200 EMA" if above_200ema_p50 else "Below 200 EMA"
        reversal_label = "Bullish reversal" if bullish_reversal else "No reversal"
        macd_passed = macd_cross or not strategy.require_macd_crossover
        ema_passed = above_200ema_p50 and at_50ema
        support_passed = above_200ema_p50
        reversal_passed = bullish_reversal
    elif strategy.strategy_style == "sharique_swing":
        # Price above 50 EMA (trend filter) + pullback to 20 EMA + RSI cooling (40-60)
        # + bullish reversal candle + above-average volume
        rsi_cooling = pd.notna(row["rsi_14"]) and 35 <= row["rsi_14"] <= 60
        near_20ema = pullback_20dma or (
            pd.notna(row["ema_signal_fast"]) and
            abs(row["close"] - row["ema_signal_fast"]) / row["close"] * 100 <= 3.0
        )
        entry_point = trend and near_20ema and rsi_cooling and bullish_reversal and good_volume
        macd_label = "MACD cross" if macd_cross else "No MACD cross"
        ema_label = "Pullback to 20 EMA" if near_20ema else "Away from 20 EMA"
        support_label = "RSI cooling" if rsi_cooling else "RSI not in zone"
        reversal_label = "Bullish reversal" if bullish_reversal else "No reversal"
        macd_passed = macd_cross or not strategy.require_macd_crossover
        ema_passed = trend and near_20ema
        support_passed = rsi_cooling
        reversal_passed = bullish_reversal
    else:
        entry_point = ema_cross and near_support
        macd_label = "Yes" if macd_cross else "No"
        ema_label = "Yes" if ema_cross else "No"
        support_label = "Near support" if near_support else "Away from support"
        reversal_label = "Yes" if bullish_reversal else "No"
        macd_passed = macd_cross or not strategy.require_macd_crossover
        ema_passed = ema_cross or not strategy.require_ema_alignment
        support_passed = near_support or not strategy.require_support_bounce
        reversal_passed = bullish_reversal or not strategy.require_bullish_reversal

    return {
        "market_trend": {"passed": bool(trend), "label": "Up" if trend else "Down"},
        "entry_point": {"passed": bool(entry_point), "label": "Good" if entry_point else "Weak"},
        "avg_volume": {"passed": bool(good_volume or not strategy.require_volume_confirmation), "label": "Good" if good_volume else "Low"},
        "macd": {"passed": bool(macd_passed), "label": macd_label},
        "ema": {"passed": bool(ema_passed), "label": ema_label},
        "support": {"passed": bool(support_passed), "label": support_label},
        "reversal": {"passed": bool(reversal_passed), "label": reversal_label},
    }


def _resolve_exit(features: pd.DataFrame, entry_idx: int, stop_loss: float, target_price: float, max_holding_days: int) -> tuple[int, float]:
    final_idx = min(len(features) - 1, entry_idx + max_holding_days - 1)
    for idx in range(entry_idx, final_idx + 1):
        row = features.iloc[idx]
        if float(row["low"]) <= stop_loss:
            return idx, stop_loss
        if float(row["high"]) >= target_price:
            return idx, target_price
    return final_idx, float(features.iloc[final_idx]["close"])


def _confidence_label(score: int) -> str:
    if score >= 6:
        return "High"
    if score >= 4:
        return "Medium"
    return "Low"


def _limit_open_positions(trades: list[TradeRecord], max_open_positions: int) -> list[TradeRecord]:
    accepted: list[TradeRecord] = []
    open_trades: list[TradeRecord] = []

    for trade in trades:
        open_trades = [item for item in open_trades if item.exit_date >= trade.entry_date]
        if len(open_trades) >= max_open_positions:
            continue
        accepted.append(trade)
        open_trades.append(trade)

    return accepted
