---
title: 'GHCB draft specification v2.04'
date: 2024-09-06
last_reply: 2024-11-08
message_count: 4
participants: ['Alexey Kardashevskiy', 'Carlos Bilbao']
---

## [1] Alexey Kardashevskiy — 2024-09-06

Hi!

Attached is a draft GHCB specification with updates for SEV-TIO, Secure 
AVIC guest APIC page, Debug Virtualization support.

Please take a look and reply with any feedback you may have. Thanks,


Changelog (copy from the pdf):
===
Revision 2.04 introduces support for SEV trusted IO (SEV-TIO). SEV-TIO 
allows for passing through trusted PCIe devices with TDISP support to 
SEV-SNP guests.
Revision 2.04 also introduces support for guest to notify hypervisor of 
a vCPU's Secure AVIC guest APIC backing page.

Document Additions:

Document the SEV-TIO Guest Request Protocol used to communicate the 
SEV-TIO device measurements, certificates and SPDM attestation reports 
to the guest and provide the guest with a means to enable the device 
functionality if it is determined that it can be trusted.

Document changes in hardware debug support in an SEV-ES guest.

Document the Secure AVIC vCPU APIC Backing Page Notification Protocol to 
communicate the GPA of the guest-owned vCPU's Secure AVIC backing page 
to the hypervisor.
===

---

## [2] Alexey Kardashevskiy — 2024-10-17
*Subject: Re: GHCB draft specification v2.04*

Hi!

Meanwhile there is another draft of v2.04, with a new GHCB MSR protocol 
function to allow the guest to request the GHCB GPA be unregistered.

Please take a look and reply with any feedback you may have.

Thanks,


On 6/9/24 00:25, Alexey Kardashevskiy wrote:
> Hi!
>

---

## [3] Alexey Kardashevskiy — 2024-11-08
*Subject: Re: GHCB draft specification v2.04*

Hi!

Meanwhile there is another minor update, please comment.

The update is "Registering a GHCB GPA automatically unregisters any 
currently registered GHCB GPA". Thanks,


On 17/10/24 22:40, Alexey Kardashevskiy wrote:
> Hi!
>

---

## [4] Carlos Bilbao — 2024-11-08
*Subject: Re: GHCB draft specification v2.04*

On 9/5/24 09:25, Alexey Kardashevskiy wrote:

> Hi!
>


Just silly feedback, but "AP (vCPU) creation from within the guest" sounds
fun! Thanks for sharing.


>
>

Best,

Carlos

---
