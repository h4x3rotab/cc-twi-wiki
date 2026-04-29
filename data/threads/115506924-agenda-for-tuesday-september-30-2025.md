---
topic_id: 115506924
subject: "Agenda for Tuesday September 30, 2025"
participants: ["Mark Novak"]
first_post: 2025-09-30
last_post: 2025-09-30
message_count: 1
source: https://lists.confidentialcomputing.io/g/Trustworthy-Workload-Identity-SIG/topic/agenda_for_tuesday_september/115506924
---

# Agenda for Tuesday September 30, 2025

## Message 1 (#93) — Mark Novak — 2025-09-30 01:06 UTC

Last week the meeting did not take place because nobody showed up. Let's try again tomorrow.

The agenda remains unchanged from last week (see attached).

Additionally, a new I-D has been introduced to RATS: <https://datatracker.ietf.org/doc/draft-ritz-eca/>. It talks about an area of interest to TWI — ephemeral workload instances — so we should probably take a look and see if we have any thoughts worth sharing. Note that this protocol appears to require two
roundtrips to the Verifier (section 4).

|  |
| --- |
| [Ephemeral Compute Attestation (ECA) Protocol draft-ritz-eca-00](https://datatracker.ietf.org/doc/draft-ritz-eca/)  This document specifies the Ephemeral Compute Attestation (ECA) protocol, which enables ephemeral compute instances to prove their identity without pre-shared operational credentials. ECA uses a three-phase ceremony that cryptographically combines a public Boot Factor (a high-entropy provisioning value), a secret Instance Factor, and a dynamically released Validator Factor to establish ...  datatracker.ietf.org |
