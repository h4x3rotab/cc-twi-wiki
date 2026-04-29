---
topic_id: 118990275
subject: "Early draft of the Vienna submission"
participants: ["Mark Novak", "Markus Rudy"]
first_post: 2026-04-24
last_post: 2026-04-24
message_count: 7
source: https://lists.confidentialcomputing.io/g/Trustworthy-Workload-Identity-SIG/topic/early_draft_of_the_vienna/118990275
---

# Early draft of the Vienna submission

## Message 1 (#161) — Mark Novak — 2026-04-24 16:05 UTC

This is what I wrote down so far. We can start reviewing this next week. Thoughts?

# Abstract

There is a large class of "RATS-Unaware" Relying Parties (RUPs) that Attesters nevertheless need to interoperate with. RUPs cannot process Attestation Results or execute Appraisal Policy for Attestation Results. This specification extends the RATS Architecture
to interoperate with RUPs.

# Introduction

Success of a technology is ultimately measured by its adoption. The RATS architecture, by requiring that Relying Parties understand Attestation Results and execute Appraisal Policy for Attestation Results, intrinsically limits adoption to Relying Parties that
understand RATS protocols and standards. Additionally, the unstated assumption present in the RATS architecture that a change in Evidence may lead to a change in Attestation Results makes it impossible to manage Relying Parties whose authentication policies
remain static for long periods of time.

For these RATS-Unaware Relying Parties, these adoption barriers can be eliminated, so long as they are capable of authenticating their clients via proof-of-possession mechanisms utilizing credentials such as x.509 certificates or WIMSE WITs. This is done by
enabling the Attester to use the RATS Attestation Results to obtain or utilize a credential that a RUP can interoperate with.

# Conventions and Terminology

# RUP-Extended RATS Architecture

In order for an Attester to interoperate with a RUP, the RATS Relying Party MUST have a mechanism for returning to the Attester either a 1) an asymmetric signing key encrypted to an attested, Attester-held asymmetric encryption key, or 2) a credential matching
an attested, Attester-held asymmetric signing key.

┌────────┐            ┌─────────┐    ┌────────┐   ┌───────┐

│Endorser├───────┐    │Reference│    │Verifier│   │Relying│

└────────┘       │    │  Value  │    │ Owner  │   │ Party │

│    │Provider │    └┬───────┘   │ Owner │

│    └───┬─────┘     │           └─┬─────┘

│        │           │Appraisal    │

│        │Reference  │Policy for   │

│        │Values     │Evidence     │Appraisal

│        │           │             │Policy for

│        │           │             │Attestation

┌─▼────────▼───────────▼ ─┐          │Results

┌────────►│    Verifier             ├──┐       │

│         └─────────────────────────┘  │       │

│                           Attestation│       │

│                               Results│       │

│                                  ┌───▼───────▼─┐

┌────┴───┐                              │   Relying   │

│Attester◄──────────────────────────────┤    Party    │

└────┬───┘          Credential          └─────────────┘

│

│                                  ┌─────────────┐

│  Authentication with Credential  │RATS-Unaware │

└──────────────────────────────────►Relying Party│

└────▲────────┘

RATS-Unaware │

Authentication │

Policy │

┌────┴────────┐

│RATS-Unaware │

│Relying Party│

│Owner        │

└─────────────┘

# Security Considerations

<fill in>

# IANA Considerations

<fill in>

## Message 2 (#162) — Markus Rudy — 2026-04-24 16:42 UTC

Hi Mark,

I don’t see anything wrong with your model, but I don’t understand why you think the RATS architecture needs to be amended with RUPs. Nothing in the existing RATS model prescribes what the RP should do with the attestation results, and maybe that’s a good thing?
You are already free to implement an RP with your requirement

> In order for an Attester to interoperate with a RUP, the RATS Relying Party MUST have a mechanism for returning to the Attester either a 1) an asymmetric signing key encrypted to an attested, Attester-held asymmetric encryption key, or 2) a credential matching
an attested, Attester-held asymmetric signing key.

but other adopters are also free to implement an RP for a RUP (i.e., an identity provider?) in another way of their choice (symmetric keys for PAKE, Kerberos tickets, …).

It’s also unclear to me why one would require “a mechanism for returning to the Attester,” but not prescribe that mechanism any further. Seems like that does not solve the interoperability?

Cheers, Markus

**From:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...> on behalf of Mark Novak via lists.confidentialcomputing.io <mark.novak=outlook.com@...>  
**Date:** Friday, 24. April 2026 at 18:05  
**To:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...>  
**Subject:** [Trustworthy-Workload-Identity-SIG] Early draft of the Vienna submission

This is what I wrote down so far. We can start reviewing this next week. Thoughts?

# Abstract

There is a large class of "RATS-Unaware" Relying Parties (RUPs) that Attesters nevertheless need to interoperate with. RUPs cannot process Attestation Results or execute Appraisal Policy for Attestation Results. This specification extends the RATS Architecture
to interoperate with RUPs.

# Introduction

Success of a technology is ultimately measured by its adoption. The RATS architecture, by requiring that Relying Parties understand Attestation Results and execute Appraisal Policy for Attestation Results, intrinsically limits adoption to Relying Parties that
understand RATS protocols and standards. Additionally, the unstated assumption present in the RATS architecture that a change in Evidence may lead to a change in Attestation Results makes it impossible to manage Relying Parties whose authentication policies
remain static for long periods of time.

For these RATS-Unaware Relying Parties, these adoption barriers can be eliminated, so long as they are capable of authenticating their clients via proof-of-possession mechanisms utilizing credentials such as x.509 certificates or WIMSE WITs. This is done by
enabling the Attester to use the RATS Attestation Results to obtain or utilize a credential that a RUP can interoperate with.

# Conventions and Terminology

# RUP-Extended RATS Architecture

In order for an Attester to interoperate with a RUP, the RATS Relying Party MUST have a mechanism for returning to the Attester either a 1) an asymmetric signing key encrypted to an attested, Attester-held asymmetric encryption key, or 2) a credential matching
an attested, Attester-held asymmetric signing key.

┌────────┐            ┌─────────┐    ┌────────┐   ┌───────┐

│Endorser├───────┐    │Reference│    │Verifier│   │Relying│

└────────┘       │    │  Value  │    │ Owner  │   │ Party │

│    │Provider │    └┬───────┘   │ Owner │

│    └───┬─────┘     │           └─┬─────┘

│        │           │Appraisal    │

│        │Reference  │Policy for   │

│        │Values     │Evidence     │Appraisal

│        │           │             │Policy for

│        │           │             │Attestation

┌─▼────────▼───────────▼ ─┐          │Results

┌────────►│    Verifier             ├──┐       │

│         └─────────────────────────┘  │       │

│                           Attestation│       │

│                               Results│       │

│                                  ┌───▼───────▼─┐

┌────┴───┐                              │   Relying   │

│Attester◄──────────────────────────────┤    Party    │

└────┬───┘          Credential          └─────────────┘

│

│                                  ┌─────────────┐

│  Authentication with Credential  │RATS-Unaware │

└──────────────────────────────────►Relying Party│

└────▲────────┘

RATS-Unaware │

Authentication │

Policy │

┌────┴────────┐

│RATS-Unaware │

│Relying Party│

│Owner        │

└─────────────┘

# Security Considerations

<fill in>

# IANA Considerations

<fill in>

## Message 3 (#163) — Mark Novak — 2026-04-24 16:55 UTC

Markus,

Thank you for the feedback.

The reason I believe this extension to the RATS architecture is necessary is because from the implementor's point of view, looking at the RATS architecture, they will say "our relying parties cannot do that", and the implementors of Confidential Computing solutions,
likewise, will not provide this option. To date, that has been the case. The ultimate goal is to unblock adoption. A lot of focus, in my opinion, has been placed outside of the needs of existing relying parties, and assuming that Relying Parties will change
because of Confidential Computing. My assertion is many of them — enough to really matter — will not. This needs to be addressed.

As to not describing the mechanism any further, I just shared the opening paragraphs. I hinted at two possibilities: the attester can include in Evidence an asymmetric signing key and receive a full credential corresponding to that key (making the Relying Party
a Credential Authority), or it can include an asymmetric encryption key, and receive from the Relying Party (in this, case, a Key Store), just a signing key needed to unlock the use of a pre-provisioned credential that requires the key for proof-of-possession.
A completed draft would include additional details, which we can agree on in subsequent meetings.

I hope that clarifies.

[toggle quoted message
Show quoted text](#quoted-265131963)

---

**From:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...> on behalf of Markus Rudy via lists.confidentialcomputing.io <mr=edgeless.systems@...>  
**Sent:** Friday, April 24, 2026 9:41 AM  
**To:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...>  
**Subject:** Re: [Trustworthy-Workload-Identity-SIG] Early draft of the Vienna submission

Hi Mark,

I don’t see anything wrong with your model, but I don’t understand why you think the RATS architecture needs to be amended with RUPs. Nothing in the existing RATS model prescribes what the RP should do with the attestation results, and maybe that’s a good thing?
You are already free to implement an RP with your requirement

> In order for an Attester to interoperate with a RUP, the RATS Relying Party MUST have a mechanism for returning to the Attester either a 1) an asymmetric signing key encrypted to an attested, Attester-held asymmetric encryption key, or 2) a credential matching
an attested, Attester-held asymmetric signing key.

but other adopters are also free to implement an RP for a RUP (i.e., an identity provider?) in another way of their choice (symmetric keys for PAKE, Kerberos tickets, …).

It’s also unclear to me why one would require “a mechanism for returning to the Attester,” but not prescribe that mechanism any further. Seems like that does not solve the interoperability?

Cheers, Markus

**From:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...> on behalf of Mark Novak via lists.confidentialcomputing.io <mark.novak=outlook.com@...>  
**Date:** Friday, 24. April 2026 at 18:05  
**To:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...>  
**Subject:** [Trustworthy-Workload-Identity-SIG] Early draft of the Vienna submission

This is what I wrote down so far. We can start reviewing this next week. Thoughts?

# Abstract

There is a large class of "RATS-Unaware" Relying Parties (RUPs) that Attesters nevertheless need to interoperate with. RUPs cannot process Attestation Results or execute Appraisal Policy for Attestation Results. This specification extends the RATS Architecture
to interoperate with RUPs.

# Introduction

Success of a technology is ultimately measured by its adoption. The RATS architecture, by requiring that Relying Parties understand Attestation Results and execute Appraisal Policy for Attestation Results, intrinsically limits adoption to Relying Parties that
understand RATS protocols and standards. Additionally, the unstated assumption present in the RATS architecture that a change in Evidence may lead to a change in Attestation Results makes it impossible to manage Relying Parties whose authentication policies
remain static for long periods of time.

For these RATS-Unaware Relying Parties, these adoption barriers can be eliminated, so long as they are capable of authenticating their clients via proof-of-possession mechanisms utilizing credentials such as x.509 certificates or WIMSE WITs. This is done by
enabling the Attester to use the RATS Attestation Results to obtain or utilize a credential that a RUP can interoperate with.

# Conventions and Terminology

# RUP-Extended RATS Architecture

In order for an Attester to interoperate with a RUP, the RATS Relying Party MUST have a mechanism for returning to the Attester either a 1) an asymmetric signing key encrypted to an attested, Attester-held asymmetric encryption key, or 2) a credential matching
an attested, Attester-held asymmetric signing key.

┌────────┐            ┌─────────┐    ┌────────┐   ┌───────┐

│Endorser├───────┐    │Reference│    │Verifier│   │Relying│

└────────┘       │    │  Value  │    │ Owner  │   │ Party │

│    │Provider │    └┬───────┘   │ Owner │

│    └───┬─────┘     │           └─┬─────┘

│        │           │Appraisal    │

│        │Reference  │Policy for   │

│        │Values     │Evidence     │Appraisal

│        │           │             │Policy for

│        │           │             │Attestation

┌─▼────────▼───────────▼ ─┐          │Results

┌────────►│    Verifier             ├──┐       │

│         └─────────────────────────┘  │       │

│                           Attestation│       │

│                               Results│       │

│                                  ┌───▼───────▼─┐

┌────┴───┐                              │   Relying   │

│Attester◄──────────────────────────────┤    Party    │

└────┬───┘          Credential          └─────────────┘

│

│                                  ┌─────────────┐

│  Authentication with Credential  │RATS-Unaware │

└──────────────────────────────────►Relying Party│

└────▲────────┘

RATS-Unaware │

Authentication │

Policy │

┌────┴────────┐

│RATS-Unaware │

│Relying Party│

│Owner        │

└─────────────┘

# Security Considerations

<fill in>

# IANA Considerations

<fill in>

contentLoaded(false, function() {
$('#quoted-265131963').on('show.bs.collapse', function() {
$('#qlabel-265131963').text("Hide quoted text");
})
$('#quoted-265131963').on('hide.bs.collapse', function() {
$('#qlabel-265131963').text("Show quoted text");
})
});

## Message 4 (#164) — Markus Rudy — 2026-04-24 17:07 UTC

Your draft acknowledges that there needs to be a CC-aware RP - the one interpreting the attestation results and handing out credentials. I believe the RUPs you are thinking of don’t even need to be included in the model: if you already have a classical IdP
that these RUPs rely on, you only need to make that IdP CC-aware, and let it hand out credentials in the same way that’s already understood by the RUPs. The RUPs never need to learn about CC. What am I missing?

**From:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...> on behalf of Mark Novak via lists.confidentialcomputing.io <mark.novak=outlook.com@...>  
**Date:** Friday, 24. April 2026 at 18:55  
**To:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...>  
**Subject:** Re: [Trustworthy-Workload-Identity-SIG] Early draft of the Vienna submission

Markus,

Thank you for the feedback.

The reason I believe this extension to the RATS architecture is necessary is because from the implementor's point of view, looking at the RATS architecture, they will say "our relying parties cannot do that", and the implementors of Confidential Computing solutions,
likewise, will not provide this option. To date, that has been the case. The ultimate goal is to unblock adoption. A lot of focus, in my opinion, has been placed outside of the needs of existing relying parties, and assuming that Relying Parties will change
because of Confidential Computing. My assertion is many of them — enough to really matter — will not. This needs to be addressed.

As to not describing the mechanism any further, I just shared the opening paragraphs. I hinted at two possibilities: the attester can include in Evidence an asymmetric signing key and receive a full credential corresponding to that key (making the Relying Party
a Credential Authority), or it can include an asymmetric encryption key, and receive from the Relying Party (in this, case, a Key Store), just a signing key needed to unlock the use of a pre-provisioned credential that requires the key for proof-of-possession.
A completed draft would include additional details, which we can agree on in subsequent meetings.

I hope that clarifies.

[toggle quoted message
Show quoted text](#quoted-265132425)

---

**From:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...> on behalf of Markus Rudy via lists.confidentialcomputing.io <mr=edgeless.systems@...>  
**Sent:** Friday, April 24, 2026 9:41 AM  
**To:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...>  
**Subject:** Re: [Trustworthy-Workload-Identity-SIG] Early draft of the Vienna submission

Hi Mark,

I don’t see anything wrong with your model, but I don’t understand why you think the RATS architecture needs to be amended with RUPs. Nothing in the existing RATS model prescribes what the RP should do with the attestation results, and maybe that’s a good thing?
You are already free to implement an RP with your requirement

> In order for an Attester to interoperate with a RUP, the RATS Relying Party MUST have a mechanism for returning to the Attester either a 1) an asymmetric signing key encrypted to an attested, Attester-held asymmetric encryption key, or 2) a credential matching
an attested, Attester-held asymmetric signing key.

but other adopters are also free to implement an RP for a RUP (i.e., an identity provider?) in another way of their choice (symmetric keys for PAKE, Kerberos tickets, …).

It’s also unclear to me why one would require “a mechanism for returning to the Attester,” but not prescribe that mechanism any further. Seems like that does not solve the interoperability?

Cheers, Markus

**From:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...> on behalf of Mark Novak via lists.confidentialcomputing.io <mark.novak=outlook.com@...>  
**Date:** Friday, 24. April 2026 at 18:05  
**To:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...>  
**Subject:** [Trustworthy-Workload-Identity-SIG] Early draft of the Vienna submission

This is what I wrote down so far. We can start reviewing this next week. Thoughts?

# Abstract

There is a large class of "RATS-Unaware" Relying Parties (RUPs) that Attesters nevertheless need to interoperate with. RUPs cannot process Attestation Results or execute Appraisal Policy for Attestation Results. This specification extends the RATS Architecture
to interoperate with RUPs.

# Introduction

Success of a technology is ultimately measured by its adoption. The RATS architecture, by requiring that Relying Parties understand Attestation Results and execute Appraisal Policy for Attestation Results, intrinsically limits adoption to Relying Parties that
understand RATS protocols and standards. Additionally, the unstated assumption present in the RATS architecture that a change in Evidence may lead to a change in Attestation Results makes it impossible to manage Relying Parties whose authentication policies
remain static for long periods of time.

For these RATS-Unaware Relying Parties, these adoption barriers can be eliminated, so long as they are capable of authenticating their clients via proof-of-possession mechanisms utilizing credentials such as x.509 certificates or WIMSE WITs. This is done by
enabling the Attester to use the RATS Attestation Results to obtain or utilize a credential that a RUP can interoperate with.

# Conventions and Terminology

# RUP-Extended RATS Architecture

In order for an Attester to interoperate with a RUP, the RATS Relying Party MUST have a mechanism for returning to the Attester either a 1) an asymmetric signing key encrypted to an attested, Attester-held asymmetric encryption key, or 2) a credential matching
an attested, Attester-held asymmetric signing key.

┌────────┐            ┌─────────┐    ┌────────┐   ┌───────┐

│Endorser├───────┐    │Reference│    │Verifier│   │Relying│

└────────┘       │    │  Value  │    │ Owner  │   │ Party │

│    │Provider │    └┬───────┘   │ Owner │

│    └───┬─────┘     │           └─┬─────┘

│        │           │Appraisal    │

│        │Reference  │Policy for   │

│        │Values     │Evidence     │Appraisal

│        │           │             │Policy for

│        │           │             │Attestation

┌─▼────────▼───────────▼ ─┐          │Results

┌────────►│    Verifier             ├──┐       │

│         └─────────────────────────┘  │       │

│                           Attestation│       │

│                               Results│       │

│                                  ┌───▼───────▼─┐

┌────┴───┐                              │   Relying   │

│Attester◄──────────────────────────────┤    Party    │

└────┬───┘          Credential          └─────────────┘

│

│                                  ┌─────────────┐

│  Authentication with Credential  │RATS-Unaware │

└──────────────────────────────────►Relying Party│

└────▲────────┘

RATS-Unaware │

Authentication │

Policy │

┌────┴────────┐

│RATS-Unaware │

│Relying Party│

│Owner        │

└─────────────┘

# Security Considerations

<fill in>

# IANA Considerations

<fill in>

contentLoaded(false, function() {
$('#quoted-265132425').on('show.bs.collapse', function() {
$('#qlabel-265132425').text("Hide quoted text");
})
$('#quoted-265132425').on('hide.bs.collapse', function() {
$('#qlabel-265132425').text("Show quoted text");
})
});

## Message 5 (#165) — Mark Novak — 2026-04-24 17:16 UTC

The only thing you are missing is that these IdPs are nowhere to be found. There is currently no way to integrate SPIFFE with CC, for instance.

The draft is meant to initiate dialog around this subject and result in creation of products and features required for that. There is work to enable Trustworthiness Vectors for Confidential Containers, and there may be market demand for that. From where I stand,
these efforts are missing the point: we need to create deployment options in environments where things move slowly and not all at once.

Where we stand today is: potential customers looking into adoption are without options for their existing environments.

[toggle quoted message
Show quoted text](#quoted-265132738)

---

**From:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...> on behalf of Markus Rudy via lists.confidentialcomputing.io <mr=edgeless.systems@...>  
**Sent:** Friday, April 24, 2026 10:07 AM  
**To:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...>  
**Subject:** Re: [Trustworthy-Workload-Identity-SIG] Early draft of the Vienna submission

Your draft acknowledges that there needs to be a CC-aware RP - the one interpreting the attestation results and handing out credentials. I believe the RUPs you are thinking of don’t even need to be included in the model: if you already have a classical IdP
that these RUPs rely on, you only need to make that IdP CC-aware, and let it hand out credentials in the same way that’s already understood by the RUPs. The RUPs never need to learn about CC. What am I missing?

**From:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...> on behalf of Mark Novak via lists.confidentialcomputing.io <mark.novak=outlook.com@...>  
**Date:** Friday, 24. April 2026 at 18:55  
**To:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...>  
**Subject:** Re: [Trustworthy-Workload-Identity-SIG] Early draft of the Vienna submission

Markus,

Thank you for the feedback.

The reason I believe this extension to the RATS architecture is necessary is because from the implementor's point of view, looking at the RATS architecture, they will say "our relying parties cannot do that", and the implementors of Confidential Computing solutions,
likewise, will not provide this option. To date, that has been the case. The ultimate goal is to unblock adoption. A lot of focus, in my opinion, has been placed outside of the needs of existing relying parties, and assuming that Relying Parties will change
because of Confidential Computing. My assertion is many of them — enough to really matter — will not. This needs to be addressed.

As to not describing the mechanism any further, I just shared the opening paragraphs. I hinted at two possibilities: the attester can include in Evidence an asymmetric signing key and receive a full credential corresponding to that key (making the Relying Party
a Credential Authority), or it can include an asymmetric encryption key, and receive from the Relying Party (in this, case, a Key Store), just a signing key needed to unlock the use of a pre-provisioned credential that requires the key for proof-of-possession.
A completed draft would include additional details, which we can agree on in subsequent meetings.

I hope that clarifies.

---

**From:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...> on behalf of Markus Rudy via lists.confidentialcomputing.io <mr=edgeless.systems@...>  
**Sent:** Friday, April 24, 2026 9:41 AM  
**To:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...>  
**Subject:** Re: [Trustworthy-Workload-Identity-SIG] Early draft of the Vienna submission

Hi Mark,

I don’t see anything wrong with your model, but I don’t understand why you think the RATS architecture needs to be amended with RUPs. Nothing in the existing RATS model prescribes what the RP should do with the attestation results, and maybe that’s a good thing?
You are already free to implement an RP with your requirement

> In order for an Attester to interoperate with a RUP, the RATS Relying Party MUST have a mechanism for returning to the Attester either a 1) an asymmetric signing key encrypted to an attested, Attester-held asymmetric encryption key, or 2) a credential matching
an attested, Attester-held asymmetric signing key.

but other adopters are also free to implement an RP for a RUP (i.e., an identity provider?) in another way of their choice (symmetric keys for PAKE, Kerberos tickets, …).

It’s also unclear to me why one would require “a mechanism for returning to the Attester,” but not prescribe that mechanism any further. Seems like that does not solve the interoperability?

Cheers, Markus

**From:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...> on behalf of Mark Novak via lists.confidentialcomputing.io <mark.novak=outlook.com@...>  
**Date:** Friday, 24. April 2026 at 18:05  
**To:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...>  
**Subject:** [Trustworthy-Workload-Identity-SIG] Early draft of the Vienna submission

This is what I wrote down so far. We can start reviewing this next week. Thoughts?

# Abstract

There is a large class of "RATS-Unaware" Relying Parties (RUPs) that Attesters nevertheless need to interoperate with. RUPs cannot process Attestation Results or execute Appraisal Policy for Attestation Results. This specification extends the RATS Architecture
to interoperate with RUPs.

# Introduction

Success of a technology is ultimately measured by its adoption. The RATS architecture, by requiring that Relying Parties understand Attestation Results and execute Appraisal Policy for Attestation Results, intrinsically limits adoption to Relying Parties that
understand RATS protocols and standards. Additionally, the unstated assumption present in the RATS architecture that a change in Evidence may lead to a change in Attestation Results makes it impossible to manage Relying Parties whose authentication policies
remain static for long periods of time.

For these RATS-Unaware Relying Parties, these adoption barriers can be eliminated, so long as they are capable of authenticating their clients via proof-of-possession mechanisms utilizing credentials such as x.509 certificates or WIMSE WITs. This is done by
enabling the Attester to use the RATS Attestation Results to obtain or utilize a credential that a RUP can interoperate with.

# Conventions and Terminology

# RUP-Extended RATS Architecture

In order for an Attester to interoperate with a RUP, the RATS Relying Party MUST have a mechanism for returning to the Attester either a 1) an asymmetric signing key encrypted to an attested, Attester-held asymmetric encryption key, or 2) a credential matching
an attested, Attester-held asymmetric signing key.

┌────────┐            ┌─────────┐    ┌────────┐   ┌───────┐

│Endorser├───────┐    │Reference│    │Verifier│   │Relying│

└────────┘       │    │  Value  │    │ Owner  │   │ Party │

│    │Provider │    └┬───────┘   │ Owner │

│    └───┬─────┘     │           └─┬─────┘

│        │           │Appraisal    │

│        │Reference  │Policy for   │

│        │Values     │Evidence     │Appraisal

│        │           │             │Policy for

│        │           │             │Attestation

┌─▼────────▼───────────▼ ─┐          │Results

┌────────►│    Verifier             ├──┐       │

│         └─────────────────────────┘  │       │

│                           Attestation│       │

│                               Results│       │

│                                  ┌───▼───────▼─┐

┌────┴───┐                              │   Relying   │

│Attester◄──────────────────────────────┤    Party    │

└────┬───┘          Credential          └─────────────┘

│

│                                  ┌─────────────┐

│  Authentication with Credential  │RATS-Unaware │

└──────────────────────────────────►Relying Party│

└────▲────────┘

RATS-Unaware │

Authentication │

Policy │

┌────┴────────┐

│RATS-Unaware │

│Relying Party│

│Owner        │

└─────────────┘

# Security Considerations

<fill in>

# IANA Considerations

<fill in>

contentLoaded(false, function() {
$('#quoted-265132738').on('show.bs.collapse', function() {
$('#qlabel-265132738').text("Hide quoted text");
})
$('#quoted-265132738').on('hide.bs.collapse', function() {
$('#qlabel-265132738').text("Show quoted text");
})
});

## Message 6 (#166) — Markus Rudy — 2026-04-24 18:21 UTC

Understood, thanks for the explanation. For the record, I’m totally going with your expectation that most existing RPs won’t adopt CC in the foreseeable future.

Do I understand correctly that we should rather start with feature requests in SPIRE, Vault, CSP IAMs etc., as soon as the required standards (EAR and CoRIM) are final?

**From:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...> on behalf of Mark Novak via lists.confidentialcomputing.io <mark.novak=outlook.com@...>  
**Date:** Friday, 24. April 2026 at 19:16  
**To:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...>  
**Subject:** Re: [Trustworthy-Workload-Identity-SIG] Early draft of the Vienna submission

The only thing you are missing is that these IdPs are nowhere to be found. There is currently no way to integrate SPIFFE with CC, for instance.

The draft is meant to initiate dialog around this subject and result in creation of products and features required for that. There is work to enable Trustworthiness Vectors for Confidential Containers, and there may be market demand for that. From where I stand,
these efforts are missing the point: we need to create deployment options in environments where things move slowly and not all at once.

Where we stand today is: potential customers looking into adoption are without options for their existing environments.

[toggle quoted message
Show quoted text](#quoted-265134973)

---

**From:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...> on behalf of Markus Rudy via lists.confidentialcomputing.io <mr=edgeless.systems@...>  
**Sent:** Friday, April 24, 2026 10:07 AM  
**To:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...>  
**Subject:** Re: [Trustworthy-Workload-Identity-SIG] Early draft of the Vienna submission

Your draft acknowledges that there needs to be a CC-aware RP - the one interpreting the attestation results and handing out credentials. I believe the RUPs you are thinking of don’t even need to be included in the model: if you already have a classical IdP
that these RUPs rely on, you only need to make that IdP CC-aware, and let it hand out credentials in the same way that’s already understood by the RUPs. The RUPs never need to learn about CC. What am I missing?

**From:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...> on behalf of Mark Novak via lists.confidentialcomputing.io <mark.novak=outlook.com@...>  
**Date:** Friday, 24. April 2026 at 18:55  
**To:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...>  
**Subject:** Re: [Trustworthy-Workload-Identity-SIG] Early draft of the Vienna submission

Markus,

Thank you for the feedback.

The reason I believe this extension to the RATS architecture is necessary is because from the implementor's point of view, looking at the RATS architecture, they will say "our relying parties cannot do that", and the implementors of Confidential Computing solutions,
likewise, will not provide this option. To date, that has been the case. The ultimate goal is to unblock adoption. A lot of focus, in my opinion, has been placed outside of the needs of existing relying parties, and assuming that Relying Parties will change
because of Confidential Computing. My assertion is many of them — enough to really matter — will not. This needs to be addressed.

As to not describing the mechanism any further, I just shared the opening paragraphs. I hinted at two possibilities: the attester can include in Evidence an asymmetric signing key and receive a full credential corresponding to that key (making the Relying Party
a Credential Authority), or it can include an asymmetric encryption key, and receive from the Relying Party (in this, case, a Key Store), just a signing key needed to unlock the use of a pre-provisioned credential that requires the key for proof-of-possession.
A completed draft would include additional details, which we can agree on in subsequent meetings.

I hope that clarifies.

---

**From:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...> on behalf of Markus Rudy via lists.confidentialcomputing.io <mr=edgeless.systems@...>  
**Sent:** Friday, April 24, 2026 9:41 AM  
**To:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...>  
**Subject:** Re: [Trustworthy-Workload-Identity-SIG] Early draft of the Vienna submission

Hi Mark,

I don’t see anything wrong with your model, but I don’t understand why you think the RATS architecture needs to be amended with RUPs. Nothing in the existing RATS model prescribes what the RP should do with the attestation results, and maybe that’s a good thing?
You are already free to implement an RP with your requirement

> In order for an Attester to interoperate with a RUP, the RATS Relying Party MUST have a mechanism for returning to the Attester either a 1) an asymmetric signing key encrypted to an attested, Attester-held asymmetric encryption key, or 2) a credential matching
an attested, Attester-held asymmetric signing key.

but other adopters are also free to implement an RP for a RUP (i.e., an identity provider?) in another way of their choice (symmetric keys for PAKE, Kerberos tickets, …).

It’s also unclear to me why one would require “a mechanism for returning to the Attester,” but not prescribe that mechanism any further. Seems like that does not solve the interoperability?

Cheers, Markus

**From:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...> on behalf of Mark Novak via lists.confidentialcomputing.io <mark.novak=outlook.com@...>  
**Date:** Friday, 24. April 2026 at 18:05  
**To:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...>  
**Subject:** [Trustworthy-Workload-Identity-SIG] Early draft of the Vienna submission

This is what I wrote down so far. We can start reviewing this next week. Thoughts?

# Abstract

There is a large class of "RATS-Unaware" Relying Parties (RUPs) that Attesters nevertheless need to interoperate with. RUPs cannot process Attestation Results or execute Appraisal Policy for Attestation Results. This specification extends the RATS Architecture
to interoperate with RUPs.

# Introduction

Success of a technology is ultimately measured by its adoption. The RATS architecture, by requiring that Relying Parties understand Attestation Results and execute Appraisal Policy for Attestation Results, intrinsically limits adoption to Relying Parties that
understand RATS protocols and standards. Additionally, the unstated assumption present in the RATS architecture that a change in Evidence may lead to a change in Attestation Results makes it impossible to manage Relying Parties whose authentication policies
remain static for long periods of time.

For these RATS-Unaware Relying Parties, these adoption barriers can be eliminated, so long as they are capable of authenticating their clients via proof-of-possession mechanisms utilizing credentials such as x.509 certificates or WIMSE WITs. This is done by
enabling the Attester to use the RATS Attestation Results to obtain or utilize a credential that a RUP can interoperate with.

# Conventions and Terminology

# RUP-Extended RATS Architecture

In order for an Attester to interoperate with a RUP, the RATS Relying Party MUST have a mechanism for returning to the Attester either a 1) an asymmetric signing key encrypted to an attested, Attester-held asymmetric encryption key, or 2) a credential matching
an attested, Attester-held asymmetric signing key.

┌────────┐            ┌─────────┐    ┌────────┐   ┌───────┐

│Endorser├───────┐    │Reference│    │Verifier│   │Relying│

└────────┘       │    │  Value  │    │ Owner  │   │ Party │

│    │Provider │    └┬───────┘   │ Owner │

│    └───┬─────┘     │           └─┬─────┘

│        │           │Appraisal    │

│        │Reference  │Policy for   │

│        │Values     │Evidence     │Appraisal

│        │           │             │Policy for

│        │           │             │Attestation

┌─▼────────▼───────────▼ ─┐          │Results

┌────────►│    Verifier             ├──┐       │

│         └─────────────────────────┘  │       │

│                           Attestation│       │

│                               Results│       │

│                                  ┌───▼───────▼─┐

┌────┴───┐                              │   Relying   │

│Attester◄──────────────────────────────┤    Party    │

└────┬───┘          Credential          └─────────────┘

│

│                                  ┌─────────────┐

│  Authentication with Credential  │RATS-Unaware │

└──────────────────────────────────►Relying Party│

└────▲────────┘

RATS-Unaware │

Authentication │

Policy │

┌────┴────────┐

│RATS-Unaware │

│Relying Party│

│Owner        │

└─────────────┘

# Security Considerations

<fill in>

# IANA Considerations

<fill in>

contentLoaded(false, function() {
$('#quoted-265134973').on('show.bs.collapse', function() {
$('#qlabel-265134973').text("Hide quoted text");
})
$('#quoted-265134973').on('hide.bs.collapse', function() {
$('#qlabel-265134973').text("Show quoted text");
})
});

## Message 7 (#167) — Mark Novak — 2026-04-24 18:35 UTC

I am for all hands on deck approach: this new  I-D and all the outreach you mention.

The way the RATS architecture was specified causes all this confusion and adoption barriers precisely because the term Relying Party was used when really it ought to have been called the Attestation Result Recipient. The second serious shortcoming of the architecture
is failure to connect remote attestation to attester credentials issuance.

This SIG is trying to address both these issues. Fortunately, with the right approach I hope this will not be too difficult.

[toggle quoted message
Show quoted text](#quoted-265135467)

---

**From:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...> on behalf
of Markus Rudy via lists.confidentialcomputing.io <mr=edgeless.systems@...>  
**Sent:** Friday, April 24, 2026 11:21:14 AM  
**To:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...>  
**Subject:** Re: [Trustworthy-Workload-Identity-SIG] Early draft of the Vienna submission

Understood, thanks for the explanation. For the record, I’m totally going with your expectation that most existing RPs won’t adopt CC in the foreseeable future.

Do I understand correctly that we should rather start with feature requests in SPIRE, Vault, CSP IAMs etc., as soon as the required standards (EAR and CoRIM) are final?

**From:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...> on behalf of Mark Novak via lists.confidentialcomputing.io <mark.novak=outlook.com@...>  
**Date:** Friday, 24. April 2026 at 19:16  
**To:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...>  
**Subject:** Re: [Trustworthy-Workload-Identity-SIG] Early draft of the Vienna submission

The only thing you are missing is that these IdPs are nowhere to be found. There is currently no way to integrate SPIFFE with CC, for instance.

The draft is meant to initiate dialog around this subject and result in creation of products and features required for that. There is work to enable Trustworthiness Vectors for Confidential Containers, and there may be market demand for that. From where I stand,
these efforts are missing the point: we need to create deployment options in environments where things move slowly and not all at once.

Where we stand today is: potential customers looking into adoption are without options for their existing environments.

---

**From:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...> on behalf of Markus Rudy via lists.confidentialcomputing.io <mr=edgeless.systems@...>  
**Sent:** Friday, April 24, 2026 10:07 AM  
**To:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...>  
**Subject:** Re: [Trustworthy-Workload-Identity-SIG] Early draft of the Vienna submission

Your draft acknowledges that there needs to be a CC-aware RP - the one interpreting the attestation results and handing out credentials. I believe the RUPs you are thinking of don’t even need to be included in the model: if you already have a classical IdP
that these RUPs rely on, you only need to make that IdP CC-aware, and let it hand out credentials in the same way that’s already understood by the RUPs. The RUPs never need to learn about CC. What am I missing?

**From:**Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...> on behalf of Mark Novak via lists.confidentialcomputing.io <mark.novak=outlook.com@...>  
**Date:** Friday, 24. April 2026 at 18:55  
**To:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...>  
**Subject:** Re: [Trustworthy-Workload-Identity-SIG] Early draft of the Vienna submission

Markus,

Thank you for the feedback.

The reason I believe this extension to the RATS architecture is necessary is because from the implementor's point of view, looking at the RATS architecture, they will say "our relying parties cannot do that", and the implementors of Confidential Computing solutions,
likewise, will not provide this option. To date, that has been the case. The ultimate goal is to unblock adoption. A lot of focus, in my opinion, has been placed outside of the needs of existing relying parties, and assuming that Relying Parties will change
because of Confidential Computing. My assertion is many of them — enough to really matter — will not. This needs to be addressed.

As to not describing the mechanism any further, I just shared the opening paragraphs. I hinted at two possibilities: the attester can include in Evidence an asymmetric signing key and receive a full credential corresponding to that key (making the Relying Party
a Credential Authority), or it can include an asymmetric encryption key, and receive from the Relying Party (in this, case, a Key Store), just a signing key needed to unlock the use of a pre-provisioned credential that requires the key for proof-of-possession.
A completed draft would include additional details, which we can agree on in subsequent meetings.

I hope that clarifies.

---

**From:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...> on behalf of Markus Rudy via lists.confidentialcomputing.io <mr=edgeless.systems@...>  
**Sent:** Friday, April 24, 2026 9:41 AM  
**To:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...>  
**Subject:** Re: [Trustworthy-Workload-Identity-SIG] Early draft of the Vienna submission

Hi Mark,

I don’t see anything wrong with your model, but I don’t understand why you think the RATS architecture needs to be amended with RUPs. Nothing in the existing RATS model prescribes what the RP should do with the attestation results, and maybe that’s a good thing?
You are already free to implement an RP with your requirement

> In order for an Attester to interoperate with a RUP, the RATS Relying Party MUST have a mechanism for returning to the Attester either a 1) an asymmetric signing key encrypted to an attested, Attester-held asymmetric encryption key, or 2) a credential matching
an attested, Attester-held asymmetric signing key.

but other adopters are also free to implement an RP for a RUP (i.e., an identity provider?) in another way of their choice (symmetric keys for PAKE, Kerberos tickets, …).

It’s also unclear to me why one would require “a mechanism for returning to the Attester,” but not prescribe that mechanism any further. Seems like that does not solve the interoperability?

Cheers, Markus

**From:**Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...> on behalf of Mark Novak via lists.confidentialcomputing.io <mark.novak=outlook.com@...>  
**Date:** Friday, 24. April 2026 at 18:05  
**To:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...>  
**Subject:** [Trustworthy-Workload-Identity-SIG] Early draft of the Vienna submission

This is what I wrote down so far. We can start reviewing this next week. Thoughts?

# Abstract

There is a large class of "RATS-Unaware" Relying Parties (RUPs) that Attesters nevertheless need to interoperate with. RUPs cannot process Attestation Results or execute Appraisal Policy for Attestation Results. This specification extends the RATS Architecture
to interoperate with RUPs.

# Introduction

Success of a technology is ultimately measured by its adoption. The RATS architecture, by requiring that Relying Parties understand Attestation Results and execute Appraisal Policy for Attestation Results, intrinsically limits adoption to Relying Parties that
understand RATS protocols and standards. Additionally, the unstated assumption present in the RATS architecture that a change in Evidence may lead to a change in Attestation Results makes it impossible to manage Relying Parties whose authentication policies
remain static for long periods of time.

For these RATS-Unaware Relying Parties, these adoption barriers can be eliminated, so long as they are capable of authenticating their clients via proof-of-possession mechanisms utilizing credentials such as x.509 certificates or WIMSE WITs. This is done by
enabling the Attester to use the RATS Attestation Results to obtain or utilize a credential that a RUP can interoperate with.

# Conventions and Terminology

# RUP-Extended RATS Architecture

In order for an Attester to interoperate with a RUP, the RATS Relying Party MUST have a mechanism for returning to the Attester either a 1) an asymmetric signing key encrypted to an attested, Attester-held asymmetric encryption key, or 2) a credential matching
an attested, Attester-held asymmetric signing key.

┌────────┐            ┌─────────┐    ┌────────┐   ┌───────┐

│Endorser├───────┐    │Reference│    │Verifier│   │Relying│

└────────┘       │    │  Value  │    │ Owner  │   │ Party │

│    │Provider │    └┬───────┘   │ Owner │

│    └───┬─────┘     │           └─┬─────┘

│        │           │Appraisal    │

│        │Reference  │Policy for   │

│        │Values     │Evidence     │Appraisal

│        │           │             │Policy for

│        │           │             │Attestation

┌─▼────────▼───────────▼ ─┐          │Results

┌────────►│    Verifier             ├──┐       │

│         └─────────────────────────┘  │       │

│                           Attestation│       │

│                               Results│       │

│                                  ┌───▼───────▼─┐

┌────┴───┐                              │   Relying   │

│Attester◄──────────────────────────────┤    Party    │

└────┬───┘          Credential          └─────────────┘

│

│                                  ┌─────────────┐

│  Authentication with Credential  │RATS-Unaware │

└──────────────────────────────────►Relying Party│

└────▲────────┘

RATS-Unaware │

Authentication │

Policy │

┌────┴────────┐

│RATS-Unaware │

│Relying Party│

│Owner        │

└─────────────┘

# Security Considerations

<fill in>

# IANA Considerations

<fill in>

contentLoaded(false, function() {
$('#quoted-265135467').on('show.bs.collapse', function() {
$('#qlabel-265135467').text("Hide quoted text");
})
$('#quoted-265135467').on('hide.bs.collapse', function() {
$('#qlabel-265135467').text("Show quoted text");
})
});
