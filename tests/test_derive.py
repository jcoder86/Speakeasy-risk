"""Tests voor de afgeleide reeksen — vooral: geen lookahead."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src import derive, store


@pytest.fixture(autouse=True)
def tmp_history(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "HISTORY_DIR", tmp_path)
    return tmp_path


def _write(name, dates, values):
    store.write_derived(name, pd.DataFrame({"date": dates, "value": values}))


def _bdays(n, start="2015-01-01"):
    return pd.bdate_range(start, periods=n)


def test_vix_ratio_deelt_alleen_op_gedeelde_datums():
    _write("px_vix", ["2020-01-01", "2020-01-02", "2020-01-03"], [20.0, 30.0, 25.0])
    _write("px_vix3m", ["2020-01-02", "2020-01-03"], [25.0, 25.0])

    ratio = derive._vix_ratio()

    assert list(ratio.index.strftime("%Y-%m-%d")) == ["2020-01-02", "2020-01-03"]
    assert ratio.iloc[0] == pytest.approx(1.2)


def test_curve_18m_min_is_achterwaarts_minimum():
    """Een inversie van een jaar geleden moet vandaag nog in het minimum zitten."""
    dates = _bdays(500)
    values = np.full(500, 2.0)
    values[200:210] = -0.5  # korte inversie, ruim binnen het laatste 378-daags venster
    _write("yield_curve", dates, values)

    minimum = derive._yield_curve_18m_min()

    assert minimum.iloc[-1] == pytest.approx(-0.5)
    assert minimum.index[0] == dates[377]  # pas na een vol venster een waarde


def test_spread_63d_is_verschil_met_63_handelsdagen_terug():
    dates = _bdays(100)
    _write("baa_spread", dates, np.arange(100, dtype=float))

    change = derive._change_63d("baa_spread")

    assert change.iloc[0] == pytest.approx(63.0)
    assert len(change) == 100 - 63


def test_trendstress_is_hoog_in_een_downtrend():
    """Boven het gemiddelde en op een high hoort lage stress te geven, eronder hoge."""
    dates = _bdays(400)
    stijgend = np.linspace(100, 200, 400)
    _write("px_index", dates, stijgend)
    opgaand = derive._trend_stress()

    dalend = np.concatenate([np.linspace(100, 200, 300), np.linspace(200, 120, 100)])
    _write("px_index", dates, dalend)
    neergaand = derive._trend_stress()

    assert opgaand.iloc[-1] < 0  # negatieve stress: koers boven MA én op de high
    assert neergaand.iloc[-1] > 0


def test_200dma_venster_gebruikt_geen_toekomst():
    """De 200d-MA mag pas een waarde geven vanaf de 200e observatie."""
    dates = _bdays(260)
    _write("px_index", dates, np.linspace(100, 150, 260))

    dist, _ = derive._trend_components()

    assert dist.index[0] == dates[199]


def test_sectoren_boven_200dma_rekent_over_beschikbare_sectoren():
    """XLC bestaat pas sinds 2018; het percentage telt alleen sectoren die er al waren."""
    dates = _bdays(300)
    for i, ticker in enumerate(["xlb", "xlc", "xle", "xlf", "xli", "xlk"]):
        trend = np.linspace(100, 200, 300) if i < 4 else np.linspace(200, 100, 300)
        _write(f"px_{ticker}", dates, trend)

    pct = derive._sectors_above_200dma()

    assert pct.iloc[-1] == pytest.approx(4 / 6 * 100)


def test_excess_cape_yield_koppelt_alleen_achterwaarts():
    """De reële rente van ná de CAPE-datum mag niet meetellen."""
    _write("cape", ["2020-02-05", "2020-03-05"], [25.0, 20.0])
    _write("real_10y", ["2020-01-31", "2020-02-28", "2020-12-31"], [0.0, 1.0, 9.0])

    ecy = derive._excess_cape_yield()

    assert ecy.iloc[0] == pytest.approx(100 / 25 - 0.0)  # gebruikt 31-01, niet 28-02
    assert ecy.iloc[1] == pytest.approx(100 / 20 - 1.0)


def test_margin_debt_yoy_vergelijkt_met_twaalf_maanden_terug():
    dates = pd.date_range("2020-01-25", periods=13, freq="ME")
    _write("margin_debt", dates, [100.0] * 12 + [150.0])

    yoy = derive._margin_debt_yoy().dropna()

    assert yoy.iloc[-1] == pytest.approx(50.0)
