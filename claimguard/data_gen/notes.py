"""Adjuster-note styles: clean, messy/abbreviated, or internally contradictory."""

from __future__ import annotations

from datetime import date
from typing import Any


def render_notes(claim: dict[str, Any], style: str) -> str:
    incident = claim["incident"]
    claimant = claim["claimant"]["full_name"]
    incident_date: date = date.fromisoformat(incident["incident_date"])
    peril = claim["peril"]
    city = incident["location"]["city"]
    if style == "messy":
        return (
            f"FNOL mob. insd {claimant.split()[0]}. {peril} @ {city} "
            f"{incident_date.month}/{incident_date.day}. amt asked "
            f"{claim['claimed_amount']['amount']}. "
            f"{'3p yes. need PR.' if incident.get('third_party_involved') else 'no 3p.'} "
            f"photos {len(claim.get('image_captions', ['x']))} recvd. f/u est."
        )
    if style == "contradictory":
        other_day = incident_date.replace(day=max(1, incident_date.day - 2))
        return (
            f"Insured {claimant} reports a {peril} loss on {incident_date.isoformat()} "
            f"in {city}. Notes from the first call said the loss was "
            f"{other_day.isoformat()} and that there was no third party; the FNOL form "
            f"lists third_party_involved={incident.get('third_party_involved')}. "
            f"One note says airbags did not deploy; another says they did. "
            f"Need a recorded statement before we lean on the photos."
        )
    third = (
        "A third party is involved; request the police report before settlement."
        if incident.get("third_party_involved")
        else "No third party is named."
    )
    return (
        f"First notice received for {claimant}. Loss date {incident_date.isoformat()}, "
        f"{peril} in {city}, {incident['location']['state']}. "
        f"{incident['description']} {third} Claimed amount "
        f"${claim['claimed_amount']['amount']}. Photos appear consistent with the "
        f"stated peril pending a closer desk review."
    )
