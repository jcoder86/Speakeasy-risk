"""Publicatie: risk.json (schema §11 van het design doc) en history.csv (wekelijkse samples
voor de grafiekstrip in JanApp).

    python -m src.publish
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone

import pandas as pd

from . import score
from .config import HISTORY_CSV_PATH, RISK_JSON_PATH, indicator_specs, load_config
from .main import indicator_status

log = logging.getLogger("risk.publish")

HISTORY_URL = "https://raw.githubusercontent.com/jcoder86/Speakeasy-risk/main/history.csv"

FRAGILITY_PILLARS = ["valuation", "credit_slow", "positioning"]
STRESS_PILLARS = ["volatility", "breadth", "credit_fast"]

# Korte NL-notities per indicator: (label, mechanisme). Templates, bewust nog geen LLM.
NOTES = {
    "cape": ("Shiller-CAPE", "hoge waardering vergroot hoe diep een correctie kán gaan"),
    "excess_cape_yield": ("Excess CAPE Yield", "weinig compensatie boven de reële rente maakt de waardering rentegevoelig"),
    "yield_curve_18m_min": ("rentecurve (diepste stand in 18m)", "een recente inversie hoort bij het einde van de cyclus en werkt met 6-18 maanden vertraging door"),
    "nfci": ("financiële condities (NFCI)", "krappere condities knijpen leverage en funding af"),
    "margin_debt_yoy": ("margin debt (YoY)", "hard gegroeide beleningen zijn brandstof voor gedwongen verkoop"),
    "top10_concentration": ("top-10-concentratie", "het indexrisico hangt aan een handvol namen"),
    "vix_ratio": ("VIX-termijnstructuur", "inversie betekent dat de markt nú meer vreest dan straks"),
    "trend_stress": ("trendstatus S&P 500", "een koers onder het 200-daags gemiddelde bevestigt de downtrend"),
    "sectors_above_200dma": ("sectorbreedte", "steeds minder sectoren dragen de trend"),
    "rsp_spy_6m": ("equal-weight vs cap-weight", "de index stijgt harder dan het gemiddelde aandeel: smal leiderschap"),
    "baa_spread": ("Baa-kredietspread", "de kredietmarkt prijst oplopend risico"),
    "baa_spread_63d": ("Baa-spread, 63d-verandering", "verwijdende spreads gaan aandelenstress vaak vooraf"),
}


def drivers(pcts: pd.DataFrame, top_n: int = 3) -> list[dict]:
    """Top-indicatoren op |verandering in 1 maand| x effectief gewicht in de eindscore."""
    cfg = load_config()
    if len(pcts) <= score.TRADING_DAYS_1M:
        return []

    latest = pcts.iloc[-1]
    delta = latest - pcts.iloc[-1 - score.TRADING_DAYS_1M]

    ranking = []
    for name, spec in indicator_specs().items():
        if name not in pcts.columns or pd.isna(latest[name]) or pd.isna(delta[name]):
            continue
        effective_weight = cfg["axes"][spec["axis"]][spec["pillar"]] * spec["weight"]
        ranking.append((abs(delta[name]) * effective_weight, name))

    out = []
    for _, name in sorted(ranking, reverse=True)[:top_n]:
        label, mechanism = NOTES[name]
        pct, d = latest[name], delta[name]
        note = f"{label[0].upper()}{label[1:]} staat op het {pct:.0f}e risicopercentiel ({d:+.0f} punten in een maand) — {mechanism}."
        out.append(
            {
                "indicator": name,
                "percentile": int(round(pct)),
                "delta_1m": int(round(d)),
                "note_nl": note,
            }
        )
    return out


def _axis_block(axes: pd.DataFrame, pillars: pd.DataFrame, axis: str, pillar_names: list[str]) -> dict:
    last_axis = axes[axis].dropna()
    block = {"score": None if last_axis.empty else int(round(last_axis.iloc[-1])), "pillars": {}}
    for pillar in pillar_names:
        series = pillars[pillar].dropna() if pillar in pillars.columns else pd.Series(dtype="float64")
        block["pillars"][pillar] = None if series.empty else int(round(series.iloc[-1]))
    return block


def build_payload(frames: dict[str, pd.DataFrame] | None = None) -> dict:
    frames = frames or score.compute()
    pcts, pillars, axes, regime = (
        frames["indicators"],
        frames["pillars"],
        frames["axes"],
        frames["regime"],
    )
    if regime.empty:
        raise RuntimeError("Geen regime berekend; beide assen missen data.")

    last = regime.iloc[-1]
    status = indicator_status()
    latest_pcts = pcts.iloc[-1]

    indicators = {}
    for name in pcts.columns:
        info = status.get(name, {})
        value = latest_pcts[name]
        indicators[name] = {
            "percentile": None if pd.isna(value) else int(round(value)),
            "stale": info.get("stale", True),
            "as_of": info.get("as_of"),
            "counts_for_scoring": info.get("counts_for_scoring", False),
        }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "regime": last["regime"],
        "regime_label_nl": score.REGIME_LABELS_NL[last["regime"]],
        "regime_since": pd.Timestamp(last["regime_since"]).date().isoformat(),
        "fragility": _axis_block(axes, pillars, "fragility", FRAGILITY_PILLARS),
        "stress": _axis_block(axes, pillars, "stress", STRESS_PILLARS),
        "drivers": drivers(pcts),
        "analogs": score.analog_periods(axes),
        "ai_summary_nl": None,  # fase 4
        "history_url": HISTORY_URL,
        "indicators": indicators,
    }


def write_history_csv(axes: pd.DataFrame) -> int:
    """Wekelijkse fragility/stress-samples voor de grafiekstrip."""
    weekly = axes[["fragility", "stress"]].resample("W-FRI").last().dropna(how="all").round(1)
    weekly.index.name = "date"
    weekly.to_csv(HISTORY_CSV_PATH, date_format="%Y-%m-%d")
    return len(weekly)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bereken scores en schrijf risk.json + history.csv.")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    frames = score.compute()
    payload = build_payload(frames)
    RISK_JSON_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    weeks = write_history_csv(frames["axes"])

    log.info(
        "risk.json geschreven: regime=%s (sinds %s), fragiliteit=%s, stress=%s; history.csv: %d weken.",
        payload["regime"],
        payload["regime_since"],
        payload["fragility"]["score"],
        payload["stress"]["score"],
        weeks,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
