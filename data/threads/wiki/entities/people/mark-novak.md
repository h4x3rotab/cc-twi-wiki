---
title: Mark Novak
description: Author of most TWI SIG drafts, JPMorgan Chase. Drives the deployability-first position; lead author of the IETF 123, IETF 124, Replica Workloads, and Vienna drafts.
date: 2026-04-29
tags: [people, jpmorgan, author, chair-de-facto]
---

**Mark Novak**, JPMorgan Chase. The most prolific contributor in the archive — author or lead-editor of every TWI IETF submission to date, and de-facto driver of the SIG's weekly meetings.

## Affiliations

- **JPMorgan Chase** — primary affiliation in email signatures (`mark.novak@...`, `Mark.Novak@jpmchase.com`). Confidentiality footer present on most JPMC mail[^jpmc]. Presented the CCC OC3 deck (Mar 2026)[^oc3].

[^jpmc]: 116242682-fosdem-39-26-confidential-computing-devroom-cfp.md
[^oc3]: 118076670-ccc-oc3-deck-pptx-mark-f-novak-jpmchase-com-kindly-rec.md

## Drafts authored / co-authored

- [TWI Informational Draft (IETF 123)](../drafts/informational-draft-ietf-123.md) — primary editor of PR #34 (Security Considerations), #39, others.
- [TWI eXchange Draft (IETF 124)](../drafts/twi-exchange-draft.md) — `draft-novak-twi-attestation`.
- [TWI Profile for Replica Workloads](../drafts/twi-profile-replica-workloads.md) — sole author per the v1.0 share-out.
- [Vienna submission](../drafts/vienna-submission.md) — sole author of the early draft.

## Recurring positions

| Position | Why |
|---|---|
| **Deployability over architectural purity** | Customers must be able to deploy what TWI specifies; over-constraining ("your CSP can't be trusted for geolocation") leaves enterprises unable to follow[^couplings]. |
| **Risk-tolerated composability** | Trust your CSP for some claims if your business risk allows it; TWI must not foreclose that choice[^couplings]. |
| **Credential issuance is the gap between WIMSE and RATS** | WIMSE assumes credentials are obtained somehow; RATS stops at Attestation Results. TWI fills the gap[^crack]. |
| **Tight scope on every IETF ask** | "I cannot stress highly enough how important it is to keep the focus where the focus belongs."[^pr33] |
| **CC integration with existing IdPs needs a seat at the table** | Hence the [RUP](../../concepts/rats-unaware-relying-parties.md) extension. |

[^couplings]: 114091547-thoughts-about-quot-composability-quot-and-strength-of-quot.md
[^crack]: 118956224-fw-ccc-attestation-documents-from-today-39-s-presentation.md
[^pr33]: 113881043-general-comment-on-pull-request-33.md

## Notable presentations

- **2025-10-02** — Confidential Containers (Sam Ortiz)[^cocopres]
- **2025-11-04** — IETF SEAT review[^seat]
- **2025-11-07** — IETF 124 RATS WG presentation[^pres]
- **2026-04-16** — CCC TAC, Replica Workloads v1.0[^tac]
- **2026-04-21** — CCC Attestation SIG[^attsig]

[^cocopres]: 115554186-twi-presentation-this-morning.md
[^seat]: 116109344-mail-regarding-draft-mihalcea-seat-use-cases-one-key-quot-in.md
[^pres]: 116048814-ietf-124-presentation-final-draft.md
[^tac]: 118843190-please-review-tomorrow-39-s-draft-presentation.md
[^attsig]: 118956224-fw-ccc-attestation-documents-from-today-39-s-presentation.md

## See also

- [Manu Fontaine](manu-fontaine.md) — frequent productive disagreement
- [Markus Rudy](markus-rudy.md) — Vienna-draft critic
- [Trustworthy Workload Identity](../../concepts/trustworthy-workload-identity.md)
