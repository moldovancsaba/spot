"""Calibrated confidence for model lanes.

A model's self-reported confidence is not calibrated: the adopted adapter emits a fixed 0.9 prior regardless
of the row. The calibration table replaces self-reported confidence per lane and category with that lane's
measured precision on a held-out gate (script/measure_calibration.py), so thresholds and uncertainty routing
operate on something real. Where the table has no entry, the model's own value stands and no flag is added.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

_CALIBRATION_CACHE: dict[tuple[str, float], dict] = {}

DEFAULT_CALIBRATION_PATH = "models/calibration/calibration-v1.json"


def calibration_path() -> str:
    return os.getenv("SPOT_CALIBRATION_PATH", DEFAULT_CALIBRATION_PATH)


def load_calibration(path: str | None = None) -> dict:
    path = path or calibration_path()
    stat = None
    try:
        stat = os.stat(path).st_mtime
    except OSError:
        return {}
    cached = _CALIBRATION_CACHE.get((path, stat))
    if cached is not None:
        return cached
    try:
        table = json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    if table.get("schema") != "spot.calibration.v1":
        return {}
    _CALIBRATION_CACHE[(path, stat)] = table
    return table


def calibrated_confidence(lane_version: str | None, category: str, reported: float, table: dict) -> tuple[float, bool]:
    """Return (confidence, calibrated) for a lane's proposal."""
    entry = ((table.get("lanes") or {}).get(lane_version or "") or {}).get(category)
    if entry is None:
        try:
            return float(reported), False
        except (TypeError, ValueError):
            return 0.0, False
    try:
        value = float(entry)
    except (TypeError, ValueError):
        return float(reported), False
    return round(min(max(value, 0.0), 1.0), 3), True
