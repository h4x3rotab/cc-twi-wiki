---
title: 'KVM: guest_memfd: Support in-place conversion for CoCo VMs'
date: 2025-06-12
last_reply: 2025-11-07
message_count: 18
participants: ['Michael Roth', 'David Hildenbrand', 'Vishal Annapurve', 'Ackerley Tng', 'Yan Zhao']
---

## [1] Michael Roth — 2025-06-12

This patchset is also available at:

  https://github.com/amdese/linux/commits/snp-inplace-conversion-rfc1

and is based on top of the following patches plucked from Ackerley's
HugeTLBFS series[1], which add support for tracking/converting guest_memfd
pages between private/shared states so the same physical pages can be used
to handle both private/shared accesses by the guest or by userspace:

  KVM: selftests: Update script to map shared memory from guest_memfd
  KVM: selftests: Update private_mem_conversions_test to mmap guest_memfd
  KVM: selftests: Add script to exercise private_mem_conversions_test
  KVM: selftests: Test conversion flows for guest_memfd
  KVM: selftests: Allow cleanup of ucall_pool from host
  KVM: selftests: Refactor vm_mem_add to be more flexible
  KVM: selftests: Test faulting with respect to GUEST_MEMFD_FLAG_INIT_PRIVATE
  KVM: selftests: Test flag validity after guest_memfd supports conversions
  KVM: guest_memfd: Add CAP KVM_CAP_GMEM_CONVERSION
  KVM: Query guest_memfd for private/shared status
  KVM: guest_memfd: Skip LRU for guest_memfd folios
  KVM: guest_memfd: Introduce KVM_GMEM_CONVERT_SHARED/PRIVATE ioctls
  KVM: selftests: Update guest_memfd_test for INIT_PRIVATE flag
  KVM: guest_memfd: Introduce and use shareability to guard faulting
  KVM: guest_memfd: Make guest mem use guest mem inodes instead of anonymous inodes
  fs: Refactor to provide function that allocates a secure anonymous inode

  "[RFC PATCH v2 00/51] 1G page support for guest_memfd"
  https://lore.kernel.org/lkml/cover.1747264138.git.ackerleytng@google.com/

which is in turn based on the following series[2] from Fuad which implements
the initial support for guest_memfd to manage shared memory and allow it to
be mmap()'d into userspace:

  "[PATCH v12 00/18] KVM: Mapping guest_memfd backed memory at the host for software protected VMs"
  https://lore.kernel.org/kvm/20250611133330.1514028-1-tabba@google.com/

(One of the main goals of posting this series in it's current form is to
identify the common set of dependencies to enable in-place conversion
support for SEV-SNP, TDX, and pKVM, which have been coined "stage 2"
according to upstreaming plans discussed during guest_memfd bi-weekly calls
and summarized by David here[3] (Fuad's series[2] being "stage 1"),
so please feel free to chime in here if there's any feedback on whether
something like the above set of dependencies is a reasonable starting point
for "stage 2" and how best to handle setting up a common tree to track this
dependency.)


Overview
--------

Currently guest_memfd is only used by CoCo VMs to handle private memory, and
relies on hole-punching to free memory from guest_memfd when it is converted
to shared and re-allocated from normal/non-gmem memory that's been associated
with the memslot. This has some major downsides:

  1) for future use-cases like 1GB HugeTLB support in gmem, the ability to
     hole-punch pages after conversion is almost completely lost since
     truncation at sub-1GB granularities won't free the page, and truncation
     at 1GB or greater granularity will likely userspace to track free ranges
     and defer truncation until the entire range has been converted, which
     will often never happen for a particular 1GB range.

  2) for things like PCI passthrough, where normal/non-gmem memory is
     pinned, this quickly leads to doubled guest memory usage once the guest
     has converted most of its pages to private, but the previous allocated
     pages can't be hole-punched until being unmapped from IOMMU. While there
     are reasonable solutions for this like the RamDiscardManager proposed[4]
     for QEMU, in-place conversion handles this memory doubling problem
     essentially for free, and makes it easier to mix PCI passthrough of
     normal devices together with PCI passthrough of trusted devices (e.g.
     for SEV-TIO) where it's actually *private* memory that needs to be
     mapped into the IOMMU, and thus there's less clarity about what pages
     can/can't be freed/unmapped from IOMMU when pages are converted between
     shared/private.

  3) interfaces like mbind() which rely on virtual addresses to set NUMA
     affinities are not available for unmappable guest_memfd pages, requiring
     additional management interfaces to handle guest_memfd separately from
     normal memory.

  4) not being able to populate pages directly from userspace due to
     guest_memfd being unmappable, requiring the user of intermediate buffers
     which the kernel then copies into corresponding guest_memfd page.

Supporting in-place conversion, and allowing shared pages to be mmap() and
accessed by userspace similarly to normal/non-CoCo guests, addresses most of
these issues fairly naturally.

With the above-mentioned dependencies in place, only a fairly small set of
additional changes are needed to allow SEV-SNP and (hopefully) other CoCo
platforms to use guest_memfd in this manner, and that "small set" of
additional changes is what this series is meant to call out to consider for
potential inclusion into the common "stage 2" tree so that pKVM/TDX in-place
conversion can be similarly enabled with minimal additional changes needed
on top and so we can start looking at getting the related userspace APIs
finalized.


Some topics for discussion
--------------------------

1) Removal of preparation tracking from guest_memfd
   
   This is the most significant change in this series, since I know in
   the past there was a strong desire to have guest_memfd be aware of
   what has/hasn't been prepared rather than off-loading the knowledge
   to platform-specific code. While it was initially planned to maintain
   this preparedness-tracking in guest_memfd, there are some complexities
   it brings along in the context of in-place conversion and hugetlb
   enablement that I think make it worthwhile to revisit.
   
   A) it has unique locking requirements[5], since "preparation" needs to
      happen lazily to gain any benefit from lazy-acceptance/lazy-faulting
      of guest memory, and that generally ends up being at fault-time, but
      data structures to track "preparation" require locks to update the
      state, and reduce guest_memfd ability to handle concurrent faults
      from multiple vCPUs efficiently. While there are proposed locking
      schemes that could potentially handle this reasonably[5], getting rid
      of this tracking in guest_memfd allows for things like shared/private
      state to be tracked via much simpler schemes like rw_semaphores (or
      just re-using the filemap invalidate lock as is done here).

   B) only SEV-SNP is actually making any meaningful use of it. Platforms
      like TDX handle preparation and preparation-tracking outside of
      guest_memfd, so operating under the general assumption that guest_memfd
      has a clear notion of what is/isn't prepared could bite us in some
      cases versus just punting to platform-specific tracking.


2) Proper point to begin generally advertising KVM_CAP_GMEM_CONVERSION?

   Currently the various dependencies these patches are based on top of
   advertise support for converting guest_memfd pages between shared/private
   via KVM_CAP_GMEM_CONVERSION. However, for SEV-SNP at least, these
   additional pages are needed. So perhaps the initial enablement for
   KVM_CAP_GMEM_CONVERSION should only be done for non-CoCo VMs to enable
   the self-tests so that userspace can reliably probe for support for a
   specific VM type?


Testing
-------

This series has only been tested with SEV-SNP guests using the following
modified QEMU branch:

  https://github.com/amdese/qemu/commits/snp-mmap-gmem0-wip4

and beyond that only via the kselftests added by Ackerley that exercise the
gmem conversion support/ioctls this series is based on.


TODO
----

 - Rebase on (or merge into?) proper "stage 2" once we work out what that is.
 - Confirm no breakages to Fuad's "stage 1" kselftests 
 - Add kselftest coverage for SNP guests using shareable gmem.


References
----------

[1] "[RFC PATCH v2 00/51] 1G page support for guest_memfd",
    https://lore.kernel.org/lkml/cover.1747264138.git.ackerleytng@google.com/
[2] "[PATCH v12 00/18] KVM: Mapping guest_memfd backed memory at the host for software protected VMs",
    https://lore.kernel.org/kvm/20250611133330.1514028-1-tabba@google.com/
[3] "[Overview] guest_memfd extensions and dependencies 2025-05-15",
    https://lore.kernel.org/kvm/c1c9591d-218a-495c-957b-ba356c8f8e09@redhat.com/
[4] "[PATCH v7 0/5] Enable shared device assignment"
    https://lore.kernel.org/kvm/20250612082747.51539-1-chenyi.qiang@intel.com/
[5] https://lore.kernel.org/kvm/20250529054227.hh2f4jmyqf6igd3i@amd.com/


Thanks!

-Mike


----------------------------------------------------------------
Michael Roth (5):
      KVM: guest_memfd: Remove preparation tracking
      KVM: guest_memfd: Only access KVM memory attributes when appropriate
      KVM: guest_memfd: Call arch invalidation hooks when converting to shared
      KVM: guest_memfd: Don't prepare shared folios
      KVM: SEV: Make SNP_LAUNCH_UPDATE ignore 'uaddr' if guest_memfd is shareable

 .../virt/kvm/x86/amd-memory-encryption.rst         |  4 +-
 arch/x86/kvm/svm/sev.c                             | 14 +++-
 virt/kvm/guest_memfd.c                             | 92 +++++++++++++---------
 3 files changed, 68 insertions(+), 42 deletions(-)

---

## [2] Michael Roth — 2025-06-12
*Subject: [PATCH RFC v1 1/5] KVM: guest_memfd: Remove preparation tracking*

guest_memfd currently uses the folio uptodate flag to track:

  1) whether or not a page had been cleared before initial usage
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
index 35f94a288e52..cc93c502b5d8 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -421,11 +421,6 @@ static int __kvm_gmem_prepare_folio(struct kvm *kvm, struct kvm_memory_slot *slo
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
@@ -435,13 +430,7 @@ static inline void kvm_gmem_mark_prepared(struct folio *folio)
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
@@ -459,11 +448,8 @@ static int kvm_gmem_prepare_folio(struct kvm *kvm, struct kvm_memory_slot *slot,
 	WARN_ON(!IS_ALIGNED(slot->gmem.pgoff, 1 << folio_order(folio)));
 	index = gfn - slot->base_gfn + slot->gmem.pgoff;
 	index = ALIGN_DOWN(index, 1 << folio_order(folio));
-	r = __kvm_gmem_prepare_folio(kvm, slot, index, folio);
-	if (!r)
-		kvm_gmem_mark_prepared(folio);
 
-	return r;
+	return __kvm_gmem_prepare_folio(kvm, slot, index, folio);
 }
 
 static int __kvm_gmem_filemap_add_folio(struct address_space *mapping,
@@ -808,7 +794,7 @@ static vm_fault_t kvm_gmem_fault_shared(struct vm_fault *vmf)
 
 	if (!folio_test_uptodate(folio)) {
 		clear_highpage(folio_page(folio, 0));
-		kvm_gmem_mark_prepared(folio);
+		folio_mark_uptodate(folio);
 	}
 
 	vmf->page = folio_file_page(folio, vmf->pgoff);
@@ -1306,7 +1292,7 @@ void kvm_gmem_unbind(struct kvm_memory_slot *slot)
 static struct folio *__kvm_gmem_get_pfn(struct file *file,
 					struct kvm_memory_slot *slot,
 					pgoff_t index, kvm_pfn_t *pfn,
-					bool *is_prepared, int *max_order)
+					int *max_order)
 {
 	struct file *gmem_file = READ_ONCE(slot->gmem.file);
 	struct kvm_gmem *gmem = file->private_data;
@@ -1337,7 +1323,6 @@ static struct folio *__kvm_gmem_get_pfn(struct file *file,
 	if (max_order)
 		*max_order = 0;
 
-	*is_prepared = folio_test_uptodate(folio);
 	return folio;
 }
 
@@ -1348,7 +1333,6 @@ int kvm_gmem_get_pfn(struct kvm *kvm, struct kvm_memory_slot *slot,
 	pgoff_t index = kvm_gmem_get_index(slot, gfn);
 	struct file *file = kvm_gmem_get_file(slot);
 	struct folio *folio;
-	bool is_prepared = false;
 	int r = 0;
 
 	if (!file)
@@ -1356,14 +1340,21 @@ int kvm_gmem_get_pfn(struct kvm *kvm, struct kvm_memory_slot *slot,
 
 	filemap_invalidate_lock_shared(file_inode(file)->i_mapping);
 
-	folio = __kvm_gmem_get_pfn(file, slot, index, pfn, &is_prepared, max_order);
+	folio = __kvm_gmem_get_pfn(file, slot, index, pfn, max_order);
 	if (IS_ERR(folio)) {
 		r = PTR_ERR(folio);
 		goto out;
 	}
 
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
 
@@ -1420,7 +1411,6 @@ long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long
 		struct folio *folio;
 		gfn_t gfn = start_gfn + i;
 		pgoff_t index = kvm_gmem_get_index(slot, gfn);
-		bool is_prepared = false;
 		kvm_pfn_t pfn;
 
 		if (signal_pending(current)) {
@@ -1428,19 +1418,12 @@ long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long
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
@@ -1457,7 +1440,7 @@ long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long
 		p = src ? src + i * PAGE_SIZE : NULL;
 		ret = post_populate(kvm, gfn, pfn, p, max_order, opaque);
 		if (!ret)
-			kvm_gmem_mark_prepared(folio);
+			folio_mark_uptodate(folio);
 
 put_folio_and_exit:
 		folio_put(folio);

---

## [3] Michael Roth — 2025-06-12
*Subject: [PATCH RFC v1 2/5] KVM: guest_memfd: Only access KVM memory attributes when appropriate*

When a memslot is configured with KVM_MEMSLOT_SUPPORTS_GMEM_SHARED, the
KVM MMU will not rely on KVM's memory attribute tracking to determine
whether a page is shared/private, but will instead call into guest_memfd
to obtain this information.

In the case of kvm_gmem_populate(), KVM's memory attributes are used to
determine the max order for pages that will be used for the guest's
initial memory payload, but this information will not be valid if
KVM_MEMSLOT_SUPPORTS_GMEM_SHARED is set, so update the handling to
account for this. Just hard-code the order to 0 for now since there
isn't yet hugepage support in guest_memfd.

Signed-off-by: Michael Roth <michael.roth@amd.com>
---
 virt/kvm/guest_memfd.c | 16 ++++++++++------
 1 file changed, 10 insertions(+), 6 deletions(-)

diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index cc93c502b5d8..b77cdccd340e 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -1429,12 +1429,16 @@ long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long
 			(npages - i) < (1 << max_order));
 
 		ret = -EINVAL;
-		while (!kvm_range_has_memory_attributes(kvm, gfn, gfn + (1 << max_order),
-							KVM_MEMORY_ATTRIBUTE_PRIVATE,
-							KVM_MEMORY_ATTRIBUTE_PRIVATE)) {
-			if (!max_order)
-				goto put_folio_and_exit;
-			max_order--;
+		if (!kvm_gmem_memslot_supports_shared(slot)) {
+			while (!kvm_range_has_memory_attributes(kvm, gfn, gfn + (1 << max_order),
+								KVM_MEMORY_ATTRIBUTE_PRIVATE,
+								KVM_MEMORY_ATTRIBUTE_PRIVATE)) {
+				if (!max_order)
+					goto put_folio_and_exit;
+				max_order--;
+			}
+		} else {
+			max_order = 0;
 		}
 
 		p = src ? src + i * PAGE_SIZE : NULL;

---

## [4] Michael Roth — 2025-06-12
*Subject: [PATCH RFC v1 3/5] KVM: guest_memfd: Call arch invalidation hooks when converting to shared*

When guest_memfd is used for both shared/private memory, converting
pages to shared may require kvm_arch_gmem_invalidate() to be issued to
return the pages to an architecturally-defined "shared" state if the
pages were previously allocated and transitioned to a private state via
kvm_arch_gmem_prepare().

Handle this by issuing the appropriate kvm_arch_gmem_invalidate() calls
when converting ranges in the filemap to a shared state.

Signed-off-by: Michael Roth <michael.roth@amd.com>
---
 virt/kvm/guest_memfd.c | 22 ++++++++++++++++++++++
 1 file changed, 22 insertions(+)

diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index b77cdccd340e..f27e1f3962bb 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -203,6 +203,28 @@ static int kvm_gmem_shareability_apply(struct inode *inode,
 	struct maple_tree *mt;
 
 	mt = &kvm_gmem_private(inode)->shareability;
+
+	/*
+	 * If a folio has been allocated then it was possibly in a private
+	 * state prior to conversion. Ensure arch invalidations are issued
+	 * to return the folio to a normal/shared state as defined by the
+	 * architecture before tracking it as shared in gmem.
+	 */
+	if (m == SHAREABILITY_ALL) {
+		pgoff_t idx;
+
+		for (idx = work->start; idx < work->start + work->nr_pages; idx++) {
+			struct folio *folio = filemap_lock_folio(inode->i_mapping, idx);
+
+			if (!IS_ERR(folio)) {
+				kvm_arch_gmem_invalidate(folio_pfn(folio),
+							 folio_pfn(folio) + folio_nr_pages(folio));
+				folio_unlock(folio);
+				folio_put(folio);
+			}
+		}
+	}
+
 	return kvm_gmem_shareability_store(mt, work->start, work->nr_pages, m);
 }

---

## [5] Michael Roth — 2025-06-12
*Subject: [PATCH RFC v1 4/5] KVM: guest_memfd: Don't prepare shared folios*

In the current guest_memfd logic, "preparation" is only used currently
to describe the additional work of putting a guest_memfd page into an
architecturally-defined "private" state, such as updating RMP table
entries for SEV-SNP guests. As such, there's no input to the
corresponding kvm_arch_gmem_prepare() hooks as to whether a page is
being prepared/accessed as shared or as private, so "preparation" will
end up being erroneously done on pages that were supposed to remain in a
shared state. Rather than plumb through the additional information
needed to distinguish between shared vs. private preparation, just
continue to only do preparation on private pages, as was the case prior
to support for GUEST_MEMFD_FLAG_SUPPORT_SHARED being introduced.

Signed-off-by: Michael Roth <michael.roth@amd.com>
---
 virt/kvm/guest_memfd.c | 3 ++-
 1 file changed, 2 insertions(+), 1 deletion(-)

diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index f27e1f3962bb..a912b00776f1 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -1376,7 +1376,8 @@ int kvm_gmem_get_pfn(struct kvm *kvm, struct kvm_memory_slot *slot,
 		folio_mark_uptodate(folio);
 	}
 
-	r = kvm_gmem_prepare_folio(kvm, slot, gfn, folio);
+	if (kvm_gmem_shareability_get(file_inode(file), index) == SHAREABILITY_GUEST)
+		r = kvm_gmem_prepare_folio(kvm, slot, gfn, folio);
 
 	folio_unlock(folio);

---

## [6] Michael Roth — 2025-06-12
*Subject: [PATCH RFC v1 5/5] KVM: SEV: Make SNP_LAUNCH_UPDATE ignore 'uaddr' if guest_memfd is shareable*

There is no need to copy in the data for initial guest memory payload
in the case of shareable gmem instances since userspace can just
initialize the contents directly. Ignore the 'uaddr' parameter in cases
where KVM_MEMSLOT_SUPPORTS_SHARED is set for the GPA's memslot.

Also incorporate similar expectations into kvm_gmem_populate() to avoid
dealing with potential issues where guest_memfd's shared fault handler
might trigger when issuing callbacks to populate pages and not know how
to deal the index being marked as private.

Signed-off-by: Michael Roth <michael.roth@amd.com>
---
 .../virt/kvm/x86/amd-memory-encryption.rst         |  4 +++-
 arch/x86/kvm/svm/sev.c                             | 14 ++++++++++----
 virt/kvm/guest_memfd.c                             |  8 ++++++++
 3 files changed, 21 insertions(+), 5 deletions(-)

diff --git a/Documentation/virt/kvm/x86/amd-memory-encryption.rst b/Documentation/virt/kvm/x86/amd-memory-encryption.rst
index 1ddb6a86ce7f..399b331a523f 100644
--- a/Documentation/virt/kvm/x86/amd-memory-encryption.rst
+++ b/Documentation/virt/kvm/x86/amd-memory-encryption.rst
@@ -513,7 +513,9 @@ calling this command until those fields indicate the entire range has been
 processed, e.g. ``len`` is 0, ``gfn_start`` is equal to the last GFN in the
 range plus 1, and ``uaddr`` is the last byte of the userspace-provided source
 buffer address plus 1. In the case where ``type`` is KVM_SEV_SNP_PAGE_TYPE_ZERO,
-``uaddr`` will be ignored completely.
+``uaddr`` will be ignored completely. If the guest_memfd instance backing the
+GFN range has the GUEST_MEMFD_FLAG_SUPPORT_SHARED flag set, then ``uaddr`` will
+be ignored for all KVM_SEV_SNP_PAGE_TYPE_*'s.
 
 Parameters (in): struct  kvm_sev_snp_launch_update
 
diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index ed85634eb2bd..6e4473e8db6d 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -2174,6 +2174,7 @@ struct sev_gmem_populate_args {
 	__u8 type;
 	int sev_fd;
 	int fw_error;
+	bool gmem_supports_shared;
 };
 
 static int sev_gmem_post_populate(struct kvm *kvm, gfn_t gfn_start, kvm_pfn_t pfn,
@@ -2185,7 +2186,8 @@ static int sev_gmem_post_populate(struct kvm *kvm, gfn_t gfn_start, kvm_pfn_t pf
 	int npages = (1 << order);
 	gfn_t gfn;
 
-	if (WARN_ON_ONCE(sev_populate_args->type != KVM_SEV_SNP_PAGE_TYPE_ZERO && !src))
+	if (WARN_ON_ONCE(sev_populate_args->type != KVM_SEV_SNP_PAGE_TYPE_ZERO &&
+			 !sev_populate_args->gmem_supports_shared && !src))
 		return -EINVAL;
 
 	for (gfn = gfn_start, i = 0; gfn < gfn_start + npages; gfn++, i++) {
@@ -2275,7 +2277,7 @@ static int snp_launch_update(struct kvm *kvm, struct kvm_sev_cmd *argp)
 	struct kvm_sev_snp_launch_update params;
 	struct kvm_memory_slot *memslot;
 	long npages, count;
-	void __user *src;
+	void __user *src = NULL;
 	int ret = 0;
 
 	if (!sev_snp_guest(kvm) || !sev->snp_context)
@@ -2326,7 +2328,10 @@ static int snp_launch_update(struct kvm *kvm, struct kvm_sev_cmd *argp)
 
 	sev_populate_args.sev_fd = argp->sev_fd;
 	sev_populate_args.type = params.type;
-	src = params.type == KVM_SEV_SNP_PAGE_TYPE_ZERO ? NULL : u64_to_user_ptr(params.uaddr);
+	sev_populate_args.gmem_supports_shared = kvm_gmem_memslot_supports_shared(memslot);
+
+	if (!kvm_gmem_memslot_supports_shared(memslot))
+		src = params.type == KVM_SEV_SNP_PAGE_TYPE_ZERO ? NULL : u64_to_user_ptr(params.uaddr);
 
 	count = kvm_gmem_populate(kvm, params.gfn_start, src, npages,
 				  sev_gmem_post_populate, &sev_populate_args);
@@ -2338,7 +2343,8 @@ static int snp_launch_update(struct kvm *kvm, struct kvm_sev_cmd *argp)
 	} else {
 		params.gfn_start += count;
 		params.len -= count * PAGE_SIZE;
-		if (params.type != KVM_SEV_SNP_PAGE_TYPE_ZERO)
+		if (!kvm_gmem_memslot_supports_shared(memslot) &&
+		    params.type != KVM_SEV_SNP_PAGE_TYPE_ZERO)
 			params.uaddr += count * PAGE_SIZE;
 
 		ret = 0;
diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index a912b00776f1..309455e44e96 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -1462,6 +1462,14 @@ long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long
 			}
 		} else {
 			max_order = 0;
+
+			/*
+			 * If shared memory is available, it is expected that
+			 * userspace will populate memory contents directly and
+			 * not provide an intermediate buffer to copy from.
+			 */
+			if (src)
+				return -EINVAL;
 		}
 
 		p = src ? src + i * PAGE_SIZE : NULL;

---

## [7] David Hildenbrand — 2025-06-13
*Subject: Re: [PATCH RFC v1 0/5] KVM: guest_memfd: Support in-place conversion
 for CoCo VMs*

On 13.06.25 02:53, Michael Roth wrote:
> This patchset is also available at:
> 

If nobody else volunteers, I can soon start maintaining a guest_memfd 
preview tree. I suspect a good starting point would be once stage-2 is 
posted separately.

---

## [8] Vishal Annapurve — 2025-07-15
*Subject: Re: [PATCH RFC v1 1/5] KVM: guest_memfd: Remove preparation tracking*

On Thu, Jun 12, 2025 at 5:55 PM Michael Roth <michael.roth@amd.com> wrote:
>
> guest_memfd currently uses the folio uptodate flag to track:

I believe this patch doesn't need to depend on stage1/stage2 and can
be sent directly for review on kvm tip, is that right?

This update paired with zeroing modifications[1] will make uptodate
flag redundant for guest_memfd memory.

[1] https://lore.kernel.org/lkml/CAGtprH-+gPN8J_RaEit=M_ErHWTmFHeCipC6viT6PHhG3ELg6A@mail.gmail.com/

---

## [9] Vishal Annapurve — 2025-07-15
*Subject: Re: [PATCH RFC v1 3/5] KVM: guest_memfd: Call arch invalidation hooks
 when converting to shared*

On Thu, Jun 12, 2025 at 5:56 PM Michael Roth <michael.roth@amd.com> wrote:
>
> When guest_memfd is used for both shared/private memory, converting

It is redundant to enter this loop for VM variants that don't need
this loop e.g. for pKVM/TDX. I think KVM can dictate a set of rules
(based on VM type) that guest_memfd will follow for memory management
when it's created, e.g. something like:
1) needs pfn invalidation
2) needs zeroing on shared faults
3) needs zeroing on allocation

> +                       struct folio *folio = filemap_lock_folio(inode->i_mapping, idx);
> +

---

## [10] Michael Roth — 2025-07-15
*Subject: Re: [PATCH RFC v1 3/5] KVM: guest_memfd: Call arch invalidation
 hooks when converting to shared*

On Tue, Jul 15, 2025 at 06:20:09AM -0700, Vishal Annapurve wrote:
> On Thu, Jun 12, 2025 at 5:56 PM Michael Roth <michael.roth@amd.com> wrote:
> >

Makes sense. Maybe internal/reserved GUEST_MEMFD_FLAG_*'s that can be passed
to kvm_gmem_create()?

-Mike

> 
> > +                       struct folio *folio = filemap_lock_folio(inode->i_mapping, idx);

---

## [11] Michael Roth — 2025-07-15
*Subject: Re: [PATCH RFC v1 1/5] KVM: guest_memfd: Remove preparation tracking*

On Tue, Jul 15, 2025 at 05:47:31AM -0700, Vishal Annapurve wrote:
> On Thu, Jun 12, 2025 at 5:55 PM Michael Roth <michael.roth@amd.com> wrote:
> >

Yes, this was actually tested initially against kvm/next and should not
cause issues. I wanted to post the change in the context of in-place
conversion/hugetlb work to help motivate why we're considering the
change, but ideally we'd get this one applied soon-ish since the question
of "how to track preparation state" seems to be throwing a wrench into all
the planning activities and at the end of the day only SNP is making use
of it so it seems to be becoming more trouble than it's worth at a
fairly fast pace.

-Mike

> 
> This update paired with zeroing modifications[1] will make uptodate

---

## [12] Vishal Annapurve — 2025-07-16
*Subject: Re: [PATCH RFC v1 3/5] KVM: guest_memfd: Call arch invalidation hooks
 when converting to shared*

On Tue, Jul 15, 2025 at 3:56 PM Michael Roth <michael.roth@amd.com> wrote:
> > > diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
> > > index b77cdccd340e..f27e1f3962bb 100644

Yeah, a set of internal flags in addition to what is passed by user
space looks good to me. i.e. Something like:

-int kvm_gmem_create(struct kvm *kvm, struct kvm_create_guest_memfd *args)
+int kvm_gmem_create(struct kvm *kvm, struct kvm_create_guest_memfd
*args, u64 kvm_flags)

>
> -Mike

---

## [13] Ackerley Tng — 2025-08-25
*Subject: Re: [PATCH RFC v1 1/5] KVM: guest_memfd: Remove preparation tracking*

Michael Roth <michael.roth@amd.com> writes:

> guest_memfd currently uses the folio uptodate flag to track:
>

While working on HugeTLB support for guest_memfd, I added a test that
tries to map a non-huge-page-aligned gmem.pgoff to a huge-page aligned
gfn.

I understand that config would destroy the performance advantages of
huge pages, but I think the test is necessary since Yan brought up the
use case here [1].

The conclusion in that thread, I believe, was to allow binding of
unaligned GFNs to offsets, but disallow large pages in that case. The
next series for guest_memfd HugeTLB support will include a fix similar
to this [2].

While testing, I hit this WARN_ON with a non-huge-page-aligned
gmem.pgoff.

>  	WARN_ON(!IS_ALIGNED(slot->gmem.pgoff, 1 << folio_order(folio)));

Do you all think this WARN_ON can be removed?

Also, do you think kvm_gmem_prepare_folio()s interface should perhaps be
changed to take pfn, gfn, nr_pages (PAGE_SIZE pages) and level?

I think taking a folio is kind of awkward since we're not really setting
up the folio, we're setting up something mapping-related for the
folio. Also, kvm_gmem_invalidate() doesn't take folios, which is more
aligned with invalidating mappings rather than something folio-related.

[1] https://lore.kernel.org/all/aA7UXI0NB7oQQrL2@yzhao56-desk.sh.intel.com/
[2] https://github.com/googleprodkernel/linux-cc/commit/371ed9281e0c9ba41cfdc20b48a6c5566f61a7df

>  	index = gfn - slot->base_gfn + slot->gmem.pgoff;
>  	index = ALIGN_DOWN(index, 1 << folio_order(folio));

---

## [14] Michael Roth — 2025-09-16
*Subject: Re: [PATCH RFC v1 1/5] KVM: guest_memfd: Remove preparation tracking*

On Mon, Aug 25, 2025 at 04:08:19PM -0700, Ackerley Tng wrote:
> Michael Roth <michael.roth@amd.com> writes:
> 

I think so.. I actually ended up dropping this WARN_ON() for a similar
reason:

  https://github.com/AMDESE/linux/commit/c654cd144ad0d823f4db8793ebf9b43a3e8a7c48

but in that case it was to deal with memslots where most of the GPA
ranges are huge-page aligned to the gmemfd, and it's just that the start/end
GPA ranges have been split up and associated with other memslots. In that case
I still try to allow hugepages but force order 0 in kvm_gmem_get_pfn()
for the start/end ranges.

I haven't really considered the case where entire GPA range is misaligned
with gmemfd hugepage offsets but the proposed handling seems reasonable
to me... I need to take a closer look at whether the above-mentioned
logic is at odds with what is/will be implemented in
kvm_alloc_memslot_metadata() however as that seems a bit more restrictive.

Thanks,

Mike

> 
> Also, do you think kvm_gmem_prepare_folio()s interface should perhaps be

---

## [15] Ackerley Tng — 2025-09-18
*Subject: Re: [PATCH RFC v1 1/5] KVM: guest_memfd: Remove preparation tracking*

Michael Roth <michael.roth@amd.com> writes:

> On Mon, Aug 25, 2025 at 04:08:19PM -0700, Ackerley Tng wrote:
>> Michael Roth <michael.roth@amd.com> writes:

Thanks for confirming!

>   https://github.com/AMDESE/linux/commit/c654cd144ad0d823f4db8793ebf9b43a3e8a7c48
>

Does this help? [1] (from a WIP patch series).

KVM already checks that the guest base address (base_gfn) and the
userspace virtual address (userspace_addr) are aligned relative to each
other for each large page level. If they are not, large pages are
disabled for the entire memory slot.

[1] extends that same check for slot->base_gfn and
slot->gmem.pgoff. Hence, guest_memfd is letting KVM manage the
mapping. guest_memfd reports max_order based on what it knows (folio
size, and folio size is also determined by shareability), and KVM
manages the mapping after taking account lpage_info in addition to
max_order.

[1] https://github.com/googleprodkernel/linux-cc/commit/371ed9281e0c9ba41cfdc20b48a6c5566f61a7df

> Thanks,
>

---

## [16] Ackerley Tng — 2025-09-18
*Subject: Re: [PATCH RFC v1 1/5] KVM: guest_memfd: Remove preparation tracking*

Ackerley Tng <ackerleytng@google.com> writes:

> Michael Roth <michael.roth@amd.com> writes:
>

Dropping this WARN_ON() actually further highlights the importance of
separating preparedness from folio flags (and the folio).

With huge pages being supported in guest_memfd, it's possible for just
part of a folio to be mapped into the stage 2 page tables. One example
of this is if userspace were to request populating just 2M in a 1G
page. If preparedness were recorded in folio flags, then the entire 1G
would be considered prepared even though only 2M of that page was
prepared (updated in RMP tables).

So I do support making the uptodate flag only mean zeroed, and taking
preparedness out of the picture.

With this change, kvm_gmem_prepare_folio() and
__kvm_gmem_prepare_folio() seems to be a misnomer, since conceptually
we're not preparing a folio, we can't assume that we're always preparing
a whole folio once huge pages are in the picture.

What do you all think of taking this even further? Instead of keeping
kvm_gmem_prepare_folio() within guest_memfd, what if we

1. Focus on preparing pfn ranges (retaining kvm_arch_gmem_prepare() is
   good) and not folios
   
2. More clearly and directly associate preparing pfns with mapping
   (rather than with getting a folio to be mapped) into stage 2 page
   tables

What I have in mind for (2) is to update kvm_tdp_mmu_map() to do an
arch-specific call, when fault->is_private, to call
kvm_arch_gmem_prepare() just before mapping the pfns and when the
mapping level is known.

The cleanup counterpart would then be to call kvm_arch_gmem_invalidate()
somewhere in tdp_mmu_zap_leafs().

kvm_arch_gmem_prepare() and kvm_arch_gmem_invalidate() would then drop
out of guest_memfd and be moved back into the core of KVM.

Technically these two functions don't even need to have gmem in the name
since any memory can be prepared in the SNP sense, though for the
foreseeable future gmem is the only memory supported for private memory
in CoCo VMs.

Also, to push this along a little, I feel that this series does a few
things. What do you all think of re-focusing this series (or a part of
this series) as "Separating SNP preparation from guest_memfd" or
"Separating arch-specific preparation from guest_memfd"?

>> 
>> [...snip...]

---

## [17] Ackerley Tng — 2025-09-18
*Subject: Re: [PATCH RFC v1 1/5] KVM: guest_memfd: Remove preparation tracking*

Ackerley Tng <ackerleytng@google.com> writes:

> Ackerley Tng <ackerleytng@google.com> writes:
>

Thought about this a little more and maybe this is not quite accurate
either. On a conversion, for SNP, does the memory actually need to be
unmapped from the NPTs, or would it be possible to just flip the C bit?

If conversion only involves flipping the C bit and updating RMP tables,
then perhaps preparation and invalidation shouldn't be associated with
mapping, but directly with conversions, or setting page private/shared
state.


> What I have in mind for (2) is to update kvm_tdp_mmu_map() to do an
> arch-specific call, when fault->is_private, to call

---

## [18] Yan Zhao — 2025-11-07
*Subject: Re: [PATCH RFC v1 1/5] KVM: guest_memfd: Remove preparation tracking*

Hi Michael,
Have you posted a newer version of this patch?

I also have a question about this patch:

Suppose there's a 2MB huge folio A, where
A1 and A2 are 4KB pages belonging to folio A.

(1) kvm_gmem_populate() invokes __kvm_gmem_get_pfn() and gets folio A.
    It adds page A1 and invokes folio_mark_uptodate() on folio A.

(2) kvm_gmem_get_pfn() later faults in page A2.
    As folio A is uptodate, clear_highpage() is not invoked on page A2.
    kvm_gmem_prepare_folio() is invoked on the whole folio A.

(2) could occur at least in TDX when only a part the 2MB page is added as guest
initial memory.

My questions:
- Would (2) occur on SEV?
- If it does, is the lack of clear_highpage() on A2 a problem ?
- Is invoking gmem_prepare on page A1 a problem?

Thanks
Yan

On Thu, Jun 12, 2025 at 07:53:56PM -0500, Michael Roth wrote:
> guest_memfd currently uses the folio uptodate flag to track:
>

---
