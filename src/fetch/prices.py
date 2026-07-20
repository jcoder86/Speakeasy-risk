"""Koersen via yfinance, met Stooq als terugvaloptie.

Yahoo is gratis maar niet contractueel betrouwbaar: het schema van yfinance verandert regelmatig
en de API rate-limit slaat zonder aankondiging toe. Vandaar de defensieve kolomafhandeling en de
Stooq-fallback. Voor ETF's gebruiken we voor dividend gecorrigeerde slotkoersen (auto_adjust),
zodat RSP/SPY een eerlijke relatieve return oplevert; voor indices maakt dat geen verschil.
"""
from __future__ import annotations

import io
import logging

import pandas as pd

from .base import http_get, to_series

log = logging.getLogger(__name__)

STOOQ_URL = "https://stooq.com/q/d/l/"

# Stooq hanteert eigen symbolen; alles wat hier niet in staat wordt "<ticker>.us".
STOOQ_SYMBOLS = {
    "^GSPC": "^spx",
    "^VIX": "^vix",
    "^VIX3M": "^vix3m",
}


def fetch(ticker: str, start: str = "1980-01-01") -> pd.DataFrame:
    """Slotkoersen voor één ticker. Probeert Yahoo, valt terug op Stooq."""
    try:
        df = _from_yahoo(ticker, start)
        if len(df) > 0:
            return df
        log.warning("Yahoo gaf geen rijen voor %s, probeer Stooq.", ticker)
    except Exception as e:
        log.warning("Yahoo faalde voor %s (%s: %s), probeer Stooq.", ticker, type(e).__name__, e)

    return _from_stooq(ticker, start)


def _from_yahoo(ticker: str, start: str) -> pd.DataFrame:
    import yfinance as yf

    raw = yf.download(
        ticker,
        start=start,
        auto_adjust=True,
        progress=False,
        actions=False,
        threads=False,
    )
    if raw is None or len(raw) == 0:
        return pd.DataFrame()

    close = _extract_close(raw, ticker)
    return to_series(close.index, close.values)


def _extract_close(raw: pd.DataFrame, ticker: str) -> pd.Series:
    """Haal de Close-kolom eruit, ongeacht of yfinance een MultiIndex teruggeeft."""
    if isinstance(raw.columns, pd.MultiIndex):
        for level in range(raw.columns.nlevels):
            values = raw.columns.get_level_values(level)
            if "Close" in set(values):
                sub = raw.xs("Close", axis=1, level=level)
                return sub[ticker] if ticker in sub.columns else sub.iloc[:, 0]
        raise ValueError(f"Geen Close-kolom in yfinance-respons voor {ticker}")

    for col in ("Close", "Adj Close"):
        if col in raw.columns:
            return raw[col]
    raise ValueError(f"Geen Close-kolom in yfinance-respons voor {ticker}")


def _from_stooq(ticker: str, start: str) -> pd.DataFrame:
    symbol = STOOQ_SYMBOLS.get(ticker, f"{ticker.lower()}.us")
    resp = http_get(STOOQ_URL, params={"s": symbol, "i": "d"})
    text = resp.text.strip()

    # Stooq antwoordt op een onbekend symbool met HTTP 200 en de tekst "No data".
    if not text or "No data" in text[:200] or "Date" not in text[:200]:
        raise ValueError(f"Stooq gaf geen data voor {symbol}")

    raw = pd.read_csv(io.StringIO(text))
    if "Close" not in raw.columns:
        raise ValueError(f"Stooq-respons voor {symbol} mist een Close-kolom")

    df = to_series(raw["Date"], raw["Close"])
    df = df[df["date"] >= pd.Timestamp(start)]
    log.info("Stooq %s: %d rijen.", symbol, len(df))
    return df
