"""Deterministic fraud signals. These run before the LLM synthesis call."""

from __future__ import annotations

from claimguard.data_gen.weather import has_hail_or_wind
from claimguard.schemas.fraud import FraudRuleHit
from claimguard.schemas.intake import ClaimIntake


def evaluate_fraud_rules(intake: ClaimIntake) -> list[FraudRuleHit]:
    hits: list[FraudRuleHit] = []
    incident = intake.incident
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
    if incident.vehicle and incident.vehicle.vin and len(incident.vehicle.vin) != 17:
        hits.append(
            FraudRuleHit(
                rule_id="FR-VIN-LENGTH",
                rule_name="VIN is not 17 characters",
                severity="medium",
                detail="Extracted VIN failed the 17-character check.",
            )
        )
    return hits
