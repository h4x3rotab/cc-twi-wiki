---
title: '[RFC PATCH v8 0/7] Add NUMA mempolicy support for KVM guest-memfd'
date: 2025-06-18
last_reply: 2025-06-29
message_count: 34
participants: ['Shivank Garg', 'Gregory Price', 'Vlastimil Babka', 'Matthew Wilcox', 'Andrew Morton', 'Gupta, Pankaj', 'Huang, Ying']
---

## [1] Shivank Garg — 2025-06-18

This series introduces NUMA-aware memory placement support for KVM guests
with guest_memfd memory backends. It builds upon Fuad Tabba's work that
enabled host-mapping for guest_memfd memory [1] and can be applied directly
on KVM tree (branch:queue, base commit:7915077245) [2].

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
2. Builds on Fuad's host-mapping work.

Phase2 (future work):
1. NUMA support for private guest_memfd (CoCo VMs).
2. Depends on SNP in-place conversion support [5].

This series provides a clean integration path for NUMA-aware memory
management for guest_memfd and lays the groundwork for future confidential
computing NUMA capabilities.

Please review and provide feedback!

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

[1] https://lore.kernel.org/all/20250611133330.1514028-1-tabba@google.com
[2] https://git.kernel.org/pub/scm/virt/kvm/kvm.git/log/?h=queue
[3] https://lore.kernel.org/all/c1c9591d-218a-495c-957b-ba356c8f8e09@redhat.com
[4] https://docs.google.com/document/d/1M6766BzdY1Lhk7LiR5IqVR8B8mG3cr-cxTxOrAosPOk/edit?tab=t.0#heading=h.svcbod20b5ur
[5] https://lore.kernel.org/all/20250613005400.3694904-1-michael.roth@amd.com
[6] https://lore.kernel.org/all/6fbef654-36e2-4be5-906e-2a648a845278@redhat.com
[7] https://lore.kernel.org/all/2b77e055-98ac-43a1-a7ad-9f9065d7f38f@amd.com
[8] https://lore.kernel.org/all/diqzbjumm167.fsf@ackerleytng-ctop.c.googlers.com

Ackerley Tng (1):
  KVM: guest_memfd: Use guest mem inodes instead of anonymous inodes

Shivank Garg (5):
  security: Export anon_inode_make_secure_inode for KVM guest_memfd
  mm/mempolicy: Export memory policy symbols
  KVM: guest_memfd: Add slab-allocated inode cache
  KVM: guest_memfd: Enforce NUMA mempolicy using shared policy
  KVM: guest_memfd: selftests: Add tests for mmap and NUMA policy
    support

Shivansh Dhiman (1):
  mm/filemap: Add mempolicy support to the filemap layer

 fs/anon_inodes.c                              |  20 +-
 include/linux/fs.h                            |   2 +
 include/linux/pagemap.h                       |  41 +++
 include/uapi/linux/magic.h                    |   1 +
 mm/filemap.c                                  |  27 +-
 mm/mempolicy.c                                |   6 +
 tools/testing/selftests/kvm/Makefile.kvm      |   1 +
 .../testing/selftests/kvm/guest_memfd_test.c  | 123 ++++++++-
 virt/kvm/guest_memfd.c                        | 254 ++++++++++++++++--
 virt/kvm/kvm_main.c                           |   7 +-
 virt/kvm/kvm_mm.h                             |  10 +-
 11 files changed, 456 insertions(+), 36 deletions(-)

---

## [2] Shivank Garg — 2025-06-18
*Subject: [RFC PATCH v8 1/7] security: Export anon_inode_make_secure_inode for KVM guest_memfd*

KVM guest_memfd is implementing its own inodes to store metadata for
backing memory using a custom filesystem. This requires the ability to
allocate an anonymous inode with security context using
anon_inode_make_secure_inode().

As guest_memfd currently resides in the KVM module, we need to export this
symbol for use outside the core kernel. In the future, guest_memfd might be
moved to core-mm, at which point the symbols no longer would have to be
exported. When/if that happens is still unclear.

Signed-off-by: Shivank Garg <shivankg@amd.com>
---

The handling of the S_PRIVATE flag for these inodes was discussed
extensively ([1], [2])
My understanding [3], is that because KVM guest_memfd and secretmem
results in user-visible file descriptors, its inodes should not bypass
LSM security checks. Therefore, anon_inode_make_secure_inode() (as
implemented in this patch) correctly clears the S_PRIVATE flag
set by alloc_anon_inode() to ensure proper security policy enforcement.

[1] https://lore.kernel.org/all/b9e5fa41-62fd-4b3d-bb2d-24ae9d3c33da@redhat.com
[2] https://lore.kernel.org/all/cover.1748890962.git.ackerleytng@google.com
[3] https://lore.kernel.org/all/647ab7a4-790f-4858-acf2-0f6bae5b7f99@amd.com

 fs/anon_inodes.c   | 20 +++++++++++++++++---
 include/linux/fs.h |  2 ++
 2 files changed, 19 insertions(+), 3 deletions(-)

diff --git a/fs/anon_inodes.c b/fs/anon_inodes.c
index e51e7d88980a..441fff40b55a 100644
--- a/fs/anon_inodes.c
+++ b/fs/anon_inodes.c
@@ -98,14 +98,26 @@ static struct file_system_type anon_inode_fs_type = {
 	.kill_sb	= kill_anon_super,
 };
 
-static struct inode *anon_inode_make_secure_inode(
+/**
+ * anon_inode_make_secure_inode - allocate an anonymous inode with security context
+ * @sb:		[in]	Superblock to allocate from
+ * @name:	[in]	Name of the class of the newfile (e.g., "secretmem")
+ * @context_inode:
+ *		[in]	Optional parent inode for security inheritance
+ *
+ * The function ensures proper security initialization through the LSM hook
+ * security_inode_init_security_anon().
+ *
+ * Return:	Pointer to new inode on success, ERR_PTR on failure.
+ */
+struct inode *anon_inode_make_secure_inode(struct super_block *sb,
 	const char *name,
 	const struct inode *context_inode)
 {
 	struct inode *inode;
 	int error;
 
-	inode = alloc_anon_inode(anon_inode_mnt->mnt_sb);
+	inode = alloc_anon_inode(sb);
 	if (IS_ERR(inode))
 		return inode;
 	inode->i_flags &= ~S_PRIVATE;
@@ -118,6 +130,7 @@ static struct inode *anon_inode_make_secure_inode(
 	}
 	return inode;
 }
+EXPORT_SYMBOL_GPL(anon_inode_make_secure_inode);
 
 static struct file *__anon_inode_getfile(const char *name,
 					 const struct file_operations *fops,
@@ -132,7 +145,8 @@ static struct file *__anon_inode_getfile(const char *name,
 		return ERR_PTR(-ENOENT);
 
 	if (make_inode) {
-		inode =	anon_inode_make_secure_inode(name, context_inode);
+		inode =	anon_inode_make_secure_inode(anon_inode_mnt->mnt_sb,
+						     name, context_inode);
 		if (IS_ERR(inode)) {
 			file = ERR_CAST(inode);
 			goto err;
diff --git a/include/linux/fs.h b/include/linux/fs.h
index 96c7925a6551..7ba45be0d7a0 100644
--- a/include/linux/fs.h
+++ b/include/linux/fs.h
@@ -3604,6 +3604,8 @@ extern int simple_write_begin(struct file *file, struct address_space *mapping,
 extern const struct address_space_operations ram_aops;
 extern int always_delete_dentry(const struct dentry *);
 extern struct inode *alloc_anon_inode(struct super_block *);
+extern struct inode *anon_inode_make_secure_inode(struct super_block *sb,
+	const char *name, const struct inode *context_inode);
 extern int simple_nosetlease(struct file *, int, struct file_lease **, void **);
 extern const struct dentry_operations simple_dentry_operations;

---

## [3] Shivank Garg — 2025-06-18
*Subject: [RFC PATCH v8 2/7] KVM: guest_memfd: Use guest mem inodes instead of anonymous inodes*

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

Signed-off-by: Ackerley Tng <ackerleytng@google.com>
Co-developed-by: Fuad Tabba <tabba@google.com>
Signed-off-by: Fuad Tabba <tabba@google.com>
Signed-off-by: Shivank Garg <shivankg@amd.com>
---
 include/uapi/linux/magic.h |   1 +
 virt/kvm/guest_memfd.c     | 134 +++++++++++++++++++++++++++++++------
 virt/kvm/kvm_main.c        |   7 +-
 virt/kvm/kvm_mm.h          |  10 ++-
 4 files changed, 127 insertions(+), 25 deletions(-)

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
index ebdb2d8bf57a..159df462d193 100644
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
@@ -388,9 +392,51 @@ static struct file_operations kvm_gmem_fops = {
 	.fallocate	= kvm_gmem_fallocate,
 };
 
-void kvm_gmem_init(struct module *module)
+static const struct super_operations kvm_gmem_super_operations = {
+	.statfs		= simple_statfs,
+};
+
+static int kvm_gmem_init_fs_context(struct fs_context *fc)
+{
+	struct pseudo_fs_context *ctx;
+
+	if (!init_pseudo(fc, GUEST_MEMFD_MAGIC))
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
+static int kvm_gmem_init_mount(void)
+{
+	kvm_gmem_mnt = kern_mount(&kvm_gmem_fs);
+
+	if (WARN_ON_ONCE(IS_ERR(kvm_gmem_mnt)))
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
@@ -472,11 +518,71 @@ static const struct inode_operations kvm_gmem_iops = {
 	.setattr	= kvm_gmem_setattr,
 };
 
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
 
@@ -490,32 +596,16 @@ static int __kvm_gmem_create(struct kvm *kvm, loff_t size, u64 flags)
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
index e2f6344256ce..88c7dd6770da 100644
--- a/virt/kvm/kvm_main.c
+++ b/virt/kvm/kvm_main.c
@@ -6482,7 +6482,9 @@ int kvm_init(unsigned vcpu_size, unsigned vcpu_align, struct module *module)
 	if (WARN_ON_ONCE(r))
 		goto err_vfio;
 
-	kvm_gmem_init(module);
+	r = kvm_gmem_init(module);
+	if (r)
+		goto err_gmem;
 
 	r = kvm_init_virtualization();
 	if (r)
@@ -6503,6 +6505,8 @@ int kvm_init(unsigned vcpu_size, unsigned vcpu_align, struct module *module)
 err_register:
 	kvm_uninit_virtualization();
 err_virt:
+	kvm_gmem_exit();
+err_gmem:
 	kvm_vfio_ops_exit();
 err_vfio:
 	kvm_async_pf_deinit();
@@ -6534,6 +6538,7 @@ void kvm_exit(void)
 	for_each_possible_cpu(cpu)
 		free_cpumask_var(per_cpu(cpu_kick_mask, cpu));
 	kmem_cache_destroy(kvm_vcpu_cache);
+	kvm_gmem_exit();
 	kvm_vfio_ops_exit();
 	kvm_async_pf_deinit();
 	kvm_irqfd_exit();
diff --git a/virt/kvm/kvm_mm.h b/virt/kvm/kvm_mm.h
index ec311c0d6718..4b825a7f114a 100644
--- a/virt/kvm/kvm_mm.h
+++ b/virt/kvm/kvm_mm.h
@@ -68,16 +68,22 @@ static inline void gfn_to_pfn_cache_invalidate_start(struct kvm *kvm,
 #endif /* HAVE_KVM_PFNCACHE */
 
 #ifdef CONFIG_KVM_GMEM
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
 
+	return 0;
 }
+
+static inline void kvm_gmem_exit(void) {};
+
+static inline void kvm_gmem_init(struct module *module)
 
 static inline int kvm_gmem_bind(struct kvm *kvm,
 					 struct kvm_memory_slot *slot,

---

## [4] Shivank Garg — 2025-06-18
*Subject: [RFC PATCH v8 3/7] mm/filemap: Add mempolicy support to the filemap layer*

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
Co-developed-by: Shivank Garg <shivankg@amd.com>
Signed-off-by: Shivank Garg <shivankg@amd.com>
---
 include/linux/pagemap.h | 41 +++++++++++++++++++++++++++++++++++++++++
 mm/filemap.c            | 27 +++++++++++++++++++++++----
 2 files changed, 64 insertions(+), 4 deletions(-)

diff --git a/include/linux/pagemap.h b/include/linux/pagemap.h
index e63fbfbd5b0f..6558c672740d 100644
--- a/include/linux/pagemap.h
+++ b/include/linux/pagemap.h
@@ -647,15 +647,24 @@ static inline void *detach_page_private(struct page *page)
 
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
@@ -747,6 +756,8 @@ static inline fgf_t fgf_set_order(size_t size)
 void *filemap_get_entry(struct address_space *mapping, pgoff_t index);
 struct folio *__filemap_get_folio(struct address_space *mapping, pgoff_t index,
 		fgf_t fgp_flags, gfp_t gfp);
+struct folio *__filemap_get_folio_mpol(struct address_space *mapping,
+		pgoff_t index, fgf_t fgp_flags, gfp_t gfp, struct mempolicy *mpol, pgoff_t ilx);
 struct page *pagecache_get_page(struct address_space *mapping, pgoff_t index,
 		fgf_t fgp_flags, gfp_t gfp);
 
@@ -805,6 +816,36 @@ static inline struct folio *filemap_grab_folio(struct address_space *mapping,
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
index bada249b9fb7..c7e913b91636 100644
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
@@ -1891,11 +1900,14 @@ void *filemap_get_entry(struct address_space *mapping, pgoff_t index)
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
@@ -1906,8 +1918,8 @@ void *filemap_get_entry(struct address_space *mapping, pgoff_t index)
  *
  * Return: The found folio or an ERR_PTR() otherwise.
  */
-struct folio *__filemap_get_folio(struct address_space *mapping, pgoff_t index,
-		fgf_t fgp_flags, gfp_t gfp)
+struct folio *__filemap_get_folio_mpol(struct address_space *mapping, pgoff_t index,
+		fgf_t fgp_flags, gfp_t gfp, struct mempolicy *mpol, pgoff_t ilx)
 {
 	struct folio *folio;
 
@@ -1977,7 +1989,7 @@ struct folio *__filemap_get_folio(struct address_space *mapping, pgoff_t index,
 			err = -ENOMEM;
 			if (order > min_order)
 				alloc_gfp |= __GFP_NORETRY | __GFP_NOWARN;
-			folio = filemap_alloc_folio(alloc_gfp, order);
+			folio = filemap_alloc_folio_mpol(alloc_gfp, order, mpol, ilx);
 			if (!folio)
 				continue;
 
@@ -2024,6 +2036,13 @@ struct folio *__filemap_get_folio(struct address_space *mapping, pgoff_t index,
 		folio_clear_dropbehind(folio);
 	return folio;
 }
+EXPORT_SYMBOL_GPL(__filemap_get_folio_mpol);
+
+struct folio *__filemap_get_folio(struct address_space *mapping, pgoff_t index,
+		fgf_t fgp_flags, gfp_t gfp)
+{
+	return __filemap_get_folio_mpol(mapping, index, fgp_flags, gfp, NULL, 0);
+}
 EXPORT_SYMBOL(__filemap_get_folio);
 
 static inline struct folio *find_get_entry(struct xa_state *xas, pgoff_t max,

---

## [5] Shivank Garg — 2025-06-18
*Subject: [RFC PATCH v8 4/7] mm/mempolicy: Export memory policy symbols*

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
index 3b1dfd08338b..d98243cdf090 100644
--- a/mm/mempolicy.c
+++ b/mm/mempolicy.c
@@ -354,6 +354,7 @@ struct mempolicy *get_task_policy(struct task_struct *p)
 
 	return &default_policy;
 }
+EXPORT_SYMBOL_GPL(get_task_policy);
 
 static const struct mempolicy_operations {
 	int (*create)(struct mempolicy *pol, const nodemask_t *nodes);
@@ -487,6 +488,7 @@ void __mpol_put(struct mempolicy *pol)
 		return;
 	kmem_cache_free(policy_cache, pol);
 }
+EXPORT_SYMBOL_GPL(__mpol_put);
 
 static void mpol_rebind_default(struct mempolicy *pol, const nodemask_t *nodes)
 {
@@ -2888,6 +2890,7 @@ struct mempolicy *mpol_shared_policy_lookup(struct shared_policy *sp,
 	read_unlock(&sp->lock);
 	return pol;
 }
+EXPORT_SYMBOL_GPL(mpol_shared_policy_lookup);
 
 static void sp_free(struct sp_node *n)
 {
@@ -3173,6 +3176,7 @@ void mpol_shared_policy_init(struct shared_policy *sp, struct mempolicy *mpol)
 		mpol_put(mpol);	/* drop our incoming ref on sb mpol */
 	}
 }
+EXPORT_SYMBOL_GPL(mpol_shared_policy_init);
 
 int mpol_set_shared_policy(struct shared_policy *sp,
 			struct vm_area_struct *vma, struct mempolicy *pol)
@@ -3191,6 +3195,7 @@ int mpol_set_shared_policy(struct shared_policy *sp,
 		sp_free(new);
 	return err;
 }
+EXPORT_SYMBOL_GPL(mpol_set_shared_policy);
 
 /* Free a backing policy store on inode delete. */
 void mpol_free_shared_policy(struct shared_policy *sp)
@@ -3209,6 +3214,7 @@ void mpol_free_shared_policy(struct shared_policy *sp)
 	}
 	write_unlock(&sp->lock);
 }
+EXPORT_SYMBOL_GPL(mpol_free_shared_policy);
 
 #ifdef CONFIG_NUMA_BALANCING
 static int __initdata numabalancing_override;

---

## [6] Shivank Garg — 2025-06-18
*Subject: [RFC PATCH v8 5/7] KVM: guest_memfd: Add slab-allocated inode cache*

Add dedicated inode structure (kvm_gmem_inode_info) and slab-allocated
inode cache for guest memory backing, similar to how shmem handles inodes.

This adds the necessary allocation/destruction functions and prepares
for upcoming guest_memfd NUMA policy support changes.

Signed-off-by: Shivank Garg <shivankg@amd.com>
---
 virt/kvm/guest_memfd.c | 51 ++++++++++++++++++++++++++++++++++++++++++
 1 file changed, 51 insertions(+)

diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index 159df462d193..5a1ce6f5e287 100644
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
@@ -392,8 +401,33 @@ static struct file_operations kvm_gmem_fops = {
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
 static const struct super_operations kvm_gmem_super_operations = {
 	.statfs		= simple_statfs,
+	.alloc_inode	= kvm_gmem_alloc_inode,
+	.destroy_inode	= kvm_gmem_destroy_inode,
+	.free_inode	= kvm_gmem_free_inode,
 };
 
 static int kvm_gmem_init_fs_context(struct fs_context *fc)
@@ -426,10 +460,26 @@ static int kvm_gmem_init_mount(void)
 	return 0;
 }
 
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
 int kvm_gmem_init(struct module *module)
 {
 	kvm_gmem_fops.owner = module;
 
+	kvm_gmem_init_inodecache();
 	return kvm_gmem_init_mount();
 }
 
@@ -437,6 +487,7 @@ void kvm_gmem_exit(void)
 {
 	kern_unmount(kvm_gmem_mnt);
 	kvm_gmem_mnt = NULL;
+	kmem_cache_destroy(kvm_gmem_inode_cachep);
 }
 
 static int kvm_gmem_migrate_folio(struct address_space *mapping,

---

## [7] Shivank Garg — 2025-06-18
*Subject: [RFC PATCH v8 6/7] KVM: guest_memfd: Enforce NUMA mempolicy using shared policy*

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
Signed-off-by: Shivank Garg <shivankg@amd.com>
---
 virt/kvm/guest_memfd.c | 69 ++++++++++++++++++++++++++++++++++++++++--
 1 file changed, 67 insertions(+), 2 deletions(-)

diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index 5a1ce6f5e287..2bd5ff3abd87 100644
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
@@ -112,7 +117,24 @@ static int kvm_gmem_prepare_folio(struct kvm *kvm, struct kvm_memory_slot *slot,
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
@@ -375,12 +397,52 @@ static vm_fault_t kvm_gmem_fault_shared(struct vm_fault *vmf)
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
-	.fault = kvm_gmem_fault_shared,
+	.fault		= kvm_gmem_fault_shared,
+#ifdef CONFIG_NUMA
+	.get_policy	= kvm_gmem_get_policy,
+	.set_policy	= kvm_gmem_set_policy,
+#endif
 };
 
 static int kvm_gmem_mmap(struct file *file, struct vm_area_struct *vma)
 {
+	struct kvm_gmem *gmem = file->private_data;
+	struct kvm *kvm = gmem->kvm;
+
 	if (!kvm_gmem_supports_shared(file_inode(file)))
 		return -ENODEV;
 
@@ -411,11 +473,14 @@ static struct inode *kvm_gmem_alloc_inode(struct super_block *sb)
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

## [8] Shivank Garg — 2025-06-18
*Subject: [RFC PATCH v8 7/7] KVM: guest_memfd: selftests: Add tests for mmap and NUMA policy support*

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
 .../testing/selftests/kvm/guest_memfd_test.c  | 123 +++++++++++++++++-
 2 files changed, 122 insertions(+), 2 deletions(-)

diff --git a/tools/testing/selftests/kvm/Makefile.kvm b/tools/testing/selftests/kvm/Makefile.kvm
index e11ed9e59ab5..f4bb02231d6a 100644
--- a/tools/testing/selftests/kvm/Makefile.kvm
+++ b/tools/testing/selftests/kvm/Makefile.kvm
@@ -273,6 +273,7 @@ pgste-option = $(call try-run, echo 'int main(void) { return 0; }' | \
 	$(CC) -Werror -Wl$(comma)--s390-pgste -x c - -o "$$TMP",-Wl$(comma)--s390-pgste)
 
 LDLIBS += -ldl
+LDLIBS += -lnuma
 LDFLAGS += -pthread $(no-pie-option) $(pgste-option)
 
 LIBKVM_C := $(filter %.c,$(LIBKVM))
diff --git a/tools/testing/selftests/kvm/guest_memfd_test.c b/tools/testing/selftests/kvm/guest_memfd_test.c
index 5da2ed6277ac..a5d261dcfdf5 100644
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
@@ -18,6 +20,7 @@
 #include <sys/mman.h>
 #include <sys/types.h>
 #include <sys/stat.h>
+#include <sys/syscall.h>
 
 #include "kvm_util.h"
 #include "test_util.h"
@@ -115,6 +118,122 @@ static void test_mmap_not_supported(int fd, size_t page_size, size_t total_size)
 	TEST_ASSERT_EQ(mem, MAP_FAILED);
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
 static void test_file_size(int fd, size_t page_size, size_t total_size)
 {
 	struct stat sb;
@@ -275,7 +394,8 @@ static void test_with_type(unsigned long vm_type, uint64_t guest_memfd_flags,
 	if (expect_mmap_allowed) {
 		test_mmap_supported(fd, page_size, total_size);
 		test_fault_overflow(fd, page_size, total_size);
-
+		test_mbind(fd, page_size, total_size);
+		test_numa_allocation(fd, page_size, total_size);
 	} else {
 		test_mmap_not_supported(fd, page_size, total_size);
 	}

---

## [9] Gregory Price — 2025-06-18
*Subject: Re: [RFC PATCH v8 4/7] mm/mempolicy: Export memory policy symbols*

On Wed, Jun 18, 2025 at 11:29:32AM +0000, Shivank Garg wrote:
> KVM guest_memfd wants to implement support for NUMA policies just like
> shmem already does using the shared policy infrastructure. As

I'm concerned that get_task_policy doesn't actually increment the policy
refcount - and mpol_cond_put only decrements the refcount for shared
policies (vma policies) - while __mpol_put decrements it unconditionally.

If you look at how get_task_policy is used internally to mempolicy,
you'll find that it either completes the operation in the context of the
task lock (allocation time) or it calls mpol_get afterwards.

Exporting this as-is creates a triping hazard, if only because get/put
naming implies reference counting.

~Gregory

---

## [10] Shivank Garg — 2025-06-19
*Subject: Re: [RFC PATCH v8 4/7] mm/mempolicy: Export memory policy symbols*

On 6/18/2025 8:42 PM, Gregory Price wrote:
> On Wed, Jun 18, 2025 at 11:29:32AM +0000, Shivank Garg wrote:
>> KVM guest_memfd wants to implement support for NUMA policies just like

I agree. But the semantics of my usage isn't new. shmem use this in same way.

I think the alloc_frozen_pages_noprof(), alloc_pages_bulk_mempolicy_noprof()
calls get_task_policy without task_lock or calling mpol_get.

> 
> Exporting this as-is creates a triping hazard, if only because get/put

Since KVM is the only user, we could consider newly added EXPORT_SYMBOL_GPL_FOR_MODULES(..., "kvm")
to avoid wider exposure.
Does this solve your concern?
Or should we rename these functions.
What should be the preferred approach?

Thanks,
Shivank

---

## [11] Vlastimil Babka — 2025-06-19
*Subject: Re: [RFC PATCH v8 3/7] mm/filemap: Add mempolicy support to the
 filemap layer*

On 6/18/25 13:29, Shivank Garg wrote:
> From: Shivansh Dhiman <shivansh.dhiman@amd.com>
> 

I think __filemap_get_folio() could become a static inline wrapper for
__filemap_get_folio_mpol in pagemap.h.
Otherwise,

Acked-by: Vlastimil Babka <vbabka@suse.cz>

---

## [12] Matthew Wilcox — 2025-06-19
*Subject: Re: [RFC PATCH v8 3/7] mm/filemap: Add mempolicy support to the
 filemap layer*

On Wed, Jun 18, 2025 at 11:29:31AM +0000, Shivank Garg wrote:
> From: Shivansh Dhiman <shivansh.dhiman@amd.com>
> 

You don't use these APIs in this series, so I can't evaludate whether
any of my suggestiosn for improving this patch would actually work.
NACK.  Introduce the APIs *with a user*.  Come on, this isn't a new
requirement.

---

## [13] Vlastimil Babka — 2025-06-19
*Subject: Re: [RFC PATCH v8 4/7] mm/mempolicy: Export memory policy symbols*

On 6/19/25 13:13, Shivank Garg wrote:
> 
> 

Hm it might be a bit misnomer. But fixing that would be out of scope here.

>> refcount - and mpol_cond_put only decrements the refcount for shared
>> policies (vma policies) - while __mpol_put decrements it unconditionally.

Yeah it's only used in the context of the allocation or the get_mempolicy()
syscall and the pointer is not retained somewhere indefinitely. In case of
task's mempolicy, the protection comes from only accessing current task's
policy, and also only the current task can replace it with the
sys_mempolicy() syscall.

> I think the alloc_frozen_pages_noprof(), alloc_pages_bulk_mempolicy_noprof()
> calls get_task_policy without task_lock or calling mpol_get.

Yes.

>> 
>> Exporting this as-is creates a triping hazard, if only because get/put

I don't think we in general consider the act of export a larger hazard for
misuse than misuse by internal code. For e.g. __mpol_put() we have to export
it due to combination of inlined and non-inlined code, but nobody would
really call it directly, but use mpol_put() and mpol_cond_put(). We'd need
to be able to "un-declare" it after the usage in the two inline wrappers to
prevent direct (mis)use by both modules and non-modules.

> Since KVM is the only user, we could consider newly added EXPORT_SYMBOL_GPL_FOR_MODULES(..., "kvm")
> to avoid wider exposure.

Yes that would be preferred now for all the guest_memfd related series in
flight adding exports anywhere.

> Does this solve your concern?
> Or should we rename these functions.

---

## [14] Shivank Garg — 2025-06-20
*Subject: Re: [RFC PATCH v8 3/7] mm/filemap: Add mempolicy support to the
 filemap layer*

On 6/19/2025 9:33 PM, Matthew Wilcox wrote:
> On Wed, Jun 18, 2025 at 11:29:31AM +0000, Shivank Garg wrote:
>> From: Shivansh Dhiman <shivansh.dhiman@amd.com>

Hi willy,

Thank you for the feedback.

filemap_grab_folio_mpol() is used in [Patch 6/7] in kvm_gmem_prepare_folio().

filemap_alloc_folio_mpol() and __filemap_get_folio_mpol()) are internally used
to support the filemap_grab_folio_mpol().

Thanks,
Shivank

---

## [15] Vlastimil Babka — 2025-06-20
*Subject: Re: [RFC PATCH v8 3/7] mm/filemap: Add mempolicy support to the
 filemap layer*

On 6/20/25 07:59, Shivank Garg wrote:
> 
> 

Maybe they can be static then and don't need to be declared in the header.

> Thanks,
> Shivank

---

## [16] Matthew Wilcox — 2025-06-20
*Subject: Re: [RFC PATCH v8 3/7] mm/filemap: Add mempolicy support to the
 filemap layer*

On Fri, Jun 20, 2025 at 11:29:20AM +0530, Shivank Garg wrote:
> filemap_grab_folio_mpol() is used in [Patch 6/7] in kvm_gmem_prepare_folio().
> 

That's not better.  We don't add unused functions, and unless there's
something coming that's going to use them, the entire structure of this
is wrong.

filemap_grab_folio() is a convenience function that avoids us having to
specify the other two arguments to __filemap_get_folio().  Since there's
no indication at this point that there are going to be more callers of
it, filemap_grab_folio_mpol() should not even exist.

I'll send a pair of patches which should be sufficient for your needs.

---

## [17] Matthew Wilcox (Oracle) — 2025-06-20
*Subject: [PATCH 1/2] filemap: Add a mempolicy argument to filemap_alloc_folio()*

guest_memfd needs to support memory policies so add an argument
to filemap_alloc_folio().  All existing users pass NULL, the first
user will show up later in this series.

Signed-off-by: Matthew Wilcox (Oracle) <willy@infradead.org>
---
 fs/bcachefs/fs-io-buffered.c |  2 +-
 fs/btrfs/compression.c       |  3 ++-
 fs/btrfs/verity.c            |  2 +-
 fs/erofs/zdata.c             |  2 +-
 fs/f2fs/compress.c           |  2 +-
 include/linux/pagemap.h      |  6 +++---
 mm/filemap.c                 | 13 +++++++++----
 mm/readahead.c               |  2 +-
 8 files changed, 19 insertions(+), 13 deletions(-)

diff --git a/fs/bcachefs/fs-io-buffered.c b/fs/bcachefs/fs-io-buffered.c
index 66bacdd49f78..392344232b16 100644
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
index 48d07939fee4..8430ccf70887 100644
--- a/fs/btrfs/compression.c
+++ b/fs/btrfs/compression.c
@@ -475,7 +475,8 @@ static noinline int add_ra_bio_pages(struct inode *inode,
 		}
 
 		folio = filemap_alloc_folio(mapping_gfp_constraint(mapping,
-								   ~__GFP_FS), 0);
+								   ~__GFP_FS),
+				0, NULL);
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
index fe8071844724..00e9160a0d24 100644
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
index b3c1df93a163..7ef937dd7624 100644
--- a/fs/f2fs/compress.c
+++ b/fs/f2fs/compress.c
@@ -1942,7 +1942,7 @@ void f2fs_cache_compressed_page(struct f2fs_sb_info *sbi, struct page *page,
 		return;
 	}
 
-	cfolio = filemap_alloc_folio(__GFP_NOWARN | __GFP_IO, 0);
+	cfolio = filemap_alloc_folio(__GFP_NOWARN | __GFP_IO, 0, NULL);
 	if (!cfolio)
 		return;
 
diff --git a/include/linux/pagemap.h b/include/linux/pagemap.h
index e63fbfbd5b0f..c176aeeb38db 100644
--- a/include/linux/pagemap.h
+++ b/include/linux/pagemap.h
@@ -646,9 +646,9 @@ static inline void *detach_page_private(struct page *page)
 }
 
 #ifdef CONFIG_NUMA
-struct folio *filemap_alloc_folio_noprof(gfp_t gfp, unsigned int order);
+struct folio *filemap_alloc_folio_noprof(gfp_t gfp, unsigned int order, struct mempolicy *policy);
 #else
-static inline struct folio *filemap_alloc_folio_noprof(gfp_t gfp, unsigned int order)
+static inline struct folio *filemap_alloc_folio_noprof(gfp_t gfp, unsigned int order, struct mempolicy *policy)
 {
 	return folio_alloc_noprof(gfp, order);
 }
@@ -659,7 +659,7 @@ static inline struct folio *filemap_alloc_folio_noprof(gfp_t gfp, unsigned int o
 
 static inline struct page *__page_cache_alloc(gfp_t gfp)
 {
-	return &filemap_alloc_folio(gfp, 0)->page;
+	return &filemap_alloc_folio(gfp, 0, NULL)->page;
 }
 
 static inline gfp_t readahead_gfp_mask(struct address_space *x)
diff --git a/mm/filemap.c b/mm/filemap.c
index bada249b9fb7..a26df313207d 100644
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
@@ -1977,7 +1982,7 @@ struct folio *__filemap_get_folio(struct address_space *mapping, pgoff_t index,
 			err = -ENOMEM;
 			if (order > min_order)
 				alloc_gfp |= __GFP_NORETRY | __GFP_NOWARN;
-			folio = filemap_alloc_folio(alloc_gfp, order);
+			folio = filemap_alloc_folio(alloc_gfp, order, NULL);
 			if (!folio)
 				continue;
 
@@ -2516,7 +2521,7 @@ static int filemap_create_folio(struct kiocb *iocb, struct folio_batch *fbatch)
 	if (iocb->ki_flags & (IOCB_NOWAIT | IOCB_WAITQ))
 		return -EAGAIN;
 
-	folio = filemap_alloc_folio(mapping_gfp_mask(mapping), min_order);
+	folio = filemap_alloc_folio(mapping_gfp_mask(mapping), min_order, NULL);
 	if (!folio)
 		return -ENOMEM;
 	if (iocb->ki_flags & IOCB_DONTCACHE)
@@ -3854,7 +3859,7 @@ static struct folio *do_read_cache_folio(struct address_space *mapping,
 	folio = filemap_get_folio(mapping, index);
 	if (IS_ERR(folio)) {
 		folio = filemap_alloc_folio(gfp,
-					    mapping_min_folio_order(mapping));
+				mapping_min_folio_order(mapping), NULL);
 		if (!folio)
 			return ERR_PTR(-ENOMEM);
 		index = mapping_align_index(mapping, index);
diff --git a/mm/readahead.c b/mm/readahead.c
index 20d36d6b055e..0b2aec0231e6 100644
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

## [18] Matthew Wilcox (Oracle) — 2025-06-20
*Subject: [PATCH 2/2] filemap: Add __filemap_get_folio_mpol()*

This allows guest_memfd to pass in a memory policy.

Signed-off-by: Matthew Wilcox (Oracle) <willy@infradead.org>
---
 include/linux/pagemap.h | 10 ++++++++--
 mm/filemap.c            | 10 ++++++----
 2 files changed, 14 insertions(+), 6 deletions(-)

diff --git a/include/linux/pagemap.h b/include/linux/pagemap.h
index c176aeeb38db..1cfbf7b8f573 100644
--- a/include/linux/pagemap.h
+++ b/include/linux/pagemap.h
@@ -745,11 +745,17 @@ static inline fgf_t fgf_set_order(size_t size)
 }
 
 void *filemap_get_entry(struct address_space *mapping, pgoff_t index);
-struct folio *__filemap_get_folio(struct address_space *mapping, pgoff_t index,
-		fgf_t fgp_flags, gfp_t gfp);
+struct folio *__filemap_get_folio_mpol(struct address_space *mapping,
+		pgoff_t index, fgf_t fgf_flags, gfp_t gfp, struct mempolicy *);
 struct page *pagecache_get_page(struct address_space *mapping, pgoff_t index,
 		fgf_t fgp_flags, gfp_t gfp);
 
+static inline struct folio *__filemap_get_folio(struct address_space *mapping,
+		pgoff_t index, fgf_t fgf_flags, gfp_t gfp)
+{
+	return __filemap_get_folio_mpol(mapping, index, fgf_flags, gfp, NULL);
+}
+
 /**
  * filemap_get_folio - Find and get a folio.
  * @mapping: The address_space to search.
diff --git a/mm/filemap.c b/mm/filemap.c
index a26df313207d..597d146cbb3a 100644
--- a/mm/filemap.c
+++ b/mm/filemap.c
@@ -1896,11 +1896,12 @@ void *filemap_get_entry(struct address_space *mapping, pgoff_t index)
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
@@ -1911,8 +1912,9 @@ void *filemap_get_entry(struct address_space *mapping, pgoff_t index)
  *
  * Return: The found folio or an ERR_PTR() otherwise.
  */
-struct folio *__filemap_get_folio(struct address_space *mapping, pgoff_t index,
-		fgf_t fgp_flags, gfp_t gfp)
+struct folio *__filemap_get_folio_mpol(struct address_space *mapping,
+		pgoff_t index, fgf_t fgp_flags, gfp_t gfp,
+		struct mempolicy *policy)
 {
 	struct folio *folio;
 
@@ -1982,7 +1984,7 @@ struct folio *__filemap_get_folio(struct address_space *mapping, pgoff_t index,
 			err = -ENOMEM;
 			if (order > min_order)
 				alloc_gfp |= __GFP_NORETRY | __GFP_NOWARN;
-			folio = filemap_alloc_folio(alloc_gfp, order, NULL);
+			folio = filemap_alloc_folio(alloc_gfp, order, policy);
 			if (!folio)
 				continue;

---

## [19] Shivank Garg — 2025-06-20
*Subject: Re: [RFC PATCH v8 3/7] mm/filemap: Add mempolicy support to the
 filemap layer*

On 6/20/2025 8:04 PM, Matthew Wilcox wrote:
> On Fri, Jun 20, 2025 at 11:29:20AM +0530, Shivank Garg wrote:
>> filemap_grab_folio_mpol() is used in [Patch 6/7] in kvm_gmem_prepare_folio().

Thank you willy :)
I'll them add to my series.

Thanks,
Shivank

---

## [20] Matthew Wilcox — 2025-06-20
*Subject: Re: [RFC PATCH v8 3/7] mm/filemap: Add mempolicy support to the
 filemap layer*

On Fri, Jun 20, 2025 at 08:22:49PM +0530, Shivank Garg wrote:
> 
> 

Thanks.  You probably want to touch up the commit messages, I didn't
spend very long on them.

---

## [21] Matthew Wilcox — 2025-06-20
*Subject: Re: [PATCH 2/2] filemap: Add __filemap_get_folio_mpol()*

On Fri, Jun 20, 2025 at 03:34:47PM +0100, Matthew Wilcox (Oracle) wrote:
> +struct folio *__filemap_get_folio_mpol(struct address_space *mapping,
> +		pgoff_t index, fgf_t fgp_flags, gfp_t gfp,

This is missing the EXPORT_SYMBOL_GPL() change.  Sorry about that.
I'm sure you can fix it up ;-)  I only tested "make O=.build-all/ -j16
mm/ fs/" (on an allmodconfig) which doesn't get as far as making sure
that modules can still see all the symbols they need.

---

## [22] Andrew Morton — 2025-06-22
*Subject: Re: [PATCH 2/2] filemap: Add __filemap_get_folio_mpol()*

On Fri, 20 Jun 2025 17:53:15 +0100 Matthew Wilcox <willy@infradead.org> wrote:

> On Fri, Jun 20, 2025 at 03:34:47PM +0100, Matthew Wilcox (Oracle) wrote:
> > +struct folio *__filemap_get_folio_mpol(struct address_space *mapping,

I added this:

--- a/mm/filemap.c~filemap-add-__filemap_get_folio_mpol-fix
+++ a/mm/filemap.c
@@ -2032,7 +2032,7 @@ no_page:
 		folio_clear_dropbehind(folio);
 	return folio;
 }
-EXPORT_SYMBOL(__filemap_get_folio);
+EXPORT_SYMBOL(__filemap_get_folio_mpol);
 
 static inline struct folio *find_get_entry(struct xa_state *xas, pgoff_t max,
 		xa_mark_t mark)
_

---

## [23] Shivank Garg — 2025-06-23
*Subject: Re: [PATCH 2/2] filemap: Add __filemap_get_folio_mpol()*

On 6/23/2025 12:13 AM, Andrew Morton wrote:
> On Fri, 20 Jun 2025 17:53:15 +0100 Matthew Wilcox <willy@infradead.org> wrote:
> 

Hi Andrew,

Thank you for addressing this.

If you don’t mind me asking,
I was curious why we used EXPORT_SYMBOL instead of EXPORT_SYMBOL_GPL here.
I had previously received feedback recommending the use of EXPORT_SYMBOL_GPL
to better align with the kernel’s licensing philosophy, which made sense to me.

Thanks,
Shivank

---

## [24] Andrew Morton — 2025-06-22
*Subject: Re: [PATCH 2/2] filemap: Add __filemap_get_folio_mpol()*

On Mon, 23 Jun 2025 00:32:05 +0530 Shivank Garg <shivankg@amd.com> wrote:

> > -EXPORT_SYMBOL(__filemap_get_folio);
> > +EXPORT_SYMBOL(__filemap_get_folio_mpol);

Making this _GPL would effectively switch __filemap_get_folio() from
non-GPL to GPL.  Leaving it at non-GPL is less disruptive and Matthew's
patch did not have the intention of changing licensing.

Also,

hp2:/usr/src/25> grep "EXPORT_SYMBOL(" mm/filemap.c|wc -l
48
hp2:/usr/src/25> grep "EXPORT_SYMBOL_GPL(" mm/filemap.c|wc -l 
9

---

## [25] Shivank Garg — 2025-06-23
*Subject: Re: [PATCH 2/2] filemap: Add __filemap_get_folio_mpol()*

On 6/23/2025 3:46 AM, Andrew Morton wrote:
> On Mon, 23 Jun 2025 00:32:05 +0530 Shivank Garg <shivankg@amd.com> wrote:
> 

Thank you for the explanation.
This makes sense to me.

Reviewed-by: Shivank Garg <shivankg@amd.com>


Thanks,
Shivank

---

## [26] Gupta, Pankaj — 2025-06-23
*Subject: Re: [PATCH 1/2] filemap: Add a mempolicy argument to
 filemap_alloc_folio()*

> guest_memfd needs to support memory policies so add an argument
> to filemap_alloc_folio().  All existing users pass NULL, the first

Reviewed-by: Pankaj Gupta <pankaj.gupta@amd.com>

> ---
>   fs/bcachefs/fs-io-buffered.c |  2 +-

---

## [27] Gupta, Pankaj — 2025-06-23
*Subject: Re: [PATCH 2/2] filemap: Add __filemap_get_folio_mpol()*

> This allows guest_memfd to pass in a memory policy.
> 

Reviewed-by: Pankaj Gupta <pankaj.gupta@amd.com>

> ---
>   include/linux/pagemap.h | 10 ++++++++--

---

## [28] Vlastimil Babka — 2025-06-23
*Subject: Re: [PATCH 2/2] filemap: Add __filemap_get_folio_mpol()*

On 6/22/25 21:02, Shivank Garg wrote:
> 
> Hi Andrew,

That's the recommendation for new symbols, but this has become effectively a
rename (plus a new parameter) so it's a bit different situation.

> Thanks,
> Shivank

---

## [29] Vlastimil Babka — 2025-06-23
*Subject: Re: [PATCH 1/2] filemap: Add a mempolicy argument to
 filemap_alloc_folio()*

On 6/20/25 16:34, Matthew Wilcox (Oracle) wrote:
> guest_memfd needs to support memory policies so add an argument
> to filemap_alloc_folio().  All existing users pass NULL, the first

Reviewed-by: Vlastimil Babka <vbabka@suse.cz>

---

## [30] Vlastimil Babka — 2025-06-23
*Subject: Re: [PATCH 2/2] filemap: Add __filemap_get_folio_mpol()*

On 6/20/25 16:34, Matthew Wilcox (Oracle) wrote:
> This allows guest_memfd to pass in a memory policy.
> 

Reviewed-by: Vlastimil Babka <vbabka@suse.cz>

---

## [31] Shivank Garg — 2025-06-23
*Subject: Re: [PATCH 2/2] filemap: Add __filemap_get_folio_mpol()*

On 6/23/2025 12:46 PM, Vlastimil Babka wrote:
> On 6/22/25 21:02, Shivank Garg wrote:
>>

agreed, Thanks.

---

## [32] Shivank Garg — 2025-06-23
*Subject: Re: [PATCH 2/2] filemap: Add __filemap_get_folio_mpol()*

On 6/23/2025 3:46 AM, Andrew Morton wrote:
> On Mon, 23 Jun 2025 00:32:05 +0530 Shivank Garg <shivankg@amd.com> wrote:
> 

Can you pick these revised patches:

https://lore.kernel.org/linux-mm/20250623093939.1323623-4-shivankg@amd.com

I did some touch-up on commit description, changed some code alignments to make it more readable
and fixed couple of checkpatch.pl warnings.

Thanks,
Shivank

---

## [33] Huang, Ying — 2025-06-24
*Subject: Re: [RFC PATCH v8 5/7] KVM: guest_memfd: Add slab-allocated inode
 cache*

Shivank Garg <shivankg@amd.com> writes:

> Add dedicated inode structure (kvm_gmem_inode_info) and slab-allocated
> inode cache for guest memory backing, similar to how shmem handles inodes.

Check the return value?

And, I'm not a big fan of (logically) one line function encapsulation.

> +}
> +

kmem_cache_destroy(kvm_gmem_inode_cachep) if kvm_gmem_init_mount()
return with error?

>  }
>  

---
Best Regards,
Huang, Ying

---

## [34] Shivank Garg — 2025-06-29
*Subject: Re: [RFC PATCH v8 5/7] KVM: guest_memfd: Add slab-allocated inode
 cache*

On 6/24/2025 9:46 AM, Huang, Ying wrote:
> Shivank Garg <shivankg@amd.com> writes:
> 

Thanks for the feedback, Ying.
Good catch on the leak!

Regarding the missing error check, I noticed while looking at examples that 
kernel code is sometimes inconsistent with kmem_cache_create() error handling, 
but you're right about checking for failures, So I'll handle them properly.

diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index 7b8c548986d4..8cb83692f7a0 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -530,20 +530,23 @@ static void kvm_gmem_init_inode(void *foo)
        inode_init_once(&info->vfs_inode);
 }

-static void kvm_gmem_init_inodecache(void)
+int kvm_gmem_init(struct module *module)
 {
+       int ret;
+
+       kvm_gmem_fops.owner = module;
        kvm_gmem_inode_cachep = kmem_cache_create("kvm_gmem_inode_cache",
                                                  sizeof(struct kvm_gmem_inode_info),
                                                  0, SLAB_ACCOUNT,
                                                  kvm_gmem_init_inode);
-}
-
-int kvm_gmem_init(struct module *module)
-{
-       kvm_gmem_fops.owner = module;
-
-       kvm_gmem_init_inodecache();
-       return kvm_gmem_init_mount();
+       if (!kvm_gmem_inode_cachep)
+               return -ENOMEM;
+       ret = kvm_gmem_init_mount();
+       if (ret) {
+               kmem_cache_destroy(kvm_gmem_inode_cachep);
+               return ret;
+       }
+       return 0;
 }

Best Regards,
Shivank

---
