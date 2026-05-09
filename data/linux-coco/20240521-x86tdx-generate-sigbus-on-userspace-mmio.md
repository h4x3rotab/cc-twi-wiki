---
title: 'x86/tdx: Generate SIGBUS on userspace MMIO'
date: 2024-05-21
last_reply: 2024-05-23
message_count: 4
participants: ['Kirill A. Shutemov', 'Kuppuswamy Sathyanarayanan', 'Chris Oo']
---

## [1] Kirill A. Shutemov — 2024-05-21

Currently attempt to do MMIO from userspace in TDX guest leads to
warning about unexpect #VE and SIGSEGV being delivered to the process.

Enlightened userspace might choose to deal with MMIO on their own if
kernel doesn't emulate it.

Handle EPT_VIOLATION exit reason for userspace and deliver SIGBUS
instead of SIGSEV. SIGBUS is more appropriate for MMIO situation.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/coco/tdx/tdx.c | 19 ++++++++++++++-----
 1 file changed, 14 insertions(+), 5 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index c1cb90369915..d2aa93cebf5a 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -7,6 +7,7 @@
 #include <linux/cpufeature.h>
 #include <linux/export.h>
 #include <linux/io.h>
+#include <linux/sched/signal.h>
 #include <asm/coco.h>
 #include <asm/tdx.h>
 #include <asm/vmx.h>
@@ -630,6 +631,11 @@ void tdx_get_ve_info(struct ve_info *ve)
 	ve->instr_info  = upper_32_bits(args.r10);
 }
 
+static inline bool is_private_gpa(u64 gpa)
+{
+	return gpa == cc_mkenc(gpa);
+}
+
 /*
  * Handle the user initiated #VE.
  *
@@ -641,17 +647,20 @@ static int virt_exception_user(struct pt_regs *regs, struct ve_info *ve)
 	switch (ve->exit_reason) {
 	case EXIT_REASON_CPUID:
 		return handle_cpuid(regs, ve);
+	case EXIT_REASON_EPT_VIOLATION:
+		if (is_private_gpa(ve->gpa))
+			panic("Unexpected EPT-violation on private memory.");
+
+		force_sig_fault(SIGBUS, BUS_ADRERR, (void __user *)ve->gla);
+
+		/* Return 0 to avoid incrementing RIP */
+		return 0;
 	default:
 		pr_warn("Unexpected #VE: %lld\n", ve->exit_reason);
 		return -EIO;
 	}
 }
 
-static inline bool is_private_gpa(u64 gpa)
-{
-	return gpa == cc_mkenc(gpa);
-}
-
 /*
  * Handle the kernel #VE.
  *

---

## [2] Kuppuswamy Sathyanarayanan — 2024-05-21
*Subject: Re: [PATCH] x86/tdx: Generate SIGBUS on userspace MMIO*

On 5/21/24 12:35 AM, Kirill A. Shutemov wrote:
> Currently attempt to do MMIO from userspace in TDX guest leads to
> warning about unexpect #VE and SIGSEGV being delivered to the process.

Any specific use cases ? Like who is using it?

> Handle EPT_VIOLATION exit reason for userspace and deliver SIGBUS
> instead of SIGSEV. SIGBUS is more appropriate for MMIO situation.

Code looks good to me.

Reviewed-by: Kuppuswamy Sathyanarayanan <sathyanarayanan.kuppuswamy@linux.intel.com>

>  arch/x86/coco/tdx/tdx.c | 19 ++++++++++++++-----
>  1 file changed, 14 insertions(+), 5 deletions(-)

---

## [3] Kirill A. Shutemov — 2024-05-23
*Subject: Re: [PATCH] x86/tdx: Generate SIGBUS on userspace MMIO*

On Tue, May 21, 2024 at 06:35:49AM -0700, Kuppuswamy Sathyanarayanan wrote:
> 
> On 5/21/24 12:35 AM, Kirill A. Shutemov wrote:

Microsoft folks wanted it. Chris, Dexuan, John, any comments?

But it is generally right thing to do. SIGBUS is right signal to deliver.

---

## [4] Chris Oo — 2024-05-23
*Subject: RE: [EXTERNAL] Re: [PATCH] x86/tdx: Generate SIGBUS on userspace MMIO*

We use this to handle MMIO issued by userspace that the kernel does not handle in a #VE, for devices assigned to a TDX VM. 

Chris

-----Original Message-----
From: Kirill A. Shutemov <kirill.shutemov@linux.intel.com> 
Sent: Thursday, May 23, 2024 3:15 AM
To: Kuppuswamy Sathyanarayanan <sathyanarayanan.kuppuswamy@linux.intel.com>
Cc: Dave Hansen <dave.hansen@linux.intel.com>; Thomas Gleixner <tglx@linutronix.de>; Ingo Molnar <mingo@redhat.com>; Borislav Petkov <bp@alien8.de>; x86@kernel.org; H. Peter Anvin <hpa@zytor.com>; linux-coco@lists.linux.dev; linux-kernel@vger.kernel.org; Chris Oo <cho@microsoft.com>; Dexuan Cui <decui@microsoft.com>; John Starks <John.Starks@microsoft.com>
Subject: [EXTERNAL] Re: [PATCH] x86/tdx: Generate SIGBUS on userspace MMIO

On Tue, May 21, 2024 at 06:35:49AM -0700, Kuppuswamy Sathyanarayanan wrote:
> 
> On 5/21/24 12:35 AM, Kirill A. Shutemov wrote:

Microsoft folks wanted it. Chris, Dexuan, John, any comments?

But it is generally right thing to do. SIGBUS is right signal to deliver.

--
  Kiryl Shutsemau / Kirill A. Shutemov

---
