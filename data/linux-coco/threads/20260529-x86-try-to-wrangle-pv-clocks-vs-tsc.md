---
title: 'x86: Try to wrangle PV clocks vs. TSC'
date: 2026-05-29
last_reply: 2026-06-05
message_count: 66
participants: ['Sean Christopherson', 'Jürgen Groß', 'Borislav Petkov', 'David Woodhouse', 'Kiryl Shutsemau', 'Thomas Gleixner']
---

## [1] Sean Christopherson — 2026-05-29

Well, the number of patches in the series is going in the wrong direction,
but I'm much happier with this version, which eschews the x86_platform
overrides entirely in favor of a fixed sequence for selecting the TSC/CPU
frequency "routine".

Given that previous versions had fatal NULL pointer deref bugs that affected
VMware and Xen, this series needs testing and acks from those maintainers.

The primary goal of this series to fix flaws with SNP and TDX guests where a
PV clock provided by the untrusted hypervisor is used instead of the secure
TSC that is controlled by trusted firmware.

The secondary goal is modernize running under KVM.  Currently, KVM guests will
use TSC for clocksource, but not sched_clock.  And Linux-as-a-KVM-guest doesn't
support paravirt enumeration of the TSC/APIC frequencies, even though QEMU
provides that information by default.

The tertiary goal is to clean up the PV clock code to deduplicate logic across
hypervisors, and to hopefully make it all easier to maintain going forward.

v4 also adds a quaternary goal of cleaning up the TSC calibration code, which
was made stupidly hard to follow by hypervisor code mixing in with the native
calibration routines, instead of being implemented as a pure alternative.

Lots more background on the SNP/TDX motiviation:
https://lore.kernel.org/all/20250106124633.1418972-13-nikunj@amd.com

As before, I deliberately omitted jailhouse-dev@googlegroups.com from the To/Cc,
as those emails bounced on v1, AFAICT nothing has changed.

Note, I deliberately didn't collect a few reviews as the patches changed quite
a bit from what was reviewed in v3.

v4:
 - Use x86_init_noop() to skip save/restore on VMware and Xen instead of
   nullifying x86_platform.{save,restore}_sched_clock_state. [Sashiko]
 - Use '0' to indicate "failure" when getting the CPU frequency from CPUID, to
   avoid using an out-param and thus make it all but impossible to
   unintentionally clobber the global cpu_khz (which v3 did). [Sashiko]
 - Rename cpuid_get_cpu_freq() => __cpu_khz_from_cpuid() to capture its
   relationship with cpu_khz_from_cpuid().
 - Compute lapic_timer_period in units of ticks, not Khz. [Sashiko]
 - Kill off x86_platform_ops.calibrate_{cpu,tsc}(), and instead use dedicated
   hooks for hypervisor code, and direct calls for TDX and SNP. [David, loosely]
 - Drop SNP's secure TSC override of _CPU_ calibration, as there's zero
   evidence it's justified or a net positive.
 - Collect reviews/acks. [David, Wei]
 - Decouple getting TSC/APIC frequencies from KVM PV CPUID from kvmclock. [David]
 - Fix an amusing number of Opportunistically misspellings. [David]
 - Set kvm_sched_clock_offset _before_ registering kvmclock as sched_clock,
   and add a comment to guard against future goofs. [Sashiko]
 - Keep "setup_force_cpu_cap(X86_FEATURE_TSC_RELIABLE)" in Hyper-V's handling
   of HV_ACCESS_TSC_INVARIANT, as it's technically possible to have a VM
   with HV_ACCESS_TSC_INVARIANT but not HV_ACCESS_FREQUENCY_MSRS.  Though as
   a _very_ nice side effect of using dedicated sequencing for selecting the
   TSC frequency source, this would have naturally happened anyways. [Sashiko]

v3:
 - https://lore.kernel.org/all/20260515191942.1892718-1-seanjc@google.com
 - Collect reviews. [Michael, Thomas]
 - Use Hyper-V reference counter / refcounter instead of Hyper-V timer. [Michael]
 - Use the paravirt CPUID interface first proposed by VMware for KVM's
   "official" mechanism for communicating frequency to KVM-aware guests,
   instead of abusing Intel's CPUID leafs. [David]
 - Deal with paravirt code being moved into asm/timers.h and
   arch/x86/kernel/tsc.c.

v2:
 - https://lore.kernel.org/all/Z8YWttWDtvkyCtdJ@google.com
 - Add struct to hold the TSC CPUID output. [Boris]
 - Don't pointlessly inline the TSC CPUID helpers. [Boris]
 - Fix a variable goof in a helper, hopefully for real this time. [Dan]
 - Collect reviews. [Nikunj]
 - Override the sched_clock save/restore hooks if and only if a PV clock
   is successfully registered.
 - During resome, restore clocksources before reading persistent time.
 - Clean up more warts created by kvmclock.
 - Fix more bugs in kvmclock's suspend/resume handling.
 - Try to harden kvmclock against future bugs.

v1: https://lore.kernel.org/all/20250201021718.699411-1-seanjc@google.com

David Woodhouse (3):
  KVM: x86: Officially define CPUID 0x40000010 as PV Timing Info (TSC
    and Bus)
  x86/kvm: Obtain TSC frequency from PV CPUID if present
  x86/xen: Obtain TSC frequency from CPUID if present

Sean Christopherson (44):
  x86/tsc: Never re-calibrate TSC frequency if its exact timing is known
  x86/tsc: Add a standalone helpers for getting TSC info from CPUID.0x15
  x86/sev: Mark TSC as reliable when configuring Secure TSC
  x86/sev: Don't override CPU frequency calibration for SNP's Secure TSC
  x86/sev: Move check for SNP Secure TSC support to tsc_early_init()
  x86/sev: Shove SNP's secure/trusted TSC frequency directly into
    "calibration"
  x86/tdx: Force TSC frequency with CPUID-based info provided by the
    TDX-Module
  x86/tsc: Add dedicated hypervisor hooks for getting known TSC/CPU
    frequencies
  x86/acrn: Mark TSC frequency as known when using ACRN for calibration
  x86/tsc: Consolidate forcing of X86_FEATURE_TSC_KNOWN_FREQ for PV code
  x86/tsc: Kill off x86_platform_ops.calibrate_{cpu,tsc}() hooks
  x86/tsc: Rename pit_hpet_ptimer_calibrate_cpu() =>
    native_calibrate_cpu_late()
  x86/tsc: Fold native_calibrate_cpu() into recalibrate_cpu_khz()
  x86/kvmclock: Rename kvm_get_tsc_khz() to kvmclock_get_tsc_khz()
  x86/kvm: Mark TSC as reliable when it's constant and nonstop
  x86/kvm: Get local APIC bus frequency from PV CPUID Timing Info
  x86/tsc: Add standalone helper for getting CPU frequency from CPUID
  x86/kvm: Get CPU base frequency from CPUID when it's available
  clocksource: hyper-v: Register sched_clock save/restore iff it's
    necessary
  clocksource: hyper-v: Drop wrappers to sched_clock save/restore
    helpers
  clocksource: hyper-v: Don't save/restore TSC offset when using HV
    sched_clock
  x86/kvmclock: Setup kvmclock for secondary CPUs iff CONFIG_SMP=y
  x86/kvm: Don't disable kvmclock on BSP in syscore_suspend()
  x86/paravirt: Remove unnecessary PARAVIRT=n stub for
    paravirt_set_sched_clock()
  x86/paravirt: Move handling of unstable PV clocks into
    paravirt_set_sched_clock()
  x86/kvmclock: Move sched_clock save/restore helpers up in kvmclock.c
  x86/xen/time: NOP-ify x86_platform's sched_clock save/restore hooks
  x86/vmware: NOP-ify save/restore hooks when using VMware's sched_clock
  x86/tsc: WARN if TSC sched_clock save/restore used with PV sched_clock
  x86/paravirt: Pass sched_clock save/restore helpers during
    registration
  x86/kvmclock: Move kvm_sched_clock_init() down in kvmclock.c
  x86/xen/time: Mark xen_setup_vsyscall_time_info() as __init
  x86/pvclock: Mark setup helpers and related various as
    __init/__ro_after_init
  x86/pvclock: WARN if pvclock's valid_flags are overwritten
  x86/kvmclock: Refactor handling of PVCLOCK_TSC_STABLE_BIT during
    kvmclock_init()
  timekeeping: Resume clocksources before reading persistent clock
  x86/kvmclock: Hook clocksource.suspend/resume when kvmclock isn't
    sched_clock
  x86/kvmclock: WARN if wall clock is read while kvmclock is suspended
  x86/paravirt: Mark __paravirt_set_sched_clock() as __init
  x86/paravirt: Plumb a return code into __paravirt_set_sched_clock()
  x86/paravirt: Don't use a PV sched_clock in CoCo guests with trusted
    TSC
  x86/kvmclock: Use TSC for sched_clock if it's constant and non-stop
  x86/kvmclock: Plumb in AP-online and BSP-resume to kvmlock, for
    documentation
  x86/paravirt: Move using_native_sched_clock() stub into timer.h

 Documentation/virt/kvm/x86/cpuid.rst |  12 ++
 arch/x86/coco/sev/core.c             |  21 +--
 arch/x86/coco/tdx/tdx.c              |  19 ++-
 arch/x86/include/asm/acrn.h          |   5 -
 arch/x86/include/asm/kvm_para.h      |  12 +-
 arch/x86/include/asm/sev.h           |   4 +-
 arch/x86/include/asm/tdx.h           |   2 +
 arch/x86/include/asm/timer.h         |  15 +-
 arch/x86/include/asm/tsc.h           |  11 +-
 arch/x86/include/asm/x86_init.h      |   8 +-
 arch/x86/include/uapi/asm/kvm_para.h |  11 ++
 arch/x86/kernel/cpu/acrn.c           |  10 +-
 arch/x86/kernel/cpu/mshyperv.c       |  65 +-------
 arch/x86/kernel/cpu/vmware.c         |  13 +-
 arch/x86/kernel/jailhouse.c          |   7 +-
 arch/x86/kernel/kvm.c                | 108 +++++++++++--
 arch/x86/kernel/kvmclock.c           | 208 ++++++++++++++++---------
 arch/x86/kernel/pvclock.c            |   9 +-
 arch/x86/kernel/tsc.c                | 218 +++++++++++++++++----------
 arch/x86/kernel/x86_init.c           |   2 -
 arch/x86/mm/mem_encrypt_amd.c        |   3 -
 arch/x86/xen/time.c                  |  25 ++-
 drivers/clocksource/hyperv_timer.c   |  38 +++--
 include/clocksource/hyperv_timer.h   |   2 -
 kernel/time/timekeeping.c            |   9 +-
 25 files changed, 533 insertions(+), 304 deletions(-)


base-commit: 4678d11f294de0fd295a265e02955b5d1a4a2684

---

## [2] Sean Christopherson — 2026-05-29
*Subject: [PATCH v4 01/47] x86/tsc: Never re-calibrate TSC frequency if its
 exact timing is known*

Don't re-calibrate the TSC frequency if the TSC is known to run at a fixed
frequency.  In practice, this is likely one big nop, as re-calibration is
used only for SMP=n kernels, and only for hardware that is 20+ years old,
i.e. is extremely unlikely to collide with TSC_KNOWN_FREQ.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kernel/tsc.c | 3 ++-
 1 file changed, 2 insertions(+), 1 deletion(-)

diff --git a/arch/x86/kernel/tsc.c b/arch/x86/kernel/tsc.c
index c5110eb554bc..08cf6625d484 100644
--- a/arch/x86/kernel/tsc.c
+++ b/arch/x86/kernel/tsc.c
@@ -946,7 +946,8 @@ void recalibrate_cpu_khz(void)
 		return;
 
 	cpu_khz = x86_platform.calibrate_cpu();
-	tsc_khz = x86_platform.calibrate_tsc();
+	if (!boot_cpu_has(X86_FEATURE_TSC_KNOWN_FREQ))
+		tsc_khz = x86_platform.calibrate_tsc();
 	if (tsc_khz == 0)
 		tsc_khz = cpu_khz;
 	else if (abs(cpu_khz - tsc_khz) * 10 > tsc_khz)

---

## [3] Sean Christopherson — 2026-05-29
*Subject: [PATCH v4 02/47] x86/tsc: Add a standalone helpers for getting TSC
 info from CPUID.0x15*

Extract retrieval of TSC frequency information from CPUID into standalone
helpers so that TDX guest support can reuse the logic.  Provide a version
that includes the multiplier math as TDX does NOT want to use
native_calibrate_tsc()'s fallback logic that derives the TSC frequency
based on CPUID.0x16, when the core crystal frequency isn't known.

Opportunistically drop native_calibrate_tsc()'s "== 0" and "!= 0" checks
in favor of the kernel's preferred style.

No functional change intended.

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/tsc.h |  8 +++++
 arch/x86/kernel/tsc.c      | 67 +++++++++++++++++++++++++-------------
 2 files changed, 52 insertions(+), 23 deletions(-)

diff --git a/arch/x86/include/asm/tsc.h b/arch/x86/include/asm/tsc.h
index 4f7f09f50552..6cf26e62e9a6 100644
--- a/arch/x86/include/asm/tsc.h
+++ b/arch/x86/include/asm/tsc.h
@@ -83,6 +83,14 @@ static inline cycles_t get_cycles(void)
 }
 #define get_cycles get_cycles
 
+struct cpuid_tsc_info {
+	unsigned int denominator;
+	unsigned int numerator;
+	unsigned int crystal_khz;
+	unsigned int tsc_khz;
+};
+extern int __init cpuid_get_tsc_freq(struct cpuid_tsc_info *info);
+
 extern void tsc_early_init(void);
 extern void tsc_init(void);
 extern void mark_tsc_unstable(char *reason);
diff --git a/arch/x86/kernel/tsc.c b/arch/x86/kernel/tsc.c
index 08cf6625d484..f7f561722efa 100644
--- a/arch/x86/kernel/tsc.c
+++ b/arch/x86/kernel/tsc.c
@@ -658,46 +658,67 @@ static unsigned long quick_pit_calibrate(void)
 	return delta;
 }
 
+static int cpuid_get_tsc_info(struct cpuid_tsc_info *info)
+{
+	unsigned int ecx_hz, edx;
+
+	memset(info, 0, sizeof(*info));
+
+	if (boot_cpu_data.cpuid_level < CPUID_LEAF_TSC)
+		return -ENOENT;
+
+	/* CPUID 15H TSC/Crystal ratio, plus optionally Crystal Hz */
+	cpuid(CPUID_LEAF_TSC, &info->denominator, &info->numerator, &ecx_hz, &edx);
+
+	if (!info->denominator || !info->numerator)
+		return -ENOENT;
+
+	/*
+	 * Note, some CPUs provide the multiplier information, but not the core
+	 * crystal frequency.  The multiplier information is still useful for
+	 * such CPUs, as the crystal frequency can be gleaned from CPUID.0x16.
+	 */
+	info->crystal_khz = ecx_hz / 1000;
+	return 0;
+}
+
+int __init cpuid_get_tsc_freq(struct cpuid_tsc_info *info)
+{
+	if (cpuid_get_tsc_info(info) || !info->crystal_khz)
+		return -ENOENT;
+
+	info->tsc_khz = info->crystal_khz * info->numerator / info->denominator;
+	return 0;
+}
+
 /**
  * native_calibrate_tsc - determine TSC frequency
  * Determine TSC frequency via CPUID, else return 0.
  */
 unsigned long native_calibrate_tsc(void)
 {
-	unsigned int eax_denominator, ebx_numerator, ecx_hz, edx;
-	unsigned int crystal_khz;
+	struct cpuid_tsc_info info;
 
 	if (boot_cpu_data.x86_vendor != X86_VENDOR_INTEL)
 		return 0;
 
-	if (boot_cpu_data.cpuid_level < CPUID_LEAF_TSC)
+	if (cpuid_get_tsc_info(&info))
 		return 0;
 
-	eax_denominator = ebx_numerator = ecx_hz = edx = 0;
-
-	/* CPUID 15H TSC/Crystal ratio, plus optionally Crystal Hz */
-	cpuid(CPUID_LEAF_TSC, &eax_denominator, &ebx_numerator, &ecx_hz, &edx);
-
-	if (ebx_numerator == 0 || eax_denominator == 0)
-		return 0;
-
-	crystal_khz = ecx_hz / 1000;
-
 	/*
 	 * Denverton SoCs don't report crystal clock, and also don't support
 	 * CPUID_LEAF_FREQ for the calculation below, so hardcode the 25MHz
 	 * crystal clock.
 	 */
-	if (crystal_khz == 0 &&
-			boot_cpu_data.x86_vfm == INTEL_ATOM_GOLDMONT_D)
-		crystal_khz = 25000;
+	if (!info.crystal_khz && boot_cpu_data.x86_vfm == INTEL_ATOM_GOLDMONT_D)
+		info.crystal_khz = 25000;
 
 	/*
 	 * TSC frequency reported directly by CPUID is a "hardware reported"
 	 * frequency and is the most accurate one so far we have. This
 	 * is considered a known frequency.
 	 */
-	if (crystal_khz != 0)
+	if (info.crystal_khz)
 		setup_force_cpu_cap(X86_FEATURE_TSC_KNOWN_FREQ);
 
 	/*
@@ -705,15 +726,15 @@ unsigned long native_calibrate_tsc(void)
 	 * clock, but we can easily calculate it to a high degree of accuracy
 	 * by considering the crystal ratio and the CPU speed.
 	 */
-	if (crystal_khz == 0 && boot_cpu_data.cpuid_level >= CPUID_LEAF_FREQ) {
+	if (!info.crystal_khz && boot_cpu_data.cpuid_level >= CPUID_LEAF_FREQ) {
 		unsigned int eax_base_mhz, ebx, ecx, edx;
 
 		cpuid(CPUID_LEAF_FREQ, &eax_base_mhz, &ebx, &ecx, &edx);
-		crystal_khz = eax_base_mhz * 1000 *
-			eax_denominator / ebx_numerator;
+		info.crystal_khz = eax_base_mhz * 1000 *
+			info.denominator / info.numerator;
 	}
 
-	if (crystal_khz == 0)
+	if (!info.crystal_khz)
 		return 0;
 
 	/*
@@ -730,10 +751,10 @@ unsigned long native_calibrate_tsc(void)
 	 * lapic_timer_period here to avoid having to calibrate the APIC
 	 * timer later.
 	 */
-	lapic_timer_period = crystal_khz * 1000 / HZ;
+	lapic_timer_period = info.crystal_khz * 1000 / HZ;
 #endif
 
-	return crystal_khz * ebx_numerator / eax_denominator;
+	return info.crystal_khz * info.numerator / info.denominator;
 }
 
 static unsigned long cpu_khz_from_cpuid(void)

---

## [4] Sean Christopherson — 2026-05-29
*Subject: [PATCH v4 03/47] x86/sev: Mark TSC as reliable when configuring
 Secure TSC*

Move the code to mark the TSC as reliable from sme_early_init() to
snp_secure_tsc_init().  The only reader of TSC_RELIABLE is the aptly
named check_system_tsc_reliable(), which runs in tsc_init(), i.e.
after snp_secure_tsc_init().

This will allow consolidating the handling of TSC_KNOWN_FREQ and
TSC_RELIABLE when overriding the TSC calibration routine.

Cc: Tom Lendacky <thomas.lendacky@amd.com>
Reviewed-by: Nikunj A Dadhania <nikunj@amd.com>
Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/coco/sev/core.c      | 2 ++
 arch/x86/mm/mem_encrypt_amd.c | 3 ---
 2 files changed, 2 insertions(+), 3 deletions(-)

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index ecd77d3217f3..ed0ac52a765e 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -2037,6 +2037,8 @@ void __init snp_secure_tsc_init(void)
 	secrets = (__force struct snp_secrets_page *)mem;
 
 	setup_force_cpu_cap(X86_FEATURE_TSC_KNOWN_FREQ);
+	setup_force_cpu_cap(X86_FEATURE_TSC_RELIABLE);
+
 	rdmsrq(MSR_AMD64_GUEST_TSC_FREQ, tsc_freq_mhz);
 
 	/* Extract the GUEST TSC MHZ from BIT[17:0], rest is reserved space */
diff --git a/arch/x86/mm/mem_encrypt_amd.c b/arch/x86/mm/mem_encrypt_amd.c
index 2f8c32173972..6c3af974c7c2 100644
--- a/arch/x86/mm/mem_encrypt_amd.c
+++ b/arch/x86/mm/mem_encrypt_amd.c
@@ -535,9 +535,6 @@ void __init sme_early_init(void)
 		 */
 		x86_init.resources.dmi_setup = snp_dmi_setup;
 	}
-
-	if (sev_status & MSR_AMD64_SNP_SECURE_TSC)
-		setup_force_cpu_cap(X86_FEATURE_TSC_RELIABLE);
 }
 
 void __init mem_encrypt_free_decrypted_mem(void)

---

## [5] Sean Christopherson — 2026-05-29
*Subject: [PATCH v4 04/47] x86/sev: Don't override CPU frequency calibration
 for SNP's Secure TSC*

Don't override the kernel's CPU frequency calibration routine when
registering SNP's Secure TSC calibration routine.  SNP (the architecture)
provides zero guarantees that the CPU runs at the same frequency as the
TSC.  The justification for clobbering the CPU routine was:

  Since the difference between CPU base and TSC frequency does not apply
  in this case, the same callback is being used.

but that's simply not true.  E.g. if APERF/MPERF is exposed to the VM, then
the CPU frequency absolutely does matter.

While relying on heuristics and/or the untrusted hypervisor to provide the
CPU frequency isn't ideal, it's at least not outright wrong.

Fixes: 73bbf3b0fbba ("x86/tsc: Init the TSC for Secure TSC guests")
Cc: Nikunj A Dadhania <nikunj@amd.com>
Cc: Tom Lendacky <thomas.lendacky@amd.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/coco/sev/core.c | 1 -
 1 file changed, 1 deletion(-)

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index ed0ac52a765e..665de1aea0ee 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -2046,7 +2046,6 @@ void __init snp_secure_tsc_init(void)
 
 	snp_tsc_freq_khz = SNP_SCALE_TSC_FREQ(tsc_freq_mhz * 1000, secrets->tsc_factor);
 
-	x86_platform.calibrate_cpu = securetsc_get_tsc_khz;
 	x86_platform.calibrate_tsc = securetsc_get_tsc_khz;
 
 	early_memunmap(mem, PAGE_SIZE);

---

## [6] Sean Christopherson — 2026-05-29
*Subject: [PATCH v4 05/47] x86/sev: Move check for SNP Secure TSC support to tsc_early_init()*

Move the check on having a Secure TSC to the common tsc_early_init() so
that it's obvious that having a Secure TSC is conditional, and to prepare
for adding TDX to the mix (blindly initializing *both* SNP and TDX TSC
logic looks especially weird).

No functional change intended.

Cc: Tom Lendacky <thomas.lendacky@amd.com>
Reviewed-by: Nikunj A Dadhania <nikunj@amd.com>
Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/coco/sev/core.c | 3 ---
 arch/x86/kernel/tsc.c    | 3 ++-
 2 files changed, 2 insertions(+), 4 deletions(-)

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index 665de1aea0ee..403dcea86452 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -2025,9 +2025,6 @@ void __init snp_secure_tsc_init(void)
 	unsigned long tsc_freq_mhz;
 	void *mem;
 
-	if (!cc_platform_has(CC_ATTR_GUEST_SNP_SECURE_TSC))
-		return;
-
 	mem = early_memremap_encrypted(sev_secrets_pa, PAGE_SIZE);
 	if (!mem) {
 		pr_err("Unable to get TSC_FACTOR: failed to map the SNP secrets page.\n");
diff --git a/arch/x86/kernel/tsc.c b/arch/x86/kernel/tsc.c
index f7f561722efa..833eed5c048a 100644
--- a/arch/x86/kernel/tsc.c
+++ b/arch/x86/kernel/tsc.c
@@ -1543,7 +1543,8 @@ void __init tsc_early_init(void)
 	if (is_early_uv_system())
 		return;
 
-	snp_secure_tsc_init();
+	if (cc_platform_has(CC_ATTR_GUEST_SNP_SECURE_TSC))
+		snp_secure_tsc_init();
 
 	if (!determine_cpu_tsc_frequencies(true))
 		return;

---

## [7] Sean Christopherson — 2026-05-29
*Subject: [PATCH v4 06/47] x86/sev: Shove SNP's secure/trusted TSC frequency
 directly into "calibration"*

As a first step towards dropping .calibrate_{cpu,tsc}() and explicitly
defining precedence/priority for "calibration" routines, pass the secure
TSC frequency obtained from SNP firmware directly to
determine_cpu_tsc_frequencies() instead of overriding the .calibrate_tsc()
hook.

Unlike the native calibration routines, all of the paravirtual overrides,
including SNP and TDX, are constant in the sense that the frequency
provided by the hypervisor or trusted firmware is fixed, known, and always
available during early boot.  More importantly, for CoCo (SNP and TDX) VMs,
it's imperative that the kernel uses the frequency provided by the trusted
firmware, not by the untrusted hypervisor.  Enforcing the priority between
sources by carefully ordering seemingly unrelated init calls, so that the
trusted override "wins", is brittle and all but impossible to follow.

While it's rather weird, deliberately prioritize tsc_early_khz over all
else to maintain existing behavior.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/coco/sev/core.c   | 14 ++++----------
 arch/x86/include/asm/sev.h |  4 ++--
 arch/x86/kernel/tsc.c      | 19 ++++++++++++-------
 3 files changed, 18 insertions(+), 19 deletions(-)

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index 403dcea86452..bc5ae9ef74da 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -99,7 +99,6 @@ static const char * const sev_status_feat_names[] = {
  */
 static u64 snp_tsc_scale __ro_after_init;
 static u64 snp_tsc_offset __ro_after_init;
-static unsigned long snp_tsc_freq_khz __ro_after_init;
 
 DEFINE_PER_CPU(struct sev_es_runtime_data*, runtime_data);
 DEFINE_PER_CPU(struct sev_es_save_area *, sev_vmsa);
@@ -2014,15 +2013,10 @@ void __init snp_secure_tsc_prepare(void)
 	pr_debug("SecureTSC enabled");
 }
 
-static unsigned long securetsc_get_tsc_khz(void)
-{
-	return snp_tsc_freq_khz;
-}
-
-void __init snp_secure_tsc_init(void)
+unsigned int __init snp_secure_tsc_init(void)
 {
+	unsigned long snp_tsc_freq_khz, tsc_freq_mhz;
 	struct snp_secrets_page *secrets;
-	unsigned long tsc_freq_mhz;
 	void *mem;
 
 	mem = early_memremap_encrypted(sev_secrets_pa, PAGE_SIZE);
@@ -2043,7 +2037,7 @@ void __init snp_secure_tsc_init(void)
 
 	snp_tsc_freq_khz = SNP_SCALE_TSC_FREQ(tsc_freq_mhz * 1000, secrets->tsc_factor);
 
-	x86_platform.calibrate_tsc = securetsc_get_tsc_khz;
-
 	early_memunmap(mem, PAGE_SIZE);
+
+	return snp_tsc_freq_khz;
 }
diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index 594cfa19cbd4..05ebf0b73ef4 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -530,7 +530,7 @@ int snp_send_guest_request(struct snp_msg_desc *mdesc, struct snp_guest_req *req
 int snp_svsm_vtpm_send_command(u8 *buffer);
 
 void __init snp_secure_tsc_prepare(void);
-void __init snp_secure_tsc_init(void);
+unsigned int snp_secure_tsc_init(void);
 enum es_result savic_register_gpa(u64 gpa);
 enum es_result savic_unregister_gpa(u64 *gpa);
 u64 savic_ghcb_msr_read(u32 reg);
@@ -637,7 +637,7 @@ static inline int snp_send_guest_request(struct snp_msg_desc *mdesc,
 					 struct snp_guest_req *req) { return -ENODEV; }
 static inline int snp_svsm_vtpm_send_command(u8 *buffer) { return -ENODEV; }
 static inline void __init snp_secure_tsc_prepare(void) { }
-static inline void __init snp_secure_tsc_init(void) { }
+static inline unsigned int __init snp_secure_tsc_init(void) { return 0; }
 static inline void sev_evict_cache(void *va, int npages) {}
 static inline enum es_result savic_register_gpa(u64 gpa) { return ES_UNSUPPORTED; }
 static inline enum es_result savic_unregister_gpa(u64 *gpa) { return ES_UNSUPPORTED; }
diff --git a/arch/x86/kernel/tsc.c b/arch/x86/kernel/tsc.c
index 833eed5c048a..2b8f94c3fcc7 100644
--- a/arch/x86/kernel/tsc.c
+++ b/arch/x86/kernel/tsc.c
@@ -1474,15 +1474,16 @@ static int __init init_tsc_clocksource(void)
  */
 device_initcall(init_tsc_clocksource);
 
-static bool __init determine_cpu_tsc_frequencies(bool early)
+static bool __init determine_cpu_tsc_frequencies(bool early,
+						 unsigned int known_tsc_khz)
 {
 	/* Make sure that cpu and tsc are not already calibrated */
 	WARN_ON(cpu_khz || tsc_khz);
 
 	if (early) {
 		cpu_khz = x86_platform.calibrate_cpu();
-		if (tsc_early_khz)
-			tsc_khz = tsc_early_khz;
+		if (known_tsc_khz)
+			tsc_khz = known_tsc_khz;
 		else
 			tsc_khz = x86_platform.calibrate_tsc();
 	} else {
@@ -1537,16 +1538,20 @@ static void __init tsc_enable_sched_clock(void)
 
 void __init tsc_early_init(void)
 {
+	unsigned int known_tsc_khz = 0;
+
 	if (!boot_cpu_has(X86_FEATURE_TSC))
 		return;
 	/* Don't change UV TSC multi-chassis synchronization */
 	if (is_early_uv_system())
 		return;
 
-	if (cc_platform_has(CC_ATTR_GUEST_SNP_SECURE_TSC))
-		snp_secure_tsc_init();
+	if (tsc_early_khz)
+		known_tsc_khz = tsc_early_khz;
+	else if (cc_platform_has(CC_ATTR_GUEST_SNP_SECURE_TSC))
+		known_tsc_khz = snp_secure_tsc_init();
 
-	if (!determine_cpu_tsc_frequencies(true))
+	if (!determine_cpu_tsc_frequencies(true, known_tsc_khz))
 		return;
 	tsc_enable_sched_clock();
 }
@@ -1567,7 +1572,7 @@ void __init tsc_init(void)
 
 	if (!tsc_khz) {
 		/* We failed to determine frequencies earlier, try again */
-		if (!determine_cpu_tsc_frequencies(false)) {
+		if (!determine_cpu_tsc_frequencies(false, 0)) {
 			mark_tsc_unstable("could not calculate TSC khz");
 			setup_clear_cpu_cap(X86_FEATURE_TSC_DEADLINE_TIMER);
 			return;

---

## [8] Sean Christopherson — 2026-05-29
*Subject: [PATCH v4 07/47] x86/tdx: Force TSC frequency with CPUID-based info
 provided by the TDX-Module*

When running as a TDX guest, explicitly set the TSC frequency to a known
value, using CPUID-based information, instead of potentially relying on a
hypervisor-controlled PV routine.  For TDX guests, CPUID.0x15 is always
emulated by the TDX-Module, i.e. the information from CPUID is more
trustworthy than the information provided by the hypervisor.

To maintain backwards compatibility with TDX guest kernels that use native
calibration, and because it's the least awful option, retain
native_calibrate_tsc()'s stuffing of the local APIC bus period using the
core crystal frequency.  While it's entirely possible for the hypervisor
to emulate the APIC timer at a different frequency than the core crystal
frequency, the commonly accepted interpretation of Intel's SDM is that APIC
timer runs at the core crystal frequency when that latter is enumerated via
CPUID:

  The APIC timer frequency will be the processor’s bus clock or core
  crystal clock frequency (when TSC/core crystal clock ratio is enumerated
  in CPUID leaf 0x15).

If the hypervisor is malicious and deliberately runs the APIC timer at the
wrong frequency, nothing would stop the hypervisor from modifying the
frequency at any time, i.e. attempting to manually calibrate the frequency
out of paranoia would be futile.

Deliberately leave CPU frequency calibration as is, since the TDX-Module
doesn't provide any guarantees with respect to CPUID.0x16.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/coco/tdx/tdx.c    | 20 +++++++++++++++++---
 arch/x86/include/asm/tdx.h |  2 ++
 arch/x86/kernel/tsc.c      |  3 +++
 3 files changed, 22 insertions(+), 3 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 29b6f1ed59ec..5d7976359220 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -8,6 +8,7 @@
 #include <linux/export.h>
 #include <linux/io.h>
 #include <linux/kexec.h>
+#include <asm/apic.h>
 #include <asm/coco.h>
 #include <asm/tdx.h>
 #include <asm/vmx.h>
@@ -1123,9 +1124,6 @@ void __init tdx_early_init(void)
 
 	setup_force_cpu_cap(X86_FEATURE_TDX_GUEST);
 
-	/* TSC is the only reliable clock in TDX guest */
-	setup_force_cpu_cap(X86_FEATURE_TSC_RELIABLE);
-
 	cc_vendor = CC_VENDOR_INTEL;
 
 	/* Configure the TD */
@@ -1195,3 +1193,19 @@ void __init tdx_early_init(void)
 
 	tdx_announce();
 }
+
+unsigned int __init tdx_tsc_init(void)
+{
+	struct cpuid_tsc_info info;
+
+	if (WARN_ON_ONCE(cpuid_get_tsc_freq(&info)))
+		return 0;
+
+	lapic_timer_period = info.crystal_khz * 1000 / HZ;
+
+	/* TSC is the only reliable clock in TDX guest */
+	setup_force_cpu_cap(X86_FEATURE_TSC_RELIABLE);
+	setup_force_cpu_cap(X86_FEATURE_TSC_KNOWN_FREQ);
+
+	return info.tsc_khz;
+}
diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index e5a9cf656c07..1d841d464aa4 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -67,6 +67,7 @@ struct ve_info {
 #ifdef CONFIG_INTEL_TDX_GUEST
 
 void __init tdx_early_init(void);
+unsigned int __init tdx_tsc_init(void);
 
 void tdx_get_ve_info(struct ve_info *ve);
 
@@ -88,6 +89,7 @@ void __init tdx_dump_td_ctls(u64 td_ctls);
 #else
 
 static inline void tdx_early_init(void) { };
+static inline unsigned int tdx_tsc_init(void) { return 0; }
 static inline void tdx_halt(void) { };
 
 static inline bool tdx_early_handle_ve(struct pt_regs *regs) { return false; }
diff --git a/arch/x86/kernel/tsc.c b/arch/x86/kernel/tsc.c
index 2b8f94c3fcc7..2603f136e29b 100644
--- a/arch/x86/kernel/tsc.c
+++ b/arch/x86/kernel/tsc.c
@@ -34,6 +34,7 @@
 #include <asm/topology.h>
 #include <asm/uv/uv.h>
 #include <asm/sev.h>
+#include <asm/tdx.h>
 
 unsigned int __read_mostly cpu_khz;	/* TSC clocks / usec, not used here */
 EXPORT_SYMBOL(cpu_khz);
@@ -1550,6 +1551,8 @@ void __init tsc_early_init(void)
 		known_tsc_khz = tsc_early_khz;
 	else if (cc_platform_has(CC_ATTR_GUEST_SNP_SECURE_TSC))
 		known_tsc_khz = snp_secure_tsc_init();
+	else if (boot_cpu_has(X86_FEATURE_TDX_GUEST))
+		known_tsc_khz = tdx_tsc_init();
 
 	if (!determine_cpu_tsc_frequencies(true, known_tsc_khz))
 		return;

---

## [9] Sean Christopherson — 2026-05-29
*Subject: [PATCH v4 08/47] x86/tsc: Add dedicated hypervisor hooks for getting
 known TSC/CPU frequencies*

Add dedicated hypervisor hooks for getting known TSC/CPU frequencies
instead of overriding seemingly generic platform hooks, and explicitly
priotize hypervisor-provided frequencies over native methods, but do NOT
clobber the frequency obtained from trusted firmware.  While shuffling the
hooks around is arguably "six of one, half dozen of the other", scoping
them to x86_hyper_init makes their purpose more obvious, and allows for
explicitly defining the priority of sources (as is done here).

Cc: David Woodhouse <dwmw2@infradead.org>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/acrn.h     |  5 -----
 arch/x86/include/asm/x86_init.h |  4 ++++
 arch/x86/kernel/cpu/acrn.c      | 10 +++++++---
 arch/x86/kernel/cpu/mshyperv.c  |  6 +++---
 arch/x86/kernel/cpu/vmware.c    |  8 ++++----
 arch/x86/kernel/jailhouse.c     |  6 +++---
 arch/x86/kernel/kvmclock.c      |  6 +++---
 arch/x86/kernel/tsc.c           | 23 +++++++++++++++++++----
 arch/x86/xen/time.c             |  4 ++--
 9 files changed, 45 insertions(+), 27 deletions(-)

diff --git a/arch/x86/include/asm/acrn.h b/arch/x86/include/asm/acrn.h
index db42b477c41d..a892179c61c6 100644
--- a/arch/x86/include/asm/acrn.h
+++ b/arch/x86/include/asm/acrn.h
@@ -32,11 +32,6 @@ static inline u32 acrn_cpuid_base(void)
 	return 0;
 }
 
-static inline unsigned long acrn_get_tsc_khz(void)
-{
-	return cpuid_eax(ACRN_CPUID_TIMING_INFO);
-}
-
 /*
  * Hypercalls for ACRN
  *
diff --git a/arch/x86/include/asm/x86_init.h b/arch/x86/include/asm/x86_init.h
index 6c8a6ead84f6..a4f8a4aa601d 100644
--- a/arch/x86/include/asm/x86_init.h
+++ b/arch/x86/include/asm/x86_init.h
@@ -120,6 +120,8 @@ struct x86_init_pci {
  * @msi_ext_dest_id:		MSI supports 15-bit APIC IDs
  * @init_mem_mapping:		setup early mappings during init_mem_mapping()
  * @init_after_bootmem:		guest init after boot allocator is finished
+ * @get_tsc_khz:		get the TSC frequency (returns 0 if frequency is unknown)
+ * @get_cpu_khz:		get the CPU frequency (returns 0 if frequency is unknown)
  */
 struct x86_hyper_init {
 	void (*init_platform)(void);
@@ -128,6 +130,8 @@ struct x86_hyper_init {
 	bool (*msi_ext_dest_id)(void);
 	void (*init_mem_mapping)(void);
 	void (*init_after_bootmem)(void);
+	unsigned int (*get_tsc_khz)(void);
+	unsigned int (*get_cpu_khz)(void);
 };
 
 /**
diff --git a/arch/x86/kernel/cpu/acrn.c b/arch/x86/kernel/cpu/acrn.c
index dc119af83524..ad8f2da8003b 100644
--- a/arch/x86/kernel/cpu/acrn.c
+++ b/arch/x86/kernel/cpu/acrn.c
@@ -24,13 +24,15 @@ static u32 __init acrn_detect(void)
 	return acrn_cpuid_base();
 }
 
+static unsigned int __init acrn_get_tsc_khz(void)
+{
+	return cpuid_eax(ACRN_CPUID_TIMING_INFO);
+}
+
 static void __init acrn_init_platform(void)
 {
 	/* Install system interrupt handler for ACRN hypervisor callback */
 	sysvec_install(HYPERVISOR_CALLBACK_VECTOR, sysvec_acrn_hv_callback);
-
-	x86_platform.calibrate_tsc = acrn_get_tsc_khz;
-	x86_platform.calibrate_cpu = acrn_get_tsc_khz;
 }
 
 static bool acrn_x2apic_available(void)
@@ -78,4 +80,6 @@ const __initconst struct hypervisor_x86 x86_hyper_acrn = {
 	.type			= X86_HYPER_ACRN,
 	.init.init_platform     = acrn_init_platform,
 	.init.x2apic_available  = acrn_x2apic_available,
+	.init.get_tsc_khz	= acrn_get_tsc_khz,
+	.init.get_cpu_khz	= acrn_get_tsc_khz,
 };
diff --git a/arch/x86/kernel/cpu/mshyperv.c b/arch/x86/kernel/cpu/mshyperv.c
index 185d4f677ec0..733e12d5a7dd 100644
--- a/arch/x86/kernel/cpu/mshyperv.c
+++ b/arch/x86/kernel/cpu/mshyperv.c
@@ -395,7 +395,7 @@ static int hv_nmi_unknown(unsigned int val, struct pt_regs *regs)
 }
 #endif
 
-static unsigned long hv_get_tsc_khz(void)
+static unsigned int __init hv_get_tsc_khz(void)
 {
 	unsigned long freq;
 
@@ -573,8 +573,8 @@ static void __init ms_hyperv_init_platform(void)
 
 	if (ms_hyperv.features & HV_ACCESS_FREQUENCY_MSRS &&
 	    ms_hyperv.misc_features & HV_FEATURE_FREQUENCY_MSRS_AVAILABLE) {
-		x86_platform.calibrate_tsc = hv_get_tsc_khz;
-		x86_platform.calibrate_cpu = hv_get_tsc_khz;
+		x86_init.hyper.get_tsc_khz = hv_get_tsc_khz;
+		x86_init.hyper.get_cpu_khz = hv_get_tsc_khz;
 		setup_force_cpu_cap(X86_FEATURE_TSC_KNOWN_FREQ);
 	}
 
diff --git a/arch/x86/kernel/cpu/vmware.c b/arch/x86/kernel/cpu/vmware.c
index 34b73573b108..7c8cf4885e82 100644
--- a/arch/x86/kernel/cpu/vmware.c
+++ b/arch/x86/kernel/cpu/vmware.c
@@ -64,7 +64,7 @@ struct vmware_steal_time {
 	u64 reserved[7];
 };
 
-static unsigned long vmware_tsc_khz __ro_after_init;
+static unsigned long vmware_tsc_khz __initdata;
 static u8 vmware_hypercall_mode     __ro_after_init;
 
 unsigned long vmware_hypercall_slow(unsigned long cmd,
@@ -137,7 +137,7 @@ static inline int __vmware_platform(void)
 	return eax != UINT_MAX && ebx == VMWARE_HYPERVISOR_MAGIC;
 }
 
-static unsigned long vmware_get_tsc_khz(void)
+static unsigned int __init vmware_get_tsc_khz(void)
 {
 	return vmware_tsc_khz;
 }
@@ -419,8 +419,8 @@ static void __init vmware_platform_setup(void)
 		}
 
 		vmware_tsc_khz = tsc_khz;
-		x86_platform.calibrate_tsc = vmware_get_tsc_khz;
-		x86_platform.calibrate_cpu = vmware_get_tsc_khz;
+		x86_init.hyper.get_tsc_khz = vmware_get_tsc_khz;
+		x86_init.hyper.get_cpu_khz = vmware_get_tsc_khz;
 
 #ifdef CONFIG_X86_LOCAL_APIC
 		/* Skip lapic calibration since we know the bus frequency. */
diff --git a/arch/x86/kernel/jailhouse.c b/arch/x86/kernel/jailhouse.c
index f58ce9220e0f..4034e08c5f11 100644
--- a/arch/x86/kernel/jailhouse.c
+++ b/arch/x86/kernel/jailhouse.c
@@ -68,7 +68,7 @@ static void __init jailhouse_timer_init(void)
 	lapic_timer_period = setup_data.v1.apic_khz * (1000 / HZ);
 }
 
-static unsigned long jailhouse_get_tsc(void)
+static unsigned int __init jailhouse_get_tsc(void)
 {
 	return precalibrated_tsc_khz;
 }
@@ -210,8 +210,6 @@ static void __init jailhouse_init_platform(void)
 	x86_init.mpparse.parse_smp_cfg		= jailhouse_parse_smp_config;
 	x86_init.pci.arch_init			= jailhouse_pci_arch_init;
 
-	x86_platform.calibrate_cpu		= jailhouse_get_tsc;
-	x86_platform.calibrate_tsc		= jailhouse_get_tsc;
 	x86_platform.get_wallclock		= jailhouse_get_wallclock;
 	x86_platform.legacy.rtc			= 0;
 	x86_platform.legacy.warm_reset		= 0;
@@ -293,5 +291,7 @@ const struct hypervisor_x86 x86_hyper_jailhouse __refconst = {
 	.detect			= jailhouse_detect,
 	.init.init_platform	= jailhouse_init_platform,
 	.init.x2apic_available	= jailhouse_x2apic_available,
+	.init.get_tsc_khz	= jailhouse_get_tsc,
+	.init.get_cpu_khz	= jailhouse_get_tsc,
 	.ignore_nopv		= true,
 };
diff --git a/arch/x86/kernel/kvmclock.c b/arch/x86/kernel/kvmclock.c
index b5991d53fc0e..ec888eef74aa 100644
--- a/arch/x86/kernel/kvmclock.c
+++ b/arch/x86/kernel/kvmclock.c
@@ -115,7 +115,7 @@ static inline void kvm_sched_clock_init(bool stable)
  * poll of guests can be running and trouble each other. So we preset
  * lpj here
  */
-static unsigned long kvm_get_tsc_khz(void)
+static unsigned int __init kvm_get_tsc_khz(void)
 {
 	setup_force_cpu_cap(X86_FEATURE_TSC_KNOWN_FREQ);
 	return pvclock_tsc_khz(this_cpu_pvti());
@@ -321,8 +321,8 @@ void __init kvmclock_init(void)
 	flags = pvclock_read_flags(&hv_clock_boot[0].pvti);
 	kvm_sched_clock_init(flags & PVCLOCK_TSC_STABLE_BIT);
 
-	x86_platform.calibrate_tsc = kvm_get_tsc_khz;
-	x86_platform.calibrate_cpu = kvm_get_tsc_khz;
+	x86_init.hyper.get_tsc_khz = kvm_get_tsc_khz;
+	x86_init.hyper.get_cpu_khz = kvm_get_tsc_khz;
 	x86_platform.get_wallclock = kvm_get_wallclock;
 	x86_platform.set_wallclock = kvm_set_wallclock;
 #ifdef CONFIG_X86_LOCAL_APIC
diff --git a/arch/x86/kernel/tsc.c b/arch/x86/kernel/tsc.c
index 2603f136e29b..362596612442 100644
--- a/arch/x86/kernel/tsc.c
+++ b/arch/x86/kernel/tsc.c
@@ -1476,13 +1476,17 @@ static int __init init_tsc_clocksource(void)
 device_initcall(init_tsc_clocksource);
 
 static bool __init determine_cpu_tsc_frequencies(bool early,
+						 unsigned int known_cpu_khz,
 						 unsigned int known_tsc_khz)
 {
 	/* Make sure that cpu and tsc are not already calibrated */
 	WARN_ON(cpu_khz || tsc_khz);
 
 	if (early) {
-		cpu_khz = x86_platform.calibrate_cpu();
+		if (known_cpu_khz)
+			cpu_khz = known_cpu_khz;
+		else
+			cpu_khz = x86_platform.calibrate_cpu();
 		if (known_tsc_khz)
 			tsc_khz = known_tsc_khz;
 		else
@@ -1539,7 +1543,7 @@ static void __init tsc_enable_sched_clock(void)
 
 void __init tsc_early_init(void)
 {
-	unsigned int known_tsc_khz = 0;
+	unsigned int known_cpu_khz = 0, known_tsc_khz = 0;
 
 	if (!boot_cpu_has(X86_FEATURE_TSC))
 		return;
@@ -1547,6 +1551,9 @@ void __init tsc_early_init(void)
 	if (is_early_uv_system())
 		return;
 
+	if (x86_init.hyper.get_cpu_khz)
+		known_cpu_khz = x86_init.hyper.get_cpu_khz();
+
 	if (tsc_early_khz)
 		known_tsc_khz = tsc_early_khz;
 	else if (cc_platform_has(CC_ATTR_GUEST_SNP_SECURE_TSC))
@@ -1554,7 +1561,15 @@ void __init tsc_early_init(void)
 	else if (boot_cpu_has(X86_FEATURE_TDX_GUEST))
 		known_tsc_khz = tdx_tsc_init();
 
-	if (!determine_cpu_tsc_frequencies(true, known_tsc_khz))
+	/*
+	 * If the TSC frequency is still unknown, i.e. not provided by the user
+	 * or by trusted firmware, try to get it from the hypervisor (which is
+	 * untrusted when running as a CoCo guest).
+	 */
+	if (!known_tsc_khz && x86_init.hyper.get_tsc_khz)
+		known_tsc_khz = x86_init.hyper.get_tsc_khz();
+
+	if (!determine_cpu_tsc_frequencies(true, known_cpu_khz, known_tsc_khz))
 		return;
 	tsc_enable_sched_clock();
 }
@@ -1575,7 +1590,7 @@ void __init tsc_init(void)
 
 	if (!tsc_khz) {
 		/* We failed to determine frequencies earlier, try again */
-		if (!determine_cpu_tsc_frequencies(false, 0)) {
+		if (!determine_cpu_tsc_frequencies(false, 0, 0)) {
 			mark_tsc_unstable("could not calculate TSC khz");
 			setup_clear_cpu_cap(X86_FEATURE_TSC_DEADLINE_TIMER);
 			return;
diff --git a/arch/x86/xen/time.c b/arch/x86/xen/time.c
index d62c14334b35..1adb44fdddb2 100644
--- a/arch/x86/xen/time.c
+++ b/arch/x86/xen/time.c
@@ -38,7 +38,7 @@
 static u64 xen_sched_clock_offset __read_mostly;
 
 /* Get the TSC speed from Xen */
-static unsigned long xen_tsc_khz(void)
+static unsigned int __init xen_tsc_khz(void)
 {
 	struct pvclock_vcpu_time_info *info =
 		&HYPERVISOR_shared_info->vcpu_info[0].time;
@@ -569,7 +569,7 @@ static void __init xen_init_time_common(void)
 	static_call_update(pv_steal_clock, xen_steal_clock);
 	paravirt_set_sched_clock(xen_sched_clock);
 
-	x86_platform.calibrate_tsc = xen_tsc_khz;
+	x86_init.hyper.get_tsc_khz = xen_tsc_khz;
 	x86_platform.get_wallclock = xen_get_wallclock;
 }

---

## [10] Sean Christopherson — 2026-05-29
*Subject: [PATCH v4 09/47] x86/acrn: Mark TSC frequency as known when using
 ACRN for calibration*

Mark the TSC frequency as known when using ACRN's PV CPUID information.
Per commit 81a71f51b89e ("x86/acrn: Set up timekeeping") and common sense,
the TSC freq is explicitly provided by the hypervisor.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kernel/cpu/acrn.c | 2 ++
 1 file changed, 2 insertions(+)

diff --git a/arch/x86/kernel/cpu/acrn.c b/arch/x86/kernel/cpu/acrn.c
index ad8f2da8003b..0303fe6a2efa 100644
--- a/arch/x86/kernel/cpu/acrn.c
+++ b/arch/x86/kernel/cpu/acrn.c
@@ -33,6 +33,8 @@ static void __init acrn_init_platform(void)
 {
 	/* Install system interrupt handler for ACRN hypervisor callback */
 	sysvec_install(HYPERVISOR_CALLBACK_VECTOR, sysvec_acrn_hv_callback);
+
+	setup_force_cpu_cap(X86_FEATURE_TSC_KNOWN_FREQ);
 }
 
 static bool acrn_x2apic_available(void)

---

## [11] Sean Christopherson — 2026-05-29
*Subject: [PATCH v4 10/47] x86/tsc: Consolidate forcing of X86_FEATURE_TSC_KNOWN_FREQ
 for PV code*

Now that all paravirt code that explicitly specifies the TSC frequency
also sets X86_FEATURE_TSC_KNOWN_FREQ, replace all of the one-off code
and simply set X86_FEATURE_TSC_KNOWN_FREQ if the TSC frequency is known.

Do NOT force set TSC_KNOWN_FREQ if the "known" TSC frequency was provided
by the user.  Per commit bd35c77e32e4 ("x86/tsc: Add tsc_early_khz command
line parameter"), one of the goals of the param is to allow the refined
calibration work "to do meaningful error checking".

Note, preferring the user-provided TSC frequency over the frequency from
the hypervisor or trusted firmware, while simultaneously not treating the
user-provided frequency as gospel, is obviously incongruous.  Sweep the
problem under the rug for now to avoid opening a big can of worms that
likely doesn't have a great answer.

No functional change intended.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/coco/sev/core.c       | 1 -
 arch/x86/coco/tdx/tdx.c        | 1 -
 arch/x86/kernel/cpu/acrn.c     | 2 --
 arch/x86/kernel/cpu/mshyperv.c | 1 -
 arch/x86/kernel/cpu/vmware.c   | 2 --
 arch/x86/kernel/jailhouse.c    | 1 -
 arch/x86/kernel/kvmclock.c     | 1 -
 arch/x86/kernel/tsc.c          | 9 +++++++++
 arch/x86/xen/time.c            | 1 -
 9 files changed, 9 insertions(+), 10 deletions(-)

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index bc5ae9ef74da..72313b36b6f5 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -2027,7 +2027,6 @@ unsigned int __init snp_secure_tsc_init(void)
 
 	secrets = (__force struct snp_secrets_page *)mem;
 
-	setup_force_cpu_cap(X86_FEATURE_TSC_KNOWN_FREQ);
 	setup_force_cpu_cap(X86_FEATURE_TSC_RELIABLE);
 
 	rdmsrq(MSR_AMD64_GUEST_TSC_FREQ, tsc_freq_mhz);
diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 5d7976359220..ab463c2b2dab 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -1205,7 +1205,6 @@ unsigned int __init tdx_tsc_init(void)
 
 	/* TSC is the only reliable clock in TDX guest */
 	setup_force_cpu_cap(X86_FEATURE_TSC_RELIABLE);
-	setup_force_cpu_cap(X86_FEATURE_TSC_KNOWN_FREQ);
 
 	return info.tsc_khz;
 }
diff --git a/arch/x86/kernel/cpu/acrn.c b/arch/x86/kernel/cpu/acrn.c
index 0303fe6a2efa..ad8f2da8003b 100644
--- a/arch/x86/kernel/cpu/acrn.c
+++ b/arch/x86/kernel/cpu/acrn.c
@@ -33,8 +33,6 @@ static void __init acrn_init_platform(void)
 {
 	/* Install system interrupt handler for ACRN hypervisor callback */
 	sysvec_install(HYPERVISOR_CALLBACK_VECTOR, sysvec_acrn_hv_callback);
-
-	setup_force_cpu_cap(X86_FEATURE_TSC_KNOWN_FREQ);
 }
 
 static bool acrn_x2apic_available(void)
diff --git a/arch/x86/kernel/cpu/mshyperv.c b/arch/x86/kernel/cpu/mshyperv.c
index 733e12d5a7dd..f8653fc05a40 100644
--- a/arch/x86/kernel/cpu/mshyperv.c
+++ b/arch/x86/kernel/cpu/mshyperv.c
@@ -575,7 +575,6 @@ static void __init ms_hyperv_init_platform(void)
 	    ms_hyperv.misc_features & HV_FEATURE_FREQUENCY_MSRS_AVAILABLE) {
 		x86_init.hyper.get_tsc_khz = hv_get_tsc_khz;
 		x86_init.hyper.get_cpu_khz = hv_get_tsc_khz;
-		setup_force_cpu_cap(X86_FEATURE_TSC_KNOWN_FREQ);
 	}
 
 	if (ms_hyperv.priv_high & HV_ISOLATION) {
diff --git a/arch/x86/kernel/cpu/vmware.c b/arch/x86/kernel/cpu/vmware.c
index 7c8cf4885e82..2d0624c66799 100644
--- a/arch/x86/kernel/cpu/vmware.c
+++ b/arch/x86/kernel/cpu/vmware.c
@@ -390,8 +390,6 @@ static void __init vmware_set_capabilities(void)
 {
 	setup_force_cpu_cap(X86_FEATURE_CONSTANT_TSC);
 	setup_force_cpu_cap(X86_FEATURE_TSC_RELIABLE);
-	if (vmware_tsc_khz)
-		setup_force_cpu_cap(X86_FEATURE_TSC_KNOWN_FREQ);
 	if (vmware_hypercall_mode == CPUID_VMWARE_FEATURES_ECX_VMCALL)
 		setup_force_cpu_cap(X86_FEATURE_VMCALL);
 	else if (vmware_hypercall_mode == CPUID_VMWARE_FEATURES_ECX_VMMCALL)
diff --git a/arch/x86/kernel/jailhouse.c b/arch/x86/kernel/jailhouse.c
index 4034e08c5f11..e4d7d9e2cd69 100644
--- a/arch/x86/kernel/jailhouse.c
+++ b/arch/x86/kernel/jailhouse.c
@@ -255,7 +255,6 @@ static void __init jailhouse_init_platform(void)
 	pr_debug("Jailhouse: PM-Timer IO Port: %#x\n", pmtmr_ioport);
 
 	precalibrated_tsc_khz = setup_data.v1.tsc_khz;
-	setup_force_cpu_cap(X86_FEATURE_TSC_KNOWN_FREQ);
 
 	pci_probe = 0;
 
diff --git a/arch/x86/kernel/kvmclock.c b/arch/x86/kernel/kvmclock.c
index ec888eef74aa..69752b170e0a 100644
--- a/arch/x86/kernel/kvmclock.c
+++ b/arch/x86/kernel/kvmclock.c
@@ -117,7 +117,6 @@ static inline void kvm_sched_clock_init(bool stable)
  */
 static unsigned int __init kvm_get_tsc_khz(void)
 {
-	setup_force_cpu_cap(X86_FEATURE_TSC_KNOWN_FREQ);
 	return pvclock_tsc_khz(this_cpu_pvti());
 }
 
diff --git a/arch/x86/kernel/tsc.c b/arch/x86/kernel/tsc.c
index 362596612442..8cef918486db 100644
--- a/arch/x86/kernel/tsc.c
+++ b/arch/x86/kernel/tsc.c
@@ -1569,6 +1569,15 @@ void __init tsc_early_init(void)
 	if (!known_tsc_khz && x86_init.hyper.get_tsc_khz)
 		known_tsc_khz = x86_init.hyper.get_tsc_khz();
 
+	/*
+	 * Mark the TSC frequency as known if it was obtained from a hypervisor
+	 * or trusted firmware.  Don't mark the frequency as known if the user
+	 * specified the frequency, as the user-provided frequency is intended
+	 * as a "starting point", not a known, guaranteed frequency.
+	 */
+	if (known_tsc_khz && !tsc_early_khz)
+		setup_force_cpu_cap(X86_FEATURE_TSC_KNOWN_FREQ);
+
 	if (!determine_cpu_tsc_frequencies(true, known_cpu_khz, known_tsc_khz))
 		return;
 	tsc_enable_sched_clock();
diff --git a/arch/x86/xen/time.c b/arch/x86/xen/time.c
index 1adb44fdddb2..487ad838c441 100644
--- a/arch/x86/xen/time.c
+++ b/arch/x86/xen/time.c
@@ -43,7 +43,6 @@ static unsigned int __init xen_tsc_khz(void)
 	struct pvclock_vcpu_time_info *info =
 		&HYPERVISOR_shared_info->vcpu_info[0].time;
 
-	setup_force_cpu_cap(X86_FEATURE_TSC_KNOWN_FREQ);
 	return pvclock_tsc_khz(info);
 }

---

## [12] Sean Christopherson — 2026-05-29
*Subject: [PATCH v4 11/47] x86/tsc: Kill off x86_platform_ops.calibrate_{cpu,tsc}()
 hooks*

Now that getting the CPU and/or TSC frequencies from the hypervisor uses
dedicated hooks, drop x86_platform_ops.calibrate_{cpu,tsc}() and instead
directly invoke the correct helper at each phase of (re)calibration.  In
addition to eliminating unnecessary code, this makes it a bit more obvious
when the "late" path invokes pit_hpet_ptimer_calibrate_cpu() instead of
x86_platform_ops.calibrate_cpu().

No functional change intended.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/tsc.h      |  2 --
 arch/x86/include/asm/x86_init.h |  4 ----
 arch/x86/kernel/tsc.c           | 28 ++++++++++++----------------
 arch/x86/kernel/x86_init.c      |  2 --
 4 files changed, 12 insertions(+), 24 deletions(-)

diff --git a/arch/x86/include/asm/tsc.h b/arch/x86/include/asm/tsc.h
index 6cf26e62e9a6..4a224f99c3b9 100644
--- a/arch/x86/include/asm/tsc.h
+++ b/arch/x86/include/asm/tsc.h
@@ -97,8 +97,6 @@ extern void mark_tsc_unstable(char *reason);
 extern int unsynchronized_tsc(void);
 extern int check_tsc_unstable(void);
 extern void mark_tsc_async_resets(char *reason);
-extern unsigned long native_calibrate_cpu_early(void);
-extern unsigned long native_calibrate_tsc(void);
 extern unsigned long long native_sched_clock_from_tsc(u64 tsc);
 
 extern int tsc_clocksource_reliable;
diff --git a/arch/x86/include/asm/x86_init.h b/arch/x86/include/asm/x86_init.h
index a4f8a4aa601d..ada17827ea51 100644
--- a/arch/x86/include/asm/x86_init.h
+++ b/arch/x86/include/asm/x86_init.h
@@ -292,8 +292,6 @@ struct x86_hyper_runtime {
 
 /**
  * struct x86_platform_ops - platform specific runtime functions
- * @calibrate_cpu:		calibrate CPU
- * @calibrate_tsc:		calibrate TSC, if different from CPU
  * @get_wallclock:		get time from HW clock like RTC etc.
  * @set_wallclock:		set time back to HW clock
  * @iommu_shutdown:		set by an IOMMU driver for shutdown if necessary
@@ -317,8 +315,6 @@ struct x86_hyper_runtime {
  * @guest:			guest incarnations callbacks
  */
 struct x86_platform_ops {
-	unsigned long (*calibrate_cpu)(void);
-	unsigned long (*calibrate_tsc)(void);
 	void (*get_wallclock)(struct timespec64 *ts);
 	int (*set_wallclock)(const struct timespec64 *ts);
 	void (*iommu_shutdown)(void);
diff --git a/arch/x86/kernel/tsc.c b/arch/x86/kernel/tsc.c
index 8cef918486db..5b4b6e43c94c 100644
--- a/arch/x86/kernel/tsc.c
+++ b/arch/x86/kernel/tsc.c
@@ -696,7 +696,7 @@ int __init cpuid_get_tsc_freq(struct cpuid_tsc_info *info)
  * native_calibrate_tsc - determine TSC frequency
  * Determine TSC frequency via CPUID, else return 0.
  */
-unsigned long native_calibrate_tsc(void)
+static unsigned long native_calibrate_tsc(void)
 {
 	struct cpuid_tsc_info info;
 
@@ -931,7 +931,7 @@ static unsigned long pit_hpet_ptimer_calibrate_cpu(void)
 /**
  * native_calibrate_cpu_early - can calibrate the cpu early in boot
  */
-unsigned long native_calibrate_cpu_early(void)
+static unsigned long native_calibrate_cpu_early(void)
 {
 	unsigned long flags, fast_calibrate = cpu_khz_from_cpuid();
 
@@ -945,7 +945,7 @@ unsigned long native_calibrate_cpu_early(void)
 	return fast_calibrate;
 }
 
-
+#ifndef CONFIG_SMP
 /**
  * native_calibrate_cpu - calibrate the cpu
  */
@@ -958,6 +958,7 @@ static unsigned long native_calibrate_cpu(void)
 
 	return tsc_freq;
 }
+#endif
 
 void recalibrate_cpu_khz(void)
 {
@@ -967,9 +968,9 @@ void recalibrate_cpu_khz(void)
 	if (!boot_cpu_has(X86_FEATURE_TSC))
 		return;
 
-	cpu_khz = x86_platform.calibrate_cpu();
+	cpu_khz = native_calibrate_cpu();
 	if (!boot_cpu_has(X86_FEATURE_TSC_KNOWN_FREQ))
-		tsc_khz = x86_platform.calibrate_tsc();
+		tsc_khz = native_calibrate_tsc();
 	if (tsc_khz == 0)
 		tsc_khz = cpu_khz;
 	else if (abs(cpu_khz - tsc_khz) * 10 > tsc_khz)
@@ -1483,17 +1484,19 @@ static bool __init determine_cpu_tsc_frequencies(bool early,
 	WARN_ON(cpu_khz || tsc_khz);
 
 	if (early) {
+		/*
+		 * Early CPU calibration can only use methods that are available
+		 * early in boot (obviously).
+		 */
 		if (known_cpu_khz)
 			cpu_khz = known_cpu_khz;
 		else
-			cpu_khz = x86_platform.calibrate_cpu();
+			cpu_khz = native_calibrate_cpu_early();
 		if (known_tsc_khz)
 			tsc_khz = known_tsc_khz;
 		else
-			tsc_khz = x86_platform.calibrate_tsc();
+			tsc_khz = native_calibrate_tsc();
 	} else {
-		/* We should not be here with non-native cpu calibration */
-		WARN_ON(x86_platform.calibrate_cpu != native_calibrate_cpu);
 		cpu_khz = pit_hpet_ptimer_calibrate_cpu();
 	}
 
@@ -1590,13 +1593,6 @@ void __init tsc_init(void)
 		return;
 	}
 
-	/*
-	 * native_calibrate_cpu_early can only calibrate using methods that are
-	 * available early in boot.
-	 */
-	if (x86_platform.calibrate_cpu == native_calibrate_cpu_early)
-		x86_platform.calibrate_cpu = native_calibrate_cpu;
-
 	if (!tsc_khz) {
 		/* We failed to determine frequencies earlier, try again */
 		if (!determine_cpu_tsc_frequencies(false, 0, 0)) {
diff --git a/arch/x86/kernel/x86_init.c b/arch/x86/kernel/x86_init.c
index ebefb77c37bb..c674cbbd466d 100644
--- a/arch/x86/kernel/x86_init.c
+++ b/arch/x86/kernel/x86_init.c
@@ -144,8 +144,6 @@ static void enc_kexec_finish_noop(void) {}
 static bool is_private_mmio_noop(u64 addr) {return false; }
 
 struct x86_platform_ops x86_platform __ro_after_init = {
-	.calibrate_cpu			= native_calibrate_cpu_early,
-	.calibrate_tsc			= native_calibrate_tsc,
 	.get_wallclock			= mach_get_cmos_time,
 	.set_wallclock			= mach_set_cmos_time,
 	.iommu_shutdown			= iommu_shutdown_noop,

---

## [13] Sean Christopherson — 2026-05-29
*Subject: [PATCH v4 12/47] x86/tsc: Rename pit_hpet_ptimer_calibrate_cpu() => native_calibrate_cpu_late()*

Rename the late CPU calibration routine so that its relationship to the
early routine is more obvious and intuitive.

No functional change intended.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kernel/tsc.c | 6 +++---
 1 file changed, 3 insertions(+), 3 deletions(-)

diff --git a/arch/x86/kernel/tsc.c b/arch/x86/kernel/tsc.c
index 5b4b6e43c94c..534462c81c78 100644
--- a/arch/x86/kernel/tsc.c
+++ b/arch/x86/kernel/tsc.c
@@ -779,7 +779,7 @@ static unsigned long cpu_khz_from_cpuid(void)
  * calibrate cpu using pit, hpet, and ptimer methods. They are available
  * later in boot after acpi is initialized.
  */
-static unsigned long pit_hpet_ptimer_calibrate_cpu(void)
+static unsigned long native_calibrate_cpu_late(void)
 {
 	u64 tsc1, tsc2, delta, ref1, ref2;
 	unsigned long tsc_pit_min = ULONG_MAX, tsc_ref_min = ULONG_MAX;
@@ -954,7 +954,7 @@ static unsigned long native_calibrate_cpu(void)
 	unsigned long tsc_freq = native_calibrate_cpu_early();
 
 	if (!tsc_freq)
-		tsc_freq = pit_hpet_ptimer_calibrate_cpu();
+		tsc_freq = native_calibrate_cpu_late();
 
 	return tsc_freq;
 }
@@ -1497,7 +1497,7 @@ static bool __init determine_cpu_tsc_frequencies(bool early,
 		else
 			tsc_khz = native_calibrate_tsc();
 	} else {
-		cpu_khz = pit_hpet_ptimer_calibrate_cpu();
+		cpu_khz = native_calibrate_cpu_late();
 	}
 
 	/*

---

## [14] Sean Christopherson — 2026-05-29
*Subject: [PATCH v4 13/47] x86/tsc: Fold native_calibrate_cpu() into recalibrate_cpu_khz()*

Fold the guts of native_calibrate_cpu() into its sole remaining caller,
recalibrate_cpu_khz() to eliminate the extra SMP=n #ifdef, and so that it's
more obvious that directly invoking the early vs. late calibration routines
in determine_cpu_tsc_frequencies() is intentional.

No functional change intended.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kernel/tsc.c | 20 ++++----------------
 1 file changed, 4 insertions(+), 16 deletions(-)

diff --git a/arch/x86/kernel/tsc.c b/arch/x86/kernel/tsc.c
index 534462c81c78..3e911f0f7364 100644
--- a/arch/x86/kernel/tsc.c
+++ b/arch/x86/kernel/tsc.c
@@ -945,21 +945,6 @@ static unsigned long native_calibrate_cpu_early(void)
 	return fast_calibrate;
 }
 
-#ifndef CONFIG_SMP
-/**
- * native_calibrate_cpu - calibrate the cpu
- */
-static unsigned long native_calibrate_cpu(void)
-{
-	unsigned long tsc_freq = native_calibrate_cpu_early();
-
-	if (!tsc_freq)
-		tsc_freq = native_calibrate_cpu_late();
-
-	return tsc_freq;
-}
-#endif
-
 void recalibrate_cpu_khz(void)
 {
 #ifndef CONFIG_SMP
@@ -968,7 +953,10 @@ void recalibrate_cpu_khz(void)
 	if (!boot_cpu_has(X86_FEATURE_TSC))
 		return;
 
-	cpu_khz = native_calibrate_cpu();
+	cpu_khz = native_calibrate_cpu_early();
+	if (!cpu_khz)
+		cpu_khz = native_calibrate_cpu_late();
+
 	if (!boot_cpu_has(X86_FEATURE_TSC_KNOWN_FREQ))
 		tsc_khz = native_calibrate_tsc();
 	if (tsc_khz == 0)

---

## [15] Sean Christopherson — 2026-05-29
*Subject: [PATCH v4 14/47] x86/kvmclock: Rename kvm_get_tsc_khz() to kvmclock_get_tsc_khz()*

Rename kvm_get_tsc_khz() to kvmclock_get_tsc_khz() in anticipation of
adding support for getting TSC info from PV CPUID, i.e. in a KVM specific
way, but without non-kvmclock.

No functional change intended.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kernel/kvmclock.c | 8 ++++----
 1 file changed, 4 insertions(+), 4 deletions(-)

diff --git a/arch/x86/kernel/kvmclock.c b/arch/x86/kernel/kvmclock.c
index 69752b170e0a..c4a782a0c903 100644
--- a/arch/x86/kernel/kvmclock.c
+++ b/arch/x86/kernel/kvmclock.c
@@ -115,7 +115,7 @@ static inline void kvm_sched_clock_init(bool stable)
  * poll of guests can be running and trouble each other. So we preset
  * lpj here
  */
-static unsigned int __init kvm_get_tsc_khz(void)
+static unsigned int __init kvmclock_get_tsc_khz(void)
 {
 	return pvclock_tsc_khz(this_cpu_pvti());
 }
@@ -125,7 +125,7 @@ static void __init kvm_get_preset_lpj(void)
 	unsigned long khz;
 	u64 lpj;
 
-	khz = kvm_get_tsc_khz();
+	khz = kvmclock_get_tsc_khz();
 
 	lpj = ((u64)khz * 1000);
 	do_div(lpj, HZ);
@@ -320,8 +320,8 @@ void __init kvmclock_init(void)
 	flags = pvclock_read_flags(&hv_clock_boot[0].pvti);
 	kvm_sched_clock_init(flags & PVCLOCK_TSC_STABLE_BIT);
 
-	x86_init.hyper.get_tsc_khz = kvm_get_tsc_khz;
-	x86_init.hyper.get_cpu_khz = kvm_get_tsc_khz;
+	x86_init.hyper.get_tsc_khz = kvmclock_get_tsc_khz;
+	x86_init.hyper.get_cpu_khz = kvmclock_get_tsc_khz;
 	x86_platform.get_wallclock = kvm_get_wallclock;
 	x86_platform.set_wallclock = kvm_set_wallclock;
 #ifdef CONFIG_X86_LOCAL_APIC

---

## [16] Sean Christopherson — 2026-05-29
*Subject: [PATCH v4 15/47] KVM: x86: Officially define CPUID 0x40000010 as PV
 Timing Info (TSC and Bus)*

From: David Woodhouse <dwmw@amazon.co.uk>

Formally define and document CPUID 0x40000010 as providing TSC and local
APIC bus frequency information for KVM's PV CPUID range.  Way back in
2008, VMware proposed (https://lkml.org/lkml/2008/10/1/246) carving out a
range of CPUID leaves for use by hypervisors.  While the broader proposal
from VMware was mostly shot down in flames, use of CPUID 0x40000010 to
provide TSC and local APIC bus frequency information survived and made it's
way into multiple guest operating systems.

XNU unconditionally assumes CPUID 0x40000010 contains the frequency
information, if it's present on any hypervisor:

  https://github.com/apple/darwin-xnu/blob/main/osfmk/i386/cpuid.c

As does FreeBSD:

  https://github.com/freebsd/freebsd-src/commit/4a432614f68

More importantly, QEMU (the de facto "reference" VMM for KVM) has
conditionally provided timing information in CPUID 0x40000010 for almost
9 years, since commit 9954a1582e ("x86-KVM: Supply TSC and APIC clock
rates to guest like VMWare").

So at this point it would be daft for KVM (or any hypervisor) to expose
0x40000010 for any *other* content.  Officially carve out and define the
CPUID leaf so that Linux-as-a-guest can follow suit and pull TSC and Local
APIC Bus frequency information from CPUID.

Defer providing userspace with the necessary information needed to
precisely and accurately enumerate the _actual_ configured TSC frequency
to the guest (that exact information, along with the scaled ratio, isn't
exposed to userspace).  As evidenced by QEMU, providing CPUID 0x40000010
without help from KVM is entirely possible, just not ideal.

Link: https://lore.kernel.org/all/ea0d7f43d910cee9600b254e303f468722fa355b.camel@infradead.org
Signed-off-by: David Woodhouse <dwmw@amazon.co.uk>
[sean: drop KVM filling of CPUID, add documentation, massage changelog]
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 Documentation/virt/kvm/x86/cpuid.rst | 12 ++++++++++++
 arch/x86/include/uapi/asm/kvm_para.h | 11 +++++++++++
 2 files changed, 23 insertions(+)

diff --git a/Documentation/virt/kvm/x86/cpuid.rst b/Documentation/virt/kvm/x86/cpuid.rst
index bda3e3e737d7..f02e395cfa9b 100644
--- a/Documentation/virt/kvm/x86/cpuid.rst
+++ b/Documentation/virt/kvm/x86/cpuid.rst
@@ -122,3 +122,15 @@ KVM_HINTS_REALTIME 0            guest checks this feature bit to
                                 preempted for an unlimited time
                                 allowing optimizations
 ================== ============ =================================
+
+function: KVM_CPUID_TIMING_INFO (0x40000010)
+
+returns::
+
+   eax = (Virtual) TSC frequency in kHz
+   ebx = (Virtual) Bus (local APIC timer) frequency in kHz
+   ecx = 0 (Reserved)
+   edx = 0 (Reserved)
+
+Note, KVM only defines the semantics of KVM_CPUID_TIMING_INFO; KVM does NOT
+advertise support via KVM_GET_SUPPORTED_CPUID.
\ No newline at end of file
diff --git a/arch/x86/include/uapi/asm/kvm_para.h b/arch/x86/include/uapi/asm/kvm_para.h
index a1efa7907a0b..c3a384711f3a 100644
--- a/arch/x86/include/uapi/asm/kvm_para.h
+++ b/arch/x86/include/uapi/asm/kvm_para.h
@@ -44,6 +44,17 @@
  */
 #define KVM_FEATURE_CLOCKSOURCE_STABLE_BIT	24
 
+/*
+ * The timing information leaf provides TSC and local APIC timer frequency
+ * information to the guest.  Note, userspace is responsible for filling the
+ * leaf with the correct information.
+ *
+ *  # EAX: (Virtual) TSC frequency in kHz.
+ *  # EBX: (Virtual) Bus (local APIC timer) frequency in kHz.
+ *  # ECX, EDX: Reserved (must be zero).
+ */
+#define KVM_CPUID_TIMING_INFO	0x40000010
+
 #define MSR_KVM_WALL_CLOCK  0x11
 #define MSR_KVM_SYSTEM_TIME 0x12

---

## [17] Sean Christopherson — 2026-05-29
*Subject: [PATCH v4 16/47] x86/kvm: Obtain TSC frequency from PV CPUID if present*

From: David Woodhouse <dwmw@amazon.co.uk>

In https://lkml.org/lkml/2008/10/1/246 a proposal was made for generic
CPUID conventions across hypervisors. It was mostly shot down in flames,
but the leaf at 0x40000010 containing timing information didn't die.

It's used by XNU and FreeBSD guests under all hypervisors¹² to determine
the TSC frequency, and also exposed by the EC2 Nitro hypervisor (as
well as, presumably, VMware). FreeBSD's Bhyve is probably just about
to start exposing it too.

Use it under KVM to obtain the TSC frequency more accurately, instead of
reverse-calculating the frequency from the mul/shift values in the KVM
clock.  Use the information to get the CPU frequency as well (kvmclock
feeds in kvm_get_tsc_khz() for both TSC and CPU calibration), as the info
from CPUID is superior in every way; whether or not kvmclock should be
overriding CPU calibration in the first place is an entirely different
question.

Use the info from CPUID even if the user explicitly disables kvmclock, or
if it's unsupported.  The PV CPUID leaf has no dependency on kvmclock, and
is in fact more useful if kvmclock is disabled since the kernel won't be
able to use kvmclock to derive a derive the TSC frequency.

Before:
[    0.000020] tsc: Detected 2900.014 MHz processor

After:
[    0.000020] tsc: Detected 2900.015 MHz processor

$ cpuid -1 -l 0x40000010
CPU:
   hypervisor generic timing information (0x40000010):
      TSC frequency (Hz) = 2900015
      bus frequency (Hz) = 1000000

Note!  *Independently* query for non-null get_{cpu,tsc}_khz() overrides so
that kvmclock doesn't clobber x86_init.hyper.get_cpu_khz() if/when KVM adds
support for getting the CPU frequency separately from the TSC frequency.

¹ https://github.com/apple/darwin-xnu/blob/main/osfmk/i386/cpuid.c
² https://github.com/freebsd/freebsd-src/commit/4a432614f68

Signed-off-by: David Woodhouse <dwmw@amazon.co.uk>
Co-developed-by: Sean Christopherson <seanjc@google.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kernel/kvm.c      | 33 +++++++++++++++++++++++++++++++++
 arch/x86/kernel/kvmclock.c |  6 ++++--
 2 files changed, 37 insertions(+), 2 deletions(-)

diff --git a/arch/x86/kernel/kvm.c b/arch/x86/kernel/kvm.c
index dcef84da304b..909d3e5e5bcd 100644
--- a/arch/x86/kernel/kvm.c
+++ b/arch/x86/kernel/kvm.c
@@ -49,6 +49,8 @@
 #include <asm/svm.h>
 #include <asm/e820/api.h>
 
+static unsigned int kvm_tsc_khz_cpuid __initdata;
+
 DEFINE_STATIC_KEY_FALSE_RO(kvm_async_pf_enabled);
 
 static int kvmapf = 1;
@@ -911,6 +913,21 @@ bool kvm_para_available(void)
 }
 EXPORT_SYMBOL_GPL(kvm_para_available);
 
+static u32 __init kvm_cpuid_timing_info_leaf(void)
+{
+	u32 base = kvm_cpuid_base();
+
+	if (!base || cpuid_eax(base) < (base | KVM_CPUID_TIMING_INFO))
+		return 0;
+
+	return base | KVM_CPUID_TIMING_INFO;
+}
+
+static unsigned int __init kvm_get_tsc_khz(void)
+{
+	return kvm_tsc_khz_cpuid;
+}
+
 unsigned int kvm_arch_para_features(void)
 {
 	return cpuid_eax(kvm_cpuid_base() | KVM_CPUID_FEATURES);
@@ -960,6 +977,7 @@ static void __init kvm_init_platform(void)
 		.mask_lo = (u32)(~(SZ_4G - tolud - 1)) | MTRR_PHYSMASK_V,
 		.mask_hi = (BIT_ULL(boot_cpu_data.x86_phys_bits) - 1) >> 32,
 	};
+	u32 timing_info_leaf;
 
 	if (cc_platform_has(CC_ATTR_GUEST_MEM_ENCRYPT) &&
 	    kvm_para_has_feature(KVM_FEATURE_MIGRATION_CONTROL)) {
@@ -1007,6 +1025,21 @@ static void __init kvm_init_platform(void)
 			wrmsrq(MSR_KVM_MIGRATION_CONTROL,
 			       KVM_MIGRATION_READY);
 	}
+
+	/*
+	 * If KVM advertises the frequency directly in CPUID, use that instead
+	 * of reverse-calculating it from the KVM clock data, or worse, trying
+	 * to calibratate the TSC using an emulated device.
+	 */
+	timing_info_leaf = kvm_cpuid_timing_info_leaf();
+	if (timing_info_leaf) {
+		kvm_tsc_khz_cpuid = cpuid_eax(timing_info_leaf);
+		if (kvm_tsc_khz_cpuid) {
+			x86_init.hyper.get_tsc_khz = kvm_get_tsc_khz;
+			x86_init.hyper.get_cpu_khz = kvm_get_tsc_khz;
+		}
+	}
+
 	kvmclock_init();
 	x86_platform.apic_post_init = kvm_apic_init;
 
diff --git a/arch/x86/kernel/kvmclock.c b/arch/x86/kernel/kvmclock.c
index c4a782a0c903..404f60741aa8 100644
--- a/arch/x86/kernel/kvmclock.c
+++ b/arch/x86/kernel/kvmclock.c
@@ -320,8 +320,10 @@ void __init kvmclock_init(void)
 	flags = pvclock_read_flags(&hv_clock_boot[0].pvti);
 	kvm_sched_clock_init(flags & PVCLOCK_TSC_STABLE_BIT);
 
-	x86_init.hyper.get_tsc_khz = kvmclock_get_tsc_khz;
-	x86_init.hyper.get_cpu_khz = kvmclock_get_tsc_khz;
+	if (!x86_init.hyper.get_tsc_khz)
+		x86_init.hyper.get_tsc_khz = kvmclock_get_tsc_khz;
+	if (!x86_init.hyper.get_cpu_khz)
+		x86_init.hyper.get_cpu_khz = kvmclock_get_tsc_khz;
 	x86_platform.get_wallclock = kvm_get_wallclock;
 	x86_platform.set_wallclock = kvm_set_wallclock;
 #ifdef CONFIG_X86_LOCAL_APIC

---

## [18] Sean Christopherson — 2026-05-29
*Subject: [PATCH v4 17/47] x86/kvm: Mark TSC as reliable when it's constant and nonstop*

Mark the TSC as reliable if the hypervisor (KVM) has enumerated the TSC
as constant and nonstop, and the admin hasn't explicitly marked the TSC
as unstable.  Like most (all?) virtualization setups, any secondary
clocksource that's used as a watchdog is guaranteed to be less reliable
than a constant, nonstop TSC, as all clocksources the kernel uses as a
watchdog are all but guaranteed to be emulated when running as a KVM
guest.  I.e. any observed discrepancies between the TSC and watchdog will
be due to jitter in the watchdog.

This is especially true for KVM, as the watchdog clocksource is usually
emulated in host userspace, i.e. reading the clock incurs a roundtrip
cost of thousands of cycles.

Marking the TSC reliable addresses a flaw where the TSC will occasionally
be marked unstable if the host is under moderate/heavy load.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/kvm_para.h |  2 +-
 arch/x86/kernel/kvm.c           | 16 +++++++++++++++-
 arch/x86/kernel/kvmclock.c      | 15 +++++----------
 3 files changed, 21 insertions(+), 12 deletions(-)

diff --git a/arch/x86/include/asm/kvm_para.h b/arch/x86/include/asm/kvm_para.h
index 4a47c16e2df8..4a49fc286b4c 100644
--- a/arch/x86/include/asm/kvm_para.h
+++ b/arch/x86/include/asm/kvm_para.h
@@ -118,7 +118,7 @@ static inline long kvm_sev_hypercall3(unsigned int nr, unsigned long p1,
 }
 
 #ifdef CONFIG_KVM_GUEST
-void kvmclock_init(void);
+void kvmclock_init(bool prefer_tsc);
 void kvmclock_disable(void);
 bool kvm_para_available(void);
 unsigned int kvm_arch_para_features(void);
diff --git a/arch/x86/kernel/kvm.c b/arch/x86/kernel/kvm.c
index 909d3e5e5bcd..4fe9c69bf40b 100644
--- a/arch/x86/kernel/kvm.c
+++ b/arch/x86/kernel/kvm.c
@@ -978,6 +978,7 @@ static void __init kvm_init_platform(void)
 		.mask_hi = (BIT_ULL(boot_cpu_data.x86_phys_bits) - 1) >> 32,
 	};
 	u32 timing_info_leaf;
+	bool tsc_is_reliable;
 
 	if (cc_platform_has(CC_ATTR_GUEST_MEM_ENCRYPT) &&
 	    kvm_para_has_feature(KVM_FEATURE_MIGRATION_CONTROL)) {
@@ -1040,7 +1041,20 @@ static void __init kvm_init_platform(void)
 		}
 	}
 
-	kvmclock_init();
+        /*
+         * If the TSC counts at a constant frequency across P/T states, counts
+         * in deep C-states, and the TSC hasn't been marked unstable, treat the
+         * TSC reliable, as guaranteed by KVM.  Note, the TSC unstable check
+         * exists purely to honor the TSC being marked unstable via command
+         * line, any runtime detection of an unstable will happen after this.
+         */
+	tsc_is_reliable = boot_cpu_has(X86_FEATURE_CONSTANT_TSC) &&
+			  boot_cpu_has(X86_FEATURE_NONSTOP_TSC) &&
+			  !check_tsc_unstable();
+	if (tsc_is_reliable)
+		setup_force_cpu_cap(X86_FEATURE_TSC_RELIABLE);
+
+	kvmclock_init(tsc_is_reliable);
 	x86_platform.apic_post_init = kvm_apic_init;
 
 	/*
diff --git a/arch/x86/kernel/kvmclock.c b/arch/x86/kernel/kvmclock.c
index 404f60741aa8..69a15fbfb779 100644
--- a/arch/x86/kernel/kvmclock.c
+++ b/arch/x86/kernel/kvmclock.c
@@ -285,7 +285,7 @@ static int kvmclock_setup_percpu(unsigned int cpu)
 	return p ? 0 : -ENOMEM;
 }
 
-void __init kvmclock_init(void)
+void __init kvmclock_init(bool prefer_tsc)
 {
 	u8 flags;
 
@@ -334,16 +334,11 @@ void __init kvmclock_init(void)
 	kvm_get_preset_lpj();
 
 	/*
-	 * X86_FEATURE_NONSTOP_TSC is TSC runs at constant rate
-	 * with P/T states and does not stop in deep C-states.
-	 *
-	 * Invariant TSC exposed by host means kvmclock is not necessary:
-	 * can use TSC as clocksource.
-	 *
+	 * If TSC is preferred over kvmlock, drop kvmclock's rating so that TSC
+	 * is chosen as the clocksource (but still register kvmclock in case
+	 * the kernel doesn't want to use TSC for whatever reason).
 	 */
-	if (boot_cpu_has(X86_FEATURE_CONSTANT_TSC) &&
-	    boot_cpu_has(X86_FEATURE_NONSTOP_TSC) &&
-	    !check_tsc_unstable())
+	if (prefer_tsc)
 		kvm_clock.rating = 299;
 
 	clocksource_register_hz(&kvm_clock, NSEC_PER_SEC);

---

## [19] Sean Christopherson — 2026-05-29
*Subject: [PATCH v4 18/47] x86/kvm: Get local APIC bus frequency from PV CPUID
 Timing Info*

When running as a KVM guest with PV timing info provided by the host,
stuff the APIC timer period/frequency with the local APIC bus frequency
reported in CPUID.0x40000010.EBX instead of trying to calibrate/guess the
frequency.

Note, the unit of measurement for lapic_timer_period is "ticks per HZ", not
Khz.

See Documentation/virt/kvm/x86/cpuid.rst for details.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kernel/kvm.c | 8 ++++++++
 1 file changed, 8 insertions(+)

diff --git a/arch/x86/kernel/kvm.c b/arch/x86/kernel/kvm.c
index 4fe9c69bf40b..c1139182121d 100644
--- a/arch/x86/kernel/kvm.c
+++ b/arch/x86/kernel/kvm.c
@@ -977,6 +977,7 @@ static void __init kvm_init_platform(void)
 		.mask_lo = (u32)(~(SZ_4G - tolud - 1)) | MTRR_PHYSMASK_V,
 		.mask_hi = (BIT_ULL(boot_cpu_data.x86_phys_bits) - 1) >> 32,
 	};
+	u32 apic_khz __maybe_unused;
 	u32 timing_info_leaf;
 	bool tsc_is_reliable;
 
@@ -1039,6 +1040,13 @@ static void __init kvm_init_platform(void)
 			x86_init.hyper.get_tsc_khz = kvm_get_tsc_khz;
 			x86_init.hyper.get_cpu_khz = kvm_get_tsc_khz;
 		}
+
+#ifdef CONFIG_X86_LOCAL_APIC
+		/* The leaf also includes the local APIC bus/timer frequency.*/
+		apic_khz = cpuid_ebx(timing_info_leaf);
+		if (apic_khz)
+	               lapic_timer_period = apic_khz * 1000 / HZ;
+#endif
 	}
 
         /*

---

## [20] Sean Christopherson — 2026-05-29
*Subject: [PATCH v4 19/47] x86/tsc: Add standalone helper for getting CPU
 frequency from CPUID*

Extract the guts of cpu_khz_from_cpuid() to a standalone helper that
doesn't restrict the usage to Intel CPUs.  This will allow sharing the
core logic with KVM-as-a-guest, as KVM generally doesn't restrict CPUID
based on vendor.

No functional change intended.

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/tsc.h |  1 +
 arch/x86/kernel/tsc.c      | 32 +++++++++++++++-----------------
 2 files changed, 16 insertions(+), 17 deletions(-)

diff --git a/arch/x86/include/asm/tsc.h b/arch/x86/include/asm/tsc.h
index 4a224f99c3b9..7ff2bfdcdf38 100644
--- a/arch/x86/include/asm/tsc.h
+++ b/arch/x86/include/asm/tsc.h
@@ -90,6 +90,7 @@ struct cpuid_tsc_info {
 	unsigned int tsc_khz;
 };
 extern int __init cpuid_get_tsc_freq(struct cpuid_tsc_info *info);
+extern unsigned int __cpu_khz_from_cpuid(void);
 
 extern void tsc_early_init(void);
 extern void tsc_init(void);
diff --git a/arch/x86/kernel/tsc.c b/arch/x86/kernel/tsc.c
index 3e911f0f7364..bdff8c988866 100644
--- a/arch/x86/kernel/tsc.c
+++ b/arch/x86/kernel/tsc.c
@@ -692,6 +692,18 @@ int __init cpuid_get_tsc_freq(struct cpuid_tsc_info *info)
 	return 0;
 }
 
+unsigned int __cpu_khz_from_cpuid(void)
+{
+	unsigned int eax_base_mhz, ebx, ecx, edx;
+
+	if (boot_cpu_data.cpuid_level < CPUID_LEAF_FREQ)
+		return 0;
+
+	cpuid(CPUID_LEAF_FREQ, &eax_base_mhz, &ebx, &ecx, &edx);
+
+	return eax_base_mhz * 1000;
+}
+
 /**
  * native_calibrate_tsc - determine TSC frequency
  * Determine TSC frequency via CPUID, else return 0.
@@ -727,13 +739,8 @@ static unsigned long native_calibrate_tsc(void)
 	 * clock, but we can easily calculate it to a high degree of accuracy
 	 * by considering the crystal ratio and the CPU speed.
 	 */
-	if (!info.crystal_khz && boot_cpu_data.cpuid_level >= CPUID_LEAF_FREQ) {
-		unsigned int eax_base_mhz, ebx, ecx, edx;
-
-		cpuid(CPUID_LEAF_FREQ, &eax_base_mhz, &ebx, &ecx, &edx);
-		info.crystal_khz = eax_base_mhz * 1000 *
-			info.denominator / info.numerator;
-	}
+	if (!info.crystal_khz)
+		info.crystal_khz = __cpu_khz_from_cpuid() * info.denominator / info.numerator;
 
 	if (!info.crystal_khz)
 		return 0;
@@ -760,19 +767,10 @@ static unsigned long native_calibrate_tsc(void)
 
 static unsigned long cpu_khz_from_cpuid(void)
 {
-	unsigned int eax_base_mhz, ebx_max_mhz, ecx_bus_mhz, edx;
-
 	if (boot_cpu_data.x86_vendor != X86_VENDOR_INTEL)
 		return 0;
 
-	if (boot_cpu_data.cpuid_level < CPUID_LEAF_FREQ)
-		return 0;
-
-	eax_base_mhz = ebx_max_mhz = ecx_bus_mhz = edx = 0;
-
-	cpuid(CPUID_LEAF_FREQ, &eax_base_mhz, &ebx_max_mhz, &ecx_bus_mhz, &edx);
-
-	return eax_base_mhz * 1000;
+	return __cpu_khz_from_cpuid();
 }
 
 /*

---

## [21] Sean Christopherson — 2026-05-29
*Subject: [PATCH v4 20/47] x86/kvm: Get CPU base frequency from CPUID when it's available*

If CPUID.0x16 is present and valid, use the CPU frequency provided by
CPUID instead of assuming that the virtual CPU runs at the same
frequency as TSC and/or kvmclock.  Back before constant TSCs were a
thing, treating the TSC and CPU frequencies as one and the same was
somewhat reasonable, but now it's nonsensical, especially if the
hypervisor explicitly enumerates the CPU frequency.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kernel/kvm.c | 14 ++++++++++++++
 1 file changed, 14 insertions(+)

diff --git a/arch/x86/kernel/kvm.c b/arch/x86/kernel/kvm.c
index c1139182121d..c81a24d0efdf 100644
--- a/arch/x86/kernel/kvm.c
+++ b/arch/x86/kernel/kvm.c
@@ -50,6 +50,7 @@
 #include <asm/e820/api.h>
 
 static unsigned int kvm_tsc_khz_cpuid __initdata;
+static unsigned int kvm_cpu_khz_cpuid __initdata;
 
 DEFINE_STATIC_KEY_FALSE_RO(kvm_async_pf_enabled);
 
@@ -928,6 +929,11 @@ static unsigned int __init kvm_get_tsc_khz(void)
 	return kvm_tsc_khz_cpuid;
 }
 
+static unsigned int __init kvm_get_cpu_khz(void)
+{
+	return kvm_cpu_khz_cpuid;
+}
+
 unsigned int kvm_arch_para_features(void)
 {
 	return cpuid_eax(kvm_cpuid_base() | KVM_CPUID_FEATURES);
@@ -1049,6 +1055,14 @@ static void __init kvm_init_platform(void)
 #endif
 	}
 
+	/*
+	 * Prefer CPUID.0x16 over KVM's PV CPUID when possible, as the base CPU
+	 * frequency isn't necessarily the same as the TSC frequency.
+	 */
+	kvm_cpu_khz_cpuid = __cpu_khz_from_cpuid();
+	if (kvm_cpu_khz_cpuid)
+		x86_init.hyper.get_cpu_khz = kvm_get_cpu_khz;
+
         /*
          * If the TSC counts at a constant frequency across P/T states, counts
          * in deep C-states, and the TSC hasn't been marked unstable, treat the

---

## [22] Sean Christopherson — 2026-05-29
*Subject: [PATCH v4 21/47] x86/xen: Obtain TSC frequency from CPUID if present*

From: David Woodhouse <dwmw@amazon.co.uk>

The Xen CPUID leaf 3, sub-leaf 0, ECX provides the guest TSC frequency
in kHz directly. Use it when available instead of reverse-calculating
the frequency from the pvclock tsc_to_system_mul and tsc_shift values,
which loses precision.

This mirrors the equivalent change for KVM guests using the generic
0x40000010 timing leaf.

Signed-off-by: David Woodhouse <dwmw@amazon.co.uk>
[sean: drop non-Xen changes]
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/xen/time.c | 11 +++++++++++
 1 file changed, 11 insertions(+)

diff --git a/arch/x86/xen/time.c b/arch/x86/xen/time.c
index 487ad838c441..36d66abf5379 100644
--- a/arch/x86/xen/time.c
+++ b/arch/x86/xen/time.c
@@ -42,6 +42,17 @@ static unsigned int __init xen_tsc_khz(void)
 {
 	struct pvclock_vcpu_time_info *info =
 		&HYPERVISOR_shared_info->vcpu_info[0].time;
+	u32 base = xen_cpuid_base();
+	u32 eax, ebx, ecx, edx;
+
+	/*
+	 * If Xen provides the guest TSC frequency directly in CPUID
+	 * (leaf 3, sub-leaf 0, ECX), use that instead of reverse-
+	 * calculating from the pvclock mul/shift.
+	 */
+	cpuid_count(base + 3, 0, &eax, &ebx, &ecx, &edx);
+	if (ecx)
+		return ecx;
 
 	return pvclock_tsc_khz(info);
 }

---

## [23] Sean Christopherson — 2026-05-29
*Subject: [PATCH v4 22/47] clocksource: hyper-v: Register sched_clock
 save/restore iff it's necessary*

Register the Hyper-V reference counter (refcounter) callbacks for saving
and restoring its PV sched_clock, if and only if the refcounter is
actually being used for sched_clock.  Currently, Hyper-V overrides the
save/restore hooks if the reference TSC available, whereas the Hyper-V
refcounter code only overrides sched_clock if the reference TSC is
available *and* it's not invariant.  The flaw is effectively papered over
by invoking the "old" save/restore callbacks as part of save/restore, but
that's unnecessary and fragile.

To avoid introducing more complexity, and to allow for additional cleanups
of the PV sched_clock code, move the save/restore hooks and logic into
hyperv_timer.c and simply wire up the hooks when overriding sched_clock
itself.

Note, while the Hyper-V refcounter code is intended to be architecture
neutral, CONFIG_PARAVIRT is firmly x86-only, i.e. adding a small amount of
x86 specific code (which will be reduced in future cleanups) doesn't
meaningfully pollute generic code.

Reviewed-by: Michael Kelley <mhklinux@outlook.com>
Tested-by: Michael Kelley <mhklinux@outlook.com>
Acked-by: Wei Liu <wei.liu@kernel.org>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kernel/cpu/mshyperv.c     | 58 ------------------------------
 drivers/clocksource/hyperv_timer.c | 50 ++++++++++++++++++++++++++
 2 files changed, 50 insertions(+), 58 deletions(-)

diff --git a/arch/x86/kernel/cpu/mshyperv.c b/arch/x86/kernel/cpu/mshyperv.c
index f8653fc05a40..2403231fd4b0 100644
--- a/arch/x86/kernel/cpu/mshyperv.c
+++ b/arch/x86/kernel/cpu/mshyperv.c
@@ -275,63 +275,6 @@ static void hv_guest_crash_shutdown(struct pt_regs *regs)
 }
 #endif /* CONFIG_CRASH_DUMP */
 
-static u64 hv_ref_counter_at_suspend;
-static void (*old_save_sched_clock_state)(void);
-static void (*old_restore_sched_clock_state)(void);
-
-/*
- * Hyper-V clock counter resets during hibernation. Save and restore clock
- * offset during suspend/resume, while also considering the time passed
- * before suspend. This is to make sure that sched_clock using hv tsc page
- * based clocksource, proceeds from where it left off during suspend and
- * it shows correct time for the timestamps of kernel messages after resume.
- */
-static void save_hv_clock_tsc_state(void)
-{
-	hv_ref_counter_at_suspend = hv_read_reference_counter();
-}
-
-static void restore_hv_clock_tsc_state(void)
-{
-	/*
-	 * Adjust the offsets used by hv tsc clocksource to
-	 * account for the time spent before hibernation.
-	 * adjusted value = reference counter (time) at suspend
-	 *                - reference counter (time) now.
-	 */
-	hv_adj_sched_clock_offset(hv_ref_counter_at_suspend - hv_read_reference_counter());
-}
-
-/*
- * Functions to override save_sched_clock_state and restore_sched_clock_state
- * functions of x86_platform. The Hyper-V clock counter is reset during
- * suspend-resume and the offset used to measure time needs to be
- * corrected, post resume.
- */
-static void hv_save_sched_clock_state(void)
-{
-	old_save_sched_clock_state();
-	save_hv_clock_tsc_state();
-}
-
-static void hv_restore_sched_clock_state(void)
-{
-	restore_hv_clock_tsc_state();
-	old_restore_sched_clock_state();
-}
-
-static void __init x86_setup_ops_for_tsc_pg_clock(void)
-{
-	if (!(ms_hyperv.features & HV_MSR_REFERENCE_TSC_AVAILABLE))
-		return;
-
-	old_save_sched_clock_state = x86_platform.save_sched_clock_state;
-	x86_platform.save_sched_clock_state = hv_save_sched_clock_state;
-
-	old_restore_sched_clock_state = x86_platform.restore_sched_clock_state;
-	x86_platform.restore_sched_clock_state = hv_restore_sched_clock_state;
-}
-
 #ifdef CONFIG_X86_64
 DEFINE_STATIC_CALL(hv_hypercall, hv_std_hypercall);
 EXPORT_STATIC_CALL_TRAMP_GPL(hv_hypercall);
@@ -739,7 +682,6 @@ static void __init ms_hyperv_init_platform(void)
 
 	/* Register Hyper-V specific clocksource */
 	hv_init_clocksource();
-	x86_setup_ops_for_tsc_pg_clock();
 	hv_vtl_init_platform();
 #endif
 	/*
diff --git a/drivers/clocksource/hyperv_timer.c b/drivers/clocksource/hyperv_timer.c
index e9f5034a1bc8..72b966340a46 100644
--- a/drivers/clocksource/hyperv_timer.c
+++ b/drivers/clocksource/hyperv_timer.c
@@ -537,10 +537,60 @@ static __always_inline void hv_setup_sched_clock(void *sched_clock)
 #elif defined CONFIG_PARAVIRT
 #include <asm/timer.h>
 
+static u64 hv_ref_counter_at_suspend;
+static void (*old_save_sched_clock_state)(void);
+static void (*old_restore_sched_clock_state)(void);
+
+/*
+ * Hyper-V clock counter resets during hibernation. Save and restore clock
+ * offset during suspend/resume, while also considering the time passed
+ * before suspend. This is to make sure that sched_clock using hv tsc page
+ * based clocksource, proceeds from where it left off during suspend and
+ * it shows correct time for the timestamps of kernel messages after resume.
+ */
+static void save_hv_clock_tsc_state(void)
+{
+	hv_ref_counter_at_suspend = hv_read_reference_counter();
+}
+
+static void restore_hv_clock_tsc_state(void)
+{
+	/*
+	 * Adjust the offsets used by hv tsc clocksource to
+	 * account for the time spent before hibernation.
+	 * adjusted value = reference counter (time) at suspend
+	 *                - reference counter (time) now.
+	 */
+	hv_adj_sched_clock_offset(hv_ref_counter_at_suspend - hv_read_reference_counter());
+}
+/*
+ * Functions to override save_sched_clock_state and restore_sched_clock_state
+ * functions of x86_platform. The Hyper-V clock counter is reset during
+ * suspend-resume and the offset used to measure time needs to be
+ * corrected, post resume.
+ */
+static void hv_save_sched_clock_state(void)
+{
+	old_save_sched_clock_state();
+	save_hv_clock_tsc_state();
+}
+
+static void hv_restore_sched_clock_state(void)
+{
+	restore_hv_clock_tsc_state();
+	old_restore_sched_clock_state();
+}
+
 static __always_inline void hv_setup_sched_clock(void *sched_clock)
 {
 	/* We're on x86/x64 *and* using PV ops */
 	paravirt_set_sched_clock(sched_clock);
+
+	old_save_sched_clock_state = x86_platform.save_sched_clock_state;
+	x86_platform.save_sched_clock_state = hv_save_sched_clock_state;
+
+	old_restore_sched_clock_state = x86_platform.restore_sched_clock_state;
+	x86_platform.restore_sched_clock_state = hv_restore_sched_clock_state;
 }
 #else /* !CONFIG_GENERIC_SCHED_CLOCK && !CONFIG_PARAVIRT */
 static __always_inline void hv_setup_sched_clock(void *sched_clock) {}

---

## [24] Sean Christopherson — 2026-05-29
*Subject: [PATCH v4 23/47] clocksource: hyper-v: Drop wrappers to sched_clock
 save/restore helpers*

Now that all of the Hyper-V reference counter sched_clock code is located
in a single file, drop the superfluous wrappers for the save/restore flows.

No functional change intended.

Reviewed-by: Michael Kelley <mhklinux@outlook.com>
Tested-by: Michael Kelley <mhklinux@outlook.com>
Acked-by: Wei Liu <wei.liu@kernel.org>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 drivers/clocksource/hyperv_timer.c | 34 +++++-------------------------
 include/clocksource/hyperv_timer.h |  2 --
 2 files changed, 5 insertions(+), 31 deletions(-)

diff --git a/drivers/clocksource/hyperv_timer.c b/drivers/clocksource/hyperv_timer.c
index 72b966340a46..69c1c7264e5d 100644
--- a/drivers/clocksource/hyperv_timer.c
+++ b/drivers/clocksource/hyperv_timer.c
@@ -472,17 +472,6 @@ static void resume_hv_clock_tsc(struct clocksource *arg)
 	hv_set_msr(HV_MSR_REFERENCE_TSC, tsc_msr.as_uint64);
 }
 
-/*
- * Called during resume from hibernation, from overridden
- * x86_platform.restore_sched_clock_state routine. This is to adjust offsets
- * used to calculate time for hv tsc page based sched_clock, to account for
- * time spent before hibernation.
- */
-void hv_adj_sched_clock_offset(u64 offset)
-{
-	hv_sched_clock_offset -= offset;
-}
-
 #ifdef HAVE_VDSO_CLOCKMODE_HVCLOCK
 static int hv_cs_enable(struct clocksource *cs)
 {
@@ -548,12 +537,14 @@ static void (*old_restore_sched_clock_state)(void);
  * based clocksource, proceeds from where it left off during suspend and
  * it shows correct time for the timestamps of kernel messages after resume.
  */
-static void save_hv_clock_tsc_state(void)
+static void hv_save_sched_clock_state(void)
 {
+	old_save_sched_clock_state();
+
 	hv_ref_counter_at_suspend = hv_read_reference_counter();
 }
 
-static void restore_hv_clock_tsc_state(void)
+static void hv_restore_sched_clock_state(void)
 {
 	/*
 	 * Adjust the offsets used by hv tsc clocksource to
@@ -561,23 +552,8 @@ static void restore_hv_clock_tsc_state(void)
 	 * adjusted value = reference counter (time) at suspend
 	 *                - reference counter (time) now.
 	 */
-	hv_adj_sched_clock_offset(hv_ref_counter_at_suspend - hv_read_reference_counter());
-}
-/*
- * Functions to override save_sched_clock_state and restore_sched_clock_state
- * functions of x86_platform. The Hyper-V clock counter is reset during
- * suspend-resume and the offset used to measure time needs to be
- * corrected, post resume.
- */
-static void hv_save_sched_clock_state(void)
-{
-	old_save_sched_clock_state();
-	save_hv_clock_tsc_state();
-}
+	hv_sched_clock_offset -= (hv_ref_counter_at_suspend - hv_read_reference_counter());
 
-static void hv_restore_sched_clock_state(void)
-{
-	restore_hv_clock_tsc_state();
 	old_restore_sched_clock_state();
 }
 
diff --git a/include/clocksource/hyperv_timer.h b/include/clocksource/hyperv_timer.h
index d48dd4176fd3..a4c81a60f53d 100644
--- a/include/clocksource/hyperv_timer.h
+++ b/include/clocksource/hyperv_timer.h
@@ -38,8 +38,6 @@ extern void hv_remap_tsc_clocksource(void);
 extern unsigned long hv_get_tsc_pfn(void);
 extern struct ms_hyperv_tsc_page *hv_get_tsc_page(void);
 
-extern void hv_adj_sched_clock_offset(u64 offset);
-
 static __always_inline bool
 hv_read_tsc_page_tsc(const struct ms_hyperv_tsc_page *tsc_pg,
 		     u64 *cur_tsc, u64 *time)

---

## [25] Sean Christopherson — 2026-05-29
*Subject: [PATCH v4 24/47] clocksource: hyper-v: Don't save/restore TSC offset
 when using HV sched_clock*

Now that Hyper-V overrides the sched_clock save/restore hooks if and only
sched_clock itself is set to the Hyper-V reference counter, drop the
invocation of the "old" save/restore callbacks.  When the registration of
the PV sched_clock was done separately from overriding the save/restore
hooks, it was possible for Hyper-V to clobber the TSC save/restore
callbacks without actually switching to the Hyper-V refcounter.

Enabling a PV sched_clock is a one-way street, i.e. the kernel will never
revert to using TSC for sched_clock, and so there is no need to invoke the
TSC save/restore hooks (and if there was, it belongs in common PV code).

Reviewed-by: Michael Kelley <mhklinux@outlook.com>
Tested-by: Michael Kelley <mhklinux@outlook.com>
Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>
Acked-by: Wei Liu <wei.liu@kernel.org>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 drivers/clocksource/hyperv_timer.c | 10 ----------
 1 file changed, 10 deletions(-)

diff --git a/drivers/clocksource/hyperv_timer.c b/drivers/clocksource/hyperv_timer.c
index 69c1c7264e5d..ac1d9f9c381c 100644
--- a/drivers/clocksource/hyperv_timer.c
+++ b/drivers/clocksource/hyperv_timer.c
@@ -527,9 +527,6 @@ static __always_inline void hv_setup_sched_clock(void *sched_clock)
 #include <asm/timer.h>
 
 static u64 hv_ref_counter_at_suspend;
-static void (*old_save_sched_clock_state)(void);
-static void (*old_restore_sched_clock_state)(void);
-
 /*
  * Hyper-V clock counter resets during hibernation. Save and restore clock
  * offset during suspend/resume, while also considering the time passed
@@ -539,8 +536,6 @@ static void (*old_restore_sched_clock_state)(void);
  */
 static void hv_save_sched_clock_state(void)
 {
-	old_save_sched_clock_state();
-
 	hv_ref_counter_at_suspend = hv_read_reference_counter();
 }
 
@@ -553,8 +548,6 @@ static void hv_restore_sched_clock_state(void)
 	 *                - reference counter (time) now.
 	 */
 	hv_sched_clock_offset -= (hv_ref_counter_at_suspend - hv_read_reference_counter());
-
-	old_restore_sched_clock_state();
 }
 
 static __always_inline void hv_setup_sched_clock(void *sched_clock)
@@ -562,10 +555,7 @@ static __always_inline void hv_setup_sched_clock(void *sched_clock)
 	/* We're on x86/x64 *and* using PV ops */
 	paravirt_set_sched_clock(sched_clock);
 
-	old_save_sched_clock_state = x86_platform.save_sched_clock_state;
 	x86_platform.save_sched_clock_state = hv_save_sched_clock_state;
-
-	old_restore_sched_clock_state = x86_platform.restore_sched_clock_state;
 	x86_platform.restore_sched_clock_state = hv_restore_sched_clock_state;
 }
 #else /* !CONFIG_GENERIC_SCHED_CLOCK && !CONFIG_PARAVIRT */

---

## [26] Sean Christopherson — 2026-05-29
*Subject: [PATCH v4 25/47] x86/kvmclock: Setup kvmclock for secondary CPUs iff CONFIG_SMP=y*

Gate kvmclock's secondary CPU code on CONFIG_SMP, not CONFIG_X86_LOCAL_APIC.
Originally, kvmclock piggybacked PV APIC ops to setup secondary CPUs.
When that wart was fixed by commit df156f90a0f9 ("x86: Introduce
x86_cpuinit.early_percpu_clock_init hook"), the dependency on a local APIC
got carried forward unnecessarily.

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kernel/kvmclock.c | 4 ++--
 1 file changed, 2 insertions(+), 2 deletions(-)

diff --git a/arch/x86/kernel/kvmclock.c b/arch/x86/kernel/kvmclock.c
index 69a15fbfb779..13c728444e12 100644
--- a/arch/x86/kernel/kvmclock.c
+++ b/arch/x86/kernel/kvmclock.c
@@ -186,7 +186,7 @@ static void kvm_restore_sched_clock_state(void)
 	kvm_register_clock("primary cpu clock, resume");
 }
 
-#ifdef CONFIG_X86_LOCAL_APIC
+#ifdef CONFIG_SMP
 static void kvm_setup_secondary_clock(void)
 {
 	kvm_register_clock("secondary cpu clock");
@@ -326,7 +326,7 @@ void __init kvmclock_init(bool prefer_tsc)
 		x86_init.hyper.get_cpu_khz = kvmclock_get_tsc_khz;
 	x86_platform.get_wallclock = kvm_get_wallclock;
 	x86_platform.set_wallclock = kvm_set_wallclock;
-#ifdef CONFIG_X86_LOCAL_APIC
+#ifdef CONFIG_SMP
 	x86_cpuinit.early_percpu_clock_init = kvm_setup_secondary_clock;
 #endif
 	x86_platform.save_sched_clock_state = kvm_save_sched_clock_state;

---

## [27] Sean Christopherson — 2026-05-29
*Subject: [PATCH v4 26/47] x86/kvm: Don't disable kvmclock on BSP in syscore_suspend()*

Don't disable kvmclock on the BSP during syscore_suspend(), as the BSP's
clock is NOT restored during syscore_resume(), but is instead restored
earlier via the sched_clock restore callback.  If suspend is aborted, e.g.
due to a late wakeup, the BSP will run without its clock enabled, which
"works" only because KVM-the-hypervisor is kind enough to not clobber the
shared memory when the clock is disabled.  But over time, the BSP's view
of time will drift from APs.

Plumb in an "action" to KVM-as-a-guest and kvmclock code in preparation
for additional cleanups to kvmclock's suspend/resume logic.

Fixes: c02027b5742b ("x86/kvm: Disable kvmclock on all CPUs on shutdown")
Cc: stable@vger.kernel.org
Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/kvm_para.h |  8 +++++++-
 arch/x86/kernel/kvm.c           | 15 ++++++++-------
 arch/x86/kernel/kvmclock.c      | 31 +++++++++++++++++++++++++------
 3 files changed, 40 insertions(+), 14 deletions(-)

diff --git a/arch/x86/include/asm/kvm_para.h b/arch/x86/include/asm/kvm_para.h
index 4a49fc286b4c..08686ff19caa 100644
--- a/arch/x86/include/asm/kvm_para.h
+++ b/arch/x86/include/asm/kvm_para.h
@@ -118,8 +118,14 @@ static inline long kvm_sev_hypercall3(unsigned int nr, unsigned long p1,
 }
 
 #ifdef CONFIG_KVM_GUEST
+enum kvm_guest_cpu_action {
+	KVM_GUEST_BSP_SUSPEND,
+	KVM_GUEST_AP_OFFLINE,
+	KVM_GUEST_SHUTDOWN,
+};
+
 void kvmclock_init(bool prefer_tsc);
-void kvmclock_disable(void);
+void kvmclock_cpu_action(enum kvm_guest_cpu_action action);
 bool kvm_para_available(void);
 unsigned int kvm_arch_para_features(void);
 unsigned int kvm_arch_para_hints(void);
diff --git a/arch/x86/kernel/kvm.c b/arch/x86/kernel/kvm.c
index c81a24d0efdf..fd1c417b4f9b 100644
--- a/arch/x86/kernel/kvm.c
+++ b/arch/x86/kernel/kvm.c
@@ -460,7 +460,7 @@ static void __init sev_map_percpu_data(void)
 	}
 }
 
-static void kvm_guest_cpu_offline(bool shutdown)
+static void kvm_guest_cpu_offline(enum kvm_guest_cpu_action action)
 {
 	kvm_disable_steal_time();
 	if (kvm_para_has_feature(KVM_FEATURE_PV_EOI))
@@ -468,9 +468,10 @@ static void kvm_guest_cpu_offline(bool shutdown)
 	if (kvm_para_has_feature(KVM_FEATURE_MIGRATION_CONTROL))
 		wrmsrq(MSR_KVM_MIGRATION_CONTROL, 0);
 	kvm_pv_disable_apf();
-	if (!shutdown)
+	if (action != KVM_GUEST_SHUTDOWN)
 		apf_task_wake_all();
-	kvmclock_disable();
+
+	kvmclock_cpu_action(action);
 }
 
 static int kvm_cpu_online(unsigned int cpu)
@@ -726,7 +727,7 @@ static int kvm_cpu_down_prepare(unsigned int cpu)
 	unsigned long flags;
 
 	local_irq_save(flags);
-	kvm_guest_cpu_offline(false);
+	kvm_guest_cpu_offline(KVM_GUEST_AP_OFFLINE);
 	local_irq_restore(flags);
 	return 0;
 }
@@ -737,7 +738,7 @@ static int kvm_suspend(void *data)
 {
 	u64 val = 0;
 
-	kvm_guest_cpu_offline(false);
+	kvm_guest_cpu_offline(KVM_GUEST_BSP_SUSPEND);
 
 #ifdef CONFIG_ARCH_CPUIDLE_HALTPOLL
 	if (kvm_para_has_feature(KVM_FEATURE_POLL_CONTROL))
@@ -768,7 +769,7 @@ static struct syscore kvm_syscore = {
 
 static void kvm_pv_guest_cpu_reboot(void *unused)
 {
-	kvm_guest_cpu_offline(true);
+	kvm_guest_cpu_offline(KVM_GUEST_SHUTDOWN);
 }
 
 static int kvm_pv_reboot_notify(struct notifier_block *nb,
@@ -792,7 +793,7 @@ static struct notifier_block kvm_pv_reboot_nb = {
 #ifdef CONFIG_CRASH_DUMP
 static void kvm_crash_shutdown(struct pt_regs *regs)
 {
-	kvm_guest_cpu_offline(true);
+	kvm_guest_cpu_offline(KVM_GUEST_SHUTDOWN);
 	native_machine_crash_shutdown(regs);
 }
 #endif
diff --git a/arch/x86/kernel/kvmclock.c b/arch/x86/kernel/kvmclock.c
index 13c728444e12..13c4be3a7f0a 100644
--- a/arch/x86/kernel/kvmclock.c
+++ b/arch/x86/kernel/kvmclock.c
@@ -177,8 +177,22 @@ static void kvm_register_clock(char *txt)
 	pr_debug("kvm-clock: cpu %d, msr %llx, %s", smp_processor_id(), pa, txt);
 }
 
+static void kvmclock_disable(void)
+{
+	if (msr_kvm_system_time)
+		native_write_msr(msr_kvm_system_time, 0);
+}
+
 static void kvm_save_sched_clock_state(void)
 {
+	/*
+	 * Stop host writes to kvmclock immediately prior to suspend/hibernate.
+	 * If the system is hibernating, then kvmclock will likely reside at a
+	 * different physical address when the system awakens, and host writes
+	 * to the old address prior to reconfiguring kvmclock would clobber
+	 * random memory.
+	 */
+	kvmclock_disable();
 }
 
 static void kvm_restore_sched_clock_state(void)
@@ -186,6 +200,17 @@ static void kvm_restore_sched_clock_state(void)
 	kvm_register_clock("primary cpu clock, resume");
 }
 
+void kvmclock_cpu_action(enum kvm_guest_cpu_action action)
+{
+	/*
+	 * Don't disable kvmclock on the BSP during suspend.  If kvmclock is
+	 * being used for sched_clock, then it needs to be kept alive until the
+	 * last minute, and restored as quickly as possible after resume.
+	 */
+	if (action != KVM_GUEST_BSP_SUSPEND)
+		kvmclock_disable();
+}
+
 #ifdef CONFIG_SMP
 static void kvm_setup_secondary_clock(void)
 {
@@ -193,12 +218,6 @@ static void kvm_setup_secondary_clock(void)
 }
 #endif
 
-void kvmclock_disable(void)
-{
-	if (msr_kvm_system_time)
-		native_write_msr(msr_kvm_system_time, 0);
-}
-
 static void __init kvmclock_init_mem(void)
 {
 	unsigned long ncpus;

---

## [28] Sean Christopherson — 2026-05-29
*Subject: [PATCH v4 27/47] x86/paravirt: Remove unnecessary PARAVIRT=n stub for paravirt_set_sched_clock()*

Remove the unnecessary paravirt_set_sched_clock() stub for PARAVIRT=n, as
all callers are gated by PARAVIRT=y.  Eliminating the stub will avoid a
pile of pointless churn as the "real" implementation evolves.

No functional change intended.

Fixes: 39965afb1151 ("x86/paravirt: Move paravirt_sched_clock() related code into tsc.c")
Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/timer.h | 3 +++
 arch/x86/kernel/tsc.c        | 1 -
 2 files changed, 3 insertions(+), 1 deletion(-)

diff --git a/arch/x86/include/asm/timer.h b/arch/x86/include/asm/timer.h
index fda18bcb19b4..c71b466d6ace 100644
--- a/arch/x86/include/asm/timer.h
+++ b/arch/x86/include/asm/timer.h
@@ -12,7 +12,10 @@ extern void recalibrate_cpu_khz(void);
 extern int no_timer_check;
 
 extern bool using_native_sched_clock(void);
+
+#ifdef CONFIG_PARAVIRT
 void paravirt_set_sched_clock(u64 (*func)(void));
+#endif
 
 /*
  * We use the full linear equation: f(x) = a + b*x, in order to allow
diff --git a/arch/x86/kernel/tsc.c b/arch/x86/kernel/tsc.c
index bdff8c988866..888bd1cbd9bc 100644
--- a/arch/x86/kernel/tsc.c
+++ b/arch/x86/kernel/tsc.c
@@ -288,7 +288,6 @@ void paravirt_set_sched_clock(u64 (*func)(void))
 u64 sched_clock_noinstr(void) __attribute__((alias("native_sched_clock")));
 
 bool using_native_sched_clock(void) { return true; }
-void paravirt_set_sched_clock(u64 (*func)(void)) { }
 #endif
 
 notrace u64 sched_clock(void)

---

## [29] Sean Christopherson — 2026-05-29
*Subject: [PATCH v4 28/47] x86/paravirt: Move handling of unstable PV clocks
 into paravirt_set_sched_clock()*

Move the handling of unstable PV clocks, of which kvmclock is the only
example, into paravirt_set_sched_clock().  This will allow modifying
paravirt_set_sched_clock() to keep using the TSC for sched_clock in
certain scenarios without unintentionally marking the TSC-based clock as
unstable.

No functional change intended.

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/timer.h | 7 ++++++-
 arch/x86/kernel/kvmclock.c   | 5 +----
 arch/x86/kernel/tsc.c        | 5 ++++-
 3 files changed, 11 insertions(+), 6 deletions(-)

diff --git a/arch/x86/include/asm/timer.h b/arch/x86/include/asm/timer.h
index c71b466d6ace..fe41d40a9ae6 100644
--- a/arch/x86/include/asm/timer.h
+++ b/arch/x86/include/asm/timer.h
@@ -14,7 +14,12 @@ extern int no_timer_check;
 extern bool using_native_sched_clock(void);
 
 #ifdef CONFIG_PARAVIRT
-void paravirt_set_sched_clock(u64 (*func)(void));
+void __paravirt_set_sched_clock(u64 (*func)(void), bool stable);
+
+static inline void paravirt_set_sched_clock(u64 (*func)(void))
+{
+	__paravirt_set_sched_clock(func, true);
+}
 #endif
 
 /*
diff --git a/arch/x86/kernel/kvmclock.c b/arch/x86/kernel/kvmclock.c
index 13c4be3a7f0a..4e50e75ff43d 100644
--- a/arch/x86/kernel/kvmclock.c
+++ b/arch/x86/kernel/kvmclock.c
@@ -12,7 +12,6 @@
 #include <linux/hardirq.h>
 #include <linux/cpuhotplug.h>
 #include <linux/sched.h>
-#include <linux/sched/clock.h>
 #include <linux/mm.h>
 #include <linux/slab.h>
 #include <linux/set_memory.h>
@@ -94,10 +93,8 @@ static noinstr u64 kvm_sched_clock_read(void)
 
 static inline void kvm_sched_clock_init(bool stable)
 {
-	if (!stable)
-		clear_sched_clock_stable();
 	kvm_sched_clock_offset = kvm_clock_read();
-	paravirt_set_sched_clock(kvm_sched_clock_read);
+	__paravirt_set_sched_clock(kvm_sched_clock_read, stable);
 
 	pr_info("kvm-clock: using sched offset of %llu cycles",
 		kvm_sched_clock_offset);
diff --git a/arch/x86/kernel/tsc.c b/arch/x86/kernel/tsc.c
index 888bd1cbd9bc..a9b6d3399c23 100644
--- a/arch/x86/kernel/tsc.c
+++ b/arch/x86/kernel/tsc.c
@@ -280,8 +280,11 @@ bool using_native_sched_clock(void)
 	return static_call_query(pv_sched_clock) == native_sched_clock;
 }
 
-void paravirt_set_sched_clock(u64 (*func)(void))
+void __paravirt_set_sched_clock(u64 (*func)(void), bool stable)
 {
+	if (!stable)
+		clear_sched_clock_stable();
+
 	static_call_update(pv_sched_clock, func);
 }
 #else

---

## [30] Sean Christopherson — 2026-05-29
*Subject: [PATCH v4 29/47] x86/kvmclock: Move sched_clock save/restore helpers
 up in kvmclock.c*

Move kvmclock's sched_clock save/restore helper "up" so that they can
(eventually) be referenced by kvm_sched_clock_init().

No functional change intended.

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kernel/kvmclock.c | 108 ++++++++++++++++++-------------------
 1 file changed, 54 insertions(+), 54 deletions(-)

diff --git a/arch/x86/kernel/kvmclock.c b/arch/x86/kernel/kvmclock.c
index 4e50e75ff43d..0d4f2cf97246 100644
--- a/arch/x86/kernel/kvmclock.c
+++ b/arch/x86/kernel/kvmclock.c
@@ -71,6 +71,25 @@ static int kvm_set_wallclock(const struct timespec64 *now)
 	return -ENODEV;
 }
 
+static void kvm_register_clock(char *txt)
+{
+	struct pvclock_vsyscall_time_info *src = this_cpu_hvclock();
+	u64 pa;
+
+	if (!src)
+		return;
+
+	pa = slow_virt_to_phys(&src->pvti) | 0x01ULL;
+	wrmsrq(msr_kvm_system_time, pa);
+	pr_debug("kvm-clock: cpu %d, msr %llx, %s", smp_processor_id(), pa, txt);
+}
+
+static void kvmclock_disable(void)
+{
+	if (msr_kvm_system_time)
+		native_write_msr(msr_kvm_system_time, 0);
+}
+
 static u64 kvm_clock_read(void)
 {
 	u64 ret;
@@ -91,6 +110,30 @@ static noinstr u64 kvm_sched_clock_read(void)
 	return pvclock_clocksource_read_nowd(this_cpu_pvti()) - kvm_sched_clock_offset;
 }
 
+static void kvm_save_sched_clock_state(void)
+{
+	/*
+	 * Stop host writes to kvmclock immediately prior to suspend/hibernate.
+	 * If the system is hibernating, then kvmclock will likely reside at a
+	 * different physical address when the system awakens, and host writes
+	 * to the old address prior to reconfiguring kvmclock would clobber
+	 * random memory.
+	 */
+	kvmclock_disable();
+}
+
+#ifdef CONFIG_SMP
+static void kvm_setup_secondary_clock(void)
+{
+	kvm_register_clock("secondary cpu clock");
+}
+#endif
+
+static void kvm_restore_sched_clock_state(void)
+{
+	kvm_register_clock("primary cpu clock, resume");
+}
+
 static inline void kvm_sched_clock_init(bool stable)
 {
 	kvm_sched_clock_offset = kvm_clock_read();
@@ -103,6 +146,17 @@ static inline void kvm_sched_clock_init(bool stable)
 		sizeof(((struct pvclock_vcpu_time_info *)NULL)->system_time));
 }
 
+void kvmclock_cpu_action(enum kvm_guest_cpu_action action)
+{
+	/*
+	 * Don't disable kvmclock on the BSP during suspend.  If kvmclock is
+	 * being used for sched_clock, then it needs to be kept alive until the
+	 * last minute, and restored as quickly as possible after resume.
+	 */
+	if (action != KVM_GUEST_BSP_SUSPEND)
+		kvmclock_disable();
+}
+
 /*
  * If we don't do that, there is the possibility that the guest
  * will calibrate under heavy load - thus, getting a lower lpj -
@@ -161,60 +215,6 @@ static struct clocksource kvm_clock = {
 	.enable	= kvm_cs_enable,
 };
 
-static void kvm_register_clock(char *txt)
-{
-	struct pvclock_vsyscall_time_info *src = this_cpu_hvclock();
-	u64 pa;
-
-	if (!src)
-		return;
-
-	pa = slow_virt_to_phys(&src->pvti) | 0x01ULL;
-	wrmsrq(msr_kvm_system_time, pa);
-	pr_debug("kvm-clock: cpu %d, msr %llx, %s", smp_processor_id(), pa, txt);
-}
-
-static void kvmclock_disable(void)
-{
-	if (msr_kvm_system_time)
-		native_write_msr(msr_kvm_system_time, 0);
-}
-
-static void kvm_save_sched_clock_state(void)
-{
-	/*
-	 * Stop host writes to kvmclock immediately prior to suspend/hibernate.
-	 * If the system is hibernating, then kvmclock will likely reside at a
-	 * different physical address when the system awakens, and host writes
-	 * to the old address prior to reconfiguring kvmclock would clobber
-	 * random memory.
-	 */
-	kvmclock_disable();
-}
-
-static void kvm_restore_sched_clock_state(void)
-{
-	kvm_register_clock("primary cpu clock, resume");
-}
-
-void kvmclock_cpu_action(enum kvm_guest_cpu_action action)
-{
-	/*
-	 * Don't disable kvmclock on the BSP during suspend.  If kvmclock is
-	 * being used for sched_clock, then it needs to be kept alive until the
-	 * last minute, and restored as quickly as possible after resume.
-	 */
-	if (action != KVM_GUEST_BSP_SUSPEND)
-		kvmclock_disable();
-}
-
-#ifdef CONFIG_SMP
-static void kvm_setup_secondary_clock(void)
-{
-	kvm_register_clock("secondary cpu clock");
-}
-#endif
-
 static void __init kvmclock_init_mem(void)
 {
 	unsigned long ncpus;

---

## [31] Sean Christopherson — 2026-05-29
*Subject: [PATCH v4 30/47] x86/xen/time: NOP-ify x86_platform's sched_clock
 save/restore hooks*

NOP-ify the x86_platform sched_clock save/restore hooks when setting up
Xen's PV clock to make it somewhat obvious the hooks aren't used when
running as a Xen guest (Xen uses a paravirtualized suspend/resume flow).

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/xen/time.c | 6 ++++++
 1 file changed, 6 insertions(+)

diff --git a/arch/x86/xen/time.c b/arch/x86/xen/time.c
index 36d66abf5379..640b71d22d97 100644
--- a/arch/x86/xen/time.c
+++ b/arch/x86/xen/time.c
@@ -578,6 +578,12 @@ static void __init xen_init_time_common(void)
 	xen_sched_clock_offset = xen_clocksource_read();
 	static_call_update(pv_steal_clock, xen_steal_clock);
 	paravirt_set_sched_clock(xen_sched_clock);
+	/*
+	 * Xen has paravirtualized suspend/resume and so doesn't use the common
+	 * x86 sched_clock save/restore hooks.
+	 */
+	x86_platform.save_sched_clock_state = x86_init_noop;
+	x86_platform.restore_sched_clock_state = x86_init_noop;
 
 	x86_init.hyper.get_tsc_khz = xen_tsc_khz;
 	x86_platform.get_wallclock = xen_get_wallclock;

---

## [32] Sean Christopherson — 2026-05-29
*Subject: [PATCH v4 31/47] x86/vmware: NOP-ify save/restore hooks when using
 VMware's sched_clock*

NOP-ify the sched_clock save/restore hooks when using VMware's version of
sched_clock.  This will allow extending paravirt_set_sched_clock() to set
the save/restore hooks, without having to simultaneously change the
behavior of VMware guests.

Note, it's not at all obvious that it's safe/correct for VMware guests to
do nothing on suspend/resume, but that's a pre-existing problem.  Leave it
for a VMware expert to sort out.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kernel/cpu/vmware.c | 5 ++++-
 1 file changed, 4 insertions(+), 1 deletion(-)

diff --git a/arch/x86/kernel/cpu/vmware.c b/arch/x86/kernel/cpu/vmware.c
index 2d0624c66799..051ef89029a7 100644
--- a/arch/x86/kernel/cpu/vmware.c
+++ b/arch/x86/kernel/cpu/vmware.c
@@ -347,8 +347,11 @@ static void __init vmware_paravirt_ops_setup(void)
 
 	vmware_cyc2ns_setup();
 
-	if (vmw_sched_clock)
+	if (vmw_sched_clock) {
 		paravirt_set_sched_clock(vmware_sched_clock);
+		x86_platform.save_sched_clock_state = x86_init_noop;
+		x86_platform.restore_sched_clock_state = x86_init_noop;
+	}
 
 	if (vmware_is_stealclock_available()) {
 		has_steal_clock = true;

---

## [33] Sean Christopherson — 2026-05-29
*Subject: [PATCH v4 32/47] x86/tsc: WARN if TSC sched_clock save/restore used
 with PV sched_clock*

Now that all PV clocksources override the sched_clock save/restore hooks
when overriding sched_clock, WARN if the "default" TSC hooks are invoked
when using a PV sched_clock, e.g. to guard against regressions.

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kernel/tsc.c | 12 ++++++++++--
 1 file changed, 10 insertions(+), 2 deletions(-)

diff --git a/arch/x86/kernel/tsc.c b/arch/x86/kernel/tsc.c
index a9b6d3399c23..19da1a3d2126 100644
--- a/arch/x86/kernel/tsc.c
+++ b/arch/x86/kernel/tsc.c
@@ -972,9 +972,17 @@ EXPORT_SYMBOL_GPL(recalibrate_cpu_khz);
 
 static unsigned long long cyc2ns_suspend;
 
+static __always_inline bool tsc_is_save_restore_needed(void)
+{
+	if (WARN_ON_ONCE(!using_native_sched_clock()))
+		return false;
+
+	return static_branch_likely(&__use_tsc) || sched_clock_stable();
+}
+
 void tsc_save_sched_clock_state(void)
 {
-	if (!static_branch_likely(&__use_tsc) && !sched_clock_stable())
+	if (!tsc_is_save_restore_needed())
 		return;
 
 	cyc2ns_suspend = sched_clock();
@@ -994,7 +1002,7 @@ void tsc_restore_sched_clock_state(void)
 	unsigned long flags;
 	int cpu;
 
-	if (!static_branch_likely(&__use_tsc) && !sched_clock_stable())
+	if (!tsc_is_save_restore_needed())
 		return;
 
 	local_irq_save(flags);

---

## [34] Sean Christopherson — 2026-05-29
*Subject: [PATCH v4 33/47] x86/paravirt: Pass sched_clock save/restore helpers
 during registration*

Pass in a PV clock's save/restore helpers when configuring sched_clock
instead of relying on each PV clock to manually set the save/restore hooks.
In addition to bringing sanity to the code, this will allow gracefully
"rejecting" a PV sched_clock, e.g. when running as a CoCo guest that has
access to a "secure" TSC.

No functional change intended.

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/timer.h       | 9 ++++++---
 arch/x86/kernel/cpu/vmware.c       | 8 +++-----
 arch/x86/kernel/kvmclock.c         | 6 +++---
 arch/x86/kernel/tsc.c              | 5 ++++-
 arch/x86/xen/time.c                | 5 ++---
 drivers/clocksource/hyperv_timer.c | 6 ++----
 6 files changed, 20 insertions(+), 19 deletions(-)

diff --git a/arch/x86/include/asm/timer.h b/arch/x86/include/asm/timer.h
index fe41d40a9ae6..e97cd1ae03d1 100644
--- a/arch/x86/include/asm/timer.h
+++ b/arch/x86/include/asm/timer.h
@@ -14,11 +14,14 @@ extern int no_timer_check;
 extern bool using_native_sched_clock(void);
 
 #ifdef CONFIG_PARAVIRT
-void __paravirt_set_sched_clock(u64 (*func)(void), bool stable);
+void __paravirt_set_sched_clock(u64 (*func)(void), bool stable,
+				void (*save)(void), void (*restore)(void));
 
-static inline void paravirt_set_sched_clock(u64 (*func)(void))
+static inline void paravirt_set_sched_clock(u64 (*func)(void),
+					    void (*save)(void),
+					    void (*restore)(void))
 {
-	__paravirt_set_sched_clock(func, true);
+	__paravirt_set_sched_clock(func, true, save, restore);
 }
 #endif
 
diff --git a/arch/x86/kernel/cpu/vmware.c b/arch/x86/kernel/cpu/vmware.c
index 051ef89029a7..f3ffc05c7c53 100644
--- a/arch/x86/kernel/cpu/vmware.c
+++ b/arch/x86/kernel/cpu/vmware.c
@@ -347,11 +347,9 @@ static void __init vmware_paravirt_ops_setup(void)
 
 	vmware_cyc2ns_setup();
 
-	if (vmw_sched_clock) {
-		paravirt_set_sched_clock(vmware_sched_clock);
-		x86_platform.save_sched_clock_state = x86_init_noop;
-		x86_platform.restore_sched_clock_state = x86_init_noop;
-	}
+	if (vmw_sched_clock)
+		paravirt_set_sched_clock(vmware_sched_clock,
+					 x86_init_noop, x86_init_noop);
 
 	if (vmware_is_stealclock_available()) {
 		has_steal_clock = true;
diff --git a/arch/x86/kernel/kvmclock.c b/arch/x86/kernel/kvmclock.c
index 0d4f2cf97246..05bca2be0df3 100644
--- a/arch/x86/kernel/kvmclock.c
+++ b/arch/x86/kernel/kvmclock.c
@@ -137,7 +137,9 @@ static void kvm_restore_sched_clock_state(void)
 static inline void kvm_sched_clock_init(bool stable)
 {
 	kvm_sched_clock_offset = kvm_clock_read();
-	__paravirt_set_sched_clock(kvm_sched_clock_read, stable);
+	__paravirt_set_sched_clock(kvm_sched_clock_read, stable,
+				   kvm_save_sched_clock_state,
+				   kvm_restore_sched_clock_state);
 
 	pr_info("kvm-clock: using sched offset of %llu cycles",
 		kvm_sched_clock_offset);
@@ -345,8 +347,6 @@ void __init kvmclock_init(bool prefer_tsc)
 #ifdef CONFIG_SMP
 	x86_cpuinit.early_percpu_clock_init = kvm_setup_secondary_clock;
 #endif
-	x86_platform.save_sched_clock_state = kvm_save_sched_clock_state;
-	x86_platform.restore_sched_clock_state = kvm_restore_sched_clock_state;
 	kvm_get_preset_lpj();
 
 	/*
diff --git a/arch/x86/kernel/tsc.c b/arch/x86/kernel/tsc.c
index 19da1a3d2126..7fbcfc2efd1d 100644
--- a/arch/x86/kernel/tsc.c
+++ b/arch/x86/kernel/tsc.c
@@ -280,12 +280,15 @@ bool using_native_sched_clock(void)
 	return static_call_query(pv_sched_clock) == native_sched_clock;
 }
 
-void __paravirt_set_sched_clock(u64 (*func)(void), bool stable)
+void __paravirt_set_sched_clock(u64 (*func)(void), bool stable,
+				void (*save)(void), void (*restore)(void))
 {
 	if (!stable)
 		clear_sched_clock_stable();
 
 	static_call_update(pv_sched_clock, func);
+	x86_platform.save_sched_clock_state = save;
+	x86_platform.restore_sched_clock_state = restore;
 }
 #else
 u64 sched_clock_noinstr(void) __attribute__((alias("native_sched_clock")));
diff --git a/arch/x86/xen/time.c b/arch/x86/xen/time.c
index 640b71d22d97..91ef83b1e540 100644
--- a/arch/x86/xen/time.c
+++ b/arch/x86/xen/time.c
@@ -577,13 +577,12 @@ static void __init xen_init_time_common(void)
 {
 	xen_sched_clock_offset = xen_clocksource_read();
 	static_call_update(pv_steal_clock, xen_steal_clock);
-	paravirt_set_sched_clock(xen_sched_clock);
+
 	/*
 	 * Xen has paravirtualized suspend/resume and so doesn't use the common
 	 * x86 sched_clock save/restore hooks.
 	 */
-	x86_platform.save_sched_clock_state = x86_init_noop;
-	x86_platform.restore_sched_clock_state = x86_init_noop;
+	paravirt_set_sched_clock(xen_sched_clock, x86_init_noop, x86_init_noop);
 
 	x86_init.hyper.get_tsc_khz = xen_tsc_khz;
 	x86_platform.get_wallclock = xen_get_wallclock;
diff --git a/drivers/clocksource/hyperv_timer.c b/drivers/clocksource/hyperv_timer.c
index ac1d9f9c381c..dee59ce61c29 100644
--- a/drivers/clocksource/hyperv_timer.c
+++ b/drivers/clocksource/hyperv_timer.c
@@ -553,10 +553,8 @@ static void hv_restore_sched_clock_state(void)
 static __always_inline void hv_setup_sched_clock(void *sched_clock)
 {
 	/* We're on x86/x64 *and* using PV ops */
-	paravirt_set_sched_clock(sched_clock);
-
-	x86_platform.save_sched_clock_state = hv_save_sched_clock_state;
-	x86_platform.restore_sched_clock_state = hv_restore_sched_clock_state;
+	paravirt_set_sched_clock(sched_clock, hv_save_sched_clock_state,
+				 hv_restore_sched_clock_state);
 }
 #else /* !CONFIG_GENERIC_SCHED_CLOCK && !CONFIG_PARAVIRT */
 static __always_inline void hv_setup_sched_clock(void *sched_clock) {}

---

## [35] Sean Christopherson — 2026-05-29
*Subject: [PATCH v4 34/47] x86/kvmclock: Move kvm_sched_clock_init() down in kvmclock.c*

Move kvm_sched_clock_init() "down" so that it can reference the global
kvm_clock structure without needing a forward declaration.

Opportunistically mark the helper as "__init" instead of "inline" to make
its usage more obvious; modern compilers don't need a hint to inline a
single-use function, and an extra CALL+RET pair during boot is a complete
non-issue.  And, if the compiler ignores the hint and does NOT inline the
function, the resulting code may not get discarded after boot due lack of
an __init annotation.

No functional change intended.

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kernel/kvmclock.c | 28 ++++++++++++++--------------
 1 file changed, 14 insertions(+), 14 deletions(-)

diff --git a/arch/x86/kernel/kvmclock.c b/arch/x86/kernel/kvmclock.c
index 05bca2be0df3..6372b4dc7b0c 100644
--- a/arch/x86/kernel/kvmclock.c
+++ b/arch/x86/kernel/kvmclock.c
@@ -134,20 +134,6 @@ static void kvm_restore_sched_clock_state(void)
 	kvm_register_clock("primary cpu clock, resume");
 }
 
-static inline void kvm_sched_clock_init(bool stable)
-{
-	kvm_sched_clock_offset = kvm_clock_read();
-	__paravirt_set_sched_clock(kvm_sched_clock_read, stable,
-				   kvm_save_sched_clock_state,
-				   kvm_restore_sched_clock_state);
-
-	pr_info("kvm-clock: using sched offset of %llu cycles",
-		kvm_sched_clock_offset);
-
-	BUILD_BUG_ON(sizeof(kvm_sched_clock_offset) >
-		sizeof(((struct pvclock_vcpu_time_info *)NULL)->system_time));
-}
-
 void kvmclock_cpu_action(enum kvm_guest_cpu_action action)
 {
 	/*
@@ -303,6 +289,20 @@ static int kvmclock_setup_percpu(unsigned int cpu)
 	return p ? 0 : -ENOMEM;
 }
 
+static __init void kvm_sched_clock_init(bool stable)
+{
+	kvm_sched_clock_offset = kvm_clock_read();
+	__paravirt_set_sched_clock(kvm_sched_clock_read, stable,
+				   kvm_save_sched_clock_state,
+				   kvm_restore_sched_clock_state);
+
+	pr_info("kvm-clock: using sched offset of %llu cycles",
+		kvm_sched_clock_offset);
+
+	BUILD_BUG_ON(sizeof(kvm_sched_clock_offset) >
+		sizeof(((struct pvclock_vcpu_time_info *)NULL)->system_time));
+}
+
 void __init kvmclock_init(bool prefer_tsc)
 {
 	u8 flags;

---

## [36] Sean Christopherson — 2026-05-29
*Subject: [PATCH v4 35/47] x86/xen/time: Mark xen_setup_vsyscall_time_info() as __init*

Annotate xen_setup_vsyscall_time_info() as being used only during kernel
initialization; it's called only by xen_time_init(), which is already
tagged __init.

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/xen/time.c | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)

diff --git a/arch/x86/xen/time.c b/arch/x86/xen/time.c
index 91ef83b1e540..8f4511f91d16 100644
--- a/arch/x86/xen/time.c
+++ b/arch/x86/xen/time.c
@@ -454,7 +454,7 @@ void xen_restore_time_memory_area(void)
 	xen_sched_clock_offset = xen_clocksource_read() - xen_clock_value_saved;
 }
 
-static void xen_setup_vsyscall_time_info(void)
+static void __init xen_setup_vsyscall_time_info(void)
 {
 	struct vcpu_register_time_memory_area t;
 	struct pvclock_vsyscall_time_info *ti;

---

## [37] Sean Christopherson — 2026-05-29
*Subject: [PATCH v4 36/47] x86/pvclock: Mark setup helpers and related various
 as __init/__ro_after_init*

Now that Xen PV clock and kvmclock explicitly do setup only during init,
tag the common PV clock flags/vsyscall variables and their mutators with
__init.

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kernel/pvclock.c | 8 ++++----
 1 file changed, 4 insertions(+), 4 deletions(-)

diff --git a/arch/x86/kernel/pvclock.c b/arch/x86/kernel/pvclock.c
index b3f81379c2fc..a51adce67f92 100644
--- a/arch/x86/kernel/pvclock.c
+++ b/arch/x86/kernel/pvclock.c
@@ -16,10 +16,10 @@
 #include <asm/pvclock.h>
 #include <asm/vgtod.h>
 
-static u8 valid_flags __read_mostly = 0;
-static struct pvclock_vsyscall_time_info *pvti_cpu0_va __read_mostly;
+static u8 valid_flags __ro_after_init = 0;
+static struct pvclock_vsyscall_time_info *pvti_cpu0_va __ro_after_init;
 
-void pvclock_set_flags(u8 flags)
+void __init pvclock_set_flags(u8 flags)
 {
 	valid_flags = flags;
 }
@@ -153,7 +153,7 @@ void pvclock_read_wallclock(struct pvclock_wall_clock *wall_clock,
 	set_normalized_timespec64(ts, now.tv_sec, now.tv_nsec);
 }
 
-void pvclock_set_pvti_cpu0_va(struct pvclock_vsyscall_time_info *pvti)
+void __init pvclock_set_pvti_cpu0_va(struct pvclock_vsyscall_time_info *pvti)
 {
 	WARN_ON(vclock_was_used(VDSO_CLOCKMODE_PVCLOCK));
 	pvti_cpu0_va = pvti;

---

## [38] Sean Christopherson — 2026-05-29
*Subject: [PATCH v4 37/47] x86/pvclock: WARN if pvclock's valid_flags are overwritten*

WARN if the common PV clock valid_flags are overwritten; all PV clocks
expect that they are the one and only PV clock, i.e. don't guard against
another PV clock having modified the flags.

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kernel/pvclock.c | 1 +
 1 file changed, 1 insertion(+)

diff --git a/arch/x86/kernel/pvclock.c b/arch/x86/kernel/pvclock.c
index a51adce67f92..8d098841a225 100644
--- a/arch/x86/kernel/pvclock.c
+++ b/arch/x86/kernel/pvclock.c
@@ -21,6 +21,7 @@ static struct pvclock_vsyscall_time_info *pvti_cpu0_va __ro_after_init;
 
 void __init pvclock_set_flags(u8 flags)
 {
+	WARN_ON(valid_flags);
 	valid_flags = flags;
 }

---

## [39] Sean Christopherson — 2026-05-29
*Subject: [PATCH v4 38/47] x86/kvmclock: Refactor handling of
 PVCLOCK_TSC_STABLE_BIT during kvmclock_init()*

Clean up the setting of PVCLOCK_TSC_STABLE_BIT during kvmclock init to
make it somewhat obvious that pvclock_read_flags() must be called *after*
pvclock_set_flags().

Note, in theory, a different PV clock could have set PVCLOCK_TSC_STABLE_BIT
in the supported flags, i.e. reading flags only if
KVM_FEATURE_CLOCKSOURCE_STABLE_BIT is set could very, very theoretically
result in a change in behavior.  In practice, the kernel only supports a
single PV clock.

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kernel/kvmclock.c | 15 +++++++++++----
 1 file changed, 11 insertions(+), 4 deletions(-)

diff --git a/arch/x86/kernel/kvmclock.c b/arch/x86/kernel/kvmclock.c
index 6372b4dc7b0c..4e304f1c887d 100644
--- a/arch/x86/kernel/kvmclock.c
+++ b/arch/x86/kernel/kvmclock.c
@@ -305,7 +305,7 @@ static __init void kvm_sched_clock_init(bool stable)
 
 void __init kvmclock_init(bool prefer_tsc)
 {
-	u8 flags;
+	bool stable = false;
 
 	if (!kvm_para_available() || !kvmclock)
 		return;
@@ -332,11 +332,18 @@ void __init kvmclock_init(bool prefer_tsc)
 	kvm_register_clock("primary cpu clock");
 	pvclock_set_pvti_cpu0_va(hv_clock_boot);
 
-	if (kvm_para_has_feature(KVM_FEATURE_CLOCKSOURCE_STABLE_BIT))
+	if (kvm_para_has_feature(KVM_FEATURE_CLOCKSOURCE_STABLE_BIT)) {
 		pvclock_set_flags(PVCLOCK_TSC_STABLE_BIT);
 
-	flags = pvclock_read_flags(&hv_clock_boot[0].pvti);
-	kvm_sched_clock_init(flags & PVCLOCK_TSC_STABLE_BIT);
+		/*
+		 * Check if the clock is stable *after* marking TSC_STABLE as a
+		 * valid flag.
+		 */
+		stable = pvclock_read_flags(&hv_clock_boot[0].pvti) &
+			 PVCLOCK_TSC_STABLE_BIT;
+	}
+
+	kvm_sched_clock_init(stable);
 
 	if (!x86_init.hyper.get_tsc_khz)
 		x86_init.hyper.get_tsc_khz = kvmclock_get_tsc_khz;

---

## [40] Sean Christopherson — 2026-05-29
*Subject: [PATCH v4 39/47] timekeeping: Resume clocksources before reading
 persistent clock*

When resuming timekeeping after suspend, restore clocksources prior to
reading the persistent clock.  Paravirt clocks, e.g. kvmclock, tie the
validity of a PV persistent clock to a clocksource, i.e. reading the PV
persistent clock will return garbage if the underlying PV clocksource
hasn't been enabled.  The flaw has gone unnoticed because kvmclock is a
mess and uses its own suspend/resume hooks instead of the clocksource
suspend/resume hooks, which happens to work by sheer dumb luck (the
kvmclock resume hook runs before timekeeping_resume()).

Note, there is no evidence that any clocksource supported by the kernel
depends on a persistent clock.

Reviewed-by: Thomas Gleixner <tglx@linutronix.de>
Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 kernel/time/timekeeping.c | 9 +++++++--
 1 file changed, 7 insertions(+), 2 deletions(-)

diff --git a/kernel/time/timekeeping.c b/kernel/time/timekeeping.c
index c493a4010305..26f3291a814d 100644
--- a/kernel/time/timekeeping.c
+++ b/kernel/time/timekeeping.c
@@ -2098,11 +2098,16 @@ void timekeeping_resume(void)
 	u64 cycle_now, nsec;
 	unsigned long flags;
 
-	read_persistent_clock64(&ts_new);
-
 	clockevents_resume();
 	clocksource_resume();
 
+	/*
+	 * Read persistent time after clocksources have been resumed.  Paravirt
+	 * clocks have a nasty habit of piggybacking a persistent clock on a
+	 * system clock, and may return garbage if the system clock is suspended.
+	 */
+	read_persistent_clock64(&ts_new);
+
 	raw_spin_lock_irqsave(&tk_core.lock, flags);
 
 	/*

---

## [41] Sean Christopherson — 2026-05-29
*Subject: [PATCH v4 40/47] x86/kvmclock: Hook clocksource.suspend/resume when
 kvmclock isn't sched_clock*

Save/restore kvmclock across suspend/resume via clocksource hooks when
kvmclock isn't being used for sched_clock.  This will allow using kvmclock
as a clocksource (or for wallclock!) without also using it for sched_clock.

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kernel/kvmclock.c | 23 ++++++++++++++++++++++-
 1 file changed, 22 insertions(+), 1 deletion(-)

diff --git a/arch/x86/kernel/kvmclock.c b/arch/x86/kernel/kvmclock.c
index 4e304f1c887d..5dfac79a5d30 100644
--- a/arch/x86/kernel/kvmclock.c
+++ b/arch/x86/kernel/kvmclock.c
@@ -131,7 +131,17 @@ static void kvm_setup_secondary_clock(void)
 
 static void kvm_restore_sched_clock_state(void)
 {
-	kvm_register_clock("primary cpu clock, resume");
+	kvm_register_clock("primary cpu, sched_clock resume");
+}
+
+static void kvmclock_suspend(struct clocksource *cs)
+{
+	kvmclock_disable();
+}
+
+static void kvmclock_resume(struct clocksource *cs)
+{
+	kvm_register_clock("primary cpu, clocksource resume");
 }
 
 void kvmclock_cpu_action(enum kvm_guest_cpu_action action)
@@ -201,6 +211,8 @@ static struct clocksource kvm_clock = {
 	.flags	= CLOCK_SOURCE_IS_CONTINUOUS,
 	.id     = CSID_X86_KVM_CLK,
 	.enable	= kvm_cs_enable,
+	.suspend = kvmclock_suspend,
+	.resume = kvmclock_resume,
 };
 
 static void __init kvmclock_init_mem(void)
@@ -296,6 +308,15 @@ static __init void kvm_sched_clock_init(bool stable)
 				   kvm_save_sched_clock_state,
 				   kvm_restore_sched_clock_state);
 
+	/*
+	 * The BSP's clock is managed via dedicated sched_clock save/restore
+	 * hooks when kvmclock is used as sched_clock, as sched_clock needs to
+	 * be kept alive until the very end of suspend entry, and restored as
+	 * quickly as possible after resume.
+	 */
+	kvm_clock.suspend = NULL;
+	kvm_clock.resume = NULL;
+
 	pr_info("kvm-clock: using sched offset of %llu cycles",
 		kvm_sched_clock_offset);

---

## [42] Sean Christopherson — 2026-05-29
*Subject: [PATCH v4 41/47] x86/kvmclock: WARN if wall clock is read while
 kvmclock is suspended*

WARN if kvmclock is still suspended when its wallclock is read, i.e. when
the kernel reads its persistent clock.  The wallclock subtly depends on
the BSP's kvmclock being enabled, and returns garbage if kvmclock is
disabled.

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kernel/kvmclock.c | 7 +++++++
 1 file changed, 7 insertions(+)

diff --git a/arch/x86/kernel/kvmclock.c b/arch/x86/kernel/kvmclock.c
index 5dfac79a5d30..73fabfac2bc9 100644
--- a/arch/x86/kernel/kvmclock.c
+++ b/arch/x86/kernel/kvmclock.c
@@ -53,6 +53,8 @@ static struct pvclock_vsyscall_time_info *hvclock_mem;
 DEFINE_PER_CPU(struct pvclock_vsyscall_time_info *, hv_clock_per_cpu);
 EXPORT_PER_CPU_SYMBOL_GPL(hv_clock_per_cpu);
 
+static bool kvmclock_suspended;
+
 /*
  * The wallclock is the time of day when we booted. Since then, some time may
  * have elapsed since the hypervisor wrote the data. So we try to account for
@@ -60,6 +62,7 @@ EXPORT_PER_CPU_SYMBOL_GPL(hv_clock_per_cpu);
  */
 static void kvm_get_wallclock(struct timespec64 *now)
 {
+	WARN_ON_ONCE(kvmclock_suspended);
 	wrmsrq(msr_kvm_wall_clock, slow_virt_to_phys(&wall_clock));
 	preempt_disable();
 	pvclock_read_wallclock(&wall_clock, this_cpu_pvti(), now);
@@ -119,6 +122,7 @@ static void kvm_save_sched_clock_state(void)
 	 * to the old address prior to reconfiguring kvmclock would clobber
 	 * random memory.
 	 */
+	kvmclock_suspended = true;
 	kvmclock_disable();
 }
 
@@ -131,16 +135,19 @@ static void kvm_setup_secondary_clock(void)
 
 static void kvm_restore_sched_clock_state(void)
 {
+	kvmclock_suspended = false;
 	kvm_register_clock("primary cpu, sched_clock resume");
 }
 
 static void kvmclock_suspend(struct clocksource *cs)
 {
+	kvmclock_suspended = true;
 	kvmclock_disable();
 }
 
 static void kvmclock_resume(struct clocksource *cs)
 {
+	kvmclock_suspended = false;
 	kvm_register_clock("primary cpu, clocksource resume");
 }

---

## [43] Sean Christopherson — 2026-05-29
*Subject: [PATCH v4 42/47] x86/paravirt: Mark __paravirt_set_sched_clock() as __init*

Annotate __paravirt_set_sched_clock() as __init, and make its wrapper
__always_inline to ensure sanitizers don't result in a non-inline version
hanging around.  All callers run during __init, and changing sched_clock
after boot would be all kinds of crazy.

No functional change intended.

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/timer.h | 10 +++++-----
 arch/x86/kernel/tsc.c        |  4 ++--
 2 files changed, 7 insertions(+), 7 deletions(-)

diff --git a/arch/x86/include/asm/timer.h b/arch/x86/include/asm/timer.h
index e97cd1ae03d1..96ae7feac47c 100644
--- a/arch/x86/include/asm/timer.h
+++ b/arch/x86/include/asm/timer.h
@@ -14,12 +14,12 @@ extern int no_timer_check;
 extern bool using_native_sched_clock(void);
 
 #ifdef CONFIG_PARAVIRT
-void __paravirt_set_sched_clock(u64 (*func)(void), bool stable,
-				void (*save)(void), void (*restore)(void));
+void __init __paravirt_set_sched_clock(u64 (*func)(void), bool stable,
+				       void (*save)(void), void (*restore)(void));
 
-static inline void paravirt_set_sched_clock(u64 (*func)(void),
-					    void (*save)(void),
-					    void (*restore)(void))
+static __always_inline void paravirt_set_sched_clock(u64 (*func)(void),
+						     void (*save)(void),
+						     void (*restore)(void))
 {
 	__paravirt_set_sched_clock(func, true, save, restore);
 }
diff --git a/arch/x86/kernel/tsc.c b/arch/x86/kernel/tsc.c
index 7fbcfc2efd1d..6da0a3ac05c2 100644
--- a/arch/x86/kernel/tsc.c
+++ b/arch/x86/kernel/tsc.c
@@ -280,8 +280,8 @@ bool using_native_sched_clock(void)
 	return static_call_query(pv_sched_clock) == native_sched_clock;
 }
 
-void __paravirt_set_sched_clock(u64 (*func)(void), bool stable,
-				void (*save)(void), void (*restore)(void))
+void __init __paravirt_set_sched_clock(u64 (*func)(void), bool stable,
+				       void (*save)(void), void (*restore)(void))
 {
 	if (!stable)
 		clear_sched_clock_stable();

---

## [44] Sean Christopherson — 2026-05-29
*Subject: [PATCH v4 43/47] x86/paravirt: Plumb a return code into __paravirt_set_sched_clock()*

Add a return code to __paravirt_set_sched_clock() so that the kernel can
reject attempts to use a PV sched_clock without breaking the caller.  E.g.
when running as a CoCo VM with a secure TSC, using a PV clock is generally
undesirable.

Note, kvmclock is the only PV clock that does anything "extra" beyond
simply registering itself as sched_clock, i.e. is the only caller that
needs to check the new return value.

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/timer.h | 6 +++---
 arch/x86/kernel/kvmclock.c   | 9 ++++++---
 arch/x86/kernel/tsc.c        | 5 +++--
 3 files changed, 12 insertions(+), 8 deletions(-)

diff --git a/arch/x86/include/asm/timer.h b/arch/x86/include/asm/timer.h
index 96ae7feac47c..ca5c95d48c03 100644
--- a/arch/x86/include/asm/timer.h
+++ b/arch/x86/include/asm/timer.h
@@ -14,14 +14,14 @@ extern int no_timer_check;
 extern bool using_native_sched_clock(void);
 
 #ifdef CONFIG_PARAVIRT
-void __init __paravirt_set_sched_clock(u64 (*func)(void), bool stable,
-				       void (*save)(void), void (*restore)(void));
+int __init __paravirt_set_sched_clock(u64 (*func)(void), bool stable,
+				      void (*save)(void), void (*restore)(void));
 
 static __always_inline void paravirt_set_sched_clock(u64 (*func)(void),
 						     void (*save)(void),
 						     void (*restore)(void))
 {
-	__paravirt_set_sched_clock(func, true, save, restore);
+	(void)__paravirt_set_sched_clock(func, true, save, restore);
 }
 #endif
 
diff --git a/arch/x86/kernel/kvmclock.c b/arch/x86/kernel/kvmclock.c
index 73fabfac2bc9..1336c24f59cf 100644
--- a/arch/x86/kernel/kvmclock.c
+++ b/arch/x86/kernel/kvmclock.c
@@ -310,10 +310,13 @@ static int kvmclock_setup_percpu(unsigned int cpu)
 
 static __init void kvm_sched_clock_init(bool stable)
 {
+	/* Ensure the offset is configured before making kvmclock visible! */
 	kvm_sched_clock_offset = kvm_clock_read();
-	__paravirt_set_sched_clock(kvm_sched_clock_read, stable,
-				   kvm_save_sched_clock_state,
-				   kvm_restore_sched_clock_state);
+
+	if (__paravirt_set_sched_clock(kvm_sched_clock_read, stable,
+				       kvm_save_sched_clock_state,
+				       kvm_restore_sched_clock_state))
+		return;
 
 	/*
 	 * The BSP's clock is managed via dedicated sched_clock save/restore
diff --git a/arch/x86/kernel/tsc.c b/arch/x86/kernel/tsc.c
index 6da0a3ac05c2..7bcf757bf551 100644
--- a/arch/x86/kernel/tsc.c
+++ b/arch/x86/kernel/tsc.c
@@ -280,8 +280,8 @@ bool using_native_sched_clock(void)
 	return static_call_query(pv_sched_clock) == native_sched_clock;
 }
 
-void __init __paravirt_set_sched_clock(u64 (*func)(void), bool stable,
-				       void (*save)(void), void (*restore)(void))
+int __init __paravirt_set_sched_clock(u64 (*func)(void), bool stable,
+				      void (*save)(void), void (*restore)(void))
 {
 	if (!stable)
 		clear_sched_clock_stable();
@@ -289,6 +289,7 @@ void __init __paravirt_set_sched_clock(u64 (*func)(void), bool stable,
 	static_call_update(pv_sched_clock, func);
 	x86_platform.save_sched_clock_state = save;
 	x86_platform.restore_sched_clock_state = restore;
+	return 0;
 }
 #else
 u64 sched_clock_noinstr(void) __attribute__((alias("native_sched_clock")));

---

## [45] Sean Christopherson — 2026-05-29
*Subject: [PATCH v4 44/47] x86/paravirt: Don't use a PV sched_clock in CoCo
 guests with trusted TSC*

Silently ignore attempts to switch to a paravirt sched_clock when running
as a CoCo guest with trusted TSC.  In hand-wavy theory, a misbehaving
hypervisor could attack the guest by manipulating the PV clock to affect
guest scheduling in some weird and/or predictable way.  More importantly,
reading TSC on such platforms is faster than any PV clock, and sched_clock
is all about speed.

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kernel/tsc.c | 9 +++++++++
 1 file changed, 9 insertions(+)

diff --git a/arch/x86/kernel/tsc.c b/arch/x86/kernel/tsc.c
index 7bcf757bf551..036916953f4a 100644
--- a/arch/x86/kernel/tsc.c
+++ b/arch/x86/kernel/tsc.c
@@ -283,6 +283,15 @@ bool using_native_sched_clock(void)
 int __init __paravirt_set_sched_clock(u64 (*func)(void), bool stable,
 				      void (*save)(void), void (*restore)(void))
 {
+	/*
+	 * Don't replace TSC with a PV clock when running as a CoCo guest and
+	 * the TSC is secure/trusted; PV clocks are emulated by the hypervisor,
+	 * which isn't in the guest's TCB.
+	 */
+	if (cc_platform_has(CC_ATTR_GUEST_SNP_SECURE_TSC) ||
+	    boot_cpu_has(X86_FEATURE_TDX_GUEST))
+		return -EPERM;
+
 	if (!stable)
 		clear_sched_clock_stable();

---

## [46] Sean Christopherson — 2026-05-29
*Subject: [PATCH v4 45/47] x86/kvmclock: Use TSC for sched_clock if it's
 constant and non-stop*

Prefer the TSC over kvmclock for sched_clock if the TSC is constant,
nonstop, and not marked unstable via command line.  I.e. use the same
criteria as tweaking the clocksource rating so that TSC is preferred over
kvmclock.  Per the below comment from native_sched_clock(), sched_clock
is more tolerant of slop than clocksource; using TSC for clocksource but
not sched_clock makes little to no sense, especially now that KVM CoCo
guests with a trusted TSC use TSC, not kvmclock.

        /*
         * Fall back to jiffies if there's no TSC available:
         * ( But note that we still use it if the TSC is marked
         *   unstable. We do this because unlike Time Of Day,
         *   the scheduler clock tolerates small errors and it's
         *   very important for it to be as fast as the platform
         *   can achieve it. )
         */

The only advantage of using kvmclock is that doing so allows for early
and common detection of PVCLOCK_GUEST_STOPPED, but that code has been
broken for over two years with nary a complaint, i.e. it can't be
_that_ valuable.  And as above, certain types of KVM guests are losing
the functionality regardless, i.e. acknowledging PVCLOCK_GUEST_STOPPED
needs to be decoupled from sched_clock() no matter what.

Link: https://lore.kernel.org/all/Z4hDK27OV7wK572A@google.com
Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kernel/kvmclock.c | 3 ++-
 1 file changed, 2 insertions(+), 1 deletion(-)

diff --git a/arch/x86/kernel/kvmclock.c b/arch/x86/kernel/kvmclock.c
index 1336c24f59cf..cd65ad328637 100644
--- a/arch/x86/kernel/kvmclock.c
+++ b/arch/x86/kernel/kvmclock.c
@@ -374,7 +374,6 @@ void __init kvmclock_init(bool prefer_tsc)
 			 PVCLOCK_TSC_STABLE_BIT;
 	}
 
-	kvm_sched_clock_init(stable);
 
 	if (!x86_init.hyper.get_tsc_khz)
 		x86_init.hyper.get_tsc_khz = kvmclock_get_tsc_khz;
@@ -394,6 +393,8 @@ void __init kvmclock_init(bool prefer_tsc)
 	 */
 	if (prefer_tsc)
 		kvm_clock.rating = 299;
+	else
+		kvm_sched_clock_init(stable);
 
 	clocksource_register_hz(&kvm_clock, NSEC_PER_SEC);
 	pv_info.name = "KVM";

---

## [47] Sean Christopherson — 2026-05-29
*Subject: [PATCH v4 46/47] x86/kvmclock: Plumb in AP-online and BSP-resume to
 kvmlock, for documentation*

Invoke kvmclock_cpu_action() with AP_ONLINE and BSP_RESUME, even though
kvmclock doesn't need to do anything in either case, so that the asymmetry
of kvmclock is a detail buried in kvmclock, and to explicitly document
that doing nothing during those phases is intentional and correct.

For all intents and purposes, no functional change intended.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/kvm_para.h |  2 ++
 arch/x86/kernel/kvm.c           | 22 +++++++++++++-------
 arch/x86/kernel/kvmclock.c      | 37 ++++++++++++++++++++++++++-------
 3 files changed, 45 insertions(+), 16 deletions(-)

diff --git a/arch/x86/include/asm/kvm_para.h b/arch/x86/include/asm/kvm_para.h
index 08686ff19caa..763ed017738a 100644
--- a/arch/x86/include/asm/kvm_para.h
+++ b/arch/x86/include/asm/kvm_para.h
@@ -120,6 +120,8 @@ static inline long kvm_sev_hypercall3(unsigned int nr, unsigned long p1,
 #ifdef CONFIG_KVM_GUEST
 enum kvm_guest_cpu_action {
 	KVM_GUEST_BSP_SUSPEND,
+	KVM_GUEST_BSP_RESUME,
+	KVM_GUEST_AP_ONLINE,
 	KVM_GUEST_AP_OFFLINE,
 	KVM_GUEST_SHUTDOWN,
 };
diff --git a/arch/x86/kernel/kvm.c b/arch/x86/kernel/kvm.c
index fd1c417b4f9b..2ed4bf13e3ed 100644
--- a/arch/x86/kernel/kvm.c
+++ b/arch/x86/kernel/kvm.c
@@ -474,18 +474,24 @@ static void kvm_guest_cpu_offline(enum kvm_guest_cpu_action action)
 	kvmclock_cpu_action(action);
 }
 
+static void __kvm_cpu_online(unsigned int cpu, enum kvm_guest_cpu_action action)
+{
+	unsigned long flags;
+
+	local_irq_save(flags);
+	kvmclock_cpu_action(action);
+	kvm_guest_cpu_init();
+	local_irq_restore(flags);
+}
+
+#ifdef CONFIG_SMP
+
 static int kvm_cpu_online(unsigned int cpu)
 {
-	unsigned long flags;
-
-	local_irq_save(flags);
-	kvm_guest_cpu_init();
-	local_irq_restore(flags);
+	__kvm_cpu_online(cpu, KVM_GUEST_AP_ONLINE);
 	return 0;
 }
 
-#ifdef CONFIG_SMP
-
 static DEFINE_PER_CPU(cpumask_var_t, __pv_cpu_mask);
 
 static bool pv_tlb_flush_supported(void)
@@ -750,7 +756,7 @@ static int kvm_suspend(void *data)
 
 static void kvm_resume(void *data)
 {
-	kvm_cpu_online(raw_smp_processor_id());
+	__kvm_cpu_online(raw_smp_processor_id(), KVM_GUEST_BSP_RESUME);
 
 #ifdef CONFIG_ARCH_CPUIDLE_HALTPOLL
 	if (kvm_para_has_feature(KVM_FEATURE_POLL_CONTROL) && has_guest_poll)
diff --git a/arch/x86/kernel/kvmclock.c b/arch/x86/kernel/kvmclock.c
index cd65ad328637..d122912b8856 100644
--- a/arch/x86/kernel/kvmclock.c
+++ b/arch/x86/kernel/kvmclock.c
@@ -129,7 +129,7 @@ static void kvm_save_sched_clock_state(void)
 #ifdef CONFIG_SMP
 static void kvm_setup_secondary_clock(void)
 {
-	kvm_register_clock("secondary cpu clock");
+	kvm_register_clock("secondary cpu, startup");
 }
 #endif
 
@@ -153,13 +153,34 @@ static void kvmclock_resume(struct clocksource *cs)
 
 void kvmclock_cpu_action(enum kvm_guest_cpu_action action)
 {
-	/*
-	 * Don't disable kvmclock on the BSP during suspend.  If kvmclock is
-	 * being used for sched_clock, then it needs to be kept alive until the
-	 * last minute, and restored as quickly as possible after resume.
-	 */
-	if (action != KVM_GUEST_BSP_SUSPEND)
+	switch (action) {
+		/*
+		 * The BSP's clock is managed via clocksource suspend/resume,
+		 * to ensure it's enabled/disabled when timekeeping needs it
+		 * to be, e.g. before reading wallclock (which uses kvmclock).
+		 */
+	case KVM_GUEST_BSP_SUSPEND:
+	case KVM_GUEST_BSP_RESUME:
+		break;
+	case KVM_GUEST_AP_ONLINE:
+		/*
+		 * Secondary CPUs use a dedicated hook to enable kvmclock early
+		 * during bringup, there's nothing to be done during CPU online
+		 * (which runs at CPUHP_AP_ONLINE_DYN).  When kvmclock is being
+		 * used as sched_clock, kvmclock must be enabled *very* early,
+		 * and even when kvmclock is "only" being used for the main
+		 * clocksource, it still needs to be enabled long before the
+		 * dynamic CPUHP calls are made.
+		 */
+		break;
+	case KVM_GUEST_AP_OFFLINE:
+	case KVM_GUEST_SHUTDOWN:
 		kvmclock_disable();
+		break;
+	default:
+		WARN_ON_ONCE(1);
+		break;
+	}
 }
 
 /*
@@ -360,7 +381,7 @@ void __init kvmclock_init(bool prefer_tsc)
 		msr_kvm_system_time, msr_kvm_wall_clock);
 
 	this_cpu_write(hv_clock_per_cpu, &hv_clock_boot[0]);
-	kvm_register_clock("primary cpu clock");
+	kvm_register_clock("primary cpu, online");
 	pvclock_set_pvti_cpu0_va(hv_clock_boot);
 
 	if (kvm_para_has_feature(KVM_FEATURE_CLOCKSOURCE_STABLE_BIT)) {

---

## [48] Sean Christopherson — 2026-05-29
*Subject: [PATCH v4 47/47] x86/paravirt: Move using_native_sched_clock() stub
 into timer.h*

Now that timer.h ended up with CONFIG_PARAVIRT #ifdeffery anyways, move the
PARAVIRT=n using_native_sched_clock() stub into timer.h as a "free"
optimization.

No functional change intended.

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/timer.h | 6 ++++--
 arch/x86/kernel/tsc.c        | 2 --
 2 files changed, 4 insertions(+), 4 deletions(-)

diff --git a/arch/x86/include/asm/timer.h b/arch/x86/include/asm/timer.h
index ca5c95d48c03..a52388af6055 100644
--- a/arch/x86/include/asm/timer.h
+++ b/arch/x86/include/asm/timer.h
@@ -11,9 +11,9 @@ extern void recalibrate_cpu_khz(void);
 
 extern int no_timer_check;
 
-extern bool using_native_sched_clock(void);
-
 #ifdef CONFIG_PARAVIRT
+extern bool using_native_sched_clock(void);
+
 int __init __paravirt_set_sched_clock(u64 (*func)(void), bool stable,
 				      void (*save)(void), void (*restore)(void));
 
@@ -23,6 +23,8 @@ static __always_inline void paravirt_set_sched_clock(u64 (*func)(void),
 {
 	(void)__paravirt_set_sched_clock(func, true, save, restore);
 }
+#else
+static inline bool using_native_sched_clock(void) { return true; }
 #endif
 
 /*
diff --git a/arch/x86/kernel/tsc.c b/arch/x86/kernel/tsc.c
index 036916953f4a..159d7d060204 100644
--- a/arch/x86/kernel/tsc.c
+++ b/arch/x86/kernel/tsc.c
@@ -302,8 +302,6 @@ int __init __paravirt_set_sched_clock(u64 (*func)(void), bool stable,
 }
 #else
 u64 sched_clock_noinstr(void) __attribute__((alias("native_sched_clock")));
-
-bool using_native_sched_clock(void) { return true; }
 #endif
 
 notrace u64 sched_clock(void)

---

## [49] Sean Christopherson — 2026-05-29
*Subject: Re: [PATCH v4 00/47] x86: Try to wrangle PV clocks vs. TSC*

On Fri, May 29, 2026, Sean Christopherson wrote:
> Well, the number of patches in the series is going in the wrong direction,
> but I'm much happier with this version, which eschews the x86_platform

FYI, our internal mail server flamed out after sending patch 26 in the initial
go.  I'm pretty sure I managed to get the rest sent without screwing up the
threading.  Holler if something is wonky and I'll RESEND the whole pile if necessary.

---

## [50] Jürgen Groß — 2026-05-29
*Subject: Re: [PATCH v4 00/47] x86: Try to wrangle PV clocks vs. TSC*

On 29.05.26 17:10, Sean Christopherson wrote:
> On Fri, May 29, 2026, Sean Christopherson wrote:
>> Well, the number of patches in the series is going in the wrong direction,

Looks fine on my side.


Juergen

---

## [51] Borislav Petkov — 2026-05-29
*Subject: Re: [PATCH v4 01/47] x86/tsc: Never re-calibrate TSC frequency if
 its exact timing is known*

On Fri, May 29, 2026 at 07:43:48AM -0700, Sean Christopherson wrote:
> Don't re-calibrate the TSC frequency if the TSC is known to run at a fixed
> frequency.  In practice, this is likely one big nop, as re-calibration is

Why do we care?

So what if it recalibrates once on UP?

Look where it is called - all old rust which no one uses anymore.

> Signed-off-by: Sean Christopherson <seanjc@google.com>
> ---

cpu_feature_enabled() everywhere please.

---

## [52] David Woodhouse — 2026-06-01
*Subject: Re: [PATCH v4 1/47] x86/tsc: Never re-calibrate TSC frequency if
 its exact timing is known*

On Fri, 29 May 2026 07:43:48 -0700, Sean Christopherson wrote:
> Don't re-calibrate the TSC frequency if the TSC is known to run at a fixed
> frequency.  In practice, this is likely one big nop, as re-calibration is

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>

---

## [53] David Woodhouse — 2026-06-01
*Subject: Re: [PATCH v4 8/47] x86/tsc: Add dedicated hypervisor hooks for
 getting known TSC/CPU frequencies*

On Fri, 29 May 2026 07:43:55 -0700, Sean Christopherson wrote:
> Add dedicated hypervisor hooks for getting known TSC/CPU frequencies
> instead of overriding seemingly generic platform hooks, and explicitly

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>

---

## [54] David Woodhouse — 2026-06-01
*Subject: Re: [PATCH v4 11/47] x86/tsc: Kill off
 x86_platform_ops.calibrate_{cpu,tsc}() hooks*

On Fri, 29 May 2026 07:43:58 -0700, Sean Christopherson wrote:
> Now that getting the CPU and/or TSC frequencies from the hypervisor uses
> dedicated hooks, drop x86_platform_ops.calibrate_{cpu,tsc}() and instead

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>

---

## [55] David Woodhouse — 2026-06-01
*Subject: Re: [PATCH v4 13/47] x86/tsc: Fold native_calibrate_cpu() into
 recalibrate_cpu_khz()*

On Fri, 29 May 2026 07:44:00 -0700, Sean Christopherson wrote:
> Fold the guts of native_calibrate_cpu() into its sole remaining caller,
> recalibrate_cpu_khz() to eliminate the extra SMP=n #ifdef, and so that it's

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>

---

## [56] David Woodhouse — 2026-06-01
*Subject: Re: [PATCH v4 12/47] x86/tsc: Rename
 pit_hpet_ptimer_calibrate_cpu() => native_calibrate_cpu_late()*

On Fri, 29 May 2026 07:43:59 -0700, Sean Christopherson wrote:
> Rename the late CPU calibration routine so that its relationship to the
> early routine is more obvious and intuitive.

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>

---

## [57] David Woodhouse — 2026-06-01
*Subject: Re: [PATCH v4 14/47] x86/kvmclock: Rename kvm_get_tsc_khz() to
 kvmclock_get_tsc_khz()*

On Fri, 29 May 2026 07:44:01 -0700, Sean Christopherson wrote:
> Rename kvm_get_tsc_khz() to kvmclock_get_tsc_khz() in anticipation of
> adding support for getting TSC info from PV CPUID, i.e. in a KVM specific

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>

---

## [58] David Woodhouse — 2026-06-01
*Subject: Re: [PATCH v4 31/47] x86/vmware: NOP-ify save/restore hooks when
 using VMware's sched_clock*

On Fri, 29 May 2026 08:07:52 -0700, Sean Christopherson wrote:
> NOP-ify the sched_clock save/restore hooks when using VMware's version of
> sched_clock.  This will allow extending paravirt_set_sched_clock() to set

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>

---

## [59] David Woodhouse — 2026-06-01
*Subject: Re: [PATCH v4 30/47] x86/xen/time: NOP-ify x86_platform's
 sched_clock save/restore hooks*

On Fri, 29 May 2026 08:07:41 -0700, Sean Christopherson wrote:
> NOP-ify the x86_platform sched_clock save/restore hooks when setting up
> Xen's PV clock to make it somewhat obvious the hooks aren't used when

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>

---

## [60] David Woodhouse — 2026-06-01
*Subject: Re: [PATCH v4 46/47] x86/kvmclock: Plumb in AP-online and
 BSP-resume to kvmlock, for documentation*

On Fri, 29 May 2026 08:08:33 -0700, Sean Christopherson wrote:
> Invoke kvmclock_cpu_action() with AP_ONLINE and BSP_RESUME, even though
> kvmclock doesn't need to do anything in either case, so that the asymmetry

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>

---

## [61] Borislav Petkov — 2026-06-01
*Subject: Re: [PATCH v4 02/47] x86/tsc: Add a standalone helpers for getting
 TSC info from CPUID.0x15*

On Fri, May 29, 2026 at 07:43:49AM -0700, Sean Christopherson wrote:
> +static int cpuid_get_tsc_info(struct cpuid_tsc_info *info)
> +{

Let's not clear this unnecessarily...

> +
> +	if (boot_cpu_data.cpuid_level < CPUID_LEAF_TSC)

... just to return here...

> +
> +	/* CPUID 15H TSC/Crystal ratio, plus optionally Crystal Hz */

... or here.

We wanna clear it here, when we'll return success.

> +
> +	/*

	Note: some CPUs...

> +	 * crystal frequency.  The multiplier information is still useful for
> +	 * such CPUs, as the crystal frequency can be gleaned from CPUID.0x16.

Unused here. Add it with its first user pls.

---

## [62] Kiryl Shutsemau — 2026-06-03
*Subject: Re: [PATCH v4 07/47] x86/tdx: Force TSC frequency with CPUID-based
 info provided by the TDX-Module*

On Fri, May 29, 2026 at 07:43:54AM -0700, Sean Christopherson wrote:
> When running as a TDX guest, explicitly set the TSC frequency to a known
> value, using CPUID-based information, instead of potentially relying on a

Right. EBX is configurable by TD_PARAMS.TSC_FREQUENCY at TD build. The
rest is fixed.

> To maintain backwards compatibility with TDX guest kernels that use native
> calibration, and because it's the least awful option, retain

Agreed.

> Deliberately leave CPU frequency calibration as is, since the TDX-Module
> doesn't provide any guarantees with respect to CPUID.0x16.

It is fixed to zeros. Sounds like a guarantee to me :P

> Signed-off-by: Sean Christopherson <seanjc@google.com>

Looks sane to me. Including your reasoning about tsc_early_khz= in reply
to Sashiko.

Reviewed-by: Kiryl Shutsemau (Meta) <kas@kernel.org>

---

## [63] Thomas Gleixner — 2026-06-05
*Subject: Re: [PATCH v4 01/47] x86/tsc: Never re-calibrate TSC frequency if
 its exact timing is known*

On Fri, May 29 2026 at 07:43, Sean Christopherson wrote:
> Don't re-calibrate the TSC frequency if the TSC is known to run at a fixed
> frequency.

That's misleading because fixed frequency means that the frequency does
not change, i.e. X86_FEATURE_CONSTANT_TSC is set. But
X86_FEATURE_CONSTANT_TSC does not imply that the frequency can be read
from CPUID/MSRs.

> In practice, this is likely one big nop, as re-calibration is
> used only for SMP=n kernels, and only for hardware that is 20+ years old,

recalibrate_cpu_khz() is only invoked from Intel P4 and AMD K7 CPU
frequency drivers, which means that's absolutely not interesting and
neither X86_FEATURE_CONSTANT_TSC nor X86_FEATURE_TSC_KNOWN_FREQ can be
set on those systems.

IOW, this patch is pointless voodoo ware.

Thanks,

        tglx

---

## [64] Thomas Gleixner — 2026-06-05
*Subject: Re: [PATCH v4 02/47] x86/tsc: Add a standalone helpers for getting
 TSC info from CPUID.0x15*

On Fri, May 29 2026 at 07:43, Sean Christopherson wrote:
>  		cpuid(CPUID_LEAF_FREQ, &eax_base_mhz, &ebx, &ecx, &edx);
> -		crystal_khz = eax_base_mhz * 1000 *

Please get rid of this ugly line break. You have 100 characters.

---

## [65] Sean Christopherson — 2026-06-05
*Subject: Re: [PATCH v4 01/47] x86/tsc: Never re-calibrate TSC frequency if its
 exact timing is known*

On Fri, Jun 05, 2026, Thomas Gleixner wrote:
> On Fri, May 29 2026 at 07:43, Sean Christopherson wrote:
> > Don't re-calibrate the TSC frequency if the TSC is known to run at a fixed

Sorry, "if the TSC runs at a known, fixed frequency" would be a better way to
phrase this.

> > In practice, this is likely one big nop, as re-calibration is
> > used only for SMP=n kernels, and only for hardware that is 20+ years old,

It _shouldn't_ be set on those systems, but in the world of virtualization it's
not completely impossible.

> IOW, this patch is pointless voodoo ware.

Would y'all be opposed to adding a WARN?  I don't actually care about P4 or K7
CPUs, but without any reference to X86_FEATURE_TSC_KNOWN_FREQ in
recalibrate_cpu_khz(), the code _looks_ wrong, and so is very confusing for
readers that don't already know that in practice, it's limited to ancient CPUs.

In other words, the point is to document expectations and mutual exclusion, not
to "fix" anything.

---

## [66] Thomas Gleixner — 2026-06-05
*Subject: Re: [PATCH v4 01/47] x86/tsc: Never re-calibrate TSC frequency if
 its exact timing is known*

On Fri, Jun 05 2026 at 11:04, Sean Christopherson wrote:
> On Fri, Jun 05, 2026, Thomas Gleixner wrote:
>> On Fri, May 29 2026 at 07:43, Sean Christopherson wrote:

Fair enough.

So yes, having a check there for actually X86_FEATURE_CONSTANT_TSC
(X86_FEATURE_CONSTANT_TSC is not interesting) and emitting a warning and
returning early is the right thing to do there.

But we also should have a check in the TSC init code somewhere which
validates that X86_FEATURE_CONSTANT_TSC is set when
X86_FEATURE_TSC_KNOWN_FREQ is set. X86_FEATURE_TSC_KNOWN_FREQ is useless
w/o X86_FEATURE_CONSTANT_TSC.

Thanks,

        tglx

---
