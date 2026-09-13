"""Run the intake agent against one synthetic claim folder and print the result.

Usage:
    uv run python scripts/run_intake_sample.py
    uv run python scripts/run_intake_sample.py --claim-dir data/synthetic_claims/<id>
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from claimguard.agents.intake_agent import intake_input_from_claim_dir, run_intake
from claimguard.intake.pdf_parser import parse_document

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CLAIM = ROOT / "data/synthetic_claims/09d919dc-2168-544f-8ec0-4a0f018c8ef6"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claim-dir", type=Path, default=DEFAULT_CLAIM)
    args = parser.parse_args()
    payload = intake_input_from_claim_dir(args.claim_dir)
    print(f"claim_id={payload.claim_id}")
    print(f"documents={len(payload.raw_documents)} images={len(payload.raw_images)}")
    for ref in payload.raw_documents:
        parsed = parse_document(ref)
        print(f"  parse {ref.filename}: method={parsed.method} chars={len(parsed.text)}")
    update = run_intake(payload)
    if update.get("error"):
        print("ERROR", update["error"])
        print("requires_human_review", update.get("requires_human_review"))
        return
    intake = update["intake"]
    assert intake is not None
    dump = intake.model_dump(mode="json")
    print("policy_number", dump["policy_number"])
    print("claimant", dump["claimant"]["full_name"])
    print("incident_type", dump["incident"]["incident_type"])
    print("incident_date", dump["incident"]["incident_date"])
    print("claimed_amount", dump["claimed_amount"])
    print("missing_fields", dump["missing_fields"])
    print("intake_confidence", dump["intake_confidence"])
    print("entities", [(e["entity_type"], e["value"]) for e in dump["extracted_entities"]])
    print("parser_versions", dump["parser_versions"])
    print("--- ClaimIntake JSON ---")
    print(json.dumps(dump, indent=2, default=str))


if __name__ == "__main__":
    main()
