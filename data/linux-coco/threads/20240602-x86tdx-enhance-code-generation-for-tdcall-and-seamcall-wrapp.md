---
title: 'x86/tdx: Enhance code generation for TDCALL and SEAMCALL wrappers'
date: 2024-06-02
last_reply: 2024-09-11
message_count: 6
participants: ['Kirill A. Shutemov', 'Dave Hansen', 'Sean Christopherson', 'Edgecombe, Rick P']
---

## [1] Kirill A. Shutemov — 2024-06-02

Sean observed that the compiler is generating inefficient code to clear
the tdx_module_args struct for TDCALL and SEAMCALL wrappers. The
compiler is generating numerous instructions at each call site to clear
the unused fields of the structure.

To address this issue, avoid using C99-initializer and instead
explicitly use string instructions to clear the struct.

With Clang, this change results in a savings of approximately 3K with my
configuration:

add/remove: 0/0 grow/shrink: 0/21 up/down: 0/-3187 (-3187)

With GCC, the savings are less significant at around 300 bytes:

add/remove: 0/0 grow/shrink: 3/22 up/down: 17/-313 (-296)

GCC tends to generate string instructions more frequently to clear the
struct.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Suggested-by: Dave Hansen <dave.hansen@linux.intel.com>
Cc: Sean Christopherson <seanjc@google.com>
---
 arch/x86/boot/compressed/tdx.c    |  32 ++++---
 arch/x86/coco/tdx/tdx-shared.c    |   3 +-
 arch/x86/coco/tdx/tdx.c           | 150 +++++++++++++++++-------------
 arch/x86/hyperv/ivm.c             |  33 ++++---
 arch/x86/include/asm/shared/tdx.h |  25 +++--
 arch/x86/virt/vmx/tdx/tdx.c       |  28 +++---
 6 files changed, 155 insertions(+), 116 deletions(-)

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
index c1cb90369915..8112b2910ca2 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -49,13 +49,14 @@ noinstr void __noreturn __tdx_hypercall_failed(void)
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
@@ -89,13 +90,14 @@ static inline void tdcall(u64 fn, struct tdx_module_args *args)
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
@@ -130,11 +132,7 @@ EXPORT_SYMBOL_GPL(tdx_hcall_get_quote);
 
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
@@ -145,6 +143,11 @@ static void __noreturn tdx_panic(const char *msg)
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
@@ -165,10 +168,12 @@ static void __noreturn tdx_panic(const char *msg)
 
 static void tdx_parse_tdinfo(u64 *cc_mask)
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
@@ -252,11 +257,12 @@ static int ve_instr_len(struct ve_info *ve)
 
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
@@ -296,11 +302,12 @@ void __cpuidle tdx_safe_halt(void)
 
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
@@ -317,12 +324,13 @@ static int read_msr(struct pt_regs *regs, struct ve_info *ve)
 
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
@@ -337,12 +345,13 @@ static int write_msr(struct pt_regs *regs, struct ve_info *ve)
 
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
@@ -379,14 +388,15 @@ static int handle_cpuid(struct pt_regs *regs, struct ve_info *ve)
 
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
@@ -508,16 +518,17 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 
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
@@ -602,7 +613,9 @@ __init bool tdx_early_handle_ve(struct pt_regs *regs)
 
 void tdx_get_ve_info(struct ve_info *ve)
 {
-	struct tdx_module_args args = {};
+	struct tdx_module_args args;
+
+	tdx_arg_init(&args);
 
 	/*
 	 * Called during #VE handling to retrieve the #VE info from the
@@ -745,14 +758,16 @@ static bool tdx_map_gpa(phys_addr_t start, phys_addr_t end, bool enc)
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
@@ -824,10 +839,8 @@ static bool tdx_enc_status_change_finish(unsigned long vaddr, int numpages,
 
 void __init tdx_early_init(void)
 {
-	struct tdx_module_args args = {
-		.rdx = TDCS_NOTIFY_ENABLES,
-		.r9 = -1ULL,
-	};
+	struct tdx_module_args args;
+
 	u64 cc_mask;
 	u32 eax, sig[3];
 
@@ -846,6 +859,9 @@ void __init tdx_early_init(void)
 	cc_set_mask(cc_mask);
 
 	/* Kernel does not use NOTIFY_ENABLES and does not need random #VEs */
+	tdx_arg_init(&args);
+	args.rdx = TDCS_NOTIFY_ENABLES;
+	args.r9 = -1ULL;
 	tdcall(TDG_VM_WR, &args);
 
 	/*
diff --git a/arch/x86/hyperv/ivm.c b/arch/x86/hyperv/ivm.c
index 768d73de0d09..4a49d09b23ad 100644
--- a/arch/x86/hyperv/ivm.c
+++ b/arch/x86/hyperv/ivm.c
@@ -385,27 +385,31 @@ static inline void hv_ghcb_msr_read(u64 msr, u64 *value) {}
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
+	tdx_arg_init(&args);
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
@@ -415,8 +419,9 @@ static void hv_tdx_msr_read(u64 msr, u64 *val)
 
 u64 hv_tdx_hypercall(u64 control, u64 param1, u64 param2)
 {
-	struct tdx_module_args args = { };
+	struct tdx_module_args args;
 
+	tdx_arg_init(&args);
 	args.r10 = control;
 	args.rdx = param1;
 	args.r8  = param2;
diff --git a/arch/x86/include/asm/shared/tdx.h b/arch/x86/include/asm/shared/tdx.h
index fdfd41511b02..0519dd7cbb92 100644
--- a/arch/x86/include/asm/shared/tdx.h
+++ b/arch/x86/include/asm/shared/tdx.h
@@ -89,6 +89,14 @@ struct tdx_module_args {
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
@@ -103,14 +111,15 @@ u64 __tdx_hypercall(struct tdx_module_args *args);
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
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 4e2b2e2ac9f9..50d1ff9d874f 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -103,7 +103,7 @@ static inline int sc_retry_prerr(sc_func_t func, sc_err_func_t err_func,
  */
 static int try_init_module_global(void)
 {
-	struct tdx_module_args args = {};
+	struct tdx_module_args args;
 	static DEFINE_RAW_SPINLOCK(sysinit_lock);
 	static bool sysinit_done;
 	static int sysinit_ret;
@@ -115,6 +115,8 @@ static int try_init_module_global(void)
 	if (sysinit_done)
 		goto out;
 
+	tdx_arg_init(&args);
+
 	/* RCX is module attributes and all bits are reserved */
 	args.rcx = 0;
 	sysinit_ret = seamcall_prerr(TDH_SYS_INIT, &args);
@@ -146,7 +148,7 @@ static int try_init_module_global(void)
  */
 int tdx_cpu_enable(void)
 {
-	struct tdx_module_args args = {};
+	struct tdx_module_args args;
 	int ret;
 
 	if (!boot_cpu_has(X86_FEATURE_TDX_HOST_PLATFORM))
@@ -166,6 +168,7 @@ int tdx_cpu_enable(void)
 	if (ret)
 		return ret;
 
+	tdx_arg_init(&args);
 	ret = seamcall_prerr(TDH_SYS_LP_INIT, &args);
 	if (ret)
 		return ret;
@@ -252,7 +255,7 @@ static int build_tdx_memlist(struct list_head *tmb_list)
 
 static int read_sys_metadata_field(u64 field_id, u64 *data)
 {
-	struct tdx_module_args args = {};
+	struct tdx_module_args args;
 	int ret;
 
 	/*
@@ -260,6 +263,7 @@ static int read_sys_metadata_field(u64 field_id, u64 *data)
 	 *  - RDX (in): the field to read
 	 *  - R8 (out): the field data
 	 */
+	tdx_arg_init(&args);
 	args.rdx = field_id;
 	ret = seamcall_prerr_ret(TDH_SYS_RD, &args);
 	if (ret)
@@ -955,7 +959,7 @@ static int construct_tdmrs(struct list_head *tmb_list,
 
 static int config_tdx_module(struct tdmr_info_list *tdmr_list, u64 global_keyid)
 {
-	struct tdx_module_args args = {};
+	struct tdx_module_args args;
 	u64 *tdmr_pa_array;
 	size_t array_sz;
 	int i, ret;
@@ -977,6 +981,7 @@ static int config_tdx_module(struct tdmr_info_list *tdmr_list, u64 global_keyid)
 	for (i = 0; i < tdmr_list->nr_consumed_tdmrs; i++)
 		tdmr_pa_array[i] = __pa(tdmr_entry(tdmr_list, i));
 
+	tdx_arg_init(&args);
 	args.rcx = __pa(tdmr_pa_array);
 	args.rdx = tdmr_list->nr_consumed_tdmrs;
 	args.r8 = global_keyid;
@@ -990,8 +995,9 @@ static int config_tdx_module(struct tdmr_info_list *tdmr_list, u64 global_keyid)
 
 static int do_global_key_config(void *unused)
 {
-	struct tdx_module_args args = {};
+	struct tdx_module_args args;
 
+	tdx_arg_init(&args);
 	return seamcall_prerr(TDH_SYS_KEY_CONFIG, &args);
 }
 
@@ -1056,11 +1062,11 @@ static int init_tdmr(struct tdmr_info *tdmr)
 	 * TDMR in each call.
 	 */
 	do {
-		struct tdx_module_args args = {
-			.rcx = tdmr->base,
-		};
+		struct tdx_module_args args;
 		int ret;
 
+		tdx_arg_init(&args);
+		args.rcx = tdmr->base;
 		ret = seamcall_prerr_ret(TDH_SYS_TDMR_INIT, &args);
 		if (ret)
 			return ret;
@@ -1284,15 +1290,15 @@ static bool is_pamt_page(unsigned long phys)
  */
 static bool paddr_is_tdx_private(unsigned long phys)
 {
-	struct tdx_module_args args = {
-		.rcx = phys & PAGE_MASK,
-	};
+	struct tdx_module_args args;
 	u64 sret;
 
 	if (!boot_cpu_has(X86_FEATURE_TDX_HOST_PLATFORM))
 		return false;
 
 	/* Get page type from the TDX module */
+	tdx_arg_init(&args);
+	args.rcx = phys & PAGE_MASK;
 	sret = __seamcall_ret(TDH_PHYMEM_PAGE_RDMD, &args);
 
 	/*

---

## [2] Dave Hansen — 2024-06-03
*Subject: Re: [PATCH] x86/tdx: Enhance code generation for TDCALL and SEAMCALL
 wrappers*

On 6/2/24 04:54, Kirill A. Shutemov wrote:
> Sean observed that the compiler is generating inefficient code to clear
> the tdx_module_args struct for TDCALL and SEAMCALL wrappers. The

<shrug>

I don't think moving away from perfectly normal C struct initialization
is worth it for 300 bytes of text in couple of slow paths.

If someone out there is using clang, is confident that it is doing the
right thing and not just being silly, _and_ is horribly bothered by its
code generation, then please speak up.

> +static __always_inline void tdx_arg_init(struct tdx_module_args *args)
> +{

The inline assembly also has the side-effect of tripping up the
compiler.  The compiler can't optimize across these at all and it
probably has the effect of bloating the code.

Oh, and if we're going to leave this weirdo initialization idiom for
TDX, it needs to be well commented:

/*
 * Using normal " = {};" to initialize tdx_module_args results in
 * bloated hard-to-read assembly.  Zero it using the most compact way
 * available.
 */

Eh?

---

## [3] Kirill A. Shutemov — 2024-06-04
*Subject: Re: [PATCH] x86/tdx: Enhance code generation for TDCALL and SEAMCALL
 wrappers*

On Mon, Jun 03, 2024 at 06:37:45AM -0700, Dave Hansen wrote:
> On 6/2/24 04:54, Kirill A. Shutemov wrote:
> > Sean observed that the compiler is generating inefficient code to clear

Conceptually, I like my previous attempt more. But it is much more
intrusive and I am not sure it is worth the risk.

This patch feels like hack around compiler.

Sean, do you have any comments?

> > +static __always_inline void tdx_arg_init(struct tdx_module_args *args)
> > +{

It can, but it is limited. Compiler has to flush registers content back to
memory before asm() and cannot assume anything that read from memory
before the asm() is still valid after.
 
> Oh, and if we're going to leave this weirdo initialization idiom for
> TDX, it needs to be well commented:

Okay.

---

## [4] Sean Christopherson — 2024-06-04
*Subject: Re: [PATCH] x86/tdx: Enhance code generation for TDCALL and SEAMCALL wrappers*

On Tue, Jun 04, 2024, Kirill A. Shutemov wrote:
> On Mon, Jun 03, 2024 at 06:37:45AM -0700, Dave Hansen wrote:
> > On 6/2/24 04:54, Kirill A. Shutemov wrote:

Yes :-)

1. Y'all *really* need to actually look at the generated code, because this is
   amusingly broken.

diff --git a/arch/x86/include/asm/shared/tdx.h b/arch/x86/include/asm/shared/tdx.h
index 0519dd7cbb92..575cc54670ef 100644
--- a/arch/x86/include/asm/shared/tdx.h
+++ b/arch/x86/include/asm/shared/tdx.h
@@ -91,7 +91,7 @@ struct tdx_module_args {
 
 static __always_inline void tdx_arg_init(struct tdx_module_args *args)
 {
-       asm ("rep stosb"
+       asm volatile ("rep stosb"
             : "+D" (args)
             : "c" (sizeof(*args)), "a" (0)
             : "memory");

2. Look at *all* the code generation, because the code generation for TDX-as-a-guest
   as a whole is bad/confusing.  E.g. switching on ve->exit_reason in ve_instr_len()
   after doing the same in virt_exception_kernel() _could_ be optimized away, but
   in part because tdx_module_args generates so much code, gcc-13 at least tends
   to not inline the individual handlers, which in turn means ve_instr_len() doesn't
   get inlined because the compiler doesn't know that e.g. handle_cpuid() will
   only ever call ve_instr_len() with ve->exit_reason == EXIT_REASON_CPUID.

3. As Paolo pointed out[*], passing arguments vs. explicitly filling operands
   have different tradeoffs.  Explicitly filling operands is *visually* pleasing,
   but it's also prone to typos, and as evidenced by a data leak in mmio_read(),
   being able to easily audit the code doesn't mean squat unless someone actually
   does the audit (usually in response to a bug).

   static bool mmio_read(int size, unsigned long addr, unsigned long *val)
   {
	struct tdx_module_args args = {
		.r10 = TDX_HYPERCALL_STANDARD,
		.r11 = hcall_func(EXIT_REASON_EPT_VIOLATION),
		.r12 = size,
		.r13 = EPT_READ,
		.r14 = addr,
		.r15 = *val,    <==== data leak
	};

	if (__tdx_hypercall(&args))
		return false;

	*val = args.r11;
	return true;
   }

   [*] https://lore.kernel.org/all/611a387b-ba7e-46d7-b6bf-84dc6c037d33@redhat.com

3. Pick _one_ approach for the majority of TDVMCALLs.  The existing code is a mix
   of passing arguments (e.g. mmio_write()) and explicit operands (e.g. mmio_read()).
   There will inevitably be special snowflakes, e.g. for some asinine reason, CPUID
   skips r11 as an output.  But AFAICT, most TDVMCALLs conform to a standard
   pattern.

4. Using a trampoline probably isn't worth the marginal reduction in *written*
   code.  The generated code is almost as weird as the tdx_module_args code.
   E.g. each callsite generates a pile of MOV instructions to registers that
   *don't* match the GHCI, and so I doubt the end result would be any easier to
   debug for unsuspecting users.

If we're willing to suffer a few gnarly macros, I think we get a satisfactory mix
of standardized arguments and explicit operands, and generate vastly better code.

The macros are beyond ugly and are also error prone to some extent, but having to
add new macros should be quite rare, and much of the boilerplate could be stripped
away with even more macros.

And while the macros are ugly, the advantage of having to specify the number of
input and output operands reduces the probability of a data leak, e.g. the mmio_read()
bug wouldn't escape compilation because TDVMCALL_4_1() would be unhappy, and
TDVMCALL_5_1() doesn't need to exist.

Dump of assembler code for function tdx_handle_virt_exception:
   0xffffffff81003220 <+0>:	call   0xffffffff810577d0 <__fentry__>
   0xffffffff81003225 <+5>:	push   %r13
   0xffffffff81003227 <+7>:	push   %r12
   0xffffffff81003229 <+9>:	push   %rbp
   0xffffffff8100322a <+10>:	push   %rbx
   0xffffffff8100322b <+11>:	mov    %rdi,%rbx
   0xffffffff8100322e <+14>:	sub    $0x8,%rsp
   0xffffffff81003232 <+18>:	testb  $0x3,0x88(%rdi)
   0xffffffff81003239 <+25>:	mov    (%rsi),%rax
   0xffffffff8100323c <+28>:	je     0xffffffff81003269 <tdx_handle_virt_exception+73>
   0xffffffff8100323e <+30>:	cmp    $0xa,%rax
   0xffffffff81003242 <+34>:	jne    0xffffffff8100327a <tdx_handle_virt_exception+90>
   0xffffffff81003244 <+36>:	mov    %rbx,%rdi
   0xffffffff81003247 <+39>:	call   0xffffffff81002820 <handle_cpuid>
   0xffffffff8100324c <+44>:	test   %eax,%eax
   0xffffffff8100324e <+46>:	js     0xffffffff81003289 <tdx_handle_virt_exception+105>
   0xffffffff81003250 <+48>:	cltq
   0xffffffff81003252 <+50>:	add    %rax,0x80(%rbx)
   0xffffffff81003259 <+57>:	mov    $0x1,%eax
   0xffffffff8100325e <+62>:	add    $0x8,%rsp
   0xffffffff81003262 <+66>:	pop    %rbx
   0xffffffff81003263 <+67>:	pop    %rbp
   0xffffffff81003264 <+68>:	pop    %r12
   0xffffffff81003266 <+70>:	pop    %r13
   0xffffffff81003268 <+72>:	ret
   0xffffffff81003269 <+73>:	lea    -0xa(%rax),%rdx
   0xffffffff8100326d <+77>:	cmp    $0x26,%rdx
   0xffffffff81003271 <+81>:	ja     0xffffffff8100327a <tdx_handle_virt_exception+90>
   0xffffffff81003273 <+83>:	jmp    *-0x7e3ffd88(,%rdx,8)
   0xffffffff8100327a <+90>:	mov    %rax,%rsi
   0xffffffff8100327d <+93>:	mov    $0xffffffff81e6b0b6,%rdi
   0xffffffff81003284 <+100>:	call   0xffffffff810eb170 <_printk>
   0xffffffff81003289 <+105>:	xor    %eax,%eax
   0xffffffff8100328b <+107>:	jmp    0xffffffff8100325e <tdx_handle_virt_exception+62>
   0xffffffff8100328d <+109>:	mov    0x18(%rsi),%rbp
   0xffffffff81003291 <+113>:	mov    %rsi,(%rsp)
   0xffffffff81003295 <+117>:	mov    %rbp,%rdi
   0xffffffff81003298 <+120>:	call   0xffffffff81002700 <cc_mkenc>
   0xffffffff8100329d <+125>:	mov    (%rsp),%rsi
   0xffffffff810032a1 <+129>:	cmp    %rax,%rbp
   0xffffffff810032a4 <+132>:	je     0xffffffff81003376 <tdx_handle_virt_exception+342>
   0xffffffff810032aa <+138>:	mov    %rbx,%rdi
   0xffffffff810032ad <+141>:	call   0xffffffff81002e20 <handle_mmio>
   0xffffffff810032b2 <+146>:	jmp    0xffffffff8100324c <tdx_handle_virt_exception+44>
   0xffffffff810032b4 <+148>:	mov    0x60(%rdi),%rdx
   0xffffffff810032b8 <+152>:	xor    %eax,%eax
   0xffffffff810032ba <+154>:	mov    $0x3c00,%ecx
   0xffffffff810032bf <+159>:	shl    $0x20,%rdx
   0xffffffff810032c3 <+163>:	or     0x50(%rdi),%rdx
   0xffffffff810032c7 <+167>:	mov    $0x20,%r11
   0xffffffff810032ce <+174>:	mov    0x58(%rdi),%r12
   0xffffffff810032d2 <+178>:	mov    %rdx,%r13
   0xffffffff810032d5 <+181>:	xor    %r10d,%r10d
   0xffffffff810032d8 <+184>:	tdcall
   0xffffffff810032dc <+188>:	mov    %r10,%rcx
   0xffffffff810032df <+191>:	test   %rax,%rax
   0xffffffff810032e2 <+194>:	jne    0xffffffff81003371 <tdx_handle_virt_exception+337>
   0xffffffff810032e8 <+200>:	test   %rcx,%rcx
   0xffffffff810032eb <+203>:	jne    0xffffffff81003289 <tdx_handle_virt_exception+105>
   0xffffffff810032ed <+205>:	mov    0x20(%rsi),%eax
   0xffffffff810032f0 <+208>:	jmp    0xffffffff8100324c <tdx_handle_virt_exception+44>
   0xffffffff810032f5 <+213>:	xor    %eax,%eax
   0xffffffff810032f7 <+215>:	mov    $0x1c00,%ecx
   0xffffffff810032fc <+220>:	mov    $0x1f,%r11
   0xffffffff81003303 <+227>:	mov    0x58(%rdi),%r12
   0xffffffff81003307 <+231>:	xor    %r10d,%r10d
   0xffffffff8100330a <+234>:	tdcall
   0xffffffff8100330e <+238>:	mov    %r10,%rcx
   0xffffffff81003311 <+241>:	mov    %r11,%rdx
   0xffffffff81003314 <+244>:	test   %rax,%rax
   0xffffffff81003317 <+247>:	jne    0xffffffff81003371 <tdx_handle_virt_exception+337>
   0xffffffff81003319 <+249>:	test   %rcx,%rcx
   0xffffffff8100331c <+252>:	jne    0xffffffff81003289 <tdx_handle_virt_exception+105>
   0xffffffff81003322 <+258>:	movq   $0x0,0x50(%rdi)
   0xffffffff8100332a <+266>:	movq   $0x0,0x60(%rdi)
   0xffffffff81003332 <+274>:	cmpq   $0x1f,(%rsi)
   0xffffffff81003336 <+278>:	je     0xffffffff810032ed <tdx_handle_virt_exception+205>
   0xffffffff81003338 <+280>:	ud2
   0xffffffff8100333a <+282>:	jmp    0xffffffff810032ed <tdx_handle_virt_exception+205>
   0xffffffff8100333c <+284>:	mov    %rsi,(%rsp)
   0xffffffff81003340 <+288>:	pushf
   0xffffffff81003341 <+289>:	pop    %rdi
   0xffffffff81003342 <+290>:	shr    $0x9,%rdi
   0xffffffff81003346 <+294>:	xor    $0x1,%rdi
   0xffffffff8100334a <+298>:	and    $0x1,%edi
   0xffffffff8100334d <+301>:	call   0xffffffff81949c00 <__halt>
   0xffffffff81003352 <+306>:	test   %rax,%rax
   0xffffffff81003355 <+309>:	jne    0xffffffff81003289 <tdx_handle_virt_exception+105>
   0xffffffff8100335b <+315>:	mov    (%rsp),%rsi
   0xffffffff8100335f <+319>:	cmpq   $0xc,(%rsi)
   0xffffffff81003363 <+323>:	je     0xffffffff810032ed <tdx_handle_virt_exception+205>
   0xffffffff81003365 <+325>:	jmp    0xffffffff81003338 <tdx_handle_virt_exception+280>
   0xffffffff81003367 <+327>:	call   0xffffffff81002d20 <handle_io>
   0xffffffff8100336c <+332>:	jmp    0xffffffff8100324c <tdx_handle_virt_exception+44>
   0xffffffff81003371 <+337>:	call   0xffffffff81944440 <__tdx_hypercall_failed>
   0xffffffff81003376 <+342>:	mov    $0xffffffff81eab098,%rdi
   0xffffffff8100337d <+349>:	call   0xffffffff81080cf0 <panic>
End of assembler dump.

---
 arch/x86/boot/compressed/tdx.c    |  31 ++---
 arch/x86/coco/tdx/tdx.c           | 136 +++++++++-----------
 arch/x86/hyperv/ivm.c             |  26 +---
 arch/x86/include/asm/shared/tdx.h | 204 +++++++++++++++++++++++++++---
 4 files changed, 262 insertions(+), 135 deletions(-)

diff --git a/arch/x86/boot/compressed/tdx.c b/arch/x86/boot/compressed/tdx.c
index 8451d6a1030c..5a94cab412ed 100644
--- a/arch/x86/boot/compressed/tdx.c
+++ b/arch/x86/boot/compressed/tdx.c
@@ -18,32 +18,25 @@ void __tdx_hypercall_failed(void)
 
 static inline unsigned int tdx_io_in(int size, u16 port)
 {
-	struct tdx_module_args args = {
-		.r10 = TDX_HYPERCALL_STANDARD,
-		.r11 = hcall_func(EXIT_REASON_IO_INSTRUCTION),
-		.r12 = size,
-		.r13 = 0,
-		.r14 = port,
-	};
+	unsigned int val;
 
-	if (__tdx_hypercall(&args))
+	if (TDVMCALL_4_1(r11 = hcall_func(EXIT_REASON_IO_INSTRUCTION),
+			     r12 = size,
+			     r13 = 0,
+			     r14 = port,
+			     TDX_ON_SUCCESS(val = out_r11)))
 		return UINT_MAX;
 
-	return args.r11;
+	return val;
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
+	TDVMCALL_5_0(r11 = hcall_func(EXIT_REASON_IO_INSTRUCTION),
+		     r12 = size,
+		     r13 = 1,
+		     r14 = port,
+		     r15 = value);
 }
 
 static inline u8 tdx_inb(u16 port)
diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index c1cb90369915..b9f76445419c 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -124,7 +124,10 @@ EXPORT_SYMBOL_GPL(tdx_mcall_get_report0);
 u64 tdx_hcall_get_quote(u8 *buf, size_t size)
 {
 	/* Since buf is a shared memory, set the shared (decrypted) bits */
-	return _tdx_hypercall(TDVMCALL_GET_QUOTE, cc_mkdec(virt_to_phys(buf)), size, 0, 0);
+	return TDVMCALL_3_0(r11 = TDVMCALL_GET_QUOTE,
+			    r12 = cc_mkdec(virt_to_phys(buf)),
+			    r13 = size);
+	return 0;
 }
 EXPORT_SYMBOL_GPL(tdx_hcall_get_quote);
 
@@ -226,9 +229,11 @@ static void tdx_parse_tdinfo(u64 *cc_mask)
  * information if #VE occurred due to instruction execution, but not for EPT
  * violations.
  */
-static int ve_instr_len(struct ve_info *ve)
+static int ve_instr_len(u32 exit_reason, struct ve_info *ve)
 {
-	switch (ve->exit_reason) {
+	WARN_ON_ONCE(ve->exit_reason != exit_reason);
+
+	switch (exit_reason) {
 	case EXIT_REASON_HLT:
 	case EXIT_REASON_MSR_READ:
 	case EXIT_REASON_MSR_WRITE:
@@ -252,12 +257,6 @@ static int ve_instr_len(struct ve_info *ve)
 
 static u64 __cpuidle __halt(const bool irq_disabled)
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
@@ -270,7 +269,8 @@ static u64 __cpuidle __halt(const bool irq_disabled)
 	 * can keep the vCPU in virtual HLT, even if an IRQ is
 	 * pending, without hanging/breaking the guest.
 	 */
-	return __tdx_hypercall(&args);
+	return TDVMCALL_2_0(r11 = hcall_func(EXIT_REASON_HLT),
+			    r12 = irq_disabled);
 }
 
 static int handle_halt(struct ve_info *ve)
@@ -280,7 +280,7 @@ static int handle_halt(struct ve_info *ve)
 	if (__halt(irq_disabled))
 		return -EIO;
 
-	return ve_instr_len(ve);
+	return ve_instr_len(EXIT_REASON_HLT, ve);
 }
 
 void __cpuidle tdx_safe_halt(void)
@@ -296,43 +296,37 @@ void __cpuidle tdx_safe_halt(void)
 
 static int read_msr(struct pt_regs *regs, struct ve_info *ve)
 {
-	struct tdx_module_args args = {
-		.r10 = TDX_HYPERCALL_STANDARD,
-		.r11 = hcall_func(EXIT_REASON_MSR_READ),
-		.r12 = regs->cx,
-	};
+	u64 val = 0;
 
 	/*
 	 * Emulate the MSR read via hypercall. More info about ABI
 	 * can be found in TDX Guest-Host-Communication Interface
 	 * (GHCI), section titled "TDG.VP.VMCALL<Instruction.RDMSR>".
 	 */
-	if (__tdx_hypercall(&args))
+	if (TDVMCALL_2_1(r11 = hcall_func(EXIT_REASON_MSR_READ),
+			 r12 = regs->cx,
+			 TDX_ON_SUCCESS(val = out_r11)))
 		return -EIO;
 
-	regs->ax = lower_32_bits(args.r11);
-	regs->dx = upper_32_bits(args.r11);
-	return ve_instr_len(ve);
+	regs->ax = lower_32_bits(val);
+	regs->dx = upper_32_bits(val);
+
+	return ve_instr_len(EXIT_REASON_MSR_READ, ve);
 }
 
 static int write_msr(struct pt_regs *regs, struct ve_info *ve)
 {
-	struct tdx_module_args args = {
-		.r10 = TDX_HYPERCALL_STANDARD,
-		.r11 = hcall_func(EXIT_REASON_MSR_WRITE),
-		.r12 = regs->cx,
-		.r13 = (u64)regs->dx << 32 | regs->ax,
-	};
-
 	/*
 	 * Emulate the MSR write via hypercall. More info about ABI
 	 * can be found in TDX Guest-Host-Communication Interface
 	 * (GHCI) section titled "TDG.VP.VMCALL<Instruction.WRMSR>".
 	 */
-	if (__tdx_hypercall(&args))
+	if (TDVMCALL_3_0(r11 = hcall_func(EXIT_REASON_MSR_WRITE),
+			 r12 = regs->cx,
+			 r13 = (u64)regs->dx << 32 | regs->ax))
 		return -EIO;
 
-	return ve_instr_len(ve);
+	return ve_instr_len(EXIT_REASON_MSR_WRITE, ve);
 }
 
 static int handle_cpuid(struct pt_regs *regs, struct ve_info *ve)
@@ -353,7 +347,7 @@ static int handle_cpuid(struct pt_regs *regs, struct ve_info *ve)
 	 */
 	if (regs->ax < 0x40000000 || regs->ax > 0x4FFFFFFF) {
 		regs->ax = regs->bx = regs->cx = regs->dx = 0;
-		return ve_instr_len(ve);
+		return ve_instr_len(EXIT_REASON_CPUID, ve);
 	}
 
 	/*
@@ -374,31 +368,26 @@ static int handle_cpuid(struct pt_regs *regs, struct ve_info *ve)
 	regs->cx = args.r14;
 	regs->dx = args.r15;
 
-	return ve_instr_len(ve);
+	return ve_instr_len(EXIT_REASON_CPUID, ve);
 }
 
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
-
-	if (__tdx_hypercall(&args))
-		return false;
-
-	*val = args.r11;
-	return true;
+	return !TDVMCALL_4_1(r11 = hcall_func(EXIT_REASON_EPT_VIOLATION),
+			     r12 = size,
+			     r13 = EPT_READ,
+			     r14 = addr,
+			     TDX_ON_SUCCESS(*val = out_r11));
+	return false;
 }
 
 static bool mmio_write(int size, unsigned long addr, unsigned long val)
 {
-	return !_tdx_hypercall(hcall_func(EXIT_REASON_EPT_VIOLATION), size,
-			       EPT_WRITE, addr, val);
+	return !TDVMCALL_5_0(r11 = hcall_func(EXIT_REASON_EPT_VIOLATION),
+			     r12 = size,
+			     r13 = EPT_WRITE,
+			     r14 = addr,
+			     r15 = val);
 }
 
 static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
@@ -508,42 +497,37 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 
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
-	bool success;
-
-	/*
-	 * Emulate the I/O read via hypercall. More info about ABI can be found
-	 * in TDX Guest-Host-Communication Interface (GHCI) section titled
-	 * "TDG.VP.VMCALL<Instruction.IO>".
-	 */
-	success = !__tdx_hypercall(&args);
+	const u64 mask = GENMASK(BITS_PER_BYTE * size, 0);
 
 	/* Update part of the register affected by the emulated instruction */
 	regs->ax &= ~mask;
-	if (success)
-		regs->ax |= args.r11 & mask;
 
-	return success;
+	/*
+	 * Emulate the I/O read via hypercall. More info about ABI can be found
+	 * in TDX Guest-Host-Communication Interface (GHCI) section titled
+	 * "TDG.VP.VMCALL<Instruction.IO>".
+	 */
+	return !TDVMCALL_4_1(r11 = hcall_func(EXIT_REASON_IO_INSTRUCTION),
+			     r12 = size,
+			     r13 = PORT_READ,
+			     r14 = port,
+			     TDX_ON_SUCCESS(regs->ax |= out_r11 & mask));
 }
 
 static bool handle_out(struct pt_regs *regs, int size, int port)
 {
-	u64 mask = GENMASK(BITS_PER_BYTE * size, 0);
+	const u64 mask = GENMASK(BITS_PER_BYTE * size, 0);
 
 	/*
 	 * Emulate the I/O write via hypercall. More info about ABI can be found
 	 * in TDX Guest-Host-Communication Interface (GHCI) section titled
 	 * "TDG.VP.VMCALL<Instruction.IO>".
 	 */
-	return !_tdx_hypercall(hcall_func(EXIT_REASON_IO_INSTRUCTION), size,
-			       PORT_WRITE, port, regs->ax & mask);
+	return !TDVMCALL_5_0(r11 = hcall_func(EXIT_REASON_IO_INSTRUCTION),
+			     r12 = size,
+			     r13 = PORT_WRITE,
+			     r14 = port,
+			     r15 = regs->ax & mask);
 }
 
 /*
@@ -575,7 +559,7 @@ static int handle_io(struct pt_regs *regs, struct ve_info *ve)
 	if (!ret)
 		return -EIO;
 
-	return ve_instr_len(ve);
+	return ve_instr_len(EXIT_REASON_IO_INSTRUCTION, ve);
 }
 
 /*
@@ -745,14 +729,11 @@ static bool tdx_map_gpa(phys_addr_t start, phys_addr_t end, bool enc)
 	}
 
 	while (retry_count < max_retries_per_page) {
-		struct tdx_module_args args = {
-			.r10 = TDX_HYPERCALL_STANDARD,
-			.r11 = TDVMCALL_MAP_GPA,
-			.r12 = start,
-			.r13 = end - start };
-
 		u64 map_fail_paddr;
-		u64 ret = __tdx_hypercall(&args);
+		u64 ret = TDVMCALL_3_1(r11 = TDVMCALL_MAP_GPA,
+				       r12 = start,
+				       r13 = end - start,
+				       map_fail_paddr = out_r11);
 
 		if (ret != TDVMCALL_STATUS_RETRY)
 			return !ret;
@@ -761,7 +742,6 @@ static bool tdx_map_gpa(phys_addr_t start, phys_addr_t end, bool enc)
 		 * region starting at the GPA specified in R11. R11 comes
 		 * from the untrusted VMM. Sanity check it.
 		 */
-		map_fail_paddr = args.r11;
 		if (map_fail_paddr < start || map_fail_paddr >= end)
 			return false;
 
diff --git a/arch/x86/hyperv/ivm.c b/arch/x86/hyperv/ivm.c
index 768d73de0d09..4d51b8fde6b1 100644
--- a/arch/x86/hyperv/ivm.c
+++ b/arch/x86/hyperv/ivm.c
@@ -385,32 +385,20 @@ static inline void hv_ghcb_msr_read(u64 msr, u64 *value) {}
 #ifdef CONFIG_INTEL_TDX_GUEST
 static void hv_tdx_msr_write(u64 msr, u64 val)
 {
-	struct tdx_module_args args = {
-		.r10 = TDX_HYPERCALL_STANDARD,
-		.r11 = EXIT_REASON_MSR_WRITE,
-		.r12 = msr,
-		.r13 = val,
-	};
-
-	u64 ret = __tdx_hypercall(&args);
+	u64 ret = TDVMCALL_3_0(r11 = EXIT_REASON_MSR_WRITE,
+			       r12 = msr,
+			       r13 = val);
 
 	WARN_ONCE(ret, "Failed to emulate MSR write: %lld\n", ret);
 }
 
 static void hv_tdx_msr_read(u64 msr, u64 *val)
 {
-	struct tdx_module_args args = {
-		.r10 = TDX_HYPERCALL_STANDARD,
-		.r11 = EXIT_REASON_MSR_READ,
-		.r12 = msr,
-	};
+	u64 ret = TDVMCALL_2_1(r11 = hcall_func(EXIT_REASON_MSR_READ),
+			       r12 = msr,
+			       *val = out_r11);
 
-	u64 ret = __tdx_hypercall(&args);
-
-	if (WARN_ONCE(ret, "Failed to emulate MSR read: %lld\n", ret))
-		*val = 0;
-	else
-		*val = args.r11;
+	WARN_ONCE(ret, "Failed to emulate MSR read: %lld\n", ret);
 }
 
 u64 hv_tdx_hypercall(u64 control, u64 param1, u64 param2)
diff --git a/arch/x86/include/asm/shared/tdx.h b/arch/x86/include/asm/shared/tdx.h
index fdfd41511b02..c1354054f144 100644
--- a/arch/x86/include/asm/shared/tdx.h
+++ b/arch/x86/include/asm/shared/tdx.h
@@ -65,6 +65,191 @@
 
 #include <linux/compiler_attributes.h>
 
+#define TDVMCALL_BUG_ON(ret)							\
+do {										\
+	if (unlikely(ret))							\
+		__tdx_hypercall_failed();					\
+} while (0)
+
+#define TDX_ON_SUCCESS(x) if (__ret) (x)
+
+#define TDVMCALL_2_0(__in_r11, __in_r12)					\
+({										\
+	u64 vmcall_ret = TDG_VP_VMCALL;						\
+	u64 __in_r11, __in_r12;							\
+	u64 __ret;								\
+										\
+	asm volatile (								\
+		"movq	%[r11_in], %%r11\n\t"					\
+		"movq	%[r12_in], %%r12\n\t"					\
+		"xor    %%r10d, %%r10d\n\t"					\
+		".byte 0x66,0x0f,0x01,0xcc\n\t"					\
+		"movq	%%r10, %[r10_out]\n\t"					\
+		: "+a"(vmcall_ret),						\
+		  [r10_out] "=rm" (__ret)					\
+		: "c" (TDX_R10 | TDX_R11 | TDX_R12),				\
+		  [r11_in] "irm" (r11),						\
+		  [r12_in] "irm" (r12)						\
+		: "r10", "r11", "r12"						\
+	);									\
+										\
+	TDVMCALL_BUG_ON(vmcall_ret);						\
+										\
+	__ret;									\
+})
+
+#define TDVMCALL_2_1(__in_r11, __in_r12, __out_r11)				\
+({										\
+	u64 vmcall_ret = TDG_VP_VMCALL;						\
+	u64 __in_r11, __in_r12;							\
+	u64 out_r11;								\
+	u64 __ret;								\
+										\
+	asm volatile (								\
+		"movq	%[r11_in], %%r11\n\t"					\
+		"movq	%[r12_in], %%r12\n\t"					\
+		"xor    %%r10d, %%r10d\n\t"					\
+		".byte 0x66,0x0f,0x01,0xcc\n\t"					\
+		"movq	%%r10, %[r10_out]\n\t"					\
+		"movq	%%r11, %[r11_out]\n\t"					\
+		: "+a"(vmcall_ret),						\
+		  [r10_out] "=rm" (__ret),					\
+		  [r11_out] "=rm" (out_r11)					\
+		: "c" (TDX_R10 | TDX_R11 | TDX_R12),				\
+		  [r11_in] "irm" (r11),						\
+		  [r12_in] "irm" (r12)						\
+		: "r10", "r11", "r12"						\
+	);									\
+										\
+	TDVMCALL_BUG_ON(vmcall_ret);						\
+										\
+	__out_r11;								\
+	__ret;									\
+})
+
+#define TDVMCALL_3_0(__in_r11, __in_r12, __in_r13)				\
+({										\
+	u64 vmcall_ret = TDG_VP_VMCALL;						\
+	u64 __in_r11, __in_r12, __in_r13;					\
+	u64 __ret;								\
+										\
+	asm volatile (								\
+		"movq	%[r11_in], %%r11\n\t"					\
+		"movq	%[r12_in], %%r12\n\t"					\
+		"movq	%[r13_in], %%r13\n\t"					\
+		"xor    %%r10d, %%r10d\n\t"					\
+		".byte 0x66,0x0f,0x01,0xcc\n\t"					\
+		"movq	%%r10, %[r10_out]\n\t"					\
+		: "+a"(vmcall_ret),						\
+		  [r10_out] "=rm" (__ret)					\
+		: "c" (TDX_R10 | TDX_R11 | TDX_R12 | TDX_R13),			\
+		  [r11_in] "irm" (r11),						\
+		  [r12_in] "irm" (r12),						\
+		  [r13_in] "irm" (r13)						\
+		: "r10", "r11", "r12", "r13"					\
+	);									\
+										\
+	TDVMCALL_BUG_ON(vmcall_ret);						\
+										\
+	__ret;									\
+})
+
+#define TDVMCALL_3_1(__in_r11, __in_r12, __in_r13, __out_r11)			\
+({										\
+	u64 vmcall_ret = TDG_VP_VMCALL;						\
+	u64 __in_r11, __in_r12, __in_r13;					\
+	u64 out_r11;								\
+	u64 __ret;								\
+										\
+	asm volatile (								\
+		"movq	%[r11_in], %%r11\n\t"					\
+		"movq	%[r12_in], %%r12\n\t"					\
+		"movq	%[r13_in], %%r13\n\t"					\
+		"xor    %%r10d, %%r10d\n\t"					\
+		".byte 0x66,0x0f,0x01,0xcc\n\t"					\
+		"movq	%%r10, %[r10_out]\n\t"					\
+		"movq	%%r11, %[r11_out]\n\t"					\
+		: "+a"(vmcall_ret),						\
+		  [r10_out] "=rm" (__ret),					\
+		  [r11_out] "=rm" (out_r11)					\
+		: "c" (TDX_R10 | TDX_R11 | TDX_R12 | TDX_R13),			\
+		  [r11_in] "irm" (r11),						\
+		  [r12_in] "irm" (r12),						\
+		  [r13_in] "irm" (r13)						\
+		: "r10", "r11", "r12", "r13"					\
+	);									\
+										\
+	TDVMCALL_BUG_ON(vmcall_ret);						\
+										\
+	__out_r11;								\
+	__ret;									\
+})
+
+#define TDVMCALL_4_1(__in_r11, __in_r12, __in_r13, __in_r14, __out_r11)		\
+({										\
+	u64 vmcall_ret = TDG_VP_VMCALL;						\
+	u64 __in_r11, __in_r12, __in_r13, __in_r14;				\
+	u64 out_r11;								\
+	u64 __ret;								\
+										\
+	asm volatile (								\
+		"movq	%[r11_in], %%r11\n\t"					\
+		"movq	%[r12_in], %%r12\n\t"					\
+		"movq	%[r13_in], %%r13\n\t"					\
+		"movq	%[r14_in], %%r14\n\t"					\
+		"xor    %%r10d, %%r10d\n\t"					\
+		".byte 0x66,0x0f,0x01,0xcc\n\t"					\
+		"movq	%%r10, %[r10_out]\n\t"					\
+		"movq	%%r11, %[r11_out]\n\t"					\
+		: "+a"(vmcall_ret),						\
+		  [r10_out] "=rm" (__ret),					\
+		  [r11_out] "=rm" (out_r11)					\
+		: "c" (TDX_R10 | TDX_R11 | TDX_R12 | TDX_R13 | TDX_R14),	\
+		  [r11_in] "irm" (r11),						\
+		  [r12_in] "irm" (r12),						\
+		  [r13_in] "irm" (r13),						\
+		  [r14_in] "irm" (r14)						\
+		: "r10", "r11", "r12", "r13", "r14"				\
+	);									\
+										\
+	TDVMCALL_BUG_ON(vmcall_ret);						\
+										\
+	__out_r11;								\
+	__ret;									\
+})
+
+
+#define TDVMCALL_5_0(__in_r11, __in_r12, __in_r13, __in_r14, __in_r15)		\
+({										\
+	u64 vmcall_ret = TDG_VP_VMCALL;						\
+	u64 __in_r11, __in_r12, __in_r13, __in_r14, __in_r15;			\
+	u64 __ret;								\
+										\
+	asm volatile (								\
+		"movq	%[r11_in], %%r11\n\t"					\
+		"movq	%[r12_in], %%r12\n\t"					\
+		"movq	%[r13_in], %%r13\n\t"					\
+		"movq	%[r14_in], %%r14\n\t"					\
+		"movq	%[r15_in], %%r15\n\t"					\
+		"xor    %%r10d, %%r10d\n\t"					\
+		".byte 0x66,0x0f,0x01,0xcc\n\t"					\
+		"movq	%%r10, %[r10_out]\n\t"					\
+		: "+a"(vmcall_ret),						\
+		  [r10_out] "=rm" (__ret)					\
+		: "c" (TDX_R10 | TDX_R11 | TDX_R12 | TDX_R13 | TDX_R14 | TDX_R15),\
+		  [r11_in] "irm" (r11),						\
+		  [r12_in] "irm" (r12),						\
+		  [r13_in] "irm" (r13),						\
+		  [r14_in] "irm" (r14),						\
+		  [r15_in] "irm" (r15)						\
+		: "r10", "r11", "r12", "r13", "r14", "r15"			\
+	);									\
+										\
+	TDVMCALL_BUG_ON(vmcall_ret);						\
+										\
+	__ret;									\
+})
+
 /*
  * Used in __tdcall*() to gather the input/output registers' values of the
  * TDCALL instruction when requesting services from the TDX module. This is a
@@ -97,25 +282,6 @@ u64 __tdcall_saved_ret(u64 fn, struct tdx_module_args *args);
 /* Used to request services from the VMM */
 u64 __tdx_hypercall(struct tdx_module_args *args);
 
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
 /* Called from __tdx_hypercall() for unrecoverable failure */
 void __noreturn __tdx_hypercall_failed(void);
 

base-commit: 2ab79514109578fc4b6df90633d500cf281eb689

---

## [5] Edgecombe, Rick P — 2024-08-28
*Subject: Re: [PATCH] x86/tdx: Enhance code generation for TDCALL and SEAMCALL
 wrappers*

On Tue, 2024-06-04 at 12:34 -0700, Sean Christopherson wrote:
> 
> If we're willing to suffer a few gnarly macros, I think we get a satisfactory

Hi Sean,

We are kind of stuck on improving the code generation for the existing calls.
x86 maintainers don't seem to be enthusiastic about tackling this urgently and
there is not consensus on how to weigh source code clarity with code generation
sanity [0]. I think we are going to table it for the time being, unless it's a
showstopper for you.

An option is still to have a separate helper infrastructure for KVM's calls, but
as discussed originally this duplicates code.

Rick

[0] https://lore.kernel.org/all/3a210286-7d0f-4404-ad79-c8eab1514381@intel.com/

---

## [6] Sean Christopherson — 2024-09-11
*Subject: Re: [PATCH] x86/tdx: Enhance code generation for TDCALL and SEAMCALL wrappers*

On Wed, Aug 28, 2024, Rick P Edgecombe wrote:
> On Tue, 2024-06-04 at 12:34 -0700, Sean Christopherson wrote:
> > 

I'll survive.

> An option is still to have a separate helper infrastructure for KVM's calls, but
> as discussed originally this duplicates code.

Ya.  Tangentially related to this topic, at some point in the not-to-distant
future, I think we need to have a discussion for how to maintain TDX (and SNP)
going forward.

Not because I want to take more ownership in KVM (I would generally prefer to do
the opposite), but because I suspect there will be more overlaps similar to this
in the future, e.g. if the guest kernel gets cornered into doing some amount
of SSE/AVX emulation for userspace MMIO.  And because I also suspect that future
additions to TDX and SNP will require modifications and tighter integration in/with
subsystems outside of KVM, while simultaneously moving further away from the areas
that KVM has historically operated in, e.g. emulation, feature enumeration, memory
management, etc.

I don't have any concrete (or even half-baked) thoughts, just flagging that we
might want to have a conversation to hash out what we think would be the best
way to operate, knowing what's on the horizon, versus winging it as we go and
hoping everything works out.

---
