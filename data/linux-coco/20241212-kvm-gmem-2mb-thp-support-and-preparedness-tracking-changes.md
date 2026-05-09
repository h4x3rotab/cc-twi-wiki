---
title: 'KVM: gmem: 2MB THP support and preparedness tracking changes'
date: 2024-12-12
last_reply: 2025-04-23
message_count: 24
participants: ['Michael Roth', 'David Hildenbrand', 'Shah, Amit', 'Tom Lendacky', 'Vishal Annapurve', 'Yan Zhao', 'Ackerley Tng']
---

## [1] Michael Roth — 2024-12-12

This patchset is also available at:

  https://github.com/amdese/linux/commits/snp-prepare-thp-rfc1

and is based on top of Paolo's kvm-coco-queue-2024-11 tag which includes
a snapshot of his patches[1] to provide tracking of whether or not
sub-pages of a huge folio need to have kvm_arch_gmem_prepare() hooks issued
before guest access:

  d55475f23cea KVM: gmem: track preparedness a page at a time
  64b46ca6cd6d KVM: gmem: limit hole-punching to ranges within the file
  17df70a5ea65 KVM: gmem: add a complete set of functions to query page preparedness
  e3449f6841ef KVM: gmem: allocate private data for the gmem inode 

  [1] https://lore.kernel.org/lkml/20241108155056.332412-1-pbonzini@redhat.com/

This series addresses some of the pending review comments for those patches
(feel free to squash/rework as-needed), and implements a first real user in
the form of a reworked version of Sean's original 2MB THP support for gmem.

It is still a bit up in the air as to whether or not gmem should support
THP at all rather than moving straight to 2MB/1GB hugepages in the form of
something like HugeTLB folios[2] or the lower-level PFN range allocator
presented by Yu Zhao during the guest_memfd call last week. The main
arguments against THP, as I understand it, is that THPs will become
split over time due to hole-punching and rarely have an opportunity to get 
rebuilt due to lack of memory migration support for current CoCo hypervisor
implementations like SNP (and adding the migration support to resolve that
not necessarily resulting in a net-gain performance-wise). The current
plan for SNP, as discussed during the first guest_memfd call, is to
implement something similar to 2MB HugeTLB, and disallow hole-punching
at sub-2MB granularity.

However, there have also been some discussions during recent PUCK calls
where the KVM maintainers have some still expressed some interest in pulling
in gmem THP support in a more official capacity. The thinking there is that
hole-punching is a userspace policy, and that it could in theory avoid
holepunching for sub-2MB GFN ranges to avoid degradation over time.
And if there's a desire to enforce this from the kernel-side by blocking
sub-2MB hole-punching from the host-side, this would provide similar
semantics/behavior to the 2MB HugeTLB-like approach above.

So maybe there is still some room for discussion about these approaches.

Outside that, there are a number of other development areas where it would
be useful to at least have some experimental 2MB support in place so that
those efforts can be pursued in parallel, such as the preparedness
tracking touched on here, and exploring how that will intersect with other
development areas like using gmem for both shared and private memory, mmap
support, guest_memfd library, etc., so my hopes are that this approach
could be useful for that purpose at least, even if only as an out-of-tree
stop-gap.

Thoughts/comments welcome!

[2] https://lore.kernel.org/all/cover.1728684491.git.ackerleytng@google.com/


Testing
-------

Currently, this series does not default to enabling 2M support, but it
can instead be switched on/off dynamically via a module parameter:

  echo 1 >/sys/module/kvm/parameters/gmem_2m_enabled
  echo 0 >/sys/module/kvm/parameters/gmem_2m_enabled

This can be useful for simulating things like host pressure where we start
getting a mix of 4K/2MB allocations. I've used this to help test that the
preparedness-tracking still handles things properly in these situations.

But if we do decide to pull in THP support upstream it would make more
sense to drop the parameter completely.


----------------------------------------------------------------
Michael Roth (4):
      KVM: gmem: Don't rely on __kvm_gmem_get_pfn() for preparedness
      KVM: gmem: Don't clear pages that have already been prepared
      KVM: gmem: Hold filemap invalidate lock while allocating/preparing folios
      KVM: SEV: Improve handling of large ranges in gmem prepare callback

Sean Christopherson (1):
      KVM: Add hugepage support for dedicated guest memory

 arch/x86/kvm/svm/sev.c   | 163 ++++++++++++++++++++++++++------------------
 include/linux/kvm_host.h |   2 +
 virt/kvm/guest_memfd.c   | 173 ++++++++++++++++++++++++++++++++++-------------
 virt/kvm/kvm_main.c      |   4 ++
 4 files changed, 228 insertions(+), 114 deletions(-)

---

## [2] Michael Roth — 2024-12-12
*Subject: [PATCH 1/5] KVM: gmem: Don't rely on __kvm_gmem_get_pfn() for preparedness*

Currently __kvm_gmem_get_pfn() sets 'is_prepared' so callers can skip
calling kvm_gmem_prepare_folio(). However, subsequent patches will
introduce some locking constraints around setting/checking preparedness
that will require filemap_invalidate_lock*() to be held while checking
for preparedness. This locking could theoretically be done inside
__kvm_gmem_get_pfn(), or by requiring that filemap_invalidate_lock*() is
held while calling __kvm_gmem_get_pfn(), but that places unnecessary
constraints around when __kvm_gmem_get_pfn() can be called, whereas
callers could just as easily call kvm_gmem_is_prepared() directly.

So, in preparation for these locking changes, drop the 'is_prepared'
argument, and leave it up to callers to handle checking preparedness
where needed and with the proper locking constraints.

Signed-off-by: Michael Roth <michael.roth@amd.com>
---
 virt/kvm/guest_memfd.c | 13 +++++--------
 1 file changed, 5 insertions(+), 8 deletions(-)

diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index b69af3580bef..aa0038ddf4a4 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -773,7 +773,7 @@ void kvm_gmem_unbind(struct kvm_memory_slot *slot)
 static struct folio *__kvm_gmem_get_pfn(struct file *file,
 					struct kvm_memory_slot *slot,
 					pgoff_t index, kvm_pfn_t *pfn,
-					bool *is_prepared, int *max_order)
+					int *max_order)
 {
 	struct kvm_gmem *gmem = file->private_data;
 	struct folio *folio;
@@ -803,7 +803,6 @@ static struct folio *__kvm_gmem_get_pfn(struct file *file,
 	if (max_order)
 		*max_order = 0;
 
-	*is_prepared = kvm_gmem_is_prepared(file, index, folio);
 	return folio;
 }
 
@@ -814,19 +813,18 @@ int kvm_gmem_get_pfn(struct kvm *kvm, struct kvm_memory_slot *slot,
 	pgoff_t index = kvm_gmem_get_index(slot, gfn);
 	struct file *file = kvm_gmem_get_file(slot);
 	struct folio *folio;
-	bool is_prepared = false;
 	int r = 0;
 
 	if (!file)
 		return -EFAULT;
 
-	folio = __kvm_gmem_get_pfn(file, slot, index, pfn, &is_prepared, max_order);
+	folio = __kvm_gmem_get_pfn(file, slot, index, pfn, max_order);
 	if (IS_ERR(folio)) {
 		r = PTR_ERR(folio);
 		goto out;
 	}
 
-	if (!is_prepared)
+	if (kvm_gmem_is_prepared(file, index, folio))
 		r = kvm_gmem_prepare_folio(kvm, file, slot, gfn, folio);
 
 	folio_unlock(folio);
@@ -872,7 +870,6 @@ long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long
 		struct folio *folio;
 		gfn_t gfn = start_gfn + i;
 		pgoff_t index = kvm_gmem_get_index(slot, gfn);
-		bool is_prepared = false;
 		kvm_pfn_t pfn;
 
 		if (signal_pending(current)) {
@@ -880,13 +877,13 @@ long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long
 			break;
 		}
 
-		folio = __kvm_gmem_get_pfn(file, slot, index, &pfn, &is_prepared, &max_order);
+		folio = __kvm_gmem_get_pfn(file, slot, index, &pfn, &max_order);
 		if (IS_ERR(folio)) {
 			ret = PTR_ERR(folio);
 			break;
 		}
 
-		if (is_prepared) {
+		if (kvm_gmem_is_prepared(file, index, folio)) {
 			folio_unlock(folio);
 			folio_put(folio);
 			ret = -EEXIST;

---

## [3] Michael Roth — 2024-12-12
*Subject: [PATCH 2/5] KVM: gmem: Don't clear pages that have already been prepared*

Currently kvm_gmem_prepare_folio() and kvm_gmem_mark_prepared() try to
use the folio order to determine the range of PFNs that needs to be
cleared before usage and subsequently marked prepared. There may however
be cases, at least once hugepage support is added, where some PFNs may
have been previously prepared when kvm_gmem_prepare_folio() was called
with a smaller max_order than the current one, and this can lead to the
current code attempting to clear pages that have already been prepared.

It also makes sense to provide more control to the caller over what
order to use, since interfaces like kvm_gmem_populate() might
specifically want to prepare sub-ranges while leaving other PFNs within
the folio in an unprepared state. It could be argued that
opportunistically preparing additional pages isn't necessarily a bad
thing, but this will complicate things down the road when future uses
cases like using gmem for both shared/private guest memory come along.

Address these issues by allowing the callers of
kvm_gmem_prepare_folio()/kvm_gmem_mark_prepared() to explicitly specify
the order of the range being prepared, and in cases where these ranges
overlap with previously-prepared pages, do not attempt to re-clear the
pages.

Signed-off-by: Michael Roth <michael.roth@amd.com>
---
 virt/kvm/guest_memfd.c | 106 ++++++++++++++++++++++++++---------------
 1 file changed, 68 insertions(+), 38 deletions(-)

diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index aa0038ddf4a4..6907ae9fe149 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -96,15 +96,15 @@ static inline kvm_pfn_t folio_file_pfn(struct folio *folio, pgoff_t index)
 }
 
 static int __kvm_gmem_prepare_folio(struct kvm *kvm, struct kvm_memory_slot *slot,
-				    pgoff_t index, struct folio *folio)
+				    pgoff_t index, struct folio *folio, int max_order)
 {
 #ifdef CONFIG_HAVE_KVM_ARCH_GMEM_PREPARE
 	kvm_pfn_t pfn = folio_file_pfn(folio, index);
 	gfn_t gfn = slot->base_gfn + index - slot->gmem.pgoff;
-	int rc = kvm_arch_gmem_prepare(kvm, gfn, pfn, folio_order(folio));
+	int rc = kvm_arch_gmem_prepare(kvm, gfn, pfn, max_order);
 	if (rc) {
-		pr_warn_ratelimited("gmem: Failed to prepare folio for index %lx GFN %llx PFN %llx error %d.\n",
-				    index, gfn, pfn, rc);
+		pr_warn_ratelimited("gmem: Failed to prepare folio for index %lx GFN %llx PFN %llx max_order %d error %d.\n",
+				    index, gfn, pfn, max_order, rc);
 		return rc;
 	}
 #endif
@@ -148,15 +148,15 @@ static bool bitmap_test_allset_word(unsigned long *p, unsigned long start, unsig
 	return (*p & mask_to_set) == mask_to_set;
 }
 
-static void kvm_gmem_mark_prepared(struct file *file, pgoff_t index, struct folio *folio)
+static void kvm_gmem_mark_prepared(struct file *file, pgoff_t index, int order)
 {
 	struct kvm_gmem_inode *i_gmem = (struct kvm_gmem_inode *)file->f_inode->i_private;
-	unsigned long *p = i_gmem->prepared + BIT_WORD(index);
-	unsigned long npages = folio_nr_pages(folio);
+	unsigned long npages = (1ul << order);
+	unsigned long *p;
 
-	/* Folios must be naturally aligned */
-	WARN_ON_ONCE(index & (npages - 1));
+	/* The index isn't necessarily aligned to the requested order. */
 	index &= ~(npages - 1);
+	p = i_gmem->prepared + BIT_WORD(index);
 
 	/* Clear page before updating bitmap.  */
 	smp_wmb();
@@ -193,16 +193,16 @@ static void kvm_gmem_mark_range_unprepared(struct inode *inode, pgoff_t index, p
 		bitmap_clear_atomic_word(p++, 0, npages);
 }
 
-static bool kvm_gmem_is_prepared(struct file *file, pgoff_t index, struct folio *folio)
+static bool kvm_gmem_is_prepared(struct file *file, pgoff_t index, int order)
 {
 	struct kvm_gmem_inode *i_gmem = (struct kvm_gmem_inode *)file->f_inode->i_private;
-	unsigned long *p = i_gmem->prepared + BIT_WORD(index);
-	unsigned long npages = folio_nr_pages(folio);
+	unsigned long npages = (1ul << order);
+	unsigned long *p;
 	bool ret;
 
-	/* Folios must be naturally aligned */
-	WARN_ON_ONCE(index & (npages - 1));
+	/* The index isn't necessarily aligned to the requested order. */
 	index &= ~(npages - 1);
+	p = i_gmem->prepared + BIT_WORD(index);
 
 	if (npages < BITS_PER_LONG) {
 		ret = bitmap_test_allset_word(p, index, npages);
@@ -226,35 +226,41 @@ static bool kvm_gmem_is_prepared(struct file *file, pgoff_t index, struct folio
  */
 static int kvm_gmem_prepare_folio(struct kvm *kvm, struct file *file,
 				  struct kvm_memory_slot *slot,
-				  gfn_t gfn, struct folio *folio)
+				  gfn_t gfn, struct folio *folio, int max_order)
 {
 	unsigned long nr_pages, i;
-	pgoff_t index;
+	pgoff_t index, aligned_index;
 	int r;
 
-	nr_pages = folio_nr_pages(folio);
+	index = gfn - slot->base_gfn + slot->gmem.pgoff;
+	nr_pages = (1ull << max_order);
+	WARN_ON(nr_pages > folio_nr_pages(folio));
+	aligned_index = ALIGN_DOWN(index, nr_pages);
+
 	for (i = 0; i < nr_pages; i++)
-		clear_highpage(folio_page(folio, i));
+		if (!kvm_gmem_is_prepared(file, aligned_index + i, 0))
+			clear_highpage(folio_page(folio, aligned_index - folio_index(folio) + i));
 
 	/*
-	 * Preparing huge folios should always be safe, since it should
-	 * be possible to split them later if needed.
-	 *
-	 * Right now the folio order is always going to be zero, but the
-	 * code is ready for huge folios.  The only assumption is that
-	 * the base pgoff of memslots is naturally aligned with the
-	 * requested page order, ensuring that huge folios can also use
-	 * huge page table entries for GPA->HPA mapping.
+	 * In cases where only a sub-range of a folio is prepared, e.g. via
+	 * calling kvm_gmem_populate() for a non-aligned GPA range, or when
+	 * there's a mix of private/shared attributes for the GPA range that
+	 * the folio backs, it's possible that later on the same folio might
+	 * be accessed with a larger order when it becomes possible to map
+	 * the full GPA range into the guest using a larger order. In such
+	 * cases, some sub-ranges might already have been prepared.
 	 *
-	 * The order will be passed when creating the guest_memfd, and
-	 * checked when creating memslots.
+	 * Because of this, the arch-specific callbacks should be expected
+	 * to handle dealing with cases where some sub-ranges are already
+	 * in a prepared state, since the alternative would involve needing
+	 * to issue multiple prepare callbacks with finer granularity, and
+	 * potentially obfuscating cases where arch-specific callbacks can
+	 * be notified of larger-order mappings and potentially optimize
+	 * preparation based on that knowledge.
 	 */
-	WARN_ON(!IS_ALIGNED(slot->gmem.pgoff, 1 << folio_order(folio)));
-	index = gfn - slot->base_gfn + slot->gmem.pgoff;
-	index = ALIGN_DOWN(index, 1 << folio_order(folio));
-	r = __kvm_gmem_prepare_folio(kvm, slot, index, folio);
+	r = __kvm_gmem_prepare_folio(kvm, slot, index, folio, max_order);
 	if (!r)
-		kvm_gmem_mark_prepared(file, index, folio);
+		kvm_gmem_mark_prepared(file, index, max_order);
 
 	return r;
 }
@@ -812,20 +818,31 @@ int kvm_gmem_get_pfn(struct kvm *kvm, struct kvm_memory_slot *slot,
 {
 	pgoff_t index = kvm_gmem_get_index(slot, gfn);
 	struct file *file = kvm_gmem_get_file(slot);
+	int max_order_local;
 	struct folio *folio;
 	int r = 0;
 
 	if (!file)
 		return -EFAULT;
 
-	folio = __kvm_gmem_get_pfn(file, slot, index, pfn, max_order);
+	/*
+	 * The caller might pass a NULL 'max_order', but internally this
+	 * function needs to be aware of any order limitations set by
+	 * __kvm_gmem_get_pfn() so the scope of preparation operations can
+	 * be limited to the corresponding range. The initial order can be
+	 * arbitrarily large, but gmem doesn't currently support anything
+	 * greater than PMD_ORDER so use that for now.
+	 */
+	max_order_local = PMD_ORDER;
+
+	folio = __kvm_gmem_get_pfn(file, slot, index, pfn, &max_order_local);
 	if (IS_ERR(folio)) {
 		r = PTR_ERR(folio);
 		goto out;
 	}
 
-	if (kvm_gmem_is_prepared(file, index, folio))
-		r = kvm_gmem_prepare_folio(kvm, file, slot, gfn, folio);
+	if (!kvm_gmem_is_prepared(file, index, max_order_local))
+		r = kvm_gmem_prepare_folio(kvm, file, slot, gfn, folio, max_order_local);
 
 	folio_unlock(folio);
 
@@ -835,6 +852,8 @@ int kvm_gmem_get_pfn(struct kvm *kvm, struct kvm_memory_slot *slot,
 		folio_put(folio);
 
 out:
+	if (max_order)
+		*max_order = max_order_local;
 	fput(file);
 	return r;
 }
@@ -877,13 +896,24 @@ long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long
 			break;
 		}
 
+		/*
+		 * The max order shouldn't extend beyond the GFN range being
+		 * populated in this iteration, so set max_order accordingly.
+		 * __kvm_gmem_get_pfn() will then further adjust the order to
+		 * one that is contained by the backing memslot/folio.
+		 */
+		max_order = 0;
+		while (IS_ALIGNED(gfn, 1 << (max_order + 1)) &&
+		       (npages - i >= (1 << (max_order + 1))))
+			max_order++;
+
 		folio = __kvm_gmem_get_pfn(file, slot, index, &pfn, &max_order);
 		if (IS_ERR(folio)) {
 			ret = PTR_ERR(folio);
 			break;
 		}
 
-		if (kvm_gmem_is_prepared(file, index, folio)) {
+		if (kvm_gmem_is_prepared(file, index, max_order)) {
 			folio_unlock(folio);
 			folio_put(folio);
 			ret = -EEXIST;
@@ -907,7 +937,7 @@ long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long
 		ret = post_populate(kvm, gfn, pfn, p, max_order, opaque);
 		if (!ret) {
 			pgoff_t index = gfn - slot->base_gfn + slot->gmem.pgoff;
-			kvm_gmem_mark_prepared(file, index, folio);
+			kvm_gmem_mark_prepared(file, index, max_order);
 		}
 
 put_folio_and_exit:

---

## [4] Michael Roth — 2024-12-12
*Subject: [PATCH 3/5] KVM: gmem: Hold filemap invalidate lock while allocating/preparing folios*

Currently the preparedness tracking relies on holding a folio's lock
to keep allocations/preparations and corresponding updates to the
prepared bitmap atomic.

However, on the invalidation side, the bitmap entry for the GFN/index
corresponding to a folio might need to be cleared after truncation. In
these cases the folio's are no longer part of the filemap, so nothing
guards against a newly-allocated folio getting prepared for the same
GFN/index, and then subsequently having its bitmap entry cleared by the
concurrently executing invalidation code.

Avoid this by ensuring that the filemap invalidation lock is held to
ensure allocations/preparations and corresponding updates to the
prepared bitmap are atomic even versus invalidations. Use a shared lock
in the kvm_gmem_get_pfn() case so vCPUs can still fault in pages in
parallel.

Signed-off-by: Michael Roth <michael.roth@amd.com>
---
 virt/kvm/guest_memfd.c | 14 ++++++++++++++
 1 file changed, 14 insertions(+)

diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index 6907ae9fe149..9a5172de6a03 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -154,6 +154,8 @@ static void kvm_gmem_mark_prepared(struct file *file, pgoff_t index, int order)
 	unsigned long npages = (1ul << order);
 	unsigned long *p;
 
+	rwsem_assert_held(&file->f_mapping->invalidate_lock);
+
 	/* The index isn't necessarily aligned to the requested order. */
 	index &= ~(npages - 1);
 	p = i_gmem->prepared + BIT_WORD(index);
@@ -174,6 +176,8 @@ static void kvm_gmem_mark_range_unprepared(struct inode *inode, pgoff_t index, p
 	struct kvm_gmem_inode *i_gmem = (struct kvm_gmem_inode *)inode->i_private;
 	unsigned long *p = i_gmem->prepared + BIT_WORD(index);
 
+	rwsem_assert_held(&inode->i_mapping->invalidate_lock);
+
 	index &= BITS_PER_LONG - 1;
 	if (index) {
 		int first_word_count = min(npages, BITS_PER_LONG - index);
@@ -200,6 +204,8 @@ static bool kvm_gmem_is_prepared(struct file *file, pgoff_t index, int order)
 	unsigned long *p;
 	bool ret;
 
+	rwsem_assert_held(&file->f_mapping->invalidate_lock);
+
 	/* The index isn't necessarily aligned to the requested order. */
 	index &= ~(npages - 1);
 	p = i_gmem->prepared + BIT_WORD(index);
@@ -232,6 +238,8 @@ static int kvm_gmem_prepare_folio(struct kvm *kvm, struct file *file,
 	pgoff_t index, aligned_index;
 	int r;
 
+	rwsem_assert_held(&file->f_mapping->invalidate_lock);
+
 	index = gfn - slot->base_gfn + slot->gmem.pgoff;
 	nr_pages = (1ull << max_order);
 	WARN_ON(nr_pages > folio_nr_pages(folio));
@@ -819,12 +827,16 @@ int kvm_gmem_get_pfn(struct kvm *kvm, struct kvm_memory_slot *slot,
 	pgoff_t index = kvm_gmem_get_index(slot, gfn);
 	struct file *file = kvm_gmem_get_file(slot);
 	int max_order_local;
+	struct address_space *mapping;
 	struct folio *folio;
 	int r = 0;
 
 	if (!file)
 		return -EFAULT;
 
+	mapping = file->f_inode->i_mapping;
+	filemap_invalidate_lock_shared(mapping);
+
 	/*
 	 * The caller might pass a NULL 'max_order', but internally this
 	 * function needs to be aware of any order limitations set by
@@ -838,6 +850,7 @@ int kvm_gmem_get_pfn(struct kvm *kvm, struct kvm_memory_slot *slot,
 	folio = __kvm_gmem_get_pfn(file, slot, index, pfn, &max_order_local);
 	if (IS_ERR(folio)) {
 		r = PTR_ERR(folio);
+		filemap_invalidate_unlock_shared(mapping);
 		goto out;
 	}
 
@@ -845,6 +858,7 @@ int kvm_gmem_get_pfn(struct kvm *kvm, struct kvm_memory_slot *slot,
 		r = kvm_gmem_prepare_folio(kvm, file, slot, gfn, folio, max_order_local);
 
 	folio_unlock(folio);
+	filemap_invalidate_unlock_shared(mapping);
 
 	if (!r)
 		*page = folio_file_page(folio, index);

---

## [5] Michael Roth — 2024-12-12
*Subject: [PATCH 4/5] KVM: SEV: Improve handling of large ranges in gmem prepare callback*

The current code relies on the fact that guest_memfd will always call
sev_gmem_prepare() for each initial access to a particular guest GFN.
Once hugepage support is added to gmem, sev_gmem_prepare() might only
be called once for an entire range of GFNs. The current code will handle
this properly for 2MB folios if the entire range is currently shared and
can be marked as private using a 2MB RMP entry, but if any sub-ranges
were already in a prepared state (e.g. because they were part of the
initial guest state prepared via kvm_gmem_populate(), or userspace
initially had the 2MB region in a mixed attribute state for whatever
reason), then only the specific 4K GFN will get updated. If gmem rightly
decides it shouldn't have to call the prepare hook again for that range,
then the RMP entries for the other GFNs will never get updated.

Additionally, the current code assumes it will never be called for a
range larger than 2MB. This obviously won't work when 1GB+ hugepage
support is eventually added.

Rework the logic to ensure everything in the entire range gets updated,
with care taken to avoid ranges that are already private while still
maximizing the RMP entry sizes used to fill in the shared gaps.

Signed-off-by: Michael Roth <michael.roth@amd.com>
---
 arch/x86/kvm/svm/sev.c | 163 ++++++++++++++++++++++++-----------------
 1 file changed, 96 insertions(+), 67 deletions(-)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 418767dd69fa..40407768e4dd 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -4777,100 +4777,129 @@ void sev_handle_rmp_fault(struct kvm_vcpu *vcpu, gpa_t gpa, u64 error_code)
 	kvm_release_page_unused(page);
 }
 
-static bool is_pfn_range_shared(kvm_pfn_t start, kvm_pfn_t end)
+/*
+ * Find the offset of the next contiguous shared PFN range within the bounds of
+ * pfn_start/npages_max. If no shared pages are present, 'offset' will correspond
+ * to the end off the range and 'npages_shared' will be 0.
+ */
+static int next_shared_offset(struct kvm *kvm, kvm_pfn_t pfn_start, long npages_max,
+			      kvm_pfn_t *offset, long *npages_shared)
 {
-	kvm_pfn_t pfn = start;
+	kvm_pfn_t pfn = pfn_start;
+	int ret;
 
-	while (pfn < end) {
-		int ret, rmp_level;
+	*offset = 0;
+	*npages_shared = 0;
+
+	while (pfn < pfn_start + npages_max) {
 		bool assigned;
+		int level;
 
-		ret = snp_lookup_rmpentry(pfn, &assigned, &rmp_level);
+		ret = snp_lookup_rmpentry(pfn, &assigned, &level);
 		if (ret) {
-			pr_warn_ratelimited("SEV: Failed to retrieve RMP entry: PFN 0x%llx GFN start 0x%llx GFN end 0x%llx RMP level %d error %d\n",
-					    pfn, start, end, rmp_level, ret);
-			return false;
+			pr_warn_ratelimited("SEV: Failed to retrieve RMP entry: PFN 0x%llx error %d\n",
+					    pfn, ret);
+			return -EINVAL;
 		}
 
 		if (assigned) {
-			pr_debug("%s: overlap detected, PFN 0x%llx start 0x%llx end 0x%llx RMP level %d\n",
-				 __func__, pfn, start, end, rmp_level);
-			return false;
+			/* Continue if a shared range hasn't been found yet. */
+			if (*npages_shared)
+				break;
+		} else {
+			if (!*npages_shared)
+				*offset = pfn - pfn_start;
+			*npages_shared += PHYS_PFN(page_level_size(level));
 		}
 
-		pfn++;
-	}
-
-	return true;
-}
-
-static u8 max_level_for_order(int order)
-{
-	if (order >= KVM_HPAGE_GFN_SHIFT(PG_LEVEL_2M))
-		return PG_LEVEL_2M;
-
-	return PG_LEVEL_4K;
-}
+		pfn += PHYS_PFN(page_level_size(level));
 
-static bool is_large_rmp_possible(struct kvm *kvm, kvm_pfn_t pfn, int order)
-{
-	kvm_pfn_t pfn_aligned = ALIGN_DOWN(pfn, PTRS_PER_PMD);
+		/*
+		 * Only possible if RMP entry size is larger than the folio,
+		 * which kvm_gmem_prepare() should never allow for.
+		 */
+		WARN_ON_ONCE(pfn > pfn_start + npages_max);
+	}
 
-	/*
-	 * If this is a large folio, and the entire 2M range containing the
-	 * PFN is currently shared, then the entire 2M-aligned range can be
-	 * set to private via a single 2M RMP entry.
-	 */
-	if (max_level_for_order(order) > PG_LEVEL_4K &&
-	    is_pfn_range_shared(pfn_aligned, pfn_aligned + PTRS_PER_PMD))
-		return true;
+	if (!*npages_shared)
+		*offset = npages_max;
 
-	return false;
+	return 0;
 }
 
+/*
+ * This relies on the fact that the folio backing the PFN range is locked while
+ * this callback is issued. Otherwise, concurrent accesses to the same folio
+ * could result in the RMP table getting out of sync with what gmem is tracking
+ * as prepared/unprepared, likely resulting in the vCPU looping on
+ * KVM_EXIT_MEMORY_FAULTs that are never resolved since gmem thinks it has
+ * already processed the RMP table updates.
+ *
+ * This also assumes gmem is using filemap invalidate locks (or some other
+ * mechanism) to ensure that invalidations/hole-punches don't get interleaved
+ * with prepare callbacks.
+ *
+ * The net affect of this is that RMP table checks/updates should be consistent
+ * for the range of PFNs/GFNs this function is called with.
+ */
 int sev_gmem_prepare(struct kvm *kvm, kvm_pfn_t pfn, gfn_t gfn, int max_order)
 {
 	struct kvm_sev_info *sev = &to_kvm_svm(kvm)->sev_info;
-	kvm_pfn_t pfn_aligned;
-	gfn_t gfn_aligned;
-	int level, rc;
-	bool assigned;
+	unsigned long npages;
+	kvm_pfn_t pfn_start;
+	gfn_t gfn_start;
 
 	if (!sev_snp_guest(kvm))
 		return 0;
 
-	rc = snp_lookup_rmpentry(pfn, &assigned, &level);
-	if (rc) {
-		pr_err_ratelimited("SEV: Failed to look up RMP entry: GFN %llx PFN %llx error %d\n",
-				   gfn, pfn, rc);
-		return -ENOENT;
-	}
+	npages = (1ul << max_order);
+	pfn_start = ALIGN_DOWN(pfn, npages);
+	gfn_start = ALIGN_DOWN(gfn, npages);
+
+	for (pfn = pfn_start, gfn = gfn_start; pfn < pfn_start + npages;) {
+		long npages_shared;
+		kvm_pfn_t offset;
+		int rc;
+
+		rc = next_shared_offset(kvm, pfn, npages - (pfn - pfn_start),
+					&offset, &npages_shared);
+		if (rc < 0)
+			return offset;
+
+		pfn += offset;
+		gfn += offset;
+
+		while (npages_shared) {
+			int order, level;
+
+			if (IS_ALIGNED(pfn, 1ull << PMD_ORDER) &&
+			    npages_shared >= (1ul << PMD_ORDER)) {
+				order = PMD_ORDER;
+				level = PG_LEVEL_2M;
+			} else {
+				order = 0;
+				level = PG_LEVEL_4K;
+			}
 
-	if (assigned) {
-		pr_debug("%s: already assigned: gfn %llx pfn %llx max_order %d level %d\n",
-			 __func__, gfn, pfn, max_order, level);
-		return 0;
-	}
+			pr_debug("%s: preparing sub-range: gfn 0x%llx pfn 0x%llx order %d npages_shared %ld\n",
+				 __func__, gfn, pfn, order, npages_shared);
 
-	if (is_large_rmp_possible(kvm, pfn, max_order)) {
-		level = PG_LEVEL_2M;
-		pfn_aligned = ALIGN_DOWN(pfn, PTRS_PER_PMD);
-		gfn_aligned = ALIGN_DOWN(gfn, PTRS_PER_PMD);
-	} else {
-		level = PG_LEVEL_4K;
-		pfn_aligned = pfn;
-		gfn_aligned = gfn;
-	}
+			rc = rmp_make_private(pfn, gfn_to_gpa(gfn), level,
+					      sev->asid, false);
+			if (rc) {
+				pr_err_ratelimited("SEV: Failed to update RMP entry: GFN 0x%llx PFN 0x%llx order %d error %d\n",
+						   gfn, pfn, order, rc);
+				return rc;
+			}
 
-	rc = rmp_make_private(pfn_aligned, gfn_to_gpa(gfn_aligned), level, sev->asid, false);
-	if (rc) {
-		pr_err_ratelimited("SEV: Failed to update RMP entry: GFN %llx PFN %llx level %d error %d\n",
-				   gfn, pfn, level, rc);
-		return -EINVAL;
+			gfn += (1ull << order);
+			pfn += (1ull << order);
+			npages_shared -= (1ul << order);
+		}
 	}
 
-	pr_debug("%s: updated: gfn %llx pfn %llx pfn_aligned %llx max_order %d level %d\n",
-		 __func__, gfn, pfn, pfn_aligned, max_order, level);
+	pr_debug("%s: updated: gfn_start 0x%llx pfn_start 0x%llx npages %ld max_order %d\n",
+		 __func__, gfn_start, pfn_start, npages, max_order);
 
 	return 0;
 }

---

## [6] Michael Roth — 2024-12-12
*Subject: [PATCH 5/5] KVM: Add hugepage support for dedicated guest memory*

From: Sean Christopherson <seanjc@google.com>

Extended guest_memfd to allow backing guest memory with hugepages. This
is done as a best-effort by default until a better-defined mechanism is
put in place that can provide better control/assurances to userspace
about hugepage allocations.

When reporting the max order when KVM gets a pfn from guest_memfd, force
order-0 pages if the hugepage is not fully contained by the memslot
binding, e.g. if userspace requested hugepages but punches a hole in the
memslot bindings in order to emulate x86's VGA hole.

Link: https://lore.kernel.org/kvm/20231027182217.3615211-1-seanjc@google.com/T/#mccbd3e8bf9897f0ddbf864e6318d6f2f208b269c
Signed-off-by: Sean Christopherson <seanjc@google.com>
Message-Id: <20231027182217.3615211-18-seanjc@google.com>
[Allow even with CONFIG_TRANSPARENT_HUGEPAGE; dropped momentarily due to
 uneasiness about the API. - Paolo]
Signed-off-by: Paolo Bonzini <pbonzini@redhat.com>
[mdr: based on discussion in the Link regarding original patch, make the
      following set of changes:
      - For now, don't introduce an opt-in flag to enable hugepage
        support. By default, just make a best-effort for PMD_ORDER
        allocations so that there are no false assurances to userspace
        that they'll get hugepages. Performance-wise, it's better at
        least than the current guarantee that they will get 4K pages
        every time. A more proper opt-in interface can then improve on
        things later.
      - Pass GFP_NOWARN to alloc_pages() so failures are not disruptive
        to normal operations
      - Drop size checks during creation time. Instead just avoid huge
        allocations if they extend beyond end of the memfd.
      - Drop hugepage-related unit tests since everything is now handled
        transparently to userspace anyway.
      - Update commit message accordingly.]
Signed-off-by: Michael Roth <michael.roth@amd.com>
---
 include/linux/kvm_host.h |  2 ++
 virt/kvm/guest_memfd.c   | 68 +++++++++++++++++++++++++++++++---------
 virt/kvm/kvm_main.c      |  4 +++
 3 files changed, 59 insertions(+), 15 deletions(-)

diff --git a/include/linux/kvm_host.h b/include/linux/kvm_host.h
index c7e4f8be3e17..c946ec98d614 100644
--- a/include/linux/kvm_host.h
+++ b/include/linux/kvm_host.h
@@ -2278,6 +2278,8 @@ extern unsigned int halt_poll_ns_grow;
 extern unsigned int halt_poll_ns_grow_start;
 extern unsigned int halt_poll_ns_shrink;
 
+extern unsigned int gmem_2m_enabled;
+
 struct kvm_device {
 	const struct kvm_device_ops *ops;
 	struct kvm *kvm;
diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index 9a5172de6a03..d0caec99fe03 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -273,6 +273,36 @@ static int kvm_gmem_prepare_folio(struct kvm *kvm, struct file *file,
 	return r;
 }
 
+static struct folio *kvm_gmem_get_huge_folio(struct inode *inode, pgoff_t index,
+					     unsigned int order)
+{
+	pgoff_t npages = 1UL << order;
+	pgoff_t huge_index = round_down(index, npages);
+	struct address_space *mapping  = inode->i_mapping;
+	gfp_t gfp = mapping_gfp_mask(mapping) | __GFP_NOWARN;
+	loff_t size = i_size_read(inode);
+	struct folio *folio;
+
+	/* Make sure hugepages would be fully-contained by inode */
+	if ((huge_index + npages) * PAGE_SIZE > size)
+		return NULL;
+
+	if (filemap_range_has_page(mapping, (loff_t)huge_index << PAGE_SHIFT,
+				   (loff_t)(huge_index + npages - 1) << PAGE_SHIFT))
+		return NULL;
+
+	folio = filemap_alloc_folio(gfp, order);
+	if (!folio)
+		return NULL;
+
+	if (filemap_add_folio(mapping, folio, huge_index, gfp)) {
+		folio_put(folio);
+		return NULL;
+	}
+
+	return folio;
+}
+
 /*
  * Returns a locked folio on success.  The caller is responsible for
  * setting the up-to-date flag before the memory is mapped into the guest.
@@ -284,8 +314,15 @@ static int kvm_gmem_prepare_folio(struct kvm *kvm, struct file *file,
  */
 static struct folio *kvm_gmem_get_folio(struct inode *inode, pgoff_t index)
 {
-	/* TODO: Support huge pages. */
-	return filemap_grab_folio(inode->i_mapping, index);
+	struct folio *folio = NULL;
+
+	if (gmem_2m_enabled)
+		folio = kvm_gmem_get_huge_folio(inode, index, PMD_ORDER);
+
+	if (!folio)
+		folio = filemap_grab_folio(inode->i_mapping, index);
+
+	return folio;
 }
 
 static void kvm_gmem_invalidate_begin(struct kvm_gmem *gmem, pgoff_t start,
@@ -660,6 +697,7 @@ static int __kvm_gmem_create(struct kvm *kvm, loff_t size, u64 flags)
 	inode->i_size = size;
 	mapping_set_gfp_mask(inode->i_mapping, GFP_HIGHUSER);
 	mapping_set_inaccessible(inode->i_mapping);
+	mapping_set_large_folios(inode->i_mapping);
 	/* Unmovable mappings are supposed to be marked unevictable as well. */
 	WARN_ON_ONCE(!mapping_unevictable(inode->i_mapping));
 
@@ -791,6 +829,7 @@ static struct folio *__kvm_gmem_get_pfn(struct file *file,
 {
 	struct kvm_gmem *gmem = file->private_data;
 	struct folio *folio;
+	pgoff_t huge_index;
 
 	if (file != slot->gmem.file) {
 		WARN_ON_ONCE(slot->gmem.file);
@@ -803,6 +842,17 @@ static struct folio *__kvm_gmem_get_pfn(struct file *file,
 		return ERR_PTR(-EIO);
 	}
 
+	/*
+	 * The folio can be mapped with a hugepage if and only if the folio is
+	 * fully contained by the range the memslot is bound to.  Note, the
+	 * caller is responsible for handling gfn alignment, this only deals
+	 * with the file binding.
+	 */
+	huge_index = ALIGN_DOWN(index, 1ull << *max_order);
+	if (huge_index < slot->gmem.pgoff ||
+	    huge_index + (1ull << *max_order) > slot->gmem.pgoff + slot->npages)
+		*max_order = 0;
+
 	folio = kvm_gmem_get_folio(file_inode(file), index);
 	if (IS_ERR(folio))
 		return folio;
@@ -814,8 +864,7 @@ static struct folio *__kvm_gmem_get_pfn(struct file *file,
 	}
 
 	*pfn = folio_file_pfn(folio, index);
-	if (max_order)
-		*max_order = 0;
+	*max_order = min_t(int, *max_order, folio_order(folio));
 
 	return folio;
 }
@@ -910,17 +959,6 @@ long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long
 			break;
 		}
 
-		/*
-		 * The max order shouldn't extend beyond the GFN range being
-		 * populated in this iteration, so set max_order accordingly.
-		 * __kvm_gmem_get_pfn() will then further adjust the order to
-		 * one that is contained by the backing memslot/folio.
-		 */
-		max_order = 0;
-		while (IS_ALIGNED(gfn, 1 << (max_order + 1)) &&
-		       (npages - i >= (1 << (max_order + 1))))
-			max_order++;
-
 		folio = __kvm_gmem_get_pfn(file, slot, index, &pfn, &max_order);
 		if (IS_ERR(folio)) {
 			ret = PTR_ERR(folio);
diff --git a/virt/kvm/kvm_main.c b/virt/kvm/kvm_main.c
index 5901d03e372c..525d136ba235 100644
--- a/virt/kvm/kvm_main.c
+++ b/virt/kvm/kvm_main.c
@@ -94,6 +94,10 @@ unsigned int halt_poll_ns_shrink = 2;
 module_param(halt_poll_ns_shrink, uint, 0644);
 EXPORT_SYMBOL_GPL(halt_poll_ns_shrink);
 
+unsigned int gmem_2m_enabled;
+EXPORT_SYMBOL_GPL(gmem_2m_enabled);
+module_param(gmem_2m_enabled, uint, 0644);
+
 /*
  * Allow direct access (from KVM or the CPU) without MMU notifier protection
  * to unpinned pages.

---

## [7] David Hildenbrand — 2024-12-20
*Subject: Re: [PATCH RFC v1 0/5] KVM: gmem: 2MB THP support and preparedness
 tracking changes*

On 12.12.24 07:36, Michael Roth wrote:
> This patchset is also available at:
> 

Sorry for the late reply, it's been a couple of crazy weeks, and I'm 
trying to give at least some feedback on stuff in my inbox before even 
more will pile up over Christmas :) . Let me summarize my thoughts:

THPs in Linux rely on the following principle:

(1) We try allocating a THP, if that fails we rely on khugepaged to fix
     it up later (shmem+anon). So id we cannot grab a free THP, we
     deffer it to a later point.

(2) We try to be as transparent as possible: punching a hole will
     usually destroy the THP (either immediately for shmem/pagecache or
     deferred for anon memory) to free up the now-free pages. That's
     different to hugetlb, where partial hole-punching will always zero-
     out the memory only; the partial memory will not get freed up and
     will get reused later.

     Destroying a THP for shmem/pagecache only works if there are no
     unexpected page references, so there can be cases where we fail to
     free up memory. For the pagecache that's not really
     an issue, because memory reclaim will fix that up at some point. For
     shmem, there  were discussions to do scan for 0ed pages and free
     them up during memory reclaim, just like we do now for anon memory
      as well.

(3) Memory compaction is vital for guaranteeing that we will be able to
     create THPs the longer the system was running,


With guest_memfd we cannot rely on any daemon to fix it up as in (1) for 
us later (would require page memory migration support).

We use truncate_inode_pages_range(), which will split a THP into small 
pages if you partially punch-hole it, so (2) would apply; splitting 
might fail as well in some cases if there are unexpected references.

I wonder what would happen if user space would punch a hole in private 
memory, making truncate_inode_pages_range() overwrite it with 0s if 
splitting the THP failed (memory write to private pages under TDX?). 
Maybe something similar would happen if a private page would get 0-ed 
out when freeing+reallocating it, not sure how that is handled.


guest_memfd currently actively works against (3) as soon as we (A) 
fallback to allocating small pages or (B) split a THP due to hole 
punching, as the remaining fragments cannot get reassembled anymore.

I assume there is some truth to "hole-punching is a userspace policy", 
but this mechanism will actively work against itself as soon as you 
start falling back to small pages in any way.



So I'm wondering if a better start would be to (A) always allocate huge 
pages from the buddy (no fallback) and (B) partial punches are either 
disallowed or only zero-out the memory. But even a sequence of partial 
punches that cover the whole huge page will not end up freeing all parts 
if splitting failed at some point, which I quite dislike ...

But then we'd need memory preallocation, and I suspect to make this 
really useful -- just like with 2M/1G "hugetlb" support -- in-place 
shared<->private conversion will be a requirement. ... at which point 
we'd have reached the state where it's almost the 2M hugetlb support.


This is not a very strong push back, more a "this does not quite sound 
right to me" and I have the feeling that this might get in the way of 
in-place shared<->private conversion; I might be wrong about the latter 
though.

With memory compaction working for guest_memfd, it would all be easier.

Note that I'm not quite sure about the "2MB" interface, should it be a 
"PMD-size" interface?

---

## [8] Shah, Amit — 2025-01-07
*Subject: Re: [PATCH RFC v1 0/5] KVM: gmem: 2MB THP support and preparedness
 tracking changes*

On Fri, 2024-12-20 at 12:31 +0100, David Hildenbrand wrote:
> On 12.12.24 07:36, Michael Roth wrote:
> > This patchset is also available at:

My turn for the lateness - back from a break.

I should also preface that Mike is off for at least a month more, but
he will return to continue working on this.  In the meantime, I've had
a chat with him about this work to keep the discussion alive on the
lists.

> THPs in Linux rely on the following principle:
> 

True.  And not having a huge page when requested to begin with (as in 1
above) beats the purpose entirely -- the point is to speed up SEV-SNP
setup and guests by having fewer pages to work with.

> We use truncate_inode_pages_range(), which will split a THP into
> small 

that sounds fine..

> (B) partial punches are either
> disallowed or only zero-out the memory. But even a sequence of

... this  basically just looks like hugetlb support (i.e. without the
"transparent" part), isn't it?

> But then we'd need memory preallocation, and I suspect to make this 
> really useful -- just like with 2M/1G "hugetlb" support -- in-place 

Right, exactly.

> This is not a very strong push back, more a "this does not quite
> sound 

TBH my 2c are that getting hugepage supported, and disabling THP for
SEV-SNP guests will work fine.

But as Mike mentioned above, this series is to add a user on top of
Paolo's work - and that seems more straightforward to experiment with
and figure out hugepage support in general while getting all the other
hugepage details done in parallel.

> With memory compaction working for guest_memfd, it would all be
> easier.

... btw do you know how well this is coming along?

> Note that I'm not quite sure about the "2MB" interface, should it be
> a 

I think Mike and I touched upon this aspect too - and I may be
misremembering - Mike suggested getting 1M, 2M, and bigger page sizes
in increments -- and then fitting in PMD sizes when we've had enough of
those.  That is to say he didn't want to preclude it, or gate the PMD
work on enabling all sizes first.

		Amit

---

## [9] David Hildenbrand — 2025-01-22
*Subject: Re: [PATCH RFC v1 0/5] KVM: gmem: 2MB THP support and preparedness
 tracking changes*

>> Sorry for the late reply, it's been a couple of crazy weeks, and I'm
>> trying to give at least some feedback on stuff in my inbox before

So now it's my turn to being late again ;) As promised during the last 
call, a few points from my side.

> 
>> THPs in Linux rely on the following principle:

Right.

> 
>> We use truncate_inode_pages_range(), which will split a THP into

Yes, just using a different allocator until we have a predictable 
allocator with reserves.

Note that I am not sure how much "transparent" here really applies, 
given the differences to THPs ...

> 
>> But then we'd need memory preallocation, and I suspect to make this

As discussed in the last bi-weekly MM meeting (and in contrast to what I 
assumed), Vishal was right: we should be able to support in-place 
shared<->private conversion as long as we can split a large folio when 
any page of it is getting converted to shared.

(split is possible if there are no unexpected folio references; private 
pages cannot be GUP'ed, so it is feasible)

So similar to the hugetlb work, that split would happen and would be a 
bit "easier", because ordinary folios (in contrast to hugetlb) are 
prepared to be split.

So supporting larger folios for private memory might not make in-place 
conversion significantly harder; the important part is that shared 
folios may only be small.

The split would just mean that we start exposing individual small folios 
to the core-mm, not that we would allow page migration for the shared 
parts etc. So the "whole 2M chunk" will remain allocated to guest_memfd.

> 
> TBH my 2c are that getting hugepage supported, and disabling THP for

Likely it will not be that easy as soon as hugetlb reserves etc. will 
come into play.

> 
> But as Mike mentioned above, this series is to add a user on top of

I would suggest to not call this "THP". Maybe we can call it "2M folio 
support" for gmem.

Similar to other FSes, we could just not limit ourselves to 2M folios, 
and simply allocate any large folios. But sticking to 2M might be 
beneficial in regards to memory fragmentation (below).

> 
>> With memory compaction working for guest_memfd, it would all be

People have been talking about that, but I suspect this is very 
long-term material.

> 
>> Note that I'm not quite sure about the "2MB" interface, should it be

Starting with 2M is reasonable for now. The real question is how we want 
to deal with

(a) Not being able to allocate a 2M folio reliably
(b) Partial discarding

Using only (unmovable) 2M folios would effectively not cause any real 
memory fragmentation in the system, because memory compaction operates 
on 2M pageblocks on x86. So that feels quite compelling.

Ideally we'd have a 2M pagepool from which guest_memfd would allocate 
pages and to which it would putback pages. Yes, this sound similar to 
hugetlb, but might be much easier to implement, because we are not 
limited by some of the hugetlb design decisions (HVO, not being able to 
partially map them, etc.).

---

## [10] Tom Lendacky — 2025-01-22
*Subject: Re: [PATCH 1/5] KVM: gmem: Don't rely on __kvm_gmem_get_pfn() for
 preparedness*

On 12/12/24 00:36, Michael Roth wrote:
> Currently __kvm_gmem_get_pfn() sets 'is_prepared' so callers can skip
> calling kvm_gmem_prepare_folio(). However, subsequent patches will

Shouldn't this be !kvm_gmem_is_prepared() ?

Thanks,
Tom

>  		r = kvm_gmem_prepare_folio(kvm, file, slot, gfn, folio);
>

---

## [11] Vishal Annapurve — 2025-02-10
*Subject: Re: [PATCH RFC v1 0/5] KVM: gmem: 2MB THP support and preparedness
 tracking changes*

On Wed, Dec 11, 2024 at 10:37 PM Michael Roth <michael.roth@amd.com> wrote:
>
> This patchset is also available at:

Looking at the work targeted by Fuad to add in-place memory conversion
support via [1] and Ackerley in future to address hugetlb page
support, can the state tracking for preparedness be simplified as?
i) prepare guest memfd ranges when "first time an offset with
mappability = GUEST is allocated or first time an allocated offset has
mappability = GUEST". Some scenarios that would lead to guest memfd
range preparation:
     - Create file with default mappability to host, fallocate, convert
     - Create file with default mappability to Guest, guest faults on
private memory
ii) Unprepare guest memfd ranges when "first time an offset with
mappability = GUEST is deallocated or first time an allocated offset
has lost mappability = GUEST attribute", some scenarios that would
lead to guest memfd range unprepare:
     -  Truncation
     -  Conversion
iii) To handle scenarios with hugepages, page splitting/merging in
guest memfd can also signal change in page granularities.

[1] https://lore.kernel.org/kvm/20250117163001.2326672-1-tabba@google.com/

---

## [12] Michael Roth — 2025-02-19
*Subject: Re: [PATCH RFC v1 0/5] KVM: gmem: 2MB THP support and preparedness
 tracking changes*

On Mon, Feb 10, 2025 at 05:16:33PM -0800, Vishal Annapurve wrote:
> On Wed, Dec 11, 2024 at 10:37 PM Michael Roth <michael.roth@amd.com> wrote:
> >

Yes, this seems like a compelling approach. One aspect that still
remains is knowing *when* the preparation has been done, so that the
next time a private page is accessed, either to re-fault into the guest
(e.g. because it was originally mapped 2MB and then a sub-page got
converted to shared so the still-private pages need to get re-faulted
in as 4K), or maybe some other path where KVM needs to grab the private
PFN via kvm_gmem_get_pfn() but not actually read/write to it (I think
the GHCB AP_CREATION path for bringing up APs might do this).

We could just keep re-checking the RMP table to see if the PFN was
already set to private in the RMP table, but I think one of the design
goals of the preparedness tracking was to have gmem itself be aware of
this and not farm it out to platform-specific data structures/tracking.

So as a proof of concept I've been experimenting with using Fuad's
series ([1] in your response) and adding an additional GUEST_PREPARED
state so that it can be tracked via the same mappability xarray (or
whatever data structure we end up using for mappability-tracking).
In that case GUEST becomes sort of a transient state that can be set
in advance of actual allocation/fault-time.

That seems to have a lot of nice characteristics, because (in that
series at least) guest-mappable (as opposed to all-mappable)
specifically corresponds to private guest pages, which for SNP require
preparation before they can be mapped into the nested page table so
it seems like a natural fit.

> ii) Unprepare guest memfd ranges when "first time an offset with
> mappability = GUEST is deallocated or first time an allocated offset

Similar story here: it seems like a good fit. Truncation already does
the unprepare via .free_folio->kvm_arch_gmem_invalidate callback, and
if we rework THP to behave similar to HugeTLB in that we only free back
the full 2MB folio rather than splitting it like in this series, I think
that might be sufficient for truncation. If userspace tries to truncate
a subset of a 2MB private folio we could no-op and just leave it in
GUEST_PREPARED. If we stick with THP, my thinking is we tell userspace
what the max granularity is, and userspace will know that it must
truncate with that same granularity if it actually wants to free memory.
It sounds like the HugeTLB would similarly be providing this sort of
information. What's nice is that if we stick with best-effort THP-based
allocator, and allow best-effort allocator to fall back to smaller page
sizes, this scheme would still work, since we'd still always be able to
free folios without splitting. But I'll try to get a better idea of what
this looks like in practice.

For conversion, we'd need to hook in an additional
kvm_arch_gmem_invalidate() somewhere to make sure the folio is
host-owned in the RMP table before transitioning to host/all-mappable,
but that seems pretty straightforward.

> iii) To handle scenarios with hugepages, page splitting/merging in
> guest memfd can also signal change in page granularities.

Not yet clear to me if extra handling for prepare/unprepare is needed
here, but it does seem like an option if needed.

Thanks,

Mike

> 
> [1] https://lore.kernel.org/kvm/20250117163001.2326672-1-tabba@google.com/

---

## [13] Michael Roth — 2025-02-19
*Subject: Re: [PATCH 1/5] KVM: gmem: Don't rely on __kvm_gmem_get_pfn() for
 preparedness*

On Wed, Jan 22, 2025 at 08:39:37AM -0600, Tom Lendacky wrote:
> On 12/12/24 00:36, Michael Roth wrote:
> > Currently __kvm_gmem_get_pfn() sets 'is_prepared' so callers can skip

Yes indeed. It looks like I fixed this up later, but accidentally squashed it
into PATCH #2 rather than here. Will fix for the next spin.

Thanks,

Mike

> 
> Thanks,

---

## [14] Yan Zhao — 2025-03-14
*Subject: Re: [PATCH RFC v1 0/5] KVM: gmem: 2MB THP support and preparedness
 tracking changes*

On Wed, Jan 22, 2025 at 03:25:29PM +0100, David Hildenbrand wrote:
>(split is possible if there are no unexpected folio references; private 
>pages cannot be GUP'ed, so it is feasible)
...
> > > Note that I'm not quite sure about the "2MB" interface, should it be
> > > a
Hi David,

I'm just trying to understand the background of in-place conversion.

Regarding to the two issues you mentioned with THP and non-in-place-conversion,
I have some questions (still based on starting with 2M):

> (a) Not being able to allocate a 2M folio reliably
If we start with fault in private pages from guest_memfd (not in page pool way)
and shared pages anonymously, is it correct to say that this is only a concern
when memory is under pressure?

> (b) Partial discarding
For shared pages, page migration and folio split are possible for shared THP?

For private pages, as you pointed out earlier, if we can ensure there are no
unexpected folio references for private memory, splitting a private huge folio
should succeed. Are you concerned about the memory fragmentation after repeated
partial conversions of private pages to and from shared?

Thanks
Yan

> Using only (unmovable) 2M folios would effectively not cause any real memory
> fragmentation in the system, because memory compaction operates on 2M

---

## [15] Yan Zhao — 2025-03-14
*Subject: Re: [PATCH RFC v1 0/5] KVM: gmem: 2MB THP support and preparedness
 tracking changes*

On Wed, Feb 19, 2025 at 07:09:57PM -0600, Michael Roth wrote:
> On Mon, Feb 10, 2025 at 05:16:33PM -0800, Vishal Annapurve wrote:
> > On Wed, Dec 11, 2024 at 10:37 PM Michael Roth <michael.roth@amd.com> wrote:
Hi Michael,

We are currently working on enabling 2M huge pages on TDX.
We noticed this series and hope if could also work with TDX huge pages.

While disallowing <2M page conversion is also not ideal for TDX, we also think
that it would be great if we could start with 2M and non-in-place conversion
first. In that case, is memory fragmentation caused by partial discarding a
problem for you [1]? Is page promotion a must in your initial huge page support?

Do you have any repo containing your latest POC?

Thanks
Yan

[1] https://lore.kernel.org/all/Z9PyLE%2FLCrSr2jCM@yzhao56-desk.sh.intel.com/

---

## [16] Yan Zhao — 2025-03-14
*Subject: Re: [PATCH 3/5] KVM: gmem: Hold filemap invalidate lock while
 allocating/preparing folios*

This patch would cause host deadlock when booting up a TDX VM even if huge page
is turned off. I currently reverted this patch. No further debug yet.

On Thu, Dec 12, 2024 at 12:36:33AM -0600, Michael Roth wrote:
> Currently the preparedness tracking relies on holding a folio's lock
> to keep allocations/preparations and corresponding updates to the

---

## [17] David Hildenbrand — 2025-03-14
*Subject: Re: [PATCH RFC v1 0/5] KVM: gmem: 2MB THP support and preparedness
 tracking changes*

On 14.03.25 10:09, Yan Zhao wrote:
> On Wed, Jan 22, 2025 at 03:25:29PM +0100, David Hildenbrand wrote:
>> (split is possible if there are no unexpected folio references; private

Hi!

> I'm just trying to understand the background of in-place conversion.
> 

Usually, fragmentation starts being a problem under memory pressure, and 
memory pressure can show up simply because the page cache makes us of as 
much memory as it wants.

As soon as we start allocating a 2 MB page for guest_memfd, to then 
split it up + free only some parts back to the buddy (on private->shared 
conversion), we create fragmentation that cannot get resolved as long as 
the remaining private pages are not freed. A new conversion from 
shared->private on the previously freed parts will allocate other 
unmovable pages (not the freed ones) and make fragmentation worse.

In-place conversion improves that quite a lot, because guest_memfd tself 
will not cause unmovable fragmentation. Of course, under memory 
pressure, when and cannot allocate a 2M page for guest_memfd, it's 
unavoidable. But then, we already had fragmentation (and did not really 
cause any new one).

We discussed in the upstream call, that if guest_memfd (primarily) only 
allocates 2M pages and frees 2M pages, it will not cause fragmentation 
itself, which is pretty nice.

> 
>> (b) Partial discarding

I assume by "shared" you mean "not guest_memfd, but some other memory we 
use as an overlay" -- so no in-place conversion.

Yes, that should be possible as long as nothing else prevents 
migration/split (e.g., longterm pinning)

> 
> For private pages, as you pointed out earlier, if we can ensure there are no

Yes, and maybe (hopefully) we'll reach a point where private parts will 
not have a refcount at all (initially, frozen refcount, discussed during 
the last upstream call).

Are you concerned about the memory fragmentation after repeated
> partial conversions of private pages to and from shared?

Not only repeated, even just a single partial conversion. But of course, 
repeated partial conversions will make it worse (e.g., never getting a 
private huge page back when there was a partial conversion).

---

## [18] Yan Zhao — 2025-03-14
*Subject: Re: [PATCH 5/5] KVM: Add hugepage support for dedicated guest memory*

> +static struct folio *kvm_gmem_get_huge_folio(struct inode *inode, pgoff_t index,
> +					     unsigned int order)
Instead of returning NULL here, what about invoking __filemap_get_folio()
directly as below?

> +	if (filemap_add_folio(mapping, folio, huge_index, gfp)) {
> +		folio_put(folio);
Also need to check IS_ERR(folio).

> +		folio = filemap_grab_folio(inode->i_mapping, index);
> +
Could we introduce a common helper to calculate max_order by checking for
gfn/index alignment and ensuring memory attributes in range are uniform?

Then we can pass in the max_order to kvm_gmem_get_folio() and only allocate huge
folio when it's necessary.

static struct folio *kvm_gmem_get_folio(struct inode *inode, pgoff_t index, int max_order)
{                                                                                
        struct folio *folio = NULL;                                              
                                                                                 
        if (max_order >= PMD_ORDER) {                                            
                fgf_t fgp_flags = FGP_LOCK | FGP_ACCESSED | FGP_CREAT;           
                                                                                 
                fgp_flags |= fgf_set_order(1U << (PAGE_SHIFT + PMD_ORDER));      
                folio = __filemap_get_folio(inode->i_mapping, index, fgp_flags,  
                        mapping_gfp_mask(inode->i_mapping));                     
        }                                                                        
                                                                                 
        if (!folio || IS_ERR(folio))                                             
                folio = filemap_grab_folio(inode->i_mapping, index);             
                                                                                 
        return folio;                                                            
}

---

## [19] Yan Zhao — 2025-03-14
*Subject: Re: [PATCH RFC v1 0/5] KVM: gmem: 2MB THP support and preparedness
 tracking changes*

On Fri, Mar 14, 2025 at 10:33:07AM +0100, David Hildenbrand wrote:
> On 14.03.25 10:09, Yan Zhao wrote:
> > On Wed, Jan 22, 2025 at 03:25:29PM +0100, David Hildenbrand wrote:
Ah, I see. The problem of fragmentation is because memory allocated by
guest_memfd is unmovable. So after freeing part of a 2MB folio, the whole 2MB is
still unmovable. 

I previously thought fragmentation would only impact the guest by providing no
new huge pages. So if a confidential VM does not support merging small PTEs into
a huge PMD entry in its private page table, even if the new huge memory range is
physically contiguous after a private->shared->private conversion, the guest
still cannot bring back huge pages.

> In-place conversion improves that quite a lot, because guest_memfd tself
> will not cause unmovable fragmentation. Of course, under memory pressure,
Makes sense.

> > 
> > > (b) Partial discarding
Yes, not guest_memfd, in the case of non-in-place conversion.

> as an overlay" -- so no in-place conversion.
> 
Yes, I also tested in TDX by not acquiring folio ref count in TDX specific code
and found that partial splitting could work.

> Are you concerned about the memory fragmentation after repeated
> > partial conversions of private pages to and from shared?
Thanks for the explanation!

Do you think there's any chance for guest_memfd to support non-in-place
conversion first?

---

## [20] Yan Zhao — 2025-03-18
*Subject: Re: [PATCH RFC v1 0/5] KVM: gmem: 2MB THP support and preparedness
 tracking changes*

On Fri, Mar 14, 2025 at 07:19:33PM +0800, Yan Zhao wrote:
> On Fri, Mar 14, 2025 at 10:33:07AM +0100, David Hildenbrand wrote:
> > On 14.03.25 10:09, Yan Zhao wrote:
e.g. we can have private pages allocated from guest_memfd and allows the
private pages to be THP.

Meanwhile, shared pages are not allocated from guest_memfd, and let it only
fault in 4K granularity. (specify it by a flag?)

When we want to convert a 4K from a 2M private folio to shared, we can just
split the 2M private folio as there's no extra ref count of private pages;

when we do shared to private conversion, no split is required as shared pages
are in 4K granularity. And even if user fails to specify the shared pages as
small pages only, the worst thing is that a 2M shared folio cannot be split, and
more memory is consumed.

Of couse, memory fragmentation is still an issue as the private pages are
allocated unmovable. But do you think it's a good simpler start before in-place
conversion is ready?

Thanks
Yan

---

## [21] David Hildenbrand — 2025-03-18
*Subject: Re: [PATCH RFC v1 0/5] KVM: gmem: 2MB THP support and preparedness
 tracking changes*

On 18.03.25 03:24, Yan Zhao wrote:
> On Fri, Mar 14, 2025 at 07:19:33PM +0800, Yan Zhao wrote:
>> On Fri, Mar 14, 2025 at 10:33:07AM +0100, David Hildenbrand wrote:

Yes, IIRC that's precisely what this series is doing, because the 
ftruncate() will try splitting the folio (which might still fail on 
speculative references, see my comment as rely to this series)

In essence: yes, splitting to 4k should work (although speculative 
reference might require us to retry). But the "4k hole punch" is the 
ugly it.

So you really want in-place conversion where the private->shared will 
split (but not punch) and the shared->private will collapse again if 
possible.

> 
> when we do shared to private conversion, no split is required as shared pages

Yes, and that you will never ever get a "THP" back when there was a 
conversion from private->shared of a single page that split the THP and 
discarded that page.

  But do you think it's a good simpler start before in-place
> conversion is ready?

There was a discussion on that on the bi-weekly upstream meeting on 
February the 6. The recording has more details, I summarized it as

"David: Probably a good idea to focus on the long-term use case where we 
have in-place conversion support, and only allow truncation in hugepage 
(e.g., 2 MiB) size; conversion shared<->private could still be done on 4 
KiB granularity as for hugetlb."

In general, I think our time is better spent working on the real deal 
than on interim solutions that should not be called "THP support".

---

## [22] Yan Zhao — 2025-03-19
*Subject: Re: [PATCH RFC v1 0/5] KVM: gmem: 2MB THP support and preparedness
 tracking changes*

On Tue, Mar 18, 2025 at 08:13:05PM +0100, David Hildenbrand wrote:
> On 18.03.25 03:24, Yan Zhao wrote:
> > On Fri, Mar 14, 2025 at 07:19:33PM +0800, Yan Zhao wrote:
Yes, unless we still keep that page in page cache, which would consume even more
memory.
 
>  But do you think it's a good simpler start before in-place
> > conversion is ready?
Will check and study it. Thanks for directing me to the history.

> In general, I think our time is better spent working on the real deal than
> on interim solutions that should not be called "THP support".
I see. Thanks for the explanation!

---

## [23] Yan Zhao — 2025-04-07
*Subject: Re: [PATCH 3/5] KVM: gmem: Hold filemap invalidate lock while
 allocating/preparing folios*

On Fri, Mar 14, 2025 at 05:20:21PM +0800, Yan Zhao wrote:
> This patch would cause host deadlock when booting up a TDX VM even if huge page
> is turned off. I currently reverted this patch. No further debug yet.
This is because kvm_gmem_populate() takes filemap invalidation lock, and for
TDX, kvm_gmem_populate() further invokes kvm_gmem_get_pfn(), causing deadlock.

kvm_gmem_populate
  filemap_invalidate_lock
  post_populate
    tdx_gmem_post_populate
      kvm_tdp_map_page
       kvm_mmu_do_page_fault
         kvm_tdp_page_fault
	   kvm_tdp_mmu_page_fault
	     kvm_mmu_faultin_pfn
	       __kvm_mmu_faultin_pfn
	         kvm_mmu_faultin_pfn_private
		   kvm_gmem_get_pfn
		     filemap_invalidate_lock_shared
	
Though, kvm_gmem_populate() is able to take shared filemap invalidation lock,
(then no deadlock), lockdep would still warn "Possible unsafe locking scenario:
...DEADLOCK" due to the recursive shared lock, since commit e918188611f0
("locking: More accurate annotations for read_lock()").

> > @@ -819,12 +827,16 @@ int kvm_gmem_get_pfn(struct kvm *kvm, struct kvm_memory_slot *slot,
> >  	pgoff_t index = kvm_gmem_get_index(slot, gfn);

---

## [24] Ackerley Tng — 2025-04-23
*Subject: Re: [PATCH 3/5] KVM: gmem: Hold filemap invalidate lock while
 allocating/preparing folios*

Yan Zhao <yan.y.zhao@intel.com> writes:

> On Fri, Mar 14, 2025 at 05:20:21PM +0800, Yan Zhao wrote:
>> This patch would cause host deadlock when booting up a TDX VM even if huge page

Thank you for investigating. This should be fixed in the next revision.

>> > @@ -819,12 +827,16 @@ int kvm_gmem_get_pfn(struct kvm *kvm, struct kvm_memory_slot *slot,
>> >  	pgoff_t index = kvm_gmem_get_index(slot, gfn);

---
