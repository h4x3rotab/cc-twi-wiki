---
topic_id: 118365330
subject: "Fw: Trustworthy Workload Identity Profile for Replica Workloads"
participants: ["Mark Novak"]
first_post: 2026-03-17
last_post: 2026-03-17
message_count: 1
source: https://lists.confidentialcomputing.io/g/Trustworthy-Workload-Identity-SIG/topic/fw_trustworthy_workload/118365330
---

# Fw: Trustworthy Workload Identity Profile for Replica Workloads

## Message 1 (#137) — Mark Novak — 2026-03-17 14:47 UTC

Just shared this with the Attestation SIG. Should've cc'ed this SIG but didn't. Apologies.

[toggle quoted message
Show quoted text](#quoted-263807954)

---

**From:** Mark Novak <Mark.Novak@...>  
**Sent:** Tuesday, March 17, 2026 7:47 AM  
**To:** attestation@... <attestation@...>  
**Subject:** Trustworthy Workload Identity Profile for Replica Workloads

Please review the attached document from the TWI SIG. This is the output of the last few months' work by the TWI SIG.

Here is the key scenario that this proposal addresses:

An organization has standardized on a workload identity architecture that is based on bound tokens — for example, but not necessarily, WIMSE. The organization operates multiple workloads, each owned by a different team/division within the organization. It ought
to be possible to upgrade any workload inside the organization to Confidential Computing without the workload's clients or servers noticing the difference (the "zero blast radius" requirement).

To comment, use the source document at [this URL](https://docs.google.com/document/d/1hIBda3-MRgqrVY-Klv4vvlt0TNU1ibmiAtSddzXPO1c/edit?tab=t.0). Request access if you don't have it, I will grant promptly.

On April 21st, I will be making a presentation to the Attestation SIG that is related to this proposal. Specifically, my presentation will address the following two issues:

* The workload and the hardware on which it runs are typically managed by different teams, even different organization, in case of public clouds. Therefore, the question of "what constitutes a valid workload" and
  "what constitutes valid hardware" are answered by different people. The appraisal policy for evidence, therefore, has multiple independent parts that the Verifier must treat as such in its policy management.
* Not all upgrades are security sensitive, but all change evidence. The mapping between evidence and attestation results must take that into consideration — the result is improved robustness.

We welcome all comments.

contentLoaded(false, function() {
$('#quoted-263807954').on('show.bs.collapse', function() {
$('#qlabel-263807954').text("Hide quoted text");
})
$('#quoted-263807954').on('hide.bs.collapse', function() {
$('#qlabel-263807954').text("Show quoted text");
})
});
