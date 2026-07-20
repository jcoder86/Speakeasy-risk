"""Scoring-engine: point-in-time percentielen, pijlerscores, assen, regime en analogen.

Percentielen zijn per constructie point-in-time: een expanderend venster kan niet in de
toekomst kijken. Het venster gebruikt de volledige eigen historie van een indicator (voor
CAPE dus terug tot 1881, voor NFCI tot 1971): juist die lange verdeling is de voorspellende
kracht. Scores en regimes worden pas vanaf `history.start` (1990) berekend.

Indicatoren vallen uit en komen erbij (VIX3M bestaat pas sinds 2006, RSP sinds 2003, en de
10-jaarsregel houdt jonge reeksen buiten de deur). Gewichten worden dan hernormaliseerd over
wat er wél is, zodat een pijler of as nooit halfleeg is. Welke onderdelen wanneer meetelden
wordt in de validatie (fase 3) gerapporteerd.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from . import store
from .config import indicator_specs, load_config

log = logging.getLogger(__name__)

TRADING_DAYS_1M = 21

QUADRANT = {
    (False, False): "calm",
    (True, False): "fragile_calm",
    (False, True): "shock",
    (True, True): "storm",
}

REGIME_LABELS_NL = {
    "calm": "Kalm",
    "fragile_calm": "Fragiele rust",
    "shock": "Schok",
    "storm": "Storm",
}


def risk_percentile(s: pd.Series, direction: str, min_years: int) -> pd.Series:
    """Expanderend percentiel (0-100) van een reeks, gedraaid naar risico-richting.

    Elke waarde wordt gerangschikt binnen alle observaties tot en met dat moment — nooit
    later. De eerste `min_years` jaar levert geen output: zo'n jong percentiel is ruis.
    """
    s = s.dropna()
    if s.empty:
        return pd.Series(dtype="float64")

    pct = s.expanding(min_periods=1).rank(pct=True) * 100.0
    cutoff = s.index[0] + pd.DateOffset(years=min_years)
    pct = pct[pct.index >= cutoff]
    return (100.0 - pct) if direction == "low" else pct


def indicator_percentiles() -> pd.DataFrame:
    """Dagelijkse risicopercentielen per scoring-indicator op een business-day-grid.

    Percentielen worden op de eigen frequentie van de indicator berekend (maandelijks voor
    CAPE) en daarna forward-filled — zo telt een maandwaarde één keer mee in de verdeling,
    niet dertig keer.
    """
    cfg = load_config()
    min_years = int(cfg["history"]["min_years"])
    start = pd.Timestamp(cfg["history"]["start"])

    native: dict[str, pd.Series] = {}
    for name, spec in indicator_specs().items():
        df = store.read(name)
        if df.empty:
            log.info("Indicator %s heeft geen historie en blijft leeg.", name)
            continue
        pct = risk_percentile(df.set_index("date")["value"], spec["direction"], min_years)
        if pct.empty:
            log.info("Indicator %s heeft nog geen %d jaar historie.", name, min_years)
        else:
            native[name] = pct

    if not native:
        return pd.DataFrame()

    end = max(s.index.max() for s in native.values())
    grid = pd.bdate_range(start, end)
    out = pd.DataFrame(index=grid)
    for name, pct in native.items():
        out[name] = pct.reindex(grid.union(pct.index)).ffill().reindex(grid)
    out.index.name = "date"
    return out


def _weighted_mean(values: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    """Gewogen gemiddelde per rij; gewichten hernormaliseren over niet-NaN kolommen."""
    cols = [c for c in weights if c in values.columns]
    if not cols:
        return pd.Series(np.nan, index=values.index, dtype="float64")

    w = pd.Series({c: float(weights[c]) for c in cols})
    present = values[cols].notna()
    weight_sum = present.mul(w, axis=1).sum(axis=1)
    total = values[cols].fillna(0.0).mul(w, axis=1).sum(axis=1)
    return (total / weight_sum).where(weight_sum > 0)


def pillar_scores(pcts: pd.DataFrame) -> pd.DataFrame:
    cfg = load_config()
    out = pd.DataFrame(index=pcts.index)
    for pillar, pcfg in cfg["pillars"].items():
        weights = {name: icfg["weight"] for name, icfg in pcfg["indicators"].items()}
        out[pillar] = _weighted_mean(pcts, weights)
    return out


def axis_scores(pillars: pd.DataFrame, axis_weights: dict[str, dict[str, float]] | None = None) -> pd.DataFrame:
    """Asscores; `axis_weights` overschrijft de config (voor de sensitiviteitsanalyse)."""
    weights_by_axis = axis_weights or load_config()["axes"]
    out = pd.DataFrame(index=pillars.index)
    for axis, weights in weights_by_axis.items():
        out[axis] = _weighted_mean(pillars, weights)
    return out


def _schmitt(value: float, was_high: bool, threshold: float, exit_margin: float) -> bool:
    """Tweezijdige drempel: hoog worden bij >= drempel, pas terugvallen onder (drempel - marge).

    Zonder deze marge flippert een as die rond de drempel schommelt op weekschaal heen en
    weer — de 5-dagen-hysterese vangt alleen dag-geflipper af.
    """
    return value >= (threshold - exit_margin if was_high else threshold)


def regime_series(
    axes: pd.DataFrame,
    threshold: float | None = None,
    hysteresis: int | None = None,
    exit_margin: float | None = None,
) -> pd.DataFrame:
    """Regime per dag, met hysterese: een wissel vereist `hysteresis_days` opeenvolgende
    dagen in het nieuwe kwadrant. `regime_since` is de eerste dag van die reeks."""
    rcfg = load_config()["regime"]
    threshold = float(rcfg["high_threshold"] if threshold is None else threshold)
    hysteresis = int(rcfg["hysteresis_days"] if hysteresis is None else hysteresis)
    exit_margin = float(rcfg.get("exit_margin", 0) if exit_margin is None else exit_margin)

    valid = axes.dropna(subset=["fragility", "stress"])
    regimes: list[str] = []
    sinces: list[pd.Timestamp] = []

    current = candidate = None
    since = streak_start = None
    streak = 0
    frag_high = stress_high = False

    for date, row in valid.iterrows():
        frag_high = _schmitt(row["fragility"], frag_high, threshold, exit_margin)
        stress_high = _schmitt(row["stress"], stress_high, threshold, exit_margin)
        quad = QUADRANT[(frag_high, stress_high)]
        if current is None:
            current, since = quad, date
        elif quad == current:
            candidate, streak = None, 0
        else:
            if quad != candidate:
                candidate, streak, streak_start = quad, 0, date
            streak += 1
            if streak >= hysteresis:
                current, since = candidate, streak_start
                candidate, streak = None, 0
        regimes.append(current)
        sinces.append(since)

    return pd.DataFrame({"regime": regimes, "regime_since": sinces}, index=valid.index)


def compute() -> dict[str, pd.DataFrame]:
    """Volledige berekening: indicatorpercentielen -> pijlers -> assen -> regime."""
    pcts = indicator_percentiles()
    if pcts.empty:
        raise RuntimeError("Geen enkele indicator heeft bruikbare historie; draai eerst de bootstrap.")
    pillars = pillar_scores(pcts)
    axes = axis_scores(pillars)
    regime = regime_series(axes)
    return {"indicators": pcts, "pillars": pillars, "axes": axes, "regime": regime}


def forward_max_drawdown(px: pd.Series, anchor: pd.Timestamp, months: int = 12) -> float | None:
    """Diepste terugval in de `months` maanden ná `anchor`, t.o.v. de lopende top erbinnen."""
    window = px[(px.index > anchor) & (px.index <= anchor + pd.DateOffset(months=months))]
    if len(window) < 20:
        return None
    return float((window / window.cummax() - 1.0).min())


def analog_periods(axes: pd.DataFrame) -> list[dict]:
    """De meest nabije historische maanden in (fragiliteit, stress)-ruimte, met per analoog
    de forward 12-maands max-drawdown van de S&P 500. De recentste maanden doen niet mee."""
    acfg = load_config()["analogs"]
    px = store.read("px_index")
    valid = axes.dropna(subset=["fragility", "stress"])
    if valid.empty or px.empty:
        return []

    px_s = px.set_index("date")["value"]
    monthly = valid[["fragility", "stress"]].resample("ME").last().dropna()
    cutoff = valid.index[-1] - pd.DateOffset(months=int(acfg["exclude_recent_months"]))
    history = monthly[monthly.index <= cutoff]
    if history.empty:
        return []

    current = valid.iloc[-1]
    distance = np.sqrt(
        (history["fragility"] - current["fragility"]) ** 2
        + (history["stress"] - current["stress"]) ** 2
    )

    out = []
    for month in sorted(distance.nsmallest(int(acfg["count"])).index):
        dd = forward_max_drawdown(px_s, month)
        out.append(
            {
                "period": month.strftime("%Y-%m"),
                "fwd_12m_max_dd": None if dd is None else round(dd, 3),
            }
        )
    return out
