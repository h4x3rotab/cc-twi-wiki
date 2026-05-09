---
title: WIMSE & TWI — Compatibility and the One Architectural Ask
description: TWI is mostly compatible with WIMSE as drafted. The single hard requirement is to invert the trust relationship so the workload performs attestation rather than an external "agent".
date: 2026-04-29
tags: [wimse, twi, ietf, compatibility, comparison]
---

The IETF **WIMSE** WG (Workload Identity in a Multi-System Environment) is the standardisation home for workload identity — Workload Identity Tokens (WITs), the S2S protocol, the workload-identity-practices draft, and the WIMSE Reference Architecture. TWI's relationship to WIMSE is summarised in [Mark Novak](../entities/people/mark-novak.md)'s July 2025 recap[^recap]:

> "TWI is mostly compatible with WIMSE as is, but care must be taken to ensure that it remains so in everything they do. […] All matters of credentials issuance should be dealt with inside the RATS working group, and after Madrid we should focus most of our attention on that."

[^recap]: [113926112-twi-vs-wimse-recap.md](../../113926112-twi-vs-wimse-recap.md)
## The compatibility audit

A point-by-point read of WIMSE drafts, with TWI annotations[^recap]:

| WIMSE source | TWI reaction |
|---|---|
| **WIMSE Arch §3.1.3** — *"An agent provisions the identity credentials to the workload."* | **Incompatible with CC.** Under CC the workload acquires its own credentials; there is no "agent" external to the workload. |
| **WIMSE Arch §3.1.3** — *"the workload identity token binds a JWT to a cryptographic key."* | Good. |
| **WIMSE Arch §3.2.1** — workloads obtain credentials from a Credentials Service. *"The credentials are often X.509 based or JWT based."* | Good (no "agent" mentioned). Should restate that the WIT is a JWT with a JWS. |
| **WIMSE Arch §3.2.1** — *"Workloads typically retrieve their workload identity credentials early in their lifecycle…"* | "Retrieve" sounds like someone else has created them. **"Obtain" is a better term.** |
| **WIMSE Arch §3.2.1** — *"workloads can use a JWT based authentication mechanism to authenticate"* | Why not say WIT-based, since WIT is a JWT? |
| **WIMSE Arch Figure 4** — agent performs attestation, agent serves multiple workloads. | **Does not work for CC.** The workload performs attestation, one agent cannot serve multiple workloads. Add Figure 4.1 for the CC variant; placing the agent inside the workload may fix the problem. |
| **WIMSE S2S §3** — `jti` claim is OPTIONAL | Should be **REQUIRED** or at least **SHOULD**. |
| **WIMSE S2S §3.6** — coexistence with JWT bearer tokens | Can't have that — except for ingress authentication of (presumably non-confidential) workloads. |
| **WIMSE S2S §5.2/5.3** — PoP replay mitigation | TODO: analyse for sufficiency. |
| **Workload Identity Practices Draft 1** — discussion of credential acquisition | May not be CC-compatible; does not include remote attestation; credential binding is **MUST** for CC. |

## The one architectural ask

Across all the line-by-line nits, there is one thing the SIG insists must change in the WIMSE architecture itself[^pr33]:

> "The one thing we MUST get out of WIMSE is agreement at IETF 123 to invert the trust relationship between the workload and its hosting environment, where the workload does not trust the hosting environment to attest itself and instead must rely on RATS-style attestation."

[^pr33]: [113881043-general-comment-on-pull-request-33.md](../../113881043-general-comment-on-pull-request-33.md)
A "good but secondary" goal is **compound attestation** combining workload + platform claims (already being explored in the geofencing draft).

## Strategic discipline: don't ask for too much

The PR-33 discussion shows the SIG actively pruning its asks of WIMSE[^pr33]:

- **Provenance** is, at most, a credential-unique-ID extension — and the unique ID rides on existing `jti`-style claims. WIMSE must not be asked to redesign for provenance.
- All deeper provenance work (Workload Provenance, Workload Credential Provenance metadata) belongs in the **TWI Reference Architecture**, not in the WIMSE-facing I-D.
- A separate informational draft (potentially IETF 124) is the proper home for relying-party-side provenance handling.

[Mateusz Bronk](../entities/people/mateusz-bronk.md) (Intel) refined PR-33 along exactly these lines.

## Where TWI work fits in WIMSE today

| WIMSE artifact | TWI's contribution |
|---|---|
| [Informational Draft (IETF 123)](../entities/drafts/informational-draft-ietf-123.md) | Submitted Jul 2025; the "TWI for WIMSE" delta. |
| Bootstrapping (Arch §3.1.1) | Tracked actively as of Apr 2026[^reading]. |
| `draft-liu-wimse-wit-attestation` — Carrying RA Evidence in WITs | Tracked. |
| `draft-mw-wimse-transitive-attestation` | Tracked. |
| `draft-rosomakho-tls-wimse-cert-hint` (early routing vs identity in mTLS) | Discussion forwarded for awareness[^early]. |
| TWI Profile for WIMSE (later renamed Replica Workloads profile) | Targeted as a **WIMSE profile**, no architectural changes — "a big win for interoperability."[^horiz] |

[^reading]: [118844386-some-reading-for-next-week-39-s-twi-meeting.md](../../118844386-some-reading-for-next-week-39-s-twi-meeting.md)
[^early]: [117367917-fw-wimse-re-problem-statement-early-routing-vs-workload-iden.md](../../117367917-fw-wimse-re-problem-statement-early-routing-vs-workload-iden.md)
[^horiz]: [117140104-trustworthy-workload-identity-for-horizontally-scaling-workl.md](../../117140104-trustworthy-workload-identity-for-horizontally-scaling-workl.md)
## See also

- [IETF WIMSE WG](../entities/orgs/ietf-wimse.md)
- [Trustworthy Workload Identity](trustworthy-workload-identity.md)
- [TWI Informational Draft (IETF 123)](../entities/drafts/informational-draft-ietf-123.md)
