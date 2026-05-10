---
title: '[RFC PATCH 0/4] SEV-SNP Unaccepted Memory Hotplug'
date: 2025-11-25
last_reply: 2025-12-11
message_count: 40
participants: ['Pratik R. Sampat', 'Kiryl Shutsemau', 'Borislav Petkov', 'David Hildenbrand (Red Hat)', 'Rik van Riel']
---

## [1] Pratik R. Sampat — 2025-11-25

Guest memory hot-plug/remove via the QEMU monitor is used by virtual
machines to dynamically scale the memory capacity of a system with
virtually zero downtime to the guest. For confidential VMs, memory has
to be first accepted before it can be used.

The unaccepted memory feature provides a mechanism to accept memory
either up-front or right before it is needed. The unaccepted table that
tracks this information is allocated and memory block reserved at boot
time. For memory hotplug, this means the table cannot be updated to
track additional regions and accept them as the guest physical memory
grows.

This proof-of-concept series extends the unaccepted memory
infrastructure to support memory hotplug and hot-unplug on the SNP
platform. On a high-level, it does so by decoupling the memory bitmap
from the unaccepted table so that kernel can manage bitmap when memory
is added. For hot-remove, it reverts the page states so that the
hypervisor can reuse that memory. Hot-remove also presents a unique
scenario where the memory we attempt to share can already be in a shared
state set externally which can cause pvalidation on the platform to fail
since no updates were made to the validated bit. Handle this case by
tracking the state of hotplugged memory within the guest and disallow
pvalidate operations on the same state.

Usage (for SNP guests)
----------------------
Step1: Spawn a QEMU SNP guest with the additional parameter of slots and
maximum possible memory, along with the initial memory as below:
"-m X,slots=Y,maxmem=Z".

Use the "accept_memory=[eager|lazy]" kernel command-line parameter to
specify whether hotplugged memory should be accepted immediately upon
addition or only when first accessed. By default, lazy acceptance is
used.

Step2: Once the guest is booted, launch the qemu monitor and hotplug
the memory as follows:
(qemu) object_add memory-backend-memfd,id=mem1,size=1G
(qemu) device_add pc-dimm,id=dimm1,memdev=mem1

Step3: If using auto-onlining by either:
    a) echo online > /sys/devices/system/memory/auto_online_blocks, OR
    b) enable CONFIG_MHP_DEFAULT_ONLINE_TYPE_* while compiling kernel
Memory should show up automatically.

Otherwise, memory can also be onlined by echoing 1 to the newly added
blocks in: /sys/devices/system/memory/memoryXX/online

Step4: If accept_memory is set to eager, all memory is accepted
immediately. Otherwise, memory is accepted on access. For the latter,
acceptance can be triggered by simply running a program such as
stress-ng that requests enough memory to cover the newly allocated
hotplugged regions.

$ stress-ng --vm 1 --vm-bytes={X}G -t {T}s

Step5: memory can be hot-removed using the qemu monitor using:
(qemu) device_remove dimm1
(qemu) object_remove mem1

Tip: Enable the kvm_convert_memory event in QEMU to observe memory
conversions between private and shared during hotplug/remove.

The series is based on
        git.kernel.org/pub/scm/virt/kvm/kvm.git next

Comments and feedback appreciated!

Pratik R. Sampat (4):
  efi/libstub: Decouple memory bitmap from the unaccepted table
  mm: Add support for unaccepted memory hotplug
  x86/sev: Introduce hotplug-aware SNP page state validation
  mm: Add support for unaccepted memory hot-remove

 arch/x86/boot/compressed/efi.h                |   3 +-
 arch/x86/coco/sev/core.c                      | 127 +++++++++++++++-
 arch/x86/include/asm/sev.h                    |  34 +++++
 arch/x86/include/asm/unaccepted_memory.h      |  31 ++++
 .../firmware/efi/libstub/unaccepted_memory.c  |  12 +-
 drivers/firmware/efi/unaccepted_memory.c      | 139 +++++++++++++++++-
 include/linux/efi.h                           |   3 +-
 include/linux/mm.h                            |  18 +++
 mm/memory_hotplug.c                           |   9 ++
 mm/page_alloc.c                               |   2 +
 10 files changed, 363 insertions(+), 15 deletions(-)

---

## [2] Pratik R. Sampat — 2025-11-25
*Subject: [RFC PATCH 1/4] efi/libstub: Decouple memory bitmap from the unaccepted table*

Memory hotplug in secure environments requires the unaccepted memory
bitmap to grow as new memory is added. Currently, the bitmap is
implemented as a flexible array member at the end of struct
efi_unaccepted_memory, which is reserved by memblock at boot and cannot
be resized without reallocating the entire structure.

Replace the flexible array member with a pointer. This allows the bitmap
to be allocated and managed independently from the unaccepted memory
table, enabling dynamic growth to support memory hotplug.

Signed-off-by: Pratik R. Sampat <prsampat@amd.com>
---
 arch/x86/boot/compressed/efi.h                |  2 +-
 arch/x86/include/asm/unaccepted_memory.h      |  9 +++++++++
 .../firmware/efi/libstub/unaccepted_memory.c  | 11 ++++++++++-
 drivers/firmware/efi/unaccepted_memory.c      | 19 ++++++++++++++-----
 include/linux/efi.h                           |  2 +-
 5 files changed, 35 insertions(+), 8 deletions(-)

diff --git a/arch/x86/boot/compressed/efi.h b/arch/x86/boot/compressed/efi.h
index b22300970f97..4f7027f33def 100644
--- a/arch/x86/boot/compressed/efi.h
+++ b/arch/x86/boot/compressed/efi.h
@@ -102,7 +102,7 @@ struct efi_unaccepted_memory {
 	u32 unit_size;
 	u64 phys_base;
 	u64 size;
-	unsigned long bitmap[];
+	unsigned long *bitmap;
 };
 
 static inline int efi_guidcmp (efi_guid_t left, efi_guid_t right)
diff --git a/arch/x86/include/asm/unaccepted_memory.h b/arch/x86/include/asm/unaccepted_memory.h
index f5937e9866ac..5da80e68d718 100644
--- a/arch/x86/include/asm/unaccepted_memory.h
+++ b/arch/x86/include/asm/unaccepted_memory.h
@@ -24,4 +24,13 @@ static inline struct efi_unaccepted_memory *efi_get_unaccepted_table(void)
 		return NULL;
 	return __va(efi.unaccepted);
 }
+
+static inline unsigned long *efi_get_unaccepted_bitmap(void)
+{
+	struct efi_unaccepted_memory *unaccepted = efi_get_unaccepted_table();
+
+	if (!unaccepted)
+		return NULL;
+	return __va(unaccepted->bitmap);
+}
 #endif
diff --git a/drivers/firmware/efi/libstub/unaccepted_memory.c b/drivers/firmware/efi/libstub/unaccepted_memory.c
index 757dbe734a47..c1370fc14555 100644
--- a/drivers/firmware/efi/libstub/unaccepted_memory.c
+++ b/drivers/firmware/efi/libstub/unaccepted_memory.c
@@ -63,13 +63,22 @@ efi_status_t allocate_unaccepted_bitmap(__u32 nr_desc,
 				   EFI_UNACCEPTED_UNIT_SIZE * BITS_PER_BYTE);
 
 	status = efi_bs_call(allocate_pool, EFI_ACPI_RECLAIM_MEMORY,
-			     sizeof(*unaccepted_table) + bitmap_size,
+			     sizeof(*unaccepted_table),
 			     (void **)&unaccepted_table);
 	if (status != EFI_SUCCESS) {
 		efi_err("Failed to allocate unaccepted memory config table\n");
 		return status;
 	}
 
+	status = efi_bs_call(allocate_pool, EFI_ACPI_RECLAIM_MEMORY,
+			     bitmap_size,
+			     (void **)&unaccepted_table->bitmap);
+	if (status != EFI_SUCCESS) {
+		efi_bs_call(free_pool, unaccepted_table);
+		efi_err("Failed to allocate unaccepted memory bitmap\n");
+		return status;
+	}
+
 	unaccepted_table->version = 1;
 	unaccepted_table->unit_size = EFI_UNACCEPTED_UNIT_SIZE;
 	unaccepted_table->phys_base = unaccepted_start;
diff --git a/drivers/firmware/efi/unaccepted_memory.c b/drivers/firmware/efi/unaccepted_memory.c
index c2c067eff634..4479aad258f8 100644
--- a/drivers/firmware/efi/unaccepted_memory.c
+++ b/drivers/firmware/efi/unaccepted_memory.c
@@ -36,7 +36,7 @@ void accept_memory(phys_addr_t start, unsigned long size)
 	unsigned long range_start, range_end;
 	struct accept_range range, *entry;
 	phys_addr_t end = start + size;
-	unsigned long flags;
+	unsigned long flags, *bitmap;
 	u64 unit_size;
 
 	unaccepted = efi_get_unaccepted_table();
@@ -124,8 +124,12 @@ void accept_memory(phys_addr_t start, unsigned long size)
 	list_add(&range.list, &accepting_list);
 
 	range_start = range.start;
-	for_each_set_bitrange_from(range_start, range_end, unaccepted->bitmap,
-				   range.end) {
+
+	bitmap = efi_get_unaccepted_bitmap();
+	if (!bitmap)
+		return;
+
+	for_each_set_bitrange_from(range_start, range_end, bitmap, range.end) {
 		unsigned long phys_start, phys_end;
 		unsigned long len = range_end - range_start;
 
@@ -147,7 +151,7 @@ void accept_memory(phys_addr_t start, unsigned long size)
 		arch_accept_memory(phys_start, phys_end);
 
 		spin_lock(&unaccepted_memory_lock);
-		bitmap_clear(unaccepted->bitmap, range_start, len);
+		bitmap_clear(bitmap, range_start, len);
 	}
 
 	list_del(&range.list);
@@ -197,7 +201,12 @@ bool range_contains_unaccepted_memory(phys_addr_t start, unsigned long size)
 
 	spin_lock_irqsave(&unaccepted_memory_lock, flags);
 	while (start < end) {
-		if (test_bit(start / unit_size, unaccepted->bitmap)) {
+		unsigned long *bitmap = efi_get_unaccepted_bitmap();
+
+		if (!bitmap)
+			break;
+
+		if (test_bit(start / unit_size, bitmap)) {
 			ret = true;
 			break;
 		}
diff --git a/include/linux/efi.h b/include/linux/efi.h
index a98cc39e7aaa..a74b393c54d8 100644
--- a/include/linux/efi.h
+++ b/include/linux/efi.h
@@ -545,7 +545,7 @@ struct efi_unaccepted_memory {
 	u32 unit_size;
 	u64 phys_base;
 	u64 size;
-	unsigned long bitmap[];
+	unsigned long *bitmap;
 };
 
 /*

---

## [3] Pratik R. Sampat — 2025-11-25
*Subject: [RFC PATCH 2/4] mm: Add support for unaccepted memory hotplug*

The unaccepted memory structure currently only supports accepting memory
present at boot time. The unaccepted table uses a fixed-size bitmap
reserved in memblock based on the initial memory layout, preventing
dynamic addition of memory ranges after boot. This causes guest
termination when memory is hot-added in a secure virtual machine due to
accessing pages that have not transitioned to private before use.

Extend the unaccepted memory framework to handle hotplugged memory by
dynamically managing the unaccepted bitmap. Allocate a new bitmap when
hotplugged ranges exceed the reserved bitmap capacity and switch to
kernel-managed allocation.

Hotplugged memory also follows the same acceptance policy using the
accept_memory=[eager|lazy] kernel parameter to accept memory either
up-front when added or before first use.

Signed-off-by: Pratik R. Sampat <prsampat@amd.com>
---
 arch/x86/boot/compressed/efi.h                |  1 +
 .../firmware/efi/libstub/unaccepted_memory.c  |  1 +
 drivers/firmware/efi/unaccepted_memory.c      | 83 +++++++++++++++++++
 include/linux/efi.h                           |  1 +
 include/linux/mm.h                            | 11 +++
 mm/memory_hotplug.c                           |  7 ++
 mm/page_alloc.c                               |  2 +
 7 files changed, 106 insertions(+)

diff --git a/arch/x86/boot/compressed/efi.h b/arch/x86/boot/compressed/efi.h
index 4f7027f33def..a220a1966cae 100644
--- a/arch/x86/boot/compressed/efi.h
+++ b/arch/x86/boot/compressed/efi.h
@@ -102,6 +102,7 @@ struct efi_unaccepted_memory {
 	u32 unit_size;
 	u64 phys_base;
 	u64 size;
+	bool mem_reserved;
 	unsigned long *bitmap;
 };
 
diff --git a/drivers/firmware/efi/libstub/unaccepted_memory.c b/drivers/firmware/efi/libstub/unaccepted_memory.c
index c1370fc14555..b16bd61c12bf 100644
--- a/drivers/firmware/efi/libstub/unaccepted_memory.c
+++ b/drivers/firmware/efi/libstub/unaccepted_memory.c
@@ -83,6 +83,7 @@ efi_status_t allocate_unaccepted_bitmap(__u32 nr_desc,
 	unaccepted_table->unit_size = EFI_UNACCEPTED_UNIT_SIZE;
 	unaccepted_table->phys_base = unaccepted_start;
 	unaccepted_table->size = bitmap_size;
+	unaccepted_table->mem_reserved = true;
 	memset(unaccepted_table->bitmap, 0, bitmap_size);
 
 	status = efi_bs_call(install_configuration_table,
diff --git a/drivers/firmware/efi/unaccepted_memory.c b/drivers/firmware/efi/unaccepted_memory.c
index 4479aad258f8..8537812346e2 100644
--- a/drivers/firmware/efi/unaccepted_memory.c
+++ b/drivers/firmware/efi/unaccepted_memory.c
@@ -218,6 +218,89 @@ bool range_contains_unaccepted_memory(phys_addr_t start, unsigned long size)
 	return ret;
 }
 
+static int extend_unaccepted_bitmap(phys_addr_t mem_range_start,
+				    unsigned long mem_range_size)
+{
+	struct efi_unaccepted_memory *unacc_tbl;
+	unsigned long *old_bitmap, *new_bitmap;
+	phys_addr_t start, end, mem_range_end;
+	u64 phys_base, size, unit_size;
+	unsigned long flags;
+
+	unacc_tbl = efi_get_unaccepted_table();
+	if (!unacc_tbl || !unacc_tbl->unit_size)
+		return -EIO;
+
+	unit_size = unacc_tbl->unit_size;
+	phys_base = unacc_tbl->phys_base;
+
+	mem_range_end = round_up(mem_range_start + mem_range_size, unit_size);
+	size = DIV_ROUND_UP(mem_range_end - phys_base, unit_size * BITS_PER_BYTE);
+
+	/* Translate to offsets from the beginning of the bitmap */
+	start = mem_range_start - phys_base;
+	end = mem_range_end - phys_base;
+
+	old_bitmap = efi_get_unaccepted_bitmap();
+	if (!old_bitmap)
+		return -EIO;
+
+	/* If the bitmap is already large enough, just set the bits */
+	if (unacc_tbl->size >= size) {
+		spin_lock_irqsave(&unaccepted_memory_lock, flags);
+		bitmap_set(old_bitmap, start / unit_size, (end - start) / unit_size);
+		spin_unlock_irqrestore(&unaccepted_memory_lock, flags);
+
+		return 0;
+	}
+
+	/* Reserved memblocks cannot be extended so allocate a new bitmap */
+	if (unacc_tbl->mem_reserved) {
+		new_bitmap = kzalloc(size, GFP_KERNEL);
+		if (!new_bitmap)
+			return -ENOMEM;
+
+		spin_lock_irqsave(&unaccepted_memory_lock, flags);
+		memcpy(new_bitmap, old_bitmap, unacc_tbl->size);
+		unacc_tbl->mem_reserved = false;
+		free_reserved_area(old_bitmap, old_bitmap + unacc_tbl->size, -1, NULL);
+		spin_unlock_irqrestore(&unaccepted_memory_lock, flags);
+	} else {
+		new_bitmap = krealloc(old_bitmap, size, GFP_KERNEL);
+		if (!new_bitmap)
+			return -ENOMEM;
+
+		/* Zero the bitmap from the range it was extended from */
+		memset(new_bitmap + unacc_tbl->size, 0, size - unacc_tbl->size);
+	}
+
+	bitmap_set(new_bitmap, start / unit_size, (end - start) / unit_size);
+
+	spin_lock_irqsave(&unaccepted_memory_lock, flags);
+	unacc_tbl->size = size;
+	unacc_tbl->bitmap = (unsigned long *)__pa(new_bitmap);
+	spin_unlock_irqrestore(&unaccepted_memory_lock, flags);
+
+	return 0;
+}
+
+int accept_hotplug_memory(phys_addr_t mem_range_start, unsigned long mem_range_size)
+{
+	int ret;
+
+	if (!IS_ENABLED(CONFIG_UNACCEPTED_MEMORY))
+		return 0;
+
+	ret = extend_unaccepted_bitmap(mem_range_start, mem_range_size);
+	if (ret)
+		return ret;
+
+	if (!mm_lazy_accept_enabled())
+		accept_memory(mem_range_start, mem_range_size);
+
+	return 0;
+}
+
 #ifdef CONFIG_PROC_VMCORE
 static bool unaccepted_memory_vmcore_pfn_is_ram(struct vmcore_cb *cb,
 						unsigned long pfn)
diff --git a/include/linux/efi.h b/include/linux/efi.h
index a74b393c54d8..1021eb78388f 100644
--- a/include/linux/efi.h
+++ b/include/linux/efi.h
@@ -545,6 +545,7 @@ struct efi_unaccepted_memory {
 	u32 unit_size;
 	u64 phys_base;
 	u64 size;
+	bool mem_reserved;
 	unsigned long *bitmap;
 };
 
diff --git a/include/linux/mm.h b/include/linux/mm.h
index 1ae97a0b8ec7..bb43876e6c47 100644
--- a/include/linux/mm.h
+++ b/include/linux/mm.h
@@ -4077,6 +4077,9 @@ int set_anon_vma_name(unsigned long addr, unsigned long size,
 
 bool range_contains_unaccepted_memory(phys_addr_t start, unsigned long size);
 void accept_memory(phys_addr_t start, unsigned long size);
+int accept_hotplug_memory(phys_addr_t mem_range_start,
+			  unsigned long mem_range_size);
+bool mm_lazy_accept_enabled(void);
 
 #else
 
@@ -4090,6 +4093,14 @@ static inline void accept_memory(phys_addr_t start, unsigned long size)
 {
 }
 
+static inline int accept_hotplug_memory(phys_addr_t mem_range_start,
+					unsigned long mem_range_size)
+{
+	return 0;
+}
+
+static inline bool mm_lazy_accept_enabled(void) { return false; }
+
 #endif
 
 static inline bool pfn_is_unaccepted_memory(unsigned long pfn)
diff --git a/mm/memory_hotplug.c b/mm/memory_hotplug.c
index 74318c787715..bf8086682b66 100644
--- a/mm/memory_hotplug.c
+++ b/mm/memory_hotplug.c
@@ -1581,6 +1581,13 @@ int add_memory_resource(int nid, struct resource *res, mhp_t mhp_flags)
 	if (!strcmp(res->name, "System RAM"))
 		firmware_map_add_hotplug(start, start + size, "System RAM");
 
+	ret = accept_hotplug_memory(start, size);
+	if (ret) {
+		remove_memory_block_devices(start, size);
+		arch_remove_memory(start, size, params.altmap);
+		goto error;
+	}
+
 	/* device_online() will take the lock when calling online_pages() */
 	mem_hotplug_done();
 
diff --git a/mm/page_alloc.c b/mm/page_alloc.c
index d1d037f97c5f..d0c298dcaf9d 100644
--- a/mm/page_alloc.c
+++ b/mm/page_alloc.c
@@ -7331,6 +7331,8 @@ bool has_managed_dma(void)
 
 static bool lazy_accept = true;
 
+bool mm_lazy_accept_enabled(void) { return lazy_accept; }
+
 static int __init accept_memory_parse(char *p)
 {
 	if (!strcmp(p, "lazy")) {

---

## [4] Pratik R. Sampat — 2025-11-25
*Subject: [RFC PATCH 3/4] x86/sev: Introduce hotplug-aware SNP page state validation*

When hot-removing memory in a SEV-SNP environment, pages must be set to
shared state so they can be reused by the hypervisor. This also applies
when memory is intended to be hotplugged back in later, as those pages
will need to be re-accepted after crossing the trust boundary.

However, memory can already be set to shared state externally. In such
cases, the pvalidate rescind operation will not change the validated bit
in the RMP table, setting the carry flag and causing the guest to
terminate.

Since memory hotplug is arguably unique, introduce a guest-maintained
memory state tracking structure that maintains a bitmap to track the
state (private vs shared) of all hotplugged memory supplemented with a
flag to indicate intent. This allows for memory that is already marked
as shared in the hotplug bitmap to avoid performing the pvalidate
rescind operation. Additionally, tracking page state changes from the
guest's perspective, enables the detection of inconsistencies if the
hypervisor changes states unexpectedly. For example, if the guest bitmap
reports memory as private but the hypervisor has already changed the RMP
state to shared, the guest detects this inconsistency when attempting to
share the memory and terminate rather than skipping over the pvalidate
rescind operation.

Signed-off-by: Pratik R. Sampat <prsampat@amd.com>
---
 arch/x86/coco/sev/core.c                 | 104 +++++++++++++++++++++--
 arch/x86/include/asm/sev.h               |  32 +++++++
 arch/x86/include/asm/unaccepted_memory.h |  13 +++
 drivers/firmware/efi/unaccepted_memory.c |   2 +-
 4 files changed, 143 insertions(+), 8 deletions(-)

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index 14ef5908fb27..a5c9615a6e0c 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -46,6 +46,8 @@
 #include <asm/cmdline.h>
 #include <asm/msr.h>
 
+struct snp_hotplug_memory *snp_hp_mem;
+
 /* AP INIT values as documented in the APM2  section "Processor Initialization State" */
 #define AP_INIT_CS_LIMIT		0xffff
 #define AP_INIT_DS_LIMIT		0xffff
@@ -453,9 +455,54 @@ static int vmgexit_psc(struct ghcb *ghcb, struct snp_psc_desc *desc)
 	return ret;
 }
 
+static bool snp_hotplug_state_shared(unsigned long vaddr)
+{
+	phys_addr_t paddr = __pa(vaddr);
+	u64 hotplug_bit;
+
+	if (!snp_is_hotplug_memory(paddr))
+		return false;
+
+	hotplug_bit = (paddr - snp_hp_mem->phys_base) / snp_hp_mem->unit_size;
+
+	return !test_bit(hotplug_bit, snp_hp_mem->bitmap);
+}
+
+static void snp_set_hotplug_bit(unsigned long vaddr, bool private)
+{
+	phys_addr_t paddr = __pa(vaddr);
+	u64 hotplug_bit;
+
+	if (!snp_is_hotplug_memory(paddr))
+		return;
+
+	hotplug_bit = (paddr - snp_hp_mem->phys_base) / snp_hp_mem->unit_size;
+	if (private)
+		set_bit(hotplug_bit, snp_hp_mem->bitmap);
+	else
+		clear_bit(hotplug_bit, snp_hp_mem->bitmap);
+}
+
+static void set_hotplug_pages_state(struct snp_psc_desc *desc)
+{
+	struct psc_entry *e;
+	unsigned long vaddr;
+	bool op;
+	int i;
+
+	for (i = 0; i <= desc->hdr.end_entry; i++) {
+		e = &desc->entries[i];
+		vaddr = (unsigned long)pfn_to_kaddr(e->gfn);
+		op = e->operation == SNP_PAGE_STATE_PRIVATE;
+
+		snp_set_hotplug_bit(vaddr, op);
+	}
+}
+
 static unsigned long __set_pages_state(struct snp_psc_desc *data, unsigned long vaddr,
-				       unsigned long vaddr_end, int op)
+				       unsigned long vaddr_end, int op, u8 psc_flags)
 {
+	unsigned long vaddr_base;
 	struct ghcb_state state;
 	bool use_large_entry;
 	struct psc_hdr *hdr;
@@ -465,6 +512,7 @@ static unsigned long __set_pages_state(struct snp_psc_desc *data, unsigned long
 	struct ghcb *ghcb;
 	int i;
 
+	vaddr_base = vaddr;
 	hdr = &data->hdr;
 	e = data->entries;
 
@@ -499,7 +547,8 @@ static unsigned long __set_pages_state(struct snp_psc_desc *data, unsigned long
 	}
 
 	/* Page validation must be rescinded before changing to shared */
-	if (op == SNP_PAGE_STATE_SHARED)
+	if (op == SNP_PAGE_STATE_SHARED &&
+	    !(snp_hotplug_state_shared(vaddr_base) && (psc_flags & SNP_PSC_SHARED_TO_SHARED)))
 		pvalidate_pages(data);
 
 	local_irq_save(flags);
@@ -522,10 +571,12 @@ static unsigned long __set_pages_state(struct snp_psc_desc *data, unsigned long
 	if (op == SNP_PAGE_STATE_PRIVATE)
 		pvalidate_pages(data);
 
+	set_hotplug_pages_state(data);
+
 	return vaddr;
 }
 
-static void set_pages_state(unsigned long vaddr, unsigned long npages, int op)
+static void set_pages_state(unsigned long vaddr, unsigned long npages, int op, u8 psc_flags)
 {
 	struct snp_psc_desc desc;
 	unsigned long vaddr_end;
@@ -538,7 +589,7 @@ static void set_pages_state(unsigned long vaddr, unsigned long npages, int op)
 	vaddr_end = vaddr + (npages << PAGE_SHIFT);
 
 	while (vaddr < vaddr_end)
-		vaddr = __set_pages_state(&desc, vaddr, vaddr_end, op);
+		vaddr = __set_pages_state(&desc, vaddr, vaddr_end, op, psc_flags);
 }
 
 void snp_set_memory_shared(unsigned long vaddr, unsigned long npages)
@@ -546,7 +597,7 @@ void snp_set_memory_shared(unsigned long vaddr, unsigned long npages)
 	if (!cc_platform_has(CC_ATTR_GUEST_SEV_SNP))
 		return;
 
-	set_pages_state(vaddr, npages, SNP_PAGE_STATE_SHARED);
+	set_pages_state(vaddr, npages, SNP_PAGE_STATE_SHARED, 0);
 }
 
 void snp_set_memory_private(unsigned long vaddr, unsigned long npages)
@@ -554,7 +605,7 @@ void snp_set_memory_private(unsigned long vaddr, unsigned long npages)
 	if (!cc_platform_has(CC_ATTR_GUEST_SEV_SNP))
 		return;
 
-	set_pages_state(vaddr, npages, SNP_PAGE_STATE_PRIVATE);
+	set_pages_state(vaddr, npages, SNP_PAGE_STATE_PRIVATE, 0);
 }
 
 void snp_accept_memory(phys_addr_t start, phys_addr_t end)
@@ -567,7 +618,46 @@ void snp_accept_memory(phys_addr_t start, phys_addr_t end)
 	vaddr = (unsigned long)__va(start);
 	npages = (end - start) >> PAGE_SHIFT;
 
-	set_pages_state(vaddr, npages, SNP_PAGE_STATE_PRIVATE);
+	set_pages_state(vaddr, npages, SNP_PAGE_STATE_PRIVATE, 0);
+}
+
+int snp_extend_hotplug_memory_state_bitmap(phys_addr_t start,
+					   unsigned long size,
+					   uint64_t unit_size)
+{
+	u64 hp_mem_size = DIV_ROUND_UP(size, unit_size * BITS_PER_BYTE);
+
+	if (snp_hp_mem) {
+		u64 old_size = snp_hp_mem->size;
+		unsigned long *bitmap;
+
+		bitmap = krealloc(snp_hp_mem->bitmap, hp_mem_size, GFP_KERNEL);
+		if (!bitmap)
+			return -ENOMEM;
+
+		memset(bitmap + old_size, 0, hp_mem_size - old_size);
+		snp_hp_mem->size = hp_mem_size;
+		snp_hp_mem->bitmap = bitmap;
+
+		return 0;
+	}
+
+	snp_hp_mem = kzalloc(sizeof(*snp_hp_mem), GFP_KERNEL);
+	if (!snp_hp_mem)
+		return -ENOMEM;
+
+	snp_hp_mem->bitmap = kzalloc(hp_mem_size, GFP_KERNEL);
+	if (!snp_hp_mem->bitmap) {
+		kfree(snp_hp_mem);
+		return -ENOMEM;
+	}
+
+	snp_hp_mem->phys_base = start;
+	snp_hp_mem->phys_end = start + hp_mem_size;
+	snp_hp_mem->size = hp_mem_size;
+	snp_hp_mem->unit_size = unit_size;
+
+	return 0;
 }
 
 static int vmgexit_ap_control(u64 event, struct sev_es_save_area *vmsa, u32 apic_id)
diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index 465b19fd1a2d..eb605892645c 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -464,6 +464,38 @@ static __always_inline void sev_es_nmi_complete(void)
 extern int __init sev_es_efi_map_ghcbs_cas(pgd_t *pgd);
 extern void sev_enable(struct boot_params *bp);
 
+#define SNP_PSC_SHARED_TO_SHARED	0x1
+
+struct snp_hotplug_memory {
+	u64 phys_base;
+	u64 phys_end;
+	u32 unit_size;
+	u64 size;
+	/* bitmap bit unset: shared, set: private */
+	unsigned long *bitmap;
+};
+
+extern struct snp_hotplug_memory *snp_hp_mem;
+
+#ifdef CONFIG_UNACCEPTED_MEMORY
+int snp_extend_hotplug_memory_state_bitmap(phys_addr_t start,
+					   unsigned long size,
+					   uint64_t unit_size);
+static inline bool snp_is_hotplug_memory(phys_addr_t paddr)
+{
+	return snp_hp_mem && paddr >= snp_hp_mem->phys_base && paddr < snp_hp_mem->phys_end;
+}
+#else /* !CONFIG_UNACCEPTED_MEMORY */
+static inline int snp_extend_hotplug_memory_state_bitmap(phys_addr_t start,
+							 unsigned long size,
+							 uint64_t unit_size)
+{
+	return 0;
+}
+
+static inline bool snp_is_hotplug_memory(phys_addr_t paddr) { return false; }
+#endif
+
 /*
  * RMPADJUST modifies the RMP permissions of a page of a lesser-
  * privileged (numerically higher) VMPL.
diff --git a/arch/x86/include/asm/unaccepted_memory.h b/arch/x86/include/asm/unaccepted_memory.h
index 5da80e68d718..abdf5472de9e 100644
--- a/arch/x86/include/asm/unaccepted_memory.h
+++ b/arch/x86/include/asm/unaccepted_memory.h
@@ -33,4 +33,17 @@ static inline unsigned long *efi_get_unaccepted_bitmap(void)
 		return NULL;
 	return __va(unaccepted->bitmap);
 }
+
+static inline int arch_set_unaccepted_mem_state(phys_addr_t start, unsigned long size)
+{
+	struct efi_unaccepted_memory *unaccepted = efi_get_unaccepted_table();
+
+	if (!unaccepted)
+		return -EIO;
+
+	if (cc_platform_has(CC_ATTR_GUEST_SEV_SNP))
+		return snp_extend_hotplug_memory_state_bitmap(start, size, unaccepted->unit_size);
+
+	return 0;
+}
 #endif
diff --git a/drivers/firmware/efi/unaccepted_memory.c b/drivers/firmware/efi/unaccepted_memory.c
index 8537812346e2..6796042a64aa 100644
--- a/drivers/firmware/efi/unaccepted_memory.c
+++ b/drivers/firmware/efi/unaccepted_memory.c
@@ -281,7 +281,7 @@ static int extend_unaccepted_bitmap(phys_addr_t mem_range_start,
 	unacc_tbl->bitmap = (unsigned long *)__pa(new_bitmap);
 	spin_unlock_irqrestore(&unaccepted_memory_lock, flags);
 
-	return 0;
+	return arch_set_unaccepted_mem_state(mem_range_start, mem_range_size);
 }
 
 int accept_hotplug_memory(phys_addr_t mem_range_start, unsigned long mem_range_size)

---

## [5] Pratik R. Sampat — 2025-11-25
*Subject: [RFC PATCH 4/4] mm: Add support for unaccepted memory hot-remove*

Transition memory to shared during a hot-remove operation so that it can
be re-used by the hypervisor. During lazy acceptance, only memory that
was used has been accepted, therefore during hot-remove only mark pages
as shared that were previously accepted / made private.

Signed-off-by: Pratik R. Sampat <prsampat@amd.com>
---
 arch/x86/coco/sev/core.c                 | 23 +++++++++++++++
 arch/x86/include/asm/sev.h               |  2 ++
 arch/x86/include/asm/unaccepted_memory.h |  9 ++++++
 drivers/firmware/efi/unaccepted_memory.c | 37 ++++++++++++++++++++++++
 include/linux/mm.h                       |  7 +++++
 mm/memory_hotplug.c                      |  2 ++
 6 files changed, 80 insertions(+)

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index a5c9615a6e0c..c05fc91d10a1 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -621,6 +621,29 @@ void snp_accept_memory(phys_addr_t start, phys_addr_t end)
 	set_pages_state(vaddr, npages, SNP_PAGE_STATE_PRIVATE, 0);
 }
 
+void snp_unaccept_memory(phys_addr_t start, phys_addr_t end)
+{
+	unsigned long vaddr, npages;
+
+	if (!cc_platform_has(CC_ATTR_GUEST_SEV_SNP))
+		return;
+
+	vaddr = (unsigned long)__va(start);
+	npages = (end - start) >> PAGE_SHIFT;
+
+	/*
+	 * Hotplugged memory can be set to shared externally. Attempting to
+	 * re-share the memory (during hot-remove) will cause the pvalidate
+	 * operation to not make any changes to the RMP table triggering the
+	 * PVALIDATE_FAIL_NOUPDATE condition
+	 *
+	 * Since the memory hotplug case is unique, specify this intent so that
+	 * if the page is part of hotplugged memory a pvalidate rescind
+	 * operation is not performed
+	 */
+	set_pages_state(vaddr, npages, SNP_PAGE_STATE_SHARED, SNP_PSC_SHARED_TO_SHARED);
+}
+
 int snp_extend_hotplug_memory_state_bitmap(phys_addr_t start,
 					   unsigned long size,
 					   uint64_t unit_size)
diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index eb605892645c..8f3c5b878fd7 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -547,6 +547,7 @@ void __noreturn snp_abort(void);
 void snp_dmi_setup(void);
 int snp_issue_svsm_attest_req(u64 call_id, struct svsm_call *call, struct svsm_attest_call *input);
 void snp_accept_memory(phys_addr_t start, phys_addr_t end);
+void snp_unaccept_memory(phys_addr_t start, phys_addr_t end);
 u64 snp_get_unsupported_features(u64 status);
 u64 sev_get_status(void);
 void sev_show_status(void);
@@ -639,6 +640,7 @@ static inline int snp_issue_svsm_attest_req(u64 call_id, struct svsm_call *call,
 	return -ENOTTY;
 }
 static inline void snp_accept_memory(phys_addr_t start, phys_addr_t end) { }
+static inline void snp_unaccept_memory(phys_addr_t start, phys_addr_t end) { }
 static inline u64 snp_get_unsupported_features(u64 status) { return 0; }
 static inline u64 sev_get_status(void) { return 0; }
 static inline void sev_show_status(void) { }
diff --git a/arch/x86/include/asm/unaccepted_memory.h b/arch/x86/include/asm/unaccepted_memory.h
index abdf5472de9e..ad392294b71b 100644
--- a/arch/x86/include/asm/unaccepted_memory.h
+++ b/arch/x86/include/asm/unaccepted_memory.h
@@ -18,6 +18,15 @@ static inline void arch_accept_memory(phys_addr_t start, phys_addr_t end)
 	}
 }
 
+static inline void arch_unaccept_memory(phys_addr_t start, phys_addr_t end)
+{
+	if (cc_platform_has(CC_ATTR_GUEST_SEV_SNP)) {
+		snp_unaccept_memory(start, end);
+	} else {
+		panic("Cannot accept memory: unknown platform\n");
+	}
+}
+
 static inline struct efi_unaccepted_memory *efi_get_unaccepted_table(void)
 {
 	if (efi.unaccepted == EFI_INVALID_TABLE_ADDR)
diff --git a/drivers/firmware/efi/unaccepted_memory.c b/drivers/firmware/efi/unaccepted_memory.c
index 6796042a64aa..662cf0d6715f 100644
--- a/drivers/firmware/efi/unaccepted_memory.c
+++ b/drivers/firmware/efi/unaccepted_memory.c
@@ -301,6 +301,43 @@ int accept_hotplug_memory(phys_addr_t mem_range_start, unsigned long mem_range_s
 	return 0;
 }
 
+void unaccept_hotplug_memory(phys_addr_t mem_range_start, unsigned long mem_range_size)
+{
+	u64 unit_size, phys_base, bit_start, bit_end, addr;
+	struct efi_unaccepted_memory *unacc_tbl;
+	unsigned long flags, *bitmap;
+	phys_addr_t start, end;
+	int i;
+
+	unacc_tbl = efi_get_unaccepted_table();
+	if (!unacc_tbl)
+		return;
+
+	phys_base = unacc_tbl->phys_base;
+	unit_size = unacc_tbl->unit_size;
+
+	start = mem_range_start - phys_base;
+	end = (mem_range_start + mem_range_size) - phys_base;
+
+	bit_start = start / unit_size;
+	bit_end = end / unit_size;
+
+	/* Only unaccept memory that was previously accepted in the range */
+	for (i = bit_start; i < bit_end; i++) {
+		spin_lock_irqsave(&unaccepted_memory_lock, flags);
+		bitmap = efi_get_unaccepted_bitmap();
+		if (!bitmap || test_bit(i, bitmap)) {
+			spin_unlock_irqrestore(&unaccepted_memory_lock, flags);
+			continue;
+		}
+
+		addr = phys_base + i * unit_size;
+
+		arch_unaccept_memory(addr, addr + unit_size);
+		spin_unlock_irqrestore(&unaccepted_memory_lock, flags);
+	}
+}
+
 #ifdef CONFIG_PROC_VMCORE
 static bool unaccepted_memory_vmcore_pfn_is_ram(struct vmcore_cb *cb,
 						unsigned long pfn)
diff --git a/include/linux/mm.h b/include/linux/mm.h
index bb43876e6c47..34d48693dc86 100644
--- a/include/linux/mm.h
+++ b/include/linux/mm.h
@@ -4079,6 +4079,8 @@ bool range_contains_unaccepted_memory(phys_addr_t start, unsigned long size);
 void accept_memory(phys_addr_t start, unsigned long size);
 int accept_hotplug_memory(phys_addr_t mem_range_start,
 			  unsigned long mem_range_size);
+void unaccept_hotplug_memory(phys_addr_t mem_range_start,
+			     unsigned long mem_range_size);
 bool mm_lazy_accept_enabled(void);
 
 #else
@@ -4099,6 +4101,11 @@ static inline int accept_hotplug_memory(phys_addr_t mem_range_start,
 	return 0;
 }
 
+static inline void unaccept_hotplug_memory(phys_addr_t mem_range_start,
+					   unsigned long mem_range_size)
+{
+}
+
 static inline bool mm_lazy_accept_enabled(void) { return false; }
 
 #endif
diff --git a/mm/memory_hotplug.c b/mm/memory_hotplug.c
index bf8086682b66..0b14b14e53fe 100644
--- a/mm/memory_hotplug.c
+++ b/mm/memory_hotplug.c
@@ -2254,6 +2254,8 @@ static int try_remove_memory(u64 start, u64 size)
 
 	mem_hotplug_begin();
 
+	unaccept_hotplug_memory(start, size);
+
 	rc = memory_blocks_have_altmaps(start, size);
 	if (rc < 0) {
 		mem_hotplug_done();

---

## [6] Kiryl Shutsemau — 2025-11-26
*Subject: Re: [RFC PATCH 1/4] efi/libstub: Decouple memory bitmap from the
 unaccepted table*

On Tue, Nov 25, 2025 at 11:57:50AM -0600, Pratik R. Sampat wrote:
> Memory hotplug in secure environments requires the unaccepted memory
> bitmap to grow as new memory is added. Currently, the bitmap is

Well, it break interoperability between kernel before and after the
patch. Consider kexec from kernel without the patch to the kernel with
the patch and then back to older kernel. It is ABI break.

Is re-allocating the entire structure such a big pain?

---

## [7] Kiryl Shutsemau — 2025-11-26
*Subject: Re: [RFC PATCH 2/4] mm: Add support for unaccepted memory hotplug*

On Tue, Nov 25, 2025 at 11:57:51AM -0600, Pratik R. Sampat wrote:
> The unaccepted memory structure currently only supports accepting memory
> present at boot time. The unaccepted table uses a fixed-size bitmap

How does the hot-pluggable memory look in EFI memory map? I thought
hot-pluggable ranges suppose to be declared thare. The cleanest solution
would be to have hot-pluggable and unaccepted indicated in EFI memory,
so we can size bitmap accordingly upfront.

> Extend the unaccepted memory framework to handle hotplugged memory by
> dynamically managing the unaccepted bitmap. Allocate a new bitmap when

Again, this is ABI break for kexec.

---

## [8] Pratik R. Sampat — 2025-11-26
*Subject: Re: [RFC PATCH 1/4] efi/libstub: Decouple memory bitmap from the
 unaccepted table*

Hi Kiryl,

Thanks for you comments.

On 11/26/25 5:08 AM, Kiryl Shutsemau wrote:
> On Tue, Nov 25, 2025 at 11:57:50AM -0600, Pratik R. Sampat wrote:
>> Memory hotplug in secure environments requires the unaccepted memory

We could do that. My concern is that we would then need to protect the
entire table instead of just the bitmap, which may add an additional
overhead?

--
Pratik

---

## [9] Pratik R. Sampat — 2025-11-26
*Subject: Re: [RFC PATCH 2/4] mm: Add support for unaccepted memory hotplug*

On 11/26/25 5:12 AM, Kiryl Shutsemau wrote:
> On Tue, Nov 25, 2025 at 11:57:51AM -0600, Pratik R. Sampat wrote:
>> The unaccepted memory structure currently only supports accepting memory

I'm not quite sure if I fully understand. Do you mean to refer to the
EFI_MEMORY_HOT_PLUGGABLE attribute that is used for cold plugged boot
memory? If so, wouldn't it still be desirable to increase the size of
the bitmap to what was marked as hotpluggable initially?

>> Extend the unaccepted memory framework to handle hotplugged memory by
>> dynamically managing the unaccepted bitmap. Allocate a new bitmap when

Right, maybe I could just use memblock_is_reserved() instead to prevent
this ABI breakage.

Thanks!
--
Pratik

---

## [10] Borislav Petkov — 2025-11-26
*Subject: Re: [RFC PATCH 2/4] mm: Add support for unaccepted memory hotplug*

On Wed, Nov 26, 2025 at 11:12:13AM +0000, Kiryl Shutsemau wrote:
> > diff --git a/arch/x86/boot/compressed/efi.h b/arch/x86/boot/compressed/efi.h
> > index 4f7027f33def..a220a1966cae 100644

ABI break for kexec? Is that a thing?

Since when do we enforce ABI compatibility for kexec and where are we
documenting that?

---

## [11] Kiryl Shutsemau — 2025-11-27
*Subject: Re: [RFC PATCH 1/4] efi/libstub: Decouple memory bitmap from the
 unaccepted table*

On Wed, Nov 26, 2025 at 04:27:19PM -0600, Pratik R. Sampat wrote:
> Hi Kiryl,
> 

What additional overhead? The main contention is going to be on binmap
anyway.

---

## [12] Kiryl Shutsemau — 2025-11-27
*Subject: Re: [RFC PATCH 2/4] mm: Add support for unaccepted memory hotplug*

On Wed, Nov 26, 2025 at 11:31:27PM +0100, Borislav Petkov wrote:
> On Wed, Nov 26, 2025 at 11:12:13AM +0000, Kiryl Shutsemau wrote:
> > > diff --git a/arch/x86/boot/compressed/efi.h b/arch/x86/boot/compressed/efi.h

The whole purpose of kexec() is to switch between kernel versions. This
struct defines format we communicate information about unaccepted memory
between kernels. The mismatch will lead to boot failure.

The structure is versioned. Ideally, we should know the format of the
structure the next kernel supports and act accordingly in the first
kernel. Like, we can accept all memory before kexec on mismatch.

---

## [13] Kiryl Shutsemau — 2025-11-27
*Subject: Re: [RFC PATCH 2/4] mm: Add support for unaccepted memory hotplug*

On Wed, Nov 26, 2025 at 04:27:29PM -0600, Pratik R. Sampat wrote:
> 
> 

I just don't understand how hotpluggable memory presented in EFI memory
map in presence of unaccepted memory. If not-yet-plugged memory marked
as unaccepted we can preallocate bitmap upfront and make unaccepted
memory transparent wrt hotplug.

BTW, isn't virtio-mem a more attractive target to support than HW-style
hotplug?

---

## [14] Borislav Petkov — 2025-11-27
*Subject: Re: [RFC PATCH 2/4] mm: Add support for unaccepted memory hotplug*

On Thu, Nov 27, 2025 at 05:35:57PM +0000, Kiryl Shutsemau wrote:
> > ABI break for kexec? Is that a thing?
> > 

I'll take that as a "no".

> The whole purpose of kexec() is to switch between kernel versions. This
> struct defines format we communicate information about unaccepted memory

None of that matters if you kexec the same kernels.

IOW, for some reason you want to be able to kexec different kernels. The
question is why do we care?

AFAICT, nowhere do we say that there's an ABI between kexec-ed kernels...

Thx.

---

## [15] David Hildenbrand (Red Hat) — 2025-11-28
*Subject: Re: [RFC PATCH 2/4] mm: Add support for unaccepted memory hotplug*

On 11/27/25 19:12, Borislav Petkov wrote:
> On Thu, Nov 27, 2025 at 05:35:57PM +0000, Kiryl Shutsemau wrote:
>>> ABI break for kexec? Is that a thing?

kexecing the same kernel is typically used for kdump purposes.

kexecing different kernels is used for all sorts of things 
(live-upgrade, grub-emu come to mind). It's quite common to kexec 
different kernels, or maybe I misunderstood the question here?

---

## [16] David Hildenbrand (Red Hat) — 2025-11-28
*Subject: Re: [RFC PATCH 2/4] mm: Add support for unaccepted memory hotplug*

On 11/25/25 18:57, Pratik R. Sampat wrote:
> The unaccepted memory structure currently only supports accepting memory
> present at boot time. The unaccepted table uses a fixed-size bitmap

What makes this special that we have to have "hotplug_memory" as part of 
the name?

Staring at the helper itself, there isn't anything really hotplug 
specific happening in there except extending the bitmap, maybe?

---

## [17] David Hildenbrand (Red Hat) — 2025-11-28
*Subject: Re: [RFC PATCH 2/4] mm: Add support for unaccepted memory hotplug*

On 11/27/25 18:40, Kiryl Shutsemau wrote:
> On Wed, Nov 26, 2025 at 04:27:29PM -0600, Pratik R. Sampat wrote:
>>

I would have thought so as well, such that we can just let virtio-mem 
take care of any acceptance before actually using hotplugged memory 
(exposing it to the buddy).

Likely there is desire to support other hypervisors?

---

## [18] Borislav Petkov — 2025-11-28
*Subject: Re: [RFC PATCH 2/4] mm: Add support for unaccepted memory hotplug*

On Fri, Nov 28, 2025 at 10:30:15AM +0100, David Hildenbrand (Red Hat) wrote:
> kexecing the same kernel is typically used for kdump purposes.
> 

And my question is: since when do we enforce no-ABI-changes between kernels so
that we can kexec any kernel into any kernel?

By that logic I should be able to kexec 5.x into 6.x. I'll bet some money that
it won't work.

So unless it is written down somewhere, I think we should probably talk first
what we want to support and why...

Makes sense?

---

## [19] David Hildenbrand (Red Hat) — 2025-12-01
*Subject: Re: [RFC PATCH 2/4] mm: Add support for unaccepted memory hotplug*

On 11/28/25 12:34, Borislav Petkov wrote:
> On Fri, Nov 28, 2025 at 10:30:15AM +0100, David Hildenbrand (Red Hat) wrote:
>> kexecing the same kernel is typically used for kdump purposes.

I *think* ordinary kexec would likely work, as I recall that it doesn't 
need a lot of that special kexec ABI sauce like unaccepted memory uses.

Within confidential VMs (kexec ...) I am pretty sure that it's a 
different discussion.

> 
> So unless it is written down somewhere, I think we should probably talk first

Makes sense to me, especially for confidential VMs where we pass such 
kernel-managed data from the old to the new kernel.

---

## [20] Borislav Petkov — 2025-12-01
*Subject: Re: [RFC PATCH 2/4] mm: Add support for unaccepted memory hotplug*

On Mon, Dec 01, 2025 at 10:18:37AM +0100, David Hildenbrand (Red Hat) wrote:
> Makes sense to me, especially for confidential VMs where we pass such
> kernel-managed data from the old to the new kernel.

It shouldn't matter, right?

I think the question is whether the kernel should agree to the software
contract (/eyeroll) to keep the kernel ABI compatible wrt kexec.

And I don't think we have agreed to that AFAIK.

Thx.

---

## [21] Pratik R. Sampat — 2025-12-01
*Subject: Re: [RFC PATCH 2/4] mm: Add support for unaccepted memory hotplug*

On 11/27/25 11:40 AM, Kiryl Shutsemau wrote:
> On Wed, Nov 26, 2025 at 04:27:29PM -0600, Pratik R. Sampat wrote:
>>

If memory that hasn't been plugged yet never gets plugged in or is only
partially plugged in, wouldn't we be wasting space by preallocating
the bitmap upfront? Or would that not be a concern in favor of
transparency?

--Pratik

---

## [22] Pratik R. Sampat — 2025-12-01
*Subject: Re: [RFC PATCH 2/4] mm: Add support for unaccepted memory hotplug*

Hi David,

On 11/28/25 3:34 AM, David Hildenbrand (Red Hat) wrote:
> On 11/27/25 18:40, Kiryl Shutsemau wrote:
>> On Wed, Nov 26, 2025 at 04:27:29PM -0600, Pratik R. Sampat wrote:

That's true. We are certainly thinking about how the RAM discard manager
should look like with multiple states to allow guest_memfd and
virtio-mem to work together.

Since both paths in Linux eventually converge around
add_memory_resource(), based on some light hacking in QEMU I could see
similar hotplug behavior for virtio-mem as well. So I thought I'd get
some feedback on the Linux side of the design since enabling it
for traditional memory seemed like a simpler first step in enabling
hotplug.

Thanks,
--Pratik

---

## [23] Pratik R. Sampat — 2025-12-01
*Subject: Re: [RFC PATCH 2/4] mm: Add support for unaccepted memory hotplug*

On 11/28/25 3:32 AM, David Hildenbrand (Red Hat) wrote:
> On 11/25/25 18:57, Pratik R. Sampat wrote:
>> The unaccepted memory structure currently only supports accepting memory

Right, we are extending the original bitmap and initializing a structure
to track state as well. I added the hotplug_memory keyword without
much thought, since I didn't see anyone else attempting to extend these
structures.

That said, I agree the name is awkward. I could either come up with
something different, or we could eliminate the parent function
entirely and call extend_unaccepted_bitmap() + accept_memory() directly
from add_memory_resource(). Similarly, we could do the same to
s/unaccept_hotplug_memory/unaccept_memory too.

Thanks,
--Pratik

---

## [24] Kiryl Shutsemau — 2025-12-01
*Subject: Re: [RFC PATCH 2/4] mm: Add support for unaccepted memory hotplug*

On Mon, Dec 01, 2025 at 11:15:13AM -0600, Pratik R. Sampat wrote:
> 
> 

4k per 64GiB of physical address space should be low enough to ignore, no?

We can look into optimizing it out when it is an actual, not imaginary
problem.

---

## [25] Pratik R. Sampat — 2025-12-01
*Subject: Re: [RFC PATCH 2/4] mm: Add support for unaccepted memory hotplug*

On 12/1/25 11:48 AM, Kiryl Shutsemau wrote:
> On Mon, Dec 01, 2025 at 11:15:13AM -0600, Pratik R. Sampat wrote:
>>

Sure, that's fair!

--Pratik

---

## [26] David Hildenbrand (Red Hat) — 2025-12-01
*Subject: Re: [RFC PATCH 2/4] mm: Add support for unaccepted memory hotplug*

On 12/1/25 18:15, Pratik R. Sampat wrote:
> Hi David,
> 

Right, there is the QEMU side of it as well.

> Since both paths in Linux eventually converge around
> add_memory_resource(), based on some light hacking in QEMU I could see

For virtio-mem it would not be add_memory_resource().

Whenever we would be plugging memory we would be accepting it, and when 
we would be unplugging memory we would unaccept it.

That is, acceptance does not happen at add_memory_resource() time, but 
when virtio-mem asks the device to transition a device block from 
unplugged<->plugged.

That also means that kexec is not a concern, because the device block 
state will reflect whether memory was accepted or not.

So far the theory :)

So it will be very different to DIMM-based hotplug handling.

---

## [27] David Hildenbrand (Red Hat) — 2025-12-01
*Subject: Re: [RFC PATCH 2/4] mm: Add support for unaccepted memory hotplug*

On 12/1/25 12:12, Borislav Petkov wrote:
> On Mon, Dec 01, 2025 at 10:18:37AM +0100, David Hildenbrand (Red Hat) wrote:
>> Makes sense to me, especially for confidential VMs where we pass such

I think we are in agreement: from what I recall, this software contract used to be
rather simple and stable.

Looking into the details, I guess it's all about

$ grep "define LINUX_EFI_" include/linux/efi.h
#define LINUX_EFI_CRASH_GUID                    EFI_GUID(0xcfc8fc79, 0xbe2e, 0x4ddc,  0x97, 0xf0, 0x9f, 0x98, 0xbf, 0xe2, 0x98, 0xa0)
#define LINUX_EFI_SCREEN_INFO_TABLE_GUID        EFI_GUID(0xe03fc20a, 0x85dc, 0x406e,  0xb9, 0x0e, 0x4a, 0xb5, 0x02, 0x37, 0x1d, 0x95)
#define LINUX_EFI_ARM_CPU_STATE_TABLE_GUID      EFI_GUID(0xef79e4aa, 0x3c3d, 0x4989,  0xb9, 0x02, 0x07, 0xa9, 0x43, 0xe5, 0x50, 0xd2)
#define LINUX_EFI_LOADER_ENTRY_GUID             EFI_GUID(0x4a67b082, 0x0a4c, 0x41cf,  0xb6, 0xc7, 0x44, 0x0b, 0x29, 0xbb, 0x8c, 0x4f)
#define LINUX_EFI_RANDOM_SEED_TABLE_GUID        EFI_GUID(0x1ce1e5bc, 0x7ceb, 0x42f2,  0x81, 0xe5, 0x8a, 0xad, 0xf1, 0x80, 0xf5, 0x7b)
#define LINUX_EFI_TPM_EVENT_LOG_GUID            EFI_GUID(0xb7799cb0, 0xeca2, 0x4943,  0x96, 0x67, 0x1f, 0xae, 0x07, 0xb7, 0x47, 0xfa)
#define LINUX_EFI_MEMRESERVE_TABLE_GUID         EFI_GUID(0x888eb0c6, 0x8ede, 0x4ff5,  0xa8, 0xf0, 0x9a, 0xee, 0x5c, 0xb9, 0x77, 0xc2)
#define LINUX_EFI_INITRD_MEDIA_GUID             EFI_GUID(0x5568e427, 0x68fc, 0x4f3d,  0xac, 0x74, 0xca, 0x55, 0x52, 0x31, 0xcc, 0x68)
#define LINUX_EFI_MOK_VARIABLE_TABLE_GUID       EFI_GUID(0xc451ed2b, 0x9694, 0x45d3,  0xba, 0xba, 0xed, 0x9f, 0x89, 0x88, 0xa3, 0x89)
#define LINUX_EFI_COCO_SECRET_AREA_GUID         EFI_GUID(0xadf956ad, 0xe98c, 0x484c,  0xae, 0x11, 0xb5, 0x1c, 0x7d, 0x33, 0x64, 0x47)
#define LINUX_EFI_BOOT_MEMMAP_GUID              EFI_GUID(0x800f683f, 0xd08b, 0x423a,  0xa2, 0x93, 0x96, 0x5c, 0x3c, 0x6f, 0xe2, 0xb4)
#define LINUX_EFI_UNACCEPTED_MEM_TABLE_GUID     EFI_GUID(0xd5d1de3c, 0x105c, 0x44f9,  0x9e, 0xa9, 0xbc, 0xef, 0x98, 0x12, 0x00, 0x31)
#define LINUX_EFI_LOADED_IMAGE_FIXED_GUID       EFI_GUID(0xf5a37b6d, 0x3344, 0x42a5,  0xb6, 0xbb, 0x97, 0x86, 0x48, 0xc1, 0x89, 0x0a)

Likely the format of these section stayed unchanged over the years.

---

## [28] David Hildenbrand (Red Hat) — 2025-12-01
*Subject: Re: [RFC PATCH 2/4] mm: Add support for unaccepted memory hotplug*

On 12/1/25 18:21, Pratik R. Sampat wrote:
> 
> 

BTW, can't we allocate the bitmap based on maximum memory in the system 
as indicated by e820 (which includes to-maybe-be-hotplugged-ranges) and 
not do this allocation during hotplug events?

If you search for max_possible_pfn / max_pfn I think you should find 
what I mean.

Then it would be a simple accept_memory().

---

## [29] Borislav Petkov — 2025-12-01
*Subject: Re: [RFC PATCH 2/4] mm: Add support for unaccepted memory hotplug*

On Mon, Dec 01, 2025 at 07:32:38PM +0100, David Hildenbrand (Red Hat) wrote:
> I think we are in agreement: from what I recall, this software contract used to be
> rather simple and stable.

Ok, please point me to the *explicit* document in our tree which says: "we
won't break the kernel and support kexec with any kernel version"?

Something ala Documentation/process/stable-api-nonsense.rst

Which says things like:

"Assuming that we had a stable kernel source interface for the kernel,
a binary interface would naturally happen too, right?  Wrong."

Which I read as a "no" to the kexec question too.

IOW, it is not about whether it works or not - it is about enforcing that.

---

## [30] Pratik R. Sampat — 2025-12-01
*Subject: Re: [RFC PATCH 2/4] mm: Add support for unaccepted memory hotplug*

On 12/1/25 12:36 PM, David Hildenbrand (Red Hat) wrote:
> On 12/1/25 18:21, Pratik R. Sampat wrote:
>>

Agreed, I think Kiryl was hinting at pre-allocated bitmaps as well.

Since, the overhead to do this upfront is fairly minimal, that should
certainly simplify things and have very little to no meddling with the
original EFI struct.

--Pratik

---

## [31] Pratik R. Sampat — 2025-12-01
*Subject: Re: [RFC PATCH 2/4] mm: Add support for unaccepted memory hotplug*

On 12/1/25 12:25 PM, David Hildenbrand (Red Hat) wrote:
> On 12/1/25 18:15, Pratik R. Sampat wrote:
>> Hi David,

Ah, I see. Thanks for clearing that up!

---

## [32] David Hildenbrand (Red Hat) — 2025-12-01
*Subject: Re: [RFC PATCH 2/4] mm: Add support for unaccepted memory hotplug*

On 12/1/25 20:10, Borislav Petkov wrote:
> On Mon, Dec 01, 2025 at 07:32:38PM +0100, David Hildenbrand (Red Hat) wrote:
>> I think we are in agreement: from what I recall, this software contract used to be

Just to be clear, I don't think it exist and also I don't think that it 
should exist.

> 
> Something ala Documentation/process/stable-api-nonsense.rst

Agreed.

---

## [33] Borislav Petkov — 2025-12-01
*Subject: Re: [RFC PATCH 2/4] mm: Add support for unaccepted memory hotplug*

On Mon, Dec 01, 2025 at 09:10:26PM +0100, David Hildenbrand (Red Hat) wrote:
> Just to be clear, I don't think it exist and also I don't think that it
> should exist.

By that logic if it doesn't exist and someone sends a patch, I should simply
ignore a review comment about that patch breaking some non-existent ABI and
simply take it.

Well, it certainly works for me.

Unless you folks come-a-runnin' later screaming it broke some use case of
yours. And then we're back to what I've been preaching on this thread from the
very beginning: having a common agreement on what ABI Linux enforces.

---

## [34] David Hildenbrand (Red Hat) — 2025-12-01
*Subject: Re: [RFC PATCH 2/4] mm: Add support for unaccepted memory hotplug*

On 12/1/25 21:25, Borislav Petkov wrote:
> On Mon, Dec 01, 2025 at 09:10:26PM +0100, David Hildenbrand (Red Hat) wrote:
>> Just to be clear, I don't think it exist and also I don't think that it

Well, we can always discuss and see if there is a way to not break a 
specific use case, independent of any ABI stability guarantees.

> 
> Well, it certainly works for me.

Heh, not me, but likely some of the CoCo folks regarding this specific 
use case (kexec in a confidential VM).

> And then we're back to what I've been preaching on this thread from the
> very beginning: having a common agreement on what ABI Linux enforces.

Right. Maybe Kiryl knows more about this specific case as he brought up that
these structures are versioned.

---

## [35] Kiryl Shutsemau — 2025-12-03
*Subject: Re: [RFC PATCH 2/4] mm: Add support for unaccepted memory hotplug*

On Mon, Dec 01, 2025 at 09:36:58PM +0100, David Hildenbrand (Red Hat) wrote:
> On 12/1/25 21:25, Borislav Petkov wrote:
> > On Mon, Dec 01, 2025 at 09:10:26PM +0100, David Hildenbrand (Red Hat) wrote:

There is also the #1 Kernel Rule: "we do not break users."

Booting a different version of the kernel is a core functionality of
kexec. It is widely used to deploy new kernels or revert to older ones.
Breaking this functionality is a show-stopper for most, if not all,
hyperscalers.

This specific change may not be a show-stopper as CoCo deployment is not
widespread enough to be noticed yet.

The notion that nobody promised that you can kexec into a different kernel
is absurd. It is used everywhere.

> > 
> > Well, it certainly works for me.

I am not involved in the deployment of CoCo VMs, but I don't believe it
is specifically about CoCo or the kexec ABI. I think it is more about
the boot protocol. Kexec is one way to boot the kernel.

Should we consider the EFI configuration tables format as part of the
boot protocol? I believe the answer is "yes," at least for some of them,
like LINUX_EFI_INITRD_MEDIA_GUID.

I also think LINUX_EFI_UNACCEPTED_MEM_TABLE_GUID should be considered in
the same way.

Ard, do you have any comments on this?

---

## [36] Rik van Riel — 2025-12-03
*Subject: Re: [RFC PATCH 2/4] mm: Add support for unaccepted memory hotplug*

On Fri, 2025-11-28 at 10:30 +0100, David Hildenbrand (Red Hat) wrote:
> On 11/27/25 19:12, Borislav Petkov wrote:
> > 

Even for kdump it is not unusual to use a different
kernel.

When working on kernel code, getting a proper crash
dump can really help figure out where my code went
wrong.

It helps if the kdump kernel doesn't have the same
broken code that my test kernel does :)

---

## [37] Borislav Petkov — 2025-12-03
*Subject: Re: [RFC PATCH 2/4] mm: Add support for unaccepted memory hotplug*

On Wed, Dec 03, 2025 at 02:46:23PM +0000, Kiryl Shutsemau wrote:
> There is also the #1 Kernel Rule: "we do not break users."

Do I need to point you to that too:

Documentation/process/stable-api-nonsense.rst

?

> Booting a different version of the kernel is a core functionality of
> kexec. It is widely used to deploy new kernels or revert to older ones.

Dude, can you please stop handwaving and say what you really wanna say: you
want different kernels to kexec. And it has worked so far but nothing
guarantees that. And we should all agree on some strategy going forward and
enforce it.

I don't care if different kernels can kexec or not. If I need to kexec, then
I simply build the same kernel.

So I'd take a patch which breaks that and when the submitter gets stopped by
you or someone else, I'll go tell him: "well, actually, I can't take your
patch because Kiryl said so but that's his opinion."

Do you see how absurd this is?!

Geez, I'm tired of typing the same shit over and over again on this thread.

Feel free to propose to make kexec'ing different kernels a rule and let's all
discuss it but let's stop this nonsense of what worked and so on. The kernel
gets complicated constantly, grows things here and there and without such
a rule, are you going to sit around and guard that kexec works?

Pfff.

> I am not involved in the deployment of CoCo VMs, but I don't believe it
> is specifically about CoCo or the kexec ABI. I think it is more about

You're basically proving my point: this needs to be discussed and agreed upon.
It doesn't matter if it used to work implicitly in the past.

Thx.

---

## [38] Pratik R. Sampat — 2025-12-09
*Subject: Re: [RFC PATCH 2/4] mm: Add support for unaccepted memory hotplug*

On 12/1/25 1:35 PM, Pratik R. Sampat wrote:
> 
> 

Taking another look at this suggestion, I think there may be more to it
than I previously thought. Parsing e820 tables to know what the range
are for allocating the bitmap to cover hotplug may be difficult. For e.g

[ 0.000000] efi: mem110: [Unaccepted <snip>] 
range=[0x0000000100000000-0x000000017fffffff] (2048MB)
[ 0.000000] efi: mem111: [Reserved   <snip>] 
range=[0x000000fd00000000-0x000000ffffffffff] (12288MB)

Parsing of the ACPI SRAT seems to be the one that gives us useful ranges
to base the upfront bitmap allocation on. e.g.
...
[    0.018357] ACPI: SRAT: Node 0 PXM 0 [mem 0x100000000-0x17fffffff]
[    0.018781] ACPI: SRAT: Node 0 PXM 0 [mem 0x180000000-0x2ffffffff] 
hotplug
This is also where max_possible_pfn gets updated to reflect this range.

One potential solution could be to parse the SRAT during unaccepted
memory bitmap allocation in the EFI stub. However, this would fragment
the implementation by duplicating the SRAT parsing. Alternatively, we
could keep the current approach of dynamically allocating the bitmap on
hotplug or I could also replace the entire memblock_reserved unaccepted
table like Kiryl suggested if we must absolutely avoid changing the
unaccepted structure?

--Pratik

---

## [39] Kiryl Shutsemau — 2025-12-11
*Subject: Re: [RFC PATCH 2/4] mm: Add support for unaccepted memory hotplug*

On Tue, Dec 09, 2025 at 03:36:09PM -0600, Pratik R. Sampat wrote:
> > Agreed, I think Kiryl was hinting at pre-allocated bitmaps as well.
> > 

Do I understand correctly that EFI memory map doesn't mention hot plug
range at all, but SRAT does?

That's a mess. I thought, all hotpluggable range supposed to be declared
in the memory map.

I wounder if it is what BIOS provides, or is it result of EFI memmap
cleanup by kernel? I see we are doing bunch of them, like in
efi_remove_e820_mmio().

> One potential solution could be to parse the SRAT during unaccepted
> memory bitmap allocation in the EFI stub. However, this would fragment

Other possible option would be to accept all memory on hotplug and don't
touch the bitmap at all. It might be not that bad: it doesn't block boot.
We can think of a better solution later, if needed.

---

## [40] Pratik R. Sampat — 2025-12-11
*Subject: Re: [RFC PATCH 2/4] mm: Add support for unaccepted memory hotplug*

On 12/11/25 9:00 AM, Kiryl Shutsemau wrote:
> On Tue, Dec 09, 2025 at 03:36:09PM -0600, Pratik R. Sampat wrote:
>>> Agreed, I think Kiryl was hinting at pre-allocated bitmaps as well.

Not an EFI expert by a long shot, but seems so.
EFI_MEMORY_HOT_PLUGGABLE attribute does exist for hot-removable regions
of memory that must not be used for allocation during the boot context.
However, I am unclear if this in principle is also supposed to span
the entire range or just the cold-plugged regions of memory.

> 
> I wounder if it is what BIOS provides, or is it result of EFI memmap

Absolutely, accepting memory as soon as it's added is easy.
Benchmarking it's effects may be a little tricky since unlike measuring
boot-time in eager vs lazy we may have to find representative workloads
to measure how much overheads accepting memory up-front adds.

Thanks
--Pratik

---
