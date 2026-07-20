"""FRED-API: HY OAS, rentecurve, NFCI en de 10-jaars reële rente.

FRED reviseert sommige reeksen (NFCI vooral). De store houdt bestaande datums vast, dus een
revisie sijpelt niet met terugwerkende kracht de historie in.
"""
from __future__ import annotations

import logging

import pandas as pd

from ..config import FRED_API_KEY
from .base import http_get, to_series

log = logging.getLogger(__name__)

BASE_URL = "https://api.stlouisfed.org/fred/series/observations"


def fetch(series_id: str, start: str = "1900-01-01") -> pd.DataFrame:
    if not FRED_API_KEY:
        raise RuntimeError("FRED_API_KEY ontbreekt in de omgeving")

    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "observation_start": start,
    }
    payload = http_get(BASE_URL, params=params).json()
    observations = payload.get("observations", [])
    if not observations:
        raise ValueError(f"FRED gaf geen observaties voor {series_id}")

    # FRED codeert ontbrekende waarden als "."; to_numeric maakt daar NaN van, normalize gooit ze weg.
    df = to_series([o["date"] for o in observations], [o["value"] for o in observations])
    log.info("FRED %s: %d observaties (%s t/m %s)", series_id, len(df), df["date"].min().date(), df["date"].max().date())
    return df
