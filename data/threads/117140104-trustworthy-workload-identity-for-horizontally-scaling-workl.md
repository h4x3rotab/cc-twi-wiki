---
topic_id: 117140104
subject: "Trustworthy Workload Identity for horizontally scaling workloads"
participants: ["Mark Novak"]
first_post: 2026-01-07
last_post: 2026-01-07
message_count: 1
source: https://lists.confidentialcomputing.io/g/Trustworthy-Workload-Identity-SIG/topic/trustworthy_workload_identity/117140104
---

# Trustworthy Workload Identity for horizontally scaling workloads

## Message 1 (#119) — Mark Novak — 2026-01-07 19:09 UTC

Happy new year everyone,

In 2026 the TWI SIG will continue our efforts to standardize mechanisms for trustworthy credentials issuance for confidential workloads. We believe we have a path forward that will be acceptable to both WIMSE and RATS IETF working groups. This will most likely
be expressed in a revision of our 2025 IETF drafts.

For WIMSE, we'll present it in an interim meeting as soon as we're ready. Per my conversations with the WIMSE leadership, this will simply be a new WIMSE profile, i.e., no architectural or design changes required — a big win for interoperability.

For RATS, the goal is to submit it to the Shenzhen IETF meeting.

This may be the same document, or two different perspectives on the same core idea. The first class of workloads we'll be targeting are of the "horizontal scale-out" variety, meaning multiple twin workload instances sharing the same key and credential, best
exemplified by containers and lambda functions.

It would be great if we could also, in parallel, initiate a proof of concept implementation of these ideas in one of the CCC projects. "Trustee" is the closest that was discussed, but there very well may be others. As convincing as documents can be, implementation
always seals the deal.

If you are interested in collaborating on this effort, join the TWI meeting, every Tuesday, 6am Pacific. Here is the Zoom link.

<https://zoom-lfx.platform.linuxfoundation.org/meeting/98843213693?password=4502f135-8bbe-4e84-a171-bb8b8132758d>
