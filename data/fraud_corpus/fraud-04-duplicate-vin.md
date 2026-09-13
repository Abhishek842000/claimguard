---
case_id: fraud-04-duplicate-vin
citation: Synthetic pattern (entity-graph / VIN cloning; public VIN-fraud bulletins)
---

# Duplicate or cloned VIN

The same 17-character VIN appearing on two open claims with different
named insureds, or on a new claim shortly after a total-loss settlement,
is a classic cloning or double-dipping indicator. Less obvious: the VIN
checksum is valid but the year/make/model decoded from the VIN does not
match the photos or the declarations.

Always run an exact VIN match across the book. A shared VIN is a
high-severity graph edge (relationship: same_vin) and should force human
review regardless of photo quality.
