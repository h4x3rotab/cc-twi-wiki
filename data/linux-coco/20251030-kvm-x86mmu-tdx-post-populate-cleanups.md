---
title: 'KVM: x86/mmu: TDX post-populate cleanups'
date: 2025-10-30
last_reply: 2025-11-10
message_count: 66
participants: ['Sean Christopherson', 'Huang, Kai', 'Binbin Wu', 'Yan Zhao', 'Edgecombe, Rick P']
---

## [1] Sean Christopherson — 2025-10-30

Non-x86 folks, as with v3, patches 1 and 2 are likely the only thing of
interest here.  They make kvm_arch_vcpu_async_ioctl() mandatory and then
rename it to kvm_arch_vcpu_unlocked_ioctl().

As for the x86 side...

Clean up the TDX post-populate paths (and many tangentially related paths) to
address locking issues between gmem and TDX's post-populate hook[*], and
within KVM itself (KVM doesn't ensure full mutual exclusivity between paths
that for all intents and purposes the TDX-Module requires to be serialized).

I apologize if I missed any trailers or feedback, I think I got everything...

[*] http://lore.kernel.org/all/aG_pLUlHdYIZ2luh@google.com

v4:
 - Collect reviews/acks.
 - Add a lockdep assertion in kvm_tdp_mmu_map_private_pfn(). [Yan]
 - Wrap kvm_tdp_mmu_map_private_pfn() with CONFIG_KVM_GUEST_MEMFD=y. [test bot]
 - Improve (or add) comments. [Kai, and probably others]
 - s/spte/mirror_spte to make it clear what's being passed in
 - Update set_external_spte() to take @mirror_spte as well. [Yan]
 - Move the KVM_BUG_ON() on tdh_mr_extend() failure to the end. [Rick]
 - Take "all" the locks in tdx_vm_ioctl(). [Kai]
 - WARN if KVM attempts to map SPTEs into an invalid root. [Yan]
 - Use tdx_flush_vp_on_cpu() instead of tdx_disassociate_vp() when freeing
   a vCPU in VCPU_TD_STATE_UNINITIALIZED state. [Yan]

v3:
 - https://lore.kernel.org/all/20251017003244.186495-1-seanjc@google.com
 - Collect more reviews.
 - Add the async_ioctl() => unlocked_ioctl() patches, and use the "unlocked"
   variant in the TDX vCPU sub-ioctls so they can take kvm->lock outside of
   vcpu->mutex.
 - Add a patch to document that vcpu->mutex is taken *outside* kvm->slots_lock.
 - Add the tdx_vm_state_guard CLASS() to take kvm->lock, all vcpu->mutex locks,
   and kvm->slots_lock, in order to make tdx_td_init(), tdx_td_finalize(),
   tdx_vcpu_init_mem_region(), and tdx_vcpu_init() mutually exclusive with
   each other, and mutually exclusvie with basically anything that can result
   in contending one of the TDX-Module locks (can't remember which one).
 - Refine the changelog for the "Drop PROVE_MMU=y" patch. [Binbin]

v2:
 - Collect a few reviews (and ignore some because the patches went away).
   [Rick, Kai, Ira]
 - Move TDH_MEM_PAGE_ADD under mmu_lock and drop nr_premapped. [Yan, Rick]
 - Force max_level = PG_LEVEL_4K straightaway. [Yan]
 - s/kvm_tdp_prefault_page/kvm_tdp_page_prefault. [Rick]
 - Use Yan's version of "Say no to pinning!".  [Yan, Rick]
 - Tidy up helpers and macros to reduce boilerplate and copy+pate code, and
   to eliminate redundant/dead code (e.g. KVM_BUG_ON() the same error
   multiple times).
 - KVM_BUG_ON() if TDH_MR_EXTEND fails (I convinced myself it can't).

v1: https://lore.kernel.org/all/20250827000522.4022426-1-seanjc@google.com


Sean Christopherson (26):
  KVM: Make support for kvm_arch_vcpu_async_ioctl() mandatory
  KVM: Rename kvm_arch_vcpu_async_ioctl() to
    kvm_arch_vcpu_unlocked_ioctl()
  KVM: TDX: Drop PROVE_MMU=y sanity check on to-be-populated mappings
  KVM: x86/mmu: Add dedicated API to map guest_memfd pfn into TDP MMU
  KVM: x86/mmu: WARN if KVM attempts to map into an invalid TDP MMU root
  Revert "KVM: x86/tdp_mmu: Add a helper function to walk down the TDP
    MMU"
  KVM: x86/mmu: Rename kvm_tdp_map_page() to kvm_tdp_page_prefault()
  KVM: TDX: Return -EIO, not -EINVAL, on a KVM_BUG_ON() condition
  KVM: TDX: Fold tdx_sept_drop_private_spte() into
    tdx_sept_remove_private_spte()
  KVM: x86/mmu: Drop the return code from
    kvm_x86_ops.remove_external_spte()
  KVM: TDX: WARN if mirror SPTE doesn't have full RWX when creating
    S-EPT mapping
  KVM: TDX: Avoid a double-KVM_BUG_ON() in tdx_sept_zap_private_spte()
  KVM: TDX: Use atomic64_dec_return() instead of a poor equivalent
  KVM: TDX: Fold tdx_mem_page_record_premap_cnt() into its sole caller
  KVM: TDX: ADD pages to the TD image while populating mirror EPT
    entries
  KVM: TDX: Fold tdx_sept_zap_private_spte() into
    tdx_sept_remove_private_spte()
  KVM: TDX: Combine KVM_BUG_ON + pr_tdx_error() into TDX_BUG_ON()
  KVM: TDX: Derive error argument names from the local variable names
  KVM: TDX: Assert that mmu_lock is held for write when removing S-EPT
    entries
  KVM: TDX: Add macro to retry SEAMCALLs when forcing vCPUs out of guest
  KVM: TDX: Add tdx_get_cmd() helper to get and validate sub-ioctl
    command
  KVM: TDX: Convert INIT_MEM_REGION and INIT_VCPU to "unlocked" vCPU
    ioctl
  KVM: TDX: Use guard() to acquire kvm->lock in tdx_vm_ioctl()
  KVM: TDX: Don't copy "cmd" back to userspace for KVM_TDX_CAPABILITIES
  KVM: TDX: Guard VM state transitions with "all" the locks
  KVM: TDX: Bug the VM if extending the initial measurement fails

Yan Zhao (2):
  KVM: TDX: Drop superfluous page pinning in S-EPT management
  KVM: TDX: Fix list_add corruption during vcpu_load()

 arch/arm64/kvm/arm.c               |   6 +
 arch/loongarch/kvm/Kconfig         |   1 -
 arch/loongarch/kvm/vcpu.c          |   4 +-
 arch/mips/kvm/Kconfig              |   1 -
 arch/mips/kvm/mips.c               |   4 +-
 arch/powerpc/kvm/Kconfig           |   1 -
 arch/powerpc/kvm/powerpc.c         |   4 +-
 arch/riscv/kvm/Kconfig             |   1 -
 arch/riscv/kvm/vcpu.c              |   4 +-
 arch/s390/kvm/Kconfig              |   1 -
 arch/s390/kvm/kvm-s390.c           |   4 +-
 arch/x86/include/asm/kvm-x86-ops.h |   1 +
 arch/x86/include/asm/kvm_host.h    |   7 +-
 arch/x86/kvm/mmu.h                 |   3 +-
 arch/x86/kvm/mmu/mmu.c             |  87 +++-
 arch/x86/kvm/mmu/tdp_mmu.c         |  50 +--
 arch/x86/kvm/vmx/main.c            |   9 +
 arch/x86/kvm/vmx/tdx.c             | 659 ++++++++++++++---------------
 arch/x86/kvm/vmx/tdx.h             |   8 +-
 arch/x86/kvm/vmx/x86_ops.h         |   1 +
 arch/x86/kvm/x86.c                 |  13 +
 include/linux/kvm_host.h           |  14 +-
 virt/kvm/Kconfig                   |   3 -
 virt/kvm/kvm_main.c                |   6 +-
 24 files changed, 468 insertions(+), 424 deletions(-)


base-commit: 4cc167c50eb19d44ac7e204938724e685e3d8057

---

## [2] Sean Christopherson — 2025-10-30
*Subject: [PATCH v4 01/28] KVM: Make support for kvm_arch_vcpu_async_ioctl() mandatory*

Implement kvm_arch_vcpu_async_ioctl() "natively" in x86 and arm64 instead
of relying on an #ifdef'd stub, and drop HAVE_KVM_VCPU_ASYNC_IOCTL in
anticipation of using the API on x86.  Once x86 uses the API, providing a
stub for one architecture and having all other architectures opt-in
requires more code than simply implementing the API in the lone holdout.

Eliminating the Kconfig will also reduce churn if the API is renamed in
the future (spoiler alert).

No functional change intended.

Acked-by: Claudio Imbrenda <imbrenda@linux.ibm.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/arm64/kvm/arm.c       |  6 ++++++
 arch/loongarch/kvm/Kconfig |  1 -
 arch/mips/kvm/Kconfig      |  1 -
 arch/powerpc/kvm/Kconfig   |  1 -
 arch/riscv/kvm/Kconfig     |  1 -
 arch/s390/kvm/Kconfig      |  1 -
 arch/x86/kvm/x86.c         |  6 ++++++
 include/linux/kvm_host.h   | 10 ----------
 virt/kvm/Kconfig           |  3 ---
 9 files changed, 12 insertions(+), 18 deletions(-)

diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index 870953b4a8a7..ef5bf57f79b7 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -1835,6 +1835,12 @@ long kvm_arch_vcpu_ioctl(struct file *filp,
 	return r;
 }
 
+long kvm_arch_vcpu_async_ioctl(struct file *filp, unsigned int ioctl,
+			       unsigned long arg)
+{
+	return -ENOIOCTLCMD;
+}
+
 void kvm_arch_sync_dirty_log(struct kvm *kvm, struct kvm_memory_slot *memslot)
 {
 
diff --git a/arch/loongarch/kvm/Kconfig b/arch/loongarch/kvm/Kconfig
index ae64bbdf83a7..ed4f724db774 100644
--- a/arch/loongarch/kvm/Kconfig
+++ b/arch/loongarch/kvm/Kconfig
@@ -25,7 +25,6 @@ config KVM
 	select HAVE_KVM_IRQCHIP
 	select HAVE_KVM_MSI
 	select HAVE_KVM_READONLY_MEM
-	select HAVE_KVM_VCPU_ASYNC_IOCTL
 	select KVM_COMMON
 	select KVM_GENERIC_DIRTYLOG_READ_PROTECT
 	select KVM_GENERIC_HARDWARE_ENABLING
diff --git a/arch/mips/kvm/Kconfig b/arch/mips/kvm/Kconfig
index ab57221fa4dd..cc13cc35f208 100644
--- a/arch/mips/kvm/Kconfig
+++ b/arch/mips/kvm/Kconfig
@@ -22,7 +22,6 @@ config KVM
 	select EXPORT_UASM
 	select KVM_COMMON
 	select KVM_GENERIC_DIRTYLOG_READ_PROTECT
-	select HAVE_KVM_VCPU_ASYNC_IOCTL
 	select KVM_MMIO
 	select KVM_GENERIC_MMU_NOTIFIER
 	select KVM_GENERIC_HARDWARE_ENABLING
diff --git a/arch/powerpc/kvm/Kconfig b/arch/powerpc/kvm/Kconfig
index 2f2702c867f7..c9a2d50ff1b0 100644
--- a/arch/powerpc/kvm/Kconfig
+++ b/arch/powerpc/kvm/Kconfig
@@ -20,7 +20,6 @@ if VIRTUALIZATION
 config KVM
 	bool
 	select KVM_COMMON
-	select HAVE_KVM_VCPU_ASYNC_IOCTL
 	select KVM_VFIO
 	select HAVE_KVM_IRQ_BYPASS
 
diff --git a/arch/riscv/kvm/Kconfig b/arch/riscv/kvm/Kconfig
index c50328212917..77379f77840a 100644
--- a/arch/riscv/kvm/Kconfig
+++ b/arch/riscv/kvm/Kconfig
@@ -23,7 +23,6 @@ config KVM
 	select HAVE_KVM_IRQCHIP
 	select HAVE_KVM_IRQ_ROUTING
 	select HAVE_KVM_MSI
-	select HAVE_KVM_VCPU_ASYNC_IOCTL
 	select HAVE_KVM_READONLY_MEM
 	select HAVE_KVM_DIRTY_RING_ACQ_REL
 	select KVM_COMMON
diff --git a/arch/s390/kvm/Kconfig b/arch/s390/kvm/Kconfig
index cae908d64550..96d16028e8b7 100644
--- a/arch/s390/kvm/Kconfig
+++ b/arch/s390/kvm/Kconfig
@@ -20,7 +20,6 @@ config KVM
 	def_tristate y
 	prompt "Kernel-based Virtual Machine (KVM) support"
 	select HAVE_KVM_CPU_RELAX_INTERCEPT
-	select HAVE_KVM_VCPU_ASYNC_IOCTL
 	select KVM_ASYNC_PF
 	select KVM_ASYNC_PF_SYNC
 	select KVM_COMMON
diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index b4b5d2d09634..ca5ba2caf314 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -7240,6 +7240,12 @@ static int kvm_vm_ioctl_set_clock(struct kvm *kvm, void __user *argp)
 	return 0;
 }
 
+long kvm_arch_vcpu_async_ioctl(struct file *filp, unsigned int ioctl,
+			       unsigned long arg)
+{
+	return -ENOIOCTLCMD;
+}
+
 int kvm_arch_vm_ioctl(struct file *filp, unsigned int ioctl, unsigned long arg)
 {
 	struct kvm *kvm = filp->private_data;
diff --git a/include/linux/kvm_host.h b/include/linux/kvm_host.h
index 5bd76cf394fa..7186b2ae4b57 100644
--- a/include/linux/kvm_host.h
+++ b/include/linux/kvm_host.h
@@ -2437,18 +2437,8 @@ static inline bool kvm_arch_no_poll(struct kvm_vcpu *vcpu)
 }
 #endif /* CONFIG_HAVE_KVM_NO_POLL */
 
-#ifdef CONFIG_HAVE_KVM_VCPU_ASYNC_IOCTL
 long kvm_arch_vcpu_async_ioctl(struct file *filp,
 			       unsigned int ioctl, unsigned long arg);
-#else
-static inline long kvm_arch_vcpu_async_ioctl(struct file *filp,
-					     unsigned int ioctl,
-					     unsigned long arg)
-{
-	return -ENOIOCTLCMD;
-}
-#endif /* CONFIG_HAVE_KVM_VCPU_ASYNC_IOCTL */
-
 void kvm_arch_guest_memory_reclaimed(struct kvm *kvm);
 
 #ifdef CONFIG_HAVE_KVM_VCPU_RUN_PID_CHANGE
diff --git a/virt/kvm/Kconfig b/virt/kvm/Kconfig
index 5f0015c5dd95..267c7369c765 100644
--- a/virt/kvm/Kconfig
+++ b/virt/kvm/Kconfig
@@ -78,9 +78,6 @@ config HAVE_KVM_IRQ_BYPASS
        tristate
        select IRQ_BYPASS_MANAGER
 
-config HAVE_KVM_VCPU_ASYNC_IOCTL
-       bool
-
 config HAVE_KVM_VCPU_RUN_PID_CHANGE
        bool

---

## [3] Sean Christopherson — 2025-10-30
*Subject: [PATCH v4 02/28] KVM: Rename kvm_arch_vcpu_async_ioctl() to kvm_arch_vcpu_unlocked_ioctl()*

Rename the "async" ioctl API to "unlocked" so that upcoming usage in x86's
TDX code doesn't result in a massive misnomer.  To avoid having to retry
SEAMCALLs, TDX needs to acquire kvm->lock *and* all vcpu->mutex locks, and
acquiring all of those locks after/inside the current vCPU's mutex is a
non-starter.  However, TDX also needs to acquire the vCPU's mutex and load
the vCPU, i.e. the handling is very much not async to the vCPU.

No functional change intended.

Acked-by: Claudio Imbrenda <imbrenda@linux.ibm.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/arm64/kvm/arm.c       | 4 ++--
 arch/loongarch/kvm/vcpu.c  | 4 ++--
 arch/mips/kvm/mips.c       | 4 ++--
 arch/powerpc/kvm/powerpc.c | 4 ++--
 arch/riscv/kvm/vcpu.c      | 4 ++--
 arch/s390/kvm/kvm-s390.c   | 4 ++--
 arch/x86/kvm/x86.c         | 4 ++--
 include/linux/kvm_host.h   | 4 ++--
 virt/kvm/kvm_main.c        | 6 +++---
 9 files changed, 19 insertions(+), 19 deletions(-)

diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index ef5bf57f79b7..cf23f6b07ec7 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -1835,8 +1835,8 @@ long kvm_arch_vcpu_ioctl(struct file *filp,
 	return r;
 }
 
-long kvm_arch_vcpu_async_ioctl(struct file *filp, unsigned int ioctl,
-			       unsigned long arg)
+long kvm_arch_vcpu_unlocked_ioctl(struct file *filp, unsigned int ioctl,
+				  unsigned long arg)
 {
 	return -ENOIOCTLCMD;
 }
diff --git a/arch/loongarch/kvm/vcpu.c b/arch/loongarch/kvm/vcpu.c
index 30e3b089a596..9a5844e85fd3 100644
--- a/arch/loongarch/kvm/vcpu.c
+++ b/arch/loongarch/kvm/vcpu.c
@@ -1471,8 +1471,8 @@ int kvm_vcpu_ioctl_interrupt(struct kvm_vcpu *vcpu, struct kvm_interrupt *irq)
 	return 0;
 }
 
-long kvm_arch_vcpu_async_ioctl(struct file *filp,
-			       unsigned int ioctl, unsigned long arg)
+long kvm_arch_vcpu_unlocked_ioctl(struct file *filp, unsigned int ioctl,
+				  unsigned long arg)
 {
 	void __user *argp = (void __user *)arg;
 	struct kvm_vcpu *vcpu = filp->private_data;
diff --git a/arch/mips/kvm/mips.c b/arch/mips/kvm/mips.c
index a75587018f44..b0fb92fda4d4 100644
--- a/arch/mips/kvm/mips.c
+++ b/arch/mips/kvm/mips.c
@@ -895,8 +895,8 @@ static int kvm_vcpu_ioctl_enable_cap(struct kvm_vcpu *vcpu,
 	return r;
 }
 
-long kvm_arch_vcpu_async_ioctl(struct file *filp, unsigned int ioctl,
-			       unsigned long arg)
+long kvm_arch_vcpu_unlocked_ioctl(struct file *filp, unsigned int ioctl,
+				  unsigned long arg)
 {
 	struct kvm_vcpu *vcpu = filp->private_data;
 	void __user *argp = (void __user *)arg;
diff --git a/arch/powerpc/kvm/powerpc.c b/arch/powerpc/kvm/powerpc.c
index 2ba057171ebe..9a89a6d98f97 100644
--- a/arch/powerpc/kvm/powerpc.c
+++ b/arch/powerpc/kvm/powerpc.c
@@ -2028,8 +2028,8 @@ int kvm_arch_vcpu_ioctl_set_mpstate(struct kvm_vcpu *vcpu,
 	return -EINVAL;
 }
 
-long kvm_arch_vcpu_async_ioctl(struct file *filp,
-			       unsigned int ioctl, unsigned long arg)
+long kvm_arch_vcpu_unlocked_ioctl(struct file *filp, unsigned int ioctl,
+				  unsigned long arg)
 {
 	struct kvm_vcpu *vcpu = filp->private_data;
 	void __user *argp = (void __user *)arg;
diff --git a/arch/riscv/kvm/vcpu.c b/arch/riscv/kvm/vcpu.c
index bccb919ca615..a4bd6077eecc 100644
--- a/arch/riscv/kvm/vcpu.c
+++ b/arch/riscv/kvm/vcpu.c
@@ -238,8 +238,8 @@ vm_fault_t kvm_arch_vcpu_fault(struct kvm_vcpu *vcpu, struct vm_fault *vmf)
 	return VM_FAULT_SIGBUS;
 }
 
-long kvm_arch_vcpu_async_ioctl(struct file *filp,
-			       unsigned int ioctl, unsigned long arg)
+long kvm_arch_vcpu_unlocked_ioctl(struct file *filp, unsigned int ioctl,
+				  unsigned long arg)
 {
 	struct kvm_vcpu *vcpu = filp->private_data;
 	void __user *argp = (void __user *)arg;
diff --git a/arch/s390/kvm/kvm-s390.c b/arch/s390/kvm/kvm-s390.c
index 16ba04062854..8c4caa5f2fcd 100644
--- a/arch/s390/kvm/kvm-s390.c
+++ b/arch/s390/kvm/kvm-s390.c
@@ -5730,8 +5730,8 @@ static long kvm_s390_vcpu_memsida_op(struct kvm_vcpu *vcpu,
 	return r;
 }
 
-long kvm_arch_vcpu_async_ioctl(struct file *filp,
-			       unsigned int ioctl, unsigned long arg)
+long kvm_arch_vcpu_unlocked_ioctl(struct file *filp, unsigned int ioctl,
+				  unsigned long arg)
 {
 	struct kvm_vcpu *vcpu = filp->private_data;
 	void __user *argp = (void __user *)arg;
diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index ca5ba2caf314..b85cb213a336 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -7240,8 +7240,8 @@ static int kvm_vm_ioctl_set_clock(struct kvm *kvm, void __user *argp)
 	return 0;
 }
 
-long kvm_arch_vcpu_async_ioctl(struct file *filp, unsigned int ioctl,
-			       unsigned long arg)
+long kvm_arch_vcpu_unlocked_ioctl(struct file *filp, unsigned int ioctl,
+				  unsigned long arg)
 {
 	return -ENOIOCTLCMD;
 }
diff --git a/include/linux/kvm_host.h b/include/linux/kvm_host.h
index 7186b2ae4b57..d93f75b05ae2 100644
--- a/include/linux/kvm_host.h
+++ b/include/linux/kvm_host.h
@@ -1557,6 +1557,8 @@ long kvm_arch_dev_ioctl(struct file *filp,
 			unsigned int ioctl, unsigned long arg);
 long kvm_arch_vcpu_ioctl(struct file *filp,
 			 unsigned int ioctl, unsigned long arg);
+long kvm_arch_vcpu_unlocked_ioctl(struct file *filp,
+				  unsigned int ioctl, unsigned long arg);
 vm_fault_t kvm_arch_vcpu_fault(struct kvm_vcpu *vcpu, struct vm_fault *vmf);
 
 int kvm_vm_ioctl_check_extension(struct kvm *kvm, long ext);
@@ -2437,8 +2439,6 @@ static inline bool kvm_arch_no_poll(struct kvm_vcpu *vcpu)
 }
 #endif /* CONFIG_HAVE_KVM_NO_POLL */
 
-long kvm_arch_vcpu_async_ioctl(struct file *filp,
-			       unsigned int ioctl, unsigned long arg);
 void kvm_arch_guest_memory_reclaimed(struct kvm *kvm);
 
 #ifdef CONFIG_HAVE_KVM_VCPU_RUN_PID_CHANGE
diff --git a/virt/kvm/kvm_main.c b/virt/kvm/kvm_main.c
index 4845e5739436..9eca084bdcbe 100644
--- a/virt/kvm/kvm_main.c
+++ b/virt/kvm/kvm_main.c
@@ -4434,10 +4434,10 @@ static long kvm_vcpu_ioctl(struct file *filp,
 		return r;
 
 	/*
-	 * Some architectures have vcpu ioctls that are asynchronous to vcpu
-	 * execution; mutex_lock() would break them.
+	 * Let arch code handle select vCPU ioctls without holding vcpu->mutex,
+	 * e.g. to support ioctls that can run asynchronous to vCPU execution.
 	 */
-	r = kvm_arch_vcpu_async_ioctl(filp, ioctl, arg);
+	r = kvm_arch_vcpu_unlocked_ioctl(filp, ioctl, arg);
 	if (r != -ENOIOCTLCMD)
 		return r;

---

## [4] Sean Christopherson — 2025-10-30
*Subject: [PATCH v4 03/28] KVM: TDX: Drop PROVE_MMU=y sanity check on
 to-be-populated mappings*

Drop TDX's sanity check that a mirror EPT mapping isn't zapped between
creating said mapping and doing TDH.MEM.PAGE.ADD, as the check is
simultaneously superfluous and incomplete.  Per commit 2608f1057601
("KVM: x86/tdp_mmu: Add a helper function to walk down the TDP MMU"), the
justification for introducing kvm_tdp_mmu_gpa_is_mapped() was to check
that the target gfn was pre-populated, with a link that points to this
snippet:

 : > One small question:
 : >
 : > What if the memory region passed to KVM_TDX_INIT_MEM_REGION hasn't been pre-
 : > populated?  If we want to make KVM_TDX_INIT_MEM_REGION work with these regions,
 : > then we still need to do the real map.  Or we can make KVM_TDX_INIT_MEM_REGION
 : > return error when it finds the region hasn't been pre-populated?
 :
 : Return an error.  I don't love the idea of bleeding so many TDX details into
 : userspace, but I'm pretty sure that ship sailed a long, long time ago.

But that justification makes little sense for the final code, as the check
on nr_premapped after TDH.MEM.PAGE.ADD will detect and return an error if
KVM attempted to zap a S-EPT entry (tdx_sept_zap_private_spte() will fail
on TDH.MEM.RANGE.BLOCK due lack of a valid S-EPT entry).  And as evidenced
by the "is mapped?" code being guarded with CONFIG_KVM_PROVE_MMU=y, KVM is
NOT relying on the check for general correctness.

The sanity check is also incomplete in the sense that mmu_lock is dropped
between the check and TDH.MEM.PAGE.ADD, i.e. will only detect KVM bugs that
zap SPTEs in a very specific window (note, this also applies to the check
on nr_premapped).

Removing the sanity check will allow removing kvm_tdp_mmu_gpa_is_mapped(),
which has no business being exposed to vendor code, and more importantly
will pave the way for eliminating the "pre-map" approach entirely in favor
of doing TDH.MEM.PAGE.ADD under mmu_lock.

Reviewed-by: Ira Weiny <ira.weiny@intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/vmx/tdx.c | 14 --------------
 1 file changed, 14 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 326db9b9c567..4c3014befe9f 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -3181,20 +3181,6 @@ static int tdx_gmem_post_populate(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
 	if (ret < 0)
 		goto out;
 
-	/*
-	 * The private mem cannot be zapped after kvm_tdp_map_page()
-	 * because all paths are covered by slots_lock and the
-	 * filemap invalidate lock.  Check that they are indeed enough.
-	 */
-	if (IS_ENABLED(CONFIG_KVM_PROVE_MMU)) {
-		scoped_guard(read_lock, &kvm->mmu_lock) {
-			if (KVM_BUG_ON(!kvm_tdp_mmu_gpa_is_mapped(vcpu, gpa), kvm)) {
-				ret = -EIO;
-				goto out;
-			}
-		}
-	}
-
 	ret = 0;
 	err = tdh_mem_page_add(&kvm_tdx->td, gpa, pfn_to_page(pfn),
 			       src_page, &entry, &level_state);

---

## [5] Sean Christopherson — 2025-10-30
*Subject: [PATCH v4 04/28] KVM: x86/mmu: Add dedicated API to map guest_memfd
 pfn into TDP MMU*

Add and use a new API for mapping a private pfn from guest_memfd into the
TDP MMU from TDX's post-populate hook instead of partially open-coding the
functionality into the TDX code.  Sharing code with the pre-fault path
sounded good on paper, but it's fatally flawed as simulating a fault loses
the pfn, and calling back into gmem to re-retrieve the pfn creates locking
problems, e.g. kvm_gmem_populate() already holds the gmem invalidation
lock.

Providing a dedicated API will also removing several MMU exports that
ideally would not be exposed outside of the MMU, let alone to vendor code.
On that topic, opportunistically drop the kvm_mmu_load() export.  Leave
kvm_tdp_mmu_gpa_is_mapped() alone for now; the entire commit that added
kvm_tdp_mmu_gpa_is_mapped() will be removed in the near future.

Gate the API on CONFIG_KVM_GUEST_MEMFD=y as private memory _must_ be backed
by guest_memfd.  Add a lockdep-only assert to that the incoming pfn is
indeed backed by guest_memfd, and that the gmem instance's invalidate lock
is held (which, combined with slots_lock being held, obviates the need to
check for a stale "fault").

Cc: Michael Roth <michael.roth@amd.com>
Cc: Yan Zhao <yan.y.zhao@intel.com>
Cc: Ira Weiny <ira.weiny@intel.com>
Cc: Vishal Annapurve <vannapurve@google.com>
Cc: Rick Edgecombe <rick.p.edgecombe@intel.com>
Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Link: https://lore.kernel.org/all/20250709232103.zwmufocd3l7sqk7y@amd.com
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/mmu.h     |  1 +
 arch/x86/kvm/mmu/mmu.c | 81 +++++++++++++++++++++++++++++++++++++++++-
 arch/x86/kvm/vmx/tdx.c | 10 ++----
 3 files changed, 84 insertions(+), 8 deletions(-)

diff --git a/arch/x86/kvm/mmu.h b/arch/x86/kvm/mmu.h
index f63074048ec6..2f108e381959 100644
--- a/arch/x86/kvm/mmu.h
+++ b/arch/x86/kvm/mmu.h
@@ -259,6 +259,7 @@ extern bool tdp_mmu_enabled;
 
 bool kvm_tdp_mmu_gpa_is_mapped(struct kvm_vcpu *vcpu, u64 gpa);
 int kvm_tdp_map_page(struct kvm_vcpu *vcpu, gpa_t gpa, u64 error_code, u8 *level);
+int kvm_tdp_mmu_map_private_pfn(struct kvm_vcpu *vcpu, gfn_t gfn, kvm_pfn_t pfn);
 
 static inline bool kvm_memslots_have_rmaps(struct kvm *kvm)
 {
diff --git a/arch/x86/kvm/mmu/mmu.c b/arch/x86/kvm/mmu/mmu.c
index 18d69d48bc55..bad0480bdb0d 100644
--- a/arch/x86/kvm/mmu/mmu.c
+++ b/arch/x86/kvm/mmu/mmu.c
@@ -5014,6 +5014,86 @@ long kvm_arch_vcpu_pre_fault_memory(struct kvm_vcpu *vcpu,
 	return min(range->size, end - range->gpa);
 }
 
+#ifdef CONFIG_KVM_GUEST_MEMFD
+static void kvm_assert_gmem_invalidate_lock_held(struct kvm_memory_slot *slot)
+{
+#ifdef CONFIG_PROVE_LOCKING
+	if (WARN_ON_ONCE(!kvm_slot_has_gmem(slot)) ||
+	    WARN_ON_ONCE(!slot->gmem.file) ||
+	    WARN_ON_ONCE(!file_count(slot->gmem.file)))
+		return;
+
+	lockdep_assert_held(&file_inode(slot->gmem.file)->i_mapping->invalidate_lock);
+#endif
+}
+
+int kvm_tdp_mmu_map_private_pfn(struct kvm_vcpu *vcpu, gfn_t gfn, kvm_pfn_t pfn)
+{
+	struct kvm_page_fault fault = {
+		.addr = gfn_to_gpa(gfn),
+		.error_code = PFERR_GUEST_FINAL_MASK | PFERR_PRIVATE_ACCESS,
+		.prefetch = true,
+		.is_tdp = true,
+		.nx_huge_page_workaround_enabled = is_nx_huge_page_enabled(vcpu->kvm),
+
+		.max_level = PG_LEVEL_4K,
+		.req_level = PG_LEVEL_4K,
+		.goal_level = PG_LEVEL_4K,
+		.is_private = true,
+
+		.gfn = gfn,
+		.slot = kvm_vcpu_gfn_to_memslot(vcpu, gfn),
+		.pfn = pfn,
+		.map_writable = true,
+	};
+	struct kvm *kvm = vcpu->kvm;
+	int r;
+
+	lockdep_assert_held(&kvm->slots_lock);
+
+	/*
+	 * Mapping a pre-determined private pfn is intended only for use when
+	 * populating a guest_memfd instance.  Assert that the slot is backed
+	 * by guest_memfd and that the gmem instance's invalidate_lock is held.
+	 */
+	kvm_assert_gmem_invalidate_lock_held(fault.slot);
+
+	if (KVM_BUG_ON(!tdp_mmu_enabled, kvm))
+		return -EIO;
+
+	if (kvm_gfn_is_write_tracked(kvm, fault.slot, fault.gfn))
+		return -EPERM;
+
+	r = kvm_mmu_reload(vcpu);
+	if (r)
+		return r;
+
+	r = mmu_topup_memory_caches(vcpu, false);
+	if (r)
+		return r;
+
+	do {
+		if (signal_pending(current))
+			return -EINTR;
+
+		if (kvm_test_request(KVM_REQ_VM_DEAD, vcpu))
+			return -EIO;
+
+		cond_resched();
+
+		guard(read_lock)(&kvm->mmu_lock);
+
+		r = kvm_tdp_mmu_map(vcpu, &fault);
+	} while (r == RET_PF_RETRY);
+
+	if (r != RET_PF_FIXED)
+		return -EIO;
+
+	return 0;
+}
+EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_tdp_mmu_map_private_pfn);
+#endif
+
 static void nonpaging_init_context(struct kvm_mmu *context)
 {
 	context->page_fault = nonpaging_page_fault;
@@ -5997,7 +6077,6 @@ int kvm_mmu_load(struct kvm_vcpu *vcpu)
 out:
 	return r;
 }
-EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_mmu_load);
 
 void kvm_mmu_unload(struct kvm_vcpu *vcpu)
 {
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 4c3014befe9f..29f344af4cc2 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -3157,15 +3157,12 @@ struct tdx_gmem_post_populate_arg {
 static int tdx_gmem_post_populate(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
 				  void __user *src, int order, void *_arg)
 {
-	u64 error_code = PFERR_GUEST_FINAL_MASK | PFERR_PRIVATE_ACCESS;
-	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
 	struct tdx_gmem_post_populate_arg *arg = _arg;
-	struct kvm_vcpu *vcpu = arg->vcpu;
+	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
+	u64 err, entry, level_state;
 	gpa_t gpa = gfn_to_gpa(gfn);
-	u8 level = PG_LEVEL_4K;
 	struct page *src_page;
 	int ret, i;
-	u64 err, entry, level_state;
 
 	/*
 	 * Get the source page if it has been faulted in. Return failure if the
@@ -3177,7 +3174,7 @@ static int tdx_gmem_post_populate(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
 	if (ret != 1)
 		return -ENOMEM;
 
-	ret = kvm_tdp_map_page(vcpu, gpa, error_code, &level);
+	ret = kvm_tdp_mmu_map_private_pfn(arg->vcpu, gfn, pfn);
 	if (ret < 0)
 		goto out;
 
@@ -3240,7 +3237,6 @@ static int tdx_vcpu_init_mem_region(struct kvm_vcpu *vcpu, struct kvm_tdx_cmd *c
 	    !vt_is_tdx_private_gpa(kvm, region.gpa + (region.nr_pages << PAGE_SHIFT) - 1))
 		return -EINVAL;
 
-	kvm_mmu_reload(vcpu);
 	ret = 0;
 	while (region.nr_pages) {
 		if (signal_pending(current)) {

---

## [6] Sean Christopherson — 2025-10-30
*Subject: [PATCH v4 05/28] KVM: x86/mmu: WARN if KVM attempts to map into an
 invalid TDP MMU root*

When mapping into the TDP MMU, WARN (if KVM_PROVE_MMU=y) if the root is
invalid, e.g. if KVM is attempting to insert a mapping without checking if
the information and MMU context is fresh.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/mmu/tdp_mmu.c | 2 ++
 1 file changed, 2 insertions(+)

diff --git a/arch/x86/kvm/mmu/tdp_mmu.c b/arch/x86/kvm/mmu/tdp_mmu.c
index c5734ca5c17d..440fd8f80397 100644
--- a/arch/x86/kvm/mmu/tdp_mmu.c
+++ b/arch/x86/kvm/mmu/tdp_mmu.c
@@ -1273,6 +1273,8 @@ int kvm_tdp_mmu_map(struct kvm_vcpu *vcpu, struct kvm_page_fault *fault)
 	struct kvm_mmu_page *sp;
 	int ret = RET_PF_RETRY;
 
+	KVM_MMU_WARN_ON(!root || root->role.invalid);
+
 	kvm_mmu_hugepage_adjust(vcpu, fault);
 
 	trace_kvm_mmu_spte_requested(fault);

---

## [7] Sean Christopherson — 2025-10-30
*Subject: [PATCH v4 06/28] Revert "KVM: x86/tdp_mmu: Add a helper function to
 walk down the TDP MMU"*

Remove the helper and exports that were added to allow TDX code to reuse
kvm_tdp_map_page() for its gmem post-populate flow now that a dedicated
TDP MMU API is provided to install a mapping given a gfn+pfn pair.

This reverts commit 2608f105760115e94a03efd9f12f8fbfd1f9af4b.

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/mmu.h         |  2 --
 arch/x86/kvm/mmu/mmu.c     |  4 ++--
 arch/x86/kvm/mmu/tdp_mmu.c | 37 +++++--------------------------------
 3 files changed, 7 insertions(+), 36 deletions(-)

diff --git a/arch/x86/kvm/mmu.h b/arch/x86/kvm/mmu.h
index 2f108e381959..9e5045a60d8b 100644
--- a/arch/x86/kvm/mmu.h
+++ b/arch/x86/kvm/mmu.h
@@ -257,8 +257,6 @@ extern bool tdp_mmu_enabled;
 #define tdp_mmu_enabled false
 #endif
 
-bool kvm_tdp_mmu_gpa_is_mapped(struct kvm_vcpu *vcpu, u64 gpa);
-int kvm_tdp_map_page(struct kvm_vcpu *vcpu, gpa_t gpa, u64 error_code, u8 *level);
 int kvm_tdp_mmu_map_private_pfn(struct kvm_vcpu *vcpu, gfn_t gfn, kvm_pfn_t pfn);
 
 static inline bool kvm_memslots_have_rmaps(struct kvm *kvm)
diff --git a/arch/x86/kvm/mmu/mmu.c b/arch/x86/kvm/mmu/mmu.c
index bad0480bdb0d..3a5104e4127a 100644
--- a/arch/x86/kvm/mmu/mmu.c
+++ b/arch/x86/kvm/mmu/mmu.c
@@ -4924,7 +4924,8 @@ int kvm_tdp_page_fault(struct kvm_vcpu *vcpu, struct kvm_page_fault *fault)
 	return direct_page_fault(vcpu, fault);
 }
 
-int kvm_tdp_map_page(struct kvm_vcpu *vcpu, gpa_t gpa, u64 error_code, u8 *level)
+static int kvm_tdp_map_page(struct kvm_vcpu *vcpu, gpa_t gpa, u64 error_code,
+			    u8 *level)
 {
 	int r;
 
@@ -4966,7 +4967,6 @@ int kvm_tdp_map_page(struct kvm_vcpu *vcpu, gpa_t gpa, u64 error_code, u8 *level
 		return -EIO;
 	}
 }
-EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_tdp_map_page);
 
 long kvm_arch_vcpu_pre_fault_memory(struct kvm_vcpu *vcpu,
 				    struct kvm_pre_fault_memory *range)
diff --git a/arch/x86/kvm/mmu/tdp_mmu.c b/arch/x86/kvm/mmu/tdp_mmu.c
index 440fd8f80397..e735d2f8367b 100644
--- a/arch/x86/kvm/mmu/tdp_mmu.c
+++ b/arch/x86/kvm/mmu/tdp_mmu.c
@@ -1941,13 +1941,16 @@ bool kvm_tdp_mmu_write_protect_gfn(struct kvm *kvm,
  *
  * Must be called between kvm_tdp_mmu_walk_lockless_{begin,end}.
  */
-static int __kvm_tdp_mmu_get_walk(struct kvm_vcpu *vcpu, u64 addr, u64 *sptes,
-				  struct kvm_mmu_page *root)
+int kvm_tdp_mmu_get_walk(struct kvm_vcpu *vcpu, u64 addr, u64 *sptes,
+			 int *root_level)
 {
+	struct kvm_mmu_page *root = root_to_sp(vcpu->arch.mmu->root.hpa);
 	struct tdp_iter iter;
 	gfn_t gfn = addr >> PAGE_SHIFT;
 	int leaf = -1;
 
+	*root_level = vcpu->arch.mmu->root_role.level;
+
 	for_each_tdp_pte(iter, vcpu->kvm, root, gfn, gfn + 1) {
 		leaf = iter.level;
 		sptes[leaf] = iter.old_spte;
@@ -1956,36 +1959,6 @@ static int __kvm_tdp_mmu_get_walk(struct kvm_vcpu *vcpu, u64 addr, u64 *sptes,
 	return leaf;
 }
 
-int kvm_tdp_mmu_get_walk(struct kvm_vcpu *vcpu, u64 addr, u64 *sptes,
-			 int *root_level)
-{
-	struct kvm_mmu_page *root = root_to_sp(vcpu->arch.mmu->root.hpa);
-	*root_level = vcpu->arch.mmu->root_role.level;
-
-	return __kvm_tdp_mmu_get_walk(vcpu, addr, sptes, root);
-}
-
-bool kvm_tdp_mmu_gpa_is_mapped(struct kvm_vcpu *vcpu, u64 gpa)
-{
-	struct kvm *kvm = vcpu->kvm;
-	bool is_direct = kvm_is_addr_direct(kvm, gpa);
-	hpa_t root = is_direct ? vcpu->arch.mmu->root.hpa :
-				 vcpu->arch.mmu->mirror_root_hpa;
-	u64 sptes[PT64_ROOT_MAX_LEVEL + 1], spte;
-	int leaf;
-
-	lockdep_assert_held(&kvm->mmu_lock);
-	rcu_read_lock();
-	leaf = __kvm_tdp_mmu_get_walk(vcpu, gpa, sptes, root_to_sp(root));
-	rcu_read_unlock();
-	if (leaf < 0)
-		return false;
-
-	spte = sptes[leaf];
-	return is_shadow_present_pte(spte) && is_last_spte(spte, leaf);
-}
-EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_tdp_mmu_gpa_is_mapped);
-
 /*
  * Returns the last level spte pointer of the shadow page walk for the given
  * gpa, and sets *spte to the spte value. This spte may be non-preset. If no

---

## [8] Sean Christopherson — 2025-10-30
*Subject: [PATCH v4 07/28] KVM: x86/mmu: Rename kvm_tdp_map_page() to kvm_tdp_page_prefault()*

Rename kvm_tdp_map_page() to kvm_tdp_page_prefault() now that it's used
only by kvm_arch_vcpu_pre_fault_memory().

No functional change intended.

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/mmu/mmu.c | 6 +++---
 1 file changed, 3 insertions(+), 3 deletions(-)

diff --git a/arch/x86/kvm/mmu/mmu.c b/arch/x86/kvm/mmu/mmu.c
index 3a5104e4127a..10e579f8fa8e 100644
--- a/arch/x86/kvm/mmu/mmu.c
+++ b/arch/x86/kvm/mmu/mmu.c
@@ -4924,8 +4924,8 @@ int kvm_tdp_page_fault(struct kvm_vcpu *vcpu, struct kvm_page_fault *fault)
 	return direct_page_fault(vcpu, fault);
 }
 
-static int kvm_tdp_map_page(struct kvm_vcpu *vcpu, gpa_t gpa, u64 error_code,
-			    u8 *level)
+static int kvm_tdp_page_prefault(struct kvm_vcpu *vcpu, gpa_t gpa,
+				 u64 error_code, u8 *level)
 {
 	int r;
 
@@ -5002,7 +5002,7 @@ long kvm_arch_vcpu_pre_fault_memory(struct kvm_vcpu *vcpu,
 	 * Shadow paging uses GVA for kvm page fault, so restrict to
 	 * two-dimensional paging.
 	 */
-	r = kvm_tdp_map_page(vcpu, range->gpa | direct_bits, error_code, &level);
+	r = kvm_tdp_page_prefault(vcpu, range->gpa | direct_bits, error_code, &level);
 	if (r < 0)
 		return r;

---

## [9] Sean Christopherson — 2025-10-30
*Subject: [PATCH v4 08/28] KVM: TDX: Drop superfluous page pinning in S-EPT management*

From: Yan Zhao <yan.y.zhao@intel.com>

Don't explicitly pin pages when mapping pages into the S-EPT, guest_memfd
doesn't support page migration in any capacity, i.e. there are no migrate
callbacks because guest_memfd pages *can't* be migrated.  See the WARN in
kvm_gmem_migrate_folio().

Eliminating TDX's explicit pinning will also enable guest_memfd to support
in-place conversion between shared and private memory[1][2].  Because KVM
cannot distinguish between speculative/transient refcounts and the
intentional refcount for TDX on private pages[3], failing to release
private page refcount in TDX could cause guest_memfd to indefinitely wait
on decreasing the refcount for the splitting.

Under normal conditions, not holding an extra page refcount in TDX is safe
because guest_memfd ensures pages are retained until its invalidation
notification to KVM MMU is completed. However, if there're bugs in KVM/TDX
module, not holding an extra refcount when a page is mapped in S-EPT could
result in a page being released from guest_memfd while still mapped in the
S-EPT.  But, doing work to make a fatal error slightly less fatal is a net
negative when that extra work adds complexity and confusion.

Several approaches were considered to address the refcount issue, including
  - Attempting to modify the KVM unmap operation to return a failure,
    which was deemed too complex and potentially incorrect[4].
  - Increasing the folio reference count only upon S-EPT zapping failure[5].
  - Use page flags or page_ext to indicate a page is still used by TDX[6],
    which does not work for HVO (HugeTLB Vmemmap Optimization).
  - Setting HWPOISON bit or leveraging folio_set_hugetlb_hwpoison()[7].

Due to the complexity or inappropriateness of these approaches, and the
fact that S-EPT zapping failure is currently only possible when there are
bugs in the KVM or TDX module, which is very rare in a production kernel,
a straightforward approach of simply not holding the page reference count
in TDX was chosen[8].

When S-EPT zapping errors occur, KVM_BUG_ON() is invoked to kick off all
vCPUs and mark the VM as dead. Although there is a potential window that a
private page mapped in the S-EPT could be reallocated and used outside the
VM, the loud warning from KVM_BUG_ON() should provide sufficient debug
information. To be robust against bugs, the user can enable panic_on_warn
as normal.

Link: https://lore.kernel.org/all/cover.1747264138.git.ackerleytng@google.com [1]
Link: https://youtu.be/UnBKahkAon4 [2]
Link: https://lore.kernel.org/all/CAGtprH_ypohFy9TOJ8Emm_roT4XbQUtLKZNFcM6Fr+fhTFkE0Q@mail.gmail.com [3]
Link: https://lore.kernel.org/all/aEEEJbTzlncbRaRA@yzhao56-desk.sh.intel.com [4]
Link: https://lore.kernel.org/all/aE%2Fq9VKkmaCcuwpU@yzhao56-desk.sh.intel.com [5]
Link: https://lore.kernel.org/all/aFkeBtuNBN1RrDAJ@yzhao56-desk.sh.intel.com [6]
Link: https://lore.kernel.org/all/diqzy0tikran.fsf@ackerleytng-ctop.c.googlers.com [7]
Link: https://lore.kernel.org/all/53ea5239f8ef9d8df9af593647243c10435fd219.camel@intel.com [8]
Suggested-by: Vishal Annapurve <vannapurve@google.com>
Suggested-by: Ackerley Tng <ackerleytng@google.com>
Suggested-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Signed-off-by: Yan Zhao <yan.y.zhao@intel.com>
Reviewed-by: Ira Weiny <ira.weiny@intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
[sean: extract out of hugepage series, massage changelog accordingly]
Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>
Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/vmx/tdx.c | 28 ++++------------------------
 1 file changed, 4 insertions(+), 24 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 29f344af4cc2..c3bae6b96dc4 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1583,29 +1583,22 @@ void tdx_load_mmu_pgd(struct kvm_vcpu *vcpu, hpa_t root_hpa, int pgd_level)
 	td_vmcs_write64(to_tdx(vcpu), SHARED_EPT_POINTER, root_hpa);
 }
 
-static void tdx_unpin(struct kvm *kvm, struct page *page)
-{
-	put_page(page);
-}
-
 static int tdx_mem_page_aug(struct kvm *kvm, gfn_t gfn,
-			    enum pg_level level, struct page *page)
+			    enum pg_level level, kvm_pfn_t pfn)
 {
 	int tdx_level = pg_level_to_tdx_sept_level(level);
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
+	struct page *page = pfn_to_page(pfn);
 	gpa_t gpa = gfn_to_gpa(gfn);
 	u64 entry, level_state;
 	u64 err;
 
 	err = tdh_mem_page_aug(&kvm_tdx->td, gpa, tdx_level, page, &entry, &level_state);
-	if (unlikely(tdx_operand_busy(err))) {
-		tdx_unpin(kvm, page);
+	if (unlikely(tdx_operand_busy(err)))
 		return -EBUSY;
-	}
 
 	if (KVM_BUG_ON(err, kvm)) {
 		pr_tdx_error_2(TDH_MEM_PAGE_AUG, err, entry, level_state);
-		tdx_unpin(kvm, page);
 		return -EIO;
 	}
 
@@ -1639,29 +1632,18 @@ static int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn,
 				     enum pg_level level, kvm_pfn_t pfn)
 {
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
-	struct page *page = pfn_to_page(pfn);
 
 	/* TODO: handle large pages. */
 	if (KVM_BUG_ON(level != PG_LEVEL_4K, kvm))
 		return -EINVAL;
 
-	/*
-	 * Because guest_memfd doesn't support page migration with
-	 * a_ops->migrate_folio (yet), no callback is triggered for KVM on page
-	 * migration.  Until guest_memfd supports page migration, prevent page
-	 * migration.
-	 * TODO: Once guest_memfd introduces callback on page migration,
-	 * implement it and remove get_page/put_page().
-	 */
-	get_page(page);
-
 	/*
 	 * Read 'pre_fault_allowed' before 'kvm_tdx->state'; see matching
 	 * barrier in tdx_td_finalize().
 	 */
 	smp_rmb();
 	if (likely(kvm_tdx->state == TD_STATE_RUNNABLE))
-		return tdx_mem_page_aug(kvm, gfn, level, page);
+		return tdx_mem_page_aug(kvm, gfn, level, pfn);
 
 	return tdx_mem_page_record_premap_cnt(kvm, gfn, level, pfn);
 }
@@ -1712,7 +1694,6 @@ static int tdx_sept_drop_private_spte(struct kvm *kvm, gfn_t gfn,
 		return -EIO;
 	}
 	tdx_quirk_reset_page(page);
-	tdx_unpin(kvm, page);
 	return 0;
 }
 
@@ -1792,7 +1773,6 @@ static int tdx_sept_zap_private_spte(struct kvm *kvm, gfn_t gfn,
 	if (tdx_is_sept_zap_err_due_to_premap(kvm_tdx, err, entry, level) &&
 	    !KVM_BUG_ON(!atomic64_read(&kvm_tdx->nr_premapped), kvm)) {
 		atomic64_dec(&kvm_tdx->nr_premapped);
-		tdx_unpin(kvm, page);
 		return 0;
 	}

---

## [10] Sean Christopherson — 2025-10-30
*Subject: [PATCH v4 09/28] KVM: TDX: Return -EIO, not -EINVAL, on a
 KVM_BUG_ON() condition*

Return -EIO when a KVM_BUG_ON() is tripped, as KVM's ABI is to return -EIO
when a VM has been killed due to a KVM bug, not -EINVAL.  Note, many (all?)
of the affected paths never propagate the error code to userspace, i.e.
this is about internal consistency more than anything else.

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Reviewed-by: Ira Weiny <ira.weiny@intel.com>
Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/vmx/tdx.c | 12 ++++++------
 1 file changed, 6 insertions(+), 6 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index c3bae6b96dc4..c242d73b6a7b 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1621,7 +1621,7 @@ static int tdx_mem_page_record_premap_cnt(struct kvm *kvm, gfn_t gfn,
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
 
 	if (KVM_BUG_ON(kvm->arch.pre_fault_allowed, kvm))
-		return -EINVAL;
+		return -EIO;
 
 	/* nr_premapped will be decreased when tdh_mem_page_add() is called. */
 	atomic64_inc(&kvm_tdx->nr_premapped);
@@ -1635,7 +1635,7 @@ static int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn,
 
 	/* TODO: handle large pages. */
 	if (KVM_BUG_ON(level != PG_LEVEL_4K, kvm))
-		return -EINVAL;
+		return -EIO;
 
 	/*
 	 * Read 'pre_fault_allowed' before 'kvm_tdx->state'; see matching
@@ -1658,10 +1658,10 @@ static int tdx_sept_drop_private_spte(struct kvm *kvm, gfn_t gfn,
 
 	/* TODO: handle large pages. */
 	if (KVM_BUG_ON(level != PG_LEVEL_4K, kvm))
-		return -EINVAL;
+		return -EIO;
 
 	if (KVM_BUG_ON(!is_hkid_assigned(kvm_tdx), kvm))
-		return -EINVAL;
+		return -EIO;
 
 	/*
 	 * When zapping private page, write lock is held. So no race condition
@@ -1846,7 +1846,7 @@ static int tdx_sept_free_private_spt(struct kvm *kvm, gfn_t gfn,
 	 * and slot move/deletion.
 	 */
 	if (KVM_BUG_ON(is_hkid_assigned(kvm_tdx), kvm))
-		return -EINVAL;
+		return -EIO;
 
 	/*
 	 * The HKID assigned to this TD was already freed and cache was
@@ -1867,7 +1867,7 @@ static int tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
 	 * there can't be anything populated in the private EPT.
 	 */
 	if (KVM_BUG_ON(!is_hkid_assigned(to_kvm_tdx(kvm)), kvm))
-		return -EINVAL;
+		return -EIO;
 
 	ret = tdx_sept_zap_private_spte(kvm, gfn, level, page);
 	if (ret <= 0)

---

## [11] Sean Christopherson — 2025-10-30
*Subject: [PATCH v4 10/28] KVM: TDX: Fold tdx_sept_drop_private_spte() into tdx_sept_remove_private_spte()*

Fold tdx_sept_drop_private_spte() into tdx_sept_remove_private_spte() as a
step towards having "remove" be the only and only function that deals with
removing/zapping/dropping a SPTE, e.g. to avoid having to differentiate
between "zap", "drop", and "remove".  Eliminating the "drop" helper also
gets rid of what is effectively dead code due to redundant checks, e.g. on
an HKID being assigned.

No functional change intended.

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/vmx/tdx.c | 90 +++++++++++++++++++-----------------------
 1 file changed, 40 insertions(+), 50 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index c242d73b6a7b..abea9b3d08cf 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1648,55 +1648,6 @@ static int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn,
 	return tdx_mem_page_record_premap_cnt(kvm, gfn, level, pfn);
 }
 
-static int tdx_sept_drop_private_spte(struct kvm *kvm, gfn_t gfn,
-				      enum pg_level level, struct page *page)
-{
-	int tdx_level = pg_level_to_tdx_sept_level(level);
-	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
-	gpa_t gpa = gfn_to_gpa(gfn);
-	u64 err, entry, level_state;
-
-	/* TODO: handle large pages. */
-	if (KVM_BUG_ON(level != PG_LEVEL_4K, kvm))
-		return -EIO;
-
-	if (KVM_BUG_ON(!is_hkid_assigned(kvm_tdx), kvm))
-		return -EIO;
-
-	/*
-	 * When zapping private page, write lock is held. So no race condition
-	 * with other vcpu sept operation.
-	 * Race with TDH.VP.ENTER due to (0-step mitigation) and Guest TDCALLs.
-	 */
-	err = tdh_mem_page_remove(&kvm_tdx->td, gpa, tdx_level, &entry,
-				  &level_state);
-
-	if (unlikely(tdx_operand_busy(err))) {
-		/*
-		 * The second retry is expected to succeed after kicking off all
-		 * other vCPUs and prevent them from invoking TDH.VP.ENTER.
-		 */
-		tdx_no_vcpus_enter_start(kvm);
-		err = tdh_mem_page_remove(&kvm_tdx->td, gpa, tdx_level, &entry,
-					  &level_state);
-		tdx_no_vcpus_enter_stop(kvm);
-	}
-
-	if (KVM_BUG_ON(err, kvm)) {
-		pr_tdx_error_2(TDH_MEM_PAGE_REMOVE, err, entry, level_state);
-		return -EIO;
-	}
-
-	err = tdh_phymem_page_wbinvd_hkid((u16)kvm_tdx->hkid, page);
-
-	if (KVM_BUG_ON(err, kvm)) {
-		pr_tdx_error(TDH_PHYMEM_PAGE_WBINVD, err);
-		return -EIO;
-	}
-	tdx_quirk_reset_page(page);
-	return 0;
-}
-
 static int tdx_sept_link_private_spt(struct kvm *kvm, gfn_t gfn,
 				     enum pg_level level, void *private_spt)
 {
@@ -1858,7 +1809,11 @@ static int tdx_sept_free_private_spt(struct kvm *kvm, gfn_t gfn,
 static int tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
 					enum pg_level level, kvm_pfn_t pfn)
 {
+	int tdx_level = pg_level_to_tdx_sept_level(level);
+	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
 	struct page *page = pfn_to_page(pfn);
+	gpa_t gpa = gfn_to_gpa(gfn);
+	u64 err, entry, level_state;
 	int ret;
 
 	/*
@@ -1869,6 +1824,10 @@ static int tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
 	if (KVM_BUG_ON(!is_hkid_assigned(to_kvm_tdx(kvm)), kvm))
 		return -EIO;
 
+	/* TODO: handle large pages. */
+	if (KVM_BUG_ON(level != PG_LEVEL_4K, kvm))
+		return -EIO;
+
 	ret = tdx_sept_zap_private_spte(kvm, gfn, level, page);
 	if (ret <= 0)
 		return ret;
@@ -1879,7 +1838,38 @@ static int tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
 	 */
 	tdx_track(kvm);
 
-	return tdx_sept_drop_private_spte(kvm, gfn, level, page);
+	/*
+	 * When zapping private page, write lock is held. So no race condition
+	 * with other vcpu sept operation.
+	 * Race with TDH.VP.ENTER due to (0-step mitigation) and Guest TDCALLs.
+	 */
+	err = tdh_mem_page_remove(&kvm_tdx->td, gpa, tdx_level, &entry,
+				  &level_state);
+
+	if (unlikely(tdx_operand_busy(err))) {
+		/*
+		 * The second retry is expected to succeed after kicking off all
+		 * other vCPUs and prevent them from invoking TDH.VP.ENTER.
+		 */
+		tdx_no_vcpus_enter_start(kvm);
+		err = tdh_mem_page_remove(&kvm_tdx->td, gpa, tdx_level, &entry,
+					  &level_state);
+		tdx_no_vcpus_enter_stop(kvm);
+	}
+
+	if (KVM_BUG_ON(err, kvm)) {
+		pr_tdx_error_2(TDH_MEM_PAGE_REMOVE, err, entry, level_state);
+		return -EIO;
+	}
+
+	err = tdh_phymem_page_wbinvd_hkid((u16)kvm_tdx->hkid, page);
+	if (KVM_BUG_ON(err, kvm)) {
+		pr_tdx_error(TDH_PHYMEM_PAGE_WBINVD, err);
+		return -EIO;
+	}
+
+	tdx_quirk_reset_page(page);
+	return 0;
 }
 
 void tdx_deliver_interrupt(struct kvm_lapic *apic, int delivery_mode,

---

## [12] Sean Christopherson — 2025-10-30
*Subject: [PATCH v4 11/28] KVM: x86/mmu: Drop the return code from kvm_x86_ops.remove_external_spte()*

Drop the return code from kvm_x86_ops.remove_external_spte(), a.k.a.
tdx_sept_remove_private_spte(), as KVM simply does a KVM_BUG_ON() failure,
and that KVM_BUG_ON() is redundant since all error paths in TDX also do a
KVM_BUG_ON().

Opportunistically pass the spte instead of the pfn, as the API is clearly
about removing an spte.

Suggested-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/kvm_host.h |  4 ++--
 arch/x86/kvm/mmu/tdp_mmu.c      |  8 ++------
 arch/x86/kvm/vmx/tdx.c          | 17 ++++++++---------
 3 files changed, 12 insertions(+), 17 deletions(-)

diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h
index 48598d017d6f..b5867f8fe6ce 100644
--- a/arch/x86/include/asm/kvm_host.h
+++ b/arch/x86/include/asm/kvm_host.h
@@ -1855,8 +1855,8 @@ struct kvm_x86_ops {
 				 void *external_spt);
 
 	/* Update external page table from spte getting removed, and flush TLB. */
-	int (*remove_external_spte)(struct kvm *kvm, gfn_t gfn, enum pg_level level,
-				    kvm_pfn_t pfn_for_gfn);
+	void (*remove_external_spte)(struct kvm *kvm, gfn_t gfn, enum pg_level level,
+				     u64 mirror_spte);
 
 	bool (*has_wbinvd_exit)(void);
 
diff --git a/arch/x86/kvm/mmu/tdp_mmu.c b/arch/x86/kvm/mmu/tdp_mmu.c
index e735d2f8367b..e1a96e9ea1bb 100644
--- a/arch/x86/kvm/mmu/tdp_mmu.c
+++ b/arch/x86/kvm/mmu/tdp_mmu.c
@@ -362,9 +362,6 @@ static void tdp_mmu_unlink_sp(struct kvm *kvm, struct kvm_mmu_page *sp)
 static void remove_external_spte(struct kvm *kvm, gfn_t gfn, u64 old_spte,
 				 int level)
 {
-	kvm_pfn_t old_pfn = spte_to_pfn(old_spte);
-	int ret;
-
 	/*
 	 * External (TDX) SPTEs are limited to PG_LEVEL_4K, and external
 	 * PTs are removed in a special order, involving free_external_spt().
@@ -377,9 +374,8 @@ static void remove_external_spte(struct kvm *kvm, gfn_t gfn, u64 old_spte,
 
 	/* Zapping leaf spte is allowed only when write lock is held. */
 	lockdep_assert_held_write(&kvm->mmu_lock);
-	/* Because write lock is held, operation should success. */
-	ret = kvm_x86_call(remove_external_spte)(kvm, gfn, level, old_pfn);
-	KVM_BUG_ON(ret, kvm);
+
+	kvm_x86_call(remove_external_spte)(kvm, gfn, level, old_spte);
 }
 
 /**
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index abea9b3d08cf..7ab67ad83677 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1806,12 +1806,12 @@ static int tdx_sept_free_private_spt(struct kvm *kvm, gfn_t gfn,
 	return tdx_reclaim_page(virt_to_page(private_spt));
 }
 
-static int tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
-					enum pg_level level, kvm_pfn_t pfn)
+static void tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
+					 enum pg_level level, u64 mirror_spte)
 {
+	struct page *page = pfn_to_page(spte_to_pfn(mirror_spte));
 	int tdx_level = pg_level_to_tdx_sept_level(level);
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
-	struct page *page = pfn_to_page(pfn);
 	gpa_t gpa = gfn_to_gpa(gfn);
 	u64 err, entry, level_state;
 	int ret;
@@ -1822,15 +1822,15 @@ static int tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
 	 * there can't be anything populated in the private EPT.
 	 */
 	if (KVM_BUG_ON(!is_hkid_assigned(to_kvm_tdx(kvm)), kvm))
-		return -EIO;
+		return;
 
 	/* TODO: handle large pages. */
 	if (KVM_BUG_ON(level != PG_LEVEL_4K, kvm))
-		return -EIO;
+		return;
 
 	ret = tdx_sept_zap_private_spte(kvm, gfn, level, page);
 	if (ret <= 0)
-		return ret;
+		return;
 
 	/*
 	 * TDX requires TLB tracking before dropping private page.  Do
@@ -1859,17 +1859,16 @@ static int tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
 
 	if (KVM_BUG_ON(err, kvm)) {
 		pr_tdx_error_2(TDH_MEM_PAGE_REMOVE, err, entry, level_state);
-		return -EIO;
+		return;
 	}
 
 	err = tdh_phymem_page_wbinvd_hkid((u16)kvm_tdx->hkid, page);
 	if (KVM_BUG_ON(err, kvm)) {
 		pr_tdx_error(TDH_PHYMEM_PAGE_WBINVD, err);
-		return -EIO;
+		return;
 	}
 
 	tdx_quirk_reset_page(page);
-	return 0;
 }
 
 void tdx_deliver_interrupt(struct kvm_lapic *apic, int delivery_mode,

---

## [13] Sean Christopherson — 2025-10-30
*Subject: [PATCH v4 12/28] KVM: TDX: WARN if mirror SPTE doesn't have full RWX
 when creating S-EPT mapping*

Pass in the mirror_spte to kvm_x86_ops.set_external_spte() to provide
symmetry with .remove_external_spte(), and assert in TDX that the mirror
SPTE is shadow-present with full RWX permissions (the TDX-Module doesn't
allow the hypervisor to control protections).

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/kvm_host.h | 2 +-
 arch/x86/kvm/mmu/tdp_mmu.c      | 3 +--
 arch/x86/kvm/vmx/tdx.c          | 6 +++++-
 3 files changed, 7 insertions(+), 4 deletions(-)

diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h
index b5867f8fe6ce..87a5f5100b1d 100644
--- a/arch/x86/include/asm/kvm_host.h
+++ b/arch/x86/include/asm/kvm_host.h
@@ -1848,7 +1848,7 @@ struct kvm_x86_ops {
 				void *external_spt);
 	/* Update the external page table from spte getting set. */
 	int (*set_external_spte)(struct kvm *kvm, gfn_t gfn, enum pg_level level,
-				 kvm_pfn_t pfn_for_gfn);
+				 u64 mirror_spte);
 
 	/* Update external page tables for page table about to be freed. */
 	int (*free_external_spt)(struct kvm *kvm, gfn_t gfn, enum pg_level level,
diff --git a/arch/x86/kvm/mmu/tdp_mmu.c b/arch/x86/kvm/mmu/tdp_mmu.c
index e1a96e9ea1bb..9c26038f6b77 100644
--- a/arch/x86/kvm/mmu/tdp_mmu.c
+++ b/arch/x86/kvm/mmu/tdp_mmu.c
@@ -515,7 +515,6 @@ static int __must_check set_external_spte_present(struct kvm *kvm, tdp_ptep_t sp
 	bool was_present = is_shadow_present_pte(old_spte);
 	bool is_present = is_shadow_present_pte(new_spte);
 	bool is_leaf = is_present && is_last_spte(new_spte, level);
-	kvm_pfn_t new_pfn = spte_to_pfn(new_spte);
 	int ret = 0;
 
 	KVM_BUG_ON(was_present, kvm);
@@ -534,7 +533,7 @@ static int __must_check set_external_spte_present(struct kvm *kvm, tdp_ptep_t sp
 	 * external page table, or leaf.
 	 */
 	if (is_leaf) {
-		ret = kvm_x86_call(set_external_spte)(kvm, gfn, level, new_pfn);
+		ret = kvm_x86_call(set_external_spte)(kvm, gfn, level, new_spte);
 	} else {
 		void *external_spt = get_external_spt(gfn, new_spte, level);
 
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 7ab67ad83677..658e0407eb21 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1629,14 +1629,18 @@ static int tdx_mem_page_record_premap_cnt(struct kvm *kvm, gfn_t gfn,
 }
 
 static int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn,
-				     enum pg_level level, kvm_pfn_t pfn)
+				     enum pg_level level, u64 mirror_spte)
 {
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
+	kvm_pfn_t pfn = spte_to_pfn(mirror_spte);
 
 	/* TODO: handle large pages. */
 	if (KVM_BUG_ON(level != PG_LEVEL_4K, kvm))
 		return -EIO;
 
+	WARN_ON_ONCE(!is_shadow_present_pte(mirror_spte) ||
+		     (mirror_spte & VMX_EPT_RWX_MASK) != VMX_EPT_RWX_MASK);
+
 	/*
 	 * Read 'pre_fault_allowed' before 'kvm_tdx->state'; see matching
 	 * barrier in tdx_td_finalize().

---

## [14] Sean Christopherson — 2025-10-30
*Subject: [PATCH v4 13/28] KVM: TDX: Avoid a double-KVM_BUG_ON() in tdx_sept_zap_private_spte()*

Return -EIO immediately from tdx_sept_zap_private_spte() if the number of
to-be-added pages underflows, so that the following "KVM_BUG_ON(err, kvm)"
isn't also triggered.  Isolating the check from the "is premap error"
if-statement will also allow adding a lockdep assertion that premap errors
are encountered if and only if slots_lock is held.

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/vmx/tdx.c | 6 ++++--
 1 file changed, 4 insertions(+), 2 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 658e0407eb21..db64a9e8c6a5 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1725,8 +1725,10 @@ static int tdx_sept_zap_private_spte(struct kvm *kvm, gfn_t gfn,
 		err = tdh_mem_range_block(&kvm_tdx->td, gpa, tdx_level, &entry, &level_state);
 		tdx_no_vcpus_enter_stop(kvm);
 	}
-	if (tdx_is_sept_zap_err_due_to_premap(kvm_tdx, err, entry, level) &&
-	    !KVM_BUG_ON(!atomic64_read(&kvm_tdx->nr_premapped), kvm)) {
+	if (tdx_is_sept_zap_err_due_to_premap(kvm_tdx, err, entry, level)) {
+		if (KVM_BUG_ON(!atomic64_read(&kvm_tdx->nr_premapped), kvm))
+			return -EIO;
+
 		atomic64_dec(&kvm_tdx->nr_premapped);
 		return 0;
 	}

---

## [15] Sean Christopherson — 2025-10-30
*Subject: [PATCH v4 14/28] KVM: TDX: Use atomic64_dec_return() instead of a
 poor equivalent*

Use atomic64_dec_return() when decrementing the number of "pre-mapped"
S-EPT pages to ensure that the count can't go negative without KVM
noticing.  In theory, checking for '0' and then decrementing in a separate
operation could miss a 0=>-1 transition.  In practice, such a condition is
impossible because nr_premapped is protected by slots_lock, i.e. doesn't
actually need to be an atomic (that wart will be addressed shortly).

Don't bother trying to keep the count non-negative, as the KVM_BUG_ON()
ensures the VM is dead, i.e. there's no point in trying to limp along.

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Reviewed-by: Ira Weiny <ira.weiny@intel.com>
Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/vmx/tdx.c | 6 ++----
 1 file changed, 2 insertions(+), 4 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index db64a9e8c6a5..99db19e02cf1 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1726,10 +1726,9 @@ static int tdx_sept_zap_private_spte(struct kvm *kvm, gfn_t gfn,
 		tdx_no_vcpus_enter_stop(kvm);
 	}
 	if (tdx_is_sept_zap_err_due_to_premap(kvm_tdx, err, entry, level)) {
-		if (KVM_BUG_ON(!atomic64_read(&kvm_tdx->nr_premapped), kvm))
+		if (KVM_BUG_ON(atomic64_dec_return(&kvm_tdx->nr_premapped) < 0, kvm))
 			return -EIO;
 
-		atomic64_dec(&kvm_tdx->nr_premapped);
 		return 0;
 	}
 
@@ -3161,8 +3160,7 @@ static int tdx_gmem_post_populate(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
 		goto out;
 	}
 
-	if (!KVM_BUG_ON(!atomic64_read(&kvm_tdx->nr_premapped), kvm))
-		atomic64_dec(&kvm_tdx->nr_premapped);
+	KVM_BUG_ON(atomic64_dec_return(&kvm_tdx->nr_premapped) < 0, kvm);
 
 	if (arg->flags & KVM_TDX_MEASURE_MEMORY_REGION) {
 		for (i = 0; i < PAGE_SIZE; i += TDX_EXTENDMR_CHUNKSIZE) {

---

## [16] Sean Christopherson — 2025-10-30
*Subject: [PATCH v4 15/28] KVM: TDX: Fold tdx_mem_page_record_premap_cnt() into
 its sole caller*

Fold tdx_mem_page_record_premap_cnt() into tdx_sept_set_private_spte() as
providing a one-off helper for effectively three lines of code is at best a
wash, and splitting the code makes the comment for smp_rmb()  _extremely_
confusing as the comment talks about reading kvm->arch.pre_fault_allowed
before kvm_tdx->state, but the immediately visible code does the exact
opposite.

Opportunistically rewrite the comments to more explicitly explain who is
checking what, as well as _why_ the ordering matters.

No functional change intended.

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/vmx/tdx.c | 49 ++++++++++++++++++------------------------
 1 file changed, 21 insertions(+), 28 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 99db19e02cf1..a30471c972ba 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1605,29 +1605,6 @@ static int tdx_mem_page_aug(struct kvm *kvm, gfn_t gfn,
 	return 0;
 }
 
-/*
- * KVM_TDX_INIT_MEM_REGION calls kvm_gmem_populate() to map guest pages; the
- * callback tdx_gmem_post_populate() then maps pages into private memory.
- * through the a seamcall TDH.MEM.PAGE.ADD().  The SEAMCALL also requires the
- * private EPT structures for the page to have been built before, which is
- * done via kvm_tdp_map_page(). nr_premapped counts the number of pages that
- * were added to the EPT structures but not added with TDH.MEM.PAGE.ADD().
- * The counter has to be zero on KVM_TDX_FINALIZE_VM, to ensure that there
- * are no half-initialized shared EPT pages.
- */
-static int tdx_mem_page_record_premap_cnt(struct kvm *kvm, gfn_t gfn,
-					  enum pg_level level, kvm_pfn_t pfn)
-{
-	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
-
-	if (KVM_BUG_ON(kvm->arch.pre_fault_allowed, kvm))
-		return -EIO;
-
-	/* nr_premapped will be decreased when tdh_mem_page_add() is called. */
-	atomic64_inc(&kvm_tdx->nr_premapped);
-	return 0;
-}
-
 static int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn,
 				     enum pg_level level, u64 mirror_spte)
 {
@@ -1642,14 +1619,30 @@ static int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn,
 		     (mirror_spte & VMX_EPT_RWX_MASK) != VMX_EPT_RWX_MASK);
 
 	/*
-	 * Read 'pre_fault_allowed' before 'kvm_tdx->state'; see matching
-	 * barrier in tdx_td_finalize().
+	 * Ensure pre_fault_allowed is read by kvm_arch_vcpu_pre_fault_memory()
+	 * before kvm_tdx->state.  Userspace must not be allowed to pre-fault
+	 * arbitrary memory until the initial memory image is finalized.  Pairs
+	 * with the smp_wmb() in tdx_td_finalize().
 	 */
 	smp_rmb();
-	if (likely(kvm_tdx->state == TD_STATE_RUNNABLE))
-		return tdx_mem_page_aug(kvm, gfn, level, pfn);
 
-	return tdx_mem_page_record_premap_cnt(kvm, gfn, level, pfn);
+	/*
+	 * If the TD isn't finalized/runnable, then userspace is initializing
+	 * the VM image via KVM_TDX_INIT_MEM_REGION.  Increment the number of
+	 * pages that need to be mapped and initialized via TDH.MEM.PAGE.ADD.
+	 * KVM_TDX_FINALIZE_VM checks the counter to ensure all pre-mapped
+	 * pages have been added to the image, to prevent running the TD with a
+	 * valid mapping in the mirror EPT, but not in the S-EPT.
+	 */
+	if (unlikely(kvm_tdx->state != TD_STATE_RUNNABLE)) {
+		if (KVM_BUG_ON(kvm->arch.pre_fault_allowed, kvm))
+			return -EIO;
+
+		atomic64_inc(&kvm_tdx->nr_premapped);
+		return 0;
+	}
+
+	return tdx_mem_page_aug(kvm, gfn, level, pfn);
 }
 
 static int tdx_sept_link_private_spt(struct kvm *kvm, gfn_t gfn,

---

## [17] Sean Christopherson — 2025-10-30
*Subject: [PATCH v4 16/28] KVM: TDX: ADD pages to the TD image while populating
 mirror EPT entries*

When populating the initial memory image for a TDX guest, ADD pages to the
TD as part of establishing the mappings in the mirror EPT, as opposed to
creating the mappings and then doing ADD after the fact.  Doing ADD in the
S-EPT callbacks eliminates the need to track "premapped" pages, as the
mirror EPT (M-EPT) and S-EPT are always synchronized, e.g. if ADD fails,
KVM reverts to the previous M-EPT entry (guaranteed to be !PRESENT).

Eliminating the hole where the M-EPT can have a mapping that doesn't exist
in the S-EPT in turn obviates the need to handle errors that are unique to
encountering a missing S-EPT entry (see tdx_is_sept_zap_err_due_to_premap()).

Keeping the M-EPT and S-EPT synchronized also eliminates the need to check
for unconsumed "premap" entries during tdx_td_finalize(), as there simply
can't be any such entries.  Dropping that check in particular reduces the
overall cognitive load, as the management of nr_premapped with respect
to removal of S-EPT is _very_ subtle.  E.g. successful removal of an S-EPT
entry after it completed ADD doesn't adjust nr_premapped, but it's not
clear why that's "ok" but having half-baked entries is not (it's not truly
"ok" in that removing pages from the image will likely prevent the guest
from booting, but from KVM's perspective it's "ok").

Doing ADD in the S-EPT path requires passing an argument via a scratch
field, but the current approach of tracking the number of "premapped"
pages effectively does the same.  And the "premapped" counter is much more
dangerous, as it doesn't have a singular lock to protect its usage, since
nr_premapped can be modified as soon as mmu_lock is dropped, at least in
theory.  I.e. nr_premapped is guarded by slots_lock, but only for "happy"
paths.

Note, this approach was used/tried at various points in TDX development,
but was ultimately discarded due to a desire to avoid stashing temporary
state in kvm_tdx.  But as above, KVM ended up with such state anyways,
and fully committing to using temporary state provides better access
rules (100% guarded by slots_lock), and makes several edge cases flat out
impossible.

Note #2, continue to extend the measurement outside of mmu_lock, as it's
a slow operation (typically 16 SEAMCALLs per page whose data is included
in the measurement), and doesn't *need* to be done under mmu_lock, e.g.
for consistency purposes.  However, MR.EXTEND isn't _that_ slow, e.g.
~1ms latency to measure a full page, so if it needs to be done under
mmu_lock in the future, e.g. because KVM gains a flow that can remove
S-EPT entries during KVM_TDX_INIT_MEM_REGION, then extending the
measurement can also be moved into the S-EPT mapping path (again, only if
absolutely necessary).  P.S. _If_ MR.EXTEND is moved into the S-EPT path,
take care not to return an error up the stack if TDH_MR_EXTEND fails, as
removing the M-EPT entry but not the S-EPT entry would result in
inconsistent state!

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/vmx/tdx.c | 106 ++++++++++++++---------------------------
 arch/x86/kvm/vmx/tdx.h |   8 +++-
 2 files changed, 43 insertions(+), 71 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index a30471c972ba..cfdf8d262756 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1583,6 +1583,32 @@ void tdx_load_mmu_pgd(struct kvm_vcpu *vcpu, hpa_t root_hpa, int pgd_level)
 	td_vmcs_write64(to_tdx(vcpu), SHARED_EPT_POINTER, root_hpa);
 }
 
+static int tdx_mem_page_add(struct kvm *kvm, gfn_t gfn, enum pg_level level,
+			    kvm_pfn_t pfn)
+{
+	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
+	u64 err, entry, level_state;
+	gpa_t gpa = gfn_to_gpa(gfn);
+
+	lockdep_assert_held(&kvm->slots_lock);
+
+	if (KVM_BUG_ON(kvm->arch.pre_fault_allowed, kvm) ||
+	    KVM_BUG_ON(!kvm_tdx->page_add_src, kvm))
+		return -EIO;
+
+	err = tdh_mem_page_add(&kvm_tdx->td, gpa, pfn_to_page(pfn),
+			       kvm_tdx->page_add_src, &entry, &level_state);
+	if (unlikely(tdx_operand_busy(err)))
+		return -EBUSY;
+
+	if (KVM_BUG_ON(err, kvm)) {
+		pr_tdx_error_2(TDH_MEM_PAGE_ADD, err, entry, level_state);
+		return -EIO;
+	}
+
+	return 0;
+}
+
 static int tdx_mem_page_aug(struct kvm *kvm, gfn_t gfn,
 			    enum pg_level level, kvm_pfn_t pfn)
 {
@@ -1628,19 +1654,10 @@ static int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn,
 
 	/*
 	 * If the TD isn't finalized/runnable, then userspace is initializing
-	 * the VM image via KVM_TDX_INIT_MEM_REGION.  Increment the number of
-	 * pages that need to be mapped and initialized via TDH.MEM.PAGE.ADD.
-	 * KVM_TDX_FINALIZE_VM checks the counter to ensure all pre-mapped
-	 * pages have been added to the image, to prevent running the TD with a
-	 * valid mapping in the mirror EPT, but not in the S-EPT.
+	 * the VM image via KVM_TDX_INIT_MEM_REGION; ADD the page to the TD.
 	 */
-	if (unlikely(kvm_tdx->state != TD_STATE_RUNNABLE)) {
-		if (KVM_BUG_ON(kvm->arch.pre_fault_allowed, kvm))
-			return -EIO;
-
-		atomic64_inc(&kvm_tdx->nr_premapped);
-		return 0;
-	}
+	if (unlikely(kvm_tdx->state != TD_STATE_RUNNABLE))
+		return tdx_mem_page_add(kvm, gfn, level, pfn);
 
 	return tdx_mem_page_aug(kvm, gfn, level, pfn);
 }
@@ -1666,39 +1683,6 @@ static int tdx_sept_link_private_spt(struct kvm *kvm, gfn_t gfn,
 	return 0;
 }
 
-/*
- * Check if the error returned from a SEPT zap SEAMCALL is due to that a page is
- * mapped by KVM_TDX_INIT_MEM_REGION without tdh_mem_page_add() being called
- * successfully.
- *
- * Since tdh_mem_sept_add() must have been invoked successfully before a
- * non-leaf entry present in the mirrored page table, the SEPT ZAP related
- * SEAMCALLs should not encounter err TDX_EPT_WALK_FAILED. They should instead
- * find TDX_EPT_ENTRY_STATE_INCORRECT due to an empty leaf entry found in the
- * SEPT.
- *
- * Further check if the returned entry from SEPT walking is with RWX permissions
- * to filter out anything unexpected.
- *
- * Note: @level is pg_level, not the tdx_level. The tdx_level extracted from
- * level_state returned from a SEAMCALL error is the same as that passed into
- * the SEAMCALL.
- */
-static int tdx_is_sept_zap_err_due_to_premap(struct kvm_tdx *kvm_tdx, u64 err,
-					     u64 entry, int level)
-{
-	if (!err || kvm_tdx->state == TD_STATE_RUNNABLE)
-		return false;
-
-	if (err != (TDX_EPT_ENTRY_STATE_INCORRECT | TDX_OPERAND_ID_RCX))
-		return false;
-
-	if ((is_last_spte(entry, level) && (entry & VMX_EPT_RWX_MASK)))
-		return false;
-
-	return true;
-}
-
 static int tdx_sept_zap_private_spte(struct kvm *kvm, gfn_t gfn,
 				     enum pg_level level, struct page *page)
 {
@@ -1718,12 +1702,6 @@ static int tdx_sept_zap_private_spte(struct kvm *kvm, gfn_t gfn,
 		err = tdh_mem_range_block(&kvm_tdx->td, gpa, tdx_level, &entry, &level_state);
 		tdx_no_vcpus_enter_stop(kvm);
 	}
-	if (tdx_is_sept_zap_err_due_to_premap(kvm_tdx, err, entry, level)) {
-		if (KVM_BUG_ON(atomic64_dec_return(&kvm_tdx->nr_premapped) < 0, kvm))
-			return -EIO;
-
-		return 0;
-	}
 
 	if (KVM_BUG_ON(err, kvm)) {
 		pr_tdx_error_2(TDH_MEM_RANGE_BLOCK, err, entry, level_state);
@@ -2829,12 +2807,6 @@ static int tdx_td_finalize(struct kvm *kvm, struct kvm_tdx_cmd *cmd)
 
 	if (!is_hkid_assigned(kvm_tdx) || kvm_tdx->state == TD_STATE_RUNNABLE)
 		return -EINVAL;
-	/*
-	 * Pages are pending for KVM_TDX_INIT_MEM_REGION to issue
-	 * TDH.MEM.PAGE.ADD().
-	 */
-	if (atomic64_read(&kvm_tdx->nr_premapped))
-		return -EINVAL;
 
 	cmd->hw_error = tdh_mr_finalize(&kvm_tdx->td);
 	if (tdx_operand_busy(cmd->hw_error))
@@ -3131,6 +3103,9 @@ static int tdx_gmem_post_populate(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
 	struct page *src_page;
 	int ret, i;
 
+	if (KVM_BUG_ON(kvm_tdx->page_add_src, kvm))
+		return -EIO;
+
 	/*
 	 * Get the source page if it has been faulted in. Return failure if the
 	 * source page has been swapped out or unmapped in primary memory.
@@ -3141,19 +3116,14 @@ static int tdx_gmem_post_populate(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
 	if (ret != 1)
 		return -ENOMEM;
 
+	kvm_tdx->page_add_src = src_page;
 	ret = kvm_tdp_mmu_map_private_pfn(arg->vcpu, gfn, pfn);
-	if (ret < 0)
-		goto out;
+	kvm_tdx->page_add_src = NULL;
 
-	ret = 0;
-	err = tdh_mem_page_add(&kvm_tdx->td, gpa, pfn_to_page(pfn),
-			       src_page, &entry, &level_state);
-	if (err) {
-		ret = unlikely(tdx_operand_busy(err)) ? -EBUSY : -EIO;
-		goto out;
-	}
+	put_page(src_page);
 
-	KVM_BUG_ON(atomic64_dec_return(&kvm_tdx->nr_premapped) < 0, kvm);
+	if (ret)
+		return ret;
 
 	if (arg->flags & KVM_TDX_MEASURE_MEMORY_REGION) {
 		for (i = 0; i < PAGE_SIZE; i += TDX_EXTENDMR_CHUNKSIZE) {
@@ -3166,8 +3136,6 @@ static int tdx_gmem_post_populate(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
 		}
 	}
 
-out:
-	put_page(src_page);
 	return ret;
 }
 
diff --git a/arch/x86/kvm/vmx/tdx.h b/arch/x86/kvm/vmx/tdx.h
index ca39a9391db1..1b00adbbaf77 100644
--- a/arch/x86/kvm/vmx/tdx.h
+++ b/arch/x86/kvm/vmx/tdx.h
@@ -36,8 +36,12 @@ struct kvm_tdx {
 
 	struct tdx_td td;
 
-	/* For KVM_TDX_INIT_MEM_REGION. */
-	atomic64_t nr_premapped;
+	/*
+	 * Scratch pointer used to pass the source page to tdx_mem_page_add.
+	 * Protected by slots_lock, and non-NULL only when mapping a private
+	 * pfn via tdx_gmem_post_populate().
+	 */
+	struct page *page_add_src;
 
 	/*
 	 * Prevent vCPUs from TD entry to ensure SEPT zap related SEAMCALLs do

---

## [18] Sean Christopherson — 2025-10-30
*Subject: [PATCH v4 17/28] KVM: TDX: Fold tdx_sept_zap_private_spte() into tdx_sept_remove_private_spte()*

Do TDH_MEM_RANGE_BLOCK directly in tdx_sept_remove_private_spte() instead
of using a one-off helper now that the nr_premapped tracking is gone.

Opportunistically drop the WARN on hugepages, which was dead code (see the
KVM_BUG_ON() in tdx_sept_remove_private_spte()).

No functional change intended.

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/vmx/tdx.c | 41 +++++++++++------------------------------
 1 file changed, 11 insertions(+), 30 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index cfdf8d262756..260b569309cf 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1683,33 +1683,6 @@ static int tdx_sept_link_private_spt(struct kvm *kvm, gfn_t gfn,
 	return 0;
 }
 
-static int tdx_sept_zap_private_spte(struct kvm *kvm, gfn_t gfn,
-				     enum pg_level level, struct page *page)
-{
-	int tdx_level = pg_level_to_tdx_sept_level(level);
-	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
-	gpa_t gpa = gfn_to_gpa(gfn) & KVM_HPAGE_MASK(level);
-	u64 err, entry, level_state;
-
-	/* For now large page isn't supported yet. */
-	WARN_ON_ONCE(level != PG_LEVEL_4K);
-
-	err = tdh_mem_range_block(&kvm_tdx->td, gpa, tdx_level, &entry, &level_state);
-
-	if (unlikely(tdx_operand_busy(err))) {
-		/* After no vCPUs enter, the second retry is expected to succeed */
-		tdx_no_vcpus_enter_start(kvm);
-		err = tdh_mem_range_block(&kvm_tdx->td, gpa, tdx_level, &entry, &level_state);
-		tdx_no_vcpus_enter_stop(kvm);
-	}
-
-	if (KVM_BUG_ON(err, kvm)) {
-		pr_tdx_error_2(TDH_MEM_RANGE_BLOCK, err, entry, level_state);
-		return -EIO;
-	}
-	return 1;
-}
-
 /*
  * Ensure shared and private EPTs to be flushed on all vCPUs.
  * tdh_mem_track() is the only caller that increases TD epoch. An increase in
@@ -1790,7 +1763,6 @@ static void tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
 	gpa_t gpa = gfn_to_gpa(gfn);
 	u64 err, entry, level_state;
-	int ret;
 
 	/*
 	 * HKID is released after all private pages have been removed, and set
@@ -1804,9 +1776,18 @@ static void tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
 	if (KVM_BUG_ON(level != PG_LEVEL_4K, kvm))
 		return;
 
-	ret = tdx_sept_zap_private_spte(kvm, gfn, level, page);
-	if (ret <= 0)
+	err = tdh_mem_range_block(&kvm_tdx->td, gpa, tdx_level, &entry, &level_state);
+	if (unlikely(tdx_operand_busy(err))) {
+		/* After no vCPUs enter, the second retry is expected to succeed */
+		tdx_no_vcpus_enter_start(kvm);
+		err = tdh_mem_range_block(&kvm_tdx->td, gpa, tdx_level, &entry, &level_state);
+		tdx_no_vcpus_enter_stop(kvm);
+	}
+
+	if (KVM_BUG_ON(err, kvm)) {
+		pr_tdx_error_2(TDH_MEM_RANGE_BLOCK, err, entry, level_state);
 		return;
+	}
 
 	/*
 	 * TDX requires TLB tracking before dropping private page.  Do

---

## [19] Sean Christopherson — 2025-10-30
*Subject: [PATCH v4 18/28] KVM: TDX: Combine KVM_BUG_ON + pr_tdx_error() into TDX_BUG_ON()*

Add TDX_BUG_ON() macros (with varying numbers of arguments) to deduplicate
the myriad flows that do KVM_BUG_ON()/WARN_ON_ONCE() followed by a call to
pr_tdx_error().  In addition to reducing boilerplate copy+paste code, this
also helps ensure that KVM provides consistent handling of SEAMCALL errors.

Opportunistically convert a handful of bare WARN_ON_ONCE() paths to the
equivalent of KVM_BUG_ON(), i.e. have them terminate the VM.  If a SEAMCALL
error is fatal enough to WARN on, it's fatal enough to terminate the TD.

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/vmx/tdx.c | 110 +++++++++++++++++------------------------
 1 file changed, 46 insertions(+), 64 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 260b569309cf..5e6f2d8b6014 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -24,20 +24,32 @@
 #undef pr_fmt
 #define pr_fmt(fmt) KBUILD_MODNAME ": " fmt
 
-#define pr_tdx_error(__fn, __err)	\
-	pr_err_ratelimited("SEAMCALL %s failed: 0x%llx\n", #__fn, __err)
+#define __TDX_BUG_ON(__err, __f, __kvm, __fmt, __args...)			\
+({										\
+	struct kvm *_kvm = (__kvm);						\
+	bool __ret = !!(__err);							\
+										\
+	if (WARN_ON_ONCE(__ret && (!_kvm || !_kvm->vm_bugged))) {		\
+		if (_kvm)							\
+			kvm_vm_bugged(_kvm);					\
+		pr_err_ratelimited("SEAMCALL " __f " failed: 0x%llx" __fmt "\n",\
+				   __err,  __args);				\
+	}									\
+	unlikely(__ret);							\
+})
 
-#define __pr_tdx_error_N(__fn_str, __err, __fmt, ...)		\
-	pr_err_ratelimited("SEAMCALL " __fn_str " failed: 0x%llx, " __fmt,  __err,  __VA_ARGS__)
+#define TDX_BUG_ON(__err, __fn, __kvm)				\
+	__TDX_BUG_ON(__err, #__fn, __kvm, "%s", "")
 
-#define pr_tdx_error_1(__fn, __err, __rcx)		\
-	__pr_tdx_error_N(#__fn, __err, "rcx 0x%llx\n", __rcx)
+#define TDX_BUG_ON_1(__err, __fn, __rcx, __kvm)			\
+	__TDX_BUG_ON(__err, #__fn, __kvm, ", rcx 0x%llx", __rcx)
 
-#define pr_tdx_error_2(__fn, __err, __rcx, __rdx)	\
-	__pr_tdx_error_N(#__fn, __err, "rcx 0x%llx, rdx 0x%llx\n", __rcx, __rdx)
+#define TDX_BUG_ON_2(__err, __fn, __rcx, __rdx, __kvm)		\
+	__TDX_BUG_ON(__err, #__fn, __kvm, ", rcx 0x%llx, rdx 0x%llx", __rcx, __rdx)
+
+#define TDX_BUG_ON_3(__err, __fn, __rcx, __rdx, __r8, __kvm)	\
+	__TDX_BUG_ON(__err, #__fn, __kvm, ", rcx 0x%llx, rdx 0x%llx, r8 0x%llx", __rcx, __rdx, __r8)
 
-#define pr_tdx_error_3(__fn, __err, __rcx, __rdx, __r8)	\
-	__pr_tdx_error_N(#__fn, __err, "rcx 0x%llx, rdx 0x%llx, r8 0x%llx\n", __rcx, __rdx, __r8)
 
 bool enable_tdx __ro_after_init;
 module_param_named(tdx, enable_tdx, bool, 0444);
@@ -313,10 +325,9 @@ static int __tdx_reclaim_page(struct page *page)
 	 * before the HKID is released and control pages have also been
 	 * released at this point, so there is no possibility of contention.
 	 */
-	if (WARN_ON_ONCE(err)) {
-		pr_tdx_error_3(TDH_PHYMEM_PAGE_RECLAIM, err, rcx, rdx, r8);
+	if (TDX_BUG_ON_3(err, TDH_PHYMEM_PAGE_RECLAIM, rcx, rdx, r8, NULL))
 		return -EIO;
-	}
+
 	return 0;
 }
 
@@ -404,8 +415,8 @@ static void tdx_flush_vp_on_cpu(struct kvm_vcpu *vcpu)
 		return;
 
 	smp_call_function_single(cpu, tdx_flush_vp, &arg, 1);
-	if (KVM_BUG_ON(arg.err, vcpu->kvm))
-		pr_tdx_error(TDH_VP_FLUSH, arg.err);
+
+	TDX_BUG_ON(arg.err, TDH_VP_FLUSH, vcpu->kvm);
 }
 
 void tdx_disable_virtualization_cpu(void)
@@ -464,8 +475,7 @@ static void smp_func_do_phymem_cache_wb(void *unused)
 	}
 
 out:
-	if (WARN_ON_ONCE(err))
-		pr_tdx_error(TDH_PHYMEM_CACHE_WB, err);
+	TDX_BUG_ON(err, TDH_PHYMEM_CACHE_WB, NULL);
 }
 
 void tdx_mmu_release_hkid(struct kvm *kvm)
@@ -504,8 +514,7 @@ void tdx_mmu_release_hkid(struct kvm *kvm)
 	err = tdh_mng_vpflushdone(&kvm_tdx->td);
 	if (err == TDX_FLUSHVP_NOT_DONE)
 		goto out;
-	if (KVM_BUG_ON(err, kvm)) {
-		pr_tdx_error(TDH_MNG_VPFLUSHDONE, err);
+	if (TDX_BUG_ON(err, TDH_MNG_VPFLUSHDONE, kvm)) {
 		pr_err("tdh_mng_vpflushdone() failed. HKID %d is leaked.\n",
 		       kvm_tdx->hkid);
 		goto out;
@@ -528,8 +537,7 @@ void tdx_mmu_release_hkid(struct kvm *kvm)
 	 * tdh_mng_key_freeid() will fail.
 	 */
 	err = tdh_mng_key_freeid(&kvm_tdx->td);
-	if (KVM_BUG_ON(err, kvm)) {
-		pr_tdx_error(TDH_MNG_KEY_FREEID, err);
+	if (TDX_BUG_ON(err, TDH_MNG_KEY_FREEID, kvm)) {
 		pr_err("tdh_mng_key_freeid() failed. HKID %d is leaked.\n",
 		       kvm_tdx->hkid);
 	} else {
@@ -580,10 +588,9 @@ static void tdx_reclaim_td_control_pages(struct kvm *kvm)
 	 * when it is reclaiming TDCS).
 	 */
 	err = tdh_phymem_page_wbinvd_tdr(&kvm_tdx->td);
-	if (KVM_BUG_ON(err, kvm)) {
-		pr_tdx_error(TDH_PHYMEM_PAGE_WBINVD, err);
+	if (TDX_BUG_ON(err, TDH_PHYMEM_PAGE_WBINVD, kvm))
 		return;
-	}
+
 	tdx_quirk_reset_page(kvm_tdx->td.tdr_page);
 
 	__free_page(kvm_tdx->td.tdr_page);
@@ -606,11 +613,8 @@ static int tdx_do_tdh_mng_key_config(void *param)
 
 	/* TDX_RND_NO_ENTROPY related retries are handled by sc_retry() */
 	err = tdh_mng_key_config(&kvm_tdx->td);
-
-	if (KVM_BUG_ON(err, &kvm_tdx->kvm)) {
-		pr_tdx_error(TDH_MNG_KEY_CONFIG, err);
+	if (TDX_BUG_ON(err, TDH_MNG_KEY_CONFIG, &kvm_tdx->kvm))
 		return -EIO;
-	}
 
 	return 0;
 }
@@ -1601,10 +1605,8 @@ static int tdx_mem_page_add(struct kvm *kvm, gfn_t gfn, enum pg_level level,
 	if (unlikely(tdx_operand_busy(err)))
 		return -EBUSY;
 
-	if (KVM_BUG_ON(err, kvm)) {
-		pr_tdx_error_2(TDH_MEM_PAGE_ADD, err, entry, level_state);
+	if (TDX_BUG_ON_2(err, TDH_MEM_PAGE_ADD, entry, level_state, kvm))
 		return -EIO;
-	}
 
 	return 0;
 }
@@ -1623,10 +1625,8 @@ static int tdx_mem_page_aug(struct kvm *kvm, gfn_t gfn,
 	if (unlikely(tdx_operand_busy(err)))
 		return -EBUSY;
 
-	if (KVM_BUG_ON(err, kvm)) {
-		pr_tdx_error_2(TDH_MEM_PAGE_AUG, err, entry, level_state);
+	if (TDX_BUG_ON_2(err, TDH_MEM_PAGE_AUG, entry, level_state, kvm))
 		return -EIO;
-	}
 
 	return 0;
 }
@@ -1675,10 +1675,8 @@ static int tdx_sept_link_private_spt(struct kvm *kvm, gfn_t gfn,
 	if (unlikely(tdx_operand_busy(err)))
 		return -EBUSY;
 
-	if (KVM_BUG_ON(err, kvm)) {
-		pr_tdx_error_2(TDH_MEM_SEPT_ADD, err, entry, level_state);
+	if (TDX_BUG_ON_2(err, TDH_MEM_SEPT_ADD, entry, level_state, kvm))
 		return -EIO;
-	}
 
 	return 0;
 }
@@ -1726,8 +1724,7 @@ static void tdx_track(struct kvm *kvm)
 		tdx_no_vcpus_enter_stop(kvm);
 	}
 
-	if (KVM_BUG_ON(err, kvm))
-		pr_tdx_error(TDH_MEM_TRACK, err);
+	TDX_BUG_ON(err, TDH_MEM_TRACK, kvm);
 
 	kvm_make_all_cpus_request(kvm, KVM_REQ_OUTSIDE_GUEST_MODE);
 }
@@ -1784,10 +1781,8 @@ static void tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
 		tdx_no_vcpus_enter_stop(kvm);
 	}
 
-	if (KVM_BUG_ON(err, kvm)) {
-		pr_tdx_error_2(TDH_MEM_RANGE_BLOCK, err, entry, level_state);
+	if (TDX_BUG_ON_2(err, TDH_MEM_RANGE_BLOCK, entry, level_state, kvm))
 		return;
-	}
 
 	/*
 	 * TDX requires TLB tracking before dropping private page.  Do
@@ -1814,16 +1809,12 @@ static void tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
 		tdx_no_vcpus_enter_stop(kvm);
 	}
 
-	if (KVM_BUG_ON(err, kvm)) {
-		pr_tdx_error_2(TDH_MEM_PAGE_REMOVE, err, entry, level_state);
+	if (TDX_BUG_ON_2(err, TDH_MEM_PAGE_REMOVE, entry, level_state, kvm))
 		return;
-	}
 
 	err = tdh_phymem_page_wbinvd_hkid((u16)kvm_tdx->hkid, page);
-	if (KVM_BUG_ON(err, kvm)) {
-		pr_tdx_error(TDH_PHYMEM_PAGE_WBINVD, err);
+	if (TDX_BUG_ON(err, TDH_PHYMEM_PAGE_WBINVD, kvm))
 		return;
-	}
 
 	tdx_quirk_reset_page(page);
 }
@@ -2463,8 +2454,7 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 		goto free_packages;
 	}
 
-	if (WARN_ON_ONCE(err)) {
-		pr_tdx_error(TDH_MNG_CREATE, err);
+	if (TDX_BUG_ON(err, TDH_MNG_CREATE, kvm)) {
 		ret = -EIO;
 		goto free_packages;
 	}
@@ -2505,8 +2495,7 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 			ret = -EAGAIN;
 			goto teardown;
 		}
-		if (WARN_ON_ONCE(err)) {
-			pr_tdx_error(TDH_MNG_ADDCX, err);
+		if (TDX_BUG_ON(err, TDH_MNG_ADDCX, kvm)) {
 			ret = -EIO;
 			goto teardown;
 		}
@@ -2523,8 +2512,7 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 		*seamcall_err = err;
 		ret = -EINVAL;
 		goto teardown;
-	} else if (WARN_ON_ONCE(err)) {
-		pr_tdx_error_1(TDH_MNG_INIT, err, rcx);
+	} else if (TDX_BUG_ON_1(err, TDH_MNG_INIT, rcx, kvm)) {
 		ret = -EIO;
 		goto teardown;
 	}
@@ -2792,10 +2780,8 @@ static int tdx_td_finalize(struct kvm *kvm, struct kvm_tdx_cmd *cmd)
 	cmd->hw_error = tdh_mr_finalize(&kvm_tdx->td);
 	if (tdx_operand_busy(cmd->hw_error))
 		return -EBUSY;
-	if (KVM_BUG_ON(cmd->hw_error, kvm)) {
-		pr_tdx_error(TDH_MR_FINALIZE, cmd->hw_error);
+	if (TDX_BUG_ON(cmd->hw_error, TDH_MR_FINALIZE, kvm))
 		return -EIO;
-	}
 
 	kvm_tdx->state = TD_STATE_RUNNABLE;
 	/* TD_STATE_RUNNABLE must be set before 'pre_fault_allowed' */
@@ -2882,16 +2868,14 @@ static int tdx_td_vcpu_init(struct kvm_vcpu *vcpu, u64 vcpu_rcx)
 	}
 
 	err = tdh_vp_create(&kvm_tdx->td, &tdx->vp);
-	if (KVM_BUG_ON(err, vcpu->kvm)) {
+	if (TDX_BUG_ON(err, TDH_VP_CREATE, vcpu->kvm)) {
 		ret = -EIO;
-		pr_tdx_error(TDH_VP_CREATE, err);
 		goto free_tdcx;
 	}
 
 	for (i = 0; i < kvm_tdx->td.tdcx_nr_pages; i++) {
 		err = tdh_vp_addcx(&tdx->vp, tdx->vp.tdcx_pages[i]);
-		if (KVM_BUG_ON(err, vcpu->kvm)) {
-			pr_tdx_error(TDH_VP_ADDCX, err);
+		if (TDX_BUG_ON(err, TDH_VP_ADDCX, vcpu->kvm)) {
 			/*
 			 * Pages already added are reclaimed by the vcpu_free
 			 * method, but the rest are freed here.
@@ -2905,10 +2889,8 @@ static int tdx_td_vcpu_init(struct kvm_vcpu *vcpu, u64 vcpu_rcx)
 	}
 
 	err = tdh_vp_init(&tdx->vp, vcpu_rcx, vcpu->vcpu_id);
-	if (KVM_BUG_ON(err, vcpu->kvm)) {
-		pr_tdx_error(TDH_VP_INIT, err);
+	if (TDX_BUG_ON(err, TDH_VP_INIT, vcpu->kvm))
 		return -EIO;
-	}
 
 	vcpu->arch.mp_state = KVM_MP_STATE_RUNNABLE;

---

## [20] Sean Christopherson — 2025-10-30
*Subject: [PATCH v4 19/28] KVM: TDX: Derive error argument names from the local
 variable names*

When printing SEAMCALL errors, use the name of the variable holding an
error parameter instead of the register from whence it came, so that flows
which use descriptive variable names will similarly print descriptive
error messages.

Suggested-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/vmx/tdx.c | 13 +++++++------
 1 file changed, 7 insertions(+), 6 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 5e6f2d8b6014..63d4609cc3bc 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -41,14 +41,15 @@
 #define TDX_BUG_ON(__err, __fn, __kvm)				\
 	__TDX_BUG_ON(__err, #__fn, __kvm, "%s", "")
 
-#define TDX_BUG_ON_1(__err, __fn, __rcx, __kvm)			\
-	__TDX_BUG_ON(__err, #__fn, __kvm, ", rcx 0x%llx", __rcx)
+#define TDX_BUG_ON_1(__err, __fn, a1, __kvm)			\
+	__TDX_BUG_ON(__err, #__fn, __kvm, ", " #a1 " 0x%llx", a1)
 
-#define TDX_BUG_ON_2(__err, __fn, __rcx, __rdx, __kvm)		\
-	__TDX_BUG_ON(__err, #__fn, __kvm, ", rcx 0x%llx, rdx 0x%llx", __rcx, __rdx)
+#define TDX_BUG_ON_2(__err, __fn, a1, a2, __kvm)	\
+	__TDX_BUG_ON(__err, #__fn, __kvm, ", " #a1 " 0x%llx, " #a2 " 0x%llx", a1, a2)
 
-#define TDX_BUG_ON_3(__err, __fn, __rcx, __rdx, __r8, __kvm)	\
-	__TDX_BUG_ON(__err, #__fn, __kvm, ", rcx 0x%llx, rdx 0x%llx, r8 0x%llx", __rcx, __rdx, __r8)
+#define TDX_BUG_ON_3(__err, __fn, a1, a2, a3, __kvm)	\
+	__TDX_BUG_ON(__err, #__fn, __kvm, ", " #a1 " 0x%llx, " #a2 ", 0x%llx, " #a3 " 0x%llx", \
+		     a1, a2, a3)
 
 
 bool enable_tdx __ro_after_init;

---

## [21] Sean Christopherson — 2025-10-30
*Subject: [PATCH v4 20/28] KVM: TDX: Assert that mmu_lock is held for write
 when removing S-EPT entries*

Unconditionally assert that mmu_lock is held for write when removing S-EPT
entries, not just when removing S-EPT entries triggers certain conditions,
e.g. needs to do TDH_MEM_TRACK or kick vCPUs out of the guest.
Conditionally asserting implies that it's safe to hold mmu_lock for read
when those paths aren't hit, which is simply not true, as KVM doesn't
support removing S-EPT entries under read-lock.

Only two paths lead to remove_external_spte(), and both paths asserts that
mmu_lock is held for write (tdp_mmu_set_spte() via lockdep, and
handle_removed_pt() via KVM_BUG_ON()).

Deliberately leave lockdep assertions in the "no vCPUs" helpers to document
that wait_for_sept_zap is guarded by holding mmu_lock for write, and keep
the conditional assert in tdx_track() as well, but with a comment to help
explain why holding mmu_lock for write matters (above and beyond why
tdx_sept_remove_private_spte()'s requirements).

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/vmx/tdx.c | 7 +++++++
 1 file changed, 7 insertions(+)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 63d4609cc3bc..999b519494e9 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1715,6 +1715,11 @@ static void tdx_track(struct kvm *kvm)
 	if (unlikely(kvm_tdx->state != TD_STATE_RUNNABLE))
 		return;
 
+	/*
+	 * The full sequence of TDH.MEM.TRACK and forcing vCPUs out of guest
+	 * mode must be serialized, as TDH.MEM.TRACK will fail if the previous
+	 * tracking epoch hasn't completed.
+	 */
 	lockdep_assert_held_write(&kvm->mmu_lock);
 
 	err = tdh_mem_track(&kvm_tdx->td);
@@ -1762,6 +1767,8 @@ static void tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
 	gpa_t gpa = gfn_to_gpa(gfn);
 	u64 err, entry, level_state;
 
+	lockdep_assert_held_write(&kvm->mmu_lock);
+
 	/*
 	 * HKID is released after all private pages have been removed, and set
 	 * before any might be populated. Warn if zapping is attempted when

---

## [22] Sean Christopherson — 2025-10-30
*Subject: [PATCH v4 21/28] KVM: TDX: Add macro to retry SEAMCALLs when forcing
 vCPUs out of guest*

Add a macro to handle kicking vCPUs out of the guest and retrying
SEAMCALLs on -EBUSY instead of providing small helpers to be used by each
SEAMCALL.  Wrapping the SEAMCALLs in a macro makes it a little harder to
tease out which SEAMCALL is being made, but significantly reduces the
amount of copy+paste code and makes it all but impossible to leave an
elevated wait_for_sept_zap.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/vmx/tdx.c | 82 +++++++++++++++++-------------------------
 1 file changed, 33 insertions(+), 49 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 999b519494e9..97632fc6b520 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -294,25 +294,34 @@ static inline void tdx_disassociate_vp(struct kvm_vcpu *vcpu)
 	vcpu->cpu = -1;
 }
 
-static void tdx_no_vcpus_enter_start(struct kvm *kvm)
-{
-	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
-
-	lockdep_assert_held_write(&kvm->mmu_lock);
-
-	WRITE_ONCE(kvm_tdx->wait_for_sept_zap, true);
-
-	kvm_make_all_cpus_request(kvm, KVM_REQ_OUTSIDE_GUEST_MODE);
-}
-
-static void tdx_no_vcpus_enter_stop(struct kvm *kvm)
-{
-	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
-
-	lockdep_assert_held_write(&kvm->mmu_lock);
-
-	WRITE_ONCE(kvm_tdx->wait_for_sept_zap, false);
-}
+/*
+ * Execute a SEAMCALL related to removing/blocking S-EPT entries, with a single
+ * retry (if necessary) after forcing vCPUs to exit and wait for the operation
+ * to complete.  All flows that remove/block S-EPT entries run with mmu_lock
+ * held for write, i.e. are mutually exclusive with each other, but they aren't
+ * mutually exclusive with running vCPUs, and so can fail with "operand busy"
+ * if a vCPU acquires a relevant lock in the TDX-Module, e.g. when doing TDCALL.
+ *
+ * Note, the retry is guaranteed to succeed, absent KVM and/or TDX-Module bugs.
+ */
+#define tdh_do_no_vcpus(tdh_func, kvm, args...)					\
+({										\
+	struct kvm_tdx *__kvm_tdx = to_kvm_tdx(kvm);				\
+	u64 __err;								\
+										\
+	lockdep_assert_held_write(&kvm->mmu_lock);				\
+										\
+	__err = tdh_func(args);							\
+	if (unlikely(tdx_operand_busy(__err))) {				\
+		WRITE_ONCE(__kvm_tdx->wait_for_sept_zap, true);			\
+		kvm_make_all_cpus_request(kvm, KVM_REQ_OUTSIDE_GUEST_MODE);	\
+										\
+		__err = tdh_func(args);						\
+										\
+		WRITE_ONCE(__kvm_tdx->wait_for_sept_zap, false);		\
+	}									\
+	__err;									\
+})
 
 /* TDH.PHYMEM.PAGE.RECLAIM is allowed only when destroying the TD. */
 static int __tdx_reclaim_page(struct page *page)
@@ -1722,14 +1731,7 @@ static void tdx_track(struct kvm *kvm)
 	 */
 	lockdep_assert_held_write(&kvm->mmu_lock);
 
-	err = tdh_mem_track(&kvm_tdx->td);
-	if (unlikely(tdx_operand_busy(err))) {
-		/* After no vCPUs enter, the second retry is expected to succeed */
-		tdx_no_vcpus_enter_start(kvm);
-		err = tdh_mem_track(&kvm_tdx->td);
-		tdx_no_vcpus_enter_stop(kvm);
-	}
-
+	err = tdh_do_no_vcpus(tdh_mem_track, kvm, &kvm_tdx->td);
 	TDX_BUG_ON(err, TDH_MEM_TRACK, kvm);
 
 	kvm_make_all_cpus_request(kvm, KVM_REQ_OUTSIDE_GUEST_MODE);
@@ -1781,14 +1783,8 @@ static void tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
 	if (KVM_BUG_ON(level != PG_LEVEL_4K, kvm))
 		return;
 
-	err = tdh_mem_range_block(&kvm_tdx->td, gpa, tdx_level, &entry, &level_state);
-	if (unlikely(tdx_operand_busy(err))) {
-		/* After no vCPUs enter, the second retry is expected to succeed */
-		tdx_no_vcpus_enter_start(kvm);
-		err = tdh_mem_range_block(&kvm_tdx->td, gpa, tdx_level, &entry, &level_state);
-		tdx_no_vcpus_enter_stop(kvm);
-	}
-
+	err = tdh_do_no_vcpus(tdh_mem_range_block, kvm, &kvm_tdx->td, gpa,
+			      tdx_level, &entry, &level_state);
 	if (TDX_BUG_ON_2(err, TDH_MEM_RANGE_BLOCK, entry, level_state, kvm))
 		return;
 
@@ -1803,20 +1799,8 @@ static void tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
 	 * with other vcpu sept operation.
 	 * Race with TDH.VP.ENTER due to (0-step mitigation) and Guest TDCALLs.
 	 */
-	err = tdh_mem_page_remove(&kvm_tdx->td, gpa, tdx_level, &entry,
-				  &level_state);
-
-	if (unlikely(tdx_operand_busy(err))) {
-		/*
-		 * The second retry is expected to succeed after kicking off all
-		 * other vCPUs and prevent them from invoking TDH.VP.ENTER.
-		 */
-		tdx_no_vcpus_enter_start(kvm);
-		err = tdh_mem_page_remove(&kvm_tdx->td, gpa, tdx_level, &entry,
-					  &level_state);
-		tdx_no_vcpus_enter_stop(kvm);
-	}
-
+	err = tdh_do_no_vcpus(tdh_mem_page_remove, kvm, &kvm_tdx->td, gpa,
+			      tdx_level, &entry, &level_state);
 	if (TDX_BUG_ON_2(err, TDH_MEM_PAGE_REMOVE, entry, level_state, kvm))
 		return;

---

## [23] Sean Christopherson — 2025-10-30
*Subject: [PATCH v4 22/28] KVM: TDX: Add tdx_get_cmd() helper to get and
 validate sub-ioctl command*

Add a helper to copy a kvm_tdx_cmd structure from userspace and verify
that must-be-zero fields are indeed zero.

No functional change intended.

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/vmx/tdx.c | 35 +++++++++++++++++++++--------------
 1 file changed, 21 insertions(+), 14 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 97632fc6b520..390c934562c1 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -2782,20 +2782,29 @@ static int tdx_td_finalize(struct kvm *kvm, struct kvm_tdx_cmd *cmd)
 	return 0;
 }
 
+static int tdx_get_cmd(void __user *argp, struct kvm_tdx_cmd *cmd)
+{
+	if (copy_from_user(cmd, argp, sizeof(*cmd)))
+		return -EFAULT;
+
+	/*
+	 * Userspace should never set hw_error.  KVM writes hw_error to report
+	 * hardware-defined error back to userspace.
+	 */
+	if (cmd->hw_error)
+		return -EINVAL;
+
+	return 0;
+}
+
 int tdx_vm_ioctl(struct kvm *kvm, void __user *argp)
 {
 	struct kvm_tdx_cmd tdx_cmd;
 	int r;
 
-	if (copy_from_user(&tdx_cmd, argp, sizeof(struct kvm_tdx_cmd)))
-		return -EFAULT;
-
-	/*
-	 * Userspace should never set hw_error. It is used to fill
-	 * hardware-defined error by the kernel.
-	 */
-	if (tdx_cmd.hw_error)
-		return -EINVAL;
+	r = tdx_get_cmd(argp, &tdx_cmd);
+	if (r)
+		return r;
 
 	mutex_lock(&kvm->lock);
 
@@ -3171,11 +3180,9 @@ int tdx_vcpu_ioctl(struct kvm_vcpu *vcpu, void __user *argp)
 	if (!is_hkid_assigned(kvm_tdx) || kvm_tdx->state == TD_STATE_RUNNABLE)
 		return -EINVAL;
 
-	if (copy_from_user(&cmd, argp, sizeof(cmd)))
-		return -EFAULT;
-
-	if (cmd.hw_error)
-		return -EINVAL;
+	ret = tdx_get_cmd(argp, &cmd);
+	if (ret)
+		return ret;
 
 	switch (cmd.id) {
 	case KVM_TDX_INIT_VCPU:

---

## [24] Sean Christopherson — 2025-10-30
*Subject: [PATCH v4 23/28] KVM: TDX: Convert INIT_MEM_REGION and INIT_VCPU to
 "unlocked" vCPU ioctl*

Handle the KVM_TDX_INIT_MEM_REGION and KVM_TDX_INIT_VCPU vCPU sub-ioctls
in the unlocked variant, i.e. outside of vcpu->mutex, in anticipation of
taking kvm->lock along with all other vCPU mutexes, at which point the
sub-ioctls _must_ start without vcpu->mutex held.

No functional change intended.

Reviewed-by: Kai Huang <kai.huang@intel.com>
Co-developed-by: Yan Zhao <yan.y.zhao@intel.com>
Signed-off-by: Yan Zhao <yan.y.zhao@intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/kvm-x86-ops.h |  1 +
 arch/x86/include/asm/kvm_host.h    |  1 +
 arch/x86/kvm/vmx/main.c            |  9 +++++++
 arch/x86/kvm/vmx/tdx.c             | 42 +++++++++++++++++++++++++-----
 arch/x86/kvm/vmx/x86_ops.h         |  1 +
 arch/x86/kvm/x86.c                 |  7 +++++
 6 files changed, 55 insertions(+), 6 deletions(-)

diff --git a/arch/x86/include/asm/kvm-x86-ops.h b/arch/x86/include/asm/kvm-x86-ops.h
index fdf178443f85..de709fb5bd76 100644
--- a/arch/x86/include/asm/kvm-x86-ops.h
+++ b/arch/x86/include/asm/kvm-x86-ops.h
@@ -128,6 +128,7 @@ KVM_X86_OP(enable_smi_window)
 KVM_X86_OP_OPTIONAL(dev_get_attr)
 KVM_X86_OP_OPTIONAL(mem_enc_ioctl)
 KVM_X86_OP_OPTIONAL(vcpu_mem_enc_ioctl)
+KVM_X86_OP_OPTIONAL(vcpu_mem_enc_unlocked_ioctl)
 KVM_X86_OP_OPTIONAL(mem_enc_register_region)
 KVM_X86_OP_OPTIONAL(mem_enc_unregister_region)
 KVM_X86_OP_OPTIONAL(vm_copy_enc_context_from)
diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h
index 87a5f5100b1d..2bfae1cfa514 100644
--- a/arch/x86/include/asm/kvm_host.h
+++ b/arch/x86/include/asm/kvm_host.h
@@ -1914,6 +1914,7 @@ struct kvm_x86_ops {
 	int (*dev_get_attr)(u32 group, u64 attr, u64 *val);
 	int (*mem_enc_ioctl)(struct kvm *kvm, void __user *argp);
 	int (*vcpu_mem_enc_ioctl)(struct kvm_vcpu *vcpu, void __user *argp);
+	int (*vcpu_mem_enc_unlocked_ioctl)(struct kvm_vcpu *vcpu, void __user *argp);
 	int (*mem_enc_register_region)(struct kvm *kvm, struct kvm_enc_region *argp);
 	int (*mem_enc_unregister_region)(struct kvm *kvm, struct kvm_enc_region *argp);
 	int (*vm_copy_enc_context_from)(struct kvm *kvm, unsigned int source_fd);
diff --git a/arch/x86/kvm/vmx/main.c b/arch/x86/kvm/vmx/main.c
index 0eb2773b2ae2..a46ccd670785 100644
--- a/arch/x86/kvm/vmx/main.c
+++ b/arch/x86/kvm/vmx/main.c
@@ -831,6 +831,14 @@ static int vt_vcpu_mem_enc_ioctl(struct kvm_vcpu *vcpu, void __user *argp)
 	return tdx_vcpu_ioctl(vcpu, argp);
 }
 
+static int vt_vcpu_mem_enc_unlocked_ioctl(struct kvm_vcpu *vcpu, void __user *argp)
+{
+	if (!is_td_vcpu(vcpu))
+		return -EINVAL;
+
+	return tdx_vcpu_unlocked_ioctl(vcpu, argp);
+}
+
 static int vt_gmem_max_mapping_level(struct kvm *kvm, kvm_pfn_t pfn,
 				     bool is_private)
 {
@@ -1005,6 +1013,7 @@ struct kvm_x86_ops vt_x86_ops __initdata = {
 
 	.mem_enc_ioctl = vt_op_tdx_only(mem_enc_ioctl),
 	.vcpu_mem_enc_ioctl = vt_op_tdx_only(vcpu_mem_enc_ioctl),
+	.vcpu_mem_enc_unlocked_ioctl = vt_op_tdx_only(vcpu_mem_enc_unlocked_ioctl),
 
 	.gmem_max_mapping_level = vt_op_tdx_only(gmem_max_mapping_level)
 };
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 390c934562c1..d6f40a481487 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -3171,6 +3171,42 @@ static int tdx_vcpu_init_mem_region(struct kvm_vcpu *vcpu, struct kvm_tdx_cmd *c
 	return ret;
 }
 
+int tdx_vcpu_unlocked_ioctl(struct kvm_vcpu *vcpu, void __user *argp)
+{
+	struct kvm_tdx *kvm_tdx = to_kvm_tdx(vcpu->kvm);
+	struct kvm_tdx_cmd cmd;
+	int r;
+
+	r = tdx_get_cmd(argp, &cmd);
+	if (r)
+		return r;
+
+	if (!is_hkid_assigned(kvm_tdx) || kvm_tdx->state == TD_STATE_RUNNABLE)
+		return -EINVAL;
+
+	if (mutex_lock_killable(&vcpu->mutex))
+		return -EINTR;
+
+	vcpu_load(vcpu);
+
+	switch (cmd.id) {
+	case KVM_TDX_INIT_MEM_REGION:
+		r = tdx_vcpu_init_mem_region(vcpu, &cmd);
+		break;
+	case KVM_TDX_INIT_VCPU:
+		r = tdx_vcpu_init(vcpu, &cmd);
+		break;
+	default:
+		r = -ENOIOCTLCMD;
+		break;
+	}
+
+	vcpu_put(vcpu);
+
+	mutex_unlock(&vcpu->mutex);
+	return r;
+}
+
 int tdx_vcpu_ioctl(struct kvm_vcpu *vcpu, void __user *argp)
 {
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(vcpu->kvm);
@@ -3185,12 +3221,6 @@ int tdx_vcpu_ioctl(struct kvm_vcpu *vcpu, void __user *argp)
 		return ret;
 
 	switch (cmd.id) {
-	case KVM_TDX_INIT_VCPU:
-		ret = tdx_vcpu_init(vcpu, &cmd);
-		break;
-	case KVM_TDX_INIT_MEM_REGION:
-		ret = tdx_vcpu_init_mem_region(vcpu, &cmd);
-		break;
 	case KVM_TDX_GET_CPUID:
 		ret = tdx_vcpu_get_cpuid(vcpu, &cmd);
 		break;
diff --git a/arch/x86/kvm/vmx/x86_ops.h b/arch/x86/kvm/vmx/x86_ops.h
index 77613a44cebf..d09abeac2b56 100644
--- a/arch/x86/kvm/vmx/x86_ops.h
+++ b/arch/x86/kvm/vmx/x86_ops.h
@@ -148,6 +148,7 @@ int tdx_get_msr(struct kvm_vcpu *vcpu, struct msr_data *msr);
 int tdx_set_msr(struct kvm_vcpu *vcpu, struct msr_data *msr);
 
 int tdx_vcpu_ioctl(struct kvm_vcpu *vcpu, void __user *argp);
+int tdx_vcpu_unlocked_ioctl(struct kvm_vcpu *vcpu, void __user *argp);
 
 void tdx_flush_tlb_current(struct kvm_vcpu *vcpu);
 void tdx_flush_tlb_all(struct kvm_vcpu *vcpu);
diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index b85cb213a336..593fccc9cf1c 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -7243,6 +7243,13 @@ static int kvm_vm_ioctl_set_clock(struct kvm *kvm, void __user *argp)
 long kvm_arch_vcpu_unlocked_ioctl(struct file *filp, unsigned int ioctl,
 				  unsigned long arg)
 {
+	struct kvm_vcpu *vcpu = filp->private_data;
+	void __user *argp = (void __user *)arg;
+
+	if (ioctl == KVM_MEMORY_ENCRYPT_OP &&
+	    kvm_x86_ops.vcpu_mem_enc_unlocked_ioctl)
+		return kvm_x86_call(vcpu_mem_enc_unlocked_ioctl)(vcpu, argp);
+
 	return -ENOIOCTLCMD;
 }

---

## [25] Sean Christopherson — 2025-10-30
*Subject: [PATCH v4 24/28] KVM: TDX: Use guard() to acquire kvm->lock in tdx_vm_ioctl()*

Use guard() in tdx_vm_ioctl() to tidy up the code a small amount, but more
importantly to minimize the diff of a future change, which will use
guard-like semantics to acquire and release multiple locks.

No functional change intended.

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/vmx/tdx.c | 9 +++------
 1 file changed, 3 insertions(+), 6 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index d6f40a481487..037429964fd7 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -2806,7 +2806,7 @@ int tdx_vm_ioctl(struct kvm *kvm, void __user *argp)
 	if (r)
 		return r;
 
-	mutex_lock(&kvm->lock);
+	guard(mutex)(&kvm->lock);
 
 	switch (tdx_cmd.id) {
 	case KVM_TDX_CAPABILITIES:
@@ -2819,15 +2819,12 @@ int tdx_vm_ioctl(struct kvm *kvm, void __user *argp)
 		r = tdx_td_finalize(kvm, &tdx_cmd);
 		break;
 	default:
-		r = -EINVAL;
-		goto out;
+		return -EINVAL;
 	}
 
 	if (copy_to_user(argp, &tdx_cmd, sizeof(struct kvm_tdx_cmd)))
-		r = -EFAULT;
+		return -EFAULT;
 
-out:
-	mutex_unlock(&kvm->lock);
 	return r;
 }

---

## [26] Sean Christopherson — 2025-10-30
*Subject: [PATCH v4 25/28] KVM: TDX: Don't copy "cmd" back to userspace for KVM_TDX_CAPABILITIES*

Don't copy the kvm_tdx_cmd structure back to userspace when handling
KVM_TDX_CAPABILITIES, as tdx_get_capabilities() doesn't modify hw_error or
any other fields.

Opportunistically hoist the call to tdx_get_capabilities() outside of the
kvm->lock critical section, as getting the capabilities doesn't touch the
VM in any way, e.g. doesn't even take @kvm.

Suggested-by: Kai Huang <kai.huang@intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/vmx/tdx.c | 6 +++---
 1 file changed, 3 insertions(+), 3 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 037429964fd7..57dfddd2a6cf 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -2806,12 +2806,12 @@ int tdx_vm_ioctl(struct kvm *kvm, void __user *argp)
 	if (r)
 		return r;
 
+	if (tdx_cmd.id == KVM_TDX_CAPABILITIES)
+		return tdx_get_capabilities(&tdx_cmd);
+
 	guard(mutex)(&kvm->lock);
 
 	switch (tdx_cmd.id) {
-	case KVM_TDX_CAPABILITIES:
-		r = tdx_get_capabilities(&tdx_cmd);
-		break;
 	case KVM_TDX_INIT_VM:
 		r = tdx_td_init(kvm, &tdx_cmd);
 		break;

---

## [27] Sean Christopherson — 2025-10-30
*Subject: [PATCH v4 26/28] KVM: TDX: Guard VM state transitions with "all" the locks*

Acquire kvm->lock, kvm->slots_lock, and all vcpu->mutex locks when
servicing ioctls that (a) transition the TD to a new state, i.e. when
doing INIT or FINALIZE or (b) are only valid if the TD is in a specific
state, i.e. when initializing a vCPU or memory region.  Acquiring "all"
the locks fixes several KVM_BUG_ON() situations where a SEAMCALL can fail
due to racing actions, e.g. if tdh_vp_create() contends with either
tdh_mr_extend() or tdh_mr_finalize().

For all intents and purposes, the paths in question are fully serialized,
i.e. there's no reason to try and allow anything remotely interesting to
happen.  Smack 'em with a big hammer instead of trying to be "nice".

Acquire kvm->lock to prevent VM-wide things from happening, slots_lock to
prevent kvm_mmu_zap_all_fast(), and _all_ vCPU mutexes to prevent vCPUs
from interefering.  Use the recently-renamed kvm_arch_vcpu_unlocked_ioctl()
to service the vCPU-scoped ioctls to avoid a lock inversion problem, e.g.
due to taking vcpu->mutex outside kvm->lock.

See also commit ecf371f8b02d ("KVM: SVM: Reject SEV{-ES} intra host
migration if vCPU creation is in-flight"), which fixed a similar bug with
SEV intra-host migration where an in-flight vCPU creation could race with
a VM-wide state transition.

Define a fancy new CLASS to handle the lock+check => unlock logic with
guard()-like syntax:

        CLASS(tdx_vm_state_guard, guard)(kvm);
        if (IS_ERR(guard))
                return PTR_ERR(guard);

to simplify juggling the many locks.

Note!  Take kvm->slots_lock *after* all vcpu->mutex locks, as per KVM's
soon-to-be-documented lock ordering rules[1].

Link: https://lore.kernel.org/all/20251016235538.171962-1-seanjc@google.com [1]
Reported-by: Yan Zhao <yan.y.zhao@intel.com>
Closes: https://lore.kernel.org/all/aLFiPq1smdzN3Ary@yzhao56-desk.sh.intel.com
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/vmx/tdx.c | 59 +++++++++++++++++++++++++++++++++++-------
 1 file changed, 49 insertions(+), 10 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 57dfddd2a6cf..8bcdec049ac6 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -2653,6 +2653,46 @@ static int tdx_read_cpuid(struct kvm_vcpu *vcpu, u32 leaf, u32 sub_leaf,
 	return -EIO;
 }
 
+typedef void *tdx_vm_state_guard_t;
+
+static tdx_vm_state_guard_t tdx_acquire_vm_state_locks(struct kvm *kvm)
+{
+	int r;
+
+	mutex_lock(&kvm->lock);
+
+	if (kvm->created_vcpus != atomic_read(&kvm->online_vcpus)) {
+		r = -EBUSY;
+		goto out_err;
+	}
+
+	r = kvm_lock_all_vcpus(kvm);
+	if (r)
+		goto out_err;
+
+	/*
+	 * Note the unintuitive ordering!  vcpu->mutex must be taken outside
+	 * kvm->slots_lock!
+	 */
+	mutex_lock(&kvm->slots_lock);
+	return kvm;
+
+out_err:
+	mutex_unlock(&kvm->lock);
+	return ERR_PTR(r);
+}
+
+static void tdx_release_vm_state_locks(struct kvm *kvm)
+{
+	mutex_unlock(&kvm->slots_lock);
+	kvm_unlock_all_vcpus(kvm);
+	mutex_unlock(&kvm->lock);
+}
+
+DEFINE_CLASS(tdx_vm_state_guard, tdx_vm_state_guard_t,
+	     if (!IS_ERR(_T)) tdx_release_vm_state_locks(_T),
+	     tdx_acquire_vm_state_locks(kvm), struct kvm *kvm);
+
 static int tdx_td_init(struct kvm *kvm, struct kvm_tdx_cmd *cmd)
 {
 	struct kvm_tdx_init_vm __user *user_data = u64_to_user_ptr(cmd->data);
@@ -2764,8 +2804,6 @@ static int tdx_td_finalize(struct kvm *kvm, struct kvm_tdx_cmd *cmd)
 {
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
 
-	guard(mutex)(&kvm->slots_lock);
-
 	if (!is_hkid_assigned(kvm_tdx) || kvm_tdx->state == TD_STATE_RUNNABLE)
 		return -EINVAL;
 
@@ -2809,7 +2847,9 @@ int tdx_vm_ioctl(struct kvm *kvm, void __user *argp)
 	if (tdx_cmd.id == KVM_TDX_CAPABILITIES)
 		return tdx_get_capabilities(&tdx_cmd);
 
-	guard(mutex)(&kvm->lock);
+	CLASS(tdx_vm_state_guard, guard)(kvm);
+	if (IS_ERR(guard))
+		return PTR_ERR(guard);
 
 	switch (tdx_cmd.id) {
 	case KVM_TDX_INIT_VM:
@@ -3113,8 +3153,6 @@ static int tdx_vcpu_init_mem_region(struct kvm_vcpu *vcpu, struct kvm_tdx_cmd *c
 	if (tdx->state != VCPU_TD_STATE_INITIALIZED)
 		return -EINVAL;
 
-	guard(mutex)(&kvm->slots_lock);
-
 	/* Once TD is finalized, the initial guest memory is fixed. */
 	if (kvm_tdx->state == TD_STATE_RUNNABLE)
 		return -EINVAL;
@@ -3170,7 +3208,8 @@ static int tdx_vcpu_init_mem_region(struct kvm_vcpu *vcpu, struct kvm_tdx_cmd *c
 
 int tdx_vcpu_unlocked_ioctl(struct kvm_vcpu *vcpu, void __user *argp)
 {
-	struct kvm_tdx *kvm_tdx = to_kvm_tdx(vcpu->kvm);
+	struct kvm *kvm = vcpu->kvm;
+	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
 	struct kvm_tdx_cmd cmd;
 	int r;
 
@@ -3178,12 +3217,13 @@ int tdx_vcpu_unlocked_ioctl(struct kvm_vcpu *vcpu, void __user *argp)
 	if (r)
 		return r;
 
+	CLASS(tdx_vm_state_guard, guard)(kvm);
+	if (IS_ERR(guard))
+		return PTR_ERR(guard);
+
 	if (!is_hkid_assigned(kvm_tdx) || kvm_tdx->state == TD_STATE_RUNNABLE)
 		return -EINVAL;
 
-	if (mutex_lock_killable(&vcpu->mutex))
-		return -EINTR;
-
 	vcpu_load(vcpu);
 
 	switch (cmd.id) {
@@ -3200,7 +3240,6 @@ int tdx_vcpu_unlocked_ioctl(struct kvm_vcpu *vcpu, void __user *argp)
 
 	vcpu_put(vcpu);
 
-	mutex_unlock(&vcpu->mutex);
 	return r;
 }

---

## [28] Sean Christopherson — 2025-10-30
*Subject: [PATCH v4 27/28] KVM: TDX: Bug the VM if extending the initial
 measurement fails*

WARN and terminate the VM if TDH_MR_EXTEND fails, as extending the
measurement should fail if and only if there is a KVM bug, or if the S-EPT
mapping is invalid.  Now that KVM makes all state transitions mutually
exclusive via tdx_vm_state_guard, it should be impossible for S-EPT
mappings to be removed between kvm_tdp_mmu_map_private_pfn() and
tdh_mr_extend().

Holding slots_lock prevents zaps due to memslot updates,
filemap_invalidate_lock() prevents zaps due to guest_memfd PUNCH_HOLE,
vcpu->mutex locks prevents updates from other vCPUs, kvm->lock prevents
VM-scoped ioctls from creating havoc (e.g. by creating new vCPUs), and all
usage of kvm_zap_gfn_range() is mutually exclusive with S-EPT entries that
can be used for the initial image.

For kvm_zap_gfn_range(), the call from sev.c is obviously mutually
exclusive, TDX disallows KVM_X86_QUIRK_IGNORE_GUEST_PAT so the same goes
for kvm_noncoherent_dma_assignment_start_or_stop(), and
__kvm_set_or_clear_apicv_inhibit() is blocked by virtue of holding all
VM and vCPU mutexes (and the APIC page has its own non-guest_memfd memslot
and so can't be used for the initial image, which means that too is
mutually exclusive irrespective of locking).

Opportunistically return early if the region doesn't need to be measured
in order to reduce line lengths and avoid wraps.  Similarly, immediately
and explicitly return if TDH_MR_EXTEND fails to make it clear that KVM
needs to bail entirely if extending the measurement fails.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/vmx/tdx.c | 24 +++++++++++++-----------
 1 file changed, 13 insertions(+), 11 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 8bcdec049ac6..762f2896547f 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -3123,21 +3123,23 @@ static int tdx_gmem_post_populate(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
 
 	put_page(src_page);
 
-	if (ret)
+	if (ret || !(arg->flags & KVM_TDX_MEASURE_MEMORY_REGION))
 		return ret;
 
-	if (arg->flags & KVM_TDX_MEASURE_MEMORY_REGION) {
-		for (i = 0; i < PAGE_SIZE; i += TDX_EXTENDMR_CHUNKSIZE) {
-			err = tdh_mr_extend(&kvm_tdx->td, gpa + i, &entry,
-					    &level_state);
-			if (err) {
-				ret = -EIO;
-				break;
-			}
-		}
+	/*
+	 * Note, MR.EXTEND can fail if the S-EPT mapping is somehow removed
+	 * between mapping the pfn and now, but slots_lock prevents memslot
+	 * updates, filemap_invalidate_lock() prevents guest_memfd updates,
+	 * mmu_notifier events can't reach S-EPT entries, and KVM's internal
+	 * zapping flows are mutually exclusive with S-EPT mappings.
+	 */
+	for (i = 0; i < PAGE_SIZE; i += TDX_EXTENDMR_CHUNKSIZE) {
+		err = tdh_mr_extend(&kvm_tdx->td, gpa + i, &entry, &level_state);
+		if (TDX_BUG_ON_2(err, TDH_MR_EXTEND, entry, level_state, kvm))
+			return -EIO;
 	}
 
-	return ret;
+	return 0;
 }
 
 static int tdx_vcpu_init_mem_region(struct kvm_vcpu *vcpu, struct kvm_tdx_cmd *cmd)

---

## [29] Sean Christopherson — 2025-10-30
*Subject: [PATCH v4 28/28] KVM: TDX: Fix list_add corruption during vcpu_load()*

From: Yan Zhao <yan.y.zhao@intel.com>

During vCPU creation, a vCPU may be destroyed immediately after
kvm_arch_vcpu_create() (e.g., due to vCPU id confiliction). However, the
vcpu_load() inside kvm_arch_vcpu_create() may have associate the vCPU to
pCPU via "list_add(&tdx->cpu_list, &per_cpu(associated_tdvcpus, cpu))"
before invoking tdx_vcpu_free().

Though there's no need to invoke tdh_vp_flush() on the vCPU, failing to
dissociate the vCPU from pCPU (i.e., "list_del(&to_tdx(vcpu)->cpu_list)")
will cause list corruption of the per-pCPU list associated_tdvcpus.

Then, a later list_add() during vcpu_load() would detect list corruption
and print calltrace as shown below.

Dissociate a vCPU from its associated pCPU in tdx_vcpu_free() for the vCPUs
destroyed immediately after creation which must be in
VCPU_TD_STATE_UNINITIALIZED state.

kernel BUG at lib/list_debug.c:29!
Oops: invalid opcode: 0000 [#2] SMP NOPTI
RIP: 0010:__list_add_valid_or_report+0x82/0xd0

Call Trace:
 <TASK>
 tdx_vcpu_load+0xa8/0x120
 vt_vcpu_load+0x25/0x30
 kvm_arch_vcpu_load+0x81/0x300
 vcpu_load+0x55/0x90
 kvm_arch_vcpu_create+0x24f/0x330
 kvm_vm_ioctl_create_vcpu+0x1b1/0x53
 kvm_vm_ioctl+0xc2/0xa60
  __x64_sys_ioctl+0x9a/0xf0
 x64_sys_call+0x10ee/0x20d0
 do_syscall_64+0xc3/0x470
 entry_SYSCALL_64_after_hwframe+0x77/0x7f

Fixes: d789fa6efac9 ("KVM: TDX: Handle vCPU dissociation")
Signed-off-by: Yan Zhao <yan.y.zhao@intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/vmx/tdx.c | 43 +++++++++++++++++++++++++++++++++++++-----
 1 file changed, 38 insertions(+), 5 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 762f2896547f..db7ac7955ca1 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -843,19 +843,52 @@ void tdx_vcpu_put(struct kvm_vcpu *vcpu)
 	tdx_prepare_switch_to_host(vcpu);
 }
 
+/*
+ * Life cycles for a TD and a vCPU:
+ * 1. KVM_CREATE_VM ioctl.
+ *    TD state is TD_STATE_UNINITIALIZED.
+ *    hkid is not assigned at this stage.
+ * 2. KVM_TDX_INIT_VM ioctl.
+ *    TD transitions to TD_STATE_INITIALIZED.
+ *    hkid is assigned after this stage.
+ * 3. KVM_CREATE_VCPU ioctl. (only when TD is TD_STATE_INITIALIZED).
+ *    3.1 tdx_vcpu_create() transitions vCPU state to VCPU_TD_STATE_UNINITIALIZED.
+ *    3.2 vcpu_load() and vcpu_put() in kvm_arch_vcpu_create().
+ *    3.3 (conditional) if any error encountered after kvm_arch_vcpu_create()
+ *        kvm_arch_vcpu_destroy() --> tdx_vcpu_free().
+ * 4. KVM_TDX_INIT_VCPU ioctl.
+ *    tdx_vcpu_init() transitions vCPU state to VCPU_TD_STATE_INITIALIZED.
+ *    vCPU control structures are allocated at this stage.
+ * 5. kvm_destroy_vm().
+ *    5.1 tdx_mmu_release_hkid(): (1) tdh_vp_flush(), disassociates all vCPUs.
+ *                                (2) puts hkid to !assigned state.
+ *    5.2 kvm_destroy_vcpus() --> tdx_vcpu_free():
+ *        transitions vCPU to VCPU_TD_STATE_UNINITIALIZED state.
+ *    5.3 tdx_vm_destroy()
+ *        transitions TD to TD_STATE_UNINITIALIZED state.
+ *
+ * tdx_vcpu_free() can be invoked only at 3.3 or 5.2.
+ * - If at 3.3, hkid is still assigned, but the vCPU must be in
+ *   VCPU_TD_STATE_UNINITIALIZED state.
+ * - if at 5.2, hkid must be !assigned and all vCPUs must be in
+ *   VCPU_TD_STATE_INITIALIZED state and have been dissociated.
+ */
 void tdx_vcpu_free(struct kvm_vcpu *vcpu)
 {
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(vcpu->kvm);
 	struct vcpu_tdx *tdx = to_tdx(vcpu);
 	int i;
 
+	if (vcpu->cpu != -1) {
+		KVM_BUG_ON(tdx->state == VCPU_TD_STATE_INITIALIZED, vcpu->kvm);
+		tdx_flush_vp_on_cpu(vcpu);
+		return;
+	}
+
 	/*
 	 * It is not possible to reclaim pages while hkid is assigned. It might
-	 * be assigned if:
-	 * 1. the TD VM is being destroyed but freeing hkid failed, in which
-	 * case the pages are leaked
-	 * 2. TD VCPU creation failed and this on the error path, in which case
-	 * there is nothing to do anyway
+	 * be assigned if the TD VM is being destroyed but freeing hkid failed,
+	 * in which case the pages are leaked.
 	 */
 	if (is_hkid_assigned(kvm_tdx))
 		return;

---

## [30] Huang, Kai — 2025-10-30
*Subject: Re: [PATCH v4 05/28] KVM: x86/mmu: WARN if KVM attempts to map into
 an invalid TDP MMU root*

On Thu, 2025-10-30 at 13:09 -0700, Sean Christopherson wrote:
> When mapping into the TDP MMU, WARN (if KVM_PROVE_MMU=y) if the root is
> invalid, e.g. if KVM is attempting to insert a mapping without checking if

Reviewed-by: Kai Huang <kai.huang@intel.com>

> ---
>  arch/x86/kvm/mmu/tdp_mmu.c | 2 ++

---

## [31] Huang, Kai — 2025-10-30
*Subject: Re: [PATCH v4 09/28] KVM: TDX: Return -EIO, not -EINVAL, on a
 KVM_BUG_ON() condition*

On Thu, 2025-10-30 at 13:09 -0700, Sean Christopherson wrote:
> Return -EIO when a KVM_BUG_ON() is tripped, as KVM's ABI is to return -EIO
> when a VM has been killed due to a KVM bug, not -EINVAL.  Note, many (all?)

Reviewed-by: Kai Huang <kai.huang@intel.com>

---

## [32] Huang, Kai — 2025-10-30
*Subject: Re: [PATCH v4 11/28] KVM: x86/mmu: Drop the return code from
 kvm_x86_ops.remove_external_spte()*

On Thu, 2025-10-30 at 13:09 -0700, Sean Christopherson wrote:
> Drop the return code from kvm_x86_ops.remove_external_spte(), a.k.a.
> tdx_sept_remove_private_spte(), as KVM simply does a KVM_BUG_ON() failure,

Reviewed-by: Kai Huang <kai.huang@intel.com>

---

## [33] Huang, Kai — 2025-10-30
*Subject: Re: [PATCH v4 12/28] KVM: TDX: WARN if mirror SPTE doesn't have full
 RWX when creating S-EPT mapping*

On Thu, 2025-10-30 at 13:09 -0700, Sean Christopherson wrote:
> Pass in the mirror_spte to kvm_x86_ops.set_external_spte() to provide
> symmetry with .remove_external_spte(), and assert in TDX that the mirror

Reviewed-by: Kai Huang <kai.huang@intel.com>

[...]

>  static int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn,
> -				     enum pg_level level, kvm_pfn_t pfn)

Nit: 

I am a little bit confused about when to use WARN_ON_ONCE() and
KVM_BUG_ON(). :-)

---

## [34] Huang, Kai — 2025-10-30
*Subject: Re: [PATCH v4 20/28] KVM: TDX: Assert that mmu_lock is held for write
 when removing S-EPT entries*

On Thu, 2025-10-30 at 13:09 -0700, Sean Christopherson wrote:
> Unconditionally assert that mmu_lock is held for write when removing S-EPT
> entries, not just when removing S-EPT entries triggers certain conditions,
								^
								assert

> mmu_lock is held for write (tdp_mmu_set_spte() via lockdep, and
> handle_removed_pt() via KVM_BUG_ON()).

Reviewed-by: Kai Huang <kai.huang@intel.com>

---

## [35] Huang, Kai — 2025-10-30
*Subject: Re: [PATCH v4 21/28] KVM: TDX: Add macro to retry SEAMCALLs when
 forcing vCPUs out of guest*

On Thu, 2025-10-30 at 13:09 -0700, Sean Christopherson wrote:
> Add a macro to handle kicking vCPUs out of the guest and retrying
> SEAMCALLs on -EBUSY instead of providing small helpers to be used by each
	       ^
Nit: maybe TDX_OPERAND_BUSY to be more accurate, but feel free to ignore.

> SEAMCALL.  Wrapping the SEAMCALLs in a macro makes it a little harder to
> tease out which SEAMCALL is being made, but significantly reduces the

Reviewed-by: Kai Huang <kai.huang@intel.com>

---

## [36] Huang, Kai — 2025-10-30
*Subject: Re: [PATCH v4 25/28] KVM: TDX: Don't copy "cmd" back to userspace for
 KVM_TDX_CAPABILITIES*

On Thu, 2025-10-30 at 13:09 -0700, Sean Christopherson wrote:
> Don't copy the kvm_tdx_cmd structure back to userspace when handling
> KVM_TDX_CAPABILITIES, as tdx_get_capabilities() doesn't modify hw_error or

Reviewed-by: Kai Huang <kai.huang@intel.com>

---

## [37] Huang, Kai — 2025-10-30
*Subject: Re: [PATCH v4 26/28] KVM: TDX: Guard VM state transitions with "all"
 the locks*

On Thu, 2025-10-30 at 13:09 -0700, Sean Christopherson wrote:
> Acquire kvm->lock, kvm->slots_lock, and all vcpu->mutex locks when
> servicing ioctls that (a) transition the TD to a new state, i.e. when
       ^
       interfering

> to service the vCPU-scoped ioctls to avoid a lock inversion problem, e.g.
> due to taking vcpu->mutex outside kvm->lock.

Reviewed-by: Kai Huang <kai.huang@intel.com>

---

## [38] Huang, Kai — 2025-10-30
*Subject: Re: [PATCH v4 27/28] KVM: TDX: Bug the VM if extending the initial
 measurement fails*

On Thu, 2025-10-30 at 13:09 -0700, Sean Christopherson wrote:
> WARN and terminate the VM if TDH_MR_EXTEND fails, as extending the
> measurement should fail if and only if there is a KVM bug, or if the S-EPT

Reviewed-by: Kai Huang <kai.huang@intel.com>

---

## [39] Huang, Kai — 2025-10-30
*Subject: Re: [PATCH v4 28/28] KVM: TDX: Fix list_add corruption during
 vcpu_load()*

On Thu, 2025-10-30 at 13:09 -0700, Sean Christopherson wrote:
> From: Yan Zhao <yan.y.zhao@intel.com>
> 

Reviewed-by: Kai Huang <kai.huang@intel.com>

---

## [40] Huang, Kai — 2025-10-30
*Subject: Re: [PATCH v4 00/28] KVM: x86/mmu: TDX post-populate cleanups*

On Thu, 2025-10-30 at 13:09 -0700, Sean Christopherson wrote:
> Non-x86 folks, as with v3, patches 1 and 2 are likely the only thing of
> interest here.  They make kvm_arch_vcpu_async_ioctl() mandatory and then

I pulled this series to local, applied to kvm-x86/next and sanity tested
that booting/destroying two TDs worked fine, so:

Tested-by: Kai Huang <kai.huang@intel.com>

---

## [41] Huang, Kai — 2025-10-30
*Subject: Re: [PATCH v4 18/28] KVM: TDX: Combine KVM_BUG_ON + pr_tdx_error()
 into TDX_BUG_ON()*

On Thu, 2025-10-30 at 13:09 -0700, Sean Christopherson wrote:
> Add TDX_BUG_ON() macros (with varying numbers of arguments) to deduplicate
> the myriad flows that do KVM_BUG_ON()/WARN_ON_ONCE() followed by a call to

Reviewed-by: Kai Huang <kai.huang@intel.com>

---

## [42] Sean Christopherson — 2025-10-30
*Subject: Re: [PATCH v4 12/28] KVM: TDX: WARN if mirror SPTE doesn't have full
 RWX when creating S-EPT mapping*

On Thu, Oct 30, 2025, Kai Huang wrote:
> On Thu, 2025-10-30 at 13:09 -0700, Sean Christopherson wrote:
> > Pass in the mirror_spte to kvm_x86_ops.set_external_spte() to provide

Very loosely: WARN if there's a decent chance carrying on might be fine,
KVM_BUG_ON() if there's a good chance carrying on will crash the host and/or
corrupt the guest, e.g. if KVM suspects a hardware/TDX-Module issue.

---

## [43] Huang, Kai — 2025-10-30
*Subject: Re: [PATCH v4 12/28] KVM: TDX: WARN if mirror SPTE doesn't have full
 RWX when creating S-EPT mapping*

On Thu, 2025-10-30 at 16:40 -0700, Sean Christopherson wrote:
> On Thu, Oct 30, 2025, Kai Huang wrote:
> > On Thu, 2025-10-30 at 13:09 -0700, Sean Christopherson wrote:

Makes sense.  Thanks.

---

## [44] Binbin Wu — 2025-10-31
*Subject: Re: [PATCH v4 04/28] KVM: x86/mmu: Add dedicated API to map
 guest_memfd pfn into TDP MMU*

On 10/31/2025 4:09 AM, Sean Christopherson wrote:
> Add and use a new API for mapping a private pfn from guest_memfd into the
> TDP MMU from TDX's post-populate hook instead of partially open-coding the

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

---

## [45] Binbin Wu — 2025-10-31
*Subject: Re: [PATCH v4 12/28] KVM: TDX: WARN if mirror SPTE doesn't have full
 RWX when creating S-EPT mapping*

On 10/31/2025 4:09 AM, Sean Christopherson wrote:
> Pass in the mirror_spte to kvm_x86_ops.set_external_spte() to provide
> symmetry with .remove_external_spte(), and assert in TDX that the mirror

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

---

## [46] Yan Zhao — 2025-10-31
*Subject: Re: [PATCH v4 10/28] KVM: TDX: Fold tdx_sept_drop_private_spte()
 into tdx_sept_remove_private_spte()*

On Thu, Oct 30, 2025 at 01:09:33PM -0700, Sean Christopherson wrote:
> Fold tdx_sept_drop_private_spte() into tdx_sept_remove_private_spte() as a
> step towards having "remove" be the only and only function that deals with
only and only?

> removing/zapping/dropping a SPTE, e.g. to avoid having to differentiate
> between "zap", "drop", and "remove".  Eliminating the "drop" helper also

---

## [47] Yan Zhao — 2025-10-31
*Subject: Re: [PATCH v4 26/28] KVM: TDX: Guard VM state transitions with "all"
 the locks*

On Thu, Oct 30, 2025 at 01:09:49PM -0700, Sean Christopherson wrote:
> Acquire kvm->lock, kvm->slots_lock, and all vcpu->mutex locks when
> servicing ioctls that (a) transition the TD to a new state, i.e. when
s/kvm_mmu_zap_all_fast/kvm_mmu_zap_memslot

> from interefering.  Use the recently-renamed kvm_arch_vcpu_unlocked_ioctl()
> to service the vCPU-scoped ioctls to avoid a lock inversion problem, e.g.
reverse xmas tree ?

>  	struct kvm_tdx_cmd cmd;
>  	int r;

---

## [48] Yan Zhao — 2025-10-31
*Subject: Re: [PATCH v4 08/28] KVM: TDX: Drop superfluous page pinning in
 S-EPT management*

>   - Increasing the folio reference count only upon S-EPT zapping failure[5].
Nit: There's a warning:

WARNING: Prefer a maximum 75 chars per line (possible unwrapped commit description?)

---

## [49] Binbin Wu — 2025-10-31
*Subject: Re: [PATCH v4 16/28] KVM: TDX: ADD pages to the TD image while
 populating mirror EPT entries*

On 10/31/2025 4:09 AM, Sean Christopherson wrote:
> When populating the initial memory image for a TDX guest, ADD pages to the
> TD as part of establishing the mappings in the mirror EPT, as opposed to
Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

One nit below.

> ---
>   arch/x86/kvm/vmx/tdx.c | 106 ++++++++++++++---------------------------
[...]
> diff --git a/arch/x86/kvm/vmx/tdx.h b/arch/x86/kvm/vmx/tdx.h
> index ca39a9391db1..1b00adbbaf77 100644
tdx_mem_page_add -> tdx_mem_page_add()

> +	 * Protected by slots_lock, and non-NULL only when mapping a private
> +	 * pfn via tdx_gmem_post_populate().

---

## [50] Yan Zhao — 2025-10-31
*Subject: Re: [PATCH v4 00/28] KVM: x86/mmu: TDX post-populate cleanups*

Reviewed-by: Yan Zhao <yan.y.zhao@intel.com>
Tested-by: Yan Zhao <yan.y.zhao@intel.com>

---

## [51] Binbin Wu — 2025-10-31
*Subject: Re: [PATCH v4 17/28] KVM: TDX: Fold tdx_sept_zap_private_spte() into
 tdx_sept_remove_private_spte()*

On 10/31/2025 4:09 AM, Sean Christopherson wrote:
> Do TDH_MEM_RANGE_BLOCK directly in tdx_sept_remove_private_spte() instead
> of using a one-off helper now that the nr_premapped tracking is gone.

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

---

## [52] Binbin Wu — 2025-10-31
*Subject: Re: [PATCH v4 18/28] KVM: TDX: Combine KVM_BUG_ON + pr_tdx_error()
 into TDX_BUG_ON()*

On 10/31/2025 4:09 AM, Sean Christopherson wrote:
> Add TDX_BUG_ON() macros (with varying numbers of arguments) to deduplicate
> the myriad flows that do KVM_BUG_ON()/WARN_ON_ONCE() followed by a call to

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

---

## [53] Binbin Wu — 2025-10-31
*Subject: Re: [PATCH v4 19/28] KVM: TDX: Derive error argument names from the
 local variable names*

On 10/31/2025 4:09 AM, Sean Christopherson wrote:
> When printing SEAMCALL errors, use the name of the variable holding an
> error parameter instead of the register from whence it came, so that flows

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

> ---
>   arch/x86/kvm/vmx/tdx.c | 13 +++++++------

---

## [54] Binbin Wu — 2025-10-31
*Subject: Re: [PATCH v4 20/28] KVM: TDX: Assert that mmu_lock is held for write
 when removing S-EPT entries*

On 10/31/2025 4:09 AM, Sean Christopherson wrote:
> Unconditionally assert that mmu_lock is held for write when removing S-EPT
> entries, not just when removing S-EPT entries triggers certain conditions,
                                                                 ^
                                                               assert
> mmu_lock is held for write (tdp_mmu_set_spte() via lockdep, and
> handle_removed_pt() via KVM_BUG_ON()).

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

> ---
>   arch/x86/kvm/vmx/tdx.c | 7 +++++++

---

## [55] Binbin Wu — 2025-10-31
*Subject: Re: [PATCH v4 21/28] KVM: TDX: Add macro to retry SEAMCALLs when
 forcing vCPUs out of guest*

On 10/31/2025 4:09 AM, Sean Christopherson wrote:
> Add a macro to handle kicking vCPUs out of the guest and retrying
> SEAMCALLs on -EBUSY instead of providing small helpers to be used by each

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

---

## [56] Binbin Wu — 2025-10-31
*Subject: Re: [PATCH v4 22/28] KVM: TDX: Add tdx_get_cmd() helper to get and
 validate sub-ioctl command*

On 10/31/2025 4:09 AM, Sean Christopherson wrote:
> Add a helper to copy a kvm_tdx_cmd structure from userspace and verify
> that must-be-zero fields are indeed zero.

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

---

## [57] Binbin Wu — 2025-10-31
*Subject: Re: [PATCH v4 23/28] KVM: TDX: Convert INIT_MEM_REGION and INIT_VCPU
 to "unlocked" vCPU ioctl*

On 10/31/2025 4:09 AM, Sean Christopherson wrote:
> Handle the KVM_TDX_INIT_MEM_REGION and KVM_TDX_INIT_VCPU vCPU sub-ioctls
> in the unlocked variant, i.e. outside of vcpu->mutex, in anticipation of

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

---

## [58] Binbin Wu — 2025-10-31
*Subject: Re: [PATCH v4 24/28] KVM: TDX: Use guard() to acquire kvm->lock in
 tdx_vm_ioctl()*

On 10/31/2025 4:09 AM, Sean Christopherson wrote:
> Use guard() in tdx_vm_ioctl() to tidy up the code a small amount, but more
> importantly to minimize the diff of a future change, which will use

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

---

## [59] Sean Christopherson — 2025-10-31
*Subject: Re: [PATCH v4 08/28] KVM: TDX: Drop superfluous page pinning in S-EPT management*

On Fri, Oct 31, 2025, Yan Zhao wrote:
> >   - Increasing the folio reference count only upon S-EPT zapping failure[5].
> Nit: There's a warning:

Checkpatch is a (very helpful) tool, but it is not authoritative in any way.
Similar to the how "wrap at 80 chars" is a soft rule that can and should be
broken depending on context, checkpatch should also be ignored for things like
this.  If someone says that the period making the line "too long" actually makes
this unreadable for them, then they're just trolling at that point :-)

---

## [60] Edgecombe, Rick P — 2025-10-31
*Subject: Re: [PATCH v4 00/28] KVM: x86/mmu: TDX post-populate cleanups*

On Thu, 2025-10-30 at 13:09 -0700, Sean Christopherson wrote:
> v4:
>  - Collect reviews/acks.

Do you want someone to follow up with a v2 of this after the series lands? (with
Binbin's verbiage comments incorporated)

https://lore.kernel.org/kvm/20251028002824.1470939-1-rick.p.edgecombe@intel.com/#t

---

## [61] Sean Christopherson — 2025-10-31
*Subject: Re: [PATCH v4 26/28] KVM: TDX: Guard VM state transitions with "all"
 the locks*

On Fri, Oct 31, 2025, Yan Zhao wrote:
> On Thu, Oct 30, 2025 at 01:09:49PM -0700, Sean Christopherson wrote:
> > Acquire kvm->lock, kvm->slots_lock, and all vcpu->mutex locks when

Argh!  Third time's a charm?  Hopefully...

> > @@ -3170,7 +3208,8 @@ static int tdx_vcpu_init_mem_region(struct kvm_vcpu *vcpu, struct kvm_tdx_cmd *c
> >  

No, because the shorter line generates an input to the longer line.  E.g. we could
do this if we really, really want an xmas tree:

	struct kvm_tdx *kvm_tdx = to_kvm_tdx(vcpu->kvm);
	struct kvm *kvm = vcpu->kvm;

but this won't compile

	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
	struct kvm *kvm = vcpu->kvm;

---

## [62] Yan Zhao — 2025-11-03
*Subject: Re: [PATCH v4 26/28] KVM: TDX: Guard VM state transitions with "all"
 the locks*

On Fri, Oct 31, 2025 at 10:34:51AM -0700, Sean Christopherson wrote:
> On Fri, Oct 31, 2025, Yan Zhao wrote:
> > On Thu, Oct 30, 2025 at 01:09:49PM -0700, Sean Christopherson wrote:
Ah! Sorry. My attention was caught by the line length, completely missing the
dependency :(

---

## [63] Binbin Wu — 2025-11-04
*Subject: Re: [PATCH v4 27/28] KVM: TDX: Bug the VM if extending the initial
 measurement fails*

On 10/31/2025 4:09 AM, Sean Christopherson wrote:
> WARN and terminate the VM if TDH_MR_EXTEND fails, as extending the
> measurement should fail if and only if there is a KVM bug, or if the S-EPT

Nit:
It sounds like TDX is using the memslot for the APIC page, but for a TD, the
memslot for the APIC page is never initialized or used?

> and so can't be used for the initial image, which means that too is
> mutually exclusive irrespective of locking).

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

> ---
>   arch/x86/kvm/vmx/tdx.c | 24 +++++++++++++-----------

---

## [64] Sean Christopherson — 2025-11-04
*Subject: Re: [PATCH v4 00/28] KVM: x86/mmu: TDX post-populate cleanups*

On Fri, Oct 31, 2025, Rick P Edgecombe wrote:
> On Thu, 2025-10-30 at 13:09 -0700, Sean Christopherson wrote:
> > v4:

Feel free to send a v2 now.  Or just reply to Binbin's mail with the updated
comment.

> https://lore.kernel.org/kvm/20251028002824.1470939-1-rick.p.edgecombe@intel.com/#t

---

## [65] Sean Christopherson — 2025-11-04
*Subject: Re: [PATCH v4 27/28] KVM: TDX: Bug the VM if extending the initial
 measurement fails*

On Tue, Nov 04, 2025, Binbin Wu wrote:
> 
> 

Oh!  Good point.  I'll tweak that snippet when applying.

---

## [66] Sean Christopherson — 2025-11-10
*Subject: Re: [PATCH v4 00/28] KVM: x86/mmu: TDX post-populate cleanups*

On Thu, 30 Oct 2025 13:09:23 -0700, Sean Christopherson wrote:
> Non-x86 folks, as with v3, patches 1 and 2 are likely the only thing of
> interest here.  They make kvm_arch_vcpu_async_ioctl() mandatory and then

Applied to kvm-x86 tdx, with fixups for the various typos.  Thanks for all the
reviews and testing!

Other KVM arch maintainers, please holler if you want a stable tag for the
kvm_arch_vcpu_async_ioctl() changes (they're based directly on v6.18-rc4).

[01/28] KVM: Make support for kvm_arch_vcpu_async_ioctl() mandatory
        https://github.com/kvm-x86/linux/commit/0a0da3f92118
[02/28] KVM: Rename kvm_arch_vcpu_async_ioctl() to kvm_arch_vcpu_unlocked_ioctl()
        https://github.com/kvm-x86/linux/commit/50efc2340a59
[03/28] KVM: TDX: Drop PROVE_MMU=y sanity check on to-be-populated mappings
        https://github.com/kvm-x86/linux/commit/5294a4b93e07
[04/28] KVM: x86/mmu: Add dedicated API to map guest_memfd pfn into TDP MMU
        https://github.com/kvm-x86/linux/commit/3ab3283dbb2c
[05/28] KVM: x86/mmu: WARN if KVM attempts to map into an invalid TDP MMU root
        https://github.com/kvm-x86/linux/commit/c1f173fb3389
[06/28] Revert "KVM: x86/tdp_mmu: Add a helper function to walk down the TDP MMU"
        https://github.com/kvm-x86/linux/commit/fe7413e39810
[07/28] KVM: x86/mmu: Rename kvm_tdp_map_page() to kvm_tdp_page_prefault()
        https://github.com/kvm-x86/linux/commit/6de2fb089bb2
[08/28] KVM: TDX: Drop superfluous page pinning in S-EPT management
        https://github.com/kvm-x86/linux/commit/ce7b5695397b
[09/28] KVM: TDX: Return -EIO, not -EINVAL, on a KVM_BUG_ON() condition
        https://github.com/kvm-x86/linux/commit/e6348c90dda9
[10/28] KVM: TDX: Fold tdx_sept_drop_private_spte() into tdx_sept_remove_private_spte()
        https://github.com/kvm-x86/linux/commit/b836503300dc
[11/28] KVM: x86/mmu: Drop the return code from kvm_x86_ops.remove_external_spte()
        https://github.com/kvm-x86/linux/commit/7139c8606505
[12/28] KVM: TDX: WARN if mirror SPTE doesn't have full RWX when creating S-EPT mapping
        https://github.com/kvm-x86/linux/commit/b9d5cf6de0b6
[13/28] KVM: TDX: Avoid a double-KVM_BUG_ON() in tdx_sept_zap_private_spte()
        https://github.com/kvm-x86/linux/commit/24adff397052
[14/28] KVM: TDX: Use atomic64_dec_return() instead of a poor equivalent
        https://github.com/kvm-x86/linux/commit/af96d5452e5e
[15/28] KVM: TDX: Fold tdx_mem_page_record_premap_cnt() into its sole caller
        https://github.com/kvm-x86/linux/commit/b4b2b6eda5af
[16/28] KVM: TDX: ADD pages to the TD image while populating mirror EPT entries
        https://github.com/kvm-x86/linux/commit/6b5b71ffabf9
[17/28] KVM: TDX: Fold tdx_sept_zap_private_spte() into tdx_sept_remove_private_spte()
        https://github.com/kvm-x86/linux/commit/14c9938619be
[18/28] KVM: TDX: Combine KVM_BUG_ON + pr_tdx_error() into TDX_BUG_ON()
        https://github.com/kvm-x86/linux/commit/597d7068702f
[19/28] KVM: TDX: Derive error argument names from the local variable names
        https://github.com/kvm-x86/linux/commit/55560b6be5bc
[20/28] KVM: TDX: Assert that mmu_lock is held for write when removing S-EPT entries
        https://github.com/kvm-x86/linux/commit/2ff14116982c
[21/28] KVM: TDX: Add macro to retry SEAMCALLs when forcing vCPUs out of guest
        https://github.com/kvm-x86/linux/commit/3d626ce5a8cc
[22/28] KVM: TDX: Add tdx_get_cmd() helper to get and validate sub-ioctl command
        https://github.com/kvm-x86/linux/commit/59d5c1ed6df2
[23/28] KVM: TDX: Convert INIT_MEM_REGION and INIT_VCPU to "unlocked" vCPU ioctl
        https://github.com/kvm-x86/linux/commit/94428e3ba325
[24/28] KVM: TDX: Use guard() to acquire kvm->lock in tdx_vm_ioctl()
        https://github.com/kvm-x86/linux/commit/0b76e827b29d
[25/28] KVM: TDX: Don't copy "cmd" back to userspace for KVM_TDX_CAPABILITIES
        https://github.com/kvm-x86/linux/commit/f26061fe2c25
[26/28] KVM: TDX: Guard VM state transitions with "all" the locks
        https://github.com/kvm-x86/linux/commit/15945e9ec195
[27/28] KVM: TDX: Bug the VM if extending the initial measurement fails
        https://github.com/kvm-x86/linux/commit/ad44aa4c5d3f
[28/28] KVM: TDX: Fix list_add corruption during vcpu_load()
        https://github.com/kvm-x86/linux/commit/1e3a825c9ec9

--
https://github.com/kvm-x86/linux/tree/next

---
