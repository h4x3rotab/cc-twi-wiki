---
title: '[V2 PATCH 0/1][Bug Report] and Fix TDX cpuid0x2 #VE causing segment'
date: 2025-04-29
last_reply: 2025-04-30
message_count: 11
participants: ['Jun Miao', 'Dave Hansen', 'Zhiquan Li', 'Kirill A. Shutemov']
---

## [1] Jun Miao — 2025-04-29

Hi

[TDX Bug Report]

There is a segfault, when boot a upstream kernel as a TDX guest.
- Boot log:
[   46.902055] systemd[1]: segfault at 55c974b82650 ip 00007f252eef09c2 sp 00007ffcd94fe7b8 error 4 in libc.so.6[7f252ee28000+175000] likely on CPU 1 (core 1, socket 0)
[   46.903302] Code: 00 0f 18 8e 00 31 00 00 0f 18 8e 40 31 00 00 0f 18 8e 80 31 00 00 0f 18 8e c0 31 00 00 62 e1 fe 48 6f 06 62 e1 fe 48 6f 4e 01 <62> e1 fe 48 6f 66 40 62 e1 fe 48 6f 6e 41 62 61 fe 48 6f 86 00 20
[   46.905516] systemd[1]: Caught <SEGV> from PID 1958225488.
[   46.921256] systemd[1]: Caught <SEGV>, dumped core as pid 346.
[   46.922056] systemd[1]: Freezing execution.

- Guest kernel version:
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
Since the enable_cpu_topology_enumeration() doesn't very little and can be integrated into reduce_unnecessary_ve().
v1-->v2:
1. checkpatch.pl the patch and adjusted code formatting.
2. modify code logic:  when configured is ok but REDUCE_VE=false enable
   ENUM_TOPOLOGY and VIRT_CPUID

***  ***

Zhiquan Li (1):
  x86/tdx: add VIRT_CPUID2 virtualization if REDUCE_VE was not
    successful
 arch/x86/coco/tdx/tdx.c | 52 +++++++++++++++++++++++++++--------------
 1 file changed, 34 insertions(+), 18 deletions(-)

---

## [2] Jun Miao — 2025-04-29
*Subject: [V2 PATCH] x86/tdx: add VIRT_CPUID2 virtualization if REDUCE_VE was not successful*

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
Signed-off-by: Jun Miao <jun.miao@intel.com>
Signed-off-by: Zhiquan Li <zhiquan1.li@intel.com>
---
 arch/x86/coco/tdx/tdx.c | 52 +++++++++++++++++++++++++++--------------
 1 file changed, 34 insertions(+), 18 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index edab6d6049be..94062dbf57fd 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -247,43 +247,59 @@ static void disable_sept_ve(u64 td_attr)
 }
 
 /*
+ * Newer TDX modules provide a "REDUCE_VE" feature.  When enabled, it
+ * drastically cuts cases when guests receive #VE on MSR and CPUID accesses,
+ * and TDX module also forces ENUM_TOPOLOGY and VIRT_CPUID to enabled.
+ *
+ * But REDUCE_VE can only be enabled if x2APIC_ID has been properly configured
+ * with unique values for each VCPU. So check if VMM has provided a valid
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
+ * returns all zeros. It is quite useful for backward compatibility.
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
-
-	tdg_vm_wr(TDCS_TD_CTLS, TD_CTLS_ENUM_TOPOLOGY, TD_CTLS_ENUM_TOPOLOGY);
-}
 
-static void reduce_unnecessary_ve(void)
-{
-	u64 err = tdg_vm_wr(TDCS_TD_CTLS, TD_CTLS_REDUCE_VE, TD_CTLS_REDUCE_VE);
+	if (configured) {
+		err = tdg_vm_wr(TDCS_TD_CTLS, TD_CTLS_REDUCE_VE, TD_CTLS_REDUCE_VE);
 
-	if (err == TDX_SUCCESS)
-		return;
+		/*
+		 * Enabling REDUCE_VE includes ENUM_TOPOLOGY. Only try to
+		 * enable ENUM_TOPOLOGY if REDUCE_VE was not successful.
+		 */
+		if (err != TDX_SUCCESS)
+			tdg_vm_wr(TDCS_TD_CTLS, TD_CTLS_ENUM_TOPOLOGY, TD_CTLS_ENUM_TOPOLOGY);
+	} else
+		pr_err("VMM did not configure X2APIC_IDs properly\n");
 
 	/*
-	 * Enabling REDUCE_VE includes ENUM_TOPOLOGY. Only try to
-	 * enable ENUM_TOPOLOGY if REDUCE_VE was not successful.
+	 * Enabling REDUCE_VE includes VIRT_CPUID2. Only try to enable
+	 * VIRT_CPUID2 if REDUCE_VE was not successful.
 	 */
-	enable_cpu_topology_enumeration();
+	if (!configured || err != TDX_SUCCESS)
+		tdg_vm_wr(TDCS_TD_CTLS, TD_CTLS_VIRT_CPUID2, TD_CTLS_VIRT_CPUID2);
+
 }
 
 static void tdx_setup(u64 *cc_mask)

---

## [3] Dave Hansen — 2025-04-29
*Subject: Re: [V2 PATCH] x86/tdx: add VIRT_CPUID2 virtualization if REDUCE_VE
 was not successful*

On 4/29/25 07:31, Jun Miao wrote:
> REDUCE_VE can only be enabled if x2APIC_ID has been properly configured
> with unique values for each VCPU.  Check if VMM has provided an activated

Isn't this just working around VMM bugs? Shouldn't we just panic as
quickly as possible so the VMM config gets fixed rather than adding kludges?

---

## [4] Zhiquan Li — 2025-04-30
*Subject: Re: [V2 PATCH] x86/tdx: add VIRT_CPUID2 virtualization if REDUCE_VE
 was not successful*

On 2025/4/29 22:50, Dave Hansen wrote:
> On 4/29/25 07:31, Jun Miao wrote:
>> REDUCE_VE can only be enabled if x2APIC_ID has been properly configured


Now failed to virtualize these two cases will cause TD VM regression vs
legacy VM.  Do you mean the panic will just for the #VE caused by CPUID
leaf 0x2? Or both (+ VMM not configure topology) will panic?

Currently the most customer's complaints come from the CPUID leaf 0x2
not virtualization, and most of access come from user space.  Is it
appropriate for such behavior directly cause a guest kernel panic?

Thanks,
Zhiquan

---

## [5] Kirill A. Shutemov — 2025-04-30
*Subject: Re: [V2 PATCH] x86/tdx: add VIRT_CPUID2 virtualization if REDUCE_VE
 was not successful*

On Wed, Apr 30, 2025 at 10:15:05AM +0800, Zhiquan Li wrote:
> 
> On 2025/4/29 22:50, Dave Hansen wrote:

The appropriate behavior would be to fix VMM to configure APIC IDs
correctly and use TDX module that supports REDUCE_VE.

---

## [6] Miao, Jun — 2025-04-30
*Subject: RE: [V2 PATCH] x86/tdx: add VIRT_CPUID2 virtualization if REDUCE_VE
 was not successful*

>
>On Wed, Apr 30, 2025 at 10:15:05AM +0800, Zhiquan Li wrote:

Yes, I completely agree with your point to fix VMM APIC IDs.
The idea here is only to avoid this panic by using the guest component even when the host is incomplete.
And thereby improving the robustness of the kernel code. Moreover, even if the VMM becomes complete later, the adjusted logic will continue to adapt still. (^v^) 

--- Jun Miao
>--
>  Kiryl Shutsemau / Kirill A. Shutemov

---

## [7] Dave Hansen — 2025-04-30
*Subject: Re: [V2 PATCH] x86/tdx: add VIRT_CPUID2 virtualization if REDUCE_VE
 was not successful*

On 4/29/25 19:15, Zhiquan Li wrote:
> On 2025/4/29 22:50, Dave Hansen wrote:
>> On 4/29/25 07:31, Jun Miao wrote:

I'm not really parsing this response. I don't understand what you are
asking.

> Currently the most customer's complaints come from the CPUID leaf 0x2
> not virtualization, and most of access come from user space.  Is it

If a VMM doesn't properly configure topology properly and allows
REDUCE_VE, then panic. They obviously got something wrong because that
configuration doesn't make any sense.

---

## [8] Kirill A. Shutemov — 2025-04-30
*Subject: Re: [V2 PATCH] x86/tdx: add VIRT_CPUID2 virtualization if REDUCE_VE
 was not successful*

On Wed, Apr 30, 2025 at 11:10:32AM +0000, Miao, Jun wrote:
> >
> >On Wed, Apr 30, 2025 at 10:15:05AM +0800, Zhiquan Li wrote:

VIRT_CPUID2 was introduced as stop gap until REDUCE_VE is landed. I don't
see a point in getting it enabled at this stage. REDUCE_VE covers much
more broken corner cases. CPUID 0x2 is just the most prominent one because
of glibc bug.

---

## [9] Miao, Jun — 2025-04-30
*Subject: RE: [V2 PATCH] x86/tdx: add VIRT_CPUID2 virtualization if REDUCE_VE
 was not successful*

>
>On Wed, Apr 30, 2025 at 11:10:32AM +0000, Miao, Jun wrote:
Hmm, at this stage, I may indeed be a pressing urgency to resolve this glibc issues in 
real applications from the user's perspective such as [Bug Report with Redhat/Rocky9.2 qcow].
The goal is to leverage existing resources(VIRT_CPUID2) to resolve this panic, and we're hoping 
for the VMM side to prioritize implementing the ability to set x2APIC IDs for each TD vCPU.
Thank you for your patient explanation again.

---Jun Miao

>--
>  Kiryl Shutsemau / Kirill A. Shutemov

---

## [10] Dave Hansen — 2025-04-30
*Subject: Re: [V2 PATCH] x86/tdx: add VIRT_CPUID2 virtualization if REDUCE_VE
 was not successful*

On 4/30/25 08:09, Zhiquan Li wrote:
> On 2025/4/30 21:44, Dave Hansen wrote:
>>> Currently the most customer's complaints come from the CPUID leaf 0x2

Either that or fix the TDX module in some way to untangle the mess.

---

## [11] Zhiquan Li — 2025-04-30
*Subject: Re: [V2 PATCH] x86/tdx: add VIRT_CPUID2 virtualization if REDUCE_VE
 was not successful*

On 2025/4/30 21:44, Dave Hansen wrote:
>> Currently the most customer's complaints come from the CPUID leaf 0x2
>> not virtualization, and most of access come from user space.  Is it

OK, I agree with you.  Is it better to simplify the logic like this:

    static void reduce_unnecessary_ve(void)
    {
        u64 configured;

        /* Has the VMM provided a valid topology configuration? */
        tdg_vm_rd(TDCS_TOPOLOGY_ENUM_CONFIGURED, &configured);

        if (!configured)
            panic("VMM did not configure X2APIC_IDs properly\n");

        tdg_vm_wr(TDCS_TD_CTLS, TD_CTLS_REDUCE_VE, TD_CTLS_REDUCE_VE);
    }

Since merely fall back to enable ENUM_TOPOLOGY isn't enough, the guest
still suffering the CPUID leaf 0x2 not virtualization regression, like
the glibc bug.  Full REDUCE_VE is really expected.

Best Regards,
Zhiquan

---
