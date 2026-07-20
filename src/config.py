"""Laden van config.yaml en omgevingsinstellingen."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "config.yaml"
HISTORY_DIR = REPO_ROOT / "data" / "history"
STATE_DIR = REPO_ROOT / "state"
FETCH_STATUS_PATH = STATE_DIR / "fetch_status.json"
RISK_JSON_PATH = REPO_ROOT / "risk.json"
HISTORY_CSV_PATH = REPO_ROOT / "history.csv"
VALIDATION_PATH = REPO_ROOT / "VALIDATION.md"

FRED_API_KEY = os.environ.get("FRED_API_KEY")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

SONNET_MODEL = os.environ.get("SONNET_MODEL", "claude-sonnet-5")


@lru_cache(maxsize=1)
def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def indicator_specs() -> dict[str, dict]:
    """Platte map indicator -> {pillar, axis, weight, direction}."""
    cfg = load_config()
    specs: dict[str, dict] = {}
    for pillar, pcfg in cfg["pillars"].items():
        for name, icfg in pcfg["indicators"].items():
            specs[name] = {
                "pillar": pillar,
                "axis": pcfg["axis"],
                "weight": icfg["weight"],
                "direction": icfg["direction"],
            }
    return specs
