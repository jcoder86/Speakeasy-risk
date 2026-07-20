"""Append-only historie-opslag: data/history/<naam>.csv met kolommen date,value.

Historie is heilig. Nieuwe datums worden toegevoegd; bestaande datums behouden standaard de
waarde die we destijds hebben vastgelegd, ook als de bron later reviseert. Dat maakt de
point-in-time-eigenschap gratis: wat er in de CSV staat, is wat we op dat moment wisten.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from .config import HISTORY_DIR

log = logging.getLogger(__name__)

COLUMNS = ["date", "value"]


def path_for(name: str) -> Path:
    return HISTORY_DIR / f"{name}.csv"


def empty_series() -> pd.DataFrame:
    return pd.DataFrame({"date": pd.Series(dtype="datetime64[ns]"), "value": pd.Series(dtype="float64")})


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Dwing het contract af: kolommen date,value, gesorteerd, uniek, zonder NaN."""
    if df is None or len(df) == 0:
        return empty_series()
    out = df.loc[:, COLUMNS].copy()
    out["date"] = pd.to_datetime(out["date"]).dt.normalize()
    out["value"] = pd.to_numeric(out["value"], errors="coerce")
    out = out.dropna(subset=["date", "value"])
    out = out.drop_duplicates(subset="date", keep="last")
    return out.sort_values("date").reset_index(drop=True)


def drop_future(df: pd.DataFrame, today: pd.Timestamp | None = None) -> pd.DataFrame:
    """Gooi rijen weg die na vandaag gedateerd zijn.

    Bronnen met een publicatielag (CAPE, margin debt) leveren een waarde waarvan de
    publicatiedatum nog moet aanbreken. Die nu al opslaan zou precies de lookahead introduceren
    die de lag moet voorkomen. De volgende run pikt de rij op zodra de datum bereikt is.
    """
    if df.empty:
        return df
    cutoff = pd.Timestamp(today or pd.Timestamp.today()).normalize()
    future = df["date"] > cutoff
    if future.any():
        log.info("%d rij(en) met een toekomstige publicatiedatum overgeslagen.", int(future.sum()))
    return df[~future].reset_index(drop=True)


def read(name: str) -> pd.DataFrame:
    p = path_for(name)
    if not p.exists():
        return empty_series()
    try:
        return normalize(pd.read_csv(p))
    except Exception as e:  # corrupte CSV mag de run niet slopen
        log.error("Historie %s kon niet worden gelezen: %s", name, e)
        return empty_series()


def last_date(name: str) -> pd.Timestamp | None:
    df = read(name)
    return None if df.empty else df["date"].iloc[-1]


def append(name: str, incoming: pd.DataFrame, allow_revision: bool = False) -> int:
    """Voeg nieuwe datums toe. Geeft het aantal toegevoegde rijen terug.

    allow_revision=True overschrijft bestaande datums — alleen voor afgeleide reeksen, die
    per definitie herberekend worden uit de ruwe historie.
    """
    incoming = drop_future(normalize(incoming))
    if incoming.empty:
        return 0

    existing = read(name)
    if existing.empty:
        merged, added = incoming, len(incoming)
    elif allow_revision:
        merged = pd.concat([existing, incoming]).drop_duplicates(subset="date", keep="last")
        added = int((~incoming["date"].isin(existing["date"])).sum())
    else:
        fresh = incoming[~incoming["date"].isin(existing["date"])]
        merged, added = pd.concat([existing, fresh]), len(fresh)

    merged = normalize(merged)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path_for(name).with_suffix(".csv.tmp")
    merged.to_csv(tmp, index=False, date_format="%Y-%m-%d", float_format="%.6f")
    tmp.replace(path_for(name))
    return added


def write_derived(name: str, df: pd.DataFrame) -> int:
    """Afgeleide reeks wegschrijven: mag bestaande waarden herberekenen."""
    return append(name, df, allow_revision=True)


def available() -> list[str]:
    if not HISTORY_DIR.exists():
        return []
    return sorted(p.stem for p in HISTORY_DIR.glob("*.csv"))


def load_all() -> dict[str, pd.DataFrame]:
    return {name: read(name) for name in available()}
