---
title: '[PATCH v2 02/14] arm64: Detect if in a realm and set RIPAS RAM'
date: 2024-05-10
last_reply: 2024-07-08
message_count: 34
participants: ['Catalin Marinas', 'Suzuki K Poulose', 'Steven Price', 'Michael Kelley', 'Jason Gunthorpe', 'Itaru Kitayama']
---

## [1] Catalin Marinas — 2024-05-10

On Fri, Apr 12, 2024 at 09:42:01AM +0100, Steven Price wrote:
> diff --git a/arch/arm64/include/asm/rsi.h b/arch/arm64/include/asm/rsi.h
> new file mode 100644

You may want to update the year ;).

> + */
> +

Nitpick: we tend to use DECLARE_STATIC_KEY_FALSE(), it pairs with
DEFINE_STATIC_KEY_FALSE().

> +void arm64_setup_memory(void);
> +

Are these always fatal? BUG_ON() is frowned upon in general. The
alternative would be returning an error code from the function and maybe
printing a warning here (it seems that some people don't like WARN_ON
either but it's better than BUG_ON; could use a pr_err() instead). Also
if something's wrong with the RSI interface to mess up the return
values, it will be hard to debug just from those BUG_ON().

If there's no chance of continuing beyond the point, add a comment on
why we have a BUG_ON().

> diff --git a/arch/arm64/kernel/rsi.c b/arch/arm64/kernel/rsi.c
> new file mode 100644

Does this need to be made available to loadable modules?

> +
> +static bool rsi_version_matches(void)

I wonder whether rsi_get_version() is the right name (I know it was
introduced in the previous patch but the usage is here, hence my
comment). From the RMM spec, this looks more like an
rsi_request_version() to me.

TBH, the RMM spec around versioning doesn't fully make sense to me ;). I
assume people working on it had some good reasons around the lower
revision reporting in case of an error.

> +
> +	if (ret == SMCCC_RET_NOT_SUPPORTED)

The above check matches what the spec says but wouldn't it be clearer to
just check for ret == RSI_SUCCESS? It saves one having to read the spec
to figure out what lower revision actually means in the spec (not the
actual lowest supported but the highest while still lower than the
requested one _or_ equal to the higher revision if the lower is higher
than the requested one - if any of this makes sense to people ;), I'm
sure I missed some other combinations).

> +
> +	pr_info("RME: Using RSI version %lu.%lu\n",

I would give this function a better name, something to resemble the RSI
setup. Similarly for others like set_memory_range_protected/shared().
Some of the functions have 'rsi' in the name like arm64_rsi_init() but
others don't and at a first look they'd seem like some generic memory
setup on arm64, not RSI-specific.

> +{
> +	u64 i;

We have an accessor for rsi_present - is_realm_world(). Why not use
that?

> +
> +	/*

Does it need to be this early? It's fine for now but I wonder whether we
may have some early parameter at some point that could influence what we
do in the arm64_rsi_init(). I'd move it after or maybe even as part of
the arm64_setup_memory(), though I haven't read the following patches if
they update this function.

>  
>  	dynamic_scs_init();

This feels like a random placement. This function is about memblock
initialisation. You might as well put it in paging_init(), it could make
more sense there. But I'd rather keep it in setup_arch() immediately
after arm64_memblock_init().

---

## [2] Catalin Marinas — 2024-05-13
*Subject: Re: [PATCH v2 03/14] arm64: realm: Query IPA size from the RMM*

On Fri, Apr 12, 2024 at 09:42:02AM +0100, Steven Price wrote:
> diff --git a/arch/arm64/include/asm/pgtable-prot.h b/arch/arm64/include/asm/pgtable-prot.h
> index dd9ee67d1d87..15d8f0133af8 100644

Nit: what's with the double parenthesis here?

>  #define PTE_MAYBE_NG		(arm64_use_ng_mappings ? PTE_NG : 0)
>  #define PMD_MAYBE_NG		(arm64_use_ng_mappings ? PMD_SECT_NG : 0)

Another nit: use __aligned(PAGE_SIZE).

However, does the spec require this to be page-size aligned? The spec
says aligned to 0x1000 and that's not necessarily the kernel page size.
It also states that the RsiRealmConfig structure is 4096 and I did not
see this in the first patch, you only have 8 bytes in this structure.
Some future spec may write more data here overriding your other
variables in the data section.

So that's the wrong place to force the alignment. Just do this when you
define the actual structure in the first patch:

struct realm_config {
	union {
		unsigned long ipa_bits; /* Width of IPA in bits */
		u8 __pad[4096];
	};
} __aligned(4096);

and maybe with a comment on why the alignment and padding. You could
also have an unnamed struct around ipa_bits in case you want to add more
fields in the future (siginfo follows this pattern).

> +
> +unsigned long prot_ns_shared;

---

## [3] Catalin Marinas — 2024-05-13
*Subject: Re: [PATCH v2 06/14] arm64: Override set_fixmap_io*

On Fri, Apr 12, 2024 at 09:42:05AM +0100, Steven Price wrote:
> Override the set_fixmap_io to set shared permission for the host
> in case of a CC guest. For now we mark it shared unconditionally.
[...]
> +void set_fixmap_io(enum fixed_addresses idx, phys_addr_t phys)
> +{

I looked through the patches and could not find any place where this
function does anything different as per the commit log suggestion. Can
we just update FIXMAP_PAGE_IO for now until you have a clear use-case?

---

## [4] Catalin Marinas — 2024-05-13
*Subject: Re: [PATCH v2 07/14] arm64: Make the PHYS_MASK_SHIFT dynamic*

On Fri, Apr 12, 2024 at 09:42:06AM +0100, Steven Price wrote:
> diff --git a/arch/arm64/include/asm/kvm_arm.h b/arch/arm64/include/asm/kvm_arm.h
> index e01bb5ca13b7..9944aca348bd 100644

Why does this need to be changed? It's still a constant not dependent on
the new dynamic IPA size.

> diff --git a/arch/arm64/include/asm/pgtable-hwdef.h b/arch/arm64/include/asm/pgtable-hwdef.h
> index ef207a0d4f0d..90dc292bed5f 100644

I prefer to have MAX as suffix in those definitions, it matches other
places like TASK_SIZE_MAX, PHYS_ADDR_MAX (I know PHYS_MASK_MAX doesn't
roll off the tongue easily but very few people tend to read the kernel
aloud ;)).

---

## [5] Catalin Marinas — 2024-05-13
*Subject: Re: [PATCH v2 08/14] arm64: Enforce bounce buffers for realm DMA*

On Fri, Apr 12, 2024 at 09:42:07AM +0100, Steven Price wrote:
> diff --git a/arch/arm64/mm/init.c b/arch/arm64/mm/init.c
> index 786fd6ce5f17..01a2e3ce6921 100644

This series tends to add unnecessary brackets.

> +
> +	swiotlb |= is_realm_world();

I first thought we wouldn't need this, just passing 'true' further down
but I guess you want to avoid reducing the bounce buffer size when it's
only needed for kmalloc() bouncing.

>  
>  	if (IS_ENABLED(CONFIG_DMA_BOUNCE_UNALIGNED_KMALLOC) && !swiotlb) {

Just do this higher up and avoid calling is_realm_world() twice:

	unsigned int flags = SWIOTLB_VERBOSE;

	...

	if (is_realm_world()) {
		swiotlb = true;
		flags |= SWIOTLB_FORCE;
	}

	...

	swiotlb_init(swiotlb, flags);

---

## [6] Suzuki K Poulose — 2024-05-14

Hi Catalin,

On 10/05/2024 18:35, Catalin Marinas wrote:
> On Fri, Apr 12, 2024 at 09:42:01AM +0100, Steven Price wrote:
>> diff --git a/arch/arm64/include/asm/rsi.h b/arch/arm64/include/asm/rsi.h

This was written in 2023 ;-), hasn't changed much since, hence the year.

> 
>> + */

Agree

> 
>> +void arm64_setup_memory(void);

The BUG_ON was put in to stop the guest from running, when it detects
that it cannot transition a given IPA to a desired state. This could
happen manily if the Host described some address to the Guest and has
backed out from the promise.

However, thinking about this a little deeper, we could relax this a bit
and leave it to the "caller" to take an action. e.g.

1. If this fails for "Main memory" -> RIPAS_RAM transition, it is fatal.

2. If we are transitioning some random IPA to RIPAS_EMPTY (for setting 
up in-realm MMIO, which we do not support yet), it may be dealt with.

We could have other cases in the future where we support trusted I/O,
and a failure to transition is not end of the world, but simply refusing
to use a device for e.g.

That said, the current uses in the kernel are always fatal. So, the 
BUG_ON is justified as it stands. Happy to change either ways.

> 
> If there's no chance of continuing beyond the point, add a comment on

Yes, for e.g., TSM_CONFIG report for attestation framework.
Patch 14 in the list.

> 
>> +

Agree.

> 
> TBH, the RMM spec around versioning doesn't fully make sense to me ;). I

;-)

> 
>> +

Ack. I guess this was never changed since the spec update. I have 
requested a similar change for RMI_ABI_VERSION checks.

> to figure out what lower revision actually means in the spec (not the
> actual lowest supported but the highest while still lower than the

Ack. arm64_rsi_setup_memory() ? I agree, we should "rsi" fy the names.

> 
>> +{

We must do this before we setup the "earlycon", so that the console
is accessed using shared alias and that happens via parse_early_param() :-(.


> 
>>   

Makes sense. This was done to make sure we process all the memory
regions, as soon as they are identified.

Suzuki


>

---

## [7] Suzuki K Poulose — 2024-05-14
*Subject: Re: [PATCH v2 06/14] arm64: Override set_fixmap_io*

On 13/05/2024 17:14, Catalin Marinas wrote:
> On Fri, Apr 12, 2024 at 09:42:05AM +0100, Steven Price wrote:
>> Override the set_fixmap_io to set shared permission for the host

This gets used by the earlycon mapping. The commit description could be
made clear.

We may have to revisit this code to optionally apply the PROT_NS_SHARED
attribute, depending on whether this is a "protected MMIO" or not.


Suzuki

---

## [8] Catalin Marinas — 2024-05-14
*Subject: Re: [PATCH v2 09/14] arm64: Enable memory encrypt for Realms*

On Fri, Apr 12, 2024 at 09:42:08AM +0100, Steven Price wrote:
>  static int change_page_range(pte_t *ptep, unsigned long addr, void *data)
> @@ -41,6 +45,7 @@ static int change_page_range(pte_t *ptep, unsigned long addr, void *data)

Oh, this TODO is problematic, not sure we can do it safely. There are
some patches on the list to trap faults from other CPUs if they happen
to access the page when broken but so far we pushed back as complex and
at risk of getting the logic wrong.

From an architecture perspective, you are changing the output address
and D8.16.1 requires a break-before-make sequence (FEAT_BBM doesn't
help). So we either come up with a way to do BMM safely (stop_machine()
maybe if it's not too expensive or some way to guarantee no accesses to
this page while being changed) or we get the architecture clarified on
the possible side-effects here ("unpredictable" doesn't help).

>  }
> @@ -192,6 +197,43 @@ int set_direct_map_default_noflush(struct page *page)

Just return from this function if it's not a linear map address. No
point in corrupting other areas since __virt_to_phys() will get it
wrong.

> +	start = __virt_to_phys(addr);
> +	end = start + numpages * PAGE_SIZE;

Can someone summarise what the point of this protection bit is? The IPA
memory is marked as protected/unprotected already via the RSI call and
presumably the RMM disables/permits sharing with a non-secure hypervisor
accordingly irrespective of which alias the realm guest has the linear
mapping mapped to. What does it do with the top bit of the IPA? Is it
that the RMM will prevent (via Stage 2) access if the IPA does not match
the requested protection? IOW, it unmaps one or the other at Stage 2?

Also, the linear map is not the only one that points to this IPA. What
if this is a buffer mapped in user-space or remapped as non-cacheable
(upgraded to cacheable via FWB) in the kernel, the code above does not
(and cannot) change the user mappings.

It needs some digging into dma_direct_alloc() as well, it uses a
pgprot_decrypted() but that's not implemented by your patches. Not sure
it helps, it looks like the remap path in this function does not have a
dma_set_decrypted() call (or maybe I missed it).

---

## [9] Catalin Marinas — 2024-05-15
*Subject: Re: [PATCH v2 10/14] arm64: Force device mappings to be non-secure
 shared*

On Fri, Apr 12, 2024 at 09:42:09AM +0100, Steven Price wrote:
> From: Suzuki K Poulose <suzuki.poulose@arm.com>
> 

You say "currently". What's the plan when the device is not emulated?
How would the guest distinguish what's emulated and what's not to avoid
setting the PROT_NS_SHARED bit?

> Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
> Signed-off-by: Steven Price <steven.price@arm.com>

This pgprot_device() is not the only one used to map device resources.
pgprot_writecombine() is another commonly macro. It feels like a hack to
plug one but not the other and without any way for the guest to figure
out what's emulated.

Can the DT actually place those emulated ranges in the higher IPA space
so that we avoid randomly adding this attribute for devices?

---

## [10] Suzuki K Poulose — 2024-05-15
*Subject: Re: [PATCH v2 09/14] arm64: Enable memory encrypt for Realms*

On 14/05/2024 19:00, Catalin Marinas wrote:
> On Fri, Apr 12, 2024 at 09:42:08AM +0100, Steven Price wrote:
>>   static int change_page_range(pte_t *ptep, unsigned long addr, void *data)

Thanks, we need to sort this out.


> 
>>   }

The Realm's IPA space is split in half. The lower half is "protected"
and all pages backing the "protected" IPA is in the Realm world and
thus cannot be shared with the hypervisor. The upper half IPA is
"unprotected" (backed by Non-secure PAS pages) and can be accessed
by the Host/hyp.

The RSI call (RSI_IPA_STATE_SET) doesn't make an IPA unprotected. It
simply "invalidates" a (protected) IPA to "EMPTY" implying the Realm 
doesn't intend to use the "ipa" as RAM anymore and any access to it from
the Realm would trigger an SEA into the Realm. The RSI call triggers an 
exit to the host with the information and is a hint to the hypervisor to 
reclaim the page backing the IPA.

Now, given we need dynamic "sharing" of pages (instead of a dedicated
set of shared pages), "aliasing" of an IPA gives us shared pages.
i.e., If OS wants to share a page "x" (protected IPA) with the host,
we mark that as EMPTY via RSI call and then access the "x" with top-bit
set (aliasing the IPA x). This fault allows the hyp to map the page 
backing IPA "x" as "unprotected" at ALIAS(x) address.

Thus we treat the "top" bit as an attribute in the Realm.

> 
> Also, the linear map is not the only one that points to this IPA. What

Good point. Will take a look.

Suzuki

---

## [11] Suzuki K Poulose — 2024-05-15
*Subject: Re: [PATCH v2 10/14] arm64: Force device mappings to be non-secure
 shared*

On 15/05/2024 10:01, Catalin Marinas wrote:
> On Fri, Apr 12, 2024 at 09:42:09AM +0100, Steven Price wrote:
>> From: Suzuki K Poulose <suzuki.poulose@arm.com>

Arm CCA plans to add support for passing through real devices,
which support PCI-TDISP protocol. This would involve the Realm
authenticating the device and explicitly requesting "protected"
mapping *after* the verification (with the help of RMM).




> 
>> Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>

Agree. I have been exploring hooking this into ioremap_prot() where we
could apply the attribute accordingly. We will change it in the next 
version.

> 
> Can the DT actually place those emulated ranges in the higher IPA space

It can, but then we kind of break the "Realm" view of the IPA space. 
i.e., right now it only knows about the "lower IPA" half and uses the 
top bit as a protection attr to access the IPA as shared.

Expanding IPA size view kind of breaks "sharing memory", where, we
must "use a different PA" for a page that is now shared.

Suzuki

---

## [12] Catalin Marinas — 2024-05-15
*Subject: Re: [PATCH v2 12/14] arm64: realm: Support nonsecure ITS emulation
 shared*

On Fri, Apr 12, 2024 at 09:42:11AM +0100, Steven Price wrote:
> @@ -198,6 +201,33 @@ static DEFINE_IDA(its_vpeid_ida);
>  #define gic_data_rdist_rd_base()	(gic_data_rdist()->rd_base)

I think you can just call alloc_pages_node() in both cases. This
function takes care of the NUMA_NO_NODE case itself.

> +
> +	if (page)

More of a nitpick on the naming: Are these functions used by the host as
well? The 'shared' part of the name does not make much sense, so maybe
just call them its_alloc_page() etc.

> @@ -3432,7 +3468,16 @@ static struct its_device *its_create_device(struct its_node *its, u32 dev_id,
>  	nr_ites = max(2, nvecs);

How much do we waste by going for a full page always if this is going to
be used on the host?

> +	if (!page)
> +		return NULL;

page_address() has the void * type already.

---

## [13] Catalin Marinas — 2024-05-15
*Subject: Re: [PATCH v2 13/14] arm64: rsi: Interfaces to query attestation
 token*

On Fri, Apr 12, 2024 at 09:42:12AM +0100, Steven Price wrote:
> diff --git a/arch/arm64/include/asm/rsi_cmds.h b/arch/arm64/include/asm/rsi_cmds.h
> index b4cbeafa2f41..c1850aefe54e 100644

The name is too generic and it goes into a header file. Also maybe move
it to rsi.h, and use it for other definitions like rsi_config struct
size and alignment.

---

## [14] Steven Price — 2024-05-15

On 10/05/2024 18:35, Catalin Marinas wrote:
> On Fri, Apr 12, 2024 at 09:42:01AM +0100, Steven Price wrote:
>> diff --git a/arch/arm64/include/asm/rsi.h b/arch/arm64/include/asm/rsi.h

Noted! ;)

>> + */
>> +

Makes sense.

>> +void arm64_setup_memory(void);
>> +

I think you're right, these shouldn't be (immediately) fatal - if this
is a change happening at runtime it might be possible to handle it.
However, at boot time it makes no sense to try to continue (which is
what I was originally looking at when this was written) as the
environment isn't what the guest is expecting, and continuing will
either lead to a later crash, attestation failure, or potential exploit
if the guest can be somehow be tricked to use the shared mapping rather
than the protected one.

I'll update the set_memory_range...() functions to return an error code
and push the boot BUG_ON up the chain (with a comment). But this is
still in the "should never happen" situation so I'll leave a WARN_ON here.

>> diff --git a/arch/arm64/kernel/rsi.c b/arch/arm64/kernel/rsi.c
>> new file mode 100644

It's used by drivers/virt/coco/arm-cca-guest/arm-cca-guest.c (through
is_realm_world()) which can be built as a module - see patch 14.

>> +
>> +static bool rsi_version_matches(void)

There's been a fair bit of discussion around versioning. Currently the
RMM implementation is very much a "get version" function. The issue was
what happens if in the future there is an incompatible RMM spec (i.e.
v2.0). The intention is that old OSes will provide the older version
number and give the RMM the opportunity to 'emulate' it. Equally where
the OS supports multiple versions then there's a need to negotiate a
commonly accepted version.

In terms of naming - mostly I've tried to just follow the spec, but the
naming in the spec isn't great. Calling the function rsi_version() would
be confusing so a verb is needed, but I'm not hung up on the verb. I'll
change it to rsi_request_version().

>> +
>> +	if (ret == SMCCC_RET_NOT_SUPPORTED)

Indeed - I got similar feedback on the RMI side. The spec evolved and I
forgot to update it. It should be sufficient (for now) to just look for
RSI_SUCCESS. Only when we start supporting multiple versions (on the
Linux side) do we need to look at the returned version numbers.

>> +
>> +	pr_info("RME: Using RSI version %lu.%lu\n",

Ack.

>> +{
>> +	u64 i;

Will change.

>> +
>> +	/*

As Suzuki said - it's needed for "earlycon" to work - I'll put a comment
in explaining.

>>  
>>  	dynamic_scs_init();

Will move.

Thanks,

Steve

---

## [15] Catalin Marinas — 2024-05-16
*Subject: Re: [PATCH v2 09/14] arm64: Enable memory encrypt for Realms*

On Wed, May 15, 2024 at 11:47:02AM +0100, Suzuki K Poulose wrote:
> On 14/05/2024 19:00, Catalin Marinas wrote:
> > On Fri, Apr 12, 2024 at 09:42:08AM +0100, Steven Price wrote:

What about emulated device I/O where there's no backing RAM at an IPA.
Does it need to have the top bit set?

> The RSI call (RSI_IPA_STATE_SET) doesn't make an IPA unprotected. It
> simply "invalidates" a (protected) IPA to "EMPTY" implying the Realm doesn't

Does the RMM sanity-checks that the NS hyp mappings are protected or
unprotected depending on the IPA range?

I assume that's also the case if the NS hyp is the first one to access a
page before the realm (e.g. inbound virtio transfer; no page allocated
yet because of a realm access).

---

## [16] Suzuki K Poulose — 2024-05-16
*Subject: Re: [PATCH v2 09/14] arm64: Enable memory encrypt for Realms*

Hi Catalin

On 16/05/2024 08:48, Catalin Marinas wrote:
> On Wed, May 15, 2024 at 11:47:02AM +0100, Suzuki K Poulose wrote:
>> On 14/05/2024 19:00, Catalin Marinas wrote:

The behaviour depends on the IPA (i.e, protected vs unprotected).

1. Unprotected : All stage2 faults in the Unprotected half are serviced
by the Host, including the areas that may be "Memory" backed. RMM 
doesn't provide any guarantees on accesses to the unprotected half. 
i.e., host could even inject a Synchronous External abort, if an MMIO
region is not understood by it.

2. Protected : The behaviour depends on the "IPA State" (only applicable 
for the protected IPAs). The possible states are RIPAS_RAM,  RIPAS_EMPTY 
and RIPAS_DESTROYED(not visible for the Realm).

The default IPA state is RIPAS_EMPTY for all IPA and the state is 
controlled by Realm with the help of RMM (serviced by Host), except
during the Realm initialisation. i.e., the Host is allowed to "mark"
some IPAs as RIPAS_RAM (for e.g., initial images loaded into the Realm)
during Realm initiliasation (via RMI_RTT_INIT_RIPAS), which gets
measured by the RMM (and affects the Realm Initial Measurement). After
the Realm is activated, the Host can only perform the changes requested
by the Realm (RMM monitors this). Hence, the Realm at boot up, marks all
of its "Described RAM" areas as RIPAS_RAM (via RSI_IPA_STATE_SET), so
that it can go ahead and acccess the RAM as normal.


a) RIPAS_EMPTY: Any access to an IPA in RIPAS_EMPTY generates a 
Synchronous External Abort back to the Realm. (In the future, this may
be serviced by another entity in the Realm).

b) RIPAS_RAM: A stage2 fault at a mapped entry triggers a Realm Exit to 
the Host (except Instruction Aborts) and the host is allowed to map a
page (that is "scrubbed" by RMM) at stage2 and continue the execution.

[ ---->8  You may skip this ---
  c) RIPAS_DESTROYED: An IPA is turned to RIPAS_DESTROYED, if the host
     "unmaps" a protected IPA in RIPAS_RAM (via RMI_DATA_DESTROY). This
     implies that the Realm contents were destroyed with no way of
     restoring back. Any access to such IPA from the Realm also causes
     a Realm EXIT, however, the Host is not allowed to map anything back
     there and thus the vCPU cannot proceed with the execution.
----<8----
]

> 
>> The RSI call (RSI_IPA_STATE_SET) doesn't make an IPA unprotected. It

RMM moderates the mappings in the protected half (as mentioned above).
Any mapping in the unprotected half is not monitored. The host is
allowed unmap, remap with anything in the unprotected half.

> 
> I assume that's also the case if the NS hyp is the first one to access a

Correct. The host need not map anything upfront in the Unprotected half
as it is allowed to map a page "with contents" at any time. A stage2 
fault can be serviced by the host to load a page with contents.

Suzuki

---

## [17] Catalin Marinas — 2024-05-16

On Tue, May 14, 2024 at 11:18:13AM +0100, Suzuki K Poulose wrote:
> On 10/05/2024 18:35, Catalin Marinas wrote:
> > On Fri, Apr 12, 2024 at 09:42:01AM +0100, Steven Price wrote:

This should work. We also have rsi_*() functions without any 'arm64' but
those are strictly about communicating with the RMM, so that's fine.

> > > @@ -293,6 +294,8 @@ void __init __no_sanitize_address setup_arch(char **cmdline_p)
> > >   	 * cpufeature code and early parameters.

Ah, ok, makes sense.

---

## [18] Steven Price — 2024-05-16
*Subject: Re: [PATCH v2 03/14] arm64: realm: Query IPA size from the RMM*

On 13/05/2024 15:03, Catalin Marinas wrote:
> On Fri, Apr 12, 2024 at 09:42:02AM +0100, Steven Price wrote:
>> diff --git a/arch/arm64/include/asm/pgtable-prot.h b/arch/arm64/include/asm/pgtable-prot.h

No idea - I'll remove a set!

>>  #define PTE_MAYBE_NG		(arm64_use_ng_mappings ? PTE_NG : 0)
>>  #define PMD_MAYBE_NG		(arm64_use_ng_mappings ? PMD_SECT_NG : 0)

Good suggestion - I'll update this. It turns out struct realm_config is
already missing "hash_algo" (not that we use it yet), so I'll add that too.

Thanks,

Steve

>> +
>> +unsigned long prot_ns_shared;

---

## [19] Steven Price — 2024-05-16
*Subject: Re: [PATCH v2 07/14] arm64: Make the PHYS_MASK_SHIFT dynamic*

On 13/05/2024 17:38, Catalin Marinas wrote:
> On Fri, Apr 12, 2024 at 09:42:06AM +0100, Steven Price wrote:
>> diff --git a/arch/arm64/include/asm/kvm_arm.h b/arch/arm64/include/asm/kvm_arm.h

Good question - this appears to be a rebase error. Since commit
a0d37784bfd7 ("KVM: arm64: Fix PAR_TO_HPFAR() to work independently of
PA_BITS.") this macro no longer uses PHYS_MASK_SHIFT. Previously the
change was to just to keep this uses the new 'MAX' constant.

>> diff --git a/arch/arm64/include/asm/pgtable-hwdef.h b/arch/arm64/include/asm/pgtable-hwdef.h
>> index ef207a0d4f0d..90dc292bed5f 100644

I could rename, but actually given the above rebasing errors it appears
these are actually no longer needed, so I'll just drop the MAX_xxx
definitions.

Thanks,

Steve

---

## [20] Catalin Marinas — 2024-05-17
*Subject: Re: [PATCH v2 10/14] arm64: Force device mappings to be non-secure
 shared*

On Wed, May 15, 2024 at 12:00:49PM +0100, Suzuki K Poulose wrote:
> On 15/05/2024 10:01, Catalin Marinas wrote:
> > On Fri, Apr 12, 2024 at 09:42:09AM +0100, Steven Price wrote:

I'd have to do some reading, no clue how this works.

> > > diff --git a/arch/arm64/include/asm/pgtable.h b/arch/arm64/include/asm/pgtable.h
> > > index f5376bd567a1..db71c564ec21 100644

pgprot_* at least has the advantage that it covers other places.
ioremap_prot() would handle the kernel mappings but you have devices
mapped in user-space via remap_pfn_range() for example. The protection
bits may come from dma_pgprot() with either write-combine or cacheable
attributes. One may map device I/O as well (not sure what DPDK does). We
could restrict those to protected devices but we need to go through the
use-cases.

All this needs some thinking, especially if at some point we'll have
protected devices. Just hijacking the low-level pgprot macros doesn't
feel like a great approach.

> > Can the DT actually place those emulated ranges in the higher IPA space
> > so that we avoid randomly adding this attribute for devices?

True, I did not realise that the IPA split is transparent to the host.

An option would be additional DT/ACPI attributes for those devices.
That's not great either though as we can't handle those attributes in
the arch code only and probably we don't want to change generic drivers.

Yet another option would be to query the RMM somehow.

---

## [21] Catalin Marinas — 2024-05-20
*Subject: Re: [PATCH v2 09/14] arm64: Enable memory encrypt for Realms*

On Wed, May 15, 2024 at 11:47:02AM +0100, Suzuki K Poulose wrote:
> On 14/05/2024 19:00, Catalin Marinas wrote:
> > On Fri, Apr 12, 2024 at 09:42:08AM +0100, Steven Price wrote:

Thanks for the clarification on RIPAS states and behaviour in one of
your replies. Thinking about this, since the page is marked as
RIPAS_EMPTY prior to changing the PTE, the address is going to fault
anyway as SEA if accessed. So actually breaking the PTE, TLBI, setting
the new PTE would not add any new behaviour. Of course, this assumes
that set_memory_decrypted() is never called on memory being currently
accessed (can we guarantee this?).

So, we need to make sure that there is no access to the linear map
between set_memory_range_shared() and the actual pte update with
__change_memory_common() in set_memory_decrypted(). At a quick look,
this seems to be the case (ignoring memory scrubbers, though dummy ones
just accessing memory are not safe anyway and unlikely to run in a
guest).

(I did come across the hv_uio_probe() which, if I read correctly, it
ends up calling set_memory_decrypted() with a vmalloc() address; let's
pretend this code doesn't exist ;))

---

## [22] Michael Kelley — 2024-05-20
*Subject: RE: [PATCH v2 09/14] arm64: Enable memory encrypt for Realms*

From: Catalin Marinas <catalin.marinas@arm.com> Sent: Monday, May 20, 2024 9:53 AM
> 
> On Wed, May 15, 2024 at 11:47:02AM +0100, Suzuki K Poulose wrote:

While I worked on CoCo VM support on Hyper-V for x86 -- both AMD
SEV-SNP and Intel TDX, I haven't ramped up on the ARM64 CoCo
VM architecture yet.  With that caveat in mind, the assumption is that callers
of set_memory_decrypted() and set_memory_encrypted() ensure that
the target memory isn't currently being accessed.   But there's a big
exception:  load_unaligned_zeropad() can generate accesses that the
caller can't control.  If load_unaligned_zeropad() touches a page that is
in transition between decrypted and encrypted, a SEV-SNP or TDX architectural
fault could occur.  On x86, those fault handlers detect this case, and
fix things up.  The Hyper-V case requires a different approach, and marks
the PTEs as "not present" before initiating a transition between decrypted
and encrypted, and marks the PTEs "present" again after the transition.
This approach causes a reference generated by load_unaligned_zeropad() 
to take the normal page fault route, and use the page-fault-based fixup for
load_unaligned_zeropad(). See commit 0f34d11234868 for the Hyper-V case.

> 
> So, we need to make sure that there is no access to the linear map

While the Hyper-V UIO driver is perhaps a bit of an outlier, the Hyper-V
netvsc driver also does set_memory_decrypted() on 16 Mbyte vmalloc()
allocations, and there's not really a viable way to avoid this. The
SEV-SNP and TDX code handles this case.   Support for this case will
probably also be needed for CoCo guests on Hyper-V on ARM64.

Michael

---

## [23] Catalin Marinas — 2024-05-21
*Subject: Re: [PATCH v2 09/14] arm64: Enable memory encrypt for Realms*

On Mon, May 20, 2024 at 08:32:43PM +0000, Michael Kelley wrote:
> From: Catalin Marinas <catalin.marinas@arm.com> Sent: Monday, May 20, 2024 9:53 AM
> > > > On Fri, Apr 12, 2024 at 09:42:08AM +0100, Steven Price wrote:
[...]
> > Thanks for the clarification on RIPAS states and behaviour in one of
> > your replies. Thinking about this, since the page is marked as

Thanks. The load_unaligned_zeropad() case is a good point. I thought
we'd get away with this on arm64 since accessing such decrypted page
would trigger a synchronous exception but looking at the code, the
do_sea() path never calls fixup_exception(), so we just kill the whole
kernel.

> This approach causes a reference generated by load_unaligned_zeropad() 
> to take the normal page fault route, and use the page-fault-based fixup for

I think for arm64 set_memory_decrypted() (and encrypted) would have to
first make the PTE invalid, TLBI, set the RIPAS_EMPTY state, set the new
PTE. Any page fault due to invalid PTE would be handled by the exception
fixup in load_unaligned_zeropad(). This way we wouldn't get any
synchronous external abort (SEA) in standard uses. Not sure we need to
do anything hyper-v specific as in the commit above.

> > (I did come across the hv_uio_probe() which, if I read correctly, it
> > ends up calling set_memory_decrypted() with a vmalloc() address; let's

Ah, I was hoping we can ignore it. So the arm64 set_memory_*() code will
have to detect and change both the vmalloc map and the linear map.
Currently this patchset assumes the latter only.

Such buffers may end up in user space as well but I think at the
set_memory_decrypted() call there aren't any such mappings and
subsequent remap_pfn_range() etc. would handle the permissions properly
through the vma->vm_page_prot attributes (assuming that someone set
those pgprot attributes).

---

## [24] Michael Kelley — 2024-05-21
*Subject: RE: [PATCH v2 09/14] arm64: Enable memory encrypt for Realms*

From: Catalin Marinas <catalin.marinas@arm.com>Sent: Tuesday, May 21, 2024 3:14 AM
> 
> On Mon, May 20, 2024 at 08:32:43PM +0000, Michael Kelley wrote:

Sounds good to me. I tried to do the same for all the x86 cases (instead of
just handling the Hyper-V paravisor), since that would completely decouple
TDX/SEV-SNP from load_unaligned_zeropad(). It worked for TDX. But
SEV-SNP does the PVALIDATE instruction during a decrypted<->encrypted
transition, and PVALIDATE inconveniently requires the virtual address as
input. It only uses the vaddr to translate to the paddr, but with the vaddr
PTE "not present", PVALIDATE fails. Sigh. This problem will probably come
back again when/if Coconut or any other paravisor redirects #VC/#VE to
the paravisor. But I disgress ....

> 
> > > (I did come across the hv_uio_probe() which, if I read correctly, it

Yep.

> Currently this patchset assumes the latter only.
> 

Yes, I'm pretty sure that's what we've seen on the x86 side.

Michael

---

## [25] Steven Price — 2024-05-22
*Subject: Re: [PATCH v2 12/14] arm64: realm: Support nonsecure ITS emulation
 shared*

On 15/05/2024 12:01, Catalin Marinas wrote:
> On Fri, Apr 12, 2024 at 09:42:11AM +0100, Steven Price wrote:
>> @@ -198,6 +201,33 @@ static DEFINE_IDA(its_vpeid_ida);

Yes, the host is emulating this so the pages need to be in the shared
region. However this is only for realms, for a normal guest this
functions obviously aren't "sharing" with anything - so perhaps dropping
the 'shared' part makes sense.

>> @@ -3432,7 +3468,16 @@ static struct its_device *its_create_device(struct its_node *its, u32 dev_id,
>>  	nr_ites = max(2, nvecs);

sz is a minimum of ITS_ITT_ALIGN*2-1 - which is 511 bytes. So
potentially PAGE_SIZE-512 bytes could be wasted here (minus kmalloc
overhead).

>> +	if (!page)
>> +		return NULL;

Indeed, the cast is pointless. I'll remove.

Thanks,

Steve

---

## [26] Steven Price — 2024-05-22
*Subject: Re: [PATCH v2 13/14] arm64: rsi: Interfaces to query attestation
 token*

On 15/05/2024 12:10, Catalin Marinas wrote:
> On Fri, Apr 12, 2024 at 09:42:12AM +0100, Steven Price wrote:
>> diff --git a/arch/arm64/include/asm/rsi_cmds.h b/arch/arm64/include/asm/rsi_cmds.h

The realm config structure although it 'happens to be' granule sized
isn't really required to be - so I think it would be a bit confusing to
specify that.

There are only two other interfaces that require this:
 * RSI_IPA_STATE_GET - completely unused so far
 * RSI_ATTESTATION_TOKEN_CONTINUE - the buffer has to be contained with
   a granule, so it affects the maximum length per operation.

I'll rename to RSI_GRANULE_{SHIFT,SIZE}, but I'm not sure it really
belongs in rsi.h because none of that functionality cares about the
granule size (indeed the driver in the following patch doesn't include
rsi.h).

Thanks,
Steve

---

## [27] Catalin Marinas — 2024-05-22
*Subject: Re: [PATCH v2 12/14] arm64: realm: Support nonsecure ITS emulation
 shared*

On Wed, May 22, 2024 at 04:52:45PM +0100, Steven Price wrote:
> On 15/05/2024 12:01, Catalin Marinas wrote:
> > On Fri, Apr 12, 2024 at 09:42:11AM +0100, Steven Price wrote:

That I figured out as well but how many times is this path called with a
size smaller than a page?

---

## [28] Steven Price — 2024-05-23
*Subject: Re: [PATCH v2 12/14] arm64: realm: Support nonsecure ITS emulation
 shared*

On 22/05/2024 18:05, Catalin Marinas wrote:
> On Wed, May 22, 2024 at 04:52:45PM +0100, Steven Price wrote:
>> On 15/05/2024 12:01, Catalin Marinas wrote:

That presumably depends on the number of devices in the guest. For my
test guest setup (using kvmtool) this is called 3 times each with sz=511.

Steve

---

## [29] Steven Price — 2024-05-31
*Subject: Re: [PATCH v2 21/43] arm64: RME: Runtime faulting of memory*

On 25/04/2024 11:43, Fuad Tabba wrote:
> Hi,

Hi,

Thanks for the review. Sorry I didn't respond earlier.

> On Fri, Apr 12, 2024 at 9:44 AM Steven Price <steven.price@arm.com> wrote:
>>
<snip>
>> +static int private_memslot_fault(struct kvm_vcpu *vcpu,
>> +                                phys_addr_t fault_ipa,

Ah, good point - that simplifies things.

> I am also confused about the return, why do you return 1 regardless of
> the reason kvm_gmem_get_pfn() fails?

Thinking about this, I don't think we actually expect kvm_gmem_get_pfn()
to fail, so it's actually more appropriate to just pass return any error
value.

>> +       ret = kvm_mmu_topup_memory_cache(memcache,
>> +                                        kvm_mmu_cache_min_pages(vcpu->arch.hw_mmu));

Good point, however...

>> +       /* FIXME: Should be able to use bigger than PAGE_SIZE mappings */
>> +       ret = realm_map_ipa(kvm, fault_ipa, pfn, PAGE_SIZE, KVM_PGTABLE_PROT_W,

... I messed this up ;) It seems I'm managing to leak all guestmem
pages. I'm not sure what I was thinking but I think I'd got it into my
head guestmem wasn't reference counting the pages. I'll fix this up in
the next version.

Thanks,

Steve

---

## [30] Suzuki K Poulose — 2024-05-31
*Subject: Re: [PATCH v2 13/14] arm64: rsi: Interfaces to query attestation
 token*

On 22/05/2024 16:52, Steven Price wrote:
> On 15/05/2024 12:10, Catalin Marinas wrote:
>> On Fri, Apr 12, 2024 at 09:42:12AM +0100, Steven Price wrote:

The struct realm_config must be aligned to GRANULE_SIZE and the argument
must be as such aligned.

> 
> There are only two other interfaces that require this:

That looks good to me.

Suzuki


> belongs in rsi.h because none of that functionality cares about the
> granule size (indeed the driver in the following patch doesn't include

---

## [31] Jason Gunthorpe — 2024-06-01
*Subject: Re: [v2] Support for Arm CCA VMs on Linux*

On Mon, Apr 15, 2024 at 09:14:47AM +0100, Steven Price wrote:

> The support for running in a guest is (I believe) in a good state
> and I don't expect to have to iterate much on that before merging -

All the stuff I've been hearing about CC is that timely guest support
is a really important thing. Right now the majority of the CC world is
running on propritary hypervisors, it is the guest enablement that is
something a wide group of people will be able to actually consume and
use.

It needs to get into mainline to be able to reach distros about a year
before anyone offers an ARM CC VM to the public. Various x86 guest
only parts for CC are already merged.

The KVM side is absolutely really important as well, but x86 has
managed for a long time now with KVM being out of tree. The KVM side
is far more complex at least.

So I'd split out the guest side and just send it, I saw a few comments
already, but it looks like it shouldn't be an issue to make it this
cycle or next? Keep sending guest enablement updates when the spec is
stable and you have some way to do basic test.

Jason

---

## [32] Itaru Kitayama — 2024-06-24
*Subject: Re: [v2] Support for Arm CCA VMs on Linux*

Hi Steven,
On Fri, Apr 12, 2024 at 09:40:56AM +0100, Steven Price wrote:
> We are happy to announce the second version of the Arm Confidential
> Compute Architecture (CCA) support for the Linux stack. The intention is

I am trying to see if libvirt can work with the CCA-aware KVM with minimal Ubuntu22.10 filesystem, however virt-install triggers a system failure:

$ sudo virt-install -v --name f39 --ram 4096        --disk path=fedora40.img,cache=none --nographics --os-variant fedora38         --import --arch aarch64 --vcpus 4
[sudo] password for realm:
[ 3694.176579] Unable to handle kernel NULL pointer dereference at virtual address 0000000000000e00
[ 3694.176687] Mem abort info:
[ 3694.176745]   ESR = 0x0000000096000004
[ 3694.176817]   EC = 0x25: DABT (current EL), IL = 32 bits
[ 3694.176907]   SET = 0, FnV = 0
[ 3694.176978]   EA = 0, S1PTW = 0
[ 3694.177049]   FSC = 0x04: level 0 translation fault
[ 3694.177132] Data abort info:
[ 3694.177189]   ISV = 0, ISS = 0x00000004, ISS2 = 0x00000000
[ 3694.177276]   CM = 0, WnR = 0, TnD = 0, TagAccess = 0
[ 3694.177370]   GCS = 0, Overlay = 0, DirtyBit = 0, Xs = 0
[ 3694.177544] user pgtable: 4k pages, 48-bit VAs, pgdp=0000000880f6e000
[ 3694.177649] [0000000000000e00] pgd=0000000000000000, p4d=0000000000000000
[ 3694.177788] Internal error: Oops: 0000000096000004 [#1] PREEMPT SMP
[ 3694.177887] Modules linked in:
[ 3694.177966] CPU: 2 PID: 540 Comm: qemu-system-aar Not tainted 6.10.0-rc1-00058-gd901c27a1783 #149
[ 3694.178105] Hardware name: FVP Base RevC (DT)
[ 3694.178180] pstate: 61400009 (nZCv daif +PAN -UAO -TCO +DIT -SSBS BTYPE=--)
[ 3694.178315] pc : kvm_vm_ioctl_check_extension+0x1fc/0x3c4
[ 3694.178447] lr : kvm_vm_ioctl_check_extension_generic+0x34/0x12c
[ 3694.178587] sp : ffff800081523cb0
[ 3694.178657] x29: ffff800081523cb0 x28: 0000000000000051 x27: 0000000000000000
[ 3694.178840] x26: 0000000000000000 x25: 0000000000000000 x24: 0000000000000000
[ 3694.179019] x23: 000000000000000a x22: 0000000000000051 x21: ffff000801075f00
[ 3694.179200] x20: ffff000801075f01 x19: 000000000000ae03 x18: 0000000000000000
[ 3694.179383] x17: 0000000000000000 x16: 0000000000000000 x15: 0000000000000000
[ 3694.179565] x14: 0000000000000000 x13: 0000000000000000 x12: 0000000000000000
[ 3694.179745] x11: 0000000000000000 x10: 0000000000000000 x9 : 0000000000000000
[ 3694.179923] x8 : 0000000000000000 x7 : ffff000801075f18 x6 : 00000000401c5820
[ 3694.180106] x5 : 000000000000000a x4 : 0000000000000800 x3 : 0000000000000000
[ 3694.180285] x2 : 000000000000000b x1 : 0000000100061001 x0 : 0000000000000001
[ 3694.180465] Call trace:
[ 3694.180523]  kvm_vm_ioctl_check_extension+0x1fc/0x3c4
[ 3694.180656]  kvm_vm_ioctl_check_extension_generic+0x34/0x12c
[ 3694.180794]  kvm_dev_ioctl+0x3c8/0x8b8
[ 3694.180938]  __arm64_sys_ioctl+0xac/0xf0
[ 3694.181079]  invoke_syscall+0x48/0x114
[ 3694.181220]  el0_svc_common.constprop.0+0x40/0xe0
[ 3694.181367]  do_el0_svc+0x1c/0x28
[ 3694.181507]  el0_svc+0x34/0xd8
[ 3694.181608]  el0t_64_sync_handler+0x120/0x12c
[ 3694.181723]  el0t_64_sync+0x190/0x194
[ 3694.181865] Code: 17ffffbd 97fffc9d 12001c00 17ffff91 (39780060)
[ 3694.181955] ---[ end trace 0000000000000000 ]---

I'd appreciate it if you could take a look at it.

Thanks,
Itaru.



> 
> An branch of kvm-unit-tests including realm-specific tests is provided

---

## [33] Steven Price — 2024-06-26
*Subject: Re: [v2] Support for Arm CCA VMs on Linux*

On 24/06/2024 07:13, Itaru Kitayama wrote:
> Hi Steven,
> On Fri, Apr 12, 2024 at 09:40:56AM +0100, Steven Price wrote:

Thanks for the bug report. I believe this is because 
kvm_vm_ioctl_check_extension() is being called with kvm==NULL and I've 
missed some checks. I believe the following should get things working - 
and it's probably better than attempting to remember to check with the 
NULL kvm at each call site.

---8<----
diff --git a/arch/arm64/include/asm/kvm_emulate.h b/arch/arm64/include/asm/kvm_emulate.h
index 27c58bbdf50b..c85e5f566506 100644
--- a/arch/arm64/include/asm/kvm_emulate.h
+++ b/arch/arm64/include/asm/kvm_emulate.h
@@ -602,7 +602,7 @@ static __always_inline void kvm_reset_cptr_el2(struct kvm_vcpu *vcpu)
 
 static inline bool kvm_is_realm(struct kvm *kvm)
 {
-       if (static_branch_unlikely(&kvm_rme_is_available))
+       if (static_branch_unlikely(&kvm_rme_is_available) && kvm)
                return kvm->arch.is_realm;
        return false;
 }
---8<----

Thanks,
Steve

---

## [34] Itaru Kitayama — 2024-07-08
*Subject: Re: [v2] Support for Arm CCA VMs on Linux*

Hi Steven,

On Wed, Jun 26, 2024 at 02:39:27PM +0100, Steven Price wrote:
> On 24/06/2024 07:13, Itaru Kitayama wrote:
> > Hi Steven,

Sorry for my late reply I was away entire last week.

With the fix above, I was able to use the virt-install command on FVP without an issue.

Tested-by: Itaru Kitayama <itaru.kitayama@fujitsu.com>

Thanks,
Itaru.

> 
> Thanks,

---
