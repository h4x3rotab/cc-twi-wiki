---
title: TWI eXchange Draft (IETF 124, Montreal)
description: draft-novak-twi-attestation — the SIG's second IETF deliverable, focused on credential issuance based on attestation results. Submitted Oct 2025 by Yogesh Deshpande.
date: 2026-04-29
tags: [ietf, rats, draft, ietf-124, montreal, twix, 2025]
---

The SIG's second IETF deliverable: a RATS-facing draft on the **integration of credentials into Verifier attestation results**. Targeted at IETF 124 (Montreal, Nov 2025), submitted **2025-10-19/20**.

## Quick facts

| | |
|---|---|
| **Filename** | `draft-novak-twi-attestation.md` |
| **Repository** | `github.com/confidential-computing/twi-rats` |
| **Working group target** | RATS |
| **Internal nickname** | "TWIX" / TWI eXchange draft[^twix] |
| **Submitter** | [Yogesh Deshpande](../people/yogesh-deshpande.md) (Arm), volunteered Oct 17[^finishing] |
| **Original Google Doc draft** | Started early Oct 2025 by Mark Novak[^twix] |

[^twix]: [115537750-help-needed-editing-the-twix-draft.md](../../threads/115537750-help-needed-editing-the-twix-draft.md)
[^finishing]: [115809076-putting-finishing-touches-on-our-ietf-submission.md](../../threads/115809076-putting-finishing-touches-on-our-ietf-submission.md)
## What it covers

The draft proposes message exchanges that lead from Attestation Results to issued credentials — specifically how an X.509 certificate or bound JWT can be issued to a Confidential workload via the attestation flow[^twix]. The first review-ready draft was announced by Mark Novak on 2025-10-10[^firstdraft]:

> "Please take a look at github.com/confidential-computing/twi-rats/blob/main/draft-novak-twi-attestation.md. Note that it references several sequence diagrams which have been placed in separate `.sd` files (CAM_A.sd, etc.). You can render those in Mermaid (mermaidchart.com) and we need someone to volunteer to automate converting these to ASCII art for the final version of the draft."

[^firstdraft]: [115689796-first-draft-of-twi-exchange-draft-ready-for-review.md](../../threads/115689796-first-draft-of-twi-exchange-draft-ready-for-review.md)
## Sequence diagrams (CAM_A, etc.)

The draft's flows were authored as Mermaid sequence diagrams in `.sd` files in the repo. Yogesh Deshpande did the bulk of diagram authoring; Mark cleaned them for consistency before the submission deadline[^finishing].

A nomenclature decision was deliberately deferred: the diagrams used "Credential Attributes" while the prose used "Claims" — agreed to standardise post-v1[^finishing].

## Outstanding TODOs at submission time

From Mark's "putting finishing touches" thread on 2025-10-17[^finishing]:

1. Strip placeholder `venue:` block.
2. Confirm submission process for compiled text.
3. Diagram review for errors / inconsistencies / omissions.
4. Security considerations — at least *note* known issues (e.g., freshness/nonce in the flow where the Workload requests a Credential directly from the Credential Authority and the CA invokes the Verifier).
5. Convert Variant 1 / Variant 2 to ASCII.

## After submission

Mark presented the draft at the RATS WG meeting at IETF 124 on 2025-11-07[^pres]. He then took the same material to:

- Confidential Containers (Sam Ortiz) on 2025-10-02[^cocopres]
- IETF SEAT WG (review of `draft-mihalcea-seat-use-cases`) on 2025-11-04[^seat]

[^pres]: [116048814-ietf-124-presentation-final-draft.md](../../threads/116048814-ietf-124-presentation-final-draft.md)
[^cocopres]: [115554186-twi-presentation-this-morning.md](../../threads/115554186-twi-presentation-this-morning.md)
[^seat]: [116109344-mail-regarding-draft-mihalcea-seat-use-cases-one-key-quot-in.md](../../threads/116109344-mail-regarding-draft-mihalcea-seat-use-cases-one-key-quot-in.md)
## Status as of Apr 2026

The TWI eXchange draft did not move forward as a working-group document; this is why the SIG asked for a fresh `twi-ietf` GitHub repo for the Vienna effort rather than reusing `twi-rats`[^newrepo]. The *content* — credential issuance based on attestation results — survives in the [TWI Profile for Replica Workloads](twi-profile-replica-workloads.md) and the [Vienna submission](vienna-submission.md), with the latter narrowing scope deliberately to the parts that require RATS architecture changes.

[^newrepo]: [118959565-new-github-repo-request-for-twi-sig.md](../../threads/118959565-new-github-repo-request-for-twi-sig.md)
## See also

- [TWI Informational Draft (IETF 123)](informational-draft-ietf-123.md) — the predecessor
- [TWI Profile for Replica Workloads](twi-profile-replica-workloads.md) — the successor
- [Vienna submission](vienna-submission.md)
- [GitHub repos](../repos/github-repos.md)
