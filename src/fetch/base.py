"""Gedeeld contract voor alle fetchers.

Een fetcher krijgt een startdatum en geeft een DataFrame met kolommen date,value terug.
Falen is toegestaan: `safe_fetch` vangt alles af en levert een FetchResult met ok=False,
waarna de pipeline op de laatst bekende waarde terugvalt en de indicator stale markeert.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable

import httpx
import pandas as pd

log = logging.getLogger(__name__)

USER_AGENT = "Speakeasy-risk/1.0 (+https://github.com/jcoder86/Speakeasy-risk)"
TIMEOUT = httpx.Timeout(60.0, connect=20.0)

Fetcher = Callable[..., pd.DataFrame]


@dataclass
class FetchResult:
    name: str
    df: pd.DataFrame = field(default_factory=pd.DataFrame)
    ok: bool = True
    error: str | None = None

    @property
    def rows(self) -> int:
        return 0 if self.df is None else len(self.df)


def http_get(url: str, **kwargs) -> httpx.Response:
    """GET met nette headers, redirects en een ruime timeout."""
    headers = {"User-Agent": USER_AGENT, **kwargs.pop("headers", {})}
    with httpx.Client(timeout=TIMEOUT, follow_redirects=True, headers=headers) as client:
        resp = client.get(url, **kwargs)
        resp.raise_for_status()
        return resp


def safe_fetch(name: str, fn: Fetcher, *args, **kwargs) -> FetchResult:
    """Draai een fetcher; elke fout wordt een FetchResult(ok=False) in plaats van een crash."""
    try:
        df = fn(*args, **kwargs)
    except Exception as e:
        log.warning("Fetcher %s faalde: %s: %s", name, type(e).__name__, e)
        return FetchResult(name=name, ok=False, error=f"{type(e).__name__}: {e}")

    if df is None or len(df) == 0:
        log.warning("Fetcher %s leverde geen rijen op.", name)
        return FetchResult(name=name, ok=False, error="lege respons")

    return FetchResult(name=name, df=df, ok=True)


def to_series(dates, values) -> pd.DataFrame:
    return pd.DataFrame({"date": pd.to_datetime(dates), "value": pd.to_numeric(values, errors="coerce")})
