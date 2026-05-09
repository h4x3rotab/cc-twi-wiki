---
title: 'Add NUMA mempolicy support for KVM guest-memfd'
date: 2025-08-27
last_reply: 2025-12-09
message_count: 39
participants: ['Shivank Garg', 'Ackerley Tng', 'David Hildenbrand', 'Kalra, Ashish', 'Sean Christopherson', 'Fuad Tabba', 'Jason Gunthorpe', 'Gregory Price', 'patchwork-bot+f2fs@kernel.org']
---

## [1] Shivank Garg — 2025-08-27

This series introduces NUMA-aware memory placement support for KVM guests
with guest_memfd memory backends. It builds upon Fuad Tabba's work (V17)
that enabled host-mapping for guest_memfd memory [1] and can be applied
directly applied on KVM tree [2] (branch kvm-next, base commit: a6ad5413,
Merge branch 'guest-memfd-mmap' into HEAD)

== Background == 
KVM's guest-memfd memory backend currently lacks support for NUMA policy
enforcement, causing guest memory allocations to be distributed across host
nodes  according to kernel's default behavior, irrespective of any policy
specified by the VMM. This limitation arises because conventional userspace
NUMA control mechanisms like mbind(2) don't work since the memory isn't
directly mapped to userspace when allocations occur.
Fuad's work [1] provides the necessary mmap capability, and this series
leverages it to enable mbind(2).

== Implementation ==
This series implements proper NUMA policy support for guest-memfd by:

1. Adding mempolicy-aware allocation APIs to the filemap layer.
2. Introducing custom inodes (via a dedicated slab-allocated inode cache,
   kvm_gmem_inode_info) to store NUMA policy and metadata for guest memory.
3. Implementing get/set_policy vm_ops in guest_memfd to support NUMA
   policy.

With these changes, VMMs can now control guest memory placement by mapping
guest_memfd file descriptor and using mbind(2) to specify:
- Policy modes: default, bind, interleave, or preferred
- Host NUMA nodes: List of target nodes for memory allocation

These Policies affect only future allocations and do not migrate existing
memory. This matches mbind(2)'s default behavior which affects only new
allocations unless overridden with MPOL_MF_MOVE/MPOL_MF_MOVE_ALL flags (Not
supported for guest_memfd as it is unmovable by design).

== Upstream Plan ==
Phased approach as per David's guest_memfd extension overview [3] and
community calls [4]:

Phase 1 (this series):
1. Focuses on shared guest_memfd support (non-CoCo VMs).
2. Builds on Fuad's host-mapping work [1].

Phase2 (future work):
1. NUMA support for private guest_memfd (CoCo VMs).
2. Depends on SNP in-place conversion support [5].

This series provides a clean integration path for NUMA-aware memory
management for guest_memfd and lays the groundwork for future confidential
computing NUMA capabilities.

Thanks,
Shivank

== Changelog ==

- v1,v2: Extended the KVM_CREATE_GUEST_MEMFD IOCTL to pass mempolicy.
- v3: Introduced fbind() syscall for VMM memory-placement configuration.
- v4-v6: Current approach using shared_policy support and vm_ops (based on
         suggestions from David [6] and guest_memfd bi-weekly upstream
         call discussion [7]).
- v7: Use inodes to store NUMA policy instead of file [8].
- v8: Rebase on top of Fuad's V12: Host mmaping for guest_memfd memory.
- v9: Rebase on top of Fuad's V13 and incorporate review comments
- V10: Rebase on top of Fuad's V17. Use latest guest_memfd inode patch
       from Ackerley (with David's review comments). Use newer kmem_cache_create()
       API variant with arg parameter (Vlastimil)
- V11: Rebase on kvm-next, remove RFC tag, use Ackerley's latest patch
       and fix a rcu race bug during kvm module unload.

[1] https://lore.kernel.org/all/20250729225455.670324-1-seanjc@google.com
[2] https://git.kernel.org/pub/scm/virt/kvm/kvm.git/log/?h=next 
[3] https://lore.kernel.org/all/c1c9591d-218a-495c-957b-ba356c8f8e09@redhat.com
[4] https://docs.google.com/document/d/1M6766BzdY1Lhk7LiR5IqVR8B8mG3cr-cxTxOrAosPOk/edit?tab=t.0#heading=h.svcbod20b5ur
[5] https://lore.kernel.org/all/20250613005400.3694904-1-michael.roth@amd.com
[6] https://lore.kernel.org/all/6fbef654-36e2-4be5-906e-2a648a845278@redhat.com
[7] https://lore.kernel.org/all/2b77e055-98ac-43a1-a7ad-9f9065d7f38f@amd.com
[8] https://lore.kernel.org/all/diqzbjumm167.fsf@ackerleytng-ctop.c.googlers.com

Ackerley Tng (1):
  KVM: guest_memfd: Use guest mem inodes instead of anonymous inodes

Matthew Wilcox (Oracle) (2):
  mm/filemap: Add NUMA mempolicy support to filemap_alloc_folio()
  mm/filemap: Extend __filemap_get_folio() to support NUMA memory
    policies

Shivank Garg (4):
  mm/mempolicy: Export memory policy symbols
  KVM: guest_memfd: Add slab-allocated inode cache
  KVM: guest_memfd: Enforce NUMA mempolicy using shared policy
  KVM: guest_memfd: selftests: Add tests for mmap and NUMA policy
    support

 fs/bcachefs/fs-io-buffered.c                  |   2 +-
 fs/btrfs/compression.c                        |   4 +-
 fs/btrfs/verity.c                             |   2 +-
 fs/erofs/zdata.c                              |   2 +-
 fs/f2fs/compress.c                            |   2 +-
 include/linux/pagemap.h                       |  18 +-
 include/uapi/linux/magic.h                    |   1 +
 mm/filemap.c                                  |  23 +-
 mm/mempolicy.c                                |   6 +
 mm/readahead.c                                |   2 +-
 tools/testing/selftests/kvm/Makefile.kvm      |   1 +
 .../testing/selftests/kvm/guest_memfd_test.c  | 121 ++++++++
 virt/kvm/guest_memfd.c                        | 262 ++++++++++++++++--
 virt/kvm/kvm_main.c                           |   7 +-
 virt/kvm/kvm_mm.h                             |   9 +-
 15 files changed, 412 insertions(+), 50 deletions(-)

---

## [2] Shivank Garg — 2025-08-27
*Subject: [PATCH kvm-next V11 1/7] mm/filemap: Add NUMA mempolicy support to filemap_alloc_folio()*

From: "Matthew Wilcox (Oracle)" <willy@infradead.org>

Add a mempolicy parameter to filemap_alloc_folio() to enable NUMA-aware
page cache allocations. This will be used by upcoming changes to
support NUMA policies in guest-memfd, where guest_memory need to be
allocated NUMA policy specified by VMM.

All existing users pass NULL maintaining current behavior.

Reviewed-by: Pankaj Gupta <pankaj.gupta@amd.com>
Reviewed-by: Vlastimil Babka <vbabka@suse.cz>
Signed-off-by: Matthew Wilcox (Oracle) <willy@infradead.org>
Reviewed-by: David Hildenbrand <david@redhat.com>
Signed-off-by: Shivank Garg <shivankg@amd.com>
---
 fs/bcachefs/fs-io-buffered.c |  2 +-
 fs/btrfs/compression.c       |  4 ++--
 fs/btrfs/verity.c            |  2 +-
 fs/erofs/zdata.c             |  2 +-
 fs/f2fs/compress.c           |  2 +-
 include/linux/pagemap.h      |  8 +++++---
 mm/filemap.c                 | 14 +++++++++-----
 mm/readahead.c               |  2 +-
 8 files changed, 21 insertions(+), 15 deletions(-)

diff --git a/fs/bcachefs/fs-io-buffered.c b/fs/bcachefs/fs-io-buffered.c
index 1c54b9b5bd69..3af2eabb7ed3 100644
--- a/fs/bcachefs/fs-io-buffered.c
+++ b/fs/bcachefs/fs-io-buffered.c
@@ -124,7 +124,7 @@ static int readpage_bio_extend(struct btree_trans *trans,
 			if (folio && !xa_is_value(folio))
 				break;
 
-			folio = filemap_alloc_folio(readahead_gfp_mask(iter->mapping), order);
+			folio = filemap_alloc_folio(readahead_gfp_mask(iter->mapping), order, NULL);
 			if (!folio)
 				break;
 
diff --git a/fs/btrfs/compression.c b/fs/btrfs/compression.c
index d09d622016ef..139f9609e737 100644
--- a/fs/btrfs/compression.c
+++ b/fs/btrfs/compression.c
@@ -474,8 +474,8 @@ static noinline int add_ra_bio_pages(struct inode *inode,
 			continue;
 		}
 
-		folio = filemap_alloc_folio(mapping_gfp_constraint(mapping,
-								   ~__GFP_FS), 0);
+		folio = filemap_alloc_folio(mapping_gfp_constraint(mapping, ~__GFP_FS),
+					    0, NULL);
 		if (!folio)
 			break;
 
diff --git a/fs/btrfs/verity.c b/fs/btrfs/verity.c
index b7a96a005487..c43a789ba6d2 100644
--- a/fs/btrfs/verity.c
+++ b/fs/btrfs/verity.c
@@ -742,7 +742,7 @@ static struct page *btrfs_read_merkle_tree_page(struct inode *inode,
 	}
 
 	folio = filemap_alloc_folio(mapping_gfp_constraint(inode->i_mapping, ~__GFP_FS),
-				    0);
+				    0, NULL);
 	if (!folio)
 		return ERR_PTR(-ENOMEM);
 
diff --git a/fs/erofs/zdata.c b/fs/erofs/zdata.c
index 2d73297003d2..e9a1bf7568c9 100644
--- a/fs/erofs/zdata.c
+++ b/fs/erofs/zdata.c
@@ -562,7 +562,7 @@ static void z_erofs_bind_cache(struct z_erofs_frontend *fe)
 			 * Allocate a managed folio for cached I/O, or it may be
 			 * then filled with a file-backed folio for in-place I/O
 			 */
-			newfolio = filemap_alloc_folio(gfp, 0);
+			newfolio = filemap_alloc_folio(gfp, 0, NULL);
 			if (!newfolio)
 				continue;
 			newfolio->private = Z_EROFS_PREALLOCATED_FOLIO;
diff --git a/fs/f2fs/compress.c b/fs/f2fs/compress.c
index 5c1f47e45dab..56a51c9ba4f1 100644
--- a/fs/f2fs/compress.c
+++ b/fs/f2fs/compress.c
@@ -1942,7 +1942,7 @@ static void f2fs_cache_compressed_page(struct f2fs_sb_info *sbi,
 		return;
 	}
 
-	cfolio = filemap_alloc_folio(__GFP_NOWARN | __GFP_IO, 0);
+	cfolio = filemap_alloc_folio(__GFP_NOWARN | __GFP_IO, 0, NULL);
 	if (!cfolio)
 		return;
 
diff --git a/include/linux/pagemap.h b/include/linux/pagemap.h
index 12a12dae727d..ce617a35dc35 100644
--- a/include/linux/pagemap.h
+++ b/include/linux/pagemap.h
@@ -646,9 +646,11 @@ static inline void *detach_page_private(struct page *page)
 }
 
 #ifdef CONFIG_NUMA
-struct folio *filemap_alloc_folio_noprof(gfp_t gfp, unsigned int order);
+struct folio *filemap_alloc_folio_noprof(gfp_t gfp, unsigned int order,
+		struct mempolicy *policy);
 #else
-static inline struct folio *filemap_alloc_folio_noprof(gfp_t gfp, unsigned int order)
+static inline struct folio *filemap_alloc_folio_noprof(gfp_t gfp, unsigned int order,
+		struct mempolicy *policy)
 {
 	return folio_alloc_noprof(gfp, order);
 }
@@ -659,7 +661,7 @@ static inline struct folio *filemap_alloc_folio_noprof(gfp_t gfp, unsigned int o
 
 static inline struct page *__page_cache_alloc(gfp_t gfp)
 {
-	return &filemap_alloc_folio(gfp, 0)->page;
+	return &filemap_alloc_folio(gfp, 0, NULL)->page;
 }
 
 static inline gfp_t readahead_gfp_mask(struct address_space *x)
diff --git a/mm/filemap.c b/mm/filemap.c
index 751838ef05e5..495f7f5c3d2e 100644
--- a/mm/filemap.c
+++ b/mm/filemap.c
@@ -989,11 +989,16 @@ int filemap_add_folio(struct address_space *mapping, struct folio *folio,
 EXPORT_SYMBOL_GPL(filemap_add_folio);
 
 #ifdef CONFIG_NUMA
-struct folio *filemap_alloc_folio_noprof(gfp_t gfp, unsigned int order)
+struct folio *filemap_alloc_folio_noprof(gfp_t gfp, unsigned int order,
+		struct mempolicy *policy)
 {
 	int n;
 	struct folio *folio;
 
+	if (policy)
+		return folio_alloc_mpol_noprof(gfp, order, policy,
+				NO_INTERLEAVE_INDEX, numa_node_id());
+
 	if (cpuset_do_page_mem_spread()) {
 		unsigned int cpuset_mems_cookie;
 		do {
@@ -1978,7 +1983,7 @@ struct folio *__filemap_get_folio(struct address_space *mapping, pgoff_t index,
 			err = -ENOMEM;
 			if (order > min_order)
 				alloc_gfp |= __GFP_NORETRY | __GFP_NOWARN;
-			folio = filemap_alloc_folio(alloc_gfp, order);
+			folio = filemap_alloc_folio(alloc_gfp, order, NULL);
 			if (!folio)
 				continue;
 
@@ -2517,7 +2522,7 @@ static int filemap_create_folio(struct kiocb *iocb, struct folio_batch *fbatch)
 	if (iocb->ki_flags & (IOCB_NOWAIT | IOCB_WAITQ))
 		return -EAGAIN;
 
-	folio = filemap_alloc_folio(mapping_gfp_mask(mapping), min_order);
+	folio = filemap_alloc_folio(mapping_gfp_mask(mapping), min_order, NULL);
 	if (!folio)
 		return -ENOMEM;
 	if (iocb->ki_flags & IOCB_DONTCACHE)
@@ -3916,8 +3921,7 @@ static struct folio *do_read_cache_folio(struct address_space *mapping,
 repeat:
 	folio = filemap_get_folio(mapping, index);
 	if (IS_ERR(folio)) {
-		folio = filemap_alloc_folio(gfp,
-					    mapping_min_folio_order(mapping));
+		folio = filemap_alloc_folio(gfp, mapping_min_folio_order(mapping), NULL);
 		if (!folio)
 			return ERR_PTR(-ENOMEM);
 		index = mapping_align_index(mapping, index);
diff --git a/mm/readahead.c b/mm/readahead.c
index 406756d34309..a4dfa837dfbd 100644
--- a/mm/readahead.c
+++ b/mm/readahead.c
@@ -183,7 +183,7 @@ static struct folio *ractl_alloc_folio(struct readahead_control *ractl,
 {
 	struct folio *folio;
 
-	folio = filemap_alloc_folio(gfp_mask, order);
+	folio = filemap_alloc_folio(gfp_mask, order, NULL);
 	if (folio && ractl->dropbehind)
 		__folio_set_dropbehind(folio);

---

## [3] Shivank Garg — 2025-08-27
*Subject: [PATCH kvm-next V11 2/7] mm/filemap: Extend __filemap_get_folio() to support NUMA memory policies*

From: "Matthew Wilcox (Oracle)" <willy@infradead.org>

Extend __filemap_get_folio() to support NUMA memory policies by
renaming the implementation to __filemap_get_folio_mpol() and adding
a mempolicy parameter. The original function becomes a static inline
wrapper that passes NULL for the mempolicy.

This infrastructure will enable future support for NUMA-aware page cache
allocations in guest_memfd memory backend KVM guests.

Reviewed-by: Pankaj Gupta <pankaj.gupta@amd.com>
Reviewed-by: Vlastimil Babka <vbabka@suse.cz>
Signed-off-by: Matthew Wilcox (Oracle) <willy@infradead.org>
Reviewed-by: David Hildenbrand <david@redhat.com>
Signed-off-by: Shivank Garg <shivankg@amd.com>
---
 include/linux/pagemap.h | 10 ++++++++--
 mm/filemap.c            | 11 ++++++-----
 2 files changed, 14 insertions(+), 7 deletions(-)

diff --git a/include/linux/pagemap.h b/include/linux/pagemap.h
index ce617a35dc35..94d65ced0a1d 100644
--- a/include/linux/pagemap.h
+++ b/include/linux/pagemap.h
@@ -747,11 +747,17 @@ static inline fgf_t fgf_set_order(size_t size)
 }
 
 void *filemap_get_entry(struct address_space *mapping, pgoff_t index);
-struct folio *__filemap_get_folio(struct address_space *mapping, pgoff_t index,
-		fgf_t fgp_flags, gfp_t gfp);
+struct folio *__filemap_get_folio_mpol(struct address_space *mapping,
+		pgoff_t index, fgf_t fgf_flags, gfp_t gfp, struct mempolicy *policy);
 struct page *pagecache_get_page(struct address_space *mapping, pgoff_t index,
 		fgf_t fgp_flags, gfp_t gfp);
 
+static inline struct folio *__filemap_get_folio(struct address_space *mapping,
+		pgoff_t index, fgf_t fgf_flags, gfp_t gfp)
+{
+	return __filemap_get_folio_mpol(mapping, index, fgf_flags, gfp, NULL);
+}
+
 /**
  * write_begin_get_folio - Get folio for write_begin with flags.
  * @iocb: The kiocb passed from write_begin (may be NULL).
diff --git a/mm/filemap.c b/mm/filemap.c
index 495f7f5c3d2e..03f223be575c 100644
--- a/mm/filemap.c
+++ b/mm/filemap.c
@@ -1897,11 +1897,12 @@ void *filemap_get_entry(struct address_space *mapping, pgoff_t index)
 }
 
 /**
- * __filemap_get_folio - Find and get a reference to a folio.
+ * __filemap_get_folio_mpol - Find and get a reference to a folio.
  * @mapping: The address_space to search.
  * @index: The page index.
  * @fgp_flags: %FGP flags modify how the folio is returned.
  * @gfp: Memory allocation flags to use if %FGP_CREAT is specified.
+ * @policy: NUMA memory allocation policy to follow.
  *
  * Looks up the page cache entry at @mapping & @index.
  *
@@ -1912,8 +1913,8 @@ void *filemap_get_entry(struct address_space *mapping, pgoff_t index)
  *
  * Return: The found folio or an ERR_PTR() otherwise.
  */
-struct folio *__filemap_get_folio(struct address_space *mapping, pgoff_t index,
-		fgf_t fgp_flags, gfp_t gfp)
+struct folio *__filemap_get_folio_mpol(struct address_space *mapping,
+		pgoff_t index, fgf_t fgp_flags, gfp_t gfp, struct mempolicy *policy)
 {
 	struct folio *folio;
 
@@ -1983,7 +1984,7 @@ struct folio *__filemap_get_folio(struct address_space *mapping, pgoff_t index,
 			err = -ENOMEM;
 			if (order > min_order)
 				alloc_gfp |= __GFP_NORETRY | __GFP_NOWARN;
-			folio = filemap_alloc_folio(alloc_gfp, order, NULL);
+			folio = filemap_alloc_folio(alloc_gfp, order, policy);
 			if (!folio)
 				continue;
 
@@ -2030,7 +2031,7 @@ struct folio *__filemap_get_folio(struct address_space *mapping, pgoff_t index,
 		folio_clear_dropbehind(folio);
 	return folio;
 }
-EXPORT_SYMBOL(__filemap_get_folio);
+EXPORT_SYMBOL(__filemap_get_folio_mpol);
 
 static inline struct folio *find_get_entry(struct xa_state *xas, pgoff_t max,
 		xa_mark_t mark)

---

## [4] Shivank Garg — 2025-08-27
*Subject: [PATCH kvm-next V11 3/7] mm/mempolicy: Export memory policy symbols*

KVM guest_memfd wants to implement support for NUMA policies just like
shmem already does using the shared policy infrastructure. As
guest_memfd currently resides in KVM module code, we have to export the
relevant symbols.

In the future, guest_memfd might be moved to core-mm, at which point the
symbols no longer would have to be exported. When/if that happens is
still unclear.

Acked-by: David Hildenbrand <david@redhat.com>
Acked-by: Vlastimil Babka <vbabka@suse.cz>
Signed-off-by: Shivank Garg <shivankg@amd.com>
---
 mm/mempolicy.c | 6 ++++++
 1 file changed, 6 insertions(+)

diff --git a/mm/mempolicy.c b/mm/mempolicy.c
index eb83cff7db8c..3d797d47a040 100644
--- a/mm/mempolicy.c
+++ b/mm/mempolicy.c
@@ -354,6 +354,7 @@ struct mempolicy *get_task_policy(struct task_struct *p)
 
 	return &default_policy;
 }
+EXPORT_SYMBOL_FOR_MODULES(get_task_policy, "kvm");
 
 static const struct mempolicy_operations {
 	int (*create)(struct mempolicy *pol, const nodemask_t *nodes);
@@ -487,6 +488,7 @@ void __mpol_put(struct mempolicy *pol)
 		return;
 	kmem_cache_free(policy_cache, pol);
 }
+EXPORT_SYMBOL_FOR_MODULES(__mpol_put, "kvm");
 
 static void mpol_rebind_default(struct mempolicy *pol, const nodemask_t *nodes)
 {
@@ -2885,6 +2887,7 @@ struct mempolicy *mpol_shared_policy_lookup(struct shared_policy *sp,
 	read_unlock(&sp->lock);
 	return pol;
 }
+EXPORT_SYMBOL_FOR_MODULES(mpol_shared_policy_lookup, "kvm");
 
 static void sp_free(struct sp_node *n)
 {
@@ -3170,6 +3173,7 @@ void mpol_shared_policy_init(struct shared_policy *sp, struct mempolicy *mpol)
 		mpol_put(mpol);	/* drop our incoming ref on sb mpol */
 	}
 }
+EXPORT_SYMBOL_FOR_MODULES(mpol_shared_policy_init, "kvm");
 
 int mpol_set_shared_policy(struct shared_policy *sp,
 			struct vm_area_struct *vma, struct mempolicy *pol)
@@ -3188,6 +3192,7 @@ int mpol_set_shared_policy(struct shared_policy *sp,
 		sp_free(new);
 	return err;
 }
+EXPORT_SYMBOL_FOR_MODULES(mpol_set_shared_policy, "kvm");
 
 /* Free a backing policy store on inode delete. */
 void mpol_free_shared_policy(struct shared_policy *sp)
@@ -3206,6 +3211,7 @@ void mpol_free_shared_policy(struct shared_policy *sp)
 	}
 	write_unlock(&sp->lock);
 }
+EXPORT_SYMBOL_FOR_MODULES(mpol_free_shared_policy, "kvm");
 
 #ifdef CONFIG_NUMA_BALANCING
 static int __initdata numabalancing_override;

---

## [5] Shivank Garg — 2025-08-27
*Subject: [PATCH kvm-next V11 4/7] KVM: guest_memfd: Use guest mem inodes instead of anonymous inodes*

From: Ackerley Tng <ackerleytng@google.com>

guest_memfd's inode represents memory the guest_memfd is
providing. guest_memfd's file represents a struct kvm's view of that
memory.

Using a custom inode allows customization of the inode teardown
process via callbacks. For example, ->evict_inode() allows
customization of the truncation process on file close, and
->destroy_inode() and ->free_inode() allow customization of the inode
freeing process.

Customizing the truncation process allows flexibility in management of
guest_memfd memory and customization of the inode freeing process
allows proper cleanup of memory metadata stored on the inode.

Memory metadata is more appropriately stored on the inode (as opposed
to the file), since the metadata is for the memory and is not unique
to a specific binding and struct kvm.

Acked-by: David Hildenbrand <david@redhat.com>
Co-developed-by: Fuad Tabba <tabba@google.com>
Signed-off-by: Fuad Tabba <tabba@google.com>
Signed-off-by: Ackerley Tng <ackerleytng@google.com>
Signed-off-by: Shivank Garg <shivankg@amd.com>
---
 include/uapi/linux/magic.h |   1 +
 virt/kvm/guest_memfd.c     | 129 ++++++++++++++++++++++++++++++-------
 virt/kvm/kvm_main.c        |   7 +-
 virt/kvm/kvm_mm.h          |   9 +--
 4 files changed, 119 insertions(+), 27 deletions(-)

diff --git a/include/uapi/linux/magic.h b/include/uapi/linux/magic.h
index bb575f3ab45e..638ca21b7a90 100644
--- a/include/uapi/linux/magic.h
+++ b/include/uapi/linux/magic.h
@@ -103,5 +103,6 @@
 #define DEVMEM_MAGIC		0x454d444d	/* "DMEM" */
 #define SECRETMEM_MAGIC		0x5345434d	/* "SECM" */
 #define PID_FS_MAGIC		0x50494446	/* "PIDF" */
+#define GUEST_MEMFD_MAGIC	0x474d454d	/* "GMEM" */
 
 #endif /* __LINUX_MAGIC_H__ */
diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index 08a6bc7d25b6..6c66a0974055 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -1,12 +1,16 @@
 // SPDX-License-Identifier: GPL-2.0
+#include <linux/anon_inodes.h>
 #include <linux/backing-dev.h>
 #include <linux/falloc.h>
+#include <linux/fs.h>
 #include <linux/kvm_host.h>
+#include <linux/pseudo_fs.h>
 #include <linux/pagemap.h>
-#include <linux/anon_inodes.h>
 
 #include "kvm_mm.h"
 
+static struct vfsmount *kvm_gmem_mnt;
+
 struct kvm_gmem {
 	struct kvm *kvm;
 	struct xarray bindings;
@@ -385,9 +389,45 @@ static struct file_operations kvm_gmem_fops = {
 	.fallocate	= kvm_gmem_fallocate,
 };
 
-void kvm_gmem_init(struct module *module)
+static int kvm_gmem_init_fs_context(struct fs_context *fc)
+{
+	if (!init_pseudo(fc, GUEST_MEMFD_MAGIC))
+		return -ENOMEM;
+
+	fc->s_iflags |= SB_I_NOEXEC;
+	fc->s_iflags |= SB_I_NODEV;
+
+	return 0;
+}
+
+static struct file_system_type kvm_gmem_fs = {
+	.name		 = "guest_memfd",
+	.init_fs_context = kvm_gmem_init_fs_context,
+	.kill_sb	 = kill_anon_super,
+};
+
+static int kvm_gmem_init_mount(void)
+{
+	kvm_gmem_mnt = kern_mount(&kvm_gmem_fs);
+
+	if (IS_ERR(kvm_gmem_mnt))
+		return PTR_ERR(kvm_gmem_mnt);
+
+	kvm_gmem_mnt->mnt_flags |= MNT_NOEXEC;
+	return 0;
+}
+
+int kvm_gmem_init(struct module *module)
 {
 	kvm_gmem_fops.owner = module;
+
+	return kvm_gmem_init_mount();
+}
+
+void kvm_gmem_exit(void)
+{
+	kern_unmount(kvm_gmem_mnt);
+	kvm_gmem_mnt = NULL;
 }
 
 static int kvm_gmem_migrate_folio(struct address_space *mapping,
@@ -463,11 +503,72 @@ bool __weak kvm_arch_supports_gmem_mmap(struct kvm *kvm)
 	return true;
 }
 
+static struct inode *kvm_gmem_inode_make_secure_inode(const char *name,
+						      loff_t size, u64 flags)
+{
+	struct inode *inode;
+
+	inode = anon_inode_make_secure_inode(kvm_gmem_mnt->mnt_sb, name, NULL);
+	if (IS_ERR(inode))
+		return inode;
+
+	inode->i_private = (void *)(unsigned long)flags;
+	inode->i_op = &kvm_gmem_iops;
+	inode->i_mapping->a_ops = &kvm_gmem_aops;
+	inode->i_mode |= S_IFREG;
+	inode->i_size = size;
+	mapping_set_gfp_mask(inode->i_mapping, GFP_HIGHUSER);
+	mapping_set_inaccessible(inode->i_mapping);
+	/* Unmovable mappings are supposed to be marked unevictable as well. */
+	WARN_ON_ONCE(!mapping_unevictable(inode->i_mapping));
+
+	return inode;
+}
+
+static struct file *kvm_gmem_inode_create_getfile(void *priv, loff_t size,
+						  u64 flags)
+{
+	static const char *name = "[kvm-gmem]";
+	struct inode *inode;
+	struct file *file;
+	int err;
+
+	err = -ENOENT;
+	/* __fput() will take care of fops_put(). */
+	if (!fops_get(&kvm_gmem_fops))
+		goto err;
+
+	inode = kvm_gmem_inode_make_secure_inode(name, size, flags);
+	if (IS_ERR(inode)) {
+		err = PTR_ERR(inode);
+		goto err_fops_put;
+	}
+
+	file = alloc_file_pseudo(inode, kvm_gmem_mnt, name, O_RDWR,
+				 &kvm_gmem_fops);
+	if (IS_ERR(file)) {
+		err = PTR_ERR(file);
+		goto err_put_inode;
+	}
+
+	file->f_flags |= O_LARGEFILE;
+	file->private_data = priv;
+
+out:
+	return file;
+
+err_put_inode:
+	iput(inode);
+err_fops_put:
+	fops_put(&kvm_gmem_fops);
+err:
+	file = ERR_PTR(err);
+	goto out;
+}
+
 static int __kvm_gmem_create(struct kvm *kvm, loff_t size, u64 flags)
 {
-	const char *anon_name = "[kvm-gmem]";
 	struct kvm_gmem *gmem;
-	struct inode *inode;
 	struct file *file;
 	int fd, err;
 
@@ -481,32 +582,16 @@ static int __kvm_gmem_create(struct kvm *kvm, loff_t size, u64 flags)
 		goto err_fd;
 	}
 
-	file = anon_inode_create_getfile(anon_name, &kvm_gmem_fops, gmem,
-					 O_RDWR, NULL);
+	file = kvm_gmem_inode_create_getfile(gmem, size, flags);
 	if (IS_ERR(file)) {
 		err = PTR_ERR(file);
 		goto err_gmem;
 	}
 
-	file->f_flags |= O_LARGEFILE;
-
-	inode = file->f_inode;
-	WARN_ON(file->f_mapping != inode->i_mapping);
-
-	inode->i_private = (void *)(unsigned long)flags;
-	inode->i_op = &kvm_gmem_iops;
-	inode->i_mapping->a_ops = &kvm_gmem_aops;
-	inode->i_mode |= S_IFREG;
-	inode->i_size = size;
-	mapping_set_gfp_mask(inode->i_mapping, GFP_HIGHUSER);
-	mapping_set_inaccessible(inode->i_mapping);
-	/* Unmovable mappings are supposed to be marked unevictable as well. */
-	WARN_ON_ONCE(!mapping_unevictable(inode->i_mapping));
-
 	kvm_get_kvm(kvm);
 	gmem->kvm = kvm;
 	xa_init(&gmem->bindings);
-	list_add(&gmem->entry, &inode->i_mapping->i_private_list);
+	list_add(&gmem->entry, &file_inode(file)->i_mapping->i_private_list);
 
 	fd_install(fd, file);
 	return fd;
diff --git a/virt/kvm/kvm_main.c b/virt/kvm/kvm_main.c
index 18f29ef93543..301d48d6e00d 100644
--- a/virt/kvm/kvm_main.c
+++ b/virt/kvm/kvm_main.c
@@ -6489,7 +6489,9 @@ int kvm_init(unsigned vcpu_size, unsigned vcpu_align, struct module *module)
 	if (WARN_ON_ONCE(r))
 		goto err_vfio;
 
-	kvm_gmem_init(module);
+	r = kvm_gmem_init(module);
+	if (r)
+		goto err_gmem;
 
 	r = kvm_init_virtualization();
 	if (r)
@@ -6510,6 +6512,8 @@ int kvm_init(unsigned vcpu_size, unsigned vcpu_align, struct module *module)
 err_register:
 	kvm_uninit_virtualization();
 err_virt:
+	kvm_gmem_exit();
+err_gmem:
 	kvm_vfio_ops_exit();
 err_vfio:
 	kvm_async_pf_deinit();
@@ -6541,6 +6545,7 @@ void kvm_exit(void)
 	for_each_possible_cpu(cpu)
 		free_cpumask_var(per_cpu(cpu_kick_mask, cpu));
 	kmem_cache_destroy(kvm_vcpu_cache);
+	kvm_gmem_exit();
 	kvm_vfio_ops_exit();
 	kvm_async_pf_deinit();
 	kvm_irqfd_exit();
diff --git a/virt/kvm/kvm_mm.h b/virt/kvm/kvm_mm.h
index 31defb08ccba..9fcc5d5b7f8d 100644
--- a/virt/kvm/kvm_mm.h
+++ b/virt/kvm/kvm_mm.h
@@ -68,17 +68,18 @@ static inline void gfn_to_pfn_cache_invalidate_start(struct kvm *kvm,
 #endif /* HAVE_KVM_PFNCACHE */
 
 #ifdef CONFIG_KVM_GUEST_MEMFD
-void kvm_gmem_init(struct module *module);
+int kvm_gmem_init(struct module *module);
+void kvm_gmem_exit(void);
 int kvm_gmem_create(struct kvm *kvm, struct kvm_create_guest_memfd *args);
 int kvm_gmem_bind(struct kvm *kvm, struct kvm_memory_slot *slot,
 		  unsigned int fd, loff_t offset);
 void kvm_gmem_unbind(struct kvm_memory_slot *slot);
 #else
-static inline void kvm_gmem_init(struct module *module)
+static inline int kvm_gmem_init(struct module *module)
 {
-
+	return 0;
 }
-
+static inline void kvm_gmem_exit(void) {};
 static inline int kvm_gmem_bind(struct kvm *kvm,
 					 struct kvm_memory_slot *slot,
 					 unsigned int fd, loff_t offset)

---

## [6] Shivank Garg — 2025-08-27
*Subject: [PATCH kvm-next V11 5/7] KVM: guest_memfd: Add slab-allocated inode cache*

Add dedicated inode structure (kvm_gmem_inode_info) and slab-allocated
inode cache for guest memory backing, similar to how shmem handles inodes.

This adds the necessary allocation/destruction functions and prepares
for upcoming guest_memfd NUMA policy support changes.

Signed-off-by: Shivank Garg <shivankg@amd.com>
---
 virt/kvm/guest_memfd.c | 70 ++++++++++++++++++++++++++++++++++++++++--
 1 file changed, 68 insertions(+), 2 deletions(-)

diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index 6c66a0974055..356947d36a47 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -17,6 +17,15 @@ struct kvm_gmem {
 	struct list_head entry;
 };
 
+struct kvm_gmem_inode_info {
+	struct inode vfs_inode;
+};
+
+static inline struct kvm_gmem_inode_info *KVM_GMEM_I(struct inode *inode)
+{
+	return container_of(inode, struct kvm_gmem_inode_info, vfs_inode);
+}
+
 /**
  * folio_file_pfn - like folio_file_page, but return a pfn.
  * @folio: The folio which contains this index.
@@ -389,13 +398,46 @@ static struct file_operations kvm_gmem_fops = {
 	.fallocate	= kvm_gmem_fallocate,
 };
 
+static struct kmem_cache *kvm_gmem_inode_cachep;
+
+static struct inode *kvm_gmem_alloc_inode(struct super_block *sb)
+{
+	struct kvm_gmem_inode_info *info;
+
+	info = alloc_inode_sb(sb, kvm_gmem_inode_cachep, GFP_KERNEL);
+	if (!info)
+		return NULL;
+
+	return &info->vfs_inode;
+}
+
+static void kvm_gmem_destroy_inode(struct inode *inode)
+{
+}
+
+static void kvm_gmem_free_inode(struct inode *inode)
+{
+	kmem_cache_free(kvm_gmem_inode_cachep, KVM_GMEM_I(inode));
+}
+
+static const struct super_operations kvm_gmem_super_operations = {
+	.statfs		= simple_statfs,
+	.alloc_inode	= kvm_gmem_alloc_inode,
+	.destroy_inode	= kvm_gmem_destroy_inode,
+	.free_inode	= kvm_gmem_free_inode,
+};
+
 static int kvm_gmem_init_fs_context(struct fs_context *fc)
 {
+	struct pseudo_fs_context *ctx;
+
 	if (!init_pseudo(fc, GUEST_MEMFD_MAGIC))
 		return -ENOMEM;
 
 	fc->s_iflags |= SB_I_NOEXEC;
 	fc->s_iflags |= SB_I_NODEV;
+	ctx = fc->fs_private;
+	ctx->ops = &kvm_gmem_super_operations;
 
 	return 0;
 }
@@ -417,17 +459,41 @@ static int kvm_gmem_init_mount(void)
 	return 0;
 }
 
+static void kvm_gmem_init_inode(void *foo)
+{
+	struct kvm_gmem_inode_info *info = foo;
+
+	inode_init_once(&info->vfs_inode);
+}
+
 int kvm_gmem_init(struct module *module)
 {
-	kvm_gmem_fops.owner = module;
+	int ret;
+	struct kmem_cache_args args = {
+		.align = 0,
+		.ctor = kvm_gmem_init_inode,
+	};
 
-	return kvm_gmem_init_mount();
+	kvm_gmem_fops.owner = module;
+	kvm_gmem_inode_cachep = kmem_cache_create("kvm_gmem_inode_cache",
+						  sizeof(struct kvm_gmem_inode_info),
+						  &args, SLAB_ACCOUNT);
+	if (!kvm_gmem_inode_cachep)
+		return -ENOMEM;
+	ret = kvm_gmem_init_mount();
+	if (ret) {
+		kmem_cache_destroy(kvm_gmem_inode_cachep);
+		return ret;
+	}
+	return 0;
 }
 
 void kvm_gmem_exit(void)
 {
 	kern_unmount(kvm_gmem_mnt);
 	kvm_gmem_mnt = NULL;
+	rcu_barrier();
+	kmem_cache_destroy(kvm_gmem_inode_cachep);
 }
 
 static int kvm_gmem_migrate_folio(struct address_space *mapping,

---

## [7] Shivank Garg — 2025-08-27
*Subject: [PATCH kvm-next V11 6/7] KVM: guest_memfd: Enforce NUMA mempolicy using shared policy*

Previously, guest-memfd allocations followed local NUMA node id in absence
of process mempolicy, resulting in arbitrary memory allocation.
Moreover, mbind() couldn't be used  by the VMM as guest memory wasn't
mapped into userspace when allocation occurred.

Enable NUMA policy support by implementing vm_ops for guest-memfd mmap
operation. This allows the VMM to map the memory and use mbind() to set the
desired NUMA policy. The policy is stored in the inode structure via
kvm_gmem_inode_info, as memory policy is a property of the memory (struct
inode) itself. The policy is then retrieved via mpol_shared_policy_lookup()
and passed to filemap_grab_folio_mpol() to ensure that allocations follow
the specified memory policy.

This enables the VMM to control guest memory NUMA placement by calling
mbind() on the mapped memory regions, providing fine-grained control over
guest memory allocation across NUMA nodes.

The policy change only affect future allocations and does not migrate
existing memory. This matches mbind(2)'s default behavior which affects
only new allocations unless overridden with MPOL_MF_MOVE/MPOL_MF_MOVE_ALL
flags, which are not supported for guest_memfd as it is unmovable.

Suggested-by: David Hildenbrand <david@redhat.com>
Acked-by: David Hildenbrand <david@redhat.com>
Acked-by: Vlastimil Babka <vbabka@suse.cz>
Signed-off-by: Shivank Garg <shivankg@amd.com>
---
 virt/kvm/guest_memfd.c | 67 ++++++++++++++++++++++++++++++++++++++++--
 1 file changed, 65 insertions(+), 2 deletions(-)

diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index 356947d36a47..85edc597bb9f 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -4,6 +4,7 @@
 #include <linux/falloc.h>
 #include <linux/fs.h>
 #include <linux/kvm_host.h>
+#include <linux/mempolicy.h>
 #include <linux/pseudo_fs.h>
 #include <linux/pagemap.h>
 
@@ -18,6 +19,7 @@ struct kvm_gmem {
 };
 
 struct kvm_gmem_inode_info {
+	struct shared_policy policy;
 	struct inode vfs_inode;
 };
 
@@ -26,6 +28,9 @@ static inline struct kvm_gmem_inode_info *KVM_GMEM_I(struct inode *inode)
 	return container_of(inode, struct kvm_gmem_inode_info, vfs_inode);
 }
 
+static struct mempolicy *kvm_gmem_get_pgoff_policy(struct kvm_gmem_inode_info *info,
+						   pgoff_t index);
+
 /**
  * folio_file_pfn - like folio_file_page, but return a pfn.
  * @folio: The folio which contains this index.
@@ -112,7 +117,25 @@ static int kvm_gmem_prepare_folio(struct kvm *kvm, struct kvm_memory_slot *slot,
 static struct folio *kvm_gmem_get_folio(struct inode *inode, pgoff_t index)
 {
 	/* TODO: Support huge pages. */
-	return filemap_grab_folio(inode->i_mapping, index);
+	struct mempolicy *policy;
+	struct folio *folio;
+
+	/*
+	 * Fast-path: See if folio is already present in mapping to avoid
+	 * policy_lookup.
+	 */
+	folio = __filemap_get_folio(inode->i_mapping, index,
+				    FGP_LOCK | FGP_ACCESSED, 0);
+	if (!IS_ERR(folio))
+		return folio;
+
+	policy = kvm_gmem_get_pgoff_policy(KVM_GMEM_I(inode), index);
+	folio = __filemap_get_folio_mpol(inode->i_mapping, index,
+					 FGP_LOCK | FGP_ACCESSED | FGP_CREAT,
+					 mapping_gfp_mask(inode->i_mapping), policy);
+	mpol_cond_put(policy);
+
+	return folio;
 }
 
 static void kvm_gmem_invalidate_begin(struct kvm_gmem *gmem, pgoff_t start,
@@ -372,8 +395,45 @@ static vm_fault_t kvm_gmem_fault_user_mapping(struct vm_fault *vmf)
 	return ret;
 }
 
+#ifdef CONFIG_NUMA
+static int kvm_gmem_set_policy(struct vm_area_struct *vma, struct mempolicy *mpol)
+{
+	struct inode *inode = file_inode(vma->vm_file);
+
+	return mpol_set_shared_policy(&KVM_GMEM_I(inode)->policy, vma, mpol);
+}
+
+static struct mempolicy *kvm_gmem_get_policy(struct vm_area_struct *vma,
+					     unsigned long addr, pgoff_t *pgoff)
+{
+	struct inode *inode = file_inode(vma->vm_file);
+
+	*pgoff = vma->vm_pgoff + ((addr - vma->vm_start) >> PAGE_SHIFT);
+	return mpol_shared_policy_lookup(&KVM_GMEM_I(inode)->policy, *pgoff);
+}
+
+static struct mempolicy *kvm_gmem_get_pgoff_policy(struct kvm_gmem_inode_info *info,
+						   pgoff_t index)
+{
+	struct mempolicy *mpol;
+
+	mpol = mpol_shared_policy_lookup(&info->policy, index);
+	return mpol ? mpol : get_task_policy(current);
+}
+#else
+static struct mempolicy *kvm_gmem_get_pgoff_policy(struct kvm_gmem_inode_info *info,
+						   pgoff_t index)
+{
+	return NULL;
+}
+#endif /* CONFIG_NUMA */
+
 static const struct vm_operations_struct kvm_gmem_vm_ops = {
-	.fault = kvm_gmem_fault_user_mapping,
+	.fault		= kvm_gmem_fault_user_mapping,
+#ifdef CONFIG_NUMA
+	.get_policy	= kvm_gmem_get_policy,
+	.set_policy	= kvm_gmem_set_policy,
+#endif
 };
 
 static int kvm_gmem_mmap(struct file *file, struct vm_area_struct *vma)
@@ -408,11 +468,14 @@ static struct inode *kvm_gmem_alloc_inode(struct super_block *sb)
 	if (!info)
 		return NULL;
 
+	mpol_shared_policy_init(&info->policy, NULL);
+
 	return &info->vfs_inode;
 }
 
 static void kvm_gmem_destroy_inode(struct inode *inode)
 {
+	mpol_free_shared_policy(&KVM_GMEM_I(inode)->policy);
 }
 
 static void kvm_gmem_free_inode(struct inode *inode)

---

## [8] Shivank Garg — 2025-08-27
*Subject: [PATCH kvm-next V11 7/7] KVM: guest_memfd: selftests: Add tests for mmap and NUMA policy support*

Add tests for NUMA memory policy binding and NUMA aware allocation in
guest_memfd. This extends the existing selftests by adding proper
validation for:
- KVM GMEM set_policy and get_policy() vm_ops functionality using
  mbind() and get_mempolicy()
- NUMA policy application before and after memory allocation

These tests help ensure NUMA support for guest_memfd works correctly.

Signed-off-by: Shivank Garg <shivankg@amd.com>
---
 tools/testing/selftests/kvm/Makefile.kvm      |   1 +
 .../testing/selftests/kvm/guest_memfd_test.c  | 121 ++++++++++++++++++
 2 files changed, 122 insertions(+)

diff --git a/tools/testing/selftests/kvm/Makefile.kvm b/tools/testing/selftests/kvm/Makefile.kvm
index 90f03f00cb04..c46cef2a7cd7 100644
--- a/tools/testing/selftests/kvm/Makefile.kvm
+++ b/tools/testing/selftests/kvm/Makefile.kvm
@@ -275,6 +275,7 @@ pgste-option = $(call try-run, echo 'int main(void) { return 0; }' | \
 	$(CC) -Werror -Wl$(comma)--s390-pgste -x c - -o "$$TMP",-Wl$(comma)--s390-pgste)
 
 LDLIBS += -ldl
+LDLIBS += -lnuma
 LDFLAGS += -pthread $(no-pie-option) $(pgste-option)
 
 LIBKVM_C := $(filter %.c,$(LIBKVM))
diff --git a/tools/testing/selftests/kvm/guest_memfd_test.c b/tools/testing/selftests/kvm/guest_memfd_test.c
index b3ca6737f304..9640d04ec293 100644
--- a/tools/testing/selftests/kvm/guest_memfd_test.c
+++ b/tools/testing/selftests/kvm/guest_memfd_test.c
@@ -7,6 +7,8 @@
 #include <stdlib.h>
 #include <string.h>
 #include <unistd.h>
+#include <numa.h>
+#include <numaif.h>
 #include <errno.h>
 #include <stdio.h>
 #include <fcntl.h>
@@ -19,6 +21,7 @@
 #include <sys/mman.h>
 #include <sys/types.h>
 #include <sys/stat.h>
+#include <sys/syscall.h>
 
 #include "kvm_util.h"
 #include "test_util.h"
@@ -72,6 +75,122 @@ static void test_mmap_supported(int fd, size_t page_size, size_t total_size)
 	TEST_ASSERT(!ret, "munmap() should succeed.");
 }
 
+#define TEST_REQUIRE_NUMA_MULTIPLE_NODES()	\
+	TEST_REQUIRE(numa_available() != -1 && numa_max_node() >= 1)
+
+static void test_mbind(int fd, size_t page_size, size_t total_size)
+{
+	unsigned long nodemask = 1; /* nid: 0 */
+	unsigned long maxnode = 8;
+	unsigned long get_nodemask;
+	int get_policy;
+	char *mem;
+	int ret;
+
+	TEST_REQUIRE_NUMA_MULTIPLE_NODES();
+
+	mem = mmap(NULL, total_size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
+	TEST_ASSERT(mem != MAP_FAILED, "mmap for mbind test should succeed");
+
+	/* Test MPOL_INTERLEAVE policy */
+	ret = syscall(__NR_mbind, mem, page_size * 2, MPOL_INTERLEAVE,
+		      &nodemask, maxnode, 0);
+	TEST_ASSERT(!ret, "mbind with INTERLEAVE to node 0 should succeed");
+	ret = syscall(__NR_get_mempolicy, &get_policy, &get_nodemask,
+		      maxnode, mem, MPOL_F_ADDR);
+	TEST_ASSERT(!ret && get_policy == MPOL_INTERLEAVE && get_nodemask == nodemask,
+		    "Policy should be MPOL_INTERLEAVE and nodes match");
+
+	/* Test basic MPOL_BIND policy */
+	ret = syscall(__NR_mbind, mem + page_size * 2, page_size * 2, MPOL_BIND,
+		      &nodemask, maxnode, 0);
+	TEST_ASSERT(!ret, "mbind with MPOL_BIND to node 0 should succeed");
+	ret = syscall(__NR_get_mempolicy, &get_policy, &get_nodemask,
+		      maxnode, mem + page_size * 2, MPOL_F_ADDR);
+	TEST_ASSERT(!ret && get_policy == MPOL_BIND && get_nodemask == nodemask,
+		    "Policy should be MPOL_BIND and nodes match");
+
+	/* Test MPOL_DEFAULT policy */
+	ret = syscall(__NR_mbind, mem, total_size, MPOL_DEFAULT, NULL, 0, 0);
+	TEST_ASSERT(!ret, "mbind with MPOL_DEFAULT should succeed");
+	ret = syscall(__NR_get_mempolicy, &get_policy, &get_nodemask,
+		      maxnode, mem, MPOL_F_ADDR);
+	TEST_ASSERT(!ret && get_policy == MPOL_DEFAULT && get_nodemask == 0,
+		    "Policy should be MPOL_DEFAULT and nodes zero");
+
+	/* Test with invalid policy */
+	ret = syscall(__NR_mbind, mem, page_size, 999, &nodemask, maxnode, 0);
+	TEST_ASSERT(ret == -1 && errno == EINVAL,
+		    "mbind with invalid policy should fail with EINVAL");
+
+	TEST_ASSERT(munmap(mem, total_size) == 0, "munmap should succeed");
+}
+
+static void test_numa_allocation(int fd, size_t page_size, size_t total_size)
+{
+	unsigned long node0_mask = 1;  /* Node 0 */
+	unsigned long node1_mask = 2;  /* Node 1 */
+	unsigned long maxnode = 8;
+	void *pages[4];
+	int status[4];
+	char *mem;
+	int ret, i;
+
+	TEST_REQUIRE_NUMA_MULTIPLE_NODES();
+
+	/* Clean slate: deallocate all file space, if any */
+	ret = fallocate(fd, FALLOC_FL_PUNCH_HOLE | FALLOC_FL_KEEP_SIZE, 0, total_size);
+	TEST_ASSERT(!ret, "fallocate(PUNCH_HOLE) should succeed");
+
+	mem = mmap(NULL, total_size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
+	TEST_ASSERT(mem != MAP_FAILED, "mmap should succeed");
+
+	for (i = 0; i < 4; i++)
+		pages[i] = (char *)mem + page_size * i;
+
+	/* Set NUMA policy after allocation */
+	memset(mem, 0xaa, page_size);
+	ret = syscall(__NR_mbind, pages[0], page_size, MPOL_BIND, &node0_mask, maxnode, 0);
+	TEST_ASSERT(!ret, "mbind after allocation page 0 to node 0 should succeed");
+	ret = fallocate(fd, FALLOC_FL_PUNCH_HOLE | FALLOC_FL_KEEP_SIZE, 0, page_size);
+	TEST_ASSERT(!ret, "fallocate(PUNCH_HOLE) should succeed");
+
+	/* Set NUMA policy before allocation */
+	ret = syscall(__NR_mbind, pages[0], page_size * 2, MPOL_BIND, &node1_mask, maxnode, 0);
+	TEST_ASSERT(!ret, "mbind page 0, 1 to node 1 should succeed");
+	ret = syscall(__NR_mbind, pages[2], page_size * 2, MPOL_BIND, &node0_mask, maxnode, 0);
+	TEST_ASSERT(!ret, "mbind page 2, 3 to node 0 should succeed");
+	memset(mem, 0xaa, total_size);
+
+	/* Validate if pages are allocated on specified NUMA nodes */
+	ret = syscall(__NR_move_pages, 0, 4, pages, NULL, status, 0);
+	TEST_ASSERT(ret >= 0, "move_pages should succeed for status check");
+	TEST_ASSERT(status[0] == 1, "Page 0 should be allocated on node 1");
+	TEST_ASSERT(status[1] == 1, "Page 1 should be allocated on node 1");
+	TEST_ASSERT(status[2] == 0, "Page 2 should be allocated on node 0");
+	TEST_ASSERT(status[3] == 0, "Page 3 should be allocated on node 0");
+
+	/* Punch hole for all pages */
+	ret = fallocate(fd, FALLOC_FL_PUNCH_HOLE | FALLOC_FL_KEEP_SIZE, 0, total_size);
+	TEST_ASSERT(!ret, "fallocate(PUNCH_HOLE) should succeed");
+
+	/* Change NUMA policy nodes and reallocate */
+	ret = syscall(__NR_mbind, pages[0], page_size * 2, MPOL_BIND, &node0_mask, maxnode, 0);
+	TEST_ASSERT(!ret, "mbind page 0, 1 to node 0 should succeed");
+	ret = syscall(__NR_mbind, pages[2], page_size * 2, MPOL_BIND, &node1_mask, maxnode, 0);
+	TEST_ASSERT(!ret, "mbind page 2, 3 to node 1 should succeed");
+	memset(mem, 0xaa, total_size);
+
+	ret = syscall(__NR_move_pages, 0, 4, pages, NULL, status, 0);
+	TEST_ASSERT(ret >= 0, "move_pages should succeed after reallocation");
+	TEST_ASSERT(status[0] == 0, "Page 0 should be allocated on node 0");
+	TEST_ASSERT(status[1] == 0, "Page 1 should be allocated on node 0");
+	TEST_ASSERT(status[2] == 1, "Page 2 should be allocated on node 1");
+	TEST_ASSERT(status[3] == 1, "Page 3 should be allocated on node 1");
+
+	TEST_ASSERT(munmap(mem, total_size) == 0, "munmap should succeed");
+}
+
 static sigjmp_buf jmpbuf;
 void fault_sigbus_handler(int signum)
 {
@@ -286,6 +405,8 @@ static void test_guest_memfd(unsigned long vm_type)
 	if (flags & GUEST_MEMFD_FLAG_MMAP) {
 		test_mmap_supported(fd, page_size, total_size);
 		test_fault_overflow(fd, page_size, total_size);
+		test_mbind(fd, page_size, total_size);
+		test_numa_allocation(fd, page_size, total_size);
 	} else {
 		test_mmap_not_supported(fd, page_size, total_size);
 	}

---

## [9] Ackerley Tng — 2025-08-27
*Subject: Re: [PATCH kvm-next V11 4/7] KVM: guest_memfd: Use guest mem inodes
 instead of anonymous inodes*

Shivank Garg <shivankg@amd.com> writes:

> 
> [...snip...]

I meant to send this to you before this version went out but you were
too quick!

Here's a new version, Fuad and I reviewed this again internally. The
changes are:

+ Sort linux/pseudo_fs.h after linux/pagemap.h (alphabetical)
+ Don't set MNT_NOEXEC on the mount, since SB_I_NOEXEC was already set
  on the superblock
+ Rename kvm_gmem_inode_make_secure_inode() to kvm_gmem_inode_create()
    + Emphasizes that there is a creation in this function
    + Remove "secure" from the function name to remove confusion that
      there may be a "non-secure" version
+ In kvm_gmem_inode_create_getfile()'s error path, return ERR_PTR(err)
  directly instead of having a goto


From ada9814b216eac129ed44dffd3acf76fce2cc08a Mon Sep 17 00:00:00 2001
From: Ackerley Tng <ackerleytng@google.com>
Date: Sun, 13 Jul 2025 17:43:35 +0000
Subject: [PATCH] KVM: guest_memfd: Use guest mem inodes instead of anonymous
 inodes

guest_memfd's inode represents memory the guest_memfd is
providing. guest_memfd's file represents a struct kvm's view of that
memory.

Using a custom inode allows customization of the inode teardown
process via callbacks. For example, ->evict_inode() allows
customization of the truncation process on file close, and
->destroy_inode() and ->free_inode() allow customization of the inode
freeing process.

Customizing the truncation process allows flexibility in management of
guest_memfd memory and customization of the inode freeing process
allows proper cleanup of memory metadata stored on the inode.

Memory metadata is more appropriately stored on the inode (as opposed
to the file), since the metadata is for the memory and is not unique
to a specific binding and struct kvm.

Co-developed-by: Fuad Tabba <tabba@google.com>
Signed-off-by: Fuad Tabba <tabba@google.com>
Signed-off-by: Shivank Garg <shivankg@amd.com>
Signed-off-by: Ackerley Tng <ackerleytng@google.com>
---
 include/uapi/linux/magic.h |   1 +
 virt/kvm/guest_memfd.c     | 126 ++++++++++++++++++++++++++++++-------
 virt/kvm/kvm_main.c        |   7 ++-
 virt/kvm/kvm_mm.h          |   9 +--
 4 files changed, 116 insertions(+), 27 deletions(-)

diff --git a/include/uapi/linux/magic.h b/include/uapi/linux/magic.h
index bb575f3ab45e5..638ca21b7a909 100644
--- a/include/uapi/linux/magic.h
+++ b/include/uapi/linux/magic.h
@@ -103,5 +103,6 @@
 #define DEVMEM_MAGIC		0x454d444d	/* "DMEM" */
 #define SECRETMEM_MAGIC		0x5345434d	/* "SECM" */
 #define PID_FS_MAGIC		0x50494446	/* "PIDF" */
+#define GUEST_MEMFD_MAGIC	0x474d454d	/* "GMEM" */

 #endif /* __LINUX_MAGIC_H__ */
diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index 08a6bc7d25b60..234e51fd69ff6 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -1,12 +1,16 @@
 // SPDX-License-Identifier: GPL-2.0
+#include <linux/anon_inodes.h>
 #include <linux/backing-dev.h>
 #include <linux/falloc.h>
+#include <linux/fs.h>
 #include <linux/kvm_host.h>
 #include <linux/pagemap.h>
-#include <linux/anon_inodes.h>
+#include <linux/pseudo_fs.h>

 #include "kvm_mm.h"

+static struct vfsmount *kvm_gmem_mnt;
+
 struct kvm_gmem {
 	struct kvm *kvm;
 	struct xarray bindings;
@@ -385,9 +389,44 @@ static struct file_operations kvm_gmem_fops = {
 	.fallocate	= kvm_gmem_fallocate,
 };

-void kvm_gmem_init(struct module *module)
+static int kvm_gmem_init_fs_context(struct fs_context *fc)
+{
+	if (!init_pseudo(fc, GUEST_MEMFD_MAGIC))
+		return -ENOMEM;
+
+	fc->s_iflags |= SB_I_NOEXEC;
+	fc->s_iflags |= SB_I_NODEV;
+
+	return 0;
+}
+
+static struct file_system_type kvm_gmem_fs = {
+	.name		 = "guest_memfd",
+	.init_fs_context = kvm_gmem_init_fs_context,
+	.kill_sb	 = kill_anon_super,
+};
+
+static int kvm_gmem_init_mount(void)
+{
+	kvm_gmem_mnt = kern_mount(&kvm_gmem_fs);
+
+	if (IS_ERR(kvm_gmem_mnt))
+		return PTR_ERR(kvm_gmem_mnt);
+
+	return 0;
+}
+
+int kvm_gmem_init(struct module *module)
 {
 	kvm_gmem_fops.owner = module;
+
+	return kvm_gmem_init_mount();
+}
+
+void kvm_gmem_exit(void)
+{
+	kern_unmount(kvm_gmem_mnt);
+	kvm_gmem_mnt = NULL;
 }

 static int kvm_gmem_migrate_folio(struct address_space *mapping,
@@ -463,11 +502,70 @@ bool __weak kvm_arch_supports_gmem_mmap(struct kvm *kvm)
 	return true;
 }

+static struct inode *kvm_gmem_inode_create(const char *name, loff_t size,
+					   u64 flags)
+{
+	struct inode *inode;
+
+	inode = anon_inode_make_secure_inode(kvm_gmem_mnt->mnt_sb, name, NULL);
+	if (IS_ERR(inode))
+		return inode;
+
+	inode->i_private = (void *)(unsigned long)flags;
+	inode->i_op = &kvm_gmem_iops;
+	inode->i_mapping->a_ops = &kvm_gmem_aops;
+	inode->i_mode |= S_IFREG;
+	inode->i_size = size;
+	mapping_set_gfp_mask(inode->i_mapping, GFP_HIGHUSER);
+	mapping_set_inaccessible(inode->i_mapping);
+	/* Unmovable mappings are supposed to be marked unevictable as well. */
+	WARN_ON_ONCE(!mapping_unevictable(inode->i_mapping));
+
+	return inode;
+}
+
+static struct file *kvm_gmem_inode_create_getfile(void *priv, loff_t size,
+						  u64 flags)
+{
+	static const char *name = "[kvm-gmem]";
+	struct inode *inode;
+	struct file *file;
+	int err;
+
+	err = -ENOENT;
+	/* __fput() will take care of fops_put(). */
+	if (!fops_get(&kvm_gmem_fops))
+		goto err;
+
+	inode = kvm_gmem_inode_create(name, size, flags);
+	if (IS_ERR(inode)) {
+		err = PTR_ERR(inode);
+		goto err_fops_put;
+	}
+
+	file = alloc_file_pseudo(inode, kvm_gmem_mnt, name, O_RDWR,
+				 &kvm_gmem_fops);
+	if (IS_ERR(file)) {
+		err = PTR_ERR(file);
+		goto err_put_inode;
+	}
+
+	file->f_flags |= O_LARGEFILE;
+	file->private_data = priv;
+
+	return file;
+
+err_put_inode:
+	iput(inode);
+err_fops_put:
+	fops_put(&kvm_gmem_fops);
+err:
+	return ERR_PTR(err);
+}
+
 static int __kvm_gmem_create(struct kvm *kvm, loff_t size, u64 flags)
 {
-	const char *anon_name = "[kvm-gmem]";
 	struct kvm_gmem *gmem;
-	struct inode *inode;
 	struct file *file;
 	int fd, err;

@@ -481,32 +579,16 @@ static int __kvm_gmem_create(struct kvm *kvm, loff_t size, u64 flags)
 		goto err_fd;
 	}

-	file = anon_inode_create_getfile(anon_name, &kvm_gmem_fops, gmem,
-					 O_RDWR, NULL);
+	file = kvm_gmem_inode_create_getfile(gmem, size, flags);
 	if (IS_ERR(file)) {
 		err = PTR_ERR(file);
 		goto err_gmem;
 	}

-	file->f_flags |= O_LARGEFILE;
-
-	inode = file->f_inode;
-	WARN_ON(file->f_mapping != inode->i_mapping);
-
-	inode->i_private = (void *)(unsigned long)flags;
-	inode->i_op = &kvm_gmem_iops;
-	inode->i_mapping->a_ops = &kvm_gmem_aops;
-	inode->i_mode |= S_IFREG;
-	inode->i_size = size;
-	mapping_set_gfp_mask(inode->i_mapping, GFP_HIGHUSER);
-	mapping_set_inaccessible(inode->i_mapping);
-	/* Unmovable mappings are supposed to be marked unevictable as well. */
-	WARN_ON_ONCE(!mapping_unevictable(inode->i_mapping));
-
 	kvm_get_kvm(kvm);
 	gmem->kvm = kvm;
 	xa_init(&gmem->bindings);
-	list_add(&gmem->entry, &inode->i_mapping->i_private_list);
+	list_add(&gmem->entry, &file_inode(file)->i_mapping->i_private_list);

 	fd_install(fd, file);
 	return fd;
diff --git a/virt/kvm/kvm_main.c b/virt/kvm/kvm_main.c
index 18f29ef935437..301d48d6e00d0 100644
--- a/virt/kvm/kvm_main.c
+++ b/virt/kvm/kvm_main.c
@@ -6489,7 +6489,9 @@ int kvm_init(unsigned vcpu_size, unsigned vcpu_align, struct module *module)
 	if (WARN_ON_ONCE(r))
 		goto err_vfio;

-	kvm_gmem_init(module);
+	r = kvm_gmem_init(module);
+	if (r)
+		goto err_gmem;

 	r = kvm_init_virtualization();
 	if (r)
@@ -6510,6 +6512,8 @@ int kvm_init(unsigned vcpu_size, unsigned vcpu_align, struct module *module)
 err_register:
 	kvm_uninit_virtualization();
 err_virt:
+	kvm_gmem_exit();
+err_gmem:
 	kvm_vfio_ops_exit();
 err_vfio:
 	kvm_async_pf_deinit();
@@ -6541,6 +6545,7 @@ void kvm_exit(void)
 	for_each_possible_cpu(cpu)
 		free_cpumask_var(per_cpu(cpu_kick_mask, cpu));
 	kmem_cache_destroy(kvm_vcpu_cache);
+	kvm_gmem_exit();
 	kvm_vfio_ops_exit();
 	kvm_async_pf_deinit();
 	kvm_irqfd_exit();
diff --git a/virt/kvm/kvm_mm.h b/virt/kvm/kvm_mm.h
index 31defb08ccbab..9fcc5d5b7f8d0 100644
--- a/virt/kvm/kvm_mm.h
+++ b/virt/kvm/kvm_mm.h
@@ -68,17 +68,18 @@ static inline void gfn_to_pfn_cache_invalidate_start(struct kvm *kvm,
 #endif /* HAVE_KVM_PFNCACHE */

 #ifdef CONFIG_KVM_GUEST_MEMFD
-void kvm_gmem_init(struct module *module);
+int kvm_gmem_init(struct module *module);
+void kvm_gmem_exit(void);
 int kvm_gmem_create(struct kvm *kvm, struct kvm_create_guest_memfd *args);
 int kvm_gmem_bind(struct kvm *kvm, struct kvm_memory_slot *slot,
 		  unsigned int fd, loff_t offset);
 void kvm_gmem_unbind(struct kvm_memory_slot *slot);
 #else
-static inline void kvm_gmem_init(struct module *module)
+static inline int kvm_gmem_init(struct module *module)
 {
-
+	return 0;
 }
-
+static inline void kvm_gmem_exit(void) {};
 static inline int kvm_gmem_bind(struct kvm *kvm,
 					 struct kvm_memory_slot *slot,
 					 unsigned int fd, loff_t offset)
--
2.51.0.268.g9569e192d0-goog

---

## [10] Garg, Shivank — 2025-08-28
*Subject: Re: [PATCH kvm-next V11 4/7] KVM: guest_memfd: Use guest mem inodes
 instead of anonymous inodes*

On 8/28/2025 4:13 AM, Ackerley Tng wrote:
> Shivank Garg <shivankg@amd.com> writes:
> 

I wanted to get it merged quickly ;)

> 
> Here's a new version, Fuad and I reviewed this again internally. The

Thanks for the quick update! The changes look good. I'll incorporate them
in the next version.

Best Regards,
Shivank

---

## [11] David Hildenbrand — 2025-08-28
*Subject: Re: [PATCH kvm-next V11 4/7] KVM: guest_memfd: Use guest mem inodes
 instead of anonymous inodes*

On 28.08.25 00:43, Ackerley Tng wrote:
> Shivank Garg <shivankg@amd.com> writes:
> 

Acked-by: David Hildenbrand <david@redhat.com>

---

## [12] David Hildenbrand — 2025-08-28
*Subject: Re: [PATCH kvm-next V11 0/7] Add NUMA mempolicy support for KVM
 guest-memfd*

On 27.08.25 19:52, Shivank Garg wrote:
> This series introduces NUMA-aware memory placement support for KVM guests
> with guest_memfd memory backends. It builds upon Fuad Tabba's work (V17)

As discussed, I'll be maintaining a guestmemfd-preview branch where I 
just pile patch sets to see how it will all look together. It's 
currently based on kvm/next where "stage 1" resides:

https://git.kernel.org/pub/scm/linux/kernel/git/david/linux.git/log/?h=guestmemfd-preview

---

## [13] David Hildenbrand — 2025-09-24
*Subject: Re: [PATCH kvm-next V11 0/7] Add NUMA mempolicy support for KVM
 guest-memfd*

On 27.08.25 19:52, Shivank Garg wrote:
> This series introduces NUMA-aware memory placement support for KVM guests
> with guest_memfd memory backends. It builds upon Fuad Tabba's work (V17)

Heads-up: I'll queue this (incl. the replacement patch for #4 from the 
reply) and send it tomorrow as a PR against kvm/next to Paolo.

---

## [14] Kalra, Ashish — 2025-09-24
*Subject: Re: [PATCH kvm-next V11 0/7] Add NUMA mempolicy support for KVM
 guest-memfd*

Tested the patch series by auditing the actual userspace (HVA) mappings and seeing if the
corresponding physical PFNs correspond to the expected NUMA node.

Enabled QEMU's kvm_set_user_memory tracepoint to dump the HVA/guest_memfd/guest_memfd_offset/base GPA/size.
This helped determine the HVAs and the memslot that QEMU registers with KVM via the kvm_set_user_memory_region() helper.

After that dumped the PFNs getting mapped into the guest for a particular GPA via enabling the
kvm_mmu_set_spte kernel trace events, performed the GPA->memslot->HVA mapping (via QEMU traces above) and then looked in 
/proc/<qemu_pid>/numa_maps to validate the HVA is bound to the NUMA node associated with that memslot/guest_memfd.
 
Additionally, looked up the PFN (from kernel traces) in /proc/zoneinfo to validate that the physical page belongs to the
NUMA node associated with the memslot/guest_memfd.


This testing/validation is based on the following trees:

Host Kernel: 

https://github.com/AMDESE/linux/commits/snp-hugetlb-v2-wip0/

This tree is based on commit 27cb583e25d0 from David Hildenbrand's guestmemfd_preview tree
(which already includes base mmap support) with Google's HugeTLB v2 patches rebased on top of those
(which include both in-place conversion and hugetlb infrastructure), along with additional
patches to enable in-place conversion and hugetlb for SNP.

QEMU:

https://github.com/AMDESE/qemu/commits/snp-hugetlb-dev-wip0/
   
QEMU command line used for testing/validation:

qemu-system-x86_64 --enable-kvm -object sev-snp-guest,id=sev0,cbitpos=51,reduced-phys-bits=1,convert-in-place=true
-object memory-backend-memfd,id=ram0,host-nodes=0,policy=bind,size=150000M,prealloc=false 
-numa node,nodeid=0,memdev=ram0,cpus=0-31,cpus=64-95 
-object memory-backend-memfd,id=ram1,host-nodes=1,policy=bind,size=150000M,prealloc=false
-numa node,nodeid=1,memdev=ram1,cpus=32-63,cpus=96-127 

(guest NUMA configuration mapped 1:1 to host NUMA configuration).

Tested-by: Ashish Kalra <ashish.kalra@amd.com>

Thanks,
Ashish

On 9/24/2025 1:19 PM, David Hildenbrand wrote:
> On 27.08.25 19:52, Shivank Garg wrote:
>> This series introduces NUMA-aware memory placement support for KVM guests

---

## [15] Sean Christopherson — 2025-09-24
*Subject: Re: [PATCH kvm-next V11 4/7] KVM: guest_memfd: Use guest mem inodes
 instead of anonymous inodes*

My apologies for the super late feedback.  None of this is critical (mechanical
things that can be cleaned up after the fact), so if there's any urgency to
getting this series into 6.18, just ignore it.

On Wed, Aug 27, 2025, Ackerley Tng wrote:
> Shivank Garg <shivankg@amd.com> writes:
> @@ -463,11 +502,70 @@ bool __weak kvm_arch_supports_gmem_mmap(struct kvm *kvm)

I don't see any reason to add two helpers.  It requires quite a bit more lines
of code due to adding more error paths and local variables, and IMO doesn't make
the code any easier to read.

Passing in "gmem" as @priv is especially ridiculous, as it adds code and
obfuscates what file->private_data is set to.

I get the sense that the code was written to be a "replacement" for common APIs,
but that is nonsensical (no pun intended).

>  static int __kvm_gmem_create(struct kvm *kvm, loff_t size, u64 flags)
>  {

I don't understand this change?  Isn't file_inode(file) == inode?

Compile tested only, and again not critical, but it's -40 LoC...


---
 include/uapi/linux/magic.h |  1 +
 virt/kvm/guest_memfd.c     | 75 ++++++++++++++++++++++++++++++++------
 virt/kvm/kvm_main.c        |  7 +++-
 virt/kvm/kvm_mm.h          |  9 +++--
 4 files changed, 76 insertions(+), 16 deletions(-)

diff --git a/include/uapi/linux/magic.h b/include/uapi/linux/magic.h
index bb575f3ab45e..638ca21b7a90 100644
--- a/include/uapi/linux/magic.h
+++ b/include/uapi/linux/magic.h
@@ -103,5 +103,6 @@
 #define DEVMEM_MAGIC		0x454d444d	/* "DMEM" */
 #define SECRETMEM_MAGIC		0x5345434d	/* "SECM" */
 #define PID_FS_MAGIC		0x50494446	/* "PIDF" */
+#define GUEST_MEMFD_MAGIC	0x474d454d	/* "GMEM" */
 
 #endif /* __LINUX_MAGIC_H__ */
diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index 08a6bc7d25b6..73c9791879d5 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -1,12 +1,16 @@
 // SPDX-License-Identifier: GPL-2.0
+#include <linux/anon_inodes.h>
 #include <linux/backing-dev.h>
 #include <linux/falloc.h>
+#include <linux/fs.h>
 #include <linux/kvm_host.h>
+#include <linux/pseudo_fs.h>
 #include <linux/pagemap.h>
-#include <linux/anon_inodes.h>
 
 #include "kvm_mm.h"
 
+static struct vfsmount *kvm_gmem_mnt;
+
 struct kvm_gmem {
 	struct kvm *kvm;
 	struct xarray bindings;
@@ -385,9 +389,45 @@ static struct file_operations kvm_gmem_fops = {
 	.fallocate	= kvm_gmem_fallocate,
 };
 
-void kvm_gmem_init(struct module *module)
+static int kvm_gmem_init_fs_context(struct fs_context *fc)
+{
+	if (!init_pseudo(fc, GUEST_MEMFD_MAGIC))
+		return -ENOMEM;
+
+	fc->s_iflags |= SB_I_NOEXEC;
+	fc->s_iflags |= SB_I_NODEV;
+
+	return 0;
+}
+
+static struct file_system_type kvm_gmem_fs = {
+	.name		 = "guest_memfd",
+	.init_fs_context = kvm_gmem_init_fs_context,
+	.kill_sb	 = kill_anon_super,
+};
+
+static int kvm_gmem_init_mount(void)
+{
+	kvm_gmem_mnt = kern_mount(&kvm_gmem_fs);
+
+	if (IS_ERR(kvm_gmem_mnt))
+		return PTR_ERR(kvm_gmem_mnt);
+
+	kvm_gmem_mnt->mnt_flags |= MNT_NOEXEC;
+	return 0;
+}
+
+int kvm_gmem_init(struct module *module)
 {
 	kvm_gmem_fops.owner = module;
+
+	return kvm_gmem_init_mount();
+}
+
+void kvm_gmem_exit(void)
+{
+	kern_unmount(kvm_gmem_mnt);
+	kvm_gmem_mnt = NULL;
 }
 
 static int kvm_gmem_migrate_folio(struct address_space *mapping,
@@ -465,7 +505,7 @@ bool __weak kvm_arch_supports_gmem_mmap(struct kvm *kvm)
 
 static int __kvm_gmem_create(struct kvm *kvm, loff_t size, u64 flags)
 {
-	const char *anon_name = "[kvm-gmem]";
+	static const char *name = "[kvm-gmem]";
 	struct kvm_gmem *gmem;
 	struct inode *inode;
 	struct file *file;
@@ -481,17 +521,17 @@ static int __kvm_gmem_create(struct kvm *kvm, loff_t size, u64 flags)
 		goto err_fd;
 	}
 
-	file = anon_inode_create_getfile(anon_name, &kvm_gmem_fops, gmem,
-					 O_RDWR, NULL);
-	if (IS_ERR(file)) {
-		err = PTR_ERR(file);
+	/* __fput() will take care of fops_put(). */
+	if (!fops_get(&kvm_gmem_fops)) {
+		err = -ENOENT;
 		goto err_gmem;
 	}
 
-	file->f_flags |= O_LARGEFILE;
-
-	inode = file->f_inode;
-	WARN_ON(file->f_mapping != inode->i_mapping);
+	inode = anon_inode_make_secure_inode(kvm_gmem_mnt->mnt_sb, name, NULL);
+	if (IS_ERR(inode)) {
+		err = PTR_ERR(inode);
+		goto err_fops;
+	}
 
 	inode->i_private = (void *)(unsigned long)flags;
 	inode->i_op = &kvm_gmem_iops;
@@ -503,6 +543,15 @@ static int __kvm_gmem_create(struct kvm *kvm, loff_t size, u64 flags)
 	/* Unmovable mappings are supposed to be marked unevictable as well. */
 	WARN_ON_ONCE(!mapping_unevictable(inode->i_mapping));
 
+	file = alloc_file_pseudo(inode, kvm_gmem_mnt, name, O_RDWR, &kvm_gmem_fops);
+	if (IS_ERR(file)) {
+		err = PTR_ERR(file);
+		goto err_inode;
+	}
+
+	file->f_flags |= O_LARGEFILE;
+	file->private_data = gmem;
+
 	kvm_get_kvm(kvm);
 	gmem->kvm = kvm;
 	xa_init(&gmem->bindings);
@@ -511,6 +560,10 @@ static int __kvm_gmem_create(struct kvm *kvm, loff_t size, u64 flags)
 	fd_install(fd, file);
 	return fd;
 
+err_inode:
+	iput(inode);
+err_fops:
+	fops_put(&kvm_gmem_fops);
 err_gmem:
 	kfree(gmem);
 err_fd:
diff --git a/virt/kvm/kvm_main.c b/virt/kvm/kvm_main.c
index 18f29ef93543..301d48d6e00d 100644
--- a/virt/kvm/kvm_main.c
+++ b/virt/kvm/kvm_main.c
@@ -6489,7 +6489,9 @@ int kvm_init(unsigned vcpu_size, unsigned vcpu_align, struct module *module)
 	if (WARN_ON_ONCE(r))
 		goto err_vfio;
 
-	kvm_gmem_init(module);
+	r = kvm_gmem_init(module);
+	if (r)
+		goto err_gmem;
 
 	r = kvm_init_virtualization();
 	if (r)
@@ -6510,6 +6512,8 @@ int kvm_init(unsigned vcpu_size, unsigned vcpu_align, struct module *module)
 err_register:
 	kvm_uninit_virtualization();
 err_virt:
+	kvm_gmem_exit();
+err_gmem:
 	kvm_vfio_ops_exit();
 err_vfio:
 	kvm_async_pf_deinit();
@@ -6541,6 +6545,7 @@ void kvm_exit(void)
 	for_each_possible_cpu(cpu)
 		free_cpumask_var(per_cpu(cpu_kick_mask, cpu));
 	kmem_cache_destroy(kvm_vcpu_cache);
+	kvm_gmem_exit();
 	kvm_vfio_ops_exit();
 	kvm_async_pf_deinit();
 	kvm_irqfd_exit();
diff --git a/virt/kvm/kvm_mm.h b/virt/kvm/kvm_mm.h
index 31defb08ccba..9fcc5d5b7f8d 100644
--- a/virt/kvm/kvm_mm.h
+++ b/virt/kvm/kvm_mm.h
@@ -68,17 +68,18 @@ static inline void gfn_to_pfn_cache_invalidate_start(struct kvm *kvm,
 #endif /* HAVE_KVM_PFNCACHE */
 
 #ifdef CONFIG_KVM_GUEST_MEMFD
-void kvm_gmem_init(struct module *module);
+int kvm_gmem_init(struct module *module);
+void kvm_gmem_exit(void);
 int kvm_gmem_create(struct kvm *kvm, struct kvm_create_guest_memfd *args);
 int kvm_gmem_bind(struct kvm *kvm, struct kvm_memory_slot *slot,
 		  unsigned int fd, loff_t offset);
 void kvm_gmem_unbind(struct kvm_memory_slot *slot);
 #else
-static inline void kvm_gmem_init(struct module *module)
+static inline int kvm_gmem_init(struct module *module)
 {
-
+	return 0;
 }
-
+static inline void kvm_gmem_exit(void) {};
 static inline int kvm_gmem_bind(struct kvm *kvm,
 					 struct kvm_memory_slot *slot,
 					 unsigned int fd, loff_t offset)

base-commit: d133892dddd6607de651b7e32510359a6af97c4c
--

---

## [16] Garg, Shivank — 2025-09-25
*Subject: Re: [PATCH kvm-next V11 4/7] KVM: guest_memfd: Use guest mem inodes
 instead of anonymous inodes*

On 9/25/2025 8:20 AM, Sean Christopherson wrote:
> My apologies for the super late feedback.  None of this is critical (mechanical
> things that can be cleaned up after the fact), so if there's any urgency to

Thanks.
I did functional testing and it works fine.


> ---
>  include/uapi/linux/magic.h |  1 +

---

## [17] David Hildenbrand — 2025-09-25
*Subject: Re: [PATCH kvm-next V11 4/7] KVM: guest_memfd: Use guest mem inodes
 instead of anonymous inodes*

On 25.09.25 13:44, Garg, Shivank wrote:
> 
> 

I can queue this instead. I guess I can reuse the patch description and 
add Sean as author + add his SOB (if he agrees).

Let me take a look at the patch later in more detail.

---

## [18] Sean Christopherson — 2025-09-25
*Subject: Re: [PATCH kvm-next V11 4/7] KVM: guest_memfd: Use guest mem inodes
 instead of anonymous inodes*

On Thu, Sep 25, 2025, David Hildenbrand wrote:
> On 25.09.25 13:44, Garg, Shivank wrote:
> > On 9/25/2025 8:20 AM, Sean Christopherson wrote:

Eh, Ackerley and Fuad did all the work.  If I had provided feedback earlier,
this would have been handled in a new version.  If they are ok with the changes,
I would prefer they remain co-authors.

Regarding timing, how much do people care about getting this into 6.18 in
particular?  AFAICT, this hasn't gotten any coverage in -next, which makes me a
little nervous.

---

## [19] Fuad Tabba — 2025-09-25
*Subject: Re: [PATCH kvm-next V11 4/7] KVM: guest_memfd: Use guest mem inodes
 instead of anonymous inodes*

On Thu, 25 Sept 2025 at 14:41, Sean Christopherson <seanjc@google.com> wrote:
>
> On Thu, Sep 25, 2025, David Hildenbrand wrote:

These changes are ok by me.
/fuad

> Regarding timing, how much do people care about getting this into 6.18 in
> particular?  AFAICT, this hasn't gotten any coverage in -next, which makes me a

---

## [20] Sean Christopherson — 2025-09-25
*Subject: Re: [PATCH kvm-next V11 5/7] KVM: guest_memfd: Add slab-allocated
 inode cache*

On Wed, Aug 27, 2025, Shivank Garg wrote:
> Add dedicated inode structure (kvm_gmem_inode_info) and slab-allocated
> inode cache for guest memory backing, similar to how shmem handles inodes.

What about naming this simply gmem_inode?

> +	struct inode vfs_inode;
> +};

And then GMEM_I()?

And then (in a later follow-up if we target this for 6.18, or as a prep patch if
we push this out to 6.19), rename kvm_gmem to gmem_file?

That would make guest_memfd look a bit more like other filesystems, and I don't
see a need to preface the local structures and helpers with "kvm_", e.g. GMEM_I()
is analogous to x86's to_vmx() and to_svm().

As for renaming kvm_gmem => gmem_file, I wandered back into this code via Ackerley's
in-place conversion series, and it took me a good long while to remember the roles
of files vs. inodes in gmem.  That's probably a sign that the code needs clarification
given that I wrote the original code.  :-)

Leveraging an old discussion[*], my thought is to get to this:

/*
 * A guest_memfd instance can be associated multiple VMs, each with its own
 * "view" of the underlying physical memory.
 *
 * The gmem's inode is effectively the raw underlying physical storage, and is
 * used to track properties of the physical memory, while each gmem file is
 * effectively a single VM's view of that storage, and is used to track assets
 * specific to its associated VM, e.g. memslots=>gmem bindings.
 */
struct gmem_file {
	struct kvm *kvm;
	struct xarray bindings;
	struct list_head entry;
};

struct gmem_inode {
	struct shared_policy policy;
	struct inode vfs_inode;
};

[*] https://lore.kernel.org/all/ZLGiEfJZTyl7M8mS@google.com

---

## [21] Sean Christopherson — 2025-09-25
*Subject: Re: [PATCH kvm-next V11 5/7] KVM: guest_memfd: Add slab-allocated
 inode cache*

On Thu, Sep 25, 2025, Sean Christopherson wrote:
> On Wed, Aug 27, 2025, Shivank Garg wrote:
> > Add dedicated inode structure (kvm_gmem_inode_info) and slab-allocated

Heh, after looking through other filesystems, they're fairly even on appending
_info or not.  My vote is definitely for gmem_inode.

Before we accumulate more inode usage, e.g. for in-place conversion (which is
actually why I started looking at this code), I think we should also settle on
naming for gmem_file and gmem_inode variables.

As below, "struct kvm_gmem *gmem" gets quite confusing once inodes are in the
picture, especially since that structure isn't _the_ gmem instance, rather it's
a VM's view of that gmem instance.  And on the other side, "info" for the inode
is a bit imprecise, e.g. doesn't immediately make me think of inodes.

A few ideas:

 (a)
   struct gmem_inode *gmem;
   struct gmem_file *f;

 (b)
   struct gmem_inode *gi;
   struct gmem_file *f;

 (c)
   struct gmem_inode *gi;
   struct gmem_file *gf;

 (d)
   struct gmem_inode *gmem_i;
   struct gmem_file *gmem_f;


I think my would be for (a) or (b).  Option (c) seems like it would be hard to
visually differentiate between "gi" and "gf", and gmem_{i,f} are a bit verbose
IMO.

> > +	struct inode vfs_inode;
> > +};

---

## [22] Sean Christopherson — 2025-09-25
*Subject: Re: [PATCH kvm-next V11 6/7] KVM: guest_memfd: Enforce NUMA mempolicy
 using shared policy*

On Wed, Aug 27, 2025, Shivank Garg wrote:
> @@ -26,6 +28,9 @@ static inline struct kvm_gmem_inode_info *KVM_GMEM_I(struct inode *inode)
>  	return container_of(inode, struct kvm_gmem_inode_info, vfs_inode);

I keep reading this is "page offset policy", as opposed to "policy given a page
offset".  Another oddity that is confusing is that this helper explicitly does
get_task_policy(current), while kvm_gmem_get_policy() lets the caller do that.
The end result is the same, but I think it would be helpful for gmem to be
internally consistent.

If we have kvm_gmem_get_policy() use this helper, then we can kill two birds with
one stone:

static struct mempolicy *__kvm_gmem_get_policy(struct gmem_inode *gi,
					       pgoff_t index)
{
	struct mempolicy *mpol;

	mpol = mpol_shared_policy_lookup(&gi->policy, index);
	return mpol ? mpol : get_task_policy(current);
}

static struct mempolicy *kvm_gmem_get_policy(struct vm_area_struct *vma,
					     unsigned long addr, pgoff_t *pgoff)
{
	*pgoff = vma->vm_pgoff + ((addr - vma->vm_start) >> PAGE_SHIFT);

	return __kvm_gmem_get_policy(GMEM_I(file_inode(vma->vm_file)), *pgoff);
}

---

## [23] David Hildenbrand — 2025-09-25
*Subject: Re: [PATCH kvm-next V11 4/7] KVM: guest_memfd: Use guest mem inodes
 instead of anonymous inodes*

On 25.09.25 15:41, Sean Christopherson wrote:
> On Thu, Sep 25, 2025, David Hildenbrand wrote:
>> On 25.09.25 13:44, Garg, Shivank wrote:

Yeah, that's what I would have done.

> 
> Regarding timing, how much do people care about getting this into 6.18 in

I think it will be beneficial if we start getting stuff upstream. But 
waiting a bit longer probably doesn't hurt.

> AFAICT, this hasn't gotten any coverage in -next, which makes me a
> little nervous.

Right.

If we agree, then Shivank can just respin a new version after the merge 
window.

---

## [24] Sean Christopherson — 2025-09-25
*Subject: Re: [PATCH kvm-next V11 4/7] KVM: guest_memfd: Use guest mem inodes
 instead of anonymous inodes*

On Thu, Sep 25, 2025, David Hildenbrand wrote:
> On 25.09.25 15:41, Sean Christopherson wrote:
> > Regarding timing, how much do people care about getting this into 6.18 in

Actually, if Shivank is ok with it, I'd be happy to post the next version(s).
I'll be focusing on the in-place conversion support for the next 1-2 weeks, and
have some (half-baked) refactoring changes to better leverage the inode support
from this series.

I can also plop the first three patches (the non-KVM changes) in a topic branch
straightaway, but not feed it into -next until the merge window closes.  The 0-day
bots scrapes kvm-x86, so that'd get us some early build-bot exposure, and we can
stop bugging the non-KVM folks.  Then when the dust settles on the KVM changes,
I can throw them into the same topic branch.

---

## [25] Sean Christopherson — 2025-09-25
*Subject: Re: [PATCH kvm-next V11 7/7] KVM: guest_memfd: selftests: Add tests
 for mmap and NUMA policy support*

On Wed, Aug 27, 2025, Shivank Garg wrote:
> Add tests for NUMA memory policy binding and NUMA aware allocation in
> guest_memfd. This extends the existing selftests by adding proper

Hrm, this is going to be very annoying.  I don't have libnuma-dev installed on
any of my <too many> systems, and I doubt I'm alone.  Installing the package is
trivial, but I'm a little wary of foisting that requirement on all KVM developers
and build bots.

I'd be especially curious what ARM and RISC-V think, as NUMA is likely a bit less
prevelant there.

>  LDFLAGS += -pthread $(no-pie-option) $(pgste-option)
>  

Using TEST_REQUIRE() here will result in skipping the _entire_ test.  Ideally
this test would use fixtures so that each testcase can run in a child process
and thus can use TEST_REQUIRE(), but that's a conversion for another day.

Easiest thing would probably be to turn this into a common helper and then bail
early.

diff --git a/tools/testing/selftests/kvm/guest_memfd_test.c b/tools/testing/selftests/kvm/guest_memfd_test.c
index 9640d04ec293..6acb186e5300 100644
--- a/tools/testing/selftests/kvm/guest_memfd_test.c
+++ b/tools/testing/selftests/kvm/guest_memfd_test.c
@@ -7,7 +7,6 @@
 #include <stdlib.h>
 #include <string.h>
 #include <unistd.h>
-#include <numa.h>
 #include <numaif.h>
 #include <errno.h>
 #include <stdio.h>
@@ -75,9 +74,6 @@ static void test_mmap_supported(int fd, size_t page_size, size_t total_size)
        TEST_ASSERT(!ret, "munmap() should succeed.");
 }
 
-#define TEST_REQUIRE_NUMA_MULTIPLE_NODES()     \
-       TEST_REQUIRE(numa_available() != -1 && numa_max_node() >= 1)
-
 static void test_mbind(int fd, size_t page_size, size_t total_size)
 {
        unsigned long nodemask = 1; /* nid: 0 */
@@ -87,7 +83,8 @@ static void test_mbind(int fd, size_t page_size, size_t total_size)
        char *mem;
        int ret;
 
-       TEST_REQUIRE_NUMA_MULTIPLE_NODES();
+       if (!is_multi_numa_node_system())
+               return;
 
        mem = mmap(NULL, total_size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
        TEST_ASSERT(mem != MAP_FAILED, "mmap for mbind test should succeed");
@@ -136,7 +133,8 @@ static void test_numa_allocation(int fd, size_t page_size, size_t total_size)
        char *mem;
        int ret, i;
 
-       TEST_REQUIRE_NUMA_MULTIPLE_NODES();
+       if (!is_multi_numa_node_system())
+               return;
 
        /* Clean slate: deallocate all file space, if any */
        ret = fallocate(fd, FALLOC_FL_PUNCH_HOLE | FALLOC_FL_KEEP_SIZE, 0, total_size);
diff --git a/tools/testing/selftests/kvm/include/kvm_util.h b/tools/testing/selftests/kvm/include/kvm_util.h
index 23a506d7eca3..d7051607e6bf 100644
--- a/tools/testing/selftests/kvm/include/kvm_util.h
+++ b/tools/testing/selftests/kvm/include/kvm_util.h
@@ -21,6 +21,7 @@
 #include <sys/eventfd.h>
 #include <sys/ioctl.h>
 
+#include <numa.h>
 #include <pthread.h>
 
 #include "kvm_util_arch.h"
@@ -633,6 +634,11 @@ static inline bool is_smt_on(void)
        return false;
 }
 
+static inline bool is_multi_numa_node_system(void)
+{
+       return numa_available() != -1 && numa_max_node() >= 1;
+}
+
 void vm_create_irqchip(struct kvm_vm *vm);
 
 static inline int __vm_create_guest_memfd(struct kvm_vm *vm, uint64_t size,

---

## [26] Sean Christopherson — 2025-09-25
*Subject: Re: [PATCH kvm-next V11 7/7] KVM: guest_memfd: selftests: Add tests
 for mmap and NUMA policy support*

On Thu, Sep 25, 2025, Sean Christopherson wrote:
> On Wed, Aug 27, 2025, Shivank Garg wrote:
> > Add tests for NUMA memory policy binding and NUMA aware allocation in

Ugh, and it doesn't play nice with static linking.  I haven't tried running on a
NUMA system yet, so maybe it's benign?

/usr/bin/ld: /usr/lib/gcc/x86_64-linux-gnu/14/../../../x86_64-linux-gnu/libnuma.a(affinity.o): in function `affinity_ip':
(.text+0x629): warning: Using 'getaddrinfo' in statically linked applications requires at runtime the shared libraries from the glibc version used for linking

---

## [27] Jason Gunthorpe — 2025-09-25
*Subject: Re: [PATCH kvm-next V11 7/7] KVM: guest_memfd: selftests: Add tests
 for mmap and NUMA policy support*

On Thu, Sep 25, 2025 at 02:35:19PM -0700, Sean Christopherson wrote:
> >  LDLIBS += -ldl
> > +LDLIBS += -lnuma

Wouldn't it be great if the kselftest build system used something like
meson and could work around these little issues without breaking the
whole build ? :(

Does anyone else think this?

Every time I try to build kselftsts I just ignore all the errors the
fly by because the one bit I wanted did build properly anyhow.

Jason

---

## [28] Sean Christopherson — 2025-09-25
*Subject: Re: [PATCH kvm-next V11 7/7] KVM: guest_memfd: selftests: Add tests
 for mmap and NUMA policy support*

On Thu, Sep 25, 2025, Jason Gunthorpe wrote:
> On Thu, Sep 25, 2025 at 02:35:19PM -0700, Sean Christopherson wrote:
> > >  LDLIBS += -ldl

I'm indifferent, as I literally never build all of kselftests, I just build KVM
selftests.  But I'm probably in the minority for the kernel overall.

---

## [29] David Hildenbrand — 2025-09-26
*Subject: Re: [PATCH kvm-next V11 7/7] KVM: guest_memfd: selftests: Add tests
 for mmap and NUMA policy support*

On 25.09.25 23:35, Sean Christopherson wrote:
> On Wed, Aug 27, 2025, Shivank Garg wrote:
>> Add tests for NUMA memory policy binding and NUMA aware allocation in

We unconditionally use it in the mm tests for ksm and migration tests, 
so it's not particularly odd to require it here as well.

What we do with liburing in mm selftests is to detect presence at 
compile time and essentially make the tests behave differently based on 
availability (see check_config.sh).

---

## [30] David Hildenbrand — 2025-09-26
*Subject: Re: [PATCH kvm-next V11 7/7] KVM: guest_memfd: selftests: Add tests
 for mmap and NUMA policy support*

On 26.09.25 01:04, Jason Gunthorpe wrote:
> On Thu, Sep 25, 2025 at 02:35:19PM -0700, Sean Christopherson wrote:
>>>   LDLIBS += -ldl

When I'm in a hurry I even do the same within mm selftests.

---

## [31] Garg, Shivank — 2025-09-26
*Subject: Re: [PATCH kvm-next V11 7/7] KVM: guest_memfd: selftests: Add tests
 for mmap and NUMA policy support*

On 9/26/2025 1:01 PM, David Hildenbrand wrote:
> On 25.09.25 23:35, Sean Christopherson wrote:
>> On Wed, Aug 27, 2025, Shivank Garg wrote:

I have an alternative that drops libnuma entirely.
If this approach looks reasonable, could we potentially factor these out into a
common test utility for other selftests that currently depend on libnuma?

What are your thoughts on this?

diff --git a/tools/testing/selftests/kvm/Makefile.kvm b/tools/testing/selftests/kvm/Makefile.kvm
index c46cef2a7cd7..90f03f00cb04 100644
--- a/tools/testing/selftests/kvm/Makefile.kvm
+++ b/tools/testing/selftests/kvm/Makefile.kvm
@@ -275,7 +275,6 @@ pgste-option = $(call try-run, echo 'int main(void) { return 0; }' | \
 	$(CC) -Werror -Wl$(comma)--s390-pgste -x c - -o "$$TMP",-Wl$(comma)--s390-pgste)
 
 LDLIBS += -ldl
-LDLIBS += -lnuma
 LDFLAGS += -pthread $(no-pie-option) $(pgste-option)
 
 LIBKVM_C := $(filter %.c,$(LIBKVM))
diff --git a/tools/testing/selftests/kvm/guest_memfd_test.c b/tools/testing/selftests/kvm/guest_memfd_test.c
index 9640d04ec293..12ce91950c44 100644
--- a/tools/testing/selftests/kvm/guest_memfd_test.c
+++ b/tools/testing/selftests/kvm/guest_memfd_test.c
@@ -7,8 +7,6 @@
 #include <stdlib.h>
 #include <string.h>
 #include <unistd.h>
-#include <numa.h>
-#include <numaif.h>
 #include <errno.h>
 #include <stdio.h>
 #include <fcntl.h>
@@ -75,9 +73,6 @@ static void test_mmap_supported(int fd, size_t page_size, size_t total_size)
 	TEST_ASSERT(!ret, "munmap() should succeed.");
 }
 
-#define TEST_REQUIRE_NUMA_MULTIPLE_NODES()	\
-	TEST_REQUIRE(numa_available() != -1 && numa_max_node() >= 1)
-
 static void test_mbind(int fd, size_t page_size, size_t total_size)
 {
 	unsigned long nodemask = 1; /* nid: 0 */
@@ -87,7 +82,8 @@ static void test_mbind(int fd, size_t page_size, size_t total_size)
 	char *mem;
 	int ret;
 
-	TEST_REQUIRE_NUMA_MULTIPLE_NODES();
+	if (!is_multi_numa_node_system())
+		return;
 
 	mem = mmap(NULL, total_size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
 	TEST_ASSERT(mem != MAP_FAILED, "mmap for mbind test should succeed");
@@ -136,7 +132,8 @@ static void test_numa_allocation(int fd, size_t page_size, size_t total_size)
 	char *mem;
 	int ret, i;
 
-	TEST_REQUIRE_NUMA_MULTIPLE_NODES();
+	if (!is_multi_numa_node_system())
+		return;
 
 	/* Clean slate: deallocate all file space, if any */
 	ret = fallocate(fd, FALLOC_FL_PUNCH_HOLE | FALLOC_FL_KEEP_SIZE, 0, total_size);
diff --git a/tools/testing/selftests/kvm/include/kvm_util.h b/tools/testing/selftests/kvm/include/kvm_util.h
index 23a506d7eca3..ba4c316f4fef 100644
--- a/tools/testing/selftests/kvm/include/kvm_util.h
+++ b/tools/testing/selftests/kvm/include/kvm_util.h
@@ -12,6 +12,7 @@
 #include "linux/list.h"
 #include <linux/kernel.h>
 #include <linux/kvm.h>
+#include <linux/mempolicy.h>
 #include "linux/rbtree.h"
 #include <linux/types.h>
 
@@ -20,6 +21,7 @@
 
 #include <sys/eventfd.h>
 #include <sys/ioctl.h>
+#include <sys/syscall.h>
 
 #include <pthread.h>
 
@@ -633,6 +635,50 @@ static inline bool is_smt_on(void)
 	return false;
 }
 
+#include <dirent.h>
+static int numa_max_node(void)
+{
+	DIR *d;
+	struct dirent *de;
+	int max_node = 0;
+
+	d = opendir("/sys/devices/system/node");
+	if (!d) {
+		/* No NUMA support or no nodes found, assume single node */
+		return 0;
+	}
+
+	while ((de = readdir(d)) != NULL) {
+		int node_id;
+		char *endptr;
+
+		if (strncmp(de->d_name, "node", 4) != 0)
+			continue;
+
+		node_id = strtol(de->d_name + 4, &endptr, 10);
+		if (*endptr != '\0')
+			continue;
+
+		if (node_id > max_node)
+			max_node = node_id;
+	}
+	closedir(d);
+
+	return max_node;
+}
+
+static int numa_available(void)
+{
+	if (syscall(__NR_get_mempolicy, NULL, NULL, 0, 0, 0) < 0 && (errno == ENOSYS || errno == EPERM))
+		return -1;
+	return 0;
+}
+
+static inline bool is_multi_numa_node_system(void)
+{
+	return numa_available() != -1 && numa_max_node() >= 1;
+}
+
 void vm_create_irqchip(struct kvm_vm *vm);
 
 static inline int __vm_create_guest_memfd(struct kvm_vm *vm, uint64_t size,

---

## [32] Sean Christopherson — 2025-09-26
*Subject: Re: [PATCH kvm-next V11 6/7] KVM: guest_memfd: Enforce NUMA mempolicy
 using shared policy*

On Thu, Sep 25, 2025, Sean Christopherson wrote:
> On Wed, Aug 27, 2025, Shivank Garg wrote:
> > @@ -26,6 +28,9 @@ static inline struct kvm_gmem_inode_info *KVM_GMEM_I(struct inode *inode)

Argh!!!!!  This breaks the selftest because do_get_mempolicy() very specifically
falls back to the default_policy, NOT to the current task's policy.  That is
*exactly* the type of subtle detail that needs to be commented, because there's
no way some random KVM developer is going to know that returning NULL here is
important with respect to get_mempolicy() ABI.

On a happier note, I'm very glad you wrote a testcase :-)

I've got this as fixup-to-the-fixup:

diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index e796cc552a96..61130a52553f 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -114,8 +114,8 @@ static int kvm_gmem_prepare_folio(struct kvm *kvm, struct kvm_memory_slot *slot,
        return r;
 }
 
-static struct mempolicy *__kvm_gmem_get_policy(struct gmem_inode *gi,
-                                              pgoff_t index)
+static struct mempolicy *kvm_gmem_get_folio_policy(struct gmem_inode *gi,
+                                                  pgoff_t index)
 {
 #ifdef CONFIG_NUMA
        struct mempolicy *mpol;
@@ -151,7 +151,7 @@ static struct folio *kvm_gmem_get_folio(struct inode *inode, pgoff_t index)
        if (!IS_ERR(folio))
                return folio;
 
-       policy = __kvm_gmem_get_policy(GMEM_I(inode), index);
+       policy = kvm_gmem_get_folio_policy(GMEM_I(inode), index);
        folio = __filemap_get_folio_mpol(inode->i_mapping, index,
                                         FGP_LOCK | FGP_ACCESSED | FGP_CREAT,
                                         mapping_gfp_mask(inode->i_mapping), policy);
@@ -431,9 +431,18 @@ static int kvm_gmem_set_policy(struct vm_area_struct *vma, struct mempolicy *mpo
 static struct mempolicy *kvm_gmem_get_policy(struct vm_area_struct *vma,
                                              unsigned long addr, pgoff_t *pgoff)
 {
+       struct inode *inode = file_inode(vma->vm_file);
+
         *pgoff = vma->vm_pgoff + ((addr - vma->vm_start) >> PAGE_SHIFT);
 
-        return __kvm_gmem_get_policy(GMEM_I(file_inode(vma->vm_file)), *pgoff);
+       /*
+        * Note!  Directly return whatever the lookup returns, do NOT return
+        * the current task's policy as is done when looking up the policy for
+        * a specific folio.  Kernel ABI for get_mempolicy() is to return
+        * MPOL_DEFAULT when there is no defined policy, not whatever the
+        * default policy resolves to.
+        */
+        return mpol_shared_policy_lookup(&GMEM_I(inode)->policy, *pgoff);
 }
 #endif /* CONFIG_NUMA */

---

## [33] Sean Christopherson — 2025-10-15
*Subject: Re: [PATCH kvm-next V11 0/7] Add NUMA mempolicy support for KVM guest-memfd*

On Wed, 27 Aug 2025 17:52:41 +0000, Shivank Garg wrote:
> This series introduces NUMA-aware memory placement support for KVM guests
> with guest_memfd memory backends. It builds upon Fuad Tabba's work (V17)

Applied the non-KVM change to kvm-x86 gmem.  We're still tweaking and iterating
on the KVM changes, but I fully expect them to land in 6.19.

Holler if you object to taking these through the kvm tree.

[1/7] mm/filemap: Add NUMA mempolicy support to filemap_alloc_folio()
      https://github.com/kvm-x86/linux/commit/601aa29f762f
[2/7] mm/filemap: Extend __filemap_get_folio() to support NUMA memory policies
      https://github.com/kvm-x86/linux/commit/2bb25703e5bd
[3/7] mm/mempolicy: Export memory policy symbols
      https://github.com/kvm-x86/linux/commit/e1b4cf7d6be3

--
https://github.com/kvm-x86/linux/tree/next

---

## [34] Gregory Price — 2025-10-15
*Subject: Re: [f2fs-dev] [PATCH kvm-next V11 6/7] KVM: guest_memfd: Enforce
 NUMA mempolicy using shared policy*

On Fri, Sep 26, 2025 at 12:36:27PM -0700, Sean Christopherson via Linux-f2fs-devel wrote:
> > 
> > static struct mempolicy *kvm_gmem_get_policy(struct vm_area_struct *vma,

Do_get_mempolicy was designed to be accessed by the syscall, not as an in-kernel ABI.

get_task_policy also returns the default policy if there's nothing
there, because that's what applies.

I have dangerous questions:

why is __kvm_gmem_get_policy using
	mpol_shared_policy_lookup()
instead of
	get_vma_policy()

get_vma_policy does this all for you

struct mempolicy *get_vma_policy(struct vm_area_struct *vma,
                                 unsigned long addr, int order, pgoff_t *ilx)
{
        struct mempolicy *pol;

        pol = __get_vma_policy(vma, addr, ilx);
        if (!pol)
                pol = get_task_policy(current);
        if (pol->mode == MPOL_INTERLEAVE ||
            pol->mode == MPOL_WEIGHTED_INTERLEAVE) {
                *ilx += vma->vm_pgoff >> order;
                *ilx += (addr - vma->vm_start) >> (PAGE_SHIFT + order);
        }
        return pol;
}

Of course you still have the same issue: get_task_policy will return the
default, because that's what applies.

do_get_mempolicy just seems like the completely incorrect interface to
be using here.

~Gregory

---

## [35] Sean Christopherson — 2025-10-15
*Subject: Re: [f2fs-dev] [PATCH kvm-next V11 6/7] KVM: guest_memfd: Enforce
 NUMA mempolicy using shared policy*

On Wed, Oct 15, 2025, Gregory Price wrote:
> On Fri, Sep 26, 2025 at 12:36:27PM -0700, Sean Christopherson via Linux-f2fs-devel wrote:
> > > 

Ya, by "get_mempolicy() ABI" I meant the uABI for the get_mempolicy syscall.

> get_task_policy also returns the default policy if there's nothing
> there, because that's what applies.

Not dangerous at all, I find them very helpful!

> why is __kvm_gmem_get_policy using
> 	mpol_shared_policy_lookup()

With the disclaimer that I haven't followed the gory details of this series super
closely, my understanding is...

Because the VMA is a means to an end, and we want the policy to persist even if
the VMA goes away.

With guest_memfd, KVM effectively inverts the standard MMU model.  Instead of mm/
being the primary MMU and KVM being a secondary MMU, guest_memfd is the primary
MMU and any VMAs are secondary (mostly; it's probably more like 1a and 1b).  This
allows KVM to map guest_memfd memory into a guest without a VMA, or with more
permissions than are granted to host userspace, e.g. guest_memfd memory could be
writable by the guest, but read-only for userspace.

But we still want to support things like mbind() so that userspace can ensure
guest_memfd allocations align with the vNUMA topology presented to the guest,
or are bound to the NUMA node where the VM will run.  We considered adding equivalent
file-based syscalls, e.g. fbind(), but IIRC the consensus was that doing so was
unnecessary (and potentially messy?) since we were planning on eventually adding
mmap() support to guest_memfd anyways.

> get_vma_policy does this all for you

I assume that doesn't work if the intent is for new VMAs to pick up the existing
policy from guest_memfd?  And more importantly, guest_memfd needs to hook
->set_policy so that changes through e.g. mbind() persist beyond the lifetime of
the VMA.

> struct mempolicy *get_vma_policy(struct vm_area_struct *vma,
>                                  unsigned long addr, int order, pgoff_t *ilx)

---

## [36] Garg, Shivank — 2025-10-16
*Subject: Re: [f2fs-dev] [PATCH kvm-next V11 6/7] KVM: guest_memfd: Enforce
 NUMA mempolicy using shared policy*

On 10/16/2025 4:18 AM, Sean Christopherson wrote:
> On Wed, Oct 15, 2025, Gregory Price wrote:
>> On Fri, Sep 26, 2025 at 12:36:27PM -0700, Sean Christopherson via Linux-f2fs-devel wrote:
Additionally, the shared_policy based design enables range-based policies via its RB-tree
implementation. IIUC, this will not work with VMA-specific policy design.

>> struct mempolicy *get_vma_policy(struct vm_area_struct *vma,
>>                                  unsigned long addr, int order, pgoff_t *ilx)

---

## [37] Gregory Price — 2025-10-16
*Subject: Re: [f2fs-dev] [PATCH kvm-next V11 6/7] KVM: guest_memfd: Enforce
 NUMA mempolicy using shared policy*

On Wed, Oct 15, 2025 at 03:48:38PM -0700, Sean Christopherson wrote:
> On Wed, Oct 15, 2025, Gregory Price wrote:
> > why is __kvm_gmem_get_policy using

Ah, you know, now that i've taken a close look, I can see that you've
essentially modeled this after ipc/shm.c | mm/shmem.c pattern.

What's had me scratching my chin is that shm/shmem already has a
mempolicy pattern which ends up using folio_alloc_mpol() where the
relationship is

tmpfs: sb_info->mpol = default set by user
  create_file: inode inherits copy of sb_info->mpol
    fault:    mpol = shmem_get_pgoff_policy(info, index, order, &ilx);
             folio = folio_alloc_mpol(gfp, order, mpol, ilx, numa_node_id())

So this inode mempolicy in guest_memfd is really acting more as a the
filesystem-default mempolicy, which you want to survive even if userland
never maps the memory/unmaps the memory.

So the relationship is more like

guest_memfd -> creates fd/inode <- copies task mempolicy (if set)
  vm:  allocates memory via filemap_get_folio_mpol()
  userland mmap(fd):
  	creates new inode<->vma mapping
	vma->mpol = kvm_gmem_get_policy()
	calls to set/get_policy/mbind go through kvm_gmem 

This makes sense, sorry for the noise.  Have been tearing apart
mempolicy lately and I'm disliking the general odor coming off
it as a whole.  I had been poking at adding mempolicy support to
filemap and you got there first.  Overall I think there are still
other problems with mempolicy, but this all looks fine as-is.

~Gregory

---

## [38] Sean Christopherson — 2025-10-20
*Subject: Re: [PATCH kvm-next V11 0/7] Add NUMA mempolicy support for KVM guest-memfd*

On Wed, Oct 15, 2025, Sean Christopherson wrote:
> On Wed, 27 Aug 2025 17:52:41 +0000, Shivank Garg wrote:
> > This series introduces NUMA-aware memory placement support for KVM guests

FYI, I rebased these onto 6.18-rc2 to avoid a silly merge.  New hashes:

[1/3] mm/filemap: Add NUMA mempolicy support to filemap_alloc_folio()
      https://github.com/kvm-x86/linux/commit/7f3779a3ac3e
[2/3] mm/filemap: Extend __filemap_get_folio() to support NUMA memory policies
      https://github.com/kvm-x86/linux/commit/16a542e22339
[3/3] mm/mempolicy: Export memory policy symbols
      https://github.com/kvm-x86/linux/commit/f634f10809ec

---

## [39] patchwork-bot+f2fs@kernel.org — 2025-12-09
*Subject: Re: [f2fs-dev] [PATCH kvm-next V11 0/7] Add NUMA mempolicy support
 for
 KVM guest-memfd*

Hello:

This series was applied to jaegeuk/f2fs.git (dev)
by Sean Christopherson <seanjc@google.com>:

On Wed, 27 Aug 2025 17:52:41 +0000 you wrote:
> This series introduces NUMA-aware memory placement support for KVM guests
> with guest_memfd memory backends. It builds upon Fuad Tabba's work (V17)

Here is the summary with links:
  - [f2fs-dev,kvm-next,V11,1/7] mm/filemap: Add NUMA mempolicy support to filemap_alloc_folio()
    (no matching commit)
  - [f2fs-dev,kvm-next,V11,2/7] mm/filemap: Extend __filemap_get_folio() to support NUMA memory policies
    https://git.kernel.org/jaegeuk/f2fs/c/16a542e22339
  - [f2fs-dev,kvm-next,V11,3/7] mm/mempolicy: Export memory policy symbols
    https://git.kernel.org/jaegeuk/f2fs/c/f634f10809ec
  - [f2fs-dev,kvm-next,V11,4/7] KVM: guest_memfd: Use guest mem inodes instead of anonymous inodes
    (no matching commit)
  - [f2fs-dev,kvm-next,V11,5/7] KVM: guest_memfd: Add slab-allocated inode cache
    (no matching commit)
  - [f2fs-dev,kvm-next,V11,6/7] KVM: guest_memfd: Enforce NUMA mempolicy using shared policy
    (no matching commit)
  - [f2fs-dev,kvm-next,V11,7/7] KVM: guest_memfd: selftests: Add tests for mmap and NUMA policy support
    (no matching commit)

You are awesome, thank you!

---
