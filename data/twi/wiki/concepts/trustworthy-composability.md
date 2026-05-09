---
title: Trustworthy Composability
description: Hushmesh's thesis that the trust strength of a composite computing service equals its weakest workload — so verifiers, registries, and the whole chain must run in TEEs.
date: 2026-04-29
tags: [composability, hushmesh, mesh, twi, philosophy, recursive-architecture]
---

**Trustworthy Composability** is the position that, since end users consume *composite* services made of many workloads, the composition mechanisms themselves must preserve the security strength of every component — otherwise a single non-CC "weak link" undoes the whole chain[^tc]. It was articulated for the SIG by [Manu Fontaine](../entities/people/manu-fontaine.md) (Hushmesh) starting in May 2025.

[^tc]: [113326321-trustworthy-composability.md](../../113326321-trustworthy-composability.md)
## The core argument

1. Confidential Computing offers orders-of-magnitude stronger security than non-CC alternatives (smallest attack surface + chip-level verifiability).
2. End users (consumers, patients, citizens, warfighters) consume *composite* services — the trustworthiness of an experience is the trustworthiness of the whole composition of workloads behind it.
3. A single non-CC component can damage the authenticity / confidentiality / privacy of that experience.
4. Therefore the eventual end state — a "Trustworthy World" — is one where **all** workloads are trustworthy.
5. Therefore the **mechanism** that composes trustworthy workloads must itself preserve their security strength. Composing trusted parts via an untrusted glue is the same as having an untrusted whole.

This implies that WIMSE — which today does not require trustworthy components — must build in trustworthy composability *now*, so the standard does not later need to be retrofitted[^tc].

## What it implies in practice

| Component | Composability claim | Source |
|---|---|---|
| Verifiers | Must run in TEEs. A compromised SPIRE server is a catastrophic failure; the same applies to attestation verifiers. | [^couplings] |
| Reference Value / endorsement registries | Must run in TEEs (they are workloads too). | [^couplings] |
| Provenance | Forces "chains of workloads" thinking; the whole verification chain ends up in the Attester's TCB → recursive system architecture (a "mesh"). | [^prov] |
| Attestation evidence | Compositional: a "composite verifier agent" gathers evidence from many "entity verifier agents". | [^mesh] |

[^couplings]: [114091547-thoughts-about-quot-composability-quot-and-strength-of-quot.md](../../114091547-thoughts-about-quot-composability-quot-and-strength-of-quot.md)
[^prov]: [118625119-let-39-s-discuss-provenance.md](../../118625119-let-39-s-discuss-provenance.md)
[^mesh]: [115008881-twi-reference-architecture-lt-gt-mesh-blueprint.md](../../115008881-twi-reference-architecture-lt-gt-mesh-blueprint.md)
## The Mesh as a worked example

Hushmesh's "Mesh" is offered as a blueprint for what a recursive-trust architecture looks like[^mesh]:

```mermaid
flowchart TD
    F[Factory Agent<br/>(verified, in TEE)]
    D[Deployment Agent<br/>(verified, in TEE)]
    CV[Composite Verifier Agent]
    EV1[Entity Verifier Agent<br/>workload]
    EV2[Entity Verifier Agent<br/>org]
    EV3[Entity Verifier Agent<br/>person]
    Reg[Decentralized Registry<br/>per agent, local + private]

    F --> D
    D --> CV
    CV --> EV1
    CV --> EV2
    CV --> EV3
    EV1 --> Reg
    EV2 --> Reg
    EV3 --> Reg
```

Every node is verified by the layer above it; identifiers are cryptographic ("StemIDs"); the same backbone serves as identity, key-management, and attestation infrastructure.

## The dispute: full-stack vs. risk-tolerated

Mark Novak's response[^couplings] is a deliberate counterweight: customers must be able to **deploy** what TWI specifies, and over-constraining (e.g., "your CSP's geolocation claims aren't acceptable") will leave most enterprises unable to follow. Trust decisions belong to the customer:

> "If I trust my CSP for geolocation claim, then that's a risk I'm willing to accept — so long as it does not affect the claims about the code in the TEE that I'm attesting."[^couplings]

Manu's pushback frames the CCC Reference Architecture as a **North Star** that articulates the fully-trustworthy end state, then relaxes constraints to provide a guided migration path rather than starting from "what is convenient today"[^couplings].

This tension surfaces in nearly every architectural decision the SIG makes: it is the through-line behind the [Replica/Twin Workloads](replica-and-twin-workloads.md) profile (a deliberately narrow, deployable scope) and the [RUP](rats-unaware-relying-parties.md) extension (deliberate accommodation of legacy RPs).

## See also

- [Provenance & Supply Chain](provenance.md) — recursive-trust thinking applied to attestation chains
- [Hushmesh](../entities/orgs/hushmesh.md)
- [Mark Novak](../entities/people/mark-novak.md), [Manu Fontaine](../entities/people/manu-fontaine.md)
