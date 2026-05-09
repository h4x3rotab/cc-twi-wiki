---
title: 'Support for running as a pKVM protected guest'
date: 2024-07-30
last_reply: 2024-08-23
message_count: 23
participants: ['Will Deacon', 'Aneesh Kumar K.V', 'Suzuki K Poulose', 'Catalin Marinas', 'Marc Zyngier']
---

## [1] Will Deacon — 2024-07-30

Hi folks,

Since the patches for running as a CCA guest were posted already at [1],
I figured it was worth posting the equivalent pKVM changes needed to run
as a protected guest under an Android host kernel. In particular, I've
tried to structure the code so that the CCA patches can use the same
hooks. I'd welcome feedback from the CCA developers (i.e. Steven and
Suzuki) as to whether this is sufficient.

There are also some pKVM-specific details which are worth discussion:

  * I've kept the code compatible with Android, so these patches allow
    an upstream kernel to run as a protected guest on a production
    (unlocked) Android device. This seemed like a good property for v1,
    but I'm happy to break compatibility if folks prefer a cleaner
    interface (e.g. using consecutive hypercall numbers).

  * I've included only the hypercalls that are necessary for a
    functioning guest. Android has some others, but I'd prefer to land
    the host support upstream before we expose optional interfaces as
    ABI.

  * For now, the stage-2 page size cannot be larger than the guest
    stage-1 page size otherwise the guest will fail to boot.

  * I don't forcefully configure SWIOTLB, as we rely on Restricted DMA
    pools (CONFIG_DMA_RESTRICTED_POOL) for devices that need it.

I also pushed a branch at [2] based on -rc1.

Cheers,

Will

[1] https://lore.kernel.org/r/20240701095505.165383-1-steven.price@arm.com
[2] git://git.kernel.org/pub/scm/linux/kernel/git/will/linux.git kvm/protected-guest

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

Will Deacon (5):
  drivers/virt: pkvm: Add initial support for running as a protected
    guest
  arm64: mm: Add top-level dispatcher for internal mem_encrypt API
  drivers/virt: pkvm: Hook up mem_encrypt API using pKVM hypercalls
  arm64: mm: Add confidential computing hook to ioremap_prot()
  drivers/virt: pkvm: Intercept ioremap using pKVM MMIO_GUARD hypercall

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
 include/linux/arm-smccc.h                     |  28 ++++
 17 files changed, 377 insertions(+), 2 deletions(-)
 create mode 100644 arch/arm64/include/asm/mem_encrypt.h
 create mode 100644 arch/arm64/mm/mem_encrypt.c
 create mode 100644 drivers/virt/coco/pkvm-guest/Kconfig
 create mode 100644 drivers/virt/coco/pkvm-guest/Makefile
 create mode 100644 drivers/virt/coco/pkvm-guest/arm-pkvm-guest.c

---

## [2] Will Deacon — 2024-07-30
*Subject: [PATCH 1/6] firmware/smccc: Call arch-specific hook on discovering KVM services*

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

## [3] Will Deacon — 2024-07-30
*Subject: [PATCH 2/6] drivers/virt: pkvm: Add initial support for running as a protected guest*

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

## [4] Will Deacon — 2024-07-30
*Subject: [PATCH 3/6] arm64: mm: Add top-level dispatcher for internal mem_encrypt API*

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
index b3fc891f1544..68d77a2f4d1a 100644
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

## [5] Will Deacon — 2024-07-30
*Subject: [PATCH 4/6] drivers/virt: pkvm: Hook up mem_encrypt API using pKVM hypercalls*

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

## [6] Will Deacon — 2024-07-30
*Subject: [PATCH 5/6] arm64: mm: Add confidential computing hook to ioremap_prot()*

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

## [7] Will Deacon — 2024-07-30
*Subject: [PATCH 6/6] drivers/virt: pkvm: Intercept ioremap using pKVM MMIO_GUARD hypercall*

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

## [8] Aneesh Kumar K.V — 2024-07-31
*Subject: Re: [PATCH 6/6] drivers/virt: pkvm: Intercept ioremap using pKVM
 MMIO_GUARD hypercall*

Will Deacon <will@kernel.org> writes:

> Hook up pKVM's MMIO_GUARD hypercall so that ioremap() and friends will
> register the target physical address as MMIO with the hypervisor,

Ok you need a SMCCC call not just a pgprot_t update. 

> diff --git a/drivers/virt/coco/pkvm-guest/arm-pkvm-guest.c b/drivers/virt/coco/pkvm-guest/arm-pkvm-guest.c
> index 8256cf68fd76..56a3859dda8a 100644

---

## [9] Suzuki K Poulose — 2024-07-31
*Subject: Re: [PATCH 0/6] Support for running as a pKVM protected guest*

Hi Will,

On 30/07/2024 16:11, Will Deacon wrote:
> Hi folks,
> 

Thanks for the patches ! The hooks for set_memory_*crypted() and the
ioremap_prot() looks fitting for the CCA support. We will cherry pick
those and base our next version on it. On a side note, this doesn't
solve the "fixmap" for earlycon. Hopefully, we can push something
based on this in the coming weeks.

Kind regards
Suzuki

> 
> There are also some pKVM-specific details which are worth discussion:

---

## [10] Aneesh Kumar K.V — 2024-07-31
*Subject: Re: [PATCH 1/6] firmware/smccc: Call arch-specific hook on
 discovering KVM services*

Will Deacon <will@kernel.org> writes:

> From: Marc Zyngier <maz@kernel.org>
>

That is a bit late to detect RMM? One of the requirements is to
figure out the pgprot_t flags for early_ioremap so that "earlycon" will
work (by mapping the address as shared alias). To do that we need to
make an RSI call to detect PROT_NS_SHARED mask as below. 

	if (rsi_get_realm_config(&config))
		return;
	prot_ns_shared = BIT(config.ipa_bits - 1);

-aneesh

---

## [11] Will Deacon — 2024-07-31
*Subject: Re: [PATCH 1/6] firmware/smccc: Call arch-specific hook on
 discovering KVM services*

On Wed, Jul 31, 2024 at 08:11:16PM +0530, Aneesh Kumar K.V wrote:
> Will Deacon <will@kernel.org> writes:
> 

Why can't the earlycon MMIO address just have that high bit set?

I think it's horribly fragile to try detecting all of this stuff before
we're allowed to touch the console. We don't even bother with pKVM --
it's the guest firmware's responsibility to MMIO_GUARD the UART if it
detects a debuggable payload.

Will

---

## [12] Will Deacon — 2024-07-31
*Subject: Re: [PATCH 0/6] Support for running as a pKVM protected guest*

On Wed, Jul 31, 2024 at 02:55:13PM +0100, Suzuki K Poulose wrote:
> On 30/07/2024 16:11, Will Deacon wrote:
> > Since the patches for running as a CCA guest were posted already at [1],

See my reply to Aneesh about 'earlycon' (and why we don't care for pKVM).
Hopefully the rest of the stuff is helpful, though.

Will

---

## [13] Aneesh Kumar K.V — 2024-07-31
*Subject: Re: [PATCH 1/6] firmware/smccc: Call arch-specific hook on
 discovering KVM services*

Will Deacon <will@kernel.org> writes:

> On Wed, Jul 31, 2024 at 08:11:16PM +0530, Aneesh Kumar K.V wrote:
>> Will Deacon <will@kernel.org> writes:

To mark something shared, we need to know the mask value which is
returned via rsi_get_realm_config() call.

-aneesh

---

## [14] Aneesh Kumar K.V — 2024-07-31
*Subject: Re: [PATCH 1/6] firmware/smccc: Call arch-specific hook on
 discovering KVM services*

Aneesh Kumar K.V <aneesh.kumar@kernel.org> writes:

> Will Deacon <will@kernel.org> writes:
>

I guess you are suggesting to leave it to firmware to set up the device
tree "reg-offset" with shared bit set?

-aneesh

---

## [15] Catalin Marinas — 2024-08-02
*Subject: Re: [PATCH 1/6] firmware/smccc: Call arch-specific hook on
 discovering KVM services*

On Wed, Jul 31, 2024 at 08:11:16PM +0530, Aneesh Kumar K.V wrote:
> Will Deacon <will@kernel.org> writes:
> > diff --git a/drivers/firmware/smccc/kvm_guest.c b/drivers/firmware/smccc/kvm_guest.c

It may be late for RMM but I'm not sure that's relevant. This function
is about KVM services provided to a guest. The RMM is meant (in theory
at least) to be hypervisor-agnostic. We shouldn't place any realm guest
initialisation in the kvm_guest.c file.

---

## [16] Suzuki K Poulose — 2024-08-02
*Subject: Re: [PATCH 1/6] firmware/smccc: Call arch-specific hook on
 discovering KVM services*

On 31/07/2024 16:50, Will Deacon wrote:
> On Wed, Jul 31, 2024 at 08:11:16PM +0530, Aneesh Kumar K.V wrote:
>> Will Deacon <will@kernel.org> writes:

Do you mean the "earlycon=<MMIO-address-to-use>" ? That could work,
except that :
1. It breaks the Realm's view of the {I}"PA" space
2. If the address is missed, it is fatal for the Realm.
3. All higher level tools that specify the command line parameter now
    need to fixup the "MMIO" address, based on the "ipa_bits" chosen by
    the VMM (which could vary with the VMMs and Hyp/System)

Also, we are making some changes to the guest support to make it future
proof for running the same guest in a less privileged context within
R_EL1 (read unprivileged plane with RMM v1.1), where the console
could be "private". And we are modifying the code to "apply" the prot_ns
dynamically (instead of hard coding it for all I/O).

Suzuki

> 
> I think it's horribly fragile to try detecting all of this stuff before

---

## [17] Catalin Marinas — 2024-08-02
*Subject: Re: [PATCH 1/6] firmware/smccc: Call arch-specific hook on
 discovering KVM services*

On Wed, Jul 31, 2024 at 09:26:31PM +0530, Aneesh Kumar K.V wrote:
> Aneesh Kumar K.V <aneesh.kumar@kernel.org> writes:
> > Will Deacon <will@kernel.org> writes:

As you know, we've been through these options internally and we
concluded not to encode this information in the DT for various reasons.

Personally I don't like this IPA split but that's too late to change it
now in the RMM spec.

---

## [18] Aneesh Kumar K.V — 2024-08-02
*Subject: Re: [PATCH 1/6] firmware/smccc: Call arch-specific hook on
 discovering KVM services*

Catalin Marinas <catalin.marinas@arm.com> writes:

> On Wed, Jul 31, 2024 at 09:26:31PM +0530, Aneesh Kumar K.V wrote:
>> Aneesh Kumar K.V <aneesh.kumar@kernel.org> writes:

I was trying to find out what a guest firmware-based control means.

>
> Personally I don't like this IPA split but that's too late to change it

Agreed. This also makes supporting both secure and non secure devices
difficult.

-aneesh

---

## [19] Suzuki K Poulose — 2024-08-07
*Subject: Re: [PATCH 1/6] firmware/smccc: Call arch-specific hook on
 discovering KVM services*

On 02/08/2024 16:30, Suzuki K Poulose wrote:
> On 31/07/2024 16:50, Will Deacon wrote:
>> On Wed, Jul 31, 2024 at 08:11:16PM +0530, Aneesh Kumar K.V wrote:

Also, forgot to add, we do need this for EFI runtim services where EFI
mapping may need to apply the "Shared" bit for MMIO.


See:

https://lore.kernel.org/all/20240701095505.165383-12-steven.price@arm.com/

Suzuki


> 
> Suzuki

---

## [20] Marc Zyngier — 2024-08-21
*Subject: Re: [PATCH 4/6] drivers/virt: pkvm: Hook up mem_encrypt API using pKVM hypercalls*

On Tue, 30 Jul 2024 16:11:10 +0100,
Will Deacon <will@kernel.org> wrote:
> 
> If we detect the presence of pKVM's SHARE and UNSHARE hypercalls, then

[...]

> diff --git a/include/linux/arm-smccc.h b/include/linux/arm-smccc.h
> index 16b6dcc54e02..9cb7c95920b0 100644

As you will certainly add a bunch of other calls (hopefully soon-ish),
how about reserving an actual range for those, so that we can
future-proof the ABI early?

Grab 64 right away, and we don't have to worry about new stuff for a
while.

What do you think?

	M.

---

## [21] Will Deacon — 2024-08-23
*Subject: Re: [PATCH 1/6] firmware/smccc: Call arch-specific hook on
 discovering KVM services*

On Fri, Aug 02, 2024 at 04:30:30PM +0100, Suzuki K Poulose wrote:
> On 31/07/2024 16:50, Will Deacon wrote:
> > On Wed, Jul 31, 2024 at 08:11:16PM +0530, Aneesh Kumar K.V wrote:

Breaks in what sense? It won't work?

> 2. If the address is missed, it is fatal for the Realm.

If earlycon= has broken/missing addresses, it's going to be fatal for
whoever is consuming it anyway, no?

> 3. All higher level tools that specify the command line parameter now
>    need to fixup the "MMIO" address, based on the "ipa_bits" chosen by

Should be fine for earlycon, though?

If not, then perhaps the RSI should include calls for putchar() so that
earlycon can be implemented using a service rather than trying to use
MMIO with a bunch of awkward caveats.

Will

---

## [22] Will Deacon — 2024-08-23
*Subject: Re: [PATCH 4/6] drivers/virt: pkvm: Hook up mem_encrypt API using
 pKVM hypercalls*

Hi Marc,

On Wed, Aug 21, 2024 at 05:49:45PM +0100, Marc Zyngier wrote:
> On Tue, 30 Jul 2024 16:11:10 +0100,
> Will Deacon <will@kernel.org> wrote:

I think that's incredibly generous. Let's see whether we really need
that to start with...

/me dives into android15-6.6

So we currently allocate 3-11 there and some of those are because we
messed up v1 of a hypercall and had to introduce a new one. I don't plan
to inflict that on upstream, but avoiding conflicts would be good.

The big thing on the horizon is a hypercall-based IOMMU interface which
looks like it will need ~10 new calls. I suppose we could multiplex some
of that, but otherwise 32 would probably do us if you don't want to give
up such a big chunk of the space immediately.

Will

---

## [23] Marc Zyngier — 2024-08-23
*Subject: Re: [PATCH 4/6] drivers/virt: pkvm: Hook up mem_encrypt API using pKVM hypercalls*

On Fri, 23 Aug 2024 16:41:55 +0100,
Will Deacon <will@kernel.org> wrote:
> 
> Hi Marc,

Honestly, whatever number of bits you have in mind, just double it and
run with it. We don't need to be precious about those, specially given
that bog-standard KVM is unlikely to grow any new PV hypercall (PTP
was enough of a disaster to cure me from that disease).

Thanks,

	M.

---
