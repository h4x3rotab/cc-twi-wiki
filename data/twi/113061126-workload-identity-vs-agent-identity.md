---
topic_id: 113061126
subject: "Workload Identity vs. Agent Identity"
participants: ["Manu Fontaine", "Mark Novak"]
first_post: 2025-05-11
last_post: 2025-05-12
message_count: 3
source: https://lists.confidentialcomputing.io/g/Trustworthy-Workload-Identity-SIG/topic/workload_identity_vs_agent/113061126
---

# Workload Identity vs. Agent Identity

## Message 1 (#23) — Manu Fontaine — 2025-05-11 21:47 UTC

Confidential Computing enables a workload in a TEE to "act exclusively on behalf" of another entity (i.e. as its exclusive "Agent") by generating, managing, and securing a unique keychain for each individual entity. By entity, I mean people, orgs, physical things, and digital things (like other Agents, for instance). This is a "key" use case (pun intended) for the "agentic era", but it's also foundational for global cybersecurity in general (authenticity, confidentiality, privacy...).

We should make sure that our CCC Reference Architecture provides zero-trust assurances to each individual entity that their Agents never expose entity-bound keys. Because this is something that cannot be done with non-CC workloads, outside TEEs, it is not contemplated at all in emerging standards. Not sure if it has an impact on what we're working on for the IETF.

Let me know what you think, talk on Tuesday.

Manu

## Message 2 (#24) — Mark Novak — 2025-05-12 13:51 UTC

Manu,

I like the sense I get of where you are going with this. I don't know if I agree with the wording as it has certain implications.

"Act exclusively on behalf of" has two implications:

First, "exclusively" is not strictly possible if a number of identical workload instances get their secrets from an HSM, which is a required deployment pattern. Under that setup another entity that is not running in a TEE could be authorized for the secret key, and then you lose exclusivity. "Exclusive" only works if each workload instance generates and certifies its own keys, but even then, if I, say, employ two secretaries to act on my behalf doing effectively identical work but in parallel, are they operating "exclusively" or "collectively"?

Second, "on behalf of" I think has a meaning already and that meaning is delegation. Again, something to be cognizant of when we advertise it that way.

Happy to discuss tomorrow.

## Message 3 (#27) — Manu Fontaine — 2025-05-12 22:34 UTC

Yeah, the wording is not easy. Always looking for better ways to explain this.

Exclusivity works across a number of identical Agent instances if they all get their secrets from their Verifier, and if the Verifier itself can generate, manage, and secure a unique keychain for each Attesting Agent. Each identical Agent instance works exclusively for the entity it serves at that moment in time, but all the identical Agent instances work collectively to serve all entities as they need something done on their behalf.

And yes, I agree: "on behalf of" is indeed delegation, as an entity delegates the management of its keychain to its Agent, which can then can act on its behalf. This construct of an Agent managing the keychain of other entities is a foundational building block to cryptographically chain and "compose" workloads, precisely because it enables cryptographic delegation.

Again, maybe not the right wording, but hopefully directionally helpful. Talk tomorrow.

Manu

  

On Mon, May 12, 2025 at 9:51 AM Mark Novak via [lists.confidentialcomputing.io](http://lists.confidentialcomputing.io) <mark.novak=[outlook.com@...](mailto:outlook.com@...)> wrote:

[toggle quoted message
Show quoted text](#quoted-252571553)

> Manu,
>
> I like the sense I get of where you are going with this. I don't know if I agree with the wording as it has certain implications.
>
> "Act exclusively on behalf of" has two implications:
>
> First, "exclusively" is not strictly possible if a number of identical workload instances get their secrets from an HSM, which is a required deployment pattern. Under that setup another entity that is not running in a TEE could be authorized for the secret key, and then you lose exclusivity. "Exclusive" only works if each workload instance generates and certifies its own keys, but even then, if I, say, employ two secretaries to act on my behalf doing effectively identical work but in parallel, are they operating "exclusively" or "collectively"?
>
> Second, "on behalf of" I think has a meaning already and that meaning is delegation. Again, something to be cognizant of when we advertise it that way.
>
> Happy to discuss tomorrow.

contentLoaded(false, function() {
$('#quoted-252571553').on('show.bs.collapse', function() {
$('#qlabel-252571553').text("Hide quoted text");
})
$('#quoted-252571553').on('hide.bs.collapse', function() {
$('#qlabel-252571553').text("Show quoted text");
})
});
