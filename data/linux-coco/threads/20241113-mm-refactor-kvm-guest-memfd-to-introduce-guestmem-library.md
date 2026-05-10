---
title: 'mm: Refactor KVM guest_memfd to introduce\n guestmem library'
date: 2024-11-13
last_reply: 2024-11-18
message_count: 8
participants: ['Elliot Berman', 'David Hildenbrand']
---

## [1] Elliot Berman — 2024-11-13

In preparation for adding more features to KVM's guest_memfd, refactor
and introduce a library which abtracts some of the core-mm decisions
about managing folios associated with guest memory. The goal of the
refactor serves two purposes:

1. Provide an easier way to reason about memory in guest_memfd. KVM
   needs to support multiple confidentiality models (TDX, SEV, pKVM, Arm
   CCA). These models support different semantics for when the host
   can(not) access guest memory. An abstraction for the allocator and
   managing the state of pages will make it eaiser to reason about the
   state of folios within the guest_memfd.

2. Provide a common implementation for other users such as Gunyah [1] and
   guestmemfs [2].

In this initial series, I'm seeking comments for the line I'm drawing
between library and user (KVM). I've not introduced new functionality in
this series; the first new feature will probably be Fuad's mappability
patches [3].

I've decided to only bring out the address_space from guest_memfd as it
seemed the simplest approach. In the current iteration, KVM "attaches"
the guestmem to the inode. I expect we'll want to provide some helpers
for inode, file, and vm operations when it's relevant to
mappability/accessiblity/faultability.

I'd appreciate any feedback, especially on how much we should pull into
the guestmem library.

[1]: https://lore.kernel.org/lkml/20240222-gunyah-v17-0-1e9da6763d38@quicinc.com/
[2]: https://lore.kernel.org/all/20240805093245.889357-1-jgowans@amazon.com/
[3]: https://lore.kernel.org/all/20241010085930.1546800-3-tabba@google.com/

Changes in v3:
 - Refactor/extract only the address_space
 - Link to v2: https://lore.kernel.org/all/20240829-guest-memfd-lib-v2-0-b9afc1ff3656@quicinc.com/

Changes in v2:
- Significantly reworked to introduce "accessible" and "safe" reference
  counters
- Link to v1: https://lore.kernel.org/r/20240805-guest-memfd-lib-v1-0-e5a29a4ff5d7@quicinc.com

Signed-off-by: Elliot Berman <quic_eberman@quicinc.com>
---
Elliot Berman (2):
      KVM: guest_memfd: Convert .free_folio() to .release_folio()
      mm: guestmem: Convert address_space operations to guestmem library

 MAINTAINERS              |   2 +
 include/linux/guestmem.h |  33 +++++++
 mm/Kconfig               |   3 +
 mm/Makefile              |   1 +
 mm/guestmem.c            | 232 +++++++++++++++++++++++++++++++++++++++++++++++
 virt/kvm/Kconfig         |   1 +
 virt/kvm/guest_memfd.c   | 107 +++++++---------------
 7 files changed, 305 insertions(+), 74 deletions(-)
---
base-commit: 5cb1659f412041e4780f2e8ee49b2e03728a2ba6
change-id: 20241112-guestmem-library-68363cb29186

Best regards,

---

## [2] Elliot Berman — 2024-11-13
*Subject: [PATCH RFC v3 1/2] KVM: guest_memfd: Convert .free_folio() to
 .release_folio()*

When guest_memfd becomes a library, a callback will need to be made to
the owner (KVM SEV) to transition pages back to hypervisor-owned/shared
state. This is currently being done as part of .free_folio() address
space op, but this callback shouldn't assume that the mapping still
exists. guest_memfd library will need the mapping to still exist to look
up its operations table.

.release_folio() and .invalidate_folio() address space ops can serve the
same purpose here. The key difference between release_folio() and
free_folio() is whether the mapping is still valid at time of the
callback. This approach was discussed in the link in the footer, but not
taken because free_folio() was easier to implement.

Link: https://lore.kernel.org/kvm/20231016115028.996656-1-michael.roth@amd.com/
Signed-off-by: Elliot Berman <quic_eberman@quicinc.com>
---
 virt/kvm/guest_memfd.c | 19 ++++++++++++++++---
 1 file changed, 16 insertions(+), 3 deletions(-)

diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index 47a9f68f7b247f4cba0c958b4c7cd9458e7c46b4..13f83ad8a4c26ba82aca4f2684f22044abb4bc19 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -358,22 +358,35 @@ static int kvm_gmem_error_folio(struct address_space *mapping, struct folio *fol
 }
 
 #ifdef CONFIG_HAVE_KVM_ARCH_GMEM_INVALIDATE
-static void kvm_gmem_free_folio(struct folio *folio)
+static bool kvm_gmem_release_folio(struct folio *folio, gfp_t gfp)
 {
 	struct page *page = folio_page(folio, 0);
 	kvm_pfn_t pfn = page_to_pfn(page);
 	int order = folio_order(folio);
 
 	kvm_arch_gmem_invalidate(pfn, pfn + (1ul << order));
+
+	return true;
+}
+
+static void kvm_gmem_invalidate_folio(struct folio *folio, size_t offset,
+				      size_t len)
+{
+	WARN_ON_ONCE(offset != 0);
+	WARN_ON_ONCE(len != folio_size(folio));
+
+	if (offset == 0 && len == folio_size(folio))
+		filemap_release_folio(folio, 0);
 }
 #endif
 
 static const struct address_space_operations kvm_gmem_aops = {
 	.dirty_folio = noop_dirty_folio,
-	.migrate_folio	= kvm_gmem_migrate_folio,
+	.migrate_folio = kvm_gmem_migrate_folio,
 	.error_remove_folio = kvm_gmem_error_folio,
 #ifdef CONFIG_HAVE_KVM_ARCH_GMEM_INVALIDATE
-	.free_folio = kvm_gmem_free_folio,
+	.release_folio = kvm_gmem_release_folio,
+	.invalidate_folio = kvm_gmem_invalidate_folio,
 #endif
 };

---

## [3] Elliot Berman — 2024-11-13
*Subject: [PATCH RFC v3 2/2] mm: guestmem: Convert address_space operations
 to guestmem library*

A few near-term features are coming to guest_memfd which make sense to
create a built-in library.
 - pKVM will introduce MMU-based protection for guests and allow guest
   memory to be switched between "guest-private" and "accessible to
   host". Additional tracking is needed to manage the state of pages as
   accessing "guest-private" pages crashes the host.
 - Introduction of large folios requires tracking since guests will not
   have awareness whether the memory backing a page is huge or not.
   Guests may wish to share only a partial page.
 - Gunyah hypervisor support will be added and also make use of guestmem
   for its MMU-based protection.

The address_space is targeted for the guestmem library.  KVM still
"owns" the inode and file.

MAINTAINERS is updated with explicit references to guestmem files
else the stm maintainers are automatically added.

Tested with:
run_kselftest.sh -t kvm:guest_memfd_test -t kvm:set_memory_region_test

Signed-off-by: Elliot Berman <quic_eberman@quicinc.com>
---
 MAINTAINERS              |   2 +
 include/linux/guestmem.h |  33 +++++++
 mm/Kconfig               |   3 +
 mm/Makefile              |   1 +
 mm/guestmem.c            | 232 +++++++++++++++++++++++++++++++++++++++++++++++
 virt/kvm/Kconfig         |   1 +
 virt/kvm/guest_memfd.c   | 112 ++++++-----------------
 7 files changed, 301 insertions(+), 83 deletions(-)

diff --git a/MAINTAINERS b/MAINTAINERS
index 391fe4b106f8cb7e1cc0b4184dc121ac74d8e00a..c684248ce65d99d62dc616c8bc6c1a7419bd6f4d 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -14888,6 +14888,7 @@ T:	git git://git.kernel.org/pub/scm/linux/kernel/git/akpm/mm
 T:	quilt git://git.kernel.org/pub/scm/linux/kernel/git/akpm/25-new
 F:	include/linux/gfp.h
 F:	include/linux/gfp_types.h
+F:	include/linux/guestmem.h
 F:	include/linux/memfd.h
 F:	include/linux/memory.h
 F:	include/linux/memory_hotplug.h
@@ -14903,6 +14904,7 @@ F:	include/linux/pagewalk.h
 F:	include/linux/rmap.h
 F:	include/trace/events/ksm.h
 F:	mm/
+F:	mm/guestmem.c
 F:	tools/mm/
 F:	tools/testing/selftests/mm/
 N:	include/linux/page[-_]*
diff --git a/include/linux/guestmem.h b/include/linux/guestmem.h
new file mode 100644
index 0000000000000000000000000000000000000000..4beb37adb5e541015fcc12a45930613c686c5580
--- /dev/null
+++ b/include/linux/guestmem.h
@@ -0,0 +1,33 @@
+/* SPDX-License-Identifier: GPL-2.0 */
+#ifndef _LINUX_GUESTMEM_H
+#define _LINUX_GUESTMEM_H
+
+struct address_space;
+struct list_head;
+
+/**
+ * struct guestmem_ops - Hypervisor-specific maintenance operations to perform on folios
+ * @release_folio - Try to bring the folio back to fully owned by Linux
+ *		    for instance: about to free the folio [optional]
+ * @invalidate_begin - start invalidating mappings between start and end offsets
+ * @invalidate_end - paired with ->invalidate_begin() [optional]
+ */
+struct guestmem_ops {
+	bool (*release_folio)(struct list_head *entry, struct folio *folio);
+	int (*invalidate_begin)(struct list_head *entry, pgoff_t start,
+				pgoff_t end);
+	void (*invalidate_end)(struct list_head *entry, pgoff_t start,
+			       pgoff_t end);
+};
+
+int guestmem_attach_mapping(struct address_space *mapping,
+			    const struct guestmem_ops *const ops,
+			    struct list_head *data);
+void guestmem_detach_mapping(struct address_space *mapping,
+			     struct list_head *data);
+
+struct folio *guestmem_grab_folio(struct address_space *mapping, pgoff_t index);
+int guestmem_punch_hole(struct address_space *mapping, loff_t offset,
+			loff_t len);
+
+#endif
diff --git a/mm/Kconfig b/mm/Kconfig
index 4c9f5ea13271d1f90163e75a35adf619ada3a5cd..48c911d3dbc1645b478d0626a5d86f5fec154b15 100644
--- a/mm/Kconfig
+++ b/mm/Kconfig
@@ -1190,6 +1190,9 @@ config SECRETMEM
 	  memory areas visible only in the context of the owning process and
 	  not mapped to other processes and other kernel page tables.
 
+config GUESTMEM
+	bool
+
 config ANON_VMA_NAME
 	bool "Anonymous VMA name support"
 	depends on PROC_FS && ADVISE_SYSCALLS && MMU
diff --git a/mm/Makefile b/mm/Makefile
index d5639b03616636e4d49913f76865e24edb270f73..4d5f003d69c8969aaae0615106b90600ef638719 100644
--- a/mm/Makefile
+++ b/mm/Makefile
@@ -136,6 +136,7 @@ obj-$(CONFIG_PERCPU_STATS) += percpu-stats.o
 obj-$(CONFIG_ZONE_DEVICE) += memremap.o
 obj-$(CONFIG_HMM_MIRROR) += hmm.o
 obj-$(CONFIG_MEMFD_CREATE) += memfd.o
+obj-$(CONFIG_GUESTMEM) += guestmem.o
 obj-$(CONFIG_MAPPING_DIRTY_HELPERS) += mapping_dirty_helpers.o
 obj-$(CONFIG_PTDUMP_CORE) += ptdump.o
 obj-$(CONFIG_PAGE_REPORTING) += page_reporting.o
diff --git a/mm/guestmem.c b/mm/guestmem.c
new file mode 100644
index 0000000000000000000000000000000000000000..21e93b2b6b18036c733e1afbccff3392ff6a6604
--- /dev/null
+++ b/mm/guestmem.c
@@ -0,0 +1,232 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/*
+ * guestmem library
+ *
+ * Copyright (c) 2024 Qualcomm Innovation Center, Inc. All rights reserved.
+ */
+
+#include <linux/fs.h>
+#include <linux/guestmem.h>
+#include <linux/mm.h>
+#include <linux/pagemap.h>
+
+struct guestmem {
+	const struct guestmem_ops *ops;
+};
+
+static inline struct guestmem *folio_to_guestmem(struct folio *folio)
+{
+	struct address_space *const mapping = folio->mapping;
+
+	return mapping->i_private_data;
+}
+
+static inline bool __guestmem_release_folio(struct address_space *const mapping,
+					    struct folio *folio)
+{
+	struct guestmem *gmem = mapping->i_private_data;
+	struct list_head *entry;
+
+	if (gmem->ops->release_folio) {
+		list_for_each(entry, &mapping->i_private_list) {
+			if (!gmem->ops->release_folio(entry, folio))
+				return false;
+		}
+	}
+
+	return true;
+}
+
+static inline int
+__guestmem_invalidate_begin(struct address_space *const mapping, pgoff_t start,
+			    pgoff_t end)
+{
+	struct guestmem *gmem = mapping->i_private_data;
+	struct list_head *entry;
+	int ret = 0;
+
+	list_for_each(entry, &mapping->i_private_list) {
+		ret = gmem->ops->invalidate_begin(entry, start, end);
+		if (ret)
+			return ret;
+	}
+
+	return 0;
+}
+
+static inline void
+__guestmem_invalidate_end(struct address_space *const mapping, pgoff_t start,
+			  pgoff_t end)
+{
+	struct guestmem *gmem = mapping->i_private_data;
+	struct list_head *entry;
+
+	if (gmem->ops->invalidate_end) {
+		list_for_each(entry, &mapping->i_private_list)
+			gmem->ops->invalidate_end(entry, start, end);
+	}
+}
+
+static bool guestmem_release_folio(struct folio *folio, gfp_t gfp)
+{
+	return __guestmem_release_folio(folio->mapping, folio);
+}
+
+static void guestmem_invalidate_folio(struct folio *folio, size_t offset,
+				      size_t len)
+{
+	WARN_ON_ONCE(offset != 0);
+	WARN_ON_ONCE(len != folio_size(folio));
+
+	if (offset == 0 && len == folio_size(folio))
+		WARN_ON_ONCE(filemap_release_folio(folio, 0));
+}
+
+static int guestmem_error_folio(struct address_space *mapping,
+				struct folio *folio)
+{
+	pgoff_t start, end;
+	int ret;
+
+	filemap_invalidate_lock_shared(mapping);
+
+	start = folio->index;
+	end = start + folio_nr_pages(folio);
+
+	ret = __guestmem_invalidate_begin(mapping, start, end);
+	if (ret)
+		goto out;
+
+	/*
+	 * Do not truncate the range, what action is taken in response to the
+	 * error is userspace's decision (assuming the architecture supports
+	 * gracefully handling memory errors).  If/when the guest attempts to
+	 * access a poisoned page, kvm_gmem_get_pfn() will return -EHWPOISON,
+	 * at which point KVM can either terminate the VM or propagate the
+	 * error to userspace.
+	 */
+
+	__guestmem_invalidate_end(mapping, start, end);
+
+out:
+	filemap_invalidate_unlock_shared(mapping);
+	return ret ? MF_DELAYED : MF_FAILED;
+}
+
+static int guestmem_migrate_folio(struct address_space *mapping,
+				  struct folio *dst, struct folio *src,
+				  enum migrate_mode mode)
+{
+	WARN_ON_ONCE(1);
+	return -EINVAL;
+}
+
+static const struct address_space_operations guestmem_aops = {
+	.dirty_folio = noop_dirty_folio,
+	.release_folio = guestmem_release_folio,
+	.invalidate_folio = guestmem_invalidate_folio,
+	.error_remove_folio = guestmem_error_folio,
+	.migrate_folio = guestmem_migrate_folio,
+};
+
+/**
+ * guestmem_attach_mapping() - Attach/create a guestmem mapping
+ * @mapping: The address space to attach to
+ * @ops: The guestmem operations to use
+ * @data: Private data to pass to the ops functions
+ */
+int guestmem_attach_mapping(struct address_space *mapping,
+			    const struct guestmem_ops *const ops,
+			    struct list_head *data)
+{
+	struct guestmem *gmem;
+
+	if (mapping->a_ops == &guestmem_aops) {
+		gmem = mapping->i_private_data;
+		if (gmem->ops != ops)
+			return -EINVAL;
+
+		goto add;
+	}
+
+	gmem = kzalloc(sizeof(*gmem), GFP_KERNEL);
+	if (!gmem)
+		return -ENOMEM;
+
+	gmem->ops = ops;
+
+	mapping->a_ops = &guestmem_aops;
+	mapping->i_private_data = gmem;
+
+	mapping_set_gfp_mask(mapping, GFP_HIGHUSER);
+	mapping_set_inaccessible(mapping);
+	/* Unmovable mappings are supposed to be marked unevictable as well. */
+	WARN_ON_ONCE(!mapping_unevictable(mapping));
+
+add:
+	list_add(data, &mapping->i_private_list);
+	return 0;
+}
+EXPORT_SYMBOL_GPL(guestmem_attach_mapping);
+
+/**
+ * guestmem_detach_mapping() - Detach a guestmem mapping
+ * @mapping: The address space to detach
+ * @data: Private data to detach
+ */
+void guestmem_detach_mapping(struct address_space *mapping,
+			     struct list_head *data)
+{
+	list_del(data);
+
+	if (list_empty(&mapping->i_private_list)) {
+		kfree(mapping->i_private_data);
+		mapping->i_private_data = NULL;
+		mapping->a_ops = &empty_aops;
+	}
+}
+EXPORT_SYMBOL_GPL(guestmem_detach_mapping);
+
+/**
+ * guestmem_grab_folio() - Grab a folio from a guestmem mapping
+ * @mapping: The address space to grab from
+ * @index: The index of the folio to grab
+ *
+ * Return: The grabbed folio, or ERR_PTR() on failure.
+ */
+struct folio *guestmem_grab_folio(struct address_space *mapping, pgoff_t index)
+{
+	/* TODO: Support huge pages. */
+	return filemap_grab_folio(mapping, index);
+}
+EXPORT_SYMBOL_GPL(guestmem_grab_folio);
+
+/**
+ * guestmem_put_folio() - Helper to punch a hole in a guestmem mapping
+ * @mapping: The address space to punch a hole in
+ * @offset: The offset to punch a hole at
+ * @len: The length of the hole to punch
+ *
+ * Return: 0 on success, -errno on failure.
+ */
+int guestmem_punch_hole(struct address_space *mapping, loff_t offset,
+			loff_t len)
+{
+	pgoff_t start = offset >> PAGE_SHIFT;
+	pgoff_t end = (offset + len) >> PAGE_SHIFT;
+	int ret;
+
+	filemap_invalidate_lock(mapping);
+	ret = __guestmem_invalidate_begin(mapping, start, end);
+	if (ret)
+		goto out;
+
+	truncate_inode_pages_range(mapping, offset, offset + len - 1);
+
+	__guestmem_invalidate_end(mapping, start, end);
+
+out:
+	filemap_invalidate_unlock(mapping);
+	return ret;
+}
+EXPORT_SYMBOL_GPL(guestmem_punch_hole);
diff --git a/virt/kvm/Kconfig b/virt/kvm/Kconfig
index fd6a3010afa833e077623065b80bdbb5b1012250..1339098795d2e859b2ee0ef419b29045aedc8487 100644
--- a/virt/kvm/Kconfig
+++ b/virt/kvm/Kconfig
@@ -106,6 +106,7 @@ config KVM_GENERIC_MEMORY_ATTRIBUTES
 
 config KVM_PRIVATE_MEM
        select XARRAY_MULTI
+       select GUESTMEM
        bool
 
 config KVM_GENERIC_PRIVATE_MEM
diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index 13f83ad8a4c26ba82aca4f2684f22044abb4bc19..a56a50a89bab42690c7acd9f0ea5fe70d41e3777 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -1,6 +1,7 @@
 // SPDX-License-Identifier: GPL-2.0
 #include <linux/backing-dev.h>
 #include <linux/falloc.h>
+#include <linux/guestmem.h>
 #include <linux/kvm_host.h>
 #include <linux/pagemap.h>
 #include <linux/anon_inodes.h>
@@ -98,8 +99,7 @@ static int kvm_gmem_prepare_folio(struct kvm *kvm, struct kvm_memory_slot *slot,
  */
 static struct folio *kvm_gmem_get_folio(struct inode *inode, pgoff_t index)
 {
-	/* TODO: Support huge pages. */
-	return filemap_grab_folio(inode->i_mapping, index);
+	return guestmem_grab_folio(inode->i_mapping, index);
 }
 
 static void kvm_gmem_invalidate_begin(struct kvm_gmem *gmem, pgoff_t start,
@@ -151,28 +151,7 @@ static void kvm_gmem_invalidate_end(struct kvm_gmem *gmem, pgoff_t start,
 
 static long kvm_gmem_punch_hole(struct inode *inode, loff_t offset, loff_t len)
 {
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
+	return guestmem_punch_hole(inode->i_mapping, offset, len);
 }
 
 static long kvm_gmem_allocate(struct inode *inode, loff_t offset, loff_t len)
@@ -277,7 +256,7 @@ static int kvm_gmem_release(struct inode *inode, struct file *file)
 	kvm_gmem_invalidate_begin(gmem, 0, -1ul);
 	kvm_gmem_invalidate_end(gmem, 0, -1ul);
 
-	list_del(&gmem->entry);
+	guestmem_detach_mapping(inode->i_mapping, &gmem->entry);
 
 	filemap_invalidate_unlock(inode->i_mapping);
 
@@ -318,47 +297,8 @@ void kvm_gmem_init(struct module *module)
 	kvm_gmem_fops.owner = module;
 }
 
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
 #ifdef CONFIG_HAVE_KVM_ARCH_GMEM_INVALIDATE
-static bool kvm_gmem_release_folio(struct folio *folio, gfp_t gfp)
+static bool kvm_gmem_release_folio(struct list_head *entry, struct folio *folio)
 {
 	struct page *page = folio_page(folio, 0);
 	kvm_pfn_t pfn = page_to_pfn(page);
@@ -368,25 +308,31 @@ static bool kvm_gmem_release_folio(struct folio *folio, gfp_t gfp)
 
 	return true;
 }
+#endif
 
-static void kvm_gmem_invalidate_folio(struct folio *folio, size_t offset,
-				      size_t len)
+static int kvm_guestmem_invalidate_begin(struct list_head *entry, pgoff_t start,
+					 pgoff_t end)
 {
-	WARN_ON_ONCE(offset != 0);
-	WARN_ON_ONCE(len != folio_size(folio));
+	struct kvm_gmem *gmem = container_of(entry, struct kvm_gmem, entry);
+
+	kvm_gmem_invalidate_begin(gmem, start, end);
 
-	if (offset == 0 && len == folio_size(folio))
-		filemap_release_folio(folio, 0);
+	return 0;
 }
-#endif
 
-static const struct address_space_operations kvm_gmem_aops = {
-	.dirty_folio = noop_dirty_folio,
-	.migrate_folio = kvm_gmem_migrate_folio,
-	.error_remove_folio = kvm_gmem_error_folio,
+static void kvm_guestmem_invalidate_end(struct list_head *entry, pgoff_t start,
+					pgoff_t end)
+{
+	struct kvm_gmem *gmem = container_of(entry, struct kvm_gmem, entry);
+
+	kvm_gmem_invalidate_end(gmem, start, end);
+}
+
+static const struct guestmem_ops kvm_guestmem_ops = {
+	.invalidate_begin = kvm_guestmem_invalidate_begin,
+	.invalidate_end = kvm_guestmem_invalidate_end,
 #ifdef CONFIG_HAVE_KVM_ARCH_GMEM_INVALIDATE
 	.release_folio = kvm_gmem_release_folio,
-	.invalidate_folio = kvm_gmem_invalidate_folio,
 #endif
 };
 
@@ -442,22 +388,22 @@ static int __kvm_gmem_create(struct kvm *kvm, loff_t size, u64 flags)
 
 	inode->i_private = (void *)(unsigned long)flags;
 	inode->i_op = &kvm_gmem_iops;
-	inode->i_mapping->a_ops = &kvm_gmem_aops;
 	inode->i_mode |= S_IFREG;
 	inode->i_size = size;
-	mapping_set_gfp_mask(inode->i_mapping, GFP_HIGHUSER);
-	mapping_set_inaccessible(inode->i_mapping);
-	/* Unmovable mappings are supposed to be marked unevictable as well. */
-	WARN_ON_ONCE(!mapping_unevictable(inode->i_mapping));
+	err = guestmem_attach_mapping(inode->i_mapping, &kvm_guestmem_ops,
+				      &gmem->entry);
+	if (err)
+		goto err_putfile;
 
 	kvm_get_kvm(kvm);
 	gmem->kvm = kvm;
 	xa_init(&gmem->bindings);
-	list_add(&gmem->entry, &inode->i_mapping->i_private_list);
 
 	fd_install(fd, file);
 	return fd;
 
+err_putfile:
+	fput(file);
 err_gmem:
 	kfree(gmem);
 err_fd:

---

## [4] David Hildenbrand — 2024-11-15
*Subject: Re: [PATCH RFC v3 0/2] mm: Refactor KVM guest_memfd to introduce
 guestmem library*

On 13.11.24 23:34, Elliot Berman wrote:
> In preparation for adding more features to KVM's guest_memfd, refactor
> and introduce a library which abtracts some of the core-mm decisions

Right, or the dummy mmap + vma->set_policy patches for NUMA handling.

---

## [5] David Hildenbrand — 2024-11-15
*Subject: Re: [PATCH RFC v3 1/2] KVM: guest_memfd: Convert .free_folio() to
 .release_folio()*

On 13.11.24 23:34, Elliot Berman wrote:
> When guest_memfd becomes a library, a callback will need to be made to
> the owner (KVM SEV) to transition pages back to hypervisor-owned/shared

I assume you mean, that the mapping is no longer set for the folio (it 
sure still exists, because we are getting a callback from it :) )?

Staring at filemap_remove_folio(), this is exactly what happens:

We remember folio->mapping, call __filemap_remove_folio(), and then call 
filemap_free_folio() where we zap folio->mapping via page_cache_delete().

Maybe it's easier+cleaner to also forward the mapping to the 
free_folio() callback, just like we do with filemap_free_folio()? Would 
that help?

CCing Willy if that would be reasonable extension of the free_folio 
callback.


> 
> .release_folio() and .invalidate_folio() address space ops can serve the

---

## [6] David Hildenbrand — 2024-11-15
*Subject: Re: [PATCH RFC v3 1/2] KVM: guest_memfd: Convert .free_folio() to
 .release_folio()*

On 15.11.24 11:58, David Hildenbrand wrote:
> On 13.11.24 23:34, Elliot Berman wrote:
>> When guest_memfd becomes a library, a callback will need to be made to

Now really CCing him. :)

> 
>>

---

## [7] Elliot Berman — 2024-11-15
*Subject: Re: [PATCH RFC v3 1/2] KVM: guest_memfd: Convert .free_folio() to
 .release_folio()*

On Fri, Nov 15, 2024 at 11:58:59AM +0100, David Hildenbrand wrote:
> On 15.11.24 11:58, David Hildenbrand wrote:
> > On 13.11.24 23:34, Elliot Berman wrote:

I like this approach too. It would avoid the checks we have to do in the
invalidate_folio() callback and is cleaner.

- Elliot

> > > 
> > > .release_folio() and .invalidate_folio() address space ops can serve the

---

## [8] David Hildenbrand — 2024-11-18
*Subject: Re: [PATCH RFC v3 1/2] KVM: guest_memfd: Convert .free_folio() to
 .release_folio()*

On 15.11.24 21:13, Elliot Berman wrote:
> On Fri, Nov 15, 2024 at 11:58:59AM +0100, David Hildenbrand wrote:
>> On 15.11.24 11:58, David Hildenbrand wrote:

It really should be fairly simple


  Documentation/filesystems/locking.rst | 2 +-
  fs/nfs/dir.c                          | 9 +++++----
  fs/orangefs/inode.c                   | 3 ++-
  include/linux/fs.h                    | 2 +-
  mm/filemap.c                          | 2 +-
  mm/secretmem.c                        | 3 ++-
  virt/kvm/guest_memfd.c                | 3 ++-
  7 files changed, 14 insertions(+), 10 deletions(-)

diff --git a/Documentation/filesystems/locking.rst b/Documentation/filesystems/locking.rst
index f5e3676db954b..f1a20ad5edbee 100644
--- a/Documentation/filesystems/locking.rst
+++ b/Documentation/filesystems/locking.rst
@@ -258,7 +258,7 @@ prototypes::
  	sector_t (*bmap)(struct address_space *, sector_t);
  	void (*invalidate_folio) (struct folio *, size_t start, size_t len);
  	bool (*release_folio)(struct folio *, gfp_t);
-	void (*free_folio)(struct folio *);
+	void (*free_folio)(struct address_space *, struct folio *);
  	int (*direct_IO)(struct kiocb *, struct iov_iter *iter);
  	int (*migrate_folio)(struct address_space *, struct folio *dst,
  			struct folio *src, enum migrate_mode);
diff --git a/fs/nfs/dir.c b/fs/nfs/dir.c
index 492cffd9d3d84..f7da6d7496b06 100644
--- a/fs/nfs/dir.c
+++ b/fs/nfs/dir.c
@@ -218,7 +218,8 @@ static void nfs_readdir_folio_init_array(struct folio *folio, u64 last_cookie,
  /*
   * we are freeing strings created by nfs_add_to_readdir_array()
   */
-static void nfs_readdir_clear_array(struct folio *folio)
+static void nfs_readdir_clear_array(struct address_space *mapping,
+		struct folio *folio)
  {
  	struct nfs_cache_array *array;
  	unsigned int i;
@@ -233,7 +234,7 @@ static void nfs_readdir_clear_array(struct folio *folio)
  static void nfs_readdir_folio_reinit_array(struct folio *folio, u64 last_cookie,
  					   u64 change_attr)
  {
-	nfs_readdir_clear_array(folio);
+	nfs_readdir_clear_array(folio->mapping, folio);
  	nfs_readdir_folio_init_array(folio, last_cookie, change_attr);
  }
  
@@ -249,7 +250,7 @@ nfs_readdir_folio_array_alloc(u64 last_cookie, gfp_t gfp_flags)
  static void nfs_readdir_folio_array_free(struct folio *folio)
  {
  	if (folio) {
-		nfs_readdir_clear_array(folio);
+		nfs_readdir_clear_array(folio->mapping, folio);
  		folio_put(folio);
  	}
  }
@@ -391,7 +392,7 @@ static void nfs_readdir_folio_init_and_validate(struct folio *folio, u64 cookie,
  	if (folio_test_uptodate(folio)) {
  		if (nfs_readdir_folio_validate(folio, cookie, change_attr))
  			return;
-		nfs_readdir_clear_array(folio);
+		nfs_readdir_clear_array(folio->mapping, folio);
  	}
  	nfs_readdir_folio_init_array(folio, cookie, change_attr);
  	folio_mark_uptodate(folio);
diff --git a/fs/orangefs/inode.c b/fs/orangefs/inode.c
index aae6d2b8767df..d936694b8e91f 100644
--- a/fs/orangefs/inode.c
+++ b/fs/orangefs/inode.c
@@ -470,7 +470,8 @@ static bool orangefs_release_folio(struct folio *folio, gfp_t foo)
  	return !folio_test_private(folio);
  }
  
-static void orangefs_free_folio(struct folio *folio)
+static void orangefs_free_folio(struct address_space *mapping,
+		struct folio *folio)
  {
  	kfree(folio_detach_private(folio));
  }
diff --git a/include/linux/fs.h b/include/linux/fs.h
index 3559446279c15..4dd4013541c1b 100644
--- a/include/linux/fs.h
+++ b/include/linux/fs.h
@@ -417,7 +417,7 @@ struct address_space_operations {
  	sector_t (*bmap)(struct address_space *, sector_t);
  	void (*invalidate_folio) (struct folio *, size_t offset, size_t len);
  	bool (*release_folio)(struct folio *, gfp_t);
-	void (*free_folio)(struct folio *folio);
+	void (*free_folio)(struct address_space *, struct folio *folio);
  	ssize_t (*direct_IO)(struct kiocb *, struct iov_iter *iter);
  	/*
  	 * migrate the contents of a folio to the specified target. If
diff --git a/mm/filemap.c b/mm/filemap.c
index e582a1545d2ae..86f975ba80746 100644
--- a/mm/filemap.c
+++ b/mm/filemap.c
@@ -239,7 +239,7 @@ void filemap_free_folio(struct address_space *mapping, struct folio *folio)
  
  	free_folio = mapping->a_ops->free_folio;
  	if (free_folio)
-		free_folio(folio);
+		free_folio(mapping, folio);
  
  	if (folio_test_large(folio))
  		refs = folio_nr_pages(folio);
diff --git a/mm/secretmem.c b/mm/secretmem.c
index 399552814fd0f..1d2ed3391734d 100644
--- a/mm/secretmem.c
+++ b/mm/secretmem.c
@@ -152,7 +152,8 @@ static int secretmem_migrate_folio(struct address_space *mapping,
  	return -EBUSY;
  }
  
-static void secretmem_free_folio(struct folio *folio)
+static void secretmem_free_folio(struct address_space *mapping,
+		struct folio *folio)
  {
  	set_direct_map_default_noflush(&folio->page);
  	folio_zero_segment(folio, 0, folio_size(folio));
diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index 8f079a61a56db..573946c4fff51 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -353,7 +353,8 @@ static int kvm_gmem_error_folio(struct address_space *mapping, struct folio *fol
  }
  
  #ifdef CONFIG_HAVE_KVM_ARCH_GMEM_INVALIDATE
-static void kvm_gmem_free_folio(struct folio *folio)
+static void kvm_gmem_free_folio(struct address_space *mapping,
+		struct folio *folio)
  {
  	struct page *page = folio_page(folio, 0);
  	kvm_pfn_t pfn = page_to_pfn(page);

---
