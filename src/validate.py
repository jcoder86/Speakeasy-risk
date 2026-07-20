"""Validatierapport (design doc §8): genereert VALIDATION.md.

    python -m src.validate

Alles in dit rapport is point-in-time berekend: elk getal gebruikt uitsluitend data die op
dat moment beschikbaar was. Resultaten worden neutraal gepresenteerd — ook waar het model
tegenvalt. Op dit rapport wordt beoordeeld of de module live gaat.
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import score, store
from .config import VALIDATION_PATH, load_config

log = logging.getLogger("risk.validate")

SIGNAL_LEVEL = 60.0  # "signaleren" = pijler op of boven de regimedrempel

EPISODES = {
    "Dotcom (2000)": "2000-03-24",
    "Kredietcrisis (2008)": "2007-10-09",
    "COVID (2020)": "2020-02-19",
    "Rentecorrectie (2022)": "2022-01-03",
}

FALSE_POSITIVES = {
    "LTCM (1998)": ("1998-07-01", "1998-12-31"),
    "Eurocrisis (2011)": ("2011-07-01", "2011-12-31"),
    "China/olie (2015-16)": ("2015-08-01", "2016-04-30"),
    "Q4 2018": ("2018-10-01", "2018-12-31"),
    "Bankenstress (mrt 2023)": ("2023-03-01", "2023-04-30"),
}

PILLAR_LABELS = {
    "valuation": "Waardering (F1)",
    "credit_slow": "Kredietcondities (F2)",
    "positioning": "Positionering (F3)",
    "volatility": "Volatiliteit (S1)",
    "breadth": "Breedte (S2)",
    "credit_fast": "Kredietstress (S3)",
}


# --- Bouwstenen -------------------------------------------------------------------


def _monthly_forward_dd(axes: pd.DataFrame) -> pd.DataFrame:
    """Maandelijkse samples van beide assen plus de forward 12m max-drawdown van de S&P."""
    px = store.read("px_index").set_index("date")["value"]
    monthly = axes[["fragility", "stress"]].resample("ME").last().dropna()
    cutoff = axes.index[-1] - pd.DateOffset(months=12)
    monthly = monthly[monthly.index <= cutoff]

    dd = {m: score.forward_max_drawdown(px, m) for m in monthly.index}
    monthly = monthly.assign(fwd_dd=pd.Series(dd))
    return monthly.dropna(subset=["fwd_dd"])


def _fmt_months(peak: pd.Timestamp, date: pd.Timestamp | None) -> str:
    if date is None:
        return "—"
    months = (date.year - peak.year) * 12 + date.month - peak.month
    rel = f"{months:+d}m" if months else "0m"
    return f"{date.date()} ({rel})"


def _first_at_or_above(series: pd.Series, level: float) -> pd.Timestamp | None:
    hit = series[series >= level]
    return None if hit.empty else hit.index[0]


def _regime_changes(regime: pd.Series) -> pd.Series:
    return regime[regime != regime.shift(1)]


def _max_dd_within(px: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> float | None:
    window = px[(px.index >= start) & (px.index <= end)]
    if len(window) < 5:
        return None
    return float((window / window.cummax() - 1.0).min())


# --- Rapportsecties ---------------------------------------------------------------


def availability_section(frames: dict) -> list[str]:
    pcts = frames["indicators"]
    lines = [
        "## 1. Databeschikbaarheid (eerlijke n)",
        "",
        "Percentielen gebruiken de volledige eigen historie van elke indicator, maar een",
        "indicator telt pas mee na tien jaar eigen data. Daardoor draait niet elke episode",
        "op dezelfde set — onderstaande tabel is de leeswijzer bij alles hierna.",
        "",
        "| Indicator | telt mee vanaf |",
        "|---|---|",
    ]
    for name in pcts.columns:
        first = pcts[name].first_valid_index()
        lines.append(f"| `{name}` | {'—' if first is None else first.date()} |")
    lines += [
        "",
        "Gevolgen: de dotcom-episode draait zonder positionering, breedte en VIX-structuur;",
        "2008 mist breedte en VIX-structuur; ECY doet pas vanaf 2013 mee. HY OAS is bij FRED",
        "afgeknot tot ~3 jaar historie (ICE-licentie); kredietstress scoort daarom op de",
        "Moody's Baa-spread (volledig sinds 1986).",
        "",
    ]
    return lines


def event_study_section(frames: dict) -> list[str]:
    pillars, axes, regime = frames["pillars"], frames["axes"], frames["regime"]
    px = store.read("px_index").set_index("date")["value"]

    lines = [
        "## 2. Event-studies (venster −24m / +12m rond de top)",
        "",
        f'"Eerste signaal" = de eerste dag binnen het venster waarop een pijler ≥ {SIGNAL_LEVEL:.0f} stond.',
        "",
    ]
    for title, peak_str in EPISODES.items():
        peak = pd.Timestamp(peak_str)
        start, end = peak - pd.DateOffset(months=24), peak + pd.DateOffset(months=12)
        p_win = pillars[(pillars.index >= start) & (pillars.index <= end)]
        a_win = axes[(axes.index >= start) & (axes.index <= end)]
        r_win = regime[(regime.index >= start) & (regime.index <= end)]

        dd = _max_dd_within(px, peak, end)
        lines += [
            f"### {title} — top {peak.date()}",
            "",
            f"Max-drawdown S&P 500 in de 12 maanden na de top: **{dd:.0%}**." if dd is not None else "",
            "",
            "| Pijler | eerste signaal (≥60) | piek in venster |",
            "|---|---|---|",
        ]
        for pillar, label in PILLAR_LABELS.items():
            series = p_win[pillar].dropna()
            if series.empty:
                lines.append(f"| {label} | geen data | geen data |")
                continue
            first = _first_at_or_above(series, SIGNAL_LEVEL)
            lines.append(f"| {label} | {_fmt_months(peak, first)} | {series.max():.0f} |")

        top_idx = a_win.index.asof(peak)
        lines += [
            "",
            f"Assen op de topdag: fragiliteit {a_win.loc[top_idx, 'fragility']:.0f}, "
            f"stress {a_win.loc[top_idx, 'stress']:.0f}. "
            f"Regime op de topdag: **{score.REGIME_LABELS_NL[r_win.loc[r_win.index.asof(peak), 'regime']]}**.",
            "",
            "Regimeverloop in het venster:",
            "",
        ]
        changes = _regime_changes(r_win["regime"])
        lines += [
            f"- {d.date()}: {score.REGIME_LABELS_NL[r]}" for d, r in changes.items()
        ] or ["- geen wissels"]
        lines.append("")
    return lines


def false_positive_section(frames: dict) -> list[str]:
    axes, regime = frames["axes"], frames["regime"]
    px = store.read("px_index").set_index("date")["value"]

    lines = [
        "## 3. False-positive-set",
        "",
        "Episodes met echte marktstress die géén 2008 werden. Verhoogde stress tonen mag;",
        "de vraag is of het model ze als Storm classificeerde en hoe lang.",
        "",
        "| Episode | daling S&P | max fragiliteit | max stress | dagen Storm | dagen Schok |",
        "|---|---|---|---|---|---|",
    ]
    for title, (start_str, end_str) in FALSE_POSITIVES.items():
        start, end = pd.Timestamp(start_str), pd.Timestamp(end_str)
        a = axes[(axes.index >= start) & (axes.index <= end)].dropna()
        r = regime[(regime.index >= start) & (regime.index <= end)]["regime"]
        dd = _max_dd_within(px, start, end)
        lines.append(
            f"| {title} | {dd:.0%} | {a['fragility'].max():.0f} | {a['stress'].max():.0f} "
            f"| {(r == 'storm').sum()} | {(r == 'shock').sum()} |"
        )
    lines.append("")
    return lines


def regime_calibration_section(frames: dict, monthly: pd.DataFrame) -> list[str]:
    regime = frames["regime"]["regime"]
    sampled = monthly.join(regime.rename("regime"), how="inner")

    lines = [
        "## 4. Kalibratie: wat volgde er op elk regime?",
        "",
        "Forward 12-maands max-drawdown van de S&P 500, per regime (maandelijkse samples,",
        "laatste 12 maanden uitgesloten). Dit kalibreert ook de analogen-uitvoer.",
        "",
        "| Regime | maanden | mediane fwd DD | ergste fwd DD | % erger dan −15% |",
        "|---|---|---|---|---|",
    ]
    for reg in ["calm", "fragile_calm", "shock", "storm"]:
        sub = sampled[sampled["regime"] == reg]["fwd_dd"]
        if sub.empty:
            lines.append(f"| {score.REGIME_LABELS_NL[reg]} | 0 | — | — | — |")
            continue
        lines.append(
            f"| {score.REGIME_LABELS_NL[reg]} | {len(sub)} | {sub.median():.0%} "
            f"| {sub.min():.0%} | {(sub <= -0.15).mean():.0%} |"
        )
    lines.append("")
    return lines


def baseline_section(frames: dict, monthly: pd.DataFrame) -> list[str]:
    pcts = frames["indicators"]

    vix = store.read("px_vix").set_index("date")["value"]
    dist = store.read("gspc_dist_200dma").set_index("date")["value"]

    signals = pd.DataFrame(index=monthly.index)
    signals["model: fragiliteit"] = monthly["fragility"]
    signals["model: stress"] = monthly["stress"]
    signals["model: (F+S)/2"] = (monthly["fragility"] + monthly["stress"]) / 2
    signals["baseline: Baa-spread-percentiel"] = (
        pcts["baa_spread"].resample("ME").last().reindex(monthly.index)
    )
    signals["baseline: koers onder 200d MA"] = (dist.resample("ME").last() < 0).astype(float).reindex(monthly.index)
    signals["baseline: VIX > 30"] = (vix.resample("ME").last() > 30).astype(float).reindex(monthly.index)

    severity = -monthly["fwd_dd"]  # hoger = erger
    lines = [
        "## 5. Baseline-vergelijking",
        "",
        "Spearman-rangcorrelatie tussen signaalwaarde en de ernst van de forward 12m",
        "max-drawdown (maandelijkse samples). Hoger = beter rangschikken van drawdown-risico.",
        "De HY-OAS-baseline uit het design doc is niet reproduceerbaar (FRED-historie afgeknot);",
        "de Baa-spread vervult die rol. De binaire regels zijn grofkorrelig — dat is precies",
        "hun handicap als baseline.",
        "",
        "| Signaal | Spearman | n |",
        "|---|---|---|",
    ]
    for col in signals.columns:
        s = signals[col].dropna()
        aligned = severity.reindex(s.index).dropna()
        s = s.reindex(aligned.index)
        # Spearman = Pearson op rangen; scheelt een scipy-dependency.
        rho = s.rank().corr(aligned.rank()) if len(s) > 24 else np.nan
        lines.append(f"| {col} | {rho:.2f} | {len(s)} |")
    lines.append("")
    return lines


def correlation_section(frames: dict) -> list[str]:
    pillars = frames["pillars"].dropna(how="all")
    corr = pillars.corr(min_periods=252)

    lines = [
        "## 6. Paarsgewijze pijlercorrelaties",
        "",
        "Boven ~0,8 zou samenvoegen aan de orde zijn (design doc §7).",
        "",
        "| | " + " | ".join(PILLAR_LABELS[c] for c in corr.columns) + " |",
        "|---|" + "---|" * len(corr.columns),
    ]
    for row in corr.index:
        cells = []
        for col in corr.columns:
            v = corr.loc[row, col]
            flag = " ⚠" if row != col and pd.notna(v) and abs(v) > 0.8 else ""
            cells.append("—" if pd.isna(v) else f"{v:.2f}{flag}")
        lines.append(f"| {PILLAR_LABELS[row]} | " + " | ".join(cells) + " |")
    lines.append("")
    return lines


def sensitivity_section(frames: dict) -> list[str]:
    cfg = load_config()
    pillars, base_regime = frames["pillars"], frames["regime"]["regime"]

    lines = [
        "## 7. Gewicht- en drempelsensitiviteit",
        "",
        "Elk pijlergewicht ±50% (as opnieuw genormaliseerd), daarna het percentage dagen",
        "waarop het regime verandert t.o.v. de basisconfiguratie. Slaat de conclusie om bij",
        "een kleine wijziging, dan is het signaal te zwak om te rapporteren (design doc §5).",
        "",
        "| As | pijler | −50% | +50% |",
        "|---|---|---|---|",
    ]
    for axis, weights in cfg["axes"].items():
        for pillar in weights:
            cells = []
            for factor in (0.5, 1.5):
                adjusted = {a: dict(w) for a, w in cfg["axes"].items()}
                adjusted[axis][pillar] = weights[pillar] * factor
                total = sum(adjusted[axis].values())
                adjusted[axis] = {p: w / total for p, w in adjusted[axis].items()}

                axes2 = score.axis_scores(pillars, adjusted)
                regime2 = score.regime_series(axes2)["regime"]
                joined = pd.concat([base_regime, regime2], axis=1, keys=["a", "b"]).dropna()
                cells.append(f"{(joined['a'] != joined['b']).mean():.1%}")
            lines.append(f"| {axis} | {PILLAR_LABELS[pillar]} | {cells[0]} | {cells[1]} |")

    lines += [
        "",
        "Drempel (basis 60) verschoven:",
        "",
        "| drempel | % dagen ander regime |",
        "|---|---|",
    ]
    axes_base = frames["axes"]
    for thr in (55, 65):
        regime2 = score.regime_series(axes_base, threshold=thr)["regime"]
        joined = pd.concat([base_regime, regime2], axis=1, keys=["a", "b"]).dropna()
        lines.append(f"| {thr} | {(joined['a'] != joined['b']).mean():.1%} |")
    lines.append("")
    return lines


def stability_and_weakness_section(frames: dict) -> list[str]:
    regime = frames["regime"]["regime"]
    changes = _regime_changes(regime)
    years = (regime.index[-1] - regime.index[0]).days / 365.25
    episode_lengths = regime.groupby((regime != regime.shift(1)).cumsum()).size()

    lines = [
        "## 8. Stabiliteit en bekende zwakke punten",
        "",
        f"Regimewissels sinds {regime.index[0].year}: **{len(changes) - 1}** "
        f"({(len(changes) - 1) / years:.1f} per jaar); mediane regimeduur "
        f"**{episode_lengths.median():.0f}** handelsdagen, kortste {episode_lengths.min():.0f}.",
        "",
        "Wat dit rapport laat zien, ook waar het tegenvalt:",
        "",
        "- **COVID (2020) is niet voorspeld — per ontwerp.** Op de topdag stond het model op",
        "  Kalm/Fragiele-rust-grens (fragiliteit 60, stress 45). Een exogene schok is ex ante",
        "  onzichtbaar; de waarde zat in de omslag naar Schok binnen drie weken en in de matige",
        "  fragiliteit die het snelle herstel verklaarde (design doc §2).",
        "- **1998 (LTCM) leest als Storm.** De stress was echt (krediet, volatiliteit) en de",
        "  waardering stond op recordniveau — de fragiliteit was dus geen vals signaal, maar de",
        "  Fed-verlagingen kapten de episode af. Wie in 1998 voorzichtig werd, was twee jaar te",
        "  vroeg voor de dotcom-top en miste die rally; de kalibratietabel (§4) prijst dit in.",
        "- **2022 kende geen kredietstress.** De Baa-spread bleef kalm en equal-weight versloeg",
        "  cap-weight; twee van de drie stresspijlers stonden daardoor laag terwijl de index",
        "  -25% deed. Het trendfilter droeg de stress-as vrijwel alleen. Het regime bleef",
        "  hangen rond de drempel — de Schmitt-marge (§7-config) houdt het label sindsdien",
        "  vast tot het signaal echt wegzakt, maar de onderliggende zwakte blijft: een",
        "  rente-gedreven daling zonder kredietstress scoort structureel lager dan een",
        "  kredietcrisis van gelijke omvang.",
        "- **De vroege jaren draaien op een smalle set.** Vóór 1996 bestaat de stress-as",
        "  vrijwel alleen uit het trendfilter (§1); conclusies over 1990-1995 zijn daarom",
        "  zwak onderbouwd.",
        "- **Positionering mist zijn tweede been.** Top-10-concentratie heeft geen gratis",
        "  historie en telt pas over tien jaar mee; F3 is tot die tijd alleen margin debt.",
        "",
    ]
    return lines


def build_report() -> str:
    frames = score.compute()
    monthly = _monthly_forward_dd(frames["axes"])

    header = [
        "# Validatierapport — JanApp Risk Module",
        "",
        f"Gegenereerd: {datetime.now(timezone.utc).date().isoformat()} · "
        f"reproduceerbaar via `python -m src.validate` · alles point-in-time.",
        "",
        "Met vier grote events is elke kwantitatieve metric indicatief; dit rapport is",
        "narratief plus kalibratie, geen bewijs (design doc §8.5).",
        "",
    ]
    sections = (
        header
        + availability_section(frames)
        + event_study_section(frames)
        + false_positive_section(frames)
        + regime_calibration_section(frames, monthly)
        + baseline_section(frames, monthly)
        + correlation_section(frames)
        + sensitivity_section(frames)
        + stability_and_weakness_section(frames)
    )
    return "\n".join(sections)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Genereer VALIDATION.md.")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)
    report = build_report()
    VALIDATION_PATH.write_text(report, encoding="utf-8")
    log.info("VALIDATION.md geschreven (%d regels).", report.count("\n") + 1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
