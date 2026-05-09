---
title: '[Bug Report] and fix TDX cpuid0x2 #VE causing segfault'
date: 2025-04-29
last_reply: 2025-04-29
message_count: 2
participants: ['Jun Miao']
---

## [1] Jun Miao — 2025-04-29

Hi

[TDX Bug Report]

There is a segfault, when boot a upstream kernel as TDX guest.
- Boot log:
[   46.902055] systemd[1]: segfault at 55c974b82650 ip 00007f252eef09c2 sp 00007ffcd94fe7b8 error 4 in libc.so.6[7f252ee28000+175000] likely on CPU 1 (core 1, socket 0)
[   46.903302] Code: 00 0f 18 8e 00 31 00 00 0f 18 8e 40 31 00 00 0f 18 8e 80 31 00 00 0f 18 8e c0 31 00 00 62 e1 fe 48 6f 06 62 e1 fe 48 6f 4e 01 <62> e1 fe 48 6f 66 40 62 e1 fe 48 6f 6e 41 62 61 fe 48 6f 86 00 20
[   46.905516] systemd[1]: Caught <SEGV> from PID 1958225488.
[   46.921256] systemd[1]: Caught <SEGV>, dumped core as pid 346.
[   46.922056] systemd[1]: Freezing execution.

- Gest kernel version:
  Linux version 6.15.0-rc4
- Guest qcow2:
  rhel-guest-image-9.2-20230414.17.x86_64.qcow2
- TDX module info:
  TDX module: 1.5.16.00.0869 (build_date 20250219, Production module), TDX_FEATURES0 0x226f3f0fbf
  TDX_FEATURES0.VE_REDUCTION (bit 30) = 1
  TDX_FEATURES0.CPUID2_VIRT (bit 29) = 1

The root cases:
Glibc 2.34 and newer segfault if CPUID leaf 0x2 reports zero.
https://sourceware.org/bugzilla/show_bug.cgi?id=30037
That is #VE on CPUID leaf 0x2 is handled by returning all-0 to the code which executed CPUID.
In many cases, an all-0 value is not the correct value, and may cause improper operation.
Although, the bits of VE_REDUCETION and VIRT_CPUID2 are marked "1" as supported in TDX FEATURES0, their functionality fails during runtime stress tests.


[Solution]

Add VIRT_CPUID2 virtualization if REDUCE_VE was not successful to avoiding the segfault when glibc invoked the CPUID leaf 0x2.
Since the enable_cpu_topology_enumeration() was very little and can be integrated into reduce_unnecessary_ve().

[PATCH 1/1] x86/tdx: add VIRT_CPUID2 virtualization if REDUCE_VE was not successful

***  ***

Zhiquan Li (1):
  x86/tdx: add VIRT_CPUID2 virtualization if REDUCE_VE was not
    successful

 arch/x86/coco/tdx/tdx.c | 56 +++++++++++++++++++++++++----------------
 1 file changed, 35 insertions(+), 21 deletions(-)

---

## [2] Jun Miao — 2025-04-29
*Subject: [PATCH 1/1] x86/tdx: add VIRT_CPUID2 virtualization if REDUCE_VE was not successful*

From: Zhiquan Li <zhiquan1.li@intel.com>

The ENUM_TOPOLOGY and VIRT_CPUID2 virtualization control are the subset
of the REDUCE_VE control, TD enabling REDUCE_VE will also implicitly
enable ENUM_TOPOLOGY and VIRT_CPUID2.  Both features were introduced
earlier than REDUCE_VE.  Now if enabling REDUCE_VE is failed
will fall back to enabling ENUM_TOPOLOGY, the same reason is applicable
for VIRT_CPUID2.

The VIRT_CPUID2 feature allows TDX module provides fixed values
eax=0x00feff01, ebx=0, ecx=0 and edx=0, meaning "cache data is returned
by CPUID leaf 0x4" and "TLB data is returned by CPUID leaf 0x18" while
TD guest execution of CPUID leaf 0x2, instead the kernel CPUID #VE
handler returns all zeros.  It is quite useful for backward
compatibility.

REDUCE_VE can only be enabled if x2APIC_ID has been properly configured
with unique values for each VCPU.  Check if VMM has provided an activated
topology configuration first as it is the prerequisite of REDUCE_VE and
ENUM_TOPOLOGY, so move it to reduce_unnecessary_ve().  The function
enable_cpu_topology_enumeration() was very little and can be
integrated into reduce_unnecessary_ve().

Only try to enable VIRT_CPUID2 when REDUCE_VE was not successful and the
depended x2APIC_ID didn't set to each TD vCPU.

Fixes: cd9ce8217345 ("x86/tdx: Disable unnecessary virtualization exceptions")
Co-developed-by: Jun Miao <jun.miao@intel.com>
Signed-off-by: Zhiquan Li <zhiquan1.li@intel.com>
---
 arch/x86/coco/tdx/tdx.c | 56 +++++++++++++++++++++++++----------------
 1 file changed, 35 insertions(+), 21 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index edab6d6049be..be1469886501 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -247,43 +247,57 @@ static void disable_sept_ve(u64 td_attr)
 }
 
 /*
+ * Newer TDX modules provide a "REDUCE_VE" feature.  When enabled, it
+ * drastically cuts cases when guests receive #VE on MSR and CPUID accesses,
+ * and TDX module also forces ENUM_TOPOLOGY and VIRT_CPUID to enabled.
+ *
+ * But REDUCE_VE can only be enabled if x2APIC_ID has been properly configured
+ * with unique values for each VCPU.  So check if VMM has provided a valid
+ * topology configuration first.
+ *
  * TDX 1.0 generates a #VE when accessing topology-related CPUID leafs (0xB and
  * 0x1F) and the X2APIC_APICID MSR. The kernel returns all zeros on CPUID #VEs.
  * In practice, this means that the kernel can only boot with a plain topology.
  * Any complications will cause problems.
  *
  * The ENUM_TOPOLOGY feature allows the VMM to provide topology information.
- * Enabling the feature  eliminates topology-related #VEs: the TDX module
+ * Enabling the feature eliminates topology-related #VEs: the TDX module
  * virtualizes accesses to the CPUID leafs and the MSR.
  *
- * Enable ENUM_TOPOLOGY if it is available.
+ * The VIRT_CPUID2 feature allows TDX module provides fixed values
+ * eax=0x00feff01, ebx=0, ecx=0 and edx=0, meaning "cache data is returned by
+ * CPUID leaf 0x4" and "TLB data is returned by CPUID leaf 0x18" while TD
+ * guest execution of CPUID leaf 0x2, instead the kernel CPUID #VE handler
+ * returns all zeros.  It is quite useful for backward compatibility.
+ *
+ * Both ENUM_TOPOLOGY and VIRT_CPUID2 are earlier than REDUCE_VE, fall back to
+ * enable them if REDUCE_VE was not successful.
  */
-static void enable_cpu_topology_enumeration(void)
+static void reduce_unnecessary_ve(void)
 {
+	u64 err = TDX_SUCCESS;
 	u64 configured;
 
 	/* Has the VMM provided a valid topology configuration? */
 	tdg_vm_rd(TDCS_TOPOLOGY_ENUM_CONFIGURED, &configured);
-	if (!configured) {
-		pr_err("VMM did not configure X2APIC_IDs properly\n");
-		return;
-	}
 
-	tdg_vm_wr(TDCS_TD_CTLS, TD_CTLS_ENUM_TOPOLOGY, TD_CTLS_ENUM_TOPOLOGY);
+	if (configured) {
+		err = tdg_vm_wr(TDCS_TD_CTLS, TD_CTLS_REDUCE_VE, TD_CTLS_REDUCE_VE);
+		if (err != TDX_SUCCESS)
+			/*
+			 * Enabling REDUCE_VE includes ENUM_TOPOLOGY. Only try to
+			 * enable ENUM_TOPOLOGY if REDUCE_VE was not successful.
+			 */
+			tdg_vm_wr(TDCS_TD_CTLS, TD_CTLS_ENUM_TOPOLOGY,TD_CTLS_ENUM_TOPOLOGY);
+	} else{
+		pr_err("VMM did not configure X2APIC_IDs properly\n");
+			/*
+			* Enabling REDUCE_VE includes VIRT_CPUID2. Only try to enable
+			* VIRT_CPUID2 if REDUCE_VE was not successful.
+			*/
+		if (!configured || err != TDX_SUCCESS)
+			tdg_vm_wr(TDCS_TD_CTLS, TD_CTLS_VIRT_CPUID2, TD_CTLS_VIRT_CPUID2);
 }
-
-static void reduce_unnecessary_ve(void)
-{
-	u64 err = tdg_vm_wr(TDCS_TD_CTLS, TD_CTLS_REDUCE_VE, TD_CTLS_REDUCE_VE);
-
-	if (err == TDX_SUCCESS)
-		return;
-
-	/*
-	 * Enabling REDUCE_VE includes ENUM_TOPOLOGY. Only try to
-	 * enable ENUM_TOPOLOGY if REDUCE_VE was not successful.
-	 */
-	enable_cpu_topology_enumeration();
 }
 
 static void tdx_setup(u64 *cc_mask)

---
