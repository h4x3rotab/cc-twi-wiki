---
title: 'KVM: SEV: Add support for BTB Isolation'
date: 2026-03-11
last_reply: 2026-03-13
message_count: 8
participants: ['Kim Phillips', 'Sean Christopherson', 'kernel test robot', 'Tom Lendacky', 'Pawan Gupta']
---

## [1] Kim Phillips — 2026-03-11

This feature ensures SNP guest Branch Target Buffers (BTBs) are not
affected by context outside that guest.

The first patch fixes a longstanding bug where users weren't able
to force Automatic IBRS on SNP enabled machines using spectre_v2=eibrs.

The second patch fixes another longstanding bug where users couldn't
select legacy / toggling SPEC_CTRL[IBRS] on AMD systems.  Users of
the BTB Isolation feature may use IBRS to mitigate possible
performance degradation caused by BTB Isolation.

The third patch adds support for the feature by adding it to the
supported features bitmask.

Based on tip/master, currently 7726ce228780.
https://git.kernel.org/pub/scm/linux/kernel/git/tip/tip.git

This series also available here:

https://github.com/AMDESE/linux/tree/btb-isol-latest

Advance qemu bits (to add btb-isol=on/off switch) available here:

https://github.com/AMDESE/qemu/tree/btb-isol-latest

Qemu bits will be posted upstream once kernel bits are merged.
They depend on Naveen Rao's "target/i386: SEV: Add support for
enabling VMSA SEV features":

https://lore.kernel.org/qemu-devel/cover.1761648149.git.naveen@kernel.org/

v2:
 - Patch 1/3:
   - Address Dave Hansen's comment to adhere to using the IBRS_ENHANCED
     Intel feature flag also for AutoIBRS.

v1:
 https://lore.kernel.org/kvm/20260224180157.725159-1-kim.phillips@amd.com/

Kim Phillips (3):
  cpu/bugs: Allow forcing Automatic IBRS with SNP enabled using
    spectre_v2=eibrs
  cpu/bugs: Allow spectre_v2=ibrs on x86 vendors other than Intel
  KVM: SEV: Add support for SNP BTB Isolation

 arch/x86/include/asm/svm.h   |  1 +
 arch/x86/kernel/cpu/bugs.c   | 19 +++++++++++--------
 arch/x86/kernel/cpu/common.c |  6 +-----
 arch/x86/kvm/svm/sev.c       |  3 +++
 4 files changed, 16 insertions(+), 13 deletions(-)


base-commit: 7726ce2287804e70b2bf2fc00f104530b603d3f3

---

## [2] Kim Phillips — 2026-03-11
*Subject: [PATCH v2 1/3] cpu/bugs: Allow forcing Automatic IBRS with SNP enabled using spectre_v2=eibrs*

To allow this, do the SNP check in spectre_v2_select_mitigation()
processing instead of the original commit's implementation in
cpu_set_bug_bits().

Since SPECTRE_V2_CMD_AUTO logic falls through to SPECTRE_V2_CMD_FORCE,
double-check if SPECTRE_V2_CMD_FORCE is used before allowing
SPECTRE_V2_EIBRS with SNP enabled.

Also mute SPECTRE_V2_IBRS_PERF_MSG if SNP is enabled on an AutoIBRS
capable machine, since, in that case, the message doesn't apply.

Fixes: acaa4b5c4c85 ("x86/speculation: Do not enable Automatic IBRS if SEV-SNP is enabled")
Reported-by: Tom Lendacky <thomas.lendacky@amd.com>
Cc: Borislav Petkov (AMD) <bp@alien8.de>
Cc: stable@kernel.org
Signed-off-by: Kim Phillips <kim.phillips@amd.com>
---
v2:
 - Address Dave Hansen's comment to adhere to using the IBRS_ENHANCED
   Intel feature flag also for AutoIBRS.

v1:
 https://lore.kernel.org/kvm/20260224180157.725159-2-kim.phillips@amd.com/

 arch/x86/kernel/cpu/bugs.c   | 12 ++++++++++--
 arch/x86/kernel/cpu/common.c |  6 +-----
 2 files changed, 11 insertions(+), 7 deletions(-)

diff --git a/arch/x86/kernel/cpu/bugs.c b/arch/x86/kernel/cpu/bugs.c
index 83f51cab0b1e..957e0df38d90 100644
--- a/arch/x86/kernel/cpu/bugs.c
+++ b/arch/x86/kernel/cpu/bugs.c
@@ -2181,7 +2181,14 @@ static void __init spectre_v2_select_mitigation(void)
 			break;
 		fallthrough;
 	case SPECTRE_V2_CMD_FORCE:
-		if (boot_cpu_has(X86_FEATURE_IBRS_ENHANCED)) {
+		/*
+		 * Unless forced, don't use AutoIBRS when SNP is enabled
+		 * because it degrades host userspace indirect branch performance.
+		 */
+		if (boot_cpu_has(X86_FEATURE_IBRS_ENHANCED) &&
+		    (!boot_cpu_has(X86_FEATURE_SEV_SNP) ||
+		     (boot_cpu_has(X86_FEATURE_SEV_SNP) &&
+		      spectre_v2_cmd == SPECTRE_V2_CMD_FORCE))) {
 			spectre_v2_enabled = SPECTRE_V2_EIBRS;
 			break;
 		}
@@ -2261,7 +2268,8 @@ static void __init spectre_v2_apply_mitigation(void)
 
 	case SPECTRE_V2_IBRS:
 		setup_force_cpu_cap(X86_FEATURE_KERNEL_IBRS);
-		if (boot_cpu_has(X86_FEATURE_IBRS_ENHANCED))
+		if (boot_cpu_has(X86_FEATURE_IBRS_ENHANCED) &&
+		    !boot_cpu_has(X86_FEATURE_SEV_SNP))
 			pr_warn(SPECTRE_V2_IBRS_PERF_MSG);
 		break;
 
diff --git a/arch/x86/kernel/cpu/common.c b/arch/x86/kernel/cpu/common.c
index bb937bc4b00f..5aff1424a27d 100644
--- a/arch/x86/kernel/cpu/common.c
+++ b/arch/x86/kernel/cpu/common.c
@@ -1486,13 +1486,9 @@ static void __init cpu_set_bug_bits(struct cpuinfo_x86 *c)
 	/*
 	 * AMD's AutoIBRS is equivalent to Intel's eIBRS - use the Intel feature
 	 * flag and protect from vendor-specific bugs via the whitelist.
-	 *
-	 * Don't use AutoIBRS when SNP is enabled because it degrades host
-	 * userspace indirect branch performance.
 	 */
 	if ((x86_arch_cap_msr & ARCH_CAP_IBRS_ALL) ||
-	    (cpu_has(c, X86_FEATURE_AUTOIBRS) &&
-	     !cpu_feature_enabled(X86_FEATURE_SEV_SNP))) {
+	    cpu_has(c, X86_FEATURE_AUTOIBRS)) {
 		setup_force_cpu_cap(X86_FEATURE_IBRS_ENHANCED);
 		if (!cpu_matches(cpu_vuln_whitelist, NO_EIBRS_PBRSB) &&
 		    !(x86_arch_cap_msr & ARCH_CAP_PBRSB_NO))

---

## [3] Kim Phillips — 2026-03-11
*Subject: [PATCH v2 2/3] cpu/bugs: Allow spectre_v2=ibrs on x86 vendors other than Intel*

This is to prepare to allow legacy IBRS toggling on AMD systems,
where the BTB Isolation SEV-SNP feature can use it to optimize the
quick VM exit to re-entry path.

There is no reason this wasn't allowed in the first place, therefore
adding the cc: stable and Fixes: tags.

Fixes: 7c693f54c873 ("x86/speculation: Add spectre_v2=ibrs option to support Kernel IBRS")
Reported-by: Tom Lendacky <thomas.lendacky@amd.com>
Cc: Pawan Gupta <pawan.kumar.gupta@linux.intel.com>
Cc: Borislav Petkov (AMD) <bp@alien8.de>
Cc: stable@kernel.org
Signed-off-by: Kim Phillips <kim.phillips@amd.com>
---
v2: No changes
v1: https://lore.kernel.org/kvm/20260224180157.725159-3-kim.phillips@amd.com/

 arch/x86/kernel/cpu/bugs.c | 7 +------
 1 file changed, 1 insertion(+), 6 deletions(-)

diff --git a/arch/x86/kernel/cpu/bugs.c b/arch/x86/kernel/cpu/bugs.c
index 957e0df38d90..c910da561044 100644
--- a/arch/x86/kernel/cpu/bugs.c
+++ b/arch/x86/kernel/cpu/bugs.c
@@ -2152,11 +2152,6 @@ static void __init spectre_v2_select_mitigation(void)
 		spectre_v2_cmd = SPECTRE_V2_CMD_AUTO;
 	}
 
-	if (spectre_v2_cmd == SPECTRE_V2_CMD_IBRS && boot_cpu_data.x86_vendor != X86_VENDOR_INTEL) {
-		pr_err("IBRS selected but not Intel CPU. Switching to AUTO select\n");
-		spectre_v2_cmd = SPECTRE_V2_CMD_AUTO;
-	}
-
 	if (spectre_v2_cmd == SPECTRE_V2_CMD_IBRS && !boot_cpu_has(X86_FEATURE_IBRS)) {
 		pr_err("IBRS selected but CPU doesn't have IBRS. Switching to AUTO select\n");
 		spectre_v2_cmd = SPECTRE_V2_CMD_AUTO;
@@ -2251,7 +2246,7 @@ static void __init spectre_v2_apply_mitigation(void)
 		pr_err(SPECTRE_V2_EIBRS_EBPF_MSG);
 
 	if (spectre_v2_in_ibrs_mode(spectre_v2_enabled)) {
-		if (boot_cpu_has(X86_FEATURE_AUTOIBRS)) {
+		if (boot_cpu_has(X86_FEATURE_AUTOIBRS) && spectre_v2_enabled != SPECTRE_V2_IBRS) {
 			msr_set_bit(MSR_EFER, _EFER_AUTOIBRS);
 		} else {
 			x86_spec_ctrl_base |= SPEC_CTRL_IBRS;

---

## [4] Kim Phillips — 2026-03-11
*Subject: [PATCH v2 3/3] KVM: SEV: Add support for SNP BTB Isolation*

This feature ensures SNP guest Branch Target Buffers (BTBs) are not
affected by context outside that guest.  CPU hardware tracks each
guest's BTB entries and can flush the BTB if it has been determined
to be contaminated with any prediction information originating outside
the particular guest's context.

To mitigate possible performance penalties incurred by these flushes,
it is recommended that the hypervisor run with SPEC_CTRL[IBRS] set.
Note that using Automatic IBRS is not an equivalent option here, since
it behaves differently when SEV-SNP is active.  See commit acaa4b5c4c85
("x86/speculation: Do not enable Automatic IBRS if SEV-SNP is enabled")
for more details.

Indicate support for BTB Isolation in sev_supported_vmsa_features,
bit 7.

SNP-active guests can enable (BTB) Isolation through SEV_Status
bit 9 (SNPBTBIsolation).

For more info, refer to page 615, Section 15.36.17 "Side-Channel
Protection", AMD64 Architecture Programmer's Manual Volume 2: System
Programming Part 2, Pub. 24593 Rev. 3.42 - March 2024 (see Link).

Link: https://bugzilla.kernel.org/attachment.cgi?id=306250
Signed-off-by: Kim Phillips <kim.phillips@amd.com>
---
v2: No changes
v1: https://lore.kernel.org/kvm/20260224180157.725159-4-kim.phillips@amd.com/

 arch/x86/include/asm/svm.h | 1 +
 arch/x86/kvm/svm/sev.c     | 3 +++
 2 files changed, 4 insertions(+)

diff --git a/arch/x86/include/asm/svm.h b/arch/x86/include/asm/svm.h
index edde36097ddc..2038461c1316 100644
--- a/arch/x86/include/asm/svm.h
+++ b/arch/x86/include/asm/svm.h
@@ -305,6 +305,7 @@ static_assert((X2AVIC_4K_MAX_PHYSICAL_ID & AVIC_PHYSICAL_MAX_INDEX_MASK) == X2AV
 #define SVM_SEV_FEAT_RESTRICTED_INJECTION		BIT(3)
 #define SVM_SEV_FEAT_ALTERNATE_INJECTION		BIT(4)
 #define SVM_SEV_FEAT_DEBUG_SWAP				BIT(5)
+#define SVM_SEV_FEAT_BTB_ISOLATION			BIT(7)
 #define SVM_SEV_FEAT_SECURE_TSC				BIT(9)
 
 #define VMCB_ALLOWED_SEV_FEATURES_VALID			BIT_ULL(63)
diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 3f9c1aa39a0a..ac29cf47dd08 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -3167,6 +3167,9 @@ void __init sev_hardware_setup(void)
 
 	if (sev_snp_enabled && tsc_khz && cpu_feature_enabled(X86_FEATURE_SNP_SECURE_TSC))
 		sev_supported_vmsa_features |= SVM_SEV_FEAT_SECURE_TSC;
+
+	if (sev_snp_enabled)
+		sev_supported_vmsa_features |= SVM_SEV_FEAT_BTB_ISOLATION;
 }
 
 void sev_hardware_unsetup(void)

---

## [5] Sean Christopherson — 2026-03-11
*Subject: Re: [PATCH v2 3/3] KVM: SEV: Add support for SNP BTB Isolation*

On Wed, Mar 11, 2026, Kim Phillips wrote:
> This feature ensures SNP guest Branch Target Buffers (BTBs) are not
> affected by context outside that guest.  CPU hardware tracks each

This isn't very useful for the changelog.  I can read the patch quite easily.

What would be useful is a description of the change in conversational language,
and an explanation of why it is the correct change.  E.g. (not really, but you
get the idea)

  Advertise support for BTB Ioslation via SEV_VMSA_FEATURES when SNP is
  enabled, as all hardware that supports SNP also support BTB Isolation.
  BTB Isolation is an optional feature that can be enabled by the guest to
  sprinkle fairy dust on the CPU to completely prevent all speculative
  execution attacks.

> SNP-active guests can enable (BTB) Isolation through SEV_Status
> bit 9 (SNPBTBIsolation).

That's not what the doc says:

  SNP-active guests may choose to enable the Branch Target Buffer Isolation
  mode through SEV_FEATURES bit 7 (BTBIsolation).

> For more info,> refer to page 615, Section 15.36.17 "Side-Channel
> Protection", AMD64 Architecture Programmer's Manual Volume 2: System

If BTB_ISOLATION is actually supported on *all* SNP hardware, then that needs to
be called out.  Please also separate this from the core kernel changes, unless
there is some dependency on them.  And if there _is_ a dependency, call that out.

Ugh, I'm getting deja vu.  I suspect I had a long response typed out for v1 of
this patch, and rebooted my system before actually sending it.

Oh wait, no, you just made the same mistakes in two different patches.  Please
revist https://lore.kernel.org/all/aaWog_UjW-M3412C@google.com.

In general, spamming patches without internalizing the feedback makes for grumpy
maintainers.

---

## [6] kernel test robot — 2026-03-12
*Subject: Re: [PATCH v2 1/3] cpu/bugs: Allow forcing Automatic IBRS with SNP
 enabled using spectre_v2=eibrs*

Hi Kim,

kernel test robot noticed the following build warnings:

[auto build test WARNING on 7726ce2287804e70b2bf2fc00f104530b603d3f3]

url:    https://github.com/intel-lab-lkp/linux/commits/Kim-Phillips/cpu-bugs-Allow-forcing-Automatic-IBRS-with-SNP-enabled-using-spectre_v2-eibrs/20260311-211730
base:   7726ce2287804e70b2bf2fc00f104530b603d3f3
patch link:    https://lore.kernel.org/r/20260311130611.2201214-2-kim.phillips%40amd.com
patch subject: [PATCH v2 1/3] cpu/bugs: Allow forcing Automatic IBRS with SNP enabled using spectre_v2=eibrs
config: x86_64-randconfig-101-20260312 (https://download.01.org/0day-ci/archive/20260312/202603121136.bc8zNsHS-lkp@intel.com/config)
compiler: gcc-14 (Debian 14.2.0-19) 14.2.0

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202603121136.bc8zNsHS-lkp@intel.com/

cocci warnings: (new ones prefixed by >>)
>> arch/x86/kernel/cpu/bugs.c:2190:42-44: WARNING !A || A && B is equivalent to !A || B

vim +2190 arch/x86/kernel/cpu/bugs.c

  2122	
  2123	static void __init spectre_v2_select_mitigation(void)
  2124	{
  2125		if ((spectre_v2_cmd == SPECTRE_V2_CMD_RETPOLINE ||
  2126		     spectre_v2_cmd == SPECTRE_V2_CMD_RETPOLINE_LFENCE ||
  2127		     spectre_v2_cmd == SPECTRE_V2_CMD_RETPOLINE_GENERIC ||
  2128		     spectre_v2_cmd == SPECTRE_V2_CMD_EIBRS_LFENCE ||
  2129		     spectre_v2_cmd == SPECTRE_V2_CMD_EIBRS_RETPOLINE) &&
  2130		    !IS_ENABLED(CONFIG_MITIGATION_RETPOLINE)) {
  2131			pr_err("RETPOLINE selected but not compiled in. Switching to AUTO select\n");
  2132			spectre_v2_cmd = SPECTRE_V2_CMD_AUTO;
  2133		}
  2134	
  2135		if ((spectre_v2_cmd == SPECTRE_V2_CMD_EIBRS ||
  2136		     spectre_v2_cmd == SPECTRE_V2_CMD_EIBRS_LFENCE ||
  2137		     spectre_v2_cmd == SPECTRE_V2_CMD_EIBRS_RETPOLINE) &&
  2138		    !boot_cpu_has(X86_FEATURE_IBRS_ENHANCED)) {
  2139			pr_err("EIBRS selected but CPU doesn't have Enhanced or Automatic IBRS. Switching to AUTO select\n");
  2140			spectre_v2_cmd = SPECTRE_V2_CMD_AUTO;
  2141		}
  2142	
  2143		if ((spectre_v2_cmd == SPECTRE_V2_CMD_RETPOLINE_LFENCE ||
  2144		     spectre_v2_cmd == SPECTRE_V2_CMD_EIBRS_LFENCE) &&
  2145		    !boot_cpu_has(X86_FEATURE_LFENCE_RDTSC)) {
  2146			pr_err("LFENCE selected, but CPU doesn't have a serializing LFENCE. Switching to AUTO select\n");
  2147			spectre_v2_cmd = SPECTRE_V2_CMD_AUTO;
  2148		}
  2149	
  2150		if (spectre_v2_cmd == SPECTRE_V2_CMD_IBRS && !IS_ENABLED(CONFIG_MITIGATION_IBRS_ENTRY)) {
  2151			pr_err("IBRS selected but not compiled in. Switching to AUTO select\n");
  2152			spectre_v2_cmd = SPECTRE_V2_CMD_AUTO;
  2153		}
  2154	
  2155		if (spectre_v2_cmd == SPECTRE_V2_CMD_IBRS && boot_cpu_data.x86_vendor != X86_VENDOR_INTEL) {
  2156			pr_err("IBRS selected but not Intel CPU. Switching to AUTO select\n");
  2157			spectre_v2_cmd = SPECTRE_V2_CMD_AUTO;
  2158		}
  2159	
  2160		if (spectre_v2_cmd == SPECTRE_V2_CMD_IBRS && !boot_cpu_has(X86_FEATURE_IBRS)) {
  2161			pr_err("IBRS selected but CPU doesn't have IBRS. Switching to AUTO select\n");
  2162			spectre_v2_cmd = SPECTRE_V2_CMD_AUTO;
  2163		}
  2164	
  2165		if (spectre_v2_cmd == SPECTRE_V2_CMD_IBRS && cpu_feature_enabled(X86_FEATURE_XENPV)) {
  2166			pr_err("IBRS selected but running as XenPV guest. Switching to AUTO select\n");
  2167			spectre_v2_cmd = SPECTRE_V2_CMD_AUTO;
  2168		}
  2169	
  2170		if (!boot_cpu_has_bug(X86_BUG_SPECTRE_V2)) {
  2171			spectre_v2_cmd = SPECTRE_V2_CMD_NONE;
  2172			return;
  2173		}
  2174	
  2175		switch (spectre_v2_cmd) {
  2176		case SPECTRE_V2_CMD_NONE:
  2177			return;
  2178	
  2179		case SPECTRE_V2_CMD_AUTO:
  2180			if (!should_mitigate_vuln(X86_BUG_SPECTRE_V2))
  2181				break;
  2182			fallthrough;
  2183		case SPECTRE_V2_CMD_FORCE:
  2184			/*
  2185			 * Unless forced, don't use AutoIBRS when SNP is enabled
  2186			 * because it degrades host userspace indirect branch performance.
  2187			 */
  2188			if (boot_cpu_has(X86_FEATURE_IBRS_ENHANCED) &&
  2189			    (!boot_cpu_has(X86_FEATURE_SEV_SNP) ||
> 2190			     (boot_cpu_has(X86_FEATURE_SEV_SNP) &&
  2191			      spectre_v2_cmd == SPECTRE_V2_CMD_FORCE))) {
  2192				spectre_v2_enabled = SPECTRE_V2_EIBRS;
  2193				break;
  2194			}
  2195	
  2196			spectre_v2_enabled = spectre_v2_select_retpoline();
  2197			break;
  2198	
  2199		case SPECTRE_V2_CMD_RETPOLINE_LFENCE:
  2200			pr_err(SPECTRE_V2_LFENCE_MSG);
  2201			spectre_v2_enabled = SPECTRE_V2_LFENCE;
  2202			break;
  2203	
  2204		case SPECTRE_V2_CMD_RETPOLINE_GENERIC:
  2205			spectre_v2_enabled = SPECTRE_V2_RETPOLINE;
  2206			break;
  2207	
  2208		case SPECTRE_V2_CMD_RETPOLINE:
  2209			spectre_v2_enabled = spectre_v2_select_retpoline();
  2210			break;
  2211	
  2212		case SPECTRE_V2_CMD_IBRS:
  2213			spectre_v2_enabled = SPECTRE_V2_IBRS;
  2214			break;
  2215	
  2216		case SPECTRE_V2_CMD_EIBRS:
  2217			spectre_v2_enabled = SPECTRE_V2_EIBRS;
  2218			break;
  2219	
  2220		case SPECTRE_V2_CMD_EIBRS_LFENCE:
  2221			spectre_v2_enabled = SPECTRE_V2_EIBRS_LFENCE;
  2222			break;
  2223	
  2224		case SPECTRE_V2_CMD_EIBRS_RETPOLINE:
  2225			spectre_v2_enabled = SPECTRE_V2_EIBRS_RETPOLINE;
  2226			break;
  2227		}
  2228	}
  2229

---

## [7] Tom Lendacky — 2026-03-13
*Subject: Re: [PATCH v2 3/3] KVM: SEV: Add support for SNP BTB Isolation*

On 3/11/26 08:06, Kim Phillips wrote:
> This feature ensures SNP guest Branch Target Buffers (BTBs) are not
> affected by context outside that guest.  CPU hardware tracks each

This would also need to update the SVM_SEV_FEAT_SNP_ONLY_MASK that Sean
suggested/created in the IBPB-On-Entry series.

Thanks,
Tom

>  }
>

---

## [8] Pawan Gupta — 2026-03-13
*Subject: Re: [PATCH v2 1/3] cpu/bugs: Allow forcing Automatic IBRS with SNP
 enabled using spectre_v2=eibrs*

On Wed, Mar 11, 2026 at 08:06:09AM -0500, Kim Phillips wrote:
> To allow this, do the SNP check in spectre_v2_select_mitigation()
> processing instead of the original commit's implementation in

This is forcing AutoIBRS when spectre_v2=on (meaning force), but the
subject says to allow forcing with spectre_v2=eibrs, which one is it?

---
