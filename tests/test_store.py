"""Tests voor de append-only historie-opslag."""
from __future__ import annotations

import pandas as pd
import pytest

from src import store


@pytest.fixture(autouse=True)
def tmp_history(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "HISTORY_DIR", tmp_path)
    return tmp_path


def _df(pairs):
    return pd.DataFrame({"date": [p[0] for p in pairs], "value": [p[1] for p in pairs]})


def test_append_voegt_alleen_nieuwe_datums_toe():
    store.append("x", _df([("2020-01-01", 1.0), ("2020-01-02", 2.0)]))
    added = store.append("x", _df([("2020-01-02", 2.0), ("2020-01-03", 3.0)]))

    assert added == 1
    assert list(store.read("x")["value"]) == [1.0, 2.0, 3.0]


def test_revisie_wordt_genegeerd_zonder_allow_revision():
    """Historie is heilig: wat we destijds vastlegden blijft staan, ook na een revisie."""
    store.append("x", _df([("2020-01-01", 1.0)]))
    store.append("x", _df([("2020-01-01", 99.0)]))

    assert list(store.read("x")["value"]) == [1.0]


def test_afgeleide_reeks_mag_wel_herberekend_worden():
    store.write_derived("d", _df([("2020-01-01", 1.0)]))
    store.write_derived("d", _df([("2020-01-01", 99.0)]))

    assert list(store.read("d")["value"]) == [99.0]


def test_normalize_sorteert_dedupliceert_en_gooit_lege_waarden_weg():
    df = store.normalize(_df([("2020-01-03", 3.0), ("2020-01-01", 1.0), ("2020-01-01", 1.5), ("2020-01-02", None)]))

    assert list(df["date"].dt.strftime("%Y-%m-%d")) == ["2020-01-01", "2020-01-03"]
    assert list(df["value"]) == [1.5, 3.0]  # bij dubbele datum wint de laatste rij


def test_toekomstige_publicatiedatums_worden_niet_opgeslagen():
    """Margin debt en CAPE krijgen een publicatielag; die datum mag nog niet bereikt zijn."""
    morgen = (pd.Timestamp.today() + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    gisteren = (pd.Timestamp.today() - pd.Timedelta(days=1)).strftime("%Y-%m-%d")

    added = store.append("x", _df([(gisteren, 1.0), (morgen, 2.0)]))

    assert added == 1
    assert list(store.read("x")["value"]) == [1.0]


def test_lezen_van_ontbrekende_reeks_geeft_lege_frame():
    assert store.read("bestaat-niet").empty
    assert store.last_date("bestaat-niet") is None
