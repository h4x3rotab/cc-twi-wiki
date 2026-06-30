---
topic_id: 119273859
subject: "Impossibility of RATS-Unaware Relying Parties in the RATS Architecture"
participants: ["Mark Novak"]
first_post: 2026-05-12
last_post: 2026-05-13
message_count: 2
source: https://lists.confidentialcomputing.io/g/Trustworthy-Workload-Identity-SIG/topic/impossibility_of_rats_unaware/119273859
---

# Impossibility of RATS-Unaware Relying Parties in the RATS Architecture

## Message 1 (#172) — Mark Novak — 2026-05-12 12:57 UTC

Hello all.

I'm deliberately cross-posting this to both SIGs as there were questions asked in both forums that needed a more formal answer than the one I was able to provide previously. Namely the question is this: Is it possible to convert an existing workload using non-human
identity with its Relying Party to run inside a TEE, and yet not make any changes to that Relying Party.

I hope that this document answers this question definitively.

Note also (here I'm being a broken record) that in the unfortunate messy real world, Relying Parties are frequently intransigent and will not change for their clients. So for us to unlock broad adoption of Confidential Computing, we need an extension to the
RATS architecture — something that the TWI SIG is hoping to present at the Vienna IETF.

As usual, critiques are welcome.

<https://docs.google.com/document/d/13r1FuOg6vRGwOxGOCCXs4kOVXC1LS-dtAmXt4upEivw/edit?tab=t.0#heading=h.jxj7tsrhw0st>

## Message 2 (#173) — Mark Novak — 2026-05-13 15:12 UTC

As a follow-up to yesterday's explanation why RATS-unaware relying parties cannot be handled within the RATS architecture proper, sharing the document explaining why RATS-unaware relying parties are unavoidable.

Together, these two documents explain why we need an extension to the RATS architecture to handle such Relying Parties.

<https://docs.google.com/document/d/1sRNAl0KL4h1zt-YcGEetu7Qxm9c5M-asxTJiqC5o5CU/edit?tab=t.0>

Commenter access will be granted to all who request it. As always, all reasonable feedback and critique is welcome.

[toggle quoted message
Show quoted text](#quoted-265782405)

---

**From:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...> on behalf of Mark Novak via lists.confidentialcomputing.io <mark.novak=outlook.com@...>  
**Sent:** Tuesday, May 12, 2026 5:57 AM  
**To:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...>; attestation@... <attestation@...>  
**Subject:** [Trustworthy-Workload-Identity-SIG] Impossibility of RATS-Unaware Relying Parties in the RATS Architecture

Hello all.

I'm deliberately cross-posting this to both SIGs as there were questions asked in both forums that needed a more formal answer than the one I was able to provide previously. Namely the question is this: Is it possible to convert an existing workload using non-human
identity with its Relying Party to run inside a TEE, and yet not make any changes to that Relying Party.

I hope that this document answers this question definitively.

Note also (here I'm being a broken record) that in the unfortunate messy real world, Relying Parties are frequently intransigent and will not change for their clients. So for us to unlock broad adoption of Confidential Computing, we need an extension to the
RATS architecture — something that the TWI SIG is hoping to present at the Vienna IETF.

As usual, critiques are welcome.

<https://docs.google.com/document/d/13r1FuOg6vRGwOxGOCCXs4kOVXC1LS-dtAmXt4upEivw/edit?tab=t.0#heading=h.jxj7tsrhw0st>

contentLoaded(false, function() {
$('#quoted-265782405').on('show.bs.collapse', function() {
$('#qlabel-265782405').text("Hide quoted text");
})
$('#quoted-265782405').on('hide.bs.collapse', function() {
$('#qlabel-265782405').text("Show quoted text");
})
});
