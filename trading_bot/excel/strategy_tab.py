import uuid
from datetime import datetime

from trading_bot.utils.logging import get_logger

logger = get_logger(__name__)

_SHEET = "Strategy"
_HEADERS = [
    "Strategy ID", "Name", "Source URL", "Active", "Timeframe",
    "Direction", "Indicators", "Entry Conditions", "Exit Conditions",
    "Stop Loss Rule", "Take Profit Rule", "Notes", "Date Added",
]


def ensure_strategy_tab(wb):
    if _SHEET not in wb.sheetnames:
        ws = wb.create_sheet(_SHEET)
        for col_idx, header in enumerate(_HEADERS, start=1):
            ws.cell(row=1, column=col_idx, value=header)
        logger.info("Strategy tab created")
    return wb[_SHEET]


def write_strategy(wb, strategy_dict: dict, url: str) -> str:
    ws = ensure_strategy_tab(wb)
    strategy_id = str(uuid.uuid4())[:8]
    row = _next_empty_row(ws)

    indicators = strategy_dict.get("indicators", [])
    entry_cond = strategy_dict.get("entry_conditions", [])
    exit_cond = strategy_dict.get("exit_conditions", [])

    ws.cell(row=row, column=1, value=strategy_id)
    ws.cell(row=row, column=2, value=strategy_dict.get("name", "Unknown"))
    ws.cell(row=row, column=3, value=url)
    ws.cell(row=row, column=4, value=False)
    ws.cell(row=row, column=5, value=strategy_dict.get("timeframe", "1d"))
    ws.cell(row=row, column=6, value=strategy_dict.get("direction", "LONG"))
    ws.cell(row=row, column=7, value=", ".join(indicators) if isinstance(indicators, list) else str(indicators))
    ws.cell(row=row, column=8, value="\n".join(entry_cond) if isinstance(entry_cond, list) else str(entry_cond))
    ws.cell(row=row, column=9, value="\n".join(exit_cond) if isinstance(exit_cond, list) else str(exit_cond))
    ws.cell(row=row, column=10, value=strategy_dict.get("stop_loss_rule", ""))
    ws.cell(row=row, column=11, value=strategy_dict.get("take_profit_rule", ""))
    ws.cell(row=row, column=12, value=strategy_dict.get("notes", ""))
    ws.cell(row=row, column=13, value=datetime.now().strftime("%Y-%m-%d %H:%M"))

    logger.info(f"Strategy '{strategy_dict.get('name')}' saved with ID {strategy_id}")
    return strategy_id


def get_active_strategy(wb) -> dict | None:
    if _SHEET not in wb.sheetnames:
        return None
    ws = wb[_SHEET]
    for row in range(2, ws.max_row + 1):
        active_val = ws.cell(row=row, column=4).value
        if active_val is True or str(active_val).strip().upper() == "TRUE":
            return {
                "id": ws.cell(row=row, column=1).value,
                "name": ws.cell(row=row, column=2).value,
                "url": ws.cell(row=row, column=3).value,
                "timeframe": ws.cell(row=row, column=5).value or "1d",
                "direction": ws.cell(row=row, column=6).value or "LONG",
                "indicators": _split_csv(ws.cell(row=row, column=7).value),
                "entry_conditions": _split_lines(ws.cell(row=row, column=8).value),
                "exit_conditions": _split_lines(ws.cell(row=row, column=9).value),
                "stop_loss_rule": ws.cell(row=row, column=10).value or "2% below entry",
                "take_profit_rule": ws.cell(row=row, column=11).value or "2:1 RR",
                "notes": ws.cell(row=row, column=12).value or "",
            }
    return None


def list_all_strategies(wb) -> list[dict]:
    """Return all rows from the Strategy tab as a list of dicts."""
    if _SHEET not in wb.sheetnames:
        return []
    ws = wb[_SHEET]
    rows = []
    for row in range(2, ws.max_row + 1):
        sid = ws.cell(row=row, column=1).value
        if not sid:
            continue
        active_val = ws.cell(row=row, column=4).value
        active = active_val is True or str(active_val).strip().upper() == "TRUE"
        rows.append({
            "id": sid,
            "name": ws.cell(row=row, column=2).value or "",
            "active": active,
            "timeframe": ws.cell(row=row, column=5).value or "",
            "direction": ws.cell(row=row, column=6).value or "",
            "date_added": ws.cell(row=row, column=13).value or "",
        })
    return rows


def _next_empty_row(ws) -> int:
    for row in range(2, ws.max_row + 2):
        if ws.cell(row=row, column=1).value in (None, ""):
            return row
    return ws.max_row + 1


def _split_csv(value) -> list[str]:
    return [s.strip() for s in str(value or "").split(",") if s.strip()]


def _split_lines(value) -> list[str]:
    return [s.strip() for s in str(value or "").splitlines() if s.strip()]
