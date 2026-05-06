from __future__ import annotations

import io
import json
import time
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

from trading_bot.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ZerodhaCredentials:
    api_key: str
    access_token: str


class HistoricalDataProvider:
    name: str = "unknown"

    def available(self) -> bool:
        raise NotImplementedError

    def get_daily_history(self, symbol: str, start_date: date, end_date: date) -> pd.DataFrame:
        raise NotImplementedError


class KiteHistoricalDataProvider:
    name = "zerodha"

    def __init__(self, cache_dir: Path, credentials: ZerodhaCredentials | None = None):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.credentials = credentials
        self._kite = None
        self._instrument_map: dict[str, int] | None = None

    def available(self) -> bool:
        return bool(self.credentials and self.credentials.api_key and self.credentials.access_token)

    def get_daily_history(self, symbol: str, start_date: date, end_date: date) -> pd.DataFrame:
        cache_file = self.cache_dir / f"{symbol}_{start_date}_{end_date}.csv"
        if cache_file.exists():
            return self._read_cached_csv(cache_file)
        if not self.available():
            raise RuntimeError("Zerodha credentials are not configured.")
        df = self._download_history(symbol, start_date, end_date)
        df.to_csv(cache_file, index=False)
        return df

    def _download_history(self, symbol: str, start_date: date, end_date: date) -> pd.DataFrame:
        from kiteconnect import KiteConnect

        if self._kite is None:
            self._kite = KiteConnect(api_key=self.credentials.api_key)
            self._kite.set_access_token(self.credentials.access_token)

        token = self._resolve_instrument_token(symbol)
        candles = self._kite.historical_data(
            instrument_token=token,
            from_date=start_date,
            to_date=end_date,
            interval="day",
            continuous=False,
            oi=False,
        )
        if not candles:
            raise RuntimeError(f"No daily candles returned for {symbol}.")
        df = pd.DataFrame(candles)
        df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
        return df[["date", "open", "high", "low", "close", "volume"]]

    def _resolve_instrument_token(self, symbol: str) -> int:
        if self._instrument_map is None:
            self._instrument_map = self._load_instrument_map()
        try:
            return self._instrument_map[symbol]
        except KeyError as exc:
            raise RuntimeError(f"Instrument token not found for {symbol}.") from exc

    def _load_instrument_map(self) -> dict[str, int]:
        assert self._kite is not None
        snapshot_file = self.cache_dir / "nse_instruments.json"
        if snapshot_file.exists():
            payload = json.loads(snapshot_file.read_text())
            snapshot_date = payload.get("snapshot_date")
            if snapshot_date == datetime.utcnow().date().isoformat():
                return {key: int(value) for key, value in payload["instrument_map"].items()}

        instruments = self._kite.instruments("NSE")
        instrument_map = {
            row["tradingsymbol"]: int(row["instrument_token"])
            for row in instruments
            if row.get("segment") == "NSE"
        }
        snapshot_file.write_text(json.dumps({
            "snapshot_date": datetime.utcnow().date().isoformat(),
            "instrument_map": instrument_map,
        }))
        return instrument_map

    @staticmethod
    def _read_cached_csv(cache_file: Path) -> pd.DataFrame:
        df = pd.read_csv(cache_file, parse_dates=["date"])
        return df[["date", "open", "high", "low", "close", "volume"]]


class NseBhavcopyDataProvider(HistoricalDataProvider):
    name = "nse_bhavcopy"
    _BASE_URL = "https://nsearchives.nseindia.com/content/cm"
    _HEADERS = {
        "User-Agent": "TradingBacktester/1.0 (Python requests)",
        "Accept-Language": "en-US,en;q=0.9",
    }
    _COLUMN_ALIASES = {
        "symbol": ["TckrSymb", "SYMBOL", "symbol"],
        "open": ["OpnPric", "OPEN", "open"],
        "high": ["HghPric", "HIGH", "high"],
        "low": ["LwPric", "LOW", "low"],
        "close": ["ClsPric", "CLOSE", "close"],
        "volume": ["TtlTradgVol", "TOTTRDQTY", "volume"],
    }

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir / "nse_bhavcopy"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._session = requests.Session()
        self._session.headers.update(self._HEADERS)

    def available(self) -> bool:
        return True

    @property
    def _holiday_cache_file(self) -> Path:
        return self.cache_dir / "_nse_holidays.json"

    def get_known_holidays(self) -> set[date]:
        if not self._holiday_cache_file.exists():
            return set()
        import json
        raw = json.loads(self._holiday_cache_file.read_text())
        return {date.fromisoformat(d) for d in raw}

    def _record_holiday(self, trade_date: date) -> None:
        import json
        holidays = self.get_known_holidays()
        holidays.add(trade_date)
        self._holiday_cache_file.write_text(json.dumps(sorted(d.isoformat() for d in holidays)))

    def get_cached_dates(self) -> set[date]:
        cached: set[date] = set()
        # New format: BhavCopy_NSE_CM_0_0_0_YYYYMMDD_F_0000.csv
        for f in self.cache_dir.glob("BhavCopy_NSE_CM_0_0_0_*_F_0000.csv"):
            parts = f.stem.split("_")
            try:
                date_str = parts[6]  # YYYYMMDD
                cached.add(date(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8])))
            except (IndexError, ValueError):
                pass
        # Old format: cmDDMMMYYYYBHAV.CSV (e.g. cm01NOV2023bhav.csv stored uppercase)
        for f in self.cache_dir.glob("CM*BHAV.CSV"):
            try:
                stem = f.stem  # e.g. CM01NOV2023BHAV
                date_part = stem[2:11]  # DDMMMYYYY
                cached.add(datetime.strptime(date_part, "%d%b%Y").date())
            except ValueError:
                pass
        return cached

    def get_coverage_stats(self, years: int = 3) -> dict:
        end = date.today()
        start = end.replace(year=end.year - years)
        weekdays: set[date] = set()
        current = start
        while current <= end:
            if current.weekday() < 5:
                weekdays.add(current)
            current += timedelta(days=1)

        cached_all = self.get_cached_dates()
        holidays = self.get_known_holidays()
        cached_in_range = cached_all & weekdays
        # "Missing" = weekdays we haven't downloaded AND haven't confirmed as holidays
        missing = sorted(weekdays - cached_in_range - holidays)
        # "Available" = cached trading days + confirmed holidays (both are accounted for)
        available = cached_in_range | (holidays & weekdays)
        total = len(weekdays)
        coverage_pct = len(available) / total * 100 if total else 0.0

        return {
            "start": start,
            "end": end,
            "expected": total,
            "cached": len(cached_in_range),
            "holidays": len(holidays & weekdays),
            "missing": missing,
            "coverage_pct": coverage_pct,
            "earliest": min(cached_all) if cached_all else None,
            "latest": max(cached_all) if cached_all else None,
        }

    def download_bulk(self, missing_dates: list[date], on_progress=None) -> tuple[int, int]:
        downloaded = skipped = 0
        logger.info("Bulk download started: %d dates to fetch.", len(missing_dates))
        for i, d in enumerate(missing_dates):
            result = self._load_bhavcopy_for_date(d)
            if result is not None:
                downloaded += 1
                logger.debug("Downloaded %s (%d/%d)", d, i + 1, len(missing_dates))
            else:
                skipped += 1
                logger.debug("Skipped %s — holiday or unavailable (%d/%d)", d, i + 1, len(missing_dates))
            if on_progress:
                on_progress(i + 1, len(missing_dates), d)
        logger.info("Bulk download done: %d downloaded, %d skipped.", downloaded, skipped)
        return downloaded, skipped

    def get_daily_history(self, symbol: str, start_date: date, end_date: date) -> pd.DataFrame:
        cache_file = self.cache_dir / f"{symbol}_{start_date}_{end_date}.csv"
        if cache_file.exists():
            return KiteHistoricalDataProvider._read_cached_csv(cache_file)

        rows: list[dict] = []
        current = start_date
        while current <= end_date:
            if current.weekday() < 5:
                row = self._get_symbol_row_for_date(symbol, current)
                if row:
                    rows.append(row)
            current += timedelta(days=1)

        if not rows:
            raise RuntimeError(f"No NSE bhavcopy rows found for {symbol} between {start_date} and {end_date}.")

        df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
        df.to_csv(cache_file, index=False)
        return df

    def _get_symbol_row_for_date(self, symbol: str, trade_date: date) -> dict | None:
        bhavcopy = self._load_bhavcopy_for_date(trade_date)  # already EQ-filtered for old format
        if bhavcopy is None or bhavcopy.empty:
            return None

        symbol_column = self._resolve_column(bhavcopy.columns, "symbol")
        matches = bhavcopy[bhavcopy[symbol_column].astype(str).str.upper() == symbol.upper()]
        if matches.empty:
            return None

        row = matches.iloc[0]
        return {
            "date": pd.Timestamp(trade_date),
            "open": float(row[self._resolve_column(bhavcopy.columns, "open")]),
            "high": float(row[self._resolve_column(bhavcopy.columns, "high")]),
            "low": float(row[self._resolve_column(bhavcopy.columns, "low")]),
            "close": float(row[self._resolve_column(bhavcopy.columns, "close")]),
            "volume": float(row[self._resolve_column(bhavcopy.columns, "volume")]),
        }

    # NSE changed archive URL format around Jan 2024.
    # New (2024+): content/cm/BhavCopy_NSE_CM_0_0_0_YYYYMMDD_F_0000.csv.zip
    # Old (≤2023): content/historical/EQUITIES/YYYY/MMM/cmDDMMMYYYYbhav.csv.zip
    _OLD_BASE_URL = "https://nsearchives.nseindia.com/content/historical/EQUITIES"

    def _load_bhavcopy_for_date(self, trade_date: date) -> pd.DataFrame | None:
        # Check both possible cache filenames
        new_cache = self.cache_dir / f"BhavCopy_NSE_CM_0_0_0_{trade_date:%Y%m%d}_F_0000.csv"
        old_cache = self.cache_dir / f"cm{trade_date:%d%b%Y}bhav.csv".upper()
        if new_cache.exists():
            return pd.read_csv(new_cache)
        if old_cache.exists():
            return self._read_old_bhavcopy(old_cache)

        # Try new URL format first (2024+), fall back to old format (≤2023)
        urls = [
            (f"{self._BASE_URL}/BhavCopy_NSE_CM_0_0_0_{trade_date:%Y%m%d}_F_0000.csv.zip", new_cache, False),
            (f"{self._OLD_BASE_URL}/{trade_date.year}/{trade_date:%b}".upper()[:0]  # dummy
             or f"{self._OLD_BASE_URL}/{trade_date.year}/{trade_date.strftime('%b').upper()}"
                f"/cm{trade_date.strftime('%d%b%Y').upper()}bhav.csv.zip",
             old_cache, True),
        ]

        for url, cache_file, is_old_format in urls:
            data = self._fetch_zip(url, trade_date)
            if data is None:
                continue
            cache_file.write_bytes(data)
            time.sleep(0.1)
            df = pd.read_csv(io.BytesIO(data))
            return self._read_old_bhavcopy_df(df) if is_old_format else df

        # Both URLs returned 404 — confirmed NSE holiday or exchange closure
        self._record_holiday(trade_date)
        logger.debug("Recorded %s as NSE holiday (both URLs returned 404).", trade_date)
        return None

    def _fetch_zip(self, url: str, trade_date: date) -> bytes | None:
        logger.debug("GET %s", url)
        for attempt in range(3):
            try:
                response = self._session.get(url, timeout=60)
                if response.status_code == 404:
                    logger.debug("404 for %s — holiday or no file.", trade_date)
                    return None
                response.raise_for_status()
                with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                    csv_names = [n for n in archive.namelist() if n.lower().endswith(".csv")]
                    if not csv_names:
                        logger.warning("No CSV inside zip for %s", trade_date)
                        return None
                    logger.debug("Fetched %s OK (%d bytes)", trade_date, len(response.content))
                    return archive.read(csv_names[0])
            except requests.exceptions.Timeout:
                if attempt == 2:
                    logger.warning("Timeout %s after 3 attempts — skipping.", trade_date)
                    return None
                wait = 2 ** attempt
                logger.warning("Timeout %s attempt %d — retrying in %ds…", trade_date, attempt + 1, wait)
                time.sleep(wait)
            except Exception as exc:
                logger.warning("Error fetching %s: %s", trade_date, exc)
                return None
        return None

    def _read_old_bhavcopy(self, cache_file: Path) -> pd.DataFrame:
        return self._read_old_bhavcopy_df(pd.read_csv(cache_file))

    def _read_old_bhavcopy_df(self, df: pd.DataFrame) -> pd.DataFrame:
        # Old bhavcopy has EQ/BE/etc series rows — keep only EQ
        if "SERIES" in df.columns:
            df = df[df["SERIES"].astype(str).str.strip() == "EQ"]
        return df

    def _resolve_column(self, columns: pd.Index, logical_name: str) -> str:
        for alias in self._COLUMN_ALIASES[logical_name]:
            if alias in columns:
                return alias
        raise RuntimeError(f"Expected {logical_name} column not found in NSE bhavcopy: {list(columns)}")
