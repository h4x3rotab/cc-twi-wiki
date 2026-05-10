---
title: 'Support userspace hypercalls for TDX'
date: 2024-07-26
last_reply: 2024-08-02
message_count: 6
participants: ['Tim Merrifield', 'kernel test robot', 'Kirill A . Shutemov']
---

## [1] Tim Merrifield — 2024-07-26

Hypercall instructions like VMCALL and VMMCALL are not restricted to CPL 0.
This allows userspace software like open-vm-tools to communicate directly
with the VMM.

For TDX VMs, this communication may violate the security model. Today,
VMCALLs are not forwarded to the host VMM, which breaks open-vm-tools
and any other userspace software that uses VMCALL.

But if userspace is aware of the risks and has been hardened to
address any known violations of the security model, then it seems
reasonable to allow hypercalls from this process to proceed.

This patchset introduces a new x86 process control flag to address this
concern. By setting the MM_CONTEXT_COCO_USER_HCALL flag, the process opts
in to user-level hypercalls. When TDX is enabled, the VMCALL will #VE and
control will be transferred to a hypervisor-specific hypercall handler
(similar to how things work today for SEV with
sev_es_hcall_prepare/sev_es_hcall_finish). The flag has no effect on
non-TDX VMs. Other confidential computing technologies could use this flag
to provide limited access to user-level hypercalls.

v1->v2 changes:
- Updated coverletter to get to the point a little faster.
- Patch 1: Changed to use a per-process flag rather than a per-thread
flag, based on feedback from Kirill Shutemov. I believe this also addresses
the issue of inheritance raised by Dave Hansen.
- Patch 1: Refactored the logic in tdx.c to be made more clear. Also,
tdx_hcall now returns an error code. Both suggested by Kirill.
- Patch 2: We now zero tdx_module_args to prevent data leakage to the VMM,
pointed out by Kirill.

Tim Merrifield (2):
  Add prctl to allow userlevel TDX hypercalls
  x86/vmware: VMware support for TDX userspace hypercalls

 arch/x86/coco/tdx/tdx.c           | 23 ++++++++++++++
 arch/x86/include/asm/mmu.h        |  2 ++
 arch/x86/include/asm/x86_init.h   |  1 +
 arch/x86/include/uapi/asm/prctl.h |  3 ++
 arch/x86/kernel/cpu/vmware.c      | 51 ++++++++++++++++++++++++-------
 arch/x86/kernel/process.c         | 22 +++++++++++++
 6 files changed, 91 insertions(+), 11 deletions(-)

---

## [2] Tim Merrifield — 2024-07-26
*Subject: [PATCH v2 1/2] Add prctl to allow userlevel TDX hypercalls*

Add a new process-level prctl option to enable/disable user-level
hypercalls when running in a confidential VM. Add support for
checking this flag on VMCALL #VE for TDX and transfer control to
a hypervisor vendor-specific handler.

Signed-off-by: Tim Merrifield <tim.merrifield@broadcom.com>
---
 arch/x86/coco/tdx/tdx.c           | 23 +++++++++++++++++++++++
 arch/x86/include/asm/mmu.h        |  2 ++
 arch/x86/include/asm/x86_init.h   |  1 +
 arch/x86/include/uapi/asm/prctl.h |  3 +++
 arch/x86/kernel/process.c         | 22 ++++++++++++++++++++++
 5 files changed, 51 insertions(+)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 078e2bac2553..02580fcf6157 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -238,6 +238,7 @@ static int ve_instr_len(struct ve_info *ve)
 	case EXIT_REASON_MSR_WRITE:
 	case EXIT_REASON_CPUID:
 	case EXIT_REASON_IO_INSTRUCTION:
+	case EXIT_REASON_VMCALL:
 		/* It is safe to use ve->instr_len for #VE due instructions */
 		return ve->instr_len;
 	case EXIT_REASON_EPT_VIOLATION:
@@ -634,6 +635,26 @@ void tdx_get_ve_info(struct ve_info *ve)
 	ve->instr_info  = upper_32_bits(args.r10);
 }
 
+/*
+ * Handle user-initiated, hypervisor-specific VMCALLs.
+ */
+static int handle_user_vmcall(struct pt_regs *regs, struct ve_info *ve)
+{
+	int err;
+
+	if (!x86_platform.hyper.tdx_hcall)
+		return -EOPNOTSUPP;
+
+	if (!test_bit(MM_CONTEXT_COCO_USER_HCALL, &current->mm->context.flags))
+		return -EOPNOTSUPP;
+
+	err = x86_platform.hyper.tdx_hcall(regs);
+	if (err)
+		return err;
+
+	return ve_instr_len(ve);
+}
+
 /*
  * Handle the user initiated #VE.
  *
@@ -645,6 +666,8 @@ static int virt_exception_user(struct pt_regs *regs, struct ve_info *ve)
 	switch (ve->exit_reason) {
 	case EXIT_REASON_CPUID:
 		return handle_cpuid(regs, ve);
+	case EXIT_REASON_VMCALL:
+		return handle_user_vmcall(regs, ve);
 	default:
 		pr_warn("Unexpected #VE: %lld\n", ve->exit_reason);
 		return -EIO;
diff --git a/arch/x86/include/asm/mmu.h b/arch/x86/include/asm/mmu.h
index ce4677b8b735..626ab327e34c 100644
--- a/arch/x86/include/asm/mmu.h
+++ b/arch/x86/include/asm/mmu.h
@@ -16,6 +16,8 @@
 #define MM_CONTEXT_LOCK_LAM		2
 /* Allow LAM and SVA coexisting */
 #define MM_CONTEXT_FORCE_TAGGED_SVA	3
+/* Allow COCO user-level hypercalls. */
+#define MM_CONTEXT_COCO_USER_HCALL	4
 
 /*
  * x86 has arch-specific MMU state beyond what lives in mm_struct.
diff --git a/arch/x86/include/asm/x86_init.h b/arch/x86/include/asm/x86_init.h
index 213cf5379a5a..04d43b91d32a 100644
--- a/arch/x86/include/asm/x86_init.h
+++ b/arch/x86/include/asm/x86_init.h
@@ -282,6 +282,7 @@ struct x86_hyper_runtime {
 	void (*sev_es_hcall_prepare)(struct ghcb *ghcb, struct pt_regs *regs);
 	bool (*sev_es_hcall_finish)(struct ghcb *ghcb, struct pt_regs *regs);
 	bool (*is_private_mmio)(u64 addr);
+	int  (*tdx_hcall)(struct pt_regs *regs);
 };
 
 /**
diff --git a/arch/x86/include/uapi/asm/prctl.h b/arch/x86/include/uapi/asm/prctl.h
index 384e2cc6ac19..37d154e503a3 100644
--- a/arch/x86/include/uapi/asm/prctl.h
+++ b/arch/x86/include/uapi/asm/prctl.h
@@ -16,6 +16,9 @@
 #define ARCH_GET_XCOMP_GUEST_PERM	0x1024
 #define ARCH_REQ_XCOMP_GUEST_PERM	0x1025
 
+#define ARCH_GET_COCO_USER_HCALL	0x1030
+#define ARCH_SET_COCO_USER_HCALL	0x1031
+
 #define ARCH_XCOMP_TILECFG		17
 #define ARCH_XCOMP_TILEDATA		18
 
diff --git a/arch/x86/kernel/process.c b/arch/x86/kernel/process.c
index f63f8fd00a91..198431919fd2 100644
--- a/arch/x86/kernel/process.c
+++ b/arch/x86/kernel/process.c
@@ -1042,6 +1042,24 @@ unsigned long __get_wchan(struct task_struct *p)
 	return addr;
 }
 
+static int get_coco_user_hcall_mode(void)
+{
+	return !test_bit(MM_CONTEXT_COCO_USER_HCALL,
+			&current->mm->context.flags);
+}
+
+static int set_coco_user_hcall_mode(unsigned long enabled)
+{
+	if (enabled)
+		set_bit(MM_CONTEXT_COCO_USER_HCALL,
+			&current->mm->context.flags);
+	else
+		clear_bit(MM_CONTEXT_COCO_USER_HCALL,
+			  &current->mm->context.flags);
+
+	return 0;
+}
+
 long do_arch_prctl_common(int option, unsigned long arg2)
 {
 	switch (option) {
@@ -1055,6 +1073,10 @@ long do_arch_prctl_common(int option, unsigned long arg2)
 	case ARCH_GET_XCOMP_GUEST_PERM:
 	case ARCH_REQ_XCOMP_GUEST_PERM:
 		return fpu_xstate_prctl(option, arg2);
+	case ARCH_GET_COCO_USER_HCALL:
+		return get_coco_user_hcall_mode();
+	case ARCH_SET_COCO_USER_HCALL:
+		return set_coco_user_hcall_mode(arg2);
 	}
 
 	return -EINVAL;

---

## [3] Tim Merrifield — 2024-07-26
*Subject: [PATCH v2 2/2] x86/vmware: VMware support for TDX userspace hypercalls*

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
index 00189cdeb775..e379facc3a5b 100644
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
+static int vmware_tdx_user_hcall(struct pt_regs *regs)
+{
+	struct tdx_module_args args = {};
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
+	return 0;
+}
 #endif
 
 #ifdef CONFIG_AMD_MEM_ENCRYPT
@@ -586,4 +612,7 @@ const __initconst struct hypervisor_x86 x86_hyper_vmware = {
 	.runtime.sev_es_hcall_prepare	= vmware_sev_es_hcall_prepare,
 	.runtime.sev_es_hcall_finish	= vmware_sev_es_hcall_finish,
 #endif
+#ifdef CONFIG_INTEL_TDX_GUEST
+	.runtime.tdx_hcall		= vmware_tdx_user_hcall,
+#endif
 };

---

## [4] kernel test robot — 2024-07-27
*Subject: Re: [PATCH v2 1/2] Add prctl to allow userlevel TDX hypercalls*

Hi Tim,

kernel test robot noticed the following build errors:

[auto build test ERROR on tip/x86/vmware]
[also build test ERROR on tip/x86/tdx linus/master v6.10 next-20240726]
[cannot apply to tip/x86/core]
[If your patch is applied to the wrong git tree, kindly drop us a note.
And when submitting patch, we suggest to use '--base' as documented in
https://git-scm.com/docs/git-format-patch#_base_tree_information]

url:    https://github.com/intel-lab-lkp/linux/commits/Tim-Merrifield/Add-prctl-to-allow-userlevel-TDX-hypercalls/20240727-025221
base:   tip/x86/vmware
patch link:    https://lore.kernel.org/r/651ceb5a89721621d522419e8a5d901632a78a22.1722019360.git.tim.merrifield%40broadcom.com
patch subject: [PATCH v2 1/2] Add prctl to allow userlevel TDX hypercalls
config: i386-buildonly-randconfig-001-20240727 (https://download.01.org/0day-ci/archive/20240727/202407271423.sLLB8VXR-lkp@intel.com/config)
compiler: gcc-13 (Ubuntu 13.2.0-4ubuntu3) 13.2.0
reproduce (this is a W=1 build): (https://download.01.org/0day-ci/archive/20240727/202407271423.sLLB8VXR-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202407271423.sLLB8VXR-lkp@intel.com/

All error/warnings (new ones prefixed by >>):

   In file included from include/linux/kernel.h:23,
                    from arch/x86/kernel/process.c:5:
   arch/x86/kernel/process.c: In function 'get_coco_user_hcall_mode':
>> arch/x86/kernel/process.c:1041:46: error: 'mm_context_t' has no member named 'flags'
    1041 |                         &current->mm->context.flags);
         |                                              ^
   include/linux/bitops.h:45:44: note: in definition of macro 'bitop'
      45 |           __builtin_constant_p((uintptr_t)(addr) != (uintptr_t)NULL) && \
         |                                            ^~~~
   arch/x86/kernel/process.c:1040:17: note: in expansion of macro 'test_bit'
    1040 |         return !test_bit(MM_CONTEXT_COCO_USER_HCALL,
         |                 ^~~~~~~~
>> arch/x86/kernel/process.c:1041:46: error: 'mm_context_t' has no member named 'flags'
    1041 |                         &current->mm->context.flags);
         |                                              ^
   include/linux/bitops.h:46:23: note: in definition of macro 'bitop'
      46 |           (uintptr_t)(addr) != (uintptr_t)NULL &&                       \
         |                       ^~~~
   arch/x86/kernel/process.c:1040:17: note: in expansion of macro 'test_bit'
    1040 |         return !test_bit(MM_CONTEXT_COCO_USER_HCALL,
         |                 ^~~~~~~~
>> arch/x86/kernel/process.c:1041:46: error: 'mm_context_t' has no member named 'flags'
    1041 |                         &current->mm->context.flags);
         |                                              ^
   include/linux/bitops.h:47:57: note: in definition of macro 'bitop'
      47 |           __builtin_constant_p(*(const unsigned long *)(addr))) ?       \
         |                                                         ^~~~
   arch/x86/kernel/process.c:1040:17: note: in expansion of macro 'test_bit'
    1040 |         return !test_bit(MM_CONTEXT_COCO_USER_HCALL,
         |                 ^~~~~~~~
>> arch/x86/kernel/process.c:1041:46: error: 'mm_context_t' has no member named 'flags'
    1041 |                         &current->mm->context.flags);
         |                                              ^
   include/linux/bitops.h:48:24: note: in definition of macro 'bitop'
      48 |          const##op(nr, addr) : op(nr, addr))
         |                        ^~~~
   arch/x86/kernel/process.c:1040:17: note: in expansion of macro 'test_bit'
    1040 |         return !test_bit(MM_CONTEXT_COCO_USER_HCALL,
         |                 ^~~~~~~~
>> arch/x86/kernel/process.c:1041:46: error: 'mm_context_t' has no member named 'flags'
    1041 |                         &current->mm->context.flags);
         |                                              ^
   include/linux/bitops.h:48:39: note: in definition of macro 'bitop'
      48 |          const##op(nr, addr) : op(nr, addr))
         |                                       ^~~~
   arch/x86/kernel/process.c:1040:17: note: in expansion of macro 'test_bit'
    1040 |         return !test_bit(MM_CONTEXT_COCO_USER_HCALL,
         |                 ^~~~~~~~
   arch/x86/kernel/process.c: In function 'set_coco_user_hcall_mode':
   arch/x86/kernel/process.c:1048:46: error: 'mm_context_t' has no member named 'flags'
    1048 |                         &current->mm->context.flags);
         |                                              ^
   arch/x86/kernel/process.c:1051:48: error: 'mm_context_t' has no member named 'flags'
    1051 |                           &current->mm->context.flags);
         |                                                ^
   arch/x86/kernel/process.c: In function 'get_coco_user_hcall_mode':
>> arch/x86/kernel/process.c:1042:1: warning: control reaches end of non-void function [-Wreturn-type]
    1042 | }
         | ^


vim +1041 arch/x86/kernel/process.c

  1037	
  1038	static int get_coco_user_hcall_mode(void)
  1039	{
  1040		return !test_bit(MM_CONTEXT_COCO_USER_HCALL,
> 1041				&current->mm->context.flags);
> 1042	}
  1043

---

## [5] kernel test robot — 2024-07-27
*Subject: Re: [PATCH v2 1/2] Add prctl to allow userlevel TDX hypercalls*

Hi Tim,

kernel test robot noticed the following build errors:

[auto build test ERROR on tip/x86/vmware]
[also build test ERROR on tip/x86/tdx linus/master v6.10 next-20240726]
[cannot apply to tip/x86/core]
[If your patch is applied to the wrong git tree, kindly drop us a note.
And when submitting patch, we suggest to use '--base' as documented in
https://git-scm.com/docs/git-format-patch#_base_tree_information]

url:    https://github.com/intel-lab-lkp/linux/commits/Tim-Merrifield/Add-prctl-to-allow-userlevel-TDX-hypercalls/20240727-025221
base:   tip/x86/vmware
patch link:    https://lore.kernel.org/r/651ceb5a89721621d522419e8a5d901632a78a22.1722019360.git.tim.merrifield%40broadcom.com
patch subject: [PATCH v2 1/2] Add prctl to allow userlevel TDX hypercalls
config: i386-buildonly-randconfig-003-20240727 (https://download.01.org/0day-ci/archive/20240727/202407271528.NcCDP6PG-lkp@intel.com/config)
compiler: gcc-8 (Ubuntu 8.4.0-3ubuntu2) 8.4.0
reproduce (this is a W=1 build): (https://download.01.org/0day-ci/archive/20240727/202407271528.NcCDP6PG-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202407271528.NcCDP6PG-lkp@intel.com/

All errors (new ones prefixed by >>):

   In file included from include/linux/kernel.h:23,
                    from arch/x86/kernel/process.c:5:
   arch/x86/kernel/process.c: In function 'get_coco_user_hcall_mode':
>> arch/x86/kernel/process.c:1041:25: error: 'mm_context_t' {aka 'struct <anonymous>'} has no member named 'flags'
       &current->mm->context.flags);
                            ^
   include/linux/bitops.h:45:37: note: in definition of macro 'bitop'
       __builtin_constant_p((uintptr_t)(addr) != (uintptr_t)NULL) && \
                                        ^~~~
   arch/x86/kernel/process.c:1040:10: note: in expansion of macro 'test_bit'
     return !test_bit(MM_CONTEXT_COCO_USER_HCALL,
             ^~~~~~~~
>> arch/x86/kernel/process.c:1041:25: error: 'mm_context_t' {aka 'struct <anonymous>'} has no member named 'flags'
       &current->mm->context.flags);
                            ^
   include/linux/bitops.h:46:16: note: in definition of macro 'bitop'
       (uintptr_t)(addr) != (uintptr_t)NULL &&   \
                   ^~~~
   arch/x86/kernel/process.c:1040:10: note: in expansion of macro 'test_bit'
     return !test_bit(MM_CONTEXT_COCO_USER_HCALL,
             ^~~~~~~~
>> arch/x86/kernel/process.c:1041:25: error: 'mm_context_t' {aka 'struct <anonymous>'} has no member named 'flags'
       &current->mm->context.flags);
                            ^
   include/linux/bitops.h:47:50: note: in definition of macro 'bitop'
       __builtin_constant_p(*(const unsigned long *)(addr))) ? \
                                                     ^~~~
   arch/x86/kernel/process.c:1040:10: note: in expansion of macro 'test_bit'
     return !test_bit(MM_CONTEXT_COCO_USER_HCALL,
             ^~~~~~~~
>> arch/x86/kernel/process.c:1041:25: error: 'mm_context_t' {aka 'struct <anonymous>'} has no member named 'flags'
       &current->mm->context.flags);
                            ^
   include/linux/bitops.h:48:17: note: in definition of macro 'bitop'
      const##op(nr, addr) : op(nr, addr))
                    ^~~~
   arch/x86/kernel/process.c:1040:10: note: in expansion of macro 'test_bit'
     return !test_bit(MM_CONTEXT_COCO_USER_HCALL,
             ^~~~~~~~
>> arch/x86/kernel/process.c:1041:25: error: 'mm_context_t' {aka 'struct <anonymous>'} has no member named 'flags'
       &current->mm->context.flags);
                            ^
   include/linux/bitops.h:48:32: note: in definition of macro 'bitop'
      const##op(nr, addr) : op(nr, addr))
                                   ^~~~
   arch/x86/kernel/process.c:1040:10: note: in expansion of macro 'test_bit'
     return !test_bit(MM_CONTEXT_COCO_USER_HCALL,
             ^~~~~~~~
   arch/x86/kernel/process.c: In function 'set_coco_user_hcall_mode':
   arch/x86/kernel/process.c:1048:25: error: 'mm_context_t' {aka 'struct <anonymous>'} has no member named 'flags'
       &current->mm->context.flags);
                            ^
   arch/x86/kernel/process.c:1051:27: error: 'mm_context_t' {aka 'struct <anonymous>'} has no member named 'flags'
         &current->mm->context.flags);
                              ^
   arch/x86/kernel/process.c: In function 'get_coco_user_hcall_mode':
   arch/x86/kernel/process.c:1042:1: warning: control reaches end of non-void function [-Wreturn-type]
    }
    ^


vim +1041 arch/x86/kernel/process.c

  1037	
  1038	static int get_coco_user_hcall_mode(void)
  1039	{
  1040		return !test_bit(MM_CONTEXT_COCO_USER_HCALL,
> 1041				&current->mm->context.flags);
  1042	}
  1043

---

## [6] Kirill A . Shutemov — 2024-08-02
*Subject: Re: [PATCH v2 1/2] Add prctl to allow userlevel TDX hypercalls*

On Fri, Jul 26, 2024 at 06:58:00PM +0000, Tim Merrifield wrote:
> Add a new process-level prctl option to enable/disable user-level
> hypercalls when running in a confidential VM. Add support for

We need more context from the cover letter here.

> diff --git a/arch/x86/kernel/process.c b/arch/x86/kernel/process.c
> index f63f8fd00a91..198431919fd2 100644

Hm. Why "!"?

---
