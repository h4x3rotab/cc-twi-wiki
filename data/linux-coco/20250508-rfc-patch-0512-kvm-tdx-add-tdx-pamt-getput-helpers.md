---
title: '[RFC, PATCH 05/12] KVM: TDX: Add tdx_pamt_get()/put() helpers'
date: 2025-05-08
last_reply: 2025-06-06
message_count: 41
participants: ['Yan Zhao', 'kirill.shutemov@linux.intel.com', 'Huang, Kai', 'Chao Gao', 'Sean Christopherson', 'Vishal Annapurve', 'Zhi Wang', 'Dave Hansen']
---

## [1] Yan Zhao — 2025-05-08

On Wed, May 07, 2025 at 09:31:22AM -0700, Dave Hansen wrote:
> On 5/5/25 05:44, Huang, Kai wrote:
> >> +static int tdx_pamt_add(atomic_t *pamt_refcount, unsigned long hpa,
In patch 2, there're per-2M-range pamt_refcounts. Could the per-2M-range
lock be implemented in a similar way?

+static atomic_t *pamt_refcounts;
+atomic_t *tdx_get_pamt_refcount(unsigned long hpa)
+{
+       return &pamt_refcounts[hpa / PMD_SIZE];
+}


> Kirill, could you put together some kind of torture test for this,
> please? I would imagine a workload which is sitting in a loop setting up
When one vCPU is trying to install a guest page of HPA A, while another vCPU
is trying to install a guest page of HPA B, theoretically they may content the
global pamt_lock even if HPA A and B belong to different PAMT 2M blocks.

> I *suspect* that real systems will get bottlenecked somewhere in the
> page conversion process rather than on this lock. But it should be a

---

## [2] kirill.shutemov@linux.intel.com — 2025-05-08
*Subject: Re: [RFC, PATCH 02/12] x86/virt/tdx: Allocate reference counters for
 PAMT memory*

On Mon, May 05, 2025 at 11:05:12AM +0000, Huang, Kai wrote:
> 
> > +static atomic_t *pamt_refcounts;

We would still need tdx_get_pamt_refcount() to handle case when we need to
bump refcount for page allocated elsewhere.

> > +
> > +static int pamt_refcount_populate(pte_t *pte, unsigned long addr, void *data)

Okay, I will look into this after dealing with huge pages.

> > +
> > +static int init_pamt_metadata(void)

---

## [3] kirill.shutemov@linux.intel.com — 2025-05-08

On Wed, May 07, 2025 at 09:31:22AM -0700, Dave Hansen wrote:
> On 5/5/25 05:44, Huang, Kai wrote:
> >> +static int tdx_pamt_add(atomic_t *pamt_refcount, unsigned long hpa,

I had this idea in mind as well.

> But having it be
> per-2M-range sounds awful. Then you have to size it, and allocate it and

It has to be multiple parallel creation/teardown loops. With single TD we
won't see much concurrency. Most of PAMT allocations comes from single
VCPU.

And it makes sense to do with huge pages as it cuts number of allocated
PAMT memory allocated on TD creation by factor of 10 in my setup.

JFYI, booting a TD with huge pages consumes 1-2MB of PAMT memory. I doubt
any optimization here is justifiable.

> That ^ would be the worst possible case, I think. If you don't see lock
> contention there, you'll hopefully never see it on real systems.

---

## [4] kirill.shutemov@linux.intel.com — 2025-05-08

On Wed, May 07, 2025 at 10:42:25AM +0800, Yan Zhao wrote:
> On Tue, May 06, 2025 at 06:15:40PM -0700, Vishal Annapurve wrote:
> > On Tue, May 6, 2025 at 6:04 PM Yan Zhao <yan.y.zhao@intel.com> wrote:

No. That's mostly wasted memory. We need to aim to allocate memory only as
needed. With huge pages wast majority of such allocations will never be
needed.

---

## [5] kirill.shutemov@linux.intel.com — 2025-05-08

On Thu, May 08, 2025 at 10:08:32AM +0800, Yan Zhao wrote:
> On Wed, May 07, 2025 at 09:31:22AM -0700, Dave Hansen wrote:
> > On 5/5/25 05:44, Huang, Kai wrote:

But why? If no contention, it is just wasteful.

> > Kirill, could you put together some kind of torture test for this,
> > please? I would imagine a workload which is sitting in a loop setting up

This contention will be be momentary if ever happen.

> > I *suspect* that real systems will get bottlenecked somewhere in the
> > page conversion process rather than on this lock. But it should be a

---

## [6] Kirill A. Shutemov — 2025-05-08
*Subject: Re: [RFC, PATCH 08/12] KVM: x86/tdp_mmu: Add phys_prepare() and
 phys_cleanup() to kvm_x86_ops*

On Tue, May 06, 2025 at 07:55:17PM +0800, Yan Zhao wrote:
> On Fri, May 02, 2025 at 04:08:24PM +0300, Kirill A. Shutemov wrote:
> > The functions kvm_x86_ops::link_external_spt() and

Because the memory pool we allocated from is per-vcpu and we lost access
to vcpu by then. And not all callers provide vcpu.

---

## [7] Huang, Kai — 2025-05-09
*Subject: Re: [RFC, PATCH 02/12] x86/virt/tdx: Allocate reference counters for
 PAMT memory*

On Thu, 2025-05-08 at 16:03 +0300, kirill.shutemov@linux.intel.com wrote:
> On Mon, May 05, 2025 at 11:05:12AM +0000, Huang, Kai wrote:
> > 

Hmm I am not sure I am following this.  What "page allocated" are you referring
to?  I am probably missing something, but if the caller wants a TDX page then it
should just call tdx_alloc_page() which handles refcount bumping internally. 
No?

---

## [8] Yan Zhao — 2025-05-09
*Subject: Re: [RFC, PATCH 08/12] KVM: x86/tdp_mmu: Add phys_prepare() and
 phys_cleanup() to kvm_x86_ops*

On Thu, May 08, 2025 at 04:23:56PM +0300, Kirill A. Shutemov wrote:
> On Tue, May 06, 2025 at 07:55:17PM +0800, Yan Zhao wrote:
> > On Fri, May 02, 2025 at 04:08:24PM +0300, Kirill A. Shutemov wrote:
Maybe we can get vcpu via kvm_get_running_vcpu(), as in [1].
Then for callers not providing vcpu (where vcpu is NULL), we can use per-KVM
cache? 


[1] https://lore.kernel.org/all/20250424030926.554-1-yan.y.zhao@intel.com/

---

## [9] Chao Gao — 2025-05-09
*Subject: Re: [RFC, PATCH 02/12] x86/virt/tdx: Allocate reference counters for
 PAMT memory*

>+static int init_pamt_metadata(void)
>+{

Shouldn't the free path also be gated by tdx_supports_dynamic_pamt()?

There is a possibility that pamt_refcounts could be NULL here, e.g., the
TDX module doesn't support dynamic PAMT and init_tdmrs() encountered an
error.  I am assuming that apply_to_existing_page_range() below will cause
issues if pamt_refcounts is NULL, e.g., unmap mappings set up by others.

>+	size = round_up(size, PAGE_SIZE);
>+	apply_to_existing_page_range(&init_mm,

---

## [10] Chao Gao — 2025-05-09
*Subject: Re: [RFC, PATCH 03/12] x86/virt/tdx: Add wrappers for
 TDH.PHYMEM.PAMT.ADD/REMOVE*

> int tdx_guest_keyid_alloc(void);
> u32 tdx_get_nr_guest_keyids(void);

When these SEAMCALL wrappers were added, Dave requested that a struct page
be passed in instead of an HPA [*]. Does this apply to
tdh_phymem_pamt_add/remove()?

[*]: https://lore.kernel.org/kvm/30d0cef5-82d5-4325-b149-0e99833b8785@intel.com/

---

## [11] Kirill A. Shutemov — 2025-05-12
*Subject: Re: [RFC, PATCH 02/12] x86/virt/tdx: Allocate reference counters for
 PAMT memory*

On Fri, May 09, 2025 at 05:52:16PM +0800, Chao Gao wrote:
> >+static int init_pamt_metadata(void)
> >+{

True. Missed this.

---

## [12] kirill.shutemov@linux.intel.com — 2025-05-12
*Subject: Re: [RFC, PATCH 02/12] x86/virt/tdx: Allocate reference counters for
 PAMT memory*

On Fri, May 09, 2025 at 01:06:05AM +0000, Huang, Kai wrote:
> On Thu, 2025-05-08 at 16:03 +0300, kirill.shutemov@linux.intel.com wrote:
> > On Mon, May 05, 2025 at 11:05:12AM +0000, Huang, Kai wrote:

Pages that get mapped to the guest is allocated externally via
guest_memfd and we need bump refcount for them.

---

## [13] Kirill A. Shutemov — 2025-05-12
*Subject: Re: [RFC, PATCH 03/12] x86/virt/tdx: Add wrappers for
 TDH.PHYMEM.PAMT.ADD/REMOVE*

On Fri, May 09, 2025 at 06:18:01PM +0800, Chao Gao wrote:
> > int tdx_guest_keyid_alloc(void);
> > u32 tdx_get_nr_guest_keyids(void);

hpa here points to a 2M region that pamt_pages covers. We don't have
struct page that represents it. Passing 4k struct page would be
misleading IMO.

---

## [14] Kirill A. Shutemov — 2025-05-12
*Subject: Re: [RFC, PATCH 08/12] KVM: x86/tdp_mmu: Add phys_prepare() and
 phys_cleanup() to kvm_x86_ops*

On Fri, May 09, 2025 at 09:25:58AM +0800, Yan Zhao wrote:
> On Thu, May 08, 2025 at 04:23:56PM +0300, Kirill A. Shutemov wrote:
> > On Tue, May 06, 2025 at 07:55:17PM +0800, Yan Zhao wrote:

Hm. I was not aware of kvm_get_running_vcpu(). Will play with it, thanks.

---

## [15] Huang, Kai — 2025-05-13
*Subject: Re: [RFC, PATCH 02/12] x86/virt/tdx: Allocate reference counters for
 PAMT memory*

On Mon, 2025-05-12 at 12:53 +0300, kirill.shutemov@linux.intel.com wrote:
> On Fri, May 09, 2025 at 01:06:05AM +0000, Huang, Kai wrote:
> > On Thu, 2025-05-08 at 16:03 +0300, kirill.shutemov@linux.intel.com wrote:

Oh right.  TDX private pages can also be in page cache.

It's better to have a way to consolidate page allocation for TDX but with page
cache I don't see a simple straightforward way to do that.

For now, I think we can just export tdx_pamt_{get|put}() in the core TDX code.
We can also provide tdx_{alloc|free}_page() wrappers (e.g., static inline in
<asm/tdx.h>) for kernel TDX memory allocation so that they can be used for TDX
Connect too.

---

## [16] Huang, Kai — 2025-05-14
*Subject: Re: [RFC, PATCH 08/12] KVM: x86/tdp_mmu: Add phys_prepare() and
 phys_cleanup() to kvm_x86_ops*

On Mon, 2025-05-12 at 12:55 +0300, Kirill A. Shutemov wrote:
> On Fri, May 09, 2025 at 09:25:58AM +0800, Yan Zhao wrote:
> > On Thu, May 08, 2025 at 04:23:56PM +0300, Kirill A. Shutemov wrote:

I am not sure why per-vcpu cache matters.

For non-leaf SEPT pages, AFAICT the "vcpu->arch.mmu_external_spt_cache" is just
an empty cache, and eventually __get_free_page() is used to allocate in:
                                                                                            
  sp->external_spt = 
	kvm_mmu_memory_cache_alloc(&vcpu->arch.mmu_external_spt_cache);

So why not we actually create a kmem_cache for it with an actual 'ctor', and we
can call tdx_alloc_page() in that.  This makes sure when the "external_spt" is
allocated, the underneath PAMT entry is there.

For the last level guest memory page, similar to SEV, we can hook the
kvm_arch_gmem_prepare() to call tdx_alloc_page() to make PAMT entry ready.

---

## [17] Huang, Kai — 2025-05-14
*Subject: Re: [RFC, PATCH 09/12] KVM: TDX: Preallocate PAMT pages to be used in
 page fault path*

On Fri, 2025-05-02 at 16:08 +0300, Kirill A. Shutemov wrote:
> Preallocate a page to be used in the link_external_spt() and
> set_external_spte() paths.

IIUC, this patch can be avoided if we create an actual kmem_cache for
mmu_external_spt_cache with an actual 'ctor' where we simply call
tdx_alloc_page() as replied to the previous patch.

---

## [18] Huang, Kai — 2025-05-14
*Subject: Re: [RFC, PATCH 11/12] KVM: TDX: Reclaim PAMT memory*

On 3/05/2025 1:08 am, Kirill A. Shutemov wrote:
> The PAMT memory holds metadata for TDX-protected memory. With Dynamic
> PAMT, PAMT_4K is allocated on demand. The kernel supplies the TDX module

IMHO, instead of explicitly hooking tdx_pamt_put() to various places, we 
should just do tdx_free_page() for the pages that were allocated by 
tdx_alloc_page() (i.e., control pages, SEPT pages).

That means, IMHO, we should do PAMT allocation/free when we actually 
*allocate* and *free* the target TDX private page(s).  I.e., we should:

- For TDX private pages with normal kernel allocation (control pages, 
SEPT pages etc), we use tdx_alloc_page() and tdx_free_page().
- For TDX private pages in page cache, i.e., guest_memfd, since we 
cannot use tdx_{alloc|free}_page(), we hook guest_memfd code to call 
tdx_pamt_{get|put}().

(I wish there's a way to unify the above two as well, but I don't have a 
simple way to do that.)

I believe this can help simplifying the code.

So, ...

> 
> Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>

... I think this change should be removed, and ...

[...]

> +	tdx_pamt_put(kvm_tdx->td.tdr_page);
>   

... The above two should be just:

	tdx_free_page(kvm_tdx->td.tdr_page);

and ...

>   	kvm_tdx->td.tdr_page = NULL;
> @@ -1768,6 +1772,7 @@ static int tdx_sept_drop_private_spte(struct kvm *kvm, gfn_t gfn,
... the above should be removed too.

For PAMT associated with sp->external_spt, we can call tdx_pamt_put() 
when we free sp->external_spt.

For PAMT associated with TDX memory in guest_memfd, we can have a 
guest_memfd specific a_ops->folio_invalidate() in which we can have a 
hook opposite to kvm_gmem_prepare_folio() to do tdx_pamt_put().  That 
should cover all the cases, right?

Or anything I missed?

---

## [19] Chao Gao — 2025-05-14

>+static int tdx_pamt_add(atomic_t *pamt_refcount, unsigned long hpa,
>+			struct list_head *pamt_pages)

Nit: it is better to use SZ_2M or PMD_SIZE consistently.

e.g., patch 2 uses PMD_SIZE:
 
+atomic_t *tdx_get_pamt_refcount(unsigned long hpa)
+{
+	return &pamt_refcounts[hpa / PMD_SIZE];
+}
+EXPORT_SYMBOL_GPL(tdx_get_pamt_refcount);

>+
>+	spin_lock(&pamt_lock);

>+	/*
>+	 * tdx_hpa_range_not_free() is true if current task won race

IIUC, this chunk is needed because tdx_pamt_put() decreases the refcount
without holding the pamt_lock. Why not move that decrease inside the lock?

And I suggest that all accesses to the pamt_refcount should be performed with
the pamt_lock held. This can make the code much clearer. It's similar to how
kvm_usage_count is managed, where transitions from 0 to 1 or 1 to 0 require
extra work, but other cases simply increases or decreases the refcount.

---

## [20] Chao Gao — 2025-05-14

>+static void tdx_pamt_put(struct page *page)
>+{

Should the refcount be increased here, since the PAMT pages are not removed?

>+		return;
>+	}

---

## [21] Chao Gao — 2025-05-14
*Subject: Re: [RFC, PATCH 08/12] KVM: x86/tdp_mmu: Add phys_prepare() and
 phys_cleanup() to kvm_x86_ops*

>+static int tdp_mmu_install_spte(struct kvm_vcpu *vcpu,
>+				struct tdp_iter *iter,

nit: kvm is using kvm_x86_call() in most of cases, e.g.,

		ret = kvm_x86_call(phys_prepare)(vcpu, pfn);

>+	}

>+	if (ret)
>+		return ret;

fold this chunk into the if() statement above to align with tdp_mmu_link_sp()
below?

I'm concerned about handling phys_prepare() failures. Such failures may not be
recoverable. ...

>+	ret = tdp_mmu_set_spte_atomic(vcpu->kvm, iter, spte);
>+	if (pfn && ret)

if RET_FP_RETRY is returned here, it could potentially cause an infinite loop.

I think we need a KVM_BUG_ON() somewhere.

---

## [22] Kirill A. Shutemov — 2025-05-14

On Wed, May 14, 2025 at 01:33:38PM +0800, Chao Gao wrote:
> >+static void tdx_pamt_put(struct page *page)
> >+{

Right. Thanks.

---

## [23] Chao Gao — 2025-05-14
*Subject: Re: [RFC, PATCH 09/12] KVM: TDX: Preallocate PAMT pages to be used
 in page fault path*

On Fri, May 02, 2025 at 04:08:25PM +0300, Kirill A. Shutemov wrote:
>Preallocate a page to be used in the link_external_spt() and
>set_external_spte() paths.

The check for vcpu->kvm->arch.vm_type == KVM_X86_TDX_VM is identical to
kvm_has_mirrored_tdp() a few lines above.

>+		int nr = tdx_nr_pamt_pages(tdx_get_sysinfo());

Since you're already accessing tdx_sysinfo, you can check if dynamic PAMT is
enabled and allocate the pamt page cache accordingly.

>+		r = kvm_mmu_topup_memory_cache(&vcpu->arch.pamt_page_cache,
>+					       nr * PT64_ROOT_MAX_LEVEL);

---

## [24] kirill.shutemov@linux.intel.com — 2025-05-14
*Subject: Re: [RFC, PATCH 08/12] KVM: x86/tdp_mmu: Add phys_prepare() and
 phys_cleanup() to kvm_x86_ops*

On Wed, May 14, 2025 at 12:00:17AM +0000, Huang, Kai wrote:
> On Mon, 2025-05-12 at 12:55 +0300, Kirill A. Shutemov wrote:
> > On Fri, May 09, 2025 at 09:25:58AM +0800, Yan Zhao wrote:

This would make hard to debug PAMT memory leaks. external_spt pages in the
pool will have PAMT memory tied to them, so we will have non-zero PAMT
memory usage with zero TDs running.

> For the last level guest memory page, similar to SEV, we can hook the
> kvm_arch_gmem_prepare() to call tdx_alloc_page() to make PAMT entry ready.

I don't think kvm_arch_gmem_prepare() is right place to allocate PAMT
memory. THPs are dynamic and page order can change due to split or
collapse between the time the page is allocated and gets mapped into EPT.
I am not sure if SEV code is correct in this regard.

---

## [25] Sean Christopherson — 2025-05-14
*Subject: Re: [RFC, PATCH 00/12] TDX: Enable Dynamic PAMT*

On Fri, May 02, 2025, Kirill A. Shutemov wrote:
> This RFC patchset enables Dynamic PAMT in TDX. It is not intended to be
> applied, but rather to receive early feedback on the feature design and

In that case, please describe the design, and specifically *why* you chose this
particular design, along with the constraints and rules of dynamic PAMTs that
led to that decision.  It would also be very helpful to know what options you
considered and discarded, so that others don't waste time coming up with solutions
that you already rejected.

> >From our perspective, this feature has a lower priority compared to huge
> page support. I will rebase this patchset on top of Yan's huge page

---

## [26] Vishal Annapurve — 2025-05-14
*Subject: Re: [RFC, PATCH 11/12] KVM: TDX: Reclaim PAMT memory*

On Tue, May 13, 2025 at 6:12 PM Huang, Kai <kai.huang@intel.com> wrote:
>
>

I think it's important to ensure that PAMT pages are *only* allocated
for a 2M range if it's getting mapped in EPT at 4K granularity.
Physical memory allocation order can be different from the EPT mapping
granularity.

---

## [27] Zhi Wang — 2025-05-14
*Subject: Re: [RFC, PATCH 00/12] TDX: Enable Dynamic PAMT*

On Fri,  2 May 2025 16:08:16 +0300
"Kirill A. Shutemov" <kirill.shutemov@linux.intel.com> wrote:

> This RFC patchset enables Dynamic PAMT in TDX. It is not intended to
> be applied, but rather to receive early feedback on the feature

Do we have any estimation on how much extra cost on TVM creation/destroy
when tightly couple the PAMT allocation/de-allocation to the private
page allocation/de-allocation? It has been trendy nowadays that
meta pages are required to be given to the TSM when doing stuff with
private page in many platforms. When the pool of the meta page is
extensible/shrinkable, there are always ideas about batch pre-charge the
pool and lazy batch reclaim it at a certain path for performance
considerations or VM characteristics. That might turn into a
vendor-agnostic path in KVM with tunable configurations.

Z.

> =========================================================================
>

---

## [28] Kirill A. Shutemov — 2025-05-15
*Subject: Re: [RFC, PATCH 00/12] TDX: Enable Dynamic PAMT*

On Wed, May 14, 2025 at 11:33:17PM +0300, Zhi Wang wrote:
> On Fri,  2 May 2025 16:08:16 +0300
> "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com> wrote:

It depends on the pages that the page allocator gives to TD. If memory is
not fragmented and TD receives memory from the same 2M chunks, we do not
need much PAMT memory and we do not need to make additional SEAMCALLs to
add it. It also depends on the availability of huge pages.

From my tests, a typical TD boot takes about 20 MiB of PAMT memory if no
huge pages are allocated and about 2MiB with huge pages. The overhead on
its management is negligible, especially with huge pages: approximately
256 SEAMCALLs to add PAMT pages and the same number to remove.

The consumption of PAMT memory for booting does not increase significantly
with the size of TD as the guest accepts memory lazily. However, it will
increase as more memory is accepted if huge pages are not used.

I don't think we can justify any batching here.

---

## [29] Dave Hansen — 2025-05-15
*Subject: Re: [RFC, PATCH 00/12] TDX: Enable Dynamic PAMT*

On 5/15/25 02:17, Kirill A. Shutemov wrote:
> I don't think we can justify any batching here.

The is one primary goal here:

	Reduce TDX overhead when not running TDX guests.

It has the side-effect of being _able_ to reduce the amount of memory
that TDX guests use when using >=2M pages only. It has the theoretical
capability to do the same for 4k users but only when the pages are quite
contiguous.

Right?

The "not running TDX guest" and ">=2M pages" benefits are relatively
easy. The 4k one is hard and is going to take a lot more work.

Could we please focus on the easy one for now and not get distracted by
the hard one that might not even be worth it in the end?

---

## [30] Kirill A. Shutemov — 2025-05-15
*Subject: Re: [RFC, PATCH 00/12] TDX: Enable Dynamic PAMT*

On Wed, May 14, 2025 at 06:41:10AM -0700, Sean Christopherson wrote:
> On Fri, May 02, 2025, Kirill A. Shutemov wrote:
> > This RFC patchset enables Dynamic PAMT in TDX. It is not intended to be

Dynamic PAMT support in TDX module
==================================

Dynamic PAMT is a TDX feature that allows VMM to allocate PAMT_4K as
needed. PAMT_1G and PAMT_2M are still allocated statically at the time of
TDX module initialization. At init stage allocation of PAMT_4K is replaced
with PAMT_PAGE_BITMAP which currently requires one bit of memory per 4k.

VMM is responsible for allocating and freeing PAMT_4K. There's a pair of
new SEAMCALLs for it: TDH.PHYMEM.PAMT.ADD and TDH.PHYMEM.PAMT.REMOVE. They
add/remove PAMT memory in form of page pair. There's no requirement for
these pages to be contiguous.

Page pair supplied via TDH.PHYMEM.PAMT.ADD will cover specified 2M region.
It allows any 4K from the region to be usable by TDX module.

With Dynamic PAMT, a number of SEAMCALLs can now fail due to missing PAMT
memory (TDX_MISSING_PAMT_PAGE_PAIR):

 - TDH.MNG.CREATE
 - TDH.MNG.ADDCX 
 - TDH.VP.ADDCX
 - TDH.VP.CREATE
 - TDH.MEM.PAGE.ADD
 - TDH.MEM.PAGE.AUG 
 - TDH.MEM.PAGE.DEMOTE
 - TDH.MEM.PAGE.RELOCATE

Basically, if you supply memory to a TD, this memory has to backed by PAMT
memory.

Once no TD uses the 2M range, the PAMT page pair can be reclaimed with
TDH.PHYMEM.PAMT.REMOVE.

TDX module track PAMT memory usage and can give VMM a hint that PAMT
memory can be removed. Such hint is provided from all SEAMCALLs that
removes memory from TD:

 - TDH.MEM.SEPT.REMOVE
 - TDH.MEM.PAGE.REMOVE
 - TDH.MEM.PAGE.PROMOTE
 - TDH.MEM.PAGE.RELOCATE
 - TDH.PHYMEM.PAGE.RECLAIM

With Dynamic PAMT, TDH.MEM.PAGE.DEMOTE takes PAMT page pair as additional
input to populate PAMT_4K on split. TDH.MEM.PAGE.PROMOTE returns no longer
needed PAMT page pair.

PAMT memory is global resource and not tied to a specific TD. TDX modules
maintains PAMT memory in a radix tree addressed by physical address. Each
entry in the tree can be locked with shared or exclusive lock. Any
modification of the tree requires exclusive lock.

Any SEAMCALL that takes explicit HPA as an argument will walk the tree
taking shared lock on entries. It required to make sure that the page
pointed by HPA is of compatible type for the usage.

TDCALLs don't take PAMT locks as none of the take HPA as an argument.

Dynamic PAMT enabling in kernel
===============================

Kernel maintains refcounts for every 2M regions with two helpers
tdx_pamt_get() and tdx_pamt_put().

The refcount represents number of users for the PAMT memory in the region.
Kernel calls TDH.PHYMEM.PAMT.ADD on 0->1 transition and
TDH.PHYMEM.PAMT.REMOVE on transition 1->0.

PAMT memory gets allocated as part of TD init, VCPU init, on populating
SEPT tree and adding guest memory (both during TD build and via AUG on
accept).

PAMT memory removed on reclaim of control pages and guest memory.

Populating PAMT memory on fault is tricky as we cannot allocate memory
from the context where it is needed. I introduced a pair of kvm_x86_ops to
allocate PAMT memory from a per-VCPU pool from context where VCPU is still
around and free it on failuire. This flow will likely be reworked in next
versions.

Previous attempt on Dynamic PAMT enabling
=========================================

My initial kernel enabling attempt was quite different. I wanted to make
PAMT allocation lazy: only try to add PAMT page pair if a SEAMCALL fails
due to missing PAMT and reclaim it back based on hint provided by the TDX
module.

The motivation was to avoid duplication of PAMT memory refcounting that
TDX module does on kernel side.

This approach is inherently more racy as we don't serialize PAMT memory
add/remove against SEAMCALLs that uses add/remove memory for a TD. Such
serialization would require global locking which is no-go.

I made this approach work, but at some point I realized that it cannot be
robust as long as we want to avoid TDX_OPERAND_BUSY loops.
TDX_OPERAND_BUSY will pop up as result of the races I mentioned above.

I gave up on this approach and went with the current one which uses
explicit refcounting.


Brain dumped.

Let me know if anything is unclear.

---

## [31] Dave Hansen — 2025-05-15
*Subject: Re: [RFC, PATCH 00/12] TDX: Enable Dynamic PAMT*

On 5/15/25 07:22, Kirill A. Shutemov wrote:
> VMM is responsible for allocating and freeing PAMT_4K. There's a pair of
> new SEAMCALLs for it: TDH.PHYMEM.PAMT.ADD and TDH.PHYMEM.PAMT.REMOVE. They

BTW, that second sentence is a little goofy. Is it talking about
ADD/REMOVE being a matched pair? Or that there needs to be 8k of
metadata storage provided to each ADD/REMOVE call?

One thing I've noticed in writing changelogs and so forth is that
repetition can hurt understanding if the concepts aren't the same. Like
saying there is a "pair" of calls and a "pair" of pages when the fact
that both are pairs is a coincidence rather than an intentional and
important part of the design.

---

## [32] Kirill A. Shutemov — 2025-05-15
*Subject: Re: [RFC, PATCH 00/12] TDX: Enable Dynamic PAMT*

On Thu, May 15, 2025 at 08:03:28AM -0700, Dave Hansen wrote:
> On 5/15/25 07:22, Kirill A. Shutemov wrote:
> > VMM is responsible for allocating and freeing PAMT_4K. There's a pair of

Both :P

Pair of SEAMCALLs operate on pairs of pages.

> One thing I've noticed in writing changelogs and so forth is that
> repetition can hurt understanding if the concepts aren't the same. Like

Yeah, I see it.

I will try to avoid to "pair" for SEAMCALLs in Dynamic PAMT context.
Maybe it will clear up the confusion.

---

## [33] Huang, Kai — 2025-05-19
*Subject: Re: [RFC, PATCH 08/12] KVM: x86/tdp_mmu: Add phys_prepare() and
 phys_cleanup() to kvm_x86_ops*

On Wed, 2025-05-14 at 09:43 +0300, kirill.shutemov@linux.intel.com wrote:
> On Wed, May 14, 2025 at 12:00:17AM +0000, Huang, Kai wrote:
> > On Mon, 2025-05-12 at 12:55 +0300, Kirill A. Shutemov wrote:

Why is that?  AFAICT all 'external_spt' pages are freed when TD is gone.

> 
> > For the last level guest memory page, similar to SEV, we can hook the

Yeah, agreed.  Not sure how does SEV-SNP handles large page split/merge either.

---

## [34] Huang, Kai — 2025-05-19
*Subject: Re: [RFC, PATCH 11/12] KVM: TDX: Reclaim PAMT memory*

On Wed, 2025-05-14 at 08:21 -0700, Vishal Annapurve wrote:
> On Tue, May 13, 2025 at 6:12 PM Huang, Kai <kai.huang@intel.com> wrote:
> > 

Agreed.  Thanks.

I still think all control pages and secure EPT pages can just use
tdx_{alloc|free}_page() though (because we always alloc and use them in 4K
granularity).

---

## [35] kirill.shutemov@linux.intel.com — 2025-05-23

On Mon, May 05, 2025 at 12:44:26PM +0000, Huang, Kai wrote:
> On Fri, 2025-05-02 at 16:08 +0300, Kirill A. Shutemov wrote:
> > Introduce a pair of helpers to allocate and free memory for a given 2M

This check would do nothing to protect you against parallel increase of
the counter as we get here with pamt_refcount == 0 the parallel
atomic_inc_unless_negative() is free to bump the counter in the fast path
without taking the lock just after this condition.

So, the code below will free PAMT memory when there is still user.

> 		spin_unlock(&pamt_lock);
> 		return;

---

## [36] Kirill A. Shutemov — 2025-05-23

On Wed, May 14, 2025 at 01:25:37PM +0800, Chao Gao wrote:
> >+static int tdx_pamt_add(atomic_t *pamt_refcount, unsigned long hpa,
> >+			struct list_head *pamt_pages)

Vast majority of cases will take fast path which requires single atomic
operation. We can move it under lock but it would double number of
atomics. I don't see a strong reason to do this.

---

## [37] kirill.shutemov@linux.intel.com — 2025-05-23
*Subject: Re: [RFC, PATCH 08/12] KVM: x86/tdp_mmu: Add phys_prepare() and
 phys_cleanup() to kvm_x86_ops*

On Wed, May 14, 2025 at 12:00:17AM +0000, Huang, Kai wrote:
> On Mon, 2025-05-12 at 12:55 +0300, Kirill A. Shutemov wrote:
> > On Fri, May 09, 2025 at 09:25:58AM +0800, Yan Zhao wrote:

I looked closer to this and while it is good idea, but ctor in kmem_cache
cannot fail which makes this approach not viable.

I guess we can a constructor directly into struct kvm_mmu_memory_cache.
Let me play with this.

---

## [38] Kirill A. Shutemov — 2025-05-30
*Subject: Re: [RFC, PATCH 09/12] KVM: TDX: Preallocate PAMT pages to be used
 in page fault path*

On Wed, May 14, 2025 at 02:30:34PM +0800, Chao Gao wrote:
> On Fri, May 02, 2025 at 04:08:25PM +0300, Kirill A. Shutemov wrote:
> >Preallocate a page to be used in the link_external_spt() and

Well, yes. But I think it is conceptually different. There can be
different virtualization mode that has mirrored TDP which is not TDX.

> 
> >+		int nr = tdx_nr_pamt_pages(tdx_get_sysinfo());

I will hide it in tdx_nr_pamt_pages() which would return 0 if Dynamic PAMT
is disabled.

---

## [39] kirill.shutemov@linux.intel.com — 2025-06-05
*Subject: Re: [RFC, PATCH 08/12] KVM: x86/tdp_mmu: Add phys_prepare() and
 phys_cleanup() to kvm_x86_ops*

On Fri, May 23, 2025 at 03:00:56PM +0300, kirill.shutemov@linux.intel.com wrote:
> On Wed, May 14, 2025 at 12:00:17AM +0000, Huang, Kai wrote:
> > On Mon, 2025-05-12 at 12:55 +0300, Kirill A. Shutemov wrote:

I failed to make it work.

We need to have destructor paired with the constructor that would do
PAMT-aware freeing. And redirect all free paths to it. It requires
substantial rework. I don't think it worth the effort.

Will do manual PAMT management for SPT in TDX code.

---

## [40] Huang, Kai — 2025-06-05
*Subject: Re: [RFC, PATCH 08/12] KVM: x86/tdp_mmu: Add phys_prepare() and
 phys_cleanup() to kvm_x86_ops*

On Thu, 2025-06-05 at 16:01 +0300, kirill.shutemov@linux.intel.com wrote:
> On Fri, May 23, 2025 at 03:00:56PM +0300, kirill.shutemov@linux.intel.com wrote:
> > On Wed, May 14, 2025 at 12:00:17AM +0000, Huang, Kai wrote:

Thanks for the effort.

Maybe something below?

diff --git a/arch/x86/kvm/mmu/mmu_internal.h
b/arch/x86/kvm/mmu/mmu_internal.h
index db8f33e4de62..48732270bff0 100644
--- a/arch/x86/kvm/mmu/mmu_internal.h
+++ b/arch/x86/kvm/mmu/mmu_internal.h
@@ -164,8 +164,10 @@ static inline bool is_mirror_sp(const struct
kvm_mmu_page *sp)
        return sp->role.is_mirror;
 }
 
-static inline void kvm_mmu_alloc_external_spt(struct kvm_vcpu *vcpu, struct
kvm_mmu_page *sp)
+static inline int kvm_mmu_alloc_external_spt(struct kvm_vcpu *vcpu, struct
kvm_mmu_page *sp)
 {
+       int r;
+
        /*
         * external_spt is allocated for TDX module to hold private EPT
mappings,
         * TDX module will initialize the page by itself.
@@ -173,6 +175,12 @@ static inline void kvm_mmu_alloc_external_spt(struct
kvm_vcpu *vcpu, struct kvm_
         * KVM only interacts with sp->spt for private EPT operations.
         */
        sp->external_spt = kvm_mmu_memory_cache_alloc(&vcpu-
>arch.mmu_external_spt_cache);
+
+       r = tdx_pamt_get(virt_to_page(sp->external_spt));
+       if (r)
+               free_page((unsigned long)sp->external_spt);
+
+       return r;
 }
 
 static inline gfn_t kvm_gfn_root_bits(const struct kvm *kvm, const struct
kvm_mmu_page *root)
diff --git a/arch/x86/kvm/mmu/tdp_mmu.c b/arch/x86/kvm/mmu/tdp_mmu.c
index 7f3d7229b2c1..2d3a716d9195 100644
--- a/arch/x86/kvm/mmu/tdp_mmu.c
+++ b/arch/x86/kvm/mmu/tdp_mmu.c
@@ -55,7 +55,10 @@ void kvm_mmu_uninit_tdp_mmu(struct kvm *kvm)
 
 static void tdp_mmu_free_sp(struct kvm_mmu_page *sp)
 {
-       free_page((unsigned long)sp->external_spt);
+       if (sp->external_spt) {
+               free_page((unsigned long)sp->external_spt);
+               tdx_pamt_put(virt_to_page(sp->external_spt));
+       }
        free_page((unsigned long)sp->spt);
        kmem_cache_free(mmu_page_header_cache, sp);
 }
@@ -1277,8 +1280,13 @@ int kvm_tdp_mmu_map(struct kvm_vcpu *vcpu, struct
kvm_page_fault *fault)
                 */
                sp = tdp_mmu_alloc_sp(vcpu);
                tdp_mmu_init_child_sp(sp, &iter);
-               if (is_mirror_sp(sp))
-                       kvm_mmu_alloc_external_spt(vcpu, sp);
+               if (is_mirror_sp(sp)) {
+                       r = kvm_mmu_alloc_external_spt(vcpu, sp);
+                       if (r) {
+                               tdp_mmu_free_sp(sp);
+                               goto retry;
+                       }
+               }
 
                sp->nx_huge_page_disallowed = fault->huge_page_disallowed;

---

## [41] kirill.shutemov@linux.intel.com — 2025-06-06
*Subject: Re: [RFC, PATCH 08/12] KVM: x86/tdp_mmu: Add phys_prepare() and
 phys_cleanup() to kvm_x86_ops*

On Thu, Jun 05, 2025 at 10:21:46PM +0000, Huang, Kai wrote:
> On Thu, 2025-06-05 at 16:01 +0300, kirill.shutemov@linux.intel.com wrote:
> > On Fri, May 23, 2025 at 03:00:56PM +0300, kirill.shutemov@linux.intel.com wrote:

With help of kvm_get_running_vcpu(), I localized these manipulations to
the internals of TDX code. No need to leak this to TDP.

phys_prepare/cleanup() is gone now.

https://git.kernel.org/pub/scm/linux/kernel/git/kas/linux.git/commit/?h=tdx/dpamt-huge&id=72394699b5454aac6c027accab6d94a52d88819b

---
