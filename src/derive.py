"""Afgeleide reeksen: alles wat uit de ruwe historie berekend wordt.

Deze reeksen worden elke run volledig herberekend uit de ruwe CSV's. Dat mag, want ze zijn een
deterministische functie van data die we al hadden — er sluipt geen toekomst in. Alle vensters
kijken uitsluitend achteruit.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from . import store
from .config import load_config

log = logging.getLogger(__name__)

TRADING_DAYS_6M = 126
TRADING_DAYS_52W = 252
MA_WINDOW = 200
HY_CHANGE_WINDOW = 63
MIN_SECTORS = 5

# Afgeleide reeksen die de scoring gebruikt, plus twee losse componenten voor het dashboard.
DERIVED = [
    "excess_cape_yield",
    "margin_debt_yoy",
    "vix_ratio",
    "sectors_above_200dma",
    "rsp_spy_6m",
    "hy_oas_63d",
    "baa_spread_63d",
    "trend_stress",
    "gspc_dist_200dma",
    "gspc_dd_52w",
]


def _series(name: str) -> pd.Series:
    """Historie als Series geïndexeerd op datum; leeg als de reeks ontbreekt."""
    df = store.read(name)
    if df.empty:
        return pd.Series(dtype="float64", index=pd.DatetimeIndex([], name="date"))
    return df.set_index("date")["value"].astype(float)


def _to_frame(s: pd.Series) -> pd.DataFrame:
    s = s.replace([np.inf, -np.inf], np.nan).dropna()
    return pd.DataFrame({"date": s.index, "value": s.values})


def run() -> dict[str, int]:
    """Bereken alle afgeleide reeksen en schrijf ze weg. Geeft naam -> nieuwe rijen."""
    written: dict[str, int] = {}
    for name, builder in _builders().items():
        try:
            series = builder()
        except Exception as e:
            log.warning("Afgeleide reeks %s mislukt (%s: %s), overgeslagen.", name, type(e).__name__, e)
            continue
        if series is None or series.empty:
            log.info("Afgeleide reeks %s heeft (nog) onvoldoende input.", name)
            continue
        written[name] = store.write_derived(name, _to_frame(series))
    return written


def _builders() -> dict[str, callable]:
    return {
        "excess_cape_yield": _excess_cape_yield,
        "margin_debt_yoy": _margin_debt_yoy,
        "vix_ratio": _vix_ratio,
        "sectors_above_200dma": _sectors_above_200dma,
        "rsp_spy_6m": _rsp_spy_6m,
        "hy_oas_63d": lambda: _change_63d("hy_oas"),
        "baa_spread_63d": lambda: _change_63d("baa_spread"),
        "gspc_dist_200dma": lambda: _trend_components()[0],
        "gspc_dd_52w": lambda: _trend_components()[1],
        "trend_stress": _trend_stress,
    }


def _excess_cape_yield() -> pd.Series:
    """ECY = CAPE-rendement (1/CAPE) minus de 10-jaars reële rente, in procentpunten.

    Gedateerd op de CAPE-datums (maandelijks). De reële rente wordt met een backward-asof
    gekoppeld: alleen de laatst bekende waarde op of vóór die datum, nooit een latere.
    """
    cape, real = _series("cape"), _series("real_10y")
    if cape.empty or real.empty:
        return pd.Series(dtype="float64")

    merged = pd.merge_asof(
        pd.DataFrame({"date": cape.index, "cape": cape.values}),
        pd.DataFrame({"date": real.index, "real": real.values}),
        on="date",
        direction="backward",
    ).dropna()

    ecy = 100.0 / merged["cape"] - merged["real"]
    return pd.Series(ecy.values, index=pd.DatetimeIndex(merged["date"]))


def _margin_debt_yoy() -> pd.Series:
    """Jaar-op-jaar groei van margin debt, in procenten.

    De reeks is al op publicatiedatum gezet, dus 12 stappen terug is 12 gepubliceerde maanden.
    """
    level = _series("margin_debt")
    if len(level) < 13:
        return pd.Series(dtype="float64")
    return (level / level.shift(12) - 1.0) * 100.0


def _vix_ratio() -> pd.Series:
    """VIX/VIX3M. Boven 1 = backwardation = de markt vreest nú meer dan straks."""
    vix, vix3m = _series("px_vix"), _series("px_vix3m")
    if vix.empty or vix3m.empty:
        return pd.Series(dtype="float64")
    aligned = pd.DataFrame({"vix": vix, "vix3m": vix3m}).dropna()
    return aligned["vix"] / aligned["vix3m"]


def _sectors_above_200dma() -> pd.Series:
    """Percentage sector-ETF's boven het eigen 200-daags gemiddelde.

    XLC bestaat pas sinds 2018 en XLRE sinds 2015; het percentage wordt daarom berekend over de
    sectoren die op dat moment bestonden, zolang er er minstens MIN_SECTORS beschikbaar zijn.
    """
    cfg = load_config()
    closes = {}
    for ticker in cfg["tickers"]["sectors"]:
        s = _series(f"px_{ticker.lower()}")
        if not s.empty:
            closes[ticker] = s
    if len(closes) < MIN_SECTORS:
        return pd.Series(dtype="float64")

    frame = pd.DataFrame(closes).sort_index()
    ma = frame.rolling(MA_WINDOW, min_periods=MA_WINDOW).mean()
    above = (frame > ma).where(ma.notna()).astype(float)  # NaN zolang een sector nog geen 200 dagen heeft

    counted = above.count(axis=1)
    valid = counted >= MIN_SECTORS  # in de eerste 200 dagen is dit nergens waar

    pct = pd.Series(np.nan, index=frame.index, dtype="float64")
    pct.loc[valid] = above.sum(axis=1)[valid] / counted[valid] * 100.0
    return pct.dropna()


def _rsp_spy_6m() -> pd.Series:
    """Relatieve 6-maands return van equal-weight (RSP) t.o.v. cap-weight (SPY), procentpunten."""
    rsp, spy = _series("px_rsp"), _series("px_spy")
    if rsp.empty or spy.empty:
        return pd.Series(dtype="float64")
    aligned = pd.DataFrame({"rsp": rsp, "spy": spy}).dropna()
    if len(aligned) <= TRADING_DAYS_6M:
        return pd.Series(dtype="float64")

    rsp_ret = aligned["rsp"] / aligned["rsp"].shift(TRADING_DAYS_6M) - 1.0
    spy_ret = aligned["spy"] / aligned["spy"].shift(TRADING_DAYS_6M) - 1.0
    return ((rsp_ret - spy_ret) * 100.0).dropna()


def _change_63d(name: str) -> pd.Series:
    """63-daagse verandering van een spreadreeks, in procentpunten."""
    spread = _series(name)
    if len(spread) <= HY_CHANGE_WINDOW:
        return pd.Series(dtype="float64")
    return (spread - spread.shift(HY_CHANGE_WINDOW)).dropna()


def _trend_components() -> tuple[pd.Series, pd.Series]:
    """Afstand tot het 200d gemiddelde en tot de 52-weeks high, beide in procenten."""
    index = _series("px_index")
    if len(index) < MA_WINDOW:
        empty = pd.Series(dtype="float64")
        return empty, empty

    ma200 = index.rolling(MA_WINDOW, min_periods=MA_WINDOW).mean()
    high52 = index.rolling(TRADING_DAYS_52W, min_periods=TRADING_DAYS_52W).max()

    dist = ((index / ma200) - 1.0) * 100.0
    drawdown = ((index / high52) - 1.0) * 100.0
    return dist.dropna(), drawdown.dropna()


def _trend_stress() -> pd.Series:
    """Samengestelde trendstress: hoger = zwakkere trend.

    Het gemiddelde van (min) de afstand tot het 200d gemiddelde en (min) de afstand tot de
    52-weeks high. Beide componenten zijn negatief in een downtrend, dus het omdraaien maakt
    er een stressmaat van die dezelfde richting op wijst als de rest van de stress-as.
    """
    dist, drawdown = _trend_components()
    if dist.empty or drawdown.empty:
        return pd.Series(dtype="float64")
    aligned = pd.DataFrame({"dist": dist, "dd": drawdown}).dropna()
    return -(0.5 * aligned["dist"] + 0.5 * aligned["dd"])
