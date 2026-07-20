"""Tests voor de triggerdetectie van de AI-laag (zonder API-calls)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.summarize import detect_triggers


def _frames(days=60, regime="calm", pillar=50.0, indicator=50.0):
    idx = pd.bdate_range("2026-01-01", periods=days)
    return {
        "regime": pd.DataFrame({"regime": [regime] * days, "regime_since": [idx[0]] * days}, index=idx),
        "pillars": pd.DataFrame({"valuation": [pillar] * days}, index=idx),
        "indicators": pd.DataFrame({"cape": [indicator] * days}, index=idx),
    }


def test_geen_triggers_bij_stilte():
    frames = _frames()
    assert detect_triggers(frames, frames["regime"].index[10]) == []


def test_regimewissel_triggert():
    frames = _frames()
    frames["regime"].iloc[-3:, 0] = "storm"

    triggers = detect_triggers(frames, frames["regime"].index[-10])

    assert any("regimewissel naar Storm" in t for t in triggers)


def test_regimewissel_voor_het_venster_triggert_niet():
    """Een wissel die al geëvalueerd is (vóór `since`) mag niet opnieuw vuren."""
    frames = _frames()
    frames["regime"].iloc[10:, 0] = "storm"

    assert detect_triggers(frames, frames["regime"].index[20]) == []


def test_pijlersprong_boven_15_punten_triggert():
    frames = _frames()
    # Sprong van 50 naar 70 op dag 40: delta_1m kruist de 15-puntengrens.
    frames["pillars"].iloc[40:, 0] = 70.0

    triggers = detect_triggers(frames, frames["regime"].index[35])

    assert any("waardering" in t and "+20" in t for t in triggers)


def test_indicator_extreem_triggert_bij_kruising():
    frames = _frames()
    frames["indicators"].iloc[-5:, 0] = 97.0

    triggers = detect_triggers(frames, frames["regime"].index[-10])

    assert any("Shiller-CAPE" in t and "95e" in t for t in triggers)


def test_indicator_die_al_extreem_stond_triggert_niet_opnieuw():
    frames = _frames(indicator=97.0)  # staat de hele periode al boven 95
    assert detect_triggers(frames, frames["regime"].index[10]) == []


def test_inhaal_over_gemiste_dagen_vangt_oude_trigger():
    """Een wissel van vijf dagen geleden telt nog als `since` verder terug ligt."""
    frames = _frames()
    frames["regime"].iloc[-5:, 0] = "shock"

    triggers = detect_triggers(frames, frames["regime"].index[-8])

    assert any("Schok" in t for t in triggers)
