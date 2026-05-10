---
title: 'Support userspace hypercalls for TDX'
date: 2024-07-03
last_reply: 2024-07-23
message_count: 11
participants: ['Tim Merrifield', 'Dave Hansen', 'Peter Zijlstra', 'Kirill A . Shutemov']
---

## [1] Tim Merrifield — 2024-07-03

VMCALL and VMMCALL instructions are used by x86 guests to request services
from the host VMM. Both VMCALL and VMMCALL are not restricted to CPL 0.
This allows userspace software like open-vm-tools to communicate directly
with the VMM.

In the context of confidential VMs, direct communication with the host may
violate the security model. Existing binaries that make use of hypercalls
and are not hardened against malicious hypervisors can become a possible
attack surface. For this reason, user-level VMCALLs are not currently
forwarded to the host on TDX VMs. This breaks any user-level software that
use these instructions.

But if user-level software is aware of the risks and has been hardened to
address any known violations of the security model, then it seems
reasonable to allow hypercalls from this process to proceed.

This patchset introduces a new x86 process control flag to address this
concern. By setting the TIF_COCO_USER_HCALL thread information flag, the
process opts in to user-level hypercalls. When TDX is enabled, the VMCALL
will #VE and control will be transferred to a hypervisor-specific
hypercall handler (similar to how things work today for SEV with
sev_es_hcall_prepare/sev_es_hcall_finish). The flag has no effect on
non-TDX VMs. Other confidential computing technologies could use this flag
to provide limited access to user-level hypercalls.

Tim Merrifield (2):
  x86/tdx: Add prctl to allow userlevel TDX hypercalls
  x86/vmware: VMware support for TDX userspace hypercalls

 arch/x86/coco/tdx/tdx.c            | 18 +++++++++++
 arch/x86/include/asm/thread_info.h |  2 ++
 arch/x86/include/asm/x86_init.h    |  1 +
 arch/x86/include/uapi/asm/prctl.h  |  3 ++
 arch/x86/kernel/cpu/vmware.c       | 51 +++++++++++++++++++++++-------
 arch/x86/kernel/process.c          | 20 ++++++++++++
 6 files changed, 84 insertions(+), 11 deletions(-)

---

## [2] Tim Merrifield — 2024-07-03
*Subject: [PATCH 1/2] x86/tdx: Add prctl to allow userlevel TDX hypercalls*

Add a new prctl option to enable/disable user-level hypercalls when
running in a confidential VM. Add support for checking this flag on
VMCALL #VE for TDX and transfer control to a hypervisor
vendor-specific handler.

Signed-off-by: Tim Merrifield <tim.merrifield@broadcom.com>
---
 arch/x86/coco/tdx/tdx.c            | 18 ++++++++++++++++++
 arch/x86/include/asm/thread_info.h |  2 ++
 arch/x86/include/asm/x86_init.h    |  1 +
 arch/x86/include/uapi/asm/prctl.h  |  3 +++
 arch/x86/kernel/process.c          | 20 ++++++++++++++++++++
 5 files changed, 44 insertions(+)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index ef8ec2425998..23111e4c1f91 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -239,6 +239,7 @@ static int ve_instr_len(struct ve_info *ve)
 	case EXIT_REASON_MSR_WRITE:
 	case EXIT_REASON_CPUID:
 	case EXIT_REASON_IO_INSTRUCTION:
+	case EXIT_REASON_VMCALL:
 		/* It is safe to use ve->instr_len for #VE due instructions */
 		return ve->instr_len;
 	case EXIT_REASON_EPT_VIOLATION:
@@ -635,6 +636,21 @@ void tdx_get_ve_info(struct ve_info *ve)
 	ve->instr_info  = upper_32_bits(args.r10);
 }
 
+/*
+ * Handle user-initiated, hypervisor-specific VMCALLs.
+ */
+static int handle_user_vmcall(struct pt_regs *regs, struct ve_info *ve)
+{
+	if (x86_platform.hyper.tdx_hcall &&
+	    test_thread_flag(TIF_COCO_USER_HCALL)) {
+		if (!x86_platform.hyper.tdx_hcall(regs))
+			return -EIO;
+		return ve_instr_len(ve);
+	} else {
+		return -EOPNOTSUPP;
+	}
+}
+
 /*
  * Handle the user initiated #VE.
  *
@@ -646,6 +662,8 @@ static int virt_exception_user(struct pt_regs *regs, struct ve_info *ve)
 	switch (ve->exit_reason) {
 	case EXIT_REASON_CPUID:
 		return handle_cpuid(regs, ve);
+	case EXIT_REASON_VMCALL:
+		return handle_user_vmcall(regs, ve);
 	default:
 		pr_warn("Unexpected #VE: %lld\n", ve->exit_reason);
 		return -EIO;
diff --git a/arch/x86/include/asm/thread_info.h b/arch/x86/include/asm/thread_info.h
index 12da7dfd5ef1..9f69a26a5e68 100644
--- a/arch/x86/include/asm/thread_info.h
+++ b/arch/x86/include/asm/thread_info.h
@@ -106,6 +106,7 @@ struct thread_info {
 #define TIF_BLOCKSTEP		25	/* set when we want DEBUGCTLMSR_BTF */
 #define TIF_LAZY_MMU_UPDATES	27	/* task is updating the mmu lazily */
 #define TIF_ADDR32		29	/* 32-bit address space on 64 bits */
+#define TIF_COCO_USER_HCALL     30      /* Userland hypercalls allowed in CoCo */
 
 #define _TIF_NOTIFY_RESUME	(1 << TIF_NOTIFY_RESUME)
 #define _TIF_SIGPENDING		(1 << TIF_SIGPENDING)
@@ -128,6 +129,7 @@ struct thread_info {
 #define _TIF_BLOCKSTEP		(1 << TIF_BLOCKSTEP)
 #define _TIF_LAZY_MMU_UPDATES	(1 << TIF_LAZY_MMU_UPDATES)
 #define _TIF_ADDR32		(1 << TIF_ADDR32)
+#define _TIF_COCO_USER_HCALL    (1 << TIF_COCO_USER_HCALL)
 
 /* flags to check in __switch_to() */
 #define _TIF_WORK_CTXSW_BASE					\
diff --git a/arch/x86/include/asm/x86_init.h b/arch/x86/include/asm/x86_init.h
index 213cf5379a5a..52975bedd33e 100644
--- a/arch/x86/include/asm/x86_init.h
+++ b/arch/x86/include/asm/x86_init.h
@@ -282,6 +282,7 @@ struct x86_hyper_runtime {
 	void (*sev_es_hcall_prepare)(struct ghcb *ghcb, struct pt_regs *regs);
 	bool (*sev_es_hcall_finish)(struct ghcb *ghcb, struct pt_regs *regs);
 	bool (*is_private_mmio)(u64 addr);
+	bool (*tdx_hcall)(struct pt_regs *regs);
 };
 
 /**
diff --git a/arch/x86/include/uapi/asm/prctl.h b/arch/x86/include/uapi/asm/prctl.h
index 384e2cc6ac19..7fa289a1815b 100644
--- a/arch/x86/include/uapi/asm/prctl.h
+++ b/arch/x86/include/uapi/asm/prctl.h
@@ -16,6 +16,9 @@
 #define ARCH_GET_XCOMP_GUEST_PERM	0x1024
 #define ARCH_REQ_XCOMP_GUEST_PERM	0x1025
 
+#define ARCH_GET_COCO_USER_HCALL        0x1030
+#define ARCH_SET_COCO_USER_HCALL        0x1031
+
 #define ARCH_XCOMP_TILECFG		17
 #define ARCH_XCOMP_TILEDATA		18
 
diff --git a/arch/x86/kernel/process.c b/arch/x86/kernel/process.c
index 1b3d417cd6c4..16f8ab6cde2e 100644
--- a/arch/x86/kernel/process.c
+++ b/arch/x86/kernel/process.c
@@ -1039,6 +1039,21 @@ unsigned long __get_wchan(struct task_struct *p)
 	return addr;
 }
 
+static int get_coco_user_hcall_mode(void)
+{
+	return !test_thread_flag(TIF_COCO_USER_HCALL);
+}
+
+static int set_coco_user_hcall_mode(unsigned long enabled)
+{
+	if (enabled)
+		set_thread_flag(TIF_COCO_USER_HCALL);
+	else
+		clear_thread_flag(TIF_COCO_USER_HCALL);
+
+	return 0;
+}
+
 long do_arch_prctl_common(int option, unsigned long arg2)
 {
 	switch (option) {
@@ -1052,6 +1067,11 @@ long do_arch_prctl_common(int option, unsigned long arg2)
 	case ARCH_GET_XCOMP_GUEST_PERM:
 	case ARCH_REQ_XCOMP_GUEST_PERM:
 		return fpu_xstate_prctl(option, arg2);
+	case ARCH_GET_COCO_USER_HCALL:
+		return get_coco_user_hcall_mode();
+	case ARCH_SET_COCO_USER_HCALL:
+		return set_coco_user_hcall_mode(arg2);
+
 	}
 
 	return -EINVAL;

---

## [3] Tim Merrifield — 2024-07-03
*Subject: [PATCH 2/2] x86/vmware: VMware support for TDX userspace hypercalls*

This change adds a handler for tdx_hcall in the x86_hyper_runtime type for
VMware hypervisors which will ultimately invoke __tdx_hypercall. The
handler (vmware_tdx_user_hcall) does not reuse the existing
vmware_tdx_hypercall for a couple of reasons.

First, while the few hypercalls that are invoked from the kernel expect
uint32 outputs, this may not be the case for every backdoor userspace may
call. So the existing interface is not sufficient. Additionally, we don't
require the branches based on output arguments. Finally, the
VMWARE_CMD_MASK employed in vmware_tdx_hypercall is applicable to only
hypercalls expected from the kernel.

Signed-off-by: Tim Merrifield <tim.merrifield@broadcom.com>
---
 arch/x86/kernel/cpu/vmware.c | 51 ++++++++++++++++++++++++++++--------
 1 file changed, 40 insertions(+), 11 deletions(-)

diff --git a/arch/x86/kernel/cpu/vmware.c b/arch/x86/kernel/cpu/vmware.c
index 00189cdeb775..54759c5a9808 100644
--- a/arch/x86/kernel/cpu/vmware.c
+++ b/arch/x86/kernel/cpu/vmware.c
@@ -494,6 +494,24 @@ static bool __init vmware_legacy_x2apic_available(void)
  * TDCALL[TDG.VP.VMCALL] uses %rax (arg0) and %rcx (arg2). Therefore,
  * we remap those registers to %r12 and %r13, respectively.
  */
+static inline void vmware_init_tdx_args(struct tdx_module_args *args, bool is_user,
+					unsigned long cmd, unsigned long in1,
+					unsigned long in3, unsigned long in4,
+					unsigned long in5, unsigned long in6)
+{
+	args->rbx = in1;
+	args->rdx = in3;
+	args->rsi = in4;
+	args->rdi = in5;
+	args->r10 = VMWARE_TDX_VENDOR_LEAF;
+	args->r11 = VMWARE_TDX_HCALL_FUNC;
+	args->r12 = VMWARE_HYPERVISOR_MAGIC;
+	args->r13 = cmd;
+	args->r14 = in6;
+	/* CPL */
+	args->r15 = is_user ? 3 : 0;
+}
+
 unsigned long vmware_tdx_hypercall(unsigned long cmd,
 				   unsigned long in1, unsigned long in3,
 				   unsigned long in4, unsigned long in5,
@@ -512,17 +530,7 @@ unsigned long vmware_tdx_hypercall(unsigned long cmd,
 		return ULONG_MAX;
 	}
 
-	args.rbx = in1;
-	args.rdx = in3;
-	args.rsi = in4;
-	args.rdi = in5;
-	args.r10 = VMWARE_TDX_VENDOR_LEAF;
-	args.r11 = VMWARE_TDX_HCALL_FUNC;
-	args.r12 = VMWARE_HYPERVISOR_MAGIC;
-	args.r13 = cmd;
-	/* CPL */
-	args.r15 = 0;
-
+	vmware_init_tdx_args(&args, false, cmd, in1, in3, in4, in5, 0);
 	__tdx_hypercall(&args);
 
 	if (out1)
@@ -539,6 +547,24 @@ unsigned long vmware_tdx_hypercall(unsigned long cmd,
 	return args.r12;
 }
 EXPORT_SYMBOL_GPL(vmware_tdx_hypercall);
+
+static bool vmware_tdx_user_hcall(struct pt_regs *regs)
+{
+	struct tdx_module_args args;
+
+	vmware_init_tdx_args(&args, true, regs->cx, regs->bx,
+			     regs->dx, regs->si, regs->di, regs->bp);
+	__tdx_hypercall(&args);
+	regs->ax = args.r12;
+	regs->bx = args.rbx;
+	regs->cx = args.r13;
+	regs->dx = args.rdx;
+	regs->si = args.rsi;
+	regs->di = args.rdi;
+	regs->bp = args.r14;
+
+	return true;
+}
 #endif
 
 #ifdef CONFIG_AMD_MEM_ENCRYPT
@@ -586,4 +612,7 @@ const __initconst struct hypervisor_x86 x86_hyper_vmware = {
 	.runtime.sev_es_hcall_prepare	= vmware_sev_es_hcall_prepare,
 	.runtime.sev_es_hcall_finish	= vmware_sev_es_hcall_finish,
 #endif
+#ifdef CONFIG_INTEL_TDX_GUEST
+	.runtime.tdx_hcall              = vmware_tdx_user_hcall,
+#endif
 };

---

## [4] Dave Hansen — 2024-07-03
*Subject: Re: [PATCH 0/2] Support userspace hypercalls for TDX*

On 7/3/24 16:35, Tim Merrifield wrote:
> VMCALL and VMMCALL instructions are used by x86 guests to request services
> from the host VMM. Both VMCALL and VMMCALL are not restricted to CPL 0.

Could we please be frank and transparent about what you actually want
here and how you expect this mechanism to be used?

...
> This patchset introduces a new x86 process control flag to address this
> concern. By setting the TIF_COCO_USER_HCALL thread information flag, the

The process, and anything it fork()s or execve()s, right?

This inheritance model seems more suited to wrapping a tiny helper app
around an existing binary, a la:

	prctl(ARCH_SET_COCO_USER_HCALL);
	execve("/existing/binary/that/i/surely/did/not/audit", ...);

... as opposed to something that you set in new versions of
open-vm-tools after an extensive audit and a bug fixing campaign to
clean up everything that the audit found.

---

## [5] Peter Zijlstra — 2024-07-04
*Subject: Re: [PATCH 0/2] Support userspace hypercalls for TDX*

On Wed, Jul 03, 2024 at 11:35:59PM +0000, Tim Merrifield wrote:
> VMCALL and VMMCALL instructions are used by x86 guests to request services
> from the host VMM. Both VMCALL and VMMCALL are not restricted to CPL 0.

And how are we to ascertain the software using these hooks is deemed
secure? What security risks are there for the kernel if a malicious
userspace process asks for these rights?

The kernel must assume malice on the part of userspace.

---

## [6] Tim Merrifield — 2024-07-05
*Subject: Re: [PATCH 0/2] Support userspace hypercalls for TDX*

Thanks for the response, Dave.

On Wed, Jul 03, 2024 at 05:18:22PM -0700, Dave Hansen wrote:
> 
> Could we please be frank and transparent about what you actually want

Sorry for being unclear. open-vm-tools is currently broken on TDX and
the intent here is to fix that. The idea is that versions of open-vm-tools
that have been audited and restricted to certain hypercalls, would execute
prctl to mark the process as capable of executing hypercalls.
    
> This inheritance model seems more suited to wrapping a tiny helper app
> around an existing binary, a la:

I understand the concern about inheritance. I chose prctl primarily
because of some existing options that seemed similar, mainly speculation
control. Is there an alternative approach that doesn't suffer from the
inheritance issue?

---

## [7] Tim Merrifield — 2024-07-05
*Subject: Re: [PATCH 0/2] Support userspace hypercalls for TDX*

On Thu, Jul 04, 2024 at 03:05:05PM +0200, Peter Zijlstra wrote:
> And how are we to ascertain the software using these hooks is deemed
> secure? What security risks are there for the kernel if a malicious

Thanks, Peter.
   
I don't believe there are any additional security risks for the kernel
itself being introduced here. The kernel is only responsible for
copying to and from userspace registers for the hypercall, and
executing the TDCALL. A similar approach already exists for AMD SEV
(see vc_handle_vmmcall), which does not restrict VMMCALL in the way
that TDX restricts VMCALL.

In the case of a malicious binary running in a TDX VM, if it wants to
communicate with the untrusted hypervisor or other software outside
of the TD, there are several existing mechanisms it could use, not
just a VMCALL. I guess the point here is that if the userspace
program is malicious, is anything gained by restricting VMCALL?

This patchset really only handles the case where a trusted guest
wants to limit access to VMCALL to binaries that self identify as
hardened against potential host attacks.

---

## [8] Kirill A . Shutemov — 2024-07-08
*Subject: Re: [PATCH 1/2] x86/tdx: Add prctl to allow userlevel TDX hypercalls*

On Wed, Jul 03, 2024 at 11:36:00PM +0000, Tim Merrifield wrote:
> Add a new prctl option to enable/disable user-level hypercalls when
> running in a confidential VM. Add support for checking this flag on

Maybe something like this would be more readable:

	if (!x86_platform.hyper.tdx_hcall)
		return -EOPNOTSUPP;

	if (!test_thread_flag(TIF_COCO_USER_HCALL))
		return -EOPNOTSUPP;

	if (!x86_platform.hyper.tdx_hcall(regs))
		return -EIO;

	return ve_instr_len(ve);

BTW, do we want tdx_hcall() to return errno instead of bool?

> +}
> +

Tabs instead of spaces for alignment, please.

>  #define _TIF_NOTIFY_RESUME	(1 << TIF_NOTIFY_RESUME)
>  #define _TIF_SIGPENDING		(1 << TIF_SIGPENDING)

Ditto.

>  
>  /* flags to check in __switch_to() */

Ditto.

>  #define ARCH_XCOMP_TILECFG		17
>  #define ARCH_XCOMP_TILEDATA		18

Hm. Per-thread flag is odd. I think it should be per-process.

>  long do_arch_prctl_common(int option, unsigned long arg2)
>  {

---

## [9] Kirill A . Shutemov — 2024-07-08
*Subject: Re: [PATCH 2/2] x86/vmware: VMware support for TDX userspace
 hypercalls*

On Wed, Jul 03, 2024 at 11:36:01PM +0000, Tim Merrifield wrote:
> @@ -539,6 +547,24 @@ unsigned long vmware_tdx_hypercall(unsigned long cmd,
>  	return args.r12;

Zero the struct to not leak data to VMM.

> +
> +	vmware_init_tdx_args(&args, true, regs->cx, regs->bx,

---

## [10] Tim Merrifield — 2024-07-22
*Subject: Re: [PATCH 1/2] x86/tdx: Add prctl to allow userlevel TDX hypercalls*

Thanks for the review, Kirill.

On Mon, Jul 08, 2024 at 03:19:54PM +0300, Kirill A . Shutemov wrote:
> Hm. Per-thread flag is odd. I think it should be per-process.

This is the only point I might need some clarification on. I agree
there doesn't seem to be much value in allowing per-thread control,
but I don't see any precedence for setting per-process flags through
arch_prctl or similar interfaces. Am I missing something?

---

## [11] Kirill A . Shutemov — 2024-07-23
*Subject: Re: [PATCH 1/2] x86/tdx: Add prctl to allow userlevel TDX hypercalls*

On Mon, Jul 22, 2024 at 10:04:40PM -0700, Tim Merrifield wrote:
> 
> Thanks for the review, Kirill.

LAM is per-process. But it can only be enabled while the process has only
one thread and locks on second thread spawn. See MM_CONTEXT_LOCK_LAM.

---
