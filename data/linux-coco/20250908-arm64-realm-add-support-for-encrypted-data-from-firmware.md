---
title: 'arm64: realm: Add support for encrypted data from firmware'
date: 2025-09-08
last_reply: 2025-09-18
message_count: 8
participants: ['Suzuki K Poulose', 'Sami Mujawar', 'Gavin Shan', 'Will Deacon']
---

## [1] Suzuki K Poulose — 2025-09-08

Confidential compute firmware may provide secret data via reserved memory regions
(e.g., ACPI CCEL, EFI Coco secret area). These must be ioremap'ed() as encrypted.
As of now, realm only maps "trusted devices" (RIPAS = RSI_RIPAS_DEV) as encrypted.
This series adds support for mapping areas that are protected
(i.e., RIPAS = RSI_RIPAS_RAM) as encrypted. Also, extrapolating that, we can map
anything that is not RIPAS_EMPTY as protected, as it is guaranteed to be "protected".

With this in place, we can naturally map any firmware provided area based on the
RIPAS value. If the firmware provides a shared region (not trusted), it must have
set the RIPAS accordingly, before placing the data, as the transition is always
destructive.

Confidential Compute Event Log is exposed as EFI_ACPI_MEMORY_NVS, which is
reserved for firmware use even after the firmware exits the boot services [0].
Thus map the region as READ only in the kernel.

[0] https://uefi.org/specs/UEFI/2.10/07_Services_Boot_Services.html#memory-type-usage-before-exitbootservices

Changes since v1: 
  https://lkml.kernel.org/r/20250613111153.1548928-1-suzuki.poulose@arm.com/
 - Collect tags
 - Map EFI_MEMORY_ACPI_NVS as READ-ONLY, update comment and commit description


Suzuki K Poulose (3):
  arm64: realm: ioremap: Allow mapping memory as encrypted
  arm64: Enable EFI secret area Securityfs support
  arm64: acpi: Enable ACPI CCEL support

 arch/arm64/include/asm/io.h          |  6 +++++-
 arch/arm64/include/asm/rsi.h         |  2 +-
 arch/arm64/kernel/acpi.c             | 11 +++++++++++
 arch/arm64/kernel/rsi.c              | 26 ++++++++++++++++++++++----
 drivers/virt/coco/efi_secret/Kconfig |  2 +-
 5 files changed, 40 insertions(+), 7 deletions(-)

---

## [2] Suzuki K Poulose — 2025-09-08
*Subject: [PATCH v2 1/3] arm64: realm: ioremap: Allow mapping memory as encrypted*

For ioremap(), so far we only checked if it was a device (RIPAS_DEV) to choose
an encrypted vs decrypted mapping. However, we may have firmware reserved memory
regions exposed to the OS (e.g., EFI Coco Secret Securityfs, ACPI CCEL).
We need to make sure that anything that is RIPAS_RAM (i.e., Guest
protected memory with RMM guarantees) are also mapped as encrypted.

Rephrasing the above, anything that is not RIPAS_EMPTY is guaranteed to be
protected by the RMM. Thus we choose encrypted mapping for anything that is not
RIPAS_EMPTY. While at it, rename the helper function

  __arm64_is_protected_mmio => arm64_rsi_is_protected

to clearly indicate that this not an arm64 generic helper, but something to do
with Realms.

Cc: Sami Mujawar <sami.mujawar@arm.com>
Cc: Will Deacon <will@kernel.org>
Cc: Catalin Marinas <catalin.marinas@arm.com>
Cc: Aneesh Kumar K.V <aneesh.kumar@kernel.org>
Cc: Steven Price <steven.price@arm.com>
Reviewed-by: Gavin Shan <gshan@redhat.com>
Reviewed-by: Steven Price <steven.price@arm.com>
Tested-by: Sami Mujawar <sami.mujawar@arm.com>
Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
---
 arch/arm64/include/asm/io.h  |  2 +-
 arch/arm64/include/asm/rsi.h |  2 +-
 arch/arm64/kernel/rsi.c      | 26 ++++++++++++++++++++++----
 3 files changed, 24 insertions(+), 6 deletions(-)

diff --git a/arch/arm64/include/asm/io.h b/arch/arm64/include/asm/io.h
index 9b96840fb979..82276282a3c7 100644
--- a/arch/arm64/include/asm/io.h
+++ b/arch/arm64/include/asm/io.h
@@ -311,7 +311,7 @@ extern bool arch_memremap_can_ram_remap(resource_size_t offset, size_t size,
 static inline bool arm64_is_protected_mmio(phys_addr_t phys_addr, size_t size)
 {
 	if (unlikely(is_realm_world()))
-		return __arm64_is_protected_mmio(phys_addr, size);
+		return arm64_rsi_is_protected(phys_addr, size);
 	return false;
 }
 
diff --git a/arch/arm64/include/asm/rsi.h b/arch/arm64/include/asm/rsi.h
index b42aeac05340..88b50d660e85 100644
--- a/arch/arm64/include/asm/rsi.h
+++ b/arch/arm64/include/asm/rsi.h
@@ -16,7 +16,7 @@ DECLARE_STATIC_KEY_FALSE(rsi_present);
 
 void __init arm64_rsi_init(void);
 
-bool __arm64_is_protected_mmio(phys_addr_t base, size_t size);
+bool arm64_rsi_is_protected(phys_addr_t base, size_t size);
 
 static inline bool is_realm_world(void)
 {
diff --git a/arch/arm64/kernel/rsi.c b/arch/arm64/kernel/rsi.c
index ce4778141ec7..c64a06f58c0b 100644
--- a/arch/arm64/kernel/rsi.c
+++ b/arch/arm64/kernel/rsi.c
@@ -84,7 +84,25 @@ static void __init arm64_rsi_setup_memory(void)
 	}
 }
 
-bool __arm64_is_protected_mmio(phys_addr_t base, size_t size)
+/*
+ * Check if a given PA range is Trusted (e.g., Protected memory, a Trusted Device
+ * mapping, or an MMIO emulated in the Realm world).
+ *
+ * We can rely on the RIPAS value of the region to detect if a given region is
+ * protected.
+ *
+ *  RIPAS_DEV - A trusted device memory or a trusted emulated MMIO (in the Realm
+ *		world
+ *  RIPAS_RAM - Memory (RAM), protected by the RMM guarantees. (e.g., Firmware
+ *		reserved regions for data sharing).
+ *
+ *  RIPAS_DESTROYED is a special case of one of the above, where the host did
+ *  something without our permission and as such we can't do anything about it.
+ *
+ * The only case where something is emulated by the untrusted hypervisor or is
+ * backed by shared memory is indicated by RSI_RIPAS_EMPTY.
+ */
+bool arm64_rsi_is_protected(phys_addr_t base, size_t size)
 {
 	enum ripas ripas;
 	phys_addr_t end, top;
@@ -101,18 +119,18 @@ bool __arm64_is_protected_mmio(phys_addr_t base, size_t size)
 			break;
 		if (WARN_ON(top <= base))
 			break;
-		if (ripas != RSI_RIPAS_DEV)
+		if (ripas == RSI_RIPAS_EMPTY)
 			break;
 		base = top;
 	}
 
 	return base >= end;
 }
-EXPORT_SYMBOL(__arm64_is_protected_mmio);
+EXPORT_SYMBOL(arm64_rsi_is_protected);
 
 static int realm_ioremap_hook(phys_addr_t phys, size_t size, pgprot_t *prot)
 {
-	if (__arm64_is_protected_mmio(phys, size))
+	if (arm64_rsi_is_protected(phys, size))
 		*prot = pgprot_encrypted(*prot);
 	else
 		*prot = pgprot_decrypted(*prot);

---

## [3] Suzuki K Poulose — 2025-09-08
*Subject: [PATCH v2 2/3] arm64: Enable EFI secret area Securityfs support*

Enable EFI COCO secrets support. Provide the ioremap_encrypted() support required
by the driver.

Cc: Sami Mujawar <sami.mujawar@arm.com>
Cc: Will Deacon <will@kernel.org>
Cc: Catalin Marinas <catalin.marinas@arm.com>
Cc: Aneesh Kumar K.V <aneesh.kumar@kernel.org>
Cc: Steven Price <steven.price@arm.com>
Reviewed-by: Gavin Shan <gshan@redhat.com>
Tested-by: Sami Mujawar <sami.mujawar@arm.com>
Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
---
 arch/arm64/include/asm/io.h          | 4 ++++
 drivers/virt/coco/efi_secret/Kconfig | 2 +-
 2 files changed, 5 insertions(+), 1 deletion(-)

diff --git a/arch/arm64/include/asm/io.h b/arch/arm64/include/asm/io.h
index 82276282a3c7..83e03abbb2ca 100644
--- a/arch/arm64/include/asm/io.h
+++ b/arch/arm64/include/asm/io.h
@@ -274,6 +274,10 @@ int arm64_ioremap_prot_hook_register(const ioremap_prot_hook_t hook);
 #define ioremap_np(addr, size)	\
 	ioremap_prot((addr), (size), __pgprot(PROT_DEVICE_nGnRnE))
 
+
+#define ioremap_encrypted(addr, size)	\
+	ioremap_prot((addr), (size), PAGE_KERNEL)
+
 /*
  * io{read,write}{16,32,64}be() macros
  */
diff --git a/drivers/virt/coco/efi_secret/Kconfig b/drivers/virt/coco/efi_secret/Kconfig
index 4404d198f3b2..94d88e5da707 100644
--- a/drivers/virt/coco/efi_secret/Kconfig
+++ b/drivers/virt/coco/efi_secret/Kconfig
@@ -1,7 +1,7 @@
 # SPDX-License-Identifier: GPL-2.0-only
 config EFI_SECRET
 	tristate "EFI secret area securityfs support"
-	depends on EFI && X86_64
+	depends on EFI && (X86_64 || ARM64)
 	select EFI_COCO_SECRET
 	select SECURITYFS
 	help

---

## [4] Suzuki K Poulose — 2025-09-08
*Subject: [PATCH v2 3/3] arm64: acpi: Enable ACPI CCEL support*

Add support for ACPI CCEL by handling the EfiACPIMemoryNVS type memory.
As per UEFI specifications NVS memory is reserved for Firmware use even
after exiting boot services. Thus map the region as read-only.

Cc: Sami Mujawar <sami.mujawar@arm.com>
Cc: Will Deacon <will@kernel.org>
Cc: Catalin Marinas <catalin.marinas@arm.com>
Cc: Aneesh Kumar K.V <aneesh.kumar@kernel.org>
Cc: Steven Price <steven.price@arm.com>
Cc: Sudeep Holla <sudeep.holla@arm.com>
Cc: Gavin Shan <gshan@redhat.com>
Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
---
Changes since v1
 - Map NVS region as read-only, update comment to clarify that the region
   is reserved for firmware use.

---
 arch/arm64/kernel/acpi.c | 11 +++++++++++
 1 file changed, 11 insertions(+)

diff --git a/arch/arm64/kernel/acpi.c b/arch/arm64/kernel/acpi.c
index 4d529ff7ba51..93b70f48a51f 100644
--- a/arch/arm64/kernel/acpi.c
+++ b/arch/arm64/kernel/acpi.c
@@ -360,6 +360,17 @@ void __iomem *acpi_os_ioremap(acpi_physical_address phys, acpi_size size)
 			prot = PAGE_KERNEL_RO;
 			break;
 
+		case EFI_ACPI_MEMORY_NVS:
+			/*
+			 * ACPI NVS marks an area reserved for use by the
+			 * firmware, even after exiting the boot service.
+			 * This may be used by the firmware for sharing dynamic
+			 * tables/data (e.g., ACPI CCEL) with the OS. Map it
+			 * as read-only.
+			 */
+			prot = PAGE_KERNEL_RO;
+			break;
+
 		case EFI_ACPI_RECLAIM_MEMORY:
 			/*
 			 * ACPI reclaim memory is used to pass firmware tables

---

## [5] Sami Mujawar — 2025-09-16
*Subject: Re: [PATCH v2 0/3] arm64: realm: Add support for encrypted data from
 firmware*

For this series.

Tested-by: Sami Mujawar <sami.mujawar@arm.com>

Thanks.

Regards,

Sami Mujawar

From: Suzuki K Poulose <suzuki.poulose@arm.com>
Date: Monday, 8 September 2025 at 23:35
To: linux-arm-kernel@lists.infradead.org <linux-arm-kernel@lists.infradead.org>
Cc: linux-kernel@vger.kernel.org <linux-kernel@vger.kernel.org>, linux-coco@lists.linux.dev <linux-coco@lists.linux.dev>, Catalin Marinas <Catalin.Marinas@arm.com>, will@kernel.org <will@kernel.org>, gshan@redhat.com <gshan@redhat.com>, aneesh.kumar@kernel.org <aneesh.kumar@kernel.org>, Sami Mujawar <Sami.Mujawar@arm.com>, Sudeep Holla <Sudeep.Holla@arm.com>, Steven Price <Steven.Price@arm.com>, Suzuki Poulose <Suzuki.Poulose@arm.com>
Subject: [PATCH v2 0/3] arm64: realm: Add support for encrypted data from firmware
Confidential compute firmware may provide secret data via reserved memory regions
(e.g., ACPI CCEL, EFI Coco secret area). These must be ioremap'ed() as encrypted.
As of now, realm only maps "trusted devices" (RIPAS = RSI_RIPAS_DEV) as encrypted.
This series adds support for mapping areas that are protected
(i.e., RIPAS = RSI_RIPAS_RAM) as encrypted. Also, extrapolating that, we can map
anything that is not RIPAS_EMPTY as protected, as it is guaranteed to be "protected".

With this in place, we can naturally map any firmware provided area based on the
RIPAS value. If the firmware provides a shared region (not trusted), it must have
set the RIPAS accordingly, before placing the data, as the transition is always
destructive.

Confidential Compute Event Log is exposed as EFI_ACPI_MEMORY_NVS, which is
reserved for firmware use even after the firmware exits the boot services [0].
Thus map the region as READ only in the kernel.

[0] https://uefi.org/specs/UEFI/2.10/07_Services_Boot_Services.html#memory-type-usage-before-exitbootservices

Changes since v1: 
  https://lkml.kernel.org/r/20250613111153.1548928-1-suzuki.poulose@arm.com/
 - Collect tags
 - Map EFI_MEMORY_ACPI_NVS as READ-ONLY, update comment and commit description


Suzuki K Poulose (3):
  arm64: realm: ioremap: Allow mapping memory as encrypted
  arm64: Enable EFI secret area Securityfs support
  arm64: acpi: Enable ACPI CCEL support

 arch/arm64/include/asm/io.h          |  6 +++++-
 arch/arm64/include/asm/rsi.h         |  2 +-
 arch/arm64/kernel/acpi.c             | 11 +++++++++++
 arch/arm64/kernel/rsi.c              | 26 ++++++++++++++++++++++----
 drivers/virt/coco/efi_secret/Kconfig |  2 +-
 5 files changed, 40 insertions(+), 7 deletions(-)

---

## [6] Gavin Shan — 2025-09-17
*Subject: Re: [PATCH v2 3/3] arm64: acpi: Enable ACPI CCEL support*

On 9/9/25 8:35 AM, Suzuki K Poulose wrote:
> Add support for ACPI CCEL by handling the EfiACPIMemoryNVS type memory.
> As per UEFI specifications NVS memory is reserved for Firmware use even

Reviewed-by: Gavin Shan <gshan@redhat.com>

---

## [7] Will Deacon — 2025-09-18
*Subject: Re: [PATCH v2 3/3] arm64: acpi: Enable ACPI CCEL support*

On Mon, Sep 08, 2025 at 11:35:19PM +0100, Suzuki K Poulose wrote:
> Add support for ACPI CCEL by handling the EfiACPIMemoryNVS type memory.
> As per UEFI specifications NVS memory is reserved for Firmware use even

Shouldn't this be merged with the other case handling read-only mappings?
e.g. something like:

		switch (region->type) {
		case EFI_LOADER_CODE:
		case EFI_LOADER_DATA:
		case EFI_BOOT_SERVICES_CODE:
		case EFI_BOOT_SERVICES_DATA:
		case EFI_CONVENTIONAL_MEMORY:
		case EFI_PERSISTENT_MEMORY:
			if (memblock_is_map_memory(phys) ||
			    !memblock_is_region_memory(phys, size)) {
				pr_warn(FW_BUG "requested region covers kernel memory @ %pa\n", &phys);
				return NULL;
			}
			/*
			 * Mapping kernel memory is permitted if the region in
			 * question is covered by a single memblock with the
			 * NOMAP attribute set: this enables the use of ACPI
			 * table overrides passed via initramfs, which are
			 * reserved in memory using arch_reserve_mem_area()
			 * below. As this particular use case only requires
			 * read access, fall through to the R/O mapping case.
			 */
			fallthrough;

		case EFI_RUNTIME_SERVICES_CODE:
			/*
			 * This would be unusual, but not problematic per se,
			 * as long as we take care not to create a writable
			 * mapping for executable code.
			 */
			fallthrough;

		case EFI_ACPI_MEMORY_NVS:
			/*
			 * ACPI NVS marks an area reserved for use by the
			 * firmware, even after exiting the boot service.
			 * This may be used by the firmware for sharing dynamic
			 * tables/data (e.g., ACPI CCEL) with the OS. Map it
			 * as read-only.
			 */
			prot = PAGE_KERNEL_RO;
			break;


With that, I'm happy to pick up the series (let me know if you want me
to make the change above locally to save you a resend).

Will

---

## [8] Suzuki K Poulose — 2025-09-18
*Subject: Re: [PATCH v2 3/3] arm64: acpi: Enable ACPI CCEL support*

Hi Will

On 18/09/2025 13:31, Will Deacon wrote:
> On Mon, Sep 08, 2025 at 11:35:19PM +0100, Suzuki K Poulose wrote:
>> Add support for ACPI CCEL by handling the EfiACPIMemoryNVS type memory.

I thought about it, but went against it, to keep the code separate. But
surely this is fine. I will resend the series with the proposed change.

Suzuki

> 		switch (region->type) {
> 		case EFI_LOADER_CODE:

---
