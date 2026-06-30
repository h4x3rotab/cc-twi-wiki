---
title: 'Enable DICE-based TDX Quoting Extension'
date: 2026-06-18
last_reply: 2026-06-29
message_count: 48
participants: ['Xu Yilun', 'Dave Hansen', 'Chao Gao', 'Peter Fang', 'Tony Lindgren', 'Sean Christopherson']
---

## [1] Xu Yilun — 2026-06-18

This series adds infrastructure to enable TDX module extensions and
then implements DICE-based TDX Quoting extension. This is the 2nd
version and a significant change is that we want the quoting part to
merge along with the basic TDX module extensions part, rather than
serving as an example. So the quoting part drops RFC tags and requires
initial review. The basic extensions part addresses v1 comments and
needs more detailed review.

The quoting part contains some KVM patches, so we sorted the series for
easier review and pick:

  Patches  1-6:  Enable the TDX module extensions support
  Patches  7-14: DICE-based TDX Quoting, x86/tdx part
  Patches  15-N: DICE-based TDX Quoting, KVM part

== Overview ==

To date, SEAMCALLs have been short lived routines that monopolize the
CPU for their duration. This limits their utility for implementing
higher order security protocols, or pushes complexity into Linux - such
as by fragmenting a protocol setup service into several SEAMCALLs. The
Linux appetite for ingesting complexity is low, so TDX now adds a new
class of SEAMCALLs that are preemptible and resumable. This capability
allows for higher-level API constructions - like "create a DICE-based
quote" - which are more aligned to what is a good fit for Linux.

This new "extension SEAMCALL" capability is akin to ARM CCA's "Stateful
RMI Operations (SRO)", and achieves similar externalized complexity
relief as a dedicated hardware co-processor like AMD SEV-SNP. The
mechanism is "give the service environment some memory", "invoke the
service API", and "continue invoking until complete". All protocol state
is internal to the service API.

TDX introduces "TDX module extensions" as the service environment for
some add-on features - such as DICE-based quoting, TDISP, and live
migration - to use "extension SEAMCALLs".

The extension SEAMCALLs are designed to be transparent to the host,
using the same interface as normal SEAMCALLs, but the service
environment should be initialized in several steps. First,
configure/select (via TDH.SYS.CONFIG) add-on features during basic TDX
initialization. Second, check if TDX module extensions are required to
support these add-on features by reading TDX global metadata. Third, add
extra memory to the TDX module via a SEAMCALL (TDH.EXT.MEM.ADD).
Finally, use another SEAMCALL (TDH.EXT.INIT) to initialize the
extensions.

== DICE-based Quoting extension ==

The first feature to use these extensions is the TDX Quoting extension [1],
which converts guest launch attestation reports into a document that can be
verified externally.

Today, the TDX host requires a separate software service to generate Quotes.
The Quoting extension allows the TDX module to generate Quotes directly,
without relying on a discrete Quoting engine. This simplifies the overall
attestation flow: KVM no longer needs to return to userspace for Quote
generation. Instead, Quote generation is handled directly by the TDX module
through an extension SEAMCALL. See [2] for an overview of TDX attestation.

The Device Identifier Composition Engine ("DICE") provides a standardized
framework for layering attestation evidence. It replaces SGX-based attestation
and moves away from Intel-proprietary formats. It also eliminates the SGX
requirement to contact an Intel service to obtain a certificate first.
Instead, all attestation evidence is embedded in the Quote itself.

== The trade-off ==

The extensions create an extension instance for each feature that
requires extension SEAMCALLs. More memory is consumed when more
extension instances are created. There are 3 extensions (quoting, TDISP,
Migration) in the foreseeable future. Turning on them all will require
tens of megabytes. Note that the host can never reclaim the memory added
to the extensions.

According to the TDX module design, basic TDX functionalities can run
without the extensions. So theoretically the extensions don't need to be
enabled at basic TDX initialization time. They could be lazily enabled
right before the first extension SEAMCALL is issued.

However, Linux applies a simple policy for TDX: turn on all the features
that Linux knows about all the time, unless and until any evidence makes
this approach untenable. Enabling the extensions along with the basic
TDX at boot time aligns with the policy, and offers several good
reasons:

  1. Simplify TDX state management, avoid runtime state transitions that
     could introduce race conditions or unexpected failure modes.

  2. The kernel doesn't have to keep track of which SEAMCALLs need the
     extensions, as there is no HW/FW enumeration for this.

  3. When no extension is configured, the extensions initialization is
     virtually skipped. So no impact on existing kernels.

  4. A small trade-off is that eager initialization allocates memory
     (tens of megabytes) at boot time before any feature starts to work.
     However, these features provide critical security capabilities in
     confidential computing. They are expected to be enabled eventually
     when available. So this merely advances the timing of memory
     allocation.

== Restore the extensions after runtime TDX module update ==

Runtime TDX module update introduces a mechanism to update the module
firmware while preserving and restoring TDX operations. As part of the
restoration process, TDX module extensions must also be re-initialized
to re-enable extension SEAMCALLs.

Similar to TDH.SYS.CONFIG, TDX module extends TDH.SYS.UPDATE with more
parameters for the host to re-enable desired add-on features. Then host
must re-execute all extensions initialization steps to restore extension
SEAMCALL functionality.

However, Linux runs the update in stop_machine() context, which prevents
memory allocation. This introduces a hard restriction that the updated
TDX environment must not consume more memory for the extensions.

Fortunately, Linux applies another policy that no newer features should
be added during runtime update to avoid disrupting live TDX operations.
To adhere to this, TDH.SYS.UPDATE must enable the same features as the
TDH.SYS.CONFIG. This policy mitigates the memory allocation problem a
lot by minimizing the chance of increased memory demand. So now the
restriction only affects the compatibility rule for choosing the update
image.

The same memory constraint applies to the Quoting extension. A compatible
runtime update must not increase the size limit of its Quotes, because the
buffer used for Quote generation is allocated during TDX bringup. Otherwise,
attestation could fail after the update if the TDX module requires a larger
buffer for Quotes.

== Some history ==

The TDX module extensions support part was first posted along with TDX
TDISP [3]. But quoting is the simplest consumer and is chosen as the
lead vehicle over TDISP.

== Misc ==

This series is based on tip/x86/tdx [4], because we need the extensions
play nice with runtime TDX module update.

Link: https://cdrdv2.intel.com/v1/dl/getContent/874303 # [1]
Link: Documentation/arch/x86/tdx.rst, Section "Attestation" # [2]
Link: https://lore.kernel.org/all/20260327160132.2946114-1-yilun.xu@linux.intel.com/ # [3]
Link: https://git.kernel.org/pub/scm/linux/kernel/git/tip/tip.git/log/?h=x86/tdx # [4]

== Changelog ==

v2:
- Support runtime TDX module update
- Refine quoting patches, drop RFC tag
- Change the patch order. (Xiaoyao & Tony)
- Fold metadata readings changes into patches that use them.
- Read the extensions metadata at init_tdx_ext() (Rick & Xiaoyao)
- Don't do get_tdx_sys_info() a 2nd time after TDH.SYS.CONFIG (Rick & Xiaoyao)
- Delete tdx_clflush_hpa_list() (Rick)
- s/TDX Module/TDX module (Sohil)
- s/Extensions/extensions (Dave)
- Change the data type of ext_required to bool (Rick)
- Change the data type of memory_pool_required_pages from u16 to u32,
  the Module team see this problem and promise the change (Sohil)
- s/init_tdx_ext()/init_tdx_module_extensions() to disambiguate from
  tdx_ext_init() (Kishen)
- Cover-letter & change log re-phrase (All reviewers)

v1: https://lore.kernel.org/all/20260522034128.3144354-1-yilun.xu@linux.intel.com/


Peter Fang (11):
  x86/virt/tdx: Initialize Quoting extension
  x86/virt/tdx: Prepare Quote buffer during extension bringup
  x86/virt/tdx: Add interface to check Quoting availability
  x86/virt/tdx: Move tdx_tdr_pa() up in the file
  x86/virt/tdx: Add interface to generate a Quote
  x86/virt/tdx: Reinitialize the Quoting extension after TDX module
    update
  x86/virt/tdx: Enable Quoting extension
  x86/tdx: Move and rename Quote request structure
  KVM: TDX: Factor out userspace return path from tdx_get_quote()
  KVM: TDX: Add in-kernel Quote generation
  KVM: TDX: Support event-notify interrupts only with userspace Quoting

Xu Yilun (6):
  x86/virt/tdx: Embed version info in SEAMCALL leaf function definitions
  x86/virt/tdx: Configure add-on features on TDX module init and update
  x86/virt/tdx: Detect if the extensions initialization is required
  x86/virt/tdx: Add extra memory to TDX module for the extensions
  x86/virt/tdx: Make TDX module initialize the extensions
  x86/virt/tdx: Re-initialize the extensions on runtime TDX module
    update

 Documentation/arch/x86/tdx.rst              |  19 +-
 Documentation/virt/kvm/api.rst              |   3 +
 arch/x86/include/asm/tdx.h                  |  35 ++
 arch/x86/include/asm/tdx_global_metadata.h  |   9 +
 arch/x86/kvm/vmx/tdx.h                      |   6 +
 arch/x86/virt/vmx/tdx/tdx.h                 |  33 +-
 arch/x86/kvm/vmx/tdx.c                      | 176 +++++++-
 arch/x86/virt/vmx/tdx/tdx.c                 | 465 +++++++++++++++++++-
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c |  34 ++
 drivers/virt/coco/tdx-guest/tdx-guest.c     |  47 +-
 virt/kvm/kvm_main.c                         |   1 +
 11 files changed, 755 insertions(+), 73 deletions(-)


base-commit: 2b9ad7a6154e0938b9458691536296dd0224942d

---

## [2] Xu Yilun — 2026-06-18
*Subject: [PATCH v2 01/17] x86/virt/tdx: Embed version info in SEAMCALL leaf function definitions*

Embed version information in SEAMCALL leaf function definitions rather
than let the caller open code them. For now, only TDH.VP.INIT is
involved.

Don't bother the caller to choose the SEAMCALL version if unnecessary.
New version SEAMCALLs are guaranteed to be backward compatible, so
ideally the kernel doesn't need to keep version history and only uses
the latest version SEAMCALLs.

And in confidential computing world, system security requires us to stop
using an older TDX module when there is a newer one. So don't burden the
kernel with long-term supporting an older TDX module that doesn't
understand newer version SEAMCALLs.

The only concern is there may be transitional periods when a new TDX
module is not widely available, meaning the kernel may temporarily need
to support multiple SEAMCALL versions. As time goes by, the old TDX
modules deprecate and old version SEAMCALL definitions should disappear.

The old TDX modules that only support TDH.VP.INIT v0 are all deprecated,
so only provide the latest (v1) definition.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 arch/x86/virt/vmx/tdx/tdx.h | 23 ++++++++++++++---------
 arch/x86/virt/vmx/tdx/tdx.c |  3 +--
 2 files changed, 15 insertions(+), 11 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index bdfd0e1e337a..fbb520704662 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -2,6 +2,7 @@
 #ifndef _X86_VIRT_TDX_H
 #define _X86_VIRT_TDX_H
 
+#include <linux/bitfield.h>
 #include <linux/bits.h>
 
 /*
@@ -11,6 +12,18 @@
  * architectural definitions come first.
  */
 
+/*
+ * SEAMCALL leaf:
+ *
+ * Bit 15:0	Leaf number
+ * Bit 23:16	Version number
+ */
+#define SEAMCALL_LEAF			GENMASK(15, 0)
+#define SEAMCALL_VER			GENMASK(23, 16)
+
+#define SEAMCALL_LEAF_VER(l, v)		(FIELD_PREP(SEAMCALL_LEAF, l) | \
+					 FIELD_PREP(SEAMCALL_VER, v))
+
 /*
  * TDX module SEAMCALL leaf functions
  */
@@ -31,7 +44,7 @@
 #define TDH_VP_CREATE			10
 #define TDH_MNG_KEY_FREEID		20
 #define TDH_MNG_INIT			21
-#define TDH_VP_INIT			22
+#define TDH_VP_INIT			SEAMCALL_LEAF_VER(22, 1)
 #define TDH_PHYMEM_PAGE_RDMD		24
 #define TDH_VP_RD			26
 #define TDH_PHYMEM_PAGE_RECLAIM		28
@@ -50,14 +63,6 @@
 #define TDH_SYS_UPDATE			53
 #define TDH_SYS_DISABLE			69
 
-/*
- * SEAMCALL leaf:
- *
- * Bit 15:0	Leaf number
- * Bit 23:16	Version number
- */
-#define TDX_VERSION_SHIFT		16
-
 /* TDX page types */
 #define	PT_NDA		0x0
 #define	PT_RSVD		0x1
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index b15269b5941d..2a03152796e6 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1903,8 +1903,7 @@ u64 tdh_vp_init(struct tdx_vp *vp, u64 initial_rcx, u32 x2apicid)
 		.r8 = x2apicid,
 	};
 
-	/* apicid requires version == 1. */
-	return seamcall(TDH_VP_INIT | (1ULL << TDX_VERSION_SHIFT), &args);
+	return seamcall(TDH_VP_INIT, &args);
 }
 EXPORT_SYMBOL_FOR_KVM(tdh_vp_init);

---

## [3] Xu Yilun — 2026-06-18
*Subject: [PATCH v2 02/17] x86/virt/tdx: Configure add-on features on TDX module init and update*

In addition to basic TDX functionalities, TDX module provides add-on
features that can be progressively enabled as the kernel supports them.
The kernel should explicitly configure these features at boot or
post-update initialization time. Configuring an add-on feature, such as
TDX Quoting, that uses extension SEAMCALLs is the prerequisite for
initializing TDX module extensions. TDX Quoting is the target feature to
enable but defer it for now until full kernel support is in place.

TDX module extends TDH.SYS.CONFIG and TDH.SYS.UPDATE with new bitmap
input parameters to specify which add-on features to configure. The
bitmap uses the same definitions as TDX_FEATURES0.

For runtime update, Linux applies a policy that no newer features should
be added after update to avoid disrupting live TDX operations. To adhere
to this, TDH.SYS.UPDATE must configure the same features as the
TDH.SYS.CONFIG. Record the kernel required add-on feature bitmap in a
global var so that both phases can use it.

TDX module advances the version of TDH.SYS.CONFIG and TDH.SYS.UPDATE for
the change, so use the latest version (v1) for add-on feature enabling.
But supporting existing modules which only support v0 is still necessary
until they are deprecated. In fact, it is unlikely that TDH.SYS.CONFIG
ever needs to change again and the code would stay in v1. So there is
little value in worrying about deprecating v0 to save a couple lines of
code in 5-7 years when these original TDX platforms sunset.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 arch/x86/virt/vmx/tdx/tdx.h |  6 ++++--
 arch/x86/virt/vmx/tdx/tdx.c | 28 ++++++++++++++++++++++++++--
 2 files changed, 30 insertions(+), 4 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index fbb520704662..a47e872480c7 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -58,9 +58,11 @@
 #define TDH_PHYMEM_CACHE_WB		40
 #define TDH_PHYMEM_PAGE_WBINVD		41
 #define TDH_VP_WR			43
-#define TDH_SYS_CONFIG			45
+#define TDH_SYS_CONFIG_V0		45
+#define TDH_SYS_CONFIG			SEAMCALL_LEAF_VER(TDH_SYS_CONFIG_V0, 1)
 #define TDH_SYS_SHUTDOWN		52
-#define TDH_SYS_UPDATE			53
+#define TDH_SYS_UPDATE_V0		53
+#define TDH_SYS_UPDATE			SEAMCALL_LEAF_VER(TDH_SYS_UPDATE_V0, 1)
 #define TDH_SYS_DISABLE			69
 
 /* TDX page types */
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 2a03152796e6..92305b5ea90d 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -57,6 +57,7 @@ static struct tdx_module_state tdx_module_state;
 static u32 tdx_global_keyid __ro_after_init;
 static u32 tdx_guest_keyid_start __ro_after_init;
 static u32 tdx_nr_guest_keyids __ro_after_init;
+static u64 tdx_addon_feature0 __ro_after_init;
 
 static DEFINE_IDA(tdx_guest_keyid_pool);
 
@@ -1004,9 +1005,18 @@ static __init int construct_tdmrs(struct list_head *tmb_list,
 	return ret;
 }
 
+static __init void set_tdx_addon_features(void)
+{
+	/*
+	 * To add DICE-based TDX Quoting feature bit in tdx_addon_feature0 when
+	 * kernel is ready.
+	 */
+}
+
 static __init int config_tdx_module(struct tdmr_info_list *tdmr_list,
 				    u64 global_keyid)
 {
+	u64 seamcall_fn = TDH_SYS_CONFIG_V0;
 	struct tdx_module_args args = {};
 	u64 *tdmr_pa_array;
 	size_t array_sz;
@@ -1032,7 +1042,15 @@ static __init int config_tdx_module(struct tdmr_info_list *tdmr_list,
 	args.rcx = __pa(tdmr_pa_array);
 	args.rdx = tdmr_list->nr_consumed_tdmrs;
 	args.r8 = global_keyid;
-	ret = seamcall_prerr(TDH_SYS_CONFIG, &args);
+
+	set_tdx_addon_features();
+
+	if (tdx_addon_feature0) {
+		args.r9 = tdx_addon_feature0;
+		seamcall_fn = TDH_SYS_CONFIG;
+	}
+
+	ret = seamcall_prerr(seamcall_fn, &args);
 
 	/* Free the array as it is not required anymore. */
 	kfree(tdmr_pa_array);
@@ -1314,10 +1332,16 @@ int tdx_module_shutdown(void)
 
 int tdx_module_run_update(void)
 {
+	u64 seamcall_fn = TDH_SYS_UPDATE_V0;
 	struct tdx_module_args args = {};
 	int ret;
 
-	ret = seamcall_prerr(TDH_SYS_UPDATE, &args);
+	if (tdx_addon_feature0) {
+		args.r9 = tdx_addon_feature0;
+		seamcall_fn = TDH_SYS_UPDATE;
+	}
+
+	ret = seamcall_prerr(seamcall_fn, &args);
 	if (ret)
 		return ret;

---

## [4] Xu Yilun — 2026-06-18
*Subject: [PATCH v2 03/17] x86/virt/tdx: Detect if the extensions initialization is required*

TDX module extensions support extension SEAMCALLs that are preemptible
and resumable, unlike normal SEAMCALLs that run to completion while
monopolizing the CPU. This allows for higher-level API constructions,
so better supports some add-on features that implement higher order
security protocols.

Add infrastructure to initialize TDX module extensions. Introduce the
initial step of this process by detecting if the extensions are required
by checking:

  1. If the extensions are supported via TDX_FEATURES0_EXT.
  2. If any TDX add-on feature needs the extensions via a boolean
     metadata field ext_required.

Currently all metadata fields are read at the very beginning of basic
TDX initialization and stored in a global var. However, ext_required is
only valid after the add-on feature configuration, making it
incompatible with the existing metadata reading method.

To resolve this lifetime conflict, add a dedicated runtime metadata
reading interface for the extensions, call it when the extensions
initialization starts, and leave the field out of the global var. In
this way, there is no confusion of when the metadata should be read.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 arch/x86/include/asm/tdx.h                  |  1 +
 arch/x86/include/asm/tdx_global_metadata.h  |  4 ++++
 arch/x86/virt/vmx/tdx/tdx.c                 | 25 +++++++++++++++++++++
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c | 14 ++++++++++++
 4 files changed, 44 insertions(+)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index e5a9cf656c07..5fbf89d5317c 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -35,6 +35,7 @@
 /* Bit definitions of TDX_FEATURES0 metadata field */
 #define TDX_FEATURES0_TD_PRESERVING	BIT_ULL(1)
 #define TDX_FEATURES0_NO_RBP_MOD	BIT_ULL(18)
+#define TDX_FEATURES0_EXT		BIT_ULL(39)
 
 #ifndef __ASSEMBLER__
 
diff --git a/arch/x86/include/asm/tdx_global_metadata.h b/arch/x86/include/asm/tdx_global_metadata.h
index 41150d546589..83fc657a438e 100644
--- a/arch/x86/include/asm/tdx_global_metadata.h
+++ b/arch/x86/include/asm/tdx_global_metadata.h
@@ -52,4 +52,8 @@ struct tdx_sys_info {
 	struct tdx_sys_info_td_conf td_conf;
 };
 
+struct tdx_sys_info_ext {
+	bool ext_required;
+};
+
 #endif
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 92305b5ea90d..6f3596f11d25 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1166,6 +1166,27 @@ static __init int init_tdmrs(struct tdmr_info_list *tdmr_list)
 	return 0;
 }
 
+static __init int init_tdx_module_extensions(void)
+{
+	struct tdx_sys_info_ext sysinfo_ext;
+	int ret;
+
+	if (!(tdx_sysinfo.features.tdx_features0 & TDX_FEATURES0_EXT))
+		return 0;
+
+	ret = get_tdx_sys_info_ext(&sysinfo_ext);
+	if (ret)
+		return ret;
+
+	/* Skip if no feature requires TDX module extensions. */
+	if (!sysinfo_ext.ext_required)
+		return 0;
+
+	/* TODO: add the extensions enabling steps here */
+
+	return 0;
+}
+
 static __init int init_tdx_module(void)
 {
 	int ret;
@@ -1220,6 +1241,10 @@ static __init int init_tdx_module(void)
 	if (ret)
 		goto err_reset_pamts;
 
+	ret = init_tdx_module_extensions();
+	if (ret)
+		goto err_reset_pamts;
+
 	pr_info("%lu KB allocated for PAMT\n", tdmrs_count_pamt_kb(&tdx_tdmr_list));
 
 out_put_tdxmem:
diff --git a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
index e49c300f23d4..b9e1c011a990 100644
--- a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
+++ b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
@@ -131,3 +131,17 @@ static __init int get_tdx_sys_info(struct tdx_sys_info *sysinfo)
 
 	return ret;
 }
+
+static __init int get_tdx_sys_info_ext(struct tdx_sys_info_ext *sysinfo_ext)
+{
+	int ret;
+	u64 val;
+
+	ret = read_sys_metadata_field(0x3100000000000001, &val);
+	if (ret)
+		return ret;
+
+	sysinfo_ext->ext_required = val;
+
+	return 0;
+}

---

## [5] Xu Yilun — 2026-06-18
*Subject: [PATCH v2 04/17] x86/virt/tdx: Add extra memory to TDX module for the extensions*

TDX module extensions receive a one-time memory allocation at
initialization time. The extensions use this memory as the baseline for
their internal states and data required by the service APIs they offer.

Add a new memory feeding process backed by a new SEAMCALL
TDH.EXT.MEM.ADD. The process is mostly the same as adding PAMT. The
kernel queries TDX module how much memory needed by reading the
memory_pool_required_pages, allocates it, hands it over to the module,
and never gets it back.

TDH.EXT.MEM.ADD uses a new parameter type, HPA_LIST_INFO, to provide
this memory. This type represents a list of pages for TDX module to
access. It references an 'hpa_list page' which contains the list of
target HPAs. It collapses the HPA of the hpa_list page and the number
of valid target HPAs into a 64 bit raw value for SEAMCALL parameters.
The hpa_list page is always a medium, TDX module never keeps the
hpa_list page.

Don't CLFLUSH the pages handed to the TDX module, as is done for some
other SEAMCALLs. The flushing operation is not expected to be needed for
current and known future architectures. As more and more page feeding
interfaces to come, the conservative flushing operation becomes a
maintenance burden.

For now, TDX module extensions consume tens of megabytes memory that
will never be returned to host. Use contiguous page allocation to
isolate these large blocks entirely, avoiding permanent memory
fragmentation and reducing buddy allocator efficiency. Print the
allocation amount on TDX module extensions initialization for
visibility.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 arch/x86/include/asm/tdx_global_metadata.h  |   1 +
 arch/x86/virt/vmx/tdx/tdx.h                 |   1 +
 arch/x86/virt/vmx/tdx/tdx.c                 | 107 +++++++++++++++++++-
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c |   6 ++
 4 files changed, 112 insertions(+), 3 deletions(-)

diff --git a/arch/x86/include/asm/tdx_global_metadata.h b/arch/x86/include/asm/tdx_global_metadata.h
index 83fc657a438e..b3442b7c88bb 100644
--- a/arch/x86/include/asm/tdx_global_metadata.h
+++ b/arch/x86/include/asm/tdx_global_metadata.h
@@ -53,6 +53,7 @@ struct tdx_sys_info {
 };
 
 struct tdx_sys_info_ext {
+	u32 memory_pool_required_pages;
 	bool ext_required;
 };
 
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index a47e872480c7..a100634087e7 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -63,6 +63,7 @@
 #define TDH_SYS_SHUTDOWN		52
 #define TDH_SYS_UPDATE_V0		53
 #define TDH_SYS_UPDATE			SEAMCALL_LEAF_VER(TDH_SYS_UPDATE_V0, 1)
+#define TDH_EXT_MEM_ADD			61
 #define TDH_SYS_DISABLE			69
 
 /* TDX page types */
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 6f3596f11d25..dab17822c1c6 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -31,6 +31,7 @@
 #include <linux/syscore_ops.h>
 #include <linux/idr.h>
 #include <linux/kvm_types.h>
+#include <linux/bitfield.h>
 #include <asm/page.h>
 #include <asm/special_insns.h>
 #include <asm/msr-index.h>
@@ -1166,6 +1167,108 @@ static __init int init_tdmrs(struct tdmr_info_list *tdmr_list)
 	return 0;
 }
 
+#define HPA_LIST_INFO_FIRST_ENTRY	GENMASK_U64(11, 3)
+#define HPA_LIST_INFO_PFN		GENMASK_U64(51, 12)
+#define HPA_LIST_INFO_LAST_ENTRY	GENMASK_U64(63, 55)
+
+static __init u64 to_hpa_list_info(struct page *hpa_list_page,
+				   unsigned int nr_pages)
+{
+	return FIELD_PREP(HPA_LIST_INFO_FIRST_ENTRY, 0) |
+	       FIELD_PREP(HPA_LIST_INFO_PFN, page_to_pfn(hpa_list_page)) |
+	       FIELD_PREP(HPA_LIST_INFO_LAST_ENTRY, nr_pages - 1);
+}
+
+static __init int tdx_ext_mem_add(struct page *hpa_list_page,
+				  unsigned int nr_pages)
+{
+	struct tdx_module_args args = {
+		.rcx = to_hpa_list_info(hpa_list_page, nr_pages),
+	};
+	u64 r;
+
+	do {
+		/*
+		 * TDH_EXT_MEM_ADD is designed to use output parameter RCX to
+		 * override/update input parameter RCX, so the caller doesn't
+		 * have to do manual parameter update on retry call.
+		 */
+		r = seamcall_ret(TDH_EXT_MEM_ADD, &args);
+	} while (r == TDX_INTERRUPTED_RESUMABLE);
+
+	if (r != TDX_SUCCESS)
+		return -EFAULT;
+
+	return 0;
+}
+
+struct tdx_hpa_list {
+	u64 phys[PAGE_SIZE / sizeof(u64)];
+};
+
+static_assert(sizeof(struct tdx_hpa_list) == PAGE_SIZE);
+
+static __init int tdx_ext_mem_setup(unsigned int required_pages)
+{
+	struct tdx_hpa_list *hpa_list;
+	struct page *page;
+	unsigned int i;
+	int ret;
+
+	/*
+	 * memory_pool_required_pages == 0 means no need to add pages,
+	 * skip the memory setup.
+	 */
+	if (!required_pages)
+		return 0;
+
+	hpa_list = kzalloc_obj(*hpa_list);
+	if (!hpa_list)
+		return -ENOMEM;
+
+	page = alloc_contig_pages(required_pages, GFP_KERNEL, numa_mem_id(),
+				  &node_online_map);
+	if (!page) {
+		ret = -ENOMEM;
+		goto out_free_hpa_list;
+	}
+
+	i = 0;
+	while (i < required_pages) {
+		unsigned int nents = min(required_pages - i,
+					 ARRAY_SIZE(hpa_list->phys));
+		unsigned int j;
+
+		for (j = 0; j < nents; j++)
+			hpa_list->phys[j] = page_to_phys(page + i + j);
+
+		ret = tdx_ext_mem_add(virt_to_page(hpa_list), nents);
+		/*
+		 * No SEAMCALLs to reclaim the added pages. For simple error
+		 * handling, leak all pages.
+		 */
+		WARN(ret, "Fatal: TDX module rejected (%d) memory for extensions, stranded all pages\n",
+		     ret);
+		if (ret)
+			break;
+
+		i += nents;
+	}
+
+	/*
+	 * Memory for extensions can't be reclaimed once added, print out the
+	 * amount, stop tracking it and free the hpa_list page, no matter
+	 * success or failure.
+	 */
+	pr_info("%lu KB consumed for TDX module extensions\n",
+		required_pages * PAGE_SIZE / 1024);
+
+out_free_hpa_list:
+	kfree(hpa_list);
+
+	return ret;
+}
+
 static __init int init_tdx_module_extensions(void)
 {
 	struct tdx_sys_info_ext sysinfo_ext;
@@ -1182,9 +1285,7 @@ static __init int init_tdx_module_extensions(void)
 	if (!sysinfo_ext.ext_required)
 		return 0;
 
-	/* TODO: add the extensions enabling steps here */
-
-	return 0;
+	return tdx_ext_mem_setup(sysinfo_ext.memory_pool_required_pages);
 }
 
 static __init int init_tdx_module(void)
diff --git a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
index b9e1c011a990..720cdaf76492 100644
--- a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
+++ b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
@@ -137,6 +137,12 @@ static __init int get_tdx_sys_info_ext(struct tdx_sys_info_ext *sysinfo_ext)
 	int ret;
 	u64 val;
 
+	ret = read_sys_metadata_field(0x3100000200000000, &val);
+	if (ret)
+		return ret;
+
+	sysinfo_ext->memory_pool_required_pages = val;
+
 	ret = read_sys_metadata_field(0x3100000000000001, &val);
 	if (ret)
 		return ret;

---

## [6] Xu Yilun — 2026-06-18
*Subject: [PATCH v2 05/17] x86/virt/tdx: Make TDX module initialize the extensions*

After providing all required memory to TDX module, initialize TDX
module extensions via TDH.EXT.INIT, so extension SEAMCALLs can be used.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Reviewed-by: Xiaoyao Li <xiaoyao.li@intel.com>
Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>
Reviewed-by: Adrian Hunter <adrian.hunter@intel.com>
---
 arch/x86/virt/vmx/tdx/tdx.h |  1 +
 arch/x86/virt/vmx/tdx/tdx.c | 22 +++++++++++++++++++++-
 2 files changed, 22 insertions(+), 1 deletion(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index a100634087e7..2deb0a5c902e 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -63,6 +63,7 @@
 #define TDH_SYS_SHUTDOWN		52
 #define TDH_SYS_UPDATE_V0		53
 #define TDH_SYS_UPDATE			SEAMCALL_LEAF_VER(TDH_SYS_UPDATE_V0, 1)
+#define TDH_EXT_INIT			60
 #define TDH_EXT_MEM_ADD			61
 #define TDH_SYS_DISABLE			69
 
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index dab17822c1c6..900928de373a 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1167,6 +1167,22 @@ static __init int init_tdmrs(struct tdmr_info_list *tdmr_list)
 	return 0;
 }
 
+/* Initialize TDX module extensions for extension SEAMCALLs */
+static __init int tdx_ext_init(void)
+{
+	struct tdx_module_args args = {};
+	u64 r;
+
+	do {
+		r = seamcall(TDH_EXT_INIT, &args);
+	} while (r == TDX_INTERRUPTED_RESUMABLE);
+
+	if (r != TDX_SUCCESS)
+		return -EFAULT;
+
+	return 0;
+}
+
 #define HPA_LIST_INFO_FIRST_ENTRY	GENMASK_U64(11, 3)
 #define HPA_LIST_INFO_PFN		GENMASK_U64(51, 12)
 #define HPA_LIST_INFO_LAST_ENTRY	GENMASK_U64(63, 55)
@@ -1285,7 +1301,11 @@ static __init int init_tdx_module_extensions(void)
 	if (!sysinfo_ext.ext_required)
 		return 0;
 
-	return tdx_ext_mem_setup(sysinfo_ext.memory_pool_required_pages);
+	ret = tdx_ext_mem_setup(sysinfo_ext.memory_pool_required_pages);
+	if (ret)
+		return ret;
+
+	return tdx_ext_init();
 }
 
 static __init int init_tdx_module(void)

---

## [7] Xu Yilun — 2026-06-18
*Subject: [PATCH v2 06/17] x86/virt/tdx: Re-initialize the extensions on runtime TDX module update*

Runtime TDX module update introduces a mechanism to update the module
firmware while preserving and restoring TDX operations. As part of the
restoration process, the host must re-execute all extensions
initialization steps to restore extension SEAMCALL functionality.

However, Linux runs the update in stop_machine() context, which prevents
memory allocation. This introduces a hard restriction that the updated
TDX environment must not consume more memory for the extensions.
Consequently, the post-update initialization for the extensions is
implemented as:

  1. Detect if the extensions are supported and required.
  2. Detect if the extensions require additional memory. If yes, fail
     the update.
  3. Initialize the extensions via TDH.EXT.INIT.

The memory allocation problem is greatly mitigated since Linux applies
a policy that configures the same add-on features for boot and for
update. This policy minimizes the chance of increased memory demand. So
now the restriction only affects the compatibility rule for choosing the
update image.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 arch/x86/virt/vmx/tdx/tdx.c                 | 31 ++++++++++++++++++++-
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c |  2 +-
 2 files changed, 31 insertions(+), 2 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 900928de373a..4d2940f4538a 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1168,7 +1168,7 @@ static __init int init_tdmrs(struct tdmr_info_list *tdmr_list)
 }
 
 /* Initialize TDX module extensions for extension SEAMCALLs */
-static __init int tdx_ext_init(void)
+static int tdx_ext_init(void)
 {
 	struct tdx_module_args args = {};
 	u64 r;
@@ -1308,6 +1308,31 @@ static __init int init_tdx_module_extensions(void)
 	return tdx_ext_init();
 }
 
+/*
+ * Mostly the same flow as init_tdx_module_extensions(), but rejects adding
+ * more memory.
+ */
+static int update_tdx_module_extensions(void)
+{
+	struct tdx_sys_info_ext sysinfo_ext;
+	int ret;
+
+	if (!(tdx_sysinfo.features.tdx_features0 & TDX_FEATURES0_EXT))
+		return 0;
+
+	ret = get_tdx_sys_info_ext(&sysinfo_ext);
+	if (ret)
+		return ret;
+
+	if (!sysinfo_ext.ext_required)
+		return 0;
+
+	if (sysinfo_ext.memory_pool_required_pages)
+		return -EFAULT;
+
+	return tdx_ext_init();
+}
+
 static __init int init_tdx_module(void)
 {
 	int ret;
@@ -1498,6 +1523,10 @@ int tdx_module_run_update(void)
 	 */
 	WARN_ON_ONCE(ret);
 
+	ret = update_tdx_module_extensions();
+	if (ret)
+		return ret;
+
 	tdx_module_state.initialized = true;
 	return 0;
 }
diff --git a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
index 720cdaf76492..84364da89649 100644
--- a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
+++ b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
@@ -132,7 +132,7 @@ static __init int get_tdx_sys_info(struct tdx_sys_info *sysinfo)
 	return ret;
 }
 
-static __init int get_tdx_sys_info_ext(struct tdx_sys_info_ext *sysinfo_ext)
+static int get_tdx_sys_info_ext(struct tdx_sys_info_ext *sysinfo_ext)
 {
 	int ret;
 	u64 val;

---

## [8] Xu Yilun — 2026-06-18
*Subject: [PATCH v2 07/17] x86/virt/tdx: Initialize Quoting extension*

From: Peter Fang <peter.fang@intel.com>

Initialize the Quoting extension during TDX bringup, after enabling TDX
module Extension.

Because Quoting is an optional TDX feature, do not let initialization
failures cause TDX bringup to fail. In that case, TDX can fall back to
the existing userspace flow via a KVM return code.

Only lay the groundwork for TDX Quoting support. Leave the opt-in
portion of the initialization to a follow-up patch after fully
implementing the feature.

Signed-off-by: Peter Fang <peter.fang@intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 arch/x86/include/asm/tdx.h  |  1 +
 arch/x86/virt/vmx/tdx/tdx.h |  1 +
 arch/x86/virt/vmx/tdx/tdx.c | 34 +++++++++++++++++++++++++++++++++-
 3 files changed, 35 insertions(+), 1 deletion(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 5fbf89d5317c..741fd97cc199 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -36,6 +36,7 @@
 #define TDX_FEATURES0_TD_PRESERVING	BIT_ULL(1)
 #define TDX_FEATURES0_NO_RBP_MOD	BIT_ULL(18)
 #define TDX_FEATURES0_EXT		BIT_ULL(39)
+#define TDX_FEATURES0_QUOTE		BIT_ULL(50)
 
 #ifndef __ASSEMBLER__
 
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index 2deb0a5c902e..1afa0b10dfc9 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -66,6 +66,7 @@
 #define TDH_EXT_INIT			60
 #define TDH_EXT_MEM_ADD			61
 #define TDH_SYS_DISABLE			69
+#define TDH_QUOTE_INIT			100
 
 /* TDX page types */
 #define	PT_NDA		0x0
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 4d2940f4538a..06c42b86b05e 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1167,6 +1167,32 @@ static __init int init_tdmrs(struct tdmr_info_list *tdmr_list)
 	return 0;
 }
 
+/* Initialize quoting extension */
+static __init int tdx_quote_init(void)
+{
+	struct tdx_module_args args = {};
+	u64 r;
+
+	do {
+		r = seamcall(TDH_QUOTE_INIT, &args);
+	} while (r == TDX_INTERRUPTED_RESUMABLE);
+
+	if (r != TDX_SUCCESS)
+		return -EFAULT;
+
+	return 0;
+}
+
+static __init void init_tdx_quoting_extension(void)
+{
+	int ret;
+
+	if (tdx_addon_feature0 & TDX_FEATURES0_QUOTE) {
+		ret = tdx_quote_init();
+		WARN_ON_ONCE(ret);
+	}
+}
+
 /* Initialize TDX module extensions for extension SEAMCALLs */
 static int tdx_ext_init(void)
 {
@@ -1305,7 +1331,13 @@ static __init int init_tdx_module_extensions(void)
 	if (ret)
 		return ret;
 
-	return tdx_ext_init();
+	ret = tdx_ext_init();
+	if (ret)
+		return ret;
+
+	init_tdx_quoting_extension();
+
+	return 0;
 }
 
 /*

---

## [9] Xu Yilun — 2026-06-18
*Subject: [PATCH v2 08/17] x86/virt/tdx: Prepare Quote buffer during extension bringup*

From: Peter Fang <peter.fang@intel.com>

During TDX attestation, the TDX guest asks the host to generate a
signed, verifiable structure (a "Quote"). With the Quoting extension,
the TDX module returns the Quote in pages that the host shares via an
Extension-SEAMCALL.

The SEAMCALL accepts the host buffer pages as a linked list of 4KB
"HPA_LINKED_LIST" nodes. Each entry holds the physical address of a 4KB
data page, except for the last entry, which points to the next node. The
TDX module reports the required Quote buffer size through a global
metadata field. See [1] for details.

For simplicity, let all guests share a global buffer. Build the buffer's
HPA_LINKED_LIST at Quoting extension bringup. This saves a bunch of
va-to-pa conversions at runtime.

[1] Intel TDX Module ABI specification, Section "Physical Memory
    Management Types"

Signed-off-by: Peter Fang <peter.fang@intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 arch/x86/include/asm/tdx_global_metadata.h  |   4 +
 arch/x86/virt/vmx/tdx/tdx.c                 | 115 +++++++++++++++++++-
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c |  14 +++
 3 files changed, 129 insertions(+), 4 deletions(-)

diff --git a/arch/x86/include/asm/tdx_global_metadata.h b/arch/x86/include/asm/tdx_global_metadata.h
index b3442b7c88bb..17cb13a1bb40 100644
--- a/arch/x86/include/asm/tdx_global_metadata.h
+++ b/arch/x86/include/asm/tdx_global_metadata.h
@@ -57,4 +57,8 @@ struct tdx_sys_info_ext {
 	bool ext_required;
 };
 
+struct tdx_sys_info_quote {
+	u32 max_quote_size;
+};
+
 #endif
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 06c42b86b05e..9716424a301f 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -32,6 +32,7 @@
 #include <linux/idr.h>
 #include <linux/kvm_types.h>
 #include <linux/bitfield.h>
+#include <linux/vmalloc.h>
 #include <asm/page.h>
 #include <asm/special_insns.h>
 #include <asm/msr-index.h>
@@ -71,6 +72,24 @@ static LIST_HEAD(tdx_memlist);
 
 static struct tdx_sys_info tdx_sysinfo;
 
+/*
+ * Quote buffer shared with the TDX module for quote generation, in HPA linked
+ * list format.
+ *
+ * @buf: Virtual address of the quote buffer.
+ * @buf_len: Size of @buf in bytes.
+ * @hpa_entries: HPA entries, starting at the first list node.
+ * @hpa_entries_pa: Physical address for @hpa_entries.
+ */
+struct tdx_quote_data {
+	void		*buf;
+	u64		buf_len;
+	u64		*hpa_entries;
+	phys_addr_t	hpa_entries_pa;
+};
+
+static struct tdx_quote_data tdx_quote;
+
 static DEFINE_RAW_SPINLOCK(sysinit_lock);
 
 /*
@@ -1167,6 +1186,81 @@ static __init int init_tdmrs(struct tdmr_info_list *tdmr_list)
 	return 0;
 }
 
+static inline phys_addr_t tdx_vmalloc_to_pa(const void *addr)
+{
+	unsigned long pfn = vmalloc_to_pfn(addr);
+
+	return PFN_PHYS(pfn);
+}
+
+#define HPAS_PER_NODE			(PAGE_SIZE / sizeof(u64))
+
+/*
+ * Pass the quote buffer to the TDX module as an HPA linked list, where each
+ * node holds 4KB page HPAs and the last entry points to the next node.
+ */
+static __init int tdx_quote_create_buf(unsigned int npages,
+				       struct tdx_quote_data *qdata)
+{
+	unsigned int nnodes;
+	u64 *hpas;
+	void *qbuf;
+	int i, j;
+
+	if (!npages)
+		return -EINVAL;
+
+	/*
+	 * Each node holds up to (HPAS_PER_NODE - 1) 4KB page HPAs.
+	 * The last entry of the node points to the next node.
+	 */
+	nnodes = DIV_ROUND_UP(npages, HPAS_PER_NODE - 1);
+
+	hpas = vmalloc_array(nnodes, PAGE_SIZE);
+	if (!hpas)
+		return -ENOMEM;
+
+	/*
+	 * ~0ULL is the list terminator for HPA_LINKED_LIST.
+	 *
+	 * Pre-fill the last node with 0xff bytes so that unused entries are
+	 * terminators. Overwrite populated entries later.
+	 */
+	memset((u8 *)hpas + (nnodes - 1) * PAGE_SIZE, 0xff, PAGE_SIZE);
+
+	qbuf = vcalloc(npages, PAGE_SIZE);
+	if (!qbuf)
+		goto out_nomem;
+
+	/* Populate the linked list */
+	for (i = 0, j = 0; j < npages; i++) {
+		if ((i % HPAS_PER_NODE) == HPAS_PER_NODE - 1) {
+			/*
+			 * The last node entry always points to the next node.
+			 * The address of the following entry must be on next
+			 * node's page boundary.
+			 */
+			hpas[i] = tdx_vmalloc_to_pa(&hpas[i + 1]);
+			continue;
+		}
+
+		hpas[i] = tdx_vmalloc_to_pa((u8 *)qbuf + j * PAGE_SIZE);
+		j++;
+	}
+
+	qdata->buf = qbuf;
+	qdata->buf_len = (u64)npages * PAGE_SIZE;
+	qdata->hpa_entries = hpas;
+	qdata->hpa_entries_pa = tdx_vmalloc_to_pa(hpas);
+
+	return 0;
+
+out_nomem:
+	vfree(hpas);
+
+	return -ENOMEM;
+}
+
 /* Initialize quoting extension */
 static __init int tdx_quote_init(void)
 {
@@ -1185,12 +1279,25 @@ static __init int tdx_quote_init(void)
 
 static __init void init_tdx_quoting_extension(void)
 {
-	int ret;
+	struct tdx_sys_info_quote sysinfo_quote;
+	unsigned int nr_quote_pages;
+
+	if (!(tdx_addon_feature0 & TDX_FEATURES0_QUOTE))
+		return;
 
-	if (tdx_addon_feature0 & TDX_FEATURES0_QUOTE) {
-		ret = tdx_quote_init();
-		WARN_ON_ONCE(ret);
+	if (tdx_quote_init()) {
+		WARN_ON_ONCE(1);
+		return;
 	}
+
+	/* Quoting metadata is valid only after initialization */
+	if (get_tdx_sys_info_quote(&sysinfo_quote))
+		return;
+
+	nr_quote_pages = PAGE_ALIGN(sysinfo_quote.max_quote_size) /
+			 PAGE_SIZE;
+	if (tdx_quote_create_buf(nr_quote_pages, &tdx_quote))
+		pr_err("Failed to create quote buffer\n");
 }
 
 /* Initialize TDX module extensions for extension SEAMCALLs */
diff --git a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
index 84364da89649..1eb2985307c6 100644
--- a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
+++ b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
@@ -151,3 +151,17 @@ static int get_tdx_sys_info_ext(struct tdx_sys_info_ext *sysinfo_ext)
 
 	return 0;
 }
+
+static __init int get_tdx_sys_info_quote(struct tdx_sys_info_quote *sysinfo_quote)
+{
+	int ret;
+	u64 val;
+
+	ret = read_sys_metadata_field(0x2300000200000002, &val);
+	if (ret)
+		return ret;
+
+	sysinfo_quote->max_quote_size = val;
+
+	return 0;
+}

---

## [10] Xu Yilun — 2026-06-18
*Subject: [PATCH v2 09/17] x86/virt/tdx: Add interface to check Quoting availability*

From: Peter Fang <peter.fang@intel.com>

KVM needs to know if the Quoting extension is available to determine
whether userspace must be involved in Quote generation.

Since the Quote buffer is always created during Quoting extension
bringup, checking whether the buffer exists is sufficient.

Signed-off-by: Peter Fang <peter.fang@intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 arch/x86/include/asm/tdx.h  |  2 ++
 arch/x86/virt/vmx/tdx/tdx.c | 10 ++++++++++
 2 files changed, 12 insertions(+)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 741fd97cc199..9432a736855e 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -147,6 +147,8 @@ struct tdx_vp {
 	struct page **tdcx_pages;
 };
 
+bool tdx_quote_enabled(void);
+
 static inline u64 mk_keyed_paddr(u16 hkid, struct page *page)
 {
 	u64 ret;
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 9716424a301f..da55c1aeeeb8 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1193,6 +1193,16 @@ static inline phys_addr_t tdx_vmalloc_to_pa(const void *addr)
 	return PFN_PHYS(pfn);
 }
 
+bool tdx_quote_enabled(void)
+{
+	/*
+	 * No need for locking here. The quote buffer is initialized as part of
+	 * core TDX bringup, which comes before KVM is ready for userspace.
+	 */
+	return !!tdx_quote.buf;
+}
+EXPORT_SYMBOL_FOR_KVM(tdx_quote_enabled);
+
 #define HPAS_PER_NODE			(PAGE_SIZE / sizeof(u64))
 
 /*

---

## [11] Xu Yilun — 2026-06-18
*Subject: [PATCH v2 10/17] x86/virt/tdx: Move tdx_tdr_pa() up in the file*

From: Peter Fang <peter.fang@intel.com>

Move tdx_tdr_pa() earlier in the file to prepare for upcoming changes
that add a new Extension-SEAMCALL.

No functional change intended.

Signed-off-by: Peter Fang <peter.fang@intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
---
 arch/x86/virt/vmx/tdx/tdx.c | 10 +++++-----
 1 file changed, 5 insertions(+), 5 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index da55c1aeeeb8..1e2c7a33c7a9 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1186,6 +1186,11 @@ static __init int init_tdmrs(struct tdmr_info_list *tdmr_list)
 	return 0;
 }
 
+static inline u64 tdx_tdr_pa(struct tdx_td *td)
+{
+	return page_to_phys(td->tdr_page);
+}
+
 static inline phys_addr_t tdx_vmalloc_to_pa(const void *addr)
 {
 	unsigned long pfn = vmalloc_to_pfn(addr);
@@ -1966,11 +1971,6 @@ void tdx_guest_keyid_free(unsigned int keyid)
 }
 EXPORT_SYMBOL_FOR_KVM(tdx_guest_keyid_free);
 
-static inline u64 tdx_tdr_pa(struct tdx_td *td)
-{
-	return page_to_phys(td->tdr_page);
-}
-
 /*
  * The TDX module exposes a CLFLUSH_BEFORE_ALLOC bit to specify whether
  * a CLFLUSH of pages is required before handing them to the TDX module.

---

## [12] Xu Yilun — 2026-06-18
*Subject: [PATCH v2 11/17] x86/virt/tdx: Add interface to generate a Quote*

From: Peter Fang <peter.fang@intel.com>

Provide an interface to generate a Quote via the TDH.QUOTE.GET
Extension-SEAMCALL. Although the TDX module may support concurrent Quote
generation, use a single shared buffer for simplicity and serialize
access with a mutex. TDX bringup code already prepares the buffer in the
format required by the TDX module.

Return a per-call buffer containing the Quote so callers don't need to
size the buffer themselves. The caller is responsible for freeing the
returned buffer.

Signed-off-by: Peter Fang <peter.fang@intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 arch/x86/include/asm/tdx.h  |  2 +
 arch/x86/virt/vmx/tdx/tdx.h |  1 +
 arch/x86/virt/vmx/tdx/tdx.c | 77 +++++++++++++++++++++++++++++++++++++
 3 files changed, 80 insertions(+)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 9432a736855e..34764838f132 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -148,6 +148,8 @@ struct tdx_vp {
 };
 
 bool tdx_quote_enabled(void);
+void *tdx_quote_generate(struct tdx_td *td, void *in_data, u32 in_data_len,
+			 u32 *quote_len);
 
 static inline u64 mk_keyed_paddr(u16 hkid, struct page *page)
 {
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index 1afa0b10dfc9..32b13b0c85f9 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -66,6 +66,7 @@
 #define TDH_EXT_INIT			60
 #define TDH_EXT_MEM_ADD			61
 #define TDH_SYS_DISABLE			69
+#define TDH_QUOTE_GET			98
 #define TDH_QUOTE_INIT			100
 
 /* TDX page types */
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 1e2c7a33c7a9..ac0da4966697 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -72,6 +72,8 @@ static LIST_HEAD(tdx_memlist);
 
 static struct tdx_sys_info tdx_sysinfo;
 
+static DEFINE_MUTEX(tdx_quote_lock);
+
 /*
  * Quote buffer shared with the TDX module for quote generation, in HPA linked
  * list format.
@@ -1208,6 +1210,81 @@ bool tdx_quote_enabled(void)
 }
 EXPORT_SYMBOL_FOR_KVM(tdx_quote_enabled);
 
+static u64 tdx_quote_get(struct tdx_td *td, u64 in_data_pa, u64 in_data_len,
+			 u64 hpa_entries_pa, u64 total_len, u64 *quote_len)
+{
+	struct tdx_module_args args = {
+		.rcx = tdx_tdr_pa(td),
+		/* [47:32] QUOTE_ID: All-1s selects the default quote format */
+		.rdx = GENMASK_U64(47, 32),
+		.r8 = in_data_pa,
+		.r9 = in_data_len,
+		.r10 = hpa_entries_pa,
+		.r11 = total_len,
+	};
+	u64 r;
+
+	do {
+		r = seamcall_ret(TDH_QUOTE_GET, &args);
+	} while (r == TDX_INTERRUPTED_RESUMABLE);
+
+	*quote_len = args.rcx;
+
+	return r;
+}
+
+/**
+ * tdx_quote_generate() - Generate a quote for a TD
+ * @td: The TD to generate the quote for.
+ * @in_data: Input data for the quote request.
+ * @in_data_len: Size of @in_data in bytes. Must not exceed one page.
+ * @quote_len: Returned size of the generated quote in bytes.
+ *
+ * Generate a quote using the TDX module. Pass the input data through the quote
+ * buffer and return the quote.
+ *
+ * Return: Newly allocated quote buffer or %NULL on failure.
+ * The caller must free the returned buffer with kvfree().
+ */
+void *tdx_quote_generate(struct tdx_td *td, void *in_data, u32 in_data_len,
+			 u32 *quote_len)
+{
+	struct tdx_quote_data *qdata = &tdx_quote;
+	void *quote_dup = NULL;
+	u64 r, out_len;
+
+	if (!tdx_quote_enabled())
+		return NULL;
+
+	mutex_lock(&tdx_quote_lock);
+
+	/*
+	 * Use the first page of the quote buffer for input data. The buffer
+	 * must be at least one page in size. @in_data may not be page-aligned,
+	 * but TDH.QUOTE.GET expects page-aligned addresses.
+	 */
+	memcpy(qdata->buf, in_data, in_data_len);
+
+	r = tdx_quote_get(td, qdata->hpa_entries[0], in_data_len,
+			  qdata->hpa_entries_pa, qdata->buf_len, &out_len);
+	if (r != TDX_SUCCESS || !out_len || out_len > qdata->buf_len)
+		goto out;
+
+	/*
+	 * The quote buffer is a shared resource, so use it only for the
+	 * SEAMCALL and copy the data out as soon as possible.
+	 */
+	quote_dup = kvmemdup(qdata->buf, out_len, GFP_KERNEL);
+
+	*quote_len = (u32)out_len;
+
+out:
+	mutex_unlock(&tdx_quote_lock);
+
+	return quote_dup;
+}
+EXPORT_SYMBOL_FOR_KVM(tdx_quote_generate);
+
 #define HPAS_PER_NODE			(PAGE_SIZE / sizeof(u64))
 
 /*

---

## [13] Xu Yilun — 2026-06-18
*Subject: [PATCH v2 12/17] x86/virt/tdx: Reinitialize the Quoting extension after TDX module update*

From: Peter Fang <peter.fang@intel.com>

Invoke TDH.QUOTE.INIT again after a runtime module update to trigger the
necessary rekey procedure in the TDX module.

Keep the existing Quote buffer since memory allocation is not permitted
during the update. Compatible TDX module updates must not increase the
Quote buffer size, or an undersized buffer might cause Quote generation
to fail. See [1] for module update details.

[1] Documentation/arch/x86/tdx.rst, Section "TDX module Runtime Update"

Signed-off-by: Peter Fang <peter.fang@intel.com>
---
 arch/x86/virt/vmx/tdx/tdx.c | 31 ++++++++++++++++++++++++++++---
 1 file changed, 28 insertions(+), 3 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index ac0da4966697..81e7b6b1dacb 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1353,8 +1353,11 @@ static __init int tdx_quote_create_buf(unsigned int npages,
 	return -ENOMEM;
 }
 
-/* Initialize quoting extension */
-static __init int tdx_quote_init(void)
+/*
+ * Initialize quoting extension.
+ * It also rekeys the TDX module after a runtime module update.
+ */
+static int tdx_quote_init(void)
 {
 	struct tdx_module_args args = {};
 	u64 r;
@@ -1539,6 +1542,22 @@ static __init int init_tdx_module_extensions(void)
 	return 0;
 }
 
+static void update_tdx_quoting_extension(void)
+{
+	int ret;
+
+	if (tdx_addon_feature0 & TDX_FEATURES0_QUOTE) {
+		/*
+		 * The TDH.QUOTE.INIT call renews the quoting keys.
+		 *
+		 * A module update must not increase the quote buffer size, or
+		 * quote generation may fail and break attestation.
+		 */
+		ret = tdx_quote_init();
+		WARN_ON(ret);
+	}
+}
+
 /*
  * Mostly the same flow as init_tdx_module_extensions(), but rejects adding
  * more memory.
@@ -1561,7 +1580,13 @@ static int update_tdx_module_extensions(void)
 	if (sysinfo_ext.memory_pool_required_pages)
 		return -EFAULT;
 
-	return tdx_ext_init();
+	ret = tdx_ext_init();
+	if (ret)
+		return ret;
+
+	update_tdx_quoting_extension();
+
+	return 0;
 }
 
 static __init int init_tdx_module(void)

---

## [14] Xu Yilun — 2026-06-18
*Subject: [PATCH v2 13/17] x86/virt/tdx: Enable Quoting extension*

From: Peter Fang <peter.fang@intel.com>

The Quoting extension generates TDX attestation Quotes in the TDX
module, without using a discrete Quoting engine. Enable this feature by
requesting it in TDH.SYS.CONFIG and TDH.SYS.UPDATE.

Signed-off-by: Peter Fang <peter.fang@intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 arch/x86/virt/vmx/tdx/tdx.c | 6 ++----
 1 file changed, 2 insertions(+), 4 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 81e7b6b1dacb..01fb01313077 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1029,10 +1029,8 @@ static __init int construct_tdmrs(struct list_head *tmb_list,
 
 static __init void set_tdx_addon_features(void)
 {
-	/*
-	 * To add DICE-based TDX Quoting feature bit in tdx_addon_feature0 when
-	 * kernel is ready.
-	 */
+	if (tdx_sysinfo.features.tdx_features0 & TDX_FEATURES0_QUOTE)
+		tdx_addon_feature0 |= TDX_FEATURES0_QUOTE;
 }
 
 static __init int config_tdx_module(struct tdmr_info_list *tdmr_list,

---

## [15] Xu Yilun — 2026-06-18
*Subject: [PATCH v2 14/17] x86/tdx: Move and rename Quote request structure*

From: Peter Fang <peter.fang@intel.com>

Move struct tdx_quote_buf to tdx.h so it can be shared by the guest
driver and core TDX code, as the host will also need the Quote buffer
format for in-kernel Quote generation.

Rename the struct to tdx_quote_req to better reflect its purpose, and
replace "quote_buf" with "quote_req" in tdx-guest.c.

Signed-off-by: Peter Fang <peter.fang@intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Reviewed-by: Dan Williams <djbw@kernel.org>
---
 arch/x86/include/asm/tdx.h              | 20 +++++++++++
 drivers/virt/coco/tdx-guest/tdx-guest.c | 47 ++++++++-----------------
 2 files changed, 34 insertions(+), 33 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 34764838f132..24bce7512de3 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -66,6 +66,26 @@ struct ve_info {
 	u32 instr_info;
 };
 
+/**
+ * struct tdx_quote_req - Format of Quote request message
+ * @version: Quote format version, filled by TD.
+ * @status: Status code of Quote request, filled by VMM.
+ * @in_len: Length of TDREPORT, filled by TD.
+ * @out_len: Length of Quote data, filled by VMM.
+ * @data: Quote data on output or TDREPORT on input.
+ *
+ * More details of Quote request message can be found in TDX
+ * Guest-Host Communication Interface (GHCI) for Intel TDX 1.0,
+ * section titled "TDG.VP.VMCALL<GetQuote>"
+ */
+struct tdx_quote_req {
+	u64 version;
+	u64 status;
+	u32 in_len;
+	u32 out_len;
+	u8 data[];
+};
+
 #ifdef CONFIG_INTEL_TDX_GUEST
 
 void __init tdx_early_init(void);
diff --git a/drivers/virt/coco/tdx-guest/tdx-guest.c b/drivers/virt/coco/tdx-guest/tdx-guest.c
index a9ecc46df187..c84ace1cbe99 100644
--- a/drivers/virt/coco/tdx-guest/tdx-guest.c
+++ b/drivers/virt/coco/tdx-guest/tdx-guest.c
@@ -171,26 +171,7 @@ static void tdx_mr_deinit(const struct attribute_group *mr_grp)
 #define GET_QUOTE_SUCCESS		0
 #define GET_QUOTE_IN_FLIGHT		0xffffffffffffffff
 
-#define TDX_QUOTE_MAX_LEN		(GET_QUOTE_BUF_SIZE - sizeof(struct tdx_quote_buf))
-
-/* struct tdx_quote_buf: Format of Quote request buffer.
- * @version: Quote format version, filled by TD.
- * @status: Status code of Quote request, filled by VMM.
- * @in_len: Length of TDREPORT, filled by TD.
- * @out_len: Length of Quote data, filled by VMM.
- * @data: Quote data on output or TDREPORT on input.
- *
- * More details of Quote request buffer can be found in TDX
- * Guest-Host Communication Interface (GHCI) for Intel TDX 1.0,
- * section titled "TDG.VP.VMCALL<GetQuote>"
- */
-struct tdx_quote_buf {
-	u64 version;
-	u64 status;
-	u32 in_len;
-	u32 out_len;
-	u8 data[];
-};
+#define TDX_QUOTE_MAX_LEN		(GET_QUOTE_BUF_SIZE - sizeof(struct tdx_quote_req))
 
 /* Quote data buffer */
 static void *quote_data;
@@ -241,7 +222,7 @@ static void *alloc_quote_buf(void)
 
 /*
  * wait_for_quote_completion() - Wait for Quote request completion
- * @quote_buf: Address of Quote buffer.
+ * @quote_req: Address of Quote buffer.
  * @timeout: Timeout in seconds to wait for the Quote generation.
  *
  * As per TDX GHCI v1.0 specification, sec titled "TDG.VP.VMCALL<GetQuote>",
@@ -250,7 +231,7 @@ static void *alloc_quote_buf(void)
  * or error code after processing is complete. So wait till the status
  * changes from GET_QUOTE_IN_FLIGHT or the request being timed out.
  */
-static int wait_for_quote_completion(struct tdx_quote_buf *quote_buf, u32 timeout)
+static int wait_for_quote_completion(struct tdx_quote_req *quote_req, u32 timeout)
 {
 	int i = 0;
 
@@ -258,7 +239,7 @@ static int wait_for_quote_completion(struct tdx_quote_buf *quote_buf, u32 timeou
 	 * Quote requests usually take a few seconds to complete, so waking up
 	 * once per second to recheck the status is fine for this use case.
 	 */
-	while (quote_buf->status == GET_QUOTE_IN_FLIGHT && i++ < timeout) {
+	while (quote_req->status == GET_QUOTE_IN_FLIGHT && i++ < timeout) {
 		if (msleep_interruptible(MSEC_PER_SEC))
 			return -EINTR;
 	}
@@ -269,7 +250,7 @@ static int wait_for_quote_completion(struct tdx_quote_buf *quote_buf, u32 timeou
 static int tdx_report_new_locked(struct tsm_report *report, void *data)
 {
 	u8 *buf;
-	struct tdx_quote_buf *quote_buf = quote_data;
+	struct tdx_quote_req *quote_req = quote_data;
 	struct tsm_report_desc *desc = &report->desc;
 	u32 out_len;
 	int ret;
@@ -280,7 +261,7 @@ static int tdx_report_new_locked(struct tsm_report *report, void *data)
 	 * Quote buf status is still in GET_QUOTE_IN_FLIGHT (owned by
 	 * VMM), don't permit any new request.
 	 */
-	if (quote_buf->status == GET_QUOTE_IN_FLIGHT)
+	if (quote_req->status == GET_QUOTE_IN_FLIGHT)
 		return -EBUSY;
 
 	if (desc->inblob_len != TDX_REPORTDATA_LEN)
@@ -289,11 +270,11 @@ static int tdx_report_new_locked(struct tsm_report *report, void *data)
 	memset(quote_data, 0, GET_QUOTE_BUF_SIZE);
 
 	/* Update Quote buffer header */
-	quote_buf->version = GET_QUOTE_CMD_VER;
-	quote_buf->in_len = TDX_REPORT_LEN;
+	quote_req->version = GET_QUOTE_CMD_VER;
+	quote_req->in_len = TDX_REPORT_LEN;
 
 	ret = tdx_do_report(KERNEL_SOCKPTR(desc->inblob),
-			    KERNEL_SOCKPTR(quote_buf->data));
+			    KERNEL_SOCKPTR(quote_req->data));
 	if (ret)
 		return ret;
 
@@ -303,23 +284,23 @@ static int tdx_report_new_locked(struct tsm_report *report, void *data)
 		return -EIO;
 	}
 
-	ret = wait_for_quote_completion(quote_buf, getquote_timeout);
+	ret = wait_for_quote_completion(quote_req, getquote_timeout);
 	if (ret) {
 		pr_err("GetQuote request timedout\n");
 		return ret;
 	}
 
-	if (quote_buf->status != GET_QUOTE_SUCCESS) {
-		pr_debug("GetQuote request failed, status:%llx\n", quote_buf->status);
+	if (quote_req->status != GET_QUOTE_SUCCESS) {
+		pr_debug("GetQuote request failed, status:%llx\n", quote_req->status);
 		return -EIO;
 	}
 
-	out_len = READ_ONCE(quote_buf->out_len);
+	out_len = READ_ONCE(quote_req->out_len);
 
 	if (out_len > TDX_QUOTE_MAX_LEN)
 		return -EFBIG;
 
-	buf = kvmemdup(quote_buf->data, out_len, GFP_KERNEL);
+	buf = kvmemdup(quote_req->data, out_len, GFP_KERNEL);
 	if (!buf)
 		return -ENOMEM;

---

## [16] Xu Yilun — 2026-06-18
*Subject: [PATCH v2 15/17] KVM: TDX: Factor out userspace return path from tdx_get_quote()*

From: Peter Fang <peter.fang@intel.com>

Separate the logic that returns the GetQuote TDVMCALL exit to userspace
so that tdx_get_quote() can be extended to support in-kernel Quote
generation.

No functional change intended.

Signed-off-by: Peter Fang <peter.fang@intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 arch/x86/kvm/vmx/tdx.c | 25 ++++++++++++++++---------
 1 file changed, 16 insertions(+), 9 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index ed12805bbb44..9f7c39e0d4b5 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1524,6 +1524,20 @@ static int tdx_complete_simple(struct kvm_vcpu *vcpu)
 	return 1;
 }
 
+static int tdx_get_quote_user(struct kvm_vcpu *vcpu, u64 gpa, u64 size)
+{
+	vcpu->run->exit_reason = KVM_EXIT_TDX;
+	vcpu->run->tdx.flags = 0;
+	vcpu->run->tdx.nr = TDVMCALL_GET_QUOTE;
+	vcpu->run->tdx.get_quote.ret = TDVMCALL_STATUS_SUBFUNC_UNSUPPORTED;
+	vcpu->run->tdx.get_quote.gpa = gpa;
+	vcpu->run->tdx.get_quote.size = size;
+
+	vcpu->arch.complete_userspace_io = tdx_complete_simple;
+
+	return 0;
+}
+
 static int tdx_get_quote(struct kvm_vcpu *vcpu)
 {
 	struct vcpu_tdx *tdx = to_tdx(vcpu);
@@ -1536,16 +1550,9 @@ static int tdx_get_quote(struct kvm_vcpu *vcpu)
 		return 1;
 	}
 
-	vcpu->run->exit_reason = KVM_EXIT_TDX;
-	vcpu->run->tdx.flags = 0;
-	vcpu->run->tdx.nr = TDVMCALL_GET_QUOTE;
-	vcpu->run->tdx.get_quote.ret = TDVMCALL_STATUS_SUBFUNC_UNSUPPORTED;
-	vcpu->run->tdx.get_quote.gpa = gpa & ~gfn_to_gpa(kvm_gfn_direct_bits(tdx->vcpu.kvm));
-	vcpu->run->tdx.get_quote.size = size;
-
-	vcpu->arch.complete_userspace_io = tdx_complete_simple;
+	gpa &= ~gfn_to_gpa(kvm_gfn_direct_bits(vcpu->kvm));
 
-	return 0;
+	return tdx_get_quote_user(vcpu, gpa, size);
 }
 
 static int tdx_setup_event_notify_interrupt(struct kvm_vcpu *vcpu)

---

## [17] Xu Yilun — 2026-06-18
*Subject: [PATCH v2 16/17] KVM: TDX: Add in-kernel Quote generation*

From: Peter Fang <peter.fang@intel.com>

Provide an in-kernel path for Quote generation when handling
TDG.VP.VMCALL<GetQuote>, without requiring an exit to userspace.

Use the core TDX API for Quote generation when the Quoting extension is
available. For simplicity, KVM checks its availability once per guest
during initialization. KVM does not handle Quoting service disruptions
or switch between the in-kernel and userspace paths.

Update the KVM API and TDX documentation to describe this new Quoting
capability.

Signed-off-by: Peter Fang <peter.fang@intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 Documentation/arch/x86/tdx.rst |  19 ++---
 Documentation/virt/kvm/api.rst |   3 +
 arch/x86/include/asm/tdx.h     |   9 +++
 arch/x86/kvm/vmx/tdx.h         |   6 ++
 arch/x86/kvm/vmx/tdx.c         | 135 ++++++++++++++++++++++++++++++++-
 virt/kvm/kvm_main.c            |   1 +
 6 files changed, 163 insertions(+), 10 deletions(-)

diff --git a/Documentation/arch/x86/tdx.rst b/Documentation/arch/x86/tdx.rst
index 3303499ad4c6..f02bb6919d91 100644
--- a/Documentation/arch/x86/tdx.rst
+++ b/Documentation/arch/x86/tdx.rst
@@ -522,15 +522,16 @@ provided by attestation service so the TDREPORT can be verified uniquely.
 More details about the TDREPORT can be found in Intel TDX Module
 specification, section titled "TDG.MR.REPORT Leaf".
 
-After getting the TDREPORT, the second step of the attestation process
-is to send it to the Quoting Enclave (QE) to generate the Quote. TDREPORT
-by design can only be verified on the local platform as the MAC key is
-bound to the platform. To support remote verification of the TDREPORT,
-TDX leverages Intel SGX Quoting Enclave to verify the TDREPORT locally
-and convert it to a remotely verifiable Quote. Method of sending TDREPORT
-to QE is implementation specific. Attestation software can choose
-whatever communication channel available (i.e. vsock or TCP/IP) to
-send the TDREPORT to QE and receive the Quote.
+After getting the TDREPORT, the second step of the attestation process is to
+convert it to a Quote. A TDREPORT by design can only be verified on the local
+platform, as the MAC key is bound to the platform. A Quote makes the TDREPORT
+remotely verifiable. It can be generated either through a Quoting Enclave
+(QE) in userspace or through the Quoting service in kernel space. In
+userspace, the Intel SGX Quoting Enclave verifies the TDREPORT locally and
+converts it to a Quote. The method of sending the TDREPORT to the QE and
+receiving the Quote is implementation-specific. If the TDX module supports the
+Quoting service, the kernel can convert a TDREPORT to a Quote directly through
+a SEAMCALL. In this case, the Quote is generated entirely by the TDX module.
 
 References
 ==========
diff --git a/Documentation/virt/kvm/api.rst b/Documentation/virt/kvm/api.rst
index 52bbbb553ce1..4a3b69b2e602 100644
--- a/Documentation/virt/kvm/api.rst
+++ b/Documentation/virt/kvm/api.rst
@@ -7335,6 +7335,9 @@ inputs and outputs of the TDVMCALL.  Currently the following values of
    queued successfully, the TDX guest can poll the status field in the
    shared-memory area to check whether the Quote generation is completed or
    not. When completed, the generated Quote is returned via the same buffer.
+   If the host kernel generates Quotes through the Quoting service provided by
+   the TDX module, KVM processes the GetQuote request and it will not appear in
+   userspace.
 
  * ``TDVMCALL_GET_TD_VM_CALL_INFO``: the guest has requested the support
    status of TDVMCALLs.  The output values for the given leaf should be
diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 24bce7512de3..b9a24104415c 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -86,6 +86,15 @@ struct tdx_quote_req {
 	u8 data[];
 };
 
+#define TDX_QUOTE_REQ_HDR_SIZE		(offsetof(struct tdx_quote_req, data))
+
+/*
+ * TDG.VP.VMCALL<GetQuote> Status Codes
+ */
+#define TDX_QUOTE_STATUS_SUCCESS	0x0000000000000000ULL
+#define TDX_QUOTE_STATUS_ERROR		0x8000000000000000ULL
+#define TDX_QUOTE_STATUS_UNAVAILABLE	0x8000000000000001ULL
+
 #ifdef CONFIG_INTEL_TDX_GUEST
 
 void __init tdx_early_init(void);
diff --git a/arch/x86/kvm/vmx/tdx.h b/arch/x86/kvm/vmx/tdx.h
index ac8323a68b16..5e4b3aee0577 100644
--- a/arch/x86/kvm/vmx/tdx.h
+++ b/arch/x86/kvm/vmx/tdx.h
@@ -47,6 +47,12 @@ struct kvm_tdx {
 	 * Set/unset is protected with kvm->mmu_lock.
 	 */
 	bool wait_for_sept_zap;
+
+	/*
+	 * Whether to get the quote directly in kernel, without exiting to
+	 * userspace.
+	 */
+	bool get_quote_in_kernel;
 };
 
 /* TDX module vCPU states */
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 9f7c39e0d4b5..20558b0185b6 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1538,11 +1538,133 @@ static int tdx_get_quote_user(struct kvm_vcpu *vcpu, u64 gpa, u64 size)
 	return 0;
 }
 
+static bool write_quote_status_to_guest(struct kvm_vcpu *vcpu, u64 status,
+					gpa_t gpa)
+{
+	if (kvm_vcpu_write_guest(vcpu,
+				 gpa + offsetof(struct tdx_quote_req, status),
+				 &status, sizeof(status)))
+		return false;
+
+	return true;
+}
+
+static bool write_quote_to_guest(struct kvm_vcpu *vcpu, void *quote_data,
+				 u32 quote_len, gpa_t gpa)
+{
+	if (kvm_vcpu_write_guest(vcpu,
+				 gpa + TDX_QUOTE_REQ_HDR_SIZE,
+				 quote_data, quote_len))
+		return false;
+
+	if (kvm_vcpu_write_guest(vcpu,
+				 gpa + offsetof(struct tdx_quote_req, out_len),
+				 &quote_len, sizeof(quote_len)))
+		return false;
+
+	return true;
+}
+
+static u64 get_quote_kernel(struct kvm_vcpu *vcpu, struct tdx_quote_req *req,
+			    gpa_t req_gpa, size_t total_len)
+{
+	struct tdx_td *td = &to_kvm_tdx(vcpu->kvm)->td;
+
+	/* Only support version 1 as defined in the GHCI spec */
+	if (req->version != 1)
+		return TDX_QUOTE_STATUS_ERROR;
+
+	/* Header + input data must fit in the page read from guest memory */
+	if ((size_t)req->in_len + TDX_QUOTE_REQ_HDR_SIZE > PAGE_SIZE)
+		return TDX_QUOTE_STATUS_ERROR;
+
+	/* Caller owns the requested quote */
+	void *quote_data __free(kvfree) =
+		tdx_quote_generate(td, req->data, req->in_len, &req->out_len);
+
+	if (!quote_data)
+		return TDX_QUOTE_STATUS_UNAVAILABLE;
+
+	if ((size_t)req->out_len + TDX_QUOTE_REQ_HDR_SIZE > total_len)
+		return TDX_QUOTE_STATUS_ERROR;
+
+	if (!write_quote_to_guest(vcpu, quote_data, req->out_len, req_gpa))
+		return TDX_QUOTE_STATUS_ERROR;
+
+	return TDX_QUOTE_STATUS_SUCCESS;
+}
+
+static u64 tdx_get_quote_check_args(struct kvm_vcpu *vcpu, u64 gpa, u64 size)
+{
+	gfn_t gfn_start, gfn_end;
+	u64 end;
+
+	if (!size)
+		return TDVMCALL_STATUS_INVALID_OPERAND;
+
+	if (!PAGE_ALIGNED(gpa) || !PAGE_ALIGNED(size))
+		return TDVMCALL_STATUS_ALIGN_ERROR;
+
+	if (check_add_overflow(gpa, size, &end))
+		return TDVMCALL_STATUS_INVALID_OPERAND;
+
+	gfn_start = gpa_to_gfn(gpa);
+	gfn_end = gpa_to_gfn(end);
+
+	/*
+	 * Reject if the guest didn't explicitly convert its quote pages to
+	 * shared.
+	 */
+	if (!kvm_range_has_memory_attributes(vcpu->kvm, gfn_start, gfn_end,
+					     KVM_MEMORY_ATTRIBUTE_PRIVATE, 0))
+		return TDVMCALL_STATUS_INVALID_OPERAND;
+
+	return TDVMCALL_STATUS_SUCCESS;
+}
+
+static int tdx_get_quote_kernel(struct kvm_vcpu *vcpu, u64 gpa, u64 size)
+{
+	void *first_page = NULL;
+	u64 err, qerr;
+
+	err = tdx_get_quote_check_args(vcpu, gpa, size);
+	if (err != TDVMCALL_STATUS_SUCCESS)
+		goto out;
+
+	err = TDVMCALL_STATUS_INVALID_OPERAND;
+
+	first_page = kmalloc(PAGE_SIZE, GFP_KERNEL);
+	if (!first_page)
+		goto out;
+
+	/*
+	 * Read the first GetQuote page for its header + input data. The check
+	 * above ensures that this GetQuote message is at least one page in
+	 * size. in_data spanning more than a page is not supported.
+	 */
+	if (kvm_vcpu_read_guest(vcpu, gpa, first_page, PAGE_SIZE))
+		goto out;
+
+	qerr = get_quote_kernel(vcpu, first_page, (gpa_t)gpa, size);
+
+	if (write_quote_status_to_guest(vcpu, qerr, (gpa_t)gpa) &&
+	    qerr == TDX_QUOTE_STATUS_SUCCESS)
+		err = TDVMCALL_STATUS_SUCCESS;
+
+out:
+	kfree(first_page);
+	tdvmcall_set_return_code(vcpu, err);
+
+	return 1;
+}
+
 static int tdx_get_quote(struct kvm_vcpu *vcpu)
 {
+	struct kvm_tdx *kvm_tdx = to_kvm_tdx(vcpu->kvm);
 	struct vcpu_tdx *tdx = to_tdx(vcpu);
 	u64 gpa = tdx->vp_enter_args.r12;
 	u64 size = tdx->vp_enter_args.r13;
+	int ret;
 
 	/* The gpa of buffer must have shared bit set. */
 	if (vt_is_tdx_private_gpa(vcpu->kvm, gpa)) {
@@ -1552,7 +1674,12 @@ static int tdx_get_quote(struct kvm_vcpu *vcpu)
 
 	gpa &= ~gfn_to_gpa(kvm_gfn_direct_bits(vcpu->kvm));
 
-	return tdx_get_quote_user(vcpu, gpa, size);
+	if (kvm_tdx->get_quote_in_kernel)
+		ret = tdx_get_quote_kernel(vcpu, gpa, size);
+	else
+		ret = tdx_get_quote_user(vcpu, gpa, size);
+
+	return ret;
 }
 
 static int tdx_setup_event_notify_interrupt(struct kvm_vcpu *vcpu)
@@ -2751,6 +2878,12 @@ static int tdx_td_init(struct kvm *kvm, struct kvm_tdx_cmd *cmd)
 	else
 		kvm->arch.gfn_direct_bits = TDX_SHARED_BIT_PWL_4;
 
+	/*
+	 * Check only once at TD creation. Switching between userspace and
+	 * in-kernel quoting is not supported.
+	 */
+	kvm_tdx->get_quote_in_kernel = tdx_quote_enabled();
+
 	kvm_tdx->state = TD_STATE_INITIALIZED;
 out:
 	/* kfree() accepts NULL. */
diff --git a/virt/kvm/kvm_main.c b/virt/kvm/kvm_main.c
index 89489996fbc1..599f88a13071 100644
--- a/virt/kvm/kvm_main.c
+++ b/virt/kvm/kvm_main.c
@@ -2461,6 +2461,7 @@ bool kvm_range_has_memory_attributes(struct kvm *kvm, gfn_t start, gfn_t end,
 
 	return true;
 }
+EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_range_has_memory_attributes);
 
 static __always_inline void kvm_handle_gfn_range(struct kvm *kvm,
 						 struct kvm_mmu_notifier_range *range)

---

## [18] Xu Yilun — 2026-06-18
*Subject: [PATCH v2 17/17] KVM: TDX: Support event-notify interrupts only with userspace Quoting*

From: Peter Fang <peter.fang@intel.com>

Tie userspace SetupEventNotifyInterrupt support to userspace Quote
generation. Delivering event-notify interrupts via userspace breaks if
KVM never exits to userspace in the first place.

This is an optional capability to notify the guest when Quoting has
completed. No known guest currently uses it, so defer adding in-kernel
support for now. The Linux TDX guest relies on polling only.

Signed-off-by: Peter Fang <peter.fang@intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 arch/x86/kvm/vmx/tdx.c | 20 +++++++++++++++++---
 1 file changed, 17 insertions(+), 3 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 20558b0185b6..25146da3933f 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -185,7 +185,7 @@ static void td_init_cpuid_entry2(struct kvm_cpuid_entry2 *entry, unsigned char i
 	tdx_clear_unsupported_cpuid(entry);
 }
 
-#define TDVMCALLINFO_SETUP_EVENT_NOTIFY_INTERRUPT	BIT(1)
+#define TDVMCALLINFO_SETUP_EVENT_NOTIFY_INTERRUPT	BIT_ULL(1)
 
 static int init_kvm_tdx_caps(const struct tdx_sys_info_td_conf *td_conf,
 			     struct kvm_tdx_capabilities *caps)
@@ -202,8 +202,15 @@ static int init_kvm_tdx_caps(const struct tdx_sys_info_td_conf *td_conf,
 
 	caps->cpuid.nent = td_conf->num_cpuid_config;
 
-	caps->user_tdvmcallinfo_1_r11 =
-		TDVMCALLINFO_SETUP_EVENT_NOTIFY_INTERRUPT;
+	/*
+	 * Don't advertise userspace event-notify interrupt support if TDX
+	 * quoting service is enabled, as quote generation will be handled
+	 * entirely in the kernel. Support in the kernel can be added later.
+	 */
+	if (!tdx_quote_enabled()) {
+		caps->user_tdvmcallinfo_1_r11 |=
+			TDVMCALLINFO_SETUP_EVENT_NOTIFY_INTERRUPT;
+	}
 
 	for (i = 0; i < td_conf->num_cpuid_config; i++)
 		td_init_cpuid_entry2(&caps->cpuid.entries[i], i);
@@ -1684,9 +1691,16 @@ static int tdx_get_quote(struct kvm_vcpu *vcpu)
 
 static int tdx_setup_event_notify_interrupt(struct kvm_vcpu *vcpu)
 {
+	struct kvm_tdx *kvm_tdx = to_kvm_tdx(vcpu->kvm);
 	struct vcpu_tdx *tdx = to_tdx(vcpu);
 	u64 vector = tdx->vp_enter_args.r12;
 
+	/* See comment in init_kvm_tdx_caps() */
+	if (kvm_tdx->get_quote_in_kernel) {
+		tdvmcall_set_return_code(vcpu, TDVMCALL_STATUS_SUBFUNC_UNSUPPORTED);
+		return 1;
+	}
+
 	if (vector < 32 || vector > 255) {
 		tdvmcall_set_return_code(vcpu, TDVMCALL_STATUS_INVALID_OPERAND);
 		return 1;

---

## [19] Dave Hansen — 2026-06-18
*Subject: Re: [PATCH v2 01/17] x86/virt/tdx: Embed version info in SEAMCALL
 leaf function definitions*

On 6/18/26 01:13, Xu Yilun wrote:
> Embed version information in SEAMCALL leaf function definitions rather
> than let the caller open code them. For now, only TDH.VP.INIT is

This is jumping the gun a bit in the changelog.

What is a SEAMCALL leaf function?

How does the version fit in?

> Don't bother the caller to choose the SEAMCALL version if unnecessary.

I think I see what you are trying to say here but it's more than that.

The question is whether there should be a base seamcall() API that takes
an explicit version or whether the version should be passed in by callers.

One wrinkle is that the naming of all of these things is around
"function", "func" and "fn":

u64 __seamcall(u64 fn, struct tdx_module_args *args);

A "function" is TDH.SYS.INIT or TDH.SYS.INFO, not 'TDH.SYS.INFO v123'.

But the low-level calls could be:

	u64 __seamcall(u64 fn, u64 version, ...);
	
or

	u64 __seamcall(u64 fn, ...);

Where 'fn' encodes the function *and* version.

> The old TDX modules that only support TDH.VP.INIT v0 are all deprecated,
> so only provide the latest (v1) definition.

No, this isn't how this is going to work.

What do we *NEED* from v1? Why churn the code if we don't *NEED*
something from v1 and can live with v0? It has *ZERO* to do with the TDX
module being deprecated or whatever.

Linux stays on the old interface until we need a new interface. We are
*not* going to bump version numbers just because.


>  /*
>   * TDX module SEAMCALL leaf functions

That is unreadable and patterns can't be seen. This is better:

#define TDH_MNG_INIT			SEAMCALL_LEAF_VER(21, 0)
#define TDH_VP_INIT			SEAMCALL_LEAF_VER(22, 1)
#define TDH_PHYMEM_PAGE_RDMD		SEAMCALL_LEAF_VER(24, 0)

> --- a/arch/x86/virt/vmx/tdx/tdx.c
> +++ b/arch/x86/virt/vmx/tdx/tdx.c

But that whole scheme falls apart the first time the kernel needs
functionality from v2. You'll need:

#define TDH_VP_INIT_V0			SEAMCALL_LEAF_VER(22, 0)
#define TDH_VP_INIT_V1			SEAMCALL_LEAF_VER(22, 1)

and then the calls will do:

	if (foo)
		return seamcall(TDH_VP_INIT_V0, &args);
	else
		return seamcall(TDH_VP_INIT_V1, &args);

So this 100% goes down the road of needing #defines for *EACH* version.
That's the real implication here and the real choice.

That said, I don't particularly like:

	if (foo)
		return seamcall(TDH_VP_INIT, 0, &args);
	else
		return seamcall(TDH_VP_INIT, 1, &args);

all that much either because of the seemingly magic numbers.

The whole seamcall RAX thing is one step too clever. I think Linux did
the right thing:

5	common	open				sys_open
288	common	openat				sys_openat
437	common	openat2				sys_openat2

New ABI gets a new base number. No need for the other end of the ABI to
know that 288 is arguably a later version of 5.

Ugh. But why is this patch even in here in the first place? Why is this
even *ASSOCIATED* with DICE-based attestation? Isn't this completely
orthogonal?

---

## [20] Dave Hansen — 2026-06-18
*Subject: Re: [PATCH v2 02/17] x86/virt/tdx: Configure add-on features on TDX
 module init and update*

On 6/18/26 01:13, Xu Yilun wrote:
>  int tdx_module_run_update(void)
>  {

Heh, and it falls apart into craziness immediately. See how it
immediately loses the logical information that there's a version 1 and a
version 0? The "1" isn't even visible. It's hidden in "TDH_SYS_UPDATE".

Isn't this a million times more sane?

	struct tdx_module_args args = {};
	u64 version;
  	int ret;

	if (tdx_addon_feature0) {
		args.r9 = tdx_addon_feature0;
		version = 1;
	} else {
		version = 0;
	}

	ret = seamcall_prerr(TDH_SYS_UPDATE, version, &args);


There's also zero stopping us from putting version in args:

	struct tdx_module_args args = {};
  	int ret;

	if (tdx_addon_feature0) {
		args.r9 = tdx_addon_feature0;
		args.version = 1;
	}

	ret = seamcall_prerr(TDH_SYS_UPDATE, &args);

Eh?

That gives args.version==0 in all the normal cases which just happens to
be the exact behavior we want. It also avoids having to plumb version
through all the seamcall*() wrappers.

But this is *exactly* the kind of thing that shouldn't be a part of an
attestation patch series. This could very much have been a separate
discussion and happened a month or a year ago. But now it is blocking
this DICE thing from getting done <grumble>.

---

## [21] Xu Yilun — 2026-06-22
*Subject: Re: [PATCH v2 01/17] x86/virt/tdx: Embed version info in SEAMCALL
 leaf function definitions*

> This is jumping the gun a bit in the changelog.
> 

I think the word "leaf function" is confusing, maybe I should say
"... SEAMCALL interface function definitions..."?

And I missed some more context explanation here:

  SEAMCALL accepts parameters via CPU registers (RAX, RCX, RDX, ...),
  where RAX selects the specific TDX module function to execute. According
  to the TDX module SPEC, RAX is mainly composed of:

  1. leaf number: selects the function.
  2. version number: selects the function version. The newer version
     defines more operations. It also defines additional parameters for
     the rest of registers.

  Newer version SEAMCALL uses the same leaf number as older versions,
  with only the version number increased. Newer version SEAMCALLs are
  guaranteed to be backward compatible.

[...]

> > The old TDX modules that only support TDH.VP.INIT v0 are all deprecated,
> > so only provide the latest (v1) definition.

Sorry for the confusing words, for this TDH.VP.INIT, kernel is now using
v1, we need v1 for virtual x2APIC. Maybe I should add "No functional change
intended."

> It has *ZERO* to do with the TDX module being deprecated or whatever.

Since newer version SEAMCALLs are always backward compatible. TDH.VP.INIT v0
is only needed when we need to support legacy modules that don't understand
TDH.VP.INIT v1. We don't support such legacy modules, so I meant to
eliminate TDH.VP.INIT v0 definition and reduce histroy burdens.

We have some previous discussion that leads to "kernel don't keep SEAMCALL
version at all":

https://lore.kernel.org/all/ca331aa3-6304-4e07-9ed9-94dc69726382@intel.com/

But I have trouble for not keeping versions for TDH.SYS.CONFIG/UPDATE (in
next patch). No public module supports TDH.SYS.CONFIG/UPDATE v1 so I can't
eliminate TDH.SYS.CONFIG/UPDATE v0. I'm GOOD we are now considering keep
aware of SEAMCALL versions at some level. Keeping in mind which module
is published is another burden...

[...]

> But that whole scheme falls apart the first time the kernel needs
> functionality from v2. You'll need:

TDH_VP_INIT_V0 has no use case in current code, so maybe not #define for
EACH version.

And we have 100+ SEAMCALLs in SPEC, 30+ is being used in Linux, 20+ is
comming, only 3 need versions now. I think making versioned definitions
for EACH of them is overkill.

I see you have another suggestion in next patch which avoids the
#defines. Let me continue in that patch.


> The whole seamcall RAX thing is one step too clever. I think Linux did
> the right thing:

Yes, that's true.

> 
> Ugh. But why is this patch even in here in the first place? Why is this

TDH.SYS.UPDATE/CONFIG is the second user of the version stuff. So as
required, fix the open code issue of the first existing user.

https://lore.kernel.org/all/62bec236-4716-4326-8342-1863ad8a3f24@intel.com/

Thanks,
Yilun

---

## [22] Xu Yilun — 2026-06-22
*Subject: Re: [PATCH v2 02/17] x86/virt/tdx: Configure add-on features on TDX
 module init and update*

> There's also zero stopping us from putting version in args:
> 

I'm thinking the version is only needed for 3 SEAMCALLs. We don't have
to make version common for all 100+ SEAMCALLs. Besides the layout of
"struct tdx_module_args" correlates the fundamental assembly code of
__seamcall() in tdcall.S.

Could we make dedicated SEAMCALL wrappers for TDH_SYS_UPDATE similar to
other SEAMCALLs and wrapper the specific version handling there? I put
the diff in the end.

> 
> That gives args.version==0 in all the normal cases which just happens to

Sorry, I was thinking "don't keep version" was the conclusion...

--------8<--------

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 01fb01313077..b3b3540e431a 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1757,18 +1757,12 @@ int tdx_module_shutdown(void)

 int tdx_module_run_update(void)
 {
-       u64 seamcall_fn = TDH_SYS_UPDATE_V0;
-       struct tdx_module_args args = {};
+       u64 err;
        int ret;

-       if (tdx_addon_feature0) {
-               args.r9 = tdx_addon_feature0;
-               seamcall_fn = TDH_SYS_UPDATE;
-       }
-
-       ret = seamcall_prerr(seamcall_fn, &args);
-       if (ret)
-               return ret;
+       err = tdx_sys_update(tdx_addon_feature0);
+       if (err)
+               return -EIO;

        ret = get_tdx_sys_info_version(&tdx_sysinfo.version);
        /*
@@ -2351,7 +2345,7 @@ u64 tdh_vp_init(struct tdx_vp *vp, u64 initial_rcx, u32 x2apicid)
                .r8 = x2apicid,
        };

-       return seamcall(TDH_VP_INIT, &args);
+       return seamcall(SEAMCALL_LEAF_VER(TDH_VP_INIT, 1), &args);
 }
 EXPORT_SYMBOL_FOR_KVM(tdh_vp_init);

@@ -2463,3 +2457,16 @@ void tdx_sys_disable(void)
        if (ret && (ret & TDX_SW_ERROR) != TDX_SW_ERROR)
                pr_err("TDH.SYS.DISABLE failed: 0x%016llx\n", ret);
 }
+
+u64 tdx_sys_update(u64 features_enable0)
+{
+       struct tdx_module_args args = {
+               .r9 = features_enable0,
+       };
+       u64 fn = TDH_SYS_UPDATE;
+
+       if (features_enable0)
+               fn = SEAMCALL_LEAF_VER(TDH_SYS_UPDATE, 1);
+
+       return seamcall(fn, &args);
+}
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index 32b13b0c85f9..f07e12552bf9 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -44,7 +44,7 @@
 #define TDH_VP_CREATE                  10
 #define TDH_MNG_KEY_FREEID             20
 #define TDH_MNG_INIT                   21
-#define TDH_VP_INIT                    SEAMCALL_LEAF_VER(22, 1)
+#define TDH_VP_INIT                    22
 #define TDH_PHYMEM_PAGE_RDMD           24
 #define TDH_VP_RD                      26
 #define TDH_PHYMEM_PAGE_RECLAIM                28
@@ -61,8 +61,7 @@
 #define TDH_SYS_SHUTDOWN               52
-#define TDH_SYS_UPDATE_V0              53
-#define TDH_SYS_UPDATE                 SEAMCALL_LEAF_VER(TDH_SYS_UPDATE_V0, 1)
+#define TDH_SYS_UPDATE                 53
 #define TDH_EXT_INIT                   60
 #define TDH_EXT_MEM_ADD                        61
 #define TDH_SYS_DISABLE                        69

---

## [23] Chao Gao — 2026-06-23
*Subject: Re: [PATCH v2 02/17] x86/virt/tdx: Configure add-on features on TDX
 module init and update*

On Thu, Jun 18, 2026 at 04:13:40PM +0800, Xu Yilun wrote:
>In addition to basic TDX functionalities, TDX module provides add-on
>features that can be progressively enabled as the kernel supports them.

Actually, we do not need another global variable here. tdx_features0 is cached
and is not updated across a runtime update, so the derived add-on feature
bitmap will be the same before and after the update.


> static __init int config_tdx_module(struct tdmr_info_list *tdmr_list,
> 				    u64 global_keyid)

How about moving this r9 assignment out of the if block and placing it next to
'args.r8 = global_keyid;'? There is no need to guard it, because args.r9 will
be 0 when no add-on features are enabled, which is perfectly fine.

>+		seamcall_fn = TDH_SYS_CONFIG;
>+	}

---

## [24] Xu Yilun — 2026-06-24
*Subject: Re: [PATCH v2 02/17] x86/virt/tdx: Configure add-on features on TDX
 module init and update*

> There's also zero stopping us from putting version in args:
> 

Ah, on 2nd reading, I'm pretty sure now I understand your logical argument in
patch 1 and 2. It's good to me. I append my diff at the end.

> 
> But this is *exactly* the kind of thing that shouldn't be a part of an

Sorry, I should have been more active in searching for the solution
rather than sticking to "kernel never keeps versions", when I've found
the problem that public modules are not available.

----8<----

diff --git a/arch/x86/include/asm/shared/tdx.h b/arch/x86/include/asm/shared/tdx.h
index f20e91d7ac35..972880910a5e 100644
--- a/arch/x86/include/asm/shared/tdx.h
+++ b/arch/x86/include/asm/shared/tdx.h
@@ -143,6 +143,8 @@ struct tdx_module_args {
        u64 rbx;
        u64 rdi;
        u64 rsi;
+       /* for RAX encoding */
+       u8  version;
 };

 /* Used to communicate with the TDX module */
diff --git a/arch/x86/kernel/asm-offsets.c b/arch/x86/kernel/asm-offsets.c
index 081816888f7a..b3c00ff4d819 100644
--- a/arch/x86/kernel/asm-offsets.c
+++ b/arch/x86/kernel/asm-offsets.c
@@ -95,6 +95,7 @@ static void __used common(void)
        OFFSET(TDX_MODULE_rbx, tdx_module_args, rbx);
        OFFSET(TDX_MODULE_rdi, tdx_module_args, rdi);
        OFFSET(TDX_MODULE_rsi, tdx_module_args, rsi);
+       OFFSET(TDX_MODULE_version, tdx_module_args, version);

        BLANK();
        OFFSET(BP_scratch, boot_params, scratch);
diff --git a/arch/x86/virt/vmx/tdx/tdxcall.S b/arch/x86/virt/vmx/tdx/tdxcall.S
index 016a2a1ec1d6..d1d3d40c5614 100644
--- a/arch/x86/virt/vmx/tdx/tdxcall.S
+++ b/arch/x86/virt/vmx/tdx/tdxcall.S
@@ -48,6 +48,14 @@
        /* Move Leaf ID to RAX */
        mov %rdi, %rax

+       /*
+        * Extract the version from 'struct tdx_module_args', append it to
+        * RAX[23:16]
+        */
+       movzbl  TDX_MODULE_version(%rsi), %ecx
+       shll    $16, %ecx
+       orq     %rcx, %rax
+
        /* Move other input regs from 'struct tdx_module_args' */
        movq    TDX_MODULE_rcx(%rsi), %rcx
        movq    TDX_MODULE_rdx(%rsi), %rdx
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index a6f8fd0a3df0..bc3aa1f78fc8 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1036,7 +1036,6 @@ static __init void set_tdx_addon_features(void)
 static __init int config_tdx_module(struct tdmr_info_list *tdmr_list,
                                    u64 global_keyid)
 {
-       u64 seamcall_fn = TDH_SYS_CONFIG_V0;
        struct tdx_module_args args = {};
        u64 *tdmr_pa_array;
        size_t array_sz;
@@ -1059,18 +1058,18 @@ static __init int config_tdx_module(struct tdmr_info_list *tdmr_list,
        for (i = 0; i < tdmr_list->nr_consumed_tdmrs; i++)
                tdmr_pa_array[i] = __pa(tdmr_entry(tdmr_list, i));

+       set_tdx_addon_features();
+
        args.rcx = __pa(tdmr_pa_array);
        args.rdx = tdmr_list->nr_consumed_tdmrs;
        args.r8 = global_keyid;

-       set_tdx_addon_features();
-
        if (tdx_addon_feature0) {
                args.r9 = tdx_addon_feature0;
-               seamcall_fn = TDH_SYS_CONFIG;
+               args.version = 1;
        }

-       ret = seamcall_prerr(seamcall_fn, &args);
+       ret = seamcall_prerr(TDH_SYS_CONFIG, &args);

        /* Free the array as it is not required anymore. */
        kfree(tdmr_pa_array);
@@ -1761,16 +1760,15 @@ int tdx_module_shutdown(void)

 int tdx_module_run_update(void)
 {
-       u64 seamcall_fn = TDH_SYS_UPDATE_V0;
        struct tdx_module_args args = {};
        int ret;

        if (tdx_addon_feature0) {
                args.r9 = tdx_addon_feature0;
-               seamcall_fn = TDH_SYS_UPDATE;
+               args.version = 1;
        }

-       ret = seamcall_prerr(seamcall_fn, &args);
+       ret = seamcall_prerr(TDH_SYS_UPDATE, &args);
        if (ret)
                return ret;

@@ -2353,6 +2351,7 @@ u64 tdh_vp_init(struct tdx_vp *vp, u64 initial_rcx, u32 x2apicid)
                .rcx = vp->tdvpr_pa,
                .rdx = initial_rcx,
                .r8 = x2apicid,
+               .version = 1,
        };

        return seamcall(TDH_VP_INIT, &args);
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index 32b13b0c85f9..018988c25caa 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -44,7 +44,7 @@
 #define TDH_VP_CREATE                  10
 #define TDH_MNG_KEY_FREEID             20
 #define TDH_MNG_INIT                   21
-#define TDH_VP_INIT                    SEAMCALL_LEAF_VER(22, 1)
+#define TDH_VP_INIT                    22
 #define TDH_PHYMEM_PAGE_RDMD           24
 #define TDH_VP_RD                      26
 #define TDH_PHYMEM_PAGE_RECLAIM                28
@@ -58,11 +58,9 @@
 #define TDH_PHYMEM_CACHE_WB            40
 #define TDH_PHYMEM_PAGE_WBINVD         41
 #define TDH_VP_WR                      43
-#define TDH_SYS_CONFIG_V0              45
-#define TDH_SYS_CONFIG                 SEAMCALL_LEAF_VER(TDH_SYS_CONFIG_V0, 1)
+#define TDH_SYS_CONFIG                 45
 #define TDH_SYS_SHUTDOWN               52
-#define TDH_SYS_UPDATE_V0              53
-#define TDH_SYS_UPDATE                 SEAMCALL_LEAF_VER(TDH_SYS_UPDATE_V0, 1)
+#define TDH_SYS_UPDATE                 53
 #define TDH_EXT_INIT                   60
 #define TDH_EXT_MEM_ADD                        61
 #define TDH_SYS_DISABLE                        69

---

## [25] Peter Fang — 2026-06-24
*Subject: Re: [PATCH v2 02/17] x86/virt/tdx: Configure add-on features on TDX
 module init and update*

On Wed, Jun 24, 2026 at 08:00:39PM +0800, Xu Yilun wrote:
> > There's also zero stopping us from putting version in args:
> > 

[ ... ]

> diff --git a/arch/x86/virt/vmx/tdx/tdxcall.S b/arch/x86/virt/vmx/tdx/tdxcall.S
> index 016a2a1ec1d6..d1d3d40c5614 100644

This approach looks much cleaner to me. Would it be better to have a
small C helper to encode the final RAX value instead of operating on RAX
directly in asm? Looking at the May 2026 edition of the ABI spec,
SEAMCALL RAX encoding is starting to get quite complex. Just thinking
about this from a readability standpoint.

---

## [26] Tony Lindgren — 2026-06-25
*Subject: Re: [PATCH v2 03/17] x86/virt/tdx: Detect if the extensions
 initialization is required*

On Thu, Jun 18, 2026 at 04:13:41PM +0800, Xu Yilun wrote:
> TDX module extensions support extension SEAMCALLs that are preemptible
> and resumable, unlike normal SEAMCALLs that run to completion while

How about "TDX module extension SEAMCALLs are preemptible and resumable..."
above to make it easier to read?

Other than that:

Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>

---

## [27] Tony Lindgren — 2026-06-25
*Subject: Re: [PATCH v2 11/17] x86/virt/tdx: Add interface to generate a Quote*

On Thu, Jun 18, 2026 at 04:13:49PM +0800, Xu Yilun wrote:
> From: Peter Fang <peter.fang@intel.com>
> --- a/arch/x86/virt/vmx/tdx/tdx.c
...
> +void *tdx_quote_generate(struct tdx_td *td, void *in_data, u32 in_data_len,
> +			 u32 *quote_len)

How about make the pre-generated static tdx_quote a template page that only
gets read and copied to an allocated bufer here?

If the tdx_quote template is only read for copying here, seems you're not
going to need the mutex at all? That is assuming tdx_quote template does
not change after init.

---

## [28] Tony Lindgren — 2026-06-25
*Subject: Re: [PATCH v2 08/17] x86/virt/tdx: Prepare Quote buffer during
 extension bringup*

On Thu, Jun 18, 2026 at 04:13:46PM +0800, Xu Yilun wrote:
> From: Peter Fang <peter.fang@intel.com>
> For simplicity, let all guests share a global buffer. Build the buffer's

To me it seems the pre-generated parts can be made into a template that
can be copied to an allocated buffer looking at patch 11/17.

---

## [29] Tony Lindgren — 2026-06-25
*Subject: Re: [PATCH v2 09/17] x86/virt/tdx: Add interface to check Quoting
 availability*

On Thu, Jun 18, 2026 at 04:13:47PM +0800, Xu Yilun wrote:
> From: Peter Fang <peter.fang@intel.com>
> 

Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>

---

## [30] Tony Lindgren — 2026-06-25
*Subject: Re: [PATCH v2 10/17] x86/virt/tdx: Move tdx_tdr_pa() up in the file*

On Thu, Jun 18, 2026 at 04:13:48PM +0800, Xu Yilun wrote:
> From: Peter Fang <peter.fang@intel.com>
> 

Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>

---

## [31] Tony Lindgren — 2026-06-25
*Subject: Re: [PATCH v2 12/17] x86/virt/tdx: Reinitialize the Quoting
 extension after TDX module update*

On Thu, Jun 18, 2026 at 04:13:50PM +0800, Xu Yilun wrote:
> From: Peter Fang <peter.fang@intel.com>
> 

Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>

---

## [32] Tony Lindgren — 2026-06-25
*Subject: Re: [PATCH v2 13/17] x86/virt/tdx: Enable Quoting extension*

On Thu, Jun 18, 2026 at 04:13:51PM +0800, Xu Yilun wrote:
> From: Peter Fang <peter.fang@intel.com>
> 

Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>

---

## [33] Tony Lindgren — 2026-06-25
*Subject: Re: [PATCH v2 14/17] x86/tdx: Move and rename Quote request structure*

On Thu, Jun 18, 2026 at 04:13:52PM +0800, Xu Yilun wrote:
> From: Peter Fang <peter.fang@intel.com>
> 

Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>

---

## [34] Tony Lindgren — 2026-06-25
*Subject: Re: [PATCH v2 15/17] KVM: TDX: Factor out userspace return path from
 tdx_get_quote()*

On Thu, Jun 18, 2026 at 04:13:53PM +0800, Xu Yilun wrote:
> From: Peter Fang <peter.fang@intel.com>
> 

Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>

---

## [35] Tony Lindgren — 2026-06-25
*Subject: Re: [PATCH v2 17/17] KVM: TDX: Support event-notify interrupts only
 with userspace Quoting*

On Thu, Jun 18, 2026 at 04:13:55PM +0800, Xu Yilun wrote:
> From: Peter Fang <peter.fang@intel.com>
> --- a/arch/x86/kvm/vmx/tdx.c

Can you use kvm_tdx->get_quote_in_kernel also above? Or should it maybe
be initialized here if not used earlier?
  
> @@ -1684,9 +1691,16 @@ static int tdx_get_quote(struct kvm_vcpu *vcpu)
>  

Since you're using kvm_tdx->get_quote_in_kernel here.

---

## [36] Xu Yilun — 2026-06-25
*Subject: Re: [PATCH v2 02/17] x86/virt/tdx: Configure add-on features on TDX
 module init and update*

On Wed, Jun 24, 2026 at 03:10:37PM -0700, Peter Fang wrote:
> On Wed, Jun 24, 2026 at 08:00:39PM +0800, Xu Yilun wrote:
> > > There's also zero stopping us from putting version in args:

I'm also good to it. I made some diff for your proposal, Some additional
effort here is to update some comments and parameter names, to reflect
the differences between "function/func/fn" (the unversioned number) and
the final composite "fn_code" for RAX.

-----8<-------

diff --git a/arch/x86/include/asm/shared/tdx.h b/arch/x86/include/asm/shared/tdx.h
index f20e91d7ac35..c26eca18fded 100644
--- a/arch/x86/include/asm/shared/tdx.h
+++ b/arch/x86/include/asm/shared/tdx.h
@@ -143,6 +143,8 @@ struct tdx_module_args {
 	u64 rbx;
 	u64 rdi;
 	u64 rsi;
+	/* for leaf encoding */
+	u8  version;
 };
 
 /* Used to communicate with the TDX module */
diff --git a/arch/x86/virt/vmx/tdx/seamcall.S b/arch/x86/virt/vmx/tdx/seamcall.S
index 6854c52c374b..5cf3993e98f4 100644
--- a/arch/x86/virt/vmx/tdx/seamcall.S
+++ b/arch/x86/virt/vmx/tdx/seamcall.S
@@ -10,8 +10,8 @@
  *
  * __seamcall() function ABI:
  *
- * @fn   (RDI)  - SEAMCALL Leaf number, moved to RAX
- * @args (RSI)  - struct tdx_module_args for input
+ * @fn_code (RDI)  - SEAMCALL composite leaf code, moved to RAX
+ * @args    (RSI)  - struct tdx_module_args for input
  *
  * Only RCX/RDX/R8-R11 are used as input registers.
  *
@@ -29,8 +29,8 @@ SYM_FUNC_END(__seamcall)
  *
  * __seamcall_ret() function ABI:
  *
- * @fn   (RDI)  - SEAMCALL Leaf number, moved to RAX
- * @args (RSI)  - struct tdx_module_args for input and output
+ * @fn_code (RDI)  - SEAMCALL composite leaf code, moved to RAX
+ * @args    (RSI)  - struct tdx_module_args for input and output
  *
  * Only RCX/RDX/R8-R11 are used as input/output registers.
  *
@@ -51,8 +51,8 @@ SYM_FUNC_END(__seamcall_ret)
  *
  * __seamcall_saved_ret() function ABI:
  *
- * @fn   (RDI)  - SEAMCALL Leaf number, moved to RAX
- * @args (RSI)  - struct tdx_module_args for input and output
+ * @fn_code (RDI)  - SEAMCALL composite leaf code, moved to RAX
+ * @args    (RSI)  - struct tdx_module_args for input and output
  *
  * All registers in @args are used as input/output registers.
  *
diff --git a/arch/x86/virt/vmx/tdx/seamcall_internal.h b/arch/x86/virt/vmx/tdx/seamcall_internal.h
index be5f446467df..bb17d965b453 100644
--- a/arch/x86/virt/vmx/tdx/seamcall_internal.h
+++ b/arch/x86/virt/vmx/tdx/seamcall_internal.h
@@ -11,17 +11,28 @@
 #ifndef _X86_VIRT_SEAMCALL_INTERNAL_H
 #define _X86_VIRT_SEAMCALL_INTERNAL_H
 
+#include <linux/bitfield.h>
 #include <linux/printk.h>
 #include <linux/types.h>
 #include <asm/archrandom.h>
 #include <asm/processor.h>
 #include <asm/tdx.h>
 
-u64 __seamcall(u64 fn, struct tdx_module_args *args);
-u64 __seamcall_ret(u64 fn, struct tdx_module_args *args);
-u64 __seamcall_saved_ret(u64 fn, struct tdx_module_args *args);
+u64 __seamcall(u64 fn_code, struct tdx_module_args *args);
+u64 __seamcall_ret(u64 fn_code, struct tdx_module_args *args);
+u64 __seamcall_saved_ret(u64 fn_code, struct tdx_module_args *args);
 
-typedef u64 (*sc_func_t)(u64 fn, struct tdx_module_args *args);
+typedef u64 (*sc_func_t)(u64 fn_code, struct tdx_module_args *args);
+
+#define SEAMCALL_VERSION_MASK		GENMASK_U64(23, 16)
+
+static __always_inline u64 __seamcall_fn_encoding(sc_func_t func, u64 fn,
+						  struct tdx_module_args *args)
+{
+	FIELD_MODIFY(SEAMCALL_VERSION_MASK, &fn, args->version);
+
+	return func(fn, args);
+}
 
 static __always_inline u64 __seamcall_dirty_cache(sc_func_t func, u64 fn,
 						  struct tdx_module_args *args)
@@ -39,7 +50,7 @@ static __always_inline u64 __seamcall_dirty_cache(sc_func_t func, u64 fn,
 	 */
 	this_cpu_write(cache_state_incoherent, true);
 
-	return func(fn, args);
+	return __seamcall_fn_encoding(func, fn, args);
 }
 
 static __always_inline u64 sc_retry(sc_func_t func, u64 fn,
diff --git a/arch/x86/virt/vmx/tdx/tdxcall.S b/arch/x86/virt/vmx/tdx/tdxcall.S
index 016a2a1ec1d6..b0f7867bcd1c 100644
--- a/arch/x86/virt/vmx/tdx/tdxcall.S
+++ b/arch/x86/virt/vmx/tdx/tdxcall.S
@@ -24,7 +24,7 @@
  *-------------------------------------------------------------------------
  * Input Registers:
  *
- * RAX                        - TDCALL/SEAMCALL Leaf number.
+ * RAX                        - TDCALL/SEAMCALL composite Leaf code.
  * RCX,RDX,RDI,RSI,RBX,R8-R15 - TDCALL/SEAMCALL Leaf specific input registers.
  *
  * Output Registers:
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 6a1c4fe202bb..8c1a5b7f603a 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1019,7 +1019,6 @@ static __init void set_tdx_addon_features(void)
 static __init int config_tdx_module(struct tdmr_info_list *tdmr_list,
 				    u64 global_keyid)
 {
-	u64 seamcall_fn = TDH_SYS_CONFIG_V0;
 	struct tdx_module_args args = {};
 	u64 *tdmr_pa_array;
 	size_t array_sz;
@@ -1042,18 +1041,18 @@ static __init int config_tdx_module(struct tdmr_info_list *tdmr_list,
 	for (i = 0; i < tdmr_list->nr_consumed_tdmrs; i++)
 		tdmr_pa_array[i] = __pa(tdmr_entry(tdmr_list, i));
 
+	set_tdx_addon_features();
+
 	args.rcx = __pa(tdmr_pa_array);
 	args.rdx = tdmr_list->nr_consumed_tdmrs;
 	args.r8 = global_keyid;
 
-	set_tdx_addon_features();
-
 	if (tdx_addon_feature0) {
 		args.r9 = tdx_addon_feature0;
-		seamcall_fn = TDH_SYS_CONFIG;
+		args.version = 1;
 	}
 
-	ret = seamcall_prerr(seamcall_fn, &args);
+	ret = seamcall_prerr(TDH_SYS_CONFIG, &args);
 
 	/* Free the array as it is not required anymore. */
 	kfree(tdmr_pa_array);
@@ -1515,16 +1514,15 @@ int tdx_module_shutdown(void)
 
 int tdx_module_run_update(void)
 {
-	u64 seamcall_fn = TDH_SYS_UPDATE_V0;
 	struct tdx_module_args args = {};
 	int ret;
 
 	if (tdx_addon_feature0) {
 		args.r9 = tdx_addon_feature0;
-		seamcall_fn = TDH_SYS_UPDATE;
+		args.version = 1;
 	}
 
-	ret = seamcall_prerr(seamcall_fn, &args);
+	ret = seamcall_prerr(TDH_SYS_UPDATE, &args);
 	if (ret)
 		return ret;
 
@@ -2112,6 +2110,7 @@ u64 tdh_vp_init(struct tdx_vp *vp, u64 initial_rcx, u32 x2apicid)
 		.rcx = vp->tdvpr_pa,
 		.rdx = initial_rcx,
 		.r8 = x2apicid,
+		.version = 1,
 	};
 
 	return seamcall(TDH_VP_INIT, &args);
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index 2deb0a5c902e..1f43d2eb2345 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -2,7 +2,6 @@
 #ifndef _X86_VIRT_TDX_H
 #define _X86_VIRT_TDX_H
 
-#include <linux/bitfield.h>
 #include <linux/bits.h>
 
 /*
@@ -12,18 +11,6 @@
  * architectural definitions come first.
  */
 
-/*
- * SEAMCALL leaf:
- *
- * Bit 15:0	Leaf number
- * Bit 23:16	Version number
- */
-#define SEAMCALL_LEAF			GENMASK(15, 0)
-#define SEAMCALL_VER			GENMASK(23, 16)
-
-#define SEAMCALL_LEAF_VER(l, v)		(FIELD_PREP(SEAMCALL_LEAF, l) | \
-					 FIELD_PREP(SEAMCALL_VER, v))
-
 /*
  * TDX module SEAMCALL leaf functions
  */
@@ -44,7 +31,7 @@
 #define TDH_VP_CREATE			10
 #define TDH_MNG_KEY_FREEID		20
 #define TDH_MNG_INIT			21
-#define TDH_VP_INIT			SEAMCALL_LEAF_VER(22, 1)
+#define TDH_VP_INIT			22
 #define TDH_PHYMEM_PAGE_RDMD		24
 #define TDH_VP_RD			26
 #define TDH_PHYMEM_PAGE_RECLAIM		28
@@ -58,11 +45,9 @@
 #define TDH_PHYMEM_CACHE_WB		40
 #define TDH_PHYMEM_PAGE_WBINVD		41
 #define TDH_VP_WR			43
-#define TDH_SYS_CONFIG_V0		45
-#define TDH_SYS_CONFIG			SEAMCALL_LEAF_VER(TDH_SYS_CONFIG_V0, 1)
+#define TDH_SYS_CONFIG			45
 #define TDH_SYS_SHUTDOWN		52
-#define TDH_SYS_UPDATE_V0		53
-#define TDH_SYS_UPDATE			SEAMCALL_LEAF_VER(TDH_SYS_UPDATE_V0, 1)
+#define TDH_SYS_UPDATE			53
 #define TDH_EXT_INIT			60
 #define TDH_EXT_MEM_ADD			61
 #define TDH_SYS_DISABLE			69

---

## [37] Xu Yilun — 2026-06-25
*Subject: Re: [PATCH v2 02/17] x86/virt/tdx: Configure add-on features on TDX
 module init and update*

> >For runtime update, Linux applies a policy that no newer features should
> >be added after update to avoid disrupting live TDX operations. To adhere

I think a global var "static u64 tdx_addon_feature0 *__ro_after_init*;"
better illustrates the policy that add-on feature bitmap should be decided at
boot up and never change later. It will also be used to decide if a specific
add-on feature initialization is needed. We don't want to calculate the bitmap
again and again, though the result must be the same.

Maybe I should strenghthen the commit message:

  ... both phases can use it. This actually mirrors a TDX module internal state
  so that kernel knows which add-on TDX operations (for example, quoting
  SEAMCALLs, which will be added in later patches) are valid.

> 
> 

I tend to keep r9 assignment in the block, it clearly shows which
SEAMCALL version needs what parameters, help people map the code to TDX
module spec.

> 
> >+		seamcall_fn = TDH_SYS_CONFIG;

---

## [38] Xu Yilun — 2026-06-25
*Subject: Re: [PATCH v2 03/17] x86/virt/tdx: Detect if the extensions
 initialization is required*

On Thu, Jun 25, 2026 at 08:19:16AM +0300, Tony Lindgren wrote:
> On Thu, Jun 18, 2026 at 04:13:41PM +0800, Xu Yilun wrote:
> > TDX module extensions support extension SEAMCALLs that are preemptible

Included, thanks.

> 
> Other than that:

---

## [39] Sean Christopherson — 2026-06-25
*Subject: Re: [PATCH v2 16/17] KVM: TDX: Add in-kernel Quote generation*

On Thu, Jun 18, 2026, Xu Yilun wrote:
> From: Peter Fang <peter.fang@intel.com>
> 

Why?

---

## [40] Chao Gao — 2026-06-29
*Subject: Re: [PATCH v2 03/17] x86/virt/tdx: Detect if the extensions
 initialization is required*

>+static __init int init_tdx_module_extensions(void)
>+{

What would happen if the kernel doesn't do this 'ext_required' check
and always does the extension initialization?

If TDH.EXT.INIT returns success when no extension is configured, we
could drop this 'ext_required' from this series entirely.

>+
>+	/* TODO: add the extensions enabling steps here */

---

## [41] Chao Gao — 2026-06-29
*Subject: Re: [PATCH v2 04/17] x86/virt/tdx: Add extra memory to TDX module
 for the extensions*

>+#define HPA_LIST_INFO_FIRST_ENTRY	GENMASK_U64(11, 3)
>+#define HPA_LIST_INFO_PFN		GENMASK_U64(51, 12)

I am not sure about the "manual parameter update" part.

how about:
		/*
		 * The TDX module overwrites RCX to track progress when
		 * this SEAMCALL is interrupted. Use seamcall_ret() to
		 * save and pass the updated value back on retry.
		 */

>+		r = seamcall_ret(TDH_EXT_MEM_ADD, &args);
>+	} while (r == TDX_INTERRUPTED_RESUMABLE);

why -EFAULT?

In sc_retry_prerr(), most SEAMCALL errors are mapped to EIO. Maybe
we should use EIO here.

>+
>+	return 0;

There is no "memory_pool_required_pages" here.

>+	if (!required_pages)
>+		return 0;

Printing 'ret' is useless since it's always -EFAULT.

The real reason to WARN here isn't "no SEAMCALL to reclaim". It is "this
SEAMCALL shouldn't fail, and if it does, things are broken enough that
complex error handling isn't worth it".

>+		if (ret)
>+			break;

This doesn't explain why it should be print. How about:

	/*
	 * Memory for TDX module extensions is never reclaimed and can be
	 * tens of megabytes. Print the amount so users know the cost.
	 */

>+	pr_info("%lu KB consumed for TDX module extensions\n",
>+		required_pages * PAGE_SIZE / 1024);

---

## [42] Chao Gao — 2026-06-29
*Subject: Re: [PATCH v2 06/17] x86/virt/tdx: Re-initialize the extensions on
 runtime TDX module update*

>+/*
>+ * Mostly the same flow as init_tdx_module_extensions(), but rejects adding

Will tdx_ext_init() return an error if more memory is needed?

If yes, we can leave this check to the module. And with ext_required
removed (per my earlier comment), this function simplifies to:

int update_tdx_module_extensions(void)
{
	if (!(tdx_sysinfo.features.tdx_features0 & TDX_FEATURES0_EXT))
		return 0;

	return tdx_ext_init();
}

>+
>+	return tdx_ext_init();

---

## [43] Chao Gao — 2026-06-29
*Subject: Re: [PATCH v2 07/17] x86/virt/tdx: Initialize Quoting extension*

On Thu, Jun 18, 2026 at 04:13:45PM +0800, Xu Yilun wrote:
>From: Peter Fang <peter.fang@intel.com>
>

This jumps into what the patch does without explaining what the Quoting
extension is. A brief background would help reviewers who aren't familiar
with it.

>
>Because Quoting is an optional TDX feature, do not let initialization

This comment isn't quite helpful.

>+static __init int tdx_quote_init(void)
>+{

nit: Reduce indentation of the main body. 

	if (!(tdx_addon_feature0 & TDX_FEATURES0_QUOTE))
		return;
	
	ret = tdx_quote_init();
	WARN_ON_ONCE(ret);


Also, why two functions? Can we inline tdx_quote_init() here, or push the
feature check into it.

>+}
>+

---

## [44] Peter Fang — 2026-06-29
*Subject: Re: [PATCH v2 16/17] KVM: TDX: Add in-kernel Quote generation*

On Thu, Jun 25, 2026 at 11:01:58AM -0700, Sean Christopherson wrote:
> On Thu, Jun 18, 2026, Xu Yilun wrote:
> > From: Peter Fang <peter.fang@intel.com>

Hi Sean,

This is mainly to avoid a round trip to userspace for the GetQuote flow.

New TDX modules can now get a Quote directly via an "extension SEAMCALL"
instead of exiting to userspace and using an SGX enclave. Exiting to
userspace for GetQuote no longer seems worth the overhead/complexity.

The first half of the series enables extension SEAMCALLs. They implement
simple APIs for higher-order security protocols that would otherwise need
to be broken into smaller routines. For Quoting, this allows KVM to get
a Quote directly through TDH.QUOTE.GET. The TDX module needs only the
input data from TDG.VP.VMCALL<GetQuote> for that call.

Thanks,
Peter

---

## [45] Sean Christopherson — 2026-06-29
*Subject: Re: [PATCH v2 16/17] KVM: TDX: Add in-kernel Quote generation*

On Mon, Jun 29, 2026, Peter Fang wrote:
> On Thu, Jun 25, 2026 at 11:01:58AM -0700, Sean Christopherson wrote:
> > On Thu, Jun 18, 2026, Xu Yilun wrote:

Again, why?

> New TDX modules can now get a Quote directly via an "extension SEAMCALL"
> instead of exiting to userspace and using an SGX enclave. Exiting to

I dunno, from a kernel perspective, this is more complexity, not less:

 Documentation/arch/x86/tdx.rst |  19 ++---
 Documentation/virt/kvm/api.rst |   3 +
 arch/x86/include/asm/tdx.h     |   9 +++
 arch/x86/kvm/vmx/tdx.h         |   6 ++
 arch/x86/kvm/vmx/tdx.c         | 135 ++++++++++++++++++++++++++++++++-
 virt/kvm/kvm_main.c            |   1 +
 6 files changed, 163 insertions(+), 10 deletions(-)

> The first half of the series enables extension SEAMCALLs. They implement
> simple APIs for higher-order security protocols that would otherwise need

Answering my own question (though probably poorly), IIUC the answer is that
DICE-based quoting is done through the TDX Module, whereas existing quoting is
done through an SGX enclave and so was routed through userspace.

If that's all there is too this, then why is KVM involved?  I.e. why doesn't the
TDX Module provide the quote directly to the guest?

---

## [46] Peter Fang — 2026-06-29
*Subject: Re: [PATCH v2 08/17] x86/virt/tdx: Prepare Quote buffer during
 extension bringup*

On Thu, Jun 25, 2026 at 09:08:28AM +0300, Tony Lindgren wrote:
> On Thu, Jun 18, 2026 at 04:13:46PM +0800, Xu Yilun wrote:
> > From: Peter Fang <peter.fang@intel.com>

Thanks. I'm planning to switch to dynamic allocation in the next
revision to make this simpler [1]. So the template will be the
HPA_LINKED_LIST node pages plus the next pointers in these nodes.

[1] https://lore.kernel.org/linux-coco/20260626095833.GB1600180@pedri/

---

## [47] Peter Fang — 2026-06-29
*Subject: Re: [PATCH v2 11/17] x86/virt/tdx: Add interface to generate a Quote*

On Thu, Jun 25, 2026 at 09:05:28AM +0300, Tony Lindgren wrote:
> On Thu, Jun 18, 2026 at 04:13:49PM +0800, Xu Yilun wrote:
> > From: Peter Fang <peter.fang@intel.com>

Hm, actually tdx_quote is an output buffer as well (in the form of a
head pointer: qdata->hpa_entries_pa). Maybe this code needs better
commenting...

---

## [48] Peter Fang — 2026-06-29
*Subject: Re: [PATCH v2 07/17] x86/virt/tdx: Initialize Quoting extension*

On Mon, Jun 29, 2026 at 04:33:25PM +0800, Chao Gao wrote:
> On Thu, Jun 18, 2026 at 04:13:45PM +0800, Xu Yilun wrote:
> >From: Peter Fang <peter.fang@intel.com>

Yep, I'll add more background in the changelog.

> 
> >diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c

Got it. It makes more sense to add it in patch 12.

> 
> >+static __init int tdx_quote_init(void)

That's better. I'll make this change.

> 
> 

tdx_quote_init() has a second call site in patch 12
(update_tdx_quoting_extension()), during runtime TDX module update.

Adding the "if (feature)" check inside a SEAMCALL helper doesn't seem
like a common pattern. I'm a bit concerned about making this look
inconsistent.

>

---
