from __future__ import annotations

import re
from pathlib import Path

from trading_bot.backtest.models import StrategyConfig


def extract_pdf_text(pdf_path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    pages = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            pages.append(text.strip())
    return "\n\n".join(pages).strip()


def infer_strategy_config(raw_text: str) -> StrategyConfig:
    config = StrategyConfig()
    text = raw_text.lower()
    config.name = "The Complete Swing Trading Framework"
    config.notes = "Auto-inferred from PDF text. Review settings before running the backtest."

    ema_values = [int(value) for value in re.findall(r"(\d{1,3})\s*ema", text)]
    if len(ema_values) >= 2:
        ordered = sorted(set(ema_values))
        config.signal_fast_ema = ordered[0]
        config.signal_slow_ema = ordered[1]
        if len(ordered) >= 4:
            config.trend_fast_ema = ordered[-2]
            config.trend_slow_ema = ordered[-1]
        else:
            config.trend_fast_ema = max(config.signal_slow_ema, 50)
            config.trend_slow_ema = max(config.trend_fast_ema + 50, 200)

    rr_match = re.search(r"(\d+(?:\.\d+)?)\s*[:/]\s*1", text)
    if rr_match:
        config.risk_reward_ratio = float(rr_match.group(1))

    stop_match = re.search(r"stop\s*loss[^.\n]*?(\d+(?:\.\d+)?)\s*%", text)
    if stop_match:
        config.stop_loss_pct = float(stop_match.group(1))

    hold_match = re.search(r"hold(?:ing)?[^.\n]*?(\d{1,2})\s*(?:day|session|candle)", text)
    if hold_match:
        config.max_holding_days = int(hold_match.group(1))
    else:
        config.max_holding_days = 10

    if "52-week  high  breakout" in text or "52-week high breakout" in text:
        config.strategy_style = "breakout_52w"
        config.name = "52-Week High Breakout + Volume"
        config.require_support_bounce = False
        config.require_bullish_reversal = False
        config.require_macd_crossover = False
        config.require_ema_alignment = False
        config.require_volume_confirmation = True
        config.risk_reward_ratio = max(config.risk_reward_ratio, 2.0)
    elif "mean-reversion  pullback  to  20-dma" in text or "mean-reversion pullback to 20-dma" in text:
        config.strategy_style = "pullback_20dma"
        config.name = "Mean-Reversion Pullback to 20 DMA"
        config.signal_fast_ema = 20
        config.require_support_bounce = True
        config.require_bullish_reversal = True
    elif "momentum  30" in text or "momentum 30" in text:
        config.strategy_style = "momentum_30"
        config.name = "NIFTY 200 Momentum 30"
        config.require_support_bounce = False
        config.require_bullish_reversal = False
        config.require_macd_crossover = False
        config.require_ema_alignment = False
        config.require_volume_confirmation = False
        config.max_holding_days = 20
        config.risk_reward_ratio = 1.5
    else:
        config.strategy_style = "ema_macd_custom"

    config.raw_source_excerpt = raw_text[:4000]
    return config
