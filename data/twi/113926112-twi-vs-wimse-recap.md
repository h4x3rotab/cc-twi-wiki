---
topic_id: 113926112
subject: "TWI vs. WIMSE -- recap"
participants: ["Mark Novak"]
first_post: 2025-07-01
last_post: 2025-07-01
message_count: 1
source: https://lists.confidentialcomputing.io/g/Trustworthy-Workload-Identity-SIG/topic/twi_vs_wimse_recap/113926112
---

# TWI vs. WIMSE -- recap

## Message 1 (#54) — Mark Novak — 2025-07-01 12:14 UTC

So I finally went through all the WIMSE drafts yesterday and took notes of where WIMSE appears incompatible with Confidential Computing. I took a few rough notes, which I quote further below.

Bottom line is that WIMSE attempts to stay completely out of the credentials issuance business, and stick to proof-of-possession requirements, but not all WIMSE documents strictly keep to these tenets. As a result, I believe TWI is mostly compatible with WIMSE
as is, but care must be taken to ensure that it remains so in everything they do.

I believe that all matters of credentials issuance should be dealt with inside the RATS working group, and after Madrid we should focus most of our attention on that (plus the reference architecture, of course). For the immediate purposes, we should scope our
informational draft very tightly to just the WIMSE relevant statements.

Here's my summary of findings. My notes in **bold**. Emphasis on original text in
*italics.*

[WIMSE Reference Architecture, Draft 4](https://datatracker.ietf.org/doc/draft-ietf-wimse-arch/)

3.1.3.  Workload Identity Credentials

An *agent* provisions the identity credentials to the workload. **<< Not under CC; with CC the workload acquires its own credentials; there is no "agent" external to the workload.**

… the WIMSE architecture defines a workload identity token that binds a JWT to a cryptographic key.
**<< Good**

3.2.1.  Basic Workload Identity Scenario

Workloads obtain their identity credentials from a Credentials Service… **<< Good; note there is no mention of "agent" here.**

The credentials are often X.509 based or JWT based. **<< Should also re-state that the WIT is a JWT with a JWS, otherwise good.**

Workloads typically *retrieve* their workload identity credentials early in their lifecycle from a credentials service associated with their trust domain.  The protocol interaction for obtaining credentials varies with deployment and is not detailed here.
**<< “Retrieve” sounds like someone else has created them… “obtain” is a better term.**

… the workloads can use a JWT based authentication mechanism to authenticate on [*sic*] another.
**<< Why not say WIT based if WIT is a JWT?**

3.3.1.  Bootstrapping Workload Identifiers and Credentials

A workload needs to *obtain* its identifier and associated credentials early in its lifecycle.
**<< Good (again, no mention of agent)**

**Figure 4 does not work for CC — under CC, “agent” does not perform attestation, the workload does, and one agent cannot serve multiple workloads; Can we add Figure 4.1 that works for CC? Placing the agent inside the workload may fix the problem.**

[WIMSE S2S Protocol, Draft 5](https://datatracker.ietf.org/doc/draft-ietf-wimse-s2s-protocol/)

“jti” claim is optional**<< we should require it, or at least make it a SHOULD**

3.6 — coexistence with JWT bearer tokens **<< can’t have that, except for ingress authentication of (presumably non-confidential) workloads**

5.2, 5.3 — **TODO: analyze the PoP replay mitigation section for sufficiency**

[Workload Identity Practices, Draft 1](https://datatracker.ietf.org/doc/draft-ietf-wimse-workload-identity-practices/)

**The discussion of how a credential is obtained may not be CC compatible.**

**The discussion of various ways in which credentials might be made available does not include remote attestation.**

**Credential binding is a MUST for CC.**
