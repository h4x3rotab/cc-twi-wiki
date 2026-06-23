---
title: 'KVM: guest_memfd: folio migration for\n non-confidential VMs'
date: 2026-06-11
last_reply: 2026-06-17
message_count: 13
participants: ['Shivank Garg', 'Alexandru Elisei', 'Sean Christopherson', 'David Hildenbrand (Arm)', 'Ackerley Tng']
---

## [1] Shivank Garg — 2026-06-11

guest_memfd folios are currently marked unmovable, so the kernel cannot
perform NUMA-balancing, memory compaction, etc. This is unavoidable for
confidential VMs (SEV-SNP, TDX), since memory is encrypted and copying it
needs firmware assistance. However, for non-confidential VMs (like
Firecracker), we can migrate the folios.

This series enables folio migration for non-confidential guest_memfd and
also lays the groundwork for migrating confidential guest_memfd later.
Once firmware-assisted copying support is available, those VMs can be
made movable, the confidential folio content can be copied separately,
and the destination folio marked with FOLIO_CONTENT_COPIED so
__migrate_folio() skips the host-side folio_mc_copy().

Testing
-------
Host: 7.1-rc7 + this, 2 NUMA nodes

- KVM selftest: allocate folios on node 0, migrate them to node 1 and
  back and verify resulting NUMA node and the folio contents at each
  step.

- Firecracker [1]: booted a microVM backed by guest_memfd. While the
  guest was running, forced host-side migration of its folios via
  migratepages(8) and explicit move_pages(2) of guest_memfd
  pages. Verify with /proc/firecracker_pid/numa_maps.

[1] https://github.com/firecracker-microvm/firecracker/tree/feature/secret-hiding
    and change builder.rs to remove GUEST_MEMFD_FLAG_NO_DIRECT_MAP from
    vm.create_guest_memfd()

Best regards,
Shivank

Signed-off-by: Shivank Garg <shivankg@amd.com>
---
Shivank Garg (3):
      mm: split AS_UNMOVABLE back out of AS_INACCESSIBLE
      KVM: guest_memfd: support folio migration for non-confidential VMs
      KVM: selftests: exercise guest_memfd folio migration

 include/linux/pagemap.h                        | 24 ++++++--
 mm/compaction.c                                | 12 ++--
 mm/migrate.c                                   |  2 +-
 tools/testing/selftests/kvm/guest_memfd_test.c | 77 ++++++++++++++++++++++++++
 virt/kvm/guest_memfd.c                         | 49 ++++++++++++++--
 5 files changed, 149 insertions(+), 15 deletions(-)
---
base-commit: 4549871118cf616eecdd2d939f78e3b9e1dddc48
change-id: 20260611-shivank-gmem-migrate-8c1c519b30a6

Best regards,

---

## [2] Shivank Garg — 2026-06-11
*Subject: [PATCH RFC 1/3] mm: split AS_UNMOVABLE back out of AS_INACCESSIBLE*

Commit 27e6a24a4cf3 ("mm, virt: merge AS_UNMOVABLE and AS_INACCESSIBLE")
folded the two flags into one, on the grounds that guest_memfd was the
only user and always set both. But the two flags were added for
different reasons and guard different things:

  AS_UNMOVABLE (0003e2a41468) marks a mapping whose folios cannot be
  migrated.

  AS_INACCESSIBLE (c72ceafbd12c) marks a mapping whose contents must
  not be directly R/W accessed. Its only job is to stop
  truncate_inode_partial_folio() from zeroing the folio.

The merge assumed unmovable and inaccessible were the same thing.
This cannot express a mapping that is inaccessible yet still movable,
which is exactly what guest_memfd wants.

Reintroduce AS_UNMOVABLE and restore the original split: truncate keeps
checking AS_INACCESSIBLE, while migration and compaction go back to
checking AS_UNMOVABLE.

Currently guest_memfd sets both, so the resulting flags and behaviour
are unchanged. Preparatory change to support folio migration for
non-confidential guest_memfd VMs.

Signed-off-by: Shivank Garg <shivankg@amd.com>
---
 include/linux/pagemap.h | 24 ++++++++++++++++++++----
 mm/compaction.c         | 12 ++++++------
 mm/migrate.c            |  2 +-
 virt/kvm/guest_memfd.c  |  1 +
 4 files changed, 28 insertions(+), 11 deletions(-)

diff --git a/include/linux/pagemap.h b/include/linux/pagemap.h
index 31a848485ad9d9850d37185418349b89e6efe420..17f5abfa6e7be97c0dcb634346f21ce076798495 100644
--- a/include/linux/pagemap.h
+++ b/include/linux/pagemap.h
@@ -210,6 +210,7 @@ enum mapping_flags {
 	AS_WRITEBACK_MAY_DEADLOCK_ON_RECLAIM = 9,
 	AS_KERNEL_FILE = 10,	/* mapping for a fake kernel file that shouldn't
 				   account usage to user cgroups */
+	AS_UNMOVABLE = 11,	/* The mapping cannot be moved, ever */
 	/* Bits 16-25 are used for FOLIO_ORDER */
 	AS_FOLIO_ORDER_BITS = 5,
 	AS_FOLIO_ORDER_MIN = 16,
@@ -322,11 +323,10 @@ static inline void mapping_clear_stable_writes(struct address_space *mapping)
 static inline void mapping_set_inaccessible(struct address_space *mapping)
 {
 	/*
-	 * It's expected inaccessible mappings are also unevictable. Compaction
-	 * migrate scanner (isolate_migratepages_block()) relies on this to
-	 * reduce page locking.
+	 * The mapping's contents must not be accessed by the CPU through
+	 * the kernel direct map or other internal paths (e.g. zeroing of
+	 * pages during truncation).
 	 */
-	set_bit(AS_UNEVICTABLE, &mapping->flags);
 	set_bit(AS_INACCESSIBLE, &mapping->flags);
 }
 
@@ -335,6 +335,22 @@ static inline bool mapping_inaccessible(const struct address_space *mapping)
 	return test_bit(AS_INACCESSIBLE, &mapping->flags);
 }
 
+static inline void mapping_set_unmovable(struct address_space *mapping)
+{
+	/*
+	 * It's expected unmovable mappings are also unevictable. Compaction
+	 * migrate scanner (isolate_migratepages_block()) relies on this to
+	 * reduce page locking.
+	 */
+	set_bit(AS_UNEVICTABLE, &mapping->flags);
+	set_bit(AS_UNMOVABLE, &mapping->flags);
+}
+
+static inline bool mapping_unmovable(const struct address_space *mapping)
+{
+	return test_bit(AS_UNMOVABLE, &mapping->flags);
+}
+
 static inline void mapping_set_writeback_may_deadlock_on_reclaim(struct address_space *mapping)
 {
 	set_bit(AS_WRITEBACK_MAY_DEADLOCK_ON_RECLAIM, &mapping->flags);
diff --git a/mm/compaction.c b/mm/compaction.c
index 3648ce22c80728b894cffce502d8caa3e4532406..8262f08c01ff407eff8732ffe1d0eb4de469eaf2 100644
--- a/mm/compaction.c
+++ b/mm/compaction.c
@@ -1133,22 +1133,22 @@ isolate_migratepages_block(struct compact_control *cc, unsigned long low_pfn,
 		if (((mode & ISOLATE_ASYNC_MIGRATE) && is_dirty) ||
 		    (mapping && is_unevictable)) {
 			bool migrate_dirty = true;
-			bool is_inaccessible;
+			bool is_unmovable;
 
 			/*
 			 * Only folios without mappings or that have
 			 * a ->migrate_folio callback are possible to migrate
 			 * without blocking.
 			 *
-			 * Folios from inaccessible mappings are not migratable.
+			 * Folios from unmovable mappings are not migratable.
 			 *
 			 * However, we can be racing with truncation, which can
 			 * free the mapping that we need to check. Truncation
 			 * holds the folio lock until after the folio is removed
 			 * from the page so holding it ourselves is sufficient.
 			 *
-			 * To avoid locking the folio just to check inaccessible,
-			 * assume every inaccessible folio is also unevictable,
+			 * To avoid locking the folio just to check unmovable,
+			 * assume every unmovable folio is also unevictable,
 			 * which is a cheaper test.  If our assumption goes
 			 * wrong, it's not a correctness bug, just potentially
 			 * wasted cycles.
@@ -1161,9 +1161,9 @@ isolate_migratepages_block(struct compact_control *cc, unsigned long low_pfn,
 				migrate_dirty = !mapping ||
 						mapping->a_ops->migrate_folio;
 			}
-			is_inaccessible = mapping && mapping_inaccessible(mapping);
+			is_unmovable = mapping && mapping_unmovable(mapping);
 			folio_unlock(folio);
-			if (!migrate_dirty || is_inaccessible)
+			if (!migrate_dirty || is_unmovable)
 				goto isolate_fail_put;
 		}
 
diff --git a/mm/migrate.c b/mm/migrate.c
index 8a64291ab5b44c401e1e0356bf39588e7b5d7b0d..c81b3900b5afd150681d973484e71982a8936221 100644
--- a/mm/migrate.c
+++ b/mm/migrate.c
@@ -1100,7 +1100,7 @@ static int move_to_new_folio(struct folio *dst, struct folio *src,
 
 	if (!mapping)
 		rc = migrate_folio(mapping, dst, src, mode);
-	else if (mapping_inaccessible(mapping))
+	else if (mapping_unmovable(mapping))
 		rc = -EOPNOTSUPP;
 	else if (mapping->a_ops->migrate_folio)
 		/*
diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index 69c9d6d546b287b4f75ef69868259c082ca50933..806a42f0e031a1c7729f53c786316d2502532553 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -592,6 +592,7 @@ static int __kvm_gmem_create(struct kvm *kvm, loff_t size, u64 flags)
 	inode->i_size = size;
 	mapping_set_gfp_mask(inode->i_mapping, GFP_HIGHUSER);
 	mapping_set_inaccessible(inode->i_mapping);
+	mapping_set_unmovable(inode->i_mapping);
 	/* Unmovable mappings are supposed to be marked unevictable as well. */
 	WARN_ON_ONCE(!mapping_unevictable(inode->i_mapping));

---

## [3] Shivank Garg — 2026-06-11
*Subject: [PATCH RFC 2/3] KVM: guest_memfd: support folio migration for
 non-confidential VMs*

guest_memfd folios are currently marked unmmovable, so the kernel
cannot perform NUMA-balancing, memory compaction, etc.
This is unavoidable for confidential VMs (SEV-SNP, TDX),
since memory is encrypted and copying it need firmware assistance.
However, for non-cofidential VMs (like firecracker), we can migrate
the folios.

Mark non-confidential VMs as movable and implement
kvm_gmem_migrate_folio() using filemap_migrate_folio().

This lays the ground work for migrating cofidential guest_memfd
later. Once the firmware-assisted copying support is available,
those VMs can be made movable. The confidential folio content can
be copied separately, and the destination folio can be marked with
FOLIO_CONTENT_COPIED so __migrate_folio() skips the host-side
folio_mc_copy().

Signed-off-by: Shivank Garg <shivankg@amd.com>
---
 virt/kvm/guest_memfd.c | 50 +++++++++++++++++++++++++++++++++++++++++++++-----
 1 file changed, 45 insertions(+), 5 deletions(-)

diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index 806a42f0e031a1c7729f53c786316d2502532553..e4470106fc7792f328bce5275419683328c8b4ab 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -487,13 +487,45 @@ static struct file_operations kvm_gmem_fops = {
 	.fallocate	= kvm_gmem_fallocate,
 };
 
+#ifdef CONFIG_MIGRATION
 static int kvm_gmem_migrate_folio(struct address_space *mapping,
 				  struct folio *dst, struct folio *src,
 				  enum migrate_mode mode)
 {
-	WARN_ON_ONCE(1);
-	return -EINVAL;
+	struct inode *inode = mapping->host;
+	pgoff_t start, end;
+	int ret;
+
+	if (!filemap_invalidate_trylock_shared(mapping))
+		return -EAGAIN;
+
+	start = src->index;
+	end = start + folio_nr_pages(src);
+
+	kvm_gmem_invalidate_begin(inode, start, end);
+
+	/*
+	 * For non-confidential guest_memfd the folio is host-readable,
+	 * so filemap_migrate_folio() can copy the contents itself via
+	 * folio_mc_copy().
+	 *
+	 * This is also the hook point for confidential VMs (SEV-SNP, TDX) once
+	 * they are made movable: the host cannot copy encrypted/private memory,
+	 * so a firmware-assisted copy would run here.
+	 * Idea: https://lore.kernel.org/r/20260428155043.39251-8-shivankg@amd.com
+	 * Mark the @dst->migrate_info field with FOLIO_CONTENT_COPIED, so
+	 * __migrate_folio() skip folio_mc_copy() for confidential VMs.
+	 */
+	ret = filemap_migrate_folio(mapping, dst, src, mode);
+
+	kvm_gmem_invalidate_end(inode, start, end);
+
+	filemap_invalidate_unlock_shared(mapping);
+	return ret;
 }
+#else
+#define kvm_gmem_migrate_folio NULL
+#endif
 
 static int kvm_gmem_error_folio(struct address_space *mapping, struct folio *folio)
 {
@@ -592,9 +624,17 @@ static int __kvm_gmem_create(struct kvm *kvm, loff_t size, u64 flags)
 	inode->i_size = size;
 	mapping_set_gfp_mask(inode->i_mapping, GFP_HIGHUSER);
 	mapping_set_inaccessible(inode->i_mapping);
-	mapping_set_unmovable(inode->i_mapping);
-	/* Unmovable mappings are supposed to be marked unevictable as well. */
-	WARN_ON_ONCE(!mapping_unevictable(inode->i_mapping));
+
+	/*
+	 * Confidential VMs (SEV-SNP, TDX) bind encryption to the physical
+	 * address and require firmware assisted copy, so their folios cannot
+	 * be migrated yet.
+	 */
+	if (kvm_arch_has_private_mem(kvm)) {
+		mapping_set_unmovable(inode->i_mapping);
+		/* Unmovable mappings are supposed to be marked unevictable as well. */
+		WARN_ON_ONCE(!mapping_unevictable(inode->i_mapping));
+	}
 
 	GMEM_I(inode)->flags = flags;

---

## [4] Shivank Garg — 2026-06-11
*Subject: [PATCH RFC 3/3] KVM: selftests: exercise guest_memfd folio
 migration*

Add a migration test to guest_memfd_test, run for the
MMAP | INIT_SHARED configuration on systems with at least two NUMA
nodes (skipped otherwise).

Migrate every folio from node 0 to node 1 with move_pages(2) and
check both the resulting node and the data. Migrate them back and
re-check the data.

Signed-off-by: Shivank Garg <shivankg@amd.com>
---
 tools/testing/selftests/kvm/guest_memfd_test.c | 77 ++++++++++++++++++++++++++
 1 file changed, 77 insertions(+)

diff --git a/tools/testing/selftests/kvm/guest_memfd_test.c b/tools/testing/selftests/kvm/guest_memfd_test.c
index 832ef4dfb99faa4411af847d21eb426c34342434..04931d3add46cb117fe5b093ed48f838cb124542 100644
--- a/tools/testing/selftests/kvm/guest_memfd_test.c
+++ b/tools/testing/selftests/kvm/guest_memfd_test.c
@@ -76,6 +76,82 @@ static void test_mmap_supported(int fd, size_t total_size)
 	kvm_munmap(mem, total_size);
 }
 
+/*
+ * Each page is filled with a distinct byte (its index). Check every byte that
+ * data is intact after migration.
+ */
+static void verify_page(const char *page, int page_idx, size_t size,
+			const char *when)
+{
+	char expected = (char)(page_idx & 0xff);
+	size_t off;
+
+	for (off = 0; off < size; off++)
+		TEST_ASSERT(page[off] == expected,
+			    "Page %d corrupted at offset %zu %s", page_idx, off, when);
+}
+
+static void test_migrate_folio(int fd, size_t total_size)
+{
+	const unsigned long nodemask_0 = 1; /* nid: 0 */
+	unsigned long maxnode = BITS_PER_TYPE(nodemask_0);
+	int page_count = total_size / page_size;
+	void **addr;
+	int *status, *nodes;
+	char *mem;
+	int i;
+
+	if (!is_multi_numa_node_system())
+		return;
+
+	mem = kvm_mmap(total_size, PROT_READ | PROT_WRITE, MAP_SHARED, fd);
+
+	addr = calloc(page_count, sizeof(*addr));
+	status = calloc(page_count, sizeof(*status));
+	nodes = calloc(page_count, sizeof(*nodes));
+	TEST_ASSERT(addr && status && nodes, "Failed to allocate page arrays");
+
+	/* Allocate all folios on node 0 and fill each with a known pattern. */
+	kvm_mbind(mem, total_size, MPOL_BIND, &nodemask_0, maxnode, 0);
+	for (i = 0; i < page_count; i++) {
+		memset(mem + i * page_size, (char)(i & 0xff), page_size);
+		addr[i] = mem + i * page_size;
+	}
+
+	kvm_move_pages(0, page_count, addr, NULL, status, 0);
+	for (i = 0; i < page_count; i++)
+		TEST_ASSERT(status[i] == 0, "Page %d should be on node 0", i);
+
+	/* Migrate node 0 -> 1, then check both the location and the data. */
+	for (i = 0; i < page_count; i++)
+		nodes[i] = 1;
+	kvm_move_pages(0, page_count, addr, nodes, status, MPOL_MF_MOVE);
+
+	kvm_move_pages(0, page_count, addr, NULL, status, 0);
+	for (i = 0; i < page_count; i++)
+		TEST_ASSERT(status[i] == 1,
+			    "Page %d should be on node 1 after migration", i);
+	for (i = 0; i < page_count; i++)
+		verify_page(mem + i * page_size, i, page_size, "after migration");
+
+	/* Migrate back node 1 -> 0, then re-check the location and the data. */
+	for (i = 0; i < page_count; i++)
+		nodes[i] = 0;
+	kvm_move_pages(0, page_count, addr, nodes, status, MPOL_MF_MOVE);
+
+	kvm_move_pages(0, page_count, addr, NULL, status, 0);
+	for (i = 0; i < page_count; i++)
+		TEST_ASSERT(status[i] == 0,
+			    "Page %d should be on node 0 after round-trip", i);
+	for (i = 0; i < page_count; i++)
+		verify_page(mem + i * page_size, i, page_size, "after round-trip");
+
+	free(addr);
+	free(status);
+	free(nodes);
+	kvm_munmap(mem, total_size);
+}
+
 static void test_mbind(int fd, size_t total_size)
 {
 	const unsigned long nodemask_0 = 1; /* nid: 0 */
@@ -434,6 +510,7 @@ static void __test_guest_memfd(struct kvm_vm *vm, u64 flags)
 			gmem_test(fault_overflow, vm, flags);
 			gmem_test(numa_allocation, vm, flags);
 			__gmem_test(collapse, vm, flags, pmd_size);
+			gmem_test(migrate_folio, vm, flags);
 		} else {
 			gmem_test(fault_private, vm, flags);
 		}

---

## [5] Alexandru Elisei — 2026-06-15
*Subject: Re: [PATCH RFC 0/3] KVM: guest_memfd: folio migration for
 non-confidential VMs*

Hi,

On Thu, Jun 11, 2026 at 01:05:07PM +0000, Shivank Garg wrote:
> guest_memfd folios are currently marked unmovable, so the kernel cannot
> perform NUMA-balancing, memory compaction, etc. This is unavoidable for

I always thought that one of the nice things about using guest_memfd as a
memory backend, as opposed to host userspace mappings, is that the host
cannot unmap VM memory because of KSM, automatic NUMA balancing, hugepage
collapse, compaction, etc, acting on the host userspace mapping of the
VM memory, and outside of the VMM's or KVM's control.

I think it would be useful to preserve this behaviour, even in the absence
of confidential VMs (i.e, guest_memfd file descriptor created with
GUEST_MEMFD_FLAG_MMAP).

Thanks,
Alex

> 
> Testing

---

## [6] Alexandru Elisei — 2026-06-15
*Subject: Re: [PATCH RFC 0/3] KVM: guest_memfd: folio migration for
 non-confidential VMs*

Hi,

On Mon, Jun 15, 2026 at 11:43:14AM +0100, Alexandru Elisei wrote:
> Hi,
> 

Just to be clear, I was thinking that it might be useful for both
behaviours to exist (migratable and non-migratable) for non-confidential
VMs, and allow KVM or userspace to decide which they prefer for a
guest_memfd.

Thanks,
Alex

---

## [7] Sean Christopherson — 2026-06-15
*Subject: Re: [PATCH RFC 0/3] KVM: guest_memfd: folio migration for
 non-confidential VMs*

On Mon, Jun 15, 2026, Alexandru Elisei wrote:
> Hi,
> 

+1000.  It's not just "nice to have", it's a core design principle of guest_memfd.

> > I think it would be useful to preserve this behaviour, even in the absence
> > of confidential VMs (i.e, guest_memfd file descriptor created with

For the purposes of this discussion, we should separate the physical act of
migrating pages from the features that trigger migration.  As I said in last week's
guest-memfd call, I am a-ok with supporting page migration as a mechanism, but I
am dead set against supporting NUMA balancing, KSM, LRU-based swap/reclaim, and
anything else that goes against the goal of guest-first memory.

If userspace wants mm/ functionality, then use anon, memfd, hugetlb, shmem, etc.

Shivank, what's the immediate motivation for this series?

---

## [8] David Hildenbrand (Arm) — 2026-06-15
*Subject: Re: [PATCH RFC 0/3] KVM: guest_memfd: folio migration for
 non-confidential VMs*

On 6/15/26 19:39, Sean Christopherson wrote:
> On Mon, Jun 15, 2026, Alexandru Elisei wrote:
>> Hi,

Right, and I raised in the guest_memfd call also the rough idea of Alexandru's
use case of having non-movable guest_memfd pages such that we can support use
cases where we can hopefully guarantee that a stage-2 mapping will not just
randomly go away.

> 
>>> I think it would be useful to preserve this behaviour, even in the absence

Right. Page migration for supporting ZONE_MOVABLE/CMA, compaction, memory
offlining, virtio-mem and possibly some collapse mechanism if we were to support
THP of some sorts in guest_memfd would are all reasonable.

As soon as we mix in access/lru semantics, we're going into the wrong direction.

Fortunately KSM is anon-only and not even worth a rant here :)

---

## [9] David Hildenbrand (Arm) — 2026-06-15
*Subject: Re: [PATCH RFC 0/3] KVM: guest_memfd: folio migration for
 non-confidential VMs*

On 6/15/26 12:43, Alexandru Elisei wrote:
> Hi,
> 

Yeah, but it doesn't play nice with THPs / large folios. So if you want to run
something else on a hypervisor than just confidential VMs, you definitely want
guest_memfd to be as nice to the system.

That is, support page migration if nothing speaks against it.

Now, if something speaks against it, for sure we can just leave the pages be
unmovable.

Fortunately, the patch is rather trivial.

---

## [10] David Hildenbrand (Arm) — 2026-06-15
*Subject: Re: [PATCH RFC 2/3] KVM: guest_memfd: support folio migration for
 non-confidential VMs*

On 6/11/26 15:05, Shivank Garg wrote:
> guest_memfd folios are currently marked unmmovable, so the kernel
> cannot perform NUMA-balancing, memory compaction, etc.

We would still want our movable mappings to be flagged unevictable.

> +	}
>

As discussed, for guest_memfd instances that support page migration, we would
want to also allocate the pages in for guest_memfd as GFP_HIGHUSER_MOVABLE.

That is, handle the mapping_set_gfp_mask() call as well.

It will unlock access to areas reserved for movable allocations (CMA/
ZONE_MOVABLE) and properly let the page allocator group pages by mobility
(MOVABLE vs. UNMOVABLE vs. RECLAIMABLE).

---

## [11] Ackerley Tng — 2026-06-16
*Subject: Re: [PATCH RFC 0/3] KVM: guest_memfd: folio migration for
 non-confidential VMs*

"David Hildenbrand (Arm)" <david@kernel.org> writes:

> On 6/15/26 19:39, Sean Christopherson wrote:
>> On Mon, Jun 15, 2026, Alexandru Elisei wrote:

More concretely, are y'all pointing towards a
GUEST_MEMFD_FLAG_MIGRATABLE, which will set .migrate =
kvm_gmem_migrate_folio, and for now, error out for CoCo VMs?

>>
>> For the purposes of this discussion, we should separate the physical act of

Background question: how would virtio-mem use migration in the host/guest_memfd?

> As soon as we mix in access/lru semantics, we're going into the wrong direction.
>

---

## [12] Garg, Shivank — 2026-06-17
*Subject: Re: [PATCH RFC 0/3] KVM: guest_memfd: folio migration for
 non-confidential VMs*

On 6/15/2026 11:09 PM, Sean Christopherson wrote:
> On Mon, Jun 15, 2026, Alexandru Elisei wrote:
>> Hi,

Hi Sean,
This makes sense!

Tbh, my main motivation was to start a dialogue on this, since the
implementation+testing itself was easy.

Compaction and memory failure handling were the cases I initially
had in mind. And as David noted, ZONE_MOVABLE/CMA, compaction, memory
offlining, virtio-mem cases would be useful too.

I fully agree that NUMA balancing, LRU/reclaim and etc. features
should stay out, and keeping the migration as mechanism only for
guest_memfd.

Thanks,
Shivank

---

## [13] David Hildenbrand (Arm) — 2026-06-17
*Subject: Re: [PATCH RFC 0/3] KVM: guest_memfd: folio migration for
 non-confidential VMs*

On 6/16/26 20:09, Ackerley Tng wrote:
> "David Hildenbrand (Arm)" <david@kernel.org> writes:
> 

Good question! As long as there is no nested-virt support (and virtio-mem
support for coco still being in the making) that wouldn't apply, only ordinary
memory hot(un)plug (incl CXL).

---
