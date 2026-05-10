---
title: 'x86/sev: KEXEC/KDUMP support for SEV-ES guests'
date: 2024-06-10
last_reply: 2024-06-10
message_count: 12
participants: ['vsntk18@gmail.com', 'Greg KH']
---

## [1] vsntk18@gmail.com — 2024-06-10

From: Vasant Karasulli <vkarasulli@suse.de>

Hi,

here are changes to enable kexec/kdump in SEV-ES guests. The biggest
problem for supporting kexec/kdump under SEV-ES is to find a way to
hand the non-boot CPUs (APs) from one kernel to another.

Without SEV-ES the first kernel parks the CPUs in a HLT loop until
they get reset by the kexec'ed kernel via an INIT-SIPI-SIPI sequence.
For virtual machines the CPU reset is emulated by the hypervisor,
which sets the vCPU registers back to reset state.

This does not work under SEV-ES, because the hypervisor has no access
to the vCPU registers and can't make modifications to them. So an
SEV-ES guest needs to reset the vCPU itself and park it using the
AP-reset-hold protocol. Upon wakeup the guest needs to jump to
real-mode and to the reset-vector configured in the AP-Jump-Table.

The code to do this is the main part of this patch-set. It works by
placing code on the AP Jump-Table page itself to park the vCPU and for
jumping to the reset vector upon wakeup. The code on the AP Jump Table
runs in 16-bit protected mode with segment base set to the beginning
of the page. The AP Jump-Table is usually not within the first 1MB of
memory, so the code can't run in real-mode.

The AP Jump-Table is the best place to put the parking code, because
the memory is owned, but read-only by the firmware and writeable by
the OS. Only the first 4 bytes are used for the reset-vector, leaving
the rest of the page for code/data/stack to park a vCPU. The code
can't be in kernel memory because by the time the vCPU wakes up the
memory will be owned by the new kernel, which might have overwritten it
already.

The other patches add initial GHCB Version 2 protocol support, because
kexec/kdump need the MSR-based (without a GHCB) AP-reset-hold VMGEXIT,
which is a GHCB protocol version 2 feature.

The kexec'ed kernel is also entered via the decompressor and needs
MMIO support there, so this patch-set also adds MMIO #VC support to
the decompressor and support for handling CLFLUSH instructions.

Finally there is also code to disable kexec/kdump support at runtime
when the environment does not support it (e.g. no GHCB protocol
version 2 support or AP Jump Table over 4GB).

The diffstat looks big, but most of it is moving code for MMIO #VC
support around to make it available to the decompressor.

The previous version of this patch-set can be found here:

	https://lore.kernel.org/kvm/20240408074049.7049-1-vsntk18@gmail.com/

Please review.

Thanks,
   Vasant

Changes v5->v6:
        - Rebased to v6.10-rc3 kernel
   
Changes v4->v5:
        - Rebased to v6.9-rc2 kernel
	- Applied review comments by Tom Lendacky
	  - Exclude the AP jump table related code for SEV-SNP guests

Changes v3->v4:
        - Rebased to v6.8 kernel
	- Applied review comments by Sean Christopherson
	- Combined sev_es_setup_ap_jump_table() and sev_setup_ap_jump_table()
          into a single function which makes caching jump table address
          unnecessary
        - annotated struct sev_ap_jump_table_header with __packed attribute
	- added code to set up real mode data segment at boot time instead of
          hardcoding the value.

Joerg Roedel (9):
  x86/kexec/64: Disable kexec when SEV-ES is active
  x86/sev: Save and print negotiated GHCB protocol version
  x86/sev: Set GHCB data structure version
  x86/sev: Setup code to park APs in the AP Jump Table
  x86/sev: Park APs on AP Jump Table with GHCB protocol version 2
  x86/sev: Use AP Jump Table blob to stop CPU
  x86/sev: Add MMIO handling support to boot/compressed/ code
  x86/sev: Handle CLFLUSH MMIO events
  x86/kexec/64: Support kexec under SEV-ES with AP Jump Table Blob

Vasant Karasulli (1):
  x86/sev: Exclude AP jump table related code for SEV-SNP guests

 arch/x86/boot/compressed/sev.c          |  45 +-
 arch/x86/include/asm/insn-eval.h        |   1 +
 arch/x86/include/asm/realmode.h         |   5 +
 arch/x86/include/asm/sev-ap-jumptable.h |  30 +
 arch/x86/include/asm/sev.h              |   7 +
 arch/x86/kernel/machine_kexec_64.c      |  12 +
 arch/x86/kernel/process.c               |   8 +
 arch/x86/kernel/sev-shared.c            | 234 +++++-
 arch/x86/kernel/sev.c                   | 376 +++++-----
 arch/x86/lib/insn-eval-shared.c         | 921 ++++++++++++++++++++++++
 arch/x86/lib/insn-eval.c                | 911 +----------------------
 arch/x86/realmode/Makefile              |   9 +-
 arch/x86/realmode/init.c                |   5 +-
 arch/x86/realmode/rm/Makefile           |  11 +-
 arch/x86/realmode/rm/header.S           |   3 +
 arch/x86/realmode/rm/sev.S              |  85 +++
 arch/x86/realmode/rmpiggy.S             |   6 +
 arch/x86/realmode/sev/Makefile          |  33 +
 arch/x86/realmode/sev/ap_jump_table.S   | 131 ++++
 arch/x86/realmode/sev/ap_jump_table.lds |  24 +
 20 files changed, 1711 insertions(+), 1146 deletions(-)
 create mode 100644 arch/x86/include/asm/sev-ap-jumptable.h
 create mode 100644 arch/x86/lib/insn-eval-shared.c
 create mode 100644 arch/x86/realmode/rm/sev.S
 create mode 100644 arch/x86/realmode/sev/Makefile
 create mode 100644 arch/x86/realmode/sev/ap_jump_table.S
 create mode 100644 arch/x86/realmode/sev/ap_jump_table.lds


base-commit: 83a7eefedc9b56fe7bfeff13b6c7356688ffa670

---

## [2] vsntk18@gmail.com — 2024-06-10
*Subject: [PATCH v6 01/10] x86/kexec/64: Disable kexec when SEV-ES is active*

From: Joerg Roedel <jroedel@suse.de>

SEV-ES needs special handling to support kexec. Disable it when SEV-ES
is active until support is implemented.

Cc: stable@vger.kernel.org
Signed-off-by: Joerg Roedel <jroedel@suse.de>
Signed-off-by: Vasant Karasulli <vkarasulli@suse.de>
---
 arch/x86/kernel/machine_kexec_64.c | 11 +++++++++++
 1 file changed, 11 insertions(+)

diff --git a/arch/x86/kernel/machine_kexec_64.c b/arch/x86/kernel/machine_kexec_64.c
index cc0f7f70b17b..1dfb47df5c01 100644
--- a/arch/x86/kernel/machine_kexec_64.c
+++ b/arch/x86/kernel/machine_kexec_64.c
@@ -267,11 +267,22 @@ static void load_segments(void)
 		);
 }
 
+static bool machine_kexec_supported(void)
+{
+	if (cc_platform_has(CC_ATTR_GUEST_STATE_ENCRYPT))
+		return false;
+
+	return true;
+}
+
 int machine_kexec_prepare(struct kimage *image)
 {
 	unsigned long start_pgtable;
 	int result;
 
+	if (!machine_kexec_supported())
+		return -ENOSYS;
+
 	/* Calculate the offsets */
 	start_pgtable = page_to_pfn(image->control_code_page) << PAGE_SHIFT;

---

## [3] vsntk18@gmail.com — 2024-06-10
*Subject: [PATCH v6 02/10] x86/sev: Save and print negotiated GHCB protocol version*

From: Joerg Roedel <jroedel@suse.de>

Save the results of the GHCB protocol negotiation into a data structure
and print information about versions supported and used to the kernel
log.

This is useful for debugging kexec issues in SEV-ES guests down the
road to quickly spot whether kexec is supported on the given host.

Signed-off-by: Joerg Roedel <jroedel@suse.de>
Signed-off-by: Vasant Karasulli <vkarasulli@suse.de>
---
 arch/x86/kernel/sev-shared.c | 33 +++++++++++++++++++++++++++++++--
 arch/x86/kernel/sev.c        |  8 ++++++++
 2 files changed, 39 insertions(+), 2 deletions(-)

diff --git a/arch/x86/kernel/sev-shared.c b/arch/x86/kernel/sev-shared.c
index b4f8fa0f722c..f5717eddf75b 100644
--- a/arch/x86/kernel/sev-shared.c
+++ b/arch/x86/kernel/sev-shared.c
@@ -23,6 +23,23 @@
 #define sev_printk_rtl(fmt, ...)
 #endif
 
+/*
+ * struct ghcb_info - Used to return GHCB protocol
+ *				   negotiation details.
+ *
+ * @hv_proto_min:	Minimum GHCB protocol version supported by Hypervisor
+ * @hv_proto_max:	Maximum GHCB protocol version supported by Hypervisor
+ * @vm_proto:		Protocol version the VM (this kernel) will use
+ */
+struct ghcb_info {
+	unsigned int hv_proto_min;
+	unsigned int hv_proto_max;
+	unsigned int vm_proto;
+};
+
+/* Negotiated GHCB protocol version */
+static struct ghcb_info ghcb_info __ro_after_init;
+
 /* I/O parameters for CPUID-related helpers */
 struct cpuid_leaf {
 	u32 fn;
@@ -159,12 +176,24 @@ static bool sev_es_negotiate_protocol(void)
 	if (GHCB_MSR_INFO(val) != GHCB_MSR_SEV_INFO_RESP)
 		return false;
 
-	if (GHCB_MSR_PROTO_MAX(val) < GHCB_PROTOCOL_MIN ||
-	    GHCB_MSR_PROTO_MIN(val) > GHCB_PROTOCOL_MAX)
+	/* Sanity check untrusted input */
+	if (GHCB_MSR_PROTO_MIN(val) > GHCB_MSR_PROTO_MAX(val))
 		return false;
 
+	/* Use maximum supported protocol version */
 	ghcb_version = min_t(size_t, GHCB_MSR_PROTO_MAX(val), GHCB_PROTOCOL_MAX);
 
+	/*
+	 * Hypervisor does not support any protocol version required for this
+	 * kernel.
+	 */
+	if (ghcb_version < GHCB_MSR_PROTO_MIN(val))
+		return false;
+
+	ghcb_info.hv_proto_min = GHCB_MSR_PROTO_MIN(val);
+	ghcb_info.hv_proto_max = GHCB_MSR_PROTO_MAX(val);
+	ghcb_info.vm_proto     = ghcb_version;
+
 	return true;
 }
 
diff --git a/arch/x86/kernel/sev.c b/arch/x86/kernel/sev.c
index 3342ed58e168..f0d87549b1e1 100644
--- a/arch/x86/kernel/sev.c
+++ b/arch/x86/kernel/sev.c
@@ -1399,6 +1399,14 @@ void __init sev_es_init_vc_handling(void)
 
 	/* Secondary CPUs use the runtime #VC handler */
 	initial_vc_handler = (unsigned long)kernel_exc_vmm_communication;
+
+	/*
+	 * Print information about supported and negotiated GHCB protocol
+	 * versions.
+	 */
+	pr_info("Hypervisor GHCB protocol version support: min=%u max=%u\n",
+		ghcb_info.hv_proto_min, ghcb_info.hv_proto_max);
+	pr_info("Using GHCB protocol version %u\n", ghcb_info.vm_proto);
 }
 
 static void __init vc_early_forward_exception(struct es_em_ctxt *ctxt)

---

## [4] vsntk18@gmail.com — 2024-06-10
*Subject: [PATCH v6 03/10] x86/sev: Set GHCB data structure version*

From: Joerg Roedel <jroedel@suse.de>

It turned out that the GHCB->protocol field does not declare the
version of the guest-hypervisor communication protocol, but rather the
version of the GHCB data structure. Reflect that in the define used to
set the protocol field.

Signed-off-by: Joerg Roedel <jroedel@suse.de>
Signed-off-by: Vasant Karasulli <vkarasulli@suse.de>
---
 arch/x86/include/asm/sev.h   | 3 +++
 arch/x86/kernel/sev-shared.c | 2 +-
 2 files changed, 4 insertions(+), 1 deletion(-)

diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index ca20cc4e5826..963d51dcf0e6 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -19,6 +19,9 @@
 #define GHCB_PROTOCOL_MAX	2ULL
 #define GHCB_DEFAULT_USAGE	0ULL
 
+/* Version of the GHCB data structure */
+#define GHCB_VERSION		1
+
 #define	VMGEXIT()			{ asm volatile("rep; vmmcall\n\r"); }
 
 struct boot_params;
diff --git a/arch/x86/kernel/sev-shared.c b/arch/x86/kernel/sev-shared.c
index f5717eddf75b..f63262a9c2a5 100644
--- a/arch/x86/kernel/sev-shared.c
+++ b/arch/x86/kernel/sev-shared.c
@@ -264,7 +264,7 @@ static enum es_result sev_es_ghcb_hv_call(struct ghcb *ghcb,
 					  u64 exit_info_2)
 {
 	/* Fill in protocol and format specifiers */
-	ghcb->protocol_version = ghcb_version;
+	ghcb->protocol_version = GHCB_VERSION;
 	ghcb->ghcb_usage       = GHCB_DEFAULT_USAGE;
 
 	ghcb_set_sw_exit_code(ghcb, exit_code);

---

## [5] vsntk18@gmail.com — 2024-06-10
*Subject: [PATCH v6 04/10] x86/sev: Setup code to park APs in the AP Jump Table*

From: Joerg Roedel <jroedel@suse.de>

The AP jump table under SEV-ES contains the reset vector where non-boot
CPUs start executing when coming out of reset. This means that a CPU
coming out of the AP-reset-hold VMGEXIT also needs to start executing at
the reset vector stored in the AP jump table.

The problem is to find a safe place to put the real-mode code which
executes the VMGEXIT and jumps to the reset vector. The code can not be
in kernel memory, because after kexec that memory is owned by the new
kernel and the code might have been overwritten.

Fortunately the AP jump table itself is a safe place, because the
memory is not owned by the OS and will not be overwritten by a new
kernel started through kexec. The table is 4k in size and only the
first 4 bytes are used for the reset vector. This leaves enough space
for some 16-bit code to do the job and even a small stack.

The AP jump table must be 4K in size, in encrypted memory and it must
be 4K (page) aligned. There can only be one AP jump table and it
should reside in memory that has been marked as reserved by UEFI.

Install 16-bit code into the AP jump table under SEV-ES.
The code will do an AP-reset-hold VMGEXIT and jump to the
reset vector after being woken up.

Signed-off-by: Joerg Roedel <jroedel@suse.de>
Signed-off-by: Vasant Karasulli <vkarasulli@suse.de>
---
 arch/x86/include/asm/realmode.h         |   2 +
 arch/x86/include/asm/sev-ap-jumptable.h |  30 ++++++
 arch/x86/kernel/sev.c                   |  94 ++++++++++++++---
 arch/x86/realmode/Makefile              |   9 +-
 arch/x86/realmode/rmpiggy.S             |   6 ++
 arch/x86/realmode/sev/Makefile          |  33 ++++++
 arch/x86/realmode/sev/ap_jump_table.S   | 131 ++++++++++++++++++++++++
 arch/x86/realmode/sev/ap_jump_table.lds |  24 +++++
 8 files changed, 316 insertions(+), 13 deletions(-)
 create mode 100644 arch/x86/include/asm/sev-ap-jumptable.h
 create mode 100644 arch/x86/realmode/sev/Makefile
 create mode 100644 arch/x86/realmode/sev/ap_jump_table.S
 create mode 100644 arch/x86/realmode/sev/ap_jump_table.lds

diff --git a/arch/x86/include/asm/realmode.h b/arch/x86/include/asm/realmode.h
index 87e5482acd0d..bd54a48fe077 100644
--- a/arch/x86/include/asm/realmode.h
+++ b/arch/x86/include/asm/realmode.h
@@ -63,6 +63,8 @@ extern unsigned long initial_code;
 extern unsigned long initial_stack;
 #ifdef CONFIG_AMD_MEM_ENCRYPT
 extern unsigned long initial_vc_handler;
+extern unsigned char rm_ap_jump_table_blob[];
+extern unsigned char rm_ap_jump_table_blob_end[];
 #endif
 
 extern u32 *trampoline_lock;
diff --git a/arch/x86/include/asm/sev-ap-jumptable.h b/arch/x86/include/asm/sev-ap-jumptable.h
new file mode 100644
index 000000000000..17b07fb19297
--- /dev/null
+++ b/arch/x86/include/asm/sev-ap-jumptable.h
@@ -0,0 +1,30 @@
+/* SPDX-License-Identifier: GPL-2.0 */
+/*
+ * AMD Encrypted Register State Support
+ *
+ * Author: Joerg Roedel <jroedel@suse.de>
+ */
+#ifndef __ASM_SEV_AP_JUMPTABLE_H
+#define __ASM_SEV_AP_JUMPTABLE_H
+
+#define	SEV_APJT_CS16	0x8
+#define	SEV_APJT_DS16	0x10
+#define	SEV_RM_DS	0x18
+
+#define SEV_APJT_ENTRY	0x10
+
+#ifndef __ASSEMBLY__
+
+/*
+ * The reset_ip and reset_cs members are fixed and defined through the GHCB
+ * specification. Do not change or move them around.
+ */
+struct sev_ap_jump_table_header {
+	u16	reset_ip;
+	u16	reset_cs;
+	u16	ap_jumptable_gdt;
+} __packed;
+
+#endif /* !__ASSEMBLY__ */
+
+#endif /* __ASM_SEV_AP_JUMPTABLE_H */
diff --git a/arch/x86/kernel/sev.c b/arch/x86/kernel/sev.c
index f0d87549b1e1..c15d3568cab9 100644
--- a/arch/x86/kernel/sev.c
+++ b/arch/x86/kernel/sev.c
@@ -26,6 +26,7 @@
 #include <linux/dmi.h>
 #include <uapi/linux/sev-guest.h>
 
+#include <asm/sev-ap-jumptable.h>
 #include <asm/init.h>
 #include <asm/cpu_entry_area.h>
 #include <asm/stacktrace.h>
@@ -92,6 +93,9 @@ static struct ghcb *boot_ghcb __section(".data");
 /* Bitmap of SEV features supported by the hypervisor */
 static u64 sev_hv_features __ro_after_init;
 
+/* Whether the AP jump table blob was successfully installed */
+static bool sev_ap_jumptable_blob_installed __ro_after_init;
+
 /* #VC handler runtime per-CPU data */
 struct sev_es_runtime_data {
 	struct ghcb ghcb_page;
@@ -670,12 +674,12 @@ static u64 __init get_snp_jump_table_addr(void)
 	return addr;
 }
 
-static u64 __init get_jump_table_addr(void)
+static phys_addr_t __init get_jump_table_addr(void)
 {
 	struct ghcb_state state;
 	unsigned long flags;
 	struct ghcb *ghcb;
-	u64 ret = 0;
+	phys_addr_t jump_table_pa;
 
 	if (cc_platform_has(CC_ATTR_GUEST_SEV_SNP))
 		return get_snp_jump_table_addr();
@@ -694,13 +698,13 @@ static u64 __init get_jump_table_addr(void)
 
 	if (ghcb_sw_exit_info_1_is_valid(ghcb) &&
 	    ghcb_sw_exit_info_2_is_valid(ghcb))
-		ret = ghcb->save.sw_exit_info_2;
+		jump_table_pa = ghcb->save.sw_exit_info_2;
 
 	__sev_put_ghcb(&state);
 
 	local_irq_restore(flags);
 
-	return ret;
+	return jump_table_pa;
 }
 
 static void __head
@@ -1135,38 +1139,104 @@ void __init snp_set_wakeup_secondary_cpu(void)
 	apic_update_callback(wakeup_secondary_cpu, wakeup_cpu_via_vmgexit);
 }
 
+/*
+ * Make the necessary runtime changes to the AP jump table blob.  For now this
+ * only sets up the GDT used while the code executes. The GDT needs to contain
+ * 16-bit code and data segments with a base that points to AP jump table page.
+ */
+void __init sev_es_setup_ap_jump_table_data(void *base, u32 pa)
+{
+	struct sev_ap_jump_table_header *header;
+	struct desc_ptr *gdt_descr;
+	u64 *ap_jumptable_gdt;
+
+	header = base;
+
+	/*
+	 * Setup 16-bit protected mode code and data segments for AP jump table.
+	 * Set the segment limits to 0xffff to already be compatible with
+	 * real-mode.
+	 */
+	ap_jumptable_gdt = (u64 *)(base + header->ap_jumptable_gdt);
+	ap_jumptable_gdt[SEV_APJT_CS16 / 8] = GDT_ENTRY(0x9b, pa, 0xffff);
+	ap_jumptable_gdt[SEV_APJT_DS16 / 8] = GDT_ENTRY(0x93, pa, 0xffff);
+	ap_jumptable_gdt[SEV_RM_DS / 8] = GDT_ENTRY(0x93, 0, 0xffff);
+
+	/* Write correct GDT base address into GDT descriptor */
+	gdt_descr = (struct desc_ptr *)(base + header->ap_jumptable_gdt);
+	gdt_descr->address += pa;
+}
+
+/*
+ * Set up the AP jump table blob which contains code which runs in 16-bit
+ * protected mode to park an AP. After the AP is woken up again the code will
+ * disable protected mode and jump to the reset vector which is also stored in
+ * the AP jump table.
+ *
+ * The jump table is a safe place to park an AP, because it is owned by the
+ * BIOS and writable by the OS. Putting the code in kernel memory would break
+ * with kexec, because by the time the APs wake up the memory is owned by
+ * the new kernel, and possibly already overwritten.
+ *
+ * Kexec is also the reason this function is an init-call after SMP bringup.
+ * Only after all CPUs are up there is a guarantee that no AP is still parked in
+ * AP jump-table code.
+ */
 int __init sev_es_setup_ap_jump_table(struct real_mode_header *rmh)
 {
 	u16 startup_cs, startup_ip;
-	phys_addr_t jump_table_pa;
-	u64 jump_table_addr;
 	u16 __iomem *jump_table;
+	phys_addr_t pa;
+	size_t blob_size = rm_ap_jump_table_blob_end - rm_ap_jump_table_blob;
+
+	if (!cc_platform_has(CC_ATTR_GUEST_STATE_ENCRYPT))
+		return 0;
+
+	if (ghcb_info.vm_proto < 2) {
+		pr_warn("AP jump table parking requires at least GHCB protocol version 2\n");
+		return 0;
+	}
 
-	jump_table_addr = get_jump_table_addr();
+	pa = get_jump_table_addr();
 
 	/* On UP guests there is no jump table so this is not a failure */
-	if (!jump_table_addr)
+	if (!pa)
 		return 0;
 
-	/* Check if AP Jump Table is page-aligned */
-	if (jump_table_addr & ~PAGE_MASK)
+	/* Check if AP jump table is page-aligned */
+	if (pa & ~PAGE_MASK)
 		return -EINVAL;
 
-	jump_table_pa = jump_table_addr & PAGE_MASK;
+	/* Check overflow and size for untrusted jump table address */
+	if (pa + PAGE_SIZE < pa || pa + PAGE_SIZE > SZ_4G) {
+		pr_info("AP jump table is above 4GB or address overflow - not enabling AP jump table parking\n");
+		return -EINVAL;
+	}
 
 	startup_cs = (u16)(rmh->trampoline_start >> 4);
 	startup_ip = (u16)(rmh->sev_es_trampoline_start -
 			   rmh->trampoline_start);
 
-	jump_table = ioremap_encrypted(jump_table_pa, PAGE_SIZE);
+	jump_table = ioremap_encrypted(pa, PAGE_SIZE);
 	if (!jump_table)
 		return -EIO;
 
+	/* Install AP jump table Blob with real mode AP parking code */
+	memcpy_toio(jump_table, rm_ap_jump_table_blob, blob_size);
+
+	/* Setup AP jump table GDT */
+	sev_es_setup_ap_jump_table_data(jump_table, (u32)pa);
+
 	writew(startup_ip, &jump_table[0]);
 	writew(startup_cs, &jump_table[1]);
 
 	iounmap(jump_table);
 
+	pr_info("AP jump table Blob successfully set up\n");
+
+	/* Mark AP jump table blob as available */
+	sev_ap_jumptable_blob_installed = true;
+
 	return 0;
 }
 
diff --git a/arch/x86/realmode/Makefile b/arch/x86/realmode/Makefile
index a0b491ae2de8..00f3cceb9580 100644
--- a/arch/x86/realmode/Makefile
+++ b/arch/x86/realmode/Makefile
@@ -11,12 +11,19 @@
 KASAN_SANITIZE			:= n
 KCSAN_SANITIZE			:= n
 
+RMPIGGY-y				 = $(obj)/rm/realmode.bin
+RMPIGGY-$(CONFIG_AMD_MEM_ENCRYPT)	+= $(obj)/sev/ap_jump_table.bin
+
 subdir- := rm
+subdir- := sev
 
 obj-y += init.o
 obj-y += rmpiggy.o
 
-$(obj)/rmpiggy.o: $(obj)/rm/realmode.bin
+$(obj)/rmpiggy.o: $(RMPIGGY-y)
 
 $(obj)/rm/realmode.bin: FORCE
 	$(Q)$(MAKE) $(build)=$(obj)/rm $@
+
+$(obj)/sev/ap_jump_table.bin: FORCE
+	$(Q)$(MAKE) $(build)=$(obj)/sev $@
diff --git a/arch/x86/realmode/rmpiggy.S b/arch/x86/realmode/rmpiggy.S
index c8fef76743f6..a659f98617ff 100644
--- a/arch/x86/realmode/rmpiggy.S
+++ b/arch/x86/realmode/rmpiggy.S
@@ -17,3 +17,9 @@ SYM_DATA_END_LABEL(real_mode_blob, SYM_L_GLOBAL, real_mode_blob_end)
 SYM_DATA_START(real_mode_relocs)
 	.incbin	"arch/x86/realmode/rm/realmode.relocs"
 SYM_DATA_END(real_mode_relocs)
+
+#ifdef CONFIG_AMD_MEM_ENCRYPT
+SYM_DATA_START(rm_ap_jump_table_blob)
+	.incbin "arch/x86/realmode/sev/ap_jump_table.bin"
+SYM_DATA_END_LABEL(rm_ap_jump_table_blob, SYM_L_GLOBAL, rm_ap_jump_table_blob_end)
+#endif
diff --git a/arch/x86/realmode/sev/Makefile b/arch/x86/realmode/sev/Makefile
new file mode 100644
index 000000000000..7cf5f31f6419
--- /dev/null
+++ b/arch/x86/realmode/sev/Makefile
@@ -0,0 +1,33 @@
+# SPDX-License-Identifier: GPL-2.0
+
+# Sanitizer runtimes are unavailable and cannot be linked here.
+KASAN_SANITIZE			:= n
+KCSAN_SANITIZE			:= n
+OBJECT_FILES_NON_STANDARD	:= y
+
+# Prevents link failures: __sanitizer_cov_trace_pc() is not linked in.
+KCOV_INSTRUMENT		:= n
+
+always-y 	:= ap_jump_table.bin
+ap_jump_table-y	+= ap_jump_table.o
+targets		+= $(ap_jump_table-y)
+
+APJUMPTABLE_OBJS = $(addprefix $(obj)/,$(ap_jump_table-y))
+
+LDFLAGS_ap_jump_table.elf := -m elf_i386 -T
+
+targets 	+= ap_jump_table.elf
+$(obj)/ap_jump_table.elf: $(obj)/ap_jump_table.lds $(APJUMPTABLE_OBJS) FORCE
+	$(call if_changed,ld)
+
+OBJCOPYFLAGS_ap_jump_table.bin := -O binary
+
+targets 	+= ap_jump_table.bin
+$(obj)/ap_jump_table.bin: $(obj)/ap_jump_table.elf FORCE
+	$(call if_changed,objcopy)
+
+# ---------------------------------------------------------------------------
+
+KBUILD_AFLAGS	:= $(REALMODE_CFLAGS) -D__ASSEMBLY__
+GCOV_PROFILE := n
+UBSAN_SANITIZE := n
diff --git a/arch/x86/realmode/sev/ap_jump_table.S b/arch/x86/realmode/sev/ap_jump_table.S
new file mode 100644
index 000000000000..b3523612a9b0
--- /dev/null
+++ b/arch/x86/realmode/sev/ap_jump_table.S
@@ -0,0 +1,131 @@
+/* SPDX-License-Identifier: GPL-2.0 */
+
+#include <linux/linkage.h>
+#include <asm/msr-index.h>
+#include <asm/sev-ap-jumptable.h>
+
+/*
+ * This file contains the source code for the binary blob which gets copied to
+ * the SEV-ES AP jump table to park APs while offlining CPUs or booting a new
+ * kernel via KEXEC.
+ *
+ * The AP jump table is the only safe place to put this code, as any memory the
+ * kernel allocates will be owned (and possibly overwritten) by the new kernel
+ * once the APs are woken up.
+ *
+ * This code runs in 16-bit protected mode, the CS, DS, and SS segment bases are
+ * set to the beginning of the AP jump table page.
+ *
+ * Since the GDT will also be gone when the AP wakes up, this blob contains its
+ * own GDT, which is set up by the AP jump table setup code with the correct
+ * offsets.
+ *
+ * Author: Joerg Roedel <jroedel@suse.de>
+ */
+
+	.text
+	.org 0x0
+	.code16
+SYM_DATA_START(ap_jumptable_header)
+	.word	0			/* reset IP */
+	.word	0			/* reset CS */
+	.word	ap_jumptable_gdt	/* GDT Offset   */
+SYM_DATA_END(ap_jumptable_header)
+
+	.org	SEV_APJT_ENTRY
+SYM_CODE_START(ap_park)
+
+	/* Switch to AP jump table GDT first */
+	lgdtl	ap_jumptable_gdt
+
+	/* Reload CS */
+	ljmpw	$SEV_APJT_CS16, $1f
+1:
+
+	/* Reload DS and SS */
+	movl	$SEV_APJT_DS16, %ecx
+	movl	%ecx, %ds
+	movl	%ecx, %ss
+
+	/*
+	 * Setup a stack pointing to the end of the AP jump table page.
+	 * The stack is needed to reset EFLAGS after wakeup.
+	 */
+	movl	$0x1000, %esp
+
+	/* Execute AP reset hold VMGEXIT */
+2:	xorl	%edx, %edx
+	movl	$0x6, %eax
+	movl	$MSR_AMD64_SEV_ES_GHCB, %ecx
+	wrmsr
+	rep; vmmcall
+	rdmsr
+	movl	%eax, %ecx
+	andl	$0xfff, %ecx
+	cmpl	$0x7, %ecx
+	jne	2b
+	shrl	$12, %eax
+	jnz	3f
+	testl	%edx, %edx
+	jnz	3f
+	jmp	2b
+3:
+	/*
+	 * Successfully woken up - patch the correct target into the far jump at
+	 * the end. An indirect far jump does not work here, because at the time
+	 * the jump is executed DS is already loaded with real-mode values.
+	 */
+
+	/* Jump target is at address 0x0 - copy it to the far jump instruction */
+	movl	$0, %ecx
+	movl	(%ecx), %eax
+	movl	%eax, jump_target
+
+	/* Set EFLAGS to reset value (bit 1 is hard-wired to 1) */
+	pushl	$2
+	popfl
+
+	/* Setup DS and SS for real-mode */
+	movl	$0x18, %ecx
+	movl	%ecx, %ds
+	movl	%ecx, %ss
+
+	/* Reset remaining registers */
+	movl	$0, %esp
+	movl	$0, %eax
+	movl	$0, %ebx
+	movl	$0, %edx
+
+	/* Set CR0 to reset value to drop out of protected mode */
+	movl	$0x60000010, %ecx
+	movl	%ecx, %cr0
+
+	/*
+	 * The below sums up to a far-jump instruction which jumps to the reset
+	 * vector configured in the AP jump table and to real-mode. An indirect
+	 * jump would be cleaner, but requires a working DS base/limit. DS is
+	 * already loaded with real-mode values, therefore a direct far jump is
+	 * used which got the correct target patched in.
+	 */
+	.byte	0xea
+SYM_DATA_LOCAL(jump_target, .long 0)
+
+SYM_CODE_END(ap_park)
+	/* Here comes the GDT */
+	.balign	16
+SYM_DATA_START_LOCAL(ap_jumptable_gdt)
+	/* Offset zero used for GDT descriptor */
+	.word	ap_jumptable_gdt_end - ap_jumptable_gdt - 1
+	.long	ap_jumptable_gdt
+	.word	0
+
+	/* 16 bit code segment - setup at boot */
+	.quad 0
+
+	/* 16 bit data segment - setup at boot */
+	.quad 0
+
+	/* Offset 0x18 - real-mode data segment - setup at boot */
+	.long	0
+	.long	0
+SYM_DATA_END_LABEL(ap_jumptable_gdt, SYM_L_LOCAL, ap_jumptable_gdt_end)
diff --git a/arch/x86/realmode/sev/ap_jump_table.lds b/arch/x86/realmode/sev/ap_jump_table.lds
new file mode 100644
index 000000000000..4e47f1a6eb4e
--- /dev/null
+++ b/arch/x86/realmode/sev/ap_jump_table.lds
@@ -0,0 +1,24 @@
+/* SPDX-License-Identifier: GPL-2.0 */
+/*
+ * ap_jump_table.lds
+ *
+ * Linker script for the SEV-ES AP jump table code
+ */
+
+OUTPUT_FORMAT("elf32-i386")
+OUTPUT_ARCH(i386)
+ENTRY(ap_park)
+
+SECTIONS
+{
+	. = 0;
+	.text : {
+		*(.text)
+		*(.text.*)
+	}
+
+	/DISCARD/ : {
+		*(.note*)
+		*(.debug*)
+	}
+}

---

## [6] vsntk18@gmail.com — 2024-06-10
*Subject: [PATCH v6 05/10] x86/sev: Park APs on AP Jump Table with GHCB protocol version 2*

From: Joerg Roedel <jroedel@suse.de>

GHCB protocol version 2 adds the MSR-based AP-reset-hold VMGEXIT which
does not need a GHCB. Use that to park APs in 16-bit protected mode on
the AP jump table.

Signed-off-by: Joerg Roedel <jroedel@suse.de>
Signed-off-by: Vasant Karasulli <vkarasulli@suse.de>
---
 arch/x86/include/asm/realmode.h |  3 ++
 arch/x86/kernel/sev.c           | 55 ++++++++++++++++++---
 arch/x86/realmode/rm/Makefile   | 11 +++--
 arch/x86/realmode/rm/header.S   |  3 ++
 arch/x86/realmode/rm/sev.S      | 85 +++++++++++++++++++++++++++++++++
 5 files changed, 146 insertions(+), 11 deletions(-)
 create mode 100644 arch/x86/realmode/rm/sev.S

diff --git a/arch/x86/include/asm/realmode.h b/arch/x86/include/asm/realmode.h
index bd54a48fe077..b0a2aa9b8366 100644
--- a/arch/x86/include/asm/realmode.h
+++ b/arch/x86/include/asm/realmode.h
@@ -23,6 +23,9 @@ struct real_mode_header {
 	u32	trampoline_header;
 #ifdef CONFIG_AMD_MEM_ENCRYPT
 	u32	sev_es_trampoline_start;
+	u32	sev_ap_park;
+	u32	sev_ap_park_seg;
+	u32	sev_ap_park_gdt;
 #endif
 #ifdef CONFIG_X86_64
 	u32	trampoline_start64;
diff --git a/arch/x86/kernel/sev.c b/arch/x86/kernel/sev.c
index c15d3568cab9..84b79630f065 100644
--- a/arch/x86/kernel/sev.c
+++ b/arch/x86/kernel/sev.c
@@ -35,6 +35,7 @@
 #include <asm/fpu/xcr.h>
 #include <asm/processor.h>
 #include <asm/realmode.h>
+#include <asm/tlbflush.h>
 #include <asm/setup.h>
 #include <asm/traps.h>
 #include <asm/svm.h>
@@ -1147,8 +1148,9 @@ void __init snp_set_wakeup_secondary_cpu(void)
 void __init sev_es_setup_ap_jump_table_data(void *base, u32 pa)
 {
 	struct sev_ap_jump_table_header *header;
+	u64 *ap_jumptable_gdt, *sev_ap_park_gdt;
 	struct desc_ptr *gdt_descr;
-	u64 *ap_jumptable_gdt;
+	int idx;
 
 	header = base;
 
@@ -1158,9 +1160,16 @@ void __init sev_es_setup_ap_jump_table_data(void *base, u32 pa)
 	 * real-mode.
 	 */
 	ap_jumptable_gdt = (u64 *)(base + header->ap_jumptable_gdt);
-	ap_jumptable_gdt[SEV_APJT_CS16 / 8] = GDT_ENTRY(0x9b, pa, 0xffff);
-	ap_jumptable_gdt[SEV_APJT_DS16 / 8] = GDT_ENTRY(0x93, pa, 0xffff);
-	ap_jumptable_gdt[SEV_RM_DS / 8] = GDT_ENTRY(0x93, 0, 0xffff);
+	sev_ap_park_gdt  = __va(real_mode_header->sev_ap_park_gdt);
+
+	idx = SEV_APJT_CS16 / 8;
+	ap_jumptable_gdt[idx] = sev_ap_park_gdt[idx] = GDT_ENTRY(0x9b, pa, 0xffff);
+
+	idx = SEV_APJT_DS16 / 8;
+	ap_jumptable_gdt[idx] = sev_ap_park_gdt[idx] = GDT_ENTRY(0x93, pa, 0xffff);
+
+	idx = SEV_RM_DS / 8;
+	ap_jumptable_gdt[idx] = GDT_ENTRY(0x93, 0x0, 0xffff);
 
 	/* Write correct GDT base address into GDT descriptor */
 	gdt_descr = (struct desc_ptr *)(base + header->ap_jumptable_gdt);
@@ -1349,6 +1358,38 @@ void setup_ghcb(void)
 }
 
 #ifdef CONFIG_HOTPLUG_CPU
+void __noreturn sev_jumptable_ap_park(void)
+{
+	local_irq_disable();
+
+	write_cr3(real_mode_header->trampoline_pgd);
+
+	/* Exiting long mode will fail if CR4.PCIDE is set. */
+	if (cpu_feature_enabled(X86_FEATURE_PCID))
+		cr4_clear_bits(X86_CR4_PCIDE);
+
+	/*
+	 * Set all GPRs except EAX, EBX, ECX, and EDX to reset state to prepare
+	 * for software reset.
+	 */
+	asm volatile("xorl	%%r15d, %%r15d\n"
+		     "xorl	%%r14d, %%r14d\n"
+		     "xorl	%%r13d, %%r13d\n"
+		     "xorl	%%r12d, %%r12d\n"
+		     "xorl	%%r11d, %%r11d\n"
+		     "xorl	%%r10d, %%r10d\n"
+		     "xorl	%%r9d,  %%r9d\n"
+		     "xorl	%%r8d,  %%r8d\n"
+		     "xorl	%%esi, %%esi\n"
+		     "xorl	%%edi, %%edi\n"
+		     "xorl	%%esp, %%esp\n"
+		     "xorl	%%ebp, %%ebp\n"
+		     "ljmpl	*%0" : :
+		     "m" (real_mode_header->sev_ap_park));
+	unreachable();
+}
+STACK_FRAME_NON_STANDARD(sev_jumptable_ap_park);
+
 static void sev_es_ap_hlt_loop(void)
 {
 	struct ghcb_state state;
@@ -1385,8 +1426,10 @@ static void sev_es_play_dead(void)
 	play_dead_common();
 
 	/* IRQs now disabled */
-
-	sev_es_ap_hlt_loop();
+	if (sev_ap_jumptable_blob_installed)
+		sev_jumptable_ap_park();
+	else
+		sev_es_ap_hlt_loop();
 
 	/*
 	 * If we get here, the VCPU was woken up again. Jump to CPU
diff --git a/arch/x86/realmode/rm/Makefile b/arch/x86/realmode/rm/Makefile
index a0fb39abc5c8..9c5892219cb1 100644
--- a/arch/x86/realmode/rm/Makefile
+++ b/arch/x86/realmode/rm/Makefile
@@ -19,11 +19,12 @@ wakeup-objs	+= video-vga.o
 wakeup-objs	+= video-vesa.o
 wakeup-objs	+= video-bios.o
 
-realmode-y			+= header.o
-realmode-y			+= trampoline_$(BITS).o
-realmode-y			+= stack.o
-realmode-y			+= reboot.o
-realmode-$(CONFIG_ACPI_SLEEP)	+= $(wakeup-objs)
+realmode-y				+= header.o
+realmode-y				+= trampoline_$(BITS).o
+realmode-y				+= stack.o
+realmode-y				+= reboot.o
+realmode-$(CONFIG_ACPI_SLEEP)		+= $(wakeup-objs)
+realmode-$(CONFIG_AMD_MEM_ENCRYPT)	+= sev.o
 
 targets	+= $(realmode-y)
 
diff --git a/arch/x86/realmode/rm/header.S b/arch/x86/realmode/rm/header.S
index 2eb62be6d256..17eae256d443 100644
--- a/arch/x86/realmode/rm/header.S
+++ b/arch/x86/realmode/rm/header.S
@@ -22,6 +22,9 @@ SYM_DATA_START(real_mode_header)
 	.long	pa_trampoline_header
 #ifdef CONFIG_AMD_MEM_ENCRYPT
 	.long	pa_sev_es_trampoline_start
+	.long	pa_sev_ap_park_asm
+	.long	__KERNEL32_CS
+	.long	pa_sev_ap_park_gdt;
 #endif
 #ifdef CONFIG_X86_64
 	.long	pa_trampoline_start64
diff --git a/arch/x86/realmode/rm/sev.S b/arch/x86/realmode/rm/sev.S
new file mode 100644
index 000000000000..ae6eea2d53f7
--- /dev/null
+++ b/arch/x86/realmode/rm/sev.S
@@ -0,0 +1,85 @@
+/* SPDX-License-Identifier: GPL-2.0 */
+#include <linux/linkage.h>
+#include <asm/segment.h>
+#include <asm/page_types.h>
+#include <asm/processor-flags.h>
+#include <asm/msr-index.h>
+#include <asm/sev-ap-jumptable.h>
+#include "realmode.h"
+
+	.section ".text32", "ax"
+	.code32
+/*
+ * The following code switches to 16-bit protected mode and sets up the
+ * execution environment for the AP jump table blob. Then it jumps to the AP
+ * jump table to park the AP.
+ *
+ * The code was copied from reboot.S and modified to fit the SEV-ES requirements
+ * for AP parking. When this code is entered, all registers except %EAX-%EDX are
+ * in reset state.
+ *
+ * %EAX, %EBX, %ECX, %EDX and EFLAGS are undefined. Only use registers %EAX-%EDX and
+ * %ESP in this code.
+ */
+SYM_CODE_START(sev_ap_park_asm)
+
+	/* Switch to trampoline GDT as it is guaranteed < 4 GiB */
+	movl	$__KERNEL_DS, %eax
+	movl	%eax, %ds
+	lgdt	pa_tr_gdt
+
+	/* Disable paging to drop us out of long mode */
+	movl	%cr0, %eax
+	btcl	$X86_CR0_PG_BIT, %eax
+	movl	%eax, %cr0
+
+	ljmpl	$__KERNEL32_CS, $pa_sev_ap_park_paging_off
+
+SYM_INNER_LABEL(sev_ap_park_paging_off, SYM_L_GLOBAL)
+	/* Clear EFER */
+	xorl	%eax, %eax
+	xorl	%edx, %edx
+	movl	$MSR_EFER, %ecx
+	wrmsr
+
+	/* Clear CR3 */
+	xorl	%ecx, %ecx
+	movl	%ecx, %cr3
+
+	/* Set up the IDT for real mode. */
+	lidtl	pa_machine_real_restart_idt
+
+	/* Load the GDT with the 16-bit segments for the AP jump table */
+	lgdtl	pa_sev_ap_park_gdt
+
+	/* Setup code and data segments for AP jump table */
+	movw	$SEV_APJT_DS16, %ax
+	movw	%ax, %ds
+	movw	%ax, %ss
+
+	/* Jump to the AP jump table into 16 bit protected mode */
+	ljmpw	$SEV_APJT_CS16, $SEV_APJT_ENTRY
+SYM_CODE_END(sev_ap_park_asm)
+
+	.data
+	.balign	16
+SYM_DATA_START(sev_ap_park_gdt)
+	/* Self-pointer */
+	.word	sev_ap_park_gdt_end - sev_ap_park_gdt - 1
+	.long	pa_sev_ap_park_gdt
+	.word	0
+
+	/*
+	 * Offset 0x8
+	 * 32 bit code segment descriptor pointing to AP jump table base
+	 * Setup at runtime in sev_es_setup_ap_jump_table_data().
+	 */
+	.quad	0
+
+	/*
+	 * Offset 0x10
+	 * 32 bit data segment descriptor pointing to AP jump table base
+	 * Setup at runtime in sev_es_setup_ap_jump_table_data().
+	 */
+	.quad	0
+SYM_DATA_END_LABEL(sev_ap_park_gdt, SYM_L_GLOBAL, sev_ap_park_gdt_end)

---

## [7] vsntk18@gmail.com — 2024-06-10
*Subject: [PATCH v6 06/10] x86/sev: Use AP Jump Table blob to stop CPU*

From: Joerg Roedel <jroedel@suse.de>

To support kexec under SEV-ES the APs can't be parked with HLT. Upon
wakeup the AP needs to find its way to execute at the reset vector set
by the new kernel and in real-mode.

This is what the AP jump table blob provides, so stop the APs the
SEV-ES way by calling the AP-reset-hold VMGEXIT from the AP jump
table.

Signed-off-by: Joerg Roedel <jroedel@suse.de>
Signed-off-by: Vasant Karasulli <vkarasulli@suse.de>
---
 arch/x86/include/asm/sev.h |  2 ++
 arch/x86/kernel/process.c  |  8 ++++++++
 arch/x86/kernel/sev.c      | 15 ++++++++++++++-
 3 files changed, 24 insertions(+), 1 deletion(-)

diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index 963d51dcf0e6..6f681ced6594 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -232,6 +232,7 @@ void snp_accept_memory(phys_addr_t start, phys_addr_t end);
 u64 snp_get_unsupported_features(u64 status);
 u64 sev_get_status(void);
 void sev_show_status(void);
+void sev_es_stop_this_cpu(void);
 #else
 static inline void sev_es_ist_enter(struct pt_regs *regs) { }
 static inline void sev_es_ist_exit(void) { }
@@ -261,6 +262,7 @@ static inline void snp_accept_memory(phys_addr_t start, phys_addr_t end) { }
 static inline u64 snp_get_unsupported_features(u64 status) { return 0; }
 static inline u64 sev_get_status(void) { return 0; }
 static inline void sev_show_status(void) { }
+static inline void sev_es_stop_this_cpu(void) { }
 #endif
 
 #ifdef CONFIG_KVM_AMD_SEV
diff --git a/arch/x86/kernel/process.c b/arch/x86/kernel/process.c
index b8441147eb5e..0bc615d69c0e 100644
--- a/arch/x86/kernel/process.c
+++ b/arch/x86/kernel/process.c
@@ -52,6 +52,7 @@
 #include <asm/tdx.h>
 #include <asm/mmu_context.h>
 #include <asm/shstk.h>
+#include <asm/sev.h>
 
 #include "process.h"
 
@@ -836,6 +837,13 @@ void __noreturn stop_this_cpu(void *dummy)
 	cpumask_clear_cpu(cpu, &cpus_stop_mask);
 
 	for (;;) {
+		/*
+		 * SEV-ES guests need a special stop routine to support
+		 * kexec. Try this first, if it fails the function will
+		 * return and native_halt() is used.
+		 */
+		sev_es_stop_this_cpu();
+
 		/*
 		 * Use native_halt() so that memory contents don't change
 		 * (stack usage and variables) after possibly issuing the
diff --git a/arch/x86/kernel/sev.c b/arch/x86/kernel/sev.c
index 84b79630f065..8d3cc5cd7e11 100644
--- a/arch/x86/kernel/sev.c
+++ b/arch/x86/kernel/sev.c
@@ -1357,7 +1357,6 @@ void setup_ghcb(void)
 		snp_register_ghcb_early(__pa(&boot_ghcb_page));
 }
 
-#ifdef CONFIG_HOTPLUG_CPU
 void __noreturn sev_jumptable_ap_park(void)
 {
 	local_irq_disable();
@@ -1390,6 +1389,20 @@ void __noreturn sev_jumptable_ap_park(void)
 }
 STACK_FRAME_NON_STANDARD(sev_jumptable_ap_park);
 
+void sev_es_stop_this_cpu(void)
+{
+	if (!(cc_vendor == CC_VENDOR_AMD) ||
+	    !cc_platform_has(CC_ATTR_GUEST_STATE_ENCRYPT))
+		return;
+
+	/* Only park in the AP jump table when the code has been installed */
+	if (!sev_ap_jumptable_blob_installed)
+		return;
+
+	sev_jumptable_ap_park();
+}
+
+#ifdef CONFIG_HOTPLUG_CPU
 static void sev_es_ap_hlt_loop(void)
 {
 	struct ghcb_state state;

---

## [8] vsntk18@gmail.com — 2024-06-10
*Subject: [PATCH v6 07/10] x86/sev: Add MMIO handling support to boot/compressed/ code*

From: Joerg Roedel <jroedel@suse.de>

Move the code for MMIO handling in the #VC handler to sev-shared.c so
that it can be used in the decompressor code. The decompressor needs
to handle MMIO events for writing to the VGA framebuffer.

When the kernel is booted via UEFI the VGA console is not enabled that
early, but a kexec boot will enable it and the decompressor needs MMIO
support to write to the frame buffer.

This also requires to share some code from lib/insn-eval.c. Since
insn-eval.c can't be included into the decompressor code directly,
move the relevant parts into lib/insn-eval-shared.c and include that
file.

Signed-off-by: Joerg Roedel <jroedel@suse.de>
Signed-off-by: Vasant Karasulli <vkarasulli@suse.de>
---
 arch/x86/boot/compressed/sev.c  |  45 +-
 arch/x86/kernel/sev-shared.c    | 196 +++++++
 arch/x86/kernel/sev.c           | 195 -------
 arch/x86/lib/insn-eval-shared.c | 914 ++++++++++++++++++++++++++++++++
 arch/x86/lib/insn-eval.c        | 911 +------------------------------
 5 files changed, 1140 insertions(+), 1121 deletions(-)
 create mode 100644 arch/x86/lib/insn-eval-shared.c

diff --git a/arch/x86/boot/compressed/sev.c b/arch/x86/boot/compressed/sev.c
index 0457a9d7e515..be930fb9f7b8 100644
--- a/arch/x86/boot/compressed/sev.c
+++ b/arch/x86/boot/compressed/sev.c
@@ -29,25 +29,6 @@
 static struct ghcb boot_ghcb_page __aligned(PAGE_SIZE);
 struct ghcb *boot_ghcb;
 
-/*
- * Copy a version of this function here - insn-eval.c can't be used in
- * pre-decompression code.
- */
-static bool insn_has_rep_prefix(struct insn *insn)
-{
-	insn_byte_t p;
-	int i;
-
-	insn_get_prefixes(insn);
-
-	for_each_insn_prefix(insn, i, p) {
-		if (p == 0xf2 || p == 0xf3)
-			return true;
-	}
-
-	return false;
-}
-
 /*
  * Only a dummy for insn_get_seg_base() - Early boot-code is 64bit only and
  * doesn't use segments.
@@ -57,6 +38,16 @@ static unsigned long insn_get_seg_base(struct pt_regs *regs, int seg_reg_idx)
 	return 0UL;
 }
 
+static int get_seg_base_limit(struct insn *insn, struct pt_regs *regs,
+			      int regoff, unsigned long *base,
+			      unsigned long *limit)
+{
+	if (base)
+		*base = 0ULL;
+	if (limit)
+		*limit = ~0ULL;
+}
+
 static inline u64 sev_es_rd_ghcb_msr(void)
 {
 	struct msr m;
@@ -104,6 +95,14 @@ static enum es_result vc_read_mem(struct es_em_ctxt *ctxt,
 	return ES_OK;
 }
 
+static enum es_result vc_slow_virt_to_phys(struct ghcb *ghcb, struct es_em_ctxt *ctxt,
+					   unsigned long vaddr, phys_addr_t *paddr)
+{
+	*paddr = (phys_addr_t)vaddr;
+
+	return ES_OK;
+}
+
 static enum es_result vc_ioio_check(struct es_em_ctxt *ctxt, u16 port, size_t size)
 {
 	return ES_OK;
@@ -122,9 +121,14 @@ static bool fault_in_kernel_space(unsigned long address)
 
 #define __BOOT_COMPRESSED
 
+#undef WARN_ONCE
+#define WARN_ONCE(condition, format...)
+
 /* Basic instruction decoding support needed */
+#include <asm/insn-eval.h>
 #include "../../lib/inat.c"
 #include "../../lib/insn.c"
+#include "../../lib/insn-eval-shared.c"
 
 /* Include code for early handlers */
 #include "../../kernel/sev-shared.c"
@@ -323,6 +327,9 @@ void do_boot_stage2_vc(struct pt_regs *regs, unsigned long exit_code)
 	case SVM_EXIT_CPUID:
 		result = vc_handle_cpuid(boot_ghcb, &ctxt);
 		break;
+	case SVM_EXIT_NPF:
+		result = vc_handle_mmio(boot_ghcb, &ctxt);
+		break;
 	default:
 		result = ES_UNSUPPORTED;
 		break;
diff --git a/arch/x86/kernel/sev-shared.c b/arch/x86/kernel/sev-shared.c
index f63262a9c2a5..1b25a6cacec7 100644
--- a/arch/x86/kernel/sev-shared.c
+++ b/arch/x86/kernel/sev-shared.c
@@ -1043,6 +1043,202 @@ static enum es_result vc_handle_rdtsc(struct ghcb *ghcb,
 	return ES_OK;
 }
 
+static long *vc_insn_get_rm(struct es_em_ctxt *ctxt)
+{
+	long *reg_array;
+	int offset;
+
+	reg_array = (long *)ctxt->regs;
+	offset    = insn_get_modrm_rm_off(&ctxt->insn, ctxt->regs);
+
+	if (offset < 0)
+		return NULL;
+
+	offset /= sizeof(long);
+
+	return reg_array + offset;
+}
+
+static enum es_result vc_do_mmio(struct ghcb *ghcb, struct es_em_ctxt *ctxt,
+				 unsigned int bytes, bool read)
+{
+	u64 exit_code, exit_info_1, exit_info_2;
+	unsigned long ghcb_pa = __pa(ghcb);
+	enum es_result res;
+	phys_addr_t paddr;
+	void __user *ref;
+
+	ref = insn_get_addr_ref(&ctxt->insn, ctxt->regs);
+	if (ref == (void __user *)-1L)
+		return ES_UNSUPPORTED;
+
+	exit_code = read ? SVM_VMGEXIT_MMIO_READ : SVM_VMGEXIT_MMIO_WRITE;
+
+	res = vc_slow_virt_to_phys(ghcb, ctxt, (unsigned long)ref, &paddr);
+	if (res != ES_OK) {
+		if (res == ES_EXCEPTION && !read)
+			ctxt->fi.error_code |= X86_PF_WRITE;
+
+		return res;
+	}
+
+	exit_info_1 = paddr;
+	/* Can never be greater than 8 */
+	exit_info_2 = bytes;
+
+	ghcb_set_sw_scratch(ghcb, ghcb_pa + offsetof(struct ghcb, shared_buffer));
+
+	return sev_es_ghcb_hv_call(ghcb, ctxt, exit_code, exit_info_1, exit_info_2);
+}
+
+/*
+ * The MOVS instruction has two memory operands, which raises the
+ * problem that it is not known whether the access to the source or the
+ * destination caused the #VC exception (and hence whether an MMIO read
+ * or write operation needs to be emulated).
+ *
+ * Instead of playing games with walking page-tables and trying to guess
+ * whether the source or destination is an MMIO range, split the move
+ * into two operations, a read and a write with only one memory operand.
+ * This will cause a nested #VC exception on the MMIO address which can
+ * then be handled.
+ *
+ * This implementation has the benefit that it also supports MOVS where
+ * source _and_ destination are MMIO regions.
+ *
+ * It will slow MOVS on MMIO down a lot, but in SEV-ES guests it is a
+ * rare operation. If it turns out to be a performance problem the split
+ * operations can be moved to memcpy_fromio() and memcpy_toio().
+ */
+static enum es_result vc_handle_mmio_movs(struct es_em_ctxt *ctxt,
+					  unsigned int bytes)
+{
+	unsigned long ds_base, es_base;
+	unsigned char *src, *dst;
+	unsigned char buffer[8];
+	enum es_result ret;
+	bool rep;
+	int off;
+
+	ds_base = insn_get_seg_base(ctxt->regs, INAT_SEG_REG_DS);
+	es_base = insn_get_seg_base(ctxt->regs, INAT_SEG_REG_ES);
+
+	if (ds_base == -1L || es_base == -1L) {
+		ctxt->fi.vector = X86_TRAP_GP;
+		ctxt->fi.error_code = 0;
+		return ES_EXCEPTION;
+	}
+
+	src = ds_base + (unsigned char *)ctxt->regs->si;
+	dst = es_base + (unsigned char *)ctxt->regs->di;
+
+	ret = vc_read_mem(ctxt, src, buffer, bytes);
+	if (ret != ES_OK)
+		return ret;
+
+	ret = vc_write_mem(ctxt, dst, buffer, bytes);
+	if (ret != ES_OK)
+		return ret;
+
+	if (ctxt->regs->flags & X86_EFLAGS_DF)
+		off = -bytes;
+	else
+		off =  bytes;
+
+	ctxt->regs->si += off;
+	ctxt->regs->di += off;
+
+	rep = insn_has_rep_prefix(&ctxt->insn);
+	if (rep)
+		ctxt->regs->cx -= 1;
+
+	if (!rep || ctxt->regs->cx == 0)
+		return ES_OK;
+	else
+		return ES_RETRY;
+}
+
+static enum es_result vc_handle_mmio(struct ghcb *ghcb, struct es_em_ctxt *ctxt)
+{
+	struct insn *insn = &ctxt->insn;
+	enum insn_mmio_type mmio;
+	unsigned int bytes = 0;
+	enum es_result ret;
+	u8 sign_byte;
+	long *reg_data;
+
+	mmio = insn_decode_mmio(insn, &bytes);
+	if (mmio == INSN_MMIO_DECODE_FAILED)
+		return ES_DECODE_FAILED;
+
+	if (mmio != INSN_MMIO_WRITE_IMM && mmio != INSN_MMIO_MOVS) {
+		reg_data = insn_get_modrm_reg_ptr(insn, ctxt->regs);
+		if (!reg_data)
+			return ES_DECODE_FAILED;
+	}
+
+	if (user_mode(ctxt->regs))
+		return ES_UNSUPPORTED;
+
+	switch (mmio) {
+	case INSN_MMIO_WRITE:
+		memcpy(ghcb->shared_buffer, reg_data, bytes);
+		ret = vc_do_mmio(ghcb, ctxt, bytes, false);
+		break;
+	case INSN_MMIO_WRITE_IMM:
+		memcpy(ghcb->shared_buffer, insn->immediate1.bytes, bytes);
+		ret = vc_do_mmio(ghcb, ctxt, bytes, false);
+		break;
+	case INSN_MMIO_READ:
+		ret = vc_do_mmio(ghcb, ctxt, bytes, true);
+		if (ret)
+			break;
+
+		/* Zero-extend for 32-bit operation */
+		if (bytes == 4)
+			*reg_data = 0;
+
+		memcpy(reg_data, ghcb->shared_buffer, bytes);
+		break;
+	case INSN_MMIO_READ_ZERO_EXTEND:
+		ret = vc_do_mmio(ghcb, ctxt, bytes, true);
+		if (ret)
+			break;
+
+		/* Zero extend based on operand size */
+		memset(reg_data, 0, insn->opnd_bytes);
+		memcpy(reg_data, ghcb->shared_buffer, bytes);
+		break;
+	case INSN_MMIO_READ_SIGN_EXTEND:
+		ret = vc_do_mmio(ghcb, ctxt, bytes, true);
+		if (ret)
+			break;
+
+		if (bytes == 1) {
+			u8 *val = (u8 *)ghcb->shared_buffer;
+
+			sign_byte = (*val & 0x80) ? 0xff : 0x00;
+		} else {
+			u16 *val = (u16 *)ghcb->shared_buffer;
+
+			sign_byte = (*val & 0x8000) ? 0xff : 0x00;
+		}
+
+		/* Sign extend based on operand size */
+		memset(reg_data, sign_byte, insn->opnd_bytes);
+		memcpy(reg_data, ghcb->shared_buffer, bytes);
+		break;
+	case INSN_MMIO_MOVS:
+		ret = vc_handle_mmio_movs(ctxt, bytes);
+		break;
+	default:
+		ret = ES_UNSUPPORTED;
+		break;
+	}
+
+	return ret;
+}
+
 struct cc_setup_data {
 	struct setup_data header;
 	u32 cc_blob_address;
diff --git a/arch/x86/kernel/sev.c b/arch/x86/kernel/sev.c
index 8d3cc5cd7e11..30ede17b5a04 100644
--- a/arch/x86/kernel/sev.c
+++ b/arch/x86/kernel/sev.c
@@ -1546,201 +1546,6 @@ static void __init vc_early_forward_exception(struct es_em_ctxt *ctxt)
 	do_early_exception(ctxt->regs, trapnr);
 }
 
-static long *vc_insn_get_rm(struct es_em_ctxt *ctxt)
-{
-	long *reg_array;
-	int offset;
-
-	reg_array = (long *)ctxt->regs;
-	offset    = insn_get_modrm_rm_off(&ctxt->insn, ctxt->regs);
-
-	if (offset < 0)
-		return NULL;
-
-	offset /= sizeof(long);
-
-	return reg_array + offset;
-}
-static enum es_result vc_do_mmio(struct ghcb *ghcb, struct es_em_ctxt *ctxt,
-				 unsigned int bytes, bool read)
-{
-	u64 exit_code, exit_info_1, exit_info_2;
-	unsigned long ghcb_pa = __pa(ghcb);
-	enum es_result res;
-	phys_addr_t paddr;
-	void __user *ref;
-
-	ref = insn_get_addr_ref(&ctxt->insn, ctxt->regs);
-	if (ref == (void __user *)-1L)
-		return ES_UNSUPPORTED;
-
-	exit_code = read ? SVM_VMGEXIT_MMIO_READ : SVM_VMGEXIT_MMIO_WRITE;
-
-	res = vc_slow_virt_to_phys(ghcb, ctxt, (unsigned long)ref, &paddr);
-	if (res != ES_OK) {
-		if (res == ES_EXCEPTION && !read)
-			ctxt->fi.error_code |= X86_PF_WRITE;
-
-		return res;
-	}
-
-	exit_info_1 = paddr;
-	/* Can never be greater than 8 */
-	exit_info_2 = bytes;
-
-	ghcb_set_sw_scratch(ghcb, ghcb_pa + offsetof(struct ghcb, shared_buffer));
-
-	return sev_es_ghcb_hv_call(ghcb, ctxt, exit_code, exit_info_1, exit_info_2);
-}
-
-/*
- * The MOVS instruction has two memory operands, which raises the
- * problem that it is not known whether the access to the source or the
- * destination caused the #VC exception (and hence whether an MMIO read
- * or write operation needs to be emulated).
- *
- * Instead of playing games with walking page-tables and trying to guess
- * whether the source or destination is an MMIO range, split the move
- * into two operations, a read and a write with only one memory operand.
- * This will cause a nested #VC exception on the MMIO address which can
- * then be handled.
- *
- * This implementation has the benefit that it also supports MOVS where
- * source _and_ destination are MMIO regions.
- *
- * It will slow MOVS on MMIO down a lot, but in SEV-ES guests it is a
- * rare operation. If it turns out to be a performance problem the split
- * operations can be moved to memcpy_fromio() and memcpy_toio().
- */
-static enum es_result vc_handle_mmio_movs(struct es_em_ctxt *ctxt,
-					  unsigned int bytes)
-{
-	unsigned long ds_base, es_base;
-	unsigned char *src, *dst;
-	unsigned char buffer[8];
-	enum es_result ret;
-	bool rep;
-	int off;
-
-	ds_base = insn_get_seg_base(ctxt->regs, INAT_SEG_REG_DS);
-	es_base = insn_get_seg_base(ctxt->regs, INAT_SEG_REG_ES);
-
-	if (ds_base == -1L || es_base == -1L) {
-		ctxt->fi.vector = X86_TRAP_GP;
-		ctxt->fi.error_code = 0;
-		return ES_EXCEPTION;
-	}
-
-	src = ds_base + (unsigned char *)ctxt->regs->si;
-	dst = es_base + (unsigned char *)ctxt->regs->di;
-
-	ret = vc_read_mem(ctxt, src, buffer, bytes);
-	if (ret != ES_OK)
-		return ret;
-
-	ret = vc_write_mem(ctxt, dst, buffer, bytes);
-	if (ret != ES_OK)
-		return ret;
-
-	if (ctxt->regs->flags & X86_EFLAGS_DF)
-		off = -bytes;
-	else
-		off =  bytes;
-
-	ctxt->regs->si += off;
-	ctxt->regs->di += off;
-
-	rep = insn_has_rep_prefix(&ctxt->insn);
-	if (rep)
-		ctxt->regs->cx -= 1;
-
-	if (!rep || ctxt->regs->cx == 0)
-		return ES_OK;
-	else
-		return ES_RETRY;
-}
-
-static enum es_result vc_handle_mmio(struct ghcb *ghcb, struct es_em_ctxt *ctxt)
-{
-	struct insn *insn = &ctxt->insn;
-	enum insn_mmio_type mmio;
-	unsigned int bytes = 0;
-	enum es_result ret;
-	u8 sign_byte;
-	long *reg_data;
-
-	mmio = insn_decode_mmio(insn, &bytes);
-	if (mmio == INSN_MMIO_DECODE_FAILED)
-		return ES_DECODE_FAILED;
-
-	if (mmio != INSN_MMIO_WRITE_IMM && mmio != INSN_MMIO_MOVS) {
-		reg_data = insn_get_modrm_reg_ptr(insn, ctxt->regs);
-		if (!reg_data)
-			return ES_DECODE_FAILED;
-	}
-
-	if (user_mode(ctxt->regs))
-		return ES_UNSUPPORTED;
-
-	switch (mmio) {
-	case INSN_MMIO_WRITE:
-		memcpy(ghcb->shared_buffer, reg_data, bytes);
-		ret = vc_do_mmio(ghcb, ctxt, bytes, false);
-		break;
-	case INSN_MMIO_WRITE_IMM:
-		memcpy(ghcb->shared_buffer, insn->immediate1.bytes, bytes);
-		ret = vc_do_mmio(ghcb, ctxt, bytes, false);
-		break;
-	case INSN_MMIO_READ:
-		ret = vc_do_mmio(ghcb, ctxt, bytes, true);
-		if (ret)
-			break;
-
-		/* Zero-extend for 32-bit operation */
-		if (bytes == 4)
-			*reg_data = 0;
-
-		memcpy(reg_data, ghcb->shared_buffer, bytes);
-		break;
-	case INSN_MMIO_READ_ZERO_EXTEND:
-		ret = vc_do_mmio(ghcb, ctxt, bytes, true);
-		if (ret)
-			break;
-
-		/* Zero extend based on operand size */
-		memset(reg_data, 0, insn->opnd_bytes);
-		memcpy(reg_data, ghcb->shared_buffer, bytes);
-		break;
-	case INSN_MMIO_READ_SIGN_EXTEND:
-		ret = vc_do_mmio(ghcb, ctxt, bytes, true);
-		if (ret)
-			break;
-
-		if (bytes == 1) {
-			u8 *val = (u8 *)ghcb->shared_buffer;
-
-			sign_byte = (*val & 0x80) ? 0xff : 0x00;
-		} else {
-			u16 *val = (u16 *)ghcb->shared_buffer;
-
-			sign_byte = (*val & 0x8000) ? 0xff : 0x00;
-		}
-
-		/* Sign extend based on operand size */
-		memset(reg_data, sign_byte, insn->opnd_bytes);
-		memcpy(reg_data, ghcb->shared_buffer, bytes);
-		break;
-	case INSN_MMIO_MOVS:
-		ret = vc_handle_mmio_movs(ctxt, bytes);
-		break;
-	default:
-		ret = ES_UNSUPPORTED;
-		break;
-	}
-
-	return ret;
-}
-
 static enum es_result vc_handle_dr7_write(struct ghcb *ghcb,
 					  struct es_em_ctxt *ctxt)
 {
diff --git a/arch/x86/lib/insn-eval-shared.c b/arch/x86/lib/insn-eval-shared.c
new file mode 100644
index 000000000000..02acdc2921ff
--- /dev/null
+++ b/arch/x86/lib/insn-eval-shared.c
@@ -0,0 +1,914 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/*
+ * AMD Memory Encryption Support
+ *
+ * Copyright (C) 2019 SUSE
+ *
+ * Author: Joerg Roedel <jroedel@suse.de>
+ */
+
+enum reg_type {
+	REG_TYPE_RM = 0,
+	REG_TYPE_REG,
+	REG_TYPE_INDEX,
+	REG_TYPE_BASE,
+};
+
+/**
+ * is_string_insn() - Determine if instruction is a string instruction
+ * @insn:	Instruction containing the opcode to inspect
+ *
+ * Returns:
+ *
+ * true if the instruction, determined by the opcode, is any of the
+ * string instructions as defined in the Intel Software Development manual.
+ * False otherwise.
+ */
+static bool is_string_insn(struct insn *insn)
+{
+	/* All string instructions have a 1-byte opcode. */
+	if (insn->opcode.nbytes != 1)
+		return false;
+
+	switch (insn->opcode.bytes[0]) {
+	case 0x6c ... 0x6f:	/* INS, OUTS */
+	case 0xa4 ... 0xa7:	/* MOVS, CMPS */
+	case 0xaa ... 0xaf:	/* STOS, LODS, SCAS */
+		return true;
+	default:
+		return false;
+	}
+}
+
+/**
+ * insn_has_rep_prefix() - Determine if instruction has a REP prefix
+ * @insn:	Instruction containing the prefix to inspect
+ *
+ * Returns:
+ *
+ * true if the instruction has a REP prefix, false if not.
+ */
+bool insn_has_rep_prefix(struct insn *insn)
+{
+	insn_byte_t p;
+	int i;
+
+	insn_get_prefixes(insn);
+
+	for_each_insn_prefix(insn, i, p) {
+		if (p == 0xf2 || p == 0xf3)
+			return true;
+	}
+
+	return false;
+}
+
+static const int pt_regoff[] = {
+	offsetof(struct pt_regs, ax),
+	offsetof(struct pt_regs, cx),
+	offsetof(struct pt_regs, dx),
+	offsetof(struct pt_regs, bx),
+	offsetof(struct pt_regs, sp),
+	offsetof(struct pt_regs, bp),
+	offsetof(struct pt_regs, si),
+	offsetof(struct pt_regs, di),
+#ifdef CONFIG_X86_64
+	offsetof(struct pt_regs, r8),
+	offsetof(struct pt_regs, r9),
+	offsetof(struct pt_regs, r10),
+	offsetof(struct pt_regs, r11),
+	offsetof(struct pt_regs, r12),
+	offsetof(struct pt_regs, r13),
+	offsetof(struct pt_regs, r14),
+	offsetof(struct pt_regs, r15),
+#else
+	offsetof(struct pt_regs, ds),
+	offsetof(struct pt_regs, es),
+	offsetof(struct pt_regs, fs),
+	offsetof(struct pt_regs, gs),
+#endif
+};
+
+int pt_regs_offset(struct pt_regs *regs, int regno)
+{
+	if ((unsigned int)regno < ARRAY_SIZE(pt_regoff))
+		return pt_regoff[regno];
+	return -EDOM;
+}
+
+static int get_regno(struct insn *insn, enum reg_type type)
+{
+	int nr_registers = ARRAY_SIZE(pt_regoff);
+	int regno = 0;
+
+	/*
+	 * Don't possibly decode a 32-bit instructions as
+	 * reading a 64-bit-only register.
+	 */
+	if (IS_ENABLED(CONFIG_X86_64) && !insn->x86_64)
+		nr_registers -= 8;
+
+	switch (type) {
+	case REG_TYPE_RM:
+		regno = X86_MODRM_RM(insn->modrm.value);
+
+		/*
+		 * ModRM.mod == 0 and ModRM.rm == 5 means a 32-bit displacement
+		 * follows the ModRM byte.
+		 */
+		if (!X86_MODRM_MOD(insn->modrm.value) && regno == 5)
+			return -EDOM;
+
+		if (X86_REX_B(insn->rex_prefix.value))
+			regno += 8;
+		break;
+
+	case REG_TYPE_REG:
+		regno = X86_MODRM_REG(insn->modrm.value);
+
+		if (X86_REX_R(insn->rex_prefix.value))
+			regno += 8;
+		break;
+
+	case REG_TYPE_INDEX:
+		regno = X86_SIB_INDEX(insn->sib.value);
+		if (X86_REX_X(insn->rex_prefix.value))
+			regno += 8;
+
+		/*
+		 * If ModRM.mod != 3 and SIB.index = 4 the scale*index
+		 * portion of the address computation is null. This is
+		 * true only if REX.X is 0. In such a case, the SIB index
+		 * is used in the address computation.
+		 */
+		if (X86_MODRM_MOD(insn->modrm.value) != 3 && regno == 4)
+			return -EDOM;
+		break;
+
+	case REG_TYPE_BASE:
+		regno = X86_SIB_BASE(insn->sib.value);
+		/*
+		 * If ModRM.mod is 0 and SIB.base == 5, the base of the
+		 * register-indirect addressing is 0. In this case, a
+		 * 32-bit displacement follows the SIB byte.
+		 */
+		if (!X86_MODRM_MOD(insn->modrm.value) && regno == 5)
+			return -EDOM;
+
+		if (X86_REX_B(insn->rex_prefix.value))
+			regno += 8;
+		break;
+
+	default:
+		return -EINVAL;
+	}
+
+	if (regno >= nr_registers) {
+		WARN_ONCE(1, "decoded an instruction with an invalid register");
+		return -EINVAL;
+	}
+	return regno;
+}
+
+static int get_reg_offset(struct insn *insn, struct pt_regs *regs,
+			  enum reg_type type)
+{
+	int regno = get_regno(insn, type);
+
+	if (regno < 0)
+		return regno;
+
+	return pt_regs_offset(regs, regno);
+}
+
+/**
+ * get_reg_offset_16() - Obtain offset of register indicated by instruction
+ * @insn:	Instruction containing ModRM byte
+ * @regs:	Register values as seen when entering kernel mode
+ * @offs1:	Offset of the first operand register
+ * @offs2:	Offset of the second operand register, if applicable
+ *
+ * Obtain the offset, in pt_regs, of the registers indicated by the ModRM byte
+ * in @insn. This function is to be used with 16-bit address encodings. The
+ * @offs1 and @offs2 will be written with the offset of the two registers
+ * indicated by the instruction. In cases where any of the registers is not
+ * referenced by the instruction, the value will be set to -EDOM.
+ *
+ * Returns:
+ *
+ * 0 on success, -EINVAL on error.
+ */
+static int get_reg_offset_16(struct insn *insn, struct pt_regs *regs,
+			     int *offs1, int *offs2)
+{
+	/*
+	 * 16-bit addressing can use one or two registers. Specifics of
+	 * encodings are given in Table 2-1. "16-Bit Addressing Forms with the
+	 * ModR/M Byte" of the Intel Software Development Manual.
+	 */
+	static const int regoff1[] = {
+		offsetof(struct pt_regs, bx),
+		offsetof(struct pt_regs, bx),
+		offsetof(struct pt_regs, bp),
+		offsetof(struct pt_regs, bp),
+		offsetof(struct pt_regs, si),
+		offsetof(struct pt_regs, di),
+		offsetof(struct pt_regs, bp),
+		offsetof(struct pt_regs, bx),
+	};
+
+	static const int regoff2[] = {
+		offsetof(struct pt_regs, si),
+		offsetof(struct pt_regs, di),
+		offsetof(struct pt_regs, si),
+		offsetof(struct pt_regs, di),
+		-EDOM,
+		-EDOM,
+		-EDOM,
+		-EDOM,
+	};
+
+	if (!offs1 || !offs2)
+		return -EINVAL;
+
+	/* Operand is a register, use the generic function. */
+	if (X86_MODRM_MOD(insn->modrm.value) == 3) {
+		*offs1 = insn_get_modrm_rm_off(insn, regs);
+		*offs2 = -EDOM;
+		return 0;
+	}
+
+	*offs1 = regoff1[X86_MODRM_RM(insn->modrm.value)];
+	*offs2 = regoff2[X86_MODRM_RM(insn->modrm.value)];
+
+	/*
+	 * If ModRM.mod is 0 and ModRM.rm is 110b, then we use displacement-
+	 * only addressing. This means that no registers are involved in
+	 * computing the effective address. Thus, ensure that the first
+	 * register offset is invalid. The second register offset is already
+	 * invalid under the aforementioned conditions.
+	 */
+	if ((X86_MODRM_MOD(insn->modrm.value) == 0) &&
+	    (X86_MODRM_RM(insn->modrm.value) == 6))
+		*offs1 = -EDOM;
+
+	return 0;
+}
+
+/**
+ * insn_get_modrm_rm_off() - Obtain register in r/m part of the ModRM byte
+ * @insn:	Instruction containing the ModRM byte
+ * @regs:	Register values as seen when entering kernel mode
+ *
+ * Returns:
+ *
+ * The register indicated by the r/m part of the ModRM byte. The
+ * register is obtained as an offset from the base of pt_regs. In specific
+ * cases, the returned value can be -EDOM to indicate that the particular value
+ * of ModRM does not refer to a register and shall be ignored.
+ */
+int insn_get_modrm_rm_off(struct insn *insn, struct pt_regs *regs)
+{
+	return get_reg_offset(insn, regs, REG_TYPE_RM);
+}
+
+/**
+ * insn_get_modrm_reg_off() - Obtain register in reg part of the ModRM byte
+ * @insn:	Instruction containing the ModRM byte
+ * @regs:	Register values as seen when entering kernel mode
+ *
+ * Returns:
+ *
+ * The register indicated by the reg part of the ModRM byte. The
+ * register is obtained as an offset from the base of pt_regs.
+ */
+int insn_get_modrm_reg_off(struct insn *insn, struct pt_regs *regs)
+{
+	return get_reg_offset(insn, regs, REG_TYPE_REG);
+}
+
+/**
+ * insn_get_modrm_reg_ptr() - Obtain register pointer based on ModRM byte
+ * @insn:	Instruction containing the ModRM byte
+ * @regs:	Register values as seen when entering kernel mode
+ *
+ * Returns:
+ *
+ * The register indicated by the reg part of the ModRM byte.
+ * The register is obtained as a pointer within pt_regs.
+ */
+unsigned long *insn_get_modrm_reg_ptr(struct insn *insn, struct pt_regs *regs)
+{
+	int offset;
+
+	offset = insn_get_modrm_reg_off(insn, regs);
+	if (offset < 0)
+		return NULL;
+	return (void *)regs + offset;
+}
+
+/**
+ * get_eff_addr_reg() - Obtain effective address from register operand
+ * @insn:	Instruction. Must be valid.
+ * @regs:	Register values as seen when entering kernel mode
+ * @regoff:	Obtained operand offset, in pt_regs, with the effective address
+ * @eff_addr:	Obtained effective address
+ *
+ * Obtain the effective address stored in the register operand as indicated by
+ * the ModRM byte. This function is to be used only with register addressing
+ * (i.e.,  ModRM.mod is 3). The effective address is saved in @eff_addr. The
+ * register operand, as an offset from the base of pt_regs, is saved in @regoff;
+ * such offset can then be used to resolve the segment associated with the
+ * operand. This function can be used with any of the supported address sizes
+ * in x86.
+ *
+ * Returns:
+ *
+ * 0 on success. @eff_addr will have the effective address stored in the
+ * operand indicated by ModRM. @regoff will have such operand as an offset from
+ * the base of pt_regs.
+ *
+ * -EINVAL on error.
+ */
+static int get_eff_addr_reg(struct insn *insn, struct pt_regs *regs,
+			    int *regoff, long *eff_addr)
+{
+	int ret;
+
+	ret = insn_get_modrm(insn);
+	if (ret)
+		return ret;
+
+	if (X86_MODRM_MOD(insn->modrm.value) != 3)
+		return -EINVAL;
+
+	*regoff = get_reg_offset(insn, regs, REG_TYPE_RM);
+	if (*regoff < 0)
+		return -EINVAL;
+
+	/* Ignore bytes that are outside the address size. */
+	if (insn->addr_bytes == 2)
+		*eff_addr = regs_get_register(regs, *regoff) & 0xffff;
+	else if (insn->addr_bytes == 4)
+		*eff_addr = regs_get_register(regs, *regoff) & 0xffffffff;
+	else /* 64-bit address */
+		*eff_addr = regs_get_register(regs, *regoff);
+
+	return 0;
+}
+
+/**
+ * get_eff_addr_modrm() - Obtain referenced effective address via ModRM
+ * @insn:	Instruction. Must be valid.
+ * @regs:	Register values as seen when entering kernel mode
+ * @regoff:	Obtained operand offset, in pt_regs, associated with segment
+ * @eff_addr:	Obtained effective address
+ *
+ * Obtain the effective address referenced by the ModRM byte of @insn. After
+ * identifying the registers involved in the register-indirect memory reference,
+ * its value is obtained from the operands in @regs. The computed address is
+ * stored @eff_addr. Also, the register operand that indicates the associated
+ * segment is stored in @regoff, this parameter can later be used to determine
+ * such segment.
+ *
+ * Returns:
+ *
+ * 0 on success. @eff_addr will have the referenced effective address. @regoff
+ * will have a register, as an offset from the base of pt_regs, that can be used
+ * to resolve the associated segment.
+ *
+ * -EINVAL on error.
+ */
+static int get_eff_addr_modrm(struct insn *insn, struct pt_regs *regs,
+			      int *regoff, long *eff_addr)
+{
+	long tmp;
+	int ret;
+
+	if (insn->addr_bytes != 8 && insn->addr_bytes != 4)
+		return -EINVAL;
+
+	ret = insn_get_modrm(insn);
+	if (ret)
+		return ret;
+
+	if (X86_MODRM_MOD(insn->modrm.value) > 2)
+		return -EINVAL;
+
+	*regoff = get_reg_offset(insn, regs, REG_TYPE_RM);
+
+	/*
+	 * -EDOM means that we must ignore the address_offset. In such a case,
+	 * in 64-bit mode the effective address relative to the rIP of the
+	 * following instruction.
+	 */
+	if (*regoff == -EDOM) {
+		if (any_64bit_mode(regs))
+			tmp = regs->ip + insn->length;
+		else
+			tmp = 0;
+	} else if (*regoff < 0) {
+		return -EINVAL;
+	} else {
+		tmp = regs_get_register(regs, *regoff);
+	}
+
+	if (insn->addr_bytes == 4) {
+		int addr32 = (int)(tmp & 0xffffffff) + insn->displacement.value;
+
+		*eff_addr = addr32 & 0xffffffff;
+	} else {
+		*eff_addr = tmp + insn->displacement.value;
+	}
+
+	return 0;
+}
+
+/**
+ * get_eff_addr_modrm_16() - Obtain referenced effective address via ModRM
+ * @insn:	Instruction. Must be valid.
+ * @regs:	Register values as seen when entering kernel mode
+ * @regoff:	Obtained operand offset, in pt_regs, associated with segment
+ * @eff_addr:	Obtained effective address
+ *
+ * Obtain the 16-bit effective address referenced by the ModRM byte of @insn.
+ * After identifying the registers involved in the register-indirect memory
+ * reference, its value is obtained from the operands in @regs. The computed
+ * address is stored @eff_addr. Also, the register operand that indicates
+ * the associated segment is stored in @regoff, this parameter can later be used
+ * to determine such segment.
+ *
+ * Returns:
+ *
+ * 0 on success. @eff_addr will have the referenced effective address. @regoff
+ * will have a register, as an offset from the base of pt_regs, that can be used
+ * to resolve the associated segment.
+ *
+ * -EINVAL on error.
+ */
+static int get_eff_addr_modrm_16(struct insn *insn, struct pt_regs *regs,
+				 int *regoff, short *eff_addr)
+{
+	int addr_offset1, addr_offset2, ret;
+	short addr1 = 0, addr2 = 0, displacement;
+
+	if (insn->addr_bytes != 2)
+		return -EINVAL;
+
+	insn_get_modrm(insn);
+
+	if (!insn->modrm.nbytes)
+		return -EINVAL;
+
+	if (X86_MODRM_MOD(insn->modrm.value) > 2)
+		return -EINVAL;
+
+	ret = get_reg_offset_16(insn, regs, &addr_offset1, &addr_offset2);
+	if (ret < 0)
+		return -EINVAL;
+
+	/*
+	 * Don't fail on invalid offset values. They might be invalid because
+	 * they cannot be used for this particular value of ModRM. Instead, use
+	 * them in the computation only if they contain a valid value.
+	 */
+	if (addr_offset1 != -EDOM)
+		addr1 = regs_get_register(regs, addr_offset1) & 0xffff;
+
+	if (addr_offset2 != -EDOM)
+		addr2 = regs_get_register(regs, addr_offset2) & 0xffff;
+
+	displacement = insn->displacement.value & 0xffff;
+	*eff_addr = addr1 + addr2 + displacement;
+
+	/*
+	 * The first operand register could indicate to use of either SS or DS
+	 * registers to obtain the segment selector.  The second operand
+	 * register can only indicate the use of DS. Thus, the first operand
+	 * will be used to obtain the segment selector.
+	 */
+	*regoff = addr_offset1;
+
+	return 0;
+}
+
+/**
+ * get_eff_addr_sib() - Obtain referenced effective address via SIB
+ * @insn:	Instruction. Must be valid.
+ * @regs:	Register values as seen when entering kernel mode
+ * @base_offset: Obtained operand offset, in pt_regs, associated with segment
+ * @eff_addr:	Obtained effective address
+ *
+ * Obtain the effective address referenced by the SIB byte of @insn. After
+ * identifying the registers involved in the indexed, register-indirect memory
+ * reference, its value is obtained from the operands in @regs. The computed
+ * address is stored @eff_addr. Also, the register operand that indicates the
+ * associated segment is stored in @base_offset; this parameter can later be
+ * used to determine such segment.
+ *
+ * Returns:
+ *
+ * 0 on success. @eff_addr will have the referenced effective address.
+ * @base_offset will have a register, as an offset from the base of pt_regs,
+ * that can be used to resolve the associated segment.
+ *
+ * Negative value on error.
+ */
+static int get_eff_addr_sib(struct insn *insn, struct pt_regs *regs,
+			    int *base_offset, long *eff_addr)
+{
+	long base, indx;
+	int indx_offset;
+	int ret;
+
+	if (insn->addr_bytes != 8 && insn->addr_bytes != 4)
+		return -EINVAL;
+
+	ret = insn_get_modrm(insn);
+	if (ret)
+		return ret;
+
+	if (!insn->modrm.nbytes)
+		return -EINVAL;
+
+	if (X86_MODRM_MOD(insn->modrm.value) > 2)
+		return -EINVAL;
+
+	ret = insn_get_sib(insn);
+	if (ret)
+		return ret;
+
+	if (!insn->sib.nbytes)
+		return -EINVAL;
+
+	*base_offset = get_reg_offset(insn, regs, REG_TYPE_BASE);
+	indx_offset = get_reg_offset(insn, regs, REG_TYPE_INDEX);
+
+	/*
+	 * Negative values in the base and index offset means an error when
+	 * decoding the SIB byte. Except -EDOM, which means that the registers
+	 * should not be used in the address computation.
+	 */
+	if (*base_offset == -EDOM)
+		base = 0;
+	else if (*base_offset < 0)
+		return -EINVAL;
+	else
+		base = regs_get_register(regs, *base_offset);
+
+	if (indx_offset == -EDOM)
+		indx = 0;
+	else if (indx_offset < 0)
+		return -EINVAL;
+	else
+		indx = regs_get_register(regs, indx_offset);
+
+	if (insn->addr_bytes == 4) {
+		int addr32, base32, idx32;
+
+		base32 = base & 0xffffffff;
+		idx32 = indx & 0xffffffff;
+
+		addr32 = base32 + idx32 * (1 << X86_SIB_SCALE(insn->sib.value));
+		addr32 += insn->displacement.value;
+
+		*eff_addr = addr32 & 0xffffffff;
+	} else {
+		*eff_addr = base + indx * (1 << X86_SIB_SCALE(insn->sib.value));
+		*eff_addr += insn->displacement.value;
+	}
+
+	return 0;
+}
+
+/**
+ * get_addr_ref_16() - Obtain the 16-bit address referred by instruction
+ * @insn:	Instruction containing ModRM byte and displacement
+ * @regs:	Register values as seen when entering kernel mode
+ *
+ * This function is to be used with 16-bit address encodings. Obtain the memory
+ * address referred by the instruction's ModRM and displacement bytes. Also, the
+ * segment used as base is determined by either any segment override prefixes in
+ * @insn or the default segment of the registers involved in the address
+ * computation. In protected mode, segment limits are enforced.
+ *
+ * Returns:
+ *
+ * Linear address referenced by the instruction operands on success.
+ *
+ * -1L on error.
+ */
+static void __user *get_addr_ref_16(struct insn *insn, struct pt_regs *regs)
+{
+	unsigned long linear_addr = -1L, seg_base, seg_limit;
+	int ret, regoff;
+	short eff_addr;
+	long tmp;
+
+	if (insn_get_displacement(insn))
+		goto out;
+
+	if (insn->addr_bytes != 2)
+		goto out;
+
+	if (X86_MODRM_MOD(insn->modrm.value) == 3) {
+		ret = get_eff_addr_reg(insn, regs, &regoff, &tmp);
+		if (ret)
+			goto out;
+
+		eff_addr = tmp;
+	} else {
+		ret = get_eff_addr_modrm_16(insn, regs, &regoff, &eff_addr);
+		if (ret)
+			goto out;
+	}
+
+	ret = get_seg_base_limit(insn, regs, regoff, &seg_base, &seg_limit);
+	if (ret)
+		goto out;
+
+	/*
+	 * Before computing the linear address, make sure the effective address
+	 * is within the limits of the segment. In virtual-8086 mode, segment
+	 * limits are not enforced. In such a case, the segment limit is -1L to
+	 * reflect this fact.
+	 */
+	if ((unsigned long)(eff_addr & 0xffff) > seg_limit)
+		goto out;
+
+	linear_addr = (unsigned long)(eff_addr & 0xffff) + seg_base;
+
+	/* Limit linear address to 20 bits */
+	if (v8086_mode(regs))
+		linear_addr &= 0xfffff;
+
+out:
+	return (void __user *)linear_addr;
+}
+
+/**
+ * get_addr_ref_32() - Obtain a 32-bit linear address
+ * @insn:	Instruction with ModRM, SIB bytes and displacement
+ * @regs:	Register values as seen when entering kernel mode
+ *
+ * This function is to be used with 32-bit address encodings to obtain the
+ * linear memory address referred by the instruction's ModRM, SIB,
+ * displacement bytes and segment base address, as applicable. If in protected
+ * mode, segment limits are enforced.
+ *
+ * Returns:
+ *
+ * Linear address referenced by instruction and registers on success.
+ *
+ * -1L on error.
+ */
+static void __user *get_addr_ref_32(struct insn *insn, struct pt_regs *regs)
+{
+	unsigned long linear_addr = -1L, seg_base, seg_limit;
+	int eff_addr, regoff;
+	long tmp;
+	int ret;
+
+	if (insn->addr_bytes != 4)
+		goto out;
+
+	if (X86_MODRM_MOD(insn->modrm.value) == 3) {
+		ret = get_eff_addr_reg(insn, regs, &regoff, &tmp);
+		if (ret)
+			goto out;
+
+		eff_addr = tmp;
+
+	} else {
+		if (insn->sib.nbytes) {
+			ret = get_eff_addr_sib(insn, regs, &regoff, &tmp);
+			if (ret)
+				goto out;
+
+			eff_addr = tmp;
+		} else {
+			ret = get_eff_addr_modrm(insn, regs, &regoff, &tmp);
+			if (ret)
+				goto out;
+
+			eff_addr = tmp;
+		}
+	}
+
+	ret = get_seg_base_limit(insn, regs, regoff, &seg_base, &seg_limit);
+	if (ret)
+		goto out;
+
+	/*
+	 * In protected mode, before computing the linear address, make sure
+	 * the effective address is within the limits of the segment.
+	 * 32-bit addresses can be used in long and virtual-8086 modes if an
+	 * address override prefix is used. In such cases, segment limits are
+	 * not enforced. When in virtual-8086 mode, the segment limit is -1L
+	 * to reflect this situation.
+	 *
+	 * After computed, the effective address is treated as an unsigned
+	 * quantity.
+	 */
+	if (!any_64bit_mode(regs) && ((unsigned int)eff_addr > seg_limit))
+		goto out;
+
+	/*
+	 * Even though 32-bit address encodings are allowed in virtual-8086
+	 * mode, the address range is still limited to [0x-0xffff].
+	 */
+	if (v8086_mode(regs) && (eff_addr & ~0xffff))
+		goto out;
+
+	/*
+	 * Data type long could be 64 bits in size. Ensure that our 32-bit
+	 * effective address is not sign-extended when computing the linear
+	 * address.
+	 */
+	linear_addr = (unsigned long)(eff_addr & 0xffffffff) + seg_base;
+
+	/* Limit linear address to 20 bits */
+	if (v8086_mode(regs))
+		linear_addr &= 0xfffff;
+
+out:
+	return (void __user *)linear_addr;
+}
+
+/**
+ * get_addr_ref_64() - Obtain a 64-bit linear address
+ * @insn:	Instruction struct with ModRM and SIB bytes and displacement
+ * @regs:	Structure with register values as seen when entering kernel mode
+ *
+ * This function is to be used with 64-bit address encodings to obtain the
+ * linear memory address referred by the instruction's ModRM, SIB,
+ * displacement bytes and segment base address, as applicable.
+ *
+ * Returns:
+ *
+ * Linear address referenced by instruction and registers on success.
+ *
+ * -1L on error.
+ */
+#ifndef CONFIG_X86_64
+static void __user *get_addr_ref_64(struct insn *insn, struct pt_regs *regs)
+{
+	return (void __user *)-1L;
+}
+#else
+static void __user *get_addr_ref_64(struct insn *insn, struct pt_regs *regs)
+{
+	unsigned long linear_addr = -1L, seg_base;
+	int regoff, ret;
+	long eff_addr;
+
+	if (insn->addr_bytes != 8)
+		goto out;
+
+	if (X86_MODRM_MOD(insn->modrm.value) == 3) {
+		ret = get_eff_addr_reg(insn, regs, &regoff, &eff_addr);
+		if (ret)
+			goto out;
+
+	} else {
+		if (insn->sib.nbytes) {
+			ret = get_eff_addr_sib(insn, regs, &regoff, &eff_addr);
+			if (ret)
+				goto out;
+		} else {
+			ret = get_eff_addr_modrm(insn, regs, &regoff, &eff_addr);
+			if (ret)
+				goto out;
+		}
+
+	}
+
+	ret = get_seg_base_limit(insn, regs, regoff, &seg_base, NULL);
+	if (ret)
+		goto out;
+
+	linear_addr = (unsigned long)eff_addr + seg_base;
+
+out:
+	return (void __user *)linear_addr;
+}
+#endif /* CONFIG_X86_64 */
+
+/**
+ * insn_get_addr_ref() - Obtain the linear address referred by instruction
+ * @insn:	Instruction structure containing ModRM byte and displacement
+ * @regs:	Structure with register values as seen when entering kernel mode
+ *
+ * Obtain the linear address referred by the instruction's ModRM, SIB and
+ * displacement bytes, and segment base, as applicable. In protected mode,
+ * segment limits are enforced.
+ *
+ * Returns:
+ *
+ * Linear address referenced by instruction and registers on success.
+ *
+ * -1L on error.
+ */
+void __user *insn_get_addr_ref(struct insn *insn, struct pt_regs *regs)
+{
+	if (!insn || !regs)
+		return (void __user *)-1L;
+
+	if (insn_get_opcode(insn))
+		return (void __user *)-1L;
+
+	switch (insn->addr_bytes) {
+	case 2:
+		return get_addr_ref_16(insn, regs);
+	case 4:
+		return get_addr_ref_32(insn, regs);
+	case 8:
+		return get_addr_ref_64(insn, regs);
+	default:
+		return (void __user *)-1L;
+	}
+}
+
+/**
+ * insn_decode_mmio() - Decode a MMIO instruction
+ * @insn:	Structure to store decoded instruction
+ * @bytes:	Returns size of memory operand
+ *
+ * Decodes instruction that used for Memory-mapped I/O.
+ *
+ * Returns:
+ *
+ * Type of the instruction. Size of the memory operand is stored in
+ * @bytes. If decode failed, INSN_MMIO_DECODE_FAILED returned.
+ */
+enum insn_mmio_type insn_decode_mmio(struct insn *insn, int *bytes)
+{
+	enum insn_mmio_type type = INSN_MMIO_DECODE_FAILED;
+
+	*bytes = 0;
+
+	if (insn_get_opcode(insn))
+		return INSN_MMIO_DECODE_FAILED;
+
+	switch (insn->opcode.bytes[0]) {
+	case 0x88: /* MOV m8,r8 */
+		*bytes = 1;
+		fallthrough;
+	case 0x89: /* MOV m16/m32/m64, r16/m32/m64 */
+		if (!*bytes)
+			*bytes = insn->opnd_bytes;
+		type = INSN_MMIO_WRITE;
+		break;
+
+	case 0xc6: /* MOV m8, imm8 */
+		*bytes = 1;
+		fallthrough;
+	case 0xc7: /* MOV m16/m32/m64, imm16/imm32/imm64 */
+		if (!*bytes)
+			*bytes = insn->opnd_bytes;
+		type = INSN_MMIO_WRITE_IMM;
+		break;
+
+	case 0x8a: /* MOV r8, m8 */
+		*bytes = 1;
+		fallthrough;
+	case 0x8b: /* MOV r16/r32/r64, m16/m32/m64 */
+		if (!*bytes)
+			*bytes = insn->opnd_bytes;
+		type = INSN_MMIO_READ;
+		break;
+
+	case 0xa4: /* MOVS m8, m8 */
+		*bytes = 1;
+		fallthrough;
+	case 0xa5: /* MOVS m16/m32/m64, m16/m32/m64 */
+		if (!*bytes)
+			*bytes = insn->opnd_bytes;
+		type = INSN_MMIO_MOVS;
+		break;
+
+	case 0x0f: /* Two-byte instruction */
+		switch (insn->opcode.bytes[1]) {
+		case 0xb6: /* MOVZX r16/r32/r64, m8 */
+			*bytes = 1;
+			fallthrough;
+		case 0xb7: /* MOVZX r32/r64, m16 */
+			if (!*bytes)
+				*bytes = 2;
+			type = INSN_MMIO_READ_ZERO_EXTEND;
+			break;
+
+		case 0xbe: /* MOVSX r16/r32/r64, m8 */
+			*bytes = 1;
+			fallthrough;
+		case 0xbf: /* MOVSX r32/r64, m16 */
+			if (!*bytes)
+				*bytes = 2;
+			type = INSN_MMIO_READ_SIGN_EXTEND;
+			break;
+		}
+		break;
+	}
+
+	return type;
+}
diff --git a/arch/x86/lib/insn-eval.c b/arch/x86/lib/insn-eval.c
index 98631c0e7a11..8dea8c181637 100644
--- a/arch/x86/lib/insn-eval.c
+++ b/arch/x86/lib/insn-eval.c
@@ -17,62 +17,10 @@
 
 #undef pr_fmt
 #define pr_fmt(fmt) "insn: " fmt
-
-enum reg_type {
-	REG_TYPE_RM = 0,
-	REG_TYPE_REG,
-	REG_TYPE_INDEX,
-	REG_TYPE_BASE,
-};
-
-/**
- * is_string_insn() - Determine if instruction is a string instruction
- * @insn:	Instruction containing the opcode to inspect
- *
- * Returns:
- *
- * true if the instruction, determined by the opcode, is any of the
- * string instructions as defined in the Intel Software Development manual.
- * False otherwise.
- */
-static bool is_string_insn(struct insn *insn)
-{
-	/* All string instructions have a 1-byte opcode. */
-	if (insn->opcode.nbytes != 1)
-		return false;
-
-	switch (insn->opcode.bytes[0]) {
-	case 0x6c ... 0x6f:	/* INS, OUTS */
-	case 0xa4 ... 0xa7:	/* MOVS, CMPS */
-	case 0xaa ... 0xaf:	/* STOS, LODS, SCAS */
-		return true;
-	default:
-		return false;
-	}
-}
-
-/**
- * insn_has_rep_prefix() - Determine if instruction has a REP prefix
- * @insn:	Instruction containing the prefix to inspect
- *
- * Returns:
- *
- * true if the instruction has a REP prefix, false if not.
- */
-bool insn_has_rep_prefix(struct insn *insn)
-{
-	insn_byte_t p;
-	int i;
-
-	insn_get_prefixes(insn);
-
-	for_each_insn_prefix(insn, i, p) {
-		if (p == 0xf2 || p == 0xf3)
-			return true;
-	}
-
-	return false;
-}
+static int get_seg_base_limit(struct insn *insn, struct pt_regs *regs,
+			      int regoff, unsigned long *base,
+			      unsigned long *limit);
+#include "insn-eval-shared.c"
 
 /**
  * get_seg_reg_override_idx() - obtain segment register override index
@@ -411,199 +359,6 @@ static short get_segment_selector(struct pt_regs *regs, int seg_reg_idx)
 #endif /* CONFIG_X86_64 */
 }
 
-static const int pt_regoff[] = {
-	offsetof(struct pt_regs, ax),
-	offsetof(struct pt_regs, cx),
-	offsetof(struct pt_regs, dx),
-	offsetof(struct pt_regs, bx),
-	offsetof(struct pt_regs, sp),
-	offsetof(struct pt_regs, bp),
-	offsetof(struct pt_regs, si),
-	offsetof(struct pt_regs, di),
-#ifdef CONFIG_X86_64
-	offsetof(struct pt_regs, r8),
-	offsetof(struct pt_regs, r9),
-	offsetof(struct pt_regs, r10),
-	offsetof(struct pt_regs, r11),
-	offsetof(struct pt_regs, r12),
-	offsetof(struct pt_regs, r13),
-	offsetof(struct pt_regs, r14),
-	offsetof(struct pt_regs, r15),
-#else
-	offsetof(struct pt_regs, ds),
-	offsetof(struct pt_regs, es),
-	offsetof(struct pt_regs, fs),
-	offsetof(struct pt_regs, gs),
-#endif
-};
-
-int pt_regs_offset(struct pt_regs *regs, int regno)
-{
-	if ((unsigned)regno < ARRAY_SIZE(pt_regoff))
-		return pt_regoff[regno];
-	return -EDOM;
-}
-
-static int get_regno(struct insn *insn, enum reg_type type)
-{
-	int nr_registers = ARRAY_SIZE(pt_regoff);
-	int regno = 0;
-
-	/*
-	 * Don't possibly decode a 32-bit instructions as
-	 * reading a 64-bit-only register.
-	 */
-	if (IS_ENABLED(CONFIG_X86_64) && !insn->x86_64)
-		nr_registers -= 8;
-
-	switch (type) {
-	case REG_TYPE_RM:
-		regno = X86_MODRM_RM(insn->modrm.value);
-
-		/*
-		 * ModRM.mod == 0 and ModRM.rm == 5 means a 32-bit displacement
-		 * follows the ModRM byte.
-		 */
-		if (!X86_MODRM_MOD(insn->modrm.value) && regno == 5)
-			return -EDOM;
-
-		if (X86_REX_B(insn->rex_prefix.value))
-			regno += 8;
-		break;
-
-	case REG_TYPE_REG:
-		regno = X86_MODRM_REG(insn->modrm.value);
-
-		if (X86_REX_R(insn->rex_prefix.value))
-			regno += 8;
-		break;
-
-	case REG_TYPE_INDEX:
-		regno = X86_SIB_INDEX(insn->sib.value);
-		if (X86_REX_X(insn->rex_prefix.value))
-			regno += 8;
-
-		/*
-		 * If ModRM.mod != 3 and SIB.index = 4 the scale*index
-		 * portion of the address computation is null. This is
-		 * true only if REX.X is 0. In such a case, the SIB index
-		 * is used in the address computation.
-		 */
-		if (X86_MODRM_MOD(insn->modrm.value) != 3 && regno == 4)
-			return -EDOM;
-		break;
-
-	case REG_TYPE_BASE:
-		regno = X86_SIB_BASE(insn->sib.value);
-		/*
-		 * If ModRM.mod is 0 and SIB.base == 5, the base of the
-		 * register-indirect addressing is 0. In this case, a
-		 * 32-bit displacement follows the SIB byte.
-		 */
-		if (!X86_MODRM_MOD(insn->modrm.value) && regno == 5)
-			return -EDOM;
-
-		if (X86_REX_B(insn->rex_prefix.value))
-			regno += 8;
-		break;
-
-	default:
-		pr_err_ratelimited("invalid register type: %d\n", type);
-		return -EINVAL;
-	}
-
-	if (regno >= nr_registers) {
-		WARN_ONCE(1, "decoded an instruction with an invalid register");
-		return -EINVAL;
-	}
-	return regno;
-}
-
-static int get_reg_offset(struct insn *insn, struct pt_regs *regs,
-			  enum reg_type type)
-{
-	int regno = get_regno(insn, type);
-
-	if (regno < 0)
-		return regno;
-
-	return pt_regs_offset(regs, regno);
-}
-
-/**
- * get_reg_offset_16() - Obtain offset of register indicated by instruction
- * @insn:	Instruction containing ModRM byte
- * @regs:	Register values as seen when entering kernel mode
- * @offs1:	Offset of the first operand register
- * @offs2:	Offset of the second operand register, if applicable
- *
- * Obtain the offset, in pt_regs, of the registers indicated by the ModRM byte
- * in @insn. This function is to be used with 16-bit address encodings. The
- * @offs1 and @offs2 will be written with the offset of the two registers
- * indicated by the instruction. In cases where any of the registers is not
- * referenced by the instruction, the value will be set to -EDOM.
- *
- * Returns:
- *
- * 0 on success, -EINVAL on error.
- */
-static int get_reg_offset_16(struct insn *insn, struct pt_regs *regs,
-			     int *offs1, int *offs2)
-{
-	/*
-	 * 16-bit addressing can use one or two registers. Specifics of
-	 * encodings are given in Table 2-1. "16-Bit Addressing Forms with the
-	 * ModR/M Byte" of the Intel Software Development Manual.
-	 */
-	static const int regoff1[] = {
-		offsetof(struct pt_regs, bx),
-		offsetof(struct pt_regs, bx),
-		offsetof(struct pt_regs, bp),
-		offsetof(struct pt_regs, bp),
-		offsetof(struct pt_regs, si),
-		offsetof(struct pt_regs, di),
-		offsetof(struct pt_regs, bp),
-		offsetof(struct pt_regs, bx),
-	};
-
-	static const int regoff2[] = {
-		offsetof(struct pt_regs, si),
-		offsetof(struct pt_regs, di),
-		offsetof(struct pt_regs, si),
-		offsetof(struct pt_regs, di),
-		-EDOM,
-		-EDOM,
-		-EDOM,
-		-EDOM,
-	};
-
-	if (!offs1 || !offs2)
-		return -EINVAL;
-
-	/* Operand is a register, use the generic function. */
-	if (X86_MODRM_MOD(insn->modrm.value) == 3) {
-		*offs1 = insn_get_modrm_rm_off(insn, regs);
-		*offs2 = -EDOM;
-		return 0;
-	}
-
-	*offs1 = regoff1[X86_MODRM_RM(insn->modrm.value)];
-	*offs2 = regoff2[X86_MODRM_RM(insn->modrm.value)];
-
-	/*
-	 * If ModRM.mod is 0 and ModRM.rm is 110b, then we use displacement-
-	 * only addressing. This means that no registers are involved in
-	 * computing the effective address. Thus, ensure that the first
-	 * register offset is invalid. The second register offset is already
-	 * invalid under the aforementioned conditions.
-	 */
-	if ((X86_MODRM_MOD(insn->modrm.value) == 0) &&
-	    (X86_MODRM_RM(insn->modrm.value) == 6))
-		*offs1 = -EDOM;
-
-	return 0;
-}
-
 /**
  * get_desc() - Obtain contents of a segment descriptor
  * @out:	Segment descriptor contents on success
@@ -840,58 +595,6 @@ int insn_get_code_seg_params(struct pt_regs *regs)
 	}
 }
 
-/**
- * insn_get_modrm_rm_off() - Obtain register in r/m part of the ModRM byte
- * @insn:	Instruction containing the ModRM byte
- * @regs:	Register values as seen when entering kernel mode
- *
- * Returns:
- *
- * The register indicated by the r/m part of the ModRM byte. The
- * register is obtained as an offset from the base of pt_regs. In specific
- * cases, the returned value can be -EDOM to indicate that the particular value
- * of ModRM does not refer to a register and shall be ignored.
- */
-int insn_get_modrm_rm_off(struct insn *insn, struct pt_regs *regs)
-{
-	return get_reg_offset(insn, regs, REG_TYPE_RM);
-}
-
-/**
- * insn_get_modrm_reg_off() - Obtain register in reg part of the ModRM byte
- * @insn:	Instruction containing the ModRM byte
- * @regs:	Register values as seen when entering kernel mode
- *
- * Returns:
- *
- * The register indicated by the reg part of the ModRM byte. The
- * register is obtained as an offset from the base of pt_regs.
- */
-int insn_get_modrm_reg_off(struct insn *insn, struct pt_regs *regs)
-{
-	return get_reg_offset(insn, regs, REG_TYPE_REG);
-}
-
-/**
- * insn_get_modrm_reg_ptr() - Obtain register pointer based on ModRM byte
- * @insn:	Instruction containing the ModRM byte
- * @regs:	Register values as seen when entering kernel mode
- *
- * Returns:
- *
- * The register indicated by the reg part of the ModRM byte.
- * The register is obtained as a pointer within pt_regs.
- */
-unsigned long *insn_get_modrm_reg_ptr(struct insn *insn, struct pt_regs *regs)
-{
-	int offset;
-
-	offset = insn_get_modrm_reg_off(insn, regs);
-	if (offset < 0)
-		return NULL;
-	return (void *)regs + offset;
-}
-
 /**
  * get_seg_base_limit() - obtain base address and limit of a segment
  * @insn:	Instruction. Must be valid.
@@ -940,528 +643,6 @@ static int get_seg_base_limit(struct insn *insn, struct pt_regs *regs,
 	return 0;
 }
 
-/**
- * get_eff_addr_reg() - Obtain effective address from register operand
- * @insn:	Instruction. Must be valid.
- * @regs:	Register values as seen when entering kernel mode
- * @regoff:	Obtained operand offset, in pt_regs, with the effective address
- * @eff_addr:	Obtained effective address
- *
- * Obtain the effective address stored in the register operand as indicated by
- * the ModRM byte. This function is to be used only with register addressing
- * (i.e.,  ModRM.mod is 3). The effective address is saved in @eff_addr. The
- * register operand, as an offset from the base of pt_regs, is saved in @regoff;
- * such offset can then be used to resolve the segment associated with the
- * operand. This function can be used with any of the supported address sizes
- * in x86.
- *
- * Returns:
- *
- * 0 on success. @eff_addr will have the effective address stored in the
- * operand indicated by ModRM. @regoff will have such operand as an offset from
- * the base of pt_regs.
- *
- * -EINVAL on error.
- */
-static int get_eff_addr_reg(struct insn *insn, struct pt_regs *regs,
-			    int *regoff, long *eff_addr)
-{
-	int ret;
-
-	ret = insn_get_modrm(insn);
-	if (ret)
-		return ret;
-
-	if (X86_MODRM_MOD(insn->modrm.value) != 3)
-		return -EINVAL;
-
-	*regoff = get_reg_offset(insn, regs, REG_TYPE_RM);
-	if (*regoff < 0)
-		return -EINVAL;
-
-	/* Ignore bytes that are outside the address size. */
-	if (insn->addr_bytes == 2)
-		*eff_addr = regs_get_register(regs, *regoff) & 0xffff;
-	else if (insn->addr_bytes == 4)
-		*eff_addr = regs_get_register(regs, *regoff) & 0xffffffff;
-	else /* 64-bit address */
-		*eff_addr = regs_get_register(regs, *regoff);
-
-	return 0;
-}
-
-/**
- * get_eff_addr_modrm() - Obtain referenced effective address via ModRM
- * @insn:	Instruction. Must be valid.
- * @regs:	Register values as seen when entering kernel mode
- * @regoff:	Obtained operand offset, in pt_regs, associated with segment
- * @eff_addr:	Obtained effective address
- *
- * Obtain the effective address referenced by the ModRM byte of @insn. After
- * identifying the registers involved in the register-indirect memory reference,
- * its value is obtained from the operands in @regs. The computed address is
- * stored @eff_addr. Also, the register operand that indicates the associated
- * segment is stored in @regoff, this parameter can later be used to determine
- * such segment.
- *
- * Returns:
- *
- * 0 on success. @eff_addr will have the referenced effective address. @regoff
- * will have a register, as an offset from the base of pt_regs, that can be used
- * to resolve the associated segment.
- *
- * -EINVAL on error.
- */
-static int get_eff_addr_modrm(struct insn *insn, struct pt_regs *regs,
-			      int *regoff, long *eff_addr)
-{
-	long tmp;
-	int ret;
-
-	if (insn->addr_bytes != 8 && insn->addr_bytes != 4)
-		return -EINVAL;
-
-	ret = insn_get_modrm(insn);
-	if (ret)
-		return ret;
-
-	if (X86_MODRM_MOD(insn->modrm.value) > 2)
-		return -EINVAL;
-
-	*regoff = get_reg_offset(insn, regs, REG_TYPE_RM);
-
-	/*
-	 * -EDOM means that we must ignore the address_offset. In such a case,
-	 * in 64-bit mode the effective address relative to the rIP of the
-	 * following instruction.
-	 */
-	if (*regoff == -EDOM) {
-		if (any_64bit_mode(regs))
-			tmp = regs->ip + insn->length;
-		else
-			tmp = 0;
-	} else if (*regoff < 0) {
-		return -EINVAL;
-	} else {
-		tmp = regs_get_register(regs, *regoff);
-	}
-
-	if (insn->addr_bytes == 4) {
-		int addr32 = (int)(tmp & 0xffffffff) + insn->displacement.value;
-
-		*eff_addr = addr32 & 0xffffffff;
-	} else {
-		*eff_addr = tmp + insn->displacement.value;
-	}
-
-	return 0;
-}
-
-/**
- * get_eff_addr_modrm_16() - Obtain referenced effective address via ModRM
- * @insn:	Instruction. Must be valid.
- * @regs:	Register values as seen when entering kernel mode
- * @regoff:	Obtained operand offset, in pt_regs, associated with segment
- * @eff_addr:	Obtained effective address
- *
- * Obtain the 16-bit effective address referenced by the ModRM byte of @insn.
- * After identifying the registers involved in the register-indirect memory
- * reference, its value is obtained from the operands in @regs. The computed
- * address is stored @eff_addr. Also, the register operand that indicates
- * the associated segment is stored in @regoff, this parameter can later be used
- * to determine such segment.
- *
- * Returns:
- *
- * 0 on success. @eff_addr will have the referenced effective address. @regoff
- * will have a register, as an offset from the base of pt_regs, that can be used
- * to resolve the associated segment.
- *
- * -EINVAL on error.
- */
-static int get_eff_addr_modrm_16(struct insn *insn, struct pt_regs *regs,
-				 int *regoff, short *eff_addr)
-{
-	int addr_offset1, addr_offset2, ret;
-	short addr1 = 0, addr2 = 0, displacement;
-
-	if (insn->addr_bytes != 2)
-		return -EINVAL;
-
-	insn_get_modrm(insn);
-
-	if (!insn->modrm.nbytes)
-		return -EINVAL;
-
-	if (X86_MODRM_MOD(insn->modrm.value) > 2)
-		return -EINVAL;
-
-	ret = get_reg_offset_16(insn, regs, &addr_offset1, &addr_offset2);
-	if (ret < 0)
-		return -EINVAL;
-
-	/*
-	 * Don't fail on invalid offset values. They might be invalid because
-	 * they cannot be used for this particular value of ModRM. Instead, use
-	 * them in the computation only if they contain a valid value.
-	 */
-	if (addr_offset1 != -EDOM)
-		addr1 = regs_get_register(regs, addr_offset1) & 0xffff;
-
-	if (addr_offset2 != -EDOM)
-		addr2 = regs_get_register(regs, addr_offset2) & 0xffff;
-
-	displacement = insn->displacement.value & 0xffff;
-	*eff_addr = addr1 + addr2 + displacement;
-
-	/*
-	 * The first operand register could indicate to use of either SS or DS
-	 * registers to obtain the segment selector.  The second operand
-	 * register can only indicate the use of DS. Thus, the first operand
-	 * will be used to obtain the segment selector.
-	 */
-	*regoff = addr_offset1;
-
-	return 0;
-}
-
-/**
- * get_eff_addr_sib() - Obtain referenced effective address via SIB
- * @insn:	Instruction. Must be valid.
- * @regs:	Register values as seen when entering kernel mode
- * @base_offset: Obtained operand offset, in pt_regs, associated with segment
- * @eff_addr:	Obtained effective address
- *
- * Obtain the effective address referenced by the SIB byte of @insn. After
- * identifying the registers involved in the indexed, register-indirect memory
- * reference, its value is obtained from the operands in @regs. The computed
- * address is stored @eff_addr. Also, the register operand that indicates the
- * associated segment is stored in @base_offset; this parameter can later be
- * used to determine such segment.
- *
- * Returns:
- *
- * 0 on success. @eff_addr will have the referenced effective address.
- * @base_offset will have a register, as an offset from the base of pt_regs,
- * that can be used to resolve the associated segment.
- *
- * Negative value on error.
- */
-static int get_eff_addr_sib(struct insn *insn, struct pt_regs *regs,
-			    int *base_offset, long *eff_addr)
-{
-	long base, indx;
-	int indx_offset;
-	int ret;
-
-	if (insn->addr_bytes != 8 && insn->addr_bytes != 4)
-		return -EINVAL;
-
-	ret = insn_get_modrm(insn);
-	if (ret)
-		return ret;
-
-	if (!insn->modrm.nbytes)
-		return -EINVAL;
-
-	if (X86_MODRM_MOD(insn->modrm.value) > 2)
-		return -EINVAL;
-
-	ret = insn_get_sib(insn);
-	if (ret)
-		return ret;
-
-	if (!insn->sib.nbytes)
-		return -EINVAL;
-
-	*base_offset = get_reg_offset(insn, regs, REG_TYPE_BASE);
-	indx_offset = get_reg_offset(insn, regs, REG_TYPE_INDEX);
-
-	/*
-	 * Negative values in the base and index offset means an error when
-	 * decoding the SIB byte. Except -EDOM, which means that the registers
-	 * should not be used in the address computation.
-	 */
-	if (*base_offset == -EDOM)
-		base = 0;
-	else if (*base_offset < 0)
-		return -EINVAL;
-	else
-		base = regs_get_register(regs, *base_offset);
-
-	if (indx_offset == -EDOM)
-		indx = 0;
-	else if (indx_offset < 0)
-		return -EINVAL;
-	else
-		indx = regs_get_register(regs, indx_offset);
-
-	if (insn->addr_bytes == 4) {
-		int addr32, base32, idx32;
-
-		base32 = base & 0xffffffff;
-		idx32 = indx & 0xffffffff;
-
-		addr32 = base32 + idx32 * (1 << X86_SIB_SCALE(insn->sib.value));
-		addr32 += insn->displacement.value;
-
-		*eff_addr = addr32 & 0xffffffff;
-	} else {
-		*eff_addr = base + indx * (1 << X86_SIB_SCALE(insn->sib.value));
-		*eff_addr += insn->displacement.value;
-	}
-
-	return 0;
-}
-
-/**
- * get_addr_ref_16() - Obtain the 16-bit address referred by instruction
- * @insn:	Instruction containing ModRM byte and displacement
- * @regs:	Register values as seen when entering kernel mode
- *
- * This function is to be used with 16-bit address encodings. Obtain the memory
- * address referred by the instruction's ModRM and displacement bytes. Also, the
- * segment used as base is determined by either any segment override prefixes in
- * @insn or the default segment of the registers involved in the address
- * computation. In protected mode, segment limits are enforced.
- *
- * Returns:
- *
- * Linear address referenced by the instruction operands on success.
- *
- * -1L on error.
- */
-static void __user *get_addr_ref_16(struct insn *insn, struct pt_regs *regs)
-{
-	unsigned long linear_addr = -1L, seg_base, seg_limit;
-	int ret, regoff;
-	short eff_addr;
-	long tmp;
-
-	if (insn_get_displacement(insn))
-		goto out;
-
-	if (insn->addr_bytes != 2)
-		goto out;
-
-	if (X86_MODRM_MOD(insn->modrm.value) == 3) {
-		ret = get_eff_addr_reg(insn, regs, &regoff, &tmp);
-		if (ret)
-			goto out;
-
-		eff_addr = tmp;
-	} else {
-		ret = get_eff_addr_modrm_16(insn, regs, &regoff, &eff_addr);
-		if (ret)
-			goto out;
-	}
-
-	ret = get_seg_base_limit(insn, regs, regoff, &seg_base, &seg_limit);
-	if (ret)
-		goto out;
-
-	/*
-	 * Before computing the linear address, make sure the effective address
-	 * is within the limits of the segment. In virtual-8086 mode, segment
-	 * limits are not enforced. In such a case, the segment limit is -1L to
-	 * reflect this fact.
-	 */
-	if ((unsigned long)(eff_addr & 0xffff) > seg_limit)
-		goto out;
-
-	linear_addr = (unsigned long)(eff_addr & 0xffff) + seg_base;
-
-	/* Limit linear address to 20 bits */
-	if (v8086_mode(regs))
-		linear_addr &= 0xfffff;
-
-out:
-	return (void __user *)linear_addr;
-}
-
-/**
- * get_addr_ref_32() - Obtain a 32-bit linear address
- * @insn:	Instruction with ModRM, SIB bytes and displacement
- * @regs:	Register values as seen when entering kernel mode
- *
- * This function is to be used with 32-bit address encodings to obtain the
- * linear memory address referred by the instruction's ModRM, SIB,
- * displacement bytes and segment base address, as applicable. If in protected
- * mode, segment limits are enforced.
- *
- * Returns:
- *
- * Linear address referenced by instruction and registers on success.
- *
- * -1L on error.
- */
-static void __user *get_addr_ref_32(struct insn *insn, struct pt_regs *regs)
-{
-	unsigned long linear_addr = -1L, seg_base, seg_limit;
-	int eff_addr, regoff;
-	long tmp;
-	int ret;
-
-	if (insn->addr_bytes != 4)
-		goto out;
-
-	if (X86_MODRM_MOD(insn->modrm.value) == 3) {
-		ret = get_eff_addr_reg(insn, regs, &regoff, &tmp);
-		if (ret)
-			goto out;
-
-		eff_addr = tmp;
-
-	} else {
-		if (insn->sib.nbytes) {
-			ret = get_eff_addr_sib(insn, regs, &regoff, &tmp);
-			if (ret)
-				goto out;
-
-			eff_addr = tmp;
-		} else {
-			ret = get_eff_addr_modrm(insn, regs, &regoff, &tmp);
-			if (ret)
-				goto out;
-
-			eff_addr = tmp;
-		}
-	}
-
-	ret = get_seg_base_limit(insn, regs, regoff, &seg_base, &seg_limit);
-	if (ret)
-		goto out;
-
-	/*
-	 * In protected mode, before computing the linear address, make sure
-	 * the effective address is within the limits of the segment.
-	 * 32-bit addresses can be used in long and virtual-8086 modes if an
-	 * address override prefix is used. In such cases, segment limits are
-	 * not enforced. When in virtual-8086 mode, the segment limit is -1L
-	 * to reflect this situation.
-	 *
-	 * After computed, the effective address is treated as an unsigned
-	 * quantity.
-	 */
-	if (!any_64bit_mode(regs) && ((unsigned int)eff_addr > seg_limit))
-		goto out;
-
-	/*
-	 * Even though 32-bit address encodings are allowed in virtual-8086
-	 * mode, the address range is still limited to [0x-0xffff].
-	 */
-	if (v8086_mode(regs) && (eff_addr & ~0xffff))
-		goto out;
-
-	/*
-	 * Data type long could be 64 bits in size. Ensure that our 32-bit
-	 * effective address is not sign-extended when computing the linear
-	 * address.
-	 */
-	linear_addr = (unsigned long)(eff_addr & 0xffffffff) + seg_base;
-
-	/* Limit linear address to 20 bits */
-	if (v8086_mode(regs))
-		linear_addr &= 0xfffff;
-
-out:
-	return (void __user *)linear_addr;
-}
-
-/**
- * get_addr_ref_64() - Obtain a 64-bit linear address
- * @insn:	Instruction struct with ModRM and SIB bytes and displacement
- * @regs:	Structure with register values as seen when entering kernel mode
- *
- * This function is to be used with 64-bit address encodings to obtain the
- * linear memory address referred by the instruction's ModRM, SIB,
- * displacement bytes and segment base address, as applicable.
- *
- * Returns:
- *
- * Linear address referenced by instruction and registers on success.
- *
- * -1L on error.
- */
-#ifndef CONFIG_X86_64
-static void __user *get_addr_ref_64(struct insn *insn, struct pt_regs *regs)
-{
-	return (void __user *)-1L;
-}
-#else
-static void __user *get_addr_ref_64(struct insn *insn, struct pt_regs *regs)
-{
-	unsigned long linear_addr = -1L, seg_base;
-	int regoff, ret;
-	long eff_addr;
-
-	if (insn->addr_bytes != 8)
-		goto out;
-
-	if (X86_MODRM_MOD(insn->modrm.value) == 3) {
-		ret = get_eff_addr_reg(insn, regs, &regoff, &eff_addr);
-		if (ret)
-			goto out;
-
-	} else {
-		if (insn->sib.nbytes) {
-			ret = get_eff_addr_sib(insn, regs, &regoff, &eff_addr);
-			if (ret)
-				goto out;
-		} else {
-			ret = get_eff_addr_modrm(insn, regs, &regoff, &eff_addr);
-			if (ret)
-				goto out;
-		}
-
-	}
-
-	ret = get_seg_base_limit(insn, regs, regoff, &seg_base, NULL);
-	if (ret)
-		goto out;
-
-	linear_addr = (unsigned long)eff_addr + seg_base;
-
-out:
-	return (void __user *)linear_addr;
-}
-#endif /* CONFIG_X86_64 */
-
-/**
- * insn_get_addr_ref() - Obtain the linear address referred by instruction
- * @insn:	Instruction structure containing ModRM byte and displacement
- * @regs:	Structure with register values as seen when entering kernel mode
- *
- * Obtain the linear address referred by the instruction's ModRM, SIB and
- * displacement bytes, and segment base, as applicable. In protected mode,
- * segment limits are enforced.
- *
- * Returns:
- *
- * Linear address referenced by instruction and registers on success.
- *
- * -1L on error.
- */
-void __user *insn_get_addr_ref(struct insn *insn, struct pt_regs *regs)
-{
-	if (!insn || !regs)
-		return (void __user *)-1L;
-
-	if (insn_get_opcode(insn))
-		return (void __user *)-1L;
-
-	switch (insn->addr_bytes) {
-	case 2:
-		return get_addr_ref_16(insn, regs);
-	case 4:
-		return get_addr_ref_32(insn, regs);
-	case 8:
-		return get_addr_ref_64(insn, regs);
-	default:
-		return (void __user *)-1L;
-	}
-}
-
 int insn_get_effective_ip(struct pt_regs *regs, unsigned long *ip)
 {
 	unsigned long seg_base = 0;
@@ -1584,87 +765,3 @@ bool insn_decode_from_regs(struct insn *insn, struct pt_regs *regs,
 
 	return true;
 }
-
-/**
- * insn_decode_mmio() - Decode a MMIO instruction
- * @insn:	Structure to store decoded instruction
- * @bytes:	Returns size of memory operand
- *
- * Decodes instruction that used for Memory-mapped I/O.
- *
- * Returns:
- *
- * Type of the instruction. Size of the memory operand is stored in
- * @bytes. If decode failed, INSN_MMIO_DECODE_FAILED returned.
- */
-enum insn_mmio_type insn_decode_mmio(struct insn *insn, int *bytes)
-{
-	enum insn_mmio_type type = INSN_MMIO_DECODE_FAILED;
-
-	*bytes = 0;
-
-	if (insn_get_opcode(insn))
-		return INSN_MMIO_DECODE_FAILED;
-
-	switch (insn->opcode.bytes[0]) {
-	case 0x88: /* MOV m8,r8 */
-		*bytes = 1;
-		fallthrough;
-	case 0x89: /* MOV m16/m32/m64, r16/m32/m64 */
-		if (!*bytes)
-			*bytes = insn->opnd_bytes;
-		type = INSN_MMIO_WRITE;
-		break;
-
-	case 0xc6: /* MOV m8, imm8 */
-		*bytes = 1;
-		fallthrough;
-	case 0xc7: /* MOV m16/m32/m64, imm16/imm32/imm64 */
-		if (!*bytes)
-			*bytes = insn->opnd_bytes;
-		type = INSN_MMIO_WRITE_IMM;
-		break;
-
-	case 0x8a: /* MOV r8, m8 */
-		*bytes = 1;
-		fallthrough;
-	case 0x8b: /* MOV r16/r32/r64, m16/m32/m64 */
-		if (!*bytes)
-			*bytes = insn->opnd_bytes;
-		type = INSN_MMIO_READ;
-		break;
-
-	case 0xa4: /* MOVS m8, m8 */
-		*bytes = 1;
-		fallthrough;
-	case 0xa5: /* MOVS m16/m32/m64, m16/m32/m64 */
-		if (!*bytes)
-			*bytes = insn->opnd_bytes;
-		type = INSN_MMIO_MOVS;
-		break;
-
-	case 0x0f: /* Two-byte instruction */
-		switch (insn->opcode.bytes[1]) {
-		case 0xb6: /* MOVZX r16/r32/r64, m8 */
-			*bytes = 1;
-			fallthrough;
-		case 0xb7: /* MOVZX r32/r64, m16 */
-			if (!*bytes)
-				*bytes = 2;
-			type = INSN_MMIO_READ_ZERO_EXTEND;
-			break;
-
-		case 0xbe: /* MOVSX r16/r32/r64, m8 */
-			*bytes = 1;
-			fallthrough;
-		case 0xbf: /* MOVSX r32/r64, m16 */
-			if (!*bytes)
-				*bytes = 2;
-			type = INSN_MMIO_READ_SIGN_EXTEND;
-			break;
-		}
-		break;
-	}
-
-	return type;
-}

---

## [9] vsntk18@gmail.com — 2024-06-10
*Subject: [PATCH v6 08/10] x86/sev: Handle CLFLUSH MMIO events*

From: Joerg Roedel <jroedel@suse.de>

Handle CLFLUSH instruction to MMIO memory in the #VC handler. The
instruction is ignored by the handler, as the Hypervisor is
responsible for cache management of emulated MMIO memory.

Signed-off-by: Joerg Roedel <jroedel@suse.de>
Signed-off-by: Vasant Karasulli <vkarasulli@suse.de>
---
 arch/x86/include/asm/insn-eval.h | 1 +
 arch/x86/kernel/sev-shared.c     | 3 +++
 arch/x86/lib/insn-eval-shared.c  | 7 +++++++
 3 files changed, 11 insertions(+)

diff --git a/arch/x86/include/asm/insn-eval.h b/arch/x86/include/asm/insn-eval.h
index 54368a43abf6..3bcea641913a 100644
--- a/arch/x86/include/asm/insn-eval.h
+++ b/arch/x86/include/asm/insn-eval.h
@@ -40,6 +40,7 @@ enum insn_mmio_type {
 	INSN_MMIO_READ_ZERO_EXTEND,
 	INSN_MMIO_READ_SIGN_EXTEND,
 	INSN_MMIO_MOVS,
+	INSN_MMIO_IGNORE,
 };
 
 enum insn_mmio_type insn_decode_mmio(struct insn *insn, int *bytes);
diff --git a/arch/x86/kernel/sev-shared.c b/arch/x86/kernel/sev-shared.c
index 1b25a6cacec7..2a963ad84f10 100644
--- a/arch/x86/kernel/sev-shared.c
+++ b/arch/x86/kernel/sev-shared.c
@@ -1171,6 +1171,9 @@ static enum es_result vc_handle_mmio(struct ghcb *ghcb, struct es_em_ctxt *ctxt)
 	if (mmio == INSN_MMIO_DECODE_FAILED)
 		return ES_DECODE_FAILED;
 
+	if (mmio == INSN_MMIO_IGNORE)
+		return ES_OK;
+
 	if (mmio != INSN_MMIO_WRITE_IMM && mmio != INSN_MMIO_MOVS) {
 		reg_data = insn_get_modrm_reg_ptr(insn, ctxt->regs);
 		if (!reg_data)
diff --git a/arch/x86/lib/insn-eval-shared.c b/arch/x86/lib/insn-eval-shared.c
index 02acdc2921ff..27fd347d84ae 100644
--- a/arch/x86/lib/insn-eval-shared.c
+++ b/arch/x86/lib/insn-eval-shared.c
@@ -906,6 +906,13 @@ enum insn_mmio_type insn_decode_mmio(struct insn *insn, int *bytes)
 				*bytes = 2;
 			type = INSN_MMIO_READ_SIGN_EXTEND;
 			break;
+		case 0xae: /* CLFLUSH */
+			/*
+			 * Ignore CLFLUSHes - those go to emulated MMIO anyway and the
+			 * hypervisor is responsible for cache management.
+			 */
+			type = INSN_MMIO_IGNORE;
+			break;
 		}
 		break;
 	}

---

## [10] vsntk18@gmail.com — 2024-06-10
*Subject: [PATCH v6 09/10] x86/kexec/64: Support kexec under SEV-ES with AP Jump Table Blob*

From: Joerg Roedel <jroedel@suse.de>

When the AP jump table blob is installed the kernel can hand over the
APs from the old to the new kernel. Enable kexec when the AP jump
table blob has been installed.

Signed-off-by: Joerg Roedel <jroedel@suse.de>
Signed-off-by: Vasant Karasulli <vkarasulli@suse.de>
---
 arch/x86/include/asm/sev.h         |  2 ++
 arch/x86/kernel/machine_kexec_64.c |  3 ++-
 arch/x86/kernel/sev.c              | 15 +++++++++++++++
 3 files changed, 19 insertions(+), 1 deletion(-)

diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index 6f681ced6594..e557eadb0ec9 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -233,6 +233,7 @@ u64 snp_get_unsupported_features(u64 status);
 u64 sev_get_status(void);
 void sev_show_status(void);
 void sev_es_stop_this_cpu(void);
+bool sev_kexec_supported(void);
 #else
 static inline void sev_es_ist_enter(struct pt_regs *regs) { }
 static inline void sev_es_ist_exit(void) { }
@@ -263,6 +264,7 @@ static inline u64 snp_get_unsupported_features(u64 status) { return 0; }
 static inline u64 sev_get_status(void) { return 0; }
 static inline void sev_show_status(void) { }
 static inline void sev_es_stop_this_cpu(void) { }
+static inline bool sev_kexec_supported(void) { return true; }
 #endif
 
 #ifdef CONFIG_KVM_AMD_SEV
diff --git a/arch/x86/kernel/machine_kexec_64.c b/arch/x86/kernel/machine_kexec_64.c
index 1dfb47df5c01..43f5f7e48cbc 100644
--- a/arch/x86/kernel/machine_kexec_64.c
+++ b/arch/x86/kernel/machine_kexec_64.c
@@ -28,6 +28,7 @@
 #include <asm/setup.h>
 #include <asm/set_memory.h>
 #include <asm/cpu.h>
+#include <asm/sev.h>
 
 #ifdef CONFIG_ACPI
 /*
@@ -269,7 +270,7 @@ static void load_segments(void)
 
 static bool machine_kexec_supported(void)
 {
-	if (cc_platform_has(CC_ATTR_GUEST_STATE_ENCRYPT))
+	if (!sev_kexec_supported())
 		return false;
 
 	return true;
diff --git a/arch/x86/kernel/sev.c b/arch/x86/kernel/sev.c
index 30ede17b5a04..e64320507da2 100644
--- a/arch/x86/kernel/sev.c
+++ b/arch/x86/kernel/sev.c
@@ -1463,6 +1463,21 @@ static void __init sev_es_setup_play_dead(void)
 static inline void sev_es_setup_play_dead(void) { }
 #endif
 
+bool sev_kexec_supported(void)
+{
+	if (!cc_platform_has(CC_ATTR_GUEST_STATE_ENCRYPT))
+		return true;
+
+	/*
+	 * KEXEC with SEV-ES and more than one CPU is only supported
+	 * when the AP jump table is installed.
+	 */
+	if (num_possible_cpus() > 1)
+		return sev_ap_jumptable_blob_installed;
+	else
+		return true;
+}
+
 static void __init alloc_runtime_data(int cpu)
 {
 	struct sev_es_runtime_data *data;

---

## [11] vsntk18@gmail.com — 2024-06-10
*Subject: [PATCH v6 10/10] x86/sev: Exclude AP jump table related code for SEV-SNP guests*

From: Vasant Karasulli <vkarasulli@suse.de>

Unlike SEV-ES, AP jump table technique is not used in SEV-SNP
when transitioning from one layer of code to another
(e.g. when going from UEFI to the OS).

Signed-off-by: Vasant Karasulli <vkarasulli@suse.de>
---
 arch/x86/kernel/sev.c    | 6 +++++-
 arch/x86/realmode/init.c | 5 +++--
 2 files changed, 8 insertions(+), 3 deletions(-)

diff --git a/arch/x86/kernel/sev.c b/arch/x86/kernel/sev.c
index e64320507da2..a9cf74512269 100644
--- a/arch/x86/kernel/sev.c
+++ b/arch/x86/kernel/sev.c
@@ -1392,7 +1392,8 @@ STACK_FRAME_NON_STANDARD(sev_jumptable_ap_park);
 void sev_es_stop_this_cpu(void)
 {
 	if (!(cc_vendor == CC_VENDOR_AMD) ||
-	    !cc_platform_has(CC_ATTR_GUEST_STATE_ENCRYPT))
+	    !cc_platform_has(CC_ATTR_GUEST_STATE_ENCRYPT) ||
+	     cc_platform_has(CC_ATTR_GUEST_SEV_SNP))
 		return;
 
 	/* Only park in the AP jump table when the code has been installed */
@@ -1468,6 +1469,9 @@ bool sev_kexec_supported(void)
 	if (!cc_platform_has(CC_ATTR_GUEST_STATE_ENCRYPT))
 		return true;
 
+	if (cc_platform_has(CC_ATTR_GUEST_SEV_SNP))
+		return false;
+
 	/*
 	 * KEXEC with SEV-ES and more than one CPU is only supported
 	 * when the AP jump table is installed.
diff --git a/arch/x86/realmode/init.c b/arch/x86/realmode/init.c
index f9bc444a3064..ed798939be5d 100644
--- a/arch/x86/realmode/init.c
+++ b/arch/x86/realmode/init.c
@@ -80,8 +80,9 @@ static void __init sme_sev_setup_real_mode(struct trampoline_header *th)
 		 */
 		th->start = (u64) secondary_startup_64_no_verify;
 
-		if (sev_es_setup_ap_jump_table(real_mode_header))
-			panic("Failed to get/update SEV-ES AP Jump Table");
+		if (!cc_platform_has(CC_ATTR_GUEST_SEV_SNP))
+			if (sev_es_setup_ap_jump_table(real_mode_header))
+				panic("Failed to get/update SEV-ES AP Jump Table");
 	}
 #endif
 }

---

## [12] Greg KH — 2024-06-10
*Subject: Re: [PATCH v6 00/10] x86/sev: KEXEC/KDUMP support for SEV-ES guests*

On Mon, Jun 10, 2024 at 12:21:03PM +0200, vsntk18@gmail.com wrote:
> From: Vasant Karasulli <vkarasulli@suse.de>
> 

<formletter>

This is not the correct way to submit patches for inclusion in the
stable kernel tree.  Please read:
    https://www.kernel.org/doc/html/latest/process/stable-kernel-rules.html
for how to do this properly.

</formletter>

---
