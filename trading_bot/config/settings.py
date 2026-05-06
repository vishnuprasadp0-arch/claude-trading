import os
from pathlib import Path
import pytz
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent.parent

GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

EXCEL_PATH = Path(os.getenv("EXCEL_PATH", str(BASE_DIR / "SwingPlanner.xlsx")))

SYMBOLS: list[str] = [
    s.strip()
    for s in os.getenv("SYMBOLS", "RELIANCE,TCS,INFY,HDFCBANK,ICICIBANK").split(",")
    if s.strip()
]

EXCHANGE = "NSE"
SCREENER = "india"

IST = pytz.timezone("Asia/Kolkata")
MARKET_OPEN_H, MARKET_OPEN_M = 9, 15
MARKET_CLOSE_H, MARKET_CLOSE_M = 15, 30

DEFAULT_RISK_PCT = 2.0
DEFAULT_NUM_TRADES = 5

LOOP_INTERVAL_SECONDS = 300
