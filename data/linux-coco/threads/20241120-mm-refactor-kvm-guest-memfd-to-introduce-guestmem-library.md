---
title: 'mm: Refactor KVM guest_memfd to introduce guestmem\n library'
date: 2024-11-20
last_reply: 2024-11-22
message_count: 7
participants: ['Elliot Berman', 'David Hildenbrand', 'Mike Day']
---

## [1] Elliot Berman — 2024-11-20

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

Changes in v4:
- Update folio_free() to add address_space mapping instead of
  invalidate_folio/free_folio path.
- Link to v3: https://lore.kernel.org/r/20241113-guestmem-library-v3-0-71fdee85676b@quicinc.com

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
      filemap: Pass address_space mapping to ->free_folio()
      mm: guestmem: Convert address_space operations to guestmem library

 Documentation/filesystems/locking.rst |   2 +-
 MAINTAINERS                           |   2 +
 fs/nfs/dir.c                          |  11 +-
 fs/orangefs/inode.c                   |   3 +-
 include/linux/fs.h                    |   2 +-
 include/linux/guestmem.h              |  33 ++++++
 mm/Kconfig                            |   3 +
 mm/Makefile                           |   1 +
 mm/filemap.c                          |   9 +-
 mm/guestmem.c                         | 196 ++++++++++++++++++++++++++++++++++
 mm/secretmem.c                        |   3 +-
 mm/vmscan.c                           |   4 +-
 virt/kvm/Kconfig                      |   1 +
 virt/kvm/guest_memfd.c                |  97 +++++------------
 14 files changed, 283 insertions(+), 84 deletions(-)
---
base-commit: 5cb1659f412041e4780f2e8ee49b2e03728a2ba6
change-id: 20241112-guestmem-library-68363cb29186

Best regards,

---

## [2] Elliot Berman — 2024-11-20
*Subject: [PATCH v4 1/2] filemap: Pass address_space mapping to
 ->free_folio()*

When guest_memfd becomes a library, a callback will need to be made to
the owner (KVM SEV) to update the RMP entry for the page back to shared
state. This is currently being done as part of .free_folio() operation,
but this callback shouldn't assume that folio->mapping is set/valid.

The mapping is well-known to callers of .free_folio(), so pass that
mapping so the callback can access the mapping's private data.

Link: https://lore.kernel.org/all/15f665b4-2d33-41ca-ac50-fafe24ade32f@redhat.com/
Suggested-by: David Hildenbrand <david@redhat.com>
Signed-off-by: Elliot Berman <quic_eberman@quicinc.com>
---
 Documentation/filesystems/locking.rst |  2 +-
 fs/nfs/dir.c                          | 11 ++++++-----
 fs/orangefs/inode.c                   |  3 ++-
 include/linux/fs.h                    |  2 +-
 mm/filemap.c                          |  9 +++++----
 mm/secretmem.c                        |  3 ++-
 mm/vmscan.c                           |  4 ++--
 virt/kvm/guest_memfd.c                |  3 ++-
 8 files changed, 21 insertions(+), 16 deletions(-)

diff --git a/Documentation/filesystems/locking.rst b/Documentation/filesystems/locking.rst
index f5e3676db954b5bce4c23a0bf723a79d66181fcd..f1a20ad5edbee70c1a3c8d8a9bfc0f008a68985b 100644
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
index 492cffd9d3d845723b5f3d0eea3874b1f1773fe1..54e7069013ef2a63db24491fa65059e5ad68057a 100644
--- a/fs/nfs/dir.c
+++ b/fs/nfs/dir.c
@@ -55,7 +55,7 @@ static int nfs_closedir(struct inode *, struct file *);
 static int nfs_readdir(struct file *, struct dir_context *);
 static int nfs_fsync_dir(struct file *, loff_t, loff_t, int);
 static loff_t nfs_llseek_dir(struct file *, loff_t, int);
-static void nfs_readdir_clear_array(struct folio *);
+static void nfs_readdir_clear_array(struct address_space *, struct folio *);
 static int nfs_do_create(struct inode *dir, struct dentry *dentry,
 			 umode_t mode, int open_flags);
 
@@ -218,7 +218,8 @@ static void nfs_readdir_folio_init_array(struct folio *folio, u64 last_cookie,
 /*
  * we are freeing strings created by nfs_add_to_readdir_array()
  */
-static void nfs_readdir_clear_array(struct folio *folio)
+static void nfs_readdir_clear_array(struct address_space *mapping,
+				    struct folio *folio)
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
index aae6d2b8767df04714647db5fe1e5ce54c092fce..2d554102ba9ac83acd2b637d4568090717e87f94 100644
--- a/fs/orangefs/inode.c
+++ b/fs/orangefs/inode.c
@@ -470,7 +470,8 @@ static bool orangefs_release_folio(struct folio *folio, gfp_t foo)
 	return !folio_test_private(folio);
 }
 
-static void orangefs_free_folio(struct folio *folio)
+static void orangefs_free_folio(struct address_space *mapping,
+				struct folio *folio)
 {
 	kfree(folio_detach_private(folio));
 }
diff --git a/include/linux/fs.h b/include/linux/fs.h
index e3c603d01337650d562405500013f5c4cfed8eb6..6e5b5cc99750a685b217cb8273c38e7f6bf5ae86 100644
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
index 36d22968be9a1e10da42927dd627d3f22c3a747b..2c8d92dd9d5dd433acbf1b87156eb2e68337332d 100644
--- a/mm/filemap.c
+++ b/mm/filemap.c
@@ -235,12 +235,12 @@ void __filemap_remove_folio(struct folio *folio, void *shadow)
 
 void filemap_free_folio(struct address_space *mapping, struct folio *folio)
 {
-	void (*free_folio)(struct folio *);
+	void (*free_folio)(struct address_space *, struct folio *);
 	int refs = 1;
 
 	free_folio = mapping->a_ops->free_folio;
 	if (free_folio)
-		free_folio(folio);
+		free_folio(mapping, folio);
 
 	if (folio_test_large(folio))
 		refs = folio_nr_pages(folio);
@@ -814,7 +814,8 @@ EXPORT_SYMBOL(file_write_and_wait_range);
 void replace_page_cache_folio(struct folio *old, struct folio *new)
 {
 	struct address_space *mapping = old->mapping;
-	void (*free_folio)(struct folio *) = mapping->a_ops->free_folio;
+	void (*free_folio)(struct address_space *, struct folio *) =
+		mapping->a_ops->free_folio;
 	pgoff_t offset = old->index;
 	XA_STATE(xas, &mapping->i_pages, offset);
 
@@ -843,7 +844,7 @@ void replace_page_cache_folio(struct folio *old, struct folio *new)
 		__lruvec_stat_add_folio(new, NR_SHMEM);
 	xas_unlock_irq(&xas);
 	if (free_folio)
-		free_folio(old);
+		free_folio(mapping, old);
 	folio_put(old);
 }
 EXPORT_SYMBOL_GPL(replace_page_cache_folio);
diff --git a/mm/secretmem.c b/mm/secretmem.c
index 3afb5ad701e14ad87b6e5173b2974f1309399b8e..8643d073b8f3554a18d419353fa604864de224c1 100644
--- a/mm/secretmem.c
+++ b/mm/secretmem.c
@@ -152,7 +152,8 @@ static int secretmem_migrate_folio(struct address_space *mapping,
 	return -EBUSY;
 }
 
-static void secretmem_free_folio(struct folio *folio)
+static void secretmem_free_folio(struct address_space *mapping,
+				 struct folio *folio)
 {
 	set_direct_map_default_noflush(&folio->page);
 	folio_zero_segment(folio, 0, folio_size(folio));
diff --git a/mm/vmscan.c b/mm/vmscan.c
index 749cdc110c745944cd455ae9c5a4c373f631341d..419dc63de05095be298fee724891f0665a397a7b 100644
--- a/mm/vmscan.c
+++ b/mm/vmscan.c
@@ -765,7 +765,7 @@ static int __remove_mapping(struct address_space *mapping, struct folio *folio,
 		xa_unlock_irq(&mapping->i_pages);
 		put_swap_folio(folio, swap);
 	} else {
-		void (*free_folio)(struct folio *);
+		void (*free_folio)(struct address_space *, struct folio *);
 
 		free_folio = mapping->a_ops->free_folio;
 		/*
@@ -794,7 +794,7 @@ static int __remove_mapping(struct address_space *mapping, struct folio *folio,
 		spin_unlock(&mapping->host->i_lock);
 
 		if (free_folio)
-			free_folio(folio);
+			free_folio(mapping, folio);
 	}
 
 	return 1;
diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index 47a9f68f7b247f4cba0c958b4c7cd9458e7c46b4..24dcbad0cb76e353509cf4718837a1999f093414 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -358,7 +358,8 @@ static int kvm_gmem_error_folio(struct address_space *mapping, struct folio *fol
 }
 
 #ifdef CONFIG_HAVE_KVM_ARCH_GMEM_INVALIDATE
-static void kvm_gmem_free_folio(struct folio *folio)
+static void kvm_gmem_free_folio(struct address_space *mapping,
+				struct folio *folio)
 {
 	struct page *page = folio_page(folio, 0);
 	kvm_pfn_t pfn = page_to_pfn(page);

---

## [3] Elliot Berman — 2024-11-20
*Subject: [PATCH v4 2/2] mm: guestmem: Convert address_space operations to
 guestmem library*

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
 include/linux/guestmem.h |  33 ++++++++
 mm/Kconfig               |   3 +
 mm/Makefile              |   1 +
 mm/guestmem.c            | 196 +++++++++++++++++++++++++++++++++++++++++++++++
 virt/kvm/Kconfig         |   1 +
 virt/kvm/guest_memfd.c   |  98 +++++++-----------------
 7 files changed, 264 insertions(+), 70 deletions(-)

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
index 0000000000000000000000000000000000000000..19dd7e5d498f07577ec5cec5b52055f7435980f4
--- /dev/null
+++ b/mm/guestmem.c
@@ -0,0 +1,196 @@
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
+	struct address_space *mapping = folio->mapping;
+
+	return mapping->i_private_data;
+}
+
+static inline bool __guestmem_release_folio(struct address_space *mapping,
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
+static void guestmem_free_folio(struct address_space *mapping,
+				struct folio *folio)
+{
+	WARN_ON_ONCE(!__guestmem_release_folio(mapping, folio));
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
+	.free_folio = guestmem_free_folio,
+	.error_remove_folio = guestmem_error_folio,
+	.migrate_folio = guestmem_migrate_folio,
+};
+
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
+struct folio *guestmem_grab_folio(struct address_space *mapping, pgoff_t index)
+{
+	/* TODO: Support huge pages. */
+	return filemap_grab_folio(mapping, index);
+}
+EXPORT_SYMBOL_GPL(guestmem_grab_folio);
+
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
index 24dcbad0cb76e353509cf4718837a1999f093414..edf57d5662cb8634bbd9ca3118b293c4f7ca229a 100644
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
 
@@ -318,63 +297,42 @@ void kvm_gmem_init(struct module *module)
 	kvm_gmem_fops.owner = module;
 }
 
-static int kvm_gmem_migrate_folio(struct address_space *mapping,
-				  struct folio *dst, struct folio *src,
-				  enum migrate_mode mode)
+static int kvm_guestmem_invalidate_begin(struct list_head *entry, pgoff_t start,
+					 pgoff_t end)
 {
-	WARN_ON_ONCE(1);
-	return -EINVAL;
-}
+	struct kvm_gmem *gmem = container_of(entry, struct kvm_gmem, entry);
 
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
+	kvm_gmem_invalidate_begin(gmem, start, end);
 
-	list_for_each_entry(gmem, gmem_list, entry)
-		kvm_gmem_invalidate_end(gmem, start, end);
+	return 0;
+}
 
-	filemap_invalidate_unlock_shared(mapping);
+static void kvm_guestmem_invalidate_end(struct list_head *entry, pgoff_t start,
+					pgoff_t end)
+{
+	struct kvm_gmem *gmem = container_of(entry, struct kvm_gmem, entry);
 
-	return MF_DELAYED;
+	kvm_gmem_invalidate_end(gmem, start, end);
 }
 
 #ifdef CONFIG_HAVE_KVM_ARCH_GMEM_INVALIDATE
-static void kvm_gmem_free_folio(struct address_space *mapping,
-				struct folio *folio)
+static bool kvm_gmem_release_folio(struct list_head *entry, struct folio *folio)
 {
 	struct page *page = folio_page(folio, 0);
 	kvm_pfn_t pfn = page_to_pfn(page);
 	int order = folio_order(folio);
 
 	kvm_arch_gmem_invalidate(pfn, pfn + (1ul << order));
+
+	return true;
 }
 #endif
 
-static const struct address_space_operations kvm_gmem_aops = {
-	.dirty_folio = noop_dirty_folio,
-	.migrate_folio	= kvm_gmem_migrate_folio,
-	.error_remove_folio = kvm_gmem_error_folio,
+static const struct guestmem_ops kvm_guestmem_ops = {
+	.invalidate_begin = kvm_guestmem_invalidate_begin,
+	.invalidate_end = kvm_guestmem_invalidate_end,
 #ifdef CONFIG_HAVE_KVM_ARCH_GMEM_INVALIDATE
-	.free_folio = kvm_gmem_free_folio,
+	.release_folio = kvm_gmem_release_folio,
 #endif
 };
 
@@ -430,22 +388,22 @@ static int __kvm_gmem_create(struct kvm *kvm, loff_t size, u64 flags)
 
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

## [4] David Hildenbrand — 2024-11-21
*Subject: Re: [PATCH v4 1/2] filemap: Pass address_space mapping to
 ->free_folio()*

On 20.11.24 19:12, Elliot Berman wrote:
> When guest_memfd becomes a library, a callback will need to be made to
> the owner (KVM SEV) to update the RMP entry for the page back to shared

In the mm world, we're nowadays indenting the second parameter line with 
two tabs. Makes it easier to rename the function without having to 
adjust many lines, and requires less lines in general.

Not sure about rules for FSes (personally, I just do it everywhere like 
this now :) ).

Acked-by: David Hildenbrand <david@redhat.com>

---

## [5] Elliot Berman — 2024-11-21
*Subject: Re: [PATCH v4 2/2] mm: guestmem: Convert address_space operations to
 guestmem library*

On Wed, Nov 20, 2024 at 10:12:08AM -0800, Elliot Berman wrote:
> diff --git a/mm/guestmem.c b/mm/guestmem.c
> new file mode 100644

Mike was helping me test this out for SEV-SNP. They helped find a bug
here. Right now, when the file closes, KVM calls
guestmem_detach_mapping() which will uninstall the ops. When that
happens, it's not necessary that all of the folios aren't removed from
the filemap yet and so our free_folio() callback isn't invoked. This
means that we skip updating the RMP entry back to shared/KVM-owned.

There are a few approaches I could take:

1. Create a guestmem superblock so I can register guestmem-specific
   destroy_inode() to do the kfree() above. This requires a lot of
   boilerplate code, and I think it's not preferred approach.
2. Update how KVM tracks the memory so it is back in "shared" state when
   the file closes. This requires some significant rework about the page
   state compared to current guest_memfd. That rework might be useful
   for the shared/private state machine.
3. Call truncate_inode_pages(mapping, 0) to force pages to be freed
   here. It's might be possible that a page is allocated after this
   point. In order for that to be a problem, KVM would need to update
   RMP entry as guest-owned, and I don't believe that's possible after
   the last guestmem_detach_mapping().

My preference is to go with #3 as it was the most easy thing to do.

> +		mapping->i_private_data = NULL;
> +		mapping->a_ops = &empty_aops;

---

## [6] Mike Day — 2024-11-21
*Subject: Re: [PATCH v4 2/2] mm: guestmem: Convert address_space operations to
 guestmem library*

On 11/21/24 10:43, Elliot Berman wrote:
> On Wed, Nov 20, 2024 at 10:12:08AM -0800, Elliot Berman wrote:
>> diff --git a/mm/guestmem.c b/mm/guestmem.c

#3 is my preference as well. The semantics are that the guest is "closing" the gmem
object, which means all the memory is being released from the guest.

Mike
> 
>> +		mapping->i_private_data = NULL;

---

## [7] David Hildenbrand — 2024-11-22
*Subject: Re: [PATCH v4 2/2] mm: guestmem: Convert address_space operations to
 guestmem library*

On 21.11.24 18:40, Mike Day wrote:
> 
> 

Yes, that's the real issue. There either must be some lifetime tracking 
(kfree() after the mapping is completely unused), or you have to tear it 
all down before you mess with the mapping.

>>
>> There are a few approaches I could take:

Agreed.

---
