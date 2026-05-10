---
title: 'mm: Introduce guest_memfd library'
date: 2024-08-05
last_reply: 2024-08-21
message_count: 41
participants: ['Elliot Berman', 'David Hildenbrand', 'Patrick Roy', 'Manwaring, Derek', 'Ackerley Tng', 'Fuad Tabba', 'Mike Rapoport']
---

## [1] Elliot Berman — 2024-08-05

In preparation for adding more features to KVM's guest_memfd, refactor
and introduce a library which abstracts some of the core-mm decisions
about managing folios associated with the file. The goal of the refactor
serves two purposes:

1. Provide an easier way to reason about memory in guest_memfd. With KVM
supporting multiple confidentiality models (TDX, SEV-SNP, pKVM, ARM
CCA), and coming support for allowing kernel and userspace to access
this memory, it seems necessary to create a stronger abstraction between
core-mm concerns and hypervisor concerns.

2. Provide a common implementation for other hypervisors (Gunyah) to use.

To create a guest_memfd, the owner provides operations to attempt to
unmap the folio and check whether a folio is accessible to the host. The
owner can call guest_memfd_make_inaccessible() to ensure Linux doesn't
have the folio mapped.

The series first introduces a guest_memfd library based on the current
KVM (next) implementation, then adds few features needed for Gunyah and
arm64 pKVM. The Gunyah usage of the series will be posted sepately
shortly after sending this series. I'll work with Fuad on using the
guest_memfd library for arm64 pKVM based on the feedback received.

I've not yet investigated deeply whether having the guest_memfd library
helps live migration. I'd appreciate any input on that part.

Signed-off-by: Elliot Berman <quic_eberman@quicinc.com>
---
Elliot Berman (4):
      mm: Introduce guest_memfd
      kvm: Convert to use mm/guest_memfd
      mm: guest_memfd: Add option to remove guest private memory from direct map
      mm: guest_memfd: Add ability for mmap'ing pages

 include/linux/guest_memfd.h |  59 ++++++
 mm/Kconfig                  |   3 +
 mm/Makefile                 |   1 +
 mm/guest_memfd.c            | 427 ++++++++++++++++++++++++++++++++++++++++++++
 virt/kvm/Kconfig            |   1 +
 virt/kvm/guest_memfd.c      | 299 +++++--------------------------
 virt/kvm/kvm_main.c         |   2 -
 virt/kvm/kvm_mm.h           |   6 -
 8 files changed, 539 insertions(+), 259 deletions(-)
---
base-commit: 8400291e289ee6b2bf9779ff1c83a291501f017b
change-id: 20240722-guest-memfd-lib-455f24115d46

Best regards,

---

## [2] Elliot Berman — 2024-08-05
*Subject: [PATCH RFC 1/4] mm: Introduce guest_memfd*

In preparation for adding more features to KVM's guest_memfd, refactor
and introduce a library which abstracts some of the core-mm decisions
about managing folios associated with the file. The goal of the refactor
serves two purposes:

Provide an easier way to reason about memory in guest_memfd. With KVM
supporting multiple confidentiality models (TDX, SEV-SNP, pKVM, ARM
CCA), and coming support for allowing kernel and userspace to access
this memory, it seems necessary to create a stronger abstraction between
core-mm concerns and hypervisor concerns.

Provide a common implementation for other hypervisors (Gunyah) to use.

Signed-off-by: Elliot Berman <quic_eberman@quicinc.com>
---
 include/linux/guest_memfd.h |  44 +++++++
 mm/Kconfig                  |   3 +
 mm/Makefile                 |   1 +
 mm/guest_memfd.c            | 285 ++++++++++++++++++++++++++++++++++++++++++++
 4 files changed, 333 insertions(+)

diff --git a/include/linux/guest_memfd.h b/include/linux/guest_memfd.h
new file mode 100644
index 000000000000..be56d9d53067
--- /dev/null
+++ b/include/linux/guest_memfd.h
@@ -0,0 +1,44 @@
+/* SPDX-License-Identifier: GPL-2.0-only */
+/*
+ * Copyright (c) 2024 Qualcomm Innovation Center, Inc. All rights reserved.
+ */
+
+#ifndef _LINUX_GUEST_MEMFD_H
+#define _LINUX_GUEST_MEMFD_H
+
+#include <linux/fs.h>
+
+/**
+ * struct guest_memfd_operations - ops provided by owner to manage folios
+ * @invalidate_begin: called when folios should be unmapped from guest.
+ *                    May fail if folios couldn't be unmapped from guest.
+ *                    Required.
+ * @invalidate_end: called after invalidate_begin returns success. Optional.
+ * @prepare: called before a folio is mapped into the guest address space.
+ *           Optional.
+ * @release: Called when releasing the guest_memfd file. Required.
+ */
+struct guest_memfd_operations {
+	int (*invalidate_begin)(struct inode *inode, pgoff_t offset, unsigned long nr);
+	void (*invalidate_end)(struct inode *inode, pgoff_t offset, unsigned long nr);
+	int (*prepare)(struct inode *inode, pgoff_t offset, struct folio *folio);
+	int (*release)(struct inode *inode);
+};
+
+/**
+ * @GUEST_MEMFD_GRAB_UPTODATE: Ensure pages are zeroed/up to date.
+ *                             If trusted hyp will do it, can ommit this flag
+ * @GUEST_MEMFD_PREPARE: Call the ->prepare() op, if present.
+ */
+enum {
+	GUEST_MEMFD_GRAB_UPTODATE	= BIT(0),
+	GUEST_MEMFD_PREPARE		= BIT(1),
+};
+
+struct folio *guest_memfd_grab_folio(struct file *file, pgoff_t index, u32 flags);
+struct file *guest_memfd_alloc(const char *name,
+			       const struct guest_memfd_operations *ops,
+			       loff_t size, unsigned long flags);
+bool is_guest_memfd(struct file *file, const struct guest_memfd_operations *ops);
+
+#endif
diff --git a/mm/Kconfig b/mm/Kconfig
index b72e7d040f78..333f46525695 100644
--- a/mm/Kconfig
+++ b/mm/Kconfig
@@ -1168,6 +1168,9 @@ config SECRETMEM
 	  memory areas visible only in the context of the owning process and
 	  not mapped to other processes and other kernel page tables.
 
+config GUEST_MEMFD
+	tristate
+
 config ANON_VMA_NAME
 	bool "Anonymous VMA name support"
 	depends on PROC_FS && ADVISE_SYSCALLS && MMU
diff --git a/mm/Makefile b/mm/Makefile
index d2915f8c9dc0..e15a95ebeac5 100644
--- a/mm/Makefile
+++ b/mm/Makefile
@@ -122,6 +122,7 @@ obj-$(CONFIG_PAGE_EXTENSION) += page_ext.o
 obj-$(CONFIG_PAGE_TABLE_CHECK) += page_table_check.o
 obj-$(CONFIG_CMA_DEBUGFS) += cma_debug.o
 obj-$(CONFIG_SECRETMEM) += secretmem.o
+obj-$(CONFIG_GUEST_MEMFD) += guest_memfd.o
 obj-$(CONFIG_CMA_SYSFS) += cma_sysfs.o
 obj-$(CONFIG_USERFAULTFD) += userfaultfd.o
 obj-$(CONFIG_IDLE_PAGE_TRACKING) += page_idle.o
diff --git a/mm/guest_memfd.c b/mm/guest_memfd.c
new file mode 100644
index 000000000000..580138b0f9d4
--- /dev/null
+++ b/mm/guest_memfd.c
@@ -0,0 +1,285 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/*
+ * Copyright (c) 2024 Qualcomm Innovation Center, Inc. All rights reserved.
+ */
+
+#include <linux/anon_inodes.h>
+#include <linux/falloc.h>
+#include <linux/guest_memfd.h>
+#include <linux/pagemap.h>
+
+struct folio *guest_memfd_grab_folio(struct file *file, pgoff_t index, u32 flags)
+{
+	struct inode *inode = file_inode(file);
+	struct guest_memfd_operations *ops = inode->i_private;
+	struct folio *folio;
+	int r;
+
+	/* TODO: Support huge pages. */
+	folio = filemap_grab_folio(inode->i_mapping, index);
+	if (IS_ERR(folio))
+		return folio;
+
+	/*
+	 * Use the up-to-date flag to track whether or not the memory has been
+	 * zeroed before being handed off to the guest.  There is no backing
+	 * storage for the memory, so the folio will remain up-to-date until
+	 * it's removed.
+	 */
+	if ((flags & GUEST_MEMFD_GRAB_UPTODATE) &&
+	    !folio_test_uptodate(folio)) {
+		unsigned long nr_pages = folio_nr_pages(folio);
+		unsigned long i;
+
+		for (i = 0; i < nr_pages; i++)
+			clear_highpage(folio_page(folio, i));
+
+		folio_mark_uptodate(folio);
+	}
+
+	if (flags & GUEST_MEMFD_PREPARE && ops->prepare) {
+		r = ops->prepare(inode, index, folio);
+		if (r < 0)
+			goto out_err;
+	}
+
+	/*
+	 * Ignore accessed, referenced, and dirty flags.  The memory is
+	 * unevictable and there is no storage to write back to.
+	 */
+	return folio;
+out_err:
+	folio_unlock(folio);
+	folio_put(folio);
+	return ERR_PTR(r);
+}
+EXPORT_SYMBOL_GPL(guest_memfd_grab_folio);
+
+static long gmem_punch_hole(struct file *file, loff_t offset, loff_t len)
+{
+	struct inode *inode = file_inode(file);
+	const struct guest_memfd_operations *ops = inode->i_private;
+	pgoff_t start = offset >> PAGE_SHIFT;
+	unsigned long nr = len >> PAGE_SHIFT;
+	long ret;
+
+	/*
+	 * Bindings must be stable across invalidation to ensure the start+end
+	 * are balanced.
+	 */
+	filemap_invalidate_lock(inode->i_mapping);
+
+	ret = ops->invalidate_begin(inode, start, nr);
+	if (ret)
+		goto out;
+
+	truncate_inode_pages_range(inode->i_mapping, offset, offset + len - 1);
+
+	if (ops->invalidate_end)
+		ops->invalidate_end(inode, start, nr);
+
+out:
+	filemap_invalidate_unlock(inode->i_mapping);
+
+	return 0;
+}
+
+static long gmem_allocate(struct file *file, loff_t offset, loff_t len)
+{
+	struct inode *inode = file_inode(file);
+	struct address_space *mapping = inode->i_mapping;
+	pgoff_t start, index, end;
+	int r;
+
+	/* Dedicated guest is immutable by default. */
+	if (offset + len > i_size_read(inode))
+		return -EINVAL;
+
+	filemap_invalidate_lock_shared(mapping);
+
+	start = offset >> PAGE_SHIFT;
+	end = (offset + len) >> PAGE_SHIFT;
+
+	r = 0;
+	for (index = start; index < end;) {
+		struct folio *folio;
+
+		if (signal_pending(current)) {
+			r = -EINTR;
+			break;
+		}
+
+		folio = guest_memfd_grab_folio(file, index,
+					       GUEST_MEMFD_GRAB_UPTODATE |
+						       GUEST_MEMFD_PREPARE);
+		if (!folio) {
+			r = -ENOMEM;
+			break;
+		}
+
+		index = folio_next_index(folio);
+
+		folio_unlock(folio);
+		folio_put(folio);
+
+		/* 64-bit only, wrapping the index should be impossible. */
+		if (WARN_ON_ONCE(!index))
+			break;
+
+		cond_resched();
+	}
+
+	filemap_invalidate_unlock_shared(mapping);
+
+	return r;
+}
+
+static long gmem_fallocate(struct file *file, int mode, loff_t offset,
+			   loff_t len)
+{
+	int ret;
+
+	if (!(mode & FALLOC_FL_KEEP_SIZE))
+		return -EOPNOTSUPP;
+
+	if (mode & ~(FALLOC_FL_KEEP_SIZE | FALLOC_FL_PUNCH_HOLE))
+		return -EOPNOTSUPP;
+
+	if (!PAGE_ALIGNED(offset) || !PAGE_ALIGNED(len))
+		return -EINVAL;
+
+	if (mode & FALLOC_FL_PUNCH_HOLE)
+		ret = gmem_punch_hole(file, offset, len);
+	else
+		ret = gmem_allocate(file, offset, len);
+
+	if (!ret)
+		file_modified(file);
+	return ret;
+}
+
+static int gmem_release(struct inode *inode, struct file *file)
+{
+	struct guest_memfd_operations *ops = inode->i_private;
+
+	return ops->release(inode);
+}
+
+static struct file_operations gmem_fops = {
+	.open = generic_file_open,
+	.llseek = generic_file_llseek,
+	.release = gmem_release,
+	.fallocate = gmem_fallocate,
+	.owner = THIS_MODULE,
+};
+
+static int gmem_migrate_folio(struct address_space *mapping, struct folio *dst,
+			      struct folio *src, enum migrate_mode mode)
+{
+	WARN_ON_ONCE(1);
+	return -EINVAL;
+}
+
+static int gmem_error_folio(struct address_space *mapping, struct folio *folio)
+{
+	struct inode *inode = mapping->host;
+	struct guest_memfd_operations *ops = inode->i_private;
+	off_t offset = folio->index;
+	size_t nr = folio_nr_pages(folio);
+	int ret;
+
+	filemap_invalidate_lock_shared(mapping);
+
+	ret = ops->invalidate_begin(inode, offset, nr);
+	if (!ret && ops->invalidate_end)
+		ops->invalidate_end(inode, offset, nr);
+
+	filemap_invalidate_unlock_shared(mapping);
+
+	return ret;
+}
+
+static bool gmem_release_folio(struct folio *folio, gfp_t gfp)
+{
+	struct inode *inode = folio_inode(folio);
+	struct guest_memfd_operations *ops = inode->i_private;
+	off_t offset = folio->index;
+	size_t nr = folio_nr_pages(folio);
+	int ret;
+
+	ret = ops->invalidate_begin(inode, offset, nr);
+	if (ret)
+		return false;
+	if (ops->invalidate_end)
+		ops->invalidate_end(inode, offset, nr);
+
+	return true;
+}
+
+static const struct address_space_operations gmem_aops = {
+	.dirty_folio = noop_dirty_folio,
+	.migrate_folio = gmem_migrate_folio,
+	.error_remove_folio = gmem_error_folio,
+	.release_folio = gmem_release_folio,
+};
+
+static inline bool guest_memfd_check_ops(const struct guest_memfd_operations *ops)
+{
+	return ops->invalidate_begin && ops->release;
+}
+
+struct file *guest_memfd_alloc(const char *name,
+			       const struct guest_memfd_operations *ops,
+			       loff_t size, unsigned long flags)
+{
+	struct inode *inode;
+	struct file *file;
+
+	if (size <= 0 || !PAGE_ALIGNED(size))
+		return ERR_PTR(-EINVAL);
+
+	if (!guest_memfd_check_ops(ops))
+		return ERR_PTR(-EINVAL);
+
+	if (flags)
+		return ERR_PTR(-EINVAL);
+
+	/*
+	 * Use the so called "secure" variant, which creates a unique inode
+	 * instead of reusing a single inode.  Each guest_memfd instance needs
+	 * its own inode to track the size, flags, etc.
+	 */
+	file = anon_inode_create_getfile(name, &gmem_fops, (void *)flags,
+					 O_RDWR, NULL);
+	if (IS_ERR(file))
+		return file;
+
+	file->f_flags |= O_LARGEFILE;
+
+	inode = file_inode(file);
+	WARN_ON(file->f_mapping != inode->i_mapping);
+
+	inode->i_private = (void *)ops; /* discards const qualifier */
+	inode->i_mapping->a_ops = &gmem_aops;
+	inode->i_mode |= S_IFREG;
+	inode->i_size = size;
+	mapping_set_gfp_mask(inode->i_mapping, GFP_HIGHUSER);
+	mapping_set_inaccessible(inode->i_mapping);
+	/* Unmovable mappings are supposed to be marked unevictable as well. */
+	WARN_ON_ONCE(!mapping_unevictable(inode->i_mapping));
+
+	return file;
+}
+EXPORT_SYMBOL_GPL(guest_memfd_alloc);
+
+bool is_guest_memfd(struct file *file, const struct guest_memfd_operations *ops)
+{
+	if (file->f_op != &gmem_fops)
+		return false;
+
+	struct inode *inode = file_inode(file);
+	struct guest_memfd_operations *gops = inode->i_private;
+
+	return ops == gops;
+}
+EXPORT_SYMBOL_GPL(is_guest_memfd);

---

## [3] Elliot Berman — 2024-08-05
*Subject: [PATCH RFC 2/4] kvm: Convert to use mm/guest_memfd*

Use the recently created mm/guest_memfd implementation. No functional
change intended.

Signed-off-by: Elliot Berman <quic_eberman@quicinc.com>
---
 virt/kvm/Kconfig       |   1 +
 virt/kvm/guest_memfd.c | 299 ++++++++-----------------------------------------
 virt/kvm/kvm_main.c    |   2 -
 virt/kvm/kvm_mm.h      |   6 -
 4 files changed, 49 insertions(+), 259 deletions(-)

diff --git a/virt/kvm/Kconfig b/virt/kvm/Kconfig
index b14e14cdbfb9..1147e004fcbd 100644
--- a/virt/kvm/Kconfig
+++ b/virt/kvm/Kconfig
@@ -106,6 +106,7 @@ config KVM_GENERIC_MEMORY_ATTRIBUTES
 
 config KVM_PRIVATE_MEM
        select XARRAY_MULTI
+       select GUEST_MEMFD
        bool
 
 config KVM_GENERIC_PRIVATE_MEM
diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index 1c509c351261..2fe3ff9e5793 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -1,9 +1,7 @@
 // SPDX-License-Identifier: GPL-2.0
-#include <linux/backing-dev.h>
-#include <linux/falloc.h>
+#include <linux/guest_memfd.h>
 #include <linux/kvm_host.h>
 #include <linux/pagemap.h>
-#include <linux/anon_inodes.h>
 
 #include "kvm_mm.h"
 
@@ -13,9 +11,16 @@ struct kvm_gmem {
 	struct list_head entry;
 };
 
-static int kvm_gmem_prepare_folio(struct inode *inode, pgoff_t index, struct folio *folio)
+static inline struct kvm_gmem *inode_to_kvm_gmem(struct inode *inode)
 {
+	struct list_head *gmem_list = &inode->i_mapping->i_private_list;
+
+	return list_first_entry_or_null(gmem_list, struct kvm_gmem, entry);
+}
+
 #ifdef CONFIG_HAVE_KVM_GMEM_PREPARE
+static int kvm_gmem_prepare_folio(struct inode *inode, pgoff_t index, struct folio *folio)
+{
 	struct list_head *gmem_list = &inode->i_mapping->i_private_list;
 	struct kvm_gmem *gmem;
 
@@ -45,57 +50,14 @@ static int kvm_gmem_prepare_folio(struct inode *inode, pgoff_t index, struct fol
 		}
 	}
 
-#endif
 	return 0;
 }
+#endif
 
-static struct folio *kvm_gmem_get_folio(struct inode *inode, pgoff_t index, bool prepare)
-{
-	struct folio *folio;
-
-	/* TODO: Support huge pages. */
-	folio = filemap_grab_folio(inode->i_mapping, index);
-	if (IS_ERR(folio))
-		return folio;
-
-	/*
-	 * Use the up-to-date flag to track whether or not the memory has been
-	 * zeroed before being handed off to the guest.  There is no backing
-	 * storage for the memory, so the folio will remain up-to-date until
-	 * it's removed.
-	 *
-	 * TODO: Skip clearing pages when trusted firmware will do it when
-	 * assigning memory to the guest.
-	 */
-	if (!folio_test_uptodate(folio)) {
-		unsigned long nr_pages = folio_nr_pages(folio);
-		unsigned long i;
-
-		for (i = 0; i < nr_pages; i++)
-			clear_highpage(folio_page(folio, i));
-
-		folio_mark_uptodate(folio);
-	}
-
-	if (prepare) {
-		int r =	kvm_gmem_prepare_folio(inode, index, folio);
-		if (r < 0) {
-			folio_unlock(folio);
-			folio_put(folio);
-			return ERR_PTR(r);
-		}
-	}
-
-	/*
-	 * Ignore accessed, referenced, and dirty flags.  The memory is
-	 * unevictable and there is no storage to write back to.
-	 */
-	return folio;
-}
-
-static void kvm_gmem_invalidate_begin(struct kvm_gmem *gmem, pgoff_t start,
+static int kvm_gmem_invalidate_begin(struct inode *inode, pgoff_t start,
 				      pgoff_t end)
 {
+	struct kvm_gmem *gmem = inode_to_kvm_gmem(inode);
 	bool flush = false, found_memslot = false;
 	struct kvm_memory_slot *slot;
 	struct kvm *kvm = gmem->kvm;
@@ -126,11 +88,14 @@ static void kvm_gmem_invalidate_begin(struct kvm_gmem *gmem, pgoff_t start,
 
 	if (found_memslot)
 		KVM_MMU_UNLOCK(kvm);
+
+	return 0;
 }
 
-static void kvm_gmem_invalidate_end(struct kvm_gmem *gmem, pgoff_t start,
+static void kvm_gmem_invalidate_end(struct inode *inode, pgoff_t start,
 				    pgoff_t end)
 {
+	struct kvm_gmem *gmem = inode_to_kvm_gmem(inode);
 	struct kvm *kvm = gmem->kvm;
 
 	if (xa_find(&gmem->bindings, &start, end - 1, XA_PRESENT)) {
@@ -140,106 +105,9 @@ static void kvm_gmem_invalidate_end(struct kvm_gmem *gmem, pgoff_t start,
 	}
 }
 
-static long kvm_gmem_punch_hole(struct inode *inode, loff_t offset, loff_t len)
-{
-	struct list_head *gmem_list = &inode->i_mapping->i_private_list;
-	pgoff_t start = offset >> PAGE_SHIFT;
-	pgoff_t end = (offset + len) >> PAGE_SHIFT;
-	struct kvm_gmem *gmem;
-
-	/*
-	 * Bindings must be stable across invalidation to ensure the start+end
-	 * are balanced.
-	 */
-	filemap_invalidate_lock(inode->i_mapping);
-
-	list_for_each_entry(gmem, gmem_list, entry)
-		kvm_gmem_invalidate_begin(gmem, start, end);
-
-	truncate_inode_pages_range(inode->i_mapping, offset, offset + len - 1);
-
-	list_for_each_entry(gmem, gmem_list, entry)
-		kvm_gmem_invalidate_end(gmem, start, end);
-
-	filemap_invalidate_unlock(inode->i_mapping);
-
-	return 0;
-}
-
-static long kvm_gmem_allocate(struct inode *inode, loff_t offset, loff_t len)
+static int kvm_gmem_release(struct inode *inode)
 {
-	struct address_space *mapping = inode->i_mapping;
-	pgoff_t start, index, end;
-	int r;
-
-	/* Dedicated guest is immutable by default. */
-	if (offset + len > i_size_read(inode))
-		return -EINVAL;
-
-	filemap_invalidate_lock_shared(mapping);
-
-	start = offset >> PAGE_SHIFT;
-	end = (offset + len) >> PAGE_SHIFT;
-
-	r = 0;
-	for (index = start; index < end; ) {
-		struct folio *folio;
-
-		if (signal_pending(current)) {
-			r = -EINTR;
-			break;
-		}
-
-		folio = kvm_gmem_get_folio(inode, index, true);
-		if (IS_ERR(folio)) {
-			r = PTR_ERR(folio);
-			break;
-		}
-
-		index = folio_next_index(folio);
-
-		folio_unlock(folio);
-		folio_put(folio);
-
-		/* 64-bit only, wrapping the index should be impossible. */
-		if (WARN_ON_ONCE(!index))
-			break;
-
-		cond_resched();
-	}
-
-	filemap_invalidate_unlock_shared(mapping);
-
-	return r;
-}
-
-static long kvm_gmem_fallocate(struct file *file, int mode, loff_t offset,
-			       loff_t len)
-{
-	int ret;
-
-	if (!(mode & FALLOC_FL_KEEP_SIZE))
-		return -EOPNOTSUPP;
-
-	if (mode & ~(FALLOC_FL_KEEP_SIZE | FALLOC_FL_PUNCH_HOLE))
-		return -EOPNOTSUPP;
-
-	if (!PAGE_ALIGNED(offset) || !PAGE_ALIGNED(len))
-		return -EINVAL;
-
-	if (mode & FALLOC_FL_PUNCH_HOLE)
-		ret = kvm_gmem_punch_hole(file_inode(file), offset, len);
-	else
-		ret = kvm_gmem_allocate(file_inode(file), offset, len);
-
-	if (!ret)
-		file_modified(file);
-	return ret;
-}
-
-static int kvm_gmem_release(struct inode *inode, struct file *file)
-{
-	struct kvm_gmem *gmem = file->private_data;
+	struct kvm_gmem *gmem = inode_to_kvm_gmem(inode);
 	struct kvm_memory_slot *slot;
 	struct kvm *kvm = gmem->kvm;
 	unsigned long index;
@@ -265,8 +133,8 @@ static int kvm_gmem_release(struct inode *inode, struct file *file)
 	 * Zap all SPTEs pointed at by this file.  Do not free the backing
 	 * memory, as its lifetime is associated with the inode, not the file.
 	 */
-	kvm_gmem_invalidate_begin(gmem, 0, -1ul);
-	kvm_gmem_invalidate_end(gmem, 0, -1ul);
+	kvm_gmem_invalidate_begin(inode, 0, -1ul);
+	kvm_gmem_invalidate_end(inode, 0, -1ul);
 
 	list_del(&gmem->entry);
 
@@ -293,56 +161,6 @@ static inline struct file *kvm_gmem_get_file(struct kvm_memory_slot *slot)
 	return get_file_active(&slot->gmem.file);
 }
 
-static struct file_operations kvm_gmem_fops = {
-	.open		= generic_file_open,
-	.release	= kvm_gmem_release,
-	.fallocate	= kvm_gmem_fallocate,
-};
-
-void kvm_gmem_init(struct module *module)
-{
-	kvm_gmem_fops.owner = module;
-}
-
-static int kvm_gmem_migrate_folio(struct address_space *mapping,
-				  struct folio *dst, struct folio *src,
-				  enum migrate_mode mode)
-{
-	WARN_ON_ONCE(1);
-	return -EINVAL;
-}
-
-static int kvm_gmem_error_folio(struct address_space *mapping, struct folio *folio)
-{
-	struct list_head *gmem_list = &mapping->i_private_list;
-	struct kvm_gmem *gmem;
-	pgoff_t start, end;
-
-	filemap_invalidate_lock_shared(mapping);
-
-	start = folio->index;
-	end = start + folio_nr_pages(folio);
-
-	list_for_each_entry(gmem, gmem_list, entry)
-		kvm_gmem_invalidate_begin(gmem, start, end);
-
-	/*
-	 * Do not truncate the range, what action is taken in response to the
-	 * error is userspace's decision (assuming the architecture supports
-	 * gracefully handling memory errors).  If/when the guest attempts to
-	 * access a poisoned page, kvm_gmem_get_pfn() will return -EHWPOISON,
-	 * at which point KVM can either terminate the VM or propagate the
-	 * error to userspace.
-	 */
-
-	list_for_each_entry(gmem, gmem_list, entry)
-		kvm_gmem_invalidate_end(gmem, start, end);
-
-	filemap_invalidate_unlock_shared(mapping);
-
-	return MF_DELAYED;
-}
-
 #ifdef CONFIG_HAVE_KVM_GMEM_INVALIDATE
 static void kvm_gmem_free_folio(struct folio *folio)
 {
@@ -354,34 +172,25 @@ static void kvm_gmem_free_folio(struct folio *folio)
 }
 #endif
 
-static const struct address_space_operations kvm_gmem_aops = {
-	.dirty_folio = noop_dirty_folio,
-	.migrate_folio	= kvm_gmem_migrate_folio,
-	.error_remove_folio = kvm_gmem_error_folio,
+static const struct guest_memfd_operations kvm_gmem_ops = {
+	.invalidate_begin = kvm_gmem_invalidate_begin,
+	.invalidate_end = kvm_gmem_invalidate_end,
+#ifdef CONFIG_HAVE_KVM_GMEM_PREAPRE
+	.prepare = kvm_gmem_prepare_folio,
+#endif
 #ifdef CONFIG_HAVE_KVM_GMEM_INVALIDATE
 	.free_folio = kvm_gmem_free_folio,
 #endif
+	.release = kvm_gmem_release,
 };
 
-static int kvm_gmem_getattr(struct mnt_idmap *idmap, const struct path *path,
-			    struct kstat *stat, u32 request_mask,
-			    unsigned int query_flags)
+static inline struct kvm_gmem *file_to_kvm_gmem(struct file *file)
 {
-	struct inode *inode = path->dentry->d_inode;
-
-	generic_fillattr(idmap, request_mask, inode, stat);
-	return 0;
-}
+	if (!is_guest_memfd(file, &kvm_gmem_ops))
+		return NULL;
 
-static int kvm_gmem_setattr(struct mnt_idmap *idmap, struct dentry *dentry,
-			    struct iattr *attr)
-{
-	return -EINVAL;
+	return inode_to_kvm_gmem(file_inode(file));
 }
-static const struct inode_operations kvm_gmem_iops = {
-	.getattr	= kvm_gmem_getattr,
-	.setattr	= kvm_gmem_setattr,
-};
 
 static int __kvm_gmem_create(struct kvm *kvm, loff_t size, u64 flags)
 {
@@ -401,31 +210,16 @@ static int __kvm_gmem_create(struct kvm *kvm, loff_t size, u64 flags)
 		goto err_fd;
 	}
 
-	file = anon_inode_create_getfile(anon_name, &kvm_gmem_fops, gmem,
-					 O_RDWR, NULL);
+	file = guest_memfd_alloc(anon_name, &kvm_gmem_ops, size, 0);
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
+	inode = file_inode(file);
 	list_add(&gmem->entry, &inode->i_mapping->i_private_list);
 
 	fd_install(fd, file);
@@ -469,11 +263,8 @@ int kvm_gmem_bind(struct kvm *kvm, struct kvm_memory_slot *slot,
 	if (!file)
 		return -EBADF;
 
-	if (file->f_op != &kvm_gmem_fops)
-		goto err;
-
-	gmem = file->private_data;
-	if (gmem->kvm != kvm)
+	gmem = file_to_kvm_gmem(file);
+	if (!gmem || gmem->kvm != kvm)
 		goto err;
 
 	inode = file_inode(file);
@@ -530,7 +321,9 @@ void kvm_gmem_unbind(struct kvm_memory_slot *slot)
 	if (!file)
 		return;
 
-	gmem = file->private_data;
+	gmem = file_to_kvm_gmem(file);
+	if (!gmem)
+		return;
 
 	filemap_invalidate_lock(file->f_mapping);
 	xa_store_range(&gmem->bindings, start, end - 1, NULL, GFP_KERNEL);
@@ -548,20 +341,24 @@ static int __kvm_gmem_get_pfn(struct file *file, struct kvm_memory_slot *slot,
 	struct kvm_gmem *gmem = file->private_data;
 	struct folio *folio;
 	struct page *page;
-	int r;
+	int r, flags = GUEST_MEMFD_GRAB_UPTODATE;
 
 	if (file != slot->gmem.file) {
 		WARN_ON_ONCE(slot->gmem.file);
 		return -EFAULT;
 	}
 
-	gmem = file->private_data;
-	if (xa_load(&gmem->bindings, index) != slot) {
-		WARN_ON_ONCE(xa_load(&gmem->bindings, index));
+	gmem = file_to_kvm_gmem(file);
+	if (WARN_ON_ONCE(!gmem))
+		return -EINVAL;
+
+	if (WARN_ON_ONCE(xa_load(&gmem->bindings, index) != slot))
 		return -EIO;
-	}
 
-	folio = kvm_gmem_get_folio(file_inode(file), index, prepare);
+	if (prepare)
+		flags |= GUEST_MEMFD_PREPARE;
+
+	folio = guest_memfd_grab_folio(file, index, flags);
 	if (IS_ERR(folio))
 		return PTR_ERR(folio);
 
diff --git a/virt/kvm/kvm_main.c b/virt/kvm/kvm_main.c
index d0788d0a72cc..cad798f4e135 100644
--- a/virt/kvm/kvm_main.c
+++ b/virt/kvm/kvm_main.c
@@ -6516,8 +6516,6 @@ int kvm_init(unsigned vcpu_size, unsigned vcpu_align, struct module *module)
 	if (WARN_ON_ONCE(r))
 		goto err_vfio;
 
-	kvm_gmem_init(module);
-
 	/*
 	 * Registration _must_ be the very last thing done, as this exposes
 	 * /dev/kvm to userspace, i.e. all infrastructure must be setup!
diff --git a/virt/kvm/kvm_mm.h b/virt/kvm/kvm_mm.h
index 715f19669d01..6336a4fdcf50 100644
--- a/virt/kvm/kvm_mm.h
+++ b/virt/kvm/kvm_mm.h
@@ -36,17 +36,11 @@ static inline void gfn_to_pfn_cache_invalidate_start(struct kvm *kvm,
 #endif /* HAVE_KVM_PFNCACHE */
 
 #ifdef CONFIG_KVM_PRIVATE_MEM
-void kvm_gmem_init(struct module *module);
 int kvm_gmem_create(struct kvm *kvm, struct kvm_create_guest_memfd *args);
 int kvm_gmem_bind(struct kvm *kvm, struct kvm_memory_slot *slot,
 		  unsigned int fd, loff_t offset);
 void kvm_gmem_unbind(struct kvm_memory_slot *slot);
 #else
-static inline void kvm_gmem_init(struct module *module)
-{
-
-}
-
 static inline int kvm_gmem_bind(struct kvm *kvm,
 					 struct kvm_memory_slot *slot,
 					 unsigned int fd, loff_t offset)

---

## [4] Elliot Berman — 2024-08-05
*Subject: [PATCH RFC 3/4] mm: guest_memfd: Add option to remove guest
 private memory from direct map*

This patch was reworked from Patrick's patch:
https://lore.kernel.org/all/20240709132041.3625501-6-roypat@amazon.co.uk/

While guest_memfd is not available to be mapped by userspace, it is
still accessible through the kernel's direct map. This means that in
scenarios where guest-private memory is not hardware protected, it can
be speculatively read and its contents potentially leaked through
hardware side-channels. Removing guest-private memory from the direct
map, thus mitigates a large class of speculative execution issues
[1, Table 1].

Direct map removal do not reuse the `.prepare` machinery, since
`prepare` can be called multiple time, and it is the responsibility of
the preparation routine to not "prepare" the same folio twice [2]. Thus,
instead explicitly check if `filemap_grab_folio` allocated a new folio,
and remove the returned folio from the direct map only if this was the
case.

The patch uses release_folio instead of free_folio to reinsert pages
back into the direct map as by the time free_folio is called,
folio->mapping can already be NULL. This means that a call to
folio_inode inside free_folio might deference a NULL pointer, leaving no
way to access the inode which stores the flags that allow determining
whether the page was removed from the direct map in the first place.

[1]: https://download.vusec.net/papers/quarantine_raid23.pdf

Cc: Patrick Roy <roypat@amazon.co.uk>
Signed-off-by: Elliot Berman <quic_eberman@quicinc.com>
---
 include/linux/guest_memfd.h |  8 ++++++
 mm/guest_memfd.c            | 65 ++++++++++++++++++++++++++++++++++++++++++++-
 2 files changed, 72 insertions(+), 1 deletion(-)

diff --git a/include/linux/guest_memfd.h b/include/linux/guest_memfd.h
index be56d9d53067..f9e4a27aed67 100644
--- a/include/linux/guest_memfd.h
+++ b/include/linux/guest_memfd.h
@@ -25,6 +25,14 @@ struct guest_memfd_operations {
 	int (*release)(struct inode *inode);
 };
 
+/**
+ * @GUEST_MEMFD_FLAG_NO_DIRECT_MAP: When making folios inaccessible by host, also
+ *                                  remove them from the kernel's direct map.
+ */
+enum {
+	GUEST_MEMFD_FLAG_NO_DIRECT_MAP		= BIT(0),
+};
+
 /**
  * @GUEST_MEMFD_GRAB_UPTODATE: Ensure pages are zeroed/up to date.
  *                             If trusted hyp will do it, can ommit this flag
diff --git a/mm/guest_memfd.c b/mm/guest_memfd.c
index 580138b0f9d4..e9d8cab72b28 100644
--- a/mm/guest_memfd.c
+++ b/mm/guest_memfd.c
@@ -7,9 +7,55 @@
 #include <linux/falloc.h>
 #include <linux/guest_memfd.h>
 #include <linux/pagemap.h>
+#include <linux/set_memory.h>
+
+static inline int guest_memfd_folio_private(struct folio *folio)
+{
+	unsigned long nr_pages = folio_nr_pages(folio);
+	unsigned long i;
+	int r;
+
+	for (i = 0; i < nr_pages; i++) {
+		struct page *page = folio_page(folio, i);
+
+		r = set_direct_map_invalid_noflush(page);
+		if (r < 0)
+			goto out_remap;
+	}
+
+	folio_set_private(folio);
+	return 0;
+out_remap:
+	for (; i > 0; i--) {
+		struct page *page = folio_page(folio, i - 1);
+
+		BUG_ON(set_direct_map_default_noflush(page));
+	}
+	return r;
+}
+
+static inline void guest_memfd_folio_clear_private(struct folio *folio)
+{
+	unsigned long start = (unsigned long)folio_address(folio);
+	unsigned long nr = folio_nr_pages(folio);
+	unsigned long i;
+
+	if (!folio_test_private(folio))
+		return;
+
+	for (i = 0; i < nr; i++) {
+		struct page *page = folio_page(folio, i);
+
+		BUG_ON(set_direct_map_default_noflush(page));
+	}
+	flush_tlb_kernel_range(start, start + folio_size(folio));
+
+	folio_clear_private(folio);
+}
 
 struct folio *guest_memfd_grab_folio(struct file *file, pgoff_t index, u32 flags)
 {
+	unsigned long gmem_flags = (unsigned long)file->private_data;
 	struct inode *inode = file_inode(file);
 	struct guest_memfd_operations *ops = inode->i_private;
 	struct folio *folio;
@@ -43,6 +89,12 @@ struct folio *guest_memfd_grab_folio(struct file *file, pgoff_t index, u32 flags
 			goto out_err;
 	}
 
+	if (gmem_flags & GUEST_MEMFD_FLAG_NO_DIRECT_MAP) {
+		r = guest_memfd_folio_private(folio);
+		if (r)
+			goto out_err;
+	}
+
 	/*
 	 * Ignore accessed, referenced, and dirty flags.  The memory is
 	 * unevictable and there is no storage to write back to.
@@ -213,14 +265,25 @@ static bool gmem_release_folio(struct folio *folio, gfp_t gfp)
 	if (ops->invalidate_end)
 		ops->invalidate_end(inode, offset, nr);
 
+	guest_memfd_folio_clear_private(folio);
+
 	return true;
 }
 
+static void gmem_invalidate_folio(struct folio *folio, size_t offset, size_t len)
+{
+	/* not yet supported */
+	BUG_ON(offset || len != folio_size(folio));
+
+	BUG_ON(!gmem_release_folio(folio, 0));
+}
+
 static const struct address_space_operations gmem_aops = {
 	.dirty_folio = noop_dirty_folio,
 	.migrate_folio = gmem_migrate_folio,
 	.error_remove_folio = gmem_error_folio,
 	.release_folio = gmem_release_folio,
+	.invalidate_folio = gmem_invalidate_folio,
 };
 
 static inline bool guest_memfd_check_ops(const struct guest_memfd_operations *ops)
@@ -241,7 +304,7 @@ struct file *guest_memfd_alloc(const char *name,
 	if (!guest_memfd_check_ops(ops))
 		return ERR_PTR(-EINVAL);
 
-	if (flags)
+	if (flags & ~GUEST_MEMFD_FLAG_NO_DIRECT_MAP)
 		return ERR_PTR(-EINVAL);
 
 	/*

---

## [5] Elliot Berman — 2024-08-05
*Subject: [PATCH RFC 4/4] mm: guest_memfd: Add ability for mmap'ing pages*

Confidential/protected guest virtual machines want to share some memory
back with the host Linux. For example, virtqueues allow host and
protected guest to exchange data. In MMU-only isolation of protected
guest virtual machines, the transition between "shared" and "private"
can be done in-place without a trusted hypervisor copying pages.

Add support for this feature and allow Linux to mmap host-accessible
pages. When the owner provides an ->accessible() callback in the
struct guest_memfd_operations, guest_memfd allows folios to be mapped
when the ->accessible() callback returns 0.

To safely make inaccessible:

```
folio = guest_memfd_grab_folio(inode, index, flags);
r = guest_memfd_make_inaccessible(inode, folio);
if (r)
        goto err;

hypervisor_does_guest_mapping(folio);

folio_unlock(folio);
```

hypervisor_does_s2_mapping(folio) should make it so
ops->accessible(...) on those folios fails.

The folio lock ensures atomicity.

Signed-off-by: Elliot Berman <quic_eberman@quicinc.com>
---
 include/linux/guest_memfd.h |  7 ++++
 mm/guest_memfd.c            | 81 ++++++++++++++++++++++++++++++++++++++++++++-
 2 files changed, 87 insertions(+), 1 deletion(-)

diff --git a/include/linux/guest_memfd.h b/include/linux/guest_memfd.h
index f9e4a27aed67..edcb4ba60cb0 100644
--- a/include/linux/guest_memfd.h
+++ b/include/linux/guest_memfd.h
@@ -16,12 +16,18 @@
  * @invalidate_end: called after invalidate_begin returns success. Optional.
  * @prepare: called before a folio is mapped into the guest address space.
  *           Optional.
+ * @accessible: called after prepare returns success and before it's mapped
+ *              into the guest address space. Returns 0 if the folio can be
+ *              accessed.
+ *              Optional. If not present, assumes folios are never accessible.
  * @release: Called when releasing the guest_memfd file. Required.
  */
 struct guest_memfd_operations {
 	int (*invalidate_begin)(struct inode *inode, pgoff_t offset, unsigned long nr);
 	void (*invalidate_end)(struct inode *inode, pgoff_t offset, unsigned long nr);
 	int (*prepare)(struct inode *inode, pgoff_t offset, struct folio *folio);
+	int (*accessible)(struct inode *inode, struct folio *folio,
+			  pgoff_t offset, unsigned long nr);
 	int (*release)(struct inode *inode);
 };
 
@@ -48,5 +54,6 @@ struct file *guest_memfd_alloc(const char *name,
 			       const struct guest_memfd_operations *ops,
 			       loff_t size, unsigned long flags);
 bool is_guest_memfd(struct file *file, const struct guest_memfd_operations *ops);
+int guest_memfd_make_inaccessible(struct file *file, struct folio *folio);
 
 #endif
diff --git a/mm/guest_memfd.c b/mm/guest_memfd.c
index e9d8cab72b28..6b5609932ca5 100644
--- a/mm/guest_memfd.c
+++ b/mm/guest_memfd.c
@@ -9,6 +9,8 @@
 #include <linux/pagemap.h>
 #include <linux/set_memory.h>
 
+#include "internal.h"
+
 static inline int guest_memfd_folio_private(struct folio *folio)
 {
 	unsigned long nr_pages = folio_nr_pages(folio);
@@ -89,7 +91,7 @@ struct folio *guest_memfd_grab_folio(struct file *file, pgoff_t index, u32 flags
 			goto out_err;
 	}
 
-	if (gmem_flags & GUEST_MEMFD_FLAG_NO_DIRECT_MAP) {
+	if (!ops->accessible && (gmem_flags & GUEST_MEMFD_FLAG_NO_DIRECT_MAP)) {
 		r = guest_memfd_folio_private(folio);
 		if (r)
 			goto out_err;
@@ -107,6 +109,82 @@ struct folio *guest_memfd_grab_folio(struct file *file, pgoff_t index, u32 flags
 }
 EXPORT_SYMBOL_GPL(guest_memfd_grab_folio);
 
+int guest_memfd_make_inaccessible(struct file *file, struct folio *folio)
+{
+	unsigned long gmem_flags = (unsigned long)file->private_data;
+	unsigned long i;
+	int r;
+
+	unmap_mapping_folio(folio);
+
+	/**
+	 * We can't use the refcount. It might be elevated due to
+	 * guest/vcpu trying to access same folio as another vcpu
+	 * or because userspace is trying to access folio for same reason
+	 *
+	 * folio_lock serializes the transitions between (in)accessible
+	 */
+	if (folio_maybe_dma_pinned(folio))
+		return -EBUSY;
+
+	if (gmem_flags & GUEST_MEMFD_FLAG_NO_DIRECT_MAP) {
+		r = guest_memfd_folio_private(folio);
+		if (r)
+			return r;
+	}
+
+	return 0;
+}
+
+static vm_fault_t gmem_fault(struct vm_fault *vmf)
+{
+	struct file *file = vmf->vma->vm_file;
+	struct inode *inode = file_inode(file);
+	const struct guest_memfd_operations *ops = inode->i_private;
+	struct folio *folio;
+	pgoff_t off;
+	int r;
+
+	folio = guest_memfd_grab_folio(file, vmf->pgoff, GUEST_MEMFD_GRAB_UPTODATE);
+	if (!folio)
+		return VM_FAULT_SIGBUS;
+
+	off = vmf->pgoff & (folio_nr_pages(folio) - 1);
+	r = ops->accessible(inode, folio, off, 1);
+	if (r) {
+		folio_unlock(folio);
+		folio_put(folio);
+		return VM_FAULT_SIGBUS;
+	}
+
+	guest_memfd_folio_clear_private(folio);
+
+	vmf->page = folio_page(folio, off);
+
+	return VM_FAULT_LOCKED;
+}
+
+static const struct vm_operations_struct gmem_vm_ops = {
+	.fault = gmem_fault,
+};
+
+static int gmem_mmap(struct file *file, struct vm_area_struct *vma)
+{
+	const struct guest_memfd_operations *ops = file_inode(file)->i_private;
+
+	if (!ops->accessible)
+		return -EPERM;
+
+	/* No support for private mappings to avoid COW.  */
+	if ((vma->vm_flags & (VM_SHARED | VM_MAYSHARE)) !=
+	    (VM_SHARED | VM_MAYSHARE))
+		return -EINVAL;
+
+	file_accessed(file);
+	vma->vm_ops = &gmem_vm_ops;
+	return 0;
+}
+
 static long gmem_punch_hole(struct file *file, loff_t offset, loff_t len)
 {
 	struct inode *inode = file_inode(file);
@@ -220,6 +298,7 @@ static int gmem_release(struct inode *inode, struct file *file)
 static struct file_operations gmem_fops = {
 	.open = generic_file_open,
 	.llseek = generic_file_llseek,
+	.mmap = gmem_mmap,
 	.release = gmem_release,
 	.fallocate = gmem_fallocate,
 	.owner = THIS_MODULE,

---

## [6] David Hildenbrand — 2024-08-06
*Subject: Re: [PATCH RFC 1/4] mm: Introduce guest_memfd*

On 05.08.24 20:34, Elliot Berman wrote:
> In preparation for adding more features to KVM's guest_memfd, refactor
> and introduce a library which abstracts some of the core-mm decisions

Instead of "Introduce guest_memfd" and "Convert to use mm/guest_memfd", 
I suggest a single patch that factors out guest_memfd into core-mm.

Or is there any particular reason for the split?

---

## [7] David Hildenbrand — 2024-08-06
*Subject: Re: [PATCH RFC 4/4] mm: guest_memfd: Add ability for mmap'ing pages*

>   
> -	if (gmem_flags & GUEST_MEMFD_FLAG_NO_DIRECT_MAP) {

As discussed, that's insufficient. We really have to drive the refcount 
to 1 -- the single reference we expect.

What is the exact problem you are running into here? Who can just grab a 
reference and maybe do nasty things with it?

---

## [8] David Hildenbrand — 2024-08-06
*Subject: Re: [PATCH RFC 3/4] mm: guest_memfd: Add option to remove guest
 private memory from direct map*

On 05.08.24 20:34, Elliot Berman wrote:
> This patch was reworked from Patrick's patch:
> https://lore.kernel.org/all/20240709132041.3625501-6-roypat@amazon.co.uk/

I think you have to point out here that the speculative execution issues 
are primarily only an issue when guest_memfd private memory is used 
without TDX and friends where the memory would be encrypted either way.

Or am I wrong?

> 
> Direct map removal do not reuse the `.prepare` machinery, since

Should we start introducing the concept of private and shared first, 
such that we can then say that this only applies to private memory?

> +enum {
> +	GUEST_MEMFD_FLAG_NO_DIRECT_MAP		= BIT(0),

guest_memfd only supports small folios, this can be simplified.

> +	unsigned long i;
> +	int r;

Set set/clear private semantics in this context are a bit confusing. I 
assume you mean "make inaccessible" "make accessible" and using the 
PG_private flag is just an implementation detail.

> +{
> +	unsigned long start = (unsigned long)folio_address(folio);

In general, no BUG_ON please. WARN_ON_ONCE() is sufficient.

> +}
> +

---

## [9] Patrick Roy — 2024-08-06
*Subject: Re: [PATCH RFC 3/4] mm: guest_memfd: Add option to remove guest
 private memory from direct map*

Hi Elliot,

On Mon, 2024-08-05 at 19:34 +0100, Elliot Berman wrote:
> This patch was reworked from Patrick's patch:
> https://lore.kernel.org/all/20240709132041.3625501-6-roypat@amazon.co.uk/

yaay :D

> While guest_memfd is not available to be mapped by userspace, it is
> still accessible through the kernel's direct map. This means that in

My patch did this, but you separated the PG_uptodate logic from the
direct map removal, right?

> The patch uses release_folio instead of free_folio to reinsert pages
> back into the direct map as by the time free_folio is called,

I thought release_folio was only called for folios with PG_private=1?
You choose PG_private=1 to mean "this folio is in the direct map", so it
gets called for exactly the wrong folios (more on that below, too).

> [1]: https://download.vusec.net/papers/quarantine_raid23.pdf
> 

Mh, you've inverted the semantics of PG_private in the context of gmem
here, compared to my patch. For me, PG_private=1 meant "this folio is
back in the direct map". For you it means "this folio is removed from
the direct map". 

Could you elaborate on why you require these different semantics for
PG_private? Actually, I think in this patch series, you could just drop
the PG_private stuff altogether, as the only place you do
folio_test_private is in guest_memfd_clear_private, but iirc calling
set_direct_map_default_noflush on a page that's already in the direct
map is a NOOP anyway.

On the other hand, as Paolo pointed out in my patches [1], just using a
page flag to track direct map presence for gmem is not enough. We
actually need to keep a refcount in folio->private to keep track of how
many different actors request a folio's direct map presence (in the
specific case in my patch series, it was different pfn_to_gfn_caches for
the kvm-clock structures of different vcpus, which the guest can place
into the same gfn). While this might not be a concern for the the
pKVM/Gunyah case, where the guest dictates memory state, it's required
for the non-CoCo case where KVM/userspace can set arbitrary guest gfns
to shared if it needs/wants to access them for whatever reason. So for
this we'd need to have PG_private=1 mean "direct map entry restored" (as
if PG_private=0, there is no folio->private).

[1]: https://lore.kernel.org/kvm/20240709132041.3625501-1-roypat@amazon.co.uk/T/#m0608c4b6a069b3953d7ee97f48577d32688a3315

> +       return 0;
> +out_remap:

How does a caller of guest_memfd_grab_folio know whether a folio needs
to be removed from the direct map? E.g. how can a caller know ahead of
time whether guest_memfd_grab_folio will return a freshly allocated
folio (which thus needs to be removed from the direct map), vs a folio
that already exists and has been removed from the direct map (probably
fine to remove from direct map again), vs a folio that already exists
and is currently re-inserted into the direct map for whatever reason
(must not remove these from the direct map, as other parts of
KVM/userspace probably don't expect the direct map entries to disappear
from underneath them). I couldn't figure this one out for my series,
which is why I went with hooking into the PG_uptodate logic to always
remove direct map entries on freshly allocated folios.

>         /*
>          * Ignore accessed, referenced, and dirty flags.  The memory is

Best, 
Patrick

---

## [10] Patrick Roy — 2024-08-06
*Subject: Re: [PATCH RFC 4/4] mm: guest_memfd: Add ability for mmap'ing pages*

On Mon, 2024-08-05 at 19:34 +0100, Elliot Berman wrote:
> Confidential/protected guest virtual machines want to share some memory
> back with the host Linux. For example, virtqueues allow host and

Wouldn't the set of inaccessible folios always match exactly the set of
folios that have PG_private=1 set? At least guest_memfd instances that
have GUEST_MEMFD_FLAG_NO_DIRECT_MAP set, having folios without direct
map entries marked "accessible" sound like it may cause a lot of mayhem
(as those folios would essentially be secretmem folios, but this time
without the GUP checks). But even more generally, wouldn't tracking
accessibility via PG_private be enough?

> To safely make inaccessible:
> 

This made be stumble at first. I know you say ops->accessible returning
0 means "this is accessible", but if I only look at this if-statement it
reads as "if the folio is accessible, send a SIGBUS", which is not
what's actually happening.

> +               folio_unlock(folio);
> +               folio_put(folio);

---

## [11] Elliot Berman — 2024-08-06
*Subject: Re: [PATCH RFC 4/4] mm: guest_memfd: Add ability for mmap'ing pages*

On Tue, Aug 06, 2024 at 03:51:22PM +0200, David Hildenbrand wrote:
> > -	if (gmem_flags & GUEST_MEMFD_FLAG_NO_DIRECT_MAP) {
> > +	if (!ops->accessible && (gmem_flags & GUEST_MEMFD_FLAG_NO_DIRECT_MAP)) {

Right, I remember we had discussed it. The problem I faced was if 2
vcpus fault on same page, they would race to look up the folio in
filemap, increment refcount, then try to lock the folio. One of the
vcpus wins the lock, while the other waits. The vcpu that gets the
lock vcpu will see the elevated refcount.

I was in middle of writing an explanation why I think this is best
approach and realized I think it should be possible to do
shared->private conversion and actually have single reference. There
would be some cost to walk through the allocated folios and convert them
to private before any vcpu runs. The approach I had gone with was to
do conversions as late as possible.

Thanks,
Elliot

---

## [12] Elliot Berman — 2024-08-06
*Subject: Re: [PATCH RFC 3/4] mm: guest_memfd: Add option to remove guest
 private memory from direct map*

On Tue, Aug 06, 2024 at 04:39:24PM +0100, Patrick Roy wrote:
> 
> Hi Elliot,

PG_private=1 should be meaning "this folio is not in the direct map".

> > [1]: https://download.vusec.net/papers/quarantine_raid23.pdf
> > 

I wonder if we can use the folio refcount itself, assuming we can rely
on refcount == 1 means we can do shared->private conversion.

In gpc_map_gmem, we convert private->shared. There's no problem here in
the non-CoCo case.

In gpc_unmap, we *try* to convert back from shared->private. If
refcount>2, then the conversion would fail. The last gpc_unmap would be
able to successfully convert back to private.

Do you see any concerns with this approach?

> > +       return 0;
> > +out_remap:

gmem_flags come from the owner. If the caller (in non-CoCo case) wants
to restore the direct map right away, it'd have to be a direct
operation. As an optimization, we could add option that asks for page in
"shared" state. If allocating new page, we can return it right away
without removing from direct map. If grabbing existing folio, it would
try to do the private->shared conversion.

Thanks for the feedback, it was helpful!

- Elliot

> >         /*
> >          * Ignore accessed, referenced, and dirty flags.  The memory is

---

## [13] Elliot Berman — 2024-08-06
*Subject: Re: [PATCH RFC 4/4] mm: guest_memfd: Add ability for mmap'ing pages*

On Tue, Aug 06, 2024 at 04:48:22PM +0100, Patrick Roy wrote:
> On Mon, 2024-08-05 at 19:34 +0100, Elliot Berman wrote:
> > Confidential/protected guest virtual machines want to share some memory

Mostly that is what is happening. The ->accessible() test allows
guest_memfd to initialize PG_private to the right value and to attempt
to convert private back to shared in the case of host trying to access
the page.

> > To safely make inaccessible:
> > 

I'll change it to return a bool :)

> > +               folio_unlock(folio);
> > +               folio_put(folio);

---

## [14] Elliot Berman — 2024-08-06
*Subject: Re: [PATCH RFC 4/4] mm: guest_memfd: Add ability for mmap'ing pages*

Hi Sean/Paolo,

Do you have a preference on when to make the kvm_gmem_prepare_folio
callback? Previously [1], we decided it needed to be at allocation time.
With memory being coverted shared->private, I'm suspecting the
->prepare() callback should only be done right before marking the page
as private?

Thanks,
Elliot

On Mon, Aug 05, 2024 at 11:34:50AM -0700, Elliot Berman wrote:
> Confidential/protected guest virtual machines want to share some memory
> back with the host Linux. For example, virtqueues allow host and

---

## [15] Patrick Roy — 2024-08-07
*Subject: Re: [PATCH RFC 3/4] mm: guest_memfd: Add option to remove guest
 private memory from direct map*

On Tue, 2024-08-06 at 21:13 +0100, Elliot Berman wrote:
> On Tue, Aug 06, 2024 at 04:39:24PM +0100, Patrick Roy wrote:
>>

Right. I just checked my patch and it indeed means the same there. No
idea what I was on about yesterday. I think I only had Paolo's comment
about using folio->private for refcounting sharings in mind, so I
thought "to use folio->private, you need PG_private=1, therefore
PG_private=1 means shared" (I just checked, and while
folio_attach_private causes PG_private=1 to be set, page_set_private
does not). Obviously my comments below and especially here on PG_private
were nonsense. Sorry about that!

>>> [1]: https://download.vusec.net/papers/quarantine_raid23.pdf
>>>

The gfn_to_pfn_cache does not keep an elevated refcount on the cached
page, and instead responds to MMU notifiers to detect whether the cached
translation has been invalidated, iirc. So the folio refcount will
not reflect the number of gpcs holding that folio.

>>> +       return 0;
>>> +out_remap:

---

## [16] Patrick Roy — 2024-08-07
*Subject: Re: [PATCH RFC 3/4] mm: guest_memfd: Add option to remove guest
 private memory from direct map*

On Wed, 2024-08-07 at 07:48 +0100, Patrick Roy wrote:
> 
> 

Ah, oops, I got it mixed up with the new `flags` parameter. 

>> to restore the direct map right away, it'd have to be a direct
>> operation. As an optimization, we could add option that asks for page in

My concern is more with the implicit shared->private conversion that
happens on every call to guest_memfd_grab_folio (and thus
kvm_gmem_get_pfn) when grabbing existing folios. If something else
marked the folio as shared, then we cannot punch it out of the direct
map again until that something is done using the folio (when working on
my RFC, kvm_gmem_get_pfn was indeed called on existing folios that were
temporarily marked shared, as I was seeing panics because of this). And
if the folio is currently private, there's nothing to do. So either way,
guest_memfd_grab_folio shouldn't touch the direct map entry for existing
folios.

>>
>> Thanks for the feedback, it was helpful!

---

## [17] David Hildenbrand — 2024-08-07
*Subject: Re: [PATCH RFC 4/4] mm: guest_memfd: Add ability for mmap'ing pages*

On 06.08.24 19:14, Elliot Berman wrote:
> On Tue, Aug 06, 2024 at 03:51:22PM +0200, David Hildenbrand wrote:
>>> -	if (gmem_flags & GUEST_MEMFD_FLAG_NO_DIRECT_MAP) {

We certainly have to support conversion while the VCPUs are running.

The VCPUs might be able to avoid grabbing a folio reference for the 
conversion and only do the folio_lock(): as long as we have a guarantee 
that we will disallow freeing the folio in gmem, for example, by syncing 
against FALLOC_FL_PUNCH_HOLE.

So if we can rely on the "gmem" reference to the folio that cannot go 
away while we do what we do, we should be fine.

<random though>

Meanwhile, I was thinking if we would want to track the references we
hand out to "safe" users differently.

Safe references would only be references that would survive a 
private<->shared conversion, like KVM MMU mappings maybe?

KVM would then have to be thought to return these gmem references 
differently.

The idea would be to track these "safe" references differently 
(page->private?) and only allow dropping *our* guest_memfd reference if 
all these "safe" references are gone. That is, FALLOC_FL_PUNCH_HOLE 
would also fail if there are any "safe" reference remaining.

<\random though>

---

## [18] Elliot Berman — 2024-08-07
*Subject: Re: [PATCH RFC 3/4] mm: guest_memfd: Add option to remove guest
 private memory from direct map*

On Wed, Aug 07, 2024 at 11:57:35AM +0100, Patrick Roy wrote:
> On Wed, 2024-08-07 at 07:48 +0100, Patrick Roy wrote:
> > On Tue, 2024-08-06 at 21:13 +0100, Elliot Berman wrote:

Ah, fair enough. This is kinda like a GUP pin which would prevent us
from making page private, but without the pin part.

[...]

> >>>>  struct folio *guest_memfd_grab_folio(struct file *file, pgoff_t index, u32 flags)
> >>>>  {

What I did could be documented/commented better.

If ops->accessible() is *not* provided, all guest_memfd allocations will
immediately remove from direct map and treat them immediately like guest
private (goal is to match what KVM does today on tip). 

If ops->accessible() is provided, then guest_memfd allocations start
as "shared" and KVM/Gunyah need to do the shared->private conversion
when they want to do the private conversion on the folio. "Shared" is
the default because that is effectively a no-op.

For the non-CoCo case you're interested in, we'd have the
ops->accessible() provided and we wouldn't pull out the direct map from
gpc.

Thanks,
Elliot

---

## [19] Manwaring, Derek — 2024-08-07
*Subject: Re: [PATCH RFC 3/4] mm: guest_memfd: Add option to remove guest
 private memory from direct map*

On 2024-08-06 07:10-0700 David Hildenbrand wrote:
> > While guest_memfd is not available to be mapped by userspace, it is
> > still accessible through the kernel's direct map. This means that in

Actually, I'm not sure how much protection CoCo solutions offer in this
regard. I'd love to hear more from Intel and AMD on this, but it looks
like they are not targeting full coverage for these types of attacks
(beyond protecting guest mitigation settings from manipulation by the
host).  For example, see this selection from AMD's 2020 whitepaper [1]
on SEV-SNP:

"There are certain classes of attacks that are not in scope for any of
these three features. Architectural side channel attacks on CPU data
structures are not specifically prevented by any hardware means. As with
standard software security practices, code which is sensitive to such
side channel attacks (e.g., cryptographic libraries) should be written
in a way which helps prevent such attacks."

And:

"While SEV-SNP offers guests several options when it comes to protection
from speculative side channel attacks and SMT, it is not able to protect
against all possible side channel attacks. For example, traditional side
channel attacks on software such as PRIME+PROBE are not protected by
SEV-SNP."

Intel's docs also indicate guests need to protect themselves in some
cases saying, "TD software should be aware that potentially untrusted
software running outside a TD may be able to influence conditional
branch predictions of software running in a TD" [2] and "a TDX guest VM
is no different from a legacy guest VM in terms of protecting this
userspace <-> OS kernel boundary" [3]. But these focus on hardening
kernel & software within the guest.

What's not clear to me is what happens during transient execution when
the host kernel attempts to access a page in physical memory that
belongs to a guest. I assume if it only happens transiently, it will not
result in a machine check like it would if the instructions were
actually retired. As far as I can tell encryption happens between the
CPU & main memory, so cache contents will be plaintext. This seems to
leave open the possibility of the host kernel retrieving the plaintext
cache contents with a transient execution attack. I assume vendors have
controls in place to stop this, but Foreshadow/L1TF is a good example of
one place this fell apart for SGX [4].

All that said, we're also dependent on hardware not being subject to
L1TF-style issues for the currently proposed non-CoCo method to be
effective.  We're simply clearing the Present bit while the physmap PTE
still points to the guest physical page. This was found to be
exploitable across OS & VMM boundaries on Intel server parts before
Cascade Lake [5] (thanks to Claudio for highlighting this). So that's a
long way of saying TDX may offer similar protection, but not because of
encryption.

Derek

[1] https://www.amd.com/content/dam/amd/en/documents/epyc-business-docs/white-papers/SEV-SNP-strengthening-vm-isolation-with-integrity-protection-and-more.pdf#page=19
[2] https://www.intel.com/content/www/us/en/developer/articles/technical/software-security-guidance/best-practices/trusted-domain-security-guidance-for-developers.html
[3] https://intel.github.io/ccc-linux-guest-hardening-docs/security-spec.html#transient-execution-attacks-and-their-mitigation
[4] https://foreshadowattack.eu/foreshadow.pdf
[5] https://foreshadowattack.eu/foreshadow-NG.pdf

---

## [20] Patrick Roy — 2024-08-08
*Subject: Re: [PATCH RFC 3/4] mm: guest_memfd: Add option to remove guest
 private memory from direct map*

On Wed, 2024-08-07 at 20:06 +0100, Elliot Berman wrote:
>>>>>>  struct folio *guest_memfd_grab_folio(struct file *file, pgoff_t index, u32 flags)
>>>>>>  {

No worries, thanks for taking the time to walk me through understanding
it!

> If ops->accessible() is *not* provided, all guest_memfd allocations will
> immediately remove from direct map and treat them immediately like guest

Ah, so if ops->accessible() is not provided, then there will never be
any shared memory inside gmem (like today, where gmem doesn't support
shared memory altogether), and thus there's no problems with just
unconditionally doing set_direct_map_invalid_noflush in
guest_memfd_grab_folio, because all existing folios already have their
direct map entry removed. Got it!

> If ops->accessible() is provided, then guest_memfd allocations start
> as "shared" and KVM/Gunyah need to do the shared->private conversion

So in pKVM/Gunyah's case, guest memory starts as shared, and at some
point the guest will issue a hypercall (or similar) to flip it to
private, at which point it'll get removed from the direct map?

That isn't really what we want for our case. We consider the folios as
private straight away, as we do not let the guest control their state at
all. Everything is always "accessible" to both KVM and userspace in the
sense that they can just flip gfns to shared as they please without the
guest having any say in it.

I think we should untangle the behavior of guest_memfd_grab_folio from
the presence of ops->accessible. E.g.  instead of direct map removal
being dependent on ops->accessible we should have some
GRAB_FOLIO_RETURN_SHARED flag for gmem_flags, which is set for y'all,
and not set for us (I don't think we should have a "call
set_direct_map_invalid_noflush unconditionally in
guest_memfd_grab_folio" mode at all, because if sharing gmem is
supported, then that is broken, and if sharing gmem is not supported
then only removing direct map entries for freshly allocated folios gets
us the same result of "all folios never in the direct map" while
avoiding some no-op direct map operations).

Because we would still use ->accessible, albeit for us that would be
more for bookkeeping along the lines of "which gfns does userspace
currently require to be in the direct map?". I haven't completely
thought it through, but what I could see working for us would be a pair
of ioctls for marking ranges accessible/inaccessible, with
"accessibility" stored in some xarray (somewhat like Fuad's patches, I
guess? [1]).

In a world where we have a "sharing refcount", the "make accessible"
ioctl reinserts into the direct map (if needed), lifts the "sharings
refcount" for each folio in the given gfn range, and marks the range as
accessible.  And the "make inaccessible" ioctl would first check that
userspace has unmapped all those gfns again, and if yes, mark them as
inaccessible, drop the "sharings refcount" by 1 for each, and removes
from the direct map again if it held the last reference (if userspace
still has some gfns mapped, the ioctl would just fail).

I guess for pKVM/Gunyah, there wouldn't be userspace ioctls, but instead
the above would happen in handlers for share/unshare hypercalls. But the
overall flow would be similar. The only difference is the default state
of guest memory (shared for you, private for us). You want a
guest_memfd_grab_folio that essentially returns folios with "sharing
refcount == 1" (and thus present in the direct map), while we want the
opposite.

So I think something like the following should work for both of us
(modulo some error handling):

static struct folio *__kvm_gmem_get_folio(struct file *file, pgoff_t index, bool prepare, bool *fresh)
{
    // as today's kvm_gmem_get_folio, except
    ...
    if (!folio_test_uptodate(folio)) {
        ...
        if (fresh)
            *fresh = true
    }
    ...
}

struct folio *kvm_gmem_get_folio(struct file *file, pgoff_t index, bool prepare)
{
    bool fresh;
    unsigned long gmem_flags = /* ... */
    struct folio *folio = __kvm_gmem_get_folio(file, index, prepare, &fresh);
    if (gmem_flag & GRAB_FOLIO_RETURN_SHARED != 0) {
        // if "sharing refcount == 0", inserts back into direct map and lifts refcount, otherwise just lifts refcount
        guest_memfd_folio_clear_private(folio);
    } else {
        if (fresh)
            guest_memfd_folio_private(folio);
    }
    return folio;
}

Now, thinking ahead, there's probably optimizations here where we defer
the direct map manipulations to gmem_fault, at which point having a
guest_memfd_grab_folio that doesn't remove direct map entries for fresh
folios would be useful in our non-CoCo usecase too. But that should also
be easily achievable by maybe having a flag to kvm_gmem_get_folio that
forces the behavior of GRAB_FOLIO_RETURN_SHARED, indendently of whether
GRAB_FOLIO_RETURN_SHARED is set in gmem_flags.

How does that sound to you?

[1]: https://lore.kernel.org/kvm/20240801090117.3841080-1-tabba@google.com/

> Thanks,
> Elliot

Best,
Patrick

---

## [21] Ackerley Tng — 2024-08-08
*Subject: Re: [PATCH RFC 1/4] mm: Introduce guest_memfd*

Elliot Berman <quic_eberman@quicinc.com> writes:

> In preparation for adding more features to KVM's guest_memfd, refactor
> and introduce a library which abstracts some of the core-mm decisions

I interpreted the current state of the code after patch [1] to mean that
the definition of the uptodate flag means "prepared for guest use", so
the two enum values here are probably actually the same thing.

For SEV, this means calling rmp_make_private(), so I guess when the page
allowed to be faulted in to userspace, rmp_make_shared() would have to
be called on the page.

Shall we continue to have the uptodate flag mean "prepared for guest
use" (whether prepared for shared or private use)?

Then we can have another enum to request a zeroed page (which will have
no accompanying page flag)? Or could we remove the zeroing feature,
since it was meant to be handled by trusted hypervisor or hardware in
the first place? It was listed as a TODO before being removed in [2].

I like the idea of having flags to control what is done to the page,
perhaps removing the page from the direct map could be yet another enum.

> +
> +struct folio *guest_memfd_grab_folio(struct file *file, pgoff_t index, u32 flags);

> <snip>

[1] https://lore.kernel.org/all/20240726185157.72821-15-pbonzini@redhat.com/
[2] https://lore.kernel.org/all/20240726185157.72821-8-pbonzini@redhat.com/

---

## [22] Ackerley Tng — 2024-08-08
*Subject: Re: [PATCH RFC 4/4] mm: guest_memfd: Add ability for mmap'ing pages*

Elliot Berman <quic_eberman@quicinc.com> writes:

> Confidential/protected guest virtual machines want to share some memory
> back with the host Linux. For example, virtqueues allow host and

I am also working on determining faultability not based on the
private-ness of the page but based on permission given by the
guest. I'd like to learn from what you've discovered here.

Could you please elaborate on this? What races is the folio_lock
intended to prevent, what operations are we ensuring atomicity of?

Is this why you did a guest_memfd_grab_folio() before checking
->accessible(), and then doing folio_unlock() if the page is
inaccessible?

>
> Signed-off-by: Elliot Berman <quic_eberman@quicinc.com>

Could grabbing the folio with GUEST_MEMFD_GRAB_UPTODATE cause unintended
zeroing of the page if the page turns out to be inaccessible?

> +	if (!folio)
> +		return VM_FAULT_SIGBUS;

---

## [23] Elliot Berman — 2024-08-08
*Subject: Re: [PATCH RFC 4/4] mm: guest_memfd: Add ability for mmap'ing pages*

On Wed, Aug 07, 2024 at 06:12:00PM +0200, David Hildenbrand wrote:
> On 06.08.24 19:14, Elliot Berman wrote:
> > On Tue, Aug 06, 2024 at 03:51:22PM +0200, David Hildenbrand wrote:

I didn't find a path in filemap where we can grab folio without
increasing its refcount. I liked the idea of keeping track of a "safe"
refcount, but I believe there is a small window to race comparing the
main folio refcount and the "safe" refcount. A vcpu could have
incremented the main folio refcount and on the way to increment the safe
refcount. Before that happens, another thread does the comparison and
sees a mismatch.

Thanks,
Elliot

---

## [24] Elliot Berman — 2024-08-08
*Subject: Re: [PATCH RFC 4/4] mm: guest_memfd: Add ability for mmap'ing pages*

On Thu, Aug 08, 2024 at 06:51:14PM +0000, Ackerley Tng wrote:
> Elliot Berman <quic_eberman@quicinc.com> writes:
> 

The contention I've been paying most attention to are racing userspace
and vcpu faults where guest needs the page to be private. There could
also be multiple vcpus demanding same page.

We had some chatter about doing the private->shared conversion via
separate ioctl (mem attributes). I think the same race can happen with
userspace whether it's vcpu fault or ioctl making the folio "finally
guest-private".

Also, in non-CoCo KVM private guest_memfd, KVM or userspace could also
convert private->shared and need to make sure that all the tracking for
the current state is consistent.

> Is this why you did a guest_memfd_grab_folio() before checking
> ->accessible(), and then doing folio_unlock() if the page is

Right, I want to guard against userspace being able to fault in a page
concurrently with that same page doing a shared->private conversion. The
folio_lock seems like the best fine-grained lock to grab.

If the shared->private converter wins the folio_lock first, then the
userspace fault waits and will see ->accessible() == false as desired. 

If userspace fault wins the folio_lock first, it relinquishes the lock
only after installing the folio in page tables[*]. When the
shared->private converter finally gets the lock,
guest_memfd_make_inaccessible() will be able to unmap the folio from any
userspace page tables (and direct map, if applicable).

[*]: I'm not mm expert, but that was what I could find when I went
digging.

Thanks,
Elliot

> >
> > Signed-off-by: Elliot Berman <quic_eberman@quicinc.com>

I assume that if page is inaccessible, it would already have been marked
up to date and we wouldn't try to zero the page.

I'm thinking that if hypervisor zeroes the page when making the page
private, it would not give the GUEST_MEMFD_GRAB_UPTODATE flag when
grabbing the folio. I believe the hypervisor should know when grabbing
the folio if it's about to donate to the guest.

Thanks,
Elliot

---

## [25] David Hildenbrand — 2024-08-08
*Subject: Re: [PATCH RFC 4/4] mm: guest_memfd: Add ability for mmap'ing pages*

On 08.08.24 23:41, Elliot Berman wrote:
> On Wed, Aug 07, 2024 at 06:12:00PM +0200, David Hildenbrand wrote:
>> On 06.08.24 19:14, Elliot Berman wrote:

There are various possible models. To detect unexpected references, we 
could either use

folio_ref_count(folio) == gmem_folio_safe_ref_count(folio) + 1

[we increment both ref counter]

or

folio_ref_count(folio) == 1

[we only increment the safe refcount and let other magic handle it as 
described]

A vcpu could have
> incremented the main folio refcount and on the way to increment the safe
> refcount. Before that happens, another thread does the comparison and

Likely there won't be a way around coming up with code that is able to 
deal with such temporary, "speculative" folio references.

In the simplest case, these references will be obtained from our gmem 
code only, and we'll have to detect that it happened and retry (a 
seqcount would be a naive solution).

In the complex case, these references are temporarily obtained from 
other core-mm code -- using folio_try_get(). We can minimize some of 
them (speculative references from GUP or the pagecache), and try 
optimizing others (PFN walkers like page migration).

But likely we'll need some retry magic, at least initially.

---

## [26] Elliot Berman — 2024-08-08
*Subject: Re: [PATCH RFC 3/4] mm: guest_memfd: Add option to remove guest
 private memory from direct map*

On Thu, Aug 08, 2024 at 02:05:55PM +0100, Patrick Roy wrote:
> On Wed, 2024-08-07 at 20:06 +0100, Elliot Berman wrote:
> >>>>>>  struct folio *guest_memfd_grab_folio(struct file *file, pgoff_t index, u32 flags)

I am warming up to the sharing refcount idea. How does the sharing
refcount look for kvm gpc?

> I guess for pKVM/Gunyah, there wouldn't be userspace ioctls, but instead
> the above would happen in handlers for share/unshare hypercalls. But the

Yeah, I think this is a good idea.

I'm also thinking to make a few tweaks to the ops structure:

struct guest_memfd_operations {
        int (*invalidate_begin)(struct inode *inode, pgoff_t offset, unsigned long nr);
        void (*invalidate_end)(struct inode *inode, pgoff_t offset, unsigned long nr);
        int (*prepare_accessible)(struct inode *inode, struct folio *folio);
        int (*prepare_private)(struct inode *inode, struct folio *folio);
        int (*release)(struct inode *inode);
};

When grabbing a folio, we'd always call either prepare_accessible() or
prepare_private() based on GRAB_FOLIO_RETURN_SHARED. In the
prepare_private() case, guest_memfd can also ensure the folio is
unmapped and not pinned. If userspace tries to grab the folio in
pKVM/Gunyah case, prepare_accessible() will fail and grab_folio returns
error. There's a lot of details I'm glossing over, but I hope it gives
some brief idea of the direction I was thinking.

In some cases, prepare_accessible() and the invalidate_*() functions
might effectively be the same thing, except that invalidate_*() could
operate on a range larger-than-a-folio. That would be useful becase we
might offer optimization to reclaim a batch of pages versus e.g.
flushing caches every page.

Thanks,
Elliot

---

## [27] Elliot Berman — 2024-08-08
*Subject: Re: [PATCH RFC 4/4] mm: guest_memfd: Add ability for mmap'ing pages*

On Thu, Aug 08, 2024 at 11:55:15PM +0200, David Hildenbrand wrote:
> On 08.08.24 23:41, Elliot Berman wrote:
> > On Wed, Aug 07, 2024 at 06:12:00PM +0200, David Hildenbrand wrote:

I thought retry magic would not fly. I'll try this out.

Thanks,
Elliot

---

## [28] David Hildenbrand — 2024-08-09
*Subject: Re: [PATCH RFC 4/4] mm: guest_memfd: Add ability for mmap'ing pages*

On 09.08.24 00:26, Elliot Berman wrote:
> On Thu, Aug 08, 2024 at 11:55:15PM +0200, David Hildenbrand wrote:
>> On 08.08.24 23:41, Elliot Berman wrote:

Any details why? At least the "other gmem code is currently taking a 
speculative reference" should be handable, these speculative references 
all happen from gmem code and it should be under our control.

We can protect against some core-mm speculative references (GUP, 
page-cache): after we allocated pages for gmem, and a RCU grace period 
passed, these can no longer happen from old context that previously had 
these pages allocated before gmem allocated them.

Other folio_try_get() users like memory offlining or page migration are 
more problematic. In general, the assumption is that they will give up 
quickly, for example when realizing that a folio is not LRU or non 
"non-lru-movable" -- which is the case for gmem-allocated pages.

Yes, no retry magic would be very much preferred, but as soon as we want 
to map these folios to user space and have GUP work on them (IOW, we 
have to make the folio refcount usable), we cannot easily block all 
speculative references from core-mm, for example, by freezing the 
refcount at 0. Long term, we might find ways to just block these 
speculative references more efficiently / differently.

---

## [29] Patrick Roy — 2024-08-09
*Subject: Re: [PATCH RFC 3/4] mm: guest_memfd: Add option to remove guest
 private memory from direct map*

On Thu, 2024-08-08 at 23:16 +0100, Elliot Berman wrote
> On Thu, Aug 08, 2024 at 02:05:55PM +0100, Patrick Roy wrote:
>> On Wed, 2024-08-07 at 20:06 +0100, Elliot Berman wrote:

I've come up with the below rough draft (written as a new commit on
top of my RFC series [1], with some bits from your patch copied in).
With this, I was able to actually boot a Firecracker VM with
multiple vCPUs (which previously didn't work because of different vCPUs
putting their kvm-clock structures into the same guest page). 

Best, 
Patrick

[1]: https://lore.kernel.org/kvm/20240709132041.3625501-1-roypat@amazon.co.uk/T/#ma44793da6bc000a2c22b1ffe37292b9615881838

---

From 2005c5a06b8a8f8568e9140b275d2c219488a71a Mon Sep 17 00:00:00 2001
From: Patrick Roy <roypat@amazon.co.uk>
Date: Fri, 9 Aug 2024 15:13:08 +0100
Subject: [RFC PATCH 009/008] kvm: gmem: Introduce "sharing refcount"

The assumption that there would never be two gfn_to_pfn_caches holding
the same gfn was wrong. The guest can put the kvm-clock structures for
different vCPUs into the same gfn. On KVM's side, one gfn_to_pfn_cache
is initialized by vCPU, meaning in multi-vCPU setups, multiple
gfn_to_pfn_caches to the same gfn exist.

For gmem, this means that multiple gfn_to_pfn_caches will want direct
map entries for the same page to be present - the direct map entry needs
to be removed when the first gpc is initialized, and can only be removed
again after the last gpc to this page is invalidated. To handle this,
introduce the concept of a "sharing refcount" to gmem: If something
inside of KVM wants to access gmem it should now do

struct folio *gmem_folio = /* ... */;
int r = kvm_gmem_folio_share(gmem_folio);
if (r)
    goto err;
/* do stuff */
kvm_gmem_folio_unshare(gmem_folio);

The first call to kvm_gmem_folio_share will increment this new "sharing
refcount" by 1 (and insert the folio back into the direct map if it
acquires the first refcount), while kvm_gmem_folio_unshare will
decrement the refcount by 1 (and remove the folio from the direct map
again if it held the last refcount).

One quirk is that we use "sharing_refcount == 1" to mean "folio is not
in the direct map" (aka not shared), as letting the refcount temporarily
drop to 0 would cause refcount_t functions to WARN.

Signed-off-by: Patrick Roy <roypat@amazon.co.uk>
---
 virt/kvm/guest_memfd.c | 139 ++++++++++++++++++++++++++++++++++++++---
 virt/kvm/kvm_main.c    |  32 ++++------
 virt/kvm/kvm_mm.h      |   2 +
 virt/kvm/pfncache.c    |  54 ++--------------
 4 files changed, 148 insertions(+), 79 deletions(-)

diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index 29abbc883c73a..05fd6149c11c2 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -55,6 +55,96 @@ static bool kvm_gmem_not_present(struct inode *inode)
 	return ((unsigned long)inode->i_private & KVM_GMEM_NO_DIRECT_MAP) != 0;
 }

+static int kvm_gmem_folio_private(struct folio* folio)
+{
+	unsigned long nr_pages = folio_nr_pages(folio);
+	unsigned long i;
+	int r;
+
+	/*
+	 * We must only remove direct map entries after the last "sharing
+	 * reference" has gone away.
+	 */
+	if(WARN_ON_ONCE(refcount_read(folio_get_private(folio)) != 1))
+		return -EPERM;
+
+	for (i = 0; i < nr_pages; i++) {
+		struct page *page = folio_page(folio, i);
+
+		r = set_direct_map_invalid_noflush(page);
+		if (r < 0)
+			goto out_remap;
+	}
+
+	// We use the private flag to track whether the folio has been removed
+	// from the direct map. This is because inside of ->free_folio,
+	// we do not have access to the address_space anymore, meaning we
+	// cannot check folio_inode(folio)->i_private to determine whether
+	// KVM_GMEM_NO_DIRECT_MAP was set.
+	folio_set_private(folio);
+	return 0;
+out_remap:
+	for (; i > 0; i--) {
+		struct page *page = folio_page(folio, i - 1);
+
+		BUG_ON(set_direct_map_default_noflush(page));
+	}
+	return r;
+}
+
+static int kvm_gmem_folio_clear_private(struct folio *folio)
+{
+	unsigned long start = (unsigned long)folio_address(folio);
+	unsigned long nr = folio_nr_pages(folio);
+	unsigned long i;
+	int r;
+
+	/*
+	 * We must restore direct map entries on acquiring the first "sharing
+	 * reference" (although restoring it before that is fine too - we
+	 * restore direct map entries with sharing_refcount == 1 in
+	 * kvm_gmem_invalidate_folio).
+	 */
+	WARN_ON_ONCE(refcount_read(folio_get_private(folio)) > 2);
+
+	for (i = 0; i < nr; i++) {
+		struct page *page = folio_page(folio, i);
+
+		r = set_direct_map_default_noflush(page);
+		if (r)
+			goto out_remap;
+	}
+	flush_tlb_kernel_range(start, start + folio_size(folio));
+
+	folio_clear_private(folio);
+	return 0;
+out_remap:
+	for (; i > 0; i--) {
+		for (; i > 0; i--) {
+			struct page *page = folio_page(folio, i - 1);
+
+			BUG_ON(set_direct_map_invalid_noflush(page));
+		}
+	}
+	return r;
+}
+
+static int kvm_gmem_init_sharing_count(struct folio *folio)
+{
+	refcount_t *sharing_count = kmalloc(sizeof(*sharing_count), GFP_KERNEL);
+	if (!sharing_count)
+		return -ENOMEM;
+
+	/*
+	 * we need to use sharing_count == 1 to mean "no sharing", because dropping
+	 * a refcount_t to 0 and later inc-ing it again would result in a WARN
+	 */
+	refcount_set(sharing_count, 1);
+	folio_change_private(folio, (void *)sharing_count);
+
+	return 0;
+}
+
 static struct folio *kvm_gmem_get_folio(struct inode *inode, pgoff_t index, bool prepare)
 {
 	struct folio *folio;
@@ -96,16 +186,12 @@ static struct folio *kvm_gmem_get_folio(struct inode *inode, pgoff_t index, bool
 	}

 	if (zap_direct_map) {
-		r = set_direct_map_invalid_noflush(&folio->page);
+		r = kvm_gmem_init_sharing_count(folio);
+		if (r < 0)
+			goto out_err;
+		r = kvm_gmem_folio_private(folio);
 		if (r < 0)
 			goto out_err;
-
-		// We use the private flag to track whether the folio has been removed
-		// from the direct map. This is because inside of ->free_folio,
-		// we do not have access to the address_space anymore, meaning we
-		// cannot check folio_inode(folio)->i_private to determine whether
-		// KVM_GMEM_NO_DIRECT_MAP was set.
-		folio_set_private(folio);
 	}

 	/*
@@ -413,11 +499,21 @@ static void kvm_gmem_free_folio(struct folio *folio)
 static void kvm_gmem_invalidate_folio(struct folio *folio, size_t start, size_t end)
 {
 	if (start == 0 && end == PAGE_SIZE) {
+		refcount_t *sharing_count = folio_get_private(folio);
+		/*
+		 * sharing_count != 1 means that something else forgot
+		 * to call kvm_gmem_folio_unshare after it was done with the
+		 * folio (meaning the folio has been in the direct map
+		 * this entire time, which means we haven't been getting the
+		 * spculation protection we wanted).
+		 */
+		WARN_ON_ONCE(refcount_read(sharing_count) != 1);
+
 		// We only get here if PG_private is set, which only happens if kvm_gmem_not_present
 		// returned true in kvm_gmem_get_folio. Thus no need to do that check again.
-		BUG_ON(set_direct_map_default_noflush(&folio->page));
+		kvm_gmem_folio_clear_private(folio);
+		kfree(sharing_count);

-		folio_clear_private(folio);
 	}
 }

@@ -610,6 +706,29 @@ void kvm_gmem_unbind(struct kvm_memory_slot *slot)
 	fput(file);
 }

+int kvm_gmem_folio_unshare(struct folio *folio)
+{
+	if (kvm_gmem_not_present(folio_inode(folio))) {
+		refcount_t *sharing_count = folio_get_private(folio);
+
+		refcount_dec(sharing_count);
+		if (refcount_read(sharing_count) == 1)
+			return kvm_gmem_folio_private(folio);
+	}
+	return 0;
+}
+
+int kvm_gmem_folio_share(struct folio *folio)
+{
+	if (kvm_gmem_not_present(folio_inode(folio))) {
+		refcount_inc(folio_get_private(folio));
+
+		if (folio_test_private(folio))
+			return kvm_gmem_folio_clear_private(folio);
+	}
+	return 0;
+}
+
 static int __kvm_gmem_get_pfn(struct file *file, struct kvm_memory_slot *slot,
 		       gfn_t gfn, kvm_pfn_t *pfn, int *max_order, bool prepare)
 {
diff --git a/virt/kvm/kvm_main.c b/virt/kvm/kvm_main.c
index 762decd9f2da0..d0680564ad52f 100644
--- a/virt/kvm/kvm_main.c
+++ b/virt/kvm/kvm_main.c
@@ -3301,17 +3301,13 @@ static int __kvm_read_guest_private_page(struct kvm *kvm,
 	folio = pfn_folio(pfn);
 	folio_lock(folio);
 	kaddr = folio_address(folio);
-	if (folio_test_private(folio)) {
-		r = set_direct_map_default_noflush(&folio->page);
-		if (r)
-			goto out_unlock;
-	}
+	r = kvm_gmem_folio_share(folio);
+	if (r)
+		goto out_unlock;
 	memcpy(data, kaddr + offset, len);
-	if (folio_test_private(folio)) {
-		r = set_direct_map_invalid_noflush(&folio->page);
-		if (r)
-			goto out_unlock;
-	}
+	r = kvm_gmem_folio_unshare(folio);
+	if (r)
+		goto out_unlock;
 out_unlock:
 	folio_unlock(folio);
 	folio_put(folio);
@@ -3458,17 +3454,13 @@ static int __kvm_write_guest_private_page(struct kvm *kvm,
 	folio = pfn_folio(pfn);
 	folio_lock(folio);
 	kaddr = folio_address(folio);
-	if (folio_test_private(folio)) {
-		r = set_direct_map_default_noflush(&folio->page);
-		if (r)
-			goto out_unlock;
-	}
+	r = kvm_gmem_folio_share(folio);
+	if (r)
+		goto out_unlock;
 	memcpy(kaddr + offset, data, len);
-	if (folio_test_private(folio)) {
-		r = set_direct_map_invalid_noflush(&folio->page);
-		if (r)
-			goto out_unlock;
-	}
+	r = kvm_gmem_folio_unshare(folio);
+	if (r)
+		goto out_unlock;

 out_unlock:
 	folio_unlock(folio);
diff --git a/virt/kvm/kvm_mm.h b/virt/kvm/kvm_mm.h
index 715f19669d01f..f3fb31a39a66f 100644
--- a/virt/kvm/kvm_mm.h
+++ b/virt/kvm/kvm_mm.h
@@ -41,6 +41,8 @@ int kvm_gmem_create(struct kvm *kvm, struct kvm_create_guest_memfd *args);
 int kvm_gmem_bind(struct kvm *kvm, struct kvm_memory_slot *slot,
 		  unsigned int fd, loff_t offset);
 void kvm_gmem_unbind(struct kvm_memory_slot *slot);
+int kvm_gmem_folio_share(struct folio *folio);
+int kvm_gmem_folio_unshare(struct folio *folio);
 #else
 static inline void kvm_gmem_init(struct module *module)
 {
diff --git a/virt/kvm/pfncache.c b/virt/kvm/pfncache.c
index 55f39fd60f8af..9f955e07efb90 100644
--- a/virt/kvm/pfncache.c
+++ b/virt/kvm/pfncache.c
@@ -111,45 +111,8 @@ static int gpc_map_gmem(kvm_pfn_t pfn)
 	if (((unsigned long)inode->i_private & KVM_GMEM_NO_DIRECT_MAP) == 0)
 		goto out;

-	/* We need to avoid race conditions where set_memory_np is called for
-	 * pages that other parts of KVM still try to access.  We use the
-	 * PG_private bit for this. If it is set, then the page is removed from
-	 * the direct map. If it is cleared, the page is present in the direct
-	 * map. All changes to this bit, and all modifications of the direct
-	 * map entries for the page happen under the page lock. The _only_
-	 * place where a page will be in the direct map while the page lock is
-	 * _not_ held is if it is inside a gpc. All other parts of KVM that
-	 * temporarily re-insert gmem pages into the direct map (currently only
-	 * guest_{read,write}_page) take the page lock before the direct map
-	 * entry is restored, and hold it until it is zapped again. This means
-	 * - If we reach gpc_map while, say, guest_read_page is operating on
-	 *   this page, we block on acquiring the page lock until
-	 *   guest_read_page is done.
-	 * - If we reach gpc_map while another gpc is already caching this
-	 *   page, the page is present in the direct map and the PG_private
-	 *   flag is cleared. Int his case, we return -EINVAL below to avoid
-	 *   two gpcs caching the same page (since we do not ref-count
-	 *   insertions back into the direct map, when the first cache gets
-	 *   invalidated it would "break" the second cache that assumes the
-	 *   page is present in the direct map until the second cache itself
-	 *   gets invalidated).
-	 * - Lastly, if guest_read_page is called for a page inside of a gpc,
-	 *   it will see that the PG_private flag is cleared, and thus assume
-	 *   it is present in the direct map (and leave the direct map entry
-	 *   untouched). Since it will be holding the page lock, it cannot race
-	 *   with gpc_unmap.
-	 */
 	folio_lock(folio);
-	if (folio_test_private(folio)) {
-		r = set_direct_map_default_noflush(&folio->page);
-		if (r)
-			goto out_unlock;
-
-		folio_clear_private(folio);
-	} else {
-		r = -EINVAL;
-	}
-out_unlock:
+	r = kvm_gmem_folio_share(folio);
 	folio_unlock(folio);
 out:
 	return r;
@@ -181,17 +144,10 @@ static void gpc_unmap(kvm_pfn_t pfn, void *khva, bool private)
 	if (pfn_valid(pfn)) {
 		if (private) {
 			struct folio *folio = pfn_folio(pfn);
-			struct inode *inode = folio_inode(folio);
-
-			if ((unsigned long)inode->i_private &
-			    KVM_GMEM_NO_DIRECT_MAP) {
-				folio_lock(folio);
-				BUG_ON(folio_test_private(folio));
-				BUG_ON(set_direct_map_invalid_noflush(
-					&folio->page));
-				folio_set_private(folio);
-				folio_unlock(folio);
-			}
+
+			folio_lock(folio);
+			kvm_gmem_folio_unshare(folio);
+			folio_unlock(folio);
 		}
 		kunmap(pfn_to_page(pfn));
 		return;
--
2.46.0

---

## [30] Fuad Tabba — 2024-08-15
*Subject: Re: [PATCH RFC 4/4] mm: guest_memfd: Add ability for mmap'ing pages*

Hi David,

On Tue, 6 Aug 2024 at 14:51, David Hildenbrand <david@redhat.com> wrote:
>
> >

I was wondering, why do we need to check the refcount? Isn't it enough
to check for page_mapped() || page_maybe_dma_pinned(), while holding
the folio lock?

Thanks!
/fuad

> --
> Cheers,

---

## [31] Manwaring, Derek — 2024-08-15
*Subject: Re: [PATCH RFC 3/4] mm: guest_memfd: Add option to remove guest
 private memory from direct map*

On 2024-08-07 17:16-0700 Derek Manwaring wrote:
> All that said, we're also dependent on hardware not being subject to
> L1TF-style issues for the currently proposed non-CoCo method to be

I was wrong here. The set_direct_map_invalid_noflush implementation
moves through __change_page_attr and pfn_pte, eventually arriving at
flip_protnone_guard where the PFN is inverted & thus no longer valid for
pages marked not present. So we do benefit from that prior work's extra
protection against L1TF.

Thank you for finding this, Patrick.

Derek

---

## [32] David Hildenbrand — 2024-08-16
*Subject: Re: [PATCH RFC 4/4] mm: guest_memfd: Add ability for mmap'ing pages*

On 15.08.24 09:24, Fuad Tabba wrote:
> Hi David,

Hi!

> 
> On Tue, 6 Aug 2024 at 14:51, David Hildenbrand <david@redhat.com> wrote:

(folio_mapped() + folio_maybe_dma_pinned())

Not everything goes trough FOLL_PIN. vmsplice() is an example, or just 
some very simple read/write through /proc/pid/mem. Further, some 
O_DIRECT implementations still don't use FOLL_PIN.

So if you see an additional folio reference, as soon as you mapped that 
thing to user space, you have to assume that it could be someone 
reading/writing that memory in possibly sane context. (vmsplice() should 
be using FOLL_PIN|FOLL_LONGTERM, but that's a longer discussion)

(noting that also folio_maybe_dma_pinned() can have false positives in 
some cases due to speculative references or *many* references).

---

## [33] Fuad Tabba — 2024-08-16
*Subject: Re: [PATCH RFC 4/4] mm: guest_memfd: Add ability for mmap'ing pages*

On Fri, 16 Aug 2024 at 10:48, David Hildenbrand <david@redhat.com> wrote:
>
> On 15.08.24 09:24, Fuad Tabba wrote:

Thanks for the clarification!
/fuad

> --
> Cheers,

---

## [34] Ackerley Tng — 2024-08-16
*Subject: Re: [PATCH RFC 4/4] mm: guest_memfd: Add ability for mmap'ing pages*

David Hildenbrand <david@redhat.com> writes:

> On 15.08.24 09:24, Fuad Tabba wrote:
>> Hi David,

Thank you Fuad for asking!

>
> (folio_mapped() + folio_maybe_dma_pinned())

Thanks David for the clarification, this example is very helpful!

IIUC folio_lock() isn't a prerequisite for taking a refcount on the
folio.

Even if we are able to figure out a "safe" refcount, and check that the
current refcount == "safe" refcount before removing from direct map,
what's stopping some other part of the kernel from taking a refcount
just after the check happens and causing trouble with the folio's
removal from direct map?

> (noting that also folio_maybe_dma_pinned() can have false positives in 
> some cases due to speculative references or *many* references).

Are false positives (speculative references) okay since it's better to
be safe than remove from direct map prematurely?

>
> --

---

## [35] David Hildenbrand — 2024-08-16
*Subject: Re: [PATCH RFC 4/4] mm: guest_memfd: Add ability for mmap'ing pages*

On 16.08.24 19:45, Ackerley Tng wrote:
> 
> David Hildenbrand <david@redhat.com> writes:

Right, to do folio_lock() you only have to guarantee that the folio 
cannot get freed concurrently. So you piggyback on another reference 
(you hold indirectly).

> 
> Even if we are able to figure out a "safe" refcount, and check that the

Once the page was unmapped from user space, and there were no additional 
references (e.g., GUP, whatever), any new references can only be 
(should, unless BUG :) ) temporary speculative references that should 
not try accessing page content, and that should back off if the folio is 
not deemed interesting or cannot be locked. (e.g., page 
migration/compaction/offlining).

Of course, there are some corner cases (kgdb, hibernation, /proc/kcore), 
but most of these can be dealt with in one way or the other (make these 
back off and not read/write page content, similar to how we handled it 
for secretmem).

These (kgdb, /proc/kcore) might not even take a folio reference, they 
just "access stuff" and we only have to teach them to "not access that".

> 
>> (noting that also folio_maybe_dma_pinned() can have false positives in

folio_maybe_dma_pinned() is primarily used in fork context. Copying more 
(if the folio maybe pinned and, therefore, must not get COW-shared with 
other processes and must instead create a private page copy) is the 
"better safe than sorry". So false positives (that happen rarely) are 
tolerable.

Regading the directmap, it would -- just like with additional references 
-- detect that the page cannot currently be removed from the direct map. 
It's similarly "better safe than sorry", but here means that we likely 
must retry if we cannot easily fallback to something else like for the 
fork+COW case.

---

## [36] Ackerley Tng — 2024-08-16
*Subject: Re: [PATCH RFC 4/4] mm: guest_memfd: Add ability for mmap'ing pages*

David Hildenbrand <david@redhat.com> writes:

> On 16.08.24 19:45, Ackerley Tng wrote:
>> 

I thought about it again - I think the vmsplice() cases are taken care
of once we check that the folios are not mapped into userspace, since
vmsplice() reads from a mapping.

splice() reads from the fd directly, but that's taken care since
guest_memfd doesn't have a .splice_read() handler.

Reading /proc/pid/mem also requires the pages to first be mapped, IIUC,
otherwise the pages won't show up, so checking that there are no more
mappings to userspace takes care of this.

>
> Of course, there are some corner cases (kgdb, hibernation, /proc/kcore), 

Does that really leave us with these corner cases? And so perhaps we
could get away with just taking the folio_lock() to keep away the
speculative references? So something like

  1. Check that the folio is not mapped and not pinned.
  2. folio_lock() all the folios about to be removed from direct map
  -- With the lock, all other accesses should be speculative --
  3. Check that the refcount == "safe" refcount
      3a. Unlock and return to userspace with -EAGAIN
  4. Remove from direct map
  5. folio_unlock() all those folios

Perhaps a very naive question: can the "safe" refcount be statically
determined by walking through the code and counting where refcount is
expected to be incremented?

Or perhaps the "safe" refcount may differ based on kernel config. Could
we perhaps have a single static variable safe_refcount, and whenever a
new guest_memfd folio is allocated, do

  safe_refcount = min(new_folio_refcount, safe_refcount)

>
> These (kgdb, /proc/kcore) might not even take a folio reference, they

---

## [37] David Hildenbrand — 2024-08-17
*Subject: Re: [PATCH RFC 4/4] mm: guest_memfd: Add ability for mmap'ing pages*

On 16.08.24 23:52, Ackerley Tng wrote:
> David Hildenbrand <david@redhat.com> writes:
> 

You have a misconception.

You can map pages to user space, GUP them, and then unmap them from user 
space. A GUP reference can outlive your user space mappings, easily.

So once there is a raised refcount, it could as well just be from 
vmsplice, or a pending reference from /proc/pid/mem, O_DIRECT, ...

> 
>>

To do that, you have to lookup the folio first. That currently requires 
a refcount increment, even if only temporarily. Maybe we could avoid 
that, if we can guarantee that we are the only one modifying the 
pageache here, and we sync against that ourselves.

>    2. folio_lock() all the folios about to be removed from direct map
>    -- With the lock, all other accesses should be speculative --


Depends on how we design it. But if you hand out "safe" references to 
KVM etc, you'd have to track that -- and how often -- somehow. At which 
point we are at "increment/decrement" safe reference to track that for you.

---

## [38] Elliot Berman — 2024-08-16
*Subject: Re: [PATCH RFC 4/4] mm: guest_memfd: Add ability for mmap'ing pages*

On Sat, Aug 17, 2024 at 12:03:50AM +0200, David Hildenbrand wrote:
> On 16.08.24 23:52, Ackerley Tng wrote:
> > David Hildenbrand <david@redhat.com> writes:

Just a status update: I've gotten the "safe" reference counter
implementation working for Gunyah now. It feels a bit flimsy because
we're juggling 3 reference counters*, but it seems like the right thing
to do after all the discussions here. It's passing all the Gunyah unit
tests I have which have so far been pretty good at finding issues.

I need to clean up the patches now and I'm aiming to have it out for RFC
next week.

* folio refcount, "accessible" refcount, and "safe" refcount

Thanks,
Elliot

---

## [39] Mike Rapoport — 2024-08-19
*Subject: Re: [PATCH RFC 3/4] mm: guest_memfd: Add option to remove guest
 private memory from direct map*

On Mon, Aug 05, 2024 at 11:34:49AM -0700, Elliot Berman wrote:
> This patch was reworked from Patrick's patch:
> https://lore.kernel.org/all/20240709132041.3625501-6-roypat@amazon.co.uk/

please name this enum, otherwise kernel-doc wont' be happy

> +	GUEST_MEMFD_FLAG_NO_DIRECT_MAP		= BIT(0),
> +};

I think that TLB flush should come after removing pages from the direct map
rather than after adding them back.

> +
> +	folio_clear_private(folio);

---

## [40] Elliot Berman — 2024-08-20
*Subject: Re: [PATCH RFC 3/4] mm: guest_memfd: Add option to remove guest
 private memory from direct map*

On Mon, Aug 19, 2024 at 01:09:52PM +0300, Mike Rapoport wrote:
> On Mon, Aug 05, 2024 at 11:34:49AM -0700, Elliot Berman wrote:
> > This patch was reworked from Patrick's patch:

Gunyah flushes the tlb when it removes the stage 2 mapping, so we
skipped it on removal as a performance optimization. I remember seeing
that pKVM does the same (tlb flush for the stage 2 unmap & the
equivalent for x86). Patrick had also done the same in their patches.

Thanks,
Elliot

---

## [41] Mike Rapoport — 2024-08-21
*Subject: Re: [PATCH RFC 3/4] mm: guest_memfd: Add option to remove guest
 private memory from direct map*

On Tue, Aug 20, 2024 at 09:56:10AM -0700, Elliot Berman wrote:
> On Mon, Aug 19, 2024 at 01:09:52PM +0300, Mike Rapoport wrote:
> > On Mon, Aug 05, 2024 at 11:34:49AM -0700, Elliot Berman wrote:

Strictly from the API perspective, unmapping the pages from the direct map
would imply removing potentially stale TLB entries.
If all currently anticipated users do it elsewhere, at the very least there
should be a huge bold comment.

And what's the point of tlb flush after setting the direct map to default?
There should not be stale tlb entries for the unmapped pages.
 
> Thanks,
> Elliot

---
