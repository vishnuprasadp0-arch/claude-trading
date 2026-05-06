import platform
import threading
from pathlib import Path

import openpyxl

from trading_bot.utils.logging import get_logger

logger = get_logger(__name__)

_lock = threading.Lock()

try:
    import xlwings as xw
    _XLWINGS_AVAILABLE = True
except ImportError:
    _XLWINGS_AVAILABLE = False


class WorkbookManager:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._wb = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.save()
        self.close()

    def open(self):
        _lock.acquire()
        self._wb = openpyxl.load_workbook(self.path)
        return self._wb

    def save(self):
        self._wb.save(self.path)
        logger.info(f"Workbook saved: {self.path}")
        if _XLWINGS_AVAILABLE and platform.system() in ("Windows", "Darwin"):
            self._try_xlwings_refresh()

    def close(self):
        self._wb = None
        _lock.release()

    def _try_xlwings_refresh(self):
        try:
            active_app = xw.apps.active
            if active_app:
                for book in active_app.books:
                    if Path(book.fullname).resolve() == self.path.resolve():
                        book.app.calculate()
        except Exception as e:
            logger.debug(f"xlwings refresh skipped: {e}")

    @property
    def workbook(self):
        return self._wb
