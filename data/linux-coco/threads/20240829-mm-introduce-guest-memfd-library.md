---
title: 'mm: Introduce guest_memfd library'
date: 2024-08-29
last_reply: 2024-10-22
message_count: 10
participants: ['Elliot Berman', 'Vishal Annapurve', 'Paolo Bonzini', 'Mike Day']
---

## [1] Elliot Berman — 2024-08-29

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
arm64 pKVM. The Gunyah usage of the series will be posted separately
shortly after sending this series. I'll work with Fuad on using the
guest_memfd library for arm64 pKVM based on the feedback received.

There are a few TODOs still pending. 
- The KVM patch isn't tested. I don't have access a SEV-SNP setup to be
  able to test.
- I've not yet investigated deeply whether having the guest_memfd
  library helps live migration. I'd appreciate any input on that part.
- We should consider consolidating the adjust_direct_map() in
  arch/x86/virt/svm/sev.c so guest_memfd can take care of it.
- There's a race possibility where the folio ref count is incremented
  and about to also increment the safe counter, but waiting for the
  folio lock to be released. The owner of folio_lock will see mismatched
  counter values and not be able to convert to (in)accessible, even
  though it should be okay to do so.
 
I'd appreciate any feedback, especially on the direction I'm taking for
tracking the (in)accessible state.

Signed-off-by: Elliot Berman <quic_eberman@quicinc.com>

Changes in v2:
- Significantly reworked to introduce "accessible" and "safe" reference
  counters
- Link to v1:
  https://lore.kernel.org/r/20240805-guest-memfd-lib-v1-0-e5a29a4ff5d7@quicinc.com

---
Elliot Berman (5):
      mm: Introduce guest_memfd
      mm: guest_memfd: Allow folios to be accessible to host
      kvm: Convert to use guest_memfd library
      mm: guest_memfd: Add ability for userspace to mmap pages
      mm: guest_memfd: Add option to remove inaccessible memory from direct map

 arch/x86/kvm/svm/sev.c      |   3 +-
 include/linux/guest_memfd.h |  49 ++++
 mm/Kconfig                  |   3 +
 mm/Makefile                 |   1 +
 mm/guest_memfd.c            | 667 ++++++++++++++++++++++++++++++++++++++++++++
 virt/kvm/Kconfig            |   1 +
 virt/kvm/guest_memfd.c      | 371 +++++-------------------
 virt/kvm/kvm_main.c         |   2 -
 virt/kvm/kvm_mm.h           |   6 -
 9 files changed, 797 insertions(+), 306 deletions(-)
---
base-commit: 5be63fc19fcaa4c236b307420483578a56986a37
change-id: 20240722-guest-memfd-lib-455f24115d46

Best regards,

---

## [2] Elliot Berman — 2024-08-29
*Subject: [PATCH RFC v2 1/5] mm: Introduce guest_memfd*

In preparation for adding more features to KVM's guest_memfd, refactor
and introduce a library which abstracts some of the core-mm decisions
about managing folios associated with the file. The goal of the refactor
serves two purposes:

Provide an easier way to reason about memory in guest_memfd. With KVM
supporting multiple confidentiality models (TDX, SEV-SNP, pKVM, ARM
CCA), and coming support for allowing kernel and userspace to access
this memory, it seems necessary to create a stronger abstraction between
core-mm concerns and hypervisor concerns.

Provide a common implementation for the various hypervisors (SEV-SNP,
Gunyah, pKVM) to use.

Signed-off-by: Elliot Berman <quic_eberman@quicinc.com>
---
 include/linux/guest_memfd.h |  38 +++++
 mm/Kconfig                  |   3 +
 mm/Makefile                 |   1 +
 mm/guest_memfd.c            | 332 ++++++++++++++++++++++++++++++++++++++++++++
 4 files changed, 374 insertions(+)

diff --git a/include/linux/guest_memfd.h b/include/linux/guest_memfd.h
new file mode 100644
index 0000000000000..8785b7d599051
--- /dev/null
+++ b/include/linux/guest_memfd.h
@@ -0,0 +1,38 @@
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
+ * @prepare_inaccessible: called when a folio transitions to inaccessible state
+ *                        Optional.
+ * @release: Called when releasing the guest_memfd file. Required.
+ */
+struct guest_memfd_operations {
+	int (*invalidate_begin)(struct inode *inode, pgoff_t offset, unsigned long nr);
+	void (*invalidate_end)(struct inode *inode, pgoff_t offset, unsigned long nr);
+	int (*prepare_inaccessible)(struct inode *inode, struct folio *folio);
+	int (*release)(struct inode *inode);
+};
+
+enum guest_memfd_create_flags {
+	GUEST_MEMFD_FLAG_CLEAR_INACCESSIBLE = (1UL << 0),
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
index b72e7d040f789..333f465256957 100644
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
index d2915f8c9dc01..e15a95ebeac5d 100644
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
index 0000000000000..c6cd01e6064a7
--- /dev/null
+++ b/mm/guest_memfd.c
@@ -0,0 +1,332 @@
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
+/**
+ * guest_memfd_grab_folio() -- grabs a folio from the guest memfd
+ * @file: guest memfd file to grab from
+ *        Caller must ensure file is a guest_memfd file
+ * @index: the page index in the file
+ * @flags: bitwise OR of guest_memfd_grab_flags
+ *
+ * If a folio is returned, the folio was successfully initialized or converted
+ * to (in)accessible based on the GUEST_MEMFD_* flags. The folio is guaranteed
+ * to be (in)accessible until the folio lock is relinquished. After folio
+ * lock relinquished, ->prepare_inaccessible and ->prepare_accessible ops are
+ * responsible for preventing transitioning between the states as
+ * required.
+ *
+ * This function may return error even if the folio exists, in the event
+ * the folio couldn't be made (in)accessible as requested in the flags.
+ *
+ * This function may sleep.
+ *
+ * The caller must call either guest_memfd_put_folio() or
+ * guest_memfd_unsafe_folio().
+ *
+ * Returns:
+ * A pointer to the grabbed folio on success, otherwise an error code.
+ */
+struct folio *guest_memfd_grab_folio(struct file *file, pgoff_t index, u32 flags)
+{
+	unsigned long gmem_flags = (unsigned long)file->private_data;
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
+	if (folio_test_uptodate(folio))
+		return folio;
+
+	folio_wait_stable(folio);
+
+	/*
+	 * Use the up-to-date flag to track whether or not the memory has been
+	 * zeroed before being handed off to the guest.  There is no backing
+	 * storage for the memory, so the folio will remain up-to-date until
+	 * it's removed.
+	 */
+	if (gmem_flags & GUEST_MEMFD_FLAG_CLEAR_INACCESSIBLE) {
+		unsigned long nr_pages = folio_nr_pages(folio);
+		unsigned long i;
+
+		for (i = 0; i < nr_pages; i++)
+			clear_highpage(folio_page(folio, i));
+
+	}
+
+	if (ops->prepare_inaccessible) {
+		r = ops->prepare_inaccessible(inode, folio);
+		if (r < 0)
+			goto out_err;
+	}
+
+	folio_mark_uptodate(folio);
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
+		folio = guest_memfd_grab_folio(file, index, 0);
+		if (!folio) {
+			r = -ENOMEM;
+			break;
+		}
+
+		index = folio_next_index(folio);
+
+		folio_unlock(folio);
+		guest_memfd_put_folio(folio, 0);
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
+static const struct file_operations gmem_fops = {
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
+static inline unsigned long guest_memfd_valid_flags(void)
+{
+	return GUEST_MEMFD_FLAG_CLEAR_INACCESSIBLE;
+}
+
+/**
+ * guest_memfd_alloc() - Create a guest_memfd file
+ * @name: the name of the new file
+ * @ops: operations table for the guest_memfd file
+ * @size: the size of the file
+ * @flags: flags controlling behavior of the file
+ *
+ * Creates a new guest_memfd file.
+ */
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
+	if (flags & ~guest_memfd_valid_flags())
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
+/**
+ * is_guest_memfd() - Returns true if the struct file is a guest_memfd
+ * @file: the file to check
+ * @ops: the expected operations table
+ */
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

## [3] Elliot Berman — 2024-08-29
*Subject: [PATCH RFC v2 2/5] mm: guest_memfd: Allow folios to be accessible
 to host*

Memory given to a confidential VM sometimes needs to be accessible by
Linux. Before the VM starts, Linux needs to load some payload into
the guest memory. While the VM is running, the guest may make some of
the memory accessible to the host, e.g. to share virtqueue buffers. We
choose less-used terminology here to avoid confusion with other terms
(i.e. private). Memory is considered "accessible" when Linux (the host)
can read/write to that memory. It is considered "inaccessible" when
reads/writes aren't allowed by the hypervisor.

Careful tracking of when the memory is supposed to be "inaccessible" and
"accessible" is needed because hypervisors will fault Linux if we
incorrectly access memory which shouldn't be accessed. On arm64 systems,
this is a translation fault. On x86 systems, this could be a machine
check.

After discussion in [1], we are using 3 counters to track the state of a
folio: the general folio_ref_count, a "safe" ref count, and an
"accessible" counter.

Transition between accessible and inaccessible is allowed only when:
0. The folio is locked
1. The "accessible" counter is at 0.
2. The "safe" ref count equals the folio_ref_count.
3. The hypervisor allows it.

The accessible counter can be used by Linux to guarantee the page stays
accessible, without elevating the general refcount. When the accessible
counter decrements to 0, we attempt to make the page inaccessible. When
the accessible counters increments to 1, we attempt to make the page
accessible.

We expect the folio_ref_count to be nearly zero. The "nearly" amount is
determined by the "safe" ref count value. The safe ref count isn't a
signal whether the folio is accessible or not, it is only used to
compare against the folio_ref_count.

The final condition to transition between (in)accessible is whether the
->prepare_accessible or ->prepare_inaccessible guest_memfd_operation
passes. In arm64 pKVM/Gunyah terms, the fallible "prepare_accessible"
check is needed to ensure that the folio is unlocked by the guest and
thus accessible to the host.

When grabbing a folio, the client can either request for it to be
accessible or inaccessible. If the folio already exists, we attempt to
transition it to the state, if not already in that state. This will
allow KVM or userspace to access guest_memfd *before* it is made
inaccessible because KVM and userspace will use
GUEST_MEMFD_GRAB_ACCESSIBLE.

[1]: https://lore.kernel.org/all/a7c5bfc0-1648-4ae1-ba08-e706596e014b@redhat.com/

Signed-off-by: Elliot Berman <quic_eberman@quicinc.com>
---
 include/linux/guest_memfd.h |  10 ++
 mm/guest_memfd.c            | 238 +++++++++++++++++++++++++++++++++++++++++---
 2 files changed, 236 insertions(+), 12 deletions(-)

diff --git a/include/linux/guest_memfd.h b/include/linux/guest_memfd.h
index 8785b7d599051..66e5d3ab42613 100644
--- a/include/linux/guest_memfd.h
+++ b/include/linux/guest_memfd.h
@@ -22,17 +22,27 @@ struct guest_memfd_operations {
 	int (*invalidate_begin)(struct inode *inode, pgoff_t offset, unsigned long nr);
 	void (*invalidate_end)(struct inode *inode, pgoff_t offset, unsigned long nr);
 	int (*prepare_inaccessible)(struct inode *inode, struct folio *folio);
+	int (*prepare_accessible)(struct inode *inode, struct folio *folio);
 	int (*release)(struct inode *inode);
 };
 
+enum guest_memfd_grab_flags {
+	GUEST_MEMFD_GRAB_INACCESSIBLE	= (0UL << 0),
+	GUEST_MEMFD_GRAB_ACCESSIBLE	= (1UL << 0),
+};
+
 enum guest_memfd_create_flags {
 	GUEST_MEMFD_FLAG_CLEAR_INACCESSIBLE = (1UL << 0),
 };
 
 struct folio *guest_memfd_grab_folio(struct file *file, pgoff_t index, u32 flags);
+void guest_memfd_put_folio(struct folio *folio, unsigned int accessible_refs);
+void guest_memfd_unsafe_folio(struct folio *folio);
 struct file *guest_memfd_alloc(const char *name,
 			       const struct guest_memfd_operations *ops,
 			       loff_t size, unsigned long flags);
 bool is_guest_memfd(struct file *file, const struct guest_memfd_operations *ops);
+int guest_memfd_make_accessible(struct folio *folio);
+int guest_memfd_make_inaccessible(struct folio *folio);
 
 #endif
diff --git a/mm/guest_memfd.c b/mm/guest_memfd.c
index c6cd01e6064a7..62cb576248a9d 100644
--- a/mm/guest_memfd.c
+++ b/mm/guest_memfd.c
@@ -4,9 +4,33 @@
  */
 
 #include <linux/anon_inodes.h>
+#include <linux/atomic.h>
 #include <linux/falloc.h>
 #include <linux/guest_memfd.h>
 #include <linux/pagemap.h>
+#include <linux/wait.h>
+
+#include "internal.h"
+
+static DECLARE_WAIT_QUEUE_HEAD(safe_wait);
+
+/**
+ * struct guest_memfd_private - private per-folio data
+ * @accessible: number of kernel users expecting folio to be accessible.
+ *              When zero, the folio converts to being inaccessible.
+ * @safe: number of "safe" references to the folio. Each reference is
+ *        aware that the folio can be made (in)accessible at any time.
+ */
+struct guest_memfd_private {
+	atomic_t accessible;
+	atomic_t safe;
+};
+
+static inline int base_safe_refs(struct folio *folio)
+{
+	/* 1 for filemap */
+	return 1 + folio_nr_pages(folio);
+}
 
 /**
  * guest_memfd_grab_folio() -- grabs a folio from the guest memfd
@@ -35,21 +59,56 @@
  */
 struct folio *guest_memfd_grab_folio(struct file *file, pgoff_t index, u32 flags)
 {
-	unsigned long gmem_flags = (unsigned long)file->private_data;
+	const bool accessible = flags & GUEST_MEMFD_GRAB_ACCESSIBLE;
 	struct inode *inode = file_inode(file);
 	struct guest_memfd_operations *ops = inode->i_private;
+	struct guest_memfd_private *private;
+	unsigned long gmem_flags;
 	struct folio *folio;
 	int r;
 
 	/* TODO: Support huge pages. */
-	folio = filemap_grab_folio(inode->i_mapping, index);
+	folio = __filemap_get_folio(inode->i_mapping, index,
+			FGP_LOCK | FGP_ACCESSED | FGP_CREAT | FGP_STABLE,
+			mapping_gfp_mask(inode->i_mapping));
 	if (IS_ERR(folio))
 		return folio;
 
-	if (folio_test_uptodate(folio))
+	if (folio_test_uptodate(folio)) {
+		private = folio_get_private(folio);
+		atomic_inc(&private->safe);
+		if (accessible)
+			r = guest_memfd_make_accessible(folio);
+		else
+			r = guest_memfd_make_inaccessible(folio);
+
+		if (r) {
+			atomic_dec(&private->safe);
+			goto out_err;
+		}
+
+		wake_up_all(&safe_wait);
 		return folio;
+	}
 
-	folio_wait_stable(folio);
+	private = kmalloc(sizeof(*private), GFP_KERNEL);
+	if (!private) {
+		r = -ENOMEM;
+		goto out_err;
+	}
+
+	folio_attach_private(folio, private);
+	/*
+	 * 1 for us
+	 * 1 for unmapping from userspace
+	 */
+	atomic_set(&private->accessible, accessible ? 2 : 0);
+	/*
+	 * +1 for us
+	 */
+	atomic_set(&private->safe, 1 + base_safe_refs(folio));
+
+	gmem_flags = (unsigned long)inode->i_mapping->i_private_data;
 
 	/*
 	 * Use the up-to-date flag to track whether or not the memory has been
@@ -57,19 +116,26 @@ struct folio *guest_memfd_grab_folio(struct file *file, pgoff_t index, u32 flags
 	 * storage for the memory, so the folio will remain up-to-date until
 	 * it's removed.
 	 */
-	if (gmem_flags & GUEST_MEMFD_FLAG_CLEAR_INACCESSIBLE) {
+	if (accessible || (gmem_flags & GUEST_MEMFD_FLAG_CLEAR_INACCESSIBLE)) {
 		unsigned long nr_pages = folio_nr_pages(folio);
 		unsigned long i;
 
 		for (i = 0; i < nr_pages; i++)
 			clear_highpage(folio_page(folio, i));
-
 	}
 
-	if (ops->prepare_inaccessible) {
-		r = ops->prepare_inaccessible(inode, folio);
-		if (r < 0)
-			goto out_err;
+	if (accessible) {
+		if (ops->prepare_accessible) {
+			r = ops->prepare_accessible(inode, folio);
+			if (r < 0)
+				goto out_free;
+		}
+	} else {
+		if (ops->prepare_inaccessible) {
+			r = ops->prepare_inaccessible(inode, folio);
+			if (r < 0)
+				goto out_free;
+		}
 	}
 
 	folio_mark_uptodate(folio);
@@ -78,6 +144,8 @@ struct folio *guest_memfd_grab_folio(struct file *file, pgoff_t index, u32 flags
 	 * unevictable and there is no storage to write back to.
 	 */
 	return folio;
+out_free:
+	kfree(private);
 out_err:
 	folio_unlock(folio);
 	folio_put(folio);
@@ -85,6 +153,132 @@ struct folio *guest_memfd_grab_folio(struct file *file, pgoff_t index, u32 flags
 }
 EXPORT_SYMBOL_GPL(guest_memfd_grab_folio);
 
+/**
+ * guest_memfd_put_folio() - Drop safe and accessible references to a folio
+ * @folio: the folio to drop references to
+ * @accessible_refs: number of accessible refs to drop, 0 if holding a
+ *                   reference to an inaccessible folio.
+ */
+void guest_memfd_put_folio(struct folio *folio, unsigned int accessible_refs)
+{
+	struct guest_memfd_private *private = folio_get_private(folio);
+
+	WARN_ON_ONCE(atomic_sub_return(accessible_refs, &private->accessible) < 0);
+	atomic_dec(&private->safe);
+	folio_put(folio);
+	wake_up_all(&safe_wait);
+}
+EXPORT_SYMBOL_GPL(guest_memfd_put_folio);
+
+/**
+ * guest_memfd_unsafe_folio() - Demotes the current folio reference to "unsafe"
+ * @folio: the folio to demote
+ *
+ * Decrements the number of safe references to this folio. The folio will not
+ * transition to inaccessible until the folio_ref_count is also decremented.
+ *
+ * This function does not release the folio reference count.
+ */
+void guest_memfd_unsafe_folio(struct folio *folio)
+{
+	struct guest_memfd_private *private = folio_get_private(folio);
+
+	atomic_dec(&private->safe);
+	wake_up_all(&safe_wait);
+}
+EXPORT_SYMBOL_GPL(guest_memfd_unsafe_folio);
+
+/**
+ * guest_memfd_make_accessible() - Attempt to make the folio accessible to host
+ * @folio: the folio to make accessible
+ *
+ * Makes the given folio accessible to the host. If the folio is currently
+ * inaccessible, attempts to convert it to accessible. Otherwise, returns with
+ * EBUSY.
+ *
+ * This function may sleep.
+ */
+int guest_memfd_make_accessible(struct folio *folio)
+{
+	struct guest_memfd_private *private = folio_get_private(folio);
+	struct inode *inode = folio_inode(folio);
+	struct guest_memfd_operations *ops = inode->i_private;
+	int r;
+
+	/*
+	 * If we already know the folio is accessible, then no need to do
+	 * anything else.
+	 */
+	if (atomic_inc_not_zero(&private->accessible))
+		return 0;
+
+	r = wait_event_timeout(safe_wait,
+			       folio_ref_count(folio) == atomic_read(&private->safe),
+			       msecs_to_jiffies(10));
+	if (!r)
+		return -EBUSY;
+
+	if (ops->prepare_accessible) {
+		r = ops->prepare_accessible(inode, folio);
+		if (r)
+			return r;
+	}
+
+	atomic_inc(&private->accessible);
+	return 0;
+}
+EXPORT_SYMBOL_GPL(guest_memfd_make_accessible);
+
+/**
+ * guest_memfd_make_inaccessible() - Attempt to make the folio inaccessible
+ * @folio: the folio to make inaccessible
+ *
+ * Makes the given folio inaccessible to the host. IF the folio is currently
+ * accessible, attempt so convert it to inaccessible. Otherwise, returns with
+ * EBUSY.
+ *
+ * Conversion to inaccessible is allowed when ->accessible decrements to zero,
+ * the folio safe counter == folio reference counter, the folio is unmapped
+ * from host, and ->prepare_inaccessible returns it's ready to do so.
+ *
+ * This function may sleep.
+ */
+int guest_memfd_make_inaccessible(struct folio *folio)
+{
+	struct guest_memfd_private *private = folio_get_private(folio);
+	struct inode *inode = folio_inode(folio);
+	struct guest_memfd_operations *ops = inode->i_private;
+	int r;
+
+	r = atomic_dec_if_positive(&private->accessible);
+	if (r < 0)
+		return 0;
+	else if (r > 0)
+		return -EBUSY;
+
+	unmap_mapping_folio(folio);
+
+	r = wait_event_timeout(safe_wait,
+			       folio_ref_count(folio) == atomic_read(&private->safe),
+			       msecs_to_jiffies(10));
+	if (!r) {
+		r = -EBUSY;
+		goto err;
+	}
+
+	if (ops->prepare_inaccessible) {
+		r = ops->prepare_inaccessible(inode, folio);
+		if (r)
+			goto err;
+	}
+
+	return 0;
+err:
+	atomic_inc(&private->accessible);
+	return r;
+}
+EXPORT_SYMBOL_GPL(guest_memfd_make_inaccessible);
+
 static long gmem_punch_hole(struct file *file, loff_t offset, loff_t len)
 {
 	struct inode *inode = file_inode(file);
@@ -229,10 +423,12 @@ static int gmem_error_folio(struct address_space *mapping, struct folio *folio)
 
 static bool gmem_release_folio(struct folio *folio, gfp_t gfp)
 {
+	struct guest_memfd_private *private = folio_get_private(folio);
 	struct inode *inode = folio_inode(folio);
 	struct guest_memfd_operations *ops = inode->i_private;
 	off_t offset = folio->index;
 	size_t nr = folio_nr_pages(folio);
+	unsigned long val, expected;
 	int ret;
 
 	ret = ops->invalidate_begin(inode, offset, nr);
@@ -241,14 +437,32 @@ static bool gmem_release_folio(struct folio *folio, gfp_t gfp)
 	if (ops->invalidate_end)
 		ops->invalidate_end(inode, offset, nr);
 
+	expected = base_safe_refs(folio);
+	val = atomic_read(&private->safe);
+	WARN_ONCE(val != expected, "folio[%x] safe ref: %d != expected %d\n",
+		  folio_index(folio), val, expected);
+
+	folio_detach_private(folio);
+	kfree(private);
+
 	return true;
 }
 
+static void gmem_invalidate_folio(struct folio *folio, size_t offset, size_t len)
+{
+	WARN_ON_ONCE(offset != 0);
+	WARN_ON_ONCE(len != folio_size(folio));
+
+	if (offset == 0 && len == folio_size(folio))
+		filemap_release_folio(folio, 0);
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
@@ -291,8 +505,7 @@ struct file *guest_memfd_alloc(const char *name,
 	 * instead of reusing a single inode.  Each guest_memfd instance needs
 	 * its own inode to track the size, flags, etc.
 	 */
-	file = anon_inode_create_getfile(name, &gmem_fops, (void *)flags,
-					 O_RDWR, NULL);
+	file = anon_inode_create_getfile(name, &gmem_fops, NULL, O_RDWR, NULL);
 	if (IS_ERR(file))
 		return file;
 
@@ -303,6 +516,7 @@ struct file *guest_memfd_alloc(const char *name,
 
 	inode->i_private = (void *)ops; /* discards const qualifier */
 	inode->i_mapping->a_ops = &gmem_aops;
+	inode->i_mapping->i_private_data = (void *)flags;
 	inode->i_mode |= S_IFREG;
 	inode->i_size = size;
 	mapping_set_gfp_mask(inode->i_mapping, GFP_HIGHUSER);

---

## [4] Elliot Berman — 2024-08-29
*Subject: [PATCH RFC v2 3/5] kvm: Convert to use guest_memfd library*

Use the recently created mm/guest_memfd implementation. No functional
change intended.

Note: I've only compile-tested this. Appreciate some help from SEV folks
to be able to test this.

Signed-off-by: Elliot Berman <quic_eberman@quicinc.com>
---
 arch/x86/kvm/svm/sev.c |   3 +-
 virt/kvm/Kconfig       |   1 +
 virt/kvm/guest_memfd.c | 371 ++++++++++---------------------------------------
 virt/kvm/kvm_main.c    |   2 -
 virt/kvm/kvm_mm.h      |   6 -
 5 files changed, 77 insertions(+), 306 deletions(-)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 714c517dd4b72..f3a6857270943 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -2297,8 +2297,7 @@ static int sev_gmem_post_populate(struct kvm *kvm, gfn_t gfn_start, kvm_pfn_t pf
 			kunmap_local(vaddr);
 		}
 
-		ret = rmp_make_private(pfn + i, gfn << PAGE_SHIFT, PG_LEVEL_4K,
-				       sev_get_asid(kvm), true);
+		ret = guest_memfd_make_inaccessible(pfn_folio(pfn));
 		if (ret)
 			goto err;
 
diff --git a/virt/kvm/Kconfig b/virt/kvm/Kconfig
index fd6a3010afa83..1e7a3dc488919 100644
--- a/virt/kvm/Kconfig
+++ b/virt/kvm/Kconfig
@@ -106,6 +106,7 @@ config KVM_GENERIC_MEMORY_ATTRIBUTES
 
 config KVM_PRIVATE_MEM
        select XARRAY_MULTI
+       select GUEST_MEMFD
        bool
 
 config KVM_GENERIC_PRIVATE_MEM
diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index 8f079a61a56db..cbff71b6019db 100644
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
 
@@ -13,6 +11,13 @@ struct kvm_gmem {
 	struct list_head entry;
 };
 
+static inline struct kvm_gmem *inode_to_kvm_gmem(struct inode *inode)
+{
+	struct list_head *gmem_list = &inode->i_mapping->i_private_list;
+
+	return list_first_entry_or_null(gmem_list, struct kvm_gmem, entry);
+}
+
 /**
  * folio_file_pfn - like folio_file_page, but return a pfn.
  * @folio: The folio which contains this index.
@@ -25,12 +30,11 @@ static inline kvm_pfn_t folio_file_pfn(struct folio *folio, pgoff_t index)
 	return folio_pfn(folio) + (index & (folio_nr_pages(folio) - 1));
 }
 
-static int __kvm_gmem_prepare_folio(struct kvm *kvm, struct kvm_memory_slot *slot,
-				    pgoff_t index, struct folio *folio)
+static int kvm_gmem_prepare_inaccessible(struct inode *inode, struct folio *folio)
 {
 #ifdef CONFIG_HAVE_KVM_ARCH_GMEM_PREPARE
-	kvm_pfn_t pfn = folio_file_pfn(folio, index);
-	gfn_t gfn = slot->base_gfn + index - slot->gmem.pgoff;
+	kvm_pfn_t pfn = folio_file_pfn(folio, 0);
+	gfn_t gfn = slot->base_gfn + folio_index(folio) - slot->gmem.pgoff;
 	int rc = kvm_arch_gmem_prepare(kvm, gfn, pfn, folio_order(folio));
 	if (rc) {
 		pr_warn_ratelimited("gmem: Failed to prepare folio for index %lx GFN %llx PFN %llx error %d.\n",
@@ -42,67 +46,7 @@ static int __kvm_gmem_prepare_folio(struct kvm *kvm, struct kvm_memory_slot *slo
 	return 0;
 }
 
-static inline void kvm_gmem_mark_prepared(struct folio *folio)
-{
-	folio_mark_uptodate(folio);
-}
-
-/*
- * Process @folio, which contains @gfn, so that the guest can use it.
- * The folio must be locked and the gfn must be contained in @slot.
- * On successful return the guest sees a zero page so as to avoid
- * leaking host data and the up-to-date flag is set.
- */
-static int kvm_gmem_prepare_folio(struct kvm *kvm, struct kvm_memory_slot *slot,
-				  gfn_t gfn, struct folio *folio)
-{
-	unsigned long nr_pages, i;
-	pgoff_t index;
-	int r;
-
-	nr_pages = folio_nr_pages(folio);
-	for (i = 0; i < nr_pages; i++)
-		clear_highpage(folio_page(folio, i));
-
-	/*
-	 * Preparing huge folios should always be safe, since it should
-	 * be possible to split them later if needed.
-	 *
-	 * Right now the folio order is always going to be zero, but the
-	 * code is ready for huge folios.  The only assumption is that
-	 * the base pgoff of memslots is naturally aligned with the
-	 * requested page order, ensuring that huge folios can also use
-	 * huge page table entries for GPA->HPA mapping.
-	 *
-	 * The order will be passed when creating the guest_memfd, and
-	 * checked when creating memslots.
-	 */
-	WARN_ON(!IS_ALIGNED(slot->gmem.pgoff, 1 << folio_order(folio)));
-	index = gfn - slot->base_gfn + slot->gmem.pgoff;
-	index = ALIGN_DOWN(index, 1 << folio_order(folio));
-	r = __kvm_gmem_prepare_folio(kvm, slot, index, folio);
-	if (!r)
-		kvm_gmem_mark_prepared(folio);
-
-	return r;
-}
-
-/*
- * Returns a locked folio on success.  The caller is responsible for
- * setting the up-to-date flag before the memory is mapped into the guest.
- * There is no backing storage for the memory, so the folio will remain
- * up-to-date until it's removed.
- *
- * Ignore accessed, referenced, and dirty flags.  The memory is
- * unevictable and there is no storage to write back to.
- */
-static struct folio *kvm_gmem_get_folio(struct inode *inode, pgoff_t index)
-{
-	/* TODO: Support huge pages. */
-	return filemap_grab_folio(inode->i_mapping, index);
-}
-
-static void kvm_gmem_invalidate_begin(struct kvm_gmem *gmem, pgoff_t start,
+static void __kvm_gmem_invalidate_begin(struct kvm_gmem *gmem, pgoff_t start,
 				      pgoff_t end)
 {
 	bool flush = false, found_memslot = false;
@@ -137,118 +81,38 @@ static void kvm_gmem_invalidate_begin(struct kvm_gmem *gmem, pgoff_t start,
 		KVM_MMU_UNLOCK(kvm);
 }
 
-static void kvm_gmem_invalidate_end(struct kvm_gmem *gmem, pgoff_t start,
-				    pgoff_t end)
+static int kvm_gmem_invalidate_begin(struct inode *inode, pgoff_t offset, unsigned long nr)
 {
-	struct kvm *kvm = gmem->kvm;
-
-	if (xa_find(&gmem->bindings, &start, end - 1, XA_PRESENT)) {
-		KVM_MMU_LOCK(kvm);
-		kvm_mmu_invalidate_end(kvm);
-		KVM_MMU_UNLOCK(kvm);
-	}
-}
-
-static long kvm_gmem_punch_hole(struct inode *inode, loff_t offset, loff_t len)
-{
-	struct list_head *gmem_list = &inode->i_mapping->i_private_list;
-	pgoff_t start = offset >> PAGE_SHIFT;
-	pgoff_t end = (offset + len) >> PAGE_SHIFT;
 	struct kvm_gmem *gmem;
 
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
+	list_for_each_entry(gmem, &inode->i_mapping->i_private_list, entry)
+		__kvm_gmem_invalidate_begin(gmem, offset, offset + nr);
 
 	return 0;
 }
 
-static long kvm_gmem_allocate(struct inode *inode, loff_t offset, loff_t len)
+static void __kvm_gmem_invalidate_end(struct kvm_gmem *gmem, pgoff_t start,
+				    pgoff_t end)
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
-		folio = kvm_gmem_get_folio(inode, index);
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
+	struct kvm *kvm = gmem->kvm;
 
-		cond_resched();
+	if (xa_find(&gmem->bindings, &start, end - 1, XA_PRESENT)) {
+		KVM_MMU_LOCK(kvm);
+		kvm_mmu_invalidate_end(kvm);
+		KVM_MMU_UNLOCK(kvm);
 	}
-
-	filemap_invalidate_unlock_shared(mapping);
-
-	return r;
 }
 
-static long kvm_gmem_fallocate(struct file *file, int mode, loff_t offset,
-			       loff_t len)
+static void kvm_gmem_invalidate_end(struct inode *inode, pgoff_t offset, unsigned long nr)
 {
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
+	struct kvm_gmem *gmem;
 
-	if (!ret)
-		file_modified(file);
-	return ret;
+	list_for_each_entry(gmem, &inode->i_mapping->i_private_list, entry)
+		__kvm_gmem_invalidate_end(gmem, offset, offset + nr);
 }
 
-static int kvm_gmem_release(struct inode *inode, struct file *file)
+static void __kvm_gmem_release(struct inode *inode, struct kvm_gmem *gmem)
 {
-	struct kvm_gmem *gmem = file->private_data;
 	struct kvm_memory_slot *slot;
 	struct kvm *kvm = gmem->kvm;
 	unsigned long index;
@@ -274,8 +138,8 @@ static int kvm_gmem_release(struct inode *inode, struct file *file)
 	 * Zap all SPTEs pointed at by this file.  Do not free the backing
 	 * memory, as its lifetime is associated with the inode, not the file.
 	 */
-	kvm_gmem_invalidate_begin(gmem, 0, -1ul);
-	kvm_gmem_invalidate_end(gmem, 0, -1ul);
+	__kvm_gmem_invalidate_begin(gmem, 0, -1ul);
+	__kvm_gmem_invalidate_end(gmem, 0, -1ul);
 
 	list_del(&gmem->entry);
 
@@ -287,6 +151,14 @@ static int kvm_gmem_release(struct inode *inode, struct file *file)
 	kfree(gmem);
 
 	kvm_put_kvm(kvm);
+}
+
+static int kvm_gmem_release(struct inode *inode)
+{
+	struct kvm_gmem *gmem;
+
+	list_for_each_entry(gmem, &inode->i_mapping->i_private_list, entry)
+		__kvm_gmem_release(inode, gmem);
 
 	return 0;
 }
@@ -302,94 +174,11 @@ static inline struct file *kvm_gmem_get_file(struct kvm_memory_slot *slot)
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
-#ifdef CONFIG_HAVE_KVM_ARCH_GMEM_INVALIDATE
-static void kvm_gmem_free_folio(struct folio *folio)
-{
-	struct page *page = folio_page(folio, 0);
-	kvm_pfn_t pfn = page_to_pfn(page);
-	int order = folio_order(folio);
-
-	kvm_arch_gmem_invalidate(pfn, pfn + (1ul << order));
-}
-#endif
-
-static const struct address_space_operations kvm_gmem_aops = {
-	.dirty_folio = noop_dirty_folio,
-	.migrate_folio	= kvm_gmem_migrate_folio,
-	.error_remove_folio = kvm_gmem_error_folio,
-#ifdef CONFIG_HAVE_KVM_ARCH_GMEM_INVALIDATE
-	.free_folio = kvm_gmem_free_folio,
-#endif
-};
-
-static int kvm_gmem_getattr(struct mnt_idmap *idmap, const struct path *path,
-			    struct kstat *stat, u32 request_mask,
-			    unsigned int query_flags)
-{
-	struct inode *inode = path->dentry->d_inode;
-
-	generic_fillattr(idmap, request_mask, inode, stat);
-	return 0;
-}
-
-static int kvm_gmem_setattr(struct mnt_idmap *idmap, struct dentry *dentry,
-			    struct iattr *attr)
-{
-	return -EINVAL;
-}
-static const struct inode_operations kvm_gmem_iops = {
-	.getattr	= kvm_gmem_getattr,
-	.setattr	= kvm_gmem_setattr,
+static const struct guest_memfd_operations kvm_gmem_ops = {
+	.invalidate_begin = kvm_gmem_invalidate_begin,
+	.invalidate_end = kvm_gmem_invalidate_end,
+	.prepare_inaccessible = kvm_gmem_prepare_inaccessible,
+	.release = kvm_gmem_release,
 };
 
 static int __kvm_gmem_create(struct kvm *kvm, loff_t size, u64 flags)
@@ -410,28 +199,16 @@ static int __kvm_gmem_create(struct kvm *kvm, loff_t size, u64 flags)
 		goto err_fd;
 	}
 
-	file = anon_inode_create_getfile(anon_name, &kvm_gmem_fops, gmem,
-					 O_RDWR, NULL);
+	file = guest_memfd_alloc(anon_name, &kvm_gmem_ops, size,
+				 GUEST_MEMFD_FLAG_CLEAR_INACCESSIBLE);
 	if (IS_ERR(file)) {
 		err = PTR_ERR(file);
 		goto err_gmem;
 	}
 
-	file->f_flags |= O_LARGEFILE;
-
 	inode = file->f_inode;
 	WARN_ON(file->f_mapping != inode->i_mapping);
 
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
@@ -462,6 +239,14 @@ int kvm_gmem_create(struct kvm *kvm, struct kvm_create_guest_memfd *args)
 	return __kvm_gmem_create(kvm, size, flags);
 }
 
+static inline struct kvm_gmem *file_to_kvm_gmem(struct file *file)
+{
+	if (!is_guest_memfd(file, &kvm_gmem_ops))
+		return NULL;
+
+	return inode_to_kvm_gmem(file_inode(file));
+}
+
 int kvm_gmem_bind(struct kvm *kvm, struct kvm_memory_slot *slot,
 		  unsigned int fd, loff_t offset)
 {
@@ -478,11 +263,8 @@ int kvm_gmem_bind(struct kvm *kvm, struct kvm_memory_slot *slot,
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
@@ -539,7 +321,9 @@ void kvm_gmem_unbind(struct kvm_memory_slot *slot)
 	if (!file)
 		return;
 
-	gmem = file->private_data;
+	gmem = file_to_kvm_gmem(file);
+	if (WARN_ON_ONCE(!gmem))
+		return;
 
 	filemap_invalidate_lock(file->f_mapping);
 	xa_store_range(&gmem->bindings, start, end - 1, NULL, GFP_KERNEL);
@@ -553,7 +337,7 @@ void kvm_gmem_unbind(struct kvm_memory_slot *slot)
 /* Returns a locked folio on success.  */
 static struct folio *
 __kvm_gmem_get_pfn(struct file *file, struct kvm_memory_slot *slot,
-		   gfn_t gfn, kvm_pfn_t *pfn, bool *is_prepared,
+		   gfn_t gfn, kvm_pfn_t *pfn, bool accessible,
 		   int *max_order)
 {
 	pgoff_t index = gfn - slot->base_gfn + slot->gmem.pgoff;
@@ -565,19 +349,27 @@ __kvm_gmem_get_pfn(struct file *file, struct kvm_memory_slot *slot,
 		return ERR_PTR(-EFAULT);
 	}
 
-	gmem = file->private_data;
+	gmem = file_to_kvm_gmem(file);
+	if (WARN_ON_ONCE(!gmem))
+		return ERR_PTR(-EFAULT);
+
 	if (xa_load(&gmem->bindings, index) != slot) {
 		WARN_ON_ONCE(xa_load(&gmem->bindings, index));
 		return ERR_PTR(-EIO);
 	}
 
-	folio = kvm_gmem_get_folio(file_inode(file), index);
+	if (accessible)
+		grab_flags = GUEST_MEMFD_GRAB_ACCESSIBLE;
+	else
+		grab_flags = GUEST_MEMFD_GRAB_INACCESSIBLE;
+
+	folio = guest_memfd_grab_folio(file, index, grab_flags);
 	if (IS_ERR(folio))
 		return folio;
 
 	if (folio_test_hwpoison(folio)) {
 		folio_unlock(folio);
-		folio_put(folio);
+		guest_memfd_put_folio(folio, accessible ? 1 : 0);
 		return ERR_PTR(-EHWPOISON);
 	}
 
@@ -585,7 +377,6 @@ __kvm_gmem_get_pfn(struct file *file, struct kvm_memory_slot *slot,
 	if (max_order)
 		*max_order = 0;
 
-	*is_prepared = folio_test_uptodate(folio);
 	return folio;
 }
 
@@ -594,24 +385,22 @@ int kvm_gmem_get_pfn(struct kvm *kvm, struct kvm_memory_slot *slot,
 {
 	struct file *file = kvm_gmem_get_file(slot);
 	struct folio *folio;
-	bool is_prepared = false;
 	int r = 0;
 
 	if (!file)
 		return -EFAULT;
 
-	folio = __kvm_gmem_get_pfn(file, slot, gfn, pfn, &is_prepared, max_order);
+	folio = __kvm_gmem_get_pfn(file, slot, gfn, pfn, false, max_order);
 	if (IS_ERR(folio)) {
 		r = PTR_ERR(folio);
 		goto out;
 	}
 
-	if (!is_prepared)
-		r = kvm_gmem_prepare_folio(kvm, slot, gfn, folio);
-
 	folio_unlock(folio);
 	if (r < 0)
-		folio_put(folio);
+		guest_memfd_put_folio(folio, 0);
+	else
+		guest_memfd_unsafe_folio(folio);
 
 out:
 	fput(file);
@@ -648,7 +437,6 @@ long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long
 	for (i = 0; i < npages; i += (1 << max_order)) {
 		struct folio *folio;
 		gfn_t gfn = start_gfn + i;
-		bool is_prepared = false;
 		kvm_pfn_t pfn;
 
 		if (signal_pending(current)) {
@@ -656,19 +444,12 @@ long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long
 			break;
 		}
 
-		folio = __kvm_gmem_get_pfn(file, slot, gfn, &pfn, &is_prepared, &max_order);
+		folio = __kvm_gmem_get_pfn(file, slot, gfn, &pfn, true, &max_order);
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
@@ -684,11 +465,9 @@ long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long
 
 		p = src ? src + i * PAGE_SIZE : NULL;
 		ret = post_populate(kvm, gfn, pfn, p, max_order, opaque);
-		if (!ret)
-			kvm_gmem_mark_prepared(folio);
 
 put_folio_and_exit:
-		folio_put(folio);
+		guest_memfd_put_folio(folio, 1);
 		if (ret)
 			break;
 	}
diff --git a/virt/kvm/kvm_main.c b/virt/kvm/kvm_main.c
index cb2b78e92910f..f94a36ca17fe2 100644
--- a/virt/kvm/kvm_main.c
+++ b/virt/kvm/kvm_main.c
@@ -6514,8 +6514,6 @@ int kvm_init(unsigned vcpu_size, unsigned vcpu_align, struct module *module)
 	if (WARN_ON_ONCE(r))
 		goto err_vfio;
 
-	kvm_gmem_init(module);
-
 	/*
 	 * Registration _must_ be the very last thing done, as this exposes
 	 * /dev/kvm to userspace, i.e. all infrastructure must be setup!
diff --git a/virt/kvm/kvm_mm.h b/virt/kvm/kvm_mm.h
index 715f19669d01f..6336a4fdcf505 100644
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

## [5] Elliot Berman — 2024-08-29
*Subject: [PATCH RFC v2 4/5] mm: guest_memfd: Add ability for userspace to
 mmap pages*

"Inaccessible" and "accessible" state are properly tracked by the
guest_memfd. Userspace can now safely access pages to preload binaries
in a hypervisor/architecture-agnostic manner.

Signed-off-by: Elliot Berman <quic_eberman@quicinc.com>
---
 mm/guest_memfd.c | 46 ++++++++++++++++++++++++++++++++++++++++++++++
 1 file changed, 46 insertions(+)

diff --git a/mm/guest_memfd.c b/mm/guest_memfd.c
index 62cb576248a9d..194b2c3ea1525 100644
--- a/mm/guest_memfd.c
+++ b/mm/guest_memfd.c
@@ -279,6 +279,51 @@ int guest_memfd_make_inaccessible(struct folio *folio)
 }
 EXPORT_SYMBOL_GPL(guest_memfd_make_inaccessible);
 
+static vm_fault_t gmem_fault(struct vm_fault *vmf)
+{
+	struct file *file = vmf->vma->vm_file;
+	struct guest_memfd_private *private;
+	struct folio *folio;
+
+	folio = guest_memfd_grab_folio(file, vmf->pgoff, GUEST_MEMFD_GRAB_ACCESSIBLE);
+	if (IS_ERR(folio))
+		return VM_FAULT_SIGBUS;
+
+	vmf->page = folio_page(folio, vmf->pgoff - folio_index(folio));
+
+	/**
+	 * Drop the safe and accessible references, the folio refcount will
+	 * be preserved and unmap_mapping_folio() will decrement the
+	 * refcount when converting to inaccessible.
+	 */
+	private = folio_get_private(folio);
+	atomic_dec(&private->accessible);
+	atomic_dec(&private->safe);
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
+	if (!ops->prepare_accessible)
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
@@ -390,6 +435,7 @@ static int gmem_release(struct inode *inode, struct file *file)
 static const struct file_operations gmem_fops = {
 	.open = generic_file_open,
 	.llseek = generic_file_llseek,
+	.mmap = gmem_mmap,
 	.release = gmem_release,
 	.fallocate = gmem_fallocate,
 	.owner = THIS_MODULE,

---

## [6] Elliot Berman — 2024-08-29
*Subject: [PATCH RFC v2 5/5] mm: guest_memfd: Add option to remove
 inaccessible memory from direct map*

When memory is made inaccessible to the host, Linux may still
speculatively access the folio if a load_unaligned_zeropad is performed
at the end of the prior page. To ensure Linux itself catches such errors
without hypervisor crashing Linux, unmap the guest-inaccessible pages
from the direct map.

This feature is made optional because arm64 pKVM can provide a special,
detectable fault which can be fixed up directly.

Signed-off-by: Elliot Berman <quic_eberman@quicinc.com>
---
 include/linux/guest_memfd.h |  1 +
 mm/guest_memfd.c            | 79 +++++++++++++++++++++++++++++++++++++++++++--
 2 files changed, 78 insertions(+), 2 deletions(-)

diff --git a/include/linux/guest_memfd.h b/include/linux/guest_memfd.h
index 66e5d3ab42613..de53bce15db99 100644
--- a/include/linux/guest_memfd.h
+++ b/include/linux/guest_memfd.h
@@ -33,6 +33,7 @@ enum guest_memfd_grab_flags {
 
 enum guest_memfd_create_flags {
 	GUEST_MEMFD_FLAG_CLEAR_INACCESSIBLE = (1UL << 0),
+	GUEST_MEMFD_FLAG_REMOVE_DIRECT_MAP = (1UL << 1),
 };
 
 struct folio *guest_memfd_grab_folio(struct file *file, pgoff_t index, u32 flags);
diff --git a/mm/guest_memfd.c b/mm/guest_memfd.c
index 194b2c3ea1525..d4232739d4c5b 100644
--- a/mm/guest_memfd.c
+++ b/mm/guest_memfd.c
@@ -8,6 +8,7 @@
 #include <linux/falloc.h>
 #include <linux/guest_memfd.h>
 #include <linux/pagemap.h>
+#include <linux/set_memory.h>
 #include <linux/wait.h>
 
 #include "internal.h"
@@ -26,6 +27,45 @@ struct guest_memfd_private {
 	atomic_t safe;
 };
 
+static inline int folio_set_direct_map_invalid_noflush(struct folio *folio)
+{
+	unsigned long i, nr = folio_nr_pages(folio);
+	int r;
+
+	for (i = 0; i < nr; i++) {
+		struct page *page = folio_page(folio, i);
+
+		r = set_direct_map_invalid_noflush(page);
+		if (r)
+			goto out_remap;
+	}
+	/**
+	 * Currently no need to flush as hypervisor will also be flushing
+	 * tlb when giving the folio to guest.
+	 */
+
+	return 0;
+out_remap:
+	for (; i > 0; i--) {
+		struct page *page = folio_page(folio, i - 1);
+
+		BUG_ON(set_direct_map_default_noflush(page));
+	}
+
+	return r;
+}
+
+static inline void folio_set_direct_map_default_noflush(struct folio *folio)
+{
+	unsigned long i, nr = folio_nr_pages(folio);
+
+	for (i = 0; i < nr; i++) {
+		struct page *page = folio_page(folio, i);
+
+		BUG_ON(set_direct_map_default_noflush(page));
+	}
+}
+
 static inline int base_safe_refs(struct folio *folio)
 {
 	/* 1 for filemap */
@@ -131,6 +171,12 @@ struct folio *guest_memfd_grab_folio(struct file *file, pgoff_t index, u32 flags
 				goto out_free;
 		}
 	} else {
+		if (gmem_flags & GUEST_MEMFD_FLAG_REMOVE_DIRECT_MAP) {
+			r = folio_set_direct_map_invalid_noflush(folio);
+			if (r < 0)
+				goto out_free;
+		}
+
 		if (ops->prepare_inaccessible) {
 			r = ops->prepare_inaccessible(inode, folio);
 			if (r < 0)
@@ -203,6 +249,7 @@ int guest_memfd_make_accessible(struct folio *folio)
 	struct guest_memfd_private *private = folio_get_private(folio);
 	struct inode *inode = folio_inode(folio);
 	struct guest_memfd_operations *ops = inode->i_private;
+	unsigned long gmem_flags;
 	int r;
 
 	/*
@@ -218,6 +265,10 @@ int guest_memfd_make_accessible(struct folio *folio)
 	if (!r)
 		return -EBUSY;
 
+	gmem_flags = (unsigned long)inode->i_mapping->i_private_data;
+	if (gmem_flags & GUEST_MEMFD_FLAG_REMOVE_DIRECT_MAP)
+		folio_set_direct_map_default_noflush(folio);
+
 	if (ops->prepare_accessible) {
 		r = ops->prepare_accessible(inode, folio);
 		if (r)
@@ -248,6 +299,7 @@ int guest_memfd_make_inaccessible(struct folio *folio)
 	struct guest_memfd_private *private = folio_get_private(folio);
 	struct inode *inode = folio_inode(folio);
 	struct guest_memfd_operations *ops = inode->i_private;
+	unsigned long gmem_flags;
 	int r;
 
 	r = atomic_dec_if_positive(&private->accessible);
@@ -266,6 +318,13 @@ int guest_memfd_make_inaccessible(struct folio *folio)
 		goto err;
 	}
 
+	gmem_flags = (unsigned long)inode->i_mapping->i_private_data;
+	if (gmem_flags & GUEST_MEMFD_FLAG_REMOVE_DIRECT_MAP) {
+		r = folio_set_direct_map_invalid_noflush(folio);
+		if (r)
+			goto err;
+	}
+
 	if (ops->prepare_inaccessible) {
 		r = ops->prepare_inaccessible(inode, folio);
 		if (r)
@@ -454,6 +513,7 @@ static int gmem_error_folio(struct address_space *mapping, struct folio *folio)
 	struct guest_memfd_operations *ops = inode->i_private;
 	off_t offset = folio->index;
 	size_t nr = folio_nr_pages(folio);
+	unsigned long gmem_flags;
 	int ret;
 
 	filemap_invalidate_lock_shared(mapping);
@@ -464,6 +524,10 @@ static int gmem_error_folio(struct address_space *mapping, struct folio *folio)
 
 	filemap_invalidate_unlock_shared(mapping);
 
+	gmem_flags = (unsigned long)inode->i_mapping->i_private_data;
+	if (gmem_flags & GUEST_MEMFD_FLAG_REMOVE_DIRECT_MAP)
+		folio_set_direct_map_default_noflush(folio);
+
 	return ret;
 }
 
@@ -474,7 +538,7 @@ static bool gmem_release_folio(struct folio *folio, gfp_t gfp)
 	struct guest_memfd_operations *ops = inode->i_private;
 	off_t offset = folio->index;
 	size_t nr = folio_nr_pages(folio);
-	unsigned long val, expected;
+	unsigned long val, expected, gmem_flags;
 	int ret;
 
 	ret = ops->invalidate_begin(inode, offset, nr);
@@ -483,6 +547,10 @@ static bool gmem_release_folio(struct folio *folio, gfp_t gfp)
 	if (ops->invalidate_end)
 		ops->invalidate_end(inode, offset, nr);
 
+	gmem_flags = (unsigned long)inode->i_mapping->i_private_data;
+	if (gmem_flags & GUEST_MEMFD_FLAG_REMOVE_DIRECT_MAP)
+		folio_set_direct_map_default_noflush(folio);
+
 	expected = base_safe_refs(folio);
 	val = atomic_read(&private->safe);
 	WARN_ONCE(val != expected, "folio[%x] safe ref: %d != expected %d\n",
@@ -518,7 +586,14 @@ static inline bool guest_memfd_check_ops(const struct guest_memfd_operations *op
 
 static inline unsigned long guest_memfd_valid_flags(void)
 {
-	return GUEST_MEMFD_FLAG_CLEAR_INACCESSIBLE;
+	unsigned long flags = GUEST_MEMFD_FLAG_CLEAR_INACCESSIBLE;
+
+#ifdef CONFIG_ARCH_HAS_SET_DIRECT_MAP
+	if (can_set_direct_map())
+		flags |= GUEST_MEMFD_FLAG_REMOVE_DIRECT_MAP;
+#endif
+
+	return flags;
 }
 
 /**

---

## [7] Vishal Annapurve — 2024-10-10
*Subject: Re: [PATCH RFC v2 2/5] mm: guest_memfd: Allow folios to be accessible
 to host*

On Fri, Aug 30, 2024 at 3:55 AM Elliot Berman <quic_eberman@quicinc.com> wrote:
>
> Memory given to a confidential VM sometimes needs to be accessible by

This is a long due response after discussion at LPC. In order to
support hugepages with guest memfd, the current direction is to split
hugepages on memory conversion [1]. During LPC session [2], we
discussed the need of reconstructing split hugepages before giving
back the memory to hugepage allocator. After the session I discussed
this topic with David H and I think that the best way to handle
reconstruction would be to get a callback from folio_put when the last
refcount of pages backing guest shared memory is dropped. Reason being
that get/pin_user_pages* don't increase inode refcount and so
guest_memfd inode can get cleaned up while backing memory is still
pinned e.g. by VFIO pinning memory ranges to setup IOMMU pagetables.

If such a callback is supported, I believe we don't need to implement
the "safe refcount" logic.  shared -> private conversion (should be
similar for truncation) handling by guest_memfd may look like:
1) Drop all the guest_memfd internal refcounts on pages backing
converted ranges.
2) Tag such pages such that core-mm invokes a callback implemented by
guest_memfd when the last refcount gets dropped.
At this point I feel that the mechanism to achieve step 2 above should
be a small modification in core-mm logic which should be generic
enough and will not need piggy-backing on ZONE_DEVICE memory handling
which already carries similar logic [3].

Private memory doesn't need such a special callback since we discussed
at LPC about the desired policy to be:
1) Guest memfd owns all long-term refcounts on private memory.
2) Any short-term refcounts distributed outside guest_memfd should be
protected by folio locks.
3) On truncation/conversion, guest memfd private memory users will be
notified to unmap/refresh the memory mappings.

i.e. After private -> shared conversion, it would be guaranteed that
there are no active users of guest private memory.

[1] Linux MM Alignment Session:
https://lore.kernel.org/all/20240712232937.2861788-1-ackerleytng@google.com/
[2] https://lpc.events/event/18/contributions/1764/
[3] https://elixir.bootlin.com/linux/v6.11.2/source/mm/swap.c#L117

>
> Transition between accessible and inaccessible is allowed only when:

---

## [8] Paolo Bonzini — 2024-10-10
*Subject: Re: [PATCH RFC v2 0/5] mm: Introduce guest_memfd library*

On 8/30/24 00:24, Elliot Berman wrote:
> In preparation for adding more features to KVM's guest_memfd, refactor
> and introduce a library which abstracts some of the core-mm decisions

Was there any discussion on this change?  If not, can you explain it a 
bit more since it's the biggest change compared to the KVM design?  I 
suppose the reference counting is used in relation to mmap, but it would 
be nice to have a few more words on how the counts are used and an 
explanation of when (especially) the accessible atomic_t can take any 
value other than 0/1.

As an aside, allocating 8 bytes of per-folio private memory (and 
dereferencing the pointer, too) is a bit of a waste considering that the 
private pointer itself is 64 bits on all platforms of interest.

Paolo

> - Link to v1:
>    https://lore.kernel.org/r/20240805-guest-memfd-lib-v1-0-e5a29a4ff5d7@quicinc.com

I think I'd rather have this in virt/lib.

Paolo

---

## [9] Elliot Berman — 2024-10-10
*Subject: Re: [PATCH RFC v2 0/5] mm: Introduce guest_memfd library*

On Thu, Oct 10, 2024 at 03:04:16PM +0200, Paolo Bonzini wrote:
> On 8/30/24 00:24, Elliot Berman wrote:
> > In preparation for adding more features to KVM's guest_memfd, refactor

The accessible and safe refcount was discussed in the PUCK and over the
mailing lists in the previous version of this patchset.

That being said though, after discussions at LPC, I'm now behind the
design Fuad has recently posted [1]. I was on vacation last week and I
still need to go through his series, but we had discussed the key parts
of the design offline.

[1]: https://lore.kernel.org/all/20241010085930.1546800-1-tabba@google.com/

> the reference counting is used in relation to mmap, but it would be nice to
> have a few more words on how the counts are used and an explanation of when

---

## [10] Mike Day — 2024-10-22
*Subject: Re: [PATCH RFC v2 3/5] kvm: Convert to use guest_memfd library*

On 8/29/24 17:24, Elliot Berman wrote:
> Use the recently created mm/guest_memfd implementation. No functional
> change intended.

Is there an updated patchset?

> 
> Signed-off-by: Elliot Berman <quic_eberman@quicinc.com>

Need to keep rmp_make_private(), it is updating firmware reverse mapping (RMP) to assign the folio to the
guest. Would be used in combination with guest_memfd_make_inaccessible(), but that call cannot be
made from here, needs to move elsewhere.

> +static inline struct kvm_gmem *inode_to_kvm_gmem(struct inode *inode)
> +{

gmem SEV-SNP guests end up creating multiple struct kvm_gmem objects per guest, each one having
different memory slots. So this will not always return the correct gmem object for an SEV-SNP guest.
> +}
> +

There is no longer a struct kvm_memory_slot * in the prototype, so this won't compile. It creates
an impedence mismatch with the way kvm gmem calls prepare_folio() on SEV-SNP.

>   	int rc = kvm_arch_gmem_prepare(kvm, gfn, pfn, folio_order(folio));
>   	if (rc) {
mark_prepared takes on additional meaning with SEV-SNP beyond uptodate, although this
could be separated into a different state. "preparation" includes setting the Reverse MaPping (RMP)
assigned bit - it eventually ends up in the sev code making and RMP assignment and
clearing the folio (from :/arch/x86/kvm/svm/sev.c)

	if (!folio_test_uptodate(folio)) {
		unsigned long nr_pages = level == PG_LEVEL_4K ? 1 : 512;
		int i;

		pr_debug("%s: folio not up-to-date, clearing folio pages.\n", __func__);
		for (i = 0; i < nr_pages; i++)
			clear_highpage(pfn_to_page(pfn_aligned + i));

{mark|test}_uptodate is still intertwined with the architectural code, probably should be
disentangled in favor of "prepare."

> -
> -/*

Is it correct that gmem->prepare_inaccessible() is the direct analogue to
kvm_gmem_prepare_folio?

> -#ifdef CONFIG_HAVE_KVM_ARCH_GMEM_INVALIDATE
> -static void kvm_gmem_free_folio(struct folio *folio)

kvm_arch_gmem_invalidate() is necessary for gmem SEV-SNP - it calls sev_gmem_invalidate()
which performs RMP modifications and flushes caches. When a guest page is split or released
these operations must occur.

> @@ -656,19 +444,12 @@ long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long
>   			break;

probably need to retain a check _is_prepared() here instead of always declaring the folio prepared.

thanks,

Mike

---
