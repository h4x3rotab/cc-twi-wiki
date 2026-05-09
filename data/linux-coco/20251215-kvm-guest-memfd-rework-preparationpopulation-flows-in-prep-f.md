---
title: 'KVM: guest_memfd: Rework preparation/population flows in prep for in-place conversion'
date: 2025-12-15
last_reply: 2026-01-08
message_count: 20
participants: ['Michael Roth', 'Vishal Annapurve', 'Sean Christopherson', 'Gupta, Pankaj', 'Huang, Kai', 'Yan Zhao']
---

## [1] Michael Roth — 2025-12-15

This patchset is also available at:

  https://github.com/AMDESE/linux/tree/gmem-populate-rework-v2

and is based on top of kvm/next (e0c26d47def7)


Overview
--------

Yan previously posted a series[1] that reworked kvm_gmem_populate() to deal
with potential locking issues that might arise once in-place conversion
support[2] is added for guest_memfd. To quote Yan's original summary of the
issues:

  (1)
  In Michael's series "KVM: gmem: 2MB THP support and preparedness tracking
  changes" [4], kvm_gmem_get_pfn() was modified to rely on the filemap
  invalidation lock for protecting its preparedness tracking. Similarly, the
  in-place conversion version of guest_memfd series by Ackerly also requires
  kvm_gmem_get_pfn() to acquire filemap invalidation lock [5].
  
  kvm_gmem_get_pfn
      filemap_invalidate_lock_shared(file_inode(file)->i_mapping);
  
  However, since kvm_gmem_get_pfn() is called by kvm_tdp_map_page(), which is
  in turn invoked within kvm_gmem_populate() in TDX, a deadlock occurs on the
  filemap invalidation lock.
  
  (2)
  Moreover, in step 2, get_user_pages_fast() may acquire mm->mmap_lock,
  resulting in the following lock sequence in tdx_vcpu_init_mem_region():
  - filemap invalidation lock --> mm->mmap_lock
  
  However, in future code, the shared filemap invalidation lock will be held
  in kvm_gmem_fault_shared() (see [6]), leading to the lock sequence:
  - mm->mmap_lock --> filemap invalidation lock
  
  This creates an AB-BA deadlock issue.

Sean has since then addressed (1) with his series[3] that avoids relying on
calling kvm_gmem_get_pfn() within the TDX post-populate callback to re-fetch
the PFN that was passed to it.

This series aims to address (2), which is still outstanding, and does so based
heavily on Sean's suggested approach[4] of hoisting the get_user_pages_fast()
out of the TDX post-populate callback so that it can be called prior to taking
the filemap invalidate lock so that the ABBA deadlock is no longer possible.
As preperation for this change, all the partial enablement for hugepages in
the kvm_gmem_populate() path is stripped out so that it can be better
considered once hugepage support is actually in place and code/design can be
kept simpler in the meantime.

It additionally removes 'preparation' tracking from guest_memfd, which would
similarly complicate locking considerations in the context of in-place
conversion (and even moreso in the context of hugepage support). This has
been discussed during both the guest_memfd calls and PUCK calls, and so far
no strong objections have been given, so hopefully that particular change
isn't too controversial.


Some items worth noting/discussing
----------------------------------

(A) While one of the aims of this rework is to implement things such that
    a separate source address can still be passed to kvm_gmem_populate()
    even though the gmem pages can be populated in-place from userspace
    beforehand, issues still arise if the source address itself has the
    KVM_MEMORY_ATTRIBUTE_PRIVATE attribute set, e.g. if source/target
    addresses are the same page. One line of reasoning would be to
    conclude that KVM_MEMORY_ATTRIBUTE_PRIVATE implies that it cannot
    be used as the source of a GUP/copy_from_user(), and thus cases like
    source==target are naturally disallowed. Thus userspace has no choice
    but to populate pages in-place *prior* to setting the
    KVM_MEMORY_ATTRIBUTE_PRIVATE attribute (as kvm_gmem_populate()
    requires), and passing in NULL for the source such that the GUP can
    be skipped (otherwise, it will trigger the shared memory fault path,
    which will then SIGBUS because it will see that it is faulting in
    pages for which KVM_MEMORY_ATTRIBUTE_PRIVATE is set).

    While workable, this would at the very least involve documentation
    updates to KVM_TDX_INIT_MEM_REGION/KVM_SEV_SNP_LAUNCH_UPDATE to cover
    these soon-to-be-possible scenarios. Ira posted a patch separately
    that demonstrates how a NULL source could be safely handled within
    the TDX post-populate callback[5].

    
Known issues / TODO
-------------------

- Compile-tested only for the TDX bits (testing/feedback welcome!)


Changes since RFC v1
--------------------

- and a prep patch to remove partial hugepage enablement in
  kvm_gmem_populate() to simplify things until a hugepage implementation
  can actually make use of it (Yan, Ira, Vishal, Sean)
- begin retroactively enforcing that source pages must be page-aligned
  so that kvm_gmem_populate() callbacks can be simplified. add a patch
  to update SNP user-facing documentation to mention this.
- drop handling for GUP'ing multiple pages before issuing callbacks.
  This will only be needed for potentially for hugepages, and it must
  simpler to handle per-page in the meantime. (Yan, Vishal)
- make sure TDX actually builds (Ira, Yan)


Thanks,

Mike


[1] https://lore.kernel.org/kvm/20250703062641.3247-1-yan.y.zhao@intel.com/
[2] https://lore.kernel.org/kvm/cover.1760731772.git.ackerleytng@google.com/
[3] https://lore.kernel.org/kvm/20251030200951.3402865-1-seanjc@google.com/
[4] https://lore.kernel.org/kvm/aHEwT4X0RcfZzHlt@google.com/
[5] https://lore.kernel.org/kvm/20251105-tdx-init-in-place-v1-1-1196b67d0423@intel.com/


----------------------------------------------------------------
Michael Roth (5):
      KVM: guest_memfd: Remove partial hugepage handling from kvm_gmem_populate()
      KVM: guest_memfd: Remove preparation tracking
      KVM: SEV: Document/enforce page-alignment for KVM_SEV_SNP_LAUNCH_UPDATE
      KVM: TDX: Document alignment requirements for KVM_TDX_INIT_MEM_REGION
      KVM: guest_memfd: GUP source pages prior to populating guest memory

 .../virt/kvm/x86/amd-memory-encryption.rst         |   2 +-
 Documentation/virt/kvm/x86/intel-tdx.rst           |   2 +-
 arch/x86/kvm/svm/sev.c                             | 108 +++++++---------
 arch/x86/kvm/vmx/tdx.c                             |  15 +--
 include/linux/kvm_host.h                           |   4 +-
 virt/kvm/guest_memfd.c                             | 140 +++++++++++----------
 6 files changed, 129 insertions(+), 142 deletions(-)

---

## [2] Michael Roth — 2025-12-15
*Subject: [PATCH v2 1/5] KVM: guest_memfd: Remove partial hugepage handling from kvm_gmem_populate()*

kvm_gmem_populate(), and the associated post-populate callbacks, have
some limited support for dealing with guests backed by hugepages by
passing the order information along to each post-populate callback and
iterating through the pages passed to kvm_gmem_populate() in
hugepage-chunks.

However, guest_memfd doesn't yet support hugepages, and in most cases
additional changes in the kvm_gmem_populate() path would also be needed
to actually allow for this functionality.

This makes the existing code unecessarily complex, and makes changes
difficult to work through upstream due to theoretical impacts on
hugepage support that can't be considered properly without an actual
hugepage implementation to reference. So for now, remove what's there
so changes for things like in-place conversion can be
implemented/reviewed more efficiently.

Suggested-by: Vishal Annapurve <vannapurve@google.com>
Co-developed-by: Vishal Annapurve <vannapurve@google.com>
Signed-off-by: Vishal Annapurve <vannapurve@google.com>
Signed-off-by: Michael Roth <michael.roth@amd.com>
---
 arch/x86/kvm/svm/sev.c   | 94 ++++++++++++++++------------------------
 arch/x86/kvm/vmx/tdx.c   |  2 +-
 include/linux/kvm_host.h |  2 +-
 virt/kvm/guest_memfd.c   | 30 +++++++------
 4 files changed, 56 insertions(+), 72 deletions(-)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index f59c65abe3cf..362c6135401a 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -2267,66 +2267,52 @@ struct sev_gmem_populate_args {
 	int fw_error;
 };
 
-static int sev_gmem_post_populate(struct kvm *kvm, gfn_t gfn_start, kvm_pfn_t pfn,
-				  void __user *src, int order, void *opaque)
+static int sev_gmem_post_populate(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
+				  void __user *src, void *opaque)
 {
 	struct sev_gmem_populate_args *sev_populate_args = opaque;
+	struct sev_data_snp_launch_update fw_args = {0};
 	struct kvm_sev_info *sev = to_kvm_sev_info(kvm);
-	int n_private = 0, ret, i;
-	int npages = (1 << order);
-	gfn_t gfn;
+	bool assigned = false;
+	int level;
+	int ret;
 
 	if (WARN_ON_ONCE(sev_populate_args->type != KVM_SEV_SNP_PAGE_TYPE_ZERO && !src))
 		return -EINVAL;
 
-	for (gfn = gfn_start, i = 0; gfn < gfn_start + npages; gfn++, i++) {
-		struct sev_data_snp_launch_update fw_args = {0};
-		bool assigned = false;
-		int level;
-
-		ret = snp_lookup_rmpentry((u64)pfn + i, &assigned, &level);
-		if (ret || assigned) {
-			pr_debug("%s: Failed to ensure GFN 0x%llx RMP entry is initial shared state, ret: %d assigned: %d\n",
-				 __func__, gfn, ret, assigned);
-			ret = ret ? -EINVAL : -EEXIST;
-			goto err;
-		}
+	ret = snp_lookup_rmpentry((u64)pfn, &assigned, &level);
+	if (ret || assigned) {
+		pr_debug("%s: Failed to ensure GFN 0x%llx RMP entry is initial shared state, ret: %d assigned: %d\n",
+			 __func__, gfn, ret, assigned);
+		ret = ret ? -EINVAL : -EEXIST;
+		goto out;
+	}
 
-		if (src) {
-			void *vaddr = kmap_local_pfn(pfn + i);
+	if (src) {
+		void *vaddr = kmap_local_pfn(pfn);
 
-			if (copy_from_user(vaddr, src + i * PAGE_SIZE, PAGE_SIZE)) {
-				ret = -EFAULT;
-				goto err;
-			}
-			kunmap_local(vaddr);
+		if (copy_from_user(vaddr, src, PAGE_SIZE)) {
+			ret = -EFAULT;
+			goto out;
 		}
-
-		ret = rmp_make_private(pfn + i, gfn << PAGE_SHIFT, PG_LEVEL_4K,
-				       sev_get_asid(kvm), true);
-		if (ret)
-			goto err;
-
-		n_private++;
-
-		fw_args.gctx_paddr = __psp_pa(sev->snp_context);
-		fw_args.address = __sme_set(pfn_to_hpa(pfn + i));
-		fw_args.page_size = PG_LEVEL_TO_RMP(PG_LEVEL_4K);
-		fw_args.page_type = sev_populate_args->type;
-
-		ret = __sev_issue_cmd(sev_populate_args->sev_fd, SEV_CMD_SNP_LAUNCH_UPDATE,
-				      &fw_args, &sev_populate_args->fw_error);
-		if (ret)
-			goto fw_err;
+		kunmap_local(vaddr);
 	}
 
-	return 0;
+	ret = rmp_make_private(pfn, gfn << PAGE_SHIFT, PG_LEVEL_4K,
+			       sev_get_asid(kvm), true);
+	if (ret)
+		goto out;
+
+	fw_args.gctx_paddr = __psp_pa(sev->snp_context);
+	fw_args.address = __sme_set(pfn_to_hpa(pfn));
+	fw_args.page_size = PG_LEVEL_TO_RMP(PG_LEVEL_4K);
+	fw_args.page_type = sev_populate_args->type;
 
-fw_err:
+	ret = __sev_issue_cmd(sev_populate_args->sev_fd, SEV_CMD_SNP_LAUNCH_UPDATE,
+			      &fw_args, &sev_populate_args->fw_error);
 	/*
 	 * If the firmware command failed handle the reclaim and cleanup of that
-	 * PFN specially vs. prior pages which can be cleaned up below without
-	 * needing to reclaim in advance.
+	 * PFN before reporting an error.
 	 *
 	 * Additionally, when invalid CPUID function entries are detected,
 	 * firmware writes the expected values into the page and leaves it
@@ -2336,26 +2322,20 @@ static int sev_gmem_post_populate(struct kvm *kvm, gfn_t gfn_start, kvm_pfn_t pf
 	 * information to provide information on which CPUID leaves/fields
 	 * failed CPUID validation.
 	 */
-	if (!snp_page_reclaim(kvm, pfn + i) &&
+	if (ret && !snp_page_reclaim(kvm, pfn) &&
 	    sev_populate_args->type == KVM_SEV_SNP_PAGE_TYPE_CPUID &&
 	    sev_populate_args->fw_error == SEV_RET_INVALID_PARAM) {
-		void *vaddr = kmap_local_pfn(pfn + i);
+		void *vaddr = kmap_local_pfn(pfn);
 
-		if (copy_to_user(src + i * PAGE_SIZE, vaddr, PAGE_SIZE))
+		if (copy_to_user(src, vaddr, PAGE_SIZE))
 			pr_debug("Failed to write CPUID page back to userspace\n");
 
 		kunmap_local(vaddr);
 	}
 
-	/* pfn + i is hypervisor-owned now, so skip below cleanup for it. */
-	n_private--;
-
-err:
-	pr_debug("%s: exiting with error ret %d (fw_error %d), restoring %d gmem PFNs to shared.\n",
-		 __func__, ret, sev_populate_args->fw_error, n_private);
-	for (i = 0; i < n_private; i++)
-		kvm_rmp_make_shared(kvm, pfn + i, PG_LEVEL_4K);
-
+out:
+	pr_debug("%s: exiting with return code %d (fw_error %d)\n",
+		 __func__, ret, sev_populate_args->fw_error);
 	return ret;
 }
 
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 2d7a4d52ccfb..4fb042ce8ed1 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -3118,7 +3118,7 @@ struct tdx_gmem_post_populate_arg {
 };
 
 static int tdx_gmem_post_populate(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
-				  void __user *src, int order, void *_arg)
+				  void __user *src, void *_arg)
 {
 	struct tdx_gmem_post_populate_arg *arg = _arg;
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
diff --git a/include/linux/kvm_host.h b/include/linux/kvm_host.h
index d93f75b05ae2..1d0cee72e560 100644
--- a/include/linux/kvm_host.h
+++ b/include/linux/kvm_host.h
@@ -2581,7 +2581,7 @@ int kvm_arch_gmem_prepare(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn, int max_ord
  * Returns the number of pages that were populated.
  */
 typedef int (*kvm_gmem_populate_cb)(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
-				    void __user *src, int order, void *opaque);
+				    void __user *src, void *opaque);
 
 long kvm_gmem_populate(struct kvm *kvm, gfn_t gfn, void __user *src, long npages,
 		       kvm_gmem_populate_cb post_populate, void *opaque);
diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index fdaea3422c30..9dafa44838fe 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -151,6 +151,15 @@ static struct folio *kvm_gmem_get_folio(struct inode *inode, pgoff_t index)
 					 mapping_gfp_mask(inode->i_mapping), policy);
 	mpol_cond_put(policy);
 
+	/*
+	 * External interfaces like kvm_gmem_get_pfn() support dealing
+	 * with hugepages to a degree, but internally, guest_memfd currently
+	 * assumes that all folios are order-0 and handling would need
+	 * to be updated for anything otherwise (e.g. page-clearing
+	 * operations).
+	 */
+	WARN_ON_ONCE(folio_order(folio));
+
 	return folio;
 }
 
@@ -829,7 +838,7 @@ long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long
 	struct kvm_memory_slot *slot;
 	void __user *p;
 
-	int ret = 0, max_order;
+	int ret = 0;
 	long i;
 
 	lockdep_assert_held(&kvm->slots_lock);
@@ -848,7 +857,7 @@ long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long
 	filemap_invalidate_lock(file->f_mapping);
 
 	npages = min_t(ulong, slot->npages - (start_gfn - slot->base_gfn), npages);
-	for (i = 0; i < npages; i += (1 << max_order)) {
+	for (i = 0; i < npages; i++) {
 		struct folio *folio;
 		gfn_t gfn = start_gfn + i;
 		pgoff_t index = kvm_gmem_get_index(slot, gfn);
@@ -860,7 +869,7 @@ long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long
 			break;
 		}
 
-		folio = __kvm_gmem_get_pfn(file, slot, index, &pfn, &is_prepared, &max_order);
+		folio = __kvm_gmem_get_pfn(file, slot, index, &pfn, &is_prepared, NULL);
 		if (IS_ERR(folio)) {
 			ret = PTR_ERR(folio);
 			break;
@@ -874,20 +883,15 @@ long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long
 		}
 
 		folio_unlock(folio);
-		WARN_ON(!IS_ALIGNED(gfn, 1 << max_order) ||
-			(npages - i) < (1 << max_order));
 
 		ret = -EINVAL;
-		while (!kvm_range_has_memory_attributes(kvm, gfn, gfn + (1 << max_order),
-							KVM_MEMORY_ATTRIBUTE_PRIVATE,
-							KVM_MEMORY_ATTRIBUTE_PRIVATE)) {
-			if (!max_order)
-				goto put_folio_and_exit;
-			max_order--;
-		}
+		if (!kvm_range_has_memory_attributes(kvm, gfn, gfn + 1,
+						     KVM_MEMORY_ATTRIBUTE_PRIVATE,
+						     KVM_MEMORY_ATTRIBUTE_PRIVATE))
+			goto put_folio_and_exit;
 
 		p = src ? src + i * PAGE_SIZE : NULL;
-		ret = post_populate(kvm, gfn, pfn, p, max_order, opaque);
+		ret = post_populate(kvm, gfn, pfn, p, opaque);
 		if (!ret)
 			kvm_gmem_mark_prepared(folio);

---

## [3] Michael Roth — 2025-12-15
*Subject: [PATCH v2 2/5] KVM: guest_memfd: Remove preparation tracking*

guest_memfd currently uses the folio uptodate flag to track:

  1) whether or not a page has been cleared before initial usage
  2) whether or not the architecture hooks have been issued to put the
     page in a private state as defined by the architecture

In practice, 2) is only actually being tracked for SEV-SNP VMs, and
there do not seem to be any plans/reasons that would suggest this will
change in the future, so this additional tracking/complexity is not
really providing any general benefit to guest_memfd users. Future plans
around in-place conversion and hugepage support, where the per-folio
uptodate flag is planned to be used purely to track the initial clearing
of folios, whereas conversion operations could trigger multiple
transitions between 'prepared' and 'unprepared' and thus need separate
tracking, will make the burden of tracking this information within
guest_memfd even more complex, since preparation generally happens
during fault time, on the "read-side" of any global locks that might
protect state tracked by guest_memfd, and so may require more complex
locking schemes to allow for concurrent handling of page faults for
multiple vCPUs where the "preparedness" state tracked by guest_memfd
might need to be updated as part of handling the fault.

Instead of keeping this current/future complexity within guest_memfd for
what is essentially just SEV-SNP, just drop the tracking for 2) and have
the arch-specific preparation hooks get triggered unconditionally on
every fault so the arch-specific hooks can check the preparation state
directly and decide whether or not a folio still needs additional
preparation. In the case of SEV-SNP, the preparation state is already
checked again via the preparation hooks to avoid double-preparation, so
nothing extra needs to be done to update the handling of things there.

Signed-off-by: Michael Roth <michael.roth@amd.com>
---
 virt/kvm/guest_memfd.c | 44 ++++++++++++------------------------------
 1 file changed, 12 insertions(+), 32 deletions(-)

diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index 9dafa44838fe..8b1248f42aae 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -76,11 +76,6 @@ static int __kvm_gmem_prepare_folio(struct kvm *kvm, struct kvm_memory_slot *slo
 	return 0;
 }
 
-static inline void kvm_gmem_mark_prepared(struct folio *folio)
-{
-	folio_mark_uptodate(folio);
-}
-
 /*
  * Process @folio, which contains @gfn, so that the guest can use it.
  * The folio must be locked and the gfn must be contained in @slot.
@@ -90,13 +85,7 @@ static inline void kvm_gmem_mark_prepared(struct folio *folio)
 static int kvm_gmem_prepare_folio(struct kvm *kvm, struct kvm_memory_slot *slot,
 				  gfn_t gfn, struct folio *folio)
 {
-	unsigned long nr_pages, i;
 	pgoff_t index;
-	int r;
-
-	nr_pages = folio_nr_pages(folio);
-	for (i = 0; i < nr_pages; i++)
-		clear_highpage(folio_page(folio, i));
 
 	/*
 	 * Preparing huge folios should always be safe, since it should
@@ -114,11 +103,8 @@ static int kvm_gmem_prepare_folio(struct kvm *kvm, struct kvm_memory_slot *slot,
 	WARN_ON(!IS_ALIGNED(slot->gmem.pgoff, folio_nr_pages(folio)));
 	index = kvm_gmem_get_index(slot, gfn);
 	index = ALIGN_DOWN(index, folio_nr_pages(folio));
-	r = __kvm_gmem_prepare_folio(kvm, slot, index, folio);
-	if (!r)
-		kvm_gmem_mark_prepared(folio);
 
-	return r;
+	return __kvm_gmem_prepare_folio(kvm, slot, index, folio);
 }
 
 /*
@@ -429,7 +415,7 @@ static vm_fault_t kvm_gmem_fault_user_mapping(struct vm_fault *vmf)
 
 	if (!folio_test_uptodate(folio)) {
 		clear_highpage(folio_page(folio, 0));
-		kvm_gmem_mark_prepared(folio);
+		folio_mark_uptodate(folio);
 	}
 
 	vmf->page = folio_file_page(folio, vmf->pgoff);
@@ -766,7 +752,7 @@ void kvm_gmem_unbind(struct kvm_memory_slot *slot)
 static struct folio *__kvm_gmem_get_pfn(struct file *file,
 					struct kvm_memory_slot *slot,
 					pgoff_t index, kvm_pfn_t *pfn,
-					bool *is_prepared, int *max_order)
+					int *max_order)
 {
 	struct file *slot_file = READ_ONCE(slot->gmem.file);
 	struct gmem_file *f = file->private_data;
@@ -796,7 +782,6 @@ static struct folio *__kvm_gmem_get_pfn(struct file *file,
 	if (max_order)
 		*max_order = 0;
 
-	*is_prepared = folio_test_uptodate(folio);
 	return folio;
 }
 
@@ -806,19 +791,22 @@ int kvm_gmem_get_pfn(struct kvm *kvm, struct kvm_memory_slot *slot,
 {
 	pgoff_t index = kvm_gmem_get_index(slot, gfn);
 	struct folio *folio;
-	bool is_prepared = false;
 	int r = 0;
 
 	CLASS(gmem_get_file, file)(slot);
 	if (!file)
 		return -EFAULT;
 
-	folio = __kvm_gmem_get_pfn(file, slot, index, pfn, &is_prepared, max_order);
+	folio = __kvm_gmem_get_pfn(file, slot, index, pfn, max_order);
 	if (IS_ERR(folio))
 		return PTR_ERR(folio);
 
-	if (!is_prepared)
-		r = kvm_gmem_prepare_folio(kvm, slot, gfn, folio);
+	if (!folio_test_uptodate(folio)) {
+		clear_highpage(folio_page(folio, 0));
+		folio_mark_uptodate(folio);
+	}
+
+	r = kvm_gmem_prepare_folio(kvm, slot, gfn, folio);
 
 	folio_unlock(folio);
 
@@ -861,7 +849,6 @@ long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long
 		struct folio *folio;
 		gfn_t gfn = start_gfn + i;
 		pgoff_t index = kvm_gmem_get_index(slot, gfn);
-		bool is_prepared = false;
 		kvm_pfn_t pfn;
 
 		if (signal_pending(current)) {
@@ -869,19 +856,12 @@ long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long
 			break;
 		}
 
-		folio = __kvm_gmem_get_pfn(file, slot, index, &pfn, &is_prepared, NULL);
+		folio = __kvm_gmem_get_pfn(file, slot, index, &pfn, NULL);
 		if (IS_ERR(folio)) {
 			ret = PTR_ERR(folio);
 			break;
 		}
 
-		if (is_prepared) {
-			folio_unlock(folio);
-			folio_put(folio);
-			ret = -EEXIST;
-			break;
-		}
-
 		folio_unlock(folio);
 
 		ret = -EINVAL;
@@ -893,7 +873,7 @@ long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long
 		p = src ? src + i * PAGE_SIZE : NULL;
 		ret = post_populate(kvm, gfn, pfn, p, opaque);
 		if (!ret)
-			kvm_gmem_mark_prepared(folio);
+			folio_mark_uptodate(folio);
 
 put_folio_and_exit:
 		folio_put(folio);

---

## [4] Michael Roth — 2025-12-15
*Subject: [PATCH v2 3/5] KVM: SEV: Document/enforce page-alignment for KVM_SEV_SNP_LAUNCH_UPDATE*

In the past, KVM_SEV_SNP_LAUNCH_UPDATE accepted a non-page-aligned
'uaddr' parameter to copy data from, but continuing to support this with
new functionality like in-place conversion and hugepages in the pipeline
has proven to be more trouble than it is worth, since there are no known
users that have been identified who use a non-page-aligned 'uaddr'
parameter.

Rather than locking guest_memfd into continuing to support this, go
ahead and document page-alignment as a requirement and begin enforcing
this in the handling function.

Signed-off-by: Michael Roth <michael.roth@amd.com>
---
 Documentation/virt/kvm/x86/amd-memory-encryption.rst | 2 +-
 arch/x86/kvm/svm/sev.c                               | 6 +++++-
 2 files changed, 6 insertions(+), 2 deletions(-)

diff --git a/Documentation/virt/kvm/x86/amd-memory-encryption.rst b/Documentation/virt/kvm/x86/amd-memory-encryption.rst
index 1ddb6a86ce7f..5a88d0197cb3 100644
--- a/Documentation/virt/kvm/x86/amd-memory-encryption.rst
+++ b/Documentation/virt/kvm/x86/amd-memory-encryption.rst
@@ -523,7 +523,7 @@ Returns: 0 on success, < 0 on error, -EAGAIN if caller should retry
 
         struct kvm_sev_snp_launch_update {
                 __u64 gfn_start;        /* Guest page number to load/encrypt data into. */
-                __u64 uaddr;            /* Userspace address of data to be loaded/encrypted. */
+                __u64 uaddr;            /* 4k-aligned address of data to be loaded/encrypted. */
                 __u64 len;              /* 4k-aligned length in bytes to copy into guest memory.*/
                 __u8 type;              /* The type of the guest pages being initialized. */
                 __u8 pad0;
diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 362c6135401a..90c512ca24a9 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -2366,6 +2366,11 @@ static int snp_launch_update(struct kvm *kvm, struct kvm_sev_cmd *argp)
 	     params.type != KVM_SEV_SNP_PAGE_TYPE_CPUID))
 		return -EINVAL;
 
+	src = params.type == KVM_SEV_SNP_PAGE_TYPE_ZERO ? NULL : u64_to_user_ptr(params.uaddr);
+
+	if (!PAGE_ALIGNED(src))
+		return -EINVAL;
+
 	npages = params.len / PAGE_SIZE;
 
 	/*
@@ -2397,7 +2402,6 @@ static int snp_launch_update(struct kvm *kvm, struct kvm_sev_cmd *argp)
 
 	sev_populate_args.sev_fd = argp->sev_fd;
 	sev_populate_args.type = params.type;
-	src = params.type == KVM_SEV_SNP_PAGE_TYPE_ZERO ? NULL : u64_to_user_ptr(params.uaddr);
 
 	count = kvm_gmem_populate(kvm, params.gfn_start, src, npages,
 				  sev_gmem_post_populate, &sev_populate_args);

---

## [5] Michael Roth — 2025-12-15
*Subject: [PATCH v2 4/5] KVM: TDX: Document alignment requirements for KVM_TDX_INIT_MEM_REGION*

Since it was never possible to use a non-PAGE_SIZE-aligned @source_addr,
go ahead and document this as a requirement. This is in preparation for
enforcing page-aligned @source_addr for all architectures in
guest_memfd.

Signed-off-by: Michael Roth <michael.roth@amd.com>
---
 Documentation/virt/kvm/x86/intel-tdx.rst | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)

diff --git a/Documentation/virt/kvm/x86/intel-tdx.rst b/Documentation/virt/kvm/x86/intel-tdx.rst
index 5efac62c92c7..6a222e9d0954 100644
--- a/Documentation/virt/kvm/x86/intel-tdx.rst
+++ b/Documentation/virt/kvm/x86/intel-tdx.rst
@@ -156,7 +156,7 @@ KVM_TDX_INIT_MEM_REGION
 :Returns: 0 on success, <0 on error
 
 Initialize @nr_pages TDX guest private memory starting from @gpa with userspace
-provided data from @source_addr.
+provided data from @source_addr. @source_addr must be PAGE_SIZE-aligned.
 
 Note, before calling this sub command, memory attribute of the range
 [gpa, gpa + nr_pages] needs to be private.  Userspace can use

---

## [6] Michael Roth — 2025-12-15
*Subject: [PATCH v2 5/5] KVM: guest_memfd: GUP source pages prior to populating guest memory*

Currently the post-populate callbacks handle copying source pages into
private GPA ranges backed by guest_memfd, where kvm_gmem_populate()
acquires the filemap invalidate lock, then calls a post-populate
callback which may issue a get_user_pages() on the source pages prior to
copying them into the private GPA (e.g. TDX).

This will not be compatible with in-place conversion, where the
userspace page fault path will attempt to acquire filemap invalidate
lock while holding the mm->mmap_lock, leading to a potential ABBA
deadlock[1].

Address this by hoisting the GUP above the filemap invalidate lock so
that these page faults path can be taken early, prior to acquiring the
filemap invalidate lock.

It's not currently clear whether this issue is reachable with the
current implementation of guest_memfd, which doesn't support in-place
conversion, however it does provide a consistent mechanism to provide
stable source/target PFNs to callbacks rather than punting to
vendor-specific code, which allows for more commonality across
architectures, which may be worthwhile even without in-place conversion.

As part of this change, also begin enforcing that the 'src' argument to
kvm_gmem_populate() must be page-aligned, as this greatly reduces the
complexity around how the post-populate callbacks are implemented, and
since no current in-tree users support using a non-page-aligned 'src'
argument.

Suggested-by: Sean Christopherson <seanjc@google.com>
Co-developed-by: Sean Christopherson <seanjc@google.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
Co-developed-by: Vishal Annapurve <vannapurve@google.com>
Signed-off-by: Vishal Annapurve <vannapurve@google.com>
Signed-off-by: Michael Roth <michael.roth@amd.com>
---
 arch/x86/kvm/svm/sev.c   | 32 ++++++++-------
 arch/x86/kvm/vmx/tdx.c   | 15 +------
 include/linux/kvm_host.h |  4 +-
 virt/kvm/guest_memfd.c   | 84 +++++++++++++++++++++++++++-------------
 4 files changed, 77 insertions(+), 58 deletions(-)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 90c512ca24a9..11ae008aec8a 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -2268,7 +2268,7 @@ struct sev_gmem_populate_args {
 };
 
 static int sev_gmem_post_populate(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
-				  void __user *src, void *opaque)
+				  struct page *src_page, void *opaque)
 {
 	struct sev_gmem_populate_args *sev_populate_args = opaque;
 	struct sev_data_snp_launch_update fw_args = {0};
@@ -2277,7 +2277,7 @@ static int sev_gmem_post_populate(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
 	int level;
 	int ret;
 
-	if (WARN_ON_ONCE(sev_populate_args->type != KVM_SEV_SNP_PAGE_TYPE_ZERO && !src))
+	if (WARN_ON_ONCE(sev_populate_args->type != KVM_SEV_SNP_PAGE_TYPE_ZERO && !src_page))
 		return -EINVAL;
 
 	ret = snp_lookup_rmpentry((u64)pfn, &assigned, &level);
@@ -2288,14 +2288,14 @@ static int sev_gmem_post_populate(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
 		goto out;
 	}
 
-	if (src) {
-		void *vaddr = kmap_local_pfn(pfn);
+	if (src_page) {
+		void *src_vaddr = kmap_local_pfn(page_to_pfn(src_page));
+		void *dst_vaddr = kmap_local_pfn(pfn);
 
-		if (copy_from_user(vaddr, src, PAGE_SIZE)) {
-			ret = -EFAULT;
-			goto out;
-		}
-		kunmap_local(vaddr);
+		memcpy(dst_vaddr, src_vaddr, PAGE_SIZE);
+
+		kunmap_local(src_vaddr);
+		kunmap_local(dst_vaddr);
 	}
 
 	ret = rmp_make_private(pfn, gfn << PAGE_SHIFT, PG_LEVEL_4K,
@@ -2325,17 +2325,19 @@ static int sev_gmem_post_populate(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
 	if (ret && !snp_page_reclaim(kvm, pfn) &&
 	    sev_populate_args->type == KVM_SEV_SNP_PAGE_TYPE_CPUID &&
 	    sev_populate_args->fw_error == SEV_RET_INVALID_PARAM) {
-		void *vaddr = kmap_local_pfn(pfn);
+		void *src_vaddr = kmap_local_pfn(page_to_pfn(src_page));
+		void *dst_vaddr = kmap_local_pfn(pfn);
 
-		if (copy_to_user(src, vaddr, PAGE_SIZE))
-			pr_debug("Failed to write CPUID page back to userspace\n");
+		memcpy(src_vaddr, dst_vaddr, PAGE_SIZE);
 
-		kunmap_local(vaddr);
+		kunmap_local(src_vaddr);
+		kunmap_local(dst_vaddr);
 	}
 
 out:
-	pr_debug("%s: exiting with return code %d (fw_error %d)\n",
-		 __func__, ret, sev_populate_args->fw_error);
+	if (ret)
+		pr_debug("%s: error updating GFN %llx, return code %d (fw_error %d)\n",
+			 __func__, gfn, ret, sev_populate_args->fw_error);
 	return ret;
 }
 
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 4fb042ce8ed1..3eb597c0e79f 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -3118,34 +3118,21 @@ struct tdx_gmem_post_populate_arg {
 };
 
 static int tdx_gmem_post_populate(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
-				  void __user *src, void *_arg)
+				  struct page *src_page, void *_arg)
 {
 	struct tdx_gmem_post_populate_arg *arg = _arg;
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
 	u64 err, entry, level_state;
 	gpa_t gpa = gfn_to_gpa(gfn);
-	struct page *src_page;
 	int ret, i;
 
 	if (KVM_BUG_ON(kvm_tdx->page_add_src, kvm))
 		return -EIO;
 
-	/*
-	 * Get the source page if it has been faulted in. Return failure if the
-	 * source page has been swapped out or unmapped in primary memory.
-	 */
-	ret = get_user_pages_fast((unsigned long)src, 1, 0, &src_page);
-	if (ret < 0)
-		return ret;
-	if (ret != 1)
-		return -ENOMEM;
-
 	kvm_tdx->page_add_src = src_page;
 	ret = kvm_tdp_mmu_map_private_pfn(arg->vcpu, gfn, pfn);
 	kvm_tdx->page_add_src = NULL;
 
-	put_page(src_page);
-
 	if (ret || !(arg->flags & KVM_TDX_MEASURE_MEMORY_REGION))
 		return ret;
 
diff --git a/include/linux/kvm_host.h b/include/linux/kvm_host.h
index 1d0cee72e560..49c0cfe24fd8 100644
--- a/include/linux/kvm_host.h
+++ b/include/linux/kvm_host.h
@@ -2566,7 +2566,7 @@ int kvm_arch_gmem_prepare(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn, int max_ord
  * @gfn: starting GFN to be populated
  * @src: userspace-provided buffer containing data to copy into GFN range
  *       (passed to @post_populate, and incremented on each iteration
- *       if not NULL)
+ *       if not NULL). Must be page-aligned.
  * @npages: number of pages to copy from userspace-buffer
  * @post_populate: callback to issue for each gmem page that backs the GPA
  *                 range
@@ -2581,7 +2581,7 @@ int kvm_arch_gmem_prepare(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn, int max_ord
  * Returns the number of pages that were populated.
  */
 typedef int (*kvm_gmem_populate_cb)(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
-				    void __user *src, void *opaque);
+				    struct page *page, void *opaque);
 
 long kvm_gmem_populate(struct kvm *kvm, gfn_t gfn, void __user *src, long npages,
 		       kvm_gmem_populate_cb post_populate, void *opaque);
diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index 8b1248f42aae..18ae59b92257 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -820,12 +820,48 @@ int kvm_gmem_get_pfn(struct kvm *kvm, struct kvm_memory_slot *slot,
 EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_gmem_get_pfn);
 
 #ifdef CONFIG_HAVE_KVM_ARCH_GMEM_POPULATE
+
+static long __kvm_gmem_populate(struct kvm *kvm, struct kvm_memory_slot *slot,
+				struct file *file, gfn_t gfn, struct page *src_page,
+				kvm_gmem_populate_cb post_populate, void *opaque)
+{
+	pgoff_t index = kvm_gmem_get_index(slot, gfn);
+	struct folio *folio;
+	kvm_pfn_t pfn;
+	int ret;
+
+	filemap_invalidate_lock(file->f_mapping);
+
+	folio = __kvm_gmem_get_pfn(file, slot, index, &pfn, NULL);
+	if (IS_ERR(folio)) {
+		ret = PTR_ERR(folio);
+		goto out_unlock;
+	}
+
+	folio_unlock(folio);
+
+	if (!kvm_range_has_memory_attributes(kvm, gfn, gfn + 1,
+					     KVM_MEMORY_ATTRIBUTE_PRIVATE,
+					     KVM_MEMORY_ATTRIBUTE_PRIVATE)) {
+		ret = -EINVAL;
+		goto out_put_folio;
+	}
+
+	ret = post_populate(kvm, gfn, pfn, src_page, opaque);
+	if (!ret)
+		folio_mark_uptodate(folio);
+
+out_put_folio:
+	folio_put(folio);
+out_unlock:
+	filemap_invalidate_unlock(file->f_mapping);
+	return ret;
+}
+
 long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long npages,
 		       kvm_gmem_populate_cb post_populate, void *opaque)
 {
 	struct kvm_memory_slot *slot;
-	void __user *p;
-
 	int ret = 0;
 	long i;
 
@@ -834,6 +870,9 @@ long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long
 	if (WARN_ON_ONCE(npages <= 0))
 		return -EINVAL;
 
+	if (WARN_ON_ONCE(!PAGE_ALIGNED(src)))
+		return -EINVAL;
+
 	slot = gfn_to_memslot(kvm, start_gfn);
 	if (!kvm_slot_has_gmem(slot))
 		return -EINVAL;
@@ -842,47 +881,38 @@ long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long
 	if (!file)
 		return -EFAULT;
 
-	filemap_invalidate_lock(file->f_mapping);
-
 	npages = min_t(ulong, slot->npages - (start_gfn - slot->base_gfn), npages);
 	for (i = 0; i < npages; i++) {
-		struct folio *folio;
-		gfn_t gfn = start_gfn + i;
-		pgoff_t index = kvm_gmem_get_index(slot, gfn);
-		kvm_pfn_t pfn;
+		struct page *src_page = NULL;
+		void __user *p;
 
 		if (signal_pending(current)) {
 			ret = -EINTR;
 			break;
 		}
 
-		folio = __kvm_gmem_get_pfn(file, slot, index, &pfn, NULL);
-		if (IS_ERR(folio)) {
-			ret = PTR_ERR(folio);
-			break;
-		}
+		p = src ? src + i * PAGE_SIZE : NULL;
 
-		folio_unlock(folio);
+		if (p) {
+			ret = get_user_pages_fast((unsigned long)p, 1, 0, &src_page);
+			if (ret < 0)
+				break;
+			if (ret != 1) {
+				ret = -ENOMEM;
+				break;
+			}
+		}
 
-		ret = -EINVAL;
-		if (!kvm_range_has_memory_attributes(kvm, gfn, gfn + 1,
-						     KVM_MEMORY_ATTRIBUTE_PRIVATE,
-						     KVM_MEMORY_ATTRIBUTE_PRIVATE))
-			goto put_folio_and_exit;
+		ret = __kvm_gmem_populate(kvm, slot, file, start_gfn + i, src_page,
+					  post_populate, opaque);
 
-		p = src ? src + i * PAGE_SIZE : NULL;
-		ret = post_populate(kvm, gfn, pfn, p, opaque);
-		if (!ret)
-			folio_mark_uptodate(folio);
+		if (src_page)
+			put_page(src_page);
 
-put_folio_and_exit:
-		folio_put(folio);
 		if (ret)
 			break;
 	}
 
-	filemap_invalidate_unlock(file->f_mapping);
-
 	return ret && !i ? ret : i;
 }
 EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_gmem_populate);

---

## [7] Vishal Annapurve — 2025-12-15
*Subject: Re: [PATCH v2 1/5] KVM: guest_memfd: Remove partial hugepage handling
 from kvm_gmem_populate()*

On Mon, Dec 15, 2025 at 7:35 AM Michael Roth <michael.roth@amd.com> wrote:
>
> kvm_gmem_populate(), and the associated post-populate callbacks, have

Tested-By: Vishal Annapurve <vannapurve@google.com>

> diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
> index fdaea3422c30..9dafa44838fe 100644

I am not sure if this WARN_ON adds any value. i.e. The current code
can't hit it. This note concerns future efforts to add hugepage
support and could be omitted altogether from the current
implementation.

> +
>         return folio;

---

## [8] Vishal Annapurve — 2025-12-15
*Subject: Re: [PATCH v2 2/5] KVM: guest_memfd: Remove preparation tracking*

On Mon, Dec 15, 2025 at 7:35 AM Michael Roth <michael.roth@amd.com> wrote:
>
> guest_memfd currently uses the folio uptodate flag to track:

Reviewed-By: Vishal Annapurve <vannapurve@google.com>
Tested-By: Vishal Annapurve <vannapurve@google.com>

---

## [9] Vishal Annapurve — 2025-12-15
*Subject: Re: [PATCH v2 3/5] KVM: SEV: Document/enforce page-alignment for KVM_SEV_SNP_LAUNCH_UPDATE*

On Mon, Dec 15, 2025 at 7:35 AM Michael Roth <michael.roth@amd.com> wrote:
>
> In the past, KVM_SEV_SNP_LAUNCH_UPDATE accepted a non-page-aligned

Reviewed-By: Vishal Annapurve <vannapurve@google.com>

---

## [10] Sean Christopherson — 2025-12-15
*Subject: Re: [PATCH v2 1/5] KVM: guest_memfd: Remove partial hugepage handling
 from kvm_gmem_populate()*

On Mon, Dec 15, 2025, Vishal Annapurve wrote:
> On Mon, Dec 15, 2025 at 7:35 AM Michael Roth <michael.roth@amd.com> wrote:
> > diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c

The current code _shouldn't_ hit it.

> This note concerns future efforts to add hugepage support and could be
> omitted altogether from the current implementation.

IMO, this is a good use of WARN_ON_ONCE().  It documents guest_memfd's assumptions
and/or limitations, which is extremely helpful to readers/contributors that aren't
familiar with guest_memfd and/or its history of hugepage support.

---

## [11] Vishal Annapurve — 2025-12-15
*Subject: Re: [PATCH v2 5/5] KVM: guest_memfd: GUP source pages prior to
 populating guest memory*

On Mon, Dec 15, 2025 at 7:36 AM Michael Roth <michael.roth@amd.com> wrote:
>
> Currently the post-populate callbacks handle copying source pages into

Tested-By: Vishal Annapurve <vannapurve@google.com>

---

## [12] Vishal Annapurve — 2025-12-15
*Subject: Re: [PATCH v2 4/5] KVM: TDX: Document alignment requirements for KVM_TDX_INIT_MEM_REGION*

On Mon, Dec 15, 2025 at 7:36 AM Michael Roth <michael.roth@amd.com> wrote:
>
> Since it was never possible to use a non-PAGE_SIZE-aligned @source_addr,

Reviewed-By: Vishal Annapurve <vannapurve@google.com>

---

## [13] Gupta, Pankaj — 2025-12-16
*Subject: Re: [PATCH v2 2/5] KVM: guest_memfd: Remove preparation tracking*

> guest_memfd currently uses the folio uptodate flag to track:
>

Reviewed-by: Pankaj Gupta <pankaj.gupta@amd.com>

> ---
>   virt/kvm/guest_memfd.c | 44 ++++++++++++------------------------------

---

## [14] Huang, Kai — 2025-12-18
*Subject: Re: [PATCH v2 5/5] KVM: guest_memfd: GUP source pages prior to
 populating guest memory*

On Mon, 2025-12-15 at 09:34 -0600, Michael Roth wrote:
> Currently the post-populate callbacks handle copying source pages into
> private GPA ranges backed by guest_memfd, where kvm_gmem_populate()

Nit: there's no link to mention [1].


[...]

> Suggested-by: Sean Christopherson <seanjc@google.com>
> Co-developed-by: Sean Christopherson <seanjc@google.com>

[...]

> +	if (src_page) {
> +		void *src_vaddr = kmap_local_pfn(page_to_pfn(src_page));

Nit: maybe you can use kmap_local_page(src_page) directly.

> +		void *dst_vaddr = kmap_local_pfn(pfn);
>  

Ditto.

---

## [15] Huang, Kai — 2025-12-18
*Subject: Re: [PATCH v2 2/5] KVM: guest_memfd: Remove preparation tracking*

>  /*
>   * Process @folio, which contains @gfn, so that the guest can use it.

Here the entire folio is cleared, but ...

[...]

> -	folio = __kvm_gmem_get_pfn(file, slot, index, pfn, &is_prepared, max_order);
> +	folio = __kvm_gmem_get_pfn(file, slot, index, pfn, max_order);

... here only the first page is cleared.

I understand currently there's no huge folio coming out of gmem now, but
since both __kvm_gmem_get_pfn() and kvm_gmem_get_pfn() still have
@max_level as output, it's kinda inconsistent here.

I also see kvm_gmem_fault_user_mapping() only clears the first page too,
but I think that already has assumption that folio can never be huge
currently?

Given this, and the fact that the first patch of this series has
introduced 

	WARN_ON_ONCE(folio_order(folio));

in kvm_gmem_get_folio(), I think it's fine to only clear the first page,
but for the sake of consistency, perhaps we should just remove @max_order
from __kvm_gmem_get_pfn() and kvm_gmem_get_pfn()?

Then we can handle huge folio logic when that comes to play.

Btw:

I actually looked into the RFC v1 discussion but the code there actually
does a loop to clear all pages in the folio.  There were some other
discussions about AFAICT they were more related to issues regarding to 
"mark entire folio as uptodate while only one page is processed in
post_populate()".

Btw2:

There was also discussion that clearing page isn't required for TDX.  To
that end, maybe we can remove clearing page from gmem common code but to
SEV code, e.g., as part of "folio preparation"?

---

## [16] Huang, Kai — 2025-12-18
*Subject: Re: [PATCH v2 0/5] KVM: guest_memfd: Rework preparation/population
 flows in prep for in-place conversion*

On Mon, 2025-12-15 at 09:34 -0600, Michael Roth wrote:
> Known issues / TODO
> -------------------

Applied this series to 6.19-rc1, and tested booting/destroying TD worked
fine, so:

Tested-by: Kai Huang <kai.huang@intel.com>

---

## [17] Yan Zhao — 2025-12-26
*Subject: Re: [PATCH v2 5/5] KVM: guest_memfd: GUP source pages prior to
 populating guest memory*

On Mon, Dec 15, 2025 at 09:34:11AM -0600, Michael Roth wrote:
> diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
> index 4fb042ce8ed1..3eb597c0e79f 100644
Check if src_page is NULL.

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index f9dc59a39eb8..98ff84bc83f2 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -3190,6 +3190,9 @@ static int tdx_gmem_post_populate(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
        if (KVM_BUG_ON(kvm_tdx->page_add_src, kvm))
                return -EIO;
 
+       if (!src_page)
+               return -EOPNOTSUPP;
+
        kvm_tdx->page_add_src = src_page;
        ret = kvm_tdp_mmu_map_private_pfn(arg->vcpu, gfn, pfn);
        kvm_tdx->page_add_src = NULL;

> -	/*
> -	 * Get the source page if it has been faulted in. Return failure if the
...
>  long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long npages,
>  		       kvm_gmem_populate_cb post_populate, void *opaque)
Put pages in this case? e.g.,

--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -1645,6 +1645,9 @@ long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long
                        if (ret < 0)
                                break;
                        if (ret != 1) {
+                               while (ret--)
+                                       put_page(src_page++);
+
                                ret = -ENOMEM;
                                break;
                        }




> +				ret = -ENOMEM;
> +				break;

---

## [18] Yan Zhao — 2025-12-26
*Subject: Re: [PATCH v2 1/5] KVM: guest_memfd: Remove partial hugepage
 handling from kvm_gmem_populate()*

> -static int sev_gmem_post_populate(struct kvm *kvm, gfn_t gfn_start, kvm_pfn_t pfn,
> -				  void __user *src, int order, void *opaque)
Please consider apply the following fix before this patch. Thanks!

commit 2714522d42263e0e250f21a0b171c10c4bb17ed3
Author: Yan Zhao <yan.y.zhao@intel.com>
Date:   Mon Nov 10 11:22:28 2025 +0800

    KVM: SVM: Fix a missing kunmap_local() in sev_gmem_post_populate()
    
    sev_gmem_post_populate() needs to unmap the target vaddr after
    copy_from_user() to the vaddr fails.
    
    Fixes: dee5a47cc7a4 ("KVM: SEV: Add KVM_SEV_SNP_LAUNCH_UPDATE command")
    Signed-off-by: Yan Zhao <yan.y.zhao@intel.com>

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index f59c65abe3cf..261d9ef8631b 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -2296,6 +2296,7 @@ static int sev_gmem_post_populate(struct kvm *kvm, gfn_t gfn_start, kvm_pfn_t pf
                        void *vaddr = kmap_local_pfn(pfn + i);
 
                        if (copy_from_user(vaddr, src + i * PAGE_SIZE, PAGE_SIZE)) {
+                               kunmap_local(vaddr);
                                ret = -EFAULT;
                                goto err;
                        }



> -			}
> -			kunmap_local(vaddr);

---

## [19] Yan Zhao — 2025-12-26
*Subject: Re: [PATCH v2 5/5] KVM: guest_memfd: GUP source pages prior to
 populating guest memory*

On Fri, Dec 26, 2025 at 10:48:03AM +0800, Yan Zhao wrote:
> > @@ -842,47 +881,38 @@ long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long
> >  	if (!file)
Oops. Need to check if ret == 0, and looks put_page() is not required in this
case given nr_pages == 1.
So, please ignore this comment.
> +                                       put_page(src_page++);
> +

---

## [20] Michael Roth — 2026-01-08
*Subject: Re: [PATCH v2 2/5] KVM: guest_memfd: Remove preparation tracking*

On Thu, Dec 18, 2025 at 10:53:14PM +0000, Huang, Kai wrote:
> 
> >  /*

Sean had mentioned during the PUCK prior to this that he was okay with
stripping out traces of hugepage support from kvm_gmem_populate() path,
since it's bringing about unecessary complexity for a use-case we'll
potentially never support. We will however eventually support hugepages
outside the kvm_gmem_populate() path, and the bits and pieces of the
API that plumb those details into KVM MMU code are more useful to keep
around since there's existing hugepage support in KVM MMU that make it
clearer where/when we'll need it. So I'm not sure we gain much from the
churn of stripping it out. However, if as part of wiring up hugepage
support those interfaces prove insufficient, then I wouldn't be opposed
to similarly adding pre-patches to strip it out for a cleaner base
implementation, but I don't really think that need to be part fo this
series which is focused more on the population path rather than fault
handling at run-time, so I've left things as-is for v3 for now.

> 
> Btw:

The thinking there was to try to not actively break the hugepage-related
bits that were already in place, but since we decided to implement
hugepage-related stuff for kvm_gmem_populate() as a clean follow-up
implementation, there's no need to consider the hugepage case and loop
through the page.

> discussions about AFAICT they were more related to issues regarding to 
> "mark entire folio as uptodate while only one page is processed in

I think we are considering this approach for TDX and there was some
discussion of having gmem-internal flags to select for this type of
handling, but I think that would make more sense as part of TDX-specific
enablement of in-place conversion. I'm planning to post the SNP-specific
enablement of in-place conversion patches on top of this series, so
maybe we can consider this in response to that series or as part of the
TDX-specific enablement.

-Mike

---
