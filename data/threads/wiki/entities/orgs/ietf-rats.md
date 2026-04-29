---
title: IETF RATS Working Group
description: The IETF working group that owns the Remote ATtestation procedureS architecture (RFC 9334). The TWI SIG's primary IETF target after Madrid 2025 — credential issuance from attestation results lives here.
date: 2026-04-29
tags: [ietf, rats, working-group, org, rfc-9334]
---

**RATS — Remote ATtestation procedureS Working Group** at the IETF. Owns the RATS architecture (RFC 9334) and a growing family of related drafts. After IETF 123 in Madrid, the TWI SIG explicitly redirected its focus to RATS, on Mark Novak's recap[^recap]:

> "All matters of credentials issuance should be dealt with inside the RATS working group, and after Madrid we should focus most of our attention on that (plus the reference architecture, of course)."

[^recap]: 113926112-twi-vs-wimse-recap.md

## SIG submissions targeting RATS

| Draft | Venue | Submitted |
|---|---|---|
| [TWI eXchange Draft](../drafts/twi-exchange-draft.md) `draft-novak-twi-attestation` | IETF 124 (Montreal, Nov 2025) | 2025-10-19/20 by Yogesh Deshpande |
| [Vienna submission](../drafts/vienna-submission.md) (RUP-extended RATS) | IETF Vienna (Jul 2026) | In drafting as of 2026-04-29 |

Mark Novak also forwarded the **"Anticipating Reference Values"** question to the RATS list on 2026-04-15[^antrv] and re-subscribed to the list specifically for that.

[^antrv]: 118845083-fw-anticipating-reference-values.md

## RATS drafts the SIG actively tracks

| Draft | Why TWI cares |
|---|---|
| `draft-ietf-rats-msg-wrap` (CMW — Conceptual Messages Wrapper) | Common envelope (CBOR/JWT/CWT/X.509) for Evidence/AR/Endorsements/Reference Values — potential building block[^cmw]. |
| `draft-ietf-rats-ar4si` (Attestation Results for Secure Interactions) | Different / richer model for conveying attester identity than TWI's. WIMSE compatibility unclear[^ar4si]. |
| `draft-mihalcea-seat-use-cases` (SEAT use cases) | Use cases for attestation-bound credentials — TWI input: include manageability/credential-stability[^seat]. |
| `draft-liu-wimse-wit-attestation` (Carrying RA Evidence in WITs) | WIMSE/RATS interaction on putting attestation directly into WITs[^reading]. |

[^cmw]: 114663896-conceptual-message-wrapper-cmw-ietf-draft-from-rats.md
[^ar4si]: 114723280-ar4si-draft-from-rats.md
[^seat]: 116109344-mail-regarding-draft-mihalcea-seat-use-cases-one-key-quot-in.md
[^reading]: 118844386-some-reading-for-next-week-39-s-twi-meeting.md

## Personnel overlap with TWI

[Henk Birkholz](../people/henk-birkholz.md) is active in both the TWI SIG and RATS — he submitted the IETF 123 informational draft and is co-author on `draft-ietf-rats-msg-wrap` and `draft-ietf-rats-ar4si`. [Yogesh Deshpande](../people/yogesh-deshpande.md) (Arm) is active in both as well, having submitted the IETF 124 TWI eXchange draft.

## See also

- [RATS Architecture](../../concepts/rats-architecture.md)
- [RATS-Unaware Relying Parties](../../concepts/rats-unaware-relying-parties.md)
- [Henk Birkholz](../people/henk-birkholz.md), [Yogesh Deshpande](../people/yogesh-deshpande.md)
