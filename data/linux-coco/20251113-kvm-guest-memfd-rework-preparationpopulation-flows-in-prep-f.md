---
title: 'KVM: guest_memfd: Rework preparation/population flows in prep for in-place conversion'
date: 2025-11-13
last_reply: 2025-12-09
message_count: 37
participants: ['Michael Roth', 'Ackerley Tng', 'Yan Zhao', 'Ira Weiny', 'Vishal Annapurve', 'Vlastimil Babka', 'Sean Christopherson']
---

## [1] Michael Roth — 2025-11-13

This patchset is also available at:

  https://github.com/AMDESE/linux/tree/gmem-populate-rework-rfc1

and is based on top of kvm-x86/next (kvm-x86-next-2025.11.07)


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

It additionally removes 'preparation' tracking from guest_memfd, which would
similarly complicate locking considerations in the context of in-place
conversion (and even moreso in the context of hugepage support). This has
been discussed during both the guest_memfd calls and PUCK calls, and so far
no strong objections have been given, so hopefully that particular change
isn't too controversial.


Some items worth noting/discussing
----------------------------------

(A) Unlike TDX, which has always enforced that the source address used to
    populate the contents of gmem pages via kvm_gmem_populate() is
    page-aligned, SNP explicitly allowed for this. This unfortunately means
    that instead of a simple 1:1 correspondance between source/target pages,
    post-populate callbacks need to be able to handle straddling multiple
    source pages to populate a single target page within guest_memfd, which
    complicates the handling. While the changes to the SNP post-populate
    callback in patch #3 are not horrendous, they certainly are not ideal.
    However, architectures that never allowed a non-page-aligned source
    address can essentially ignore the src_pages/src_offset considerations
    and simply assume/enforce src_offset is 0, and that src_pages[0] is the
    source struct page of relevance for each call.

    That said, it would be possible to have SNP copy unaligned pages into
    an intermediate set of bounce-buffer pages before passing them to some
    variant of kvm_gmem_populate() that skips the GUP and just works directly
    with the kernel-allocated bounce pages, but there is a performance hit
    there, and potentially some additional complexity with the interfaces to
    handle the different flow, so it's not clear if the trade-off is worth
    it.

    Another potential approach would be to take advantage of the fact that
    all *known* VMM implementations of SNP do use page-aligned source
    addresses, so it *may* be justifiable to retroactively enforce this as
    a requirement so that the post-populate callbacks can be simplified
    accordingly.

(B) While one of the aims of this rework is to implement things such that
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


Thanks,

Mike


[1] https://lore.kernel.org/kvm/20250703062641.3247-1-yan.y.zhao@intel.com/
[2] https://lore.kernel.org/kvm/cover.1760731772.git.ackerleytng@google.com/
[3] https://lore.kernel.org/kvm/20251030200951.3402865-1-seanjc@google.com/
[4] https://lore.kernel.org/kvm/aHEwT4X0RcfZzHlt@google.com/
[5] https://lore.kernel.org/kvm/20251105-tdx-init-in-place-v1-1-1196b67d0423@intel.com/


----------------------------------------------------------------
Michael Roth (3):
      KVM: guest_memfd: Remove preparation tracking
      KVM: TDX: Document alignment requirements for KVM_TDX_INIT_MEM_REGION
      KVM: guest_memfd: GUP source pages prior to populating guest memory

 Documentation/virt/kvm/x86/intel-tdx.rst |  2 +-
 arch/x86/kvm/svm/sev.c                   | 40 +++++++++-----
 arch/x86/kvm/vmx/tdx.c                   | 20 +++----
 include/linux/kvm_host.h                 |  3 +-
 virt/kvm/guest_memfd.c                   | 89 ++++++++++++++++++--------------
 5 files changed, 88 insertions(+), 66 deletions(-)

---

## [2] Michael Roth — 2025-11-13
*Subject: [PATCH 1/3] KVM: guest_memfd: Remove preparation tracking*

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
 virt/kvm/guest_memfd.c | 47 ++++++++++++++----------------------------
 1 file changed, 15 insertions(+), 32 deletions(-)

diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index fdaea3422c30..9160379df378 100644
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
@@ -420,7 +406,7 @@ static vm_fault_t kvm_gmem_fault_user_mapping(struct vm_fault *vmf)
 
 	if (!folio_test_uptodate(folio)) {
 		clear_highpage(folio_page(folio, 0));
-		kvm_gmem_mark_prepared(folio);
+		folio_mark_uptodate(folio);
 	}
 
 	vmf->page = folio_file_page(folio, vmf->pgoff);
@@ -757,7 +743,7 @@ void kvm_gmem_unbind(struct kvm_memory_slot *slot)
 static struct folio *__kvm_gmem_get_pfn(struct file *file,
 					struct kvm_memory_slot *slot,
 					pgoff_t index, kvm_pfn_t *pfn,
-					bool *is_prepared, int *max_order)
+					int *max_order)
 {
 	struct file *slot_file = READ_ONCE(slot->gmem.file);
 	struct gmem_file *f = file->private_data;
@@ -787,7 +773,6 @@ static struct folio *__kvm_gmem_get_pfn(struct file *file,
 	if (max_order)
 		*max_order = 0;
 
-	*is_prepared = folio_test_uptodate(folio);
 	return folio;
 }
 
@@ -797,19 +782,25 @@ int kvm_gmem_get_pfn(struct kvm *kvm, struct kvm_memory_slot *slot,
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
+		unsigned long i, nr_pages = folio_nr_pages(folio);
+
+		for (i = 0; i < nr_pages; i++)
+			clear_highpage(folio_page(folio, i));
+		folio_mark_uptodate(folio);
+	}
+
+	r = kvm_gmem_prepare_folio(kvm, slot, gfn, folio);
 
 	folio_unlock(folio);
 
@@ -852,7 +843,6 @@ long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long
 		struct folio *folio;
 		gfn_t gfn = start_gfn + i;
 		pgoff_t index = kvm_gmem_get_index(slot, gfn);
-		bool is_prepared = false;
 		kvm_pfn_t pfn;
 
 		if (signal_pending(current)) {
@@ -860,19 +850,12 @@ long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long
 			break;
 		}
 
-		folio = __kvm_gmem_get_pfn(file, slot, index, &pfn, &is_prepared, &max_order);
+		folio = __kvm_gmem_get_pfn(file, slot, index, &pfn, &max_order);
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
 		WARN_ON(!IS_ALIGNED(gfn, 1 << max_order) ||
 			(npages - i) < (1 << max_order));
@@ -889,7 +872,7 @@ long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long
 		p = src ? src + i * PAGE_SIZE : NULL;
 		ret = post_populate(kvm, gfn, pfn, p, max_order, opaque);
 		if (!ret)
-			kvm_gmem_mark_prepared(folio);
+			folio_mark_uptodate(folio);
 
 put_folio_and_exit:
 		folio_put(folio);

---

## [3] Michael Roth — 2025-11-13
*Subject: [PATCH 2/3] KVM: TDX: Document alignment requirements for KVM_TDX_INIT_MEM_REGION*

Since it was never possible to use a non-PAGE_SIZE-aligned @source_addr,
go ahead and document this as a requirement, and add a KVM_BUG_ON() in
the post-populate callback handler to ensure future reworks to
guest_memfd do not violate this constraint.

Signed-off-by: Michael Roth <michael.roth@amd.com>
---
 Documentation/virt/kvm/x86/intel-tdx.rst | 2 +-
 arch/x86/kvm/vmx/tdx.c                   | 3 +++
 2 files changed, 4 insertions(+), 1 deletion(-)

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
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 3cf80babc3c1..57ed101a1181 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -3127,6 +3127,9 @@ static int tdx_gmem_post_populate(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
 	if (KVM_BUG_ON(kvm_tdx->page_add_src, kvm))
 		return -EIO;
 
+	if (KVM_BUG_ON(!PAGE_ALIGNED(src), kvm))
+		return -EINVAL;
+
 	/*
 	 * Get the source page if it has been faulted in. Return failure if the
 	 * source page has been swapped out or unmapped in primary memory.

---

## [4] Michael Roth — 2025-11-13
*Subject: [PATCH 3/3] KVM: guest_memfd: GUP source pages prior to populating guest memory*

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

Suggested-by: Sean Christopherson <seanjc@google.com>
Signed-off-by: Michael Roth <michael.roth@amd.com>
---
 arch/x86/kvm/svm/sev.c   | 40 ++++++++++++++++++++++++++------------
 arch/x86/kvm/vmx/tdx.c   | 21 +++++---------------
 include/linux/kvm_host.h |  3 ++-
 virt/kvm/guest_memfd.c   | 42 ++++++++++++++++++++++++++++++++++------
 4 files changed, 71 insertions(+), 35 deletions(-)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 0835c664fbfd..d0ac710697a2 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -2260,7 +2260,8 @@ struct sev_gmem_populate_args {
 };
 
 static int sev_gmem_post_populate(struct kvm *kvm, gfn_t gfn_start, kvm_pfn_t pfn,
-				  void __user *src, int order, void *opaque)
+				  struct page **src_pages, loff_t src_offset,
+				  int order, void *opaque)
 {
 	struct sev_gmem_populate_args *sev_populate_args = opaque;
 	struct kvm_sev_info *sev = to_kvm_sev_info(kvm);
@@ -2268,7 +2269,7 @@ static int sev_gmem_post_populate(struct kvm *kvm, gfn_t gfn_start, kvm_pfn_t pf
 	int npages = (1 << order);
 	gfn_t gfn;
 
-	if (WARN_ON_ONCE(sev_populate_args->type != KVM_SEV_SNP_PAGE_TYPE_ZERO && !src))
+	if (WARN_ON_ONCE(sev_populate_args->type != KVM_SEV_SNP_PAGE_TYPE_ZERO && !src_pages))
 		return -EINVAL;
 
 	for (gfn = gfn_start, i = 0; gfn < gfn_start + npages; gfn++, i++) {
@@ -2284,14 +2285,21 @@ static int sev_gmem_post_populate(struct kvm *kvm, gfn_t gfn_start, kvm_pfn_t pf
 			goto err;
 		}
 
-		if (src) {
-			void *vaddr = kmap_local_pfn(pfn + i);
+		if (src_pages) {
+			void *src_vaddr = kmap_local_pfn(page_to_pfn(src_pages[i]));
+			void *dst_vaddr = kmap_local_pfn(pfn + i);
 
-			if (copy_from_user(vaddr, src + i * PAGE_SIZE, PAGE_SIZE)) {
-				ret = -EFAULT;
-				goto err;
+			memcpy(dst_vaddr, src_vaddr + src_offset, PAGE_SIZE - src_offset);
+			kunmap_local(src_vaddr);
+
+			if (src_offset) {
+				src_vaddr = kmap_local_pfn(page_to_pfn(src_pages[i + 1]));
+
+				memcpy(dst_vaddr + PAGE_SIZE - src_offset, src_vaddr, src_offset);
+				kunmap_local(src_vaddr);
 			}
-			kunmap_local(vaddr);
+
+			kunmap_local(dst_vaddr);
 		}
 
 		ret = rmp_make_private(pfn + i, gfn << PAGE_SHIFT, PG_LEVEL_4K,
@@ -2331,12 +2339,20 @@ static int sev_gmem_post_populate(struct kvm *kvm, gfn_t gfn_start, kvm_pfn_t pf
 	if (!snp_page_reclaim(kvm, pfn + i) &&
 	    sev_populate_args->type == KVM_SEV_SNP_PAGE_TYPE_CPUID &&
 	    sev_populate_args->fw_error == SEV_RET_INVALID_PARAM) {
-		void *vaddr = kmap_local_pfn(pfn + i);
+		void *src_vaddr = kmap_local_pfn(page_to_pfn(src_pages[i]));
+		void *dst_vaddr = kmap_local_pfn(pfn + i);
 
-		if (copy_to_user(src + i * PAGE_SIZE, vaddr, PAGE_SIZE))
-			pr_debug("Failed to write CPUID page back to userspace\n");
+		memcpy(src_vaddr + src_offset, dst_vaddr, PAGE_SIZE - src_offset);
+		kunmap_local(src_vaddr);
+
+		if (src_offset) {
+			src_vaddr = kmap_local_pfn(page_to_pfn(src_pages[i + 1]));
+
+			memcpy(src_vaddr, dst_vaddr + PAGE_SIZE - src_offset, src_offset);
+			kunmap_local(src_vaddr);
+		}
 
-		kunmap_local(vaddr);
+		kunmap_local(dst_vaddr);
 	}
 
 	/* pfn + i is hypervisor-owned now, so skip below cleanup for it. */
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 57ed101a1181..dd5439ec1473 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -3115,37 +3115,26 @@ struct tdx_gmem_post_populate_arg {
 };
 
 static int tdx_gmem_post_populate(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
-				  void __user *src, int order, void *_arg)
+				  struct page **src_pages, loff_t src_offset,
+				  int order, void *_arg)
 {
 	struct tdx_gmem_post_populate_arg *arg = _arg;
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
 	u64 err, entry, level_state;
 	gpa_t gpa = gfn_to_gpa(gfn);
-	struct page *src_page;
 	int ret, i;
 
 	if (KVM_BUG_ON(kvm_tdx->page_add_src, kvm))
 		return -EIO;
 
-	if (KVM_BUG_ON(!PAGE_ALIGNED(src), kvm))
+	/* Source should be page-aligned, in which case src_offset will be 0. */
+	if (KVM_BUG_ON(src_offset))
 		return -EINVAL;
 
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
-	kvm_tdx->page_add_src = src_page;
+	kvm_tdx->page_add_src = src_pages[i];
 	ret = kvm_tdp_mmu_map_private_pfn(arg->vcpu, gfn, pfn);
 	kvm_tdx->page_add_src = NULL;
 
-	put_page(src_page);
-
 	if (ret || !(arg->flags & KVM_TDX_MEASURE_MEMORY_REGION))
 		return ret;
 
diff --git a/include/linux/kvm_host.h b/include/linux/kvm_host.h
index d93f75b05ae2..7e9d2403c61f 100644
--- a/include/linux/kvm_host.h
+++ b/include/linux/kvm_host.h
@@ -2581,7 +2581,8 @@ int kvm_arch_gmem_prepare(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn, int max_ord
  * Returns the number of pages that were populated.
  */
 typedef int (*kvm_gmem_populate_cb)(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
-				    void __user *src, int order, void *opaque);
+				    struct page **src_pages, loff_t src_offset,
+				    int order, void *opaque);
 
 long kvm_gmem_populate(struct kvm *kvm, gfn_t gfn, void __user *src, long npages,
 		       kvm_gmem_populate_cb post_populate, void *opaque);
diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index 9160379df378..e9ac3fd4fd8f 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -814,14 +814,17 @@ int kvm_gmem_get_pfn(struct kvm *kvm, struct kvm_memory_slot *slot,
 EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_gmem_get_pfn);
 
 #ifdef CONFIG_HAVE_KVM_ARCH_GMEM_POPULATE
+
+#define GMEM_GUP_NPAGES (1UL << PMD_ORDER)
+
 long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long npages,
 		       kvm_gmem_populate_cb post_populate, void *opaque)
 {
 	struct kvm_memory_slot *slot;
-	void __user *p;
-
+	struct page **src_pages;
 	int ret = 0, max_order;
-	long i;
+	loff_t src_offset = 0;
+	long i, src_npages;
 
 	lockdep_assert_held(&kvm->slots_lock);
 
@@ -836,9 +839,28 @@ long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long
 	if (!file)
 		return -EFAULT;
 
+	npages = min_t(ulong, slot->npages - (start_gfn - slot->base_gfn), npages);
+	npages = min_t(ulong, npages, GMEM_GUP_NPAGES);
+
+	if (src) {
+		src_npages = IS_ALIGNED((unsigned long)src, PAGE_SIZE) ? npages : npages + 1;
+
+		src_pages = kmalloc_array(src_npages, sizeof(struct page *), GFP_KERNEL);
+		if (!src_pages)
+			return -ENOMEM;
+
+		ret = get_user_pages_fast((unsigned long)src, src_npages, 0, src_pages);
+		if (ret < 0)
+			return ret;
+
+		if (ret != src_npages)
+			return -ENOMEM;
+
+		src_offset = (loff_t)(src - PTR_ALIGN_DOWN(src, PAGE_SIZE));
+	}
+
 	filemap_invalidate_lock(file->f_mapping);
 
-	npages = min_t(ulong, slot->npages - (start_gfn - slot->base_gfn), npages);
 	for (i = 0; i < npages; i += (1 << max_order)) {
 		struct folio *folio;
 		gfn_t gfn = start_gfn + i;
@@ -869,8 +891,8 @@ long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long
 			max_order--;
 		}
 
-		p = src ? src + i * PAGE_SIZE : NULL;
-		ret = post_populate(kvm, gfn, pfn, p, max_order, opaque);
+		ret = post_populate(kvm, gfn, pfn, src ? &src_pages[i] : NULL,
+				    src_offset, max_order, opaque);
 		if (!ret)
 			folio_mark_uptodate(folio);
 
@@ -882,6 +904,14 @@ long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long
 
 	filemap_invalidate_unlock(file->f_mapping);
 
+	if (src) {
+		long j;
+
+		for (j = 0; j < src_npages; j++)
+			put_page(src_pages[j]);
+		kfree(src_pages);
+	}
+
 	return ret && !i ? ret : i;
 }
 EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_gmem_populate);

---

## [5] Ackerley Tng — 2025-11-17
*Subject: Re: [PATCH 1/3] KVM: guest_memfd: Remove preparation tracking*

Michael Roth <michael.roth@amd.com> writes:

> guest_memfd currently uses the folio uptodate flag to track:
>

This looks good to me, thanks!

What do you think of moving preparation (or SNP-specific work) to be
done when the page is actually mapped by KVM instead? So whatever's done
in preparation is now called from KVM instead of within guest_memfd [1]?

I'm concerned about how this preparation needs to be done for the entire
folio. With huge pages, could it be weird if actually only one page in
the huge page is faulted in, and hence only that one page needs to be
prepared, instead of the entire huge page?

In the other series [2], there was a part about how guest_memfd should
invalidate the shared status on conversion from private to shared. Is
that still an intended step, after this series to remove preparation
tracking?

[1] https://lore.kernel.org/all/diqzcy7op5wg.fsf@google.com/
[2] https://lore.kernel.org/all/20250613005400.3694904-4-michael.roth@amd.com/

> Signed-off-by: Michael Roth <michael.roth@amd.com>
> ---

---

## [6] Michael Roth — 2025-11-18
*Subject: Re: [PATCH 1/3] KVM: guest_memfd: Remove preparation tracking*

On Mon, Nov 17, 2025 at 03:58:46PM -0800, Ackerley Tng wrote:
> Michael Roth <michael.roth@amd.com> writes:
> 

Now that preparation tracking is removed, it is now completely decoupled
from the kvm_gmem_populate() path and fully contained in
kvm_gmem_get_pfn(), where it becomes a lot more straightforward to move
this into the KVM MMU fault path.

But gmem currently also handles the inverse operation via the
gmem_invalidate() hooks, which is driven separately from the KVM MMU
notifiers. And it's not so simple to just plumb it into those paths,
but invalidation in this sense involves clearing the 'validated' bit
in the RMP table for the page, which is a destructive operation, whereas
the notifiers as they exist today can be using for non-destructive
operations like simply rebuilding stage2 mappings. So we'd probably need
to think through what that would look like if we really want to move
preparation/un-preparation out of gmem.

So I think it makes sense to consider this patch as-is as a stepping
stone toward that, but I don't have any objection to going that
direction. Curious what others have to say though.

> 
> I'm concerned about how this preparation needs to be done for the entire

In previous iterations of THP support for SNP[1] I think this worked out
okay. You'd prepare optimistically prepare the whole huge folio, and if KVM
mapped it as, say, 4K, you'd get an RMP fault and PSMASH the RMP table
to smaller 4K/prepare entries. But that was before in-place conversion
was in the picture, so we didn't have to worry about ever converting
those other prepared entries to a shared state, so you could defer
everything until folio cleanup. For in-place we'd need to take the
memory attributes for the range we are mapping into account and clamp
the range down to a smaller order accordingly before issuing the prepare
hook. But I think it would still be doable.

Maybe more directly would be to let KVM MMU tell us the max mapping
level it will be using so we can just defer all the attribute handling
to KVM. But this same approach could still be done with gmem issuing
the prepare hooks in the case of in-place conversion. So I think it's
doable either way... hard to tell what approach is cleaner without some
hugepage patches on top. I'm still trying to get update THP on top of
your in-place conversion patches posted and maybe it'll be easier to see
what things would look like in that context.

[1] https://lore.kernel.org/kvm/20241212063635.712877-1-michael.roth@amd.com/

> 
> In the other series [2], there was a part about how guest_memfd should

Yes, I was still planning to have gmem drive prepare/invalidate where
needed. If we move things out to MMU that will require some rethinking
however.


Thanks,

Mike

> 
> [1] https://lore.kernel.org/all/diqzcy7op5wg.fsf@google.com/

---

## [7] Yan Zhao — 2025-11-20
*Subject: Re: [PATCH 3/3] KVM: guest_memfd: GUP source pages prior to
 populating guest memory*

On Thu, Nov 13, 2025 at 05:07:59PM -0600, Michael Roth wrote:
> Currently the post-populate callbacks handle copying source pages into
> private GPA ranges backed by guest_memfd, where kvm_gmem_populate()
IIUC, src_offset is the src's offset from the first page. e.g.,
src could be 0x7fea82684100, with src_offset=0x100, while npages could be 512.

Then it looks like the two memcpy() calls here only work when npages == 1 ?

>  			}
> -			kunmap_local(vaddr);
	if (KVM_BUG_ON(src_offset, kvm))

>  		return -EINVAL;
>  
src_pages[0] ? i is not initialized. 

Should there also be a KVM_BUG_ON(order > 0, kvm) ?

>  	ret = kvm_tdp_mmu_map_private_pfn(arg->vcpu, gfn, pfn);
>  	kvm_tdx->page_add_src = NULL;
Limiting GMEM_GUP_NPAGES to PMD_ORDER may only work when the max_order of a huge
folio is 2MB. What if the max_order returned from  __kvm_gmem_get_pfn() is 1GB
when src_pages[] can only hold up to 512 pages?

Increasing GMEM_GUP_NPAGES to (1UL << PUD_ORDER) is probabaly not a good idea.

Given both TDX/SNP map at 4KB granularity, why not just invoke post_populate()
per 4KB while removing the max_order from post_populate() parameters, as done
in Sean's sketch patch [1]?

Then the WARN_ON() in kvm_gmem_populate() can be removed, which would be easily
triggered by TDX when max_order > 0 && npages == 1:

      WARN_ON(!IS_ALIGNED(gfn, 1 << max_order) ||
              (npages - i) < (1 << max_order));


[1] https://lore.kernel.org/all/aHEwT4X0RcfZzHlt@google.com/

>  long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long npages,
>  		       kvm_gmem_populate_cb post_populate, void *opaque)
Why src_offset is not 0 starting from the 2nd page?

>  		if (!ret)
>  			folio_mark_uptodate(folio);

---

## [8] Yan Zhao — 2025-11-20
*Subject: Re: [PATCH 1/3] KVM: guest_memfd: Remove preparation tracking*

On Thu, Nov 13, 2025 at 05:07:57PM -0600, Michael Roth wrote:
> @@ -797,19 +782,25 @@ int kvm_gmem_get_pfn(struct kvm *kvm, struct kvm_memory_slot *slot,
>  {
Here, the entire folio is cleared only when the folio is not marked uptodate.
Then, please check my questions at the bottom

> +	}
> +
TDX could hit this warning easily when npages == 1, max_order == 9.

> @@ -889,7 +872,7 @@ long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long
>  		p = src ? src + i * PAGE_SIZE : NULL;
As also asked in [1], why is the entire folio marked as uptodate here? Why does
kvm_gmem_get_pfn() clear all pages of a huge folio when the folio isn't marked
uptodate?

It's possible (at least for TDX) that a huge folio is only partially populated
by kvm_gmem_populate(). Then kvm_gmem_get_pfn() faults in another part of the
huge folio. For example, in TDX, GFN 0x81f belongs to the init memory region,
while GFN 0x820 is faulted after TD is running. However, these two GFNs can
belong to the same folio of order 9.

Note: the current code should not impact TDX. I'm just asking out of curiosity:)

[1] https://lore.kernel.org/all/aQ3uj4BZL6uFQzrD@yzhao56-desk.sh.intel.com/

---

## [9] Ira Weiny — 2025-11-20
*Subject: Re: [PATCH 3/3] KVM: guest_memfd: GUP source pages prior to
 populating guest memory*

Michael Roth wrote:
> Currently the post-populate callbacks handle copying source pages into
> private GPA ranges backed by guest_memfd, where kvm_gmem_populate()

After thinking on the alignment issue:

In the direction we are going, in-place conversion, I'm struggling to
see why keeping the complexity of allowing a miss-aligned src pointer for
the data (which BTW seems to require at least an aligned size to (x *
PAGE_SIZE to not leak data?) is valuable.

Once in-place is complete the entire page needs to be converted to private
and so it seems keeping that alignment just makes things cleaner without
really restricting any known use cases.

General comments below.

[snip]

> @@ -2284,14 +2285,21 @@ static int sev_gmem_post_populate(struct kvm *kvm, gfn_t gfn_start, kvm_pfn_t pf
>  			goto err;
                                                                                      ^^^^^^^^^^
									PAGE_SIZE - src_offset?

> +				kunmap_local(src_vaddr);
>  			}
                                                                                      ^^^^^^^^^^
									PAGE_SIZE - src_offset?
> +			kunmap_local(src_vaddr);
> +		}

This failed to compile, need the kvm parameter in the macro.

>  		return -EINVAL;
>  

i is uninitialized here.  src_pages[0] should be fine.

All the src_offset stuff in the rest of the patch would just go away if we
made that restriction for SNP.  You mentioned there was not a real use
case for it.  Also technically I think TDX _could_ do the same thing SNP
populate is doing.  The kernel could map the buffer do the offset copy to
the destination page and do the in-place encryption.  But I've not tried
it because I really think this is more effort than the whole kernel needs
to do.  If a use case becomes necessary it may be better to have that in
the gmem core once TDX is tested.

Thoughts?
Ira

[snip]

---

## [10] Michael Roth — 2025-11-21
*Subject: Re: [PATCH 1/3] KVM: guest_memfd: Remove preparation tracking*

On Thu, Nov 20, 2025 at 05:12:55PM +0800, Yan Zhao wrote:
> On Thu, Nov 13, 2025 at 05:07:57PM -0600, Michael Roth wrote:
> > @@ -797,19 +782,25 @@ int kvm_gmem_get_pfn(struct kvm *kvm, struct kvm_memory_slot *slot,

Yes, in this patch at least where I tried to mirror the current logic. I
would not be surprised if we need to rework things for inplace/hugepage
support though, but decoupling 'preparation' from the uptodate flag is
the main goal here.

> 
> > +	}

Yes, this will need to change to handle that. I don't think I had to
change this for previous iterations of SNP hugepage support, but
there are definitely cases where a sub-2M range might get populated 
even though it's backed by a 2M folio, so I'm not sure why I didn't
hit it there.

But I'm taking Sean's cue on touching as little of the existing
hugepage logic as possible in this particular series so we can revisit
the remaining changes with some better context.

> 
> > @@ -889,7 +872,7 @@ long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long

Quoting your example from[1] for more context:

> I also have a question about this patch:
> 

In SNP hugepage patchset you responded to, it would only mark A1 as
prepared/cleared. There was 4K-granularity tracking added to handle this.
There was an odd subtlety in that series though: it was defaulting to the
folio_order() for the prep-tracking/post-populate, but it would then clamp
it down based on the max order possible according whether that particular
order was a homogenous range of KVM_MEMORY_ATTRIBUTE_PRIVATE. Which is not
a great way to handle things, and I don't remember if I'd actually intended
to implement it that way or not... that's probably why I never tripped over
the WARN_ON() above, now that I think of it.

But neither of these these apply to any current plans for hugepage support
that I'm aware of, so probably not worth working through what that series
did and look at this from a fresh perspective.

> 
> (2) kvm_gmem_get_pfn() later faults in page A2.

Assuming this patch goes upstream in some form, we will now have the
following major differences versus previous code:

  1) uptodate flag only tracks whether a folio has been cleared
  2) gmem always calls kvm_arch_gmem_prepare() via kvm_gmem_get_pfn() and
     the architecture can handle it's own tracking at whatever granularity
     it likes.

My hope is that 1) can similarly be done in such a way that gmem does not
need to track things at sub-hugepage granularity and necessitate the need
for some new data structure/state/flag to track sub-page status.

My understanding based on prior discussion in guest_memfd calls was that
it would be okay to go ahead and clear the entire folio at initial allocation
time, and basically never mess with it again. It was also my understanding
that for TDX it might even be optimal to completely skip clearing the folio
if it is getting mapped into SecureEPT as a hugepage since the TDX module
would handle that, but that maybe conversely after private->shared there
would be some need to reclear... I'll try to find that discussion and
refresh. Vishal I believe suggested some flags to provide more control over
this behavior.

> 
> It's possible (at least for TDX) that a huge folio is only partially populated

Would the above scheme of clearing the entire folio up front and not re-clearing
at fault time work for this case?

Thanks,

Mike

> 
> Note: the current code should not impact TDX. I'm just asking out of curiosity:)

---

## [11] Michael Roth — 2025-11-21
*Subject: Re: [PATCH 3/3] KVM: guest_memfd: GUP source pages prior to
 populating guest memory*

On Thu, Nov 20, 2025 at 05:11:48PM +0800, Yan Zhao wrote:
> On Thu, Nov 13, 2025 at 05:07:59PM -0600, Michael Roth wrote:
> > Currently the post-populate callbacks handle copying source pages into

src_offset ends up being the offset into the pair of src pages that we
are using to fully populate a single dest page with each iteration. So
if we start at src_offset, read a page worth of data, then we are now at
src_offset in the next src page and the loop continues that way even if
npages > 1.

If src_offset is 0 we never have to bother with straddling 2 src pages so
the 2nd memcpy is skipped on every iteration.

That's the intent at least. Is there a flaw in the code/reasoning that I
missed?

> 
> >  			}

Sorry, I switched on TDX options for compile testing but I must have done a
sloppy job confirming it actually built. I'll re-test push these and squash
in the fixes in the github tree.

> 
> Should there also be a KVM_BUG_ON(order > 0, kvm) ?

Seems reasonable, but I'm not sure this is the right patch. Maybe I
could squash it into the preceeding documentation patch so as to not
give the impression this patch changes those expectations in any way.

> 
> >  	ret = kvm_tdp_mmu_map_private_pfn(arg->vcpu, gfn, pfn);

This was necessarily chosen in prep for hugepages, but more about my
unease at letting userspace GUP arbitrarilly large ranges. PMD_ORDER
happens to align with 2MB hugepages while seeming like a reasonable
batching value so that's why I chose it.

Even with 1GB support, I wasn't really planning to increase it. SNP
doesn't really make use of RMP sizes >2MB, and it sounds like TDX
handles promotion in a completely different path. So atm I'm leaning
toward just letting GMEM_GUP_NPAGES be the cap for the max page size we
support for kvm_gmem_populate() path and not bothering to change it
until a solid use-case arises.

> 
> Increasing GMEM_GUP_NPAGES to (1UL << PUD_ORDER) is probabaly not a good idea.

That's an option too, but SNP can make use of 2MB pages in the
post-populate callback so I don't want to shut the door on that option
just yet if it's not too much of a pain to work in. Given the guest BIOS
lives primarily in 1 or 2 of these 2MB regions the benefits might be
worthwhile, and SNP doesn't have a post-post-populate promotion path
like TDX (at least, not one that would help much for guest boot times)

Thanks,

Mike

> 
> Then the WARN_ON() in kvm_gmem_populate() can be removed, which would be easily

---

## [12] Yan Zhao — 2025-11-24
*Subject: Re: [PATCH 3/3] KVM: guest_memfd: GUP source pages prior to
 populating guest memory*

On Fri, Nov 21, 2025 at 07:01:44AM -0600, Michael Roth wrote:
> On Thu, Nov 20, 2025 at 05:11:48PM +0800, Yan Zhao wrote:
> > On Thu, Nov 13, 2025 at 05:07:59PM -0600, Michael Roth wrote:
Oh, I got you. SNP expects a single src_offset applies for each src page.

So if npages = 2, there're 4 memcpy() calls.

src:  |---------|---------|---------|  (VA contiguous)
          ^         ^         ^
          |         |         |
dst:      |---------|---------|   (PA contiguous)


I previously incorrectly thought kvm_gmem_populate() should pass in src_offset
as 0 for the 2nd src page.

Would you consider checking if params.uaddr is PAGE_ALIGNED() in
snp_launch_update() to simplify the design?

> > 
> > >  			}
I don't think it should be documented as a user requirement.

However, we need to comment out that this assertion is due to that
tdx_vcpu_init_mem_region() passes npages as 1 to kvm_gmem_populate().

> > 
> > >  	ret = kvm_tdp_mmu_map_private_pfn(arg->vcpu, gfn, pfn);
The problem is that with hugetlb-based guest_memfd, the folio itself could be
of 1GB, though SNP and TDX can force mapping at only 4KB.

Then since max_order = folio_order(folio) (at least in the tree for [1]), 
WARN_ON() in kvm_gmem_populate() could still be hit:

folio = __kvm_gmem_get_pfn(file, slot, index, &pfn, &max_order);
WARN_ON(!IS_ALIGNED(gfn, 1 << max_order) ||
        (npages - i) < (1 << max_order));

TDX is even easier to hit this warning because it always passes npages as 1.

[1] https://lore.kernel.org/all/cover.1747264138.git.ackerleytng@google.com

 
> > Increasing GMEM_GUP_NPAGES to (1UL << PUD_ORDER) is probabaly not a good idea.
> > 
I see.

So, what about below change?

--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -878,11 +878,10 @@ long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long
                }

                folio_unlock(folio);
-               WARN_ON(!IS_ALIGNED(gfn, 1 << max_order) ||
-                       (npages - i) < (1 << max_order));

                ret = -EINVAL;
-               while (!kvm_range_has_memory_attributes(kvm, gfn, gfn + (1 << max_order),
+               while (!IS_ALIGNED(gfn, 1 << max_order) || (npages - i) < (1 << max_order) ||
+                      !kvm_range_has_memory_attributes(kvm, gfn, gfn + (1 << max_order),
                                                        KVM_MEMORY_ATTRIBUTE_PRIVATE,
                                                        KVM_MEMORY_ATTRIBUTE_PRIVATE)) {
                        if (!max_order)



> 
> >

---

## [13] Ira Weiny — 2025-11-24
*Subject: Re: [PATCH 3/3] KVM: guest_memfd: GUP source pages prior to
 populating guest memory*

Yan Zhao wrote:
> On Fri, Nov 21, 2025 at 07:01:44AM -0600, Michael Roth wrote:
> > On Thu, Nov 20, 2025 at 05:11:48PM +0800, Yan Zhao wrote:

[snip]

> > > > @@ -2284,14 +2285,21 @@ static int sev_gmem_post_populate(struct kvm *kvm, gfn_t gfn_start, kvm_pfn_t pf
> > > >  			goto err;

I'm not following the above diagram.  Either src and dst are aligned and
src_pages points to exactly one page.  OR not aligned and src_pages points
to 2 pages.

src:  |---------|---------|  (VA contiguous)
          ^         ^
          |         |
dst:      |---------|   (PA contiguous)

Regardless I think this is all bike shedding over a feature which I really
don't think buys us much trying to allow the src to be missaligned.

> 
> I previously incorrectly thought kvm_gmem_populate() should pass in src_offset

I think this would help a lot...  ATM I'm not even sure the algorithm
works if order is not 0.

[snip]

>  
> > > Increasing GMEM_GUP_NPAGES to (1UL << PUD_ORDER) is probabaly not a good idea.

I'm not following what this change has to do with moving GUP out of the
post_populate calls?

Ira

> 
> --- a/virt/kvm/guest_memfd.c

[snip]

---

## [14] Yan Zhao — 2025-11-25
*Subject: Re: [PATCH 3/3] KVM: guest_memfd: GUP source pages prior to
 populating guest memory*

On Mon, Nov 24, 2025 at 09:53:03AM -0600, Ira Weiny wrote:
> Yan Zhao wrote:
> > On Fri, Nov 21, 2025 at 07:01:44AM -0600, Michael Roth wrote:
Hmm, the src/dst legend in the above diagram just denotes source and target,
not the actual src user pointer.

> src_pages points to exactly one page.  OR not aligned and src_pages points
> to 2 pages.
Without this change, TDX (and possibly SNP) would hit a warning when max_order>0.
(either GUP in 4KB granularity or this change can get rid of the warning).

Since this series already contains changes for 2MB pages (e.g., batched GUP to
allow SNP to map 2MB pages, and actually we don't need the change in patch 1
without considering huge pages), I don't see any reason to leave this change out
of tree.

Note: kvm_gmem_populate() already contains the logic of

    while (!kvm_range_has_memory_attributes(kvm, gfn, gfn + (1 << max_order),
                                            KVM_MEMORY_ATTRIBUTE_PRIVATE,
                                            KVM_MEMORY_ATTRIBUTE_PRIVATE)) {
        if (!max_order)
            goto put_folio_and_exit;
        max_order--;
    }


Also, the series is titled "Rework preparation/population flows in prep for
in-place conversion", so it's not just about "moving GUP out of the
post_populate", right? :)

> > --- a/virt/kvm/guest_memfd.c
> > +++ b/virt/kvm/guest_memfd.c

---

## [15] Yan Zhao — 2025-11-25
*Subject: Re: [PATCH 1/3] KVM: guest_memfd: Remove preparation tracking*

On Fri, Nov 21, 2025 at 06:43:14AM -0600, Michael Roth wrote:
> On Thu, Nov 20, 2025 at 05:12:55PM +0800, Yan Zhao wrote:
> > On Thu, Nov 13, 2025 at 05:07:57PM -0600, Michael Roth wrote:
Could you elaborate a little why the decoupling is needed if it's not for
hugepage?


> > > +	}
> > > +
Frankly, I don't understand why this patch 1 is required if we only want "moving
GUP out of post_populate()" to work for 4KB folios.

> > 
> > > @@ -889,7 +872,7 @@ long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long
You mean code in
https://github.com/amdese/linux/commits/snp-inplace-conversion-rfc1 ?

> prepared/cleared. There was 4K-granularity tracking added to handle this.
I don't find the code that marks only A1 as "prepared/cleared".
Instead, I just found folio_mark_uptodate() is invoked by kvm_gmem_populate()
to mark the entire folio A as uptodate.

However, according to your statement below that "uptodate flag only tracks
whether a folio has been cleared", I don't follow why and where the entire folio
A would be cleared if kvm_gmem_populate() only adds page A1.

> There was an odd subtlety in that series though: it was defaulting to the
> folio_order() for the prep-tracking/post-populate, but it would then clamp
2) looks good to me.

> My hope is that 1) can similarly be done in such a way that gmem does not
> need to track things at sub-hugepage granularity and necessitate the need
I actually don't understand what uptodate flag helps gmem to track.
Why can't clear_highpage() be done inside arch specific code? TDX doesn't need
this clearing after all.

> My understanding based on prior discussion in guest_memfd calls was that
> it would be okay to go ahead and clear the entire folio at initial allocation
That's where I don't follow in this patch.
I don't see where the entire folio A is cleared if it's only partially mapped by
kvm_gmem_populate(). kvm_gmem_get_pfn() won't clear folio A either due to
kvm_gmem_populate() has set the uptodate flag.

> that for TDX it might even be optimal to completely skip clearing the folio
> if it is getting mapped into SecureEPT as a hugepage since the TDX module
This case doesn't affect TDX, because TDX clearing private pages internally in
SEAM APIs. So, as long as kvm_gmem_get_pfn() does not invoke clear_highpage()
after making a folio private, it works fine for TDX.

I was just trying to understand why SNP needs the clearing of entire folio in
kvm_gmem_get_pfn() while I don't see how the entire folio is cleared when it's
partially mapped in kvm_gmem_populate().
Also, I'm wondering if it would be better if SNP could move the clearing of
folio into something like kvm_arch_gmem_clear(), just as kvm_arch_gmem_prepare()
which is always invoked by kvm_gmem_get_pfn() and the architecture can handle
it's own tracking at whatever granularity.

 
> > Note: the current code should not impact TDX. I'm just asking out of curiosity:)
> >

---

## [16] Vishal Annapurve — 2025-11-30
*Subject: Re: [PATCH 1/3] KVM: guest_memfd: Remove preparation tracking*

On Mon, Nov 24, 2025 at 7:15 PM Yan Zhao <yan.y.zhao@intel.com> wrote:
>
> On Fri, Nov 21, 2025 at 06:43:14AM -0600, Michael Roth wrote:

IMO, decoupling is useful in general and we don't necessarily need to
wait till hugepage support lands to clean up this logic. Current
preparation logic has created some confusion regarding multiple
features for guest_memfd under discussion such as generic write, uffd
support, and direct map removal. It would be useful to simplify the
guest_memfd logic in this regard.

>
>

I think kvm_gmem_populate() is currently only used by SNP and TDX
logic, I don't see an issue with marking the complete folio as
uptodate even if its partially updated by kvm_gmem_populate() paths as
the private memory will eventually get initialized anyways.

>
> > There was an odd subtlety in that series though: it was defaulting to the

Target audience for guest_memfd includes non-confidential VMs as well.
Inline with shmem and other filesystems, guest_memfd should clear
pages on fault before handing them out to the users. There should be a
way to opt-out of this behavior for certain private faults like for
SNP/TDX and possibly for CCA as well.

>
> > My understanding based on prior discussion in guest_memfd calls was that

Since kvm_gmem_populate() is specific to SNP and TDX VMs, I don't
think this behavior is concerning.

---

## [17] Vishal Annapurve — 2025-11-30
*Subject: Re: [PATCH 3/3] KVM: guest_memfd: GUP source pages prior to
 populating guest memory*

On Fri, Nov 21, 2025 at 5:02 AM Michael Roth <michael.roth@amd.com> wrote:
>
> >

Given the small initial payload size, do you really think optimizing
for setting up huge page-aligned RMP entries is worthwhile?
The code becomes somewhat complex when trying to get this scenario
working and IIUC it depends on userspace-passed initial payload
regions aligning to the huge page size. What happens if userspace
tries to trigger snp_launch_update() for two unaligned regions within
the same huge page?

What Sean suggested earlier[1] seems relatively simpler to maintain.

[1] https://lore.kernel.org/kvm/aHEwT4X0RcfZzHlt@google.com/

>
> Thanks,

---

## [18] Vishal Annapurve — 2025-11-30
*Subject: Re: [PATCH 3/3] KVM: guest_memfd: GUP source pages prior to
 populating guest memory*

On Mon, Nov 24, 2025 at 1:34 AM Yan Zhao <yan.y.zhao@intel.com> wrote:
>
> > > > +                 if (src_offset) {

IIUC, this ship has sailed, as asserting this would break existing
userspace which can pass unaligned userspace buffers.

---

## [19] Yan Zhao — 2025-12-01
*Subject: Re: [PATCH 1/3] KVM: guest_memfd: Remove preparation tracking*

On Sun, Nov 30, 2025 at 05:35:41PM -0800, Vishal Annapurve wrote:
> On Mon, Nov 24, 2025 at 7:15 PM Yan Zhao <yan.y.zhao@intel.com> wrote:
> > > > > @@ -889,7 +872,7 @@ long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long
Still using the above example,
If only page A1 is passed to sev_gmem_post_populate(), will SNP initialize the
entire folio A?
- if yes, could you kindly point me to the code that does this? .
- if sev_gmem_post_populate() only initializes page A1, after marking the
  complete folio A as uptodate in kvm_gmem_populate(), later faulting in page A2
  in kvm_gmem_get_pfn() will not clear page A2 by invoking clear_highpage(),
  since the entire folio A is uptodate. I don't understand why this is OK.
  Or what's the purpose of invoking clear_highpage() on other folios?

Thanks
Yan

---

## [20] Vishal Annapurve — 2025-12-01
*Subject: Re: [PATCH 1/3] KVM: guest_memfd: Remove preparation tracking*

On Sun, Nov 30, 2025 at 6:53 PM Yan Zhao <yan.y.zhao@intel.com> wrote:
>
> On Sun, Nov 30, 2025 at 05:35:41PM -0800, Vishal Annapurve wrote:

I think sev_gmem_post_populate() only initializes the ranges marked
for snp_launch_update(). Since the current code lacks a hugepage
provider, the kvm_gmem_populate() doesn't need to explicitly clear
anything for 4K backings during kvm_gmem_populate().

I see your point. Once a hugepage provider lands, kvm_gmem_populate()
can first invoke clear_highpage() or an equivalent API on a complete
huge folio before calling the architecture-specific post-populate hook
to keep the implementation consistent.

Subsequently, we need to figure out a way to avoid this clearing for
SNP/TDX/CCA private faults.

>
> Thanks

---

## [21] Michael Roth — 2025-12-01
*Subject: Re: [PATCH 3/3] KVM: guest_memfd: GUP source pages prior to
 populating guest memory*

On Sun, Nov 30, 2025 at 05:47:37PM -0800, Vishal Annapurve wrote:
> On Mon, Nov 24, 2025 at 1:34 AM Yan Zhao <yan.y.zhao@intel.com> wrote:
> >

Actually, on the PUCK call before I sent this patchset Sean/Paolo seemed
to be okay with the prospect of enforcing that params.uaddr is
PAGE_ALIGNED(), since all *known* userspace implementations do use a
page-aligned params.uaddr and this would be highly unlikely to have any
serious fallout.

However, it was suggested that I post the RFC with non-page-aligned
handling intact so we can have some further discussion about it. That
would be one of the 3 approaches listed under (A) in the cover letter.
(Sean proposed another option that he might still advocate for, also
listed in the cover letter under (A), but wanted to see what this looked
like first).

Personally, I'm fine with forcing params.uaddr to. But there is still some
slight risk that some VMM out there flying under the radar will surface
this userspace breakage and that won't be fun to deal with.

IMO, if an implementation wants to enforce page alignment, they
can simply assert(src_offset == 0) in the post-populate callback and
just treat src_pages[0] as if it was the only src input, like what
was done in the tdx_post_populate() callback here. The overall changes
seemed trivial enough that I don't see it being a headache for platforms
that enforce that src pointer is PAGE-ALIGNED. And for platforms like
SNP that don't, it does not seem like a huge headache to straddle 2 src
pages for each PFN we're populating.

Maybe some better comments/documentation around kvm_gmem_populate()
would more effectively alleviate potential confusion from new users
of the proposed interface.

-Mike

---

## [22] Michael Roth — 2025-12-01
*Subject: Re: [PATCH 3/3] KVM: guest_memfd: GUP source pages prior to
 populating guest memory*

On Mon, Nov 24, 2025 at 05:31:46PM +0800, Yan Zhao wrote:
> On Fri, Nov 21, 2025 at 07:01:44AM -0600, Michael Roth wrote:
> > On Thu, Nov 20, 2025 at 05:11:48PM +0800, Yan Zhao wrote:

This was an option mentioned in the cover letter and during PUCK. I am
not opposed if that's the direction we decide, but I also don't think
it makes big difference since:

   int (*kvm_gmem_populate_cb)(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
                               struct page **src_pages, loff_t src_offset,
                               int order, void *opaque);

basically reduces to Sean's originally proposed:

   int (*kvm_gmem_populate_cb)(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
                               struct page *src_pages, int order,
                               void *opaque);

for any platform that enforces that the src is page-aligned, which
doesn't seem like a huge technical burden, IMO, despite me initially
thinking it would be gross when I brought this up during the PUCK call
that preceeding this posting.

> 
> > > 

I didn't necessarily mean in the documentation, but mainly some patch
other than this. If we add that check here as part of this patch, we
give the impression that the order expectations are changing as a result
of the changes here, when in reality they are exactly the same as
before.

If not the documentation patch here, then I don't think it really fits
in this series at all and would be more of a standalone patch against
kvm/next.

The change here:

 -	if (KVM_BUG_ON(!PAGE_ALIGNED(src), kvm))
 +	/* Source should be page-aligned, in which case src_offset will be 0. */
 +	if (KVM_BUG_ON(src_offset))

made sense as part of this patch, because now that we are passing struct
page *src_pages, we can no longer infer alignment from 'src' field, and
instead need to infer it from src_offset being 0.

> 
> However, we need to comment out that this assertion is due to that

You mean for the KVM_BUG_ON(order > 0, kvm) you're proposing to add?
Again, if feels awkward to address this as part of this series since it
is an existing/unchanged behavior and not really the intent of this
patchset.

> 
> > > 

If TDX wants to unload handling of page-clearing to its per-page
post-populate callback and tie that its shared/private tracking that's
perfectly fine by me.

*How* TDX tells gmem it wants this different behavior is a topic for a
follow-up patchset, Vishal suggested kernel-internal flags to
kvm_gmem_create(), which seemed reasonable to me. In that case, uptodate
flag would probably just default to set and punt to post-populate/prep
hooks, because we absolutely *do not* want to have to re-introduce per-4K
tracking of this type of state within gmem, since getting rid of that sort
of tracking requirement within gmem is the entire motivation of this
series. And since, within this series, the uptodate flag and
prep-tracking both have the same 4K granularity, it seems unecessary to
address this here.

If you were to send a patchset on top of this (or even independently) that
introduces said kernel-internal gmem flag to offload uptodate-tracking to
post-populate/prep hooks, and utilize it to optimize the current 4K-only
TDX implementation by letting TDX module handle the initial
page-clearing, then I think that change/discussion can progress without
being blocked in any major way by this series.

But I don't think we need to flesh all that out here, so long as we are
aware of this as a future change/requirement and have reasonable
indication that it is compatible with this series.

> 
> Then since max_order = folio_order(folio) (at least in the tree for [1]), 

Yes, in the SNP implementation of hugetlb I ended up removing this
warning, and in that case I also ended up forcing kvm_gmem_populate() to
be 4K-only:

  https://github.com/AMDESE/linux/blob/snp-hugetlb-v2-wip0/virt/kvm/guest_memfd.c#L2372

but it makes a lot more sense to make those restrictions and changes in
the context of hugepage support, rather than this series which is trying
very hard to not do hugepage enablement, but simply keep what's partially
there intact while reworking other things that have proven to be
continued impediments to both in-place conversion and hugepage
enablement.

Also, there's talk now of enabling hugepages even without in-place
conversion for hugetlbfs, and that will likely be the same path we
follow for THP to remain in alignment. Rather than anticipating what all
these changes will mean WRT hugepage implementation/requirements, I
think it will be fruitful to remove some of the baggage that will
complicate that process/discussion like this patchset attempts.

-Mike

> 
> TDX is even easier to hit this warning because it always passes npages as 1.

---

## [23] Michael Roth — 2025-12-01
*Subject: Re: [PATCH 1/3] KVM: guest_memfd: Remove preparation tracking*

On Tue, Nov 25, 2025 at 11:13:25AM +0800, Yan Zhao wrote:
> On Fri, Nov 21, 2025 at 06:43:14AM -0600, Michael Roth wrote:
> > On Thu, Nov 20, 2025 at 05:12:55PM +0800, Yan Zhao wrote:

For instance, for in-place conversion:

  1. initial allocation: clear, set uptodate, fault in as private
  2. private->shared: call invalidate hook, fault in as shared
  3. shared->private: call prep hook, fault in as private

Here, 2/3 need to track where the current state is shared/private in
order to make appropriate architecture-specific changes (e.g. RMP table
updates). But we want to allow for non-destructive in-place conversion,
where a page is 'uptodate', but not in the desired shared/private state.
So 'uptodate' becomes a separate piece of state, which is still
reasonable for gmem to track in the current 4K-only implementation, and
provides for a reasonable approach to upstreaming in-place conversion,
which isn't far off for either SNP or TDX.

For hugepages, we'll have other things to consider, but those things are
probably still somewhat far off, and so we shouldn't block steps toward
in-place conversion based on uncertainty around hugepages. I think it's
gotten enough attention at least that we know it *can* work, e.g. even
if we take the inefficient/easy route of zero'ing the whole folio on
initial access, setting it uptodate, and never doing anything with 
uptodate again, it's still a usable implementation.

> 
> 

Above I outlined one of the use-cases for in-place conversion.

During the 2 PUCK sessions prior to this RFC, Sean also mentioned some
potential that other deadlocks might exist in current code due to
how the locking is currently handled, and that we should consider this
as a general cleanup against current kvm/next, but I leave that to Sean
to elaborate on.

Personally I think this series makes sense against kvm/next regardless:
tracking preparation in gmem is basically already broken: everyone ignores
it except SNP, so it was never performing that duty as-designed. So we
are now simplying uptodate flag to no longer include this extra
state-tracking, and leaving it for architecture-specific tracking. I
can't see that be anything but beneficial to future gmem changes.

> 
> > > 

No, sorry, I got my references mixed up. The only publically-posted
version of SNP hugepage support is the THP series that does not involve
in-place conversion, and that's what I was referencing. It's there where
per-4K bitmap was added to track preparation, and in that series
page-clearing/preparation are still coupled to some degree so per-4K
tracking of page-clearing was still possible and that's how it was
handled:

  https://github.com/AMDESE/linux/blob/snp-prepare-thp-rfc1/virt/kvm/guest_memfd.c#L992

but that can be considered an abandoned approach so I wouldn't spend
much time referencing that.

> 
> > prepared/cleared. There was 4K-granularity tracking added to handle this.

It could. E.g. via the kernel-internal gmem flag that I mentioned in my
earlier reply, or some alternative. 

In the context of this series, uptodate flag continues to instruct
kvm_gmem_get_pfn() that it doesn't not need to re-clear pages, because
a prior kvm_gmem_get_pfn() or kvm_gmem_populate() already initialized
the folio, and it is no longer tied to any notion of
preparedness-tracking.

What use uptodate will have in the context of hugepages: I'm not sure.
For non-in-place conversion, it's tempting to just let it continue to be
per-folio and require clearing the whole folio on initial access, but
it's not efficient. It may make sense to farm it out to
post-populate/prep hooks instead, as you're suggesting for TDX.

But then, for in-place conversion, you have to deal with pages initially
faulted in as shared. They might be split prior to initial access as a
private page, where we can't assume TDX will have scrubbed things. So in
that case it might still make sense to rely on it.

Definitely things that require some more thought. But having it inextricably
tied to preparedness just makes preparation tracking similarly more
complicated as it pulls it back into gmem when that does not seem to be
the direction any architectures other SNP have/want to go.

> 
> > My understanding based on prior discussion in guest_memfd calls was that

Possibly, but I touched elsewhere on where in-place conversion might
trip up this approach. At least decoupling them allows for the prep side
of things to be moved to architecture-specific tracking. We can deal
with uptodate separately I think.

-Mike

> 
>

---

## [24] Yan Zhao — 2025-12-02
*Subject: Re: [PATCH 1/3] KVM: guest_memfd: Remove preparation tracking*

On Mon, Dec 01, 2025 at 11:33:18AM -0800, Vishal Annapurve wrote:
> On Sun, Nov 30, 2025 at 6:53 PM Yan Zhao <yan.y.zhao@intel.com> wrote:
> >
Maybe clear_highpage() in kvm_gmem_get_folio()?

When in-place copy in kvm_gmem_populate() comes, kvm_gmem_get_folio() can be
invoked first for shared memory, so clear_highpage() there is before userspace
writes to shared memory. No clear_highpage() is required when kvm_gmem_populate()
invokes __kvm_gmem_get_pfn() to get the folio again.

> Subsequently, we need to figure out a way to avoid this clearing for
> SNP/TDX/CCA private faults.

---

## [25] Yan Zhao — 2025-12-02
*Subject: Re: [PATCH 1/3] KVM: guest_memfd: Remove preparation tracking*

On Mon, Dec 01, 2025 at 05:44:47PM -0600, Michael Roth wrote:
> On Tue, Nov 25, 2025 at 11:13:25AM +0800, Yan Zhao wrote:
> > On Fri, Nov 21, 2025 at 06:43:14AM -0600, Michael Roth wrote:
To me, "1. initial allocation: clear, set uptodate" is more appropriate to
be done in kvm_gmem_get_folio(), instead of in kvm_gmem_get_pfn().

With it, below looks reasonable to me.
> For hugepages, we'll have other things to consider, but those things are
> probably still somewhat far off, and so we shouldn't block steps toward

<...>
> > > Assuming this patch goes upstream in some form, we will now have the
> > > following major differences versus previous code:

---

## [26] Yan Zhao — 2025-12-03
*Subject: Re: [PATCH 3/3] KVM: guest_memfd: GUP source pages prior to
 populating guest memory*

On Mon, Dec 01, 2025 at 04:13:55PM -0600, Michael Roth wrote:
> On Mon, Nov 24, 2025 at 05:31:46PM +0800, Yan Zhao wrote:
> > On Fri, Nov 21, 2025 at 07:01:44AM -0600, Michael Roth wrote:

Hmm, the requirement of having each copy to dst_page account for src_offset
(which actually results in 2 copies) is quite confusing. I initially thought the
src_offset only applied to the first dst_page.

This will also cause kvm_gmem_populate() to allocate 1 more src_npages than
npages for dst pages.

> for any platform that enforces that the src is page-aligned, which
> doesn't seem like a huge technical burden, IMO, despite me initially
That's true. src_pages[0] just makes it more eye-catching.
What about just adding a comment for src_pages[0] instead of KVM_BUG_ON()?

> > > > >  	ret = kvm_tdp_mmu_map_private_pfn(arg->vcpu, gfn, pfn);
> > > > >  	kvm_tdx->page_add_src = NULL;
Not sure which flag you are referring to with "Vishal suggested kernel-internal
flags to kvm_gmem_create()".

However, my point is that when the backend folio is 1GB in size (leading to
max_order being PUD_ORDER), even if SNP only maps at 2MB to RMP, it may hit the
warning of "!IS_ALIGNED(gfn, 1 << max_order)".

For TDX, it's worse because it always passes npages as 1, so it will also hit
the warning of "(npages - i) < (1 << max_order)".

Given that this patch already considers huge pages for SNP, it feels half-baked
to leave the WARN_ON() for future handling.
    WARN_ON(!IS_ALIGNED(gfn, 1 << max_order) ||
            (npages - i) < (1 << max_order));

> flag would probably just default to set and punt to post-populate/prep
> hooks, because we absolutely *do not* want to have to re-introduce per-4K

For 1G (aka HugeTLB) page, this fix is also needed, which was missed in [1] and
I pointed out to Ackerley at [2].

[1] https://github.com/googleprodkernel/linux-cc/tree/gmem-1g-page-support-rfc-v2
[2] https://lore.kernel.org/all/aFPGPVbzo92t565h@yzhao56-desk.sh.intel.com/

> but it makes a lot more sense to make those restrictions and changes in
> the context of hugepage support, rather than this series which is trying
Not sure how fixing the warning in this series could impede hugepage enabling :)

But if you prefer, I don't mind keeping it locally for longer.

> Also, there's talk now of enabling hugepages even without in-place
> conversion for hugetlbfs, and that will likely be the same path we

---

## [27] Michael Roth — 2025-12-03
*Subject: Re: [PATCH 1/3] KVM: guest_memfd: Remove preparation tracking*

On Tue, Dec 02, 2025 at 05:17:20PM +0800, Yan Zhao wrote:
> On Mon, Dec 01, 2025 at 05:44:47PM -0600, Michael Roth wrote:
> > On Tue, Nov 25, 2025 at 11:13:25AM +0800, Yan Zhao wrote:

The downside is that preallocating originally involved just
preallocating, and zero'ing would happen lazily during fault time. (or
upfront via KVM_PRE_FAULT_MEMORY).

But in the context of the hugetlb RFC, it certainly looks cleaner to do
it there, since it could be done before any potential splitting activity,
so then all the tail pages can inherit that initial uptodate flag.

We'd probably want to weigh that these trade-offs based on how it will
affect hugepages, but that would be clearer in the context of a new
posting of hugepage support on top of these changes. So I think it's
better to address that change as a follow-up so we can consider it with
more context.

> 
> With it, below looks reasonable to me.

To me as well. But in the context of this series, against kvm/next, it
creates userspace-visible changes to pre-allocation behavior that we
can't justify in the context of this series alone, so as above I think
that's something to save for hugepage follow-up.

FWIW though, I ended up taking this approach for the hugetlb-based test
branch, to address the fact (after you reminded me) that I wasn't fully
zero'ing folio's in the kvm_gmem_populate() path:

  https://github.com/AMDESE/linux/commit/253fb30b076d81232deba0b02db070d5bc2b90b5

So maybe for your testing you could do similar. For newer hugepage
support I'll likely do similar, but I don't think any of this reasoning
or changes makes sense to people reviewing this series without already
being aware of hugepage plans/development, so that's why I'm trying to
keep this series more focused on in-place conversion enablement, because
hugepage plans might be massively reworked for next posting based on LPC
talks and changes in direction mentioned in recent guest_memfd calls and
we are basically just hand-waving about what it will look like at this
point while blocking other efforts.

-Mike

> 
> <...>

---

## [28] Michael Roth — 2025-12-03
*Subject: Re: [PATCH 3/3] KVM: guest_memfd: GUP source pages prior to
 populating guest memory*

On Wed, Dec 03, 2025 at 10:46:27AM +0800, Yan Zhao wrote:
> On Mon, Dec 01, 2025 at 04:13:55PM -0600, Michael Roth wrote:
> > On Mon, Nov 24, 2025 at 05:31:46PM +0800, Yan Zhao wrote:

What I'm wondering though is if I'd done a better job of documenting
this aspect, e.g. with the following comment added above
kvm_gmem_populate_cb:

  /*
   * ...
   * 'src_pages': array of GUP'd struct page pointers corresponding to
   *              the pages that store the data that is to be copied
   *              into the HPA corresponding to 'pfn'
   * 'src_offset': byte offset, relative to the first page in the array
   *               of pages pointed to by 'src_pages', to begin copying
   *               the data from.
   *
   * NOTE: if the caller of kvm_gmem_populate() enforces that 'src' is
   * page-aligned, then 'src_offset' will always be zero, and src_pages
   * will contain only 1 page to copy from, beginning at byte offset 0.
   * In this case, callers can assume src_offset is 0.
   */
  int (*kvm_gmem_populate_cb)(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
                              struct page **src_pages, loff_t src_offset,
                              int order, void *opaque);

could the confusion have been avoided, or is it still unwieldly?

I don't mind that users like SNP need to deal with the extra bits, but
I'm hoping for users like TDX it isn't too cludgy.

> 
> This will also cause kvm_gmem_populate() to allocate 1 more src_npages than

That's more of a decision on the part of userspace deciding to use
non-page-aligned 'src' pointer to begin with.

> 
> > for any platform that enforces that the src is page-aligned, which

That seems fair/relevant for this series.

> 
> > > > > >  	ret = kvm_tdp_mmu_map_private_pfn(arg->vcpu, gfn, pfn);

I think I've had to remove that warning every time I start working on
some new spin of THP/hugetlbfs-based SNP. I'm not objecting to that. But it's
obvious there, in those contexts, and I can explain exactly why it's being
removed.

It's not obvious in this series, where all we have are hand-wavy thoughts
about what hugepages will look like. For all we know we might decide that
kvm_gmem_populate() path should just pre-split hugepages to make all the
logic easier, or we decide to lock it in at 4K-only and just strip all the
hugepage stuff out. I don't really know, and this doesn't seem like the place
to try to hash all that out when nothing in this series will cause this
existing WARN_ON to be tripped.

> 
> For TDX, it's worse because it always passes npages as 1, so it will also hit

Yes, we'll likely need some kind of change here.

I think, if we're trying to find common ground to build hugepage support
on, you can assume this will be removed. But I just don't think we need
to squash that into this series in order to make progress on those ends.

> 
> > but it makes a lot more sense to make those restrictions and changes in

It's the whole burden of needing to anticipate hugepage design, while it
is in a state of potentially massive flux just before LPC, in order to
make tiny incremental progress toward enabling in-place conversion,
which is something I think we can get upstream much sooner. Look at your
changelog for the change above, for instance: it has no relevance in the
context of this series. What do I put in its place? Bug reports about
my experimental tree? It's just not the right place to try to justify
these changes.

And most of this weirdness stems from the fact that we prematurely added
partial hugepage enablement to begin with. Let's not repeat these mistakes,
and address changes in the proper context where we know they make sense.

I considered stripping out the existing hugepage support as a pre-patch
to avoid leaving these uncertainties in place while we are reworking
things, but it felt like needless churn. But that's where I'm coming
from with this series: let's get in-place conversion landed, get the API
fleshed out, get it working, and then re-assess hugepages with all these
common/intersecting bits out of the way. If we can remove some obstacles
for hugepages as part of that, great, but that is not the main intent
here.

-Mike

> 
> > Also, there's talk now of enabling hugepages even without in-place

---

## [29] FirstName LastName — 2025-12-03
*Subject: Re: [PATCH 3/3] KVM: guest_memfd: GUP source pages prior to
 populating guest memory*

> >
> > > but it makes a lot more sense to make those restrictions and changes in

I think simplifying this implementation to handle populate at 4K pages is worth
considering at this stage and we could optimize for huge page granularity
population in future based on the need.

e.g. 4K page based population logic will keep things simple and can be
further simplified if we can add PAGE_ALIGNED(params.uaddr) restriction.
Extending Sean's suggestion earlier, compile tested only.

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index f59c65abe3cf..224e79ab8f86 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -2267,66 +2267,56 @@ struct sev_gmem_populate_args {
 	int fw_error;
 };
 
-static int sev_gmem_post_populate(struct kvm *kvm, gfn_t gfn_start, kvm_pfn_t pfn,
-				  void __user *src, int order, void *opaque)
+static int sev_gmem_post_populate(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
+				  struct page *src_page, void *opaque)
 {
 	struct sev_gmem_populate_args *sev_populate_args = opaque;
 	struct kvm_sev_info *sev = to_kvm_sev_info(kvm);
-	int n_private = 0, ret, i;
-	int npages = (1 << order);
-	gfn_t gfn;
+	int ret;
 
-	if (WARN_ON_ONCE(sev_populate_args->type != KVM_SEV_SNP_PAGE_TYPE_ZERO && !src))
+	if (WARN_ON_ONCE(sev_populate_args->type != KVM_SEV_SNP_PAGE_TYPE_ZERO && !src_page))
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
+	struct sev_data_snp_launch_update fw_args = {0};
+	bool assigned = false;
+	int level;
 
-		if (src) {
-			void *vaddr = kmap_local_pfn(pfn + i);
+	ret = snp_lookup_rmpentry((u64)pfn, &assigned, &level);
+	if (ret || assigned) {
+		pr_debug("%s: Failed to ensure GFN 0x%llx RMP entry is initial shared state, ret: %d assigned: %d\n",
+			 __func__, gfn, ret, assigned);
+		ret = ret ? -EINVAL : -EEXIST;
+		goto err;
+	}
 
-			if (copy_from_user(vaddr, src + i * PAGE_SIZE, PAGE_SIZE)) {
-				ret = -EFAULT;
-				goto err;
-			}
-			kunmap_local(vaddr);
-		}
+	if (src_page) {
+		void *vaddr = kmap_local_pfn(pfn);
 
-		ret = rmp_make_private(pfn + i, gfn << PAGE_SHIFT, PG_LEVEL_4K,
-				       sev_get_asid(kvm), true);
-		if (ret)
-			goto err;
+		memcpy(vaddr, page_address(src_page), PAGE_SIZE);
+		kunmap_local(vaddr);
+	}
 
-		n_private++;
+	ret = rmp_make_private(pfn, gfn << PAGE_SHIFT, PG_LEVEL_4K,
+			       sev_get_asid(kvm), true);
+	if (ret)
+		goto err;
 
-		fw_args.gctx_paddr = __psp_pa(sev->snp_context);
-		fw_args.address = __sme_set(pfn_to_hpa(pfn + i));
-		fw_args.page_size = PG_LEVEL_TO_RMP(PG_LEVEL_4K);
-		fw_args.page_type = sev_populate_args->type;
+	fw_args.gctx_paddr = __psp_pa(sev->snp_context);
+	fw_args.address = __sme_set(pfn_to_hpa(pfn));
+	fw_args.page_size = PG_LEVEL_TO_RMP(PG_LEVEL_4K);
+	fw_args.page_type = sev_populate_args->type;
 
-		ret = __sev_issue_cmd(sev_populate_args->sev_fd, SEV_CMD_SNP_LAUNCH_UPDATE,
-				      &fw_args, &sev_populate_args->fw_error);
-		if (ret)
-			goto fw_err;
-	}
+	ret = __sev_issue_cmd(sev_populate_args->sev_fd, SEV_CMD_SNP_LAUNCH_UPDATE,
+			      &fw_args, &sev_populate_args->fw_error);
+	if (ret)
+		goto fw_err;
 
 	return 0;
 
 fw_err:
 	/*
 	 * If the firmware command failed handle the reclaim and cleanup of that
-	 * PFN specially vs. prior pages which can be cleaned up below without
-	 * needing to reclaim in advance.
+	 * PFN specially.
 	 *
 	 * Additionally, when invalid CPUID function entries are detected,
 	 * firmware writes the expected values into the page and leaves it
@@ -2336,25 +2326,18 @@ static int sev_gmem_post_populate(struct kvm *kvm, gfn_t gfn_start, kvm_pfn_t pf
 	 * information to provide information on which CPUID leaves/fields
 	 * failed CPUID validation.
 	 */
-	if (!snp_page_reclaim(kvm, pfn + i) &&
+	if (!snp_page_reclaim(kvm, pfn) &&
 	    sev_populate_args->type == KVM_SEV_SNP_PAGE_TYPE_CPUID &&
 	    sev_populate_args->fw_error == SEV_RET_INVALID_PARAM) {
-		void *vaddr = kmap_local_pfn(pfn + i);
-
-		if (copy_to_user(src + i * PAGE_SIZE, vaddr, PAGE_SIZE))
-			pr_debug("Failed to write CPUID page back to userspace\n");
+		void *vaddr = kmap_local_pfn(pfn);
 
+		memcpy(page_address(src_page), vaddr, PAGE_SIZE);
 		kunmap_local(vaddr);
 	}
 
-	/* pfn + i is hypervisor-owned now, so skip below cleanup for it. */
-	n_private--;
-
 err:
-	pr_debug("%s: exiting with error ret %d (fw_error %d), restoring %d gmem PFNs to shared.\n",
-		 __func__, ret, sev_populate_args->fw_error, n_private);
-	for (i = 0; i < n_private; i++)
-		kvm_rmp_make_shared(kvm, pfn + i, PG_LEVEL_4K);
+	pr_debug("%s: exiting with error ret %d (fw_error %d)\n",
+		 __func__, ret, sev_populate_args->fw_error);
 
 	return ret;
 }
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 2d7a4d52ccfb..acdcb802d9f2 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -3118,34 +3118,21 @@ struct tdx_gmem_post_populate_arg {
 };
 
 static int tdx_gmem_post_populate(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
-				  void __user *src, int order, void *_arg)
+				  struct page *src_page, void *_arg)
 {
 	struct tdx_gmem_post_populate_arg *arg = _arg;
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
 	u64 err, entry, level_state;
 	gpa_t gpa = gfn_to_gpa(gfn);
-	struct page *src_page;
-	int ret, i;
+	int ret;
 
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
 
@@ -3156,11 +3143,9 @@ static int tdx_gmem_post_populate(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
 	 * mmu_notifier events can't reach S-EPT entries, and KVM's internal
 	 * zapping flows are mutually exclusive with S-EPT mappings.
 	 */
-	for (i = 0; i < PAGE_SIZE; i += TDX_EXTENDMR_CHUNKSIZE) {
-		err = tdh_mr_extend(&kvm_tdx->td, gpa + i, &entry, &level_state);
-		if (TDX_BUG_ON_2(err, TDH_MR_EXTEND, entry, level_state, kvm))
-			return -EIO;
-	}
+	err = tdh_mr_extend(&kvm_tdx->td, gpa, &entry, &level_state);
+	if (TDX_BUG_ON_2(err, TDH_MR_EXTEND, entry, level_state, kvm))
+		return -EIO;
 
 	return 0;
 }
@@ -3196,38 +3181,26 @@ static int tdx_vcpu_init_mem_region(struct kvm_vcpu *vcpu, struct kvm_tdx_cmd *c
 		return -EINVAL;
 
 	ret = 0;
-	while (region.nr_pages) {
-		if (signal_pending(current)) {
-			ret = -EINTR;
-			break;
-		}
-
-		arg = (struct tdx_gmem_post_populate_arg) {
-			.vcpu = vcpu,
-			.flags = cmd->flags,
-		};
-		gmem_ret = kvm_gmem_populate(kvm, gpa_to_gfn(region.gpa),
-					     u64_to_user_ptr(region.source_addr),
-					     1, tdx_gmem_post_populate, &arg);
-		if (gmem_ret < 0) {
-			ret = gmem_ret;
-			break;
-		}
+	arg = (struct tdx_gmem_post_populate_arg) {
+		.vcpu = vcpu,
+		.flags = cmd->flags,
+	};
+	gmem_ret = kvm_gmem_populate(kvm, gpa_to_gfn(region.gpa),
+				     u64_to_user_ptr(region.source_addr),
+				     region.nr_pages, tdx_gmem_post_populate, &arg);
+	if (gmem_ret < 0)
+		ret = gmem_ret;
 
-		if (gmem_ret != 1) {
-			ret = -EIO;
-			break;
-		}
+	if (gmem_ret != region.nr_pages)
+		ret = -EIO;
 
-		region.source_addr += PAGE_SIZE;
-		region.gpa += PAGE_SIZE;
-		region.nr_pages--;
+	if (gmem_ret >= 0) {
+		region.source_addr += gmem_ret * PAGE_SIZE;
+		region.gpa += gmem_ret * PAGE_SIZE;
 
-		cond_resched();
+		if (copy_to_user(u64_to_user_ptr(cmd->data), &region, sizeof(region)))
+			ret = -EFAULT;
 	}
-
-	if (copy_to_user(u64_to_user_ptr(cmd->data), &region, sizeof(region)))
-		ret = -EFAULT;
 	return ret;
 }
 
diff --git a/include/linux/kvm_host.h b/include/linux/kvm_host.h
index d93f75b05ae2..263e75f90e91 100644
--- a/include/linux/kvm_host.h
+++ b/include/linux/kvm_host.h
@@ -2581,7 +2581,7 @@ int kvm_arch_gmem_prepare(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn, int max_ord
  * Returns the number of pages that were populated.
  */
 typedef int (*kvm_gmem_populate_cb)(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
-				    void __user *src, int order, void *opaque);
+				    struct page *src_page, void *opaque);
 
 long kvm_gmem_populate(struct kvm *kvm, gfn_t gfn, void __user *src, long npages,
 		       kvm_gmem_populate_cb post_populate, void *opaque);
diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index 2e62bf882aa8..550dc818748b 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -85,7 +85,6 @@ static int __kvm_gmem_prepare_folio(struct kvm *kvm, struct kvm_memory_slot *slo
 static int kvm_gmem_prepare_folio(struct kvm *kvm, struct kvm_memory_slot *slot,
 				  gfn_t gfn, struct folio *folio)
 {
-	unsigned long nr_pages, i;
 	pgoff_t index;
 
 	/*
@@ -794,7 +793,7 @@ int kvm_gmem_get_pfn(struct kvm *kvm, struct kvm_memory_slot *slot,
 		return PTR_ERR(folio);
 
 	if (!folio_test_uptodate(folio)) {
-		clear_huge_page(&folio->page, 0, folio_nr_pages(folio));
+		clear_highpage(folio_page(folio, 0));
 		folio_mark_uptodate(folio);
 	}
 
@@ -812,13 +811,54 @@ int kvm_gmem_get_pfn(struct kvm *kvm, struct kvm_memory_slot *slot,
 EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_gmem_get_pfn);
 
 #ifdef CONFIG_HAVE_KVM_ARCH_GMEM_POPULATE
+static long __kvm_gmem_populate(struct kvm *kvm, struct kvm_memory_slot *slot,
+				struct file *file, gfn_t gfn, struct page *src_page,
+				kvm_gmem_populate_cb post_populate, void *opaque)
+{
+	pgoff_t index = kvm_gmem_get_index(slot, gfn);
+	struct gmem_inode *gi;
+	struct folio *folio;
+	int ret, max_order;
+	kvm_pfn_t pfn;
+
+	gi = GMEM_I(file_inode(file));
+
+	filemap_invalidate_lock(file->f_mapping);
+
+	folio = __kvm_gmem_get_pfn(file, slot, index, &pfn, &max_order);
+	if (IS_ERR(folio)) {
+		ret = PTR_ERR(folio);
+		goto out_unlock;
+	}
+
+	folio_unlock(folio);
+
+	if (!kvm_range_has_memory_attributes(kvm, gfn, gfn + 1,
+				KVM_MEMORY_ATTRIBUTE_PRIVATE,
+				KVM_MEMORY_ATTRIBUTE_PRIVATE)) {
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
+	struct page *src_aligned_page = NULL;
 	struct kvm_memory_slot *slot;
+	struct page *src_page = NULL;
 	void __user *p;
-
-	int ret = 0, max_order;
+	int ret = 0;
 	long i;
 
 	lockdep_assert_held(&kvm->slots_lock);
@@ -834,52 +874,50 @@ long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long
 	if (!file)
 		return -EFAULT;
 
-	filemap_invalidate_lock(file->f_mapping);
+	if (src && !PAGE_ALIGNED(src)) {
+		src_page = alloc_page(GFP_KERNEL_ACCOUNT);
+		if (!src_page)
+			return -ENOMEM;
+	}
 
 	npages = min_t(ulong, slot->npages - (start_gfn - slot->base_gfn), npages);
-	for (i = 0; i < npages; i += (1 << max_order)) {
-		struct folio *folio;
-		gfn_t gfn = start_gfn + i;
-		pgoff_t index = kvm_gmem_get_index(slot, gfn);
-		kvm_pfn_t pfn;
-
+	for (i = 0; i < npages; i++) {
 		if (signal_pending(current)) {
 			ret = -EINTR;
 			break;
 		}
 
-		folio = __kvm_gmem_get_pfn(file, slot, index, &pfn, &max_order);
-		if (IS_ERR(folio)) {
-			ret = PTR_ERR(folio);
-			break;
-		}
-
-		folio_unlock(folio);
-		WARN_ON(!IS_ALIGNED(gfn, 1 << max_order) ||
-			(npages - i) < (1 << max_order));
+		p = src ? src + i * PAGE_SIZE : NULL;
 
-		ret = -EINVAL;
-		while (!kvm_range_has_memory_attributes(kvm, gfn, gfn + (1 << max_order),
-							KVM_MEMORY_ATTRIBUTE_PRIVATE,
-							KVM_MEMORY_ATTRIBUTE_PRIVATE)) {
-			if (!max_order)
-				goto put_folio_and_exit;
-			max_order--;
+		if (p) {
+			if (src_page) {
+				if (copy_from_user(page_address(src_page), p, PAGE_SIZE)) {
+					ret = -EFAULT;
+					break;
+				}
+				src_aligned_page = src_page;
+			} else {
+				ret = get_user_pages((unsigned long)p, 1, 0, &src_aligned_page);
+				if (ret < 0)
+					break;
+				if (ret != 1) {
+					ret = -ENOMEM;
+					break;
+				}
+			}
 		}
 
-		p = src ? src + i * PAGE_SIZE : NULL;
-		ret = post_populate(kvm, gfn, pfn, p, max_order, opaque);
-		if (!ret)
-			folio_mark_uptodate(folio);
+		ret = __kvm_gmem_populate(kvm, slot, file, start_gfn + i, src_aligned_page,
+					  post_populate, opaque);
+		if (p && !src_page)
+			put_page(src_aligned_page);
 
-put_folio_and_exit:
-		folio_put(folio);
 		if (ret)
 			break;
 	}
 
-	filemap_invalidate_unlock(file->f_mapping);
-
+	if (src_page)
+		__free_page(src_page);
 	return ret && !i ? ret : i;
 }
 EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_gmem_populate);

---

## [30] Ira Weiny — 2025-12-03
*Subject: Re: [PATCH 3/3] KVM: guest_memfd: GUP source pages prior to
 populating guest memory*

Michael Roth wrote:
> On Wed, Dec 03, 2025 at 10:46:27AM +0800, Yan Zhao wrote:
> > On Mon, Dec 01, 2025 at 04:13:55PM -0600, Michael Roth wrote:

[snip]

> > > > > > > ---
> > > > > > >  arch/x86/kvm/svm/sev.c   | 40 ++++++++++++++++++++++++++------------

FWIW I don't think the TDX code was a problem.  I was trying to review the
SNP code for correctness and it was confusing enough that I was concerned
the investment is not worth the cost.

I'll re-iterate that the in-place conversion _use_ _case_ requires user
space to keep the 'source' (ie the page) aligned because it is all getting
converted anyway.  So I'm not seeing a good use case for supporting this.
But Vishal seemed to think there was so...

Given this potential use case; the above comment is more clear.

FWIW, I think this is going to get even more complex if the src/dest page
sizes are miss-matched.  But that algorithm can be reviewed at that time,
not now.

> > 
> > This will also cause kvm_gmem_populate() to allocate 1 more src_npages than

IIRC this is where I think there might be an issue with the code.  The
code used PAGE_SIZE for the memcpy's.  Is it clear that user space must
have a buffer >= PAGE_SIZE when src_offset != 0?

I did not see that check; and/or I was not clear how that works.

[snip]

> > > > > 
> > > > > This was necessarily chosen in prep for hugepages, but more about my

Yea don't do that.

> I don't really know, and this doesn't seem like the place
> to try to hash all that out when nothing in this series will cause this

Agreed.


[snip]

> 
> > 

I'd like to second what Mike is saying here.  The entire discussion about
hugepage support is premature for this series.

Ira

[snip]

---

## [31] Michael Roth — 2025-12-03
*Subject: Re: [PATCH 3/3] KVM: guest_memfd: GUP source pages prior to
 populating guest memory*

On Wed, Dec 03, 2025 at 03:01:24PM -0600, Ira Weiny wrote:
> Michael Roth wrote:
> > On Wed, Dec 03, 2025 at 10:46:27AM +0800, Yan Zhao wrote:

I think it would only be worth it if we have some reasonable indication
that someone is using SNP_LAUNCH_UPDATE with un-aligned 'uaddr'/'src'
parameter, or anticipate that a future architecture would rely on such
a thing.

I don't *think* there is, but if that guess it wrong then someone out
there will be very grumpy. I'm not sure what the threshold is for
greenlighting a userspace API change like that though, so I'd prefer
to weasel out of that responsibility by assuming we need to support
non-page-aligned src until the maintainers tell me it's
okay/warranted. :)

> 
> I'll re-iterate that the in-place conversion _use_ _case_ requires user

I think Sean wanted to leave open the possibility of using a src that
isn't necessarily the same page as the destination. In this series, it
is actually not possible to use 'src' at all if the src/dst are the
same, since that means that src would have been marked with
KVM_MEMORY_ATTRIBUTE_PRIVATE in advance of calling kvm_gmem_populate(),
in which case GUP would trigger the SIGBUS handling in
kvm_gmem_fault_user_mapping(). But I consider that a feature, since
it's more efficient to let userspace initialize it in advance, prior
to marking it as PRIVATE and calling whatever ioctl triggers
kvm_gmem_populate(), and it gets naturally enforced with that existing
checks in kvm_gmem_populate(). So, if src==dst, userspace would need
to pass src==0

> 
> Given this potential use case; the above comment is more clear.

Yes, for SNP_LAUNCH_UPDATE at least, it is documented that the 'len' must
be non-0 and aligned to 4K increments, and that's enforced in
snp_launch_update() handler. I don't quite remember why we didn't just
make it a 'npages' argument but I remember there being some reasoning
for that.

> 
> [snip]

Yah, maybe a clean slate, removing the existing hugepage bits as Vishal
is suggesting, is the best way to free ourselves to address these things
incrementally without the historical baggage.

-Mike

> 
> Ira

---

## [32] Michael Roth — 2025-12-03
*Subject: Re: [PATCH 3/3] KVM: guest_memfd: GUP source pages prior to
 populating guest memory*

On Wed, Dec 03, 2025 at 08:59:10PM +0000, FirstName LastName wrote:
> > >
> > > > but it makes a lot more sense to make those restrictions and changes in

That's probably for the best, after all. Though I think a separate
pre-patch to remove the hugepage stuff would be cleaner, as it
obfuscates the GUP changes quite a bit, which are already pretty subtle
as-is.

I'll plan to do this for the next spin, if there are no objections
raised in the meantime.

> 
> e.g. 4K page based population logic will keep things simple and can be

I'm still hesitant to pull the trigger on retroactively enforcing
page-aligned uaddr for SNP, but if the maintainers are good with it then
no objection from me.

> Extending Sean's suggestion earlier, compile tested only.

Thanks!

-Mike

> 
> diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c

---

## [33] Michael Roth — 2025-12-03
*Subject: Re: [PATCH 3/3] KVM: guest_memfd: GUP source pages prior to
 populating guest memory*

On Sun, Nov 30, 2025 at 05:44:31PM -0800, Vishal Annapurve wrote:
> On Fri, Nov 21, 2025 at 5:02 AM Michael Roth <michael.roth@amd.com> wrote:
> >

Missed this reply earlier.

It could be, but would probably be worthwhile to do some performance
analysis before considering that so we can simplify in the meantime.

> The code becomes somewhat complex when trying to get this scenario
> working and IIUC it depends on userspace-passed initial payload

We'd need to gate the order that we pass to post-populate callback
according to each individual call. For 2MB pages we'd end up with
4K behavior. For 1GB pages, there's some potential of using 2MB
order for each region if gpa/dst/len are aligned, but without the
buddy-style 1G->2M-4K splitting stuff, we'd likely need to split
to 4K at some point and then the 2MB RMP entry would get PSMASH'd
to 4K anyway. But maybe the 1GB could remain intact for long enough
to get through a decent portion of OVMF boot before we end up
creating a mixed range... not sure.

But yes, this also seems like functionality that's premature to
prep for, so just locking it in at 4K is probably best for now.

-Mike

> 
> What Sean suggested earlier[1] seems relatively simpler to maintain.

---

## [34] Yan Zhao — 2025-12-05
*Subject: Re: [PATCH 3/3] KVM: guest_memfd: GUP source pages prior to
 populating guest memory*

On Wed, Dec 03, 2025 at 10:26:48PM +0800, Michael Roth wrote:
> Look at your
> changelog for the change above, for instance: it has no relevance in the

The following diff is reasonable to this series(if npages is up to 2MB), 

--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -878,11 +878,10 @@ long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long
                }

                folio_unlock(folio);
-               WARN_ON(!IS_ALIGNED(gfn, 1 << max_order) ||
-                       (npages - i) < (1 << max_order));

                ret = -EINVAL;
-               while (!kvm_range_has_memory_attributes(kvm, gfn, gfn + (1 << max_order),
+               while (!IS_ALIGNED(gfn, 1 << max_order) || (npages - i) < (1 << max_order) ||
+                      !kvm_range_has_memory_attributes(kvm, gfn, gfn + (1 << max_order),
                                                        KVM_MEMORY_ATTRIBUTE_PRIVATE,
                                                        KVM_MEMORY_ATTRIBUTE_PRIVATE)) {
                        if (!max_order)


because:

1. kmalloc_array() + GUP 2MB src pages + returning -ENOMEM in "Hunk 1" is a
   waste if max_order is always 0.
   
2. If we allow max_order > 0, then we must remove the WARN_ON().

3. When start_gfn is not 2MB aligned, just allocating 4KB src page each round is
   enough (as in Sean's sketch patch).


Hunk 1: -------------------------------------------------------------------
      src_npages = IS_ALIGNED((unsigned long)src, PAGE_SIZE) ? npages : npages + 1;

      src_pages = kmalloc_array(src_npages, sizeof(struct page *), GFP_KERNEL);
      if (!src_pages)
          return -ENOMEM;

      ret = get_user_pages_fast((unsigned long)src, src_npages, 0, src_pages);
      if (ret < 0)
          return ret;

      if (ret != src_npages)
          return -ENOMEM;

Hunk 2: -------------------------------------------------------------------
      for (i = 0; i < npages; i += (1 << max_order)) {
         ...

         folio = __kvm_gmem_get_pfn(file, slot, index, &pfn, &max_order);

	 WARN_ON(!IS_ALIGNED(gfn, 1 << max_order) ||
                 (npages - i) < (1 << max_order));

         ret = post_populate(kvm, gfn, pfn, src ? &src_pages[i] : NULL,
                             src_offset, max_order, opaque);
         ...
      }

---

## [35] Yan Zhao — 2025-12-05
*Subject: Re: [PATCH 1/3] KVM: guest_memfd: Remove preparation tracking*

On Wed, Dec 03, 2025 at 07:47:17AM -0600, Michael Roth wrote:
> On Tue, Dec 02, 2025 at 05:17:20PM +0800, Yan Zhao wrote:
> > On Mon, Dec 01, 2025 at 05:44:47PM -0600, Michael Roth wrote:
Got it. Thanks for the explanation!

---

## [36] Vlastimil Babka — 2025-12-08
*Subject: Re: [PATCH 3/3] KVM: guest_memfd: GUP source pages prior to
 populating guest memory*

On 12/4/25 00:12, Michael Roth wrote:
> On Wed, Dec 03, 2025 at 08:59:10PM +0000, FirstName LastName wrote:
>> 

IMHO it would be for the best. If there are no known users that would break,
it's worth trying. The "do not break userspace" rule isn't about eliminating
any theoretical possibility, but indeed about known breakages (and reacting
appropriately to reports about previously unknown breakages). Perhaps any
such users would be also willing to adjust and not demand a revert.

---

## [37] Sean Christopherson — 2025-12-09
*Subject: Re: [PATCH 3/3] KVM: guest_memfd: GUP source pages prior to
 populating guest memory*

On Mon, Dec 08, 2025, Vlastimil Babka wrote:
> On 12/4/25 00:12, Michael Roth wrote:
> > On Wed, Dec 03, 2025 at 08:59:10PM +0000, FirstName LastName wrote:

+1.  This code is already crazy complex, we should jump at any simplification
possible.  Especially since we expect in-place conversion to dominate usage in
the future, and in-place conversion is incompatible with an unaligned source.

---
