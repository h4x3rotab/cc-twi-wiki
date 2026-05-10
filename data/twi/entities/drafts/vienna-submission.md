---
title: Vienna Submission (IETF Vienna, Jul 2026)
description: The SIG's IETF Vienna submission, in early-draft form as of 2026-04-24. Extends the RATS architecture with RATS-Unaware Relying Parties (RUPs) so Confidential Computing can interoperate with classical IdPs and Relying Parties.
date: 2026-04-29
tags: [ietf, rats, vienna, draft, rup, 2026, in-progress]
---

The SIG's third IETF deliverable, **in active drafting as of late April 2026**. Targets the IETF meeting in **Vienna (July 2026)**. The early draft was circulated by [Mark Novak](../people/mark-novak.md) on 2026-04-24[^early].

[^early]: [118990275-early-draft-of-the-vienna-submission.md](../../threads/118990275-early-draft-of-the-vienna-submission.md)
## Quick facts

| | |
|---|---|
| **Status** | Early draft circulated 2026-04-24; pending review at TWI meeting on 2026-04-29 / 30 |
| **Repository** | `github.com/confidential-computing/twi-rats` (reused; previous draft moved to `archive/2025/`)[^repo] |
| **Author so far** | Mark Novak |
| **Likely WG target** | RATS |
| **Possible separate repo** | `twi-ietf` requested 2026-04-22 for "future drafts" but Vienna re-used `twi-rats`[^newrepo] |

[^repo]: [118988634-repository-for-vienna-ietf-submission.md](../../threads/118988634-repository-for-vienna-ietf-submission.md)
[^newrepo]: [118959565-new-github-repo-request-for-twi-sig.md](../../threads/118959565-new-github-repo-request-for-twi-sig.md)
## Abstract (verbatim from the early draft)

> "There is a large class of 'RATS-Unaware' Relying Parties (RUPs) that Attesters nevertheless need to interoperate with. RUPs cannot process Attestation Results or execute Appraisal Policy for Attestation Results. This specification extends the RATS Architecture to interoperate with RUPs."[^early]

## What's in the early draft

| Section | State |
|---|---|
| Abstract | Done |
| Introduction (deployability argument) | Done |
| Conventions and Terminology | Empty |
| **RUP-Extended RATS Architecture** | One paragraph + an architecture diagram (ASCII) |
| Security Considerations | `<fill in>` |
| IANA Considerations | `<fill in>` |

The whole concept page on [RATS-Unaware Relying Parties](../../concepts/rats-unaware-relying-parties.md) is essentially a structured walk-through of the early draft's first sections.

## The Markus Rudy review (2026-04-24)

Markus Rudy (Edgeless Systems) raised two substantive critiques on the day the draft was shared[^early]:

1. **The RATS architecture doesn't actually need to change.** Nothing in RATS prescribes what a RP does with Attestation Results — anyone is free to implement Mark's RP today. Mark's reply: in practice, vendors don't, because there's no architectural guidance saying it's normative; the goal is to unblock implementations.
2. **RUPs don't need to be in the model at all** — just make the IdP CC-aware and let it issue credentials in the format the existing RUPs already understand. Mark's reply: those CC-aware IdPs *don't exist yet* — there is currently no way to integrate SPIFFE with CC. The draft is meant to initiate the conversation that produces them.

This is the live design tension the SIG is working through ahead of Vienna.

## Strategic alternative under consideration

Mark floated narrowing the Vienna submission to *only* the **"Anticipating Reference Values"** aspect of the Replica Profile (since "the rest does not change anything about RATS")[^antrv][^attsig]. As of 2026-04-22:

> "I am still struggling with what our Vienna contribution to the IETF is going to be. I can think of two related directions:
>
> 1. More concrete: 'Achieving Relying Party stability'…
> 2. Less concrete: A discussion of a relationship between remote attestation and attester credential issuance."[^attsig]

[^antrv]: [118845083-fw-anticipating-reference-values.md](../../threads/118845083-fw-anticipating-reference-values.md)
[^attsig]: [118956224-fw-ccc-attestation-documents-from-today-39-s-presentation.md](../../threads/118956224-fw-ccc-attestation-documents-from-today-39-s-presentation.md)
## See also

- [RATS-Unaware Relying Parties](../../concepts/rats-unaware-relying-parties.md) — the conceptual page
- [TWI Profile for Replica Workloads](twi-profile-replica-workloads.md) — parent material
- [Mark Novak](../people/mark-novak.md), [Markus Rudy](../people/markus-rudy.md)
