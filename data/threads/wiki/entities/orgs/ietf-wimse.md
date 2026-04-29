---
title: IETF WIMSE Working Group
description: The IETF working group for Workload Identity in a Multi-System Environment. Owns WITs, the S2S protocol, the workload-identity-practices and reference-architecture drafts. The original target of TWI's Madrid 2025 informational draft.
date: 2026-04-29
tags: [ietf, wimse, working-group, org, workload-identity]
---

**WIMSE — Workload Identity in a Multi-System Environment** at the IETF. The standardisation home for general workload identity. The TWI SIG's first IETF deliverable was [the Madrid 2025 informational draft](../drafts/informational-draft-ietf-123.md) targeting WIMSE. After Madrid, the SIG's centre of gravity shifted to RATS for credential-issuance work, with WIMSE remaining the venue for *profile* contributions[^recap].

[^recap]: 113926112-twi-vs-wimse-recap.md

## Drafts the SIG tracks

| WIMSE draft | TWI relevance | Source |
|---|---|---|
| `draft-ietf-wimse-arch` (Reference Architecture) | The "agent provisions credentials" model is the core compatibility issue. Bootstrapping section §3.1.1 actively reviewed Apr 2026. | [^recap][^reading] |
| `draft-ietf-wimse-s2s-protocol` | TWI nits on `jti` (should be required), §3.6 (no JWT-bearer-token coexistence), §5.2/5.3 (analyse PoP replay). | [^recap] |
| `draft-ietf-wimse-workload-identity-practices` | Discussion of credential acquisition may not be CC-compatible; credential binding is a MUST for CC. | [^recap] |
| `draft-liu-wimse-wit-attestation` (Carrying RA Evidence in WITs) | Direct overlap with TWI's credential-issuance work. | [^reading] |
| `draft-mw-wimse-transitive-attestation` (sovereign workloads) | Tracked. | [^reading] |
| `draft-ni-wimse-ai-agent-identity` (WIMSE for AI Agents) | Implicates [workload vs. agent identity](../../concepts/workload-identity-vs-agent-identity.md). | [^aiagent][^reading] |
| `draft-rosomakho-tls-wimse-cert-hint` (TLS routing + identity) | Forwarded for awareness; not active TWI work. | [^early] |
| `draft-klspa-wimse-verifiable-geo-fence` | Geo-fencing draft; mentioned alongside compound attestation. | [^geofence] |

[^reading]: 118844386-some-reading-for-next-week-39-s-twi-meeting.md
[^aiagent]: 115889621-fyi-workload-identity-for-ai-agents.md
[^early]: 117367917-fw-wimse-re-problem-statement-early-routing-vs-workload-iden.md
[^geofence]: 113801931-agenda-for-tuesday-june-24-2025.md

## Cross-pollination

- [Joe Scambray / Joe Saloway](../people/dan-middleton.md) — referenced as a "key WIMSE contributor"; planned January 2026 conversations on better TWI/WIMSE integration[^joe1][^joe2].
- WIMSE leadership signed off (informally) on the [Replica Workloads profile](../drafts/twi-profile-replica-workloads.md) being a **WIMSE profile with no architectural changes**[^horiz].
- An interim WIMSE meeting was scheduled around `draft-mw-wimse-transitive-attestation` and related work[^interim1][^interim2].

[^joe1]: 117097434-agenda-for-tuesday-january-6-2026.md
[^joe2]: 117479181-agenda-for-tuesday-january-27-2026.md
[^horiz]: 117140104-trustworthy-workload-identity-for-horizontally-scaling-workl.md
[^interim1]: 114650974-fw-wimse-interims.md
[^interim2]: 114654563-wimse-interim-meetings-scheduled.md

## See also

- [WIMSE & TWI](../../concepts/wimse-and-twi.md)
- [TWI Informational Draft (IETF 123)](../drafts/informational-draft-ietf-123.md)
