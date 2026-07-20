"""AI-laag: genereert ai_summary_nl in risk.json — alléén wanneer er iets verandert.

    python -m src.summarize

Triggers (design doc §10): een regimewissel, een pijler die >15 percentielpunten in een
maand beweegt, of een indicator die een historisch extreem bereikt (>=95e of <=5e
risicopercentiel). Triggers worden geëvalueerd over alle dagen sinds de vorige succesvolle
run — een gemiste run laat dus nooit een trigger door de mazen glippen. Zonder trigger:
op maandag een synthese van drie zinnen, andere dagen blijft ai_summary_nl null.

Dagelijkse AI-boilerplate traint de gebruiker om de module te negeren; dat is de reden
voor de alleen-bij-verandering-regel, niet de (verwaarloosbare) API-kosten. Elke fout in
deze module is niet-fataal: de pipeline publiceert dan gewoon zonder samenvatting.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone

import pandas as pd

from . import score
from .config import ANTHROPIC_API_KEY, RISK_JSON_PATH, SONNET_MODEL, STATE_DIR

log = logging.getLogger("risk.summarize")

SUMMARIZE_STATE_PATH = STATE_DIR / "summarize_state.json"

PILLAR_JUMP = 15.0  # percentielpunten per maand
EXTREME_HIGH = 95.0
EXTREME_LOW = 5.0
TRADING_DAYS_1M = score.TRADING_DAYS_1M

PILLAR_LABELS = {
    "valuation": "waardering",
    "credit_slow": "kredietcondities",
    "positioning": "positionering",
    "volatility": "volatiliteit",
    "breadth": "marktbreedte",
    "credit_fast": "kredietstress",
}

INDICATOR_LABELS = {
    "cape": "Shiller-CAPE",
    "excess_cape_yield": "Excess CAPE Yield",
    "yield_curve_18m_min": "rentecurve (18m-minimum)",
    "nfci": "NFCI",
    "margin_debt_yoy": "margin debt (YoY)",
    "top10_concentration": "top-10-concentratie",
    "vix_ratio": "VIX-termijnstructuur",
    "trend_stress": "trendstatus S&P 500",
    "sectors_above_200dma": "sectorbreedte",
    "rsp_spy_6m": "equal-weight vs cap-weight",
    "baa_spread": "Baa-kredietspread",
    "baa_spread_63d": "Baa-spread (63d-verandering)",
}

SYSTEM_PROMPT = (
    "Je bent de tekstlaag van een marktrisico-dashboard. Je legt data uit, je voorspelt "
    "nooit. Geen koersdoelen, geen advies, geen hype, geen 'kan duiden op'. Schrijf in het "
    "Nederlands, warm-zakelijk, als één alinea van 3 tot 5 zinnen: wat veranderde, welke "
    "onderliggende indicator dat dreef, en welke historische parallel uit de meegegeven "
    "analogen relevant is — inclusief wat daar destijds op volgde, ook als dat 'weinig' was. "
    "Percentielen zijn risicopercentielen binnen de eigen historie van een indicator. "
    "Gebruik geen opsommingstekens en herhaal geen kale cijferreeksen die het dashboard al toont."
)


# --- Triggerdetectie --------------------------------------------------------------


def detect_triggers(frames: dict[str, pd.DataFrame], since: pd.Timestamp) -> list[str]:
    """Alle triggers op dagen ná `since`, als NL-omschrijvingen. Leeg = geen trigger."""
    triggers: list[str] = []

    regime = frames["regime"]
    changed = regime["regime"] != regime["regime"].shift(1)
    for date in regime.index[changed & (regime.index > since)]:
        label = score.REGIME_LABELS_NL[regime.loc[date, "regime"]]
        triggers.append(f"regimewissel naar {label} op {date.date()}")

    pillars = frames["pillars"]
    delta = (pillars - pillars.shift(TRADING_DAYS_1M)).abs()
    crossed = (delta > PILLAR_JUMP) & (delta.shift(1) <= PILLAR_JUMP)
    for pillar in pillars.columns:
        hits = pillars.index[crossed[pillar].fillna(False) & (pillars.index > since)]
        if len(hits) > 0:
            d = pillars[pillar].diff(TRADING_DAYS_1M).loc[hits[-1]]
            triggers.append(
                f"pijler {PILLAR_LABELS[pillar]} bewoog {d:+.0f} percentielpunten in een maand"
            )

    pcts = frames["indicators"]
    hit_high = (pcts >= EXTREME_HIGH) & (pcts.shift(1) < EXTREME_HIGH)
    hit_low = (pcts <= EXTREME_LOW) & (pcts.shift(1) > EXTREME_LOW)
    for name in pcts.columns:
        label = INDICATOR_LABELS.get(name, name)
        if hit_high[name].fillna(False)[pcts.index > since].any():
            triggers.append(f"indicator {label} bereikte het extreme deel van zijn historie (>=95e risicopercentiel)")
        if hit_low[name].fillna(False)[pcts.index > since].any():
            triggers.append(f"indicator {label} zakte naar een historisch uitzonderlijk rustige stand (<=5e risicopercentiel)")

    return triggers


# --- Staat en samenvatting --------------------------------------------------------


def _load_state() -> dict:
    if not SUMMARIZE_STATE_PATH.exists():
        return {}
    try:
        return json.loads(SUMMARIZE_STATE_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning("Samenvattingsstaat onleesbaar (%s), begin opnieuw.", e)
        return {}


def _save_state(last_evaluated: pd.Timestamp) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARIZE_STATE_PATH.write_text(
        json.dumps(
            {
                "last_evaluated": last_evaluated.date().isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _since_date(frames: dict) -> pd.Timestamp:
    """Vanaf wanneer triggers evalueren: de vorige geëvalueerde dag, anders gisteren."""
    state = _load_state()
    last_index = frames["regime"].index[-1]
    if state.get("last_evaluated"):
        return min(pd.Timestamp(state["last_evaluated"]), last_index)
    return last_index - pd.Timedelta(days=1)


def _context(frames: dict, payload: dict, triggers: list[str]) -> str:
    axes = frames["axes"].dropna()
    month_ago = axes.iloc[-1 - TRADING_DAYS_1M] if len(axes) > TRADING_DAYS_1M else axes.iloc[0]
    context = {
        "vandaag": axes.index[-1].date().isoformat(),
        "triggers": triggers,
        "regime": payload["regime_label_nl"],
        "regime_sinds": payload["regime_since"],
        "fragiliteit": payload["fragility"],
        "stress": payload["stress"],
        "fragiliteit_1m_geleden": round(float(month_ago["fragility"])),
        "stress_1m_geleden": round(float(month_ago["stress"])),
        "drivers": payload["drivers"],
        "analogen": payload["analogs"],
    }
    return json.dumps(context, ensure_ascii=False, indent=1)


def generate_summary(frames: dict, payload: dict, triggers: list[str], weekly: bool) -> str | None:
    """Roept Claude aan. Geeft None terug bij elke fout — de pipeline mag hier nooit op breken."""
    if not ANTHROPIC_API_KEY:
        log.warning("ANTHROPIC_API_KEY ontbreekt; samenvatting overgeslagen.")
        return None

    if triggers:
        instruction = (
            "Er is vandaag een trigger. Schrijf de duiding (3-5 zinnen) op basis van deze data:\n"
        )
    else:
        instruction = (
            "Geen trigger; het is maandag. Schrijf een rustige weeksynthese van precies 3 zinnen "
            "op basis van deze data:\n"
        )

    try:
        from anthropic import Anthropic

        client = Anthropic()
        message = client.messages.create(
            model=SONNET_MODEL,
            max_tokens=500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": instruction + _context(frames, payload, triggers)}],
        )
        text = "".join(block.text for block in message.content if block.type == "text").strip()
        return text or None
    except Exception as e:
        log.warning("Claude-call mislukt (%s: %s); samenvatting blijft leeg.", type(e).__name__, e)
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Vul ai_summary_nl in risk.json (alleen bij triggers of op maandag).")
    parser.add_argument("--force", action="store_true", help="genereer ook zonder trigger (test)")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    if not RISK_JSON_PATH.exists():
        log.error("risk.json ontbreekt; draai eerst python -m src.publish.")
        return 1
    payload = json.loads(RISK_JSON_PATH.read_text(encoding="utf-8"))

    frames = score.compute()
    since = _since_date(frames)
    triggers = detect_triggers(frames, since)
    weekly = datetime.now(timezone.utc).weekday() == 0

    log.info("Triggers sinds %s: %s", since.date(), "; ".join(triggers) or "geen")

    if triggers or weekly or args.force:
        summary = generate_summary(frames, payload, triggers, weekly=weekly and not triggers)
        if summary:
            payload["ai_summary_nl"] = summary
            payload["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            RISK_JSON_PATH.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            log.info("Samenvatting geschreven (%d tekens).", len(summary))
    else:
        log.info("Geen trigger en geen maandag; ai_summary_nl blijft null.")

    _save_state(frames["regime"].index[-1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
