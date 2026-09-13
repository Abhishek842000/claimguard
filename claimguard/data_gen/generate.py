"""Orchestrate claim records → PDFs / photos / notes → eval holdout."""

from __future__ import annotations

import json
import random
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from claimguard.data_gen.constants import DEFAULT_EVAL_N, DEFAULT_N_CLAIMS, DEFAULT_SEED
from claimguard.data_gen.factory import build_base_claim, inject_fraud_signals, pick_recipe
from claimguard.data_gen.notes import render_notes
from claimguard.data_gen.pdf_forms import write_claim_form
from claimguard.data_gen.photos import write_damage_photo
from claimguard.data_gen.split import assert_no_leak, hold_out_eval

ROOT = Path(__file__).resolve().parents[2]


def generate_dataset(
    *,
    n_claims: int = DEFAULT_N_CLAIMS,
    eval_n: int = DEFAULT_EVAL_N,
    seed: int = DEFAULT_SEED,
    claims_dir: Path | None = None,
    eval_dir: Path | None = None,
) -> dict[str, Any]:
    """Generate the Phase 1 book. Eval artifacts never land in claims_dir."""
    claims_dir = claims_dir or (ROOT / "data" / "synthetic_claims")
    eval_dir = eval_dir or (ROOT / "data" / "eval_set")
    rng = random.Random(seed)

    records = [build_base_claim(rng, i, pick_recipe(rng)) for i in range(n_claims)]
    inject_fraud_signals(records, rng)
    dev, ev = hold_out_eval(records, rng, eval_n)
    assert_no_leak({c["claim_id"] for c in dev}, {c["claim_id"] for c in ev})

    _reset_dir(claims_dir, keep_names={".gitkeep", "README.md"})
    _reset_dir(eval_dir / "cases", keep_names=set())
    for path in eval_dir.glob("v0.jsonl"):
        path.unlink()

    for claim in dev:
        _materialize(claim, claims_dir / claim["claim_id"], rng)
    for claim in ev:
        _materialize(claim, eval_dir / "cases" / claim["claim_id"], rng)

    _write_json(claims_dir / "SPLIT.json", _split_manifest(dev, ev, seed))
    _write_json(eval_dir / "holdout_ids.json", sorted(c["claim_id"] for c in ev))
    _write_jsonl(eval_dir / "v0.jsonl", [_eval_row(c, eval_dir) for c in ev])
    _write_json(claims_dir / "DEV_INDEX.json", [_dev_row(c, claims_dir) for c in dev])

    return {
        "n_dev": len(dev),
        "n_eval": len(ev),
        "n_fraud_dev": sum(1 for c in dev if c["ground_truth"]["is_fraud"]),
        "n_fraud_eval": sum(1 for c in ev if c["ground_truth"]["is_fraud"]),
        "claims_dir": str(claims_dir),
        "eval_dir": str(eval_dir),
    }


def _materialize(claim: dict[str, Any], dest: Path, rng: random.Random) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    claim["adjuster_notes"] = render_notes(claim, claim["notes_style"])
    form_path = dest / "documents" / "fnol-claim-form.pdf"
    write_claim_form(form_path, claim)
    claim["documents"] = [
        {
            "filename": "fnol-claim-form.pdf",
            "document_type": "claim_form",
            "relative_path": "documents/fnol-claim-form.pdf",
        }
    ]
    incident_dt = datetime.fromisoformat(claim["incident"]["incident_date"])
    offset = int(claim.get("exif_offset_days") or 0)
    taken = incident_dt + timedelta(days=offset, hours=rng.randint(8, 17))
    images = []
    for i, caption in enumerate(claim["image_captions"]):
        name = f"{claim['peril']}-{i + 1}.jpg"
        photo_path = dest / "images" / name
        write_damage_photo(
            photo_path,
            peril=claim["peril"],
            caption=caption,
            taken_at=taken,
            seed_color=rng.randint(0, 255),
        )
        images.append(
            {
                "filename": name,
                "caption": caption,
                "relative_path": f"images/{name}",
                "exif_datetime": taken.isoformat(timespec="seconds"),
            }
        )
    claim["images"] = images
    (dest / "notes.txt").write_text(claim["adjuster_notes"] + "\n", encoding="utf-8")
    # Ground truth stays on eval copies; strip from the prompt-dev JSON so a
    # later prompt-iteration script cannot casually train on labels.
    stored = dict(claim)
    if claim.get("split") == "dev":
        stored.pop("ground_truth", None)
    _write_json(dest / "claim.json", stored)


def _eval_row(claim: dict[str, Any], eval_dir: Path) -> dict[str, Any]:
    rel = f"cases/{claim['claim_id']}"
    return {
        "claim_id": claim["claim_id"],
        "dataset_version": "v0",
        "split": "eval",
        "line_of_business": claim["line_of_business"],
        "incident_type": claim["incident"]["incident_type"],
        "inputs": {
            "claim_json": f"{rel}/claim.json",
            "pdf": f"{rel}/documents/fnol-claim-form.pdf",
            "notes": f"{rel}/notes.txt",
            "images": [img["relative_path"] for img in claim["images"]],
        },
        "ground_truth_fraud_label": claim["ground_truth"]["fraud_label"],
        "ground_truth_verdict": claim["ground_truth"],
        "injected_fraud_signals": claim["injected_fraud_signals"],
    }


def _dev_row(claim: dict[str, Any], claims_dir: Path) -> dict[str, Any]:
    return {
        "claim_id": claim["claim_id"],
        "split": "dev",
        "line_of_business": claim["line_of_business"],
        "path": claim["claim_id"],
        "injected_fraud_signals": claim["injected_fraud_signals"],
    }


def _split_manifest(dev: list[dict[str, Any]], ev: list[dict[str, Any]], seed: int) -> dict[str, Any]:
    return {
        "seed": seed,
        "dev_ids": sorted(c["claim_id"] for c in dev),
        "eval_ids": sorted(c["claim_id"] for c in ev),
        "note": "eval_ids are stored only under data/eval_set/. Do not copy them into prompt-iteration sets.",
    }


def _reset_dir(path: Path, keep_names: set[str]) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for child in path.iterdir():
        if child.name in keep_names:
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
