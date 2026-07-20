"""FINRA margin debt (maandelijks).

Fragiele bron: FINRA verplaatst het bestand elke maand naar een nieuwe map en heeft de
kolomnamen in het verleden al meermaals gewijzigd. Daarom eerst de statistiekpagina scrapen
op een link naar het bestand, daarna een parser die kolommen op inhoud herkent in plaats van
op exacte naam. Bij twijfel: falen met een duidelijke logregel, niet gokken.

De historie zit in het bestand zelf, dus één succesvolle fetch vult de hele reeks.
De publicatielag (~1 maand na de meetmaand) wordt hier toegepast: een waarde over januari
telt pas mee vanaf de datum waarop FINRA hem publiceerde.
"""
from __future__ import annotations

import io
import logging
import os
import re

import pandas as pd

from ..config import load_config
from .base import http_get, to_series

log = logging.getLogger(__name__)

STATS_PAGES = [
    "https://www.finra.org/rules-guidance/key-topics/margin-accounts/margin-statistics",
    "https://www.finra.org/investors/insights/investing/margin-statistics",
]
FILE_LINK_RE = re.compile(r'href="([^"]*margin-statistics[^"]*\.(?:xlsx|xls|csv))"', re.IGNORECASE)


def fetch(start: str = "1900-01-01") -> pd.DataFrame:
    """Margin debt-niveau per maand, gedateerd op publicatiedatum."""
    errors = []
    for url in _candidate_urls():
        try:
            content = http_get(url).content
            df = _parse(url, content)
            log.info("FINRA margin debt via %s: %d maanden.", url, len(df))
            break
        except Exception as e:
            errors.append(f"{url} -> {type(e).__name__}: {e}")
            log.warning("FINRA-bron %s mislukt: %s", url, e)
    else:
        raise RuntimeError("Geen bruikbaar FINRA-bestand gevonden: " + " | ".join(errors))

    lag_days = load_config()["lags"]["margin_debt_days"]
    df["date"] = df["date"] + pd.offsets.MonthEnd(0) + pd.Timedelta(days=lag_days)
    return df[df["date"] >= pd.Timestamp(start)].reset_index(drop=True)


def _candidate_urls() -> list[str]:
    if os.environ.get("FINRA_MARGIN_URL"):
        return [os.environ["FINRA_MARGIN_URL"]]

    urls, errors = [], []
    for page in STATS_PAGES:
        try:
            html = http_get(page).text
        except Exception as e:
            errors.append(f"{page}: {e}")
            continue
        for href in FILE_LINK_RE.findall(html):
            full = href if href.startswith("http") else f"https://www.finra.org{href}"
            if full not in urls:
                urls.append(full)

    if not urls:
        raise RuntimeError("Geen link naar een margin-bestand gevonden; " + " | ".join(errors))
    log.info("FINRA: %d kandidaat-bestand(en) gevonden.", len(urls))
    return urls


def _parse(url: str, content: bytes) -> pd.DataFrame:
    if url.lower().endswith(".csv"):
        raw = pd.read_csv(io.BytesIO(content))
    else:
        sheets = pd.read_excel(io.BytesIO(content), sheet_name=None)
        raw = max(sheets.values(), key=len)  # het datablad is verreweg het grootste

    raw.columns = [str(c).strip() for c in raw.columns]

    period_col = _find_column(raw, ["year-month", "yearmonth", "month", "period", "date"])
    debit_col = _find_column(raw, ["debit balances", "debit balance", "margin debt", "debit"])
    if period_col is None or debit_col is None:
        raise ValueError(f"Kolommen niet herkend; gevonden: {list(raw.columns)[:15]}")

    dates = raw[period_col].map(_parse_period)
    values = raw[debit_col].map(_parse_amount)
    df = to_series(dates, values).dropna(subset=["date", "value"])
    if len(df) < 24:
        raise ValueError(f"Maar {len(df)} bruikbare maanden in het FINRA-bestand")
    return df.sort_values("date").reset_index(drop=True)


def _find_column(raw: pd.DataFrame, needles: list[str]) -> str | None:
    for needle in needles:  # volgorde is prioriteit: specifiek vóór generiek
        for col in raw.columns:
            if needle in str(col).lower():
                return col
    return None


def _parse_period(value) -> pd.Timestamp | None:
    """FINRA schrijft perioden als "2024-01", "Jan-24" of een echte datum."""
    if pd.isna(value):
        return None
    if isinstance(value, (pd.Timestamp,)):
        return pd.Timestamp(value).normalize().replace(day=1)
    text = str(value).strip()
    for fmt in ("%Y-%m", "%b-%y", "%B-%y", "%b-%Y", "%B %Y", "%m/%Y", "%Y-%m-%d"):
        try:
            return pd.Timestamp(pd.to_datetime(text, format=fmt)).replace(day=1)
        except (ValueError, TypeError):
            continue
    try:
        return pd.Timestamp(pd.to_datetime(text)).replace(day=1)
    except Exception:
        return None


def _parse_amount(value) -> float | None:
    """Bedragen komen soms als tekst met scheidingstekens binnen."""
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = re.sub(r"[^0-9.\-]", "", str(value))
    try:
        return float(cleaned)
    except ValueError:
        return None
