import json
import re

from groq import Groq

from trading_bot.data.models import Signal
from trading_bot.strategy.models import TradeDecision
from trading_bot.config.settings import GROQ_API_KEY, GROQ_MODEL
from trading_bot.utils.logging import get_logger

logger = get_logger(__name__)


def evaluate(signal: Signal, strategy: dict) -> TradeDecision:
    if not _rule_based(signal, strategy):
        return TradeDecision(
            symbol=signal.symbol,
            action="SKIP",
            confidence="Low",
            reasoning="Rule-based filter: no entry conditions met",
        )

    result = _llm_analysis(signal, strategy)
    action = result.get("action", "HOLD")
    confidence = result.get("confidence", "Low")
    reasoning = result.get("reasoning", "")

    if action != "BUY" or confidence == "Low":
        return TradeDecision(
            symbol=signal.symbol,
            action="SKIP",
            confidence=confidence,
            reasoning=reasoning,
        )

    return TradeDecision(
        symbol=signal.symbol,
        action="BUY",
        confidence=confidence,
        reasoning=reasoning,
    )


def _rule_based(signal: Signal, strategy: dict) -> bool:
    indicators = " ".join(strategy.get("indicators", [])).lower()
    conditions = " ".join(strategy.get("entry_conditions", [])).lower()
    combined = indicators + " " + conditions

    checks = []
    if "macd" in combined:
        checks.append(signal.macd_crossover)
    if "ema" in combined or "moving average" in combined:
        checks.append(signal.ema_crossover)
    if "rsi" in combined and signal.rsi is not None:
        threshold = 30 if ("oversold" in combined or "below 30" in combined) else (40 if "below 40" in combined else 50)
        checks.append(signal.rsi < threshold)
    if "bullish" in combined or "reversal" in combined:
        checks.append(signal.bullish_reversal)

    # No detectable conditions — let LLM decide
    if not checks:
        return True
    return any(checks)


def _llm_analysis(signal: Signal, strategy: dict) -> dict:
    system_msg = (
        f"You are a trading signal analyst. Evaluate whether to enter a trade.\n"
        f"Strategy: {strategy.get('name', 'Unknown')}\n"
        f"Timeframe: {strategy.get('timeframe', '1d')} | Direction: {strategy.get('direction', 'LONG')}\n"
        f"Entry conditions: {'; '.join(strategy.get('entry_conditions', []))}\n"
        f"Stop loss rule: {strategy.get('stop_loss_rule', 'N/A')}\n"
        f"Take profit rule: {strategy.get('take_profit_rule', 'N/A')}\n\n"
        'Respond ONLY with a JSON object: {"action": "BUY or HOLD", "confidence": "High or Medium or Low", "reasoning": "brief explanation"}'
    )

    snapshot = (
        f"Symbol: {signal.symbol}\n"
        f"Close: {signal.close}\n"
        f"RSI: {signal.rsi}\n"
        f"MACD: {signal.macd} | Signal line: {signal.macd_signal}\n"
        f"EMA10: {signal.ema10} | EMA20: {signal.ema20} | EMA50: {signal.ema50}\n"
        f"MACD crossover: {signal.macd_crossover}\n"
        f"EMA crossover: {signal.ema_crossover}\n"
        f"Price position: {signal.price_position}\n"
        f"Bullish reversal: {signal.bullish_reversal}\n"
        f"Recommendation: {signal.recommendation}\n"
        f"Volume vs 20d avg: {'Above' if (signal.volume and signal.avg_volume and signal.volume > signal.avg_volume) else 'Below or unknown'}"
    )

    try:
        client = Groq(api_key=GROQ_API_KEY)
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": snapshot},
            ],
            temperature=0.1,
            max_tokens=256,
        )
        raw = response.choices[0].message.content.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
        raw = re.sub(r"\s*```$", "", raw, flags=re.MULTILINE)
        return json.loads(raw.strip())
    except Exception as e:
        logger.error(f"LLM analysis failed for {signal.symbol}: {e}")
        return {"action": "HOLD", "confidence": "Low", "reasoning": f"LLM error: {e}"}
