---
title: 'KVM: Export KVM-internal symbols for sub-modules only'
date: 2025-07-29
last_reply: 2025-08-25
message_count: 10
participants: ['Sean Christopherson', 'Huang, Kai', 'Anthony Krowiak', 'Vlastimil Babka']
---

## [1] Sean Christopherson — 2025-07-29

Use the newfangled EXPORT_SYMBOL_GPL_FOR_MODULES() along with some macro
shenanigans to export KVM-internal symbols if and only if KVM has one or
more sub-modules, and only for those sub-modules, e.g. x86's kvm-amd.ko
and/or kvm-intel.ko.

Patch 5 gives KVM x86 the full treatment.  If anyone wants to tackle PPC,
it should be doable to restrict KVM PPC's exports as well.

Patch 6 is essentially an RFC; it compiles and is tested, but it probably
should be chunked into multiple patches.  The main reason I included it
here is to get feedback on using kvm_types.h to define the "for KVM" macros.
For KVM itself, kvm_types.h is a solid choice, but it feels a bit awkward
for non-KVM usage, and including linux/kvm_types.h in non-KVM generic code,
e.g. in kernel/, isn't viable at the moment because asm/kvm_types.h is only
provided by architectures that actually support KVM.

Based on kvm/queue.

Sean Christopherson (6):
  KVM: s390/vfio-ap: Use kvm_is_gpa_in_memslot() instead of open coded
    equivalent
  KVM: Export KVM-internal symbols for sub-modules only
  KVM: x86: Move kvm_intr_is_single_vcpu() to lapic.c
  KVM: x86: Drop pointless exports of kvm_arch_xxx() hooks
  KVM: x86: Export KVM-internal symbols for sub-modules only
  x86: Restrict KVM-induced symbol exports to KVM modules where
    obvious/possible

 arch/powerpc/include/asm/kvm_types.h |  15 ++
 arch/s390/include/asm/kvm_host.h     |   2 +
 arch/s390/kvm/priv.c                 |   8 +
 arch/x86/entry/entry.S               |   7 +-
 arch/x86/entry/entry_64_fred.S       |   3 +-
 arch/x86/events/amd/core.c           |   5 +-
 arch/x86/events/core.c               |   7 +-
 arch/x86/events/intel/lbr.c          |   3 +-
 arch/x86/events/intel/pt.c           |   7 +-
 arch/x86/include/asm/kvm_host.h      |   3 -
 arch/x86/include/asm/kvm_types.h     |  15 ++
 arch/x86/kernel/apic/apic.c          |   3 +-
 arch/x86/kernel/apic/apic_common.c   |   3 +-
 arch/x86/kernel/cpu/amd.c            |   4 +-
 arch/x86/kernel/cpu/bugs.c           |  17 +--
 arch/x86/kernel/cpu/bus_lock.c       |   3 +-
 arch/x86/kernel/cpu/common.c         |   7 +-
 arch/x86/kernel/cpu/sgx/main.c       |   3 +-
 arch/x86/kernel/cpu/sgx/virt.c       |   5 +-
 arch/x86/kernel/e820.c               |   3 +-
 arch/x86/kernel/fpu/core.c           |  21 +--
 arch/x86/kernel/fpu/xstate.c         |   7 +-
 arch/x86/kernel/hw_breakpoint.c      |   3 +-
 arch/x86/kernel/irq.c                |   3 +-
 arch/x86/kernel/kvm.c                |   5 +-
 arch/x86/kernel/nmi.c                |   5 +-
 arch/x86/kernel/process_64.c         |   5 +-
 arch/x86/kernel/reboot.c             |   5 +-
 arch/x86/kernel/tsc.c                |   1 +
 arch/x86/kvm/cpuid.c                 |  10 +-
 arch/x86/kvm/hyperv.c                |   4 +-
 arch/x86/kvm/irq.c                   |  34 +----
 arch/x86/kvm/kvm_onhyperv.c          |   6 +-
 arch/x86/kvm/lapic.c                 |  70 ++++++---
 arch/x86/kvm/lapic.h                 |   4 +-
 arch/x86/kvm/mmu/mmu.c               |  36 ++---
 arch/x86/kvm/mmu/spte.c              |  10 +-
 arch/x86/kvm/mmu/tdp_mmu.c           |   2 +-
 arch/x86/kvm/pmu.c                   |   8 +-
 arch/x86/kvm/smm.c                   |   2 +-
 arch/x86/kvm/x86.c                   | 211 +++++++++++++--------------
 arch/x86/lib/cache-smp.c             |   9 +-
 arch/x86/lib/msr.c                   |   5 +-
 arch/x86/mm/pat/memtype.c            |   3 +-
 arch/x86/mm/tlb.c                    |   5 +-
 arch/x86/virt/vmx/tdx/tdx.c          |  65 +++++----
 drivers/s390/crypto/vfio_ap_ops.c    |   2 +-
 include/linux/kvm_types.h            |  39 ++++-
 virt/kvm/eventfd.c                   |   2 +-
 virt/kvm/guest_memfd.c               |   4 +-
 virt/kvm/kvm_main.c                  | 126 ++++++++--------
 51 files changed, 457 insertions(+), 378 deletions(-)
 create mode 100644 arch/powerpc/include/asm/kvm_types.h


base-commit: beafd7ecf2255e8b62a42dc04f54843033db3d24

---

## [2] Sean Christopherson — 2025-07-29
*Subject: [PATCH 1/6] KVM: s390/vfio-ap: Use kvm_is_gpa_in_memslot() instead of
 open coded equivalent*

Use kvm_is_gpa_in_memslot() to check the validity of the notification
indicator byte address instead of open coding equivalent logic in the VFIO
AP driver.

Opportunistically use a dedicated wrapper that exists and is exported
expressly for the VFIO AP module.  kvm_is_gpa_in_memslot() is generally
unsuitable for use outside of KVM; other drivers typically shouldn't rely
on KVM's memslots, and using the API requires kvm->srcu (or slots_lock) to
be held for the entire duration of the usage, e.g. to avoid TOCTOU bugs.
handle_pqap() is a bit of a special case, as it's explicitly invoked from
KVM with kvm->srcu already held, and the VFIO AP driver is in many ways an
extension of KVM that happens to live in a separate module.

Providing a dedicated API for the VFIO AP driver will allow restricting
the vast majority of generic KVM's exports to KVM submodules (e.g. to x86's
kvm-{amd,intel}.ko vendor mdoules).

No functional change intended.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/s390/include/asm/kvm_host.h  | 2 ++
 arch/s390/kvm/priv.c              | 8 ++++++++
 drivers/s390/crypto/vfio_ap_ops.c | 2 +-
 3 files changed, 11 insertions(+), 1 deletion(-)

diff --git a/arch/s390/include/asm/kvm_host.h b/arch/s390/include/asm/kvm_host.h
index cb89e54ada25..449bc34e7cc3 100644
--- a/arch/s390/include/asm/kvm_host.h
+++ b/arch/s390/include/asm/kvm_host.h
@@ -719,6 +719,8 @@ bool kvm_s390_pv_cpu_is_protected(struct kvm_vcpu *vcpu);
 extern int kvm_s390_gisc_register(struct kvm *kvm, u32 gisc);
 extern int kvm_s390_gisc_unregister(struct kvm *kvm, u32 gisc);
 
+bool kvm_s390_is_gpa_in_memslot(struct kvm *kvm, gpa_t gpa);
+
 static inline void kvm_arch_free_memslot(struct kvm *kvm,
 					 struct kvm_memory_slot *slot) {}
 static inline void kvm_arch_memslots_updated(struct kvm *kvm, u64 gen) {}
diff --git a/arch/s390/kvm/priv.c b/arch/s390/kvm/priv.c
index 9253c70897a8..7773e1e323bc 100644
--- a/arch/s390/kvm/priv.c
+++ b/arch/s390/kvm/priv.c
@@ -605,6 +605,14 @@ static int handle_io_inst(struct kvm_vcpu *vcpu)
 	}
 }
 
+#if IS_ENABLED(CONFIG_VFIO_AP)
+bool kvm_s390_is_gpa_in_memslot(struct kvm *kvm, gpa_t gpa)
+{
+	return kvm_is_gpa_in_memslot(kvm, gpa);
+}
+EXPORT_SYMBOL_GPL_FOR_MODULES(kvm_s390_is_gpa_in_memslot, "vfio_ap");
+#endif
+
 /*
  * handle_pqap: Handling pqap interception
  * @vcpu: the vcpu having issue the pqap instruction
diff --git a/drivers/s390/crypto/vfio_ap_ops.c b/drivers/s390/crypto/vfio_ap_ops.c
index 766557547f83..eb5ff49f6fe7 100644
--- a/drivers/s390/crypto/vfio_ap_ops.c
+++ b/drivers/s390/crypto/vfio_ap_ops.c
@@ -354,7 +354,7 @@ static int vfio_ap_validate_nib(struct kvm_vcpu *vcpu, dma_addr_t *nib)
 
 	if (!*nib)
 		return -EINVAL;
-	if (kvm_is_error_hva(gfn_to_hva(vcpu->kvm, *nib >> PAGE_SHIFT)))
+	if (!kvm_s390_is_gpa_in_memslot(vcpu->kvm, *nib))
 		return -EINVAL;
 
 	return 0;

---

## [3] Sean Christopherson — 2025-07-29
*Subject: [PATCH 2/6] KVM: Export KVM-internal symbols for sub-modules only*

Rework the vast majority of KVM's exports to expose symbols only to KVM
submodules, i.e. to x86's kvm-{amd,intel}.ko and PPC's kvm-{pr,hv}.ko.
With few exceptions, KVM's exported APIs are intended (and safe) for KVM-
internal usage only.

Keep kvm_get_kvm(), kvm_get_kvm_safe(), and kvm_put_kvm() as normal
exports, as they are needed by VFIO, and are generally safe for external
usage (though ideally even the get/put APIs would be KVM-internal, and
VFIO would pin a VM by grabbing a reference to its associated file).

Implement a framework in kvm_types.h in anticipation of providing a macro
to restrict KVM-specific kernel exports, i.e. to provide symbol exports
for KVM if and only if KVM is built as one or more modules.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/powerpc/include/asm/kvm_types.h |  15 ++++
 arch/x86/include/asm/kvm_types.h     |  10 +++
 include/linux/kvm_types.h            |  25 ++++--
 virt/kvm/eventfd.c                   |   2 +-
 virt/kvm/guest_memfd.c               |   4 +-
 virt/kvm/kvm_main.c                  | 126 +++++++++++++--------------
 6 files changed, 109 insertions(+), 73 deletions(-)
 create mode 100644 arch/powerpc/include/asm/kvm_types.h

diff --git a/arch/powerpc/include/asm/kvm_types.h b/arch/powerpc/include/asm/kvm_types.h
new file mode 100644
index 000000000000..656b498ed3b6
--- /dev/null
+++ b/arch/powerpc/include/asm/kvm_types.h
@@ -0,0 +1,15 @@
+/* SPDX-License-Identifier: GPL-2.0 */
+#ifndef _ASM_PPC_KVM_TYPES_H
+#define _ASM_PPC_KVM_TYPES_H
+
+#if IS_MODULE(CONFIG_KVM_BOOK3S_64_PR) && IS_MODULE(CONFIG_KVM_BOOK3S_64_HV)
+#define KVM_SUB_MODULES kvm-pr,kvm-hv
+#elif IS_MODULE(CONFIG_KVM_BOOK3S_64_PR)
+#define KVM_SUB_MODULES kvm-pr
+#elif IS_MODULE(CONFIG_KVM_INTEL)
+#define KVM_SUB_MODULES kvm-hv
+#else
+#undef KVM_SUB_MODULES
+#endif
+
+#endif
diff --git a/arch/x86/include/asm/kvm_types.h b/arch/x86/include/asm/kvm_types.h
index 08f1b57d3b62..23268a188e70 100644
--- a/arch/x86/include/asm/kvm_types.h
+++ b/arch/x86/include/asm/kvm_types.h
@@ -2,6 +2,16 @@
 #ifndef _ASM_X86_KVM_TYPES_H
 #define _ASM_X86_KVM_TYPES_H
 
+#if IS_MODULE(CONFIG_KVM_AMD) && IS_MODULE(CONFIG_KVM_INTEL)
+#define KVM_SUB_MODULES kvm-amd,kvm-intel
+#elif IS_MODULE(CONFIG_KVM_AMD)
+#define KVM_SUB_MODULES kvm-amd
+#elif IS_MODULE(CONFIG_KVM_INTEL)
+#define KVM_SUB_MODULES kvm-intel
+#else
+#undef KVM_SUB_MODULES
+#endif
+
 #define KVM_ARCH_NR_OBJS_PER_MEMORY_CACHE 40
 
 #endif /* _ASM_X86_KVM_TYPES_H */
diff --git a/include/linux/kvm_types.h b/include/linux/kvm_types.h
index 827ecc0b7e10..92a7051c1c9c 100644
--- a/include/linux/kvm_types.h
+++ b/include/linux/kvm_types.h
@@ -3,6 +3,23 @@
 #ifndef __KVM_TYPES_H__
 #define __KVM_TYPES_H__
 
+#include <linux/bits.h>
+#include <linux/export.h>
+#include <linux/types.h>
+#include <asm/kvm_types.h>
+
+#ifdef KVM_SUB_MODULES
+#define EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(symbol) \
+	EXPORT_SYMBOL_GPL_FOR_MODULES(symbol, __stringify(KVM_SUB_MODULES))
+#else
+#define EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(symbol)
+#endif
+
+#ifndef __ASSEMBLER__
+
+#include <linux/mutex.h>
+#include <linux/spinlock_types.h>
+
 struct kvm;
 struct kvm_async_pf;
 struct kvm_device_ops;
@@ -19,13 +36,6 @@ struct kvm_memslots;
 
 enum kvm_mr_change;
 
-#include <linux/bits.h>
-#include <linux/mutex.h>
-#include <linux/types.h>
-#include <linux/spinlock_types.h>
-
-#include <asm/kvm_types.h>
-
 /*
  * Address types:
  *
@@ -116,5 +126,6 @@ struct kvm_vcpu_stat_generic {
 };
 
 #define KVM_STATS_NAME_SIZE	48
+#endif /* !__ASSEMBLER__ */
 
 #endif /* __KVM_TYPES_H__ */
diff --git a/virt/kvm/eventfd.c b/virt/kvm/eventfd.c
index 6b1133a6617f..be73b147ba6f 100644
--- a/virt/kvm/eventfd.c
+++ b/virt/kvm/eventfd.c
@@ -525,7 +525,7 @@ bool kvm_irq_has_notifier(struct kvm *kvm, unsigned irqchip, unsigned pin)
 
 	return false;
 }
-EXPORT_SYMBOL_GPL(kvm_irq_has_notifier);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_irq_has_notifier);
 
 void kvm_notify_acked_gsi(struct kvm *kvm, int gsi)
 {
diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index 7d85cc33c0bb..dd699dea8fd9 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -625,7 +625,7 @@ int kvm_gmem_get_pfn(struct kvm *kvm, struct kvm_memory_slot *slot,
 	fput(file);
 	return r;
 }
-EXPORT_SYMBOL_GPL(kvm_gmem_get_pfn);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_gmem_get_pfn);
 
 #ifdef CONFIG_KVM_GENERIC_PRIVATE_MEM
 long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long npages,
@@ -707,5 +707,5 @@ long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long
 	fput(file);
 	return ret && !i ? ret : i;
 }
-EXPORT_SYMBOL_GPL(kvm_gmem_populate);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_gmem_populate);
 #endif
diff --git a/virt/kvm/kvm_main.c b/virt/kvm/kvm_main.c
index 6c07dd423458..ce50398aa0a5 100644
--- a/virt/kvm/kvm_main.c
+++ b/virt/kvm/kvm_main.c
@@ -77,22 +77,22 @@ MODULE_LICENSE("GPL");
 /* Architectures should define their poll value according to the halt latency */
 unsigned int halt_poll_ns = KVM_HALT_POLL_NS_DEFAULT;
 module_param(halt_poll_ns, uint, 0644);
-EXPORT_SYMBOL_GPL(halt_poll_ns);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(halt_poll_ns);
 
 /* Default doubles per-vcpu halt_poll_ns. */
 unsigned int halt_poll_ns_grow = 2;
 module_param(halt_poll_ns_grow, uint, 0644);
-EXPORT_SYMBOL_GPL(halt_poll_ns_grow);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(halt_poll_ns_grow);
 
 /* The start value to grow halt_poll_ns from */
 unsigned int halt_poll_ns_grow_start = 10000; /* 10us */
 module_param(halt_poll_ns_grow_start, uint, 0644);
-EXPORT_SYMBOL_GPL(halt_poll_ns_grow_start);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(halt_poll_ns_grow_start);
 
 /* Default halves per-vcpu halt_poll_ns. */
 unsigned int halt_poll_ns_shrink = 2;
 module_param(halt_poll_ns_shrink, uint, 0644);
-EXPORT_SYMBOL_GPL(halt_poll_ns_shrink);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(halt_poll_ns_shrink);
 
 /*
  * Allow direct access (from KVM or the CPU) without MMU notifier protection
@@ -170,7 +170,7 @@ void vcpu_load(struct kvm_vcpu *vcpu)
 	kvm_arch_vcpu_load(vcpu, cpu);
 	put_cpu();
 }
-EXPORT_SYMBOL_GPL(vcpu_load);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(vcpu_load);
 
 void vcpu_put(struct kvm_vcpu *vcpu)
 {
@@ -180,7 +180,7 @@ void vcpu_put(struct kvm_vcpu *vcpu)
 	__this_cpu_write(kvm_running_vcpu, NULL);
 	preempt_enable();
 }
-EXPORT_SYMBOL_GPL(vcpu_put);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(vcpu_put);
 
 /* TODO: merge with kvm_arch_vcpu_should_kick */
 static bool kvm_request_needs_ipi(struct kvm_vcpu *vcpu, unsigned req)
@@ -288,7 +288,7 @@ bool kvm_make_all_cpus_request(struct kvm *kvm, unsigned int req)
 
 	return called;
 }
-EXPORT_SYMBOL_GPL(kvm_make_all_cpus_request);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_make_all_cpus_request);
 
 void kvm_flush_remote_tlbs(struct kvm *kvm)
 {
@@ -309,7 +309,7 @@ void kvm_flush_remote_tlbs(struct kvm *kvm)
 	    || kvm_make_all_cpus_request(kvm, KVM_REQ_TLB_FLUSH))
 		++kvm->stat.generic.remote_tlb_flush;
 }
-EXPORT_SYMBOL_GPL(kvm_flush_remote_tlbs);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_flush_remote_tlbs);
 
 void kvm_flush_remote_tlbs_range(struct kvm *kvm, gfn_t gfn, u64 nr_pages)
 {
@@ -499,7 +499,7 @@ void kvm_destroy_vcpus(struct kvm *kvm)
 
 	atomic_set(&kvm->online_vcpus, 0);
 }
-EXPORT_SYMBOL_GPL(kvm_destroy_vcpus);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_destroy_vcpus);
 
 #ifdef CONFIG_KVM_GENERIC_MMU_NOTIFIER
 static inline struct kvm *mmu_notifier_to_kvm(struct mmu_notifier *mn)
@@ -1356,7 +1356,7 @@ void kvm_put_kvm_no_destroy(struct kvm *kvm)
 {
 	WARN_ON(refcount_dec_and_test(&kvm->users_count));
 }
-EXPORT_SYMBOL_GPL(kvm_put_kvm_no_destroy);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_put_kvm_no_destroy);
 
 static int kvm_vm_release(struct inode *inode, struct file *filp)
 {
@@ -1388,7 +1388,7 @@ int kvm_trylock_all_vcpus(struct kvm *kvm)
 	}
 	return -EINTR;
 }
-EXPORT_SYMBOL_GPL(kvm_trylock_all_vcpus);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_trylock_all_vcpus);
 
 int kvm_lock_all_vcpus(struct kvm *kvm)
 {
@@ -1413,7 +1413,7 @@ int kvm_lock_all_vcpus(struct kvm *kvm)
 	}
 	return r;
 }
-EXPORT_SYMBOL_GPL(kvm_lock_all_vcpus);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_lock_all_vcpus);
 
 void kvm_unlock_all_vcpus(struct kvm *kvm)
 {
@@ -1425,7 +1425,7 @@ void kvm_unlock_all_vcpus(struct kvm *kvm)
 	kvm_for_each_vcpu(i, vcpu, kvm)
 		mutex_unlock(&vcpu->mutex);
 }
-EXPORT_SYMBOL_GPL(kvm_unlock_all_vcpus);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_unlock_all_vcpus);
 
 /*
  * Allocation size is twice as large as the actual dirty bitmap size.
@@ -2133,7 +2133,7 @@ int kvm_set_internal_memslot(struct kvm *kvm,
 
 	return kvm_set_memory_region(kvm, mem);
 }
-EXPORT_SYMBOL_GPL(kvm_set_internal_memslot);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_set_internal_memslot);
 
 static int kvm_vm_ioctl_set_memory_region(struct kvm *kvm,
 					  struct kvm_userspace_memory_region2 *mem)
@@ -2192,7 +2192,7 @@ int kvm_get_dirty_log(struct kvm *kvm, struct kvm_dirty_log *log,
 		*is_dirty = 1;
 	return 0;
 }
-EXPORT_SYMBOL_GPL(kvm_get_dirty_log);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_get_dirty_log);
 
 #else /* CONFIG_KVM_GENERIC_DIRTYLOG_READ_PROTECT */
 /**
@@ -2627,7 +2627,7 @@ struct kvm_memory_slot *gfn_to_memslot(struct kvm *kvm, gfn_t gfn)
 {
 	return __gfn_to_memslot(kvm_memslots(kvm), gfn);
 }
-EXPORT_SYMBOL_GPL(gfn_to_memslot);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(gfn_to_memslot);
 
 struct kvm_memory_slot *kvm_vcpu_gfn_to_memslot(struct kvm_vcpu *vcpu, gfn_t gfn)
 {
@@ -2668,7 +2668,7 @@ bool kvm_is_visible_gfn(struct kvm *kvm, gfn_t gfn)
 
 	return kvm_is_visible_memslot(memslot);
 }
-EXPORT_SYMBOL_GPL(kvm_is_visible_gfn);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_is_visible_gfn);
 
 bool kvm_vcpu_is_visible_gfn(struct kvm_vcpu *vcpu, gfn_t gfn)
 {
@@ -2676,7 +2676,7 @@ bool kvm_vcpu_is_visible_gfn(struct kvm_vcpu *vcpu, gfn_t gfn)
 
 	return kvm_is_visible_memslot(memslot);
 }
-EXPORT_SYMBOL_GPL(kvm_vcpu_is_visible_gfn);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_vcpu_is_visible_gfn);
 
 unsigned long kvm_host_page_size(struct kvm_vcpu *vcpu, gfn_t gfn)
 {
@@ -2733,19 +2733,19 @@ unsigned long gfn_to_hva_memslot(struct kvm_memory_slot *slot,
 {
 	return gfn_to_hva_many(slot, gfn, NULL);
 }
-EXPORT_SYMBOL_GPL(gfn_to_hva_memslot);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(gfn_to_hva_memslot);
 
 unsigned long gfn_to_hva(struct kvm *kvm, gfn_t gfn)
 {
 	return gfn_to_hva_many(gfn_to_memslot(kvm, gfn), gfn, NULL);
 }
-EXPORT_SYMBOL_GPL(gfn_to_hva);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(gfn_to_hva);
 
 unsigned long kvm_vcpu_gfn_to_hva(struct kvm_vcpu *vcpu, gfn_t gfn)
 {
 	return gfn_to_hva_many(kvm_vcpu_gfn_to_memslot(vcpu, gfn), gfn, NULL);
 }
-EXPORT_SYMBOL_GPL(kvm_vcpu_gfn_to_hva);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_vcpu_gfn_to_hva);
 
 /*
  * Return the hva of a @gfn and the R/W attribute if possible.
@@ -2809,7 +2809,7 @@ void kvm_release_page_clean(struct page *page)
 	kvm_set_page_accessed(page);
 	put_page(page);
 }
-EXPORT_SYMBOL_GPL(kvm_release_page_clean);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_release_page_clean);
 
 void kvm_release_page_dirty(struct page *page)
 {
@@ -2819,7 +2819,7 @@ void kvm_release_page_dirty(struct page *page)
 	kvm_set_page_dirty(page);
 	kvm_release_page_clean(page);
 }
-EXPORT_SYMBOL_GPL(kvm_release_page_dirty);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_release_page_dirty);
 
 static kvm_pfn_t kvm_resolve_pfn(struct kvm_follow_pfn *kfp, struct page *page,
 				 struct follow_pfnmap_args *map, bool writable)
@@ -3063,7 +3063,7 @@ kvm_pfn_t __kvm_faultin_pfn(const struct kvm_memory_slot *slot, gfn_t gfn,
 
 	return kvm_follow_pfn(&kfp);
 }
-EXPORT_SYMBOL_GPL(__kvm_faultin_pfn);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(__kvm_faultin_pfn);
 
 int kvm_prefetch_pages(struct kvm_memory_slot *slot, gfn_t gfn,
 		       struct page **pages, int nr_pages)
@@ -3080,7 +3080,7 @@ int kvm_prefetch_pages(struct kvm_memory_slot *slot, gfn_t gfn,
 
 	return get_user_pages_fast_only(addr, nr_pages, FOLL_WRITE, pages);
 }
-EXPORT_SYMBOL_GPL(kvm_prefetch_pages);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_prefetch_pages);
 
 /*
  * Don't use this API unless you are absolutely, positively certain that KVM
@@ -3102,7 +3102,7 @@ struct page *__gfn_to_page(struct kvm *kvm, gfn_t gfn, bool write)
 	(void)kvm_follow_pfn(&kfp);
 	return refcounted_page;
 }
-EXPORT_SYMBOL_GPL(__gfn_to_page);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(__gfn_to_page);
 
 int __kvm_vcpu_map(struct kvm_vcpu *vcpu, gfn_t gfn, struct kvm_host_map *map,
 		   bool writable)
@@ -3136,7 +3136,7 @@ int __kvm_vcpu_map(struct kvm_vcpu *vcpu, gfn_t gfn, struct kvm_host_map *map,
 
 	return map->hva ? 0 : -EFAULT;
 }
-EXPORT_SYMBOL_GPL(__kvm_vcpu_map);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(__kvm_vcpu_map);
 
 void kvm_vcpu_unmap(struct kvm_vcpu *vcpu, struct kvm_host_map *map)
 {
@@ -3164,7 +3164,7 @@ void kvm_vcpu_unmap(struct kvm_vcpu *vcpu, struct kvm_host_map *map)
 	map->page = NULL;
 	map->pinned_page = NULL;
 }
-EXPORT_SYMBOL_GPL(kvm_vcpu_unmap);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_vcpu_unmap);
 
 static int next_segment(unsigned long len, int offset)
 {
@@ -3200,7 +3200,7 @@ int kvm_read_guest_page(struct kvm *kvm, gfn_t gfn, void *data, int offset,
 
 	return __kvm_read_guest_page(slot, gfn, data, offset, len);
 }
-EXPORT_SYMBOL_GPL(kvm_read_guest_page);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_read_guest_page);
 
 int kvm_vcpu_read_guest_page(struct kvm_vcpu *vcpu, gfn_t gfn, void *data,
 			     int offset, int len)
@@ -3209,7 +3209,7 @@ int kvm_vcpu_read_guest_page(struct kvm_vcpu *vcpu, gfn_t gfn, void *data,
 
 	return __kvm_read_guest_page(slot, gfn, data, offset, len);
 }
-EXPORT_SYMBOL_GPL(kvm_vcpu_read_guest_page);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_vcpu_read_guest_page);
 
 int kvm_read_guest(struct kvm *kvm, gpa_t gpa, void *data, unsigned long len)
 {
@@ -3229,7 +3229,7 @@ int kvm_read_guest(struct kvm *kvm, gpa_t gpa, void *data, unsigned long len)
 	}
 	return 0;
 }
-EXPORT_SYMBOL_GPL(kvm_read_guest);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_read_guest);
 
 int kvm_vcpu_read_guest(struct kvm_vcpu *vcpu, gpa_t gpa, void *data, unsigned long len)
 {
@@ -3249,7 +3249,7 @@ int kvm_vcpu_read_guest(struct kvm_vcpu *vcpu, gpa_t gpa, void *data, unsigned l
 	}
 	return 0;
 }
-EXPORT_SYMBOL_GPL(kvm_vcpu_read_guest);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_vcpu_read_guest);
 
 static int __kvm_read_guest_atomic(struct kvm_memory_slot *slot, gfn_t gfn,
 			           void *data, int offset, unsigned long len)
@@ -3280,7 +3280,7 @@ int kvm_vcpu_read_guest_atomic(struct kvm_vcpu *vcpu, gpa_t gpa,
 
 	return __kvm_read_guest_atomic(slot, gfn, data, offset, len);
 }
-EXPORT_SYMBOL_GPL(kvm_vcpu_read_guest_atomic);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_vcpu_read_guest_atomic);
 
 /* Copy @len bytes from @data into guest memory at '(@gfn * PAGE_SIZE) + @offset' */
 static int __kvm_write_guest_page(struct kvm *kvm,
@@ -3310,7 +3310,7 @@ int kvm_write_guest_page(struct kvm *kvm, gfn_t gfn,
 
 	return __kvm_write_guest_page(kvm, slot, gfn, data, offset, len);
 }
-EXPORT_SYMBOL_GPL(kvm_write_guest_page);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_write_guest_page);
 
 int kvm_vcpu_write_guest_page(struct kvm_vcpu *vcpu, gfn_t gfn,
 			      const void *data, int offset, int len)
@@ -3319,7 +3319,7 @@ int kvm_vcpu_write_guest_page(struct kvm_vcpu *vcpu, gfn_t gfn,
 
 	return __kvm_write_guest_page(vcpu->kvm, slot, gfn, data, offset, len);
 }
-EXPORT_SYMBOL_GPL(kvm_vcpu_write_guest_page);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_vcpu_write_guest_page);
 
 int kvm_write_guest(struct kvm *kvm, gpa_t gpa, const void *data,
 		    unsigned long len)
@@ -3340,7 +3340,7 @@ int kvm_write_guest(struct kvm *kvm, gpa_t gpa, const void *data,
 	}
 	return 0;
 }
-EXPORT_SYMBOL_GPL(kvm_write_guest);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_write_guest);
 
 int kvm_vcpu_write_guest(struct kvm_vcpu *vcpu, gpa_t gpa, const void *data,
 		         unsigned long len)
@@ -3361,7 +3361,7 @@ int kvm_vcpu_write_guest(struct kvm_vcpu *vcpu, gpa_t gpa, const void *data,
 	}
 	return 0;
 }
-EXPORT_SYMBOL_GPL(kvm_vcpu_write_guest);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_vcpu_write_guest);
 
 static int __kvm_gfn_to_hva_cache_init(struct kvm_memslots *slots,
 				       struct gfn_to_hva_cache *ghc,
@@ -3410,7 +3410,7 @@ int kvm_gfn_to_hva_cache_init(struct kvm *kvm, struct gfn_to_hva_cache *ghc,
 	struct kvm_memslots *slots = kvm_memslots(kvm);
 	return __kvm_gfn_to_hva_cache_init(slots, ghc, gpa, len);
 }
-EXPORT_SYMBOL_GPL(kvm_gfn_to_hva_cache_init);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_gfn_to_hva_cache_init);
 
 int kvm_write_guest_offset_cached(struct kvm *kvm, struct gfn_to_hva_cache *ghc,
 				  void *data, unsigned int offset,
@@ -3441,14 +3441,14 @@ int kvm_write_guest_offset_cached(struct kvm *kvm, struct gfn_to_hva_cache *ghc,
 
 	return 0;
 }
-EXPORT_SYMBOL_GPL(kvm_write_guest_offset_cached);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_write_guest_offset_cached);
 
 int kvm_write_guest_cached(struct kvm *kvm, struct gfn_to_hva_cache *ghc,
 			   void *data, unsigned long len)
 {
 	return kvm_write_guest_offset_cached(kvm, ghc, data, 0, len);
 }
-EXPORT_SYMBOL_GPL(kvm_write_guest_cached);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_write_guest_cached);
 
 int kvm_read_guest_offset_cached(struct kvm *kvm, struct gfn_to_hva_cache *ghc,
 				 void *data, unsigned int offset,
@@ -3478,14 +3478,14 @@ int kvm_read_guest_offset_cached(struct kvm *kvm, struct gfn_to_hva_cache *ghc,
 
 	return 0;
 }
-EXPORT_SYMBOL_GPL(kvm_read_guest_offset_cached);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_read_guest_offset_cached);
 
 int kvm_read_guest_cached(struct kvm *kvm, struct gfn_to_hva_cache *ghc,
 			  void *data, unsigned long len)
 {
 	return kvm_read_guest_offset_cached(kvm, ghc, data, 0, len);
 }
-EXPORT_SYMBOL_GPL(kvm_read_guest_cached);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_read_guest_cached);
 
 int kvm_clear_guest(struct kvm *kvm, gpa_t gpa, unsigned long len)
 {
@@ -3505,7 +3505,7 @@ int kvm_clear_guest(struct kvm *kvm, gpa_t gpa, unsigned long len)
 	}
 	return 0;
 }
-EXPORT_SYMBOL_GPL(kvm_clear_guest);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_clear_guest);
 
 void mark_page_dirty_in_slot(struct kvm *kvm,
 			     const struct kvm_memory_slot *memslot,
@@ -3530,7 +3530,7 @@ void mark_page_dirty_in_slot(struct kvm *kvm,
 			set_bit_le(rel_gfn, memslot->dirty_bitmap);
 	}
 }
-EXPORT_SYMBOL_GPL(mark_page_dirty_in_slot);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(mark_page_dirty_in_slot);
 
 void mark_page_dirty(struct kvm *kvm, gfn_t gfn)
 {
@@ -3539,7 +3539,7 @@ void mark_page_dirty(struct kvm *kvm, gfn_t gfn)
 	memslot = gfn_to_memslot(kvm, gfn);
 	mark_page_dirty_in_slot(kvm, memslot, gfn);
 }
-EXPORT_SYMBOL_GPL(mark_page_dirty);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(mark_page_dirty);
 
 void kvm_vcpu_mark_page_dirty(struct kvm_vcpu *vcpu, gfn_t gfn)
 {
@@ -3548,7 +3548,7 @@ void kvm_vcpu_mark_page_dirty(struct kvm_vcpu *vcpu, gfn_t gfn)
 	memslot = kvm_vcpu_gfn_to_memslot(vcpu, gfn);
 	mark_page_dirty_in_slot(vcpu->kvm, memslot, gfn);
 }
-EXPORT_SYMBOL_GPL(kvm_vcpu_mark_page_dirty);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_vcpu_mark_page_dirty);
 
 void kvm_sigset_activate(struct kvm_vcpu *vcpu)
 {
@@ -3785,7 +3785,7 @@ void kvm_vcpu_halt(struct kvm_vcpu *vcpu)
 
 	trace_kvm_vcpu_wakeup(halt_ns, waited, vcpu_valid_wakeup(vcpu));
 }
-EXPORT_SYMBOL_GPL(kvm_vcpu_halt);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_vcpu_halt);
 
 bool kvm_vcpu_wake_up(struct kvm_vcpu *vcpu)
 {
@@ -3797,7 +3797,7 @@ bool kvm_vcpu_wake_up(struct kvm_vcpu *vcpu)
 
 	return false;
 }
-EXPORT_SYMBOL_GPL(kvm_vcpu_wake_up);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_vcpu_wake_up);
 
 #ifndef CONFIG_S390
 /*
@@ -3849,7 +3849,7 @@ void __kvm_vcpu_kick(struct kvm_vcpu *vcpu, bool wait)
 out:
 	put_cpu();
 }
-EXPORT_SYMBOL_GPL(__kvm_vcpu_kick);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(__kvm_vcpu_kick);
 #endif /* !CONFIG_S390 */
 
 int kvm_vcpu_yield_to(struct kvm_vcpu *target)
@@ -3872,7 +3872,7 @@ int kvm_vcpu_yield_to(struct kvm_vcpu *target)
 
 	return ret;
 }
-EXPORT_SYMBOL_GPL(kvm_vcpu_yield_to);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_vcpu_yield_to);
 
 /*
  * Helper that checks whether a VCPU is eligible for directed yield.
@@ -4027,7 +4027,7 @@ void kvm_vcpu_on_spin(struct kvm_vcpu *me, bool yield_to_kernel_mode)
 	/* Ensure vcpu is not eligible during next spinloop */
 	kvm_vcpu_set_dy_eligible(me, false);
 }
-EXPORT_SYMBOL_GPL(kvm_vcpu_on_spin);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_vcpu_on_spin);
 
 static bool kvm_page_in_dirty_ring(struct kvm *kvm, unsigned long pgoff)
 {
@@ -5007,7 +5007,7 @@ bool kvm_are_all_memslots_empty(struct kvm *kvm)
 
 	return true;
 }
-EXPORT_SYMBOL_GPL(kvm_are_all_memslots_empty);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_are_all_memslots_empty);
 
 static int kvm_vm_ioctl_enable_cap_generic(struct kvm *kvm,
 					   struct kvm_enable_cap *cap)
@@ -5462,7 +5462,7 @@ bool file_is_kvm(struct file *file)
 {
 	return file && file->f_op == &kvm_vm_fops;
 }
-EXPORT_SYMBOL_GPL(file_is_kvm);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(file_is_kvm);
 
 static int kvm_dev_ioctl_create_vm(unsigned long type)
 {
@@ -5557,10 +5557,10 @@ static struct miscdevice kvm_dev = {
 #ifdef CONFIG_KVM_GENERIC_HARDWARE_ENABLING
 bool enable_virt_at_load = true;
 module_param(enable_virt_at_load, bool, 0444);
-EXPORT_SYMBOL_GPL(enable_virt_at_load);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(enable_virt_at_load);
 
 __visible bool kvm_rebooting;
-EXPORT_SYMBOL_GPL(kvm_rebooting);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_rebooting);
 
 static DEFINE_PER_CPU(bool, virtualization_enabled);
 static DEFINE_MUTEX(kvm_usage_lock);
@@ -5711,7 +5711,7 @@ int kvm_enable_virtualization(void)
 	--kvm_usage_count;
 	return r;
 }
-EXPORT_SYMBOL_GPL(kvm_enable_virtualization);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_enable_virtualization);
 
 void kvm_disable_virtualization(void)
 {
@@ -5724,7 +5724,7 @@ void kvm_disable_virtualization(void)
 	cpuhp_remove_state(CPUHP_AP_KVM_ONLINE);
 	kvm_arch_disable_virtualization();
 }
-EXPORT_SYMBOL_GPL(kvm_disable_virtualization);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_disable_virtualization);
 
 static int kvm_init_virtualization(void)
 {
@@ -5861,7 +5861,7 @@ int kvm_io_bus_write(struct kvm_vcpu *vcpu, enum kvm_bus bus_idx, gpa_t addr,
 	r = __kvm_io_bus_write(vcpu, bus, &range, val);
 	return r < 0 ? r : 0;
 }
-EXPORT_SYMBOL_GPL(kvm_io_bus_write);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_io_bus_write);
 
 int kvm_io_bus_write_cookie(struct kvm_vcpu *vcpu, enum kvm_bus bus_idx,
 			    gpa_t addr, int len, const void *val, long cookie)
@@ -5930,7 +5930,7 @@ int kvm_io_bus_read(struct kvm_vcpu *vcpu, enum kvm_bus bus_idx, gpa_t addr,
 	r = __kvm_io_bus_read(vcpu, bus, &range, val);
 	return r < 0 ? r : 0;
 }
-EXPORT_SYMBOL_GPL(kvm_io_bus_read);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_io_bus_read);
 
 int kvm_io_bus_register_dev(struct kvm *kvm, enum kvm_bus bus_idx, gpa_t addr,
 			    int len, struct kvm_io_device *dev)
@@ -6048,7 +6048,7 @@ struct kvm_io_device *kvm_io_bus_get_dev(struct kvm *kvm, enum kvm_bus bus_idx,
 
 	return iodev;
 }
-EXPORT_SYMBOL_GPL(kvm_io_bus_get_dev);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_io_bus_get_dev);
 
 static int kvm_debugfs_open(struct inode *inode, struct file *file,
 			   int (*get)(void *, u64 *), int (*set)(void *, u64),
@@ -6385,7 +6385,7 @@ struct kvm_vcpu *kvm_get_running_vcpu(void)
 
 	return vcpu;
 }
-EXPORT_SYMBOL_GPL(kvm_get_running_vcpu);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_get_running_vcpu);
 
 /**
  * kvm_get_running_vcpus - get the per-CPU array of currently running vcpus.
@@ -6520,7 +6520,7 @@ int kvm_init(unsigned vcpu_size, unsigned vcpu_align, struct module *module)
 	kmem_cache_destroy(kvm_vcpu_cache);
 	return r;
 }
-EXPORT_SYMBOL_GPL(kvm_init);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_init);
 
 void kvm_exit(void)
 {
@@ -6543,4 +6543,4 @@ void kvm_exit(void)
 	kvm_async_pf_deinit();
 	kvm_irqfd_exit();
 }
-EXPORT_SYMBOL_GPL(kvm_exit);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_exit);

---

## [4] Sean Christopherson — 2025-07-29
*Subject: [PATCH 3/6] KVM: x86: Move kvm_intr_is_single_vcpu() to lapic.c*

Move kvm_intr_is_single_vcpu() to lapic.c, drop its export, and make its
"fast" helper local to lapic.c.  kvm_intr_is_single_vcpu() is only usable
if the local APIC is in-kernel, i.e. it most definitely belongs in the
local APIC code.

No functional change intended.

Fixes: 2f5fb6b965b3 ("KVM: x86: Dedup AVIC vs. PI code for identifying target vCPU")
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/kvm_host.h |  3 ---
 arch/x86/kvm/irq.c              | 28 ----------------------------
 arch/x86/kvm/lapic.c            | 32 ++++++++++++++++++++++++++++++--
 arch/x86/kvm/lapic.h            |  4 ++--
 4 files changed, 32 insertions(+), 35 deletions(-)

diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h
index f19a76d3ca0e..99c07a37bf80 100644
--- a/arch/x86/include/asm/kvm_host.h
+++ b/arch/x86/include/asm/kvm_host.h
@@ -2392,9 +2392,6 @@ void __user *__x86_set_memory_region(struct kvm *kvm, int id, gpa_t gpa,
 bool kvm_vcpu_is_reset_bsp(struct kvm_vcpu *vcpu);
 bool kvm_vcpu_is_bsp(struct kvm_vcpu *vcpu);
 
-bool kvm_intr_is_single_vcpu(struct kvm *kvm, struct kvm_lapic_irq *irq,
-			     struct kvm_vcpu **dest_vcpu);
-
 static inline bool kvm_irq_is_postable(struct kvm_lapic_irq *irq)
 {
 	/* We can only post Fixed and LowPrio IRQs */
diff --git a/arch/x86/kvm/irq.c b/arch/x86/kvm/irq.c
index 16da89259011..a1a388c00187 100644
--- a/arch/x86/kvm/irq.c
+++ b/arch/x86/kvm/irq.c
@@ -411,34 +411,6 @@ int kvm_set_routing_entry(struct kvm *kvm,
 	return 0;
 }
 
-bool kvm_intr_is_single_vcpu(struct kvm *kvm, struct kvm_lapic_irq *irq,
-			     struct kvm_vcpu **dest_vcpu)
-{
-	int r = 0;
-	unsigned long i;
-	struct kvm_vcpu *vcpu;
-
-	if (kvm_intr_is_single_vcpu_fast(kvm, irq, dest_vcpu))
-		return true;
-
-	kvm_for_each_vcpu(i, vcpu, kvm) {
-		if (!kvm_apic_present(vcpu))
-			continue;
-
-		if (!kvm_apic_match_dest(vcpu, NULL, irq->shorthand,
-					irq->dest_id, irq->dest_mode))
-			continue;
-
-		if (++r == 2)
-			return false;
-
-		*dest_vcpu = vcpu;
-	}
-
-	return r == 1;
-}
-EXPORT_SYMBOL_GPL(kvm_intr_is_single_vcpu);
-
 void kvm_scan_ioapic_irq(struct kvm_vcpu *vcpu, u32 dest_id, u16 dest_mode,
 			 u8 vector, unsigned long *ioapic_handled_vectors)
 {
diff --git a/arch/x86/kvm/lapic.c b/arch/x86/kvm/lapic.c
index 8172c2042dd6..20f7a7d0c422 100644
--- a/arch/x86/kvm/lapic.c
+++ b/arch/x86/kvm/lapic.c
@@ -1228,8 +1228,9 @@ bool kvm_irq_delivery_to_apic_fast(struct kvm *kvm, struct kvm_lapic *src,
  *	   interrupt.
  * - Otherwise, use remapped mode to inject the interrupt.
  */
-bool kvm_intr_is_single_vcpu_fast(struct kvm *kvm, struct kvm_lapic_irq *irq,
-			struct kvm_vcpu **dest_vcpu)
+static bool kvm_intr_is_single_vcpu_fast(struct kvm *kvm,
+					 struct kvm_lapic_irq *irq,
+					 struct kvm_vcpu **dest_vcpu)
 {
 	struct kvm_apic_map *map;
 	unsigned long bitmap;
@@ -1256,6 +1257,33 @@ bool kvm_intr_is_single_vcpu_fast(struct kvm *kvm, struct kvm_lapic_irq *irq,
 	return ret;
 }
 
+bool kvm_intr_is_single_vcpu(struct kvm *kvm, struct kvm_lapic_irq *irq,
+			     struct kvm_vcpu **dest_vcpu)
+{
+	int r = 0;
+	unsigned long i;
+	struct kvm_vcpu *vcpu;
+
+	if (kvm_intr_is_single_vcpu_fast(kvm, irq, dest_vcpu))
+		return true;
+
+	kvm_for_each_vcpu(i, vcpu, kvm) {
+		if (!kvm_apic_present(vcpu))
+			continue;
+
+		if (!kvm_apic_match_dest(vcpu, NULL, irq->shorthand,
+					irq->dest_id, irq->dest_mode))
+			continue;
+
+		if (++r == 2)
+			return false;
+
+		*dest_vcpu = vcpu;
+	}
+
+	return r == 1;
+}
+
 /*
  * Add a pending IRQ into lapic.
  * Return 1 if successfully added and 0 if discarded.
diff --git a/arch/x86/kvm/lapic.h b/arch/x86/kvm/lapic.h
index 72de14527698..b9e44956c162 100644
--- a/arch/x86/kvm/lapic.h
+++ b/arch/x86/kvm/lapic.h
@@ -240,8 +240,8 @@ void kvm_wait_lapic_expire(struct kvm_vcpu *vcpu);
 void kvm_bitmap_or_dest_vcpus(struct kvm *kvm, struct kvm_lapic_irq *irq,
 			      unsigned long *vcpu_bitmap);
 
-bool kvm_intr_is_single_vcpu_fast(struct kvm *kvm, struct kvm_lapic_irq *irq,
-			struct kvm_vcpu **dest_vcpu);
+bool kvm_intr_is_single_vcpu(struct kvm *kvm, struct kvm_lapic_irq *irq,
+			     struct kvm_vcpu **dest_vcpu);
 int kvm_vector_to_index(u32 vector, u32 dest_vcpus,
 			const unsigned long *bitmap, u32 bitmap_size);
 void kvm_lapic_switch_to_sw_timer(struct kvm_vcpu *vcpu);

---

## [5] Sean Christopherson — 2025-07-29
*Subject: [PATCH 4/6] KVM: x86: Drop pointless exports of kvm_arch_xxx() hooks*

Drop the exporting of several kvm_arch_xxx() hooks that are only called
from arch-neutral code, i.e. that are only called from kvm.ko.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/x86.c | 3 ---
 1 file changed, 3 deletions(-)

diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index a1c49bc681c4..14c0e03b48ae 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -13492,14 +13492,12 @@ void kvm_arch_register_noncoherent_dma(struct kvm *kvm)
 	if (atomic_inc_return(&kvm->arch.noncoherent_dma_count) == 1)
 		kvm_noncoherent_dma_assignment_start_or_stop(kvm);
 }
-EXPORT_SYMBOL_GPL(kvm_arch_register_noncoherent_dma);
 
 void kvm_arch_unregister_noncoherent_dma(struct kvm *kvm)
 {
 	if (!atomic_dec_return(&kvm->arch.noncoherent_dma_count))
 		kvm_noncoherent_dma_assignment_start_or_stop(kvm);
 }
-EXPORT_SYMBOL_GPL(kvm_arch_unregister_noncoherent_dma);
 
 bool kvm_arch_has_noncoherent_dma(struct kvm *kvm)
 {
@@ -13516,7 +13514,6 @@ bool kvm_arch_no_poll(struct kvm_vcpu *vcpu)
 {
 	return (vcpu->arch.msr_kvm_poll_control & 1) == 0;
 }
-EXPORT_SYMBOL_GPL(kvm_arch_no_poll);
 
 #ifdef CONFIG_HAVE_KVM_ARCH_GMEM_PREPARE
 int kvm_arch_gmem_prepare(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn, int max_order)

---

## [6] Sean Christopherson — 2025-07-29
*Subject: [PATCH 5/6] KVM: x86: Export KVM-internal symbols for sub-modules only*

Rework almost all of KVM x86's exports to expose symbols only to KVM's
vendor modules, i.e. to kvm-{amd,intel}.ko.  Keep the generic exports that
are guarded by CONFIG_KVM_EXTERNAL_WRITE_TRACKING=y, as they're explicitly
designed/intended for external usage.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/cpuid.c        |  10 +-
 arch/x86/kvm/hyperv.c       |   4 +-
 arch/x86/kvm/irq.c          |   6 +-
 arch/x86/kvm/kvm_onhyperv.c |   6 +-
 arch/x86/kvm/lapic.c        |  38 +++----
 arch/x86/kvm/mmu/mmu.c      |  36 +++----
 arch/x86/kvm/mmu/spte.c     |  10 +-
 arch/x86/kvm/mmu/tdp_mmu.c  |   2 +-
 arch/x86/kvm/pmu.c          |   8 +-
 arch/x86/kvm/smm.c          |   2 +-
 arch/x86/kvm/x86.c          | 208 ++++++++++++++++++------------------
 11 files changed, 165 insertions(+), 165 deletions(-)

diff --git a/arch/x86/kvm/cpuid.c b/arch/x86/kvm/cpuid.c
index e2836a255b16..1ff431915d2b 100644
--- a/arch/x86/kvm/cpuid.c
+++ b/arch/x86/kvm/cpuid.c
@@ -34,7 +34,7 @@
  * aligned to sizeof(unsigned long) because it's not accessed via bitops.
  */
 u32 kvm_cpu_caps[NR_KVM_CPU_CAPS] __read_mostly;
-EXPORT_SYMBOL_GPL(kvm_cpu_caps);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_cpu_caps);
 
 struct cpuid_xstate_sizes {
 	u32 eax;
@@ -131,7 +131,7 @@ struct kvm_cpuid_entry2 *kvm_find_cpuid_entry2(
 
 	return NULL;
 }
-EXPORT_SYMBOL_GPL(kvm_find_cpuid_entry2);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_find_cpuid_entry2);
 
 static int kvm_check_cpuid(struct kvm_vcpu *vcpu)
 {
@@ -1222,7 +1222,7 @@ void kvm_set_cpu_caps(void)
 		kvm_cpu_cap_clear(X86_FEATURE_RDPID);
 	}
 }
-EXPORT_SYMBOL_GPL(kvm_set_cpu_caps);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_set_cpu_caps);
 
 #undef F
 #undef SCATTERED_F
@@ -2045,7 +2045,7 @@ bool kvm_cpuid(struct kvm_vcpu *vcpu, u32 *eax, u32 *ebx,
 			used_max_basic);
 	return exact;
 }
-EXPORT_SYMBOL_GPL(kvm_cpuid);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_cpuid);
 
 int kvm_emulate_cpuid(struct kvm_vcpu *vcpu)
 {
@@ -2063,4 +2063,4 @@ int kvm_emulate_cpuid(struct kvm_vcpu *vcpu)
 	kvm_rdx_write(vcpu, edx);
 	return kvm_skip_emulated_instruction(vcpu);
 }
-EXPORT_SYMBOL_GPL(kvm_emulate_cpuid);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_emulate_cpuid);
diff --git a/arch/x86/kvm/hyperv.c b/arch/x86/kvm/hyperv.c
index 72b19a88a776..a0b9096d5b14 100644
--- a/arch/x86/kvm/hyperv.c
+++ b/arch/x86/kvm/hyperv.c
@@ -923,7 +923,7 @@ bool kvm_hv_assist_page_enabled(struct kvm_vcpu *vcpu)
 		return false;
 	return vcpu->arch.pv_eoi.msr_val & KVM_MSR_ENABLED;
 }
-EXPORT_SYMBOL_GPL(kvm_hv_assist_page_enabled);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_hv_assist_page_enabled);
 
 int kvm_hv_get_assist_page(struct kvm_vcpu *vcpu)
 {
@@ -935,7 +935,7 @@ int kvm_hv_get_assist_page(struct kvm_vcpu *vcpu)
 	return kvm_read_guest_cached(vcpu->kvm, &vcpu->arch.pv_eoi.data,
 				     &hv_vcpu->vp_assist_page, sizeof(struct hv_vp_assist_page));
 }
-EXPORT_SYMBOL_GPL(kvm_hv_get_assist_page);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_hv_get_assist_page);
 
 static void stimer_prepare_msg(struct kvm_vcpu_hv_stimer *stimer)
 {
diff --git a/arch/x86/kvm/irq.c b/arch/x86/kvm/irq.c
index a1a388c00187..67a07dce96cf 100644
--- a/arch/x86/kvm/irq.c
+++ b/arch/x86/kvm/irq.c
@@ -103,7 +103,7 @@ int kvm_cpu_has_injectable_intr(struct kvm_vcpu *v)
 
 	return kvm_apic_has_interrupt(v) != -1; /* LAPIC */
 }
-EXPORT_SYMBOL_GPL(kvm_cpu_has_injectable_intr);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_cpu_has_injectable_intr);
 
 /*
  * check if there is pending interrupt without
@@ -119,7 +119,7 @@ int kvm_cpu_has_interrupt(struct kvm_vcpu *v)
 
 	return kvm_apic_has_interrupt(v) != -1;	/* LAPIC */
 }
-EXPORT_SYMBOL_GPL(kvm_cpu_has_interrupt);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_cpu_has_interrupt);
 
 /*
  * Read pending interrupt(from non-APIC source)
@@ -148,7 +148,7 @@ int kvm_cpu_get_extint(struct kvm_vcpu *v)
 	WARN_ON_ONCE(!irqchip_split(v->kvm));
 	return get_userspace_extint(v);
 }
-EXPORT_SYMBOL_GPL(kvm_cpu_get_extint);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_cpu_get_extint);
 
 /*
  * Read pending interrupt vector and intack.
diff --git a/arch/x86/kvm/kvm_onhyperv.c b/arch/x86/kvm/kvm_onhyperv.c
index ded0bd688c65..34c7e7342e30 100644
--- a/arch/x86/kvm/kvm_onhyperv.c
+++ b/arch/x86/kvm/kvm_onhyperv.c
@@ -101,13 +101,13 @@ int hv_flush_remote_tlbs_range(struct kvm *kvm, gfn_t start_gfn, gfn_t nr_pages)
 
 	return __hv_flush_remote_tlbs_range(kvm, &range);
 }
-EXPORT_SYMBOL_GPL(hv_flush_remote_tlbs_range);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(hv_flush_remote_tlbs_range);
 
 int hv_flush_remote_tlbs(struct kvm *kvm)
 {
 	return __hv_flush_remote_tlbs_range(kvm, NULL);
 }
-EXPORT_SYMBOL_GPL(hv_flush_remote_tlbs);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(hv_flush_remote_tlbs);
 
 void hv_track_root_tdp(struct kvm_vcpu *vcpu, hpa_t root_tdp)
 {
@@ -121,4 +121,4 @@ void hv_track_root_tdp(struct kvm_vcpu *vcpu, hpa_t root_tdp)
 		spin_unlock(&kvm_arch->hv_root_tdp_lock);
 	}
 }
-EXPORT_SYMBOL_GPL(hv_track_root_tdp);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(hv_track_root_tdp);
diff --git a/arch/x86/kvm/lapic.c b/arch/x86/kvm/lapic.c
index 20f7a7d0c422..185473dcf898 100644
--- a/arch/x86/kvm/lapic.c
+++ b/arch/x86/kvm/lapic.c
@@ -102,7 +102,7 @@ bool kvm_apic_pending_eoi(struct kvm_vcpu *vcpu, int vector)
 }
 
 __read_mostly DEFINE_STATIC_KEY_FALSE(kvm_has_noapic_vcpu);
-EXPORT_SYMBOL_GPL(kvm_has_noapic_vcpu);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_has_noapic_vcpu);
 
 __read_mostly DEFINE_STATIC_KEY_DEFERRED_FALSE(apic_hw_disabled, HZ);
 __read_mostly DEFINE_STATIC_KEY_DEFERRED_FALSE(apic_sw_disabled, HZ);
@@ -642,7 +642,7 @@ bool __kvm_apic_update_irr(unsigned long *pir, void *regs, int *max_irr)
 	return ((max_updated_irr != -1) &&
 		(max_updated_irr == *max_irr));
 }
-EXPORT_SYMBOL_GPL(__kvm_apic_update_irr);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(__kvm_apic_update_irr);
 
 bool kvm_apic_update_irr(struct kvm_vcpu *vcpu, unsigned long *pir, int *max_irr)
 {
@@ -653,7 +653,7 @@ bool kvm_apic_update_irr(struct kvm_vcpu *vcpu, unsigned long *pir, int *max_irr
 		apic->irr_pending = true;
 	return irr_updated;
 }
-EXPORT_SYMBOL_GPL(kvm_apic_update_irr);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_apic_update_irr);
 
 static inline int apic_search_irr(struct kvm_lapic *apic)
 {
@@ -693,7 +693,7 @@ void kvm_apic_clear_irr(struct kvm_vcpu *vcpu, int vec)
 {
 	apic_clear_irr(vec, vcpu->arch.apic);
 }
-EXPORT_SYMBOL_GPL(kvm_apic_clear_irr);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_apic_clear_irr);
 
 static void *apic_vector_to_isr(int vec, struct kvm_lapic *apic)
 {
@@ -775,7 +775,7 @@ void kvm_apic_update_hwapic_isr(struct kvm_vcpu *vcpu)
 
 	kvm_x86_call(hwapic_isr_update)(vcpu, apic_find_highest_isr(apic));
 }
-EXPORT_SYMBOL_GPL(kvm_apic_update_hwapic_isr);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_apic_update_hwapic_isr);
 
 int kvm_lapic_find_highest_irr(struct kvm_vcpu *vcpu)
 {
@@ -786,7 +786,7 @@ int kvm_lapic_find_highest_irr(struct kvm_vcpu *vcpu)
 	 */
 	return apic_find_highest_irr(vcpu->arch.apic);
 }
-EXPORT_SYMBOL_GPL(kvm_lapic_find_highest_irr);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_lapic_find_highest_irr);
 
 static int __apic_accept_irq(struct kvm_lapic *apic, int delivery_mode,
 			     int vector, int level, int trig_mode,
@@ -948,7 +948,7 @@ void kvm_apic_update_ppr(struct kvm_vcpu *vcpu)
 {
 	apic_update_ppr(vcpu->arch.apic);
 }
-EXPORT_SYMBOL_GPL(kvm_apic_update_ppr);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_apic_update_ppr);
 
 static void apic_set_tpr(struct kvm_lapic *apic, u32 tpr)
 {
@@ -1059,7 +1059,7 @@ bool kvm_apic_match_dest(struct kvm_vcpu *vcpu, struct kvm_lapic *source,
 		return false;
 	}
 }
-EXPORT_SYMBOL_GPL(kvm_apic_match_dest);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_apic_match_dest);
 
 int kvm_vector_to_index(u32 vector, u32 dest_vcpus,
 		       const unsigned long *bitmap, u32 bitmap_size)
@@ -1507,7 +1507,7 @@ void kvm_apic_set_eoi_accelerated(struct kvm_vcpu *vcpu, int vector)
 	kvm_ioapic_send_eoi(apic, vector);
 	kvm_make_request(KVM_REQ_EVENT, apic->vcpu);
 }
-EXPORT_SYMBOL_GPL(kvm_apic_set_eoi_accelerated);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_apic_set_eoi_accelerated);
 
 void kvm_apic_send_ipi(struct kvm_lapic *apic, u32 icr_low, u32 icr_high)
 {
@@ -1532,7 +1532,7 @@ void kvm_apic_send_ipi(struct kvm_lapic *apic, u32 icr_low, u32 icr_high)
 
 	kvm_irq_delivery_to_apic(apic->vcpu->kvm, apic, &irq, NULL);
 }
-EXPORT_SYMBOL_GPL(kvm_apic_send_ipi);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_apic_send_ipi);
 
 static u32 apic_get_tmcct(struct kvm_lapic *apic)
 {
@@ -1649,7 +1649,7 @@ u64 kvm_lapic_readable_reg_mask(struct kvm_lapic *apic)
 
 	return valid_reg_mask;
 }
-EXPORT_SYMBOL_GPL(kvm_lapic_readable_reg_mask);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_lapic_readable_reg_mask);
 
 static int kvm_lapic_reg_read(struct kvm_lapic *apic, u32 offset, int len,
 			      void *data)
@@ -1890,7 +1890,7 @@ void kvm_wait_lapic_expire(struct kvm_vcpu *vcpu)
 	    lapic_timer_int_injected(vcpu))
 		__kvm_wait_lapic_expire(vcpu);
 }
-EXPORT_SYMBOL_GPL(kvm_wait_lapic_expire);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_wait_lapic_expire);
 
 static void kvm_apic_inject_pending_timer_irqs(struct kvm_lapic *apic)
 {
@@ -2204,7 +2204,7 @@ void kvm_lapic_expired_hv_timer(struct kvm_vcpu *vcpu)
 out:
 	preempt_enable();
 }
-EXPORT_SYMBOL_GPL(kvm_lapic_expired_hv_timer);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_lapic_expired_hv_timer);
 
 void kvm_lapic_switch_to_hv_timer(struct kvm_vcpu *vcpu)
 {
@@ -2457,7 +2457,7 @@ void kvm_lapic_set_eoi(struct kvm_vcpu *vcpu)
 {
 	kvm_lapic_reg_write(vcpu->arch.apic, APIC_EOI, 0);
 }
-EXPORT_SYMBOL_GPL(kvm_lapic_set_eoi);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_lapic_set_eoi);
 
 #define X2APIC_ICR_RESERVED_BITS (GENMASK_ULL(31, 20) | GENMASK_ULL(17, 16) | BIT(13))
 
@@ -2517,7 +2517,7 @@ void kvm_apic_write_nodecode(struct kvm_vcpu *vcpu, u32 offset)
 	else
 		kvm_lapic_reg_write(apic, offset, kvm_lapic_get_reg(apic, offset));
 }
-EXPORT_SYMBOL_GPL(kvm_apic_write_nodecode);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_apic_write_nodecode);
 
 void kvm_free_lapic(struct kvm_vcpu *vcpu)
 {
@@ -2655,7 +2655,7 @@ int kvm_apic_set_base(struct kvm_vcpu *vcpu, u64 value, bool host_initiated)
 	kvm_recalculate_apic_map(vcpu->kvm);
 	return 0;
 }
-EXPORT_SYMBOL_GPL(kvm_apic_set_base);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_apic_set_base);
 
 void kvm_apic_update_apicv(struct kvm_vcpu *vcpu)
 {
@@ -2706,7 +2706,7 @@ int kvm_alloc_apic_access_page(struct kvm *kvm)
 	mutex_unlock(&kvm->slots_lock);
 	return ret;
 }
-EXPORT_SYMBOL_GPL(kvm_alloc_apic_access_page);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_alloc_apic_access_page);
 
 void kvm_inhibit_apic_access_page(struct kvm_vcpu *vcpu)
 {
@@ -2970,7 +2970,7 @@ int kvm_apic_has_interrupt(struct kvm_vcpu *vcpu)
 	__apic_update_ppr(apic, &ppr);
 	return apic_has_interrupt_for_ppr(apic, ppr);
 }
-EXPORT_SYMBOL_GPL(kvm_apic_has_interrupt);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_apic_has_interrupt);
 
 int kvm_apic_accept_pic_intr(struct kvm_vcpu *vcpu)
 {
@@ -3029,7 +3029,7 @@ void kvm_apic_ack_interrupt(struct kvm_vcpu *vcpu, int vector)
 	}
 
 }
-EXPORT_SYMBOL_GPL(kvm_apic_ack_interrupt);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_apic_ack_interrupt);
 
 static int kvm_apic_state_fixup(struct kvm_vcpu *vcpu,
 		struct kvm_lapic_state *s, bool set)
diff --git a/arch/x86/kvm/mmu/mmu.c b/arch/x86/kvm/mmu/mmu.c
index 6e838cb6c9e1..b3b8786969f4 100644
--- a/arch/x86/kvm/mmu/mmu.c
+++ b/arch/x86/kvm/mmu/mmu.c
@@ -110,7 +110,7 @@ static bool __ro_after_init tdp_mmu_allowed;
 #ifdef CONFIG_X86_64
 bool __read_mostly tdp_mmu_enabled = true;
 module_param_named(tdp_mmu, tdp_mmu_enabled, bool, 0444);
-EXPORT_SYMBOL_GPL(tdp_mmu_enabled);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(tdp_mmu_enabled);
 #endif
 
 static int max_huge_page_level __read_mostly;
@@ -3810,7 +3810,7 @@ void kvm_mmu_free_roots(struct kvm *kvm, struct kvm_mmu *mmu,
 		write_unlock(&kvm->mmu_lock);
 	}
 }
-EXPORT_SYMBOL_GPL(kvm_mmu_free_roots);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_mmu_free_roots);
 
 void kvm_mmu_free_guest_mode_roots(struct kvm *kvm, struct kvm_mmu *mmu)
 {
@@ -3837,7 +3837,7 @@ void kvm_mmu_free_guest_mode_roots(struct kvm *kvm, struct kvm_mmu *mmu)
 
 	kvm_mmu_free_roots(kvm, mmu, roots_to_free);
 }
-EXPORT_SYMBOL_GPL(kvm_mmu_free_guest_mode_roots);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_mmu_free_guest_mode_roots);
 
 static hpa_t mmu_alloc_root(struct kvm_vcpu *vcpu, gfn_t gfn, int quadrant,
 			    u8 level)
@@ -4852,7 +4852,7 @@ int kvm_handle_page_fault(struct kvm_vcpu *vcpu, u64 error_code,
 
 	return r;
 }
-EXPORT_SYMBOL_GPL(kvm_handle_page_fault);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_handle_page_fault);
 
 #ifdef CONFIG_X86_64
 static int kvm_tdp_mmu_page_fault(struct kvm_vcpu *vcpu,
@@ -4942,7 +4942,7 @@ int kvm_tdp_map_page(struct kvm_vcpu *vcpu, gpa_t gpa, u64 error_code, u8 *level
 		return -EIO;
 	}
 }
-EXPORT_SYMBOL_GPL(kvm_tdp_map_page);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_tdp_map_page);
 
 long kvm_arch_vcpu_pre_fault_memory(struct kvm_vcpu *vcpu,
 				    struct kvm_pre_fault_memory *range)
@@ -5138,7 +5138,7 @@ void kvm_mmu_new_pgd(struct kvm_vcpu *vcpu, gpa_t new_pgd)
 			__clear_sp_write_flooding_count(sp);
 	}
 }
-EXPORT_SYMBOL_GPL(kvm_mmu_new_pgd);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_mmu_new_pgd);
 
 static bool sync_mmio_spte(struct kvm_vcpu *vcpu, u64 *sptep, gfn_t gfn,
 			   unsigned int access)
@@ -5784,7 +5784,7 @@ void kvm_init_shadow_npt_mmu(struct kvm_vcpu *vcpu, unsigned long cr0,
 	shadow_mmu_init_context(vcpu, context, cpu_role, root_role);
 	kvm_mmu_new_pgd(vcpu, nested_cr3);
 }
-EXPORT_SYMBOL_GPL(kvm_init_shadow_npt_mmu);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_init_shadow_npt_mmu);
 
 static union kvm_cpu_role
 kvm_calc_shadow_ept_root_page_role(struct kvm_vcpu *vcpu, bool accessed_dirty,
@@ -5838,7 +5838,7 @@ void kvm_init_shadow_ept_mmu(struct kvm_vcpu *vcpu, bool execonly,
 
 	kvm_mmu_new_pgd(vcpu, new_eptp);
 }
-EXPORT_SYMBOL_GPL(kvm_init_shadow_ept_mmu);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_init_shadow_ept_mmu);
 
 static void init_kvm_softmmu(struct kvm_vcpu *vcpu,
 			     union kvm_cpu_role cpu_role)
@@ -5903,7 +5903,7 @@ void kvm_init_mmu(struct kvm_vcpu *vcpu)
 	else
 		init_kvm_softmmu(vcpu, cpu_role);
 }
-EXPORT_SYMBOL_GPL(kvm_init_mmu);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_init_mmu);
 
 void kvm_mmu_after_set_cpuid(struct kvm_vcpu *vcpu)
 {
@@ -5939,7 +5939,7 @@ void kvm_mmu_reset_context(struct kvm_vcpu *vcpu)
 	kvm_mmu_unload(vcpu);
 	kvm_init_mmu(vcpu);
 }
-EXPORT_SYMBOL_GPL(kvm_mmu_reset_context);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_mmu_reset_context);
 
 int kvm_mmu_load(struct kvm_vcpu *vcpu)
 {
@@ -5973,7 +5973,7 @@ int kvm_mmu_load(struct kvm_vcpu *vcpu)
 out:
 	return r;
 }
-EXPORT_SYMBOL_GPL(kvm_mmu_load);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_mmu_load);
 
 void kvm_mmu_unload(struct kvm_vcpu *vcpu)
 {
@@ -6035,7 +6035,7 @@ void kvm_mmu_free_obsolete_roots(struct kvm_vcpu *vcpu)
 	__kvm_mmu_free_obsolete_roots(vcpu->kvm, &vcpu->arch.root_mmu);
 	__kvm_mmu_free_obsolete_roots(vcpu->kvm, &vcpu->arch.guest_mmu);
 }
-EXPORT_SYMBOL_GPL(kvm_mmu_free_obsolete_roots);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_mmu_free_obsolete_roots);
 
 static u64 mmu_pte_write_fetch_gpte(struct kvm_vcpu *vcpu, gpa_t *gpa,
 				    int *bytes)
@@ -6361,7 +6361,7 @@ int noinline kvm_mmu_page_fault(struct kvm_vcpu *vcpu, gpa_t cr2_or_gpa, u64 err
 	return x86_emulate_instruction(vcpu, cr2_or_gpa, emulation_type, insn,
 				       insn_len);
 }
-EXPORT_SYMBOL_GPL(kvm_mmu_page_fault);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_mmu_page_fault);
 
 void kvm_mmu_print_sptes(struct kvm_vcpu *vcpu, gpa_t gpa, const char *msg)
 {
@@ -6377,7 +6377,7 @@ void kvm_mmu_print_sptes(struct kvm_vcpu *vcpu, gpa_t gpa, const char *msg)
 		pr_cont(", spte[%d] = 0x%llx", level, sptes[level]);
 	pr_cont("\n");
 }
-EXPORT_SYMBOL_GPL(kvm_mmu_print_sptes);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_mmu_print_sptes);
 
 static void __kvm_mmu_invalidate_addr(struct kvm_vcpu *vcpu, struct kvm_mmu *mmu,
 				      u64 addr, hpa_t root_hpa)
@@ -6443,7 +6443,7 @@ void kvm_mmu_invalidate_addr(struct kvm_vcpu *vcpu, struct kvm_mmu *mmu,
 			__kvm_mmu_invalidate_addr(vcpu, mmu, addr, mmu->prev_roots[i].hpa);
 	}
 }
-EXPORT_SYMBOL_GPL(kvm_mmu_invalidate_addr);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_mmu_invalidate_addr);
 
 void kvm_mmu_invlpg(struct kvm_vcpu *vcpu, gva_t gva)
 {
@@ -6460,7 +6460,7 @@ void kvm_mmu_invlpg(struct kvm_vcpu *vcpu, gva_t gva)
 	kvm_mmu_invalidate_addr(vcpu, vcpu->arch.walk_mmu, gva, KVM_MMU_ROOTS_ALL);
 	++vcpu->stat.invlpg;
 }
-EXPORT_SYMBOL_GPL(kvm_mmu_invlpg);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_mmu_invlpg);
 
 
 void kvm_mmu_invpcid_gva(struct kvm_vcpu *vcpu, gva_t gva, unsigned long pcid)
@@ -6513,7 +6513,7 @@ void kvm_configure_mmu(bool enable_tdp, int tdp_forced_root_level,
 	else
 		max_huge_page_level = PG_LEVEL_2M;
 }
-EXPORT_SYMBOL_GPL(kvm_configure_mmu);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_configure_mmu);
 
 static void free_mmu_pages(struct kvm_mmu *mmu)
 {
@@ -7179,7 +7179,7 @@ static bool kvm_mmu_zap_collapsible_spte(struct kvm *kvm,
 
 	return need_tlb_flush;
 }
-EXPORT_SYMBOL_GPL(kvm_zap_gfn_range);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_zap_gfn_range);
 
 static void kvm_rmap_zap_collapsible_sptes(struct kvm *kvm,
 					   const struct kvm_memory_slot *slot)
diff --git a/arch/x86/kvm/mmu/spte.c b/arch/x86/kvm/mmu/spte.c
index df31039b5d63..4b4dc3e40f6a 100644
--- a/arch/x86/kvm/mmu/spte.c
+++ b/arch/x86/kvm/mmu/spte.c
@@ -22,7 +22,7 @@
 bool __read_mostly enable_mmio_caching = true;
 static bool __ro_after_init allow_mmio_caching;
 module_param_named(mmio_caching, enable_mmio_caching, bool, 0444);
-EXPORT_SYMBOL_GPL(enable_mmio_caching);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(enable_mmio_caching);
 
 bool __read_mostly kvm_ad_enabled;
 
@@ -470,13 +470,13 @@ void kvm_mmu_set_mmio_spte_mask(u64 mmio_value, u64 mmio_mask, u64 access_mask)
 	shadow_mmio_mask  = mmio_mask;
 	shadow_mmio_access_mask = access_mask;
 }
-EXPORT_SYMBOL_GPL(kvm_mmu_set_mmio_spte_mask);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_mmu_set_mmio_spte_mask);
 
 void kvm_mmu_set_mmio_spte_value(struct kvm *kvm, u64 mmio_value)
 {
 	kvm->arch.shadow_mmio_value = mmio_value;
 }
-EXPORT_SYMBOL_GPL(kvm_mmu_set_mmio_spte_value);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_mmu_set_mmio_spte_value);
 
 void kvm_mmu_set_me_spte_mask(u64 me_value, u64 me_mask)
 {
@@ -487,7 +487,7 @@ void kvm_mmu_set_me_spte_mask(u64 me_value, u64 me_mask)
 	shadow_me_value = me_value;
 	shadow_me_mask = me_mask;
 }
-EXPORT_SYMBOL_GPL(kvm_mmu_set_me_spte_mask);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_mmu_set_me_spte_mask);
 
 void kvm_mmu_set_ept_masks(bool has_ad_bits, bool has_exec_only)
 {
@@ -513,7 +513,7 @@ void kvm_mmu_set_ept_masks(bool has_ad_bits, bool has_exec_only)
 	kvm_mmu_set_mmio_spte_mask(VMX_EPT_MISCONFIG_WX_VALUE,
 				   VMX_EPT_RWX_MASK | VMX_EPT_SUPPRESS_VE_BIT, 0);
 }
-EXPORT_SYMBOL_GPL(kvm_mmu_set_ept_masks);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_mmu_set_ept_masks);
 
 void kvm_mmu_reset_all_pte_masks(void)
 {
diff --git a/arch/x86/kvm/mmu/tdp_mmu.c b/arch/x86/kvm/mmu/tdp_mmu.c
index 7f3d7229b2c1..353f0e84a8ef 100644
--- a/arch/x86/kvm/mmu/tdp_mmu.c
+++ b/arch/x86/kvm/mmu/tdp_mmu.c
@@ -1953,7 +1953,7 @@ bool kvm_tdp_mmu_gpa_is_mapped(struct kvm_vcpu *vcpu, u64 gpa)
 	spte = sptes[leaf];
 	return is_shadow_present_pte(spte) && is_last_spte(spte, leaf);
 }
-EXPORT_SYMBOL_GPL(kvm_tdp_mmu_gpa_is_mapped);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_tdp_mmu_gpa_is_mapped);
 
 /*
  * Returns the last level spte pointer of the shadow page walk for the given
diff --git a/arch/x86/kvm/pmu.c b/arch/x86/kvm/pmu.c
index 75e9cfc689f8..0a2267958c4f 100644
--- a/arch/x86/kvm/pmu.c
+++ b/arch/x86/kvm/pmu.c
@@ -27,10 +27,10 @@
 #define KVM_PMU_EVENT_FILTER_MAX_EVENTS 300
 
 struct x86_pmu_capability __read_mostly kvm_pmu_cap;
-EXPORT_SYMBOL_GPL(kvm_pmu_cap);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_pmu_cap);
 
 struct kvm_pmu_emulated_event_selectors __read_mostly kvm_pmu_eventsel;
-EXPORT_SYMBOL_GPL(kvm_pmu_eventsel);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_pmu_eventsel);
 
 /* Precise Distribution of Instructions Retired (PDIR) */
 static const struct x86_cpu_id vmx_pebs_pdir_cpu[] = {
@@ -318,7 +318,7 @@ void pmc_write_counter(struct kvm_pmc *pmc, u64 val)
 	pmc->counter &= pmc_bitmask(pmc);
 	pmc_update_sample_period(pmc);
 }
-EXPORT_SYMBOL_GPL(pmc_write_counter);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(pmc_write_counter);
 
 static int filter_cmp(const void *pa, const void *pb, u64 mask)
 {
@@ -897,7 +897,7 @@ void kvm_pmu_trigger_event(struct kvm_vcpu *vcpu, u64 eventsel)
 		kvm_pmu_incr_counter(pmc);
 	}
 }
-EXPORT_SYMBOL_GPL(kvm_pmu_trigger_event);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_pmu_trigger_event);
 
 static bool is_masked_filter_valid(const struct kvm_x86_pmu_event_filter *filter)
 {
diff --git a/arch/x86/kvm/smm.c b/arch/x86/kvm/smm.c
index 9864c057187d..9058c5bacf93 100644
--- a/arch/x86/kvm/smm.c
+++ b/arch/x86/kvm/smm.c
@@ -131,7 +131,7 @@ void kvm_smm_changed(struct kvm_vcpu *vcpu, bool entering_smm)
 
 	kvm_mmu_reset_context(vcpu);
 }
-EXPORT_SYMBOL_GPL(kvm_smm_changed);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_smm_changed);
 
 void process_smi(struct kvm_vcpu *vcpu)
 {
diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index 14c0e03b48ae..3d9573cac39f 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -97,10 +97,10 @@
  * vendor module being reloaded with different module parameters.
  */
 struct kvm_caps kvm_caps __read_mostly;
-EXPORT_SYMBOL_GPL(kvm_caps);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_caps);
 
 struct kvm_host_values kvm_host __read_mostly;
-EXPORT_SYMBOL_GPL(kvm_host);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_host);
 
 #define  ERR_PTR_USR(e)  ((void __user *)ERR_PTR(e))
 
@@ -152,7 +152,7 @@ module_param(ignore_msrs, bool, 0644);
 
 bool __read_mostly report_ignored_msrs = true;
 module_param(report_ignored_msrs, bool, 0644);
-EXPORT_SYMBOL_GPL(report_ignored_msrs);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(report_ignored_msrs);
 
 unsigned int min_timer_period_us = 200;
 module_param(min_timer_period_us, uint, 0644);
@@ -169,7 +169,7 @@ module_param(vector_hashing, bool, 0444);
 
 bool __read_mostly enable_vmware_backdoor = false;
 module_param(enable_vmware_backdoor, bool, 0444);
-EXPORT_SYMBOL_GPL(enable_vmware_backdoor);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(enable_vmware_backdoor);
 
 /*
  * Flags to manipulate forced emulation behavior (any non-zero value will
@@ -184,7 +184,7 @@ module_param(pi_inject_timer, bint, 0644);
 
 /* Enable/disable PMU virtualization */
 bool __read_mostly enable_pmu = true;
-EXPORT_SYMBOL_GPL(enable_pmu);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(enable_pmu);
 module_param(enable_pmu, bool, 0444);
 
 bool __read_mostly eager_page_split = true;
@@ -211,7 +211,7 @@ struct kvm_user_return_msrs {
 };
 
 u32 __read_mostly kvm_nr_uret_msrs;
-EXPORT_SYMBOL_GPL(kvm_nr_uret_msrs);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_nr_uret_msrs);
 static u32 __read_mostly kvm_uret_msrs_list[KVM_MAX_NR_USER_RETURN_MSRS];
 static struct kvm_user_return_msrs __percpu *user_return_msrs;
 
@@ -221,16 +221,16 @@ static struct kvm_user_return_msrs __percpu *user_return_msrs;
 				| XFEATURE_MASK_PKRU | XFEATURE_MASK_XTILE)
 
 bool __read_mostly allow_smaller_maxphyaddr = 0;
-EXPORT_SYMBOL_GPL(allow_smaller_maxphyaddr);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(allow_smaller_maxphyaddr);
 
 bool __read_mostly enable_apicv = true;
-EXPORT_SYMBOL_GPL(enable_apicv);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(enable_apicv);
 
 bool __read_mostly enable_ipiv = true;
-EXPORT_SYMBOL_GPL(enable_ipiv);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(enable_ipiv);
 
 bool __read_mostly enable_device_posted_irqs = true;
-EXPORT_SYMBOL_GPL(enable_device_posted_irqs);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(enable_device_posted_irqs);
 
 const struct _kvm_stats_desc kvm_vm_stats_desc[] = {
 	KVM_GENERIC_VM_STATS(),
@@ -614,7 +614,7 @@ int kvm_add_user_return_msr(u32 msr)
 	kvm_uret_msrs_list[kvm_nr_uret_msrs] = msr;
 	return kvm_nr_uret_msrs++;
 }
-EXPORT_SYMBOL_GPL(kvm_add_user_return_msr);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_add_user_return_msr);
 
 int kvm_find_user_return_msr(u32 msr)
 {
@@ -626,7 +626,7 @@ int kvm_find_user_return_msr(u32 msr)
 	}
 	return -1;
 }
-EXPORT_SYMBOL_GPL(kvm_find_user_return_msr);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_find_user_return_msr);
 
 static void kvm_user_return_msr_cpu_online(void)
 {
@@ -666,7 +666,7 @@ int kvm_set_user_return_msr(unsigned slot, u64 value, u64 mask)
 	kvm_user_return_register_notifier(msrs);
 	return 0;
 }
-EXPORT_SYMBOL_GPL(kvm_set_user_return_msr);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_set_user_return_msr);
 
 void kvm_user_return_msr_update_cache(unsigned int slot, u64 value)
 {
@@ -675,7 +675,7 @@ void kvm_user_return_msr_update_cache(unsigned int slot, u64 value)
 	msrs->values[slot].curr = value;
 	kvm_user_return_register_notifier(msrs);
 }
-EXPORT_SYMBOL_GPL(kvm_user_return_msr_update_cache);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_user_return_msr_update_cache);
 
 static void drop_user_return_notifiers(void)
 {
@@ -697,7 +697,7 @@ noinstr void kvm_spurious_fault(void)
 	/* Fault while not rebooting.  We want the trace. */
 	BUG_ON(!kvm_rebooting);
 }
-EXPORT_SYMBOL_GPL(kvm_spurious_fault);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_spurious_fault);
 
 #define EXCPT_BENIGN		0
 #define EXCPT_CONTRIBUTORY	1
@@ -802,7 +802,7 @@ void kvm_deliver_exception_payload(struct kvm_vcpu *vcpu,
 	ex->has_payload = false;
 	ex->payload = 0;
 }
-EXPORT_SYMBOL_GPL(kvm_deliver_exception_payload);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_deliver_exception_payload);
 
 static void kvm_queue_exception_vmexit(struct kvm_vcpu *vcpu, unsigned int vector,
 				       bool has_error_code, u32 error_code,
@@ -886,7 +886,7 @@ void kvm_queue_exception(struct kvm_vcpu *vcpu, unsigned nr)
 {
 	kvm_multiple_exception(vcpu, nr, false, 0, false, 0);
 }
-EXPORT_SYMBOL_GPL(kvm_queue_exception);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_queue_exception);
 
 
 void kvm_queue_exception_p(struct kvm_vcpu *vcpu, unsigned nr,
@@ -894,7 +894,7 @@ void kvm_queue_exception_p(struct kvm_vcpu *vcpu, unsigned nr,
 {
 	kvm_multiple_exception(vcpu, nr, false, 0, true, payload);
 }
-EXPORT_SYMBOL_GPL(kvm_queue_exception_p);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_queue_exception_p);
 
 static void kvm_queue_exception_e_p(struct kvm_vcpu *vcpu, unsigned nr,
 				    u32 error_code, unsigned long payload)
@@ -929,7 +929,7 @@ void kvm_requeue_exception(struct kvm_vcpu *vcpu, unsigned int nr,
 	vcpu->arch.exception.has_payload = false;
 	vcpu->arch.exception.payload = 0;
 }
-EXPORT_SYMBOL_GPL(kvm_requeue_exception);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_requeue_exception);
 
 int kvm_complete_insn_gp(struct kvm_vcpu *vcpu, int err)
 {
@@ -940,7 +940,7 @@ int kvm_complete_insn_gp(struct kvm_vcpu *vcpu, int err)
 
 	return 1;
 }
-EXPORT_SYMBOL_GPL(kvm_complete_insn_gp);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_complete_insn_gp);
 
 static int complete_emulated_insn_gp(struct kvm_vcpu *vcpu, int err)
 {
@@ -990,7 +990,7 @@ void kvm_inject_emulated_page_fault(struct kvm_vcpu *vcpu,
 
 	fault_mmu->inject_page_fault(vcpu, fault);
 }
-EXPORT_SYMBOL_GPL(kvm_inject_emulated_page_fault);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_inject_emulated_page_fault);
 
 void kvm_inject_nmi(struct kvm_vcpu *vcpu)
 {
@@ -1002,7 +1002,7 @@ void kvm_queue_exception_e(struct kvm_vcpu *vcpu, unsigned nr, u32 error_code)
 {
 	kvm_multiple_exception(vcpu, nr, true, error_code, false, 0);
 }
-EXPORT_SYMBOL_GPL(kvm_queue_exception_e);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_queue_exception_e);
 
 /*
  * Checks if cpl <= required_cpl; if true, return true.  Otherwise queue
@@ -1024,7 +1024,7 @@ bool kvm_require_dr(struct kvm_vcpu *vcpu, int dr)
 	kvm_queue_exception(vcpu, UD_VECTOR);
 	return false;
 }
-EXPORT_SYMBOL_GPL(kvm_require_dr);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_require_dr);
 
 static inline u64 pdptr_rsvd_bits(struct kvm_vcpu *vcpu)
 {
@@ -1079,7 +1079,7 @@ int load_pdptrs(struct kvm_vcpu *vcpu, unsigned long cr3)
 
 	return 1;
 }
-EXPORT_SYMBOL_GPL(load_pdptrs);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(load_pdptrs);
 
 static bool kvm_is_valid_cr0(struct kvm_vcpu *vcpu, unsigned long cr0)
 {
@@ -1132,7 +1132,7 @@ void kvm_post_set_cr0(struct kvm_vcpu *vcpu, unsigned long old_cr0, unsigned lon
 	if ((cr0 ^ old_cr0) & KVM_MMU_CR0_ROLE_BITS)
 		kvm_mmu_reset_context(vcpu);
 }
-EXPORT_SYMBOL_GPL(kvm_post_set_cr0);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_post_set_cr0);
 
 int kvm_set_cr0(struct kvm_vcpu *vcpu, unsigned long cr0)
 {
@@ -1173,13 +1173,13 @@ int kvm_set_cr0(struct kvm_vcpu *vcpu, unsigned long cr0)
 
 	return 0;
 }
-EXPORT_SYMBOL_GPL(kvm_set_cr0);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_set_cr0);
 
 void kvm_lmsw(struct kvm_vcpu *vcpu, unsigned long msw)
 {
 	(void)kvm_set_cr0(vcpu, kvm_read_cr0_bits(vcpu, ~0x0eul) | (msw & 0x0f));
 }
-EXPORT_SYMBOL_GPL(kvm_lmsw);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_lmsw);
 
 void kvm_load_guest_xsave_state(struct kvm_vcpu *vcpu)
 {
@@ -1202,7 +1202,7 @@ void kvm_load_guest_xsave_state(struct kvm_vcpu *vcpu)
 	     kvm_is_cr4_bit_set(vcpu, X86_CR4_PKE)))
 		wrpkru(vcpu->arch.pkru);
 }
-EXPORT_SYMBOL_GPL(kvm_load_guest_xsave_state);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_load_guest_xsave_state);
 
 void kvm_load_host_xsave_state(struct kvm_vcpu *vcpu)
 {
@@ -1228,7 +1228,7 @@ void kvm_load_host_xsave_state(struct kvm_vcpu *vcpu)
 	}
 
 }
-EXPORT_SYMBOL_GPL(kvm_load_host_xsave_state);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_load_host_xsave_state);
 
 #ifdef CONFIG_X86_64
 static inline u64 kvm_guest_supported_xfd(struct kvm_vcpu *vcpu)
@@ -1293,7 +1293,7 @@ int kvm_emulate_xsetbv(struct kvm_vcpu *vcpu)
 
 	return kvm_skip_emulated_instruction(vcpu);
 }
-EXPORT_SYMBOL_GPL(kvm_emulate_xsetbv);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_emulate_xsetbv);
 
 static bool kvm_is_valid_cr4(struct kvm_vcpu *vcpu, unsigned long cr4)
 {
@@ -1341,7 +1341,7 @@ void kvm_post_set_cr4(struct kvm_vcpu *vcpu, unsigned long old_cr4, unsigned lon
 		kvm_make_request(KVM_REQ_TLB_FLUSH_CURRENT, vcpu);
 
 }
-EXPORT_SYMBOL_GPL(kvm_post_set_cr4);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_post_set_cr4);
 
 int kvm_set_cr4(struct kvm_vcpu *vcpu, unsigned long cr4)
 {
@@ -1372,7 +1372,7 @@ int kvm_set_cr4(struct kvm_vcpu *vcpu, unsigned long cr4)
 
 	return 0;
 }
-EXPORT_SYMBOL_GPL(kvm_set_cr4);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_set_cr4);
 
 static void kvm_invalidate_pcid(struct kvm_vcpu *vcpu, unsigned long pcid)
 {
@@ -1464,7 +1464,7 @@ int kvm_set_cr3(struct kvm_vcpu *vcpu, unsigned long cr3)
 
 	return 0;
 }
-EXPORT_SYMBOL_GPL(kvm_set_cr3);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_set_cr3);
 
 int kvm_set_cr8(struct kvm_vcpu *vcpu, unsigned long cr8)
 {
@@ -1476,7 +1476,7 @@ int kvm_set_cr8(struct kvm_vcpu *vcpu, unsigned long cr8)
 		vcpu->arch.cr8 = cr8;
 	return 0;
 }
-EXPORT_SYMBOL_GPL(kvm_set_cr8);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_set_cr8);
 
 unsigned long kvm_get_cr8(struct kvm_vcpu *vcpu)
 {
@@ -1485,7 +1485,7 @@ unsigned long kvm_get_cr8(struct kvm_vcpu *vcpu)
 	else
 		return vcpu->arch.cr8;
 }
-EXPORT_SYMBOL_GPL(kvm_get_cr8);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_get_cr8);
 
 static void kvm_update_dr0123(struct kvm_vcpu *vcpu)
 {
@@ -1510,7 +1510,7 @@ void kvm_update_dr7(struct kvm_vcpu *vcpu)
 	if (dr7 & DR7_BP_EN_MASK)
 		vcpu->arch.switch_db_regs |= KVM_DEBUGREG_BP_ENABLED;
 }
-EXPORT_SYMBOL_GPL(kvm_update_dr7);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_update_dr7);
 
 static u64 kvm_dr6_fixed(struct kvm_vcpu *vcpu)
 {
@@ -1551,7 +1551,7 @@ int kvm_set_dr(struct kvm_vcpu *vcpu, int dr, unsigned long val)
 
 	return 0;
 }
-EXPORT_SYMBOL_GPL(kvm_set_dr);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_set_dr);
 
 unsigned long kvm_get_dr(struct kvm_vcpu *vcpu, int dr)
 {
@@ -1568,7 +1568,7 @@ unsigned long kvm_get_dr(struct kvm_vcpu *vcpu, int dr)
 		return vcpu->arch.dr7;
 	}
 }
-EXPORT_SYMBOL_GPL(kvm_get_dr);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_get_dr);
 
 int kvm_emulate_rdpmc(struct kvm_vcpu *vcpu)
 {
@@ -1584,7 +1584,7 @@ int kvm_emulate_rdpmc(struct kvm_vcpu *vcpu)
 	kvm_rdx_write(vcpu, data >> 32);
 	return kvm_skip_emulated_instruction(vcpu);
 }
-EXPORT_SYMBOL_GPL(kvm_emulate_rdpmc);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_emulate_rdpmc);
 
 /*
  * Some IA32_ARCH_CAPABILITIES bits have dependencies on MSRs that KVM
@@ -1723,7 +1723,7 @@ bool kvm_valid_efer(struct kvm_vcpu *vcpu, u64 efer)
 
 	return __kvm_valid_efer(vcpu, efer);
 }
-EXPORT_SYMBOL_GPL(kvm_valid_efer);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_valid_efer);
 
 static int set_efer(struct kvm_vcpu *vcpu, struct msr_data *msr_info)
 {
@@ -1766,7 +1766,7 @@ void kvm_enable_efer_bits(u64 mask)
 {
        efer_reserved_bits &= ~mask;
 }
-EXPORT_SYMBOL_GPL(kvm_enable_efer_bits);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_enable_efer_bits);
 
 bool kvm_msr_allowed(struct kvm_vcpu *vcpu, u32 index, u32 type)
 {
@@ -1809,7 +1809,7 @@ bool kvm_msr_allowed(struct kvm_vcpu *vcpu, u32 index, u32 type)
 
 	return allowed;
 }
-EXPORT_SYMBOL_GPL(kvm_msr_allowed);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_msr_allowed);
 
 /*
  * Write @data into the MSR specified by @index.  Select MSR specific fault
@@ -1938,7 +1938,7 @@ int kvm_get_msr_with_filter(struct kvm_vcpu *vcpu, u32 index, u64 *data)
 		return KVM_MSR_RET_FILTERED;
 	return kvm_get_msr_ignored_check(vcpu, index, data, false);
 }
-EXPORT_SYMBOL_GPL(kvm_get_msr_with_filter);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_get_msr_with_filter);
 
 int kvm_set_msr_with_filter(struct kvm_vcpu *vcpu, u32 index, u64 data)
 {
@@ -1946,19 +1946,19 @@ int kvm_set_msr_with_filter(struct kvm_vcpu *vcpu, u32 index, u64 data)
 		return KVM_MSR_RET_FILTERED;
 	return kvm_set_msr_ignored_check(vcpu, index, data, false);
 }
-EXPORT_SYMBOL_GPL(kvm_set_msr_with_filter);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_set_msr_with_filter);
 
 int kvm_get_msr(struct kvm_vcpu *vcpu, u32 index, u64 *data)
 {
 	return kvm_get_msr_ignored_check(vcpu, index, data, false);
 }
-EXPORT_SYMBOL_GPL(kvm_get_msr);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_get_msr);
 
 int kvm_set_msr(struct kvm_vcpu *vcpu, u32 index, u64 data)
 {
 	return kvm_set_msr_ignored_check(vcpu, index, data, false);
 }
-EXPORT_SYMBOL_GPL(kvm_set_msr);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_set_msr);
 
 static void complete_userspace_rdmsr(struct kvm_vcpu *vcpu)
 {
@@ -2047,7 +2047,7 @@ int kvm_emulate_rdmsr(struct kvm_vcpu *vcpu)
 
 	return kvm_x86_call(complete_emulated_msr)(vcpu, r);
 }
-EXPORT_SYMBOL_GPL(kvm_emulate_rdmsr);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_emulate_rdmsr);
 
 int kvm_emulate_wrmsr(struct kvm_vcpu *vcpu)
 {
@@ -2072,7 +2072,7 @@ int kvm_emulate_wrmsr(struct kvm_vcpu *vcpu)
 
 	return kvm_x86_call(complete_emulated_msr)(vcpu, r);
 }
-EXPORT_SYMBOL_GPL(kvm_emulate_wrmsr);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_emulate_wrmsr);
 
 int kvm_emulate_as_nop(struct kvm_vcpu *vcpu)
 {
@@ -2084,14 +2084,14 @@ int kvm_emulate_invd(struct kvm_vcpu *vcpu)
 	/* Treat an INVD instruction as a NOP and just skip it. */
 	return kvm_emulate_as_nop(vcpu);
 }
-EXPORT_SYMBOL_GPL(kvm_emulate_invd);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_emulate_invd);
 
 int kvm_handle_invalid_op(struct kvm_vcpu *vcpu)
 {
 	kvm_queue_exception(vcpu, UD_VECTOR);
 	return 1;
 }
-EXPORT_SYMBOL_GPL(kvm_handle_invalid_op);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_handle_invalid_op);
 
 
 static int kvm_emulate_monitor_mwait(struct kvm_vcpu *vcpu, const char *insn)
@@ -2117,13 +2117,13 @@ int kvm_emulate_mwait(struct kvm_vcpu *vcpu)
 {
 	return kvm_emulate_monitor_mwait(vcpu, "MWAIT");
 }
-EXPORT_SYMBOL_GPL(kvm_emulate_mwait);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_emulate_mwait);
 
 int kvm_emulate_monitor(struct kvm_vcpu *vcpu)
 {
 	return kvm_emulate_monitor_mwait(vcpu, "MONITOR");
 }
-EXPORT_SYMBOL_GPL(kvm_emulate_monitor);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_emulate_monitor);
 
 static inline bool kvm_vcpu_exit_request(struct kvm_vcpu *vcpu)
 {
@@ -2200,7 +2200,7 @@ fastpath_t handle_fastpath_set_msr_irqoff(struct kvm_vcpu *vcpu)
 
 	return ret;
 }
-EXPORT_SYMBOL_GPL(handle_fastpath_set_msr_irqoff);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(handle_fastpath_set_msr_irqoff);
 
 /*
  * Adapt set_msr() to msr_io()'s calling convention
@@ -2566,7 +2566,7 @@ u64 kvm_read_l1_tsc(struct kvm_vcpu *vcpu, u64 host_tsc)
 	return vcpu->arch.l1_tsc_offset +
 		kvm_scale_tsc(host_tsc, vcpu->arch.l1_tsc_scaling_ratio);
 }
-EXPORT_SYMBOL_GPL(kvm_read_l1_tsc);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_read_l1_tsc);
 
 u64 kvm_calc_nested_tsc_offset(u64 l1_offset, u64 l2_offset, u64 l2_multiplier)
 {
@@ -2581,7 +2581,7 @@ u64 kvm_calc_nested_tsc_offset(u64 l1_offset, u64 l2_offset, u64 l2_multiplier)
 	nested_offset += l2_offset;
 	return nested_offset;
 }
-EXPORT_SYMBOL_GPL(kvm_calc_nested_tsc_offset);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_calc_nested_tsc_offset);
 
 u64 kvm_calc_nested_tsc_multiplier(u64 l1_multiplier, u64 l2_multiplier)
 {
@@ -2591,7 +2591,7 @@ u64 kvm_calc_nested_tsc_multiplier(u64 l1_multiplier, u64 l2_multiplier)
 
 	return l1_multiplier;
 }
-EXPORT_SYMBOL_GPL(kvm_calc_nested_tsc_multiplier);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_calc_nested_tsc_multiplier);
 
 static void kvm_vcpu_write_tsc_offset(struct kvm_vcpu *vcpu, u64 l1_offset)
 {
@@ -3669,7 +3669,7 @@ void kvm_service_local_tlb_flush_requests(struct kvm_vcpu *vcpu)
 	if (kvm_check_request(KVM_REQ_TLB_FLUSH_GUEST, vcpu))
 		kvm_vcpu_flush_tlb_guest(vcpu);
 }
-EXPORT_SYMBOL_GPL(kvm_service_local_tlb_flush_requests);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_service_local_tlb_flush_requests);
 
 static void record_steal_time(struct kvm_vcpu *vcpu)
 {
@@ -4161,7 +4161,7 @@ int kvm_set_msr_common(struct kvm_vcpu *vcpu, struct msr_data *msr_info)
 	}
 	return 0;
 }
-EXPORT_SYMBOL_GPL(kvm_set_msr_common);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_set_msr_common);
 
 static int get_msr_mce(struct kvm_vcpu *vcpu, u32 msr, u64 *pdata, bool host)
 {
@@ -4510,7 +4510,7 @@ int kvm_get_msr_common(struct kvm_vcpu *vcpu, struct msr_data *msr_info)
 	}
 	return 0;
 }
-EXPORT_SYMBOL_GPL(kvm_get_msr_common);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_get_msr_common);
 
 /*
  * Read or write a bunch of msrs. All parameters are kernel addresses.
@@ -7484,7 +7484,7 @@ gpa_t kvm_mmu_gva_to_gpa_read(struct kvm_vcpu *vcpu, gva_t gva,
 	u64 access = (kvm_x86_call(get_cpl)(vcpu) == 3) ? PFERR_USER_MASK : 0;
 	return mmu->gva_to_gpa(vcpu, mmu, gva, access, exception);
 }
-EXPORT_SYMBOL_GPL(kvm_mmu_gva_to_gpa_read);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_mmu_gva_to_gpa_read);
 
 gpa_t kvm_mmu_gva_to_gpa_write(struct kvm_vcpu *vcpu, gva_t gva,
 			       struct x86_exception *exception)
@@ -7495,7 +7495,7 @@ gpa_t kvm_mmu_gva_to_gpa_write(struct kvm_vcpu *vcpu, gva_t gva,
 	access |= PFERR_WRITE_MASK;
 	return mmu->gva_to_gpa(vcpu, mmu, gva, access, exception);
 }
-EXPORT_SYMBOL_GPL(kvm_mmu_gva_to_gpa_write);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_mmu_gva_to_gpa_write);
 
 /* uses this to access any guest's mapped memory without checking CPL */
 gpa_t kvm_mmu_gva_to_gpa_system(struct kvm_vcpu *vcpu, gva_t gva,
@@ -7581,7 +7581,7 @@ int kvm_read_guest_virt(struct kvm_vcpu *vcpu,
 	return kvm_read_guest_virt_helper(addr, val, bytes, vcpu, access,
 					  exception);
 }
-EXPORT_SYMBOL_GPL(kvm_read_guest_virt);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_read_guest_virt);
 
 static int emulator_read_std(struct x86_emulate_ctxt *ctxt,
 			     gva_t addr, void *val, unsigned int bytes,
@@ -7653,7 +7653,7 @@ int kvm_write_guest_virt_system(struct kvm_vcpu *vcpu, gva_t addr, void *val,
 	return kvm_write_guest_virt_helper(addr, val, bytes, vcpu,
 					   PFERR_WRITE_MASK, exception);
 }
-EXPORT_SYMBOL_GPL(kvm_write_guest_virt_system);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_write_guest_virt_system);
 
 static int kvm_check_emulate_insn(struct kvm_vcpu *vcpu, int emul_type,
 				  void *insn, int insn_len)
@@ -7687,7 +7687,7 @@ int handle_ud(struct kvm_vcpu *vcpu)
 
 	return kvm_emulate_instruction(vcpu, emul_type);
 }
-EXPORT_SYMBOL_GPL(handle_ud);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(handle_ud);
 
 static int vcpu_is_mmio_gpa(struct kvm_vcpu *vcpu, unsigned long gva,
 			    gpa_t gpa, bool write)
@@ -8166,7 +8166,7 @@ int kvm_emulate_wbinvd(struct kvm_vcpu *vcpu)
 	kvm_emulate_wbinvd_noskip(vcpu);
 	return kvm_skip_emulated_instruction(vcpu);
 }
-EXPORT_SYMBOL_GPL(kvm_emulate_wbinvd);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_emulate_wbinvd);
 
 
 
@@ -8661,7 +8661,7 @@ void kvm_inject_realmode_interrupt(struct kvm_vcpu *vcpu, int irq, int inc_eip)
 		kvm_set_rflags(vcpu, ctxt->eflags);
 	}
 }
-EXPORT_SYMBOL_GPL(kvm_inject_realmode_interrupt);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_inject_realmode_interrupt);
 
 static void prepare_emulation_failure_exit(struct kvm_vcpu *vcpu, u64 *data,
 					   u8 ndata, u8 *insn_bytes, u8 insn_size)
@@ -8726,13 +8726,13 @@ void __kvm_prepare_emulation_failure_exit(struct kvm_vcpu *vcpu, u64 *data,
 {
 	prepare_emulation_failure_exit(vcpu, data, ndata, NULL, 0);
 }
-EXPORT_SYMBOL_GPL(__kvm_prepare_emulation_failure_exit);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(__kvm_prepare_emulation_failure_exit);
 
 void kvm_prepare_emulation_failure_exit(struct kvm_vcpu *vcpu)
 {
 	__kvm_prepare_emulation_failure_exit(vcpu, NULL, 0);
 }
-EXPORT_SYMBOL_GPL(kvm_prepare_emulation_failure_exit);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_prepare_emulation_failure_exit);
 
 void kvm_prepare_event_vectoring_exit(struct kvm_vcpu *vcpu, gpa_t gpa)
 {
@@ -8754,7 +8754,7 @@ void kvm_prepare_event_vectoring_exit(struct kvm_vcpu *vcpu, gpa_t gpa)
 	run->internal.suberror = KVM_INTERNAL_ERROR_DELIVERY_EV;
 	run->internal.ndata = ndata;
 }
-EXPORT_SYMBOL_GPL(kvm_prepare_event_vectoring_exit);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_prepare_event_vectoring_exit);
 
 static int handle_emulation_failure(struct kvm_vcpu *vcpu, int emulation_type)
 {
@@ -8878,7 +8878,7 @@ int kvm_skip_emulated_instruction(struct kvm_vcpu *vcpu)
 		r = kvm_vcpu_do_singlestep(vcpu);
 	return r;
 }
-EXPORT_SYMBOL_GPL(kvm_skip_emulated_instruction);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_skip_emulated_instruction);
 
 static bool kvm_is_code_breakpoint_inhibited(struct kvm_vcpu *vcpu)
 {
@@ -9009,7 +9009,7 @@ int x86_decode_emulated_instruction(struct kvm_vcpu *vcpu, int emulation_type,
 
 	return r;
 }
-EXPORT_SYMBOL_GPL(x86_decode_emulated_instruction);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(x86_decode_emulated_instruction);
 
 int x86_emulate_instruction(struct kvm_vcpu *vcpu, gpa_t cr2_or_gpa,
 			    int emulation_type, void *insn, int insn_len)
@@ -9226,14 +9226,14 @@ int kvm_emulate_instruction(struct kvm_vcpu *vcpu, int emulation_type)
 {
 	return x86_emulate_instruction(vcpu, 0, emulation_type, NULL, 0);
 }
-EXPORT_SYMBOL_GPL(kvm_emulate_instruction);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_emulate_instruction);
 
 int kvm_emulate_instruction_from_buffer(struct kvm_vcpu *vcpu,
 					void *insn, int insn_len)
 {
 	return x86_emulate_instruction(vcpu, 0, 0, insn, insn_len);
 }
-EXPORT_SYMBOL_GPL(kvm_emulate_instruction_from_buffer);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_emulate_instruction_from_buffer);
 
 static int complete_fast_pio_out_port_0x7e(struct kvm_vcpu *vcpu)
 {
@@ -9328,7 +9328,7 @@ int kvm_fast_pio(struct kvm_vcpu *vcpu, int size, unsigned short port, int in)
 		ret = kvm_fast_pio_out(vcpu, size, port);
 	return ret && kvm_skip_emulated_instruction(vcpu);
 }
-EXPORT_SYMBOL_GPL(kvm_fast_pio);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_fast_pio);
 
 static int kvmclock_cpu_down_prep(unsigned int cpu)
 {
@@ -9760,7 +9760,7 @@ int kvm_x86_vendor_init(struct kvm_x86_init_ops *ops)
 	kmem_cache_destroy(x86_emulator_cache);
 	return r;
 }
-EXPORT_SYMBOL_GPL(kvm_x86_vendor_init);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_x86_vendor_init);
 
 void kvm_x86_vendor_exit(void)
 {
@@ -9794,7 +9794,7 @@ void kvm_x86_vendor_exit(void)
 	kvm_x86_ops.enable_virtualization_cpu = NULL;
 	mutex_unlock(&vendor_module_lock);
 }
-EXPORT_SYMBOL_GPL(kvm_x86_vendor_exit);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_x86_vendor_exit);
 
 #ifdef CONFIG_X86_64
 static int kvm_pv_clock_pairing(struct kvm_vcpu *vcpu, gpa_t paddr,
@@ -9858,7 +9858,7 @@ bool kvm_apicv_activated(struct kvm *kvm)
 {
 	return (READ_ONCE(kvm->arch.apicv_inhibit_reasons) == 0);
 }
-EXPORT_SYMBOL_GPL(kvm_apicv_activated);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_apicv_activated);
 
 bool kvm_vcpu_apicv_activated(struct kvm_vcpu *vcpu)
 {
@@ -9868,7 +9868,7 @@ bool kvm_vcpu_apicv_activated(struct kvm_vcpu *vcpu)
 
 	return (vm_reasons | vcpu_reasons) == 0;
 }
-EXPORT_SYMBOL_GPL(kvm_vcpu_apicv_activated);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_vcpu_apicv_activated);
 
 static void set_or_clear_apicv_inhibit(unsigned long *inhibits,
 				       enum kvm_apicv_inhibit reason, bool set)
@@ -10041,7 +10041,7 @@ int ____kvm_emulate_hypercall(struct kvm_vcpu *vcpu, int cpl,
 	vcpu->run->hypercall.ret = ret;
 	return 1;
 }
-EXPORT_SYMBOL_GPL(____kvm_emulate_hypercall);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(____kvm_emulate_hypercall);
 
 int kvm_emulate_hypercall(struct kvm_vcpu *vcpu)
 {
@@ -10054,7 +10054,7 @@ int kvm_emulate_hypercall(struct kvm_vcpu *vcpu)
 	return __kvm_emulate_hypercall(vcpu, kvm_x86_call(get_cpl)(vcpu),
 				       complete_hypercall_exit);
 }
-EXPORT_SYMBOL_GPL(kvm_emulate_hypercall);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_emulate_hypercall);
 
 static int emulator_fix_hypercall(struct x86_emulate_ctxt *ctxt)
 {
@@ -10497,7 +10497,7 @@ void __kvm_vcpu_update_apicv(struct kvm_vcpu *vcpu)
 	preempt_enable();
 	up_read(&vcpu->kvm->arch.apicv_update_lock);
 }
-EXPORT_SYMBOL_GPL(__kvm_vcpu_update_apicv);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(__kvm_vcpu_update_apicv);
 
 static void kvm_vcpu_update_apicv(struct kvm_vcpu *vcpu)
 {
@@ -10573,7 +10573,7 @@ void kvm_set_or_clear_apicv_inhibit(struct kvm *kvm,
 	__kvm_set_or_clear_apicv_inhibit(kvm, reason, set);
 	up_write(&kvm->arch.apicv_update_lock);
 }
-EXPORT_SYMBOL_GPL(kvm_set_or_clear_apicv_inhibit);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_set_or_clear_apicv_inhibit);
 
 static void vcpu_scan_ioapic(struct kvm_vcpu *vcpu)
 {
@@ -11123,7 +11123,7 @@ bool kvm_vcpu_has_events(struct kvm_vcpu *vcpu)
 
 	return false;
 }
-EXPORT_SYMBOL_GPL(kvm_vcpu_has_events);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_vcpu_has_events);
 
 int kvm_arch_vcpu_runnable(struct kvm_vcpu *vcpu)
 {
@@ -11276,7 +11276,7 @@ int kvm_emulate_halt_noskip(struct kvm_vcpu *vcpu)
 {
 	return __kvm_emulate_halt(vcpu, KVM_MP_STATE_HALTED, KVM_EXIT_HLT);
 }
-EXPORT_SYMBOL_GPL(kvm_emulate_halt_noskip);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_emulate_halt_noskip);
 
 int kvm_emulate_halt(struct kvm_vcpu *vcpu)
 {
@@ -11287,7 +11287,7 @@ int kvm_emulate_halt(struct kvm_vcpu *vcpu)
 	 */
 	return kvm_emulate_halt_noskip(vcpu) && ret;
 }
-EXPORT_SYMBOL_GPL(kvm_emulate_halt);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_emulate_halt);
 
 fastpath_t handle_fastpath_hlt(struct kvm_vcpu *vcpu)
 {
@@ -11305,7 +11305,7 @@ fastpath_t handle_fastpath_hlt(struct kvm_vcpu *vcpu)
 
 	return EXIT_FASTPATH_EXIT_HANDLED;
 }
-EXPORT_SYMBOL_GPL(handle_fastpath_hlt);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(handle_fastpath_hlt);
 
 int kvm_emulate_ap_reset_hold(struct kvm_vcpu *vcpu)
 {
@@ -11314,7 +11314,7 @@ int kvm_emulate_ap_reset_hold(struct kvm_vcpu *vcpu)
 	return __kvm_emulate_halt(vcpu, KVM_MP_STATE_AP_RESET_HOLD,
 					KVM_EXIT_AP_RESET_HOLD) && ret;
 }
-EXPORT_SYMBOL_GPL(kvm_emulate_ap_reset_hold);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_emulate_ap_reset_hold);
 
 bool kvm_arch_dy_has_pending_interrupt(struct kvm_vcpu *vcpu)
 {
@@ -11846,7 +11846,7 @@ int kvm_task_switch(struct kvm_vcpu *vcpu, u16 tss_selector, int idt_index,
 	kvm_set_rflags(vcpu, ctxt->eflags);
 	return 1;
 }
-EXPORT_SYMBOL_GPL(kvm_task_switch);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_task_switch);
 
 static bool kvm_is_valid_sregs(struct kvm_vcpu *vcpu, struct kvm_sregs *sregs)
 {
@@ -12526,7 +12526,7 @@ void kvm_vcpu_reset(struct kvm_vcpu *vcpu, bool init_event)
 	if (init_event)
 		kvm_make_request(KVM_REQ_TLB_FLUSH_GUEST, vcpu);
 }
-EXPORT_SYMBOL_GPL(kvm_vcpu_reset);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_vcpu_reset);
 
 void kvm_vcpu_deliver_sipi_vector(struct kvm_vcpu *vcpu, u8 vector)
 {
@@ -12538,7 +12538,7 @@ void kvm_vcpu_deliver_sipi_vector(struct kvm_vcpu *vcpu, u8 vector)
 	kvm_set_segment(vcpu, &cs, VCPU_SREG_CS);
 	kvm_rip_write(vcpu, 0);
 }
-EXPORT_SYMBOL_GPL(kvm_vcpu_deliver_sipi_vector);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_vcpu_deliver_sipi_vector);
 
 void kvm_arch_enable_virtualization(void)
 {
@@ -12656,7 +12656,7 @@ bool kvm_vcpu_is_reset_bsp(struct kvm_vcpu *vcpu)
 {
 	return vcpu->kvm->arch.bsp_vcpu_id == vcpu->vcpu_id;
 }
-EXPORT_SYMBOL_GPL(kvm_vcpu_is_reset_bsp);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_vcpu_is_reset_bsp);
 
 bool kvm_vcpu_is_bsp(struct kvm_vcpu *vcpu)
 {
@@ -12820,7 +12820,7 @@ void __user * __x86_set_memory_region(struct kvm *kvm, int id, gpa_t gpa,
 
 	return (void __user *)hva;
 }
-EXPORT_SYMBOL_GPL(__x86_set_memory_region);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(__x86_set_memory_region);
 
 void kvm_arch_pre_destroy_vm(struct kvm *kvm)
 {
@@ -13228,13 +13228,13 @@ unsigned long kvm_get_linear_rip(struct kvm_vcpu *vcpu)
 	return (u32)(get_segment_base(vcpu, VCPU_SREG_CS) +
 		     kvm_rip_read(vcpu));
 }
-EXPORT_SYMBOL_GPL(kvm_get_linear_rip);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_get_linear_rip);
 
 bool kvm_is_linear_rip(struct kvm_vcpu *vcpu, unsigned long linear_rip)
 {
 	return kvm_get_linear_rip(vcpu) == linear_rip;
 }
-EXPORT_SYMBOL_GPL(kvm_is_linear_rip);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_is_linear_rip);
 
 unsigned long kvm_get_rflags(struct kvm_vcpu *vcpu)
 {
@@ -13245,7 +13245,7 @@ unsigned long kvm_get_rflags(struct kvm_vcpu *vcpu)
 		rflags &= ~X86_EFLAGS_TF;
 	return rflags;
 }
-EXPORT_SYMBOL_GPL(kvm_get_rflags);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_get_rflags);
 
 static void __kvm_set_rflags(struct kvm_vcpu *vcpu, unsigned long rflags)
 {
@@ -13260,7 +13260,7 @@ void kvm_set_rflags(struct kvm_vcpu *vcpu, unsigned long rflags)
 	__kvm_set_rflags(vcpu, rflags);
 	kvm_make_request(KVM_REQ_EVENT, vcpu);
 }
-EXPORT_SYMBOL_GPL(kvm_set_rflags);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_set_rflags);
 
 static inline u32 kvm_async_pf_hash_fn(gfn_t gfn)
 {
@@ -13503,7 +13503,7 @@ bool kvm_arch_has_noncoherent_dma(struct kvm *kvm)
 {
 	return atomic_read(&kvm->arch.noncoherent_dma_count);
 }
-EXPORT_SYMBOL_GPL(kvm_arch_has_noncoherent_dma);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_arch_has_noncoherent_dma);
 
 bool kvm_vector_hashing_enabled(void)
 {
@@ -13553,7 +13553,7 @@ int kvm_spec_ctrl_test_value(u64 value)
 
 	return ret;
 }
-EXPORT_SYMBOL_GPL(kvm_spec_ctrl_test_value);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_spec_ctrl_test_value);
 
 void kvm_fixup_and_inject_pf_error(struct kvm_vcpu *vcpu, gva_t gva, u16 error_code)
 {
@@ -13578,7 +13578,7 @@ void kvm_fixup_and_inject_pf_error(struct kvm_vcpu *vcpu, gva_t gva, u16 error_c
 	}
 	vcpu->arch.walk_mmu->inject_page_fault(vcpu, &fault);
 }
-EXPORT_SYMBOL_GPL(kvm_fixup_and_inject_pf_error);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_fixup_and_inject_pf_error);
 
 /*
  * Handles kvm_read/write_guest_virt*() result and either injects #PF or returns
@@ -13607,7 +13607,7 @@ int kvm_handle_memory_failure(struct kvm_vcpu *vcpu, int r,
 
 	return 0;
 }
-EXPORT_SYMBOL_GPL(kvm_handle_memory_failure);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_handle_memory_failure);
 
 int kvm_handle_invpcid(struct kvm_vcpu *vcpu, unsigned long type, gva_t gva)
 {
@@ -13671,7 +13671,7 @@ int kvm_handle_invpcid(struct kvm_vcpu *vcpu, unsigned long type, gva_t gva)
 		return 1;
 	}
 }
-EXPORT_SYMBOL_GPL(kvm_handle_invpcid);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_handle_invpcid);
 
 static int complete_sev_es_emulated_mmio(struct kvm_vcpu *vcpu)
 {
@@ -13756,7 +13756,7 @@ int kvm_sev_es_mmio_write(struct kvm_vcpu *vcpu, gpa_t gpa, unsigned int bytes,
 
 	return 0;
 }
-EXPORT_SYMBOL_GPL(kvm_sev_es_mmio_write);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_sev_es_mmio_write);
 
 int kvm_sev_es_mmio_read(struct kvm_vcpu *vcpu, gpa_t gpa, unsigned int bytes,
 			 void *data)
@@ -13794,7 +13794,7 @@ int kvm_sev_es_mmio_read(struct kvm_vcpu *vcpu, gpa_t gpa, unsigned int bytes,
 
 	return 0;
 }
-EXPORT_SYMBOL_GPL(kvm_sev_es_mmio_read);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_sev_es_mmio_read);
 
 static void advance_sev_es_emulated_pio(struct kvm_vcpu *vcpu, unsigned count, int size)
 {
@@ -13882,7 +13882,7 @@ int kvm_sev_es_string_io(struct kvm_vcpu *vcpu, unsigned int size,
 	return in ? kvm_sev_es_ins(vcpu, size, port)
 		  : kvm_sev_es_outs(vcpu, size, port);
 }
-EXPORT_SYMBOL_GPL(kvm_sev_es_string_io);
+EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(kvm_sev_es_string_io);
 
 EXPORT_TRACEPOINT_SYMBOL_GPL(kvm_entry);
 EXPORT_TRACEPOINT_SYMBOL_GPL(kvm_exit);

---

## [7] Sean Christopherson — 2025-07-29
*Subject: [PATCH 6/6] x86: Restrict KVM-induced symbol exports to KVM modules
 where obvious/possible*

Extend KVM's export macro framework to provide EXPORT_SYMBOL_GPL_FOR_KVM(),
and use the helper macro to export symbols for KVM throughout x86 if and
only if KVM will build one or more modules, and only for those modules.

To avoid unnecessary exports when CONFIG_KVM=m but kvm.ko will not be
built (because no vendor modules are selected), let arch code #define
EXPORT_SYMBOL_GPL_FOR_KVM to suppress/override the exports.

Note, the set of symbols to restrict to KVM was generated by manual search
and audit; any "misses" are due to human error, not some grand plan.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/entry/entry.S             |  7 ++--
 arch/x86/entry/entry_64_fred.S     |  3 +-
 arch/x86/events/amd/core.c         |  5 ++-
 arch/x86/events/core.c             |  7 ++--
 arch/x86/events/intel/lbr.c        |  3 +-
 arch/x86/events/intel/pt.c         |  7 ++--
 arch/x86/include/asm/kvm_types.h   |  5 +++
 arch/x86/kernel/apic/apic.c        |  3 +-
 arch/x86/kernel/apic/apic_common.c |  3 +-
 arch/x86/kernel/cpu/amd.c          |  4 +-
 arch/x86/kernel/cpu/bugs.c         | 17 ++++----
 arch/x86/kernel/cpu/bus_lock.c     |  3 +-
 arch/x86/kernel/cpu/common.c       |  7 ++--
 arch/x86/kernel/cpu/sgx/main.c     |  3 +-
 arch/x86/kernel/cpu/sgx/virt.c     |  5 ++-
 arch/x86/kernel/e820.c             |  3 +-
 arch/x86/kernel/fpu/core.c         | 21 +++++-----
 arch/x86/kernel/fpu/xstate.c       |  7 ++--
 arch/x86/kernel/hw_breakpoint.c    |  3 +-
 arch/x86/kernel/irq.c              |  3 +-
 arch/x86/kernel/kvm.c              |  5 ++-
 arch/x86/kernel/nmi.c              |  5 +--
 arch/x86/kernel/process_64.c       |  5 +--
 arch/x86/kernel/reboot.c           |  5 ++-
 arch/x86/kernel/tsc.c              |  1 +
 arch/x86/lib/cache-smp.c           |  9 +++--
 arch/x86/lib/msr.c                 |  5 ++-
 arch/x86/mm/pat/memtype.c          |  3 +-
 arch/x86/mm/tlb.c                  |  5 ++-
 arch/x86/virt/vmx/tdx/tdx.c        | 65 +++++++++++++++---------------
 include/linux/kvm_types.h          | 14 +++++++
 31 files changed, 140 insertions(+), 101 deletions(-)

diff --git a/arch/x86/entry/entry.S b/arch/x86/entry/entry.S
index 8e9a0cc20a4a..0a94e9c93d1e 100644
--- a/arch/x86/entry/entry.S
+++ b/arch/x86/entry/entry.S
@@ -4,6 +4,7 @@
  */
 
 #include <linux/export.h>
+#include <linux/kvm_types.h>
 #include <linux/linkage.h>
 #include <linux/objtool.h>
 #include <asm/msr-index.h>
@@ -29,8 +30,7 @@ SYM_FUNC_START(write_ibpb)
 	FILL_RETURN_BUFFER %rax, RSB_CLEAR_LOOPS, X86_BUG_IBPB_NO_RET
 	RET
 SYM_FUNC_END(write_ibpb)
-/* For KVM */
-EXPORT_SYMBOL_GPL(write_ibpb);
+EXPORT_SYMBOL_GPL_FOR_KVM(write_ibpb);
 
 .popsection
 
@@ -48,8 +48,7 @@ SYM_CODE_START_NOALIGN(x86_verw_sel)
 	.word __KERNEL_DS
 .align L1_CACHE_BYTES, 0xcc
 SYM_CODE_END(x86_verw_sel);
-/* For KVM */
-EXPORT_SYMBOL_GPL(x86_verw_sel);
+EXPORT_SYMBOL_GPL_FOR_KVM(x86_verw_sel);
 
 .popsection
 
diff --git a/arch/x86/entry/entry_64_fred.S b/arch/x86/entry/entry_64_fred.S
index 29c5c32c16c3..629cbed9061e 100644
--- a/arch/x86/entry/entry_64_fred.S
+++ b/arch/x86/entry/entry_64_fred.S
@@ -4,6 +4,7 @@
  */
 
 #include <linux/export.h>
+#include <linux/kvm_types.h>
 
 #include <asm/asm.h>
 #include <asm/fred.h>
@@ -128,5 +129,5 @@ SYM_FUNC_START(asm_fred_entry_from_kvm)
 	RET
 
 SYM_FUNC_END(asm_fred_entry_from_kvm)
-EXPORT_SYMBOL_GPL(asm_fred_entry_from_kvm);
+EXPORT_SYMBOL_GPL_FOR_KVM(asm_fred_entry_from_kvm);
 #endif
diff --git a/arch/x86/events/amd/core.c b/arch/x86/events/amd/core.c
index b20661b8621d..0c7c8022b07c 100644
--- a/arch/x86/events/amd/core.c
+++ b/arch/x86/events/amd/core.c
@@ -2,6 +2,7 @@
 #include <linux/perf_event.h>
 #include <linux/jump_label.h>
 #include <linux/export.h>
+#include <linux/kvm_types.h>
 #include <linux/types.h>
 #include <linux/init.h>
 #include <linux/slab.h>
@@ -1569,7 +1570,7 @@ void amd_pmu_enable_virt(void)
 	/* Reload all events */
 	amd_pmu_reload_virt();
 }
-EXPORT_SYMBOL_GPL(amd_pmu_enable_virt);
+EXPORT_SYMBOL_GPL_FOR_KVM(amd_pmu_enable_virt);
 
 void amd_pmu_disable_virt(void)
 {
@@ -1586,4 +1587,4 @@ void amd_pmu_disable_virt(void)
 	/* Reload all events */
 	amd_pmu_reload_virt();
 }
-EXPORT_SYMBOL_GPL(amd_pmu_disable_virt);
+EXPORT_SYMBOL_GPL_FOR_KVM(amd_pmu_disable_virt);
diff --git a/arch/x86/events/core.c b/arch/x86/events/core.c
index 7610f26dfbd9..54d0228333be 100644
--- a/arch/x86/events/core.c
+++ b/arch/x86/events/core.c
@@ -20,6 +20,7 @@
 #include <linux/export.h>
 #include <linux/init.h>
 #include <linux/kdebug.h>
+#include <linux/kvm_types.h>
 #include <linux/sched/mm.h>
 #include <linux/sched/clock.h>
 #include <linux/uaccess.h>
@@ -714,7 +715,7 @@ struct perf_guest_switch_msr *perf_guest_get_msrs(int *nr, void *data)
 {
 	return static_call(x86_pmu_guest_get_msrs)(nr, data);
 }
-EXPORT_SYMBOL_GPL(perf_guest_get_msrs);
+EXPORT_SYMBOL_GPL_FOR_KVM(perf_guest_get_msrs);
 
 /*
  * There may be PMI landing after enabled=0. The PMI hitting could be before or
@@ -3104,7 +3105,7 @@ void perf_get_x86_pmu_capability(struct x86_pmu_capability *cap)
 	cap->events_mask_len	= x86_pmu.events_mask_len;
 	cap->pebs_ept		= x86_pmu.pebs_ept;
 }
-EXPORT_SYMBOL_GPL(perf_get_x86_pmu_capability);
+EXPORT_SYMBOL_GPL_FOR_KVM(perf_get_x86_pmu_capability);
 
 u64 perf_get_hw_event_config(int hw_event)
 {
@@ -3115,4 +3116,4 @@ u64 perf_get_hw_event_config(int hw_event)
 
 	return 0;
 }
-EXPORT_SYMBOL_GPL(perf_get_hw_event_config);
+EXPORT_SYMBOL_GPL_FOR_KVM(perf_get_hw_event_config);
diff --git a/arch/x86/events/intel/lbr.c b/arch/x86/events/intel/lbr.c
index 7aa59966e7c3..972017b2fd35 100644
--- a/arch/x86/events/intel/lbr.c
+++ b/arch/x86/events/intel/lbr.c
@@ -1,4 +1,5 @@
 // SPDX-License-Identifier: GPL-2.0
+#include <linux/kvm_types.h>
 #include <linux/perf_event.h>
 #include <linux/types.h>
 
@@ -1705,7 +1706,7 @@ void x86_perf_get_lbr(struct x86_pmu_lbr *lbr)
 	lbr->info = x86_pmu.lbr_info;
 	lbr->has_callstack = x86_pmu_has_lbr_callstack();
 }
-EXPORT_SYMBOL_GPL(x86_perf_get_lbr);
+EXPORT_SYMBOL_GPL_FOR_KVM(x86_perf_get_lbr);
 
 struct event_constraint vlbr_constraint =
 	__EVENT_CONSTRAINT(INTEL_FIXED_VLBR_EVENT, (1ULL << INTEL_PMC_IDX_FIXED_VLBR),
diff --git a/arch/x86/events/intel/pt.c b/arch/x86/events/intel/pt.c
index e8cf29d2b10c..fbe1ac90499a 100644
--- a/arch/x86/events/intel/pt.c
+++ b/arch/x86/events/intel/pt.c
@@ -17,6 +17,7 @@
 #include <linux/limits.h>
 #include <linux/slab.h>
 #include <linux/device.h>
+#include <linux/kvm_types.h>
 
 #include <asm/cpuid/api.h>
 #include <asm/perf_event.h>
@@ -82,13 +83,13 @@ u32 intel_pt_validate_cap(u32 *caps, enum pt_capabilities capability)
 
 	return (c & cd->mask) >> shift;
 }
-EXPORT_SYMBOL_GPL(intel_pt_validate_cap);
+EXPORT_SYMBOL_GPL_FOR_KVM(intel_pt_validate_cap);
 
 u32 intel_pt_validate_hw_cap(enum pt_capabilities cap)
 {
 	return intel_pt_validate_cap(pt_pmu.caps, cap);
 }
-EXPORT_SYMBOL_GPL(intel_pt_validate_hw_cap);
+EXPORT_SYMBOL_GPL_FOR_KVM(intel_pt_validate_hw_cap);
 
 static ssize_t pt_cap_show(struct device *cdev,
 			   struct device_attribute *attr,
@@ -1590,7 +1591,7 @@ void intel_pt_handle_vmx(int on)
 
 	local_irq_restore(flags);
 }
-EXPORT_SYMBOL_GPL(intel_pt_handle_vmx);
+EXPORT_SYMBOL_GPL_FOR_KVM(intel_pt_handle_vmx);
 
 /*
  * PMU callbacks
diff --git a/arch/x86/include/asm/kvm_types.h b/arch/x86/include/asm/kvm_types.h
index 23268a188e70..9597fe3a6c87 100644
--- a/arch/x86/include/asm/kvm_types.h
+++ b/arch/x86/include/asm/kvm_types.h
@@ -10,6 +10,11 @@
 #define KVM_SUB_MODULES kvm-intel
 #else
 #undef KVM_SUB_MODULES
+/*
+ * Don't export symbols for KVM without vendor modules, as kvm.ko is built iff
+ * at least one vendor module is enabled.
+ */
+#define EXPORT_SYMBOL_GPL_FOR_KVM(symbol)
 #endif
 
 #define KVM_ARCH_NR_OBJS_PER_MEMORY_CACHE 40
diff --git a/arch/x86/kernel/apic/apic.c b/arch/x86/kernel/apic/apic.c
index d73ba5a7b623..1c2a810e8dab 100644
--- a/arch/x86/kernel/apic/apic.c
+++ b/arch/x86/kernel/apic/apic.c
@@ -36,6 +36,7 @@
 #include <linux/dmi.h>
 #include <linux/smp.h>
 #include <linux/mm.h>
+#include <linux/kvm_types.h>
 
 #include <xen/xen.h>
 
@@ -2311,7 +2312,7 @@ u32 x86_msi_msg_get_destid(struct msi_msg *msg, bool extid)
 		dest |= msg->arch_addr_hi.destid_8_31 << 8;
 	return dest;
 }
-EXPORT_SYMBOL_GPL(x86_msi_msg_get_destid);
+EXPORT_SYMBOL_GPL_FOR_KVM(x86_msi_msg_get_destid);
 
 static void __init apic_bsp_up_setup(void)
 {
diff --git a/arch/x86/kernel/apic/apic_common.c b/arch/x86/kernel/apic/apic_common.c
index 9ef3be866832..df1436a3a76f 100644
--- a/arch/x86/kernel/apic/apic_common.c
+++ b/arch/x86/kernel/apic/apic_common.c
@@ -4,6 +4,7 @@
  * SPDX-License-Identifier: GPL-2.0
  */
 #include <linux/irq.h>
+#include <linux/kvm_types.h>
 #include <asm/apic.h>
 
 #include "local.h"
@@ -25,7 +26,7 @@ u32 default_cpu_present_to_apicid(int mps_cpu)
 	else
 		return BAD_APICID;
 }
-EXPORT_SYMBOL_GPL(default_cpu_present_to_apicid);
+EXPORT_SYMBOL_GPL_FOR_KVM(default_cpu_present_to_apicid);
 
 /*
  * Set up the logical destination ID when the APIC operates in logical
diff --git a/arch/x86/kernel/cpu/amd.c b/arch/x86/kernel/cpu/amd.c
index 329ee185d8cc..e382a81ea35b 100644
--- a/arch/x86/kernel/cpu/amd.c
+++ b/arch/x86/kernel/cpu/amd.c
@@ -3,7 +3,7 @@
 #include <linux/bitops.h>
 #include <linux/elf.h>
 #include <linux/mm.h>
-
+#include <linux/kvm_types.h>
 #include <linux/io.h>
 #include <linux/sched.h>
 #include <linux/sched/clock.h>
@@ -1281,7 +1281,7 @@ unsigned long amd_get_dr_addr_mask(unsigned int dr)
 
 	return per_cpu(amd_dr_addr_mask[dr], smp_processor_id());
 }
-EXPORT_SYMBOL_GPL(amd_get_dr_addr_mask);
+EXPORT_SYMBOL_GPL_FOR_KVM(amd_get_dr_addr_mask);
 
 static void zenbleed_check_cpu(void *unused)
 {
diff --git a/arch/x86/kernel/cpu/bugs.c b/arch/x86/kernel/cpu/bugs.c
index f4d3abb12317..855cc523618a 100644
--- a/arch/x86/kernel/cpu/bugs.c
+++ b/arch/x86/kernel/cpu/bugs.c
@@ -16,6 +16,7 @@
 #include <linux/sched/smt.h>
 #include <linux/pgtable.h>
 #include <linux/bpf.h>
+#include <linux/kvm_types.h>
 
 #include <asm/spec-ctrl.h>
 #include <asm/cmdline.h>
@@ -169,7 +170,7 @@ DEFINE_STATIC_KEY_FALSE(switch_mm_always_ibpb);
 
 /* Control IBPB on vCPU load */
 DEFINE_STATIC_KEY_FALSE(switch_vcpu_ibpb);
-EXPORT_SYMBOL_GPL(switch_vcpu_ibpb);
+EXPORT_SYMBOL_GPL_FOR_KVM(switch_vcpu_ibpb);
 
 /* Control CPU buffer clear before idling (halt, mwait) */
 DEFINE_STATIC_KEY_FALSE(cpu_buf_idle_clear);
@@ -188,7 +189,7 @@ DEFINE_STATIC_KEY_FALSE(switch_mm_cond_l1d_flush);
  * mitigation is required.
  */
 DEFINE_STATIC_KEY_FALSE(cpu_buf_vm_clear);
-EXPORT_SYMBOL_GPL(cpu_buf_vm_clear);
+EXPORT_SYMBOL_GPL_FOR_KVM(cpu_buf_vm_clear);
 
 void __init cpu_select_mitigations(void)
 {
@@ -318,7 +319,7 @@ x86_virt_spec_ctrl(u64 guest_virt_spec_ctrl, bool setguest)
 		speculation_ctrl_update(tif);
 	}
 }
-EXPORT_SYMBOL_GPL(x86_virt_spec_ctrl);
+EXPORT_SYMBOL_GPL_FOR_KVM(x86_virt_spec_ctrl);
 
 static void x86_amd_ssb_disable(void)
 {
@@ -904,7 +905,7 @@ bool gds_ucode_mitigated(void)
 	return (gds_mitigation == GDS_MITIGATION_FULL ||
 		gds_mitigation == GDS_MITIGATION_FULL_LOCKED);
 }
-EXPORT_SYMBOL_GPL(gds_ucode_mitigated);
+EXPORT_SYMBOL_GPL_FOR_KVM(gds_ucode_mitigated);
 
 void update_gds_msr(void)
 {
@@ -2806,7 +2807,7 @@ void x86_spec_ctrl_setup_ap(void)
 }
 
 bool itlb_multihit_kvm_mitigation;
-EXPORT_SYMBOL_GPL(itlb_multihit_kvm_mitigation);
+EXPORT_SYMBOL_GPL_FOR_KVM(itlb_multihit_kvm_mitigation);
 
 #undef pr_fmt
 #define pr_fmt(fmt)	"L1TF: " fmt
@@ -2814,11 +2815,9 @@ EXPORT_SYMBOL_GPL(itlb_multihit_kvm_mitigation);
 /* Default mitigation for L1TF-affected CPUs */
 enum l1tf_mitigations l1tf_mitigation __ro_after_init =
 	IS_ENABLED(CONFIG_MITIGATION_L1TF) ? L1TF_MITIGATION_AUTO : L1TF_MITIGATION_OFF;
-#if IS_ENABLED(CONFIG_KVM_INTEL)
-EXPORT_SYMBOL_GPL(l1tf_mitigation);
-#endif
+EXPORT_SYMBOL_GPL_FOR_KVM(l1tf_mitigation);
 enum vmx_l1d_flush_state l1tf_vmx_mitigation = VMENTER_L1D_FLUSH_AUTO;
-EXPORT_SYMBOL_GPL(l1tf_vmx_mitigation);
+EXPORT_SYMBOL_GPL_FOR_KVM(l1tf_vmx_mitigation);
 
 /*
  * These CPUs all support 44bits physical address space internally in the
diff --git a/arch/x86/kernel/cpu/bus_lock.c b/arch/x86/kernel/cpu/bus_lock.c
index 981f8b1f0792..90fe42911432 100644
--- a/arch/x86/kernel/cpu/bus_lock.c
+++ b/arch/x86/kernel/cpu/bus_lock.c
@@ -6,6 +6,7 @@
 #include <linux/workqueue.h>
 #include <linux/delay.h>
 #include <linux/cpuhotplug.h>
+#include <linux/kvm_types.h>
 #include <asm/cpu_device_id.h>
 #include <asm/cmdline.h>
 #include <asm/traps.h>
@@ -289,7 +290,7 @@ bool handle_guest_split_lock(unsigned long ip)
 	force_sig_fault(SIGBUS, BUS_ADRALN, NULL);
 	return false;
 }
-EXPORT_SYMBOL_GPL(handle_guest_split_lock);
+EXPORT_SYMBOL_GPL_FOR_KVM(handle_guest_split_lock);
 
 void bus_lock_init(void)
 {
diff --git a/arch/x86/kernel/cpu/common.c b/arch/x86/kernel/cpu/common.c
index fb50c1dd53ef..72f5c32d0e64 100644
--- a/arch/x86/kernel/cpu/common.c
+++ b/arch/x86/kernel/cpu/common.c
@@ -7,6 +7,7 @@
 #include <linux/bitops.h>
 #include <linux/kernel.h>
 #include <linux/export.h>
+#include <linux/kvm_types.h>
 #include <linux/percpu.h>
 #include <linux/string.h>
 #include <linux/ctype.h>
@@ -459,14 +460,14 @@ void cr4_update_irqsoff(unsigned long set, unsigned long clear)
 		__write_cr4(newval);
 	}
 }
-EXPORT_SYMBOL(cr4_update_irqsoff);
+EXPORT_SYMBOL_GPL_FOR_KVM(cr4_update_irqsoff);
 
 /* Read the CR4 shadow. */
 unsigned long cr4_read_shadow(void)
 {
 	return this_cpu_read(cpu_tlbstate.cr4);
 }
-EXPORT_SYMBOL_GPL(cr4_read_shadow);
+EXPORT_SYMBOL_GPL_FOR_KVM(cr4_read_shadow);
 
 void cr4_init(void)
 {
@@ -721,7 +722,7 @@ void load_direct_gdt(int cpu)
 	gdt_descr.size = GDT_SIZE - 1;
 	load_gdt(&gdt_descr);
 }
-EXPORT_SYMBOL_GPL(load_direct_gdt);
+EXPORT_SYMBOL_GPL_FOR_KVM(load_direct_gdt);
 
 /* Load a fixmap remapping of the per-cpu GDT */
 void load_fixmap_gdt(int cpu)
diff --git a/arch/x86/kernel/cpu/sgx/main.c b/arch/x86/kernel/cpu/sgx/main.c
index 2de01b379aa3..c8da7984d9d8 100644
--- a/arch/x86/kernel/cpu/sgx/main.c
+++ b/arch/x86/kernel/cpu/sgx/main.c
@@ -5,6 +5,7 @@
 #include <linux/freezer.h>
 #include <linux/highmem.h>
 #include <linux/kthread.h>
+#include <linux/kvm_types.h>
 #include <linux/miscdevice.h>
 #include <linux/node.h>
 #include <linux/pagemap.h>
@@ -915,7 +916,7 @@ int sgx_set_attribute(unsigned long *allowed_attributes,
 	*allowed_attributes |= SGX_ATTR_PROVISIONKEY;
 	return 0;
 }
-EXPORT_SYMBOL_GPL(sgx_set_attribute);
+EXPORT_SYMBOL_GPL_FOR_KVM(sgx_set_attribute);
 
 static int __init sgx_init(void)
 {
diff --git a/arch/x86/kernel/cpu/sgx/virt.c b/arch/x86/kernel/cpu/sgx/virt.c
index 7aaa3652e31d..1c8318f1004a 100644
--- a/arch/x86/kernel/cpu/sgx/virt.c
+++ b/arch/x86/kernel/cpu/sgx/virt.c
@@ -5,6 +5,7 @@
  * Copyright(c) 2021 Intel Corporation.
  */
 
+#include <linux/kvm_types.h>
 #include <linux/miscdevice.h>
 #include <linux/mm.h>
 #include <linux/mman.h>
@@ -363,7 +364,7 @@ int sgx_virt_ecreate(struct sgx_pageinfo *pageinfo, void __user *secs,
 	WARN_ON_ONCE(ret);
 	return 0;
 }
-EXPORT_SYMBOL_GPL(sgx_virt_ecreate);
+EXPORT_SYMBOL_GPL_FOR_KVM(sgx_virt_ecreate);
 
 static int __sgx_virt_einit(void __user *sigstruct, void __user *token,
 			    void __user *secs)
@@ -432,4 +433,4 @@ int sgx_virt_einit(void __user *sigstruct, void __user *token,
 
 	return ret;
 }
-EXPORT_SYMBOL_GPL(sgx_virt_einit);
+EXPORT_SYMBOL_GPL_FOR_KVM(sgx_virt_einit);
diff --git a/arch/x86/kernel/e820.c b/arch/x86/kernel/e820.c
index c3acbd26408b..b06be3af86c8 100644
--- a/arch/x86/kernel/e820.c
+++ b/arch/x86/kernel/e820.c
@@ -16,6 +16,7 @@
 #include <linux/firmware-map.h>
 #include <linux/sort.h>
 #include <linux/memory_hotplug.h>
+#include <linux/kvm_types.h>
 
 #include <asm/e820/api.h>
 #include <asm/setup.h>
@@ -95,7 +96,7 @@ bool e820__mapped_raw_any(u64 start, u64 end, enum e820_type type)
 {
 	return _e820__mapped_any(e820_table_firmware, start, end, type);
 }
-EXPORT_SYMBOL_GPL(e820__mapped_raw_any);
+EXPORT_SYMBOL_GPL_FOR_KVM(e820__mapped_raw_any);
 
 bool e820__mapped_any(u64 start, u64 end, enum e820_type type)
 {
diff --git a/arch/x86/kernel/fpu/core.c b/arch/x86/kernel/fpu/core.c
index ea138583dd92..94346f59f7d4 100644
--- a/arch/x86/kernel/fpu/core.c
+++ b/arch/x86/kernel/fpu/core.c
@@ -18,6 +18,7 @@
 #include <uapi/asm/kvm.h>
 
 #include <linux/hardirq.h>
+#include <linux/kvm_types.h>
 #include <linux/pkeys.h>
 #include <linux/vmalloc.h>
 
@@ -273,7 +274,7 @@ bool fpu_alloc_guest_fpstate(struct fpu_guest *gfpu)
 
 	return true;
 }
-EXPORT_SYMBOL_GPL(fpu_alloc_guest_fpstate);
+EXPORT_SYMBOL_GPL_FOR_KVM(fpu_alloc_guest_fpstate);
 
 void fpu_free_guest_fpstate(struct fpu_guest *gfpu)
 {
@@ -288,7 +289,7 @@ void fpu_free_guest_fpstate(struct fpu_guest *gfpu)
 	gfpu->fpstate = NULL;
 	vfree(fpstate);
 }
-EXPORT_SYMBOL_GPL(fpu_free_guest_fpstate);
+EXPORT_SYMBOL_GPL_FOR_KVM(fpu_free_guest_fpstate);
 
 /*
   * fpu_enable_guest_xfd_features - Check xfeatures against guest perm and enable
@@ -310,7 +311,7 @@ int fpu_enable_guest_xfd_features(struct fpu_guest *guest_fpu, u64 xfeatures)
 
 	return __xfd_enable_feature(xfeatures, guest_fpu);
 }
-EXPORT_SYMBOL_GPL(fpu_enable_guest_xfd_features);
+EXPORT_SYMBOL_GPL_FOR_KVM(fpu_enable_guest_xfd_features);
 
 #ifdef CONFIG_X86_64
 void fpu_update_guest_xfd(struct fpu_guest *guest_fpu, u64 xfd)
@@ -321,7 +322,7 @@ void fpu_update_guest_xfd(struct fpu_guest *guest_fpu, u64 xfd)
 		xfd_update_state(guest_fpu->fpstate);
 	fpregs_unlock();
 }
-EXPORT_SYMBOL_GPL(fpu_update_guest_xfd);
+EXPORT_SYMBOL_GPL_FOR_KVM(fpu_update_guest_xfd);
 
 /**
  * fpu_sync_guest_vmexit_xfd_state - Synchronize XFD MSR and software state
@@ -345,7 +346,7 @@ void fpu_sync_guest_vmexit_xfd_state(void)
 		__this_cpu_write(xfd_state, fpstate->xfd);
 	}
 }
-EXPORT_SYMBOL_GPL(fpu_sync_guest_vmexit_xfd_state);
+EXPORT_SYMBOL_GPL_FOR_KVM(fpu_sync_guest_vmexit_xfd_state);
 #endif /* CONFIG_X86_64 */
 
 int fpu_swap_kvm_fpstate(struct fpu_guest *guest_fpu, bool enter_guest)
@@ -387,7 +388,7 @@ int fpu_swap_kvm_fpstate(struct fpu_guest *guest_fpu, bool enter_guest)
 	fpregs_unlock();
 	return 0;
 }
-EXPORT_SYMBOL_GPL(fpu_swap_kvm_fpstate);
+EXPORT_SYMBOL_GPL_FOR_KVM(fpu_swap_kvm_fpstate);
 
 void fpu_copy_guest_fpstate_to_uabi(struct fpu_guest *gfpu, void *buf,
 				    unsigned int size, u64 xfeatures, u32 pkru)
@@ -406,7 +407,7 @@ void fpu_copy_guest_fpstate_to_uabi(struct fpu_guest *gfpu, void *buf,
 		ustate->xsave.header.xfeatures = XFEATURE_MASK_FPSSE;
 	}
 }
-EXPORT_SYMBOL_GPL(fpu_copy_guest_fpstate_to_uabi);
+EXPORT_SYMBOL_GPL_FOR_KVM(fpu_copy_guest_fpstate_to_uabi);
 
 int fpu_copy_uabi_to_guest_fpstate(struct fpu_guest *gfpu, const void *buf,
 				   u64 xcr0, u32 *vpkru)
@@ -436,7 +437,7 @@ int fpu_copy_uabi_to_guest_fpstate(struct fpu_guest *gfpu, const void *buf,
 
 	return copy_uabi_from_kernel_to_xstate(kstate, ustate, vpkru);
 }
-EXPORT_SYMBOL_GPL(fpu_copy_uabi_to_guest_fpstate);
+EXPORT_SYMBOL_GPL_FOR_KVM(fpu_copy_uabi_to_guest_fpstate);
 #endif /* CONFIG_KVM */
 
 void kernel_fpu_begin_mask(unsigned int kfpu_mask)
@@ -829,7 +830,7 @@ void switch_fpu_return(void)
 
 	fpregs_restore_userregs();
 }
-EXPORT_SYMBOL_GPL(switch_fpu_return);
+EXPORT_SYMBOL_GPL_FOR_KVM(switch_fpu_return);
 
 void fpregs_lock_and_load(void)
 {
@@ -864,7 +865,7 @@ void fpregs_assert_state_consistent(void)
 
 	WARN_ON_FPU(!fpregs_state_valid(fpu, smp_processor_id()));
 }
-EXPORT_SYMBOL_GPL(fpregs_assert_state_consistent);
+EXPORT_SYMBOL_GPL_FOR_KVM(fpregs_assert_state_consistent);
 #endif
 
 void fpregs_mark_activate(void)
diff --git a/arch/x86/kernel/fpu/xstate.c b/arch/x86/kernel/fpu/xstate.c
index 9aa9ac8399ae..a3bfa0613e99 100644
--- a/arch/x86/kernel/fpu/xstate.c
+++ b/arch/x86/kernel/fpu/xstate.c
@@ -8,6 +8,7 @@
 #include <linux/compat.h>
 #include <linux/cpu.h>
 #include <linux/mman.h>
+#include <linux/kvm_types.h>
 #include <linux/nospec.h>
 #include <linux/pkeys.h>
 #include <linux/seq_file.h>
@@ -1032,7 +1033,7 @@ void *get_xsave_addr(struct xregs_state *xsave, int xfeature_nr)
 
 	return __raw_xsave_addr(xsave, xfeature_nr);
 }
-EXPORT_SYMBOL_GPL(get_xsave_addr);
+EXPORT_SYMBOL_GPL_FOR_KVM(get_xsave_addr);
 
 /*
  * Given an xstate feature nr, calculate where in the xsave buffer the state is.
@@ -1456,7 +1457,7 @@ void fpstate_clear_xstate_component(struct fpstate *fpstate, unsigned int xfeatu
 	if (addr)
 		memset(addr, 0, xstate_sizes[xfeature]);
 }
-EXPORT_SYMBOL_GPL(fpstate_clear_xstate_component);
+EXPORT_SYMBOL_GPL_FOR_KVM(fpstate_clear_xstate_component);
 #endif
 
 #ifdef CONFIG_X86_64
@@ -1792,7 +1793,7 @@ u64 xstate_get_guest_group_perm(void)
 {
 	return xstate_get_group_perm(true);
 }
-EXPORT_SYMBOL_GPL(xstate_get_guest_group_perm);
+EXPORT_SYMBOL_GPL_FOR_KVM(xstate_get_guest_group_perm);
 
 /**
  * fpu_xstate_prctl - xstate permission operations
diff --git a/arch/x86/kernel/hw_breakpoint.c b/arch/x86/kernel/hw_breakpoint.c
index b01644c949b2..a37f12a978e4 100644
--- a/arch/x86/kernel/hw_breakpoint.c
+++ b/arch/x86/kernel/hw_breakpoint.c
@@ -24,6 +24,7 @@
 #include <linux/percpu.h>
 #include <linux/kdebug.h>
 #include <linux/kernel.h>
+#include <linux/kvm_types.h>
 #include <linux/export.h>
 #include <linux/sched.h>
 #include <linux/smp.h>
@@ -489,7 +490,7 @@ void hw_breakpoint_restore(void)
 	set_debugreg(DR6_RESERVED, 6);
 	set_debugreg(__this_cpu_read(cpu_dr7), 7);
 }
-EXPORT_SYMBOL_GPL(hw_breakpoint_restore);
+EXPORT_SYMBOL_GPL_FOR_KVM(hw_breakpoint_restore);
 
 /*
  * Handle debug exception notifications.
diff --git a/arch/x86/kernel/irq.c b/arch/x86/kernel/irq.c
index 9ed29ff10e59..6aecd1a7524d 100644
--- a/arch/x86/kernel/irq.c
+++ b/arch/x86/kernel/irq.c
@@ -12,6 +12,7 @@
 #include <linux/delay.h>
 #include <linux/export.h>
 #include <linux/irq.h>
+#include <linux/kvm_types.h>
 
 #include <asm/irq_stack.h>
 #include <asm/apic.h>
@@ -328,7 +329,7 @@ void kvm_set_posted_intr_wakeup_handler(void (*handler)(void))
 		synchronize_rcu();
 	}
 }
-EXPORT_SYMBOL_GPL(kvm_set_posted_intr_wakeup_handler);
+EXPORT_SYMBOL_GPL_FOR_KVM(kvm_set_posted_intr_wakeup_handler);
 
 /*
  * Handler for POSTED_INTERRUPT_VECTOR.
diff --git a/arch/x86/kernel/kvm.c b/arch/x86/kernel/kvm.c
index 921c1c783bc1..d70e1b5a255c 100644
--- a/arch/x86/kernel/kvm.c
+++ b/arch/x86/kernel/kvm.c
@@ -29,6 +29,7 @@
 #include <linux/syscore_ops.h>
 #include <linux/cc_platform.h>
 #include <linux/efi.h>
+#include <linux/kvm_types.h>
 #include <asm/timer.h>
 #include <asm/cpu.h>
 #include <asm/traps.h>
@@ -162,7 +163,7 @@ void kvm_async_pf_task_wait_schedule(u32 token)
 	}
 	finish_swait(&n.wq, &wait);
 }
-EXPORT_SYMBOL_GPL(kvm_async_pf_task_wait_schedule);
+EXPORT_SYMBOL_GPL_FOR_KVM(kvm_async_pf_task_wait_schedule);
 
 static void apf_task_wake_one(struct kvm_task_sleep_node *n)
 {
@@ -254,7 +255,7 @@ noinstr u32 kvm_read_and_reset_apf_flags(void)
 
 	return flags;
 }
-EXPORT_SYMBOL_GPL(kvm_read_and_reset_apf_flags);
+EXPORT_SYMBOL_GPL_FOR_KVM(kvm_read_and_reset_apf_flags);
 
 noinstr bool __kvm_handle_async_pf(struct pt_regs *regs, u32 token)
 {
diff --git a/arch/x86/kernel/nmi.c b/arch/x86/kernel/nmi.c
index be93ec7255bf..5b6874554ab1 100644
--- a/arch/x86/kernel/nmi.c
+++ b/arch/x86/kernel/nmi.c
@@ -24,6 +24,7 @@
 #include <linux/export.h>
 #include <linux/atomic.h>
 #include <linux/sched/clock.h>
+#include <linux/kvm_types.h>
 
 #include <asm/cpu_entry_area.h>
 #include <asm/traps.h>
@@ -613,9 +614,7 @@ DEFINE_IDTENTRY_RAW(exc_nmi_kvm_vmx)
 {
 	exc_nmi(regs);
 }
-#if IS_MODULE(CONFIG_KVM_INTEL)
-EXPORT_SYMBOL_GPL(asm_exc_nmi_kvm_vmx);
-#endif
+EXPORT_SYMBOL_GPL_FOR_KVM(asm_exc_nmi_kvm_vmx);
 #endif
 
 #ifdef CONFIG_NMI_CHECK_CPU
diff --git a/arch/x86/kernel/process_64.c b/arch/x86/kernel/process_64.c
index b972bf72fb8b..14f2bae0042d 100644
--- a/arch/x86/kernel/process_64.c
+++ b/arch/x86/kernel/process_64.c
@@ -30,6 +30,7 @@
 #include <linux/interrupt.h>
 #include <linux/delay.h>
 #include <linux/export.h>
+#include <linux/kvm_types.h>
 #include <linux/ptrace.h>
 #include <linux/notifier.h>
 #include <linux/kprobes.h>
@@ -303,9 +304,7 @@ void current_save_fsgs(void)
 	save_fsgs(current);
 	local_irq_restore(flags);
 }
-#if IS_ENABLED(CONFIG_KVM)
-EXPORT_SYMBOL_GPL(current_save_fsgs);
-#endif
+EXPORT_SYMBOL_GPL_FOR_KVM(current_save_fsgs);
 
 static __always_inline void loadseg(enum which_selector which,
 				    unsigned short sel)
diff --git a/arch/x86/kernel/reboot.c b/arch/x86/kernel/reboot.c
index 964f6b0a3d68..e550515b1fc1 100644
--- a/arch/x86/kernel/reboot.c
+++ b/arch/x86/kernel/reboot.c
@@ -13,6 +13,7 @@
 #include <linux/objtool.h>
 #include <linux/pgtable.h>
 #include <linux/kexec.h>
+#include <linux/kvm_types.h>
 #include <acpi/reboot.h>
 #include <asm/io.h>
 #include <asm/apic.h>
@@ -541,7 +542,7 @@ void cpu_emergency_register_virt_callback(cpu_emergency_virt_cb *callback)
 
 	rcu_assign_pointer(cpu_emergency_virt_callback, callback);
 }
-EXPORT_SYMBOL_GPL(cpu_emergency_register_virt_callback);
+EXPORT_SYMBOL_GPL_FOR_KVM(cpu_emergency_register_virt_callback);
 
 void cpu_emergency_unregister_virt_callback(cpu_emergency_virt_cb *callback)
 {
@@ -551,7 +552,7 @@ void cpu_emergency_unregister_virt_callback(cpu_emergency_virt_cb *callback)
 	rcu_assign_pointer(cpu_emergency_virt_callback, NULL);
 	synchronize_rcu();
 }
-EXPORT_SYMBOL_GPL(cpu_emergency_unregister_virt_callback);
+EXPORT_SYMBOL_GPL_FOR_KVM(cpu_emergency_unregister_virt_callback);
 
 /*
  * Disable virtualization, i.e. VMX or SVM, to ensure INIT is recognized during
diff --git a/arch/x86/kernel/tsc.c b/arch/x86/kernel/tsc.c
index 87e749106dda..7d3e13e14eab 100644
--- a/arch/x86/kernel/tsc.c
+++ b/arch/x86/kernel/tsc.c
@@ -11,6 +11,7 @@
 #include <linux/cpufreq.h>
 #include <linux/delay.h>
 #include <linux/clocksource.h>
+#include <linux/kvm_types.h>
 #include <linux/percpu.h>
 #include <linux/timex.h>
 #include <linux/static_key.h>
diff --git a/arch/x86/lib/cache-smp.c b/arch/x86/lib/cache-smp.c
index c5c60d07308c..23bab469c6c6 100644
--- a/arch/x86/lib/cache-smp.c
+++ b/arch/x86/lib/cache-smp.c
@@ -2,6 +2,7 @@
 #include <asm/paravirt.h>
 #include <linux/smp.h>
 #include <linux/export.h>
+#include <linux/kvm_types.h>
 
 static void __wbinvd(void *dummy)
 {
@@ -12,7 +13,7 @@ void wbinvd_on_cpu(int cpu)
 {
 	smp_call_function_single(cpu, __wbinvd, NULL, 1);
 }
-EXPORT_SYMBOL(wbinvd_on_cpu);
+EXPORT_SYMBOL_GPL_FOR_KVM(wbinvd_on_cpu);
 
 void wbinvd_on_all_cpus(void)
 {
@@ -24,7 +25,7 @@ void wbinvd_on_cpus_mask(struct cpumask *cpus)
 {
 	on_each_cpu_mask(cpus, __wbinvd, NULL, 1);
 }
-EXPORT_SYMBOL_GPL(wbinvd_on_cpus_mask);
+EXPORT_SYMBOL_GPL_FOR_KVM(wbinvd_on_cpus_mask);
 
 static void __wbnoinvd(void *dummy)
 {
@@ -35,10 +36,10 @@ void wbnoinvd_on_all_cpus(void)
 {
 	on_each_cpu(__wbnoinvd, NULL, 1);
 }
-EXPORT_SYMBOL_GPL(wbnoinvd_on_all_cpus);
+EXPORT_SYMBOL_GPL_FOR_KVM(wbnoinvd_on_all_cpus);
 
 void wbnoinvd_on_cpus_mask(struct cpumask *cpus)
 {
 	on_each_cpu_mask(cpus, __wbnoinvd, NULL, 1);
 }
-EXPORT_SYMBOL_GPL(wbnoinvd_on_cpus_mask);
+EXPORT_SYMBOL_GPL_FOR_KVM(wbnoinvd_on_cpus_mask);
diff --git a/arch/x86/lib/msr.c b/arch/x86/lib/msr.c
index 4ef7c6dcbea6..0544a8af9f5b 100644
--- a/arch/x86/lib/msr.c
+++ b/arch/x86/lib/msr.c
@@ -1,5 +1,6 @@
 // SPDX-License-Identifier: GPL-2.0
 #include <linux/export.h>
+#include <linux/kvm_types.h>
 #include <linux/percpu.h>
 #include <linux/preempt.h>
 #include <asm/msr.h>
@@ -103,7 +104,7 @@ int msr_set_bit(u32 msr, u8 bit)
 {
 	return __flip_bit(msr, bit, true);
 }
-EXPORT_SYMBOL_GPL(msr_set_bit);
+EXPORT_SYMBOL_GPL_FOR_KVM(msr_set_bit);
 
 /**
  * msr_clear_bit - Clear @bit in a MSR @msr.
@@ -119,7 +120,7 @@ int msr_clear_bit(u32 msr, u8 bit)
 {
 	return __flip_bit(msr, bit, false);
 }
-EXPORT_SYMBOL_GPL(msr_clear_bit);
+EXPORT_SYMBOL_GPL_FOR_KVM(msr_clear_bit);
 
 #ifdef CONFIG_TRACEPOINTS
 void do_trace_write_msr(u32 msr, u64 val, int failed)
diff --git a/arch/x86/mm/pat/memtype.c b/arch/x86/mm/pat/memtype.c
index 2e7923844afe..0829d054dbf4 100644
--- a/arch/x86/mm/pat/memtype.c
+++ b/arch/x86/mm/pat/memtype.c
@@ -43,6 +43,7 @@
 #include <linux/highmem.h>
 #include <linux/fs.h>
 #include <linux/rbtree.h>
+#include <linux/kvm_types.h>
 
 #include <asm/cpu_device_id.h>
 #include <asm/cacheflush.h>
@@ -698,7 +699,7 @@ bool pat_pfn_immune_to_uc_mtrr(unsigned long pfn)
 	       cm == _PAGE_CACHE_MODE_UC_MINUS ||
 	       cm == _PAGE_CACHE_MODE_WC;
 }
-EXPORT_SYMBOL_GPL(pat_pfn_immune_to_uc_mtrr);
+EXPORT_SYMBOL_GPL_FOR_KVM(pat_pfn_immune_to_uc_mtrr);
 
 /**
  * memtype_reserve_io - Request a memory type mapping for a region of memory
diff --git a/arch/x86/mm/tlb.c b/arch/x86/mm/tlb.c
index 39f80111e6f1..33dd1c7a8b67 100644
--- a/arch/x86/mm/tlb.c
+++ b/arch/x86/mm/tlb.c
@@ -12,6 +12,7 @@
 #include <linux/task_work.h>
 #include <linux/mmu_notifier.h>
 #include <linux/mmu_context.h>
+#include <linux/kvm_types.h>
 
 #include <asm/tlbflush.h>
 #include <asm/mmu_context.h>
@@ -1562,7 +1563,7 @@ unsigned long __get_current_cr3_fast(void)
 	VM_BUG_ON(cr3 != __read_cr3());
 	return cr3;
 }
-EXPORT_SYMBOL_GPL(__get_current_cr3_fast);
+EXPORT_SYMBOL_GPL_FOR_KVM(__get_current_cr3_fast);
 
 /*
  * Flush one page in the kernel mapping
@@ -1703,7 +1704,7 @@ void __flush_tlb_all(void)
 		flush_tlb_local();
 	}
 }
-EXPORT_SYMBOL_GPL(__flush_tlb_all);
+EXPORT_SYMBOL_GPL_FOR_KVM(__flush_tlb_all);
 
 void arch_tlbbatch_flush(struct arch_tlbflush_unmap_batch *batch)
 {
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index c7a9a087ccaf..426fefdd2b60 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -29,6 +29,7 @@
 #include <linux/acpi.h>
 #include <linux/suspend.h>
 #include <linux/idr.h>
+#include <linux/kvm_types.h>
 #include <asm/page.h>
 #include <asm/special_insns.h>
 #include <asm/msr-index.h>
@@ -181,7 +182,7 @@ int tdx_cpu_enable(void)
 
 	return 0;
 }
-EXPORT_SYMBOL_GPL(tdx_cpu_enable);
+EXPORT_SYMBOL_GPL_FOR_KVM(tdx_cpu_enable);
 
 /*
  * Add a memory region as a TDX memory block.  The caller must make sure
@@ -1214,7 +1215,7 @@ int tdx_enable(void)
 
 	return ret;
 }
-EXPORT_SYMBOL_GPL(tdx_enable);
+EXPORT_SYMBOL_GPL_FOR_KVM(tdx_enable);
 
 static bool is_pamt_page(unsigned long phys)
 {
@@ -1475,13 +1476,13 @@ const struct tdx_sys_info *tdx_get_sysinfo(void)
 
 	return p;
 }
-EXPORT_SYMBOL_GPL(tdx_get_sysinfo);
+EXPORT_SYMBOL_GPL_FOR_KVM(tdx_get_sysinfo);
 
 u32 tdx_get_nr_guest_keyids(void)
 {
 	return tdx_nr_guest_keyids;
 }
-EXPORT_SYMBOL_GPL(tdx_get_nr_guest_keyids);
+EXPORT_SYMBOL_GPL_FOR_KVM(tdx_get_nr_guest_keyids);
 
 int tdx_guest_keyid_alloc(void)
 {
@@ -1489,13 +1490,13 @@ int tdx_guest_keyid_alloc(void)
 			       tdx_guest_keyid_start + tdx_nr_guest_keyids - 1,
 			       GFP_KERNEL);
 }
-EXPORT_SYMBOL_GPL(tdx_guest_keyid_alloc);
+EXPORT_SYMBOL_GPL_FOR_KVM(tdx_guest_keyid_alloc);
 
 void tdx_guest_keyid_free(unsigned int keyid)
 {
 	ida_free(&tdx_guest_keyid_pool, keyid);
 }
-EXPORT_SYMBOL_GPL(tdx_guest_keyid_free);
+EXPORT_SYMBOL_GPL_FOR_KVM(tdx_guest_keyid_free);
 
 static inline u64 tdx_tdr_pa(struct tdx_td *td)
 {
@@ -1524,7 +1525,7 @@ noinstr __flatten u64 tdh_vp_enter(struct tdx_vp *td, struct tdx_module_args *ar
 
 	return __seamcall_saved_ret(TDH_VP_ENTER, args);
 }
-EXPORT_SYMBOL_GPL(tdh_vp_enter);
+EXPORT_SYMBOL_GPL_FOR_KVM(tdh_vp_enter);
 
 u64 tdh_mng_addcx(struct tdx_td *td, struct page *tdcs_page)
 {
@@ -1536,7 +1537,7 @@ u64 tdh_mng_addcx(struct tdx_td *td, struct page *tdcs_page)
 	tdx_clflush_page(tdcs_page);
 	return seamcall(TDH_MNG_ADDCX, &args);
 }
-EXPORT_SYMBOL_GPL(tdh_mng_addcx);
+EXPORT_SYMBOL_GPL_FOR_KVM(tdh_mng_addcx);
 
 u64 tdh_mem_page_add(struct tdx_td *td, u64 gpa, struct page *page, struct page *source, u64 *ext_err1, u64 *ext_err2)
 {
@@ -1556,7 +1557,7 @@ u64 tdh_mem_page_add(struct tdx_td *td, u64 gpa, struct page *page, struct page
 
 	return ret;
 }
-EXPORT_SYMBOL_GPL(tdh_mem_page_add);
+EXPORT_SYMBOL_GPL_FOR_KVM(tdh_mem_page_add);
 
 u64 tdh_mem_sept_add(struct tdx_td *td, u64 gpa, int level, struct page *page, u64 *ext_err1, u64 *ext_err2)
 {
@@ -1575,7 +1576,7 @@ u64 tdh_mem_sept_add(struct tdx_td *td, u64 gpa, int level, struct page *page, u
 
 	return ret;
 }
-EXPORT_SYMBOL_GPL(tdh_mem_sept_add);
+EXPORT_SYMBOL_GPL_FOR_KVM(tdh_mem_sept_add);
 
 u64 tdh_vp_addcx(struct tdx_vp *vp, struct page *tdcx_page)
 {
@@ -1587,7 +1588,7 @@ u64 tdh_vp_addcx(struct tdx_vp *vp, struct page *tdcx_page)
 	tdx_clflush_page(tdcx_page);
 	return seamcall(TDH_VP_ADDCX, &args);
 }
-EXPORT_SYMBOL_GPL(tdh_vp_addcx);
+EXPORT_SYMBOL_GPL_FOR_KVM(tdh_vp_addcx);
 
 u64 tdh_mem_page_aug(struct tdx_td *td, u64 gpa, int level, struct page *page, u64 *ext_err1, u64 *ext_err2)
 {
@@ -1606,7 +1607,7 @@ u64 tdh_mem_page_aug(struct tdx_td *td, u64 gpa, int level, struct page *page, u
 
 	return ret;
 }
-EXPORT_SYMBOL_GPL(tdh_mem_page_aug);
+EXPORT_SYMBOL_GPL_FOR_KVM(tdh_mem_page_aug);
 
 u64 tdh_mem_range_block(struct tdx_td *td, u64 gpa, int level, u64 *ext_err1, u64 *ext_err2)
 {
@@ -1623,7 +1624,7 @@ u64 tdh_mem_range_block(struct tdx_td *td, u64 gpa, int level, u64 *ext_err1, u6
 
 	return ret;
 }
-EXPORT_SYMBOL_GPL(tdh_mem_range_block);
+EXPORT_SYMBOL_GPL_FOR_KVM(tdh_mem_range_block);
 
 u64 tdh_mng_key_config(struct tdx_td *td)
 {
@@ -1633,7 +1634,7 @@ u64 tdh_mng_key_config(struct tdx_td *td)
 
 	return seamcall(TDH_MNG_KEY_CONFIG, &args);
 }
-EXPORT_SYMBOL_GPL(tdh_mng_key_config);
+EXPORT_SYMBOL_GPL_FOR_KVM(tdh_mng_key_config);
 
 u64 tdh_mng_create(struct tdx_td *td, u16 hkid)
 {
@@ -1645,7 +1646,7 @@ u64 tdh_mng_create(struct tdx_td *td, u16 hkid)
 	tdx_clflush_page(td->tdr_page);
 	return seamcall(TDH_MNG_CREATE, &args);
 }
-EXPORT_SYMBOL_GPL(tdh_mng_create);
+EXPORT_SYMBOL_GPL_FOR_KVM(tdh_mng_create);
 
 u64 tdh_vp_create(struct tdx_td *td, struct tdx_vp *vp)
 {
@@ -1657,7 +1658,7 @@ u64 tdh_vp_create(struct tdx_td *td, struct tdx_vp *vp)
 	tdx_clflush_page(vp->tdvpr_page);
 	return seamcall(TDH_VP_CREATE, &args);
 }
-EXPORT_SYMBOL_GPL(tdh_vp_create);
+EXPORT_SYMBOL_GPL_FOR_KVM(tdh_vp_create);
 
 u64 tdh_mng_rd(struct tdx_td *td, u64 field, u64 *data)
 {
@@ -1674,7 +1675,7 @@ u64 tdh_mng_rd(struct tdx_td *td, u64 field, u64 *data)
 
 	return ret;
 }
-EXPORT_SYMBOL_GPL(tdh_mng_rd);
+EXPORT_SYMBOL_GPL_FOR_KVM(tdh_mng_rd);
 
 u64 tdh_mr_extend(struct tdx_td *td, u64 gpa, u64 *ext_err1, u64 *ext_err2)
 {
@@ -1691,7 +1692,7 @@ u64 tdh_mr_extend(struct tdx_td *td, u64 gpa, u64 *ext_err1, u64 *ext_err2)
 
 	return ret;
 }
-EXPORT_SYMBOL_GPL(tdh_mr_extend);
+EXPORT_SYMBOL_GPL_FOR_KVM(tdh_mr_extend);
 
 u64 tdh_mr_finalize(struct tdx_td *td)
 {
@@ -1701,7 +1702,7 @@ u64 tdh_mr_finalize(struct tdx_td *td)
 
 	return seamcall(TDH_MR_FINALIZE, &args);
 }
-EXPORT_SYMBOL_GPL(tdh_mr_finalize);
+EXPORT_SYMBOL_GPL_FOR_KVM(tdh_mr_finalize);
 
 u64 tdh_vp_flush(struct tdx_vp *vp)
 {
@@ -1711,7 +1712,7 @@ u64 tdh_vp_flush(struct tdx_vp *vp)
 
 	return seamcall(TDH_VP_FLUSH, &args);
 }
-EXPORT_SYMBOL_GPL(tdh_vp_flush);
+EXPORT_SYMBOL_GPL_FOR_KVM(tdh_vp_flush);
 
 u64 tdh_mng_vpflushdone(struct tdx_td *td)
 {
@@ -1721,7 +1722,7 @@ u64 tdh_mng_vpflushdone(struct tdx_td *td)
 
 	return seamcall(TDH_MNG_VPFLUSHDONE, &args);
 }
-EXPORT_SYMBOL_GPL(tdh_mng_vpflushdone);
+EXPORT_SYMBOL_GPL_FOR_KVM(tdh_mng_vpflushdone);
 
 u64 tdh_mng_key_freeid(struct tdx_td *td)
 {
@@ -1731,7 +1732,7 @@ u64 tdh_mng_key_freeid(struct tdx_td *td)
 
 	return seamcall(TDH_MNG_KEY_FREEID, &args);
 }
-EXPORT_SYMBOL_GPL(tdh_mng_key_freeid);
+EXPORT_SYMBOL_GPL_FOR_KVM(tdh_mng_key_freeid);
 
 u64 tdh_mng_init(struct tdx_td *td, u64 td_params, u64 *extended_err)
 {
@@ -1747,7 +1748,7 @@ u64 tdh_mng_init(struct tdx_td *td, u64 td_params, u64 *extended_err)
 
 	return ret;
 }
-EXPORT_SYMBOL_GPL(tdh_mng_init);
+EXPORT_SYMBOL_GPL_FOR_KVM(tdh_mng_init);
 
 u64 tdh_vp_rd(struct tdx_vp *vp, u64 field, u64 *data)
 {
@@ -1764,7 +1765,7 @@ u64 tdh_vp_rd(struct tdx_vp *vp, u64 field, u64 *data)
 
 	return ret;
 }
-EXPORT_SYMBOL_GPL(tdh_vp_rd);
+EXPORT_SYMBOL_GPL_FOR_KVM(tdh_vp_rd);
 
 u64 tdh_vp_wr(struct tdx_vp *vp, u64 field, u64 data, u64 mask)
 {
@@ -1777,7 +1778,7 @@ u64 tdh_vp_wr(struct tdx_vp *vp, u64 field, u64 data, u64 mask)
 
 	return seamcall(TDH_VP_WR, &args);
 }
-EXPORT_SYMBOL_GPL(tdh_vp_wr);
+EXPORT_SYMBOL_GPL_FOR_KVM(tdh_vp_wr);
 
 u64 tdh_vp_init(struct tdx_vp *vp, u64 initial_rcx, u32 x2apicid)
 {
@@ -1790,7 +1791,7 @@ u64 tdh_vp_init(struct tdx_vp *vp, u64 initial_rcx, u32 x2apicid)
 	/* apicid requires version == 1. */
 	return seamcall(TDH_VP_INIT | (1ULL << TDX_VERSION_SHIFT), &args);
 }
-EXPORT_SYMBOL_GPL(tdh_vp_init);
+EXPORT_SYMBOL_GPL_FOR_KVM(tdh_vp_init);
 
 /*
  * TDX ABI defines output operands as PT, OWNER and SIZE. These are TDX defined fomats.
@@ -1812,7 +1813,7 @@ u64 tdh_phymem_page_reclaim(struct page *page, u64 *tdx_pt, u64 *tdx_owner, u64
 
 	return ret;
 }
-EXPORT_SYMBOL_GPL(tdh_phymem_page_reclaim);
+EXPORT_SYMBOL_GPL_FOR_KVM(tdh_phymem_page_reclaim);
 
 u64 tdh_mem_track(struct tdx_td *td)
 {
@@ -1822,7 +1823,7 @@ u64 tdh_mem_track(struct tdx_td *td)
 
 	return seamcall(TDH_MEM_TRACK, &args);
 }
-EXPORT_SYMBOL_GPL(tdh_mem_track);
+EXPORT_SYMBOL_GPL_FOR_KVM(tdh_mem_track);
 
 u64 tdh_mem_page_remove(struct tdx_td *td, u64 gpa, u64 level, u64 *ext_err1, u64 *ext_err2)
 {
@@ -1839,7 +1840,7 @@ u64 tdh_mem_page_remove(struct tdx_td *td, u64 gpa, u64 level, u64 *ext_err1, u6
 
 	return ret;
 }
-EXPORT_SYMBOL_GPL(tdh_mem_page_remove);
+EXPORT_SYMBOL_GPL_FOR_KVM(tdh_mem_page_remove);
 
 u64 tdh_phymem_cache_wb(bool resume)
 {
@@ -1849,7 +1850,7 @@ u64 tdh_phymem_cache_wb(bool resume)
 
 	return seamcall(TDH_PHYMEM_CACHE_WB, &args);
 }
-EXPORT_SYMBOL_GPL(tdh_phymem_cache_wb);
+EXPORT_SYMBOL_GPL_FOR_KVM(tdh_phymem_cache_wb);
 
 u64 tdh_phymem_page_wbinvd_tdr(struct tdx_td *td)
 {
@@ -1859,7 +1860,7 @@ u64 tdh_phymem_page_wbinvd_tdr(struct tdx_td *td)
 
 	return seamcall(TDH_PHYMEM_PAGE_WBINVD, &args);
 }
-EXPORT_SYMBOL_GPL(tdh_phymem_page_wbinvd_tdr);
+EXPORT_SYMBOL_GPL_FOR_KVM(tdh_phymem_page_wbinvd_tdr);
 
 u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, struct page *page)
 {
@@ -1869,4 +1870,4 @@ u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, struct page *page)
 
 	return seamcall(TDH_PHYMEM_PAGE_WBINVD, &args);
 }
-EXPORT_SYMBOL_GPL(tdh_phymem_page_wbinvd_hkid);
+EXPORT_SYMBOL_GPL_FOR_KVM(tdh_phymem_page_wbinvd_hkid);
diff --git a/include/linux/kvm_types.h b/include/linux/kvm_types.h
index 92a7051c1c9c..4df5a1c19612 100644
--- a/include/linux/kvm_types.h
+++ b/include/linux/kvm_types.h
@@ -11,8 +11,22 @@
 #ifdef KVM_SUB_MODULES
 #define EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(symbol) \
 	EXPORT_SYMBOL_GPL_FOR_MODULES(symbol, __stringify(KVM_SUB_MODULES))
+#define EXPORT_SYMBOL_GPL_FOR_KVM(symbol) \
+	EXPORT_SYMBOL_GPL_FOR_MODULES(symbol, "kvm," __stringify(KVM_SUB_MODULES))
 #else
 #define EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL(symbol)
+/*
+ * Allow architectures to provide a custom EXPORT_SYMBOL_GPL_FOR_KVM, but only
+ * if there are no submodules, e.g. to allow suppressing exports if KVM=m, but
+ * kvm.ko won't actually be built (due to lack of at least one submodule).
+ */
+#ifndef EXPORT_SYMBOL_GPL_FOR_KVM
+#if IS_MODULE(CONFIG_KVM)
+#define EXPORT_SYMBOL_GPL_FOR_KVM(symbol) EXPORT_SYMBOL_GPL_FOR_MODULES(symbol, "kvm")
+#else
+#define EXPORT_SYMBOL_GPL_FOR_KVM(symbol)
+#endif /* IS_MODULE(CONFIG_KVM) */
+#endif /* EXPORT_SYMBOL_GPL_FOR_KVM */
 #endif
 
 #ifndef __ASSEMBLER__

---

## [8] Huang, Kai — 2025-07-30
*Subject: Re: [PATCH 6/6] x86: Restrict KVM-induced symbol exports to KVM
 modules where obvious/possible*

On Tue, 2025-07-29 at 10:42 -0700, Sean Christopherson wrote:
> Extend KVM's export macro framework to provide EXPORT_SYMBOL_GPL_FOR_KVM(),
> and use the helper macro to export symbols for KVM throughout x86 if and

[...]

>  arch/x86/kernel/cpu/sgx/main.c     |  3 +-
>  arch/x86/kernel/cpu/sgx/virt.c     |  5 ++-

[...]

>  arch/x86/virt/vmx/tdx/tdx.c        | 65 +++++++++++++++---------------
>  include/linux/kvm_types.h          | 14 +++++++

[...]

> 
> --- a/include/linux/kvm_types.h

I was thinking to send out separate patches for SGX and TDX by just
changing to use EXPORT_SYMBOL_GPL_FOR_MODULES(.., "kvm,kvm-intel")
unconditionally, but yeah I agree having EXPORT_SYMBOL_GPL_FOR_KVM() and
only having the actual export when KVM sub module is enabled is better.

I tested that with this series I can still successfully create TDX and SGX
guests, so for TDX and SGX bits:

Acked-by: Kai Huang <kai.huang@intel.com>
Tested-by: Kai Huang <kai.huang@intel.com>

---

## [9] Anthony Krowiak — 2025-08-12
*Subject: Re: [PATCH 1/6] KVM: s390/vfio-ap: Use kvm_is_gpa_in_memslot()
 instead of open coded equivalent*

On 7/29/25 1:42 PM, Sean Christopherson wrote:
> Use kvm_is_gpa_in_memslot() to check the validity of the notification
> indicator byte address instead of open coding equivalent logic in the VFIO

Acked-by: Anthony Krowiak <akrowiak@linux.ibm.com>

I only reviewed this patch in the series.

> ---
>   arch/s390/include/asm/kvm_host.h  | 2 ++

---

## [10] Vlastimil Babka — 2025-08-25
*Subject: Re: [PATCH 0/6] KVM: Export KVM-internal symbols for sub-modules only*

On 7/29/25 19:42, Sean Christopherson wrote:
> Use the newfangled EXPORT_SYMBOL_GPL_FOR_MODULES() along with some macro
> shenanigans to export KVM-internal symbols if and only if KVM has one or

Note it was renamed to EXPORT_SYMBOL_FOR_MODULES() only in 6.17-rc3 so this
series will need rebasing to that and adjustment. Probably best to rename
also EXPORT_SYMBOL_GPL_FOR_KVM_INTERNAL for consistency?

Thanks,
Vlastimil

> more sub-modules, and only for those sub-modules, e.g. x86's kvm-amd.ko
> and/or kvm-intel.ko.

---
