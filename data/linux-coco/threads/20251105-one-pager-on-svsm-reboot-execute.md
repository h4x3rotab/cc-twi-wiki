---
title: 'One pager on SVSM_REBOOT_EXECUTE'
date: 2025-11-05
last_reply: 2025-11-12
message_count: 3
participants: ['Relph, Richard', 'Jörg Rödel']
---

## [1] Relph, Richard — 2025-11-05

In our 15-October-2025 Coconut SVSM meeting, I agreed to write up a one-pager describing the initial implementation of the SVSM Reboot Protocol.

I’ve attached Tom’s original 2-pager full specification for the protocol with modifications. The substantive change is to replace "Rebooting the guest will restore the guest state to match that of a newly booted guest.” With "Rebooting the guest invalidates memory pages that were validated by the guest and resets the CPU register state to their initial state. No other system state is modified.”

Richard

---

## [2] Jörg Rödel — 2025-11-12
*Subject: Re: One pager on SVSM_REBOOT_EXECUTE*

Hey Richard,

On Wed, Nov 05, 2025 at 05:32:58PM +0000, Relph, Richard wrote:
> In our 15-October-2025 Coconut SVSM meeting, I agreed to write up a one-pager
> describing the initial implementation of the SVSM Reboot Protocol.

Thanks for putting this together. I have two comments:

	1. The protocol needs a separate feature detection call so the guest
	   can determine which version of the reboot protocol is supported by the
	   SVSM.

	2. The call definition for SVSM_REBOOT_EXECUTE needs to specifically
	   define what state is reset with this call. My understanding is that
	   it only resets memory and CPU state, but explicitly not any service
	   state (like TPM).

Could you please add that to the specification?

Thanks,

	Joerg

---

## [3] Relph, Richard — 2025-11-12
*Subject: Re: One pager on SVSM_REBOOT_EXECUTE*

> On Nov 12, 2025, at 2:27 AM, Jörg Rödel <joro@8bytes.org> wrote:
> 

Joerg,
     The SVSM_CORE_QUERY_PROTOCOL Call provides version information about all protocols.

>        2. The call definition for SVSM_REBOOT_EXECUTE needs to specifically
>           define what state is reset with this call. My understanding is that

I believe what I wrote does exactly that… what more do you think is required?

"Rebooting the guest invalidates memory pages that were validated by the guest and resets the CPU register state to their initial state. No other system state is modified.”

Richard

> 
> Could you please add that to the specification?

---
