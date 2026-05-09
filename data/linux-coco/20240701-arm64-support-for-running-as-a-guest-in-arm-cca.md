---
title: 'arm64: Support for running as a guest in Arm CCA'
date: 2024-07-01
last_reply: 2024-08-16
message_count: 50
participants: ['Steven Price', 'Gavin Shan', 'Will Deacon', 'Suzuki K Poulose', 'Matias Ezequiel Vara Larsen', 'Shanker Donthineni']
---

## [1] Steven Price — 2024-07-01

This series adds support for running Linux in a protected VM under the
Arm Confidential Compute Architecture (CCA). This has been updated
following the feedback from the v3 posting[1]. Thanks for the feedback!
Individual patches have a change log. But things to highlight:

 * a new patch ("firmware/psci: Add psci_early_test_conduit()") to
   prevent SMC calls being made on systems which don't support them -
   i.e. systems without EL2/EL3 - thanks Jean-Philippe!

 * two patches dropped (overriding set_fixmap_io). Instead
   FIXMAP_PAGE_IO is modified to include PROT_NS_SHARED. When support
   for assigning hardware devices to a realm guest is added this will
   need to be brought back in some form. But for now it's just adding
   complixity and confusion for no gain.

 * a new patch ("arm64: mm: Avoid TLBI when marking pages as valid")
   which avoids doing an extra TLBI when doing the break-before-make.
   Note that this changes the behaviour in other cases when making
   memory valid. This should be safe (and saves a TLBI for those cases),
   but it's a separate patch in case of regressions.

 * GIC ITT allocation now uses a custom genpool-based allocator. I
   expect this will be replaced with a generic way of allocating
   decrypted memory (see [4]), but for now this gets things working
   without wasting too much memory.

The ABI to the RMM from a realm (the RSI) is based on the final RMM v1.0
(EAC 5) specification[2]. Future RMM specifications will be backwards
compatible so a guest using the v1.0 specification (i.e. this series)
will be able to run on future versions of the RMM without modification.

This series is based on v6.10-rc1. It is also available as a git
repository:

https://gitlab.arm.com/linux-arm/linux-cca cca-guest/v4

This series (the guest side) should be in a good state so please review
with the intention that this could be merged soon. The host side will
require more iteration so the versioning of the series will diverge -
so for now continue to use v3 for the host support.

Introduction (unchanged from v2 posting)
============
A more general introduction to Arm CCA is available on the Arm
website[3], and links to the other components involved are available in
the overall cover letter.

Arm Confidential Compute Architecture adds two new 'worlds' to the
architecture: Root and Realm. A new software component known as the RMM
(Realm Management Monitor) runs in Realm EL2 and is trusted by both the
Normal World and VMs running within Realms. This enables mutual
distrust between the Realm VMs and the Normal World.

Virtual machines running within a Realm can decide on a (4k)
page-by-page granularity whether to share a page with the (Normal World)
host or to keep it private (protected). This protection is provided by
the hardware and attempts to access a page which isn't shared by the
Normal World will trigger a Granule Protection Fault.

Realm VMs can communicate with the RMM via another SMC interface known
as RSI (Realm Services Interface). This series adds wrappers for the
full set of RSI commands and uses them to manage the Realm IPA State
(RIPAS) and to discover the configuration of the realm.

The VM running within the Realm needs to ensure that memory that is
going to use is marked as 'RIPAS_RAM' (i.e. protected memory accessible
only to the guest). This could be provided by the VMM (and subject to
measurement to ensure it is setup correctly) or the VM can set it
itself.  This series includes a patch which will iterate over all
described RAM and set the RIPAS. This is a relatively cheap operation,
and doesn't require memory donation from the host. Instead, memory can
be dynamically provided by the host on fault. An alternative would be to
update booting.rst and state this as a requirement, but this would
reduce the flexibility of the VMM to manage the available memory to the
guest (as the initial RIPAS state is part of the guest's measurement).

Within the Realm the most-significant active bit of the IPA is used to
select whether the access is to protected memory or to memory shared
with the host. This series treats this bit as if it is attribute bit in
the page tables and will modify it when sharing/unsharing memory with
the host.

This top bit usage also necessitates that the IPA width is made more
dynamic in the guest. The VMM will choose a width (and therefore which
bit controls the shared flag) and the guest must be able to identify
this bit to mask it out when necessary. PHYS_MASK_SHIFT/PHYS_MASK are
therefore made dynamic.

To allow virtio to communicate with the host the shared buffers must be
placed in memory which has this top IPA bit set. This is achieved by
implementing the set_memory_{encrypted,decrypted} APIs for arm64 and
forcing the use of bounce buffers. For now all device access is
considered to required the memory to be shared, at this stage there is
no support for real devices to be assigned to a realm guest - obviously
if device assignment is added this will have to change.

Finally the GIC is (largely) emulated by the (untrusted) host. The RMM
provides some management (including register save/restore) but the
ITS buffers must be placed into shared memory for the host to emulate.
There is likely to be future work to harden the GIC driver against a
malicious host (along with any other drivers used within a Realm guest).

[1] https://lore.kernel.org/lkml/20240605093006.145492-1-steven.price%40arm.com
[2] https://developer.arm.com/documentation/den0137/1-0eac5/
[3] https://www.arm.com/architecture/security-features/arm-confidential-compute-architecture
[4] https://lore.kernel.org/lkml/ZmNJdSxSz-sYpVgI%40arm.com

Jean-Philippe Brucker (1):
  firmware/psci: Add psci_early_test_conduit()

Sami Mujawar (2):
  arm64: rsi: Interfaces to query attestation token
  virt: arm-cca-guest: TSM_REPORT support for realms

Steven Price (7):
  arm64: realm: Query IPA size from the RMM
  arm64: Mark all I/O as non-secure shared
  arm64: Make the PHYS_MASK_SHIFT dynamic
  arm64: Enforce bounce buffers for realm DMA
  arm64: mm: Avoid TLBI when marking pages as valid
  irqchip/gic-v3-its: Share ITS tables with a non-trusted hypervisor
  irqchip/gic-v3-its: Rely on genpool alignment

Suzuki K Poulose (5):
  arm64: rsi: Add RSI definitions
  arm64: Detect if in a realm and set RIPAS RAM
  arm64: Enable memory encrypt for Realms
  arm64: Force device mappings to be non-secure shared
  efi: arm64: Map Device with Prot Shared

 arch/arm64/Kconfig                            |   3 +
 arch/arm64/include/asm/fixmap.h               |   2 +-
 arch/arm64/include/asm/io.h                   |   8 +-
 arch/arm64/include/asm/mem_encrypt.h          |  17 ++
 arch/arm64/include/asm/pgtable-hwdef.h        |   6 -
 arch/arm64/include/asm/pgtable-prot.h         |   3 +
 arch/arm64/include/asm/pgtable.h              |  13 +-
 arch/arm64/include/asm/rsi.h                  |  64 ++++++
 arch/arm64/include/asm/rsi_cmds.h             | 134 +++++++++++
 arch/arm64/include/asm/rsi_smc.h              | 142 ++++++++++++
 arch/arm64/include/asm/set_memory.h           |   3 +
 arch/arm64/kernel/Makefile                    |   3 +-
 arch/arm64/kernel/efi.c                       |   2 +-
 arch/arm64/kernel/rsi.c                       | 104 +++++++++
 arch/arm64/kernel/setup.c                     |   8 +
 arch/arm64/mm/init.c                          |  10 +-
 arch/arm64/mm/pageattr.c                      |  76 ++++++-
 drivers/firmware/psci/psci.c                  |  25 +++
 drivers/irqchip/irq-gic-v3-its.c              | 142 +++++++++---
 drivers/virt/coco/Kconfig                     |   2 +
 drivers/virt/coco/Makefile                    |   1 +
 drivers/virt/coco/arm-cca-guest/Kconfig       |  11 +
 drivers/virt/coco/arm-cca-guest/Makefile      |   2 +
 .../virt/coco/arm-cca-guest/arm-cca-guest.c   | 211 ++++++++++++++++++
 include/linux/psci.h                          |   5 +
 25 files changed, 953 insertions(+), 44 deletions(-)
 create mode 100644 arch/arm64/include/asm/mem_encrypt.h
 create mode 100644 arch/arm64/include/asm/rsi.h
 create mode 100644 arch/arm64/include/asm/rsi_cmds.h
 create mode 100644 arch/arm64/include/asm/rsi_smc.h
 create mode 100644 arch/arm64/kernel/rsi.c
 create mode 100644 drivers/virt/coco/arm-cca-guest/Kconfig
 create mode 100644 drivers/virt/coco/arm-cca-guest/Makefile
 create mode 100644 drivers/virt/coco/arm-cca-guest/arm-cca-guest.c

---

## [2] Steven Price — 2024-07-01
*Subject: [PATCH v4 01/15] arm64: rsi: Add RSI definitions*

From: Suzuki K Poulose <suzuki.poulose@arm.com>

The RMM (Realm Management Monitor) provides functionality that can be
accessed by a realm guest through SMC (Realm Services Interface) calls.

The SMC definitions are based on DEN0137[1] version A-eac5.

[1] https://developer.arm.com/documentation/den0137/latest

Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v3:
 * Drop invoke_rsi_fn_smc_with_res() function and call arm_smccc_smc()
   directly instead.
 * Rename header guard in rsi_smc.h to be consistent.
Changes since v2:
 * Rename rsi_get_version() to rsi_request_version()
 * Fix size/alignment of struct realm_config
---
 arch/arm64/include/asm/rsi_cmds.h |  38 ++++++++
 arch/arm64/include/asm/rsi_smc.h  | 142 ++++++++++++++++++++++++++++++
 2 files changed, 180 insertions(+)
 create mode 100644 arch/arm64/include/asm/rsi_cmds.h
 create mode 100644 arch/arm64/include/asm/rsi_smc.h

diff --git a/arch/arm64/include/asm/rsi_cmds.h b/arch/arm64/include/asm/rsi_cmds.h
new file mode 100644
index 000000000000..89e907f3af0c
--- /dev/null
+++ b/arch/arm64/include/asm/rsi_cmds.h
@@ -0,0 +1,38 @@
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
+#endif
diff --git a/arch/arm64/include/asm/rsi_smc.h b/arch/arm64/include/asm/rsi_smc.h
new file mode 100644
index 000000000000..b3b3aff88f71
--- /dev/null
+++ b/arch/arm64/include/asm/rsi_smc.h
@@ -0,0 +1,142 @@
+/* SPDX-License-Identifier: GPL-2.0-only */
+/*
+ * Copyright (C) 2023 ARM Ltd.
+ */
+
+#ifndef __ASM_RSI_SMC_H_
+#define __ASM_RSI_SMC_H_
+
+/*
+ * This file describes the Realm Services Interface (RSI) Application Binary
+ * Interface (ABI) for SMC calls made from within the Realm to the RMM and
+ * serviced by the RMM.
+ */
+
+#define SMC_RSI_CALL_BASE		0xC4000000
+
+/*
+ * The major version number of the RSI implementation.  Increase this whenever
+ * the binary format or semantics of the SMC calls change.
+ */
+#define RSI_ABI_VERSION_MAJOR		1
+
+/*
+ * The minor version number of the RSI implementation.  Increase this when
+ * a bug is fixed, or a feature is added without breaking binary compatibility.
+ */
+#define RSI_ABI_VERSION_MINOR		0
+
+#define RSI_ABI_VERSION			((RSI_ABI_VERSION_MAJOR << 16) | \
+					 RSI_ABI_VERSION_MINOR)
+
+#define RSI_ABI_VERSION_GET_MAJOR(_version) ((_version) >> 16)
+#define RSI_ABI_VERSION_GET_MINOR(_version) ((_version) & 0xFFFF)
+
+#define RSI_SUCCESS			0
+#define RSI_ERROR_INPUT			1
+#define RSI_ERROR_STATE			2
+#define RSI_INCOMPLETE			3
+
+#define SMC_RSI_FID(_x)			(SMC_RSI_CALL_BASE + (_x))
+
+#define SMC_RSI_ABI_VERSION			SMC_RSI_FID(0x190)
+
+/*
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
+ * arg1 == The IPA of token buffer
+ * arg2 == Offset within the granule of the token buffer
+ * arg3 == Size of the granule buffer
+ * ret0 == Status / error
+ * ret1 == Length of token bytes copied to the granule buffer
+ */
+#define SMC_RSI_ATTESTATION_TOKEN_CONTINUE	SMC_RSI_FID(0x195)
+
+/*
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
+#ifndef __ASSEMBLY__
+
+struct realm_config {
+	union {
+		struct {
+			unsigned long ipa_bits; /* Width of IPA in bits */
+			unsigned long hash_algo; /* Hash algorithm */
+		};
+		u8 pad[0x1000];
+	};
+} __aligned(0x1000);
+
+#endif /* __ASSEMBLY__ */
+
+/*
+ * arg1 == struct realm_config addr
+ * ret0 == Status / error
+ */
+#define SMC_RSI_REALM_CONFIG			SMC_RSI_FID(0x196)
+
+/*
+ * arg1 == Base IPA address of target region
+ * arg2 == Top of the region
+ * arg3 == RIPAS value
+ * arg4 == flags
+ * ret0 == Status / error
+ * ret1 == Top of modified IPA range
+ */
+#define SMC_RSI_IPA_STATE_SET			SMC_RSI_FID(0x197)
+
+#define RSI_NO_CHANGE_DESTROYED			0
+#define RSI_CHANGE_DESTROYED			1
+
+/*
+ * arg1 == IPA of target page
+ * ret0 == Status / error
+ * ret1 == RIPAS value
+ */
+#define SMC_RSI_IPA_STATE_GET			SMC_RSI_FID(0x198)
+
+/*
+ * arg1 == IPA of host call structure
+ * ret0 == Status / error
+ */
+#define SMC_RSI_HOST_CALL			SMC_RSI_FID(0x199)
+
+#endif /* __ASM_RSI_SMC_H_ */

---

## [3] Steven Price — 2024-07-01
*Subject: [PATCH v4 02/15] firmware/psci: Add psci_early_test_conduit()*

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
index d9629ff87861..a40dcaf17822 100644
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
@@ -767,6 +768,30 @@ int __init psci_dt_init(void)
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

## [4] Steven Price — 2024-07-01
*Subject: [PATCH v4 03/15] arm64: Detect if in a realm and set RIPAS RAM*

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
 arch/arm64/include/asm/rsi.h      | 64 +++++++++++++++++++++++++
 arch/arm64/include/asm/rsi_cmds.h | 22 +++++++++
 arch/arm64/kernel/Makefile        |  3 +-
 arch/arm64/kernel/rsi.c           | 77 +++++++++++++++++++++++++++++++
 arch/arm64/kernel/setup.c         |  8 ++++
 5 files changed, 173 insertions(+), 1 deletion(-)
 create mode 100644 arch/arm64/include/asm/rsi.h
 create mode 100644 arch/arm64/kernel/rsi.c

diff --git a/arch/arm64/include/asm/rsi.h b/arch/arm64/include/asm/rsi.h
new file mode 100644
index 000000000000..29fdc194d27b
--- /dev/null
+++ b/arch/arm64/include/asm/rsi.h
@@ -0,0 +1,64 @@
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
+	return rsi_set_memory_range(start, end, RSI_RIPAS_EMPTY, 0);
+}
+#endif
diff --git a/arch/arm64/include/asm/rsi_cmds.h b/arch/arm64/include/asm/rsi_cmds.h
index 89e907f3af0c..acb557dd4b88 100644
--- a/arch/arm64/include/asm/rsi_cmds.h
+++ b/arch/arm64/include/asm/rsi_cmds.h
@@ -10,6 +10,11 @@
 
 #include <asm/rsi_smc.h>
 
+enum ripas {
+	RSI_RIPAS_EMPTY,
+	RSI_RIPAS_RAM,
+};
+
 static inline unsigned long rsi_request_version(unsigned long req,
 						unsigned long *out_lower,
 						unsigned long *out_higher)
@@ -35,4 +40,21 @@ static inline unsigned long rsi_get_realm_config(struct realm_config *cfg)
 	return res.a0;
 }
 
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
 #endif
diff --git a/arch/arm64/kernel/Makefile b/arch/arm64/kernel/Makefile
index 763824963ed1..a483b916ed11 100644
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
index 000000000000..f01bff9dab04
--- /dev/null
+++ b/arch/arm64/kernel/rsi.c
@@ -0,0 +1,77 @@
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
+		pr_err("RME: RMM doesn't support RSI version %u.%u. Supported range: %lu.%lu-%lu.%lu\n",
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
+	 * simply going to be reflected as a fault which we can't handle.
+	 * Bailing out early prevents the guest limping on and dieing later.
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

## [5] Steven Price — 2024-07-01
*Subject: [PATCH v4 04/15] arm64: realm: Query IPA size from the RMM*

The top bit of the configured IPA size is used as an attribute to
control whether the address is protected or shared. Query the
configuration from the RMM to assertain which bit this is.

Co-developed-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v2:
 * Drop unneeded extra brackets from PROT_NS_SHARED.
 * Drop the explicit alignment from 'config' as struct realm_config now
   specifies the alignment.
---
 arch/arm64/include/asm/pgtable-prot.h | 3 +++
 arch/arm64/kernel/rsi.c               | 8 ++++++++
 2 files changed, 11 insertions(+)

diff --git a/arch/arm64/include/asm/pgtable-prot.h b/arch/arm64/include/asm/pgtable-prot.h
index b11cfb9fdd37..6c29f3b32eba 100644
--- a/arch/arm64/include/asm/pgtable-prot.h
+++ b/arch/arm64/include/asm/pgtable-prot.h
@@ -70,6 +70,9 @@
 #include <asm/pgtable-types.h>
 
 extern bool arm64_use_ng_mappings;
+extern unsigned long prot_ns_shared;
+
+#define PROT_NS_SHARED		(prot_ns_shared)
 
 #define PTE_MAYBE_NG		(arm64_use_ng_mappings ? PTE_NG : 0)
 #define PMD_MAYBE_NG		(arm64_use_ng_mappings ? PMD_SECT_NG : 0)
diff --git a/arch/arm64/kernel/rsi.c b/arch/arm64/kernel/rsi.c
index f01bff9dab04..231c1a3ecdeb 100644
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
 
@@ -71,6 +76,9 @@ void __init arm64_rsi_init(void)
 		return;
 	if (!rsi_version_matches())
 		return;
+	if (rsi_get_realm_config(&config))
+		return;
+	prot_ns_shared = BIT(config.ipa_bits - 1);
 
 	static_branch_enable(&rsi_present);
 }

---

## [6] Steven Price — 2024-07-01
*Subject: [PATCH v4 05/15] arm64: Mark all I/O as non-secure shared*

All I/O is by default considered non-secure for realms. As such
mark them as shared with the host.

Co-developed-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v3:
 * Add PROT_NS_SHARED to FIXMAP_PAGE_IO rather than overriding
   set_fixmap_io() with a custom function.
 * Modify ioreamp_cache() to specify PROT_NS_SHARED too.
---
 arch/arm64/include/asm/fixmap.h | 2 +-
 arch/arm64/include/asm/io.h     | 8 ++++----
 2 files changed, 5 insertions(+), 5 deletions(-)

diff --git a/arch/arm64/include/asm/fixmap.h b/arch/arm64/include/asm/fixmap.h
index 87e307804b99..f2c5e653562e 100644
--- a/arch/arm64/include/asm/fixmap.h
+++ b/arch/arm64/include/asm/fixmap.h
@@ -98,7 +98,7 @@ enum fixed_addresses {
 #define FIXADDR_TOT_SIZE	(__end_of_fixed_addresses << PAGE_SHIFT)
 #define FIXADDR_TOT_START	(FIXADDR_TOP - FIXADDR_TOT_SIZE)
 
-#define FIXMAP_PAGE_IO     __pgprot(PROT_DEVICE_nGnRE)
+#define FIXMAP_PAGE_IO     __pgprot(PROT_DEVICE_nGnRE | PROT_NS_SHARED)
 
 void __init early_fixmap_init(void);
 
diff --git a/arch/arm64/include/asm/io.h b/arch/arm64/include/asm/io.h
index 4ff0ae3f6d66..07fc1801c6ad 100644
--- a/arch/arm64/include/asm/io.h
+++ b/arch/arm64/include/asm/io.h
@@ -277,12 +277,12 @@ static inline void __const_iowrite64_copy(void __iomem *to, const void *from,
 
 #define ioremap_prot ioremap_prot
 
-#define _PAGE_IOREMAP PROT_DEVICE_nGnRE
+#define _PAGE_IOREMAP (PROT_DEVICE_nGnRE | PROT_NS_SHARED)
 
 #define ioremap_wc(addr, size)	\
-	ioremap_prot((addr), (size), PROT_NORMAL_NC)
+	ioremap_prot((addr), (size), (PROT_NORMAL_NC | PROT_NS_SHARED))
 #define ioremap_np(addr, size)	\
-	ioremap_prot((addr), (size), PROT_DEVICE_nGnRnE)
+	ioremap_prot((addr), (size), (PROT_DEVICE_nGnRnE | PROT_NS_SHARED))
 
 /*
  * io{read,write}{16,32,64}be() macros
@@ -303,7 +303,7 @@ static inline void __iomem *ioremap_cache(phys_addr_t addr, size_t size)
 	if (pfn_is_map_memory(__phys_to_pfn(addr)))
 		return (void __iomem *)__phys_to_virt(addr);
 
-	return ioremap_prot(addr, size, PROT_NORMAL);
+	return ioremap_prot(addr, size, PROT_NORMAL | PROT_NS_SHARED);
 }
 
 /*

---

## [7] Steven Price — 2024-07-01
*Subject: [PATCH v4 06/15] arm64: Make the PHYS_MASK_SHIFT dynamic*

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
index 9943ff0af4c9..2e3af0693bd8 100644
--- a/arch/arm64/include/asm/pgtable-hwdef.h
+++ b/arch/arm64/include/asm/pgtable-hwdef.h
@@ -203,12 +203,6 @@
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
index f8efbc128446..11d614d83317 100644
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
index 231c1a3ecdeb..7ac5fc4a27d0 100644
--- a/arch/arm64/kernel/rsi.c
+++ b/arch/arm64/kernel/rsi.c
@@ -13,6 +13,8 @@ struct realm_config config;
 unsigned long prot_ns_shared;
 EXPORT_SYMBOL(prot_ns_shared);
 
+unsigned int phys_mask_shift = CONFIG_ARM64_PA_BITS;
+
 DEFINE_STATIC_KEY_FALSE_RO(rsi_present);
 EXPORT_SYMBOL(rsi_present);
 
@@ -80,6 +82,9 @@ void __init arm64_rsi_init(void)
 		return;
 	prot_ns_shared = BIT(config.ipa_bits - 1);
 
+	if (config.ipa_bits - 1 < phys_mask_shift)
+		phys_mask_shift = config.ipa_bits - 1;
+
 	static_branch_enable(&rsi_present);
 }

---

## [8] Steven Price — 2024-07-01
*Subject: [PATCH v4 07/15] arm64: Enforce bounce buffers for realm DMA*

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
 arch/arm64/kernel/rsi.c |  2 ++
 arch/arm64/mm/init.c    | 10 +++++++++-
 2 files changed, 11 insertions(+), 1 deletion(-)

diff --git a/arch/arm64/kernel/rsi.c b/arch/arm64/kernel/rsi.c
index 7ac5fc4a27d0..918db258cd4a 100644
--- a/arch/arm64/kernel/rsi.c
+++ b/arch/arm64/kernel/rsi.c
@@ -6,6 +6,8 @@
 #include <linux/jump_label.h>
 #include <linux/memblock.h>
 #include <linux/psci.h>
+#include <linux/swiotlb.h>
+
 #include <asm/rsi.h>
 
 struct realm_config config;
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

## [9] Steven Price — 2024-07-01
*Subject: [PATCH v4 08/15] arm64: mm: Avoid TLBI when marking pages as valid*

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

## [10] Steven Price — 2024-07-01
*Subject: [PATCH v4 09/15] arm64: Enable memory encrypt for Realms*

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
 arch/arm64/include/asm/mem_encrypt.h | 17 +++++++
 arch/arm64/include/asm/pgtable.h     |  5 ++
 arch/arm64/include/asm/set_memory.h  |  3 ++
 arch/arm64/kernel/rsi.c              | 12 +++++
 arch/arm64/mm/pageattr.c             | 68 ++++++++++++++++++++++++++--
 6 files changed, 105 insertions(+), 3 deletions(-)
 create mode 100644 arch/arm64/include/asm/mem_encrypt.h

diff --git a/arch/arm64/Kconfig b/arch/arm64/Kconfig
index 5d91259ee7b5..0f1480caeeec 100644
--- a/arch/arm64/Kconfig
+++ b/arch/arm64/Kconfig
@@ -20,6 +20,7 @@ config ARM64
 	select ARCH_ENABLE_SPLIT_PMD_PTLOCK if PGTABLE_LEVELS > 2
 	select ARCH_ENABLE_THP_MIGRATION if TRANSPARENT_HUGEPAGE
 	select ARCH_HAS_CACHE_LINE_SIZE
+	select ARCH_HAS_CC_PLATFORM
 	select ARCH_HAS_CURRENT_STACK_POINTER
 	select ARCH_HAS_DEBUG_VIRTUAL
 	select ARCH_HAS_DEBUG_VM_PGTABLE
@@ -41,6 +42,8 @@ config ARM64
 	select ARCH_HAS_SETUP_DMA_OPS
 	select ARCH_HAS_SET_DIRECT_MAP
 	select ARCH_HAS_SET_MEMORY
+	select ARCH_HAS_MEM_ENCRYPT
+	select ARCH_HAS_FORCE_DMA_UNENCRYPTED
 	select ARCH_STACKWALK
 	select ARCH_HAS_STRICT_KERNEL_RWX
 	select ARCH_HAS_STRICT_MODULE_RWX
diff --git a/arch/arm64/include/asm/mem_encrypt.h b/arch/arm64/include/asm/mem_encrypt.h
new file mode 100644
index 000000000000..e47265cd180a
--- /dev/null
+++ b/arch/arm64/include/asm/mem_encrypt.h
@@ -0,0 +1,17 @@
+/* SPDX-License-Identifier: GPL-2.0 */
+/*
+ * Copyright (C) 2023 ARM Ltd.
+ */
+
+#ifndef __ASM_MEM_ENCRYPT_H
+#define __ASM_MEM_ENCRYPT_H
+
+#include <asm/rsi.h>
+
+/* All DMA must be to non-secure memory for now */
+static inline bool force_dma_unencrypted(struct device *dev)
+{
+	return is_realm_world();
+}
+
+#endif
diff --git a/arch/arm64/include/asm/pgtable.h b/arch/arm64/include/asm/pgtable.h
index 11d614d83317..f5d5f416d47d 100644
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
index 0f740b781187..3b6619c04677 100644
--- a/arch/arm64/include/asm/set_memory.h
+++ b/arch/arm64/include/asm/set_memory.h
@@ -14,4 +14,7 @@ int set_direct_map_invalid_noflush(struct page *page);
 int set_direct_map_default_noflush(struct page *page);
 bool kernel_page_present(struct page *page);
 
+int set_memory_encrypted(unsigned long addr, int numpages);
+int set_memory_decrypted(unsigned long addr, int numpages);
+
 #endif /* _ASM_ARM64_SET_MEMORY_H */
diff --git a/arch/arm64/kernel/rsi.c b/arch/arm64/kernel/rsi.c
index 918db258cd4a..ef6415a1a86c 100644
--- a/arch/arm64/kernel/rsi.c
+++ b/arch/arm64/kernel/rsi.c
@@ -7,6 +7,7 @@
 #include <linux/memblock.h>
 #include <linux/psci.h>
 #include <linux/swiotlb.h>
+#include <linux/cc_platform.h>
 
 #include <asm/rsi.h>
 
@@ -20,6 +21,17 @@ unsigned int phys_mask_shift = CONFIG_ARM64_PA_BITS;
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
diff --git a/arch/arm64/mm/pageattr.c b/arch/arm64/mm/pageattr.c
index 547a9e0b46c2..458124d5454a 100644
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
@@ -198,6 +202,64 @@ int set_direct_map_default_noflush(struct page *page)
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
+	/*
+	 * Break the mapping before we make any changes to avoid stale TLB
+	 * entries or Synchronous External Aborts caused by RIPAS_EMPTY
+	 */
+	ret = __change_memory_common(addr, PAGE_SIZE * numpages,
+				     __pgprot(0),
+				     __pgprot(PTE_VALID));
+
+	if (ret)
+		return ret;
+
+	if (encrypt) {
+		clear_prot = PROT_NS_SHARED;
+		ret = rsi_set_memory_range_protected(start, end);
+	} else {
+		set_prot = PROT_NS_SHARED;
+		ret = rsi_set_memory_range_shared(start, end);
+	}
+
+	if (ret)
+		return ret;
+
+	set_prot |= PTE_VALID;
+
+	return __change_memory_common(addr, PAGE_SIZE * numpages,
+				      __pgprot(set_prot),
+				      __pgprot(clear_prot));
+}
+
+int set_memory_encrypted(unsigned long addr, int numpages)
+{
+	return __set_memory_enc_dec(addr, numpages, true);
+}
+EXPORT_SYMBOL_GPL(set_memory_encrypted);
+
+int set_memory_decrypted(unsigned long addr, int numpages)
+{
+	return __set_memory_enc_dec(addr, numpages, false);
+}
+EXPORT_SYMBOL_GPL(set_memory_decrypted);
+
 #ifdef CONFIG_DEBUG_PAGEALLOC
 void __kernel_map_pages(struct page *page, int numpages, int enable)
 {

---

## [11] Steven Price — 2024-07-01
*Subject: [PATCH v4 10/15] arm64: Force device mappings to be non-secure shared*

From: Suzuki K Poulose <suzuki.poulose@arm.com>

Device mappings (currently) need to be emulated by the VMM so must be
mapped shared with the host.

Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes from v3:
 * Make use of pgprot_decrypted() in the definition of pgprot_device()
---
 arch/arm64/include/asm/pgtable.h | 3 ++-
 1 file changed, 2 insertions(+), 1 deletion(-)

diff --git a/arch/arm64/include/asm/pgtable.h b/arch/arm64/include/asm/pgtable.h
index f5d5f416d47d..a625738ed855 100644
--- a/arch/arm64/include/asm/pgtable.h
+++ b/arch/arm64/include/asm/pgtable.h
@@ -648,8 +648,9 @@ static inline void set_pud_at(struct mm_struct *mm, unsigned long addr,
 	__pgprot_modify(prot, PTE_ATTRINDX_MASK, PTE_ATTRINDX(MT_DEVICE_nGnRnE) | PTE_PXN | PTE_UXN)
 #define pgprot_writecombine(prot) \
 	__pgprot_modify(prot, PTE_ATTRINDX_MASK, PTE_ATTRINDX(MT_NORMAL_NC) | PTE_PXN | PTE_UXN)
-#define pgprot_device(prot) \
+#define __pgprot_device(prot) \
 	__pgprot_modify(prot, PTE_ATTRINDX_MASK, PTE_ATTRINDX(MT_DEVICE_nGnRE) | PTE_PXN | PTE_UXN)
+#define pgprot_device(prot) __pgprot_device(pgprot_decrypted(prot))
 #define pgprot_tagged(prot) \
 	__pgprot_modify(prot, PTE_ATTRINDX_MASK, PTE_ATTRINDX(MT_NORMAL_TAGGED))
 #define pgprot_mhp	pgprot_tagged

---

## [12] Steven Price — 2024-07-01
*Subject: [PATCH v4 11/15] efi: arm64: Map Device with Prot Shared*

From: Suzuki K Poulose <suzuki.poulose@arm.com>

Device mappings need to be emualted by the VMM so must be mapped shared
with the host.

Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
 arch/arm64/kernel/efi.c | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)

diff --git a/arch/arm64/kernel/efi.c b/arch/arm64/kernel/efi.c
index 4a92096db34e..ae1ccc8852a4 100644
--- a/arch/arm64/kernel/efi.c
+++ b/arch/arm64/kernel/efi.c
@@ -34,7 +34,7 @@ static __init pteval_t create_mapping_protection(efi_memory_desc_t *md)
 	u32 type = md->type;
 
 	if (type == EFI_MEMORY_MAPPED_IO)
-		return PROT_DEVICE_nGnRE;
+		return PROT_NS_SHARED | PROT_DEVICE_nGnRE;
 
 	if (region_is_misaligned(md)) {
 		static bool __initdata code_is_misaligned;

---

## [13] Steven Price — 2024-07-01
*Subject: [PATCH v4 12/15] irqchip/gic-v3-its: Share ITS tables with a non-trusted hypervisor*

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
index 40ebf1726393..7d12556bc498 100644
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
 
@@ -163,6 +166,7 @@ struct its_device {
 	struct its_node		*its;
 	struct event_lpi_map	event_map;
 	void			*itt;
+	u32			itt_sz;
 	u32			nr_ites;
 	u32			device_id;
 	bool			shared;
@@ -198,6 +202,81 @@ static DEFINE_IDA(its_vpeid_ida);
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
@@ -2212,7 +2291,8 @@ static struct page *its_allocate_prop_table(gfp_t gfp_flags)
 {
 	struct page *prop_page;
 
-	prop_page = alloc_pages(gfp_flags, get_order(LPI_PROPBASE_SZ));
+	prop_page = its_alloc_pages(gfp_flags,
+				    get_order(LPI_PROPBASE_SZ));
 	if (!prop_page)
 		return NULL;
 
@@ -2223,8 +2303,8 @@ static struct page *its_allocate_prop_table(gfp_t gfp_flags)
 
 static void its_free_prop_table(struct page *prop_page)
 {
-	free_pages((unsigned long)page_address(prop_page),
-		   get_order(LPI_PROPBASE_SZ));
+	its_free_pages(page_address(prop_page),
+		       get_order(LPI_PROPBASE_SZ));
 }
 
 static bool gic_check_reserved_range(phys_addr_t addr, unsigned long size)
@@ -2346,7 +2426,8 @@ static int its_setup_baser(struct its_node *its, struct its_baser *baser,
 		order = get_order(GITS_BASER_PAGES_MAX * psz);
 	}
 
-	page = alloc_pages_node(its->numa_node, GFP_KERNEL | __GFP_ZERO, order);
+	page = its_alloc_pages_node(its->numa_node,
+				    GFP_KERNEL | __GFP_ZERO, order);
 	if (!page)
 		return -ENOMEM;
 
@@ -2359,7 +2440,7 @@ static int its_setup_baser(struct its_node *its, struct its_baser *baser,
 		/* 52bit PA is supported only when PageSize=64K */
 		if (psz != SZ_64K) {
 			pr_err("ITS: no 52bit PA support when psz=%d\n", psz);
-			free_pages((unsigned long)base, order);
+			its_free_pages(base, order);
 			return -ENXIO;
 		}
 
@@ -2415,7 +2496,7 @@ static int its_setup_baser(struct its_node *its, struct its_baser *baser,
 		pr_err("ITS@%pa: %s doesn't stick: %llx %llx\n",
 		       &its->phys_base, its_base_type_string[type],
 		       val, tmp);
-		free_pages((unsigned long)base, order);
+		its_free_pages(base, order);
 		return -ENXIO;
 	}
 
@@ -2554,8 +2635,8 @@ static void its_free_tables(struct its_node *its)
 
 	for (i = 0; i < GITS_BASER_NR_REGS; i++) {
 		if (its->tables[i].base) {
-			free_pages((unsigned long)its->tables[i].base,
-				   its->tables[i].order);
+			its_free_pages(its->tables[i].base,
+				       its->tables[i].order);
 			its->tables[i].base = NULL;
 		}
 	}
@@ -2821,7 +2902,8 @@ static bool allocate_vpe_l2_table(int cpu, u32 id)
 
 	/* Allocate memory for 2nd level table */
 	if (!table[idx]) {
-		page = alloc_pages(GFP_KERNEL | __GFP_ZERO, get_order(psz));
+		page = its_alloc_pages(GFP_KERNEL | __GFP_ZERO,
+				       get_order(psz));
 		if (!page)
 			return false;
 
@@ -2940,7 +3022,8 @@ static int allocate_vpe_l1_table(void)
 
 	pr_debug("np = %d, npg = %lld, psz = %d, epp = %d, esz = %d\n",
 		 np, npg, psz, epp, esz);
-	page = alloc_pages(GFP_ATOMIC | __GFP_ZERO, get_order(np * PAGE_SIZE));
+	page = its_alloc_pages(GFP_ATOMIC | __GFP_ZERO,
+			       get_order(np * PAGE_SIZE));
 	if (!page)
 		return -ENOMEM;
 
@@ -2986,8 +3069,8 @@ static struct page *its_allocate_pending_table(gfp_t gfp_flags)
 {
 	struct page *pend_page;
 
-	pend_page = alloc_pages(gfp_flags | __GFP_ZERO,
-				get_order(LPI_PENDBASE_SZ));
+	pend_page = its_alloc_pages(gfp_flags | __GFP_ZERO,
+				    get_order(LPI_PENDBASE_SZ));
 	if (!pend_page)
 		return NULL;
 
@@ -2999,7 +3082,7 @@ static struct page *its_allocate_pending_table(gfp_t gfp_flags)
 
 static void its_free_pending_table(struct page *pt)
 {
-	free_pages((unsigned long)page_address(pt), get_order(LPI_PENDBASE_SZ));
+	its_free_pages(page_address(pt), get_order(LPI_PENDBASE_SZ));
 }
 
 /*
@@ -3334,8 +3417,9 @@ static bool its_alloc_table_entry(struct its_node *its,
 
 	/* Allocate memory for 2nd level table */
 	if (!table[idx]) {
-		page = alloc_pages_node(its->numa_node, GFP_KERNEL | __GFP_ZERO,
-					get_order(baser->psz));
+		page = its_alloc_pages_node(its->numa_node,
+					    GFP_KERNEL | __GFP_ZERO,
+					    get_order(baser->psz));
 		if (!page)
 			return false;
 
@@ -3430,7 +3514,6 @@ static struct its_device *its_create_device(struct its_node *its, u32 dev_id,
 	if (WARN_ON(!is_power_of_2(nvecs)))
 		nvecs = roundup_pow_of_two(nvecs);
 
-	dev = kzalloc(sizeof(*dev), GFP_KERNEL);
 	/*
 	 * Even if the device wants a single LPI, the ITT must be
 	 * sized as a power of two (and you need at least one bit...).
@@ -3438,7 +3521,11 @@ static struct its_device *its_create_device(struct its_node *its, u32 dev_id,
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
@@ -3450,9 +3537,9 @@ static struct its_device *its_create_device(struct its_node *its, u32 dev_id,
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
@@ -3462,6 +3549,7 @@ static struct its_device *its_create_device(struct its_node *its, u32 dev_id,
 
 	dev->its = its;
 	dev->itt = itt;
+	dev->itt_sz = sz;
 	dev->nr_ites = nr_ites;
 	dev->event_map.lpi_map = lpi_map;
 	dev->event_map.col_map = col_map;
@@ -3489,7 +3577,7 @@ static void its_free_device(struct its_device *its_dev)
 	list_del(&its_dev->entry);
 	raw_spin_unlock_irqrestore(&its_dev->its->lock, flags);
 	kfree(its_dev->event_map.col_map);
-	kfree(its_dev->itt);
+	itt_free_pool(its_dev->itt, its_dev->itt_sz);
 	kfree(its_dev);
 }
 
@@ -5131,8 +5219,9 @@ static int __init its_probe_one(struct its_node *its)
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
@@ -5196,7 +5285,7 @@ static int __init its_probe_one(struct its_node *its)
 out_free_tables:
 	its_free_tables(its);
 out_free_cmd:
-	free_pages((unsigned long)its->cmd_base, get_order(ITS_CMD_QUEUE_SZ));
+	its_free_pages(its->cmd_base, get_order(ITS_CMD_QUEUE_SZ));
 out_unmap_sgir:
 	if (its->sgir_base)
 		iounmap(its->sgir_base);
@@ -5678,6 +5767,10 @@ int __init its_init(struct fwnode_handle *handle, struct rdists *rdists,
 	bool has_v4_1 = false;
 	int err;
 
+	itt_pool = gen_pool_create(get_order(ITS_ITT_ALIGN), -1);
+	if (!itt_pool)
+		return -ENOMEM;
+
 	gic_rdists = rdists;
 
 	its_parent = parent_domain;

---

## [14] Steven Price — 2024-07-01
*Subject: [PATCH v4 13/15] irqchip/gic-v3-its: Rely on genpool alignment*

its_create_device() over-allocated by ITS_ITT_ALIGN - 1 bytes to ensure
that an aligned area was available within the allocation. The new
genpool allocator has its min_alloc_order set to
get_order(ITS_ITT_ALIGN) so all allocations from it should be
appropriately aligned.

Remove the over-allocation from its_create_device() and alignment from
its_build_mapd_cmd().

Signed-off-by: Steven Price <steven.price@arm.com>
---
 drivers/irqchip/irq-gic-v3-its.c | 3 +--
 1 file changed, 1 insertion(+), 2 deletions(-)

diff --git a/drivers/irqchip/irq-gic-v3-its.c b/drivers/irqchip/irq-gic-v3-its.c
index 7d12556bc498..ab697e4004b9 100644
--- a/drivers/irqchip/irq-gic-v3-its.c
+++ b/drivers/irqchip/irq-gic-v3-its.c
@@ -699,7 +699,6 @@ static struct its_collection *its_build_mapd_cmd(struct its_node *its,
 	u8 size = ilog2(desc->its_mapd_cmd.dev->nr_ites);
 
 	itt_addr = virt_to_phys(desc->its_mapd_cmd.dev->itt);
-	itt_addr = ALIGN(itt_addr, ITS_ITT_ALIGN);
 
 	its_encode_cmd(cmd, GITS_CMD_MAPD);
 	its_encode_devid(cmd, desc->its_mapd_cmd.dev->device_id);
@@ -3520,7 +3519,7 @@ static struct its_device *its_create_device(struct its_node *its, u32 dev_id,
 	 */
 	nr_ites = max(2, nvecs);
 	sz = nr_ites * (FIELD_GET(GITS_TYPER_ITT_ENTRY_SIZE, its->typer) + 1);
-	sz = max(sz, ITS_ITT_ALIGN) + ITS_ITT_ALIGN - 1;
+	sz = max(sz, ITS_ITT_ALIGN);
 
 	itt = itt_alloc_pool(its->numa_node, sz);

---

## [15] Steven Price — 2024-07-01
*Subject: [PATCH v4 14/15] arm64: rsi: Interfaces to query attestation token*

From: Sami Mujawar <sami.mujawar@arm.com>

Add interfaces to query the attestation token using
the RSI calls.

Signed-off-by: Sami Mujawar <sami.mujawar@arm.com>
Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
v3: Prefix GRANULE_xxx defines with RSI_.
---
 arch/arm64/include/asm/rsi_cmds.h | 74 +++++++++++++++++++++++++++++++
 1 file changed, 74 insertions(+)

diff --git a/arch/arm64/include/asm/rsi_cmds.h b/arch/arm64/include/asm/rsi_cmds.h
index acb557dd4b88..a603ed0c60b9 100644
--- a/arch/arm64/include/asm/rsi_cmds.h
+++ b/arch/arm64/include/asm/rsi_cmds.h
@@ -10,6 +10,9 @@
 
 #include <asm/rsi_smc.h>
 
+#define RSI_GRANULE_SHIFT		12
+#define RSI_GRANULE_SIZE		(_AC(1, UL) << RSI_GRANULE_SHIFT)
+
 enum ripas {
 	RSI_RIPAS_EMPTY,
 	RSI_RIPAS_RAM,
@@ -57,4 +60,75 @@ static inline unsigned long rsi_set_addr_range_state(phys_addr_t start,
 	return res.a0;
 }
 
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
 #endif

---

## [16] Steven Price — 2024-07-01
*Subject: [PATCH v4 15/15] virt: arm-cca-guest: TSM_REPORT support for realms*

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
index 000000000000..61172730cb90
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
+	ret = tsm_register(&arm_cca_tsm_ops, NULL, &tsm_report_default_type);
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

## [17] Gavin Shan — 2024-07-09
*Subject: Re: [PATCH v4 01/15] arm64: rsi: Add RSI definitions*

On 7/1/24 7:54 PM, Steven Price wrote:
> From: Suzuki K Poulose <suzuki.poulose@arm.com>
> 

[...]

> --- /dev/null
> +++ b/arch/arm64/include/asm/rsi_smc.h

These fields have been defined in include/linux/arm-smccc.h. Those definitions
can be reused. Otherwise, it's not obvious to reader what does 0xC4000000 represent.

#define SMC_RSI_CALL_BASE	((ARM_SMCCC_FAST_CALL << ARM_SMCCC_TYPE_SHIFT)   | \
                                  (ARM_SMCCC_SMC_64 << ARM_SMCCC_CALL_CONV_SHIFT) | \
                                  (ARM_SMCCC_OWNER_STANDARD << ARM_SMCCC_OWNER_SHIFT))

or

#define SMC_RSI_CALL_BASE       ARM_SMCCC_CALL_VAL(ARM_SMCCC_FAST_CALL,            \
                                                    ARM_SMCCC_SMC_64,               \
                                                    ARM_SMCCC_OWNER_STANDARD,       \
                                                    0)

Thanks,
Gavin

---

## [18] Will Deacon — 2024-07-09
*Subject: Re: [PATCH v4 02/15] firmware/psci: Add psci_early_test_conduit()*

On Mon, Jul 01, 2024 at 10:54:52AM +0100, Steven Price wrote:
> From: Jean-Philippe Brucker <jean-philippe@linaro.org>
> 

Hmm, I don't think this is sufficient to check for SMCCC reliably.
Instead, I think you need to do something more involved:

1. Check for PSCI in the DT
2. Check that the PSCI major version is >= 1
3. Use PSCI_FEATURES to check that you have SMCCC
4. Use SMCCC_VERSION to find out which version of SMCCC you have

That's roughly what the PSCI driver does, so we should avoid duplicating
that logic.

Will

---

## [19] Will Deacon — 2024-07-09
*Subject: Re: [PATCH v4 04/15] arm64: realm: Query IPA size from the RMM*

On Mon, Jul 01, 2024 at 10:54:54AM +0100, Steven Price wrote:
> The top bit of the configured IPA size is used as an attribute to
> control whether the address is protected or shared. Query the

Since the _vast_ majority of Linux systems won't be running in a realm,
can we use a static key to avoid loading a constant each time?

Will

---

## [20] Will Deacon — 2024-07-09
*Subject: Re: [PATCH v4 05/15] arm64: Mark all I/O as non-secure shared*

On Mon, Jul 01, 2024 at 10:54:55AM +0100, Steven Price wrote:
> All I/O is by default considered non-secure for realms. As such
> mark them as shared with the host.

Hmm. I do wonder whether you've pushed the PROT_NS_SHARED too far here.

There's nothing _architecturally_ special about the top address bit.
Even if the RSI divides the IPA space in half, the CPU doesn't give two
hoots about it in the hardware. In which case, it feels wrong to bake
PROT_NS_SHARED into ioremap_prot -- it feels much better to me if the
ioremap() code OR'd that into the physical address when passing it down

There's a selfish side of that argument, in that we need to hook
ioremap() for pKVM protected guests, but I do genuinely feel that
treating address bits as protection bits is arbitrary and doesn't belong
in these low-level definitions. In a similar vein, AMD has its
sme_{set,clr}() macros that operate on the PA (e.g. via dma_to_phys()),
which feels like a more accurate abstraction to me.

Will

---

## [21] Will Deacon — 2024-07-09
*Subject: Re: [PATCH v4 06/15] arm64: Make the PHYS_MASK_SHIFT dynamic*

On Mon, Jul 01, 2024 at 10:54:56AM +0100, Steven Price wrote:
> Make the PHYS_MASK_SHIFT dynamic for Realms. This is only is required
> for masking the PFN from a pte entry. For a realm phys_mask_shift is

I tried to figure out where this is actually used so I could understand
your comment in the commit message:

 > This is only is required for masking the PFN from a pte entry

The closest thing I could find is in arch/arm64/mm/mmap.c, where the
mask is used as part of valid_mmap_phys_addr_range() which exists purely
to filter accesses to /dev/mem. That's pretty niche, so why not just
inline the RSI-specific stuff in there behind a static key instead of
changing these definitions?

Or did I miss a subtle user somewhere else?

Will

---

## [22] Will Deacon — 2024-07-09
*Subject: Re: [PATCH v4 07/15] arm64: Enforce bounce buffers for realm DMA*

On Mon, Jul 01, 2024 at 10:54:57AM +0100, Steven Price wrote:
> Within a realm guest it's not possible for a device emulated by the VMM
> to access arbitrary guest memory. So force the use of bounce buffers to

Why do we have to call this so early? Certainly, we won't have probed
the hypercalls under pKVM yet and I think it would be a lot cleaner if
you could defer your RSI discovery too.

Looking forward to the possibility of device assignment in future, how
do you see DMA_BOUNCE_UNALIGNED_KMALLOC interacting with a decrypted
SWIOTLB buffer? I'm struggling to wrap my head around how to fix that
properly.

Will

---

## [23] Will Deacon — 2024-07-09
*Subject: Re: [PATCH v4 08/15] arm64: mm: Avoid TLBI when marking pages as
 valid*

On Mon, Jul 01, 2024 at 10:54:58AM +0100, Steven Price wrote:
> When __change_memory_common() is purely setting the valid bit on a PTE
> (e.g. via the set_memory_valid() call) there is no need for a TLBI as

Can you elaborate on when this actually happens, please? It feels like a
case of "Doctor, it hurts when I do this" rather than something we should
be trying to short-circuit in the low-level code.

Will

---

## [24] Will Deacon — 2024-07-09
*Subject: Re: [PATCH v4 00/15] arm64: Support for running as a guest in Arm CCA*

Hi Steven,

On Mon, Jul 01, 2024 at 10:54:50AM +0100, Steven Price wrote:
> This series adds support for running Linux in a protected VM under the
> Arm Confidential Compute Architecture (CCA). This has been updated

Hold onto your hat, I'm going to dust off our pKVM protected guest
changes and see what we can share here! I've left a few comments on the
series, but the main differences seem to be:

  - You try to probe really early
  - You have that horrible split IPA space thing from the RSI spec

but some of the mechanisms are broadly similar (e.g. implementing the
set_memory_*crypted() API).

Hopefully I can give your GIC changes a spin, too.

Just one minor (but probably annoying) comment:

>  arch/arm64/Kconfig                            |   3 +
>  arch/arm64/include/asm/fixmap.h               |   2 +-

Any chance of some documentation, please?

Cheers,

Will

---

## [25] Suzuki K Poulose — 2024-07-09
*Subject: Re: [PATCH v4 05/15] arm64: Mark all I/O as non-secure shared*

Hi Will

On 09/07/2024 12:39, Will Deacon wrote:
> On Mon, Jul 01, 2024 at 10:54:55AM +0100, Steven Price wrote:
>> All I/O is by default considered non-secure for realms. As such

Actually we would like to push the decision of applying the 
"pgprot_decrypted" vs pgprot_encrypted into ioremap_prot(), rather
than sprinkling every user of ioremap_prot().

This could be made depending on the address that is passed on to the
ioremap_prot(). I guess we would need explicit requests from the callers
to add "encrypted vs decrypted". Is that what you guys are looking at ?

> 
> There's a selfish side of that argument, in that we need to hook

I believe that doesn't solve all the problems. They do have a hook in
__ioremap_caller() that implicitly applies pgprot_{en,de}crypted
depending on other info.

Cheers
Suzuki

> 
> Will

---

## [26] Suzuki K Poulose — 2024-07-09
*Subject: Re: [PATCH v4 06/15] arm64: Make the PHYS_MASK_SHIFT dynamic*

On 09/07/2024 12:43, Will Deacon wrote:
> On Mon, Jul 01, 2024 at 10:54:56AM +0100, Steven Price wrote:
>> Make the PHYS_MASK_SHIFT dynamic for Realms. This is only is required

We need to prevent ioremap() of addresses beyond that limit too.

Suzuki

> 
> Will

---

## [27] Will Deacon — 2024-07-10
*Subject: Re: [PATCH v4 12/15] irqchip/gic-v3-its: Share ITS tables with a
 non-trusted hypervisor*

On Mon, Jul 01, 2024 at 10:55:02AM +0100, Steven Price wrote:
> Within a realm guest the ITS is emulated by the host. This means the
> allocations must have been made available to the host by a call to

I gave this (and the following patch) a spin in a protected guest under
pKVM and was able to use MSIs for my virtio devices, so:

Tested-by: Will Deacon <will@kernel.org>

Will

---

## [28] Will Deacon — 2024-07-10
*Subject: Re: [PATCH v4 13/15] irqchip/gic-v3-its: Rely on genpool alignment*

On Mon, Jul 01, 2024 at 10:55:03AM +0100, Steven Price wrote:
> its_create_device() over-allocated by ITS_ITT_ALIGN - 1 bytes to ensure
> that an aligned area was available within the allocation. The new

Tested-by: Will Deacon <will@kernel.org>

Will

---

## [29] Steven Price — 2024-07-10
*Subject: Re: [PATCH v4 01/15] arm64: rsi: Add RSI definitions*

On 09/07/2024 06:19, Gavin Shan wrote:
> On 7/1/24 7:54 PM, Steven Price wrote:
>> From: Suzuki K Poulose <suzuki.poulose@arm.com>

Good point, even better is actually to just drop SMC_RSI_CALL_BASE and
just redefine SMC_RSI_FID() in terms of ARM_SMCCC_CALL_VAL().

Thanks,
Steve

---

## [30] Steven Price — 2024-07-10
*Subject: Re: [PATCH v4 02/15] firmware/psci: Add psci_early_test_conduit()*

Hi Will!

On 09/07/2024 11:48, Will Deacon wrote:
> On Mon, Jul 01, 2024 at 10:54:52AM +0100, Steven Price wrote:
>> From: Jean-Philippe Brucker <jean-philippe@linaro.org>

Hmm, you have a point. This was an improvement over the previous (assume
that making an SMC call is going to work well enough to return at error
for non-realms), but I guess it's technically possible for a system to
have PSCI but not implement enough of SMCCC to reliably get an error
code back.

Do you have any pointers on how pKVM detects it is a guest? Currently we
have a couple of things we have to do very early as a realm guest:

 * Mark memory as RIPAS_RAM. My preference would be to punt this problem
to the VMM (or UEFI) and make it a boot requirement. But it gets in the
way for attestation purposes as you can't have the same attestation
report for VMs which differ only by available RAM in that case.

 * earlycon - we need to know if the serial device is in unprotected
MMIO as that needs mapping with the top IPA bit set.

(I think that's all that's really early - everything else I can think of
should be after the usual PSCI probe should have happened)

Thanks for taking a look!

Steve

---

## [31] Steven Price — 2024-07-10
*Subject: Re: [PATCH v4 04/15] arm64: realm: Query IPA size from the RMM*

On 09/07/2024 11:53, Will Deacon wrote:
> On Mon, Jul 01, 2024 at 10:54:54AM +0100, Steven Price wrote:
>> The top bit of the configured IPA size is used as an attribute to

Fair enough, the following should do the trick:

#define PROT_NS_SHARED		(is_realm_world() ? prot_ns_shared : 0)

Thanks,
Steve

---

## [32] Steven Price — 2024-07-10
*Subject: Re: [PATCH v4 05/15] arm64: Mark all I/O as non-secure shared*

On 09/07/2024 13:54, Suzuki K Poulose wrote:
> Hi Will
> 

This is really just a simplification given we don't (yet) have device
assignment.

> Actually we would like to push the decision of applying the
> "pgprot_decrypted" vs pgprot_encrypted into ioremap_prot(), rather

There's a missing piece at the moment in terms of how the guest is going
to identify whether a particular device is protected or shared (i.e. a
real assigned device, or emulated by the VMM). When that's added then I
was expecting ioremap_prot() to provide that flag based on discovering
whether the address range passed in is for an assigned device or not.

>>
>> There's a selfish side of that argument, in that we need to hook

I'd be interested to see how pKVM will handle both protected and
emulated (by the VMM) devices. Although we have the 'top bit' flag it's
actually a pain to pass that down to the guest as a flag to use for this
purpose (e.g. 32 bit PCI BARs are too small). So our current thought is
an out-of-band request to identify whether a particular address
corresponds to a protected device or not. We'd then set the top bit
appropriately.

>> sme_{set,clr}() macros that operate on the PA (e.g. via dma_to_phys()),
>> which feels like a more accurate abstraction to me.

This is the other option - which pushes the knowledge down to the
individual drivers to decide whether a region is 'encrypted' (i.e.
protected) or not. It's more flexible, but potentially requires 'fixing'
many drivers to understand this.

Thanks,
Steve

> Cheers
> Suzuki

---

## [33] Steven Price — 2024-07-10
*Subject: Re: [PATCH v4 06/15] arm64: Make the PHYS_MASK_SHIFT dynamic*

On 09/07/2024 13:55, Suzuki K Poulose wrote:
> On 09/07/2024 12:43, Will Deacon wrote:
>> On Mon, Jul 01, 2024 at 10:54:56AM +0100, Steven Price wrote:

Which is arguably not much better in terms of nicheness... But this
seemed cleaner rather than trying to keep track of the niche areas of
the kernel which require this and modifying them. We could use a static
key here, but I don't think this is used for any hot-paths so it didn't
seem worth the complexity.

Steve

---

## [34] Steven Price — 2024-07-10
*Subject: Re: [PATCH v4 07/15] arm64: Enforce bounce buffers for realm DMA*

On 09/07/2024 12:56, Will Deacon wrote:
> On Mon, Jul 01, 2024 at 10:54:57AM +0100, Steven Price wrote:
>> Within a realm guest it's not possible for a device emulated by the VMM

I don't think we *need* the swiotlb up so early, it was more of a case
of this seemed a convenient place. We can probably move this later if
pKVM has a requirement for this.

In terms of RSI discovery then see my reply on patch 2.

> Looking forward to the possibility of device assignment in future, how
> do you see DMA_BOUNCE_UNALIGNED_KMALLOC interacting with a decrypted

Device assignment generally causes problems with bounce buffers. The
assumption has mostly been that any device which is clever enough to
deal with device assignment (which in our case means enlightened enough
to understand the extra bit on the bus) wouldn't need bounce buffers.

Suzuki: Do you know if DMA_BOUNCE_UNALIGNED_KMALLOC has been thought
about? Can we make the assumption that an assigned device will be coherent?

I have to admit to being a bit worried about current assumption that we
don't need two sets of bounce buffers - one decrypted for talking to the
host, and one encrypted for "old fashioned" talking to hardware which
has hardware limitations.

Steve

---

## [35] Steven Price — 2024-07-10
*Subject: Re: [PATCH v4 08/15] arm64: mm: Avoid TLBI when marking pages as
 valid*

On 09/07/2024 12:57, Will Deacon wrote:
> On Mon, Jul 01, 2024 at 10:54:58AM +0100, Steven Price wrote:
>> When __change_memory_common() is purely setting the valid bit on a PTE

This is for the benefit of the following patch. When transitioning a
page between shared and private we need to change the IPA (to set/clear
the top bit). This requires a break-before-make - see
__set_memory_enc_dec() in the following patch.

The easiest way of implementing the code was to just call
__change_memory_common() twice - once to make the entry invalid and then
again to make it valid with the new IPA. But that led to a double TLBI
which Catalin didn't like[1].

So this patch removes the unnecessary second TLBI by detecting that
we're just making the entry valid. Or at least it would if I hadn't
screwed up...

I should have changed the following patch to ensure that the second call
to __change_memory_common was only setting the PTE_VALID bit and not
changing anything else (so that the TLBI could be skipped) and forgot to
do that. So thanks for making me take a look at this again!

Thanks,
Steve

[1] https://lore.kernel.org/lkml/Zmc3euO2YGh-g9Th@arm.com/

---

## [36] Matias Ezequiel Vara Larsen — 2024-07-12
*Subject: Re: [PATCH v4 00/15] arm64: Support for running as a guest in Arm CCA*

On Mon, Jul 01, 2024 at 10:54:50AM +0100, Steven Price wrote:
> This series adds support for running Linux in a protected VM under the
> Arm Confidential Compute Architecture (CCA). This has been updated

Hello,

I tested this series on QEMU/KVM with the CCA patches(v2) and the FVP
model. I could not find any evident issue.

Tested-by: Matias Ezequiel Vara Larsen <mvaralar@redhat.com>

---

## [37] Gavin Shan — 2024-07-23
*Subject: Re: [PATCH v4 01/15] arm64: rsi: Add RSI definitions*

On 7/11/24 1:34 AM, Steven Price wrote:
> On 09/07/2024 06:19, Gavin Shan wrote:
>> On 7/1/24 7:54 PM, Steven Price wrote:

Agreed, it's going to be more clear. The point is to reuse the existing definitions
in include/linux/arm-smccc.h.

Sorry for slow response. I spent some time going through tf-a/tf-rmm implementation
to understand how GPT and stage-2 page-table are managed in order to review this
series. I realized it's complicated to manage GPT and stage-2 page-table and lots
of details still need more time to be figured out.

Thanks,
Gavin

---

## [38] Gavin Shan — 2024-07-23
*Subject: Re: [PATCH v4 01/15] arm64: rsi: Add RSI definitions*

On 7/1/24 7:54 PM, Steven Price wrote:
> From: Suzuki K Poulose <suzuki.poulose@arm.com>
> 

Some nits and questions like below.

> diff --git a/arch/arm64/include/asm/rsi_cmds.h b/arch/arm64/include/asm/rsi_cmds.h
> new file mode 100644

#endif /* __ASM_RSI_CMDS_H */

> diff --git a/arch/arm64/include/asm/rsi_smc.h b/arch/arm64/include/asm/rsi_smc.h
> new file mode 100644

I think these return values are copied from tf-rmm/lib/smc/include/smc-rsi.h, but
UL() prefix has been missed. It's still probably worthy to have it to indicate the
width of the return values. Besides, it seems that RSI_ERROR_COUNT is also missed
here.


> +#define SMC_RSI_FID(_x)			(SMC_RSI_CALL_BASE + (_x))
> +

In tf-rmm/lib/smc/include/smc-rsi.h, it is SMC_RSI_ATTEST_TOKEN_INIT instead
of SMC_RSI_ATTESTATION_TOKEN_INIT. The short description for all SMC calls have
been dropped and I think they're worthy to be kept. At least, it helps readers
to understand what the SMC call does. For this particular SMC call, the short
description is something like below:

/*
  * Initialize the operation to retrieve an attestation token.
  * :
  */

> +/*
> + * arg1 == The IPA of token buffer

SMC_RSI_ATTEST_TOKEN_CONTINUE as defined in tf-rmm.

> +/*
> + * arg1  == Index, which measurements slot to extend

The order of these SMC call definitions are sorted based on their corresponding
function IDs. For example, SMC_RSI_MEASUREMENT_READ would be appearing prior to
SMC_RSI_MEASUREMENT_EXTEND.

> +#ifndef __ASSEMBLY__
> +

This describes the argument to SMC call RSI_REALM_CONFIG and its address needs to
be aligned to 0x1000. Otherwise, RSI_ERROR_INPUT is returned. This maybe worthy
a comment to explain it why we need 0x1000 alignment here.

It seems the only 4KB page size (GRANULE_SIZE) is supported by tf-rmm at present.
The fixed alignment (0x1000) becomes broken if tf-rmm is extended to support
64KB in future. Maybe tf-rmm was designed to work with the minimal page size (4KB).

> +#endif /* __ASSEMBLY__ */
> +

Thanks,
Gavin

---

## [39] Gavin Shan — 2024-07-30
*Subject: Re: [PATCH v4 03/15] arm64: Detect if in a realm and set RIPAS RAM*

On 7/1/24 7:54 PM, Steven Price wrote:
> From: Suzuki K Poulose <suzuki.poulose@arm.com>
> 

@flags has been defined as int instead of unsigned long, which is inconsistent
to TF-RMM's definitions since it has type of 'unsigned long'.

> +/*
> + * Convert the specified range to RAM. Do not use this if you rely on the

s/0/RSI_NO_CHANGE_DESTROYED
s/#endif/#endif /* __ASM_RSI_H_ */

> diff --git a/arch/arm64/include/asm/rsi_cmds.h b/arch/arm64/include/asm/rsi_cmds.h
> index 89e907f3af0c..acb557dd4b88 100644
                                              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                              blocks and convert them to

> +	 * protected memory. We should take extra care to ensure that we DO NOT
> +	 * permit any "DESTROYED" pages to be converted to "RAM".

If I'm understanding the code completely, this changes the memory state from
RIPAS_EMPTY to RIPAS_RAM so that the following page faults can be routed to
host properly. Otherwise, a SEA is injected to the realm according to
tf-rmm/runtime/core/exit.c::handle_data_abort(). The comments can be more
explicit to replace "fault" with "SEA (Synchronous External Abort)".

Besides, this forces a guest exit with reason RMI_EXIT_RIPAS_CHANGE which is
handled by the host, where RMI_RTT_SET_RIPAS is triggered to convert the memory
state from RIPAS_EMPTY to RIPAS_RAM. The question is why the conversion can't
be done by VMM (QEMU)?

> +void __init arm64_rsi_init(void)
> +{

Thanks,
Gavin

---

## [40] Gavin Shan — 2024-07-30
*Subject: Re: [PATCH v4 05/15] arm64: Mark all I/O as non-secure shared*

On 7/1/24 7:54 PM, Steven Price wrote:
> All I/O is by default considered non-secure for realms. As such
> mark them as shared with the host.

I'm unable to understand this. Steven, could you please explain a bit how
PROT_NS_SHARED is turned to a shared (non-secure) mapping to hardware?
According to tf-rmm's implementation in tf-rmm/lib/s2tt/src/s2tt_pvt_defs.h,
a shared (non-secure) mapping is is identified by NS bit (bit#55). I find
difficulties how the NS bit is correlate with PROT_NS_SHARED. For example,
how the NS bit is set based on PROT_NS_SHARED.

> diff --git a/arch/arm64/include/asm/fixmap.h b/arch/arm64/include/asm/fixmap.h
> index 87e307804b99..f2c5e653562e 100644

Thanks,
Gavin

---

## [41] Suzuki K Poulose — 2024-07-30
*Subject: Re: [PATCH v4 05/15] arm64: Mark all I/O as non-secure shared*

Hi Gavin,

Thanks for looking at the patch. Responses inline.

On 30/07/2024 02:36, Gavin Shan wrote:
> On 7/1/24 7:54 PM, Steven Price wrote:
>> All I/O is by default considered non-secure for realms. As such


There are two things at play here :

1. Stage1 mapping controlled by the Realm (Linux in this case, as above).
2. Stage2 mapping controlled by the RMM (with RMI commands from NS Host).

Also :
The Realm's IPA space is divided into two halves (decided by the IPA 
Width of the Realm, not the NSbit #55), protected (Lower half) and
Unprotected (Upper half). All stage2 mappings of the "Unprotected IPA"
will have the NS bit (#55) set by the RMM. By design, any MMIO access
to an unprotected half is sent to the NS Host by RMM and any page
the Realm wants to share with the Host must be in the Upper half
of the IPA.

What we do above is controlling the "Stage1" used by the Linux. i.e,
for a given VA, we flip the Guest "PA" (in reality IPA) to the
"Unprotected" alias.

e.g., DTB describes a UART at address 0x10_0000 to Realm (with an IPA 
width of 40, like in the normal VM case), emulated by the host. Realm is
trying to map this I/O address into Stage1 at VA. So we apply the
BIT(39) as PROT_NS_SHARED while creating the Stage1 mapping.

ie., VA == stage1 ==> BIT(39) | 0x10_0000 =(IPA)== > 0x80_10_0000

Now, the Stage2 mapping won't be present for this IPA if it is emulated
and thus an access to "VA" causes a Stage2 Abort to the Host, which the
RMM allows the host to emulate. Otherwise a shared page would have been
mapped by the Host (and NS bit set at Stage2 by RMM), allowing the
data to be shared with the host.

Does that answer your question ?

Suzuki

> 
>> diff --git a/arch/arm64/include/asm/fixmap.h

---

## [42] Suzuki K Poulose — 2024-07-30
*Subject: Re: [PATCH v4 03/15] arm64: Detect if in a realm and set RIPAS RAM*

Hi Gavin

Thanks for your review, comments inline.

On 30/07/2024 00:37, Gavin Shan wrote:
> On 7/1/24 7:54 PM, Steven Price wrote:
>> From: Suzuki K Poulose <suzuki.poulose@arm.com>

Sorry, do you mean that TF-RMM treats the "flags" as an "int" instead of
unsigned long and we should be consistent with TF-RMM ? If so, I don't
think that is correct. We should be compliant to the RMM spec, which
describes "RsiRipasChangeFlags" as a 64bit value and thus must be
'unsigned long' as we used here.

> 
>> +/*

This is not required as we do not care if the GRANULE was destroyed or
not, since it is going to be "UNUSED" anyway in a protected way 
(RIPAS_EMPTY). And we do not rely on the contents of the memory being
preserved, when the page is made shared (In fact we cannot do that
with Arm CCA).

Thus we do not get any security benefits with the flag. The flag is ONLY
useful, when the Realm does a "blanket" IPA_STATE_SET(RIPAS_RAM) for
all of its memory area described as RAM. In this case, we want to make
sure that the Host hasn't destroyed any DATA that was loaded (and
measured) in the "NEW" state.

e.g, Host loads Kernel at Addr X in RAM (which is transitioned to 
RIPAS_RAM, measured in RIM by RMM) and ACTIVATEs the Realm. Host could 
then destroy some pages of the loaded image before the Realm boots (thus
transitioning into DESTROYED). But for the Realm, at early boot, it is
much easier to "mark" the entire RAM region as RIPAS_RAM,


for_each_memory_region(region) {
	set_ipa_state_range(region->start, region->end, RIPAS_RAM, 
RSI_NO_CHANGE_DESTROYED);
}

rather than performing:

for_each_granule(g in DRAM) :

switch (rsi_get_ipa_state(g)) {
case RIPAS_EMPTY: rsi_set_ipa_state(g, RIPAS_RAM); break;
case RIPAS_RAM: break; /* Nothing to do */
case DESTROYED: BUG();
}





> s/#endif/#endif /* __ASM_RSI_H_ */
> 

TBH, I don't see any significant difference between the two. Am I
missing something ?

> 
>> +     * protected memory. We should take extra care to ensure that we 

Agreed.  SEA is more accurate than fault.

> 
> Besides, this forces a guest exit with reason RMI_EXIT_RIPAS_CHANGE 

A VMM could potentially do this via INIT_RIPAS at Realm creation for
the entire RAM. But, as far as the Realm is concerned it is always safer 
to do this step and is relatively a lightweight operation at boot. 
Physical pages need not be allocated/mapped in stage2 with the IPA State 
change.


Suzuki
> 
>> +void __init arm64_rsi_init(void)

---

## [43] Gavin Shan — 2024-07-31
*Subject: Re: [PATCH v4 05/15] arm64: Mark all I/O as non-secure shared*

Hi Suzuki,

On 7/30/24 8:36 PM, Suzuki K Poulose wrote:
> On 30/07/2024 02:36, Gavin Shan wrote:
>> On 7/1/24 7:54 PM, Steven Price wrote:
                                                      0x8000_10_0000

> Now, the Stage2 mapping won't be present for this IPA if it is emulated
> and thus an access to "VA" causes a Stage2 Abort to the Host, which the

Thank you for the explanation and details. It really helps to understand
how the access fault to the unprotected space (upper half) is routed to NS
host, and then VMM (QEMU) for emulation. If the commit log can be improved
with those information, it will make reader easier to understand the code.

I had the following call trace and it seems the address 0x8000_10_1000 is
converted to 0x10_0000 in [1], based on current code base (branch: cca-full/v3).
At [1], the GPA is masked with kvm_gpa_stolen_bits() so that BIT#39 is removed
in this particular case.

   kvm_vcpu_ioctl(KVM_RUN)                         // non-secured host
   kvm_arch_vcpu_ioctl_run
   kvm_rec_enter
   rmi_rec_enter                                   // -> SMC_RMI_REC_ENTER
     :
   rmm_handler                                     // tf-rmm
   handle_ns_smc
   smc_rec_enter
   rec_run_loop
   run_realm
     :
   el2_vectors
   el2_sync_lel
   realm_exit
     :
   handle_realm_exit
   handle_exception_sync
   handle_data_abort
     :
   handle_rme_exit                                 // non-secured host
   rec_exit_sync_dabt
   kvm_handle_guest_abort                          // -> [1]
   gfn_to_memslot
   io_mem_abort
   kvm_io_bus_write                                // -> run->exit_reason = KVM_EXIT_MMIO

Another question is how the Granule Protection Check (GPC) table is updated so
that the corresponding granule (0x8000_10_1000) to is accessible by NS host? I
mean how the BIT#39 is synchronized to GPC table and translated to the property
"granule is accessible by NS host".
     
Thanks,
Gavin

---

## [44] Gavin Shan — 2024-07-31
*Subject: Re: [PATCH v4 03/15] arm64: Detect if in a realm and set RIPAS RAM*

Hi Suzuki,

On 7/30/24 11:51 PM, Suzuki K Poulose wrote:
> On 30/07/2024 00:37, Gavin Shan wrote:
>> On 7/1/24 7:54 PM, Steven Price wrote:

No worries, I guess I didn't make myself clear enough. Sorry about that.
Let me explain it with more details. @flag is passed down as the following
call trace shows.

   rsi_set_memory_range_protected_safe
     rsi_set_memory_range                             // RSI_NO_CHANGE_DESTROYED
       rsi_set_addr_range_state
         arm_smccc_smc(SMC_RSI_IPA_STATE_SET, ...)

The kernel defines RSI_CHANGE_DESTROYED as a "int" value, but same flag has
been defined as 'unsigned int' value in tf-rmm. However, kernel uses 'unsigned
long' flags to hold it.

   // kernel's prototype - 'unsigned long flags'
   static inline int rsi_set_memory_range(phys_addr_t start, phys_addr_t end,
                                        enum ripas state, unsigned long flags)

   // kernel's definition - 'int'
   #define RSI_CHANGE_DESTROYED    0

   // tf-rmm's definition - 'unsigned int'
   #define U(_x)                 (unsigned int)(_x)
   #define RSI_CHANGE_DESTROYED  U(0)

>>
>>> +/*

The point was 0 and RSI_NO_CHANGE_DESTROYED are interchangeable. Since RSI_NO_CHANGE_DESTROYED
has been defined as 0, why we don't used RSI_NO_CHANGE_DESTROYED?

> 
>> s/#endif/#endif /* __ASM_RSI_H_ */

for_each_mem_range() is a helper provided by memory block management module.
So 'memory block' sounds like more accurate than broadly used term "memory
range" here.

>>
>>> +     * protected memory. We should take extra care to ensure that we DO NOT

Ok.

>>
>> Besides, this forces a guest exit with reason RMI_EXIT_RIPAS_CHANGE which is

Ok. Thanks for the explanation.

> 
> Suzuki

Thanks,
Gavin

---

## [45] Suzuki K Poulose — 2024-07-31
*Subject: Re: [PATCH v4 05/15] arm64: Mark all I/O as non-secure shared*

On 31/07/2024 07:36, Gavin Shan wrote:
> Hi Suzuki,
> 

Yep, my bad.

> 
>> Now, the Stage2 mapping won't be present for this IPA if it is emulated

Correct. KVM deals with "GFN" and as such masks the "protection" bit,
as the IPA is split.

>    gfn_to_memslot
>    io_mem_abort

Good question. GPC is only applicable for memory accesses that are 
actually "made" (think of this as Stage3).
In this case, the Stage2 walk causes an abort and as such the address is
never "accessed" (like in the normal VM) and host handles it.
In case of a "shared" memory page, the "stage2" mapping created *could*
(RMM doesn't guarantee what gets mapped on the Unprotected alias) be
mapped to a Granule in the NS PAS (normal world page), via 
RMI_RTT_MAP_UNPROTECTED. RMM only guarantees that the output of the
Stage2 translation is "NS" PAS (the actual PAS of the Granule may not
be NS, e.g. if we have a malicious host).

Now, converting a "protected IPA" to "shared" (even though we don't
share the same Physical page for the aliases with guest_mem, but
CCA doesn't prevent this) would take the following route :

Realm: IPA_STATE_SET(ipa, RIPAS_EMPTY)-> REC Exit ->
        Host Reclaims the "PA" backing "IPA" via RMI_DATA_DESTROY ->
        Change PAS to Realm (RMI_GRANULE_UNDELEGATE)

Realm: Access the BIT(39)|ipa => Stage2 Fault ->
        Host maps "BIT(39)|ipa" vai RMI_RTT_MAP_UNPROTECTED.

The important things to remember:

1) "NS_PROT" is just a way to access the "Aliased IPA" in the 
UNPROTECTED half and is only a "Stage1" change.
2) It doesn't *change the PAS* of the backing PA implicitly
3) It doesn't change the PAS of the resulting "Translation" at Stage2, 
instead it targets a "different IPA"->PA translation and the resulting
*access* is guaranteed to be NS PAS.

Suzuki

> Thanks,
> Gavin

---

## [46] Suzuki K Poulose — 2024-07-31
*Subject: Re: [PATCH v4 03/15] arm64: Detect if in a realm and set RIPAS RAM*

On 31/07/2024 08:03, Gavin Shan wrote:
> Hi Suzuki,
> 

Thanks for the detailed explanation, you are right, we should fix it.

> 
>    // tf-rmm's definition - 'unsigned int'

Ah, my bad. But like I said, we should instead use the 
RSI_CHANGE_DESTROYED for transitions to EMPTY.

Suzuki



> 
>>

---

## [47] Shanker Donthineni — 2024-08-15
*Subject: Re: [PATCH v4 00/15] arm64: Support for running as a guest in Arm CCA*

Hi Steven,

On 7/12/24 03:54, Matias Ezequiel Vara Larsen wrote:
> On Mon, Jul 01, 2024 at 10:54:50AM +0100, Steven Price wrote:
>> This series adds support for running Linux in a protected VM under the

Which cca-host branch should I use for testing cca-guest/v4?

I'm getting compilation errors with cca-host/v3 and cca-guest/v4, is there
any known WAR or fix to resolve this issue?


arch/arm64/kvm/rme.c: In function ‘kvm_realm_reset_id_aa64dfr0_el1’:
././include/linux/compiler_types.h:487:45: error: call to ‘__compiletime_assert_650’ declared with attribute error: FIELD_PREP: value too large for the field
   487 |         _compiletime_assert(condition, msg, __compiletime_assert_, __COUNTER__)
       |                                             ^
././include/linux/compiler_types.h:468:25: note: in definition of macro ‘__compiletime_assert’
   468 |                         prefix ## suffix();                             \
       |                         ^~~~~~
././include/linux/compiler_types.h:487:9: note: in expansion of macro ‘_compiletime_assert’
   487 |         _compiletime_assert(condition, msg, __compiletime_assert_, __COUNTER__)
       |         ^~~~~~~~~~~~~~~~~~~
./include/linux/build_bug.h:39:37: note: in expansion of macro ‘compiletime_assert’
    39 | #define BUILD_BUG_ON_MSG(cond, msg) compiletime_assert(!(cond), msg)
       |                                     ^~~~~~~~~~~~~~~~~~
./include/linux/bitfield.h:68:17: note: in expansion of macro ‘BUILD_BUG_ON_MSG’
    68 |                 BUILD_BUG_ON_MSG(__builtin_constant_p(_val) ?           \
       |                 ^~~~~~~~~~~~~~~~
./include/linux/bitfield.h:115:17: note: in expansion of macro ‘__BF_FIELD_CHECK’
   115 |                 __BF_FIELD_CHECK(_mask, 0ULL, _val, "FIELD_PREP: ");    \
       |                 ^~~~~~~~~~~~~~~~
arch/arm64/kvm/rme.c:315:16: note: in expansion of macro ‘FIELD_PREP’
   315 |         val |= FIELD_PREP(ID_AA64DFR0_EL1_BRPs_MASK, bps - 1) |
       |                ^~~~~~~~~~
make[5]: *** [scripts/Makefile.build:244: arch/arm64/kvm/rme.o] Error 1
make[4]: *** [scripts/Makefile.build:485: arch/arm64/kvm] Error 2
make[3]: *** [scripts/Makefile.build:485: arch/arm64] Error 2
make[3]: *** Waiting for unfinished jobs....

I'm using gcc-13.3.0 compiler and cross-compiling on X86 machine.


-Shanker

---

## [48] Steven Price — 2024-08-16
*Subject: Re: [PATCH v4 01/15] arm64: rsi: Add RSI definitions*

Hi Gavin,

Sorry for the slow reply, I realised I'd never replied to this email.

On 23/07/2024 07:22, Gavin Shan wrote:
> On 7/1/24 7:54 PM, Steven Price wrote:
>> From: Suzuki K Poulose <suzuki.poulose@arm.com>

The source of all these defines is the RMM spec[1], tf-rmm obviously
also has similar defines but I haven't been copying from there because
this code is intended to work with any RMM that complies with the spec.

In particular RSI_ERROR_COUNT isn't defined by the spec and we
(currently at least) have no use for it in Linux.

I'm not sure how much benefit the UL() prefix brings, but I've no
objection so I'll add it.

[1] https://developer.arm.com/documentation/den0137/latest

>> +#define SMC_RSI_FID(_x)            (SMC_RSI_CALL_BASE + (_x))
>> +

Here tf-rmm is deviating from the spec, the specification gives the long
form, so I'd prefer to stick to the spec unless we have a good reason
for deviating.

> calls have
> been dropped and I think they're worthy to be kept. At least, it helps

Fair point, I'll include the one-line descriptions from the spec
(although in most cases that level of detail is obvious from the name).

>> +/*
>> + * arg1 == The IPA of token buffer

As above, the abbreviation isn't used in the spec.

>> +/*
>> + * arg1  == Index, which measurements slot to extend

Good spot - the spec annoyingly sorts alphabetically so I do struggle to
keep everything in the right order. Will fix.

>> +#ifndef __ASSEMBLY__
>> +

Will add.

> It seems the only 4KB page size (GRANULE_SIZE) is supported by tf-rmm at
> present.

Again this is a specification requirement. The size of a granule is
always 4k - even if the host, guest or RMM choose to use a different
page size - the specification requires that the alignment is 4k. If a
larger page size is used in the RMM then it must jump through whatever
hoops are required to support the config address being only 4k aligned.

In practice there is a distinction between page size (which could vary
between the different components in the system) and granule size which
is the size which the physical memory can be switched between the
different PA spaces. The RMM specification defines the granule size as
4k (and doesn't provide any configurability of this), see section A2.2.
The system is expected to have a "GPT MMU" which controls which physical
address spaces each granule is visible in. There's quite a good
document[2] on the Arm website explaining this in more detail.

[2]
https://developer.arm.com/documentation/den0126/0100/Granule-Protection-Checks

Thanks,
Steve

>> +#endif /* __ASSEMBLY__ */
>> +

---

## [49] Steven Price — 2024-08-16
*Subject: Re: [PATCH v4 00/15] arm64: Support for running as a guest in Arm CCA*

On 15/08/2024 23:16, Shanker Donthineni wrote:
> Hi Steven,
> 

cca-host/v3 should work with cca-guest/v4. I've been working on
rebasing/updating the branches and should be able to post v4/v5 series
next week.

> 
> arch/arm64/kvm/rme.c: In function ‘kvm_realm_reset_id_aa64dfr0_el1’:

I'm not sure quite how this happens. The 'value' (bps - 1) shouldn't be
considered constant, so I don't see how the compiler has decided to
complain here - the __builtin_constant_p() should really be evaluating to 0.

The only thing I can think of is if the compiler has somehow determined
that rmm_feat_reg0 is 0 - which in theory it could do if it knew that
kvm_init_rme() cannot succeed (rmi_features() would never be called, so
the variable will never be set). Which makes me wonder if you're
building with a PAGE_SIZE other than 4k?

Obviously the code should still build if that's the case (so this would
be a bug) but we don't currently support CCA with PAGE_SIZE != 4k.

Steve

---

## [50] Shanker Donthineni — 2024-08-16
*Subject: Re: [PATCH v4 00/15] arm64: Support for running as a guest in Arm CCA*

On 8/16/24 11:06, Steven Price wrote:
> External email: Use caution opening links or attachments
> 

I've encountered this error multiple times with both 4K and 64K, but it's
currently not reproducible. I'll update if the issue reappears. In the
meantime, I've verified the host-v3 and guest-v4 patches using v6.11.rc3,
tested Realm boot, CCA-KVM-UNIT-TESTs, and normal VM boot (without CCA).
No issues have been observed.

Additionally, I've validated Realm and CCA-KVM-UNIT-TESTs on a host with
PSZ=64K. For testing purposes, I modified KVM64 and KVM-UNIT-TESTS to
support PSZ=64K.


Tested-by: Shanker Donthineni <sdonthineni@nvidia.com>


> Steve
>

---
