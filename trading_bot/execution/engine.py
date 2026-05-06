from trading_bot.utils.logging import get_logger

logger = get_logger(__name__)


def run_once(_excel_path):
    raise RuntimeError(
        "The legacy live run path was removed because it depended on an unsupported market-data path. "
        "Use the Streamlit dashboard for PDF-driven backtesting and Zerodha-backed data."
    )


def run_loop(_excel_path):
    raise RuntimeError(
        "The legacy live run path was removed because it depended on an unsupported market-data path. "
        "Use the Streamlit dashboard for PDF-driven backtesting and Zerodha-backed data."
    )
