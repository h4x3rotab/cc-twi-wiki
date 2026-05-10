---
title: 'KVM: x86: APX reg prep work'
date: 2026-03-10
last_reply: 2026-04-07
message_count: 34
participants: ['Sean Christopherson', 'Yosry Ahmed', 'Paolo Bonzini', 'Chang S. Bae', 'Andrew Cooper', 'Dave Hansen']
---

## [1] Sean Christopherson — 2026-03-10

Clean up KVM's register tracking and storage in preparation for landing APX,
which expands the maximum number of GPRs from 16 to 32.

This is kinda sorta an RFC, as there are some very opinionated changes.  I.e.
if you dislike something, please speak up.

My thought is to treat R16-R31 as much like other GPRs as possible (though
maybe we don't need to expand regs[] as sketched out in the last patch?).

Sean Christopherson (7):
  KVM: x86: Add dedicated storage for guest RIP
  KVM: x86: Drop the "EX" part of "EXREG" to avoid collision with APX
  KVM: nVMX: Do a bitwise-AND of regs_avail when switching active VMCS
  KVM: x86: Add wrapper APIs to reset dirty/available register masks
  KVM: x86: Track available/dirty register masks as "unsigned long"
    values
  KVM: x86: Use a proper bitmap for tracking available/dirty registers
  *** DO NOT MERGE *** KVM: x86: Pretend that APX is supported on 64-bit
    kernels

 arch/x86/include/asm/kvm_host.h | 53 +++++++++++++++++++--------
 arch/x86/kvm/kvm_cache_regs.h   | 64 +++++++++++++++++++++++----------
 arch/x86/kvm/svm/sev.c          |  2 +-
 arch/x86/kvm/svm/svm.c          | 16 ++++-----
 arch/x86/kvm/svm/svm.h          |  2 +-
 arch/x86/kvm/vmx/nested.c       | 10 +++---
 arch/x86/kvm/vmx/tdx.c          | 36 +++++++++----------
 arch/x86/kvm/vmx/vmx.c          | 52 +++++++++++++--------------
 arch/x86/kvm/vmx/vmx.h          | 24 ++++++-------
 arch/x86/kvm/x86.c              | 20 +++++------
 10 files changed, 166 insertions(+), 113 deletions(-)


base-commit: 5128b972fb2801ad9aca54d990a75611ab5283a9

---

## [2] Sean Christopherson — 2026-03-10
*Subject: [PATCH 1/7] KVM: x86: Add dedicated storage for guest RIP*

Add kvm_vcpu_arch.rip to track guest RIP instead of including it in the
generic regs[] array.  Decoupling RIP from regs[] will allow using a
*completely* arbitrary index for RIP, as opposed to the mostly-arbitrary
index that is currently used.  That in turn will allow using indices
16-31 to track R16-R31 that are coming with APX.

Note, although RIP can used for addressing, it does NOT have an
architecturally defined index, and so can't be reached via flows like
get_vmx_mem_address() where KVM "blindly" reads a general purpose register
given the SIB information reported by hardware.  For RIP-relative
addressing, hardware reports the full "offset" in vmcs.EXIT_QUALIFICATION.

Note #2, keep the available/dirty tracking as RSP is context switched
through the VMCS, i.e. needs to be cached for VMX.

Opportunistically rename NR_VCPU_REGS to NR_VCPU_GENERAL_PURPOSE_REGS to
better capture what it tracks, and so that KVM can slot in R16-R13 without
running into weirdness where KVM's definition of "EXREG" doesn't line up
with APX's definition of "extended reg".

No functional change intended.

Cc: Chang S. Bae <chang.seok.bae@intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/kvm_host.h | 10 ++++++----
 arch/x86/kvm/kvm_cache_regs.h   | 12 ++++++++----
 arch/x86/kvm/svm/sev.c          |  2 +-
 arch/x86/kvm/svm/svm.c          |  6 +++---
 arch/x86/kvm/vmx/vmx.c          |  8 ++++----
 arch/x86/kvm/vmx/vmx.h          |  2 +-
 6 files changed, 23 insertions(+), 17 deletions(-)

diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h
index c94556fefb75..0461ba97a3be 100644
--- a/arch/x86/include/asm/kvm_host.h
+++ b/arch/x86/include/asm/kvm_host.h
@@ -191,10 +191,11 @@ enum kvm_reg {
 	VCPU_REGS_R14 = __VCPU_REGS_R14,
 	VCPU_REGS_R15 = __VCPU_REGS_R15,
 #endif
-	VCPU_REGS_RIP,
-	NR_VCPU_REGS,
+	NR_VCPU_GENERAL_PURPOSE_REGS,
 
-	VCPU_EXREG_PDPTR = NR_VCPU_REGS,
+	VCPU_REG_RIP = NR_VCPU_GENERAL_PURPOSE_REGS,
+
+	VCPU_EXREG_PDPTR,
 	VCPU_EXREG_CR0,
 	/*
 	 * Alias AMD's ERAPS (not a real register) to CR3 so that common code
@@ -799,7 +800,8 @@ struct kvm_vcpu_arch {
 	 * rip and regs accesses must go through
 	 * kvm_{register,rip}_{read,write} functions.
 	 */
-	unsigned long regs[NR_VCPU_REGS];
+	unsigned long regs[NR_VCPU_GENERAL_PURPOSE_REGS];
+	unsigned long rip;
 	u32 regs_avail;
 	u32 regs_dirty;
 
diff --git a/arch/x86/kvm/kvm_cache_regs.h b/arch/x86/kvm/kvm_cache_regs.h
index 8ddb01191d6f..9b7df9de0e87 100644
--- a/arch/x86/kvm/kvm_cache_regs.h
+++ b/arch/x86/kvm/kvm_cache_regs.h
@@ -112,7 +112,7 @@ static __always_inline bool kvm_register_test_and_mark_available(struct kvm_vcpu
  */
 static inline unsigned long kvm_register_read_raw(struct kvm_vcpu *vcpu, int reg)
 {
-	if (WARN_ON_ONCE((unsigned int)reg >= NR_VCPU_REGS))
+	if (WARN_ON_ONCE((unsigned int)reg >= NR_VCPU_GENERAL_PURPOSE_REGS))
 		return 0;
 
 	if (!kvm_register_is_available(vcpu, reg))
@@ -124,7 +124,7 @@ static inline unsigned long kvm_register_read_raw(struct kvm_vcpu *vcpu, int reg
 static inline void kvm_register_write_raw(struct kvm_vcpu *vcpu, int reg,
 					  unsigned long val)
 {
-	if (WARN_ON_ONCE((unsigned int)reg >= NR_VCPU_REGS))
+	if (WARN_ON_ONCE((unsigned int)reg >= NR_VCPU_GENERAL_PURPOSE_REGS))
 		return;
 
 	vcpu->arch.regs[reg] = val;
@@ -133,12 +133,16 @@ static inline void kvm_register_write_raw(struct kvm_vcpu *vcpu, int reg,
 
 static inline unsigned long kvm_rip_read(struct kvm_vcpu *vcpu)
 {
-	return kvm_register_read_raw(vcpu, VCPU_REGS_RIP);
+	if (!kvm_register_is_available(vcpu, VCPU_REG_RIP))
+		kvm_x86_call(cache_reg)(vcpu, VCPU_REG_RIP);
+
+	return vcpu->arch.rip;
 }
 
 static inline void kvm_rip_write(struct kvm_vcpu *vcpu, unsigned long val)
 {
-	kvm_register_write_raw(vcpu, VCPU_REGS_RIP, val);
+	vcpu->arch.rip = val;
+	kvm_register_mark_dirty(vcpu, VCPU_REG_RIP);
 }
 
 static inline unsigned long kvm_rsp_read(struct kvm_vcpu *vcpu)
diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index b1aa85a6ca5a..0dec619490c3 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -913,7 +913,7 @@ static int sev_es_sync_vmsa(struct vcpu_svm *svm)
 	save->r14 = svm->vcpu.arch.regs[VCPU_REGS_R14];
 	save->r15 = svm->vcpu.arch.regs[VCPU_REGS_R15];
 #endif
-	save->rip = svm->vcpu.arch.regs[VCPU_REGS_RIP];
+	save->rip = svm->vcpu.arch.rip;
 
 	/* Sync some non-GPR registers before encrypting */
 	save->xcr0 = svm->vcpu.arch.xcr0;
diff --git a/arch/x86/kvm/svm/svm.c b/arch/x86/kvm/svm/svm.c
index 3407deac90bd..4b9d79412da7 100644
--- a/arch/x86/kvm/svm/svm.c
+++ b/arch/x86/kvm/svm/svm.c
@@ -4436,7 +4436,7 @@ static __no_kcsan fastpath_t svm_vcpu_run(struct kvm_vcpu *vcpu, u64 run_flags)
 
 	svm->vmcb->save.rax = vcpu->arch.regs[VCPU_REGS_RAX];
 	svm->vmcb->save.rsp = vcpu->arch.regs[VCPU_REGS_RSP];
-	svm->vmcb->save.rip = vcpu->arch.regs[VCPU_REGS_RIP];
+	svm->vmcb->save.rip = vcpu->arch.rip;
 
 	/*
 	 * Disable singlestep if we're injecting an interrupt/exception.
@@ -4522,7 +4522,7 @@ static __no_kcsan fastpath_t svm_vcpu_run(struct kvm_vcpu *vcpu, u64 run_flags)
 		vcpu->arch.cr2 = svm->vmcb->save.cr2;
 		vcpu->arch.regs[VCPU_REGS_RAX] = svm->vmcb->save.rax;
 		vcpu->arch.regs[VCPU_REGS_RSP] = svm->vmcb->save.rsp;
-		vcpu->arch.regs[VCPU_REGS_RIP] = svm->vmcb->save.rip;
+		vcpu->arch.rip = svm->vmcb->save.rip;
 	}
 	vcpu->arch.regs_dirty = 0;
 
@@ -4954,7 +4954,7 @@ static int svm_enter_smm(struct kvm_vcpu *vcpu, union kvm_smram *smram)
 
 	svm->vmcb->save.rax = vcpu->arch.regs[VCPU_REGS_RAX];
 	svm->vmcb->save.rsp = vcpu->arch.regs[VCPU_REGS_RSP];
-	svm->vmcb->save.rip = vcpu->arch.regs[VCPU_REGS_RIP];
+	svm->vmcb->save.rip = vcpu->arch.rip;
 
 	nested_svm_simple_vmexit(svm, SVM_EXIT_SW);
 
diff --git a/arch/x86/kvm/vmx/vmx.c b/arch/x86/kvm/vmx/vmx.c
index 9302c16571cd..802cc5d8bf43 100644
--- a/arch/x86/kvm/vmx/vmx.c
+++ b/arch/x86/kvm/vmx/vmx.c
@@ -2604,8 +2604,8 @@ void vmx_cache_reg(struct kvm_vcpu *vcpu, enum kvm_reg reg)
 	case VCPU_REGS_RSP:
 		vcpu->arch.regs[VCPU_REGS_RSP] = vmcs_readl(GUEST_RSP);
 		break;
-	case VCPU_REGS_RIP:
-		vcpu->arch.regs[VCPU_REGS_RIP] = vmcs_readl(GUEST_RIP);
+	case VCPU_REG_RIP:
+		vcpu->arch.rip = vmcs_readl(GUEST_RIP);
 		break;
 	case VCPU_EXREG_PDPTR:
 		if (enable_ept)
@@ -7536,8 +7536,8 @@ fastpath_t vmx_vcpu_run(struct kvm_vcpu *vcpu, u64 run_flags)
 
 	if (kvm_register_is_dirty(vcpu, VCPU_REGS_RSP))
 		vmcs_writel(GUEST_RSP, vcpu->arch.regs[VCPU_REGS_RSP]);
-	if (kvm_register_is_dirty(vcpu, VCPU_REGS_RIP))
-		vmcs_writel(GUEST_RIP, vcpu->arch.regs[VCPU_REGS_RIP]);
+	if (kvm_register_is_dirty(vcpu, VCPU_REG_RIP))
+		vmcs_writel(GUEST_RIP, vcpu->arch.rip);
 	vcpu->arch.regs_dirty = 0;
 
 	if (run_flags & KVM_RUN_LOAD_GUEST_DR6)
diff --git a/arch/x86/kvm/vmx/vmx.h b/arch/x86/kvm/vmx/vmx.h
index 70bfe81dea54..31bee8b0e4a1 100644
--- a/arch/x86/kvm/vmx/vmx.h
+++ b/arch/x86/kvm/vmx/vmx.h
@@ -623,7 +623,7 @@ BUILD_CONTROLS_SHADOW(tertiary_exec, TERTIARY_VM_EXEC_CONTROL, 64)
  * cache on demand.  Other registers not listed here are synced to
  * the cache immediately after VM-Exit.
  */
-#define VMX_REGS_LAZY_LOAD_SET	((1 << VCPU_REGS_RIP) |         \
+#define VMX_REGS_LAZY_LOAD_SET	((1 << VCPU_REG_RIP) |         \
 				(1 << VCPU_REGS_RSP) |          \
 				(1 << VCPU_EXREG_RFLAGS) |      \
 				(1 << VCPU_EXREG_PDPTR) |       \

---

## [3] Sean Christopherson — 2026-03-10
*Subject: [PATCH 2/7] KVM: x86: Drop the "EX" part of "EXREG" to avoid
 collision with APX*

Now that NR_VCPU_REGS is no longer a thing, drop the "EX" is for
extended (or maybe extra?") prefix from non-GRP registers to avoid a
collision with APX (Advanced Performance Extensions), which adds:

  16 additional general-purpose registers (GPRs) R16–R31, also referred
  to as Extended GPRs (EGPRs)  in this document;

I.e. KVM's version of "extended" won't match with APX's definition.

No functional change intended.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/kvm_host.h | 18 +++++++--------
 arch/x86/kvm/kvm_cache_regs.h   | 16 ++++++-------
 arch/x86/kvm/svm/svm.c          |  6 ++---
 arch/x86/kvm/svm/svm.h          |  2 +-
 arch/x86/kvm/vmx/nested.c       |  6 ++---
 arch/x86/kvm/vmx/tdx.c          |  4 ++--
 arch/x86/kvm/vmx/vmx.c          | 40 ++++++++++++++++-----------------
 arch/x86/kvm/vmx/vmx.h          | 20 ++++++++---------
 arch/x86/kvm/x86.c              | 16 ++++++-------
 9 files changed, 64 insertions(+), 64 deletions(-)

diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h
index 0461ba97a3be..3af5e2661ade 100644
--- a/arch/x86/include/asm/kvm_host.h
+++ b/arch/x86/include/asm/kvm_host.h
@@ -195,8 +195,8 @@ enum kvm_reg {
 
 	VCPU_REG_RIP = NR_VCPU_GENERAL_PURPOSE_REGS,
 
-	VCPU_EXREG_PDPTR,
-	VCPU_EXREG_CR0,
+	VCPU_REG_PDPTR,
+	VCPU_REG_CR0,
 	/*
 	 * Alias AMD's ERAPS (not a real register) to CR3 so that common code
 	 * can trigger emulation of the RAP (Return Address Predictor) with
@@ -204,13 +204,13 @@ enum kvm_reg {
 	 * is cleared on writes to CR3, i.e. marking CR3 dirty will naturally
 	 * mark ERAPS dirty as well.
 	 */
-	VCPU_EXREG_CR3,
-	VCPU_EXREG_ERAPS = VCPU_EXREG_CR3,
-	VCPU_EXREG_CR4,
-	VCPU_EXREG_RFLAGS,
-	VCPU_EXREG_SEGMENTS,
-	VCPU_EXREG_EXIT_INFO_1,
-	VCPU_EXREG_EXIT_INFO_2,
+	VCPU_REG_CR3,
+	VCPU_REG_ERAPS = VCPU_REG_CR3,
+	VCPU_REG_CR4,
+	VCPU_REG_RFLAGS,
+	VCPU_REG_SEGMENTS,
+	VCPU_REG_EXIT_INFO_1,
+	VCPU_REG_EXIT_INFO_2,
 };
 
 enum {
diff --git a/arch/x86/kvm/kvm_cache_regs.h b/arch/x86/kvm/kvm_cache_regs.h
index 9b7df9de0e87..ac1f9867a234 100644
--- a/arch/x86/kvm/kvm_cache_regs.h
+++ b/arch/x86/kvm/kvm_cache_regs.h
@@ -159,8 +159,8 @@ static inline u64 kvm_pdptr_read(struct kvm_vcpu *vcpu, int index)
 {
 	might_sleep();  /* on svm */
 
-	if (!kvm_register_is_available(vcpu, VCPU_EXREG_PDPTR))
-		kvm_x86_call(cache_reg)(vcpu, VCPU_EXREG_PDPTR);
+	if (!kvm_register_is_available(vcpu, VCPU_REG_PDPTR))
+		kvm_x86_call(cache_reg)(vcpu, VCPU_REG_PDPTR);
 
 	return vcpu->arch.walk_mmu->pdptrs[index];
 }
@@ -174,8 +174,8 @@ static inline ulong kvm_read_cr0_bits(struct kvm_vcpu *vcpu, ulong mask)
 {
 	ulong tmask = mask & KVM_POSSIBLE_CR0_GUEST_BITS;
 	if ((tmask & vcpu->arch.cr0_guest_owned_bits) &&
-	    !kvm_register_is_available(vcpu, VCPU_EXREG_CR0))
-		kvm_x86_call(cache_reg)(vcpu, VCPU_EXREG_CR0);
+	    !kvm_register_is_available(vcpu, VCPU_REG_CR0))
+		kvm_x86_call(cache_reg)(vcpu, VCPU_REG_CR0);
 	return vcpu->arch.cr0 & mask;
 }
 
@@ -196,8 +196,8 @@ static inline ulong kvm_read_cr4_bits(struct kvm_vcpu *vcpu, ulong mask)
 {
 	ulong tmask = mask & KVM_POSSIBLE_CR4_GUEST_BITS;
 	if ((tmask & vcpu->arch.cr4_guest_owned_bits) &&
-	    !kvm_register_is_available(vcpu, VCPU_EXREG_CR4))
-		kvm_x86_call(cache_reg)(vcpu, VCPU_EXREG_CR4);
+	    !kvm_register_is_available(vcpu, VCPU_REG_CR4))
+		kvm_x86_call(cache_reg)(vcpu, VCPU_REG_CR4);
 	return vcpu->arch.cr4 & mask;
 }
 
@@ -211,8 +211,8 @@ static __always_inline bool kvm_is_cr4_bit_set(struct kvm_vcpu *vcpu,
 
 static inline ulong kvm_read_cr3(struct kvm_vcpu *vcpu)
 {
-	if (!kvm_register_is_available(vcpu, VCPU_EXREG_CR3))
-		kvm_x86_call(cache_reg)(vcpu, VCPU_EXREG_CR3);
+	if (!kvm_register_is_available(vcpu, VCPU_REG_CR3))
+		kvm_x86_call(cache_reg)(vcpu, VCPU_REG_CR3);
 	return vcpu->arch.cr3;
 }
 
diff --git a/arch/x86/kvm/svm/svm.c b/arch/x86/kvm/svm/svm.c
index 4b9d79412da7..1712c21f4128 100644
--- a/arch/x86/kvm/svm/svm.c
+++ b/arch/x86/kvm/svm/svm.c
@@ -1512,7 +1512,7 @@ static void svm_cache_reg(struct kvm_vcpu *vcpu, enum kvm_reg reg)
 	kvm_register_mark_available(vcpu, reg);
 
 	switch (reg) {
-	case VCPU_EXREG_PDPTR:
+	case VCPU_REG_PDPTR:
 		/*
 		 * When !npt_enabled, mmu->pdptrs[] is already available since
 		 * it is always updated per SDM when moving to CRs.
@@ -4197,7 +4197,7 @@ static void svm_flush_tlb_gva(struct kvm_vcpu *vcpu, gva_t gva)
 
 static void svm_flush_tlb_guest(struct kvm_vcpu *vcpu)
 {
-	kvm_register_mark_dirty(vcpu, VCPU_EXREG_ERAPS);
+	kvm_register_mark_dirty(vcpu, VCPU_REG_ERAPS);
 
 	svm_flush_tlb_asid(vcpu);
 }
@@ -4473,7 +4473,7 @@ static __no_kcsan fastpath_t svm_vcpu_run(struct kvm_vcpu *vcpu, u64 run_flags)
 	svm->vmcb->save.cr2 = vcpu->arch.cr2;
 
 	if (guest_cpu_cap_has(vcpu, X86_FEATURE_ERAPS) &&
-	    kvm_register_is_dirty(vcpu, VCPU_EXREG_ERAPS))
+	    kvm_register_is_dirty(vcpu, VCPU_REG_ERAPS))
 		svm->vmcb->control.erap_ctl |= ERAP_CONTROL_CLEAR_RAP;
 
 	svm_fixup_nested_rips(vcpu);
diff --git a/arch/x86/kvm/svm/svm.h b/arch/x86/kvm/svm/svm.h
index 9909bb7d2d31..dea46130aa24 100644
--- a/arch/x86/kvm/svm/svm.h
+++ b/arch/x86/kvm/svm/svm.h
@@ -460,7 +460,7 @@ static inline bool svm_is_vmrun_failure(u64 exit_code)
  * KVM_REQ_LOAD_MMU_PGD is always requested when the cached vcpu->arch.cr3
  * is changed.  svm_load_mmu_pgd() then syncs the new CR3 value into the VMCB.
  */
-#define SVM_REGS_LAZY_LOAD_SET	(1 << VCPU_EXREG_PDPTR)
+#define SVM_REGS_LAZY_LOAD_SET	(1 << VCPU_REG_PDPTR)
 
 static inline void __vmcb_set_intercept(unsigned long *intercepts, u32 bit)
 {
diff --git a/arch/x86/kvm/vmx/nested.c b/arch/x86/kvm/vmx/nested.c
index 101588914cbb..942acc46f91d 100644
--- a/arch/x86/kvm/vmx/nested.c
+++ b/arch/x86/kvm/vmx/nested.c
@@ -1189,7 +1189,7 @@ static int nested_vmx_load_cr3(struct kvm_vcpu *vcpu, unsigned long cr3,
 	}
 
 	vcpu->arch.cr3 = cr3;
-	kvm_register_mark_dirty(vcpu, VCPU_EXREG_CR3);
+	kvm_register_mark_dirty(vcpu, VCPU_REG_CR3);
 
 	/* Re-initialize the MMU, e.g. to pick up CR4 MMU role changes. */
 	kvm_init_mmu(vcpu);
@@ -4972,7 +4972,7 @@ static void nested_vmx_restore_host_state(struct kvm_vcpu *vcpu)
 
 	nested_ept_uninit_mmu_context(vcpu);
 	vcpu->arch.cr3 = vmcs_readl(GUEST_CR3);
-	kvm_register_mark_available(vcpu, VCPU_EXREG_CR3);
+	kvm_register_mark_available(vcpu, VCPU_REG_CR3);
 
 	/*
 	 * Use ept_save_pdptrs(vcpu) to load the MMU's cached PDPTRs
@@ -5074,7 +5074,7 @@ void __nested_vmx_vmexit(struct kvm_vcpu *vcpu, u32 vm_exit_reason,
 	kvm_service_local_tlb_flush_requests(vcpu);
 
 	/*
-	 * VCPU_EXREG_PDPTR will be clobbered in arch/x86/kvm/vmx/vmx.h between
+	 * VCPU_REG_PDPTR will be clobbered in arch/x86/kvm/vmx/vmx.h between
 	 * now and the new vmentry.  Ensure that the VMCS02 PDPTR fields are
 	 * up-to-date before switching to L1.
 	 */
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 1e47c194af53..c23ec4ac8bc8 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1013,8 +1013,8 @@ static fastpath_t tdx_exit_handlers_fastpath(struct kvm_vcpu *vcpu)
 	return EXIT_FASTPATH_NONE;
 }
 
-#define TDX_REGS_AVAIL_SET	(BIT_ULL(VCPU_EXREG_EXIT_INFO_1) | \
-				 BIT_ULL(VCPU_EXREG_EXIT_INFO_2) | \
+#define TDX_REGS_AVAIL_SET	(BIT_ULL(VCPU_REG_EXIT_INFO_1) | \
+				 BIT_ULL(VCPU_REG_EXIT_INFO_2) | \
 				 BIT_ULL(VCPU_REGS_RAX) | \
 				 BIT_ULL(VCPU_REGS_RBX) | \
 				 BIT_ULL(VCPU_REGS_RCX) | \
diff --git a/arch/x86/kvm/vmx/vmx.c b/arch/x86/kvm/vmx/vmx.c
index 802cc5d8bf43..ed44eb5b4349 100644
--- a/arch/x86/kvm/vmx/vmx.c
+++ b/arch/x86/kvm/vmx/vmx.c
@@ -843,8 +843,8 @@ static bool vmx_segment_cache_test_set(struct vcpu_vmx *vmx, unsigned seg,
 	bool ret;
 	u32 mask = 1 << (seg * SEG_FIELD_NR + field);
 
-	if (!kvm_register_is_available(&vmx->vcpu, VCPU_EXREG_SEGMENTS)) {
-		kvm_register_mark_available(&vmx->vcpu, VCPU_EXREG_SEGMENTS);
+	if (!kvm_register_is_available(&vmx->vcpu, VCPU_REG_SEGMENTS)) {
+		kvm_register_mark_available(&vmx->vcpu, VCPU_REG_SEGMENTS);
 		vmx->segment_cache.bitmask = 0;
 	}
 	ret = vmx->segment_cache.bitmask & mask;
@@ -1609,8 +1609,8 @@ unsigned long vmx_get_rflags(struct kvm_vcpu *vcpu)
 	struct vcpu_vmx *vmx = to_vmx(vcpu);
 	unsigned long rflags, save_rflags;
 
-	if (!kvm_register_is_available(vcpu, VCPU_EXREG_RFLAGS)) {
-		kvm_register_mark_available(vcpu, VCPU_EXREG_RFLAGS);
+	if (!kvm_register_is_available(vcpu, VCPU_REG_RFLAGS)) {
+		kvm_register_mark_available(vcpu, VCPU_REG_RFLAGS);
 		rflags = vmcs_readl(GUEST_RFLAGS);
 		if (vmx->rmode.vm86_active) {
 			rflags &= RMODE_GUEST_OWNED_EFLAGS_BITS;
@@ -1633,7 +1633,7 @@ void vmx_set_rflags(struct kvm_vcpu *vcpu, unsigned long rflags)
 	 * if L1 runs L2 as a restricted guest.
 	 */
 	if (is_unrestricted_guest(vcpu)) {
-		kvm_register_mark_available(vcpu, VCPU_EXREG_RFLAGS);
+		kvm_register_mark_available(vcpu, VCPU_REG_RFLAGS);
 		vmx->rflags = rflags;
 		vmcs_writel(GUEST_RFLAGS, rflags);
 		return;
@@ -2607,17 +2607,17 @@ void vmx_cache_reg(struct kvm_vcpu *vcpu, enum kvm_reg reg)
 	case VCPU_REG_RIP:
 		vcpu->arch.rip = vmcs_readl(GUEST_RIP);
 		break;
-	case VCPU_EXREG_PDPTR:
+	case VCPU_REG_PDPTR:
 		if (enable_ept)
 			ept_save_pdptrs(vcpu);
 		break;
-	case VCPU_EXREG_CR0:
+	case VCPU_REG_CR0:
 		guest_owned_bits = vcpu->arch.cr0_guest_owned_bits;
 
 		vcpu->arch.cr0 &= ~guest_owned_bits;
 		vcpu->arch.cr0 |= vmcs_readl(GUEST_CR0) & guest_owned_bits;
 		break;
-	case VCPU_EXREG_CR3:
+	case VCPU_REG_CR3:
 		/*
 		 * When intercepting CR3 loads, e.g. for shadowing paging, KVM's
 		 * CR3 is loaded into hardware, not the guest's CR3.
@@ -2625,7 +2625,7 @@ void vmx_cache_reg(struct kvm_vcpu *vcpu, enum kvm_reg reg)
 		if (!(exec_controls_get(to_vmx(vcpu)) & CPU_BASED_CR3_LOAD_EXITING))
 			vcpu->arch.cr3 = vmcs_readl(GUEST_CR3);
 		break;
-	case VCPU_EXREG_CR4:
+	case VCPU_REG_CR4:
 		guest_owned_bits = vcpu->arch.cr4_guest_owned_bits;
 
 		vcpu->arch.cr4 &= ~guest_owned_bits;
@@ -3350,7 +3350,7 @@ void vmx_ept_load_pdptrs(struct kvm_vcpu *vcpu)
 {
 	struct kvm_mmu *mmu = vcpu->arch.walk_mmu;
 
-	if (!kvm_register_is_dirty(vcpu, VCPU_EXREG_PDPTR))
+	if (!kvm_register_is_dirty(vcpu, VCPU_REG_PDPTR))
 		return;
 
 	if (is_pae_paging(vcpu)) {
@@ -3373,7 +3373,7 @@ void ept_save_pdptrs(struct kvm_vcpu *vcpu)
 	mmu->pdptrs[2] = vmcs_read64(GUEST_PDPTR2);
 	mmu->pdptrs[3] = vmcs_read64(GUEST_PDPTR3);
 
-	kvm_register_mark_available(vcpu, VCPU_EXREG_PDPTR);
+	kvm_register_mark_available(vcpu, VCPU_REG_PDPTR);
 }
 
 #define CR3_EXITING_BITS (CPU_BASED_CR3_LOAD_EXITING | \
@@ -3416,7 +3416,7 @@ void vmx_set_cr0(struct kvm_vcpu *vcpu, unsigned long cr0)
 	vmcs_writel(CR0_READ_SHADOW, cr0);
 	vmcs_writel(GUEST_CR0, hw_cr0);
 	vcpu->arch.cr0 = cr0;
-	kvm_register_mark_available(vcpu, VCPU_EXREG_CR0);
+	kvm_register_mark_available(vcpu, VCPU_REG_CR0);
 
 #ifdef CONFIG_X86_64
 	if (vcpu->arch.efer & EFER_LME) {
@@ -3434,8 +3434,8 @@ void vmx_set_cr0(struct kvm_vcpu *vcpu, unsigned long cr0)
 		 * (correctly) stop reading vmcs.GUEST_CR3 because it thinks
 		 * KVM's CR3 is installed.
 		 */
-		if (!kvm_register_is_available(vcpu, VCPU_EXREG_CR3))
-			vmx_cache_reg(vcpu, VCPU_EXREG_CR3);
+		if (!kvm_register_is_available(vcpu, VCPU_REG_CR3))
+			vmx_cache_reg(vcpu, VCPU_REG_CR3);
 
 		/*
 		 * When running with EPT but not unrestricted guest, KVM must
@@ -3472,7 +3472,7 @@ void vmx_set_cr0(struct kvm_vcpu *vcpu, unsigned long cr0)
 		 * GUEST_CR3 is still vmx->ept_identity_map_addr if EPT + !URG.
 		 */
 		if (!(old_cr0_pg & X86_CR0_PG) && (cr0 & X86_CR0_PG))
-			kvm_register_mark_dirty(vcpu, VCPU_EXREG_CR3);
+			kvm_register_mark_dirty(vcpu, VCPU_REG_CR3);
 	}
 
 	/* depends on vcpu->arch.cr0 to be set to a new value */
@@ -3501,7 +3501,7 @@ void vmx_load_mmu_pgd(struct kvm_vcpu *vcpu, hpa_t root_hpa, int root_level)
 
 		if (!enable_unrestricted_guest && !is_paging(vcpu))
 			guest_cr3 = to_kvm_vmx(kvm)->ept_identity_map_addr;
-		else if (kvm_register_is_dirty(vcpu, VCPU_EXREG_CR3))
+		else if (kvm_register_is_dirty(vcpu, VCPU_REG_CR3))
 			guest_cr3 = vcpu->arch.cr3;
 		else /* vmcs.GUEST_CR3 is already up-to-date. */
 			update_guest_cr3 = false;
@@ -3561,7 +3561,7 @@ void vmx_set_cr4(struct kvm_vcpu *vcpu, unsigned long cr4)
 	}
 
 	vcpu->arch.cr4 = cr4;
-	kvm_register_mark_available(vcpu, VCPU_EXREG_CR4);
+	kvm_register_mark_available(vcpu, VCPU_REG_CR4);
 
 	if (!enable_unrestricted_guest) {
 		if (enable_ept) {
@@ -5021,7 +5021,7 @@ void vmx_vcpu_reset(struct kvm_vcpu *vcpu, bool init_event)
 	vmcs_write32(GUEST_IDTR_LIMIT, 0xffff);
 
 	vmx_segment_cache_clear(vmx);
-	kvm_register_mark_available(vcpu, VCPU_EXREG_SEGMENTS);
+	kvm_register_mark_available(vcpu, VCPU_REG_SEGMENTS);
 
 	vmcs_write32(GUEST_ACTIVITY_STATE, GUEST_ACTIVITY_ACTIVE);
 	vmcs_write32(GUEST_INTERRUPTIBILITY_INFO, 0);
@@ -7514,9 +7514,9 @@ fastpath_t vmx_vcpu_run(struct kvm_vcpu *vcpu, u64 run_flags)
 
 		vmx->vt.exit_reason.full = EXIT_REASON_INVALID_STATE;
 		vmx->vt.exit_reason.failed_vmentry = 1;
-		kvm_register_mark_available(vcpu, VCPU_EXREG_EXIT_INFO_1);
+		kvm_register_mark_available(vcpu, VCPU_REG_EXIT_INFO_1);
 		vmx->vt.exit_qualification = ENTRY_FAIL_DEFAULT;
-		kvm_register_mark_available(vcpu, VCPU_EXREG_EXIT_INFO_2);
+		kvm_register_mark_available(vcpu, VCPU_REG_EXIT_INFO_2);
 		vmx->vt.exit_intr_info = 0;
 		return EXIT_FASTPATH_NONE;
 	}
diff --git a/arch/x86/kvm/vmx/vmx.h b/arch/x86/kvm/vmx/vmx.h
index 31bee8b0e4a1..d3255a054185 100644
--- a/arch/x86/kvm/vmx/vmx.h
+++ b/arch/x86/kvm/vmx/vmx.h
@@ -320,7 +320,7 @@ static __always_inline unsigned long vmx_get_exit_qual(struct kvm_vcpu *vcpu)
 {
 	struct vcpu_vt *vt = to_vt(vcpu);
 
-	if (!kvm_register_test_and_mark_available(vcpu, VCPU_EXREG_EXIT_INFO_1) &&
+	if (!kvm_register_test_and_mark_available(vcpu, VCPU_REG_EXIT_INFO_1) &&
 	    !WARN_ON_ONCE(is_td_vcpu(vcpu)))
 		vt->exit_qualification = vmcs_readl(EXIT_QUALIFICATION);
 
@@ -331,7 +331,7 @@ static __always_inline u32 vmx_get_intr_info(struct kvm_vcpu *vcpu)
 {
 	struct vcpu_vt *vt = to_vt(vcpu);
 
-	if (!kvm_register_test_and_mark_available(vcpu, VCPU_EXREG_EXIT_INFO_2) &&
+	if (!kvm_register_test_and_mark_available(vcpu, VCPU_REG_EXIT_INFO_2) &&
 	    !WARN_ON_ONCE(is_td_vcpu(vcpu)))
 		vt->exit_intr_info = vmcs_read32(VM_EXIT_INTR_INFO);
 
@@ -625,14 +625,14 @@ BUILD_CONTROLS_SHADOW(tertiary_exec, TERTIARY_VM_EXEC_CONTROL, 64)
  */
 #define VMX_REGS_LAZY_LOAD_SET	((1 << VCPU_REG_RIP) |         \
 				(1 << VCPU_REGS_RSP) |          \
-				(1 << VCPU_EXREG_RFLAGS) |      \
-				(1 << VCPU_EXREG_PDPTR) |       \
-				(1 << VCPU_EXREG_SEGMENTS) |    \
-				(1 << VCPU_EXREG_CR0) |         \
-				(1 << VCPU_EXREG_CR3) |         \
-				(1 << VCPU_EXREG_CR4) |         \
-				(1 << VCPU_EXREG_EXIT_INFO_1) | \
-				(1 << VCPU_EXREG_EXIT_INFO_2))
+				(1 << VCPU_REG_RFLAGS) |      \
+				(1 << VCPU_REG_PDPTR) |       \
+				(1 << VCPU_REG_SEGMENTS) |    \
+				(1 << VCPU_REG_CR0) |         \
+				(1 << VCPU_REG_CR3) |         \
+				(1 << VCPU_REG_CR4) |         \
+				(1 << VCPU_REG_EXIT_INFO_1) | \
+				(1 << VCPU_REG_EXIT_INFO_2))
 
 static inline unsigned long vmx_l1_guest_owned_cr0_bits(void)
 {
diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index 879cdeb6adde..dd39ccbff0d6 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -1090,14 +1090,14 @@ int load_pdptrs(struct kvm_vcpu *vcpu, unsigned long cr3)
 	}
 
 	/*
-	 * Marking VCPU_EXREG_PDPTR dirty doesn't work for !tdp_enabled.
+	 * Marking VCPU_REG_PDPTR dirty doesn't work for !tdp_enabled.
 	 * Shadow page roots need to be reconstructed instead.
 	 */
 	if (!tdp_enabled && memcmp(mmu->pdptrs, pdpte, sizeof(mmu->pdptrs)))
 		kvm_mmu_free_roots(vcpu->kvm, mmu, KVM_MMU_ROOT_CURRENT);
 
 	memcpy(mmu->pdptrs, pdpte, sizeof(mmu->pdptrs));
-	kvm_register_mark_dirty(vcpu, VCPU_EXREG_PDPTR);
+	kvm_register_mark_dirty(vcpu, VCPU_REG_PDPTR);
 	kvm_make_request(KVM_REQ_LOAD_MMU_PGD, vcpu);
 	vcpu->arch.pdptrs_from_userspace = false;
 
@@ -1478,7 +1478,7 @@ int kvm_set_cr3(struct kvm_vcpu *vcpu, unsigned long cr3)
 		kvm_mmu_new_pgd(vcpu, cr3);
 
 	vcpu->arch.cr3 = cr3;
-	kvm_register_mark_dirty(vcpu, VCPU_EXREG_CR3);
+	kvm_register_mark_dirty(vcpu, VCPU_REG_CR3);
 	/* Do not call post_set_cr3, we do not get here for confidential guests.  */
 
 handle_tlb_flush:
@@ -12446,7 +12446,7 @@ static int __set_sregs_common(struct kvm_vcpu *vcpu, struct kvm_sregs *sregs,
 	vcpu->arch.cr2 = sregs->cr2;
 	*mmu_reset_needed |= kvm_read_cr3(vcpu) != sregs->cr3;
 	vcpu->arch.cr3 = sregs->cr3;
-	kvm_register_mark_dirty(vcpu, VCPU_EXREG_CR3);
+	kvm_register_mark_dirty(vcpu, VCPU_REG_CR3);
 	kvm_x86_call(post_set_cr3)(vcpu, sregs->cr3);
 
 	kvm_set_cr8(vcpu, sregs->cr8);
@@ -12539,7 +12539,7 @@ static int __set_sregs2(struct kvm_vcpu *vcpu, struct kvm_sregs2 *sregs2)
 		for (i = 0; i < 4 ; i++)
 			kvm_pdptr_write(vcpu, i, sregs2->pdptrs[i]);
 
-		kvm_register_mark_dirty(vcpu, VCPU_EXREG_PDPTR);
+		kvm_register_mark_dirty(vcpu, VCPU_REG_PDPTR);
 		mmu_reset_needed = 1;
 		vcpu->arch.pdptrs_from_userspace = true;
 	}
@@ -13084,7 +13084,7 @@ void kvm_vcpu_reset(struct kvm_vcpu *vcpu, bool init_event)
 	kvm_rip_write(vcpu, 0xfff0);
 
 	vcpu->arch.cr3 = 0;
-	kvm_register_mark_dirty(vcpu, VCPU_EXREG_CR3);
+	kvm_register_mark_dirty(vcpu, VCPU_REG_CR3);
 
 	/*
 	 * CR0.CD/NW are set on RESET, preserved on INIT.  Note, some versions
@@ -14296,7 +14296,7 @@ int kvm_handle_invpcid(struct kvm_vcpu *vcpu, unsigned long type, gva_t gva)
 		 * the RAP (Return Address Predicator).
 		 */
 		if (guest_cpu_cap_has(vcpu, X86_FEATURE_ERAPS))
-			kvm_register_is_dirty(vcpu, VCPU_EXREG_ERAPS);
+			kvm_register_is_dirty(vcpu, VCPU_REG_ERAPS);
 
 		kvm_invalidate_pcid(vcpu, operand.pcid);
 		return kvm_skip_emulated_instruction(vcpu);
@@ -14312,7 +14312,7 @@ int kvm_handle_invpcid(struct kvm_vcpu *vcpu, unsigned long type, gva_t gva)
 		fallthrough;
 	case INVPCID_TYPE_ALL_INCL_GLOBAL:
 		/*
-		 * Don't bother marking VCPU_EXREG_ERAPS dirty, SVM will take
+		 * Don't bother marking VCPU_REG_ERAPS dirty, SVM will take
 		 * care of doing so when emulating the full guest TLB flush
 		 * (the RAP is cleared on all implicit TLB flushes).
 		 */

---

## [4] Sean Christopherson — 2026-03-10
*Subject: [PATCH 3/7] KVM: nVMX: Do a bitwise-AND of regs_avail when switching
 active VMCS*

When switching between vmcs01 and vmcs02, do a bitwise-AND of regs_avail
to effectively reset the mask for the new VMCS, purely to be consistent
with all other "full" writes of regs_avail.  In practice, a straight write
versus a bitwise-AND will yield the same result, as kvm_arch_vcpu_create()
marks *all* registers available (and dirty), and KVM never marks registers
unavailable unless they're lazily loaded.

This will allow adding wrapper APIs to set regs_{avail,dirty} without
having to add special handling for a nVMX use case that doesn't exist in
practice.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/vmx/nested.c | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)

diff --git a/arch/x86/kvm/vmx/nested.c b/arch/x86/kvm/vmx/nested.c
index 942acc46f91d..af2aaef38502 100644
--- a/arch/x86/kvm/vmx/nested.c
+++ b/arch/x86/kvm/vmx/nested.c
@@ -310,7 +310,7 @@ static void vmx_switch_vmcs(struct kvm_vcpu *vcpu, struct loaded_vmcs *vmcs)
 	vmx_sync_vmcs_host_state(vmx, prev);
 	put_cpu();
 
-	vcpu->arch.regs_avail = ~VMX_REGS_LAZY_LOAD_SET;
+	vcpu->arch.regs_avail &= ~VMX_REGS_LAZY_LOAD_SET;
 
 	/*
 	 * All lazily updated registers will be reloaded from VMCS12 on both

---

## [5] Sean Christopherson — 2026-03-10
*Subject: [PATCH 4/7] KVM: x86: Add wrapper APIs to reset dirty/available
 register masks*

Add wrappers for setting regs_{avail,dirty} in anticipation of turning the
fields into proper bitmaps, at which point direct writes won't work so
well.

Deliberately leave the initialization in kvm_arch_vcpu_create() as-is,
because the regs_avail logic in particular is special in that it's the one
and only place where KVM marks eagerly synchronized registers as available.

No functional change intended.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/kvm_cache_regs.h | 19 +++++++++++++++++++
 arch/x86/kvm/svm/svm.c        |  4 ++--
 arch/x86/kvm/vmx/nested.c     |  4 ++--
 arch/x86/kvm/vmx/tdx.c        |  2 +-
 arch/x86/kvm/vmx/vmx.c        |  4 ++--
 5 files changed, 26 insertions(+), 7 deletions(-)

diff --git a/arch/x86/kvm/kvm_cache_regs.h b/arch/x86/kvm/kvm_cache_regs.h
index ac1f9867a234..94e31cf38cb8 100644
--- a/arch/x86/kvm/kvm_cache_regs.h
+++ b/arch/x86/kvm/kvm_cache_regs.h
@@ -105,6 +105,25 @@ static __always_inline bool kvm_register_test_and_mark_available(struct kvm_vcpu
 	return arch___test_and_set_bit(reg, (unsigned long *)&vcpu->arch.regs_avail);
 }
 
+static __always_inline void kvm_reset_available_registers(struct kvm_vcpu *vcpu,
+							  u32 available_mask)
+{
+	/*
+	 * Note the bitwise-AND!  In practice, a straight write would also work
+	 * as KVM initializes the mask to all ones and never clears registers
+	 * that are eagerly synchronized.  Using a bitwise-AND adds a bit of
+	 * sanity checking as incorrectly marking an eagerly sync'd register
+	 * unavailable will generate a WARN due to an unexpected cache request.
+	 */
+	vcpu->arch.regs_avail &= available_mask;
+}
+
+static __always_inline void kvm_reset_dirty_registers(struct kvm_vcpu *vcpu,
+						      u32 dirty_mask)
+{
+	vcpu->arch.regs_dirty = dirty_mask;
+}
+
 /*
  * The "raw" register helpers are only for cases where the full 64 bits of a
  * register are read/written irrespective of current vCPU mode.  In other words,
diff --git a/arch/x86/kvm/svm/svm.c b/arch/x86/kvm/svm/svm.c
index 1712c21f4128..1a6626c32188 100644
--- a/arch/x86/kvm/svm/svm.c
+++ b/arch/x86/kvm/svm/svm.c
@@ -4524,7 +4524,7 @@ static __no_kcsan fastpath_t svm_vcpu_run(struct kvm_vcpu *vcpu, u64 run_flags)
 		vcpu->arch.regs[VCPU_REGS_RSP] = svm->vmcb->save.rsp;
 		vcpu->arch.rip = svm->vmcb->save.rip;
 	}
-	vcpu->arch.regs_dirty = 0;
+	kvm_reset_dirty_registers(vcpu, 0);
 
 	if (unlikely(svm->vmcb->control.exit_code == SVM_EXIT_NMI))
 		kvm_before_interrupt(vcpu, KVM_HANDLING_NMI);
@@ -4570,7 +4570,7 @@ static __no_kcsan fastpath_t svm_vcpu_run(struct kvm_vcpu *vcpu, u64 run_flags)
 		vcpu->arch.apf.host_apf_flags =
 			kvm_read_and_reset_apf_flags();
 
-	vcpu->arch.regs_avail &= ~SVM_REGS_LAZY_LOAD_SET;
+	kvm_reset_available_registers(vcpu, ~SVM_REGS_LAZY_LOAD_SET);
 
 	if (!msr_write_intercepted(vcpu, MSR_AMD64_PERF_CNTR_GLOBAL_CTL))
 		rdmsrq(MSR_AMD64_PERF_CNTR_GLOBAL_CTL, vcpu_to_pmu(vcpu)->global_ctrl);
diff --git a/arch/x86/kvm/vmx/nested.c b/arch/x86/kvm/vmx/nested.c
index af2aaef38502..d4ba64bde709 100644
--- a/arch/x86/kvm/vmx/nested.c
+++ b/arch/x86/kvm/vmx/nested.c
@@ -310,13 +310,13 @@ static void vmx_switch_vmcs(struct kvm_vcpu *vcpu, struct loaded_vmcs *vmcs)
 	vmx_sync_vmcs_host_state(vmx, prev);
 	put_cpu();
 
-	vcpu->arch.regs_avail &= ~VMX_REGS_LAZY_LOAD_SET;
+	kvm_reset_available_registers(vcpu, ~VMX_REGS_LAZY_LOAD_SET);
 
 	/*
 	 * All lazily updated registers will be reloaded from VMCS12 on both
 	 * vmentry and vmexit.
 	 */
-	vcpu->arch.regs_dirty = 0;
+	kvm_reset_dirty_registers(vcpu, 0);
 }
 
 static void nested_put_vmcs12_pages(struct kvm_vcpu *vcpu)
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index c23ec4ac8bc8..d4cb6dc8098f 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1098,7 +1098,7 @@ fastpath_t tdx_vcpu_run(struct kvm_vcpu *vcpu, u64 run_flags)
 
 	tdx_load_host_xsave_state(vcpu);
 
-	vcpu->arch.regs_avail &= TDX_REGS_AVAIL_SET;
+	kvm_reset_available_registers(vcpu, TDX_REGS_AVAIL_SET);
 
 	if (unlikely(tdx->vp_enter_ret == EXIT_REASON_EPT_MISCONFIG))
 		return EXIT_FASTPATH_NONE;
diff --git a/arch/x86/kvm/vmx/vmx.c b/arch/x86/kvm/vmx/vmx.c
index ed44eb5b4349..217ea6e72c2f 100644
--- a/arch/x86/kvm/vmx/vmx.c
+++ b/arch/x86/kvm/vmx/vmx.c
@@ -7472,7 +7472,7 @@ static noinstr void vmx_vcpu_enter_exit(struct kvm_vcpu *vcpu,
 				   flags);
 
 	vcpu->arch.cr2 = native_read_cr2();
-	vcpu->arch.regs_avail &= ~VMX_REGS_LAZY_LOAD_SET;
+	kvm_reset_available_registers(vcpu, ~VMX_REGS_LAZY_LOAD_SET);
 
 	vmx->idt_vectoring_info = 0;
 
@@ -7538,7 +7538,7 @@ fastpath_t vmx_vcpu_run(struct kvm_vcpu *vcpu, u64 run_flags)
 		vmcs_writel(GUEST_RSP, vcpu->arch.regs[VCPU_REGS_RSP]);
 	if (kvm_register_is_dirty(vcpu, VCPU_REG_RIP))
 		vmcs_writel(GUEST_RIP, vcpu->arch.rip);
-	vcpu->arch.regs_dirty = 0;
+	kvm_reset_dirty_registers(vcpu, 0);
 
 	if (run_flags & KVM_RUN_LOAD_GUEST_DR6)
 		set_debugreg(vcpu->arch.dr6, 6);

---

## [6] Sean Christopherson — 2026-03-10
*Subject: [PATCH 5/7] KVM: x86: Track available/dirty register masks as
 "unsigned long" values*

Convert regs_{avail,dirty} and all related masks to "unsigned long" values
as an intermediate step towards declaring the fields as actual bitmaps, and
as a step toward support APX, which will push the total number of registers
beyond 32 on 64-bit kernels.

Opportunistically convert TDX's ULL bitmask to a UL to match everything
else (TDX is 64-bit only, so it's a nop in the end).

No functional change intended.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/kvm_host.h |  4 ++--
 arch/x86/kvm/kvm_cache_regs.h   |  4 ++--
 arch/x86/kvm/svm/svm.h          |  2 +-
 arch/x86/kvm/vmx/tdx.c          | 34 ++++++++++++++++-----------------
 arch/x86/kvm/vmx/vmx.h          | 20 +++++++++----------
 5 files changed, 32 insertions(+), 32 deletions(-)

diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h
index 3af5e2661ade..734c2eee58e0 100644
--- a/arch/x86/include/asm/kvm_host.h
+++ b/arch/x86/include/asm/kvm_host.h
@@ -802,8 +802,8 @@ struct kvm_vcpu_arch {
 	 */
 	unsigned long regs[NR_VCPU_GENERAL_PURPOSE_REGS];
 	unsigned long rip;
-	u32 regs_avail;
-	u32 regs_dirty;
+	unsigned long regs_avail;
+	unsigned long regs_dirty;
 
 	unsigned long cr0;
 	unsigned long cr0_guest_owned_bits;
diff --git a/arch/x86/kvm/kvm_cache_regs.h b/arch/x86/kvm/kvm_cache_regs.h
index 94e31cf38cb8..5de6c7dfd63b 100644
--- a/arch/x86/kvm/kvm_cache_regs.h
+++ b/arch/x86/kvm/kvm_cache_regs.h
@@ -106,7 +106,7 @@ static __always_inline bool kvm_register_test_and_mark_available(struct kvm_vcpu
 }
 
 static __always_inline void kvm_reset_available_registers(struct kvm_vcpu *vcpu,
-							  u32 available_mask)
+							  unsigned long available_mask)
 {
 	/*
 	 * Note the bitwise-AND!  In practice, a straight write would also work
@@ -119,7 +119,7 @@ static __always_inline void kvm_reset_available_registers(struct kvm_vcpu *vcpu,
 }
 
 static __always_inline void kvm_reset_dirty_registers(struct kvm_vcpu *vcpu,
-						      u32 dirty_mask)
+						      unsigned long dirty_mask)
 {
 	vcpu->arch.regs_dirty = dirty_mask;
 }
diff --git a/arch/x86/kvm/svm/svm.h b/arch/x86/kvm/svm/svm.h
index dea46130aa24..7010db21e8cc 100644
--- a/arch/x86/kvm/svm/svm.h
+++ b/arch/x86/kvm/svm/svm.h
@@ -460,7 +460,7 @@ static inline bool svm_is_vmrun_failure(u64 exit_code)
  * KVM_REQ_LOAD_MMU_PGD is always requested when the cached vcpu->arch.cr3
  * is changed.  svm_load_mmu_pgd() then syncs the new CR3 value into the VMCB.
  */
-#define SVM_REGS_LAZY_LOAD_SET	(1 << VCPU_REG_PDPTR)
+#define SVM_REGS_LAZY_LOAD_SET	(BIT(VCPU_REG_PDPTR))
 
 static inline void __vmcb_set_intercept(unsigned long *intercepts, u32 bit)
 {
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index d4cb6dc8098f..1e4f59cfdc0a 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1013,23 +1013,23 @@ static fastpath_t tdx_exit_handlers_fastpath(struct kvm_vcpu *vcpu)
 	return EXIT_FASTPATH_NONE;
 }
 
-#define TDX_REGS_AVAIL_SET	(BIT_ULL(VCPU_REG_EXIT_INFO_1) | \
-				 BIT_ULL(VCPU_REG_EXIT_INFO_2) | \
-				 BIT_ULL(VCPU_REGS_RAX) | \
-				 BIT_ULL(VCPU_REGS_RBX) | \
-				 BIT_ULL(VCPU_REGS_RCX) | \
-				 BIT_ULL(VCPU_REGS_RDX) | \
-				 BIT_ULL(VCPU_REGS_RBP) | \
-				 BIT_ULL(VCPU_REGS_RSI) | \
-				 BIT_ULL(VCPU_REGS_RDI) | \
-				 BIT_ULL(VCPU_REGS_R8) | \
-				 BIT_ULL(VCPU_REGS_R9) | \
-				 BIT_ULL(VCPU_REGS_R10) | \
-				 BIT_ULL(VCPU_REGS_R11) | \
-				 BIT_ULL(VCPU_REGS_R12) | \
-				 BIT_ULL(VCPU_REGS_R13) | \
-				 BIT_ULL(VCPU_REGS_R14) | \
-				 BIT_ULL(VCPU_REGS_R15))
+#define TDX_REGS_AVAIL_SET	(BIT(VCPU_REG_EXIT_INFO_1) | \
+				 BIT(VCPU_REG_EXIT_INFO_2) | \
+				 BIT(VCPU_REGS_RAX) | \
+				 BIT(VCPU_REGS_RBX) | \
+				 BIT(VCPU_REGS_RCX) | \
+				 BIT(VCPU_REGS_RDX) | \
+				 BIT(VCPU_REGS_RBP) | \
+				 BIT(VCPU_REGS_RSI) | \
+				 BIT(VCPU_REGS_RDI) | \
+				 BIT(VCPU_REGS_R8) | \
+				 BIT(VCPU_REGS_R9) | \
+				 BIT(VCPU_REGS_R10) | \
+				 BIT(VCPU_REGS_R11) | \
+				 BIT(VCPU_REGS_R12) | \
+				 BIT(VCPU_REGS_R13) | \
+				 BIT(VCPU_REGS_R14) | \
+				 BIT(VCPU_REGS_R15))
 
 static void tdx_load_host_xsave_state(struct kvm_vcpu *vcpu)
 {
diff --git a/arch/x86/kvm/vmx/vmx.h b/arch/x86/kvm/vmx/vmx.h
index d3255a054185..0962374c4cd3 100644
--- a/arch/x86/kvm/vmx/vmx.h
+++ b/arch/x86/kvm/vmx/vmx.h
@@ -623,16 +623,16 @@ BUILD_CONTROLS_SHADOW(tertiary_exec, TERTIARY_VM_EXEC_CONTROL, 64)
  * cache on demand.  Other registers not listed here are synced to
  * the cache immediately after VM-Exit.
  */
-#define VMX_REGS_LAZY_LOAD_SET	((1 << VCPU_REG_RIP) |         \
-				(1 << VCPU_REGS_RSP) |          \
-				(1 << VCPU_REG_RFLAGS) |      \
-				(1 << VCPU_REG_PDPTR) |       \
-				(1 << VCPU_REG_SEGMENTS) |    \
-				(1 << VCPU_REG_CR0) |         \
-				(1 << VCPU_REG_CR3) |         \
-				(1 << VCPU_REG_CR4) |         \
-				(1 << VCPU_REG_EXIT_INFO_1) | \
-				(1 << VCPU_REG_EXIT_INFO_2))
+#define VMX_REGS_LAZY_LOAD_SET	(BIT(VCPU_REGS_RSP) |		\
+				 BIT(VCPU_REG_RIP) |		\
+				 BIT(VCPU_REG_RFLAGS) |		\
+				 BIT(VCPU_REG_PDPTR) |		\
+				 BIT(VCPU_REG_SEGMENTS) |	\
+				 BIT(VCPU_REG_CR0) |		\
+				 BIT(VCPU_REG_CR3) |		\
+				 BIT(VCPU_REG_CR4) |		\
+				 BIT(VCPU_REG_EXIT_INFO_1) |	\
+				 BIT(VCPU_REG_EXIT_INFO_2))
 
 static inline unsigned long vmx_l1_guest_owned_cr0_bits(void)
 {

---

## [7] Sean Christopherson — 2026-03-10
*Subject: [PATCH 6/7] KVM: x86: Use a proper bitmap for tracking
 available/dirty registers*

Define regs_{avail,dirty} as bitmaps instead of U32s to harden against
overflow, and to allow for dynamically sizing the bitmaps when APX comes
along, which will add 16 more GPRs (R16-R31) and thus increase the total
number of registers beyond 32.

Open code writes in the "reset" APIs, as the writes are hot paths and
bitmap_write() is complete overkill for what KVM needs.  Even better,
hardcoding writes to entry '0' in the array is a perfect excuse to assert
that the array contains exactly one entry, e.g. to effectively add guard
against defining R16-R31 in 32-bit kernels.

For all intents and purposes, no functional change intended even though
using bitmap_fill() will mean "undefined" registers are no longer marked
available and dirty (KVM should never be querying those bits).

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/kvm_host.h |  6 ++++--
 arch/x86/kvm/kvm_cache_regs.h   | 21 +++++++++++++--------
 arch/x86/kvm/x86.c              |  4 ++--
 3 files changed, 19 insertions(+), 12 deletions(-)

diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h
index 734c2eee58e0..cff9023f12c7 100644
--- a/arch/x86/include/asm/kvm_host.h
+++ b/arch/x86/include/asm/kvm_host.h
@@ -211,6 +211,8 @@ enum kvm_reg {
 	VCPU_REG_SEGMENTS,
 	VCPU_REG_EXIT_INFO_1,
 	VCPU_REG_EXIT_INFO_2,
+
+	NR_VCPU_TOTAL_REGS,
 };
 
 enum {
@@ -802,8 +804,8 @@ struct kvm_vcpu_arch {
 	 */
 	unsigned long regs[NR_VCPU_GENERAL_PURPOSE_REGS];
 	unsigned long rip;
-	unsigned long regs_avail;
-	unsigned long regs_dirty;
+	DECLARE_BITMAP(regs_avail, NR_VCPU_TOTAL_REGS);
+	DECLARE_BITMAP(regs_dirty, NR_VCPU_TOTAL_REGS);
 
 	unsigned long cr0;
 	unsigned long cr0_guest_owned_bits;
diff --git a/arch/x86/kvm/kvm_cache_regs.h b/arch/x86/kvm/kvm_cache_regs.h
index 5de6c7dfd63b..782710829608 100644
--- a/arch/x86/kvm/kvm_cache_regs.h
+++ b/arch/x86/kvm/kvm_cache_regs.h
@@ -67,29 +67,29 @@ static inline bool kvm_register_is_available(struct kvm_vcpu *vcpu,
 					     enum kvm_reg reg)
 {
 	kvm_assert_register_caching_allowed(vcpu);
-	return test_bit(reg, (unsigned long *)&vcpu->arch.regs_avail);
+	return test_bit(reg, vcpu->arch.regs_avail);
 }
 
 static inline bool kvm_register_is_dirty(struct kvm_vcpu *vcpu,
 					 enum kvm_reg reg)
 {
 	kvm_assert_register_caching_allowed(vcpu);
-	return test_bit(reg, (unsigned long *)&vcpu->arch.regs_dirty);
+	return test_bit(reg, vcpu->arch.regs_dirty);
 }
 
 static inline void kvm_register_mark_available(struct kvm_vcpu *vcpu,
 					       enum kvm_reg reg)
 {
 	kvm_assert_register_caching_allowed(vcpu);
-	__set_bit(reg, (unsigned long *)&vcpu->arch.regs_avail);
+	__set_bit(reg, vcpu->arch.regs_avail);
 }
 
 static inline void kvm_register_mark_dirty(struct kvm_vcpu *vcpu,
 					   enum kvm_reg reg)
 {
 	kvm_assert_register_caching_allowed(vcpu);
-	__set_bit(reg, (unsigned long *)&vcpu->arch.regs_avail);
-	__set_bit(reg, (unsigned long *)&vcpu->arch.regs_dirty);
+	__set_bit(reg, vcpu->arch.regs_avail);
+	__set_bit(reg, vcpu->arch.regs_dirty);
 }
 
 /*
@@ -102,12 +102,15 @@ static __always_inline bool kvm_register_test_and_mark_available(struct kvm_vcpu
 								 enum kvm_reg reg)
 {
 	kvm_assert_register_caching_allowed(vcpu);
-	return arch___test_and_set_bit(reg, (unsigned long *)&vcpu->arch.regs_avail);
+	return arch___test_and_set_bit(reg, vcpu->arch.regs_avail);
 }
 
 static __always_inline void kvm_reset_available_registers(struct kvm_vcpu *vcpu,
 							  unsigned long available_mask)
 {
+	BUILD_BUG_ON(sizeof(available_mask) != sizeof(vcpu->arch.regs_avail[0]));
+	BUILD_BUG_ON(ARRAY_SIZE(vcpu->arch.regs_avail) != 1);
+
 	/*
 	 * Note the bitwise-AND!  In practice, a straight write would also work
 	 * as KVM initializes the mask to all ones and never clears registers
@@ -115,13 +118,15 @@ static __always_inline void kvm_reset_available_registers(struct kvm_vcpu *vcpu,
 	 * sanity checking as incorrectly marking an eagerly sync'd register
 	 * unavailable will generate a WARN due to an unexpected cache request.
 	 */
-	vcpu->arch.regs_avail &= available_mask;
+	vcpu->arch.regs_avail[0] &= available_mask;
 }
 
 static __always_inline void kvm_reset_dirty_registers(struct kvm_vcpu *vcpu,
 						      unsigned long dirty_mask)
 {
-	vcpu->arch.regs_dirty = dirty_mask;
+	BUILD_BUG_ON(sizeof(dirty_mask) != sizeof(vcpu->arch.regs_dirty[0]));
+	BUILD_BUG_ON(ARRAY_SIZE(vcpu->arch.regs_dirty) != 1);
+	vcpu->arch.regs_dirty[0] = dirty_mask;
 }
 
 /*
diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index dd39ccbff0d6..c1e1b3030786 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -12809,8 +12809,8 @@ int kvm_arch_vcpu_create(struct kvm_vcpu *vcpu)
 	int r;
 
 	vcpu->arch.last_vmentry_cpu = -1;
-	vcpu->arch.regs_avail = ~0;
-	vcpu->arch.regs_dirty = ~0;
+	bitmap_fill(vcpu->arch.regs_avail, NR_VCPU_TOTAL_REGS);
+	bitmap_fill(vcpu->arch.regs_dirty, NR_VCPU_TOTAL_REGS);
 
 	kvm_gpc_init(&vcpu->arch.pv_time, vcpu->kvm);

---

## [8] Sean Christopherson — 2026-03-10
*Subject: [PATCH 7/7] *** DO NOT MERGE *** KVM: x86: Pretend that APX is
 supported on 64-bit kernels*

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/kvm_host.h | 21 +++++++++++++++++++++
 1 file changed, 21 insertions(+)

diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h
index cff9023f12c7..3d9c8cc9d515 100644
--- a/arch/x86/include/asm/kvm_host.h
+++ b/arch/x86/include/asm/kvm_host.h
@@ -190,6 +190,27 @@ enum kvm_reg {
 	VCPU_REGS_R13 = __VCPU_REGS_R13,
 	VCPU_REGS_R14 = __VCPU_REGS_R14,
 	VCPU_REGS_R15 = __VCPU_REGS_R15,
+#define CONFIG_X86_APX
+
+#endif
+
+#ifdef CONFIG_X86_APX
+	VCPU_REG_R16 = VCPU_REGS_R15 + 1,
+	VCPU_REG_R17,
+	VCPU_REG_R18,
+	VCPU_REG_R19,
+	VCPU_REG_R20,
+	VCPU_REG_R21,
+	VCPU_REG_R22,
+	VCPU_REG_R23,
+	VCPU_REG_R24,
+	VCPU_REG_R25,
+	VCPU_REG_R26,
+	VCPU_REG_R27,
+	VCPU_REG_R28,
+	VCPU_REG_R29,
+	VCPU_REG_R30,
+	VCPU_REG_R31,
 #endif
 	NR_VCPU_GENERAL_PURPOSE_REGS,

---

## [9] Yosry Ahmed — 2026-03-10
*Subject: Re: [PATCH 4/7] KVM: x86: Add wrapper APIs to reset dirty/available
 register masks*

On Tue, Mar 10, 2026 at 5:34 PM Sean Christopherson <seanjc@google.com> wrote:
>
> Add wrappers for setting regs_{avail,dirty} in anticipation of turning the

Not closely following this series and don't know this code well, but
this API is very confusing for me tbh. Especially in comparison with
kvm_reset_dirty_registers().

Maybe rename this to kvm_clear_available_registers(), and pass in a
"clear_mask", then reverse the polarity:

vcpu->arch.regs_avail &= ~clear_mask;

Most callers are already passing in an inverse of a mask, so might as
well pass the mask as-is and invert it here, and it helps make the
name clear, we're passing in a bitmask to clear from regs_avail.

> +{
> +       /*

---

## [10] Sean Christopherson — 2026-03-11
*Subject: Re: [PATCH 4/7] KVM: x86: Add wrapper APIs to reset dirty/available
 register masks*

On Tue, Mar 10, 2026, Yosry Ahmed wrote:
> On Tue, Mar 10, 2026 at 5:34 PM Sean Christopherson <seanjc@google.com> wrote:
> >

Oh, yeah, I can do something like that.  I originally misread the TDX code and
thought it was explicitly setting regs_avail, and so came up with a roundabout
name.  I didn't revisit the naming or the polarity of the param once I realized
all callers could use the same scheme.

No small part of me is tempted to turn it into a straigh "set" though, unless I'm
missing something, the whole &= business is an implementation quirk.

> Most callers are already passing in an inverse of a mask, so might as
> well pass the mask as-is and invert it here, and it helps make the

---

## [11] Yosry Ahmed — 2026-03-11
*Subject: Re: [PATCH 4/7] KVM: x86: Add wrapper APIs to reset dirty/available
 register masks*

On Wed, Mar 11, 2026 at 6:31 AM Sean Christopherson <seanjc@google.com> wrote:
>
> On Tue, Mar 10, 2026, Yosry Ahmed wrote:

Not sure what you mean here, this (for example)?

vcpu->arch.regs_avail = ~SVM_REGS_LAZY_LOAD_SET;

Does this mean all other bits in regs_avail should already be set for
all users so the &= is unnecessary? Or it doesn't matter if they're
set or not?

---

## [12] Paolo Bonzini — 2026-03-11
*Subject: Re: [PATCH 2/7] KVM: x86: Drop the "EX" part of "EXREG" to avoid
 collision with APX*

On 3/11/26 01:33, Sean Christopherson wrote:
> Now that NR_VCPU_REGS is no longer a thing, drop the "EX" is for
> extended (or maybe extra?") prefix from non-GRP registers to avoid a

And also, now that RIP is effectively an EXREG.

Paolo

---

## [13] Paolo Bonzini — 2026-03-11
*Subject: Re: [PATCH 4/7] KVM: x86: Add wrapper APIs to reset dirty/available
 register masks*

On 3/11/26 14:31, Sean Christopherson wrote:
>> Not closely following this series and don't know this code well, but
>> this API is very confusing for me tbh. Especially in comparison with

I like kvm_clear_available_registers() for this + removing the second 
argument completely for kvm_reset_dirty_registers().

Paolo

---

## [14] Paolo Bonzini — 2026-03-11
*Subject: Re: [PATCH 0/7] KVM: x86: APX reg prep work*

On 3/11/26 01:33, Sean Christopherson wrote:
> Clean up KVM's register tracking and storage in preparation for landing APX,
> which expands the maximum number of GPRs from 16 to 32.

The cleanups in patches 1-4 are nice.

For APX specifically, in abstract it's nice to treat R16-R31 as much as 
possible as regular GPRs.  On the other hand, the extra 16 regs[] 
entries would be more or less unused, the ugly switch statements 
wouldn't go away.  In other words, most of your remarks to Changseok's 
patches would remain...

Paolo

---

## [15] Chang S. Bae — 2026-03-12
*Subject: Re: [PATCH 0/7] KVM: x86: APX reg prep work*

On 3/11/2026 12:01 PM, Paolo Bonzini wrote:
> 
>   On the other hand, the extra 16 regs[] 

I think so...

If the host kernel ever starts using EGPRs, the state would need to be 
switched in the entry code. At that point, they would likely be saved 
somewhere other than XSAVE buffer. In turn, the guest state would also 
need to be saved to regs[] on VM exit.

However, that is sort of what-if scenarios at best. The host kernel 
still manages EGPR context switching through XSAVE. Saving EGPRs into 
regs[] would introduce an oddity to synchronize between two buffers: 
regs[] and gfpu->fpstate, which looks like unnecessary complexity.

So while ugly, the switch statements are a bit of a trade-off here. Also 
bits 16-31 in the extended regs_avail will remain unset with APX=y.

---

## [16] Sean Christopherson — 2026-03-12
*Subject: Re: [PATCH 0/7] KVM: x86: APX reg prep work*

On Thu, Mar 12, 2026, Chang S. Bae wrote:
> On 3/11/2026 12:01 PM, Paolo Bonzini wrote:
> > 

Have you measured performance/latency overhead if KVM goes straight to context
switching R16-R31 at entry/exit?  With PUSH2/POP2, it's "only" 8 more instructions
on each side.

If the overhead is in the noise, I'd be very strongly inclined to say KVM should
swap at entry/exit regardless of kernel behavior so that we don't have to special
case accesses on the back end.

---

## [17] Andrew Cooper — 2026-03-12
*Subject: Re: [PATCH 0/7] KVM: x86: APX reg prep work*

> Have you measured performance/latency overhead if KVM goes straight to context
> switching R16-R31 at entry/exit?  With PUSH2/POP2, it's "only" 8 more instructions

I tried raising this point at plumbers but I don't think it came through
well.

You can't unconditionally use PUSH2/POP2 in the VMExit, because at that
point in time it's the guest's XCR0 in context.  If the guest has APX
disabled, PUSH2 in the VMExit path will #UD.

You either need two VMExit handlers, one APX and one non-APX and choose
based on the guest XCR0 value, or you need a branch prior to regaining
speculative safety, or you need to save/restore XCR0 as the first
action.  It's horrible any way you look at it.

I've asked both Intel and AMD for changes to VT-x/SVM to have a proper
host/guest split of XCR0 which hardware manages on entry/exit.  It's the
only viable option in my opinion, but it's still an unknown period of
time away and not going to exist in the first APX-capable hardware.

~Andrew

---

## [18] Sean Christopherson — 2026-03-12
*Subject: Re: [PATCH 0/7] KVM: x86: APX reg prep work*

On Thu, Mar 12, 2026, Andrew Cooper wrote:
> > Have you measured performance/latency overhead if KVM goes straight to context
> > switching R16-R31 at entry/exit?  With PUSH2/POP2, it's "only" 8 more instructions

Oh good gravy, so that's what the spec means by "inherited XCR0-sensitivity".

> You either need two VMExit handlers, one APX and one non-APX and choose
> based on the guest XCR0 value, or you need a branch prior to regaining

Yeah, no kidding.  And now that KVM loads host XCR0 outside of the fastpath,
moving it back in just to load APX registers and take on all that complexity
makes zero sense.

> I've asked both Intel and AMD for changes to VT-x/SVM to have a proper
> host/guest split of XCR0 which hardware manages on entry/exit.  It's the

+1, especially hardware already swaps XCR0 for SEV-ES+ guests.

Thanks Andy!

---

## [19] Andrew Cooper — 2026-03-12
*Subject: Re: [PATCH 0/7] KVM: x86: APX reg prep work*

On 12/03/2026 6:29 pm, Sean Christopherson wrote:
> On Thu, Mar 12, 2026, Andrew Cooper wrote:
>>> Have you measured performance/latency overhead if KVM goes straight to context

To be clear, I've got tumbleweeds from one, and "oh yeah, we'll think
about that" from the other.  Some extra requests for this would not go
amiss.

~Andrew

---

## [20] Sean Christopherson — 2026-03-12
*Subject: Re: [PATCH 4/7] KVM: x86: Add wrapper APIs to reset dirty/available
 register masks*

On Wed, Mar 11, 2026, Paolo Bonzini wrote:
> On 3/11/26 14:31, Sean Christopherson wrote:
> > > Not closely following this series and don't know this code well, but

Ya, me too.  I almost dropped the param for kvm_reset_dirty_registers(), but
wanted symmetry since the names were the same.  But I like this a lot more.

---

## [21] Chang S. Bae — 2026-03-25
*Subject: Re: [PATCH 0/7] KVM: x86: APX reg prep work*

On 3/12/2026 10:47 AM, Sean Christopherson wrote:
> On Thu, Mar 12, 2026, Chang S. Bae wrote:
>>

No, this looks ugly. If guest EGPR state is saved in vcpu->arch.regs[], 
the APX area there isn't necessary:

When the KVM API exposes state in XSAVE format, the frontend can handle 
this separately. Alongside uABI <-> guest fpstate copy functions, new 
copy functions may deal with the state between uABI <-> VCPU cache.

Further, one could think of exclusion as such:

diff --git a/arch/x86/kernel/fpu/xstate.c b/arch/x86/kernel/fpu/xstate.c
index 76153dfb58c9..5404f9399eea 100644
--- a/arch/x86/kernel/fpu/xstate.c
+++ b/arch/x86/kernel/fpu/xstate.c
@@ -794,9 +794,10 @@ static u64 __init guest_default_mask(void)
{
	/*
	 * Exclude dynamic features, which require userspace opt-in even
-	 * for KVM guests.
+	 * for KVM guests, and APX as extended general-purpose register
+	 * states are saved in the KVM cache separately.
	 */
-	return ~(u64)XFEATURE_MASK_USER_DYNAMIC;
+	return ~((u64)XFEATURE_MASK_USER_DYNAMIC | XFEATURE_MASK_APX);
}

But this default bitmask feeds into the permission bits:

	fpu->guest_perm.__state_perm    = guest_default_cfg.features;
	fpu->guest_perm.__state_size    = guest_default_cfg.size;

This policy looks clear and sensible: permission is granted only if 
space is reserved to save the state. If there is a strong desire to save 
memory, I think it should go through a more thorough review to revisit 
this policy.

> Have you measured performance/latency overhead if KVM goes straight to context
> switching R16-R31 at entry/exit?  With PUSH2/POP2, it's "only" 8 more instructions

Yup, when I check a prototype in the lab, it appears to be in the noise, 
with less than 1% overall variance.

> If the overhead is in the noise, I'd be very strongly inclined to say KVM should
> swap at entry/exit regardless of kernel behavior so that we don't have to special

Note: The hardware request discussed looks to be on-going. I don't know 
the decision yet. But at least for now let me add you to the off-list 
thread for your info.

Right now, I think the entry path may live with guest XCR0 in this 
regard. Since XSETBV is trapped/emulated, the shadow XCR0 remains in 
sync. The entry function can take an additional flag reflecting guest 
XCR0.APX, and gate EGPR access accordingly.

Then, it looks to keep the behavior aligned with the architecture:
   * On initial enable, EGPRs are zeroed on entry following XSETBV exit
   * If APX is disabled and later re-enabled, regs[] retains the state
     while XCR0.APX=0 and restores it when returning from the re-enabling
     XSETBV exit.

---

## [22] Sean Christopherson — 2026-04-02
*Subject: Re: [PATCH 0/7] KVM: x86: APX reg prep work*

On Wed, Mar 25, 2026, Chang S. Bae wrote:
> On 3/12/2026 10:47 AM, Sean Christopherson wrote:
> > On Thu, Mar 12, 2026, Chang S. Bae wrote:

Sorry, you lost me.  What looks ugly?

> If guest EGPR state is saved in vcpu->arch.regs[], the APX area there isn't
> necessary:

And I'm lost again.

---

## [23] Sean Christopherson — 2026-04-02
*Subject: Re: [PATCH 0/7] KVM: x86: APX reg prep work*

On Wed, Mar 11, 2026, Paolo Bonzini wrote:
> On 3/11/26 01:33, Sean Christopherson wrote:
> > Clean up KVM's register tracking and storage in preparation for landing APX,

Hmm, yeah, but only if XSAVE is the source of truth for guest R16-R31.

Do we know what the compiler and/or kernel rules for using R16-R31 will be?
E.g. if C code is allowed to use R16-R31 at will, then KVM will either need to
swap R16-R31 in assembly, or annotate a pile of functions as "no_egpr" or
whatever.
 
At that point, my vote would be to use regs[] to track R16-R31 for KVM's purposes.
IIUC, we could largely ignore XSAVE state at runtime and just ensure R16-R31 are
copied to/from userspace as needed, same as we do for PKRU.

If R16-R31 aren't generally available for C code, then how exactly is APX going
to be used?

Understanding the usage rules for R16-R31 seems fundamental to figuring what to
do in KVM...

---

## [24] Chang S. Bae — 2026-04-02
*Subject: Re: [PATCH 0/7] KVM: x86: APX reg prep work*

On 4/2/2026 4:07 PM, Sean Christopherson wrote:
> On Wed, Mar 25, 2026, Chang S. Bae wrote:
>> On 3/12/2026 10:47 AM, Sean Christopherson wrote:

Oh, this is against my comment above. Keeping regs[] <-> guest fpstate 
in sync will be unnecessarily complex without clear usage (continues below).

>> If guest EGPR state is saved in vcpu->arch.regs[], the APX area there isn't
>> necessary:

Here I made myself pursuing the approach saving/restoring EGPRs via 
regs[] on VM entry/exit. Then a couple of follow-up questions:

   1. What about APX area in guest fpstate?
   2. How to support the state for KVM ABI?

It surely departs from the "XSAVE - the single source of truth" model. 
Then,

   Leave the APX area in guest fpstate unused.

   Copying APX state directly between regs[] and uABI to preserve XSAVE-
   based ABI like in the attached diff.

That's all I'm saying.
diff --git a/arch/x86/kvm/cpuid.c b/arch/x86/kvm/cpuid.c
index fffbf087937d..b3ab2ac827e6 100644
--- a/arch/x86/kvm/cpuid.c
+++ b/arch/x86/kvm/cpuid.c
@@ -59,6 +59,16 @@ void __init kvm_init_xstate_sizes(void)
 	}
 }
 
+u32 xstate_size(unsigned int xfeature)
+{
+	return xstate_sizes[xfeature].eax;
+}
+
+u32 xstate_offset(unsigned int xfeature)
+{
+	return xstate_sizes[xfeature].ebx;
+}
+
 u32 xstate_required_size(u64 xstate_bv, bool compacted)
 {
 	u32 ret = XSAVE_HDR_SIZE + XSAVE_HDR_OFFSET;
diff --git a/arch/x86/kvm/cpuid.h b/arch/x86/kvm/cpuid.h
index 039b8e6f40ba..5ace99dd152b 100644
--- a/arch/x86/kvm/cpuid.h
+++ b/arch/x86/kvm/cpuid.h
@@ -64,6 +64,8 @@ bool kvm_cpuid(struct kvm_vcpu *vcpu, u32 *eax, u32 *ebx,
 
 void __init kvm_init_xstate_sizes(void);
 u32 xstate_required_size(u64 xstate_bv, bool compacted);
+u32 xstate_size(unsigned int xfeature);
+u32 xstate_offset(unsigned int xfeature);
 
 int cpuid_query_maxphyaddr(struct kvm_vcpu *vcpu);
 int cpuid_query_maxguestphyaddr(struct kvm_vcpu *vcpu);
diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index c1e1b3030786..1f064a32b8b7 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -108,6 +108,12 @@ EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_host);
 #define emul_to_vcpu(ctxt) \
 	((struct kvm_vcpu *)(ctxt)->vcpu)
 
+#ifdef CONFIG_KVM_APX
+#define VCPU_EGPRS_PTR(vcpu)   &(vcpu)->arch.regs[VCPU_REGS_R16]
+#else
+#define VCPU_EGPRS_PTR(vcpu)   NULL
+#endif
+
 /* EFER defaults:
  * - enable syscall per default because its emulated by KVM
  * - enable LME and LMA per default on 64 bit KVM
@@ -5804,10 +5810,33 @@ static int kvm_vcpu_ioctl_x86_set_debugregs(struct kvm_vcpu *vcpu,
 	return 0;
 }
 
+static void kvm_copy_vcpu_regs_to_uabi(struct kvm_vcpu *vcpu, struct kvm_xsave *uabi_xsave)
+{
+	union fpregs_state *xstate = (union fpregs_state *)uabi_xsave->region;
+	void *uabi_apx = (void*)uabi_xsave->region + xstate_offset(XFEATURE_APX);
+	void *vcpu_egprs = VCPU_EGPRS_PTR(vcpu);
+
+	if (!vcpu_egprs)
+		return;
 
-static int kvm_vcpu_ioctl_x86_get_xsave2(struct kvm_vcpu *vcpu,
-					 u8 *state, unsigned int size)
+	memcpy(uabi_apx, vcpu_egprs, xstate_size(XFEATURE_APX));
+	xstate->xsave.header.xfeatures |= XFEATURE_MASK_APX;
+}
+
+static void kvm_copy_uabi_to_vcpu_regs(struct kvm_vcpu *vcpu, struct kvm_xsave *uabi_xsave)
 {
+	union fpregs_state *xstate = (union fpregs_state *)uabi_xsave->region;
+	void *uabi_apx = (void*)uabi_xsave->region + xstate_offset(XFEATURE_APX);
+	void *vcpu_egprs = VCPU_EGPRS_PTR(vcpu);
+
+	if (vcpu_egprs && xstate->xsave.header.xfeatures & XFEATURE_MASK_APX)
+		memcpy(vcpu_egprs, uabi_apx, xstate_size(XFEATURE_APX));
+}
+
+static int kvm_vcpu_ioctl_x86_get_xsave2(struct kvm_vcpu *vcpu, struct kvm_xsave *guest_xsave,
+					 unsigned int size)
+{
+
 	/*
 	 * Only copy state for features that are enabled for the guest.  The
 	 * state itself isn't problematic, but setting bits in the header for
@@ -5826,15 +5855,23 @@ static int kvm_vcpu_ioctl_x86_get_xsave2(struct kvm_vcpu *vcpu,
 	if (fpstate_is_confidential(&vcpu->arch.guest_fpu))
 		return vcpu->kvm->arch.has_protected_state ? -EINVAL : 0;
 
-	fpu_copy_guest_fpstate_to_uabi(&vcpu->arch.guest_fpu, state, size,
+	/*
+	 * The generic XSAVE copy function zeros out areas not present in
+	 * guest fpstate. Those not in fpstate but in somewhere else,
+	 * like EGPRs, should be copied after this.
+	 */
+	fpu_copy_guest_fpstate_to_uabi(&vcpu->arch.guest_fpu, guest_xsave->region, size,
 				       supported_xcr0, vcpu->arch.pkru);
+
+	kvm_copy_vcpu_regs_to_uabi(vcpu, guest_xsave);
+
 	return 0;
 }
 
 static int kvm_vcpu_ioctl_x86_get_xsave(struct kvm_vcpu *vcpu,
 					struct kvm_xsave *guest_xsave)
 {
-	return kvm_vcpu_ioctl_x86_get_xsave2(vcpu, (void *)guest_xsave->region,
+	return kvm_vcpu_ioctl_x86_get_xsave2(vcpu, guest_xsave,
 					     sizeof(guest_xsave->region));
 }
 
@@ -5853,6 +5890,8 @@ static int kvm_vcpu_ioctl_x86_set_xsave(struct kvm_vcpu *vcpu,
 	 */
 	xstate->xsave.header.xfeatures &= ~vcpu->arch.guest_fpu.fpstate->xfd;
 
+	kvm_copy_uabi_to_vcpu_regs(vcpu, guest_xsave);
+
 	return fpu_copy_uabi_to_guest_fpstate(&vcpu->arch.guest_fpu,
 					      guest_xsave->region,
 					      kvm_caps.supported_xcr0,
@@ -6464,7 +6503,7 @@ long kvm_arch_vcpu_ioctl(struct file *filp,
 		if (!u.xsave)
 			break;
 
-		r = kvm_vcpu_ioctl_x86_get_xsave2(vcpu, u.buffer, size);
+		r = kvm_vcpu_ioctl_x86_get_xsave2(vcpu, u.xsave, size);
 		if (r < 0)
 			break;

---

## [25] Paolo Bonzini — 2026-04-03
*Subject: Re: [PATCH 0/7] KVM: x86: APX reg prep work*

On 4/3/26 01:19, Sean Christopherson wrote:
> On Wed, Mar 11, 2026, Paolo Bonzini wrote:
>> On 3/11/26 01:33, Sean Christopherson wrote:

On the compiler side, they are enabling APX only with new enough -march, 
or with -march=native if the host has APX. This, by the way, implies 
CONFIG_X86_NATIVE_CPU is currently hosed on Diamond Rapids and newer 
machines.

 From what I remember of Chang Seok Bae's presentation at Plumbers last 
year, right now there's no plan to have the kernel use APX, except 
possibly through the usual kernel_fpu_begin/end.

> E.g. if C code is allowed to use R16-R31 at will, then KVM will either need to
> swap R16-R31 in assembly, or annotate a pile of functions as "no_egpr" or

__attribute__((__target__("no-apxf")), yeah.  Perhaps it could be done 
(kernel-wide) for all noinstr functions, but I think we agree that it's 
not a great idea overall.

> At that point, my vote would be to use regs[] to track R16-R31 for KVM's purposes.
> IIUC, we could largely ignore XSAVE state at runtime and just ensure R16-R31 are

If it can be done efficiently when APX is not available, I suppose 
that's fine.  The KVM code is nicer for sure.

But until the kernel starts using APX, I would do the save/restore near 
kvm_load_xfeatures(), because __vmx_vcpu_run()/__svm_vcpu_run() would 
have to check whether xcr0.apx is set or not.  This is much simpler:

	// runs with host xcr0, so it can assume it includes APX
	// alternatively it could be a static_call(), to only invoke
	// the function if at least one guest enables APX in xcr0
	if (static_cpu_has(X86_FEATURE_APX))
		kvm_apx_save(vcpu);
	kvm_load_xfeatures(vcpu, true);
	...
	kvm_load_xfeatures(vcpu, false);
	// same as above
	if (static_cpu_has(X86_FEATURE_APX))
		kvm_apx_restore(vcpu);

Writing kvm_apx_save() and kvm_apx_restore() already now in a .S file is 
fine but I don't care too much.

If the kernel starts using APX we would have to do the xcr0 changes in 
two steps, one in kvm_load_xfeatures() and one (finalizing the APX bit) 
right around the assembly code for world switching.  That xcr0 update 
would have to be in kvm_apx_save/restore, which would have to 1) be 
rewritten in assembly 2) be called from within 
__vmx_vcpu_run/__svm_vcpu_run.

But it would be premature to do now the two-step save/restore of xcr0.

> If R16-R31 aren't generally available for C code, then how exactly is APX going
> to be used?

Only in userspace, at least for now.

Paolo

> Understanding the usage rules for R16-R31 seems fundamental to figuring what to
> do in KVM...

---

## [26] Dave Hansen — 2026-04-03
*Subject: Re: [PATCH 0/7] KVM: x86: APX reg prep work*

On 4/2/26 16:19, Sean Christopherson wrote:
> Do we know what the compiler and/or kernel rules for using R16-R31 will be?
> E.g. if C code is allowed to use R16-R31 at will, then KVM will either need to

My _assumption_ is that the speedup from using the new GPRs as GPRs in
the kernel is going to be enough for us to support it. This is even
though those kernel binaries won't run on old hardware.

If I'm right, then we're going to have to handle the new GPRs just like
the existing ones and save them on kernel entry before we hit C code.
I'm not sure I want to be messing with XSAVE there. XSAVE requires
munging a header which means even if we used XSAVE we'd need to XSAVE
and then copy things over to pt_regs (assuming we continue using pt_regs).

That doesn't seem like loads of fun because we'll also need to copy out
to the XSAVE UABI spots, like PKRU times 32.

---

## [27] Chang S. Bae — 2026-04-03
*Subject: Re: [PATCH 0/7] KVM: x86: APX reg prep work*

On 4/3/2026 9:03 AM, Paolo Bonzini wrote:
> 
> But until the kernel starts using APX, I would do the save/restore near 
Right, I'd much prefer this. Then, it requires to audit whether any 
fast-path handler could access EGPRs.

But there are cases with the new {RD|WR}MSR (MSR_IMM) instructions that 
appear to access GPRs. Because of this, the EGPR saving/restoring needs 
to happen earlier.

---

## [28] Paolo Bonzini — 2026-04-04
*Subject: Re: [PATCH 0/7] KVM: x86: APX reg prep work*

On Sat, Apr 4, 2026 at 12:05 AM Chang S. Bae <chang.seok.bae@intel.com> wrote:
>
> On 4/3/2026 9:03 AM, Paolo Bonzini wrote:

You're right about fast paths... so something like the attached patch.
It is not too bad to translate into assembly, where it could use
alternatives (in the same way as
RESTORE_GUEST_SPEC_CTRL/RESTORE_GUEST_SPEC_CTRL_BODY) in place of
static_cpu_has(). Maybe it's best to bite the bullet and do it
already...

Paolo

---

## [29] Sean Christopherson — 2026-04-06
*Subject: Re: [PATCH 0/7] KVM: x86: APX reg prep work*

+Andrew

On Sat, Apr 04, 2026, Paolo Bonzini wrote:
> On Sat, Apr 4, 2026 at 12:05 AM Chang S. Bae <chang.seok.bae@intel.com> wrote:
> >

Ya, potential fastpath usage is why I wanted to just context switch around
entry/exit.

> so something like the attached patch.
> It is not too bad to translate into assembly, where it could use

My strong vote is to context switch in assembly, but _conditionally_ context
switch R16-R31.  All of this started from Andrew's comment:

 : You can't unconditionally use PUSH2/POP2 in the VMExit, because at that
 : point in time it's the guest's XCR0 in context.  If the guest has APX
 : disabled, PUSH2 in the VMExit path will #UD.
 : 
 : You either need two VMExit handlers, one APX and one non-APX and choose
 : based on the guest XCR0 value, or you need a branch prior to regaining
 : speculative safety, or you need to save/restore XCR0 as the first
 : action.  It's horrible any way you look at it.

But that second paragraph isn't quite correct, at least not for KVM.  Specifically,
"need a branch prior to regaining speculative safety" isn't correct, as that holds
true if and only if "regaining speculative safety" requires executing code that
might access R16-R31.  If we massage __vmx_vcpu_run() to restore SPEC_CTRL in
assembly, same as __svm_vcpu_run(), then __{svm,vmx}_vcpu_run() can simply context
switch R16-R31 if and only if APX is enabled in XCR0.

KVM always intercepts XCR0 writes (when XCR0 isn't context switched by "harware",
i.e. ignoring SEV-ES+ and TDX guests), and IIUC all access to R16-R31 is gated on
XCR0.APX=1.  So unless I'm missing something (or hardware is flawed and lets the
guest speculative consume R16-R31, which would be sad), it's perfectly safe to
run the guest with host state in R16-R31.

That would avoid pointlessly context switching 16 registers when APX is not being
used by the guest, and would avoid having to write XCR0 in the fastpath.

> diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h
> index 959fcc01ee0f..9a1766037b6f 100644

...

> diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
> index 0757b93e528d..69abfdd946dd 100644

Even _if_ we want to play XCR0 games, tracking early_xcr0 is unnecessary.  This
can be:

	/*
	 * XCR0 is context switched around VM-Enter/VM-Exit if APX is enabled
	 * in the host but not in the guest.
	 */
	if (vcpu->arch.xcr0 != kvm_host.xcr0 &&
	    (!cpu_feature_enabled(X86_FEATURE_APX) ||
	     vcpu->arch.xcr0 & XFEATURE_MASK_APX))
		xsetbv(XCR_XFEATURE_ENABLED_MASK,
		       load_guest ? vcpu->arch.xcr0 : kvm_host.xcr0);

And then __kvm_load_guest_apx()

	<context switch R16-R31>

	if (cpu_feature_enabled(X86_FEATURE_APX) &&
	    !(vcpu->arch.xcr0 & & XFEATURE_MASK_APX))
		xsetbv(XCR_XFEATURE_ENABLED_MASK, vcpu->arch.xcr0);

And __kvm_save_guest_apx() would reverse the order of __kvm_load_guest_apx().

> @@ -11056,6 +11061,49 @@ static void kvm_vcpu_reload_apic_access_page(struct kvm_vcpu *vcpu)
>  	kvm_x86_call(set_apic_access_page_addr)(vcpu);

This is wrong.  The "real" xcr0 needs to be loaded *after* accessing R16+.

> +	if (!(vcpu->arch.xcr0 & XFEATURE_MASK_APX))
> +		return;

---

## [30] Sean Christopherson — 2026-04-06
*Subject: Re: [PATCH 0/7] KVM: x86: APX reg prep work*

On Fri, Apr 03, 2026, Dave Hansen wrote:
> On 4/2/26 16:19, Sean Christopherson wrote:
> > Do we know what the compiler and/or kernel rules for using R16-R31 will be?

Ooof, one nasty wrinkle to prepare for is an NMI that arrives after VM-Exit on
Intel CPUs.  Unless Intel extends VMX to context switch XCR0 at VM-Entry/VM-Exit,
and/or provides GIF-like functionality (which would be awesome!), it will be
possible for an NMI to be taken with the guest's XCR0 loaded, i.e. with XCR0.APX=0
even when APX is fully enabled in the host.

> I'm not sure I want to be messing with XSAVE there. XSAVE requires
> munging a header which means even if we used XSAVE we'd need to XSAVE

---

## [31] Paolo Bonzini — 2026-04-06
*Subject: Re: [PATCH 0/7] KVM: x86: APX reg prep work*

Il lun 6 apr 2026, 17:28 Sean Christopherson <seanjc@google.com> ha scritto:
> > You're right about fast paths...
>

I might even have patches for that lying around (the SPEC_CTRL part).

> KVM always intercepts XCR0 writes (when XCR0 isn't context switched by "hardware",
> i.e. ignoring SEV-ES+ and TDX guests), and IIUC all access to R16-R31 is gated on

Right, fortunately.

> .  So unless I'm missing something (or hardware is flawed and lets the
> guest speculative consume R16-R31, which would be sad), it's perfectly safe to

For now yes, but once/if the kernel starts using the registers there's
no way out of writing XCR0 for APX-disabled guests in the fast path.

If we ignore that, we can keep guest XCR0 all the time for now, and
that would be:
- move SPEC_CTRL to assembly
- not changing XCR0 handling at all
- use XCR0 in addition to just static_cpu_has(X86_FEATURE_APX) to make
r16-r31 swap conditional

> > -     if (vcpu->arch.xcr0 != kvm_host.xcr0)
> > +     /*

(which depends on whether we want to be ready for kernel usage of APX, right?)

> tracking early_xcr0 is unnecessary.  This can be:
>

This is a bit more complex however, because in the end early_xcr0 is
precomputing the same conditions and optimizations. For example...

> > +void __kvm_load_guest_apx(struct kvm_vcpu *vcpu)
> > +{

... this is actually the same optimization you mention above: the real
xcr0 only needs to be loaded if APX is off in the guest, and in that
case you don't need to load r16-r31. So you can load xcr0 first, and
then any components (for now only APX) that need to be swapped.

> > +     if (!(vcpu->arch.xcr0 & XFEATURE_MASK_APX))
> > +             return;

... Because the loads are conditional on APX being enabled in the real xcr0.

Paolo

> > +
> > +     WARN_ON_ONCE(!irqs_disabled());

---

## [32] Sean Christopherson — 2026-04-06
*Subject: Re: [PATCH 0/7] KVM: x86: APX reg prep work*

On Mon, Apr 06, 2026, Paolo Bonzini wrote:
> Il lun 6 apr 2026, 17:28 Sean Christopherson <seanjc@google.com> ha scritto:
> > > You're right about fast paths...

Why's that?  So long as KVM uses vcpu->arch.regs[R16-R31] as the source of truth
when emulating anything, there's no danger of taking a #UD in the host due to
accessing R16-R31 with XCR0.APX=0.  There's not even any danger of consuming stale
guest state, e.g. in case KVM screws up accesses R16-R31 instead of generating #UD,
as the value in regs[] will still be the guest's last written value.

If we wanted be paranoid, we could add sanity checks to ensure R16-R31 don't show
up in hardware-provided informational fields, but to some extent that's orthogonal
to how KVM maintains guest values.

> If we ignore that, we can keep guest XCR0 all the time for now, and
> that would be:

No?

---

## [33] Paolo Bonzini — 2026-04-07
*Subject: Re: [PATCH 0/7] KVM: x86: APX reg prep work*

Il mar 7 apr 2026, 00:00 Sean Christopherson <seanjc@google.com> ha scritto:
>
> > > .  So unless I'm missing something (or hardware is flawed and lets the

Yes I agree with that. But the unavoidable part is the XSETBV because
only the assembly code can run with XCR0.APX=0. As soon as you go back
to C, including during the fast path, you have to ensure XCR0.APX=1
again if the kernel is compiled with -mapxf.

For now, I agree that early_xcr0 isn't needed and you can run all the
time with XCR0.APX=0.

Paolo

---

## [34] Sean Christopherson — 2026-04-07
*Subject: Re: [PATCH 0/7] KVM: x86: APX reg prep work*

On Tue, Apr 07, 2026, Paolo Bonzini wrote:
> Il mar 7 apr 2026, 00:00 Sean Christopherson <seanjc@google.com> ha scritto:
> >

/facepalm

I got so focused on register state that I completely forgot about actually
using the registers...

---
