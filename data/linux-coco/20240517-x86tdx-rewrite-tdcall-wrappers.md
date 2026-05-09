---
title: 'x86/tdx: Rewrite TDCALL wrappers'
date: 2024-05-17
last_reply: 2024-05-28
message_count: 38
participants: ['Kirill A. Shutemov', 'Dave Hansen', 'Paolo Bonzini', 'Huang, Kai', 'Wei Liu']
---

## [1] Kirill A. Shutemov — 2024-05-17

Sean noticing that the TDCALL wrappers were generating a lot of awful
code.

TDCALL calls are centralized into a few megawrappers that take the
struct tdx_module_args as input. Most of the call sites only use a few
arguments, but they have to zero out unused fields in the structure to
avoid data leaks to the VMM. This leads to the compiler generating
inefficient code: dozens of instructions per call site to clear unused
fields of the structure.

This issue can be avoided by using more targeted wrappers.

After the rewrite code size is cut by ~3K:

add/remove: 7/15 grow/shrink: 1/17 up/down: 212/-3502 (-3290)

Please take a look. I would appreciate any feedback.

Kirill A. Shutemov (20):
  x86/tdx: Introduce tdvmcall_trampoline()
  x86/tdx: Add macros to generate TDVMCALL wrappers
  x86/tdx: Convert port I/O handling to use new TDVMCALL macros
  x86/tdx: Convert HLT handling to use new TDVMCALL_0()
  x86/tdx: Convert MSR read handling to use new TDVMCALL_1()
  x86/tdx: Convert MSR write handling to use new TDVMCALL_0()
  x86/tdx: Convert CPUID handling to use new TDVMCALL_4()
  x86/tdx: Convert MMIO handling to use new TDVMCALL macros
  x86/tdx: Convert MAP_GPA hypercall to use new TDVMCALL macros
  x86/tdx: Convert GET_QUOTE hypercall to use new TDVMCALL macros
  x86/tdx: Rewrite tdx_panic() without __tdx_hypercall()
  x86/tdx: Rewrite tdx_kvm_hypercall() without __tdx_hypercall()
  x86/tdx: Rewrite hv_tdx_hypercall() without __tdx_hypercall()
  x86/tdx: Add macros to generate TDCALL wrappers
  x86/tdx: Convert PAGE_ACCEPT tdcall to use new TDCALL_0() macro
  x86/tdx: Convert VP_INFO tdcall to use new TDCALL_5() macro
  x86/tdx: Convert VM_RD/VM_WR tdcalls to use new TDCALL macros
  x86/tdx: Convert VP_VEINFO_GET tdcall to use new TDCALL_5() macro
  x86/tdx: Convert MR_REPORT tdcall to use new TDCALL_0() macro
  x86/tdx: Remove old TDCALL wrappers

 arch/x86/boot/compressed/tdx.c    |  32 +---
 arch/x86/coco/tdx/tdcall.S        | 145 ++++++++++-----
 arch/x86/coco/tdx/tdx-shared.c    |  26 +--
 arch/x86/coco/tdx/tdx.c           | 298 ++++++++----------------------
 arch/x86/hyperv/ivm.c             |  33 +---
 arch/x86/include/asm/shared/tdx.h | 159 +++++++++++-----
 arch/x86/include/asm/tdx.h        |   2 +
 arch/x86/virt/vmx/tdx/tdxcall.S   |  29 +--
 tools/objtool/noreturns.h         |   2 +-
 9 files changed, 322 insertions(+), 404 deletions(-)

---

## [2] Kirill A. Shutemov — 2024-05-17
*Subject: [PATCH 01/20] x86/tdx: Introduce tdvmcall_trampoline()*

TDCALL calls are centralized into a few megawrappers that take the
struct tdx_module_args as input. Most of the call sites only use a few
arguments, but they have to zero out unused fields in the structure to
avoid data leaks to the VMM. This leads to the compiler generating
inefficient code: dozens of instructions per call site to clear unused
fields of the structure.

This issue can be avoided by using more targeted wrappers.
tdvmcall_trampoline() provides a common base for them.

The function will be used from inline assembly to handle most TDVMCALL
cases.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/coco/tdx/tdcall.S | 49 ++++++++++++++++++++++++++++++++++++++
 1 file changed, 49 insertions(+)

diff --git a/arch/x86/coco/tdx/tdcall.S b/arch/x86/coco/tdx/tdcall.S
index 52d9786da308..12185fbd33ba 100644
--- a/arch/x86/coco/tdx/tdcall.S
+++ b/arch/x86/coco/tdx/tdcall.S
@@ -61,3 +61,52 @@ SYM_FUNC_END(__tdcall_ret)
 SYM_FUNC_START(__tdcall_saved_ret)
 	TDX_MODULE_CALL host=0 ret=1 saved=1
 SYM_FUNC_END(__tdcall_saved_ret)
+
+/*
+ * tdvmcall_trampoline() - Wrapper for TDG.VP.VMCALL. Covers common cases: up
+ * to five input and out arguments.
+ *
+ * tdvmcall_trampoline() function ABI is not SYSV ABI compliant. Caller has to
+ * deal with it.
+ *
+ * Input:
+ * RAX	- Type of call, TDX_HYPERCALL_STANDARD for calls defined in GHCI spec
+ * RBX	- 1st argument (R11), leaf ID if RAX is TDX_HYPERCALL_STANDARD
+ * RDI	- 2nd argument (R12)
+ * RSI	- 3rd argument (R13)
+ * RDX	- 4th argument (R14)
+ * RCX	- 5th argument (R15)
+ *
+ * Output:
+ * R10	- TDVMCALL error code
+ * R11	- Output 1
+ * R12	- Output 2
+ * R13	- Output 3
+ * R14	- Output 4
+ * R15	- Output 5
+ */
+.pushsection .noinstr.text, "ax"
+SYM_FUNC_START(tdvmcall_trampoline)
+	movq	%rax, %r10
+	movq    %rbx, %r11
+	movq    %rdi, %r12
+	movq    %rsi, %r13
+	movq    %rdx, %r14
+	movq    %rcx, %r15
+
+	movq	$TDG_VP_VMCALL, %rax
+
+	/* RCX is bitmap of registers exposed to VMM on TDG.VM.VMCALL */
+	movq    $(TDX_R10 | TDX_R11 | TDX_R12 | TDX_R13 | TDX_R14 | TDX_R15), %rcx
+
+	tdcall
+
+	/* TDG.VP.VMCALL never fails on correct use. Panic if it fails. */
+	testq   %rax, %rax
+	jnz     .Lpanic
+
+	RET
+.Lpanic:
+	ud2
+SYM_FUNC_END(tdvmcall_trampoline)
+.popsection

---

## [3] Kirill A. Shutemov — 2024-05-17
*Subject: [PATCH 02/20] x86/tdx: Add macros to generate TDVMCALL wrappers*

Introduce a set of macros that allow to generate wrappers for TDVMCALL
leafs. The macros uses tdvmcall_trmapoline() and provides SYSV-complaint
ABI on top of it.

There are three macros differentiated by number of return parameters.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/include/asm/shared/tdx.h | 54 +++++++++++++++++++++++++++++++
 1 file changed, 54 insertions(+)

diff --git a/arch/x86/include/asm/shared/tdx.h b/arch/x86/include/asm/shared/tdx.h
index 89f7fcade8ae..ddf2cc4a45da 100644
--- a/arch/x86/include/asm/shared/tdx.h
+++ b/arch/x86/include/asm/shared/tdx.h
@@ -76,6 +76,60 @@
 
 #include <linux/compiler_attributes.h>
 
+#define TDVMCALL_0(reason, in_r12, in_r13, in_r14, in_r15)			\
+({										\
+	long __ret;								\
+										\
+	asm(									\
+		"call	tdvmcall_trampoline\n\t"				\
+		"movq	%%r10, %[r10_out]\n\t"					\
+		: [r10_out] "=r" (__ret), ASM_CALL_CONSTRAINT			\
+		: "a" (TDX_HYPERCALL_STANDARD), "b" (reason),			\
+		  "D" (in_r12), "S"(in_r13), "d"(in_r14), "c" (in_r15)		\
+		: "r12", "r13", "r14", "r15"					\
+	);									\
+	__ret;									\
+})
+
+#define TDVMCALL_1(reason, in_r12, in_r13, in_r14, in_r15, out_r11)		\
+({										\
+	long __ret;								\
+										\
+	asm(									\
+		"call	tdvmcall_trampoline\n\t"				\
+		"movq	%%r10, %[r10_out]\n\t"					\
+		"movq	%%r11, %[r11_out]\n\t"					\
+		: [r10_out] "=r" (__ret), [r11_out] "=r" (out_r11),		\
+		  ASM_CALL_CONSTRAINT						\
+		: "a" (TDX_HYPERCALL_STANDARD), "b" (reason),			\
+		  "D" (in_r12), "S"(in_r13), "d"(in_r14), "c" (in_r15)		\
+		: "r10", "r11", "r12", "r13", "r14", "r15"			\
+	);									\
+	__ret;									\
+})
+
+#define TDVMCALL_4(reason, in_r12, in_r13, in_r14, in_r15,			\
+		   out_r12, out_r13, out_r14, out_r15)				\
+({										\
+	long __ret;								\
+										\
+	asm(									\
+		"call	tdvmcall_trampoline\n\t"				\
+		"movq	%%r10, %[r10_out]\n\t"					\
+		"movq	%%r12, %[r12_out]\n\t"					\
+		"movq	%%r13, %[r13_out]\n\t"					\
+		"movq	%%r14, %[r14_out]\n\t"					\
+		"movq	%%r15, %[r15_out]\n\t"					\
+		: [r10_out] "=r" (__ret), ASM_CALL_CONSTRAINT,			\
+		  [r12_out] "=r" (out_r12), [r13_out] "=r" (out_r13),		\
+		  [r14_out] "=r" (out_r14), [r15_out] "=r" (out_r15)		\
+		: "a" (TDX_HYPERCALL_STANDARD), "b" (reason),			\
+		  "D" (in_r12), "S"(in_r13), "d"(in_r14), "c" (in_r15)		\
+		: "r10", "r12", "r13", "r14", "r15"				\
+	);									\
+	__ret;									\
+})
+
 /*
  * Used in __tdcall*() to gather the input/output registers' values of the
  * TDCALL instruction when requesting services from the TDX module. This is a

---

## [4] Kirill A. Shutemov — 2024-05-17
*Subject: [PATCH 03/20] x86/tdx: Convert port I/O handling to use new TDVMCALL macros*

Use newly introduced TDVMCALL_0() and TDVMCALL_1() instead of
__tdx_hypercall() to handle port I/O in TDX guest.

It cuts handle_io() size in half:

Function                                     old     new   delta
handle_io                                    436     202    -234

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/boot/compressed/tdx.c    | 26 +++++++-------------------
 arch/x86/coco/tdx/tdx.c           | 23 +++++++----------------
 arch/x86/include/asm/shared/tdx.h |  4 ++++
 3 files changed, 18 insertions(+), 35 deletions(-)

diff --git a/arch/x86/boot/compressed/tdx.c b/arch/x86/boot/compressed/tdx.c
index 8451d6a1030c..0ae05edc7d42 100644
--- a/arch/x86/boot/compressed/tdx.c
+++ b/arch/x86/boot/compressed/tdx.c
@@ -18,32 +18,20 @@ void __tdx_hypercall_failed(void)
 
 static inline unsigned int tdx_io_in(int size, u16 port)
 {
-	struct tdx_module_args args = {
-		.r10 = TDX_HYPERCALL_STANDARD,
-		.r11 = hcall_func(EXIT_REASON_IO_INSTRUCTION),
-		.r12 = size,
-		.r13 = 0,
-		.r14 = port,
-	};
+	u64 out;
 
-	if (__tdx_hypercall(&args))
+	if (TDVMCALL_1(hcall_func(EXIT_REASON_IO_INSTRUCTION),
+		       size, TDX_PORT_READ, port, 0, out)) {
 		return UINT_MAX;
+	}
 
-	return args.r11;
+	return out;
 }
 
 static inline void tdx_io_out(int size, u16 port, u32 value)
 {
-	struct tdx_module_args args = {
-		.r10 = TDX_HYPERCALL_STANDARD,
-		.r11 = hcall_func(EXIT_REASON_IO_INSTRUCTION),
-		.r12 = size,
-		.r13 = 1,
-		.r14 = port,
-		.r15 = value,
-	};
-
-	__tdx_hypercall(&args);
+	TDVMCALL_0(hcall_func(EXIT_REASON_IO_INSTRUCTION),
+		   size, TDX_PORT_WRITE, port, value);
 }
 
 static inline u8 tdx_inb(u16 port)
diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index cadd583d6f62..6e0e5648ebd1 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -21,10 +21,6 @@
 #define EPT_READ	0
 #define EPT_WRITE	1
 
-/* Port I/O direction */
-#define PORT_READ	0
-#define PORT_WRITE	1
-
 /* See Exit Qualification for I/O Instructions in VMX documentation */
 #define VE_IS_IO_IN(e)		((e) & BIT(3))
 #define VE_GET_IO_SIZE(e)	(((e) & GENMASK(2, 0)) + 1)
@@ -612,14 +608,7 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 
 static bool handle_in(struct pt_regs *regs, int size, int port)
 {
-	struct tdx_module_args args = {
-		.r10 = TDX_HYPERCALL_STANDARD,
-		.r11 = hcall_func(EXIT_REASON_IO_INSTRUCTION),
-		.r12 = size,
-		.r13 = PORT_READ,
-		.r14 = port,
-	};
-	u64 mask = GENMASK(BITS_PER_BYTE * size, 0);
+	u64 mask, out;
 	bool success;
 
 	/*
@@ -627,12 +616,14 @@ static bool handle_in(struct pt_regs *regs, int size, int port)
 	 * in TDX Guest-Host-Communication Interface (GHCI) section titled
 	 * "TDG.VP.VMCALL<Instruction.IO>".
 	 */
-	success = !__tdx_hypercall(&args);
+	success = !TDVMCALL_1(hcall_func(EXIT_REASON_IO_INSTRUCTION),
+			      size, TDX_PORT_READ, port, 0, out);
 
 	/* Update part of the register affected by the emulated instruction */
+	mask = GENMASK(BITS_PER_BYTE * size, 0);
 	regs->ax &= ~mask;
 	if (success)
-		regs->ax |= args.r11 & mask;
+		regs->ax |= out & mask;
 
 	return success;
 }
@@ -646,8 +637,8 @@ static bool handle_out(struct pt_regs *regs, int size, int port)
 	 * in TDX Guest-Host-Communication Interface (GHCI) section titled
 	 * "TDG.VP.VMCALL<Instruction.IO>".
 	 */
-	return !_tdx_hypercall(hcall_func(EXIT_REASON_IO_INSTRUCTION), size,
-			       PORT_WRITE, port, regs->ax & mask);
+	return !TDVMCALL_0(hcall_func(EXIT_REASON_IO_INSTRUCTION),
+			   size, TDX_PORT_WRITE, port, regs->ax & mask);
 }
 
 /*
diff --git a/arch/x86/include/asm/shared/tdx.h b/arch/x86/include/asm/shared/tdx.h
index ddf2cc4a45da..46c299dc9cf0 100644
--- a/arch/x86/include/asm/shared/tdx.h
+++ b/arch/x86/include/asm/shared/tdx.h
@@ -72,6 +72,10 @@
 #define TDX_PS_1G	2
 #define TDX_PS_NR	(TDX_PS_1G + 1)
 
+/* Port I/O direction */
+#define TDX_PORT_READ	0
+#define TDX_PORT_WRITE	1
+
 #ifndef __ASSEMBLY__
 
 #include <linux/compiler_attributes.h>

---

## [5] Kirill A. Shutemov — 2024-05-17
*Subject: [PATCH 04/20] x86/tdx: Convert HLT handling to use new TDVMCALL_0()*

Use newly introduced TDVMCALL_0() instead of __tdx_hypercall() to handle
HLT instruction emulation.

It cuts code bloat substantially:

Function                                     old     new   delta
tdx_safe_halt                                 58      88     +30
tdx_handle_virt_exception                   2023    2052     +29
__pfx___halt                                  16       -     -16
__halt                                       171       -    -171
Total: Before=6350, After=6222, chg -2.02%

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/coco/tdx/tdx.c | 29 ++++++-----------------------
 1 file changed, 6 insertions(+), 23 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 6e0e5648ebd1..dce7d6f9f895 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -350,18 +350,12 @@ static int ve_instr_len(struct ve_info *ve)
 	}
 }
 
-static u64 __cpuidle __halt(const bool irq_disabled)
+static int handle_halt(struct ve_info *ve)
 {
-	struct tdx_module_args args = {
-		.r10 = TDX_HYPERCALL_STANDARD,
-		.r11 = hcall_func(EXIT_REASON_HLT),
-		.r12 = irq_disabled,
-	};
-
 	/*
 	 * Emulate HLT operation via hypercall. More info about ABI
 	 * can be found in TDX Guest-Host-Communication Interface
-	 * (GHCI), section 3.8 TDG.VP.VMCALL<Instruction.HLT>.
+	 * (GHCI), section TDG.VP.VMCALL<Instruction.HLT>.
 	 *
 	 * The VMM uses the "IRQ disabled" param to understand IRQ
 	 * enabled status (RFLAGS.IF) of the TD guest and to determine
@@ -370,14 +364,7 @@ static u64 __cpuidle __halt(const bool irq_disabled)
 	 * can keep the vCPU in virtual HLT, even if an IRQ is
 	 * pending, without hanging/breaking the guest.
 	 */
-	return __tdx_hypercall(&args);
-}
-
-static int handle_halt(struct ve_info *ve)
-{
-	const bool irq_disabled = irqs_disabled();
-
-	if (__halt(irq_disabled))
+	if (TDVMCALL_0(hcall_func(EXIT_REASON_HLT), irqs_disabled(), 0, 0, 0))
 		return -EIO;
 
 	return ve_instr_len(ve);
@@ -385,13 +372,9 @@ static int handle_halt(struct ve_info *ve)
 
 void __cpuidle tdx_safe_halt(void)
 {
-	const bool irq_disabled = false;
-
-	/*
-	 * Use WARN_ONCE() to report the failure.
-	 */
-	if (__halt(irq_disabled))
-		WARN_ONCE(1, "HLT instruction emulation failed\n");
+	/* See comment in handle_halt() */
+	WARN_ONCE(TDVMCALL_0(hcall_func(EXIT_REASON_HLT), false, 0, 0, 0),
+		  "HLT instruction emulation failed");
 }
 
 static int read_msr(struct pt_regs *regs, struct ve_info *ve)

---

## [6] Kirill A. Shutemov — 2024-05-17
*Subject: [PATCH 05/20] x86/tdx: Convert MSR read handling to use new TDVMCALL_1()*

Use newly introduced TDVMCALL_1() instead of __tdx_hypercall() to handle
MSR read emulation.

It cuts code bloat substantially:

Function                                     old     new   delta
tdx_handle_virt_exception                   2052    1947    -105

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/coco/tdx/tdx.c | 15 +++++++--------
 arch/x86/hyperv/ivm.c   | 10 ++--------
 2 files changed, 9 insertions(+), 16 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index dce7d6f9f895..32c519d096de 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -379,22 +379,21 @@ void __cpuidle tdx_safe_halt(void)
 
 static int read_msr(struct pt_regs *regs, struct ve_info *ve)
 {
-	struct tdx_module_args args = {
-		.r10 = TDX_HYPERCALL_STANDARD,
-		.r11 = hcall_func(EXIT_REASON_MSR_READ),
-		.r12 = regs->cx,
-	};
+	u64 val;
 
 	/*
 	 * Emulate the MSR read via hypercall. More info about ABI
 	 * can be found in TDX Guest-Host-Communication Interface
 	 * (GHCI), section titled "TDG.VP.VMCALL<Instruction.RDMSR>".
 	 */
-	if (__tdx_hypercall(&args))
+	if (TDVMCALL_1(hcall_func(EXIT_REASON_MSR_READ),
+		       regs->cx, 0, 0, 0, val)) {
 		return -EIO;
+	}
+
+	regs->ax = lower_32_bits(val);
+	regs->dx = upper_32_bits(val);
 
-	regs->ax = lower_32_bits(args.r11);
-	regs->dx = upper_32_bits(args.r11);
 	return ve_instr_len(ve);
 }
 
diff --git a/arch/x86/hyperv/ivm.c b/arch/x86/hyperv/ivm.c
index b4a851d27c7c..3e2cbfb2203d 100644
--- a/arch/x86/hyperv/ivm.c
+++ b/arch/x86/hyperv/ivm.c
@@ -399,18 +399,12 @@ static void hv_tdx_msr_write(u64 msr, u64 val)
 
 static void hv_tdx_msr_read(u64 msr, u64 *val)
 {
-	struct tdx_module_args args = {
-		.r10 = TDX_HYPERCALL_STANDARD,
-		.r11 = EXIT_REASON_MSR_READ,
-		.r12 = msr,
-	};
+	u64 ret;
 
-	u64 ret = __tdx_hypercall(&args);
+	ret = TDVMCALL_1(hcall_func(EXIT_REASON_MSR_READ), msr, 0, 0, 0, *val);
 
 	if (WARN_ONCE(ret, "Failed to emulate MSR read: %lld\n", ret))
 		*val = 0;
-	else
-		*val = args.r11;
 }
 
 u64 hv_tdx_hypercall(u64 control, u64 param1, u64 param2)

---

## [7] Kirill A. Shutemov — 2024-05-17
*Subject: [PATCH 06/20] x86/tdx: Convert MSR write handling to use new TDVMCALL_0()*

Use newly introduced TDVMCALL_0() instead of __tdx_hypercall() to handle
MSR write emulation.

It cuts code bloat substantially:

Function                                     old     new   delta
tdx_handle_virt_exception                   1947    1819    -128

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/coco/tdx/tdx.c | 9 ++-------
 arch/x86/hyperv/ivm.c   | 9 ++-------
 2 files changed, 4 insertions(+), 14 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 32c519d096de..f59a2b3500db 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -399,19 +399,14 @@ static int read_msr(struct pt_regs *regs, struct ve_info *ve)
 
 static int write_msr(struct pt_regs *regs, struct ve_info *ve)
 {
-	struct tdx_module_args args = {
-		.r10 = TDX_HYPERCALL_STANDARD,
-		.r11 = hcall_func(EXIT_REASON_MSR_WRITE),
-		.r12 = regs->cx,
-		.r13 = (u64)regs->dx << 32 | regs->ax,
-	};
+	u64 val = (u64)regs->dx << 32 | regs->ax;
 
 	/*
 	 * Emulate the MSR write via hypercall. More info about ABI
 	 * can be found in TDX Guest-Host-Communication Interface
 	 * (GHCI) section titled "TDG.VP.VMCALL<Instruction.WRMSR>".
 	 */
-	if (__tdx_hypercall(&args))
+	if (TDVMCALL_0(hcall_func(EXIT_REASON_MSR_WRITE), regs->cx, val, 0, 0))
 		return -EIO;
 
 	return ve_instr_len(ve);
diff --git a/arch/x86/hyperv/ivm.c b/arch/x86/hyperv/ivm.c
index 3e2cbfb2203d..18d0892d9fc4 100644
--- a/arch/x86/hyperv/ivm.c
+++ b/arch/x86/hyperv/ivm.c
@@ -385,14 +385,9 @@ static inline void hv_ghcb_msr_read(u64 msr, u64 *value) {}
 #ifdef CONFIG_INTEL_TDX_GUEST
 static void hv_tdx_msr_write(u64 msr, u64 val)
 {
-	struct tdx_module_args args = {
-		.r10 = TDX_HYPERCALL_STANDARD,
-		.r11 = EXIT_REASON_MSR_WRITE,
-		.r12 = msr,
-		.r13 = val,
-	};
+	u64 ret;
 
-	u64 ret = __tdx_hypercall(&args);
+	ret = TDVMCALL_0(hcall_func(EXIT_REASON_MSR_WRITE), msr, val, 0, 0);
 
 	WARN_ONCE(ret, "Failed to emulate MSR write: %lld\n", ret);
 }

---

## [8] Kirill A. Shutemov — 2024-05-17
*Subject: [PATCH 07/20] x86/tdx: Convert CPUID handling to use new TDVMCALL_4()*

Use newly introduced TDVMCALL_4() instead of __tdx_hypercall() to handle
CPUID instruction emulation.

It cuts code bloat substantially:

Function                                     old     new   delta
tdx_handle_virt_exception                   1819    1747     -72

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/coco/tdx/tdx.c | 20 ++------------------
 1 file changed, 2 insertions(+), 18 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index f59a2b3500db..c436cab355e0 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -414,13 +414,6 @@ static int write_msr(struct pt_regs *regs, struct ve_info *ve)
 
 static int handle_cpuid(struct pt_regs *regs, struct ve_info *ve)
 {
-	struct tdx_module_args args = {
-		.r10 = TDX_HYPERCALL_STANDARD,
-		.r11 = hcall_func(EXIT_REASON_CPUID),
-		.r12 = regs->ax,
-		.r13 = regs->cx,
-	};
-
 	/*
 	 * Only allow VMM to control range reserved for hypervisor
 	 * communication.
@@ -438,19 +431,10 @@ static int handle_cpuid(struct pt_regs *regs, struct ve_info *ve)
 	 * ABI can be found in TDX Guest-Host-Communication Interface
 	 * (GHCI), section titled "VP.VMCALL<Instruction.CPUID>".
 	 */
-	if (__tdx_hypercall(&args))
+	if (TDVMCALL_4(EXIT_REASON_CPUID, regs->ax, regs->cx, 0, 0,
+		       regs->ax, regs->bx, regs->cx, regs->dx))
 		return -EIO;
 
-	/*
-	 * As per TDX GHCI CPUID ABI, r12-r15 registers contain contents of
-	 * EAX, EBX, ECX, EDX registers after the CPUID instruction execution.
-	 * So copy the register contents back to pt_regs.
-	 */
-	regs->ax = args.r12;
-	regs->bx = args.r13;
-	regs->cx = args.r14;
-	regs->dx = args.r15;
-
 	return ve_instr_len(ve);
 }

---

## [9] Kirill A. Shutemov — 2024-05-17
*Subject: [PATCH 08/20] x86/tdx: Convert MMIO handling to use new TDVMCALL macros*

Use newly introduced TDVMCALL_0() and TDVMCALL_1() instead of
__tdx_hypercall() to handle MMIO emulation.

It cuts code bloat substantially:

Function                                     old     new   delta
tdx_handle_virt_exception                   1747    1383    -364

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/coco/tdx/tdx.c | 30 +++++++++++++-----------------
 1 file changed, 13 insertions(+), 17 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index c436cab355e0..df3e10d899b3 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -438,38 +438,34 @@ static int handle_cpuid(struct pt_regs *regs, struct ve_info *ve)
 	return ve_instr_len(ve);
 }
 
-static bool mmio_read(int size, unsigned long addr, unsigned long *val)
+static bool mmio_read(int size, unsigned long gpa, u64 *val)
 {
-	struct tdx_module_args args = {
-		.r10 = TDX_HYPERCALL_STANDARD,
-		.r11 = hcall_func(EXIT_REASON_EPT_VIOLATION),
-		.r12 = size,
-		.r13 = EPT_READ,
-		.r14 = addr,
-		.r15 = *val,
-	};
+	bool ret;
+	u64 out;
 
-	if (__tdx_hypercall(&args))
-		return false;
+	ret = !TDVMCALL_1(hcall_func(EXIT_REASON_EPT_VIOLATION),
+			  size, EPT_READ, gpa, 0, out);
+	if (ret)
+		*val = out;
 
-	*val = args.r11;
-	return true;
+	return ret;
 }
 
-static bool mmio_write(int size, unsigned long addr, unsigned long val)
+static bool mmio_write(int size, u64 gpa, u64 val)
 {
-	return !_tdx_hypercall(hcall_func(EXIT_REASON_EPT_VIOLATION), size,
-			       EPT_WRITE, addr, val);
+	return !TDVMCALL_0(hcall_func(EXIT_REASON_EPT_VIOLATION),
+			 size, EPT_WRITE, gpa, val);
 }
 
 static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 {
-	unsigned long *reg, val, vaddr;
+	unsigned long *reg, vaddr;
 	char buffer[MAX_INSN_SIZE];
 	enum insn_mmio_type mmio;
 	struct insn insn = {};
 	int size, extend_size;
 	u8 extend_val = 0;
+	u64 val;
 
 	/* Only in-kernel MMIO is supported */
 	if (WARN_ON_ONCE(user_mode(regs)))

---

## [10] Kirill A. Shutemov — 2024-05-17
*Subject: [PATCH 09/20] x86/tdx: Convert MAP_GPA hypercall to use new TDVMCALL macros*

Use newly introduced TDVMCALL_1() instead of __tdx_hypercall() to issue
MAP_GPA hypercall.

It cuts code bloat substantially:

Function                                     old     new   delta
tdx_enc_status_changed                       352     242    -110
tdx_kexec_finish                             645     530    -115
tdx_enc_status_change_prepare                326     181    -145
Total: Before=5553, After=5183, chg -6.66%

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/coco/tdx/tdx.c | 12 +++---------
 1 file changed, 3 insertions(+), 9 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index df3e10d899b3..7c874a50a319 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -797,15 +797,10 @@ static bool tdx_map_gpa(phys_addr_t start, phys_addr_t end, bool enc)
 	}
 
 	while (retry_count < max_retries_per_page) {
-		struct tdx_module_args args = {
-			.r10 = TDX_HYPERCALL_STANDARD,
-			.r11 = TDVMCALL_MAP_GPA,
-			.r12 = start,
-			.r13 = end - start };
-
-		u64 map_fail_paddr;
-		u64 ret = __tdx_hypercall(&args);
+		u64 map_fail_paddr, ret;
 
+		ret = TDVMCALL_1(TDVMCALL_MAP_GPA,
+				 start, end - start, 0, 0, map_fail_paddr);
 		if (ret != TDVMCALL_STATUS_RETRY)
 			return !ret;
 		/*
@@ -813,7 +808,6 @@ static bool tdx_map_gpa(phys_addr_t start, phys_addr_t end, bool enc)
 		 * region starting at the GPA specified in R11. R11 comes
 		 * from the untrusted VMM. Sanity check it.
 		 */
-		map_fail_paddr = args.r11;
 		if (map_fail_paddr < start || map_fail_paddr >= end)
 			return false;

---

## [11] Kirill A. Shutemov — 2024-05-17
*Subject: [PATCH 10/20] x86/tdx: Convert GET_QUOTE hypercall to use new TDVMCALL macros*

Use newly introduced TDVMCALL_0() instead of __tdx_hypercall() to issue
GET_QUOTE hypercall.

It cuts code bloat substantially:

Function                                     old     new   delta
tdx_hcall_get_quote                          188      76    -112

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/coco/tdx/tdx.c | 3 ++-
 1 file changed, 2 insertions(+), 1 deletion(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 7c874a50a319..3f0be1d3cccb 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -150,7 +150,8 @@ EXPORT_SYMBOL_GPL(tdx_mcall_get_report0);
 u64 tdx_hcall_get_quote(u8 *buf, size_t size)
 {
 	/* Since buf is a shared memory, set the shared (decrypted) bits */
-	return _tdx_hypercall(TDVMCALL_GET_QUOTE, cc_mkdec(virt_to_phys(buf)), size, 0, 0);
+	return TDVMCALL_0(TDVMCALL_GET_QUOTE,
+			  cc_mkdec(virt_to_phys(buf)), size, 0, 0);
 }
 EXPORT_SYMBOL_GPL(tdx_hcall_get_quote);

---

## [12] Kirill A. Shutemov — 2024-05-17
*Subject: [PATCH 11/20] x86/tdx: Rewrite tdx_panic() without __tdx_hypercall()*

tdx_panic() uses REPORT_FATAL_ERROR hypercall to deliver panic message
in ealy boot. Rewrite it without using __tdx_hypercall().

REPORT_FATAL_ERROR hypercall is special. It uses pretty much all
available registers to pass down the error message. TDVMCALL macros are
not usable here.

Implement the hypercall directly in assembly.

It cuts code bloat substantially:

Function                                     old     new   delta
tdx_panic                                    222      59    -163

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/coco/tdx/tdcall.S | 28 ++++++++++++++++++++++++++++
 arch/x86/coco/tdx/tdx.c    | 31 +++----------------------------
 arch/x86/include/asm/tdx.h |  2 ++
 tools/objtool/noreturns.h  |  1 +
 4 files changed, 34 insertions(+), 28 deletions(-)

diff --git a/arch/x86/coco/tdx/tdcall.S b/arch/x86/coco/tdx/tdcall.S
index 12185fbd33ba..269e5789672a 100644
--- a/arch/x86/coco/tdx/tdcall.S
+++ b/arch/x86/coco/tdx/tdcall.S
@@ -110,3 +110,31 @@ SYM_FUNC_START(tdvmcall_trampoline)
 	ud2
 SYM_FUNC_END(tdvmcall_trampoline)
 .popsection
+
+SYM_FUNC_START(tdvmcall_report_fatal_error)
+	movq	$TDX_HYPERCALL_STANDARD, %r10
+	movq	$TDVMCALL_REPORT_FATAL_ERROR, %r11
+	movq	%rdi, %r12
+	movq	$0, %r13
+
+	movq	%rsi, %rcx
+
+	/* Order according to the GHCI */
+	movq	0*8(%rcx), %r14
+	movq	1*8(%rcx), %r15
+	movq	2*8(%rcx), %rbx
+	movq	3*8(%rcx), %rdi
+	movq	4*8(%rcx), %rsi
+	movq	5*8(%rcx), %r8
+	movq	6*8(%rcx), %r9
+	movq	7*8(%rcx), %rdx
+
+	movq	$TDG_VP_VMCALL, %rax
+	movq	$(TDX_RDX | TDX_RBX | TDX_RSI | TDX_RDI | TDX_R8  | TDX_R9  | \
+		  TDX_R10 | TDX_R11 | TDX_R12 | TDX_R13 | TDX_R14 | TDX_R15), \
+		%rcx
+
+	tdcall
+
+	ud2
+SYM_FUNC_END(tdvmcall_report_fatal_error)
diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 3f0be1d3cccb..b7299e668564 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -157,37 +157,12 @@ EXPORT_SYMBOL_GPL(tdx_hcall_get_quote);
 
 static void __noreturn tdx_panic(const char *msg)
 {
-	struct tdx_module_args args = {
-		.r10 = TDX_HYPERCALL_STANDARD,
-		.r11 = TDVMCALL_REPORT_FATAL_ERROR,
-		.r12 = 0, /* Error code: 0 is Panic */
-	};
-	union {
-		/* Define register order according to the GHCI */
-		struct { u64 r14, r15, rbx, rdi, rsi, r8, r9, rdx; };
-
-		char str[64];
-	} message;
+	char str[64];
 
 	/* VMM assumes '\0' in byte 65, if the message took all 64 bytes */
-	strtomem_pad(message.str, msg, '\0');
+	strtomem_pad(str, msg, '\0');
 
-	args.r8  = message.r8;
-	args.r9  = message.r9;
-	args.r14 = message.r14;
-	args.r15 = message.r15;
-	args.rdi = message.rdi;
-	args.rsi = message.rsi;
-	args.rbx = message.rbx;
-	args.rdx = message.rdx;
-
-	/*
-	 * This hypercall should never return and it is not safe
-	 * to keep the guest running. Call it forever if it
-	 * happens to return.
-	 */
-	while (1)
-		__tdx_hypercall(&args);
+	tdvmcall_report_fatal_error(0, str);
 }
 
 /*
diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index eba178996d84..f67e5e6b66ad 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -54,6 +54,8 @@ struct ve_info {
 
 void __init tdx_early_init(void);
 
+void __noreturn tdvmcall_report_fatal_error(u64 error_code, const char str[64]);
+
 void tdx_get_ve_info(struct ve_info *ve);
 
 bool tdx_handle_virt_exception(struct pt_regs *regs, struct ve_info *ve);
diff --git a/tools/objtool/noreturns.h b/tools/objtool/noreturns.h
index 7ebf29c91184..0670cacf0734 100644
--- a/tools/objtool/noreturns.h
+++ b/tools/objtool/noreturns.h
@@ -39,6 +39,7 @@ NORETURN(sev_es_terminate)
 NORETURN(snp_abort)
 NORETURN(start_kernel)
 NORETURN(stop_this_cpu)
+NORETURN(tdvmcall_report_fatal_error)
 NORETURN(usercopy_abort)
 NORETURN(x86_64_start_kernel)
 NORETURN(x86_64_start_reservations)

---

## [13] Kirill A. Shutemov — 2024-05-17
*Subject: [PATCH 12/20] x86/tdx: Rewrite tdx_kvm_hypercall() without __tdx_hypercall()*

tdx_kvm_hypercall() issues KVM hypercall. Rewrite it without using
__tdx_hypercall(). Use tdvmcall_trampoline() instead.

It cuts code bloat substantially:

Function                                     old     new   delta
tdx_kvm_hypercall                            160      53    -107

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/coco/tdx/tdx.c | 16 ++++++++--------
 1 file changed, 8 insertions(+), 8 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index b7299e668564..e7ffe1cd6d32 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -49,15 +49,15 @@ noinstr void __noreturn __tdx_hypercall_failed(void)
 long tdx_kvm_hypercall(unsigned int nr, unsigned long p1, unsigned long p2,
 		       unsigned long p3, unsigned long p4)
 {
-	struct tdx_module_args args = {
-		.r10 = nr,
-		.r11 = p1,
-		.r12 = p2,
-		.r13 = p3,
-		.r14 = p4,
-	};
+	long ret;
 
-	return __tdx_hypercall(&args);
+	asm("call	tdvmcall_trampoline\n\t"
+	    "movq	%%r10, %0\n\t"
+	    : "=r" (ret)
+	    : "a" (nr), "b" (p1), "D" (p2), "S"(p3), "d"(p4), "c" (0)
+	    : "r12", "r13", "r14", "r15");
+
+	return ret;
 }
 EXPORT_SYMBOL_GPL(tdx_kvm_hypercall);
 #endif

---

## [14] Kirill A. Shutemov — 2024-05-17
*Subject: [PATCH 13/20] x86/tdx: Rewrite hv_tdx_hypercall() without __tdx_hypercall()*

Rewrite hv_tdx_hypercall() in assembly to remove one more
__tdx_hypercall() user.

tdvmcall_trampoline() cannot be used here as Hyper-V uses R8 and RDX to
pass down parameters which is incompatible with tdvmcall_trampoline()

The rewrite cuts code bloat substantially:

Function                                     old     new   delta
hv_tdx_hypercall                             171      42    -129

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/coco/tdx/tdcall.S | 30 ++++++++++++++++++++++++++++++
 arch/x86/hyperv/ivm.c      | 14 --------------
 2 files changed, 30 insertions(+), 14 deletions(-)

diff --git a/arch/x86/coco/tdx/tdcall.S b/arch/x86/coco/tdx/tdcall.S
index 269e5789672a..5b60b9c8799f 100644
--- a/arch/x86/coco/tdx/tdcall.S
+++ b/arch/x86/coco/tdx/tdcall.S
@@ -138,3 +138,33 @@ SYM_FUNC_START(tdvmcall_report_fatal_error)
 
 	ud2
 SYM_FUNC_END(tdvmcall_report_fatal_error)
+
+#ifdef CONFIG_HYPERV
+/*
+ * hv_tdx_hypercall() - Issue Hyper-V hypercall
+ *
+ * RDI - Hypercall ID
+ * RSI - Parameter 1
+ * RCX - Parameter 2
+ */
+SYM_FUNC_START(hv_tdx_hypercall)
+	movq	%rdi, %r10
+	movq    %rsi, %rdx
+	movq    %rcx, %r8
+
+	movq	$TDG_VP_VMCALL, %rax
+	movq    $(TDX_R8 | TDX_R10 | TDX_RDX), %rcx
+
+	tdcall
+
+	/* TDG.VP.VMCALL never fails on correct use. Panic if it fails. */
+	testq   %rax, %rax
+	jnz	.Lpanic_hv
+
+	movq	%r11, %rax
+
+	RET
+.Lpanic_hv:
+	ud2
+SYM_FUNC_END(hv_tdx_hypercall)
+#endif
diff --git a/arch/x86/hyperv/ivm.c b/arch/x86/hyperv/ivm.c
index 18d0892d9fc4..562980e19d68 100644
--- a/arch/x86/hyperv/ivm.c
+++ b/arch/x86/hyperv/ivm.c
@@ -401,20 +401,6 @@ static void hv_tdx_msr_read(u64 msr, u64 *val)
 	if (WARN_ONCE(ret, "Failed to emulate MSR read: %lld\n", ret))
 		*val = 0;
 }
-
-u64 hv_tdx_hypercall(u64 control, u64 param1, u64 param2)
-{
-	struct tdx_module_args args = { };
-
-	args.r10 = control;
-	args.rdx = param1;
-	args.r8  = param2;
-
-	(void)__tdx_hypercall(&args);
-
-	return args.r11;
-}
-
 #else
 static inline void hv_tdx_msr_write(u64 msr, u64 value) {}
 static inline void hv_tdx_msr_read(u64 msr, u64 *value) {}

---

## [15] Kirill A. Shutemov — 2024-05-17
*Subject: [PATCH 14/20] x86/tdx: Add macros to generate TDCALL wrappers*

Introduce a set of macros that allow to generate wrappers for TDCALL
leafs.

There are three macros differentiated by number of return parameters.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/include/asm/shared/tdx.h | 58 +++++++++++++++++++++++++++++++
 1 file changed, 58 insertions(+)

diff --git a/arch/x86/include/asm/shared/tdx.h b/arch/x86/include/asm/shared/tdx.h
index 46c299dc9cf0..70190ebc63ca 100644
--- a/arch/x86/include/asm/shared/tdx.h
+++ b/arch/x86/include/asm/shared/tdx.h
@@ -80,6 +80,64 @@
 
 #include <linux/compiler_attributes.h>
 
+#define TDCALL	".byte	0x66,0x0f,0x01,0xcc\n\t"
+
+#define TDCALL_0(reason, in_rcx, in_rdx, in_r8, in_r9)				\
+({										\
+	long __ret;								\
+										\
+	asm(									\
+		"movq	%[r8_in], %%r8\n\t"					\
+		"movq	%[r9_in], %%r9\n\t"					\
+		TDCALL								\
+		: "=a" (__ret), ASM_CALL_CONSTRAINT				\
+		: "a" (reason), "c" (in_rcx), "d" (in_rdx),			\
+		  [r8_in] "rm" ((u64)in_r8), [r9_in] "rm" ((u64)in_r9)		\
+		: "r8", "r9"							\
+	);									\
+	__ret;									\
+})
+
+#define TDCALL_1(reason, in_rcx, in_rdx, in_r8, in_r9, out_r8)			\
+({										\
+	long __ret;								\
+										\
+	asm(									\
+		"movq	%[r8_in], %%r8\n\t"					\
+		"movq	%[r9_in], %%r9\n\t"					\
+		TDCALL								\
+		"movq	%%r8, %[r8_out]\n\t"					\
+		: "=a" (__ret), ASM_CALL_CONSTRAINT, [r8_out] "=rm" (out_r8)	\
+		: "a" (reason), "c" (in_rcx), "d" (in_rdx),			\
+		  [r8_in] "rm" ((u64)in_r8), [r9_in] "rm" ((u64)in_r9)		\
+		: "r8", "r9"							\
+	);									\
+	__ret;									\
+})
+
+#define TDCALL_5(reason, in_rcx, in_rdx, in_r8, in_r9,				\
+		 out_rcx, out_rdx, out_r8, out_r9, out_r10)			\
+({										\
+	long __ret;								\
+										\
+	asm(									\
+		"movq	%[r8_in], %%r8\n\t"					\
+		"movq	%[r9_in], %%r9\n\t"					\
+		TDCALL								\
+		"movq	%%r8, %[r8_out]\n\t"					\
+		"movq	%%r9, %[r9_out]\n\t"					\
+		"movq	%%r10, %[r10_out]\n\t"					\
+		: "=a" (__ret), ASM_CALL_CONSTRAINT,				\
+		  "=c" (out_rcx), "=d" (out_rdx),				\
+		  [r8_out] "=rm" (out_r8), [r9_out] "=rm" (out_r9),		\
+		  [r10_out] "=rm" (out_r10)					\
+		: "a" (reason), "c" (in_rcx), "d" (in_rdx),			\
+		  [r8_in] "rm" ((u64)in_r8), [r9_in] "rm" ((u64)in_r9)		\
+		: "r8", "r9", "r10"						\
+	);									\
+	__ret;									\
+})
+
 #define TDVMCALL_0(reason, in_r12, in_r13, in_r14, in_r15)			\
 ({										\
 	long __ret;								\

---

## [16] Kirill A. Shutemov — 2024-05-17
*Subject: [PATCH 15/20] x86/tdx: Convert PAGE_ACCEPT tdcall to use new TDCALL_0() macro*

Use newly introduced TDCALL_0() instead of __tdcall() to issue
PAGE_ACCEPT tdcall.

It cuts code bloat substantially:

Function                                     old     new   delta
tdx_accept_memory                            592     233    -359

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/coco/tdx/tdx-shared.c | 6 +++---
 1 file changed, 3 insertions(+), 3 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx-shared.c b/arch/x86/coco/tdx/tdx-shared.c
index 1655aa56a0a5..9104e96eeefd 100644
--- a/arch/x86/coco/tdx/tdx-shared.c
+++ b/arch/x86/coco/tdx/tdx-shared.c
@@ -5,8 +5,8 @@ static unsigned long try_accept_one(phys_addr_t start, unsigned long len,
 				    enum pg_level pg_level)
 {
 	unsigned long accept_size = page_level_size(pg_level);
-	struct tdx_module_args args = {};
 	u8 page_size;
+	u64 ret;
 
 	if (!IS_ALIGNED(start, accept_size))
 		return 0;
@@ -34,8 +34,8 @@ static unsigned long try_accept_one(phys_addr_t start, unsigned long len,
 		return 0;
 	}
 
-	args.rcx = start | page_size;
-	if (__tdcall(TDG_MEM_PAGE_ACCEPT, &args))
+	ret = TDCALL_0(TDG_MEM_PAGE_ACCEPT, start | page_size, 0, 0, 0);
+	if (ret)
 		return 0;
 
 	return accept_size;

---

## [17] Kirill A. Shutemov — 2024-05-17
*Subject: [PATCH 16/20] x86/tdx: Convert VP_INFO tdcall to use new TDCALL_5() macro*

Use newly introduced TDCALL_5() instead of tdcall() to issue VP_INFO
tdcall.

It cuts code bloat slightly:

Function                                     old     new   delta
tdx_early_init                               780     744     -36

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/coco/tdx/tdx.c | 27 +++++++++++++--------------
 1 file changed, 13 insertions(+), 14 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index e7ffe1cd6d32..e1849878f3bc 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -247,20 +247,22 @@ static void enable_cpu_topology_enumeration(void)
 	tdg_vm_wr(TDCS_TD_CTLS, TD_CTLS_ENUM_TOPOLOGY, TD_CTLS_ENUM_TOPOLOGY);
 }
 
+static void tdg_vp_info(u64 *gpa_width, u64 *attributes)
+{
+	u64 dummy, ret;
+
+	ret = TDCALL_5(TDG_VP_INFO, 0, 0, 0, 0, *gpa_width, *attributes, dummy,
+		       dummy, dummy);
+	BUG_ON(ret);
+
+	*gpa_width &= GENMASK(5, 0);
+}
+
 static void tdx_setup(u64 *cc_mask)
 {
-	struct tdx_module_args args = {};
-	unsigned int gpa_width;
-	u64 td_attr;
+	u64 gpa_width, td_attr;
 
-	/*
-	 * TDINFO TDX module call is used to get the TD execution environment
-	 * information like GPA width, number of available vcpus, debug mode
-	 * information, etc. More details about the ABI can be found in TDX
-	 * Guest-Host-Communication Interface (GHCI), section 2.4.2 TDCALL
-	 * [TDG.VP.INFO].
-	 */
-	tdcall(TDG_VP_INFO, &args);
+	tdg_vp_info(&gpa_width, &td_attr);
 
 	/*
 	 * The highest bit of a guest physical address is the "sharing" bit.
@@ -269,11 +271,8 @@ static void tdx_setup(u64 *cc_mask)
 	 * The GPA width that comes out of this call is critical. TDX guests
 	 * can not meaningfully run without it.
 	 */
-	gpa_width = args.rcx & GENMASK(5, 0);
 	*cc_mask = BIT_ULL(gpa_width - 1);
 
-	td_attr = args.rdx;
-
 	/* Kernel does not use NOTIFY_ENABLES and does not need random #VEs */
 	tdg_vm_wr(TDCS_NOTIFY_ENABLES, 0, -1ULL);

---

## [18] Kirill A. Shutemov — 2024-05-17
*Subject: [PATCH 17/20] x86/tdx: Convert VM_RD/VM_WR tdcalls to use new TDCALL macros*

Use newly introduced TDCALL instead of tdcall() to issue VM_RD/VM_WR
tdcalls

It increase code slightly:

Function                                     old     new   delta
tdx_early_init                               744     776     +32

but combined with VP_INFO changes the total effect on tdx_early_init()
is code reduction.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/coco/tdx/tdx.c | 18 ++----------------
 1 file changed, 2 insertions(+), 16 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index e1849878f3bc..6559f3842f67 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -76,27 +76,13 @@ static inline void tdcall(u64 fn, struct tdx_module_args *args)
 /* Read TD-scoped metadata */
 static inline u64 tdg_vm_rd(u64 field, u64 *value)
 {
-	struct tdx_module_args args = {
-		.rdx = field,
-	};
-	u64 ret;
-
-	ret = __tdcall_ret(TDG_VM_RD, &args);
-	*value = args.r8;
-
-	return ret;
+	return TDCALL_1(TDG_VM_RD, 0, field, 0, 0, value);
 }
 
 /* Write TD-scoped metadata */
 static inline u64 tdg_vm_wr(u64 field, u64 value, u64 mask)
 {
-	struct tdx_module_args args = {
-		.rdx = field,
-		.r8 = value,
-		.r9 = mask,
-	};
-
-	return __tdcall(TDG_VM_WR, &args);
+	return TDCALL_1(TDG_VM_WR, 0, field, value, mask, value);
 }
 
 /**

---

## [19] Kirill A. Shutemov — 2024-05-17
*Subject: [PATCH 18/20] x86/tdx: Convert VP_VEINFO_GET tdcall to use new TDCALL_5() macro*

Use newly introduced TDCALL_5() instead of tdcall() to issue
VP_VEINFO_GET tdcall.

It cuts code bloat substantially:

Function                                     old     new   delta
tdx_get_ve_info                              253     116    -137

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/coco/tdx/tdx.c | 31 +++++++------------------------
 1 file changed, 7 insertions(+), 24 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 6559f3842f67..42436a43bb49 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -615,32 +615,15 @@ __init bool tdx_early_handle_ve(struct pt_regs *regs)
 
 void tdx_get_ve_info(struct ve_info *ve)
 {
-	struct tdx_module_args args = {};
+	u64 instr_info, ret;
 
-	/*
-	 * Called during #VE handling to retrieve the #VE info from the
-	 * TDX module.
-	 *
-	 * This has to be called early in #VE handling.  A "nested" #VE which
-	 * occurs before this will raise a #DF and is not recoverable.
-	 *
-	 * The call retrieves the #VE info from the TDX module, which also
-	 * clears the "#VE valid" flag. This must be done before anything else
-	 * because any #VE that occurs while the valid flag is set will lead to
-	 * #DF.
-	 *
-	 * Note, the TDX module treats virtual NMIs as inhibited if the #VE
-	 * valid flag is set. It means that NMI=>#VE will not result in a #DF.
-	 */
-	tdcall(TDG_VP_VEINFO_GET, &args);
+	ret = TDCALL_5(TDG_VP_VEINFO_GET, 0, 0, 0, 0,
+		 ve->exit_reason, ve->exit_qual, ve->gla, ve->gpa, instr_info);
 
-	/* Transfer the output parameters */
-	ve->exit_reason = args.rcx;
-	ve->exit_qual   = args.rdx;
-	ve->gla         = args.r8;
-	ve->gpa         = args.r9;
-	ve->instr_len   = lower_32_bits(args.r10);
-	ve->instr_info  = upper_32_bits(args.r10);
+	BUG_ON(ret);
+
+	ve->instr_len   = lower_32_bits(instr_info);
+	ve->instr_info  = upper_32_bits(instr_info);
 }
 
 /*

---

## [20] Kirill A. Shutemov — 2024-05-17
*Subject: [PATCH 19/20] x86/tdx: Convert MR_REPORT tdcall to use new TDCALL_0() macro*

Use newly introduced TDCALL_0() instead of tdcall() to issue
MR_REPORT tdcall.

It cuts code bloat substantially:

Function                                     old     new   delta
tdx_mcall_get_report0                        229     111    -118

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/coco/tdx/tdx.c | 16 ++++++----------
 1 file changed, 6 insertions(+), 10 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 42436a43bb49..45be53d5eeb4 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -101,19 +101,15 @@ static inline u64 tdg_vm_wr(u64 field, u64 value, u64 mask)
  */
 int tdx_mcall_get_report0(u8 *reportdata, u8 *tdreport)
 {
-	struct tdx_module_args args = {
-		.rcx = virt_to_phys(tdreport),
-		.rdx = virt_to_phys(reportdata),
-		.r8 = TDREPORT_SUBTYPE_0,
-	};
 	u64 ret;
 
-	ret = __tdcall(TDG_MR_REPORT, &args);
-	if (ret) {
-		if (TDCALL_RETURN_CODE(ret) == TDCALL_INVALID_OPERAND)
-			return -EINVAL;
+	ret = TDCALL_0(TDG_MR_REPORT, virt_to_phys(tdreport),
+		       virt_to_phys(reportdata), TDREPORT_SUBTYPE_0, 0);
+
+	if (TDCALL_RETURN_CODE(ret) == TDCALL_INVALID_OPERAND)
+		return -EINVAL;
+	else if (ret)
 		return -EIO;
-	}
 
 	return 0;
 }

---

## [21] Kirill A. Shutemov — 2024-05-17
*Subject: [PATCH 20/20] x86/tdx: Remove old TDCALL wrappers*

All code has been converted to new TDCALL wrappers.

Drop the old wrappers.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/boot/compressed/tdx.c    |  6 ----
 arch/x86/coco/tdx/tdcall.S        | 60 ++-----------------------------
 arch/x86/coco/tdx/tdx-shared.c    | 20 -----------
 arch/x86/coco/tdx/tdx.c           | 18 ----------
 arch/x86/include/asm/shared/tdx.h | 43 +---------------------
 arch/x86/virt/vmx/tdx/tdxcall.S   | 29 +++++----------
 tools/objtool/noreturns.h         |  1 -
 7 files changed, 12 insertions(+), 165 deletions(-)

diff --git a/arch/x86/boot/compressed/tdx.c b/arch/x86/boot/compressed/tdx.c
index 0ae05edc7d42..b74084a46f2f 100644
--- a/arch/x86/boot/compressed/tdx.c
+++ b/arch/x86/boot/compressed/tdx.c
@@ -10,12 +10,6 @@
 
 #include <asm/shared/tdx.h>
 
-/* Called from __tdx_hypercall() for unrecoverable failure */
-void __tdx_hypercall_failed(void)
-{
-	error("TDVMCALL failed. TDX module bug?");
-}
-
 static inline unsigned int tdx_io_in(int size, u16 port)
 {
 	u64 out;
diff --git a/arch/x86/coco/tdx/tdcall.S b/arch/x86/coco/tdx/tdcall.S
index 5b60b9c8799f..407e2b7ae515 100644
--- a/arch/x86/coco/tdx/tdcall.S
+++ b/arch/x86/coco/tdx/tdcall.S
@@ -1,66 +1,12 @@
 /* SPDX-License-Identifier: GPL-2.0 */
 #include <asm/asm-offsets.h>
 #include <asm/asm.h>
+#include <asm/shared/tdx.h>
 
 #include <linux/linkage.h>
-#include <linux/errno.h>
 
-#include "../../virt/vmx/tdx/tdxcall.S"
-
-.section .noinstr.text, "ax"
-
-/*
- * __tdcall()  - Used by TDX guests to request services from the TDX
- * module (does not include VMM services) using TDCALL instruction.
- *
- * __tdcall() function ABI:
- *
- * @fn   (RDI)	- TDCALL Leaf ID, moved to RAX
- * @args (RSI)	- struct tdx_module_args for input
- *
- * Only RCX/RDX/R8-R11 are used as input registers.
- *
- * Return status of TDCALL via RAX.
- */
-SYM_FUNC_START(__tdcall)
-	TDX_MODULE_CALL host=0
-SYM_FUNC_END(__tdcall)
-
-/*
- * __tdcall_ret() - Used by TDX guests to request services from the TDX
- * module (does not include VMM services) using TDCALL instruction, with
- * saving output registers to the 'struct tdx_module_args' used as input.
- *
- * __tdcall_ret() function ABI:
- *
- * @fn   (RDI)	- TDCALL Leaf ID, moved to RAX
- * @args (RSI)	- struct tdx_module_args for input and output
- *
- * Only RCX/RDX/R8-R11 are used as input/output registers.
- *
- * Return status of TDCALL via RAX.
- */
-SYM_FUNC_START(__tdcall_ret)
-	TDX_MODULE_CALL host=0 ret=1
-SYM_FUNC_END(__tdcall_ret)
-
-/*
- * __tdcall_saved_ret() - Used by TDX guests to request services from the
- * TDX module (including VMM services) using TDCALL instruction, with
- * saving output registers to the 'struct tdx_module_args' used as input.
- *
- * __tdcall_saved_ret() function ABI:
- *
- * @fn   (RDI)	- TDCALL leaf ID, moved to RAX
- * @args (RSI)	- struct tdx_module_args for input/output
- *
- * All registers in @args are used as input/output registers.
- *
- * On successful completion, return the hypercall error code.
- */
-SYM_FUNC_START(__tdcall_saved_ret)
-	TDX_MODULE_CALL host=0 ret=1 saved=1
-SYM_FUNC_END(__tdcall_saved_ret)
+/* TDCALL is supported in Binutils >= 2.36 */
+#define tdcall		.byte 0x66,0x0f,0x01,0xcc
 
 /*
  * tdvmcall_trampoline() - Wrapper for TDG.VP.VMCALL. Covers common cases: up
diff --git a/arch/x86/coco/tdx/tdx-shared.c b/arch/x86/coco/tdx/tdx-shared.c
index 9104e96eeefd..b181f7d4d3b9 100644
--- a/arch/x86/coco/tdx/tdx-shared.c
+++ b/arch/x86/coco/tdx/tdx-shared.c
@@ -69,23 +69,3 @@ bool tdx_accept_memory(phys_addr_t start, phys_addr_t end)
 
 	return true;
 }
-
-noinstr u64 __tdx_hypercall(struct tdx_module_args *args)
-{
-	/*
-	 * For TDVMCALL explicitly set RCX to the bitmap of shared registers.
-	 * The caller isn't expected to set @args->rcx anyway.
-	 */
-	args->rcx = TDVMCALL_EXPOSE_REGS_MASK;
-
-	/*
-	 * Failure of __tdcall_saved_ret() indicates a failure of the TDVMCALL
-	 * mechanism itself and that something has gone horribly wrong with
-	 * the TDX module.  __tdx_hypercall_failed() never returns.
-	 */
-	if (__tdcall_saved_ret(TDG_VP_VMCALL, args))
-		__tdx_hypercall_failed();
-
-	/* TDVMCALL leaf return code is in R10 */
-	return args->r10;
-}
diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 45be53d5eeb4..7d9306bd67af 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -38,13 +38,6 @@
 
 static atomic_long_t nr_shared;
 
-/* Called from __tdx_hypercall() for unrecoverable failure */
-noinstr void __noreturn __tdx_hypercall_failed(void)
-{
-	instrumentation_begin();
-	panic("TDVMCALL failed. TDX module bug?");
-}
-
 #ifdef CONFIG_KVM_GUEST
 long tdx_kvm_hypercall(unsigned int nr, unsigned long p1, unsigned long p2,
 		       unsigned long p3, unsigned long p4)
@@ -62,17 +55,6 @@ long tdx_kvm_hypercall(unsigned int nr, unsigned long p1, unsigned long p2,
 EXPORT_SYMBOL_GPL(tdx_kvm_hypercall);
 #endif
 
-/*
- * Used for TDX guests to make calls directly to the TD module.  This
- * should only be used for calls that have no legitimate reason to fail
- * or where the kernel can not survive the call failing.
- */
-static inline void tdcall(u64 fn, struct tdx_module_args *args)
-{
-	if (__tdcall_ret(fn, args))
-		panic("TDCALL %lld failed (Buggy TDX module!)\n", fn);
-}
-
 /* Read TD-scoped metadata */
 static inline u64 tdg_vm_rd(u64 field, u64 *value)
 {
diff --git a/arch/x86/include/asm/shared/tdx.h b/arch/x86/include/asm/shared/tdx.h
index 70190ebc63ca..cbbc679d64a2 100644
--- a/arch/x86/include/asm/shared/tdx.h
+++ b/arch/x86/include/asm/shared/tdx.h
@@ -55,17 +55,6 @@
 #define TDX_R14		BIT(14)
 #define TDX_R15		BIT(15)
 
-/*
- * These registers are clobbered to hold arguments for each
- * TDVMCALL. They are safe to expose to the VMM.
- * Each bit in this mask represents a register ID. Bit field
- * details can be found in TDX GHCI specification, section
- * titled "TDCALL [TDG.VP.VMCALL] leaf".
- */
-#define TDVMCALL_EXPOSE_REGS_MASK	\
-	(TDX_RDX | TDX_RBX | TDX_RSI | TDX_RDI | TDX_R8  | TDX_R9  | \
-	 TDX_R10 | TDX_R11 | TDX_R12 | TDX_R13 | TDX_R14 | TDX_R15)
-
 /* TDX supported page sizes from the TDX module ABI. */
 #define TDX_PS_4K	0
 #define TDX_PS_2M	1
@@ -193,7 +182,7 @@
 })
 
 /*
- * Used in __tdcall*() to gather the input/output registers' values of the
+ * Used in __seamcall*() to gather the input/output registers' values of the
  * TDCALL instruction when requesting services from the TDX module. This is a
  * software only structure and not part of the TDX module/VMM ABI
  */
@@ -216,36 +205,6 @@ struct tdx_module_args {
 	u64 rsi;
 };
 
-/* Used to communicate with the TDX module */
-u64 __tdcall(u64 fn, struct tdx_module_args *args);
-u64 __tdcall_ret(u64 fn, struct tdx_module_args *args);
-u64 __tdcall_saved_ret(u64 fn, struct tdx_module_args *args);
-
-/* Used to request services from the VMM */
-u64 __tdx_hypercall(struct tdx_module_args *args);
-
-/*
- * Wrapper for standard use of __tdx_hypercall with no output aside from
- * return code.
- */
-static inline u64 _tdx_hypercall(u64 fn, u64 r12, u64 r13, u64 r14, u64 r15)
-{
-	struct tdx_module_args args = {
-		.r10 = TDX_HYPERCALL_STANDARD,
-		.r11 = fn,
-		.r12 = r12,
-		.r13 = r13,
-		.r14 = r14,
-		.r15 = r15,
-	};
-
-	return __tdx_hypercall(&args);
-}
-
-
-/* Called from __tdx_hypercall() for unrecoverable failure */
-void __noreturn __tdx_hypercall_failed(void);
-
 bool tdx_accept_memory(phys_addr_t start, phys_addr_t end);
 
 /*
diff --git a/arch/x86/virt/vmx/tdx/tdxcall.S b/arch/x86/virt/vmx/tdx/tdxcall.S
index 016a2a1ec1d6..7ad2fc6ba9c8 100644
--- a/arch/x86/virt/vmx/tdx/tdxcall.S
+++ b/arch/x86/virt/vmx/tdx/tdxcall.S
@@ -4,33 +4,28 @@
 #include <asm/asm.h>
 #include <asm/tdx.h>
 
-/*
- * TDCALL and SEAMCALL are supported in Binutils >= 2.36.
- */
-#define tdcall		.byte 0x66,0x0f,0x01,0xcc
+/* SEAMCALL is supported in Binutils >= 2.36 */
 #define seamcall	.byte 0x66,0x0f,0x01,0xcf
 
 /*
  * TDX_MODULE_CALL - common helper macro for both
  *                 TDCALL and SEAMCALL instructions.
  *
- * TDCALL   - used by TDX guests to make requests to the
- *            TDX module and hypercalls to the VMM.
  * SEAMCALL - used by TDX hosts to make requests to the
  *            TDX module.
  *
  *-------------------------------------------------------------------------
- * TDCALL/SEAMCALL ABI:
+ * SEAMCALL ABI:
  *-------------------------------------------------------------------------
  * Input Registers:
  *
- * RAX                        - TDCALL/SEAMCALL Leaf number.
- * RCX,RDX,RDI,RSI,RBX,R8-R15 - TDCALL/SEAMCALL Leaf specific input registers.
+ * RAX                        - SEAMCALL Leaf number.
+ * RCX,RDX,RDI,RSI,RBX,R8-R15 - SEAMCALL Leaf specific input registers.
  *
  * Output Registers:
  *
- * RAX                        - TDCALL/SEAMCALL instruction error code.
- * RCX,RDX,RDI,RSI,RBX,R8-R15 - TDCALL/SEAMCALL Leaf specific output registers.
+ * RAX                        - SEAMCALL instruction error code.
+ * RCX,RDX,RDI,RSI,RBX,R8-R15 - SEAMCALL Leaf specific output registers.
  *
  *-------------------------------------------------------------------------
  *
@@ -42,7 +37,7 @@
  * also tramples on RDI,RSI.  This isn't strictly true, see for example
  * TDH.EXPORT.MEM.
  */
-.macro TDX_MODULE_CALL host:req ret=0 saved=0
+.macro TDX_MODULE_CALL ret=0 saved=0
 	FRAME_BEGIN
 
 	/* Move Leaf ID to RAX */
@@ -85,7 +80,6 @@
 	movq	TDX_MODULE_rsi(%rsi), %rsi
 .endif	/* \saved */
 
-.if \host
 .Lseamcall\@:
 	seamcall
 	/*
@@ -100,9 +94,6 @@
 	 * it is from the Reserved status code class.
 	 */
 	jc .Lseamcall_vmfailinvalid\@
-.else
-	tdcall
-.endif
 
 .if \ret
 .if \saved
@@ -172,11 +163,9 @@
 	xorl %r15d, %r15d
 	xorl %ebx,  %ebx
 	xorl %edi,  %edi
-.endif	/* \ret && \host */
+.endif	/* \saved && \ret */
 
-.if \host
 .Lout\@:
-.endif
 
 .if \saved
 	/* Restore callee-saved GPRs as mandated by the x86_64 ABI */
@@ -190,7 +179,6 @@
 	FRAME_END
 	RET
 
-.if \host
 .Lseamcall_vmfailinvalid\@:
 	mov $TDX_SEAMCALL_VMFAILINVALID, %rax
 	jmp .Lseamcall_fail\@
@@ -215,6 +203,5 @@
 	jmp .Lout\@
 
 	_ASM_EXTABLE_FAULT(.Lseamcall\@, .Lseamcall_trap\@)
-.endif	/* \host */
 
 .endm
diff --git a/tools/objtool/noreturns.h b/tools/objtool/noreturns.h
index 0670cacf0734..1e82a96ba960 100644
--- a/tools/objtool/noreturns.h
+++ b/tools/objtool/noreturns.h
@@ -11,7 +11,6 @@ NORETURN(__kunit_abort)
 NORETURN(__module_put_and_kthread_exit)
 NORETURN(__reiserfs_panic)
 NORETURN(__stack_chk_fail)
-NORETURN(__tdx_hypercall_failed)
 NORETURN(__ubsan_handle_builtin_unreachable)
 NORETURN(arch_cpu_idle_dead)
 NORETURN(bch2_trans_in_restart_error)

---

## [22] Dave Hansen — 2024-05-17
*Subject: Re: [PATCH 00/20] x86/tdx: Rewrite TDCALL wrappers*

On 5/17/24 07:19, Kirill A. Shutemov wrote:
>  arch/x86/boot/compressed/tdx.c    |  32 +---
>  arch/x86/coco/tdx/tdcall.S        | 145 ++++++++++-----

I was going to grumble about this being a waste of time, but it looks
like this gives smaller binaries and less code.  Looks promising so far!

---

## [23] Dave Hansen — 2024-05-17
*Subject: Re: [PATCH 01/20] x86/tdx: Introduce tdvmcall_trampoline()*

On 5/17/24 07:19, Kirill A. Shutemov wrote:
> TDCALL calls are centralized into a few megawrappers that take the
> struct tdx_module_args as input. Most of the call sites only use a few

I agree that this is what the silly compiler does in practice.  But my
first preference for fixing it would just be an out-of-line memset() or
a pretty bare REP;MOV.

In other words, I think this as the foundational justification for the
rest of the series leaves a little to be desired.

---

## [24] Dave Hansen — 2024-05-17
*Subject: Re: [PATCH 03/20] x86/tdx: Convert port I/O handling to use new
 TDVMCALL macros*

On 5/17/24 07:19, Kirill A. Shutemov wrote:
>  static inline void tdx_io_out(int size, u16 port, u32 value)
>  {

I actually really like the self-documenting nature of the structures.  I
don't think it's a win if this is where the lines-of-code savings comes
from.

---

## [25] Dave Hansen — 2024-05-17
*Subject: Re: [PATCH 16/20] x86/tdx: Convert VP_INFO tdcall to use new
 TDCALL_5() macro*

On 5/17/24 07:19, Kirill A. Shutemov wrote:
> -	/*
> -	 * TDINFO TDX module call is used to get the TD execution environment

Why is the comment going away?

---

## [26] Dave Hansen — 2024-05-17
*Subject: Re: [PATCH 17/20] x86/tdx: Convert VM_RD/VM_WR tdcalls to use new
 TDCALL macros*

Let's say you're debugging tdg_vm_rd().  You suspect someone read the
spec wrong.  You pull up the spec:

	https://sr71.net/~dave/intel/tdg.vm.rd.png

On 5/17/24 07:19, Kirill A. Shutemov wrote:
>  static inline u64 tdg_vm_rd(u64 field, u64 *value)
>  {

RDX is assigned 'field'.  Makes sense based on the input operands.

> -	u64 ret;
> -

'value' is set to r8.  Also matches the spec.  It's obvious that this is
a 'two return values' pattern.

> -	return ret;

This is also obviously correct.

Compare that to:

> +	return TDCALL_1(TDG_VM_RD, 0, field, 0, 0, value);
>  }

Where it's 100% opaque which registers thing to into or that 'value' is
an output, not an input.

So, yeah, this is fewer lines of C code.  But it's *WAY* less
self-documenting.  It's harder to audit.  It's harder to understand and
it's more opaque.

While the goals here are laudable, I'm not a big fan of the end result.

---

## [27] Paolo Bonzini — 2024-05-17
*Subject: Re: [PATCH 02/20] x86/tdx: Add macros to generate TDVMCALL wrappers*

On 5/17/24 16:19, Kirill A. Shutemov wrote:
> Introduce a set of macros that allow to generate wrappers for TDVMCALL
> leafs. The macros uses tdvmcall_trmapoline() and provides SYSV-complaint

Not really SYSV-compliant, more like "The macros use asm() to call 
tdvmcall_trampoline with its custom parameter passing convention".

Paolo

---

## [28] Paolo Bonzini — 2024-05-17
*Subject: Re: [PATCH 01/20] x86/tdx: Introduce tdvmcall_trampoline()*

On 5/17/24 16:19, Kirill A. Shutemov wrote:
> The function will be used from inline assembly to handle most TDVMCALL
> cases.

Perhaps add that the calling convention is designed to allow using the 
asm constraints a/b/c/d/S/D and keep the asm blocks simpler?

Paolo

---

## [29] Paolo Bonzini — 2024-05-17
*Subject: Re: [PATCH 14/20] x86/tdx: Add macros to generate TDCALL wrappers*

On 5/17/24 16:19, Kirill A. Shutemov wrote:
> Introduce a set of macros that allow to generate wrappers for TDCALL
> leafs.

Can you explain in the commit message why you picked a different 
approach?  That is, a sequence of inlined movq instructions here vs. 
compiler-generated movqs + a trampoline for TDVMCALL.

Paolo

---

## [30] Paolo Bonzini — 2024-05-17
*Subject: Re: [PATCH 03/20] x86/tdx: Convert port I/O handling to use new
 TDVMCALL macros*

On 5/17/24 17:28, Dave Hansen wrote:
> On 5/17/24 07:19, Kirill A. Shutemov wrote:
>>   static inline void tdx_io_out(int size, u16 port, u32 value)

It's just a tradeoff.  For example someone could well have written

#define TDVMCALL_0(reason, a1, a2, a3, a4) \
   do { \
	struct tdx_module_args args = {
		.r10 = TDX_HYPERCALL_STANDARD,
		.r11 = reason,
		.r12 = a1,
		.r13 = a2,
		.r14 = a3,
		.r15 = a4,
	__tdx_hypercall(&args);
   } while(0)

even with the current __tdx_hypercall() implementation.

I agree that TDVMCALL_x is somewhat less legible; on the other hand it 
highlights that these TDVMCALLs all have a common convention for passing 
parameters / retrieving results, and reduces the potential for silly typos.

This is also why I asked about the different approaches for TDCALL vs. 
TDVMCALL.  Given that there are only a handful of appearances for 
tdvmcall_trampoline, maybe the best of both worlds is just to inline the 
whole thing?  This way the code in the macros matches the parameter 
passing convention of the GHCI.

Paolo

---

## [31] Kirill A. Shutemov — 2024-05-20
*Subject: Re: [PATCH 01/20] x86/tdx: Introduce tdvmcall_trampoline()*

On Fri, May 17, 2024 at 08:21:37AM -0700, Dave Hansen wrote:
> On 5/17/24 07:19, Kirill A. Shutemov wrote:
> > TDCALL calls are centralized into a few megawrappers that take the

See the patch below. Is it what you had in mind?

This patch saves ~2K of code, comparing to ~3K for my patchset:

add/remove: 0/0 grow/shrink: 1/17 up/down: 8/-2266 (-2258)

But it is considerably simpler.

 arch/x86/boot/compressed/tdx.c    |  32 ++++----
 arch/x86/coco/tdx/tdx-shared.c    |   3 +-
 arch/x86/coco/tdx/tdx.c           | 159 +++++++++++++++++++++-----------------
 arch/x86/hyperv/ivm.c             |  32 ++++----
 arch/x86/include/asm/shared/tdx.h |  25 ++++--
 5 files changed, 142 insertions(+), 109 deletions(-)

diff --git a/arch/x86/boot/compressed/tdx.c b/arch/x86/boot/compressed/tdx.c
index 8451d6a1030c..a6784a9153e4 100644
--- a/arch/x86/boot/compressed/tdx.c
+++ b/arch/x86/boot/compressed/tdx.c
@@ -18,13 +18,14 @@ void __tdx_hypercall_failed(void)
 
 static inline unsigned int tdx_io_in(int size, u16 port)
 {
-	struct tdx_module_args args = {
-		.r10 = TDX_HYPERCALL_STANDARD,
-		.r11 = hcall_func(EXIT_REASON_IO_INSTRUCTION),
-		.r12 = size,
-		.r13 = 0,
-		.r14 = port,
-	};
+	struct tdx_module_args args;
+
+	tdx_arg_init(&args);
+	args.r10 = TDX_HYPERCALL_STANDARD;
+	args.r11 = hcall_func(EXIT_REASON_IO_INSTRUCTION);
+	args.r12 = size;
+	args.r13 = 0;
+	args.r14 = port;
 
 	if (__tdx_hypercall(&args))
 		return UINT_MAX;
@@ -34,14 +35,15 @@ static inline unsigned int tdx_io_in(int size, u16 port)
 
 static inline void tdx_io_out(int size, u16 port, u32 value)
 {
-	struct tdx_module_args args = {
-		.r10 = TDX_HYPERCALL_STANDARD,
-		.r11 = hcall_func(EXIT_REASON_IO_INSTRUCTION),
-		.r12 = size,
-		.r13 = 1,
-		.r14 = port,
-		.r15 = value,
-	};
+	struct tdx_module_args args;
+
+	tdx_arg_init(&args);
+	args.r10 = TDX_HYPERCALL_STANDARD;
+	args.r11 = hcall_func(EXIT_REASON_IO_INSTRUCTION);
+	args.r12 = size;
+	args.r13 = 1;
+	args.r14 = port;
+	args.r15 = value;
 
 	__tdx_hypercall(&args);
 }
diff --git a/arch/x86/coco/tdx/tdx-shared.c b/arch/x86/coco/tdx/tdx-shared.c
index 1655aa56a0a5..b8d1b3d940d2 100644
--- a/arch/x86/coco/tdx/tdx-shared.c
+++ b/arch/x86/coco/tdx/tdx-shared.c
@@ -5,7 +5,7 @@ static unsigned long try_accept_one(phys_addr_t start, unsigned long len,
 				    enum pg_level pg_level)
 {
 	unsigned long accept_size = page_level_size(pg_level);
-	struct tdx_module_args args = {};
+	struct tdx_module_args args;
 	u8 page_size;
 
 	if (!IS_ALIGNED(start, accept_size))
@@ -34,6 +34,7 @@ static unsigned long try_accept_one(phys_addr_t start, unsigned long len,
 		return 0;
 	}
 
+	tdx_arg_init(&args);
 	args.rcx = start | page_size;
 	if (__tdcall(TDG_MEM_PAGE_ACCEPT, &args))
 		return 0;
diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index cadd583d6f62..e8bb8afe04a9 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -53,13 +53,14 @@ noinstr void __noreturn __tdx_hypercall_failed(void)
 long tdx_kvm_hypercall(unsigned int nr, unsigned long p1, unsigned long p2,
 		       unsigned long p3, unsigned long p4)
 {
-	struct tdx_module_args args = {
-		.r10 = nr,
-		.r11 = p1,
-		.r12 = p2,
-		.r13 = p3,
-		.r14 = p4,
-	};
+	struct tdx_module_args args;
+
+	tdx_arg_init(&args);
+	args.r10 = nr;
+	args.r11 = p1;
+	args.r12 = p2;
+	args.r13 = p3;
+	args.r14 = p4;
 
 	return __tdx_hypercall(&args);
 }
@@ -80,11 +81,12 @@ static inline void tdcall(u64 fn, struct tdx_module_args *args)
 /* Read TD-scoped metadata */
 static inline u64 tdg_vm_rd(u64 field, u64 *value)
 {
-	struct tdx_module_args args = {
-		.rdx = field,
-	};
+	struct tdx_module_args args;
 	u64 ret;
 
+	tdx_arg_init(&args);
+	args.rdx = field,
+
 	ret = __tdcall_ret(TDG_VM_RD, &args);
 	*value = args.r8;
 
@@ -94,11 +96,12 @@ static inline u64 tdg_vm_rd(u64 field, u64 *value)
 /* Write TD-scoped metadata */
 static inline u64 tdg_vm_wr(u64 field, u64 value, u64 mask)
 {
-	struct tdx_module_args args = {
-		.rdx = field,
-		.r8 = value,
-		.r9 = mask,
-	};
+	struct tdx_module_args args;
+
+	tdx_arg_init(&args);
+	args.rdx = field;
+	args.r8 = value;
+	args.r9 = mask;
 
 	return __tdcall(TDG_VM_WR, &args);
 }
@@ -119,13 +122,14 @@ static inline u64 tdg_vm_wr(u64 field, u64 value, u64 mask)
  */
 int tdx_mcall_get_report0(u8 *reportdata, u8 *tdreport)
 {
-	struct tdx_module_args args = {
-		.rcx = virt_to_phys(tdreport),
-		.rdx = virt_to_phys(reportdata),
-		.r8 = TDREPORT_SUBTYPE_0,
-	};
+	struct tdx_module_args args;
 	u64 ret;
 
+	tdx_arg_init(&args);
+	args.rcx = virt_to_phys(tdreport);
+	args.rdx = virt_to_phys(reportdata);
+	args.r8 = TDREPORT_SUBTYPE_0;
+
 	ret = __tdcall(TDG_MR_REPORT, &args);
 	if (ret) {
 		if (TDCALL_RETURN_CODE(ret) == TDCALL_INVALID_OPERAND)
@@ -160,11 +164,7 @@ EXPORT_SYMBOL_GPL(tdx_hcall_get_quote);
 
 static void __noreturn tdx_panic(const char *msg)
 {
-	struct tdx_module_args args = {
-		.r10 = TDX_HYPERCALL_STANDARD,
-		.r11 = TDVMCALL_REPORT_FATAL_ERROR,
-		.r12 = 0, /* Error code: 0 is Panic */
-	};
+	struct tdx_module_args args;
 	union {
 		/* Define register order according to the GHCI */
 		struct { u64 r14, r15, rbx, rdi, rsi, r8, r9, rdx; };
@@ -175,6 +175,11 @@ static void __noreturn tdx_panic(const char *msg)
 	/* VMM assumes '\0' in byte 65, if the message took all 64 bytes */
 	strtomem_pad(message.str, msg, '\0');
 
+	tdx_arg_init(&args);
+	args.r10 = TDX_HYPERCALL_STANDARD;
+	args.r11 = TDVMCALL_REPORT_FATAL_ERROR;
+	args.r12 = 0; /* Error code: 0 is Panic */
+
 	args.r8  = message.r8;
 	args.r9  = message.r9;
 	args.r14 = message.r14;
@@ -277,10 +282,12 @@ static void enable_cpu_topology_enumeration(void)
 
 static void tdx_setup(u64 *cc_mask)
 {
-	struct tdx_module_args args = {};
+	struct tdx_module_args args;
 	unsigned int gpa_width;
 	u64 td_attr;
 
+	tdx_arg_init(&args);
+
 	/*
 	 * TDINFO TDX module call is used to get the TD execution environment
 	 * information like GPA width, number of available vcpus, debug mode
@@ -356,11 +363,12 @@ static int ve_instr_len(struct ve_info *ve)
 
 static u64 __cpuidle __halt(const bool irq_disabled)
 {
-	struct tdx_module_args args = {
-		.r10 = TDX_HYPERCALL_STANDARD,
-		.r11 = hcall_func(EXIT_REASON_HLT),
-		.r12 = irq_disabled,
-	};
+	struct tdx_module_args args;
+
+	tdx_arg_init(&args);
+	args.r10 = TDX_HYPERCALL_STANDARD;
+	args.r11 = hcall_func(EXIT_REASON_HLT);
+	args.r12 = irq_disabled;
 
 	/*
 	 * Emulate HLT operation via hypercall. More info about ABI
@@ -400,11 +408,12 @@ void __cpuidle tdx_safe_halt(void)
 
 static int read_msr(struct pt_regs *regs, struct ve_info *ve)
 {
-	struct tdx_module_args args = {
-		.r10 = TDX_HYPERCALL_STANDARD,
-		.r11 = hcall_func(EXIT_REASON_MSR_READ),
-		.r12 = regs->cx,
-	};
+	struct tdx_module_args args;
+
+	tdx_arg_init(&args);
+	args.r10 = TDX_HYPERCALL_STANDARD;
+	args.r11 = hcall_func(EXIT_REASON_MSR_READ);
+	args.r12 = regs->cx;
 
 	/*
 	 * Emulate the MSR read via hypercall. More info about ABI
@@ -421,12 +430,13 @@ static int read_msr(struct pt_regs *regs, struct ve_info *ve)
 
 static int write_msr(struct pt_regs *regs, struct ve_info *ve)
 {
-	struct tdx_module_args args = {
-		.r10 = TDX_HYPERCALL_STANDARD,
-		.r11 = hcall_func(EXIT_REASON_MSR_WRITE),
-		.r12 = regs->cx,
-		.r13 = (u64)regs->dx << 32 | regs->ax,
-	};
+	struct tdx_module_args args;
+
+	tdx_arg_init(&args);
+	args.r10 = TDX_HYPERCALL_STANDARD;
+	args.r11 = hcall_func(EXIT_REASON_MSR_WRITE);
+	args.r12 = regs->cx;
+	args.r13 = (u64)regs->dx << 32 | regs->ax;
 
 	/*
 	 * Emulate the MSR write via hypercall. More info about ABI
@@ -441,12 +451,13 @@ static int write_msr(struct pt_regs *regs, struct ve_info *ve)
 
 static int handle_cpuid(struct pt_regs *regs, struct ve_info *ve)
 {
-	struct tdx_module_args args = {
-		.r10 = TDX_HYPERCALL_STANDARD,
-		.r11 = hcall_func(EXIT_REASON_CPUID),
-		.r12 = regs->ax,
-		.r13 = regs->cx,
-	};
+	struct tdx_module_args args;
+
+	tdx_arg_init(&args);
+	args.r10 = TDX_HYPERCALL_STANDARD;
+	args.r11 = hcall_func(EXIT_REASON_CPUID);
+	args.r12 = regs->ax;
+	args.r13 = regs->cx;
 
 	/*
 	 * Only allow VMM to control range reserved for hypervisor
@@ -483,14 +494,15 @@ static int handle_cpuid(struct pt_regs *regs, struct ve_info *ve)
 
 static bool mmio_read(int size, unsigned long addr, unsigned long *val)
 {
-	struct tdx_module_args args = {
-		.r10 = TDX_HYPERCALL_STANDARD,
-		.r11 = hcall_func(EXIT_REASON_EPT_VIOLATION),
-		.r12 = size,
-		.r13 = EPT_READ,
-		.r14 = addr,
-		.r15 = *val,
-	};
+	struct tdx_module_args args;
+
+	tdx_arg_init(&args);
+	args.r10 = TDX_HYPERCALL_STANDARD;
+	args.r11 = hcall_func(EXIT_REASON_EPT_VIOLATION);
+	args.r12 = size;
+	args.r13 = EPT_READ;
+	args.r14 = addr;
+	args.r15 = *val;
 
 	if (__tdx_hypercall(&args))
 		return false;
@@ -612,16 +624,17 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 
 static bool handle_in(struct pt_regs *regs, int size, int port)
 {
-	struct tdx_module_args args = {
-		.r10 = TDX_HYPERCALL_STANDARD,
-		.r11 = hcall_func(EXIT_REASON_IO_INSTRUCTION),
-		.r12 = size,
-		.r13 = PORT_READ,
-		.r14 = port,
-	};
+	struct tdx_module_args args;
 	u64 mask = GENMASK(BITS_PER_BYTE * size, 0);
 	bool success;
 
+	tdx_arg_init(&args);
+	args.r10 = TDX_HYPERCALL_STANDARD;
+	args.r11 = hcall_func(EXIT_REASON_IO_INSTRUCTION);
+	args.r12 = size;
+	args.r13 = PORT_READ;
+	args.r14 = port;
+
 	/*
 	 * Emulate the I/O read via hypercall. More info about ABI can be found
 	 * in TDX Guest-Host-Communication Interface (GHCI) section titled
@@ -706,7 +719,9 @@ __init bool tdx_early_handle_ve(struct pt_regs *regs)
 
 void tdx_get_ve_info(struct ve_info *ve)
 {
-	struct tdx_module_args args = {};
+	struct tdx_module_args args;
+
+	tdx_arg_init(&args);
 
 	/*
 	 * Called during #VE handling to retrieve the #VE info from the
@@ -849,14 +864,16 @@ static bool tdx_map_gpa(phys_addr_t start, phys_addr_t end, bool enc)
 	}
 
 	while (retry_count < max_retries_per_page) {
-		struct tdx_module_args args = {
-			.r10 = TDX_HYPERCALL_STANDARD,
-			.r11 = TDVMCALL_MAP_GPA,
-			.r12 = start,
-			.r13 = end - start };
-
+		struct tdx_module_args args;
 		u64 map_fail_paddr;
-		u64 ret = __tdx_hypercall(&args);
+		u64 ret;
+
+		tdx_arg_init(&args);
+		args.r10 = TDX_HYPERCALL_STANDARD;
+		args.r11 = TDVMCALL_MAP_GPA;
+		args.r12 = start;
+		args.r13 = end - start;
+		ret = __tdx_hypercall(&args);
 
 		if (ret != TDVMCALL_STATUS_RETRY)
 			return !ret;
diff --git a/arch/x86/hyperv/ivm.c b/arch/x86/hyperv/ivm.c
index b4a851d27c7c..38560b006cdf 100644
--- a/arch/x86/hyperv/ivm.c
+++ b/arch/x86/hyperv/ivm.c
@@ -385,27 +385,30 @@ static inline void hv_ghcb_msr_read(u64 msr, u64 *value) {}
 #ifdef CONFIG_INTEL_TDX_GUEST
 static void hv_tdx_msr_write(u64 msr, u64 val)
 {
-	struct tdx_module_args args = {
-		.r10 = TDX_HYPERCALL_STANDARD,
-		.r11 = EXIT_REASON_MSR_WRITE,
-		.r12 = msr,
-		.r13 = val,
-	};
+	struct tdx_module_args args;
+	u64 ret;
 
-	u64 ret = __tdx_hypercall(&args);
+	args.r10 = TDX_HYPERCALL_STANDARD;
+	args.r11 = EXIT_REASON_MSR_WRITE;
+	args.r12 = msr;
+	args.r13 = val;
+
+	ret = __tdx_hypercall(&args);
 
 	WARN_ONCE(ret, "Failed to emulate MSR write: %lld\n", ret);
 }
 
 static void hv_tdx_msr_read(u64 msr, u64 *val)
 {
-	struct tdx_module_args args = {
-		.r10 = TDX_HYPERCALL_STANDARD,
-		.r11 = EXIT_REASON_MSR_READ,
-		.r12 = msr,
-	};
+	struct tdx_module_args args;
+	u64 ret;
 
-	u64 ret = __tdx_hypercall(&args);
+	tdx_arg_init(&args);
+	args.r10 = TDX_HYPERCALL_STANDARD;
+	args.r11 = EXIT_REASON_MSR_READ;
+	args.r12 = msr;
+
+	ret = __tdx_hypercall(&args);
 
 	if (WARN_ONCE(ret, "Failed to emulate MSR read: %lld\n", ret))
 		*val = 0;
@@ -415,8 +418,9 @@ static void hv_tdx_msr_read(u64 msr, u64 *val)
 
 u64 hv_tdx_hypercall(u64 control, u64 param1, u64 param2)
 {
-	struct tdx_module_args args = { };
+	struct tdx_module_args args;
 
+	tdx_arg_init(&args);
 	args.r10 = control;
 	args.rdx = param1;
 	args.r8  = param2;
diff --git a/arch/x86/include/asm/shared/tdx.h b/arch/x86/include/asm/shared/tdx.h
index 89f7fcade8ae..fc3082f050dc 100644
--- a/arch/x86/include/asm/shared/tdx.h
+++ b/arch/x86/include/asm/shared/tdx.h
@@ -100,6 +100,14 @@ struct tdx_module_args {
 	u64 rsi;
 };
 
+static __always_inline void tdx_arg_init(struct tdx_module_args *args)
+{
+	asm ("rep stosb"
+	     : "+D" (args)
+	     : "c" (sizeof(*args)), "a" (0)
+	     : "memory");
+}
+
 /* Used to communicate with the TDX module */
 u64 __tdcall(u64 fn, struct tdx_module_args *args);
 u64 __tdcall_ret(u64 fn, struct tdx_module_args *args);
@@ -114,14 +122,15 @@ u64 __tdx_hypercall(struct tdx_module_args *args);
  */
 static inline u64 _tdx_hypercall(u64 fn, u64 r12, u64 r13, u64 r14, u64 r15)
 {
-	struct tdx_module_args args = {
-		.r10 = TDX_HYPERCALL_STANDARD,
-		.r11 = fn,
-		.r12 = r12,
-		.r13 = r13,
-		.r14 = r14,
-		.r15 = r15,
-	};
+	struct tdx_module_args args;
+
+	tdx_arg_init(&args);
+	args.r10 = TDX_HYPERCALL_STANDARD;
+	args.r11 = fn;
+	args.r12 = r12;
+	args.r13 = r13;
+	args.r14 = r14;
+	args.r15 = r15;
 
 	return __tdx_hypercall(&args);
 }

---

## [32] Kirill A. Shutemov — 2024-05-20
*Subject: Re: [PATCH 01/20] x86/tdx: Introduce tdvmcall_trampoline()*

On Fri, May 17, 2024 at 07:02:25PM +0200, Paolo Bonzini wrote:
> On 5/17/24 16:19, Kirill A. Shutemov wrote:
> > The function will be used from inline assembly to handle most TDVMCALL

Sure.

---

## [33] Kirill A. Shutemov — 2024-05-20
*Subject: Re: [PATCH 02/20] x86/tdx: Add macros to generate TDVMCALL wrappers*

On Fri, May 17, 2024 at 06:54:15PM +0200, Paolo Bonzini wrote:
> On 5/17/24 16:19, Kirill A. Shutemov wrote:
> > Introduce a set of macros that allow to generate wrappers for TDVMCALL

Sounds better, thanks.

---

## [34] Kirill A. Shutemov — 2024-05-20
*Subject: Re: [PATCH 16/20] x86/tdx: Convert VP_INFO tdcall to use new
 TDCALL_5() macro*

On Fri, May 17, 2024 at 08:57:10AM -0700, Dave Hansen wrote:
> On 5/17/24 07:19, Kirill A. Shutemov wrote:
> > -	/*

By mistake. Will fix.

---

## [35] Huang, Kai — 2024-05-20
*Subject: Re: [PATCH 00/20] x86/tdx: Rewrite TDCALL wrappers*

On Fri, 2024-05-17 at 08:18 -0700, Dave Hansen wrote:
> On 5/17/24 07:19, Kirill A. Shutemov wrote:
> >  arch/x86/boot/compressed/tdx.c    |  32 +---

I'll start to work on the SEAMCALL part too.  Thanks Kirill for the work.

---

## [36] Dave Hansen — 2024-05-20
*Subject: Re: [PATCH 01/20] x86/tdx: Introduce tdvmcall_trampoline()*

On 5/20/24 03:32, Kirill A. Shutemov wrote:
>> In other words, I think this as the foundational justification for the
>> rest of the series leaves a little to be desired.

The diffstat is a bit misleading because those extra lines really add
very little complexity. The only real risk is that folks end up leaving
the args structure uninitialized, but there are a number of ways to
mitigate that risk.

> +static __always_inline void tdx_arg_init(struct tdx_module_args *args)
> +{

There are a bunch of ways to do this.  This one certainly isn't _bad_,
but I'd be open to doing it other ways if folks have more ideas.

Either way, I very much prefer this approach to adding a bunch more
assembly and making things less self-documenting.  I also suspect you
can get some more text size shrinkage from selectively uninlining a few
things.

---

## [37] Wei Liu — 2024-05-28
*Subject: Re: [PATCH 05/20] x86/tdx: Convert MSR read handling to use new
 TDVMCALL_1()*

On Fri, May 17, 2024 at 05:19:23PM +0300, Kirill A. Shutemov wrote:
> Use newly introduced TDVMCALL_1() instead of __tdx_hypercall() to handle
> MSR read emulation.

Acked-by: Wei Liu <wei.liu@kernel.org>

---

## [38] Wei Liu — 2024-05-28
*Subject: Re: [PATCH 06/20] x86/tdx: Convert MSR write handling to use new
 TDVMCALL_0()*

On Fri, May 17, 2024 at 05:19:24PM +0300, Kirill A. Shutemov wrote:
> Use newly introduced TDVMCALL_0() instead of __tdx_hypercall() to handle
> MSR write emulation.

Acked-by: Wei Liu <wei.liu@kernel.org>

---
