from trading_bot.execution.models import TradeRow
from trading_bot.utils.logging import get_logger

logger = get_logger(__name__)

_SHEET = "System"
_TRADE_START = 19
_TRADE_END = 49
_COL_STOCK = 2  # B


def read_capital_settings(wb) -> dict:
    ws = wb[_SHEET]
    return {
        "capital": float(ws["B3"].value or 100_000),
        "risk_pct": float(ws["B6"].value or 2.0),
        "num_trades": int(ws["B7"].value or 5),
    }


def find_next_trade_row(ws) -> int:
    for row in range(_TRADE_START, _TRADE_END + 1):
        if ws.cell(row=row, column=_COL_STOCK).value in (None, ""):
            return row
    raise RuntimeError(
        f"Trade log full (rows {_TRADE_START}–{_TRADE_END}). Clear completed trades first."
    )


def append_trade_row(wb, trade: TradeRow) -> int:
    ws = wb[_SHEET]
    row = find_next_trade_row(ws)

    # Columns A–Q (1–17), then V (22) for reasoning. T/U (20–21) are never written.
    col_values = [
        trade.market_trend,           # A=1
        trade.stock,                  # B=2
        trade.red_flag,               # C=3
        trade.entry_point,            # D=4
        trade.promoter_holding,       # E=5
        trade.institutional_holdings, # F=6
        trade.avg_volume,             # G=7
        trade.macd_crossover,         # H=8
        trade.ema_crossover,          # I=9
        trade.price_position,         # J=10
        trade.bullish_reversal,       # K=11
        trade.entry_date,             # L=12
        trade.stop_loss,              # M=13
        trade.entry,                  # N=14
        trade.target,                 # O=15
        trade.quantity,               # P=16
        trade.confidence,             # Q=17
    ]
    for col_idx, value in enumerate(col_values, start=1):
        ws.cell(row=row, column=col_idx, value=value)

    ws.cell(row=row, column=22, value=trade.reasoning)  # V
    logger.info(f"Trade appended: {trade.stock} @ row {row}")
    return row


def read_open_trades(wb) -> list[dict]:
    ws = wb[_SHEET]
    open_trades = []
    for row in range(_TRADE_START, _TRADE_END + 1):
        stock = ws.cell(row=row, column=2).value
        exit_price = ws.cell(row=row, column=18).value  # R
        if stock and not exit_price:
            open_trades.append({
                "row": row,
                "stock": stock,
                "market_trend": ws.cell(row=row, column=1).value,
                "entry_date": ws.cell(row=row, column=12).value,
                "stop_loss": ws.cell(row=row, column=13).value,
                "entry": ws.cell(row=row, column=14).value,
                "target": ws.cell(row=row, column=15).value,
                "quantity": ws.cell(row=row, column=16).value,
                "confidence": ws.cell(row=row, column=17).value,
            })
    return open_trades
