---
title: 'x86/vmware: Hypercall refactoring and improved guest support'
date: 2026-03-07
last_reply: 2026-05-18
message_count: 13
participants: ['Alexey Makhalov', 'kernel test robot']
---

## [1] Alexey Makhalov — 2026-03-07

This series improves VMware guest support on x86 by refactoring the
hypercall infrastructure and adding better crash diagnostics, along
with encrypted guest support for the steal time clock.

The first patch introduces a common vmware_hypercall() backend selected
via static calls. It consolidates the existing hypercall mechanisms
(backdoor, VMCALL/VMMCALL, and TDX) behind a single interface and
selects the optimal implementation at boot. This reduces duplication
and simplifies future extensions.

Building on top of the new hypercall infrastructure, the next two
patches improve post-mortem debugging of VMware guests. They export
panic information to the hypervisor by dumping kernel messages to the
VM vmware.log on the host and explicitly reporting guest crash event
to the hypervisor.

The final patch adds support for encrypted guests by ensuring that the
shared memory used for the steal time clock is mapped as decrypted
before being shared with the hypervisor. This enables steal time
accounting to function correctly when guest memory encryption is
enabled.

Patch overview:

1. x86/vmware: Introduce common vmware_hypercall

   * Consolidate hypercall implementations behind a common API
   * Select backend via static_call at boot

2. x86/vmware: Log kmsg dump on panic

   * Register a kmsg dumper
   * Export panic logs to the host

3. x86/vmware: Report guest crash to the hypervisor

   * Register a panic notifier
   * Notify the hypervisor about guest crashes

4. x86/vmware: Support steal time clock for encrypted guests

   * Mark shared steal time memory as decrypted early in boot


Alexey Makhalov (4):
  x86/vmware: Introduce common vmware_hypercall()
  x86/vmware: Log kmsg dump on panic
  x86/vmware: Report guest crash to the hypervisor
  x86/vmware: Support steal time clock for encrypted guests

 arch/x86/include/asm/vmware.h | 276 ++++++++------------
 arch/x86/kernel/cpu/vmware.c  | 470 +++++++++++++++++++++++++---------
 2 files changed, 463 insertions(+), 283 deletions(-)

---

## [2] Alexey Makhalov — 2026-03-07
*Subject: [PATCH 1/4] x86/vmware: Introduce common vmware_hypercall()*

Introduce vmware_hypercall(), a unified low-bandwidth VMware hypercall
API, and convert the static inlines vmware_hypercallX() family into thin
wrappers on top of it.

vmware_hypercall() is implemented as a static call with four backend
implementations: backdoor, vmcall, vmmcall, and tdxcall. All share the
same logical API but differ in their underlying register mappings.

By updating the static call target early during boot, before the first
hypercall is issued, the !alternatives_patched case no longer needs to
be handled. This allows removal of vmware_hypercall_slow().

The new API implements the widest practical hypercall use case: up to
six input and six output arguments. While this may be slightly less
efficient due to clobbering all six registers and moving unused
arguments - it avoids subtle ABI issues, including cases where other
hypervisors implementing VMware hypercalls corrupt registers.
See QEMU issue #3293 ("vmmouse driver corrupts upper 32 bits of
registers on x86-64") for an example of such behavior.

Additionally, enhance the VMware hypercall ABI documentation in
<asm/vmware.h>.

Link: https://gitlab.com/qemu-project/qemu/-/issues/3293
Suggested-by: Linus Torvalds <torvalds@linux-foundation.org>
Signed-off-by: Alexey Makhalov <alexey.makhalov@broadcom.com>
---
 arch/x86/include/asm/vmware.h | 274 ++++++++++++++-------------------
 arch/x86/kernel/cpu/vmware.c  | 276 +++++++++++++++++++---------------
 2 files changed, 267 insertions(+), 283 deletions(-)

diff --git a/arch/x86/include/asm/vmware.h b/arch/x86/include/asm/vmware.h
index 4220dae14a2d..6a084e088b30 100644
--- a/arch/x86/include/asm/vmware.h
+++ b/arch/x86/include/asm/vmware.h
@@ -3,48 +3,84 @@
 #define _ASM_X86_VMWARE_H
 
 #include <asm/cpufeatures.h>
-#include <asm/alternative.h>
 #include <linux/stringify.h>
+#include <linux/static_call.h>
 
 /*
  * VMware hypercall ABI.
  *
- * - Low bandwidth (LB) hypercalls (I/O port based, vmcall and vmmcall)
- * have up to 6 input and 6 output arguments passed and returned using
- * registers: %eax (arg0), %ebx (arg1), %ecx (arg2), %edx (arg3),
- * %esi (arg4), %edi (arg5).
- * The following input arguments must be initialized by the caller:
- * arg0 - VMWARE_HYPERVISOR_MAGIC
- * arg2 - Hypercall command
- * arg3 bits [15:0] - Port number, LB and direction flags
+ * - Low bandwidth (LB) hypercalls: I/O port based (aka backdoor), vmcall and
+ * vmmcall have up to 6 input and 6 output on registers arguments, with the
+ * register mapping:
+ *  +------+----------------------------------------+-----------------+
+ *  | Reg  | Input argument                         | Output argument |
+ *  +======+========================================+=================+
+ *  | %eax | VMWARE_HYPERVISOR_MAGIC                | out0            |
+ *  +------+----------------------------------------+-----------------+
+ *  | %ebx | (in1)                                  | out1            |
+ *  +------+----------------------------------------+-----------------+
+ *  | %ecx | (cmd) - Hypercall command              | out2            |
+ *  +------+----------------------------------------+-----------------+
+ *  | %edx | Bits [15:0] - Port number for backdoor | out3            |
+ *  |      |               Zero for vmcall/vmmcall  |                 |
+ *  |      | Bits [31:16] - (in3)                   |                 |
+ *  +------+----------------------------------------+-----------------+
+ *  | %esi | (in4)                                  | out4            |
+ *  +------+----------------------------------------+-----------------+
+ *  | %edi | (in5)                                  | out5            |
+ *  +------+----------------------------------------+-----------------+
  *
- * - Low bandwidth TDX hypercalls (x86_64 only) are similar to LB
- * hypercalls. They also have up to 6 input and 6 output on registers
- * arguments, with different argument to register mapping:
- * %r12 (arg0), %rbx (arg1), %r13 (arg2), %rdx (arg3),
- * %rsi (arg4), %rdi (arg5).
+ * - Low bandwidth TDX hypercalls (x86_64 only) are similar to LB hypercalls.
+ * They also have up to 6 input and 6 output on registers arguments, with
+ * different argument to register mapping:
+ *  +------+----------------------------------------+-----------------+
+ *  | Reg  | Input argument                         | Output argument |
+ *  +======+========================================+=================+
+ *  | %r12 | VMWARE_HYPERVISOR_MAGIC                | out0            |
+ *  +------+----------------------------------------+-----------------+
+ *  | %ebx | (in1)                                  | out1            |
+ *  +------+----------------------------------------+-----------------+
+ *  | %r13 | (cmd) - Hypercall command              | out2            |
+ *  +------+----------------------------------------+-----------------+
+ *  | %edx | Bits [15:0] - Must be zero             | out3            |
+ *  |      | Bits [31:16] - (in3)                   |                 |
+ *  +------+----------------------------------------+-----------------+
+ *  | %esi | (in4)                                  | out4            |
+ *  +------+----------------------------------------+-----------------+
+ *  | %edi | (in5)                                  | out5            |
+ *  +------+----------------------------------------+-----------------+
  *
- * - High bandwidth (HB) hypercalls are I/O port based only. They have
- * up to 7 input and 7 output arguments passed and returned using
- * registers: %eax (arg0), %ebx (arg1), %ecx (arg2), %edx (arg3),
- * %esi (arg4), %edi (arg5), %ebp (arg6).
- * The following input arguments must be initialized by the caller:
- * arg0 - VMWARE_HYPERVISOR_MAGIC
- * arg1 - Hypercall command
- * arg3 bits [15:0] - Port number, HB and direction flags
+ * - High bandwidth (HB) hypercalls are I/O port based only. They have up to 7
+ * input and 7 output on reegister arguments with the following mapping:
+ *  +------+----------------------------------------+-----------------+
+ *  | Reg  | Input argument                         | Output argument |
+ *  +======+========================================+=================+
+ *  | %eax | VMWARE_HYPERVISOR_MAGIC                | out0            |
+ *  +------+----------------------------------------+-----------------+
+ *  | %ebx | (cmd) - Hypercall command              | out1            |
+ *  +------+----------------------------------------+-----------------+
+ *  | %ebx | (in2)                                  | out2            |
+ *  +------+----------------------------------------+-----------------+
+ *  | %edx | Bits [15:0] - Port number and HB flag  | out3            |
+ *  |      | Bits [31:16] - (in3)                   |                 |
+ *  +------+----------------------------------------+-----------------+
+ *  | %esi | (in4)                                  | out4            |
+ *  +------+----------------------------------------+-----------------+
+ *  | %edi | (in5)                                  | out5            |
+ *  +------+----------------------------------------+-----------------+
+ *  | %ebp | (in6)                                  | out6            |
+ *  +------+----------------------------------------+-----------------+
  *
- * For compatibility purposes, x86_64 systems use only lower 32 bits
- * for input and output arguments.
+ * For compatibility purposes, x86_64 systems use only lower 32 bits for input
+ * and output arguments.
  *
- * The hypercall definitions differ in the low word of the %edx (arg3)
- * in the following way: the old I/O port based interface uses the port
- * number to distinguish between high- and low bandwidth versions, and
- * uses IN/OUT instructions to define transfer direction.
+ * The hypercall definitions differ in the low word of the %edx (arg3) in the
+ * following way: the old I/O port based interface uses the port number, the
+ * bandwidth mode flag, and uses IN/OUT instructions to define transfer
+ * direction.
  *
- * The new vmcall interface instead uses a set of flags to select
- * bandwidth mode and transfer direction. The flags should be loaded
- * into arg3 by any user and are automatically replaced by the port
- * number if the I/O port method is used.
+ * The new vmcall interface instead uses a set of flags to select bandwidth
+ * mode and transfer direction.
  */
 
 #define VMWARE_HYPERVISOR_HB		BIT(0)
@@ -70,103 +106,64 @@
 #define CPUID_VMWARE_FEATURES_ECX_VMMCALL	BIT(0)
 #define CPUID_VMWARE_FEATURES_ECX_VMCALL	BIT(1)
 
-extern unsigned long vmware_hypercall_slow(unsigned long cmd,
-					   unsigned long in1, unsigned long in3,
-					   unsigned long in4, unsigned long in5,
-					   u32 *out1, u32 *out2, u32 *out3,
-					   u32 *out4, u32 *out5);
-
 #define VMWARE_TDX_VENDOR_LEAF 0x1af7e4909ULL
 #define VMWARE_TDX_HCALL_FUNC  1
 
-extern unsigned long vmware_tdx_hypercall(unsigned long cmd,
-					  unsigned long in1, unsigned long in3,
-					  unsigned long in4, unsigned long in5,
-					  u32 *out1, u32 *out2, u32 *out3,
-					  u32 *out4, u32 *out5);
+unsigned long dummy_vmware_hypercall(unsigned long cmd,
+				     unsigned long in1, unsigned long in3,
+				     unsigned long in4, unsigned long in5,
+				     u32 *out1, u32 *out2, u32 *out3,
+				     u32 *out4, u32 *out5);
 
 /*
- * The low bandwidth call. The low word of %edx is presumed to have OUT bit
- * set. The high word of %edx may contain input data from the caller.
+ * Low bandwidth (LB) VMware hypercall.
+ *
+ * It is backed by the backdoor, vmcall, vmmcall or tdx call implementation.
+ *
+ * Use inX/outX arguments naming as the register mappings vary between
+ * different implementations. See VMware hypercall ABI above.
+ * These 10 arguments could be nicely wrapped in in/out structures, but it
+ * will introduce unnecessary structs copy in vmware_tdx_hypercall().
+ *
+ * NOTE:
+ * Do not merge vmware_{backdoor,vmcall,vmmcall}_hypercall implementations
+ * using alternative instructions. Such patching mechanism can not be used
+ * in vmware_hypercall path, as the first hypercall will be called much
+ * before the apply_alternatives(). See vmware_platform_setup().
  */
-#define VMWARE_HYPERCALL					\
-	ALTERNATIVE_2("movw %[port], %%dx\n\t"			\
-		      "inl (%%dx), %%eax",			\
-		      "vmcall", X86_FEATURE_VMCALL,		\
-		      "vmmcall", X86_FEATURE_VMW_VMMCALL)
+DECLARE_STATIC_CALL(vmware_hypercall, dummy_vmware_hypercall);
 
+/*
+ * Set of commonly used vmware_hypercallX functions - wrappers on top of the
+ * vmware_hypercall.
+ */
 static inline
 unsigned long vmware_hypercall1(unsigned long cmd, unsigned long in1)
 {
-	unsigned long out0;
-
-	if (cpu_feature_enabled(X86_FEATURE_TDX_GUEST))
-		return vmware_tdx_hypercall(cmd, in1, 0, 0, 0,
-					    NULL, NULL, NULL, NULL, NULL);
-
-	if (unlikely(!alternatives_patched) && !__is_defined(MODULE))
-		return vmware_hypercall_slow(cmd, in1, 0, 0, 0,
-					     NULL, NULL, NULL, NULL, NULL);
+	u32 out1, out2, out3, out4, out5;
 
-	asm_inline volatile (VMWARE_HYPERCALL
-		: "=a" (out0)
-		: [port] "i" (VMWARE_HYPERVISOR_PORT),
-		  "a" (VMWARE_HYPERVISOR_MAGIC),
-		  "b" (in1),
-		  "c" (cmd),
-		  "d" (0)
-		: "cc", "memory");
-	return out0;
+	return static_call_mod(vmware_hypercall)(cmd, in1, 0, 0, 0,
+			       &out1, &out2, &out3, &out4, &out5);
 }
 
 static inline
 unsigned long vmware_hypercall3(unsigned long cmd, unsigned long in1,
 				u32 *out1, u32 *out2)
 {
-	unsigned long out0;
-
-	if (cpu_feature_enabled(X86_FEATURE_TDX_GUEST))
-		return vmware_tdx_hypercall(cmd, in1, 0, 0, 0,
-					    out1, out2, NULL, NULL, NULL);
-
-	if (unlikely(!alternatives_patched) && !__is_defined(MODULE))
-		return vmware_hypercall_slow(cmd, in1, 0, 0, 0,
-					     out1, out2, NULL, NULL, NULL);
+	u32 out3, out4, out5;
 
-	asm_inline volatile (VMWARE_HYPERCALL
-		: "=a" (out0), "=b" (*out1), "=c" (*out2)
-		: [port] "i" (VMWARE_HYPERVISOR_PORT),
-		  "a" (VMWARE_HYPERVISOR_MAGIC),
-		  "b" (in1),
-		  "c" (cmd),
-		  "d" (0)
-		: "di", "si", "cc", "memory");
-	return out0;
+	return static_call_mod(vmware_hypercall)(cmd, in1, 0, 0, 0,
+			       out1, out2, &out3, &out4, &out5);
 }
 
 static inline
 unsigned long vmware_hypercall4(unsigned long cmd, unsigned long in1,
 				u32 *out1, u32 *out2, u32 *out3)
 {
-	unsigned long out0;
-
-	if (cpu_feature_enabled(X86_FEATURE_TDX_GUEST))
-		return vmware_tdx_hypercall(cmd, in1, 0, 0, 0,
-					    out1, out2, out3, NULL, NULL);
-
-	if (unlikely(!alternatives_patched) && !__is_defined(MODULE))
-		return vmware_hypercall_slow(cmd, in1, 0, 0, 0,
-					     out1, out2, out3, NULL, NULL);
+	u32 out4, out5;
 
-	asm_inline volatile (VMWARE_HYPERCALL
-		: "=a" (out0), "=b" (*out1), "=c" (*out2), "=d" (*out3)
-		: [port] "i" (VMWARE_HYPERVISOR_PORT),
-		  "a" (VMWARE_HYPERVISOR_MAGIC),
-		  "b" (in1),
-		  "c" (cmd),
-		  "d" (0)
-		: "di", "si", "cc", "memory");
-	return out0;
+	return static_call_mod(vmware_hypercall)(cmd, in1, 0, 0, 0,
+			       out1, out2, out3, &out4, &out5);
 }
 
 static inline
@@ -174,27 +171,10 @@ unsigned long vmware_hypercall5(unsigned long cmd, unsigned long in1,
 				unsigned long in3, unsigned long in4,
 				unsigned long in5, u32 *out2)
 {
-	unsigned long out0;
-
-	if (cpu_feature_enabled(X86_FEATURE_TDX_GUEST))
-		return vmware_tdx_hypercall(cmd, in1, in3, in4, in5,
-					    NULL, out2, NULL, NULL, NULL);
+	u32 out1, out3, out4, out5;
 
-	if (unlikely(!alternatives_patched) && !__is_defined(MODULE))
-		return vmware_hypercall_slow(cmd, in1, in3, in4, in5,
-					     NULL, out2, NULL, NULL, NULL);
-
-	asm_inline volatile (VMWARE_HYPERCALL
-		: "=a" (out0), "=c" (*out2)
-		: [port] "i" (VMWARE_HYPERVISOR_PORT),
-		  "a" (VMWARE_HYPERVISOR_MAGIC),
-		  "b" (in1),
-		  "c" (cmd),
-		  "d" (in3),
-		  "S" (in4),
-		  "D" (in5)
-		: "cc", "memory");
-	return out0;
+	return static_call_mod(vmware_hypercall)(cmd, in1, in3, in4, in5,
+			       &out1, out2, &out3, &out4, &out5);
 }
 
 static inline
@@ -202,26 +182,10 @@ unsigned long vmware_hypercall6(unsigned long cmd, unsigned long in1,
 				unsigned long in3, u32 *out2,
 				u32 *out3, u32 *out4, u32 *out5)
 {
-	unsigned long out0;
-
-	if (cpu_feature_enabled(X86_FEATURE_TDX_GUEST))
-		return vmware_tdx_hypercall(cmd, in1, in3, 0, 0,
-					    NULL, out2, out3, out4, out5);
+	u32 out1;
 
-	if (unlikely(!alternatives_patched) && !__is_defined(MODULE))
-		return vmware_hypercall_slow(cmd, in1, in3, 0, 0,
-					     NULL, out2, out3, out4, out5);
-
-	asm_inline volatile (VMWARE_HYPERCALL
-		: "=a" (out0), "=c" (*out2), "=d" (*out3), "=S" (*out4),
-		  "=D" (*out5)
-		: [port] "i" (VMWARE_HYPERVISOR_PORT),
-		  "a" (VMWARE_HYPERVISOR_MAGIC),
-		  "b" (in1),
-		  "c" (cmd),
-		  "d" (in3)
-		: "cc", "memory");
-	return out0;
+	return static_call_mod(vmware_hypercall)(cmd, in1, in3, 0, 0,
+			       &out1, out2, out3, out4, out5);
 }
 
 static inline
@@ -230,27 +194,10 @@ unsigned long vmware_hypercall7(unsigned long cmd, unsigned long in1,
 				unsigned long in5, u32 *out1,
 				u32 *out2, u32 *out3)
 {
-	unsigned long out0;
-
-	if (cpu_feature_enabled(X86_FEATURE_TDX_GUEST))
-		return vmware_tdx_hypercall(cmd, in1, in3, in4, in5,
-					    out1, out2, out3, NULL, NULL);
+	u32 out4, out5;
 
-	if (unlikely(!alternatives_patched) && !__is_defined(MODULE))
-		return vmware_hypercall_slow(cmd, in1, in3, in4, in5,
-					     out1, out2, out3, NULL, NULL);
-
-	asm_inline volatile (VMWARE_HYPERCALL
-		: "=a" (out0), "=b" (*out1), "=c" (*out2), "=d" (*out3)
-		: [port] "i" (VMWARE_HYPERVISOR_PORT),
-		  "a" (VMWARE_HYPERVISOR_MAGIC),
-		  "b" (in1),
-		  "c" (cmd),
-		  "d" (in3),
-		  "S" (in4),
-		  "D" (in5)
-		: "cc", "memory");
-	return out0;
+	return static_call_mod(vmware_hypercall)(cmd, in1, in3, in4, in5,
+			       out1, out2, out3, &out4, &out5);
 }
 
 #ifdef CONFIG_X86_64
@@ -322,6 +269,5 @@ unsigned long vmware_hypercall_hb_in(unsigned long cmd, unsigned long in2,
 	return out0;
 }
 #undef VMW_BP_CONSTRAINT
-#undef VMWARE_HYPERCALL
 
 #endif
diff --git a/arch/x86/kernel/cpu/vmware.c b/arch/x86/kernel/cpu/vmware.c
index a3e6936839b1..93acd3414e37 100644
--- a/arch/x86/kernel/cpu/vmware.c
+++ b/arch/x86/kernel/cpu/vmware.c
@@ -64,70 +64,140 @@ struct vmware_steal_time {
 };
 
 static unsigned long vmware_tsc_khz __ro_after_init;
-static u8 vmware_hypercall_mode     __ro_after_init;
-
-unsigned long vmware_hypercall_slow(unsigned long cmd,
-				    unsigned long in1, unsigned long in3,
-				    unsigned long in4, unsigned long in5,
-				    u32 *out1, u32 *out2, u32 *out3,
-				    u32 *out4, u32 *out5)
-{
-	unsigned long out0, rbx, rcx, rdx, rsi, rdi;
-
-	switch (vmware_hypercall_mode) {
-	case CPUID_VMWARE_FEATURES_ECX_VMCALL:
-		asm_inline volatile ("vmcall"
-				: "=a" (out0), "=b" (rbx), "=c" (rcx),
-				"=d" (rdx), "=S" (rsi), "=D" (rdi)
-				: "a" (VMWARE_HYPERVISOR_MAGIC),
-				"b" (in1),
-				"c" (cmd),
-				"d" (in3),
-				"S" (in4),
-				"D" (in5)
-				: "cc", "memory");
-		break;
-	case CPUID_VMWARE_FEATURES_ECX_VMMCALL:
-		asm_inline volatile ("vmmcall"
-				: "=a" (out0), "=b" (rbx), "=c" (rcx),
-				"=d" (rdx), "=S" (rsi), "=D" (rdi)
-				: "a" (VMWARE_HYPERVISOR_MAGIC),
-				"b" (in1),
-				"c" (cmd),
-				"d" (in3),
-				"S" (in4),
-				"D" (in5)
-				: "cc", "memory");
-		break;
-	default:
-		asm_inline volatile ("movw %[port], %%dx; inl (%%dx), %%eax"
-				: "=a" (out0), "=b" (rbx), "=c" (rcx),
-				"=d" (rdx), "=S" (rsi), "=D" (rdi)
-				: [port] "i" (VMWARE_HYPERVISOR_PORT),
-				"a" (VMWARE_HYPERVISOR_MAGIC),
-				"b" (in1),
-				"c" (cmd),
-				"d" (in3),
-				"S" (in4),
-				"D" (in5)
-				: "cc", "memory");
-		break;
-	}
+static u8 vmware_hypercall_mode     __initdata;
+
+static unsigned long vmware_backdoor_hypercall(unsigned long cmd,
+			       unsigned long in1, unsigned long in3,
+			       unsigned long in4, unsigned long in5,
+			       u32 *out1, u32 *out2, u32 *out3,
+			       u32 *out4, u32 *out5)
+{
+	unsigned long out0;
+
+	/* The low word of in3(%edx) must have the backdoor port number */
+	in3 = (in3 & ~0xffff) | VMWARE_HYPERVISOR_PORT;
+
+	asm_inline volatile ("inl (%%dx), %%eax"
+		: "=a" (out0), "=b" (*out1), "=c" (*out2),
+		  "=d" (*out3), "=S" (*out4), "=D" (*out5)
+		: "a" (VMWARE_HYPERVISOR_MAGIC),
+		  "b" (in1),
+		  "c" (cmd),
+		  "d" (in3),
+		  "S" (in4),
+		  "D" (in5)
+		: "cc", "memory");
 
-	if (out1)
-		*out1 = rbx;
-	if (out2)
-		*out2 = rcx;
-	if (out3)
-		*out3 = rdx;
-	if (out4)
-		*out4 = rsi;
-	if (out5)
-		*out5 = rdi;
+	return out0;
+}
+
+static unsigned long vmware_vmcall_hypercall(unsigned long cmd,
+			       unsigned long in1, unsigned long in3,
+			       unsigned long in4, unsigned long in5,
+			       u32 *out1, u32 *out2, u32 *out3,
+			       u32 *out4, u32 *out5)
+{
+	unsigned long out0;
+
+	/* The low word of in3(%edx) must be zero: LB, IN */
+	in3 &= ~0xffff;
+
+	asm_inline volatile ("vmcall"
+		: "=a" (out0), "=b" (*out1), "=c" (*out2),
+		  "=d" (*out3), "=S" (*out4), "=D" (*out5)
+		: "a" (VMWARE_HYPERVISOR_MAGIC),
+		  "b" (in1),
+		  "c" (cmd),
+		  "d" (in3),
+		  "S" (in4),
+		  "D" (in5)
+		: "cc", "memory");
 
 	return out0;
 }
 
+static unsigned long vmware_vmmcall_hypercall(unsigned long cmd,
+			       unsigned long in1, unsigned long in3,
+			       unsigned long in4, unsigned long in5,
+			       u32 *out1, u32 *out2, u32 *out3,
+			       u32 *out4, u32 *out5)
+{
+	unsigned long out0;
+
+	/* The low word of in3(%edx) must be zero: LB, IN */
+	in3 &= ~0xffff;
+
+	asm_inline volatile ("vmmcall"
+		: "=a" (out0), "=b" (*out1), "=c" (*out2),
+		  "=d" (*out3), "=S" (*out4), "=D" (*out5)
+		: "a" (VMWARE_HYPERVISOR_MAGIC),
+		  "b" (in1),
+		  "c" (cmd),
+		  "d" (in3),
+		  "S" (in4),
+		  "D" (in5)
+		: "cc", "memory");
+
+	return out0;
+}
+
+/*
+ * TDCALL[TDG.VP.VMCALL] uses %rax (arg0) and %rcx (arg2). Therefore,
+ * we remap those registers to %r12 and %r13, respectively.
+ */
+static unsigned long vmware_tdx_hypercall(unsigned long cmd,
+				   unsigned long in1, unsigned long in3,
+				   unsigned long in4, unsigned long in5,
+				   u32 *out1, u32 *out2, u32 *out3,
+				   u32 *out4, u32 *out5)
+{
+#ifdef CONFIG_INTEL_TDX_GUEST
+	struct tdx_module_args args = {};
+
+	if (!hypervisor_is_type(X86_HYPER_VMWARE)) {
+		pr_warn_once("Incorrect usage\n");
+		return ULONG_MAX;
+	}
+
+	if (cmd & ~VMWARE_CMD_MASK) {
+		pr_warn_once("Out of range command %lx\n", cmd);
+		return ULONG_MAX;
+	}
+
+	args.rbx = in1;
+	/* The low word of in3(%rdx) must be zero: LB, IN */
+	args.rdx = in3 & ~0xffff;
+	args.rsi = in4;
+	args.rdi = in5;
+	args.r10 = VMWARE_TDX_VENDOR_LEAF;
+	args.r11 = VMWARE_TDX_HCALL_FUNC;
+	args.r12 = VMWARE_HYPERVISOR_MAGIC;
+	args.r13 = cmd;
+	/* CPL */
+	args.r15 = 0;
+
+	__tdx_hypercall(&args);
+
+	*out1 = args.rbx;
+	*out2 = args.r13;
+	*out3 = args.rdx;
+	*out4 = args.rsi;
+	*out5 = args.rdi;
+
+	return args.r12;
+#else
+	return ULONG_MAX;
+#endif
+}
+
+
+DEFINE_STATIC_CALL(vmware_hypercall, vmware_backdoor_hypercall);
+EXPORT_STATIC_CALL_GPL(vmware_hypercall);
+
+/*
+ * Perform backdoor probbing of the hypervisor when
+ * X86_FEATURE_HYPERVISOR bit is not set.
+ */
 static inline int __vmware_platform(void)
 {
 	u32 eax, ebx, ecx;
@@ -397,11 +467,35 @@ static void __init vmware_set_capabilities(void)
 		setup_force_cpu_cap(X86_FEATURE_VMW_VMMCALL);
 }
 
+static void __init vmware_select_hypercall(void)
+{
+	char *mode;
+
+	if (IS_ENABLED(CONFIG_INTEL_TDX_GUEST) &&
+	    cpu_feature_enabled(X86_FEATURE_TDX_GUEST)) {
+		static_call_update(vmware_hypercall, vmware_tdx_hypercall);
+		mode = "tdcall";
+	} else if (vmware_hypercall_mode == CPUID_VMWARE_FEATURES_ECX_VMCALL) {
+		static_call_update(vmware_hypercall, vmware_vmcall_hypercall);
+		mode = "vmcall";
+	} else if (vmware_hypercall_mode == CPUID_VMWARE_FEATURES_ECX_VMMCALL) {
+		static_call_update(vmware_hypercall, vmware_vmmcall_hypercall);
+		mode = "vmmcall";
+	} else {
+		mode = "backdoor";
+	}
+
+	pr_info("hypercall mode: %s\n", mode);
+}
+
 static void __init vmware_platform_setup(void)
 {
 	u32 eax, ebx, ecx;
 	u64 lpj, tsc_khz;
 
+	/* Update vmware_hypercall() before the first use. */
+	vmware_select_hypercall();
+
 	eax = vmware_hypercall3(VMWARE_CMD_GETHZ, UINT_MAX, &ebx, &ecx);
 
 	if (ebx != UINT_MAX) {
@@ -443,7 +537,7 @@ static void __init vmware_platform_setup(void)
 	vmware_set_capabilities();
 }
 
-static u8 __init vmware_select_hypercall(void)
+static u8 __init get_hypercall_mode(void)
 {
 	int eax, ebx, ecx, edx;
 
@@ -456,8 +550,8 @@ static u8 __init vmware_select_hypercall(void)
  * While checking the dmi string information, just checking the product
  * serial key should be enough, as this will always have a VMware
  * specific string when running under VMware hypervisor.
- * If !boot_cpu_has(X86_FEATURE_HYPERVISOR), vmware_hypercall_mode
- * intentionally defaults to 0.
+ * If !boot_cpu_has(X86_FEATURE_HYPERVISOR), __vmware_platform()
+ * intentionally defaults to backdoor hypercall.
  */
 static u32 __init vmware_platform(void)
 {
@@ -470,11 +564,7 @@ static u32 __init vmware_platform(void)
 		if (!memcmp(hyper_vendor_id, "VMwareVMware", 12)) {
 			if (eax >= CPUID_VMWARE_FEATURES_LEAF)
 				vmware_hypercall_mode =
-					vmware_select_hypercall();
-
-			pr_info("hypercall mode: 0x%02x\n",
-				(unsigned int) vmware_hypercall_mode);
-
+					get_hypercall_mode();
 			return CPUID_VMWARE_INFO_LEAF;
 		}
 	} else if (dmi_available && dmi_name_in_serial("VMware") &&
@@ -494,58 +584,6 @@ static bool __init vmware_legacy_x2apic_available(void)
 		(eax & GETVCPU_INFO_LEGACY_X2APIC);
 }
 
-#ifdef CONFIG_INTEL_TDX_GUEST
-/*
- * TDCALL[TDG.VP.VMCALL] uses %rax (arg0) and %rcx (arg2). Therefore,
- * we remap those registers to %r12 and %r13, respectively.
- */
-unsigned long vmware_tdx_hypercall(unsigned long cmd,
-				   unsigned long in1, unsigned long in3,
-				   unsigned long in4, unsigned long in5,
-				   u32 *out1, u32 *out2, u32 *out3,
-				   u32 *out4, u32 *out5)
-{
-	struct tdx_module_args args = {};
-
-	if (!hypervisor_is_type(X86_HYPER_VMWARE)) {
-		pr_warn_once("Incorrect usage\n");
-		return ULONG_MAX;
-	}
-
-	if (cmd & ~VMWARE_CMD_MASK) {
-		pr_warn_once("Out of range command %lx\n", cmd);
-		return ULONG_MAX;
-	}
-
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
-	__tdx_hypercall(&args);
-
-	if (out1)
-		*out1 = args.rbx;
-	if (out2)
-		*out2 = args.r13;
-	if (out3)
-		*out3 = args.rdx;
-	if (out4)
-		*out4 = args.rsi;
-	if (out5)
-		*out5 = args.rdi;
-
-	return args.r12;
-}
-EXPORT_SYMBOL_GPL(vmware_tdx_hypercall);
-#endif
-
 #ifdef CONFIG_AMD_MEM_ENCRYPT
 static void vmware_sev_es_hcall_prepare(struct ghcb *ghcb,
 					struct pt_regs *regs)

---

## [3] Alexey Makhalov — 2026-03-07
*Subject: [PATCH 2/4] x86/vmware: Log kmsg dump on panic*

Improve debugability of VMware Linux guests by dumping
kernel messages during a panic to VM log file (vmware.log).

Co-developed-by: Bo Gan <bo.gan@broadcom.com>
Signed-off-by: Bo Gan <bo.gan@broadcom.com>
Signed-off-by: Alexey Makhalov <alexey.makhalov@broadcom.com>
---
 arch/x86/include/asm/vmware.h |   1 +
 arch/x86/kernel/cpu/vmware.c  | 132 ++++++++++++++++++++++++++++++++++
 2 files changed, 133 insertions(+)

diff --git a/arch/x86/include/asm/vmware.h b/arch/x86/include/asm/vmware.h
index 6a084e088b30..c23164503e54 100644
--- a/arch/x86/include/asm/vmware.h
+++ b/arch/x86/include/asm/vmware.h
@@ -93,6 +93,7 @@
 #define VMWARE_HYPERVISOR_MAGIC		0x564d5868U
 
 #define VMWARE_CMD_GETVERSION		10
+#define VMWARE_CMD_MESSAGE		30
 #define VMWARE_CMD_GETHZ		45
 #define VMWARE_CMD_GETVCPU_INFO		68
 #define VMWARE_CMD_STEALCLOCK		91
diff --git a/arch/x86/kernel/cpu/vmware.c b/arch/x86/kernel/cpu/vmware.c
index 93acd3414e37..d9753b1aba58 100644
--- a/arch/x86/kernel/cpu/vmware.c
+++ b/arch/x86/kernel/cpu/vmware.c
@@ -30,6 +30,7 @@
 #include <linux/reboot.h>
 #include <linux/static_call.h>
 #include <linux/sched/cputime.h>
+#include <linux/kmsg_dump.h>
 #include <asm/div64.h>
 #include <asm/x86_init.h>
 #include <asm/hypervisor.h>
@@ -211,6 +212,13 @@ static unsigned long vmware_get_tsc_khz(void)
 	return vmware_tsc_khz;
 }
 
+static void kmsg_dumper_vmware_log(struct kmsg_dumper *dumper,
+				   struct kmsg_dump_detail *detail);
+
+static struct kmsg_dumper kmsg_dumper = {
+	.dump = kmsg_dumper_vmware_log
+};
+
 #ifdef CONFIG_PARAVIRT
 static struct cyc2ns_data vmware_cyc2ns __ro_after_init;
 static bool vmw_sched_clock __initdata = true;
@@ -535,6 +543,8 @@ static void __init vmware_platform_setup(void)
 #endif
 
 	vmware_set_capabilities();
+
+	kmsg_dump_register(&kmsg_dumper);
 }
 
 static u8 __init get_hypercall_mode(void)
@@ -630,3 +640,125 @@ const __initconst struct hypervisor_x86 x86_hyper_vmware = {
 	.runtime.sev_es_hcall_finish	= vmware_sev_es_hcall_finish,
 #endif
 };
+
+#define VMWARE_HB_CMD_MESSAGE	0
+#define MESSAGE_STATUS_SUCCESS	(0x01 << 16)
+#define MESSAGE_STATUS_CPT	(0x10 << 16)
+#define MESSAGE_STATUS_HB	(0x80 << 16)
+
+#define RPCI_PROTOCOL_NUM	0x49435052 /* 'RPCI' */
+#define GUESTMSG_FLAG_COOKIE	0x80000000
+
+#define MESSAGE_TYPE_OPEN	(0 << 16)
+#define MESSAGE_TYPE_SENDSIZE	(1 << 16)
+#define MESSAGE_TYPE_SEND	(2 << 16)
+#define MESSAGE_TYPE_CLOSE	(6 << 16)
+
+struct vmw_msg {
+	u32 id;
+	u32 cookie_high;
+	u32 cookie_low;
+};
+
+static int
+vmware_log_open(struct vmw_msg *msg)
+{
+	u32 info;
+
+	vmware_hypercall6(VMWARE_CMD_MESSAGE | MESSAGE_TYPE_OPEN,
+			  RPCI_PROTOCOL_NUM | GUESTMSG_FLAG_COOKIE,
+			  0, &info, &msg->id, &msg->cookie_high,
+			  &msg->cookie_low);
+
+	if ((info & MESSAGE_STATUS_SUCCESS) == 0)
+		return 1;
+
+	msg->id &= 0xffff0000UL;
+	return 0;
+}
+
+static int
+vmware_log_close(struct vmw_msg *msg)
+{
+	u32 info;
+
+	vmware_hypercall5(VMWARE_CMD_MESSAGE | MESSAGE_TYPE_CLOSE, 0, msg->id,
+			  msg->cookie_high, msg->cookie_low, &info);
+
+	if ((info & MESSAGE_STATUS_SUCCESS) == 0)
+		return 1;
+	return 0;
+}
+
+static int
+vmware_log_send(struct vmw_msg *msg, const char *string)
+{
+	u32 info;
+	u32 len = strlen(string);
+
+retry:
+	vmware_hypercall5(VMWARE_CMD_MESSAGE | MESSAGE_TYPE_SENDSIZE, len,
+			  msg->id, msg->cookie_high, msg->cookie_low, &info);
+
+	if (!(info & MESSAGE_STATUS_SUCCESS))
+		return 1;
+
+	/* HB port can't access encrypted memory. */
+	if (!cc_platform_has(CC_ATTR_MEM_ENCRYPT) && (info & MESSAGE_STATUS_HB)) {
+		vmware_hypercall_hb_out(
+			VMWARE_HB_CMD_MESSAGE | MESSAGE_STATUS_SUCCESS,
+			len, msg->id, (uintptr_t) string, msg->cookie_low,
+			msg->cookie_high, &info);
+	} else {
+		do {
+			u32 word;
+			size_t s = min_t(u32, len, sizeof(word));
+
+			memcpy(&word, string, s);
+			len -= s;
+			string += s;
+
+			vmware_hypercall5(VMWARE_CMD_MESSAGE | MESSAGE_TYPE_SEND,
+					  word, msg->id, msg->cookie_high,
+					  msg->cookie_low, &info);
+		} while (len && (info & MESSAGE_STATUS_SUCCESS));
+	}
+
+	if ((info & MESSAGE_STATUS_SUCCESS) == 0) {
+		if (info & MESSAGE_STATUS_CPT)
+			/* A checkpoint occurred. Retry. */
+			goto retry;
+		return 1;
+	}
+	return 0;
+}
+STACK_FRAME_NON_STANDARD(vmware_log_send);
+
+/**
+ * kmsg_dumper_vmware_log - dumps kmsg to vmware.log file on the host
+ */
+static void kmsg_dumper_vmware_log(struct kmsg_dumper *dumper,
+				   struct kmsg_dump_detail *detail)
+{
+	struct vmw_msg msg;
+	struct kmsg_dump_iter iter;
+	static char line[1024];
+	size_t len = 0;
+
+	/* Line prefix to send to VM log file. */
+	line[0] = 'l';
+	line[1] = 'o';
+	line[2] = 'g';
+	line[3] = ' ';
+
+	kmsg_dump_rewind(&iter);
+	while (kmsg_dump_get_line(&iter, true, line + 4, sizeof(line) - 4,
+				  &len)) {
+		line[len + 4] = '\0';
+		if (vmware_log_open(&msg))
+			return;
+		if (vmware_log_send(&msg, line))
+			return;
+		vmware_log_close(&msg);
+	}
+}

---

## [4] Alexey Makhalov — 2026-03-07
*Subject: [PATCH 3/4] x86/vmware: Report guest crash to the hypervisor*

Register the guest crash reporter to panic_notifier_list,
which will be called at panic time. Guest crash reporter
will report the crash to the hypervisor through
a hypercall.

Co-developed-by: Brennan Lamoreaux <brennan.lamoreaux@broadcom.com>
Signed-off-by: Brennan Lamoreaux <brennan.lamoreaux@broadcom.com>
Signed-off-by: Alexey Makhalov <alexey.makhalov@broadcom.com>
---
 arch/x86/include/asm/vmware.h |  1 +
 arch/x86/kernel/cpu/vmware.c  | 21 +++++++++++++++++++++
 2 files changed, 22 insertions(+)

diff --git a/arch/x86/include/asm/vmware.h b/arch/x86/include/asm/vmware.h
index c23164503e54..bf6141353774 100644
--- a/arch/x86/include/asm/vmware.h
+++ b/arch/x86/include/asm/vmware.h
@@ -97,6 +97,7 @@
 #define VMWARE_CMD_GETHZ		45
 #define VMWARE_CMD_GETVCPU_INFO		68
 #define VMWARE_CMD_STEALCLOCK		91
+#define VMWARE_CMD_REPORTGUESTCRASH	102
 /*
  * Hypercall command mask:
  *   bits [6:0] command, range [0, 127]
diff --git a/arch/x86/kernel/cpu/vmware.c b/arch/x86/kernel/cpu/vmware.c
index d9753b1aba58..8997295a5a5c 100644
--- a/arch/x86/kernel/cpu/vmware.c
+++ b/arch/x86/kernel/cpu/vmware.c
@@ -31,6 +31,7 @@
 #include <linux/static_call.h>
 #include <linux/sched/cputime.h>
 #include <linux/kmsg_dump.h>
+#include <linux/panic_notifier.h>
 #include <asm/div64.h>
 #include <asm/x86_init.h>
 #include <asm/hypervisor.h>
@@ -451,6 +452,24 @@ static void __init vmware_paravirt_ops_setup(void)
 #define vmware_paravirt_ops_setup() do {} while (0)
 #endif
 
+static int vmware_report_guest_crash(struct notifier_block *self,
+				     unsigned long action, void *data)
+{
+	vmware_hypercall1(VMWARE_CMD_REPORTGUESTCRASH, 0);
+	return 0;
+}
+
+static struct notifier_block guest_crash_reporter = {
+	.notifier_call = vmware_report_guest_crash
+};
+
+static int __init register_guest_crash_reporter(void)
+{
+	atomic_notifier_chain_register(&panic_notifier_list,
+					&guest_crash_reporter);
+
+	return 0;
+}
 /*
  * VMware hypervisor takes care of exporting a reliable TSC to the guest.
  * Still, due to timing difference when running on virtual cpus, the TSC can
@@ -545,6 +564,8 @@ static void __init vmware_platform_setup(void)
 	vmware_set_capabilities();
 
 	kmsg_dump_register(&kmsg_dumper);
+
+	register_guest_crash_reporter();
 }
 
 static u8 __init get_hypercall_mode(void)

---

## [5] Alexey Makhalov — 2026-03-07
*Subject: [PATCH 4/4] x86/vmware: Support steal time clock for encrypted guests*

Shared memory containing steal time counter should be set to
decrypted when guest memory is encrypted.

Co-developed-by: Bo Gan <bo.gan@broadcom.com>
Signed-off-by: Bo Gan <bo.gan@broadcom.com>
Signed-off-by: Alexey Makhalov <alexey.makhalov@broadcom.com>
---
 arch/x86/kernel/cpu/vmware.c | 41 ++++++++++++++++++++++++++++++++++++
 1 file changed, 41 insertions(+)

diff --git a/arch/x86/kernel/cpu/vmware.c b/arch/x86/kernel/cpu/vmware.c
index 8997295a5a5c..e33400d4f2c1 100644
--- a/arch/x86/kernel/cpu/vmware.c
+++ b/arch/x86/kernel/cpu/vmware.c
@@ -32,6 +32,7 @@
 #include <linux/sched/cputime.h>
 #include <linux/kmsg_dump.h>
 #include <linux/panic_notifier.h>
+#include <linux/set_memory.h>
 #include <asm/div64.h>
 #include <asm/x86_init.h>
 #include <asm/hypervisor.h>
@@ -39,6 +40,7 @@
 #include <asm/apic.h>
 #include <asm/vmware.h>
 #include <asm/svm.h>
+#include <asm/coco.h>
 
 #undef pr_fmt
 #define pr_fmt(fmt)	"vmware: " fmt
@@ -379,9 +381,47 @@ static struct notifier_block vmware_pv_reboot_nb = {
 	.notifier_call = vmware_pv_reboot_notify,
 };
 
+/*
+ * Map per-CPU variables for all possible CPUs as decrypted.
+ * Do this early in boot, before sharing the corresponding
+ * guest physical addresses with the hypervisor.
+ */
+static void __init set_shared_memory_decrypted(void)
+{
+	int cpu;
+
+	if (!cc_platform_has(CC_ATTR_GUEST_MEM_ENCRYPT))
+		return;
+
+	for_each_possible_cpu(cpu) {
+		unsigned long size = sizeof(vmw_steal_time);
+		unsigned long addr = (unsigned long)&per_cpu(vmw_steal_time,
+							cpu);
+
+		/*
+		 * There is no generic high-level API to mark memory as
+		 * decrypted. Intel's set_memory_decrypted() depends on the
+		 * buddy allocator and can fail early in boot if a page split
+		 * is required and allocation is not possible. Use AMD's
+		 * early_set_memory_decrypted() instead, which can perform
+		 * the split during early boot.
+		 */
+		early_set_memory_decrypted(addr, size);
+
+		/* That's it for AMD */
+		if (cc_vendor == CC_VENDOR_AMD)
+			continue;
+
+		set_memory_decrypted(addr & PAGE_MASK, 1UL <<
+				     get_order((addr & ~PAGE_MASK) + size));
+
+	}
+}
+
 #ifdef CONFIG_SMP
 static void __init vmware_smp_prepare_boot_cpu(void)
 {
+	set_shared_memory_decrypted();
 	vmware_guest_cpu_init();
 	native_smp_prepare_boot_cpu();
 }
@@ -444,6 +484,7 @@ static void __init vmware_paravirt_ops_setup(void)
 					      vmware_cpu_down_prepare) < 0)
 			pr_err("vmware_guest: Failed to install cpu hotplug callbacks\n");
 #else
+		set_shared_memory_decrypted();
 		vmware_guest_cpu_init();
 #endif
 	}

---

## [6] kernel test robot — 2026-03-07
*Subject: Re: [PATCH 2/4] x86/vmware: Log kmsg dump on panic*

Hi Alexey,

kernel test robot noticed the following build warnings:

[auto build test WARNING on tip/master]
[also build test WARNING on linus/master v7.0-rc2 next-20260306]
[cannot apply to tip/x86/vmware tip/auto-latest]
[If your patch is applied to the wrong git tree, kindly drop us a note.
And when submitting patch, we suggest to use '--base' as documented in
https://git-scm.com/docs/git-format-patch#_base_tree_information]

url:    https://github.com/intel-lab-lkp/linux/commits/Alexey-Makhalov/x86-vmware-Introduce-common-vmware_hypercall/20260307-091038
base:   tip/master
patch link:    https://lore.kernel.org/r/20260307004238.1181299-3-alexey.makhalov%40broadcom.com
patch subject: [PATCH 2/4] x86/vmware: Log kmsg dump on panic
config: x86_64-rhel-9.4-ltp (https://download.01.org/0day-ci/archive/20260307/202603071246.JbbF0Qpv-lkp@intel.com/config)
compiler: gcc-14 (Debian 14.2.0-19) 14.2.0
reproduce (this is a W=1 build): (https://download.01.org/0day-ci/archive/20260307/202603071246.JbbF0Qpv-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202603071246.JbbF0Qpv-lkp@intel.com/

All warnings (new ones prefixed by >>):

>> Warning: arch/x86/kernel/cpu/vmware.c:741 function parameter 'dumper' not described in 'kmsg_dumper_vmware_log'
>> Warning: arch/x86/kernel/cpu/vmware.c:741 function parameter 'detail' not described in 'kmsg_dumper_vmware_log'

---

## [7] kernel test robot — 2026-03-07
*Subject: Re: [PATCH 2/4] x86/vmware: Log kmsg dump on panic*

Hi Alexey,

kernel test robot noticed the following build warnings:

[auto build test WARNING on tip/master]
[also build test WARNING on linus/master v7.0-rc2 next-20260305]
[cannot apply to tip/x86/vmware tip/auto-latest]
[If your patch is applied to the wrong git tree, kindly drop us a note.
And when submitting patch, we suggest to use '--base' as documented in
https://git-scm.com/docs/git-format-patch#_base_tree_information]

url:    https://github.com/intel-lab-lkp/linux/commits/Alexey-Makhalov/x86-vmware-Introduce-common-vmware_hypercall/20260307-091038
base:   tip/master
patch link:    https://lore.kernel.org/r/20260307004238.1181299-3-alexey.makhalov%40broadcom.com
patch subject: [PATCH 2/4] x86/vmware: Log kmsg dump on panic
config: x86_64-kexec (https://download.01.org/0day-ci/archive/20260307/202603072123.02mytKqA-lkp@intel.com/config)
compiler: clang version 20.1.8 (https://github.com/llvm/llvm-project 87f0227cb60147a26a1eeb4fb06e3b505e9c7261)
reproduce (this is a W=1 build): (https://download.01.org/0day-ci/archive/20260307/202603072123.02mytKqA-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202603072123.02mytKqA-lkp@intel.com/

All warnings (new ones prefixed by >>):

>> Warning: arch/x86/kernel/cpu/vmware.c:741 function parameter 'dumper' not described in 'kmsg_dumper_vmware_log'
>> Warning: arch/x86/kernel/cpu/vmware.c:741 function parameter 'detail' not described in 'kmsg_dumper_vmware_log'

---

## [8] Alexey Makhalov — 2026-03-09
*Subject: [PATCH v2 0/4] x86/vmware: Hypercall refactoring and improved guest support*

This series improves VMware guest support on x86 by refactoring the
hypercall infrastructure and adding better crash diagnostics, along
with encrypted guest support for the steal time clock.

The first patch introduces a common vmware_hypercall() backend selected
via static calls. It consolidates the existing hypercall mechanisms
(backdoor, VMCALL/VMMCALL, and TDX) behind a single interface and
selects the optimal implementation at boot. This reduces duplication
and simplifies future extensions.

Building on top of the new hypercall infrastructure, the next two
patches improve post-mortem debugging of VMware guests. They export
panic information to the hypervisor by dumping kernel messages to the
VM vmware.log on the host and explicitly reporting guest crash event
to the hypervisor.

The final patch adds support for encrypted guests by ensuring that the
shared memory used for the steal time clock is mapped as decrypted
before being shared with the hypervisor. This enables steal time
accounting to function correctly when guest memory encryption is
enabled.

Patch overview:

1. x86/vmware: Introduce common vmware_hypercall

   * Consolidate hypercall implementations behind a common API
   * Select backend via static_call at boot

2. x86/vmware: Log kmsg dump on panic

   * Register a kmsg dumper
   * Export panic logs to the host

3. x86/vmware: Report guest crash to the hypervisor

   * Register a panic notifier
   * Notify the hypervisor about guest crashes

4. x86/vmware: Support steal time clock for encrypted guests

   * Mark shared steal time memory as decrypted early in boot


Changelog:

V1 -> V2
   * Fix compilation warnings in patch 2 "x86/vmware: Log kmsg dump on panic"
     reported by kernel test robot <lkp@intel.com>


Alexey Makhalov (4):
  x86/vmware: Introduce common vmware_hypercall()
  x86/vmware: Log kmsg dump on panic
  x86/vmware: Report guest crash to the hypervisor
  x86/vmware: Support steal time clock for encrypted guests

 arch/x86/include/asm/vmware.h | 276 ++++++++------------
 arch/x86/kernel/cpu/vmware.c  | 470 +++++++++++++++++++++++++---------
 2 files changed, 463 insertions(+), 283 deletions(-)


base-commit: 7d08a6ad25f85c9bb7d0382142838cb54713f1a3

---

## [9] Alexey Makhalov — 2026-03-09
*Subject: [PATCH v2 1/4] x86/vmware: Introduce common vmware_hypercall()*

Introduce vmware_hypercall(), a unified low-bandwidth VMware hypercall
API, and convert the static inlines vmware_hypercallX() family into thin
wrappers on top of it.

vmware_hypercall() is implemented as a static call with four backend
implementations: backdoor, vmcall, vmmcall, and tdxcall. All share the
same logical API but differ in their underlying register mappings.

By updating the static call target early during boot, before the first
hypercall is issued, the !alternatives_patched case no longer needs to
be handled. This allows removal of vmware_hypercall_slow().

The new API implements the widest practical hypercall use case: up to
six input and six output arguments. While this may be slightly less
efficient due to clobbering all six registers and moving unused
arguments - it avoids subtle ABI issues, including cases where other
hypervisors implementing VMware hypercalls corrupt registers.
See QEMU issue #3293 ("vmmouse driver corrupts upper 32 bits of
registers on x86-64") for an example of such behavior.

Additionally, enhance the VMware hypercall ABI documentation in
<asm/vmware.h>.

Link: https://gitlab.com/qemu-project/qemu/-/issues/3293
Suggested-by: Linus Torvalds <torvalds@linux-foundation.org>
Signed-off-by: Alexey Makhalov <alexey.makhalov@broadcom.com>
---
 arch/x86/include/asm/vmware.h | 274 ++++++++++++++-------------------
 arch/x86/kernel/cpu/vmware.c  | 276 +++++++++++++++++++---------------
 2 files changed, 267 insertions(+), 283 deletions(-)

diff --git a/arch/x86/include/asm/vmware.h b/arch/x86/include/asm/vmware.h
index 4220dae14a2d..6a084e088b30 100644
--- a/arch/x86/include/asm/vmware.h
+++ b/arch/x86/include/asm/vmware.h
@@ -3,48 +3,84 @@
 #define _ASM_X86_VMWARE_H
 
 #include <asm/cpufeatures.h>
-#include <asm/alternative.h>
 #include <linux/stringify.h>
+#include <linux/static_call.h>
 
 /*
  * VMware hypercall ABI.
  *
- * - Low bandwidth (LB) hypercalls (I/O port based, vmcall and vmmcall)
- * have up to 6 input and 6 output arguments passed and returned using
- * registers: %eax (arg0), %ebx (arg1), %ecx (arg2), %edx (arg3),
- * %esi (arg4), %edi (arg5).
- * The following input arguments must be initialized by the caller:
- * arg0 - VMWARE_HYPERVISOR_MAGIC
- * arg2 - Hypercall command
- * arg3 bits [15:0] - Port number, LB and direction flags
+ * - Low bandwidth (LB) hypercalls: I/O port based (aka backdoor), vmcall and
+ * vmmcall have up to 6 input and 6 output on registers arguments, with the
+ * register mapping:
+ *  +------+----------------------------------------+-----------------+
+ *  | Reg  | Input argument                         | Output argument |
+ *  +======+========================================+=================+
+ *  | %eax | VMWARE_HYPERVISOR_MAGIC                | out0            |
+ *  +------+----------------------------------------+-----------------+
+ *  | %ebx | (in1)                                  | out1            |
+ *  +------+----------------------------------------+-----------------+
+ *  | %ecx | (cmd) - Hypercall command              | out2            |
+ *  +------+----------------------------------------+-----------------+
+ *  | %edx | Bits [15:0] - Port number for backdoor | out3            |
+ *  |      |               Zero for vmcall/vmmcall  |                 |
+ *  |      | Bits [31:16] - (in3)                   |                 |
+ *  +------+----------------------------------------+-----------------+
+ *  | %esi | (in4)                                  | out4            |
+ *  +------+----------------------------------------+-----------------+
+ *  | %edi | (in5)                                  | out5            |
+ *  +------+----------------------------------------+-----------------+
  *
- * - Low bandwidth TDX hypercalls (x86_64 only) are similar to LB
- * hypercalls. They also have up to 6 input and 6 output on registers
- * arguments, with different argument to register mapping:
- * %r12 (arg0), %rbx (arg1), %r13 (arg2), %rdx (arg3),
- * %rsi (arg4), %rdi (arg5).
+ * - Low bandwidth TDX hypercalls (x86_64 only) are similar to LB hypercalls.
+ * They also have up to 6 input and 6 output on registers arguments, with
+ * different argument to register mapping:
+ *  +------+----------------------------------------+-----------------+
+ *  | Reg  | Input argument                         | Output argument |
+ *  +======+========================================+=================+
+ *  | %r12 | VMWARE_HYPERVISOR_MAGIC                | out0            |
+ *  +------+----------------------------------------+-----------------+
+ *  | %ebx | (in1)                                  | out1            |
+ *  +------+----------------------------------------+-----------------+
+ *  | %r13 | (cmd) - Hypercall command              | out2            |
+ *  +------+----------------------------------------+-----------------+
+ *  | %edx | Bits [15:0] - Must be zero             | out3            |
+ *  |      | Bits [31:16] - (in3)                   |                 |
+ *  +------+----------------------------------------+-----------------+
+ *  | %esi | (in4)                                  | out4            |
+ *  +------+----------------------------------------+-----------------+
+ *  | %edi | (in5)                                  | out5            |
+ *  +------+----------------------------------------+-----------------+
  *
- * - High bandwidth (HB) hypercalls are I/O port based only. They have
- * up to 7 input and 7 output arguments passed and returned using
- * registers: %eax (arg0), %ebx (arg1), %ecx (arg2), %edx (arg3),
- * %esi (arg4), %edi (arg5), %ebp (arg6).
- * The following input arguments must be initialized by the caller:
- * arg0 - VMWARE_HYPERVISOR_MAGIC
- * arg1 - Hypercall command
- * arg3 bits [15:0] - Port number, HB and direction flags
+ * - High bandwidth (HB) hypercalls are I/O port based only. They have up to 7
+ * input and 7 output on reegister arguments with the following mapping:
+ *  +------+----------------------------------------+-----------------+
+ *  | Reg  | Input argument                         | Output argument |
+ *  +======+========================================+=================+
+ *  | %eax | VMWARE_HYPERVISOR_MAGIC                | out0            |
+ *  +------+----------------------------------------+-----------------+
+ *  | %ebx | (cmd) - Hypercall command              | out1            |
+ *  +------+----------------------------------------+-----------------+
+ *  | %ebx | (in2)                                  | out2            |
+ *  +------+----------------------------------------+-----------------+
+ *  | %edx | Bits [15:0] - Port number and HB flag  | out3            |
+ *  |      | Bits [31:16] - (in3)                   |                 |
+ *  +------+----------------------------------------+-----------------+
+ *  | %esi | (in4)                                  | out4            |
+ *  +------+----------------------------------------+-----------------+
+ *  | %edi | (in5)                                  | out5            |
+ *  +------+----------------------------------------+-----------------+
+ *  | %ebp | (in6)                                  | out6            |
+ *  +------+----------------------------------------+-----------------+
  *
- * For compatibility purposes, x86_64 systems use only lower 32 bits
- * for input and output arguments.
+ * For compatibility purposes, x86_64 systems use only lower 32 bits for input
+ * and output arguments.
  *
- * The hypercall definitions differ in the low word of the %edx (arg3)
- * in the following way: the old I/O port based interface uses the port
- * number to distinguish between high- and low bandwidth versions, and
- * uses IN/OUT instructions to define transfer direction.
+ * The hypercall definitions differ in the low word of the %edx (arg3) in the
+ * following way: the old I/O port based interface uses the port number, the
+ * bandwidth mode flag, and uses IN/OUT instructions to define transfer
+ * direction.
  *
- * The new vmcall interface instead uses a set of flags to select
- * bandwidth mode and transfer direction. The flags should be loaded
- * into arg3 by any user and are automatically replaced by the port
- * number if the I/O port method is used.
+ * The new vmcall interface instead uses a set of flags to select bandwidth
+ * mode and transfer direction.
  */
 
 #define VMWARE_HYPERVISOR_HB		BIT(0)
@@ -70,103 +106,64 @@
 #define CPUID_VMWARE_FEATURES_ECX_VMMCALL	BIT(0)
 #define CPUID_VMWARE_FEATURES_ECX_VMCALL	BIT(1)
 
-extern unsigned long vmware_hypercall_slow(unsigned long cmd,
-					   unsigned long in1, unsigned long in3,
-					   unsigned long in4, unsigned long in5,
-					   u32 *out1, u32 *out2, u32 *out3,
-					   u32 *out4, u32 *out5);
-
 #define VMWARE_TDX_VENDOR_LEAF 0x1af7e4909ULL
 #define VMWARE_TDX_HCALL_FUNC  1
 
-extern unsigned long vmware_tdx_hypercall(unsigned long cmd,
-					  unsigned long in1, unsigned long in3,
-					  unsigned long in4, unsigned long in5,
-					  u32 *out1, u32 *out2, u32 *out3,
-					  u32 *out4, u32 *out5);
+unsigned long dummy_vmware_hypercall(unsigned long cmd,
+				     unsigned long in1, unsigned long in3,
+				     unsigned long in4, unsigned long in5,
+				     u32 *out1, u32 *out2, u32 *out3,
+				     u32 *out4, u32 *out5);
 
 /*
- * The low bandwidth call. The low word of %edx is presumed to have OUT bit
- * set. The high word of %edx may contain input data from the caller.
+ * Low bandwidth (LB) VMware hypercall.
+ *
+ * It is backed by the backdoor, vmcall, vmmcall or tdx call implementation.
+ *
+ * Use inX/outX arguments naming as the register mappings vary between
+ * different implementations. See VMware hypercall ABI above.
+ * These 10 arguments could be nicely wrapped in in/out structures, but it
+ * will introduce unnecessary structs copy in vmware_tdx_hypercall().
+ *
+ * NOTE:
+ * Do not merge vmware_{backdoor,vmcall,vmmcall}_hypercall implementations
+ * using alternative instructions. Such patching mechanism can not be used
+ * in vmware_hypercall path, as the first hypercall will be called much
+ * before the apply_alternatives(). See vmware_platform_setup().
  */
-#define VMWARE_HYPERCALL					\
-	ALTERNATIVE_2("movw %[port], %%dx\n\t"			\
-		      "inl (%%dx), %%eax",			\
-		      "vmcall", X86_FEATURE_VMCALL,		\
-		      "vmmcall", X86_FEATURE_VMW_VMMCALL)
+DECLARE_STATIC_CALL(vmware_hypercall, dummy_vmware_hypercall);
 
+/*
+ * Set of commonly used vmware_hypercallX functions - wrappers on top of the
+ * vmware_hypercall.
+ */
 static inline
 unsigned long vmware_hypercall1(unsigned long cmd, unsigned long in1)
 {
-	unsigned long out0;
-
-	if (cpu_feature_enabled(X86_FEATURE_TDX_GUEST))
-		return vmware_tdx_hypercall(cmd, in1, 0, 0, 0,
-					    NULL, NULL, NULL, NULL, NULL);
-
-	if (unlikely(!alternatives_patched) && !__is_defined(MODULE))
-		return vmware_hypercall_slow(cmd, in1, 0, 0, 0,
-					     NULL, NULL, NULL, NULL, NULL);
+	u32 out1, out2, out3, out4, out5;
 
-	asm_inline volatile (VMWARE_HYPERCALL
-		: "=a" (out0)
-		: [port] "i" (VMWARE_HYPERVISOR_PORT),
-		  "a" (VMWARE_HYPERVISOR_MAGIC),
-		  "b" (in1),
-		  "c" (cmd),
-		  "d" (0)
-		: "cc", "memory");
-	return out0;
+	return static_call_mod(vmware_hypercall)(cmd, in1, 0, 0, 0,
+			       &out1, &out2, &out3, &out4, &out5);
 }
 
 static inline
 unsigned long vmware_hypercall3(unsigned long cmd, unsigned long in1,
 				u32 *out1, u32 *out2)
 {
-	unsigned long out0;
-
-	if (cpu_feature_enabled(X86_FEATURE_TDX_GUEST))
-		return vmware_tdx_hypercall(cmd, in1, 0, 0, 0,
-					    out1, out2, NULL, NULL, NULL);
-
-	if (unlikely(!alternatives_patched) && !__is_defined(MODULE))
-		return vmware_hypercall_slow(cmd, in1, 0, 0, 0,
-					     out1, out2, NULL, NULL, NULL);
+	u32 out3, out4, out5;
 
-	asm_inline volatile (VMWARE_HYPERCALL
-		: "=a" (out0), "=b" (*out1), "=c" (*out2)
-		: [port] "i" (VMWARE_HYPERVISOR_PORT),
-		  "a" (VMWARE_HYPERVISOR_MAGIC),
-		  "b" (in1),
-		  "c" (cmd),
-		  "d" (0)
-		: "di", "si", "cc", "memory");
-	return out0;
+	return static_call_mod(vmware_hypercall)(cmd, in1, 0, 0, 0,
+			       out1, out2, &out3, &out4, &out5);
 }
 
 static inline
 unsigned long vmware_hypercall4(unsigned long cmd, unsigned long in1,
 				u32 *out1, u32 *out2, u32 *out3)
 {
-	unsigned long out0;
-
-	if (cpu_feature_enabled(X86_FEATURE_TDX_GUEST))
-		return vmware_tdx_hypercall(cmd, in1, 0, 0, 0,
-					    out1, out2, out3, NULL, NULL);
-
-	if (unlikely(!alternatives_patched) && !__is_defined(MODULE))
-		return vmware_hypercall_slow(cmd, in1, 0, 0, 0,
-					     out1, out2, out3, NULL, NULL);
+	u32 out4, out5;
 
-	asm_inline volatile (VMWARE_HYPERCALL
-		: "=a" (out0), "=b" (*out1), "=c" (*out2), "=d" (*out3)
-		: [port] "i" (VMWARE_HYPERVISOR_PORT),
-		  "a" (VMWARE_HYPERVISOR_MAGIC),
-		  "b" (in1),
-		  "c" (cmd),
-		  "d" (0)
-		: "di", "si", "cc", "memory");
-	return out0;
+	return static_call_mod(vmware_hypercall)(cmd, in1, 0, 0, 0,
+			       out1, out2, out3, &out4, &out5);
 }
 
 static inline
@@ -174,27 +171,10 @@ unsigned long vmware_hypercall5(unsigned long cmd, unsigned long in1,
 				unsigned long in3, unsigned long in4,
 				unsigned long in5, u32 *out2)
 {
-	unsigned long out0;
-
-	if (cpu_feature_enabled(X86_FEATURE_TDX_GUEST))
-		return vmware_tdx_hypercall(cmd, in1, in3, in4, in5,
-					    NULL, out2, NULL, NULL, NULL);
+	u32 out1, out3, out4, out5;
 
-	if (unlikely(!alternatives_patched) && !__is_defined(MODULE))
-		return vmware_hypercall_slow(cmd, in1, in3, in4, in5,
-					     NULL, out2, NULL, NULL, NULL);
-
-	asm_inline volatile (VMWARE_HYPERCALL
-		: "=a" (out0), "=c" (*out2)
-		: [port] "i" (VMWARE_HYPERVISOR_PORT),
-		  "a" (VMWARE_HYPERVISOR_MAGIC),
-		  "b" (in1),
-		  "c" (cmd),
-		  "d" (in3),
-		  "S" (in4),
-		  "D" (in5)
-		: "cc", "memory");
-	return out0;
+	return static_call_mod(vmware_hypercall)(cmd, in1, in3, in4, in5,
+			       &out1, out2, &out3, &out4, &out5);
 }
 
 static inline
@@ -202,26 +182,10 @@ unsigned long vmware_hypercall6(unsigned long cmd, unsigned long in1,
 				unsigned long in3, u32 *out2,
 				u32 *out3, u32 *out4, u32 *out5)
 {
-	unsigned long out0;
-
-	if (cpu_feature_enabled(X86_FEATURE_TDX_GUEST))
-		return vmware_tdx_hypercall(cmd, in1, in3, 0, 0,
-					    NULL, out2, out3, out4, out5);
+	u32 out1;
 
-	if (unlikely(!alternatives_patched) && !__is_defined(MODULE))
-		return vmware_hypercall_slow(cmd, in1, in3, 0, 0,
-					     NULL, out2, out3, out4, out5);
-
-	asm_inline volatile (VMWARE_HYPERCALL
-		: "=a" (out0), "=c" (*out2), "=d" (*out3), "=S" (*out4),
-		  "=D" (*out5)
-		: [port] "i" (VMWARE_HYPERVISOR_PORT),
-		  "a" (VMWARE_HYPERVISOR_MAGIC),
-		  "b" (in1),
-		  "c" (cmd),
-		  "d" (in3)
-		: "cc", "memory");
-	return out0;
+	return static_call_mod(vmware_hypercall)(cmd, in1, in3, 0, 0,
+			       &out1, out2, out3, out4, out5);
 }
 
 static inline
@@ -230,27 +194,10 @@ unsigned long vmware_hypercall7(unsigned long cmd, unsigned long in1,
 				unsigned long in5, u32 *out1,
 				u32 *out2, u32 *out3)
 {
-	unsigned long out0;
-
-	if (cpu_feature_enabled(X86_FEATURE_TDX_GUEST))
-		return vmware_tdx_hypercall(cmd, in1, in3, in4, in5,
-					    out1, out2, out3, NULL, NULL);
+	u32 out4, out5;
 
-	if (unlikely(!alternatives_patched) && !__is_defined(MODULE))
-		return vmware_hypercall_slow(cmd, in1, in3, in4, in5,
-					     out1, out2, out3, NULL, NULL);
-
-	asm_inline volatile (VMWARE_HYPERCALL
-		: "=a" (out0), "=b" (*out1), "=c" (*out2), "=d" (*out3)
-		: [port] "i" (VMWARE_HYPERVISOR_PORT),
-		  "a" (VMWARE_HYPERVISOR_MAGIC),
-		  "b" (in1),
-		  "c" (cmd),
-		  "d" (in3),
-		  "S" (in4),
-		  "D" (in5)
-		: "cc", "memory");
-	return out0;
+	return static_call_mod(vmware_hypercall)(cmd, in1, in3, in4, in5,
+			       out1, out2, out3, &out4, &out5);
 }
 
 #ifdef CONFIG_X86_64
@@ -322,6 +269,5 @@ unsigned long vmware_hypercall_hb_in(unsigned long cmd, unsigned long in2,
 	return out0;
 }
 #undef VMW_BP_CONSTRAINT
-#undef VMWARE_HYPERCALL
 
 #endif
diff --git a/arch/x86/kernel/cpu/vmware.c b/arch/x86/kernel/cpu/vmware.c
index a3e6936839b1..93acd3414e37 100644
--- a/arch/x86/kernel/cpu/vmware.c
+++ b/arch/x86/kernel/cpu/vmware.c
@@ -64,70 +64,140 @@ struct vmware_steal_time {
 };
 
 static unsigned long vmware_tsc_khz __ro_after_init;
-static u8 vmware_hypercall_mode     __ro_after_init;
-
-unsigned long vmware_hypercall_slow(unsigned long cmd,
-				    unsigned long in1, unsigned long in3,
-				    unsigned long in4, unsigned long in5,
-				    u32 *out1, u32 *out2, u32 *out3,
-				    u32 *out4, u32 *out5)
-{
-	unsigned long out0, rbx, rcx, rdx, rsi, rdi;
-
-	switch (vmware_hypercall_mode) {
-	case CPUID_VMWARE_FEATURES_ECX_VMCALL:
-		asm_inline volatile ("vmcall"
-				: "=a" (out0), "=b" (rbx), "=c" (rcx),
-				"=d" (rdx), "=S" (rsi), "=D" (rdi)
-				: "a" (VMWARE_HYPERVISOR_MAGIC),
-				"b" (in1),
-				"c" (cmd),
-				"d" (in3),
-				"S" (in4),
-				"D" (in5)
-				: "cc", "memory");
-		break;
-	case CPUID_VMWARE_FEATURES_ECX_VMMCALL:
-		asm_inline volatile ("vmmcall"
-				: "=a" (out0), "=b" (rbx), "=c" (rcx),
-				"=d" (rdx), "=S" (rsi), "=D" (rdi)
-				: "a" (VMWARE_HYPERVISOR_MAGIC),
-				"b" (in1),
-				"c" (cmd),
-				"d" (in3),
-				"S" (in4),
-				"D" (in5)
-				: "cc", "memory");
-		break;
-	default:
-		asm_inline volatile ("movw %[port], %%dx; inl (%%dx), %%eax"
-				: "=a" (out0), "=b" (rbx), "=c" (rcx),
-				"=d" (rdx), "=S" (rsi), "=D" (rdi)
-				: [port] "i" (VMWARE_HYPERVISOR_PORT),
-				"a" (VMWARE_HYPERVISOR_MAGIC),
-				"b" (in1),
-				"c" (cmd),
-				"d" (in3),
-				"S" (in4),
-				"D" (in5)
-				: "cc", "memory");
-		break;
-	}
+static u8 vmware_hypercall_mode     __initdata;
+
+static unsigned long vmware_backdoor_hypercall(unsigned long cmd,
+			       unsigned long in1, unsigned long in3,
+			       unsigned long in4, unsigned long in5,
+			       u32 *out1, u32 *out2, u32 *out3,
+			       u32 *out4, u32 *out5)
+{
+	unsigned long out0;
+
+	/* The low word of in3(%edx) must have the backdoor port number */
+	in3 = (in3 & ~0xffff) | VMWARE_HYPERVISOR_PORT;
+
+	asm_inline volatile ("inl (%%dx), %%eax"
+		: "=a" (out0), "=b" (*out1), "=c" (*out2),
+		  "=d" (*out3), "=S" (*out4), "=D" (*out5)
+		: "a" (VMWARE_HYPERVISOR_MAGIC),
+		  "b" (in1),
+		  "c" (cmd),
+		  "d" (in3),
+		  "S" (in4),
+		  "D" (in5)
+		: "cc", "memory");
 
-	if (out1)
-		*out1 = rbx;
-	if (out2)
-		*out2 = rcx;
-	if (out3)
-		*out3 = rdx;
-	if (out4)
-		*out4 = rsi;
-	if (out5)
-		*out5 = rdi;
+	return out0;
+}
+
+static unsigned long vmware_vmcall_hypercall(unsigned long cmd,
+			       unsigned long in1, unsigned long in3,
+			       unsigned long in4, unsigned long in5,
+			       u32 *out1, u32 *out2, u32 *out3,
+			       u32 *out4, u32 *out5)
+{
+	unsigned long out0;
+
+	/* The low word of in3(%edx) must be zero: LB, IN */
+	in3 &= ~0xffff;
+
+	asm_inline volatile ("vmcall"
+		: "=a" (out0), "=b" (*out1), "=c" (*out2),
+		  "=d" (*out3), "=S" (*out4), "=D" (*out5)
+		: "a" (VMWARE_HYPERVISOR_MAGIC),
+		  "b" (in1),
+		  "c" (cmd),
+		  "d" (in3),
+		  "S" (in4),
+		  "D" (in5)
+		: "cc", "memory");
 
 	return out0;
 }
 
+static unsigned long vmware_vmmcall_hypercall(unsigned long cmd,
+			       unsigned long in1, unsigned long in3,
+			       unsigned long in4, unsigned long in5,
+			       u32 *out1, u32 *out2, u32 *out3,
+			       u32 *out4, u32 *out5)
+{
+	unsigned long out0;
+
+	/* The low word of in3(%edx) must be zero: LB, IN */
+	in3 &= ~0xffff;
+
+	asm_inline volatile ("vmmcall"
+		: "=a" (out0), "=b" (*out1), "=c" (*out2),
+		  "=d" (*out3), "=S" (*out4), "=D" (*out5)
+		: "a" (VMWARE_HYPERVISOR_MAGIC),
+		  "b" (in1),
+		  "c" (cmd),
+		  "d" (in3),
+		  "S" (in4),
+		  "D" (in5)
+		: "cc", "memory");
+
+	return out0;
+}
+
+/*
+ * TDCALL[TDG.VP.VMCALL] uses %rax (arg0) and %rcx (arg2). Therefore,
+ * we remap those registers to %r12 and %r13, respectively.
+ */
+static unsigned long vmware_tdx_hypercall(unsigned long cmd,
+				   unsigned long in1, unsigned long in3,
+				   unsigned long in4, unsigned long in5,
+				   u32 *out1, u32 *out2, u32 *out3,
+				   u32 *out4, u32 *out5)
+{
+#ifdef CONFIG_INTEL_TDX_GUEST
+	struct tdx_module_args args = {};
+
+	if (!hypervisor_is_type(X86_HYPER_VMWARE)) {
+		pr_warn_once("Incorrect usage\n");
+		return ULONG_MAX;
+	}
+
+	if (cmd & ~VMWARE_CMD_MASK) {
+		pr_warn_once("Out of range command %lx\n", cmd);
+		return ULONG_MAX;
+	}
+
+	args.rbx = in1;
+	/* The low word of in3(%rdx) must be zero: LB, IN */
+	args.rdx = in3 & ~0xffff;
+	args.rsi = in4;
+	args.rdi = in5;
+	args.r10 = VMWARE_TDX_VENDOR_LEAF;
+	args.r11 = VMWARE_TDX_HCALL_FUNC;
+	args.r12 = VMWARE_HYPERVISOR_MAGIC;
+	args.r13 = cmd;
+	/* CPL */
+	args.r15 = 0;
+
+	__tdx_hypercall(&args);
+
+	*out1 = args.rbx;
+	*out2 = args.r13;
+	*out3 = args.rdx;
+	*out4 = args.rsi;
+	*out5 = args.rdi;
+
+	return args.r12;
+#else
+	return ULONG_MAX;
+#endif
+}
+
+
+DEFINE_STATIC_CALL(vmware_hypercall, vmware_backdoor_hypercall);
+EXPORT_STATIC_CALL_GPL(vmware_hypercall);
+
+/*
+ * Perform backdoor probbing of the hypervisor when
+ * X86_FEATURE_HYPERVISOR bit is not set.
+ */
 static inline int __vmware_platform(void)
 {
 	u32 eax, ebx, ecx;
@@ -397,11 +467,35 @@ static void __init vmware_set_capabilities(void)
 		setup_force_cpu_cap(X86_FEATURE_VMW_VMMCALL);
 }
 
+static void __init vmware_select_hypercall(void)
+{
+	char *mode;
+
+	if (IS_ENABLED(CONFIG_INTEL_TDX_GUEST) &&
+	    cpu_feature_enabled(X86_FEATURE_TDX_GUEST)) {
+		static_call_update(vmware_hypercall, vmware_tdx_hypercall);
+		mode = "tdcall";
+	} else if (vmware_hypercall_mode == CPUID_VMWARE_FEATURES_ECX_VMCALL) {
+		static_call_update(vmware_hypercall, vmware_vmcall_hypercall);
+		mode = "vmcall";
+	} else if (vmware_hypercall_mode == CPUID_VMWARE_FEATURES_ECX_VMMCALL) {
+		static_call_update(vmware_hypercall, vmware_vmmcall_hypercall);
+		mode = "vmmcall";
+	} else {
+		mode = "backdoor";
+	}
+
+	pr_info("hypercall mode: %s\n", mode);
+}
+
 static void __init vmware_platform_setup(void)
 {
 	u32 eax, ebx, ecx;
 	u64 lpj, tsc_khz;
 
+	/* Update vmware_hypercall() before the first use. */
+	vmware_select_hypercall();
+
 	eax = vmware_hypercall3(VMWARE_CMD_GETHZ, UINT_MAX, &ebx, &ecx);
 
 	if (ebx != UINT_MAX) {
@@ -443,7 +537,7 @@ static void __init vmware_platform_setup(void)
 	vmware_set_capabilities();
 }
 
-static u8 __init vmware_select_hypercall(void)
+static u8 __init get_hypercall_mode(void)
 {
 	int eax, ebx, ecx, edx;
 
@@ -456,8 +550,8 @@ static u8 __init vmware_select_hypercall(void)
  * While checking the dmi string information, just checking the product
  * serial key should be enough, as this will always have a VMware
  * specific string when running under VMware hypervisor.
- * If !boot_cpu_has(X86_FEATURE_HYPERVISOR), vmware_hypercall_mode
- * intentionally defaults to 0.
+ * If !boot_cpu_has(X86_FEATURE_HYPERVISOR), __vmware_platform()
+ * intentionally defaults to backdoor hypercall.
  */
 static u32 __init vmware_platform(void)
 {
@@ -470,11 +564,7 @@ static u32 __init vmware_platform(void)
 		if (!memcmp(hyper_vendor_id, "VMwareVMware", 12)) {
 			if (eax >= CPUID_VMWARE_FEATURES_LEAF)
 				vmware_hypercall_mode =
-					vmware_select_hypercall();
-
-			pr_info("hypercall mode: 0x%02x\n",
-				(unsigned int) vmware_hypercall_mode);
-
+					get_hypercall_mode();
 			return CPUID_VMWARE_INFO_LEAF;
 		}
 	} else if (dmi_available && dmi_name_in_serial("VMware") &&
@@ -494,58 +584,6 @@ static bool __init vmware_legacy_x2apic_available(void)
 		(eax & GETVCPU_INFO_LEGACY_X2APIC);
 }
 
-#ifdef CONFIG_INTEL_TDX_GUEST
-/*
- * TDCALL[TDG.VP.VMCALL] uses %rax (arg0) and %rcx (arg2). Therefore,
- * we remap those registers to %r12 and %r13, respectively.
- */
-unsigned long vmware_tdx_hypercall(unsigned long cmd,
-				   unsigned long in1, unsigned long in3,
-				   unsigned long in4, unsigned long in5,
-				   u32 *out1, u32 *out2, u32 *out3,
-				   u32 *out4, u32 *out5)
-{
-	struct tdx_module_args args = {};
-
-	if (!hypervisor_is_type(X86_HYPER_VMWARE)) {
-		pr_warn_once("Incorrect usage\n");
-		return ULONG_MAX;
-	}
-
-	if (cmd & ~VMWARE_CMD_MASK) {
-		pr_warn_once("Out of range command %lx\n", cmd);
-		return ULONG_MAX;
-	}
-
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
-	__tdx_hypercall(&args);
-
-	if (out1)
-		*out1 = args.rbx;
-	if (out2)
-		*out2 = args.r13;
-	if (out3)
-		*out3 = args.rdx;
-	if (out4)
-		*out4 = args.rsi;
-	if (out5)
-		*out5 = args.rdi;
-
-	return args.r12;
-}
-EXPORT_SYMBOL_GPL(vmware_tdx_hypercall);
-#endif
-
 #ifdef CONFIG_AMD_MEM_ENCRYPT
 static void vmware_sev_es_hcall_prepare(struct ghcb *ghcb,
 					struct pt_regs *regs)

---

## [10] Alexey Makhalov — 2026-03-09
*Subject: [PATCH v2 2/4] x86/vmware: Log kmsg dump on panic*

Improve debugability of VMware Linux guests by dumping
kernel messages during a panic to VM log file (vmware.log).

Co-developed-by: Bo Gan <bo.gan@broadcom.com>
Signed-off-by: Bo Gan <bo.gan@broadcom.com>
Signed-off-by: Alexey Makhalov <alexey.makhalov@broadcom.com>
---
 arch/x86/include/asm/vmware.h |   1 +
 arch/x86/kernel/cpu/vmware.c  | 132 ++++++++++++++++++++++++++++++++++
 2 files changed, 133 insertions(+)

diff --git a/arch/x86/include/asm/vmware.h b/arch/x86/include/asm/vmware.h
index 6a084e088b30..c23164503e54 100644
--- a/arch/x86/include/asm/vmware.h
+++ b/arch/x86/include/asm/vmware.h
@@ -93,6 +93,7 @@
 #define VMWARE_HYPERVISOR_MAGIC		0x564d5868U
 
 #define VMWARE_CMD_GETVERSION		10
+#define VMWARE_CMD_MESSAGE		30
 #define VMWARE_CMD_GETHZ		45
 #define VMWARE_CMD_GETVCPU_INFO		68
 #define VMWARE_CMD_STEALCLOCK		91
diff --git a/arch/x86/kernel/cpu/vmware.c b/arch/x86/kernel/cpu/vmware.c
index 93acd3414e37..9955f2ea0c84 100644
--- a/arch/x86/kernel/cpu/vmware.c
+++ b/arch/x86/kernel/cpu/vmware.c
@@ -30,6 +30,7 @@
 #include <linux/reboot.h>
 #include <linux/static_call.h>
 #include <linux/sched/cputime.h>
+#include <linux/kmsg_dump.h>
 #include <asm/div64.h>
 #include <asm/x86_init.h>
 #include <asm/hypervisor.h>
@@ -211,6 +212,13 @@ static unsigned long vmware_get_tsc_khz(void)
 	return vmware_tsc_khz;
 }
 
+static void kmsg_dumper_vmware_log(struct kmsg_dumper *dumper,
+				   struct kmsg_dump_detail *detail);
+
+static struct kmsg_dumper kmsg_dumper = {
+	.dump = kmsg_dumper_vmware_log
+};
+
 #ifdef CONFIG_PARAVIRT
 static struct cyc2ns_data vmware_cyc2ns __ro_after_init;
 static bool vmw_sched_clock __initdata = true;
@@ -535,6 +543,8 @@ static void __init vmware_platform_setup(void)
 #endif
 
 	vmware_set_capabilities();
+
+	kmsg_dump_register(&kmsg_dumper);
 }
 
 static u8 __init get_hypercall_mode(void)
@@ -630,3 +640,125 @@ const __initconst struct hypervisor_x86 x86_hyper_vmware = {
 	.runtime.sev_es_hcall_finish	= vmware_sev_es_hcall_finish,
 #endif
 };
+
+#define VMWARE_HB_CMD_MESSAGE	0
+#define MESSAGE_STATUS_SUCCESS	(0x01 << 16)
+#define MESSAGE_STATUS_CPT	(0x10 << 16)
+#define MESSAGE_STATUS_HB	(0x80 << 16)
+
+#define RPCI_PROTOCOL_NUM	0x49435052 /* 'RPCI' */
+#define GUESTMSG_FLAG_COOKIE	0x80000000
+
+#define MESSAGE_TYPE_OPEN	(0 << 16)
+#define MESSAGE_TYPE_SENDSIZE	(1 << 16)
+#define MESSAGE_TYPE_SEND	(2 << 16)
+#define MESSAGE_TYPE_CLOSE	(6 << 16)
+
+struct vmw_msg {
+	u32 id;
+	u32 cookie_high;
+	u32 cookie_low;
+};
+
+static int
+vmware_log_open(struct vmw_msg *msg)
+{
+	u32 info;
+
+	vmware_hypercall6(VMWARE_CMD_MESSAGE | MESSAGE_TYPE_OPEN,
+			  RPCI_PROTOCOL_NUM | GUESTMSG_FLAG_COOKIE,
+			  0, &info, &msg->id, &msg->cookie_high,
+			  &msg->cookie_low);
+
+	if ((info & MESSAGE_STATUS_SUCCESS) == 0)
+		return 1;
+
+	msg->id &= 0xffff0000UL;
+	return 0;
+}
+
+static int
+vmware_log_close(struct vmw_msg *msg)
+{
+	u32 info;
+
+	vmware_hypercall5(VMWARE_CMD_MESSAGE | MESSAGE_TYPE_CLOSE, 0, msg->id,
+			  msg->cookie_high, msg->cookie_low, &info);
+
+	if ((info & MESSAGE_STATUS_SUCCESS) == 0)
+		return 1;
+	return 0;
+}
+
+static int
+vmware_log_send(struct vmw_msg *msg, const char *string)
+{
+	u32 info;
+	u32 len = strlen(string);
+
+retry:
+	vmware_hypercall5(VMWARE_CMD_MESSAGE | MESSAGE_TYPE_SENDSIZE, len,
+			  msg->id, msg->cookie_high, msg->cookie_low, &info);
+
+	if (!(info & MESSAGE_STATUS_SUCCESS))
+		return 1;
+
+	/* HB port can't access encrypted memory. */
+	if (!cc_platform_has(CC_ATTR_MEM_ENCRYPT) && (info & MESSAGE_STATUS_HB)) {
+		vmware_hypercall_hb_out(
+			VMWARE_HB_CMD_MESSAGE | MESSAGE_STATUS_SUCCESS,
+			len, msg->id, (uintptr_t) string, msg->cookie_low,
+			msg->cookie_high, &info);
+	} else {
+		do {
+			u32 word;
+			size_t s = min_t(u32, len, sizeof(word));
+
+			memcpy(&word, string, s);
+			len -= s;
+			string += s;
+
+			vmware_hypercall5(VMWARE_CMD_MESSAGE | MESSAGE_TYPE_SEND,
+					  word, msg->id, msg->cookie_high,
+					  msg->cookie_low, &info);
+		} while (len && (info & MESSAGE_STATUS_SUCCESS));
+	}
+
+	if ((info & MESSAGE_STATUS_SUCCESS) == 0) {
+		if (info & MESSAGE_STATUS_CPT)
+			/* A checkpoint occurred. Retry. */
+			goto retry;
+		return 1;
+	}
+	return 0;
+}
+STACK_FRAME_NON_STANDARD(vmware_log_send);
+
+/*
+ * kmsg_dumper_vmware_log - dumps kmsg to vmware.log file on the host
+ */
+static void kmsg_dumper_vmware_log(struct kmsg_dumper *dumper,
+				   struct kmsg_dump_detail *detail)
+{
+	struct vmw_msg msg;
+	struct kmsg_dump_iter iter;
+	static char line[1024];
+	size_t len = 0;
+
+	/* Line prefix to send to VM log file. */
+	line[0] = 'l';
+	line[1] = 'o';
+	line[2] = 'g';
+	line[3] = ' ';
+
+	kmsg_dump_rewind(&iter);
+	while (kmsg_dump_get_line(&iter, true, line + 4, sizeof(line) - 4,
+				  &len)) {
+		line[len + 4] = '\0';
+		if (vmware_log_open(&msg))
+			return;
+		if (vmware_log_send(&msg, line))
+			return;
+		vmware_log_close(&msg);
+	}
+}

---

## [11] Alexey Makhalov — 2026-03-09
*Subject: [PATCH v2 3/4] x86/vmware: Report guest crash to the hypervisor*

Register the guest crash reporter to panic_notifier_list,
which will be called at panic time. Guest crash reporter
will report the crash to the hypervisor through
a hypercall.

Co-developed-by: Brennan Lamoreaux <brennan.lamoreaux@broadcom.com>
Signed-off-by: Brennan Lamoreaux <brennan.lamoreaux@broadcom.com>
Signed-off-by: Alexey Makhalov <alexey.makhalov@broadcom.com>
---
 arch/x86/include/asm/vmware.h |  1 +
 arch/x86/kernel/cpu/vmware.c  | 21 +++++++++++++++++++++
 2 files changed, 22 insertions(+)

diff --git a/arch/x86/include/asm/vmware.h b/arch/x86/include/asm/vmware.h
index c23164503e54..bf6141353774 100644
--- a/arch/x86/include/asm/vmware.h
+++ b/arch/x86/include/asm/vmware.h
@@ -97,6 +97,7 @@
 #define VMWARE_CMD_GETHZ		45
 #define VMWARE_CMD_GETVCPU_INFO		68
 #define VMWARE_CMD_STEALCLOCK		91
+#define VMWARE_CMD_REPORTGUESTCRASH	102
 /*
  * Hypercall command mask:
  *   bits [6:0] command, range [0, 127]
diff --git a/arch/x86/kernel/cpu/vmware.c b/arch/x86/kernel/cpu/vmware.c
index 9955f2ea0c84..c631e577348a 100644
--- a/arch/x86/kernel/cpu/vmware.c
+++ b/arch/x86/kernel/cpu/vmware.c
@@ -31,6 +31,7 @@
 #include <linux/static_call.h>
 #include <linux/sched/cputime.h>
 #include <linux/kmsg_dump.h>
+#include <linux/panic_notifier.h>
 #include <asm/div64.h>
 #include <asm/x86_init.h>
 #include <asm/hypervisor.h>
@@ -451,6 +452,24 @@ static void __init vmware_paravirt_ops_setup(void)
 #define vmware_paravirt_ops_setup() do {} while (0)
 #endif
 
+static int vmware_report_guest_crash(struct notifier_block *self,
+				     unsigned long action, void *data)
+{
+	vmware_hypercall1(VMWARE_CMD_REPORTGUESTCRASH, 0);
+	return 0;
+}
+
+static struct notifier_block guest_crash_reporter = {
+	.notifier_call = vmware_report_guest_crash
+};
+
+static int __init register_guest_crash_reporter(void)
+{
+	atomic_notifier_chain_register(&panic_notifier_list,
+					&guest_crash_reporter);
+
+	return 0;
+}
 /*
  * VMware hypervisor takes care of exporting a reliable TSC to the guest.
  * Still, due to timing difference when running on virtual cpus, the TSC can
@@ -545,6 +564,8 @@ static void __init vmware_platform_setup(void)
 	vmware_set_capabilities();
 
 	kmsg_dump_register(&kmsg_dumper);
+
+	register_guest_crash_reporter();
 }
 
 static u8 __init get_hypercall_mode(void)

---

## [12] Alexey Makhalov — 2026-03-09
*Subject: [PATCH v2 4/4] x86/vmware: Support steal time clock for encrypted guests*

Shared memory containing steal time counter should be set to
decrypted when guest memory is encrypted.

Co-developed-by: Bo Gan <bo.gan@broadcom.com>
Signed-off-by: Bo Gan <bo.gan@broadcom.com>
Signed-off-by: Alexey Makhalov <alexey.makhalov@broadcom.com>
---
 arch/x86/kernel/cpu/vmware.c | 41 ++++++++++++++++++++++++++++++++++++
 1 file changed, 41 insertions(+)

diff --git a/arch/x86/kernel/cpu/vmware.c b/arch/x86/kernel/cpu/vmware.c
index c631e577348a..523a9b99847d 100644
--- a/arch/x86/kernel/cpu/vmware.c
+++ b/arch/x86/kernel/cpu/vmware.c
@@ -32,6 +32,7 @@
 #include <linux/sched/cputime.h>
 #include <linux/kmsg_dump.h>
 #include <linux/panic_notifier.h>
+#include <linux/set_memory.h>
 #include <asm/div64.h>
 #include <asm/x86_init.h>
 #include <asm/hypervisor.h>
@@ -39,6 +40,7 @@
 #include <asm/apic.h>
 #include <asm/vmware.h>
 #include <asm/svm.h>
+#include <asm/coco.h>
 
 #undef pr_fmt
 #define pr_fmt(fmt)	"vmware: " fmt
@@ -379,9 +381,47 @@ static struct notifier_block vmware_pv_reboot_nb = {
 	.notifier_call = vmware_pv_reboot_notify,
 };
 
+/*
+ * Map per-CPU variables for all possible CPUs as decrypted.
+ * Do this early in boot, before sharing the corresponding
+ * guest physical addresses with the hypervisor.
+ */
+static void __init set_shared_memory_decrypted(void)
+{
+	int cpu;
+
+	if (!cc_platform_has(CC_ATTR_GUEST_MEM_ENCRYPT))
+		return;
+
+	for_each_possible_cpu(cpu) {
+		unsigned long size = sizeof(vmw_steal_time);
+		unsigned long addr = (unsigned long)&per_cpu(vmw_steal_time,
+							cpu);
+
+		/*
+		 * There is no generic high-level API to mark memory as
+		 * decrypted. Intel's set_memory_decrypted() depends on the
+		 * buddy allocator and can fail early in boot if a page split
+		 * is required and allocation is not possible. Use AMD's
+		 * early_set_memory_decrypted() instead, which can perform
+		 * the split during early boot.
+		 */
+		early_set_memory_decrypted(addr, size);
+
+		/* That's it for AMD */
+		if (cc_vendor == CC_VENDOR_AMD)
+			continue;
+
+		set_memory_decrypted(addr & PAGE_MASK, 1UL <<
+				     get_order((addr & ~PAGE_MASK) + size));
+
+	}
+}
+
 #ifdef CONFIG_SMP
 static void __init vmware_smp_prepare_boot_cpu(void)
 {
+	set_shared_memory_decrypted();
 	vmware_guest_cpu_init();
 	native_smp_prepare_boot_cpu();
 }
@@ -444,6 +484,7 @@ static void __init vmware_paravirt_ops_setup(void)
 					      vmware_cpu_down_prepare) < 0)
 			pr_err("vmware_guest: Failed to install cpu hotplug callbacks\n");
 #else
+		set_shared_memory_decrypted();
 		vmware_guest_cpu_init();
 #endif
 	}

---

## [13] Alexey Makhalov — 2026-05-18
*Subject: Re: [PATCH v2 0/4] x86/vmware: Hypercall refactoring and improved
 guest support*

On 3/9/26 4:52 PM, Alexey Makhalov wrote:
> This series improves VMware guest support on x86 by refactoring the
> hypercall infrastructure and adding better crash diagnostics, along

Gentle reminder to review this change. Thanks,
--Alexey

---
