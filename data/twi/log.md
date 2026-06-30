---
title: Wiki Log
description: Append-only record of ingests, queries, and lint passes against this wiki.
date: 2026-04-29
tags: [log, meta]
---

Chronological record of ingests, queries, and maintenance passes.

## [2026-06-30] ingest | Incremental update (May–Jun 2026)

- Scraped 11 new topics (IDs 119157220–120041110, range 2026-05-05 → 2026-06-30). Bot detection on topic-listing pages bypassed by fetching individual topic pages directly (groups.io added Spur MCL bot detection to listing pages since April).
- Noise filtered (9 skipped): 7× agenda-for-tuesday, 1× respond-if-attending, 1× meeting-cancelled/no-meeting.
- Signal incorporated (2 threads):
  - `concepts/rats-unaware-relying-parties.md` — Formal Impossibility Papers (May 13) added
  - `entities/drafts/vienna-submission.md` — Status updated to final sprint; 3-direction convergence, Credential Broker role, June 25 deadline
  - `timeline.md` — May–June 2026 section added
  - `overview.md` — corpus updated to 130 threads / ~183 messages through 2026-06-30

## [2026-04-29] ingest | Full TWI SIG mailing-list archive (119 threads, 169 messages)

- Ingested every thread file under `/` (119 files, 169 messages, range 2025-03-31 → 2026-04-28).
- Created [overview.md](overview.md) as the hub page (5 key findings, source inventory, structural diagram).
- Created concept pages:
  - [Trustworthy Workload Identity](concepts/trustworthy-workload-identity.md)
  - [Trustworthy Composability](concepts/trustworthy-composability.md)
  - [Workload Identity vs. Agent Identity](concepts/workload-identity-vs-agent-identity.md)
  - [Replica & Twin Workloads](concepts/replica-and-twin-workloads.md)
  - [RATS Architecture](concepts/rats-architecture.md)
  - [RATS-Unaware Relying Parties](concepts/rats-unaware-relying-parties.md)
  - [WIMSE & TWI](concepts/wimse-and-twi.md)
  - [Provenance & Supply Chain](concepts/provenance.md)
- Created entity pages:
  - **Drafts:** [Informational Draft (IETF 123)](entities/drafts/informational-draft-ietf-123.md), [TWI eXchange Draft (IETF 124)](entities/drafts/twi-exchange-draft.md), [TWI Profile for Replica Workloads](entities/drafts/twi-profile-replica-workloads.md), [Vienna submission](entities/drafts/vienna-submission.md)
  - **Repos:** [GitHub repos](entities/repos/github-repos.md)
  - **Orgs:** [CCC](entities/orgs/ccc.md), [IETF RATS](entities/orgs/ietf-rats.md), [IETF WIMSE](entities/orgs/ietf-wimse.md), [Hushmesh](entities/orgs/hushmesh.md)
  - **People:** [Mark Novak](entities/people/mark-novak.md), [Manu Fontaine](entities/people/manu-fontaine.md), [Markus Rudy](entities/people/markus-rudy.md), [Henk Birkholz](entities/people/henk-birkholz.md), [Yogesh Deshpande](entities/people/yogesh-deshpande.md), [Mateusz Bronk](entities/people/mateusz-bronk.md), [Dan Middleton](entities/people/dan-middleton.md), [Hang Yin](entities/people/hang-yin.md)
- Created [timeline.md](timeline.md) — 13-month chronological narrative.
- Key takeaway: TWI's strategic core is delivering a deployable credential-issuance story for replica workloads, while resolving the long-running tension between full-stack trust (Hushmesh) and risk-tolerated deployability (JPMC).
