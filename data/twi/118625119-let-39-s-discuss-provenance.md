---
topic_id: 118625119
subject: "Let&#39;s discuss Provenance?"
participants: ["Manu Fontaine"]
first_post: 2026-04-01
last_post: 2026-04-01
message_count: 1
source: https://lists.confidentialcomputing.io/g/Trustworthy-Workload-Identity-SIG/topic/let_s_discuss_provenance/118625119
---

# Let&#39;s discuss Provenance?

## Message 1 (#142) — Manu Fontaine — 2026-04-01 22:08 UTC

During this week's TWI call, Abdullah brought up Provenance and Supply Chain Security as critical topics we should discuss, and I agree.

Provenance will force us to think about "chains of workloads" instead of each workload individually.

As we realized while working on the "TWI Profile for Replica Workloads" paper, the entire attestation verification chain ends up in the Attester workload's TCB.

This means that all the bits the verification chain relies on to verify the Attester workload's attestation evidence are themselves in the TCB.

Because all bits originate from other workloads, it follows that we need to approach this as a recursive system architecture for workload chains. (Dare I say, a "mesh" of workloads :)

I look forward to the discussion, and we can start on the list.

Thanks, Abdullah, for bringing up the topic.

Manu
