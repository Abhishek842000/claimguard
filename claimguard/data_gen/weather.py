"""Frozen NOAA-shaped storm lookup.

A live NOAA CDO pull needs a token and is not reproducible in CI. This
module reads `data/weather/noaa_reference.json`. `refresh_from_noaa` is
the documented swap-in when NOAA_TOKEN is set.
"""

from __future__ import annotations

import json
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

REFERENCE_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "weather" / "noaa_reference.json"
)


@lru_cache
def load_events(path: Path | None = None) -> list[dict[str, Any]]:
    raw = json.loads((path or REFERENCE_PATH).read_text())
    return list(raw["events"])


def lookup_severe_weather(
    city: str,
    state: str,
    on: date,
    *,
    types: frozenset[str] | None = None,
) -> list[dict[str, Any]]:
    """Return fixture events matching city/state/date (and optional type set)."""
    iso = on.isoformat()
    hits = [
        event
        for event in load_events()
        if event["city"].lower() == city.lower()
        and event["state"].upper() == state.upper()
        and event["date"] == iso
    ]
    if types is not None:
        hits = [event for event in hits if event["type"] in types]
    return hits


def has_hail_or_wind(city: str, state: str, on: date) -> bool:
    return bool(
        lookup_severe_weather(
            city,
            state,
            on,
            types=frozenset({"hail", "thunderstorm_wind", "high_wind", "tropical_storm"}),
        )
    )


def refresh_from_noaa(_token: str) -> None:
    """Placeholder: pull NCEI CDO storm events and rewrite the fixture.

    Intentionally unimplemented so eval dates stay frozen. Wire this only
    when you are deliberately versioning a new weather extract.
    """
    raise NotImplementedError(
        "Live NOAA refresh is opt-in. Keep the frozen fixture for eval reproducibility."
    )
