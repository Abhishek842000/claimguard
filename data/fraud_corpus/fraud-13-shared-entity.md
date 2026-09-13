---
case_id: fraud-13-shared-entity
citation: Synthetic pattern (entity resolution; Kaggle-like policyholder linkage)
---

# Shared address or phone across unrelated insureds

Unrelated named insureds who share a mobile number, email, or unit
address — especially when the loss dates are close — often belong to a
paper-insured ring. The individual files look ordinary in isolation.

Redact the raw phone in logs, but persist a hash and run exact-match
edges (same_phone, same_address). Two or more matches is medium severity;
three or more with overlapping shops or VINs is high.
