---
case_id: fraud-11-shop-ring
citation: Synthetic pattern (Kaggle auto-fraud feature family: auto_make/model clustering, repair shop)
---

# Repair-shop kickback ring

A single body shop appearing on many unrelated claims with the same
estimator name, identical labor hours, and recycled photo backgrounds is
a ring indicator. The insured may be steered to the shop at the scene.

Graph-match on shop name and phone. When three or more claims share a
shop and at least one other entity (VIN prefix, address block, or
claimant phone), route all open claims from that cluster to SIU.
