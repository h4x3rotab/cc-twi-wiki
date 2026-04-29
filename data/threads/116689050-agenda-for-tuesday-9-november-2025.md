---
topic_id: 116689050
subject: "Agenda for Tuesday 9 November 2025"
participants: ["Manu Fontaine", "Mark Novak"]
first_post: 2025-12-09
last_post: 2025-12-09
message_count: 2
source: https://lists.confidentialcomputing.io/g/Trustworthy-Workload-Identity-SIG/topic/agenda_for_tuesday_9_november/116689050
---

# Agenda for Tuesday 9 November 2025

## Message 1 (#114) — Mark Novak — 2025-12-09 03:13 UTC

There are quite a few TODOs in the Reference Architecture. I'm hoping to close some of them tomorrow. Looking guards to the discussion.

## Message 2 (#115) — Manu Fontaine — 2025-12-09 10:48 UTC

Good morning, Mark.

Unfortunately, I won't be able to attend the meeting this week.

Things that I would have liked to bring up:

* If a "workload instance" is a single entity running across a cluster of machines, how do we call each "[the code running on a single machine]" and how do all of them share the same identities, identifiers, keys, and information across the cluster?
* I think we need to explicitly think of "chains or relying parties" (as opposed to just one RP) to make sure the architecture deals with third-, fourth-, fifth-party risks. This is adjacent to delegation and composite attestations, and I think it brings up the need for "verifiers of verifiers" across administrative domains (a la SitusAMC), i.e. global supply chains.

Thanks, see you next time, be well.

Sincerely,

Manu Fontaine

Hushmesh Founder and CEO

  

On Mon, Dec 8, 2025 at 10:13 PM Mark Novak via [lists.confidentialcomputing.io](http://lists.confidentialcomputing.io) <mark.novak=[outlook.com@...](mailto:outlook.com@...)> wrote:

[toggle quoted message
Show quoted text](#quoted-260229144)

> There are quite a few TODOs in the Reference Architecture. I'm hoping to close some of them tomorrow. Looking guards to the discussion.

contentLoaded(false, function() {
$('#quoted-260229144').on('show.bs.collapse', function() {
$('#qlabel-260229144').text("Hide quoted text");
})
$('#quoted-260229144').on('hide.bs.collapse', function() {
$('#qlabel-260229144').text("Show quoted text");
})
});
