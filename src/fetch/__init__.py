"""Registry van ruwe reeksen: naam -> aanroepbare fetcher die een DataFrame date,value geeft.

Alles wat hier binnenkomt is *ruwe* data. Afgeleide reeksen (ratio's, YoY, breedte) worden in
derive.py uit deze reeksen berekend.
"""
from __future__ import annotations

from typing import Callable

import pandas as pd

from ..config import load_config
from . import finra, fred, holdings, prices, shiller


def raw_fetchers() -> dict[str, Callable[..., pd.DataFrame]]:
    cfg = load_config()
    registry: dict[str, Callable[..., pd.DataFrame]] = {}

    for name, series_id in cfg["fred_series"].items():
        registry[name] = _bind_fred(series_id)

    tickers = cfg["tickers"]
    for name in ("index", "vix", "vix3m", "spy", "rsp"):
        registry[f"px_{name}"] = _bind_price(tickers[name])
    for ticker in tickers["sectors"]:
        registry[f"px_{ticker.lower()}"] = _bind_price(ticker)

    registry["cape"] = shiller.fetch
    registry["margin_debt"] = finra.fetch
    registry["top10_concentration"] = holdings.fetch
    return registry


def _bind_fred(series_id: str) -> Callable[..., pd.DataFrame]:
    def call(start: str = "1900-01-01") -> pd.DataFrame:
        return fred.fetch(series_id, start=start)

    return call


def _bind_price(ticker: str) -> Callable[..., pd.DataFrame]:
    def call(start: str = "1980-01-01") -> pd.DataFrame:
        return prices.fetch(ticker, start=start)

    return call
