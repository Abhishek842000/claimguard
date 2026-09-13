---
case_id: fraud-15-lapse-backdate
citation: Synthetic pattern (Kaggle auto-fraud feature family: policy bind vs incident_hour / incident_date)
---

# Policy-lapse then backdated loss

A loss dated the same day as a reinstatement, or a few hours after a
late-night bind, is a well-known moral-hazard pattern. The insured
already had the accident and buys coverage before FNOL.

Compare incident_date (and time if present) to the policy effective
timestamp. A loss before bind is not covered. A loss within 24 hours of
bind is not automatically fraudulent but is a medium rule hit that
should block auto-resolve.
