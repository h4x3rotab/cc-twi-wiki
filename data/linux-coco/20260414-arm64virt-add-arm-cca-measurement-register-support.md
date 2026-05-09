---
title: '[PATCH 0/3] arm64/virt: Add Arm CCA measurement register support'
date: 2026-04-14
last_reply: 2026-04-22
message_count: 6
participants: ['Suzuki K Poulose', 'Jason Gunthorpe', 'Sami Mujawar']
---

## [1] Suzuki K Poulose — 2026-04-14

Cc: Dan, Cedric, Dionna, Aneesh, Alexey. linux-coco

Hi Jason,

On 13/04/2026 13:59, Jason Gunthorpe wrote:
> On Mon, Apr 13, 2026 at 09:49:54AM +0100, Sami Mujawar wrote:
>> This series adds support for Arm Confidential Compute Architecture (CCA)

That is true. This is the infrastructure for exposing Runtime
Measurement registers (R/W) for use by the OS, complementing the
TSM_REPORTS (Read Only Platform measurements+Attestation Reports, e.g.
on CCA Attestation Report from RMM). Unlike the TSM reports,
this doesn't have a generic interface for userspace.


> I also think exposing PCRs as was done for TPM in sysfs was something
> of a mistake.. Allowing extension without logging is too low level and

Agreed, such a subsystem would solve the below.

>   - Discover available measurements
>   - Report signed measurements, with ingesting a nonce

That makes sense and AFAIU, there are efforts in progress to expose
the Device measurements+Certificates in a different form. May be a good
idea to intervene early enough to see if we can find a common ground.

> 
> Isn't this also sort of incomplete?  Doesn't anything serious need
As mentioned above, this series adds the support for Runtime Extendible
Measurements (REM in CCA, RTMR on TDX). The RIM+Platform Attestation is 
already provided via the TSM_REPORT


Kind regards
Suzuki

> 
> Jason

---

## [2] Jason Gunthorpe — 2026-04-14

On Tue, Apr 14, 2026 at 11:10:51AM +0100, Suzuki K Poulose wrote:

> > Isn't this also sort of incomplete?  Doesn't anything serious need
> > signed measurements? Isnt't there alot more data that comes out of RMM

Okay, but what actual use is this?

Extendable measrements with no log
Measurement read back without signature

What is the use case? What do you imagine any userspace will do with
this? Put it in the cover letter.

I don't think the raw rmm calls are sufficiently developed to be
usable directly by userspace. They are less capable than TPM and even
TPM has a lot of software around it to make it useful.

Jason

---

## [3] Suzuki K Poulose — 2026-04-14

On 14/04/2026 13:29, Jason Gunthorpe wrote:
> On Tue, Apr 14, 2026 at 11:10:51AM +0100, Suzuki K Poulose wrote:
> 

Good point. This REMs are planned to be used for 
EFI_CC_MEASUREMENT_PROTOCOL as described below:

https://github.com/tianocore/edk2/issues/11383

At the moment they are exposed as raw, similar to the Intel TDX RTMRs.
This may eventually need to be connected to IMA subsystem.

> Extendable measrements with no log
> Measurement read back without signature

Agreed.

> 
> I don't think the raw rmm calls are sufficiently developed to be

See above.

Kind regards
Suzuki

> 
> Jason

---

## [4] Jason Gunthorpe — 2026-04-14

On Tue, Apr 14, 2026 at 02:26:58PM +0100, Suzuki K Poulose wrote:
> On 14/04/2026 13:29, Jason Gunthorpe wrote:
> > On Tue, Apr 14, 2026 at 11:10:51AM +0100, Suzuki K Poulose wrote:

So this is tying it to the same FW event log that TPM uses.

I think that strengthens my point this should all be uninform. TPM
drivers are directly exposing the event log today, but I guess that
needs generalization if non-TPM drivers are going to present it as
well.

How do you imagine getting and manipulating the EFI event log to use
with this?

Jason

---

## [5] Sami Mujawar — 2026-04-22

Hi Jason,

> On Tue, Apr 14, 2026 at 02:26:58PM +0100, Suzuki K Poulose wrote:
> > On 14/04/2026 13:29, Jason Gunthorpe wrote:

The event logs from UEFI will be handed off to the OS using CCEL ACPI table. The CCEL table spec update can be seen at  https://github.com/tianocore/edk2/issues/11384 

Regards,

Sami Mujawar
> Jason
>

---

## [6] Jason Gunthorpe — 2026-04-22

On Wed, Apr 22, 2026 at 08:57:00AM +0000, Sami Mujawar wrote:

> > So this is tying it to the same FW event log that TPM uses.
> > 

I ment from linux userspace. event log is well establihsed in the aCPI
side for TPM and in Linux today it is only exposed to userspace
through TPM.

This is not TPM, so how do you intend to give the event log to
userspace?

Jason

---
