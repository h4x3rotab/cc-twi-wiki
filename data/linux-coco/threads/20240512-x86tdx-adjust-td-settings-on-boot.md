---
title: 'x86/tdx: Adjust TD settings on boot'
date: 2024-05-12
last_reply: 2024-05-15
message_count: 10
participants: ['Kirill A. Shutemov', 'Nikolay Borisov', 'Dave Hansen']
---

## [1] Kirill A. Shutemov — 2024-05-12

The patchset adjusts a few TD settings on boot for the optimal functioning
of the system:

  - Disable EPT violation #VE on private memory if TD can control it

    The newer TDX module allows the guest to control whether it wants to
    see #VE on EPT violation on private memory. The Linux kernel does not
    want such #VEs and needs to disable them.

  - Enable virtualization of topology-related CPUID leafs X2APIC_APICID MSR;

    The ENUM_TOPOLOGY feature allows the VMM to provide topology
    information to the guest. Enabling the feature eliminates
    topology-related #VEs: the TDX module virtualizes accesses to the
    CPUID leafs and the MSR.

    It allows TDX guest to run with non-trivial topology configuration.

v4:
 - Drop unnecessary enumeration;
 - Drop TDG.SYS.RD wrapper;
 - CC stable@ for SEPT disable patch;
 - Update commit messages;
v3:
  - Update commit messages;
  - Rework patches 3/4 and 4/4;
v2:
  - Rebased;
  - Allow write to TDCS_TD_CTLS to fail;
  - Adjust commit messages;

Kirill A. Shutemov (4):
  x86/tdx: Factor out TD metadata write TDCALL
  x86/tdx: Rename tdx_parse_tdinfo() to tdx_setup()
  x86/tdx: Dynamically disable SEPT violations from causing #VEs
  x86/tdx: Enable CPU topology enumeration

 arch/x86/coco/tdx/tdx.c           | 140 +++++++++++++++++++++++++-----
 arch/x86/include/asm/shared/tdx.h |  13 ++-
 2 files changed, 130 insertions(+), 23 deletions(-)

---

## [2] Kirill A. Shutemov — 2024-05-12
*Subject: [PATCHv4 1/4] x86/tdx: Factor out TD metadata write TDCALL*

The TDG_VM_WR TDCALL is used to ask the TDX module to change some
TD-specific VM configuration. There is currently only one user in the
kernel of this TDCALL leaf.  More will be added shortly.

Refactor to make way for more users of TDG_VM_WR who will need to modify
other TD configuration values.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Reviewed-by: Kuppuswamy Sathyanarayanan <sathyanarayanan.kuppuswamy@linux.intel.com>
Cc: stable@vger.kernel.org
---
 arch/x86/coco/tdx/tdx.c | 18 +++++++++++++-----
 1 file changed, 13 insertions(+), 5 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index b556cbcc847e..4bb786dcd6b4 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -77,6 +77,18 @@ static inline void tdcall(u64 fn, struct tdx_module_args *args)
 		panic("TDCALL %lld failed (Buggy TDX module!)\n", fn);
 }
 
+/* Write TD-scoped metadata */
+static inline u64 tdg_vm_wr(u64 field, u64 value, u64 mask)
+{
+	struct tdx_module_args args = {
+		.rdx = field,
+		.r8 = value,
+		.r9 = mask,
+	};
+
+	return __tdcall(TDG_VM_WR, &args);
+}
+
 /**
  * tdx_mcall_get_report0() - Wrapper to get TDREPORT0 (a.k.a. TDREPORT
  *                           subtype 0) using TDG.MR.REPORT TDCALL.
@@ -901,10 +913,6 @@ static void tdx_kexec_finish(void)
 
 void __init tdx_early_init(void)
 {
-	struct tdx_module_args args = {
-		.rdx = TDCS_NOTIFY_ENABLES,
-		.r9 = -1ULL,
-	};
 	u64 cc_mask;
 	u32 eax, sig[3];
 
@@ -923,7 +931,7 @@ void __init tdx_early_init(void)
 	cc_set_mask(cc_mask);
 
 	/* Kernel does not use NOTIFY_ENABLES and does not need random #VEs */
-	tdcall(TDG_VM_WR, &args);
+	tdg_vm_wr(TDCS_NOTIFY_ENABLES, 0, -1ULL);
 
 	/*
 	 * All bits above GPA width are reserved and kernel treats shared bit

---

## [3] Kirill A. Shutemov — 2024-05-12
*Subject: [PATCHv4 2/4] x86/tdx: Rename tdx_parse_tdinfo() to tdx_setup()*

Rename tdx_parse_tdinfo() to tdx_setup() and move setting NOTIFY_ENABLES
there.

The function will be extended to adjust TD configuration.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Reviewed-by: Kuppuswamy Sathyanarayanan <sathyanarayanan.kuppuswamy@linux.intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Cc: stable@vger.kernel.org
---
 arch/x86/coco/tdx/tdx.c | 13 ++++++++-----
 1 file changed, 8 insertions(+), 5 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 4bb786dcd6b4..1ff571cb9177 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -179,7 +179,7 @@ static void __noreturn tdx_panic(const char *msg)
 		__tdx_hypercall(&args);
 }
 
-static void tdx_parse_tdinfo(u64 *cc_mask)
+static void tdx_setup(u64 *cc_mask)
 {
 	struct tdx_module_args args = {};
 	unsigned int gpa_width;
@@ -204,6 +204,9 @@ static void tdx_parse_tdinfo(u64 *cc_mask)
 	gpa_width = args.rcx & GENMASK(5, 0);
 	*cc_mask = BIT_ULL(gpa_width - 1);
 
+	/* Kernel does not use NOTIFY_ENABLES and does not need random #VEs */
+	tdg_vm_wr(TDCS_NOTIFY_ENABLES, 0, -1ULL);
+
 	/*
 	 * The kernel can not handle #VE's when accessing normal kernel
 	 * memory.  Ensure that no #VE will be delivered for accesses to
@@ -927,11 +930,11 @@ void __init tdx_early_init(void)
 	setup_force_cpu_cap(X86_FEATURE_TSC_RELIABLE);
 
 	cc_vendor = CC_VENDOR_INTEL;
-	tdx_parse_tdinfo(&cc_mask);
-	cc_set_mask(cc_mask);
 
-	/* Kernel does not use NOTIFY_ENABLES and does not need random #VEs */
-	tdg_vm_wr(TDCS_NOTIFY_ENABLES, 0, -1ULL);
+	/* Configure the TD */
+	tdx_setup(&cc_mask);
+
+	cc_set_mask(cc_mask);
 
 	/*
 	 * All bits above GPA width are reserved and kernel treats shared bit

---

## [4] Kirill A. Shutemov — 2024-05-12
*Subject: [PATCHv4 3/4] x86/tdx: Dynamically disable SEPT violations from causing #VEs*

Memory access #VE's are hard for Linux to handle in contexts like the
entry code or NMIs.  But other OSes need them for functionality.
There's a static (pre-guest-boot) way for a VMM to choose one or the
other.  But VMMs don't always know which OS they are booting, so they
choose to deliver those #VE's so the "other" OSes will work.  That,
unfortunately has left us in the lurch and exposed to these
hard-to-handle #VEs.

The TDX module has introduced a new feature.  Even if the static
configuration is "send nasty #VE's", the kernel can dynamically request
that they be disabled.

Check if the feature is available and disable SEPT #VE if possible.

If the TD allowed to disable/enable SEPT #VEs, the ATTR_SEPT_VE_DISABLE
attribute is no longer reliable. It reflects the initial state of the
control for the TD, but it will not be updated if someone (e.g. bootloader)
changes it before the kernel starts. Kernel must check TDCS_TD_CTLS bit to
determine if SEPT #VEs are enabled or disabled.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Fixes: 373e715e31bf ("x86/tdx: Panic on bad configs that #VE on "private" memory access")
Cc: stable@vger.kernel.org
---
 arch/x86/coco/tdx/tdx.c           | 88 +++++++++++++++++++++++++------
 arch/x86/include/asm/shared/tdx.h | 11 +++-
 2 files changed, 83 insertions(+), 16 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 1ff571cb9177..ba37f4306f4e 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -77,6 +77,20 @@ static inline void tdcall(u64 fn, struct tdx_module_args *args)
 		panic("TDCALL %lld failed (Buggy TDX module!)\n", fn);
 }
 
+/* Read TD-scoped metadata */
+static inline u64 tdg_vm_rd(u64 field, u64 *value)
+{
+	struct tdx_module_args args = {
+		.rdx = field,
+	};
+	u64 ret;
+
+	ret = __tdcall_ret(TDG_VM_RD, &args);
+	*value = args.r8;
+
+	return ret;
+}
+
 /* Write TD-scoped metadata */
 static inline u64 tdg_vm_wr(u64 field, u64 value, u64 mask)
 {
@@ -179,6 +193,62 @@ static void __noreturn tdx_panic(const char *msg)
 		__tdx_hypercall(&args);
 }
 
+/*
+ * The kernel cannot handle #VEs when accessing normal kernel memory. Ensure
+ * that no #VE will be delivered for accesses to TD-private memory.
+ *
+ * TDX 1.0 does not allow the guest to disable SEPT #VE on its own. The VMM
+ * controls if the guest will receive such #VE with TD attribute
+ * ATTR_SEPT_VE_DISABLE.
+ *
+ * Newer TDX module allows the guest to control if it wants to receive SEPT
+ * violation #VEs.
+ *
+ * Check if the feature is available and disable SEPT #VE if possible.
+ *
+ * If the TD allowed to disable/enable SEPT #VEs, the ATTR_SEPT_VE_DISABLE
+ * attribute is no longer reliable. It reflects the initial state of the
+ * control for the TD, but it will not be updated if someone (e.g. bootloader)
+ * changes it before the kernel starts. Kernel must check TDCS_TD_CTLS bit to
+ * determine if SEPT #VEs are enabled or disabled.
+ */
+static void disable_sept_ve(u64 td_attr)
+{
+	const char *msg = "TD misconfiguration: SEPT #VE has to be disabled";
+	bool debug = td_attr & ATTR_DEBUG;
+	u64 config, controls;
+
+	/* Is this TD allowed to disable SEPT #VE */
+	tdg_vm_rd(TDCS_CONFIG_FLAGS, &config);
+	if (!(config & TDCS_CONFIG_FLEXIBLE_PENDING_VE)) {
+		/* No SEPT #VE controls for the guest: check the attribute */
+		if (td_attr & ATTR_SEPT_VE_DISABLE)
+			return;
+
+		/* Relax SEPT_VE_DISABLE check for debug TD for backtraces */
+		if (debug)
+			pr_warn("%s\n", msg);
+		else
+			tdx_panic(msg);
+		return;
+	}
+
+	/* Check if SEPT #VE has been disabled before us */
+	tdg_vm_rd(TDCS_TD_CTLS, &controls);
+	if (controls & TD_CTLS_PENDING_VE_DISABLE)
+		return;
+
+	/* Keep #VEs enabled for splats in debugging environments */
+	if (debug)
+		return;
+
+	/* Disable SEPT #VEs */
+	tdg_vm_wr(TDCS_TD_CTLS, TD_CTLS_PENDING_VE_DISABLE,
+		  TD_CTLS_PENDING_VE_DISABLE);
+
+	return;
+}
+
 static void tdx_setup(u64 *cc_mask)
 {
 	struct tdx_module_args args = {};
@@ -204,24 +274,12 @@ static void tdx_setup(u64 *cc_mask)
 	gpa_width = args.rcx & GENMASK(5, 0);
 	*cc_mask = BIT_ULL(gpa_width - 1);
 
+	td_attr = args.rdx;
+
 	/* Kernel does not use NOTIFY_ENABLES and does not need random #VEs */
 	tdg_vm_wr(TDCS_NOTIFY_ENABLES, 0, -1ULL);
 
-	/*
-	 * The kernel can not handle #VE's when accessing normal kernel
-	 * memory.  Ensure that no #VE will be delivered for accesses to
-	 * TD-private memory.  Only VMM-shared memory (MMIO) will #VE.
-	 */
-	td_attr = args.rdx;
-	if (!(td_attr & ATTR_SEPT_VE_DISABLE)) {
-		const char *msg = "TD misconfiguration: SEPT_VE_DISABLE attribute must be set.";
-
-		/* Relax SEPT_VE_DISABLE check for debug TD. */
-		if (td_attr & ATTR_DEBUG)
-			pr_warn("%s\n", msg);
-		else
-			tdx_panic(msg);
-	}
+	disable_sept_ve(td_attr);
 }
 
 /*
diff --git a/arch/x86/include/asm/shared/tdx.h b/arch/x86/include/asm/shared/tdx.h
index fdfd41511b02..fecb2a6e864b 100644
--- a/arch/x86/include/asm/shared/tdx.h
+++ b/arch/x86/include/asm/shared/tdx.h
@@ -16,11 +16,20 @@
 #define TDG_VP_VEINFO_GET		3
 #define TDG_MR_REPORT			4
 #define TDG_MEM_PAGE_ACCEPT		6
+#define TDG_VM_RD			7
 #define TDG_VM_WR			8
 
-/* TDCS fields. To be used by TDG.VM.WR and TDG.VM.RD module calls */
+/* TDX TD-Scope Metadata. To be used by TDG.VM.WR and TDG.VM.RD */
+#define TDCS_CONFIG_FLAGS		0x1110000300000016
+#define TDCS_TD_CTLS			0x1110000300000017
 #define TDCS_NOTIFY_ENABLES		0x9100000000000010
 
+/* TDCS_CONFIG_FLAGS bits */
+#define TDCS_CONFIG_FLEXIBLE_PENDING_VE	BIT_ULL(1)
+
+/* TDCS_TD_CTLS bits */
+#define TD_CTLS_PENDING_VE_DISABLE	BIT_ULL(0)
+
 /* TDX hypercall Leaf IDs */
 #define TDVMCALL_MAP_GPA		0x10001
 #define TDVMCALL_GET_QUOTE		0x10002

---

## [5] Kirill A. Shutemov — 2024-05-12
*Subject: [PATCHv4 4/4] x86/tdx: Enable CPU topology enumeration*

TDX 1.0 defines baseline behaviour of TDX guest platform. In TDX 1.0
generates a #VE when accessing topology-related CPUID leafs (0xB and
0x1F) and the X2APIC_APICID MSR. The kernel returns all zeros on CPUID
topology. In practice, this means that the kernel can only boot with a
plain topology. Any complications will cause problems.

The ENUM_TOPOLOGY feature allows the VMM to provide topology
information to the guest. Enabling the feature eliminates
topology-related #VEs: the TDX module virtualizes accesses to
the CPUID leafs and the MSR.

Enable ENUM_TOPOLOGY if it is available.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/coco/tdx/tdx.c           | 27 +++++++++++++++++++++++++++
 arch/x86/include/asm/shared/tdx.h |  2 ++
 2 files changed, 29 insertions(+)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index ba37f4306f4e..53d0b9df5a7f 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -249,6 +249,32 @@ static void disable_sept_ve(u64 td_attr)
 	return;
 }
 
+/*
+ * TDX 1.0 generates a #VE when accessing topology-related CPUID leafs (0xB and
+ * 0x1F) and the X2APIC_APICID MSR. The kernel returns all zeros on CPUID #VEs.
+ * In practice, this means that the kernel can only boot with a plain topology.
+ * Any complications will cause problems.
+ *
+ * The ENUM_TOPOLOGY feature allows the VMM to provide topology information.
+ * Enabling the feature  eliminates topology-related #VEs: the TDX module
+ * virtualizes accesses to the CPUID leafs and the MSR.
+ *
+ * Enable ENUM_TOPOLOGY if it is available.
+ */
+static void enable_cpu_topology_enumeration(void)
+{
+	u64 configured;
+
+	/* Has the VMM provided a valid topology configuration? */
+	tdg_vm_rd(TDCS_TOPOLOGY_ENUM_CONFIGURED, &configured);
+	if (!configured) {
+		pr_err("VMM did not configure X2APIC_IDs properly\n");
+		return;
+	}
+
+	tdg_vm_wr(TDCS_TD_CTLS, TD_CTLS_ENUM_TOPOLOGY, TD_CTLS_ENUM_TOPOLOGY);
+}
+
 static void tdx_setup(u64 *cc_mask)
 {
 	struct tdx_module_args args = {};
@@ -280,6 +306,7 @@ static void tdx_setup(u64 *cc_mask)
 	tdg_vm_wr(TDCS_NOTIFY_ENABLES, 0, -1ULL);
 
 	disable_sept_ve(td_attr);
+	enable_cpu_topology_enumeration();
 }
 
 /*
diff --git a/arch/x86/include/asm/shared/tdx.h b/arch/x86/include/asm/shared/tdx.h
index fecb2a6e864b..89f7fcade8ae 100644
--- a/arch/x86/include/asm/shared/tdx.h
+++ b/arch/x86/include/asm/shared/tdx.h
@@ -23,12 +23,14 @@
 #define TDCS_CONFIG_FLAGS		0x1110000300000016
 #define TDCS_TD_CTLS			0x1110000300000017
 #define TDCS_NOTIFY_ENABLES		0x9100000000000010
+#define TDCS_TOPOLOGY_ENUM_CONFIGURED	0x9100000000000019
 
 /* TDCS_CONFIG_FLAGS bits */
 #define TDCS_CONFIG_FLEXIBLE_PENDING_VE	BIT_ULL(1)
 
 /* TDCS_TD_CTLS bits */
 #define TD_CTLS_PENDING_VE_DISABLE	BIT_ULL(0)
+#define TD_CTLS_ENUM_TOPOLOGY		BIT_ULL(1)
 
 /* TDX hypercall Leaf IDs */
 #define TDVMCALL_MAP_GPA		0x10001

---

## [6] Nikolay Borisov — 2024-05-14
*Subject: Re: [PATCHv4 3/4] x86/tdx: Dynamically disable SEPT violations from
 causing #VEs*

On 12.05.24 г. 15:21 ч., Kirill A. Shutemov wrote:
> Memory access #VE's are hard for Linux to handle in contexts like the
> entry code or NMIs.  But other OSes need them for functionality.

Reviewed-by: Nikolay Borisov <nik.borisov@suse.com> though one nit below.

> ---
>   arch/x86/coco/tdx/tdx.c           | 88 +++++++++++++++++++++++++------

nit: Perhaps this function can be put in the first patch and the 
description there be made more generic, something along the lines of 
"introduce functions for tdg_rd/tdg_wr" ?

> +
>   /* Write TD-scoped metadata */

---

## [7] Kirill A. Shutemov — 2024-05-15
*Subject: Re: [PATCHv4 3/4] x86/tdx: Dynamically disable SEPT violations from
 causing #VEs*

On Tue, May 14, 2024 at 05:56:21PM +0300, Nikolay Borisov wrote:
> > diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
> > index 1ff571cb9177..ba37f4306f4e 100644

A static function without an user will generate a build warning. I don't
think it is good idea.

---

## [8] Nikolay Borisov — 2024-05-15
*Subject: Re: [PATCHv4 3/4] x86/tdx: Dynamically disable SEPT violations from
 causing #VEs*

On 15.05.24 г. 12:30 ч., Kirill A. Shutemov wrote:
> On Tue, May 14, 2024 at 05:56:21PM +0300, Nikolay Borisov wrote:
>>> diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c

But are those 2 wrappers really static-worthy? Those two interfaces seem 
to be rather generic and could be used by more things in the future? 
OTOH when the time comes they can be exposed as needed.

Anyway that could be considered a minor thing.

---

## [9] Kirill A. Shutemov — 2024-05-15
*Subject: Re: [PATCHv4 3/4] x86/tdx: Dynamically disable SEPT violations from
 causing #VEs*

On Wed, May 15, 2024 at 04:14:18PM +0300, Nikolay Borisov wrote:
> 
> 

Generally, functions have to static unless they used outside of the
translation unit.

---

## [10] Dave Hansen — 2024-05-15
*Subject: Re: [PATCHv4 3/4] x86/tdx: Dynamically disable SEPT violations from
 causing #VEs*

On 5/15/24 02:30, Kirill A. Shutemov wrote:
>> nit: Perhaps this function can be put in the first patch and the description
>> there be made more generic, something along the lines of "introduce

OK, so stick a __maybe_unused on it when you define it and remove it on
first use.

---
