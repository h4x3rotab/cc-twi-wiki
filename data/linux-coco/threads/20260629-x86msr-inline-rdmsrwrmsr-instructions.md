---
title: 'x86/msr: Inline rdmsr/wrmsr instructions'
date: 2026-06-29
last_reply: 2026-06-29
message_count: 3
participants: ['Juergen Gross']
---

## [1] Juergen Gross — 2026-06-29

When building a kernel with CONFIG_PARAVIRT_XXL the paravirt
infrastructure will always use functions for reading or writing MSRs,
even when running on bare metal.

Switch to inline RDMSR/WRMSR instructions in this case, reducing the
paravirt overhead.

The first patch is a prerequisite fix for alternative patching. Its
is needed due to the initial indirect call needs to be padded with
NOPs in some cases with the following patches.

In order to make this less intrusive, some further reorganization of
the MSR access helpers is done in the patches 2-6.

The next 5 patches are converting the non-paravirt case to use direct
inlining of the MSR access instructions, including the WRMSRNS
instruction and the immediate variants of RDMSR and WRMSR if possible.

Patches 12-14 are some further preparations for making the real switch
to directly patch in the native MSR instructions easier.

Patch 15 is switching the paravirt MSR function interface from normal
call ABI to one more similar to the native MSR instructions.

Patch 16 is a little cleanup patch.

Patch 17 is the final step for patching in the native MSR instructions
when not running as a Xen PV guest.

Patch 18 converts the rest of the MSR helpers to __always_inline.

This series has been tested to work with Xen PV and on bare metal.

Based on [1] and [2].

Changes since V3:
- Rebase
- wrmsrns() related changes (patches 9+10)

Changes since V2:
- switch back to the paravirt approach

Changes since V1:
- Use Xin Li's approach for inlining
- Several new patches

[1]: https://lore.kernel.org/lkml/20260629060526.3638272-1-jgross@suse.com/T/#t
[2]: https://lore.kernel.org/lkml/20260629063943.3641266-1-jgross@suse.com/T/#t

Juergen Gross (18):
  x86/alternative: Support alt_replace_call() with instructions after
    call
  coco/tdx: Rename MSR access helpers
  KVM: x86: Remove the KVM private read_msr() function
  x86/msr: Minimize usage of native_*() msr access functions
  x86/msr: Move MSR trace calls one function level up
  x86/hyperv: Switch from __rdmsr() to native_rdmsrq()
  x86/opcode: Add immediate form MSR instructions
  x86/extable: Add support for immediate form MSR instructions
  x86/msr: Make wrmsrns() a first class citizen
  x86/msr: Introduce sync_cpu_after_wrmsrns()
  x86/msr: Use the alternatives mechanism for RDMSR
  x86/alternatives: Add ALTERNATIVE_4()
  x86/paravirt: Split off MSR related hooks into new header
  x86/paravirt: Prepare support of MSR instruction interfaces
  x86/paravirt: Switch MSR access pv_ops functions to instruction
    interfaces
  x86/msr: Reduce number of low level MSR access helpers
  x86/paravirt: Use alternatives for MSR access with paravirt
  x86/msr: Make all MSR access functions __always_inline

 arch/x86/coco/tdx/tdx.c                   |   8 +-
 arch/x86/hyperv/hv_crash.c                |   6 +-
 arch/x86/hyperv/ivm.c                     |   2 +-
 arch/x86/include/asm/alternative.h        |   6 +
 arch/x86/include/asm/fred.h               |   2 +-
 arch/x86/include/asm/kvm_host.h           |   7 -
 arch/x86/include/asm/msr.h                | 340 +++++++++++++++++-----
 arch/x86/include/asm/paravirt-msr.h       | 180 ++++++++++++
 arch/x86/include/asm/paravirt.h           |  45 ---
 arch/x86/include/asm/paravirt_types.h     |  57 ++--
 arch/x86/include/asm/qspinlock_paravirt.h |   4 +-
 arch/x86/kernel/alternative.c             |   5 +-
 arch/x86/kernel/cpu/mshyperv.c            |   4 +-
 arch/x86/kernel/kvmclock.c                |   2 +-
 arch/x86/kernel/paravirt.c                |  42 ++-
 arch/x86/kvm/svm/svm.c                    |  16 +-
 arch/x86/kvm/vmx/tdx.c                    |   2 +-
 arch/x86/kvm/vmx/vmx.c                    |   6 +-
 arch/x86/lib/x86-opcode-map.txt           |   5 +-
 arch/x86/mm/extable.c                     |  46 ++-
 arch/x86/xen/enlighten_pv.c               |  52 +++-
 arch/x86/xen/pmu.c                        |   4 +-
 tools/arch/x86/lib/x86-opcode-map.txt     |   5 +-
 tools/objtool/check.c                     |   1 +
 24 files changed, 641 insertions(+), 206 deletions(-)
 create mode 100644 arch/x86/include/asm/paravirt-msr.h

---

## [2] Juergen Gross — 2026-06-29
*Subject: [PATCH v4 02/18] coco/tdx: Rename MSR access helpers*

In order to avoid a name clash with some general MSR access helpers
after a future MSR infrastructure rework, rename the TDX specific
helpers.

Signed-off-by: Juergen Gross <jgross@suse.com>
Reviewed-by: Kiryl Shutsemau <kas@kernel.org>
Reviewed-by: H. Peter Anvin (Intel) <hpa@zytor.com>
Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
---
 arch/x86/coco/tdx/tdx.c | 8 ++++----
 1 file changed, 4 insertions(+), 4 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 29b6f1ed59ec..24379affb90d 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -469,7 +469,7 @@ static void __cpuidle tdx_safe_halt(void)
 	raw_local_irq_enable();
 }
 
-static int read_msr(struct pt_regs *regs, struct ve_info *ve)
+static int tdx_read_msr(struct pt_regs *regs, struct ve_info *ve)
 {
 	struct tdx_module_args args = {
 		.r10 = TDX_HYPERCALL_STANDARD,
@@ -490,7 +490,7 @@ static int read_msr(struct pt_regs *regs, struct ve_info *ve)
 	return ve_instr_len(ve);
 }
 
-static int write_msr(struct pt_regs *regs, struct ve_info *ve)
+static int tdx_write_msr(struct pt_regs *regs, struct ve_info *ve)
 {
 	struct tdx_module_args args = {
 		.r10 = TDX_HYPERCALL_STANDARD,
@@ -843,9 +843,9 @@ static int virt_exception_kernel(struct pt_regs *regs, struct ve_info *ve)
 	case EXIT_REASON_HLT:
 		return handle_halt(ve);
 	case EXIT_REASON_MSR_READ:
-		return read_msr(regs, ve);
+		return tdx_read_msr(regs, ve);
 	case EXIT_REASON_MSR_WRITE:
-		return write_msr(regs, ve);
+		return tdx_write_msr(regs, ve);
 	case EXIT_REASON_CPUID:
 		return handle_cpuid(regs, ve);
 	case EXIT_REASON_EPT_VIOLATION:

---

## [3] Juergen Gross — 2026-06-29
*Subject: [PATCH v4 03/18] KVM: x86: Remove the KVM private read_msr() function*

Instead of having a KVM private read_msr() function, just use rdmsrq().

Signed-off-by: Juergen Gross <jgross@suse.com>
Reviewed-by: H. Peter Anvin (Intel) <hpa@zytor.com>
Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Acked-by: Sean Christopherson <seanjc@google.com>
---
V2:
- remove the helper and use rdmsrq() directly (Sean Christopherson)
---
 arch/x86/include/asm/kvm_host.h | 7 -------
 arch/x86/kvm/vmx/tdx.c          | 2 +-
 arch/x86/kvm/vmx/vmx.c          | 6 +++---
 3 files changed, 4 insertions(+), 11 deletions(-)

diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h
index c87545070347..b4473c4428cf 100644
--- a/arch/x86/include/asm/kvm_host.h
+++ b/arch/x86/include/asm/kvm_host.h
@@ -2412,13 +2412,6 @@ static inline void kvm_load_ldt(u16 sel)
 	asm("lldt %0" : : "rm"(sel));
 }
 
-#ifdef CONFIG_X86_64
-static inline unsigned long read_msr(unsigned long msr)
-{
-	return rdmsrq(msr);
-}
-#endif
-
 static inline void kvm_inject_gp(struct kvm_vcpu *vcpu, u32 error_code)
 {
 	kvm_queue_exception_e(vcpu, GP_VECTOR, error_code);
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 989ab29b8c6f..cf4efca81fd4 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -793,7 +793,7 @@ void tdx_prepare_switch_to_guest(struct kvm_vcpu *vcpu)
 	if (likely(is_64bit_mm(current->mm)))
 		vt->msr_host_kernel_gs_base = current->thread.gsbase;
 	else
-		vt->msr_host_kernel_gs_base = read_msr(MSR_KERNEL_GS_BASE);
+		vt->msr_host_kernel_gs_base = rdmsrq(MSR_KERNEL_GS_BASE);
 
 	vt->guest_state_loaded = true;
 
diff --git a/arch/x86/kvm/vmx/vmx.c b/arch/x86/kvm/vmx/vmx.c
index 3d53b5bb6914..729d4a0d0beb 100644
--- a/arch/x86/kvm/vmx/vmx.c
+++ b/arch/x86/kvm/vmx/vmx.c
@@ -1375,8 +1375,8 @@ void vmx_prepare_switch_to_guest(struct kvm_vcpu *vcpu)
 	} else {
 		savesegment(fs, fs_sel);
 		savesegment(gs, gs_sel);
-		fs_base = read_msr(MSR_FS_BASE);
-		vt->msr_host_kernel_gs_base = read_msr(MSR_KERNEL_GS_BASE);
+		fs_base = rdmsrq(MSR_FS_BASE);
+		vt->msr_host_kernel_gs_base = rdmsrq(MSR_KERNEL_GS_BASE);
 	}
 
 	wrmsrq(MSR_KERNEL_GS_BASE, vmx->msr_guest_kernel_gs_base);
@@ -1435,7 +1435,7 @@ static u64 vmx_read_guest_host_msr(struct vcpu_vmx *vmx, u32 msr, u64 *cache)
 {
 	preempt_disable();
 	if (vmx->vt.guest_state_loaded)
-		*cache = read_msr(msr);
+		*cache = rdmsrq(msr);
 	preempt_enable();
 	return *cache;
 }

---
