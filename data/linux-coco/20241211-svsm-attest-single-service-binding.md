---
title: 'SVSM attest single service binding'
date: 2024-12-11
last_reply: 2024-12-11
message_count: 2
participants: ['Dionna Amalie Glaze', 'James Bottomley']
---

## [1] Dionna Amalie Glaze — 2024-12-11

The attestation protocol has two different attestation methods. One is
a GUID table similar to that specified for an extended guest request
in the GHCB specification, and the other is "service specific" as
requested by the spec. Both formats are referred to as "service
manifest", which is unfortunate.

The REPORT_DATA for the VMPL0 attestation for both attestation methods
is SHA2-512(nonce || service manifest), so you can end up with
evidence that looks like SVSM_ATTEST_SERVICES with a single service in
the manifest when requesting a single service's manifest. There's no
tag between the two. There's no requirement that whatever is reported
in the service manifest under a single service's identifier is exactly
the content of the service manifest that would appear in the
attest_services. Even still, it's generally bad practice to hash raw
data. You should have a context string.

I would like to request a change to the specification to add context
tags in the REPORT_DATA, at least for attest_single_service, e.g.,
SHA2-512(nonce || "svsm service <uuid>" || service manifest)

A solution could just be to say single services shouldn't use GUID
tables as their own service manifests, but that's a bit brittle.

Thanks!

--
-Dionna Glaze, PhD, CISSP, CCSP (she/her)

---

## [2] James Bottomley — 2024-12-11
*Subject: Re: SVSM attest single service binding*

On Wed, 2024-12-11 at 10:20 -0800, Dionna Amalie Glaze wrote:
[...]
> I would like to request a change to the specification to add context
> tags in the REPORT_DATA, at least for attest_single_service, e.g.,

Another possibility is to define an end of report GUID which would have
a zero size entry and define that it should always appear last in the
manifest for all services attestation but should never appear in a
single service attestation.

Regards,

James

---
