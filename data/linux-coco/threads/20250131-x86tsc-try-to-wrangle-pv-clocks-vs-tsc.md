---
title: 'x86/tsc: Try to wrangle PV clocks vs. TSC'
date: 2025-01-31
last_reply: 2025-02-12
message_count: 42
participants: ['Sean Christopherson', 'Nikunj A Dadhania', 'Tom Lendacky', 'Michael Kelley', 'Borislav Petkov']
---

## [1] Sean Christopherson — 2025-01-31

Attempt to bring some amount of order to the PV clocks vs. TSC madness in
the kernel.  The primary goal of this series is to fix flaws with SNP
and TDX guests where a PV clock provided by the untrusted hypervisor is
used instead of the secure/trusted TSC that is controlled by trusted
firmware.

The secondary goal (last few patches) is to draft off of the SNP and TDX
changes to slightly modernize running under KVM.  Currently, KVM guests
will use TSC for clocksource, but not sched_clock.  And they ignore Intel's
CPUID-based TSC and CPU frequency enumeration, even when using the TSC
instead of kvmclock.  And if the host provides the core crystal frequency
in CPUID.0x15, then KVM guests can use that for the APIC timer period
instead of manually calibrating the frequency.

Lots more background: https://lore.kernel.org/all/20250106124633.1418972-13-nikunj@amd.com

This is all *very* lightly tested (borderline RFC).

Sean Christopherson (16):
  x86/tsc: Add a standalone helpers for getting TSC info from CPUID.0x15
  x86/tsc: Add standalone helper for getting CPU frequency from CPUID
  x86/tsc: Add helper to register CPU and TSC freq calibration routines
  x86/sev: Mark TSC as reliable when configuring Secure TSC
  x86/sev: Move check for SNP Secure TSC support to tsc_early_init()
  x86/tdx: Override PV calibration routines with CPUID-based calibration
  x86/acrn: Mark TSC frequency as known when using ACRN for calibration
  x86/tsc: Pass KNOWN_FREQ and RELIABLE as params to registration
  x86/tsc: Rejects attempts to override TSC calibration with lesser
    routine
  x86/paravirt: Move handling of unstable PV clocks into
    paravirt_set_sched_clock()
  x86/paravirt: Don't use a PV sched_clock in CoCo guests with trusted
    TSC
  x86/kvmclock: Mark TSC as reliable when it's constant and nonstop
  x86/kvmclock: Get CPU base frequency from CPUID when it's available
  x86/kvmclock: Get TSC frequency from CPUID when its available
  x86/kvmclock: Stuff local APIC bus period when core crystal freq comes
    from CPUID
  x86/kvmclock: Use TSC for sched_clock if it's constant and non-stop

 arch/x86/coco/sev/core.c        |  9 ++--
 arch/x86/coco/tdx/tdx.c         | 27 ++++++++--
 arch/x86/include/asm/paravirt.h |  7 ++-
 arch/x86/include/asm/tdx.h      |  2 +
 arch/x86/include/asm/tsc.h      | 67 +++++++++++++++++++++++++
 arch/x86/kernel/cpu/acrn.c      |  5 +-
 arch/x86/kernel/cpu/mshyperv.c  | 11 +++--
 arch/x86/kernel/cpu/vmware.c    |  9 ++--
 arch/x86/kernel/jailhouse.c     |  6 +--
 arch/x86/kernel/kvmclock.c      | 88 +++++++++++++++++++++++----------
 arch/x86/kernel/paravirt.c      | 15 +++++-
 arch/x86/kernel/tsc.c           | 74 ++++++++++++++++-----------
 arch/x86/mm/mem_encrypt_amd.c   |  3 --
 arch/x86/xen/time.c             |  4 +-
 14 files changed, 243 insertions(+), 84 deletions(-)


base-commit: ebbb8be421eefbe2d47b99c2e1a6dd840d7930f9

---

## [2] Sean Christopherson — 2025-01-31
*Subject: [PATCH 01/16] x86/tsc: Add a standalone helpers for getting TSC info
 from CPUID.0x15*

Extract retrieval of TSC frequency information from CPUID into standalone
helpers so that TDX guest support and kvmlock can reuse the logic.  Provide
a version that includes the multiplier math as TDX in particular does NOT
want to use native_calibrate_tsc()'s fallback logic that derives the TSC
frequency based on CPUID.0x16 when the core crystal frequency isn't known.

No functional change intended.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/tsc.h | 41 ++++++++++++++++++++++++++++++++++++++
 arch/x86/kernel/tsc.c      | 14 ++-----------
 2 files changed, 43 insertions(+), 12 deletions(-)

diff --git a/arch/x86/include/asm/tsc.h b/arch/x86/include/asm/tsc.h
index 94408a784c8e..14a81a66b37c 100644
--- a/arch/x86/include/asm/tsc.h
+++ b/arch/x86/include/asm/tsc.h
@@ -28,6 +28,47 @@ static inline cycles_t get_cycles(void)
 }
 #define get_cycles get_cycles
 
+static inline int cpuid_get_tsc_info(unsigned int *crystal_khz,
+				     unsigned int *denominator,
+				     unsigned int *numerator)
+{
+	unsigned int ecx_hz, edx;
+
+	if (boot_cpu_data.cpuid_level < CPUID_LEAF_TSC)
+		return -ENOENT;
+
+	*crystal_khz = *denominator = *numerator = ecx_hz = edx = 0;
+
+	/* CPUID 15H TSC/Crystal ratio, plus optionally Crystal Hz */
+	cpuid(CPUID_LEAF_TSC, denominator, numerator, &ecx_hz, &edx);
+
+	if (!*denominator || !*numerator)
+		return -ENOENT;
+
+	/*
+	 * Note, some CPUs provide the multiplier information, but not the core
+	 * crystal frequency.  The multiplier information is still useful for
+	 * such CPUs, as the crystal frequency can be gleaned from CPUID.0x16.
+	 */
+	*crystal_khz = ecx_hz / 1000;
+	return 0;
+}
+
+static inline int cpuid_get_tsc_freq(unsigned int *tsc_khz,
+				     unsigned int *crystal_khz)
+{
+	unsigned int denominator, numerator;
+
+	if (cpuid_get_tsc_info(tsc_khz, &denominator, &numerator))
+		return -ENOENT;
+
+	if (!*crystal_khz)
+		return -ENOENT;
+
+	*tsc_khz = *crystal_khz * numerator / denominator;
+	return 0;
+}
+
 extern void tsc_early_init(void);
 extern void tsc_init(void);
 extern void mark_tsc_unstable(char *reason);
diff --git a/arch/x86/kernel/tsc.c b/arch/x86/kernel/tsc.c
index 34dec0b72ea8..e3faa2b36910 100644
--- a/arch/x86/kernel/tsc.c
+++ b/arch/x86/kernel/tsc.c
@@ -661,25 +661,15 @@ static unsigned long quick_pit_calibrate(void)
  */
 unsigned long native_calibrate_tsc(void)
 {
-	unsigned int eax_denominator, ebx_numerator, ecx_hz, edx;
+	unsigned int eax_denominator, ebx_numerator;
 	unsigned int crystal_khz;
 
 	if (boot_cpu_data.x86_vendor != X86_VENDOR_INTEL)
 		return 0;
 
-	if (boot_cpu_data.cpuid_level < CPUID_LEAF_TSC)
+	if (cpuid_get_tsc_info(&crystal_khz, &eax_denominator, &ebx_numerator))
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

---

## [3] Sean Christopherson — 2025-01-31
*Subject: [PATCH 02/16] x86/tsc: Add standalone helper for getting CPU
 frequency from CPUID*

Extract the guts of cpu_khz_from_cpuid() to a standalone helper that
doesn't restrict the usage to Intel CPUs.  This will allow sharing the
core logic with kvmclock, as (a) CPUID.0x16 may be enumerated alongside
kvmclock, and (b) KVM generally doesn't restrict CPUID based on vendor.

No functional change intended.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/tsc.h | 16 ++++++++++++++++
 arch/x86/kernel/tsc.c      | 21 ++++++---------------
 2 files changed, 22 insertions(+), 15 deletions(-)

diff --git a/arch/x86/include/asm/tsc.h b/arch/x86/include/asm/tsc.h
index 14a81a66b37c..540e2a31c87d 100644
--- a/arch/x86/include/asm/tsc.h
+++ b/arch/x86/include/asm/tsc.h
@@ -69,6 +69,22 @@ static inline int cpuid_get_tsc_freq(unsigned int *tsc_khz,
 	return 0;
 }
 
+static inline int cpuid_get_cpu_freq(unsigned int *cpu_khz)
+{
+	unsigned int eax_base_mhz, ebx, ecx, edx;
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
 extern void tsc_early_init(void);
 extern void tsc_init(void);
 extern void mark_tsc_unstable(char *reason);
diff --git a/arch/x86/kernel/tsc.c b/arch/x86/kernel/tsc.c
index e3faa2b36910..4fc633ac5873 100644
--- a/arch/x86/kernel/tsc.c
+++ b/arch/x86/kernel/tsc.c
@@ -662,7 +662,7 @@ static unsigned long quick_pit_calibrate(void)
 unsigned long native_calibrate_tsc(void)
 {
 	unsigned int eax_denominator, ebx_numerator;
-	unsigned int crystal_khz;
+	unsigned int crystal_khz, cpu_khz;
 
 	if (boot_cpu_data.x86_vendor != X86_VENDOR_INTEL)
 		return 0;
@@ -692,13 +692,8 @@ unsigned long native_calibrate_tsc(void)
 	 * clock, but we can easily calculate it to a high degree of accuracy
 	 * by considering the crystal ratio and the CPU speed.
 	 */
-	if (crystal_khz == 0 && boot_cpu_data.cpuid_level >= CPUID_LEAF_FREQ) {
-		unsigned int eax_base_mhz, ebx, ecx, edx;
-
-		cpuid(CPUID_LEAF_FREQ, &eax_base_mhz, &ebx, &ecx, &edx);
-		crystal_khz = eax_base_mhz * 1000 *
-			eax_denominator / ebx_numerator;
-	}
+	if (crystal_khz == 0 && !cpuid_get_cpu_freq(&cpu_khz))
+		crystal_khz = cpu_khz * eax_denominator / ebx_numerator;
 
 	if (crystal_khz == 0)
 		return 0;
@@ -725,19 +720,15 @@ unsigned long native_calibrate_tsc(void)
 
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

## [4] Sean Christopherson — 2025-01-31
*Subject: [PATCH 03/16] x86/tsc: Add helper to register CPU and TSC freq
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
index 82492efc5d94..684cef70edc1 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -3291,6 +3291,6 @@ void __init snp_secure_tsc_init(void)
 	rdmsrl(MSR_AMD64_GUEST_TSC_FREQ, tsc_freq_mhz);
 	snp_tsc_freq_khz = (unsigned long)(tsc_freq_mhz * 1000);
 
-	x86_platform.calibrate_cpu = securetsc_get_tsc_khz;
-	x86_platform.calibrate_tsc = securetsc_get_tsc_khz;
+	tsc_register_calibration_routines(securetsc_get_tsc_khz,
+					  securetsc_get_tsc_khz);
 }
diff --git a/arch/x86/include/asm/tsc.h b/arch/x86/include/asm/tsc.h
index 540e2a31c87d..82a6cc27cafb 100644
--- a/arch/x86/include/asm/tsc.h
+++ b/arch/x86/include/asm/tsc.h
@@ -87,6 +87,10 @@ static inline int cpuid_get_cpu_freq(unsigned int *cpu_khz)
 
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
index f285757618fc..aa60491bf738 100644
--- a/arch/x86/kernel/cpu/mshyperv.c
+++ b/arch/x86/kernel/cpu/mshyperv.c
@@ -478,8 +478,7 @@ static void __init ms_hyperv_init_platform(void)
 
 	if (ms_hyperv.features & HV_ACCESS_FREQUENCY_MSRS &&
 	    ms_hyperv.misc_features & HV_FEATURE_FREQUENCY_MSRS_AVAILABLE) {
-		x86_platform.calibrate_tsc = hv_get_tsc_khz;
-		x86_platform.calibrate_cpu = hv_get_tsc_khz;
+		tsc_register_calibration_routines(hv_get_tsc_khz, hv_get_tsc_khz);
 		setup_force_cpu_cap(X86_FEATURE_TSC_KNOWN_FREQ);
 	}
 
diff --git a/arch/x86/kernel/cpu/vmware.c b/arch/x86/kernel/cpu/vmware.c
index 00189cdeb775..d6f079a75f05 100644
--- a/arch/x86/kernel/cpu/vmware.c
+++ b/arch/x86/kernel/cpu/vmware.c
@@ -416,8 +416,8 @@ static void __init vmware_platform_setup(void)
 		}
 
 		vmware_tsc_khz = tsc_khz;
-		x86_platform.calibrate_tsc = vmware_get_tsc_khz;
-		x86_platform.calibrate_cpu = vmware_get_tsc_khz;
+		tsc_register_calibration_routines(vmware_get_tsc_khz,
+						  vmware_get_tsc_khz);
 
 #ifdef CONFIG_X86_LOCAL_APIC
 		/* Skip lapic calibration since we know the bus frequency. */
diff --git a/arch/x86/kernel/jailhouse.c b/arch/x86/kernel/jailhouse.c
index cd8ed1edbf9e..b0a053692161 100644
--- a/arch/x86/kernel/jailhouse.c
+++ b/arch/x86/kernel/jailhouse.c
@@ -209,8 +209,6 @@ static void __init jailhouse_init_platform(void)
 	x86_init.mpparse.parse_smp_cfg		= jailhouse_parse_smp_config;
 	x86_init.pci.arch_init			= jailhouse_pci_arch_init;
 
-	x86_platform.calibrate_cpu		= jailhouse_get_tsc;
-	x86_platform.calibrate_tsc		= jailhouse_get_tsc;
 	x86_platform.get_wallclock		= jailhouse_get_wallclock;
 	x86_platform.legacy.rtc			= 0;
 	x86_platform.legacy.warm_reset		= 0;
@@ -220,6 +218,8 @@ static void __init jailhouse_init_platform(void)
 
 	machine_ops.emergency_restart		= jailhouse_no_restart;
 
+	tsc_register_calibration_routines(jailhouse_get_tsc, jailhouse_get_tsc);
+
 	while (pa_data) {
 		mapping = early_memremap(pa_data, sizeof(header));
 		memcpy(&header, mapping, sizeof(header));
diff --git a/arch/x86/kernel/kvmclock.c b/arch/x86/kernel/kvmclock.c
index 5b2c15214a6b..b898b95a7d50 100644
--- a/arch/x86/kernel/kvmclock.c
+++ b/arch/x86/kernel/kvmclock.c
@@ -320,8 +320,8 @@ void __init kvmclock_init(void)
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
index 4fc633ac5873..5a16271b7a5c 100644
--- a/arch/x86/kernel/tsc.c
+++ b/arch/x86/kernel/tsc.c
@@ -1245,6 +1245,23 @@ static void __init check_system_tsc_reliable(void)
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
index 96521b1874ac..9e2e900dc0c7 100644
--- a/arch/x86/xen/time.c
+++ b/arch/x86/xen/time.c
@@ -566,7 +566,7 @@ static void __init xen_init_time_common(void)
 	static_call_update(pv_steal_clock, xen_steal_clock);
 	paravirt_set_sched_clock(xen_sched_clock);
 
-	x86_platform.calibrate_tsc = xen_tsc_khz;
+	tsc_register_calibration_routines(xen_tsc_khz, NULL);
 	x86_platform.get_wallclock = xen_get_wallclock;
 }

---

## [5] Sean Christopherson — 2025-01-31
*Subject: [PATCH 04/16] x86/sev: Mark TSC as reliable when configuring Secure TSC*

Move the code to mark the TSC as reliable from sme_early_init() to
snp_secure_tsc_init().  The only reader of TSC_RELIABLE is the aptly
named check_system_tsc_reliable(), which runs in tsc_init(), i.e.
after snp_secure_tsc_init().

This will allow consolidating the handling of TSC_KNOWN_FREQ and
TSC_RELIABLE when overriding the TSC calibration routine.

Cc: Nikunj A Dadhania <nikunj@amd.com>
Cc: Tom Lendacky <thomas.lendacky@amd.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/coco/sev/core.c      | 2 ++
 arch/x86/mm/mem_encrypt_amd.c | 3 ---
 2 files changed, 2 insertions(+), 3 deletions(-)

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index 684cef70edc1..e6ce4ca72465 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -3288,6 +3288,8 @@ void __init snp_secure_tsc_init(void)
 		return;
 
 	setup_force_cpu_cap(X86_FEATURE_TSC_KNOWN_FREQ);
+	setup_force_cpu_cap(X86_FEATURE_TSC_RELIABLE);
+
 	rdmsrl(MSR_AMD64_GUEST_TSC_FREQ, tsc_freq_mhz);
 	snp_tsc_freq_khz = (unsigned long)(tsc_freq_mhz * 1000);
 
diff --git a/arch/x86/mm/mem_encrypt_amd.c b/arch/x86/mm/mem_encrypt_amd.c
index b56c5c073003..774f9677458f 100644
--- a/arch/x86/mm/mem_encrypt_amd.c
+++ b/arch/x86/mm/mem_encrypt_amd.c
@@ -541,9 +541,6 @@ void __init sme_early_init(void)
 	 * kernel mapped.
 	 */
 	snp_update_svsm_ca();
-
-	if (sev_status & MSR_AMD64_SNP_SECURE_TSC)
-		setup_force_cpu_cap(X86_FEATURE_TSC_RELIABLE);
 }
 
 void __init mem_encrypt_free_decrypted_mem(void)

---

## [6] Sean Christopherson — 2025-01-31
*Subject: [PATCH 05/16] x86/sev: Move check for SNP Secure TSC support to tsc_early_init()*

Move the check on having a Secure TSC to the common tsc_early_init() so
that it's obvious that having a Secure TSC is conditional, and to prepare
for adding TDX to the mix (blindly initializing *both* SNP and TDX TSC
logic looks especially weird).

No functional change intended.

Cc: Nikunj A Dadhania <nikunj@amd.com>
Cc: Tom Lendacky <thomas.lendacky@amd.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/coco/sev/core.c | 3 ---
 arch/x86/kernel/tsc.c    | 3 ++-
 2 files changed, 2 insertions(+), 4 deletions(-)

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index e6ce4ca72465..dab386f782ce 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -3284,9 +3284,6 @@ void __init snp_secure_tsc_init(void)
 {
 	unsigned long long tsc_freq_mhz;
 
-	if (!cc_platform_has(CC_ATTR_GUEST_SNP_SECURE_TSC))
-		return;
-
 	setup_force_cpu_cap(X86_FEATURE_TSC_KNOWN_FREQ);
 	setup_force_cpu_cap(X86_FEATURE_TSC_RELIABLE);
 
diff --git a/arch/x86/kernel/tsc.c b/arch/x86/kernel/tsc.c
index 5a16271b7a5c..09ca0cbd4f31 100644
--- a/arch/x86/kernel/tsc.c
+++ b/arch/x86/kernel/tsc.c
@@ -1514,7 +1514,8 @@ void __init tsc_early_init(void)
 	if (is_early_uv_system())
 		return;
 
-	snp_secure_tsc_init();
+	if (cc_platform_has(CC_ATTR_GUEST_SNP_SECURE_TSC))
+		snp_secure_tsc_init();
 
 	if (!determine_cpu_tsc_frequencies(true))
 		return;

---

## [7] Sean Christopherson — 2025-01-31
*Subject: [PATCH 06/16] x86/tdx: Override PV calibration routines with
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
index 32809a06dab4..9d95dc713331 100644
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
@@ -1063,9 +1064,6 @@ void __init tdx_early_init(void)
 
 	setup_force_cpu_cap(X86_FEATURE_TDX_GUEST);
 
-	/* TSC is the only reliable clock in TDX guest */
-	setup_force_cpu_cap(X86_FEATURE_TSC_RELIABLE);
-
 	cc_vendor = CC_VENDOR_INTEL;
 
 	/* Configure the TD */
@@ -1122,3 +1120,29 @@ void __init tdx_early_init(void)
 
 	tdx_announce();
 }
+
+static unsigned long tdx_get_tsc_khz(void)
+{
+	unsigned int __tsc_khz, crystal_khz;
+
+	if (WARN_ON_ONCE(cpuid_get_tsc_freq(&__tsc_khz, &crystal_khz)))
+		return 0;
+
+	lapic_timer_period = crystal_khz * 1000 / HZ;
+
+	return __tsc_khz;
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
index b4b16dafd55e..621fbdd101e2 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -53,6 +53,7 @@ struct ve_info {
 #ifdef CONFIG_INTEL_TDX_GUEST
 
 void __init tdx_early_init(void);
+void __init tdx_tsc_init(void);
 
 void tdx_get_ve_info(struct ve_info *ve);
 
@@ -72,6 +73,7 @@ void __init tdx_dump_td_ctls(u64 td_ctls);
 #else
 
 static inline void tdx_early_init(void) { };
+static inline void tdx_tsc_init(void) { }
 static inline void tdx_safe_halt(void) { };
 
 static inline bool tdx_early_handle_ve(struct pt_regs *regs) { return false; }
diff --git a/arch/x86/kernel/tsc.c b/arch/x86/kernel/tsc.c
index 09ca0cbd4f31..922003059101 100644
--- a/arch/x86/kernel/tsc.c
+++ b/arch/x86/kernel/tsc.c
@@ -32,6 +32,7 @@
 #include <asm/topology.h>
 #include <asm/uv/uv.h>
 #include <asm/sev.h>
+#include <asm/tdx.h>
 
 unsigned int __read_mostly cpu_khz;	/* TSC clocks / usec, not used here */
 EXPORT_SYMBOL(cpu_khz);
@@ -1514,8 +1515,15 @@ void __init tsc_early_init(void)
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

## [8] Sean Christopherson — 2025-01-31
*Subject: [PATCH 07/16] x86/acrn: Mark TSC frequency as known when using ACRN
 for calibration*

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

## [9] Sean Christopherson — 2025-01-31
*Subject: [PATCH 08/16] x86/tsc: Pass KNOWN_FREQ and RELIABLE as params to registration*

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
index dab386f782ce..29dd50552715 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -3284,12 +3284,10 @@ void __init snp_secure_tsc_init(void)
 {
 	unsigned long long tsc_freq_mhz;
 
-	setup_force_cpu_cap(X86_FEATURE_TSC_KNOWN_FREQ);
-	setup_force_cpu_cap(X86_FEATURE_TSC_RELIABLE);
-
 	rdmsrl(MSR_AMD64_GUEST_TSC_FREQ, tsc_freq_mhz);
 	snp_tsc_freq_khz = (unsigned long)(tsc_freq_mhz * 1000);
 
 	tsc_register_calibration_routines(securetsc_get_tsc_khz,
-					  securetsc_get_tsc_khz);
+					  securetsc_get_tsc_khz,
+					  TSC_FREQ_KNOWN_AND_RELIABLE);
 }
diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 9d95dc713331..b1e3cca091b3 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -1135,14 +1135,11 @@ static unsigned long tdx_get_tsc_khz(void)
 
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
index 82a6cc27cafb..e99966f10594 100644
--- a/arch/x86/include/asm/tsc.h
+++ b/arch/x86/include/asm/tsc.h
@@ -88,8 +88,14 @@ static inline int cpuid_get_cpu_freq(unsigned int *cpu_khz)
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
index aa60491bf738..607a3c51eddf 100644
--- a/arch/x86/kernel/cpu/mshyperv.c
+++ b/arch/x86/kernel/cpu/mshyperv.c
@@ -478,8 +478,13 @@ static void __init ms_hyperv_init_platform(void)
 
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
@@ -582,7 +587,6 @@ static void __init ms_hyperv_init_platform(void)
 		 * is called.
 		 */
 		wrmsrl(HV_X64_MSR_TSC_INVARIANT_CONTROL, HV_EXPOSE_INVARIANT_TSC);
-		setup_force_cpu_cap(X86_FEATURE_TSC_RELIABLE);
 	}
 
 	/*
diff --git a/arch/x86/kernel/cpu/vmware.c b/arch/x86/kernel/cpu/vmware.c
index d6f079a75f05..6e4a2053857c 100644
--- a/arch/x86/kernel/cpu/vmware.c
+++ b/arch/x86/kernel/cpu/vmware.c
@@ -385,10 +385,10 @@ static void __init vmware_paravirt_ops_setup(void)
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
@@ -417,7 +417,8 @@ static void __init vmware_platform_setup(void)
 
 		vmware_tsc_khz = tsc_khz;
 		tsc_register_calibration_routines(vmware_get_tsc_khz,
-						  vmware_get_tsc_khz);
+						  vmware_get_tsc_khz,
+						  TSC_FREQ_KNOWN_AND_RELIABLE);
 
 #ifdef CONFIG_X86_LOCAL_APIC
 		/* Skip lapic calibration since we know the bus frequency. */
diff --git a/arch/x86/kernel/jailhouse.c b/arch/x86/kernel/jailhouse.c
index b0a053692161..d73a4d0fb118 100644
--- a/arch/x86/kernel/jailhouse.c
+++ b/arch/x86/kernel/jailhouse.c
@@ -218,7 +218,8 @@ static void __init jailhouse_init_platform(void)
 
 	machine_ops.emergency_restart		= jailhouse_no_restart;
 
-	tsc_register_calibration_routines(jailhouse_get_tsc, jailhouse_get_tsc);
+	tsc_register_calibration_routines(jailhouse_get_tsc, jailhouse_get_tsc,
+					  TSC_FREQUENCY_KNOWN);
 
 	while (pa_data) {
 		mapping = early_memremap(pa_data, sizeof(header));
@@ -256,7 +257,6 @@ static void __init jailhouse_init_platform(void)
 	pr_debug("Jailhouse: PM-Timer IO Port: %#x\n", pmtmr_ioport);
 
 	precalibrated_tsc_khz = setup_data.v1.tsc_khz;
-	setup_force_cpu_cap(X86_FEATURE_TSC_KNOWN_FREQ);
 
 	pci_probe = 0;
 
diff --git a/arch/x86/kernel/kvmclock.c b/arch/x86/kernel/kvmclock.c
index b898b95a7d50..b41ac7f27b9f 100644
--- a/arch/x86/kernel/kvmclock.c
+++ b/arch/x86/kernel/kvmclock.c
@@ -116,7 +116,6 @@ static inline void kvm_sched_clock_init(bool stable)
  */
 static unsigned long kvm_get_tsc_khz(void)
 {
-	setup_force_cpu_cap(X86_FEATURE_TSC_KNOWN_FREQ);
 	return pvclock_tsc_khz(this_cpu_pvti());
 }
 
@@ -320,7 +319,8 @@ void __init kvmclock_init(void)
 	flags = pvclock_read_flags(&hv_clock_boot[0].pvti);
 	kvm_sched_clock_init(flags & PVCLOCK_TSC_STABLE_BIT);
 
-	tsc_register_calibration_routines(kvm_get_tsc_khz, kvm_get_tsc_khz);
+	tsc_register_calibration_routines(kvm_get_tsc_khz, kvm_get_tsc_khz,
+					  TSC_FREQUENCY_KNOWN);
 
 	x86_platform.get_wallclock = kvm_get_wallclock;
 	x86_platform.set_wallclock = kvm_set_wallclock;
diff --git a/arch/x86/kernel/tsc.c b/arch/x86/kernel/tsc.c
index 922003059101..47776f450720 100644
--- a/arch/x86/kernel/tsc.c
+++ b/arch/x86/kernel/tsc.c
@@ -1252,11 +1252,17 @@ static void __init check_system_tsc_reliable(void)
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
index 9e2e900dc0c7..e7429f3cffc6 100644
--- a/arch/x86/xen/time.c
+++ b/arch/x86/xen/time.c
@@ -40,7 +40,6 @@ static unsigned long xen_tsc_khz(void)
 	struct pvclock_vcpu_time_info *info =
 		&HYPERVISOR_shared_info->vcpu_info[0].time;
 
-	setup_force_cpu_cap(X86_FEATURE_TSC_KNOWN_FREQ);
 	return pvclock_tsc_khz(info);
 }
 
@@ -566,7 +565,8 @@ static void __init xen_init_time_common(void)
 	static_call_update(pv_steal_clock, xen_steal_clock);
 	paravirt_set_sched_clock(xen_sched_clock);
 
-	tsc_register_calibration_routines(xen_tsc_khz, NULL);
+	tsc_register_calibration_routines(xen_tsc_khz, NULL,
+					  TSC_FREQUENCY_KNOWN);
 	x86_platform.get_wallclock = xen_get_wallclock;
 }

---

## [10] Sean Christopherson — 2025-01-31
*Subject: [PATCH 09/16] x86/tsc: Rejects attempts to override TSC calibration
 with lesser routine*

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
index 47776f450720..d7096323c2c4 100644
--- a/arch/x86/kernel/tsc.c
+++ b/arch/x86/kernel/tsc.c
@@ -1260,8 +1260,13 @@ void tsc_register_calibration_routines(unsigned long (*calibrate_tsc)(void),
 
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

## [11] Sean Christopherson — 2025-01-31
*Subject: [PATCH 10/16] x86/paravirt: Move handling of unstable PV clocks into paravirt_set_sched_clock()*

Move the handling of unstable PV clocks, of which kvmclock is the only
example, into paravirt_set_sched_clock().  This will allow modifying
paravirt_set_sched_clock() to keep using the TSC for sched_clock in
certain scenarios without unintentionally marking the TSC-based clock as
unstable.

No functional change intended.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/paravirt.h | 7 ++++++-
 arch/x86/kernel/kvmclock.c      | 5 +----
 arch/x86/kernel/paravirt.c      | 6 +++++-
 3 files changed, 12 insertions(+), 6 deletions(-)

diff --git a/arch/x86/include/asm/paravirt.h b/arch/x86/include/asm/paravirt.h
index 041aff51eb50..cfceabd5f7e1 100644
--- a/arch/x86/include/asm/paravirt.h
+++ b/arch/x86/include/asm/paravirt.h
@@ -28,7 +28,12 @@ u64 dummy_sched_clock(void);
 DECLARE_STATIC_CALL(pv_steal_clock, dummy_steal_clock);
 DECLARE_STATIC_CALL(pv_sched_clock, dummy_sched_clock);
 
-void paravirt_set_sched_clock(u64 (*func)(void));
+void __paravirt_set_sched_clock(u64 (*func)(void), bool stable);
+
+static inline void paravirt_set_sched_clock(u64 (*func)(void))
+{
+	__paravirt_set_sched_clock(func, true);
+}
 
 static __always_inline u64 paravirt_sched_clock(void)
 {
diff --git a/arch/x86/kernel/kvmclock.c b/arch/x86/kernel/kvmclock.c
index b41ac7f27b9f..890535ddc059 100644
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
@@ -93,10 +92,8 @@ static noinstr u64 kvm_sched_clock_read(void)
 
 static inline void kvm_sched_clock_init(bool stable)
 {
-	if (!stable)
-		clear_sched_clock_stable();
 	kvm_sched_clock_offset = kvm_clock_read();
-	paravirt_set_sched_clock(kvm_sched_clock_read);
+	__paravirt_set_sched_clock(kvm_sched_clock_read, stable);
 
 	pr_info("kvm-clock: using sched offset of %llu cycles",
 		kvm_sched_clock_offset);
diff --git a/arch/x86/kernel/paravirt.c b/arch/x86/kernel/paravirt.c
index 1ccaa3397a67..55c819673a9d 100644
--- a/arch/x86/kernel/paravirt.c
+++ b/arch/x86/kernel/paravirt.c
@@ -14,6 +14,7 @@
 #include <linux/highmem.h>
 #include <linux/kprobes.h>
 #include <linux/pgtable.h>
+#include <linux/sched/clock.h>
 #include <linux/static_call.h>
 
 #include <asm/bug.h>
@@ -85,8 +86,11 @@ static u64 native_steal_clock(int cpu)
 DEFINE_STATIC_CALL(pv_steal_clock, native_steal_clock);
 DEFINE_STATIC_CALL(pv_sched_clock, native_sched_clock);
 
-void paravirt_set_sched_clock(u64 (*func)(void))
+void __paravirt_set_sched_clock(u64 (*func)(void), bool stable)
 {
+	if (!stable)
+		clear_sched_clock_stable();
+
 	static_call_update(pv_sched_clock, func);
 }

---

## [12] Sean Christopherson — 2025-01-31
*Subject: [PATCH 11/16] x86/paravirt: Don't use a PV sched_clock in CoCo guests
 with trusted TSC*

Silently ignore attempts to switch to a paravirt sched_clock when running
as a CoCo guest with trusted TSC.  In hand-wavy theory, a misbehaving
hypervisor could attack the guest by manipulating the PV clock to affect
guest scheduling in some weird and/or predictable way.  More importantly,
reading TSC on such platforms is faster than any PV clock, and sched_clock
is all about speed.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kernel/paravirt.c | 9 +++++++++
 1 file changed, 9 insertions(+)

diff --git a/arch/x86/kernel/paravirt.c b/arch/x86/kernel/paravirt.c
index 55c819673a9d..980440d34997 100644
--- a/arch/x86/kernel/paravirt.c
+++ b/arch/x86/kernel/paravirt.c
@@ -88,6 +88,15 @@ DEFINE_STATIC_CALL(pv_sched_clock, native_sched_clock);
 
 void __paravirt_set_sched_clock(u64 (*func)(void), bool stable)
 {
+	/*
+	 * Don't replace TSC with a PV clock when running as a CoCo guest and
+	 * the TSC is secure/trusted; PV clocks are emulated by the hypervisor,
+	 * which isn't in the guest's TCB.
+	 */
+	if (cc_platform_has(CC_ATTR_GUEST_SNP_SECURE_TSC) ||
+	    boot_cpu_has(X86_FEATURE_TDX_GUEST))
+		return;
+
 	if (!stable)
 		clear_sched_clock_stable();

---

## [13] Sean Christopherson — 2025-01-31
*Subject: [PATCH 12/16] x86/kvmclock: Mark TSC as reliable when it's constant
 and nonstop*

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
 arch/x86/kernel/kvmclock.c | 31 +++++++++++++++++--------------
 1 file changed, 17 insertions(+), 14 deletions(-)

diff --git a/arch/x86/kernel/kvmclock.c b/arch/x86/kernel/kvmclock.c
index 890535ddc059..a7c4ae7f92e2 100644
--- a/arch/x86/kernel/kvmclock.c
+++ b/arch/x86/kernel/kvmclock.c
@@ -283,6 +283,7 @@ static int kvmclock_setup_percpu(unsigned int cpu)
 
 void __init kvmclock_init(void)
 {
+	enum tsc_properties tsc_properties = TSC_FREQUENCY_KNOWN;
 	u8 flags;
 
 	if (!kvm_para_available() || !kvmclock)
@@ -313,11 +314,26 @@ void __init kvmclock_init(void)
 	if (kvm_para_has_feature(KVM_FEATURE_CLOCKSOURCE_STABLE_BIT))
 		pvclock_set_flags(PVCLOCK_TSC_STABLE_BIT);
 
+	/*
+	 * X86_FEATURE_NONSTOP_TSC is TSC runs at constant rate
+	 * with P/T states and does not stop in deep C-states.
+	 *
+	 * Invariant TSC exposed by host means kvmclock is not necessary:
+	 * can use TSC as clocksource.
+	 *
+	 */
+	if (boot_cpu_has(X86_FEATURE_CONSTANT_TSC) &&
+	    boot_cpu_has(X86_FEATURE_NONSTOP_TSC) &&
+	    !check_tsc_unstable()) {
+		kvm_clock.rating = 299;
+		tsc_properties = TSC_FREQ_KNOWN_AND_RELIABLE;
+	}
+
 	flags = pvclock_read_flags(&hv_clock_boot[0].pvti);
 	kvm_sched_clock_init(flags & PVCLOCK_TSC_STABLE_BIT);
 
 	tsc_register_calibration_routines(kvm_get_tsc_khz, kvm_get_tsc_khz,
-					  TSC_FREQUENCY_KNOWN);
+					  tsc_properties);
 
 	x86_platform.get_wallclock = kvm_get_wallclock;
 	x86_platform.set_wallclock = kvm_set_wallclock;
@@ -328,19 +344,6 @@ void __init kvmclock_init(void)
 	x86_platform.restore_sched_clock_state = kvm_restore_sched_clock_state;
 	kvm_get_preset_lpj();
 
-	/*
-	 * X86_FEATURE_NONSTOP_TSC is TSC runs at constant rate
-	 * with P/T states and does not stop in deep C-states.
-	 *
-	 * Invariant TSC exposed by host means kvmclock is not necessary:
-	 * can use TSC as clocksource.
-	 *
-	 */
-	if (boot_cpu_has(X86_FEATURE_CONSTANT_TSC) &&
-	    boot_cpu_has(X86_FEATURE_NONSTOP_TSC) &&
-	    !check_tsc_unstable())
-		kvm_clock.rating = 299;
-
 	clocksource_register_hz(&kvm_clock, NSEC_PER_SEC);
 	pv_info.name = "KVM";
 }

---

## [14] Sean Christopherson — 2025-01-31
*Subject: [PATCH 13/16] x86/kvmclock: Get CPU base frequency from CPUID when
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
index a7c4ae7f92e2..66e53b15dd1d 100644
--- a/arch/x86/kernel/kvmclock.c
+++ b/arch/x86/kernel/kvmclock.c
@@ -102,6 +102,20 @@ static inline void kvm_sched_clock_init(bool stable)
 		sizeof(((struct pvclock_vcpu_time_info *)NULL)->system_time));
 }
 
+static unsigned long kvm_get_cpu_khz(void)
+{
+	unsigned int cpu_khz;
+
+	/*
+	 * Prefer CPUID over kvmclock when possible, as the base CPU frequency
+	 * isn't necessary the same as the kvmlock "TSC" frequency.
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
@@ -332,7 +346,7 @@ void __init kvmclock_init(void)
 	flags = pvclock_read_flags(&hv_clock_boot[0].pvti);
 	kvm_sched_clock_init(flags & PVCLOCK_TSC_STABLE_BIT);
 
-	tsc_register_calibration_routines(kvm_get_tsc_khz, kvm_get_tsc_khz,
+	tsc_register_calibration_routines(kvm_get_tsc_khz, kvm_get_cpu_khz,
 					  tsc_properties);
 
 	x86_platform.get_wallclock = kvm_get_wallclock;

---

## [15] Sean Christopherson — 2025-01-31
*Subject: [PATCH 14/16] x86/kvmclock: Get TSC frequency from CPUID when its available*

When kvmclock and CPUID.0x15 are both present, use the TSC frequency from
CPUID.0x15 instead of kvmclock's frequency.  Barring a misconfigured
setup, both sources should provide the same frequency, CPUID.0x15 is
arguably a better source when using the TSC over kvmclock, and most
importantly, using CPUID.0x15 will allow stuffing the local APIC timer
frequency based on the core crystal frequency, i.e. will allow skipping
APIC timer calibration.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kernel/kvmclock.c | 15 ++++++++++-----
 1 file changed, 10 insertions(+), 5 deletions(-)

diff --git a/arch/x86/kernel/kvmclock.c b/arch/x86/kernel/kvmclock.c
index 66e53b15dd1d..0ec867807b84 100644
--- a/arch/x86/kernel/kvmclock.c
+++ b/arch/x86/kernel/kvmclock.c
@@ -102,6 +102,16 @@ static inline void kvm_sched_clock_init(bool stable)
 		sizeof(((struct pvclock_vcpu_time_info *)NULL)->system_time));
 }
 
+static unsigned long kvm_get_tsc_khz(void)
+{
+	unsigned int __tsc_khz, crystal_khz;
+
+	if (!cpuid_get_tsc_freq(&__tsc_khz, &crystal_khz))
+		return __tsc_khz;
+
+	return pvclock_tsc_khz(this_cpu_pvti());
+}
+
 static unsigned long kvm_get_cpu_khz(void)
 {
 	unsigned int cpu_khz;
@@ -125,11 +135,6 @@ static unsigned long kvm_get_cpu_khz(void)
  * poll of guests can be running and trouble each other. So we preset
  * lpj here
  */
-static unsigned long kvm_get_tsc_khz(void)
-{
-	return pvclock_tsc_khz(this_cpu_pvti());
-}
-
 static void __init kvm_get_preset_lpj(void)
 {
 	unsigned long khz;

---

## [16] Sean Christopherson — 2025-01-31
*Subject: [PATCH 15/16] x86/kvmclock: Stuff local APIC bus period when core
 crystal freq comes from CPUID*

When running as a KVM guest with kvmclock support enabled, stuff the APIC
timer period/frequency with the core crystal frequency from CPUID.0x15 (if
CPUID.0x15 is provided).  KVM's ABI adheres to Intel's SDM, which states
that the APIC timer runs at the core crystal frequency when said frequency
is enumerated via CPUID.0x15.

  The APIC timer frequency will be the processor’s bus clock or core
  crystal clock frequency (when TSC/core crystal clock ratio is enumerated
  in CPUID leaf 0x15).

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kernel/kvmclock.c | 12 +++++++++++-
 1 file changed, 11 insertions(+), 1 deletion(-)

diff --git a/arch/x86/kernel/kvmclock.c b/arch/x86/kernel/kvmclock.c
index 0ec867807b84..9d05d070fe25 100644
--- a/arch/x86/kernel/kvmclock.c
+++ b/arch/x86/kernel/kvmclock.c
@@ -106,8 +106,18 @@ static unsigned long kvm_get_tsc_khz(void)
 {
 	unsigned int __tsc_khz, crystal_khz;
 
-	if (!cpuid_get_tsc_freq(&__tsc_khz, &crystal_khz))
+	/*
+	 * Prefer CPUID over kvmclock when possible, as CPUID also includes the
+	 * core crystal frequency, i.e. the APIC timer frequency.  When the core
+	 * crystal frequency is enumerated in CPUID.0x15, KVM's ABI is that the
+	 * (virtual) APIC BUS runs at the same frequency.
+	 */
+	if (!cpuid_get_tsc_freq(&__tsc_khz, &crystal_khz)) {
+#ifdef CONFIG_X86_LOCAL_APIC
+		lapic_timer_period = crystal_khz * 1000 / HZ;
+#endif
 		return __tsc_khz;
+	}
 
 	return pvclock_tsc_khz(this_cpu_pvti());
 }

---

## [17] Sean Christopherson — 2025-01-31
*Subject: [PATCH 16/16] x86/kvmclock: Use TSC for sched_clock if it's constant
 and non-stop*

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
broken for nearly two years with nary a complaint, i.e. it can't be
_that_ valuable.  And as above, certain types of KVM guests are losing
the functionality regardless, i.e. acknowledging PVCLOCK_GUEST_STOPPED
needs to be decoupled from sched_clock() no matter what.

Link: https://lore.kernel.org/all/Z4hDK27OV7wK572A@google.com
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kernel/kvmclock.c | 23 ++++++++++++++---------
 1 file changed, 14 insertions(+), 9 deletions(-)

diff --git a/arch/x86/kernel/kvmclock.c b/arch/x86/kernel/kvmclock.c
index 9d05d070fe25..fb8cd8313d18 100644
--- a/arch/x86/kernel/kvmclock.c
+++ b/arch/x86/kernel/kvmclock.c
@@ -344,23 +344,23 @@ void __init kvmclock_init(void)
 		pvclock_set_flags(PVCLOCK_TSC_STABLE_BIT);
 
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
+		flags = pvclock_read_flags(&hv_clock_boot[0].pvti);
+		kvm_sched_clock_init(flags & PVCLOCK_TSC_STABLE_BIT);
 	}
 
-	flags = pvclock_read_flags(&hv_clock_boot[0].pvti);
-	kvm_sched_clock_init(flags & PVCLOCK_TSC_STABLE_BIT);
-
 	tsc_register_calibration_routines(kvm_get_tsc_khz, kvm_get_cpu_khz,
 					  tsc_properties);
 
@@ -369,6 +369,11 @@ void __init kvmclock_init(void)
 #ifdef CONFIG_X86_LOCAL_APIC
 	x86_cpuinit.early_percpu_clock_init = kvm_setup_secondary_clock;
 #endif
+	/*
+	 * Save/restore "sched" clock state even if kvmclock isn't being used
+	 * for sched_clock, as kvmclock is still used for wallclock and relies
+	 * on these hooks to re-enable kvmclock after suspend+resume.
+	 */
 	x86_platform.save_sched_clock_state = kvm_save_sched_clock_state;
 	x86_platform.restore_sched_clock_state = kvm_restore_sched_clock_state;
 	kvm_get_preset_lpj();

---

## [18] Nikunj A Dadhania — 2025-02-03
*Subject: Re: [PATCH 01/16] x86/tsc: Add a standalone helpers for getting TSC
 info from CPUID.0x15*

Sean Christopherson <seanjc@google.com> writes:
> Extract retrieval of TSC frequency information from CPUID into standalone
> helpers so that TDX guest support and kvmlock can reuse the logic.  Provide

s/kvmlock/kvmclock

> a version that includes the multiplier math as TDX in particular does NOT
> want to use native_calibrate_tsc()'s fallback logic that derives the TSC

...

> +
> +static inline int cpuid_get_tsc_freq(unsigned int *tsc_khz,

Should we add this in patch 6/16 where it is being used for the first time ?

Regards
Nikunj

---

## [19] Tom Lendacky — 2025-02-03
*Subject: Re: [PATCH 08/16] x86/tsc: Pass KNOWN_FREQ and RELIABLE as params to
 registration*

On 1/31/25 20:17, Sean Christopherson wrote:
> Add a "tsc_properties" set of flags and use it to annotate whether the
> TSC operates at a known and/or reliable frequency when registering a

> diff --git a/arch/x86/kernel/cpu/vmware.c b/arch/x86/kernel/cpu/vmware.c
> index d6f079a75f05..6e4a2053857c 100644

Should this line be deleted, too, or does the VMware flow require this
to be done separate from the tsc_register_calibration_routines() call?

Thanks,
Tom

> -	if (vmware_tsc_khz)
> -		setup_force_cpu_cap(X86_FEATURE_TSC_KNOWN_FREQ);

---

## [20] Sean Christopherson — 2025-02-03
*Subject: Re: [PATCH 08/16] x86/tsc: Pass KNOWN_FREQ and RELIABLE as params to registration*

On Mon, Feb 03, 2025, Tom Lendacky wrote:
> On 1/31/25 20:17, Sean Christopherson wrote:
> > Add a "tsc_properties" set of flags and use it to annotate whether the

No idea, I just didn't want to break existing setups.  I assume VMware hypervisors
will always advertise the TSC frequency, but nothing in the code guarantees that.

The check on the hypervisor providing the TSC frequency has existed since the
original support was added, and the CONSTANT+RELIABLE logic was added immediately
after.  So even if it the above code _shouldn't_ be needed, I don't want to be
the sucker that finds out :-)

  395628ef4ea12ff0748099f145363b5e33c69acb x86: Skip verification by the watchdog for TSC clocksource.
  eca0cd028bdf0f6aaceb0d023e9c7501079a7dda x86: Add a synthetic TSC_RELIABLE feature bit.
  88b094fb8d4fe43b7025ea8d487059e8813e02cd x86: Hypervisor detection and get tsc_freq from hypervisor

---

## [21] Sean Christopherson — 2025-02-03
*Subject: Re: [PATCH 01/16] x86/tsc: Add a standalone helpers for getting TSC
 info from CPUID.0x15*

On Mon, Feb 03, 2025, Nikunj A Dadhania wrote:
> Sean Christopherson <seanjc@google.com> writes:
> > Extract retrieval of TSC frequency information from CPUID into standalone

No strong preference on my end.  I put it here mostly to keep each patch focused
on a single subsystem where possible, since the series touches so many areas.  I
also wanted to show the "full" API in a single patch, but I agree that adding a
helper without a user is generally undesirable.

---

## [22] Nikunj A Dadhania — 2025-02-04
*Subject: Re: [PATCH 04/16] x86/sev: Mark TSC as reliable when configuring
 Secure TSC*

Sean Christopherson <seanjc@google.com> writes:

> Move the code to mark the TSC as reliable from sme_early_init() to
> snp_secure_tsc_init().  The only reader of TSC_RELIABLE is the aptly

Reviewed-by: Nikunj A Dadhania <nikunj@amd.com>

> ---
>  arch/x86/coco/sev/core.c      | 2 ++

---

## [23] Nikunj A Dadhania — 2025-02-04
*Subject: Re: [PATCH 05/16] x86/sev: Move check for SNP Secure TSC support to
 tsc_early_init()*

Sean Christopherson <seanjc@google.com> writes:

> Move the check on having a Secure TSC to the common tsc_early_init() so
> that it's obvious that having a Secure TSC is conditional, and to prepare

Agree.

>
> No functional change intended.

Reviewed-by: Nikunj A Dadhania <nikunj@amd.com>

> ---
>  arch/x86/coco/sev/core.c | 3 ---

---

## [24] Nikunj A Dadhania — 2025-02-04
*Subject: Re: [PATCH 06/16] x86/tdx: Override PV calibration routines with
 CPUID-based calibration*

Sean Christopherson <seanjc@google.com> writes:

> When running as a TDX guest, explicitly override the TSC frequency
> calibration routine with CPUID-based calibration instead of potentially

Does TDX use kvmclock? If yes, kvmclock would have registered the CPU
frequency calibration routine:

	tsc_register_calibration_routines(kvm_get_tsc_khz, kvm_get_cpu_khz,
 					  tsc_properties);

so TDX will use kvm_get_cpu_khz(), which will either use CPUID.0x16 or
PV clock, is this on the expected line ?

Regards
Nikunj

> +
> +void __init tdx_tsc_init(void)

---

## [25] Sean Christopherson — 2025-02-04
*Subject: Re: [PATCH 06/16] x86/tdx: Override PV calibration routines with
 CPUID-based calibration*

On Tue, Feb 04, 2025, Nikunj A Dadhania wrote:
> Sean Christopherson <seanjc@google.com> writes:
> 

A TDX guest can.  That's up to the host (expose kvmclock) and the guest (enable
kvmclock).

> If yes, kvmclock would have registered the CPU frequency calibration routine:
> 

What do you mean by "is this on the expected line"?  If you are asking "is this
intended", then the answer is "yes, working as intended".  As above, the TDX-Module
doesn't emulate CPUID.0x16, so no matter what, the guest is relying on the untrusted
hypervisor to get the CPU frequency.  If someone thinks that TDX guests should
assume the CPU runs as the same frequency as the TSC, a la SNP's Secure TSC, then
they are welcome to propose such a change.

---

## [26] Nikunj A Dadhania — 2025-02-05
*Subject: Re: [PATCH 06/16] x86/tdx: Override PV calibration routines with
 CPUID-based calibration*

Sean Christopherson <seanjc@google.com> writes:

> On Tue, Feb 04, 2025, Nikunj A Dadhania wrote:
>> Sean Christopherson <seanjc@google.com> writes:

Yes, that is what I meant.

> then the answer is "yes, working as intended".  As above, the TDX-Module
> doesn't emulate CPUID.0x16, so no matter what, the guest is relying on the untrusted

Ok, that makes sense.

Regards
Nikunj

---

## [27] Sean Christopherson — 2025-02-05
*Subject: Re: [PATCH 01/16] x86/tsc: Add a standalone helpers for getting TSC
 info from CPUID.0x15*

On Fri, Jan 31, 2025, Sean Christopherson wrote:
> +static inline int cpuid_get_tsc_freq(unsigned int *tsc_khz,
> +				     unsigned int *crystal_khz)

As pointed out by Dan, this is broken.  It should be crystal_khz, not tsc_khz.
I fixed the bug in my test build but clobbered it before posting.

> +		return -ENOENT;
> +

---

## [28] Sean Christopherson — 2025-02-07
*Subject: Re: [PATCH 16/16] x86/kvmclock: Use TSC for sched_clock if it's
 constant and non-stop*

Dropping a few people/lists whose emails are bouncing.

On Fri, Jan 31, 2025, Sean Christopherson wrote:
> @@ -369,6 +369,11 @@ void __init kvmclock_init(void)
>  #ifdef CONFIG_X86_LOCAL_APIC

This is wrong, wallclock is a different MSR entirely.

> +	 */
>  	x86_platform.save_sched_clock_state = kvm_save_sched_clock_state;

And usurping sched_clock save/restore is *really* wrong if kvmclock isn't being
used as sched_clock, because when TSC is reset on suspend/hiberation, not doing
tsc_{save,restore}_sched_clock_state() results in time going haywire.

Subtly, that issue goes all the way back to patch "x86/paravirt: Don't use a PV
sched_clock in CoCo guests with trusted TSC" because pulling the rug out from
under kvmclock leads to the same problem.

The whole PV sched_clock scheme is a disaster.

Hyper-V overrides the save/restore callbacks, but _also_ runs the old TSC callbacks,
because Hyper-V doesn't ensure that it's actually using the Hyper-V clock for
sched_clock.  And the code is all kinds of funky, because it tries to keep the
x86 code isolated from the generic HV clock code, but (a) there's already x86 PV
specific code in drivers/clocksource/hyperv_timer.c, and (b) splitting the code
means that Hyper-V overides the sched_clock save/restore hooks even when PARAVIRT=n,
i.e. when HV clock can't possibly be used as sched_clock.

VMware appears to be buggy and doesn't do have offset adjustments, and also lets
the TSC callbacks run.

I can't tell if Xen is broken, or if it's the sanest of the bunch.  Xen does
save/restore things a la kvmclock, but only in the Xen PV suspend path.  So if
the "normal" suspend/hibernate paths are unreachable, Xen is sane.  If not, Xen
is quite broken.

To make matters worse, kvmclock is a mess and has existing bugs.  The BSP's clock
is disabled during syscore_suspend() (via kvm_suspend()), but only re-enabled in
the sched_clock callback.  So if suspend is aborted due to a late wakeup, the BSP
will run without its clock enabled, which "works" only because KVM-the-hypervisor
is kind enough to not clobber the shared memory when the clock is disabled.  But
over time, I would expect time on the BSP to drift from APs.

And then there's this crud:

  #ifdef CONFIG_X86_LOCAL_APIC
	x86_cpuinit.early_percpu_clock_init = kvm_setup_secondary_clock;
  #endif

which (a) should be guarded by CONFIG_SMP, not X86_LOCAL_APIC, and (b) is only
actually needed when kvmclock is sched_clock, because timekeeping doesn't actually
need to start that early.  But of course kvmclock craptastic handling of suspend
and resume makes untangling that more difficult than it needs to be.

The icing on the cake is that after cleaning up all the hacks, and having
kvmclock hook clocksource.suspend/resume like it should, suspend/resume under
kvmclock corrupts wall clock time because timekeeping_resume() reads the persistent
clock before resuming clocksource clocks, and the stupid kvmclock wall clock subtly
consumes the clocksource/system clock.  *sigh*

I have yet more patches to clean all of this up.  The series is rather unwieldly,
as it's now sitting at 38 patches (ugh), but I don't see a way to chunk it up in
a meaningful way, because everything is so intertwined.  :-/

---

## [29] Michael Kelley — 2025-02-08
*Subject: RE: [PATCH 16/16] x86/kvmclock: Use TSC for sched_clock if it's
 constant and non-stop*

From: Sean Christopherson <seanjc@google.com> Sent: Friday, February 7, 2025 9:23 AM
> 
> Dropping a few people/lists whose emails are bouncing.

Regarding (a), the one occurrence of x86 PV-specific code hyperv_timer.c is
the call to paravirt_set_sched_clock(), and it's under an #ifdef sequence so that
it's not built if targeting some other architecture. Or do you see something else
that is x86-specific?

Regarding (b), in drivers/hv/Kconfig, CONFIG_HYPERV always selects PARAVIRT.
So the #else clause (where PARAVIRT=n) in that #ifdef sequence could arguably
have a BUILD_BUG() added. If I recall correctly, other Hyper-V stuff breaks if
PARAVIRT is forced to "n". So I don't think there's a current problem with the
sched_clock save/restore hooks. But I would be good with some restructuring
so that setting the sched clock save/restore hooks is more closely tied to the
sched clock choice, as long as the architecture independence of hyperv_timer.c
is preserved. And maybe there's a better way to handle hv_setup_sched_clock()
that is less messy with the #ifdef's. I'll think about that too.

Michael

> 
> VMware appears to be buggy and doesn't do have offset adjustments, and also lets

---

## [30] Sean Christopherson — 2025-02-10
*Subject: Re: [PATCH 16/16] x86/kvmclock: Use TSC for sched_clock if it's
 constant and non-stop*

On Sat, Feb 08, 2025, Michael Kelley wrote:
> From: Sean Christopherson <seanjc@google.com> Sent: Friday, February 7, 2025 9:23 AM
> > 

Oh, there are no build issues, and all of the x86 bits are nicely cordoned off.
My complaint is essentially that they're _too_ isolated; putting the sched_clock
save/restore setup in arch/x86/kernel/cpu/mshyperv.c is well-intentioned, but IMO
it does more harm than good because the split makes it difficult to connect the
dots to hv_setup_sched_clock() in drivers/clocksource/hyperv_timer.c.

> But I would be good with some restructuring so that setting the sched clock
> save/restore hooks is more closely tied to the sched clock choice,

Yeah, this is the intent of my ranting.  After the dust settles, the code can
look like this.

---
#ifdef CONFIG_GENERIC_SCHED_CLOCK
static __always_inline void hv_setup_sched_clock(void *sched_clock)
{
	/*
	 * We're on an architecture with generic sched clock (not x86/x64).
	 * The Hyper-V sched clock read function returns nanoseconds, not
	 * the normal 100ns units of the Hyper-V synthetic clock.
	 */
	sched_clock_register(sched_clock, 64, NSEC_PER_SEC);
}
#elif defined CONFIG_PARAVIRT
static u64 hv_ref_counter_at_suspend;
/*
 * Hyper-V clock counter resets during hibernation. Save and restore clock
 * offset during suspend/resume, while also considering the time passed
 * before suspend. This is to make sure that sched_clock using hv tsc page
 * based clocksource, proceeds from where it left off during suspend and
 * it shows correct time for the timestamps of kernel messages after resume.
 */
static void hv_save_sched_clock_state(void)
{
	hv_ref_counter_at_suspend = hv_read_reference_counter();
}

static void hv_restore_sched_clock_state(void)
{
	/*
	 * Adjust the offsets used by hv tsc clocksource to
	 * account for the time spent before hibernation.
	 * adjusted value = reference counter (time) at suspend
	 *                - reference counter (time) now.
	 */
	hv_sched_clock_offset -= (hv_ref_counter_at_suspend - hv_read_reference_counter());
}

static __always_inline void hv_setup_sched_clock(void *sched_clock)
{
	/* We're on x86/x64 *and* using PV ops */
	paravirt_set_sched_clock(sched_clock, hv_save_sched_clock_state,
				 hv_restore_sched_clock_state);
}
#else /* !CONFIG_GENERIC_SCHED_CLOCK && !CONFIG_PARAVIRT */
static __always_inline void hv_setup_sched_clock(void *sched_clock) {}
#endif /* CONFIG_GENERIC_SCHED_CLOCK */
---

> as long as the architecture independence of hyperv_timer.c is preserved.

LOL, ah yes, the architecture independence of MSRs and TSC :-D

Teasing aside, the code is firmly x86-only at the moment.  It's selectable only
by x86:

  config HYPERV_TIMER
	def_bool HYPERV && X86
 
and since at least commit e39acc37db34 ("clocksource: hyper-v: Provide noinstr
sched_clock()") there are references to symbols/functions that are provided only
by x86.

I assume arm64 support is a WIP, but keeping the upstream code arch independent
isn't very realistic if the code can't be at least compile-tested.  To help
drive-by contributors like myself, maybe select HYPER_TIMER on arm64 for
COMPILE_TEST=y builds?

  config HYPERV_TIMER
	def_bool HYPERV && (X86 || (COMPILE_TEST && ARM64))

I have no plans to touch code outside of CONFIG_PARAVIRT, i.e. outside of code
that is explicitly x86-only, but something along those lines would help people
like me understand the goal/intent, and in theory would also help y'all maintain
the code by detecting breakage.

---

## [31] Borislav Petkov — 2025-02-11
*Subject: Re: [PATCH 00/16] x86/tsc: Try to wrangle PV clocks vs. TSC*

On Fri, Jan 31, 2025 at 06:17:02PM -0800, Sean Christopherson wrote:
> And if the host provides the core crystal frequency in CPUID.0x15, then KVM
> guests can use that for the APIC timer period instead of manually

Hmm, so that part: what's stopping the host from faking the CPUID leaf? I.e.,
I would think that actually doing the work to calibrate the frequency would be
more reliable/harder to fake to a guest than the guest simply reading some
untrusted values from CPUID...

Or are we saying here: oh well, there are so many ways for a normal guest to
be lied to so that we simply do the completely different approach and trust
the HV to be benevolent when we're not dealing with confidential guests which
have all those other things to keep the HV honest?

Just checking the general thinking here.

Thx.

---

## [32] Borislav Petkov — 2025-02-11
*Subject: Re: [PATCH 01/16] x86/tsc: Add a standalone helpers for getting TSC
 info from CPUID.0x15*

On Fri, Jan 31, 2025 at 06:17:03PM -0800, Sean Christopherson wrote:
> Extract retrieval of TSC frequency information from CPUID into standalone
> helpers so that TDX guest support and kvmlock can reuse the logic.  Provide

Bah, why in the header as inlines? Just leave them in tsc.c and call them...

> @@ -28,6 +28,47 @@ static inline cycles_t get_cycles(void)
>  }

Can we pls do a

struct cpuid_tsc_info {
	unsigned int denominator;
	unsigned int numerator;
	unsigned int crystal_khz;
	unsigned int tsc_khz;
}

and hand that around instead of those I/O pointers?

It would make the code a bit saner to stare at and follow.

Thx.

---

## [33] Sean Christopherson — 2025-02-11
*Subject: Re: [PATCH 00/16] x86/tsc: Try to wrangle PV clocks vs. TSC*

On Tue, Feb 11, 2025, Borislav Petkov wrote:
> On Fri, Jan 31, 2025 at 06:17:02PM -0800, Sean Christopherson wrote:
> > And if the host provides the core crystal frequency in CPUID.0x15, then KVM

Not really.  Crafting an attack based on timing would be far more difficult than
tricking the guest into thinking the APIC runs at the "wrong" frequency.  The
APIC timer itself is controlled by the hypervisor, e.g. the host can emulate the
timer at the "wrong" freuquency on-demand.  Detecting that the guest is post-boot
and thus done calibrating is trivial.

> Or are we saying here: oh well, there are so many ways for a normal guest to
> be lied to so that we simply do the completely different approach and trust

This.  Outside of CoCo, the hypervisor is 100% trusted.  And there's zero reason
for the hypervisor to lie, it can simply read/write all guest state.

---

## [34] Sean Christopherson — 2025-02-11
*Subject: Re: [PATCH 01/16] x86/tsc: Add a standalone helpers for getting TSC
 info from CPUID.0x15*

On Tue, Feb 11, 2025, Borislav Petkov wrote:
> On Fri, Jan 31, 2025 at 06:17:03PM -0800, Sean Christopherson wrote:
> > Extract retrieval of TSC frequency information from CPUID into standalone

Because obviously optimizing code that's called once during boot is super
critical?

> Just leave them in tsc.c and call them...
> 

Ah, yeah, that's way better.

---

## [35] Borislav Petkov — 2025-02-11
*Subject: Re: [PATCH 03/16] x86/tsc: Add helper to register CPU and TSC freq
 calibration routines*

On Fri, Jan 31, 2025 at 06:17:05PM -0800, Sean Christopherson wrote:

Drop:

jailhouse-dev@googlegroups.com
Alexey Makhalov <alexey.amakhalov@broadcom.com>

from Cc as they're bouncing.

> Add a TODO to call out that AMD_MEM_ENCRYPT is a mess and doesn't depend on
> HYPERVISOR_GUEST because it gates both guest and host code.

Why is it a mess?

I don't see it, frankly.

---

## [36] Sean Christopherson — 2025-02-11
*Subject: Re: [PATCH 03/16] x86/tsc: Add helper to register CPU and TSC freq
 calibration routines*

On Tue, Feb 11, 2025, Borislav Petkov wrote:
> On Fri, Jan 31, 2025 at 06:17:05PM -0800, Sean Christopherson wrote:
> 

It conflates two very different things: host/bare metal support for memory
encryption, and SEV guest support.  For kernels that will never run in a VM,
pulling in all the SEV guest code just to enable host-side support for SME (and
SEV) is very undesirable.

And in this case, because AMD_MEM_ENCRYPT gates both host and guest code, it
can't depend on HYPERVISOR_GUEST like it should, because taking a dependency on
HYPERVISOR_GUEST to enable SME is obviously wrong.

---

## [37] Borislav Petkov — 2025-02-11
*Subject: Re: [PATCH 01/16] x86/tsc: Add a standalone helpers for getting TSC
 info from CPUID.0x15*

On Tue, Feb 11, 2025 at 09:25:47AM -0800, Sean Christopherson wrote:
> Because obviously optimizing code that's called once during boot is super
> critical?

Because let's stick 'em where they belong and keep headers containing only
small, trivial and inlineable functions. Having unusually big functions in
a header triggers my weird code patterns detector. :)

---

## [38] Sean Christopherson — 2025-02-11
*Subject: Re: [PATCH 01/16] x86/tsc: Add a standalone helpers for getting TSC
 info from CPUID.0x15*

On Tue, Feb 11, 2025, Borislav Petkov wrote:
> On Tue, Feb 11, 2025 at 09:25:47AM -0800, Sean Christopherson wrote:
> > Because obviously optimizing code that's called once during boot is super

LOL, sorry, I was being sarcastic and poking fun at myself.  I completely agree
there's no reason to make them inline.

---

## [39] Borislav Petkov — 2025-02-11
*Subject: Re: [PATCH 03/16] x86/tsc: Add helper to register CPU and TSC freq
 calibration routines*

On Tue, Feb 11, 2025 at 09:43:23AM -0800, Sean Christopherson wrote:
> It conflates two very different things: host/bare metal support for memory
> encryption, and SEV guest support.  For kernels that will never run in a VM,

Well, that might've grown in the meantime... when we started it, it was all
small so it didn't really matter and we kept it simple. That's why I never
thought about it. And actually, we've been thinking of even ripping out SME
in favor of TSME which is transparent and doesn't need any SME glue. But there
was some reason why we didn't want to do it yet, Tom would know.

As to carving it out now, meh, dunno how much savings that would be. Got
a student to put on that task? :-P

> And in this case, because AMD_MEM_ENCRYPT gates both host and guest code, it
> can't depend on HYPERVISOR_GUEST like it should, because taking a dependency on

Right.

---

## [40] Michael Kelley — 2025-02-12
*Subject: RE: [PATCH 16/16] x86/kvmclock: Use TSC for sched_clock if it's
 constant and non-stop*

From: Sean Christopherson <seanjc@google.com> Sent: Monday, February 10, 2025 8:22 AM
> 
> On Sat, Feb 08, 2025, Michael Kelley wrote:

I'm good with what you are proposing. And if you want, there's no real need
for hv_ref_counter_at_suspend and hv_save/restore_sched_clock_state()
to be in the #ifdef sequence since the code has no architecture dependencies.
Sure, the only current caller is x86-specific, but the functionality is generic
and might useful on some other architecture in the future. That was the
essence of my comment on the original patch that added this code [1].
The patch author took it a step further and moved all the code into an
x86-specific module, which I was OK with at the time. But your moving
it back is probably better.

[1] https://lore.kernel.org/all/SN6PR02MB4157141DD58FD6EAE96C7CABD4992@SN6PR02MB4157.namprd02.prod.outlook.com/

> 
> ---

This is a digression from what you are trying to accomplish, but the function
and symbols names reflect history and are misleading. The terms "TSC" and
"MSR" are used, but arch-specific wrapper functions map "TSC" to the arm64
architectural system counter, for example. And the MSR references are all to
Hyper-V synthetic MSRs, which are mapped to the arm64 equivalent
registers and are accessed via explicit hypercalls instead of rdmsr()/wrmsr(). I
wish we had better terminology to use in the generic code.

> 
> Teasing aside, the code is firmly x86-only at the moment.  It's selectable only

Ah yes. I think I missed that commit e39acc37db34 added hv_raw_get_register(),
which doesn't have an arm64 equivalent. I had not previously known about
COMPILE_TEST=y. Thanks for pointing that out, and I'll check into using it.

Michael

> 
>   config HYPERV_TIMER

---

## [41] Tom Lendacky — 2025-02-12
*Subject: Re: [PATCH 03/16] x86/tsc: Add helper to register CPU and TSC freq
 calibration routines*

On 2/11/25 14:32, Borislav Petkov wrote:
> On Tue, Feb 11, 2025 at 09:43:23AM -0800, Sean Christopherson wrote:
>> It conflates two very different things: host/bare metal support for memory

I think it was because TSME is a BIOS setting and you don't trust BIOS
to always expose the setting :)

I do have a patch series to remove SME. I haven't updated it in a couple
of releases, so would just need to dust it off and rebase it.

Thanks,
Tom

> 
> As to carving it out now, meh, dunno how much savings that would be. Got

---

## [42] Sean Christopherson — 2025-02-12
*Subject: Re: [PATCH 16/16] x86/kvmclock: Use TSC for sched_clock if it's
 constant and non-stop*

On Wed, Feb 12, 2025, Michael Kelley wrote:
> From: Sean Christopherson <seanjc@google.com> Sent: Monday, February 10, 2025 8:22 AM
> > On Sat, Feb 08, 2025, Michael Kelley wrote:

Right, but because they will be local/static and there are no users outside of
x86, the compiler will complain about unused variables/functions on other
architectures.

---
