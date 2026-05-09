---
title: 'Support for running as a pKVM protected guest'
date: 2024-08-30
last_reply: 2024-09-04
message_count: 13
participants: ['Will Deacon', 'Marc Zyngier', 'Steven Price', 'Catalin Marinas']
---

## [1] Will Deacon — 2024-08-30

Hi all,

This is version two of the series previously posted here:

  https://lore.kernel.org/r/20240730151113.1497-1-will@kernel.org

Changes since v1:
  * New patch allocating additional hypercalls for future pKVM usage

It looks like the CCA series is now using some of the pieces here [1],
so it would be great to merge this with an Ack from the kvmarm
maintainers.

Cheers,

Will

[1] https://lore.kernel.org/r/20240819131924.372366-1-steven.price@arm.com

Cc: Sudeep Holla <sudeep.holla@arm.com>
Cc: Catalin Marinas <catalin.marinas@arm.com>
Cc: Lorenzo Pieralisi <lpieralisi@kernel.org>
Cc: Suzuki Poulose <suzuki.poulose@arm.com>
Cc: Steven Price <steven.price@arm.com>
Cc: Oliver Upton <oliver.upton@linux.dev>
Cc: Marc Zyngier <maz@kernel.org>
Cc: linux-coco@lists.linux.dev

--->8

Marc Zyngier (1):
  firmware/smccc: Call arch-specific hook on discovering KVM services

Will Deacon (6):
  drivers/virt: pkvm: Add initial support for running as a protected
    guest
  arm64: mm: Add top-level dispatcher for internal mem_encrypt API
  drivers/virt: pkvm: Hook up mem_encrypt API using pKVM hypercalls
  arm64: mm: Add confidential computing hook to ioremap_prot()
  drivers/virt: pkvm: Intercept ioremap using pKVM MMIO_GUARD hypercall
  arm64: smccc: Reserve block of KVM "vendor" services for pKVM
    hypercalls

 Documentation/virt/kvm/arm/hypercalls.rst     |  98 ++++++++++++++
 arch/arm/include/asm/hypervisor.h             |   2 +
 arch/arm64/Kconfig                            |   1 +
 arch/arm64/include/asm/hypervisor.h           |  11 ++
 arch/arm64/include/asm/io.h                   |   4 +
 arch/arm64/include/asm/mem_encrypt.h          |  15 +++
 arch/arm64/include/asm/set_memory.h           |   1 +
 arch/arm64/mm/Makefile                        |   2 +-
 arch/arm64/mm/ioremap.c                       |  23 +++-
 arch/arm64/mm/mem_encrypt.c                   |  50 +++++++
 drivers/firmware/smccc/kvm_guest.c            |   2 +
 drivers/virt/coco/Kconfig                     |   2 +
 drivers/virt/coco/Makefile                    |   1 +
 drivers/virt/coco/pkvm-guest/Kconfig          |  10 ++
 drivers/virt/coco/pkvm-guest/Makefile         |   2 +
 drivers/virt/coco/pkvm-guest/arm-pkvm-guest.c | 127 ++++++++++++++++++
 include/linux/arm-smccc.h                     |  88 ++++++++++++
 17 files changed, 437 insertions(+), 2 deletions(-)
 create mode 100644 arch/arm64/include/asm/mem_encrypt.h
 create mode 100644 arch/arm64/mm/mem_encrypt.c
 create mode 100644 drivers/virt/coco/pkvm-guest/Kconfig
 create mode 100644 drivers/virt/coco/pkvm-guest/Makefile
 create mode 100644 drivers/virt/coco/pkvm-guest/arm-pkvm-guest.c

---

## [2] Will Deacon — 2024-08-30
*Subject: [PATCH v2 1/7] firmware/smccc: Call arch-specific hook on discovering KVM services*

From: Marc Zyngier <maz@kernel.org>

arm64 will soon require its own callback to initialise services
that are only available on this architecture. Introduce a hook
that can be overloaded by the architecture.

Signed-off-by: Marc Zyngier <maz@kernel.org>
Signed-off-by: Will Deacon <will@kernel.org>
---
 arch/arm/include/asm/hypervisor.h   | 2 ++
 arch/arm64/include/asm/hypervisor.h | 4 ++++
 drivers/firmware/smccc/kvm_guest.c  | 2 ++
 3 files changed, 8 insertions(+)

diff --git a/arch/arm/include/asm/hypervisor.h b/arch/arm/include/asm/hypervisor.h
index bd61502b9715..8a648e506540 100644
--- a/arch/arm/include/asm/hypervisor.h
+++ b/arch/arm/include/asm/hypervisor.h
@@ -7,4 +7,6 @@
 void kvm_init_hyp_services(void);
 bool kvm_arm_hyp_service_available(u32 func_id);
 
+static inline void kvm_arch_init_hyp_services(void) { };
+
 #endif
diff --git a/arch/arm64/include/asm/hypervisor.h b/arch/arm64/include/asm/hypervisor.h
index 0ae427f352c8..8cab2ab535b7 100644
--- a/arch/arm64/include/asm/hypervisor.h
+++ b/arch/arm64/include/asm/hypervisor.h
@@ -7,4 +7,8 @@
 void kvm_init_hyp_services(void);
 bool kvm_arm_hyp_service_available(u32 func_id);
 
+static inline void kvm_arch_init_hyp_services(void)
+{
+};
+
 #endif
diff --git a/drivers/firmware/smccc/kvm_guest.c b/drivers/firmware/smccc/kvm_guest.c
index 89a68e7eeaa6..f3319be20b36 100644
--- a/drivers/firmware/smccc/kvm_guest.c
+++ b/drivers/firmware/smccc/kvm_guest.c
@@ -39,6 +39,8 @@ void __init kvm_init_hyp_services(void)
 
 	pr_info("hypervisor services detected (0x%08lx 0x%08lx 0x%08lx 0x%08lx)\n",
 		 res.a3, res.a2, res.a1, res.a0);
+
+	kvm_arch_init_hyp_services();
 }
 
 bool kvm_arm_hyp_service_available(u32 func_id)

---

## [3] Will Deacon — 2024-08-30
*Subject: [PATCH v2 2/7] drivers/virt: pkvm: Add initial support for running as a protected guest*

Implement a pKVM protected guest driver to probe the presence of pKVM
and determine the memory protection granule using the HYP_MEMINFO
hypercall.

Signed-off-by: Will Deacon <will@kernel.org>
---
 Documentation/virt/kvm/arm/hypercalls.rst     | 22 +++++++++++
 arch/arm64/include/asm/hypervisor.h           |  7 ++++
 drivers/virt/coco/Kconfig                     |  2 +
 drivers/virt/coco/Makefile                    |  1 +
 drivers/virt/coco/pkvm-guest/Kconfig          | 10 +++++
 drivers/virt/coco/pkvm-guest/Makefile         |  2 +
 drivers/virt/coco/pkvm-guest/arm-pkvm-guest.c | 37 +++++++++++++++++++
 include/linux/arm-smccc.h                     |  7 ++++
 8 files changed, 88 insertions(+)
 create mode 100644 drivers/virt/coco/pkvm-guest/Kconfig
 create mode 100644 drivers/virt/coco/pkvm-guest/Makefile
 create mode 100644 drivers/virt/coco/pkvm-guest/arm-pkvm-guest.c

diff --git a/Documentation/virt/kvm/arm/hypercalls.rst b/Documentation/virt/kvm/arm/hypercalls.rst
index 17be111f493f..16515eb42149 100644
--- a/Documentation/virt/kvm/arm/hypercalls.rst
+++ b/Documentation/virt/kvm/arm/hypercalls.rst
@@ -44,3 +44,25 @@ Provides a discovery mechanism for other KVM/arm64 hypercalls.
 ----------------------------------------
 
 See ptp_kvm.rst
+
+``ARM_SMCCC_KVM_FUNC_HYP_MEMINFO``
+----------------------------------
+
+Query the memory protection parameters for a pKVM protected virtual machine.
+
++---------------------+-------------------------------------------------------------+
+| Presence:           | Optional; pKVM protected guests only.                       |
++---------------------+-------------------------------------------------------------+
+| Calling convention: | HVC64                                                       |
++---------------------+----------+--------------------------------------------------+
+| Function ID:        | (uint32) | 0xC6000002                                       |
++---------------------+----------+----+---------------------------------------------+
+| Arguments:          | (uint64) | R1 | Reserved / Must be zero                     |
+|                     +----------+----+---------------------------------------------+
+|                     | (uint64) | R2 | Reserved / Must be zero                     |
+|                     +----------+----+---------------------------------------------+
+|                     | (uint64) | R3 | Reserved / Must be zero                     |
++---------------------+----------+----+---------------------------------------------+
+| Return Values:      | (int64)  | R0 | ``INVALID_PARAMETER (-3)`` on error, else   |
+|                     |          |    | memory protection granule in bytes          |
++---------------------+----------+----+---------------------------------------------+
diff --git a/arch/arm64/include/asm/hypervisor.h b/arch/arm64/include/asm/hypervisor.h
index 8cab2ab535b7..409e239834d1 100644
--- a/arch/arm64/include/asm/hypervisor.h
+++ b/arch/arm64/include/asm/hypervisor.h
@@ -7,8 +7,15 @@
 void kvm_init_hyp_services(void);
 bool kvm_arm_hyp_service_available(u32 func_id);
 
+#ifdef CONFIG_ARM_PKVM_GUEST
+void pkvm_init_hyp_services(void);
+#else
+static inline void pkvm_init_hyp_services(void) { };
+#endif
+
 static inline void kvm_arch_init_hyp_services(void)
 {
+	pkvm_init_hyp_services();
 };
 
 #endif
diff --git a/drivers/virt/coco/Kconfig b/drivers/virt/coco/Kconfig
index 87d142c1f932..d9ff676bf48d 100644
--- a/drivers/virt/coco/Kconfig
+++ b/drivers/virt/coco/Kconfig
@@ -9,6 +9,8 @@ config TSM_REPORTS
 
 source "drivers/virt/coco/efi_secret/Kconfig"
 
+source "drivers/virt/coco/pkvm-guest/Kconfig"
+
 source "drivers/virt/coco/sev-guest/Kconfig"
 
 source "drivers/virt/coco/tdx-guest/Kconfig"
diff --git a/drivers/virt/coco/Makefile b/drivers/virt/coco/Makefile
index 18c1aba5edb7..b69c30c1c720 100644
--- a/drivers/virt/coco/Makefile
+++ b/drivers/virt/coco/Makefile
@@ -4,5 +4,6 @@
 #
 obj-$(CONFIG_TSM_REPORTS)	+= tsm.o
 obj-$(CONFIG_EFI_SECRET)	+= efi_secret/
+obj-$(CONFIG_ARM_PKVM_GUEST)	+= pkvm-guest/
 obj-$(CONFIG_SEV_GUEST)		+= sev-guest/
 obj-$(CONFIG_INTEL_TDX_GUEST)	+= tdx-guest/
diff --git a/drivers/virt/coco/pkvm-guest/Kconfig b/drivers/virt/coco/pkvm-guest/Kconfig
new file mode 100644
index 000000000000..d2f344f1f98f
--- /dev/null
+++ b/drivers/virt/coco/pkvm-guest/Kconfig
@@ -0,0 +1,10 @@
+config ARM_PKVM_GUEST
+	bool "Arm pKVM protected guest driver"
+	depends on ARM64
+	help
+	  Protected guests running under the pKVM hypervisor on arm64
+	  are isolated from the host and must issue hypercalls to enable
+	  interaction with virtual devices. This driver implements
+	  support for probing and issuing these hypercalls.
+
+	  If unsure, say 'N'.
diff --git a/drivers/virt/coco/pkvm-guest/Makefile b/drivers/virt/coco/pkvm-guest/Makefile
new file mode 100644
index 000000000000..4bee24579423
--- /dev/null
+++ b/drivers/virt/coco/pkvm-guest/Makefile
@@ -0,0 +1,2 @@
+# SPDX-License-Identifier: GPL-2.0-only
+obj-$(CONFIG_ARM_PKVM_GUEST) += arm-pkvm-guest.o
diff --git a/drivers/virt/coco/pkvm-guest/arm-pkvm-guest.c b/drivers/virt/coco/pkvm-guest/arm-pkvm-guest.c
new file mode 100644
index 000000000000..a5148701d2f1
--- /dev/null
+++ b/drivers/virt/coco/pkvm-guest/arm-pkvm-guest.c
@@ -0,0 +1,37 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/*
+ * Support for the hypercall interface exposed to protected guests by
+ * pKVM.
+ *
+ * Author: Will Deacon <will@kernel.org>
+ * Copyright (C) 2024 Google LLC
+ */
+
+#include <linux/arm-smccc.h>
+#include <linux/array_size.h>
+#include <linux/mm.h>
+
+#include <asm/hypervisor.h>
+
+static size_t pkvm_granule;
+
+void pkvm_init_hyp_services(void)
+{
+	int i;
+	struct arm_smccc_res res;
+	const u32 funcs[] = {
+		ARM_SMCCC_KVM_FUNC_HYP_MEMINFO,
+	};
+
+	for (i = 0; i < ARRAY_SIZE(funcs); ++i) {
+		if (!kvm_arm_hyp_service_available(funcs[i]))
+			return;
+	}
+
+	arm_smccc_1_1_invoke(ARM_SMCCC_VENDOR_HYP_KVM_HYP_MEMINFO_FUNC_ID,
+			     0, 0, 0, &res);
+	if (res.a0 > PAGE_SIZE) /* Includes error codes */
+		return;
+
+	pkvm_granule = res.a0;
+}
diff --git a/include/linux/arm-smccc.h b/include/linux/arm-smccc.h
index 083f85653716..16b6dcc54e02 100644
--- a/include/linux/arm-smccc.h
+++ b/include/linux/arm-smccc.h
@@ -115,6 +115,7 @@
 /* KVM "vendor specific" services */
 #define ARM_SMCCC_KVM_FUNC_FEATURES		0
 #define ARM_SMCCC_KVM_FUNC_PTP			1
+#define ARM_SMCCC_KVM_FUNC_HYP_MEMINFO		2
 #define ARM_SMCCC_KVM_FUNC_FEATURES_2		127
 #define ARM_SMCCC_KVM_NUM_FUNCS			128
 
@@ -137,6 +138,12 @@
 			   ARM_SMCCC_OWNER_VENDOR_HYP,			\
 			   ARM_SMCCC_KVM_FUNC_PTP)
 
+#define ARM_SMCCC_VENDOR_HYP_KVM_HYP_MEMINFO_FUNC_ID			\
+	ARM_SMCCC_CALL_VAL(ARM_SMCCC_FAST_CALL,				\
+			   ARM_SMCCC_SMC_64,				\
+			   ARM_SMCCC_OWNER_VENDOR_HYP,			\
+			   ARM_SMCCC_KVM_FUNC_HYP_MEMINFO)
+
 /* ptp_kvm counter type ID */
 #define KVM_PTP_VIRT_COUNTER			0
 #define KVM_PTP_PHYS_COUNTER			1

---

## [4] Will Deacon — 2024-08-30
*Subject: [PATCH v2 3/7] arm64: mm: Add top-level dispatcher for internal mem_encrypt API*

Implementing the internal mem_encrypt API for arm64 depends entirely on
the Confidential Computing environment in which the kernel is running.

Introduce a simple dispatcher so that backend hooks can be registered
depending upon the environment in which the kernel finds itself.

Signed-off-by: Will Deacon <will@kernel.org>
---
 arch/arm64/Kconfig                   |  1 +
 arch/arm64/include/asm/mem_encrypt.h | 15 +++++++++
 arch/arm64/include/asm/set_memory.h  |  1 +
 arch/arm64/mm/Makefile               |  2 +-
 arch/arm64/mm/mem_encrypt.c          | 50 ++++++++++++++++++++++++++++
 5 files changed, 68 insertions(+), 1 deletion(-)
 create mode 100644 arch/arm64/include/asm/mem_encrypt.h
 create mode 100644 arch/arm64/mm/mem_encrypt.c

diff --git a/arch/arm64/Kconfig b/arch/arm64/Kconfig
index a2f8ff354ca6..164858120191 100644
--- a/arch/arm64/Kconfig
+++ b/arch/arm64/Kconfig
@@ -34,6 +34,7 @@ config ARM64
 	select ARCH_HAS_KERNEL_FPU_SUPPORT if KERNEL_MODE_NEON
 	select ARCH_HAS_KEEPINITRD
 	select ARCH_HAS_MEMBARRIER_SYNC_CORE
+	select ARCH_HAS_MEM_ENCRYPT
 	select ARCH_HAS_NMI_SAFE_THIS_CPU_OPS
 	select ARCH_HAS_NON_OVERLAPPING_ADDRESS_SPACE
 	select ARCH_HAS_PTE_DEVMAP
diff --git a/arch/arm64/include/asm/mem_encrypt.h b/arch/arm64/include/asm/mem_encrypt.h
new file mode 100644
index 000000000000..b0c9a86b13a4
--- /dev/null
+++ b/arch/arm64/include/asm/mem_encrypt.h
@@ -0,0 +1,15 @@
+/* SPDX-License-Identifier: GPL-2.0-only */
+#ifndef __ASM_MEM_ENCRYPT_H
+#define __ASM_MEM_ENCRYPT_H
+
+struct arm64_mem_crypt_ops {
+	int (*encrypt)(unsigned long addr, int numpages);
+	int (*decrypt)(unsigned long addr, int numpages);
+};
+
+int arm64_mem_crypt_ops_register(const struct arm64_mem_crypt_ops *ops);
+
+int set_memory_encrypted(unsigned long addr, int numpages);
+int set_memory_decrypted(unsigned long addr, int numpages);
+
+#endif	/* __ASM_MEM_ENCRYPT_H */
diff --git a/arch/arm64/include/asm/set_memory.h b/arch/arm64/include/asm/set_memory.h
index 0f740b781187..917761feeffd 100644
--- a/arch/arm64/include/asm/set_memory.h
+++ b/arch/arm64/include/asm/set_memory.h
@@ -3,6 +3,7 @@
 #ifndef _ASM_ARM64_SET_MEMORY_H
 #define _ASM_ARM64_SET_MEMORY_H
 
+#include <asm/mem_encrypt.h>
 #include <asm-generic/set_memory.h>
 
 bool can_set_direct_map(void);
diff --git a/arch/arm64/mm/Makefile b/arch/arm64/mm/Makefile
index 60454256945b..2fc8c6dd0407 100644
--- a/arch/arm64/mm/Makefile
+++ b/arch/arm64/mm/Makefile
@@ -1,7 +1,7 @@
 # SPDX-License-Identifier: GPL-2.0
 obj-y				:= dma-mapping.o extable.o fault.o init.o \
 				   cache.o copypage.o flush.o \
-				   ioremap.o mmap.o pgd.o mmu.o \
+				   ioremap.o mmap.o pgd.o mem_encrypt.o mmu.o \
 				   context.o proc.o pageattr.o fixmap.o
 obj-$(CONFIG_ARM64_CONTPTE)	+= contpte.o
 obj-$(CONFIG_HUGETLB_PAGE)	+= hugetlbpage.o
diff --git a/arch/arm64/mm/mem_encrypt.c b/arch/arm64/mm/mem_encrypt.c
new file mode 100644
index 000000000000..ee3c0ab04384
--- /dev/null
+++ b/arch/arm64/mm/mem_encrypt.c
@@ -0,0 +1,50 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/*
+ * Implementation of the memory encryption/decryption API.
+ *
+ * Since the low-level details of the operation depend on the
+ * Confidential Computing environment (e.g. pKVM, CCA, ...), this just
+ * acts as a top-level dispatcher to whatever hooks may have been
+ * registered.
+ *
+ * Author: Will Deacon <will@kernel.org>
+ * Copyright (C) 2024 Google LLC
+ *
+ * "Hello, boils and ghouls!"
+ */
+
+#include <linux/bug.h>
+#include <linux/compiler.h>
+#include <linux/err.h>
+#include <linux/mm.h>
+
+#include <asm/mem_encrypt.h>
+
+static const struct arm64_mem_crypt_ops *crypt_ops;
+
+int arm64_mem_crypt_ops_register(const struct arm64_mem_crypt_ops *ops)
+{
+	if (WARN_ON(crypt_ops))
+		return -EBUSY;
+
+	crypt_ops = ops;
+	return 0;
+}
+
+int set_memory_encrypted(unsigned long addr, int numpages)
+{
+	if (likely(!crypt_ops) || WARN_ON(!PAGE_ALIGNED(addr)))
+		return 0;
+
+	return crypt_ops->encrypt(addr, numpages);
+}
+EXPORT_SYMBOL_GPL(set_memory_encrypted);
+
+int set_memory_decrypted(unsigned long addr, int numpages)
+{
+	if (likely(!crypt_ops) || WARN_ON(!PAGE_ALIGNED(addr)))
+		return 0;
+
+	return crypt_ops->decrypt(addr, numpages);
+}
+EXPORT_SYMBOL_GPL(set_memory_decrypted);

---

## [5] Will Deacon — 2024-08-30
*Subject: [PATCH v2 4/7] drivers/virt: pkvm: Hook up mem_encrypt API using pKVM hypercalls*

If we detect the presence of pKVM's SHARE and UNSHARE hypercalls, then
register a backend implementation of the mem_encrypt API so that things
like DMA buffers can be shared appropriately with the host.

Signed-off-by: Will Deacon <will@kernel.org>
---
 Documentation/virt/kvm/arm/hypercalls.rst     | 50 +++++++++++++++++
 drivers/virt/coco/pkvm-guest/arm-pkvm-guest.c | 55 +++++++++++++++++++
 include/linux/arm-smccc.h                     | 14 +++++
 3 files changed, 119 insertions(+)

diff --git a/Documentation/virt/kvm/arm/hypercalls.rst b/Documentation/virt/kvm/arm/hypercalls.rst
index 16515eb42149..c42580e71bf8 100644
--- a/Documentation/virt/kvm/arm/hypercalls.rst
+++ b/Documentation/virt/kvm/arm/hypercalls.rst
@@ -66,3 +66,53 @@ Query the memory protection parameters for a pKVM protected virtual machine.
 | Return Values:      | (int64)  | R0 | ``INVALID_PARAMETER (-3)`` on error, else   |
 |                     |          |    | memory protection granule in bytes          |
 +---------------------+----------+----+---------------------------------------------+
+
+``ARM_SMCCC_KVM_FUNC_MEM_SHARE``
+--------------------------------
+
+Share a region of memory with the KVM host, granting it read, write and execute
+permissions. The size of the region is equal to the memory protection granule
+advertised by ``ARM_SMCCC_KVM_FUNC_HYP_MEMINFO``.
+
++---------------------+-------------------------------------------------------------+
+| Presence:           | Optional; pKVM protected guests only.                       |
++---------------------+-------------------------------------------------------------+
+| Calling convention: | HVC64                                                       |
++---------------------+----------+--------------------------------------------------+
+| Function ID:        | (uint32) | 0xC6000003                                       |
++---------------------+----------+----+---------------------------------------------+
+| Arguments:          | (uint64) | R1 | Base IPA of memory region to share          |
+|                     +----------+----+---------------------------------------------+
+|                     | (uint64) | R2 | Reserved / Must be zero                     |
+|                     +----------+----+---------------------------------------------+
+|                     | (uint64) | R3 | Reserved / Must be zero                     |
++---------------------+----------+----+---------------------------------------------+
+| Return Values:      | (int64)  | R0 | ``SUCCESS (0)``                             |
+|                     |          |    +---------------------------------------------+
+|                     |          |    | ``INVALID_PARAMETER (-3)``                  |
++---------------------+----------+----+---------------------------------------------+
+
+``ARM_SMCCC_KVM_FUNC_MEM_UNSHARE``
+----------------------------------
+
+Revoke access permission from the KVM host to a memory region previously shared
+with ``ARM_SMCCC_KVM_FUNC_MEM_SHARE``. The size of the region is equal to the
+memory protection granule advertised by ``ARM_SMCCC_KVM_FUNC_HYP_MEMINFO``.
+
++---------------------+-------------------------------------------------------------+
+| Presence:           | Optional; pKVM protected guests only.                       |
++---------------------+-------------------------------------------------------------+
+| Calling convention: | HVC64                                                       |
++---------------------+----------+--------------------------------------------------+
+| Function ID:        | (uint32) | 0xC6000004                                       |
++---------------------+----------+----+---------------------------------------------+
+| Arguments:          | (uint64) | R1 | Base IPA of memory region to unshare        |
+|                     +----------+----+---------------------------------------------+
+|                     | (uint64) | R2 | Reserved / Must be zero                     |
+|                     +----------+----+---------------------------------------------+
+|                     | (uint64) | R3 | Reserved / Must be zero                     |
++---------------------+----------+----+---------------------------------------------+
+| Return Values:      | (int64)  | R0 | ``SUCCESS (0)``                             |
+|                     |          |    +---------------------------------------------+
+|                     |          |    | ``INVALID_PARAMETER (-3)``                  |
++---------------------+----------+----+---------------------------------------------+
diff --git a/drivers/virt/coco/pkvm-guest/arm-pkvm-guest.c b/drivers/virt/coco/pkvm-guest/arm-pkvm-guest.c
index a5148701d2f1..8256cf68fd76 100644
--- a/drivers/virt/coco/pkvm-guest/arm-pkvm-guest.c
+++ b/drivers/virt/coco/pkvm-guest/arm-pkvm-guest.c
@@ -9,18 +9,72 @@
 
 #include <linux/arm-smccc.h>
 #include <linux/array_size.h>
+#include <linux/mem_encrypt.h>
 #include <linux/mm.h>
 
 #include <asm/hypervisor.h>
 
 static size_t pkvm_granule;
 
+static int arm_smccc_do_one_page(u32 func_id, phys_addr_t phys)
+{
+	phys_addr_t end = phys + PAGE_SIZE;
+
+	while (phys < end) {
+		struct arm_smccc_res res;
+
+		arm_smccc_1_1_invoke(func_id, phys, 0, 0, &res);
+		if (res.a0 != SMCCC_RET_SUCCESS)
+			return -EPERM;
+
+		phys += pkvm_granule;
+	}
+
+	return 0;
+}
+
+static int __set_memory_range(u32 func_id, unsigned long start, int numpages)
+{
+	void *addr = (void *)start, *end = addr + numpages * PAGE_SIZE;
+
+	while (addr < end) {
+		int err;
+
+		err = arm_smccc_do_one_page(func_id, virt_to_phys(addr));
+		if (err)
+			return err;
+
+		addr += PAGE_SIZE;
+	}
+
+	return 0;
+}
+
+static int pkvm_set_memory_encrypted(unsigned long addr, int numpages)
+{
+	return __set_memory_range(ARM_SMCCC_VENDOR_HYP_KVM_MEM_UNSHARE_FUNC_ID,
+				  addr, numpages);
+}
+
+static int pkvm_set_memory_decrypted(unsigned long addr, int numpages)
+{
+	return __set_memory_range(ARM_SMCCC_VENDOR_HYP_KVM_MEM_SHARE_FUNC_ID,
+				  addr, numpages);
+}
+
+static const struct arm64_mem_crypt_ops pkvm_crypt_ops = {
+	.encrypt	= pkvm_set_memory_encrypted,
+	.decrypt	= pkvm_set_memory_decrypted,
+};
+
 void pkvm_init_hyp_services(void)
 {
 	int i;
 	struct arm_smccc_res res;
 	const u32 funcs[] = {
 		ARM_SMCCC_KVM_FUNC_HYP_MEMINFO,
+		ARM_SMCCC_KVM_FUNC_MEM_SHARE,
+		ARM_SMCCC_KVM_FUNC_MEM_UNSHARE,
 	};
 
 	for (i = 0; i < ARRAY_SIZE(funcs); ++i) {
@@ -34,4 +88,5 @@ void pkvm_init_hyp_services(void)
 		return;
 
 	pkvm_granule = res.a0;
+	arm64_mem_crypt_ops_register(&pkvm_crypt_ops);
 }
diff --git a/include/linux/arm-smccc.h b/include/linux/arm-smccc.h
index 16b6dcc54e02..9cb7c95920b0 100644
--- a/include/linux/arm-smccc.h
+++ b/include/linux/arm-smccc.h
@@ -116,6 +116,8 @@
 #define ARM_SMCCC_KVM_FUNC_FEATURES		0
 #define ARM_SMCCC_KVM_FUNC_PTP			1
 #define ARM_SMCCC_KVM_FUNC_HYP_MEMINFO		2
+#define ARM_SMCCC_KVM_FUNC_MEM_SHARE		3
+#define ARM_SMCCC_KVM_FUNC_MEM_UNSHARE		4
 #define ARM_SMCCC_KVM_FUNC_FEATURES_2		127
 #define ARM_SMCCC_KVM_NUM_FUNCS			128
 
@@ -144,6 +146,18 @@
 			   ARM_SMCCC_OWNER_VENDOR_HYP,			\
 			   ARM_SMCCC_KVM_FUNC_HYP_MEMINFO)
 
+#define ARM_SMCCC_VENDOR_HYP_KVM_MEM_SHARE_FUNC_ID			\
+	ARM_SMCCC_CALL_VAL(ARM_SMCCC_FAST_CALL,				\
+			   ARM_SMCCC_SMC_64,				\
+			   ARM_SMCCC_OWNER_VENDOR_HYP,			\
+			   ARM_SMCCC_KVM_FUNC_MEM_SHARE)
+
+#define ARM_SMCCC_VENDOR_HYP_KVM_MEM_UNSHARE_FUNC_ID			\
+	ARM_SMCCC_CALL_VAL(ARM_SMCCC_FAST_CALL,				\
+			   ARM_SMCCC_SMC_64,				\
+			   ARM_SMCCC_OWNER_VENDOR_HYP,			\
+			   ARM_SMCCC_KVM_FUNC_MEM_UNSHARE)
+
 /* ptp_kvm counter type ID */
 #define KVM_PTP_VIRT_COUNTER			0
 #define KVM_PTP_PHYS_COUNTER			1

---

## [6] Will Deacon — 2024-08-30
*Subject: [PATCH v2 5/7] arm64: mm: Add confidential computing hook to ioremap_prot()*

Confidential Computing environments such as pKVM and Arm's CCA
distinguish between shared (i.e. emulated) and private (i.e. assigned)
MMIO regions.

Introduce a hook into our implementation of ioremap_prot() so that MMIO
regions can be shared if necessary.

Signed-off-by: Will Deacon <will@kernel.org>
---
 arch/arm64/include/asm/io.h |  4 ++++
 arch/arm64/mm/ioremap.c     | 23 ++++++++++++++++++++++-
 2 files changed, 26 insertions(+), 1 deletion(-)

diff --git a/arch/arm64/include/asm/io.h b/arch/arm64/include/asm/io.h
index 41fd90895dfc..1ada23a6ec19 100644
--- a/arch/arm64/include/asm/io.h
+++ b/arch/arm64/include/asm/io.h
@@ -271,6 +271,10 @@ __iowrite64_copy(void __iomem *to, const void *from, size_t count)
  * I/O memory mapping functions.
  */
 
+typedef int (*ioremap_prot_hook_t)(phys_addr_t phys_addr, size_t size,
+				   pgprot_t *prot);
+int arm64_ioremap_prot_hook_register(const ioremap_prot_hook_t hook);
+
 #define ioremap_prot ioremap_prot
 
 #define _PAGE_IOREMAP PROT_DEVICE_nGnRE
diff --git a/arch/arm64/mm/ioremap.c b/arch/arm64/mm/ioremap.c
index 269f2f63ab7d..6cc0b7e7eb03 100644
--- a/arch/arm64/mm/ioremap.c
+++ b/arch/arm64/mm/ioremap.c
@@ -3,10 +3,22 @@
 #include <linux/mm.h>
 #include <linux/io.h>
 
+static ioremap_prot_hook_t ioremap_prot_hook;
+
+int arm64_ioremap_prot_hook_register(ioremap_prot_hook_t hook)
+{
+	if (WARN_ON(ioremap_prot_hook))
+		return -EBUSY;
+
+	ioremap_prot_hook = hook;
+	return 0;
+}
+
 void __iomem *ioremap_prot(phys_addr_t phys_addr, size_t size,
 			   unsigned long prot)
 {
 	unsigned long last_addr = phys_addr + size - 1;
+	pgprot_t pgprot = __pgprot(prot);
 
 	/* Don't allow outside PHYS_MASK */
 	if (last_addr & ~PHYS_MASK)
@@ -16,7 +28,16 @@ void __iomem *ioremap_prot(phys_addr_t phys_addr, size_t size,
 	if (WARN_ON(pfn_is_map_memory(__phys_to_pfn(phys_addr))))
 		return NULL;
 
-	return generic_ioremap_prot(phys_addr, size, __pgprot(prot));
+	/*
+	 * If a hook is registered (e.g. for confidential computing
+	 * purposes), call that now and barf if it fails.
+	 */
+	if (unlikely(ioremap_prot_hook) &&
+	    WARN_ON(ioremap_prot_hook(phys_addr, size, &pgprot))) {
+		return NULL;
+	}
+
+	return generic_ioremap_prot(phys_addr, size, pgprot);
 }
 EXPORT_SYMBOL(ioremap_prot);

---

## [7] Will Deacon — 2024-08-30
*Subject: [PATCH v2 6/7] drivers/virt: pkvm: Intercept ioremap using pKVM MMIO_GUARD hypercall*

Hook up pKVM's MMIO_GUARD hypercall so that ioremap() and friends will
register the target physical address as MMIO with the hypervisor,
allowing guest exits to that page to be emulated by the host with full
syndrome information.

Signed-off-by: Will Deacon <will@kernel.org>
---
 Documentation/virt/kvm/arm/hypercalls.rst     | 26 ++++++++++++++
 drivers/virt/coco/pkvm-guest/arm-pkvm-guest.c | 35 +++++++++++++++++++
 include/linux/arm-smccc.h                     |  7 ++++
 3 files changed, 68 insertions(+)

diff --git a/Documentation/virt/kvm/arm/hypercalls.rst b/Documentation/virt/kvm/arm/hypercalls.rst
index c42580e71bf8..af7bc2c2e0cb 100644
--- a/Documentation/virt/kvm/arm/hypercalls.rst
+++ b/Documentation/virt/kvm/arm/hypercalls.rst
@@ -116,3 +116,29 @@ memory protection granule advertised by ``ARM_SMCCC_KVM_FUNC_HYP_MEMINFO``.
 |                     |          |    +---------------------------------------------+
 |                     |          |    | ``INVALID_PARAMETER (-3)``                  |
 +---------------------+----------+----+---------------------------------------------+
+
+``ARM_SMCCC_KVM_FUNC_MMIO_GUARD``
+----------------------------------
+
+Request that a given memory region is handled as MMIO by the hypervisor,
+allowing accesses to this region to be emulated by the KVM host. The size of the
+region is equal to the memory protection granule advertised by
+``ARM_SMCCC_KVM_FUNC_HYP_MEMINFO``.
+
++---------------------+-------------------------------------------------------------+
+| Presence:           | Optional; pKVM protected guests only.                       |
++---------------------+-------------------------------------------------------------+
+| Calling convention: | HVC64                                                       |
++---------------------+----------+--------------------------------------------------+
+| Function ID:        | (uint32) | 0xC6000007                                       |
++---------------------+----------+----+---------------------------------------------+
+| Arguments:          | (uint64) | R1 | Base IPA of MMIO memory region              |
+|                     +----------+----+---------------------------------------------+
+|                     | (uint64) | R2 | Reserved / Must be zero                     |
+|                     +----------+----+---------------------------------------------+
+|                     | (uint64) | R3 | Reserved / Must be zero                     |
++---------------------+----------+----+---------------------------------------------+
+| Return Values:      | (int64)  | R0 | ``SUCCESS (0)``                             |
+|                     |          |    +---------------------------------------------+
+|                     |          |    | ``INVALID_PARAMETER (-3)``                  |
++---------------------+----------+----+---------------------------------------------+
diff --git a/drivers/virt/coco/pkvm-guest/arm-pkvm-guest.c b/drivers/virt/coco/pkvm-guest/arm-pkvm-guest.c
index 8256cf68fd76..56a3859dda8a 100644
--- a/drivers/virt/coco/pkvm-guest/arm-pkvm-guest.c
+++ b/drivers/virt/coco/pkvm-guest/arm-pkvm-guest.c
@@ -9,8 +9,10 @@
 
 #include <linux/arm-smccc.h>
 #include <linux/array_size.h>
+#include <linux/io.h>
 #include <linux/mem_encrypt.h>
 #include <linux/mm.h>
+#include <linux/pgtable.h>
 
 #include <asm/hypervisor.h>
 
@@ -67,6 +69,36 @@ static const struct arm64_mem_crypt_ops pkvm_crypt_ops = {
 	.decrypt	= pkvm_set_memory_decrypted,
 };
 
+static int mmio_guard_ioremap_hook(phys_addr_t phys, size_t size,
+				   pgprot_t *prot)
+{
+	phys_addr_t end;
+	pteval_t protval = pgprot_val(*prot);
+
+	/*
+	 * We only expect MMIO emulation for regions mapped with device
+	 * attributes.
+	 */
+	if (protval != PROT_DEVICE_nGnRE && protval != PROT_DEVICE_nGnRnE)
+		return 0;
+
+	phys = PAGE_ALIGN_DOWN(phys);
+	end = phys + PAGE_ALIGN(size);
+
+	while (phys < end) {
+		const int func_id = ARM_SMCCC_VENDOR_HYP_KVM_MMIO_GUARD_FUNC_ID;
+		int err;
+
+		err = arm_smccc_do_one_page(func_id, phys);
+		if (err)
+			return err;
+
+		phys += PAGE_SIZE;
+	}
+
+	return 0;
+}
+
 void pkvm_init_hyp_services(void)
 {
 	int i;
@@ -89,4 +121,7 @@ void pkvm_init_hyp_services(void)
 
 	pkvm_granule = res.a0;
 	arm64_mem_crypt_ops_register(&pkvm_crypt_ops);
+
+	if (kvm_arm_hyp_service_available(ARM_SMCCC_KVM_FUNC_MMIO_GUARD))
+		arm64_ioremap_prot_hook_register(&mmio_guard_ioremap_hook);
 }
diff --git a/include/linux/arm-smccc.h b/include/linux/arm-smccc.h
index 9cb7c95920b0..e93c1f7cea70 100644
--- a/include/linux/arm-smccc.h
+++ b/include/linux/arm-smccc.h
@@ -118,6 +118,7 @@
 #define ARM_SMCCC_KVM_FUNC_HYP_MEMINFO		2
 #define ARM_SMCCC_KVM_FUNC_MEM_SHARE		3
 #define ARM_SMCCC_KVM_FUNC_MEM_UNSHARE		4
+#define ARM_SMCCC_KVM_FUNC_MMIO_GUARD		7
 #define ARM_SMCCC_KVM_FUNC_FEATURES_2		127
 #define ARM_SMCCC_KVM_NUM_FUNCS			128
 
@@ -158,6 +159,12 @@
 			   ARM_SMCCC_OWNER_VENDOR_HYP,			\
 			   ARM_SMCCC_KVM_FUNC_MEM_UNSHARE)
 
+#define ARM_SMCCC_VENDOR_HYP_KVM_MMIO_GUARD_FUNC_ID			\
+	ARM_SMCCC_CALL_VAL(ARM_SMCCC_FAST_CALL,				\
+			   ARM_SMCCC_SMC_64,				\
+			   ARM_SMCCC_OWNER_VENDOR_HYP,			\
+			   ARM_SMCCC_KVM_FUNC_MMIO_GUARD)
+
 /* ptp_kvm counter type ID */
 #define KVM_PTP_VIRT_COUNTER			0
 #define KVM_PTP_PHYS_COUNTER			1

---

## [8] Will Deacon — 2024-08-30
*Subject: [PATCH v2 7/7] arm64: smccc: Reserve block of KVM "vendor" services for pKVM hypercalls*

pKVM relies on hypercalls to expose services such as memory sharing to
protected guests. Tentatively allocate a block of 58 hypercalls (i.e.
fill the remaining space in the first 64 function IDs) for pKVM usage,
as future extensions such as pvIOMMU support, range-based memory sharing
and validation of assigned devices will require additional services.

Suggested-by: Marc Zyngier <maz@kernel.org>
Link: https://lore.kernel.org/r/86a5h5yg5y.wl-maz@kernel.org
Signed-off-by: Will Deacon <will@kernel.org>
---
 include/linux/arm-smccc.h | 60 +++++++++++++++++++++++++++++++++++++++
 1 file changed, 60 insertions(+)

diff --git a/include/linux/arm-smccc.h b/include/linux/arm-smccc.h
index e93c1f7cea70..f59099a213d0 100644
--- a/include/linux/arm-smccc.h
+++ b/include/linux/arm-smccc.h
@@ -115,10 +115,70 @@
 /* KVM "vendor specific" services */
 #define ARM_SMCCC_KVM_FUNC_FEATURES		0
 #define ARM_SMCCC_KVM_FUNC_PTP			1
+/* Start of pKVM hypercall range */
 #define ARM_SMCCC_KVM_FUNC_HYP_MEMINFO		2
 #define ARM_SMCCC_KVM_FUNC_MEM_SHARE		3
 #define ARM_SMCCC_KVM_FUNC_MEM_UNSHARE		4
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_5		5
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_6		6
 #define ARM_SMCCC_KVM_FUNC_MMIO_GUARD		7
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_8		8
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_9		9
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_10		10
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_11		11
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_12		12
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_13		13
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_14		14
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_15		15
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_16		16
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_17		17
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_18		18
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_19		19
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_20		20
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_21		21
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_22		22
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_23		23
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_24		24
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_25		25
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_26		26
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_27		27
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_28		28
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_29		29
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_30		30
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_31		31
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_32		32
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_33		33
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_34		34
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_35		35
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_36		36
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_37		37
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_38		38
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_39		39
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_40		40
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_41		41
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_42		42
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_43		43
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_44		44
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_45		45
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_46		46
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_47		47
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_48		48
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_49		49
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_50		50
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_51		51
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_52		52
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_53		53
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_54		54
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_55		55
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_56		56
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_57		57
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_58		58
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_59		59
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_60		60
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_61		61
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_62		62
+#define ARM_SMCCC_KVM_FUNC_PKVM_RESV_63		63
+/* End of pKVM hypercall range */
 #define ARM_SMCCC_KVM_FUNC_FEATURES_2		127
 #define ARM_SMCCC_KVM_NUM_FUNCS			128

---

## [9] Marc Zyngier — 2024-08-30
*Subject: Re: [PATCH v2 0/7] Support for running as a pKVM protected guest*

On Fri, 30 Aug 2024 14:01:43 +0100,
Will Deacon <will@kernel.org> wrote:
> 
> Hi all,

For patches 2-7:

Acked-by: Marc Zyngier <maz@kernel.org>

Thanks,

	M.

---

## [10] Steven Price — 2024-08-30
*Subject: Re: [PATCH v2 0/7] Support for running as a pKVM protected guest*

On 30/08/2024 14:01, Will Deacon wrote:
> Hi all,
> 

Indeed, for what it's worth, patches 3 and 5 are both:

Reviewed-by: Steven Price <steven.price@arm.com>

Thanks,
Steve

> Cheers,
>

---

## [11] Will Deacon — 2024-08-30
*Subject: Re: [PATCH v2 0/7] Support for running as a pKVM protected guest*

On Fri, 30 Aug 2024 14:01:43 +0100, Will Deacon wrote:
> This is version two of the series previously posted here:
> 

Applied to arm64 (for-next/pkvm-guest), thanks!

[1/7] firmware/smccc: Call arch-specific hook on discovering KVM services
      https://git.kernel.org/arm64/c/0ba5b4ba6178
[2/7] drivers/virt: pkvm: Add initial support for running as a protected guest
      https://git.kernel.org/arm64/c/a06c3fad49a5
[3/7] arm64: mm: Add top-level dispatcher for internal mem_encrypt API
      https://git.kernel.org/arm64/c/e7bafbf71777
[4/7] drivers/virt: pkvm: Hook up mem_encrypt API using pKVM hypercalls
      https://git.kernel.org/arm64/c/ebc59b120c58
[5/7] arm64: mm: Add confidential computing hook to ioremap_prot()
      https://git.kernel.org/arm64/c/c86fa3470c10
[6/7] drivers/virt: pkvm: Intercept ioremap using pKVM MMIO_GUARD hypercall
      https://git.kernel.org/arm64/c/0f1269495800
[7/7] arm64: smccc: Reserve block of KVM "vendor" services for pKVM hypercalls
      https://git.kernel.org/arm64/c/21be9f7110d4

Cheers,

---

## [12] Catalin Marinas — 2024-09-02
*Subject: Re: [PATCH v2 5/7] arm64: mm: Add confidential computing hook to
 ioremap_prot()*

On Fri, Aug 30, 2024 at 02:01:48PM +0100, Will Deacon wrote:
> @@ -16,7 +28,16 @@ void __iomem *ioremap_prot(phys_addr_t phys_addr, size_t size,
>  	if (WARN_ON(pfn_is_map_memory(__phys_to_pfn(phys_addr))))

I mentioned on the CCA series, the patch is all good but we may need
something similar for io_remap_pfn_range() which uses
pgprot_decrypted() (I think it mostly matters for the pKVM case).

---

## [13] Will Deacon — 2024-09-04
*Subject: Re: [PATCH v2 5/7] arm64: mm: Add confidential computing hook to
 ioremap_prot()*

On Mon, Sep 02, 2024 at 08:08:45PM +0100, Catalin Marinas wrote:
> On Fri, Aug 30, 2024 at 02:01:48PM +0100, Will Deacon wrote:
> > @@ -16,7 +28,16 @@ void __iomem *ioremap_prot(phys_addr_t phys_addr, size_t size,

Thanks for pointing this out.

We've not needed this on Android yet, but I think that it would be
pretty straightforward to add with an arm64 definition of
io_remap_pfn_range(). I'd just prefer to leave that until we know that
we need it -- in all likelihood a driver would MMIO_GUARD the resources
as part of its own ioremap() before remapping into userspace.

Will

---
