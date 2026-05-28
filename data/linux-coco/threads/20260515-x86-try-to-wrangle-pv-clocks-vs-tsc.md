---
title: 'x86: Try to wrangle PV clocks vs. TSC'
date: 2026-05-15
last_reply: 2026-05-27
message_count: 111
participants: ['Sean Christopherson', 'Paolo Bonzini', 'Woodhouse, David', 'David Woodhouse', 'Dongli Zhang', 'Peter Zijlstra', 'Wei Liu']
---

## [1] Sean Christopherson — 2026-05-15

Dave/Thomas/Peter/Boris, what's the going rate for bribes to take something
like this through the tip tree?  

The bulk of the changes are in kvmclock and TSC, but pretty much every
hypervisor's guest-side code gets touched at some point.  I am reaonsably
confident in the correctness of the KVM changes.  Michael tested Hyper-V in
v2, and while there were conflicts when rebasing, they were largely
superficial (and I've just jinxed myself).  For all other hypervisors, assume
the code is compile-tested only, but those changes are all quite small and
straightforward.

The only changes that are questionable/contentious are the last two patches,
which have KVM-as-a-guest use CPUID 0x16 to get the CPU frequency, even on
AMD (that's the dubious part).  I very deliberately put them last, so that
they can be dropped at will (I don't care terribly if those patches land).
To merge them, I would want explicit Acks from Paolo and David W.

So, except for the last two patches, to get the stuff I really care about
landed, I think/hope it's just the TSC and guest-side CoCo changes that need
reviews/acks?

The primary goal of this series is (or at least was, when I started) to
fix flaws with SNP and TDX guests where a PV clock provided by the untrusted
hypervisor is used instead of the secure/trusted TSC that is controlled by
trusted firmware.

The secondary goal is to draft off of the SNP and TDX changes to slightly
modernize running under KVM.  Currently, KVM guests will use TSC for
clocksource, but not sched_clock.  And they ignore Intel's CPUID-based TSC
and CPU frequency enumeration, even when using the TSC instead of kvmclock.
And if the host provides the core crystal frequency in CPUID.0x15, then KVM
guests can use that for the APIC timer period instead of manually calibrating
the frequency.

The tertiary goal is to clean up all of the PV clock code to deduplicate logic
across hypervisors, and to hopefully make it all easier to maintain going
forward.

Lots more background on the SNP/TDX motiviation:
https://lore.kernel.org/all/20250106124633.1418972-13-nikunj@amd.com

Note, I deliberately omitted:

  jailhouse-dev@googlegroups.com

from the To/Cc, as those emails bounced on v1, AFAICT nothing has changed, and
I have zero desire to get 41 emails telling me an email couldn't be delivered.

v3:
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

David Woodhouse (2):
  KVM: x86: Officially define CPUID 0x40000010 as PV Timing Info (TSC
    and Bus)
  x86/kvmclock: Obtain TSC frequency from CPUID if present

Sean Christopherson (39):
  x86/tsc: Add a standalone helpers for getting TSC info from CPUID.0x15
  x86/tsc: Add helper to register CPU and TSC freq calibration routines
  x86/sev: Mark TSC as reliable when configuring Secure TSC
  x86/sev: Move check for SNP Secure TSC support to tsc_early_init()
  x86/tdx: Override PV calibration routines with CPUID-based calibration
  x86/acrn: Mark TSC frequency as known when using ACRN for calibration
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
  x86/xen/time: Nullify x86_platform's sched_clock save/restore hooks
  x86/vmware: Nullify save/restore hooks when using VMware's sched_clock
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
  x86/kvmclock: Enable kvmclock on APs during onlining if kvmclock isn't
    sched_clock
  x86/paravirt: Mark __paravirt_set_sched_clock() as __init
  x86/paravirt: Plumb a return code into __paravirt_set_sched_clock()
  x86/paravirt: Don't use a PV sched_clock in CoCo guests with trusted
    TSC
  x86/tsc: Pass KNOWN_FREQ and RELIABLE as params to registration
  x86/tsc: Rejects attempts to override TSC calibration with lesser
    routine
  x86/kvmclock: Mark TSC as reliable when it's constant and nonstop
  x86/kvmclock: Get local APIC bus frequency from PV CPUID Timing Info
  x86/kvmclock: Use TSC for sched_clock if it's constant and non-stop
  x86/paravirt: kvmclock: Setup kvmclock early iff it's sched_clock
  x86/paravirt: Move using_native_sched_clock() stub into timer.h
  x86/tsc: Add standalone helper for getting CPU frequency from CPUID
  x86/kvmclock: Get CPU base frequency from CPUID when it's available

 Documentation/virt/kvm/x86/cpuid.rst |  12 ++
 arch/x86/coco/sev/core.c             |   9 +-
 arch/x86/coco/tdx/tdx.c              |  27 ++-
 arch/x86/include/asm/kvm_para.h      |  12 +-
 arch/x86/include/asm/tdx.h           |   2 +
 arch/x86/include/asm/timer.h         |  18 +-
 arch/x86/include/asm/tsc.h           |  20 +++
 arch/x86/include/asm/x86_init.h      |   2 -
 arch/x86/include/uapi/asm/kvm_para.h |  11 ++
 arch/x86/kernel/cpu/acrn.c           |   5 +-
 arch/x86/kernel/cpu/mshyperv.c       |  69 +-------
 arch/x86/kernel/cpu/vmware.c         |  11 +-
 arch/x86/kernel/jailhouse.c          |   6 +-
 arch/x86/kernel/kvm.c                |  62 +++++--
 arch/x86/kernel/kvmclock.c           | 250 +++++++++++++++++++--------
 arch/x86/kernel/pvclock.c            |   9 +-
 arch/x86/kernel/smpboot.c            |   3 +-
 arch/x86/kernel/tsc.c                | 184 +++++++++++++++-----
 arch/x86/kernel/x86_init.c           |   1 -
 arch/x86/mm/mem_encrypt_amd.c        |   3 -
 arch/x86/xen/time.c                  |  13 +-
 drivers/clocksource/hyperv_timer.c   |  38 ++--
 include/clocksource/hyperv_timer.h   |   2 -
 kernel/time/timekeeping.c            |   9 +-
 24 files changed, 537 insertions(+), 241 deletions(-)


base-commit: 1196e304db58189264bb5953b4e8da7e90cda615

---

## [2] Sean Christopherson — 2026-05-15
*Subject: [PATCH v3 01/41] x86/tsc: Add a standalone helpers for getting TSC
 info from CPUID.0x15*

Extract retrieval of TSC frequency information from CPUID into standalone
helpers so that TDX guest support can reuse the logic.  Provide a version
that includes the multiplier math as TDX does NOT want to use
native_calibrate_tsc()'s fallback logic that derives the TSC frequency
based on CPUID.0x16, when the core crystal frequency isn't known.

Opportunsitically drop native_calibrate_tsc()'s "== 0" and "!= 0" checks
in favor of the kernel's preferred style.

No functional change intended.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/tsc.h |  9 +++++
 arch/x86/kernel/tsc.c      | 67 +++++++++++++++++++++++++-------------
 2 files changed, 53 insertions(+), 23 deletions(-)

diff --git a/arch/x86/include/asm/tsc.h b/arch/x86/include/asm/tsc.h
index 4f7f09f50552..0c57fadc4a39 100644
--- a/arch/x86/include/asm/tsc.h
+++ b/arch/x86/include/asm/tsc.h
@@ -83,6 +83,15 @@ static inline cycles_t get_cycles(void)
 }
 #define get_cycles get_cycles
 
+struct cpuid_tsc_info {
+	unsigned int denominator;
+	unsigned int numerator;
+	unsigned int crystal_khz;
+	unsigned int tsc_khz;
+};
+extern int cpuid_get_tsc_info(struct cpuid_tsc_info *info);
+extern int cpuid_get_tsc_freq(struct cpuid_tsc_info *info);
+
 extern void tsc_early_init(void);
 extern void tsc_init(void);
 extern void mark_tsc_unstable(char *reason);
diff --git a/arch/x86/kernel/tsc.c b/arch/x86/kernel/tsc.c
index c5110eb554bc..f92236f40cbc 100644
--- a/arch/x86/kernel/tsc.c
+++ b/arch/x86/kernel/tsc.c
@@ -658,46 +658,67 @@ static unsigned long quick_pit_calibrate(void)
 	return delta;
 }
 
+int cpuid_get_tsc_info(struct cpuid_tsc_info *info)
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
+int cpuid_get_tsc_freq(struct cpuid_tsc_info *info)
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

## [3] Sean Christopherson — 2026-05-15
*Subject: [PATCH v3 02/41] x86/tsc: Add helper to register CPU and TSC freq
 calibration routines*

Add a helper to register non-native, i.e. PV and CoCo, CPU and TSC
frequency calibration routines.  This will allow consolidating handling
of common TSC properties that are forced by hypervisor (PV routines),
and will also allow adding sanity checks to guard against overriding a
TSC calibration routine with a routine that is less robust/trusted.

Make the CPU calibration routine optional, as Xen (very sanely) doesn't
assume the CPU runs as the same frequency as the TSC.

Wrap the helper in an #ifdef to document that the kernel overrides
the native routines when running as a VM, and to guard against unwanted
usage.  Add a TODO to call out that AMD_MEM_ENCRYPT is a mess and doesn't
depend on HYPERVISOR_GUEST because it gates both guest and host code.

No functional change intended.

Reviewed-by: Michael Kelley <mhklinux@outlook.com>
Tested-by: Michael Kelley <mhklinux@outlook.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/coco/sev/core.c       |  4 ++--
 arch/x86/include/asm/tsc.h     |  4 ++++
 arch/x86/kernel/cpu/acrn.c     |  4 ++--
 arch/x86/kernel/cpu/mshyperv.c |  3 +--
 arch/x86/kernel/cpu/vmware.c   |  4 ++--
 arch/x86/kernel/jailhouse.c    |  4 ++--
 arch/x86/kernel/kvmclock.c     |  4 ++--
 arch/x86/kernel/tsc.c          | 17 +++++++++++++++++
 arch/x86/xen/time.c            |  2 +-
 9 files changed, 33 insertions(+), 13 deletions(-)

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index 7ed3da998489..d27cf8f8b025 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -2048,8 +2048,8 @@ void __init snp_secure_tsc_init(void)
 
 	snp_tsc_freq_khz = SNP_SCALE_TSC_FREQ(tsc_freq_mhz * 1000, secrets->tsc_factor);
 
-	x86_platform.calibrate_cpu = securetsc_get_tsc_khz;
-	x86_platform.calibrate_tsc = securetsc_get_tsc_khz;
+	tsc_register_calibration_routines(securetsc_get_tsc_khz,
+					  securetsc_get_tsc_khz);
 
 	early_memunmap(mem, PAGE_SIZE);
 }
diff --git a/arch/x86/include/asm/tsc.h b/arch/x86/include/asm/tsc.h
index 0c57fadc4a39..bae709f5f44d 100644
--- a/arch/x86/include/asm/tsc.h
+++ b/arch/x86/include/asm/tsc.h
@@ -94,6 +94,10 @@ extern int cpuid_get_tsc_freq(struct cpuid_tsc_info *info);
 
 extern void tsc_early_init(void);
 extern void tsc_init(void);
+#if defined(CONFIG_HYPERVISOR_GUEST) || defined(CONFIG_AMD_MEM_ENCRYPT)
+extern void tsc_register_calibration_routines(unsigned long (*calibrate_tsc)(void),
+					      unsigned long (*calibrate_cpu)(void));
+#endif
 extern void mark_tsc_unstable(char *reason);
 extern int unsynchronized_tsc(void);
 extern int check_tsc_unstable(void);
diff --git a/arch/x86/kernel/cpu/acrn.c b/arch/x86/kernel/cpu/acrn.c
index 2c5b51aad91a..c1506cb87d8c 100644
--- a/arch/x86/kernel/cpu/acrn.c
+++ b/arch/x86/kernel/cpu/acrn.c
@@ -29,8 +29,8 @@ static void __init acrn_init_platform(void)
 	/* Install system interrupt handler for ACRN hypervisor callback */
 	sysvec_install(HYPERVISOR_CALLBACK_VECTOR, sysvec_acrn_hv_callback);
 
-	x86_platform.calibrate_tsc = acrn_get_tsc_khz;
-	x86_platform.calibrate_cpu = acrn_get_tsc_khz;
+	tsc_register_calibration_routines(acrn_get_tsc_khz,
+					  acrn_get_tsc_khz);
 }
 
 static bool acrn_x2apic_available(void)
diff --git a/arch/x86/kernel/cpu/mshyperv.c b/arch/x86/kernel/cpu/mshyperv.c
index 640e6b223c2d..8d2401be420c 100644
--- a/arch/x86/kernel/cpu/mshyperv.c
+++ b/arch/x86/kernel/cpu/mshyperv.c
@@ -573,8 +573,7 @@ static void __init ms_hyperv_init_platform(void)
 
 	if (ms_hyperv.features & HV_ACCESS_FREQUENCY_MSRS &&
 	    ms_hyperv.misc_features & HV_FEATURE_FREQUENCY_MSRS_AVAILABLE) {
-		x86_platform.calibrate_tsc = hv_get_tsc_khz;
-		x86_platform.calibrate_cpu = hv_get_tsc_khz;
+		tsc_register_calibration_routines(hv_get_tsc_khz, hv_get_tsc_khz);
 		setup_force_cpu_cap(X86_FEATURE_TSC_KNOWN_FREQ);
 	}
 
diff --git a/arch/x86/kernel/cpu/vmware.c b/arch/x86/kernel/cpu/vmware.c
index 34b73573b108..b88d9ca01202 100644
--- a/arch/x86/kernel/cpu/vmware.c
+++ b/arch/x86/kernel/cpu/vmware.c
@@ -419,8 +419,8 @@ static void __init vmware_platform_setup(void)
 		}
 
 		vmware_tsc_khz = tsc_khz;
-		x86_platform.calibrate_tsc = vmware_get_tsc_khz;
-		x86_platform.calibrate_cpu = vmware_get_tsc_khz;
+		tsc_register_calibration_routines(vmware_get_tsc_khz,
+						  vmware_get_tsc_khz);
 
 #ifdef CONFIG_X86_LOCAL_APIC
 		/* Skip lapic calibration since we know the bus frequency. */
diff --git a/arch/x86/kernel/jailhouse.c b/arch/x86/kernel/jailhouse.c
index f58ce9220e0f..db8f31fdb480 100644
--- a/arch/x86/kernel/jailhouse.c
+++ b/arch/x86/kernel/jailhouse.c
@@ -210,8 +210,6 @@ static void __init jailhouse_init_platform(void)
 	x86_init.mpparse.parse_smp_cfg		= jailhouse_parse_smp_config;
 	x86_init.pci.arch_init			= jailhouse_pci_arch_init;
 
-	x86_platform.calibrate_cpu		= jailhouse_get_tsc;
-	x86_platform.calibrate_tsc		= jailhouse_get_tsc;
 	x86_platform.get_wallclock		= jailhouse_get_wallclock;
 	x86_platform.legacy.rtc			= 0;
 	x86_platform.legacy.warm_reset		= 0;
@@ -221,6 +219,8 @@ static void __init jailhouse_init_platform(void)
 
 	machine_ops.emergency_restart		= jailhouse_no_restart;
 
+	tsc_register_calibration_routines(jailhouse_get_tsc, jailhouse_get_tsc);
+
 	while (pa_data) {
 		mapping = early_memremap(pa_data, sizeof(header));
 		memcpy(&header, mapping, sizeof(header));
diff --git a/arch/x86/kernel/kvmclock.c b/arch/x86/kernel/kvmclock.c
index b5991d53fc0e..e9e7394140dd 100644
--- a/arch/x86/kernel/kvmclock.c
+++ b/arch/x86/kernel/kvmclock.c
@@ -321,8 +321,8 @@ void __init kvmclock_init(void)
 	flags = pvclock_read_flags(&hv_clock_boot[0].pvti);
 	kvm_sched_clock_init(flags & PVCLOCK_TSC_STABLE_BIT);
 
-	x86_platform.calibrate_tsc = kvm_get_tsc_khz;
-	x86_platform.calibrate_cpu = kvm_get_tsc_khz;
+	tsc_register_calibration_routines(kvm_get_tsc_khz, kvm_get_tsc_khz);
+
 	x86_platform.get_wallclock = kvm_get_wallclock;
 	x86_platform.set_wallclock = kvm_set_wallclock;
 #ifdef CONFIG_X86_LOCAL_APIC
diff --git a/arch/x86/kernel/tsc.c b/arch/x86/kernel/tsc.c
index f92236f40cbc..7e639c0a94a2 100644
--- a/arch/x86/kernel/tsc.c
+++ b/arch/x86/kernel/tsc.c
@@ -1281,6 +1281,23 @@ static void __init check_system_tsc_reliable(void)
 		tsc_disable_clocksource_watchdog();
 }
 
+/*
+ * TODO: Disentangle AMD_MEM_ENCRYPT and make SEV guest support depend on
+ *	 HYPERVISOR_GUEST.
+ */
+#if defined(CONFIG_HYPERVISOR_GUEST) || defined(CONFIG_AMD_MEM_ENCRYPT)
+void tsc_register_calibration_routines(unsigned long (*calibrate_tsc)(void),
+				       unsigned long (*calibrate_cpu)(void))
+{
+	if (WARN_ON_ONCE(!calibrate_tsc))
+		return;
+
+	x86_platform.calibrate_tsc = calibrate_tsc;
+	if (calibrate_cpu)
+		x86_platform.calibrate_cpu = calibrate_cpu;
+}
+#endif
+
 /*
  * Make an educated guess if the TSC is trustworthy and synchronized
  * over all CPUs.
diff --git a/arch/x86/xen/time.c b/arch/x86/xen/time.c
index d62c14334b35..3d3165eef821 100644
--- a/arch/x86/xen/time.c
+++ b/arch/x86/xen/time.c
@@ -569,7 +569,7 @@ static void __init xen_init_time_common(void)
 	static_call_update(pv_steal_clock, xen_steal_clock);
 	paravirt_set_sched_clock(xen_sched_clock);
 
-	x86_platform.calibrate_tsc = xen_tsc_khz;
+	tsc_register_calibration_routines(xen_tsc_khz, NULL);
 	x86_platform.get_wallclock = xen_get_wallclock;
 }

---

## [4] Sean Christopherson — 2026-05-15
*Subject: [PATCH v3 03/41] x86/sev: Mark TSC as reliable when configuring
 Secure TSC*

Move the code to mark the TSC as reliable from sme_early_init() to
snp_secure_tsc_init().  The only reader of TSC_RELIABLE is the aptly
named check_system_tsc_reliable(), which runs in tsc_init(), i.e.
after snp_secure_tsc_init().

This will allow consolidating the handling of TSC_KNOWN_FREQ and
TSC_RELIABLE when overriding the TSC calibration routine.

Cc: Tom Lendacky <thomas.lendacky@amd.com>
Reviewed-by: Nikunj A Dadhania <nikunj@amd.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/coco/sev/core.c      | 2 ++
 arch/x86/mm/mem_encrypt_amd.c | 3 ---
 2 files changed, 2 insertions(+), 3 deletions(-)

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index d27cf8f8b025..14ced854cd83 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -2041,6 +2041,8 @@ void __init snp_secure_tsc_init(void)
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

## [5] Sean Christopherson — 2026-05-15
*Subject: [PATCH v3 04/41] x86/sev: Move check for SNP Secure TSC support to tsc_early_init()*

Move the check on having a Secure TSC to the common tsc_early_init() so
that it's obvious that having a Secure TSC is conditional, and to prepare
for adding TDX to the mix (blindly initializing *both* SNP and TDX TSC
logic looks especially weird).

No functional change intended.

Cc: Tom Lendacky <thomas.lendacky@amd.com>
Reviewed-by: Nikunj A Dadhania <nikunj@amd.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/coco/sev/core.c | 3 ---
 arch/x86/kernel/tsc.c    | 3 ++-
 2 files changed, 2 insertions(+), 4 deletions(-)

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index 14ced854cd83..39fb50697542 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -2029,9 +2029,6 @@ void __init snp_secure_tsc_init(void)
 	unsigned long tsc_freq_mhz;
 	void *mem;
 
-	if (!cc_platform_has(CC_ATTR_GUEST_SNP_SECURE_TSC))
-		return;
-
 	mem = early_memremap_encrypted(sev_secrets_pa, PAGE_SIZE);
 	if (!mem) {
 		pr_err("Unable to get TSC_FACTOR: failed to map the SNP secrets page.\n");
diff --git a/arch/x86/kernel/tsc.c b/arch/x86/kernel/tsc.c
index 7e639c0a94a2..243999692aea 100644
--- a/arch/x86/kernel/tsc.c
+++ b/arch/x86/kernel/tsc.c
@@ -1559,7 +1559,8 @@ void __init tsc_early_init(void)
 	if (is_early_uv_system())
 		return;
 
-	snp_secure_tsc_init();
+	if (cc_platform_has(CC_ATTR_GUEST_SNP_SECURE_TSC))
+		snp_secure_tsc_init();
 
 	if (!determine_cpu_tsc_frequencies(true))
 		return;

---

## [6] Sean Christopherson — 2026-05-15
*Subject: [PATCH v3 05/41] x86/tdx: Override PV calibration routines with
 CPUID-based calibration*

When running as a TDX guest, explicitly override the TSC frequency
calibration routine with CPUID-based calibration instead of potentially
relying on a hypervisor-controlled PV routine.  For TDX guests, CPUID.0x15
is always emulated by the TDX-Module, i.e. the information from CPUID is
more trustworthy than the information provided by the hypervisor.

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

Deliberately leave the CPU frequency calibration routine as is, since the
TDX-Module doesn't provide any guarantees with respect to CPUID.0x16.

Opportunistically add a comment explaining that CoCo TSC initialization
needs to come after hypervisor specific initialization.

Cc: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/coco/tdx/tdx.c    | 30 +++++++++++++++++++++++++++---
 arch/x86/include/asm/tdx.h |  2 ++
 arch/x86/kernel/tsc.c      |  8 ++++++++
 3 files changed, 37 insertions(+), 3 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 29b6f1ed59ec..26890cea790b 100644
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
@@ -1195,3 +1193,29 @@ void __init tdx_early_init(void)
 
 	tdx_announce();
 }
+
+static unsigned long tdx_get_tsc_khz(void)
+{
+	struct cpuid_tsc_info info;
+
+	if (WARN_ON_ONCE(cpuid_get_tsc_freq(&info)))
+		return 0;
+
+	lapic_timer_period = info.crystal_khz * 1000 / HZ;
+
+	return info.tsc_khz;
+}
+
+void __init tdx_tsc_init(void)
+{
+	/* TSC is the only reliable clock in TDX guest */
+	setup_force_cpu_cap(X86_FEATURE_TSC_RELIABLE);
+	setup_force_cpu_cap(X86_FEATURE_TSC_KNOWN_FREQ);
+
+	/*
+	 * Override the PV calibration routines (if set) with more trustworthy
+	 * CPUID-based calibration.  The TDX module emulates CPUID, whereas any
+	 * PV information is provided by the hypervisor.
+	 */
+	tsc_register_calibration_routines(tdx_get_tsc_khz, NULL);
+}
diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 15eac89b0afb..60deab0ed979 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -57,6 +57,7 @@ struct ve_info {
 #ifdef CONFIG_INTEL_TDX_GUEST
 
 void __init tdx_early_init(void);
+void __init tdx_tsc_init(void);
 
 void tdx_get_ve_info(struct ve_info *ve);
 
@@ -78,6 +79,7 @@ void __init tdx_dump_td_ctls(u64 td_ctls);
 #else
 
 static inline void tdx_early_init(void) { };
+static inline void tdx_tsc_init(void) { }
 static inline void tdx_halt(void) { };
 
 static inline bool tdx_early_handle_ve(struct pt_regs *regs) { return false; }
diff --git a/arch/x86/kernel/tsc.c b/arch/x86/kernel/tsc.c
index 243999692aea..e00f53e3dd8d 100644
--- a/arch/x86/kernel/tsc.c
+++ b/arch/x86/kernel/tsc.c
@@ -34,6 +34,7 @@
 #include <asm/topology.h>
 #include <asm/uv/uv.h>
 #include <asm/sev.h>
+#include <asm/tdx.h>
 
 unsigned int __read_mostly cpu_khz;	/* TSC clocks / usec, not used here */
 EXPORT_SYMBOL(cpu_khz);
@@ -1559,8 +1560,15 @@ void __init tsc_early_init(void)
 	if (is_early_uv_system())
 		return;
 
+	/*
+	 * Do CoCo specific "secure" TSC initialization *after* hypervisor
+	 * platform initialization so that the secure variant can override the
+	 * hypervisor's PV calibration routine with a more trusted method.
+	 */
 	if (cc_platform_has(CC_ATTR_GUEST_SNP_SECURE_TSC))
 		snp_secure_tsc_init();
+	else if (boot_cpu_has(X86_FEATURE_TDX_GUEST))
+		tdx_tsc_init();
 
 	if (!determine_cpu_tsc_frequencies(true))
 		return;

---

## [7] Sean Christopherson — 2026-05-15
*Subject: [PATCH v3 06/41] x86/acrn: Mark TSC frequency as known when using
 ACRN for calibration*

Mark the TSC frequency as known when using ACRN's PV CPUID information.
Per commit 81a71f51b89e ("x86/acrn: Set up timekeeping") and common sense,
the TSC freq is explicitly provided by the hypervisor.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kernel/cpu/acrn.c | 1 +
 1 file changed, 1 insertion(+)

diff --git a/arch/x86/kernel/cpu/acrn.c b/arch/x86/kernel/cpu/acrn.c
index c1506cb87d8c..2da3de4d470e 100644
--- a/arch/x86/kernel/cpu/acrn.c
+++ b/arch/x86/kernel/cpu/acrn.c
@@ -29,6 +29,7 @@ static void __init acrn_init_platform(void)
 	/* Install system interrupt handler for ACRN hypervisor callback */
 	sysvec_install(HYPERVISOR_CALLBACK_VECTOR, sysvec_acrn_hv_callback);
 
+	setup_force_cpu_cap(X86_FEATURE_TSC_KNOWN_FREQ);
 	tsc_register_calibration_routines(acrn_get_tsc_khz,
 					  acrn_get_tsc_khz);
 }

---

## [8] Sean Christopherson — 2026-05-15
*Subject: [PATCH v3 07/41] clocksource: hyper-v: Register sched_clock
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
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kernel/cpu/mshyperv.c     | 58 ------------------------------
 drivers/clocksource/hyperv_timer.c | 50 ++++++++++++++++++++++++++
 2 files changed, 50 insertions(+), 58 deletions(-)

diff --git a/arch/x86/kernel/cpu/mshyperv.c b/arch/x86/kernel/cpu/mshyperv.c
index 8d2401be420c..5ca139ae50b4 100644
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

## [9] Sean Christopherson — 2026-05-15
*Subject: [PATCH v3 08/41] clocksource: hyper-v: Drop wrappers to sched_clock
 save/restore helpers*

Now that all of the Hyper-V reference counter sched_clock code is located
in a single file, drop the superfluous wrappers for the save/restore flows.

No functional change intended.

Reviewed-by: Michael Kelley <mhklinux@outlook.com>
Tested-by: Michael Kelley <mhklinux@outlook.com>
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

## [10] Sean Christopherson — 2026-05-15
*Subject: [PATCH v3 09/41] clocksource: hyper-v: Don't save/restore TSC offset
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

## [11] Sean Christopherson — 2026-05-15
*Subject: [PATCH v3 10/41] x86/kvmclock: Setup kvmclock for secondary CPUs iff CONFIG_SMP=y*

Gate kvmclock's secondary CPU code on CONFIG_SMP, not CONFIG_X86_LOCAL_APIC.
Originally, kvmclock piggybacked PV APIC ops to setup secondary CPUs.
When that wart was fixed by commit df156f90a0f9 ("x86: Introduce
x86_cpuinit.early_percpu_clock_init hook"), the dependency on a local APIC
got carried forward unnecessarily.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kernel/kvmclock.c | 4 ++--
 1 file changed, 2 insertions(+), 2 deletions(-)

diff --git a/arch/x86/kernel/kvmclock.c b/arch/x86/kernel/kvmclock.c
index e9e7394140dd..df95516a9d89 100644
--- a/arch/x86/kernel/kvmclock.c
+++ b/arch/x86/kernel/kvmclock.c
@@ -187,7 +187,7 @@ static void kvm_restore_sched_clock_state(void)
 	kvm_register_clock("primary cpu clock, resume");
 }
 
-#ifdef CONFIG_X86_LOCAL_APIC
+#ifdef CONFIG_SMP
 static void kvm_setup_secondary_clock(void)
 {
 	kvm_register_clock("secondary cpu clock");
@@ -325,7 +325,7 @@ void __init kvmclock_init(void)
 
 	x86_platform.get_wallclock = kvm_get_wallclock;
 	x86_platform.set_wallclock = kvm_set_wallclock;
-#ifdef CONFIG_X86_LOCAL_APIC
+#ifdef CONFIG_SMP
 	x86_cpuinit.early_percpu_clock_init = kvm_setup_secondary_clock;
 #endif
 	x86_platform.save_sched_clock_state = kvm_save_sched_clock_state;

---

## [12] Sean Christopherson — 2026-05-15
*Subject: [PATCH v3 11/41] x86/kvm: Don't disable kvmclock on BSP in syscore_suspend()*

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
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/kvm_para.h |  8 +++++++-
 arch/x86/kernel/kvm.c           | 15 ++++++++-------
 arch/x86/kernel/kvmclock.c      | 31 +++++++++++++++++++++++++------
 3 files changed, 40 insertions(+), 14 deletions(-)

diff --git a/arch/x86/include/asm/kvm_para.h b/arch/x86/include/asm/kvm_para.h
index 4a47c16e2df8..2adba2aff539 100644
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
 void kvmclock_init(void);
-void kvmclock_disable(void);
+void kvmclock_cpu_action(enum kvm_guest_cpu_action action);
 bool kvm_para_available(void);
 unsigned int kvm_arch_para_features(void);
 unsigned int kvm_arch_para_hints(void);
diff --git a/arch/x86/kernel/kvm.c b/arch/x86/kernel/kvm.c
index 06534e16cfb5..0131bc1cb459 100644
--- a/arch/x86/kernel/kvm.c
+++ b/arch/x86/kernel/kvm.c
@@ -457,7 +457,7 @@ static void __init sev_map_percpu_data(void)
 	}
 }
 
-static void kvm_guest_cpu_offline(bool shutdown)
+static void kvm_guest_cpu_offline(enum kvm_guest_cpu_action action)
 {
 	kvm_disable_steal_time();
 	if (kvm_para_has_feature(KVM_FEATURE_PV_EOI))
@@ -465,9 +465,10 @@ static void kvm_guest_cpu_offline(bool shutdown)
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
@@ -723,7 +724,7 @@ static int kvm_cpu_down_prepare(unsigned int cpu)
 	unsigned long flags;
 
 	local_irq_save(flags);
-	kvm_guest_cpu_offline(false);
+	kvm_guest_cpu_offline(KVM_GUEST_AP_OFFLINE);
 	local_irq_restore(flags);
 	return 0;
 }
@@ -734,7 +735,7 @@ static int kvm_suspend(void *data)
 {
 	u64 val = 0;
 
-	kvm_guest_cpu_offline(false);
+	kvm_guest_cpu_offline(KVM_GUEST_BSP_SUSPEND);
 
 #ifdef CONFIG_ARCH_CPUIDLE_HALTPOLL
 	if (kvm_para_has_feature(KVM_FEATURE_POLL_CONTROL))
@@ -765,7 +766,7 @@ static struct syscore kvm_syscore = {
 
 static void kvm_pv_guest_cpu_reboot(void *unused)
 {
-	kvm_guest_cpu_offline(true);
+	kvm_guest_cpu_offline(KVM_GUEST_SHUTDOWN);
 }
 
 static int kvm_pv_reboot_notify(struct notifier_block *nb,
@@ -789,7 +790,7 @@ static struct notifier_block kvm_pv_reboot_nb = {
 #ifdef CONFIG_CRASH_DUMP
 static void kvm_crash_shutdown(struct pt_regs *regs)
 {
-	kvm_guest_cpu_offline(true);
+	kvm_guest_cpu_offline(KVM_GUEST_SHUTDOWN);
 	native_machine_crash_shutdown(regs);
 }
 #endif
diff --git a/arch/x86/kernel/kvmclock.c b/arch/x86/kernel/kvmclock.c
index df95516a9d89..006e3a13500b 100644
--- a/arch/x86/kernel/kvmclock.c
+++ b/arch/x86/kernel/kvmclock.c
@@ -178,8 +178,22 @@ static void kvm_register_clock(char *txt)
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
@@ -187,6 +201,17 @@ static void kvm_restore_sched_clock_state(void)
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
@@ -194,12 +219,6 @@ static void kvm_setup_secondary_clock(void)
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

## [13] Sean Christopherson — 2026-05-15
*Subject: [PATCH v3 12/41] x86/paravirt: Remove unnecessary PARAVIRT=n stub for paravirt_set_sched_clock()*

Remove the unnecessary paravirt_set_sched_clock() stub for PARAVIRT=n, as
all callers are gated by PARAVIRT=y.  Eliminating the stub will avoid a
pile of pointless churn as the "real" implementation evolves.

No functional change intended.

Fixes: 39965afb1151 ("x86/paravirt: Move paravirt_sched_clock() related code into tsc.c")
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
index e00f53e3dd8d..021612c22b84 100644
--- a/arch/x86/kernel/tsc.c
+++ b/arch/x86/kernel/tsc.c
@@ -288,7 +288,6 @@ void paravirt_set_sched_clock(u64 (*func)(void))
 u64 sched_clock_noinstr(void) __attribute__((alias("native_sched_clock")));
 
 bool using_native_sched_clock(void) { return true; }
-void paravirt_set_sched_clock(u64 (*func)(void)) { }
 #endif
 
 notrace u64 sched_clock(void)

---

## [14] Sean Christopherson — 2026-05-15
*Subject: [PATCH v3 13/41] x86/paravirt: Move handling of unstable PV clocks
 into paravirt_set_sched_clock()*

Move the handling of unstable PV clocks, of which kvmclock is the only
example, into paravirt_set_sched_clock().  This will allow modifying
paravirt_set_sched_clock() to keep using the TSC for sched_clock in
certain scenarios without unintentionally marking the TSC-based clock as
unstable.

No functional change intended.

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
index 006e3a13500b..1cbdb48e5503 100644
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
index 021612c22b84..567d30b30a5a 100644
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

## [15] Sean Christopherson — 2026-05-15
*Subject: [PATCH v3 14/41] x86/kvmclock: Move sched_clock save/restore helpers
 up in kvmclock.c*

Move kvmclock's sched_clock save/restore helper "up" so that they can
(eventually) be referenced by kvm_sched_clock_init().

No functional change intended.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kernel/kvmclock.c | 108 ++++++++++++++++++-------------------
 1 file changed, 54 insertions(+), 54 deletions(-)

diff --git a/arch/x86/kernel/kvmclock.c b/arch/x86/kernel/kvmclock.c
index 1cbdb48e5503..800c3d65f0af 100644
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
@@ -162,60 +216,6 @@ static struct clocksource kvm_clock = {
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

## [16] Sean Christopherson — 2026-05-15
*Subject: [PATCH v3 15/41] x86/xen/time: Nullify x86_platform's sched_clock
 save/restore hooks*

Nullify the x86_platform sched_clock save/restore hooks when setting up
Xen's PV clock to make it somewhat obvious the hooks aren't used when
running as a Xen guest (Xen uses a paravirtualized suspend/resume flow).

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/xen/time.c | 6 ++++++
 1 file changed, 6 insertions(+)

diff --git a/arch/x86/xen/time.c b/arch/x86/xen/time.c
index 3d3165eef821..21d366d01985 100644
--- a/arch/x86/xen/time.c
+++ b/arch/x86/xen/time.c
@@ -568,6 +568,12 @@ static void __init xen_init_time_common(void)
 	xen_sched_clock_offset = xen_clocksource_read();
 	static_call_update(pv_steal_clock, xen_steal_clock);
 	paravirt_set_sched_clock(xen_sched_clock);
+	/*
+	 * Xen has paravirtualized suspend/resume and so doesn't use the common
+	 * x86 sched_clock save/restore hooks.
+	 */
+	x86_platform.save_sched_clock_state = NULL;
+	x86_platform.restore_sched_clock_state = NULL;
 
 	tsc_register_calibration_routines(xen_tsc_khz, NULL);
 	x86_platform.get_wallclock = xen_get_wallclock;

---

## [17] Sean Christopherson — 2026-05-15
*Subject: [PATCH v3 16/41] x86/vmware: Nullify save/restore hooks when using
 VMware's sched_clock*

Nullify the sched_clock save/restore hooks when using VMware's version of
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
index b88d9ca01202..b5cb66ca022b 100644
--- a/arch/x86/kernel/cpu/vmware.c
+++ b/arch/x86/kernel/cpu/vmware.c
@@ -347,8 +347,11 @@ static void __init vmware_paravirt_ops_setup(void)
 
 	vmware_cyc2ns_setup();
 
-	if (vmw_sched_clock)
+	if (vmw_sched_clock) {
 		paravirt_set_sched_clock(vmware_sched_clock);
+		x86_platform.save_sched_clock_state = NULL;
+		x86_platform.restore_sched_clock_state = NULL;
+	}
 
 	if (vmware_is_stealclock_available()) {
 		has_steal_clock = true;

---

## [18] Sean Christopherson — 2026-05-15
*Subject: [PATCH v3 17/41] x86/tsc: WARN if TSC sched_clock save/restore used
 with PV sched_clock*

Now that all PV clocksources override the sched_clock save/restore hooks
when overriding sched_clock, WARN if the "default" TSC hooks are invoked
when using a PV sched_clock, e.g. to guard against regressions.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kernel/tsc.c | 12 ++++++++++--
 1 file changed, 10 insertions(+), 2 deletions(-)

diff --git a/arch/x86/kernel/tsc.c b/arch/x86/kernel/tsc.c
index 567d30b30a5a..b14c4ada89a3 100644
--- a/arch/x86/kernel/tsc.c
+++ b/arch/x86/kernel/tsc.c
@@ -984,9 +984,17 @@ EXPORT_SYMBOL_GPL(recalibrate_cpu_khz);
 
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
@@ -1006,7 +1014,7 @@ void tsc_restore_sched_clock_state(void)
 	unsigned long flags;
 	int cpu;
 
-	if (!static_branch_likely(&__use_tsc) && !sched_clock_stable())
+	if (!tsc_is_save_restore_needed())
 		return;
 
 	local_irq_save(flags);

---

## [19] Sean Christopherson — 2026-05-15
*Subject: [PATCH v3 18/41] x86/paravirt: Pass sched_clock save/restore helpers
 during registration*

Pass in a PV clock's save/restore helpers when configuring sched_clock
instead of relying on each PV clock to manually set the save/restore hooks.
In addition to bringing sanity to the code, this will allow gracefully
"rejecting" a PV sched_clock, e.g. when running as a CoCo guest that has
access to a "secure" TSC.

No functional change intended.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/timer.h       | 9 ++++++---
 arch/x86/kernel/cpu/vmware.c       | 7 ++-----
 arch/x86/kernel/kvmclock.c         | 6 +++---
 arch/x86/kernel/tsc.c              | 5 ++++-
 arch/x86/xen/time.c                | 5 ++---
 drivers/clocksource/hyperv_timer.c | 6 ++----
 6 files changed, 19 insertions(+), 19 deletions(-)

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
index b5cb66ca022b..968de002975f 100644
--- a/arch/x86/kernel/cpu/vmware.c
+++ b/arch/x86/kernel/cpu/vmware.c
@@ -347,11 +347,8 @@ static void __init vmware_paravirt_ops_setup(void)
 
 	vmware_cyc2ns_setup();
 
-	if (vmw_sched_clock) {
-		paravirt_set_sched_clock(vmware_sched_clock);
-		x86_platform.save_sched_clock_state = NULL;
-		x86_platform.restore_sched_clock_state = NULL;
-	}
+	if (vmw_sched_clock)
+		paravirt_set_sched_clock(vmware_sched_clock, NULL, NULL);
 
 	if (vmware_is_stealclock_available()) {
 		has_steal_clock = true;
diff --git a/arch/x86/kernel/kvmclock.c b/arch/x86/kernel/kvmclock.c
index 800c3d65f0af..962b6fcb5c60 100644
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
@@ -344,8 +346,6 @@ void __init kvmclock_init(void)
 #ifdef CONFIG_SMP
 	x86_cpuinit.early_percpu_clock_init = kvm_setup_secondary_clock;
 #endif
-	x86_platform.save_sched_clock_state = kvm_save_sched_clock_state;
-	x86_platform.restore_sched_clock_state = kvm_restore_sched_clock_state;
 	kvm_get_preset_lpj();
 
 	/*
diff --git a/arch/x86/kernel/tsc.c b/arch/x86/kernel/tsc.c
index b14c4ada89a3..0114c63dfdd9 100644
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
index 21d366d01985..ee7095febfd1 100644
--- a/arch/x86/xen/time.c
+++ b/arch/x86/xen/time.c
@@ -567,13 +567,12 @@ static void __init xen_init_time_common(void)
 {
 	xen_sched_clock_offset = xen_clocksource_read();
 	static_call_update(pv_steal_clock, xen_steal_clock);
-	paravirt_set_sched_clock(xen_sched_clock);
+
 	/*
 	 * Xen has paravirtualized suspend/resume and so doesn't use the common
 	 * x86 sched_clock save/restore hooks.
 	 */
-	x86_platform.save_sched_clock_state = NULL;
-	x86_platform.restore_sched_clock_state = NULL;
+	paravirt_set_sched_clock(xen_sched_clock, NULL, NULL);
 
 	tsc_register_calibration_routines(xen_tsc_khz, NULL);
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

## [20] Sean Christopherson — 2026-05-15
*Subject: [PATCH v3 19/41] x86/kvmclock: Move kvm_sched_clock_init() down in kvmclock.c*

Move kvm_sched_clock_init() "down" so that it can reference the global
kvm_clock structure without needing a forward declaration.

Opportunistically mark the helper as "__init" instead of "inline" to make
its usage more obvious; modern compilers don't need a hint to inline a
single-use function, and an extra CALL+RET pair during boot is a complete
non-issue.  And, if the compiler ignores the hint and does NOT inline the
function, the resulting code may not get discarded after boot due lack of
an __init annotation.

No functional change intended.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kernel/kvmclock.c | 28 ++++++++++++++--------------
 1 file changed, 14 insertions(+), 14 deletions(-)

diff --git a/arch/x86/kernel/kvmclock.c b/arch/x86/kernel/kvmclock.c
index 962b6fcb5c60..8df6adcd6cd8 100644
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
@@ -304,6 +290,20 @@ static int kvmclock_setup_percpu(unsigned int cpu)
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
 void __init kvmclock_init(void)
 {
 	u8 flags;

---

## [21] Sean Christopherson — 2026-05-15
*Subject: [PATCH v3 20/41] x86/xen/time: Mark xen_setup_vsyscall_time_info() as __init*

Annotate xen_setup_vsyscall_time_info() as being used only during kernel
initialization; it's called only by xen_time_init(), which is already
tagged __init.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/xen/time.c | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)

diff --git a/arch/x86/xen/time.c b/arch/x86/xen/time.c
index ee7095febfd1..f087bb76457d 100644
--- a/arch/x86/xen/time.c
+++ b/arch/x86/xen/time.c
@@ -444,7 +444,7 @@ void xen_restore_time_memory_area(void)
 	xen_sched_clock_offset = xen_clocksource_read() - xen_clock_value_saved;
 }
 
-static void xen_setup_vsyscall_time_info(void)
+static void __init xen_setup_vsyscall_time_info(void)
 {
 	struct vcpu_register_time_memory_area t;
 	struct pvclock_vsyscall_time_info *ti;

---

## [22] Sean Christopherson — 2026-05-15
*Subject: [PATCH v3 21/41] x86/pvclock: Mark setup helpers and related various
 as __init/__ro_after_init*

Now that Xen PV clock and kvmclock explicitly do setup only during init,
tag the common PV clock flags/vsyscall variables and their mutators with
__init.

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

## [23] Sean Christopherson — 2026-05-15
*Subject: [PATCH v3 22/41] x86/pvclock: WARN if pvclock's valid_flags are overwritten*

WARN if the common PV clock valid_flags are overwritten; all PV clocks
expect that they are the one and only PV clock, i.e. don't guard against
another PV clock having modified the flags.

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

## [24] Sean Christopherson — 2026-05-15
*Subject: [PATCH v3 23/41] x86/kvmclock: Refactor handling of
 PVCLOCK_TSC_STABLE_BIT during kvmclock_init()*

Clean up the setting of PVCLOCK_TSC_STABLE_BIT during kvmclock init to
make it somewhat obvious that pvclock_read_flags() must be called *after*
pvclock_set_flags().

Note, in theory, a different PV clock could have set PVCLOCK_TSC_STABLE_BIT
in the supported flags, i.e. reading flags only if
KVM_FEATURE_CLOCKSOURCE_STABLE_BIT is set could very, very theoretically
result in a change in behavior.  In practice, the kernel only supports a
single PV clock.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kernel/kvmclock.c | 15 +++++++++++----
 1 file changed, 11 insertions(+), 4 deletions(-)

diff --git a/arch/x86/kernel/kvmclock.c b/arch/x86/kernel/kvmclock.c
index 8df6adcd6cd8..ccb2aff89b2f 100644
--- a/arch/x86/kernel/kvmclock.c
+++ b/arch/x86/kernel/kvmclock.c
@@ -306,7 +306,7 @@ static __init void kvm_sched_clock_init(bool stable)
 
 void __init kvmclock_init(void)
 {
-	u8 flags;
+	bool stable = false;
 
 	if (!kvm_para_available() || !kvmclock)
 		return;
@@ -333,11 +333,18 @@ void __init kvmclock_init(void)
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
 
 	tsc_register_calibration_routines(kvm_get_tsc_khz, kvm_get_tsc_khz);

---

## [25] Sean Christopherson — 2026-05-15
*Subject: [PATCH v3 24/41] timekeeping: Resume clocksources before reading
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

## [26] Sean Christopherson — 2026-05-15
*Subject: [PATCH v3 25/41] x86/kvmclock: Hook clocksource.suspend/resume when
 kvmclock isn't sched_clock*

Save/restore kvmclock across suspend/resume via clocksource hooks when
kvmclock isn't being used for sched_clock.  This will allow using kvmclock
as a clocksource (or for wallclock!) without also using it for sched_clock.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kernel/kvmclock.c | 23 ++++++++++++++++++++++-
 1 file changed, 22 insertions(+), 1 deletion(-)

diff --git a/arch/x86/kernel/kvmclock.c b/arch/x86/kernel/kvmclock.c
index ccb2aff89b2f..655037949446 100644
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
@@ -202,6 +212,8 @@ static struct clocksource kvm_clock = {
 	.flags	= CLOCK_SOURCE_IS_CONTINUOUS,
 	.id     = CSID_X86_KVM_CLK,
 	.enable	= kvm_cs_enable,
+	.suspend = kvmclock_suspend,
+	.resume = kvmclock_resume,
 };
 
 static void __init kvmclock_init_mem(void)
@@ -297,6 +309,15 @@ static __init void kvm_sched_clock_init(bool stable)
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

## [27] Sean Christopherson — 2026-05-15
*Subject: [PATCH v3 26/41] x86/kvmclock: WARN if wall clock is read while
 kvmclock is suspended*

WARN if kvmclock is still suspended when its wallclock is read, i.e. when
the kernel reads its persistent clock.  The wallclock subtly depends on
the BSP's kvmclock being enabled, and returns garbage if kvmclock is
disabled.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kernel/kvmclock.c | 7 +++++++
 1 file changed, 7 insertions(+)

diff --git a/arch/x86/kernel/kvmclock.c b/arch/x86/kernel/kvmclock.c
index 655037949446..e7250d21c672 100644
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

## [28] Sean Christopherson — 2026-05-15
*Subject: [PATCH v3 27/41] x86/kvmclock: Enable kvmclock on APs during onlining
 if kvmclock isn't sched_clock*

In anticipation of making x86_cpuinit.early_percpu_clock_init(), i.e.
kvm_setup_secondary_clock(), a dedicated sched_clock hook that will be
invoked if and only if kvmclock is set as sched_clock, ensure APs enable
their kvmclock during CPU online.  While a redundant write to the MSR is
technically ok, skip the registration when kvmclock is sched_clock so that
it's somewhat obvious that kvmclock *needs* to be enabled during early
bringup when it's being used as sched_clock.

Plumb in the BSP's resume path purely for documentation purposes.  Both
KVM (as-a-guest) and timekeeping/clocksource hook syscore_ops, and it's
not super obvious that using KVM's hooks would be flawed.  E.g. it would
work today, because KVM's hooks happen to run after/before timekeeping's
hooks during suspend/resume, but that's sheer dumb luck as the order in
which syscore_ops are invoked depends entirely on when a subsystem is
initialized and thus registers its hooks.

Opportunsitically make the registration messages more precise to help
debug issues where kvmclock is enabled too late.

Opportunstically WARN in kvmclock_{suspend,resume}() to harden against
future bugs.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/kvm_para.h |  2 ++
 arch/x86/kernel/kvm.c           | 24 +++++++++++-------
 arch/x86/kernel/kvmclock.c      | 44 +++++++++++++++++++++++++++------
 3 files changed, 53 insertions(+), 17 deletions(-)

diff --git a/arch/x86/include/asm/kvm_para.h b/arch/x86/include/asm/kvm_para.h
index 2adba2aff539..17053d2bf270 100644
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
index 0131bc1cb459..65c787b1ea03 100644
--- a/arch/x86/kernel/kvm.c
+++ b/arch/x86/kernel/kvm.c
@@ -471,18 +471,24 @@ static void kvm_guest_cpu_offline(enum kvm_guest_cpu_action action)
 	kvmclock_cpu_action(action);
 }
 
+static int __kvm_cpu_online(unsigned int cpu, enum kvm_guest_cpu_action action)
+{
+	unsigned long flags;
+
+	local_irq_save(flags);
+	kvmclock_cpu_action(action);
+	kvm_guest_cpu_init();
+	local_irq_restore(flags);
+	return 0;
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
-	return 0;
+	return __kvm_cpu_online(cpu, KVM_GUEST_AP_ONLINE);
 }
 
-#ifdef CONFIG_SMP
-
 static DEFINE_PER_CPU(cpumask_var_t, __pv_cpu_mask);
 
 static bool pv_tlb_flush_supported(void)
@@ -747,7 +753,7 @@ static int kvm_suspend(void *data)
 
 static void kvm_resume(void *data)
 {
-	kvm_cpu_online(raw_smp_processor_id());
+	__kvm_cpu_online(raw_smp_processor_id(), KVM_GUEST_BSP_RESUME);
 
 #ifdef CONFIG_ARCH_CPUIDLE_HALTPOLL
 	if (kvm_para_has_feature(KVM_FEATURE_POLL_CONTROL) && has_guest_poll)
diff --git a/arch/x86/kernel/kvmclock.c b/arch/x86/kernel/kvmclock.c
index e7250d21c672..d3bb281c0805 100644
--- a/arch/x86/kernel/kvmclock.c
+++ b/arch/x86/kernel/kvmclock.c
@@ -53,6 +53,7 @@ static struct pvclock_vsyscall_time_info *hvclock_mem;
 DEFINE_PER_CPU(struct pvclock_vsyscall_time_info *, hv_clock_per_cpu);
 EXPORT_PER_CPU_SYMBOL_GPL(hv_clock_per_cpu);
 
+static bool kvmclock_is_sched_clock;
 static bool kvmclock_suspended;
 
 /*
@@ -129,7 +130,7 @@ static void kvm_save_sched_clock_state(void)
 #ifdef CONFIG_SMP
 static void kvm_setup_secondary_clock(void)
 {
-	kvm_register_clock("secondary cpu clock");
+	kvm_register_clock("secondary cpu, sched_clock setup");
 }
 #endif
 
@@ -141,25 +142,51 @@ static void kvm_restore_sched_clock_state(void)
 
 static void kvmclock_suspend(struct clocksource *cs)
 {
+	if (WARN_ON_ONCE(kvmclock_is_sched_clock))
+		return;
+
 	kvmclock_suspended = true;
 	kvmclock_disable();
 }
 
 static void kvmclock_resume(struct clocksource *cs)
 {
+	if (WARN_ON_ONCE(kvmclock_is_sched_clock))
+		return;
+
 	kvmclock_suspended = false;
 	kvm_register_clock("primary cpu, clocksource resume");
 }
 
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
+		 * Secondary CPUs use dedicated sched_clock hooks to enable
+		 * kvmclock early during bringup, there's nothing to be done
+		 * when during CPU online.
+		 */
+		if (kvmclock_is_sched_clock)
+			break;
+		kvm_register_clock("secondary cpu, online");
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
@@ -315,6 +342,7 @@ static __init void kvm_sched_clock_init(bool stable)
 	__paravirt_set_sched_clock(kvm_sched_clock_read, stable,
 				   kvm_save_sched_clock_state,
 				   kvm_restore_sched_clock_state);
+	kvmclock_is_sched_clock = true;
 
 	/*
 	 * The BSP's clock is managed via dedicated sched_clock save/restore
@@ -358,7 +386,7 @@ void __init kvmclock_init(void)
 		msr_kvm_system_time, msr_kvm_wall_clock);
 
 	this_cpu_write(hv_clock_per_cpu, &hv_clock_boot[0]);
-	kvm_register_clock("primary cpu clock");
+	kvm_register_clock("primary cpu, online");
 	pvclock_set_pvti_cpu0_va(hv_clock_boot);
 
 	if (kvm_para_has_feature(KVM_FEATURE_CLOCKSOURCE_STABLE_BIT)) {

---

## [29] Sean Christopherson — 2026-05-15
*Subject: [PATCH v3 28/41] x86/paravirt: Mark __paravirt_set_sched_clock() as __init*

Annotate __paravirt_set_sched_clock() as __init, and make its wrapper
__always_inline to ensure sanitizers don't result in a non-inline version
hanging around.  All callers run during __init, and changing sched_clock
after boot would be all kinds of crazy.

No functional change intended.

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
index 0114c63dfdd9..4a48b8ba5bea 100644
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

## [30] Sean Christopherson — 2026-05-15
*Subject: [PATCH v3 29/41] x86/paravirt: Plumb a return code into __paravirt_set_sched_clock()*

Add a return code to __paravirt_set_sched_clock() so that the kernel can
reject attempts to use a PV sched_clock without breaking the caller.  E.g.
when running as a CoCo VM with a secure TSC, using a PV clock is generally
undesirable.

Note, kvmclock is the only PV clock that does anything "extra" beyond
simply registering itself as sched_clock, i.e. is the only caller that
needs to check the new return value.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/timer.h | 6 +++---
 arch/x86/kernel/kvmclock.c   | 8 +++++---
 arch/x86/kernel/tsc.c        | 5 +++--
 3 files changed, 11 insertions(+), 8 deletions(-)

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
index d3bb281c0805..9b3d1ed1a96d 100644
--- a/arch/x86/kernel/kvmclock.c
+++ b/arch/x86/kernel/kvmclock.c
@@ -338,10 +338,12 @@ static int kvmclock_setup_percpu(unsigned int cpu)
 
 static __init void kvm_sched_clock_init(bool stable)
 {
+	if (__paravirt_set_sched_clock(kvm_sched_clock_read, stable,
+				       kvm_save_sched_clock_state,
+				       kvm_restore_sched_clock_state))
+		return;
+
 	kvm_sched_clock_offset = kvm_clock_read();
-	__paravirt_set_sched_clock(kvm_sched_clock_read, stable,
-				   kvm_save_sched_clock_state,
-				   kvm_restore_sched_clock_state);
 	kvmclock_is_sched_clock = true;
 
 	/*
diff --git a/arch/x86/kernel/tsc.c b/arch/x86/kernel/tsc.c
index 4a48b8ba5bea..3c15fc10e501 100644
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

## [31] Sean Christopherson — 2026-05-15
*Subject: [PATCH v3 30/41] x86/paravirt: Don't use a PV sched_clock in CoCo
 guests with trusted TSC*

Silently ignore attempts to switch to a paravirt sched_clock when running
as a CoCo guest with trusted TSC.  In hand-wavy theory, a misbehaving
hypervisor could attack the guest by manipulating the PV clock to affect
guest scheduling in some weird and/or predictable way.  More importantly,
reading TSC on such platforms is faster than any PV clock, and sched_clock
is all about speed.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kernel/tsc.c | 9 +++++++++
 1 file changed, 9 insertions(+)

diff --git a/arch/x86/kernel/tsc.c b/arch/x86/kernel/tsc.c
index 3c15fc10e501..ac4abfec1f05 100644
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

## [32] Sean Christopherson — 2026-05-15
*Subject: [PATCH v3 31/41] x86/tsc: Pass KNOWN_FREQ and RELIABLE as params to registration*

Add a "tsc_properties" set of flags and use it to annotate whether the
TSC operates at a known and/or reliable frequency when registering a
paravirtual TSC calibration routine.  Currently, each PV flow manually
sets the associated feature flags, but often in haphazard fashion that
makes it difficult for unfamiliar readers to see the properties of the
TSC when running under a particular hypervisor.

The other, bigger issue with manually setting the feature flags is that
it decouples the flags from the calibration routine.  E.g. in theory, PV
code could mark the TSC as having a known frequency, but then have its
PV calibration discarded in favor of a method that doesn't use that known
frequency.  Passing the TSC properties along with the calibration routine
will allow adding sanity checks to guard against replacing a "better"
calibration routine with a "worse" routine.

As a bonus, the flags also give developers working on new PV code a heads
up that they should at least mark the TSC as having a known frequency.

Reviewed-by: Michael Kelley <mhklinux@outlook.com>
Tested-by: Michael Kelley <mhklinux@outlook.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/coco/sev/core.c       |  6 ++----
 arch/x86/coco/tdx/tdx.c        |  7 ++-----
 arch/x86/include/asm/tsc.h     |  8 +++++++-
 arch/x86/kernel/cpu/acrn.c     |  4 ++--
 arch/x86/kernel/cpu/mshyperv.c | 10 +++++++---
 arch/x86/kernel/cpu/vmware.c   |  7 ++++---
 arch/x86/kernel/jailhouse.c    |  4 ++--
 arch/x86/kernel/kvmclock.c     |  4 ++--
 arch/x86/kernel/tsc.c          |  8 +++++++-
 arch/x86/xen/time.c            |  4 ++--
 10 files changed, 37 insertions(+), 25 deletions(-)

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index 39fb50697542..822a2a0f1a2f 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -2037,9 +2037,6 @@ void __init snp_secure_tsc_init(void)
 
 	secrets = (__force struct snp_secrets_page *)mem;
 
-	setup_force_cpu_cap(X86_FEATURE_TSC_KNOWN_FREQ);
-	setup_force_cpu_cap(X86_FEATURE_TSC_RELIABLE);
-
 	rdmsrq(MSR_AMD64_GUEST_TSC_FREQ, tsc_freq_mhz);
 
 	/* Extract the GUEST TSC MHZ from BIT[17:0], rest is reserved space */
@@ -2048,7 +2045,8 @@ void __init snp_secure_tsc_init(void)
 	snp_tsc_freq_khz = SNP_SCALE_TSC_FREQ(tsc_freq_mhz * 1000, secrets->tsc_factor);
 
 	tsc_register_calibration_routines(securetsc_get_tsc_khz,
-					  securetsc_get_tsc_khz);
+					  securetsc_get_tsc_khz,
+					  TSC_FREQ_KNOWN_AND_RELIABLE);
 
 	early_memunmap(mem, PAGE_SIZE);
 }
diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 26890cea790b..7050f3ee6593 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -1208,14 +1208,11 @@ static unsigned long tdx_get_tsc_khz(void)
 
 void __init tdx_tsc_init(void)
 {
-	/* TSC is the only reliable clock in TDX guest */
-	setup_force_cpu_cap(X86_FEATURE_TSC_RELIABLE);
-	setup_force_cpu_cap(X86_FEATURE_TSC_KNOWN_FREQ);
-
 	/*
 	 * Override the PV calibration routines (if set) with more trustworthy
 	 * CPUID-based calibration.  The TDX module emulates CPUID, whereas any
 	 * PV information is provided by the hypervisor.
 	 */
-	tsc_register_calibration_routines(tdx_get_tsc_khz, NULL);
+	tsc_register_calibration_routines(tdx_get_tsc_khz, NULL,
+					  TSC_FREQ_KNOWN_AND_RELIABLE);
 }
diff --git a/arch/x86/include/asm/tsc.h b/arch/x86/include/asm/tsc.h
index bae709f5f44d..f458be688512 100644
--- a/arch/x86/include/asm/tsc.h
+++ b/arch/x86/include/asm/tsc.h
@@ -95,8 +95,14 @@ extern int cpuid_get_tsc_freq(struct cpuid_tsc_info *info);
 extern void tsc_early_init(void);
 extern void tsc_init(void);
 #if defined(CONFIG_HYPERVISOR_GUEST) || defined(CONFIG_AMD_MEM_ENCRYPT)
+enum tsc_properties {
+	TSC_FREQUENCY_KNOWN	= BIT(0),
+	TSC_RELIABLE		= BIT(1),
+	TSC_FREQ_KNOWN_AND_RELIABLE = TSC_FREQUENCY_KNOWN | TSC_RELIABLE,
+};
 extern void tsc_register_calibration_routines(unsigned long (*calibrate_tsc)(void),
-					      unsigned long (*calibrate_cpu)(void));
+					      unsigned long (*calibrate_cpu)(void),
+					      enum tsc_properties properties);
 #endif
 extern void mark_tsc_unstable(char *reason);
 extern int unsynchronized_tsc(void);
diff --git a/arch/x86/kernel/cpu/acrn.c b/arch/x86/kernel/cpu/acrn.c
index 2da3de4d470e..4f2f4f7ec334 100644
--- a/arch/x86/kernel/cpu/acrn.c
+++ b/arch/x86/kernel/cpu/acrn.c
@@ -29,9 +29,9 @@ static void __init acrn_init_platform(void)
 	/* Install system interrupt handler for ACRN hypervisor callback */
 	sysvec_install(HYPERVISOR_CALLBACK_VECTOR, sysvec_acrn_hv_callback);
 
-	setup_force_cpu_cap(X86_FEATURE_TSC_KNOWN_FREQ);
 	tsc_register_calibration_routines(acrn_get_tsc_khz,
-					  acrn_get_tsc_khz);
+					  acrn_get_tsc_khz,
+					  TSC_FREQUENCY_KNOWN);
 }
 
 static bool acrn_x2apic_available(void)
diff --git a/arch/x86/kernel/cpu/mshyperv.c b/arch/x86/kernel/cpu/mshyperv.c
index 5ca139ae50b4..734d79c10ae5 100644
--- a/arch/x86/kernel/cpu/mshyperv.c
+++ b/arch/x86/kernel/cpu/mshyperv.c
@@ -516,8 +516,13 @@ static void __init ms_hyperv_init_platform(void)
 
 	if (ms_hyperv.features & HV_ACCESS_FREQUENCY_MSRS &&
 	    ms_hyperv.misc_features & HV_FEATURE_FREQUENCY_MSRS_AVAILABLE) {
-		tsc_register_calibration_routines(hv_get_tsc_khz, hv_get_tsc_khz);
-		setup_force_cpu_cap(X86_FEATURE_TSC_KNOWN_FREQ);
+		enum tsc_properties tsc_properties = TSC_FREQUENCY_KNOWN;
+
+		if (ms_hyperv.features & HV_ACCESS_TSC_INVARIANT)
+			tsc_properties = TSC_FREQ_KNOWN_AND_RELIABLE;
+
+		tsc_register_calibration_routines(hv_get_tsc_khz, hv_get_tsc_khz,
+						  tsc_properties);
 	}
 
 	if (ms_hyperv.priv_high & HV_ISOLATION) {
@@ -629,7 +634,6 @@ static void __init ms_hyperv_init_platform(void)
 		 * is called.
 		 */
 		wrmsrq(HV_X64_MSR_TSC_INVARIANT_CONTROL, HV_EXPOSE_INVARIANT_TSC);
-		setup_force_cpu_cap(X86_FEATURE_TSC_RELIABLE);
 	}
 
 	/*
diff --git a/arch/x86/kernel/cpu/vmware.c b/arch/x86/kernel/cpu/vmware.c
index 968de002975f..c19fa4471800 100644
--- a/arch/x86/kernel/cpu/vmware.c
+++ b/arch/x86/kernel/cpu/vmware.c
@@ -388,10 +388,10 @@ static void __init vmware_paravirt_ops_setup(void)
  */
 static void __init vmware_set_capabilities(void)
 {
+	/* TSC is non-stop and reliable even if the frequency isn't known. */
 	setup_force_cpu_cap(X86_FEATURE_CONSTANT_TSC);
 	setup_force_cpu_cap(X86_FEATURE_TSC_RELIABLE);
-	if (vmware_tsc_khz)
-		setup_force_cpu_cap(X86_FEATURE_TSC_KNOWN_FREQ);
+
 	if (vmware_hypercall_mode == CPUID_VMWARE_FEATURES_ECX_VMCALL)
 		setup_force_cpu_cap(X86_FEATURE_VMCALL);
 	else if (vmware_hypercall_mode == CPUID_VMWARE_FEATURES_ECX_VMMCALL)
@@ -420,7 +420,8 @@ static void __init vmware_platform_setup(void)
 
 		vmware_tsc_khz = tsc_khz;
 		tsc_register_calibration_routines(vmware_get_tsc_khz,
-						  vmware_get_tsc_khz);
+						  vmware_get_tsc_khz,
+						  TSC_FREQ_KNOWN_AND_RELIABLE);
 
 #ifdef CONFIG_X86_LOCAL_APIC
 		/* Skip lapic calibration since we know the bus frequency. */
diff --git a/arch/x86/kernel/jailhouse.c b/arch/x86/kernel/jailhouse.c
index db8f31fdb480..1bdc9ab321e0 100644
--- a/arch/x86/kernel/jailhouse.c
+++ b/arch/x86/kernel/jailhouse.c
@@ -219,7 +219,8 @@ static void __init jailhouse_init_platform(void)
 
 	machine_ops.emergency_restart		= jailhouse_no_restart;
 
-	tsc_register_calibration_routines(jailhouse_get_tsc, jailhouse_get_tsc);
+	tsc_register_calibration_routines(jailhouse_get_tsc, jailhouse_get_tsc,
+					  TSC_FREQUENCY_KNOWN);
 
 	while (pa_data) {
 		mapping = early_memremap(pa_data, sizeof(header));
@@ -257,7 +258,6 @@ static void __init jailhouse_init_platform(void)
 	pr_debug("Jailhouse: PM-Timer IO Port: %#x\n", pmtmr_ioport);
 
 	precalibrated_tsc_khz = setup_data.v1.tsc_khz;
-	setup_force_cpu_cap(X86_FEATURE_TSC_KNOWN_FREQ);
 
 	pci_probe = 0;
 
diff --git a/arch/x86/kernel/kvmclock.c b/arch/x86/kernel/kvmclock.c
index 9b3d1ed1a96d..b6b2018c51db 100644
--- a/arch/x86/kernel/kvmclock.c
+++ b/arch/x86/kernel/kvmclock.c
@@ -200,7 +200,6 @@ void kvmclock_cpu_action(enum kvm_guest_cpu_action action)
  */
 static unsigned long kvm_get_tsc_khz(void)
 {
-	setup_force_cpu_cap(X86_FEATURE_TSC_KNOWN_FREQ);
 	return pvclock_tsc_khz(this_cpu_pvti());
 }
 
@@ -404,7 +403,8 @@ void __init kvmclock_init(void)
 
 	kvm_sched_clock_init(stable);
 
-	tsc_register_calibration_routines(kvm_get_tsc_khz, kvm_get_tsc_khz);
+	tsc_register_calibration_routines(kvm_get_tsc_khz, kvm_get_tsc_khz,
+					  TSC_FREQUENCY_KNOWN);
 
 	x86_platform.get_wallclock = kvm_get_wallclock;
 	x86_platform.set_wallclock = kvm_set_wallclock;
diff --git a/arch/x86/kernel/tsc.c b/arch/x86/kernel/tsc.c
index ac4abfec1f05..98bef1d06fa9 100644
--- a/arch/x86/kernel/tsc.c
+++ b/arch/x86/kernel/tsc.c
@@ -1311,11 +1311,17 @@ static void __init check_system_tsc_reliable(void)
  */
 #if defined(CONFIG_HYPERVISOR_GUEST) || defined(CONFIG_AMD_MEM_ENCRYPT)
 void tsc_register_calibration_routines(unsigned long (*calibrate_tsc)(void),
-				       unsigned long (*calibrate_cpu)(void))
+				       unsigned long (*calibrate_cpu)(void),
+				       enum tsc_properties properties)
 {
 	if (WARN_ON_ONCE(!calibrate_tsc))
 		return;
 
+	if (properties & TSC_FREQUENCY_KNOWN)
+		setup_force_cpu_cap(X86_FEATURE_TSC_KNOWN_FREQ);
+	if (properties & TSC_RELIABLE)
+		setup_force_cpu_cap(X86_FEATURE_TSC_RELIABLE);
+
 	x86_platform.calibrate_tsc = calibrate_tsc;
 	if (calibrate_cpu)
 		x86_platform.calibrate_cpu = calibrate_cpu;
diff --git a/arch/x86/xen/time.c b/arch/x86/xen/time.c
index f087bb76457d..c04548641558 100644
--- a/arch/x86/xen/time.c
+++ b/arch/x86/xen/time.c
@@ -43,7 +43,6 @@ static unsigned long xen_tsc_khz(void)
 	struct pvclock_vcpu_time_info *info =
 		&HYPERVISOR_shared_info->vcpu_info[0].time;
 
-	setup_force_cpu_cap(X86_FEATURE_TSC_KNOWN_FREQ);
 	return pvclock_tsc_khz(info);
 }
 
@@ -574,7 +573,8 @@ static void __init xen_init_time_common(void)
 	 */
 	paravirt_set_sched_clock(xen_sched_clock, NULL, NULL);
 
-	tsc_register_calibration_routines(xen_tsc_khz, NULL);
+	tsc_register_calibration_routines(xen_tsc_khz, NULL,
+					  TSC_FREQUENCY_KNOWN);
 	x86_platform.get_wallclock = xen_get_wallclock;
 }

---

## [33] Sean Christopherson — 2026-05-15
*Subject: [PATCH v3 32/41] x86/tsc: Rejects attempts to override TSC
 calibration with lesser routine*

When registering a TSC frequency calibration routine, sanity check that
the incoming routine is as robust as the outgoing routine, and reject the
incoming routine if the sanity check fails.

Because native calibration routines only mark the TSC frequency as known
and reliable when they actually run, the effective progression of
capabilities is: None (native) => Known and maybe Reliable (PV) =>
Known and Reliable (CoCo).  Violating that progression for a PV override
is relatively benign, but messing up the progression when CoCo is
involved is more problematic, as it likely means a trusted source of
information (hardware/firmware) is being discarded in favor of a less
trusted source (hypervisor).

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kernel/tsc.c | 5 +++++
 1 file changed, 5 insertions(+)

diff --git a/arch/x86/kernel/tsc.c b/arch/x86/kernel/tsc.c
index 98bef1d06fa9..7a261214fa3e 100644
--- a/arch/x86/kernel/tsc.c
+++ b/arch/x86/kernel/tsc.c
@@ -1319,8 +1319,13 @@ void tsc_register_calibration_routines(unsigned long (*calibrate_tsc)(void),
 
 	if (properties & TSC_FREQUENCY_KNOWN)
 		setup_force_cpu_cap(X86_FEATURE_TSC_KNOWN_FREQ);
+	else if (WARN_ON(boot_cpu_has(X86_FEATURE_TSC_KNOWN_FREQ)))
+		return;
+
 	if (properties & TSC_RELIABLE)
 		setup_force_cpu_cap(X86_FEATURE_TSC_RELIABLE);
+	else if (WARN_ON(boot_cpu_has(X86_FEATURE_TSC_RELIABLE)))
+		return;
 
 	x86_platform.calibrate_tsc = calibrate_tsc;
 	if (calibrate_cpu)

---

## [34] Sean Christopherson — 2026-05-15
*Subject: [PATCH v3 33/41] x86/kvmclock: Mark TSC as reliable when it's
 constant and nonstop*

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
 arch/x86/kernel/kvmclock.c | 29 ++++++++++++++++-------------
 1 file changed, 16 insertions(+), 13 deletions(-)

diff --git a/arch/x86/kernel/kvmclock.c b/arch/x86/kernel/kvmclock.c
index b6b2018c51db..47f7df1e81a0 100644
--- a/arch/x86/kernel/kvmclock.c
+++ b/arch/x86/kernel/kvmclock.c
@@ -363,6 +363,7 @@ static __init void kvm_sched_clock_init(bool stable)
 
 void __init kvmclock_init(void)
 {
+	enum tsc_properties tsc_properties = TSC_FREQUENCY_KNOWN;
 	bool stable = false;
 
 	if (!kvm_para_available() || !kvmclock)
@@ -401,18 +402,6 @@ void __init kvmclock_init(void)
 			 PVCLOCK_TSC_STABLE_BIT;
 	}
 
-	kvm_sched_clock_init(stable);
-
-	tsc_register_calibration_routines(kvm_get_tsc_khz, kvm_get_tsc_khz,
-					  TSC_FREQUENCY_KNOWN);
-
-	x86_platform.get_wallclock = kvm_get_wallclock;
-	x86_platform.set_wallclock = kvm_set_wallclock;
-#ifdef CONFIG_SMP
-	x86_cpuinit.early_percpu_clock_init = kvm_setup_secondary_clock;
-#endif
-	kvm_get_preset_lpj();
-
 	/*
 	 * X86_FEATURE_NONSTOP_TSC is TSC runs at constant rate
 	 * with P/T states and does not stop in deep C-states.
@@ -423,8 +412,22 @@ void __init kvmclock_init(void)
 	 */
 	if (boot_cpu_has(X86_FEATURE_CONSTANT_TSC) &&
 	    boot_cpu_has(X86_FEATURE_NONSTOP_TSC) &&
-	    !check_tsc_unstable())
+	    !check_tsc_unstable()) {
 		kvm_clock.rating = 299;
+		tsc_properties = TSC_FREQ_KNOWN_AND_RELIABLE;
+	}
+
+	kvm_sched_clock_init(stable);
+
+	tsc_register_calibration_routines(kvm_get_tsc_khz, kvm_get_tsc_khz,
+					  tsc_properties);
+
+	x86_platform.get_wallclock = kvm_get_wallclock;
+	x86_platform.set_wallclock = kvm_set_wallclock;
+#ifdef CONFIG_SMP
+	x86_cpuinit.early_percpu_clock_init = kvm_setup_secondary_clock;
+#endif
+	kvm_get_preset_lpj();
 
 	clocksource_register_hz(&kvm_clock, NSEC_PER_SEC);
 	pv_info.name = "KVM";

---

## [35] Sean Christopherson — 2026-05-15
*Subject: [PATCH v3 34/41] KVM: x86: Officially define CPUID 0x40000010 as PV
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

## [36] Sean Christopherson — 2026-05-15
*Subject: [PATCH v3 35/41] x86/kvmclock: Obtain TSC frequency from CPUID if present*

From: David Woodhouse <dwmw@amazon.co.uk>

In https://lkml.org/lkml/2008/10/1/246 a proposal was made for generic
CPUID conventions across hypervisors. It was mostly shot down in flames,
but the leaf at 0x40000010 containing timing information didn't die.

It's used by XNU and FreeBSD guests under all hypervisors¹² to determine
the TSC frequency, and also exposed by the EC2 Nitro hypervisor (as
well as, presumably, VMware). FreeBSD's Bhyve is probably just about
to start exposing it too.

Use it under KVM to obtain the TSC frequency more accurately, instead
of reverse-calculating the frequency from the mul/shift values in the
KVM clock.

Before:
[    0.000020] tsc: Detected 2900.014 MHz processor

After:
[    0.000020] tsc: Detected 2900.015 MHz processor

$ cpuid -1 -l 0x40000010
CPU:
   hypervisor generic timing information (0x40000010):
      TSC frequency (Hz) = 2900015
      bus frequency (Hz) = 1000000

¹ https://github.com/apple/darwin-xnu/blob/main/osfmk/i386/cpuid.c
² https://github.com/freebsd/freebsd-src/commit/4a432614f68

Signed-off-by: David Woodhouse <dwmw@amazon.co.uk>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/kvm_para.h |  1 +
 arch/x86/kernel/kvm.c           | 10 ++++++++++
 arch/x86/kernel/kvmclock.c      |  6 +++++-
 3 files changed, 16 insertions(+), 1 deletion(-)

diff --git a/arch/x86/include/asm/kvm_para.h b/arch/x86/include/asm/kvm_para.h
index 17053d2bf270..3f7f558b5b24 100644
--- a/arch/x86/include/asm/kvm_para.h
+++ b/arch/x86/include/asm/kvm_para.h
@@ -129,6 +129,7 @@ enum kvm_guest_cpu_action {
 void kvmclock_init(void);
 void kvmclock_cpu_action(enum kvm_guest_cpu_action action);
 bool kvm_para_available(void);
+unsigned int kvm_para_tsc_khz(void);
 unsigned int kvm_arch_para_features(void);
 unsigned int kvm_arch_para_hints(void);
 void kvm_async_pf_task_wait_schedule(u32 token);
diff --git a/arch/x86/kernel/kvm.c b/arch/x86/kernel/kvm.c
index 65c787b1ea03..5cd92a0b156a 100644
--- a/arch/x86/kernel/kvm.c
+++ b/arch/x86/kernel/kvm.c
@@ -918,6 +918,16 @@ bool kvm_para_available(void)
 }
 EXPORT_SYMBOL_GPL(kvm_para_available);
 
+unsigned int kvm_para_tsc_khz(void)
+{
+	u32 base = kvm_cpuid_base();
+
+	if (cpuid_eax(base) >= (base | KVM_CPUID_TIMING_INFO))
+		return cpuid_eax(base | KVM_CPUID_TIMING_INFO);
+
+	return 0;
+}
+
 unsigned int kvm_arch_para_features(void)
 {
 	return cpuid_eax(kvm_cpuid_base() | KVM_CPUID_FEATURES);
diff --git a/arch/x86/kernel/kvmclock.c b/arch/x86/kernel/kvmclock.c
index 47f7df1e81a0..5ceba4f3836c 100644
--- a/arch/x86/kernel/kvmclock.c
+++ b/arch/x86/kernel/kvmclock.c
@@ -200,7 +200,11 @@ void kvmclock_cpu_action(enum kvm_guest_cpu_action action)
  */
 static unsigned long kvm_get_tsc_khz(void)
 {
-	return pvclock_tsc_khz(this_cpu_pvti());
+	/*
+	 * If KVM advertises the frequency directly in CPUID, use that
+	 * instead of reverse-calculating it from the KVM clock data.
+	 */
+	return kvm_para_tsc_khz() ? : pvclock_tsc_khz(this_cpu_pvti());
 }
 
 static void __init kvm_get_preset_lpj(void)

---

## [37] Sean Christopherson — 2026-05-15
*Subject: [PATCH v3 36/41] x86/kvmclock: Get local APIC bus frequency from PV
 CPUID Timing Info*

When running as a KVM guest with kvmclock support enabled, stuff the APIC
timer period/frequency with the local APIC bus frequency reported in
CPUID.0x40000010.EBX instead of trying to calibrate/guess the frequency.

See Documentation/virt/kvm/x86/cpuid.rst for details.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/kvm_para.h |  1 +
 arch/x86/kernel/kvm.c           | 19 ++++++++++++++++---
 arch/x86/kernel/kvmclock.c      | 13 +++++++++++--
 3 files changed, 28 insertions(+), 5 deletions(-)

diff --git a/arch/x86/include/asm/kvm_para.h b/arch/x86/include/asm/kvm_para.h
index 3f7f558b5b24..381d029b72e7 100644
--- a/arch/x86/include/asm/kvm_para.h
+++ b/arch/x86/include/asm/kvm_para.h
@@ -130,6 +130,7 @@ void kvmclock_init(void);
 void kvmclock_cpu_action(enum kvm_guest_cpu_action action);
 bool kvm_para_available(void);
 unsigned int kvm_para_tsc_khz(void);
+unsigned int kvm_para_apic_bus_khz(void);
 unsigned int kvm_arch_para_features(void);
 unsigned int kvm_arch_para_hints(void);
 void kvm_async_pf_task_wait_schedule(u32 token);
diff --git a/arch/x86/kernel/kvm.c b/arch/x86/kernel/kvm.c
index 5cd92a0b156a..bfe36e361b3c 100644
--- a/arch/x86/kernel/kvm.c
+++ b/arch/x86/kernel/kvm.c
@@ -918,12 +918,25 @@ bool kvm_para_available(void)
 }
 EXPORT_SYMBOL_GPL(kvm_para_available);
 
-unsigned int kvm_para_tsc_khz(void)
+static bool kvm_cpuid_has_timing_info(void)
 {
 	u32 base = kvm_cpuid_base();
 
-	if (cpuid_eax(base) >= (base | KVM_CPUID_TIMING_INFO))
-		return cpuid_eax(base | KVM_CPUID_TIMING_INFO);
+	return cpuid_eax(base) >= (base | KVM_CPUID_TIMING_INFO);
+}
+
+unsigned int kvm_para_tsc_khz(void)
+{
+	if (kvm_cpuid_has_timing_info())
+		return cpuid_eax(kvm_cpuid_base() | KVM_CPUID_TIMING_INFO);
+
+	return 0;
+}
+
+unsigned int kvm_para_apic_bus_khz(void)
+{
+	if (kvm_cpuid_has_timing_info())
+		return cpuid_ebx(kvm_cpuid_base() | KVM_CPUID_TIMING_INFO);
 
 	return 0;
 }
diff --git a/arch/x86/kernel/kvmclock.c b/arch/x86/kernel/kvmclock.c
index 5ceba4f3836c..abcc5b36ea1d 100644
--- a/arch/x86/kernel/kvmclock.c
+++ b/arch/x86/kernel/kvmclock.c
@@ -200,10 +200,19 @@ void kvmclock_cpu_action(enum kvm_guest_cpu_action action)
  */
 static unsigned long kvm_get_tsc_khz(void)
 {
+#ifdef CONFIG_X86_LOCAL_APIC
+	u32 apic_khz = kvm_para_apic_bus_khz();
+
 	/*
-	 * If KVM advertises the frequency directly in CPUID, use that
-	 * instead of reverse-calculating it from the KVM clock data.
+	 * Use the TSC frequency from KVM's (and other hypervisors') PV CPUID
+	 * leaf when available, instead of reverse-calculating it from the KVM
+	 * clock data.  As a bonus, the CPUID leaf also includes the local APIC
+	 * bus/timer frequency.
 	 */
+	if (apic_khz)
+		lapic_timer_period = apic_khz;
+#endif
+
 	return kvm_para_tsc_khz() ? : pvclock_tsc_khz(this_cpu_pvti());
 }

---

## [38] Sean Christopherson — 2026-05-15
*Subject: [PATCH v3 37/41] x86/kvmclock: Use TSC for sched_clock if it's
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
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kernel/kvmclock.c | 16 ++++++++--------
 1 file changed, 8 insertions(+), 8 deletions(-)

diff --git a/arch/x86/kernel/kvmclock.c b/arch/x86/kernel/kvmclock.c
index abcc5b36ea1d..0578bc448b1b 100644
--- a/arch/x86/kernel/kvmclock.c
+++ b/arch/x86/kernel/kvmclock.c
@@ -416,22 +416,22 @@ void __init kvmclock_init(void)
 	}
 
 	/*
-	 * X86_FEATURE_NONSTOP_TSC is TSC runs at constant rate
-	 * with P/T states and does not stop in deep C-states.
-	 *
-	 * Invariant TSC exposed by host means kvmclock is not necessary:
-	 * can use TSC as clocksource.
-	 *
+	 * If the TSC counts at a constant frequency across P/T states, counts
+	 * in deep C-states, and the TSC hasn't been marked unstable, prefer
+	 * the TSC over kvmclock for sched_clock and drop kvmclock's rating so
+	 * that TSC is chosen as the clocksource.  Note, the TSC unstable check
+	 * exists purely to honor the TSC being marked unstable via command
+	 * line, any runtime detection of an unstable will happen after this.
 	 */
 	if (boot_cpu_has(X86_FEATURE_CONSTANT_TSC) &&
 	    boot_cpu_has(X86_FEATURE_NONSTOP_TSC) &&
 	    !check_tsc_unstable()) {
 		kvm_clock.rating = 299;
 		tsc_properties = TSC_FREQ_KNOWN_AND_RELIABLE;
+	} else {
+		kvm_sched_clock_init(stable);
 	}
 
-	kvm_sched_clock_init(stable);
-
 	tsc_register_calibration_routines(kvm_get_tsc_khz, kvm_get_tsc_khz,
 					  tsc_properties);

---

## [39] Sean Christopherson — 2026-05-15
*Subject: [PATCH v3 38/41] x86/paravirt: kvmclock: Setup kvmclock early iff
 it's sched_clock*

Rework the seemingly generic x86_cpuinit_ops.early_percpu_clock_init hook
into a dedicated PV sched_clock hook, as the only reason the hook exists
is to allow kvmclock to enable its PV clock on secondary CPUs before the
kernel tries to reference sched_clock, e.g. when grabbing a timestamp for
printk.

Rearranging the hook doesn't exactly reduce complexity; arguably it does
the opposite.  But as-is, it's practically impossible to understand *why*
kvmclock needs to do early configuration.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/timer.h    |  8 ++++++--
 arch/x86/include/asm/x86_init.h |  2 --
 arch/x86/kernel/kvmclock.c      | 13 ++++++-------
 arch/x86/kernel/smpboot.c       |  3 ++-
 arch/x86/kernel/tsc.c           | 16 +++++++++++++++-
 arch/x86/kernel/x86_init.c      |  1 -
 6 files changed, 29 insertions(+), 14 deletions(-)

diff --git a/arch/x86/include/asm/timer.h b/arch/x86/include/asm/timer.h
index ca5c95d48c03..ab1271bd9c3b 100644
--- a/arch/x86/include/asm/timer.h
+++ b/arch/x86/include/asm/timer.h
@@ -15,14 +15,18 @@ extern bool using_native_sched_clock(void);
 
 #ifdef CONFIG_PARAVIRT
 int __init __paravirt_set_sched_clock(u64 (*func)(void), bool stable,
-				      void (*save)(void), void (*restore)(void));
+				      void (*save)(void), void (*restore)(void),
+				      void (*start_secondary));
 
 static __always_inline void paravirt_set_sched_clock(u64 (*func)(void),
 						     void (*save)(void),
 						     void (*restore)(void))
 {
-	(void)__paravirt_set_sched_clock(func, true, save, restore);
+	(void)__paravirt_set_sched_clock(func, true, save, restore, NULL);
 }
+void paravirt_sched_clock_start_secondary(void);
+#else
+static inline void paravirt_sched_clock_start_secondary(void) { }
 #endif
 
 /*
diff --git a/arch/x86/include/asm/x86_init.h b/arch/x86/include/asm/x86_init.h
index 6c8a6ead84f6..d1b3f18ea41f 100644
--- a/arch/x86/include/asm/x86_init.h
+++ b/arch/x86/include/asm/x86_init.h
@@ -187,13 +187,11 @@ struct x86_init_ops {
 /**
  * struct x86_cpuinit_ops - platform specific cpu hotplug setups
  * @setup_percpu_clockev:	set up the per cpu clock event device
- * @early_percpu_clock_init:	early init of the per cpu clock event device
  * @fixup_cpu_id:		fixup function for cpuinfo_x86::topo.pkg_id
  * @parallel_bringup:		Parallel bringup control
  */
 struct x86_cpuinit_ops {
 	void (*setup_percpu_clockev)(void);
-	void (*early_percpu_clock_init)(void);
 	void (*fixup_cpu_id)(struct cpuinfo_x86 *c, int node);
 	bool parallel_bringup;
 };
diff --git a/arch/x86/kernel/kvmclock.c b/arch/x86/kernel/kvmclock.c
index 0578bc448b1b..62c8ea2e6769 100644
--- a/arch/x86/kernel/kvmclock.c
+++ b/arch/x86/kernel/kvmclock.c
@@ -127,12 +127,13 @@ static void kvm_save_sched_clock_state(void)
 	kvmclock_disable();
 }
 
-#ifdef CONFIG_SMP
-static void kvm_setup_secondary_clock(void)
+static void kvm_setup_secondary_sched_clock(void)
 {
+	if (WARN_ON_ONCE(!IS_ENABLED(CONFIG_SMP)))
+		return;
+
 	kvm_register_clock("secondary cpu, sched_clock setup");
 }
-#endif
 
 static void kvm_restore_sched_clock_state(void)
 {
@@ -352,7 +353,8 @@ static __init void kvm_sched_clock_init(bool stable)
 {
 	if (__paravirt_set_sched_clock(kvm_sched_clock_read, stable,
 				       kvm_save_sched_clock_state,
-				       kvm_restore_sched_clock_state))
+				       kvm_restore_sched_clock_state,
+				       kvm_setup_secondary_sched_clock))
 		return;
 
 	kvm_sched_clock_offset = kvm_clock_read();
@@ -437,9 +439,6 @@ void __init kvmclock_init(void)
 
 	x86_platform.get_wallclock = kvm_get_wallclock;
 	x86_platform.set_wallclock = kvm_set_wallclock;
-#ifdef CONFIG_SMP
-	x86_cpuinit.early_percpu_clock_init = kvm_setup_secondary_clock;
-#endif
 	kvm_get_preset_lpj();
 
 	clocksource_register_hz(&kvm_clock, NSEC_PER_SEC);
diff --git a/arch/x86/kernel/smpboot.c b/arch/x86/kernel/smpboot.c
index 294a8ea60298..318ae70e5e7b 100644
--- a/arch/x86/kernel/smpboot.c
+++ b/arch/x86/kernel/smpboot.c
@@ -78,6 +78,7 @@
 #include <asm/io_apic.h>
 #include <asm/fpu/api.h>
 #include <asm/setup.h>
+#include <asm/timer.h>
 #include <asm/uv/uv.h>
 #include <asm/microcode.h>
 #include <asm/i8259.h>
@@ -275,7 +276,7 @@ static void notrace __noendbr start_secondary(void *unused)
 	cpu_init();
 	fpu__init_cpu();
 	rcutree_report_cpu_starting(raw_smp_processor_id());
-	x86_cpuinit.early_percpu_clock_init();
+	paravirt_sched_clock_start_secondary();
 
 	ap_starting();
 
diff --git a/arch/x86/kernel/tsc.c b/arch/x86/kernel/tsc.c
index 7a261214fa3e..f78e86494dec 100644
--- a/arch/x86/kernel/tsc.c
+++ b/arch/x86/kernel/tsc.c
@@ -280,8 +280,19 @@ bool using_native_sched_clock(void)
 	return static_call_query(pv_sched_clock) == native_sched_clock;
 }
 
+#ifdef CONFIG_SMP
+static void (*pv_sched_clock_start_secondary)(void) __ro_after_init;
+
+void paravirt_sched_clock_start_secondary(void)
+{
+	if (pv_sched_clock_start_secondary)
+		pv_sched_clock_start_secondary();
+}
+#endif
+
 int __init __paravirt_set_sched_clock(u64 (*func)(void), bool stable,
-				      void (*save)(void), void (*restore)(void))
+				      void (*save)(void), void (*restore)(void),
+				      void (*start_secondary))
 {
 	/*
 	 * Don't replace TSC with a PV clock when running as a CoCo guest and
@@ -298,6 +309,9 @@ int __init __paravirt_set_sched_clock(u64 (*func)(void), bool stable,
 	static_call_update(pv_sched_clock, func);
 	x86_platform.save_sched_clock_state = save;
 	x86_platform.restore_sched_clock_state = restore;
+#ifdef CONFIG_SMP
+	pv_sched_clock_start_secondary = start_secondary;
+#endif
 	return 0;
 }
 #else
diff --git a/arch/x86/kernel/x86_init.c b/arch/x86/kernel/x86_init.c
index ebefb77c37bb..cbb5ee613ed5 100644
--- a/arch/x86/kernel/x86_init.c
+++ b/arch/x86/kernel/x86_init.c
@@ -128,7 +128,6 @@ struct x86_init_ops x86_init __initdata = {
 };
 
 struct x86_cpuinit_ops x86_cpuinit = {
-	.early_percpu_clock_init	= x86_init_noop,
 	.setup_percpu_clockev		= setup_secondary_APIC_clock,
 	.parallel_bringup		= true,
 };

---

## [40] Sean Christopherson — 2026-05-15
*Subject: [PATCH v3 39/41] x86/paravirt: Move using_native_sched_clock() stub
 into timer.h*

Now that timer.h ended up with CONFIG_PARAVIRT #ifdeffery anyways, move the
PARAVIRT=n using_native_sched_clock() stub into timer.h as a "free"
optimization.

No functional change intended.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/timer.h | 5 +++--
 arch/x86/kernel/tsc.c        | 2 --
 2 files changed, 3 insertions(+), 4 deletions(-)

diff --git a/arch/x86/include/asm/timer.h b/arch/x86/include/asm/timer.h
index ab1271bd9c3b..d8cb9c84f2c7 100644
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
 				      void (*save)(void), void (*restore)(void),
 				      void (*start_secondary));
@@ -27,6 +27,7 @@ static __always_inline void paravirt_set_sched_clock(u64 (*func)(void),
 void paravirt_sched_clock_start_secondary(void);
 #else
 static inline void paravirt_sched_clock_start_secondary(void) { }
+static inline bool using_native_sched_clock(void) { return true; }
 #endif
 
 /*
diff --git a/arch/x86/kernel/tsc.c b/arch/x86/kernel/tsc.c
index f78e86494dec..1b569954ae5e 100644
--- a/arch/x86/kernel/tsc.c
+++ b/arch/x86/kernel/tsc.c
@@ -316,8 +316,6 @@ int __init __paravirt_set_sched_clock(u64 (*func)(void), bool stable,
 }
 #else
 u64 sched_clock_noinstr(void) __attribute__((alias("native_sched_clock")));
-
-bool using_native_sched_clock(void) { return true; }
 #endif
 
 notrace u64 sched_clock(void)

---

## [41] Sean Christopherson — 2026-05-15
*Subject: [PATCH v3 40/41] x86/tsc: Add standalone helper for getting CPU
 frequency from CPUID*

Extract the guts of cpu_khz_from_cpuid() to a standalone helper that
doesn't restrict the usage to Intel CPUs.  This will allow sharing the
core logic with kvmclock, as (a) CPUID.0x16 may be enumerated alongside
kvmclock, and (b) KVM generally doesn't restrict CPUID based on vendor.

No functional change intended.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/tsc.h |  1 +
 arch/x86/kernel/tsc.c      | 37 +++++++++++++++++++++++--------------
 2 files changed, 24 insertions(+), 14 deletions(-)

diff --git a/arch/x86/include/asm/tsc.h b/arch/x86/include/asm/tsc.h
index f458be688512..c145f5707b52 100644
--- a/arch/x86/include/asm/tsc.h
+++ b/arch/x86/include/asm/tsc.h
@@ -91,6 +91,7 @@ struct cpuid_tsc_info {
 };
 extern int cpuid_get_tsc_info(struct cpuid_tsc_info *info);
 extern int cpuid_get_tsc_freq(struct cpuid_tsc_info *info);
+extern int cpuid_get_cpu_freq(unsigned int *cpu_khz);
 
 extern void tsc_early_init(void);
 extern void tsc_init(void);
diff --git a/arch/x86/kernel/tsc.c b/arch/x86/kernel/tsc.c
index 1b569954ae5e..745fa2052c74 100644
--- a/arch/x86/kernel/tsc.c
+++ b/arch/x86/kernel/tsc.c
@@ -719,6 +719,24 @@ int cpuid_get_tsc_freq(struct cpuid_tsc_info *info)
 	return 0;
 }
 
+int cpuid_get_cpu_freq(unsigned int *cpu_khz)
+{
+	unsigned int eax_base_mhz, ebx, ecx, edx;
+
+	*cpu_khz = 0;
+
+	if (boot_cpu_data.cpuid_level < CPUID_LEAF_FREQ)
+		return -ENOENT;
+
+	cpuid(CPUID_LEAF_FREQ, &eax_base_mhz, &ebx, &ecx, &edx);
+
+	if (!eax_base_mhz)
+		return -ENOENT;
+
+	*cpu_khz = eax_base_mhz * 1000;
+	return 0;
+}
+
 /**
  * native_calibrate_tsc - determine TSC frequency
  * Determine TSC frequency via CPUID, else return 0.
@@ -754,13 +772,8 @@ unsigned long native_calibrate_tsc(void)
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
+	if (!info.crystal_khz && !cpuid_get_cpu_freq(&cpu_khz))
+		info.crystal_khz = cpu_khz * info.denominator / info.numerator;
 
 	if (!info.crystal_khz)
 		return 0;
@@ -787,19 +800,15 @@ unsigned long native_calibrate_tsc(void)
 
 static unsigned long cpu_khz_from_cpuid(void)
 {
-	unsigned int eax_base_mhz, ebx_max_mhz, ecx_bus_mhz, edx;
+	unsigned int cpu_khz;
 
 	if (boot_cpu_data.x86_vendor != X86_VENDOR_INTEL)
 		return 0;
 
-	if (boot_cpu_data.cpuid_level < CPUID_LEAF_FREQ)
+	if (cpuid_get_cpu_freq(&cpu_khz))
 		return 0;
 
-	eax_base_mhz = ebx_max_mhz = ecx_bus_mhz = edx = 0;
-
-	cpuid(CPUID_LEAF_FREQ, &eax_base_mhz, &ebx_max_mhz, &ecx_bus_mhz, &edx);
-
-	return eax_base_mhz * 1000;
+	return cpu_khz;
 }
 
 /*

---

## [42] Sean Christopherson — 2026-05-15
*Subject: [PATCH v3 41/41] x86/kvmclock: Get CPU base frequency from CPUID when
 it's available*

If CPUID.0x16 is present and valid, use the CPU frequency provided by
CPUID instead of assuming that the virtual CPU runs at the same
frequency as TSC and/or kvmclock.  Back before constant TSCs were a
thing, treating the TSC and CPU frequencies as one and the same was
somewhat reasonable, but now it's nonsensical, especially if the
hypervisor explicitly enumerates the CPU frequency.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kernel/kvmclock.c | 16 +++++++++++++++-
 1 file changed, 15 insertions(+), 1 deletion(-)

diff --git a/arch/x86/kernel/kvmclock.c b/arch/x86/kernel/kvmclock.c
index 62c8ea2e6769..7607920ae386 100644
--- a/arch/x86/kernel/kvmclock.c
+++ b/arch/x86/kernel/kvmclock.c
@@ -190,6 +190,20 @@ void kvmclock_cpu_action(enum kvm_guest_cpu_action action)
 	}
 }
 
+static unsigned long kvm_get_cpu_khz(void)
+{
+	unsigned int cpu_khz;
+
+	/*
+	 * Prefer CPUID over kvmclock when possible, as the base CPU frequency
+	 * isn't necessarily the same as the kvmlock "TSC" frequency.
+	 */
+	if (!cpuid_get_cpu_freq(&cpu_khz))
+		return cpu_khz;
+
+	return pvclock_tsc_khz(this_cpu_pvti());
+}
+
 /*
  * If we don't do that, there is the possibility that the guest
  * will calibrate under heavy load - thus, getting a lower lpj -
@@ -434,7 +448,7 @@ void __init kvmclock_init(void)
 		kvm_sched_clock_init(stable);
 	}
 
-	tsc_register_calibration_routines(kvm_get_tsc_khz, kvm_get_tsc_khz,
+	tsc_register_calibration_routines(kvm_get_tsc_khz, kvm_get_cpu_khz,
 					  tsc_properties);
 
 	x86_platform.get_wallclock = kvm_get_wallclock;

---

## [43] Paolo Bonzini — 2026-05-16
*Subject: Re: [PATCH v3 40/41] x86/tsc: Add standalone helper for getting CPU
 frequency from CPUID*

On 5/15/26 21:19, Sean Christopherson wrote:
> Extract the guts of cpu_khz_from_cpuid() to a standalone helper that
> doesn't restrict the usage to Intel CPUs.  This will allow sharing the

Even for native there's no real reason to restrict to Intel, I think. 
native_calibrate_tsc() only limits itself because historically (prior to 
commit 604dc9170f24, "x86/tsc: Use CPUID.0x16 to calculate missing 
crystal frequency", 2019-05-09) it used a hardcoded table of crystal 
frequencies.

Of course paranoia applies, but for virtualization, if the leaf exists 
there is no reason not to trust it.

Thanks,

Paolo

> No functional change intended.
>

---

## [44] Sean Christopherson — 2026-05-18
*Subject: Re: [PATCH v3 00/41] x86: Try to wrangle PV clocks vs. TSC*

On Fri, May 15, 2026, Sean Christopherson wrote:
> Dave/Thomas/Peter/Boris, what's the going rate for bribes to take something
> like this through the tip tree?  

FYI, don't bother reviewing this version.  Sashiko found several glaring flaws,
but I just realized that sashiko-bot's emails are only being sent to myself and
linux-hyperv@vger.kernel.org.  I'll make sure to highlight the changes in the
next version.

In the meantime, Sashiko's feedback is archived on lore if you want to see me
get torched by AI :-)

---

## [45] Woodhouse, David — 2026-05-18
*Subject: Re: [PATCH v3 02/41] x86/tsc: Add helper to register CPU and TSC freq
 calibration routines*

On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> 
> --- a/arch/x86/xen/time.c

xen_tsc_khz() doesn't use CPUID but really *should*.

Care to pull in
https://lore.kernel.org/all/20260509224824.3264567-31-dwmw2@infradead.org/
to your next round please?

(Without the misplaced changes in kvm/x86.c that should have been in
two different prior commits, and are now folded into those correctly in
my kvmclock5 branch ready for the next posting of that).

I'll drop that patch, and the similar x86/kvm one which you *have*
already taken in this series, from my next posting.

Thanks.





Amazon Development Centre (London) Ltd. Registered in England and Wales with registration number 04543232 with its registered office at 1 Principal Place, Worship Street, London EC2A 2FA, United Kingdom.

---

## [46] David Woodhouse — 2026-05-19
*Subject: Re: [PATCH v3 00/41] x86: Try to wrangle PV clocks vs. TSC*

On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> Dave/Thomas/Peter/Boris, what's the going rate for bribes to take something
> like this through the tip tree?

I booted this in qemu with -cpu host,+invtsc,+vmware-cpuid-freq

I was expecting to see it eschew the kvmclock and use *only* the TSC.
Is there even any need for 'tsc-early' given that it's *told* the TSC
frequency in CPUID? Shouldn't it have detected that the TSC is known
before init_tsc_clocksource() runs?

And then it even spent some time at boot actually using the kvmclock as
clocksource... when ideally I don't think it would even have *enabled*
it at all?

[    0.000000] clocksource: kvm-clock: mask: 0xffffffffffffffff max_cycles: 0x1cd42e4dffb, max_idle_ns: 881590591483 ns
[    0.000000] tsc: Detected 2400.000 MHz processor
[    0.008205] TSC deadline timer available
[    0.008270] clocksource: refined-jiffies: mask: 0xffffffff max_cycles: 0xffffffff, max_idle_ns: 1910969940391419 ns
[    0.159085] clocksource: hpet: mask: 0xffffffff max_cycles: 0xffffffff, max_idle_ns: 19112604467 ns
[    0.164074] clocksource: tsc-early: mask: 0xffffffffffffffff max_cycles: 0x22983777dd9, max_idle_ns: 440795300422 ns
[    0.229087] clocksource: jiffies: mask: 0xffffffff max_cycles: 0xffffffff, max_idle_ns: 1911260446275000 ns
[    0.337095] clocksource: Switched to clocksource kvm-clock
[    0.345246] clocksource: acpi_pm: mask: 0xffffff max_cycles: 0xffffff, max_idle_ns: 2085701024 ns
[    0.356201] clocksource: tsc: mask: 0xffffffffffffffff max_cycles: 0x22983777dd9, max_idle_ns: 440795300422 ns
[    0.360560] clocksource: Switched to clocksource tsc

---

## [47] Sean Christopherson — 2026-05-20
*Subject: Re: [PATCH v3 02/41] x86/tsc: Add helper to register CPU and TSC freq
 calibration routines*

On Mon, May 18, 2026, David Woodhouse wrote:
> On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> > 

Ya, will do.  What's one more patch...

---

## [48] Sean Christopherson — 2026-05-20
*Subject: Re: [PATCH v3 00/41] x86: Try to wrangle PV clocks vs. TSC*

On Tue, May 19, 2026, David Woodhouse wrote:
> On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> > Dave/Thomas/Peter/Boris, what's the going rate for bribes to take something

Yeah, that's definitely the ideal state.  And I had all the same expectations and
observations as you when digging in and testing this.  But unless this series
makes things worse, I want punt on achieving the ideal state for the moment, as
it's proving to be a big lift just to get to a not-awful state.

> [    0.000000] clocksource: kvm-clock: mask: 0xffffffffffffffff max_cycles: 0x1cd42e4dffb, max_idle_ns: 881590591483 ns
> [    0.000000] tsc: Detected 2400.000 MHz processor

---

## [49] David Woodhouse — 2026-05-20
*Subject: Re: [PATCH v3 00/41] x86: Try to wrangle PV clocks vs. TSC*

On Wed, 2026-05-20 at 10:59 -0700, Sean Christopherson wrote:
> 
> > And then it even spent some time at boot actually using the kvmclock as

Ack. Just checking my understanding was correct. Baby steps... 40 patches at a time :)

---

## [50] David Woodhouse — 2026-05-20
*Subject: Re: [PATCH v3 40/41] x86/tsc: Add standalone helper for getting CPU
 frequency from CPUID*

On Sat, 2026-05-16 at 09:42 +0200, Paolo Bonzini wrote:
> On 5/15/26 21:19, Sean Christopherson wrote:
> > Extract the guts of cpu_khz_from_cpuid() to a standalone helper that

Agreed.

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>

---

## [51] David Woodhouse — 2026-05-20
*Subject: Re: [PATCH v3 41/41] x86/kvmclock: Get CPU base frequency from
 CPUID when it's available*

On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> If CPUID.0x16 is present and valid, use the CPU frequency provided by
> CPUID instead of assuming that the virtual CPU runs at the same

I'm fine with this in principle but shouldn't the fallback be calling
kvm_get_tsc_khz() instead of directly calling pvclock_tsc_khz()?

---

## [52] David Woodhouse — 2026-05-20
*Subject: Re: [PATCH v3 01/41] x86/tsc: Add a standalone helpers for getting
 TSC info from CPUID.0x15*

On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> Extract retrieval of TSC frequency information from CPUID into standalone
> helpers so that TDX guest support can reuse the logic.  Provide a version

"Opportunistically" ? Now that looks wrong too... 

> No functional change intended.
> 

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>

---

## [53] David Woodhouse — 2026-05-20
*Subject: Re: [PATCH v3 02/41] x86/tsc: Add helper to register CPU and TSC
 freq calibration routines*

On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> Add a helper to register non-native, i.e. PV and CoCo, CPU and TSC
> frequency calibration routines.  This will allow consolidating handling

Mildly concerned that we might want to support multiple options — does
it have CPUID 0x15? Does it have 0x40000x10? Does it have a pvclock?
There are various permutations of those which are perhaps best handled
by *trying* each one, in some order, and populating a struct with the
answers?

But on the basis that perfect is the enemy of good,

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>

> diff --git a/arch/x86/kernel/kvmclock.c b/arch/x86/kernel/kvmclock.c
> index b5991d53fc0e..e9e7394140dd 100644

Can we move those (and maybe everything in the context there too) up
*before* the check for no-kvmclock at the top of the function? Probably
in a separate patch.

---

## [54] Sean Christopherson — 2026-05-20
*Subject: Re: [PATCH v3 41/41] x86/kvmclock: Get CPU base frequency from CPUID
 when it's available*

On Wed, May 20, 2026, David Woodhouse wrote:
> On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> > If CPUID.0x16 is present and valid, use the CPU frequency provided by

Oh, yeah, for this patch, definitely yes, so that there's no side effects.  The
question really should be answered in the context of "x86/kvmclock: Obtain TSC
frequency from CPUID if present", which subtly impacts the CPU frequency, but I
think the answer is "yes" there as well.

---

## [55] David Woodhouse — 2026-05-20
*Subject: Re: [PATCH v3 03/41] x86/sev: Mark TSC as reliable when configuring
 Secure TSC*

On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> Move the code to mark the TSC as reliable from sme_early_init() to
> snp_secure_tsc_init().  The only reader of TSC_RELIABLE is the aptly


Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>

---

## [56] David Woodhouse — 2026-05-20
*Subject: Re: [PATCH v3 04/41] x86/sev: Move check for SNP Secure TSC support
 to tsc_early_init()*

On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> Move the check on having a Secure TSC to the common tsc_early_init() so
> that it's obvious that having a Secure TSC is conditional, and to prepare

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>

---

## [57] David Woodhouse — 2026-05-20
*Subject: Re: [PATCH v3 05/41] x86/tdx: Override PV calibration routines with
 CPUID-based calibration*

On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> When running as a TDX guest, explicitly override the TSC frequency
> calibration routine with CPUID-based calibration instead of potentially

I don't much like stuffing the lapic_timer_period... but I'll give you
'least awful option'. For now.

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>

---

## [58] David Woodhouse — 2026-05-20
*Subject: Re: [PATCH v3 06/41] x86/acrn: Mark TSC frequency as known when
 using ACRN for calibration*

On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> Mark the TSC frequency as known when using ACRN's PV CPUID information.
> Per commit 81a71f51b89e ("x86/acrn: Set up timekeeping") and common sense,

I'd feel slightly happier doing that from within acrn_get_tsc_khz()
itself.... which I note is 'static inline'. I'm vaguely surprised that
even builds (although it does). Probably nicer to move it explicitly
out of line in acrn.c though.

Most of that should be a comment on patch  2 of the series, I guess?

---

## [59] Sean Christopherson — 2026-05-20
*Subject: Re: [PATCH v3 02/41] x86/tsc: Add helper to register CPU and TSC freq
 calibration routines*

On Wed, May 20, 2026, David Woodhouse wrote:
> On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> > diff --git a/arch/x86/kernel/kvmclock.c b/arch/x86/kernel/kvmclock.c

Oof, I was going to say "no", but disabling kvmclock is exactly the workaround
I've told people to use to get the kernel to use the TSC instead of kvmclock.

> Probably in a separate patch.

Ya.  I think this?

diff --git a/arch/x86/kernel/kvmclock.c b/arch/x86/kernel/kvmclock.c
index 08ee4bc304c8..92a1ebf31e4d 100644
--- a/arch/x86/kernel/kvmclock.c
+++ b/arch/x86/kernel/kvmclock.c
@@ -27,6 +27,7 @@ static int kvmclock_vsyscall __initdata = 1;
 static int msr_kvm_system_time __ro_after_init;
 static int msr_kvm_wall_clock __ro_after_init;
 static u64 kvm_sched_clock_offset __ro_after_init;
+static unsigned int kvm_tsc_khz_cpuid __ro_after_init;
 
 static int __init parse_no_kvmclock(char *arg)
 {
@@ -207,7 +208,7 @@ static unsigned long kvm_get_tsc_khz(void)
                lapic_timer_period = apic_khz * 1000 / HZ;
 #endif
 
-       return kvm_para_tsc_khz() ? : pvclock_tsc_khz(this_cpu_pvti());
+       return kvm_tsc_khz_cpuid ? : pvclock_tsc_khz(this_cpu_pvti());
 }
 
 static unsigned long kvm_get_cpu_khz(void)
@@ -387,9 +388,39 @@ void __init kvmclock_init(void)
        enum tsc_properties tsc_properties = TSC_FREQUENCY_KNOWN;
        bool stable = false;
 
-       if (!kvm_para_available() || !kvmclock)
+       if (!kvm_para_available())
                return;
 
+       /*
+        * If the TSC counts at a constant frequency across P/T states, counts
+        * in deep C-states, and the TSC hasn't been marked unstable, treat the
+        * TSC reliable, as guaranteed by KVM.  Note, the TSC unstable check
+        * exists purely to honor the TSC being marked unstable via command
+        * line, any runtime detection of an unstable will happen after this.
+        */
+       if (boot_cpu_has(X86_FEATURE_CONSTANT_TSC) &&
+           boot_cpu_has(X86_FEATURE_NONSTOP_TSC) &&
+           !check_tsc_unstable())
+               tsc_properties = TSC_FREQ_KNOWN_AND_RELIABLE;
+
+       kvm_tsc_khz_cpuid = kvm_para_tsc_khz();
+
+       /*
+        * If provided, use the TSC (and APIC bus) frequency provided in KVM's
+        * PV CPUID leaf even if kvmclock itself is disabled via command line.
+        * The PV CPUID information isn't dependent on kvmclock in any way, and
+        * in fact using the precise information is *more* important when the
+        * user has explicitly disabled kvmclock to force the kernel to use the
+        * TSC as its clocksource.
+        */
+       if (!kvmclock) {
+               if (kvm_tsc_khz_cpuid)
+                       tsc_register_calibration_routines(kvm_get_tsc_khz,
+                                                         kvm_get_cpu_khz,
+                                                         tsc_properties);
+               return;
+       }
+
        if (kvm_para_has_feature(KVM_FEATURE_CLOCKSOURCE2)) {
                msr_kvm_system_time = MSR_KVM_SYSTEM_TIME_NEW;
                msr_kvm_wall_clock = MSR_KVM_WALL_CLOCK_NEW;
@@ -424,21 +455,14 @@ void __init kvmclock_init(void)
        }
 
        /*
-        * If the TSC counts at a constant frequency across P/T states, counts
-        * in deep C-states, and the TSC hasn't been marked unstable, prefer
-        * the TSC over kvmclock for sched_clock and drop kvmclock's rating so
-        * that TSC is chosen as the clocksource.  Note, the TSC unstable check
-        * exists purely to honor the TSC being marked unstable via command
-        * line, any runtime detection of an unstable will happen after this.
+        * If the TSC is reliable (see above), prefer the TSC over kvmclock for
+        * sched_clock and drop kvmclock's rating so that TSC is chosen as the
+        * clocksource.
         */
-       if (boot_cpu_has(X86_FEATURE_CONSTANT_TSC) &&
-           boot_cpu_has(X86_FEATURE_NONSTOP_TSC) &&
-           !check_tsc_unstable()) {
+       if (tsc_properties & TSC_RELIABLE)
                kvm_clock.rating = 299;
-               tsc_properties = TSC_FREQ_KNOWN_AND_RELIABLE;
-       } else {
+       else
                kvm_sched_clock_init(stable);
-       }
 
        tsc_register_calibration_routines(kvm_get_tsc_khz, kvm_get_cpu_khz,
                                          tsc_properties);

---

## [60] Sean Christopherson — 2026-05-20
*Subject: Re: [PATCH v3 06/41] x86/acrn: Mark TSC frequency as known when using
 ACRN for calibration*

On Wed, May 20, 2026, David Woodhouse wrote:
> On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> > Mark the TSC frequency as known when using ACRN's PV CPUID information.

Ya, though as you note below, this is really a comment on the overall series.

Waiting to set the cap until the calibration routine is actually run does prevent
the case where the something registers a calibration routine, but its routine is
never run.

However, because the cap is sticky, it doesn't handle the scenario where its
routine _does_ run, but the kernel ultimately throws away its calibration in favor
of something else.

Further complicating things is that ~half of the paravirt flows already force set
caps before their routines are invoked:

  snp_secure_tsc_init(), jailhouse_init_platform(), ms_hyperv_init_platform(),
  vmware_set_capabilities()

Rather than trying to convince everyone that waiting is better, despite that
approach still being flawed, I chose to handle this by ensuring that once the TSC
is marked known and/or reliable, the kernel won't replace the calibration routine
with a "lesser" source:

  x86/tsc: Rejects attempts to override TSC calibration with lesser routine

That doesn't completely prevent the kernel from being stupid, but it should prevent
both the case where X's routine is registered but never run, as well as the case
where it's run but ultimately ignored.

> which I note is 'static inline'. I'm vaguely surprised that even builds
> (although it does).

Heh, KVM x86 (in the host) does stupid things like this too.  E.g. kvm_pdptr_read()
is a static inline, but then wired up as a function pointer in three different
places.

> Probably nicer to move it explicitly out of line in acrn.c though.
>

---

## [61] David Woodhouse — 2026-05-20
*Subject: Re: [PATCH v3 02/41] x86/tsc: Add helper to register CPU and TSC
 freq calibration routines*

On Wed, 2026-05-20 at 13:44 -0700, Sean Christopherson wrote:
> 
> +       /*
    { 
> +               tsc_properties = TSC_FREQ_KNOWN_AND_RELIABLE;

    kvmclock = 0; /* Why use it if the TSC works? The kvmclock exists
                     *purely* to work around a TSC which *doesn't*
                     have those properties checked above. */
    }

I was going to say PVCLOCK_TSC_STABLE_BIT, and maybe we should check
that *too* for paranoia? But hopefully the checks you have above are
equivalent?

> +
> +       kvm_tsc_khz_cpuid = kvm_para_tsc_khz();


Regardless of the above, why not just register these here
unconditionally, and remove the later call that does the same?

---

## [62] David Woodhouse — 2026-05-20
*Subject: Re: [PATCH v3 07/41] clocksource: hyper-v: Register sched_clock
 save/restore iff it's necessary*

On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> Register the Hyper-V reference counter (refcounter) callbacks for saving
> and restoring its PV sched_clock, if and only if the refcounter is

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>

---

## [63] David Woodhouse — 2026-05-20
*Subject: Re: [PATCH v3 08/41] clocksource: hyper-v: Drop wrappers to
 sched_clock save/restore helpers*

On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> Now that all of the Hyper-V reference counter sched_clock code is located
> in a single file, drop the superfluous wrappers for the save/restore flows.

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>

---

## [64] David Woodhouse — 2026-05-20
*Subject: Re: [PATCH v3 09/41] clocksource: hyper-v: Don't save/restore TSC
 offset when using HV sched_clock*

On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> Now that Hyper-V overrides the sched_clock save/restore hooks if and only
> sched_clock itself is set to the Hyper-V reference counter, drop the

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>

---

## [65] Sean Christopherson — 2026-05-20
*Subject: Re: [PATCH v3 02/41] x86/tsc: Add helper to register CPU and TSC freq
 calibration routines*

On Wed, May 20, 2026, David Woodhouse wrote:
> On Wed, 2026-05-20 at 13:44 -0700, Sean Christopherson wrote:
> > 

kvmclock still provides SYSTEM_TIME and WALL_CLOCK :-/

>     }
> 

No? PVCLOCK_TSC_STABLE is property of kvmclock more than it's a property of the
TSC itself.  And for the no-kvmclock case, we most definitely don't want to setup
kvmclock just to query that flag.

> But hopefully the checks you have above are equivalent?

They aren't as paranoid, but if the host enumerates CONSTANT+NONSTOP TSC despite
KVM-the-host not being able to advertise PVCLOCK_TSC_STABLE_BIT, then the VMM done
messed up.

> > +
> > +       kvm_tsc_khz_cpuid = kvm_para_tsc_khz();

Because if kvmclock=n, it's only safe to call kvm_get_tsc_khz() if kvm_tsc_khz_cpuid
is non-zero, other wise the "else" path will hit a NULL pointer deref when trying
to get the frequency from the PV clock struct:

	return kvm_tsc_khz_cpuid ? : pvclock_tsc_khz(this_cpu_pvti());

---

## [66] David Woodhouse — 2026-05-20
*Subject: Re: [PATCH v3 02/41] x86/tsc: Add helper to register CPU and TSC
 freq calibration routines*

On Wed, 2026-05-20 at 14:33 -0700, Sean Christopherson wrote:
> On Wed, May 20, 2026, David Woodhouse wrote:
> > On Wed, 2026-05-20 at 13:44 -0700, Sean Christopherson wrote:

Um, SYSTEM_TIME *is* the kvmclock of which we speak, isn't it?

WALL_CLOCK is something else, and I guess we should still consume that,
yes.

> 
> > > +

Ah, right. Thanks. Ick though :)

---

## [67] David Woodhouse — 2026-05-20
*Subject: Re: [PATCH v3 10/41] x86/kvmclock: Setup kvmclock for secondary
 CPUs iff CONFIG_SMP=y*

On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> Gate kvmclock's secondary CPU code on CONFIG_SMP, not CONFIG_X86_LOCAL_APIC.
> Originally, kvmclock piggybacked PV APIC ops to setup secondary CPUs.

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>

---

## [68] David Woodhouse — 2026-05-20
*Subject: Re: [PATCH v3 11/41] x86/kvm: Don't disable kvmclock on BSP in
 syscore_suspend()*

On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> Don't disable kvmclock on the BSP during syscore_suspend(), as the BSP's
> clock is NOT restored during syscore_resume(), but is instead restored

The work that Dongli and I have been doing elsewhere makes me want to
phrase that last sentence far more judgmentally, as the kvmclock
absolutely should *not* be randomly drifting over time without good
reason, and what was written to it earlier really *ought* to still be
valid.

But OK :)

> Plumb in an "action" to KVM-as-a-guest and kvmclock code in preparation
> for additional cleanups to kvmclock's suspend/resume logic.

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>

---

## [69] David Woodhouse — 2026-05-20
*Subject: Re: [PATCH v3 12/41] x86/paravirt: Remove unnecessary PARAVIRT=n
 stub for paravirt_set_sched_clock()*

On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> Remove the unnecessary paravirt_set_sched_clock() stub for PARAVIRT=n, as
> all callers are gated by PARAVIRT=y.  Eliminating the stub will avoid a

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>

---

## [70] David Woodhouse — 2026-05-20
*Subject: Re: [PATCH v3 13/41] x86/paravirt: Move handling of unstable PV
 clocks into paravirt_set_sched_clock()*

On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> Move the handling of unstable PV clocks, of which kvmclock is the only
> example, into paravirt_set_sched_clock().  This will allow modifying

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>

> -void paravirt_set_sched_clock(u64 (*func)(void));
> +void __paravirt_set_sched_clock(u64 (*func)(void), bool stable);

One of the few things I actually like about C++ is default arguments...

---

## [71] David Woodhouse — 2026-05-20
*Subject: Re: [PATCH v3 14/41] x86/kvmclock: Move sched_clock save/restore
 helpers up in kvmclock.c*

On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> Move kvmclock's sched_clock save/restore helper "up" so that they can
> (eventually) be referenced by kvm_sched_clock_init().

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>

---

## [72] David Woodhouse — 2026-05-20
*Subject: Re: [PATCH v3 15/41] x86/xen/time: Nullify x86_platform's
 sched_clock save/restore hooks*

On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> Nullify the x86_platform sched_clock save/restore hooks when setting up
> Xen's PV clock to make it somewhat obvious the hooks aren't used when

Hm. Xen HVM guests *do* use a standard ACPI S4 hibernation flow.

Does that need testing?

> ---
>  arch/x86/xen/time.c | 6 ++++++

---

## [73] David Woodhouse — 2026-05-20
*Subject: Re: [PATCH v3 16/41] x86/vmware: Nullify save/restore hooks when
 using VMware's sched_clock*

On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> Nullify the sched_clock save/restore hooks when using VMware's version of
> sched_clock.  This will allow extending paravirt_set_sched_clock() to set

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>

---

## [74] David Woodhouse — 2026-05-20
*Subject: Re: [PATCH v3 17/41] x86/tsc: WARN if TSC sched_clock save/restore
 used with PV sched_clock*

On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> Now that all PV clocksources override the sched_clock save/restore hooks
> when overriding sched_clock, WARN if the "default" TSC hooks are invoked

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>

---

## [75] Woodhouse, David — 2026-05-20
*Subject: Re: [PATCH v3 18/41] x86/paravirt: Pass sched_clock save/restore
 helpers during registration*

On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> Pass in a PV clock's save/restore helpers when configuring sched_clock
> instead of relying on each PV clock to manually set the save/restore hooks.

Nice!

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>

> --- a/arch/x86/xen/time.c
> +++ b/arch/x86/xen/time.c


Same deal here as with kvmclock, FWIW. If the TSC is viable, then it's
the better choice. 

Especially now there's a significant chance that a "Xen guest" is
actually running under KVM. Xen never screwed its pvclock up quite as
much as KVM did :)




Amazon Development Centre (London) Ltd. Registered in England and Wales with registration number 04543232 with its registered office at 1 Principal Place, Worship Street, London EC2A 2FA, United Kingdom.

---

## [76] David Woodhouse — 2026-05-20
*Subject: Re: [PATCH v3 19/41] x86/kvmclock: Move kvm_sched_clock_init() down
 in kvmclock.c*

On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> Move kvm_sched_clock_init() "down" so that it can reference the global
> kvm_clock structure without needing a forward declaration.

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>

---

## [77] David Woodhouse — 2026-05-20
*Subject: Re: [PATCH v3 20/41] x86/xen/time: Mark
 xen_setup_vsyscall_time_info() as __init*

On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> Annotate xen_setup_vsyscall_time_info() as being used only during kernel
> initialization; it's called only by xen_time_init(), which is already

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>

---

## [78] Woodhouse, David — 2026-05-20
*Subject: Re: [PATCH v3 21/41] x86/pvclock: Mark setup helpers and related
 various as __init/__ro_after_init*

On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> Now that Xen PV clock and kvmclock explicitly do setup only during init,
> tag the common PV clock flags/vsyscall variables and their mutators with

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>




Amazon Development Centre (London) Ltd. Registered in England and Wales with registration number 04543232 with its registered office at 1 Principal Place, Worship Street, London EC2A 2FA, United Kingdom.

---

## [79] David Woodhouse — 2026-05-20
*Subject: Re: [PATCH v3 22/41] x86/pvclock: WARN if pvclock's valid_flags are
 overwritten*

On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> WARN if the common PV clock valid_flags are overwritten; all PV clocks
> expect that they are the one and only PV clock, i.e. don't guard against

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>

---

## [80] David Woodhouse — 2026-05-20
*Subject: Re: [PATCH v3 23/41] x86/kvmclock: Refactor handling of
 PVCLOCK_TSC_STABLE_BIT during kvmclock_init()*

On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> Clean up the setting of PVCLOCK_TSC_STABLE_BIT during kvmclock init to
> make it somewhat obvious that pvclock_read_flags() must be called *after*

> Signed-off-by: Sean Christopherson <seanjc@google.com>

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>

---

## [81] David Woodhouse — 2026-05-20
*Subject: Re: [PATCH v3 24/41] timekeeping: Resume clocksources before
 reading persistent clock*

On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> When resuming timekeeping after suspend, restore clocksources prior to
> reading the persistent clock.  Paravirt clocks, e.g. kvmclock, tie the

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>

---

## [82] David Woodhouse — 2026-05-20
*Subject: Re: [PATCH v3 15/41] x86/xen/time: Nullify x86_platform's
 sched_clock save/restore hooks*

On Wed, 2026-05-20 at 23:11 +0100, David Woodhouse wrote:
> On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> > Nullify the x86_platform sched_clock save/restore hooks when setting up

Ah, this looks as sane as we can expect.

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>

> 
> > ---

---

## [83] David Woodhouse — 2026-05-21
*Subject: Re: [PATCH v3 25/41] x86/kvmclock: Hook clocksource.suspend/resume
 when kvmclock isn't sched_clock*

On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> Save/restore kvmclock across suspend/resume via clocksource hooks when
> kvmclock isn't being used for sched_clock.  This will allow using kvmclock

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>

---

## [84] David Woodhouse — 2026-05-21
*Subject: Re: [PATCH v3 25/41] x86/kvmclock: Hook clocksource.suspend/resume
 when kvmclock isn't sched_clock*

On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> Save/restore kvmclock across suspend/resume via clocksource hooks when
> kvmclock isn't being used for sched_clock.  This will allow using kvmclock

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>

---

## [85] David Woodhouse — 2026-05-21
*Subject: Re: [PATCH v3 26/41] x86/kvmclock: WARN if wall clock is read while
 kvmclock is suspended*

On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> WARN if kvmclock is still suspended when its wallclock is read, i.e. when
> the kernel reads its persistent clock.  The wallclock subtly depends on

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>


Although I still hate the whole KVM wallclock thing, as the kvmclock
itself is monotonic_raw, so adding that to the wallclock epoch is kind
of wrong.

Maybe the host should updated the wallclock occasionally to keep it up
to date...


Or maybe the guest should prefer the KVM_HC_CLOCK_PAIRING hypercall if
it exists, over kvm-wallclock.

---

## [86] David Woodhouse — 2026-05-21
*Subject: Re: [PATCH v3 27/41] x86/kvmclock: Enable kvmclock on APs during
 onlining if kvmclock isn't sched_clock*

On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> In anticipation of making x86_cpuinit.early_percpu_clock_init(), i.e.
> kvm_setup_secondary_clock(), a dedicated sched_clock hook that will be

That's a hard word to type, isn't it?

> Opportunstically WARN in kvmclock_{suspend,resume}() to harden against
> future bugs.

So is that :)

> Signed-off-by: Sean Christopherson <seanjc@google.com>

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>

---

## [87] David Woodhouse — 2026-05-21
*Subject: Re: [PATCH v3 28/41] x86/paravirt: Mark
 __paravirt_set_sched_clock() as __init*

On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> Annotate __paravirt_set_sched_clock() as __init, and make its wrapper
> __always_inline to ensure sanitizers don't result in a non-inline version

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>

---

## [88] David Woodhouse — 2026-05-21
*Subject: Re: [PATCH v3 29/41] x86/paravirt: Plumb a return code into
 __paravirt_set_sched_clock()*

On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> Add a return code to __paravirt_set_sched_clock() so that the kernel can
> reject attempts to use a PV sched_clock without breaking the caller.  E.g.

Oooh... can we use this to reject the kvmclock when we have a stable
and reliable TSC even for non-CoCo guests?

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>

---

## [89] David Woodhouse — 2026-05-21
*Subject: Re: [PATCH v3 30/41] x86/paravirt: Don't use a PV sched_clock in
 CoCo guests with trusted TSC*

On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> Silently ignore attempts to switch to a paravirt sched_clock when running
> as a CoCo guest with trusted TSC.  In hand-wavy theory, a misbehaving

And kvmclock. And Xen.

Are there *any* reasons we'd use a PV sched_clock when the TSC is
usable?

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>

> ---
>  arch/x86/kernel/tsc.c | 9 +++++++++

---

## [90] Woodhouse, David — 2026-05-20
*Subject: Re: [PATCH v3 31/41] x86/tsc: Pass KNOWN_FREQ and RELIABLE as params
 to registration*

On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> Add a "tsc_properties" set of flags and use it to annotate whether the
> TSC operates at a known and/or reliable frequency when registering a

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>




Amazon Development Centre (London) Ltd. Registered in England and Wales with registration number 04543232 with its registered office at 1 Principal Place, Worship Street, London EC2A 2FA, United Kingdom.

---

## [91] David Woodhouse — 2026-05-21
*Subject: Re: [PATCH v3 32/41] x86/tsc: Rejects attempts to override TSC
 calibration with lesser routine*

On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> When registering a TSC frequency calibration routine, sanity check that
> the incoming routine is as robust as the outgoing routine, and reject the

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>

---

## [92] David Woodhouse — 2026-05-21
*Subject: Re: [PATCH v3 33/41] x86/kvmclock: Mark TSC as reliable when it's
 constant and nonstop*

On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> Mark the TSC as reliable if the hypervisor (KVM) has enumerated the TSC
> as constant and nonstop, and the admin hasn't explicitly marked the TSC

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>

---

## [93] Woodhouse, David — 2026-05-20
*Subject: Re: [PATCH v3 36/41] x86/kvmclock: Get local APIC bus frequency from
 PV CPUID Timing Info*

On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> When running as a KVM guest with kvmclock support enabled, stuff the APIC
> timer period/frequency with the local APIC bus frequency reported in

I still don't much like the way this is done inside kvm_get_tsc_khz().

We also probably ought to be looking for the timing leaf on other
hypervisors including VMware and probably Bhyve too. Should it be done
somewhere else?






Amazon Development Centre (London) Ltd. Registered in England and Wales with registration number 04543232 with its registered office at 1 Principal Place, Worship Street, London EC2A 2FA, United Kingdom.

---

## [94] David Woodhouse — 2026-05-21
*Subject: Re: [PATCH v3 37/41] x86/kvmclock: Use TSC for sched_clock if it's
 constant and non-stop*

On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> Prefer the TSC over kvmclock for sched_clock if the TSC is constant,
> nonstop, and not marked unstable via command line.  I.e. use the same

Yay! (Albeit only for sched_clock, and we should do Xen too)

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>

---

## [95] David Woodhouse — 2026-05-21
*Subject: Re: [PATCH v3 38/41] x86/paravirt: kvmclock: Setup kvmclock early
 iff it's sched_clock*

On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> Rework the seemingly generic x86_cpuinit_ops.early_percpu_clock_init hook
> into a dedicated PV sched_clock hook, as the only reason the hook exists

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>

---

## [96] David Woodhouse — 2026-05-21
*Subject: Re: [PATCH v3 39/41] x86/paravirt: Move using_native_sched_clock()
 stub into timer.h*

On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> Now that timer.h ended up with CONFIG_PARAVIRT #ifdeffery anyways, move the
> PARAVIRT=n using_native_sched_clock() stub into timer.h as a "free"

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>

---

## [97] Dongli Zhang — 2026-05-21
*Subject: Re: [PATCH v3 37/41] x86/kvmclock: Use TSC for sched_clock if it's
 constant and non-stop*

On 2026-05-15 12:19 PM, Sean Christopherson wrote:
> Prefer the TSC over kvmclock for sched_clock if the TSC is constant,
> nonstop, and not marked unstable via command line.  I.e. use the same

Has it been broken for two years because of pvclock_clocksource_read_nowd()?

Thank you very much!

Dongli Zhang

---

## [98] Sean Christopherson — 2026-05-21
*Subject: Re: [PATCH v3 27/41] x86/kvmclock: Enable kvmclock on APs during
 onlining if kvmclock isn't sched_clock*

On Thu, May 21, 2026, David Woodhouse wrote:
> On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> > In anticipation of making x86_cpuinit.early_percpu_clock_init(), i.e.

Heh, you have no idea.  I've been "this" close to creating a VIM binding for a
while, it is time...

---

## [99] Peter Zijlstra — 2026-05-21
*Subject: Re: [PATCH v3 27/41] x86/kvmclock: Enable kvmclock on APs during
 onlining if kvmclock isn't sched_clock*

On Thu, May 21, 2026 at 05:59:17AM -0700, Sean Christopherson wrote:
> On Thu, May 21, 2026, David Woodhouse wrote:
> > On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:

'z=' not good enough?

---

## [100] Sean Christopherson — 2026-05-21
*Subject: Re: [PATCH v3 27/41] x86/kvmclock: Enable kvmclock on APs during
 onlining if kvmclock isn't sched_clock*

On Thu, May 21, 2026, Peter Zijlstra wrote:
> On Thu, May 21, 2026 at 05:59:17AM -0700, Sean Christopherson wrote:
> > On Thu, May 21, 2026, David Woodhouse wrote:

You people and your fancy ways.  I'm just happy I can get in and out of the editor :-)

---

## [101] David Woodhouse — 2026-05-21
*Subject: Re: [PATCH v3 27/41] x86/kvmclock: Enable kvmclock on APs during
 onlining if kvmclock isn't sched_clock*

On Thu, 2026-05-21 at 06:38 -0700, Sean Christopherson wrote:
> On Thu, May 21, 2026, Peter Zijlstra wrote:
> > On Thu, May 21, 2026 at 05:59:17AM -0700, Sean Christopherson wrote:

I reached the peak of my vi knowledge in about 1995 when I learned that
I could log in on another terminal, kill it from there, and then set
EDITOR=emacs.

Ironically I still find myself doing that kind of thing when I'm
composing a git-send-email cover letter and decide I don't want to send
the series as-is at all. Maybe there's a way to put a poison pill in
the message (or save it unchanged?) to make git *NOT* send anything...
but I always err on the side of caution and just nuke it from orbit, or
at least from another terminal.

---

## [102] Sean Christopherson — 2026-05-21
*Subject: Re: [PATCH v3 36/41] x86/kvmclock: Get local APIC bus frequency from
 PV CPUID Timing Info*

On Wed, May 20, 2026, David Woodhouse wrote:
> On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> > When running as a KVM guest with kvmclock support enabled, stuff the APIC

Yeah, I don't like it either (understatement).  Aha!  native_calibrate_tsc() is
the oddball, all of the PV flows stuff lapic_timer_period when parsing the initial
timing info.  I'll just do that.  Blindly writing a global is all kinds of fugly,
but that's a future
problem to solve.

> We also probably ought to be looking for the timing leaf on other
> hypervisors including VMware 

VMware gets the frequency via hypercall.  Why, I have no idea.  I'll let the
VMware folks deal with that.

	eax = vmware_hypercall3(VMWARE_CMD_GETHZ, UINT_MAX, &ebx, &ecx);

> and probably Bhyve too.  Should it be done somewhere else?

I'm not opposed to that, though I don't know that it'd be a net positive. The
"hard" part of getting the info is finding the CPUID base and checking if the
leaf is available.  Unlike the native CPUID leaf, no math is necessary, and so
once the leaf is obtained, getting the frequency is trivial.

Regardless, I definitely don't want to take it on in this series. :-)

---

## [103] Sean Christopherson — 2026-05-21
*Subject: Re: [PATCH v3 29/41] x86/paravirt: Plumb a return code into __paravirt_set_sched_clock()*

On Thu, May 21, 2026, David Woodhouse wrote:
> On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> > Add a return code to __paravirt_set_sched_clock() so that the kernel can

Yes, but I would much rather "fix" kvmclock to not even attempt to register itself
as the sched_clock (which this series does).

---

## [104] Sean Christopherson — 2026-05-21
*Subject: Re: [PATCH v3 02/41] x86/tsc: Add helper to register CPU and TSC freq
 calibration routines*

On Wed, May 20, 2026, David Woodhouse wrote:
> On Fri, 2026-05-15 at 12:19 -0700, Sean Christopherson wrote:
> > Add a helper to register non-native, i.e. PV and CoCo, CPU and TSC

This has been bothering me too.

Aha!  AHA!  Idea.

... 4 hours later ...

Mhahahaahah, victory is mine!!!!

TL;DR: Overriding x86_platform_ops hooks is dumb.

To your point about making an informed decision, that's essentialy what this series
is already doing, just in a very roundabout way:

  1. x86_platform.calibrate_{cpu,tsc}() are initialized to "native" versions
  2. Hypervisor init code runs and conditionally overrides calibrate_{cpu,tsc}()
  3. CoCo init code runs and conditionally overrides calibrate_{cpu,tsc}()

So the ordering you want is already there, as is "trying" each source to some
extent, in the form of steps #2 and #3 overriding the hooks if and only if their
source of information is valid.  For all intents and purposes, the hardening I
was adding by formalizing the calibration overrides was to enforce the above ordering.

But that's obviously all but impossible to follow, _and_ it's pointless.

For every PV case, including TDX and SNP, "calibration" is simply information
retrieval, i.e. it never changes (barring broken hypervisors/firmware), and the
information is always available during early boot.

Contrast that with the pre-CPUID CPU frequency calibration, where the frequency
might change, the kernel is making a best guest based on other timekeeping sources,
and not all timekeeping sources are available during early boot.

And so overriding x86_platform.calibrate_{cpu,tsc}() for PV code is completely
unecessary, because steps #2 and #3 already know the frequency when they override
the hooks, and "success" is guaranteed, i.e. the kernel won't have to switch to a
"late" calibration flow.

If we provide x86_hyper_init hooks:

	unsigned int (*get_tsc_khz)(void);
	unsigned int (*get_cpu_khz)(void);

then we can kill off x86_platform.calibrate_{cpu,tsc}() entirely, explicitly
define the preferred ordering (user-forced => CoCo => Hypervisor => native), and
depup some of the hypervisor code.

E.g. this is what I've got for the early flow.  Testing now. 

  void __init tsc_early_init(void)
  {
	unsigned int known_cpu_khz = 0, known_tsc_khz = 0;

	if (!boot_cpu_has(X86_FEATURE_TSC))
		return;
	/* Don't change UV TSC multi-chassis synchronization */
	if (is_early_uv_system())
		return;

	if (x86_init.hyper.get_cpu_khz)
		known_cpu_khz = x86_init.hyper.get_cpu_khz();

	if (tsc_early_khz)
		known_tsc_khz = tsc_early_khz;
	else if (cc_platform_has(CC_ATTR_GUEST_SNP_SECURE_TSC))
		known_tsc_khz = snp_secure_tsc_init();
	else if (boot_cpu_has(X86_FEATURE_TDX_GUEST))
		known_tsc_khz = tdx_tsc_init();

	/*
	 * If the TSC frequency is still unknown, i.e. not provided by the user
	 * or by trusted firmware, try to get it from the hypervisor (which is
	 * untrusted when running as a CoCo guest).
	 */
	if (!known_tsc_khz && x86_init.hyper.get_tsc_khz)
		known_tsc_khz = x86_init.hyper.get_tsc_khz();

	if (known_tsc_khz)
		setup_force_cpu_cap(X86_FEATURE_TSC_KNOWN_FREQ);

	if (!determine_cpu_tsc_frequencies(true, known_cpu_khz, known_tsc_khz))
		return;
	tsc_enable_sched_clock();
  }

---

## [105] Sean Christopherson — 2026-05-21
*Subject: Re: [PATCH v3 37/41] x86/kvmclock: Use TSC for sched_clock if it's
 constant and non-stop*

On Thu, May 21, 2026, Dongli Zhang wrote:
> On 2026-05-15 12:19 PM, Sean Christopherson wrote:
> > Prefer the TSC over kvmclock for sched_clock if the TSC is constant,

Yep.  Because pvclock_clocksource_read_nowd() ignores PVCLOCK_GUEST_STOPPED, the
flag only ever gets recognized when the kernel reads WALL_CLOCK, which AFAICT
only happens at initial boot, and during suspend and resume.

---

## [106] David Woodhouse — 2026-05-21
*Subject: Re: [PATCH v3 02/41] x86/tsc: Add helper to register CPU and TSC
 freq calibration routines*

On Thu, 2026-05-21 at 13:53 -0700, Sean Christopherson wrote:
> 
> E.g. this is what I've got for the early flow.  Testing now. 

That seems reasonable. Where does the call to native_calibrate_tsc()
happen; is that from determine_cpu_tsc_frequencies()?

---

## [107] Sean Christopherson — 2026-05-21
*Subject: Re: [PATCH v3 02/41] x86/tsc: Add helper to register CPU and TSC freq
 calibration routines*

On Thu, May 21, 2026, David Woodhouse wrote:
> On Thu, 2026-05-21 at 13:53 -0700, Sean Christopherson wrote:
> > 

Yep.

static bool __init determine_cpu_tsc_frequencies(bool early,
						 unsigned int known_cpu_khz,
						 unsigned int known_tsc_khz)
{
	/* Make sure that cpu and tsc are not already calibrated */
	WARN_ON(cpu_khz || tsc_khz);

	if (early) {
		/*
		 * Early CPU calibration can only use methods that are available
		 * early in boot (obviously).
		 */
		if (known_cpu_khz)
			cpu_khz = known_cpu_khz;
		else
			cpu_khz = native_calibrate_cpu_early();
		if (known_tsc_khz)
			tsc_khz = known_tsc_khz;
		else
			tsc_khz = native_calibrate_tsc();
	} else {
		cpu_khz = pit_hpet_ptimer_calibrate_cpu();
	}

	...

---

## [108] David Woodhouse — 2026-05-21
*Subject: Re: [PATCH v3 02/41] x86/tsc: Add helper to register CPU and TSC
 freq calibration routines*

On Thu, 2026-05-21 at 14:17 -0700, Sean Christopherson wrote:
>  
> > That seems reasonable. Where does the call to

Great, thanks.

> static bool __init determine_cpu_tsc_frequencies(bool early,
> 						 unsigned int


If, after all that, we still end up in the case where we *do* have to
calibrate it against a legacy timer (which sadly IIRC is the case even
on some fairly modern AMD generations), could we round the answer?

We currently have *far* more precision than accuracy, leading to values
like 2399997kHz which change every boot (and end up being what gets
*advertised* to guests on such a host... and then unless we're careful
to avoid it, we end up trying to *scale* a different host's TSC down
from 2399998 to 2399997 for a guest which is migrated from the first
host...)

We should just fix them (e.g. to 2400000kHz) and let NTP sort them out.

Something like "round to the nearest MHz if that's within ±10PPM"?

---

## [109] Wei Liu — 2026-05-27
*Subject: Re: [PATCH v3 07/41] clocksource: hyper-v: Register sched_clock
 save/restore iff it's necessary*

On Fri, May 15, 2026 at 12:19:08PM -0700, Sean Christopherson wrote:
> Register the Hyper-V reference counter (refcounter) callbacks for saving
> and restoring its PV sched_clock, if and only if the refcounter is

Acked-by: Wei Liu <wei.liu@kernel.org>

---

## [110] Wei Liu — 2026-05-27
*Subject: Re: [PATCH v3 08/41] clocksource: hyper-v: Drop wrappers to
 sched_clock save/restore helpers*

On Fri, May 15, 2026 at 12:19:09PM -0700, Sean Christopherson wrote:
> Now that all of the Hyper-V reference counter sched_clock code is located
> in a single file, drop the superfluous wrappers for the save/restore flows.

Acked-by: Wei Liu <wei.liu@kernel.org>

---

## [111] Wei Liu — 2026-05-27
*Subject: Re: [PATCH v3 09/41] clocksource: hyper-v: Don't save/restore TSC
 offset when using HV sched_clock*

On Fri, May 15, 2026 at 12:19:10PM -0700, Sean Christopherson wrote:
> Now that Hyper-V overrides the sched_clock save/restore hooks if and only
> sched_clock itself is set to the Hyper-V reference counter, drop the

Acked-by: Wei Liu <wei.liu@kernel.org>

---
