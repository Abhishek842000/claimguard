---
case_id: fraud-06-mileage-date
citation: Synthetic pattern (Kaggle auto-fraud feature family: months_as_customer, incident_date vs policy bind)
---

# Mileage and date-of-loss inconsistency

Odometer readings that go backward between a prior claim and the current
FNOL, or a daily-mileage implication that exceeds 400 miles/day for a
commuter vehicle, are mechanical red flags. Another variant: the
incident date is before the policy effective date, or a few hours after
a late-night bind.

Flag claims where (current odometer − prior odometer) / elapsed days is
implausible, or where the insured reports the loss date as "last month"
but the photos or shop invoice are dated weeks earlier.
