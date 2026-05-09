---
title: '[RFC PATCH v4 0/3] Add NUMA mempolicy support for KVM guest-memfd'
date: 2025-02-10
last_reply: 2025-02-19
message_count: 14
participants: ['Shivank Garg', 'David Hildenbrand', 'Vlastimil Babka', 'Sean Christopherson']
---

## [1] Shivank Garg — 2025-02-10

KVM's guest-memfd memory backend currently lacks support for NUMA policy
enforcement, causing guest memory allocations to be distributed arbitrarily
across host NUMA nodes regardless of the policy specified by the VMM. This
occurs because conventional userspace NUMA control mechanisms like mbind()
are ineffective with guest-memfd, as the memory isn't directly mapped to
userspace when allocations occur.

For SEV-SNP guests, which use the guest-memfd memory backend, NUMA-aware
memory placement is essential for optimal performance, particularly for
memory-intensive workloads.

This series implements proper NUMA policy support for guest-memfd by:
1. Adding mempolicy-aware allocation APIs to the filemap layer.
2. Implementing get/set_policy vm_ops in the guest_memfd to support the
   shared policy.

With these changes, VMMs can now control guest memory placement by
specifying:
- Policy modes: default, bind, interleave, or preferred
- Host NUMA nodes: List of target nodes for memory allocation

This series builds on the existing guest-memfd support in KVM and provides
a clean integration path for NUMA-aware memory management in confidential
computing environments. The work is primarily focused on supporting SEV-SNP
requirements, though the benefits extend to any VMM using the guest-memfd
backend that needs control over guest memory placement.

This approach suggested by David [1] and also discussed in bi-weekly
guest_memfd upstream call on 2024-11-14 [2].

== Example usage with QEMU (requires patched QEMU from [3]) ==

The QEMU changes[3] needed to support this feature are available at:

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

SEV-SNP enabled host, 6.14.0-rc1, AMD Zen 3, 2 socket 2 NUMA node system
NUMA for Policy Guest Node 0: policy=interleave, host-node=0-1

Test: Allocate and touch 50GB inside guest on node=0.

Generic Kernel (without NUMA supported guest-memfd):
                          Node 0          Node 1           Total
Before running Test:
MemUsed                  9981.60         3312.00        13293.60
After running Test:
MemUsed                 61451.72         3201.62        64653.34

Arbitrary allocations: all ~50GB allocated on node 0.

With NUMA supported guest-memfd:
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

== Earlier postings and changelogs ==

v4:
- Dropped fbind() approach in favor of shared policy support

v3:
- https://lore.kernel.org/linux-mm/20241105164549.154700-1-shivankg@amd.com
- Introduce fbind() syscall and drop the IOCTL-based approach

v2:
- https://lore.kernel.org/linux-mm/20240919094438.10987-1-shivankg@amd.com
- Add fixes suggested by Matthew Wilcox

v1:
- https://lore.kernel.org/linux-mm/20240916165743.201087-1-shivankg@amd.com
- Proposed IOCTL based approach to pass NUMA mempolicy

Shivank Garg (2):
  mm/mempolicy: export memory policy symbols
  KVM: guest_memfd: Enforce NUMA mempolicy using shared policy

Shivansh Dhiman (1):
  mm/filemap: add mempolicy support to the filemap layer

 include/linux/pagemap.h | 40 ++++++++++++++++++++
 mm/filemap.c            | 30 ++++++++++++---
 mm/mempolicy.c          |  6 +++
 virt/kvm/guest_memfd.c  | 84 ++++++++++++++++++++++++++++++++++++++---
 4 files changed, 149 insertions(+), 11 deletions(-)

---

## [2] Shivank Garg — 2025-02-10
*Subject: [RFC PATCH v4 1/3] mm/filemap: add mempolicy support to the filemap layer*

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
 include/linux/pagemap.h | 40 ++++++++++++++++++++++++++++++++++++++++
 mm/filemap.c            | 30 +++++++++++++++++++++++++-----
 2 files changed, 65 insertions(+), 5 deletions(-)

diff --git a/include/linux/pagemap.h b/include/linux/pagemap.h
index 47bfc6b1b632..4ae7fa63cb26 100644
--- a/include/linux/pagemap.h
+++ b/include/linux/pagemap.h
@@ -662,15 +662,25 @@ static inline void *detach_page_private(struct page *page)
 
 #ifdef CONFIG_NUMA
 struct folio *filemap_alloc_folio_noprof(gfp_t gfp, unsigned int order);
+struct folio *filemap_alloc_folio_mpol_noprof(gfp_t gfp, unsigned int order,
+						struct mempolicy *mpol);
 #else
 static inline struct folio *filemap_alloc_folio_noprof(gfp_t gfp, unsigned int order)
 {
 	return folio_alloc_noprof(gfp, order);
 }
+static inline struct folio *filemap_alloc_folio_mpol_noprof(gfp_t gfp,
+						unsigned int order,
+						struct mempolicy *mpol)
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
@@ -762,6 +772,8 @@ static inline fgf_t fgf_set_order(size_t size)
 void *filemap_get_entry(struct address_space *mapping, pgoff_t index);
 struct folio *__filemap_get_folio(struct address_space *mapping, pgoff_t index,
 		fgf_t fgp_flags, gfp_t gfp);
+struct folio *__filemap_get_folio_mpol(struct address_space *mapping,
+		pgoff_t index, fgf_t fgp_flags, gfp_t gfp, struct mempolicy *mpol);
 struct page *pagecache_get_page(struct address_space *mapping, pgoff_t index,
 		fgf_t fgp_flags, gfp_t gfp);
 
@@ -820,6 +832,34 @@ static inline struct folio *filemap_grab_folio(struct address_space *mapping,
 			mapping_gfp_mask(mapping));
 }
 
+/**
+ * filemap_grab_folio_mpol - grab a folio from the page cache
+ * @mapping: The address space to search
+ * @index: The page index
+ * @mpol: The mempolicy to apply
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
index 804d7365680c..c5ea32702774 100644
--- a/mm/filemap.c
+++ b/mm/filemap.c
@@ -1001,8 +1001,13 @@ int filemap_add_folio(struct address_space *mapping, struct folio *folio,
 EXPORT_SYMBOL_GPL(filemap_add_folio);
 
 #ifdef CONFIG_NUMA
-struct folio *filemap_alloc_folio_noprof(gfp_t gfp, unsigned int order)
+struct folio *filemap_alloc_folio_mpol_noprof(gfp_t gfp, unsigned int order,
+			struct mempolicy *mpol)
 {
+	if (mpol)
+		return folio_alloc_mpol_noprof(gfp, order, mpol,
+				NO_INTERLEAVE_INDEX, numa_node_id());
+
 	int n;
 	struct folio *folio;
 
@@ -1018,6 +1023,12 @@ struct folio *filemap_alloc_folio_noprof(gfp_t gfp, unsigned int order)
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
 
@@ -1881,11 +1892,12 @@ void *filemap_get_entry(struct address_space *mapping, pgoff_t index)
 }
 
 /**
- * __filemap_get_folio - Find and get a reference to a folio.
+ * __filemap_get_folio_mpol - Find and get a reference to a folio.
  * @mapping: The address_space to search.
  * @index: The page index.
  * @fgp_flags: %FGP flags modify how the folio is returned.
  * @gfp: Memory allocation flags to use if %FGP_CREAT is specified.
+ * @mpol: The mempolicy to apply.
  *
  * Looks up the page cache entry at @mapping & @index.
  *
@@ -1896,8 +1908,8 @@ void *filemap_get_entry(struct address_space *mapping, pgoff_t index)
  *
  * Return: The found folio or an ERR_PTR() otherwise.
  */
-struct folio *__filemap_get_folio(struct address_space *mapping, pgoff_t index,
-		fgf_t fgp_flags, gfp_t gfp)
+struct folio *__filemap_get_folio_mpol(struct address_space *mapping, pgoff_t index,
+		fgf_t fgp_flags, gfp_t gfp, struct mempolicy *mpol)
 {
 	struct folio *folio;
 
@@ -1967,7 +1979,7 @@ struct folio *__filemap_get_folio(struct address_space *mapping, pgoff_t index,
 			err = -ENOMEM;
 			if (order > min_order)
 				alloc_gfp |= __GFP_NORETRY | __GFP_NOWARN;
-			folio = filemap_alloc_folio(alloc_gfp, order);
+			folio = filemap_alloc_folio_mpol(alloc_gfp, order, mpol);
 			if (!folio)
 				continue;
 
@@ -2003,6 +2015,14 @@ struct folio *__filemap_get_folio(struct address_space *mapping, pgoff_t index,
 		folio_clear_dropbehind(folio);
 	return folio;
 }
+EXPORT_SYMBOL(__filemap_get_folio_mpol);
+
+struct folio *__filemap_get_folio(struct address_space *mapping, pgoff_t index,
+		fgf_t fgp_flags, gfp_t gfp)
+{
+	return __filemap_get_folio_mpol(mapping, index,
+			fgp_flags, gfp, NULL);
+}
 EXPORT_SYMBOL(__filemap_get_folio);
 
 static inline struct folio *find_get_entry(struct xa_state *xas, pgoff_t max,

---

## [3] Shivank Garg — 2025-02-10
*Subject: [RFC PATCH v4 2/3] mm/mempolicy: export memory policy symbols*

Export memory policy related symbols needed by the KVM guest-memfd to
implement NUMA policy support.

These symbols are required to implement per-memory region NUMA policies
for guest memory, allowing VMMs to control guest memory placement across
NUMA nodes.

Signed-off-by: Shivank Garg <shivankg@amd.com>
---
 mm/mempolicy.c | 6 ++++++
 1 file changed, 6 insertions(+)

diff --git a/mm/mempolicy.c b/mm/mempolicy.c
index bbaadbeeb291..9c15780cfa63 100644
--- a/mm/mempolicy.c
+++ b/mm/mempolicy.c
@@ -214,6 +214,7 @@ struct mempolicy *get_task_policy(struct task_struct *p)
 
 	return &default_policy;
 }
+EXPORT_SYMBOL(get_task_policy);
 
 static const struct mempolicy_operations {
 	int (*create)(struct mempolicy *pol, const nodemask_t *nodes);
@@ -347,6 +348,7 @@ void __mpol_put(struct mempolicy *pol)
 		return;
 	kmem_cache_free(policy_cache, pol);
 }
+EXPORT_SYMBOL(__mpol_put);
 
 static void mpol_rebind_default(struct mempolicy *pol, const nodemask_t *nodes)
 {
@@ -2736,6 +2738,7 @@ struct mempolicy *mpol_shared_policy_lookup(struct shared_policy *sp,
 	read_unlock(&sp->lock);
 	return pol;
 }
+EXPORT_SYMBOL(mpol_shared_policy_lookup);
 
 static void sp_free(struct sp_node *n)
 {
@@ -3021,6 +3024,7 @@ void mpol_shared_policy_init(struct shared_policy *sp, struct mempolicy *mpol)
 		mpol_put(mpol);	/* drop our incoming ref on sb mpol */
 	}
 }
+EXPORT_SYMBOL(mpol_shared_policy_init);
 
 int mpol_set_shared_policy(struct shared_policy *sp,
 			struct vm_area_struct *vma, struct mempolicy *pol)
@@ -3039,6 +3043,7 @@ int mpol_set_shared_policy(struct shared_policy *sp,
 		sp_free(new);
 	return err;
 }
+EXPORT_SYMBOL(mpol_set_shared_policy);
 
 /* Free a backing policy store on inode delete. */
 void mpol_free_shared_policy(struct shared_policy *sp)
@@ -3057,6 +3062,7 @@ void mpol_free_shared_policy(struct shared_policy *sp)
 	}
 	write_unlock(&sp->lock);
 }
+EXPORT_SYMBOL(mpol_free_shared_policy);
 
 #ifdef CONFIG_NUMA_BALANCING
 static int __initdata numabalancing_override;

---

## [4] Shivank Garg — 2025-02-10
*Subject: [RFC PATCH v4 3/3] KVM: guest_memfd: Enforce NUMA mempolicy using shared policy*

Previously, guest-memfd allocations were following local NUMA node id
in absence of process mempolicy, resulting in random memory allocation.
Moreover, mbind() couldn't be used since memory wasn't mapped to userspace
in VMM.

Enable NUMA policy support by implementing vm_ops for guest-memfd mmap
operation. This allows VMM to map the memory and use mbind() to set the
desired NUMA policy. The policy is then retrieved via
mpol_shared_policy_lookup() and passed to filemap_grab_folio_mpol() to
ensure that allocations follow the specified memory policy.

This enables VMM to control guest memory NUMA placement by calling mbind()
on the mapped memory regions, providing fine-grained control over guest
memory allocation across NUMA nodes.

Suggested-by: David Hildenbrand <david@redhat.com>
Signed-off-by: Shivank Garg <shivankg@amd.com>
---
 virt/kvm/guest_memfd.c | 84 +++++++++++++++++++++++++++++++++++++++---
 1 file changed, 78 insertions(+), 6 deletions(-)

diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index b2aa6bf24d3a..e1ea8cb292fa 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -2,6 +2,7 @@
 #include <linux/backing-dev.h>
 #include <linux/falloc.h>
 #include <linux/kvm_host.h>
+#include <linux/mempolicy.h>
 #include <linux/pagemap.h>
 #include <linux/anon_inodes.h>
 
@@ -11,8 +12,13 @@ struct kvm_gmem {
 	struct kvm *kvm;
 	struct xarray bindings;
 	struct list_head entry;
+	struct shared_policy policy;
 };
 
+static struct mempolicy *kvm_gmem_get_pgoff_policy(struct kvm_gmem *gmem,
+						   pgoff_t index,
+						   pgoff_t *ilx);
+
 /**
  * folio_file_pfn - like folio_file_page, but return a pfn.
  * @folio: The folio which contains this index.
@@ -96,10 +102,20 @@ static int kvm_gmem_prepare_folio(struct kvm *kvm, struct kvm_memory_slot *slot,
  * Ignore accessed, referenced, and dirty flags.  The memory is
  * unevictable and there is no storage to write back to.
  */
-static struct folio *kvm_gmem_get_folio(struct inode *inode, pgoff_t index)
+static struct folio *kvm_gmem_get_folio(struct file *file, pgoff_t index)
 {
 	/* TODO: Support huge pages. */
-	return filemap_grab_folio(inode->i_mapping, index);
+	struct folio *folio = NULL;
+	struct inode *inode = file_inode(file);
+	struct kvm_gmem *gmem = file->private_data;
+	struct mempolicy *policy;
+	pgoff_t ilx;
+
+	policy = kvm_gmem_get_pgoff_policy(gmem, index, &ilx);
+	folio =  filemap_grab_folio_mpol(inode->i_mapping, index, policy);
+	mpol_cond_put(policy);
+
+	return folio;
 }
 
 static void kvm_gmem_invalidate_begin(struct kvm_gmem *gmem, pgoff_t start,
@@ -177,8 +193,9 @@ static long kvm_gmem_punch_hole(struct inode *inode, loff_t offset, loff_t len)
 	return 0;
 }
 
-static long kvm_gmem_allocate(struct inode *inode, loff_t offset, loff_t len)
+static long kvm_gmem_allocate(struct file *file, loff_t offset, loff_t len)
 {
+	struct inode *inode = file_inode(file);
 	struct address_space *mapping = inode->i_mapping;
 	pgoff_t start, index, end;
 	int r;
@@ -201,7 +218,7 @@ static long kvm_gmem_allocate(struct inode *inode, loff_t offset, loff_t len)
 			break;
 		}
 
-		folio = kvm_gmem_get_folio(inode, index);
+		folio = kvm_gmem_get_folio(file, index);
 		if (IS_ERR(folio)) {
 			r = PTR_ERR(folio);
 			break;
@@ -241,7 +258,7 @@ static long kvm_gmem_fallocate(struct file *file, int mode, loff_t offset,
 	if (mode & FALLOC_FL_PUNCH_HOLE)
 		ret = kvm_gmem_punch_hole(file_inode(file), offset, len);
 	else
-		ret = kvm_gmem_allocate(file_inode(file), offset, len);
+		ret = kvm_gmem_allocate(file, offset, len);
 
 	if (!ret)
 		file_modified(file);
@@ -290,6 +307,7 @@ static int kvm_gmem_release(struct inode *inode, struct file *file)
 	mutex_unlock(&kvm->slots_lock);
 
 	xa_destroy(&gmem->bindings);
+	mpol_free_shared_policy(&gmem->policy);
 	kfree(gmem);
 
 	kvm_put_kvm(kvm);
@@ -311,8 +329,61 @@ static pgoff_t kvm_gmem_get_index(struct kvm_memory_slot *slot, gfn_t gfn)
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
+						   pgoff_t index,
+						   pgoff_t *ilx)
+{
+	struct mempolicy *mpol;
+
+	*ilx = NO_INTERLEAVE_INDEX;
+	mpol = mpol_shared_policy_lookup(&gmem->policy, index);
+	return mpol ? mpol : get_task_policy(current);
+}
+
+static const struct vm_operations_struct kvm_gmem_vm_ops = {
+	.get_policy	= kvm_gmem_get_policy,
+	.set_policy	= kvm_gmem_set_policy,
+};
+
+static int kvm_gmem_mmap(struct file *file, struct vm_area_struct *vma)
+{
+	file_accessed(file);
+	vma->vm_ops = &kvm_gmem_vm_ops;
+	return 0;
+}
+#else
+static struct mempolicy *kvm_gmem_get_pgoff_policy(struct kvm_gmem *gmem,
+						   pgoff_t index,
+						   pgoff_t *ilx)
+{
+	*ilx = 0;
+	return NULL;
+}
+#endif /* CONFIG_NUMA */
 
 static struct file_operations kvm_gmem_fops = {
+#ifdef CONFIG_NUMA
+	.mmap		= kvm_gmem_mmap,
+#endif
 	.open		= generic_file_open,
 	.release	= kvm_gmem_release,
 	.fallocate	= kvm_gmem_fallocate,
@@ -445,6 +516,7 @@ static int __kvm_gmem_create(struct kvm *kvm, loff_t size, u64 flags)
 	kvm_get_kvm(kvm);
 	gmem->kvm = kvm;
 	xa_init(&gmem->bindings);
+	mpol_shared_policy_init(&gmem->policy, NULL);
 	list_add(&gmem->entry, &inode->i_mapping->i_private_list);
 
 	fd_install(fd, file);
@@ -585,7 +657,7 @@ static struct folio *__kvm_gmem_get_pfn(struct file *file,
 		return ERR_PTR(-EIO);
 	}
 
-	folio = kvm_gmem_get_folio(file_inode(file), index);
+	folio = kvm_gmem_get_folio(file, index);
 	if (IS_ERR(folio))
 		return folio;

---

## [5] David Hildenbrand — 2025-02-12
*Subject: Re: [RFC PATCH v4 1/3] mm/filemap: add mempolicy support to the
 filemap layer*

On 10.02.25 07:32, Shivank Garg wrote:
> From: Shivansh Dhiman <shivansh.dhiman@amd.com>
> 

shmem handles this using custom shmem_alloc_folio()->folio_alloc_mpol().

I'm curious, is there

(1) A way to make shmem also use this new API?
(2) Handle it in guest_memfd manually, like shmem does?

> The existing non-mempolicy APIs remain unchanged and continue to use the
> default allocation behavior.

Two tabs indent on second parameter line, please.

>   #else
>   static inline struct folio *filemap_alloc_folio_noprof(gfp_t gfp, unsigned int order)

Dito.

>   #endif
>   

"The mempolicy to apply when allocating a new folio." ?

> + *
> + * Same as filemap_grab_folio(), except that it allocates the folio using

This should go below the variable declaration. (and indentation on 
second parameter line should align with the first parameter)

>   	int n;
>   	struct folio *folio;

"The mempolicy to apply when allocating a new folio." ?

>    *
>    * Looks up the page cache entry at @mapping & @index.


For guest_memfd, where pages are un-movable and un-swappable, the memory 
policy will never change later.

shmem seems to handle the swap-in case, because it keeps care of 
allocating pages in that case itself.

For ordinary pagecache pages (movable), page migration would likely not 
be aware of the specified mpol; I assume the same applies to shmem?

alloc_migration_target() seems to prefer the current nid (nid = 
folio_nid(src)), but apart from that, does not lookup any mempolicy.

compaction likely handles this by comapcting within a node/zone.

Maybe migration to the right target node on misplacement is handled on a 
higher level lagter (numa hinting faults -> migrate_misplaced_folio). 
Likely at least for anon memory, not sure about unmapped shmem.

---

## [6] David Hildenbrand — 2025-02-12
*Subject: Re: [RFC PATCH v4 2/3] mm/mempolicy: export memory policy symbols*

On 10.02.25 07:32, Shivank Garg wrote:
> Export memory policy related symbols needed by the KVM guest-memfd to
> implement NUMA policy support.

Probably worth mentioning something like

"guest_memfd wants to implement support for NUMA policies just like 
shmem already does using the shared policy infrastructure. As 
guest_memfd currently resides in KVM module code, we have to export the 
relevant symbols.

In the future, guest_memfd might be moved to core-mm, at which point the 
symbols no longer would have to be exported. When/if that happens is 
still unclear."

Acked-by: David Hildenbrand <david@redhat.com>

---

## [7] David Hildenbrand — 2025-02-12
*Subject: Re: [RFC PATCH v4 3/3] KVM: guest_memfd: Enforce NUMA mempolicy using
 shared policy*

On 10.02.25 07:32, Shivank Garg wrote:
> Previously, guest-memfd allocations were following local NUMA node id
> in absence of process mempolicy, resulting in random memory allocation.

Yes, I think that is the right direction, especially with upcoming 
in-place conversion of shared<->private in mind.

> 
> Suggested-by: David Hildenbrand <david@redhat.com>

I'd probably do that change in a separate prep-patch; would remove some 
of the unrelated noise in this patch.

>   {
>   	/* TODO: Support huge pages. */

No need to init folio.

> +	struct inode *inode = file_inode(file);
> +	struct kvm_gmem *gmem = file->private_data;

Prefer reverse christmas-tree (longest line first) as possible.

> +	struct mempolicy *policy;
> +	pgoff_t ilx;

Why do you return the ilx from kvm_gmem_get_pgoff_policy() if it is 
completely unused?

> +
> +	policy = kvm_gmem_get_pgoff_policy(gmem, index, &ilx);

The downside is that we always have to lookup the policy, even if we 
don't have to allocate anything because the pagecache already contains a 
folio.

Would there be a way to lookup if there is something already allcoated 
(fast-path) and fallback to the slow-path (lookup policy+call 
filemap_grab_folio_mpol) only if that failed?

Note that shmem.c does exactly that: shmem_alloc_folio() is only called 
after filemap_get_entry() told us that there is nothing.

> +
> +	return folio;

[...]

> +#ifdef CONFIG_NUMA
> +static int kvm_gmem_set_policy(struct vm_area_struct *vma, struct mempolicy *new)

With Fuad's work, this will be unconditional, and you'd only set the 
kvm_gmem_vm_ops conditionally -- just like shmem.c. Maybe best to 
prepare for that already: allow unconditional mmap (Fuad will implement 
the faulting logic of shared pages, until then all accesses would SIGBUS 
I assume, did you try that?) and only mess with get_policy/set_policy.

---

## [8] Shivank Garg — 2025-02-13
*Subject: Re: [RFC PATCH v4 1/3] mm/filemap: add mempolicy support to the
 filemap layer*

Hi David,

Thanks for the review.

On 2/12/2025 3:33 PM, David Hildenbrand wrote:
> On 10.02.25 07:32, Shivank Garg wrote:
>> From: Shivansh Dhiman <shivansh.dhiman@amd.com>

(1) As you noted later, shmem has unique requirements due to handling swapin.
It does considerable open-coding.
Initially, I was considering simplifying the shmem but it was not possible due
to above constraints. 
One option would be to add shmem's special cases in the filemap and check for
themusing shmem_mapping()?
But, I don't understand the shmem internals well enough to determine if it is
feasible.

(2) I considered handling it manually in guest_memfd like shmem does, but this
would lead to code duplication and more open-coding in guest_memfd. The current
approach seems cleaner.

> Two tabs indent on second parameter line, please.
> 
..
> 
> This should go below the variable declaration. (and indentation on second parameter line should align with the first parameter)
..
> "The mempolicy to apply when allocating a new folio." ?
> 

I'll address all the formatting and documentation issues in next posting.

> 
> For guest_memfd, where pages are un-movable and un-swappable, the memory policy will never change later.

Page migration does handle the NUMA mempolicy using mtc (struct migration_target_control *)
which takes node ID input and allocates on the "preferred" node id. 
The target node in migrate_misplaced_folio() is obtained using get_vma_policy(), so the
per-VMA policy handles proper node placement for mapped pages.
It use current nid (folio_nid(src)) only if NUMA_NO_NODE is passed.

mempolicy.c provides the alloc_migration_target_by_mpol() that allocates according to
NUMA mempolicy, which is used by do_mbind().

> 
> compaction likely handles this by comapcting within a node/zone.

Yes.

Thanks,
Shivank

---

## [9] Shivank Garg — 2025-02-13
*Subject: Re: [RFC PATCH v4 2/3] mm/mempolicy: export memory policy symbols*

On 2/12/2025 3:53 PM, David Hildenbrand wrote:
> On 10.02.25 07:32, Shivank Garg wrote:
>> Export memory policy related symbols needed by the KVM guest-memfd to

Thanks for the suggestion.
I'll add it.

Best Regards,
Shivank

---

## [10] Shivank Garg — 2025-02-13
*Subject: Re: [RFC PATCH v4 3/3] KVM: guest_memfd: Enforce NUMA mempolicy using
 shared policy*

On 2/12/2025 4:09 PM, David Hildenbrand wrote:
> On 10.02.25 07:32, Shivank Garg wrote:
>> Previously, guest-memfd allocations were following local NUMA node id

Yes, I'll separate it.
> 
>>   {

I'll remove the kvm_gmem_get_pgoff_policy.

> The downside is that we always have to lookup the policy, even if we don't have to allocate anything because the pagecache already contains a folio.
> 
Yes, It's doable.
A filemap_get_folio() for fast-path: If it does not return folio, then falling back to current slowpath.

>> +
>> +    return folio;
...

>> +}
>> +#endif /* CONFIG_NUMA */

Yes, I'll change according to it.
I have to try that out.

Thanks,
Shivank

---

## [11] Vlastimil Babka — 2025-02-17
*Subject: Re: [RFC PATCH v4 2/3] mm/mempolicy: export memory policy symbols*

On 2/10/25 07:32, Shivank Garg wrote:
> Export memory policy related symbols needed by the KVM guest-memfd to
> implement NUMA policy support.

I think we should use EXPORT_SYMBOL_GPL() these days.

Wasn't there also some way to limit the exports to KVM?

> ---
>  mm/mempolicy.c | 6 ++++++

---

## [12] David Hildenbrand — 2025-02-17
*Subject: Re: [RFC PATCH v4 1/3] mm/filemap: add mempolicy support to the
 filemap layer*

> 
> (1) As you noted later, shmem has unique requirements due to handling swapin.

Okay, thanks for looking into this.

> (2) I considered handling it manually in guest_memfd like shmem does, but this
> would lead to code duplication and more open-coding in guest_memfd. The current

Okay, thanks.

> 
>> Two tabs indent on second parameter line, please.

Thanks, LGTM.

---

## [13] Sean Christopherson — 2025-02-18
*Subject: Re: [RFC PATCH v4 2/3] mm/mempolicy: export memory policy symbols*

On Mon, Feb 17, 2025, Vlastimil Babka wrote:
> On 2/10/25 07:32, Shivank Garg wrote:
> > Export memory policy related symbols needed by the KVM guest-memfd to

The infrastructure is still a WIP[1], though when that lands, I definitely plan
on tightening down the KVM-induced exports[2].

[1] https://lore.kernel.org/all/20241202145946.108093528@infradead.org
[2] https://lore.kernel.org/all/ZzJOoFFPjrzYzKir@google.com

---

## [14] Shivank Garg — 2025-02-19
*Subject: Re: [RFC PATCH v4 2/3] mm/mempolicy: export memory policy symbols*

On 2/18/2025 8:52 PM, Sean Christopherson wrote:
> On Mon, Feb 17, 2025, Vlastimil Babka wrote:
>> On 2/10/25 07:32, Shivank Garg wrote:

Thanks Vlastimil, will use EXPORT_SYMBOL_GPL.

>>
>> Wasn't there also some way to limit the exports to KVM?

---
