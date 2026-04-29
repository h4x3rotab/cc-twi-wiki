---
title: Workload Identity vs. Agent Identity
description: A workload is the running code; an agent is something that acts on behalf of an entity (person, org, thing). Confidential Computing lets one workload act exclusively as an agent for an entity by holding a per-entity keychain.
date: 2026-04-29
tags: [workload-identity, agent-identity, hushmesh, terminology, ai-agents]
---

A **workload** is what's running — code in a TEE, with its own attestation evidence. An **agent** is a *role* a workload can play: it acts on behalf of some entity (a user, an organisation, a physical thing, another agent) and may hold credentials on that entity's behalf. Confidential Computing matters because a TEE-bound workload can act *exclusively* as an agent for an entity by managing a unique keychain per entity it serves[^wivai].

[^wivai]: 113061126-workload-identity-vs-agent-identity.md

## Why the SIG cares about the distinction

Once "AI agents" became a household term, drafts started showing up in IETF proposing a single workload-identity-token also serve as the agent's identity[^aiagent]. The SIG's view is that workload identity is necessary but **not sufficient** for personal agents:

> "Personal Agents not only have to have their own 'identity', but also must be able to secure credentials and other personal information on behalf of each of the entities they represent. That requires each agent to be able to persist not only its own keychain for its own use, but also a unique keychain for each entity it represents."[^chatgptlinkedin]

The trigger discussion was a public incident where ChatGPT logged into a user's LinkedIn — a textbook case of an agent without proper per-entity credential isolation[^chatgptlinkedin].

[^aiagent]: 115889621-fyi-workload-identity-for-ai-agents.md
[^chatgptlinkedin]: 115104223-workload-identity-for-ai-agents-can-t-come-soon-enough.md

## The "exclusivity" question

Manu Fontaine's original framing — a workload "acts exclusively on behalf of" an entity — provoked a productive disagreement[^wivai]:

| Concern | Position |
|---|---|
| **HSM-shared keys break exclusivity** (Mark Novak) | If N identical workload instances pull the same secret from an HSM, an external non-TEE party can also be authorized — exclusivity is lost. Exclusivity only holds if each workload instance generates and certifies its own keys. |
| **"On behalf of" already means delegation** (Mark Novak) | Be cognisant when advertising it that way — the term has prior art. |
| **Verifier-managed keychains preserve it** (Manu Fontaine) | Each agent instance works exclusively for the entity it serves at a given moment; together the cluster works collectively. The Verifier holds a unique keychain per Attesting Agent. |
| **Cryptographic delegation as the building block** (Manu Fontaine) | An agent managing the keychain of another entity is foundational for chaining and composing workloads. |

This same axis — share identity across replicas, vs. each instance having its own — is exactly what the [Replica & Twin Workloads](replica-and-twin-workloads.md) profile resolves for the cloud-deployment case.

## Adjacent IETF work

The SIG tracks (without owning) several drafts in this space[^reading]:

- `draft-ni-wimse-ai-agent-identity` — WIMSE applicability for AI agents.
- `draft-klrc-aiagent-auth` — AI Agent Authentication and Authorization (Network WG, not WIMSE).
- `draft-mw-wimse-transitive-attestation` — transitive attestation for "sovereign workloads".

[^reading]: 118844386-some-reading-for-next-week-39-s-twi-meeting.md

## See also

- [Trustworthy Composability](trustworthy-composability.md) — the recursive trust frame in which "agent" is layered
- [Trustworthy Workload Identity](trustworthy-workload-identity.md)
- [Manu Fontaine](../entities/people/manu-fontaine.md), [Mark Novak](../entities/people/mark-novak.md)
