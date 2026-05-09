---
title: 'Add NUMA mempolicy support for KVM guest-memfd'
date: 2025-02-26
last_reply: 2025-03-09
message_count: 19
participants: ['Shivank Garg', 'Vlastimil Babka', 'Ackerley Tng', 'Sean Christopherson', 'David Hildenbrand', 'Vishal Annapurve']
---

## [1] Shivank Garg — 2025-02-26

In this patch-series:
Based on the discussion in the bi-weekly guest_memfd upstream call on
2025-02-20[4], I have dropped the RFC tag, documented the memory allocation
behavior after policy changes and added selftests.


KVM's guest-memfd memory backend currently lacks support for NUMA policy
enforcement, causing guest memory allocations to be distributed arbitrarily
across host NUMA nodes regardless of the policy specified by the VMM. This
occurs because conventional userspace NUMA control mechanisms like mbind()
are ineffective with guest-memfd, as the memory isn't directly mapped to
userspace when allocations occur.

This patch-series adds NUMA binding capabilities to guest_memfd backend
KVM guests. It has evolved through several approaches based on community
feedback:

- v1,v2: Extended the KVM_CREATE_GUEST_MEMFD IOCTL to pass mempolicy.
- v3: Introduced fbind() syscall for VMM memory-placement configuration.
- v4-v6: Current approach using shared_policy support and vm_ops (based on
      suggestions from David[1] and guest_memfd biweekly upstream call[2]).

For SEV-SNP guests, which use the guest-memfd memory backend, NUMA-aware
memory placement is essential for optimal performance, particularly for
memory-intensive workloads.

This series implements proper NUMA policy support for guest-memfd by:

1. Adding mempolicy-aware allocation APIs to the filemap layer.
2. Implementing get/set_policy vm_ops in guest_memfd to support shared policy.

With these changes, VMMs can now control guest memory placement by
specifying:
- Policy modes: default, bind, interleave, or preferred
- Host NUMA nodes: List of target nodes for memory allocation

The policy change only affect future allocations and do not migrate
existing memory. This matches mbind(2)'s default behavior which affects
only new allocations unless overridden with MPOL_MF_MOVE/MPOL_MF_MOVE_ALL
flags, which are not supported for guest_memfd as it is unmovable.

This series builds on the existing guest-memfd support in KVM and provides
a clean integration path for NUMA-aware memory management in confidential
computing environments. The work is primarily focused on supporting SEV-SNP
requirements, though the benefits extend to any VMM using the guest-memfd
backend that needs control over guest memory placement.

== Example usage with QEMU (requires patched QEMU from [3]) ==

Snippet of the QEMU changes[3] needed to support this feature:

        /* Create and map guest-memfd region */
        new_block->guest_memfd = kvm_create_guest_memfd(
                                  new_block->max_length, 0, errp);
...
        void *ptr_memfd = mmap(NULL, new_block->max_length,
                               PROT_READ | PROT_WRITE, MAP_SHARED,
                               new_block->guest_memfd, 0);
...
        /* Apply NUMA policy */
        int ret = mbind(ptr_memfd, new_block->max_length,
                        backend->policy, backend->host_nodes,
                        maxnode+1, 0);
...

QEMU Command to run SEV-SNP guest with interleaved memory across
nodes 0 and 1 of the host:

$ qemu-system-x86_64 \
   -enable-kvm \
  ...
   -machine memory-encryption=sev0,vmport=off \
   -object sev-snp-guest,id=sev0,cbitpos=51,reduced-phys-bits=1 \
   -numa node,nodeid=0,memdev=ram0,cpus=0-15 \
   -object memory-backend-memfd,id=ram0,host-nodes=0-1,policy=interleave,size=1024M,share=true,prealloc=false

== Experiment and Analysis == 

SEV-SNP enabled host, AMD Zen 3, 2 socket 2 NUMA node system
NUMA for Policy Guest Node 0: policy=interleave, host-node=0-1

Test: Allocate and touch 50GB inside guest on node=0.


* Generic Kernel (without NUMA supported guest-memfd):
                          Node 0          Node 1           Total
Before running Test:
MemUsed                  9981.60         3312.00        13293.60
After running Test:
MemUsed                 61451.72         3201.62        64653.34

Arbitrary allocations: all ~50GB allocated on node 0.


* With NUMA supported guest-memfd:
                          Node 0          Node 1           Total
Before running Test:
MemUsed                  5003.88         3963.07         8966.94
After running Test:
MemUsed                 30607.55        29670.00        60277.55

Balanced memory distribution: Equal increase (~25GB) on both nodes.

== Conclusion ==

Adding the NUMA-aware memory management to guest_memfd will make a lot of
sense. Improving performance of memory-intensive and locality-sensitive
workloads with fine-grained control over guest memory allocations, as
pointed out in the analysis.

[1] https://lore.kernel.org/linux-mm/6fbef654-36e2-4be5-906e-2a648a845278@redhat.com
[2] https://lore.kernel.org/linux-mm/82c53460-a550-4236-a65a-78f292814edb@redhat.com
[3] https://github.com/shivankgarg98/qemu/tree/guest_memfd_mbind_NUMA
[4] https://lore.kernel.org/linux-mm/2b77e055-98ac-43a1-a7ad-9f9065d7f38f@amd.com

== Earlier postings and changelogs ==

v6 (current):
- Rebase to linux mainline
- Drop RFC tag
- Add selftests to ensure NUMA support for guest_memfd works correctly.

v5:
- https://lore.kernel.org/linux-mm/20250219101559.414878-1-shivankg@amd.com
- Fix documentation and style issues.
- Use EXPORT_SYMBOL_GPL
- Split preparatory change in separate patch

v4:
- https://lore.kernel.org/linux-mm/20250210063227.41125-1-shivankg@amd.com
- Dropped fbind() approach in favor of shared policy support.

v3:
- https://lore.kernel.org/linux-mm/20241105164549.154700-1-shivankg@amd.com
- Introduce fbind() syscall and drop the IOCTL-based approach.

v2:
- https://lore.kernel.org/linux-mm/20240919094438.10987-1-shivankg@amd.com
- Add fixes suggested by Matthew Wilcox.

v1:
- https://lore.kernel.org/linux-mm/20240916165743.201087-1-shivankg@amd.com
- Proposed IOCTL based approach to pass NUMA mempolicy.

Shivank Garg (4):
  mm/mempolicy: export memory policy symbols
  KVM: guest_memfd: Pass file pointer instead of inode pointer
  KVM: guest_memfd: Enforce NUMA mempolicy using shared policy
  KVM: guest_memfd: selftests: add tests for mmap and NUMA policy
    support

Shivansh Dhiman (1):
  mm/filemap: add mempolicy support to the filemap layer

 include/linux/pagemap.h                       | 39 +++++++++
 mm/filemap.c                                  | 30 +++++--
 mm/mempolicy.c                                |  6 ++
 .../testing/selftests/kvm/guest_memfd_test.c  | 86 +++++++++++++++++-
 virt/kvm/guest_memfd.c                        | 87 +++++++++++++++++--
 5 files changed, 233 insertions(+), 15 deletions(-)

---

## [2] Shivank Garg — 2025-02-26
*Subject: [PATCH v6 1/5] mm/filemap: add mempolicy support to the filemap layer*

From: Shivansh Dhiman <shivansh.dhiman@amd.com>

Add NUMA mempolicy support to the filemap allocation path by introducing
new APIs that take a mempolicy argument:
- filemap_grab_folio_mpol()
- filemap_alloc_folio_mpol()
- __filemap_get_folio_mpol()

These APIs allow callers to specify a NUMA policy during page cache
allocations, enabling fine-grained control over memory placement. This is
particularly needed by KVM when using guest-memfd memory backends, where
the guest memory needs to be allocated according to the NUMA policy
specified by VMM.

The existing non-mempolicy APIs remain unchanged and continue to use the
default allocation behavior.

Signed-off-by: Shivansh Dhiman <shivansh.dhiman@amd.com>
Signed-off-by: Shivank Garg <shivankg@amd.com>
---
 include/linux/pagemap.h | 39 +++++++++++++++++++++++++++++++++++++++
 mm/filemap.c            | 30 +++++++++++++++++++++++++-----
 2 files changed, 64 insertions(+), 5 deletions(-)

diff --git a/include/linux/pagemap.h b/include/linux/pagemap.h
index 47bfc6b1b632..f480b3b29113 100644
--- a/include/linux/pagemap.h
+++ b/include/linux/pagemap.h
@@ -662,15 +662,24 @@ static inline void *detach_page_private(struct page *page)
 
 #ifdef CONFIG_NUMA
 struct folio *filemap_alloc_folio_noprof(gfp_t gfp, unsigned int order);
+struct folio *filemap_alloc_folio_mpol_noprof(gfp_t gfp, unsigned int order,
+		struct mempolicy *mpol);
 #else
 static inline struct folio *filemap_alloc_folio_noprof(gfp_t gfp, unsigned int order)
 {
 	return folio_alloc_noprof(gfp, order);
 }
+static inline struct folio *filemap_alloc_folio_mpol_noprof(gfp_t gfp,
+		unsigned int order, struct mempolicy *mpol)
+{
+	return filemap_alloc_folio_noprof(gfp, order);
+}
 #endif
 
 #define filemap_alloc_folio(...)				\
 	alloc_hooks(filemap_alloc_folio_noprof(__VA_ARGS__))
+#define filemap_alloc_folio_mpol(...)				\
+	alloc_hooks(filemap_alloc_folio_mpol_noprof(__VA_ARGS__))
 
 static inline struct page *__page_cache_alloc(gfp_t gfp)
 {
@@ -762,6 +771,8 @@ static inline fgf_t fgf_set_order(size_t size)
 void *filemap_get_entry(struct address_space *mapping, pgoff_t index);
 struct folio *__filemap_get_folio(struct address_space *mapping, pgoff_t index,
 		fgf_t fgp_flags, gfp_t gfp);
+struct folio *__filemap_get_folio_mpol(struct address_space *mapping,
+		pgoff_t index, fgf_t fgp_flags, gfp_t gfp, struct mempolicy *mpol);
 struct page *pagecache_get_page(struct address_space *mapping, pgoff_t index,
 		fgf_t fgp_flags, gfp_t gfp);
 
@@ -820,6 +831,34 @@ static inline struct folio *filemap_grab_folio(struct address_space *mapping,
 			mapping_gfp_mask(mapping));
 }
 
+/**
+ * filemap_grab_folio_mpol - grab a folio from the page cache.
+ * @mapping: The address space to search.
+ * @index: The page index.
+ * @mpol: The mempolicy to apply when allocating a new folio.
+ *
+ * Same as filemap_grab_folio(), except that it allocates the folio using
+ * given memory policy.
+ *
+ * Return: A found or created folio. ERR_PTR(-ENOMEM) if no folio is found
+ * and failed to create a folio.
+ */
+#ifdef CONFIG_NUMA
+static inline struct folio *filemap_grab_folio_mpol(struct address_space *mapping,
+					pgoff_t index, struct mempolicy *mpol)
+{
+	return __filemap_get_folio_mpol(mapping, index,
+			FGP_LOCK | FGP_ACCESSED | FGP_CREAT,
+			mapping_gfp_mask(mapping), mpol);
+}
+#else
+static inline struct folio *filemap_grab_folio_mpol(struct address_space *mapping,
+					pgoff_t index, struct mempolicy *mpol)
+{
+	return filemap_grab_folio(mapping, index);
+}
+#endif /* CONFIG_NUMA */
+
 /**
  * find_get_page - find and get a page reference
  * @mapping: the address_space to search
diff --git a/mm/filemap.c b/mm/filemap.c
index 804d7365680c..9abb20c4d705 100644
--- a/mm/filemap.c
+++ b/mm/filemap.c
@@ -1001,11 +1001,17 @@ int filemap_add_folio(struct address_space *mapping, struct folio *folio,
 EXPORT_SYMBOL_GPL(filemap_add_folio);
 
 #ifdef CONFIG_NUMA
-struct folio *filemap_alloc_folio_noprof(gfp_t gfp, unsigned int order)
+struct folio *filemap_alloc_folio_mpol_noprof(gfp_t gfp, unsigned int order,
+		struct mempolicy *mpol)
 {
 	int n;
 	struct folio *folio;
 
+	if (mpol)
+		return folio_alloc_mpol_noprof(gfp, order, mpol,
+					       NO_INTERLEAVE_INDEX,
+					       numa_node_id());
+
 	if (cpuset_do_page_mem_spread()) {
 		unsigned int cpuset_mems_cookie;
 		do {
@@ -1018,6 +1024,12 @@ struct folio *filemap_alloc_folio_noprof(gfp_t gfp, unsigned int order)
 	}
 	return folio_alloc_noprof(gfp, order);
 }
+EXPORT_SYMBOL(filemap_alloc_folio_mpol_noprof);
+
+struct folio *filemap_alloc_folio_noprof(gfp_t gfp, unsigned int order)
+{
+	return filemap_alloc_folio_mpol_noprof(gfp, order, NULL);
+}
 EXPORT_SYMBOL(filemap_alloc_folio_noprof);
 #endif
 
@@ -1881,11 +1893,12 @@ void *filemap_get_entry(struct address_space *mapping, pgoff_t index)
 }
 
 /**
- * __filemap_get_folio - Find and get a reference to a folio.
+ * __filemap_get_folio_mpol - Find and get a reference to a folio.
  * @mapping: The address_space to search.
  * @index: The page index.
  * @fgp_flags: %FGP flags modify how the folio is returned.
  * @gfp: Memory allocation flags to use if %FGP_CREAT is specified.
+ * @mpol: The mempolicy to apply when allocating a new folio.
  *
  * Looks up the page cache entry at @mapping & @index.
  *
@@ -1896,8 +1909,8 @@ void *filemap_get_entry(struct address_space *mapping, pgoff_t index)
  *
  * Return: The found folio or an ERR_PTR() otherwise.
  */
-struct folio *__filemap_get_folio(struct address_space *mapping, pgoff_t index,
-		fgf_t fgp_flags, gfp_t gfp)
+struct folio *__filemap_get_folio_mpol(struct address_space *mapping, pgoff_t index,
+		fgf_t fgp_flags, gfp_t gfp, struct mempolicy *mpol)
 {
 	struct folio *folio;
 
@@ -1967,7 +1980,7 @@ struct folio *__filemap_get_folio(struct address_space *mapping, pgoff_t index,
 			err = -ENOMEM;
 			if (order > min_order)
 				alloc_gfp |= __GFP_NORETRY | __GFP_NOWARN;
-			folio = filemap_alloc_folio(alloc_gfp, order);
+			folio = filemap_alloc_folio_mpol(alloc_gfp, order, mpol);
 			if (!folio)
 				continue;
 
@@ -2003,6 +2016,13 @@ struct folio *__filemap_get_folio(struct address_space *mapping, pgoff_t index,
 		folio_clear_dropbehind(folio);
 	return folio;
 }
+EXPORT_SYMBOL(__filemap_get_folio_mpol);
+
+struct folio *__filemap_get_folio(struct address_space *mapping, pgoff_t index,
+		fgf_t fgp_flags, gfp_t gfp)
+{
+	return __filemap_get_folio_mpol(mapping, index, fgp_flags, gfp, NULL);
+}
 EXPORT_SYMBOL(__filemap_get_folio);
 
 static inline struct folio *find_get_entry(struct xa_state *xas, pgoff_t max,

---

## [3] Shivank Garg — 2025-02-26
*Subject: [PATCH v6 2/5] mm/mempolicy: export memory policy symbols*

KVM guest_memfd wants to implement support for NUMA policies just like
shmem already does using the shared policy infrastructure. As
guest_memfd currently resides in KVM module code, we have to export the
relevant symbols.

In the future, guest_memfd might be moved to core-mm, at which point the
symbols no longer would have to be exported. When/if that happens is
still unclear.

Acked-by: David Hildenbrand <david@redhat.com>
Signed-off-by: Shivank Garg <shivankg@amd.com>
---
 mm/mempolicy.c | 6 ++++++
 1 file changed, 6 insertions(+)

diff --git a/mm/mempolicy.c b/mm/mempolicy.c
index bbaadbeeb291..d9c5dcdadcd0 100644
--- a/mm/mempolicy.c
+++ b/mm/mempolicy.c
@@ -214,6 +214,7 @@ struct mempolicy *get_task_policy(struct task_struct *p)
 
 	return &default_policy;
 }
+EXPORT_SYMBOL_GPL(get_task_policy);
 
 static const struct mempolicy_operations {
 	int (*create)(struct mempolicy *pol, const nodemask_t *nodes);
@@ -347,6 +348,7 @@ void __mpol_put(struct mempolicy *pol)
 		return;
 	kmem_cache_free(policy_cache, pol);
 }
+EXPORT_SYMBOL_GPL(__mpol_put);
 
 static void mpol_rebind_default(struct mempolicy *pol, const nodemask_t *nodes)
 {
@@ -2736,6 +2738,7 @@ struct mempolicy *mpol_shared_policy_lookup(struct shared_policy *sp,
 	read_unlock(&sp->lock);
 	return pol;
 }
+EXPORT_SYMBOL_GPL(mpol_shared_policy_lookup);
 
 static void sp_free(struct sp_node *n)
 {
@@ -3021,6 +3024,7 @@ void mpol_shared_policy_init(struct shared_policy *sp, struct mempolicy *mpol)
 		mpol_put(mpol);	/* drop our incoming ref on sb mpol */
 	}
 }
+EXPORT_SYMBOL_GPL(mpol_shared_policy_init);
 
 int mpol_set_shared_policy(struct shared_policy *sp,
 			struct vm_area_struct *vma, struct mempolicy *pol)
@@ -3039,6 +3043,7 @@ int mpol_set_shared_policy(struct shared_policy *sp,
 		sp_free(new);
 	return err;
 }
+EXPORT_SYMBOL_GPL(mpol_set_shared_policy);
 
 /* Free a backing policy store on inode delete. */
 void mpol_free_shared_policy(struct shared_policy *sp)
@@ -3057,6 +3062,7 @@ void mpol_free_shared_policy(struct shared_policy *sp)
 	}
 	write_unlock(&sp->lock);
 }
+EXPORT_SYMBOL_GPL(mpol_free_shared_policy);
 
 #ifdef CONFIG_NUMA_BALANCING
 static int __initdata numabalancing_override;

---

## [4] Shivank Garg — 2025-02-26
*Subject: [PATCH v6 3/5] KVM: guest_memfd: Pass file pointer instead of inode pointer*

Pass file pointer instead of inode pointer to access struct kvm_gmem stored
in file->private_data. This change is needed to access NUMA policy when
allocating memory for guest_memfd, which will be added in a following
patch.

The following functions are modified to use file pointers:
- kvm_gmem_get_folio()
- kvm_gmem_allocate()

Preparatory patch and no functional changes.

Signed-off-by: Shivank Garg <shivankg@amd.com>
---
 virt/kvm/guest_memfd.c | 13 +++++++------
 1 file changed, 7 insertions(+), 6 deletions(-)

diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index b2aa6bf24d3a..f18176976ae3 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -96,10 +96,10 @@ static int kvm_gmem_prepare_folio(struct kvm *kvm, struct kvm_memory_slot *slot,
  * Ignore accessed, referenced, and dirty flags.  The memory is
  * unevictable and there is no storage to write back to.
  */
-static struct folio *kvm_gmem_get_folio(struct inode *inode, pgoff_t index)
+static struct folio *kvm_gmem_get_folio(struct file *file, pgoff_t index)
 {
 	/* TODO: Support huge pages. */
-	return filemap_grab_folio(inode->i_mapping, index);
+	return filemap_grab_folio(file_inode(file)->i_mapping, index);
 }
 
 static void kvm_gmem_invalidate_begin(struct kvm_gmem *gmem, pgoff_t start,
@@ -177,8 +177,9 @@ static long kvm_gmem_punch_hole(struct inode *inode, loff_t offset, loff_t len)
 	return 0;
 }
 
-static long kvm_gmem_allocate(struct inode *inode, loff_t offset, loff_t len)
+static long kvm_gmem_allocate(struct file *file, loff_t offset, loff_t len)
 {
+	struct inode *inode = file_inode(file);
 	struct address_space *mapping = inode->i_mapping;
 	pgoff_t start, index, end;
 	int r;
@@ -201,7 +202,7 @@ static long kvm_gmem_allocate(struct inode *inode, loff_t offset, loff_t len)
 			break;
 		}
 
-		folio = kvm_gmem_get_folio(inode, index);
+		folio = kvm_gmem_get_folio(file, index);
 		if (IS_ERR(folio)) {
 			r = PTR_ERR(folio);
 			break;
@@ -241,7 +242,7 @@ static long kvm_gmem_fallocate(struct file *file, int mode, loff_t offset,
 	if (mode & FALLOC_FL_PUNCH_HOLE)
 		ret = kvm_gmem_punch_hole(file_inode(file), offset, len);
 	else
-		ret = kvm_gmem_allocate(file_inode(file), offset, len);
+		ret = kvm_gmem_allocate(file, offset, len);
 
 	if (!ret)
 		file_modified(file);
@@ -585,7 +586,7 @@ static struct folio *__kvm_gmem_get_pfn(struct file *file,
 		return ERR_PTR(-EIO);
 	}
 
-	folio = kvm_gmem_get_folio(file_inode(file), index);
+	folio = kvm_gmem_get_folio(file, index);
 	if (IS_ERR(folio))
 		return folio;

---

## [5] Shivank Garg — 2025-02-26
*Subject: [PATCH v6 4/5] KVM: guest_memfd: Enforce NUMA mempolicy using shared policy*

Previously, guest-memfd allocations followed local NUMA node id in absence
of process mempolicy, resulting in arbitrary memory allocation.
Moreover, mbind() couldn't be used since memory wasn't mapped to userspace
in the VMM.

Enable NUMA policy support by implementing vm_ops for guest-memfd mmap
operation. This allows the VMM to map the memory and use mbind() to set
the desired NUMA policy. The policy is then retrieved via
mpol_shared_policy_lookup() and passed to filemap_grab_folio_mpol() to
ensure that allocations follow the specified memory policy.

This enables the VMM to control guest memory NUMA placement by calling
mbind() on the mapped memory regions, providing fine-grained control over
guest memory allocation across NUMA nodes.

The policy change only affect future allocations and does not migrate
existing memory. This matches mbind(2)'s default behavior which affects
only new allocations unless overridden with MPOL_MF_MOVE/MPOL_MF_MOVE_ALL
flags, which are not supported for guest_memfd as it is unmovable.

Suggested-by: David Hildenbrand <david@redhat.com>
Signed-off-by: Shivank Garg <shivankg@amd.com>
---
 virt/kvm/guest_memfd.c | 76 +++++++++++++++++++++++++++++++++++++++++-
 1 file changed, 75 insertions(+), 1 deletion(-)

diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index f18176976ae3..b3a8819117a0 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -2,6 +2,7 @@
 #include <linux/backing-dev.h>
 #include <linux/falloc.h>
 #include <linux/kvm_host.h>
+#include <linux/mempolicy.h>
 #include <linux/pagemap.h>
 #include <linux/anon_inodes.h>
 
@@ -11,8 +12,12 @@ struct kvm_gmem {
 	struct kvm *kvm;
 	struct xarray bindings;
 	struct list_head entry;
+	struct shared_policy policy;
 };
 
+static struct mempolicy *kvm_gmem_get_pgoff_policy(struct kvm_gmem *gmem,
+						   pgoff_t index);
+
 /**
  * folio_file_pfn - like folio_file_page, but return a pfn.
  * @folio: The folio which contains this index.
@@ -99,7 +104,25 @@ static int kvm_gmem_prepare_folio(struct kvm *kvm, struct kvm_memory_slot *slot,
 static struct folio *kvm_gmem_get_folio(struct file *file, pgoff_t index)
 {
 	/* TODO: Support huge pages. */
-	return filemap_grab_folio(file_inode(file)->i_mapping, index);
+	struct kvm_gmem *gmem = file->private_data;
+	struct inode *inode = file_inode(file);
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
+	policy = kvm_gmem_get_pgoff_policy(gmem, index);
+	folio = filemap_grab_folio_mpol(inode->i_mapping, index, policy);
+	mpol_cond_put(policy);
+
+	return folio;
 }
 
 static void kvm_gmem_invalidate_begin(struct kvm_gmem *gmem, pgoff_t start,
@@ -291,6 +314,7 @@ static int kvm_gmem_release(struct inode *inode, struct file *file)
 	mutex_unlock(&kvm->slots_lock);
 
 	xa_destroy(&gmem->bindings);
+	mpol_free_shared_policy(&gmem->policy);
 	kfree(gmem);
 
 	kvm_put_kvm(kvm);
@@ -312,8 +336,57 @@ static pgoff_t kvm_gmem_get_index(struct kvm_memory_slot *slot, gfn_t gfn)
 {
 	return gfn - slot->base_gfn + slot->gmem.pgoff;
 }
+#ifdef CONFIG_NUMA
+static int kvm_gmem_set_policy(struct vm_area_struct *vma, struct mempolicy *new)
+{
+	struct file *file = vma->vm_file;
+	struct kvm_gmem *gmem = file->private_data;
+
+	return mpol_set_shared_policy(&gmem->policy, vma, new);
+}
+
+static struct mempolicy *kvm_gmem_get_policy(struct vm_area_struct *vma,
+		unsigned long addr, pgoff_t *pgoff)
+{
+	struct file *file = vma->vm_file;
+	struct kvm_gmem *gmem = file->private_data;
+
+	*pgoff = vma->vm_pgoff + ((addr - vma->vm_start) >> PAGE_SHIFT);
+	return mpol_shared_policy_lookup(&gmem->policy, *pgoff);
+}
+
+static struct mempolicy *kvm_gmem_get_pgoff_policy(struct kvm_gmem *gmem,
+						   pgoff_t index)
+{
+	struct mempolicy *mpol;
+
+	mpol = mpol_shared_policy_lookup(&gmem->policy, index);
+	return mpol ? mpol : get_task_policy(current);
+}
+#else
+static struct mempolicy *kvm_gmem_get_pgoff_policy(struct kvm_gmem *gmem,
+						   pgoff_t index)
+{
+	return NULL;
+}
+#endif /* CONFIG_NUMA */
+
+static const struct vm_operations_struct kvm_gmem_vm_ops = {
+#ifdef CONFIG_NUMA
+	.get_policy	= kvm_gmem_get_policy,
+	.set_policy	= kvm_gmem_set_policy,
+#endif
+};
+
+static int kvm_gmem_mmap(struct file *file, struct vm_area_struct *vma)
+{
+	file_accessed(file);
+	vma->vm_ops = &kvm_gmem_vm_ops;
+	return 0;
+}
 
 static struct file_operations kvm_gmem_fops = {
+	.mmap		= kvm_gmem_mmap,
 	.open		= generic_file_open,
 	.release	= kvm_gmem_release,
 	.fallocate	= kvm_gmem_fallocate,
@@ -446,6 +519,7 @@ static int __kvm_gmem_create(struct kvm *kvm, loff_t size, u64 flags)
 	kvm_get_kvm(kvm);
 	gmem->kvm = kvm;
 	xa_init(&gmem->bindings);
+	mpol_shared_policy_init(&gmem->policy, NULL);
 	list_add(&gmem->entry, &inode->i_mapping->i_private_list);
 
 	fd_install(fd, file);

---

## [6] Shivank Garg — 2025-02-26
*Subject: [PATCH v6 5/5] KVM: guest_memfd: selftests: add tests for mmap and NUMA policy support*

Add tests for memory mapping and NUMA memory policy binding in
guest_memfd. This extends the existing selftests by adding proper
validation for:
- Basic mmap() functionality
- KVM GMEM set_policy and get_policy() vm_ops functionality using
  mbind() and get_mempolicy()
- NUMA policy application before and after memory allocation

These tests help ensure NUMA support for guest_memfd works correctly.

Signed-off-by: Shivank Garg <shivankg@amd.com>
---
 .../testing/selftests/kvm/guest_memfd_test.c  | 86 ++++++++++++++++++-
 1 file changed, 82 insertions(+), 4 deletions(-)

diff --git a/tools/testing/selftests/kvm/guest_memfd_test.c b/tools/testing/selftests/kvm/guest_memfd_test.c
index ce687f8d248f..b9c845cc41e0 100644
--- a/tools/testing/selftests/kvm/guest_memfd_test.c
+++ b/tools/testing/selftests/kvm/guest_memfd_test.c
@@ -13,9 +13,11 @@
 
 #include <linux/bitmap.h>
 #include <linux/falloc.h>
+#include <linux/mempolicy.h>
 #include <sys/mman.h>
 #include <sys/types.h>
 #include <sys/stat.h>
+#include <sys/syscall.h>
 
 #include "kvm_util.h"
 #include "test_util.h"
@@ -34,12 +36,86 @@ static void test_file_read_write(int fd)
 		    "pwrite on a guest_mem fd should fail");
 }
 
-static void test_mmap(int fd, size_t page_size)
+static void test_mmap(int fd, size_t page_size, size_t total_size)
 {
 	char *mem;
 
-	mem = mmap(NULL, page_size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
-	TEST_ASSERT_EQ(mem, MAP_FAILED);
+	mem = mmap(NULL, total_size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
+	TEST_ASSERT(mem != MAP_FAILED, "mmap should succeed");
+	TEST_ASSERT(munmap(mem, total_size) == 0, "munmap should succeed");
+}
+
+static void test_mbind(int fd, size_t page_size, size_t total_size)
+{
+	unsigned long nodemask = 1; /* nid: 0 */
+	unsigned long maxnode = 8;
+	unsigned long get_nodemask;
+	int get_policy;
+	void *mem;
+	int ret;
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
+	unsigned long nodemask = 1;  /* Node 0 */
+	unsigned long maxnode = 8;
+	void *mem;
+	int ret;
+
+	mem = mmap(NULL, total_size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
+	TEST_ASSERT(mem != MAP_FAILED, "mmap should succeed");
+
+	/* Set NUMA policy after allocation */
+	ret = fallocate(fd, FALLOC_FL_KEEP_SIZE, 0, page_size * 2);
+	TEST_ASSERT(!ret, "fallocate with aligned offset and size should succeed");
+	ret = syscall(__NR_mbind, mem, page_size * 2, MPOL_BIND, &nodemask,
+		      maxnode, 0);
+	TEST_ASSERT(!ret, "mbind should succeed");
+
+	/* Set NUMA policy before allocation */
+	ret = syscall(__NR_mbind, mem + page_size * 2, page_size, MPOL_BIND,
+		      &nodemask, maxnode, 0);
+	TEST_ASSERT(!ret, "mbind should succeed");
+	ret = fallocate(fd, FALLOC_FL_KEEP_SIZE, page_size * 2, page_size * 2);
+	TEST_ASSERT(!ret, "fallocate with aligned offset and size should succeed");
+
+	TEST_ASSERT(munmap(mem, total_size) == 0, "munmap should succeed");
 }
 
 static void test_file_size(int fd, size_t page_size, size_t total_size)
@@ -190,7 +266,9 @@ int main(int argc, char *argv[])
 	fd = vm_create_guest_memfd(vm, total_size, 0);
 
 	test_file_read_write(fd);
-	test_mmap(fd, page_size);
+	test_mmap(fd, page_size, total_size);
+	test_mbind(fd, page_size, total_size);
+	test_numa_allocation(fd, page_size, total_size);
 	test_file_size(fd, page_size, total_size);
 	test_fallocate(fd, page_size, total_size);
 	test_invalid_punch_hole(fd, page_size, total_size);

---

## [7] Vlastimil Babka — 2025-02-26
*Subject: Re: [PATCH v6 2/5] mm/mempolicy: export memory policy symbols*

On 2/26/25 9:25 AM, Shivank Garg wrote:
> KVM guest_memfd wants to implement support for NUMA policies just like
> shmem already does using the shared policy infrastructure. As

Acked-by: Vlastimil Babka <vbabka@suse.cz>

> ---
>  mm/mempolicy.c | 6 ++++++

---

## [8] Vlastimil Babka — 2025-02-28
*Subject: Re: [PATCH v6 1/5] mm/filemap: add mempolicy support to the filemap
 layer*

On 2/26/25 09:25, Shivank Garg wrote:
> From: Shivansh Dhiman <shivansh.dhiman@amd.com>
> 

<snip>

> --- a/mm/filemap.c
> +++ b/mm/filemap.c

Here it seems to me:

- filemap_alloc_folio_noprof() could stay unchanged
- filemap_alloc_folio_mpol_noprof() would
  - call folio_alloc_mpol_noprof() if (mpol)
  - call filemap_alloc_folio_noprof() otherwise

The code would be a bit more clearly structured that way?

> @@ -1881,11 +1893,12 @@ void *filemap_get_entry(struct address_space *mapping, pgoff_t index)
>  }

---

## [9] Ackerley Tng — 2025-02-28
*Subject: Re: [PATCH v6 4/5] KVM: guest_memfd: Enforce NUMA mempolicy using
 shared policy*

Shivank Garg <shivankg@amd.com> writes:

> Previously, guest-memfd allocations followed local NUMA node id in absence
> of process mempolicy, resulting in arbitrary memory allocation.

struct shared_policy should be stored on the inode rather than the file,
since the memory policy is a property of the memory (struct inode),
rather than a property of how the memory is used for a given VM (struct
file).

When the shared_policy is stored on the inode, intra-host migration [1]
will work correctly, since the while the inode will be transferred from
one VM (struct kvm) to another, the file (a VM's view/bindings of the
memory) will be recreated for the new VM.

I'm thinking of having a patch like this [2] to introduce inodes.

With this, we shouldn't need to pass file pointers instead of inode
pointers.

> +static struct mempolicy *kvm_gmem_get_pgoff_policy(struct kvm_gmem *gmem,
> +						   pgoff_t index);

[1] https://lore.kernel.org/lkml/cover.1691446946.git.ackerleytng@google.com/T/
[2] https://lore.kernel.org/all/d1940d466fc69472c8b6dda95df2e0522b2d8744.1726009989.git.ackerleytng@google.com/

---

## [10] Ackerley Tng — 2025-02-28
*Subject: Re: [PATCH v6 1/5] mm/filemap: add mempolicy support to the filemap layer*

Vlastimil Babka <vbabka@suse.cz> writes:

> On 2/26/25 09:25, Shivank Garg wrote:
>> From: Shivansh Dhiman <shivansh.dhiman@amd.com>

Could we pass in the interleave index instead of hard-coding it?

>> +					       numa_node_id());
>> +

I feel that the original proposal makes it clearer that for all filemap
folio allocations, if mpol is defined, anything to do with cpuset's page
spread is overridden. Just a slight preference though. I do also agree
that having filemap_alloc_folio_mpol_noprof() call
filemap_alloc_folio_noprof() would result in fewer changes.

>> @@ -1881,11 +1893,12 @@ void *filemap_get_entry(struct address_space *mapping, pgoff_t index)
>>  }

---

## [11] Vlastimil Babka — 2025-03-03
*Subject: Re: [PATCH v6 4/5] KVM: guest_memfd: Enforce NUMA mempolicy using
 shared policy*

On 2/28/25 18:25, Ackerley Tng wrote:
> Shivank Garg <shivankg@amd.com> writes:
> 

That makes sense. AFAICS shmem also uses inodes to store policy.

> When the shared_policy is stored on the inode, intra-host migration [1]
> will work correctly, since the while the inode will be transferred from

shmem has it easier by already having inodes

> With this, we shouldn't need to pass file pointers instead of inode
> pointers.

Any downsides, besides more work needed? Or is it feasible to do it using
files now and convert to inodes later?

Feels like something that must have been discussed already, but I don't
recall specifics.

---

## [12] Ackerley Tng — 2025-03-04
*Subject: Re: [PATCH v6 4/5] KVM: guest_memfd: Enforce NUMA mempolicy using
 shared policy*

Vlastimil Babka <vbabka@suse.cz> writes:

> On 2/28/25 18:25, Ackerley Tng wrote:
>> Shivank Garg <shivankg@amd.com> writes:

Here's where Sean described file vs inode: "The inode is effectively the
raw underlying physical storage, while the file is the VM's view of that
storage." [1].

I guess you're right that for now there is little distinction between
file and inode and using file should be feasible, but I feel that this
dilutes the original intent. Something like [2] doesn't seem like too
big of a change and could perhaps be included earlier rather than later,
since it will also contribute to support for restricted mapping [3].

[1] https://lore.kernel.org/all/ZLGiEfJZTyl7M8mS@google.com/
[2] https://lore.kernel.org/all/d1940d466fc69472c8b6dda95df2e0522b2d8744.1726009989.git.ackerleytng@google.com/
[3] https://lore.kernel.org/all/20250117163001.2326672-1-tabba@google.com/T/

---

## [13] Sean Christopherson — 2025-03-04
*Subject: Re: [PATCH v6 4/5] KVM: guest_memfd: Enforce NUMA mempolicy using
 shared policy*

On Tue, Mar 04, 2025, Ackerley Tng wrote:
> Vlastimil Babka <vbabka@suse.cz> writes:
> >> struct shared_policy should be stored on the inode rather than the file,

Hmm, and using the file would be actively problematic at some point.  One could
argue that NUMA policy is property of the VM accessing the memory, i.e. that two
VMs mapping the same guest_memfd could want different policies.  But in practice,
that would allow for conflicting requirements, e.g. different policies in each
VM for the same chunk of memory, and would likely lead to surprising behavior due
to having to manually do mbind() for every VM/file view.

> Something like [2] doesn't seem like too big of a change and could perhaps be
> included earlier rather than later, since it will also contribute to support

---

## [14] David Hildenbrand — 2025-03-04
*Subject: Re: [PATCH v6 4/5] KVM: guest_memfd: Enforce NUMA mempolicy using
 shared policy*

On 04.03.25 16:30, Sean Christopherson wrote:
> On Tue, Mar 04, 2025, Ackerley Tng wrote:
>> Vlastimil Babka <vbabka@suse.cz> writes:

I think that's the same behavior with shmem? I mean, if you have two 
people asking for different things for the same MAP_SHARE file range, 
surprises are unavoidable.

Or am I missing something?

---

## [15] Sean Christopherson — 2025-03-04
*Subject: Re: [PATCH v6 4/5] KVM: guest_memfd: Enforce NUMA mempolicy using
 shared policy*

On Tue, Mar 04, 2025, David Hildenbrand wrote:
> On 04.03.25 16:30, Sean Christopherson wrote:
> > On Tue, Mar 04, 2025, Ackerley Tng wrote:

Yeah, I was specifically thinking of the case where a secondary mapping doesn't
do mbind() at all, e.g. could end up effectively polluting guest_memfd with "bad"
allocations.

---

## [16] Shivank Garg — 2025-03-05
*Subject: Re: [PATCH v6 4/5] KVM: guest_memfd: Enforce NUMA mempolicy using
 shared policy*

On 3/4/2025 10:29 PM, Sean Christopherson wrote:
> On Tue, Mar 04, 2025, David Hildenbrand wrote:
>> On 04.03.25 16:30, Sean Christopherson wrote:

Thank you for the feedback.
I agree that storing the policy in the inode is the correct approach, as it aligns
with shmem's behavior. I now understand that keeping the policy in file-private data
could lead to surprising behavior, especially with multiple VMs mapping the same
guest_memfd.

The inode-based approach also makes sense from a long-term perspective, especially
with upcoming restricted mapping support. I'll pick the Ackerley's patch[1] to add
support for gmem inodes. With this patch, it does not seem overly complex to
implement to policy storage in inodes.

I'll test this approach and submit a revised patch shortly.

[1] https://lore.kernel.org/all/d1940d466fc69472c8b6dda95df2e0522b2d8744.1726009989.git.ackerleytng@google.com/

Thanks,
Shivank

---

## [17] Shivank Garg — 2025-03-05
*Subject: Re: [PATCH v6 1/5] mm/filemap: add mempolicy support to the filemap
 layer*

On 2/28/2025 11:21 PM, Ackerley Tng wrote:
> Vlastimil Babka <vbabka@suse.cz> writes:
> 

Good point.
I'll modify this to allow passing the interleave index. 

> 
>>> +					       numa_node_id());

Your proposed structure makes sense.
I'll update the patch to add these suggestions in the next version.

Thanks,
Shivank

>>> @@ -1881,11 +1893,12 @@ void *filemap_get_entry(struct address_space *mapping, pgoff_t index)
>>>  }

---

## [18] Vishal Annapurve — 2025-03-08
*Subject: Re: [PATCH v6 0/5] Add NUMA mempolicy support for KVM guest-memfd*

On Wed, Feb 26, 2025 at 12:28 AM Shivank Garg <shivankg@amd.com> wrote:
>
> In this patch-series:

I have been thinking more about this after the last guest_memfd
upstream call on March 6th.

To allow 1G page support with guest_memfd [1] without encountering
significant memory overheads, its important to support in-place memory
conversion with private hugepages getting split/merged upon
conversion. Private pages can be seamlessly split/merged only if the
refcounts of complete subpages are frozen, most effective way to
achieve and enforce this is to just not have struct pages for private
memory. All the guest_memfd private range users (including IOMMU [2]
in future) can request pfns for offsets and get notified about
invalidation when pfns go away.

Not having struct pages for private memory also provide additional benefits:
* Significantly lesser memory overhead for handling splitting/merge operations
    - With struct pages around, every split of 1G page needs struct
page allocation for 512 * 512 4K pages in worst case.
* Enable roadmap for PFN range allocators in the backend and usecases
like KHO [3] that target use of memory without struct page.

IIRC, filemap was initially used as a matter of convenience for
initial guest memfd implementation.

As pointed by David in the call, to get rid of struct page for private
memory ranges, filemap/pagecache needs to be replaced by a lightweight
mechanism that tracks offsets -> pfns mapping for private memory
ranges while still keeping filemap/pagecache for shared memory ranges
(it's still needed to allow GUP usecases). I am starting to think that
the filemap replacement for private memory ranges should be done
sooner rather than later, otherwise it will become more and more
difficult with features landing in guest_memfd relying on presence of
filemap.

This discussion matters more for hugepages and PFN range allocations.
I would like to ensure that we have consensus on this direction.

[1] https://lpc.events/event/18/contributions/1764/
[2] https://lore.kernel.org/kvm/CAGtprH8C4MQwVTFPBMbFWyW4BrK8-mDqjJn-UUFbFhw4w23f3A@mail.gmail.com/
[3] https://lore.kernel.org/linux-mm/20240805093245.889357-1-jgowans@amazon.com/

---

## [19] Vishal Annapurve — 2025-03-09
*Subject: Re: [PATCH v6 0/5] Add NUMA mempolicy support for KVM guest-memfd*

On Sat, Mar 8, 2025 at 5:09 PM Vishal Annapurve <vannapurve@google.com> wrote:
>
> On Wed, Feb 26, 2025 at 12:28 AM Shivank Garg <shivankg@amd.com> wrote:

Going one step further, If we support folio->mapping and possibly any
other needed bits while still tracking folios corresponding to shared
memory ranges along with private memory pfns in a separate
"gmem_cache" to keep core-mm interaction compatible, can that allow
pursuing the direction of not needing filemap at all?

> the filemap replacement for private memory ranges should be done
> sooner rather than later, otherwise it will become more and more

---
