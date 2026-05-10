---
title: 'Provide SEV-SNP support for running under an SVSM'
date: 2024-06-05
last_reply: 2024-07-11
message_count: 22
participants: ['Tom Lendacky', 'Borislav Petkov', 'Dan Williams', 'Christophe JAILLET']
---

## [1] Tom Lendacky — 2024-06-05

This series adds SEV-SNP support for running Linux under an Secure VM
Service Module (SVSM) at a less privileged VM Privilege Level (VMPL).
By running at a less privileged VMPL, the SVSM can be used to provide
services, e.g. a virtual TPM, for Linux within the SEV-SNP confidential
VM (CVM) rather than trust such services from the hypervisor.

Currently, a Linux guest expects to run at the highest VMPL, VMPL0, and
there are certain SNP related operations that require that VMPL level.
Specifically, the PVALIDATE instruction and the RMPADJUST instruction
when setting the VMSA attribute of a page (used when starting APs).

If Linux is to run at a less privileged VMPL, e.g. VMPL2, then it must
use an SVSM (which is running at VMPL0) to perform the operations that
it is no longer able to perform.

How Linux interacts with and uses the SVSM is documented in the SVSM
specification [1] and the GHCB specification [2].

This series introduces support to run Linux under an SVSM. It consists
of:
  - Detecting the presence of an SVSM
  - When not running at VMPL0, invoking the SVSM for page validation and
    VMSA page creation/deletion
  - Adding a sysfs entry that specifies the Linux VMPL
  - Modifying the sev-guest driver to use the VMPCK key associated with
    the Linux VMPL
  - Expanding the config-fs TSM support to request attestation reports
    from the SVSM and allowing attributes to be hidden
  - Detecting and allowing Linux to run in a VMPL other than 0 when an
    SVSM is present

The series is based off of and tested against the tip tree:
  https://git.kernel.org/pub/scm/linux/kernel/git/tip/tip.git master

  77db0895e650 ("Merge branch into tip/master: 'x86/percpu'")

[1] https://www.amd.com/content/dam/amd/en/documents/epyc-technical-docs/specifications/58019.pdf
[2] https://www.amd.com/content/dam/amd/en/documents/epyc-technical-docs/specifications/56421.pdf

Cc: Joel Becker <jlbec@evilplan.org>
Cc: Christoph Hellwig <hch@lst.de>

---

Changes in v5:
- Create native versions of local_irq_save()/local_irq_restore().
- Add RIP_REL_REF() calls to functions executed early in boot.
- Fix logic around the return value of the SVSM invocations. This required
  changes where svsm_perform_call_protocol() is invoked to check the
  SVSM return value in the struct svsm_call variable.
- Update configfs support to only recognize group attributes associated
  with a particular item when checking for visibility (don't check for
  a default group).
- Move TSM configfs visibility support from the default group to the
  TSM report attributes.
- Simplify generated assembly for SVSM protocol invocation.
- Remove simple VMPL level accessor function and make the vmpl variable
  global. Rename it from vmpl to snp_vmpl.
- Miscellaneous updates (i.e. initialize variable when declared, rename
  functions, shorten variable names, etc.).
- Documentation updates.

Changes in v4:
- Add a pre-patch to rename the struct snp_secrets_page_layout to just
  snp_secrets_page.
- Move the config-fs visibility support to be group based and referenced
  by an index. Remove the macro changes that set the visibility function
  for an entry.
- Make the TSM visibility support vendor specific via an ops callback.
- Use the rmpadjust() function directly and remove the enforce_vmpl0()
  function.
- Consolidate common variables into arch/x86/kernel/sev-shared.c.

Changes in v3:
- Rename decompresor snp_setup() to early_snp_setup() to better indicate
  when it is called.
- Rename the "svsm" config-fs attribute into the more generic
  "service_provider" attribute that takes a name as input.
- Change config-fs visibility function to be a simple bool return type
  instead of returning the mode.
- Switch to using new RIP_REL_REF() macro and __head notation where
  appropriate.

Changes in v2:
- Define X86_FEATURE_SVSM_PRESENT and set the bit in the CPUID table,
  removing the need to set the CPUID bit in the #VC handler.
- Rename the TSM service_version attribute to service_manifest_version.
- Add support to config-fs to hide attributes and hide the SVSM attributes
  when an SVSM is not present.


Tom Lendacky (13):
  x86/irqflags: Provide native versions of the
    local_irq_save()/restore()
  x86/sev: Check for the presence of an SVSM in the SNP Secrets page
  x86/sev: Use kernel provided SVSM Calling Areas
  x86/sev: Perform PVALIDATE using the SVSM when not at VMPL0
  x86/sev: Use the SVSM to create a vCPU when not in VMPL0
  x86/sev: Provide SVSM discovery support
  x86/sev: Provide guest VMPL level to userspace
  virt: sev-guest: Choose the VMPCK key based on executing VMPL
  configfs-tsm: Allow the privlevel_floor attribute to be updated
  fs/configfs: Add a callback to determine attribute visibility
  x86/sev: Take advantage of configfs visibility support in TSM
  x86/sev: Extend the config-fs attestation support for an SVSM
  x86/sev: Allow non-VMPL0 execution when an SVSM is present

 Documentation/ABI/testing/configfs-tsm        |  63 +++
 .../ABI/testing/sysfs-devices-system-cpu      |  12 +
 .../arch/x86/amd-memory-encryption.rst        |  23 +
 Documentation/virt/coco/sev-guest.rst         |  11 +
 arch/x86/boot/compressed/sev.c                |  83 +++-
 arch/x86/include/asm/cpufeatures.h            |   1 +
 arch/x86/include/asm/irqflags.h               |  20 +
 arch/x86/include/asm/msr-index.h              |   2 +
 arch/x86/include/asm/sev-common.h             |  18 +
 arch/x86/include/asm/sev.h                    | 136 +++++-
 arch/x86/include/uapi/asm/svm.h               |   1 +
 arch/x86/kernel/sev-shared.c                  | 457 +++++++++++++++++-
 arch/x86/kernel/sev.c                         | 442 ++++++++++++++---
 arch/x86/mm/mem_encrypt_amd.c                 |   8 +-
 drivers/virt/coco/sev-guest/sev-guest.c       | 203 +++++++-
 drivers/virt/coco/tdx-guest/tdx-guest.c       |  26 +-
 drivers/virt/coco/tsm.c                       | 177 +++++--
 fs/configfs/dir.c                             |  10 +
 include/linux/configfs.h                      |   3 +
 include/linux/tsm.h                           |  59 ++-
 20 files changed, 1596 insertions(+), 159 deletions(-)

---

## [2] Tom Lendacky — 2024-06-05
*Subject: [PATCH v5 01/13] x86/irqflags: Provide native versions of the local_irq_save()/restore()*

Functions that need to disable IRQs, but are common to both early boot and
post-boot execution, are unable to deal with paravirt support associated
with local_irq_save() and local_irq_restore().

Create native versions of these for use in these situations.

Signed-off-by: Tom Lendacky <thomas.lendacky@amd.com>
---
 arch/x86/include/asm/irqflags.h | 20 ++++++++++++++++++++
 1 file changed, 20 insertions(+)

diff --git a/arch/x86/include/asm/irqflags.h b/arch/x86/include/asm/irqflags.h
index 8c5ae649d2df..cf7fc2b8e3ce 100644
--- a/arch/x86/include/asm/irqflags.h
+++ b/arch/x86/include/asm/irqflags.h
@@ -54,6 +54,26 @@ static __always_inline void native_halt(void)
 	asm volatile("hlt": : :"memory");
 }
 
+static __always_inline int native_irqs_disabled_flags(unsigned long flags)
+{
+	return !(flags & X86_EFLAGS_IF);
+}
+
+static __always_inline unsigned long native_local_irq_save(void)
+{
+	unsigned long flags = native_save_fl();
+
+	native_irq_disable();
+
+	return flags;
+}
+
+static __always_inline void native_local_irq_restore(unsigned long flags)
+{
+	if (!native_irqs_disabled_flags(flags))
+		native_irq_enable();
+}
+
 #endif
 
 #ifdef CONFIG_PARAVIRT_XXL

---

## [3] Tom Lendacky — 2024-06-05
*Subject: [PATCH v5 02/13] x86/sev: Check for the presence of an SVSM in the SNP Secrets page*

During early boot phases, check for the presence of an SVSM when running
as an SEV-SNP guest.

An SVSM is present if not running at VMPL0 and the 64-bit value at offset
0x148 into the secrets page is non-zero. If an SVSM is present, save the
SVSM Calling Area address (CAA), located at offset 0x150 into the secrets
page, and set the VMPL level of the guest, which should be non-zero, to
indicate the presence of an SVSM.

Signed-off-by: Tom Lendacky <thomas.lendacky@amd.com>
---
 .../arch/x86/amd-memory-encryption.rst        | 23 ++++++
 arch/x86/boot/compressed/sev.c                | 21 +++---
 arch/x86/include/asm/sev-common.h             |  4 ++
 arch/x86/include/asm/sev.h                    | 34 ++++++++-
 arch/x86/kernel/sev-shared.c                  | 71 +++++++++++++++++++
 arch/x86/kernel/sev.c                         |  7 ++
 6 files changed, 151 insertions(+), 9 deletions(-)

diff --git a/Documentation/arch/x86/amd-memory-encryption.rst b/Documentation/arch/x86/amd-memory-encryption.rst
index 414bc7402ae7..79eebaa85b7d 100644
--- a/Documentation/arch/x86/amd-memory-encryption.rst
+++ b/Documentation/arch/x86/amd-memory-encryption.rst
@@ -130,4 +130,27 @@ SNP feature support.
 
 More details in AMD64 APM[1] Vol 2: 15.34.10 SEV_STATUS MSR
 
+Secure VM Service Module (SVSM)
+===============================
+SNP provides a feature called Virtual Machine Privilege Levels (VMPL) which
+defines four privilege levels at which guest software can run. The most
+privileged level is 0 and numerically higher numbers have lesser privileges.
+More details in the AMD64 APM[1] Vol 2, section "15.35.7 Virtual Machine
+Privilege Levels", docID: 24593.
+
+When using that feature, different services can run at different protection
+levels, apart from the guest OS but still within the secure SNP environment.
+They can provide services to the guest, like a vTPM, for example.
+
+When a guest is not running at VMPL0, it needs to communicate with the software
+running at VMPL0 to perform privileged operations or to interact with secure
+services. An example fur such a privileged operation is PVALIDATE which is
+*required* to be executed at VMPL0.
+
+In this scenario, the software running at VMPL0 is usually called a Secure VM
+Service Module (SVSM). Discovery of an SVSM and the API used to communicate
+with it is documented in "Secure VM Service Module for SEV-SNP Guests", docID:
+58019[2].
+
 [1] https://www.amd.com/content/dam/amd/en/documents/processor-tech-docs/programmer-references/24593.pdf
+[2] https://www.amd.com/content/dam/amd/en/documents/epyc-technical-docs/specifications/58019.pdf
diff --git a/arch/x86/boot/compressed/sev.c b/arch/x86/boot/compressed/sev.c
index 0457a9d7e515..927b71495122 100644
--- a/arch/x86/boot/compressed/sev.c
+++ b/arch/x86/boot/compressed/sev.c
@@ -462,6 +462,13 @@ static bool early_snp_init(struct boot_params *bp)
 	 */
 	setup_cpuid_table(cc_info);
 
+	/*
+	 * Record the SVSM Calling Area (CA) address if the guest is not
+	 * running at VMPL0. The CA will be used to communicate with the
+	 * SVSM to perform the SVSM services.
+	 */
+	svsm_setup_ca(cc_info);
+
 	/*
 	 * Pass run-time kernel a pointer to CC info via boot_params so EFI
 	 * config table doesn't need to be searched again during early startup
@@ -571,14 +578,12 @@ void sev_enable(struct boot_params *bp)
 		/*
 		 * Enforce running at VMPL0.
 		 *
-		 * RMPADJUST modifies RMP permissions of a lesser-privileged (numerically
-		 * higher) privilege level. Here, clear the VMPL1 permission mask of the
-		 * GHCB page. If the guest is not running at VMPL0, this will fail.
-		 *
-		 * If the guest is running at VMPL0, it will succeed. Even if that operation
-		 * modifies permission bits, it is still ok to do so currently because Linux
-		 * SNP guests running at VMPL0 only run at VMPL0, so VMPL1 or higher
-		 * permission mask changes are a don't-care.
+		 * Use RMPADJUST (see the rmpadjust() function for a description of
+		 * what the instruction does) to update the VMPL1 permissions of a
+		 * page. If the guest is running at VMPL0, this will succeed. If the
+		 * guest is running at any other VMPL, this will fail. Linux SNP guests
+		 * only ever run at a single VMPL level so permission mask changes of a
+		 * lesser-privileged VMPL are a don't-care.
 		 */
 		if (rmpadjust((unsigned long)&boot_ghcb_page, RMP_PG_SIZE_4K, 1))
 			sev_es_terminate(SEV_TERM_SET_LINUX, GHCB_TERM_NOT_VMPL0);
diff --git a/arch/x86/include/asm/sev-common.h b/arch/x86/include/asm/sev-common.h
index 5a8246dd532f..d31f2ed398f0 100644
--- a/arch/x86/include/asm/sev-common.h
+++ b/arch/x86/include/asm/sev-common.h
@@ -163,6 +163,10 @@ struct snp_psc_desc {
 #define GHCB_TERM_NOT_VMPL0		3	/* SNP guest is not running at VMPL-0 */
 #define GHCB_TERM_CPUID			4	/* CPUID-validation failure */
 #define GHCB_TERM_CPUID_HV		5	/* CPUID failure during hypervisor fallback */
+#define GHCB_TERM_SECRETS_PAGE		6	/* Secrets page failure */
+#define GHCB_TERM_NO_SVSM		7	/* SVSM is not advertised in the secrets page */
+#define GHCB_TERM_SVSM_VMPL0		8	/* SVSM is present but has set VMPL to 0 */
+#define GHCB_TERM_SVSM_CAA		9	/* SVSM is present but CAA is not page aligned */
 
 #define GHCB_RESP_CODE(v)		((v) & GHCB_MSR_INFO_MASK)
 
diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index ca20cc4e5826..16d09c1a8ceb 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -152,9 +152,32 @@ struct snp_secrets_page {
 	u8 vmpck2[VMPCK_KEY_LEN];
 	u8 vmpck3[VMPCK_KEY_LEN];
 	struct secrets_os_area os_area;
-	u8 rsvd3[3840];
+
+	u8 vmsa_tweak_bitmap[64];
+
+	/* SVSM fields */
+	u64 svsm_base;
+	u64 svsm_size;
+	u64 svsm_caa;
+	u32 svsm_max_version;
+	u8 svsm_guest_vmpl;
+	u8 rsvd3[3];
+
+	/* Remainder of page */
+	u8 rsvd4[3744];
 } __packed;
 
+/*
+ * The SVSM Calling Area (CA) related structures.
+ */
+struct svsm_ca {
+	u8 call_pending;
+	u8 mem_available;
+	u8 rsvd1[6];
+
+	u8 svsm_buffer[PAGE_SIZE - 8];
+};
+
 #ifdef CONFIG_AMD_MEM_ENCRYPT
 extern void __sev_es_ist_enter(struct pt_regs *regs);
 extern void __sev_es_ist_exit(void);
@@ -185,6 +208,15 @@ static inline int rmpadjust(unsigned long vaddr, bool rmp_psize, unsigned long a
 {
 	int rc;
 
+	/*
+	 * RMPADJUST modifies the RMP permissions of a page of a lesser-privileged
+	 * (numerically higher) VMPL.
+	 *
+	 * If the guest is running at a higher-privilege than the privilege level
+	 * the instruction is targeting, the instruction will succeed, otherwise,
+	 * it will fail.
+	 */
+
 	/* "rmpadjust" mnemonic support in binutils 2.36 and newer */
 	asm volatile(".byte 0xF3,0x0F,0x01,0xFE\n\t"
 		     : "=a"(rc)
diff --git a/arch/x86/kernel/sev-shared.c b/arch/x86/kernel/sev-shared.c
index b4f8fa0f722c..739362066e00 100644
--- a/arch/x86/kernel/sev-shared.c
+++ b/arch/x86/kernel/sev-shared.c
@@ -23,6 +23,21 @@
 #define sev_printk_rtl(fmt, ...)
 #endif
 
+/*
+ * SVSM related information:
+ *   When running under an SVSM, the VMPL that Linux is executing at must be
+ *   non-zero. The VMPL is therefore used to indicate the presence of an SVSM.
+ *
+ *   During boot, the page tables are set up as identity mapped and later
+ *   changed to use kernel virtual addresses. Maintain separate virtual and
+ *   physical addresses for the CAA to allow SVSM functions to be used during
+ *   early boot, both with identity mapped virtual addresses and proper kernel
+ *   virtual addresses.
+ */
+static u8 snp_vmpl __ro_after_init;
+static struct svsm_ca *boot_svsm_caa __ro_after_init;
+static u64 boot_svsm_caa_pa __ro_after_init;
+
 /* I/O parameters for CPUID-related helpers */
 struct cpuid_leaf {
 	u32 fn;
@@ -1269,3 +1284,59 @@ static enum es_result vc_check_opcode_bytes(struct es_em_ctxt *ctxt,
 
 	return ES_UNSUPPORTED;
 }
+
+/*
+ * Maintain the GPA of the SVSM Calling Area (CA) in order to utilize the SVSM
+ * services needed when not running in VMPL0.
+ */
+static void __head svsm_setup_ca(const struct cc_blob_sev_info *cc_info)
+{
+	struct snp_secrets_page *secrets_page;
+	u64 caa;
+
+	BUILD_BUG_ON(sizeof(*secrets_page) != PAGE_SIZE);
+
+	/*
+	 * Check if running at VMPL0.
+	 *
+	 * Use RMPADJUST (see the rmpadjust() function for a description of what
+	 * the instruction does) to update the VMPL1 permissions of a page. If
+	 * the guest is running at VMPL0, this will succeed and implies there is
+	 * no SVSM. If the guest is running at any other VMPL, this will fail.
+	 * Linux SNP guests only ever run at a single VMPL level so permission mask
+	 * changes of a lesser-privileged VMPL are a don't-care.
+	 *
+	 * Use a rip-relative reference to obtain the proper address, since this
+	 * routine is running identity mapped when called, both by the decompressor
+	 * code and the early kernel code.
+	 */
+	if (!rmpadjust((unsigned long)&RIP_REL_REF(boot_ghcb_page), RMP_PG_SIZE_4K, 1))
+		return;
+
+	/*
+	 * Not running at VMPL0, ensure everything has been properly supplied
+	 * for running under an SVSM.
+	 */
+	if (!cc_info || !cc_info->secrets_phys || cc_info->secrets_len != PAGE_SIZE)
+		sev_es_terminate(SEV_TERM_SET_LINUX, GHCB_TERM_SECRETS_PAGE);
+
+	secrets_page = (struct snp_secrets_page *)cc_info->secrets_phys;
+	if (!secrets_page->svsm_size)
+		sev_es_terminate(SEV_TERM_SET_LINUX, GHCB_TERM_NO_SVSM);
+
+	if (!secrets_page->svsm_guest_vmpl)
+		sev_es_terminate(SEV_TERM_SET_LINUX, GHCB_TERM_SVSM_VMPL0);
+
+	RIP_REL_REF(snp_vmpl) = secrets_page->svsm_guest_vmpl;
+
+	caa = secrets_page->svsm_caa;
+	if (caa & (PAGE_SIZE - 1))
+		sev_es_terminate(SEV_TERM_SET_LINUX, GHCB_TERM_SVSM_CAA);
+
+	/*
+	 * The CA is identity mapped when this routine is called, both by the
+	 * decompressor code and the early kernel code.
+	 */
+	RIP_REL_REF(boot_svsm_caa) = (struct svsm_ca *)caa;
+	RIP_REL_REF(boot_svsm_caa_pa) = caa;
+}
diff --git a/arch/x86/kernel/sev.c b/arch/x86/kernel/sev.c
index 3342ed58e168..36a117a38b10 100644
--- a/arch/x86/kernel/sev.c
+++ b/arch/x86/kernel/sev.c
@@ -2108,6 +2108,13 @@ bool __head snp_init(struct boot_params *bp)
 
 	setup_cpuid_table(cc_info);
 
+	/*
+	 * Record the SVSM Calling Area address (CAA) if the guest is not
+	 * running at VMPL0. The CA will be used to communicate with the
+	 * SVSM to perform the SVSM services.
+	 */
+	svsm_setup_ca(cc_info);
+
 	/*
 	 * The CC blob will be used later to access the secrets page. Cache
 	 * it here like the boot kernel does.

---

## [4] Tom Lendacky — 2024-06-05
*Subject: [PATCH v5 03/13] x86/sev: Use kernel provided SVSM Calling Areas*

The SVSM Calling Area (CA) is used to communicate between Linux and the
SVSM. Since the firmware supplied CA for the BSP is likely to be in
reserved memory, switch off that CA to a kernel provided CA so that access
and use of the CA is available during boot. The CA switch is done using
the SVSM core protocol SVSM_CORE_REMAP_CA call.

An SVSM call is executed by filling out the SVSM CA and setting the proper
register state as documented by the SVSM protocol. The SVSM is invoked by
by requesting the hypervisor to run VMPL0.

Once it is safe to allocate/reserve memory, allocate a CA for each CPU.
After allocating the new CAs, the BSP will switch from the boot CA to the
per-CPU CA. The CA for an AP is identified to the SVSM when creating the
VMSA in preparation for booting the AP.

Signed-off-by: Tom Lendacky <thomas.lendacky@amd.com>
---
 arch/x86/include/asm/sev-common.h |  13 ++
 arch/x86/include/asm/sev.h        |  32 +++++
 arch/x86/include/uapi/asm/svm.h   |   1 +
 arch/x86/kernel/sev-shared.c      | 128 +++++++++++++++++-
 arch/x86/kernel/sev.c             | 217 +++++++++++++++++++++++++-----
 arch/x86/mm/mem_encrypt_amd.c     |   8 +-
 6 files changed, 360 insertions(+), 39 deletions(-)

diff --git a/arch/x86/include/asm/sev-common.h b/arch/x86/include/asm/sev-common.h
index d31f2ed398f0..78a4c25119da 100644
--- a/arch/x86/include/asm/sev-common.h
+++ b/arch/x86/include/asm/sev-common.h
@@ -98,6 +98,19 @@ enum psc_op {
 	/* GHCBData[63:32] */				\
 	(((u64)(val) & GENMASK_ULL(63, 32)) >> 32)
 
+/* GHCB Run at VMPL Request/Response */
+#define GHCB_MSR_VMPL_REQ		0x016
+#define GHCB_MSR_VMPL_REQ_LEVEL(v)			\
+	/* GHCBData[39:32] */				\
+	(((u64)(v) & GENMASK_ULL(7, 0) << 32) |		\
+	/* GHCBDdata[11:0] */				\
+	GHCB_MSR_VMPL_REQ)
+
+#define GHCB_MSR_VMPL_RESP		0x017
+#define GHCB_MSR_VMPL_RESP_VAL(v)			\
+	/* GHCBData[63:32] */				\
+	(((u64)(v) & GENMASK_ULL(63, 32)) >> 32)
+
 /* GHCB Hypervisor Feature Request/Response */
 #define GHCB_MSR_HV_FT_REQ		0x080
 #define GHCB_MSR_HV_FT_RESP		0x081
diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index 16d09c1a8ceb..3abc2d759db7 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -178,6 +178,36 @@ struct svsm_ca {
 	u8 svsm_buffer[PAGE_SIZE - 8];
 };
 
+#define SVSM_SUCCESS				0
+#define SVSM_ERR_INCOMPLETE			0x80000000
+#define SVSM_ERR_UNSUPPORTED_PROTOCOL		0x80000001
+#define SVSM_ERR_UNSUPPORTED_CALL		0x80000002
+#define SVSM_ERR_INVALID_ADDRESS		0x80000003
+#define SVSM_ERR_INVALID_FORMAT			0x80000004
+#define SVSM_ERR_INVALID_PARAMETER		0x80000005
+#define SVSM_ERR_INVALID_REQUEST		0x80000006
+#define SVSM_ERR_BUSY				0x80000007
+
+/*
+ * SVSM protocol structure
+ */
+struct svsm_call {
+	struct svsm_ca *caa;
+	u64 rax;
+	u64 rcx;
+	u64 rdx;
+	u64 r8;
+	u64 r9;
+	u64 rax_out;
+	u64 rcx_out;
+	u64 rdx_out;
+	u64 r8_out;
+	u64 r9_out;
+};
+
+#define SVSM_CORE_CALL(x)		((0ULL << 32) | (x))
+#define SVSM_CORE_REMAP_CA		0
+
 #ifdef CONFIG_AMD_MEM_ENCRYPT
 extern void __sev_es_ist_enter(struct pt_regs *regs);
 extern void __sev_es_ist_exit(void);
@@ -261,6 +291,7 @@ void snp_accept_memory(phys_addr_t start, phys_addr_t end);
 u64 snp_get_unsupported_features(u64 status);
 u64 sev_get_status(void);
 void sev_show_status(void);
+void snp_remap_svsm_ca(void);
 #else
 static inline void sev_es_ist_enter(struct pt_regs *regs) { }
 static inline void sev_es_ist_exit(void) { }
@@ -290,6 +321,7 @@ static inline void snp_accept_memory(phys_addr_t start, phys_addr_t end) { }
 static inline u64 snp_get_unsupported_features(u64 status) { return 0; }
 static inline u64 sev_get_status(void) { return 0; }
 static inline void sev_show_status(void) { }
+static inline void snp_remap_svsm_ca(void) { }
 #endif
 
 #ifdef CONFIG_KVM_AMD_SEV
diff --git a/arch/x86/include/uapi/asm/svm.h b/arch/x86/include/uapi/asm/svm.h
index 80e1df482337..1814b413fd57 100644
--- a/arch/x86/include/uapi/asm/svm.h
+++ b/arch/x86/include/uapi/asm/svm.h
@@ -115,6 +115,7 @@
 #define SVM_VMGEXIT_AP_CREATE_ON_INIT		0
 #define SVM_VMGEXIT_AP_CREATE			1
 #define SVM_VMGEXIT_AP_DESTROY			2
+#define SVM_VMGEXIT_SNP_RUN_VMPL		0x80000018
 #define SVM_VMGEXIT_HV_FEATURES			0x8000fffd
 #define SVM_VMGEXIT_TERM_REQUEST		0x8000fffe
 #define SVM_VMGEXIT_TERM_REASON(reason_set, reason_code)	\
diff --git a/arch/x86/kernel/sev-shared.c b/arch/x86/kernel/sev-shared.c
index 739362066e00..00173deefc46 100644
--- a/arch/x86/kernel/sev-shared.c
+++ b/arch/x86/kernel/sev-shared.c
@@ -21,6 +21,8 @@
 #define WARN(condition, format...) (!!(condition))
 #define sev_printk(fmt, ...)
 #define sev_printk_rtl(fmt, ...)
+#undef vc_forward_exception
+#define vc_forward_exception(c)		panic("SNP: Hypervisor requested exception\n")
 #endif
 
 /*
@@ -244,6 +246,126 @@ static enum es_result verify_exception_info(struct ghcb *ghcb, struct es_em_ctxt
 	return ES_VMM_ERROR;
 }
 
+static int process_svsm_result_codes(struct svsm_call *call)
+{
+	switch (call->rax_out) {
+	case SVSM_SUCCESS:
+		return 0;
+	case SVSM_ERR_INCOMPLETE:
+	case SVSM_ERR_BUSY:
+		return -EAGAIN;
+	default:
+		return -EINVAL;
+	}
+}
+
+/*
+ * Issue a VMGEXIT to call the SVSM:
+ *   - Load the SVSM register state (RAX, RCX, RDX, R8 and R9)
+ *   - Set the CA call pending field to 1
+ *   - Issue VMGEXIT
+ *   - Save the SVSM return register state (RAX, RCX, RDX, R8 and R9)
+ *   - Perform atomic exchange of the CA call pending field
+ *
+ *   - See the "Secure VM Service Module for SEV-SNP Guests" specification for
+ *     details on the calling convention.
+ *     - The calling convention loosely follows the Microsoft X64 calling
+ *       convention by putting arguments in RCX, RDX, R8 and R9.
+ *     - RAX specifies the SVSM protocol/callid as input and the return code
+ *       as output.
+ */
+static __always_inline void issue_svsm_call(struct svsm_call *call, u8 *pending)
+{
+	register unsigned long rax asm("rax") = call->rax;
+	register unsigned long rcx asm("rcx") = call->rcx;
+	register unsigned long rdx asm("rdx") = call->rdx;
+	register unsigned long r8  asm("r8")  = call->r8;
+	register unsigned long r9  asm("r9")  = call->r9;
+
+	call->caa->call_pending = 1;
+
+	asm volatile("rep; vmmcall\n\t"
+		     : "+r" (rax), "+r" (rcx), "+r" (rdx), "+r" (r8), "+r" (r9)
+		     : : "memory");
+
+	*pending = xchg(&call->caa->call_pending, *pending);
+
+	call->rax_out = rax;
+	call->rcx_out = rcx;
+	call->rdx_out = rdx;
+	call->r8_out  = r8;
+	call->r9_out  = r9;
+}
+
+static int svsm_perform_msr_protocol(struct svsm_call *call)
+{
+	u8 pending = 0;
+	u64 val, resp;
+
+	/*
+	 * When using the MSR protocol, be sure to save and restore
+	 * the current MSR value.
+	 */
+	val = sev_es_rd_ghcb_msr();
+
+	sev_es_wr_ghcb_msr(GHCB_MSR_VMPL_REQ_LEVEL(0));
+
+	issue_svsm_call(call, &pending);
+
+	resp = sev_es_rd_ghcb_msr();
+
+	sev_es_wr_ghcb_msr(val);
+
+	if (pending)
+		return -EINVAL;
+
+	if (GHCB_RESP_CODE(resp) != GHCB_MSR_VMPL_RESP)
+		return -EINVAL;
+
+	if (GHCB_MSR_VMPL_RESP_VAL(resp))
+		return -EINVAL;
+
+	return process_svsm_result_codes(call);
+}
+
+static int svsm_perform_ghcb_protocol(struct ghcb *ghcb, struct svsm_call *call)
+{
+	struct es_em_ctxt ctxt;
+	u8 pending = 0;
+
+	vc_ghcb_invalidate(ghcb);
+
+	/*
+	 * Fill in protocol and format specifiers. This can be called very early
+	 * in the boot, so use rip-relative references as needed.
+	 */
+	ghcb->protocol_version = RIP_REL_REF(ghcb_version);
+	ghcb->ghcb_usage       = GHCB_DEFAULT_USAGE;
+
+	ghcb_set_sw_exit_code(ghcb, SVM_VMGEXIT_SNP_RUN_VMPL);
+	ghcb_set_sw_exit_info_1(ghcb, 0);
+	ghcb_set_sw_exit_info_2(ghcb, 0);
+
+	sev_es_wr_ghcb_msr(__pa(ghcb));
+
+	issue_svsm_call(call, &pending);
+
+	if (pending)
+		return -EINVAL;
+
+	switch (verify_exception_info(ghcb, &ctxt)) {
+	case ES_OK:
+		break;
+	case ES_EXCEPTION:
+		vc_forward_exception(&ctxt);
+		fallthrough;
+	default:
+		return -EINVAL;
+	}
+
+	return process_svsm_result_codes(call);
+}
+
 static enum es_result sev_es_ghcb_hv_call(struct ghcb *ghcb,
 					  struct es_em_ctxt *ctxt,
 					  u64 exit_code, u64 exit_info_1,
@@ -1289,7 +1411,7 @@ static enum es_result vc_check_opcode_bytes(struct es_em_ctxt *ctxt,
  * Maintain the GPA of the SVSM Calling Area (CA) in order to utilize the SVSM
  * services needed when not running in VMPL0.
  */
-static void __head svsm_setup_ca(const struct cc_blob_sev_info *cc_info)
+static bool __head svsm_setup_ca(const struct cc_blob_sev_info *cc_info)
 {
 	struct snp_secrets_page *secrets_page;
 	u64 caa;
@@ -1311,7 +1433,7 @@ static void __head svsm_setup_ca(const struct cc_blob_sev_info *cc_info)
 	 * code and the early kernel code.
 	 */
 	if (!rmpadjust((unsigned long)&RIP_REL_REF(boot_ghcb_page), RMP_PG_SIZE_4K, 1))
-		return;
+		return false;
 
 	/*
 	 * Not running at VMPL0, ensure everything has been properly supplied
@@ -1339,4 +1461,6 @@ static void __head svsm_setup_ca(const struct cc_blob_sev_info *cc_info)
 	 */
 	RIP_REL_REF(boot_svsm_caa) = (struct svsm_ca *)caa;
 	RIP_REL_REF(boot_svsm_caa_pa) = caa;
+
+	return true;
 }
diff --git a/arch/x86/kernel/sev.c b/arch/x86/kernel/sev.c
index 36a117a38b10..6bab3244a3b9 100644
--- a/arch/x86/kernel/sev.c
+++ b/arch/x86/kernel/sev.c
@@ -133,16 +133,20 @@ struct ghcb_state {
 	struct ghcb *ghcb;
 };
 
+/* For early boot SVSM communication */
+static struct svsm_ca boot_svsm_ca_page __aligned(PAGE_SIZE);
+
 static DEFINE_PER_CPU(struct sev_es_runtime_data*, runtime_data);
 static DEFINE_PER_CPU(struct sev_es_save_area *, sev_vmsa);
+static DEFINE_PER_CPU(struct svsm_ca *, svsm_caa);
+static DEFINE_PER_CPU(u64, svsm_caa_pa);
 
 struct sev_config {
 	__u64 debug		: 1,
 
 	      /*
-	       * A flag used by __set_pages_state() that indicates when the
-	       * per-CPU GHCB has been created and registered and thus can be
-	       * used by the BSP instead of the early boot GHCB.
+	       * Indicates when the per-CPU GHCB has been created and registered
+	       * and thus can be used by the BSP instead of the early boot GHCB.
 	       *
 	       * For APs, the per-CPU GHCB is created before they are started
 	       * and registered upon startup, so this flag can be used globally
@@ -150,6 +154,15 @@ struct sev_config {
 	       */
 	      ghcbs_initialized	: 1,
 
+	      /*
+	       * Indicates when the per-CPU SVSM CA is to be used instead of the
+	       * boot SVSM CA.
+	       *
+	       * For APs, the per-CPU SVSM CA is created as part of the AP
+	       * bringup, so this flag can be used globally for the BSP and APs.
+	       */
+	      cas_initialized	: 1,
+
 	      __reserved	: 62;
 };
 
@@ -572,9 +585,47 @@ static enum es_result vc_ioio_check(struct es_em_ctxt *ctxt, u16 port, size_t si
 	return ES_EXCEPTION;
 }
 
+static __always_inline void vc_forward_exception(struct es_em_ctxt *ctxt)
+{
+	long error_code = ctxt->fi.error_code;
+	int trapnr = ctxt->fi.vector;
+
+	ctxt->regs->orig_ax = ctxt->fi.error_code;
+
+	switch (trapnr) {
+	case X86_TRAP_GP:
+		exc_general_protection(ctxt->regs, error_code);
+		break;
+	case X86_TRAP_UD:
+		exc_invalid_op(ctxt->regs);
+		break;
+	case X86_TRAP_PF:
+		write_cr2(ctxt->fi.cr2);
+		exc_page_fault(ctxt->regs, error_code);
+		break;
+	case X86_TRAP_AC:
+		exc_alignment_check(ctxt->regs, error_code);
+		break;
+	default:
+		pr_emerg("Unsupported exception in #VC instruction emulation - can't continue\n");
+		BUG();
+	}
+}
+
 /* Include code shared with pre-decompression boot stage */
 #include "sev-shared.c"
 
+static struct svsm_ca *svsm_get_caa(void)
+{
+	/*
+	 * Use rip-relative references when called early in the boot. If
+	 * cas_initialized is set, then it is late in the boot and no need
+	 * to worry about rip-relative references.
+	 */
+	return RIP_REL_REF(sev_cfg).cas_initialized ? this_cpu_read(svsm_caa)
+						    : RIP_REL_REF(boot_svsm_caa);
+}
+
 static noinstr void __sev_put_ghcb(struct ghcb_state *state)
 {
 	struct sev_es_runtime_data *data;
@@ -600,6 +651,44 @@ static noinstr void __sev_put_ghcb(struct ghcb_state *state)
 	}
 }
 
+static int svsm_perform_call_protocol(struct svsm_call *call)
+{
+	struct ghcb_state state;
+	unsigned long flags;
+	struct ghcb *ghcb;
+	int ret;
+
+	/*
+	 * This can be called very early in the boot, use native functions in
+	 * order to avoid paravirt issues.
+	 */
+	flags = native_local_irq_save();
+
+	/*
+	 * Use rip-relative references when called early in the boot. If
+	 * ghcbs_initialized is set, then it is late in the boot and no need
+	 * to worry about rip-relative references in called functions.
+	 */
+	if (RIP_REL_REF(sev_cfg).ghcbs_initialized)
+		ghcb = __sev_get_ghcb(&state);
+	else if (RIP_REL_REF(boot_ghcb))
+		ghcb = RIP_REL_REF(boot_ghcb);
+	else
+		ghcb = NULL;
+
+	do {
+		ret = ghcb ? svsm_perform_ghcb_protocol(ghcb, call)
+			   : svsm_perform_msr_protocol(call);
+	} while (ret == -EAGAIN);
+
+	if (RIP_REL_REF(sev_cfg).ghcbs_initialized)
+		__sev_put_ghcb(&state);
+
+	native_local_irq_restore(flags);
+
+	return ret;
+}
+
 void noinstr __sev_es_nmi_complete(void)
 {
 	struct ghcb_state state;
@@ -1346,6 +1435,18 @@ static void __init alloc_runtime_data(int cpu)
 		panic("Can't allocate SEV-ES runtime data");
 
 	per_cpu(runtime_data, cpu) = data;
+
+	if (snp_vmpl) {
+		struct svsm_ca *caa;
+
+		/* Allocate the SVSM CA page if an SVSM is present */
+		caa = memblock_alloc(sizeof(*caa), PAGE_SIZE);
+		if (!caa)
+			panic("Can't allocate SVSM CA page\n");
+
+		per_cpu(svsm_caa, cpu) = caa;
+		per_cpu(svsm_caa_pa, cpu) = __pa(caa);
+	}
 }
 
 static void __init init_ghcb(int cpu)
@@ -1395,6 +1496,32 @@ void __init sev_es_init_vc_handling(void)
 		init_ghcb(cpu);
 	}
 
+	/* If running under an SVSM, switch to the per-cpu CA */
+	if (snp_vmpl) {
+		struct svsm_call call = {};
+		unsigned long flags;
+		int ret;
+
+		local_irq_save(flags);
+
+		/*
+		 * SVSM_CORE_REMAP_CA call:
+		 *   RAX = 0 (Protocol=0, CallID=0)
+		 *   RCX = New CA GPA
+		 */
+		call.caa = svsm_get_caa();
+		call.rax = SVSM_CORE_CALL(SVSM_CORE_REMAP_CA);
+		call.rcx = this_cpu_read(svsm_caa_pa);
+		ret = svsm_perform_call_protocol(&call);
+		if (ret)
+			panic("Can't remap the SVSM CA, ret=%d, rax_out=0x%llx\n",
+			      ret, call.rax_out);
+
+		sev_cfg.cas_initialized = true;
+
+		local_irq_restore(flags);
+	}
+
 	sev_es_setup_play_dead();
 
 	/* Secondary CPUs use the runtime #VC handler */
@@ -1819,33 +1946,6 @@ static enum es_result vc_handle_exitcode(struct es_em_ctxt *ctxt,
 	return result;
 }
 
-static __always_inline void vc_forward_exception(struct es_em_ctxt *ctxt)
-{
-	long error_code = ctxt->fi.error_code;
-	int trapnr = ctxt->fi.vector;
-
-	ctxt->regs->orig_ax = ctxt->fi.error_code;
-
-	switch (trapnr) {
-	case X86_TRAP_GP:
-		exc_general_protection(ctxt->regs, error_code);
-		break;
-	case X86_TRAP_UD:
-		exc_invalid_op(ctxt->regs);
-		break;
-	case X86_TRAP_PF:
-		write_cr2(ctxt->fi.cr2);
-		exc_page_fault(ctxt->regs, error_code);
-		break;
-	case X86_TRAP_AC:
-		exc_alignment_check(ctxt->regs, error_code);
-		break;
-	default:
-		pr_emerg("Unsupported exception in #VC instruction emulation - can't continue\n");
-		BUG();
-	}
-}
-
 static __always_inline bool is_vc2_stack(unsigned long sp)
 {
 	return (sp >= __this_cpu_ist_bottom_va(VC2) && sp < __this_cpu_ist_top_va(VC2));
@@ -2095,6 +2195,47 @@ static __head struct cc_blob_sev_info *find_cc_blob(struct boot_params *bp)
 	return cc_info;
 }
 
+static __head void svsm_setup(struct cc_blob_sev_info *cc_info)
+{
+	struct svsm_call call = {};
+	int ret;
+	u64 pa;
+
+	/*
+	 * Record the SVSM Calling Area address (CAA) if the guest is not
+	 * running at VMPL0. The CA will be used to communicate with the
+	 * SVSM to perform the SVSM services.
+	 */
+	if (!svsm_setup_ca(cc_info))
+		return;
+
+	/*
+	 * It is very early in the boot and the kernel is running identity
+	 * mapped but without having adjusted the pagetables to where the
+	 * kernel was loaded (physbase), so the get the CA address using
+	 * RIP-relative addressing.
+	 */
+	pa = (u64)&RIP_REL_REF(boot_svsm_ca_page);
+
+	/*
+	 * Switch over to the boot SVSM CA while the current CA is still
+	 * addressable. There is no GHCB at this point so use the MSR protocol.
+	 *
+	 * SVSM_CORE_REMAP_CA call:
+	 *   RAX = 0 (Protocol=0, CallID=0)
+	 *   RCX = New CA GPA
+	 */
+	call.caa = svsm_get_caa();
+	call.rax = SVSM_CORE_CALL(SVSM_CORE_REMAP_CA);
+	call.rcx = pa;
+	ret = svsm_perform_call_protocol(&call);
+	if (ret)
+		panic("Can't remap the SVSM CA, ret=%d, rax_out=0x%llx\n", ret, call.rax_out);
+
+	RIP_REL_REF(boot_svsm_caa) = (struct svsm_ca *)pa;
+	RIP_REL_REF(boot_svsm_caa_pa) = pa;
+}
+
 bool __head snp_init(struct boot_params *bp)
 {
 	struct cc_blob_sev_info *cc_info;
@@ -2108,12 +2249,7 @@ bool __head snp_init(struct boot_params *bp)
 
 	setup_cpuid_table(cc_info);
 
-	/*
-	 * Record the SVSM Calling Area address (CAA) if the guest is not
-	 * running at VMPL0. The CA will be used to communicate with the
-	 * SVSM to perform the SVSM services.
-	 */
-	svsm_setup_ca(cc_info);
+	svsm_setup(cc_info);
 
 	/*
 	 * The CC blob will be used later to access the secrets page. Cache
@@ -2306,3 +2442,12 @@ void sev_show_status(void)
 	}
 	pr_cont("\n");
 }
+
+void __init snp_remap_svsm_ca(void)
+{
+	if (!snp_vmpl)
+		return;
+
+	/* Update the CAA to a proper kernel address */
+	boot_svsm_caa = &boot_svsm_ca_page;
+}
diff --git a/arch/x86/mm/mem_encrypt_amd.c b/arch/x86/mm/mem_encrypt_amd.c
index 422602f6039b..6155020e4d2d 100644
--- a/arch/x86/mm/mem_encrypt_amd.c
+++ b/arch/x86/mm/mem_encrypt_amd.c
@@ -2,7 +2,7 @@
 /*
  * AMD Memory Encryption Support
  *
- * Copyright (C) 2016 Advanced Micro Devices, Inc.
+ * Copyright (C) 2016-2024 Advanced Micro Devices, Inc.
  *
  * Author: Tom Lendacky <thomas.lendacky@amd.com>
  */
@@ -510,6 +510,12 @@ void __init sme_early_init(void)
 		 */
 		x86_init.resources.dmi_setup = snp_dmi_setup;
 	}
+
+	/*
+	 * Switch the SVSM CA mapping (if active) from identity mapped to
+	 * kernel mapped.
+	 */
+	snp_remap_svsm_ca();
 }
 
 void __init mem_encrypt_free_decrypted_mem(void)

---

## [5] Tom Lendacky — 2024-06-05
*Subject: [PATCH v5 04/13] x86/sev: Perform PVALIDATE using the SVSM when not at VMPL0*

The PVALIDATE instruction can only be performed at VMPL0. An SVSM will
be present when running at VMPL1 or a lower privilege level.

When an SVSM is present, use the SVSM_CORE_PVALIDATE call to perform
memory validation instead of issuing the PVALIDATE instruction directly.

The validation of a single 4K page is now explicitly identified as such
in the function name, pvalidate_4k_page(). The pvalidate_pages() function
is used for validating 1 or more pages at either 4K or 2M in size. Each
function, however, determines whether it can issue the PVALIDATE directly
or whether the SVSM needs to be invoked.

Signed-off-by: Tom Lendacky <thomas.lendacky@amd.com>
---
 arch/x86/boot/compressed/sev.c |  45 +++++-
 arch/x86/include/asm/sev.h     |  26 ++++
 arch/x86/kernel/sev-shared.c   | 250 +++++++++++++++++++++++++++++++--
 arch/x86/kernel/sev.c          |  30 ++--
 4 files changed, 325 insertions(+), 26 deletions(-)

diff --git a/arch/x86/boot/compressed/sev.c b/arch/x86/boot/compressed/sev.c
index 927b71495122..1cc3106a3ba7 100644
--- a/arch/x86/boot/compressed/sev.c
+++ b/arch/x86/boot/compressed/sev.c
@@ -129,6 +129,34 @@ static bool fault_in_kernel_space(unsigned long address)
 /* Include code for early handlers */
 #include "../../kernel/sev-shared.c"
 
+static struct svsm_ca *svsm_get_caa(void)
+{
+	return boot_svsm_caa;
+}
+
+static u64 svsm_get_caa_pa(void)
+{
+	return boot_svsm_caa_pa;
+}
+
+static int svsm_perform_call_protocol(struct svsm_call *call)
+{
+	struct ghcb *ghcb;
+	int ret;
+
+	if (boot_ghcb)
+		ghcb = boot_ghcb;
+	else
+		ghcb = NULL;
+
+	do {
+		ret = ghcb ? svsm_perform_ghcb_protocol(ghcb, call)
+			   : svsm_perform_msr_protocol(call);
+	} while (ret == -EAGAIN);
+
+	return ret;
+}
+
 bool sev_snp_enabled(void)
 {
 	return sev_status & MSR_AMD64_SEV_SNP_ENABLED;
@@ -145,8 +173,8 @@ static void __page_state_change(unsigned long paddr, enum psc_op op)
 	 * If private -> shared then invalidate the page before requesting the
 	 * state change in the RMP table.
 	 */
-	if (op == SNP_PAGE_STATE_SHARED && pvalidate(paddr, RMP_PG_SIZE_4K, 0))
-		sev_es_terminate(SEV_TERM_SET_LINUX, GHCB_TERM_PVALIDATE);
+	if (op == SNP_PAGE_STATE_SHARED)
+		pvalidate_4k_page(paddr, paddr, false);
 
 	/* Issue VMGEXIT to change the page state in RMP table. */
 	sev_es_wr_ghcb_msr(GHCB_MSR_PSC_REQ_GFN(paddr >> PAGE_SHIFT, op));
@@ -161,8 +189,8 @@ static void __page_state_change(unsigned long paddr, enum psc_op op)
 	 * Now that page state is changed in the RMP table, validate it so that it is
 	 * consistent with the RMP entry.
 	 */
-	if (op == SNP_PAGE_STATE_PRIVATE && pvalidate(paddr, RMP_PG_SIZE_4K, 1))
-		sev_es_terminate(SEV_TERM_SET_LINUX, GHCB_TERM_PVALIDATE);
+	if (op == SNP_PAGE_STATE_PRIVATE)
+		pvalidate_4k_page(paddr, paddr, true);
 }
 
 void snp_set_page_private(unsigned long paddr)
@@ -255,6 +283,15 @@ void sev_es_shutdown_ghcb(void)
 	if (!sev_es_check_cpu_features())
 		error("SEV-ES CPU Features missing.");
 
+	/*
+	 * This is used to determine whether to use the GHCB MSR protocol or
+	 * the GHCB shared page to perform a GHCB request. Since the GHCB page
+	 * is being changed to encrypted, it can't be used to perform GHCB
+	 * requests. Clear the boot_ghcb variable so that the GHCB MSR protocol
+	 * is used to change the GHCB page over to an encrypted page.
+	 */
+	boot_ghcb = NULL;
+
 	/*
 	 * GHCB Page must be flushed from the cache and mapped encrypted again.
 	 * Otherwise the running kernel will see strange cache effects when
diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index 3abc2d759db7..01e3866c4d61 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -187,6 +187,31 @@ struct svsm_ca {
 #define SVSM_ERR_INVALID_PARAMETER		0x80000005
 #define SVSM_ERR_INVALID_REQUEST		0x80000006
 #define SVSM_ERR_BUSY				0x80000007
+#define SVSM_PVALIDATE_FAIL_SIZEMISMATCH	0x80001006
+
+/*
+ * The SVSM PVALIDATE related structures
+ */
+struct svsm_pvalidate_entry {
+	u64 page_size		: 2,
+	    action		: 1,
+	    ignore_cf		: 1,
+	    rsvd		: 8,
+	    pfn			: 52;
+};
+
+struct svsm_pvalidate_call {
+	u16 num_entries;
+	u16 cur_index;
+
+	u8 rsvd1[4];
+
+	struct svsm_pvalidate_entry entry[];
+};
+
+#define SVSM_PVALIDATE_MAX_COUNT	((sizeof_field(struct svsm_ca, svsm_buffer) -		\
+					  offsetof(struct svsm_pvalidate_call, entry)) /	\
+					 sizeof(struct svsm_pvalidate_entry))
 
 /*
  * SVSM protocol structure
@@ -207,6 +232,7 @@ struct svsm_call {
 
 #define SVSM_CORE_CALL(x)		((0ULL << 32) | (x))
 #define SVSM_CORE_REMAP_CA		0
+#define SVSM_CORE_PVALIDATE		1
 
 #ifdef CONFIG_AMD_MEM_ENCRYPT
 extern void __sev_es_ist_enter(struct pt_regs *regs);
diff --git a/arch/x86/kernel/sev-shared.c b/arch/x86/kernel/sev-shared.c
index 00173deefc46..c274fa826ef0 100644
--- a/arch/x86/kernel/sev-shared.c
+++ b/arch/x86/kernel/sev-shared.c
@@ -40,6 +40,10 @@ static u8 snp_vmpl __ro_after_init;
 static struct svsm_ca *boot_svsm_caa __ro_after_init;
 static u64 boot_svsm_caa_pa __ro_after_init;
 
+static struct svsm_ca *svsm_get_caa(void);
+static u64 svsm_get_caa_pa(void);
+static int svsm_perform_call_protocol(struct svsm_call *call);
+
 /* I/O parameters for CPUID-related helpers */
 struct cpuid_leaf {
 	u32 fn;
@@ -1216,19 +1220,97 @@ static void __head setup_cpuid_table(const struct cc_blob_sev_info *cc_info)
 	}
 }
 
-static void pvalidate_pages(struct snp_psc_desc *desc)
+static void svsm_pval_terminate(struct svsm_pvalidate_call *pc, int ret, u64 svsm_ret)
+{
+	unsigned int page_size;
+	bool action;
+	u64 pfn;
+
+	pfn = pc->entry[pc->cur_index].pfn;
+	action = pc->entry[pc->cur_index].action;
+	page_size = pc->entry[pc->cur_index].page_size;
+
+	WARN(1, "PVALIDATE failure: pfn 0x%llx, action=%u, size=%u - ret=%d, svsm_ret=0x%llx\n",
+	     pfn, action, page_size, ret, svsm_ret);
+	sev_es_terminate(SEV_TERM_SET_LINUX, GHCB_TERM_PVALIDATE);
+}
+
+static void pval_terminate(u64 pfn, bool action, unsigned int page_size, int ret)
+{
+	WARN(1, "PVALIDATE failure: pfn 0x%llx, action=%u, size=%u - ret=%d\n",
+	     pfn, action, page_size, ret);
+	sev_es_terminate(SEV_TERM_SET_LINUX, GHCB_TERM_PVALIDATE);
+}
+
+static void svsm_pval_4k_page(unsigned long paddr, bool validate)
+{
+	struct svsm_pvalidate_call *pc;
+	struct svsm_call call = {};
+	unsigned long flags;
+	u64 pc_pa;
+	int ret;
+
+	/*
+	 * This can be called very early in the boot, use native functions in
+	 * order to avoid paravirt issues.
+	 */
+	flags = native_local_irq_save();
+
+	call.caa = svsm_get_caa();
+
+	pc = (struct svsm_pvalidate_call *)call.caa->svsm_buffer;
+	pc_pa = svsm_get_caa_pa() + offsetof(struct svsm_ca, svsm_buffer);
+
+	pc->num_entries = 1;
+	pc->cur_index   = 0;
+	pc->entry[0].page_size = RMP_PG_SIZE_4K;
+	pc->entry[0].action    = validate;
+	pc->entry[0].ignore_cf = 0;
+	pc->entry[0].pfn       = paddr >> PAGE_SHIFT;
+
+	/* Protocol 0, Call ID 1 */
+	call.rax = SVSM_CORE_CALL(SVSM_CORE_PVALIDATE);
+	call.rcx = pc_pa;
+
+	ret = svsm_perform_call_protocol(&call);
+	if (ret)
+		svsm_pval_terminate(pc, ret, call.rax_out);
+
+	native_local_irq_restore(flags);
+}
+
+static void pvalidate_4k_page(unsigned long vaddr, unsigned long paddr, bool validate)
+{
+	int ret;
+
+	/*
+	 * This can be called very early in the boot, so use rip-relative
+	 * references as needed.
+	 */
+	if (RIP_REL_REF(snp_vmpl)) {
+		svsm_pval_4k_page(paddr, validate);
+	} else {
+		ret = pvalidate(vaddr, RMP_PG_SIZE_4K, validate);
+		if (ret)
+			pval_terminate(PHYS_PFN(paddr), validate, RMP_PG_SIZE_4K, ret);
+	}
+}
+
+static void pval_pages(struct snp_psc_desc *desc)
 {
 	struct psc_entry *e;
 	unsigned long vaddr;
 	unsigned int size;
 	unsigned int i;
 	bool validate;
+	u64 pfn;
 	int rc;
 
 	for (i = 0; i <= desc->hdr.end_entry; i++) {
 		e = &desc->entries[i];
 
-		vaddr = (unsigned long)pfn_to_kaddr(e->gfn);
+		pfn = e->gfn;
+		vaddr = (unsigned long)pfn_to_kaddr(pfn);
 		size = e->pagesize ? RMP_PG_SIZE_2M : RMP_PG_SIZE_4K;
 		validate = e->operation == SNP_PAGE_STATE_PRIVATE;
 
@@ -1236,20 +1318,170 @@ static void pvalidate_pages(struct snp_psc_desc *desc)
 		if (rc == PVALIDATE_FAIL_SIZEMISMATCH && size == RMP_PG_SIZE_2M) {
 			unsigned long vaddr_end = vaddr + PMD_SIZE;
 
-			for (; vaddr < vaddr_end; vaddr += PAGE_SIZE) {
+			for (; vaddr < vaddr_end; vaddr += PAGE_SIZE, pfn++) {
 				rc = pvalidate(vaddr, RMP_PG_SIZE_4K, validate);
 				if (rc)
-					break;
+					pval_terminate(pfn, validate, RMP_PG_SIZE_4K, rc);
 			}
-		}
-
-		if (rc) {
-			WARN(1, "Failed to validate address 0x%lx ret %d", vaddr, rc);
-			sev_es_terminate(SEV_TERM_SET_LINUX, GHCB_TERM_PVALIDATE);
+		} else if (rc) {
+			pval_terminate(pfn, validate, size, rc);
 		}
 	}
 }
 
+static u64 svsm_build_ca_from_pfn_range(u64 pfn, u64 pfn_end, bool action,
+					struct svsm_pvalidate_call *pc)
+{
+	struct svsm_pvalidate_entry *pe;
+
+	/* Nothing in the CA yet */
+	pc->num_entries = 0;
+	pc->cur_index   = 0;
+
+	pe = &pc->entry[0];
+
+	while (pfn < pfn_end) {
+		pe->page_size = RMP_PG_SIZE_4K;
+		pe->action    = action;
+		pe->ignore_cf = 0;
+		pe->pfn       = pfn;
+
+		pe++;
+		pfn++;
+
+		pc->num_entries++;
+		if (pc->num_entries == SVSM_PVALIDATE_MAX_COUNT)
+			break;
+	}
+
+	return pfn;
+}
+
+static void svsm_build_ca_from_psc_desc(struct snp_psc_desc *desc,
+					struct svsm_pvalidate_call *pc)
+{
+	struct svsm_pvalidate_entry *pe;
+	unsigned int desc_entry;
+	struct psc_entry *e;
+
+	desc_entry = desc->hdr.cur_entry;
+
+	/* Nothing in the CA yet */
+	pc->num_entries = 0;
+	pc->cur_index   = 0;
+
+	pe = &pc->entry[0];
+	e  = &desc->entries[desc_entry];
+
+	while (desc_entry <= desc->hdr.end_entry) {
+		pe->page_size = e->pagesize ? RMP_PG_SIZE_2M : RMP_PG_SIZE_4K;
+		pe->action    = e->operation == SNP_PAGE_STATE_PRIVATE;
+		pe->ignore_cf = 0;
+		pe->pfn       = e->gfn;
+
+		pe++;
+		e++;
+
+		desc_entry++;
+		pc->num_entries++;
+		if (pc->num_entries == SVSM_PVALIDATE_MAX_COUNT)
+			break;
+	}
+
+	desc->hdr.cur_entry = desc_entry;
+}
+
+static void svsm_pval_pages(struct snp_psc_desc *desc)
+{
+	struct svsm_pvalidate_entry pv_4k[VMGEXIT_PSC_MAX_ENTRY];
+	unsigned int i, pv_4k_count = 0;
+	struct svsm_pvalidate_call *pc;
+	struct svsm_call call = {};
+	unsigned long flags;
+	bool action;
+	u64 pc_pa;
+	int ret;
+
+	/*
+	 * This can be called very early in the boot, use native functions in
+	 * order to avoid paravirt issues.
+	 */
+	flags = native_local_irq_save();
+
+	/*
+	 * The SVSM calling area (CA) can support processing 510 entries at a
+	 * time. Loop through the Page State Change descriptor until the CA is
+	 * full or the last entry in the descriptor is reached, at which time
+	 * the SVSM is invoked. This repeats until all entries in the descriptor
+	 * are processed.
+	 */
+	call.caa = svsm_get_caa();
+
+	pc = (struct svsm_pvalidate_call *)call.caa->svsm_buffer;
+	pc_pa = svsm_get_caa_pa() + offsetof(struct svsm_ca, svsm_buffer);
+
+	/* Protocol 0, Call ID 1 */
+	call.rax = SVSM_CORE_CALL(SVSM_CORE_PVALIDATE);
+	call.rcx = pc_pa;
+
+	while (desc->hdr.cur_entry <= desc->hdr.end_entry) {
+		svsm_build_ca_from_psc_desc(desc, pc);
+
+		do {
+			ret = svsm_perform_call_protocol(&call);
+			if (ret) {
+				/*
+				 * Check if the entry failed because of an RMP mismatch (a
+				 * PVALIDATE at 2M was requested, but the page is mapped in
+				 * the RMP as 4K).
+				 */
+				if (call.rax_out == SVSM_PVALIDATE_FAIL_SIZEMISMATCH &&
+				    pc->entry[pc->cur_index].page_size == RMP_PG_SIZE_2M) {
+					/* Save this entry for post-processing at 4K */
+					pv_4k[pv_4k_count++] = pc->entry[pc->cur_index];
+
+					/* Skip to the next one unless at the end of the list */
+					pc->cur_index++;
+					if (pc->cur_index < pc->num_entries)
+						ret = -EAGAIN;
+					else
+						ret = 0;
+				}
+			}
+		} while (ret == -EAGAIN);
+
+		if (ret)
+			svsm_pval_terminate(pc, ret, call.rax_out);
+	}
+
+	/* Process any entries that failed to be validated at 2M and validate them at 4K */
+	for (i = 0; i < pv_4k_count; i++) {
+		u64 pfn, pfn_end;
+
+		action  = pv_4k[i].action;
+		pfn     = pv_4k[i].pfn;
+		pfn_end = pfn + 512;
+
+		while (pfn < pfn_end) {
+			pfn = svsm_build_ca_from_pfn_range(pfn, pfn_end, action, pc);
+
+			ret = svsm_perform_call_protocol(&call);
+			if (ret)
+				svsm_pval_terminate(pc, ret, call.rax_out);
+		}
+	}
+
+	native_local_irq_restore(flags);
+}
+
+static void pvalidate_pages(struct snp_psc_desc *desc)
+{
+	if (snp_vmpl)
+		svsm_pval_pages(desc);
+	else
+		pval_pages(desc);
+}
+
 static int vmgexit_psc(struct ghcb *ghcb, struct snp_psc_desc *desc)
 {
 	int cur_entry, end_entry, ret = 0;
diff --git a/arch/x86/kernel/sev.c b/arch/x86/kernel/sev.c
index 6bab3244a3b9..b5c18ed4c572 100644
--- a/arch/x86/kernel/sev.c
+++ b/arch/x86/kernel/sev.c
@@ -626,6 +626,17 @@ static struct svsm_ca *svsm_get_caa(void)
 						    : RIP_REL_REF(boot_svsm_caa);
 }
 
+static u64 svsm_get_caa_pa(void)
+{
+	/*
+	 * Use rip-relative references when called early in the boot. If
+	 * cas_initialized is set, then it is late in the boot and no need
+	 * to worry about rip-relative references.
+	 */
+	return RIP_REL_REF(sev_cfg).cas_initialized ? this_cpu_read(svsm_caa_pa)
+						    : RIP_REL_REF(boot_svsm_caa_pa);
+}
+
 static noinstr void __sev_put_ghcb(struct ghcb_state *state)
 {
 	struct sev_es_runtime_data *data;
@@ -798,7 +809,6 @@ early_set_pages_state(unsigned long vaddr, unsigned long paddr,
 {
 	unsigned long paddr_end;
 	u64 val;
-	int ret;
 
 	vaddr = vaddr & PAGE_MASK;
 
@@ -806,12 +816,9 @@ early_set_pages_state(unsigned long vaddr, unsigned long paddr,
 	paddr_end = paddr + (npages << PAGE_SHIFT);
 
 	while (paddr < paddr_end) {
-		if (op == SNP_PAGE_STATE_SHARED) {
-			/* Page validation must be rescinded before changing to shared */
-			ret = pvalidate(vaddr, RMP_PG_SIZE_4K, false);
-			if (WARN(ret, "Failed to validate address 0x%lx ret %d", paddr, ret))
-				goto e_term;
-		}
+		/* Page validation must be rescinded before changing to shared */
+		if (op == SNP_PAGE_STATE_SHARED)
+			pvalidate_4k_page(vaddr, paddr, false);
 
 		/*
 		 * Use the MSR protocol because this function can be called before
@@ -833,12 +840,9 @@ early_set_pages_state(unsigned long vaddr, unsigned long paddr,
 			 paddr, GHCB_MSR_PSC_RESP_VAL(val)))
 			goto e_term;
 
-		if (op == SNP_PAGE_STATE_PRIVATE) {
-			/* Page validation must be performed after changing to private */
-			ret = pvalidate(vaddr, RMP_PG_SIZE_4K, true);
-			if (WARN(ret, "Failed to validate address 0x%lx ret %d", paddr, ret))
-				goto e_term;
-		}
+		/* Page validation must be performed after changing to private */
+		if (op == SNP_PAGE_STATE_PRIVATE)
+			pvalidate_4k_page(vaddr, paddr, true);
 
 		vaddr += PAGE_SIZE;
 		paddr += PAGE_SIZE;

---

## [6] Tom Lendacky — 2024-06-05
*Subject: [PATCH v5 05/13] x86/sev: Use the SVSM to create a vCPU when not in VMPL0*

Using the RMPADJUST instruction, the VSMA attribute can only be changed
at VMPL0. An SVSM will be present when running at VMPL1 or a lower
privilege level.

When an SVSM is present, use the SVSM_CORE_CREATE_VCPU call or the
SVSM_CORE_DESTROY_VCPU call to perform VMSA attribute changes. Use the
VMPL level supplied by the SVSM for the VMSA when starting the AP.

Signed-off-by: Tom Lendacky <thomas.lendacky@amd.com>
---
 arch/x86/include/asm/sev.h |  2 +
 arch/x86/kernel/sev.c      | 75 ++++++++++++++++++++++++++++----------
 2 files changed, 57 insertions(+), 20 deletions(-)

diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index 01e3866c4d61..36cd7aebaa9b 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -233,6 +233,8 @@ struct svsm_call {
 #define SVSM_CORE_CALL(x)		((0ULL << 32) | (x))
 #define SVSM_CORE_REMAP_CA		0
 #define SVSM_CORE_PVALIDATE		1
+#define SVSM_CORE_CREATE_VCPU		2
+#define SVSM_CORE_DELETE_VCPU		3
 
 #ifdef CONFIG_AMD_MEM_ENCRYPT
 extern void __sev_es_ist_enter(struct pt_regs *regs);
diff --git a/arch/x86/kernel/sev.c b/arch/x86/kernel/sev.c
index b5c18ed4c572..ea4677177396 100644
--- a/arch/x86/kernel/sev.c
+++ b/arch/x86/kernel/sev.c
@@ -1006,22 +1006,50 @@ void snp_accept_memory(phys_addr_t start, phys_addr_t end)
 	set_pages_state(vaddr, npages, SNP_PAGE_STATE_PRIVATE);
 }
 
-static int snp_set_vmsa(void *va, bool vmsa)
+static int snp_set_vmsa(void *va, void *caa, int apic_id, bool make_vmsa)
 {
-	u64 attrs;
+	int ret;
 
-	/*
-	 * Running at VMPL0 allows the kernel to change the VMSA bit for a page
-	 * using the RMPADJUST instruction. However, for the instruction to
-	 * succeed it must target the permissions of a lesser privileged
-	 * (higher numbered) VMPL level, so use VMPL1 (refer to the RMPADJUST
-	 * instruction in the AMD64 APM Volume 3).
-	 */
-	attrs = 1;
-	if (vmsa)
-		attrs |= RMPADJUST_VMSA_PAGE_BIT;
+	if (snp_vmpl) {
+		struct svsm_call call = {};
+		unsigned long flags;
 
-	return rmpadjust((unsigned long)va, RMP_PG_SIZE_4K, attrs);
+		local_irq_save(flags);
+
+		call.caa = this_cpu_read(svsm_caa);
+		call.rcx = __pa(va);
+
+		if (make_vmsa) {
+			/* Protocol 0, Call ID 2 */
+			call.rax = SVSM_CORE_CALL(SVSM_CORE_CREATE_VCPU);
+			call.rdx = __pa(caa);
+			call.r8  = apic_id;
+		} else {
+			/* Protocol 0, Call ID 3 */
+			call.rax = SVSM_CORE_CALL(SVSM_CORE_DELETE_VCPU);
+		}
+
+		ret = svsm_perform_call_protocol(&call);
+
+		local_irq_restore(flags);
+	} else {
+		u64 attrs;
+
+		/*
+		 * Running at VMPL0 allows the kernel to change the VMSA bit for a page
+		 * using the RMPADJUST instruction. However, for the instruction to
+		 * succeed it must target the permissions of a lesser privileged
+		 * (higher numbered) VMPL level, so use VMPL1 (refer to the RMPADJUST
+		 * instruction in the AMD64 APM Volume 3).
+		 */
+		attrs = 1;
+		if (make_vmsa)
+			attrs |= RMPADJUST_VMSA_PAGE_BIT;
+
+		ret = rmpadjust((unsigned long)va, RMP_PG_SIZE_4K, attrs);
+	}
+
+	return ret;
 }
 
 #define __ATTR_BASE		(SVM_SELECTOR_P_MASK | SVM_SELECTOR_S_MASK)
@@ -1055,11 +1083,11 @@ static void *snp_alloc_vmsa_page(int cpu)
 	return page_address(p + 1);
 }
 
-static void snp_cleanup_vmsa(struct sev_es_save_area *vmsa)
+static void snp_cleanup_vmsa(struct sev_es_save_area *vmsa, int apic_id)
 {
 	int err;
 
-	err = snp_set_vmsa(vmsa, false);
+	err = snp_set_vmsa(vmsa, NULL, apic_id, false);
 	if (err)
 		pr_err("clear VMSA page failed (%u), leaking page\n", err);
 	else
@@ -1070,6 +1098,7 @@ static int wakeup_cpu_via_vmgexit(u32 apic_id, unsigned long start_ip)
 {
 	struct sev_es_save_area *cur_vmsa, *vmsa;
 	struct ghcb_state state;
+	struct svsm_ca *caa;
 	unsigned long flags;
 	struct ghcb *ghcb;
 	u8 sipi_vector;
@@ -1116,6 +1145,9 @@ static int wakeup_cpu_via_vmgexit(u32 apic_id, unsigned long start_ip)
 	if (!vmsa)
 		return -ENOMEM;
 
+	/* If an SVSM is present, the SVSM per-CPU CAA will be !NULL */
+	caa = per_cpu(svsm_caa, cpu);
+
 	/* CR4 should maintain the MCE value */
 	cr4 = native_read_cr4() & X86_CR4_MCE;
 
@@ -1163,11 +1195,11 @@ static int wakeup_cpu_via_vmgexit(u32 apic_id, unsigned long start_ip)
 	 *   VMPL level
 	 *   SEV_FEATURES (matches the SEV STATUS MSR right shifted 2 bits)
 	 */
-	vmsa->vmpl		= 0;
+	vmsa->vmpl		= snp_vmpl;
 	vmsa->sev_features	= sev_status >> 2;
 
 	/* Switch the page over to a VMSA page now that it is initialized */
-	ret = snp_set_vmsa(vmsa, true);
+	ret = snp_set_vmsa(vmsa, caa, apic_id, true);
 	if (ret) {
 		pr_err("set VMSA page failed (%u)\n", ret);
 		free_page((unsigned long)vmsa);
@@ -1183,7 +1215,10 @@ static int wakeup_cpu_via_vmgexit(u32 apic_id, unsigned long start_ip)
 	vc_ghcb_invalidate(ghcb);
 	ghcb_set_rax(ghcb, vmsa->sev_features);
 	ghcb_set_sw_exit_code(ghcb, SVM_VMGEXIT_AP_CREATION);
-	ghcb_set_sw_exit_info_1(ghcb, ((u64)apic_id << 32) | SVM_VMGEXIT_AP_CREATE);
+	ghcb_set_sw_exit_info_1(ghcb,
+				((u64)apic_id << 32)	|
+				((u64)snp_vmpl << 16)	|
+				SVM_VMGEXIT_AP_CREATE);
 	ghcb_set_sw_exit_info_2(ghcb, __pa(vmsa));
 
 	sev_es_wr_ghcb_msr(__pa(ghcb));
@@ -1201,13 +1236,13 @@ static int wakeup_cpu_via_vmgexit(u32 apic_id, unsigned long start_ip)
 
 	/* Perform cleanup if there was an error */
 	if (ret) {
-		snp_cleanup_vmsa(vmsa);
+		snp_cleanup_vmsa(vmsa, apic_id);
 		vmsa = NULL;
 	}
 
 	/* Free up any previous VMSA page */
 	if (cur_vmsa)
-		snp_cleanup_vmsa(cur_vmsa);
+		snp_cleanup_vmsa(cur_vmsa, apic_id);
 
 	/* Record the current VMSA page */
 	per_cpu(sev_vmsa, cpu) = vmsa;

---

## [7] Tom Lendacky — 2024-06-05
*Subject: [PATCH v5 06/13] x86/sev: Provide SVSM discovery support*

The SVSM specification documents an alternative method of discovery for
the SVSM using a reserved CPUID bit and a reserved MSR. This is intended
for guest components that do not have access to the secrets page in order
for those components to call the SVSM (e.g. UEFI runtime services).

For the CPUID support, update the SNP CPUID table to set bit 28 of the
EAX register of the 0x8000001f leaf when an SVSM is present. This bit
has been reserved for use in this capacity.

For the MSR support, a new reserved MSR 0xc001f000 has been defined. A #VC
should be generated when accessing this MSR. The #VC handler is expected
to ignore writes to this MSR and return the physical calling area address
(CAA) on reads of this MSR.

While the CPUID leaf is updated, allowing the creation of a CPU feature,
the code will continue to use the VMPL level as an indication of the
presence of an SVSM. This is because the SVSM can be called well before
the CPU feature is in place and a non-zero VMPL requires that an SVSM be
present.

Signed-off-by: Tom Lendacky <thomas.lendacky@amd.com>
---
 arch/x86/include/asm/cpufeatures.h |  1 +
 arch/x86/include/asm/msr-index.h   |  2 ++
 arch/x86/kernel/sev-shared.c       | 11 +++++++++++
 arch/x86/kernel/sev.c              | 11 +++++++++++
 4 files changed, 25 insertions(+)

diff --git a/arch/x86/include/asm/cpufeatures.h b/arch/x86/include/asm/cpufeatures.h
index 3c7434329661..1826f1f94111 100644
--- a/arch/x86/include/asm/cpufeatures.h
+++ b/arch/x86/include/asm/cpufeatures.h
@@ -446,6 +446,7 @@
 #define X86_FEATURE_V_TSC_AUX		(19*32+ 9) /* "" Virtual TSC_AUX */
 #define X86_FEATURE_SME_COHERENT	(19*32+10) /* "" AMD hardware-enforced cache coherency */
 #define X86_FEATURE_DEBUG_SWAP		(19*32+14) /* AMD SEV-ES full debug state swap support */
+#define X86_FEATURE_SVSM		(19*32+28) /* SVSM present */
 
 /* AMD-defined Extended Feature 2 EAX, CPUID level 0x80000021 (EAX), word 20 */
 #define X86_FEATURE_NO_NESTED_DATA_BP	(20*32+ 0) /* "" No Nested Data Breakpoints */
diff --git a/arch/x86/include/asm/msr-index.h b/arch/x86/include/asm/msr-index.h
index e022e6eb766c..45ffa27569f4 100644
--- a/arch/x86/include/asm/msr-index.h
+++ b/arch/x86/include/asm/msr-index.h
@@ -660,6 +660,8 @@
 #define MSR_AMD64_RMP_BASE		0xc0010132
 #define MSR_AMD64_RMP_END		0xc0010133
 
+#define MSR_SVSM_CAA			0xc001f000
+
 /* AMD Collaborative Processor Performance Control MSRs */
 #define MSR_AMD_CPPC_CAP1		0xc00102b0
 #define MSR_AMD_CPPC_ENABLE		0xc00102b1
diff --git a/arch/x86/kernel/sev-shared.c b/arch/x86/kernel/sev-shared.c
index c274fa826ef0..e91fcffcf602 100644
--- a/arch/x86/kernel/sev-shared.c
+++ b/arch/x86/kernel/sev-shared.c
@@ -1646,6 +1646,8 @@ static enum es_result vc_check_opcode_bytes(struct es_em_ctxt *ctxt,
 static bool __head svsm_setup_ca(const struct cc_blob_sev_info *cc_info)
 {
 	struct snp_secrets_page *secrets_page;
+	struct snp_cpuid_table *cpuid_table;
+	unsigned int i;
 	u64 caa;
 
 	BUILD_BUG_ON(sizeof(*secrets_page) != PAGE_SIZE);
@@ -1694,5 +1696,14 @@ static bool __head svsm_setup_ca(const struct cc_blob_sev_info *cc_info)
 	RIP_REL_REF(boot_svsm_caa) = (struct svsm_ca *)caa;
 	RIP_REL_REF(boot_svsm_caa_pa) = caa;
 
+	/* Advertise the SVSM presence via CPUID. */
+	cpuid_table = (struct snp_cpuid_table *)snp_cpuid_get_table();
+	for (i = 0; i < cpuid_table->count; i++) {
+		struct snp_cpuid_fn *fn = &cpuid_table->fn[i];
+
+		if (fn->eax_in == 0x8000001f)
+			fn->eax |= BIT(28);
+	}
+
 	return true;
 }
diff --git a/arch/x86/kernel/sev.c b/arch/x86/kernel/sev.c
index ea4677177396..5ba1c481b867 100644
--- a/arch/x86/kernel/sev.c
+++ b/arch/x86/kernel/sev.c
@@ -1337,6 +1337,17 @@ static enum es_result vc_handle_msr(struct ghcb *ghcb, struct es_em_ctxt *ctxt)
 	/* Is it a WRMSR? */
 	exit_info_1 = (ctxt->insn.opcode.bytes[1] == 0x30) ? 1 : 0;
 
+	if (regs->cx == MSR_SVSM_CAA) {
+		/* Writes to the SVSM CAA msr are ignored */
+		if (exit_info_1)
+			return ES_OK;
+
+		regs->ax = lower_32_bits(this_cpu_read(svsm_caa_pa));
+		regs->dx = upper_32_bits(this_cpu_read(svsm_caa_pa));
+
+		return ES_OK;
+	}
+
 	ghcb_set_rcx(ghcb, regs->cx);
 	if (exit_info_1) {
 		ghcb_set_rax(ghcb, regs->ax);

---

## [8] Tom Lendacky — 2024-06-05
*Subject: [PATCH v5 07/13] x86/sev: Provide guest VMPL level to userspace*

Requesting an attestation report from userspace involves providing the
VMPL level for the report. Currently any value from 0-3 is valid because
Linux enforces running at VMPL0.

When an SVSM is present, though, Linux will not be running at VMPL0 and
only VMPL values starting at the VMPL level Linux is running at to 3 are
valid. In order to allow userspace to determine the minimum VMPL value
that can be supplied to an attestation report, create a sysfs entry that
can be used to retrieve the current VMPL level of Linux.

Signed-off-by: Tom Lendacky <thomas.lendacky@amd.com>
---
 .../ABI/testing/sysfs-devices-system-cpu      | 12 +++++
 arch/x86/kernel/sev.c                         | 44 +++++++++++++++++++
 2 files changed, 56 insertions(+)

diff --git a/Documentation/ABI/testing/sysfs-devices-system-cpu b/Documentation/ABI/testing/sysfs-devices-system-cpu
index e7e160954e79..8fd7ed9aee4e 100644
--- a/Documentation/ABI/testing/sysfs-devices-system-cpu
+++ b/Documentation/ABI/testing/sysfs-devices-system-cpu
@@ -605,6 +605,18 @@ Description:	Umwait control
 			  Note that a value of zero means there is no limit.
 			  Low order two bits must be zero.
 
+What:		/sys/devices/system/cpu/sev
+		/sys/devices/system/cpu/sev/vmpl
+Date:		May 2024
+Contact:	Linux kernel mailing list <linux-kernel@vger.kernel.org>
+Description:	Secure Encrypted Virtualization (SEV) information
+
+		This directory is only present when running as an SEV-SNP guest.
+
+		vmpl: Reports the Virtual Machine Privilege Level (VMPL) at which
+		      the SEV-SNP guest is running.
+
+
 What:		/sys/devices/system/cpu/svm
 Date:		August 2019
 Contact:	Linux kernel mailing list <linux-kernel@vger.kernel.org>
diff --git a/arch/x86/kernel/sev.c b/arch/x86/kernel/sev.c
index 5ba1c481b867..d09844db2361 100644
--- a/arch/x86/kernel/sev.c
+++ b/arch/x86/kernel/sev.c
@@ -2501,3 +2501,47 @@ void __init snp_remap_svsm_ca(void)
 	/* Update the CAA to a proper kernel address */
 	boot_svsm_caa = &boot_svsm_ca_page;
 }
+
+static ssize_t vmpl_show(struct kobject *kobj,
+			 struct kobj_attribute *attr, char *buf)
+{
+	return sysfs_emit(buf, "%d\n", snp_vmpl);
+}
+
+static struct kobj_attribute vmpl_attr = __ATTR_RO(vmpl);
+
+static struct attribute *vmpl_attrs[] = {
+	&vmpl_attr.attr,
+	NULL
+};
+
+static struct attribute_group sev_attr_group = {
+	.attrs = vmpl_attrs,
+};
+
+static int __init sev_sysfs_init(void)
+{
+	struct kobject *sev_kobj;
+	struct device *dev_root;
+	int ret;
+
+	if (!cc_platform_has(CC_ATTR_GUEST_SEV_SNP))
+		return -ENODEV;
+
+	dev_root = bus_get_dev_root(&cpu_subsys);
+	if (!dev_root)
+		return -ENODEV;
+
+	sev_kobj = kobject_create_and_add("sev", &dev_root->kobj);
+	put_device(dev_root);
+
+	if (!sev_kobj)
+		return -ENOMEM;
+
+	ret = sysfs_create_group(sev_kobj, &sev_attr_group);
+	if (ret)
+		kobject_put(sev_kobj);
+
+	return ret;
+}
+arch_initcall(sev_sysfs_init);

---

## [9] Tom Lendacky — 2024-06-05
*Subject: [PATCH v5 08/13] virt: sev-guest: Choose the VMPCK key based on executing VMPL*

Currently, the sev-guest driver uses the vmpck-0 key by default. When an
SVSM is present, the kernel is running at a VMPL other than 0 and the
vmpck-0 key is no longer available. If a specific vmpck key has not be
requested by the user via the vmpck_id module parameter, choose the vmpck
key based on the active VMPL level.

Signed-off-by: Tom Lendacky <thomas.lendacky@amd.com>
---
 Documentation/virt/coco/sev-guest.rst   | 11 +++++++++++
 arch/x86/include/asm/sev.h              | 11 +++++++++--
 arch/x86/kernel/sev-shared.c            |  3 ++-
 drivers/virt/coco/sev-guest/sev-guest.c | 17 ++++++++++++++---
 4 files changed, 36 insertions(+), 6 deletions(-)

diff --git a/Documentation/virt/coco/sev-guest.rst b/Documentation/virt/coco/sev-guest.rst
index e1eaf6a830ce..9d00967a5b2b 100644
--- a/Documentation/virt/coco/sev-guest.rst
+++ b/Documentation/virt/coco/sev-guest.rst
@@ -204,6 +204,17 @@ has taken care to make use of the SEV-SNP CPUID throughout all stages of boot.
 Otherwise, guest owner attestation provides no assurance that the kernel wasn't
 fed incorrect values at some point during boot.
 
+4. SEV Guest Driver Communication Key
+=====================================
+
+Communication between an SEV guest and the SEV firmware in the AMD Secure
+Processor (ASP, aka PSP) is protected by a VM Platform Communication Key
+(VMPCK). By default, the sev-guest driver uses the VMPCK associated with the
+VM Privilege Level (VMPL) at which the guest is running. Should this key be
+wiped by the sev-guest driver (see the driver for reasons why a VMPCK can be
+wiped), a different key can be used by reloading the sev-guest driver and
+specifying the desired key using the vmpck_id module parameter.
+
 
 Reference
 ---------
diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index 36cd7aebaa9b..f7a966e99a73 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -237,6 +237,9 @@ struct svsm_call {
 #define SVSM_CORE_DELETE_VCPU		3
 
 #ifdef CONFIG_AMD_MEM_ENCRYPT
+
+extern u8 snp_vmpl;
+
 extern void __sev_es_ist_enter(struct pt_regs *regs);
 extern void __sev_es_ist_exit(void);
 static __always_inline void sev_es_ist_enter(struct pt_regs *regs)
@@ -320,7 +323,10 @@ u64 snp_get_unsupported_features(u64 status);
 u64 sev_get_status(void);
 void sev_show_status(void);
 void snp_remap_svsm_ca(void);
-#else
+
+#else	/* !CONFIG_AMD_MEM_ENCRYPT */
+
+#define snp_vmpl 0
 static inline void sev_es_ist_enter(struct pt_regs *regs) { }
 static inline void sev_es_ist_exit(void) { }
 static inline int sev_es_setup_ap_jump_table(struct real_mode_header *rmh) { return 0; }
@@ -350,7 +356,8 @@ static inline u64 snp_get_unsupported_features(u64 status) { return 0; }
 static inline u64 sev_get_status(void) { return 0; }
 static inline void sev_show_status(void) { }
 static inline void snp_remap_svsm_ca(void) { }
-#endif
+
+#endif	/* CONFIG_AMD_MEM_ENCRYPT */
 
 #ifdef CONFIG_KVM_AMD_SEV
 bool snp_probe_rmptable_info(void);
diff --git a/arch/x86/kernel/sev-shared.c b/arch/x86/kernel/sev-shared.c
index e91fcffcf602..10599e66c5fd 100644
--- a/arch/x86/kernel/sev-shared.c
+++ b/arch/x86/kernel/sev-shared.c
@@ -36,7 +36,8 @@
  *   early boot, both with identity mapped virtual addresses and proper kernel
  *   virtual addresses.
  */
-static u8 snp_vmpl __ro_after_init;
+u8 snp_vmpl __ro_after_init;
+EXPORT_SYMBOL_GPL(snp_vmpl);
 static struct svsm_ca *boot_svsm_caa __ro_after_init;
 static u64 boot_svsm_caa_pa __ro_after_init;
 
diff --git a/drivers/virt/coco/sev-guest/sev-guest.c b/drivers/virt/coco/sev-guest/sev-guest.c
index 654290a8e1ba..4597042f31e4 100644
--- a/drivers/virt/coco/sev-guest/sev-guest.c
+++ b/drivers/virt/coco/sev-guest/sev-guest.c
@@ -2,7 +2,7 @@
 /*
  * AMD Secure Encrypted Virtualization (SEV) guest driver interface
  *
- * Copyright (C) 2021 Advanced Micro Devices, Inc.
+ * Copyright (C) 2021-2024 Advanced Micro Devices, Inc.
  *
  * Author: Brijesh Singh <brijesh.singh@amd.com>
  */
@@ -70,8 +70,15 @@ struct snp_guest_dev {
 	u8 *vmpck;
 };
 
-static u32 vmpck_id;
-module_param(vmpck_id, uint, 0444);
+/*
+ * The VMPCK ID represents the key used by the SNP guest to communicate with the
+ * SEV firmware in the AMD Secure Processor (ASP, aka PSP). By default, the key
+ * used will be the key associated with the VMPL at which the guest is running.
+ * Should the default key be wiped (see snp_disable_vmpck()), this parameter
+ * allows for using one of the remaining VMPCKs.
+ */
+static int vmpck_id = -1;
+module_param(vmpck_id, int, 0444);
 MODULE_PARM_DESC(vmpck_id, "The VMPCK ID to use when communicating with the PSP.");
 
 /* Mutex to serialize the shared buffer access and command handling. */
@@ -923,6 +930,10 @@ static int __init sev_guest_probe(struct platform_device *pdev)
 	if (!snp_dev)
 		goto e_unmap;
 
+	/* Adjust the default VMPCK key based on the executing VMPL level */
+	if (vmpck_id == -1)
+		vmpck_id = snp_vmpl;
+
 	ret = -EINVAL;
 	snp_dev->vmpck = get_vmpck(vmpck_id, secrets, &snp_dev->os_area_msg_seqno);
 	if (!snp_dev->vmpck) {

---

## [10] Tom Lendacky — 2024-06-05
*Subject: [PATCH v5 09/13] configfs-tsm: Allow the privlevel_floor attribute to be updated*

With the introduction of an SVSM, Linux will be running at a non-zero
VMPL. Any request for an attestation report at a higher privilege VMPL
than what Linux is currently running will result in an error. Allow for
the privlevel_floor attribute to be updated dynamically so that the
attribute may be set dynamically. Set the privlevel_floor attribute to
be the value of the vmpck_id being used.

Signed-off-by: Tom Lendacky <thomas.lendacky@amd.com>
---
 drivers/virt/coco/sev-guest/sev-guest.c | 5 ++++-
 include/linux/tsm.h                     | 2 +-
 2 files changed, 5 insertions(+), 2 deletions(-)

diff --git a/drivers/virt/coco/sev-guest/sev-guest.c b/drivers/virt/coco/sev-guest/sev-guest.c
index 4597042f31e4..3560b3a8bb4d 100644
--- a/drivers/virt/coco/sev-guest/sev-guest.c
+++ b/drivers/virt/coco/sev-guest/sev-guest.c
@@ -892,7 +892,7 @@ static int sev_report_new(struct tsm_report *report, void *data)
 	return 0;
 }
 
-static const struct tsm_ops sev_tsm_ops = {
+static struct tsm_ops sev_tsm_ops = {
 	.name = KBUILD_MODNAME,
 	.report_new = sev_report_new,
 };
@@ -979,6 +979,9 @@ static int __init sev_guest_probe(struct platform_device *pdev)
 	snp_dev->input.resp_gpa = __pa(snp_dev->response);
 	snp_dev->input.data_gpa = __pa(snp_dev->certs_data);
 
+	/* Set the privlevel_floor attribute based on the vmpck_id */
+	sev_tsm_ops.privlevel_floor = vmpck_id;
+
 	ret = tsm_register(&sev_tsm_ops, snp_dev, &tsm_report_extra_type);
 	if (ret)
 		goto e_free_cert_data;
diff --git a/include/linux/tsm.h b/include/linux/tsm.h
index de8324a2223c..50c5769657d8 100644
--- a/include/linux/tsm.h
+++ b/include/linux/tsm.h
@@ -54,7 +54,7 @@ struct tsm_report {
  */
 struct tsm_ops {
 	const char *name;
-	const unsigned int privlevel_floor;
+	unsigned int privlevel_floor;
 	int (*report_new)(struct tsm_report *report, void *data);
 };

---

## [11] Tom Lendacky — 2024-06-05
*Subject: [PATCH v5 10/13] fs/configfs: Add a callback to determine attribute visibility*

In order to support dynamic decisions as to whether an attribute should be
created, add a callback that returns a bool to indicate whether the
attribute should be displayed. If no callback is registered, the attribute
is displayed by default.

Cc: Joel Becker <jlbec@evilplan.org>
Cc: Christoph Hellwig <hch@lst.de>
Co-developed-by: Dan Williams <dan.j.williams@intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
Signed-off-by: Tom Lendacky <thomas.lendacky@amd.com>
---
 fs/configfs/dir.c        | 10 ++++++++++
 include/linux/configfs.h |  3 +++
 2 files changed, 13 insertions(+)

diff --git a/fs/configfs/dir.c b/fs/configfs/dir.c
index 18677cd4e62f..43d6bde1adcc 100644
--- a/fs/configfs/dir.c
+++ b/fs/configfs/dir.c
@@ -580,6 +580,7 @@ static void detach_attrs(struct config_item * item)
 static int populate_attrs(struct config_item *item)
 {
 	const struct config_item_type *t = item->ci_type;
+	struct configfs_group_operations *ops;
 	struct configfs_attribute *attr;
 	struct configfs_bin_attribute *bin_attr;
 	int error = 0;
@@ -587,14 +588,23 @@ static int populate_attrs(struct config_item *item)
 
 	if (!t)
 		return -EINVAL;
+
+	ops = t->ct_group_ops;
+
 	if (t->ct_attrs) {
 		for (i = 0; (attr = t->ct_attrs[i]) != NULL; i++) {
+			if (ops && ops->is_visible && !ops->is_visible(item, attr, i))
+				continue;
+
 			if ((error = configfs_create_file(item, attr)))
 				break;
 		}
 	}
 	if (t->ct_bin_attrs) {
 		for (i = 0; (bin_attr = t->ct_bin_attrs[i]) != NULL; i++) {
+			if (ops && ops->is_bin_visible && !ops->is_bin_visible(item, bin_attr, i))
+				continue;
+
 			error = configfs_create_bin_file(item, bin_attr);
 			if (error)
 				break;
diff --git a/include/linux/configfs.h b/include/linux/configfs.h
index 2606711adb18..c771e9d0d0b9 100644
--- a/include/linux/configfs.h
+++ b/include/linux/configfs.h
@@ -216,6 +216,9 @@ struct configfs_group_operations {
 	struct config_group *(*make_group)(struct config_group *group, const char *name);
 	void (*disconnect_notify)(struct config_group *group, struct config_item *item);
 	void (*drop_item)(struct config_group *group, struct config_item *item);
+	bool (*is_visible)(struct config_item *item, struct configfs_attribute *attr, int n);
+	bool (*is_bin_visible)(struct config_item *item, struct configfs_bin_attribute *attr,
+			       int n);
 };
 
 struct configfs_subsystem {

---

## [12] Tom Lendacky — 2024-06-05
*Subject: [PATCH v5 11/13] x86/sev: Take advantage of configfs visibility support in TSM*

The TSM attestation report support provides multiple configfs attribute
types (both for standard and binary attributes) to allow for additional
attributes to be displayed for SNP as compared to TDX. With the ability
to hide attributes via configfs, consolidate the multiple attribute groups
into a single standard attribute group and a single binary attribute
group. Modify the TDX support to hide the attributes that were previously
"hidden" as a result of registering the selective attribute groups.

Reviewed-by: Kuppuswamy Sathyanarayanan <sathyanarayanan.kuppuswamy@linux.intel.com>
Co-developed-by: Dan Williams <dan.j.williams@intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
Signed-off-by: Tom Lendacky <thomas.lendacky@amd.com>
---
 drivers/virt/coco/sev-guest/sev-guest.c |  3 +-
 drivers/virt/coco/tdx-guest/tdx-guest.c | 26 +++++++-
 drivers/virt/coco/tsm.c                 | 86 ++++++++++++-------------
 include/linux/tsm.h                     | 38 +++++++++--
 4 files changed, 100 insertions(+), 53 deletions(-)

diff --git a/drivers/virt/coco/sev-guest/sev-guest.c b/drivers/virt/coco/sev-guest/sev-guest.c
index 3560b3a8bb4d..0c70a38c8cc0 100644
--- a/drivers/virt/coco/sev-guest/sev-guest.c
+++ b/drivers/virt/coco/sev-guest/sev-guest.c
@@ -23,6 +23,7 @@
 #include <linux/sockptr.h>
 #include <linux/cleanup.h>
 #include <linux/uuid.h>
+#include <linux/configfs.h>
 #include <uapi/linux/sev-guest.h>
 #include <uapi/linux/psp-sev.h>
 
@@ -982,7 +983,7 @@ static int __init sev_guest_probe(struct platform_device *pdev)
 	/* Set the privlevel_floor attribute based on the vmpck_id */
 	sev_tsm_ops.privlevel_floor = vmpck_id;
 
-	ret = tsm_register(&sev_tsm_ops, snp_dev, &tsm_report_extra_type);
+	ret = tsm_register(&sev_tsm_ops, snp_dev);
 	if (ret)
 		goto e_free_cert_data;
 
diff --git a/drivers/virt/coco/tdx-guest/tdx-guest.c b/drivers/virt/coco/tdx-guest/tdx-guest.c
index 1253bf76b570..2acba56ad42e 100644
--- a/drivers/virt/coco/tdx-guest/tdx-guest.c
+++ b/drivers/virt/coco/tdx-guest/tdx-guest.c
@@ -249,6 +249,28 @@ static int tdx_report_new(struct tsm_report *report, void *data)
 	return ret;
 }
 
+static bool tdx_report_attr_visible(int n)
+{
+	switch (n) {
+	case TSM_REPORT_GENERATION:
+	case TSM_REPORT_PROVIDER:
+		return true;
+	}
+
+	return false;
+}
+
+static bool tdx_report_bin_attr_visible(int n)
+{
+	switch (n) {
+	case TSM_REPORT_INBLOB:
+	case TSM_REPORT_OUTBLOB:
+		return true;
+	}
+
+	return false;
+}
+
 static long tdx_guest_ioctl(struct file *file, unsigned int cmd,
 			    unsigned long arg)
 {
@@ -281,6 +303,8 @@ MODULE_DEVICE_TABLE(x86cpu, tdx_guest_ids);
 static const struct tsm_ops tdx_tsm_ops = {
 	.name = KBUILD_MODNAME,
 	.report_new = tdx_report_new,
+	.report_attr_visible = tdx_report_attr_visible,
+	.report_bin_attr_visible = tdx_report_bin_attr_visible,
 };
 
 static int __init tdx_guest_init(void)
@@ -301,7 +325,7 @@ static int __init tdx_guest_init(void)
 		goto free_misc;
 	}
 
-	ret = tsm_register(&tdx_tsm_ops, NULL, NULL);
+	ret = tsm_register(&tdx_tsm_ops, NULL);
 	if (ret)
 		goto free_quote;
 
diff --git a/drivers/virt/coco/tsm.c b/drivers/virt/coco/tsm.c
index d1c2db83a8ca..7db534b63c9f 100644
--- a/drivers/virt/coco/tsm.c
+++ b/drivers/virt/coco/tsm.c
@@ -14,7 +14,6 @@
 
 static struct tsm_provider {
 	const struct tsm_ops *ops;
-	const struct config_item_type *type;
 	void *data;
 } provider;
 static DECLARE_RWSEM(tsm_rwsem);
@@ -252,34 +251,18 @@ static ssize_t tsm_report_auxblob_read(struct config_item *cfg, void *buf,
 }
 CONFIGFS_BIN_ATTR_RO(tsm_report_, auxblob, NULL, TSM_OUTBLOB_MAX);
 
-#define TSM_DEFAULT_ATTRS() \
-	&tsm_report_attr_generation, \
-	&tsm_report_attr_provider
-
 static struct configfs_attribute *tsm_report_attrs[] = {
-	TSM_DEFAULT_ATTRS(),
+	[TSM_REPORT_GENERATION] = &tsm_report_attr_generation,
+	[TSM_REPORT_PROVIDER] = &tsm_report_attr_provider,
+	[TSM_REPORT_PRIVLEVEL] = &tsm_report_attr_privlevel,
+	[TSM_REPORT_PRIVLEVEL_FLOOR] = &tsm_report_attr_privlevel_floor,
 	NULL,
 };
 
-static struct configfs_attribute *tsm_report_extra_attrs[] = {
-	TSM_DEFAULT_ATTRS(),
-	&tsm_report_attr_privlevel,
-	&tsm_report_attr_privlevel_floor,
-	NULL,
-};
-
-#define TSM_DEFAULT_BIN_ATTRS() \
-	&tsm_report_attr_inblob, \
-	&tsm_report_attr_outblob
-
 static struct configfs_bin_attribute *tsm_report_bin_attrs[] = {
-	TSM_DEFAULT_BIN_ATTRS(),
-	NULL,
-};
-
-static struct configfs_bin_attribute *tsm_report_bin_extra_attrs[] = {
-	TSM_DEFAULT_BIN_ATTRS(),
-	&tsm_report_attr_auxblob,
+	[TSM_REPORT_INBLOB] = &tsm_report_attr_inblob,
+	[TSM_REPORT_OUTBLOB] = &tsm_report_attr_outblob,
+	[TSM_REPORT_AUXBLOB] = &tsm_report_attr_auxblob,
 	NULL,
 };
 
@@ -297,21 +280,44 @@ static struct configfs_item_operations tsm_report_item_ops = {
 	.release = tsm_report_item_release,
 };
 
-const struct config_item_type tsm_report_default_type = {
+static bool tsm_report_is_visible(struct config_item *item,
+				  struct configfs_attribute *attr, int n)
+{
+	guard(rwsem_read)(&tsm_rwsem);
+	if (!provider.ops)
+		return false;
+
+	if (!provider.ops->report_attr_visible)
+		return true;
+
+	return provider.ops->report_attr_visible(n);
+}
+
+static bool tsm_report_is_bin_visible(struct config_item *item,
+				      struct configfs_bin_attribute *attr, int n)
+{
+	guard(rwsem_read)(&tsm_rwsem);
+	if (!provider.ops)
+		return false;
+
+	if (!provider.ops->report_bin_attr_visible)
+		return true;
+
+	return provider.ops->report_bin_attr_visible(n);
+}
+
+static struct configfs_group_operations tsm_report_attr_group_ops = {
+	.is_visible = tsm_report_is_visible,
+	.is_bin_visible = tsm_report_is_bin_visible,
+};
+
+static const struct config_item_type tsm_report_type = {
 	.ct_owner = THIS_MODULE,
 	.ct_bin_attrs = tsm_report_bin_attrs,
 	.ct_attrs = tsm_report_attrs,
 	.ct_item_ops = &tsm_report_item_ops,
+	.ct_group_ops = &tsm_report_attr_group_ops,
 };
-EXPORT_SYMBOL_GPL(tsm_report_default_type);
-
-const struct config_item_type tsm_report_extra_type = {
-	.ct_owner = THIS_MODULE,
-	.ct_bin_attrs = tsm_report_bin_extra_attrs,
-	.ct_attrs = tsm_report_extra_attrs,
-	.ct_item_ops = &tsm_report_item_ops,
-};
-EXPORT_SYMBOL_GPL(tsm_report_extra_type);
 
 static struct config_item *tsm_report_make_item(struct config_group *group,
 						const char *name)
@@ -326,7 +332,7 @@ static struct config_item *tsm_report_make_item(struct config_group *group,
 	if (!state)
 		return ERR_PTR(-ENOMEM);
 
-	config_item_init_type_name(&state->cfg, name, provider.type);
+	config_item_init_type_name(&state->cfg, name, &tsm_report_type);
 	return &state->cfg;
 }
 
@@ -353,16 +359,10 @@ static struct configfs_subsystem tsm_configfs = {
 	.su_mutex = __MUTEX_INITIALIZER(tsm_configfs.su_mutex),
 };
 
-int tsm_register(const struct tsm_ops *ops, void *priv,
-		 const struct config_item_type *type)
+int tsm_register(const struct tsm_ops *ops, void *priv)
 {
 	const struct tsm_ops *conflict;
 
-	if (!type)
-		type = &tsm_report_default_type;
-	if (!(type == &tsm_report_default_type || type == &tsm_report_extra_type))
-		return -EINVAL;
-
 	guard(rwsem_write)(&tsm_rwsem);
 	conflict = provider.ops;
 	if (conflict) {
@@ -372,7 +372,6 @@ int tsm_register(const struct tsm_ops *ops, void *priv,
 
 	provider.ops = ops;
 	provider.data = priv;
-	provider.type = type;
 	return 0;
 }
 EXPORT_SYMBOL_GPL(tsm_register);
@@ -384,7 +383,6 @@ int tsm_unregister(const struct tsm_ops *ops)
 		return -EBUSY;
 	provider.ops = NULL;
 	provider.data = NULL;
-	provider.type = NULL;
 	return 0;
 }
 EXPORT_SYMBOL_GPL(tsm_unregister);
diff --git a/include/linux/tsm.h b/include/linux/tsm.h
index 50c5769657d8..30d9d270b446 100644
--- a/include/linux/tsm.h
+++ b/include/linux/tsm.h
@@ -42,12 +42,40 @@ struct tsm_report {
 	u8 *auxblob;
 };
 
+/**
+ * enum tsm_attr_index - index used to reference report attributes
+ * @TSM_REPORT_GENERATION: index of the report generation number attribute
+ * @TSM_REPORT_PROVIDER: index of the provider name attribute
+ * @TSM_REPORT_PRIVLEVEL: index of the desired privilege level attribute
+ * @TSM_REPORT_PRIVLEVEL_FLOOR: index of the minimum allowed privileg level attribute
+ */
+enum tsm_attr_index {
+	TSM_REPORT_GENERATION,
+	TSM_REPORT_PROVIDER,
+	TSM_REPORT_PRIVLEVEL,
+	TSM_REPORT_PRIVLEVEL_FLOOR,
+};
+
+/**
+ * enum tsm_bin_attr_index - index used to reference binary report attributes
+ * @TSM_REPORT_INBLOB: index of the binary report input attribute
+ * @TSM_REPORT_OUTBLOB: index of the binary report output attribute
+ * @TSM_REPORT_AUXBLOB: index of the binary auxiliary data attribute
+ */
+enum tsm_bin_attr_index {
+	TSM_REPORT_INBLOB,
+	TSM_REPORT_OUTBLOB,
+	TSM_REPORT_AUXBLOB,
+};
+
 /**
  * struct tsm_ops - attributes and operations for tsm instances
  * @name: tsm id reflected in /sys/kernel/config/tsm/report/$report/provider
  * @privlevel_floor: convey base privlevel for nested scenarios
  * @report_new: Populate @report with the report blob and auxblob
  * (optional), return 0 on successful population, or -errno otherwise
+ * @report_attr_visible: show or hide a report attribute entry
+ * @report_bin_attr_visible: show or hide a report binary attribute entry
  *
  * Implementation specific ops, only one is expected to be registered at
  * a time i.e. only one of "sev-guest", "tdx-guest", etc.
@@ -56,14 +84,10 @@ struct tsm_ops {
 	const char *name;
 	unsigned int privlevel_floor;
 	int (*report_new)(struct tsm_report *report, void *data);
+	bool (*report_attr_visible)(int n);
+	bool (*report_bin_attr_visible)(int n);
 };
 
-extern const struct config_item_type tsm_report_default_type;
-
-/* publish @privlevel, @privlevel_floor, and @auxblob attributes */
-extern const struct config_item_type tsm_report_extra_type;
-
-int tsm_register(const struct tsm_ops *ops, void *priv,
-		 const struct config_item_type *type);
+int tsm_register(const struct tsm_ops *ops, void *priv);
 int tsm_unregister(const struct tsm_ops *ops);
 #endif /* __TSM_H */

---

## [13] Tom Lendacky — 2024-06-05
*Subject: [PATCH v5 12/13] x86/sev: Extend the config-fs attestation support for an SVSM*

When an SVSM is present, the guest can also request attestation reports
from the SVSM. These SVSM attestation reports can be used to attest the
SVSM and any services running within the SVSM.

Extend the config-fs attestation support to allow for an SVSM attestation
report. This involves creating four (4) new config-fs attributes:

  - 'service-provider' (input)
    This attribute is used to determine whether the attestation request
    should be sent to the specified service provider or to the SEV
    firmware. The SVSM service provider is represented by the value
    'svsm'.

  - 'service_guid' (input)
    Used for requesting the attestation of a single service within the
    service provider. A null GUID implies that the SVSM_ATTEST_SERVICES
    call should be used to request the attestation report. A non-null
    GUID implies that the SVSM_ATTEST_SINGLE_SERVICE call should be used.

  - 'service_manifest_version' (input)
    Used with the SVSM_ATTEST_SINGLE_SERVICE call, the service version
    represents a specific service manifest version be used for the
    attestation report.

  - 'manifestblob' (output)
    Used to return the service manifest associated with the attestation
    report.

Only display these new attributes when running under an SVSM.

Signed-off-by: Tom Lendacky <thomas.lendacky@amd.com>
---
 Documentation/ABI/testing/configfs-tsm  |  63 +++++++++
 arch/x86/include/asm/sev.h              |  31 ++++-
 arch/x86/kernel/sev.c                   |  50 +++++++
 drivers/virt/coco/sev-guest/sev-guest.c | 178 ++++++++++++++++++++++++
 drivers/virt/coco/tsm.c                 |  93 ++++++++++++-
 include/linux/tsm.h                     |  19 +++
 6 files changed, 431 insertions(+), 3 deletions(-)

diff --git a/Documentation/ABI/testing/configfs-tsm b/Documentation/ABI/testing/configfs-tsm
index dd24202b5ba5..bc8f6efa5d6f 100644
--- a/Documentation/ABI/testing/configfs-tsm
+++ b/Documentation/ABI/testing/configfs-tsm
@@ -31,6 +31,18 @@ Description:
 		Standardization v2.03 Section 4.1.8.1 MSG_REPORT_REQ.
 		https://www.amd.com/content/dam/amd/en/documents/epyc-technical-docs/specifications/56421.pdf
 
+What:		/sys/kernel/config/tsm/report/$name/manifestblob
+Date:		January, 2024
+KernelVersion:	v6.10
+Contact:	linux-coco@lists.linux.dev
+Description:
+		(RO) Optional supplemental data that a TSM may emit, visibility
+		of this attribute depends on TSM, and may be empty if no
+		manifest data is available.
+
+		See 'service_provider' for information on the format of the
+		manifest blob.
+
 What:		/sys/kernel/config/tsm/report/$name/provider
 Date:		September, 2023
 KernelVersion:	v6.7
@@ -80,3 +92,54 @@ Contact:	linux-coco@lists.linux.dev
 Description:
 		(RO) Indicates the minimum permissible value that can be written
 		to @privlevel.
+
+What:		/sys/kernel/config/tsm/report/$name/service_provider
+Date:		January, 2024
+KernelVersion:	v6.10
+Contact:	linux-coco@lists.linux.dev
+Description:
+		(WO) Attribute is visible if a TSM implementation provider
+		supports the concept of attestation reports from a service
+		provider for TVMs, like SEV-SNP running under an SVSM.
+		Specifying the service provider via this attribute will create
+		an attestation report as specified by the service provider.
+		Currently supported service-providers are:
+			svsm
+
+		For the "svsm" service provider, see the Secure VM Service Module
+		for SEV-SNP Guests v1.00 Section 7.
+		https://www.amd.com/content/dam/amd/en/documents/epyc-technical-docs/specifications/58019.pdf
+
+What:		/sys/kernel/config/tsm/report/$name/service_guid
+Date:		January, 2024
+KernelVersion:	v6.10
+Contact:	linux-coco@lists.linux.dev
+Description:
+		(WO) Attribute is visible if a TSM implementation provider
+		supports the concept of attestation reports from a service
+		provider for TVMs, like SEV-SNP running under an SVSM.
+		Specifying an empty/null GUID (00000000-0000-0000-0000-000000)
+		requests all active services within the service provider be
+		part of the attestation report. Specifying a GUID request
+		an attestation report of just the specified service using the
+		manifest form specified by the service_manifest_version
+		attribute.
+
+		See 'service_provider' for information on the format of the
+		service guid.
+
+What:		/sys/kernel/config/tsm/report/$name/service_manifest_version
+Date:		January, 2024
+KernelVersion:	v6.10
+Contact:	linux-coco@lists.linux.dev
+Description:
+		(WO) Attribute is visible if a TSM implementation provider
+		supports the concept of attestation reports from a service
+		provider for TVMs, like SEV-SNP running under an SVSM.
+		Indicates the service manifest version requested for the
+		attestation report (default 0). If this field is not set by
+		the user, the default manifest version of the service (the
+		service's initial/first manifest version) is returned.
+
+		See 'service_provider' for information on the format of the
+		service manifest version.
diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index f7a966e99a73..96897cd6b9e6 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -213,6 +213,27 @@ struct svsm_pvalidate_call {
 					  offsetof(struct svsm_pvalidate_call, entry)) /	\
 					 sizeof(struct svsm_pvalidate_entry))
 
+/*
+ * The SVSM Attestation related structures
+ */
+struct svsm_loc_entry {
+	u64 pa;
+	u32 len;
+	u8 rsvd[4];
+};
+
+struct svsm_attestation_call {
+	struct svsm_loc_entry report_buf;
+	struct svsm_loc_entry nonce;
+	struct svsm_loc_entry manifest_buf;
+	struct svsm_loc_entry certificates_buf;
+
+	/* For attesting a single service */
+	u8 service_guid[16];
+	u32 service_manifest_ver;
+	u8 rsvd[4];
+};
+
 /*
  * SVSM protocol structure
  */
@@ -236,6 +257,10 @@ struct svsm_call {
 #define SVSM_CORE_CREATE_VCPU		2
 #define SVSM_CORE_DELETE_VCPU		3
 
+#define SVSM_ATTEST_CALL(x)		((1ULL << 32) | (x))
+#define SVSM_ATTEST_SERVICES		0
+#define SVSM_ATTEST_SINGLE_SERVICE	1
+
 #ifdef CONFIG_AMD_MEM_ENCRYPT
 
 extern u8 snp_vmpl;
@@ -318,6 +343,7 @@ bool snp_init(struct boot_params *bp);
 void __noreturn snp_abort(void);
 void snp_dmi_setup(void);
 int snp_issue_guest_request(u64 exit_code, struct snp_req_data *input, struct snp_guest_request_ioctl *rio);
+int snp_issue_svsm_attest_req(u64 call_id, struct svsm_call *call, struct svsm_attestation_call *input);
 void snp_accept_memory(phys_addr_t start, phys_addr_t end);
 u64 snp_get_unsupported_features(u64 status);
 u64 sev_get_status(void);
@@ -350,7 +376,10 @@ static inline int snp_issue_guest_request(u64 exit_code, struct snp_req_data *in
 {
 	return -ENOTTY;
 }
-
+static inline int snp_issue_svsm_attest_req(u64 call_id, struct svsm_call *call, struct svsm_attestation_call *input)
+{
+	return -ENOTTY;
+}
 static inline void snp_accept_memory(phys_addr_t start, phys_addr_t end) { }
 static inline u64 snp_get_unsupported_features(u64 status) { return 0; }
 static inline u64 sev_get_status(void) { return 0; }
diff --git a/arch/x86/kernel/sev.c b/arch/x86/kernel/sev.c
index d09844db2361..f4ae1d037b04 100644
--- a/arch/x86/kernel/sev.c
+++ b/arch/x86/kernel/sev.c
@@ -2384,6 +2384,56 @@ static int __init init_sev_config(char *str)
 }
 __setup("sev=", init_sev_config);
 
+static void update_attest_input(struct svsm_call *call, struct svsm_attestation_call *input)
+{
+	/* If (new) lengths have been returned, propagate them up */
+	if (call->rcx_out != call->rcx)
+		input->manifest_buf.len = call->rcx_out;
+
+	if (call->rdx_out != call->rdx)
+		input->certificates_buf.len = call->rdx_out;
+
+	if (call->r8_out != call->r8)
+		input->report_buf.len = call->r8_out;
+}
+
+int snp_issue_svsm_attest_req(u64 call_id, struct svsm_call *call,
+			      struct svsm_attestation_call *input)
+{
+	struct svsm_attestation_call *ac;
+	unsigned long flags;
+	u64 attest_call_pa;
+	int ret;
+
+	if (!snp_vmpl)
+		return -EINVAL;
+
+	local_irq_save(flags);
+
+	call->caa = svsm_get_caa();
+
+	ac = (struct svsm_attestation_call *)call->caa->svsm_buffer;
+	attest_call_pa = svsm_get_caa_pa() + offsetof(struct svsm_ca, svsm_buffer);
+
+	*ac = *input;
+
+	/*
+	 * Set input registers for the request and set RDX and R8 to known
+	 * values in order to detect length values being returned in them.
+	 */
+	call->rax = call_id;
+	call->rcx = attest_call_pa;
+	call->rdx = -1;
+	call->r8 = -1;
+	ret = svsm_perform_call_protocol(call);
+	update_attest_input(call, input);
+
+	local_irq_restore(flags);
+
+	return ret;
+}
+EXPORT_SYMBOL_GPL(snp_issue_svsm_attest_req);
+
 int snp_issue_guest_request(u64 exit_code, struct snp_req_data *input, struct snp_guest_request_ioctl *rio)
 {
 	struct ghcb_state state;
diff --git a/drivers/virt/coco/sev-guest/sev-guest.c b/drivers/virt/coco/sev-guest/sev-guest.c
index 0c70a38c8cc0..655865164705 100644
--- a/drivers/virt/coco/sev-guest/sev-guest.c
+++ b/drivers/virt/coco/sev-guest/sev-guest.c
@@ -39,6 +39,8 @@
 #define SNP_REQ_MAX_RETRY_DURATION	(60*HZ)
 #define SNP_REQ_RETRY_DELAY		(2*HZ)
 
+#define SVSM_MAX_RETRIES		3
+
 struct snp_guest_crypto {
 	struct crypto_aead *tfm;
 	u8 *iv, *authtag;
@@ -791,6 +793,142 @@ struct snp_msg_cert_entry {
 	u32 length;
 };
 
+static int sev_svsm_report_new(struct tsm_report *report, void *data)
+{
+	unsigned int rep_len, man_len, certs_len;
+	struct tsm_desc *desc = &report->desc;
+	struct svsm_attestation_call ac = {};
+	unsigned int retry_count;
+	void *rep, *man, *certs;
+	struct svsm_call call;
+	unsigned int size;
+	bool try_again;
+	void *buffer;
+	u64 call_id;
+	int ret;
+
+	/*
+	 * Allocate pages for the request:
+	 * - Report blob (4K)
+	 * - Manifest blob (4K)
+	 * - Certificate blob (16K)
+	 *
+	 * Above addresses must be 4K aligned
+	 */
+	rep_len = SZ_4K;
+	man_len = SZ_4K;
+	certs_len = SEV_FW_BLOB_MAX_SIZE;
+
+	guard(mutex)(&snp_cmd_mutex);
+
+	if (guid_is_null(&desc->service_guid)) {
+		call_id = SVSM_ATTEST_CALL(SVSM_ATTEST_SERVICES);
+	} else {
+		export_guid(ac.service_guid, &desc->service_guid);
+		ac.service_manifest_ver = desc->service_manifest_version;
+
+		call_id = SVSM_ATTEST_CALL(SVSM_ATTEST_SINGLE_SERVICE);
+	}
+
+	retry_count = 0;
+
+retry:
+	memset(&call, 0, sizeof(call));
+
+	size = rep_len + man_len + certs_len;
+	buffer = alloc_pages_exact(size, __GFP_ZERO);
+	if (!buffer)
+		return -ENOMEM;
+
+	rep = buffer;
+	ac.report_buf.pa = __pa(rep);
+	ac.report_buf.len = rep_len;
+
+	man = rep + rep_len;
+	ac.manifest_buf.pa = __pa(man);
+	ac.manifest_buf.len = man_len;
+
+	certs = man + man_len;
+	ac.certificates_buf.pa = __pa(certs);
+	ac.certificates_buf.len = certs_len;
+
+	ac.nonce.pa = __pa(desc->inblob);
+	ac.nonce.len = desc->inblob_len;
+
+	ret = snp_issue_svsm_attest_req(call_id, &call, &ac);
+	if (ret) {
+		free_pages_exact(buffer, size);
+
+		switch (call.rax_out) {
+		case SVSM_ERR_INVALID_PARAMETER:
+			try_again = false;
+
+			if (ac.report_buf.len > rep_len) {
+				rep_len = PAGE_ALIGN(ac.report_buf.len);
+				try_again = true;
+			}
+
+			if (ac.manifest_buf.len > man_len) {
+				man_len = PAGE_ALIGN(ac.manifest_buf.len);
+				try_again = true;
+			}
+
+			if (ac.certificates_buf.len > certs_len) {
+				certs_len = PAGE_ALIGN(ac.certificates_buf.len);
+				try_again = true;
+			}
+
+			/* If one of the buffers wasn't large enough, retry the request */
+			if (try_again && retry_count < SVSM_MAX_RETRIES) {
+				retry_count++;
+				goto retry;
+			}
+
+			return -EINVAL;
+		default:
+			pr_err_ratelimited("SVSM attestation request failed (%#x)\n", ret);
+			return -EINVAL;
+		}
+	}
+
+	/*
+	 * Allocate all the blob memory buffers at once so that the cleanup is
+	 * done for errors that occur after the first allocation (i.e. before
+	 * using no_free_ptr()).
+	 */
+	rep_len = ac.report_buf.len;
+	void *rbuf __free(kvfree) = kvzalloc(rep_len, GFP_KERNEL);
+
+	man_len = ac.manifest_buf.len;
+	void *mbuf __free(kvfree) = kvzalloc(man_len, GFP_KERNEL);
+
+	certs_len = ac.certificates_buf.len;
+	void *cbuf __free(kvfree) = certs_len ? kvzalloc(certs_len, GFP_KERNEL) : NULL;
+
+	if (!rbuf || !mbuf || (certs_len && !cbuf)) {
+		free_pages_exact(buffer, size);
+		return -ENOMEM;
+	}
+
+	memcpy(rbuf, rep, rep_len);
+	report->outblob = no_free_ptr(rbuf);
+	report->outblob_len = rep_len;
+
+	memcpy(mbuf, man, man_len);
+	report->manifestblob = no_free_ptr(mbuf);
+	report->manifestblob_len = man_len;
+
+	if (certs_len) {
+		memcpy(cbuf, certs, certs_len);
+		report->auxblob = no_free_ptr(cbuf);
+		report->auxblob_len = certs_len;
+	}
+
+	free_pages_exact(buffer, size);
+
+	return 0;
+}
+
 static int sev_report_new(struct tsm_report *report, void *data)
 {
 	struct snp_msg_cert_entry *cert_table;
@@ -805,6 +943,13 @@ static int sev_report_new(struct tsm_report *report, void *data)
 	if (desc->inblob_len != SNP_REPORT_USER_DATA_SIZE)
 		return -EINVAL;
 
+	if (desc->service_provider) {
+		if (strcmp(desc->service_provider, "svsm"))
+			return -EINVAL;
+
+		return sev_svsm_report_new(report, data);
+	}
+
 	void *buf __free(kvfree) = kvzalloc(size, GFP_KERNEL);
 	if (!buf)
 		return -ENOMEM;
@@ -893,9 +1038,42 @@ static int sev_report_new(struct tsm_report *report, void *data)
 	return 0;
 }
 
+static bool sev_report_attr_visible(int n)
+{
+	switch (n) {
+	case TSM_REPORT_GENERATION:
+	case TSM_REPORT_PROVIDER:
+	case TSM_REPORT_PRIVLEVEL:
+	case TSM_REPORT_PRIVLEVEL_FLOOR:
+		return true;
+	case TSM_REPORT_SERVICE_PROVIDER:
+	case TSM_REPORT_SERVICE_GUID:
+	case TSM_REPORT_SERVICE_MANIFEST_VER:
+		return snp_vmpl;
+	}
+
+	return false;
+}
+
+static bool sev_report_bin_attr_visible(int n)
+{
+	switch (n) {
+	case TSM_REPORT_INBLOB:
+	case TSM_REPORT_OUTBLOB:
+	case TSM_REPORT_AUXBLOB:
+		return true;
+	case TSM_REPORT_MANIFESTBLOB:
+		return snp_vmpl;
+	}
+
+	return false;
+}
+
 static struct tsm_ops sev_tsm_ops = {
 	.name = KBUILD_MODNAME,
 	.report_new = sev_report_new,
+	.report_attr_visible = sev_report_attr_visible,
+	.report_bin_attr_visible = sev_report_bin_attr_visible,
 };
 
 static void unregister_sev_tsm(void *data)
diff --git a/drivers/virt/coco/tsm.c b/drivers/virt/coco/tsm.c
index 7db534b63c9f..9432d4e303f1 100644
--- a/drivers/virt/coco/tsm.c
+++ b/drivers/virt/coco/tsm.c
@@ -34,7 +34,7 @@ static DECLARE_RWSEM(tsm_rwsem);
  * The attestation report format is TSM provider specific, when / if a standard
  * materializes that can be published instead of the vendor layout. Until then
  * the 'provider' attribute indicates the format of 'outblob', and optionally
- * 'auxblob'.
+ * 'auxblob' and 'manifestblob'.
  */
 
 struct tsm_report_state {
@@ -47,6 +47,7 @@ struct tsm_report_state {
 enum tsm_data_select {
 	TSM_REPORT,
 	TSM_CERTS,
+	TSM_MANIFEST,
 };
 
 static struct tsm_report *to_tsm_report(struct config_item *cfg)
@@ -118,6 +119,74 @@ static ssize_t tsm_report_privlevel_floor_show(struct config_item *cfg,
 }
 CONFIGFS_ATTR_RO(tsm_report_, privlevel_floor);
 
+static ssize_t tsm_report_service_provider_store(struct config_item *cfg,
+						 const char *buf, size_t len)
+{
+	struct tsm_report *report = to_tsm_report(cfg);
+	size_t sp_len;
+	char *sp;
+	int rc;
+
+	guard(rwsem_write)(&tsm_rwsem);
+	rc = try_advance_write_generation(report);
+	if (rc)
+		return rc;
+
+	sp_len = (buf[len - 1] != '\n') ? len : len - 1;
+
+	sp = kstrndup(buf, sp_len, GFP_KERNEL);
+	if (!sp)
+		return -ENOMEM;
+	kfree(report->desc.service_provider);
+
+	report->desc.service_provider = sp;
+
+	return len;
+}
+CONFIGFS_ATTR_WO(tsm_report_, service_provider);
+
+static ssize_t tsm_report_service_guid_store(struct config_item *cfg,
+					     const char *buf, size_t len)
+{
+	struct tsm_report *report = to_tsm_report(cfg);
+	int rc;
+
+	guard(rwsem_write)(&tsm_rwsem);
+	rc = try_advance_write_generation(report);
+	if (rc)
+		return rc;
+
+	report->desc.service_guid = guid_null;
+
+	rc = guid_parse(buf, &report->desc.service_guid);
+	if (rc)
+		return rc;
+
+	return len;
+}
+CONFIGFS_ATTR_WO(tsm_report_, service_guid);
+
+static ssize_t tsm_report_service_manifest_version_store(struct config_item *cfg,
+							 const char *buf, size_t len)
+{
+	struct tsm_report *report = to_tsm_report(cfg);
+	unsigned int val;
+	int rc;
+
+	rc = kstrtouint(buf, 0, &val);
+	if (rc)
+		return rc;
+
+	guard(rwsem_write)(&tsm_rwsem);
+	rc = try_advance_write_generation(report);
+	if (rc)
+		return rc;
+	report->desc.service_manifest_version = val;
+
+	return len;
+}
+CONFIGFS_ATTR_WO(tsm_report_, service_manifest_version);
+
 static ssize_t tsm_report_inblob_write(struct config_item *cfg,
 				       const void *buf, size_t count)
 {
@@ -162,6 +231,9 @@ static ssize_t __read_report(struct tsm_report *report, void *buf, size_t count,
 	if (select == TSM_REPORT) {
 		out = report->outblob;
 		len = report->outblob_len;
+	} else if (select == TSM_MANIFEST) {
+		out = report->manifestblob;
+		len = report->manifestblob_len;
 	} else {
 		out = report->auxblob;
 		len = report->auxblob_len;
@@ -187,7 +259,7 @@ static ssize_t read_cached_report(struct tsm_report *report, void *buf,
 
 	/*
 	 * A given TSM backend always fills in ->outblob regardless of
-	 * whether the report includes an auxblob or not.
+	 * whether the report includes an auxblob/manifestblob or not.
 	 */
 	if (!report->outblob ||
 	    state->read_generation != state->write_generation)
@@ -223,8 +295,10 @@ static ssize_t tsm_report_read(struct tsm_report *report, void *buf,
 
 	kvfree(report->outblob);
 	kvfree(report->auxblob);
+	kvfree(report->manifestblob);
 	report->outblob = NULL;
 	report->auxblob = NULL;
+	report->manifestblob = NULL;
 	rc = ops->report_new(report, provider.data);
 	if (rc < 0)
 		return rc;
@@ -251,11 +325,23 @@ static ssize_t tsm_report_auxblob_read(struct config_item *cfg, void *buf,
 }
 CONFIGFS_BIN_ATTR_RO(tsm_report_, auxblob, NULL, TSM_OUTBLOB_MAX);
 
+static ssize_t tsm_report_manifestblob_read(struct config_item *cfg, void *buf,
+					    size_t count)
+{
+	struct tsm_report *report = to_tsm_report(cfg);
+
+	return tsm_report_read(report, buf, count, TSM_MANIFEST);
+}
+CONFIGFS_BIN_ATTR_RO(tsm_report_, manifestblob, NULL, TSM_OUTBLOB_MAX);
+
 static struct configfs_attribute *tsm_report_attrs[] = {
 	[TSM_REPORT_GENERATION] = &tsm_report_attr_generation,
 	[TSM_REPORT_PROVIDER] = &tsm_report_attr_provider,
 	[TSM_REPORT_PRIVLEVEL] = &tsm_report_attr_privlevel,
 	[TSM_REPORT_PRIVLEVEL_FLOOR] = &tsm_report_attr_privlevel_floor,
+	[TSM_REPORT_SERVICE_PROVIDER] = &tsm_report_attr_service_provider,
+	[TSM_REPORT_SERVICE_GUID] = &tsm_report_attr_service_guid,
+	[TSM_REPORT_SERVICE_MANIFEST_VER] = &tsm_report_attr_service_manifest_version,
 	NULL,
 };
 
@@ -263,6 +349,7 @@ static struct configfs_bin_attribute *tsm_report_bin_attrs[] = {
 	[TSM_REPORT_INBLOB] = &tsm_report_attr_inblob,
 	[TSM_REPORT_OUTBLOB] = &tsm_report_attr_outblob,
 	[TSM_REPORT_AUXBLOB] = &tsm_report_attr_auxblob,
+	[TSM_REPORT_MANIFESTBLOB] = &tsm_report_attr_manifestblob,
 	NULL,
 };
 
@@ -271,8 +358,10 @@ static void tsm_report_item_release(struct config_item *cfg)
 	struct tsm_report *report = to_tsm_report(cfg);
 	struct tsm_report_state *state = to_state(report);
 
+	kvfree(report->manifestblob);
 	kvfree(report->auxblob);
 	kvfree(report->outblob);
+	kfree(report->desc.service_provider);
 	kfree(state);
 }
 
diff --git a/include/linux/tsm.h b/include/linux/tsm.h
index 30d9d270b446..11b0c525be30 100644
--- a/include/linux/tsm.h
+++ b/include/linux/tsm.h
@@ -4,6 +4,7 @@
 
 #include <linux/sizes.h>
 #include <linux/types.h>
+#include <linux/uuid.h>
 
 #define TSM_INBLOB_MAX 64
 #define TSM_OUTBLOB_MAX SZ_32K
@@ -19,11 +20,17 @@
  * @privlevel: optional privilege level to associate with @outblob
  * @inblob_len: sizeof @inblob
  * @inblob: arbitrary input data
+ * @service_provider: optional name of where to obtain the tsm report blob
+ * @service_guid: optional service-provider service guid to attest
+ * @service_manifest_version: optional service-provider service manifest version requested
  */
 struct tsm_desc {
 	unsigned int privlevel;
 	size_t inblob_len;
 	u8 inblob[TSM_INBLOB_MAX];
+	char *service_provider;
+	guid_t service_guid;
+	unsigned int service_manifest_version;
 };
 
 /**
@@ -33,6 +40,8 @@ struct tsm_desc {
  * @outblob: generated evidence to provider to the attestation agent
  * @auxblob_len: sizeof(@auxblob)
  * @auxblob: (optional) auxiliary data to the report (e.g. certificate data)
+ * @manifestblob_len: sizeof(@manifestblob)
+ * @manifestblob: (optional) manifest data associated with the report
  */
 struct tsm_report {
 	struct tsm_desc desc;
@@ -40,6 +49,8 @@ struct tsm_report {
 	u8 *outblob;
 	size_t auxblob_len;
 	u8 *auxblob;
+	size_t manifestblob_len;
+	u8 *manifestblob;
 };
 
 /**
@@ -48,12 +59,18 @@ struct tsm_report {
  * @TSM_REPORT_PROVIDER: index of the provider name attribute
  * @TSM_REPORT_PRIVLEVEL: index of the desired privilege level attribute
  * @TSM_REPORT_PRIVLEVEL_FLOOR: index of the minimum allowed privileg level attribute
+ * @TSM_REPORT_SERVICE_PROVIDER: index of the service provider identifier attribute
+ * @TSM_REPORT_SERVICE_GUID: index of the service GUID attribute
+ * @TSM_REPORT_SERVICE_MANIFEST_VER: index of the service manifest version attribute
  */
 enum tsm_attr_index {
 	TSM_REPORT_GENERATION,
 	TSM_REPORT_PROVIDER,
 	TSM_REPORT_PRIVLEVEL,
 	TSM_REPORT_PRIVLEVEL_FLOOR,
+	TSM_REPORT_SERVICE_PROVIDER,
+	TSM_REPORT_SERVICE_GUID,
+	TSM_REPORT_SERVICE_MANIFEST_VER,
 };
 
 /**
@@ -61,11 +78,13 @@ enum tsm_attr_index {
  * @TSM_REPORT_INBLOB: index of the binary report input attribute
  * @TSM_REPORT_OUTBLOB: index of the binary report output attribute
  * @TSM_REPORT_AUXBLOB: index of the binary auxiliary data attribute
+ * @TSM_REPORT_MANIFESTBLOB: index of the binary manifest data attribute
  */
 enum tsm_bin_attr_index {
 	TSM_REPORT_INBLOB,
 	TSM_REPORT_OUTBLOB,
 	TSM_REPORT_AUXBLOB,
+	TSM_REPORT_MANIFESTBLOB,
 };
 
 /**

---

## [14] Tom Lendacky — 2024-06-05
*Subject: [PATCH v5 13/13] x86/sev: Allow non-VMPL0 execution when an SVSM is present*

To allow execution at a level other than VMPL0, an SVSM must be present.
Allow the SEV-SNP guest to continue booting if an SVSM is detected and
the hypervisor supports the SVSM feature as indicated in the GHCB
hypervisor features bitmap.

Signed-off-by: Tom Lendacky <thomas.lendacky@amd.com>
---
 arch/x86/boot/compressed/sev.c    | 17 ++++++++++++++---
 arch/x86/include/asm/sev-common.h |  1 +
 arch/x86/kernel/sev.c             | 20 ++++++++++++--------
 3 files changed, 27 insertions(+), 11 deletions(-)

diff --git a/arch/x86/boot/compressed/sev.c b/arch/x86/boot/compressed/sev.c
index 1cc3106a3ba7..018c37ec1838 100644
--- a/arch/x86/boot/compressed/sev.c
+++ b/arch/x86/boot/compressed/sev.c
@@ -609,11 +609,15 @@ void sev_enable(struct boot_params *bp)
 	 * features.
 	 */
 	if (sev_status & MSR_AMD64_SEV_SNP_ENABLED) {
-		if (!(get_hv_features() & GHCB_HV_FT_SNP))
+		u64 hv_features;
+		int ret;
+
+		hv_features = get_hv_features();
+		if (!(hv_features & GHCB_HV_FT_SNP))
 			sev_es_terminate(SEV_TERM_SET_GEN, GHCB_SNP_UNSUPPORTED);
 
 		/*
-		 * Enforce running at VMPL0.
+		 * Enforce running at VMPL0 or with an SVSM.
 		 *
 		 * Use RMPADJUST (see the rmpadjust() function for a description of
 		 * what the instruction does) to update the VMPL1 permissions of a
@@ -622,7 +626,14 @@ void sev_enable(struct boot_params *bp)
 		 * only ever run at a single VMPL level so permission mask changes of a
 		 * lesser-privileged VMPL are a don't-care.
 		 */
-		if (rmpadjust((unsigned long)&boot_ghcb_page, RMP_PG_SIZE_4K, 1))
+
+		ret = rmpadjust((unsigned long)&boot_ghcb_page, RMP_PG_SIZE_4K, 1);
+
+		/*
+		 * Running at VMPL0 is not required if an SVSM is present and the hypervisor
+		 * supports the required SVSM GHCB events.
+		 */
+		if (ret && !(snp_vmpl && (hv_features & GHCB_HV_FT_SNP_MULTI_VMPL)))
 			sev_es_terminate(SEV_TERM_SET_LINUX, GHCB_TERM_NOT_VMPL0);
 	}
 
diff --git a/arch/x86/include/asm/sev-common.h b/arch/x86/include/asm/sev-common.h
index 78a4c25119da..e90d403f2068 100644
--- a/arch/x86/include/asm/sev-common.h
+++ b/arch/x86/include/asm/sev-common.h
@@ -122,6 +122,7 @@ enum psc_op {
 
 #define GHCB_HV_FT_SNP			BIT_ULL(0)
 #define GHCB_HV_FT_SNP_AP_CREATION	BIT_ULL(1)
+#define GHCB_HV_FT_SNP_MULTI_VMPL	BIT_ULL(5)
 
 /*
  * SNP Page State Change NAE event
diff --git a/arch/x86/kernel/sev.c b/arch/x86/kernel/sev.c
index f4ae1d037b04..b7f3c767ef00 100644
--- a/arch/x86/kernel/sev.c
+++ b/arch/x86/kernel/sev.c
@@ -2349,23 +2349,27 @@ static void dump_cpuid_table(void)
  * expected, but that initialization happens too early in boot to print any
  * sort of indicator, and there's not really any other good place to do it,
  * so do it here.
+ *
+ * If running as an SNP guest, report the current VM privilege level (VMPL).
  */
-static int __init report_cpuid_table(void)
+static int __init report_snp_info(void)
 {
 	const struct snp_cpuid_table *cpuid_table = snp_cpuid_get_table();
 
-	if (!cpuid_table->count)
-		return 0;
+	if (cpuid_table->count) {
+		pr_info("Using SNP CPUID table, %d entries present.\n",
+			cpuid_table->count);
 
-	pr_info("Using SNP CPUID table, %d entries present.\n",
-		cpuid_table->count);
+		if (sev_cfg.debug)
+			dump_cpuid_table();
+	}
 
-	if (sev_cfg.debug)
-		dump_cpuid_table();
+	if (cc_platform_has(CC_ATTR_GUEST_SEV_SNP))
+		pr_info("SNP running at VMPL%u.\n", snp_vmpl);
 
 	return 0;
 }
-arch_initcall(report_cpuid_table);
+arch_initcall(report_snp_info);
 
 static int __init init_sev_config(char *str)
 {

---

## [15] Borislav Petkov — 2024-06-05
*Subject: Re: [PATCH v5 02/13] x86/sev: Check for the presence of an SVSM in
 the SNP Secrets page*

On Wed, Jun 05, 2024 at 10:18:45AM -0500, Tom Lendacky wrote:
> During early boot phases, check for the presence of an SVSM when running
> as an SEV-SNP guest.

I did some touch-ups ontop:

diff --git a/Documentation/arch/x86/amd-memory-encryption.rst b/Documentation/arch/x86/amd-memory-encryption.rst
index 79eebaa85b7d..6df3264f23b9 100644
--- a/Documentation/arch/x86/amd-memory-encryption.rst
+++ b/Documentation/arch/x86/amd-memory-encryption.rst
@@ -135,7 +135,7 @@ Secure VM Service Module (SVSM)
 SNP provides a feature called Virtual Machine Privilege Levels (VMPL) which
 defines four privilege levels at which guest software can run. The most
 privileged level is 0 and numerically higher numbers have lesser privileges.
-More details in the AMD64 APM[1] Vol 2, section "15.35.7 Virtual Machine
+More details in the AMD64 APM Vol 2, section "15.35.7 Virtual Machine
 Privilege Levels", docID: 24593.
 
 When using that feature, different services can run at different protection
@@ -150,7 +150,11 @@ services. An example fur such a privileged operation is PVALIDATE which is
 In this scenario, the software running at VMPL0 is usually called a Secure VM
 Service Module (SVSM). Discovery of an SVSM and the API used to communicate
 with it is documented in "Secure VM Service Module for SEV-SNP Guests", docID:
-58019[2].
+58019.
 
-[1] https://www.amd.com/content/dam/amd/en/documents/processor-tech-docs/programmer-references/24593.pdf
-[2] https://www.amd.com/content/dam/amd/en/documents/epyc-technical-docs/specifications/58019.pdf
+(Latest versions of the above-mentioned documents can be found by using
+a search engine like duckduckgo.com and typing in:
+
+  site:amd.com "Secure VM Service Module for SEV-SNP Guests", docID: 58019
+
+for example.)
diff --git a/arch/x86/boot/compressed/sev.c b/arch/x86/boot/compressed/sev.c
index 927b71495122..c65820b192b4 100644
--- a/arch/x86/boot/compressed/sev.c
+++ b/arch/x86/boot/compressed/sev.c
@@ -465,7 +465,7 @@ static bool early_snp_init(struct boot_params *bp)
 	/*
 	 * Record the SVSM Calling Area (CA) address if the guest is not
 	 * running at VMPL0. The CA will be used to communicate with the
-	 * SVSM to perform the SVSM services.
+	 * SVSM and request its services.
 	 */
 	svsm_setup_ca(cc_info);
 
diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index 16d09c1a8ceb..2a44376f9f91 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -204,19 +204,18 @@ static __always_inline void sev_es_nmi_complete(void)
 extern int __init sev_es_efi_map_ghcbs(pgd_t *pgd);
 extern void sev_enable(struct boot_params *bp);
 
+/*
+ * RMPADJUST modifies the RMP permissions of a page of a lesser-
+ * privileged (numerically higher) VMPL.
+ *
+ * If the guest is running at a higher-privilege than the privilege
+ * level the instruction is targeting, the instruction will succeed,
+ * otherwise, it will fail.
+ */
 static inline int rmpadjust(unsigned long vaddr, bool rmp_psize, unsigned long attrs)
 {
 	int rc;
 
-	/*
-	 * RMPADJUST modifies the RMP permissions of a page of a lesser-privileged
-	 * (numerically higher) VMPL.
-	 *
-	 * If the guest is running at a higher-privilege than the privilege level
-	 * the instruction is targeting, the instruction will succeed, otherwise,
-	 * it will fail.
-	 */
-
 	/* "rmpadjust" mnemonic support in binutils 2.36 and newer */
 	asm volatile(".byte 0xF3,0x0F,0x01,0xFE\n\t"
 		     : "=a"(rc)
diff --git a/arch/x86/kernel/sev-shared.c b/arch/x86/kernel/sev-shared.c
index 739362066e00..06a5078150b5 100644
--- a/arch/x86/kernel/sev-shared.c
+++ b/arch/x86/kernel/sev-shared.c
@@ -1330,6 +1330,11 @@ static void __head svsm_setup_ca(const struct cc_blob_sev_info *cc_info)
 	RIP_REL_REF(snp_vmpl) = secrets_page->svsm_guest_vmpl;
 
 	caa = secrets_page->svsm_caa;
+
+	/*
+	 * An open-coded PAGE_ALIGNED() in order to avoid including
+	 * kernel-proper headers into the decompressor.
+	 */
 	if (caa & (PAGE_SIZE - 1))
 		sev_es_terminate(SEV_TERM_SET_LINUX, GHCB_TERM_SVSM_CAA);

---

## [16] Tom Lendacky — 2024-06-05
*Subject: Re: [PATCH v5 02/13] x86/sev: Check for the presence of an SVSM in
 the SNP Secrets page*

On 6/5/24 14:38, Borislav Petkov wrote:
> On Wed, Jun 05, 2024 at 10:18:45AM -0500, Tom Lendacky wrote:
>> During early boot phases, check for the presence of an SVSM when running

Works for me, thanks!

Tom

>

---

## [17] Borislav Petkov — 2024-06-06
*Subject: Re: [PATCH v5 03/13] x86/sev: Use kernel provided SVSM Calling Areas*

On Wed, Jun 05, 2024 at 10:18:46AM -0500, Tom Lendacky wrote:
> The SVSM Calling Area (CA) is used to communicate between Linux and the
> SVSM. Since the firmware supplied CA for the BSP is likely to be in

Some touchups again:

diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index c101b42cb421..4145928d2874 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -290,7 +290,7 @@ void snp_accept_memory(phys_addr_t start, phys_addr_t end);
 u64 snp_get_unsupported_features(u64 status);
 u64 sev_get_status(void);
 void sev_show_status(void);
-void snp_remap_svsm_ca(void);
+void snp_update_svsm_ca(void);
 #else
 static inline void sev_es_ist_enter(struct pt_regs *regs) { }
 static inline void sev_es_ist_exit(void) { }
@@ -320,7 +320,7 @@ static inline void snp_accept_memory(phys_addr_t start, phys_addr_t end) { }
 static inline u64 snp_get_unsupported_features(u64 status) { return 0; }
 static inline u64 sev_get_status(void) { return 0; }
 static inline void sev_show_status(void) { }
-static inline void snp_remap_svsm_ca(void) { }
+static inline void snp_update_svsm_ca(void) { }
 #endif
 
 #ifdef CONFIG_KVM_AMD_SEV
diff --git a/arch/x86/kernel/sev-shared.c b/arch/x86/kernel/sev-shared.c
index b458f3c2242a..b5110c68d241 100644
--- a/arch/x86/kernel/sev-shared.c
+++ b/arch/x86/kernel/sev-shared.c
@@ -246,7 +246,7 @@ static enum es_result verify_exception_info(struct ghcb *ghcb, struct es_em_ctxt
 	return ES_VMM_ERROR;
 }
 
-static int process_svsm_result_codes(struct svsm_call *call)
+static inline int svsm_process_result_codes(struct svsm_call *call)
 {
 	switch (call->rax_out) {
 	case SVSM_SUCCESS:
@@ -274,7 +274,7 @@ static int process_svsm_result_codes(struct svsm_call *call)
  *     - RAX specifies the SVSM protocol/callid as input and the return code
  *       as output.
  */
-static __always_inline void issue_svsm_call(struct svsm_call *call, u8 *pending)
+static __always_inline void svsm_issue_call(struct svsm_call *call, u8 *pending)
 {
 	register unsigned long rax asm("rax") = call->rax;
 	register unsigned long rcx asm("rcx") = call->rcx;
@@ -310,7 +310,7 @@ static int svsm_perform_msr_protocol(struct svsm_call *call)
 
 	sev_es_wr_ghcb_msr(GHCB_MSR_VMPL_REQ_LEVEL(0));
 
-	issue_svsm_call(call, &pending);
+	svsm_issue_call(call, &pending);
 
 	resp = sev_es_rd_ghcb_msr();
 
@@ -325,7 +325,7 @@ static int svsm_perform_msr_protocol(struct svsm_call *call)
 	if (GHCB_MSR_VMPL_RESP_VAL(resp))
 		return -EINVAL;
 
-	return process_svsm_result_codes(call);
+	return svsm_process_result_codes(call);
 }
 
 static int svsm_perform_ghcb_protocol(struct ghcb *ghcb, struct svsm_call *call)
@@ -348,7 +348,7 @@ static int svsm_perform_ghcb_protocol(struct ghcb *ghcb, struct svsm_call *call)
 
 	sev_es_wr_ghcb_msr(__pa(ghcb));
 
-	issue_svsm_call(call, &pending);
+	svsm_issue_call(call, &pending);
 
 	if (pending)
 		return -EINVAL;
@@ -363,7 +363,7 @@ static int svsm_perform_ghcb_protocol(struct ghcb *ghcb, struct svsm_call *call)
 		return -EINVAL;
 	}
 
-	return process_svsm_result_codes(call);
+	return svsm_process_result_codes(call);
 }
 
 static enum es_result sev_es_ghcb_hv_call(struct ghcb *ghcb,
diff --git a/arch/x86/kernel/sev.c b/arch/x86/kernel/sev.c
index 6bab3244a3b9..51a0984b422c 100644
--- a/arch/x86/kernel/sev.c
+++ b/arch/x86/kernel/sev.c
@@ -161,7 +161,7 @@ struct sev_config {
 	       * For APs, the per-CPU SVSM CA is created as part of the AP
 	       * bringup, so this flag can be used globally for the BSP and APs.
 	       */
-	      cas_initialized	: 1,
+	      use_cas		: 1,
 
 	      __reserved	: 62;
 };
@@ -615,15 +615,17 @@ static __always_inline void vc_forward_exception(struct es_em_ctxt *ctxt)
 /* Include code shared with pre-decompression boot stage */
 #include "sev-shared.c"
 
-static struct svsm_ca *svsm_get_caa(void)
+static inline struct svsm_ca *svsm_get_caa(void)
 {
 	/*
-	 * Use rip-relative references when called early in the boot. If
-	 * cas_initialized is set, then it is late in the boot and no need
-	 * to worry about rip-relative references.
+	 * Use rIP-relative references when called early in the boot. If
+	 * ->use_cas is set, then it is late in the boot and no need
+	 * to worry about rIP-relative references.
 	 */
-	return RIP_REL_REF(sev_cfg).cas_initialized ? this_cpu_read(svsm_caa)
-						    : RIP_REL_REF(boot_svsm_caa);
+	if (RIP_REL_REF(sev_cfg).use_cas)
+		return this_cpu_read(svsm_caa);
+	else
+		return RIP_REL_REF(boot_svsm_caa);
 }
 
 static noinstr void __sev_put_ghcb(struct ghcb_state *state)
@@ -1517,7 +1519,7 @@ void __init sev_es_init_vc_handling(void)
 			panic("Can't remap the SVSM CA, ret=%d, rax_out=0x%llx\n",
 			      ret, call.rax_out);
 
-		sev_cfg.cas_initialized = true;
+		sev_cfg.use_cas = true;
 
 		local_irq_restore(flags);
 	}
@@ -2443,7 +2445,7 @@ void sev_show_status(void)
 	pr_cont("\n");
 }
 
-void __init snp_remap_svsm_ca(void)
+void __init snp_update_svsm_ca(void)
 {
 	if (!snp_vmpl)
 		return;
diff --git a/arch/x86/mm/mem_encrypt_amd.c b/arch/x86/mm/mem_encrypt_amd.c
index 6155020e4d2d..84624ae83b71 100644
--- a/arch/x86/mm/mem_encrypt_amd.c
+++ b/arch/x86/mm/mem_encrypt_amd.c
@@ -515,7 +515,7 @@ void __init sme_early_init(void)
 	 * Switch the SVSM CA mapping (if active) from identity mapped to
 	 * kernel mapped.
 	 */
-	snp_remap_svsm_ca();
+	snp_update_svsm_ca();
 }
 
 void __init mem_encrypt_free_decrypted_mem(void)

---

## [18] Borislav Petkov — 2024-06-06
*Subject: Re: [PATCH v5 04/13] x86/sev: Perform PVALIDATE using the SVSM when
 not at VMPL0*

On Wed, Jun 05, 2024 at 10:18:47AM -0500, Tom Lendacky wrote:
> The PVALIDATE instruction can only be performed at VMPL0. An SVSM will
> be present when running at VMPL1 or a lower privilege level.

Some touchups ontop like slimming down indentation levels, etc.

diff --git a/arch/x86/boot/compressed/sev.c b/arch/x86/boot/compressed/sev.c
index 226b68b4a29f..ce941a9890f8 100644
--- a/arch/x86/boot/compressed/sev.c
+++ b/arch/x86/boot/compressed/sev.c
@@ -284,11 +284,12 @@ void sev_es_shutdown_ghcb(void)
 		error("SEV-ES CPU Features missing.");
 
 	/*
-	 * This is used to determine whether to use the GHCB MSR protocol or
-	 * the GHCB shared page to perform a GHCB request. Since the GHCB page
-	 * is being changed to encrypted, it can't be used to perform GHCB
-	 * requests. Clear the boot_ghcb variable so that the GHCB MSR protocol
-	 * is used to change the GHCB page over to an encrypted page.
+	 * This denotes whether to use the GHCB MSR protocol or the GHCB
+	 * shared page to perform a GHCB request. Since the GHCB page is
+	 * being changed to encrypted, it can't be used to perform GHCB
+	 * requests. Clear the boot_ghcb variable so that the GHCB MSR
+	 * protocol is used to change the GHCB page over to an encrypted
+	 * page.
 	 */
 	boot_ghcb = NULL;
 
diff --git a/arch/x86/kernel/sev-shared.c b/arch/x86/kernel/sev-shared.c
index 8b191e313c0a..b889be32ef9c 100644
--- a/arch/x86/kernel/sev-shared.c
+++ b/arch/x86/kernel/sev-shared.c
@@ -1220,6 +1220,15 @@ static void __head setup_cpuid_table(const struct cc_blob_sev_info *cc_info)
 	}
 }
 
+static inline void __pval_terminate(u64 pfn, bool action, unsigned int page_size,
+				    int ret, u64 svsm_ret)
+{
+	WARN(1, "PVALIDATE failure: pfn: 0x%llx, action: %u, size: %u, ret: %d, svsm_ret: 0x%llx\n",
+	     pfn, action, page_size, ret, svsm_ret);
+
+	sev_es_terminate(SEV_TERM_SET_LINUX, GHCB_TERM_PVALIDATE);
+}
+
 static void svsm_pval_terminate(struct svsm_pvalidate_call *pc, int ret, u64 svsm_ret)
 {
 	unsigned int page_size;
@@ -1230,16 +1239,7 @@ static void svsm_pval_terminate(struct svsm_pvalidate_call *pc, int ret, u64 svs
 	action = pc->entry[pc->cur_index].action;
 	page_size = pc->entry[pc->cur_index].page_size;
 
-	WARN(1, "PVALIDATE failure: pfn 0x%llx, action=%u, size=%u - ret=%d, svsm_ret=0x%llx\n",
-	     pfn, action, page_size, ret, svsm_ret);
-	sev_es_terminate(SEV_TERM_SET_LINUX, GHCB_TERM_PVALIDATE);
-}
-
-static void pval_terminate(u64 pfn, bool action, unsigned int page_size, int ret)
-{
-	WARN(1, "PVALIDATE failure: pfn 0x%llx, action=%u, size=%u - ret=%d\n",
-	     pfn, action, page_size, ret);
-	sev_es_terminate(SEV_TERM_SET_LINUX, GHCB_TERM_PVALIDATE);
+	__pval_terminate(pfn, action, page_size, ret, svsm_ret);
 }
 
 static void svsm_pval_4k_page(unsigned long paddr, bool validate)
@@ -1284,7 +1284,7 @@ static void pvalidate_4k_page(unsigned long vaddr, unsigned long paddr, bool val
 	int ret;
 
 	/*
-	 * This can be called very early in the boot, so use rip-relative
+	 * This can be called very early during boot, so use rIP-relative
 	 * references as needed.
 	 */
 	if (RIP_REL_REF(snp_vmpl)) {
@@ -1292,7 +1292,7 @@ static void pvalidate_4k_page(unsigned long vaddr, unsigned long paddr, bool val
 	} else {
 		ret = pvalidate(vaddr, RMP_PG_SIZE_4K, validate);
 		if (ret)
-			pval_terminate(PHYS_PFN(paddr), validate, RMP_PG_SIZE_4K, ret);
+			__pval_terminate(PHYS_PFN(paddr), validate, RMP_PG_SIZE_4K, ret, 0);
 	}
 }
 
@@ -1315,16 +1315,19 @@ static void pval_pages(struct snp_psc_desc *desc)
 		validate = e->operation == SNP_PAGE_STATE_PRIVATE;
 
 		rc = pvalidate(vaddr, size, validate);
+		if (!rc)
+			continue;
+
 		if (rc == PVALIDATE_FAIL_SIZEMISMATCH && size == RMP_PG_SIZE_2M) {
 			unsigned long vaddr_end = vaddr + PMD_SIZE;
 
 			for (; vaddr < vaddr_end; vaddr += PAGE_SIZE, pfn++) {
 				rc = pvalidate(vaddr, RMP_PG_SIZE_4K, validate);
 				if (rc)
-					pval_terminate(pfn, validate, RMP_PG_SIZE_4K, rc);
+					__pval_terminate(pfn, validate, RMP_PG_SIZE_4K, rc, 0);
 			}
-		} else if (rc) {
-			pval_terminate(pfn, validate, size, rc);
+		} else {
+			__pval_terminate(pfn, validate, size, rc, 0);
 		}
 	}
 }
@@ -1429,24 +1432,26 @@ static void svsm_pval_pages(struct snp_psc_desc *desc)
 
 		do {
 			ret = svsm_perform_call_protocol(&call);
-			if (ret) {
-				/*
-				 * Check if the entry failed because of an RMP mismatch (a
-				 * PVALIDATE at 2M was requested, but the page is mapped in
-				 * the RMP as 4K).
-				 */
-				if (call.rax_out == SVSM_PVALIDATE_FAIL_SIZEMISMATCH &&
-				    pc->entry[pc->cur_index].page_size == RMP_PG_SIZE_2M) {
-					/* Save this entry for post-processing at 4K */
-					pv_4k[pv_4k_count++] = pc->entry[pc->cur_index];
-
-					/* Skip to the next one unless at the end of the list */
-					pc->cur_index++;
-					if (pc->cur_index < pc->num_entries)
-						ret = -EAGAIN;
-					else
-						ret = 0;
-				}
+			if (!ret)
+				continue;
+
+			/*
+			 * Check if the entry failed because of an RMP mismatch (a
+			 * PVALIDATE at 2M was requested, but the page is mapped in
+			 * the RMP as 4K).
+			 */
+
+			if (call.rax_out == SVSM_PVALIDATE_FAIL_SIZEMISMATCH &&
+			    pc->entry[pc->cur_index].page_size == RMP_PG_SIZE_2M) {
+				/* Save this entry for post-processing at 4K */
+				pv_4k[pv_4k_count++] = pc->entry[pc->cur_index];
+
+				/* Skip to the next one unless at the end of the list */
+				pc->cur_index++;
+				if (pc->cur_index < pc->num_entries)
+					ret = -EAGAIN;
+				else
+					ret = 0;
 			}
 		} while (ret == -EAGAIN);

---

## [19] Tom Lendacky — 2024-06-06
*Subject: Re: [PATCH v5 12/13] x86/sev: Extend the config-fs attestation
 support for an SVSM*

On 6/5/24 10:18, Tom Lendacky wrote:
> When an SVSM is present, the guest can also request attestation reports
> from the SVSM. These SVSM attestation reports can be used to attest the

Here's a small change to provide better error detail that you can squash
into this patch if that's ok.

Thanks,
Tom

diff --git a/drivers/virt/coco/sev-guest/sev-guest.c b/drivers/virt/coco/sev-guest/sev-guest.c
index 655865164705..e32ac31e0630 100644
--- a/drivers/virt/coco/sev-guest/sev-guest.c
+++ b/drivers/virt/coco/sev-guest/sev-guest.c
@@ -886,7 +886,8 @@ static int sev_svsm_report_new(struct tsm_report *report, void *data)
  
  			return -EINVAL;
  		default:
-			pr_err_ratelimited("SVSM attestation request failed (%#x)\n", ret);
+			pr_err_ratelimited("SVSM attestation request failed (%d / 0x%llx)\n",
+					   ret, call.rax_out);
  			return -EINVAL;
  		}
  	}

---

## [20] Dan Williams — 2024-06-14
*Subject: Re: [PATCH v5 09/13] configfs-tsm: Allow the privlevel_floor
 attribute to be updated*

Tom Lendacky wrote:
> With the introduction of an SVSM, Linux will be running at a non-zero
> VMPL. Any request for an attestation report at a higher privilege VMPL

Makes sense,

Reviewed-by: Dan Williams <dan.j.williams@intel.com>

---

## [21] Tom Lendacky — 2024-06-17
*Subject: Re: [PATCH v5 04/13] x86/sev: Perform PVALIDATE using the SVSM when
 not at VMPL0*

On 6/5/24 10:18, Tom Lendacky wrote:
> The PVALIDATE instruction can only be performed at VMPL0. An SVSM will
> be present when running at VMPL1 or a lower privilege level.

Small fix on top of this patch for SVSM PVALIDATE support.

Thanks,
Tom

diff --git a/arch/x86/kernel/sev-shared.c b/arch/x86/kernel/sev-shared.c
index b889be32ef9c..7933c1203b63 100644
--- a/arch/x86/kernel/sev-shared.c
+++ b/arch/x86/kernel/sev-shared.c
@@ -1360,15 +1360,12 @@ static u64 svsm_build_ca_from_pfn_range(u64 pfn, u64 pfn_end, bool action,
  	return pfn;
  }
  
-static void svsm_build_ca_from_psc_desc(struct snp_psc_desc *desc,
-					struct svsm_pvalidate_call *pc)
+static int svsm_build_ca_from_psc_desc(struct snp_psc_desc *desc, unsigned int desc_entry,
+				       struct svsm_pvalidate_call *pc)
  {
  	struct svsm_pvalidate_entry *pe;
-	unsigned int desc_entry;
  	struct psc_entry *e;
  
-	desc_entry = desc->hdr.cur_entry;
-
  	/* Nothing in the CA yet */
  	pc->num_entries = 0;
  	pc->cur_index   = 0;
@@ -1391,7 +1388,7 @@ static void svsm_build_ca_from_psc_desc(struct snp_psc_desc *desc,
  			break;
  	}
  
-	desc->hdr.cur_entry = desc_entry;
+	return desc_entry;
  }
  
  static void svsm_pval_pages(struct snp_psc_desc *desc)
@@ -1427,8 +1424,8 @@ static void svsm_pval_pages(struct snp_psc_desc *desc)
  	call.rax = SVSM_CORE_CALL(SVSM_CORE_PVALIDATE);
  	call.rcx = pc_pa;
  
-	while (desc->hdr.cur_entry <= desc->hdr.end_entry) {
-		svsm_build_ca_from_psc_desc(desc, pc);
+	for (i = 0; i <= desc->hdr.end_entry;) {
+		i = svsm_build_ca_from_psc_desc(desc, i, pc);
  
  		do {
  			ret = svsm_perform_call_protocol(&call);

>

---

## [22] Christophe JAILLET — 2024-07-11
*Subject: Re: [PATCH v5 10/13] fs/configfs: Add a callback to determine
 attribute visibility*

Le 05/06/2024 à 17:18, Tom Lendacky a écrit :
> In order to support dynamic decisions as to whether an attribute should be
> created, add a callback that returns a bool to indicate whether the

Hi,

Should/could this take a *const* struct configfs_bin_attribute * and a 
const struct config_item *?

I'm currently looking if if is feasible to constify struct 
configfs_attribute and co.

In my investigation, I arrived on this new API.
So, if it makes sense to constify the attr argument, it would avoid some 
later work if.

Just my 2c

CJ



> +			       int n);
>   };

---
