"""Build synthetic claim records, then inject measurable fraud signals."""

from __future__ import annotations

import random
import string
from datetime import date, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid5

from claimguard.data_gen.constants import (
    CITIES,
    FIRST_NAMES,
    LAST_NAMES,
    RECIPES,
    SEVERITY_SCORE,
    STREETS,
    TARGET_FRAUD_RATE,
    VEHICLES,
)
from claimguard.data_gen.weather import has_hail_or_wind

NAMESPACE = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
VIN_ALPHABET = "ABCDEFGHJKLMNPRSTUVWXYZ0123456789"


def make_vin(rng: random.Random) -> str:
    return "".join(rng.choice(VIN_ALPHABET) for _ in range(17))


def pick_recipe(rng: random.Random) -> tuple:
    weights = [recipe[6] for recipe in RECIPES]
    return rng.choices(list(RECIPES), weights=weights, k=1)[0]


def _phone(rng: random.Random) -> str:
    return f"{rng.randint(200, 989)}-555-{rng.randint(1000, 9899)}"


def _date(rng: random.Random) -> date:
    return date(2026, 1, 1) + timedelta(days=rng.randint(0, 240))


def build_base_claim(rng: random.Random, index: int, recipe: tuple) -> dict[str, Any]:
    (
        key,
        lob,
        incident_type,
        coverage,
        severity,
        peril,
        _weight,
        amt_lo,
        amt_hi,
    ) = recipe
    claim_id = str(uuid5(NAMESPACE, f"claimguard:{index}"))
    city, state, zipc = rng.choice(CITIES)
    first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
    incident_date = _date(rng)
    lag = rng.choice([0, 1, 1, 2, 4, 8, 35])
    reported = incident_date + timedelta(days=lag)
    amount = Decimal(rng.randint(amt_lo, amt_hi)).quantize(Decimal("0.01"))
    third_party = incident_type == "auto_collision" and rng.random() < 0.7
    vehicle = None
    if lob == "auto":
        year, make, model = rng.choice(VEHICLES)
        vehicle = {
            "year": year,
            "make": make,
            "model": model,
            "vin": make_vin(rng),
            "license_plate": f"{rng.randint(1, 9)}{rng.choice(string.ascii_uppercase)}{rng.choice(string.ascii_uppercase)}{rng.choice(string.ascii_uppercase)}{rng.randint(100, 999)}",
            "odometer": rng.randint(12_000, 140_000),
            "prior_odometer": None,
            "prior_odometer_date": None,
        }
    if peril in {"hail", "wind"} and not has_hail_or_wind(city, state, incident_date):
        # Legitimate weather claims are pinned to a fixture storm date in-city.
        from claimguard.data_gen.weather import load_events

        matches = [
            e
            for e in load_events()
            if e["city"] == city and e["state"] == state and e["type"] in {"hail", "high_wind", "thunderstorm_wind"}
        ]
        if matches:
            incident_date = date.fromisoformat(rng.choice(matches)["date"])
            reported = incident_date + timedelta(days=rng.choice([0, 1, 2]))

    description = _description(peril, city, incident_type, third_party)
    police = f"{state}-{rng.randint(100000, 999999)}" if third_party and rng.random() < 0.55 else None
    notes_style = rng.choice(["clean", "clean", "messy", "contradictory"])
    n_photos = 1 if severity == "low" else rng.choice([2, 2, 3])
    captions = [f"{peril} photo {i + 1} — {city}" for i in range(n_photos)]
    prefix = "PA" if lob == "auto" else "HO"
    claim: dict[str, Any] = {
        "claim_id": claim_id,
        "recipe_key": key,
        "line_of_business": lob,
        "policy_number": f"{prefix}-2026-{index:06d}",
        "policy_form": "PAP-CG-01" if lob == "auto" else "HO3-CG-01",
        "peril": peril,
        "claimant": {
            "full_name": f"{first} {last}",
            "email": f"{first}.{last}.{index}@example.test".lower(),
            "phone": _phone(rng),
            "date_of_birth": f"{rng.randint(1965, 2000)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
        },
        "incident": {
            "incident_type": incident_type,
            "incident_date": incident_date.isoformat(),
            "reported_date": reported.isoformat(),
            "description": description,
            "location": {
                "city": city,
                "state": state,
                "postal_code": zipc,
                "street_address": f"{rng.randint(100, 8900)} {rng.choice(STREETS)}",
            },
            "third_party_involved": third_party,
            "police_report_number": police,
            "vehicle": vehicle,
        },
        "claimed_amount": {"amount": f"{amount:.2f}", "currency": "USD"},
        "notes_style": notes_style,
        "image_captions": captions,
        "injected_fraud_signals": [],
        "ground_truth": {
            "is_fraud": False,
            "fraud_label": "legitimate",
            "coverage_status": coverage,
            "severity_band": severity,
            "severity_score": SEVERITY_SCORE[severity],
            "expected_routing": _routing(False, coverage, severity, police, third_party, notes_style),
            "rationale": _rationale(coverage, peril, False, []),
        },
    }
    if lag >= 30:
        claim["ground_truth"]["expected_routing"] = "human_review"
    return claim


def inject_fraud_signals(claims: list[dict[str, Any]], rng: random.Random) -> None:
    """Mutate ~20% of claims with detectable, labeled patterns."""
    n_fraud = max(1, round(len(claims) * TARGET_FRAUD_RATE))
    targets = rng.sample(range(len(claims)), k=n_fraud)
    donors = [i for i in range(len(claims)) if i not in targets]
    tactics = [
        "duplicate_vin",
        "weather_mismatch",
        "photo_exif_mismatch",
        "mileage_inconsistency",
        "inflated_estimate",
        "shared_phone",
    ]
    for i, idx in enumerate(targets):
        tactic = tactics[i % len(tactics)]
        claim = claims[idx]
        signals = [tactic]
        if tactic == "duplicate_vin":
            _duplicate_vin(claim, claims[donors[i % len(donors)]])
        elif tactic == "weather_mismatch":
            _weather_mismatch(claim)
        elif tactic == "photo_exif_mismatch":
            claim["exif_offset_days"] = rng.choice([-21, -14, 18, 27])
        elif tactic == "mileage_inconsistency":
            _mileage_inconsistency(claim)
        elif tactic == "inflated_estimate":
            claim["claimed_amount"]["amount"] = "18500.00"
            claim["ground_truth"]["severity_band"] = "low"
            claim["ground_truth"]["severity_score"] = SEVERITY_SCORE["low"]
        elif tactic == "shared_phone":
            donor = claims[donors[i % len(donors)]]
            claim["claimant"]["phone"] = donor["claimant"]["phone"]
            signals.append("shared_entity")
        claim["injected_fraud_signals"] = signals
        claim["ground_truth"]["is_fraud"] = True
        claim["ground_truth"]["fraud_label"] = "fraud"
        claim["ground_truth"]["expected_routing"] = "human_review"
        claim["ground_truth"]["rationale"] = _rationale(
            claim["ground_truth"]["coverage_status"],
            claim["peril"],
            True,
            signals,
        )


def _duplicate_vin(claim: dict[str, Any], donor: dict[str, Any]) -> None:
    donor_vin = (donor.get("incident") or {}).get("vehicle", {}) or {}
    if not donor_vin.get("vin"):
        # Invent a shared VIN even if donor is a home claim.
        donor_vin = {"vin": make_vin(random.Random(7))}
    if claim["incident"].get("vehicle") is None:
        claim["incident"]["vehicle"] = {
            "year": 2019,
            "make": "Toyota",
            "model": "Camry",
            "vin": donor_vin["vin"],
            "license_plate": "8SYN001",
            "odometer": 54000,
        }
        claim["line_of_business"] = "auto"
        claim["policy_form"] = "PAP-CG-01"
    else:
        claim["incident"]["vehicle"]["vin"] = donor_vin["vin"]


def _weather_mismatch(claim: dict[str, Any]) -> None:
    # Phoenix has no fixture hail events — a hail FNOL there is ungrounded.
    claim["peril"] = "hail"
    claim["incident"]["incident_type"] = (
        "auto_weather" if claim["line_of_business"] == "auto" else "property_weather"
    )
    claim["incident"]["location"]["city"] = "Phoenix"
    claim["incident"]["location"]["state"] = "AZ"
    claim["incident"]["location"]["postal_code"] = "85004"
    claim["incident"]["incident_date"] = "2026-06-12"
    claim["incident"]["reported_date"] = "2026-06-13"
    claim["incident"]["description"] = (
        "Insured reports golf-ball hail in Phoenix on 2026-06-12 that dented "
        "every horizontal panel. Neighbor did not report a storm."
    )


def _mileage_inconsistency(claim: dict[str, Any]) -> None:
    vehicle = claim["incident"].get("vehicle")
    if vehicle is None:
        return
    vehicle["prior_odometer"] = vehicle["odometer"] + 18000
    vehicle["prior_odometer_date"] = (
        date.fromisoformat(claim["incident"]["incident_date"]) - timedelta(days=20)
    ).isoformat()


def _description(peril: str, city: str, incident_type: str, third_party: bool) -> str:
    if peril == "collision":
        extra = " Another driver is identified." if third_party else " No other vehicle is named."
        return f"Low-to-moderate speed impact in {city}.{extra} Visible bumper and lamp damage."
    if incident_type == "auto_theft":
        return f"Covered auto missing from street parking in {city}. Keys accounted for. Police notified."
    if incident_type == "property_theft":
        return f"Forced rear-door entry in {city}. Electronics and jewelry missing."
    if peril == "vandalism":
        return f"Keyed panels and a smashed side glass overnight in {city}."
    if peril == "hail":
        return f"Hood and roof show circular dings after a hail cell moved through {city}."
    if peril == "mechanical_breakdown":
        return f"Transmission failed on the highway near {city}. Bumper is unmarked. Insured says they 'must have hit something.'"
    if peril == "fire":
        return f"Kitchen fire on the residence premises in {city}. Fire department extinguished. Smoke throughout first floor."
    if peril == "sudden_pipe":
        return f"Supply line under the sink burst while the insured was home in {city}. Water stopped within an hour."
    if peril == "flood":
        return f"Surface water from the street entered the first floor in {city} after heavy rain."
    if peril == "wind":
        return f"Wind-thrown limb punctured the rear roof plane in {city}."
    return f"Loss involving {peril} in {city}."


def _routing(
    is_fraud: bool,
    coverage: str,
    severity: str,
    police: str | None,
    third_party: bool,
    notes_style: str,
) -> str:
    if is_fraud:
        return "human_review"
    if coverage in {"excluded", "insufficient_information", "partially_covered"}:
        return "human_review"
    if third_party and not police:
        return "human_review"
    if notes_style == "contradictory":
        return "human_review"
    if severity in {"high", "catastrophic"}:
        return "human_review"
    return "auto_resolve"


def _rationale(coverage: str, peril: str, is_fraud: bool, signals: list[str]) -> str:
    bits = [f"Coverage label {coverage} follows specimen wording for peril '{peril}'."]
    if is_fraud:
        bits.append("Fraud label is positive because injected signals " + ", ".join(signals) + ".")
    else:
        bits.append("No injected fraud signals.")
    return " ".join(bits)
