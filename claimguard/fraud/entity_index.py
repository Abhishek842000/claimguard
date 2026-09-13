"""Book-of-business entity index for shared-phone / duplicate-VIN rules.

Built from on-disk synthetic + eval `claim.json` files. This is the same
signal a production graph store would compute; we do not read `ground_truth`.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class EntityIndex:
    phones: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    vins: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    emails: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))

    def phone_claim_ids(self, phone: str) -> set[str]:
        return self.phones.get(phone, set())

    def vin_claim_ids(self, vin: str) -> set[str]:
        return self.vins.get(vin, set())

    def email_claim_ids(self, email: str) -> set[str]:
        return self.emails.get(email, set())


def build_entity_index(root: Path | None = None) -> EntityIndex:
    base = root or REPO_ROOT
    index = EntityIndex()
    for path in [
        *sorted((base / "data" / "synthetic_claims").glob("*/claim.json")),
        *sorted((base / "data" / "eval_set" / "cases").glob("*/claim.json")),
    ]:
        raw = json.loads(path.read_text(encoding="utf-8"))
        claim_id = str(raw.get("claim_id") or path.parent.name)
        claimant = raw.get("claimant") or {}
        phone = claimant.get("phone")
        email = claimant.get("email")
        if phone:
            index.phones[str(phone)].add(claim_id)
        if email:
            index.emails[str(email)].add(claim_id)
        vehicle = (raw.get("incident") or {}).get("vehicle") or {}
        vin = vehicle.get("vin")
        if vin:
            index.vins[str(vin)].add(claim_id)
    return index


@lru_cache(maxsize=1)
def get_entity_index() -> EntityIndex:
    return build_entity_index()
