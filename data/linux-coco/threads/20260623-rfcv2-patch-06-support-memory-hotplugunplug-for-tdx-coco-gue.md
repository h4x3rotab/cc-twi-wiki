---
title: '[RFCv2 PATCH 0/6] Support memory hotplug/unplug for TDX CoCo guests'
date: 2026-06-23
last_reply: 2026-06-25
message_count: 13
participants: ['Zhenzhong Duan', 'Kiryl Shutsemau', 'Pratik R. Sampat']
---

## [1] Zhenzhong Duan — 2026-06-23

This RFCv2 series implements comprehensive support for virtio-mem and ACPI
DIMM memory hotplug/unplug in Intel TDX confidential computing guests.
It explores the start-private memory approach utilizing the native
TDG.MEM.PAGE.RELEASE API.

We are seeking feedback from Kiryl on the CoCo guest implementation, MM
experts on DIMM & virio-mem memory hotplug integration and broader
virtio/CoCo community input on the overall approach. We are not seeking
x86 maintainer review at this stage.

== Changes from RFC v1 ==

- Eliminated callback infrastructure: Dropped plug callback and replaced
  unplug callback with platform-level unaccept function into core MM
  hotplug and virtio-mem subsystems.
- Added comprehensive bitmap tracking: Introduced a "plugged" bitmap
  alongside the unaccepted bitmap to track populated hotplug memory
  states to support load_unaligned_zeropad().
- Enhanced SRAT parsing: Extended the EFI stub to parse ACPI SRAT tables
  early, ensuring hotpluggable ranges are tracked from initial boot.

For more introduction about the background or other efforts in community,
please check the RFCv1 cover letter [1].

== Technical Approach ==

- Early SRAT Integration: A lightweight EFI stub parser scans ACPI SRAT
  tables to identify hotpluggable ranges and adjust bitmap boundaries
  early, avoiding the overhead of the full ACPI subsystem.
- Comprehensive Bitmap Tracking: Introduces a "plugged" bitmap right
  after the unaccepted bitmap. Both static and hotplugged memory are
  tracked, allowing the guest to map which ranges are populated by the
  VMM. This prevents acceptance beyond plugged memory boundaries due to
  load_unaligned_zeropad() operations.
- Platform Extensibility: Exposes generic CoCo memory interfaces. Other
  confidential platforms (like AMD SEV-SNP) can easily adopt this by
  hooking their specific mechanisms into arch_unaccept_memory().
- Hotplug & Guest Control: Integrates platform-level unaccept logic
  into ACPI hotplug and virtio-mem handlers. Uses TDG.MEM.PAGE.RELEASE
  for TDX to explicitly set memory to the "unaccepted" state during
  unplug, removing host hole-punching dependencies.
- Kexec Handover: Leverages existing EFI mechanisms to seamlessly hand
  over both the extended unaccepted bitmap and the new plugged bitmap
  across kexec boundaries.

== Testing ==

- dimm and virtio-mem memory hotplug/unplug
- lazy and eager accept
- kexec/kdump with hotplugged memory

This is tested with Marc-André Lureau's newest qemu series [2]

Comments appreciated, thanks.

Zhenzhong

[1] https://lore.kernel.org/all/20260604093551.1511079-1-zhenzhong.duan@intel.com/
[2] https://lore.kernel.org/all/20260604-rdm5-v5-0-5768e6a0943d@redhat.com/

Zhenzhong Duan (6):
  efi/unaccepted: Support hotplug memory in unaccepted bitmap via SRAT
  efi/unaccepted: Set unaccepted bits for all hotplug memory
  efi/unaccepted: Create plugged bitmap to support hotplug memory in
    coco guest
  x86/tdx: Implement arch_unaccept_memory()
  mm/memory_hotplug: Support ACPI hotplug/unplug for coco guest
  virtio-mem: Support memory hotplug/unplug for coco guest

 arch/x86/include/asm/shared/tdx.h             |   2 +
 arch/x86/include/asm/tdx.h                    |   2 +
 arch/x86/include/asm/unaccepted_memory.h      |  11 ++
 drivers/firmware/efi/libstub/efistub.h        |   6 +
 include/linux/efi.h                           |   5 +
 include/linux/mm.h                            |  11 ++
 arch/x86/boot/compressed/mem.c                |   4 +-
 arch/x86/coco/tdx/tdx.c                       | 120 ++++++++++++++++
 drivers/firmware/efi/efi.c                    |   4 +-
 .../firmware/efi/libstub/unaccepted_memory.c  | 128 +++++++++++++++++-
 drivers/firmware/efi/unaccepted_memory.c      | 122 ++++++++++++++++-
 drivers/virtio/virtio_mem.c                   |   8 ++
 mm/memory_hotplug.c                           |  16 +++
 13 files changed, 425 insertions(+), 14 deletions(-)

---

## [2] Zhenzhong Duan — 2026-06-23
*Subject: [RFCv2 PATCH 1/6] efi/unaccepted: Support hotplug memory in unaccepted bitmap via SRAT*

Currently, allocate_unaccepted_bitmap() only scans the initial EFI
boot memory map. This misses hotpluggable ranges described in the
ACPI SRAT. Without early tracking, hotplug pages are accessed without
acceptance and this triggers guest crash.

Introduce a lightweight ACPI SRAT parser to scan these regions early.
If a region has both ACPI_SRAT_MEM_ENABLED and ACPI_SRAT_MEM_HOT_PLUGGABLE
flags, expand the tracking boundaries. This avoids pulling in the full
ACPI subsystem while ensuring the bitmap covers both static memory and
hotplug memory.

Bail out early with success on non-confidential guests to prevent
unnecessary bitmap allocation.

Signed-off-by: Zhenzhong Duan <zhenzhong.duan@intel.com>
---
 drivers/firmware/efi/libstub/efistub.h        |  6 ++
 arch/x86/boot/compressed/mem.c                |  2 +-
 .../firmware/efi/libstub/unaccepted_memory.c  | 94 +++++++++++++++++++
 3 files changed, 101 insertions(+), 1 deletion(-)

diff --git a/drivers/firmware/efi/libstub/efistub.h b/drivers/firmware/efi/libstub/efistub.h
index fd91fc15ec81..fc0cd33a5962 100644
--- a/drivers/firmware/efi/libstub/efistub.h
+++ b/drivers/firmware/efi/libstub/efistub.h
@@ -1260,4 +1260,10 @@ void arch_accept_memory(phys_addr_t start, phys_addr_t end);
 efi_status_t efi_zboot_decompress_init(unsigned long *alloc_size);
 efi_status_t efi_zboot_decompress(u8 *out, unsigned long outlen);
 
+bool early_is_tdx_guest(void);
+#ifdef CONFIG_AMD_MEM_ENCRYPT
+bool early_is_sevsnp_guest(void);
+#else
+static inline bool early_is_sevsnp_guest(void) { return false; }
+#endif
 #endif
diff --git a/arch/x86/boot/compressed/mem.c b/arch/x86/boot/compressed/mem.c
index 0e9f84ab4bdc..40e9c81a2206 100644
--- a/arch/x86/boot/compressed/mem.c
+++ b/arch/x86/boot/compressed/mem.c
@@ -12,7 +12,7 @@
  *
  * Enumerate TDX directly from the early users.
  */
-static bool early_is_tdx_guest(void)
+bool early_is_tdx_guest(void)
 {
 	static bool once;
 	static bool is_tdx;
diff --git a/drivers/firmware/efi/libstub/unaccepted_memory.c b/drivers/firmware/efi/libstub/unaccepted_memory.c
index 757dbe734a47..bfbb78bd7b8a 100644
--- a/drivers/firmware/efi/libstub/unaccepted_memory.c
+++ b/drivers/firmware/efi/libstub/unaccepted_memory.c
@@ -1,19 +1,109 @@
 // SPDX-License-Identifier: GPL-2.0-only
 
 #include <linux/efi.h>
+#include <linux/acpi.h>
 #include <asm/efi.h>
 #include "efistub.h"
 
 struct efi_unaccepted_memory *unaccepted_table;
 
+struct srat_parse_ctx {
+	u64 *mem_start;
+	u64 *mem_end;
+};
+
+typedef void (*srat_region_handler_t)(struct acpi_srat_mem_affinity *mem,
+				      struct srat_parse_ctx *ctx);
+
+/*
+ * parse_acpi_srat_regions - Loop through ACPI SRAT tables to process
+ * hotpluggable memory regions via a custom callback handler.
+ */
+static void parse_acpi_srat_regions(srat_region_handler_t handler, struct srat_parse_ctx *ctx)
+{
+	u32 hotplug_mask = ACPI_SRAT_MEM_ENABLED | ACPI_SRAT_MEM_HOT_PLUGGABLE;
+	struct acpi_table_header *xsdt, *srat = NULL;
+	struct acpi_table_rsdp *rsdp = NULL;
+	u8 *current_ptr, *end_ptr;
+	u64 *table_pointers;
+	u32 entry_count;
+	unsigned long i;
+
+	rsdp = get_efi_config_table(ACPI_20_TABLE_GUID);
+
+	if (!rsdp || !ACPI_VALIDATE_RSDP_SIG(rsdp->signature))
+		return;
+
+	xsdt = (struct acpi_table_header *)(unsigned long)rsdp->xsdt_physical_address;
+	if (!xsdt || !ACPI_COMPARE_NAMESEG(xsdt->signature, ACPI_SIG_XSDT))
+		return;
+
+	if (xsdt->length < sizeof(struct acpi_table_header) + ACPI_XSDT_ENTRY_SIZE)
+		return;
+
+	entry_count = (xsdt->length - sizeof(struct acpi_table_header)) / ACPI_XSDT_ENTRY_SIZE;
+	table_pointers = (u64 *)((u8 *)xsdt + sizeof(struct acpi_table_header));
+
+	for (i = 0; i < entry_count; i++) {
+		struct acpi_table_header *tbl;
+
+		tbl = (struct acpi_table_header *)(unsigned long)table_pointers[i];
+		if (tbl && ACPI_COMPARE_NAMESEG(tbl->signature, ACPI_SIG_SRAT)) {
+			srat = tbl;
+			break;
+		}
+	}
+
+	if (!srat)
+		return;
+
+	current_ptr = (u8 *)srat + sizeof(struct acpi_table_srat);
+	end_ptr = (u8 *)srat + srat->length;
+
+	while (current_ptr < end_ptr) {
+		struct acpi_subtable_header *sub_header;
+		u64 range_end;
+
+		sub_header = (struct acpi_subtable_header *)current_ptr;
+		if (sub_header->length == 0)
+			break;
+
+		if (sub_header->type == ACPI_SRAT_TYPE_MEMORY_AFFINITY &&
+		    sub_header->length >= sizeof(struct acpi_srat_mem_affinity)) {
+			struct acpi_srat_mem_affinity *mem;
+
+			mem = (struct acpi_srat_mem_affinity *)current_ptr;
+			if ((mem->flags & hotplug_mask) == hotplug_mask &&
+			    !check_add_overflow(mem->base_address, mem->length, &range_end))
+				handler(mem, ctx);
+		}
+		current_ptr += sub_header->length;
+	}
+}
+
+static void update_mem_boundaries(struct acpi_srat_mem_affinity *mem, struct srat_parse_ctx *ctx)
+{
+	u64 range_end = mem->base_address + mem->length;
+
+	if (mem->base_address < *(ctx->mem_start))
+		*(ctx->mem_start) = mem->base_address;
+
+	if (range_end > *(ctx->mem_end))
+		*(ctx->mem_end) = range_end;
+}
+
 efi_status_t allocate_unaccepted_bitmap(__u32 nr_desc,
 					struct efi_boot_memmap *map)
 {
 	efi_guid_t unaccepted_table_guid = LINUX_EFI_UNACCEPTED_MEM_TABLE_GUID;
 	u64 unaccepted_start = ULLONG_MAX, unaccepted_end = 0, bitmap_size;
+	struct srat_parse_ctx ctx;
 	efi_status_t status;
 	int i;
 
+	if (!early_is_tdx_guest() && !early_is_sevsnp_guest())
+		return EFI_SUCCESS;
+
 	/* Check if the table is already installed */
 	unaccepted_table = get_efi_config_table(unaccepted_table_guid);
 	if (unaccepted_table) {
@@ -38,6 +128,10 @@ efi_status_t allocate_unaccepted_bitmap(__u32 nr_desc,
 				     d->phys_addr + d->num_pages * PAGE_SIZE);
 	}
 
+	ctx.mem_start = &unaccepted_start;
+	ctx.mem_end = &unaccepted_end;
+	parse_acpi_srat_regions(update_mem_boundaries, &ctx);
+
 	if (unaccepted_start == ULLONG_MAX)
 		return EFI_SUCCESS;

---

## [3] Zhenzhong Duan — 2026-06-23
*Subject: [RFCv2 PATCH 2/6] efi/unaccepted: Set unaccepted bits for all hotplug memory*

In coco guests, hotpluggable memory ranges are initially unaccepted.
While a previous change expanded the unaccepted memory bitmap boundaries
to include these hotplug spaces, the actual bits inside the bitmap are
not yet marked as unaccepted.

Walks SRAT a second time after the bitmap is allocated and sets the bits
corresponding to hotpluggable ranges.

This ensures the bitmap state accurately reflects all static and hotplug
memory ranges before booting kernel.

Signed-off-by: Zhenzhong Duan <zhenzhong.duan@intel.com>
---
 .../firmware/efi/libstub/unaccepted_memory.c   | 18 ++++++++++++++++++
 1 file changed, 18 insertions(+)

diff --git a/drivers/firmware/efi/libstub/unaccepted_memory.c b/drivers/firmware/efi/libstub/unaccepted_memory.c
index bfbb78bd7b8a..01bed8e751ca 100644
--- a/drivers/firmware/efi/libstub/unaccepted_memory.c
+++ b/drivers/firmware/efi/libstub/unaccepted_memory.c
@@ -92,6 +92,23 @@ static void update_mem_boundaries(struct acpi_srat_mem_affinity *mem, struct sra
 		*(ctx->mem_end) = range_end;
 }
 
+static void mark_hotplug_memory_unaccepted(struct acpi_srat_mem_affinity *mem,
+					   struct srat_parse_ctx *ctx)
+{
+	u64 unit_size = unaccepted_table->unit_size;
+	u64 start, end;
+
+	start = round_up(mem->base_address, unit_size);
+	end = round_down(mem->base_address + mem->length, unit_size);
+
+	/* Translate to offsets from the beginning of the bitmap */
+	start -= unaccepted_table->phys_base;
+	end -= unaccepted_table->phys_base;
+
+	bitmap_set(unaccepted_table->bitmap,
+		   start / unit_size, (end - start) / unit_size);
+}
+
 efi_status_t allocate_unaccepted_bitmap(__u32 nr_desc,
 					struct efi_boot_memmap *map)
 {
@@ -169,6 +186,7 @@ efi_status_t allocate_unaccepted_bitmap(__u32 nr_desc,
 	unaccepted_table->phys_base = unaccepted_start;
 	unaccepted_table->size = bitmap_size;
 	memset(unaccepted_table->bitmap, 0, bitmap_size);
+	parse_acpi_srat_regions(mark_hotplug_memory_unaccepted, &ctx);
 
 	status = efi_bs_call(install_configuration_table,
 			     &unaccepted_table_guid, unaccepted_table);

---

## [4] Zhenzhong Duan — 2026-06-23
*Subject: [RFCv2 PATCH 3/6] efi/unaccepted: Create plugged bitmap to support hotplug memory in coco guest*

The load_unaligned_zeropad() function can cause unintended memory loads
across page boundaries. To safely handle these unaligned reads in a
confidential computing guest, the kernel implicitly accepts an extra
unit_size block of memory to serve as a safety guard.

However, near hotplug boundaries, this extra acceptance can fall within
unpopulated gaps between hotplugged memory ranges, triggering a guest
kernel crash.

To protect these boundaries against out-of-bounds access, introduce a
"plugged" bitmap positioned immediately following the unaccepted memory
bitmap.

Initial static boot memory ranges have their corresponding bits marked
as plugged by default during early initialization. For hotpluggable
memory ranges, the memory driver must explicitly set the proper bits
when a memory block is plugged, and clear them upon an unplug event.

Update accept_memory() and range_contains_unaccepted_memory() to check
the intersection of both bitmaps. The kernel now combines them to
determine exactly which plugged, unaccepted pages require acceptance.

Additionally, bump the unaccepted memory table layout version from 1
to 2. This strict layout enforcement guarantees that a version 1 table
passed to a new kernel, or a version 2 table passed to an old kernel,
will explicitly fail kexec early due to the version mismatch.

Signed-off-by: Zhenzhong Duan <zhenzhong.duan@intel.com>
---
 include/linux/efi.h                           |  5 ++++
 arch/x86/boot/compressed/mem.c                |  2 +-
 drivers/firmware/efi/efi.c                    |  4 +--
 .../firmware/efi/libstub/unaccepted_memory.c  | 16 +++++++----
 drivers/firmware/efi/unaccepted_memory.c      | 28 +++++++++++++++----
 5 files changed, 42 insertions(+), 13 deletions(-)

diff --git a/include/linux/efi.h b/include/linux/efi.h
index ccbc35479684..579d102f128a 100644
--- a/include/linux/efi.h
+++ b/include/linux/efi.h
@@ -551,6 +551,11 @@ struct efi_unaccepted_memory {
 	unsigned long bitmap[];
 };
 
+static inline void *plugged_bitmap_of(struct efi_unaccepted_memory *u)
+{
+	return (void *)u->bitmap + u->size;
+}
+
 /*
  * Architecture independent structure for describing a memory map for the
  * benefit of efi_memmap_init_early(), and for passing context between
diff --git a/arch/x86/boot/compressed/mem.c b/arch/x86/boot/compressed/mem.c
index 40e9c81a2206..61b8d0edd2f6 100644
--- a/arch/x86/boot/compressed/mem.c
+++ b/arch/x86/boot/compressed/mem.c
@@ -69,7 +69,7 @@ bool init_unaccepted_memory(void)
 	if (!table)
 		return false;
 
-	if (table->version != 1)
+	if (table->version != 2)
 		error("Unknown version of unaccepted memory table\n");
 
 	/*
diff --git a/drivers/firmware/efi/efi.c b/drivers/firmware/efi/efi.c
index 318d1cc9a066..7f7341634c13 100644
--- a/drivers/firmware/efi/efi.c
+++ b/drivers/firmware/efi/efi.c
@@ -701,7 +701,7 @@ static __init void reserve_unaccepted(struct efi_unaccepted_memory *unaccepted)
 	phys_addr_t start, end;
 
 	start = PAGE_ALIGN_DOWN(efi.unaccepted);
-	end = PAGE_ALIGN(efi.unaccepted + sizeof(*unaccepted) + unaccepted->size);
+	end = PAGE_ALIGN(efi.unaccepted + sizeof(*unaccepted) + unaccepted->size * 2);
 
 	memblock_add(start, end - start);
 	memblock_reserve(start, end - start);
@@ -837,7 +837,7 @@ int __init efi_config_parse_tables(const efi_config_table_t *config_tables,
 		unaccepted = early_memremap(efi.unaccepted, sizeof(*unaccepted));
 		if (unaccepted) {
 
-			if (unaccepted->version == 1) {
+			if (unaccepted->version == 2) {
 				reserve_unaccepted(unaccepted);
 			} else {
 				efi.unaccepted = EFI_INVALID_TABLE_ADDR;
diff --git a/drivers/firmware/efi/libstub/unaccepted_memory.c b/drivers/firmware/efi/libstub/unaccepted_memory.c
index 01bed8e751ca..5b0deb6c91f1 100644
--- a/drivers/firmware/efi/libstub/unaccepted_memory.c
+++ b/drivers/firmware/efi/libstub/unaccepted_memory.c
@@ -113,7 +113,7 @@ efi_status_t allocate_unaccepted_bitmap(__u32 nr_desc,
 					struct efi_boot_memmap *map)
 {
 	efi_guid_t unaccepted_table_guid = LINUX_EFI_UNACCEPTED_MEM_TABLE_GUID;
-	u64 unaccepted_start = ULLONG_MAX, unaccepted_end = 0, bitmap_size;
+	u64 unaccepted_start = ULLONG_MAX, unaccepted_end = 0, bitmap_size, total_size;
 	struct srat_parse_ctx ctx;
 	efi_status_t status;
 	int i;
@@ -124,7 +124,7 @@ efi_status_t allocate_unaccepted_bitmap(__u32 nr_desc,
 	/* Check if the table is already installed */
 	unaccepted_table = get_efi_config_table(unaccepted_table_guid);
 	if (unaccepted_table) {
-		if (unaccepted_table->version != 1) {
+		if (unaccepted_table->version != 2) {
 			efi_err("Unknown version of unaccepted memory table\n");
 			return EFI_UNSUPPORTED;
 		}
@@ -173,19 +173,22 @@ efi_status_t allocate_unaccepted_bitmap(__u32 nr_desc,
 	bitmap_size = DIV_ROUND_UP(unaccepted_end - unaccepted_start,
 				   EFI_UNACCEPTED_UNIT_SIZE * BITS_PER_BYTE);
 
+	/* There is a plugged bitmap after unaccepted bitmap */
+	total_size = bitmap_size << 1;
+
 	status = efi_bs_call(allocate_pool, EFI_ACPI_RECLAIM_MEMORY,
-			     sizeof(*unaccepted_table) + bitmap_size,
+			     sizeof(*unaccepted_table) + total_size,
 			     (void **)&unaccepted_table);
 	if (status != EFI_SUCCESS) {
 		efi_err("Failed to allocate unaccepted memory config table\n");
 		return status;
 	}
 
-	unaccepted_table->version = 1;
+	unaccepted_table->version = 2;
 	unaccepted_table->unit_size = EFI_UNACCEPTED_UNIT_SIZE;
 	unaccepted_table->phys_base = unaccepted_start;
 	unaccepted_table->size = bitmap_size;
-	memset(unaccepted_table->bitmap, 0, bitmap_size);
+	memset(unaccepted_table->bitmap, 0, total_size);
 	parse_acpi_srat_regions(mark_hotplug_memory_unaccepted, &ctx);
 
 	status = efi_bs_call(install_configuration_table,
@@ -287,6 +290,9 @@ void process_unaccepted_memory(u64 start, u64 end)
 	 */
 	bitmap_set(unaccepted_table->bitmap,
 		   start / unit_size, (end - start) / unit_size);
+	/* Set plugged bits for static memory and never unset */
+	bitmap_set(plugged_bitmap_of(unaccepted_table),
+		   start / unit_size, (end - start) / unit_size);
 }
 
 void accept_memory(phys_addr_t start, unsigned long size)
diff --git a/drivers/firmware/efi/unaccepted_memory.c b/drivers/firmware/efi/unaccepted_memory.c
index 4a8ec8d6a571..c290b16c5142 100644
--- a/drivers/firmware/efi/unaccepted_memory.c
+++ b/drivers/firmware/efi/unaccepted_memory.c
@@ -38,6 +38,7 @@ void accept_memory(phys_addr_t start, unsigned long size)
 	unsigned long flags;
 	phys_addr_t end;
 	u64 unit_size;
+	void *plugged_bitmap;
 
 	unaccepted = efi_get_unaccepted_table();
 	if (!unaccepted)
@@ -126,12 +127,23 @@ void accept_memory(phys_addr_t start, unsigned long size)
 	 */
 	list_add(&range.list, &accepting_list);
 
-	range_start = range.start;
-	for_each_set_bitrange_from(range_start, range_end, unaccepted->bitmap,
-				   range.end) {
+	plugged_bitmap = plugged_bitmap_of(unaccepted);
+
+	for (range_start = range.start; range_start < range.end; range_start = range_end) {
 		unsigned long phys_start, phys_end;
-		unsigned long len = range_end - range_start;
+		unsigned long len;
+		unsigned long unaccepted_zero, plugged_zero;
+
+		range_start = find_next_and_bit(plugged_bitmap, unaccepted->bitmap,
+						range.end, range_start);
+
+		if (range_start >= range.end)
+			break;
 
+		unaccepted_zero = find_next_zero_bit(unaccepted->bitmap, range.end, range_start);
+		plugged_zero = find_next_zero_bit(plugged_bitmap, range.end, range_start);
+		range_end = min(unaccepted_zero, plugged_zero);
+		len = range_end - range_start;
 		phys_start = range_start * unit_size + unaccepted->phys_base;
 		phys_end = range_end * unit_size + unaccepted->phys_base;
 
@@ -167,6 +179,7 @@ bool range_contains_unaccepted_memory(phys_addr_t start, unsigned long size)
 	bool ret = false;
 	phys_addr_t end;
 	u64 unit_size;
+	void *plugged_bitmap;
 
 	unaccepted = efi_get_unaccepted_table();
 	if (!unaccepted)
@@ -201,9 +214,14 @@ bool range_contains_unaccepted_memory(phys_addr_t start, unsigned long size)
 	if (end > unaccepted->size * unit_size * BITS_PER_BYTE)
 		end = unaccepted->size * unit_size * BITS_PER_BYTE;
 
+	plugged_bitmap = plugged_bitmap_of(unaccepted);
+
 	spin_lock_irqsave(&unaccepted_memory_lock, flags);
 	while (start < end) {
-		if (test_bit(start / unit_size, unaccepted->bitmap)) {
+		unsigned long range_start = start / unit_size;
+
+		if (test_bit(range_start, plugged_bitmap) &&
+		    test_bit(range_start, unaccepted->bitmap)) {
 			ret = true;
 			break;
 		}

---

## [5] Zhenzhong Duan — 2026-06-23
*Subject: [RFCv2 PATCH 4/6] x86/tdx: Implement arch_unaccept_memory()*

During memory hot-unplug, if the VMM does not punch hole the memory, the
memory stays in "accepted" state. Consequently, subsequent re-acceptance
of that same memory during a re-plug operation will trigger re-accept
failure. To guard this, a confidential guest must maintain control of
the memory state explicitly, e.g., setting memory to "unaccepted" state
during unplug.

In the context of TDX, the "unaccepted" state maps to the PENDING state,
while the "accepted" state maps to the MAPPED state. Implement
arch_unaccept_memory() for TDX guest via the TDG.MEM.PAGE.RELEASE TDCALL.
It uses 1G/2M/4K page size fallbacks and rolls back on partial failure. A
failure during this rollback step indicates severe corruption of the TDX
module state and triggers a kernel panic.

Signed-off-by: Zhenzhong Duan <zhenzhong.duan@intel.com>
---
 arch/x86/include/asm/shared/tdx.h        |   2 +
 arch/x86/include/asm/tdx.h               |   2 +
 arch/x86/include/asm/unaccepted_memory.h |  11 +++
 arch/x86/coco/tdx/tdx.c                  | 120 +++++++++++++++++++++++
 4 files changed, 135 insertions(+)

diff --git a/arch/x86/include/asm/shared/tdx.h b/arch/x86/include/asm/shared/tdx.h
index 049638e3da74..910ec1e57528 100644
--- a/arch/x86/include/asm/shared/tdx.h
+++ b/arch/x86/include/asm/shared/tdx.h
@@ -19,6 +19,7 @@
 #define TDG_MEM_PAGE_ACCEPT		6
 #define TDG_VM_RD			7
 #define TDG_VM_WR			8
+#define TDG_MEM_PAGE_RELEASE		30
 
 /* TDX TD attributes */
 #define TDX_TD_ATTR_DEBUG_BIT		0
@@ -54,6 +55,7 @@
 
 /* TDCS_CONFIG_FLAGS bits */
 #define TDCS_CONFIG_FLEXIBLE_PENDING_VE	BIT_ULL(1)
+#define TDCS_CONFIG_PAGE_RELEASE	BIT_ULL(6)
 
 /* TDCS_TD_CTLS bits */
 #define TD_CTLS_PENDING_VE_DISABLE_BIT	0
diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index a149740b24e8..8608d33a7db6 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -72,6 +72,8 @@ int tdx_mcall_extend_rtmr(u8 index, u8 *data);
 
 u64 tdx_hcall_get_quote(u8 *buf, size_t size);
 
+bool tdx_unaccept_memory(phys_addr_t start, phys_addr_t end);
+
 void __init tdx_dump_attributes(u64 td_attr);
 void __init tdx_dump_td_ctls(u64 td_ctls);
 
diff --git a/arch/x86/include/asm/unaccepted_memory.h b/arch/x86/include/asm/unaccepted_memory.h
index f5937e9866ac..9fd9411d2c44 100644
--- a/arch/x86/include/asm/unaccepted_memory.h
+++ b/arch/x86/include/asm/unaccepted_memory.h
@@ -18,6 +18,17 @@ static inline void arch_accept_memory(phys_addr_t start, phys_addr_t end)
 	}
 }
 
+static inline void arch_unaccept_memory(phys_addr_t start, phys_addr_t end)
+{
+	/* Platform-specific memory-unacceptance call goes here */
+	if (cpu_feature_enabled(X86_FEATURE_TDX_GUEST)) {
+		if (!tdx_unaccept_memory(start, end))
+			panic("TDX: Failed to unaccept memory\n");
+	} else {
+		panic("Cannot unaccept memory: unknown platform\n");
+	}
+}
+
 static inline struct efi_unaccepted_memory *efi_get_unaccepted_table(void)
 {
 	if (efi.unaccepted == EFI_INVALID_TABLE_ADDR)
diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 186915a17c50..1bab8f4687bf 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -326,6 +326,124 @@ static void reduce_unnecessary_ve(void)
 	enable_cpu_topology_enumeration();
 }
 
+static bool tdx_page_release_supported;
+
+static void tdx_detect_page_release_support(void)
+{
+	u64 config = 0;
+
+	tdg_vm_rd(TDCS_CONFIG_FLAGS, &config);
+
+	tdx_page_release_supported = !!(config & TDCS_CONFIG_PAGE_RELEASE);
+}
+
+static unsigned long try_release_one(phys_addr_t start, unsigned long len,
+				     enum pg_level pg_level)
+{
+	unsigned long release_size = page_level_size(pg_level);
+	struct tdx_module_args args = {};
+	u8 page_size;
+	u64 ret;
+
+	if (!IS_ALIGNED(start, release_size))
+		return 0;
+
+	if (len < release_size)
+		return 0;
+
+	/*
+	 * Pass the page physical address to TDX module to release the
+	 * private page and to put it in PENDING state.
+	 *
+	 * Encode page size in RCX[2:0] using TDX_PS_*
+	 */
+	switch (pg_level) {
+	case PG_LEVEL_4K:
+		page_size = TDX_PS_4K;
+		break;
+	case PG_LEVEL_2M:
+		page_size = TDX_PS_2M;
+		break;
+	case PG_LEVEL_1G:
+		page_size = TDX_PS_1G;
+		break;
+	default:
+		return 0;
+	}
+
+	args.rcx = start | page_size;
+	ret = __tdcall(TDG_MEM_PAGE_RELEASE, &args);
+	if (ret)
+		return 0;
+
+	return release_size;
+}
+
+static bool tdx_release_memory(phys_addr_t start, phys_addr_t end, phys_addr_t *cur)
+{
+	*cur = start;
+
+	while (*cur < end) {
+		unsigned long len = end - *cur;
+		unsigned long release_size;
+
+		/*
+		 * Try larger release first. It speeds up process by cutting
+		 * number of hypercalls (if successful).
+		 */
+
+		release_size = try_release_one(*cur, len, PG_LEVEL_1G);
+		if (!release_size)
+			release_size = try_release_one(*cur, len, PG_LEVEL_2M);
+		if (!release_size)
+			release_size = try_release_one(*cur, len, PG_LEVEL_4K);
+		if (!release_size)
+			return false;
+		*cur += release_size;
+	}
+
+	return true;
+}
+
+/**
+ * Release private memory and put it in PENDING state.
+ *
+ * @start: Physical start address of memory range to release
+ * @end:   Physical end address of memory range to release
+ *
+ * Uses TDG.MEM.PAGE.RELEASE TDCALL to transition private pages back to
+ * PENDING state. If PAGE_RELEASE is not supported by the TDX
+ * configuration, returns true (success) as no action is needed.
+ *
+ * On partial failure, automatically re-accepts any successfully released
+ * pages to restore consistent memory state. Re-acceptance failure is
+ * treated as a fatal error since it indicates severe TDX module issues.
+ *
+ * Returns: true on success, false on failure
+ */
+bool tdx_unaccept_memory(phys_addr_t start, phys_addr_t end)
+{
+	phys_addr_t released = start;
+	bool ret;
+
+	if (!tdx_page_release_supported)
+		return true;
+
+	ret = tdx_release_memory(start, end, &released);
+	if (!ret) {
+		pr_err("Failed to unaccept memory [%pa, %pa)\n", &start, &end);
+		/*
+		 * Re-accept any pages that were successfully released before
+		 * the failure occurred. This should never fail since we're
+		 * just restoring the previous MAPPED state.
+		 */
+		if (!tdx_accept_memory(start, released))
+			panic("%s: Failed to re-accept memory\n", __func__);
+	}
+
+	return ret;
+}
+
 static void tdx_setup(u64 *cc_mask)
 {
 	struct tdx_module_args args = {};
@@ -359,6 +477,8 @@ static void tdx_setup(u64 *cc_mask)
 	disable_sept_ve(td_attr);
 
 	reduce_unnecessary_ve();
+
+	tdx_detect_page_release_support();
 }
 
 /*

---

## [6] Zhenzhong Duan — 2026-06-23
*Subject: [RFCv2 PATCH 5/6] mm/memory_hotplug: Support ACPI hotplug/unplug for coco guest*

Integrate coco memory management operations into the core memory hotplug
subsystem to handle the lifecycle of hotplug memory.

In add_memory_resource(), invoke coco_set_plugged_bitmap(..., true) to mark
memory plugged before adding the memory block, because self hosted memmap
initialization needs their plugged bits set before acceptance. There is no
explicit call to accept_memory() for normal pages, because they can be
lazily accepted by the core memory management subsystem after the memory
block is onlined.

In try_remove_memory(), before finalizing the physical removal of the
memory blocks, invoke unaccept_memory(). This allows the guest to take
direct control of its own memory state and release the pages itself,
eliminating the dependency on the VMM to implicitly hole-punch the memory.
It loops through the targeted ranges using find_next_andnot_bit(), matching
pages that are marked plugged and accepted, and releases them back to the
host. Following the unacceptance step, clear the ranges from the plugged
bitmap.

These operations guarantee that both the unaccepted and plugged tracking
states stay completely synchronized with the actual dynamic memory
configurations of the guest.

Signed-off-by: Zhenzhong Duan <zhenzhong.duan@intel.com>
---
 include/linux/mm.h                       | 11 +++
 drivers/firmware/efi/unaccepted_memory.c | 94 ++++++++++++++++++++++++
 mm/memory_hotplug.c                      | 16 ++++
 3 files changed, 121 insertions(+)

diff --git a/include/linux/mm.h b/include/linux/mm.h
index fc2acedf0b76..4c094038872a 100644
--- a/include/linux/mm.h
+++ b/include/linux/mm.h
@@ -5105,6 +5105,8 @@ int set_anon_vma_name(unsigned long addr, unsigned long size,
 
 bool range_contains_unaccepted_memory(phys_addr_t start, unsigned long size);
 void accept_memory(phys_addr_t start, unsigned long size);
+void unaccept_memory(phys_addr_t start, unsigned long size);
+int coco_set_plugged_bitmap(phys_addr_t start, unsigned long size, bool set);
 
 #else
 
@@ -5118,6 +5120,15 @@ static inline void accept_memory(phys_addr_t start, unsigned long size)
 {
 }
 
+static inline void unaccept_memory(phys_addr_t start, unsigned long size)
+{
+}
+
+static inline int coco_set_plugged_bitmap(phys_addr_t start, unsigned long size, bool set)
+{
+	return 0;
+}
+
 #endif
 
 static inline bool pfn_is_unaccepted_memory(unsigned long pfn)
diff --git a/drivers/firmware/efi/unaccepted_memory.c b/drivers/firmware/efi/unaccepted_memory.c
index c290b16c5142..f35f7016af53 100644
--- a/drivers/firmware/efi/unaccepted_memory.c
+++ b/drivers/firmware/efi/unaccepted_memory.c
@@ -233,6 +233,100 @@ bool range_contains_unaccepted_memory(phys_addr_t start, unsigned long size)
 	return ret;
 }
 
+static int coco_hotplug_range_check(struct efi_unaccepted_memory *unaccepted,
+				    phys_addr_t start, unsigned long size)
+{
+	u64 unit_size = unaccepted->unit_size;
+	u64 phys_base = unaccepted->phys_base;
+	u64 phys_end = phys_base + unaccepted->size * unit_size * BITS_PER_BYTE;
+
+	if (!IS_ALIGNED(start | size, unit_size))
+		return -EINVAL;
+
+	if (start < phys_base || start + size > phys_end)
+		return -EINVAL;
+
+	return 0;
+}
+
+/* Only used by hotplug memory, we don't unaccept static memory */
+void unaccept_memory(phys_addr_t start, unsigned long size)
+{
+	unsigned long range_start, range_end, bitmap_size, flags;
+	struct efi_unaccepted_memory *unaccepted;
+	void *plugged_bitmap;
+	u64 unit_size;
+
+	unaccepted = efi_get_unaccepted_table();
+	if (!unaccepted)
+		return;
+
+	if (WARN_ON(coco_hotplug_range_check(unaccepted, start, size)))
+		return;
+
+	unit_size = unaccepted->unit_size;
+	range_start = (start - unaccepted->phys_base) / unit_size;
+	bitmap_size = range_start + size / unit_size;
+	plugged_bitmap = plugged_bitmap_of(unaccepted);
+
+	spin_lock_irqsave(&unaccepted_memory_lock, flags);
+	for (; range_start < bitmap_size; range_start = range_end) {
+		unsigned long phys_start, phys_end;
+		unsigned long unaccepted_one, plugged_zero;
+
+		range_start = find_next_andnot_bit(plugged_bitmap, unaccepted->bitmap,
+						   bitmap_size, range_start);
+
+		if (range_start >= bitmap_size)
+			break;
+
+		unaccepted_one = find_next_bit(unaccepted->bitmap, bitmap_size, range_start);
+		plugged_zero = find_next_zero_bit(plugged_bitmap, bitmap_size, range_start);
+		range_end = min(unaccepted_one, plugged_zero);
+
+		phys_start = range_start * unit_size + unaccepted->phys_base;
+		phys_end = range_end * unit_size + unaccepted->phys_base;
+
+		arch_unaccept_memory(phys_start, phys_end);
+		bitmap_set(unaccepted->bitmap, range_start, range_end - range_start);
+	}
+	spin_unlock_irqrestore(&unaccepted_memory_lock, flags);
+}
+
+/*
+ * Only used by hotplug memory, plugged bits of static memory are handled
+ * in process_unaccepted_memory()
+ */
+int coco_set_plugged_bitmap(phys_addr_t start, unsigned long size, bool set)
+{
+	struct efi_unaccepted_memory *unaccepted;
+	unsigned long range_start, flags;
+	void *plugged_bitmap;
+	u64 unit_size;
+	int ret;
+
+	unaccepted = efi_get_unaccepted_table();
+	if (!unaccepted)
+		return 0;
+
+	ret = coco_hotplug_range_check(unaccepted, start, size);
+	if (ret)
+		return ret;
+
+	unit_size = unaccepted->unit_size;
+	range_start = (start - unaccepted->phys_base) / unit_size;
+	plugged_bitmap = plugged_bitmap_of(unaccepted);
+
+	spin_lock_irqsave(&unaccepted_memory_lock, flags);
+	if (set)
+		bitmap_set(plugged_bitmap, range_start, size / unit_size);
+	else
+		bitmap_clear(plugged_bitmap, range_start, size / unit_size);
+	spin_unlock_irqrestore(&unaccepted_memory_lock, flags);
+
+	return 0;
+}
+
 #ifdef CONFIG_PROC_VMCORE
 static bool unaccepted_memory_vmcore_pfn_is_ram(struct vmcore_cb *cb,
 						unsigned long pfn)
diff --git a/mm/memory_hotplug.c b/mm/memory_hotplug.c
index 40c7915dabe0..2f71514a0616 100644
--- a/mm/memory_hotplug.c
+++ b/mm/memory_hotplug.c
@@ -1429,6 +1429,8 @@ static void remove_memory_blocks_and_altmaps(u64 start, u64 size)
 
 		arch_remove_memory(cur_start, memblock_size, altmap);
 
+		unaccept_memory(cur_start, PFN_PHYS(altmap->free));
+
 		/* Verify that all vmemmap pages have actually been freed. */
 		WARN(altmap->alloc, "Altmap not fully unmapped");
 		kfree(altmap);
@@ -1459,9 +1461,13 @@ static int create_altmaps_and_memory_blocks(int nid, struct memory_group *group,
 			goto out;
 		}
 
+		/* Accept self hosted memmap array before access it */
+		accept_memory(cur_start, PFN_PHYS(mhp_altmap.free));
+
 		/* call arch's memory hotadd */
 		ret = arch_add_memory(nid, cur_start, memblock_size, &params);
 		if (ret < 0) {
+			unaccept_memory(cur_start, PFN_PHYS(mhp_altmap.free));
 			kfree(params.altmap);
 			goto out;
 		}
@@ -1471,6 +1477,7 @@ static int create_altmaps_and_memory_blocks(int nid, struct memory_group *group,
 						  params.altmap, group);
 		if (ret) {
 			arch_remove_memory(cur_start, memblock_size, NULL);
+			unaccept_memory(cur_start, PFN_PHYS(mhp_altmap.free));
 			kfree(params.altmap);
 			goto out;
 		}
@@ -1540,6 +1547,10 @@ int add_memory_resource(int nid, struct resource *res, mhp_t mhp_flags)
 		new_node = true;
 	}
 
+	ret = coco_set_plugged_bitmap(start, size, true);
+	if (ret)
+		goto error_offline_node;
+
 	/*
 	 * Self hosted memmap array
 	 */
@@ -1584,6 +1595,8 @@ int add_memory_resource(int nid, struct resource *res, mhp_t mhp_flags)
 
 	return ret;
 error:
+	WARN_ON(coco_set_plugged_bitmap(start, size, false));
+error_offline_node:
 	if (new_node) {
 		node_set_offline(nid);
 		unregister_node(nid);
@@ -2282,6 +2295,9 @@ static int try_remove_memory(u64 start, u64 size)
 	if (nid != NUMA_NO_NODE)
 		try_offline_node(nid);
 
+	unaccept_memory(start, size);
+	WARN_ON(coco_set_plugged_bitmap(start, size, false));
+
 	mem_hotplug_done();
 	return 0;
 }

---

## [7] Zhenzhong Duan — 2026-06-23
*Subject: [RFCv2 PATCH 6/6] virtio-mem: Support memory hotplug/unplug for coco guest*

Integrate coco memory management operations into the virtio-mem driver to
manage the state of hotplug memory.

In virtio_mem_send_plug_request(), once the host hypervisor acknowledges a
plug request, invoke coco_set_plugged_bitmap() to set the corresponding
bits in the plugged bitmap. Conversely, in virtio_mem_send_unplug_request()
and virtio_mem_send_unplug_all_request(), call unaccept_memory() to let the
guest autonomously transition the target private pages back to "unaccepted"
state before asking the VMM to unplug them. After the VMM acknowledges the
unplug request, clear the ranges from the plugged bitmap.

Note that memory block hotplug/unplug also sets or clears the plugged
bitmap at memory block granularity. While doing this at device block
granularity here creates a slight redundancy, it is completely harmless.

Additionally, update virtio_mem_fake_online() to explicitly invoke
accept_memory() when transitioning memory out of the fake-offline state and
back into service. This ensures that any pages returning to the buddy
system are cleanly accepted by the guest architecture before they are freed
back into the allocator via free_contig_range().

Signed-off-by: Zhenzhong Duan <zhenzhong.duan@intel.com>
---
 drivers/virtio/virtio_mem.c | 8 ++++++++
 1 file changed, 8 insertions(+)

diff --git a/drivers/virtio/virtio_mem.c b/drivers/virtio/virtio_mem.c
index 48051e9e98ab..9f6e53df8caf 100644
--- a/drivers/virtio/virtio_mem.c
+++ b/drivers/virtio/virtio_mem.c
@@ -1211,6 +1211,7 @@ static void virtio_mem_fake_online(unsigned long pfn, unsigned long nr_pages)
 			generic_online_page(page, order);
 		} else {
 			virtio_mem_clear_fake_offline(pfn + i, 1 << order, true);
+			accept_memory(page_to_phys(page), PAGE_SIZE << order);
 			free_contig_range(pfn + i, 1 << order);
 			adjust_managed_page_count(page, 1 << order);
 		}
@@ -1436,6 +1437,7 @@ static int virtio_mem_send_plug_request(struct virtio_mem *vm, uint64_t addr,
 	switch (virtio_mem_send_request(vm, &req)) {
 	case VIRTIO_MEM_RESP_ACK:
 		vm->plugged_size += size;
+		WARN_ON(coco_set_plugged_bitmap(addr, size, true));
 		return 0;
 	case VIRTIO_MEM_RESP_NACK:
 		rc = -EAGAIN;
@@ -1471,9 +1473,12 @@ static int virtio_mem_send_unplug_request(struct virtio_mem *vm, uint64_t addr,
 	dev_dbg(&vm->vdev->dev, "unplugging memory: 0x%llx - 0x%llx\n", addr,
 		addr + size - 1);
 
+	unaccept_memory(addr, size);
+
 	switch (virtio_mem_send_request(vm, &req)) {
 	case VIRTIO_MEM_RESP_ACK:
 		vm->plugged_size -= size;
+		WARN_ON(coco_set_plugged_bitmap(addr, size, false));
 		return 0;
 	case VIRTIO_MEM_RESP_BUSY:
 		rc = -ETXTBSY;
@@ -1498,10 +1503,13 @@ static int virtio_mem_send_unplug_all_request(struct virtio_mem *vm)
 
 	dev_dbg(&vm->vdev->dev, "unplugging all memory");
 
+	unaccept_memory(vm->addr, vm->region_size);
+
 	switch (virtio_mem_send_request(vm, &req)) {
 	case VIRTIO_MEM_RESP_ACK:
 		vm->unplug_all_required = false;
 		vm->plugged_size = 0;
+		WARN_ON(coco_set_plugged_bitmap(vm->addr, vm->region_size, false));
 		/* usable region might have shrunk */
 		atomic_set(&vm->config_changed, 1);
 		return 0;

---

## [8] Kiryl Shutsemau — 2026-06-24
*Subject: Re: [RFCv2 PATCH 1/6] efi/unaccepted: Support hotplug memory in
 unaccepted bitmap via SRAT*

On Tue, Jun 23, 2026 at 06:17:32AM -0400, Zhenzhong Duan wrote:
> Currently, allocate_unaccepted_bitmap() only scans the initial EFI
> boot memory map. This misses hotpluggable ranges described in the

Ugh.. Parsing SRAT there is ugly. I would rather avoid it.

Do I understand correctly that we don't have a way represent pluggable,
but not present memory in EFI memory map?

IIUC, EFI_MEMORY_HOT_PLUGGABLE is actually present, but unpluggable
memory.

Maybe it would be better just allocate bitmap upto maxmem?

And fix EFI spec to add pluggable-but-not-present attribute.

---

## [9] Kiryl Shutsemau — 2026-06-24
*Subject: Re: [RFCv2 PATCH 2/6] efi/unaccepted: Set unaccepted bits for all
 hotplug memory*

On Tue, Jun 23, 2026 at 06:17:33AM -0400, Zhenzhong Duan wrote:
> In coco guests, hotpluggable memory ranges are initially unaccepted.
> While a previous change expanded the unaccepted memory bitmap boundaries

We can get here with start > end if srat range is less then unit_size.

> +
> +	/* Translate to offsets from the beginning of the bitmap */

---

## [10] Kiryl Shutsemau — 2026-06-24
*Subject: Re: [RFCv2 PATCH 5/6] mm/memory_hotplug: Support ACPI hotplug/unplug
 for coco guest*

On Tue, Jun 23, 2026 at 06:17:36AM -0400, Zhenzhong Duan wrote:
> +	spin_lock_irqsave(&unaccepted_memory_lock, flags);
> +	for (; range_start < bitmap_size; range_start = range_end) {

Accept TDCALL under the spin lock will kill scalability.

---

## [11] Pratik R. Sampat — 2026-06-24
*Subject: Re: [RFCv2 PATCH 1/6] efi/unaccepted: Support hotplug memory in
 unaccepted bitmap via SRAT*

On 6/24/26 8:25 AM, Kiryl Shutsemau wrote:
> On Tue, Jun 23, 2026 at 06:17:32AM -0400, Zhenzhong Duan wrote:
>> Currently, allocate_unaccepted_bitmap() only scans the initial EFI

I agree. Parsing it here means SRAT gets parsed twice, which doesn't make much
sense.

> Do I understand correctly that we don't have a way represent pluggable,
> but not present memory in EFI memory map?

Right. And repurposing EFI_MEMORY_HOT_PLUGGABLE (plus updating the spec) would
likely make this messier: by its current definition it describes cold-plugged
pages that may be removed, not pages that may be hot-added later.

> Maybe it would be better just allocate bitmap upto maxmem?
> 

I am currently working with the UEFI community around two proposals for a spec
change:
1. Add a new attribute, as Kiryl suggested, or
2. Add a generic new hotplug memory type that represents all the memory that
   could be added later.

In either case, we could then precisely allocate the bitmap by parsing the
region with the attribute/type.

I prefer (1), but I have RFC proposals, code-first edk2 changes, and the Linux
plumbing ready for both approaches, and plan to post them in the following week
after ironing out a few kinks.

Thanks,
--Pratik

---

## [12] Duan, Zhenzhong — 2026-06-25
*Subject: RE: [RFCv2 PATCH 5/6] mm/memory_hotplug: Support ACPI hotplug/unplug
 for coco guest*

>-----Original Message-----
>From: Kiryl Shutsemau <kas@kernel.org>

OK, I can drop the lock during arch_unaccept_memory() and avoid race
by checking the accepting_list just like in accept_memory().

I initially wrapped this in the spinlock because TDG.MEM.PAGE.RELEASE
is a quick local TDX module call to transition pages back to PENDING state,
without the heavy VMM trapping/faulting overhead associated with
memory acceptance paths.

Thanks
Zhenzhong

---

## [13] Duan, Zhenzhong — 2026-06-25
*Subject: RE: [RFCv2 PATCH 2/6] efi/unaccepted: Set unaccepted bits for all
 hotplug memory*

>-----Original Message-----
>From: Kiryl Shutsemau <kas@kernel.org>

Will add a check to ignore small range less than unit_size:

+       if (start >= end)
+               return;
+

Thanks
Zhenzhong

---
