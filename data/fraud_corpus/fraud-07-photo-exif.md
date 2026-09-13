---
case_id: fraud-07-photo-exif
citation: Synthetic pattern (image forensics / EXIF DateTimeOriginal vs FNOL date)
---

# Photo EXIF or stock-photo mismatch

Damage photos whose EXIF DateTimeOriginal is weeks away from the reported
incident date, or whose GPS tag is in another state, are inconsistent
with a same-day FNOL. Recycled images also appear: identical crop and
compression across two claim files.

A mismatch of more than 48 hours between EXIF and incident_date, without
an explanation (phone clock, shop photo taken at estimate), is a
medium-severity rule hit. Missing EXIF is common on messaging-app
recompressions and is not, by itself, fraud.
