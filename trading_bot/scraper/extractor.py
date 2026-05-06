import json
import re

from groq import Groq

from trading_bot.config.settings import GROQ_API_KEY, GROQ_MODEL
from trading_bot.utils.logging import get_logger

logger = get_logger(__name__)

_SYSTEM_PROMPT = """You are an expert at extracting trading strategies from YouTube video transcripts.
The transcript may be in Malayalam, English, or a mix of both — extract the strategy and respond ONLY in English.

Analyze the transcript and return ONLY a valid JSON object with exactly these fields (no markdown, no extra text):
{
  "name": "Strategy name (concise, in English)",
  "timeframe": "1d, 1h, 4h, 15m, etc.",
  "direction": "LONG or SHORT or BOTH",
  "indicators": ["indicator1", "indicator2"],
  "entry_conditions": ["condition 1", "condition 2"],
  "exit_conditions": ["condition 1", "condition 2"],
  "stop_loss_rule": "e.g. 2% below entry or below recent swing low",
  "take_profit_rule": "e.g. 2:1 RR or 5% above entry",
  "notes": "any extra context translated to English"
}"""


def extract_strategy(transcript: str, url: str, title: str) -> dict:
    client = Groq(api_key=GROQ_API_KEY)
    user_content = (
        f"Video Title: {title}\n"
        f"Source URL: {url}\n\n"
        f"Transcript (may be in Malayalam):\n{transcript[:12000]}"
    )
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0.1,
        max_tokens=1024,
    )
    raw = response.choices[0].message.content.strip()
    return _parse_json(raw)


def _parse_json(raw: str) -> dict:
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"\s*```$", "", raw, flags=re.MULTILINE)
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse strategy JSON: {e}\nRaw output: {raw[:400]}")
        raise ValueError(f"LLM returned invalid JSON: {e}")
