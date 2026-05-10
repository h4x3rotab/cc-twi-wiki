---
title: '[PATCH v3 00/14] arm64: Support for running as a guest in Arm CCA'
date: 2024-06-05
last_reply: 2024-06-28
message_count: 54
participants: ['Itaru Kitayama', 'Steven Price', 'Marc Zyngier', 'Catalin Marinas', 'Michael Kelley', 'Jean-Philippe Brucker', 'Suzuki K Poulose', 'Peter Maydell', 'Jeremy Linton']
---

## [1] Itaru Kitayama — 2024-06-05

Hi Steven,
On Wed, Jun 05, 2024 at 10:29:52AM +0100, Steven Price wrote:
> This series adds support for running Linux in a protected VM under the
> Arm Confidential Compute Architecture (CCA). This has been updated

The v3 guest built with clang booted fine on FVP backed by v2 host kernel.

Tested-by: Itaru Kitayama <itaru.kitayama@fujitsu.com>

Thanks,
Itaru.

> Sami Mujawar (2):
>   arm64: rsi: Interfaces to query attestation token

---

## [2] Steven Price — 2024-06-05
*Subject: [PATCH v3 00/14] arm64: Support for running as a guest in Arm CCA*

This series adds support for running Linux in a protected VM under the
Arm Confidential Compute Architecture (CCA). This has been updated
following the feedback from the v2 posting[1]. Thanks for the feedback!
Individual patches have a change log for v3.

The biggest change from v2 is fixing set_memory_{en,de}crypted() to
perform a break-before-make sequence. Note that only the virtual address
supplied is flipped between shared and protected, so if e.g. a vmalloc()
address is passed the linear map will still point to the (now invalid)
previous IPA. Attempts to access the wrong address may trigger a
Synchronous External Abort. However any code which attempts to access
the 'encrypted' alias after set_memory_decrypted() is already likely to
be broken on platforms that implement memory encryption, so I don't
expect problems.

The ABI to the RMM from a realm (the RSI) is based on the final RMM v1.0
(EAC 5) specification[2]. Future RMM specifications will be backwards
compatible so a guest using the v1.0 specification (i.e. this series)
will be able to run on future versions of the RMM without modification.

Arm plans to set up a CI system to perform at a minimum boot testing of
Linux as a guest within a realm.

This series is based on v6.10-rc1. It is also available as a git
repository:

https://gitlab.arm.com/linux-arm/linux-cca cca-guest/v3

This series (the guest side) should be in a good state so please review
with the intention that this could be merged soon. The host side (KVM
changes) is likely to require some more iteration and I'll post that as
a separate series shortly - note that there is no tie between the series
(i.e. you can mix and match v2 and v3 postings of the host and guest).

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

[1] https://lore.kernel.org/r/20240412084213.1733764-1-steven.price%40arm.com
[2] https://developer.arm.com/documentation/den0137/1-0eac5/
[3] https://www.arm.com/architecture/security-features/arm-confidential-compute-architecture

Sami Mujawar (2):
  arm64: rsi: Interfaces to query attestation token
  virt: arm-cca-guest: TSM_REPORT support for realms

Steven Price (5):
  arm64: realm: Query IPA size from the RMM
  arm64: Mark all I/O as non-secure shared
  arm64: Make the PHYS_MASK_SHIFT dynamic
  arm64: Enforce bounce buffers for realm DMA
  arm64: realm: Support nonsecure ITS emulation shared

Suzuki K Poulose (7):
  arm64: rsi: Add RSI definitions
  arm64: Detect if in a realm and set RIPAS RAM
  fixmap: Allow architecture overriding set_fixmap_io
  arm64: Override set_fixmap_io
  arm64: Enable memory encrypt for Realms
  arm64: Force device mappings to be non-secure shared
  efi: arm64: Map Device with Prot Shared

 arch/arm64/Kconfig                            |   3 +
 arch/arm64/include/asm/fixmap.h               |   4 +-
 arch/arm64/include/asm/io.h                   |   6 +-
 arch/arm64/include/asm/mem_encrypt.h          |  17 ++
 arch/arm64/include/asm/pgtable-hwdef.h        |   6 -
 arch/arm64/include/asm/pgtable-prot.h         |   3 +
 arch/arm64/include/asm/pgtable.h              |   7 +-
 arch/arm64/include/asm/rsi.h                  |  48 ++++
 arch/arm64/include/asm/rsi_cmds.h             | 143 ++++++++++++
 arch/arm64/include/asm/rsi_smc.h              | 142 ++++++++++++
 arch/arm64/include/asm/set_memory.h           |   3 +
 arch/arm64/kernel/Makefile                    |   3 +-
 arch/arm64/kernel/efi.c                       |   2 +-
 arch/arm64/kernel/rsi.c                       |  96 ++++++++
 arch/arm64/kernel/setup.c                     |   8 +
 arch/arm64/mm/init.c                          |  10 +-
 arch/arm64/mm/mmu.c                           |  13 ++
 arch/arm64/mm/pageattr.c                      |  65 +++++-
 drivers/irqchip/irq-gic-v3-its.c              |  90 ++++++--
 drivers/virt/coco/Kconfig                     |   2 +
 drivers/virt/coco/Makefile                    |   1 +
 drivers/virt/coco/arm-cca-guest/Kconfig       |  11 +
 drivers/virt/coco/arm-cca-guest/Makefile      |   2 +
 .../virt/coco/arm-cca-guest/arm-cca-guest.c   | 211 ++++++++++++++++++
 include/asm-generic/fixmap.h                  |   2 +
 25 files changed, 858 insertions(+), 40 deletions(-)
 create mode 100644 arch/arm64/include/asm/mem_encrypt.h
 create mode 100644 arch/arm64/include/asm/rsi.h
 create mode 100644 arch/arm64/include/asm/rsi_cmds.h
 create mode 100644 arch/arm64/include/asm/rsi_smc.h
 create mode 100644 arch/arm64/kernel/rsi.c
 create mode 100644 drivers/virt/coco/arm-cca-guest/Kconfig
 create mode 100644 drivers/virt/coco/arm-cca-guest/Makefile
 create mode 100644 drivers/virt/coco/arm-cca-guest/arm-cca-guest.c

---

## [3] Steven Price — 2024-06-05
*Subject: [PATCH v3 01/14] arm64: rsi: Add RSI definitions*

From: Suzuki K Poulose <suzuki.poulose@arm.com>

The RMM (Realm Management Monitor) provides functionality that can be
accessed by a realm guest through SMC (Realm Services Interface) calls.

The SMC definitions are based on DEN0137[1] version A-eac5.

[1] https://developer.arm.com/documentation/den0137/latest

Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v2:
 * Rename rsi_get_version() to rsi_request_version()
 * Fix size/alignment of struct realm_config
---
 arch/arm64/include/asm/rsi_cmds.h |  47 ++++++++++
 arch/arm64/include/asm/rsi_smc.h  | 142 ++++++++++++++++++++++++++++++
 2 files changed, 189 insertions(+)
 create mode 100644 arch/arm64/include/asm/rsi_cmds.h
 create mode 100644 arch/arm64/include/asm/rsi_smc.h

diff --git a/arch/arm64/include/asm/rsi_cmds.h b/arch/arm64/include/asm/rsi_cmds.h
new file mode 100644
index 000000000000..ad425c5d6f1b
--- /dev/null
+++ b/arch/arm64/include/asm/rsi_cmds.h
@@ -0,0 +1,47 @@
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
+static inline void invoke_rsi_fn_smc_with_res(unsigned long function_id,
+					      unsigned long arg0,
+					      unsigned long arg1,
+					      unsigned long arg2,
+					      unsigned long arg3,
+					      struct arm_smccc_res *res)
+{
+	arm_smccc_smc(function_id, arg0, arg1, arg2, arg3, 0, 0, 0, res);
+}
+
+static inline unsigned long rsi_request_version(unsigned long req,
+						unsigned long *out_lower,
+						unsigned long *out_higher)
+{
+	struct arm_smccc_res res;
+
+	invoke_rsi_fn_smc_with_res(SMC_RSI_ABI_VERSION, req, 0, 0, 0, &res);
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
+	invoke_rsi_fn_smc_with_res(SMC_RSI_REALM_CONFIG, virt_to_phys(cfg), 0, 0, 0, &res);
+	return res.a0;
+}
+
+#endif
diff --git a/arch/arm64/include/asm/rsi_smc.h b/arch/arm64/include/asm/rsi_smc.h
new file mode 100644
index 000000000000..c0a65caa3ab3
--- /dev/null
+++ b/arch/arm64/include/asm/rsi_smc.h
@@ -0,0 +1,142 @@
+/* SPDX-License-Identifier: GPL-2.0-only */
+/*
+ * Copyright (C) 2023 ARM Ltd.
+ */
+
+#ifndef __SMC_RSI_H_
+#define __SMC_RSI_H_
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
+#endif /* __SMC_RSI_H_ */

---

## [4] Steven Price — 2024-06-05
*Subject: [PATCH v3 02/14] arm64: Detect if in a realm and set RIPAS RAM*

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
 arch/arm64/include/asm/rsi.h      | 48 +++++++++++++++++++++
 arch/arm64/include/asm/rsi_cmds.h | 22 ++++++++++
 arch/arm64/kernel/Makefile        |  3 +-
 arch/arm64/kernel/rsi.c           | 69 +++++++++++++++++++++++++++++++
 arch/arm64/kernel/setup.c         |  8 ++++
 arch/arm64/mm/init.c              |  1 +
 6 files changed, 150 insertions(+), 1 deletion(-)
 create mode 100644 arch/arm64/include/asm/rsi.h
 create mode 100644 arch/arm64/kernel/rsi.c

diff --git a/arch/arm64/include/asm/rsi.h b/arch/arm64/include/asm/rsi.h
new file mode 100644
index 000000000000..ce2cdb501d84
--- /dev/null
+++ b/arch/arm64/include/asm/rsi.h
@@ -0,0 +1,48 @@
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
+				       enum ripas state)
+{
+	unsigned long ret;
+	phys_addr_t top;
+
+	while (start != end) {
+		ret = rsi_set_addr_range_state(start, end, state, &top);
+		if (WARN_ON(ret || top < start || top > end))
+			return -EINVAL;
+		start = top;
+	}
+
+	return 0;
+}
+
+static inline int rsi_set_memory_range_protected(phys_addr_t start,
+						 phys_addr_t end)
+{
+	return rsi_set_memory_range(start, end, RSI_RIPAS_RAM);
+}
+
+static inline int rsi_set_memory_range_shared(phys_addr_t start,
+					      phys_addr_t end)
+{
+	return rsi_set_memory_range(start, end, RSI_RIPAS_EMPTY);
+}
+#endif
diff --git a/arch/arm64/include/asm/rsi_cmds.h b/arch/arm64/include/asm/rsi_cmds.h
index ad425c5d6f1b..ab8ad435f10e 100644
--- a/arch/arm64/include/asm/rsi_cmds.h
+++ b/arch/arm64/include/asm/rsi_cmds.h
@@ -10,6 +10,11 @@
 
 #include <asm/rsi_smc.h>
 
+enum ripas {
+	RSI_RIPAS_EMPTY,
+	RSI_RIPAS_RAM,
+};
+
 static inline void invoke_rsi_fn_smc_with_res(unsigned long function_id,
 					      unsigned long arg0,
 					      unsigned long arg1,
@@ -44,4 +49,21 @@ static inline unsigned long rsi_get_realm_config(struct realm_config *cfg)
 	return res.a0;
 }
 
+static inline unsigned long rsi_set_addr_range_state(phys_addr_t start,
+						     phys_addr_t end,
+						     enum ripas state,
+						     phys_addr_t *top)
+{
+	struct arm_smccc_res res;
+
+	invoke_rsi_fn_smc_with_res(SMC_RSI_IPA_STATE_SET,
+				   start, end, state, RSI_NO_CHANGE_DESTROYED,
+				   &res);
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
index 000000000000..3a992bdfd6bb
--- /dev/null
+++ b/arch/arm64/kernel/rsi.c
@@ -0,0 +1,69 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/*
+ * Copyright (C) 2023 ARM Ltd.
+ */
+
+#include <linux/jump_label.h>
+#include <linux/memblock.h>
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
+	 * Iterate over the available memory ranges
+	 * and convert the state to protected memory.
+	 *
+	 * BUG_ON is used because if the attempt to switch the memory to
+	 * protected has failed here, then future accesses to the memory are
+	 * simply going to be reflected as a fault which we can't handle.
+	 * Bailing out early prevents the guest limping on and dieing later.
+	 */
+	for_each_mem_range(i, &start, &end) {
+		BUG_ON(rsi_set_memory_range_protected(start, end));
+	}
+}
+
+void __init arm64_rsi_init(void)
+{
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
diff --git a/arch/arm64/mm/init.c b/arch/arm64/mm/init.c
index 9b5ab6818f7f..9d8d38e3bee2 100644
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

---

## [5] Steven Price — 2024-06-05
*Subject: [PATCH v3 03/14] arm64: realm: Query IPA size from the RMM*

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
index 3a992bdfd6bb..d34e05b339ae 100644
--- a/arch/arm64/kernel/rsi.c
+++ b/arch/arm64/kernel/rsi.c
@@ -7,6 +7,11 @@
 #include <linux/memblock.h>
 #include <asm/rsi.h>
 
+struct realm_config config;
+
+unsigned long prot_ns_shared;
+EXPORT_SYMBOL(prot_ns_shared);
+
 DEFINE_STATIC_KEY_FALSE_RO(rsi_present);
 EXPORT_SYMBOL(rsi_present);
 
@@ -63,6 +68,9 @@ void __init arm64_rsi_init(void)
 {
 	if (!rsi_version_matches())
 		return;
+	if (rsi_get_realm_config(&config))
+		return;
+	prot_ns_shared = BIT(config.ipa_bits - 1);
 
 	static_branch_enable(&rsi_present);
 }

---

## [6] Steven Price — 2024-06-05
*Subject: [PATCH v3 04/14] arm64: Mark all I/O as non-secure shared*

All I/O is by default considered non-secure for realms. As such
mark them as shared with the host.

Co-developed-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
 arch/arm64/include/asm/io.h | 6 +++---
 1 file changed, 3 insertions(+), 3 deletions(-)

diff --git a/arch/arm64/include/asm/io.h b/arch/arm64/include/asm/io.h
index 4ff0ae3f6d66..0a219c03750b 100644
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

---

## [7] Steven Price — 2024-06-05
*Subject: [PATCH v3 05/14] fixmap: Allow architecture overriding set_fixmap_io*

From: Suzuki K Poulose <suzuki.poulose@arm.com>

For a realm guest it will be necessary to ensure IO mappings are shared
so that the VMM can emulate the device. The following patch will provide
an implementation of set_fixmap_io for arm64 setting the shared bit (if
in a realm).

Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
 include/asm-generic/fixmap.h | 2 ++
 1 file changed, 2 insertions(+)

diff --git a/include/asm-generic/fixmap.h b/include/asm-generic/fixmap.h
index 8cc7b09c1bc7..c5ce0368c1ee 100644
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
 
 #define set_fixmap_offset_io(idx, phys) \
 	__set_fixmap_offset(idx, phys, FIXMAP_PAGE_IO)

---

## [8] Steven Price — 2024-06-05
*Subject: [PATCH v3 06/14] arm64: Override set_fixmap_io*

From: Suzuki K Poulose <suzuki.poulose@arm.com>

Override the set_fixmap_io to set shared permission for the host
in case of a CC guest. For now we mark it shared unconditionally.

If/when support for device assignment and device emulation in the realm
is added in the future then this will need to filter the physical
address and make the decision accordingly.

Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
 arch/arm64/include/asm/fixmap.h |  4 +++-
 arch/arm64/mm/mmu.c             | 13 +++++++++++++
 2 files changed, 16 insertions(+), 1 deletion(-)

diff --git a/arch/arm64/include/asm/fixmap.h b/arch/arm64/include/asm/fixmap.h
index 87e307804b99..f765943b088c 100644
--- a/arch/arm64/include/asm/fixmap.h
+++ b/arch/arm64/include/asm/fixmap.h
@@ -107,7 +107,9 @@ void __init early_fixmap_init(void);
 #define __late_set_fixmap __set_fixmap
 #define __late_clear_fixmap(idx) __set_fixmap((idx), 0, FIXMAP_PAGE_CLEAR)
 
-extern void __set_fixmap(enum fixed_addresses idx, phys_addr_t phys, pgprot_t prot);
+#define set_fixmap_io set_fixmap_io
+void set_fixmap_io(enum fixed_addresses idx, phys_addr_t phys);
+void __set_fixmap(enum fixed_addresses idx, phys_addr_t phys, pgprot_t prot);
 
 #include <asm-generic/fixmap.h>
 
diff --git a/arch/arm64/mm/mmu.c b/arch/arm64/mm/mmu.c
index c927e9312f10..9123df312842 100644
--- a/arch/arm64/mm/mmu.c
+++ b/arch/arm64/mm/mmu.c
@@ -1192,6 +1192,19 @@ void vmemmap_free(unsigned long start, unsigned long end,
 }
 #endif /* CONFIG_MEMORY_HOTPLUG */
 
+void set_fixmap_io(enum fixed_addresses idx, phys_addr_t phys)
+{
+	pgprot_t prot = FIXMAP_PAGE_IO;
+
+	/*
+	 * For now we consider all I/O as non-secure. For future
+	 * filter the I/O base for setting appropriate permissions.
+	 */
+	prot = __pgprot(pgprot_val(prot) | PROT_NS_SHARED);
+
+	return __set_fixmap(idx, phys, prot);
+}
+
 int pud_set_huge(pud_t *pudp, phys_addr_t phys, pgprot_t prot)
 {
 	pud_t new_pud = pfn_pud(__phys_to_pfn(phys), mk_pud_sect_prot(prot));

---

## [9] Steven Price — 2024-06-05
*Subject: [PATCH v3 07/14] arm64: Make the PHYS_MASK_SHIFT dynamic*

Make the PHYS_MASK_SHIFT dynamic for Realms. This is only is required
for masking the PFN from a pte entry. For a realm phys_mask_shift is
reduced if the RMM reports a smaller configured size for the guest.

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
index d34e05b339ae..c5c03e8e341a 100644
--- a/arch/arm64/kernel/rsi.c
+++ b/arch/arm64/kernel/rsi.c
@@ -12,6 +12,8 @@ struct realm_config config;
 unsigned long prot_ns_shared;
 EXPORT_SYMBOL(prot_ns_shared);
 
+unsigned int phys_mask_shift = CONFIG_ARM64_PA_BITS;
+
 DEFINE_STATIC_KEY_FALSE_RO(rsi_present);
 EXPORT_SYMBOL(rsi_present);
 
@@ -72,6 +74,9 @@ void __init arm64_rsi_init(void)
 		return;
 	prot_ns_shared = BIT(config.ipa_bits - 1);
 
+	if (config.ipa_bits - 1 < phys_mask_shift)
+		phys_mask_shift = config.ipa_bits - 1;
+
 	static_branch_enable(&rsi_present);
 }

---

## [10] Steven Price — 2024-06-05
*Subject: [PATCH v3 08/14] arm64: Enforce bounce buffers for realm DMA*

Within a realm guest it's not possible for a device emulated by the VMM
to access arbitrary guest memory. So force the use of bounce buffers to
ensure that the memory the emulated devices are accessing is in memory
which is explicitly shared with the host.

Co-developed-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
v3: Simplify mem_init() by using a 'flags' variable.
---
 arch/arm64/kernel/rsi.c | 2 ++
 arch/arm64/mm/init.c    | 9 ++++++++-
 2 files changed, 10 insertions(+), 1 deletion(-)

diff --git a/arch/arm64/kernel/rsi.c b/arch/arm64/kernel/rsi.c
index c5c03e8e341a..5cb42609219f 100644
--- a/arch/arm64/kernel/rsi.c
+++ b/arch/arm64/kernel/rsi.c
@@ -5,6 +5,8 @@
 
 #include <linux/jump_label.h>
 #include <linux/memblock.h>
+#include <linux/swiotlb.h>
+
 #include <asm/rsi.h>
 
 struct realm_config config;
diff --git a/arch/arm64/mm/init.c b/arch/arm64/mm/init.c
index 9d8d38e3bee2..1d595b63da71 100644
--- a/arch/arm64/mm/init.c
+++ b/arch/arm64/mm/init.c
@@ -370,8 +370,14 @@ void __init bootmem_init(void)
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
@@ -383,7 +389,8 @@ void __init mem_init(void)
 		swiotlb = true;
 	}
 
-	swiotlb_init(swiotlb, SWIOTLB_VERBOSE);
+	swiotlb_init(swiotlb, flags);
+	swiotlb_update_mem_attributes();
 
 	/* this will put all unused low memory onto the freelists */
 	memblock_free_all();

---

## [11] Steven Price — 2024-06-05
*Subject: [PATCH v3 09/14] arm64: Enable memory encrypt for Realms*

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
Changes since v2:
 * Fix location of set_memory_{en,de}crypted() and export them.
 * Break-before-make when changing the top bit of the IPA for
   transitioning to/from shared.
---
 arch/arm64/Kconfig                   |  3 ++
 arch/arm64/include/asm/mem_encrypt.h | 17 ++++++++
 arch/arm64/include/asm/set_memory.h  |  3 ++
 arch/arm64/kernel/rsi.c              | 12 +++++
 arch/arm64/mm/pageattr.c             | 65 ++++++++++++++++++++++++++--
 5 files changed, 97 insertions(+), 3 deletions(-)
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
index 5cb42609219f..898952d135b0 100644
--- a/arch/arm64/kernel/rsi.c
+++ b/arch/arm64/kernel/rsi.c
@@ -6,6 +6,7 @@
 #include <linux/jump_label.h>
 #include <linux/memblock.h>
 #include <linux/swiotlb.h>
+#include <linux/cc_platform.h>
 
 #include <asm/rsi.h>
 
@@ -19,6 +20,17 @@ unsigned int phys_mask_shift = CONFIG_ARM64_PA_BITS;
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
index 0e270a1c51e6..3e7d81696756 100644
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
@@ -192,6 +196,61 @@ int set_direct_map_default_noflush(struct page *page)
 				   PAGE_SIZE, change_page_range, &data);
 }
 
+static int __set_memory_encrypted(unsigned long addr,
+				  int numpages,
+				  bool encrypt)
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
+	return __set_memory_encrypted(addr, numpages, true);
+}
+EXPORT_SYMBOL_GPL(set_memory_encrypted);
+
+int set_memory_decrypted(unsigned long addr, int numpages)
+{
+	return __set_memory_encrypted(addr, numpages, false);
+}
+EXPORT_SYMBOL_GPL(set_memory_decrypted);
+
 #ifdef CONFIG_DEBUG_PAGEALLOC
 void __kernel_map_pages(struct page *page, int numpages, int enable)
 {

---

## [12] Steven Price — 2024-06-05
*Subject: [PATCH v3 10/14] arm64: Force device mappings to be non-secure shared*

From: Suzuki K Poulose <suzuki.poulose@arm.com>

Device mappings (currently) need to be emulated by the VMM so must be
mapped shared with the host.

Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
 arch/arm64/include/asm/pgtable.h | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)

diff --git a/arch/arm64/include/asm/pgtable.h b/arch/arm64/include/asm/pgtable.h
index 11d614d83317..c986fde262c0 100644
--- a/arch/arm64/include/asm/pgtable.h
+++ b/arch/arm64/include/asm/pgtable.h
@@ -644,7 +644,7 @@ static inline void set_pud_at(struct mm_struct *mm, unsigned long addr,
 #define pgprot_writecombine(prot) \
 	__pgprot_modify(prot, PTE_ATTRINDX_MASK, PTE_ATTRINDX(MT_NORMAL_NC) | PTE_PXN | PTE_UXN)
 #define pgprot_device(prot) \
-	__pgprot_modify(prot, PTE_ATTRINDX_MASK, PTE_ATTRINDX(MT_DEVICE_nGnRE) | PTE_PXN | PTE_UXN)
+	__pgprot_modify(prot, PTE_ATTRINDX_MASK, PTE_ATTRINDX(MT_DEVICE_nGnRE) | PTE_PXN | PTE_UXN | PROT_NS_SHARED)
 #define pgprot_tagged(prot) \
 	__pgprot_modify(prot, PTE_ATTRINDX_MASK, PTE_ATTRINDX(MT_NORMAL_TAGGED))
 #define pgprot_mhp	pgprot_tagged

---

## [13] Steven Price — 2024-06-05
*Subject: [PATCH v3 11/14] efi: arm64: Map Device with Prot Shared*

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

## [14] Steven Price — 2024-06-05
*Subject: [PATCH v3 12/14] arm64: realm: Support nonsecure ITS emulation shared*

Within a realm guest the ITS is emulated by the host. This means the
allocations must have been made available to the host by a call to
set_memory_decrypted(). Introduce an allocation function which performs
this extra call.

Co-developed-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v2:
 * Drop 'shared' from the new its_xxx function names as they are used
   for non-realm guests too.
 * Don't handle the NUMA_NO_NODE case specially - alloc_pages_node()
   should do the right thing.
 * Drop a pointless (void *) cast.
---
 drivers/irqchip/irq-gic-v3-its.c | 90 ++++++++++++++++++++++++--------
 1 file changed, 67 insertions(+), 23 deletions(-)

diff --git a/drivers/irqchip/irq-gic-v3-its.c b/drivers/irqchip/irq-gic-v3-its.c
index 40ebf1726393..ca72f830f4cc 100644
--- a/drivers/irqchip/irq-gic-v3-its.c
+++ b/drivers/irqchip/irq-gic-v3-its.c
@@ -18,6 +18,7 @@
 #include <linux/irqdomain.h>
 #include <linux/list.h>
 #include <linux/log2.h>
+#include <linux/mem_encrypt.h>
 #include <linux/memblock.h>
 #include <linux/mm.h>
 #include <linux/msi.h>
@@ -27,6 +28,7 @@
 #include <linux/of_pci.h>
 #include <linux/of_platform.h>
 #include <linux/percpu.h>
+#include <linux/set_memory.h>
 #include <linux/slab.h>
 #include <linux/syscore_ops.h>
 
@@ -163,6 +165,7 @@ struct its_device {
 	struct its_node		*its;
 	struct event_lpi_map	event_map;
 	void			*itt;
+	u32			itt_order;
 	u32			nr_ites;
 	u32			device_id;
 	bool			shared;
@@ -198,6 +201,30 @@ static DEFINE_IDA(its_vpeid_ida);
 #define gic_data_rdist_rd_base()	(gic_data_rdist()->rd_base)
 #define gic_data_rdist_vlpi_base()	(gic_data_rdist_rd_base() + SZ_128K)
 
+static struct page *its_alloc_pages_node(int node, gfp_t gfp,
+					 unsigned int order)
+{
+	struct page *page;
+
+	page = alloc_pages_node(node, gfp, order);
+
+	if (page)
+		set_memory_decrypted((unsigned long)page_address(page),
+				     1 << order);
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
+	set_memory_encrypted((unsigned long)addr, 1 << order);
+	free_pages((unsigned long)addr, order);
+}
+
 /*
  * Skip ITSs that have no vLPIs mapped, unless we're on GICv4.1, as we
  * always have vSGIs mapped.
@@ -2212,7 +2239,8 @@ static struct page *its_allocate_prop_table(gfp_t gfp_flags)
 {
 	struct page *prop_page;
 
-	prop_page = alloc_pages(gfp_flags, get_order(LPI_PROPBASE_SZ));
+	prop_page = its_alloc_pages(gfp_flags,
+				    get_order(LPI_PROPBASE_SZ));
 	if (!prop_page)
 		return NULL;
 
@@ -2223,8 +2251,8 @@ static struct page *its_allocate_prop_table(gfp_t gfp_flags)
 
 static void its_free_prop_table(struct page *prop_page)
 {
-	free_pages((unsigned long)page_address(prop_page),
-		   get_order(LPI_PROPBASE_SZ));
+	its_free_pages(page_address(prop_page),
+		       get_order(LPI_PROPBASE_SZ));
 }
 
 static bool gic_check_reserved_range(phys_addr_t addr, unsigned long size)
@@ -2346,7 +2374,8 @@ static int its_setup_baser(struct its_node *its, struct its_baser *baser,
 		order = get_order(GITS_BASER_PAGES_MAX * psz);
 	}
 
-	page = alloc_pages_node(its->numa_node, GFP_KERNEL | __GFP_ZERO, order);
+	page = its_alloc_pages_node(its->numa_node,
+				    GFP_KERNEL | __GFP_ZERO, order);
 	if (!page)
 		return -ENOMEM;
 
@@ -2359,7 +2388,7 @@ static int its_setup_baser(struct its_node *its, struct its_baser *baser,
 		/* 52bit PA is supported only when PageSize=64K */
 		if (psz != SZ_64K) {
 			pr_err("ITS: no 52bit PA support when psz=%d\n", psz);
-			free_pages((unsigned long)base, order);
+			its_free_pages(base, order);
 			return -ENXIO;
 		}
 
@@ -2415,7 +2444,7 @@ static int its_setup_baser(struct its_node *its, struct its_baser *baser,
 		pr_err("ITS@%pa: %s doesn't stick: %llx %llx\n",
 		       &its->phys_base, its_base_type_string[type],
 		       val, tmp);
-		free_pages((unsigned long)base, order);
+		its_free_pages(base, order);
 		return -ENXIO;
 	}
 
@@ -2554,8 +2583,8 @@ static void its_free_tables(struct its_node *its)
 
 	for (i = 0; i < GITS_BASER_NR_REGS; i++) {
 		if (its->tables[i].base) {
-			free_pages((unsigned long)its->tables[i].base,
-				   its->tables[i].order);
+			its_free_pages(its->tables[i].base,
+				       its->tables[i].order);
 			its->tables[i].base = NULL;
 		}
 	}
@@ -2821,7 +2850,8 @@ static bool allocate_vpe_l2_table(int cpu, u32 id)
 
 	/* Allocate memory for 2nd level table */
 	if (!table[idx]) {
-		page = alloc_pages(GFP_KERNEL | __GFP_ZERO, get_order(psz));
+		page = its_alloc_pages(GFP_KERNEL | __GFP_ZERO,
+				       get_order(psz));
 		if (!page)
 			return false;
 
@@ -2940,7 +2970,8 @@ static int allocate_vpe_l1_table(void)
 
 	pr_debug("np = %d, npg = %lld, psz = %d, epp = %d, esz = %d\n",
 		 np, npg, psz, epp, esz);
-	page = alloc_pages(GFP_ATOMIC | __GFP_ZERO, get_order(np * PAGE_SIZE));
+	page = its_alloc_pages(GFP_ATOMIC | __GFP_ZERO,
+			       get_order(np * PAGE_SIZE));
 	if (!page)
 		return -ENOMEM;
 
@@ -2986,8 +3017,8 @@ static struct page *its_allocate_pending_table(gfp_t gfp_flags)
 {
 	struct page *pend_page;
 
-	pend_page = alloc_pages(gfp_flags | __GFP_ZERO,
-				get_order(LPI_PENDBASE_SZ));
+	pend_page = its_alloc_pages(gfp_flags | __GFP_ZERO,
+				    get_order(LPI_PENDBASE_SZ));
 	if (!pend_page)
 		return NULL;
 
@@ -2999,7 +3030,7 @@ static struct page *its_allocate_pending_table(gfp_t gfp_flags)
 
 static void its_free_pending_table(struct page *pt)
 {
-	free_pages((unsigned long)page_address(pt), get_order(LPI_PENDBASE_SZ));
+	its_free_pages(page_address(pt), get_order(LPI_PENDBASE_SZ));
 }
 
 /*
@@ -3334,8 +3365,9 @@ static bool its_alloc_table_entry(struct its_node *its,
 
 	/* Allocate memory for 2nd level table */
 	if (!table[idx]) {
-		page = alloc_pages_node(its->numa_node, GFP_KERNEL | __GFP_ZERO,
-					get_order(baser->psz));
+		page = its_alloc_pages_node(its->numa_node,
+					    GFP_KERNEL | __GFP_ZERO,
+					    get_order(baser->psz));
 		if (!page)
 			return false;
 
@@ -3418,7 +3450,9 @@ static struct its_device *its_create_device(struct its_node *its, u32 dev_id,
 	unsigned long *lpi_map = NULL;
 	unsigned long flags;
 	u16 *col_map = NULL;
+	struct page *page;
 	void *itt;
+	int itt_order;
 	int lpi_base;
 	int nr_lpis;
 	int nr_ites;
@@ -3430,7 +3464,6 @@ static struct its_device *its_create_device(struct its_node *its, u32 dev_id,
 	if (WARN_ON(!is_power_of_2(nvecs)))
 		nvecs = roundup_pow_of_two(nvecs);
 
-	dev = kzalloc(sizeof(*dev), GFP_KERNEL);
 	/*
 	 * Even if the device wants a single LPI, the ITT must be
 	 * sized as a power of two (and you need at least one bit...).
@@ -3438,7 +3471,16 @@ static struct its_device *its_create_device(struct its_node *its, u32 dev_id,
 	nr_ites = max(2, nvecs);
 	sz = nr_ites * (FIELD_GET(GITS_TYPER_ITT_ENTRY_SIZE, its->typer) + 1);
 	sz = max(sz, ITS_ITT_ALIGN) + ITS_ITT_ALIGN - 1;
-	itt = kzalloc_node(sz, GFP_KERNEL, its->numa_node);
+	itt_order = get_order(sz);
+	page = its_alloc_pages_node(its->numa_node,
+				    GFP_KERNEL | __GFP_ZERO,
+				    itt_order);
+	if (!page)
+		return NULL;
+	itt = page_address(page);
+
+	dev = kzalloc(sizeof(*dev), GFP_KERNEL);
+
 	if (alloc_lpis) {
 		lpi_map = its_lpi_alloc(nvecs, &lpi_base, &nr_lpis);
 		if (lpi_map)
@@ -3450,9 +3492,9 @@ static struct its_device *its_create_device(struct its_node *its, u32 dev_id,
 		lpi_base = 0;
 	}
 
-	if (!dev || !itt ||  !col_map || (!lpi_map && alloc_lpis)) {
+	if (!dev || !col_map || (!lpi_map && alloc_lpis)) {
 		kfree(dev);
-		kfree(itt);
+		its_free_pages(itt, itt_order);
 		bitmap_free(lpi_map);
 		kfree(col_map);
 		return NULL;
@@ -3462,6 +3504,7 @@ static struct its_device *its_create_device(struct its_node *its, u32 dev_id,
 
 	dev->its = its;
 	dev->itt = itt;
+	dev->itt_order = itt_order;
 	dev->nr_ites = nr_ites;
 	dev->event_map.lpi_map = lpi_map;
 	dev->event_map.col_map = col_map;
@@ -3489,7 +3532,7 @@ static void its_free_device(struct its_device *its_dev)
 	list_del(&its_dev->entry);
 	raw_spin_unlock_irqrestore(&its_dev->its->lock, flags);
 	kfree(its_dev->event_map.col_map);
-	kfree(its_dev->itt);
+	its_free_pages(its_dev->itt, its_dev->itt_order);
 	kfree(its_dev);
 }
 
@@ -5131,8 +5174,9 @@ static int __init its_probe_one(struct its_node *its)
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
@@ -5196,7 +5240,7 @@ static int __init its_probe_one(struct its_node *its)
 out_free_tables:
 	its_free_tables(its);
 out_free_cmd:
-	free_pages((unsigned long)its->cmd_base, get_order(ITS_CMD_QUEUE_SZ));
+	its_free_pages(its->cmd_base, get_order(ITS_CMD_QUEUE_SZ));
 out_unmap_sgir:
 	if (its->sgir_base)
 		iounmap(its->sgir_base);

---

## [15] Steven Price — 2024-06-05
*Subject: [PATCH v3 13/14] arm64: rsi: Interfaces to query attestation token*

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
index ab8ad435f10e..ca0ea5929ecc 100644
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
@@ -66,4 +69,75 @@ static inline unsigned long rsi_set_addr_range_state(phys_addr_t start,
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

## [16] Steven Price — 2024-06-05
*Subject: [PATCH v3 14/14] virt: arm-cca-guest: TSM_REPORT support for realms*

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

## [17] Marc Zyngier — 2024-06-05
*Subject: Re: [PATCH v3 12/14] arm64: realm: Support nonsecure ITS emulation shared*

The subject line is... odd. I'd expect something like:

"irqchip/gic-v3-its: Share ITS tables with a non-trusted hypervisor"

because nothing here should be CCA specific.

On Wed, 05 Jun 2024 10:30:04 +0100,
Steven Price <steven.price@arm.com> wrote:
> 
> Within a realm guest the ITS is emulated by the host. This means the

This doesn't mention that this patch radically changes the allocation
of some tables.

> 
> Co-developed-by: Suzuki K Poulose <suzuki.poulose@arm.com>

Please use BIT(order).

> +	return page;
> +}

So we go from an allocation that was so far measured in *bytes* to
something that is now at least a page. Per device. This seems a bit
excessive to me, specially when it isn't conditioned on anything and
is now imposed on all platforms, including the non-CCA systems (which
are exactly 100% of the machines).

Another thing is that if we go with page alignment, then the 256 byte
alignment can obviously be removed everywhere (hint: MAPD needs to
change).

Thanks,

	M.

---

## [18] Steven Price — 2024-06-05
*Subject: Re: [PATCH v3 12/14] arm64: realm: Support nonsecure ITS emulation
 shared*

Hi Marc,

On 05/06/2024 14:39, Marc Zyngier wrote:
> The subject line is... odd. I'd expect something like:
> 

Good point - that's a much better subject.

> On Wed, 05 Jun 2024 10:30:04 +0100,
> Steven Price <steven.price@arm.com> wrote:

I guess that depends on your definition of radical, see below.

>>
>> Co-developed-by: Suzuki K Poulose <suzuki.poulose@arm.com>

Sure.

>> +	return page;
>> +}

Catalin asked about this in v2:
https://lore.kernel.org/lkml/c329ae18-2b61-4851-8d6a-9e691a2007c8@arm.com/

To be honest, I don't have a great handle on how much memory is being
wasted here. Within the realm guest I was testing this is rounding up an
otherwise 511 byte allocation to a 4k page, and there are 3 of them.
Which seems reasonable from a realm guest perspective.

I can see two options to improve here:

1. Add a !is_realm_world() check and return to the previous behaviour
when not running in a realm. It's ugly, and doesn't deal with any other
potential future memory encryption. cc_platform_has(CC_ATTR_MEM_ENCRYPT)
might be preferable? But this means no impact to non-realm guests.

2. Use a special (global) memory allocator that does the
set_memory_decrypted() dance on the pages that it allocates but allows
packing the allocations. I'm not aware of an existing kernel API for
this, so it's potentially quite a bit of code. The benefit is that it
reduces memory consumption in a realm guest, although fragmentation
still means we're likely to see a (small) growth.

Any thoughts on what you think would be best?

> Another thing is that if we go with page alignment, then the 256 byte
> alignment can obviously be removed everywhere (hint: MAPD needs to

Ah, good point - I'll need to look into that, my GIC-foo isn't quite up
to speed on that.

Thanks,

Steve

---

## [19] Steven Price — 2024-06-06

On 05/06/2024 09:37, Itaru Kitayama wrote:
> Hi Steven,
> On Wed, Jun 05, 2024 at 10:29:52AM +0100, Steven Price wrote:

Thanks for testing!

Steve

---

## [20] Marc Zyngier — 2024-06-06
*Subject: Re: [PATCH v3 12/14] arm64: realm: Support nonsecure ITS emulation shared*

On Wed, 05 Jun 2024 16:08:49 +0100,
Steven Price <steven.price@arm.com> wrote:
> 
> Hi Marc,

It's election time, I'm all about making bold statements!

[...]

> >> @@ -3334,8 +3365,9 @@ static bool its_alloc_table_entry(struct its_node *its,
> >>  

And not that reasonable on a smaller system, such as my own router VM
that has a whole lot of devices and very little memory. Not to mention
that while CCA is stuck with 4k pages (duh!), the world is moving
towards larger pages, meaning that this is wasting even more memory.

> 
> I can see two options to improve here:

No, this is way too ugly, and doesn't help with things like pKVM.

> 
> 2. Use a special (global) memory allocator that does the

I would expect that something similar to kmem_cache could be of help,
only with the ability to deal with variable object sizes (in this
case: minimum of 256 bytes, in increments defined by the
implementation, and with a 256 byte alignment).

I don't think the ITS is particularly special here, and we should come
up with something that is generic enough to support sharing of
non-page-sized objects.

Thanks,

	M.

---

## [21] Catalin Marinas — 2024-06-06
*Subject: Re: [PATCH v3 12/14] arm64: realm: Support nonsecure ITS emulation
 shared*

On Thu, Jun 06, 2024 at 11:17:36AM +0100, Marc Zyngier wrote:
> On Wed, 05 Jun 2024 16:08:49 +0100,
> Steven Price <steven.price@arm.com> wrote:

Hmm, that's doable but not that easy to make generic. We'd need a new
class of kmalloc-* caches (e.g. kmalloc-decrypted-*) which use only
decrypted pages together with a GFP_DECRYPTED flag or something to get
the slab allocator to go for these pages and avoid merging with other
caches. It would actually be the page allocator parsing this gfp flag,
probably in post_alloc_hook() to set the page decrypted and re-encrypt
it in free_pages_prepare(). A slight problem here is that free_pages()
doesn't get the gfp flag, so we'd need to store some bit in the page
flags. Maybe the flag is not that bad, do we have something like for
page_to_phys() to give us the high IPA address for decrypted pages?

Similarly if we go for a kmem_cache (or a few for multiple sizes). One
can specify a constructor which could set the memory decrypted but
there's no destructor (and also the constructor is per object, not per
page, so we'd need some refcounting).

Another approach contained within the driver is to use mempool_create()
with our own _alloc_fn/_free_fn that sets the memory decrypted/encrypted
accordingly, though sub-page allocations need additional tracking. Also
that's fairly similar to kmem_cache, fixed size.

Yet another option would be to wire it somehow in the DMA API but the
minimum allocation is already a page size, so we don't gain anything.

What gets somewhat closer to what we need is gen_pool. It can track
different sizes, we just need to populate the chunks as needed. I don't
think this would work as a generic allocator but may be good enough
within the ITS code.

If there's a need for such generic allocations in other parts of the
kernel, my preference would be something around kmalloc caches and a new
GFP flag (first option; subject to the selling it to the mm folk). But
that's more of a separate prototyping effort that may or may not
succeed.

Anyway, we could do some hacking around gen_pool as a temporary solution
(maybe as a set of patches on top of this series to be easier to revert)
and start investigating a proper decrypted page allocator in parallel.
We just need to find a victim that has the page allocator fresh in mind
(Ryan or Alexandru ;)).

---

## [22] Michael Kelley — 2024-06-07
*Subject: RE: [PATCH v3 00/14] arm64: Support for running as a guest in Arm CCA*

From: Steven Price <steven.price@arm.com> Sent: Wednesday, June 5, 2024 2:30 AM
> 
> This series adds support for running Linux in a protected VM under the

In the case of a vmalloc() address, load_unaligned_zeropad() could still
make an access to the underlying pages through the linear address. In
CoCo guests on x86, both the vmalloc PTE and the linear map PTE are
flipped, so the load_unaligned_zeropad() problem can occur only during
the transition between decrypted and encrypted. But even then, the
exception handlers have code to fixup this case and allow everything to
proceed normally.

I haven't looked at the code in your patches, but do you handle that case,
or somehow prevent it?

Thanks,

Michael

---

## [23] Catalin Marinas — 2024-06-07

On Fri, Jun 07, 2024 at 01:38:15AM +0000, Michael Kelley wrote:
> From: Steven Price <steven.price@arm.com> Sent: Wednesday, June 5, 2024 2:30 AM
> > This series adds support for running Linux in a protected VM under the

If we can guarantee that only full a vm_struct area is changed at a
time, the vmap guard page would prevent this issue (not sure we can
though). Otherwise I think we either change the set_memory_*() code to
deal with the other mappings or we handle the exception.

We also have potential user mappings, do we need to do anything about
them?

---

## [24] Steven Price — 2024-06-07
*Subject: Re: [PATCH v3 12/14] arm64: realm: Support nonsecure ITS emulation
 shared*

On 06/06/2024 19:38, Catalin Marinas wrote:
> On Thu, Jun 06, 2024 at 11:17:36AM +0100, Marc Zyngier wrote:
>> On Wed, 05 Jun 2024 16:08:49 +0100,

Thanks for the suggestions Catalin. I had a go at implementing something
with gen_pool - the below (very lightly tested) hack seems to work. This
is on top of the current series.

I *think* it should also be safe to drop the whole alignment part with
this custom allocator, which could actually save memory. But I haven't
quite got my head around that yet.

Steve

----8<-----
diff --git a/drivers/irqchip/irq-gic-v3-its.c b/drivers/irqchip/irq-gic-v3-its.c
index ca72f830f4cc..e78634d4d22c 100644
--- a/drivers/irqchip/irq-gic-v3-its.c
+++ b/drivers/irqchip/irq-gic-v3-its.c
@@ -12,6 +12,7 @@
 #include <linux/crash_dump.h>
 #include <linux/delay.h>
 #include <linux/efi.h>
+#include <linux/genalloc.h>
 #include <linux/interrupt.h>
 #include <linux/iommu.h>
 #include <linux/iopoll.h>
@@ -165,7 +166,7 @@ struct its_device {
 	struct its_node		*its;
 	struct event_lpi_map	event_map;
 	void			*itt;
-	u32			itt_order;
+	u32			itt_sz;
 	u32			nr_ites;
 	u32			device_id;
 	bool			shared;
@@ -225,6 +226,50 @@ static void its_free_pages(void *addr, unsigned int order)
 	free_pages((unsigned long)addr, order);
 }
 
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
+	return (void*)addr;
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
@@ -3450,9 +3495,7 @@ static struct its_device *its_create_device(struct its_node *its, u32 dev_id,
 	unsigned long *lpi_map = NULL;
 	unsigned long flags;
 	u16 *col_map = NULL;
-	struct page *page;
 	void *itt;
-	int itt_order;
 	int lpi_base;
 	int nr_lpis;
 	int nr_ites;
@@ -3471,13 +3514,8 @@ static struct its_device *its_create_device(struct its_node *its, u32 dev_id,
 	nr_ites = max(2, nvecs);
 	sz = nr_ites * (FIELD_GET(GITS_TYPER_ITT_ENTRY_SIZE, its->typer) + 1);
 	sz = max(sz, ITS_ITT_ALIGN) + ITS_ITT_ALIGN - 1;
-	itt_order = get_order(sz);
-	page = its_alloc_pages_node(its->numa_node,
-				    GFP_KERNEL | __GFP_ZERO,
-				    itt_order);
-	if (!page)
-		return NULL;
-	itt = page_address(page);
+
+	itt = itt_alloc_pool(its->numa_node, sz);
 
 	dev = kzalloc(sizeof(*dev), GFP_KERNEL);
 
@@ -3492,9 +3530,9 @@ static struct its_device *its_create_device(struct its_node *its, u32 dev_id,
 		lpi_base = 0;
 	}
 
-	if (!dev || !col_map || (!lpi_map && alloc_lpis)) {
+	if (!dev || !itt || !col_map || (!lpi_map && alloc_lpis)) {
 		kfree(dev);
-		its_free_pages(itt, itt_order);
+		itt_free_pool(itt, sz);
 		bitmap_free(lpi_map);
 		kfree(col_map);
 		return NULL;
@@ -3504,7 +3542,7 @@ static struct its_device *its_create_device(struct its_node *its, u32 dev_id,
 
 	dev->its = its;
 	dev->itt = itt;
-	dev->itt_order = itt_order;
+	dev->itt_sz = sz;
 	dev->nr_ites = nr_ites;
 	dev->event_map.lpi_map = lpi_map;
 	dev->event_map.col_map = col_map;
@@ -3532,7 +3570,7 @@ static void its_free_device(struct its_device *its_dev)
 	list_del(&its_dev->entry);
 	raw_spin_unlock_irqrestore(&its_dev->its->lock, flags);
 	kfree(its_dev->event_map.col_map);
-	its_free_pages(its_dev->itt, its_dev->itt_order);
+	itt_free_pool(its_dev->itt, its_dev->itt_sz);
 	kfree(its_dev);
 }
 
@@ -5722,6 +5760,10 @@ int __init its_init(struct fwnode_handle *handle, struct rdists *rdists,
 	bool has_v4_1 = false;
 	int err;
 
+	itt_pool = gen_pool_create(get_order(ITS_ITT_ALIGN), -1);
+	if (!itt_pool)
+		return -ENOMEM;
+
 	gic_rdists = rdists;
 
 	its_parent = parent_domain;

---

## [25] Michael Kelley — 2024-06-07
*Subject: RE: [PATCH v3 00/14] arm64: Support for running as a guest in Arm CCA*

From: Catalin Marinas <catalin.marinas@arm.com> Sent: Friday, June 7, 2024 8:13 AM
> 
> On Fri, Jun 07, 2024 at 01:38:15AM +0000, Michael Kelley wrote:

I don't think the vmap guard pages help. The vmalloc() memory consists
of individual pages that are scattered throughout the direct map. The stray
reference from load_unaligned_zeropad() will originate in a kmalloc'ed
memory page that precedes one of these scattered individual pages, and
will use a direct map kernel vaddr.  So the guard page in vmalloc space don't
come into play. At least in the Hyper-V use case, an entire vmalloc allocation
*is* flipped as a unit, so the guard pages do prevent a stray reference from
load_unaligned_zeropad() that originates in vmalloc space. At one
point I looked to see if load_unaligned_zeropad() is ever used on vmalloc
addresses.  I think the answer was "no",  making the guard page question
moot, but I'm not sure. :-(

Another thought: The use of load_unaligned_zeropad() is conditional on
CONFIG_DCACHE_WORD_ACCESS. There are #ifdef'ed alternate
implementations that don't use load_unaligned_zeropad() if it is not
enabled. I looked at just disabling it in CoCo VMs, but I don't know the
performance impact. I speculated that the benefits were more noticeable
in processors from a decade or more ago, and perhaps less so now, but
never did any measurements. There was also a snag in that x86-only
code has a usage of load_unaligned_zeropad() without an alternate
implementation, so I never went fully down that path. But arm64 would
probably "just work" if it were disabled.

> 
> We also have potential user mappings, do we need to do anything about

I'm unclear on the scenario here.  Would memory with a user mapping
ever be flipped between decrypted and encrypted while the user mapping
existed?  I don't recall being concerned about user mappings, so maybe
had ruled out that scenario. On x86, flipping between decrypted and
encrypted may effectively change the contents of the memory, so doing
a flip while mapped into user space seems problematic. But maybe I'm
missing something.

Michael

---

## [26] Catalin Marinas — 2024-06-07
*Subject: Re: [PATCH v3 12/14] arm64: realm: Support nonsecure ITS emulation
 shared*

On Fri, Jun 07, 2024 at 04:45:14PM +0100, Steven Price wrote:
> On 06/06/2024 19:38, Catalin Marinas wrote:
> > Anyway, we could do some hacking around gen_pool as a temporary solution

Thanks Steven. It doesn't look too complex and it solves the memory
wasting. We don't actually free the pages from gen_pool but I don't
think it matters much, the memory would get reused if devices are
removed and re-added.

---

## [27] Catalin Marinas — 2024-06-07
*Subject: Re: [PATCH v3 12/14] arm64: realm: Support nonsecure ITS emulation
 shared*

On Thu, Jun 06, 2024 at 07:38:08PM +0100, Catalin Marinas wrote:
> On Thu, Jun 06, 2024 at 11:17:36AM +0100, Marc Zyngier wrote:
> > On Wed, 05 Jun 2024 16:08:49 +0100,

I had a go at this generic approach, Friday afternoon fun. Not tested
with the CCA patches, just my own fake set_memory_*() functionality on
top of 6.10-rc2. I also mindlessly added __GFP_DECRYPTED to the ITS code
following the changes in this patch. I noticed that
allocate_vpe_l2_table() doesn't use shared pages (I either missed it or
it's not needed).

If we want to go this way, I can tidy up the diff below, split it into a
proper series and add what's missing. What I can't tell is how a driver
writer knows when to pass __GFP_DECRYPTED. There's also a theoretical
overlap with __GFP_DMA, it can't handle both. The DMA flag takes
priority currently but I realised it probably needs to be the other way
around, we wouldn't have dma mask restrictions for emulated devices.

--------------------8<----------------------------------
diff --git a/drivers/irqchip/irq-gic-v3-its.c b/drivers/irqchip/irq-gic-v3-its.c
index 40ebf1726393..b6627e839e62 100644
--- a/drivers/irqchip/irq-gic-v3-its.c
+++ b/drivers/irqchip/irq-gic-v3-its.c
@@ -2212,7 +2212,8 @@ static struct page *its_allocate_prop_table(gfp_t gfp_flags)
 {
 	struct page *prop_page;
 
-	prop_page = alloc_pages(gfp_flags, get_order(LPI_PROPBASE_SZ));
+	prop_page = alloc_pages(gfp_flags | __GFP_DECRYPTED,
+				get_order(LPI_PROPBASE_SZ));
 	if (!prop_page)
 		return NULL;
 
@@ -2346,7 +2347,8 @@ static int its_setup_baser(struct its_node *its, struct its_baser *baser,
 		order = get_order(GITS_BASER_PAGES_MAX * psz);
 	}
 
-	page = alloc_pages_node(its->numa_node, GFP_KERNEL | __GFP_ZERO, order);
+	page = alloc_pages_node(its->numa_node, GFP_KERNEL | __GFP_ZERO |
+				__GFP_DECRYPTED, order);
 	if (!page)
 		return -ENOMEM;
 
@@ -2940,7 +2942,8 @@ static int allocate_vpe_l1_table(void)
 
 	pr_debug("np = %d, npg = %lld, psz = %d, epp = %d, esz = %d\n",
 		 np, npg, psz, epp, esz);
-	page = alloc_pages(GFP_ATOMIC | __GFP_ZERO, get_order(np * PAGE_SIZE));
+	page = alloc_pages(GFP_ATOMIC | __GFP_ZERO | __GFP_DECRYPTED,
+			   get_order(np * PAGE_SIZE));
 	if (!page)
 		return -ENOMEM;
 
@@ -2986,7 +2989,7 @@ static struct page *its_allocate_pending_table(gfp_t gfp_flags)
 {
 	struct page *pend_page;
 
-	pend_page = alloc_pages(gfp_flags | __GFP_ZERO,
+	pend_page = alloc_pages(gfp_flags | __GFP_ZERO | __GFP_DECRYPTED,
 				get_order(LPI_PENDBASE_SZ));
 	if (!pend_page)
 		return NULL;
@@ -3334,7 +3337,8 @@ static bool its_alloc_table_entry(struct its_node *its,
 
 	/* Allocate memory for 2nd level table */
 	if (!table[idx]) {
-		page = alloc_pages_node(its->numa_node, GFP_KERNEL | __GFP_ZERO,
+		page = alloc_pages_node(its->numa_node, GFP_KERNEL |
+					__GFP_ZERO | __GFP_DECRYPTED,
 					get_order(baser->psz));
 		if (!page)
 			return false;
@@ -3438,7 +3442,7 @@ static struct its_device *its_create_device(struct its_node *its, u32 dev_id,
 	nr_ites = max(2, nvecs);
 	sz = nr_ites * (FIELD_GET(GITS_TYPER_ITT_ENTRY_SIZE, its->typer) + 1);
 	sz = max(sz, ITS_ITT_ALIGN) + ITS_ITT_ALIGN - 1;
-	itt = kzalloc_node(sz, GFP_KERNEL, its->numa_node);
+	itt = kzalloc_node(sz, GFP_KERNEL | __GFP_DECRYPTED, its->numa_node);
 	if (alloc_lpis) {
 		lpi_map = its_lpi_alloc(nvecs, &lpi_base, &nr_lpis);
 		if (lpi_map)
@@ -5131,8 +5135,8 @@ static int __init its_probe_one(struct its_node *its)
 		}
 	}
 
-	page = alloc_pages_node(its->numa_node, GFP_KERNEL | __GFP_ZERO,
-				get_order(ITS_CMD_QUEUE_SZ));
+	page = alloc_pages_node(its->numa_node, GFP_KERNEL | __GFP_ZERO |
+				__GFP_DECRYPTED, get_order(ITS_CMD_QUEUE_SZ));
 	if (!page) {
 		err = -ENOMEM;
 		goto out_unmap_sgir;
diff --git a/include/linux/gfp_types.h b/include/linux/gfp_types.h
index 313be4ad79fd..573989664639 100644
--- a/include/linux/gfp_types.h
+++ b/include/linux/gfp_types.h
@@ -57,6 +57,9 @@ enum {
 #endif
 #ifdef CONFIG_SLAB_OBJ_EXT
 	___GFP_NO_OBJ_EXT_BIT,
+#endif
+#ifdef CONFIG_ARCH_HAS_MEM_ENCRYPT
+	___GFP_DECRYPTED_BIT,
 #endif
 	___GFP_LAST_BIT
 };
@@ -103,6 +106,11 @@ enum {
 #else
 #define ___GFP_NO_OBJ_EXT       0
 #endif
+#ifdef CONFIG_ARCH_HAS_MEM_ENCRYPT
+#define ___GFP_DECRYPTED	BIT(___GFP_DECRYPTED_BIT)
+#else
+#define ___GFP_DECRYPTED	0
+#endif
 
 /*
  * Physical address zone modifiers (see linux/mmzone.h - low four bits)
@@ -117,6 +125,8 @@ enum {
 #define __GFP_MOVABLE	((__force gfp_t)___GFP_MOVABLE)  /* ZONE_MOVABLE allowed */
 #define GFP_ZONEMASK	(__GFP_DMA|__GFP_HIGHMEM|__GFP_DMA32|__GFP_MOVABLE)
 
+#define __GFP_DECRYPTED	((__force gfp_t)___GFP_DECRYPTED)
+
 /**
  * DOC: Page mobility and placement hints
  *
diff --git a/include/linux/page-flags.h b/include/linux/page-flags.h
index 104078afe0b1..705707052274 100644
--- a/include/linux/page-flags.h
+++ b/include/linux/page-flags.h
@@ -127,6 +127,9 @@ enum pageflags {
 #ifdef CONFIG_MEMORY_FAILURE
 	PG_hwpoison,		/* hardware poisoned page. Don't touch */
 #endif
+#ifdef CONFIG_ARCH_HAS_MEM_ENCRYPT
+	PG_decrypted,
+#endif
 #if defined(CONFIG_PAGE_IDLE_FLAG) && defined(CONFIG_64BIT)
 	PG_young,
 	PG_idle,
@@ -626,6 +629,15 @@ PAGEFLAG_FALSE(HWPoison, hwpoison)
 #define __PG_HWPOISON 0
 #endif
 
+#ifdef CONFIG_ARCH_HAS_MEM_ENCRYPT
+PAGEFLAG(Decrypted, decrypted, PF_HEAD)
+#define __PG_DECRYPTED	(1UL << PG_decrypted)
+#else
+PAGEFLAG_FALSE(Decrypted, decrypted)
+#define __PG_DECRYPTED	0
+#endif
+
+
 #ifdef CONFIG_PAGE_IDLE_FLAG
 #ifdef CONFIG_64BIT
 FOLIO_TEST_FLAG(young, FOLIO_HEAD_PAGE)
diff --git a/include/linux/slab.h b/include/linux/slab.h
index 7247e217e21b..f7a2cf624c35 100644
--- a/include/linux/slab.h
+++ b/include/linux/slab.h
@@ -422,6 +422,9 @@ enum kmalloc_cache_type {
 #endif
 #ifdef CONFIG_MEMCG_KMEM
 	KMALLOC_CGROUP,
+#endif
+#ifdef CONFIG_ARCH_HAS_MEM_ENCRYPT
+	KMALLOC_DECRYPTED,
 #endif
 	NR_KMALLOC_TYPES
 };
@@ -433,7 +436,7 @@ kmalloc_caches[NR_KMALLOC_TYPES][KMALLOC_SHIFT_HIGH + 1];
  * Define gfp bits that should not be set for KMALLOC_NORMAL.
  */
 #define KMALLOC_NOT_NORMAL_BITS					\
-	(__GFP_RECLAIMABLE |					\
+	(__GFP_RECLAIMABLE | __GFP_DECRYPTED |			\
 	(IS_ENABLED(CONFIG_ZONE_DMA)   ? __GFP_DMA : 0) |	\
 	(IS_ENABLED(CONFIG_MEMCG_KMEM) ? __GFP_ACCOUNT : 0))
 
@@ -458,11 +461,14 @@ static __always_inline enum kmalloc_cache_type kmalloc_type(gfp_t flags, unsigne
 	 * At least one of the flags has to be set. Their priorities in
 	 * decreasing order are:
 	 *  1) __GFP_DMA
-	 *  2) __GFP_RECLAIMABLE
-	 *  3) __GFP_ACCOUNT
+	 *  2) __GFP_DECRYPTED
+	 *  3) __GFP_RECLAIMABLE
+	 *  4) __GFP_ACCOUNT
 	 */
 	if (IS_ENABLED(CONFIG_ZONE_DMA) && (flags & __GFP_DMA))
 		return KMALLOC_DMA;
+	if (IS_ENABLED(CONFIG_ARCH_HAS_MEM_ENCRYPT) && (flags & __GFP_DECRYPTED))
+		return KMALLOC_DECRYPTED;
 	if (!IS_ENABLED(CONFIG_MEMCG_KMEM) || (flags & __GFP_RECLAIMABLE))
 		return KMALLOC_RECLAIM;
 	else
diff --git a/include/trace/events/mmflags.h b/include/trace/events/mmflags.h
index e46d6e82765e..a0879155f892 100644
--- a/include/trace/events/mmflags.h
+++ b/include/trace/events/mmflags.h
@@ -83,6 +83,12 @@
 #define IF_HAVE_PG_HWPOISON(_name)
 #endif
 
+#ifdef CONFIG_ARCH_HAS_MEM_ENCRYPT
+#define IF_HAVE_PG_DECRYPTED(_name) ,{1UL << PG_##_name, __stringify(_name)}
+#else
+#define IF_HAVE_PG_DECRYPTED(_name)
+#endif
+
 #if defined(CONFIG_PAGE_IDLE_FLAG) && defined(CONFIG_64BIT)
 #define IF_HAVE_PG_IDLE(_name) ,{1UL << PG_##_name, __stringify(_name)}
 #else
@@ -121,6 +127,7 @@
 IF_HAVE_PG_MLOCK(mlocked)						\
 IF_HAVE_PG_UNCACHED(uncached)						\
 IF_HAVE_PG_HWPOISON(hwpoison)						\
+IF_HAVE_PG_DECRYPTED(decrypted)						\
 IF_HAVE_PG_IDLE(idle)							\
 IF_HAVE_PG_IDLE(young)							\
 IF_HAVE_PG_ARCH_X(arch_2)						\
diff --git a/mm/page_alloc.c b/mm/page_alloc.c
index 2e22ce5675ca..c93ae50ec402 100644
--- a/mm/page_alloc.c
+++ b/mm/page_alloc.c
@@ -47,6 +47,7 @@
 #include <linux/sched/mm.h>
 #include <linux/page_owner.h>
 #include <linux/page_table_check.h>
+#include <linux/set_memory.h>
 #include <linux/memcontrol.h>
 #include <linux/ftrace.h>
 #include <linux/lockdep.h>
@@ -1051,6 +1052,12 @@ __always_inline bool free_pages_prepare(struct page *page,
 		return false;
 	}
 
+	if (unlikely(PageDecrypted(page))) {
+		set_memory_encrypted((unsigned long)page_address(page),
+				     1 << order);
+		ClearPageDecrypted(page);
+	}
+
 	VM_BUG_ON_PAGE(compound && compound_order(page) != order, page);
 
 	/*
@@ -1415,6 +1422,7 @@ inline void post_alloc_hook(struct page *page, unsigned int order,
 	bool init = !want_init_on_free() && want_init_on_alloc(gfp_flags) &&
 			!should_skip_init(gfp_flags);
 	bool zero_tags = init && (gfp_flags & __GFP_ZEROTAGS);
+	bool decrypted = true; //gfp_flags & __GFP_DECRYPTED;
 	int i;
 
 	set_page_private(page, 0);
@@ -1465,6 +1473,12 @@ inline void post_alloc_hook(struct page *page, unsigned int order,
 	if (init)
 		kernel_init_pages(page, 1 << order);
 
+	if (decrypted) {
+		set_memory_decrypted((unsigned long)page_address(page),
+				     1 << order);
+		SetPageDecrypted(page);
+	}
+
 	set_page_owner(page, order, gfp_flags);
 	page_table_check_alloc(page, order);
 	pgalloc_tag_add(page, current, 1 << order);
diff --git a/mm/slab_common.c b/mm/slab_common.c
index 1560a1546bb1..de9c8c674aa1 100644
--- a/mm/slab_common.c
+++ b/mm/slab_common.c
@@ -737,6 +737,12 @@ EXPORT_SYMBOL(kmalloc_size_roundup);
 #define KMALLOC_RCL_NAME(sz)
 #endif
 
+#ifdef CONFIG_ARCH_HAS_MEM_ENCRYPT
+#define KMALLOC_DECRYPTED_NAME(sz)	.name[KMALLOC_DECRYPTED] = "kmalloc-decrypted-" #sz,
+#else
+#define KMALLOC_DECRYPTED_NAME(sz)
+#endif
+
 #ifdef CONFIG_RANDOM_KMALLOC_CACHES
 #define __KMALLOC_RANDOM_CONCAT(a, b) a ## b
 #define KMALLOC_RANDOM_NAME(N, sz) __KMALLOC_RANDOM_CONCAT(KMA_RAND_, N)(sz)
@@ -765,6 +771,7 @@ EXPORT_SYMBOL(kmalloc_size_roundup);
 	KMALLOC_RCL_NAME(__short_size)				\
 	KMALLOC_CGROUP_NAME(__short_size)			\
 	KMALLOC_DMA_NAME(__short_size)				\
+	KMALLOC_DECRYPTED_NAME(__short_size)			\
 	KMALLOC_RANDOM_NAME(RANDOM_KMALLOC_CACHES_NR, __short_size)	\
 	.size = __size,						\
 }
@@ -889,6 +896,9 @@ new_kmalloc_cache(int idx, enum kmalloc_cache_type type)
 	if (IS_ENABLED(CONFIG_MEMCG_KMEM) && (type == KMALLOC_NORMAL))
 		flags |= SLAB_NO_MERGE;
 
+	if (IS_ENABLED(CONFIG_ARCH_HAS_MEM_ENCRYPT) && (type == KMALLOC_DECRYPTED))
+		flags |= SLAB_NO_MERGE;
+
 	if (minalign > ARCH_KMALLOC_MINALIGN) {
 		aligned_size = ALIGN(aligned_size, minalign);
 		aligned_idx = __kmalloc_index(aligned_size, false);

---

## [28] Catalin Marinas — 2024-06-10

On Fri, Jun 07, 2024 at 04:36:18PM +0000, Michael Kelley wrote:
> From: Catalin Marinas <catalin.marinas@arm.com> Sent: Friday, June 7, 2024 8:13 AM
> > On Fri, Jun 07, 2024 at 01:38:15AM +0000, Michael Kelley wrote:

My point was about load_unaligned_zeropad() originating in the vmalloc
space. What I had in mind is changing the underlying linear map via
set_memory_*() while we have live vmalloc() mappings. But I forgot about
the case you mentioned in a previous thread: set_memory_*() being called
on vmalloc()'ed memory directly:

https://lore.kernel.org/r/SN6PR02MB41578D7BFEDE33BD2E8246EFD4E92@SN6PR02MB4157.namprd02.prod.outlook.com/

I wonder whether something like __GFP_DECRYPTED could be used to get
shared memory from the allocation time and avoid having to change the
vmalloc() ranges. This way functions like netvsc_init_buf() would get
decrypted memory from the start and vmbus_establish_gpadl() would not
need to call set_memory_decrypted() on a vmalloc() address.

> Another thought: The use of load_unaligned_zeropad() is conditional on
> CONFIG_DCACHE_WORD_ACCESS. There are #ifdef'ed alternate

We shouldn't penalise the performance, especially as I expect a single
image to run both as a guest or a host. However, I think now the linear
map is handled correctly since we make the PTE invalid before making the
page shared and this would force the fault path through the one that
safely handles load_unaligned_zeropad(). Steven's patches also currently
reject non-linear-map addresses, I guess this would be a separate
addition.

> > We also have potential user mappings, do we need to do anything about
> > them?

Maybe it doesn't matter. Do we expect it the underlying pages to be
flipped while live mappings other than the linear map exist? I assume
not, one would first allocate and configure the memory in the kernel
before some remap_pfn_range() to user with the appropriate pgprot.

---

## [29] Catalin Marinas — 2024-06-10
*Subject: Re: [PATCH v3 02/14] arm64: Detect if in a realm and set RIPAS RAM*

On Wed, Jun 05, 2024 at 10:29:54AM +0100, Steven Price wrote:
> diff --git a/arch/arm64/mm/init.c b/arch/arm64/mm/init.c
> index 9b5ab6818f7f..9d8d38e3bee2 100644

What's this random include here? It looks like a leftover from the
previous version.

---

## [30] Catalin Marinas — 2024-06-10
*Subject: Re: [PATCH v3 01/14] arm64: rsi: Add RSI definitions*

On Wed, Jun 05, 2024 at 10:29:53AM +0100, Steven Price wrote:
> --- /dev/null
> +++ b/arch/arm64/include/asm/rsi_cmds.h
[...]
> --- /dev/null
> +++ b/arch/arm64/include/asm/rsi_smc.h

A small nitpick if you respin some patches - please make the header
guards consistent. We tend to to use the top variant above, so the
rsi_smc.h would be __ASM_RSI_SMC_H. The same throughout this series.

---

## [31] Steven Price — 2024-06-10
*Subject: Re: [PATCH v3 02/14] arm64: Detect if in a realm and set RIPAS RAM*

On 10/06/2024 15:11, Catalin Marinas wrote:
> On Wed, Jun 05, 2024 at 10:29:54AM +0100, Steven Price wrote:
>> diff --git a/arch/arm64/mm/init.c b/arch/arm64/mm/init.c

Whoops - indeed that shouldn't be there.

Thanks,
Steve

---

## [32] Michael Kelley — 2024-06-10
*Subject: RE: [PATCH v3 00/14] arm64: Support for running as a guest in Arm CCA*

From: Catalin Marinas <catalin.marinas@arm.com> Sent: Monday, June 10, 2024 3:34 AM
> 
> On Fri, Jun 07, 2024 at 04:36:18PM +0000, Michael Kelley wrote:

OK, right.  You and I were thinking about different cases.

> I wonder whether something like __GFP_DECRYPTED could be used to get
> shared memory from the allocation time and avoid having to change the

I would not have any conceptual objections to such an approach. But I'm
certainly not an expert in that area so I'm not sure what it would take
to make that work for vmalloc(). I presume that __GFP_DECRYPTED
should also work for kmalloc()?

I've seen the separate discussion about a designated pool of decrypted
memory, to avoid always allocating a new page and decrypting when a
smaller allocation is sufficient. If such a pool could also work for page size
or larger allocations, it would have the additional benefit of concentrating
decrypted allocations in fewer 2 Meg large pages vs. scattering wherever
and forcing the break-up of more large page mappings in the direct map.

I'll note that netvsc devices can be added or removed from a running VM.
The vmalloc() memory allocated by netvsc_init_buf() can be freed, and/or
additional calls to netvsc_init_buf() can be made at any time -- they aren't
limited to initial Linux boot.  So the mechanism for getting decrypted
memory at allocation time must be reasonably dynamic.

> 
> > Another thought: The use of load_unaligned_zeropad() is conditional on

Rejecting vmalloc() addresses may work for the moment -- I don't know
when CCA guests might be tried on Hyper-V.  The original SEV-SNP and TDX
work started that way as well. :-) Handling the vmalloc() case was added
later, though I think on x86 the machinery to also flip all the alias PTEs was
already mostly or completely in place, probably for other reasons. So
fixing the vmalloc() case was more about not assuming that the underlying
physical address range is contiguous. Instead, each page must be processed
independently, which was straightforward.

> 
> > > We also have potential user mappings, do we need to do anything about

Yes, for user space mappings I also assume not.

Michael

---

## [33] Catalin Marinas — 2024-06-10
*Subject: Re: [PATCH v3 09/14] arm64: Enable memory encrypt for Realms*

On Wed, Jun 05, 2024 at 10:30:01AM +0100, Steven Price wrote:
> +static int __set_memory_encrypted(unsigned long addr,
> +				  int numpages,

This works, does break-before-make and also rejects vmalloc() ranges
(for the time being).

One particular aspect I don't like is doing the TLBI twice. It's
sufficient to do it when you first make the pte invalid. We could guess
this in __change_memory_common() if set_mask has PTE_VALID. The call
sites are restricted to this file, just add a comment. An alternative
would be to add a bool flush argument to this function.

---

## [34] Catalin Marinas — 2024-06-10

On Mon, Jun 10, 2024 at 05:03:44PM +0000, Michael Kelley wrote:
> From: Catalin Marinas <catalin.marinas@arm.com> Sent: Monday, June 10, 2024 3:34 AM
> > I wonder whether something like __GFP_DECRYPTED could be used to get

Yeah, my quick, not fully tested hack here:

https://lore.kernel.org/linux-arm-kernel/ZmNJdSxSz-sYpVgI@arm.com/

It's the underlying page allocator that gives back decrypted pages when
the flag is passed, so it should work for alloc_pages() and friends. The
kmalloc() changes only ensure that we have separate caches for this
memory and they are not merged. It needs some more work on kmem_cache,
maybe introducing a SLAB_DECRYPTED flag as well as not to rely on the
GFP flag.

For vmalloc(), we'd need a pgprot_decrypted() macro to ensure the
decrypted pages are marked with the appropriate attributes (arch
specific), otherwise it's fairly easy to wire up if alloc_pages() gives
back decrypted memory.

> I'll note that netvsc devices can be added or removed from a running VM.
> The vmalloc() memory allocated by netvsc_init_buf() can be freed, and/or

I think the above should work. But, of course, we'd have to get this
past the mm maintainers, it's likely that I missed something.

> Rejecting vmalloc() addresses may work for the moment -- I don't know
> when CCA guests might be tried on Hyper-V.  The original SEV-SNP and TDX

There may be a slight performance impact but I guess that's not on a
critical path. Walking the page tables and changing the vmalloc ptes
should be fine but for each page, we'd have to break the linear map,
flush the TLBs, re-create the linear map. Those TLBs may become a
bottleneck, especially on hardware with lots of CPUs and the
microarchitecture. Note that even with a __GFP_DECRYPTED attribute, we'd
still need to go for individual pages in the linear map.

---

## [35] Catalin Marinas — 2024-06-10
*Subject: Re: [PATCH v3 06/14] arm64: Override set_fixmap_io*

On Wed, Jun 05, 2024 at 10:29:58AM +0100, Steven Price wrote:
> +void set_fixmap_io(enum fixed_addresses idx, phys_addr_t phys)
> +{

In v2, Suzuki said that we want to keep this as a function rather than
just adding PROT_NS_SHARED to FIXMAP_PAGE_IO in case we want to change
this function in the future to allow protected MMIO.

https://lore.kernel.org/linux-arm-kernel/6ba1fd72-3bad-44ca-810d-572b70050772@arm.com/

What I don't understand is that all the other MMIO cases just statically
assume unprotected/shard MMIO. Should we drop this patch here as well,
adjust FIXMAP_PAGE_IO and think about protected MMIO later when we
actually have to do device assignment?

---

## [36] Jean-Philippe Brucker — 2024-06-12
*Subject: Re: [PATCH v3 02/14] arm64: Detect if in a realm and set RIPAS RAM*

On Wed, Jun 05, 2024 at 10:29:54AM +0100, Steven Price wrote:
> From: Suzuki K Poulose <suzuki.poulose@arm.com>
> 

> +static bool rsi_version_matches(void)
> +{

There is a regression on QEMU TCG (in emulation mode, not running under KVM):

  qemu-system-aarch64 -M virt -cpu max -kernel Image -nographic

This doesn't implement EL3 or EL2, so SMC is UNDEFINED (DDI0487J.a R_HMXQS),
and we end up with an undef instruction exception. So this patch would
also break hardware that only implements EL1 (I don't know if it exists).

The easiest fix is to detect the SMC conduit through the PSCI node in DT.
SMCCC helpers already do this, but we can't use them this early in the
boot. I tested adding an early probe to the PSCI driver to check this, see
attached patches.

Note that we do need to test the conduit after finding a PSCI node,
because even though it doesn't implement EL2 in this configuration, QEMU
still accepts PSCI HVCs in order to support SMP.

Thanks,
Jean


From 788bfd45e7ce521666a19dba99277106e4d33c80 Mon Sep 17 00:00:00 2001
From: Jean-Philippe Brucker <jean-philippe@linaro.org>
Date: Tue, 11 Jun 2024 19:15:30 +0100
Subject: [PATCH 1/2] firmware/psci: Add psci_early_test_conduit()

Add a function to test early if PSCI is present and what conduit it
uses. Because the PSCI conduit corresponds to the SMCCC one, this will
let the kernel know whether it can use SMC instructions to discuss with
the Realm Management Monitor (RMM), early enough to enable RAM and
serial access when running in a Realm.

Signed-off-by: Jean-Philippe Brucker <jean-philippe@linaro.org>
---
 include/linux/psci.h         |  5 +++++
 drivers/firmware/psci/psci.c | 25 +++++++++++++++++++++++++
 2 files changed, 30 insertions(+)

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

---

## [37] Suzuki K Poulose — 2024-06-12
*Subject: Re: [PATCH v3 02/14] arm64: Detect if in a realm and set RIPAS RAM*

On 12/06/2024 11:40, Jean-Philippe Brucker wrote:
> On Wed, Jun 05, 2024 at 10:29:54AM +0100, Steven Price wrote:
>> From: Suzuki K Poulose <suzuki.poulose@arm.com>

Thanks for the report,  Could we not check ID_AA64PFR0_EL1.EL3 >= 0 ? I
think we do this for kvm-unit-tests, we need the same here.


Suzuki

> 
> The easiest fix is to detect the SMC conduit through the PSCI node in DT.

---

## [38] Jean-Philippe Brucker — 2024-06-13
*Subject: Re: [PATCH v3 02/14] arm64: Detect if in a realm and set RIPAS RAM*

On Wed, Jun 12, 2024 at 11:59:22AM +0100, Suzuki K Poulose wrote:
> On 12/06/2024 11:40, Jean-Philippe Brucker wrote:
> > On Wed, Jun 05, 2024 at 10:29:54AM +0100, Steven Price wrote:

Good point, it also fixes this case and is simpler. It assumes RMM doesn't
hide this field, but I can't think of a reason it would.

This command won't work anymore:

  qemu-system-aarch64 -M virt,secure=on -cpu max -kernel Image -nographic

implements EL3 and SMC still treated as undef. QEMU has a special case for
starting at EL2 in this case, but I couldn't find what this is for.

Treating SMC as undef is correct because SCR_EL3.SMD resets to an
architectutally UNKNOWN value. But the architecture requires that the CPU
resets to the highest implemented exception level (DDI0487J.a R_JYLQV). So
in my opinion we can use the ID_AA64PFR0_EL1.EL3 field here, and breaking
this particular configuration is not a problem: users shouldn't expect
Linux to boot when EL3 is implemented and doesn't run a firmware.

Thanks,
Jean

> 
>

---

## [39] Suzuki K Poulose — 2024-06-14
*Subject: Re: [PATCH v3 02/14] arm64: Detect if in a realm and set RIPAS RAM*

Hi Steven

On 05/06/2024 10:29, Steven Price wrote:
> From: Suzuki K Poulose <suzuki.poulose@arm.com>
> 

Though this is fine from the KVM as NS Host perspective, it may be 
unnecessarily restrictive in general for a Host implementation. We only
need that RSI_NO_CHANGE_DESTROYED flag for "init all DRAM range as RAM"
(where we want to prevent a host from "destroying pages" that were
populated before activation, without consent). But in all other cases
where we do not rely on the content of the "newly" encrypted page,
we could drop the flag.

I think we need could have variants of this helper one which allows 
"DESTROYED" granules to be converted, which must be only used while 
"transitioning" a page to encrypted, where we don't rely on the contents 
of the page.

Something like :

rsi_set_memory_range_protected_safe() : Do not allow DESTROYED contents 
to be converted.

rsi_set_memory_range_protected().

Something like:

---8>---

diff --git a/arch/arm64/include/asm/rsi.h b/arch/arm64/include/asm/rsi.h
index ce2cdb501d84..dea2ed99f6d1 100644
--- a/arch/arm64/include/asm/rsi.h
+++ b/arch/arm64/include/asm/rsi.h
@@ -19,13 +19,13 @@ static inline bool is_realm_world(void)
  }

  static inline int rsi_set_memory_range(phys_addr_t start, phys_addr_t end,
-				       enum ripas state)
+				       enum ripas state, unsigned long flags)
  {
  	unsigned long ret;
  	phys_addr_t top;

  	while (start != end) {
-		ret = rsi_set_addr_range_state(start, end, state, &top);
+		ret = rsi_set_addr_range_state(start, end, state, flags, &top);
  		if (WARN_ON(ret || top < start || top > end))
  			return -EINVAL;
  		start = top;
@@ -34,15 +34,29 @@ static inline int rsi_set_memory_range(phys_addr_t 
start, phys_addr_t end,
  	return 0;
  }

+/*
+ * Convert the specified range to RAM. Do not use this if you rely on 
the contents
+ * of a page that may already be in RAM state.
+ */
  static inline int rsi_set_memory_range_protected(phys_addr_t start,
  						 phys_addr_t end)
  {
-	return rsi_set_memory_range(start, end, RSI_RIPAS_RAM);
+	return rsi_set_memory_range(start, end, RSI_RIPAS_RAM, 0);
+}
+
+/*
+ * Convert the specified range to RAM. Do not convert any pages that 
may have
+ * been DESTROYED, without our permission.
+ */
+static inline int rsi_set_memory_range_protected_safe(phys_addr_t start,
+						      phys_addr_t end)
+{
+	return rsi_set_memory_range(start, end, RSI_RIPAS_RAM, 
RSI_NO_CHANGE_DESTROYED);
  }

  static inline int rsi_set_memory_range_shared(phys_addr_t start,
  					      phys_addr_t end)
  {
-	return rsi_set_memory_range(start, end, RSI_RIPAS_EMPTY);
+	return rsi_set_memory_range(start, end, RSI_RIPAS_EMPTY, 0);
  }
  #endif
diff --git a/arch/arm64/include/asm/rsi_cmds.h 
b/arch/arm64/include/asm/rsi_cmds.h
index ab8ad435f10e..466615ff90de 100644
--- a/arch/arm64/include/asm/rsi_cmds.h
+++ b/arch/arm64/include/asm/rsi_cmds.h
@@ -52,12 +52,13 @@ static inline unsigned long 
rsi_get_realm_config(struct realm_config *cfg)
  static inline unsigned long rsi_set_addr_range_state(phys_addr_t start,
  						     phys_addr_t end,
  						     enum ripas state,
+						     unsigned long flags,
  						     phys_addr_t *top)
  {
  	struct arm_smccc_res res;

  	invoke_rsi_fn_smc_with_res(SMC_RSI_IPA_STATE_SET,
-				   start, end, state, RSI_NO_CHANGE_DESTROYED,
+				   start, end, state, flags,
  				   &res);

  	if (top)
diff --git a/arch/arm64/kernel/rsi.c b/arch/arm64/kernel/rsi.c
index 3a992bdfd6bb..e6a6681524a0 100644
--- a/arch/arm64/kernel/rsi.c
+++ b/arch/arm64/kernel/rsi.c
@@ -46,8 +46,9 @@ void __init arm64_rsi_setup_memory(void)
  		return;

  	/*
-	 * Iterate over the available memory ranges
-	 * and convert the state to protected memory.
+	 * Iterate over the available memory ranges and convert the state to
+	 * protected memory. We should take extra care to ensure that we DO NOT
+	 * permit any "DESTROYED" pages to be converted to "RAM".
  	 *
  	 * BUG_ON is used because if the attempt to switch the memory to
  	 * protected has failed here, then future accesses to the memory are
@@ -55,7 +56,7 @@ void __init arm64_rsi_setup_memory(void)
  	 * Bailing out early prevents the guest limping on and dieing later.
  	 */
  	for_each_mem_range(i, &start, &end) {
-		BUG_ON(rsi_set_memory_range_protected(start, end));
+		BUG_ON(rsi_set_memory_range_protected_safe(start, end));
  	}
  }



Kind regards


Suzuki


> +				   &res);
> +

---

## [40] Michael Kelley — 2024-06-17
*Subject: RE: [PATCH v3 10/14] arm64: Force device mappings to be non-secure
 shared*

From: Steven Price <steven.price@arm.com> Sent: Wednesday, June 5, 2024 2:30 AM
> 
> From: Suzuki K Poulose <suzuki.poulose@arm.com>

In v2 of the patches, Catalin raised a question about the need for
pgprot_decrypted(). What was concluded? It still looks to me like
pgprot_decrypted() and prot_encrypted() are needed, by
dma_direct_mmap() and remap_oldmem_pfn_range(), respectively.
Also, assuming Hyper-V supports CCA at some point, the Linux guest
drivers for Hyper-V need pgprot_decrypted() in hv_ringbuffer_init().

Michael

---

## [41] Michael Kelley — 2024-06-17
*Subject: RE: [PATCH v3 12/14] arm64: realm: Support nonsecure ITS emulation
 shared*

From: Steven Price <steven.price@arm.com> Sent: Wednesday, June 5, 2024 2:30 AM
> 
> Within a realm guest the ITS is emulated by the host. This means the

There's been considerable discussion on the x86 side about
what to do when set_memory_decrypted() or set_memory_encrypted()
fails. The conclusions are:

1) set_memory_decrypted()/encrypted() *could* fail due to a
compromised/malicious host, due to a bug somewhere in the
software stack, or due to resource constraints (x86 might need to
split a large page mapping, and need to allocate additional page
table pages, which could fail).

2) The guest memory that was the target of such a failed call could
be left in an indeterminate state that the guest could not reliably
undo or correct. The guest's view of the page's decrypted/encrypted
state might not match the host's view. Therefore, any such guest
memory must be leaked rather than being used or put back on the
free list.

3) After some discussion, we decided not to panic in such a case.
Instead, set_memory_decrypted()/encrypted() generates a WARN,
as well as returns a failure result. The most security conscious
users could set panic_on_warn=1 in their VMs, and thereby stop
further operation if there any indication that the transition between
encrypted and decrypt is suspect. The caller of these functions
also can take explicit action in the case of a failure.

It seems like the same guidelines should apply here. On the x86
side we've also cleaned up cases where the return value isn't
checked, like here and the use of set_memory_encrypted() below.

Michael

> +	return page;
> +}

---

## [42] Michael Kelley — 2024-06-17
*Subject: RE: [PATCH v3 00/14] arm64: Support for running as a guest in Arm CCA*

From: Catalin Marinas <catalin.marinas@arm.com> Sent: Monday, June 10, 2024 10:46 AM
> 
> On Mon, Jun 10, 2024 at 05:03:44PM +0000, Michael Kelley wrote:

Having thought about this a few days, I like the model of telling the
memory allocators to decrypt/re-encrypt the memory, instead of the
caller having to explicitly do set_memory_decrypted()/encrypted().
I'll add some further comments to the thread with your initial
implementation.

> 
> > Rejecting vmalloc() addresses may work for the moment -- I don't know

Agreed. While synthetic devices can come-and-go anytime, it's pretty
rare in the grand scheme of things. I guess we would have to try it on
a system with high CPU count, but even if the code needed to "pace
itself" to avoid hammering the TLBs too hard, that would be OK.

Michael

---

## [43] Peter Maydell — 2024-06-17
*Subject: Re: [PATCH v3 02/14] arm64: Detect if in a realm and set RIPAS RAM*

On Thu, 13 Jun 2024 at 11:50, Jean-Philippe Brucker
<jean-philippe@linaro.org> wrote:
>
> On Wed, Jun 12, 2024 at 11:59:22AM +0100, Suzuki K Poulose wrote:

That's a bit of an odd config, because it says "emulate EL3 but
never use it". QEMU's boot loader starts the kernel at EL2 because
the kernel boot protocol requires that (this is more relevant on
boards other than virt where EL3 is not command-line disableable).
I have a feeling we've occasionally found that somebody's had some
corner case reason to use it, though. (eg
https://gitlab.com/qemu-project/qemu/-/issues/1899
is from somebody who says they use this when booting Windows 11 because
it asserts at boot time that EL3 is present and won't boot otherwise.)

Your underlying problem here seems to be that you don't have
a way for the firmware to say "hey, SMC works, you can use it" ?

-- PMM

---

## [44] Jean-Philippe Brucker — 2024-06-17
*Subject: Re: [PATCH v3 02/14] arm64: Detect if in a realm and set RIPAS RAM*

On Mon, Jun 17, 2024 at 11:27:31AM +0100, Peter Maydell wrote:
> On Thu, 13 Jun 2024 at 11:50, Jean-Philippe Brucker
> <jean-philippe@linaro.org> wrote:

Thanks for the pointer. In this case it looks like Linux was used as
reproducer and not the main use-case, though I wonder if some CIs
regularly boot this particular configuration.

> 
> Your underlying problem here seems to be that you don't have

We do: SMCCC recommends to look at the PSCI conduit declared in DT/ACPI.
Given that RMM mandates using the SMC conduit for both PSCI and RSI calls,
we could use this discovery mechanism here. The problem is that we have to
discover it very early at boot, before the DT infrastructure is ready,
so the implementation is a little awkward. I did post one earlier in this
thread but it doesn't yet account for ACPI-only boot, which will need
something similar. Testing ID_AA64PFR0_EL1.EL3 would be much simpler, but
it would break this config.

Thanks,
Jean

---

## [45] Suzuki K Poulose — 2024-06-17
*Subject: Re: [PATCH v3 10/14] arm64: Force device mappings to be non-secure
 shared*

On 17/06/2024 04:33, Michael Kelley wrote:
> From: Steven Price <steven.price@arm.com> Sent: Wednesday, June 5, 2024 2:30 AM
>>

Right, I think we could simply do :

diff --git a/arch/arm64/include/asm/pgtable.h 
b/arch/arm64/include/asm/pgtable.h
index c986fde262c0..1ed45893d1e6 100644
--- a/arch/arm64/include/asm/pgtable.h
+++ b/arch/arm64/include/asm/pgtable.h
@@ -648,6 +648,10 @@ static inline void set_pud_at(struct mm_struct *mm, 
unsigned long addr,
  #define pgprot_tagged(prot) \
         __pgprot_modify(prot, PTE_ATTRINDX_MASK, 
PTE_ATTRINDX(MT_NORMAL_TAGGED))
  #define pgprot_mhp     pgprot_tagged
+
+#define pgprot_decrypted(prot) __pgprot_modify(prot, PROT_NS_SHARED, 
PROT_NS_SHARED)
+#define pgprot_encrypted(prot)  __pgprot_modify(prot, PROT_NS_SHARED, 0)
+


Suzuki

---

## [46] Catalin Marinas — 2024-06-17
*Subject: Re: [PATCH v3 10/14] arm64: Force device mappings to be non-secure
 shared*

On Mon, Jun 17, 2024 at 03:55:22PM +0100, Suzuki K Poulose wrote:
> On 17/06/2024 04:33, Michael Kelley wrote:
> > From: Steven Price <steven.price@arm.com> Sent: Wednesday, June 5, 2024 2:30 AM

And maybe rewrite pgprot_device() as:

#define __pgprot_device(prot) \
	__pgprot_modify(prot, PTE_ATTRINDX_MASK, PTE_ATTRINDX(MT_DEVICE_nGnRE) | PTE_PXN | PTE_UXN)
#define pgprot_device(prot)	__pgprot_device(pgprot_decrypted(prot))

---

## [47] Michael Kelley — 2024-06-17
*Subject: RE: [PATCH v3 10/14] arm64: Force device mappings to be non-secure
 shared*

From: Suzuki K Poulose <suzuki.poulose@arm.com> Sent: Monday, June 17, 2024 7:55 AM
> 
> On 17/06/2024 04:33, Michael Kelley wrote:

Yes, looks right to me.

Michael

---

## [48] Michael Kelley — 2024-06-18
*Subject: RE: [PATCH v3 12/14] arm64: realm: Support nonsecure ITS emulation
 shared*

From: Catalin Marinas <catalin.marinas@arm.com> Sent: Friday, June 7, 2024 10:55 AM
> 
> On Thu, Jun 06, 2024 at 07:38:08PM +0100, Catalin Marinas wrote:

As someone who has spent time in Linux code on the x86 side that
manages memory shared between the guest and host, a GFP_DECRYPTED
flag on the memory allocation calls seems very useful. Here are my
general comments, some of which are probably obvious, but I thought
I'd write them down anyway.

1)  The impetus in this case is to efficiently allow sub-page allocations.
But on x86, there's also an issue in that the x86 direct map uses large
page mappings, which must be split if any 4K page in the large page
is decrypted. Ideally, we could cluster such decrypted pages into the
same large page(s) vs. just grabbing any 4K page, and reduce the
number of splits. I haven't looked at how feasible that is to implement
in the context of the existing allocator code, so this is aspirational.

2) GFP_DECRYPTED should work for the three memory allocation
interfaces and their variants: alloc_pages(), kmalloc(), and vmalloc().

3) The current paradigm is to allocate memory and call
set_memory_decrypted(). Then do the reverse when freeing memory.
Using GFP_DECRYPTED on the allocation, and having the re-encryption
done automatically when freeing certainly simplifies the call sites.
The error handling at the call sites is additional messiness that gets
much simpler.

4) GFP_DECRYPTED should be silently ignored when not running
in a CoCo VM. Drivers that need decrypted memory in a CoCo VM
always set this flag, and work normally as if the flag isn't set when
not in a CoCo VM. This is how set_memory_decrypted()/encrypted()
work today. Drivers call them in all cases, and they are no-ops
when not in a CoCo VM.

5) The implementation of GFP_DECRYPTED must correctly handle
errors from set_memory_decrypted()/encrypted() as I've described
separately on this thread.

Michael

> 
> --------------------8<----------------------------------

---

## [49] Catalin Marinas — 2024-06-21
*Subject: Re: [PATCH v3 09/14] arm64: Enable memory encrypt for Realms*

On Wed, Jun 05, 2024 at 10:30:01AM +0100, Steven Price wrote:
> +static int __set_memory_encrypted(unsigned long addr,
> +				  int numpages,

While reading Michael's replies, it occurred to me that we need check
the error paths. Here for example we ignore the return code from
__change_memory_common() by overriding the 'ret' variable.

I think the only other place where we don't check at all is the ITS
allocation/freeing. Freeing is more interesting as I think we should not
release the page back to the kernel if we did not manage to restore the
original state. Better have a memory leak than data leak.

---

## [50] Catalin Marinas — 2024-06-21
*Subject: Re: [PATCH v3 12/14] arm64: realm: Support nonsecure ITS emulation
 shared*

Hi Michael,

All good points below, thanks.

On Tue, Jun 18, 2024 at 04:04:17PM +0000, Michael Kelley wrote:
> As someone who has spent time in Linux code on the x86 side that
> manages memory shared between the guest and host, a GFP_DECRYPTED

It might be doable, though it's a lot more intrusive than just a GFP
flag. However, such memory cannot be used for any other things than
sharing data with the host.

> 2) GFP_DECRYPTED should work for the three memory allocation
> interfaces and their variants: alloc_pages(), kmalloc(), and vmalloc().

Yes. There are two main aspects: (1) the page allocation + linear map
change and (2) additional mapping attributes like in the vmalloc() case.

> 3) The current paradigm is to allocate memory and call
> set_memory_decrypted(). Then do the reverse when freeing memory.

Yes, this should be straightforward. Maybe simplified further to avoid
creating additional kmalloc() caches if these functions are not
supported, though we seem to be missing some generic
arch_has_mem_encrypt() API.

> 5) The implementation of GFP_DECRYPTED must correctly handle
> errors from set_memory_decrypted()/encrypted() as I've described

Good point, I completely missed this aspect.

I'll prepare some patches and post them next week to get feedback from
the mm folk.

Thanks.

---

## [51] Jeremy Linton — 2024-06-25
*Subject: Re: [PATCH v3 02/14] arm64: Detect if in a realm and set RIPAS RAM*

Hi,

On 6/12/24 05:40, Jean-Philippe Brucker wrote:
> On Wed, Jun 05, 2024 at 10:29:54AM +0100, Steven Price wrote:
>> From: Suzuki K Poulose <suzuki.poulose@arm.com>

To note: i've found out the hard way this set breaks a qemu+kvm+ACPI 
setup as well, for roughly the same reason. I imagine we want kernels 
which can boot in either a realm or a normal guest.

I delayed the version check a bit and then, did enough that 
arm_smcccc_1_1_invoke() could replace arm_smccc_smc() in 
invoke_rsi_fn_smc_with_res(). Which naturally gets it booting again, the 
larger implications i've not considered yet.




> 
> The easiest fix is to detect the SMC conduit through the PSCI node in DT.

---

## [52] Steven Price — 2024-06-27
*Subject: Re: [PATCH v3 06/14] arm64: Override set_fixmap_io*

On 10/06/2024 18:49, Catalin Marinas wrote:
> On Wed, Jun 05, 2024 at 10:29:58AM +0100, Steven Price wrote:
>> +void set_fixmap_io(enum fixed_addresses idx, phys_addr_t phys)

I agree, there's not much point in this patch as it stands. I'll drop it
(and the previous one) for the next version of the series. We can add it
back if needed when protected MMIO is a thing.

Thanks,
Steve

---

## [53] Steven Price — 2024-06-27
*Subject: Re: [PATCH v3 09/14] arm64: Enable memory encrypt for Realms*

On 10/06/2024 18:27, Catalin Marinas wrote:
> On Wed, Jun 05, 2024 at 10:30:01AM +0100, Steven Price wrote:
>> +static int __set_memory_encrypted(unsigned long addr,

I'm always a bit scared of changing this sort of thing, but AFAICT the 
below should be safe:

-       flush_tlb_kernel_range(start, start + size);
+       /*
+        * If the memory is being made valid without changing any other bits
+        * then a TLBI isn't required as a non-valid entry cannot be cached in
+        * the TLB.
+        */
+       if (set_mask != PTE_VALID || clear_mask)
+               flush_tlb_kernel_range(start, start + size);

It will affect users of set_memory_valid() by removing the TLBI when 
marking memory as valid.

I'll add this change as a separate patch so it can be reverted easily
if there's something I've overlooked.

Thanks,
Steve

---

## [54] Steven Price — 2024-06-28
*Subject: Re: [PATCH v3 12/14] arm64: realm: Support nonsecure ITS emulation
 shared*

On 17/06/2024 04:54, Michael Kelley wrote:
> From: Steven Price <steven.price@arm.com> Sent: Wednesday, June 5, 2024 2:30 AM
>>

Very good points - this code was lacking error handling. I think you are
also right that the correct situation when set_memory_{en,de}crypted()
fails is to WARN() and leak the page. It's something that shouldn't
happen with a well behaving host and it's unclear how to safely recover
the page - so leaking the page is the safest result. And the WARN()
approach gives the user the option as to whether this is fatal via
panic_on_warn.

Thanks,
Steve

---
