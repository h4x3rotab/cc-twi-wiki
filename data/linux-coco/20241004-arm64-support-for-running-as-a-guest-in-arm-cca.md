---
title: 'arm64: Support for running as a guest in Arm CCA'
date: 2024-10-04
last_reply: 2024-10-15
message_count: 46
participants: ['Steven Price', 'kernel test robot', 'Gavin Shan', 'Jean-Philippe Brucker', 'Catalin Marinas', 'Suzuki K Poulose']
---

## [1] Steven Price — 2024-10-04

This series adds support for running Linux in a protected VM under the
Arm Confidential Compute Architecture (CCA). This is a trimmed down
series following the feedback from the v5 posting[1]. Thanks for the
feedback!

Individual patches have a change log. But things to highlight:

 * Some patches have been merged already. The first two patches from v4
   were borrowed from pKVM were merged as part of that series. The GIC
   ITS patches[2][3] have been merged via the tip tree.

 * Final RMM v1.0 spec[4] - only minor changes over the previous spec,
   but we've now got a proper release.

 * Probing/initialisation of the RMM is now done later. This means
   there's no need for finding the PSCI conduit and can drop the patch
   for that.

 * The patches for set_fixmap_io() is also gone - we the RMM is detected
   later it's now too late for earlycon. See below for instructions on
   how to use earlycon.

 * Mainline no longer uses PHYS_MASK_SHIFT for manipulating PTEs, so we
   can drop the patch for making that dynamic.

 * There's now some documentation! In particular this clarifies a change
   in the boot requirements - memory must now be RIPAS RAM for a realm
   guest.

This series is based on v6.12-rc1.

Testing
=======

Since a couple of the patches have been merged separately, and there was
also a bug[5] in -rc1 which impacts 9p filesystems, I've provided the
below git tree with everything you need for a CCA guest:

https://gitlab.arm.com/linux-arm/linux-cca cca-guest/v6

Back by popular demand is also a tree with both host and guest changes:

https://gitlab.arm.com/linux-arm/linux-cca cca-full/v5+v6

(I'll post the v5 series of the host changes shortly)

You will also need an up-to-date RMM - the necessary changes have been
merged into the 'main' branch of upstream:

https://git.trustedfirmware.org/TF-RMM/tf-rmm.git main

And you also need an updated kvmtool, there's a branch with the
necessary changes here:

https://git.gitlab.arm.com/linux-arm/kvmtool-cca.git cca/v3

earlycon
--------

If using 'earlycon' on the kernel command line it is now necessary to
pass the address of the serial port *in the unprotected IPA*. This is
because the fixmap changes were dropped (due to the late probing of the
RMM). E.g. for kvmtool you will need:

  earlycon=uart,mmio,0x101000000

This is the main drawback to late probing. One potential improvement
would be an option like "earlycon=realm" to identify that the earlycon
uart is in the unprotected space without having to know the actual IPA.
I've left this out for now as I'm not sure whether there is any actual
interest in this.

[1] https://lore.kernel.org/r/20240819131924.372366-1-steven.price%40arm.com
[2] e36d4165f079 ("irqchip/gic-v3-its: Rely on genpool alignment")
[3] b08e2f42e86b ("irqchip/gic-v3-its: Share ITS tables with a non-trusted hypervisor")
[4] https://developer.arm.com/documentation/den0137/1-0rel0/
[5] https://lore.kernel.org/all/cbaf141ba6c0e2e209717d02746584072844841a.1727722269.git.osandov@fb.com/

Sami Mujawar (1):
  virt: arm-cca-guest: TSM_REPORT support for realms

Steven Price (4):
  arm64: realm: Query IPA size from the RMM
  arm64: Enforce bounce buffers for realm DMA
  arm64: mm: Avoid TLBI when marking pages as valid
  arm64: Document Arm Confidential Compute

Suzuki K Poulose (6):
  arm64: rsi: Add RSI definitions
  arm64: Detect if in a realm and set RIPAS RAM
  arm64: rsi: Add support for checking whether an MMIO is protected
  arm64: rsi: Map unprotected MMIO as decrypted
  efi: arm64: Map Device with Prot Shared
  arm64: Enable memory encrypt for Realms

 Documentation/arch/arm64/arm-cca.rst          |  67 ++++++
 Documentation/arch/arm64/booting.rst          |   3 +
 Documentation/arch/arm64/index.rst            |   1 +
 arch/arm64/Kconfig                            |   3 +
 arch/arm64/include/asm/io.h                   |   8 +
 arch/arm64/include/asm/mem_encrypt.h          |   9 +
 arch/arm64/include/asm/pgtable-prot.h         |   4 +
 arch/arm64/include/asm/pgtable.h              |   5 +
 arch/arm64/include/asm/rsi.h                  |  68 ++++++
 arch/arm64/include/asm/rsi_cmds.h             | 160 +++++++++++++
 arch/arm64/include/asm/rsi_smc.h              | 193 ++++++++++++++++
 arch/arm64/include/asm/set_memory.h           |   3 +
 arch/arm64/kernel/Makefile                    |   3 +-
 arch/arm64/kernel/efi.c                       |  12 +-
 arch/arm64/kernel/rsi.c                       | 141 ++++++++++++
 arch/arm64/kernel/setup.c                     |   3 +
 arch/arm64/mm/init.c                          |  10 +-
 arch/arm64/mm/pageattr.c                      |  98 +++++++-
 drivers/virt/coco/Kconfig                     |   2 +
 drivers/virt/coco/Makefile                    |   1 +
 drivers/virt/coco/arm-cca-guest/Kconfig       |  11 +
 drivers/virt/coco/arm-cca-guest/Makefile      |   2 +
 .../virt/coco/arm-cca-guest/arm-cca-guest.c   | 211 ++++++++++++++++++
 23 files changed, 1010 insertions(+), 8 deletions(-)
 create mode 100644 Documentation/arch/arm64/arm-cca.rst
 create mode 100644 arch/arm64/include/asm/rsi.h
 create mode 100644 arch/arm64/include/asm/rsi_cmds.h
 create mode 100644 arch/arm64/include/asm/rsi_smc.h
 create mode 100644 arch/arm64/kernel/rsi.c
 create mode 100644 drivers/virt/coco/arm-cca-guest/Kconfig
 create mode 100644 drivers/virt/coco/arm-cca-guest/Makefile
 create mode 100644 drivers/virt/coco/arm-cca-guest/arm-cca-guest.c

---

## [2] Steven Price — 2024-10-04
*Subject: [PATCH v6 01/11] arm64: rsi: Add RSI definitions*

From: Suzuki K Poulose <suzuki.poulose@arm.com>

The RMM (Realm Management Monitor) provides functionality that can be
accessed by a realm guest through SMC (Realm Services Interface) calls.

The SMC definitions are based on DEN0137[1] version 1.0-rel0.

[1] https://developer.arm.com/documentation/den0137/1-0rel0/

Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Acked-by: Catalin Marinas <catalin.marinas@arm.com>
Reviewed-by: Gavin Shan <gshan@redht.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v5:
 * Rename RSI_RIPAS_IO to RSI_RIPAS_DEV (to match spec v1.0-rel0).
 * Correctly deal with the 'response' return value from RSI_IPA_STATE_SET.
 * Fix return type of rsi_attestation_token_init().
 * Minor documentation typos.
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
 arch/arm64/include/asm/rsi_cmds.h | 139 +++++++++++++++++++++
 arch/arm64/include/asm/rsi_smc.h  | 193 ++++++++++++++++++++++++++++++
 2 files changed, 332 insertions(+)
 create mode 100644 arch/arm64/include/asm/rsi_cmds.h
 create mode 100644 arch/arm64/include/asm/rsi_smc.h

diff --git a/arch/arm64/include/asm/rsi_cmds.h b/arch/arm64/include/asm/rsi_cmds.h
new file mode 100644
index 000000000000..b661331c9204
--- /dev/null
+++ b/arch/arm64/include/asm/rsi_cmds.h
@@ -0,0 +1,139 @@
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
+	RSI_RIPAS_DEV = 3,
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
+	if (res.a2 != RSI_ACCEPT)
+		return -EPERM;
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
+static inline long
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
index 000000000000..6cb070eca9e9
--- /dev/null
+++ b/arch/arm64/include/asm/rsi_smc.h
@@ -0,0 +1,193 @@
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
+ * ret0 == Status / error
+ * ret1 == Lower implemented interface revision
+ * ret2 == Higher implemented interface revision
+ */
+#define SMC_RSI_ABI_VERSION	SMC_RSI_FID(0x190)
+
+/*
+ * Read feature register.
+ *
+ * arg1 == Feature register index
+ * ret0 == Status / error
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
+ * ret2 == Measurement value, bytes:  8 - 15
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
+ * arg4  == Measurement value, bytes:  8 - 15
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
+ * arg2 == Challenge value, bytes:  8 - 15
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
+ * ret2 == Whether the Host accepted or rejected the request
+ */
+#define SMC_RSI_IPA_STATE_SET			SMC_RSI_FID(0x197)
+
+#define RSI_NO_CHANGE_DESTROYED			UL(0)
+#define RSI_CHANGE_DESTROYED			UL(1)
+
+#define RSI_ACCEPT				UL(0)
+#define RSI_REJECT				UL(1)
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

## [3] Steven Price — 2024-10-04
*Subject: [PATCH v6 02/11] arm64: Detect if in a realm and set RIPAS RAM*

From: Suzuki K Poulose <suzuki.poulose@arm.com>

Detect that the VM is a realm guest by the presence of the RSI
interface. This is done after PSCI has been initialised so that we can
check the SMCCC conduit before making any RSI calls.

If in a realm then all memory needs to be marked as RIPAS RAM initially,
the loader may or may not have done this for us. To be sure iterate over
all RAM and mark it as such. Any failure is fatal as that implies the
RAM regions passed to Linux are incorrect - which would mean failing
later when attempting to access non-existent RAM.

Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Co-developed-by: Steven Price <steven.price@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v5:
 * Replace BUG_ON() with a panic() call that provides a message with the
   memory range that couldn't be set to RIPAS_RAM.
 * Move the call to arm64_rsi_init() later so that it is after PSCI,
   this means we can use arm_smccc_1_1_get_conduit() to check if it is
   safe to make RSI calls.
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
 arch/arm64/include/asm/rsi.h | 66 +++++++++++++++++++++++++++++++
 arch/arm64/kernel/Makefile   |  3 +-
 arch/arm64/kernel/rsi.c      | 75 ++++++++++++++++++++++++++++++++++++
 arch/arm64/kernel/setup.c    |  3 ++
 4 files changed, 146 insertions(+), 1 deletion(-)
 create mode 100644 arch/arm64/include/asm/rsi.h
 create mode 100644 arch/arm64/kernel/rsi.c

diff --git a/arch/arm64/include/asm/rsi.h b/arch/arm64/include/asm/rsi.h
new file mode 100644
index 000000000000..e4c01796c618
--- /dev/null
+++ b/arch/arm64/include/asm/rsi.h
@@ -0,0 +1,66 @@
+/* SPDX-License-Identifier: GPL-2.0-only */
+/*
+ * Copyright (C) 2024 ARM Ltd.
+ */
+
+#ifndef __ASM_RSI_H_
+#define __ASM_RSI_H_
+
+#include <linux/errno.h>
+#include <linux/jump_label.h>
+#include <asm/rsi_cmds.h>
+
+DECLARE_STATIC_KEY_FALSE(rsi_present);
+
+void __init arm64_rsi_init(void);
+
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
+				    RSI_CHANGE_DESTROYED);
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
index 000000000000..9bf757b4b00c
--- /dev/null
+++ b/arch/arm64/kernel/rsi.c
@@ -0,0 +1,75 @@
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
+static void __init arm64_rsi_setup_memory(void)
+{
+	u64 i;
+	phys_addr_t start, end;
+
+	/*
+	 * Iterate over the available memory ranges and convert the state to
+	 * protected memory. We should take extra care to ensure that we DO NOT
+	 * permit any "DESTROYED" pages to be converted to "RAM".
+	 *
+	 * panic() is used because if the attempt to switch the memory to
+	 * protected has failed here, then future accesses to the memory are
+	 * simply going to be reflected as a SEA (Synchronous External Abort)
+	 * which we can't handle.  Bailing out early prevents the guest limping
+	 * on and dying later.
+	 */
+	for_each_mem_range(i, &start, &end) {
+		if (rsi_set_memory_range_protected_safe(start, end))
+			panic("Failed to set memory range to protected: %pa-%pa",
+			      &start, &end);
+	}
+}
+
+void __init arm64_rsi_init(void)
+{
+	if (arm_smccc_1_1_get_conduit() != SMCCC_CONDUIT_SMC)
+		return;
+	if (!rsi_version_matches())
+		return;
+
+	arm64_rsi_setup_memory();
+
+	static_branch_enable(&rsi_present);
+}
+
diff --git a/arch/arm64/kernel/setup.c b/arch/arm64/kernel/setup.c
index b22d28ec8028..b5e1e306fa51 100644
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
@@ -351,6 +352,8 @@ void __init __no_sanitize_address setup_arch(char **cmdline_p)
 	else
 		psci_acpi_init();
 
+	arm64_rsi_init();
+
 	init_bootcpu_ops();
 	smp_init_cpus();
 	smp_build_mpidr_hash();

---

## [4] Steven Price — 2024-10-04
*Subject: [PATCH v6 03/11] arm64: realm: Query IPA size from the RMM*

The top bit of the configured IPA size is used as an attribute to
control whether the address is protected or shared. Query the
configuration from the RMM to assertain which bit this is.

Reviewed-by: Catalin Marinas <catalin.marinas@arm.com>
Reviewed-by: Gavin Shan <gshan@redhat.com>
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
 arch/arm64/include/asm/rsi.h          | 2 +-
 arch/arm64/kernel/rsi.c               | 8 ++++++++
 3 files changed, 13 insertions(+), 1 deletion(-)

diff --git a/arch/arm64/include/asm/pgtable-prot.h b/arch/arm64/include/asm/pgtable-prot.h
index 2a11d0c10760..820a3b06f08c 100644
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
diff --git a/arch/arm64/include/asm/rsi.h b/arch/arm64/include/asm/rsi.h
index e4c01796c618..acba065eb00e 100644
--- a/arch/arm64/include/asm/rsi.h
+++ b/arch/arm64/include/asm/rsi.h
@@ -27,7 +27,7 @@ static inline int rsi_set_memory_range(phys_addr_t start, phys_addr_t end,
 
 	while (start != end) {
 		ret = rsi_set_addr_range_state(start, end, state, flags, &top);
-		if (WARN_ON(ret || top < start || top > end))
+		if (ret || top < start || top > end)
 			return -EINVAL;
 		start = top;
 	}
diff --git a/arch/arm64/kernel/rsi.c b/arch/arm64/kernel/rsi.c
index 9bf757b4b00c..a6495a64d9bb 100644
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
 
@@ -67,6 +72,9 @@ void __init arm64_rsi_init(void)
 		return;
 	if (!rsi_version_matches())
 		return;
+	if (WARN_ON(rsi_get_realm_config(&config)))
+		return;
+	prot_ns_shared = BIT(config.ipa_bits - 1);
 
 	arm64_rsi_setup_memory();

---

## [5] Steven Price — 2024-10-04
*Subject: [PATCH v6 04/11] arm64: rsi: Add support for checking whether an MMIO is protected*

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

Reviewed-by: Catalin Marinas <catalin.marinas@arm.com>
Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
New patch for v5
---
 arch/arm64/include/asm/io.h       |  8 ++++++++
 arch/arm64/include/asm/rsi.h      |  2 ++
 arch/arm64/include/asm/rsi_cmds.h | 21 +++++++++++++++++++++
 arch/arm64/kernel/rsi.c           | 26 ++++++++++++++++++++++++++
 4 files changed, 57 insertions(+)

diff --git a/arch/arm64/include/asm/io.h b/arch/arm64/include/asm/io.h
index 1ada23a6ec19..cce445ff8e3f 100644
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
 
+static inline bool arm64_is_mmio_private(phys_addr_t phys_addr, size_t size)
+{
+	if (unlikely(is_realm_world()))
+		return arm64_is_protected_mmio(phys_addr, size);
+	return false;
+}
+
 #endif	/* __ASM_IO_H */
diff --git a/arch/arm64/include/asm/rsi.h b/arch/arm64/include/asm/rsi.h
index acba065eb00e..42ff93c7b0ba 100644
--- a/arch/arm64/include/asm/rsi.h
+++ b/arch/arm64/include/asm/rsi.h
@@ -14,6 +14,8 @@ DECLARE_STATIC_KEY_FALSE(rsi_present);
 
 void __init arm64_rsi_init(void);
 
+bool arm64_is_protected_mmio(phys_addr_t base, size_t size);
+
 static inline bool is_realm_world(void)
 {
 	return static_branch_unlikely(&rsi_present);
diff --git a/arch/arm64/include/asm/rsi_cmds.h b/arch/arm64/include/asm/rsi_cmds.h
index b661331c9204..fdb47f690307 100644
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
index a6495a64d9bb..d7bba4cee627 100644
--- a/arch/arm64/kernel/rsi.c
+++ b/arch/arm64/kernel/rsi.c
@@ -66,6 +66,32 @@ static void __init arm64_rsi_setup_memory(void)
 	}
 }
 
+bool arm64_is_protected_mmio(phys_addr_t base, size_t size)
+{
+	enum ripas ripas;
+	phys_addr_t end, top;
+
+	/* Overflow ? */
+	if (WARN_ON(base + size <= base))
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
+		if (ripas != RSI_RIPAS_DEV)
+			break;
+		base = top;
+	}
+
+	return base >= end;
+}
+EXPORT_SYMBOL(arm64_is_protected_mmio);
+
 void __init arm64_rsi_init(void)
 {
 	if (arm_smccc_1_1_get_conduit() != SMCCC_CONDUIT_SMC)

---

## [6] Steven Price — 2024-10-04
*Subject: [PATCH v6 05/11] arm64: rsi: Map unprotected MMIO as decrypted*

From: Suzuki K Poulose <suzuki.poulose@arm.com>

Instead of marking every MMIO as shared, check if the given region is
"Protected" and apply the permissions accordingly.

Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
New patch for v5
---
 arch/arm64/kernel/rsi.c | 15 +++++++++++++++
 1 file changed, 15 insertions(+)

diff --git a/arch/arm64/kernel/rsi.c b/arch/arm64/kernel/rsi.c
index d7bba4cee627..f1add76f89ce 100644
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
@@ -92,6 +94,16 @@ bool arm64_is_protected_mmio(phys_addr_t base, size_t size)
 }
 EXPORT_SYMBOL(arm64_is_protected_mmio);
 
+static int realm_ioremap_hook(phys_addr_t phys, size_t size, pgprot_t *prot)
+{
+	if (arm64_is_protected_mmio(phys, size))
+		*prot = pgprot_encrypted(*prot);
+	else
+		*prot = pgprot_decrypted(*prot);
+
+	return 0;
+}
+
 void __init arm64_rsi_init(void)
 {
 	if (arm_smccc_1_1_get_conduit() != SMCCC_CONDUIT_SMC)
@@ -102,6 +114,9 @@ void __init arm64_rsi_init(void)
 		return;
 	prot_ns_shared = BIT(config.ipa_bits - 1);
 
+	if (arm64_ioremap_prot_hook_register(realm_ioremap_hook))
+		return;
+
 	arm64_rsi_setup_memory();
 
 	static_branch_enable(&rsi_present);

---

## [7] Steven Price — 2024-10-04
*Subject: [PATCH v6 06/11] efi: arm64: Map Device with Prot Shared*

From: Suzuki K Poulose <suzuki.poulose@arm.com>

Device mappings need to be emulated by the VMM so must be mapped shared
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
index 712718aed5dd..1cc64053d6b1 100644
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
+		if (arm64_is_mmio_private(md->phys_addr,
+					  md->num_pages << EFI_PAGE_SHIFT))
+			prot = pgprot_encrypted(prot);
+		else
+			prot = pgprot_decrypted(prot);
+		return pgprot_val(prot);
+	}
 
 	if (region_is_misaligned(md)) {
 		static bool __initdata code_is_misaligned;

---

## [8] Steven Price — 2024-10-04
*Subject: [PATCH v6 07/11] arm64: Enforce bounce buffers for realm DMA*

Within a realm guest it's not possible for a device emulated by the VMM
to access arbitrary guest memory. So force the use of bounce buffers to
ensure that the memory the emulated devices are accessing is in memory
which is explicitly shared with the host.

This adds a call to swiotlb_update_mem_attributes() which calls
set_memory_decrypted() to ensure the bounce buffer memory is shared with
the host. For non-realm guests or hosts this is a no-op.

Reviewed-by: Catalin Marinas <catalin.marinas@arm.com>
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
index f1add76f89ce..58408f5add49 100644
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
index 27a32ff15412..d21f67d67cf5 100644
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
@@ -366,8 +367,14 @@ void __init bootmem_init(void)
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
@@ -379,7 +386,8 @@ void __init mem_init(void)
 		swiotlb = true;
 	}
 
-	swiotlb_init(swiotlb, SWIOTLB_VERBOSE);
+	swiotlb_init(swiotlb, flags);
+	swiotlb_update_mem_attributes();
 
 	/* this will put all unused low memory onto the freelists */
 	memblock_free_all();

---

## [9] Steven Price — 2024-10-04
*Subject: [PATCH v6 08/11] arm64: mm: Avoid TLBI when marking pages as valid*

When __change_memory_common() is purely setting the valid bit on a PTE
(e.g. via the set_memory_valid() call) there is no need for a TLBI as
either the entry isn't changing (the valid bit was already set) or the
entry was invalid and so should not have been cached in the TLB.

Reviewed-by: Catalin Marinas <catalin.marinas@arm.com>
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

## [10] Steven Price — 2024-10-04
*Subject: [PATCH v6 09/11] arm64: Enable memory encrypt for Realms*

From: Suzuki K Poulose <suzuki.poulose@arm.com>

Use the memory encryption APIs to trigger a RSI call to request a
transition between protected memory and shared memory (or vice versa)
and updating the kernel's linear map of modified pages to flip the top
bit of the IPA. This requires that block mappings are not used in the
direct map for realm guests.

Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Co-developed-by: Steven Price <steven.price@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
Reviewed-by: Catalin Marinas <catalin.marinas@arm.com>
---
Changes since v5:
 * Added comments and a WARN() in realm_set_memory_{en,de}crypted() to
   explain that memory is leaked if the transition fails. This means the
   callers no longer need to provide their own WARN.
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
 arch/arm64/Kconfig                   |  3 +
 arch/arm64/include/asm/mem_encrypt.h |  9 +++
 arch/arm64/include/asm/pgtable.h     |  5 ++
 arch/arm64/include/asm/set_memory.h  |  3 +
 arch/arm64/kernel/rsi.c              | 16 +++++
 arch/arm64/mm/pageattr.c             | 90 +++++++++++++++++++++++++++-
 6 files changed, 123 insertions(+), 3 deletions(-)

diff --git a/arch/arm64/Kconfig b/arch/arm64/Kconfig
index 3e29b44d2d7b..ccea9c22d6df 100644
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
@@ -44,6 +45,8 @@ config ARM64
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
index c329ea061dc9..7e4bdc8259a2 100644
--- a/arch/arm64/include/asm/pgtable.h
+++ b/arch/arm64/include/asm/pgtable.h
@@ -684,6 +684,11 @@ static inline void set_pud_at(struct mm_struct *mm, unsigned long addr,
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
index 58408f5add49..6f39275b43a7 100644
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
@@ -19,6 +21,17 @@ EXPORT_SYMBOL(prot_ns_shared);
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
@@ -118,6 +131,9 @@ void __init arm64_rsi_init(void)
 	if (arm64_ioremap_prot_hook_register(realm_ioremap_hook))
 		return;
 
+	if (realm_register_memory_enc_ops())
+		return;
+
 	arm64_rsi_setup_memory();
 
 	static_branch_enable(&rsi_present);
diff --git a/arch/arm64/mm/pageattr.c b/arch/arm64/mm/pageattr.c
index 547a9e0b46c2..6ae6ae806454 100644
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
@@ -198,6 +202,86 @@ int set_direct_map_default_noflush(struct page *page)
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
+	int ret = __set_memory_enc_dec(addr, numpages, true);
+
+	/*
+	 * If the request to change state fails, then the only sensible cause
+	 * of action for the caller is to leak the memory
+	 */
+	WARN(ret, "Failed to encrypt memory, %d pages will be leaked",
+	     numpages);
+
+	return ret;
+}
+
+static int realm_set_memory_decrypted(unsigned long addr, int numpages)
+{
+	int ret = __set_memory_enc_dec(addr, numpages, false);
+
+	WARN(ret, "Failed to decrypt memory, %d pages will be leaked",
+	     numpages);
+
+	return ret;
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

## [11] Steven Price — 2024-10-04
*Subject: [PATCH v6 10/11] virt: arm-cca-guest: TSM_REPORT support for realms*

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
index d9ff676bf48d..ff869d883d95 100644
--- a/drivers/virt/coco/Kconfig
+++ b/drivers/virt/coco/Kconfig
@@ -14,3 +14,5 @@ source "drivers/virt/coco/pkvm-guest/Kconfig"
 source "drivers/virt/coco/sev-guest/Kconfig"
 
 source "drivers/virt/coco/tdx-guest/Kconfig"
+
+source "drivers/virt/coco/arm-cca-guest/Kconfig"
diff --git a/drivers/virt/coco/Makefile b/drivers/virt/coco/Makefile
index b69c30c1c720..c3d07cfc087e 100644
--- a/drivers/virt/coco/Makefile
+++ b/drivers/virt/coco/Makefile
@@ -7,3 +7,4 @@ obj-$(CONFIG_EFI_SECRET)	+= efi_secret/
 obj-$(CONFIG_ARM_PKVM_GUEST)	+= pkvm-guest/
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
index 000000000000..e22a565cb425
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
+ * passed in the TSM descriptor. Allocate memory for the attestation token
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

## [12] Steven Price — 2024-10-04
*Subject: [PATCH v6 11/11] arm64: Document Arm Confidential Compute*

Add some documentation on Arm CCA and the requirements for running Linux
as a Realm guest. Also update booting.rst to describe the requirement
for RIPAS RAM.

Signed-off-by: Steven Price <steven.price@arm.com>
---
 Documentation/arch/arm64/arm-cca.rst | 67 ++++++++++++++++++++++++++++
 Documentation/arch/arm64/booting.rst |  3 ++
 Documentation/arch/arm64/index.rst   |  1 +
 3 files changed, 71 insertions(+)
 create mode 100644 Documentation/arch/arm64/arm-cca.rst

diff --git a/Documentation/arch/arm64/arm-cca.rst b/Documentation/arch/arm64/arm-cca.rst
new file mode 100644
index 000000000000..ab7f90e64c2f
--- /dev/null
+++ b/Documentation/arch/arm64/arm-cca.rst
@@ -0,0 +1,67 @@
+.. SPDX-License-Identifier: GPL-2.0
+
+=====================================
+Arm Confidential Compute Architecture
+=====================================
+
+Arm systems that support the Realm Management Extension (RME) contain
+hardware to allow a VM guest to be run in a way which protects the code
+and data of the guest from the hypervisor. It extends the older "two
+world" model (Normal and Secure World) into four worlds: Normal, Secure,
+Root and Realm. Linux can then also be run as a guest to a monitor
+running in the Realm world.
+
+The monitor running in the Realm world is known as the Realm Management
+Monitor (RMM) and implements the Realm Management Monitor
+specification[1]. The monitor acts a bit like a hypervisor (e.g. it runs
+in EL2 and manages the stage 2 page tables etc of the guests running in
+Realm world), however much of the control is handled by a hypervisor
+running in the Normal World. The Normal World hypervisor uses the Realm
+Management Interface (RMI) defined by the RMM specification to request
+the RMM to perform operations (e.g. mapping memory or executing a vCPU).
+
+The RMM defines an environment for guests where the address space (IPA)
+is split into two. The lower half is protected - any memory that is
+mapped in this half cannot be seen by the Normal World and the RMM
+restricts what operations the Normal World can perform on this memory
+(e.g. the Normal World cannot replace pages in this region without the
+guest's cooperation). The upper half is shared, the Normal World is free
+to make changes to the pages in this region, and is able to emulate MMIO
+devices in this region too.
+
+A guest running in a Realm may also communicate with the RMM to request
+changes in its environment or to perform attestation about its
+environment. In particular it may request that areas of the protected
+address space are transitioned between 'RAM' and 'EMPTY' (in either
+direction). This allows a Realm guest to give up memory to be returned
+to the Normal World, or to request new memory from the Normal World.
+Without an explicit request from the Realm guest the RMM will otherwise
+prevent the Normal World from making these changes.
+
+Linux as a Realm Guest
+----------------------
+
+To run Linux as a guest within a Realm, the following must be provided
+either by the VMM or by a `boot loader` run in the Realm before Linux:
+
+ * All protected RAM described to Linux (by DT or ACPI) must be marked
+   RIPAS RAM before handing over the Linux.
+
+ * MMIO devices must be either unprotected (e.g. emulated by the Normal
+   World) or marked RIPAS DEV.
+
+ * MMIO devices emulated by the Normal World and used very early in boot
+   (specifically earlycon) must be specified in the upper half of IPA.
+   For earlycon this can be done by specifying the address on the
+   command line, e.g.: ``earlycon=uart,mmio,0x101000000``
+
+ * Linux will use bounce buffers for communicating with unprotected
+   devices. It will transition some protected memory to RIPAS EMPTY and
+   expect to be able to access unprotected pages at the same IPA address
+   but with the highest valid IPA bit set. The expectation is that the
+   VMM will remove the physical pages from the protected mapping and
+   provide those pages as unprotected pages.
+
+References
+----------
+[1] https://developer.arm.com/documentation/den0137/
diff --git a/Documentation/arch/arm64/booting.rst b/Documentation/arch/arm64/booting.rst
index b57776a68f15..30164fb24a24 100644
--- a/Documentation/arch/arm64/booting.rst
+++ b/Documentation/arch/arm64/booting.rst
@@ -41,6 +41,9 @@ to automatically locate and size all RAM, or it may use knowledge of
 the RAM in the machine, or any other method the boot loader designer
 sees fit.)
 
+For Arm Confidential Compute Realms this includes ensuring that all
+protected RAM has a Realm IPA state (RIPAS) of "RAM".
+
 
 2. Setup the device tree
 -------------------------
diff --git a/Documentation/arch/arm64/index.rst b/Documentation/arch/arm64/index.rst
index 78544de0a8a9..12c243c3af20 100644
--- a/Documentation/arch/arm64/index.rst
+++ b/Documentation/arch/arm64/index.rst
@@ -10,6 +10,7 @@ ARM64 Architecture
     acpi_object_usage
     amu
     arm-acpi
+    arm-cca
     asymmetric-32bit
     booting
     cpu-feature-registers

---

## [13] Steven Price — 2024-10-04
*Subject: Re: [PATCH v6 02/11] arm64: Detect if in a realm and set RIPAS RAM*

On 04/10/2024 15:42, Steven Price wrote:
> From: Suzuki K Poulose <suzuki.poulose@arm.com>
> 

And it appears I didn't review this closely enough before posting ;)
Suzuki pointed out to me that this patch description doesn't make sense
given my comments in the cover letter about the VMM or bootloader having
to set everything RIPAS RAM.

I should have reworded this commit message to something like:

"""
Detect that the VM is a realm guest by the presence of the RSI
interface. This is done after PSCI has been initialised so that we can
check the SMCCC conduit before making any RSI calls.

If in a realm then iterate over all memory ensuring that it is marked as
RIPAS RAM. The loader is required to do this for us, however if some
memory is missed this will cause the guest to receive a hard to debug
external abort at some random point in the future. So for a
belt-and-braces approach set all memory to RIPAS RAM. Any failure here
implies that the RAM regions passed to Linux are incorrect so panic()
promptly to make the situation clear.
"""

Steve

> Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
> Co-developed-by: Steven Price <steven.price@arm.com>

---

## [14] kernel test robot — 2024-10-05
*Subject: Re: [PATCH v6 10/11] virt: arm-cca-guest: TSM_REPORT support for
 realms*

Hi Steven,

kernel test robot noticed the following build warnings:

[auto build test WARNING on arm64/for-next/core]
[also build test WARNING on linus/master v6.12-rc1 next-20241004]
[cannot apply to efi/next]
[If your patch is applied to the wrong git tree, kindly drop us a note.
And when submitting patch, we suggest to use '--base' as documented in
https://git-scm.com/docs/git-format-patch#_base_tree_information]

url:    https://github.com/intel-lab-lkp/linux/commits/Steven-Price/arm64-rsi-Add-RSI-definitions/20241004-225034
base:   https://git.kernel.org/pub/scm/linux/kernel/git/arm64/linux.git for-next/core
patch link:    https://lore.kernel.org/r/20241004144307.66199-11-steven.price%40arm.com
patch subject: [PATCH v6 10/11] virt: arm-cca-guest: TSM_REPORT support for realms
config: arm64-randconfig-004-20241005 (https://download.01.org/0day-ci/archive/20241005/202410052337.YQFmvTFu-lkp@intel.com/config)
compiler: aarch64-linux-gcc (GCC) 14.1.0
reproduce (this is a W=1 build): (https://download.01.org/0day-ci/archive/20241005/202410052337.YQFmvTFu-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202410052337.YQFmvTFu-lkp@intel.com/

All warnings (new ones prefixed by >>):

>> drivers/virt/coco/arm-cca-guest/arm-cca-guest.c:27: warning: Excess struct member 'len' description in 'arm_cca_token_info'


vim +27 drivers/virt/coco/arm-cca-guest/arm-cca-guest.c

    15	
    16	/**
    17	 * struct arm_cca_token_info - a descriptor for the token buffer.
    18	 * @granule:	PA of the page to which the token will be written
    19	 * @offset:	Offset within granule to start of buffer in bytes
    20	 * @len:	Number of bytes of token data that was retrieved
    21	 * @result:	result of rsi_attestation_token_continue operation
    22	 */
    23	struct arm_cca_token_info {
    24		phys_addr_t     granule;
    25		unsigned long   offset;
    26		int             result;
  > 27	};
    28

---

## [15] Gavin Shan — 2024-10-08
*Subject: Re: [PATCH v6 01/11] arm64: rsi: Add RSI definitions*

On 10/5/24 12:42 AM, Steven Price wrote:
> From: Suzuki K Poulose <suzuki.poulose@arm.com>
> 

[...]

> +
> +static inline unsigned long rsi_set_addr_range_state(phys_addr_t start,

Similar to rsi_attestation_token_init(), the return value type needs to be 'long'
since '-EPERM' can be returned from the function.

> +/**
> + * rsi_attestation_token_init - Initialise the operation to retrieve an

The return value type of this function needs to be 'unsigned long' even it's
converted to 'int' in arm_cca_attestation_continue(). In this way, the wrapper
functions has consistent return value type, which is 'unsigned long' or 'long'.

Thanks,
Gavin

---

## [16] Gavin Shan — 2024-10-08
*Subject: Re: [PATCH v6 02/11] arm64: Detect if in a realm and set RIPAS RAM*

On 10/5/24 12:42 AM, Steven Price wrote:
> From: Suzuki K Poulose <suzuki.poulose@arm.com>
> 

Two nitpicks below.

Reviewed-by: Gavin Shan <gshan@redhat.com>

> diff --git a/arch/arm64/include/asm/rsi.h b/arch/arm64/include/asm/rsi.h
> new file mode 100644

The WARN_ON() is redundant when the caller is arm64_rsi_setup_memory(), where
system panic is invoked on any errors. So we perhaps need to drop the WARN_ON().

[...]

> +
> +static void __init arm64_rsi_setup_memory(void)

{} is needed since the panic statement spans multiple lines.

Thanks,
Gavin

---

## [17] Gavin Shan — 2024-10-08
*Subject: Re: [PATCH v6 03/11] arm64: realm: Query IPA size from the RMM*

On 10/5/24 12:42 AM, Steven Price wrote:
> The top bit of the configured IPA size is used as an attribute to
> control whether the address is protected or shared. Query the

[...]

> diff --git a/arch/arm64/include/asm/rsi.h b/arch/arm64/include/asm/rsi.h
> index e4c01796c618..acba065eb00e 100644

I think the changes belong to PATCH[02/11] :)

Thanks,
Gavin

---

## [18] Gavin Shan — 2024-10-08
*Subject: Re: [PATCH v6 04/11] arm64: rsi: Add support for checking whether an
 MMIO is protected*

On 10/5/24 12:42 AM, Steven Price wrote:
> From: Suzuki K Poulose <suzuki.poulose@arm.com>
> 

With the following nitpick addressed:

Reviewed-by: Gavin Shan <gshan@redhat.com>

> diff --git a/arch/arm64/include/asm/io.h b/arch/arm64/include/asm/io.h
> index 1ada23a6ec19..cce445ff8e3f 100644

The function names (arm64_is_{mmio_private, protected_mmio} are indicators to the
MMIO region's state or property. arm64_is_mmio_private() indicates the MMIO region
is 'private MMIO' while arm64_is_protected_mmio() indicates the MMIO region is
'protected MMIO'. They are equivalent and it may be worthy to unify the function
names (indicators) as below.

   option#1                         option#2
   --------                         --------
   arm64_is_private_mmio            arm64_is_protected_mmio
   __arm64_is_private_mmio          __arm64_is_protected_mmio


>   #endif	/* __ASM_IO_H */
> diff --git a/arch/arm64/include/asm/rsi.h b/arch/arm64/include/asm/rsi.h

The function may be worthy to be renamed to __arm64_is_private_mmio, as explained
as above.

>   void __init arm64_rsi_init(void)
>   {

Thanks,
Gavin

---

## [19] Gavin Shan — 2024-10-08
*Subject: Re: [PATCH v6 05/11] arm64: rsi: Map unprotected MMIO as decrypted*

On 10/5/24 12:43 AM, Steven Price wrote:
> From: Suzuki K Poulose <suzuki.poulose@arm.com>
> 

With the following potential issue addressed:

Reviewed-by: Gavin Shan <gshan@redhat.com>

> diff --git a/arch/arm64/kernel/rsi.c b/arch/arm64/kernel/rsi.c
> index d7bba4cee627..f1add76f89ce 100644

We probably need arm64_is_mmio_private() here, meaning arm64_is_protected_mmio() isn't
sufficient to avoid invoking SMCCC call SMC_RSI_IPA_STATE_GET in a regular guest where
realm capability isn't present.

>   void __init arm64_rsi_init(void)
>   {

Thanks,
Gavin

---

## [20] Gavin Shan — 2024-10-08
*Subject: Re: [PATCH v6 06/11] efi: arm64: Map Device with Prot Shared*

On 10/5/24 12:43 AM, Steven Price wrote:
> From: Suzuki K Poulose <suzuki.poulose@arm.com>
> 

Reviewed-by: Gavin Shan <gshan@redhat.com>

---

## [21] Gavin Shan — 2024-10-08
*Subject: Re: [PATCH v6 07/11] arm64: Enforce bounce buffers for realm DMA*

On 10/5/24 12:43 AM, Steven Price wrote:
> Within a realm guest it's not possible for a device emulated by the VMM
> to access arbitrary guest memory. So force the use of bounce buffers to

Reviewed-by: Gavin Shan <gshan@redhat.com>

---

## [22] Gavin Shan — 2024-10-08
*Subject: Re: [PATCH v6 08/11] arm64: mm: Avoid TLBI when marking pages as
 valid*

On 10/5/24 12:43 AM, Steven Price wrote:
> When __change_memory_common() is purely setting the valid bit on a PTE
> (e.g. via the set_memory_valid() call) there is no need for a TLBI as

Reviewed-by: Gavin Shan <gshan@redhat.com>

---

## [23] Gavin Shan — 2024-10-08
*Subject: Re: [PATCH v6 09/11] arm64: Enable memory encrypt for Realms*

On 10/5/24 12:43 AM, Steven Price wrote:
> From: Suzuki K Poulose <suzuki.poulose@arm.com>
> 
Reviewed-by: Gavin Shan <gshan@redhat.com>

---

## [24] Gavin Shan — 2024-10-08
*Subject: Re: [PATCH v6 10/11] virt: arm-cca-guest: TSM_REPORT support for
 realms*

On 10/5/24 12:43 AM, Steven Price wrote:
> From: Sami Mujawar <sami.mujawar@arm.com>
> 
                       ^^^^^^^^

s/the page/the granule. They are same thing when we have 4KB page size,
but there are conceptually different if I'm correct.

> + * @offset:	Offset within granule to start of buffer in bytes
> + * @len:	Number of bytes of token data that was retrieved

This check seems unnecessary and can be dropped.

> +
> +	info = (struct arm_cca_token_info *)param;

As I suggested in another reply, the return value type of rsi_attestation_token_continue()
needs to be 'unsigned long'. In that case, the type of struct arm_cca_token_info::result
needs to be adjusted either.

> +/**
> + * arm_cca_report_new - Generate a new attestation token.

This check seems unnecessary and can be dropped.

> +	if (desc->inblob_len < 32 || desc->inblob_len > 64)
> +		return -EINVAL;

It seems that put_cpu() is called early, meaning the CPU can go away before
the subsequent call to arm_cca_attestation_continue() ?

> +	if (max_size <= 0)
> +		return -EINVAL;

This initial assignment can be moved to where the variable is declared.

> +	/* Loop until the token is ready or there is an error. */
                                                              ^^

Maybe it's the personal preference, I personally prefer to avoid the ending
character '.' for the single line of comment.

> +	do {
> +		/* Retrieve one RSI_GRANULE_SIZE data per loop iteration. */

It may be clearer to use 'info.result' here. Besides, unnecessary () exists
in the check.

                 } while (info.result == RSI_INCOMPLETE &&
                          info.offset < RSI_GRANULE_SIZE);

Apart from that, we needn't to copy the token over when info.result isn't
RSI_SUCCESS nor RSI_INCOMPLETE.

> +
> +		/*

As above, it may be clearer to use 'info.result' in the check.

         } while (info.result == RSI_INCOMPLETE);

> +	if (ret != RSI_SUCCESS) {
> +		ret = -ENXIO;

It's probably a bit helpful to print the errno returned from tsm_register().

   pr_err("Error %d registering with TSM\n", ret);

The only errno that can be returned from tsm_register() is -EBUSY. So there
is no way for arm_cca_guest_init() to return -EINVAL. The comments need
correction by dropping the description relevant to -EINVAL.

> +/**
> + * arm_cca_guest_exit - unregister with the Trusted Security Module (TSM)

The ending character '.' for the module's description may not be needed and can be
dropped.

Thanks,
Gavin

---

## [25] Gavin Shan — 2024-10-08
*Subject: Re: [PATCH v6 11/11] arm64: Document Arm Confidential Compute*

On 10/5/24 12:43 AM, Steven Price wrote:
> Add some documentation on Arm CCA and the requirements for running Linux
> as a Realm guest. Also update booting.rst to describe the requirement

Reviewed-by: Gavin Shan <gshan@redhat.com>

---

## [26] Jean-Philippe Brucker — 2024-10-08
*Subject: Re: [PATCH v6 11/11] arm64: Document Arm Confidential Compute*

On Fri, Oct 04, 2024 at 03:43:06PM +0100, Steven Price wrote:
> Add some documentation on Arm CCA and the requirements for running Linux
> as a Realm guest. Also update booting.rst to describe the requirement

We could mention that this interface is "RSI", so readers know what to
look for next

> +
> +Linux as a Realm Guest

"handing control over to Linux", or something like that?

> +
> + * MMIO devices must be either unprotected (e.g. emulated by the Normal

This is going to be needed frequently, so maybe we should explain in a
little more detail how we come up with this value: "e.g. with an IPA size
of 33 and the base address of the emulated UART at 0x1000000,
``earlycon=uart,mmio,0x101000000``"

(Because the example IPA size is rather unintuitive and specific to the
kvmtool memory map)

Thanks,
Jean

> +
> + * Linux will use bounce buffers for communicating with unprotected

---

## [27] Catalin Marinas — 2024-10-11
*Subject: Re: [PATCH v6 02/11] arm64: Detect if in a realm and set RIPAS RAM*

On Fri, Oct 04, 2024 at 04:05:17PM +0100, Steven Price wrote:
> I should have reworded this commit message to something like:
> 

With the updated commit description, the patch looks fine to me.

Reviewed-by: Catalin Marinas <catalin.marinas@arm.com>

---

## [28] Catalin Marinas — 2024-10-11
*Subject: Re: [PATCH v6 05/11] arm64: rsi: Map unprotected MMIO as decrypted*

On Tue, Oct 08, 2024 at 10:31:06AM +1000, Gavin Shan wrote:
> On 10/5/24 12:43 AM, Steven Price wrote:
> > diff --git a/arch/arm64/kernel/rsi.c b/arch/arm64/kernel/rsi.c

I think we get away with this since the hook won't be registered in a
normal guest (done from arm64_rsi_init()). So the additional check in
arm64_is_mmio_private() is unnecessary.

---

## [29] Catalin Marinas — 2024-10-11
*Subject: Re: [PATCH v6 05/11] arm64: rsi: Map unprotected MMIO as decrypted*

On Fri, Oct 04, 2024 at 03:43:00PM +0100, Steven Price wrote:
> From: Suzuki K Poulose <suzuki.poulose@arm.com>
> 

Reviewed-by: Catalin Marinas <catalin.marinas@arm.com>

---

## [30] Catalin Marinas — 2024-10-11
*Subject: Re: [PATCH v6 06/11] efi: arm64: Map Device with Prot Shared*

On Fri, Oct 04, 2024 at 03:43:01PM +0100, Steven Price wrote:
> From: Suzuki K Poulose <suzuki.poulose@arm.com>
> 

Reviewed-by: Catalin Marinas <catalin.marinas@arm.com>

---

## [31] Steven Price — 2024-10-11
*Subject: Re: [PATCH v6 01/11] arm64: rsi: Add RSI definitions*

On 08/10/2024 00:08, Gavin Shan wrote:
> On 10/5/24 12:42 AM, Steven Price wrote:
>> From: Suzuki K Poulose <suzuki.poulose@arm.com>

Good spot.

>> +/**
>> + * rsi_attestation_token_init - Initialise the operation to retrieve an

Ack, seems reasonable.

Thanks,
Steve

---

## [32] Steven Price — 2024-10-11
*Subject: Re: [PATCH v6 02/11] arm64: Detect if in a realm and set RIPAS RAM*

On 08/10/2024 00:31, Gavin Shan wrote:
> On 10/5/24 12:42 AM, Steven Price wrote:
>> From: Suzuki K Poulose <suzuki.poulose@arm.com>

Actually this is error when I was preparing the series - the WARN_ON is
then dropped in the next patch. Thanks for pointing it out!

> [...]
> 

Ack.

Thanks,
Steve

---

## [33] Steven Price — 2024-10-11
*Subject: Re: [PATCH v6 04/11] arm64: rsi: Add support for checking whether an
 MMIO is protected*

On 08/10/2024 01:24, Gavin Shan wrote:
> On 10/5/24 12:42 AM, Steven Price wrote:
>> From: Suzuki K Poulose <suzuki.poulose@arm.com>

Very valid point, I think I prefer option #2 here - "protected" is the
architectural term in CCA.

Thanks,
Steve

>>   #endif    /* __ASM_IO_H */
>> diff --git a/arch/arm64/include/asm/rsi.h b/arch/arm64/include/asm/rsi.h

---

## [34] Steven Price — 2024-10-11
*Subject: Re: [PATCH v6 10/11] virt: arm-cca-guest: TSM_REPORT support for
 realms*

On 08/10/2024 05:12, Gavin Shan wrote:
> On 10/5/24 12:43 AM, Steven Price wrote:
>> From: Sami Mujawar <sami.mujawar@arm.com>

Indeed they are different, the granule is always 4KB, the host (and
guest) page size could be bigger (although that's not yet supported).

Here 'granule' does indeed point to a (host) page (because it's returned
from alloc_pages_exact()), but that's just a confusing detail.

I'll update as you suggest.

>> + * @offset:    Offset within granule to start of buffer in bytes
>> + * @len:    Number of bytes of token data that was retrieved

Ack

>> +
>> +    info = (struct arm_cca_token_info *)param;

Ack

>> +/**
>> + * arm_cca_report_new - Generate a new attestation token.

Ack

>> +    if (desc->inblob_len < 32 || desc->inblob_len > 64)
>> +        return -EINVAL;

Indeed, good spot. I'll move it to the end of the function and update
the error paths below.

>> +    if (max_size <= 0)
>> +        return -EINVAL;

Ack

>> +    /* Loop until the token is ready or there is an error. */
>                                                              ^^

I agree, my preference is the same. I'll update this.

>> +    do {
>> +        /* Retrieve one RSI_GRANULE_SIZE data per loop iteration. */

Sure

> Apart from that, we needn't to copy the token over when info.result isn't
> RSI_SUCCESS nor RSI_INCOMPLETE.

I'll move the error case up to avoid the copy.

>> +
>> +        /*

Ack

>> +    if (ret != RSI_SUCCESS) {
>> +        ret = -ENXIO;

Ack

>> +/**
>> + * arm_cca_guest_exit - unregister with the Trusted Security Module

Ack.

Thanks for the review!

Steve

---

## [35] Steven Price — 2024-10-11
*Subject: Re: [PATCH v6 11/11] arm64: Document Arm Confidential Compute*

On 08/10/2024 12:05, Jean-Philippe Brucker wrote:
> On Fri, Oct 04, 2024 at 03:43:06PM +0100, Steven Price wrote:
>> Add some documentation on Arm CCA and the requirements for running Linux

Good idea.

>> +
>> +Linux as a Realm Guest

Indeed that actually makes grammatical sense! ;)

>> +
>> + * MMIO devices must be either unprotected (e.g. emulated by the Normal

Agreed.

Thanks,
Steve

> Thanks,
> Jean

---

## [36] Suzuki K Poulose — 2024-10-11
*Subject: Re: [PATCH v6 10/11] virt: arm-cca-guest: TSM_REPORT support for
 realms*

On 11/10/2024 15:14, Steven Price wrote:
> On 08/10/2024 05:12, Gavin Shan wrote:
>> On 10/5/24 12:43 AM, Steven Price wrote:

Actually this was on purpose, not to block the CPU hotplug. The
attestation must be completed on the same CPU.

We can detect the failure from "smp_call" further down and make sure
we can safely complete the operation or restart it.



Suzuki

> 
>>> +    if (max_size <= 0)

---

## [37] Gavin Shan — 2024-10-12
*Subject: Re: [PATCH v6 05/11] arm64: rsi: Map unprotected MMIO as decrypted*

On 10/11/24 11:19 PM, Catalin Marinas wrote:
> On Tue, Oct 08, 2024 at 10:31:06AM +1000, Gavin Shan wrote:
>> On 10/5/24 12:43 AM, Steven Price wrote:

Indeed. I missed the point that the hook won't be registered for a normal
guest. So we're good and safe.

Thanks,
Gavin

---

## [38] Gavin Shan — 2024-10-12
*Subject: Re: [PATCH v6 10/11] virt: arm-cca-guest: TSM_REPORT support for
 realms*

On 10/12/24 2:22 AM, Suzuki K Poulose wrote:
> On 11/10/2024 15:14, Steven Price wrote:
>> On 08/10/2024 05:12, Gavin Shan wrote:

[...]

>>>> +/**
>>>> + * arm_cca_report_new - Generate a new attestation token.

Yes, It's fine to call put_cpu() early since we're tolerant to error introduced
by CPU unplug. It's a bit confused that rsi_attestation_token_init() is called
on the local CPU while arm_cca_attestation_continue() is called on same CPU
with help of smp_call_function_single(). Does it make sense to unify so that
both will be invoked with the help of smp_call_function_single() ?

     int cpu = smp_processor_id();

     /*
      * The calling and target CPU can be different after the calling process
      * is migrated to another different CPU. It's guaranteed the attestatation
      * always happen on the target CPU with smp_call_function_single().
      */
     ret = smp_call_function_single(cpu, rsi_attestation_token_init_wrapper,
                                    (void *)&info, true);
     if (ret) {
         ...
     }

     
Thanks,
Gavin

---

## [39] Suzuki K Poulose — 2024-10-14
*Subject: Re: [PATCH v6 10/11] virt: arm-cca-guest: TSM_REPORT support for
 realms*

On 12/10/2024 07:06, Gavin Shan wrote:
> On 10/12/24 2:22 AM, Suzuki K Poulose wrote:
>> On 11/10/2024 15:14, Steven Price wrote:

Well, we want to allocate sufficient size buffer (size returned from
token_init())  outside an atomic context (thus not in smp_call_function()).

May be we could make this "allocation" restriction in a comment to
make it clear, why we do it this way.

Suzuki




>      if (ret) {
>          ...

---

## [40] Steven Price — 2024-10-14
*Subject: Re: [PATCH v6 10/11] virt: arm-cca-guest: TSM_REPORT support for
 realms*

On 14/10/2024 09:56, Suzuki K Poulose wrote:
> On 12/10/2024 07:06, Gavin Shan wrote:
>> On 10/12/24 2:22 AM, Suzuki K Poulose wrote:

So if I've followed this correctly the get_cpu() route doesn't work
because of the need to allocate outblob. So using
smp_call_function_single() for all calls seems to be the best approach,
along with a comment explaining what's going on. So how about:

	/*
	 * The attestation token 'init' and 'continue' calls must be
	 * performed on the same CPU. smp_call_function_single() is used
	 * instead of simply calling get_cpu() because of the need to
	 * allocate outblob based on the returned value from the 'init'
	 * call and that cannot be done in an atomic context.
	 */
	cpu = smp_processor_id();

	info.challenge = desc->inblob;
	info.challenge_size = desc->inblob_len;

	ret = smp_call_function_single(cpu, arm_cca_attestation_init,
				       &info, true);
	if (ret)
		return ret;
	max_size = info.result;

(with appropriate updates to the 'info' struct and a new
arm_cca_attestation_init() wrapper for rsi_attestation_token_init()).

Steve

---

## [41] Suzuki K Poulose — 2024-10-14
*Subject: Re: [PATCH v6 10/11] virt: arm-cca-guest: TSM_REPORT support for
 realms*

On 14/10/2024 15:41, Steven Price wrote:
> On 14/10/2024 09:56, Suzuki K Poulose wrote:
>> On 12/10/2024 07:06, Gavin Shan wrote:

That sounds good to me.

Suzuki

---

## [42] Gavin Shan — 2024-10-15
*Subject: Re: [PATCH v6 10/11] virt: arm-cca-guest: TSM_REPORT support for
 realms*

On 10/15/24 12:46 AM, Suzuki K Poulose wrote:
> On 14/10/2024 15:41, Steven Price wrote:
>> On 14/10/2024 09:56, Suzuki K Poulose wrote:

+1, it looks good to me as well.

Thanks,
Gavin

---

## [43] Gavin Shan — 2024-10-15
*Subject: Re: [PATCH v6 03/11] arm64: realm: Query IPA size from the RMM*

On 10/5/24 12:42 AM, Steven Price wrote:
> The top bit of the configured IPA size is used as an attribute to
> control whether the address is protected or shared. Query the

[...]

> diff --git a/arch/arm64/kernel/rsi.c b/arch/arm64/kernel/rsi.c
> index 9bf757b4b00c..a6495a64d9bb 100644

Nit: I think this variable is file-scoped since it has a generic name.
In this case, 'static' is needed to match with the scope.

> +unsigned long prot_ns_shared;
> +EXPORT_SYMBOL(prot_ns_shared);

Thanks,
Gavin

---

## [44] Steven Price — 2024-10-15
*Subject: Re: [PATCH v6 03/11] arm64: realm: Query IPA size from the RMM*

On 15/10/2024 04:55, Gavin Shan wrote:
> On 10/5/24 12:42 AM, Steven Price wrote:
>> The top bit of the configured IPA size is used as an attribute to

Good spot - it should definitely be static.

Thanks,
Steve

>> +unsigned long prot_ns_shared;
>> +EXPORT_SYMBOL(prot_ns_shared);

---

## [45] Suzuki K Poulose — 2024-10-15
*Subject: Re: [PATCH v6 08/11] arm64: mm: Avoid TLBI when marking pages as
 valid*

On 04/10/2024 15:43, Steven Price wrote:
> When __change_memory_common() is purely setting the valid bit on a PTE
> (e.g. via the set_memory_valid() call) there is no need for a TLBI as

Reviewed-by: Suzuki K Poulose <suzuki.poulose@arm.com>


> ---
> v4: New patch

---

## [46] Suzuki K Poulose — 2024-10-15
*Subject: Re: [PATCH v6 11/11] arm64: Document Arm Confidential Compute*

On 11/10/2024 15:14, Steven Price wrote:
> On 08/10/2024 12:05, Jean-Philippe Brucker wrote:
>> On Fri, Oct 04, 2024 at 03:43:06PM +0100, Steven Price wrote:

With the above addressed:

Reviewed-by: Suzuki K Poulose <suzuki.poulose@arm.com>

---
