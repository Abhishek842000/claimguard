from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_policy_and_fraud_counts() -> None:
    policies = list((ROOT / "data" / "policy_docs").glob("*.md"))
    policies = [p for p in policies if p.name != "README.md"]
    fraud = list((ROOT / "data" / "fraud_corpus").glob("fraud-*.md"))
    assert 5 <= len(policies) <= 10
    assert 10 <= len(fraud) <= 20
