---
title: '[RFC PATCH 0/1] KVM: SEV: Add support for SMT Protection'
date: 2025-08-07
last_reply: 2025-08-08
message_count: 4
participants: ['Kim Phillips', 'Dave Hansen', 'K Prateek Nayak']
---

## [1] Kim Phillips — 2025-08-07

On an SMT-enabled system, the SMT Protection feature allows an
SNP guest to demand its hardware vCPU thread to run alone on
the physical core.  It will opt to do this to protect itself
against possible side channel attacks from shared core resources.
Hardware supports this by enforcing the sibling of the vCPU thread
to be in the idle state when the vCPU is running: If hardware detects
the sibling has not entered the idle state, or it exited it, then
the vCPU VMRUN exits with a new "IDLE_REQUIRED" status, where the
hypervisor should schedule the idle process on the sibling thread
simultaneously with resuming the vCPU VMRUN.

There is a new HLT_WAKEUP_ICR MSR that the hypervisor programs
for each system SMT thread such that if an idle sibling of a
SMT Protected guest vCPU receives an interrupt, hardware will write
the HLT_WAKEUP_ICR value to the APIC ICR to 'kick' the vCPU
thread out of its VMRUN state. Hardware then allows the sibling
to then exit the idle state and service its interrupt.

The feature is supported on EYPC Zen 4 and above CPUs.

For more information, see "15.36.17 Side-Channel Protection",
"SMT Protection", in:

"AMD64 Architecture Programmer's Manual Volume 2: System Programming Part 2,
Pub. 24593 Rev. 3.42 - March 2024"

available here:

https://bugzilla.kernel.org/attachment.cgi?id=306250

See the end of this message for the qemu hack that calls the
Linux Core Scheduler prctl syscall to create a unique per-vCPU
cookie to ensure the vCPU process will not be scheduled if
there is anything else running on the sibling thread of the
core.

As it turns out, this approach is less than efficient because
existing Core Scheduling semantics only prevent other userspace
processes from running on the sibling thread that hardware requires
to be in the idle state.

Because of this, the sibling CPU VMRUN frequently exits with
"IDLE_REQUIRED" when the scheduler runs its "OS noise" (softirq
work, etc.) instead of forcing the hardware idle state throughout
the duration of the VMRUN.

Mild testing yields eventual CPU stalls in the guest (minutes after
boot):

[    C0] rcu: INFO: rcu_preempt detected stalls on CPUs/tasks:
[    C0] rcu: 	1-...!: (0 ticks this GP) idle=8d58/0/0x0 softirq=12830/12830 fqs=0 (false positive?)
[    C0] rcu: 	(detected by 0, t=16253 jiffies, g=12377, q=12 ncpus=2)
[    C0] rcu: rcu_preempt kthread timer wakeup didn't happen for 16252 jiffies! g12377 f0x0 RCU_GP_WAIT_FQS(5) ->state=0x402
[    C0] rcu: 	Possible timer handling issue on cpu=1 timer-softirq=15006
[    C0] rcu: rcu_preempt kthread starved for 16253 jiffies! g12377 f0x0 RCU_GP_WAIT_FQS(5) ->state=0x402 ->cpu=1
[    C0] rcu: 	Unless rcu_preempt kthread gets sufficient CPU time, OOM is now expected behavior.

..with the occasional "NOHZ tick-stop error: local softirq work is
pending, handler #200!!!" on the host.

However, this RFC represents only one of three approaches attempted:

 - Another brute-force approach simply called remove_cpu() on the sibling
   before, and add_cpu() after __svm_sev_es_vcpu_run() in
   svm_vcpu_enter_exit().  The effort was quickly abandoned since
   it led to insurmountable lock contention issues:
   BUG: scheduling while atomic: qemu-system-x86/6743/0x00000002
    4 locks held by qemu-system-x86/6743:
    #0: ff160079b2dd80b8 (&vcpu->mutex){....}-{3:3}, at: kvm_vcpu_ioctl+0x94/0xa40 [kvm]
    #1: ffffffffba3c5410 (device_hotplug_lock){....}-{3:3}, at: lock_device_hotplug+0x1b/0x30
    #2: ff16009838ff5398 (&dev->mutex){....}-{3:3}, at: device_offline+0x9c/0x120
    #3: ffffffffb9e7e6b0 (cpu_add_remove_lock){....}-{3:3}, at: cpu_device_down+0x24/0x50

 - The third approach attempted to forward port vCPU Core Scheduling
   from the original 4.18 based work by Peter Z.:

   https://github.com/pdxChen/gang/commits/sched_1.23-base

   K. Prateek Nayak provided enough guidance to get me past host lockups
   from "kvm,sched: Track VCPU threads", but the following "sched: Add VCPU
   aware SMT scheduling" commit proved insurmountable to forward-port
   given the complex changes to scheduler internals since then.

Comments welcome:

- Are any of these three approaches even close to an
  upstream-acceptable solution to support SMT Protection?

- Given the feature's strict sibling idle state constraints,
  should SMT Protection even be supported at all?

This RFC applies to kvm-x86/next kvm-x86-next-2025.07.21 (33f843444e28).

Qemu hack:

From 0278a4078933d9bce16a8e80f415466b44244a59 Mon Sep 17 00:00:00 2001
From: Kim Phillips <kim.phillips@amd.com>
Date: Wed, 2 Apr 2025 16:02:50 -0500
Subject: [RFC PATCH] system/cpus: Affine and Core-Schedule vCPUs onto pCPUs

DO NOT MERGE.

Hack to experiment supporting SEV-SNP "SMT Protection" feature.  It:

 1. Affines vCPUs to individual core pCPUs (as cpu_index increments
    over single-core threads 1, 2, etc.),

 2. Calls the Linux Core Scheduler prctl syscall to create a per-vCPU
    unique cookie to ensure the vCPU process will not be scheduled
    if there is anything else on the sibling thread of the pCPU core.

Note: It contains POSIX-specific code that really belongs in
util/qemu-thread-posix.c, and other hackery.

Signed-off-by: Kim Phillips <kim.phillips@amd.com>
---
 accel/kvm/kvm-accel-ops.c | 13 +++++++++++++
 1 file changed, 13 insertions(+)

diff --git a/accel/kvm/kvm-accel-ops.c b/accel/kvm/kvm-accel-ops.c
index c239dfc87a..4b853d3024 100644
--- a/accel/kvm/kvm-accel-ops.c
+++ b/accel/kvm/kvm-accel-ops.c
@@ -26,9 +26,12 @@
 #include <linux/kvm.h>
 #include "kvm-cpus.h"

+#include <sys/prctl.h> /* PR_SCHED_CORE_CREATE */
+
 static void *kvm_vcpu_thread_fn(void *arg)
 {
     CPUState *cpu = arg;
+    cpu_set_t cpuset;
     int r;

     rcu_register_thread();
@@ -38,6 +41,16 @@ static void *kvm_vcpu_thread_fn(void *arg)
     cpu->thread_id = qemu_get_thread_id();
     current_cpu = cpu;

+    CPU_ZERO(&cpuset);
+    CPU_SET(cpu->cpu_index, &cpuset);
+    pthread_setaffinity_np(cpu->thread->thread, sizeof(cpu_set_t), &cpuset);
+
+    r = prctl(PR_SCHED_CORE, PR_SCHED_CORE_CREATE, 0, 0, 0);
+    if (r) {
+        printf("%s %d: CORE CREATE ret %d \r\n", __func__, __LINE__, r);
+        exit(1);
+    }
+
     r = kvm_init_vcpu(cpu, &error_fatal);
     kvm_init_cpu_signals(cpu);

--
2.43.0

Kim Phillips (1):
  KVM: SEV: Add support for SMT Protection

 arch/x86/include/asm/cpufeatures.h |  1 +
 arch/x86/include/asm/msr-index.h   |  1 +
 arch/x86/include/asm/svm.h         |  1 +
 arch/x86/include/uapi/asm/svm.h    |  1 +
 arch/x86/kvm/svm/sev.c             | 17 +++++++++++++++++
 arch/x86/kvm/svm/svm.c             |  3 +++
 6 files changed, 24 insertions(+)

base-commit: 33f843444e28920d6e624c6c24637b4bb5d3c8de
--
2.43.0

Kim Phillips (1):
  KVM: SEV: Add support for SMT Protection

 arch/x86/include/asm/cpufeatures.h |  1 +
 arch/x86/include/asm/msr-index.h   |  1 +
 arch/x86/include/asm/svm.h         |  1 +
 arch/x86/include/uapi/asm/svm.h    |  1 +
 arch/x86/kvm/svm/sev.c             | 17 +++++++++++++++++
 arch/x86/kvm/svm/svm.c             |  3 +++
 6 files changed, 24 insertions(+)


base-commit: 33f843444e28920d6e624c6c24637b4bb5d3c8de

---

## [2] Kim Phillips — 2025-08-07
*Subject: [RFC PATCH 1/1] KVM: SEV: Add support for SMT Protection*

Add the new CPUID bit that indicates available hardware support:
CPUID_Fn8000001F_EAX [AMD Secure Encryption EAX] bit 25.

Indicate support for SEV_FEATURES bit 15 (SmtProtection) to be set by
an SNP guest to enable the feature.

Handle the new "IDLE_REQUIRED" VMRUN exit code case that indicates that
the hardware has detected that the sibling of the vCPU is not in the
idle state.  If the new IDLE_REQUIRED error code is returned, return
to the guest.  Ideally this would be optimized to rendezvous with
sibling idle state transitions.

Program new HLT_WAKEUP_ICR MSRs on all pCPUs with their sibling
ACPI IDs.  This enables hardware/microcode to 'kick' the pCPU running
the vCPU when its sibling needs to process a pending interrupt.

For more information, see "15.36.17 Side-Channel Protection",
"SMT Protection", in:

"AMD64 Architecture Programmer's Manual Volume 2: System Programming Part 2,
Pub. 24593 Rev. 3.42 - March 2024"

available here:

https://bugzilla.kernel.org/attachment.cgi?id=306250

Signed-off-by: Kim Phillips <kim.phillips@amd.com>
---
 arch/x86/include/asm/cpufeatures.h |  1 +
 arch/x86/include/asm/msr-index.h   |  1 +
 arch/x86/include/asm/svm.h         |  1 +
 arch/x86/include/uapi/asm/svm.h    |  1 +
 arch/x86/kvm/svm/sev.c             | 17 +++++++++++++++++
 arch/x86/kvm/svm/svm.c             |  3 +++
 6 files changed, 24 insertions(+)

diff --git a/arch/x86/include/asm/cpufeatures.h b/arch/x86/include/asm/cpufeatures.h
index 286d509f9363..4536fe40f5aa 100644
--- a/arch/x86/include/asm/cpufeatures.h
+++ b/arch/x86/include/asm/cpufeatures.h
@@ -448,6 +448,7 @@
 #define X86_FEATURE_DEBUG_SWAP		(19*32+14) /* "debug_swap" SEV-ES full debug state swap support */
 #define X86_FEATURE_RMPREAD		(19*32+21) /* RMPREAD instruction */
 #define X86_FEATURE_SEGMENTED_RMP	(19*32+23) /* Segmented RMP support */
+#define X86_FEATURE_SMT_PROTECTION	(19*32+25) /* SEV-SNP SMT Protection */
 #define X86_FEATURE_ALLOWED_SEV_FEATURES (19*32+27) /* Allowed SEV Features */
 #define X86_FEATURE_SVSM		(19*32+28) /* "svsm" SVSM present */
 #define X86_FEATURE_HV_INUSE_WR_ALLOWED	(19*32+30) /* Allow Write to in-use hypervisor-owned pages */
diff --git a/arch/x86/include/asm/msr-index.h b/arch/x86/include/asm/msr-index.h
index c29127ac626a..a75999a93c3f 100644
--- a/arch/x86/include/asm/msr-index.h
+++ b/arch/x86/include/asm/msr-index.h
@@ -707,6 +707,7 @@
 #define MSR_AMD64_SEG_RMP_ENABLED_BIT	0
 #define MSR_AMD64_SEG_RMP_ENABLED	BIT_ULL(MSR_AMD64_SEG_RMP_ENABLED_BIT)
 #define MSR_AMD64_RMP_SEGMENT_SHIFT(x)	(((x) & GENMASK_ULL(13, 8)) >> 8)
+#define MSR_AMD64_HLT_WAKEUP_ICR	0xc0010137
 
 #define MSR_SVSM_CAA			0xc001f000
 
diff --git a/arch/x86/include/asm/svm.h b/arch/x86/include/asm/svm.h
index ffc27f676243..251cead18681 100644
--- a/arch/x86/include/asm/svm.h
+++ b/arch/x86/include/asm/svm.h
@@ -299,6 +299,7 @@ static_assert((X2AVIC_MAX_PHYSICAL_ID & AVIC_PHYSICAL_MAX_INDEX_MASK) == X2AVIC_
 #define SVM_SEV_FEAT_RESTRICTED_INJECTION		BIT(3)
 #define SVM_SEV_FEAT_ALTERNATE_INJECTION		BIT(4)
 #define SVM_SEV_FEAT_DEBUG_SWAP				BIT(5)
+#define SVM_SEV_FEAT_SMT_PROTECTION			BIT(15)
 
 #define VMCB_ALLOWED_SEV_FEATURES_VALID			BIT_ULL(63)
 
diff --git a/arch/x86/include/uapi/asm/svm.h b/arch/x86/include/uapi/asm/svm.h
index 9c640a521a67..7b81ee574c55 100644
--- a/arch/x86/include/uapi/asm/svm.h
+++ b/arch/x86/include/uapi/asm/svm.h
@@ -126,6 +126,7 @@
 	/* SW_EXITINFO1[11:4] */				\
 	((((u64)reason_code) & 0xff) << 4))
 #define SVM_VMGEXIT_UNSUPPORTED_EVENT		0x8000ffff
+#define SVM_VMGEXIT_IDLE_REQUIRED		0xfffffffd
 
 /* Exit code reserved for hypervisor/software use */
 #define SVM_EXIT_SW				0xf0000000
diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 2fbdebf79fbb..5f2605bd265f 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -3082,6 +3082,23 @@ void __init sev_hardware_setup(void)
 	sev_supported_vmsa_features = 0;
 	if (sev_es_debug_swap_enabled)
 		sev_supported_vmsa_features |= SVM_SEV_FEAT_DEBUG_SWAP;
+
+	if (sev_snp_enabled && cpu_feature_enabled(X86_FEATURE_SMT_PROTECTION)) {
+		unsigned long long hlt_wakeup_icr;
+		unsigned int cpu, sibling;
+
+		sev_supported_vmsa_features |= SVM_SEV_FEAT_SMT_PROTECTION;
+
+		for_each_online_cpu(cpu) {
+			for_each_cpu(sibling, topology_sibling_cpumask(cpu)) {
+				if (sibling == cpu)
+					continue;
+				hlt_wakeup_icr = LOCAL_TIMER_VECTOR | (unsigned long long)
+						 per_cpu(x86_cpu_to_apicid, sibling) << 32;
+				wrmsrq_safe_on_cpu(cpu, MSR_AMD64_HLT_WAKEUP_ICR, hlt_wakeup_icr);
+			}
+		}
+	}
 }
 
 void sev_hardware_unsetup(void)
diff --git a/arch/x86/kvm/svm/svm.c b/arch/x86/kvm/svm/svm.c
index d9931c6c4bc6..708c5e939b0d 100644
--- a/arch/x86/kvm/svm/svm.c
+++ b/arch/x86/kvm/svm/svm.c
@@ -3502,6 +3502,9 @@ static int svm_handle_invalid_exit(struct kvm_vcpu *vcpu, u64 exit_code)
 
 int svm_invoke_exit_handler(struct kvm_vcpu *vcpu, u64 exit_code)
 {
+	if (exit_code == SVM_VMGEXIT_IDLE_REQUIRED)
+		return 1; /* resume guest */
+
 	if (!svm_check_exit_valid(exit_code))
 		return svm_handle_invalid_exit(vcpu, exit_code);

---

## [3] Dave Hansen — 2025-08-07
*Subject: Re: [RFC PATCH 1/1] KVM: SEV: Add support for SMT Protection*

On 8/7/25 09:59, Kim Phillips wrote:
> Add the new CPUID bit that indicates available hardware support:
> CPUID_Fn8000001F_EAX [AMD Secure Encryption EAX] bit 25.

It would be ideal to see an logical description of what "SmtProtection"
is and what it means for the kernel as opposed to referring to the
documentation and letting reviewers draw their own conclusions.

---

## [4] K Prateek Nayak — 2025-08-08
*Subject: Re: [RFC PATCH 1/1] KVM: SEV: Add support for SMT Protection*

Hello Dave,

On 8/7/2025 11:30 PM, Dave Hansen wrote:
> On 8/7/25 09:59, Kim Phillips wrote:
>> Add the new CPUID bit that indicates available hardware support:

I'll try to elaborate on the general idea of SMT Protection for SEV-SNP
VM: The idea is when a vCPU is running (between VMRUN and VMEXIT), the
sibling CPU must be idle - in HLT or C2 state.

If the sibling is not idling in one of those state the VMRUN will
immediately exit with the "VMEXIT_IDLE_REQUIRED" error code.

Ideally, some layer in KVM / kernel has to coordinate the following:

  (I'm using thread_info flags for illustrative purposes)

                CPU0 (Running vCPU)                               CPU128 (SMT sibling)
                ===================                               ====================

  /* VMRUN Path */                                      /*
  set_thread_flag(TIF_SVM_PROTECTED);                    * Core scheduling ensures this thread is
  retry:                                                 * force into an idle state.
    while (!(READ_ONCE(smt_ti->flags) & TIF_IDLING))     * XXX: Needs to only select HLT / C2
      cpu_relax();                                       */
      cpu_relax();                                      if (READ_ONCE(smt_ti->flags) & TIF_SVM_PROTECTED)
      cpu_relax();                                        force_hlt_or_c2()
      cpu_relax();                                          set_thread_flag(TIF_IDLING);
      /* Sees TIF_IDLING on SMT */                          native_safe_halt(); 
      VMRUN /* Success */


Here is a case where the VMRUN fails with "VMEXIT_IDLE_REQUIRED":

                CPU0 (Running vCPU)                               CPU128 (SMT sibling)
                ===================                               ====================

  /* VMRUN Path */                                      /*
  set_thread_flag(TIF_SVM_PROTECTED);                    * Core scheduling ensures this thread is
  retry:                                                 * force into an idle state.
    while (!(READ_ONCE(smt_ti->flags) & TIF_IDLING))     * XXX: Needs to only select HLT / C2
      cpu_relax();                                       */
      cpu_relax();                                      if (READ_ONCE(smt_ti->flags) & TIF_SVM_PROTECTED)
      cpu_relax();                                        force_hlt_or_c2()
      cpu_relax();                                          set_thread_flag(TIF_IDLING);
      /* Sees TIF_IDLING on SMT */                          native_safe_halt()
      ... /* Interrupted before VMRUN */                      sti; hlt; /* Recieves an interrupt */
      ...                                                     /* Thread is busy running interrupt handler */
      VMRUN /* Fails */                                       ... /* Busy */
      VMGEXIT /* VMEXIT_IDLE_REQUIRED */
        if (exit_code == SVM_VMGEXIT_IDLE_REQUIRED)
          goto retry;


Obviously we cannot just disable interrupts on sibling - if a high
priority task wakes up on the SMT sibling, the core scheduling
infrastructure will preempt the vCPU and run the high priority task on
the sibling.

This is where the "IDLE_WAKEUP_ICR" MSR (MSR_AMD64_HLT_WAKEUP_ICR) comes
into play - when a CPU is idle and the SMT is running the vCPU of an SMT
Protected guest, the idle CPU will not immediately exit idle when
receiving an interrupt (or any "wake up event" as .

It instead programs the value of the IDLE_WAKEUP_ICR into the local APIC
register and waits. The expectation is that an interrupt will be sent to the
sibling CPU which will cause a VMEXIT on the sibling and then the H/W will
exit idle and start running the interrupt handler.

This is the full flow with IDLE_WAKEUP_ICR programming:

                CPU0 (Running vCPU)                               CPU128 (SMT sibling)
                ===================                               ====================

  /* VMRUN Path */                                      /*
  set_thread_flag(TIF_SVM_PROTECTED);                    * Core scheduling ensures this thread is
  retry:                                                 * force into an idle state.
    while (!(READ_ONCE(smt_ti->flags) & TIF_IDLING))     * XXX: Needs to only select HLT / C2
      cpu_relax();                                       */
      cpu_relax();                                      if (READ_ONCE(smt_ti->flags) & TIF_SVM_PROTECTED)
      cpu_relax();                                        force_hlt_or_c2()
      cpu_relax();                                          /* Program to send IPI to CPU0 */
      cpu_relax();                                          wrmsrl(MSR_AMD64_HLT_WAKEUP_ICR, ...)
      cpu_relax();                                          set_thread_flag(TIF_IDLING);
      /* Sees TIF_IDLING on SMT */                          native_safe_halt()
      ...                                                     sti; hlt; /* Idle */
      VMRUN /* Success */                                     ... /* Idle */
      ... /* Running protected guest. */                      ... 
      ...                                                     /*
      ...                                                      * Receives an interrupt. H/W writes
      ...                                                      * value in MSR_AMD64_HLT_WAKEUP_ICR
      ...                                                      * to the local APIC.
      ...                                                      */
      /* Interrupted */                                        ... /* Still idle */
      VMEXIT                                                   /* Exits idle, executes interrupt. */
      /* Handle the dummy interrupt. */
      goto retry;


Apart form the "MSR_AMD64_HLT_WAKEUP_ICR" related bits, the coordination
to force idle the sibling and waiting until HLT / C2 is executed has to
be done by the OS / KVM.

As Kim mentions, core scheduling can only ensure SMT starts running the
idle task but the VMRUN for an SMT Protected guest requires the idle
thread on the sibling to reach the idle instruction in order to proceed.

Furthermore, every little noise on the sibling will cause the guest to
continuously exit out which is a whole difference challenge to deal
with and I'm assuming the folks will use isolated partitions to get
around that.

---
