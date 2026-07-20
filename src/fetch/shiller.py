"""Shiller-dataset (ie_data.xls): maandelijkse CAPE sinds 1881.

De Excel verhuist regelmatig van URL en heeft koppen die over meerdere rijen lopen. Daarom:
een lijst kandidaat-URL's en een parser die de koprij zelf opzoekt in plaats van een vaste
rij-index te vertrouwen. De Excess CAPE Yield wordt niet hier maar in derive.py berekend,
omdat die de FRED-reeks DFII10 nodig heeft.
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

LANDING_PAGE = "https://shillerdata.com/"
LINK_RE = re.compile(r'href="([^"]*ie_data\.xls[^"]*)"', re.IGNORECASE)

# Terugvaloptie als de landingspagina onbereikbaar is. Let op: de blob-URL bevat een versie-id
# dat bij elke maandelijkse update verandert, dus deze lijst veroudert per definitie — hij is
# een vangnet, niet de hoofdroute.
FALLBACK_URLS = [
    "http://www.econ.yale.edu/~shiller/data/ie_data.xls",
    "https://www.econ.yale.edu/~shiller/data/ie_data.xls",
]


def fetch(start: str = "1900-01-01") -> pd.DataFrame:
    """CAPE per maand, gedateerd op de publicatiedatum (maandeinde + lag)."""
    urls = [os.environ["SHILLER_URL"]] if os.environ.get("SHILLER_URL") else _discover_urls()

    errors = []
    for url in urls:
        try:
            content = http_get(url).content
            df = _parse(content)
            log.info("Shiller CAPE via %s: %d maanden.", url, len(df))
            break
        except Exception as e:
            errors.append(f"{url} -> {type(e).__name__}: {e}")
            log.warning("Shiller-bron %s mislukt: %s", url, e)
    else:
        raise RuntimeError("Alle Shiller-bronnen faalden: " + " | ".join(errors))

    lag_days = load_config()["lags"]["cape_days"]
    df["date"] = df["date"] + pd.offsets.MonthEnd(0) + pd.Timedelta(days=lag_days)
    return df[df["date"] >= pd.Timestamp(start)].reset_index(drop=True)


def _discover_urls() -> list[str]:
    """Zoek de actuele downloadlink op shillerdata.com; val terug op de bekende Yale-URL's."""
    try:
        html = http_get(LANDING_PAGE).text
    except Exception as e:
        log.warning("Shiller-landingspagina onbereikbaar (%s), alleen fallbacks.", e)
        return list(FALLBACK_URLS)

    found = []
    for href in LINK_RE.findall(html):
        if href.startswith("//"):  # protocol-relatief, zo staat de blob-link op de pagina
            full = f"https:{href}"
        elif href.startswith("http"):
            full = href
        else:
            full = f"https://shillerdata.com/{href.lstrip('/')}"
        if full not in found:
            found.append(full)

    log.info("Shiller: %d downloadlink(s) op de landingspagina gevonden.", len(found))
    return found + FALLBACK_URLS


def _parse(content: bytes) -> pd.DataFrame:
    sheets = pd.read_excel(io.BytesIO(content), sheet_name=None, header=None)
    sheet = sheets.get("Data")
    if sheet is None:
        raise ValueError(f"Sheet 'Data' ontbreekt; gevonden: {list(sheets)}")

    # De sheet heeft koppen over meerdere rijen, en meer dan één rij bevat de tekst "Date":
    # boven de fractionele datumkolom staat óók "Date". Daarom proberen we elke kandidaat en
    # accepteren we pas een parse die er als een echte maandreeks uitziet.
    errors = []
    for header_row in _candidate_header_rows(sheet):
        try:
            return _parse_with_header(sheet, header_row)
        except ValueError as e:
            errors.append(f"koprij {header_row}: {e}")

    raise ValueError("Geen bruikbare koprij in de Shiller-sheet — " + "; ".join(errors))


def _candidate_header_rows(sheet: pd.DataFrame) -> list[int]:
    rows = [
        i
        for i in range(min(20, len(sheet)))
        if "date" in {str(c).strip().lower() for c in sheet.iloc[i]}
    ]
    if not rows:
        raise ValueError("Geen koprij met 'Date' gevonden in de Shiller-sheet")
    # Van onder naar boven: de echte kolomlabels staan direct boven de data.
    return sorted(rows, reverse=True)


def _parse_with_header(sheet: pd.DataFrame, header_row: int) -> pd.DataFrame:
    table = sheet.iloc[header_row + 1 :].copy()
    table.columns = [str(c).strip() for c in sheet.iloc[header_row]]

    date_col = _find_column(table, lambda c: c.lower() == "date")
    cape_col = _find_column(
        table,
        lambda c: "cape" in c.lower() and "tr" not in c.lower(),
    ) or _find_column(table, lambda c: "p/e10" in c.lower().replace(" ", ""))
    if date_col is None or cape_col is None:
        raise ValueError(f"Date- of CAPE-kolom ontbreekt; kolommen: {list(table.columns)[:20]}")

    dates = _column(table, date_col).map(_parse_shiller_date)
    df = to_series(dates, _column(table, cape_col)).dropna(subset=["date", "value"])
    _validate(df)
    return df.reset_index(drop=True)


def _column(table: pd.DataFrame, name: str) -> pd.Series:
    """De Shiller-sheet heeft dubbele kolomnamen; pak dan de eerste."""
    col = table[name]
    return col.iloc[:, 0] if isinstance(col, pd.DataFrame) else col


def _validate(df: pd.DataFrame) -> None:
    """Een geldige parse is een lange, oplopende reeks met stappen van ongeveer een maand.

    Dit is de vangrail tegen de fractionele datumkolom: die levert scheve, botsende datums op
    en haalt deze controle niet.
    """
    if len(df) < 1000:
        raise ValueError(f"maar {len(df)} rijen, verwacht >1000 maanden sinds 1881")

    dates = pd.DatetimeIndex(df["date"])
    if not dates.is_monotonic_increasing:
        raise ValueError("datums lopen niet oplopend")

    median_gap = pd.Series(dates).diff().dt.days.median()
    if not 28 <= median_gap <= 31:
        raise ValueError(f"mediane stap is {median_gap} dagen, dat is geen maandreeks")


def _find_column(table: pd.DataFrame, predicate) -> str | None:
    for col in table.columns:
        if predicate(str(col)):
            return col
    return None


def _parse_shiller_date(value) -> pd.Timestamp | None:
    """Shiller codeert maanden als 2020.01 t/m 2020.12.

    Let op: 2020.10 is als float gelijk aan 2020.1. Formatteren op twee decimalen herstelt de
    maand correct — "2020.10" is oktober, "2020.01" is januari.
    """
    try:
        year_str, month_str = f"{float(value):.2f}".split(".")
        year, month = int(year_str), int(month_str)
    except (TypeError, ValueError):
        return None
    if not 1 <= month <= 12 or not 1800 <= year <= 2200:
        return None
    return pd.Timestamp(year=year, month=month, day=1)
