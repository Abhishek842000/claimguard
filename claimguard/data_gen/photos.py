"""Synthetic damage photos with EXIF tags.

CarDD and similar research sets are not redistributable here. These
placeholders are labeled diagrams plus metadata the fraud agent can read.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import piexif
from PIL import Image, ImageDraw, ImageFont

_PALETTE = {
    "collision": ((42, 58, 78), (190, 80, 70), "REAR IMPACT"),
    "theft": ((28, 28, 32), (220, 200, 80), "THEFT / ENTRY"),
    "vandalism": ((50, 46, 62), (180, 90, 200), "VANDALISM"),
    "hail": ((70, 86, 100), (200, 200, 210), "HAIL DINGS"),
    "mechanical_breakdown": ((60, 60, 60), (120, 120, 120), "POWERTRAIN — NO IMPACT"),
    "fire": ((40, 18, 12), (220, 90, 30), "FIRE CHAR"),
    "sudden_pipe": ((36, 52, 72), (80, 140, 190), "WATER STAIN"),
    "flood": ((24, 40, 64), (40, 90, 140), "FLOOD LINE"),
    "wind": ((48, 64, 56), (160, 180, 140), "WIND / DEBRIS"),
}


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("Helvetica.ttc", size)
    except OSError:
        return ImageFont.load_default()


def write_damage_photo(
    path: Path,
    *,
    peril: str,
    caption: str,
    taken_at: datetime,
    seed_color: int,
) -> None:
    """Write a JPEG with DateTimeOriginal = taken_at."""
    path.parent.mkdir(parents=True, exist_ok=True)
    bg, accent, banner = _PALETTE.get(peril, ((40, 40, 48), (180, 180, 180), peril.upper()))
    image = Image.new("RGB", (960, 640), bg)
    draw = ImageDraw.Draw(image)
    # Stylized "damage" so two photos of the same peril are not byte-identical.
    for i in range(6):
        x0 = 80 + (i * 130 + seed_color * 7) % 700
        y0 = 160 + (i * 47 + seed_color * 3) % 280
        draw.ellipse((x0, y0, x0 + 90, y0 + 55), outline=accent, width=4)
        if i % 2 == 0:
            draw.line((x0, y0 + 20, x0 + 120, y0 + 40), fill=accent, width=3)
    draw.rectangle((0, 0, 960, 72), fill=accent)
    draw.text((24, 18), banner, fill=(255, 255, 255), font=_font(28))
    draw.text((24, 580), caption[:80], fill=(230, 230, 230), font=_font(20))
    image.save(path, "JPEG", quality=88)
    _stamp_exif(path, taken_at)


def _stamp_exif(path: Path, taken_at: datetime) -> None:
    stamp = taken_at.strftime("%Y:%m:%d %H:%M:%S")
    exif_dict = {
        "0th": {
            piexif.ImageIFD.Make: b"ClaimGuardSynth",
            piexif.ImageIFD.Model: b"Phase1-Placeholder",
            piexif.ImageIFD.DateTime: stamp.encode(),
        },
        "Exif": {
            piexif.ExifIFD.DateTimeOriginal: stamp.encode(),
            piexif.ExifIFD.DateTimeDigitized: stamp.encode(),
        },
        "GPS": {},
        "1st": {},
        "thumbnail": None,
    }
    piexif.insert(piexif.dump(exif_dict), str(path))
