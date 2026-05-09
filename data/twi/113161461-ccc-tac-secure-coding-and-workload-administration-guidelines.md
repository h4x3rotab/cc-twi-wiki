---
topic_id: 113161461
subject: "[CCC][tac] Secure coding and workload administration guidelines for confidential computing"
participants: ["Manu Fontaine"]
first_post: 2025-05-17
last_post: 2025-05-17
message_count: 1
source: https://lists.confidentialcomputing.io/g/Trustworthy-Workload-Identity-SIG/topic/ccc_tac_secure_coding_and/113161461
---

# [CCC][tac] Secure coding and workload administration guidelines for confidential computing

## Message 1 (#30) — Manu Fontaine — 2025-05-17 14:05 UTC

Mark, I agree with your point on the importance of "overall payload security" and the need for clear guidelines around "secure workload administration."  
  
The value of attestation is significantly reduced (if not entirely undermined) when the expected behavior of a verified workload (i.e., its "identity" *from the perspective of the relying party*, not internal operators) can be altered post-attestation using unverified artifacts. If a workload requires "altered states", those should occur through verifiable composability (potentially with different "identities"). In practice, this means that if admins can alter a workload’s configuration, the configuration files themselves should be part of the verifiable composition.  
  

In this context, Grok’s “[Unauthorized Modification](https://gizmodo.com/elon-musks-xai-says-unauthorized-modification-made-grok-spout-white-genocide-conspiracy-theory-2000603363)” event is particularly illuminating. It suggests that even "components" like AI prompts, along with their provenance, should be bound within the verifiable composition. This incident serves as a textbook case of what we might call “Agentic [Dissociative Identity Disorder](https://en.wikipedia.org/wiki/Dissociative_identity_disorder#:~:text=compartmentalization%20of%20psychological,control%20mental%20functions%22),” and it should inform our Trusted Workload Identity (TWI) efforts, too.

Thanks,

Manu

  

On Fri, May 16, 2025 at 9:47 AM Mark Novak via [lists.confidentialcomputing.io](http://lists.confidentialcomputing.io) <mark.novak=[outlook.com@...](mailto:outlook.com@...)> wrote:

[toggle quoted message
Show quoted text](#quoted-252745050)

> Dan,
>
> Yesterday's TAC discussion got me thinking that we should take a different approach to Confidential Computing coding guidelines. The current approach has been to document what we can inside the Payload governance pattern. Since the field is evolving, that would
> make that governance pattern too fluid. Instead, it should mention "write your code securely as documented in X" and we should author X separately.
>
> So I propose that we start a different document, not a governance pattern (because it does not lend itself to dedicated governance requirements), and solicit contributions to it from all participants, including the Kernel SIG. Then we will reference this document
> from the Payload governance pattern.
>
> Similarly, we need to think about overall payload security, not just what code developers need to think about, but also what system administrators need to do. My poster child for this is confidential VMs: huge TCB, extensible by design, hard to make sense of
> attestation reference values, administrators can really mess things up if they log in interactively, etc. So perhaps a different "secure workload administration" guide would be in order, that we could likewise reference from the governance documents.
>
> Thoughts?

contentLoaded(false, function() {
$('#quoted-252745050').on('show.bs.collapse', function() {
$('#qlabel-252745050').text("Hide quoted text");
})
$('#quoted-252745050').on('hide.bs.collapse', function() {
$('#qlabel-252745050').text("Show quoted text");
})
});
