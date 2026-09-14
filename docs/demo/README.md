# Demo capture

The walkthrough file is [`claimguard-demo.mp4`](claimguard-demo.mp4) (1280×720,
~29s). It submits sample `PA-2026-000039 · hail` and scrolls the verdict plus
agent timeline (intake → fraud weather-mismatch → policy → vision dent →
adjudicator → human review).

The live path is still http://localhost:3001 (see the root README).

Sample-folder JPEGs (`hail-1.jpg`, etc.) are **labeled diagrams**, not camera
photos. CarDD and similar research sets are not redistributable here. For a
video that looks like a real FNOL, do **not** paste a real customer's claim.
Use photos you took or royalty-free stock, plus **synthetic** names and
amounts. The upload form on the home page is the path that shows those files
on camera.

## Film with realistic photos (recommended)

1. Get 2–3 damage photos you are allowed to show:
   - your own car / hood / bumper, or
   - Unsplash / Pexels search: `car hail dent`, `bumper collision` (check the
     license; crop plates and faces).
2. Rename them so the vision heuristic can label them (it reads **filename**,
   not pixels): `hail-hood.jpg`, `hail-roof.jpg`, `dent-fender.jpg`.
3. Start API, worker, and `apps/frontend` (`npm run dev` on port 3001).
4. On http://localhost:3001 use **Upload docs / images**, not "Run sample
   claim". Attach the photos. Optionally also attach
   `data/synthetic_claims/09d919dc-2168-544f-8ec0-4a0f018c8ef6/documents/fnol-claim-form.pdf`
   so a form appears in the file picker.
5. Paste notes that keep the interesting Phoenix / no-NOAA-storm path:

   ```
   FNOL for Jordan Hale, PA-2026-000039. Golf-ball hail in Phoenix, AZ on
   2026-06-12 dented the hood and roof. Neighbor did not report a storm.
   Claimed amount $6225. Third party involved; police report not attached.
   ```

   Phoenix on 2026-06-12 is **not** in `data/weather/noaa_reference.json`, so
   `FR-WEATHER-MISMATCH` still fires and the claim should land in
   `needs_review`. Do not put a real SSN, phone, or street address in the notes.
6. QuickTime → File → New Screen Recording. Show the file picker (real
   photos), submit, wait for the verdict, scroll the timeline.
7. Save as `docs/demo/claimguard-demo.mp4`.

The claim-detail page does not render the JPEG pixels — the viewer sees them
when you pick files. The pipeline still reads the uploaded bytes (EXIF dates
feed `FR-PHOTO-EXIF` if the photo is 7+ days off the loss date).

## Optional: swap photos into the sample folder

If you want **Run sample claim** (`PA-2026-000039 · hail`) to use camera
photos on disk, overwrite the JPEGs in place and keep the filenames:

`data/synthetic_claims/09d919dc-2168-544f-8ec0-4a0f018c8ef6/images/hail-1.jpg`

Stamp `DateTimeOriginal` to the loss date if you do **not** want an EXIF
fraud hit; use a date 7+ days away if you do.

```bash
uv run python - <<'PY'
from datetime import datetime
from pathlib import Path
import piexif

path = Path("data/synthetic_claims/09d919dc-2168-544f-8ec0-4a0f018c8ef6/images/hail-1.jpg")
stamp = datetime(2026, 6, 12, 15, 0, 0).strftime("%Y:%m:%d %H:%M:%S")
exif = piexif.load(str(path))
exif.setdefault("0th", {})[piexif.ImageIFD.DateTime] = stamp.encode()
exif.setdefault("Exif", {})[piexif.ExifIFD.DateTimeOriginal] = stamp.encode()
piexif.insert(piexif.dump(exif), str(path))
PY
```

Do not commit those replacements if the photos are not yours to redistribute.

## Publish path (sample only, diagrams on disk)

1. Start API, worker, and `apps/frontend`.
2. macOS QuickTime Player → File → New Screen Recording.
3. Submit `PA-2026-000039 · hail`, wait for the verdict, scroll the timeline.
4. Save as `docs/demo/claimguard-demo.mp4` and keep the README link pointed here.
