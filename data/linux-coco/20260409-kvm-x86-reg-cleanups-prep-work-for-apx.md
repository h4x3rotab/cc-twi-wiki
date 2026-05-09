---
title: 'KVM: x86: Reg cleanups / prep work for APX'
date: 2026-04-09
last_reply: 2026-04-15
message_count: 26
participants: ['Sean Christopherson', 'Chang S. Bae', 'Huang, Kai', 'Xiaoyao Li']
---

## [1] Sean Christopherson — 2026-04-09

Clean up KVM's register tracking and storage, primarily to prepare for landing
APX, which expands the maximum number of GPRs from 16 to 32.

v2:
 - Call out the RIP is effectively an "EX" reg too (in patch 2). [Paolo]
 - Rework the available/dirty APIs to have an explicit "clear" operation
   for available, and only a full "reset" for dirty. [Yosry, Paolo]

v1: https://lore.kernel.org/all/20260311003346.2626238-1-seanjc@google.com

Sean Christopherson (6):
  KVM: x86: Add dedicated storage for guest RIP
  KVM: x86: Drop the "EX" part of "EXREG" to avoid collision with APX
  KVM: nVMX: Do a bitwise-AND of regs_avail when switching active VMCS
  KVM: x86: Add wrapper APIs to reset dirty/available register masks
  KVM: x86: Track available/dirty register masks as "unsigned long"
    values
  KVM: x86: Use a proper bitmap for tracking available/dirty registers

 arch/x86/include/asm/kvm_host.h | 32 +++++++++--------
 arch/x86/kvm/kvm_cache_regs.h   | 62 +++++++++++++++++++++++----------
 arch/x86/kvm/svm/sev.c          |  2 +-
 arch/x86/kvm/svm/svm.c          | 16 ++++-----
 arch/x86/kvm/svm/svm.h          |  2 +-
 arch/x86/kvm/vmx/nested.c       | 10 +++---
 arch/x86/kvm/vmx/tdx.c          | 36 +++++++++----------
 arch/x86/kvm/vmx/vmx.c          | 52 +++++++++++++--------------
 arch/x86/kvm/vmx/vmx.h          | 24 ++++++-------
 arch/x86/kvm/x86.c              | 20 +++++------
 10 files changed, 143 insertions(+), 113 deletions(-)


base-commit: b89df297a47e641581ee67793592e5c6ae0428f4

---

## [2] Sean Christopherson — 2026-04-09
*Subject: [PATCH v2 1/6] KVM: x86: Add dedicated storage for guest RIP*

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
index c470e40a00aa..68a11325e8bc 100644
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
index 75d0c03d69bc..2010b157e288 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -967,7 +967,7 @@ static int sev_es_sync_vmsa(struct vcpu_svm *svm)
 	save->r14 = svm->vcpu.arch.regs[VCPU_REGS_R14];
 	save->r15 = svm->vcpu.arch.regs[VCPU_REGS_R15];
 #endif
-	save->rip = svm->vcpu.arch.regs[VCPU_REGS_RIP];
+	save->rip = svm->vcpu.arch.rip;
 
 	/* Sync some non-GPR registers before encrypting */
 	save->xcr0 = svm->vcpu.arch.xcr0;
diff --git a/arch/x86/kvm/svm/svm.c b/arch/x86/kvm/svm/svm.c
index e7fdd7a9c280..85edaee27b03 100644
--- a/arch/x86/kvm/svm/svm.c
+++ b/arch/x86/kvm/svm/svm.c
@@ -4420,7 +4420,7 @@ static __no_kcsan fastpath_t svm_vcpu_run(struct kvm_vcpu *vcpu, u64 run_flags)
 
 	svm->vmcb->save.rax = vcpu->arch.regs[VCPU_REGS_RAX];
 	svm->vmcb->save.rsp = vcpu->arch.regs[VCPU_REGS_RSP];
-	svm->vmcb->save.rip = vcpu->arch.regs[VCPU_REGS_RIP];
+	svm->vmcb->save.rip = vcpu->arch.rip;
 
 	/*
 	 * Disable singlestep if we're injecting an interrupt/exception.
@@ -4506,7 +4506,7 @@ static __no_kcsan fastpath_t svm_vcpu_run(struct kvm_vcpu *vcpu, u64 run_flags)
 		vcpu->arch.cr2 = svm->vmcb->save.cr2;
 		vcpu->arch.regs[VCPU_REGS_RAX] = svm->vmcb->save.rax;
 		vcpu->arch.regs[VCPU_REGS_RSP] = svm->vmcb->save.rsp;
-		vcpu->arch.regs[VCPU_REGS_RIP] = svm->vmcb->save.rip;
+		vcpu->arch.rip = svm->vmcb->save.rip;
 	}
 	vcpu->arch.regs_dirty = 0;
 
@@ -4946,7 +4946,7 @@ static int svm_enter_smm(struct kvm_vcpu *vcpu, union kvm_smram *smram)
 
 	svm->vmcb->save.rax = vcpu->arch.regs[VCPU_REGS_RAX];
 	svm->vmcb->save.rsp = vcpu->arch.regs[VCPU_REGS_RSP];
-	svm->vmcb->save.rip = vcpu->arch.regs[VCPU_REGS_RIP];
+	svm->vmcb->save.rip = vcpu->arch.rip;
 
 	nested_svm_simple_vmexit(svm, SVM_EXIT_SW);
 
diff --git a/arch/x86/kvm/vmx/vmx.c b/arch/x86/kvm/vmx/vmx.c
index a29896a9ef14..577b0c6286ad 100644
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
index db84e8001da5..d0cc5f6c6879 100644
--- a/arch/x86/kvm/vmx/vmx.h
+++ b/arch/x86/kvm/vmx/vmx.h
@@ -620,7 +620,7 @@ BUILD_CONTROLS_SHADOW(tertiary_exec, TERTIARY_VM_EXEC_CONTROL, 64)
  * cache on demand.  Other registers not listed here are synced to
  * the cache immediately after VM-Exit.
  */
-#define VMX_REGS_LAZY_LOAD_SET	((1 << VCPU_REGS_RIP) |         \
+#define VMX_REGS_LAZY_LOAD_SET	((1 << VCPU_REG_RIP) |         \
 				(1 << VCPU_REGS_RSP) |          \
 				(1 << VCPU_EXREG_RFLAGS) |      \
 				(1 << VCPU_EXREG_PDPTR) |       \

---

## [3] Sean Christopherson — 2026-04-09
*Subject: [PATCH v2 2/6] KVM: x86: Drop the "EX" part of "EXREG" to avoid
 collision with APX*

Now that NR_VCPU_REGS is no longer a thing, and now that now that RIP is
effectively an EXREG, drop the "EX" is for extended (or maybe extra?")
prefix from non-GPR registers to avoid a collision with APX (Advanced
Performance Extensions), which adds:

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
index 68a11325e8bc..b1eae1e7b04f 100644
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
index 85edaee27b03..ee5749d8b3e8 100644
--- a/arch/x86/kvm/svm/svm.c
+++ b/arch/x86/kvm/svm/svm.c
@@ -1517,7 +1517,7 @@ static void svm_cache_reg(struct kvm_vcpu *vcpu, enum kvm_reg reg)
 	kvm_register_mark_available(vcpu, reg);
 
 	switch (reg) {
-	case VCPU_EXREG_PDPTR:
+	case VCPU_REG_PDPTR:
 		/*
 		 * When !npt_enabled, mmu->pdptrs[] is already available since
 		 * it is always updated per SDM when moving to CRs.
@@ -4179,7 +4179,7 @@ static void svm_flush_tlb_gva(struct kvm_vcpu *vcpu, gva_t gva)
 
 static void svm_flush_tlb_guest(struct kvm_vcpu *vcpu)
 {
-	kvm_register_mark_dirty(vcpu, VCPU_EXREG_ERAPS);
+	kvm_register_mark_dirty(vcpu, VCPU_REG_ERAPS);
 
 	svm_flush_tlb_asid(vcpu);
 }
@@ -4457,7 +4457,7 @@ static __no_kcsan fastpath_t svm_vcpu_run(struct kvm_vcpu *vcpu, u64 run_flags)
 	svm->vmcb->save.cr2 = vcpu->arch.cr2;
 
 	if (guest_cpu_cap_has(vcpu, X86_FEATURE_ERAPS) &&
-	    kvm_register_is_dirty(vcpu, VCPU_EXREG_ERAPS))
+	    kvm_register_is_dirty(vcpu, VCPU_REG_ERAPS))
 		svm->vmcb->control.erap_ctl |= ERAP_CONTROL_CLEAR_RAP;
 
 	svm_fixup_nested_rips(vcpu);
diff --git a/arch/x86/kvm/svm/svm.h b/arch/x86/kvm/svm/svm.h
index fd0652b32c81..677d268ae9c7 100644
--- a/arch/x86/kvm/svm/svm.h
+++ b/arch/x86/kvm/svm/svm.h
@@ -474,7 +474,7 @@ static inline bool svm_is_vmrun_failure(u64 exit_code)
  * KVM_REQ_LOAD_MMU_PGD is always requested when the cached vcpu->arch.cr3
  * is changed.  svm_load_mmu_pgd() then syncs the new CR3 value into the VMCB.
  */
-#define SVM_REGS_LAZY_LOAD_SET	(1 << VCPU_EXREG_PDPTR)
+#define SVM_REGS_LAZY_LOAD_SET	(1 << VCPU_REG_PDPTR)
 
 static inline void __vmcb_set_intercept(unsigned long *intercepts, u32 bit)
 {
diff --git a/arch/x86/kvm/vmx/nested.c b/arch/x86/kvm/vmx/nested.c
index 3fe88f29be7a..22b1f06a9d40 100644
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
index 577b0c6286ad..aa1c26018439 100644
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
index d0cc5f6c6879..9fb76ea48caf 100644
--- a/arch/x86/kvm/vmx/vmx.h
+++ b/arch/x86/kvm/vmx/vmx.h
@@ -317,7 +317,7 @@ static __always_inline unsigned long vmx_get_exit_qual(struct kvm_vcpu *vcpu)
 {
 	struct vcpu_vt *vt = to_vt(vcpu);
 
-	if (!kvm_register_test_and_mark_available(vcpu, VCPU_EXREG_EXIT_INFO_1) &&
+	if (!kvm_register_test_and_mark_available(vcpu, VCPU_REG_EXIT_INFO_1) &&
 	    !WARN_ON_ONCE(is_td_vcpu(vcpu)))
 		vt->exit_qualification = vmcs_readl(EXIT_QUALIFICATION);
 
@@ -328,7 +328,7 @@ static __always_inline u32 vmx_get_intr_info(struct kvm_vcpu *vcpu)
 {
 	struct vcpu_vt *vt = to_vt(vcpu);
 
-	if (!kvm_register_test_and_mark_available(vcpu, VCPU_EXREG_EXIT_INFO_2) &&
+	if (!kvm_register_test_and_mark_available(vcpu, VCPU_REG_EXIT_INFO_2) &&
 	    !WARN_ON_ONCE(is_td_vcpu(vcpu)))
 		vt->exit_intr_info = vmcs_read32(VM_EXIT_INTR_INFO);
 
@@ -622,14 +622,14 @@ BUILD_CONTROLS_SHADOW(tertiary_exec, TERTIARY_VM_EXEC_CONTROL, 64)
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
index 0a1b63c63d1a..ac05cc289b56 100644
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
@@ -12473,7 +12473,7 @@ static int __set_sregs_common(struct kvm_vcpu *vcpu, struct kvm_sregs *sregs,
 	vcpu->arch.cr2 = sregs->cr2;
 	*mmu_reset_needed |= kvm_read_cr3(vcpu) != sregs->cr3;
 	vcpu->arch.cr3 = sregs->cr3;
-	kvm_register_mark_dirty(vcpu, VCPU_EXREG_CR3);
+	kvm_register_mark_dirty(vcpu, VCPU_REG_CR3);
 	kvm_x86_call(post_set_cr3)(vcpu, sregs->cr3);
 
 	kvm_set_cr8(vcpu, sregs->cr8);
@@ -12566,7 +12566,7 @@ static int __set_sregs2(struct kvm_vcpu *vcpu, struct kvm_sregs2 *sregs2)
 		for (i = 0; i < 4 ; i++)
 			kvm_pdptr_write(vcpu, i, sregs2->pdptrs[i]);
 
-		kvm_register_mark_dirty(vcpu, VCPU_EXREG_PDPTR);
+		kvm_register_mark_dirty(vcpu, VCPU_REG_PDPTR);
 		mmu_reset_needed = 1;
 		vcpu->arch.pdptrs_from_userspace = true;
 	}
@@ -13111,7 +13111,7 @@ void kvm_vcpu_reset(struct kvm_vcpu *vcpu, bool init_event)
 	kvm_rip_write(vcpu, 0xfff0);
 
 	vcpu->arch.cr3 = 0;
-	kvm_register_mark_dirty(vcpu, VCPU_EXREG_CR3);
+	kvm_register_mark_dirty(vcpu, VCPU_REG_CR3);
 
 	/*
 	 * CR0.CD/NW are set on RESET, preserved on INIT.  Note, some versions
@@ -14323,7 +14323,7 @@ int kvm_handle_invpcid(struct kvm_vcpu *vcpu, unsigned long type, gva_t gva)
 		 * the RAP (Return Address Predicator).
 		 */
 		if (guest_cpu_cap_has(vcpu, X86_FEATURE_ERAPS))
-			kvm_register_is_dirty(vcpu, VCPU_EXREG_ERAPS);
+			kvm_register_is_dirty(vcpu, VCPU_REG_ERAPS);
 
 		kvm_invalidate_pcid(vcpu, operand.pcid);
 		return kvm_skip_emulated_instruction(vcpu);
@@ -14339,7 +14339,7 @@ int kvm_handle_invpcid(struct kvm_vcpu *vcpu, unsigned long type, gva_t gva)
 		fallthrough;
 	case INVPCID_TYPE_ALL_INCL_GLOBAL:
 		/*
-		 * Don't bother marking VCPU_EXREG_ERAPS dirty, SVM will take
+		 * Don't bother marking VCPU_REG_ERAPS dirty, SVM will take
 		 * care of doing so when emulating the full guest TLB flush
 		 * (the RAP is cleared on all implicit TLB flushes).
 		 */

---

## [4] Sean Christopherson — 2026-04-09
*Subject: [PATCH v2 3/6] KVM: nVMX: Do a bitwise-AND of regs_avail when
 switching active VMCS*

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
index 22b1f06a9d40..63c4ca8c97d5 100644
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

## [5] Sean Christopherson — 2026-04-09
*Subject: [PATCH v2 4/6] KVM: x86: Add wrapper APIs to reset dirty/available
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
 arch/x86/kvm/kvm_cache_regs.h | 18 ++++++++++++++++++
 arch/x86/kvm/svm/svm.c        |  4 ++--
 arch/x86/kvm/vmx/nested.c     |  4 ++--
 arch/x86/kvm/vmx/tdx.c        |  2 +-
 arch/x86/kvm/vmx/vmx.c        |  4 ++--
 5 files changed, 25 insertions(+), 7 deletions(-)

diff --git a/arch/x86/kvm/kvm_cache_regs.h b/arch/x86/kvm/kvm_cache_regs.h
index ac1f9867a234..7f71d468178c 100644
--- a/arch/x86/kvm/kvm_cache_regs.h
+++ b/arch/x86/kvm/kvm_cache_regs.h
@@ -105,6 +105,24 @@ static __always_inline bool kvm_register_test_and_mark_available(struct kvm_vcpu
 	return arch___test_and_set_bit(reg, (unsigned long *)&vcpu->arch.regs_avail);
 }
 
+static __always_inline void kvm_clear_available_registers(struct kvm_vcpu *vcpu,
+							  u32 clear_mask)
+{
+	/*
+	 * Note the bitwise-AND!  In practice, a straight write would also work
+	 * as KVM initializes the mask to all ones and never clears registers
+	 * that are eagerly synchronized.  Using a bitwise-AND adds a bit of
+	 * sanity checking as incorrectly marking an eagerly sync'd register
+	 * unavailable will generate a WARN due to an unexpected cache request.
+	 */
+	vcpu->arch.regs_avail &= ~clear_mask;
+}
+
+static __always_inline void kvm_reset_dirty_registers(struct kvm_vcpu *vcpu)
+{
+	vcpu->arch.regs_dirty = 0;
+}
+
 /*
  * The "raw" register helpers are only for cases where the full 64 bits of a
  * register are read/written irrespective of current vCPU mode.  In other words,
diff --git a/arch/x86/kvm/svm/svm.c b/arch/x86/kvm/svm/svm.c
index ee5749d8b3e8..2b73d2650155 100644
--- a/arch/x86/kvm/svm/svm.c
+++ b/arch/x86/kvm/svm/svm.c
@@ -4508,7 +4508,7 @@ static __no_kcsan fastpath_t svm_vcpu_run(struct kvm_vcpu *vcpu, u64 run_flags)
 		vcpu->arch.regs[VCPU_REGS_RSP] = svm->vmcb->save.rsp;
 		vcpu->arch.rip = svm->vmcb->save.rip;
 	}
-	vcpu->arch.regs_dirty = 0;
+	kvm_reset_dirty_registers(vcpu);
 
 	if (unlikely(svm->vmcb->control.exit_code == SVM_EXIT_NMI))
 		kvm_before_interrupt(vcpu, KVM_HANDLING_NMI);
@@ -4554,7 +4554,7 @@ static __no_kcsan fastpath_t svm_vcpu_run(struct kvm_vcpu *vcpu, u64 run_flags)
 		vcpu->arch.apf.host_apf_flags =
 			kvm_read_and_reset_apf_flags();
 
-	vcpu->arch.regs_avail &= ~SVM_REGS_LAZY_LOAD_SET;
+	kvm_clear_available_registers(vcpu, SVM_REGS_LAZY_LOAD_SET);
 
 	if (!msr_write_intercepted(vcpu, MSR_AMD64_PERF_CNTR_GLOBAL_CTL))
 		rdmsrq(MSR_AMD64_PERF_CNTR_GLOBAL_CTL, vcpu_to_pmu(vcpu)->global_ctrl);
diff --git a/arch/x86/kvm/vmx/nested.c b/arch/x86/kvm/vmx/nested.c
index 63c4ca8c97d5..c4d2bc080add 100644
--- a/arch/x86/kvm/vmx/nested.c
+++ b/arch/x86/kvm/vmx/nested.c
@@ -310,13 +310,13 @@ static void vmx_switch_vmcs(struct kvm_vcpu *vcpu, struct loaded_vmcs *vmcs)
 	vmx_sync_vmcs_host_state(vmx, prev);
 	put_cpu();
 
-	vcpu->arch.regs_avail &= ~VMX_REGS_LAZY_LOAD_SET;
+	kvm_clear_available_registers(vcpu, VMX_REGS_LAZY_LOAD_SET);
 
 	/*
 	 * All lazily updated registers will be reloaded from VMCS12 on both
 	 * vmentry and vmexit.
 	 */
-	vcpu->arch.regs_dirty = 0;
+	kvm_reset_dirty_registers(vcpu);
 }
 
 static void nested_put_vmcs12_pages(struct kvm_vcpu *vcpu)
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index c23ec4ac8bc8..c9ab7902151f 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1098,7 +1098,7 @@ fastpath_t tdx_vcpu_run(struct kvm_vcpu *vcpu, u64 run_flags)
 
 	tdx_load_host_xsave_state(vcpu);
 
-	vcpu->arch.regs_avail &= TDX_REGS_AVAIL_SET;
+	kvm_clear_available_registers(vcpu, ~(u32)TDX_REGS_AVAIL_SET);
 
 	if (unlikely(tdx->vp_enter_ret == EXIT_REASON_EPT_MISCONFIG))
 		return EXIT_FASTPATH_NONE;
diff --git a/arch/x86/kvm/vmx/vmx.c b/arch/x86/kvm/vmx/vmx.c
index aa1c26018439..61eeafcd70f1 100644
--- a/arch/x86/kvm/vmx/vmx.c
+++ b/arch/x86/kvm/vmx/vmx.c
@@ -7472,7 +7472,7 @@ static noinstr void vmx_vcpu_enter_exit(struct kvm_vcpu *vcpu,
 				   flags);
 
 	vcpu->arch.cr2 = native_read_cr2();
-	vcpu->arch.regs_avail &= ~VMX_REGS_LAZY_LOAD_SET;
+	kvm_clear_available_registers(vcpu, VMX_REGS_LAZY_LOAD_SET);
 
 	vmx->idt_vectoring_info = 0;
 
@@ -7538,7 +7538,7 @@ fastpath_t vmx_vcpu_run(struct kvm_vcpu *vcpu, u64 run_flags)
 		vmcs_writel(GUEST_RSP, vcpu->arch.regs[VCPU_REGS_RSP]);
 	if (kvm_register_is_dirty(vcpu, VCPU_REG_RIP))
 		vmcs_writel(GUEST_RIP, vcpu->arch.rip);
-	vcpu->arch.regs_dirty = 0;
+	kvm_reset_dirty_registers(vcpu);
 
 	if (run_flags & KVM_RUN_LOAD_GUEST_DR6)
 		set_debugreg(vcpu->arch.dr6, 6);

---

## [6] Sean Christopherson — 2026-04-09
*Subject: [PATCH v2 5/6] KVM: x86: Track available/dirty register masks as
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
 arch/x86/kvm/kvm_cache_regs.h   |  2 +-
 arch/x86/kvm/svm/svm.h          |  2 +-
 arch/x86/kvm/vmx/tdx.c          | 36 ++++++++++++++++-----------------
 arch/x86/kvm/vmx/vmx.h          | 20 +++++++++---------
 5 files changed, 32 insertions(+), 32 deletions(-)

diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h
index b1eae1e7b04f..c47eb294c066 100644
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
index 7f71d468178c..171e6bc2e169 100644
--- a/arch/x86/kvm/kvm_cache_regs.h
+++ b/arch/x86/kvm/kvm_cache_regs.h
@@ -106,7 +106,7 @@ static __always_inline bool kvm_register_test_and_mark_available(struct kvm_vcpu
 }
 
 static __always_inline void kvm_clear_available_registers(struct kvm_vcpu *vcpu,
-							  u32 clear_mask)
+							  unsigned long clear_mask)
 {
 	/*
 	 * Note the bitwise-AND!  In practice, a straight write would also work
diff --git a/arch/x86/kvm/svm/svm.h b/arch/x86/kvm/svm/svm.h
index 677d268ae9c7..7b46a3f13de1 100644
--- a/arch/x86/kvm/svm/svm.h
+++ b/arch/x86/kvm/svm/svm.h
@@ -474,7 +474,7 @@ static inline bool svm_is_vmrun_failure(u64 exit_code)
  * KVM_REQ_LOAD_MMU_PGD is always requested when the cached vcpu->arch.cr3
  * is changed.  svm_load_mmu_pgd() then syncs the new CR3 value into the VMCB.
  */
-#define SVM_REGS_LAZY_LOAD_SET	(1 << VCPU_REG_PDPTR)
+#define SVM_REGS_LAZY_LOAD_SET	(BIT(VCPU_REG_PDPTR))
 
 static inline void __vmcb_set_intercept(unsigned long *intercepts, u32 bit)
 {
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index c9ab7902151f..85f28363e4cc 100644
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
@@ -1098,7 +1098,7 @@ fastpath_t tdx_vcpu_run(struct kvm_vcpu *vcpu, u64 run_flags)
 
 	tdx_load_host_xsave_state(vcpu);
 
-	kvm_clear_available_registers(vcpu, ~(u32)TDX_REGS_AVAIL_SET);
+	kvm_clear_available_registers(vcpu, ~TDX_REGS_AVAIL_SET);
 
 	if (unlikely(tdx->vp_enter_ret == EXIT_REASON_EPT_MISCONFIG))
 		return EXIT_FASTPATH_NONE;
diff --git a/arch/x86/kvm/vmx/vmx.h b/arch/x86/kvm/vmx/vmx.h
index 9fb76ea48caf..48447fa983f4 100644
--- a/arch/x86/kvm/vmx/vmx.h
+++ b/arch/x86/kvm/vmx/vmx.h
@@ -620,16 +620,16 @@ BUILD_CONTROLS_SHADOW(tertiary_exec, TERTIARY_VM_EXEC_CONTROL, 64)
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

## [7] Sean Christopherson — 2026-04-09
*Subject: [PATCH v2 6/6] KVM: x86: Use a proper bitmap for tracking
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
 arch/x86/kvm/kvm_cache_regs.h   | 20 ++++++++++++--------
 arch/x86/kvm/x86.c              |  4 ++--
 3 files changed, 18 insertions(+), 12 deletions(-)

diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h
index c47eb294c066..ef0c368676c5 100644
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
index 171e6bc2e169..2ae492ad6412 100644
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
 
 static __always_inline void kvm_clear_available_registers(struct kvm_vcpu *vcpu,
 							  unsigned long clear_mask)
 {
+	BUILD_BUG_ON(sizeof(clear_mask) != sizeof(vcpu->arch.regs_avail[0]));
+	BUILD_BUG_ON(ARRAY_SIZE(vcpu->arch.regs_avail) != 1);
+
 	/*
 	 * Note the bitwise-AND!  In practice, a straight write would also work
 	 * as KVM initializes the mask to all ones and never clears registers
@@ -115,12 +118,13 @@ static __always_inline void kvm_clear_available_registers(struct kvm_vcpu *vcpu,
 	 * sanity checking as incorrectly marking an eagerly sync'd register
 	 * unavailable will generate a WARN due to an unexpected cache request.
 	 */
-	vcpu->arch.regs_avail &= ~clear_mask;
+	vcpu->arch.regs_avail[0] &= ~clear_mask;
 }
 
 static __always_inline void kvm_reset_dirty_registers(struct kvm_vcpu *vcpu)
 {
-	vcpu->arch.regs_dirty = 0;
+	BUILD_BUG_ON(ARRAY_SIZE(vcpu->arch.regs_dirty) != 1);
+	vcpu->arch.regs_dirty[0] = 0;
 }
 
 /*
diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index ac05cc289b56..b8a91feec8e1 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -12836,8 +12836,8 @@ int kvm_arch_vcpu_create(struct kvm_vcpu *vcpu)
 	int r;
 
 	vcpu->arch.last_vmentry_cpu = -1;
-	vcpu->arch.regs_avail = ~0;
-	vcpu->arch.regs_dirty = ~0;
+	bitmap_fill(vcpu->arch.regs_avail, NR_VCPU_TOTAL_REGS);
+	bitmap_fill(vcpu->arch.regs_dirty, NR_VCPU_TOTAL_REGS);
 
 	kvm_gpc_init(&vcpu->arch.pv_time, vcpu->kvm);

---

## [8] Chang S. Bae — 2026-04-10
*Subject: Re: [PATCH v2 1/6] KVM: x86: Add dedicated storage for guest RIP*

On 4/9/2026 3:42 PM, Sean Christopherson wrote:
> Add kvm_vcpu_arch.rip to track guest RIP instead of including it in the
> generic regs[] array.  Decoupling RIP from regs[] will allow using a

Digging the history, this effectively reverts part of changes in

   commit 5fdbf9765b7b ("KVM: x86: accessors for guest registers")

which had

-       unsigned long regs[NR_VCPU_REGS];
-       unsigned long rip;      /* needs vcpu_load_rsp_rip() */
+       /*
+        * rip and regs accesses must go through
+        * kvm_{register,rip}_{read,write} functions.
+        */
+       unsigned long regs[NR_VCPU_REGS];

But its changelog didn't go into much detail about this change. I could 
only relate to vcpu_load_rsp_rip() which might establish perception 
coupling RSP with RIP back then.

In any case, it doesn't matter. I think this patch makes a clear 
improvement - for example, now aligns with _regs[NR_EMULATOR_GPRS] in 
struct x86_emulate_ctxt for general consistency.

Indeed, this and the whole series paves the way for APX. Appreciate for 
the time and effort!

Reviewed-by: Chang S. Bae <chang.seok.bae@intel.com>

---

## [9] Huang, Kai — 2026-04-13
*Subject: Re: [PATCH v2 2/6] KVM: x86: Drop the "EX" part of "EXREG" to avoid
 collision with APX*

On Thu, 2026-04-09 at 15:42 -0700, Sean Christopherson wrote:
> Now that NR_VCPU_REGS is no longer a thing, and now that now that RIP is

Nit: double "now that".

---

## [10] Huang, Kai — 2026-04-13
*Subject: Re: [PATCH v2 5/6] KVM: x86: Track available/dirty register masks as
 "unsigned long" values*

On Thu, 2026-04-09 at 15:42 -0700, Sean Christopherson wrote:
> Convert regs_{avail,dirty} and all related masks to "unsigned long" values
> as an intermediate step towards declaring the fields as actual bitmaps, and

Nit: a step toward supporting APX.

---

## [11] Huang, Kai — 2026-04-13
*Subject: Re: [PATCH v2 5/6] KVM: x86: Track available/dirty register masks as
 "unsigned long" values*

On Thu, 2026-04-09 at 15:42 -0700, Sean Christopherson wrote:
> -#define TDX_REGS_AVAIL_SET	(BIT_ULL(VCPU_REG_EXIT_INFO_1) | \
> -				 BIT_ULL(VCPU_REG_EXIT_INFO_2) | \

Not related to this series, but this made me look into whether these
registers are truly needed to be set as available for TDX.

Firstly, all the listed registers are marked as available immediately after
exiting from tdh_vp_enter(), but except VCPU_REG_EXIT_INFO_1 and
VCPU_REG_EXIT_INFO_2 are immediately saved to the common 'struct vcpu_vt',
all other GPRs are not saved to vcpu->arch.regs[], which means marking GPRs
available immediately doesn't quite make sense.

In fact, IIUC other than when the TD exits with TDVMCALL on which TD shares
couple of GPRs with KVM, KVM has no way to get TD's GPRs.  So perhaps it
makes more sense is to mark the shared GPRs available upon TDVMCALL.

But even that does not make sense from KVM's "GPR available" perspective,
because TDVMCALL has a different ABI from KVM's existing infrastructure for
e.g., CPUID/MSR emulation.  E.g.,  KVM uses RCX/RAX/RDX for MSR emulation,
but TDVMCALL<MSR.WRITE> uses R12 and R13 to convey MSR index/value:

        case EXIT_REASON_MSR_WRITE:                 
                kvm_rcx_write(vcpu, tdx->vp_enter_args.r12);         
                kvm_rax_write(vcpu, tdx->vp_enter_args.r13 & -1u);   
                kvm_rdx_write(vcpu, tdx->vp_enter_args.r13 >> 32);

So I think the most accurate way is to explicitly mark the relevant GPRs
available for each type of TDVMCALL. I am not sure whether it's worth to do
though, because AFAICT there's no real bug in the existing code, other than
"marking GPRs not in vcpu->arch.regs[] as available looks wrong".

A less invasive way is to mark all possible GPRs that can be used in
TDVMCALL emulation available once after TD exits.  AFAICT the KVM hypercall
uses most GPRs (RAX/RBX/RCX/RDX/RSI) and all other TDVMCALLs only use a
subset, so maybe we can remove other GPRs from the available list (the diff
in [*] passed my test of booting/destroying TD).

Bug again, not sure whether it's worth doing.

[*]:

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 85f28363e4cc..7b4c182c22cf 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1019,17 +1019,7 @@ static fastpath_t tdx_exit_handlers_fastpath(struct
kvm_vcpu *vcpu)
                                 BIT(VCPU_REGS_RBX) | \
                                 BIT(VCPU_REGS_RCX) | \
                                 BIT(VCPU_REGS_RDX) | \
-                                BIT(VCPU_REGS_RBP) | \
-                                BIT(VCPU_REGS_RSI) | \
-                                BIT(VCPU_REGS_RDI) | \
-                                BIT(VCPU_REGS_R8) | \
-                                BIT(VCPU_REGS_R9) | \
-                                BIT(VCPU_REGS_R10) | \
-                                BIT(VCPU_REGS_R11) | \
-                                BIT(VCPU_REGS_R12) | \
-                                BIT(VCPU_REGS_R13) | \
-                                BIT(VCPU_REGS_R14) | \
-                                BIT(VCPU_REGS_R15))
+                                BIT(VCPU_REGS_RSI))

---

## [12] Huang, Kai — 2026-04-13
*Subject: Re: [PATCH v2 0/6] KVM: x86: Reg cleanups / prep work for APX*

On Thu, 2026-04-09 at 15:42 -0700, Sean Christopherson wrote:
> Clean up KVM's register tracking and storage, primarily to prepare for landing
> APX, which expands the maximum number of GPRs from 16 to 32.

Tested booting/destroying both normal VMX guest and TD worked fine:

Reviewed-by: Kai Huang <kai.huang@intel.com>
Tested-by: Kai Huang <kai.huang@intel.com>

---

## [13] Sean Christopherson — 2026-04-13
*Subject: Re: [PATCH v2 5/6] KVM: x86: Track available/dirty register masks as
 "unsigned long" values*

On Mon, Apr 13, 2026, Kai Huang wrote:
> On Thu, 2026-04-09 at 15:42 -0700, Sean Christopherson wrote:
> > -#define TDX_REGS_AVAIL_SET	(BIT_ULL(VCPU_REG_EXIT_INFO_1) | \

Not worth doing.  Because VMX and SVM make all GRPs available immediately, except
for RSP, KVM ignores avail/dirty for GPRs.  I.e. "fixing" TDX will just shift the
"bugs" elsewhere.

More importantly, because the TDX-Module *requires* RCX (the GPR that holds the
mask of registers to expose to the VMM) to be hidden on TDVMCALL, KVM *can't*
do any kind of meaningful "available" tracking.  Versus sev_es_validate_vmgexit(),
which can at least sanity check that the registers needed to service a hypercall
have valid data.

So unfortunately, since we need to rely on testing to verify KVM's implementation
no matter what, I don't think it'd be a net positive to overhaul KVM's handling
of GPRs to support SEV-ES+'s and TDX's "sometimes available" GPR set.

---

## [14] Huang, Kai — 2026-04-13
*Subject: Re: [PATCH v2 5/6] KVM: x86: Track available/dirty register masks as
 "unsigned long" values*

On Mon, 2026-04-13 at 07:54 -0700, Sean Christopherson wrote:
> On Mon, Apr 13, 2026, Kai Huang wrote:
> > On Thu, 2026-04-09 at 15:42 -0700, Sean Christopherson wrote:

Fine to me. :-)

> Because VMX and SVM make all GRPs available immediately, except
> for RSP, KVM ignores avail/dirty for GPRs.  I.e. "fixing" TDX will just shift the

Just want to understand:

I thought the fix could be we simply remove the wrong GPRs from the list. 
Not sure how fixing TDX will shift bugs elsewhere?

> 
> More importantly, because the TDX-Module *requires* RCX (the GPR that holds the

Hmm I think RCX conveys the shared GPRs and VMM can read.  Per "Table 5.323:
TDH.VP.ENTER Output Operands Format #5 Definition: On TDCALL(TDG.VP.VMCALL)
Following a TD Entry":

  RCX   ...
	Bit(s) Name         Description

	31:0   PARAMS_MASK  Value as passed into TDCALL(TDG.VP.VMCALL) by
			    the guest TD: indicates which part of the guest
			    TD GPR and XMM state is passed as-is to the
VMM 
			    and back. For details, see the description of
			    TDG.VP.VMCALL in 5.5.26.

I think the problem is, as said previously, currently KVM TDX code uses
KVM's existing infrastructure to emulate MSR, KVM hypercall etc,  but
TDVMCALL has a different ABI, thus there's a mismatch here.

---

## [15] Xiaoyao Li — 2026-04-14
*Subject: Re: [PATCH v2 5/6] KVM: x86: Track available/dirty register masks as
 "unsigned long" values*

On 4/14/2026 7:03 AM, Huang, Kai wrote:
>> Because VMX and SVM make all GRPs available immediately, except
>> for RSP, KVM ignores avail/dirty for GPRs.  I.e. "fixing" TDX will just shift the

I'm curious too.

>> More importantly, because the TDX-Module*requires* RCX (the GPR that holds the
>> mask of registers to expose to the VMM) to be hidden on TDVMCALL, KVM*can't*

I once had patch for it internally.

It adds back the available check for GPRs when accessing instead of 
assuming they are always available. For normal VMX and SVM, all the GPRs 
are still always available. But for TDX, only EXIT_INFO_1 and 
EXIT_INFO_2 are always marked available, while others need to be 
explicitly set case by case.

The good thing is it makes TDX safer that KVM won't consume invalid data 
silently for TDX. But it adds additional overhead of checking the 
unnecessary register availability for VMX and SVM case.

-----------------------------&<-------------------------------------
From: Xiaoyao Li <xiaoyao.li@intel.com>
Date: Tue, 11 Mar 2025 07:13:29 -0400
Subject: [PATCH] KVM: x86: Add available check for GPRs

Since commit de3cd117ed2f ("KVM: x86: Omit caching logic for
always-available GPRs"), KVM doesn't check the availability of GPRs
except RSP and RIP when accessing them, because they are always
available.

However, it's not true when it comes to TDX. The GPRs are not available
after TD vcpu exits actually. And it relies on KVM manually sets the
GPRs value when needed, e.g.

  - setting rax, rbx, rcx, rdx, rsi, for hypercall emulation in
    tdx_emulate_tdvmall();

  - setting rax, rcx and rdx before MSR write emulation;

Add the available check of GPRs read, and WARN_ON_ONCE() when unavailable.
It can help capture the cases of undesired GPRs consumption by TDX.

Signed-off-by: Xiaoyao Li <xiaoyao.li@intel.com>
---
  arch/x86/kvm/kvm_cache_regs.h | 60 +++++++++++++++++++----------------
  arch/x86/kvm/vmx/tdx.c        | 25 +++------------
  2 files changed, 37 insertions(+), 48 deletions(-)

diff --git a/arch/x86/kvm/kvm_cache_regs.h b/arch/x86/kvm/kvm_cache_regs.h
index 8ddb01191d6f..b2fa01ee2b4b 100644
--- a/arch/x86/kvm/kvm_cache_regs.h
+++ b/arch/x86/kvm/kvm_cache_regs.h
@@ -16,34 +16,6 @@

  static_assert(!(KVM_POSSIBLE_CR0_GUEST_BITS & X86_CR0_PDPTR_BITS));

-#define BUILD_KVM_GPR_ACCESSORS(lname, uname)				      \
-static __always_inline unsigned long kvm_##lname##_read(struct kvm_vcpu 
*vcpu)\
-{									      \
-	return vcpu->arch.regs[VCPU_REGS_##uname];			      \
-}									      \
-static __always_inline void kvm_##lname##_write(struct kvm_vcpu *vcpu,	 
      \
-						unsigned long val)	      \
-{									      \
-	vcpu->arch.regs[VCPU_REGS_##uname] = val;			      \
-}
-BUILD_KVM_GPR_ACCESSORS(rax, RAX)
-BUILD_KVM_GPR_ACCESSORS(rbx, RBX)
-BUILD_KVM_GPR_ACCESSORS(rcx, RCX)
-BUILD_KVM_GPR_ACCESSORS(rdx, RDX)
-BUILD_KVM_GPR_ACCESSORS(rbp, RBP)
-BUILD_KVM_GPR_ACCESSORS(rsi, RSI)
-BUILD_KVM_GPR_ACCESSORS(rdi, RDI)
-#ifdef CONFIG_X86_64
-BUILD_KVM_GPR_ACCESSORS(r8,  R8)
-BUILD_KVM_GPR_ACCESSORS(r9,  R9)
-BUILD_KVM_GPR_ACCESSORS(r10, R10)
-BUILD_KVM_GPR_ACCESSORS(r11, R11)
-BUILD_KVM_GPR_ACCESSORS(r12, R12)
-BUILD_KVM_GPR_ACCESSORS(r13, R13)
-BUILD_KVM_GPR_ACCESSORS(r14, R14)
-BUILD_KVM_GPR_ACCESSORS(r15, R15)
-#endif
-
  /*
   * Using the register cache from interrupt context is generally not 
allowed, as
   * caching a register and marking it available/dirty can't be done 
atomically,
@@ -92,6 +64,38 @@ static inline void kvm_register_mark_dirty(struct 
kvm_vcpu *vcpu,
  	__set_bit(reg, (unsigned long *)&vcpu->arch.regs_dirty);
  }

+#define BUILD_KVM_GPR_ACCESSORS(lname, uname)				      \
+static __always_inline unsigned long kvm_##lname##_read(struct kvm_vcpu 
*vcpu)\
+{									      \
+	if (WARN_ON_ONCE(!kvm_register_is_available(vcpu, VCPU_REGS_##uname)))\
+		return 0;						      \
+									      \
+	return vcpu->arch.regs[VCPU_REGS_##uname];			      \
+}									      \
+static __always_inline void kvm_##lname##_write(struct kvm_vcpu *vcpu,	 
      \
+						unsigned long val)	      \
+{									      \
+	vcpu->arch.regs[VCPU_REGS_##uname] = val;			      \
+	kvm_register_mark_available(vcpu, VCPU_REGS_##uname);	      	      \
+}
+BUILD_KVM_GPR_ACCESSORS(rax, RAX)
+BUILD_KVM_GPR_ACCESSORS(rbx, RBX)
+BUILD_KVM_GPR_ACCESSORS(rcx, RCX)
+BUILD_KVM_GPR_ACCESSORS(rdx, RDX)
+BUILD_KVM_GPR_ACCESSORS(rbp, RBP)
+BUILD_KVM_GPR_ACCESSORS(rsi, RSI)
+BUILD_KVM_GPR_ACCESSORS(rdi, RDI)
+#ifdef CONFIG_X86_64
+BUILD_KVM_GPR_ACCESSORS(r8,  R8)
+BUILD_KVM_GPR_ACCESSORS(r9,  R9)
+BUILD_KVM_GPR_ACCESSORS(r10, R10)
+BUILD_KVM_GPR_ACCESSORS(r11, R11)
+BUILD_KVM_GPR_ACCESSORS(r12, R12)
+BUILD_KVM_GPR_ACCESSORS(r13, R13)
+BUILD_KVM_GPR_ACCESSORS(r14, R14)
+BUILD_KVM_GPR_ACCESSORS(r15, R15)
+#endif
+
  /*
   * kvm_register_test_and_mark_available() is a special snowflake that 
uses an
   * arch bitop directly to avoid the explicit instrumentation that 
comes with
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index cefe6cdd60a9..2b90a60e6f64 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -969,6 +969,9 @@ static __always_inline u32 
tdx_to_vmx_exit_reason(struct kvm_vcpu *vcpu)
  	return exit_reason;
  }

+#define TDX_REGS_AVAIL_SET	(BIT_ULL(VCPU_EXREG_EXIT_INFO_1) | \
+				 BIT_ULL(VCPU_EXREG_EXIT_INFO_2))
+
  static noinstr void tdx_vcpu_enter_exit(struct kvm_vcpu *vcpu)
  {
  	struct vcpu_tdx *tdx = to_tdx(vcpu);
@@ -985,6 +988,8 @@ static noinstr void tdx_vcpu_enter_exit(struct 
kvm_vcpu *vcpu)
  	tdx->exit_gpa = tdx->vp_enter_args.r8;
  	vt->exit_intr_info = tdx->vp_enter_args.r9;

+	vcpu->arch.regs_avail &= TDX_REGS_AVAIL_SET;
+
  	vmx_handle_nmi(vcpu);

  	guest_state_exit_irqoff();
@@ -1017,24 +1022,6 @@ static fastpath_t 
tdx_exit_handlers_fastpath(struct kvm_vcpu *vcpu)
  	return EXIT_FASTPATH_NONE;
  }

-#define TDX_REGS_AVAIL_SET	(BIT_ULL(VCPU_EXREG_EXIT_INFO_1) | \
-				 BIT_ULL(VCPU_EXREG_EXIT_INFO_2) | \
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
-
  static void tdx_load_host_xsave_state(struct kvm_vcpu *vcpu)
  {
  	struct kvm_tdx *kvm_tdx = to_kvm_tdx(vcpu->kvm);
@@ -1108,8 +1095,6 @@ fastpath_t tdx_vcpu_run(struct kvm_vcpu *vcpu, u64 
run_flags)

  	tdx_load_host_xsave_state(vcpu);

-	vcpu->arch.regs_avail &= TDX_REGS_AVAIL_SET;
-
  	if (unlikely(tdx->vp_enter_ret == EXIT_REASON_EPT_MISCONFIG))
  		return EXIT_FASTPATH_NONE;

---

## [16] Xiaoyao Li — 2026-04-14
*Subject: Re: [PATCH v2 1/6] KVM: x86: Add dedicated storage for guest RIP*

On 4/10/2026 6:42 AM, Sean Christopherson wrote:
> Add kvm_vcpu_arch.rip to track guest RIP instead of including it in the
> generic regs[] array.  Decoupling RIP from regs[] will allow using a

Even leave RIP in regs[], what is the problem by just allocating the 
index 16-31 to R16-R31 and making RIP the index 32? (I think I need go 
read the APX discussion to better understand the reason)

> Note, although RIP can used for addressing, it does NOT have an
                          ^
missing a 'be'

> architecturally defined index, and so can't be reached via flows like
> get_vmx_mem_address() where KVM "blindly" reads a general purpose register

s/RSP/RIP

> through the VMCS, i.e. needs to be cached for VMX.
> 

s/R16-R13/R16-R31

> running into weirdness where KVM's definition of "EXREG" doesn't line up
> with APX's definition of "extended reg".

---

## [17] Chang S. Bae — 2026-04-14
*Subject: Re: [PATCH v2 1/6] KVM: x86: Add dedicated storage for guest RIP*

On 4/14/2026 5:31 AM, Xiaoyao Li wrote:
> Even leave RIP in regs[], what is the problem by just allocating the 
> index 16-31 to R16-R31 and making RIP the index 32?

But why?

Even though the array isn't explicitly labeled as GPRs, that's 
effectively how it's being used, and RIP isn't part of that set.

I don't think there is any benefit of leaving it in regs[]. Instead, It 
can be stored like that simple, period.

Thanks,
Chang

---

## [18] Sean Christopherson — 2026-04-14
*Subject: Re: [PATCH v2 5/6] KVM: x86: Track available/dirty register masks as
 "unsigned long" values*

On Tue, Apr 14, 2026, Xiaoyao Li wrote:
> On 4/14/2026 7:03 AM, Huang, Kai wrote:
> > > Because VMX and SVM make all GRPs available immediately, except

What I'm saying is that, _if_ there are bugs where KVM uses a register that isn't
available, then modifying TDX's list won't actually fix anything (without more
changes), it will just change which code is technically buggy (hence all the quotes
above).

> > > More importantly, because the TDX-Module*requires* RCX (the GPR that holds the
> > > mask of registers to expose to the VMM) to be hidden on TDVMCALL, KVM*can't*

> And it relies on KVM manually sets the
> GPRs value when needed, e.g.

Sorry, but NAK.  I am strongly against adding any code to the GPR accessors/mutators
just for TDX.  It's a _lot_ of code.  From commit de3cd117ed2f ("KVM: x86: Omit
caching logic for always-available GPRs"):

    E.g. on x86_64, kvm_emulate_cpuid() is reduced from 342 to 182 bytes and
    kvm_emulate_hypercall() from 1362 to 1143, with the total size of KVM
    dropping by ~1000 bytes.  With CONFIG_RETPOLINE=y, the numbers are even
    more pronounced, e.g.: 353->182, 1418->1172 and well over 2000 bytes.

Note that updating only the "available" masks is wrong, as TDX needs to marshall
written registers back to their correct location.

In the end, the available/dirty tracking isn't about hardening against bugs, it's
about deferring expensive VMREAD and VMWRITE (and guest memory) operations until
action is required.

We could bury sanity checks behind a Kconfig of some kind, but I genuinely don't
see much value in doing so.  These emulation flows are very static (all register
usage is hardcoded), and so it's very much a "get it right once" sort of thing,
i.e. the odds of a runtime check finding a bug after initial development are
basically zero.

An alternative for TDX would be to avoid bouncing through GPRs in the first place,
e.g. by reworking __kvm_emulate_rdmsr() to not access any registers.  But I'm
probably opposed to even that, because I doubt the end result would be an overall
net positive for KVM.  We'd end up with duplicate code, harder to read common
code (because of the new abstractions), and likely without meaningfully moving
the needle in terms of finding/preventing bugs.  KVM still needs to get operands
to/from the right parameters, though only difference is that for TDX, the parameters
would be very "direct".

---

## [19] Sean Christopherson — 2026-04-14
*Subject: Re: [PATCH v2 1/6] KVM: x86: Add dedicated storage for guest RIP*

On Tue, Apr 14, 2026, Chang S. Bae wrote:
> On 4/14/2026 5:31 AM, Xiaoyao Li wrote:
> > Even leave RIP in regs[], what is the problem by just allocating the

+1.  Chang's earlier argument that RIP isn't a proper GPR swayed me over, e.g. RIP
doesn't have an architectural index.

Keeping RIP in regs[] saves one line of code in arch/x86/include/asm/kvm_host.h,
at the cost of making the code less readable (IMO) and incorrectly suggesting that
RIP can be accessed like other regs[].

---

## [20] Sean Christopherson — 2026-04-14
*Subject: Re: [PATCH v2 5/6] KVM: x86: Track available/dirty register masks as
 "unsigned long" values*

On Mon, Apr 13, 2026, Kai Huang wrote:
> On Mon, 2026-04-13 at 07:54 -0700, Sean Christopherson wrote:
> > More importantly, because the TDX-Module *requires* RCX (the GPR that holds the

The problem is that bit 1 in RCX is required to be '0'.  I.e. the guest *can't*
expose RCX to the VMM.  From the spec:

  15:0    GPR Mask Controls the transfer of GPR values:
  Bit 0:  RAX (must be 0)
  Bit 1:  RCX (must be 0)

And the code:

  api_error_type tdg_vp_vmcall(uint64_t controller_value)
  {
    api_error_type retval = TDX_OPERAND_INVALID;
    tdx_module_local_t* tdx_local_data_ptr = get_local_data();

    tdvmcall_control_t control = { .raw = controller_value };

    // Bits 0, 1 and 4 and 63:32 of RCX must be 0
    if (((control.gpr_select & (uint16_t)(BIT(0) | BIT(1) | BIT(4))) != 0) ||  <==== sadness
         (control.reserved != 0))
    {
        retval = api_error_with_operand_id(TDX_OPERAND_INVALID, OPERAND_ID_RCX);
        TDX_ERROR("Unsupported bits in GPR_SELECT field = 0x%x\n", control.gpr_select)
        goto EXIT_FAILURE;
    }

Oh, dagnabbit.  The spec also says:

  The value of RCX itself is always passed to the host VMM.

and then in code:

    td_exit_qual.gpr_select = control.gpr_select;
    td_exit_qual.xmm_select = control.xmm_select;

    tdx_local_data_ptr->vmm_regs.rcx = td_exit_qual.raw;

    // RAX is not copied, RCX filled above, start from RDX

I don't get why TDX requires bit 1 to be 0, but whatever.

So I was wrong, KVM can (and should!) validate the registers coming from the
guest.  If we want to harden TDX, that's the obvious first step.

---

## [21] Huang, Kai — 2026-04-14
*Subject: Re: [PATCH v2 5/6] KVM: x86: Track available/dirty register masks as
 "unsigned long" values*

On Tue, 2026-04-14 at 08:48 -0700, Sean Christopherson wrote:
> On Mon, Apr 13, 2026, Kai Huang wrote:
> > On Mon, 2026-04-13 at 07:54 -0700, Sean Christopherson wrote:

Right.  It's a bit confusing unfortunately.  Maybe because they think RCX
has a special purpose and don't want to mix it with other registers.

> 
> So I was wrong, KVM can (and should!) validate the registers coming from the

And by "harden TDX" you mean to validate the necessary GPRs are indeed
marked as shared in RCX for each GHCI-defined TDVMCALL, but otherwise return
error to TD immediately (basically like what sev_es_validate_vmgexit() does
IIUC)?

---

## [22] Xiaoyao Li — 2026-04-15
*Subject: Re: [PATCH v2 1/6] KVM: x86: Add dedicated storage for guest RIP*

On 4/14/2026 11:37 PM, Sean Christopherson wrote:
> On Tue, Apr 14, 2026, Chang S. Bae wrote:
>> On 4/14/2026 5:31 AM, Xiaoyao Li wrote:

I'm not trying to object this patch. Instead, I'm trying to understand 
the justification of the change.

So I would expected an updated changelog with above justifications 
incorporated.

---

## [23] Xiaoyao Li — 2026-04-15
*Subject: Re: [PATCH v2 5/6] KVM: x86: Track available/dirty register masks as
 "unsigned long" values*

On 4/14/2026 10:04 PM, Sean Christopherson wrote:
> On Tue, Apr 14, 2026, Xiaoyao Li wrote:
>> On 4/14/2026 7:03 AM, Huang, Kai wrote:

yeah. I had the same feeling that bring up the reduced overhead is not 
acceptable.

> Note that updating only the "available" masks is wrong, as TDX needs to marshall
> written registers back to their correct location.

In what case it needs to marshall written registers back? Can you elaborate?

> In the end, the available/dirty tracking isn't about hardening against bugs, it's
> about deferring expensive VMREAD and VMWRITE (and guest memory) operations until

The initial purpose of writing the code was to find if any case/path in 
KVM that consumes the GPRs for TDX unexpectedly. Not only for the 
hypercall/MSR emulation paths. There are lots of paths in KVM consuming 
the GPRs. It's difficult to aduit every path to ensure either a) it 
won't be reachable by TDX or b) KVM syncs the valid data to the GPRs 
before accessed by TDX.

> An alternative for TDX would be to avoid bouncing through GPRs in the first place,
> e.g. by reworking __kvm_emulate_rdmsr() to not access any registers.  But I'm

---

## [24] Xiaoyao Li — 2026-04-15
*Subject: Re: [PATCH v2 5/6] KVM: x86: Track available/dirty register masks as
 "unsigned long" values*

On 4/15/2026 7:29 PM, Xiaoyao Li wrote:
>> Note that updating only the "available" masks is wrong, as TDX needs 
>> to marshall

Sorry that I asked a silly question. I mistakenly thought TDVMCALL for 
instructions (like, CPUID, RDMSR, WRMSR) use the same output register as 
the x86 instructions. After checking the TDX GHCI, obviously I'm wrong.

But I don't understand what's is wrong regarding "updating only the 
"available" masks". Or what is missing for "marshall written registers 
back to their correct location"?

---

## [25] Sean Christopherson — 2026-04-15
*Subject: Re: [PATCH v2 5/6] KVM: x86: Track available/dirty register masks as
 "unsigned long" values*

On Wed, Apr 15, 2026, Xiaoyao Li wrote:
> On 4/15/2026 7:29 PM, Xiaoyao Li wrote:
> > > Note that updating only the "available" masks is wrong, as TDX needs

KVM would need to also update the "dirty" mask, so that TDX knows it (a) needs
to propagate state back to the GHCI, and (b) that all registers it expects to be
dirty are indeed marked dirty.

---

## [26] Sean Christopherson — 2026-04-15
*Subject: Re: [PATCH v2 1/6] KVM: x86: Add dedicated storage for guest RIP*

On Wed, Apr 15, 2026, Xiaoyao Li wrote:
> On 4/14/2026 11:37 PM, Sean Christopherson wrote:
> > On Tue, Apr 14, 2026, Chang S. Bae wrote:

Noted, I'll expand the changelog for the next version.

---
