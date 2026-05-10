---
title: 'x86/msr: Inline rdmsr/wrmsr instructions'
date: 2026-02-18
last_reply: 2026-02-19
message_count: 8
participants: ['Juergen Gross', 'Edgecombe, Rick P', 'Sean Christopherson', 'H. Peter Anvin']
---

## [1] Juergen Gross — 2026-02-18

When building a kernel with CONFIG_PARAVIRT_XXL the paravirt
infrastructure will always use functions for reading or writing MSRs,
even when running on bare metal.

Switch to inline RDMSR/WRMSR instructions in this case, reducing the
paravirt overhead.

The first patch is a prerequisite fix for alternative patching. Its
is needed due to the initial indirect call needs to be padded with
NOPs in some cases with the following patches.

In order to make this less intrusive, some further reorganization of
the MSR access helpers is done in the patches 1-6.

The next 4 patches are converting the non-paravirt case to use direct
inlining of the MSR access instructions, including the WRMSRNS
instruction and the immediate variants of RDMSR and WRMSR if possible.

Patches 11-13 are some further preparations for making the real switch
to directly patch in the native MSR instructions easier.

Patch 14 is switching the paravirt MSR function interface from normal
call ABI to one more similar to the native MSR instructions.

Patch 15 is a little cleanup patch.

Patch 16 is the final step for patching in the native MSR instructions
when not running as a Xen PV guest.

This series has been tested to work with Xen PV and on bare metal.

Note that there is more room for improvement. This series is sent out
to get a first impression how the code will basically look like.

Right now the same problem is solved differently for the paravirt and
the non-paravirt cases. In case this is not desired, there are two
possibilities to merge the two implementations. Both solutions have
the common idea to have rather similar code for paravirt and
non-paravirt variants, but just use a different main macro for
generating the respective code. For making the code of both possible
scenarios more similar, the following variants are possible:

1. Remove the micro-optimizations of the non-paravirt case, making
   it similar to the paravirt code in my series. This has the
   advantage of being more simple, but might have a very small
   negative performance impact (probably not really detectable).

2. Add the same micro-optimizations to the paravirt case, requiring
   to enhance paravirt patching to support a to be patched indirect
   call in the middle of the initial code snipplet.

In both cases the native MSR function variants would no longer be
usable in the paravirt case, but this would mostly affect Xen, as it
would need to open code the WRMSR/RDMSR instructions to be used
instead the native_*msr*() functions.

Changes since V2:
- switch back to the paravirt approach

Changes since V1:
- Use Xin Li's approach for inlining
- Several new patches

Juergen Gross (16):
  x86/alternative: Support alt_replace_call() with instructions after
    call
  coco/tdx: Rename MSR access helpers
  x86/sev: Replace call of native_wrmsr() with native_wrmsrq()
  KVM: x86: Remove the KVM private read_msr() function
  x86/msr: Minimize usage of native_*() msr access functions
  x86/msr: Move MSR trace calls one function level up
  x86/opcode: Add immediate form MSR instructions
  x86/extable: Add support for immediate form MSR instructions
  x86/msr: Use the alternatives mechanism for WRMSR
  x86/msr: Use the alternatives mechanism for RDMSR
  x86/alternatives: Add ALTERNATIVE_4()
  x86/paravirt: Split off MSR related hooks into new header
  x86/paravirt: Prepare support of MSR instruction interfaces
  x86/paravirt: Switch MSR access pv_ops functions to instruction
    interfaces
  x86/msr: Reduce number of low level MSR access helpers
  x86/paravirt: Use alternatives for MSR access with paravirt

 arch/x86/coco/sev/internal.h              |   7 +-
 arch/x86/coco/tdx/tdx.c                   |   8 +-
 arch/x86/hyperv/ivm.c                     |   2 +-
 arch/x86/include/asm/alternative.h        |   6 +
 arch/x86/include/asm/fred.h               |   2 +-
 arch/x86/include/asm/kvm_host.h           |  10 -
 arch/x86/include/asm/msr.h                | 345 ++++++++++++++++------
 arch/x86/include/asm/paravirt-msr.h       | 148 ++++++++++
 arch/x86/include/asm/paravirt.h           |  67 -----
 arch/x86/include/asm/paravirt_types.h     |  57 ++--
 arch/x86/include/asm/qspinlock_paravirt.h |   4 +-
 arch/x86/kernel/alternative.c             |   5 +-
 arch/x86/kernel/cpu/mshyperv.c            |   7 +-
 arch/x86/kernel/kvmclock.c                |   2 +-
 arch/x86/kernel/paravirt.c                |  42 ++-
 arch/x86/kvm/svm/svm.c                    |  16 +-
 arch/x86/kvm/vmx/tdx.c                    |   2 +-
 arch/x86/kvm/vmx/vmx.c                    |   8 +-
 arch/x86/lib/x86-opcode-map.txt           |   5 +-
 arch/x86/mm/extable.c                     |  35 ++-
 arch/x86/xen/enlighten_pv.c               |  52 +++-
 arch/x86/xen/pmu.c                        |   4 +-
 tools/arch/x86/lib/x86-opcode-map.txt     |   5 +-
 tools/objtool/check.c                     |   1 +
 24 files changed, 576 insertions(+), 264 deletions(-)
 create mode 100644 arch/x86/include/asm/paravirt-msr.h

---

## [2] Juergen Gross — 2026-02-18
*Subject: [PATCH v3 02/16] coco/tdx: Rename MSR access helpers*

In order to avoid a name clash with some general MSR access helpers
after a future MSR infrastructure rework, rename the TDX specific
helpers.

Signed-off-by: Juergen Gross <jgross@suse.com>
Reviewed-by: Kiryl Shutsemau <kas@kernel.org>
Reviewed-by: H. Peter Anvin (Intel) <hpa@zytor.com>
---
 arch/x86/coco/tdx/tdx.c | 8 ++++----
 1 file changed, 4 insertions(+), 4 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 7b2833705d47..500166c1a161 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -468,7 +468,7 @@ static void __cpuidle tdx_safe_halt(void)
 	raw_local_irq_enable();
 }
 
-static int read_msr(struct pt_regs *regs, struct ve_info *ve)
+static int tdx_read_msr(struct pt_regs *regs, struct ve_info *ve)
 {
 	struct tdx_module_args args = {
 		.r10 = TDX_HYPERCALL_STANDARD,
@@ -489,7 +489,7 @@ static int read_msr(struct pt_regs *regs, struct ve_info *ve)
 	return ve_instr_len(ve);
 }
 
-static int write_msr(struct pt_regs *regs, struct ve_info *ve)
+static int tdx_write_msr(struct pt_regs *regs, struct ve_info *ve)
 {
 	struct tdx_module_args args = {
 		.r10 = TDX_HYPERCALL_STANDARD,
@@ -842,9 +842,9 @@ static int virt_exception_kernel(struct pt_regs *regs, struct ve_info *ve)
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

## [3] Juergen Gross — 2026-02-18
*Subject: [PATCH v3 04/16] KVM: x86: Remove the KVM private read_msr() function*

Instead of having a KVM private read_msr() function, just use rdmsrq().

Signed-off-by: Juergen Gross <jgross@suse.com>
Reviewed-by: H. Peter Anvin (Intel) <hpa@zytor.com>
---
V2:
- remove the helper and use rdmsrq() directly (Sean Christopherson)
---
 arch/x86/include/asm/kvm_host.h | 10 ----------
 arch/x86/kvm/vmx/tdx.c          |  2 +-
 arch/x86/kvm/vmx/vmx.c          |  6 +++---
 3 files changed, 4 insertions(+), 14 deletions(-)

diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h
index ff07c45e3c73..9034222a96e8 100644
--- a/arch/x86/include/asm/kvm_host.h
+++ b/arch/x86/include/asm/kvm_host.h
@@ -2347,16 +2347,6 @@ static inline void kvm_load_ldt(u16 sel)
 	asm("lldt %0" : : "rm"(sel));
 }
 
-#ifdef CONFIG_X86_64
-static inline unsigned long read_msr(unsigned long msr)
-{
-	u64 value;
-
-	rdmsrq(msr, value);
-	return value;
-}
-#endif
-
 static inline void kvm_inject_gp(struct kvm_vcpu *vcpu, u32 error_code)
 {
 	kvm_queue_exception_e(vcpu, GP_VECTOR, error_code);
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 5df9d32d2058..d9e371e39853 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -801,7 +801,7 @@ void tdx_prepare_switch_to_guest(struct kvm_vcpu *vcpu)
 	if (likely(is_64bit_mm(current->mm)))
 		vt->msr_host_kernel_gs_base = current->thread.gsbase;
 	else
-		vt->msr_host_kernel_gs_base = read_msr(MSR_KERNEL_GS_BASE);
+		rdmsrq(MSR_KERNEL_GS_BASE, vt->msr_host_kernel_gs_base);
 
 	vt->guest_state_loaded = true;
 
diff --git a/arch/x86/kvm/vmx/vmx.c b/arch/x86/kvm/vmx/vmx.c
index 967b58a8ab9d..3799cbbb4577 100644
--- a/arch/x86/kvm/vmx/vmx.c
+++ b/arch/x86/kvm/vmx/vmx.c
@@ -1403,8 +1403,8 @@ void vmx_prepare_switch_to_guest(struct kvm_vcpu *vcpu)
 	} else {
 		savesegment(fs, fs_sel);
 		savesegment(gs, gs_sel);
-		fs_base = read_msr(MSR_FS_BASE);
-		vt->msr_host_kernel_gs_base = read_msr(MSR_KERNEL_GS_BASE);
+		rdmsrq(MSR_FS_BASE, fs_base);
+		rdmsrq(MSR_KERNEL_GS_BASE, vt->msr_host_kernel_gs_base);
 	}
 
 	wrmsrq(MSR_KERNEL_GS_BASE, vmx->msr_guest_kernel_gs_base);
@@ -1463,7 +1463,7 @@ static u64 vmx_read_guest_host_msr(struct vcpu_vmx *vmx, u32 msr, u64 *cache)
 {
 	preempt_disable();
 	if (vmx->vt.guest_state_loaded)
-		*cache = read_msr(msr);
+		rdmsrq(msr, *cache);
 	preempt_enable();
 	return *cache;
 }

---

## [4] Edgecombe, Rick P — 2026-02-18
*Subject: Re: [PATCH v3 02/16] coco/tdx: Rename MSR access helpers*

On Wed, 2026-02-18 at 09:21 +0100, Juergen Gross wrote:
> In order to avoid a name clash with some general MSR access helpers
> after a future MSR infrastructure rework, rename the TDX specific
Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>

---

## [5] Edgecombe, Rick P — 2026-02-18
*Subject: Re: [PATCH v3 04/16] KVM: x86: Remove the KVM private read_msr()
 function*

On Wed, 2026-02-18 at 09:21 +0100, Juergen Gross wrote:
> Instead of having a KVM private read_msr() function, just use
> rdmsrq().

Might be nice to include a little bit more on the "why", but the patch
is pretty simple.

> 
> Signed-off-by: Juergen Gross <jgross@suse.com>

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>

---

## [6] Sean Christopherson — 2026-02-18
*Subject: Re: [PATCH v3 04/16] KVM: x86: Remove the KVM private read_msr() function*

On Wed, Feb 18, 2026, Rick P Edgecombe wrote:
> On Wed, 2026-02-18 at 09:21 +0100, Juergen Gross wrote:
> > Instead of having a KVM private read_msr() function, just use

Eh, the why is basically "KVM is old and crusty".  I'm a-ok without a history
lesson on how we got here :-)

> > Signed-off-by: Juergen Gross <jgross@suse.com>
> > Reviewed-by: H. Peter Anvin (Intel) <hpa@zytor.com>

Acked-by: Sean Christopherson <seanjc@google.com>

---

## [7] H. Peter Anvin — 2026-02-18
*Subject: Re: [PATCH v3 00/16] x86/msr: Inline rdmsr/wrmsr instructions*

On February 18, 2026 12:21:17 AM PST, Juergen Gross <jgross@suse.com> wrote:
>When building a kernel with CONFIG_PARAVIRT_XXL the paravirt
>infrastructure will always use functions for reading or writing MSRs,

Does that mean you are considering this patchset an RFC? If so, you should put that in the subject header. 

>Right now the same problem is solved differently for the paravirt and
>the non-paravirt cases. In case this is not desired, there are two

Could you clarify *on the high design level* what "go back to the paravirt approach" means, and the motivation for that?

Note that for Xen *most* MSRs fall in one of two categories: those that are dropped entirely and those that are just passed straight on to the hardware.

I don't know if anyone cares about optimizing PV Xen anymore, but at least in theory Xen can un-paravirtualize most sites.

---

## [8] Jürgen Groß — 2026-02-19
*Subject: Re: [PATCH v3 00/16] x86/msr: Inline rdmsr/wrmsr instructions*

On 18.02.26 21:37, H. Peter Anvin wrote:
> On February 18, 2026 12:21:17 AM PST, Juergen Gross <jgross@suse.com> wrote:
>> When building a kernel with CONFIG_PARAVIRT_XXL the paravirt

It is one possible solution.

> 
>> Right now the same problem is solved differently for the paravirt and

This is related to V2 of this series, where I used a static branch for
special casing Xen PV.

Peter Zijlstra commented on that asking to try harder using the pv_ops
hooks for Xen PV, too.

> Note that for Xen *most* MSRs fall in one of two categories: those that are dropped entirely and those that are just passed straight on to the hardware.
> 

The problem with that is, that this would need to be taken care at the
callers' sites, "poisoning" a lot of code with Xen specific paths. Or we'd
need to use the native variants explicitly at all places where Xen PV
would just use the MSR instructions itself. But please be aware, that
there are plans to introduce a hypercall for Xen to speed up MSR accesses,
which would reduce the "passed through to hardware" cases to 0.


Juergen

---
