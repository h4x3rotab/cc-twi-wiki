---
title: 'Add NUMA mempolicy support for KVM guest-memfd'
date: 2025-04-08
last_reply: 2025-04-22
message_count: 20
participants: ['Shivank Garg', 'Paul Moore', 'Christoph Hellwig', 'Ackerley Tng', 'David Hildenbrand']
---

## [1] Shivank Garg — 2025-04-08

KVM's guest-memfd memory backend currently lacks support for NUMA policy
enforcement, causing guest memory allocations to be distributed arbitrarily
across host NUMA nodes regardless of the policy specified by the VMM. This
occurs because conventional userspace NUMA control mechanisms like mbind()
are ineffective with guest-memfd, as the memory isn't directly mapped to
userspace when allocations occur.

This patch-series adds NUMA-aware memory placement for guest_memfd backed
KVM guests. Based on community feedback, the approach has evolved as
follows:

- v1,v2: Extended the KVM_CREATE_GUEST_MEMFD IOCTL to pass mempolicy.
- v3: Introduced fbind() syscall for VMM memory-placement configuration.
- v4-v6: Current approach using shared_policy support and vm_ops (based on
         suggestions from David[1] and guest_memfd biweekly upstream
         calls[2][4]).
- v7: Use inodes to store NUMA policy instead of file[5].

== Implementation ==

This series implements proper NUMA policy support for guest-memfd by:

1. Adding mempolicy-aware allocation APIs to the filemap layer.
2. Add custom inodes (via a dedicated slab-allocated inode cache,
   kvm_gmem_inode_info) to store NUMA policy and metadata for guest memory.
3. Implementing get/set_policy vm_ops in guest_memfd to support shared policy.

With these changes, VMMs can now control guest memory placement by
specifying:
- Policy modes: default, bind, interleave, or preferred
- Host NUMA nodes: List of target nodes for memory allocation

Policies only affect future allocations and do not migrate existing memory.
This matches mbind(2)'s default behavior which affects only new allocations
unless overridden with MPOL_MF_MOVE/MPOL_MF_MOVE_ALL flags (Not supported
for guest_memfd as it is unmovable).

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

Please review and provide feedback!

Thanks,
Shivank

[1] https://lore.kernel.org/all/6fbef654-36e2-4be5-906e-2a648a845278@redhat.com
[2] https://lore.kernel.org/all/6f2bfac2-d9e7-4e4a-9298-7accded16b4f@redhat.com
[3] https://github.com/shivankgarg98/qemu/tree/guest_memfd_mbind_NUMA
[4] https://lore.kernel.org/all/2b77e055-98ac-43a1-a7ad-9f9065d7f38f@amd.com
[5] https://lore.kernel.org/all/diqzbjumm167.fsf@ackerleytng-ctop.c.googlers.com

== Earlier postings and changelogs ==

v7 (current):
- Add fixes suggested by Vlastimil and Ackerley.
- Store NUMA policy in custom inode struct instead of file.

v6:
- https://lore.kernel.org/all/20250226082549.6034-1-shivankg@amd.com
- Rebase to linux mainline
- Drop RFC tag
- Add selftests to ensure NUMA support for guest_memfd works correctly.

v5:
- https://lore.kernel.org/all/20250219101559.414878-1-shivankg@amd.com
- Fix documentation and style issues.
- Use EXPORT_SYMBOL_GPL
- Split preparatory change in separate patch

v4:
- https://lore.kernel.org/all/20250210063227.41125-1-shivankg@amd.com
- Dropped fbind() approach in favor of shared policy support.

v3:
- https://lore.kernel.org/all/20241105164549.154700-1-shivankg@amd.com
- Introduce fbind() syscall and drop the IOCTL-based approach.

v2:
- https://lore.kernel.org/all/20240919094438.10987-1-shivankg@amd.com
- Add fixes suggested by Matthew Wilcox.

v1:
- https://lore.kernel.org/all/20240916165743.201087-1-shivankg@amd.com
- Proposed IOCTL based approach to pass NUMA mempolicy.

Ackerley Tng (1):
  KVM: guest_memfd: Make guest mem use guest mem inodes instead of
    anonymous inodes

Shivank Garg (6):
  mm/mempolicy: Export memory policy symbols
  security: Export security_inode_init_security_anon for KVM guest_memfd
  KVM: Add kvm_gmem_exit() cleanup function
  KVM: guest_memfd: Add slab-allocated inode cache
  KVM: guest_memfd: Enforce NUMA mempolicy using shared policy
  KVM: guest_memfd: selftests: Add tests for mmap and NUMA policy
    support

Shivansh Dhiman (1):
  mm/filemap: Add mempolicy support to the filemap layer

 include/linux/pagemap.h                       |  41 +++
 include/uapi/linux/magic.h                    |   1 +
 mm/filemap.c                                  |  27 +-
 mm/mempolicy.c                                |   6 +
 security/security.c                           |   1 +
 .../testing/selftests/kvm/guest_memfd_test.c  |  86 +++++-
 virt/kvm/guest_memfd.c                        | 261 ++++++++++++++++--
 virt/kvm/kvm_main.c                           |   2 +
 virt/kvm/kvm_mm.h                             |   6 +
 9 files changed, 402 insertions(+), 29 deletions(-)

---

## [2] Shivank Garg — 2025-04-08
*Subject: [PATCH RFC v7 1/8] mm/filemap: Add mempolicy support to the filemap layer*

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
 include/linux/pagemap.h | 41 +++++++++++++++++++++++++++++++++++++++++
 mm/filemap.c            | 27 +++++++++++++++++++++++----
 2 files changed, 64 insertions(+), 4 deletions(-)

diff --git a/include/linux/pagemap.h b/include/linux/pagemap.h
index 26baa78f1ca7..bc5231626557 100644
--- a/include/linux/pagemap.h
+++ b/include/linux/pagemap.h
@@ -637,15 +637,24 @@ static inline void *detach_page_private(struct page *page)
 
 #ifdef CONFIG_NUMA
 struct folio *filemap_alloc_folio_noprof(gfp_t gfp, unsigned int order);
+struct folio *filemap_alloc_folio_mpol_noprof(gfp_t gfp, unsigned int order,
+		struct mempolicy *mpol, pgoff_t ilx);
 #else
 static inline struct folio *filemap_alloc_folio_noprof(gfp_t gfp, unsigned int order)
 {
 	return folio_alloc_noprof(gfp, order);
 }
+static inline struct folio *filemap_alloc_folio_mpol_noprof(gfp_t gfp,
+		unsigned int order, struct mempolicy *mpol, pgoff_t ilx)
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
@@ -737,6 +746,8 @@ static inline fgf_t fgf_set_order(size_t size)
 void *filemap_get_entry(struct address_space *mapping, pgoff_t index);
 struct folio *__filemap_get_folio(struct address_space *mapping, pgoff_t index,
 		fgf_t fgp_flags, gfp_t gfp);
+struct folio *__filemap_get_folio_mpol(struct address_space *mapping,
+		pgoff_t index, fgf_t fgp_flags, gfp_t gfp, struct mempolicy *mpol, pgoff_t ilx);
 struct page *pagecache_get_page(struct address_space *mapping, pgoff_t index,
 		fgf_t fgp_flags, gfp_t gfp);
 
@@ -795,6 +806,36 @@ static inline struct folio *filemap_grab_folio(struct address_space *mapping,
 			mapping_gfp_mask(mapping));
 }
 
+/**
+ * filemap_grab_folio_mpol - grab a folio from the page cache.
+ * @mapping: The address space to search.
+ * @index: The page index.
+ * @mpol: The mempolicy to apply when allocating a new folio.
+ * @ilx: The interleave index, for use only with MPOL_INTERLEAVE or
+ *       MPOL_WEIGHTED_INTERLEAVE.
+ *
+ * Same as filemap_grab_folio(), except that it allocates the folio using
+ * given memory policy.
+ *
+ * Return: A found or created folio. ERR_PTR(-ENOMEM) if no folio is found
+ * and failed to create a folio.
+ */
+#ifdef CONFIG_NUMA
+static inline struct folio *filemap_grab_folio_mpol(struct address_space *mapping,
+					pgoff_t index, struct mempolicy *mpol, pgoff_t ilx)
+{
+	return __filemap_get_folio_mpol(mapping, index,
+			FGP_LOCK | FGP_ACCESSED | FGP_CREAT,
+			mapping_gfp_mask(mapping), mpol, ilx);
+}
+#else
+static inline struct folio *filemap_grab_folio_mpol(struct address_space *mapping,
+					pgoff_t index, struct mempolicy *mpol, pgoff_t ilx)
+{
+	return filemap_grab_folio(mapping, index);
+}
+#endif /* CONFIG_NUMA */
+
 /**
  * find_get_page - find and get a page reference
  * @mapping: the address_space to search
diff --git a/mm/filemap.c b/mm/filemap.c
index b5e784f34d98..7b06ee4b4d63 100644
--- a/mm/filemap.c
+++ b/mm/filemap.c
@@ -1007,6 +1007,15 @@ struct folio *filemap_alloc_folio_noprof(gfp_t gfp, unsigned int order)
 	return folio_alloc_noprof(gfp, order);
 }
 EXPORT_SYMBOL(filemap_alloc_folio_noprof);
+
+struct folio *filemap_alloc_folio_mpol_noprof(gfp_t gfp, unsigned int order,
+		struct mempolicy *mpol, pgoff_t ilx)
+{
+	if (mpol)
+		return folio_alloc_mpol_noprof(gfp, order, mpol,
+					       ilx, numa_node_id());
+	return filemap_alloc_folio_noprof(gfp, order);
+}
 #endif
 
 /*
@@ -1880,11 +1889,14 @@ void *filemap_get_entry(struct address_space *mapping, pgoff_t index)
 }
 
 /**
- * __filemap_get_folio - Find and get a reference to a folio.
+ * __filemap_get_folio_mpol - Find and get a reference to a folio.
  * @mapping: The address_space to search.
  * @index: The page index.
  * @fgp_flags: %FGP flags modify how the folio is returned.
  * @gfp: Memory allocation flags to use if %FGP_CREAT is specified.
+ * @mpol: The mempolicy to apply when allocating a new folio.
+ * @ilx: The interleave index, for use only with MPOL_INTERLEAVE or
+ *       MPOL_WEIGHTED_INTERLEAVE.
  *
  * Looks up the page cache entry at @mapping & @index.
  *
@@ -1895,8 +1907,8 @@ void *filemap_get_entry(struct address_space *mapping, pgoff_t index)
  *
  * Return: The found folio or an ERR_PTR() otherwise.
  */
-struct folio *__filemap_get_folio(struct address_space *mapping, pgoff_t index,
-		fgf_t fgp_flags, gfp_t gfp)
+struct folio *__filemap_get_folio_mpol(struct address_space *mapping, pgoff_t index,
+		fgf_t fgp_flags, gfp_t gfp, struct mempolicy *mpol, pgoff_t ilx)
 {
 	struct folio *folio;
 
@@ -1966,7 +1978,7 @@ struct folio *__filemap_get_folio(struct address_space *mapping, pgoff_t index,
 			err = -ENOMEM;
 			if (order > min_order)
 				alloc_gfp |= __GFP_NORETRY | __GFP_NOWARN;
-			folio = filemap_alloc_folio(alloc_gfp, order);
+			folio = filemap_alloc_folio_mpol(alloc_gfp, order, mpol, ilx);
 			if (!folio)
 				continue;
 
@@ -2013,6 +2025,13 @@ struct folio *__filemap_get_folio(struct address_space *mapping, pgoff_t index,
 		folio_clear_dropbehind(folio);
 	return folio;
 }
+EXPORT_SYMBOL(__filemap_get_folio_mpol);
+
+struct folio *__filemap_get_folio(struct address_space *mapping, pgoff_t index,
+		fgf_t fgp_flags, gfp_t gfp)
+{
+	return __filemap_get_folio_mpol(mapping, index, fgp_flags, gfp, NULL, 0);
+}
 EXPORT_SYMBOL(__filemap_get_folio);
 
 static inline struct folio *find_get_entry(struct xa_state *xas, pgoff_t max,

---

## [3] Shivank Garg — 2025-04-08
*Subject: [PATCH RFC v7 2/8] mm/mempolicy: Export memory policy symbols*

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
index b28a1e6ae096..18182dd38fc1 100644
--- a/mm/mempolicy.c
+++ b/mm/mempolicy.c
@@ -245,6 +245,7 @@ struct mempolicy *get_task_policy(struct task_struct *p)
 
 	return &default_policy;
 }
+EXPORT_SYMBOL_GPL(get_task_policy);
 
 static const struct mempolicy_operations {
 	int (*create)(struct mempolicy *pol, const nodemask_t *nodes);
@@ -378,6 +379,7 @@ void __mpol_put(struct mempolicy *pol)
 		return;
 	kmem_cache_free(policy_cache, pol);
 }
+EXPORT_SYMBOL_GPL(__mpol_put);
 
 static void mpol_rebind_default(struct mempolicy *pol, const nodemask_t *nodes)
 {
@@ -2767,6 +2769,7 @@ struct mempolicy *mpol_shared_policy_lookup(struct shared_policy *sp,
 	read_unlock(&sp->lock);
 	return pol;
 }
+EXPORT_SYMBOL_GPL(mpol_shared_policy_lookup);
 
 static void sp_free(struct sp_node *n)
 {
@@ -3052,6 +3055,7 @@ void mpol_shared_policy_init(struct shared_policy *sp, struct mempolicy *mpol)
 		mpol_put(mpol);	/* drop our incoming ref on sb mpol */
 	}
 }
+EXPORT_SYMBOL_GPL(mpol_shared_policy_init);
 
 int mpol_set_shared_policy(struct shared_policy *sp,
 			struct vm_area_struct *vma, struct mempolicy *pol)
@@ -3070,6 +3074,7 @@ int mpol_set_shared_policy(struct shared_policy *sp,
 		sp_free(new);
 	return err;
 }
+EXPORT_SYMBOL_GPL(mpol_set_shared_policy);
 
 /* Free a backing policy store on inode delete. */
 void mpol_free_shared_policy(struct shared_policy *sp)
@@ -3088,6 +3093,7 @@ void mpol_free_shared_policy(struct shared_policy *sp)
 	}
 	write_unlock(&sp->lock);
 }
+EXPORT_SYMBOL_GPL(mpol_free_shared_policy);
 
 #ifdef CONFIG_NUMA_BALANCING
 static int __initdata numabalancing_override;

---

## [4] Shivank Garg — 2025-04-08
*Subject: [PATCH RFC v7 3/8] security: Export security_inode_init_security_anon for KVM guest_memfd*

KVM guest_memfd is implementing its own inodes to store metadata for
backing memory using a custom filesystem. This requires the ability to
initialize anonymous inode using security_inode_init_security_anon().

As guest_memfd currently resides in the KVM module, we need to export this
symbol for use outside the core kernel. In the future, guest_memfd might be
moved to core-mm, at which point the symbols no longer would have to be
exported. When/if that happens is still unclear.

Signed-off-by: Shivank Garg <shivankg@amd.com>
---
 security/security.c | 1 +
 1 file changed, 1 insertion(+)

diff --git a/security/security.c b/security/security.c
index fb57e8fddd91..097283bb06a5 100644
--- a/security/security.c
+++ b/security/security.c
@@ -1877,6 +1877,7 @@ int security_inode_init_security_anon(struct inode *inode,
 	return call_int_hook(inode_init_security_anon, inode, name,
 			     context_inode);
 }
+EXPORT_SYMBOL(security_inode_init_security_anon);
 
 #ifdef CONFIG_SECURITY_PATH
 /**

---

## [5] Shivank Garg — 2025-04-08
*Subject: [PATCH RFC v7 4/8] KVM: Add kvm_gmem_exit() cleanup function*

Add empty kvm_gmem_exit() function for proper cleanup of guest memory
resources. Call it from both kvm_init() error path and kvm_exit().

This is preparatory change for upcoming work that involves KVM guest_memfd
using inodes to store metadata for backing memory.

Signed-off-by: Shivank Garg <shivankg@amd.com>
---
 virt/kvm/guest_memfd.c | 5 +++++
 virt/kvm/kvm_main.c    | 2 ++
 virt/kvm/kvm_mm.h      | 6 ++++++
 3 files changed, 13 insertions(+)

diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index b2aa6bf24d3a..88453b040926 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -323,6 +323,11 @@ void kvm_gmem_init(struct module *module)
 	kvm_gmem_fops.owner = module;
 }
 
+void kvm_gmem_exit(void)
+{
+
+}
+
 static int kvm_gmem_migrate_folio(struct address_space *mapping,
 				  struct folio *dst, struct folio *src,
 				  enum migrate_mode mode)
diff --git a/virt/kvm/kvm_main.c b/virt/kvm/kvm_main.c
index e85b33a92624..39580f79908a 100644
--- a/virt/kvm/kvm_main.c
+++ b/virt/kvm/kvm_main.c
@@ -6441,6 +6441,7 @@ int kvm_init(unsigned vcpu_size, unsigned vcpu_align, struct module *module)
 err_register:
 	kvm_uninit_virtualization();
 err_virt:
+	kvm_gmem_exit();
 	kvm_vfio_ops_exit();
 err_vfio:
 	kvm_async_pf_deinit();
@@ -6471,6 +6472,7 @@ void kvm_exit(void)
 	debugfs_remove_recursive(kvm_debugfs_dir);
 	for_each_possible_cpu(cpu)
 		free_cpumask_var(per_cpu(cpu_kick_mask, cpu));
+	kvm_gmem_exit();
 	kmem_cache_destroy(kvm_vcpu_cache);
 	kvm_vfio_ops_exit();
 	kvm_async_pf_deinit();
diff --git a/virt/kvm/kvm_mm.h b/virt/kvm/kvm_mm.h
index acef3f5c582a..8070956b1a43 100644
--- a/virt/kvm/kvm_mm.h
+++ b/virt/kvm/kvm_mm.h
@@ -69,6 +69,7 @@ static inline void gfn_to_pfn_cache_invalidate_start(struct kvm *kvm,
 
 #ifdef CONFIG_KVM_PRIVATE_MEM
 void kvm_gmem_init(struct module *module);
+void kvm_gmem_exit(void);
 int kvm_gmem_create(struct kvm *kvm, struct kvm_create_guest_memfd *args);
 int kvm_gmem_bind(struct kvm *kvm, struct kvm_memory_slot *slot,
 		  unsigned int fd, loff_t offset);
@@ -79,6 +80,11 @@ static inline void kvm_gmem_init(struct module *module)
 
 }
 
+static inline void kvm_gmem_exit(void)
+{
+
+}
+
 static inline int kvm_gmem_bind(struct kvm *kvm,
 					 struct kvm_memory_slot *slot,
 					 unsigned int fd, loff_t offset)

---

## [6] Shivank Garg — 2025-04-08
*Subject: [PATCH RFC v7 5/8] KVM: guest_memfd: Make guest mem use guest mem inodes instead of anonymous inodes*

From: Ackerley Tng <ackerleytng@google.com>

Using guest mem inodes allows us to store metadata for the backing
memory on the inode. Metadata will be added in a later patch to support
HugeTLB pages.

Metadata about backing memory should not be stored on the file, since
the file represents a guest_memfd's binding with a struct kvm, and
metadata about backing memory is not unique to a specific binding and
struct kvm.

Signed-off-by: Ackerley Tng <ackerleytng@google.com>
Signed-off-by: Fuad Tabba <tabba@google.com>
Signed-off-by: Shivank Garg <shivankg@amd.com>
---
 include/uapi/linux/magic.h |   1 +
 virt/kvm/guest_memfd.c     | 133 +++++++++++++++++++++++++++++++------
 2 files changed, 113 insertions(+), 21 deletions(-)

diff --git a/include/uapi/linux/magic.h b/include/uapi/linux/magic.h
index bb575f3ab45e..169dba2a6920 100644
--- a/include/uapi/linux/magic.h
+++ b/include/uapi/linux/magic.h
@@ -103,5 +103,6 @@
 #define DEVMEM_MAGIC		0x454d444d	/* "DMEM" */
 #define SECRETMEM_MAGIC		0x5345434d	/* "SECM" */
 #define PID_FS_MAGIC		0x50494446	/* "PIDF" */
+#define GUEST_MEMORY_MAGIC	0x474d454d	/* "GMEM" */
 
 #endif /* __LINUX_MAGIC_H__ */
diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index 88453b040926..002328569c9e 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -1,12 +1,17 @@
 // SPDX-License-Identifier: GPL-2.0
+#include <linux/fs.h>
+#include <linux/mount.h>
 #include <linux/backing-dev.h>
 #include <linux/falloc.h>
 #include <linux/kvm_host.h>
+#include <linux/pseudo_fs.h>
 #include <linux/pagemap.h>
 #include <linux/anon_inodes.h>
 
 #include "kvm_mm.h"
 
+static struct vfsmount *kvm_gmem_mnt;
+
 struct kvm_gmem {
 	struct kvm *kvm;
 	struct xarray bindings;
@@ -312,6 +317,38 @@ static pgoff_t kvm_gmem_get_index(struct kvm_memory_slot *slot, gfn_t gfn)
 	return gfn - slot->base_gfn + slot->gmem.pgoff;
 }
 
+static const struct super_operations kvm_gmem_super_operations = {
+	.statfs		= simple_statfs,
+};
+
+static int kvm_gmem_init_fs_context(struct fs_context *fc)
+{
+	struct pseudo_fs_context *ctx;
+
+	if (!init_pseudo(fc, GUEST_MEMORY_MAGIC))
+		return -ENOMEM;
+
+	ctx = fc->fs_private;
+	ctx->ops = &kvm_gmem_super_operations;
+
+	return 0;
+}
+
+static struct file_system_type kvm_gmem_fs = {
+	.name		 = "kvm_guest_memory",
+	.init_fs_context = kvm_gmem_init_fs_context,
+	.kill_sb	 = kill_anon_super,
+};
+
+static void kvm_gmem_init_mount(void)
+{
+	kvm_gmem_mnt = kern_mount(&kvm_gmem_fs);
+	BUG_ON(IS_ERR(kvm_gmem_mnt));
+
+	/* For giggles. Userspace can never map this anyways. */
+	kvm_gmem_mnt->mnt_flags |= MNT_NOEXEC;
+}
+
 static struct file_operations kvm_gmem_fops = {
 	.open		= generic_file_open,
 	.release	= kvm_gmem_release,
@@ -321,11 +358,13 @@ static struct file_operations kvm_gmem_fops = {
 void kvm_gmem_init(struct module *module)
 {
 	kvm_gmem_fops.owner = module;
+
+	kvm_gmem_init_mount();
 }
 
 void kvm_gmem_exit(void)
 {
-
+	kern_unmount(kvm_gmem_mnt);
 }
 
 static int kvm_gmem_migrate_folio(struct address_space *mapping,
@@ -407,11 +446,79 @@ static const struct inode_operations kvm_gmem_iops = {
 	.setattr	= kvm_gmem_setattr,
 };
 
+static struct inode *kvm_gmem_inode_make_secure_inode(const char *name,
+						      loff_t size, u64 flags)
+{
+	const struct qstr qname = QSTR_INIT(name, strlen(name));
+	struct inode *inode;
+	int err;
+
+	inode = alloc_anon_inode(kvm_gmem_mnt->mnt_sb);
+	if (IS_ERR(inode))
+		return inode;
+
+	err = security_inode_init_security_anon(inode, &qname, NULL);
+	if (err) {
+		iput(inode);
+		return ERR_PTR(err);
+	}
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
+	if (!try_module_get(kvm_gmem_fops.owner))
+		goto err;
+
+	inode = kvm_gmem_inode_make_secure_inode(name, size, flags);
+	if (IS_ERR(inode)) {
+		err = PTR_ERR(inode);
+		goto err_put_module;
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
+err_put_module:
+	module_put(kvm_gmem_fops.owner);
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
 
@@ -425,32 +532,16 @@ static int __kvm_gmem_create(struct kvm *kvm, loff_t size, u64 flags)
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

---

## [7] Shivank Garg — 2025-04-08
*Subject: [PATCH RFC v7 6/8] KVM: guest_memfd: Add slab-allocated inode cache*

Add dedicated inode structure (kvm_gmem_inode_info) and slab-allocated
inode cache for guest memory backing, similar to how shmem handles inodes.

This adds the necessary allocation/destruction functions and prepares
for upcoming guest_memfd NUMA policy support changes.

Signed-off-by: Shivank Garg <shivankg@amd.com>
---
 virt/kvm/guest_memfd.c | 52 ++++++++++++++++++++++++++++++++++++++++++
 1 file changed, 52 insertions(+)

diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index 002328569c9e..0ccbb152483a 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -18,6 +18,15 @@ struct kvm_gmem {
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
@@ -317,8 +326,34 @@ static pgoff_t kvm_gmem_get_index(struct kvm_memory_slot *slot, gfn_t gfn)
 	return gfn - slot->base_gfn + slot->gmem.pgoff;
 }
 
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
+
+}
+
+static void kvm_gmem_free_inode(struct inode *inode)
+{
+	kmem_cache_free(kvm_gmem_inode_cachep, KVM_GMEM_I(inode));
+}
+
 static const struct super_operations kvm_gmem_super_operations = {
 	.statfs		= simple_statfs,
+	.alloc_inode	= kvm_gmem_alloc_inode,
+	.destroy_inode	= kvm_gmem_destroy_inode,
+	.free_inode	= kvm_gmem_free_inode,
 };
 
 static int kvm_gmem_init_fs_context(struct fs_context *fc)
@@ -355,16 +390,33 @@ static struct file_operations kvm_gmem_fops = {
 	.fallocate	= kvm_gmem_fallocate,
 };
 
+static void kvm_gmem_init_inode(void *foo)
+{
+	struct kvm_gmem_inode_info *info = foo;
+
+	inode_init_once(&info->vfs_inode);
+}
+
+static void kvm_gmem_init_inodecache(void)
+{
+	kvm_gmem_inode_cachep = kmem_cache_create("kvm_gmem_inode_cache",
+						  sizeof(struct kvm_gmem_inode_info),
+						  0, SLAB_ACCOUNT,
+						  kvm_gmem_init_inode);
+}
+
 void kvm_gmem_init(struct module *module)
 {
 	kvm_gmem_fops.owner = module;
 
+	kvm_gmem_init_inodecache();
 	kvm_gmem_init_mount();
 }
 
 void kvm_gmem_exit(void)
 {
 	kern_unmount(kvm_gmem_mnt);
+	kmem_cache_destroy(kvm_gmem_inode_cachep);
 }
 
 static int kvm_gmem_migrate_folio(struct address_space *mapping,

---

## [8] Shivank Garg — 2025-04-08
*Subject: [PATCH RFC v7 7/8] KVM: guest_memfd: Enforce NUMA mempolicy using shared policy*

Previously, guest-memfd allocations followed local NUMA node id in absence
of process mempolicy, resulting in arbitrary memory allocation.
Moreover, mbind() couldn't be used since memory wasn't mapped to userspace
in the VMM.

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
Signed-off-by: Shivank Garg <shivankg@amd.com>
---
 virt/kvm/guest_memfd.c | 75 ++++++++++++++++++++++++++++++++++++++++--
 1 file changed, 73 insertions(+), 2 deletions(-)

diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index 0ccbb152483a..233d3fd5781c 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -4,6 +4,7 @@
 #include <linux/backing-dev.h>
 #include <linux/falloc.h>
 #include <linux/kvm_host.h>
+#include <linux/mempolicy.h>
 #include <linux/pseudo_fs.h>
 #include <linux/pagemap.h>
 #include <linux/anon_inodes.h>
@@ -19,6 +20,7 @@ struct kvm_gmem {
 };
 
 struct kvm_gmem_inode_info {
+	struct shared_policy policy;
 	struct inode vfs_inode;
 };
 
@@ -27,6 +29,9 @@ static inline struct kvm_gmem_inode_info *KVM_GMEM_I(struct inode *inode)
 	return container_of(inode, struct kvm_gmem_inode_info, vfs_inode);
 }
 
+static struct mempolicy *kvm_gmem_get_pgoff_policy(struct kvm_gmem_inode_info *info,
+						   pgoff_t index);
+
 /**
  * folio_file_pfn - like folio_file_page, but return a pfn.
  * @folio: The folio which contains this index.
@@ -113,7 +118,24 @@ static int kvm_gmem_prepare_folio(struct kvm *kvm, struct kvm_memory_slot *slot,
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
+	folio = filemap_grab_folio_mpol(inode->i_mapping, index, policy,
+					NO_INTERLEAVE_INDEX);
+	mpol_cond_put(policy);
+
+	return folio;
 }
 
 static void kvm_gmem_invalidate_begin(struct kvm_gmem *gmem, pgoff_t start,
@@ -336,12 +358,14 @@ static struct inode *kvm_gmem_alloc_inode(struct super_block *sb)
 	if (!info)
 		return NULL;
 
+	mpol_shared_policy_init(&info->policy, NULL);
+
 	return &info->vfs_inode;
 }
 
 static void kvm_gmem_destroy_inode(struct inode *inode)
 {
-
+	mpol_free_shared_policy(&KVM_GMEM_I(inode)->policy);
 }
 
 static void kvm_gmem_free_inode(struct inode *inode)
@@ -384,7 +408,54 @@ static void kvm_gmem_init_mount(void)
 	kvm_gmem_mnt->mnt_flags |= MNT_NOEXEC;
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
+static const struct vm_operations_struct kvm_gmem_vm_ops = {
+#ifdef CONFIG_NUMA
+	.get_policy	= kvm_gmem_get_policy,
+	.set_policy	= kvm_gmem_set_policy,
+#endif
+};
+
+static int kvm_gmem_mmap(struct file *file, struct vm_area_struct *vma)
+{
+	vma->vm_ops = &kvm_gmem_vm_ops;
+	return 0;
+}
+
 static struct file_operations kvm_gmem_fops = {
+	.mmap		= kvm_gmem_mmap,
 	.open		= generic_file_open,
 	.release	= kvm_gmem_release,
 	.fallocate	= kvm_gmem_fallocate,

---

## [9] Shivank Garg — 2025-04-08
*Subject: [PATCH RFC v7 8/8] KVM: guest_memfd: selftests: Add tests for mmap and NUMA policy support*

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
index ce687f8d248f..2af6d0d8f091 100644
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

## [10] Paul Moore — 2025-04-09
*Subject: Re: [PATCH RFC v7 3/8] security: Export security_inode_init_security_anon
 for KVM guest_memfd*

On Tue, Apr 8, 2025 at 7:25 AM Shivank Garg <shivankg@amd.com> wrote:
>
> KVM guest_memfd is implementing its own inodes to store metadata for

Can you help me understand the timing just a bit more ... do you
expect the move to the core MM code to happen during the lifetime of
this patchset, or is it just some hand-wavy "future date"?  No worries
either way, just trying to understand things a bit better.

> Signed-off-by: Shivank Garg <shivankg@amd.com>
> ---

---

## [11] Christoph Hellwig — 2025-04-10
*Subject: Re: [PATCH RFC v7 3/8] security: Export
 security_inode_init_security_anon for KVM guest_memfd*

On Tue, Apr 08, 2025 at 11:23:57AM +0000, Shivank Garg wrote:
> KVM guest_memfd is implementing its own inodes to store metadata for
> backing memory using a custom filesystem. This requires the ability to

This really should be a EXPORT_SYMBOL_GPL, if at all.

But you really should look into a new interface in anon_inode.c that
can be reused instead of duplicating anonymouns inode logic in kvm.ko.

---

## [12] Christoph Hellwig — 2025-04-10
*Subject: Re: [PATCH RFC v7 5/8] KVM: guest_memfd: Make guest mem use guest
 mem inodes instead of anonymous inodes*

On Tue, Apr 08, 2025 at 11:23:59AM +0000, Shivank Garg wrote:
> From: Ackerley Tng <ackerleytng@google.com>
> 

So why do other alloc_anon_inode callers not need
security_inode_init_security_anon?

---

## [13] Ackerley Tng — 2025-04-10
*Subject: Re: [PATCH RFC v7 7/8] KVM: guest_memfd: Enforce NUMA mempolicy using
 shared policy*

Shivank Garg <shivankg@amd.com> writes:

> Previously, guest-memfd allocations followed local NUMA node id in absence
> of process mempolicy, resulting in arbitrary memory allocation.

What are the pros and cons that you see of storing struct shared_policy
in a containing struct kvm_gmem_inode_info, as opposed to storing it in
inode->i_private?

I've just been using inode->i_private for sharability and hugetlb
metadata and didn't consider this option.

Could one reason be that struct shared_policy is a requirement for all
inodes (not a CONFIG flag) but sharability and hugetlb metadata are both
configurable, possibly at runtime?

>  
> @@ -27,6 +29,9 @@ static inline struct kvm_gmem_inode_info *KVM_GMEM_I(struct inode *inode)

---

## [14] Ackerley Tng — 2025-04-10
*Subject: Re: [PATCH RFC v7 5/8] KVM: guest_memfd: Make guest mem use guest mem
 inodes instead of anonymous inodes*

Christoph Hellwig <hch@infradead.org> writes:

> On Tue, Apr 08, 2025 at 11:23:59AM +0000, Shivank Garg wrote:
>> From: Ackerley Tng <ackerleytng@google.com>

Thanks for this tip!

When I did this refactoring, I was just refactoring
anon_inode_create_getfile(), to set up the guest_memfd inode and file in
separate stages, and anon_inode_create_getfile() was already using
security_inode_init_security_anon().

In the next revision I can remove this call.

Is it too late to remove the call to security_inode_init_security_anon()
though? IIUC it is used by LSMs, which means security modules may
already be assuming this call?

---

## [15] Christoph Hellwig — 2025-04-10
*Subject: Re: [PATCH RFC v7 5/8] KVM: guest_memfd: Make guest mem use guest
 mem inodes instead of anonymous inodes*

On Thu, Apr 10, 2025 at 06:53:15AM -0700, Ackerley Tng wrote:
> > So why do other alloc_anon_inode callers not need
> > security_inode_init_security_anon?

I'd really like to here from the security folks if we need it or not,
both in this case and for other alloc_anon_inode callers.

---

## [16] Shivank Garg — 2025-04-11
*Subject: Re: [PATCH RFC v7 3/8] security: Export
 security_inode_init_security_anon for KVM guest_memfd*

Hi Paul,

On 4/10/2025 1:49 AM, Paul Moore wrote:
> On Tue, Apr 8, 2025 at 7:25 AM Shivank Garg <shivankg@amd.com> wrote:
>>

I am not sure about it, any ideas David?

Thanks,
Shivank

> 
>> Signed-off-by: Shivank Garg <shivankg@amd.com>

---

## [17] Shivank Garg — 2025-04-11
*Subject: Re: [PATCH RFC v7 7/8] KVM: guest_memfd: Enforce NUMA mempolicy using
 shared policy*

On 4/10/2025 7:10 PM, Ackerley Tng wrote:
> Shivank Garg <shivankg@amd.com> writes:
> 

This makes sense.

I considered using i_private but opted for the kvm_gmem_inode_info
container approach finally.
I think it's more extensible if we need to add fields later for new features
and it's more maintainable when the struct grows more complex with time.
It follows the established patterns in other filesystems (shmem, ext4, etc.)
which have proven maintainable over time - so I don't have to worry
about it.
Also, since you're already using i_private for flags, I'd have
needed to create a wrapper struct anyway to contain both policy and flags.

> 
>>

---

## [18] Shivank Garg — 2025-04-11
*Subject: Re: [PATCH RFC v7 3/8] security: Export
 security_inode_init_security_anon for KVM guest_memfd*

On 4/10/2025 2:11 PM, Christoph Hellwig wrote:
> On Tue, Apr 08, 2025 at 11:23:57AM +0000, Shivank Garg wrote:
>> KVM guest_memfd is implementing its own inodes to store metadata for

I agree, it makes sense.
I'll use EXPORT_SYMBOL_GPL in next version and look into reusing reusing
existing logic.

Thanks,
Shivank

---

## [19] David Hildenbrand — 2025-04-22
*Subject: Re: [PATCH RFC v7 3/8] security: Export
 security_inode_init_security_anon for KVM guest_memfd*

On 11.04.25 08:07, Shivank Garg wrote:
> Hi Paul,
> 

Sorry for the late reply.

Hand-wavy future date after this series. Elliot was working on this, but 
IIRC he now has a new job and might no longer be able to work on this.

Ackerley+Patrick started looking into this, and will likely require it 
for other guest_memfd features (hugetlb support, directmap removal).

---

## [20] David Hildenbrand — 2025-04-22
*Subject: Re: [PATCH RFC v7 3/8] security: Export
 security_inode_init_security_anon for KVM guest_memfd*

On 10.04.25 10:41, Christoph Hellwig wrote:
> On Tue, Apr 08, 2025 at 11:23:57AM +0000, Shivank Garg wrote:
>> KVM guest_memfd is implementing its own inodes to store metadata for

I assume you mean combining the alloc_anon_inode()+
security_inode_init_security_anon(), correct?

I can see mm/secretmem.c doing the same thing, so agreed that
we're duplicating it.


Regarding your other mail, I am also starting to wonder where/why
we want security_inode_init_security_anon(). At least for
mm/secretmem.c, it was introduced by:

commit 2bfe15c5261212130f1a71f32a300bcf426443d4
Author: Christian Göttsche <cgzones@googlemail.com>
Date:   Tue Jan 25 15:33:04 2022 +0100

     mm: create security context for memfd_secret inodes
     
     Create a security context for the inodes created by memfd_secret(2) via
     the LSM hook inode_init_security_anon to allow a fine grained control.
     As secret memory areas can affect hibernation and have a global shared
     limit access control might be desirable.
     
     Signed-off-by: Christian Göttsche <cgzones@googlemail.com>
     Signed-off-by: Paul Moore <paul@paul-moore.com>


In combination with Paul's review comment [1]

"
This seems reasonable to me, and I like the idea of labeling the anon
inode as opposed to creating a new set of LSM hooks.  If we want to
apply access control policy to the memfd_secret() fds we are going to
need to attach some sort of LSM state to the inode, we might as well
use the mechanism we already have instead of inventing another one.
"


IIUC, we really only want security_inode_init_security_anon() when there
might be interest to have global access control.


Given that guest_memfd already shares many similarities with guest_memfd
(e.g., pages not swappable/migratable) and might share even more in the future
(e.g., directmap removal), I assume that we want the same thing for guest_memfd.


Would something like the following seem reasonable? We should be adding some
documentation for the new function, and I wonder if S_PRIVATE should actually
be cleared for secretmem + guest_memfd (I have no idea what this "fs-internal" flag
affects).

 From 782a6053268d8a2bddf90ba18c008495b0791710 Mon Sep 17 00:00:00 2001
From: David Hildenbrand <david@redhat.com>
Date: Tue, 22 Apr 2025 19:22:00 +0200
Subject: [PATCH] tmp

Signed-off-by: David Hildenbrand <david@redhat.com>
---
  fs/anon_inodes.c   | 20 ++++++++++++++------
  include/linux/fs.h |  1 +
  mm/secretmem.c     |  9 +--------
  3 files changed, 16 insertions(+), 14 deletions(-)

diff --git a/fs/anon_inodes.c b/fs/anon_inodes.c
index 583ac81669c24..ea51fd582deb4 100644
--- a/fs/anon_inodes.c
+++ b/fs/anon_inodes.c
@@ -55,17 +55,18 @@ static struct file_system_type anon_inode_fs_type = {
  	.kill_sb	= kill_anon_super,
  };
  
-static struct inode *anon_inode_make_secure_inode(
-	const char *name,
-	const struct inode *context_inode)
+static struct inode *anon_inode_make_secure_inode(struct super_block *s,
+		const char *name, const struct inode *context_inode,
+		bool fs_internal)
  {
  	struct inode *inode;
  	int error;
  
-	inode = alloc_anon_inode(anon_inode_mnt->mnt_sb);
+	inode = alloc_anon_inode(s);
  	if (IS_ERR(inode))
  		return inode;
-	inode->i_flags &= ~S_PRIVATE;
+	if (!fs_internal)
+		inode->i_flags &= ~S_PRIVATE;
  	error =	security_inode_init_security_anon(inode, &QSTR(name),
  						  context_inode);
  	if (error) {
@@ -75,6 +76,12 @@ static struct inode *anon_inode_make_secure_inode(
  	return inode;
  }
  
+struct inode *alloc_anon_secure_inode(struct super_block *s, const char *name)
+{
+	return anon_inode_make_secure_inode(s, name, NULL, true);
+}
+EXPORT_SYMBOL_GPL(alloc_anon_secure_inode);
+
  static struct file *__anon_inode_getfile(const char *name,
  					 const struct file_operations *fops,
  					 void *priv, int flags,
@@ -88,7 +95,8 @@ static struct file *__anon_inode_getfile(const char *name,
  		return ERR_PTR(-ENOENT);
  
  	if (make_inode) {
-		inode =	anon_inode_make_secure_inode(name, context_inode);
+		inode =	anon_inode_make_secure_inode(anon_inode_mnt->mnt_sb,
+						     name, context_inode, false);
  		if (IS_ERR(inode)) {
  			file = ERR_CAST(inode);
  			goto err;
diff --git a/include/linux/fs.h b/include/linux/fs.h
index 016b0fe1536e3..0fded2e3c661a 100644
--- a/include/linux/fs.h
+++ b/include/linux/fs.h
@@ -3550,6 +3550,7 @@ extern int simple_write_begin(struct file *file, struct address_space *mapping,
  extern const struct address_space_operations ram_aops;
  extern int always_delete_dentry(const struct dentry *);
  extern struct inode *alloc_anon_inode(struct super_block *);
+extern struct inode *alloc_anon_secure_inode(struct super_block *, const char *);
  extern int simple_nosetlease(struct file *, int, struct file_lease **, void **);
  extern const struct dentry_operations simple_dentry_operations;
  
diff --git a/mm/secretmem.c b/mm/secretmem.c
index 1b0a214ee5580..c0e459e58cb65 100644
--- a/mm/secretmem.c
+++ b/mm/secretmem.c
@@ -195,18 +195,11 @@ static struct file *secretmem_file_create(unsigned long flags)
  	struct file *file;
  	struct inode *inode;
  	const char *anon_name = "[secretmem]";
-	int err;
  
-	inode = alloc_anon_inode(secretmem_mnt->mnt_sb);
+	inode = alloc_anon_secure_inode(secretmem_mnt->mnt_sb, anon_name);
  	if (IS_ERR(inode))
  		return ERR_CAST(inode);
  
-	err = security_inode_init_security_anon(inode, &QSTR(anon_name), NULL);
-	if (err) {
-		file = ERR_PTR(err);
-		goto err_free_inode;
-	}
-
  	file = alloc_file_pseudo(inode, secretmem_mnt, "secretmem",
  				 O_RDWR, &secretmem_fops);
  	if (IS_ERR(file))

---
