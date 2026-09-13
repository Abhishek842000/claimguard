"""Deterministic fraud signals. These run before the LLM synthesis call."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from claimguard.data_gen.weather import has_hail_or_wind
from claimguard.fraud.entity_index import EntityIndex, get_entity_index
from claimguard.schemas.fraud import FraudRuleHit
from claimguard.schemas.intake import ClaimIntake


def evaluate_fraud_rules(
    intake: ClaimIntake,
    *,
    book: EntityIndex | None = None,
    image_uris: list[str] | None = None,
) -> list[FraudRuleHit]:
    hits: list[FraudRuleHit] = []
    incident = intake.incident
    index = book if book is not None else get_entity_index()
    claim_id = str(intake.claim_id)
    if incident.third_party_involved and not incident.police_report_number:
        hits.append(
            FraudRuleHit(
                rule_id="FR-MISSING-POLICE-REPORT",
                rule_name="Police report referenced but not attached",
                severity="low",
                detail="third_party_involved is true and police_report_number is null.",
            )
        )
    location = incident.location
    weather_perils = {"auto_weather", "property_weather"}
    if location and str(incident.incident_type) in weather_perils:
        observed = has_hail_or_wind(location.city, location.state, incident.incident_date)
        if not observed:
            hits.append(
                FraudRuleHit(
                    rule_id="FR-WEATHER-MISMATCH",
                    rule_name="Claimed storm has no NOAA fixture event",
                    severity="high",
                    detail=(
                        f"No hail/wind event in the frozen NOAA fixture for "
                        f"{location.city}, {location.state} on {incident.incident_date.isoformat()}."
                    ),
                )
            )
    vehicle = incident.vehicle
    if vehicle and vehicle.vin and len(vehicle.vin) != 17:
        hits.append(
            FraudRuleHit(
                rule_id="FR-VIN-LENGTH",
                rule_name="VIN is not 17 characters",
                severity="medium",
                detail="Extracted VIN failed the 17-character check.",
            )
        )
    if intake.claimant.phone:
        peers = index.phone_claim_ids(intake.claimant.phone) - {claim_id}
        if peers:
            hits.append(
                FraudRuleHit(
                    rule_id="FR-SHARED-PHONE",
                    rule_name="Phone number appears on another claim",
                    severity="high",
                    detail=f"Shared with {len(peers)} other claim(s) in the book of business.",
                )
            )
    if intake.claimant.email:
        peers = index.email_claim_ids(intake.claimant.email) - {claim_id}
        if peers:
            hits.append(
                FraudRuleHit(
                    rule_id="FR-SHARED-EMAIL",
                    rule_name="Email appears on another claim",
                    severity="medium",
                    detail=f"Shared with {len(peers)} other claim(s).",
                )
            )
    if vehicle and vehicle.vin:
        peers = index.vin_claim_ids(vehicle.vin) - {claim_id}
        if peers:
            hits.append(
                FraudRuleHit(
                    rule_id="FR-DUPLICATE-VIN",
                    rule_name="VIN appears on another claim",
                    severity="high",
                    detail=f"Shared with {len(peers)} other claim(s) in the book of business.",
                )
            )
    uris = image_uris if image_uris is not None else [image.storage_uri for image in intake.images]
    exif_hit = _exif_mismatch(intake, uris)
    if exif_hit is not None:
        hits.append(exif_hit)
    return hits


def _exif_mismatch(intake: ClaimIntake, image_uris: list[str]) -> FraudRuleHit | None:
    if intake.incident.incident_date.year < 2000:
        return None
    try:
        import piexif
    except ImportError:
        return None
    for uri in image_uris:
        path = _uri_to_path(uri)
        if path is None or not path.is_file():
            continue
        try:
            exif = piexif.load(str(path))
            raw = exif.get("Exif", {}).get(piexif.ExifIFD.DateTimeOriginal)
            if not raw:
                continue
            stamp = raw.decode() if isinstance(raw, bytes) else str(raw)
            taken = datetime.strptime(stamp, "%Y:%m:%d %H:%M:%S")
        except Exception:
            continue
        delta = abs((taken.date() - intake.incident.incident_date).days)
        if delta >= 7:
            return FraudRuleHit(
                rule_id="FR-PHOTO-EXIF",
                rule_name="Photo EXIF date is offset from the loss date",
                severity="high",
                detail=f"{path.name} EXIF is {delta} day(s) away from the incident date.",
            )
    return None


def _uri_to_path(uri: str) -> Path | None:
    if uri.startswith("file:"):
        parsed = urlparse(uri)
        return Path(parsed.path)
    path = Path(uri)
    return path if path.exists() else None
