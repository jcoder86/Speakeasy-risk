"""Sanity-tests op bekende datums, tegen de echte (gebootstrapte) historie.

Deze tests draaien alleen als de volledige historie aanwezig is. Falen ze, dan is de opdracht:
eerst begrijpen waarom — niet de drempels bijstellen tot het past.
"""
from __future__ import annotations

import pandas as pd
import pytest

from src import score
from src.config import HISTORY_DIR

pytestmark = pytest.mark.skipif(
    not (HISTORY_DIR / "baa_spread.csv").exists() or not (HISTORY_DIR / "cape.csv").exists(),
    reason="volledige historie vereist — draai eerst python -m src.main --bootstrap",
)


@pytest.fixture(scope="module")
def frames():
    return score.compute()


def _regime_op(frames, datum: str) -> str:
    regime = frames["regime"]
    idx = regime.index.asof(pd.Timestamp(datum))
    return regime.loc[idx, "regime"]


def test_oktober_2008_is_storm(frames):
    assert _regime_op(frames, "2008-10-15") == "storm"


def test_december_2021_is_fragiele_rust(frames):
    assert _regime_op(frames, "2021-12-15") == "fragile_calm"


def test_april_2020_is_schok_of_storm(frames):
    assert _regime_op(frames, "2020-04-15") in ("shock", "storm")
