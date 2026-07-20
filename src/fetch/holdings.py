"""Top-10-concentratie van de S&P 500 via ETF-holdings (IVV, fallback SPY).

Fragiele bron, en met een belangrijke beperking: deze bestanden geven alléén de holdings van
vandaag. Er is geen gratis historie, dus deze reeks begint op de dag van de eerste run en
groeit vanaf daar. Onder de 10-jaarsregel uit het design doc telt de indicator dus pas over
tien jaar mee in de scoring — zie README, dit is een bewuste, gedocumenteerde keuze en geen bug.
"""
from __future__ import annotations

import io
import logging
import os

import pandas as pd

from .base import http_get, to_series

log = logging.getLogger(__name__)

IVV_URL = (
    "https://www.ishares.com/us/products/239726/ishares-core-sp-500-etf/"
    "1467271812596.ajax?fileType=csv&fileName=IVV_holdings&dataType=fund"
)
SPY_URL = (
    "https://www.ssga.com/us/en/intermediary/library-content/products/fund-data/etfs/us/"
    "holdings-daily-us-en-spy.xlsx"
)

TOP_N = 10


def fetch(as_of: pd.Timestamp | None = None) -> pd.DataFrame:
    """Som van de tien grootste gewichten, als fractie (0-1), voor vandaag."""
    as_of = pd.Timestamp(as_of or pd.Timestamp.today()).normalize()

    # SSGA/SPY staat voorop: de iShares-ajax-URL levert sinds kort de productpagina in HTML
    # terug in plaats van een CSV. Hij blijft als terugvaloptie staan voor als dat weer omdraait.
    errors = []
    for label, loader in (("SPY", _from_ssga), ("IVV", _from_ishares)):
        try:
            weight = loader()
            log.info("Top-%d-concentratie via %s: %.1f%%", TOP_N, label, weight * 100)
            return to_series([as_of], [weight])
        except Exception as e:
            errors.append(f"{label} -> {type(e).__name__}: {e}")
            log.warning("Holdings-bron %s mislukt: %s", label, e)

    raise RuntimeError("Geen holdings-bron beschikbaar: " + " | ".join(errors))


def _from_ishares() -> float:
    text = http_get(os.environ.get("IVV_HOLDINGS_URL", IVV_URL)).text
    if text.lstrip()[:200].lower().startswith("<!doctype html") or "<html" in text[:500].lower():
        raise ValueError("iShares gaf HTML terug in plaats van een CSV")
    header_row = _find_header_row(text.splitlines())
    table = pd.read_csv(io.StringIO(text), skiprows=header_row)
    return _top_weight(table)


def _from_ssga() -> float:
    content = http_get(os.environ.get("SPY_HOLDINGS_URL", SPY_URL)).content
    raw = pd.read_excel(io.BytesIO(content), header=None)
    lines = [" ".join(str(c) for c in row) for _, row in raw.iterrows()]
    header_row = _find_header_row(lines)
    table = pd.read_excel(io.BytesIO(content), skiprows=header_row)
    return _top_weight(table)


def _find_header_row(lines: list[str], limit: int = 25) -> int:
    """De echte koprij bevat zowel 'ticker' als 'weight'.

    Op beide zoeken is nodig, niet netjes: de SSGA-sheet begint met een regel "Ticker Symbol: SPY",
    en alleen op 'ticker' matchen levert dus de verkeerde rij op.
    """
    for i, line in enumerate(lines[:limit]):
        lowered = line.lower()
        if "ticker" in lowered and "weight" in lowered:
            return i
    raise ValueError("Geen koprij met zowel 'ticker' als 'weight' gevonden in het holdings-bestand")


def _top_weight(table: pd.DataFrame) -> float:
    table.columns = [str(c).strip() for c in table.columns]

    weight_col = next((c for c in table.columns if "weight" in c.lower()), None)
    if weight_col is None:
        raise ValueError(f"Geen gewicht-kolom; gevonden: {list(table.columns)[:15]}")

    # Cash, futures en FX-regels horen niet in een concentratiemaat thuis.
    asset_col = next((c for c in table.columns if "asset class" in c.lower()), None)
    if asset_col is not None:
        table = table[table[asset_col].astype(str).str.strip().str.lower() == "equity"]

    weights = pd.to_numeric(
        table[weight_col].astype(str).str.replace("%", "", regex=False).str.replace(",", "", regex=False),
        errors="coerce",
    ).dropna()

    if len(weights) < 100:
        raise ValueError(f"Maar {len(weights)} holdings gevonden, dat is geen S&P 500-bestand")

    total = weights.sum()
    if not 95 <= total <= 105:
        raise ValueError(f"Gewichten sommeren tot {total:.1f}, verwacht ~100 — formaat gewijzigd?")

    return float(weights.nlargest(TOP_N).sum() / 100.0)
