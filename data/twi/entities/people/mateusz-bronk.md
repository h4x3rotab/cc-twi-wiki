---
title: Mateusz Bronk
description: Engineer at Intel. Author of TWI-WIMSE PR #33 (Provenance reorganisation); helped scope the IETF 123 ask down to "no changes required of WIMSE for provenance".
date: 2026-04-29
tags: [people, intel, provenance, pr-author]
---

**Mateusz Bronk**, Intel (`mateusz.bronk@intel.com`). Provenance editor on the IETF 123 informational draft.

## SIG contributions

- **PR #33** (Provenance reorganisation) on `confidential-computing/twi-wimse`. Mark's review pushed back that PR #33's text risked making WIMSE believe TWI required architectural changes for provenance. Mateusz refined the proposal[^pr33]:
  - Keep new definitions in the I-D for precision.
  - Move the Provenance section (with sub-chapters and metadata types) to the TWI Reference Architecture.
  - Replace it in the IETF 123 draft with a generic "compatible with existing WIMSE arch — no changes required at this time" statement.

  This pruning is what let the IETF 123 draft remain narrowly scoped.
- Articulated the three association mechanisms for provenance — by-ID (e.g. `jti`), inline locator/claim, and hash-based fingerprinting — and argued for keeping all three open in the IETF document[^pr33].
- Pointed out that future provenance work likely warrants a **separate Internet-Draft** (probably not WIMSE-targeted)[^pr33].

[^pr33]: [113881043-general-comment-on-pull-request-33.md](../../threads/113881043-general-comment-on-pull-request-33.md)
## See also

- [Provenance & Supply Chain](../../concepts/provenance.md)
- [TWI Informational Draft (IETF 123)](../drafts/informational-draft-ietf-123.md)
