---
topic_id: 117479181
subject: "Agenda for Tuesday January 27, 2026"
participants: ["Manu Fontaine", "Mark Novak"]
first_post: 2026-01-26
last_post: 2026-01-26
message_count: 2
source: https://lists.confidentialcomputing.io/g/Trustworthy-Workload-Identity-SIG/topic/agenda_for_tuesday_january/117479181
---

# Agenda for Tuesday January 27, 2026

## Message 1 (#123) — Mark Novak — 2026-01-26 22:47 UTC

Hello all,

New diagrams were added to the "[TWI
Profile for WIMSE](https://docs.google.com/document/d/1hIBda3-MRgqrVY-Klv4vvlt0TNU1ibmiAtSddzXPO1c/edit?tab=t.0)" that we can review tomorrow. I suspect there will be multiple ways of doing provisioning, but only one to do acquisition. Manu, can you check if the Provisioning diagram works for HushMesh, and if not, we can add that as an alternative.

Tomorrow we'll review the latest edits to the TWI Profile document, discuss in what format to present it to the IETF (both WIMSE and RATS), and, time permitting, start working out the threat model for the proposed message exchanges.

I'm also working to have this proposal prototyped by one of our engineers, stay tuned for that.

On Wednesday I have a meeting with one of WIMSE's principals, Joe Saloway, but since that's after our meeting tomorrow, I won't have those inputs just yet.

## Message 2 (#124) — Manu Fontaine — 2026-01-26 23:18 UTC

Thanks Mark!

I think the diagram, with the wrapping key mechanism, is directionally correct. Our flows are somewhat different/simpler as the only communication the attesting workload has is with its verifier (itself in a TEE, per the "least trust" principle).

I won't be able to attend tomorrow's meeting. I'll see you next week. Thanks, be well.

Sincerely,

Manu Fontaine

Hushmesh Founder and CEO

  

On Mon, Jan 26, 2026 at 5:47 PM Mark Novak via [lists.confidentialcomputing.io](http://lists.confidentialcomputing.io) <mark.novak=[outlook.com@...](mailto:outlook.com@...)> wrote:

[toggle quoted message
Show quoted text](#quoted-261914545)

> Hello all,
>
> New diagrams were added to the "[TWI
> Profile for WIMSE](https://docs.google.com/document/d/1hIBda3-MRgqrVY-Klv4vvlt0TNU1ibmiAtSddzXPO1c/edit?tab=t.0)" that we can review tomorrow. I suspect there will be multiple ways of doing provisioning, but only one to do acquisition. Manu, can you check if the Provisioning diagram works for HushMesh, and if not, we can add that as an alternative.
>
> Tomorrow we'll review the latest edits to the TWI Profile document, discuss in what format to present it to the IETF (both WIMSE and RATS), and, time permitting, start working out the threat model for the proposed message exchanges.
>
> I'm also working to have this proposal prototyped by one of our engineers, stay tuned for that.
>
> On Wednesday I have a meeting with one of WIMSE's principals, Joe Saloway, but since that's after our meeting tomorrow, I won't have those inputs just yet.

contentLoaded(false, function() {
$('#quoted-261914545').on('show.bs.collapse', function() {
$('#qlabel-261914545').text("Hide quoted text");
})
$('#quoted-261914545').on('hide.bs.collapse', function() {
$('#qlabel-261914545').text("Show quoted text");
})
});
