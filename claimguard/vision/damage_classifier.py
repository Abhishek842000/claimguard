"""Swappable damage classifier. Agents depend on this protocol, not a model id.

Default is a filename/caption heuristic so CI and local demos do not download
a vision checkpoint. Swap in a fine-tuned HF classifier by implementing
`DamageClassifier` and passing it to `run_vision_agent`.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from claimguard.schemas.common import DamageType, SeverityLevel
from claimguard.schemas.damage import PhotoFinding


class DamageClassifier:
    name = "base"
    version = "0"

    def classify(
        self,
        image_path: Path,
        *,
        image_id: UUID,
        caption: str | None,
        context: str = "",
    ) -> PhotoFinding:
        raise NotImplementedError


class HeuristicDamageClassifier(DamageClassifier):
    """Keyword heuristic over filename, caption, and claim text. No vision weights.

    Uploaded demo photos are often `IMG_1234.jpg` / `demo_img.webp`. Intake
    notes still say "hail dented the hood", so we read that context too.
    """

    name = "heuristic-filename-v1"
    version = "1.1.0"

    def classify(
        self,
        image_path: Path,
        *,
        image_id: UUID,
        caption: str | None,
        context: str = "",
    ) -> PhotoFinding:
        blob = f"{image_path.name} {caption or ''} {context}".lower()
        types: list[DamageType] = []
        severity = SeverityLevel.LOW
        if any(word in blob for word in ("hail", "dent")):
            types.append(DamageType.DENT)
            severity = SeverityLevel.MODERATE
        if any(word in blob for word in ("scratch", "scrape")):
            types.append(DamageType.SCRATCH)
        if any(word in blob for word in ("glass", "windshield", "crack")):
            types.append(DamageType.CRACKED_GLASS)
            severity = SeverityLevel.MODERATE
        if any(word in blob for word in ("light", "taillight", "lamp")):
            types.append(DamageType.BROKEN_LIGHT)
        if any(word in blob for word in ("fire", "char", "burn")):
            types.append(DamageType.FIRE_CHAR)
            severity = SeverityLevel.HIGH
        if any(word in blob for word in ("water", "flood", "stain")):
            types.append(DamageType.WATER_STAIN)
            severity = SeverityLevel.MODERATE
        if any(word in blob for word in ("airbag",)):
            types.append(DamageType.DEPLOYED_AIRBAG)
            severity = SeverityLevel.HIGH
        if not types:
            types = [DamageType.UNKNOWN]
            severity = SeverityLevel.LOW
        return PhotoFinding(
            image_id=image_id,
            damage_types=types,
            severity=severity,
            consistency_notes=(
                "Heuristic labels from filename, caption, and claim text; "
                "not a trained vision model."
            ),
            confidence=0.62 if types != [DamageType.UNKNOWN] else 0.40,
        )


def classify_image(image_path: str) -> dict[str, object]:
    finding = HeuristicDamageClassifier().classify(
        Path(image_path),
        image_id=UUID("00000000-0000-4000-8000-000000000000"),
        caption=None,
    )
    return finding.model_dump(mode="json")
