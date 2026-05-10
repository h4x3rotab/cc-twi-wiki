---
title: '[PATCH v8 13/43] arm64: RME: Support for the VGIC in realms'
date: 2025-05-12
last_reply: 2025-06-02
message_count: 34
participants: ['Steven Price', 'Suzuki K Poulose', 'Emi Kisanuki (Fujitsu)']
---

## [1] Steven Price — 2025-05-12

On 02/05/2025 12:04, Suzuki K Poulose wrote:
> On 16/04/2025 14:41, Steven Price wrote:
>> The RMM provides emulation of a VGIC to the realm guest but delegates

I'm not sure how I missed that. Note that the RMM spec restricts the
fields that the normal world is allowed to set. So I'll also add a new
define to rmi_smc.h to provide the bitmask:

#define RMI_PERMITTED_GICV3_HCR_BITS   (ICH_HCR_EL2_UIE |              \
                                        ICH_HCR_EL2_LRENPIE |          \
                                        ICH_HCR_EL2_NPIE |             \
                                        ICH_HCR_EL2_VGrp0EIE |         \
                                        ICH_HCR_EL2_VGrp0DIE |         \
                                        ICH_HCR_EL2_VGrp1EIE |         \
                                        ICH_HCR_EL2_VGrp1DIE |         \
                                        ICH_HCR_EL2_TDIR)

>> +
>>   static inline void vgic_save_state(struct kvm_vcpu *vcpu)

Ack. I think this was me getting confused during a rebase ;) I'll pull
out the "if (unlikely(vcpu_is_rec())" and return early.

Steve

> Rest looks good to me.
>

---

## [2] Steven Price — 2025-05-12
*Subject: Re: [PATCH v8 15/43] arm64: RME: Allow VMM to set RIPAS*

On 06/05/2025 14:23, Suzuki K Poulose wrote:
> Hi Steven
> 

I think what I should do is provide wrappers for the RTT functions and
move the kvm_account_pgtables_pages() to the wrappers. That would make
it more obvious which allocations are for RTTs and hopefully avoid
accounting errors.

>> +
>> +    return phys;

Ack

>> +
>> +    if (RMI_RETURN_STATUS(ret) == RMI_SUCCESS && rtt_granule)

We're holding the KVM mmu_lock (the only call path is
realm_unmap_private_range() > realm_unmap_private_page() >
realm_destroy_private_granule(). So we can't race with another thread
doing the same thing.

This situation happens when there's a block mapping, so we know there
can't be a racing thread faulting in other pages in the same RTT (as all
the base pages are already there). So AFAICT this should never happen
due to a race...

I may have missed something though ;)

I'm also a little wary of using rtt read because that in itself can be
racy (unless we're holding a suitable lock the situation can change
before/after the read).

>> +            free_delegated_granule(rtt);
>> +            return -ENXIO;

In this particular case the error is not RMI_ERROR_RTT, so the RTT
probably isn't particularly enlightening. But I agree the default
WARN_ON splat tends not to be informative, I'll take a look at if a
wrapper could help.

>> +        return -ENXIO;
>> +    }

Ack

>> +
>> +    return 0;

Ack

>> +            /* The RTT already exists, continue */
>> +            continue;

Yes, I've already got a local change adding a "may_block" flag to the
function so we can do a cond_resched_rwlock_write() call here when possible.

>> +    }
>> +

I'm not sure I follow: realm_fold_rtt_level() will free any RTTs that
are released.

Or are you referring to the fact that we don't (yet) fold the shared
range? I have been purposefully leaving that for now as normally we'd
follow the page size in the VMM to choose the page size on the guest,
but that doesn't work when the RMM might have a different page size to
the host. So my reasons for leaving it for later are:

 * First huge pages is very much a TODO in general.

 * When we support >4K host pages then a huge page on the host may not
   be available in the RMM, so we can't just follow the VMM.

 * We don't have support in realm_unmap_shared_range() to split a block
   mapping up - it could be added, but it's not clear to me if it's best
   to split a block mapping, or remove the whole and refault as
   required.

 * guest_memfd might well be able to provide some good hints here, but
   we'll have to wait for that series to settle.

>> +}
>> +

I have to admit I've struggled to get my head round this ;)

init_ripas will fail with ERROR_RTT in three cases:

 1. (base_align) The base address isn't aligned for the level reached.

 2. (rtt_state) The rtte state is !UNASSIGNED.

 3. (no_progress) base==walk_top - the while condition should prevent
    this.

So I think case 1 is the case we're expecting, and creating RTTs should
resolve it.

Case 2 is presumably the case you are concerned about, although it's not
because tables have been created, but because INIT_RIPAS is invalid on
areas that have been populated already.

If my reading of the spec is correct, then level == 3 isn't a possible
result, so beyond potentially finding RMM bugs I don't think a WARN for
that is very interesting. So for now I'll just drop the WARN_ON here
altogether.

Thanks,
Steve

> Suzuki
>

---

## [3] Steven Price — 2025-05-12
*Subject: Re: [PATCH v8 16/43] arm64: RME: Handle realm enter/exit*

On 30/04/2025 12:55, Gavin Shan wrote:
> On 4/16/25 11:41 PM, Steven Price wrote:
>> Entering a realm is done using a SMC call to the RMM. On exit the

Thanks

[...]

>> diff --git a/arch/arm64/kvm/rme-exit.c b/arch/arm64/kvm/rme-exit.c
>> new file mode 100644

I'm not sure the "always returns positive values" is a good
justification - that might change in the future (although I guess the
only reason it returns '1' is just to have the correct function
signature - so it's unlike to change).

However there isn't really any harm here in setting the 'enter' value
even if it fails. So I'll drop the "ret > 0" check.

Thanks,
Steve

---

## [4] Steven Price — 2025-05-12
*Subject: Re: [PATCH v8 16/43] arm64: RME: Handle realm enter/exit*

On 07/05/2025 11:26, Suzuki K Poulose wrote:
> On 16/04/2025 14:41, Steven Price wrote:
>> Entering a realm is done using a SMC call to the RMM. On exit the

I dropped the trace because we can't provide the PC value. I'm not sure
what's best here:

 (1). Provide kvm_exit trace but with a bogus PC.
 (2). Introduce a new 'kvm_rec_exit'.
 (3). Wait until someone comes along with a use-case and hope they
      implement what they need.

Obviously my preference is 3 ;)

In practice I haven't actually dropped kvm_entry (so that has a bogus
PC), so for now I guess I'll go with (1).

>>             preempt_enable();
>>   @@ -1345,7 +1351,10 @@ int kvm_arch_vcpu_ioctl_run(struct kvm_vcpu

Makes sense, will add.

Thanks,
Steve

> Rest looks fine to me.
>

---

## [5] Suzuki K Poulose — 2025-05-13
*Subject: Re: [PATCH v8 15/43] arm64: RME: Allow VMM to set RIPAS*

On 12/05/2025 15:45, Steven Price wrote:
> On 06/05/2025 14:23, Suzuki K Poulose wrote:
>> Hi Steven

I see, we shouldn't see a fault as the mappings are valid. Thanks for
the clarification.

> 
> I may have missed something though ;)

Very much true. But it at least gives you some chance of a debug.

> 
>>> +            free_delegated_granule(rtt);

...

>>>    void kvm_realm_destroy_rtts(struct kvm *kvm, u32 ia_bits)
>>>    {

Cool, thanks.

> 
>>> +    }

sorry it was a bit vague. We don't seem to be reclaiming the RTTs in
realm_unmap_shared_range(), like we do for the private range.


> follow the page size in the VMM to choose the page size on the guest,
> but that doesn't work when the RMM might have a different page size to

I am not sure I follow. None of this affects folding, once we have 
"unmapped". For that matter, we could easily DESTROY the RTTs in
shared side without unmapping, but we can do that later as an
optimisation.


> 
>>> +}

Correct, this is the case I was referring to.

> 
> If my reading of the spec is correct, then level == 3 isn't a possible

It is almost certainly possible, with L3 page mapping created for
POPULATE and a follow up INIT_RIPAS with 2M or even 1G alignment, could
lead us to expect that only L1 or L2 is required (find_map_level) but
the RTT walk reached L3 and failed. This is not a case of RMM bug, but
a VMM not following the rules.

> that is very interesting. So for now I'll just drop the WARN_ON here
> altogether.

Thanks, that is much safer

Suzuki

---

## [6] Steven Price — 2025-05-14
*Subject: Re: [PATCH v8 15/43] arm64: RME: Allow VMM to set RIPAS*

On 13/05/2025 11:43, Suzuki K Poulose wrote:
> On 12/05/2025 15:45, Steven Price wrote:
>> On 06/05/2025 14:23, Suzuki K Poulose wrote:

[...]

> 
>>

Ah, you mean we potentially leave empty RTTs which are only reclaimed
when destroying the realm. Whereas in the private range we
opportunistically fold which will (usually) cause these to be freed.

>> follow the page size in the VMM to choose the page size on the guest,
>> but that doesn't work when the RMM might have a different page size to

Yeah, ignore the above - like you say it's not relevant to unmapping, I
hadn't understood your point ;)

I'll stick a call to realm_fold_rtt_level() at the end of
realm_unmap_shared_range() which should opportunistically free unused
RTTs. Like you say there's a optimisation to just straight to destroying
the RTTs in the shared region - but I think that's best left until later.

>>
>>>> +}

Sorry, I wasn't clear. I mean "level == 3" isn't something that we
should be WARNing on.

>> that is very interesting. So for now I'll just drop the WARN_ON here
>> altogether.

Ack.

Thanks,
Steve

> Suzuki
>

---

## [7] Emi Kisanuki (Fujitsu) — 2025-05-15
*Subject: RE: [PATCH v8 00/43] arm64: Support for Arm CCA in KVM*

We tested this patch in our internal simulator which is a hardware simulator for Fujitsu's next generation CPU known as Monaka. and it produced the expected results.

I have verified the following
1. Launching the realm VM using Internal simulator → Successfully launched by disabling MPAM support in the ID register.
2. Running kvm-unit-tests (with lkvm) → All tests passed except for PMU (as expected, since PMU is not supported by the Internal simulator).[1]

Tested-by: Emi Kisanuki <fj0570is@fujitsu.com> [1] https://gitlab.arm.com/linux-arm/kvm-unit-tests-cca cca/v3

Best Regards,
Emi Kisanuki
> This series adds support for running protected VMs using KVM under the Arm
> Confidential Compute Architecture (CCA).

---

## [8] Steven Price — 2025-05-16
*Subject: Re: [PATCH v8 17/43] arm64: RME: Handle RMI_EXIT_RIPAS_CHANGE*

On 30/04/2025 13:11, Gavin Shan wrote:
> On 4/16/25 11:41 PM, Steven Price wrote:
>> The guest can request that a region of it's protected address space is

I believe it's just two functions: realm_set_ipa_state() and
realm_init_ipa_state(). Those two functions are going basically the same
thing just at different stages (realm_init before the guest has started,
and realm_set when it's running).

I've had a go and combing the two functions, it's a little clunky
because of the differences, but I think it's an improvement over the
repeated code.

Thanks,
Steve

>> +            break;
>> +        } else {

---

## [9] Steven Price — 2025-05-16
*Subject: Re: [PATCH v8 17/43] arm64: RME: Handle RMI_EXIT_RIPAS_CHANGE*

On 07/05/2025 11:42, Suzuki K Poulose wrote:
> On 16/04/2025 14:41, Steven Price wrote:
>> The guest can request that a region of it's protected address space is

I'm not really sure this is the right place, and following Gavin's
comment I've combined this with the INIT_RIPAS code.

Also the situation at the moment isn't that we return to the guest -
kvm_complete_ripas_change() will topup the memory cache and retry until
the whole region is covered. There is an argument that perhaps it
shouldn't, but I'm not sure what a guest can usefully do beyond retry in
the case of a partial RIPAS change. In which case why have the overhead
of returning to the guest?

>> +                if (!ret)
>> +                    continue;

Since I'm combining the two functions, I've kept just the switch()
version of the code.

>> +    }
>> +

Thanks,
Steve

---

## [10] Steven Price — 2025-05-16
*Subject: Re: [PATCH v8 20/43] arm64: RME: Runtime faulting of memory*

On 01/05/2025 01:16, Gavin Shan wrote:
> On 4/16/25 11:41 PM, Steven Price wrote:
>> At runtime if the realm guest accesses memory which hasn't yet been

Ack.

>>   void kvm_stage2_unmap_range(struct kvm_s2_mmu *mmu, phys_addr_t start,
>> @@ -359,7 +364,10 @@ static void stage2_flush_memslot(struct kvm *kvm,

Yes, that's probably neater. There's a WARN_ON() in
__unmap_stage2_range() otherwise I'd have just used a simple ~0ULL.

>>   @@ -1482,6 +1495,82 @@ static bool kvm_vma_mte_allowed(struct
>> vm_area_struct *vma)

Ack.

>> +
>> +    ipa = ALIGN_DOWN(ipa, PAGE_SIZE);

Fair enough.

>> +
>> +        /*

Ack

>> +    if (map_level < RMM_RTT_MAX_LEVEL) {
>> +        /*

I agree combining the WARN_ON()s makes sense. But the repeated ternary
operator just hides the map_level/map_size connection (and I'm not a big
fan of the ternary operator).

However, we do have rme_rtt_level_mapsize() which I can use to convert
the level to the size and avoid the second ternary.

>> +    for (offset = 0; offset < size; offset += map_size) {
>> +        /*

The spec is clear on what the RMM is permitted to return error codes, so
we're safe for any conforming implementation. And (hopefully) if new
error conditions are added we can ensure that they can be distinguished
from the existing conditions. Clearly we'd have to update the code to
support new spec features.

There's a cost with doing these hypercalls. I expect there will be a
strong desire in the near future for optimisations to reduce the number
of calls and we'll see spec changes to enable it. So I've tried to avoid
"doubling checking".

And if the mapping really doesn't exist then we'd simply expect another
fault from the guest when it retries the operation that caused the fault
in the first place. So the retry logic is there (albeit in a very
expensive form).

Of course if you've spotted a condition here that I haven't thought of
then please do let me know - these paths are quite tricky to reason
about and very difficult to get meaningful testing on.

Thanks,
Steve

>> +
>> +        ipa += map_size;

---

## [11] Steven Price — 2025-05-16
*Subject: Re: [PATCH v8 00/43] arm64: Support for Arm CCA in KVM*

Hi Emi,

On 15/05/2025 04:01, Emi Kisanuki (Fujitsu) wrote:
> We tested this patch in our internal simulator which is a hardware simulator for Fujitsu's next generation CPU known as Monaka. and it produced the expected results.
> 

Thanks for testing!

Regards,
Steve

> Best Regards,
> Emi Kisanuki

---

## [12] Steven Price — 2025-05-16
*Subject: Re: [PATCH v8 00/43] arm64: Support for Arm CCA in KVM*

Hi Gavin,

On 02/05/2025 01:46, Gavin Shan wrote:
> On 4/16/25 11:41 PM, Steven Price wrote:
> 

So I suspect this is because I didn't have a cond_resched_rwlock_write()
in here - which was (as you pointed out) because I hadn't propagated
"may_block" down. Finger's crossed this will be fixed with that change.

Thanks,
Steve

> [ 7816.401347]  kvm_realm_unmap_range+0x94/0xb0
> [ 7816.401894]  __unmap_stage2_range+0x70/0xa0

---

## [13] Suzuki K Poulose — 2025-05-19
*Subject: Re: [PATCH v8 20/43] arm64: RME: Runtime faulting of memory*

Hi Steven

On 16/04/2025 14:41, Steven Price wrote:
> At runtime if the realm guest accesses memory which hasn't yet been
> mapped then KVM needs to either populate the region or fault the guest.

Please find some comments below.

...

> diff --git a/arch/arm64/kvm/rme.c b/arch/arm64/kvm/rme.c
> index f6af3ea6ea8a..b6959cd17a6c 100644

minor nit : RMM_RTT_BLOCK_LEVEL

> +	else
> +		map_level = 3;

minor nit:  RMM_RTT_MAX_LEVEL ?

> +
> +	if (map_level < RMM_RTT_MAX_LEVEL) {

Same here, stick to the symbols than digits.

> +	} else {
> +		map_level = 3;

The function names seems to be obsolete, please fix.

> +		 * so for now we permit both read and write.
> +		 */

Could we hit the following case and end up in failure ?

* Initially a single page is shared and the S2 is mapped
* Later the Realm shares the entire L2 block and encounters a fault
   at a new IPA within the L2 block.

In this case, we may try to L2 mapping when there is a L3 mapping and
we could encounter (RMI_ERROR_RTT, 2).


> +			/* Create missing RTTs and retry */
> +			int level = RMI_RETURN_INDEX(ret);

So we should probably go down the rtt create step, with the following
check.

			if (level < map_level) {

> +
> +			ret = realm_create_rtt_levels(realm, ipa, level,


		} else {

Otherwise, may be we need to do some more hard work to fix it up.

1. If map_level == 3, something is terribly wrong or we raced with 
another thread ?

2. If map_level < 3 and we didn't race :

   a. Going one level down and creating the mappings there and then 
folding. But we could endup dealing with ERROR_RTT,3 as in (1).

   b. Easiest is to destroy the table at "map_level + 1" and retry the map.


Suzuki



> +		}
> +		/*

---

## [14] Suzuki K Poulose — 2025-05-19
*Subject: Re: [PATCH v8 21/43] KVM: arm64: Handle realm VCPU load*

On 16/04/2025 14:41, Steven Price wrote:
> When loading a realm VCPU much of the work is handled by the RMM so only
> some of the actions are required. Rearrange kvm_arch_vcpu_load()

I think we use the pkvm hook to skip to the nommu goto, to avoid
the VMID allocation and context flush.


>   	kvm_timer_vcpu_load(vcpu);
>   	kvm_vgic_load(vcpu);

We could also move thise pvtime to the bottom too ?

>   
> @@ -671,6 +667,15 @@ void kvm_arch_vcpu_load(struct kvm_vcpu *vcpu, int cpu)

With the above addressed:

Reviewed-by: Suzuki K Poulose <suzuki.poulose@arm.com>


>   	if (!cpumask_test_cpu(cpu, vcpu->kvm->arch.supported_cpus))
>   		vcpu_set_on_unsupported_cpu(vcpu);

---

## [15] Suzuki K Poulose — 2025-05-19
*Subject: Re: [PATCH v8 22/43] KVM: arm64: Validate register access for a Realm
 VM*

On 16/04/2025 14:41, Steven Price wrote:
> The RMM only allows setting the GPRS (x0-x30) and PC for a realm
> guest. Check this in kvm_arm_set_reg() so that the VMM can receive a

May be add :

	/* PC can only be set before the Realm is ACTIVATED */

Either ways:

Reviewed-by: Suzuki K Poulose <suzuki.poulose@arm.com>


> +	case KVM_REG_ARM_CORE_REG(regs.pc):
> +		return true;

---

## [16] Suzuki K Poulose — 2025-05-19
*Subject: Re: [PATCH v8 18/43] KVM: arm64: Handle realm MMIO emulation*

On 16/04/2025 14:41, Steven Price wrote:
> MMIO emulation for a realm cannot be done directly with the VM's
> registers as they are protected from the host. However, for emulatable

Reviewed-by: Suzuki K Poulose <suzuki.poulose@arm.com>

---

## [17] Suzuki K Poulose — 2025-05-20
*Subject: Re: [PATCH v8 33/43] arm64: RME: Hide KVM_CAP_READONLY_MEM for realm
 guests*

On 16/04/2025 14:41, Steven Price wrote:
> For protected memory read only isn't supported by the RMM. While it may
> be possible to support read only for unprotected memory, this isn't

minor nit: s/allowing the/allowing the unprotected/

> mappings to be made read only.
> 

Reviewed-by: Suzuki K Poulose <suzuki.poulose@arm.com>

> ---
> Changes since v7:

---

## [18] Suzuki K Poulose — 2025-05-20
*Subject: Re: [PATCH v8 34/43] arm64: RME: Propagate number of breakpoints and
 watchpoints to userspace*

On 16/04/2025 14:41, Steven Price wrote:
> From: Jean-Philippe Brucker <jean-philippe@linaro.org>
> 

Reviewed-by: Suzuki K Poulose <suzuki.poulose@arm.com>


> ---
>   arch/arm64/include/asm/kvm_rme.h |  2 ++

---

## [19] Suzuki K Poulose — 2025-05-20
*Subject: Re: [PATCH v8 35/43] arm64: RME: Set breakpoint parameters through
 SET_ONE_REG*

On 16/04/2025 14:41, Steven Price wrote:
> From: Jean-Philippe Brucker <jean-philippe@linaro.org>
> 

Reviewed-by: Suzuki K Poulose <suzuki.poulose@arm.com>

---

## [20] Suzuki K Poulose — 2025-05-20
*Subject: Re: [PATCH v8 36/43] arm64: RME: Initialize PMCR.N with number
 counter supported by RMM*

On 16/04/2025 14:41, Steven Price wrote:
> From: Jean-Philippe Brucker <jean-philippe@linaro.org>
> 

Reviewed-by: Suzuki K Poulose <suzuki.poulose@arm.com>

---

## [21] Suzuki K Poulose — 2025-05-20
*Subject: Re: [PATCH v8 37/43] arm64: RME: Propagate max SVE vector length from
 RMM*

On 16/04/2025 14:41, Steven Price wrote:
> From: Jean-Philippe Brucker <jean-philippe@linaro.org>
> 

Reviewed-by: Suzuki K Poulose <suzuki.poulose@arm.com>

---

## [22] Suzuki K Poulose — 2025-05-20
*Subject: Re: [PATCH v8 38/43] arm64: RME: Configure max SVE vector length for
 a Realm*

On 16/04/2025 14:42, Steven Price wrote:
> From: Jean-Philippe Brucker <jean-philippe@linaro.org>
> 

Reviewed-by: Suzuki K Poulose <suzuki.poulose@arm.com>

---

## [23] Suzuki K Poulose — 2025-05-20
*Subject: Re: [PATCH v8 43/43] KVM: arm64: Allow activating realms*

On 16/04/2025 14:42, Steven Price wrote:
> Add the ioctl to activate a realm and set the static branch to enable
> access to the realm functionality if the RMM is detected.

Reviewed-by: Suzuki K Poulose <suzuki.poulose@arm.com>

---

## [24] Suzuki K Poulose — 2025-05-20
*Subject: Re: [PATCH v8 40/43] arm64: RME: Provide accurate register list*

On 16/04/2025 14:42, Steven Price wrote:
> From: Jean-Philippe Brucker <jean-philippe@linaro.org>
> 

Reviewed-by: Suzuki K Poulose <suzuki.poulose@arm.com>

---

## [25] Suzuki K Poulose — 2025-05-20
*Subject: Re: [PATCH v8 30/43] arm64: RME: Prevent Device mappings for Realms*

On 16/04/2025 14:41, Steven Price wrote:
> Physical device assignment is not yet supported by the RMM, so it
> doesn't make much sense to allow device mappings within the realm.

Reviewed-by: Suzuki K Poulose <suzuki.poulose@arm.com>

---

## [26] Suzuki K Poulose — 2025-05-20
*Subject: Re: [PATCH v8 20/43] arm64: RME: Runtime faulting of memory*

On 16/05/2025 16:33, Steven Price wrote:
> On 01/05/2025 01:16, Gavin Shan wrote:
>> On 4/16/25 11:41 PM, Steven Price wrote:

I think this must be, given the end is excluding:
	   kvm_stage2_unmap_range(mmu, 0, BIT(realm->ia_bits), false);

BIT(realm->ia_bits - 1) only covers the protected half. The unprotected 
half spans  [ BIT(realm->ia_bits - 1), BIT(realm->ia_bits))

Suzuki

---

## [27] Suzuki K Poulose — 2025-05-20
*Subject: Re: [PATCH v8 20/43] arm64: RME: Runtime faulting of memory*

On 19/05/2025 18:35, Suzuki K Poulose wrote:
> Hi Steven
> 

>> +    } else {
>> +        map_level = 3;

Doh, it is in arch/arm64/kvm/mmu.c, please ignore this comment.

Suzuki

---

## [28] Suzuki K Poulose — 2025-05-20
*Subject: Re: [PATCH v8 29/43] arm64: RME: Always use 4k pages for realms*

On 16/04/2025 14:41, Steven Price wrote:
> Guest_memfd doesn't yet natively support huge pages, and there are
> currently difficulties for a VMM to manage huge pages efficiently so for

With comments from Gavin addressed,

Reviewed-by: Suzuki K Poulose <suzuki.poulose@arm.com>

> ---
> Changes since v7:

---

## [29] Steven Price — 2025-05-21
*Subject: Re: [PATCH v8 20/43] arm64: RME: Runtime faulting of memory*

On 20/05/2025 15:48, Suzuki K Poulose wrote:
> On 16/05/2025 16:33, Steven Price wrote:
>> On 01/05/2025 01:16, Gavin Shan wrote:

The kernel treats the two halves as aliasing. kvm_realm_unmap_range()
caps the end to min(BIT(realm->ia_bits - 1), end). So this wouldn't make
any difference.

This an unfortunate outcome of the memory slots describing both the
protected region (via guestmem_fd) and the shared region (via VMM maps).
So a single memslot describes two regions which leads to the kernel
treating those regions as aliasing for some purposes.

Thanks,
Steve

---

## [30] Steven Price — 2025-05-21
*Subject: Re: [PATCH v8 20/43] arm64: RME: Runtime faulting of memory*

On 19/05/2025 18:35, Suzuki K Poulose wrote:
> Hi Steven
> 

Ack

>> +
>> +    if (map_level < RMM_RTT_MAX_LEVEL) {

Ack

>> +    } else {
>> +        map_level = 3;

realm_map_ipa() is in arch/arm64/kvm/mmu.c and contains...

	/*
	 * Write permission is required for now even though it's possible to
	 * map unprotected pages (granules) as read-only. It's impossible to
	 * map protected pages (granules) as read-only.
	 */
	if (WARN_ON(!(prot & KVM_PGTABLE_PROT_W)))
		return -EFAULT;

...which is what this is referring to.
[And now I've read your follow up email ;) ]

>> +         * so for now we permit both read and write.
>> +         */

Ugh! You are of course correct, this is broken. It turns out this is all
irrelevant as things stand because we don't currently support anything
bigger than (host) PAGE_SIZE mappings (forced in user_mem_abort()).

Given this I'm very much tempted to just delete the code supporting
block mappings for now (just set map_level to RMM_RTT_MAX_LEVEL).

Longer term, I'm not sure what is the best approach, the options are:

1. Drop down and map the region at L3 (ignoring conflicting entries),
   followed by attempting to fold.

2. Destroy the table and directly map at L2.

Option 2 is clearly the most performant, but is potentially racy. In
particular I'm not 100% sure whether you could end up with another
thread attempting to map at L3 between the destroy and map, and
therefore recreating the table.

Thanks,
Steve

> 
>> +            /* Create missing RTTs and retry */

---

## [31] Steven Price — 2025-05-21
*Subject: Re: [PATCH v8 21/43] KVM: arm64: Handle realm VCPU load*

On 19/05/2025 18:48, Suzuki K Poulose wrote:
> On 16/04/2025 14:41, Steven Price wrote:
>> When loading a realm VCPU much of the work is handled by the RMM so only

Thanks, the suggestions above seem sensible, I'll make those changes.

Thanks,
Steve

> 
>

---

## [32] Emi Kisanuki (Fujitsu) — 2025-05-29
*Subject: RE: [PATCH v8 16/43] arm64: RME: Handle realm enter/exit*

Hello, I comment below.

> Subject: [PATCH v8 16/43] arm64: RME: Handle realm enter/exit
> 
Running kvm-unit-tests-cca selftest(smp) test in quick succession may trigger these conditions, resulting in the following error logs.
 Error: KVM exit reason: 0 ("KVM_EXIT_UNKNOWN")

Since KVM_EXIT_UNKNOWN is used when no specific exit reason applies, I think it would be better to make it identifiable as an error.
How about adding and setting a new ARM64 exit_reason value to indicate that the PSCI_SYSTEM_OFF request is conflicting with a running vcpu?

Best Regards,
Emi Kisanuki
> +
> +	if (rec_run_ret)

---

## [33] Steven Price — 2025-06-02
*Subject: Re: [PATCH v8 16/43] arm64: RME: Handle realm enter/exit*

On 29/05/2025 05:52, Emi Kisanuki (Fujitsu) wrote:
> Hello, I comment below.

Hi Emi,

>> Subject: [PATCH v8 16/43] arm64: RME: Handle realm enter/exit
>>

[..]

>> +/*
>> + * Return > 0 to return to guest, < 0 on error, 0 (and set exit_reason)

Aneesh pointed this out to me off-list. We agreed that KVM_EXIT_SHUTDOWN
was more appropriate here. I'll make the change for v9.

Thanks,
Steve

> Best Regards,
> Emi Kisanuki

---

## [34] Suzuki K Poulose — 2025-06-02
*Subject: Re: [PATCH v8 16/43] arm64: RME: Handle realm enter/exit*

On 02/06/2025 16:14, Steven Price wrote:
> On 29/05/2025 05:52, Emi Kisanuki (Fujitsu) wrote:
>> Hello, I comment below.

Sounds good to me

Cheers
Suzuki

---
