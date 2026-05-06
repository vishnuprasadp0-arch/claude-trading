import logging
from pathlib import Path

_LOG_FILE = Path(__file__).resolve().parents[2] / "trading_bot.log"
_root_configured = False


def _configure_root() -> None:
    global _root_configured
    if _root_configured:
        return
    fmt = logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    root = logging.getLogger("trading_bot")
    root.setLevel(logging.DEBUG)

    # Console — INFO and above
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    root.addHandler(ch)

    # File — DEBUG and above (rotates at 5 MB, keeps 2 backups)
    from logging.handlers import RotatingFileHandler
    fh = RotatingFileHandler(_LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=2, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    root.addHandler(fh)

    root.propagate = False
    _root_configured = True


def get_logger(name: str) -> logging.Logger:
    _configure_root()
    return logging.getLogger(name)
