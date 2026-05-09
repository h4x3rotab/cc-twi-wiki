---
topic_id: 116109344
subject: "Mail regarding draft-mihalcea-seat-use-cases: one key &quot;integration property&quot; missing"
participants: ["Mark Novak"]
first_post: 2025-11-04
last_post: 2025-11-04
message_count: 1
source: https://lists.confidentialcomputing.io/g/Trustworthy-Workload-Identity-SIG/topic/mail_regarding/116109344
---

# Mail regarding draft-mihalcea-seat-use-cases: one key &quot;integration property&quot; missing

## Message 1 (#107) — Mark Novak — 2025-11-04 00:20 UTC

Reviewing the SEAT use cases [draft](https://datatracker.ietf.org/doc/draft-mihalcea-seat-use-cases/), I'm noticing that it says nothing about manageability of deployments. I believe that ease of operation is a key integration property.

My talk on Friday about integration of trustworthy workload identity (TWI) with RATS emphasizes precisely that: stability of credentials. As software and hardware is patched (including periodic reversal of faulty patches), there is a policy invariant in place:
what constitutes an acceptable set of properties for a counter-party. Stability is usually achieved by reasoning about a set of business-centric claims ("latest version of payroll application", "running on approved hardware").

There is, at the very least, ample room for collaboration between SEAT and TWI.

Let's discuss.
