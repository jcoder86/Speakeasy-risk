"""Orkestratie van de ophaalstap.

Twee modi:
  python -m src.main --bootstrap   volledige beschikbare historie ophalen
  python -m src.main               incrementeel bijwerken

Incrementeel betekent hier: opnieuw ophalen vanaf een marge vóór de laatst bekende datum. Elke
fetcher levert een aaneengesloten reeks, dus een gemiste of mislukte run wordt vanzelf ingehaald
zodra de volgende run slaagt — er ontstaan nooit gaten in de historie.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import derive, store
from .config import FETCH_STATUS_PATH, STATE_DIR, load_config
from .fetch import raw_fetchers
from .fetch.base import safe_fetch

log = logging.getLogger("risk.fetch")

# Hoe ver we bij een incrementele run terugkijken. Ruim genoeg om revisies en een reeks
# mislukte runs op te vangen, klein genoeg om de calls licht te houden.
LOOKBACK_DAYS = 30

BOOTSTRAP_START = {"price": "1980-01-01", "default": "1900-01-01"}

# Frequentie per scoring-indicator, bepaalt wanneer een reeks "stale" heet.
FREQUENCY = {
    "cape": "monthly",
    "excess_cape_yield": "monthly",
    "margin_debt_yoy": "monthly",
    "yield_curve": "daily",
    "nfci": "weekly",
    "top10_concentration": "daily",
    "vix_ratio": "daily",
    "trend_stress": "daily",
    "sectors_above_200dma": "daily",
    "rsp_spy_6m": "daily",
    "hy_oas": "daily",
    "hy_oas_63d": "daily",
}


def fetch_all(bootstrap: bool = False, only: list[str] | None = None) -> dict[str, dict]:
    """Haal alle ruwe reeksen op. Geeft per reeks een statusdict terug."""
    registry = raw_fetchers()
    if only:
        registry = {k: v for k, v in registry.items() if k in only}
        if not registry:
            raise SystemExit(f"Geen enkele bekende reeks in --only; keuze uit: {sorted(raw_fetchers())}")

    results: dict[str, dict] = {}
    for name, fetcher in registry.items():
        start = _start_for(name, bootstrap)
        kwargs = {} if name == "top10_concentration" else {"start": start}

        result = safe_fetch(name, fetcher, **kwargs)
        added = store.append(name, result.df) if result.ok else 0
        last = store.last_date(name)

        results[name] = {
            "ok": result.ok,
            "error": result.error,
            "rows_added": added,
            "rows_total": len(store.read(name)),
            "last_date": None if last is None else last.date().isoformat(),
        }
        log.info(
            "%-22s %s  +%-5d totaal=%-6d t/m %s",
            name,
            "ok " if result.ok else "FAIL",
            added,
            results[name]["rows_total"],
            results[name]["last_date"],
        )

    return results


def _start_for(name: str, bootstrap: bool) -> str:
    if bootstrap:
        return BOOTSTRAP_START["price"] if name.startswith("px_") else BOOTSTRAP_START["default"]

    last = store.last_date(name)
    if last is None:  # nog geen historie: behandel als bootstrap voor deze ene reeks
        return BOOTSTRAP_START["price"] if name.startswith("px_") else BOOTSTRAP_START["default"]
    return (last - pd.Timedelta(days=LOOKBACK_DAYS)).date().isoformat()


def indicator_status(today: pd.Timestamp | None = None) -> dict[str, dict]:
    """Per scoring-indicator: laatste datum, stale-vlag en of hij meetelt in de scoring."""
    cfg = load_config()
    today = pd.Timestamp(today or pd.Timestamp.today()).normalize()
    thresholds = cfg["robustness"]["stale_after_days"]
    min_years = cfg["history"]["min_years"]

    status: dict[str, dict] = {}
    for name, freq in FREQUENCY.items():
        df = store.read(name)
        if df.empty:
            status[name] = {
                "as_of": None, "stale": True, "counts_for_scoring": False,
                "frequency": freq, "years_of_history": 0.0,
            }
            continue

        last = df["date"].iloc[-1]
        age = _business_days(last, today) if freq in ("daily", "weekly") else (today - last).days
        years = (last - df["date"].iloc[0]).days / 365.25

        status[name] = {
            "as_of": last.date().isoformat(),
            "stale": bool(age > thresholds[freq]),
            "counts_for_scoring": bool(years >= min_years),
            "frequency": freq,
            "years_of_history": round(years, 1),
        }
    return status


def _business_days(start: pd.Timestamp, end: pd.Timestamp) -> int:
    if end <= start:
        return 0
    return int(np.busday_count(start.date(), end.date()))


def check_staleness(status: dict[str, dict]) -> tuple[bool, str]:
    """De run faalt pas als meer dan de toegestane fractie van de meetellende indicatoren stale is."""
    max_fraction = load_config()["robustness"]["max_stale_fraction"]
    counting = {k: v for k, v in status.items() if v["counts_for_scoring"]}
    if not counting:
        return False, "geen enkele indicator heeft genoeg historie om mee te tellen"

    stale = [k for k, v in counting.items() if v["stale"]]
    fraction = len(stale) / len(counting)
    message = f"{len(stale)}/{len(counting)} meetellende indicatoren stale ({fraction:.0%}): {', '.join(stale) or '-'}"
    return fraction <= max_fraction, message


def write_status(fetch_results: dict, status: dict, ok: bool, message: str) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ok": ok,
        "message": message,
        "sources": fetch_results,
        "indicators": status,
    }
    FETCH_STATUS_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Haal marktdata op en werk de historie bij.")
    parser.add_argument("--bootstrap", action="store_true", help="volledige historie ophalen")
    parser.add_argument("--only", nargs="+", help="beperk tot deze ruwe reeksen (debuggen)")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    log.info("Ophalen gestart (%s).", "bootstrap" if args.bootstrap else "incrementeel")
    fetch_results = fetch_all(bootstrap=args.bootstrap, only=args.only)

    written = derive.run()
    log.info("Afgeleide reeksen bijgewerkt: %s", ", ".join(f"{k}(+{v})" for k, v in written.items()) or "geen")

    status = indicator_status()
    ok, message = check_staleness(status)
    write_status(fetch_results, status, ok, message)

    not_counting = [k for k, v in status.items() if not v["counts_for_scoring"]]
    if not_counting:
        log.info("Nog geen 10 jaar historie, telt niet mee in de scoring: %s", ", ".join(not_counting))

    if not ok:
        log.error("Run afgekeurd: %s", message)
        return 1

    log.info("Klaar. %s", message)
    return 0


if __name__ == "__main__":
    sys.exit(main())
