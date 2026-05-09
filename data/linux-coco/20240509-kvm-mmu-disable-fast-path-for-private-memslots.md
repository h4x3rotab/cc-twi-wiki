---
title: 'KVM: MMU: Disable fast path for private memslots'
date: 2024-05-09
last_reply: 2024-08-16
message_count: 45
participants: ['Michael Roth', 'Sean Christopherson', 'Paolo Bonzini', 'Isaku Yamahata', 'Borislav Petkov', 'Binbin Wu', 'Huang, Kai', 'Zhi Wang', 'Ackerley Tng', 'Yosry Ahmed', 'Dionna Amalie Glaze']
---

## [1] Michael Roth — 2024-05-09

For hardware-protected VMs like SEV-SNP guests, certain conditions like
attempting to perform a write to a page which is not in the state that
the guest expects it to be in can result in a nested/extended #PF which
can only be satisfied by the host performing an implicit page state
change to transition the page into the expected shared/private state.
This is generally handled by generating a KVM_EXIT_MEMORY_FAULT event
that gets forwarded to userspace to handle via
KVM_SET_MEMORY_ATTRIBUTES.

However, the fast_page_fault() code might misconstrue this situation as
being the result of a write-protected access, and treat it as a spurious
case when it sees that writes are already allowed for the sPTE. This
results in the KVM MMU trying to resume the guest rather than taking any
action to satisfy the real source of the #PF such as generating a
KVM_EXIT_MEMORY_FAULT, resulting in the guest spinning on nested #PFs.

For now, just skip the fast path for hardware-protected VMs since they
don't currently utilize any of this access-tracking machinery anyway. In
the future, these considerations will need to be taken into account if
there's any need/desire to re-enable the fast path for
hardware-protected VMs.

Since software-protected VMs don't have a notion of a shared vs. private
that's separate from what KVM is tracking, the above
KVM_EXIT_MEMORY_FAULT condition wouldn't occur, so avoid the special
handling for that case for now.

Cc: Isaku Yamahata <isaku.yamahata@intel.com>
Signed-off-by: Michael Roth <michael.roth@amd.com>
---
 arch/x86/kvm/mmu/mmu.c | 30 ++++++++++++++++++++++++++++--
 1 file changed, 28 insertions(+), 2 deletions(-)

diff --git a/arch/x86/kvm/mmu/mmu.c b/arch/x86/kvm/mmu/mmu.c
index 62ad38b2a8c9..cecd8360378f 100644
--- a/arch/x86/kvm/mmu/mmu.c
+++ b/arch/x86/kvm/mmu/mmu.c
@@ -3296,7 +3296,7 @@ static int kvm_handle_noslot_fault(struct kvm_vcpu *vcpu,
 	return RET_PF_CONTINUE;
 }
 
-static bool page_fault_can_be_fast(struct kvm_page_fault *fault)
+static bool page_fault_can_be_fast(struct kvm_vcpu *vcpu, struct kvm_page_fault *fault)
 {
 	/*
 	 * Page faults with reserved bits set, i.e. faults on MMIO SPTEs, only
@@ -3307,6 +3307,32 @@ static bool page_fault_can_be_fast(struct kvm_page_fault *fault)
 	if (fault->rsvd)
 		return false;
 
+	/*
+	 * For hardware-protected VMs, certain conditions like attempting to
+	 * perform a write to a page which is not in the state that the guest
+	 * expects it to be in can result in a nested/extended #PF. In this
+	 * case, the below code might misconstrue this situation as being the
+	 * result of a write-protected access, and treat it as a spurious case
+	 * rather than taking any action to satisfy the real source of the #PF
+	 * such as generating a KVM_EXIT_MEMORY_FAULT. This can lead to the
+	 * guest spinning on a #PF indefinitely.
+	 *
+	 * For now, just skip the fast path for hardware-protected VMs since
+	 * they don't currently utilize any of this machinery anyway. In the
+	 * future, these considerations will need to be taken into account if
+	 * there's any need/desire to re-enable the fast path for
+	 * hardware-protected VMs.
+	 *
+	 * Since software-protected VMs don't have a notion of a shared vs.
+	 * private that's separate from what KVM is tracking, the above
+	 * KVM_EXIT_MEMORY_FAULT condition wouldn't occur, so avoid the
+	 * special handling for that case for now.
+	 */
+	if (kvm_slot_can_be_private(fault->slot) &&
+	    !(IS_ENABLED(CONFIG_KVM_SW_PROTECTED_VM) &&
+	      vcpu->kvm->arch.vm_type == KVM_X86_SW_PROTECTED_VM))
+		return false;
+
 	/*
 	 * #PF can be fast if:
 	 *
@@ -3407,7 +3433,7 @@ static int fast_page_fault(struct kvm_vcpu *vcpu, struct kvm_page_fault *fault)
 	u64 *sptep;
 	uint retry_count = 0;
 
-	if (!page_fault_can_be_fast(fault))
+	if (!page_fault_can_be_fast(vcpu, fault))
 		return ret;
 
 	walk_shadow_page_lockless_begin(vcpu);

---

## [2] Michael Roth — 2024-05-09
*Subject: [PATCH v15 22/23] KVM: SEV: Fix return code interpretation for RMP nested page faults*

The intended logic when handling #NPFs with the RMP bit set (31) is to
first check to see if the #NPF requires a shared<->private transition
and, if so, to go ahead and let the corresponding KVM_EXIT_MEMORY_FAULT
get forwarded on to userspace before proceeding with any handling of
other potential RMP fault conditions like needing to PSMASH the RMP
entry/etc (which will be done later if the guest still re-faults after
the KVM_EXIT_MEMORY_FAULT is processed by userspace).

The determination of whether any userspace handling of
KVM_EXIT_MEMORY_FAULT is needed is done by interpreting the return code
of kvm_mmu_page_fault(). However, the current code misinterprets the
return code, expecting 0 to indicate a userspace exit rather than less
than 0 (-EFAULT). This leads to the following unexpected behavior:

  - for KVM_EXIT_MEMORY_FAULTs resulting for implicit shared->private
    conversions, warnings get printed from sev_handle_rmp_fault()
    because it does not expect to be called for GPAs where
    KVM_MEMORY_ATTRIBUTE_PRIVATE is not set. Standard linux guests don't
    generally do this, but it is allowed and should be handled
    similarly to private->shared conversions rather than triggering any
    sort of warnings

  - if gmem support for 2MB folios is enabled (via currently out-of-tree
    code), implicit shared<->private conversions will always result in
    a PSMASH being attempted, even if it's not actually needed to
    resolve the RMP fault. This doesn't cause any harm, but results in a
    needless PSMASH and zapping of the sPTE

Resolve these issues by calling sev_handle_rmp_fault() only when
kvm_mmu_page_fault()'s return code is greater than or equal to 0,
indicating a KVM_MEMORY_EXIT_FAULT/-EFAULT isn't needed. While here,
simplify the code slightly and fix up the associated comments for better
clarity.

Fixes: ccc9d836c5c3 ("KVM: SEV: Add support to handle RMP nested page faults")

Signed-off-by: Michael Roth <michael.roth@amd.com>
---
 arch/x86/kvm/svm/svm.c | 10 ++++------
 1 file changed, 4 insertions(+), 6 deletions(-)

diff --git a/arch/x86/kvm/svm/svm.c b/arch/x86/kvm/svm/svm.c
index 426ad49325d7..9431ce74c7d4 100644
--- a/arch/x86/kvm/svm/svm.c
+++ b/arch/x86/kvm/svm/svm.c
@@ -2070,14 +2070,12 @@ static int npf_interception(struct kvm_vcpu *vcpu)
 				svm->vmcb->control.insn_len);
 
 	/*
-	 * rc == 0 indicates a userspace exit is needed to handle page
-	 * transitions, so do that first before updating the RMP table.
+	 * rc < 0 indicates a userspace exit may be needed to handle page
+	 * attribute updates, so deal with that first before handling other
+	 * potential RMP fault conditions.
 	 */
-	if (error_code & PFERR_GUEST_RMP_MASK) {
-		if (rc == 0)
-			return rc;
+	if (rc >= 0 && error_code & PFERR_GUEST_RMP_MASK)
 		sev_handle_rmp_fault(vcpu, fault_address, error_code);
-	}
 
 	return rc;
 }

---

## [3] Michael Roth — 2024-05-09
*Subject: [PATCH v15 23/23] KVM: SEV: Fix PSC handling for SMASH/UNSMASH and partial update ops*

There are a few edge-cases that the current processing for GHCB PSC
requests doesn't handle properly:

 - KVM properly ignores SMASH/UNSMASH ops when they are embedded in a
   PSC request buffer which contains other PSC operations, but
   inadvertantly forwards them to userspace as private->shared PSC
   requests if they appear at the end of the buffer. Make sure these are
   ignored instead, just like cases where they are not at the end of the
   request buffer.

 - Current code handles non-zero 'cur_page' fields when they are at the
   beginning of a new GPA range, but it is not handling properly when
   iterating through subsequent entries which are otherwise part of a
   contiguous range. Fix up the handling so that these entries are not
   combined into a larger contiguous range that include unintended GPA
   ranges and are instead processed later as the start of a new
   contiguous range.

 - The page size variable used to track 2M entries in KVM for inflight PSCs
   might be artifically set to a different value, which can lead to
   unexpected values in the entry's final 'cur_page' update. Use the
   entry's 'pagesize' field instead to determine what the value of
   'cur_page' should be upon completion of processing.

While here, also add a small helper for clearing in-flight PSCs
variables and fix up comments for better readability.

Fixes: 266205d810d2 ("KVM: SEV: Add support to handle Page State Change VMGEXIT")
Signed-off-by: Michael Roth <michael.roth@amd.com>
---
 arch/x86/kvm/svm/sev.c | 73 +++++++++++++++++++++++++++---------------
 1 file changed, 47 insertions(+), 26 deletions(-)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 35f0bd91f92e..ab23329e2bd0 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -3555,43 +3555,50 @@ struct psc_buffer {
 
 static int snp_begin_psc(struct vcpu_svm *svm, struct psc_buffer *psc);
 
-static int snp_complete_psc(struct kvm_vcpu *vcpu)
+static void snp_reset_inflight_psc(struct vcpu_svm *svm)
+{
+	svm->sev_es.psc_idx = 0;
+	svm->sev_es.psc_inflight = 0;
+	svm->sev_es.psc_2m = false;
+}
+
+static void __snp_complete_psc(struct vcpu_svm *svm)
 {
-	struct vcpu_svm *svm = to_svm(vcpu);
 	struct psc_buffer *psc = svm->sev_es.ghcb_sa;
 	struct psc_entry *entries = psc->entries;
 	struct psc_hdr *hdr = &psc->hdr;
-	__u64 psc_ret;
 	__u16 idx;
 
-	if (vcpu->run->hypercall.ret) {
-		psc_ret = VMGEXIT_PSC_ERROR_GENERIC;
-		goto out_resume;
-	}
-
 	/*
 	 * Everything in-flight has been processed successfully. Update the
-	 * corresponding entries in the guest's PSC buffer.
+	 * corresponding entries in the guest's PSC buffer and zero out the
+	 * count of in-flight PSC entries.
 	 */
 	for (idx = svm->sev_es.psc_idx; svm->sev_es.psc_inflight;
 	     svm->sev_es.psc_inflight--, idx++) {
 		struct psc_entry *entry = &entries[idx];
 
-		entry->cur_page = svm->sev_es.psc_2m ? 512 : 1;
+		entry->cur_page = entry->pagesize ? 512 : 1;
 	}
 
 	hdr->cur_entry = idx;
+}
 
-	/* Handle the next range (if any). */
-	return snp_begin_psc(svm, psc);
+static int snp_complete_psc(struct kvm_vcpu *vcpu)
+{
+	struct vcpu_svm *svm = to_svm(vcpu);
+	struct psc_buffer *psc = svm->sev_es.ghcb_sa;
 
-out_resume:
-	svm->sev_es.psc_idx = 0;
-	svm->sev_es.psc_inflight = 0;
-	svm->sev_es.psc_2m = false;
-	ghcb_set_sw_exit_info_2(svm->sev_es.ghcb, psc_ret);
+	if (vcpu->run->hypercall.ret) {
+		snp_reset_inflight_psc(svm);
+		ghcb_set_sw_exit_info_2(svm->sev_es.ghcb, VMGEXIT_PSC_ERROR_GENERIC);
+		return 1; /* resume guest */
+	}
 
-	return 1; /* resume guest */
+	__snp_complete_psc(svm);
+
+	/* Handle the next range (if any). */
+	return snp_begin_psc(svm, psc);
 }
 
 static int snp_begin_psc(struct vcpu_svm *svm, struct psc_buffer *psc)
@@ -3634,6 +3641,7 @@ static int snp_begin_psc(struct vcpu_svm *svm, struct psc_buffer *psc)
 		goto out_resume;
 	}
 
+next_range:
 	/* Find the start of the next range which needs processing. */
 	for (idx = idx_start; idx <= idx_end; idx++, hdr->cur_entry++) {
 		__u16 cur_page;
@@ -3642,11 +3650,6 @@ static int snp_begin_psc(struct vcpu_svm *svm, struct psc_buffer *psc)
 
 		entry_start = entries[idx];
 
-		/* Only private/shared conversions are currently supported. */
-		if (entry_start.operation != VMGEXIT_PSC_OP_PRIVATE &&
-		    entry_start.operation != VMGEXIT_PSC_OP_SHARED)
-			continue;
-
 		gfn = entry_start.gfn;
 		cur_page = entry_start.cur_page;
 		huge = entry_start.pagesize;
@@ -3687,6 +3690,7 @@ static int snp_begin_psc(struct vcpu_svm *svm, struct psc_buffer *psc)
 
 		if (entry.operation != entry_start.operation ||
 		    entry.gfn != entry_start.gfn + npages ||
+		    entry.cur_page != 0 ||
 		    !!entry.pagesize != svm->sev_es.psc_2m)
 			break;
 
@@ -3694,6 +3698,25 @@ static int snp_begin_psc(struct vcpu_svm *svm, struct psc_buffer *psc)
 		npages += entry_start.pagesize ? 512 : 1;
 	}
 
+	/*
+	 * Only shared/private PSC operations are currently supported, so if the
+	 * entire range consists of unsupported operations (e.g. SMASH/UNSMASH),
+	 * then consider the entire range completed and avoid exiting to
+	 * userspace. In theory snp_complete_psc() can always be called directly
+	 * at this point to complete the current range and start the next one,
+	 * but that could lead to unexpected levels of recursion, so only do
+	 * that if there are no more entries to process and the entire request
+	 * has been completed.
+	 */
+	if (entry_start.operation != VMGEXIT_PSC_OP_PRIVATE &&
+	    entry_start.operation != VMGEXIT_PSC_OP_SHARED) {
+		if (idx > idx_end)
+			return snp_complete_psc(vcpu);
+
+		__snp_complete_psc(svm);
+		goto next_range;
+	}
+
 	vcpu->run->exit_reason = KVM_EXIT_HYPERCALL;
 	vcpu->run->hypercall.nr = KVM_HC_MAP_GPA_RANGE;
 	vcpu->run->hypercall.args[0] = gpa;
@@ -3709,9 +3732,7 @@ static int snp_begin_psc(struct vcpu_svm *svm, struct psc_buffer *psc)
 	return 0; /* forward request to userspace */
 
 out_resume:
-	svm->sev_es.psc_idx = 0;
-	svm->sev_es.psc_inflight = 0;
-	svm->sev_es.psc_2m = false;
+	snp_reset_inflight_psc(svm);
 	ghcb_set_sw_exit_info_2(svm->sev_es.ghcb, psc_ret);
 
 	return 1; /* resume guest */

---

## [4] Michael Roth — 2024-05-09
*Subject: Re: [PATCH v15 00/20] Add AMD Secure Nested Paging (SEV-SNP)
 Hypervisor Support*

On Tue, May 07, 2024 at 01:14:24PM -0500, Michael Roth wrote:
> On Tue, May 07, 2024 at 08:04:50PM +0200, Paolo Bonzini wrote:
> > On Wed, May 1, 2024 at 11:03 AM Michael Roth <michael.roth@amd.com> wrote:

In the process if adding some additional units tests we ran uncovered a
couple of other issues in addition to the fixups for PSC:

  [PATCH 21/20] KVM: MMU: Disable fast path for private memslots

    addresses an issue with fast_page_fault() handling that can lead to
    KVM_EXIT_MEMORY_FAULT cases being treated as spurious #NPFs which
    results in the guest spinning forever. This seems like it could be
    generally needed for both SNP/TDX, and would likely replace the need
    for this patch from the TDX series:
    
      KVM: x86/mmu: Disallow fast page fault on private GPA
      https://lore.kernel.org/lkml/91c797997b57056224571e22362321a23947172f.1705965635.git.isaku.yamahata@intel.com/

    This is a standalone patch and not really a fixup for anything

  [PATCH 22/20] KVM: SEV: Fix return code interpretation for RMP nested page faults

    addresses an issue where the return code of kvm_mmu_page_fault() was
    being misinterpreted, leading to sev_handle_rmp_fault() being called
    unecessarily in some cases. Interestingly, because
    sev_handle_rmp_fault() results in zapping sPTEs after PSMASH'ing them,
    this bug was hiding the issue addressed in the above PATCH 21 by
    forcing the fast path to get skipped. This can be squashed into:

      KVM: SEV: Add support to handle RMP nested page faults

  [PATCH 23/20] KVM: SEV: Fix PSC handling for SMASH/UNSMASH and partial update ops 

    fixes up the GHCB PSC handling code to address a number of situations
    that aren't triggered by normal SNP guests, but are allowed by the
    GHCB spec and could become issues with future/other guest
    implementations. This can be squashed into:

      KVM: SEV: Add support to handle Page State Change VMGEXIT

I've sent them all as a response to this series, but have them available
here applied on top of the your current kvm/queue (commit 15889fca49df):

  https://github.com/mdroth/linux/commits/snp-host-v15c2-unsquashed
  (the patch at the top can be ignored, it's only for testing 2MB gmem
   backing pages)

I've also put together a branch with the patches already squashed in
(except for "KVM: MMU: Disable fast path for private memslots" which is
a standalone patch that is likely applicable to both TDX and SNP, so
I've simply moved it to the beginning of the SNP series)

  https://github.com/mdroth/linux/commits/snp-host-v15c2

Sorry for the late fixes. Let me know if you want me to submit any of
these by some other means.

-Mike


> 
>

---

## [5] Sean Christopherson — 2024-05-10
*Subject: Re: [PATCH v15 21/23] KVM: MMU: Disable fast path for private memslots*

On Thu, May 09, 2024, Michael Roth wrote:
> ---
>  arch/x86/kvm/mmu/mmu.c | 30 ++++++++++++++++++++++++++++--

Very technically, it can occur if userspace _just_ modified the attributes.  And
as I've said multiple times, at least for now, I want to avoid special casing
SW-protected VMs unless it is *absolutely* necessary, because their sole purpose
is to allow testing flows that are impossible to excercise without SNP/TDX hardware.

> +	 */
> +	if (kvm_slot_can_be_private(fault->slot) &&

Heh, !(x && y) kills me, I misread this like 4 times.

Anyways, I don't like the heuristic.  It doesn't tie the restriction back to the
cause in any reasonable way.  Can't this simply be?

	if (fault->is_private != kvm_mem_is_private(vcpu->kvm, fault->gfn)
		return false;

Which is much, much more self-explanatory.

---

## [6] Paolo Bonzini — 2024-05-10
*Subject: Re: [PATCH v15 21/23] KVM: MMU: Disable fast path for private memslots*

On Fri, May 10, 2024 at 3:47 PM Sean Christopherson <seanjc@google.com> wrote:
>
> > +      * Since software-protected VMs don't have a notion of a shared vs.

Yep, it is not like they have to be optimized.

> > +      */
> > +     if (kvm_slot_can_be_private(fault->slot) &&

You beat me to it by seconds. And it can also be guarded by a check on
kvm->arch.has_private_mem to avoid the attributes lookup.

> Which is much, much more self-explanatory.

Both more self-explanatory and more correct.

Paolo

---

## [7] Sean Christopherson — 2024-05-10
*Subject: Re: [PATCH v15 22/23] KVM: SEV: Fix return code interpretation for
 RMP nested page faults*

On Thu, May 09, 2024, Michael Roth wrote:
> The intended logic when handling #NPFs with the RMP bit set (31) is to
> first check to see if the #NPF requires a shared<->private transition

This isn't correct either.  A return of '0' also indiciates "exit to userspace",
it just doesn't happen with SNP because '0' is returned only when KVM attempts
emulation, and that too gets short-circuited by svm_check_emulate_instruction().

And I would honestly drop the comment, KVM's less-than-pleasant 1/0/-errno return
values overload is ubiquitous enough that it should be relatively self-explanatory.

Or if you prefer to keep a comment, drop the part that specifically calls out
attributes updates, because that incorrectly implies that's the _only_ reason
why KVM checks the return.  But my vote is to drop the comment, because it
essentially becomes "don't proceed to step 2 if step 1 failed", which kind of
makes the reader go "well, yeah".

---

## [8] Michael Roth — 2024-05-10
*Subject: Re: [PATCH v15 21/23] KVM: MMU: Disable fast path for private
 memslots*

On Fri, May 10, 2024 at 03:50:26PM +0200, Paolo Bonzini wrote:
> On Fri, May 10, 2024 at 3:47 PM Sean Christopherson <seanjc@google.com> wrote:
> >

Ok, I thought there were maybe some future plans to use sw-protected VMs
to get some added protections from userspace. But even then there'd
probably still be extra considerations for how to handle access tracking
so white-listing them probably isn't right anyway.

I was also partly tempted to take this route because it would cover this
TDX patch as well:

  https://lore.kernel.org/lkml/91c797997b57056224571e22362321a23947172f.1705965635.git.isaku.yamahata@intel.com/

and avoid any weirdness about checking kvm_mem_is_private() without
checking mmu_invalidate_seq, but I think those cases all end up
resolving themselves eventually and added some comments around that.

> 
> > > +      */

I re-tested with things implemented this way and everything seems to
look good. It's not clear to me whether this would cover the cases the
above-mentioned TDX patch handles, but no biggie if that's still needed.

The new version of the patch is here:

  https://github.com/mdroth/linux/commit/39643f9f6da6265d39d633a703c53997985c1208

And I've updated my branches with to replace the old patch and also
incorporate Sean's suggestions for patch 22:

  https://github.com/mdroth/linux/commits/snp-host-v15c3-unsquashed

and have them here with things already squashed in/relocated:

  https://github.com/mdroth/linux/commits/snp-host-v15c3

Thanks for the feedback Sean, Paolo.

-Mike
  
> 
> > Which is much, much more self-explanatory.

---

## [9] Michael Roth — 2024-05-10
*Subject: Re: [PATCH v15 22/23] KVM: SEV: Fix return code interpretation for
 RMP nested page faults*

On Fri, May 10, 2024 at 06:58:45AM -0700, Sean Christopherson wrote:
> On Thu, May 09, 2024, Michael Roth wrote:
> > The intended logic when handling #NPFs with the RMP bit set (31) is to

Ok, I think I was just paranoid after missing this. I've gone ahead and
dropped the comment, and hopefully it's now drilled into my head enough
that it's obvious to me now as well :) I've also changed the logic to
skip the extra RMP handling for rc==0 as well (should that ever arise
for any future reason):

  https://github.com/mdroth/linux/commit/0a0ba0d7f7571a31f0abc68acc51f24c2a14a8cf

Thanks!

-Mike

---

## [10] Sean Christopherson — 2024-05-10
*Subject: Re: [PATCH v15 21/23] KVM: MMU: Disable fast path for private memslots*

On Fri, May 10, 2024, Michael Roth wrote:
> On Fri, May 10, 2024 at 03:50:26PM +0200, Paolo Bonzini wrote:
> > On Fri, May 10, 2024 at 3:47 PM Sean Christopherson <seanjc@google.com> wrote:

Hmm, I'm pretty sure that patch is trying to fix the exact same issue you are
fixing, just in a less precise way.  S-EPT entries only support RWX=0 and RWX=111b,
i.e. it should be impossible to have a write-fault to a present S-EPT entry.

And if TDX is running afoul of this code:

	if (!fault->present)
		return !kvm_ad_enabled();

then KVM should do the sane thing and require A/D support be enabled for TDX.

And if it's something else entirely, that changelog has some explaining to do.

> and avoid any weirdness about checking kvm_mem_is_private() without
> checking mmu_invalidate_seq, but I think those cases all end up

Yep, checking state that is protected by mmu_invalidate_seq outside of mmu_lock
is definitely allowed, e.g. the entire fast page fault path operates outside of
mmu_lock and thus outside of mmu_invalidate_seq's purview.

It's a-ok because the SPTE are done with an atomic CMPXCHG, and so KVM only needs
to ensure its page tables aren't outright _freed_.  If the zap triggered by the
attributes change "wins", then the fast #PF path will fail the CMPXCHG and be an
expensive NOP.  If the fast #PF wins, the zap will pave over the fast #PF fix,
and the IPI+flush that is needed for all zaps, to ensure vCPUs don't have stale
references, does the rest.

And if there's an attributes race that causes the fast #PF to bail early, the vCPU
will see the correct state on the next page fault.

---

## [11] Paolo Bonzini — 2024-05-10
*Subject: Re: [PATCH v15 22/23] KVM: SEV: Fix return code interpretation for
 RMP nested page faults*

On 5/10/24 15:58, Sean Christopherson wrote:
> On Thu, May 09, 2024, Michael Roth wrote:
>> The intended logic when handling #NPFs with the RMP bit set (31) is to

So IIUC you're suggesting

diff --git a/arch/x86/kvm/svm/svm.c b/arch/x86/kvm/svm/svm.c
index 426ad49325d7..c39eaeb21981 100644
--- a/arch/x86/kvm/svm/svm.c
+++ b/arch/x86/kvm/svm/svm.c
@@ -2068,16 +2068,11 @@ static int npf_interception(struct kvm_vcpu *vcpu)
  				static_cpu_has(X86_FEATURE_DECODEASSISTS) ?
  				svm->vmcb->control.insn_bytes : NULL,
  				svm->vmcb->control.insn_len);
+	if (rc <= 0)
+		return rc;
  
-	/*
-	 * rc == 0 indicates a userspace exit is needed to handle page
-	 * transitions, so do that first before updating the RMP table.
-	 */
-	if (error_code & PFERR_GUEST_RMP_MASK) {
-		if (rc == 0)
-			return rc;
+	if (error_code & PFERR_GUEST_RMP_MASK)
  		sev_handle_rmp_fault(vcpu, fault_address, error_code);
-	}
  
  	return rc;
  }

?

So, we're... a bit tight for 6.10 to include SNP and that is an
understatement.  My plan is to merge it for 6.11, but do so
immediately after the merge window ends.  In other words, it
is a delay in terms of release but not in terms of time.  I
don't want QEMU and kvm-unit-tests work to be delayed any
further, in particular.

Once we sort out the loose ends of patches 21-23, you could send
it as a pull request.

Paolo

---

## [12] Michael Roth — 2024-05-10
*Subject: Re: [PATCH v15 22/23] KVM: SEV: Fix return code interpretation for
 RMP nested page faults*

On Fri, May 10, 2024 at 06:01:52PM +0200, Paolo Bonzini wrote:
> On 5/10/24 15:58, Sean Christopherson wrote:
> > On Thu, May 09, 2024, Michael Roth wrote:

That's unfortunate, I'd thought from the PUCK call that we still had
some time to stabilize things before merge window. But whatever you
think is best.

> 
> Once we sort out the loose ends of patches 21-23, you could send

Ok, as a pull request against kvm/next, or kvm/queue?

Thanks,

Mike

> 
> Paolo

---

## [13] Paolo Bonzini — 2024-05-10
*Subject: Re: [PATCH v15 22/23] KVM: SEV: Fix return code interpretation for
 RMP nested page faults*

On 5/10/24 18:37, Michael Roth wrote:
>> So, we're... a bit tight for 6.10 to include SNP and that is an
>> understatement.  My plan is to merge it for 6.11, but do so

Well, the merge window starts next sunday, doesn't it?  If there's an 
-rc8 I agree there's some leeway, but that is not too likely.

>> Once we sort out the loose ends of patches 21-23, you could send
>> it as a pull request.

Against kvm/next.

Paolo

---

## [14] Paolo Bonzini — 2024-05-10
*Subject: Re: [PATCH v15 23/23] KVM: SEV: Fix PSC handling for SMASH/UNSMASH
 and partial update ops*

On 5/10/24 03:58, Michael Roth wrote:
> There are a few edge-cases that the current processing for GHCB PSC
> requests doesn't handle properly:

There are some more improvements that can be made to the readability of
the code... this one is already better than the patch is fixing up, but I
don't like the code that is in the loop even though it is unconditionally
followed by "break".

Here's my attempt at replacing this patch, which is really more of a
rewrite of the whole function...  Untested beyond compilation.

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 35f0bd91f92e..6e612789c35f 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -3555,23 +3555,25 @@ struct psc_buffer {
  
  static int snp_begin_psc(struct vcpu_svm *svm, struct psc_buffer *psc);
  
-static int snp_complete_psc(struct kvm_vcpu *vcpu)
+static void snp_complete_psc(struct vcpu_svm *svm, u64 psc_ret)
+{
+	svm->sev_es.psc_inflight = 0;
+	svm->sev_es.psc_idx = 0;
+	svm->sev_es.psc_2m = 0;
+	ghcb_set_sw_exit_info_2(svm->sev_es.ghcb, psc_ret);
+}
+
+static void __snp_complete_one_psc(struct vcpu_svm *svm)
  {
-	struct vcpu_svm *svm = to_svm(vcpu);
  	struct psc_buffer *psc = svm->sev_es.ghcb_sa;
  	struct psc_entry *entries = psc->entries;
  	struct psc_hdr *hdr = &psc->hdr;
-	__u64 psc_ret;
  	__u16 idx;
  
-	if (vcpu->run->hypercall.ret) {
-		psc_ret = VMGEXIT_PSC_ERROR_GENERIC;
-		goto out_resume;
-	}
-
  	/*
  	 * Everything in-flight has been processed successfully. Update the
-	 * corresponding entries in the guest's PSC buffer.
+	 * corresponding entries in the guest's PSC buffer and zero out the
+	 * count of in-flight PSC entries.
  	 */
  	for (idx = svm->sev_es.psc_idx; svm->sev_es.psc_inflight;
  	     svm->sev_es.psc_inflight--, idx++) {
@@ -3581,17 +3583,22 @@ static int snp_complete_psc(struct kvm_vcpu *vcpu)
  	}
  
  	hdr->cur_entry = idx;
+}
+
+static int snp_complete_one_psc(struct kvm_vcpu *vcpu)
+{
+	struct vcpu_svm *svm = to_svm(vcpu);
+	struct psc_buffer *psc = svm->sev_es.ghcb_sa;
+
+	if (vcpu->run->hypercall.ret) {
+		snp_complete_psc(svm, VMGEXIT_PSC_ERROR_GENERIC);
+		return 1; /* resume guest */
+	}
+
+	__snp_complete_one_psc(svm);
  
  	/* Handle the next range (if any). */
  	return snp_begin_psc(svm, psc);
-
-out_resume:
-	svm->sev_es.psc_idx = 0;
-	svm->sev_es.psc_inflight = 0;
-	svm->sev_es.psc_2m = false;
-	ghcb_set_sw_exit_info_2(svm->sev_es.ghcb, psc_ret);
-
-	return 1; /* resume guest */
  }
  
  static int snp_begin_psc(struct vcpu_svm *svm, struct psc_buffer *psc)
@@ -3601,18 +3608,20 @@ static int snp_begin_psc(struct vcpu_svm *svm, struct psc_buffer *psc)
  	struct psc_hdr *hdr = &psc->hdr;
  	struct psc_entry entry_start;
  	u16 idx, idx_start, idx_end;
-	__u64 psc_ret, gpa;
+	u64 gfn;
  	int npages;
-
-	/* There should be no other PSCs in-flight at this point. */
-	if (WARN_ON_ONCE(svm->sev_es.psc_inflight)) {
-		psc_ret = VMGEXIT_PSC_ERROR_GENERIC;
-		goto out_resume;
-	}
+	bool huge;
  
  	if (!(vcpu->kvm->arch.hypercall_exit_enabled & (1 << KVM_HC_MAP_GPA_RANGE))) {
-		psc_ret = VMGEXIT_PSC_ERROR_GENERIC;
-		goto out_resume;
+		snp_complete_psc(svm, VMGEXIT_PSC_ERROR_GENERIC);
+		return 1;
+	}
+
+next_range:
+	/* There should be no other PSCs in-flight at this point. */
+	if (WARN_ON_ONCE(svm->sev_es.psc_inflight)) {
+		snp_complete_psc(svm, VMGEXIT_PSC_ERROR_GENERIC);
+		return 1;
  	}
  
  	/*
@@ -3624,97 +3633,99 @@ static int snp_begin_psc(struct vcpu_svm *svm, struct psc_buffer *psc)
  	idx_end = hdr->end_entry;
  
  	if (idx_end >= VMGEXIT_PSC_MAX_COUNT) {
-		psc_ret = VMGEXIT_PSC_ERROR_INVALID_HDR;
-		goto out_resume;
-	}
-
-	/* Nothing more to process. */
-	if (idx_start > idx_end) {
-		psc_ret = 0;
-		goto out_resume;
+		snp_complete_psc(svm, VMGEXIT_PSC_ERROR_INVALID_HDR);
+		return 1;
  	}
  
  	/* Find the start of the next range which needs processing. */
  	for (idx = idx_start; idx <= idx_end; idx++, hdr->cur_entry++) {
-		__u16 cur_page;
-		gfn_t gfn;
-		bool huge;
-
  		entry_start = entries[idx];
-
-		/* Only private/shared conversions are currently supported. */
-		if (entry_start.operation != VMGEXIT_PSC_OP_PRIVATE &&
-		    entry_start.operation != VMGEXIT_PSC_OP_SHARED)
-			continue;
-
  		gfn = entry_start.gfn;
-		cur_page = entry_start.cur_page;
  		huge = entry_start.pagesize;
+		npages = huge ? 512 : 1;
  
-		if ((huge && (cur_page > 512 || !IS_ALIGNED(gfn, 512))) ||
-		    (!huge && cur_page > 1)) {
-			psc_ret = VMGEXIT_PSC_ERROR_INVALID_ENTRY;
-			goto out_resume;
+		if (entry_start.cur_page > npages || !IS_ALIGNED(gfn, npages)) {
+			snp_complete_psc(svm, VMGEXIT_PSC_ERROR_INVALID_ENTRY);
+			return 1;
  		}
  
+		if (entry_start.cur_page) {
+			/*
+			 * If this is a partially-completed 2M range, force 4K
+			 * handling for the remaining pages since they're effectively
+			 * split at this point. Subsequent code should ensure this
+			 * doesn't get combined with adjacent PSC entries where 2M
+			 * handling is still possible.
+			 */
+			npages -= entry_start.cur_page;
+			gfn += entry_start.cur_page;
+			huge = false;
+		}
+		if (npages)
+			break;
+
  		/* All sub-pages already processed. */
-		if ((huge && cur_page == 512) || (!huge && cur_page == 1))
-			continue;
-
-		/*
-		 * If this is a partially-completed 2M range, force 4K handling
-		 * for the remaining pages since they're effectively split at
-		 * this point. Subsequent code should ensure this doesn't get
-		 * combined with adjacent PSC entries where 2M handling is still
-		 * possible.
-		 */
-		svm->sev_es.psc_2m = cur_page ? false : huge;
-		svm->sev_es.psc_idx = idx;
-		svm->sev_es.psc_inflight = 1;
-
-		gpa = gfn_to_gpa(gfn + cur_page);
-		npages = huge ? 512 - cur_page : 1;
-		break;
  	}
  
+	if (idx > idx_end) {
+		/* Nothing more to process. */
+		snp_complete_psc(svm, 0);
+		return 1;
+	}
+
+	svm->sev_es.psc_2m = huge;
+	svm->sev_es.psc_idx = idx;
+	svm->sev_es.psc_inflight = 1;
+
  	/*
  	 * Find all subsequent PSC entries that contain adjacent GPA
  	 * ranges/operations and can be combined into a single
  	 * KVM_HC_MAP_GPA_RANGE exit.
  	 */
-	for (idx = svm->sev_es.psc_idx + 1; idx <= idx_end; idx++) {
+	while (++idx <= idx_end) {
  		struct psc_entry entry = entries[idx];
  
  		if (entry.operation != entry_start.operation ||
-		    entry.gfn != entry_start.gfn + npages ||
-		    !!entry.pagesize != svm->sev_es.psc_2m)
+		    entry.gfn != gfn + npages ||
+		    entry.cur_page ||
+		    !!entry.pagesize != huge)
  			break;
  
  		svm->sev_es.psc_inflight++;
-		npages += entry_start.pagesize ? 512 : 1;
+		npages += huge ? 512 : 1;
  	}
  
-	vcpu->run->exit_reason = KVM_EXIT_HYPERCALL;
-	vcpu->run->hypercall.nr = KVM_HC_MAP_GPA_RANGE;
-	vcpu->run->hypercall.args[0] = gpa;
-	vcpu->run->hypercall.args[1] = npages;
-	vcpu->run->hypercall.args[2] = entry_start.operation == VMGEXIT_PSC_OP_PRIVATE
-				       ? KVM_MAP_GPA_RANGE_ENCRYPTED
-				       : KVM_MAP_GPA_RANGE_DECRYPTED;
-	vcpu->run->hypercall.args[2] |= entry_start.pagesize
-					? KVM_MAP_GPA_RANGE_PAGE_SZ_2M
-					: KVM_MAP_GPA_RANGE_PAGE_SZ_4K;
-	vcpu->arch.complete_userspace_io = snp_complete_psc;
+	switch (entry_start.operation) {
+	case VMGEXIT_PSC_OP_PRIVATE:
+	case VMGEXIT_PSC_OP_SHARED:
+		vcpu->run->exit_reason = KVM_EXIT_HYPERCALL;
+		vcpu->run->hypercall.nr = KVM_HC_MAP_GPA_RANGE;
+		vcpu->run->hypercall.args[0] = gfn_to_gpa(gfn);
+		vcpu->run->hypercall.args[1] = npages;
+		vcpu->run->hypercall.args[2] = entry_start.operation == VMGEXIT_PSC_OP_PRIVATE
+			? KVM_MAP_GPA_RANGE_ENCRYPTED
+			: KVM_MAP_GPA_RANGE_DECRYPTED;
+		vcpu->run->hypercall.args[2] |= huge
+			? KVM_MAP_GPA_RANGE_PAGE_SZ_2M
+			: KVM_MAP_GPA_RANGE_PAGE_SZ_4K;
+		vcpu->arch.complete_userspace_io = snp_complete_one_psc;
  
-	return 0; /* forward request to userspace */
+		return 0; /* forward request to userspace */
  
-out_resume:
-	svm->sev_es.psc_idx = 0;
-	svm->sev_es.psc_inflight = 0;
-	svm->sev_es.psc_2m = false;
-	ghcb_set_sw_exit_info_2(svm->sev_es.ghcb, psc_ret);
+	default:
+		/*
+		 * Only shared/private PSC operations are currently supported, so if the
+		 * entire range consists of unsupported operations (e.g. SMASH/UNSMASH),
+		 * then consider the entire range completed and avoid exiting to
+		 * userspace. In theory snp_complete_psc() can be called directly
+		 * at this point to complete the current range and start the next one,
+		 * but that could lead to unexpected levels of recursion.
+		 */
+		__snp_complete_one_psc(svm);
+		goto next_range;
+	}
  
-	return 1; /* resume guest */
+	unreachable();
  }
  
  static int __sev_snp_update_protected_guest_state(struct kvm_vcpu *vcpu)

---

## [15] Paolo Bonzini — 2024-05-10
*Subject: Re: [PATCH v15 22/23] KVM: SEV: Fix return code interpretation for
 RMP nested page faults*

On Fri, May 10, 2024 at 6:59 PM Paolo Bonzini <pbonzini@redhat.com> wrote:
> Well, the merge window starts next sunday, doesn't it?  If there's an
> -rc8 I agree there's some leeway, but that is not too likely.

Ah no, only kvm/queue has the preparatory hooks - they make no sense
without something that uses them.  kvm/queue is ready now.

Also, please send the pull request "QEMU style", i.e. with patches
as replies.

If there's an -rc8, I'll probably pull it on Thursday morning.

Paolo

---

## [16] Isaku Yamahata — 2024-05-10
*Subject: Re: [PATCH v15 21/23] KVM: MMU: Disable fast path for private
 memslots*

On Fri, May 10, 2024 at 08:59:09AM -0700,
Sean Christopherson <seanjc@google.com> wrote:

> On Fri, May 10, 2024, Michael Roth wrote:
> > On Fri, May 10, 2024 at 03:50:26PM +0200, Paolo Bonzini wrote:

Yes, it's for KVM_EXIT_MEMORY_FAULT case.  Because Secure-EPT has non-present or
all RWX allowed, fast page fault always returns RET_PF_INVALID by
is_shadow_present_pte() check.

I lightly tested the patch at [1] and it works for TDX KVM.

[1] https://github.com/mdroth/linux/commit/39643f9f6da6265d39d633a703c53997985c1208

Just in case for that patch,
Reviewed-by: Isaku Yamahata <isaku.yamahata@intel.com>

---

## [17] Michael Roth — 2024-05-10
*Subject: Re: [PATCH v15 23/23] KVM: SEV: Fix PSC handling for SMASH/UNSMASH
 and partial update ops*

On Fri, May 10, 2024 at 07:09:07PM +0200, Paolo Bonzini wrote:
> On 5/10/24 03:58, Michael Roth wrote:
> > There are a few edge-cases that the current processing for GHCB PSC

Thanks for the suggested rework. I tested with/without 2MB pages and
everything worked as-written. This is the full/squashed patch I plan to
include in the pull request:

  https://github.com/mdroth/linux/commit/91f6d31c4dfc88dd1ac378e2db6117b0c982e63c

-Mike

> 
> diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c

---

## [18] Sean Christopherson — 2024-05-13
*Subject: Re: [PATCH v15 19/20] KVM: SEV: Provide support for
 SNP_EXTENDED_GUEST_REQUEST NAE event*

On Wed, May 01, 2024, Michael Roth wrote:
> Version 2 of GHCB specification added support for the SNP Extended Guest
> Request Message NAE event. This event serves a nearly identical purpose

LOL, it looks dumb, but maybe kvm_vmgexit_exit to avoid confusing about whether
the struct refers to host userspace vs. guest userspace?

Actually, I vote to punt on naming until more exits need to be kicked to userspace,
and just do (see below for details on how I got here):

		/* KVM_EXIT_VMGEXIT */
		struct {
			__u64 exit_code;
			union {
				struct {
					__u64 data_gpa;
					__u64 data_npages;
					__u64 ret;
				} req_certs;
			};
		} vmgexit;

> +  #define KVM_USER_VMGEXIT_REQ_CERTS		1
> +			__u32 type; /* KVM_USER_VMGEXIT_* type */

Regardless of whether or not requesting a certificate is vendor specific enough
to justify its own exit reason, I don't think KVM should have a #VMGEXIT that
adds its own layer.  Structuring the user exit this way will make it weird and/or
difficult to handle #VMGEXITs that _do_ fit a generic pattern, e.g. a user might
wonder why PSC #VMGEXITs don't show up here.

And defining an exit reason that is, for all intents and purposes, a regurgitation
of the raw #VMGEXIT reason, but with a different value, is also confusing.  E.g.
it wouldn't be unreasonable for a reader to expect that "type" matches the value
defined in the GHCB (or whever the values are defined).

Ah, you copied what KVM does for Hyper-V and Xen emulation.  Hrm.  But only
partially.

Assuming it's impractical to have a generic user exit for this, and we think
there is a high likelihood of needing to punt more #VMGEXITs to userspace, then
we should more closely (perhaps even exactly) follow the Hyper-V and Xen models.
I.e. for all values and whanot that are controlled/defined by a third party
(Hyper-V, Xen, the GHCB, etc.) #define those values in a header that is clearly
"owned" by the third party.

E.g. IIRC, include/xen/interface/xen.h is copied verbatim from Xen documentation
(source?).  And include/asm-generic/hyperv-tlfs.h is the kernel's copy of the
TLFS, which dictates all of the Hyper-V hypercalls.

If we do that, then my concerns/objections largely go away, e.g. KVM isn't
defining magic values, there's less chance for confusion about what "type" holds,
etc.

Oh, and if we go that route, the sizes for all fields should follow the GHCB,
e.g. I believe the "type" should be a __u64.

> +			union {
> +				struct {

Hopefully it won't matter, but are BUSY and GENERIC actually defined somewhere?
I don't see them in GHCB 2.0.

In a perfect world, it would be nice for KVM to not have to care about the error
codes.  But KVM disallows KVM_{G,S}ET_REGS for guest with protected state, which
means it's not feasible for userspace to set registers, at least not in any sane
way.

Heh, we could abuse KVM_SYNC_X86_REGS to let userspace specify RBX, but (a) that's
gross, and (b) KVM_SYNC_X86_REGS and KVM_SYNC_X86_SREGS really ought to be rejected
if guest state is protected.

> +					__u32 ret;
> +  #define KVM_USER_VMGEXIT_REQ_CERTS_FLAGS_NOTIFY_DONE	BIT(0)

This has no business being buried in a VMGEXIT_REQ_CERTS flags.  Notifying
userspace that KVM completed its portion of a userspace exit is completely generic.

And aside from where the notification flag lives, _if_ we add a notification
mechanism, it belongs in a separate patch, because it's purely a performance
optimization.  Userspace can use immediate_exit to force KVM to re-exit after
completing an exit.

Actually, I take that back, this isn't even an optimization, it's literally a
non-generic implementation of kvm_run.immediate_exit.

If this were an optimization, i.e. KVM truly notified userspace without exiting,
then it would need to be a lot more robust, e.g. to ensure userspace actually
received the notification before KVM moved on.

> +					__u8 flags;
> +  #define KVM_USER_VMGEXIT_REQ_CERTS_STATUS_PENDING	0

This is also a weird reimplementation of generic functionality.  KVM nullifies
vcpu->arch.complete_userspace_io _before_ invoking the callback.  So if a callback
needs to run again on the next KVM_RUN, it can simply set complete_userspace_io
again.  In other words, literally doing nothing will get you what you want :-)

> +					__u8 status;
> +				} req_certs;

---

## [19] Michael Roth — 2024-05-13
*Subject: Re: [PATCH v15 19/20] KVM: SEV: Provide support for
 SNP_EXTENDED_GUEST_REQUEST NAE event*

On Mon, May 13, 2024 at 04:48:25PM -0700, Sean Christopherson wrote:
> On Wed, May 01, 2024, Michael Roth wrote:
> > Version 2 of GHCB specification added support for the SNP Extended Guest

The type in this case is actually "extended guest request". You'd rightly
pointed out that that is miles away from describing what KVM wants
userspace to do, so I named it "request certificate". And now with PSC being
handled as seperate KVM_HC_MAP_GPA_RANGE event with no exposure of GHCB/etc
to userspace, it made further sense to not lean too heavily on the GHCB for
defining the types.

But continuing to name it KVM_EXIT_VMGEXIT sort of goes against that
decoupling, so I can see some potential for confusion there. KVM_EXIT_SNP is
probably a better generic name for what this exit is meant to cover. But I'm
not aware of anything specific that would involve requiring extending this in
the near-term, though maybe there's some potential with live migration. So a
renaming to something more generic and less specific to VMGEXIT/GHCB,
like KVM_EXIT_SNP, or something more specific like KVM_EXIT_SNP_REQ_CERTS,
both seem warranted, but I don't think moving to something more coupled to
VMGEXIT/GHCB would provide much benefit long-term.

> 
> Ah, you copied what KVM does for Hyper-V and Xen emulation.  Hrm.  But only

BUSY is defined in 4.1.7:

  It is not expected that a guest would issue many Guest Request NAE
  events. However, access to the SNP firmware is a sequential and
  synchronous operation. To avoid the possibility of a guest creating a
  denial-of-service attack against the SNP firmware, it is recommended
  that some form of rate limiting be implemented should it be detected
  that a high number of Guest Request NAE events are being issued. To
  allow for this, the hypervisor may set the SW_EXITINFO2 field to
  0x0000000200000000, which will inform the guest to retry the request

INVALID_LEN in 4.1.8.1:

  The hypervisor must validate that the guest has supplied enough pages
  to hold the certificates that will be returned before performing the SNP
  guest request. If there are not enough guest pages to hold the certificate
  table and certificate data, the hypervisor will return the required number
  of pages needed to hold the certificate table and certificate data in the
  RBX register and set the SW_EXITINFO2 field to 0x0000000100000000.

and GENERIC chosen to provide an non-zero error code that doesn't
conflict with that above (or future) GHCB-defined values. But KVM isn't
trying to expose the actual GHCB details, like how these values are to be in
the upper 32-bits of SW_EXITINFO2, it just re-uses the values to avoid
purposefully obfuscating the GHCB return codes they relate to.

> 
> In a perfect world, it would be nice for KVM to not have to care about the error

Relying on a generic -EINTR response resulting from kvm_run.immediate_exit
doesn't seem like a very robust way to ensure the attestation request
was made to firmware. It seems fully possible that future code changes
could result in EINTR being returned for other reasons. So how do you
reliably detect that the EINTR is a result of immediate_exit being called
after the attestation request is made to firmware? We could squirrel something
away in struct kvm_run to probe for, but delivering another
KVM_EXIT_SNP_REQ_CERT with an extra flag set seems to be reasonably
userspace-friendly.

> 
> If this were an optimization, i.e. KVM truly notified userspace without exiting,

Right, this does rely on exiting via , not userspace polling for flags or
anything along that line.

> 
> > +					__u8 flags;

We could just have the completion callback set complete_userspace_io
again, but then you'd always get 2 userspace exit events per attestation
request. There could be some userspaces that don't implement the
file-locking scheme, in which case they wouldn't need the 2nd notification.
That's why the KVM_USER_VMGEXIT_REQ_CERTS_FLAGS_NOTIFY_DONE flag is provided
as an opt-in.

The pending/done status bits are so userspace can distinguish between the
start of a certificate request and the completion side of it after it gets
bound a completed attestation request and the filelock can be released.

Thanks,

Mike

> 
> > +					__u8 status;

---

## [20] Borislav Petkov — 2024-05-14
*Subject: Re: [PATCH v15 22/23] KVM: SEV: Fix return code interpretation for RMP nested page faults*

On May 10, 2024 6:59:37 PM GMT+02:00, Paolo Bonzini <pbonzini@redhat.com> wrote:
>Well, the merge window starts next sunday, doesn't it?  If there's an -rc8 I agree there's some leeway, but that is not too likely.

Nah, the merge window just opened yesterday.

---

## [21] Sean Christopherson — 2024-05-14
*Subject: Re: [PATCH v15 19/20] KVM: SEV: Provide support for
 SNP_EXTENDED_GUEST_REQUEST NAE event*

On Mon, May 13, 2024, Michael Roth wrote:
> On Mon, May 13, 2024 at 04:48:25PM -0700, Sean Christopherson wrote:
> > Actually, I take that back, this isn't even an optimization, it's literally a

And unnecessarily specific to a single exit.  But it's a non-issue (except
possibly on ARM).

I doubt it's formally documented anywhere, but userspace absolutely relies on
kvm_run.immediate_exit to be processed _after_ complete_userspace_io().  If KVM
exits with -EINTR before invoking cui(), live migration will break due to taking
a snapshot of vCPU state in the middle of an instruction.

Given that userspace has likely built up rigid expectations for immediate_exit,
I don't see any problem formally documenting KVM's behavior, i.e. signing a
contract guaranteeing that KVM will complete the "back half" of emulation if
immediate_exit is set and KVM_RUN return -EINTR.

ARM is the only arch that is at all suspect, due to its rather massive
kvm_arch_vcpu_run_pid_change() hook.  At a quick glance, it seems to be ok, too.
And if it's not, we need to fix that asap, because it's like a bug waiting to
happen.

> > If this were an optimization, i.e. KVM truly notified userspace without exiting,
> > then it would need to be a lot more robust, e.g. to ensure userspace actually

Then they don't set immediate_exit.

> That's why the KVM_USER_VMGEXIT_REQ_CERTS_FLAGS_NOTIFY_DONE flag is provided
> as an opt-in.

---

## [22] Michael Roth — 2024-05-14
*Subject: [PATCH] KVM: SEV: Replace KVM_EXIT_VMGEXIT with KVM_EXIT_SNP_REQ_CERTS*

It's not clear if SNP guests will need any other SNP-specific userspace
exit types in the future, and if they do, it's not clear that they would
necessary be related to VMGEXIT events or something else entirely.

So, rather than trying to anticipate future use-cases and have a single
union structure to manage the associated parameters, just use a common
KVM_EXIT_SNP_* prefix, but otherwise treat these as separate events, and
go ahead and convert the only VMGEXIT type currently defined,
KVM_USER_VMGEXIT_REQ_CERTS, over to KVM_EXIT_SNP_REQ_CERTS.

Also, formally document that kvm_run->immediate_exit is guaranteed to
handle userspace IO completion callbacks before returning to userspace
with -EINTR, and use this mechanism to allow userspace to use this
mechanism as a means to know when an attestation request is complete and
the KVM_EXIT_SNP_REQ_CERTS event is fully-finished, allowing userspace
to at that point handle any certificate synchronization cleanup like
releasing file locks/etc.

Suggested-by: Sean Christopherson <seanjc@google.com>
Signed-off-by: Michael Roth <michael.roth@amd.com>
---
Hi Sean,

Here's an attempt to address your concerns regarding
KVM_EXIT_VMGEXIT/KVM_USER_VMGEXIT_REQ_CERTS. Please let me know what
you think.

The main gist of it is that it leverages kvm->immediate_edit rather than
a flag in the kvm_run exit struct to receive notification when the
attestation has been completed and the certificate is no longer needed.

Additionally it drops the confusing KVM_EXIT_VMGEXIT naming in favor of
the KVM_EXIT_SNP_* prefix, and rather than introduce infrastructure and
a union to handle other SNP-specific types in the future, it simply
defines KVM_EXIT_SNP_REQ_CERTS as a one-off event so we are free to
handle future SNP-specific/SNP-related userspace exits however makes
sense for future cases.

Thanks,

Mike

 Documentation/virt/kvm/api.rst | 64 +++++++++++-----------------------
 arch/x86/kvm/svm/sev.c         | 28 +++------------
 include/uapi/linux/kvm.h       | 31 ++++++++--------
 3 files changed, 43 insertions(+), 80 deletions(-)

diff --git a/Documentation/virt/kvm/api.rst b/Documentation/virt/kvm/api.rst
index 6ab8b5b7c64e..ea05c16f3438 100644
--- a/Documentation/virt/kvm/api.rst
+++ b/Documentation/virt/kvm/api.rst
@@ -6381,6 +6381,11 @@ to avoid usage of KVM_SET_SIGNAL_MASK, which has worse scalability.
 Rather than blocking the signal outside KVM_RUN, userspace can set up
 a signal handler that sets run->immediate_exit to a non-zero value.
 
+Also note that any KVM_EXIT_* events that have associated completion
+callbacks that KVM needs to process when KVM_RUN is called will be
+processed *before* exiting again to userspace with -EINTR as a result
+of run->immediate_exit.
+
 This field is ignored if KVM_CAP_IMMEDIATE_EXIT is not available.
 
 ::
@@ -7069,50 +7074,24 @@ values in kvm_run even if the corresponding bit in kvm_dirty_regs is not set.
 
 ::
 
-		/* KVM_EXIT_VMGEXIT */
-		struct kvm_user_vmgexit {
-  #define KVM_USER_VMGEXIT_REQ_CERTS		1
-			__u32 type; /* KVM_USER_VMGEXIT_* type */
-			union {
-				struct {
-					__u64 data_gpa;
-					__u64 data_npages;
-  #define KVM_USER_VMGEXIT_REQ_CERTS_ERROR_INVALID_LEN   1
-  #define KVM_USER_VMGEXIT_REQ_CERTS_ERROR_BUSY          2
-  #define KVM_USER_VMGEXIT_REQ_CERTS_ERROR_GENERIC       (1 << 31)
-					__u32 ret;
-  #define KVM_USER_VMGEXIT_REQ_CERTS_FLAGS_NOTIFY_DONE	BIT(0)
-					__u8 flags;
-  #define KVM_USER_VMGEXIT_REQ_CERTS_STATUS_PENDING	0
-  #define KVM_USER_VMGEXIT_REQ_CERTS_STATUS_DONE		1
-					__u8 status;
-				} req_certs;
-			};
-		};
-
-
-If exit reason is KVM_EXIT_VMGEXIT then it indicates that an SEV-SNP guest
-has issued a VMGEXIT instruction (as documented by the AMD Architecture
-Programmer's Manual (APM)) to the hypervisor that needs to be serviced by
-userspace. These are generally handled by the host kernel, but in some
-cases some aspects of handling a VMGEXIT are done in userspace.
-
-A kvm_user_vmgexit structure is defined to encapsulate the data to be
-sent to or returned by userspace. The type field defines the specific type
-of exit that needs to be serviced, and that type is used as a discriminator
-to determine which union type should be used for input/output.
-
-KVM_USER_VMGEXIT_REQ_CERTS
---------------------------
+		/* KVM_EXIT_SNP_REQ_CERTS */
+		struct {
+			__u64 data_gpa;
+			__u64 data_npages;
+  #define KVM_EXIT_SNP_REQ_CERTS_ERROR_INVALID_LEN   1
+  #define KVM_EXIT_SNP_REQ_CERTS_ERROR_BUSY          2
+  #define KVM_EXIT_SNP_REQ_CERTS_ERROR_GENERIC       (1 << 31)
+			__u32 ret;
+		} snp_req_certs;
 
 When an SEV-SNP issues a guest request for an attestation report, it has the
 option of issuing it in the form an *extended* guest request when a
 certificate blob is returned alongside the attestation report so the guest
 can validate the endorsement key used by SNP firmware to sign the report.
 These certificates are managed by userspace and are requested via
-KVM_EXIT_VMGEXITs using the KVM_USER_VMGEXIT_REQ_CERTS type.
+KVM_EXIT_SNP exits using the KVM_EXIT_SNP_REQ_CERTS type.
 
-For the KVM_USER_VMGEXIT_REQ_CERTS type, the req_certs union type
+For the KVM_EXIT_SNP_REQ_CERTS type, the req_certs union type
 is used. The kernel will supply in 'data_gpa' the value the guest supplies
 via the RAX field of the GHCB when issuing extended guest requests.
 'data_npages' will similarly contain the value the guest supplies in RBX
@@ -7139,12 +7118,11 @@ this is for the VMM to obtain a shared or exclusive lock on the path the
 certificate blob file resides at before reading it and returning it to KVM,
 and that it continues to hold the lock until the attestation request is
 actually sent to firmware. To facilitate this, the VMM can set the
-KVM_USER_VMGEXIT_REQ_CERTS_FLAGS_NOTIFY_DONE flag before returning the
-certificate blob, in which case another KVM_EXIT_VMGEXIT of type
-KVM_USER_VMGEXIT_REQ_CERTS will be sent to userspace with
-KVM_USER_VMGEXIT_REQ_CERTS_STATUS_DONE being set in the status field to
-indicate the request is fully-completed and that any associated locks can be
-released.
+run->immediate_exit flag before returning the certificate blob, in which
+case KVM is guaranteed to complete the issuing of all pending IO completion
+callbacks before exiting to userspace with EINTR. At this point userspace
+can release any locks it may have taken when the KVM_EXIT_SNP_REQ_CERTS exit
+was originally received.
 
 Tools/libraries that perform updates to SNP firmware TCB values or endorsement
 keys (e.g. firmware interfaces such as SNP_COMMIT, SNP_SET_CONFIG, or
diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 6cf665c410b2..e6318bbd8a6a 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -4006,21 +4006,14 @@ static int snp_complete_ext_guest_req(struct kvm_vcpu *vcpu)
 	sev_ret_code fw_err = 0;
 	int vmm_ret;
 
-	vmm_ret = vcpu->run->vmgexit.req_certs.ret;
+	vmm_ret = vcpu->run->snp_req_certs.ret;
 	if (vmm_ret) {
 		if (vmm_ret == SNP_GUEST_VMM_ERR_INVALID_LEN)
 			vcpu->arch.regs[VCPU_REGS_RBX] =
-				vcpu->run->vmgexit.req_certs.data_npages;
+				vcpu->run->snp_req_certs.data_npages;
 		goto out;
 	}
 
-	/*
-	 * The request was completed on the previous completion callback and
-	 * this completion is only for the STATUS_DONE userspace notification.
-	 */
-	if (vcpu->run->vmgexit.req_certs.status == KVM_USER_VMGEXIT_REQ_CERTS_STATUS_DONE)
-		goto out_resume;
-
 	control = &svm->vmcb->control;
 
 	if (__snp_handle_guest_req(kvm, control->exit_info_1,
@@ -4029,14 +4022,6 @@ static int snp_complete_ext_guest_req(struct kvm_vcpu *vcpu)
 
 out:
 	ghcb_set_sw_exit_info_2(svm->sev_es.ghcb, SNP_GUEST_ERR(vmm_ret, fw_err));
-
-	if (vcpu->run->vmgexit.req_certs.flags & KVM_USER_VMGEXIT_REQ_CERTS_FLAGS_NOTIFY_DONE) {
-		vcpu->run->vmgexit.req_certs.status = KVM_USER_VMGEXIT_REQ_CERTS_STATUS_DONE;
-		vcpu->run->vmgexit.req_certs.flags = 0;
-		return 0; /* notify userspace of completion */
-	}
-
-out_resume:
 	return 1; /* resume guest */
 }
 
@@ -4060,12 +4045,9 @@ static int snp_begin_ext_guest_req(struct kvm_vcpu *vcpu)
 	 * Grab the certificates from userspace so that can be bundled with
 	 * attestation/guest requests.
 	 */
-	vcpu->run->exit_reason = KVM_EXIT_VMGEXIT;
-	vcpu->run->vmgexit.type = KVM_USER_VMGEXIT_REQ_CERTS;
-	vcpu->run->vmgexit.req_certs.data_gpa = data_gpa;
-	vcpu->run->vmgexit.req_certs.data_npages = data_npages;
-	vcpu->run->vmgexit.req_certs.flags = 0;
-	vcpu->run->vmgexit.req_certs.status = KVM_USER_VMGEXIT_REQ_CERTS_STATUS_PENDING;
+	vcpu->run->exit_reason = KVM_EXIT_SNP_REQ_CERTS;
+	vcpu->run->snp_req_certs.data_gpa = data_gpa;
+	vcpu->run->snp_req_certs.data_npages = data_npages;
 	vcpu->arch.complete_userspace_io = snp_complete_ext_guest_req;
 
 	return 0; /* forward request to userspace */
diff --git a/include/uapi/linux/kvm.h b/include/uapi/linux/kvm.h
index 106367d87189..8ebfc91dc967 100644
--- a/include/uapi/linux/kvm.h
+++ b/include/uapi/linux/kvm.h
@@ -135,22 +135,17 @@ struct kvm_xen_exit {
 	} u;
 };
 
-struct kvm_user_vmgexit {
-#define KVM_USER_VMGEXIT_REQ_CERTS		1
-	__u32 type; /* KVM_USER_VMGEXIT_* type */
+struct kvm_exit_snp {
+#define KVM_EXIT_SNP_REQ_CERTS		1
+	__u32 type; /* KVM_EXIT_SNP_* type */
 	union {
 		struct {
 			__u64 data_gpa;
 			__u64 data_npages;
-#define KVM_USER_VMGEXIT_REQ_CERTS_ERROR_INVALID_LEN   1
-#define KVM_USER_VMGEXIT_REQ_CERTS_ERROR_BUSY          2
-#define KVM_USER_VMGEXIT_REQ_CERTS_ERROR_GENERIC       (1 << 31)
+#define KVM_EXIT_SNP_REQ_CERTS_ERROR_INVALID_LEN   1
+#define KVM_EXIT_SNP_REQ_CERTS_ERROR_BUSY          2
+#define KVM_EXIT_SNP_REQ_CERTS_ERROR_GENERIC       (1 << 31)
 			__u32 ret;
-#define KVM_USER_VMGEXIT_REQ_CERTS_FLAGS_NOTIFY_DONE	BIT(0)
-			__u8 flags;
-#define KVM_USER_VMGEXIT_REQ_CERTS_STATUS_PENDING	0
-#define KVM_USER_VMGEXIT_REQ_CERTS_STATUS_DONE		1
-			__u8 status;
 		} req_certs;
 	};
 };
@@ -198,7 +193,7 @@ struct kvm_user_vmgexit {
 #define KVM_EXIT_NOTIFY           37
 #define KVM_EXIT_LOONGARCH_IOCSR  38
 #define KVM_EXIT_MEMORY_FAULT     39
-#define KVM_EXIT_VMGEXIT          40
+#define KVM_EXIT_SNP_REQUEST_CERTS 40
 
 /* For KVM_EXIT_INTERNAL_ERROR */
 /* Emulate instruction failed. */
@@ -454,8 +449,16 @@ struct kvm_run {
 			__u64 gpa;
 			__u64 size;
 		} memory_fault;
-		/* KVM_EXIT_VMGEXIT */
-		struct kvm_user_vmgexit vmgexit;
+		/* KVM_EXIT_SNP_REQ_CERTS */
+		struct {
+			__u64 data_gpa;
+			__u64 data_npages;
+#define KVM_EXIT_SNP_REQ_CERTS_ERROR_INVALID_LEN   1
+#define KVM_EXIT_SNP_REQ_CERTS_ERROR_BUSY          2
+#define KVM_EXIT_SNP_REQ_CERTS_ERROR_GENERIC       (1 << 31)
+			__u32 ret;
+		} snp_req_certs;
+
 		/* Fix the size of the union. */
 		char padding[256];
 	};

---

## [23] Binbin Wu — 2024-05-16
*Subject: Re: [PATCH v15 09/20] KVM: SEV: Add support to handle MSR based Page
 State Change VMGEXIT*

On 5/1/2024 4:51 PM, Michael Roth wrote:
> SEV-SNP VMs can ask the hypervisor to change the page state in the RMP
> table to be private or shared using the Page State Change MSR protocol

Do we have definition of ret? I didn't find clear documentation about it.
According to the code, 0 means succssful. Is there any other error codes 
need to or can be interpreted?

For TDX, it may also want to use KVM_HC_MAP_GPA_RANGE hypercall  to 
userspace via KVM_EXIT_HYPERCALL.


> +		set_ghcb_msr(svm, GHCB_MSR_PSC_RESP_ERROR);
> +	else
[...]

---

## [24] Paolo Bonzini — 2024-05-16
*Subject: Re: [PATCH v15 09/20] KVM: SEV: Add support to handle MSR based Page
 State Change VMGEXIT*

On Thu, May 16, 2024 at 10:29 AM Binbin Wu <binbin.wu@linux.intel.com> wrote:
>
>

They are defined in include/uapi/linux/kvm_para.h

#define KVM_ENOSYS        1000
#define KVM_EFAULT        EFAULT /* 14 */
#define KVM_EINVAL        EINVAL /* 22 */
#define KVM_E2BIG        E2BIG /* 7 */
#define KVM_EPERM        EPERM /* 1*/
#define KVM_EOPNOTSUPP        95

Linux however does not expect the hypercall to fail for SEV/SEV-ES; and
it will terminate the guest if the PSC operation fails for SEV-SNP.  So
it's best for userspace if the hypercall always succeeds. :)

> For TDX, it may also want to use KVM_HC_MAP_GPA_RANGE hypercall  to
> userspace via KVM_EXIT_HYPERCALL.

Yes, definitely.

Paolo

---

## [25] Huang, Kai — 2024-05-20
*Subject: Re: [PATCH v15 13/20] KVM: SEV: Implement gmem hook for initializing
 private pages*

On Wed, 2024-05-01 at 03:52 -0500, Michael Roth wrote:
> This will handle the RMP table updates needed to put a page into a
> private state before mapping it into an SEV-SNP guest.

[...]

> +int sev_gmem_prepare(struct kvm *kvm, kvm_pfn_t pfn, gfn_t gfn, int max_order)
> +{

+Rick, Isaku,

I am wondering whether this can be done in the KVM page fault handler?

The reason that I am asking is KVM will introduce several new
kvm_x86_ops::xx_private_spte() ops for TDX to handle setting up the
private mapping, and I am wondering whether SNP can just reuse some of
them so we can avoid having this .gmem_prepare():

        /* Add a page as page table page into private page table */
        int (*link_private_spt)(struct kvm *kvm, gfn_t gfn, 
			enum pg_level level, void *private_spt);
        /*
         * Free a page table page of private page table.
	 * ...
         */
        int (*free_private_spt)(struct kvm *kvm, gfn_t gfn, 
			enum pg_level level, void *private_spt);

        /* Add a guest private page into private page table */
        int (*set_private_spte)(struct kvm *kvm, gfn_t gfn, 
			enum pg_level level, kvm_pfn_t pfn);

        /* Remove a guest private page from private page table*/
        int (*remove_private_spte)(struct kvm *kvm, gfn_t gfn, 
			enum pg_level level, kvm_pfn_t pfn);
        /*
         * Keep a guest private page mapped in private page table, 
	 * but clear its present bit
         */
        int (*zap_private_spte)(struct kvm *kvm, gfn_t gfn,
			enum pg_level level);

The idea behind these is in the fault handler:

	bool use_private_pt = fault->is_private && 
			kvm_use_private_pt(kvm);

	root_pt = use_private_pt ? mmu->private_root_hpa : mmu->root_hpa;

	tdp_mmu_for_each_pte(&iter, root_pt, gfn, gfn+1, ..) {

		if (use_private_pt)
			kvm_x86_ops->xx_private_spte();
		else
			// normal TDP MMU ops
	}

Which means: if the fault is for private GPA, _AND_ when the VM has a
separate private table, use the specific xx_private_spte() ops to handle
private mapping.

But I am thinking we can use those hooks for SNP too, because
"conceptually", SNP also has concept of "private GPA" and must at least
issue some command to update the RMP table when private mapping is
setup/torn down.

So if we change the above logic to use fault->is_private, but not
'use_private_pt' to decide whether to invoke the
kvm_x86_ops::xx_private_spte(), then we can also implement SNP commands in
those callbacks IIUC:

	if (fault->is_private && kvm_x86_ops::xx_private_spte())
		kvm_x86_ops::xx_private_spte();
	else
		// normal TDP MMU operation

For SNP, these callbacks will operate on normal page table using the
normal TDP MMU code, but can do additional things like issuing commands as
shown in this patch.

My understanding is SNP doesn't need specific handling for middle level
page table, but should be able to utilize the ops when setting up /
tearing down the leaf SPTE?

---

## [26] Sean Christopherson — 2024-05-20
*Subject: Re: [PATCH v15 13/20] KVM: SEV: Implement gmem hook for initializing
 private pages*

On Mon, May 20, 2024, Kai Huang wrote:
> On Wed, 2024-05-01 at 03:52 -0500, Michael Roth wrote:
> > This will handle the RMP table updates needed to put a page into a

...

> +Rick, Isaku,
> 

No, because the state of a pfn in the RMP is tied to the guest_memfd inode, not
to the file descriptor, i.e. not to an individual VM.  And the NPT page tables
are treated as ephemeral for SNP.

---

## [27] Isaku Yamahata — 2024-05-20
*Subject: Re: [PATCH v15 13/20] KVM: SEV: Implement gmem hook for initializing
 private pages*

On Mon, May 20, 2024 at 10:16:54AM +0000,
"Huang, Kai" <kai.huang@intel.com> wrote:

> On Wed, 2024-05-01 at 03:52 -0500, Michael Roth wrote:
> > This will handle the RMP table updates needed to put a page into a

Although I can't speak for SNP folks, I guess those hooks doesn't make sense for
them.  I guess they want to stay away from directly modifying the TDP MMU to add
hooks to the TDP MMU.  Instead, They intentionally chose to add hooks to
guest_memfd.  Maybe it's possible for SNP to use those hooks, what's the benefit
for SNP?

If you're looking for the benefit to allow the hooks of the TDP MMU for shared
page table, what about other vm type? SW_PROTECTED or future one?

---

## [28] Huang, Kai — 2024-05-21
*Subject: Re: [PATCH v15 13/20] KVM: SEV: Implement gmem hook for initializing
 private pages*

On 21/05/2024 5:35 am, Sean Christopherson wrote:
> On Mon, May 20, 2024, Kai Huang wrote:
>> On Wed, 2024-05-01 at 03:52 -0500, Michael Roth wrote:

It's strange that as state of a PFN of SNP doesn't bind to individual 
VM, at least for the private pages.  The command rpm_make_private() 
indeed reflects the mapping between PFN <-> <GFN, SSID>.

	rc = rmp_make_private(pfn_aligned, gfn_to_gpa(gfn_aligned),
			level, sev->asid, false);

> And the NPT page tables
> are treated as ephemeral for SNP.

Do you mean private mappings for SNP guest can be zapped from the VM 
(the private pages are still there unchanged) and re-mapped later w/o 
needing to have guest's explicit acceptance?

If so, I think "we can zap" doesn't mean "we need to zap"?  Because the 
privates are now pinned anyway.  If we truly want to zap private 
mappings for SNP, IIUC it can be done by distinguishing whether a VM 
needs to use a separate private table, which is TDX-only.

I'll look into the SNP spec to understand more.

---

## [29] Sean Christopherson — 2024-05-20
*Subject: Re: [PATCH v15 13/20] KVM: SEV: Implement gmem hook for initializing
 private pages*

On Tue, May 21, 2024, Kai Huang wrote:
> On 21/05/2024 5:35 am, Sean Christopherson wrote:
> > On Mon, May 20, 2024, Kai Huang wrote:

s/SSID/ASID

KVM allows a single ASID to be bound to multiple "struct kvm" instances, e.g.
for intra-host migration.  If/when trusted I/O is a thing, presumably KVM will
also need to share the ASID with other entities, e.g. IOMMUFD.

> 	rc = rmp_make_private(pfn_aligned, gfn_to_gpa(gfn_aligned),
> 			level, sev->asid, false);

Correct.

> If so, I think "we can zap" doesn't mean "we need to zap"?

Correct.

> Because the privates are now pinned anyway.

Pinning is an orthogonal issue.  And it's not so much that the pfns are pinned
as it is that guest_memfd simply doesn't support page migration or swap at this
time.

Regardless of whether or not guest_memfd supports page migration, KVM needs to
track the state of the physical page in guest_memfd, e.g. if it's been assigned
to the ASID versus if it's still in a shared state.

> If we truly want to zap private mappings for SNP, IIUC it can be done by
> distinguishing whether a VM needs to use a separate private table, which is

I wouldn't say we "want" to zap private mappings for SNP, rather that it's a lot
less work to keep KVM's existing behavior (literally do nothing) than it is to
rework the MMU and whatnot to not zap SPTEs.  And there's no big motivation to
avoid zapping because SNP VMs are unlikely to delete memslots.

If it turns out that it's easy to preserve SNP mappings after TDX lands, then we
can certainly go that route, but AFAIK there's no reason to force the issue.

---

## [30] Huang, Kai — 2024-05-21
*Subject: Re: [PATCH v15 13/20] KVM: SEV: Implement gmem hook for initializing
 private pages*

On 21/05/2024 11:15 am, Sean Christopherson wrote:
> On Tue, May 21, 2024, Kai Huang wrote:
>> On 21/05/2024 5:35 am, Sean Christopherson wrote:

But is this the case for SNP?  I thought due to the nature of private 
pages, they cannot be shared between VMs?  So to me this RMP entry 
mapping for PFN <-> GFN for private page should just be per-VM.

> 
>> 	rc = rmp_make_private(pfn_aligned, gfn_to_gpa(gfn_aligned),

Yes.

> 
> Regardless of whether or not guest_memfd supports page migration, KVM needs to

I am not certain this can impact whether we want to do RMP commands via 
guest_memfd() hooks or TDP MMU hooks?

> 
>> If we truly want to zap private mappings for SNP, IIUC it can be done by

My thinking too.

> And there's no big motivation to
> avoid zapping because SNP VMs are unlikely to delete memslots.

I think we should also consider MMU notifier?

> 
> If it turns out that it's easy to preserve SNP mappings after TDX lands, then we

No I am certainly not saying we should do SNP after TDX.  Sorry I didn't 
closely monitor the status of this SNP patchset.

My intention is just wanting to make the TDP MMU common code change more 
useful (since we need that for TDX anyway), i.e., not effectively just 
for TDX if possible:

Currently the TDP MMU hooks are called depending whether the page table 
type is private (or mirrored whatever), but I think conceptually, we 
should decide whether to call TDP MMU hooks based on whether faulting 
GPA is private, _AND_ when the hook is available.

https://lore.kernel.org/lkml/5e8119c0-31f5-4aa9-a496-4ae10bd745a3@intel.com/

If invoking SNP RMP commands is feasible in TDP MMU hooks, then I think 
there's value of letting SNP code to use them too.  And we can simply 
split one patch out to only add the TDP MMU hooks for SNP to land first.

---

## [31] Sean Christopherson — 2024-05-20
*Subject: Re: [PATCH v15 13/20] KVM: SEV: Implement gmem hook for initializing
 private pages*

On Tue, May 21, 2024, Kai Huang wrote:
> On 21/05/2024 11:15 am, Sean Christopherson wrote:
> > On Tue, May 21, 2024, Kai Huang wrote:

Sorry to redirect, but please read this mail (and probably surrounding mails).
It hopefully explains most of the question you have.

https://lore.kernel.org/all/ZLGiEfJZTyl7M8mS@google.com

> > Regardless of whether or not guest_memfd supports page migration, KVM needs to
> > track the state of the physical page in guest_memfd, e.g. if it's been assigned

No, private mappings have no host userspace mappings, i.e. are completely exempt
from MMU notifier events.  guest_memfd() can still invalidate mappings, but that
only occurs if userspace punches a hole, which is destructive.

> > If it turns out that it's easy to preserve SNP mappings after TDX lands, then we
> > can certainly go that route, but AFAIK there's no reason to force the issue.

Feasible.  Yes.  Desirable?  No.  Either KVM tracks the state of the physical page
using the guest_memfd inode, or KVM _guarantees_ the NPT mappings _never_ get
dropped, including during intra-host migration.  E.g. to support intra-host
migration of TDX VMs, KVM is pretty much forced to transer the S-EPT tables as-is,
which is ugly and painful (though performant).  We could do the same for NPT, but
there would need to be massive performance benefits to justify the complexity.

> then I think there's value of letting SNP code to use them too.  And we can
> simply split one patch out to only add the TDP MMU hooks for SNP to land

---

## [32] Binbin Wu — 2024-05-21
*Subject: Re: [PATCH v15 09/20] KVM: SEV: Add support to handle MSR based Page
 State Change VMGEXIT*

On 5/17/2024 1:23 AM, Paolo Bonzini wrote:
> On Thu, May 16, 2024 at 10:29 AM Binbin Wu <binbin.wu@linux.intel.com> wrote:
>>
Thanks for the info.

For TDX, it wants to restrict the size of memory range for conversion in 
one hypercall to avoid a too long latency.
Previously, in TDX QEMU patchset v5, the limitation is in userspace and  
if the size is too big, the status_code will set to TDG_VP_VMCALL_RETRY 
and the failed GPA for guest to retry is updated.
https://lore.kernel.org/all/20240229063726.610065-51-xiaoyao.li@intel.com/

When TDX converts TDVMCALL_MAP_GPA to KVM_HC_MAP_GPA_RANGE, do you think 
which is more reasonable to set the restriction? In KVM (TDX specific 
code) or userspace?
If userspace is preferred, then the interface needs to  be extended to 
support it.


>
>> For TDX, it may also want to use KVM_HC_MAP_GPA_RANGE hypercall  to

---

## [33] Michael Roth — 2024-05-21
*Subject: Re: [PATCH v15 09/20] KVM: SEV: Add support to handle MSR based Page
 State Change VMGEXIT*

On Tue, May 21, 2024 at 08:49:59AM +0800, Binbin Wu wrote:
> 
> 

With SNP we might get a batch of requests in a single GHCB request, and
potentially each of those requests need to get set out to userspace as 
a single KVM_HC_MAP_GPA_RANGE. The subsequent patch here handles that in
a loop by issuing a new KVM_HC_MAP_GPA_RANGE via the completion handler.
So we also sort of need to split large requests into multiple userspace
requests in some cases.

It seems like TDX should be able to do something similar by limiting the
size of each KVM_HC_MAP_GPA_RANGE to TDX_MAP_GPA_MAX_LEN, and then
returning TDG_VP_VMCALL_RETRY to guest if the original size was greater
than TDX_MAP_GPA_MAX_LEN. But at that point you're effectively done with
the entire request and can return to guest, so it actually seems a little
more straightforward than the SNP case above. E.g. TDX has a 1:1 mapping
between TDG_VP_VMCALL_MAP_GPA and KVM_HC_MAP_GPA_RANGE events. (And even
similar names :))

So doesn't seem like there's a good reason to expose any of these
throttling details to userspace, in which case existing
KVM_HC_MAP_GPA_RANGE interface seems like it should be sufficient.

-Mike

> 
>

---

## [34] Binbin Wu — 2024-05-27
*Subject: Re: [PATCH v15 09/20] KVM: SEV: Add support to handle MSR based Page
 State Change VMGEXIT*

On 5/22/2024 5:49 AM, Michael Roth wrote:
> On Tue, May 21, 2024 at 08:49:59AM +0800, Binbin Wu wrote:
>>

The reasons I want to put the throttling in userspace are:
1. Hardcode the TDX_MAP_GPA_MAX_LEN in kernel may not be preferred.
2. The throttling thing doesn't need to be TDX specific, it can be 
generic in userspace.

I think we can set a reasonable value in userspace, so that for SNP, it 
doesn't trigger the throttling since the large request will be split to 
multiple userspace requests.


> in which case existing
> KVM_HC_MAP_GPA_RANGE interface seems like it should be sufficient.

---

## [35] Paolo Bonzini — 2024-05-28
*Subject: Re: [PATCH v15 09/20] KVM: SEV: Add support to handle MSR based Page
 State Change VMGEXIT*

On Mon, May 27, 2024 at 2:26 PM Binbin Wu <binbin.wu@linux.intel.com> wrote:
> > It seems like TDX should be able to do something similar by limiting the
> > size of each KVM_HC_MAP_GPA_RANGE to TDX_MAP_GPA_MAX_LEN, and then

I think userspace should never be worried about throttling. I would
say it's up to the guest to split the GPA into multiple ranges, but
that's not how arch/x86/coco/tdx/tdx.c is implemented so instead we
can do the split in KVM instead. It can be a module parameter or VM
attribute, establishing the size that will be processed in a single
TDVMCALL.

Paolo

>
> The reasons I want to put the throttling in userspace are:

---

## [36] Sean Christopherson — 2024-05-29
*Subject: Re: [PATCH v15 09/20] KVM: SEV: Add support to handle MSR based Page
 State Change VMGEXIT*

On Tue, May 28, 2024, Paolo Bonzini wrote:
> On Mon, May 27, 2024 at 2:26 PM Binbin Wu <binbin.wu@linux.intel.com> wrote:
> > > It seems like TDX should be able to do something similar by limiting the

I agree in principle, but in practice I can understand not wanting to split up
the conversion in the guest due to the additional overhead of the world switches.

>  but that's not how arch/x86/coco/tdx/tdx.c is implemented so instead we can
>  do the split in KVM instead. It can be a module parameter or VM attribute,

Is it just interrupts that are problematic for conversions?  I assume so, because
I can't think of anything else where telling the guest to retry would be appropriate
and useful.

If so, KVM shouldn't need to unconditionally restrict the size for a single
TDVMCALL, KVM just needs to ensure interrupts are handled soonish.  To do that,
KVM could use a much smaller chunk size, e.g. 64KiB (completely made up number),
and keep processing the TDVMCALL as long as there is no interrupt pending.
Hopefully that would obviate the need for a tunable.

---

## [37] Zhi Wang — 2024-05-30
*Subject: Re: [PATCH v15 09/20] KVM: SEV: Add support to handle MSR based
 Page State Change VMGEXIT*

On Tue, 21 May 2024 16:49:52 -0500
Michael Roth <michael.roth@amd.com> wrote:

> On Tue, May 21, 2024 at 08:49:59AM +0800, Binbin Wu wrote:
> > 

Is there any rough data about the latency of private-shared and
shared-private page conversion?

Thanks,
Zhi. 
> -Mike
>

---

## [38] Binbin Wu — 2024-05-31
*Subject: Re: [PATCH v15 09/20] KVM: SEV: Add support to handle MSR based Page
 State Change VMGEXIT*

On 5/30/2024 4:02 AM, Sean Christopherson wrote:
> On Tue, May 28, 2024, Paolo Bonzini wrote:
>> On Mon, May 27, 2024 at 2:26 PM Binbin Wu <binbin.wu@linux.intel.com> wrote:

The concern was the lockup detection in guest.

>
> If so, KVM shouldn't need to unconditionally restrict the size for a single

Thanks for the suggestion.
By this way, interrupt can be injected to guest in time and the lockup 
detection should not be a problem.

About the chunk size, if it is too small, it will increase the cost of 
kernel/userspace context switches.
Maybe 2MB?

---

## [39] Paolo Bonzini — 2024-05-31
*Subject: Re: [PATCH v15 09/20] KVM: SEV: Add support to handle MSR based Page
 State Change VMGEXIT*

On Fri, May 31, 2024 at 3:23 AM Binbin Wu <binbin.wu@linux.intel.com> wrote:
> About the chunk size, if it is too small, it will increase the cost of
> kernel/userspace context switches.

Yeah, 2MB sounds right.

Paolo

---

## [40] Ackerley Tng — 2024-08-01
*Subject: [PATCH] Fixes: f32fb32820b1 ("KVM: x86: Add hook for determining max
 NPT mapping level")*

The `if (req_max_level)` test was meant ignore req_max_level if
PG_LEVEL_NONE was returned. Hence, this function should return
max_level instead of the ignored req_max_level.

Signed-off-by: Ackerley Tng <ackerleytng@google.com>
Change-Id: I403898aacc379ed98ba5caa41c9f1c52f277adc2
---
 arch/x86/kvm/mmu/mmu.c | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)

diff --git a/arch/x86/kvm/mmu/mmu.c b/arch/x86/kvm/mmu/mmu.c
index 901be9e420a4..e6b73774645d 100644
--- a/arch/x86/kvm/mmu/mmu.c
+++ b/arch/x86/kvm/mmu/mmu.c
@@ -4335,7 +4335,7 @@ static u8 kvm_max_private_mapping_level(struct kvm *kvm, kvm_pfn_t pfn,
 	if (req_max_level)
 		max_level = min(max_level, req_max_level);
 
-	return req_max_level;
+	return max_level;
 }
 
 static int kvm_faultin_pfn_private(struct kvm_vcpu *vcpu,

---

## [41] Sean Christopherson — 2024-08-01
*Subject: Re: [PATCH] Fixes: f32fb32820b1 ("KVM: x86: Add hook for determining
 max NPT mapping level")*

On Thu, Aug 01, 2024, Ackerley Tng wrote:
> The `if (req_max_level)` test was meant ignore req_max_level if
> PG_LEVEL_NONE was returned. Hence, this function should return

Fixes: ?

> Signed-off-by: Ackerley Tng <ackerleytng@google.com>
> Change-Id: I403898aacc379ed98ba5caa41c9f1c52f277adc2

Bad gerrit, bad!

---

## [42] Yosry Ahmed — 2024-08-01
*Subject: Re: [PATCH] Fixes: f32fb32820b1 ("KVM: x86: Add hook for determining
 max NPT mapping level")*

On Thu, Aug 1, 2024 at 10:58 AM Sean Christopherson <seanjc@google.com> wrote:
>
> On Thu, Aug 01, 2024, Ackerley Tng wrote:

I think it's in the subject :)

>
> > Signed-off-by: Ackerley Tng <ackerleytng@google.com>

---

## [43] Paolo Bonzini — 2024-08-01
*Subject: Re: [PATCH] Fixes: f32fb32820b1 ("KVM: x86: Add hook for determining
 max NPT mapping level")*

On Thu, Aug 1, 2024 at 7:40 PM Ackerley Tng <ackerleytng@google.com> wrote:
>
> The `if (req_max_level)` test was meant ignore req_max_level if

It's worth pointing out that this is only a latent issue for now,
since guest_memfd does not support large pages ( __kvm_gmem_get_pfn
always returns 0).

Queued with a small note in the commit message and fixed subject.

Thanks,

Paolo


> ---
>  arch/x86/kvm/mmu/mmu.c | 2 +-

---

## [44] Dionna Amalie Glaze — 2024-08-16
*Subject: Re: [PATCH] KVM: SEV: Replace KVM_EXIT_VMGEXIT with KVM_EXIT_SNP_REQ_CERTS*

> --- a/arch/x86/kvm/svm/sev.c
> +++ b/arch/x86/kvm/svm/sev.c

Finally getting around to this patch. Thanks for your patience.

Whether the exit to guest for certs is first or second when getting
the attestation report, the certificates need to be
consistent. Since we don't have any locks held before exiting, and no
checks happening on the result, there's a
chance that a well-intentioned host can still provide the wrong
certificate to the guest when VMs are running and requesting
attestations during a firmware hotload.

Thread 1:
DOWNLOAD_FIRMWARE_EX please
CURRENT_TCB > REPORTED_TCB
(notify service to get a new VCEK cert)
Interrupted

Thread 2:
VM extended guest request in.
Exit to user space
Call SNP_PLATFORM_STATUS to get REPORTED_TCB.
Get certs for REPORTED_TCB for the blob. It's at /x/y/z-REPORTED_TCB.crt.
Interrupted

Thread 1:
I got my VCEK cert delivered for CURRENT_TCB! I'll put it at
/x/y/z-CURRENT_TCB.crt
Great. SNP_COMMIT.
Now both REPORTED_TCB and COMMITTED_TCB to CURRENT_TCB, because that's
the spec. Different reported_tcb here. than in thread 1.
Interrupted

Thread 2:
Get the attestation report. It will be signed by the VCEK versioned to
the newer REPORTED_TCB.
Return to VM guest

VM guest:
My report's signature doesn't verify with the VCEK cert I was given.
Yes, 1-88-COM-PLAIN?

How do we avoid this?
1. We can advise that the guest parses the certificate and the
attestation report to determine if their TCBs match expectations and
retry if they're different because of a bad luck data race.
2. We can add a new global lock that KVM holds from CCP similar to
sev_cmd_lock to sequentialize req_certs, attestation reports, and
SNP_COMMIT. KVM releases the lock before returning to the guest.
  SNP_COMMIT must now hold this lock before attempting to grab the sev_cmd_lock.

I think probably 2 is better.

>
> @@ -4060,12 +4045,9 @@ static int snp_begin_ext_guest_req(struct kvm_vcpu *vcpu)

This should be whatever exit reason #define you go with (40), not the
(1) you defined for kvm_snp_exit.

> +       vcpu->run->snp_req_certs.data_gpa = data_gpa;
> +       vcpu->run->snp_req_certs.data_npages = data_npages;

I think this whole struct should be removed since we're only doing the
one exit reason. This is unused.
You also double-#define the return value preprocessor directives.

>  };
> @@ -198,7 +193,7 @@ struct kvm_user_vmgexit {

Probably we should just make this KVM_EXT_SNP_REQ_CERTS so the rest of
the code works.
>
>  /* For KVM_EXIT_INTERNAL_ERROR */


--
-Dionna Glaze, PhD, CISSP, CCSP (she/her)

---

## [45] Dionna Amalie Glaze — 2024-08-16
*Subject: Re: [PATCH] KVM: SEV: Replace KVM_EXIT_VMGEXIT with KVM_EXIT_SNP_REQ_CERTS*

> How do we avoid this?
> 1. We can advise that the guest parses the certificate and the

Actually no, we shouldn't hold a global lock and only release it if
user space returns to KVM in a specific way, unless we can ensure it
will be unlocked safely on fd close.

---
