---
topic_id: 118845083
subject: "Fw: Anticipating Reference Values"
participants: ["Mark Novak"]
first_post: 2026-04-15
last_post: 2026-04-15
message_count: 1
source: https://lists.confidentialcomputing.io/g/Trustworthy-Workload-Identity-SIG/topic/fw_anticipating_reference/118845083
---

# Fw: Anticipating Reference Values

## Message 1 (#156) — Mark Novak — 2026-04-15 17:35 UTC

I just emailed the following to the RATS mailing list at the IETF. It may yet bounce, since I first sent this and only then subscribed to the mailing list. If so, I will resend.

Please review. This led me to question: rather than take on the full burden of converting our entire proposal to an IETF draft, should we instead focus specifically on this aspect of the proposal, since the rest does not change anything about RATS?

We can discuss on the mailing list on in next week's meeting.

[toggle quoted message
Show quoted text](#quoted-264821691)

---

**From:** Mark Novak <Mark.Novak@...>  
**Sent:** Wednesday, April 15, 2026 10:11 AM  
**To:** rats <rats@...>  
**Subject:** Anticipating Reference Values

Hello,

The Trustworthy Workload Identity SIG at the Confidential Computing Consortium is putting together a proposal for providing "replica" workloads with industry-standard credentials based on results of Remote Attestation. Replica workloads are defined as those
workloads that are functionally indistinguishable from each other from the POV of their clients and servers, as is typical with containers, lambda functions, horizontally scaling VMs and the like.

The precise nature of the proposal is not central to the question below, but I am attaching it for your reference. In a nutshell, the proposal involves precomputing the credentials for the workloads in question and making the corresponding credential signing
key available only to the workloads that successfully perform Remote Attestation.

The question is this: what are the existing best practices/considerations around being able to predict what Attestation Results would be returned for a given workload, without first having to start and remotely attest the workload?

Presumably, being able to do this would require:

1. Knowing ahead of time what Evidence a workload would be presenting, as well as
2. Knowing and/or controlling what Appraisal Policy for this Evidence is going to be

We would love to hear your thoughts.

contentLoaded(false, function() {
$('#quoted-264821691').on('show.bs.collapse', function() {
$('#qlabel-264821691').text("Hide quoted text");
})
$('#quoted-264821691').on('hide.bs.collapse', function() {
$('#qlabel-264821691').text("Show quoted text");
})
});
