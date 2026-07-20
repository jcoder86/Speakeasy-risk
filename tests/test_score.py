"""Tests voor de scoring-engine: percentielen zonder lookahead, hysterese, gewichten."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src import score
from src.config import load_config


def _series(values, start="2000-01-03"):
    return pd.Series(values, index=pd.bdate_range(start, periods=len(values)), dtype="float64")


# --- Percentielen ---------------------------------------------------------------


def test_percentiel_gebruikt_alleen_het_verleden():
    """Het percentiel op dag i moet exact de rang binnen dag 0..i zijn — een latere extreme
    waarde mag eerdere percentielen niet veranderen."""
    rng = np.random.default_rng(42)
    values = rng.normal(size=300)
    pct = score.risk_percentile(_series(values), "high", min_years=0)

    for i in (50, 150, 299):
        window = values[: i + 1]
        # Gemiddelde rang bij ties: count_less + (count_equal + 1) / 2, gedeeld door n.
        expected = (np.sum(window < window[i]) + (np.sum(window == window[i]) + 1) / 2) / len(window) * 100
        assert pct.iloc[i] == pytest.approx(expected)

    met_extreme = np.append(values, 1e9)
    pct2 = score.risk_percentile(_series(met_extreme), "high", min_years=0)
    assert pct2.iloc[150] == pytest.approx(pct.iloc[150])


def test_richting_laag_keert_het_percentiel_om():
    values = np.arange(100, dtype=float)
    hoog = score.risk_percentile(_series(values), "high", min_years=0)
    laag = score.risk_percentile(_series(values), "low", min_years=0)

    assert np.allclose(hoog.values + laag.values, 100.0)


def test_minimale_historie_wordt_afgedwongen():
    s = pd.Series(1.0, index=pd.bdate_range("2000-01-03", periods=15 * 252))
    pct = score.risk_percentile(s, "high", min_years=10)

    assert pct.index[0] >= s.index[0] + pd.DateOffset(years=10)


# --- Gewichten -------------------------------------------------------------------


def test_asgewichten_sommeren_tot_1():
    cfg = load_config()
    for axis, weights in cfg["axes"].items():
        assert sum(weights.values()) == pytest.approx(1.0), f"as {axis}"


def test_pijlergewichten_sommeren_tot_1():
    cfg = load_config()
    for pillar, pcfg in cfg["pillars"].items():
        total = sum(i["weight"] for i in pcfg["indicators"].values())
        assert total == pytest.approx(1.0), f"pijler {pillar}"


def test_hernormalisatie_bij_ontbrekende_indicator():
    """Valt één indicator uit, dan draagt de ander de hele pijler."""
    idx = pd.bdate_range("2020-01-01", periods=3)
    values = pd.DataFrame({"a": [80.0, 80.0, 80.0], "b": [np.nan, 20.0, np.nan]}, index=idx)

    result = score._weighted_mean(values, {"a": 0.5, "b": 0.5})

    assert result.iloc[0] == pytest.approx(80.0)
    assert result.iloc[1] == pytest.approx(50.0)
    assert result.iloc[2] == pytest.approx(80.0)


def test_volledig_ontbrekende_pijler_geeft_nan():
    idx = pd.bdate_range("2020-01-01", periods=2)
    values = pd.DataFrame({"a": [np.nan, np.nan]}, index=idx)

    result = score._weighted_mean(values, {"a": 1.0})

    assert result.isna().all()


# --- Hysterese -------------------------------------------------------------------


def _axes(stress_values, fragility=50.0):
    idx = pd.bdate_range("2020-01-01", periods=len(stress_values))
    return pd.DataFrame(
        {"fragility": [fragility] * len(stress_values), "stress": stress_values}, index=idx
    )


def test_korte_uitschieter_wisselt_het_regime_niet():
    """3 dagen boven de drempel is minder dan de vereiste 5 — geen wissel."""
    axes = _axes([50.0] * 10 + [70.0] * 3 + [50.0] * 10)
    regime = score.regime_series(axes)

    assert (regime["regime"] == "calm").all()


def test_vijf_dagen_over_de_drempel_wisselt_wel():
    axes = _axes([50.0] * 10 + [70.0] * 8)
    regime = score.regime_series(axes)

    assert regime["regime"].iloc[-1] == "shock"
    # De wissel wordt op dag 5 van de reeks erkend; dag 1-4 gelden nog als het oude regime.
    assert regime["regime"].iloc[10 + 3] == "calm"
    assert regime["regime"].iloc[10 + 4] == "shock"
    # regime_since wijst terug naar de eerste dag van de reeks die tot de wissel leidde.
    assert regime["regime_since"].iloc[-1] == axes.index[10]


def test_beide_assen_hoog_is_storm():
    axes = _axes([70.0] * 10, fragility=70.0)
    assert score.regime_series(axes)["regime"].iloc[-1] == "storm"
