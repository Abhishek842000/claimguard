from uuid import UUID

from claimguard.fraud.entity_index import EntityIndex, build_entity_index
from claimguard.fraud.rules import evaluate_fraud_rules
from tests.unit.test_fraud_agent import _weather_intake


def test_entity_index_finds_shared_phone_in_book() -> None:
    index = build_entity_index()
    peers = index.phone_claim_ids("632-555-4006")
    assert len(peers) >= 2


def test_shared_phone_rule_fires_when_book_has_a_peer() -> None:
    intake = _weather_intake()
    intake = intake.model_copy(
        update={"claimant": intake.claimant.model_copy(update={"phone": "632-555-4006"})}
    )
    hits = evaluate_fraud_rules(intake)
    assert any(hit.rule_id == "FR-SHARED-PHONE" for hit in hits)


def test_unique_phone_does_not_fire_shared_rule() -> None:
    intake = _weather_intake()
    intake = intake.model_copy(
        update={"claimant": intake.claimant.model_copy(update={"phone": "000-555-0199"})}
    )
    hits = evaluate_fraud_rules(intake)
    assert all(hit.rule_id != "FR-SHARED-PHONE" for hit in hits)


def test_shared_phone_subtracts_uuid_claim_id() -> None:
    """Intake.claim_id is a UUID; the book stores strings. Self must not count as a peer."""
    claim_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    book = EntityIndex()
    book.phones["555-0100"] = {claim_id}
    intake = _weather_intake().model_copy(
        update={
            "claim_id": UUID(claim_id),
            "claimant": _weather_intake().claimant.model_copy(update={"phone": "555-0100"}),
        }
    )
    hits = evaluate_fraud_rules(intake, book=book)
    assert all(hit.rule_id != "FR-SHARED-PHONE" for hit in hits)
