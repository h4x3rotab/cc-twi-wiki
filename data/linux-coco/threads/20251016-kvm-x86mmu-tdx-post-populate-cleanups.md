---
title: 'KVM: x86/mmu: TDX post-populate cleanups'
date: 2025-10-16
last_reply: 2025-11-19
message_count: 97
participants: ['Sean Christopherson', 'Claudio Imbrenda', 'Yan Zhao', 'Edgecombe, Rick P', 'Binbin Wu', 'Huang, Kai']
---

## [1] Sean Christopherson — 2025-10-16

Non-x86 folks, patches 1 and 2 are likely the only thing of interest here.
They make kvm_arch_vcpu_async_ioctl() mandatory and then rename it to
kvm_arch_vcpu_unlocked_ioctl().  Hopefully they're boring?

As for the x86 side...

Clean up the TDX post-populate paths (and many tangentially related paths) to
address locking issues between gmem and TDX's post-populate hook[*], and
within KVM itself (KVM doesn't ensure full mutual exclusivity between paths
that for all intents and purposes the TDX-Module requires to be serialized).

Compile tested only again on my end, but Rick and Yan took v2 for a spin, so I
dropped the RFC.

[*] http://lore.kernel.org/all/aG_pLUlHdYIZ2luh@google.com

v3:
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

Sean Christopherson (23):
  KVM: Make support for kvm_arch_vcpu_async_ioctl() mandatory
  KVM: Rename kvm_arch_vcpu_async_ioctl() to
    kvm_arch_vcpu_unlocked_ioctl()
  KVM: TDX: Drop PROVE_MMU=y sanity check on to-be-populated mappings
  KVM: x86/mmu: Add dedicated API to map guest_memfd pfn into TDP MMU
  Revert "KVM: x86/tdp_mmu: Add a helper function to walk down the TDP
    MMU"
  KVM: x86/mmu: Rename kvm_tdp_map_page() to kvm_tdp_page_prefault()
  KVM: TDX: Return -EIO, not -EINVAL, on a KVM_BUG_ON() condition
  KVM: TDX: Fold tdx_sept_drop_private_spte() into
    tdx_sept_remove_private_spte()
  KVM: x86/mmu: Drop the return code from
    kvm_x86_ops.remove_external_spte()
  KVM: TDX: Avoid a double-KVM_BUG_ON() in tdx_sept_zap_private_spte()
  KVM: TDX: Use atomic64_dec_return() instead of a poor equivalent
  KVM: TDX: Fold tdx_mem_page_record_premap_cnt() into its sole caller
  KVM: TDX: Bug the VM if extended the initial measurement fails
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
  KVM: TDX: Guard VM state transitions with "all" the locks

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
 arch/x86/include/asm/kvm_host.h    |   5 +-
 arch/x86/kvm/mmu.h                 |   3 +-
 arch/x86/kvm/mmu/mmu.c             |  66 ++-
 arch/x86/kvm/mmu/tdp_mmu.c         |  45 +-
 arch/x86/kvm/vmx/main.c            |   9 +
 arch/x86/kvm/vmx/tdx.c             | 638 ++++++++++++++---------------
 arch/x86/kvm/vmx/tdx.h             |   8 +-
 arch/x86/kvm/vmx/x86_ops.h         |   1 +
 arch/x86/kvm/x86.c                 |  13 +
 include/linux/kvm_host.h           |  14 +-
 virt/kvm/Kconfig                   |   3 -
 virt/kvm/kvm_main.c                |   6 +-
 24 files changed, 422 insertions(+), 421 deletions(-)


base-commit: f222788458c8a7753d43befef2769cd282dc008e

---

## [2] Sean Christopherson — 2025-10-16
*Subject: [PATCH v3 01/25] KVM: Make support for kvm_arch_vcpu_async_ioctl() mandatory*

Implement kvm_arch_vcpu_async_ioctl() "natively" in x86 and arm64 instead
of relying on an #ifdef'd stub, and drop HAVE_KVM_VCPU_ASYNC_IOCTL in
anticipation of using the API on x86.  Once x86 uses the API, providing a
stub for one architecture and having all other architectures opt-in
requires more code than simply implementing the API in the lone holdout.

Eliminating the Kconfig will also reduce churn if the API is renamed in
the future (spoiler alert).

No functional change intended.

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
index f21d1b7f20f8..785aaaee6a5d 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -1828,6 +1828,12 @@ long kvm_arch_vcpu_ioctl(struct file *filp,
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

## [3] Sean Christopherson — 2025-10-16
*Subject: [PATCH v3 02/25] KVM: Rename kvm_arch_vcpu_async_ioctl() to kvm_arch_vcpu_unlocked_ioctl()*

Rename the "async" ioctl API to "unlocked" so that upcoming usage in x86's
TDX code doesn't result in a massive misnomer.  To avoid having to retry
SEAMCALLs, TDX needs to acquire kvm->lock *and* all vcpu->mutex locks, and
acquiring all of those locks after/inside the current vCPU's mutex is a
non-starter.  However, TDX also needs to acquire the vCPU's mutex and load
the vCPU, i.e. the handling is very much not async to the vCPU.

No functional change intended.

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
index 785aaaee6a5d..e8d654024608 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -1828,8 +1828,8 @@ long kvm_arch_vcpu_ioctl(struct file *filp,
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
index b7a0ae2a7b20..b7db1d5f71a8 100644
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

## [4] Sean Christopherson — 2025-10-16
*Subject: [PATCH v3 03/25] KVM: TDX: Drop PROVE_MMU=y sanity check on
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

## [5] Sean Christopherson — 2025-10-16
*Subject: [PATCH v3 04/25] KVM: x86/mmu: Add dedicated API to map guest_memfd
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

Cc: Michael Roth <michael.roth@amd.com>
Cc: Yan Zhao <yan.y.zhao@intel.com>
Cc: Ira Weiny <ira.weiny@intel.com>
Cc: Vishal Annapurve <vannapurve@google.com>
Cc: Rick Edgecombe <rick.p.edgecombe@intel.com>
Link: https://lore.kernel.org/all/20250709232103.zwmufocd3l7sqk7y@amd.com
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/mmu.h     |  1 +
 arch/x86/kvm/mmu/mmu.c | 60 +++++++++++++++++++++++++++++++++++++++++-
 arch/x86/kvm/vmx/tdx.c | 10 +++----
 3 files changed, 63 insertions(+), 8 deletions(-)

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
index 18d69d48bc55..ba5cca825a7f 100644
--- a/arch/x86/kvm/mmu/mmu.c
+++ b/arch/x86/kvm/mmu/mmu.c
@@ -5014,6 +5014,65 @@ long kvm_arch_vcpu_pre_fault_memory(struct kvm_vcpu *vcpu,
 	return min(range->size, end - range->gpa);
 }
 
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
+
 static void nonpaging_init_context(struct kvm_mmu *context)
 {
 	context->page_fault = nonpaging_page_fault;
@@ -5997,7 +6056,6 @@ int kvm_mmu_load(struct kvm_vcpu *vcpu)
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

## [6] Sean Christopherson — 2025-10-16
*Subject: [PATCH v3 05/25] Revert "KVM: x86/tdp_mmu: Add a helper function to
 walk down the TDP MMU"*

Remove the helper and exports that were added to allow TDX code to reuse
kvm_tdp_map_page() for its gmem post-populate flow now that a dedicated
TDP MMU API is provided to install a mapping given a gfn+pfn pair.

This reverts commit 2608f105760115e94a03efd9f12f8fbfd1f9af4b.

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
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
index ba5cca825a7f..3711dba92440 100644
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
index c5734ca5c17d..9b4006c2120e 100644
--- a/arch/x86/kvm/mmu/tdp_mmu.c
+++ b/arch/x86/kvm/mmu/tdp_mmu.c
@@ -1939,13 +1939,16 @@ bool kvm_tdp_mmu_write_protect_gfn(struct kvm *kvm,
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
@@ -1954,36 +1957,6 @@ static int __kvm_tdp_mmu_get_walk(struct kvm_vcpu *vcpu, u64 addr, u64 *sptes,
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

## [7] Sean Christopherson — 2025-10-16
*Subject: [PATCH v3 06/25] KVM: x86/mmu: Rename kvm_tdp_map_page() to kvm_tdp_page_prefault()*

Rename kvm_tdp_map_page() to kvm_tdp_page_prefault() now that it's used
only by kvm_arch_vcpu_pre_fault_memory().

No functional change intended.

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/mmu/mmu.c | 6 +++---
 1 file changed, 3 insertions(+), 3 deletions(-)

diff --git a/arch/x86/kvm/mmu/mmu.c b/arch/x86/kvm/mmu/mmu.c
index 3711dba92440..94d7f32a03b6 100644
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

## [8] Sean Christopherson — 2025-10-16
*Subject: [PATCH v3 07/25] KVM: TDX: Drop superfluous page pinning in S-EPT management*

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

## [9] Sean Christopherson — 2025-10-16
*Subject: [PATCH v3 08/25] KVM: TDX: Return -EIO, not -EINVAL, on a
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

## [10] Sean Christopherson — 2025-10-16
*Subject: [PATCH v3 09/25] KVM: TDX: Fold tdx_sept_drop_private_spte() into tdx_sept_remove_private_spte()*

Fold tdx_sept_drop_private_spte() into tdx_sept_remove_private_spte() to
avoid having to differnatiate between "zap", "drop", and "remove", and to
eliminate dead code due to redundant checks, e.g. on an HKID being
assigned.

No functional change intended.

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>
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

## [11] Sean Christopherson — 2025-10-16
*Subject: [PATCH v3 10/25] KVM: x86/mmu: Drop the return code from kvm_x86_ops.remove_external_spte()*

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
index 48598d017d6f..7e92aebd07e8 100644
--- a/arch/x86/include/asm/kvm_host.h
+++ b/arch/x86/include/asm/kvm_host.h
@@ -1855,8 +1855,8 @@ struct kvm_x86_ops {
 				 void *external_spt);
 
 	/* Update external page table from spte getting removed, and flush TLB. */
-	int (*remove_external_spte)(struct kvm *kvm, gfn_t gfn, enum pg_level level,
-				    kvm_pfn_t pfn_for_gfn);
+	void (*remove_external_spte)(struct kvm *kvm, gfn_t gfn, enum pg_level level,
+				     u64 spte);
 
 	bool (*has_wbinvd_exit)(void);
 
diff --git a/arch/x86/kvm/mmu/tdp_mmu.c b/arch/x86/kvm/mmu/tdp_mmu.c
index 9b4006c2120e..c09c25f3f93b 100644
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
index abea9b3d08cf..f5cbcbf4e663 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1806,12 +1806,12 @@ static int tdx_sept_free_private_spt(struct kvm *kvm, gfn_t gfn,
 	return tdx_reclaim_page(virt_to_page(private_spt));
 }
 
-static int tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
-					enum pg_level level, kvm_pfn_t pfn)
+static void tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
+					 enum pg_level level, u64 spte)
 {
+	struct page *page = pfn_to_page(spte_to_pfn(spte));
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

## [12] Sean Christopherson — 2025-10-16
*Subject: [PATCH v3 11/25] KVM: TDX: Avoid a double-KVM_BUG_ON() in tdx_sept_zap_private_spte()*

Return -EIO immediately from tdx_sept_zap_private_spte() if the number of
to-be-added pages underflows, so that the following "KVM_BUG_ON(err, kvm)"
isn't also triggered.  Isolating the check from the "is premap error"
if-statement will also allow adding a lockdep assertion that premap errors
are encountered if and only if slots_lock is held.

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/vmx/tdx.c | 6 ++++--
 1 file changed, 4 insertions(+), 2 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index f5cbcbf4e663..220989a1e085 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1721,8 +1721,10 @@ static int tdx_sept_zap_private_spte(struct kvm *kvm, gfn_t gfn,
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

## [13] Sean Christopherson — 2025-10-16
*Subject: [PATCH v3 12/25] KVM: TDX: Use atomic64_dec_return() instead of a
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
index 220989a1e085..6c0adc1b3bd5 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1722,10 +1722,9 @@ static int tdx_sept_zap_private_spte(struct kvm *kvm, gfn_t gfn,
 		tdx_no_vcpus_enter_stop(kvm);
 	}
 	if (tdx_is_sept_zap_err_due_to_premap(kvm_tdx, err, entry, level)) {
-		if (KVM_BUG_ON(!atomic64_read(&kvm_tdx->nr_premapped), kvm))
+		if (KVM_BUG_ON(atomic64_dec_return(&kvm_tdx->nr_premapped) < 0, kvm))
 			return -EIO;
 
-		atomic64_dec(&kvm_tdx->nr_premapped);
 		return 0;
 	}
 
@@ -3157,8 +3156,7 @@ static int tdx_gmem_post_populate(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
 		goto out;
 	}
 
-	if (!KVM_BUG_ON(!atomic64_read(&kvm_tdx->nr_premapped), kvm))
-		atomic64_dec(&kvm_tdx->nr_premapped);
+	KVM_BUG_ON(atomic64_dec_return(&kvm_tdx->nr_premapped) < 0, kvm);
 
 	if (arg->flags & KVM_TDX_MEASURE_MEMORY_REGION) {
 		for (i = 0; i < PAGE_SIZE; i += TDX_EXTENDMR_CHUNKSIZE) {

---

## [14] Sean Christopherson — 2025-10-16
*Subject: [PATCH v3 13/25] KVM: TDX: Fold tdx_mem_page_record_premap_cnt() into
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
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/vmx/tdx.c | 49 ++++++++++++++++++------------------------
 1 file changed, 21 insertions(+), 28 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 6c0adc1b3bd5..c37591730cc5 100644
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
 				     enum pg_level level, kvm_pfn_t pfn)
 {
@@ -1638,14 +1615,30 @@ static int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn,
 		return -EIO;
 
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
+	 * KVM_TDX_FINALIZE_VM checks the counter to ensure all mapped pages
+	 * have been added to the image, to prevent running the TD with a
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

## [15] Sean Christopherson — 2025-10-16
*Subject: [PATCH v3 14/25] KVM: TDX: Bug the VM if extended the initial
 measurement fails*

WARN and terminate the VM if TDH_MR_EXTEND fails, as extending the
measurement should fail if and only if there is a KVM bug, or if the S-EPT
mapping is invalid, and it should be impossible for the S-EPT mappings to
be removed between kvm_tdp_mmu_map_private_pfn() and tdh_mr_extend().

Holding slots_lock prevents zaps due to memslot updates,
filemap_invalidate_lock() prevents zaps due to guest_memfd PUNCH_HOLE,
and all usage of kvm_zap_gfn_range() is mutually exclusive with S-EPT
entries that can be used for the initial image.  The call from sev.c is
obviously mutually exclusive, TDX disallows KVM_X86_QUIRK_IGNORE_GUEST_PAT
so same goes for kvm_noncoherent_dma_assignment_start_or_stop, and while
__kvm_set_or_clear_apicv_inhibit() can likely be tripped while building the
image, the APIC page has its own non-guest_memfd memslot and so can't be
used for the initial image, which means that too is mutually exclusive.

Opportunistically switch to "goto" to jump around the measurement code,
partly to make it clear that KVM needs to bail entirely if extending the
measurement fails, partly in anticipation of reworking how and when
TDH_MEM_PAGE_ADD is done.

Fixes: d789fa6efac9 ("KVM: TDX: Handle vCPU dissociation")
Signed-off-by: Yan Zhao <yan.y.zhao@intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/vmx/tdx.c | 24 ++++++++++++++++--------
 1 file changed, 16 insertions(+), 8 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index c37591730cc5..f4bab75d3ffb 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -3151,14 +3151,22 @@ static int tdx_gmem_post_populate(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
 
 	KVM_BUG_ON(atomic64_dec_return(&kvm_tdx->nr_premapped) < 0, kvm);
 
-	if (arg->flags & KVM_TDX_MEASURE_MEMORY_REGION) {
-		for (i = 0; i < PAGE_SIZE; i += TDX_EXTENDMR_CHUNKSIZE) {
-			err = tdh_mr_extend(&kvm_tdx->td, gpa + i, &entry,
-					    &level_state);
-			if (err) {
-				ret = -EIO;
-				break;
-			}
+	if (!(arg->flags & KVM_TDX_MEASURE_MEMORY_REGION))
+		goto out;
+
+	/*
+	 * Note, MR.EXTEND can fail if the S-EPT mapping is somehow removed
+	 * between mapping the pfn and now, but slots_lock prevents memslot
+	 * updates, filemap_invalidate_lock() prevents guest_memfd updates,
+	 * mmu_notifier events can't reach S-EPT entries, and KVM's internal
+	 * zapping flows are mutually exclusive with S-EPT mappings.
+	 */
+	for (i = 0; i < PAGE_SIZE; i += TDX_EXTENDMR_CHUNKSIZE) {
+		err = tdh_mr_extend(&kvm_tdx->td, gpa + i, &entry, &level_state);
+		if (KVM_BUG_ON(err, kvm)) {
+			pr_tdx_error_2(TDH_MR_EXTEND, err, entry, level_state);
+			ret = -EIO;
+			goto out;
 		}
 	}

---

## [16] Sean Christopherson — 2025-10-16
*Subject: [PATCH v3 15/25] KVM: TDX: ADD pages to the TD image while populating
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
overall cognitive load, as the managemented of nr_premapped with respect
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
S-EPT entries uring KVM_TDX_INIT_MEM_REGION, then extending the
measurement can also be moved into the S-EPT mapping path (again, only if
absolutely necessary).  P.S. _If_ MR.EXTEND is moved into the S-EPT path,
take care not to return an error up the stack if TDH_MR_EXTEND fails, as
removing the M-EPT entry but not the S-EPT entry would result in
inconsistent state!

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/vmx/tdx.c | 114 ++++++++++++++---------------------------
 arch/x86/kvm/vmx/tdx.h |   8 ++-
 2 files changed, 45 insertions(+), 77 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index f4bab75d3ffb..76030461c8f7 100644
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
@@ -1624,19 +1650,10 @@ static int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn,
 
 	/*
 	 * If the TD isn't finalized/runnable, then userspace is initializing
-	 * the VM image via KVM_TDX_INIT_MEM_REGION.  Increment the number of
-	 * pages that need to be mapped and initialized via TDH.MEM.PAGE.ADD.
-	 * KVM_TDX_FINALIZE_VM checks the counter to ensure all mapped pages
-	 * have been added to the image, to prevent running the TD with a
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
@@ -1662,39 +1679,6 @@ static int tdx_sept_link_private_spt(struct kvm *kvm, gfn_t gfn,
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
@@ -1714,12 +1698,6 @@ static int tdx_sept_zap_private_spte(struct kvm *kvm, gfn_t gfn,
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
@@ -2825,12 +2803,6 @@ static int tdx_td_finalize(struct kvm *kvm, struct kvm_tdx_cmd *cmd)
 
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
@@ -3127,6 +3099,9 @@ static int tdx_gmem_post_populate(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
 	struct page *src_page;
 	int ret, i;
 
+	if (KVM_BUG_ON(kvm_tdx->page_add_src, kvm))
+		return -EIO;
+
 	/*
 	 * Get the source page if it has been faulted in. Return failure if the
 	 * source page has been swapped out or unmapped in primary memory.
@@ -3137,22 +3112,14 @@ static int tdx_gmem_post_populate(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
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
-
-	if (!(arg->flags & KVM_TDX_MEASURE_MEMORY_REGION))
-		goto out;
+	if (ret || !(arg->flags & KVM_TDX_MEASURE_MEMORY_REGION))
+		return ret;
 
 	/*
 	 * Note, MR.EXTEND can fail if the S-EPT mapping is somehow removed
@@ -3165,14 +3132,11 @@ static int tdx_gmem_post_populate(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
 		err = tdh_mr_extend(&kvm_tdx->td, gpa + i, &entry, &level_state);
 		if (KVM_BUG_ON(err, kvm)) {
 			pr_tdx_error_2(TDH_MR_EXTEND, err, entry, level_state);
-			ret = -EIO;
-			goto out;
+			return -EIO;
 		}
 	}
 
-out:
-	put_page(src_page);
-	return ret;
+	return 0;
 }
 
 static int tdx_vcpu_init_mem_region(struct kvm_vcpu *vcpu, struct kvm_tdx_cmd *cmd)
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

## [17] Sean Christopherson — 2025-10-16
*Subject: [PATCH v3 16/25] KVM: TDX: Fold tdx_sept_zap_private_spte() into tdx_sept_remove_private_spte()*

Do TDH_MEM_RANGE_BLOCK directly in tdx_sept_remove_private_spte() instead
of using a one-off helper now that the nr_premapped tracking is gone.

Opportunistically drop the WARN on hugepages, which was dead code (see the
KVM_BUG_ON() in tdx_sept_remove_private_spte()).

No functional change intended.

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/vmx/tdx.c | 41 +++++++++++------------------------------
 1 file changed, 11 insertions(+), 30 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 76030461c8f7..d77b2de6db8a 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1679,33 +1679,6 @@ static int tdx_sept_link_private_spt(struct kvm *kvm, gfn_t gfn,
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
@@ -1786,7 +1759,6 @@ static void tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
 	gpa_t gpa = gfn_to_gpa(gfn);
 	u64 err, entry, level_state;
-	int ret;
 
 	/*
 	 * HKID is released after all private pages have been removed, and set
@@ -1800,9 +1772,18 @@ static void tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
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

## [18] Sean Christopherson — 2025-10-16
*Subject: [PATCH v3 17/25] KVM: TDX: Combine KVM_BUG_ON + pr_tdx_error() into TDX_BUG_ON()*

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
 arch/x86/kvm/vmx/tdx.c | 114 +++++++++++++++++------------------------
 1 file changed, 47 insertions(+), 67 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index d77b2de6db8a..2d587a38581e 100644
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
@@ -1671,10 +1671,8 @@ static int tdx_sept_link_private_spt(struct kvm *kvm, gfn_t gfn,
 	if (unlikely(tdx_operand_busy(err)))
 		return -EBUSY;
 
-	if (KVM_BUG_ON(err, kvm)) {
-		pr_tdx_error_2(TDH_MEM_SEPT_ADD, err, entry, level_state);
+	if (TDX_BUG_ON_2(err, TDH_MEM_SEPT_ADD, entry, level_state, kvm))
 		return -EIO;
-	}
 
 	return 0;
 }
@@ -1722,8 +1720,7 @@ static void tdx_track(struct kvm *kvm)
 		tdx_no_vcpus_enter_stop(kvm);
 	}
 
-	if (KVM_BUG_ON(err, kvm))
-		pr_tdx_error(TDH_MEM_TRACK, err);
+	TDX_BUG_ON(err, TDH_MEM_TRACK, kvm);
 
 	kvm_make_all_cpus_request(kvm, KVM_REQ_OUTSIDE_GUEST_MODE);
 }
@@ -1780,10 +1777,8 @@ static void tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
 		tdx_no_vcpus_enter_stop(kvm);
 	}
 
-	if (KVM_BUG_ON(err, kvm)) {
-		pr_tdx_error_2(TDH_MEM_RANGE_BLOCK, err, entry, level_state);
+	if (TDX_BUG_ON_2(err, TDH_MEM_RANGE_BLOCK, entry, level_state, kvm))
 		return;
-	}
 
 	/*
 	 * TDX requires TLB tracking before dropping private page.  Do
@@ -1810,16 +1805,12 @@ static void tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
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
@@ -2459,8 +2450,7 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 		goto free_packages;
 	}
 
-	if (WARN_ON_ONCE(err)) {
-		pr_tdx_error(TDH_MNG_CREATE, err);
+	if (TDX_BUG_ON(err, TDH_MNG_CREATE, kvm)) {
 		ret = -EIO;
 		goto free_packages;
 	}
@@ -2501,8 +2491,7 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 			ret = -EAGAIN;
 			goto teardown;
 		}
-		if (WARN_ON_ONCE(err)) {
-			pr_tdx_error(TDH_MNG_ADDCX, err);
+		if (TDX_BUG_ON(err, TDH_MNG_ADDCX, kvm)) {
 			ret = -EIO;
 			goto teardown;
 		}
@@ -2519,8 +2508,7 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 		*seamcall_err = err;
 		ret = -EINVAL;
 		goto teardown;
-	} else if (WARN_ON_ONCE(err)) {
-		pr_tdx_error_1(TDH_MNG_INIT, err, rcx);
+	} else if (TDX_BUG_ON_1(err, TDH_MNG_INIT, rcx, kvm)) {
 		ret = -EIO;
 		goto teardown;
 	}
@@ -2788,10 +2776,8 @@ static int tdx_td_finalize(struct kvm *kvm, struct kvm_tdx_cmd *cmd)
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
@@ -2878,16 +2864,14 @@ static int tdx_td_vcpu_init(struct kvm_vcpu *vcpu, u64 vcpu_rcx)
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
@@ -2901,10 +2885,8 @@ static int tdx_td_vcpu_init(struct kvm_vcpu *vcpu, u64 vcpu_rcx)
 	}
 
 	err = tdh_vp_init(&tdx->vp, vcpu_rcx, vcpu->vcpu_id);
-	if (KVM_BUG_ON(err, vcpu->kvm)) {
-		pr_tdx_error(TDH_VP_INIT, err);
+	if (TDX_BUG_ON(err, TDH_VP_INIT, vcpu->kvm))
 		return -EIO;
-	}
 
 	vcpu->arch.mp_state = KVM_MP_STATE_RUNNABLE;
 
@@ -3111,10 +3093,8 @@ static int tdx_gmem_post_populate(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
 	 */
 	for (i = 0; i < PAGE_SIZE; i += TDX_EXTENDMR_CHUNKSIZE) {
 		err = tdh_mr_extend(&kvm_tdx->td, gpa + i, &entry, &level_state);
-		if (KVM_BUG_ON(err, kvm)) {
-			pr_tdx_error_2(TDH_MR_EXTEND, err, entry, level_state);
+		if (TDX_BUG_ON_2(err, TDH_MR_EXTEND, entry, level_state, kvm))
 			return -EIO;
-		}
 	}
 
 	return 0;

---

## [19] Sean Christopherson — 2025-10-16
*Subject: [PATCH v3 18/25] KVM: TDX: Derive error argument names from the local
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
index 2d587a38581e..e517ad3d5f4f 100644
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

## [20] Sean Christopherson — 2025-10-16
*Subject: [PATCH v3 19/25] KVM: TDX: Assert that mmu_lock is held for write
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
that wait_for_sept_zap is guarded by holding mmu_lock for write.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/vmx/tdx.c | 4 ++--
 1 file changed, 2 insertions(+), 2 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index e517ad3d5f4f..f6782b0ffa98 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1711,8 +1711,6 @@ static void tdx_track(struct kvm *kvm)
 	if (unlikely(kvm_tdx->state != TD_STATE_RUNNABLE))
 		return;
 
-	lockdep_assert_held_write(&kvm->mmu_lock);
-
 	err = tdh_mem_track(&kvm_tdx->td);
 	if (unlikely(tdx_operand_busy(err))) {
 		/* After no vCPUs enter, the second retry is expected to succeed */
@@ -1758,6 +1756,8 @@ static void tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
 	gpa_t gpa = gfn_to_gpa(gfn);
 	u64 err, entry, level_state;
 
+	lockdep_assert_held_write(&kvm->mmu_lock);
+
 	/*
 	 * HKID is released after all private pages have been removed, and set
 	 * before any might be populated. Warn if zapping is attempted when

---

## [21] Sean Christopherson — 2025-10-16
*Subject: [PATCH v3 20/25] KVM: TDX: Add macro to retry SEAMCALLs when forcing
 vCPUs out of guest*

Add a macro to handle kicking vCPUs out of the guest and retrying
SEAMCALLs on -EBUSY instead of providing small helpers to be used by each
SEAMCALL.  Wrapping the SEAMCALLs in a macro makes it a little harder to
tease out which SEAMCALL is being made, but significantly reduces the
amount of copy+paste code and makes it all but impossible to leave an
elevated wait_for_sept_zap.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/vmx/tdx.c | 72 ++++++++++++++----------------------------
 1 file changed, 23 insertions(+), 49 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index f6782b0ffa98..2e2dab89c98f 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -294,25 +294,24 @@ static inline void tdx_disassociate_vp(struct kvm_vcpu *vcpu)
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
@@ -1711,14 +1710,7 @@ static void tdx_track(struct kvm *kvm)
 	if (unlikely(kvm_tdx->state != TD_STATE_RUNNABLE))
 		return;
 
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
@@ -1770,14 +1762,8 @@ static void tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
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
 
@@ -1792,20 +1778,8 @@ static void tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
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

## [22] Sean Christopherson — 2025-10-16
*Subject: [PATCH v3 21/25] KVM: TDX: Add tdx_get_cmd() helper to get and
 validate sub-ioctl command*

Add a helper to copy a kvm_tdx_cmd structure from userspace and verify
that must-be-zero fields are indeed zero.

No functional change intended.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/vmx/tdx.c | 31 +++++++++++++++++--------------
 1 file changed, 17 insertions(+), 14 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 2e2dab89c98f..d5f810435f34 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -2761,20 +2761,25 @@ static int tdx_td_finalize(struct kvm *kvm, struct kvm_tdx_cmd *cmd)
 	return 0;
 }
 
+static int tdx_get_cmd(void __user *argp, struct kvm_tdx_cmd *cmd)
+{
+	if (copy_from_user(cmd, argp, sizeof(*cmd)))
+		return -EFAULT;
+
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
 
@@ -3152,11 +3157,9 @@ int tdx_vcpu_ioctl(struct kvm_vcpu *vcpu, void __user *argp)
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

## [23] Sean Christopherson — 2025-10-16
*Subject: [PATCH v3 22/25] KVM: TDX: Convert INIT_MEM_REGION and INIT_VCPU to
 "unlocked" vCPU ioctl*

Handle the KVM_TDX_INIT_MEM_REGION and KVM_TDX_INIT_VCPU vCPU sub-ioctls
in the unlocked variant, i.e. outside of vcpu->mutex, in anticipation of
taking kvm->lock along with all other vCPU mutexes, at which point the
sub-ioctls _must_ start without vcpu->mutex held.

No functional change intended.

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
index 7e92aebd07e8..fda24da9e4e5 100644
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
index d5f810435f34..1de5f17a7989 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -3148,6 +3148,42 @@ static int tdx_vcpu_init_mem_region(struct kvm_vcpu *vcpu, struct kvm_tdx_cmd *c
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
@@ -3162,12 +3198,6 @@ int tdx_vcpu_ioctl(struct kvm_vcpu *vcpu, void __user *argp)
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

## [24] Sean Christopherson — 2025-10-16
*Subject: [PATCH v3 23/25] KVM: TDX: Use guard() to acquire kvm->lock in tdx_vm_ioctl()*

Use guard() in tdx_vm_ioctl() to tidy up the code a small amount, but more
importantly to minimize the diff of a future change, which will use
guard-like semantics to acquire and release multiple locks.

No functional change intended.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/vmx/tdx.c | 9 +++------
 1 file changed, 3 insertions(+), 6 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 1de5f17a7989..84b5fe654c99 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -2781,7 +2781,7 @@ int tdx_vm_ioctl(struct kvm *kvm, void __user *argp)
 	if (r)
 		return r;
 
-	mutex_lock(&kvm->lock);
+	guard(mutex)(&kvm->lock);
 
 	switch (tdx_cmd.id) {
 	case KVM_TDX_CAPABILITIES:
@@ -2794,15 +2794,12 @@ int tdx_vm_ioctl(struct kvm *kvm, void __user *argp)
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

## [25] Sean Christopherson — 2025-10-16
*Subject: [PATCH v3 24/25] KVM: TDX: Guard VM state transitions with "all" the locks*

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
 arch/x86/kvm/vmx/tdx.c | 63 +++++++++++++++++++++++++++++++++++-------
 1 file changed, 53 insertions(+), 10 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 84b5fe654c99..d6541b08423f 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -2632,6 +2632,46 @@ static int tdx_read_cpuid(struct kvm_vcpu *vcpu, u32 leaf, u32 sub_leaf,
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
@@ -2644,6 +2684,10 @@ static int tdx_td_init(struct kvm *kvm, struct kvm_tdx_cmd *cmd)
 	BUILD_BUG_ON(sizeof(*init_vm) != 256 + sizeof_field(struct kvm_tdx_init_vm, cpuid));
 	BUILD_BUG_ON(sizeof(struct td_params) != 1024);
 
+	CLASS(tdx_vm_state_guard, guard)(kvm);
+	if (IS_ERR(guard))
+		return PTR_ERR(guard);
+
 	if (kvm_tdx->state != TD_STATE_UNINITIALIZED)
 		return -EINVAL;
 
@@ -2743,7 +2787,9 @@ static int tdx_td_finalize(struct kvm *kvm, struct kvm_tdx_cmd *cmd)
 {
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
 
-	guard(mutex)(&kvm->slots_lock);
+	CLASS(tdx_vm_state_guard, guard)(kvm);
+	if (IS_ERR(guard))
+		return PTR_ERR(guard);
 
 	if (!is_hkid_assigned(kvm_tdx) || kvm_tdx->state == TD_STATE_RUNNABLE)
 		return -EINVAL;
@@ -2781,8 +2827,6 @@ int tdx_vm_ioctl(struct kvm *kvm, void __user *argp)
 	if (r)
 		return r;
 
-	guard(mutex)(&kvm->lock);
-
 	switch (tdx_cmd.id) {
 	case KVM_TDX_CAPABILITIES:
 		r = tdx_get_capabilities(&tdx_cmd);
@@ -3090,8 +3134,6 @@ static int tdx_vcpu_init_mem_region(struct kvm_vcpu *vcpu, struct kvm_tdx_cmd *c
 	if (tdx->state != VCPU_TD_STATE_INITIALIZED)
 		return -EINVAL;
 
-	guard(mutex)(&kvm->slots_lock);
-
 	/* Once TD is finalized, the initial guest memory is fixed. */
 	if (kvm_tdx->state == TD_STATE_RUNNABLE)
 		return -EINVAL;
@@ -3147,7 +3189,8 @@ static int tdx_vcpu_init_mem_region(struct kvm_vcpu *vcpu, struct kvm_tdx_cmd *c
 
 int tdx_vcpu_unlocked_ioctl(struct kvm_vcpu *vcpu, void __user *argp)
 {
-	struct kvm_tdx *kvm_tdx = to_kvm_tdx(vcpu->kvm);
+	struct kvm *kvm = vcpu->kvm;
+	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
 	struct kvm_tdx_cmd cmd;
 	int r;
 
@@ -3155,12 +3198,13 @@ int tdx_vcpu_unlocked_ioctl(struct kvm_vcpu *vcpu, void __user *argp)
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
@@ -3177,7 +3221,6 @@ int tdx_vcpu_unlocked_ioctl(struct kvm_vcpu *vcpu, void __user *argp)
 
 	vcpu_put(vcpu);
 
-	mutex_unlock(&vcpu->mutex);
 	return r;
 }

---

## [26] Sean Christopherson — 2025-10-16
*Subject: [PATCH v3 25/25] KVM: TDX: Fix list_add corruption during vcpu_load()*

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

Signed-off-by: Yan Zhao <yan.y.zhao@intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/vmx/tdx.c | 43 +++++++++++++++++++++++++++++++++++++-----
 1 file changed, 38 insertions(+), 5 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index d6541b08423f..daec88d4b88d 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -833,19 +833,52 @@ void tdx_vcpu_put(struct kvm_vcpu *vcpu)
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
+		tdx_disassociate_vp(vcpu);
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

## [27] Claudio Imbrenda — 2025-10-17
*Subject: Re: [PATCH v3 01/25] KVM: Make support for
 kvm_arch_vcpu_async_ioctl() mandatory*

On Thu, 16 Oct 2025 17:32:19 -0700
Sean Christopherson <seanjc@google.com> wrote:

> Implement kvm_arch_vcpu_async_ioctl() "natively" in x86 and arm64 instead
> of relying on an #ifdef'd stub, and drop HAVE_KVM_VCPU_ASYNC_IOCTL in

Acked-by: Claudio Imbrenda <imbrenda@linux.ibm.com>

> ---
>  arch/arm64/kvm/arm.c       |  6 ++++++

---

## [28] Claudio Imbrenda — 2025-10-17
*Subject: Re: [PATCH v3 02/25] KVM: Rename kvm_arch_vcpu_async_ioctl() to
 kvm_arch_vcpu_unlocked_ioctl()*

On Thu, 16 Oct 2025 17:32:20 -0700
Sean Christopherson <seanjc@google.com> wrote:

> Rename the "async" ioctl API to "unlocked" so that upcoming usage in x86's
> TDX code doesn't result in a massive misnomer.  To avoid having to retry

Acked-by: Claudio Imbrenda <imbrenda@linux.ibm.com>

> ---
>  arch/arm64/kvm/arm.c       | 4 ++--

---

## [29] Yan Zhao — 2025-10-20
*Subject: Re: [PATCH v3 25/25] KVM: TDX: Fix list_add corruption during
 vcpu_load()*

On Thu, Oct 16, 2025 at 05:32:43PM -0700, Sean Christopherson wrote:
> From: Yan Zhao <yan.y.zhao@intel.com>
> 
Sorry, I should use "tdx_flush_vp_on_cpu(vcpu);" rather than invoking
tdx_disassociate_vp() directly.

This is to ensure that list_del() in tdx_disassociate_vp() runs on the physical
cpu that owns the list and to which the vcpu is associated with in the previous
tdx_vcpu_load().

> +		return;
> +	}

---

## [30] Edgecombe, Rick P — 2025-10-21
*Subject: Re: [PATCH v3 23/25] KVM: TDX: Use guard() to acquire kvm->lock in
 tdx_vm_ioctl()*

On Thu, 2025-10-16 at 17:32 -0700, Sean Christopherson wrote:
> Use guard() in tdx_vm_ioctl() to tidy up the code a small amount, but more
> importantly to minimize the diff of a future change, which will use

There is a tiny functional change. In the default case it no longer re-copies
the struct back to userspace.

> 
> Signed-off-by: Sean Christopherson <seanjc@google.com>

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>

---

## [31] Edgecombe, Rick P — 2025-10-21
*Subject: Re: [PATCH v3 04/25] KVM: x86/mmu: Add dedicated API to map
 guest_memfd pfn into TDP MMU*

On Thu, 2025-10-16 at 17:32 -0700, Sean Christopherson wrote:
> Add and use a new API for mapping a private pfn from guest_memfd into the
> TDP MMU from TDX's post-populate hook instead of partially open-coding the

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>

---

## [32] Edgecombe, Rick P — 2025-10-21
*Subject: Re: [PATCH v3 07/25] KVM: TDX: Drop superfluous page pinning in S-EPT
 management*

On Thu, 2025-10-16 at 17:32 -0700, Sean Christopherson wrote:
> From: Yan Zhao <yan.y.zhao@intel.com>
> 

Some white space issues above. But in any case:

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>

---

## [33] Edgecombe, Rick P — 2025-10-21
*Subject: Re: [PATCH v3 14/25] KVM: TDX: Bug the VM if extended the initial
 measurement fails*

On Thu, 2025-10-16 at 17:32 -0700, Sean Christopherson wrote:
> WARN and terminate the VM if TDH_MR_EXTEND fails, as extending the
> measurement should fail if and only if there is a KVM bug, or if the S-EPT

Per the discussion in v2, shouldn't it go after patch 24 'KVM: TDX: Guard VM
state transitions with "all" the locks'? Otherwise it introduces a KVM_BUG_ON()
that can be triggered from userspace. not a huge deal though.

---

## [34] Edgecombe, Rick P — 2025-10-21
*Subject: Re: [PATCH v3 21/25] KVM: TDX: Add tdx_get_cmd() helper to get and
 validate sub-ioctl command*

On Thu, 2025-10-16 at 17:32 -0700, Sean Christopherson wrote:
> Add a helper to copy a kvm_tdx_cmd structure from userspace and verify
> that must-be-zero fields are indeed zero.

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>

---

## [35] Yan Zhao — 2025-10-21
*Subject: Re: [PATCH v3 04/25] KVM: x86/mmu: Add dedicated API to map
 guest_memfd pfn into TDP MMU*

On Thu, Oct 16, 2025 at 05:32:22PM -0700, Sean Christopherson wrote:
> Add and use a new API for mapping a private pfn from guest_memfd into the
> TDP MMU from TDX's post-populate hook instead of partially open-coding the
Do we need to assert that filemap_invalidate_lock() is held as well?
Otherwise, a concurrent kvm_gmem_punch_hole(), which does not hold slots_lock,
could make the pfn stale.

Or check for stale mapping?
> +
> +	if (KVM_BUG_ON(!tdp_mmu_enabled, kvm))

---

## [36] Sean Christopherson — 2025-10-21
*Subject: Re: [PATCH v3 04/25] KVM: x86/mmu: Add dedicated API to map
 guest_memfd pfn into TDP MMU*

On Tue, Oct 21, 2025, Yan Zhao wrote:
> On Thu, Oct 16, 2025 at 05:32:22PM -0700, Sean Christopherson wrote:
> > diff --git a/arch/x86/kvm/mmu/mmu.c b/arch/x86/kvm/mmu/mmu.c

Hrm, a lockdep assertion would be nice to have, but it's obviously not strictly
necessary, and I'm not sure it's worth the cost.  To safely assert, KVM would need
to first assert that the file refcount is elevated, e.g. to guard against
guest_memfd _really_ screwing up and not grabbing a reference to the underlying
file.

E.g. it'd have to be something like this:

diff --git a/arch/x86/kvm/mmu/mmu.c b/arch/x86/kvm/mmu/mmu.c
index 94d7f32a03b6..5d46b2ac0292 100644
--- a/arch/x86/kvm/mmu/mmu.c
+++ b/arch/x86/kvm/mmu/mmu.c
@@ -5014,6 +5014,18 @@ long kvm_arch_vcpu_pre_fault_memory(struct kvm_vcpu *vcpu,
        return min(range->size, end - range->gpa);
 }
 
+static void kvm_assert_gmem_invalidate_lock_held(struct kvm_memory_slot *slot)
+{
+#ifdef CONFIG_PROVE_LOCKING
+       if (WARN_ON_ONCE(!kvm_slot_has_gmem(slot)) ||
+           WARN_ON_ONCE(!slot->gmem.file) ||
+           WARN_ON_ONCE(!file_count(slot->gmem.file)))
+               return;
+
+       lockdep_assert_held(file_inode(&slot->gmem.file)->i_mapping->invalidate_lock));
+#endif
+}
+
 int kvm_tdp_mmu_map_private_pfn(struct kvm_vcpu *vcpu, gfn_t gfn, kvm_pfn_t pfn)
 {
        struct kvm_page_fault fault = {
@@ -5038,6 +5050,8 @@ int kvm_tdp_mmu_map_private_pfn(struct kvm_vcpu *vcpu, gfn_t gfn, kvm_pfn_t pfn)
 
        lockdep_assert_held(&kvm->slots_lock);
 
+       kvm_assert_gmem_invalidate_lock_held(fault.slot);
+
        if (KVM_BUG_ON(!tdp_mmu_enabled, kvm))
                return -EIO;
--

Which I suppose isn't that terrible?

---

## [37] Sean Christopherson — 2025-10-21
*Subject: Re: [PATCH v3 23/25] KVM: TDX: Use guard() to acquire kvm->lock in tdx_vm_ioctl()*

On Tue, Oct 21, 2025, Rick P Edgecombe wrote:
> On Thu, 2025-10-16 at 17:32 -0700, Sean Christopherson wrote:
> > Use guard() in tdx_vm_ioctl() to tidy up the code a small amount, but more

No?  The default case doesn't copy the struct back even before this patch, it
explicitly skips the copy_to_user().

	mutex_lock(&kvm->lock);

	switch (tdx_cmd.id) {
	case KVM_TDX_CAPABILITIES:
		r = tdx_get_capabilities(&tdx_cmd);
		break;
	case KVM_TDX_INIT_VM:
		r = tdx_td_init(kvm, &tdx_cmd);
		break;
	case KVM_TDX_FINALIZE_VM:
		r = tdx_td_finalize(kvm, &tdx_cmd);
		break;
	default:
		r = -EINVAL;
		goto out;  <====================
	}

	if (copy_to_user(argp, &tdx_cmd, sizeof(struct kvm_tdx_cmd)))
		r = -EFAULT;

out:
	mutex_unlock(&kvm->lock);
	return r;

---

## [38] Edgecombe, Rick P — 2025-10-21
*Subject: Re: [PATCH v3 23/25] KVM: TDX: Use guard() to acquire kvm->lock in
 tdx_vm_ioctl()*

On Tue, 2025-10-21 at 09:56 -0700, Sean Christopherson wrote:
> No?  The default case doesn't copy the struct back even before this patch, it
> explicitly skips the copy_to_user().

Err, right. sorry.

---

## [39] Binbin Wu — 2025-10-22
*Subject: Re: [PATCH v3 03/25] KVM: TDX: Drop PROVE_MMU=y sanity check on
 to-be-populated mappings*

On 10/17/2025 8:32 AM, Sean Christopherson wrote:
> Drop TDX's sanity check that a mirror EPT mapping isn't zapped between
> creating said mapping and doing TDH.MEM.PAGE.ADD, as the check is

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

> ---
>   arch/x86/kvm/vmx/tdx.c | 14 --------------

---

## [40] Yan Zhao — 2025-10-22
*Subject: Re: [PATCH v3 04/25] KVM: x86/mmu: Add dedicated API to map
 guest_memfd pfn into TDP MMU*

On Thu, Oct 16, 2025 at 05:32:22PM -0700, Sean Christopherson wrote:
> Link: https://lore.kernel.org/all/20250709232103.zwmufocd3l7sqk7y@amd.com

Hi Sean,                                                                         

Will you post [1] to fix the AB-BA deadlock issue for huge page in-place
conversion as well?

Without it, the "WARNING: possible circular locking dependency detected" would
still appear due to

- lock(mapping.invalidate_lock#4) --> lock(&mm->mmap_lock)
  for init mem on non-in-place-conversion guest_memfd
- rlock(&mm->mmap_lock) --> rlock(mapping.invalidate_lock#4)
  for faulting shared pages on in-place-convertion guest_memfd

[1] https://lore.kernel.org/all/aHEwT4X0RcfZzHlt@google.com/                     
                                                                                 
Thanks                                                                           
Yan

---

## [41] Binbin Wu — 2025-10-22
*Subject: Re: [PATCH v3 05/25] Revert "KVM: x86/tdp_mmu: Add a helper function
 to walk down the TDP MMU"*

On 10/17/2025 8:32 AM, Sean Christopherson wrote:
> Remove the helper and exports that were added to allow TDX code to reuse
> kvm_tdp_map_page() for its gmem post-populate flow now that a dedicated

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

---

## [42] Binbin Wu — 2025-10-22
*Subject: Re: [PATCH v3 06/25] KVM: x86/mmu: Rename kvm_tdp_map_page() to
 kvm_tdp_page_prefault()*

On 10/17/2025 8:32 AM, Sean Christopherson wrote:
> Rename kvm_tdp_map_page() to kvm_tdp_page_prefault() now that it's used
> only by kvm_arch_vcpu_pre_fault_memory().

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

---

## [43] Yan Zhao — 2025-10-22
*Subject: Re: [PATCH v3 04/25] KVM: x86/mmu: Add dedicated API to map
 guest_memfd pfn into TDP MMU*

On Tue, Oct 21, 2025 at 09:36:52AM -0700, Sean Christopherson wrote:
> On Tue, Oct 21, 2025, Yan Zhao wrote:
> > On Thu, Oct 16, 2025 at 05:32:22PM -0700, Sean Christopherson wrote:
Not sure. Maybe just add a comment?
But even with kvm_assert_gmem_invalidate_lock_held() and
lockdep_assert_held(&kvm->slots_lock), it seems that
kvm_tdp_mmu_map_private_pfn() still can't guarantee that the pfn is not stale.
e.g., if hypothetically those locks were released and re-acquired after getting
the pfn.

> to first assert that the file refcount is elevated, e.g. to guard against
> guest_memfd _really_ screwing up and not grabbing a reference to the underlying
	  lockdep_assert_held(&file_inode(slot->gmem.file)->i_mapping->invalidate_lock);
> +#endif
> +}
Is it good if we test is_page_fault_stale()? e.g.,

diff --git a/arch/x86/kvm/mmu.h b/arch/x86/kvm/mmu.h
index 9e5045a60d8b..b2cf754f6f92 100644
--- a/arch/x86/kvm/mmu.h
+++ b/arch/x86/kvm/mmu.h
@@ -257,7 +257,8 @@ extern bool tdp_mmu_enabled;
 #define tdp_mmu_enabled false
 #endif

-int kvm_tdp_mmu_map_private_pfn(struct kvm_vcpu *vcpu, gfn_t gfn, kvm_pfn_t pfn);
+int kvm_tdp_mmu_map_private_pfn(struct kvm_vcpu *vcpu, gfn_t gfn, kvm_pfn_t pfn,
+                               unsigned long mmu_seq);

 static inline bool kvm_memslots_have_rmaps(struct kvm *kvm)
 {
diff --git a/arch/x86/kvm/mmu/mmu.c b/arch/x86/kvm/mmu/mmu.c
index 94d7f32a03b6..0dc9ff1bc63e 100644
--- a/arch/x86/kvm/mmu/mmu.c
+++ b/arch/x86/kvm/mmu/mmu.c
@@ -5014,7 +5014,8 @@ long kvm_arch_vcpu_pre_fault_memory(struct kvm_vcpu *vcpu,
        return min(range->size, end - range->gpa);
 }

-int kvm_tdp_mmu_map_private_pfn(struct kvm_vcpu *vcpu, gfn_t gfn, kvm_pfn_t pfn)
+int kvm_tdp_mmu_map_private_pfn(struct kvm_vcpu *vcpu, gfn_t gfn, kvm_pfn_t pfn,
+                               unsigned long mmu_seq)
 {
        struct kvm_page_fault fault = {
                .addr = gfn_to_gpa(gfn),
@@ -5032,12 +5033,12 @@ int kvm_tdp_mmu_map_private_pfn(struct kvm_vcpu *vcpu, gfn_t gfn, kvm_pfn_t pfn)
                .slot = kvm_vcpu_gfn_to_memslot(vcpu, gfn),
                .pfn = pfn,
                .map_writable = true,
+
+               .mmu_seq = mmu_seq,
        };
        struct kvm *kvm = vcpu->kvm;
        int r;

-       lockdep_assert_held(&kvm->slots_lock);
-
        if (KVM_BUG_ON(!tdp_mmu_enabled, kvm))
                return -EIO;

@@ -5063,6 +5064,9 @@ int kvm_tdp_mmu_map_private_pfn(struct kvm_vcpu *vcpu, gfn_t gfn, kvm_pfn_t pfn)

                guard(read_lock)(&kvm->mmu_lock);

+               if (is_page_fault_stale(vcpu, &fault))
+                       return -EIO;
+
                r = kvm_tdp_mmu_map(vcpu, &fault);
        } while (r == RET_PF_RETRY);

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index cae694d3ff33..4bb3e68a12b3 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -3113,7 +3113,8 @@ struct tdx_gmem_post_populate_arg {
 };

 static int tdx_gmem_post_populate(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
-                                 void __user *src, int order, void *_arg)
+                                 unsigned long mmu_seq, void __user *src,
+                                 int order, void *_arg)
 {
        struct tdx_gmem_post_populate_arg *arg = _arg;
        struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
@@ -3136,7 +3137,7 @@ static int tdx_gmem_post_populate(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
                return -ENOMEM;

        kvm_tdx->page_add_src = src_page;
-       ret = kvm_tdp_mmu_map_private_pfn(arg->vcpu, gfn, pfn);
+       ret = kvm_tdp_mmu_map_private_pfn(arg->vcpu, gfn, pfn, mmu_seq);
        kvm_tdx->page_add_src = NULL;

        put_page(src_page);
diff --git a/include/linux/kvm_host.h b/include/linux/kvm_host.h
index d93f75b05ae2..406472f60e63 100644
--- a/include/linux/kvm_host.h
+++ b/include/linux/kvm_host.h
@@ -2581,7 +2581,8 @@ int kvm_arch_gmem_prepare(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn, int max_ord
  * Returns the number of pages that were populated.
  */
 typedef int (*kvm_gmem_populate_cb)(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
-                                   void __user *src, int order, void *opaque);
+                                   unsigned long mmu_seq, void __user *src,
+                                   int order, void *opaque);

 long kvm_gmem_populate(struct kvm *kvm, gfn_t gfn, void __user *src, long npages,
                       kvm_gmem_populate_cb post_populate, void *opaque);
diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index 427c0acee9d7..c9a87197412e 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -836,6 +836,7 @@ long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long
                pgoff_t index = kvm_gmem_get_index(slot, gfn);
                bool is_prepared = false;
                kvm_pfn_t pfn;
+               unsigned long mmu_seq = kvm->mmu_invalidate_seq;

                if (signal_pending(current)) {
                        ret = -EINTR;
@@ -869,7 +870,7 @@ long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long
                }

                p = src ? src + i * PAGE_SIZE : NULL;
-               ret = post_populate(kvm, gfn, pfn, p, max_order, opaque);
+               ret = post_populate(kvm, gfn, pfn, mmu_seq, p, max_order, opaque);
                if (!ret)
                        kvm_gmem_mark_prepared(folio);

---

## [44] Yan Zhao — 2025-10-22
*Subject: Re: [PATCH v3 10/25] KVM: x86/mmu: Drop the return code from
 kvm_x86_ops.remove_external_spte()*

On Thu, Oct 16, 2025 at 05:32:28PM -0700, Sean Christopherson wrote:
> Opportunistically pass the spte instead of the pfn, as the API is clearly
> about removing an spte.
From my perspective, "remove_external_spte" means removing an external SPTE (not
a mirror SPTE). So passing in pfn_for_gfn seems reasonable as well.

Additionally, passing in the pfn eliminates potential concerns about incorrect
spte content.

> diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h
> index 48598d017d6f..7e92aebd07e8 100644
Also update set_external_spte?

        /* Update the external page table from spte getting set. */                
        int (*set_external_spte)(struct kvm *kvm, gfn_t gfn, enum pg_level level,
                                 kvm_pfn_t pfn_for_gfn);

---

## [45] Sean Christopherson — 2025-10-22
*Subject: Re: [PATCH v3 04/25] KVM: x86/mmu: Add dedicated API to map
 guest_memfd pfn into TDP MMU*

On Wed, Oct 22, 2025, Yan Zhao wrote:
> On Tue, Oct 21, 2025 at 09:36:52AM -0700, Sean Christopherson wrote:
> > On Tue, Oct 21, 2025, Yan Zhao wrote:

At some point we have to assume correctness.  E.g. one could also argue that
holding every locking in the universe still doesn't ensure the pfn is fresh,
because theoretically guest_memfd could violate the locking scheme.

Aha!  And to further harden and document this code, this API can be gated on
CONFIG_KVM_GUEST_MEMFD=y, as pointed out by the amazing-as-always test bot:

https://lore.kernel.org/all/202510221928.ikBXHGCf-lkp@intel.com

We could go a step further and gate it on CONFIG_KVM_INTEL_TDX=y, but I don't
like that idea as I think it'd would be a net negative in terms of documenation,
compared to checking CONFIG_KVM_GUEST_MEMFD.  And in general I don't want to set
a precedent of ifdef-ing common x86 based on what vendor code _currently_ needs
an API.

> e.g., if hypothetically those locks were released and re-acquired after getting
> the pfn.

No, because it can only get false positives, e.g. if an mmu_notifier invalidation
on shared, non-guest_memfd memory.  Though a sanity check would be nice to have;
I believe we can simply do:

diff --git a/arch/x86/kvm/mmu/tdp_mmu.c b/arch/x86/kvm/mmu/tdp_mmu.c
index c5734ca5c17d..440fd8f80397 100644
--- a/arch/x86/kvm/mmu/tdp_mmu.c
+++ b/arch/x86/kvm/mmu/tdp_mmu.c
@@ -1273,6 +1273,8 @@ int kvm_tdp_mmu_map(struct kvm_vcpu *vcpu, struct kvm_page_fault *fault)
        struct kvm_mmu_page *sp;
        int ret = RET_PF_RETRY;
 
+       KVM_MMU_WARN_ON(!root || root->role.invalid);
+
        kvm_mmu_hugepage_adjust(vcpu, fault);
 
        trace_kvm_mmu_spte_requested(fault);

---

## [46] Sean Christopherson — 2025-10-22
*Subject: Re: [PATCH v3 10/25] KVM: x86/mmu: Drop the return code from kvm_x86_ops.remove_external_spte()*

On Wed, Oct 22, 2025, Yan Zhao wrote:
> On Thu, Oct 16, 2025 at 05:32:28PM -0700, Sean Christopherson wrote:
> > Opportunistically pass the spte instead of the pfn, as the API is clearly

No, it just makes bugs harder to debug.  E.g. it doesn't magically guarantee the
@pfn matches the pfn that was mapped into the S-EPT.

> > diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h
> > index 48598d017d6f..7e92aebd07e8 100644

Thinking more about what "spte" actually tracks, I think I'll rename it to
"mirror_spte".

> Also update set_external_spte?

Ooh, yeah, good call.  And we can use the mirror_spte information to assert that
KVM expects full RWX permissions, e.g. that we aren't creation a security hole by
letting the guest write memory that KVM thinks is read-only (extreme paranoia,
more for documentation purposes).

---

## [47] Yan Zhao — 2025-10-23
*Subject: Re: [PATCH v3 04/25] KVM: x86/mmu: Add dedicated API to map
 guest_memfd pfn into TDP MMU*

On Wed, Oct 22, 2025 at 11:12:47AM -0700, Sean Christopherson wrote:
> On Wed, Oct 22, 2025, Yan Zhao wrote:
> > On Tue, Oct 21, 2025 at 09:36:52AM -0700, Sean Christopherson wrote:
Right. The false positive is annoying.

> I believe we can simply do:
> 
Ok.

---

## [48] Yan Zhao — 2025-10-23
*Subject: Re: [PATCH v3 19/25] KVM: TDX: Assert that mmu_lock is held for
 write when removing S-EPT entries*

On Thu, Oct 16, 2025 at 05:32:37PM -0700, Sean Christopherson wrote:
> Unconditionally assert that mmu_lock is held for write when removing S-EPT
> entries, not just when removing S-EPT entries triggers certain conditions,
Could we also deliberately leave lockdep assertion for tdx_track()?
This is because if we allow removing S-EPT entries while holding mmu_lock for
read in future, tdx_track() needs to be protected by a separate spinlock to
ensure serialization of tdh_mem_track() and vCPUs kick-off (kicking off vCPUs
must follow each tdh_mem_track() to unblock the next tdh_mem_track()).

>  	err = tdh_mem_track(&kvm_tdx->td);
>  	if (unlikely(tdx_operand_busy(err))) {

---

## [49] Huang, Kai — 2025-10-23
*Subject: Re: [PATCH v3 04/25] KVM: x86/mmu: Add dedicated API to map
 guest_memfd pfn into TDP MMU*

On Thu, 2025-10-16 at 17:32 -0700, Sean Christopherson wrote:
> Add and use a new API for mapping a private pfn from guest_memfd into the
> TDP MMU from TDX's post-populate hook instead of partially open-coding the
				      ^
				      remove

> ideally would not be exposed outside of the MMU, let alone to vendor code.
> On that topic, opportunistically drop the kvm_mmu_load() export.  Leave

Reviewed-by: Kai Huang <kai.huang@intel.com>

---

## [50] Huang, Kai — 2025-10-23
*Subject: Re: [PATCH v3 05/25] Revert "KVM: x86/tdp_mmu: Add a helper function
 to walk down the TDP MMU"*

On Thu, 2025-10-16 at 17:32 -0700, Sean Christopherson wrote:
> Remove the helper and exports that were added to allow TDX code to reuse
> kvm_tdp_map_page() for its gmem post-populate flow now that a dedicated

Reviewed-by: Kai Huang <kai.huang@intel.com>

---

## [51] Huang, Kai — 2025-10-23
*Subject: Re: [PATCH v3 06/25] KVM: x86/mmu: Rename kvm_tdp_map_page() to
 kvm_tdp_page_prefault()*

On Thu, 2025-10-16 at 17:32 -0700, Sean Christopherson wrote:
> Rename kvm_tdp_map_page() to kvm_tdp_page_prefault() now that it's used
> only by kvm_arch_vcpu_pre_fault_memory().

Reviewed-by: Kai Huang <kai.huang@intel.com>

---

## [52] Huang, Kai — 2025-10-23
*Subject: Re: [PATCH v3 09/25] KVM: TDX: Fold tdx_sept_drop_private_spte() into
 tdx_sept_remove_private_spte()*

On Thu, 2025-10-16 at 17:32 -0700, Sean Christopherson wrote:
> Fold tdx_sept_drop_private_spte() into tdx_sept_remove_private_spte() to
> avoid having to differnatiate between "zap", "drop", and "remove", and to
		  ^
		  differentiate

Nit: it's a wee bit confusing that you mentioned "zap", because after this
patch tdx_sept_zap_private_spte() is still there.  But it may be only me
feeling that way.

> eliminate dead code due to redundant checks, e.g. on an HKID being
> assigned.

Reviewed-by: Kai Huang <kai.huang@intel.com>

---

## [53] Sean Christopherson — 2025-10-23
*Subject: Re: [PATCH v3 09/25] KVM: TDX: Fold tdx_sept_drop_private_spte() into tdx_sept_remove_private_spte()*

On Thu, Oct 23, 2025, Kai Huang wrote:
> On Thu, 2025-10-16 at 17:32 -0700, Sean Christopherson wrote:
> > Fold tdx_sept_drop_private_spte() into tdx_sept_remove_private_spte() to

Hmm, yeah, I agree that's a confusing/misleading.  How about this?

  KVM: TDX: Fold tdx_sept_drop_private_spte() into tdx_sept_remove_private_spte()
  
  Fold tdx_sept_drop_private_spte() into tdx_sept_remove_private_spte() as a
  step towards having "remove" be the only and only function that deals with
  removing/zapping/dropping a SPTE, e.g. to avoid having to differentiate
  between "zap", "drop", and "remove".  Eliminating the "drop" helper also
  gets rid of what is effectively dead code due to redundant checks, e.g. on
  an HKID being assigned.
  
  No functional change intended.

---

## [54] Sean Christopherson — 2025-10-23
*Subject: Re: [PATCH v3 19/25] KVM: TDX: Assert that mmu_lock is held for write
 when removing S-EPT entries*

On Thu, Oct 23, 2025, Yan Zhao wrote:
> On Thu, Oct 16, 2025 at 05:32:37PM -0700, Sean Christopherson wrote:
> > Unconditionally assert that mmu_lock is held for write when removing S-EPT

Can do.

> This is because if we allow removing S-EPT entries while holding mmu_lock for
> read in future, tdx_track() needs to be protected by a separate spinlock to

Does this look/sound right?

From: Sean Christopherson <seanjc@google.com>
Date: Thu, 28 Aug 2025 17:06:17 -0700
Subject: [PATCH] KVM: TDX: Assert that mmu_lock is held for write when
 removing S-EPT entries

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
index dca9e2561270..899051c64faa 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1715,6 +1715,11 @@ static void tdx_track(struct kvm *kvm)
 	if (unlikely(kvm_tdx->state != TD_STATE_RUNNABLE))
 		return;
 
+	/*
+	 * The full sequence of TDH.MEM.TRACK and forcing vCPUs out of guest
+	 * mode must be serialized, as TDH.MEM.TRACK will fail if the previous
+	 * tracking epoch hasn't completed.
+	*/
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

base-commit: 69564844a116861ebea4396894005c8b4e48f870
--

---

## [55] Sean Christopherson — 2025-10-23
*Subject: Re: [PATCH v3 14/25] KVM: TDX: Bug the VM if extended the initial
 measurement fails*

On Tue, Oct 21, 2025, Rick P Edgecombe wrote:
> On Thu, 2025-10-16 at 17:32 -0700, Sean Christopherson wrote:
> > WARN and terminate the VM if TDH_MR_EXTEND fails, as extending the

Oh, right.  And then the changelog needs to be updated too.

---

## [56] Huang, Kai — 2025-10-23
*Subject: Re: [PATCH v3 09/25] KVM: TDX: Fold tdx_sept_drop_private_spte() into
 tdx_sept_remove_private_spte()*

On Thu, 2025-10-23 at 07:59 -0700, Sean Christopherson wrote:
> On Thu, Oct 23, 2025, Kai Huang wrote:
> > On Thu, 2025-10-16 at 17:32 -0700, Sean Christopherson wrote:

Yeah LGTM. Thanks.

---

## [57] Huang, Kai — 2025-10-23
*Subject: Re: [PATCH v3 11/25] KVM: TDX: Avoid a double-KVM_BUG_ON() in
 tdx_sept_zap_private_spte()*

On Thu, 2025-10-16 at 17:32 -0700, Sean Christopherson wrote:
> Return -EIO immediately from tdx_sept_zap_private_spte() if the number of
> to-be-added pages underflows, so that the following "KVM_BUG_ON(err, kvm)"

Reviewed-by: Kai Huang <kai.huang@intel.com>

---

## [58] Huang, Kai — 2025-10-23
*Subject: Re: [PATCH v3 13/25] KVM: TDX: Fold tdx_mem_page_record_premap_cnt()
 into its sole caller*

On Thu, 2025-10-16 at 17:32 -0700, Sean Christopherson wrote:
> Fold tdx_mem_page_record_premap_cnt() into tdx_sept_set_private_spte() as
> providing a one-off helper for effectively three lines of code is at best a

Reviewed-by: Kai Huang <kai.huang@intel.com>

> ---
>  arch/x86/kvm/vmx/tdx.c | 49 ++++++++++++++++++------------------------

Nit: the comment

  /* nr_premapped will be decreased when tdh_mem_page_add() is called. */

is lost.  I think we can somehow embed it to the big comment above?

---

## [59] Huang, Kai — 2025-10-23
*Subject: Re: [PATCH v3 14/25] KVM: TDX: Bug the VM if extended the initial
 measurement fails*

On Thu, 2025-10-16 at 17:32 -0700, Sean Christopherson wrote:
> WARN and terminate the VM if TDH_MR_EXTEND fails, as extending the
> measurement should fail if and only if there is a KVM bug, or if the S-EPT

So IIUC this patch only adds a KVM_BUG_ON() when TDH.MR.EXTEND fails.  How
does this fix anything?

Looking at v2, they may have a relationship, but it's quite confusing w/o
any explanation?

> Signed-off-by: Yan Zhao <yan.y.zhao@intel.com>
> Signed-off-by: Sean Christopherson <seanjc@google.com>

---

## [60] Huang, Kai — 2025-10-24
*Subject: Re: [PATCH v3 15/25] KVM: TDX: ADD pages to the TD image while
 populating mirror EPT entries*

On Thu, 2025-10-16 at 17:32 -0700, Sean Christopherson wrote:
> When populating the initial memory image for a TDX guest, ADD pages to the
> TD as part of establishing the mappings in the mirror EPT, as opposed to
				 ^
				 management

> to removal of S-EPT is _very_ subtle.  E.g. successful removal of an S-EPT
> entry after it completed ADD doesn't adjust nr_premapped, but it's not
		^
		during

> measurement can also be moved into the S-EPT mapping path (again, only if
> absolutely necessary).  P.S. _If_ MR.EXTEND is moved into the S-EPT path,

Reviewed-by: Kai Huang <kai.huang@intel.com>

---

## [61] Huang, Kai — 2025-10-24
*Subject: Re: [PATCH v3 13/25] KVM: TDX: Fold tdx_mem_page_record_premap_cnt()
 into its sole caller*

> > +	/*
> > +	 * If the TD isn't finalized/runnable, then userspace is initializing

Please ignore this.  I saw the whole 'nr_premapped' eventually got removed
later in this series so don't bother :-)

---

## [62] Binbin Wu — 2025-10-24
*Subject: Re: [PATCH v3 13/25] KVM: TDX: Fold tdx_mem_page_record_premap_cnt()
 into its sole caller*

On 10/17/2025 8:32 AM, Sean Christopherson wrote:
> Fold tdx_mem_page_record_premap_cnt() into tdx_sept_set_private_spte() as
> providing a one-off helper for effectively three lines of code is at best a

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

One nit below.

[...]
> +	/*
> +	 * If the TD isn't finalized/runnable, then userspace is initializing
                                                                    ^
                                                 Nit: Is pre-mapped better?
> +	 * have been added to the image, to prevent running the TD with a
> +	 * valid mapping in the mirror EPT, but not in the S-EPT.

---

## [63] Huang, Kai — 2025-10-24
*Subject: Re: [PATCH v3 16/25] KVM: TDX: Fold tdx_sept_zap_private_spte() into
 tdx_sept_remove_private_spte()*

On Thu, 2025-10-16 at 17:32 -0700, Sean Christopherson wrote:
> Do TDH_MEM_RANGE_BLOCK directly in tdx_sept_remove_private_spte() instead
> of using a one-off helper now that the nr_premapped tracking is gone.

Reviewed-by: Kai Huang <kai.huang@intel.com>

---

## [64] Yan Zhao — 2025-10-24
*Subject: Re: [PATCH v3 24/25] KVM: TDX: Guard VM state transitions with "all"
 the locks*

On Thu, Oct 16, 2025 at 05:32:42PM -0700, Sean Christopherson wrote:
> Acquire kvm->lock, kvm->slots_lock, and all vcpu->mutex locks when
> servicing ioctls that (a) transition the TD to a new state, i.e. when
slots_lock to prevent kvm_mmu_zap_memslot()?
kvm_mmu_zap_all_fast() does not operate on the mirror root.

We may have missed a zap in the guest_memfd punch hole path:

The SEAMCALLs tdh_mem_range_block(), tdh_mem_track() tdh_mem_page_remove()
in the guest_memfd punch hole path are only protected by the filemap invaliate
lock and mmu_lock, so they could contend with v1 version of tdh_vp_init().
(I'm writing a selftest to verify this, haven't been able to reproduce
tdh_vp_init(v1) returning BUSY yet. However, this race condition should be
theoretically possible.)

Resources              SHARED  users              EXCLUSIVE users
------------------------------------------------------------------------
(1) TDR                tdh_mng_rdwr               tdh_mng_create
                       tdh_vp_create              tdh_mng_add_cx
                       tdh_vp_addcx               tdh_mng_init
                       tdh_vp_init(v0)            tdh_mng_vpflushdone
                       tdh_vp_enter               tdh_mng_key_config
                       tdh_vp_flush               tdh_mng_key_freeid
                       tdh_vp_rd_wr               tdh_mr_extend
                       tdh_mem_sept_add           tdh_mr_finalize
                       tdh_mem_sept_remove        tdh_vp_init(v1)
                       tdh_mem_page_aug           tdh_mem_page_add
                       tdh_mem_page_remove
                       tdh_mem_range_block
                       tdh_mem_track
                       tdh_mem_range_unblock
                       tdh_phymem_page_reclaim

Do you think we can acquire the mmu_lock for cmd KVM_TDX_INIT_VCPU?

> @@ -3155,12 +3198,13 @@ int tdx_vcpu_unlocked_ioctl(struct kvm_vcpu *vcpu, void __user *argp)
>  	if (r)
Should we move the guard to inside each cmd? Then there's no need to acquire the
locks in the default cases.

---

## [65] Yan Zhao — 2025-10-24
*Subject: Re: [PATCH v3 19/25] KVM: TDX: Assert that mmu_lock is held for
 write when removing S-EPT entries*

On Thu, Oct 23, 2025 at 08:14:04AM -0700, Sean Christopherson wrote:
> On Thu, Oct 23, 2025, Yan Zhao wrote:
> > On Thu, Oct 16, 2025 at 05:32:37PM -0700, Sean Christopherson wrote:
LGTM. Thanks!

> From: Sean Christopherson <seanjc@google.com>
> Date: Thu, 28 Aug 2025 17:06:17 -0700

---

## [66] Huang, Kai — 2025-10-24
*Subject: Re: [PATCH v3 20/25] KVM: TDX: Add macro to retry SEAMCALLs when
 forcing vCPUs out of guest*

On Thu, 2025-10-16 at 17:32 -0700, Sean Christopherson wrote:
> Add a macro to handle kicking vCPUs out of the guest and retrying
> SEAMCALLs on -EBUSY instead of providing small helpers to be used by each

The comment which says "the second retry should succeed" is lost, could we
add it to tdh_do_no_vcpus()?

Also, perhaps we can just TDX_BUG_ON() inside tdh_do_no_vcpus() when the
second call of tdh_func() fails?

---

## [67] Huang, Kai — 2025-10-24
*Subject: Re: [PATCH v3 21/25] KVM: TDX: Add tdx_get_cmd() helper to get and
 validate sub-ioctl command*

On Thu, 2025-10-16 at 17:32 -0700, Sean Christopherson wrote:
> Add a helper to copy a kvm_tdx_cmd structure from userspace and verify
> that must-be-zero fields are indeed zero.

Reviewed-by: Kai Huang <kai.huang@intel.com>

> ---
>  arch/x86/kvm/vmx/tdx.c | 31 +++++++++++++++++--------------

Nit: to me it's a little bit pity to lose the below comment:

	/*
	 * Userspace should never set hw_error. It is used to fill
	 * hardware-defined error by the kernel.
	 */

---

## [68] Huang, Kai — 2025-10-24
*Subject: Re: [PATCH v3 22/25] KVM: TDX: Convert INIT_MEM_REGION and INIT_VCPU
 to "unlocked" vCPU ioctl*

On Thu, 2025-10-16 at 17:32 -0700, Sean Christopherson wrote:
> Handle the KVM_TDX_INIT_MEM_REGION and KVM_TDX_INIT_VCPU vCPU sub-ioctls
> in the unlocked variant, i.e. outside of vcpu->mutex, in anticipation of

Reviewed-by: Kai Huang <kai.huang@intel.com>

---

## [69] Huang, Kai — 2025-10-24
*Subject: Re: [PATCH v3 23/25] KVM: TDX: Use guard() to acquire kvm->lock in
 tdx_vm_ioctl()*

On Thu, 2025-10-16 at 17:32 -0700, Sean Christopherson wrote:
> Use guard() in tdx_vm_ioctl() to tidy up the code a small amount, but more
> importantly to minimize the diff of a future change, which will use

Reviewed-by: Kai Huang <kai.huang@intel.com>

---

## [70] Huang, Kai — 2025-10-24
*Subject: Re: [PATCH v3 24/25] KVM: TDX: Guard VM state transitions with "all"
 the locks*

>  
> +typedef void *tdx_vm_state_guard_t;

Since you are changing both tdx_td_init() and tdx_td_finalize(), maybe
just changing tdx_vm_ioctl() instead (like tdx_vcpu_unlocked_ioctl())?  
This is not required for tdx_get_capabilities() but there's no harm to do
it too AFACIT.

---

## [71] Sean Christopherson — 2025-10-24
*Subject: Re: [PATCH v3 13/25] KVM: TDX: Fold tdx_mem_page_record_premap_cnt()
 into its sole caller*

On Fri, Oct 24, 2025, Binbin Wu wrote:
> 
> 

Yeah, updated (and then it gets deleted a few commits later :-) ).

---

## [72] Sean Christopherson — 2025-10-24
*Subject: Re: [PATCH v3 14/25] KVM: TDX: Bug the VM if extended the initial
 measurement fails*

On Thu, Oct 23, 2025, Kai Huang wrote:
> On Thu, 2025-10-16 at 17:32 -0700, Sean Christopherson wrote:
> > WARN and terminate the VM if TDH_MR_EXTEND fails, as extending the

Hmm, yeah, I'll drop the Fixes.  It made more sense when I thought it was
impossible for tdh_mr_extend() to fail, as returning an error and not explicitly
terminating the VM was "wrong".  But I agree it does far more harm than good,
even when relocated to the end of the series.

---

## [73] Sean Christopherson — 2025-10-24
*Subject: Re: [PATCH v3 24/25] KVM: TDX: Guard VM state transitions with "all"
 the locks*

On Fri, Oct 24, 2025, Yan Zhao wrote:
> On Thu, Oct 16, 2025 at 05:32:42PM -0700, Sean Christopherson wrote:
> > Acquire kvm->lock, kvm->slots_lock, and all vcpu->mutex locks when

Oh, right.

> We may have missed a zap in the guest_memfd punch hole path:
> 

Ugh, I'd rather not?  Refresh me, what's the story with "v1"?  Are we now on v2?
If this is effectively limited to deprecated TDX modules, my vote would be to
ignore the flaw and avoid even more complexity in KVM.

> > @@ -3155,12 +3198,13 @@ int tdx_vcpu_unlocked_ioctl(struct kvm_vcpu *vcpu, void __user *argp)
> >  	if (r)

No, I don't think it's a good tradeoff.  We'd also need to move vcpu_{load,put}()
into the cmd helpers, and theoretically slowing down a bad ioctl invocation due
to taking extra locks is a complete non-issue.

---

## [74] Binbin Wu — 2025-10-27
*Subject: Re: [PATCH v3 13/25] KVM: TDX: Fold tdx_mem_page_record_premap_cnt()
 into its sole caller*

On 10/25/2025 12:33 AM, Sean Christopherson wrote:
> On Fri, Oct 24, 2025, Binbin Wu wrote:
>>
Oh, right, nr_premapped will be dropped later.

Since the whole nr_premapped will be dropped, do we still need a cleanup patch
like patch 12 which will be dropped finally?

---

## [75] Yan Zhao — 2025-10-27
*Subject: Re: [PATCH v3 24/25] KVM: TDX: Guard VM state transitions with "all"
 the locks*

On Fri, Oct 24, 2025 at 09:57:20AM -0700, Sean Christopherson wrote:
> On Fri, Oct 24, 2025, Yan Zhao wrote:
> > On Thu, Oct 16, 2025 at 05:32:42PM -0700, Sean Christopherson wrote:
No... We are now on v1.
As in [1], I found that TDX module changed SEAMCALL TDH_VP_INIT behavior to
require exclusive lock on resource TDR when leaf_opcode.version > 0.

Therefore, we moved KVM_TDX_INIT_VCPU to tdx_vcpu_unlocked_ioctl() in patch 22.

[1] https://lore.kernel.org/all/aLa34QCJCXGLk%2Ffl@yzhao56-desk.sh.intel.com/

> If this is effectively limited to deprecated TDX modules, my vote would be to
> ignore the flaw and avoid even more complexity in KVM.
Conversely, the new TDX module has this flaw...

> > > @@ -3155,12 +3198,13 @@ int tdx_vcpu_unlocked_ioctl(struct kvm_vcpu *vcpu, void __user *argp)
> > >  	if (r)
Fair enough.

---

## [76] Yan Zhao — 2025-10-27
*Subject: Re: [PATCH v3 14/25] KVM: TDX: Bug the VM if extended the initial
 measurement fails*

On Fri, Oct 24, 2025 at 09:35:43AM -0700, Sean Christopherson wrote:
> On Thu, Oct 23, 2025, Kai Huang wrote:
> > On Thu, 2025-10-16 at 17:32 -0700, Sean Christopherson wrote:
Maybe this tag is for patch 25?

> > So IIUC this patch only adds a KVM_BUG_ON() when TDH.MR.EXTEND fails.  How
> > does this fix anything?

---

## [77] Edgecombe, Rick P — 2025-10-27
*Subject: Re: [PATCH v3 24/25] KVM: TDX: Guard VM state transitions with "all"
 the locks*

On Mon, 2025-10-27 at 17:26 +0800, Yan Zhao wrote:
> > Ugh, I'd rather not?  Refresh me, what's the story with "v1"?  Are we now on
> > v2?

Looking at the PDF docs, TDR exclusive locking in version == 1 is called out at
least back to the oldest ABI docs I have (March 2024). Not sure about the
assertion that the behavior changed, but if indeed this was documented, it's a
little bit our bad. We might consider being flexible around calling it a TDX ABI
break?

Sean, can you elaborate why taking mmu_lock is objectionable here, though?

Note, myself (and I think Yan?) determined the locking by examining TDX module
source. For myself, it's possible I misread the locking originally.

Also, I'm not sure about switching gears at this point, but it makes me wonder
about the previously discussed option of trying to just duplicate the TDX locks
on the kernel side. Or perhaps make some kind of debug time lockdep type thing
to document/check the assumptions in the kernel. Something along the lines of
this patch, but to map the TDX locks to KVM locks or something. As we add more
things (DPAMT, etc), it doesn't seem like the TDX locking is getting tamer...

---

## [78] Sean Christopherson — 2025-10-27
*Subject: Re: [PATCH v3 24/25] KVM: TDX: Guard VM state transitions with "all"
 the locks*

On Mon, Oct 27, 2025, Rick P Edgecombe wrote:
> On Mon, 2025-10-27 at 17:26 +0800, Yan Zhao wrote:
> > > Ugh, I'd rather not?  Refresh me, what's the story with "v1"?  Are we now on

It's not, I was just hoping we could avoid yet more complexity.

Assuming we do indeed need to take mmu_lock, can you send a patch that applies
on top?  I'm not planning on sending any of this to stable@, so I don't see any
reason to try and juggle patches around.

> Note, myself (and I think Yan?) determined the locking by examining TDX module
> source. For myself, it's possible I misread the locking originally.

Please no.  At best that will yield a pile of effectively useless code.  At worst,
it will make us lazy and lead to real bugs because we don't propery guard the *KVM*
flows that need exclusivity relative to what is going on in the TDX-Module.

> Or perhaps make some kind of debug time lockdep type thing to document/check
> the assumptions in the kernel. Something along the lines of this patch, but

Hmm, I like the idea, but actually getting meaningful coverage could be quite
difficult.

---

## [79] Sean Christopherson — 2025-10-27
*Subject: Re: [PATCH v3 20/25] KVM: TDX: Add macro to retry SEAMCALLs when
 forcing vCPUs out of guest*

On Fri, Oct 24, 2025, Kai Huang wrote:
> On Thu, 2025-10-16 at 17:32 -0700, Sean Christopherson wrote:
> > Add a macro to handle kicking vCPUs out of the guest and retrying

+1, definitely needs a comment.

/*
 * Execute a SEAMCALL related to removing/blocking S-EPT entries, with a single
 * retry (if necessary) after forcing vCPUs to exit and wait for the operation
 * to complete.  All flows that remove/block S-EPT entries run with mmu_lock
 * held for write, i.e. are mutually exlusive with each other, but they aren't
 * mutually exclusive with vCPUs running (because that would be overkill), and
 * so can fail with "operand busy" if a vCPU acquires a required lock in the
 * TDX-Module.
 *
 * Note, the retry is guaranteed to succeed, absent KVM and/or TDX-Module bugs.
 */
 
> Also, perhaps we can just TDX_BUG_ON() inside tdh_do_no_vcpus() when the
> second call of tdh_func() fails?

Heh, this also caught my eye when typing up the comment.  Unfortunately, I don't
think it's worth doing the TDX_BUG_ON() inside the macro as that would require
plumbing in the UPPERCASE name, and doesn't work well with the variadic arguments,
e.g. TRACK wants TDX_BUG_ON(), but REMOVE and BLOCK want TDX_BUG_ON_2().

Given that REMOVE and BLOCK need to check the return value, getting the TDX_BUG_ON()
call into the macro wouldn't buy that much.

---

## [80] Huang, Kai — 2025-10-27
*Subject: Re: [PATCH v3 20/25] KVM: TDX: Add macro to retry SEAMCALLs when
 forcing vCPUs out of guest*

On Mon, 2025-10-27 at 12:20 -0700, Sean Christopherson wrote:
> On Fri, Oct 24, 2025, Kai Huang wrote:
> > On Thu, 2025-10-16 at 17:32 -0700, Sean Christopherson wrote:

LGTM.  Nit: is it more clear to just say they can contend with TDX guest?

   All flows that ..., but they aren't mutually exclusive with vCPUs
   running, i.e., they can also contend with TDCALL from guest and fail with
   "operand busy".

>  *
>  * Note, the retry is guaranteed to succeed, absent KVM and/or TDX-Module bugs.

Agreed.  Seems it sounds nice in concept but not in practice. :-)

---

## [81] Huang, Kai — 2025-10-28
*Subject: Re: [PATCH v3 24/25] KVM: TDX: Guard VM state transitions with "all"
 the locks*

On Thu, 2025-10-16 at 17:32 -0700, Sean Christopherson wrote:
> @@ -2781,8 +2827,6 @@ int tdx_vm_ioctl(struct kvm *kvm, void __user *argp)
>  	if (r)

IIRC, this patch removes grabbing the kvm->lock in tdx_vm_ioctl() but only
adds the "big hammer" to tdx_td_init() and tdx_td_finalize(), so the
tdx_get_capabilities() lost holding the kvm->lock.

As replied earlier, I think we can just hold the "big hammer" in
tdx_vm_ioctl()?

One thing is when tdx_vm_ioctl() is called, the TD may not have any vCPU
(e.g., for tdx_td_init()).  This means the "big hammer" will hold kvm-
>slots_lock w/o holding any lock of vCPU.  But IIUC this should be OK.

---

## [82] Rick Edgecombe — 2025-10-27
*Subject: [PATCH] KVM: TDX: Take MMU lock around tdh_vp_init()*

Take MMU lock around tdh_vp_init() in KVM_TDX_INIT_VCPU to prevent
meeting contention during retries in some no-fail MMU paths.

The TDX module takes various try-locks internally, which can cause
SEAMCALLs to return an error code when contention is met. Dealing with
an error in some of the MMU paths that make SEAMCALLs is not straight
forward, so KVM takes steps to ensure that these will meet no contention
during a single BUSY error retry. The whole scheme relies on KVM to take
appropriate steps to avoid making any SEAMCALLs that could contend while
the retry is happening.

Unfortunately, there is a case where contention could be met if userspace
does something unusual. Specifically, hole punching a gmem fd while
initializing the TD vCPU. The impact would be triggering a KVM_BUG_ON().

The resource being contended is called the "TDR resource" in TDX docs 
parlance. The tdh_vp_init() can take this resource as exclusive if the 
'version' passed is 1, which happens to be version the kernel passes. The 
various MMU operations (tdh_mem_range_block(), tdh_mem_track() and 
tdh_mem_page_remove()) take it as shared.

There isn't a KVM lock that maps conceptually and in a lock order friendly 
way to the TDR lock. So to minimize infrastructure, just take MMU lock 
around tdh_vp_init(). This makes the operations we care about mutually 
exclusive. Since the other operations are under a write mmu_lock, the code 
could just take the lock for read, however this is weirdly inverted from 
the actual underlying resource being contended. Since this is covering an 
edge case that shouldn't be hit in normal usage, be a little less weird 
and take the mmu_lock for write around the call.

Fixes: 02ab57707bdb ("KVM: TDX: Implement hooks to propagate changes of TDP MMU mirror page table")
Reported-by: Yan Zhao <yan.y.zhao@intel.com>
Suggested-by: Yan Zhao <yan.y.zhao@intel.com>
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
---
Hi,

It was indeed awkward, as Sean must have sniffed. But seems ok enough to
close the issue.

Yan, can you give it a look?

Posted here, but applies on top of this series.

Thanks,

Rick
---
 arch/x86/kvm/vmx/tdx.c | 15 ++++++++++++---
 1 file changed, 12 insertions(+), 3 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index daec88d4b88d..8bf5d2624152 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -2938,9 +2938,18 @@ static int tdx_td_vcpu_init(struct kvm_vcpu *vcpu, u64 vcpu_rcx)
 		}
 	}
 
-	err = tdh_vp_init(&tdx->vp, vcpu_rcx, vcpu->vcpu_id);
-	if (TDX_BUG_ON(err, TDH_VP_INIT, vcpu->kvm))
-		return -EIO;
+	/*
+	 * tdh_vp_init() can take a exclusive lock of the TDR resource inside
+	 * the TDX module. This resource is also taken as shared in several
+	 * no-fail MMU paths, which could return TDX_OPERAND_BUSY on contention.
+	 * A read lock here would be enough to exclude the contention, but take
+	 * a write lock to avoid the weird inversion.
+	 */
+	scoped_guard(write_lock, &vcpu->kvm->mmu_lock) {
+		err = tdh_vp_init(&tdx->vp, vcpu_rcx, vcpu->vcpu_id);
+		if (TDX_BUG_ON(err, TDH_VP_INIT, vcpu->kvm))
+			return -EIO;
+	}
 
 	vcpu->arch.mp_state = KVM_MP_STATE_RUNNABLE;

---

## [83] Sean Christopherson — 2025-10-27
*Subject: Re: [PATCH v3 13/25] KVM: TDX: Fold tdx_mem_page_record_premap_cnt()
 into its sole caller*

On Mon, Oct 27, 2025, Binbin Wu wrote:
> 
> 

We don't strictly "need" the cleanups, but IMO intermediate cleanups are often
worth doing even if they get thrown away, soo that the code is in a (hopefully)
better state when the "big" functional change comes along.  I.e. if code 'X' is
easier to understand than code 'Y', then theoretically/hopefully X=>Z is also
easier to understand than Y=>Z.

---

## [84] Sean Christopherson — 2025-10-27
*Subject: Re: [PATCH v3 24/25] KVM: TDX: Guard VM state transitions with "all"
 the locks*

On Tue, Oct 28, 2025, Kai Huang wrote:
> On Thu, 2025-10-16 at 17:32 -0700, Sean Christopherson wrote:
> > @@ -2781,8 +2827,6 @@ int tdx_vm_ioctl(struct kvm *kvm, void __user *argp)

Ooh, yeah, nice catch, that is indeed silly and unnecessary churn.

> As replied earlier, I think we can just hold the "big hammer" in
> tdx_vm_ioctl()?

Actually, I think we can have our cake and eat it too.  With this slotted in as
a prep patch, the big hammer can land directly in tdx_vm_ioctl(), without any
change in functionality for KVM_TDX_CAPABILITIES.

--
From: Sean Christopherson <seanjc@google.com>
Date: Mon, 27 Oct 2025 17:32:34 -0700
Subject: [PATCH] KVM: TDX: Don't copy "cmd" back to userspace for
 KVM_TDX_CAPABILITIES

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
index 1642da9c1fa9..43c0c3f6a8c0 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -2807,12 +2807,12 @@ int tdx_vm_ioctl(struct kvm *kvm, void __user *argp)
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

base-commit: 672537233b8da2c29dca7154bf3a3211af7f6128
--

---

## [85] Huang, Kai — 2025-10-28
*Subject: Re: [PATCH v3 24/25] KVM: TDX: Guard VM state transitions with "all"
 the locks*

On Mon, 2025-10-27 at 17:37 -0700, Sean Christopherson wrote:
> On Tue, Oct 28, 2025, Kai Huang wrote:
> > On Thu, 2025-10-16 at 17:32 -0700, Sean Christopherson wrote:

OK fine to me. :-)

Maybe add a comment saying tdx_get_capabilities() doesn't copy any data 
back to kvm_tdx_cmd structure, and doesn't need to take @kvm?  This gives
people some notice if they want to change in the future (not sure whether
any change will happen though).

>  	guard(mutex)(&kvm->lock);
>

---

## [86] Yan Zhao — 2025-10-28
*Subject: Re: [PATCH v3 24/25] KVM: TDX: Guard VM state transitions with "all"
 the locks*

On Tue, Oct 28, 2025 at 01:46:03AM +0800, Edgecombe, Rick P wrote:
> On Mon, 2025-10-27 at 17:26 +0800, Yan Zhao wrote:
> > > Ugh, I'd rather not?� Refresh me, what's the story with "v1"?� Are we now on
I apologize that the ABI documentation had already called this out earlier in
March 2024.

I determined the locking behavior by reading the TDX module's source code,
specifically, from public repo https://github.com/intel/tdx-module.git, branch
tdx_1.5.

I checked my git snapshot of that branch, and I think it's because back to my
checking time, branch tdx_1.5 was pointing to TDX_1.5.01, which did not include
the code for version 1.

commit 72d8cffb214b74ae94d75afce36423020f74b47c (HEAD -> tdx_1.5, tag: TDX_1.5.01)
Author: mvainer <michael1.vainer@intel.com>
Date:   Thu Feb 22 15:36:58 2024 +0200

    TDX 1.5.01

    Signed-off-by: mvainer <michael1.vainer@intel.com>



In that repository, the latest tdx_1.5 branch points to tag TDX_1.5.16.
The exclusive TDR lock in TDH.VP.INIT was introduced starting from TDX 1.5.05.


commit 147ba2973479be63147048954f77a0d7248fcc35
Author: Vainer, Michael1 <michael1.vainer@intel.com>
Date:   Mon Aug 11 11:53:07 2025 +0300

    TDX 1.5.05

    Signed-off-by: Vainer, Michael1 <michael1.vainer@intel.com>

diff --git a/src/vmm_dispatcher/api_calls/tdh_vp_init.c b/src/vmm_dispatcher/api_calls/tdh_vp_init.c
index ccb6b9e..ee51a18 100644
--- a/src/vmm_dispatcher/api_calls/tdh_vp_init.c
+++ b/src/vmm_dispatcher/api_calls/tdh_vp_init.c
@@ -114,6 +114,17 @@ api_error_type tdh_vp_init(uint64_t target_tdvpr_pa, uint64_t td_vcpu_rcx)

     api_error_type        return_val = UNINITIALIZE_ERROR;

+    tdx_leaf_and_version_t leaf_opcode;
+    leaf_opcode.raw = get_local_data()->vmm_regs.rax;
+
+    uint64_t x2apic_id = get_local_data()->vmm_regs.r8;
+
+    // TDH.VP.INIT supports version 1.  Other version checks are done by the SEAMCALL dispatcher.
+    if (leaf_opcode.version > 1)
+    {
+        return_val = api_error_with_operand_id(TDX_OPERAND_INVALID, OPERAND_ID_RAX);
+        goto EXIT;
+    }

     // Check and lock the parent TDVPR page
     return_val = check_and_lock_explicit_4k_private_hpa(tdvpr_pa,
@@ -129,11 +140,13 @@ api_error_type tdh_vp_init(uint64_t target_tdvpr_pa, uint64_t td_vcpu_rcx)
         goto EXIT;
     }

+    lock_type_t tdr_lock_type = (leaf_opcode.version > 0) ? TDX_LOCK_EXCLUSIVE : TDX_LOCK_SHARED;
+
     // Lock and map the TDR page
     return_val = lock_and_map_implicit_tdr(get_pamt_entry_owner(tdvpr_pamt_entry_ptr),
                                            OPERAND_ID_TDR,
                                            TDX_RANGE_RO,
-                                           TDX_LOCK_SHARED,
+                                           tdr_lock_type,
                                            &tdr_pamt_entry_ptr,
                                            &tdr_locked_flag,
                                            &tdr_ptr);
@@ -190,6 +203,32 @@ api_error_type tdh_vp_init(uint64_t target_tdvpr_pa, uint64_t td_vcpu_rcx)
     }
     tdvps_ptr->management.vcpu_index = vcpu_index;

+    if (leaf_opcode.version == 0)
+    {
+        // No x2APIC ID was provided
+        tdcs_ptr->executions_ctl_fields.topology_enum_configured = false;
+    }
+    else
+    {
+        // Check and save the configured x2APIC ID.  Upper 32 bits must be 0.
+        if (x2apic_id > 0xFFFFFFFF)
+        {
+            (void)_lock_xadd_32b(&tdcs_ptr->management_fields.num_vcpus, (uint32_t)-1);
+            return_val = api_error_with_operand_id(TDX_OPERAND_INVALID, OPERAND_ID_R8);
+            goto EXIT;
+        }
+
+        for (uint32_t i = 0; i < vcpu_index; i++)
+        {
+            if ((uint32_t)x2apic_id == tdcs_ptr->x2apic_ids[i])
+            {
+                return_val = api_error_with_operand_id(TDX_X2APIC_ID_NOT_UNIQUE, tdcs_ptr->x2apic_ids[i]);
+                goto EXIT;
+            }
+        }
+
+        tdcs_ptr->x2apic_ids[vcpu_index] = (uint32_t)x2apic_id;
+    }

     // We read TSC below.  Compare IA32_TSC_ADJUST to the value sampled on TDHSYSINIT
     // to make sure the host VMM doesn't play any trick on us. */
@@ -282,7 +321,7 @@ EXIT:
     }
     if (tdr_locked_flag)
     {
-        pamt_implicit_release_lock(tdr_pamt_entry_ptr, TDX_LOCK_SHARED);
+        pamt_implicit_release_lock(tdr_pamt_entry_ptr, tdr_lock_type);
         free_la(tdr_ptr);
     }
     if (tdvpr_locked_flag)

---

## [87] Yan Zhao — 2025-10-28
*Subject: Re: [PATCH] KVM: TDX: Take MMU lock around tdh_vp_init()*

On Mon, Oct 27, 2025 at 05:28:24PM -0700, Rick Edgecombe wrote:
> Take MMU lock around tdh_vp_init() in KVM_TDX_INIT_VCPU to prevent
> meeting contention during retries in some no-fail MMU paths.
It passed my local tests. LGTM. Thanks!

> Posted here, but applies on top of this series.
>

---

## [88] Edgecombe, Rick P — 2025-10-28
*Subject: Re: [PATCH v3 24/25] KVM: TDX: Guard VM state transitions with "all"
 the locks*

On Tue, 2025-10-28 at 09:37 +0800, Yan Zhao wrote:
> I checked my git snapshot of that branch, and I think it's because back to my
> checking time, branch tdx_1.5 was pointing to TDX_1.5.01, which did not include

Ah, that explains it. I've been looking more at the code for this kind of info
too. I guess we should cross check the docs more.

---

## [89] Binbin Wu — 2025-10-29
*Subject: Re: [PATCH] KVM: TDX: Take MMU lock around tdh_vp_init()*

On 10/28/2025 8:28 AM, Rick Edgecombe wrote:
> Take MMU lock around tdh_vp_init() in KVM_TDX_INIT_VCPU to prevent
> meeting contention during retries in some no-fail MMU paths.
                                   ^
                                   an

> +	 * the TDX module. This resource is also taken as shared in several
> +	 * no-fail MMU paths, which could return TDX_OPERAND_BUSY on contention.
Can we also add the description that the lock is trying to prevent an edge case
as in the change log if not too wordy?

> +	 */
> +	scoped_guard(write_lock, &vcpu->kvm->mmu_lock) {

---

## [90] Yan Zhao — 2025-10-30
*Subject: Re: [PATCH v3 04/25] KVM: x86/mmu: Add dedicated API to map
 guest_memfd pfn into TDP MMU*

On Wed, Oct 22, 2025 at 12:53:53PM +0800, Yan Zhao wrote:
> On Thu, Oct 16, 2025 at 05:32:22PM -0700, Sean Christopherson wrote:
> > Link: https://lore.kernel.org/all/20250709232103.zwmufocd3l7sqk7y@amd.com
[2] https://lore.kernel.org/all/cover.1760731772.git.ackerleytng@google.com/

Note: [1] is still required even with [2].

Consider the following scenario (assuming vm_memory_attributes=Y):

1. Create a TDX VM with non-in-place-conversion guest_memfd.

   In the init mem path, the lock sequence is
   lock(mapping.invalidate_lock#4) --> lock(&mm->mmap_lock)

2. Create a normal VM with in-place-conversion guest_memfd, with guest_memfd
   memory defaulting to shared by specifying flags
   GUEST_MEMFD_FLAG_MMAP | GUEST_MEMFD_FLAG_INIT_SHARED.
   (Since kvm_arch_supports_gmem_init_shared() returns true for normal VMs due
    to kvm->arch.has_private_mem == false, GUEST_MEMFD_FLAG_INIT_SHARED is a
    valid flag).

   Accessing the mmap'ed VA of this guest_memfd invokes
   kvm_gmem_fault_user_mapping().
   
   The lock sequence in this path is
   rlock(&mm->mmap_lock) --> rlock(mapping.invalidate_lock#4)

Running 1 & 2 in the same process would trigger a circular locking warning:

[  297.090165][ T3469] ======================================================
[  297.099976][ T3469] WARNING: possible circular locking dependency detected
[  297.109830][ T3469] 6.17.0-rc7-upstream+ #109 Tainted: G S
[  297.119825][ T3469] ------------------------------------------------------
[  297.129795][ T3469] tdx_vm_huge_pag/3469 is trying to acquire lock:
[  297.139032][ T3469] ff110004a0625c70 (mapping.invalidate_lock#4){++++}-{4:4}, at: kvm_gmem_fault_user_mapping+0xfc/0x4c0 [kvm]
[  297.156463][ T3469]
[  297.156463][ T3469] but task is already holding lock:
[  297.169168][ T3469] ff110004db628d80 (&mm->mmap_lock){++++}-{4:4}, at: lock_mm_and_find_vma+0x2d/0x520
[  297.184330][ T3469]
[  297.184330][ T3469] which lock already depends on the new lock.
[  297.184330][ T3469]
[  297.202954][ T3469]
[  297.202954][ T3469] the existing dependency chain (in reverse order) is:
[  297.217582][ T3469]
[  297.217582][ T3469] -> #1 (&mm->mmap_lock){++++}-{4:4}:
[  297.230618][ T3469]        __lock_acquire+0x5ba/0xa20
[  297.238730][ T3469]        lock_acquire.part.0+0xb4/0x240
[  297.247200][ T3469]        lock_acquire+0x60/0x130
[  297.254942][ T3469]        gup_fast_fallback+0x1fb/0x390
[  297.263269][ T3469]        get_user_pages_fast+0x8f/0xd0
[  297.271610][ T3469]        tdx_gmem_post_populate+0x163/0x640 [kvm_intel]
[  297.281603][ T3469]        kvm_gmem_populate+0x53b/0x960 [kvm]
[  297.290663][ T3469]        tdx_vcpu_init_mem_region+0x33b/0x530 [kvm_intel]
[  297.300978][ T3469]        tdx_vcpu_unlocked_ioctl+0x16f/0x250 [kvm_intel]
[  297.311245][ T3469]        vt_vcpu_mem_enc_unlocked_ioctl+0x6b/0xa0 [kvm_intel]
[  297.322045][ T3469]        kvm_arch_vcpu_unlocked_ioctl+0x50/0x80 [kvm]
[  297.332167][ T3469]        kvm_vcpu_ioctl+0x27b/0xf30 [kvm]
[  297.341084][ T3469]        __x64_sys_ioctl+0x13c/0x1d0
[  297.349416][ T3469]        x64_sys_call+0x10ee/0x20d0
[  297.357566][ T3469]        do_syscall_64+0xc9/0x400
[  297.365507][ T3469]        entry_SYSCALL_64_after_hwframe+0x77/0x7f
[  297.375053][ T3469]
[  297.375053][ T3469] -> #0 (mapping.invalidate_lock#4){++++}-{4:4}:
[  297.389364][ T3469]        check_prev_add+0x8b/0x4c0
[  297.397442][ T3469]        validate_chain+0x367/0x440
[  297.405580][ T3469]        __lock_acquire+0x5ba/0xa20
[  297.413664][ T3469]        lock_acquire.part.0+0xb4/0x240
[  297.422123][ T3469]        lock_acquire+0x60/0x130
[  297.429836][ T3469]        down_read+0x9f/0x540
[  297.437187][ T3469]        kvm_gmem_fault_user_mapping+0xfc/0x4c0 [kvm]
[  297.446895][ T3469]        __do_fault+0xf8/0x690
[  297.454304][ T3469]        do_shared_fault+0x8a/0x3b0
[  297.462205][ T3469]        do_fault+0xf0/0xb80
[  297.469355][ T3469]        handle_pte_fault+0x499/0x9a0
[  297.477294][ T3469]        __handle_mm_fault+0x98d/0x1100
[  297.485449][ T3469]        handle_mm_fault+0x1e2/0x500
[  297.493288][ T3469]        do_user_addr_fault+0x4f3/0xf20
[  297.501419][ T3469]        exc_page_fault+0x5d/0xc0
[  297.509027][ T3469]        asm_exc_page_fault+0x27/0x30
[  297.517003][ T3469]
[  297.517003][ T3469] other info that might help us debug this:
[  297.517003][ T3469]
[  297.534317][ T3469]  Possible unsafe locking scenario:
[  297.534317][ T3469]
[  297.546565][ T3469]        CPU0                    CPU1
[  297.554486][ T3469]        ----                    ----
[  297.562385][ T3469]   rlock(&mm->mmap_lock);
[  297.569203][ T3469]                                lock(mapping.invalidate_lock#4);
[  297.579871][ T3469]                                lock(&mm->mmap_lock);
[  297.589429][ T3469]   rlock(mapping.invalidate_lock#4);
[  297.597345][ T3469]
[  297.597345][ T3469]  *** DEADLOCK ***
[  297.597345][ T3469]
[  297.611988][ T3469] 1 lock held by tdx_vm_huge_pag/3469:
[  297.619863][ T3469]  #0: ff110004db628d80 (&mm->mmap_lock){++++}-{4:4}, at: lock_mm_and_find_vma+0x2d/0x520
[  297.634775][ T3469]
[  297.634775][ T3469] stack backtrace:
[  297.645161][ T3469] CPU: 7 UID: 0 PID: 3469 Comm: tdx_vm_huge_pag Tainted: G S                  6.17.0-rc7-upstream+ #109 PREEMPT(voluntary)  cdf4eff053c68cc34a4de47b373cdf3e020105d7
[  297.645166][ T3469] Tainted: [S]=CPU_OUT_OF_SPEC
[  297.645167][ T3469] Hardware name: Intel Corporation ArcherCity/ArcherCity, BIOS EGSDCRB1.SYS.0101.D29.2303301937 03/30/2023
[  297.645168][ T3469] Call Trace:
[  297.645170][ T3469]  <TASK>
[  297.645171][ T3469]  dump_stack_lvl+0x81/0xe0
[  297.645176][ T3469]  dump_stack+0x10/0x20
[  297.645178][ T3469]  print_circular_bug+0xf3/0x120
[  297.645181][ T3469]  check_noncircular+0x135/0x150
[  297.645186][ T3469]  check_prev_add+0x8b/0x4c0
[  297.645189][ T3469]  validate_chain+0x367/0x440
[  297.645192][ T3469]  __lock_acquire+0x5ba/0xa20
[  297.645196][ T3469]  lock_acquire.part.0+0xb4/0x240
[  297.645198][ T3469]  ? kvm_gmem_fault_user_mapping+0xfc/0x4c0 [kvm 92b56a1aeace799385454e64f4d853f860f01956]
[  297.645279][ T3469]  lock_acquire+0x60/0x130
[  297.645281][ T3469]  ? kvm_gmem_fault_user_mapping+0xfc/0x4c0 [kvm 92b56a1aeace799385454e64f4d853f860f01956]
[  297.645360][ T3469]  down_read+0x9f/0x540
[  297.645363][ T3469]  ? kvm_gmem_fault_user_mapping+0xfc/0x4c0 [kvm 92b56a1aeace799385454e64f4d853f860f01956]
[  297.645441][ T3469]  ? __pfx_down_read+0x10/0x10
[  297.645444][ T3469]  ? __this_cpu_preempt_check+0x13/0x20
[  297.645447][ T3469]  kvm_gmem_fault_user_mapping+0xfc/0x4c0 [kvm 92b56a1aeace799385454e64f4d853f860f01956]
[  297.645527][ T3469]  __do_fault+0xf8/0x690
[  297.645530][ T3469]  do_shared_fault+0x8a/0x3b0
[  297.645532][ T3469]  do_fault+0xf0/0xb80
[  297.645534][ T3469]  ? __this_cpu_preempt_check+0x13/0x20
[  297.645537][ T3469]  handle_pte_fault+0x499/0x9a0
[  297.645541][ T3469]  ? __pfx_handle_pte_fault+0x10/0x10
[  297.645545][ T3469]  __handle_mm_fault+0x98d/0x1100
[  297.645547][ T3469]  ? mt_find+0x3e3/0x5d0
[  297.645552][ T3469]  ? __pfx___handle_mm_fault+0x10/0x10
[  297.645557][ T3469]  ? __this_cpu_preempt_check+0x13/0x20
[  297.645560][ T3469]  handle_mm_fault+0x1e2/0x500
[  297.645563][ T3469]  ? __pfx_handle_mm_fault+0x10/0x10
[  297.645566][ T3469]  ? down_read_trylock+0x49/0x60
[  297.645571][ T3469]  do_user_addr_fault+0x4f3/0xf20
[  297.645575][ T3469]  exc_page_fault+0x5d/0xc0
[  297.645577][ T3469]  asm_exc_page_fault+0x27/0x30
[  297.645579][ T3469] RIP: 0033:0x41fba0
[  297.645581][ T3469] Code: f8 41 89 f0 48 8d 3c 17 48 89 c1 48 85 d2 74 2a 48 89 fa 48 29 c2 83 e2 01 74 0f 48 8d 48 01 40 88 71 ff 48 39 cf 74 13 66 90 <44> 88 01 48 83 c1 02 44 88 41 ff 48 39 cf 75 f0 c3 c3 66 66 2e 0f
[  297.645583][ T3469] RSP: 002b:00007ffc8037f1c8 EFLAGS: 00010246
[  297.645585][ T3469] RAX: 00007f604ee9d000 RBX: 00007f604ee906a8 RCX: 00007f604ee9d000
[  297.645587][ T3469] RDX: 0000000000000000 RSI: 00000000000000aa RDI: 00007f604ee9e000
[  297.645588][ T3469] RBP: 00007f604ee9d000 R08: 00000000000000aa R09: 0000000000426886
[  297.645589][ T3469] R10: 0000000000000001 R11: 0000000000000246 R12: 000000003b5502a0
[  297.645591][ T3469] R13: 0000000000001000 R14: 0000000000000200 R15: 00007f604eee4000
[  297.645595][ T3469]  </TASK>

---

## [91] Sean Christopherson — 2025-11-04
*Subject: Re: [PATCH v3 04/25] KVM: x86/mmu: Add dedicated API to map
 guest_memfd pfn into TDP MMU*

On Thu, Oct 30, 2025, Yan Zhao wrote:
> On Wed, Oct 22, 2025 at 12:53:53PM +0800, Yan Zhao wrote:
> > On Thu, Oct 16, 2025 at 05:32:22PM -0700, Sean Christopherson wrote:

If you (or anyone) has the bandwidth, please pick it up.  I won't have cycles to
look at that for many weeks (potentially not even this calendar year).

---

## [92] Yan Zhao — 2025-11-05
*Subject: Re: [PATCH v3 04/25] KVM: x86/mmu: Add dedicated API to map
 guest_memfd pfn into TDP MMU*

On Tue, Nov 04, 2025 at 09:57:26AM -0800, Sean Christopherson wrote:
> On Thu, Oct 30, 2025, Yan Zhao wrote:
> > On Wed, Oct 22, 2025 at 12:53:53PM +0800, Yan Zhao wrote:
Got it!
On the other hand, do you think we can address the warning as below?
The code is based on [2].

@@ -853,6 +859,10 @@ static int kvm_gmem_init_inode(struct inode *inode, loff_t size, u64 flags)
        inode->i_size = size;
        mapping_set_gfp_mask(inode->i_mapping, GFP_HIGHUSER);
        mapping_set_inaccessible(inode->i_mapping);
+       if (flags &GUEST_MEMFD_FLAG_MMAP)
+               lockdep_set_class_and_subclass(&inode->i_mapping->invalidate_lock,
+                                              &inode->i_sb->s_type->invalidate_lock_key, 1);
+
        /* Unmovable mappings are supposed to be marked unevictable as well. */
        WARN_ON_ONCE(!mapping_unevictable(inode->i_mapping));


As noted in [3], the only scenario can trigger the warning after [2] is when a
process creates a TDX VM with non-in-place-conversion guest_memfd and a normal
VM with in-place-conversion guest_memfd. The two invalidate_lock's don't contend
with each other theoretically.


[2] https://lore.kernel.org/all/cover.1760731772.git.ackerleytng@google.com/
[3] https://lore.kernel.org/all/aQMi%2Fn9DVyeaWsVH@yzhao56-desk.sh.intel.com/

---

## [93] Yan Zhao — 2025-11-05
*Subject: Re: [PATCH v3 04/25] KVM: x86/mmu: Add dedicated API to map
 guest_memfd pfn into TDP MMU*

On Wed, Nov 05, 2025 at 03:32:29PM +0800, Yan Zhao wrote:
> On Tue, Nov 04, 2025 at 09:57:26AM -0800, Sean Christopherson wrote:
> > On Thu, Oct 30, 2025, Yan Zhao wrote:
Hmm, updated the diff.

diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index 7b4a4474d468..543e1eb9db65 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -853,6 +853,9 @@ static int kvm_gmem_init_inode(struct inode *inode, loff_t size, u64 flags)
        inode->i_size = size;
        mapping_set_gfp_mask(inode->i_mapping, GFP_HIGHUSER);
        mapping_set_inaccessible(inode->i_mapping);
+       if (flags &GUEST_MEMFD_FLAG_MMAP)
+               lockdep_set_subclass(&inode->i_mapping->invalidate_lock, 1);
+
        /* Unmovable mappings are supposed to be marked unevictable as well. */
        WARN_ON_ONCE(!mapping_unevictable(inode->i_mapping));

 
> As noted in [3], the only scenario can trigger the warning after [2] is when a
> process creates a TDX VM with non-in-place-conversion guest_memfd and a normal

---

## [94] Sean Christopherson — 2025-11-05
*Subject: Re: [PATCH v3 04/25] KVM: x86/mmu: Add dedicated API to map
 guest_memfd pfn into TDP MMU*

On Wed, Nov 05, 2025, Yan Zhao wrote:
> On Wed, Nov 05, 2025 at 03:32:29PM +0800, Yan Zhao wrote:
> > On Tue, Nov 04, 2025 at 09:57:26AM -0800, Sean Christopherson wrote:

Hmm, no, I think we need to hoist gup() call outside of filemap_invalidate_lock(),
because I don't think this is strictly limited to TDX VMs without in-place
conversion.  Even with in-place conversion, I think KVM should allow the source
page to be shared memory, at which point I believe this becomes a legimate AB-BA
issue.

In general, playing lockdep games with so many subsystems involved terrifies me.

> > [2] https://lore.kernel.org/all/cover.1760731772.git.ackerleytng@google.com/
> > [3] https://lore.kernel.org/all/aQMi%2Fn9DVyeaWsVH@yzhao56-desk.sh.intel.com/

---

## [95] Sean Christopherson — 2025-11-18
*Subject: Re: [PATCH] KVM: TDX: Take MMU lock around tdh_vp_init()*

On Mon, Oct 27, 2025, Rick Edgecombe wrote:
> Take MMU lock around tdh_vp_init() in KVM_TDX_INIT_VCPU to prevent
> meeting contention during retries in some no-fail MMU paths.

In the future, please don't post in-reply-to, as it mucks up my b4 workflow.

Applied to kvm-x86 tdx, with a more verbose comment as suggested by Binbin.

[1/1] KVM: TDX: Take MMU lock around tdh_vp_init()
      https://github.com/kvm-x86/linux/commit/9a89894f30d5

---

## [96] Edgecombe, Rick P — 2025-11-19
*Subject: Re: [PATCH] KVM: TDX: Take MMU lock around tdh_vp_init()*

On Tue, 2025-11-18 at 15:31 -0800, Sean Christopherson wrote:
> In the future, please don't post in-reply-to, as it mucks up my b4 workflow.

Sure thing, sorry.

---

## [97] Edgecombe, Rick P — 2025-11-19
*Subject: Re: [PATCH] KVM: TDX: Take MMU lock around tdh_vp_init()*

On Tue, 2025-11-18 at 15:31 -0800, Sean Christopherson wrote:
> In the future, please don't post in-reply-to, as it mucks up my b4 workflow.

Sure thing, sorry.

---
