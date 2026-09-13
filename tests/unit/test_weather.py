from datetime import date

from claimguard.data_gen.weather import has_hail_or_wind, lookup_severe_weather


def test_denver_hail_fixture_hits() -> None:
    hits = lookup_severe_weather("Denver", "CO", date(2026, 6, 12))
    assert hits and hits[0]["type"] == "hail"


def test_phoenix_has_no_hail_on_storm_date() -> None:
    assert not has_hail_or_wind("Phoenix", "AZ", date(2026, 6, 12))
