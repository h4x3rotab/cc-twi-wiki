---
topic_id: 118956224
subject: "Fw: [CCC] [attestation] Documents from today&#39;s presentation"
participants: ["Mark Novak"]
first_post: 2026-04-22
last_post: 2026-04-22
message_count: 1
source: https://lists.confidentialcomputing.io/g/Trustworthy-Workload-Identity-SIG/topic/fw_ccc_attestation/118956224
---

# Fw: [CCC] [attestation] Documents from today&#39;s presentation

## Message 1 (#158) — Mark Novak — 2026-04-22 15:02 UTC

I presented some attestation-focused aspects of our work to the Attestation SIG yesterday.

I am still struggling with what our Vienna contribution to the IETF is going to be. I can think of two related directions:

1. More concrete: "Achieving Relying Party stability": since Attestation Results may change with each change in Evidence, and we are faced with rollouts and rollbacks of workloads, in the real-world, Relying Parties
   cannot be affected by what the organization considers a "known good" version of the workload. That can be mitigated by introducing another architectural entity between the Verifier and the Relying Party (so, Attestation Results go to that new entity, which
   allows the Attester to present the outcome of Remote Attestation — in the form of a credential — to the Relying Party in a manner that isolates the Relying Party from the volatility.
2. Less concrete: A discussion of a relationship between remote attestation and attester credential issuance. This to my mind is less desirable as the IETF has indicated before that they like focused drafts, just
   like they did with our earlier submissions. I have noted in a number of forums already that credential bootstrapping falls into the crack between WIMSE and RATS, and needs a home.

  

Your thoughts are appreciated.

[toggle quoted message
Show quoted text](#quoted-265056368)

---

**From:** attestation@... <attestation@...> on behalf of Mark Novak via lists.confidentialcomputing.io <mark.novak=outlook.com@...>  
**Sent:** Wednesday, April 22, 2026 6:41 AM  
**To:** attestation@... <attestation@...>  
**Subject:** Re: [CCC] [attestation] Documents from today's presentation

Upon reflection, I think an important detail was left out of the conversation yesterday: just how flexible can Attestation Results be? Are they really so binary as to require them to literally contain just an identifier of the workload? The answer may have
come across as an unequivocal "yes", but it's more nuanced than that.

In the TWI for Replica proposal, you will see that Attestation Results can change when the Evidence changes. This is still done without disrupting the Relying Parties, as the proposal allows the key release policy for the Credential Signing Key (CSK) to be
updated with the Evidence. In fact that can be said to be a security requirement, as older workloads should not be allowed to obtain the credential (after the rollout completes).

So really the implementor has two options:

1: turn the Verifier into a Credential Authority and then Attestation Results are what the Attester needs to get to successfully authenticate to the Relying Party, and the Attestation Results must remain unchanged for as long as the Evidence input into the
Verifier is the "known good".

2. Insert an intermediary between the Verifier and the Relying Party (like the Key Store in the TWI proposal) that contains the Attestation Results volatility — and guarantees that the Relying Party remains unperturbed by any known-good change.

---

**From:** Mark Novak <Mark.Novak@...>  
**Sent:** Tuesday, April 21, 2026 11:07 AM  
**To:** attestation@... <attestation@...>  
**Subject:** Documents from today's presentation

Key points:

* Large organizations that are most likely to pay good $ for Confidential Computing are internally divided with clients and servers often owned by different business units
* Use of workload identity (e.g. SPIFFE) is increasingly common
* Workload identities are typically short and not very semantically rich (e.g., URIs such as SVIDs), they express trust domain, workload purpose and maybe location, little else — that's a good thing, Relying Parties
  want to let someone else decide and manage what is "known good"
* It ought to be possible to move any workload to Confidential Computing in a way that retains its identity: the key requirement is that such a change does not affect — at all! — any of their clients or servers.
  A payroll app is a payroll app before and after, whether it is moving from legacy to confidential, or from one known-good version to another.

The "replica workloads" proposal from the TWI SIG is attached as PDF if you want to read it, but if you want to comment please use
[this URL](https://docs.google.com/document/d/1hIBda3-MRgqrVY-Klv4vvlt0TNU1ibmiAtSddzXPO1c/edit?usp=sharing).

Thank you for the discussion today. Now can we talk about the next steps?

contentLoaded(false, function() {
$('#quoted-265056368').on('show.bs.collapse', function() {
$('#qlabel-265056368').text("Hide quoted text");
})
$('#quoted-265056368').on('hide.bs.collapse', function() {
$('#qlabel-265056368').text("Show quoted text");
})
});
