---
title: 'arm64: Support for running as a guest in Arm CCA'
date: 2024-08-19
last_reply: 2024-10-17
message_count: 67
participants: ['Steven Price', 'Suzuki K Poulose', 'Marc Zyngier', 'Will Deacon', 'Catalin Marinas', 'Aneesh Kumar K.V', 'Gavin Shan', 'Shanker Donthineni', 'Matias Ezequiel Vara Larsen']
---

## [1] Steven Price — 2024-08-19

This series adds support for running Linux in a protected VM under the
Arm Confidential Compute Architecture (CCA). This has been updated
following the feedback from the v4 posting[1]. Thanks for the feedback!
Individual patches have a change log. But things to highlight:

 * New RMM spec version[2] (v1.0-rel0-rc1). Note that this makes a
   number of (small) breaking changes so you will need to update the RMM
   and host too (see below).

 * 'Borrowed' two commits by Will from the pKVM series which add a
   dispatcher/hook for mem_encrypt and ioremap. These will hopefully
   make it easier for CCA to live alongside pKVM.

 * Reworked the code for handling protected/shared MMIO. The new RMM
   spec adds a new state (RIPAS_IO - although that may get renamed),
   which is currently unused, but will be used in a later version to
   signify that a granule is backed by a protected hardware MMIO region.
   Using this we can now identify whether the top bit should be set when
   performing an ioremap (or similar).

The ABI to the RMM from a realm (the RSI) is based on the RMM
v1.0-rel0-rc1 specification[2]. Future RMM specifications after v1.0
will be backwards compatible so a guest using the v1.0 specification
(i.e. this series) will be able to run on future versions of the RMM
without modification.

This series is based on v6.11-rc1. It is also available as a git
repository:

https://gitlab.arm.com/linux-arm/linux-cca cca-guest/v5

As mentioned above the new RMM specification means that corresponding
changes need to be made in the RMM, at this time these changes are still
in review (see 'topics/rmm-1.0-rel0-rc1'). So you'll need to fetch the
changes[3] from the gerrit instance until they are pushed to the main
branch.

It has also been pointed out that some documentation would be a good
idea - I'm afraid it hasn't made this version, but I didn't want to hold
off posting for any longer.

The new version of the RMM also means you'll need to update the host
support, a v4 of the host changes will be posted soon, in the mean time
the code is available from git here:

https://gitlab.arm.com/linux-arm/linux-cca cca-host/v4

[1] https://lore.kernel.org/r/20240701095505.165383-1-steven.price%40arm.com
[2] https://developer.arm.com/-/cdn-downloads/permalink/PDF/Architectures/DEN0137_1.0-rel0-rc1_rmm-arch_external.pdf
[3] https://review.trustedfirmware.org/c/TF-RMM/tf-rmm/+/30485

Jean-Philippe Brucker (1):
  firmware/psci: Add psci_early_test_conduit()

Sami Mujawar (1):
  virt: arm-cca-guest: TSM_REPORT support for realms

Steven Price (6):
  arm64: realm: Query IPA size from the RMM
  arm64: Make the PHYS_MASK_SHIFT dynamic
  arm64: Enforce bounce buffers for realm DMA
  arm64: mm: Avoid TLBI when marking pages as valid
  irqchip/gic-v3-its: Share ITS tables with a non-trusted hypervisor
  irqchip/gic-v3-its: Rely on genpool alignment

Suzuki K Poulose (9):
  arm64: rsi: Add RSI definitions
  arm64: Detect if in a realm and set RIPAS RAM
  arm64: rsi: Add support for checking whether an MMIO is protected
  fixmap: Allow architecture overriding set_fixmap_io
  fixmap: Pass down the full phys address for set_fixmap_io
  arm64: Override set_fixmap_io
  arm64: rsi: Map unprotected MMIO as decrypted
  efi: arm64: Map Device with Prot Shared
  arm64: Enable memory encrypt for Realms

Will Deacon (2):
  arm64: mm: Add top-level dispatcher for internal mem_encrypt API
  arm64: mm: Add confidential computing hook to ioremap_prot()

 arch/arm64/Kconfig                            |   4 +
 arch/arm64/include/asm/fixmap.h               |   2 +
 arch/arm64/include/asm/io.h                   |  12 +
 arch/arm64/include/asm/mem_encrypt.h          |  24 ++
 arch/arm64/include/asm/pgtable-hwdef.h        |   6 -
 arch/arm64/include/asm/pgtable-prot.h         |   4 +
 arch/arm64/include/asm/pgtable.h              |  10 +
 arch/arm64/include/asm/rsi.h                  |  68 ++++++
 arch/arm64/include/asm/rsi_cmds.h             | 157 +++++++++++++
 arch/arm64/include/asm/rsi_smc.h              | 189 ++++++++++++++++
 arch/arm64/include/asm/set_memory.h           |   4 +
 arch/arm64/kernel/Makefile                    |   3 +-
 arch/arm64/kernel/efi.c                       |  12 +-
 arch/arm64/kernel/rsi.c                       | 149 +++++++++++++
 arch/arm64/kernel/setup.c                     |   8 +
 arch/arm64/mm/Makefile                        |   2 +-
 arch/arm64/mm/init.c                          |  10 +-
 arch/arm64/mm/ioremap.c                       |  23 +-
 arch/arm64/mm/mem_encrypt.c                   |  50 +++++
 arch/arm64/mm/mmu.c                           |  17 ++
 arch/arm64/mm/pageattr.c                      |  84 ++++++-
 drivers/firmware/psci/psci.c                  |  25 +++
 drivers/irqchip/irq-gic-v3-its.c              | 142 +++++++++---
 drivers/tty/serial/earlycon.c                 |   2 +-
 drivers/virt/coco/Kconfig                     |   2 +
 drivers/virt/coco/Makefile                    |   1 +
 drivers/virt/coco/arm-cca-guest/Kconfig       |  11 +
 drivers/virt/coco/arm-cca-guest/Makefile      |   2 +
 .../virt/coco/arm-cca-guest/arm-cca-guest.c   | 211 ++++++++++++++++++
 include/asm-generic/fixmap.h                  |   4 +-
 include/linux/psci.h                          |   5 +
 31 files changed, 1200 insertions(+), 43 deletions(-)
 create mode 100644 arch/arm64/include/asm/mem_encrypt.h
 create mode 100644 arch/arm64/include/asm/rsi.h
 create mode 100644 arch/arm64/include/asm/rsi_cmds.h
 create mode 100644 arch/arm64/include/asm/rsi_smc.h
 create mode 100644 arch/arm64/kernel/rsi.c
 create mode 100644 arch/arm64/mm/mem_encrypt.c
 create mode 100644 drivers/virt/coco/arm-cca-guest/Kconfig
 create mode 100644 drivers/virt/coco/arm-cca-guest/Makefile
 create mode 100644 drivers/virt/coco/arm-cca-guest/arm-cca-guest.c

---

## [2] Steven Price — 2024-08-19
*Subject: [PATCH v5 01/19] arm64: mm: Add top-level dispatcher for internal mem_encrypt API*

From: Will Deacon <will@kernel.org>

Implementing the internal mem_encrypt API for arm64 depends entirely on
the Confidential Computing environment in which the kernel is running.

Introduce a simple dispatcher so that backend hooks can be registered
depending upon the environment in which the kernel finds itself.

Signed-off-by: Will Deacon <will@kernel.org>
Signed-off-by: Steven Price <steven.price@arm.com>
---
Patch 'borrowed' from Will's series for pKVM:
https://lore.kernel.org/r/20240730151113.1497-4-will%40kernel.org
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

## [3] Steven Price — 2024-08-19
*Subject: [PATCH v5 02/19] arm64: mm: Add confidential computing hook to ioremap_prot()*

From: Will Deacon <will@kernel.org>

Confidential Computing environments such as pKVM and Arm's CCA
distinguish between shared (i.e. emulated) and private (i.e. assigned)
MMIO regions.

Introduce a hook into our implementation of ioremap_prot() so that MMIO
regions can be shared if necessary.

Signed-off-by: Will Deacon <will@kernel.org>
Signed-off-by: Steven Price <steven.price@arm.com>
---
Patch 'borrowed' from Will's series for pKVM:
https://lore.kernel.org/r/20240730151113.1497-6-will%40kernel.org
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

## [4] Steven Price — 2024-08-19
*Subject: [PATCH v5 03/19] arm64: rsi: Add RSI definitions*

From: Suzuki K Poulose <suzuki.poulose@arm.com>

The RMM (Realm Management Monitor) provides functionality that can be
accessed by a realm guest through SMC (Realm Services Interface) calls.

The SMC definitions are based on DEN0137[1] version 1.0-rel0-rc1.

[1] https://developer.arm.com/-/cdn-downloads/permalink/PDF/Architectures/DEN0137_1.0-rel0-rc1_rmm-arch_external.pdf

Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v4:
 * Update to match the latest RMM spec version 1.0-rel0-rc1.
 * Make use of the ARM_SMCCC_CALL_VAL macro.
 * Cast using (_UL macro) various values to unsigned long.
Changes since v3:
 * Drop invoke_rsi_fn_smc_with_res() function and call arm_smccc_smc()
   directly instead.
 * Rename header guard in rsi_smc.h to be consistent.
Changes since v2:
 * Rename rsi_get_version() to rsi_request_version()
 * Fix size/alignment of struct realm_config
---
 arch/arm64/include/asm/rsi_cmds.h | 136 +++++++++++++++++++++
 arch/arm64/include/asm/rsi_smc.h  | 189 ++++++++++++++++++++++++++++++
 2 files changed, 325 insertions(+)
 create mode 100644 arch/arm64/include/asm/rsi_cmds.h
 create mode 100644 arch/arm64/include/asm/rsi_smc.h

diff --git a/arch/arm64/include/asm/rsi_cmds.h b/arch/arm64/include/asm/rsi_cmds.h
new file mode 100644
index 000000000000..968b03f4e703
--- /dev/null
+++ b/arch/arm64/include/asm/rsi_cmds.h
@@ -0,0 +1,136 @@
+/* SPDX-License-Identifier: GPL-2.0-only */
+/*
+ * Copyright (C) 2023 ARM Ltd.
+ */
+
+#ifndef __ASM_RSI_CMDS_H
+#define __ASM_RSI_CMDS_H
+
+#include <linux/arm-smccc.h>
+
+#include <asm/rsi_smc.h>
+
+#define RSI_GRANULE_SHIFT		12
+#define RSI_GRANULE_SIZE		(_AC(1, UL) << RSI_GRANULE_SHIFT)
+
+enum ripas {
+	RSI_RIPAS_EMPTY = 0,
+	RSI_RIPAS_RAM = 1,
+	RSI_RIPAS_DESTROYED = 2,
+	RSI_RIPAS_IO = 3,
+};
+
+static inline unsigned long rsi_request_version(unsigned long req,
+						unsigned long *out_lower,
+						unsigned long *out_higher)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_smc(SMC_RSI_ABI_VERSION, req, 0, 0, 0, 0, 0, 0, &res);
+
+	if (out_lower)
+		*out_lower = res.a1;
+	if (out_higher)
+		*out_higher = res.a2;
+
+	return res.a0;
+}
+
+static inline unsigned long rsi_get_realm_config(struct realm_config *cfg)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_smc(SMC_RSI_REALM_CONFIG, virt_to_phys(cfg),
+		      0, 0, 0, 0, 0, 0, &res);
+	return res.a0;
+}
+
+static inline unsigned long rsi_set_addr_range_state(phys_addr_t start,
+						     phys_addr_t end,
+						     enum ripas state,
+						     unsigned long flags,
+						     phys_addr_t *top)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_smc(SMC_RSI_IPA_STATE_SET, start, end, state,
+		      flags, 0, 0, 0, &res);
+
+	if (top)
+		*top = res.a1;
+
+	return res.a0;
+}
+
+/**
+ * rsi_attestation_token_init - Initialise the operation to retrieve an
+ * attestation token.
+ *
+ * @challenge:	The challenge data to be used in the attestation token
+ *		generation.
+ * @size:	Size of the challenge data in bytes.
+ *
+ * Initialises the attestation token generation and returns an upper bound
+ * on the attestation token size that can be used to allocate an adequate
+ * buffer. The caller is expected to subsequently call
+ * rsi_attestation_token_continue() to retrieve the attestation token data on
+ * the same CPU.
+ *
+ * Returns:
+ *  On success, returns the upper limit of the attestation report size.
+ *  Otherwise, -EINVAL
+ */
+static inline unsigned long
+rsi_attestation_token_init(const u8 *challenge, unsigned long size)
+{
+	struct arm_smccc_1_2_regs regs = { 0 };
+
+	/* The challenge must be at least 32bytes and at most 64bytes */
+	if (!challenge || size < 32 || size > 64)
+		return -EINVAL;
+
+	regs.a0 = SMC_RSI_ATTESTATION_TOKEN_INIT;
+	memcpy(&regs.a1, challenge, size);
+	arm_smccc_1_2_smc(&regs, &regs);
+
+	if (regs.a0 == RSI_SUCCESS)
+		return regs.a1;
+
+	return -EINVAL;
+}
+
+/**
+ * rsi_attestation_token_continue - Continue the operation to retrieve an
+ * attestation token.
+ *
+ * @granule: {I}PA of the Granule to which the token will be written.
+ * @offset:  Offset within Granule to start of buffer in bytes.
+ * @size:    The size of the buffer.
+ * @len:     The number of bytes written to the buffer.
+ *
+ * Retrieves up to a RSI_GRANULE_SIZE worth of token data per call. The caller
+ * is expected to call rsi_attestation_token_init() before calling this
+ * function to retrieve the attestation token.
+ *
+ * Return:
+ * * %RSI_SUCCESS     - Attestation token retrieved successfully.
+ * * %RSI_INCOMPLETE  - Token generation is not complete.
+ * * %RSI_ERROR_INPUT - A parameter was not valid.
+ * * %RSI_ERROR_STATE - Attestation not in progress.
+ */
+static inline int rsi_attestation_token_continue(phys_addr_t granule,
+						 unsigned long offset,
+						 unsigned long size,
+						 unsigned long *len)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RSI_ATTESTATION_TOKEN_CONTINUE,
+			     granule, offset, size, 0, &res);
+
+	if (len)
+		*len = res.a1;
+	return res.a0;
+}
+
+#endif /* __ASM_RSI_CMDS_H */
diff --git a/arch/arm64/include/asm/rsi_smc.h b/arch/arm64/include/asm/rsi_smc.h
new file mode 100644
index 000000000000..b76b03a8fea8
--- /dev/null
+++ b/arch/arm64/include/asm/rsi_smc.h
@@ -0,0 +1,189 @@
+/* SPDX-License-Identifier: GPL-2.0-only */
+/*
+ * Copyright (C) 2023 ARM Ltd.
+ */
+
+#ifndef __ASM_RSI_SMC_H_
+#define __ASM_RSI_SMC_H_
+
+#include <linux/arm-smccc.h>
+
+/*
+ * This file describes the Realm Services Interface (RSI) Application Binary
+ * Interface (ABI) for SMC calls made from within the Realm to the RMM and
+ * serviced by the RMM.
+ */
+
+/*
+ * The major version number of the RSI implementation.  This is increased when
+ * the binary format or semantics of the SMC calls change.
+ */
+#define RSI_ABI_VERSION_MAJOR		UL(1)
+
+/*
+ * The minor version number of the RSI implementation.  This is increased when
+ * a bug is fixed, or a feature is added without breaking binary compatibility.
+ */
+#define RSI_ABI_VERSION_MINOR		UL(0)
+
+#define RSI_ABI_VERSION			((RSI_ABI_VERSION_MAJOR << 16) | \
+					 RSI_ABI_VERSION_MINOR)
+
+#define RSI_ABI_VERSION_GET_MAJOR(_version) ((_version) >> 16)
+#define RSI_ABI_VERSION_GET_MINOR(_version) ((_version) & 0xFFFF)
+
+#define RSI_SUCCESS		UL(0)
+#define RSI_ERROR_INPUT		UL(1)
+#define RSI_ERROR_STATE		UL(2)
+#define RSI_INCOMPLETE		UL(3)
+#define RSI_ERROR_UNKNOWN	UL(4)
+
+#define SMC_RSI_FID(n)		ARM_SMCCC_CALL_VAL(ARM_SMCCC_FAST_CALL,      \
+						   ARM_SMCCC_SMC_64,         \
+						   ARM_SMCCC_OWNER_STANDARD, \
+						   n)
+
+/*
+ * Returns RSI version.
+ *
+ * arg1 == Requested interface revision
+ * ret0 == Status /error
+ * ret1 == Lower implemented interface revision
+ * ret2 == Higher implemented interface revision
+ */
+#define SMC_RSI_ABI_VERSION	SMC_RSI_FID(0x190)
+
+/*
+ * Read feature register.
+ *
+ * arg1 == Feature register index
+ * ret0 == Status /error
+ * ret1 == Feature register value
+ */
+#define SMC_RSI_FEATURES			SMC_RSI_FID(0x191)
+
+/*
+ * Read measurement for the current Realm.
+ *
+ * arg1 == Index, which measurements slot to read
+ * ret0 == Status / error
+ * ret1 == Measurement value, bytes:  0 -  7
+ * ret2 == Measurement value, bytes:  7 - 15
+ * ret3 == Measurement value, bytes: 16 - 23
+ * ret4 == Measurement value, bytes: 24 - 31
+ * ret5 == Measurement value, bytes: 32 - 39
+ * ret6 == Measurement value, bytes: 40 - 47
+ * ret7 == Measurement value, bytes: 48 - 55
+ * ret8 == Measurement value, bytes: 56 - 63
+ */
+#define SMC_RSI_MEASUREMENT_READ		SMC_RSI_FID(0x192)
+
+/*
+ * Extend Realm Extensible Measurement (REM) value.
+ *
+ * arg1  == Index, which measurements slot to extend
+ * arg2  == Size of realm measurement in bytes, max 64 bytes
+ * arg3  == Measurement value, bytes:  0 -  7
+ * arg4  == Measurement value, bytes:  7 - 15
+ * arg5  == Measurement value, bytes: 16 - 23
+ * arg6  == Measurement value, bytes: 24 - 31
+ * arg7  == Measurement value, bytes: 32 - 39
+ * arg8  == Measurement value, bytes: 40 - 47
+ * arg9  == Measurement value, bytes: 48 - 55
+ * arg10 == Measurement value, bytes: 56 - 63
+ * ret0  == Status / error
+ */
+#define SMC_RSI_MEASUREMENT_EXTEND		SMC_RSI_FID(0x193)
+
+/*
+ * Initialize the operation to retrieve an attestation token.
+ *
+ * arg1 == Challenge value, bytes:  0 -  7
+ * arg2 == Challenge value, bytes:  7 - 15
+ * arg3 == Challenge value, bytes: 16 - 23
+ * arg4 == Challenge value, bytes: 24 - 31
+ * arg5 == Challenge value, bytes: 32 - 39
+ * arg6 == Challenge value, bytes: 40 - 47
+ * arg7 == Challenge value, bytes: 48 - 55
+ * arg8 == Challenge value, bytes: 56 - 63
+ * ret0 == Status / error
+ * ret1 == Upper bound of token size in bytes
+ */
+#define SMC_RSI_ATTESTATION_TOKEN_INIT		SMC_RSI_FID(0x194)
+
+/*
+ * Continue the operation to retrieve an attestation token.
+ *
+ * arg1 == The IPA of token buffer
+ * arg2 == Offset within the granule of the token buffer
+ * arg3 == Size of the granule buffer
+ * ret0 == Status / error
+ * ret1 == Length of token bytes copied to the granule buffer
+ */
+#define SMC_RSI_ATTESTATION_TOKEN_CONTINUE	SMC_RSI_FID(0x195)
+
+#ifndef __ASSEMBLY__
+
+struct realm_config {
+	union {
+		struct {
+			unsigned long ipa_bits; /* Width of IPA in bits */
+			unsigned long hash_algo; /* Hash algorithm */
+		};
+		u8 pad[0x200];
+	};
+	union {
+		u8 rpv[64]; /* Realm Personalization Value */
+		u8 pad2[0xe00];
+	};
+	/*
+	 * The RMM requires the configuration structure to be aligned to a 4k
+	 * boundary, ensure this happens by aligning this structure.
+	 */
+} __aligned(0x1000);
+
+#endif /* __ASSEMBLY__ */
+
+/*
+ * Read configuration for the current Realm.
+ *
+ * arg1 == struct realm_config addr
+ * ret0 == Status / error
+ */
+#define SMC_RSI_REALM_CONFIG			SMC_RSI_FID(0x196)
+
+/*
+ * Request RIPAS of a target IPA range to be changed to a specified value.
+ *
+ * arg1 == Base IPA address of target region
+ * arg2 == Top of the region
+ * arg3 == RIPAS value
+ * arg4 == flags
+ * ret0 == Status / error
+ * ret1 == Top of modified IPA range
+ */
+#define SMC_RSI_IPA_STATE_SET			SMC_RSI_FID(0x197)
+
+#define RSI_NO_CHANGE_DESTROYED			UL(0)
+#define RSI_CHANGE_DESTROYED			UL(1)
+
+/*
+ * Get RIPAS of a target IPA range.
+ *
+ * arg1 == Base IPA of target region
+ * arg2 == End of target IPA region
+ * ret0 == Status / error
+ * ret1 == Top of IPA region which has the reported RIPAS value
+ * ret2 == RIPAS value
+ */
+#define SMC_RSI_IPA_STATE_GET			SMC_RSI_FID(0x198)
+
+/*
+ * Make a Host call.
+ *
+ * arg1 == IPA of host call structure
+ * ret0 == Status / error
+ */
+#define SMC_RSI_HOST_CALL			SMC_RSI_FID(0x199)
+
+#endif /* __ASM_RSI_SMC_H_ */

---

## [5] Steven Price — 2024-08-19
*Subject: [PATCH v5 04/19] firmware/psci: Add psci_early_test_conduit()*

From: Jean-Philippe Brucker <jean-philippe@linaro.org>

Add a function to test early if PSCI is present and what conduit it
uses. Because the PSCI conduit corresponds to the SMCCC one, this will
let the kernel know whether it can use SMC instructions to discuss with
the Realm Management Monitor (RMM), early enough to enable RAM and
serial access when running in a Realm.

Signed-off-by: Jean-Philippe Brucker <jean-philippe@linaro.org>
Signed-off-by: Steven Price <steven.price@arm.com>
---
v4: New patch
---
 drivers/firmware/psci/psci.c | 25 +++++++++++++++++++++++++
 include/linux/psci.h         |  5 +++++
 2 files changed, 30 insertions(+)

diff --git a/drivers/firmware/psci/psci.c b/drivers/firmware/psci/psci.c
index 2328ca58bba6..2b308f97ef2c 100644
--- a/drivers/firmware/psci/psci.c
+++ b/drivers/firmware/psci/psci.c
@@ -13,6 +13,7 @@
 #include <linux/errno.h>
 #include <linux/linkage.h>
 #include <linux/of.h>
+#include <linux/of_fdt.h>
 #include <linux/pm.h>
 #include <linux/printk.h>
 #include <linux/psci.h>
@@ -769,6 +770,30 @@ int __init psci_dt_init(void)
 	return ret;
 }
 
+/*
+ * Test early if PSCI is supported, and if its conduit matches @conduit
+ */
+bool __init psci_early_test_conduit(enum arm_smccc_conduit conduit)
+{
+	int len;
+	int psci_node;
+	const char *method;
+	unsigned long dt_root;
+
+	/* DT hasn't been unflattened yet, we have to work with the flat blob */
+	dt_root = of_get_flat_dt_root();
+	psci_node = of_get_flat_dt_subnode_by_name(dt_root, "psci");
+	if (psci_node <= 0)
+		return false;
+
+	method = of_get_flat_dt_prop(psci_node, "method", &len);
+	if (!method)
+		return false;
+
+	return  (conduit == SMCCC_CONDUIT_SMC && strncmp(method, "smc", len) == 0) ||
+		(conduit == SMCCC_CONDUIT_HVC && strncmp(method, "hvc", len) == 0);
+}
+
 #ifdef CONFIG_ACPI
 /*
  * We use PSCI 0.2+ when ACPI is deployed on ARM64 and it's
diff --git a/include/linux/psci.h b/include/linux/psci.h
index 4ca0060a3fc4..a1fc1703ba20 100644
--- a/include/linux/psci.h
+++ b/include/linux/psci.h
@@ -45,8 +45,13 @@ struct psci_0_1_function_ids get_psci_0_1_function_ids(void);
 
 #if defined(CONFIG_ARM_PSCI_FW)
 int __init psci_dt_init(void);
+bool __init psci_early_test_conduit(enum arm_smccc_conduit conduit);
 #else
 static inline int psci_dt_init(void) { return 0; }
+static inline bool psci_early_test_conduit(enum arm_smccc_conduit conduit)
+{
+	return false;
+}
 #endif
 
 #if defined(CONFIG_ARM_PSCI_FW) && defined(CONFIG_ACPI)

---

## [6] Steven Price — 2024-08-19
*Subject: [PATCH v5 05/19] arm64: Detect if in a realm and set RIPAS RAM*

From: Suzuki K Poulose <suzuki.poulose@arm.com>

Detect that the VM is a realm guest by the presence of the RSI
interface.

If in a realm then all memory needs to be marked as RIPAS RAM initially,
the loader may or may not have done this for us. To be sure iterate over
all RAM and mark it as such. Any failure is fatal as that implies the
RAM regions passed to Linux are incorrect - which would mean failing
later when attempting to access non-existent RAM.

Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Co-developed-by: Steven Price <steven.price@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v4:
 * Minor tidy ups.
Changes since v3:
 * Provide safe/unsafe versions for converting memory to protected,
   using the safer version only for the early boot.
 * Use the new psci_early_test_conduit() function to avoid calling an
   SMC if EL3 is not present (or not configured to handle an SMC).
Changes since v2:
 * Use DECLARE_STATIC_KEY_FALSE rather than "extern struct
   static_key_false".
 * Rename set_memory_range() to rsi_set_memory_range().
 * Downgrade some BUG()s to WARN()s and handle the condition by
   propagating up the stack. Comment the remaining case that ends in a
   BUG() to explain why.
 * Rely on the return from rsi_request_version() rather than checking
   the version the RMM claims to support.
 * Rename the generic sounding arm64_setup_memory() to
   arm64_rsi_setup_memory() and move the call site to setup_arch().
---
 arch/arm64/include/asm/rsi.h | 65 ++++++++++++++++++++++++++++++
 arch/arm64/kernel/Makefile   |  3 +-
 arch/arm64/kernel/rsi.c      | 78 ++++++++++++++++++++++++++++++++++++
 arch/arm64/kernel/setup.c    |  8 ++++
 4 files changed, 153 insertions(+), 1 deletion(-)
 create mode 100644 arch/arm64/include/asm/rsi.h
 create mode 100644 arch/arm64/kernel/rsi.c

diff --git a/arch/arm64/include/asm/rsi.h b/arch/arm64/include/asm/rsi.h
new file mode 100644
index 000000000000..2bc013badbc3
--- /dev/null
+++ b/arch/arm64/include/asm/rsi.h
@@ -0,0 +1,65 @@
+/* SPDX-License-Identifier: GPL-2.0-only */
+/*
+ * Copyright (C) 2024 ARM Ltd.
+ */
+
+#ifndef __ASM_RSI_H_
+#define __ASM_RSI_H_
+
+#include <linux/jump_label.h>
+#include <asm/rsi_cmds.h>
+
+DECLARE_STATIC_KEY_FALSE(rsi_present);
+
+void __init arm64_rsi_init(void);
+void __init arm64_rsi_setup_memory(void);
+static inline bool is_realm_world(void)
+{
+	return static_branch_unlikely(&rsi_present);
+}
+
+static inline int rsi_set_memory_range(phys_addr_t start, phys_addr_t end,
+				       enum ripas state, unsigned long flags)
+{
+	unsigned long ret;
+	phys_addr_t top;
+
+	while (start != end) {
+		ret = rsi_set_addr_range_state(start, end, state, flags, &top);
+		if (WARN_ON(ret || top < start || top > end))
+			return -EINVAL;
+		start = top;
+	}
+
+	return 0;
+}
+
+/*
+ * Convert the specified range to RAM. Do not use this if you rely on the
+ * contents of a page that may already be in RAM state.
+ */
+static inline int rsi_set_memory_range_protected(phys_addr_t start,
+						 phys_addr_t end)
+{
+	return rsi_set_memory_range(start, end, RSI_RIPAS_RAM,
+				    RSI_CHANGE_DESTROYED);
+}
+
+/*
+ * Convert the specified range to RAM. Do not convert any pages that may have
+ * been DESTROYED, without our permission.
+ */
+static inline int rsi_set_memory_range_protected_safe(phys_addr_t start,
+						      phys_addr_t end)
+{
+	return rsi_set_memory_range(start, end, RSI_RIPAS_RAM,
+				    RSI_NO_CHANGE_DESTROYED);
+}
+
+static inline int rsi_set_memory_range_shared(phys_addr_t start,
+					      phys_addr_t end)
+{
+	return rsi_set_memory_range(start, end, RSI_RIPAS_EMPTY,
+				    RSI_NO_CHANGE_DESTROYED);
+}
+#endif /* __ASM_RSI_H_ */
diff --git a/arch/arm64/kernel/Makefile b/arch/arm64/kernel/Makefile
index 2b112f3b7510..71c29a2a2f19 100644
--- a/arch/arm64/kernel/Makefile
+++ b/arch/arm64/kernel/Makefile
@@ -33,7 +33,8 @@ obj-y			:= debug-monitors.o entry.o irq.o fpsimd.o		\
 			   return_address.o cpuinfo.o cpu_errata.o		\
 			   cpufeature.o alternative.o cacheinfo.o		\
 			   smp.o smp_spin_table.o topology.o smccc-call.o	\
-			   syscall.o proton-pack.o idle.o patching.o pi/
+			   syscall.o proton-pack.o idle.o patching.o pi/	\
+			   rsi.o
 
 obj-$(CONFIG_COMPAT)			+= sys32.o signal32.o			\
 					   sys_compat.o
diff --git a/arch/arm64/kernel/rsi.c b/arch/arm64/kernel/rsi.c
new file mode 100644
index 000000000000..128a9a05a96b
--- /dev/null
+++ b/arch/arm64/kernel/rsi.c
@@ -0,0 +1,78 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/*
+ * Copyright (C) 2023 ARM Ltd.
+ */
+
+#include <linux/jump_label.h>
+#include <linux/memblock.h>
+#include <linux/psci.h>
+#include <asm/rsi.h>
+
+DEFINE_STATIC_KEY_FALSE_RO(rsi_present);
+EXPORT_SYMBOL(rsi_present);
+
+static bool rsi_version_matches(void)
+{
+	unsigned long ver_lower, ver_higher;
+	unsigned long ret = rsi_request_version(RSI_ABI_VERSION,
+						&ver_lower,
+						&ver_higher);
+
+	if (ret == SMCCC_RET_NOT_SUPPORTED)
+		return false;
+
+	if (ret != RSI_SUCCESS) {
+		pr_err("RME: RMM doesn't support RSI version %lu.%lu. Supported range: %lu.%lu-%lu.%lu\n",
+		       RSI_ABI_VERSION_MAJOR, RSI_ABI_VERSION_MINOR,
+		       RSI_ABI_VERSION_GET_MAJOR(ver_lower),
+		       RSI_ABI_VERSION_GET_MINOR(ver_lower),
+		       RSI_ABI_VERSION_GET_MAJOR(ver_higher),
+		       RSI_ABI_VERSION_GET_MINOR(ver_higher));
+		return false;
+	}
+
+	pr_info("RME: Using RSI version %lu.%lu\n",
+		RSI_ABI_VERSION_GET_MAJOR(ver_lower),
+		RSI_ABI_VERSION_GET_MINOR(ver_lower));
+
+	return true;
+}
+
+void __init arm64_rsi_setup_memory(void)
+{
+	u64 i;
+	phys_addr_t start, end;
+
+	if (!is_realm_world())
+		return;
+
+	/*
+	 * Iterate over the available memory ranges and convert the state to
+	 * protected memory. We should take extra care to ensure that we DO NOT
+	 * permit any "DESTROYED" pages to be converted to "RAM".
+	 *
+	 * BUG_ON is used because if the attempt to switch the memory to
+	 * protected has failed here, then future accesses to the memory are
+	 * simply going to be reflected as a SEA (Synchronous External Abort)
+	 * which we can't handle.  Bailing out early prevents the guest limping
+	 * on and dying later.
+	 */
+	for_each_mem_range(i, &start, &end) {
+		BUG_ON(rsi_set_memory_range_protected_safe(start, end));
+	}
+}
+
+void __init arm64_rsi_init(void)
+{
+	/*
+	 * If PSCI isn't using SMC, RMM isn't present. Don't try to execute an
+	 * SMC as it could be UNDEFINED.
+	 */
+	if (!psci_early_test_conduit(SMCCC_CONDUIT_SMC))
+		return;
+	if (!rsi_version_matches())
+		return;
+
+	static_branch_enable(&rsi_present);
+}
+
diff --git a/arch/arm64/kernel/setup.c b/arch/arm64/kernel/setup.c
index a096e2451044..143f87615af0 100644
--- a/arch/arm64/kernel/setup.c
+++ b/arch/arm64/kernel/setup.c
@@ -43,6 +43,7 @@
 #include <asm/cpu_ops.h>
 #include <asm/kasan.h>
 #include <asm/numa.h>
+#include <asm/rsi.h>
 #include <asm/scs.h>
 #include <asm/sections.h>
 #include <asm/setup.h>
@@ -293,6 +294,11 @@ void __init __no_sanitize_address setup_arch(char **cmdline_p)
 	 * cpufeature code and early parameters.
 	 */
 	jump_label_init();
+	/*
+	 * Init RSI before early param so that "earlycon" console uses the
+	 * shared alias when in a realm
+	 */
+	arm64_rsi_init();
 	parse_early_param();
 
 	dynamic_scs_init();
@@ -328,6 +334,8 @@ void __init __no_sanitize_address setup_arch(char **cmdline_p)
 
 	arm64_memblock_init();
 
+	arm64_rsi_setup_memory();
+
 	paging_init();
 
 	acpi_table_upgrade();

---

## [7] Steven Price — 2024-08-19
*Subject: [PATCH v5 06/19] arm64: realm: Query IPA size from the RMM*

The top bit of the configured IPA size is used as an attribute to
control whether the address is protected or shared. Query the
configuration from the RMM to assertain which bit this is.

Co-developed-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v4:
 * Make PROT_NS_SHARED check is_realm_world() to reduce impact on
   non-CCA systems.
Changes since v2:
 * Drop unneeded extra brackets from PROT_NS_SHARED.
 * Drop the explicit alignment from 'config' as struct realm_config now
   specifies the alignment.
---
 arch/arm64/include/asm/pgtable-prot.h | 4 ++++
 arch/arm64/kernel/rsi.c               | 8 ++++++++
 2 files changed, 12 insertions(+)

diff --git a/arch/arm64/include/asm/pgtable-prot.h b/arch/arm64/include/asm/pgtable-prot.h
index b11cfb9fdd37..5e578274a3b7 100644
--- a/arch/arm64/include/asm/pgtable-prot.h
+++ b/arch/arm64/include/asm/pgtable-prot.h
@@ -68,8 +68,12 @@
 
 #include <asm/cpufeature.h>
 #include <asm/pgtable-types.h>
+#include <asm/rsi.h>
 
 extern bool arm64_use_ng_mappings;
+extern unsigned long prot_ns_shared;
+
+#define PROT_NS_SHARED		(is_realm_world() ? prot_ns_shared : 0)
 
 #define PTE_MAYBE_NG		(arm64_use_ng_mappings ? PTE_NG : 0)
 #define PMD_MAYBE_NG		(arm64_use_ng_mappings ? PMD_SECT_NG : 0)
diff --git a/arch/arm64/kernel/rsi.c b/arch/arm64/kernel/rsi.c
index 128a9a05a96b..e968a5c9929e 100644
--- a/arch/arm64/kernel/rsi.c
+++ b/arch/arm64/kernel/rsi.c
@@ -8,6 +8,11 @@
 #include <linux/psci.h>
 #include <asm/rsi.h>
 
+struct realm_config config;
+
+unsigned long prot_ns_shared;
+EXPORT_SYMBOL(prot_ns_shared);
+
 DEFINE_STATIC_KEY_FALSE_RO(rsi_present);
 EXPORT_SYMBOL(rsi_present);
 
@@ -72,6 +77,9 @@ void __init arm64_rsi_init(void)
 		return;
 	if (!rsi_version_matches())
 		return;
+	if (rsi_get_realm_config(&config))
+		return;
+	prot_ns_shared = BIT(config.ipa_bits - 1);
 
 	static_branch_enable(&rsi_present);
 }

---

## [8] Steven Price — 2024-08-19
*Subject: [PATCH v5 07/19] arm64: rsi: Add support for checking whether an MMIO is protected*

From: Suzuki K Poulose <suzuki.poulose@arm.com>

On Arm CCA, with RMM-v1.0, all MMIO regions are shared. However, in
the future, an Arm CCA-v1.0 compliant guest may be run in a lesser
privileged partition in the Realm World (with Arm CCA-v1.1 Planes
feature). In this case, some of the MMIO regions may be emulated
by a higher privileged component in the Realm world, i.e, protected.

Thus the guest must decide today, whether a given MMIO region is shared
vs Protected and create the stage1 mapping accordingly. On Arm CCA, this
detection is based on the "IPA State" (RIPAS == RIPAS_IO). Provide a
helper to run this check on a given range of MMIO.

Also, provide a arm64 helper which may be hooked in by other solutions.

Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
New patch for v5
---
 arch/arm64/include/asm/io.h       |  8 ++++++++
 arch/arm64/include/asm/rsi.h      |  3 +++
 arch/arm64/include/asm/rsi_cmds.h | 21 +++++++++++++++++++++
 arch/arm64/kernel/rsi.c           | 26 ++++++++++++++++++++++++++
 4 files changed, 58 insertions(+)

diff --git a/arch/arm64/include/asm/io.h b/arch/arm64/include/asm/io.h
index 1ada23a6ec19..a6c551c5e44e 100644
--- a/arch/arm64/include/asm/io.h
+++ b/arch/arm64/include/asm/io.h
@@ -17,6 +17,7 @@
 #include <asm/early_ioremap.h>
 #include <asm/alternative.h>
 #include <asm/cpufeature.h>
+#include <asm/rsi.h>
 
 /*
  * Generic IO read/write.  These perform native-endian accesses.
@@ -318,4 +319,11 @@ extern bool arch_memremap_can_ram_remap(resource_size_t offset, size_t size,
 					unsigned long flags);
 #define arch_memremap_can_ram_remap arch_memremap_can_ram_remap
 
+static inline bool arm64_is_iomem_private(phys_addr_t phys_addr, size_t size)
+{
+	if (unlikely(is_realm_world()))
+		return arm64_rsi_is_protected_mmio(phys_addr, size);
+	return false;
+}
+
 #endif	/* __ASM_IO_H */
diff --git a/arch/arm64/include/asm/rsi.h b/arch/arm64/include/asm/rsi.h
index 2bc013badbc3..e31231b50b6a 100644
--- a/arch/arm64/include/asm/rsi.h
+++ b/arch/arm64/include/asm/rsi.h
@@ -13,6 +13,9 @@ DECLARE_STATIC_KEY_FALSE(rsi_present);
 
 void __init arm64_rsi_init(void);
 void __init arm64_rsi_setup_memory(void);
+
+bool arm64_rsi_is_protected_mmio(phys_addr_t base, size_t size);
+
 static inline bool is_realm_world(void)
 {
 	return static_branch_unlikely(&rsi_present);
diff --git a/arch/arm64/include/asm/rsi_cmds.h b/arch/arm64/include/asm/rsi_cmds.h
index 968b03f4e703..c2363f36d167 100644
--- a/arch/arm64/include/asm/rsi_cmds.h
+++ b/arch/arm64/include/asm/rsi_cmds.h
@@ -45,6 +45,27 @@ static inline unsigned long rsi_get_realm_config(struct realm_config *cfg)
 	return res.a0;
 }
 
+static inline unsigned long rsi_ipa_state_get(phys_addr_t start,
+					      phys_addr_t end,
+					      enum ripas *state,
+					      phys_addr_t *top)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_smc(SMC_RSI_IPA_STATE_GET,
+		      start, end, 0, 0, 0, 0, 0,
+		      &res);
+
+	if (res.a0 == RSI_SUCCESS) {
+		if (top)
+			*top = res.a1;
+		if (state)
+			*state = res.a2;
+	}
+
+	return res.a0;
+}
+
 static inline unsigned long rsi_set_addr_range_state(phys_addr_t start,
 						     phys_addr_t end,
 						     enum ripas state,
diff --git a/arch/arm64/kernel/rsi.c b/arch/arm64/kernel/rsi.c
index e968a5c9929e..381a5b9a5333 100644
--- a/arch/arm64/kernel/rsi.c
+++ b/arch/arm64/kernel/rsi.c
@@ -67,6 +67,32 @@ void __init arm64_rsi_setup_memory(void)
 	}
 }
 
+bool arm64_rsi_is_protected_mmio(phys_addr_t base, size_t size)
+{
+	enum ripas ripas;
+	phys_addr_t end, top;
+
+	/* Overflow ? */
+	if (WARN_ON(base + size < base))
+		return false;
+
+	end = ALIGN(base + size, RSI_GRANULE_SIZE);
+	base = ALIGN_DOWN(base, RSI_GRANULE_SIZE);
+
+	while (base < end) {
+		if (WARN_ON(rsi_ipa_state_get(base, end, &ripas, &top)))
+			break;
+		if (WARN_ON(top <= base))
+			break;
+		if (ripas != RSI_RIPAS_IO)
+			break;
+		base = top;
+	}
+
+	return (size && base >= end);
+}
+EXPORT_SYMBOL(arm64_rsi_is_protected_mmio);
+
 void __init arm64_rsi_init(void)
 {
 	/*

---

## [9] Steven Price — 2024-08-19
*Subject: [PATCH v5 08/19] fixmap: Allow architecture overriding set_fixmap_io*

From: Suzuki K Poulose <suzuki.poulose@arm.com>

For a realm guest it will be necessary to ensure IO mappings are shared
so that the VMM can emulate the device. The following patch will provide
an implementation of set_fixmap_io for arm64 setting the shared bit (if
in a realm).

Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
New patch for v5
---
 include/asm-generic/fixmap.h | 2 ++
 1 file changed, 2 insertions(+)

diff --git a/include/asm-generic/fixmap.h b/include/asm-generic/fixmap.h
index 29cab7947980..9b75fe2bd8fd 100644
--- a/include/asm-generic/fixmap.h
+++ b/include/asm-generic/fixmap.h
@@ -94,8 +94,10 @@ static inline unsigned long virt_to_fix(const unsigned long vaddr)
 /*
  * Some fixmaps are for IO
  */
+#ifndef set_fixmap_io
 #define set_fixmap_io(idx, phys) \
 	__set_fixmap(idx, phys, FIXMAP_PAGE_IO)
+#endif
 
 #endif /* __ASSEMBLY__ */
 #endif /* __ASM_GENERIC_FIXMAP_H */

---

## [10] Steven Price — 2024-08-19
*Subject: [PATCH v5 09/19] fixmap: Pass down the full phys address for set_fixmap_io*

From: Suzuki K Poulose <suzuki.poulose@arm.com>

For early I/O mapping using fixmap, we mask the address by PAGE_MASK
base and then map it to the FIXMAP slot. However, with confidential
computing, the granularity at which "protections" (encrypted vs
decrypted) are applied may be finer than the PAGE_SIZE. e.g., for Arm
CCA it is 4K while an arm64 kernel could be using 64K pagesize. However
we need to know the exact address being mapped in.

Thus in-order to calculate the accurate protection, pass down the exact
phys address to the helpers. This would be later used by arm64 to detect
if the MMIO address is shared vs protected. The users of such drivers
already cope with running the same code with "4K" page size, thus
mapping a PAGE_SIZE covering the address range is considered acceptable.

Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
New patch for v5
---
 drivers/tty/serial/earlycon.c | 2 +-
 include/asm-generic/fixmap.h  | 2 +-
 2 files changed, 2 insertions(+), 2 deletions(-)

diff --git a/drivers/tty/serial/earlycon.c b/drivers/tty/serial/earlycon.c
index a5fbb6ed38ae..c8414b648d47 100644
--- a/drivers/tty/serial/earlycon.c
+++ b/drivers/tty/serial/earlycon.c
@@ -40,7 +40,7 @@ static void __iomem * __init earlycon_map(resource_size_t paddr, size_t size)
 {
 	void __iomem *base;
 #ifdef CONFIG_FIX_EARLYCON_MEM
-	set_fixmap_io(FIX_EARLYCON_MEM_BASE, paddr & PAGE_MASK);
+	set_fixmap_io(FIX_EARLYCON_MEM_BASE, paddr);
 	base = (void __iomem *)__fix_to_virt(FIX_EARLYCON_MEM_BASE);
 	base += paddr & ~PAGE_MASK;
 #else
diff --git a/include/asm-generic/fixmap.h b/include/asm-generic/fixmap.h
index 9b75fe2bd8fd..8d2222035ed2 100644
--- a/include/asm-generic/fixmap.h
+++ b/include/asm-generic/fixmap.h
@@ -96,7 +96,7 @@ static inline unsigned long virt_to_fix(const unsigned long vaddr)
  */
 #ifndef set_fixmap_io
 #define set_fixmap_io(idx, phys) \
-	__set_fixmap(idx, phys, FIXMAP_PAGE_IO)
+	__set_fixmap(idx, phys & PAGE_MASK, FIXMAP_PAGE_IO)
 #endif
 
 #endif /* __ASSEMBLY__ */

---

## [11] Steven Price — 2024-08-19
*Subject: [PATCH v5 10/19] arm64: Override set_fixmap_io*

From: Suzuki K Poulose <suzuki.poulose@arm.com>

Override the set_fixmap_io to set shared permission for the host
in case of a CC guest. For now we mark it shared unconditionally.

If/when support for device assignment and device emulation in the realm
is added in the future then this will need to filter the physical
address and make the decision accordingly.

Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
New patch for v5
---
 arch/arm64/include/asm/fixmap.h |  2 ++
 arch/arm64/mm/mmu.c             | 17 +++++++++++++++++
 2 files changed, 19 insertions(+)

diff --git a/arch/arm64/include/asm/fixmap.h b/arch/arm64/include/asm/fixmap.h
index 87e307804b99..2c20da3a468c 100644
--- a/arch/arm64/include/asm/fixmap.h
+++ b/arch/arm64/include/asm/fixmap.h
@@ -108,6 +108,8 @@ void __init early_fixmap_init(void);
 #define __late_clear_fixmap(idx) __set_fixmap((idx), 0, FIXMAP_PAGE_CLEAR)
 
 extern void __set_fixmap(enum fixed_addresses idx, phys_addr_t phys, pgprot_t prot);
+#define set_fixmap_io set_fixmap_io
+void set_fixmap_io(enum fixed_addresses idx, phys_addr_t phys);
 
 #include <asm-generic/fixmap.h>
 
diff --git a/arch/arm64/mm/mmu.c b/arch/arm64/mm/mmu.c
index 353ea5dc32b8..06b66c23c124 100644
--- a/arch/arm64/mm/mmu.c
+++ b/arch/arm64/mm/mmu.c
@@ -1193,6 +1193,23 @@ void vmemmap_free(unsigned long start, unsigned long end,
 }
 #endif /* CONFIG_MEMORY_HOTPLUG */
 
+void set_fixmap_io(enum fixed_addresses idx, phys_addr_t phys)
+{
+	pgprot_t prot = FIXMAP_PAGE_IO;
+
+	/*
+	 * The set_fixmap_io maps a single Page covering phys.
+	 * To make better decision, we stick to the smallest page
+	 * size supported (4K).
+	 */
+	if (!arm64_is_iomem_private(phys, SZ_4K))
+		prot = pgprot_decrypted(prot);
+	else
+		prot = pgprot_encrypted(prot);
+
+	__set_fixmap(idx, phys, prot);
+}
+
 int pud_set_huge(pud_t *pudp, phys_addr_t phys, pgprot_t prot)
 {
 	pud_t new_pud = pfn_pud(__phys_to_pfn(phys), mk_pud_sect_prot(prot));

---

## [12] Steven Price — 2024-08-19
*Subject: [PATCH v5 11/19] arm64: rsi: Map unprotected MMIO as decrypted*

From: Suzuki K Poulose <suzuki.poulose@arm.com>

Instead of marking every MMIO as shared, check if the given region is
"Protected" and apply the permissions accordingly.

Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
New patch for v5
---
 arch/arm64/kernel/rsi.c | 15 +++++++++++++++
 arch/arm64/mm/mmu.c     |  2 +-
 2 files changed, 16 insertions(+), 1 deletion(-)

diff --git a/arch/arm64/kernel/rsi.c b/arch/arm64/kernel/rsi.c
index 381a5b9a5333..672dd6862298 100644
--- a/arch/arm64/kernel/rsi.c
+++ b/arch/arm64/kernel/rsi.c
@@ -6,6 +6,8 @@
 #include <linux/jump_label.h>
 #include <linux/memblock.h>
 #include <linux/psci.h>
+
+#include <asm/io.h>
 #include <asm/rsi.h>
 
 struct realm_config config;
@@ -93,6 +95,16 @@ bool arm64_rsi_is_protected_mmio(phys_addr_t base, size_t size)
 }
 EXPORT_SYMBOL(arm64_rsi_is_protected_mmio);
 
+static int realm_ioremap_hook(phys_addr_t phys, size_t size, pgprot_t *prot)
+{
+	if (arm64_rsi_is_protected_mmio(phys, size))
+		*prot = pgprot_encrypted(*prot);
+	else
+		*prot = pgprot_decrypted(*prot);
+
+	return 0;
+}
+
 void __init arm64_rsi_init(void)
 {
 	/*
@@ -107,6 +119,9 @@ void __init arm64_rsi_init(void)
 		return;
 	prot_ns_shared = BIT(config.ipa_bits - 1);
 
+	if (arm64_ioremap_prot_hook_register(realm_ioremap_hook))
+		return;
+
 	static_branch_enable(&rsi_present);
 }
 
diff --git a/arch/arm64/mm/mmu.c b/arch/arm64/mm/mmu.c
index 06b66c23c124..0c2fa35beca0 100644
--- a/arch/arm64/mm/mmu.c
+++ b/arch/arm64/mm/mmu.c
@@ -1207,7 +1207,7 @@ void set_fixmap_io(enum fixed_addresses idx, phys_addr_t phys)
 	else
 		prot = pgprot_encrypted(prot);
 
-	__set_fixmap(idx, phys, prot);
+	__set_fixmap(idx, phys & PAGE_MASK, prot);
 }
 
 int pud_set_huge(pud_t *pudp, phys_addr_t phys, pgprot_t prot)

---

## [13] Steven Price — 2024-08-19
*Subject: [PATCH v5 12/19] efi: arm64: Map Device with Prot Shared*

From: Suzuki K Poulose <suzuki.poulose@arm.com>

Device mappings need to be emualted by the VMM so must be mapped shared
with the host.

Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v4:
 * Reworked to use arm64_is_iomem_private() to decide whether the memory
   needs to be decrypted or not.
---
 arch/arm64/kernel/efi.c | 12 ++++++++++--
 1 file changed, 10 insertions(+), 2 deletions(-)

diff --git a/arch/arm64/kernel/efi.c b/arch/arm64/kernel/efi.c
index 712718aed5dd..95f8e8bf07f8 100644
--- a/arch/arm64/kernel/efi.c
+++ b/arch/arm64/kernel/efi.c
@@ -34,8 +34,16 @@ static __init pteval_t create_mapping_protection(efi_memory_desc_t *md)
 	u64 attr = md->attribute;
 	u32 type = md->type;
 
-	if (type == EFI_MEMORY_MAPPED_IO)
-		return PROT_DEVICE_nGnRE;
+	if (type == EFI_MEMORY_MAPPED_IO) {
+		pgprot_t prot = __pgprot(PROT_DEVICE_nGnRE);
+
+		if (arm64_is_iomem_private(md->phys_addr,
+					   md->num_pages << EFI_PAGE_SHIFT))
+			prot = pgprot_encrypted(prot);
+		else
+			prot = pgprot_decrypted(prot);
+		return pgprot_val(prot);
+	}
 
 	if (region_is_misaligned(md)) {
 		static bool __initdata code_is_misaligned;

---

## [14] Steven Price — 2024-08-19
*Subject: [PATCH v5 13/19] arm64: Make the PHYS_MASK_SHIFT dynamic*

Make the PHYS_MASK_SHIFT dynamic for Realms. This is only is required
for masking the PFN from a pte entry. For a realm phys_mask_shift is
reduced if the RMM reports a smaller configured size for the guest.

The realm configuration splits the address space into two with the top
half being memory shared with the host, and the bottom half being
protected memory. We treat the bit which controls this split as an
attribute bit and hence exclude it (and any higher bits) from the mask.

Co-developed-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>

---
v3: Drop the MAX_PHYS_MASK{,_SHIFT} definitions as they are no longer
needed.
---
 arch/arm64/include/asm/pgtable-hwdef.h | 6 ------
 arch/arm64/include/asm/pgtable.h       | 5 +++++
 arch/arm64/kernel/rsi.c                | 5 +++++
 3 files changed, 10 insertions(+), 6 deletions(-)

diff --git a/arch/arm64/include/asm/pgtable-hwdef.h b/arch/arm64/include/asm/pgtable-hwdef.h
index 1f60aa1bc750..183431ec8f7d 100644
--- a/arch/arm64/include/asm/pgtable-hwdef.h
+++ b/arch/arm64/include/asm/pgtable-hwdef.h
@@ -204,12 +204,6 @@
  */
 #define PTE_S2_MEMATTR(t)	(_AT(pteval_t, (t)) << 2)
 
-/*
- * Highest possible physical address supported.
- */
-#define PHYS_MASK_SHIFT		(CONFIG_ARM64_PA_BITS)
-#define PHYS_MASK		((UL(1) << PHYS_MASK_SHIFT) - 1)
-
 #define TTBR_CNP_BIT		(UL(1) << 0)
 
 /*
diff --git a/arch/arm64/include/asm/pgtable.h b/arch/arm64/include/asm/pgtable.h
index 7a4f5604be3f..f39a4cbbf73a 100644
--- a/arch/arm64/include/asm/pgtable.h
+++ b/arch/arm64/include/asm/pgtable.h
@@ -39,6 +39,11 @@
 #include <linux/sched.h>
 #include <linux/page_table_check.h>
 
+extern unsigned int phys_mask_shift;
+
+#define PHYS_MASK_SHIFT		(phys_mask_shift)
+#define PHYS_MASK		((1UL << PHYS_MASK_SHIFT) - 1)
+
 #ifdef CONFIG_TRANSPARENT_HUGEPAGE
 #define __HAVE_ARCH_FLUSH_PMD_TLB_RANGE
 
diff --git a/arch/arm64/kernel/rsi.c b/arch/arm64/kernel/rsi.c
index 672dd6862298..5c2c977a50fb 100644
--- a/arch/arm64/kernel/rsi.c
+++ b/arch/arm64/kernel/rsi.c
@@ -15,6 +15,8 @@ struct realm_config config;
 unsigned long prot_ns_shared;
 EXPORT_SYMBOL(prot_ns_shared);
 
+unsigned int phys_mask_shift = CONFIG_ARM64_PA_BITS;
+
 DEFINE_STATIC_KEY_FALSE_RO(rsi_present);
 EXPORT_SYMBOL(rsi_present);
 
@@ -119,6 +121,9 @@ void __init arm64_rsi_init(void)
 		return;
 	prot_ns_shared = BIT(config.ipa_bits - 1);
 
+	if (config.ipa_bits - 1 < phys_mask_shift)
+		phys_mask_shift = config.ipa_bits - 1;
+
 	if (arm64_ioremap_prot_hook_register(realm_ioremap_hook))
 		return;

---

## [15] Steven Price — 2024-08-19
*Subject: [PATCH v5 14/19] arm64: Enforce bounce buffers for realm DMA*

Within a realm guest it's not possible for a device emulated by the VMM
to access arbitrary guest memory. So force the use of bounce buffers to
ensure that the memory the emulated devices are accessing is in memory
which is explicitly shared with the host.

This adds a call to swiotlb_update_mem_attributes() which calls
set_memory_decrypted() to ensure the bounce buffer memory is shared with
the host. For non-realm guests or hosts this is a no-op.

Co-developed-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
v3: Simplify mem_init() by using a 'flags' variable.
---
 arch/arm64/kernel/rsi.c |  1 +
 arch/arm64/mm/init.c    | 10 +++++++++-
 2 files changed, 10 insertions(+), 1 deletion(-)

diff --git a/arch/arm64/kernel/rsi.c b/arch/arm64/kernel/rsi.c
index 5c2c977a50fb..69d8d9791c65 100644
--- a/arch/arm64/kernel/rsi.c
+++ b/arch/arm64/kernel/rsi.c
@@ -6,6 +6,7 @@
 #include <linux/jump_label.h>
 #include <linux/memblock.h>
 #include <linux/psci.h>
+#include <linux/swiotlb.h>
 
 #include <asm/io.h>
 #include <asm/rsi.h>
diff --git a/arch/arm64/mm/init.c b/arch/arm64/mm/init.c
index 9b5ab6818f7f..1d595b63da71 100644
--- a/arch/arm64/mm/init.c
+++ b/arch/arm64/mm/init.c
@@ -41,6 +41,7 @@
 #include <asm/kvm_host.h>
 #include <asm/memory.h>
 #include <asm/numa.h>
+#include <asm/rsi.h>
 #include <asm/sections.h>
 #include <asm/setup.h>
 #include <linux/sizes.h>
@@ -369,8 +370,14 @@ void __init bootmem_init(void)
  */
 void __init mem_init(void)
 {
+	unsigned int flags = SWIOTLB_VERBOSE;
 	bool swiotlb = max_pfn > PFN_DOWN(arm64_dma_phys_limit);
 
+	if (is_realm_world()) {
+		swiotlb = true;
+		flags |= SWIOTLB_FORCE;
+	}
+
 	if (IS_ENABLED(CONFIG_DMA_BOUNCE_UNALIGNED_KMALLOC) && !swiotlb) {
 		/*
 		 * If no bouncing needed for ZONE_DMA, reduce the swiotlb
@@ -382,7 +389,8 @@ void __init mem_init(void)
 		swiotlb = true;
 	}
 
-	swiotlb_init(swiotlb, SWIOTLB_VERBOSE);
+	swiotlb_init(swiotlb, flags);
+	swiotlb_update_mem_attributes();
 
 	/* this will put all unused low memory onto the freelists */
 	memblock_free_all();

---

## [16] Steven Price — 2024-08-19
*Subject: [PATCH v5 15/19] arm64: mm: Avoid TLBI when marking pages as valid*

When __change_memory_common() is purely setting the valid bit on a PTE
(e.g. via the set_memory_valid() call) there is no need for a TLBI as
either the entry isn't changing (the valid bit was already set) or the
entry was invalid and so should not have been cached in the TLB.

Signed-off-by: Steven Price <steven.price@arm.com>
---
v4: New patch
---
 arch/arm64/mm/pageattr.c | 8 +++++++-
 1 file changed, 7 insertions(+), 1 deletion(-)

diff --git a/arch/arm64/mm/pageattr.c b/arch/arm64/mm/pageattr.c
index 0e270a1c51e6..547a9e0b46c2 100644
--- a/arch/arm64/mm/pageattr.c
+++ b/arch/arm64/mm/pageattr.c
@@ -60,7 +60,13 @@ static int __change_memory_common(unsigned long start, unsigned long size,
 	ret = apply_to_page_range(&init_mm, start, size, change_page_range,
 					&data);
 
-	flush_tlb_kernel_range(start, start + size);
+	/*
+	 * If the memory is being made valid without changing any other bits
+	 * then a TLBI isn't required as a non-valid entry cannot be cached in
+	 * the TLB.
+	 */
+	if (pgprot_val(set_mask) != PTE_VALID || pgprot_val(clear_mask))
+		flush_tlb_kernel_range(start, start + size);
 	return ret;
 }

---

## [17] Steven Price — 2024-08-19
*Subject: [PATCH v5 16/19] arm64: Enable memory encrypt for Realms*

From: Suzuki K Poulose <suzuki.poulose@arm.com>

Use the memory encryption APIs to trigger a RSI call to request a
transition between protected memory and shared memory (or vice versa)
and updating the kernel's linear map of modified pages to flip the top
bit of the IPA. This requires that block mappings are not used in the
direct map for realm guests.

Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Co-developed-by: Steven Price <steven.price@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
Changed since v4:
 * Reworked to use the new dispatcher for the mem_encrypt API
Changes since v3:
 * Provide pgprot_{de,en}crypted() macros
 * Rename __set_memory_encrypted() to __set_memory_enc_dec() since it
   both encrypts and decrypts.
Changes since v2:
 * Fix location of set_memory_{en,de}crypted() and export them.
 * Break-before-make when changing the top bit of the IPA for
   transitioning to/from shared.
---
 arch/arm64/Kconfig                   |  3 ++
 arch/arm64/include/asm/mem_encrypt.h |  9 ++++
 arch/arm64/include/asm/pgtable.h     |  5 ++
 arch/arm64/include/asm/set_memory.h  |  3 ++
 arch/arm64/kernel/rsi.c              | 16 ++++++
 arch/arm64/mm/pageattr.c             | 76 ++++++++++++++++++++++++++--
 6 files changed, 109 insertions(+), 3 deletions(-)

diff --git a/arch/arm64/Kconfig b/arch/arm64/Kconfig
index 68d77a2f4d1a..03d3dae34277 100644
--- a/arch/arm64/Kconfig
+++ b/arch/arm64/Kconfig
@@ -21,6 +21,7 @@ config ARM64
 	select ARCH_ENABLE_SPLIT_PMD_PTLOCK if PGTABLE_LEVELS > 2
 	select ARCH_ENABLE_THP_MIGRATION if TRANSPARENT_HUGEPAGE
 	select ARCH_HAS_CACHE_LINE_SIZE
+	select ARCH_HAS_CC_PLATFORM
 	select ARCH_HAS_CURRENT_STACK_POINTER
 	select ARCH_HAS_DEBUG_VIRTUAL
 	select ARCH_HAS_DEBUG_VM_PGTABLE
@@ -43,6 +44,8 @@ config ARM64
 	select ARCH_HAS_SETUP_DMA_OPS
 	select ARCH_HAS_SET_DIRECT_MAP
 	select ARCH_HAS_SET_MEMORY
+	select ARCH_HAS_MEM_ENCRYPT
+	select ARCH_HAS_FORCE_DMA_UNENCRYPTED
 	select ARCH_STACKWALK
 	select ARCH_HAS_STRICT_KERNEL_RWX
 	select ARCH_HAS_STRICT_MODULE_RWX
diff --git a/arch/arm64/include/asm/mem_encrypt.h b/arch/arm64/include/asm/mem_encrypt.h
index b0c9a86b13a4..f8f78f622dd2 100644
--- a/arch/arm64/include/asm/mem_encrypt.h
+++ b/arch/arm64/include/asm/mem_encrypt.h
@@ -2,6 +2,8 @@
 #ifndef __ASM_MEM_ENCRYPT_H
 #define __ASM_MEM_ENCRYPT_H
 
+#include <asm/rsi.h>
+
 struct arm64_mem_crypt_ops {
 	int (*encrypt)(unsigned long addr, int numpages);
 	int (*decrypt)(unsigned long addr, int numpages);
@@ -12,4 +14,11 @@ int arm64_mem_crypt_ops_register(const struct arm64_mem_crypt_ops *ops);
 int set_memory_encrypted(unsigned long addr, int numpages);
 int set_memory_decrypted(unsigned long addr, int numpages);
 
+int realm_register_memory_enc_ops(void);
+
+static inline bool force_dma_unencrypted(struct device *dev)
+{
+	return is_realm_world();
+}
+
 #endif	/* __ASM_MEM_ENCRYPT_H */
diff --git a/arch/arm64/include/asm/pgtable.h b/arch/arm64/include/asm/pgtable.h
index f39a4cbbf73a..4e8c648f5213 100644
--- a/arch/arm64/include/asm/pgtable.h
+++ b/arch/arm64/include/asm/pgtable.h
@@ -636,6 +636,11 @@ static inline void set_pud_at(struct mm_struct *mm, unsigned long addr,
 #define pgprot_nx(prot) \
 	__pgprot_modify(prot, PTE_MAYBE_GP, PTE_PXN)
 
+#define pgprot_decrypted(prot) \
+	__pgprot_modify(prot, PROT_NS_SHARED, PROT_NS_SHARED)
+#define pgprot_encrypted(prot) \
+	__pgprot_modify(prot, PROT_NS_SHARED, 0)
+
 /*
  * Mark the prot value as uncacheable and unbufferable.
  */
diff --git a/arch/arm64/include/asm/set_memory.h b/arch/arm64/include/asm/set_memory.h
index 917761feeffd..37774c793006 100644
--- a/arch/arm64/include/asm/set_memory.h
+++ b/arch/arm64/include/asm/set_memory.h
@@ -15,4 +15,7 @@ int set_direct_map_invalid_noflush(struct page *page);
 int set_direct_map_default_noflush(struct page *page);
 bool kernel_page_present(struct page *page);
 
+int set_memory_encrypted(unsigned long addr, int numpages);
+int set_memory_decrypted(unsigned long addr, int numpages);
+
 #endif /* _ASM_ARM64_SET_MEMORY_H */
diff --git a/arch/arm64/kernel/rsi.c b/arch/arm64/kernel/rsi.c
index 69d8d9791c65..9cb3353e5cbf 100644
--- a/arch/arm64/kernel/rsi.c
+++ b/arch/arm64/kernel/rsi.c
@@ -7,8 +7,10 @@
 #include <linux/memblock.h>
 #include <linux/psci.h>
 #include <linux/swiotlb.h>
+#include <linux/cc_platform.h>
 
 #include <asm/io.h>
+#include <asm/mem_encrypt.h>
 #include <asm/rsi.h>
 
 struct realm_config config;
@@ -21,6 +23,17 @@ unsigned int phys_mask_shift = CONFIG_ARM64_PA_BITS;
 DEFINE_STATIC_KEY_FALSE_RO(rsi_present);
 EXPORT_SYMBOL(rsi_present);
 
+bool cc_platform_has(enum cc_attr attr)
+{
+	switch (attr) {
+	case CC_ATTR_MEM_ENCRYPT:
+		return is_realm_world();
+	default:
+		return false;
+	}
+}
+EXPORT_SYMBOL_GPL(cc_platform_has);
+
 static bool rsi_version_matches(void)
 {
 	unsigned long ver_lower, ver_higher;
@@ -128,6 +141,9 @@ void __init arm64_rsi_init(void)
 	if (arm64_ioremap_prot_hook_register(realm_ioremap_hook))
 		return;
 
+	if (realm_register_memory_enc_ops())
+		return;
+
 	static_branch_enable(&rsi_present);
 }
 
diff --git a/arch/arm64/mm/pageattr.c b/arch/arm64/mm/pageattr.c
index 547a9e0b46c2..d11f5dc4c2c5 100644
--- a/arch/arm64/mm/pageattr.c
+++ b/arch/arm64/mm/pageattr.c
@@ -5,10 +5,12 @@
 #include <linux/kernel.h>
 #include <linux/mm.h>
 #include <linux/module.h>
+#include <linux/mem_encrypt.h>
 #include <linux/sched.h>
 #include <linux/vmalloc.h>
 
 #include <asm/cacheflush.h>
+#include <asm/pgtable-prot.h>
 #include <asm/set_memory.h>
 #include <asm/tlbflush.h>
 #include <asm/kfence.h>
@@ -23,14 +25,16 @@ bool rodata_full __ro_after_init = IS_ENABLED(CONFIG_RODATA_FULL_DEFAULT_ENABLED
 bool can_set_direct_map(void)
 {
 	/*
-	 * rodata_full and DEBUG_PAGEALLOC require linear map to be
-	 * mapped at page granularity, so that it is possible to
+	 * rodata_full, DEBUG_PAGEALLOC and a Realm guest all require linear
+	 * map to be mapped at page granularity, so that it is possible to
 	 * protect/unprotect single pages.
 	 *
 	 * KFENCE pool requires page-granular mapping if initialized late.
+	 *
+	 * Realms need to make pages shared/protected at page granularity.
 	 */
 	return rodata_full || debug_pagealloc_enabled() ||
-	       arm64_kfence_can_set_direct_map();
+		arm64_kfence_can_set_direct_map() || is_realm_world();
 }
 
 static int change_page_range(pte_t *ptep, unsigned long addr, void *data)
@@ -198,6 +202,72 @@ int set_direct_map_default_noflush(struct page *page)
 				   PAGE_SIZE, change_page_range, &data);
 }
 
+static int __set_memory_enc_dec(unsigned long addr,
+				int numpages,
+				bool encrypt)
+{
+	unsigned long set_prot = 0, clear_prot = 0;
+	phys_addr_t start, end;
+	int ret;
+
+	if (!is_realm_world())
+		return 0;
+
+	if (!__is_lm_address(addr))
+		return -EINVAL;
+
+	start = __virt_to_phys(addr);
+	end = start + numpages * PAGE_SIZE;
+
+	if (encrypt)
+		clear_prot = PROT_NS_SHARED;
+	else
+		set_prot = PROT_NS_SHARED;
+
+	/*
+	 * Break the mapping before we make any changes to avoid stale TLB
+	 * entries or Synchronous External Aborts caused by RIPAS_EMPTY
+	 */
+	ret = __change_memory_common(addr, PAGE_SIZE * numpages,
+				     __pgprot(set_prot),
+				     __pgprot(clear_prot | PTE_VALID));
+
+	if (ret)
+		return ret;
+
+	if (encrypt)
+		ret = rsi_set_memory_range_protected(start, end);
+	else
+		ret = rsi_set_memory_range_shared(start, end);
+
+	if (ret)
+		return ret;
+
+	return __change_memory_common(addr, PAGE_SIZE * numpages,
+				      __pgprot(PTE_VALID),
+				      __pgprot(0));
+}
+
+static int realm_set_memory_encrypted(unsigned long addr, int numpages)
+{
+	return __set_memory_enc_dec(addr, numpages, true);
+}
+
+static int realm_set_memory_decrypted(unsigned long addr, int numpages)
+{
+	return __set_memory_enc_dec(addr, numpages, false);
+}
+
+static const struct arm64_mem_crypt_ops realm_crypt_ops = {
+	.encrypt = realm_set_memory_encrypted,
+	.decrypt = realm_set_memory_decrypted,
+};
+
+int realm_register_memory_enc_ops(void)
+{
+	return arm64_mem_crypt_ops_register(&realm_crypt_ops);
+}
+
 #ifdef CONFIG_DEBUG_PAGEALLOC
 void __kernel_map_pages(struct page *page, int numpages, int enable)
 {

---

## [18] Steven Price — 2024-08-19
*Subject: [PATCH v5 17/19] irqchip/gic-v3-its: Share ITS tables with a non-trusted hypervisor*

Within a realm guest the ITS is emulated by the host. This means the
allocations must have been made available to the host by a call to
set_memory_decrypted(). Introduce an allocation function which performs
this extra call.

For the ITT use a custom genpool-based allocator that calls
set_memory_decrypted() for each page allocated, but then suballocates
the size needed for each ITT. Note that there is no mechanism
implemented to return pages from the genpool, but it is unlikely the
peak number of devices will so much larger than the normal level - so
this isn't expected to be an issue.

Co-developed-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Tested-by: Will Deacon <will@kernel.org>
Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v3:
 * Use BIT() macro.
 * Use a genpool based allocator in its_create_device() to avoid
   allocating a full page.
 * Fix subject to drop "realm" and use gic-v3-its.
 * Add error handling to ITS alloc/free.
Changes since v2:
 * Drop 'shared' from the new its_xxx function names as they are used
   for non-realm guests too.
 * Don't handle the NUMA_NO_NODE case specially - alloc_pages_node()
   should do the right thing.
 * Drop a pointless (void *) cast.
---
 drivers/irqchip/irq-gic-v3-its.c | 139 ++++++++++++++++++++++++++-----
 1 file changed, 116 insertions(+), 23 deletions(-)

diff --git a/drivers/irqchip/irq-gic-v3-its.c b/drivers/irqchip/irq-gic-v3-its.c
index 9b34596b3542..557214c774c3 100644
--- a/drivers/irqchip/irq-gic-v3-its.c
+++ b/drivers/irqchip/irq-gic-v3-its.c
@@ -12,12 +12,14 @@
 #include <linux/crash_dump.h>
 #include <linux/delay.h>
 #include <linux/efi.h>
+#include <linux/genalloc.h>
 #include <linux/interrupt.h>
 #include <linux/iommu.h>
 #include <linux/iopoll.h>
 #include <linux/irqdomain.h>
 #include <linux/list.h>
 #include <linux/log2.h>
+#include <linux/mem_encrypt.h>
 #include <linux/memblock.h>
 #include <linux/mm.h>
 #include <linux/msi.h>
@@ -27,6 +29,7 @@
 #include <linux/of_pci.h>
 #include <linux/of_platform.h>
 #include <linux/percpu.h>
+#include <linux/set_memory.h>
 #include <linux/slab.h>
 #include <linux/syscore_ops.h>
 
@@ -164,6 +167,7 @@ struct its_device {
 	struct its_node		*its;
 	struct event_lpi_map	event_map;
 	void			*itt;
+	u32			itt_sz;
 	u32			nr_ites;
 	u32			device_id;
 	bool			shared;
@@ -199,6 +203,81 @@ static DEFINE_IDA(its_vpeid_ida);
 #define gic_data_rdist_rd_base()	(gic_data_rdist()->rd_base)
 #define gic_data_rdist_vlpi_base()	(gic_data_rdist_rd_base() + SZ_128K)
 
+static struct page *its_alloc_pages_node(int node, gfp_t gfp,
+					 unsigned int order)
+{
+	struct page *page;
+	int ret = 0;
+
+	page = alloc_pages_node(node, gfp, order);
+
+	if (!page)
+		return NULL;
+
+	ret = set_memory_decrypted((unsigned long)page_address(page),
+				   1 << order);
+	if (WARN_ON(ret))
+		return NULL;
+
+	return page;
+}
+
+static struct page *its_alloc_pages(gfp_t gfp, unsigned int order)
+{
+	return its_alloc_pages_node(NUMA_NO_NODE, gfp, order);
+}
+
+static void its_free_pages(void *addr, unsigned int order)
+{
+	if (WARN_ON(set_memory_encrypted((unsigned long)addr, 1 << order)))
+		return;
+	free_pages((unsigned long)addr, order);
+}
+
+static struct gen_pool *itt_pool;
+
+static void *itt_alloc_pool(int node, int size)
+{
+	unsigned long addr;
+	struct page *page;
+
+	if (size >= PAGE_SIZE) {
+		page = its_alloc_pages_node(node,
+					    GFP_KERNEL | __GFP_ZERO,
+					    get_order(size));
+
+		return page_address(page);
+	}
+
+	do {
+		addr = gen_pool_alloc(itt_pool, size);
+		if (addr)
+			break;
+
+		page = its_alloc_pages_node(node, GFP_KERNEL | __GFP_ZERO, 1);
+		if (!page)
+			break;
+
+		gen_pool_add(itt_pool, (unsigned long)page_address(page),
+			     PAGE_SIZE, node);
+	} while (!addr);
+
+	return (void *)addr;
+}
+
+static void itt_free_pool(void *addr, int size)
+{
+	if (!addr)
+		return;
+
+	if (size >= PAGE_SIZE) {
+		its_free_pages(addr, get_order(size));
+		return;
+	}
+
+	gen_pool_free(itt_pool, (unsigned long)addr, size);
+}
+
 /*
  * Skip ITSs that have no vLPIs mapped, unless we're on GICv4.1, as we
  * always have vSGIs mapped.
@@ -2187,7 +2266,8 @@ static struct page *its_allocate_prop_table(gfp_t gfp_flags)
 {
 	struct page *prop_page;
 
-	prop_page = alloc_pages(gfp_flags, get_order(LPI_PROPBASE_SZ));
+	prop_page = its_alloc_pages(gfp_flags,
+				    get_order(LPI_PROPBASE_SZ));
 	if (!prop_page)
 		return NULL;
 
@@ -2198,8 +2278,8 @@ static struct page *its_allocate_prop_table(gfp_t gfp_flags)
 
 static void its_free_prop_table(struct page *prop_page)
 {
-	free_pages((unsigned long)page_address(prop_page),
-		   get_order(LPI_PROPBASE_SZ));
+	its_free_pages(page_address(prop_page),
+		       get_order(LPI_PROPBASE_SZ));
 }
 
 static bool gic_check_reserved_range(phys_addr_t addr, unsigned long size)
@@ -2321,7 +2401,8 @@ static int its_setup_baser(struct its_node *its, struct its_baser *baser,
 		order = get_order(GITS_BASER_PAGES_MAX * psz);
 	}
 
-	page = alloc_pages_node(its->numa_node, GFP_KERNEL | __GFP_ZERO, order);
+	page = its_alloc_pages_node(its->numa_node,
+				    GFP_KERNEL | __GFP_ZERO, order);
 	if (!page)
 		return -ENOMEM;
 
@@ -2334,7 +2415,7 @@ static int its_setup_baser(struct its_node *its, struct its_baser *baser,
 		/* 52bit PA is supported only when PageSize=64K */
 		if (psz != SZ_64K) {
 			pr_err("ITS: no 52bit PA support when psz=%d\n", psz);
-			free_pages((unsigned long)base, order);
+			its_free_pages(base, order);
 			return -ENXIO;
 		}
 
@@ -2390,7 +2471,7 @@ static int its_setup_baser(struct its_node *its, struct its_baser *baser,
 		pr_err("ITS@%pa: %s doesn't stick: %llx %llx\n",
 		       &its->phys_base, its_base_type_string[type],
 		       val, tmp);
-		free_pages((unsigned long)base, order);
+		its_free_pages(base, order);
 		return -ENXIO;
 	}
 
@@ -2529,8 +2610,8 @@ static void its_free_tables(struct its_node *its)
 
 	for (i = 0; i < GITS_BASER_NR_REGS; i++) {
 		if (its->tables[i].base) {
-			free_pages((unsigned long)its->tables[i].base,
-				   its->tables[i].order);
+			its_free_pages(its->tables[i].base,
+				       its->tables[i].order);
 			its->tables[i].base = NULL;
 		}
 	}
@@ -2796,7 +2877,8 @@ static bool allocate_vpe_l2_table(int cpu, u32 id)
 
 	/* Allocate memory for 2nd level table */
 	if (!table[idx]) {
-		page = alloc_pages(GFP_KERNEL | __GFP_ZERO, get_order(psz));
+		page = its_alloc_pages(GFP_KERNEL | __GFP_ZERO,
+				       get_order(psz));
 		if (!page)
 			return false;
 
@@ -2915,7 +2997,8 @@ static int allocate_vpe_l1_table(void)
 
 	pr_debug("np = %d, npg = %lld, psz = %d, epp = %d, esz = %d\n",
 		 np, npg, psz, epp, esz);
-	page = alloc_pages(GFP_ATOMIC | __GFP_ZERO, get_order(np * PAGE_SIZE));
+	page = its_alloc_pages(GFP_ATOMIC | __GFP_ZERO,
+			       get_order(np * PAGE_SIZE));
 	if (!page)
 		return -ENOMEM;
 
@@ -2961,8 +3044,8 @@ static struct page *its_allocate_pending_table(gfp_t gfp_flags)
 {
 	struct page *pend_page;
 
-	pend_page = alloc_pages(gfp_flags | __GFP_ZERO,
-				get_order(LPI_PENDBASE_SZ));
+	pend_page = its_alloc_pages(gfp_flags | __GFP_ZERO,
+				    get_order(LPI_PENDBASE_SZ));
 	if (!pend_page)
 		return NULL;
 
@@ -2974,7 +3057,7 @@ static struct page *its_allocate_pending_table(gfp_t gfp_flags)
 
 static void its_free_pending_table(struct page *pt)
 {
-	free_pages((unsigned long)page_address(pt), get_order(LPI_PENDBASE_SZ));
+	its_free_pages(page_address(pt), get_order(LPI_PENDBASE_SZ));
 }
 
 /*
@@ -3309,8 +3392,9 @@ static bool its_alloc_table_entry(struct its_node *its,
 
 	/* Allocate memory for 2nd level table */
 	if (!table[idx]) {
-		page = alloc_pages_node(its->numa_node, GFP_KERNEL | __GFP_ZERO,
-					get_order(baser->psz));
+		page = its_alloc_pages_node(its->numa_node,
+					    GFP_KERNEL | __GFP_ZERO,
+					    get_order(baser->psz));
 		if (!page)
 			return false;
 
@@ -3405,7 +3489,6 @@ static struct its_device *its_create_device(struct its_node *its, u32 dev_id,
 	if (WARN_ON(!is_power_of_2(nvecs)))
 		nvecs = roundup_pow_of_two(nvecs);
 
-	dev = kzalloc(sizeof(*dev), GFP_KERNEL);
 	/*
 	 * Even if the device wants a single LPI, the ITT must be
 	 * sized as a power of two (and you need at least one bit...).
@@ -3413,7 +3496,11 @@ static struct its_device *its_create_device(struct its_node *its, u32 dev_id,
 	nr_ites = max(2, nvecs);
 	sz = nr_ites * (FIELD_GET(GITS_TYPER_ITT_ENTRY_SIZE, its->typer) + 1);
 	sz = max(sz, ITS_ITT_ALIGN) + ITS_ITT_ALIGN - 1;
-	itt = kzalloc_node(sz, GFP_KERNEL, its->numa_node);
+
+	itt = itt_alloc_pool(its->numa_node, sz);
+
+	dev = kzalloc(sizeof(*dev), GFP_KERNEL);
+
 	if (alloc_lpis) {
 		lpi_map = its_lpi_alloc(nvecs, &lpi_base, &nr_lpis);
 		if (lpi_map)
@@ -3425,9 +3512,9 @@ static struct its_device *its_create_device(struct its_node *its, u32 dev_id,
 		lpi_base = 0;
 	}
 
-	if (!dev || !itt ||  !col_map || (!lpi_map && alloc_lpis)) {
+	if (!dev || !itt || !col_map || (!lpi_map && alloc_lpis)) {
 		kfree(dev);
-		kfree(itt);
+		itt_free_pool(itt, sz);
 		bitmap_free(lpi_map);
 		kfree(col_map);
 		return NULL;
@@ -3437,6 +3524,7 @@ static struct its_device *its_create_device(struct its_node *its, u32 dev_id,
 
 	dev->its = its;
 	dev->itt = itt;
+	dev->itt_sz = sz;
 	dev->nr_ites = nr_ites;
 	dev->event_map.lpi_map = lpi_map;
 	dev->event_map.col_map = col_map;
@@ -3464,7 +3552,7 @@ static void its_free_device(struct its_device *its_dev)
 	list_del(&its_dev->entry);
 	raw_spin_unlock_irqrestore(&its_dev->its->lock, flags);
 	kfree(its_dev->event_map.col_map);
-	kfree(its_dev->itt);
+	itt_free_pool(its_dev->itt, its_dev->itt_sz);
 	kfree(its_dev);
 }
 
@@ -5112,8 +5200,9 @@ static int __init its_probe_one(struct its_node *its)
 		}
 	}
 
-	page = alloc_pages_node(its->numa_node, GFP_KERNEL | __GFP_ZERO,
-				get_order(ITS_CMD_QUEUE_SZ));
+	page = its_alloc_pages_node(its->numa_node,
+				    GFP_KERNEL | __GFP_ZERO,
+				    get_order(ITS_CMD_QUEUE_SZ));
 	if (!page) {
 		err = -ENOMEM;
 		goto out_unmap_sgir;
@@ -5177,7 +5266,7 @@ static int __init its_probe_one(struct its_node *its)
 out_free_tables:
 	its_free_tables(its);
 out_free_cmd:
-	free_pages((unsigned long)its->cmd_base, get_order(ITS_CMD_QUEUE_SZ));
+	its_free_pages(its->cmd_base, get_order(ITS_CMD_QUEUE_SZ));
 out_unmap_sgir:
 	if (its->sgir_base)
 		iounmap(its->sgir_base);
@@ -5663,6 +5752,10 @@ int __init its_init(struct fwnode_handle *handle, struct rdists *rdists,
 	bool has_v4_1 = false;
 	int err;
 
+	itt_pool = gen_pool_create(get_order(ITS_ITT_ALIGN), -1);
+	if (!itt_pool)
+		return -ENOMEM;
+
 	gic_rdists = rdists;
 
 	lpi_prop_prio = irq_prio;

---

## [19] Steven Price — 2024-08-19
*Subject: [PATCH v5 18/19] irqchip/gic-v3-its: Rely on genpool alignment*

its_create_device() over-allocated by ITS_ITT_ALIGN - 1 bytes to ensure
that an aligned area was available within the allocation. The new
genpool allocator has its min_alloc_order set to
get_order(ITS_ITT_ALIGN) so all allocations from it should be
appropriately aligned.

Remove the over-allocation from its_create_device() and alignment from
its_build_mapd_cmd().

Tested-by: Will Deacon <will@kernel.org>
Signed-off-by: Steven Price <steven.price@arm.com>
---
 drivers/irqchip/irq-gic-v3-its.c | 3 +--
 1 file changed, 1 insertion(+), 2 deletions(-)

diff --git a/drivers/irqchip/irq-gic-v3-its.c b/drivers/irqchip/irq-gic-v3-its.c
index 557214c774c3..49aacf96ade2 100644
--- a/drivers/irqchip/irq-gic-v3-its.c
+++ b/drivers/irqchip/irq-gic-v3-its.c
@@ -700,7 +700,6 @@ static struct its_collection *its_build_mapd_cmd(struct its_node *its,
 	u8 size = ilog2(desc->its_mapd_cmd.dev->nr_ites);
 
 	itt_addr = virt_to_phys(desc->its_mapd_cmd.dev->itt);
-	itt_addr = ALIGN(itt_addr, ITS_ITT_ALIGN);
 
 	its_encode_cmd(cmd, GITS_CMD_MAPD);
 	its_encode_devid(cmd, desc->its_mapd_cmd.dev->device_id);
@@ -3495,7 +3494,7 @@ static struct its_device *its_create_device(struct its_node *its, u32 dev_id,
 	 */
 	nr_ites = max(2, nvecs);
 	sz = nr_ites * (FIELD_GET(GITS_TYPER_ITT_ENTRY_SIZE, its->typer) + 1);
-	sz = max(sz, ITS_ITT_ALIGN) + ITS_ITT_ALIGN - 1;
+	sz = max(sz, ITS_ITT_ALIGN);
 
 	itt = itt_alloc_pool(its->numa_node, sz);

---

## [20] Steven Price — 2024-08-19
*Subject: [PATCH v5 19/19] virt: arm-cca-guest: TSM_REPORT support for realms*

From: Sami Mujawar <sami.mujawar@arm.com>

Introduce an arm-cca-guest driver that registers with
the configfs-tsm module to provide user interfaces for
retrieving an attestation token.

When a new report is requested the arm-cca-guest driver
invokes the appropriate RSI interfaces to query an
attestation token.

The steps to retrieve an attestation token are as follows:
  1. Mount the configfs filesystem if not already mounted
     mount -t configfs none /sys/kernel/config
  2. Generate an attestation token
     report=/sys/kernel/config/tsm/report/report0
     mkdir $report
     dd if=/dev/urandom bs=64 count=1 > $report/inblob
     hexdump -C $report/outblob
     rmdir $report

Signed-off-by: Sami Mujawar <sami.mujawar@arm.com>
Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
v3: Minor improvements to comments and adapt to the renaming of
GRANULE_SIZE to RSI_GRANULE_SIZE.
---
 drivers/virt/coco/Kconfig                     |   2 +
 drivers/virt/coco/Makefile                    |   1 +
 drivers/virt/coco/arm-cca-guest/Kconfig       |  11 +
 drivers/virt/coco/arm-cca-guest/Makefile      |   2 +
 .../virt/coco/arm-cca-guest/arm-cca-guest.c   | 211 ++++++++++++++++++
 5 files changed, 227 insertions(+)
 create mode 100644 drivers/virt/coco/arm-cca-guest/Kconfig
 create mode 100644 drivers/virt/coco/arm-cca-guest/Makefile
 create mode 100644 drivers/virt/coco/arm-cca-guest/arm-cca-guest.c

diff --git a/drivers/virt/coco/Kconfig b/drivers/virt/coco/Kconfig
index 87d142c1f932..4fb69804b622 100644
--- a/drivers/virt/coco/Kconfig
+++ b/drivers/virt/coco/Kconfig
@@ -12,3 +12,5 @@ source "drivers/virt/coco/efi_secret/Kconfig"
 source "drivers/virt/coco/sev-guest/Kconfig"
 
 source "drivers/virt/coco/tdx-guest/Kconfig"
+
+source "drivers/virt/coco/arm-cca-guest/Kconfig"
diff --git a/drivers/virt/coco/Makefile b/drivers/virt/coco/Makefile
index 18c1aba5edb7..a6228a1bf992 100644
--- a/drivers/virt/coco/Makefile
+++ b/drivers/virt/coco/Makefile
@@ -6,3 +6,4 @@ obj-$(CONFIG_TSM_REPORTS)	+= tsm.o
 obj-$(CONFIG_EFI_SECRET)	+= efi_secret/
 obj-$(CONFIG_SEV_GUEST)		+= sev-guest/
 obj-$(CONFIG_INTEL_TDX_GUEST)	+= tdx-guest/
+obj-$(CONFIG_ARM_CCA_GUEST)	+= arm-cca-guest/
diff --git a/drivers/virt/coco/arm-cca-guest/Kconfig b/drivers/virt/coco/arm-cca-guest/Kconfig
new file mode 100644
index 000000000000..9dd27c3ee215
--- /dev/null
+++ b/drivers/virt/coco/arm-cca-guest/Kconfig
@@ -0,0 +1,11 @@
+config ARM_CCA_GUEST
+	tristate "Arm CCA Guest driver"
+	depends on ARM64
+	default m
+	select TSM_REPORTS
+	help
+	  The driver provides userspace interface to request and
+	  attestation report from the Realm Management Monitor(RMM).
+
+	  If you choose 'M' here, this module will be called
+	  arm-cca-guest.
diff --git a/drivers/virt/coco/arm-cca-guest/Makefile b/drivers/virt/coco/arm-cca-guest/Makefile
new file mode 100644
index 000000000000..69eeba08e98a
--- /dev/null
+++ b/drivers/virt/coco/arm-cca-guest/Makefile
@@ -0,0 +1,2 @@
+# SPDX-License-Identifier: GPL-2.0-only
+obj-$(CONFIG_ARM_CCA_GUEST) += arm-cca-guest.o
diff --git a/drivers/virt/coco/arm-cca-guest/arm-cca-guest.c b/drivers/virt/coco/arm-cca-guest/arm-cca-guest.c
new file mode 100644
index 000000000000..7f724a03676f
--- /dev/null
+++ b/drivers/virt/coco/arm-cca-guest/arm-cca-guest.c
@@ -0,0 +1,211 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/*
+ * Copyright (C) 2023 ARM Ltd.
+ */
+
+#include <linux/arm-smccc.h>
+#include <linux/cc_platform.h>
+#include <linux/kernel.h>
+#include <linux/module.h>
+#include <linux/smp.h>
+#include <linux/tsm.h>
+#include <linux/types.h>
+
+#include <asm/rsi.h>
+
+/**
+ * struct arm_cca_token_info - a descriptor for the token buffer.
+ * @granule:	PA of the page to which the token will be written
+ * @offset:	Offset within granule to start of buffer in bytes
+ * @len:	Number of bytes of token data that was retrieved
+ * @result:	result of rsi_attestation_token_continue operation
+ */
+struct arm_cca_token_info {
+	phys_addr_t     granule;
+	unsigned long   offset;
+	int             result;
+};
+
+/**
+ * arm_cca_attestation_continue - Retrieve the attestation token data.
+ *
+ * @param: pointer to the arm_cca_token_info
+ *
+ * Attestation token generation is a long running operation and therefore
+ * the token data may not be retrieved in a single call. Moreover, the
+ * token retrieval operation must be requested on the same CPU on which the
+ * attestation token generation was initialised.
+ * This helper function is therefore scheduled on the same CPU multiple
+ * times until the entire token data is retrieved.
+ */
+static void arm_cca_attestation_continue(void *param)
+{
+	unsigned long len;
+	unsigned long size;
+	struct arm_cca_token_info *info;
+
+	if (!param)
+		return;
+
+	info = (struct arm_cca_token_info *)param;
+
+	size = RSI_GRANULE_SIZE - info->offset;
+	info->result = rsi_attestation_token_continue(info->granule,
+						      info->offset, size, &len);
+	info->offset += len;
+}
+
+/**
+ * arm_cca_report_new - Generate a new attestation token.
+ *
+ * @report: pointer to the TSM report context information.
+ * @data:  pointer to the context specific data for this module.
+ *
+ * Initialise the attestation token generation using the challenge data
+ * passed in the TSM decriptor. Allocate memory for the attestation token
+ * and schedule calls to retrieve the attestation token on the same CPU
+ * on which the attestation token generation was initialised.
+ *
+ * The challenge data must be at least 32 bytes and no more than 64 bytes. If
+ * less than 64 bytes are provided it will be zero padded to 64 bytes.
+ *
+ * Return:
+ * * %0        - Attestation token generated successfully.
+ * * %-EINVAL  - A parameter was not valid.
+ * * %-ENOMEM  - Out of memory.
+ * * %-EFAULT  - Failed to get IPA for memory page(s).
+ * * A negative status code as returned by smp_call_function_single().
+ */
+static int arm_cca_report_new(struct tsm_report *report, void *data)
+{
+	int ret;
+	int cpu;
+	long max_size;
+	unsigned long token_size;
+	struct arm_cca_token_info info;
+	void *buf;
+	u8 *token __free(kvfree) = NULL;
+	struct tsm_desc *desc = &report->desc;
+
+	if (!report)
+		return -EINVAL;
+
+	if (desc->inblob_len < 32 || desc->inblob_len > 64)
+		return -EINVAL;
+
+	/*
+	 * Get a CPU on which the attestation token generation will be
+	 * scheduled and initialise the attestation token generation.
+	 */
+	cpu = get_cpu();
+	max_size = rsi_attestation_token_init(desc->inblob, desc->inblob_len);
+	put_cpu();
+
+	if (max_size <= 0)
+		return -EINVAL;
+
+	/* Allocate outblob */
+	token = kvzalloc(max_size, GFP_KERNEL);
+	if (!token)
+		return -ENOMEM;
+
+	/*
+	 * Since the outblob may not be physically contiguous, use a page
+	 * to bounce the buffer from RMM.
+	 */
+	buf = alloc_pages_exact(RSI_GRANULE_SIZE, GFP_KERNEL);
+	if (!buf)
+		return -ENOMEM;
+
+	/* Get the PA of the memory page(s) that were allocated. */
+	info.granule = (unsigned long)virt_to_phys(buf);
+
+	token_size = 0;
+	/* Loop until the token is ready or there is an error. */
+	do {
+		/* Retrieve one RSI_GRANULE_SIZE data per loop iteration. */
+		info.offset = 0;
+		do {
+			/*
+			 * Schedule a call to retrieve a sub-granule chunk
+			 * of data per loop iteration.
+			 */
+			ret = smp_call_function_single(cpu,
+						       arm_cca_attestation_continue,
+						       (void *)&info, true);
+			if (ret != 0) {
+				token_size = 0;
+				goto exit_free_granule_page;
+			}
+
+			ret = info.result;
+		} while ((ret == RSI_INCOMPLETE) &&
+			 (info.offset < RSI_GRANULE_SIZE));
+
+		/*
+		 * Copy the retrieved token data from the granule
+		 * to the token buffer, ensuring that the RMM doesn't
+		 * overflow the buffer.
+		 */
+		if (WARN_ON(token_size + info.offset > max_size))
+			break;
+		memcpy(&token[token_size], buf, info.offset);
+		token_size += info.offset;
+	} while (ret == RSI_INCOMPLETE);
+
+	if (ret != RSI_SUCCESS) {
+		ret = -ENXIO;
+		token_size = 0;
+		goto exit_free_granule_page;
+	}
+
+	report->outblob = no_free_ptr(token);
+exit_free_granule_page:
+	report->outblob_len = token_size;
+	free_pages_exact(buf, RSI_GRANULE_SIZE);
+	return ret;
+}
+
+static const struct tsm_ops arm_cca_tsm_ops = {
+	.name = KBUILD_MODNAME,
+	.report_new = arm_cca_report_new,
+};
+
+/**
+ * arm_cca_guest_init - Register with the Trusted Security Module (TSM)
+ * interface.
+ *
+ * Return:
+ * * %0        - Registered successfully with the TSM interface.
+ * * %-ENODEV  - The execution context is not an Arm Realm.
+ * * %-EINVAL  - A parameter was not valid.
+ * * %-EBUSY   - Already registered.
+ */
+static int __init arm_cca_guest_init(void)
+{
+	int ret;
+
+	if (!is_realm_world())
+		return -ENODEV;
+
+	ret = tsm_register(&arm_cca_tsm_ops, NULL);
+	if (ret < 0)
+		pr_err("Failed to register with TSM.\n");
+
+	return ret;
+}
+module_init(arm_cca_guest_init);
+
+/**
+ * arm_cca_guest_exit - unregister with the Trusted Security Module (TSM)
+ * interface.
+ */
+static void __exit arm_cca_guest_exit(void)
+{
+	tsm_unregister(&arm_cca_tsm_ops);
+}
+module_exit(arm_cca_guest_exit);
+
+MODULE_AUTHOR("Sami Mujawar <sami.mujawar@arm.com>");
+MODULE_DESCRIPTION("Arm CCA Guest TSM Driver.");
+MODULE_LICENSE("GPL");

---

## [21] Suzuki K Poulose — 2024-08-19
*Subject: Re: [PATCH v5 05/19] arm64: Detect if in a realm and set RIPAS RAM*

Hi Steven

On 19/08/2024 14:19, Steven Price wrote:
> From: Suzuki K Poulose <suzuki.poulose@arm.com>
> 

I think this should be RSI_CHANGE_DESTROYED, as we are transitioning a 
page to "shared" (i.e, IPA state to EMPTY) and we do not expect the data
to be retained over the transition. Thus we do not care if the IPA was
in RIPAS_DESTROYED.

Rest looks good to me.


Suzuki

---

## [22] Steven Price — 2024-08-19
*Subject: Re: [PATCH v5 05/19] arm64: Detect if in a realm and set RIPAS RAM*

On 19/08/2024 15:04, Suzuki K Poulose wrote:
> Hi Steven
> 

Fair point - although something has gone wrong if the VMM has destroyed
the memory we're calling this on. But it's not going to cause problems
using RSI_CHANGE_DESTROYED and might be (slightly) more efficient.

Thanks,

Steve

> Rest looks good to me.
>

---

## [23] Suzuki K Poulose — 2024-08-19
*Subject: Re: [PATCH v5 11/19] arm64: rsi: Map unprotected MMIO as decrypted*

Hi Steven

On 19/08/2024 14:19, Steven Price wrote:
> From: Suzuki K Poulose <suzuki.poulose@arm.com>
> 

This looks like it should be part of the previous patch ? Otherwise 
looks good to me.

Suzuki

---

## [24] Suzuki K Poulose — 2024-08-19
*Subject: Re: [PATCH v5 10/19] arm64: Override set_fixmap_io*

On 19/08/2024 14:19, Steven Price wrote:
> From: Suzuki K Poulose <suzuki.poulose@arm.com>
> 

With the ioremap_prot_hook introduction, this one looks like should use
that, instead of open coding the same thing. Thoughts ?

Suzuki

---

## [25] Marc Zyngier — 2024-08-19
*Subject: Re: [PATCH v5 17/19] irqchip/gic-v3-its: Share ITS tables with a non-trusted hypervisor*

On Mon, 19 Aug 2024 14:19:22 +0100,
Steven Price <steven.price@arm.com> wrote:
> 
> Within a realm guest the ITS is emulated by the host. This means the

I think this patch and the next are pretty ripe, and shouldn't have to
wait much longer.

Can you please send them as a separate irqchip series, with the
relevant people on Cc (realistically, tglx and me), with a

Reviewed-by: Marc Zyngier <maz@kernel.org>

added to them?

Thanks,

	M.

---

## [26] Suzuki K Poulose — 2024-08-19
*Subject: Re: [PATCH v5 17/19] irqchip/gic-v3-its: Share ITS tables with a
 non-trusted hypervisor*

Hi Steven,

On 19/08/2024 14:19, Steven Price wrote:
> Within a realm guest the ITS is emulated by the host. This means the
> allocations must have been made available to the host by a call to

This may not be sufficient to make it future proof. We need to detect if
the GIC is private vs shared, before we make the allocation choice. 
Please see below :

> Co-developed-by: Suzuki K Poulose <suzuki.poulose@arm.com>
> Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>


How about something like this folded into this patch ? Or if this patch 
goes in independently, we could carry the following as part of the CCA
series.

diff --git a/drivers/irqchip/irq-gic-v3-its.c 
b/drivers/irqchip/irq-gic-v3-its.c
index 6f4ddf7faed1..f1a779b52210 100644
--- a/drivers/irqchip/irq-gic-v3-its.c
+++ b/drivers/irqchip/irq-gic-v3-its.c
@@ -209,7 +209,7 @@ static struct page *its_alloc_pages_node(int node, 
gfp_t gfp,

  	page = alloc_pages_node(node, gfp, order);

-	if (page)
+	if (gic_rdists->is_shared && page)
  		set_memory_decrypted((unsigned long)page_address(page),
  				     BIT(order));
  	return page;
@@ -222,7 +222,8 @@ static struct page *its_alloc_pages(gfp_t gfp, 
unsigned int order)

  static void its_free_pages(void *addr, unsigned int order)
  {
-	set_memory_encrypted((unsigned long)addr, BIT(order));
+	if (gic_rdists->is_shared)
+		set_memory_encrypted((unsigned long)addr, BIT(order));
  	free_pages((unsigned long)addr, order);
  }

diff --git a/drivers/irqchip/irq-gic-v3.c b/drivers/irqchip/irq-gic-v3.c
index 6fb276504bcc..48c6b2c8dd8c 100644
--- a/drivers/irqchip/irq-gic-v3.c
+++ b/drivers/irqchip/irq-gic-v3.c
@@ -2015,6 +2015,8 @@ static int __init gic_init_bases(phys_addr_t 
dist_phys_base,
  	typer = readl_relaxed(gic_data.dist_base + GICD_TYPER);
  	gic_data.rdists.gicd_typer = typer;

+	gic_data.rdists.is_shared = 
!arm64_is_iomem_private(gic_data.dist_phys_base,
+							    PAGE_SIZE);
  	gic_enable_quirks(readl_relaxed(gic_data.dist_base + GICD_IIDR),
  			  gic_quirks, &gic_data);

diff --git a/include/linux/irqchip/arm-gic-v3.h 
b/include/linux/irqchip/arm-gic-v3.h
index 728691365464..1edc33608d52 100644
--- a/include/linux/irqchip/arm-gic-v3.h
+++ b/include/linux/irqchip/arm-gic-v3.h
@@ -631,6 +631,7 @@ struct rdists {
  	bool			has_rvpeid;
  	bool			has_direct_lpi;
  	bool			has_vpend_valid_dirty;
+	bool			is_shared;
  };

  struct irq_domain;

---

## [27] Marc Zyngier — 2024-08-19
*Subject: Re: [PATCH v5 17/19] irqchip/gic-v3-its: Share ITS tables with a non-trusted hypervisor*

On Mon, 19 Aug 2024 15:51:00 +0100,
Suzuki K Poulose <suzuki.poulose@arm.com> wrote:
> 
> Hi Steven,

What do you mean by that? Do you foresee a *GICv3* implementation on
the realm side?

[...]

> How about something like this folded into this patch ? Or if this
> patch goes in independently, we could carry the following as part of

Why would you base the status of the RDs on that of the distributor?

>  	gic_enable_quirks(readl_relaxed(gic_data.dist_base + GICD_IIDR),
>  			  gic_quirks, &gic_data);

I really don't like this.

If we have to go down the route of identifying whether the GIC needs
encryption or not based on the platform, then maybe we should bite the
bullet and treat it as a first class device, given that we expect
devices to be either realm or non-secure.

Thanks,

	M.

---

## [28] Suzuki K Poulose — 2024-08-19
*Subject: Re: [PATCH v5 17/19] irqchip/gic-v3-its: Share ITS tables with a
 non-trusted hypervisor*

Hi Marc

On 19/08/2024 16:24, Marc Zyngier wrote:
> On Mon, 19 Aug 2024 15:51:00 +0100,
> Suzuki K Poulose <suzuki.poulose@arm.com> wrote:

No, but it may be emulated in the Realm World (by a higher privileged 
component, with future RMM versions with Planes - Plane0) and this
"Realm guest" may run in a lesser privileged plane and must use
"protected" accesses to make sure the accesses are seen by the "Realm
world" emulator.

> 
> [...]

We expect that, the GIC as a whole is either Realm or non-secure, but
not split (like most of the devices). The only reason for using rdists
is because thats shared and available with the ITS driver code. (and
was an easy hack). Happy to change this to something better.

> 
>>   	gic_enable_quirks(readl_relaxed(gic_data.dist_base + GICD_IIDR),

Agreed and that is exactly we would like. i.e., treat the GIC as either
Realm or NS (as a whole). Now, how do we make that decision is based on
whether GIC Distributor area is private or not. Like I mentioned above, 
we need a cleaner way of making this available in the ITS driver.

Thoughts ? Is that what you were hinting at ?

Suzuki


> Thanks,
>

---

## [29] Will Deacon — 2024-08-23
*Subject: Re: [PATCH v5 04/19] firmware/psci: Add psci_early_test_conduit()*

On Mon, Aug 19, 2024 at 02:19:09PM +0100, Steven Price wrote:
> From: Jean-Philippe Brucker <jean-philippe@linaro.org>
> 

This still looks incomplete to me as per my earlier comments:

https://lore.kernel.org/all/20240709104851.GE12978@willie-the-truck/

For the first implementation, can we punt the RIPAS_RAM to the bootloader
and drop support for earlycon? Even if we manage to shoe-horn enough code
into the early boot path, I think we'll regret it later on because there's
always something that wants to be first and it inevitably ends up being
a nightmare to maintain.

Will

---

## [30] Catalin Marinas — 2024-08-26
*Subject: Re: [PATCH v5 01/19] arm64: mm: Add top-level dispatcher for
 internal mem_encrypt API*

On Mon, Aug 19, 2024 at 02:19:06PM +0100, Steven Price wrote:
> From: Will Deacon <will@kernel.org>
> 

Reviewed-by: Catalin Marinas <catalin.marinas@arm.com>

---

## [31] Catalin Marinas — 2024-08-26
*Subject: Re: [PATCH v5 02/19] arm64: mm: Add confidential computing hook to
 ioremap_prot()*

On Mon, Aug 19, 2024 at 02:19:07PM +0100, Steven Price wrote:
> From: Will Deacon <will@kernel.org>
> 

I should have commented on Will's original series since it's more likely
to affect pKVM than CCA. Anyway, this is all good with the hook,
especially if the guest needs to do some paravirtual call. However, we
have other instances of mapping I/O memory without going through
ioremap() - io_remap_pfn_range() which uses pgprot_decrypted(). We'll
need some hooks there as well. And I think there are a few other cases
of pgprot_decrypted() but we can fix them on a case by case bases (e.g.
routing them through io_remap_pfn_range()).

For this patch:

Reviewed-by: Catalin Marinas <catalin.marinas@arm.com>

---

## [32] Catalin Marinas — 2024-08-26
*Subject: Re: [PATCH v5 03/19] arm64: rsi: Add RSI definitions*

On Mon, Aug 19, 2024 at 02:19:08PM +0100, Steven Price wrote:
> From: Suzuki K Poulose <suzuki.poulose@arm.com>
> 

Acked-by: Catalin Marinas <catalin.marinas@arm.com>

(I did cross-check the definitions with the spec)

> +struct realm_config {
> +	union {

It might have been easier to just write the pad sizes in decimal (trying
to figure out what 0xe00 is ;)). Anyway, it's fine like this as well.

---

## [33] Catalin Marinas — 2024-08-26
*Subject: Re: [PATCH v5 04/19] firmware/psci: Add psci_early_test_conduit()*

On Mon, Aug 19, 2024 at 02:19:09PM +0100, Steven Price wrote:
> From: Jean-Philippe Brucker <jean-philippe@linaro.org>
> 

On the code itself:

Reviewed-by: Catalin Marinas <catalin.marinas@arm.com>

However, Will has a point and it would be good if we can avoid this
early setup as much as possible. If it's just the early console used for
debugging, maybe just pass the full IPA address on the command line and
allow those high addresses in fixmap. Not sure about the EFI map.

---

## [34] Catalin Marinas — 2024-08-26
*Subject: Re: [PATCH v5 05/19] arm64: Detect if in a realm and set RIPAS RAM*

On Mon, Aug 19, 2024 at 02:19:10PM +0100, Steven Price wrote:
> +static bool rsi_version_matches(void)
> +{

I don't have the spec at hand now (on a plane) but given the possibility
of a 1.0 guest regressing on later RMM versions, I wonder whether we
should simply bail out if it's not an exact version match. I forgot what
the spec says about returned ranges (they were pretty confusing last
time I checked).

> +
> +void __init arm64_rsi_setup_memory(void)

Would it help debugging if we print the memory ranges as well rather
than just a BUG_ON()?

---

## [35] Catalin Marinas — 2024-08-26
*Subject: Re: [PATCH v5 06/19] arm64: realm: Query IPA size from the RMM*

On Mon, Aug 19, 2024 at 02:19:11PM +0100, Steven Price wrote:
> The top bit of the configured IPA size is used as an attribute to
> control whether the address is protected or shared. Query the

Reviewed-by: Catalin Marinas <catalin.marinas@arm.com>

---

## [36] Catalin Marinas — 2024-08-26
*Subject: Re: [PATCH v5 07/19] arm64: rsi: Add support for checking whether an
 MMIO is protected*

On Mon, Aug 19, 2024 at 02:19:12PM +0100, Steven Price wrote:
> +static inline bool arm64_is_iomem_private(phys_addr_t phys_addr, size_t size)
> +{

I was wondering whether to return true in non-realm world. It doesn't
matter since the pgprot_decrypted() wouldn't do anything. Anyway:

Reviewed-by: Catalin Marinas <catalin.marinas@arm.com>

---

## [37] Catalin Marinas — 2024-08-26
*Subject: Re: [PATCH v5 09/19] fixmap: Pass down the full phys address for
 set_fixmap_io*

On Mon, Aug 19, 2024 at 02:19:14PM +0100, Steven Price wrote:
> From: Suzuki K Poulose <suzuki.poulose@arm.com>
> 

Will was keen (and I'd prefer it as well) to get rid of the early fixmap
code, at least for the time being. Have you tried without these and the
early RSI probing?

Apart from the earlycon I recall you mentioned EFI early maps. These
would be more problematic.

---

## [38] Catalin Marinas — 2024-08-26
*Subject: Re: [PATCH v5 12/19] efi: arm64: Map Device with Prot Shared*

On Mon, Aug 19, 2024 at 02:19:17PM +0100, Steven Price wrote:
> From: Suzuki K Poulose <suzuki.poulose@arm.com>
> 

Nit: This pattern appears in the previous patch as well. Maybe add a
pgprot_maybe_decrypted().

The patch looks fine other than the need for an early initialisation if
we find any workaround. In the pKVM case, IIUC this would need to call
into the hypervisor as well but that can be handled by the bootloader.
For CCA, our problem is setting the top bit of the IPA.

What's the x86 approach here? The EFI is a bigger problem than the
earlycon.

---

## [39] Catalin Marinas — 2024-08-26
*Subject: Re: [PATCH v5 13/19] arm64: Make the PHYS_MASK_SHIFT dynamic*

On Mon, Aug 19, 2024 at 02:19:18PM +0100, Steven Price wrote:
> Make the PHYS_MASK_SHIFT dynamic for Realms. This is only is required
> for masking the PFN from a pte entry.

Unless my grep failed, pte_pfn() hasn't used PHYS_MASK for many years,
since commit 75387b92635e ("arm64: handle 52-bit physical addresses in
page table entries").

Can you check what pte_pfn() returns on a shared page?

Unless we need this macro for other things, I'm more tempted to clear
the bit in __pte_to_phys().

---

## [40] Catalin Marinas — 2024-08-26
*Subject: Re: [PATCH v5 14/19] arm64: Enforce bounce buffers for realm DMA*

On Mon, Aug 19, 2024 at 02:19:19PM +0100, Steven Price wrote:
> Within a realm guest it's not possible for a device emulated by the VMM
> to access arbitrary guest memory. So force the use of bounce buffers to

IIRC Will mentioned on a previous version of this series: what do we do
with the kmalloc() minalign bouncing (or other bouncing)? I think this
would only work if the device is shared.

I'm more and more inclined to only support shared devices with this
series (no dev assignment) and make it a strict dependence on RMM 1.0.
Running it in a different configuration with private devices will fall
apart. With this condition, the patch looks fine:

Reviewed-by: Catalin Marinas <catalin.marinas@arm.com>

---

## [41] Catalin Marinas — 2024-08-26
*Subject: Re: [PATCH v5 15/19] arm64: mm: Avoid TLBI when marking pages as
 valid*

On Mon, Aug 19, 2024 at 02:19:20PM +0100, Steven Price wrote:
> When __change_memory_common() is purely setting the valid bit on a PTE
> (e.g. via the set_memory_valid() call) there is no need for a TLBI as

Reviewed-by: Catalin Marinas <catalin.marinas@arm.com>

---

## [42] Catalin Marinas — 2024-08-26
*Subject: Re: [PATCH v5 16/19] arm64: Enable memory encrypt for Realms*

On Mon, Aug 19, 2024 at 02:19:21PM +0100, Steven Price wrote:
> From: Suzuki K Poulose <suzuki.poulose@arm.com>
> 

Reviewed-by: Catalin Marinas <catalin.marinas@arm.com>

---

## [43] Steven Price — 2024-08-30
*Subject: Re: [PATCH v5 05/19] arm64: Detect if in a realm and set RIPAS RAM*

On 26/08/2024 11:03, Catalin Marinas wrote:
> On Mon, Aug 19, 2024 at 02:19:10PM +0100, Steven Price wrote:
>> +static bool rsi_version_matches(void)

Well the idea at least is that the RMM can tell us that it is providing
a 1.0 compatible interface. So it might be supporting 1.x but it's
promising that what it's providing is 1.0 compatible.

Indeed the spec allows the RMM to emulate 1.0 while supporting a higher
(incompatible) interface as well - which is where the version ranges
come in. So in the future we might negotiate versions with the RMM, or
opportunistically use newer features if the RMM provides them. But
obviously for now the guest is only 1.0.

I'd prefer not to add an exact version match because then upgrading the
RMM would break existing guests and would probably lead to pressure for
the RMM to simply lie to guests to avoid them breaking on upgrade.

>> +
>> +void __init arm64_rsi_setup_memory(void)

Yes that would probably be useful - I'll fix that.

Thanks,
Steve

---

## [44] Steven Price — 2024-08-30
*Subject: Re: [PATCH v5 10/19] arm64: Override set_fixmap_io*

On 19/08/2024 15:13, Suzuki K Poulose wrote:
> On 19/08/2024 14:19, Steven Price wrote:
>> From: Suzuki K Poulose <suzuki.poulose@arm.com>

I can see the logic, but it's not quite that simple to implement. Either
the ioremap_prot_hook needs moving out (and presumably) renaming to be a
more generic "override device pgprot" mechanism, we it would be a horrid
hack to put ioremap code in arch/arm64/mm/ioremap.c to handle this.

Given that we're not even sure that the set_fixmap hack is a good idea,
I'll leave this alone for now - the open coding is clear even if it's a
duplicate.

Thanks,
Steve

---

## [45] Steven Price — 2024-08-30
*Subject: Re: [PATCH v5 11/19] arm64: rsi: Map unprotected MMIO as decrypted*

On 19/08/2024 15:11, Suzuki K Poulose wrote:
> Hi Steven
> 

Good spot - yes it should!

Thanks,
Steve

---

## [46] Steven Price — 2024-08-30
*Subject: Re: [PATCH v5 04/19] firmware/psci: Add psci_early_test_conduit()*

On 23/08/2024 14:29, Will Deacon wrote:
> On Mon, Aug 19, 2024 at 02:19:09PM +0100, Steven Price wrote:
>> From: Jean-Philippe Brucker <jean-philippe@linaro.org>

Short-answer: yes, although it has drawbacks.

I've never been keen on the RIPAS_RAM requirement, the logic behind it
is that it makes it easier to have varying amounts of RAM given to the
guest without affecting the attestation. But it's a weak argument and
I'd personally prefer to punt the responsibility to a bootloader/VMM.

earlycon should be fairly easy to remove - and it doesn't have to
actually kill earlycon because we can pass in the address with the top
bit set - it just requires fixing up the VMM.

EFI is the main issue.

I'll have a go at coming up with a cut down series - at the very least
I'll see if I can rearrange to have the troublesome parts at the end so
they can be dropped if necessary.

Steve

---

## [47] Aneesh Kumar K.V — 2024-09-02
*Subject: Re: [PATCH v5 19/19] virt: arm-cca-guest: TSM_REPORT support for
 realms*

Steven Price <steven.price@arm.com> writes:

> From: Sami Mujawar <sami.mujawar@arm.com>
 
...
 
> --- /dev/null
> +++ b/drivers/virt/coco/arm-cca-guest/Kconfig

Can we rename the generic Kconfig variable to ARM_CCA_TSM_REPORT?. Also
should the directory be arm64-cca-guest?


-aneesh

---

## [48] Gavin Shan — 2024-09-06
*Subject: Re: [PATCH v5 07/19] arm64: rsi: Add support for checking whether an
 MMIO is protected*

Hi Steven,

On 8/19/24 11:19 PM, Steven Price wrote:
> From: Suzuki K Poulose <suzuki.poulose@arm.com>
> 

I don't understand why @size needs to be checked here. Its initial value
taken from the input parameter should be larger than zero and its value
is never updated in the loop. So I'm understanding @size is always larger
than zero, and the condition would be something like below if I'm correct.

        return (base >= end);     /* RSI_RIPAS_IO returned for all granules */

Another issue is @top is always zero with the latest tf-rmm. More details
are provided below.

> +EXPORT_SYMBOL(arm64_rsi_is_protected_mmio);
> +

The unexpected calltrace is continuously observed with host/v4, guest/v5 and
latest upstream tf-rmm on 'WARN_ON(top <= base)' because @top is never updated
by the latest tf-rmm. The following call path indicates how SMC_RSI_IPA_STATE_GET
is handled by tf-rmm. I don't see RSI_RIPAS_IO is defined there and @top is
updated.

[    0.000000] ------------[ cut here ]------------
[    0.000000] WARNING: CPU: 0 PID: 0 at arch/arm64/kernel/rsi.c:103 arm64_rsi_is_protected_mmio+0xf0/0x110
[    0.000000] Modules linked in:
[    0.000000] CPU: 0 UID: 0 PID: 0 Comm: swapper Not tainted 6.11.0-rc1-gavin-g3527d001084e #1
[    0.000000] Hardware name: linux,dummy-virt (DT)
[    0.000000] pstate: 200000c5 (nzCv daIF -PAN -UAO -TCO -DIT -SSBS BTYPE=--)
[    0.000000] pc : arm64_rsi_is_protected_mmio+0xf0/0x110
[    0.000000] lr : arm64_rsi_is_protected_mmio+0x80/0x110
[    0.000000] sp : ffffcd7097053bf0
[    0.000000] x29: ffffcd7097053c30 x28: 0000000000000000 x27: 0000000000000000
[    0.000000] x26: 00000000000003d0 x25: 00000000ffffff8e x24: ffffcd7096831bd0
[    0.000000] x23: ffffcd7097053c08 x22: 00000000c4000198 x21: 0000000000001000
[    0.000000] x20: 0000000001001000 x19: 0000000001000000 x18: 0000000000000002
[    0.000000] x17: 0000000000000000 x16: 0000000000000010 x15: 0001000080000000
[    0.000000] x14: 0068000000000703 x13: ffffffffff5fe000 x12: ffffcd7097053ba4
[    0.000000] x11: 00000000000003d0 x10: ffffcd7097053bc4 x9 : 0000000000000444
[    0.000000] x8 : ffffffffff5fe000 x7 : 0000000000000000 x6 : 0000000000000000
[    0.000000] x5 : 0000000000000000 x4 : 0000000000000000 x3 : 0000000000000000
[    0.000000] x2 : 0000000000000000 x1 : 0000000000000000 x0 : 0000000000000000
[    0.000000] Call trace:
[    0.000000]  arm64_rsi_is_protected_mmio+0xf0/0x110
[    0.000000]  set_fixmap_io+0x8c/0xd0
[    0.000000]  of_setup_earlycon+0xa0/0x294
[    0.000000]  early_init_dt_scan_chosen_stdout+0x104/0x1dc
[    0.000000]  acpi_boot_table_init+0x1a4/0x2d8
[    0.000000]  setup_arch+0x240/0x610
[    0.000000]  start_kernel+0x6c/0x708
[    0.000000]  __primary_switched+0x80/0x88

===> tf-rmm: git@github.com:TF-RMM/tf-rmm.git

handle_realm_rsi
   handle_rsi_ipa_state_get
     realm_ipa_get_ripas

===> tf-rmm/lib/s2tt/include/ripas.h

enum ripas {
         RIPAS_EMPTY = RMI_EMPTY,        /* Unused IPA for Realm */
         RIPAS_RAM = RMI_RAM,            /* IPA used for Code/Data by Realm */
         RIPAS_DESTROYED = RMI_DESTROYED /* IPA is inaccessible to the Realm */
};

===> tf-rmm/runtime/rsi/memory.c

void handle_rsi_ipa_state_get(struct rec *rec,
                               struct rsi_result *res)
{
         unsigned long ipa = rec->regs[1];
         enum s2_walk_status ws;
         enum ripas ripas_val = RIPAS_EMPTY;

         res->action = UPDATE_REC_RETURN_TO_REALM;

         if (!GRANULE_ALIGNED(ipa) || !addr_in_rec_par(rec, ipa)) {
                 res->smc_res.x[0] = RSI_ERROR_INPUT;
                 return;
         }

         ws = realm_ipa_get_ripas(rec, ipa, &ripas_val);
         if (ws == WALK_SUCCESS) {
                 res->smc_res.x[0] = RSI_SUCCESS;
                 res->smc_res.x[1] = (unsigned long)ripas_val;
         } else {
                 res->smc_res.x[0] = RSI_ERROR_INPUT;
         }
}

Thanks,
Gavin

---

## [49] Gavin Shan — 2024-09-06
*Subject: Re: [PATCH v5 07/19] arm64: rsi: Add support for checking whether an
 MMIO is protected*

On 9/6/24 2:32 PM, Gavin Shan wrote:
> On 8/19/24 11:19 PM, Steven Price wrote:
>> From: Suzuki K Poulose <suzuki.poulose@arm.com>

I have local changes like below to avoid the unexpected calltrace.

diff --git a/arch/arm64/kernel/rsi.c b/arch/arm64/kernel/rsi.c
index 9cb3353e5cbf..3d132d45fd83 100644
--- a/arch/arm64/kernel/rsi.c
+++ b/arch/arm64/kernel/rsi.c
@@ -100,14 +100,15 @@ bool arm64_rsi_is_protected_mmio(phys_addr_t base, size_t size)
         while (base < end) {
                 if (WARN_ON(rsi_ipa_state_get(base, end, &ripas, &top)))
                         break;
-               if (WARN_ON(top <= base))
+               if (WARN_ON(top && top <= base))
                         break;
                 if (ripas != RSI_RIPAS_IO)
                         break;
-               base = top;
+
+               base = top ? top : end;
         }
  
-       return (size && base >= end);
+       return base >= end;

Thanks,
Gavin

---

## [50] Steven Price — 2024-09-06
*Subject: Re: [PATCH v5 07/19] arm64: rsi: Add support for checking whether an
 MMIO is protected*

On 06/09/2024 05:32, Gavin Shan wrote:
> Hi Steven,
> 

Yes you are correct. I'm not entirely sure why it was written that way.
The only change dropping 'size' as you suggest is that a zero-sized
region is considered protected. But I'd consider it a bug if this is
called with size=0. I'll drop 'size' here.

>        return (base >= end);     /* RSI_RIPAS_IO returned for all
> granules */

That suggests that you are not actually using the 'latest' tf-rmm ;)
(for some definition of 'latest' which might not be obvious!)

From the cover letter:

> As mentioned above the new RMM specification means that corresponding
> changes need to be made in the RMM, at this time these changes are still

Sorry, I should probably have made this much more prominent in the cover
letter.

Running something like...

 git fetch https://git.trustedfirmware.org/TF-RMM/tf-rmm.git \
	refs/changes/85/30485/11

... should get you the latest. Hopefully these changes will get merged
to the main branch soon.

Steve

>> +EXPORT_SYMBOL(arm64_rsi_is_protected_mmio);
>> +

---

## [51] Shanker Donthineni — 2024-09-06
*Subject: Re: [PATCH v5 05/19] arm64: Detect if in a realm and set RIPAS RAM*

Hi Steven,

On 8/19/24 08:19, Steven Price wrote:
> External email: Use caution opening links or attachments
> 
For ACPI-based kernel boot flow, control never reaches this point because the above
function does not check the PSCI conduit method when the kernel is booted via UEFI.

As a result, the boot process fails when using ACPI. It works fine with DTB based
boot.

> +       if (!rsi_version_matches())
> +               return;

---

## [52] Gavin Shan — 2024-09-09
*Subject: Re: [PATCH v5 07/19] arm64: rsi: Add support for checking whether an
 MMIO is protected*

On 9/6/24 11:55 PM, Steven Price wrote:
> On 06/09/2024 05:32, Gavin Shan wrote:
>> On 8/19/24 11:19 PM, Steven Price wrote:

[...]

>>> diff --git a/arch/arm64/kernel/rsi.c b/arch/arm64/kernel/rsi.c
>>> index e968a5c9929e..381a5b9a5333 100644

The check 'size == 0' could be squeezed to the overflow check if you agree.

     /* size == 0 or overflow */
     if (WARN_ON(base + size) <= base)
         return false;
     :
     
     return (base >= end);


>>         return (base >= end);     /* RSI_RIPAS_IO returned for all
>> granules */

My bad. I didn't check the cover letter in time. With this specific TF-RMM branch,
I'm able to boot the guest with cca/host-v4 and cca/guest-v5. However, there are
messages indicating unhandled system register accesses, as below.

# ./start.sh
   Info: # lkvm run -k Image -m 256 -c 2 --name guest-152
   Info: Removed ghost socket file "/root/.lkvm//guest-152.sock".
[   rmm ] SMC_RMI_REALM_CREATE          882860000 880856000 > RMI_SUCCESS
[   rmm ] SMC_RMI_REC_AUX_COUNT         882860000 > RMI_SUCCESS 10
[   rmm ] SMC_RMI_REC_CREATE            882860000 88bdc5000 88bdc4000 > RMI_SUCCESS
[   rmm ] SMC_RMI_REC_CREATE            882860000 88bdd7000 88bdc4000 > RMI_SUCCESS
[   rmm ] SMC_RMI_REALM_ACTIVATE        882860000 > RMI_SUCCESS
[   rmm ] Unhandled write S2_0_C0_C2_2
[   rmm ] Unhandled write S3_3_C9_C14_0
[   rmm ] SMC_RSI_VERSION               10000 > RSI_SUCCESS 10000 10000
[   rmm ] SMC_RSI_REALM_CONFIG          82b2b000 > RSI_SUCCESS
[   rmm ] SMC_RSI_IPA_STATE_SET         80000000 90000000 1 0 > RSI_SUCCESS 90000000 0
[   rmm ] SMC_RSI_IPA_STATE_GET         1000000 1001000 > RSI_SUCCESS 1001000 0
      :
[    1.835570] DMA: preallocated 128 KiB GFP_KERNEL|GFP_DMA32 pool for atomic allocations
[    1.865993] audit: initializing netlink subsys (disabled)
[    1.891218] audit: type=2000 audit(0.492:1): state=initialized audit_enabled=0 res=1
[    1.899066] thermal_sys: Registered thermal governor 'step_wise'
[    1.920869] thermal_sys: Registered thermal governor 'power_allocator'
[    1.944151] cpuidle: using governor menu
[    1.988588] hw-breakpoint: found 16 breakpoint and 16 watchpoint registers.
[   rmm ] Unhandled write S2_0_C0_C0_5
[   rmm ] Unhandled write S2_0_C0_C0_4
[   rmm ] Unhandled write S2_0_C0_C1_5
[   rmm ] Unhandled write S2_0_C0_C1_4
[   rmm ] Unhandled write S2_0_C0_C2_5
      :
[   rmm ] Unhandled write S2_0_C0_C13_6
[   rmm ] Unhandled write S2_0_C0_C14_7
[   rmm ] Unhandled write S2_0_C0_C14_6
[   rmm ] Unhandled write S2_0_C0_C15_7
[   rmm ] Unhandled write S2_0_C0_C15_6

Thanks,
Gavin

---

## [53] Gavin Shan — 2024-09-09
*Subject: Re: [PATCH v5 19/19] virt: arm-cca-guest: TSM_REPORT support for
 realms*

On 8/19/24 11:19 PM, Steven Price wrote:
> From: Sami Mujawar <sami.mujawar@arm.com>
> 

[...]

> +
> +/**
                         ^^^^^^^^^

Typo. s/decriptor/descriptor as reported by './scripts/checkpatch.pl --codespell'


> + * and schedule calls to retrieve the attestation token on the same CPU
> + * on which the attestation token generation was initialised.

Thanks,
Gavin

---

## [54] Gavin Shan — 2024-09-09
*Subject: Re: [PATCH v5 03/19] arm64: rsi: Add RSI definitions*

On 8/19/24 11:19 PM, Steven Price wrote:
> From: Suzuki K Poulose <suzuki.poulose@arm.com>
> 

With the following minor comments addressed:

Reviewed-by: Gavin Shan <gshan@redht.com>

> diff --git a/arch/arm64/include/asm/rsi_cmds.h b/arch/arm64/include/asm/rsi_cmds.h
> new file mode 100644

The 'RSI_RIPAS_IO' corresponds to 'RIPAS_DEV' defined in tf-rmm/lib/s2tt/include/ripas.h.
Shall we rename it to RSI_RIPAS_DEV so that the name is matched with that defined in
tf-rmm?

---> tf-rmm/lib/s2tt/include/ripas.h

/*
  * The RmmRipas enumeration represents realm IPA state.
  *
  * Map RmmRipas to RmiRipas to simplify code/decode operations.
  */
enum ripas {
         RIPAS_EMPTY = RMI_EMPTY,        /* Unused IPA for Realm */
         RIPAS_RAM = RMI_RAM,            /* IPA used for Code/Data by Realm */
         RIPAS_DESTROYED = RMI_DESTROYED,/* IPA is inaccessible to the Realm */
         RIPAS_DEV                       /* Address where memory of an assigned
                                            Realm device is mapped */
};

> +static inline unsigned long rsi_request_version(unsigned long req,
> +						unsigned long *out_lower,

The type of the return value would be 'long' instead of 'unsigned long' since
'-EINVAL' can be returned.

> +/**
> + * rsi_attestation_token_continue - Continue the operation to retrieve an
               ^^^^^^^^^^^^^
               Status / error

> + * ret1 == Feature register value
> + */
                                          ^^^^^^
                                          8 - 15

> + * ret3 == Measurement value, bytes: 16 - 23
> + * ret4 == Measurement value, bytes: 24 - 31
                                           ^^^^^^
                                           8 - 15

> + * arg5  == Measurement value, bytes: 16 - 23
> + * arg6  == Measurement value, bytes: 24 - 31
                                        ^^^^^^
                                        8 - 15

> + * arg3 == Challenge value, bytes: 16 - 23
> + * arg4 == Challenge value, bytes: 24 - 31

According to the linked specification, the description for the third return value
has been missed here.

ret2 == Whether the host accepted or rejected the request

> +/*
> + * Get RIPAS of a target IPA range.

Thanks,
Gavin

---

## [55] Steven Price — 2024-09-09
*Subject: Re: [PATCH v5 03/19] arm64: rsi: Add RSI definitions*

On 09/09/2024 06:10, Gavin Shan wrote:
> On 8/19/24 11:19 PM, Steven Price wrote:
>> From: Suzuki K Poulose <suzuki.poulose@arm.com>

Thanks for the review!

>> diff --git a/arch/arm64/include/asm/rsi_cmds.h
>> b/arch/arm64/include/asm/rsi_cmds.h

Yes it should be renamed. This was posted based on the v1.0-rel0-rc1
spec and follows the naming there. But shortly after that spec was
released the decision to rename to RIPAS_DEV was made (as it's really
specifying that it's a device not that I/O is happening at an address).
I kept the naming to match the spec, but the next release of the spec
should have the RIPAS_DEV so I'll update to match that.

> ---> tf-rmm/lib/s2tt/include/ripas.h
> 

Good spot! The call site is casting back to long, so it "should work",
but clearly this is the wrong type.

>> +/**
>> + * rsi_attestation_token_continue - Continue the operation to

Ack

>> + * ret1 == Feature register value
>> + */

One mistake and too much copy/pasting :(

>> + * arg3 == Challenge value, bytes: 16 - 23
>> + * arg4 == Challenge value, bytes: 24 - 31

Worse than just a documentation error - I'd completely forgotten to
check this extra return value in rsi_set_addr_range_state(). Thanks for
spotting this!

Steve

>> +/*
>> + * Get RIPAS of a target IPA range.

---

## [56] Steven Price — 2024-09-09
*Subject: Re: [PATCH v5 07/19] arm64: rsi: Add support for checking whether an
 MMIO is protected*

On 09/09/2024 00:53, Gavin Shan wrote:
> On 9/6/24 11:55 PM, Steven Price wrote:
>> On 06/09/2024 05:32, Gavin Shan wrote:

Yes that makes sense, thanks for the suggestion.

>>>         return (base >= end);     /* RSI_RIPAS_IO returned for all
>>> granules */

To some extent unhandled system register accesses are expected. The
kernel will probe for features, and if the RMM doesn't support them it
will be emulating those registers as RAZ/WI. I believe RAZ/WI is an
appropriate emulation, so Linux won't have any trouble here, and I don't
think there's anything wrong with Linux probing these registers.

So the question really is whether the RMM needs to have dummy handlers
to silence the 'warnings'. They are currently output using 'INFO' so
priority - so will only be visible in a 'debug' build (or if the log
level has been explicitly set).

Steve

> # ./start.sh
>   Info: # lkvm run -k Image -m 256 -c 2 --name guest-152

---

## [57] Matias Ezequiel Vara Larsen — 2024-09-09
*Subject: Re: [PATCH v5 12/19] efi: arm64: Map Device with Prot Shared*

On Mon, Aug 19, 2024 at 02:19:17PM +0100, Steven Price wrote:
> From: Suzuki K Poulose <suzuki.poulose@arm.com>
> 
Typo. s/emualted/emulated 

Matias

---

## [58] Shanker Donthineni — 2024-09-09
*Subject: Re: [PATCH v5 05/19] arm64: Detect if in a realm and set RIPAS RAM*

Hi Steven,

On 8/19/24 09:10, Steven Price wrote:
> External email: Use caution opening links or attachments
> 

The error number macros are used in this file, but the header file
'<linux/errno.h>' is not included.


>>> +
>>> +DECLARE_STATIC_KEY_FALSE(rsi_present);

-Shanker

---

## [59] Gavin Shan — 2024-09-10
*Subject: Re: [PATCH v5 04/19] firmware/psci: Add psci_early_test_conduit()*

On 8/19/24 11:19 PM, Steven Price wrote:
> From: Jean-Philippe Brucker <jean-philippe@linaro.org>
> 

Question: Do we need same check for ACPI based system?

> diff --git a/drivers/firmware/psci/psci.c b/drivers/firmware/psci/psci.c
> index 2328ca58bba6..2b308f97ef2c 100644

Nit: The comments needn't span into multiple lines.

> +bool __init psci_early_test_conduit(enum arm_smccc_conduit conduit)
> +{

Nit: Strictly speaking, "psci_node == 0" isn't an error. So the check would be
"if (psci_node < 0)" if I'm correct.

> +	method = of_get_flat_dt_prop(psci_node, "method", &len);
> +	if (!method)

Thanks,
Gavin

---

## [60] Gavin Shan — 2024-09-10
*Subject: Re: [PATCH v5 05/19] arm64: Detect if in a realm and set RIPAS RAM*

On 8/31/24 1:54 AM, Steven Price wrote:
> On 26/08/2024 11:03, Catalin Marinas wrote:
>> On Mon, Aug 19, 2024 at 02:19:10PM +0100, Steven Price wrote:

[...]

>>> +
>>> +void __init arm64_rsi_setup_memory(void)

One potential issue I'm seeing is WARN_ON() followed by BUG_ON(). They're a bit
duplicate. I would suggest to remove the WARN_ON() and print informative messages
in rsi_set_memory_range().

   setup_arch
   arm64_rsi_setup_memory                    // BUG_ON(error)
   rsi_set_memory_range_protected_safe
   rsi_set_memory_range                      // WARN_ON(error)

Thanks,
Gavin

---

## [61] Gavin Shan — 2024-09-10
*Subject: Re: [PATCH v5 06/19] arm64: realm: Query IPA size from the RMM*

On 8/19/24 11:19 PM, Steven Price wrote:
> The top bit of the configured IPA size is used as an attribute to
> control whether the address is protected or shared. Query the

One nit below.

Reviewed-by: Gavin Shan <gshan@redhat.com>

> diff --git a/arch/arm64/include/asm/pgtable-prot.h b/arch/arm64/include/asm/pgtable-prot.h
> index b11cfb9fdd37..5e578274a3b7 100644

Nit: It's probably worthy to warn on errors returned from rsi_get_realm_config(),
It's hard to debug and follow if it fails silently.

Thanks,
Gavin

---

## [62] Gavin Shan — 2024-09-10
*Subject: Re: [PATCH v5 07/19] arm64: rsi: Add support for checking whether an
 MMIO is protected*

On 8/19/24 11:19 PM, Steven Price wrote:
> From: Suzuki K Poulose <suzuki.poulose@arm.com>
> 

I guess it might be better to unify the function names here. The name of
arm64_is_iomem_private() indicates the IO region is private, while the
name of arm64_rsi_is_protected_mmio() indicates the IO region is protected.
I think it would be nice to rename arm64_is_iomem_private() arm64_is_protected_iomem(),
or rename arm64_rsi_is_protected_mmio() to arm64_rsi_is_private_iomem().

Thanks,
Gavin

---

## [63] Gavin Shan — 2024-09-10
*Subject: Re: [PATCH v5 12/19] efi: arm64: Map Device with Prot Shared*

On 8/19/24 11:19 PM, Steven Price wrote:
> From: Suzuki K Poulose <suzuki.poulose@arm.com>
> 

Question: the second parameter (@size) passed to arm64_is_iomem_private() covers the
whole region. In [PATCH v5 10/19] arm64: Override set_fixmap_io, the size has been
truncated to the granule size (4KB). They look inconsistent and I don't understand
the reason.

Thanks,
Gavin

---

## [64] Suzuki K Poulose — 2024-09-10
*Subject: Re: [PATCH v5 12/19] efi: arm64: Map Device with Prot Shared*

On 10/09/2024 05:15, Gavin Shan wrote:
> On 8/19/24 11:19 PM, Steven Price wrote:
>> From: Suzuki K Poulose <suzuki.poulose@arm.com>

Agreed, and the comment in patches 09/19 and 10/19 kind of vaguely 
explains this. For set_fixmap_io, we are trying to map a PAGE_SIZE, 
always. And when we want to check the "Is the range Private ?" the
answer could be different based on the PAGE_SIZE used by the kernel.
This is due to the fact that RMM always tracks the RIPAS for a 4K
granule and not the OS page size. So, if the kernel uses a 64K page
size, the RMM cannot confirm that the region is entirely RIPAS_DEV
if only the 4K granule is indeed marked as RIPAS_DEV. However, given
the same driver works for a 4K page size kernel, we can safely assume
that the driver doesn't access it beyond the 4K range  with FIXMAP.

e.g:

Addr  = 0x100000        +0x2000              0x110000
RIPAS = [ EMPTY | EMPTY | DEV | EMPTY | ...] [EMPTY | ...]

So, if we were to check the RIPAS of 0x102000, we have to restrict the
check to 4K (for the FIXMAP). Elswhere, we get the exact size of the
requested map region and can use that to check the state.

I agree that we should have a comment explaining this in the appropriate
patch.

Kind regards
Suzuki


> 
> Thanks,

---

## [65] Suzuki K Poulose — 2024-09-13
*Subject: Re: [PATCH v5 04/19] firmware/psci: Add psci_early_test_conduit()*

On 26/08/2024 11:03, Catalin Marinas wrote:
> On Mon, Aug 19, 2024 at 02:19:09PM +0100, Steven Price wrote:
>> From: Jean-Philippe Brucker <jean-philippe@linaro.org>

We could delay the RSI init until we have probed the PSCI conduit.
This could be done from setup_arch(), after the psci_{dt,acpi}_init().
This is safe, as the EFI maps are only created later, as an 
early_initcall().

Kind regards
Suzuki

---

## [66] Steven Price — 2024-09-27
*Subject: Re: [PATCH v5 19/19] virt: arm-cca-guest: TSM_REPORT support for
 realms*

On 02/09/2024 04:53, Aneesh Kumar K.V wrote:
> Steven Price <steven.price@arm.com> writes:
> 

This matches the existing sev-guest and tdx-guest directories (and
SEV_GUEST/TDX_GUEST_DRIVER kconfig), although I agree it's not great
naming as it stands.

But I'm also wondering if this will one day expand to include some other
communication with the RMM. For example I know it's been discussed
whether the guest should have involvement with firmware updates or
migration to another host. So there's a reasonable chance we could end
up renaming it back to a general "arm_cca_guest" if it grows more
capabilities in the future.

Steve

---

## [67] Shanker Donthineni — 2024-10-17
*Subject: Re: [PATCH v5 17/19] irqchip/gic-v3-its: Share ITS tables with a
 non-trusted hypervisor*

Hi Steve,

On 8/19/24 08:19, Steven Price wrote:
> External email: Use caution opening links or attachments
> 
...
> +
> +static void *itt_alloc_pool(int node, int size)


Two (2^1) pages are allocated here, but only one page is being added to the pool.
Is this a typo or intentional?

> +               if (!page)
> +                       break;

-Shanker

---
