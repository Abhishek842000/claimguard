"""Deterministic FNOL-line parser used when no LLM completer is injected.

The production path is still `generate_structured`. This completer lets a
sample claim run end-to-end without an API key so we can inspect parse + NER.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from claimguard.schemas.common import GeoLocation, IncidentType, Money
from claimguard.schemas.intake import (
    ClaimantProfile,
    IncidentDetails,
    IntakeExtraction,
    VehicleInfo,
)

_LABEL = re.compile(r"^(?P<label>[A-Za-z][A-Za-z /]+):\s*(?P<value>.*)$")
_MONEY_AMOUNT = re.compile(r"(\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{2})?")


def heuristic_extract(document_text: str, notes: str = "") -> IntakeExtraction:
    fields = _labeled_fields(document_text)
    blob = f"{document_text}\n{notes}"

    policy = _clean(fields.get("policy number"))
    name = _clean(fields.get("named insured")) or _first_person(blob)
    email = _clean(fields.get("email"))
    phone = _clean(fields.get("phone"))
    incident_type = _incident_type(_clean(fields.get("incident type")) or _clean(fields.get("peril")))
    incident_date = _parse_date(_clean(fields.get("date of loss"))) or _first_date(blob)
    reported = _parse_date(_clean(fields.get("date reported")))
    location = _parse_location(_clean(fields.get("location")))
    amount = _parse_money(_clean(fields.get("claimed amount"))) or _first_money(blob)
    description = _loss_description(document_text) or notes or "Loss description not extracted."
    third_party = _truthy(_clean(fields.get("third party")))
    police = _clean(fields.get("police report"))
    if police and police.lower() in {"not attached", "none", "n/a"}:
        police = None
    vehicle = _parse_vehicle(_clean(fields.get("vehicle")))

    missing: list[str] = []
    if not policy:
        missing.append("policy_number")
    if not name:
        missing.append("claimant.full_name")
    if amount is None:
        missing.append("claimed_amount")
    if vehicle is None and incident_type.value.startswith("auto_"):
        missing.append("incident.vehicle")

    confidence = max(0.35, 0.95 - 0.08 * len(missing))
    return IntakeExtraction(
        policy_number=policy,
        claimant=ClaimantProfile(full_name=name or "Unknown claimant", email=email, phone=phone),
        incident=IncidentDetails(
            incident_type=incident_type,
            incident_date=incident_date or date(1970, 1, 1),
            reported_date=reported,
            description=description,
            location=location,
            third_party_involved=third_party,
            police_report_number=police,
            vehicle=vehicle,
        ),
        claimed_amount=amount,
        missing_fields=missing,
        intake_confidence=round(confidence, 2),
    )


class HeuristicIntakeCompleter:
    """Completer that ignores the model and returns heuristic JSON."""

    def __init__(self, document_text: str, notes: str = "") -> None:
        self.document_text = document_text
        self.notes = notes

    def complete(self, messages: list[dict[str, str]], *, schema_name: str) -> str:
        return heuristic_extract(self.document_text, self.notes).model_dump_json()


def _labeled_fields(text: str) -> dict[str, str]:
    """Parse `Label: value` rows, including reportlab extracts where the value is on the next line."""

    fields: dict[str, str] = {}
    lines = [line.strip() for line in text.splitlines()]
    pending: str | None = None
    for line in lines:
        if pending:
            if line and not _LABEL.match(line):
                fields[pending] = line
                pending = None
                continue
            pending = None
        match = _LABEL.match(line)
        if not match:
            continue
        label = match.group("label").strip().lower()
        value = (match.group("value") or "").strip()
        if value:
            fields[label] = value
        else:
            pending = label
    return fields


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _incident_type(raw: str | None) -> IncidentType:
    if not raw:
        return IncidentType.OTHER
    key = raw.strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "hail": IncidentType.AUTO_WEATHER,
        "collision": IncidentType.AUTO_COLLISION,
        "theft": IncidentType.AUTO_THEFT,
        "vandalism": IncidentType.AUTO_VANDALISM,
        "water": IncidentType.PROPERTY_WATER,
        "fire": IncidentType.PROPERTY_FIRE,
        "weather": IncidentType.AUTO_WEATHER,
    }
    if key in IncidentType._value2member_map_:
        return IncidentType(key)
    return aliases.get(key, IncidentType.OTHER)


def _parse_date(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return datetime.strptime(raw[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _first_date(text: str) -> date | None:
    match = re.search(r"20\d{2}-\d{2}-\d{2}", text)
    return _parse_date(match.group(0)) if match else None


def _parse_money(raw: str | None) -> Money | None:
    if not raw:
        return None
    match = _MONEY_AMOUNT.search(raw.replace("USD", ""))
    if not match:
        return None
    try:
        return Money(amount=Decimal(match.group(0).replace(",", "")))
    except (InvalidOperation, ValueError):
        return None


def _first_money(text: str) -> Money | None:
    match = re.search(r"\$\s*" + _MONEY_AMOUNT.pattern, text)
    return _parse_money(match.group(0) if match else None)


def _parse_location(raw: str | None) -> GeoLocation | None:
    if not raw:
        return None
    # "1224 Highland Dr, Phoenix, AZ 85004"
    match = re.match(
        r"(?P<street>.+),\s*(?P<city>[^,]+),\s*(?P<state>[A-Z]{2})\s+(?P<zip>\d{5}(?:-\d{4})?)",
        raw,
    )
    if not match:
        return None
    return GeoLocation(
        city=match.group("city").strip(),
        state=match.group("state"),
        postal_code=match.group("zip"),
        street_address=match.group("street").strip(),
    )


def _parse_vehicle(raw: str | None) -> VehicleInfo | None:
    if not raw:
        return None
    match = re.search(
        r"(?P<year>19\d{2}|20\d{2})\s+(?P<make>\S+)\s+(?P<model>\S+).*VIN\s+(?P<vin>[A-HJ-NPR-Z0-9]{17})",
        raw,
        re.IGNORECASE,
    )
    if not match:
        return VehicleInfo()
    return VehicleInfo(
        year=int(match.group("year")),
        make=match.group("make"),
        model=match.group("model"),
        vin=match.group("vin"),
    )


def _loss_description(text: str) -> str | None:
    marker = "Loss description"
    idx = text.find(marker)
    if idx < 0:
        return None
    body = text[idx + len(marker) :].strip(" \n:")
    # Stop at the next obvious footer if present.
    for stop in ("Adjuster notes", "Page ", "Specimen"):
        cut = body.find(stop)
        if cut > 20:
            body = body[:cut]
    body = body.strip()
    return body or None


def _truthy(raw: str | None) -> bool:
    if not raw:
        return False
    return raw.strip().lower() in {"yes", "true", "y", "1"}


def _first_person(text: str) -> str | None:
    match = re.search(r"First notice received for ([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\.", text)
    return match.group(1) if match else None
