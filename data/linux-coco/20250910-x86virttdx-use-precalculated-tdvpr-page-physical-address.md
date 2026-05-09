---
title: 'x86/virt/tdx: Use precalculated TDVPR page physical address'
date: 2025-09-10
last_reply: 2025-10-30
message_count: 15
participants: ['Dave Hansen', 'Kiryl Shutsemau', 'Dave Hansen', 'Sean Christopherson']
---

## [1] Dave Hansen — 2025-09-10

From: Kai Huang <kai.huang@intel.com>

All of the x86 KVM guest types (VMX, SEV and TDX) do some special context
tracking when entering guests. This means that the actual guest entry
sequence must be noinstr.

Part of entering a TDX guest is passing a physical address to the TDX
module. Right now, that physical address is stored as a 'struct page'
and converted to a physical address at guest entry. That page=>phys
conversion can be complicated, can vary greatly based on kernel
config, and it is definitely _not_ a noinstr path today.

There have been a number of tinkering approaches to try and fix this
up, but they all fall down due to some part of the page=>phys
conversion infrastructure not being noinstr friendly.

Precalculate the page=>phys conversion and store it in the existing
'tdx_vp' structure.  Use the new field at every site that needs a
tdvpr physical address. Remove the now redundant tdx_tdvpr_pa().
Remove the __flatten remnant from the tinkering.

Note that only one user of the new field is actually noinstr. All
others can use page_to_phys(). But, they might as well save the effort
since there is a pre-calculated value sitting there for them.

[ dhansen: rewrite all the text ]

Signed-off-by: Kai Huang <kai.huang@intel.com>
Signed-off-by: Dave Hansen <dave.hansen@linux.intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
---
 arch/x86/include/asm/tdx.h  |  2 ++
 arch/x86/kvm/vmx/tdx.c      |  9 +++++++++
 arch/x86/virt/vmx/tdx/tdx.c | 21 ++++++++-------------
 3 files changed, 19 insertions(+), 13 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 6120461bd5ff3..6b338d7f01b7d 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -171,6 +171,8 @@ struct tdx_td {
 struct tdx_vp {
 	/* TDVP root page */
 	struct page *tdvpr_page;
+	/* precalculated page_to_phys(tdvpr_page) for use in noinstr code */
+	phys_addr_t tdvpr_pa;
 
 	/* TD vCPU control structure: */
 	struct page **tdcx_pages;
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 04b6d332c1afa..75326a7449cc3 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -852,6 +852,7 @@ void tdx_vcpu_free(struct kvm_vcpu *vcpu)
 	if (tdx->vp.tdvpr_page) {
 		tdx_reclaim_control_page(tdx->vp.tdvpr_page);
 		tdx->vp.tdvpr_page = 0;
+		tdx->vp.tdvpr_pa = 0;
 	}
 
 	tdx->state = VCPU_TD_STATE_UNINITIALIZED;
@@ -2931,6 +2932,13 @@ static int tdx_td_vcpu_init(struct kvm_vcpu *vcpu, u64 vcpu_rcx)
 		return -ENOMEM;
 	tdx->vp.tdvpr_page = page;
 
+	/*
+	 * page_to_phys() does not work in 'noinstr' code, like guest
+	 * entry via tdh_vp_enter(). Precalculate and store it instead
+	 * of doing it at runtime later.
+	 */
+	tdx->vp.tdvpr_pa = page_to_phys(tdx->vp.tdvpr_page);
+
 	tdx->vp.tdcx_pages = kcalloc(kvm_tdx->td.tdcx_nr_pages, sizeof(*tdx->vp.tdcx_pages),
 			       	     GFP_KERNEL);
 	if (!tdx->vp.tdcx_pages) {
@@ -2993,6 +3001,7 @@ static int tdx_td_vcpu_init(struct kvm_vcpu *vcpu, u64 vcpu_rcx)
 	if (tdx->vp.tdvpr_page)
 		__free_page(tdx->vp.tdvpr_page);
 	tdx->vp.tdvpr_page = 0;
+	tdx->vp.tdvpr_pa = 0;
 
 	return ret;
 }
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 330b560313afe..eac4032484626 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1504,11 +1504,6 @@ static inline u64 tdx_tdr_pa(struct tdx_td *td)
 	return page_to_phys(td->tdr_page);
 }
 
-static inline u64 tdx_tdvpr_pa(struct tdx_vp *td)
-{
-	return page_to_phys(td->tdvpr_page);
-}
-
 /*
  * The TDX module exposes a CLFLUSH_BEFORE_ALLOC bit to specify whether
  * a CLFLUSH of pages is required before handing them to the TDX module.
@@ -1520,9 +1515,9 @@ static void tdx_clflush_page(struct page *page)
 	clflush_cache_range(page_to_virt(page), PAGE_SIZE);
 }
 
-noinstr __flatten u64 tdh_vp_enter(struct tdx_vp *td, struct tdx_module_args *args)
+noinstr u64 tdh_vp_enter(struct tdx_vp *td, struct tdx_module_args *args)
 {
-	args->rcx = tdx_tdvpr_pa(td);
+	args->rcx = td->tdvpr_pa;
 
 	return __seamcall_dirty_cache(__seamcall_saved_ret, TDH_VP_ENTER, args);
 }
@@ -1583,7 +1578,7 @@ u64 tdh_vp_addcx(struct tdx_vp *vp, struct page *tdcx_page)
 {
 	struct tdx_module_args args = {
 		.rcx = page_to_phys(tdcx_page),
-		.rdx = tdx_tdvpr_pa(vp),
+		.rdx = vp->tdvpr_pa,
 	};
 
 	tdx_clflush_page(tdcx_page);
@@ -1652,7 +1647,7 @@ EXPORT_SYMBOL_GPL(tdh_mng_create);
 u64 tdh_vp_create(struct tdx_td *td, struct tdx_vp *vp)
 {
 	struct tdx_module_args args = {
-		.rcx = tdx_tdvpr_pa(vp),
+		.rcx = vp->tdvpr_pa,
 		.rdx = tdx_tdr_pa(td),
 	};
 
@@ -1708,7 +1703,7 @@ EXPORT_SYMBOL_GPL(tdh_mr_finalize);
 u64 tdh_vp_flush(struct tdx_vp *vp)
 {
 	struct tdx_module_args args = {
-		.rcx = tdx_tdvpr_pa(vp),
+		.rcx = vp->tdvpr_pa,
 	};
 
 	return seamcall(TDH_VP_FLUSH, &args);
@@ -1754,7 +1749,7 @@ EXPORT_SYMBOL_GPL(tdh_mng_init);
 u64 tdh_vp_rd(struct tdx_vp *vp, u64 field, u64 *data)
 {
 	struct tdx_module_args args = {
-		.rcx = tdx_tdvpr_pa(vp),
+		.rcx = vp->tdvpr_pa,
 		.rdx = field,
 	};
 	u64 ret;
@@ -1771,7 +1766,7 @@ EXPORT_SYMBOL_GPL(tdh_vp_rd);
 u64 tdh_vp_wr(struct tdx_vp *vp, u64 field, u64 data, u64 mask)
 {
 	struct tdx_module_args args = {
-		.rcx = tdx_tdvpr_pa(vp),
+		.rcx = vp->tdvpr_pa,
 		.rdx = field,
 		.r8 = data,
 		.r9 = mask,
@@ -1784,7 +1779,7 @@ EXPORT_SYMBOL_GPL(tdh_vp_wr);
 u64 tdh_vp_init(struct tdx_vp *vp, u64 initial_rcx, u32 x2apicid)
 {
 	struct tdx_module_args args = {
-		.rcx = tdx_tdvpr_pa(vp),
+		.rcx = vp->tdvpr_pa,
 		.rdx = initial_rcx,
 		.r8 = x2apicid,
 	};

---

## [2] Kiryl Shutsemau — 2025-09-10
*Subject: Re: [PATCH] x86/virt/tdx: Use precalculated TDVPR page physical
 address*

On Wed, Sep 10, 2025 at 07:44:53AM -0700, Dave Hansen wrote:
> From: Kai Huang <kai.huang@intel.com>
> 

Reviewed-by: Kiryl Shutsemau <kas@kernel.org>

One nitpick is below.

> ---
>  arch/x86/include/asm/tdx.h  |  2 ++

Missing newline above the new field?

---

## [3] Dave Hansen — 2025-09-10
*Subject: Re: [PATCH] x86/virt/tdx: Use precalculated TDVPR page physical
 address*

On 9/10/25 09:06, Kiryl Shutsemau wrote:
>>  struct tdx_vp {
>>  	/* TDVP root page */

I was actually trying to group the two fields together that are aliases
for the same logical thing.

Is that problematic?

---

## [4] Kiryl Shutsemau — 2025-09-10
*Subject: Re: [PATCH] x86/virt/tdx: Use precalculated TDVPR page physical
 address*

On Wed, Sep 10, 2025 at 09:10:06AM -0700, Dave Hansen wrote:
> On 9/10/25 09:06, Kiryl Shutsemau wrote:
> >>  struct tdx_vp {

No. Just looks odd to me. But I see 'struct tdx_td' also uses similar
style.

---

## [5] Dave Hansen — 2025-09-10
*Subject: Re: [PATCH] x86/virt/tdx: Use precalculated TDVPR page physical
 address*

On 9/10/25 09:12, Kiryl Shutsemau wrote:
> On Wed, Sep 10, 2025 at 09:10:06AM -0700, Dave Hansen wrote:
>> On 9/10/25 09:06, Kiryl Shutsemau wrote:

Your review or ack tag there seems to have been mangled by your email
client. Could you try to resend it, please? ;)

---

## [6] Kiryl Shutsemau — 2025-09-11
*Subject: Re: [PATCH] x86/virt/tdx: Use precalculated TDVPR page physical
 address*

On Wed, Sep 10, 2025 at 09:57:13AM -0700, Dave Hansen wrote:
> On 9/10/25 09:12, Kiryl Shutsemau wrote:
> > On Wed, Sep 10, 2025 at 09:10:06AM -0700, Dave Hansen wrote:

Do you mean my name spelling?

I've decided to move to transliteration from Belarusian rather than
Russian. I will update MAINTAINERS and mailmap later.

---

## [7] Sean Christopherson — 2025-10-20
*Subject: Re: [PATCH] x86/virt/tdx: Use precalculated TDVPR page physical address*

On Wed, Sep 10, 2025, Dave Hansen wrote:
> From: Kai Huang <kai.huang@intel.com>
> 

'0' is a perfectly legal physical address.  And using '0' in the existing code to
nullify a pointer is gross.

Why do these structures track struct page everywhere?  Nothing actually uses the
struct page object (except calls to __free_page().  The leaf functions all take
a physical address or a virtual address.  Track one of those and then use __pa()
or __va() to get at the other.

Side topic, if you're going to bother tracking the number of pages in each struct
despite them being global values, at least reap the benefits of __counted_by().

struct tdx_td {
	/* TD root structure: */
	void *tdr_page;

	int tdcs_nr_pages;
	/* TD control structure: */
	void *tdcs_pages[] __counted_by(tdcs_nr_pages);
};

struct tdx_vp {
	/* TDVP root page */
	void *tdvpr_page;

	int tdcx_nr_pages;
	/* TD vCPU control structure: */
	void *tdcx_pages[] __counted_by(tdcx_nr_pages);
};

---

## [8] Dave Hansen — 2025-10-20
*Subject: Re: [PATCH] x86/virt/tdx: Use precalculated TDVPR page physical
 address*

On 10/20/25 06:57, Sean Christopherson wrote:
> Why do these structures track struct page everywhere?

I asked for it at some point. It allows an unambiguous reference to
normal, (mostly) allocated physical memory. It means that you (mostly)
can't accidentally swap in a virtual address, pfn, or something else
that's not a physical address into the variable.

The TDX ABI is just littered with u64's. There's almost no type safety
anywhere. This is one place to bring a wee little bit of order to the chaos.

In a perfect world, we'd have sparse annotations for the vaddr, paddr,
pfn, dma_addr_t and all the other address spaces. Until then, I like
passing struct page around.

---

## [9] Sean Christopherson — 2025-10-20
*Subject: Re: [PATCH] x86/virt/tdx: Use precalculated TDVPR page physical address*

On Mon, Oct 20, 2025, Dave Hansen wrote:
> On 10/20/25 06:57, Sean Christopherson wrote:
> > Why do these structures track struct page everywhere?

But that clearly doesn't work since now the raw paddr is being passed in many
places, and we end up with goofy code like this where one param takes a raw paddr,
and another uses page_to_phys().

@@ -1583,7 +1578,7 @@ u64 tdh_vp_addcx(struct tdx_vp *vp, struct page *tdcx_page)
 {
        struct tdx_module_args args = {
                .rcx = page_to_phys(tdcx_page),
-               .rdx = tdx_tdvpr_pa(vp),
+               .rdx = vp->tdvpr_pa,
        };


If some form of type safety is the goal, why not do something like this?

  typedef void __private *tdx_page_t;

Or maybe even define a new address space.

  # define __tdx __attribute__((noderef, address_space(__tdx)))

The effective type safety is limited to sparse, but if you keep the tdx code free
of warnings, then any and all warnings from build bots can be treated as "fatal"
errors from a maintenance perspective.

---

## [10] Dave Hansen — 2025-10-20
*Subject: Re: [PATCH] x86/virt/tdx: Use precalculated TDVPR page physical
 address*

On 10/20/25 07:42, Sean Christopherson wrote:
>> In a perfect world, we'd have sparse annotations for the vaddr, paddr,
>> pfn, dma_addr_t and all the other address spaces. Until then, I like

I'm kinda dense normally and my coffee hasn't kicked in yet. What
clearly does not work there?

Yeah, vp->tdvpr_pa is storing a physical address as a raw u64 and not a
'struct page'. That's not ideal. But it's also for a pretty good reason.

The "use 'struct page *' instead of u64 for physical addresses" thingy
is a good pattern, not an absolute rule. Use it when you can, but
abandon it for the greater good when necessary.

I don't hate the idea of a tdx_page_t. I'm just not sure it's worth the
trouble. I'd certainly take a good look at the patches if someone hacked
it together.

---

## [11] Sean Christopherson — 2025-10-20
*Subject: Re: [PATCH] x86/virt/tdx: Use precalculated TDVPR page physical address*

On Mon, Oct 20, 2025, Dave Hansen wrote:
> On 10/20/25 07:42, Sean Christopherson wrote:
> >> In a perfect world, we'd have sparse annotations for the vaddr, paddr,

Relying on struct page to provide type safety.

> Yeah, vp->tdvpr_pa is storing a physical address as a raw u64 and not a
> 'struct page'. That's not ideal. But it's also for a pretty good reason.

Right, but my point is that regradless of the justification, every exception to
passing a struct page diminishes the benefits of using struct page in the first
place.

> The "use 'struct page *' instead of u64 for physical addresses" thingy
> is a good pattern, not an absolute rule. Use it when you can, but

---

## [12] Dave Hansen — 2025-10-20
*Subject: Re: [PATCH] x86/virt/tdx: Use precalculated TDVPR page physical
 address*

On 10/20/25 08:25, Sean Christopherson wrote:
>>> @@ -1583,7 +1578,7 @@ u64 tdh_vp_addcx(struct tdx_vp *vp, struct page *tdcx_page)
>>>  {

Yeah, I'm in total agreement with you there.

But I don't think there's any type scheme that won't have exceptions or
other downsides.

u64's are really nice for prototyping because you can just pass those
suckers around anywhere and the compiler will never say a thing. But we
know the downsides of too many plain integer types getting passed around.

Sparse-enforced address spaces are pretty nifty, but they can get messy
around the edges of the subsystem where the type is used. You end up
with lots of ugly force casts there to bend the compiler to your will.

'struct page *' isn't perfect either. As we saw, you can't get from it
to a physical address easily in noinstr code. It doesn't work everywhere
either.

So I dunno. Sounds like there is no shortage of imperfect ways skin this
cat. Yay, engineering!

But, seriously, if you're super confident that a sparse-enforced address
space is the way to go, it's not *that* hard to go look at it. TDX isn't
that big. I can go poke at it for a bit.

---

## [13] Sean Christopherson — 2025-10-21
*Subject: Re: [PATCH] x86/virt/tdx: Use precalculated TDVPR page physical address*

On Mon, Oct 20, 2025, Dave Hansen wrote:
> On 10/20/25 08:25, Sean Christopherson wrote:
> >>> @@ -1583,7 +1578,7 @@ u64 tdh_vp_addcx(struct tdx_vp *vp, struct page *tdcx_page)

Heh, I dunno about "super confident", but I do think it will be the most robust
overall, and will be helpful for readers by documenting which pages/assets are
effectively opaque handles things that are owned by the TDX-Module.

KVM uses the sparse approach in KVM's TDP MMU implementation to typedef PTE
pointers, which are RCU-protected.

  typedef u64 __rcu *tdp_ptep_t;

There are handful of one open-coded rcu_dereference() calls, but the vast majority
of dereferences get routed through helpers that deal with the gory details.  And
of the open-coded calls, I distinctly remember two being interesting cases where
the __rcu enforcement forced us to slow down and think about exactly the lifetime
of the PTE.  I.e. even the mildly painful "overhead" has been a net positive.

> space is the way to go, it's not *that* hard to go look at it. TDX isn't
> that big. I can go poke at it for a bit.

---

## [14] Dave Hansen — 2025-10-29
*Subject: Re: [PATCH] x86/virt/tdx: Use precalculated TDVPR page physical
 address*

On 10/20/25 07:42, Sean Christopherson wrote:
...
> If some form of type safety is the goal, why not do something like this?
> 

Sean,

I hacked up a TDX physical address namespace for sparse. It's not awful.
It doesn't make the .c files any uglier (or prettier really). It
definitely adds code because it needs a handful of conversion functions.
But those are all one-liner functions.

Net, this approach seems to add a few conversion functions versus the
'struct page' approach. That's because there are at least a couple of
places that *need* a 'struct page' like tdx_unpin().

There's some wonkiness in this like using virtual addresses to back the
"paddr" type. I did that so we could still do NULL checks instead of
keeping some explicit "invalid paddr" value. It's hidden in the helpers
and not exposed to the users, but it is weird for sure. The important
part isn't what the type is in the end, it's that something is making it
opaque.

This can definitely be taken further like getting rid of
tdx->vp.tdvpr_pa precalcuation. But it's mostly a straight s/struct page
*/tdx_paddr_t/ replacement.

I'm not looking at this and jumping up and down for how much better it
makes the code. It certainly *can* find a few things by leveraging
sparse. But, honestly, after seeing that nobody runs or cares about
sparse on this code, it's hard to take it seriously.

Was this generally what you had in mind? Should I turn this into a real
series?

---

## [15] Sean Christopherson — 2025-10-30
*Subject: Re: [PATCH] x86/virt/tdx: Use precalculated TDVPR page physical address*

On Wed, Oct 29, 2025, Dave Hansen wrote:
> On 10/20/25 07:42, Sean Christopherson wrote:
> ...

tdx_unpin() is going away[*] in v6.19 (hopefully; I'll post the next version today).
In fact, that rework eliminates a handful of the helpers that are needed, and in
general can help clean things up.

[*] https://lore.kernel.org/all/20251017003244.186495-8-seanjc@google.com

> There's some wonkiness in this like using virtual addresses to back the
> "paddr" type. I did that so we could still do NULL checks instead of

I really, really, REALLY don't like the tdx_paddr_t nomenclature.  It's obviously
not a physical address, KVM uses "paddr" to track actual physical address (and
does so heavily in selftests), and I don't like that it drops the "page" aspect
of things, i.e. loses the detail that the TDX-Module _only_ works with 4KiB pages.

IMO, "tdx_page_t page" is a much better fit, as it's roughly analogous to
"struct page *page", and which should be a familiar pattern for readers and thus
more intuitive.

> keeping some explicit "invalid paddr" value. It's hidden in the helpers
> and not exposed to the users, but it is weird for sure. The important

Yeah, utilizing sparse can be difficult, because it's so noisy.  My tactic is to
rely on the bots to detect _new_ warnings, but for whateer reason that approach
didn't work for TDX, probably because so much code came in all at once.  In theory,
if we get the initial support right, then the bots will help keep things clean.

> Was this generally what you had in mind? Should I turn this into a real
> series?

More or less, ya.

> diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
> index 6b338d7f01b7d..644b53bcfdfed 100644

Maybe "struct tdx_module_page", to hint to readers that these pages are ultimately
used by the TDX-Module?  Not sure if that's better or worse than e.g. "struct tdx_page".

> +#if defined(__CHECKER__)
> +#define __tdx __attribute__((noderef, address_space(__tdx)))

Is it worth going through alloc_page()?  I'm not entirely clear on whether there's
a meaningful difference in the allocator.  If so, this can be:

	struct page *page = alloc_page(gfp_flags);

	return (__force tdx_page_t)(page ? page_to_virt(page) : NULL);

> +}
> +

To eliminate a few of the open-coded __force, what if we add an equivalent to
rcu_dereference()?  That seems to work well with the tdx_page_t concept, e.g.

static inline tdx_page_t tdx_alloc_page(gfp_t gfp_flags)
{
	struct page *page = alloc_page(gfp_flags);

	return (__force tdx_page_t)(page ? page_to_virt(page) : NULL);
}

static inline struct tdx_module_page *tdx_page_dereference(tdx_page_t page)
{
	return (__force struct tdx_module_page *)page;
}

static inline void tdx_free_page(tdx_page_t page)
{
	free_page((unsigned long)tdx_page_dereference(page));
}

static inline phys_addr_t tdx_page_to_phys(tdx_page_t page)
{
	return __pa(tdx_page_dereference(page));
}

static inline tdx_page_t tdx_phys_to_page(phys_addr_t pa)
{
	return (__force tdx_page_t)phys_to_virt(pa);
}

> @@ -1872,13 +1872,13 @@ static int tdx_sept_free_private_spt(struct kvm *kvm, gfn_t gfn,
>  	 * The HKID assigned to this TD was already freed and cache was

Rather than cast, I vote to change kvm_mmu_page.external_spt to a tdx_page_t.
There's already a comment above the field calling out that its used by TDX, I
don't see any reason to add a layer of indirection there.  That helps eliminate
a helper or two.

	tdx_page_t external_spt;

>  }
>  

Rather than do pfn_to_page() => tdx_page_to_paddr(), we can go straight to
tdx_phys_to_page() and avoid another helper or two.

And with the rework, it's gets even a bit more cleaner, because the KVM API takes
in a mirror_spte instead of a raw pfn.  Then KVM can have:

static tdx_page_t tdx_mirror_spte_to_page(u64 mirror_spte)
{
	return tdx_phys_to_page(spte_to_pfn(mirror_spte) << PAGE_SHIFT);
}

and this code becomes

static int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn,
				     enum pg_level level, u64 mirror_spte)
{
	tdx_page_t page = tdx_mirror_spte_to_page(mirror_spte);

	...

Compile tested only on top of the rework, and I didn't check sparse yet.

---
 arch/x86/include/asm/kvm_host.h |  4 +-
 arch/x86/include/asm/tdx.h      | 65 +++++++++++++++++++++------
 arch/x86/kvm/mmu/mmu_internal.h |  2 +-
 arch/x86/kvm/vmx/tdx.c          | 80 +++++++++++++++++----------------
 arch/x86/virt/vmx/tdx/tdx.c     | 36 +++++++--------
 5 files changed, 114 insertions(+), 73 deletions(-)

diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h
index 9f9839bbce13..9129108dc99c 100644
--- a/arch/x86/include/asm/kvm_host.h
+++ b/arch/x86/include/asm/kvm_host.h
@@ -1842,14 +1842,14 @@ struct kvm_x86_ops {
 
 	/* Update external mapping with page table link. */
 	int (*link_external_spt)(struct kvm *kvm, gfn_t gfn, enum pg_level level,
-				void *external_spt);
+				 tdx_page_t external_spt);
 	/* Update the external page table from spte getting set. */
 	int (*set_external_spte)(struct kvm *kvm, gfn_t gfn, enum pg_level level,
 				 u64 mirror_spte);
 
 	/* Update external page tables for page table about to be freed. */
 	int (*free_external_spt)(struct kvm *kvm, gfn_t gfn, enum pg_level level,
-				 void *external_spt);
+				 tdx_page_t external_spt);
 
 	/* Update external page table from spte getting removed, and flush TLB. */
 	void (*remove_external_spte)(struct kvm *kvm, gfn_t gfn, enum pg_level level,
diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 6b338d7f01b7..270018027a25 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -36,7 +36,9 @@
 
 #include <uapi/asm/mce.h>
 #include <asm/tdx_global_metadata.h>
+#include <linux/io.h>
 #include <linux/pgtable.h>
+#include <linux/mm.h>
 
 /*
  * Used by the #VE exception handler to gather the #VE exception
@@ -154,15 +156,50 @@ int tdx_guest_keyid_alloc(void);
 u32 tdx_get_nr_guest_keyids(void);
 void tdx_guest_keyid_free(unsigned int keyid);
 
-void tdx_quirk_reset_page(struct page *page);
+struct tdx_module_page;
+#if defined(__CHECKER__)
+#define __tdx __attribute__((noderef, address_space(__tdx)))
+#else
+#define __tdx
+#endif
+typedef struct tdx_module_page __tdx * tdx_page_t;
+
+static inline tdx_page_t tdx_alloc_page(gfp_t gfp_flags)
+{
+	struct page *page = alloc_page(gfp_flags);
+
+	return (__force tdx_page_t)(page ? page_to_virt(page) : NULL);
+}
+
+static inline struct tdx_module_page *tdx_page_dereference(tdx_page_t page)
+{
+	return (__force struct tdx_module_page *)page;
+}
+
+static inline void tdx_free_page(tdx_page_t page)
+{
+	free_page((unsigned long)tdx_page_dereference(page));
+}
+
+static inline phys_addr_t tdx_page_to_phys(tdx_page_t page)
+{
+	return __pa(tdx_page_dereference(page));
+}
+
+static inline tdx_page_t tdx_phys_to_page(phys_addr_t pa)
+{
+	return (__force tdx_page_t)phys_to_virt(pa);
+}
+
+void tdx_quirk_reset_page(tdx_page_t page);
 
 struct tdx_td {
 	/* TD root structure: */
-	struct page *tdr_page;
+	tdx_page_t tdr_page;
 
 	int tdcs_nr_pages;
 	/* TD control structure: */
-	struct page **tdcs_pages;
+	tdx_page_t *tdcs_pages;
 
 	/* Size of `tdcx_pages` in struct tdx_vp */
 	int tdcx_nr_pages;
@@ -170,19 +207,19 @@ struct tdx_td {
 
 struct tdx_vp {
 	/* TDVP root page */
-	struct page *tdvpr_page;
+	tdx_page_t tdvpr_page;
 	/* precalculated page_to_phys(tdvpr_page) for use in noinstr code */
 	phys_addr_t tdvpr_pa;
 
 	/* TD vCPU control structure: */
-	struct page **tdcx_pages;
+	tdx_page_t *tdcx_pages;
 };
 
-static inline u64 mk_keyed_paddr(u16 hkid, struct page *page)
+static inline u64 mk_keyed_paddr(u16 hkid, tdx_page_t page)
 {
 	u64 ret;
 
-	ret = page_to_phys(page);
+	ret = tdx_page_to_phys(page);
 	/* KeyID bits are just above the physical address bits: */
 	ret |= (u64)hkid << boot_cpu_data.x86_phys_bits;
 
@@ -196,11 +233,11 @@ static inline int pg_level_to_tdx_sept_level(enum pg_level level)
 }
 
 u64 tdh_vp_enter(struct tdx_vp *vp, struct tdx_module_args *args);
-u64 tdh_mng_addcx(struct tdx_td *td, struct page *tdcs_page);
-u64 tdh_mem_page_add(struct tdx_td *td, u64 gpa, struct page *page, struct page *source, u64 *ext_err1, u64 *ext_err2);
-u64 tdh_mem_sept_add(struct tdx_td *td, u64 gpa, int level, struct page *page, u64 *ext_err1, u64 *ext_err2);
-u64 tdh_vp_addcx(struct tdx_vp *vp, struct page *tdcx_page);
-u64 tdh_mem_page_aug(struct tdx_td *td, u64 gpa, int level, struct page *page, u64 *ext_err1, u64 *ext_err2);
+u64 tdh_mng_addcx(struct tdx_td *td, tdx_page_t tdcs_page);
+u64 tdh_mem_page_add(struct tdx_td *td, u64 gpa, tdx_page_t page, struct page *source, u64 *ext_err1, u64 *ext_err2);
+u64 tdh_mem_sept_add(struct tdx_td *td, u64 gpa, int level, tdx_page_t page, u64 *ext_err1, u64 *ext_err2);
+u64 tdh_vp_addcx(struct tdx_vp *vp, tdx_page_t tdcx_page);
+u64 tdh_mem_page_aug(struct tdx_td *td, u64 gpa, int level, tdx_page_t page, u64 *ext_err1, u64 *ext_err2);
 u64 tdh_mem_range_block(struct tdx_td *td, u64 gpa, int level, u64 *ext_err1, u64 *ext_err2);
 u64 tdh_mng_key_config(struct tdx_td *td);
 u64 tdh_mng_create(struct tdx_td *td, u16 hkid);
@@ -215,12 +252,12 @@ u64 tdh_mng_init(struct tdx_td *td, u64 td_params, u64 *extended_err);
 u64 tdh_vp_init(struct tdx_vp *vp, u64 initial_rcx, u32 x2apicid);
 u64 tdh_vp_rd(struct tdx_vp *vp, u64 field, u64 *data);
 u64 tdh_vp_wr(struct tdx_vp *vp, u64 field, u64 data, u64 mask);
-u64 tdh_phymem_page_reclaim(struct page *page, u64 *tdx_pt, u64 *tdx_owner, u64 *tdx_size);
+u64 tdh_phymem_page_reclaim(tdx_page_t page, u64 *tdx_pt, u64 *tdx_owner, u64 *tdx_size);
 u64 tdh_mem_track(struct tdx_td *tdr);
 u64 tdh_mem_page_remove(struct tdx_td *td, u64 gpa, u64 level, u64 *ext_err1, u64 *ext_err2);
 u64 tdh_phymem_cache_wb(bool resume);
 u64 tdh_phymem_page_wbinvd_tdr(struct tdx_td *td);
-u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, struct page *page);
+u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, tdx_page_t page);
 #else
 static inline void tdx_init(void) { }
 static inline int tdx_cpu_enable(void) { return -ENODEV; }
diff --git a/arch/x86/kvm/mmu/mmu_internal.h b/arch/x86/kvm/mmu/mmu_internal.h
index 73cdcbccc89e..144f46b93b5e 100644
--- a/arch/x86/kvm/mmu/mmu_internal.h
+++ b/arch/x86/kvm/mmu/mmu_internal.h
@@ -110,7 +110,7 @@ struct kvm_mmu_page {
 		 * Page table page of external PT.
 		 * Passed to TDX module, not accessed by KVM.
 		 */
-		void *external_spt;
+		tdx_page_t external_spt;
 	};
 	union {
 		struct kvm_rmap_head parent_ptes; /* rmap pointers to parent sptes */
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index ae43974d033c..5a8a5d50b529 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -324,7 +324,7 @@ static inline void tdx_disassociate_vp(struct kvm_vcpu *vcpu)
 })
 
 /* TDH.PHYMEM.PAGE.RECLAIM is allowed only when destroying the TD. */
-static int __tdx_reclaim_page(struct page *page)
+static int __tdx_reclaim_page(tdx_page_t page)
 {
 	u64 err, rcx, rdx, r8;
 
@@ -341,7 +341,7 @@ static int __tdx_reclaim_page(struct page *page)
 	return 0;
 }
 
-static int tdx_reclaim_page(struct page *page)
+static int tdx_reclaim_page(tdx_page_t page)
 {
 	int r;
 
@@ -357,7 +357,7 @@ static int tdx_reclaim_page(struct page *page)
  * private KeyID.  Assume the cache associated with the TDX private KeyID has
  * been flushed.
  */
-static void tdx_reclaim_control_page(struct page *ctrl_page)
+static void tdx_reclaim_control_page(tdx_page_t ctrl_page)
 {
 	/*
 	 * Leak the page if the kernel failed to reclaim the page.
@@ -366,7 +366,7 @@ static void tdx_reclaim_control_page(struct page *ctrl_page)
 	if (tdx_reclaim_page(ctrl_page))
 		return;
 
-	__free_page(ctrl_page);
+	tdx_free_page(ctrl_page);
 }
 
 struct tdx_flush_vp_arg {
@@ -603,7 +603,7 @@ static void tdx_reclaim_td_control_pages(struct kvm *kvm)
 
 	tdx_quirk_reset_page(kvm_tdx->td.tdr_page);
 
-	__free_page(kvm_tdx->td.tdr_page);
+	tdx_free_page(kvm_tdx->td.tdr_page);
 	kvm_tdx->td.tdr_page = NULL;
 }
 
@@ -898,7 +898,7 @@ void tdx_vcpu_free(struct kvm_vcpu *vcpu)
 	}
 	if (tdx->vp.tdvpr_page) {
 		tdx_reclaim_control_page(tdx->vp.tdvpr_page);
-		tdx->vp.tdvpr_page = 0;
+		tdx->vp.tdvpr_page = NULL;
 		tdx->vp.tdvpr_pa = 0;
 	}
 
@@ -1622,7 +1622,7 @@ void tdx_load_mmu_pgd(struct kvm_vcpu *vcpu, hpa_t root_hpa, int pgd_level)
 }
 
 static int tdx_mem_page_add(struct kvm *kvm, gfn_t gfn, enum pg_level level,
-			    kvm_pfn_t pfn)
+			    tdx_page_t page)
 {
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
 	u64 err, entry, level_state;
@@ -1634,8 +1634,8 @@ static int tdx_mem_page_add(struct kvm *kvm, gfn_t gfn, enum pg_level level,
 	    KVM_BUG_ON(!kvm_tdx->page_add_src, kvm))
 		return -EIO;
 
-	err = tdh_mem_page_add(&kvm_tdx->td, gpa, pfn_to_page(pfn),
-			       kvm_tdx->page_add_src, &entry, &level_state);
+	err = tdh_mem_page_add(&kvm_tdx->td, gpa, page, kvm_tdx->page_add_src,
+			       &entry, &level_state);
 	if (unlikely(tdx_operand_busy(err)))
 		return -EBUSY;
 
@@ -1646,11 +1646,10 @@ static int tdx_mem_page_add(struct kvm *kvm, gfn_t gfn, enum pg_level level,
 }
 
 static int tdx_mem_page_aug(struct kvm *kvm, gfn_t gfn,
-			    enum pg_level level, kvm_pfn_t pfn)
+			    enum pg_level level, tdx_page_t page)
 {
 	int tdx_level = pg_level_to_tdx_sept_level(level);
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
-	struct page *page = pfn_to_page(pfn);
 	gpa_t gpa = gfn_to_gpa(gfn);
 	u64 entry, level_state;
 	u64 err;
@@ -1665,11 +1664,16 @@ static int tdx_mem_page_aug(struct kvm *kvm, gfn_t gfn,
 	return 0;
 }
 
+static tdx_page_t tdx_mirror_spte_to_page(u64 mirror_spte)
+{
+	return tdx_phys_to_page(spte_to_pfn(mirror_spte) << PAGE_SHIFT);
+}
+
 static int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn,
 				     enum pg_level level, u64 mirror_spte)
 {
+	tdx_page_t page = tdx_mirror_spte_to_page(mirror_spte);
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
-	kvm_pfn_t pfn = spte_to_pfn(mirror_spte);
 
 	/* TODO: handle large pages. */
 	if (KVM_BUG_ON(level != PG_LEVEL_4K, kvm))
@@ -1691,21 +1695,20 @@ static int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn,
 	 * the VM image via KVM_TDX_INIT_MEM_REGION; ADD the page to the TD.
 	 */
 	if (unlikely(kvm_tdx->state != TD_STATE_RUNNABLE))
-		return tdx_mem_page_add(kvm, gfn, level, pfn);
+		return tdx_mem_page_add(kvm, gfn, level, page);
 
-	return tdx_mem_page_aug(kvm, gfn, level, pfn);
+	return tdx_mem_page_aug(kvm, gfn, level, page);
 }
 
 static int tdx_sept_link_private_spt(struct kvm *kvm, gfn_t gfn,
-				     enum pg_level level, void *private_spt)
+				     enum pg_level level, tdx_page_t private_spt)
 {
 	int tdx_level = pg_level_to_tdx_sept_level(level);
 	gpa_t gpa = gfn_to_gpa(gfn);
-	struct page *page = virt_to_page(private_spt);
 	u64 err, entry, level_state;
 
-	err = tdh_mem_sept_add(&to_kvm_tdx(kvm)->td, gpa, tdx_level, page, &entry,
-			       &level_state);
+	err = tdh_mem_sept_add(&to_kvm_tdx(kvm)->td, gpa, tdx_level,
+			       private_spt, &entry, &level_state);
 	if (unlikely(tdx_operand_busy(err)))
 		return -EBUSY;
 
@@ -1762,7 +1765,7 @@ static void tdx_track(struct kvm *kvm)
 }
 
 static int tdx_sept_free_private_spt(struct kvm *kvm, gfn_t gfn,
-				     enum pg_level level, void *private_spt)
+				     enum pg_level level, tdx_page_t private_spt)
 {
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
 
@@ -1781,13 +1784,13 @@ static int tdx_sept_free_private_spt(struct kvm *kvm, gfn_t gfn,
 	 * The HKID assigned to this TD was already freed and cache was
 	 * already flushed. We don't have to flush again.
 	 */
-	return tdx_reclaim_page(virt_to_page(private_spt));
+	return tdx_reclaim_page(private_spt);
 }
 
 static void tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
 					 enum pg_level level, u64 mirror_spte)
 {
-	struct page *page = pfn_to_page(spte_to_pfn(mirror_spte));
+	tdx_page_t page = tdx_mirror_spte_to_page(mirror_spte);
 	int tdx_level = pg_level_to_tdx_sept_level(level);
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
 	gpa_t gpa = gfn_to_gpa(gfn);
@@ -2390,8 +2393,8 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 {
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
 	cpumask_var_t packages;
-	struct page **tdcs_pages = NULL;
-	struct page *tdr_page;
+	tdx_page_t *tdcs_pages = NULL;
+	tdx_page_t tdr_page;
 	int ret, i;
 	u64 err, rcx;
 
@@ -2409,7 +2412,7 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 
 	atomic_inc(&nr_configured_hkid);
 
-	tdr_page = alloc_page(GFP_KERNEL);
+	tdr_page = tdx_alloc_page(GFP_KERNEL);
 	if (!tdr_page)
 		goto free_hkid;
 
@@ -2422,7 +2425,7 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 		goto free_tdr;
 
 	for (i = 0; i < kvm_tdx->td.tdcs_nr_pages; i++) {
-		tdcs_pages[i] = alloc_page(GFP_KERNEL);
+		tdcs_pages[i] = tdx_alloc_page(GFP_KERNEL);
 		if (!tdcs_pages[i])
 			goto free_tdcs;
 	}
@@ -2541,7 +2544,7 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 	/* Only free pages not yet added, so start at 'i' */
 	for (; i < kvm_tdx->td.tdcs_nr_pages; i++) {
 		if (tdcs_pages[i]) {
-			__free_page(tdcs_pages[i]);
+			tdx_free_page(tdcs_pages[i]);
 			tdcs_pages[i] = NULL;
 		}
 	}
@@ -2560,15 +2563,15 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 free_tdcs:
 	for (i = 0; i < kvm_tdx->td.tdcs_nr_pages; i++) {
 		if (tdcs_pages[i])
-			__free_page(tdcs_pages[i]);
+			tdx_free_page(tdcs_pages[i]);
 	}
 	kfree(tdcs_pages);
 	kvm_tdx->td.tdcs_pages = NULL;
 
 free_tdr:
 	if (tdr_page)
-		__free_page(tdr_page);
-	kvm_tdx->td.tdr_page = 0;
+		tdx_free_page(tdr_page);
+	kvm_tdx->td.tdr_page = NULL;
 
 free_hkid:
 	tdx_hkid_free(kvm_tdx);
@@ -2893,11 +2896,11 @@ static int tdx_td_vcpu_init(struct kvm_vcpu *vcpu, u64 vcpu_rcx)
 {
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(vcpu->kvm);
 	struct vcpu_tdx *tdx = to_tdx(vcpu);
-	struct page *page;
+	tdx_page_t page;
 	int ret, i;
 	u64 err;
 
-	page = alloc_page(GFP_KERNEL);
+	page = tdx_alloc_page(GFP_KERNEL);
 	if (!page)
 		return -ENOMEM;
 	tdx->vp.tdvpr_page = page;
@@ -2907,7 +2910,7 @@ static int tdx_td_vcpu_init(struct kvm_vcpu *vcpu, u64 vcpu_rcx)
 	 * entry via tdh_vp_enter(). Precalculate and store it instead
 	 * of doing it at runtime later.
 	 */
-	tdx->vp.tdvpr_pa = page_to_phys(tdx->vp.tdvpr_page);
+	tdx->vp.tdvpr_pa = tdx_page_to_phys(tdx->vp.tdvpr_page);
 
 	tdx->vp.tdcx_pages = kcalloc(kvm_tdx->td.tdcx_nr_pages, sizeof(*tdx->vp.tdcx_pages),
 			       	     GFP_KERNEL);
@@ -2917,7 +2920,7 @@ static int tdx_td_vcpu_init(struct kvm_vcpu *vcpu, u64 vcpu_rcx)
 	}
 
 	for (i = 0; i < kvm_tdx->td.tdcx_nr_pages; i++) {
-		page = alloc_page(GFP_KERNEL);
+		page = tdx_alloc_page(GFP_KERNEL);
 		if (!page) {
 			ret = -ENOMEM;
 			goto free_tdcx;
@@ -2939,7 +2942,7 @@ static int tdx_td_vcpu_init(struct kvm_vcpu *vcpu, u64 vcpu_rcx)
 			 * method, but the rest are freed here.
 			 */
 			for (; i < kvm_tdx->td.tdcx_nr_pages; i++) {
-				__free_page(tdx->vp.tdcx_pages[i]);
+				tdx_free_page(tdx->vp.tdcx_pages[i]);
 				tdx->vp.tdcx_pages[i] = NULL;
 			}
 			return -EIO;
@@ -2957,7 +2960,7 @@ static int tdx_td_vcpu_init(struct kvm_vcpu *vcpu, u64 vcpu_rcx)
 free_tdcx:
 	for (i = 0; i < kvm_tdx->td.tdcx_nr_pages; i++) {
 		if (tdx->vp.tdcx_pages[i])
-			__free_page(tdx->vp.tdcx_pages[i]);
+			tdx_free_page(tdx->vp.tdcx_pages[i]);
 		tdx->vp.tdcx_pages[i] = NULL;
 	}
 	kfree(tdx->vp.tdcx_pages);
@@ -2965,8 +2968,8 @@ static int tdx_td_vcpu_init(struct kvm_vcpu *vcpu, u64 vcpu_rcx)
 
 free_tdvpr:
 	if (tdx->vp.tdvpr_page)
-		__free_page(tdx->vp.tdvpr_page);
-	tdx->vp.tdvpr_page = 0;
+		tdx_free_page(tdx->vp.tdvpr_page);
+	tdx->vp.tdvpr_page = NULL;
 	tdx->vp.tdvpr_pa = 0;
 
 	return ret;
@@ -3004,7 +3007,8 @@ static int tdx_vcpu_get_cpuid_leaf(struct kvm_vcpu *vcpu, u32 leaf, int *entry_i
 
 static int tdx_vcpu_get_cpuid(struct kvm_vcpu *vcpu, struct kvm_tdx_cmd *cmd)
 {
-	struct kvm_cpuid2 __user *output, *td_cpuid;
+	struct kvm_cpuid2 __user *output;
+	struct kvm_cpuid2 *td_cpuid;
 	int r = 0, i = 0, leaf;
 	u32 level;
 
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index eac403248462..1429dbe4da85 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -658,9 +658,9 @@ static void tdx_quirk_reset_paddr(unsigned long base, unsigned long size)
 	mb();
 }
 
-void tdx_quirk_reset_page(struct page *page)
+void tdx_quirk_reset_page(tdx_page_t page)
 {
-	tdx_quirk_reset_paddr(page_to_phys(page), PAGE_SIZE);
+	tdx_quirk_reset_paddr(tdx_page_to_phys(page), PAGE_SIZE);
 }
 EXPORT_SYMBOL_GPL(tdx_quirk_reset_page);
 
@@ -1501,7 +1501,7 @@ EXPORT_SYMBOL_GPL(tdx_guest_keyid_free);
 
 static inline u64 tdx_tdr_pa(struct tdx_td *td)
 {
-	return page_to_phys(td->tdr_page);
+	return tdx_page_to_phys(td->tdr_page);
 }
 
 /*
@@ -1510,9 +1510,9 @@ static inline u64 tdx_tdr_pa(struct tdx_td *td)
  * Be conservative and make the code simpler by doing the CLFLUSH
  * unconditionally.
  */
-static void tdx_clflush_page(struct page *page)
+static void tdx_clflush_page(tdx_page_t page)
 {
-	clflush_cache_range(page_to_virt(page), PAGE_SIZE);
+	clflush_cache_range(tdx_page_dereference(page), PAGE_SIZE);
 }
 
 noinstr u64 tdh_vp_enter(struct tdx_vp *td, struct tdx_module_args *args)
@@ -1523,10 +1523,10 @@ noinstr u64 tdh_vp_enter(struct tdx_vp *td, struct tdx_module_args *args)
 }
 EXPORT_SYMBOL_GPL(tdh_vp_enter);
 
-u64 tdh_mng_addcx(struct tdx_td *td, struct page *tdcs_page)
+u64 tdh_mng_addcx(struct tdx_td *td, tdx_page_t tdcs_page)
 {
 	struct tdx_module_args args = {
-		.rcx = page_to_phys(tdcs_page),
+		.rcx = tdx_page_to_phys(tdcs_page),
 		.rdx = tdx_tdr_pa(td),
 	};
 
@@ -1535,12 +1535,12 @@ u64 tdh_mng_addcx(struct tdx_td *td, struct page *tdcs_page)
 }
 EXPORT_SYMBOL_GPL(tdh_mng_addcx);
 
-u64 tdh_mem_page_add(struct tdx_td *td, u64 gpa, struct page *page, struct page *source, u64 *ext_err1, u64 *ext_err2)
+u64 tdh_mem_page_add(struct tdx_td *td, u64 gpa, tdx_page_t page, struct page *source, u64 *ext_err1, u64 *ext_err2)
 {
 	struct tdx_module_args args = {
 		.rcx = gpa,
 		.rdx = tdx_tdr_pa(td),
-		.r8 = page_to_phys(page),
+		.r8 = tdx_page_to_phys(page),
 		.r9 = page_to_phys(source),
 	};
 	u64 ret;
@@ -1555,12 +1555,12 @@ u64 tdh_mem_page_add(struct tdx_td *td, u64 gpa, struct page *page, struct page
 }
 EXPORT_SYMBOL_GPL(tdh_mem_page_add);
 
-u64 tdh_mem_sept_add(struct tdx_td *td, u64 gpa, int level, struct page *page, u64 *ext_err1, u64 *ext_err2)
+u64 tdh_mem_sept_add(struct tdx_td *td, u64 gpa, int level, tdx_page_t page, u64 *ext_err1, u64 *ext_err2)
 {
 	struct tdx_module_args args = {
 		.rcx = gpa | level,
 		.rdx = tdx_tdr_pa(td),
-		.r8 = page_to_phys(page),
+		.r8 = tdx_page_to_phys(page),
 	};
 	u64 ret;
 
@@ -1574,10 +1574,10 @@ u64 tdh_mem_sept_add(struct tdx_td *td, u64 gpa, int level, struct page *page, u
 }
 EXPORT_SYMBOL_GPL(tdh_mem_sept_add);
 
-u64 tdh_vp_addcx(struct tdx_vp *vp, struct page *tdcx_page)
+u64 tdh_vp_addcx(struct tdx_vp *vp, tdx_page_t tdcx_page)
 {
 	struct tdx_module_args args = {
-		.rcx = page_to_phys(tdcx_page),
+		.rcx = tdx_page_to_phys(tdcx_page),
 		.rdx = vp->tdvpr_pa,
 	};
 
@@ -1586,12 +1586,12 @@ u64 tdh_vp_addcx(struct tdx_vp *vp, struct page *tdcx_page)
 }
 EXPORT_SYMBOL_GPL(tdh_vp_addcx);
 
-u64 tdh_mem_page_aug(struct tdx_td *td, u64 gpa, int level, struct page *page, u64 *ext_err1, u64 *ext_err2)
+u64 tdh_mem_page_aug(struct tdx_td *td, u64 gpa, int level, tdx_page_t page, u64 *ext_err1, u64 *ext_err2)
 {
 	struct tdx_module_args args = {
 		.rcx = gpa | level,
 		.rdx = tdx_tdr_pa(td),
-		.r8 = page_to_phys(page),
+		.r8 = tdx_page_to_phys(page),
 	};
 	u64 ret;
 
@@ -1794,10 +1794,10 @@ EXPORT_SYMBOL_GPL(tdh_vp_init);
  * So despite the names, they must be interpted specially as described by the spec. Return
  * them only for error reporting purposes.
  */
-u64 tdh_phymem_page_reclaim(struct page *page, u64 *tdx_pt, u64 *tdx_owner, u64 *tdx_size)
+u64 tdh_phymem_page_reclaim(tdx_page_t page, u64 *tdx_pt, u64 *tdx_owner, u64 *tdx_size)
 {
 	struct tdx_module_args args = {
-		.rcx = page_to_phys(page),
+		.rcx = tdx_page_to_phys(page),
 	};
 	u64 ret;
 
@@ -1858,7 +1858,7 @@ u64 tdh_phymem_page_wbinvd_tdr(struct tdx_td *td)
 }
 EXPORT_SYMBOL_GPL(tdh_phymem_page_wbinvd_tdr);
 
-u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, struct page *page)
+u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, tdx_page_t page)
 {
 	struct tdx_module_args args = {};
 

base-commit: 0da566344bd6586a7c358ab4e19417748e7b0feb
--

---
