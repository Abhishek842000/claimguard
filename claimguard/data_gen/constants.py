"""Fixed knobs for a reproducible synthetic book of business."""

from __future__ import annotations

DEFAULT_SEED = 42
DEFAULT_N_CLAIMS = 55
DEFAULT_EVAL_N = 18
TARGET_FRAUD_RATE = 0.20

CITIES: list[tuple[str, str, str]] = [
    ("Denver", "CO", "80203"),
    ("Austin", "TX", "78701"),
    ("Chicago", "IL", "60611"),
    ("Seattle", "WA", "98101"),
    ("Atlanta", "GA", "30303"),
    ("Phoenix", "AZ", "85004"),
    ("Boston", "MA", "02108"),
    ("Nashville", "TN", "37203"),
    ("San Francisco", "CA", "94103"),
    ("Miami", "FL", "33130"),
]

FIRST_NAMES = [
    "Jordan",
    "Riley",
    "Casey",
    "Avery",
    "Quinn",
    "Morgan",
    "Cameron",
    "Reese",
    "Skyler",
    "Harper",
    "Logan",
    "Parker",
    "Drew",
    "Finley",
    "Rowan",
]
LAST_NAMES = [
    "Hale",
    "Okoye",
    "Brennan",
    "Singh",
    "Vargas",
    "Nguyen",
    "Patel",
    "Kowalski",
    "Diaz",
    "Okafor",
    "Berg",
    "Cho",
    "Ibrahim",
    "Sullivan",
    "Moreau",
]
STREETS = [
    "Market St",
    "Pine Ave",
    "Cedar Rd",
    "Highland Dr",
    "Summit Blvd",
    "Oak Ct",
    "Riverway",
    "Lakeshore Dr",
]
VEHICLES = [
    (2018, "Honda", "Civic"),
    (2019, "Toyota", "Camry"),
    (2020, "Ford", "Escape"),
    (2021, "Hyundai", "Tucson"),
    (2017, "Subaru", "Outback"),
    (2022, "Chevrolet", "Equinox"),
    (2016, "Nissan", "Altima"),
    (2023, "Kia", "Sportage"),
]

# Recipe: (key, lob, incident_type, coverage_status, severity_band, peril, weight, amt_lo, amt_hi)
RECIPES: list[tuple] = [
    ("auto_collision", "auto", "auto_collision", "covered", "moderate", "collision", 14, 1800, 7200),
    ("auto_collision_low", "auto", "auto_collision", "covered", "low", "collision", 6, 400, 1600),
    ("auto_theft", "auto", "auto_theft", "covered", "high", "theft", 5, 8000, 22000),
    ("auto_vandalism", "auto", "auto_vandalism", "covered", "low", "vandalism", 4, 600, 2400),
    ("auto_hail", "auto", "auto_weather", "covered", "moderate", "hail", 5, 2200, 6800),
    ("auto_mechanical", "auto", "other", "excluded", "low", "mechanical_breakdown", 3, 900, 2800),
    ("home_fire", "home", "property_fire", "covered", "high", "fire", 5, 12000, 48000),
    ("home_pipe", "home", "property_water", "partially_covered", "moderate", "sudden_pipe", 5, 3500, 14000),
    ("home_flood", "home", "property_water", "excluded", "high", "flood", 4, 15000, 60000),
    ("home_theft", "home", "property_theft", "covered", "moderate", "theft", 4, 1500, 9000),
    ("home_wind", "home", "property_weather", "covered", "moderate", "wind", 4, 2800, 12000),
]

SEVERITY_SCORE = {
    "minimal": 0.12,
    "low": 0.28,
    "moderate": 0.48,
    "high": 0.74,
    "catastrophic": 0.92,
}
