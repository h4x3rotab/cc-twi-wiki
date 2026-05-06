---
title: Hushmesh
description: Manu Fontaine's company, originator of the "Mesh" architecture and the "Trustworthy Composability" position inside the SIG. Pushes for a fully trustworthy CC end state as the CCC Reference Architecture's North Star.
date: 2026-04-29
tags: [hushmesh, manu-fontaine, mesh, composability, vendor]
---

**Hushmesh** is the company founded and led by [Manu Fontaine](../people/manu-fontaine.md). Inside the SIG, Hushmesh provides the architectural counterweight to the JPMorgan-style "deploy what's possible today" position — pushing the SIG and the CCC Reference Architecture to articulate a fully trustworthy end state first, then plan the migration[^couplings].

[^couplings]: [114091547-thoughts-about-quot-composability-quot-and-strength-of-quot.md](../../../114091547-thoughts-about-quot-composability-quot-and-strength-of-quot.md)
## The Mesh

Hushmesh's architectural blueprint, presented to the SIG on 2025-09-02 as input to the CCC Reference Architecture[^mesh]:

| Property | Description |
|---|---|
| Recursive Attester/Verifier network | Backbone is itself in TEEs; serves as decentralized, tamper-proof, confidential registry. |
| Verified leaf agents | Connect to entities of varying types (workloads, people, orgs, IoT). |
| Composite verifier agents | Solve composition by gathering Evidence from many entity verifiers. |
| Verified Factory & Deployment agents | Connect CI/CD to deployment with verified executables. |
| Local registry per agent | Private, confidential, tamper-proof — relaxes uptime requirements on the central network. |
| StemIDs | Cryptographic identifiers; only possible thanks to CC. |

[^mesh]: [115008881-twi-reference-architecture-lt-gt-mesh-blueprint.md](../../../115008881-twi-reference-architecture-lt-gt-mesh-blueprint.md)
A LinkedIn post on 2025-07-15 announced "the Mesh is becoming the secure-by-design [...]" — referenced in the composability thread as evidence the architecture is being deployed in practice[^couplings].

## Recurring positions

| Position | Source |
|---|---|
| Verifiers and registries must run in TEEs (recursive trust) | [^couplings] |
| Provenance forces "chains of workloads" — a mesh | [^prov] |
| Personal agents need per-entity keychains, not just one identity | [^chatgptlinkedin] |
| CCC Reference Architecture should be a North Star, then relaxed for migration | [^couplings] |
| "Protection in use" should be through encryption | [^couplings] |
| Trustworthy digital twins, "trustworthy composability" for systems-of-systems | [^digtwin] |

[^prov]: [118625119-let-39-s-discuss-provenance.md](../../../118625119-let-39-s-discuss-provenance.md)
[^chatgptlinkedin]: [115104223-workload-identity-for-ai-agents-can-t-come-soon-enough.md](../../../115104223-workload-identity-for-ai-agents-can-t-come-soon-enough.md)
[^digtwin]: [113801931-agenda-for-tuesday-june-24-2025.md](../../../113801931-agenda-for-tuesday-june-24-2025.md)
## See also

- [Manu Fontaine](../people/manu-fontaine.md)
- [Trustworthy Composability](../../concepts/trustworthy-composability.md)
- [Workload Identity vs. Agent Identity](../../concepts/workload-identity-vs-agent-identity.md)
