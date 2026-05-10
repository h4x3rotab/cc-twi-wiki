---
title: 'coc: tsm: Implement ->connect()/->disconnect() callbacks for ARM CCA IDE setup'
date: 2025-10-27
last_reply: 2026-01-06
message_count: 34
participants: ['Aneesh Kumar K.V (Arm)', 'Jonathan Cameron', 'Jason Gunthorpe']
---

## [1] Aneesh Kumar K.V (Arm) — 2025-10-27

This patch series implements the TSM ->connect() and ->disconnect() callbacks
required for the ARM CCA IDE setup described in the RMM ALP17 specification [1].

The series builds upon the TSM framework patches posted at [2] and depends on
the KVM CCA patchset [3]. A git repository containing all the related changes is
available at [4].

Testing / Usage

To initiate the IDE setup:
echo tsm0 > /sys/bus/pci/devices/$DEVICE/tsm/connect

To disconnect:
echo tsm0 > /sys/bus/pci/devices/$DEVICE/tsm/disconnect

[1] https://developer.arm.com/-/cdn-downloads/permalink/Architectures/Armv9/DEN0137_1.1-alp17.zip
[2] https://lore.kernel.org/all/20251024020418.1366664-1-dan.j.williams@intel.com
[3] https://lore.kernel.org/all/461fa23f-9add-40e5-a0d0-759030e7c70b@arm.com
[4] https://git.gitlab.arm.com/linux-arm/linux-cca.git cca/topics/cca-ide-setup-upstream-v2


Aneesh Kumar K.V (Arm) (9):
  KVM: arm64: RMI: Export kvm_has_da_feature
  firmware: smccc: coco: Manage arm-smccc platform device and CCA
    auxiliary drivers
  coco: guest: arm64: Drop dummy RSI platform device stub
  coco: host: arm64: Add host TSM callback and IDE stream allocation
    support
  coco: host: arm64: Build and register RMM pdev descriptors
  coco: host: arm64: Add RMM device communication helpers
  coco: host: arm64: Add helper to stop and tear down an RMM pdev
  coco: host: arm64: Instantiate RMM pdev during device connect
  coco: host: arm64: Register device public key with RMM

Lukas Wunner (3):
  X.509: Make certificate parser public
  X.509: Parse Subject Alternative Name in certificates
  X.509: Move certificate length retrieval into new helper

 arch/arm64/include/asm/kvm_rmi.h              |   1 +
 arch/arm64/include/asm/rmi_cmds.h             |  78 +++
 arch/arm64/include/asm/rmi_smc.h              | 180 +++++-
 arch/arm64/include/asm/rsi.h                  |   2 +-
 arch/arm64/kernel/rsi.c                       |  15 -
 arch/arm64/kvm/rmi.c                          |   6 +
 crypto/asymmetric_keys/x509_cert_parser.c     |   9 +
 crypto/asymmetric_keys/x509_loader.c          |  38 +-
 crypto/asymmetric_keys/x509_parser.h          |  40 +-
 drivers/firmware/smccc/Kconfig                |   1 +
 drivers/firmware/smccc/smccc.c                |  56 ++
 drivers/virt/coco/Kconfig                     |   2 +
 drivers/virt/coco/Makefile                    |   1 +
 drivers/virt/coco/arm-cca-guest/Kconfig       |   1 +
 drivers/virt/coco/arm-cca-guest/Makefile      |   2 +
 .../{arm-cca-guest.c => arm-cca.c}            |  57 +-
 drivers/virt/coco/arm-cca-host/Kconfig        |  23 +
 drivers/virt/coco/arm-cca-host/Makefile       |   5 +
 drivers/virt/coco/arm-cca-host/arm-cca.c      | 261 ++++++++
 drivers/virt/coco/arm-cca-host/rmi-da.c       | 608 ++++++++++++++++++
 drivers/virt/coco/arm-cca-host/rmi-da.h       | 111 ++++
 include/keys/asymmetric-type.h                |   2 +
 include/keys/x509-parser.h                    |  55 ++
 23 files changed, 1457 insertions(+), 97 deletions(-)
 rename drivers/virt/coco/arm-cca-guest/{arm-cca-guest.c => arm-cca.c} (85%)
 create mode 100644 drivers/virt/coco/arm-cca-host/Kconfig
 create mode 100644 drivers/virt/coco/arm-cca-host/Makefile
 create mode 100644 drivers/virt/coco/arm-cca-host/arm-cca.c
 create mode 100644 drivers/virt/coco/arm-cca-host/rmi-da.c
 create mode 100644 drivers/virt/coco/arm-cca-host/rmi-da.h
 create mode 100644 include/keys/x509-parser.h

---

## [2] Aneesh Kumar K.V (Arm) — 2025-10-27
*Subject: [PATCH RESEND v2 01/12] KVM: arm64: RMI: Export kvm_has_da_feature*

This will be used in later patches

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/kvm_rmi.h | 1 +
 arch/arm64/include/asm/rmi_smc.h | 1 +
 arch/arm64/kvm/rmi.c             | 6 ++++++
 3 files changed, 8 insertions(+)

diff --git a/arch/arm64/include/asm/kvm_rmi.h b/arch/arm64/include/asm/kvm_rmi.h
index 1b2cdaac6c50..a967061af6ed 100644
--- a/arch/arm64/include/asm/kvm_rmi.h
+++ b/arch/arm64/include/asm/kvm_rmi.h
@@ -90,6 +90,7 @@ u32 kvm_realm_ipa_limit(void);
 u32 kvm_realm_vgic_nr_lr(void);
 u8 kvm_realm_max_pmu_counters(void);
 unsigned int kvm_realm_sve_max_vl(void);
+bool kvm_has_da_feature(void);
 
 u64 kvm_realm_reset_id_aa64dfr0_el1(const struct kvm_vcpu *vcpu, u64 val);
 
diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
index 1000368f1bca..2ea657a87402 100644
--- a/arch/arm64/include/asm/rmi_smc.h
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -87,6 +87,7 @@ enum rmi_ripas {
 #define RMI_FEATURE_REGISTER_0_GICV3_NUM_LRS	GENMASK(37, 34)
 #define RMI_FEATURE_REGISTER_0_MAX_RECS_ORDER	GENMASK(41, 38)
 #define RMI_FEATURE_REGISTER_0_Reserved		GENMASK(63, 42)
+#define RMI_FEATURE_REGISTER_0_DA		BIT(42)
 
 #define RMI_REALM_PARAM_FLAG_LPA2		BIT(0)
 #define RMI_REALM_PARAM_FLAG_SVE		BIT(1)
diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index 478a73e0b35a..08f3d2362dfd 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -1738,6 +1738,12 @@ int kvm_init_realm_vm(struct kvm *kvm)
 	return 0;
 }
 
+bool kvm_has_da_feature(void)
+{
+	return rmi_has_feature(RMI_FEATURE_REGISTER_0_DA);
+}
+EXPORT_SYMBOL_GPL(kvm_has_da_feature);
+
 void kvm_init_rmi(void)
 {
 	/* Only 4k page size on the host is supported */

---

## [3] Aneesh Kumar K.V (Arm) — 2025-10-27
*Subject: [PATCH RESEND v2 02/12] firmware: smccc: coco: Manage arm-smccc platform device and CCA auxiliary drivers*

Make the SMCCC driver responsible for registering the arm-smccc platform
device and after confirming the relevant SMCCC function IDs, create
the arm_cca_guest auxiliary device.

Also update the arm-cca-guest driver to use the auxiliary device
interface instead of the platform device (arm-cca-dev). The removal of
the platform device registration will follow in a subsequent patch,
allowing this change to be applied without immediately breaking existing
userspace dependencies [1].

[1] https://lore.kernel.org/all/4a7d84b2-2ec4-4773-a2d5-7b63d5c683cf@arm.com
Cc: Jeremy Linton <jeremy.linton@arm.com>
Cc: Greg KH <gregkh@linuxfoundation.org>
Cc: Mark Rutland <mark.rutland@arm.com>
Cc: Lorenzo Pieralisi <lpieralisi@kernel.org>
Cc: Sudeep Holla <sudeep.holla@arm.com>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rsi.h                  |  2 +-
 arch/arm64/kernel/rsi.c                       |  2 +-
 drivers/firmware/smccc/Kconfig                |  1 +
 drivers/firmware/smccc/smccc.c                | 37 ++++++++++++
 drivers/virt/coco/arm-cca-guest/Kconfig       |  1 +
 drivers/virt/coco/arm-cca-guest/Makefile      |  2 +
 .../{arm-cca-guest.c => arm-cca.c}            | 57 +++++++++----------
 7 files changed, 71 insertions(+), 31 deletions(-)
 rename drivers/virt/coco/arm-cca-guest/{arm-cca-guest.c => arm-cca.c} (85%)

diff --git a/arch/arm64/include/asm/rsi.h b/arch/arm64/include/asm/rsi.h
index 88b50d660e85..2d2d363aaaee 100644
--- a/arch/arm64/include/asm/rsi.h
+++ b/arch/arm64/include/asm/rsi.h
@@ -10,7 +10,7 @@
 #include <linux/jump_label.h>
 #include <asm/rsi_cmds.h>
 
-#define RSI_PDEV_NAME "arm-cca-dev"
+#define RSI_DEV_NAME "arm-rsi-dev"
 
 DECLARE_STATIC_KEY_FALSE(rsi_present);
 
diff --git a/arch/arm64/kernel/rsi.c b/arch/arm64/kernel/rsi.c
index c64a06f58c0b..5d711942e543 100644
--- a/arch/arm64/kernel/rsi.c
+++ b/arch/arm64/kernel/rsi.c
@@ -160,7 +160,7 @@ void __init arm64_rsi_init(void)
 }
 
 static struct platform_device rsi_dev = {
-	.name = RSI_PDEV_NAME,
+	.name = "arm-cca-dev",
 	.id = PLATFORM_DEVID_NONE
 };
 
diff --git a/drivers/firmware/smccc/Kconfig b/drivers/firmware/smccc/Kconfig
index 15e7466179a6..2b6984757241 100644
--- a/drivers/firmware/smccc/Kconfig
+++ b/drivers/firmware/smccc/Kconfig
@@ -8,6 +8,7 @@ config HAVE_ARM_SMCCC
 config HAVE_ARM_SMCCC_DISCOVERY
 	bool
 	depends on ARM_PSCI_FW
+	select AUXILIARY_BUS
 	default y
 	help
 	 SMCCC v1.0 lacked discoverability and hence PSCI v1.0 was updated
diff --git a/drivers/firmware/smccc/smccc.c b/drivers/firmware/smccc/smccc.c
index bdee057db2fd..3dbf0d067cc5 100644
--- a/drivers/firmware/smccc/smccc.c
+++ b/drivers/firmware/smccc/smccc.c
@@ -10,7 +10,12 @@
 #include <linux/arm-smccc.h>
 #include <linux/kernel.h>
 #include <linux/platform_device.h>
+#include <linux/auxiliary_bus.h>
+
 #include <asm/archrandom.h>
+#ifdef CONFIG_ARM64
+#include <asm/rsi_cmds.h>
+#endif
 
 static u32 smccc_version = ARM_SMCCC_VERSION_1_0;
 static enum arm_smccc_conduit smccc_conduit = SMCCC_CONDUIT_NONE;
@@ -81,10 +86,42 @@ bool arm_smccc_hypervisor_has_uuid(const uuid_t *hyp_uuid)
 }
 EXPORT_SYMBOL_GPL(arm_smccc_hypervisor_has_uuid);
 
+#ifdef CONFIG_ARM64
+static void __init register_rsi_device(struct platform_device *pdev)
+{
+	unsigned long ver_lower, ver_higher;
+	unsigned long ret = rsi_request_version(RSI_ABI_VERSION,
+						&ver_lower,
+						&ver_higher);
+
+	if (ret == RSI_SUCCESS)
+		__devm_auxiliary_device_create(&pdev->dev,
+					"arm_cca_guest", RSI_DEV_NAME, NULL, 0);
+
+}
+#else
+static void __init register_rsi_device(struct platform_device *pdev)
+{
+
+}
+#endif
+
 static int __init smccc_devices_init(void)
 {
 	struct platform_device *pdev;
 
+	pdev = platform_device_register_simple("arm-smccc",
+					PLATFORM_DEVID_NONE, NULL, 0);
+	if (IS_ERR(pdev)) {
+		pr_err("arm-smccc: could not register device: %ld\n", PTR_ERR(pdev));
+	} else {
+		/*
+		 * Register the RMI and RSI devices only when firmware exposes
+		 * the required SMCCC function IDs at a supported revision.
+		 */
+		register_rsi_device(pdev);
+	}
+
 	if (smccc_trng_available) {
 		pdev = platform_device_register_simple("smccc_trng", -1,
 						       NULL, 0);
diff --git a/drivers/virt/coco/arm-cca-guest/Kconfig b/drivers/virt/coco/arm-cca-guest/Kconfig
index 3f0f013f03f1..a42359a90558 100644
--- a/drivers/virt/coco/arm-cca-guest/Kconfig
+++ b/drivers/virt/coco/arm-cca-guest/Kconfig
@@ -2,6 +2,7 @@ config ARM_CCA_GUEST
 	tristate "Arm CCA Guest driver"
 	depends on ARM64
 	select TSM_REPORTS
+	select AUXILIARY_BUS
 	help
 	  The driver provides userspace interface to request and
 	  attestation report from the Realm Management Monitor(RMM).
diff --git a/drivers/virt/coco/arm-cca-guest/Makefile b/drivers/virt/coco/arm-cca-guest/Makefile
index 69eeba08e98a..75a120e24fda 100644
--- a/drivers/virt/coco/arm-cca-guest/Makefile
+++ b/drivers/virt/coco/arm-cca-guest/Makefile
@@ -1,2 +1,4 @@
 # SPDX-License-Identifier: GPL-2.0-only
 obj-$(CONFIG_ARM_CCA_GUEST) += arm-cca-guest.o
+
+arm-cca-guest-y +=  arm-cca.o
diff --git a/drivers/virt/coco/arm-cca-guest/arm-cca-guest.c b/drivers/virt/coco/arm-cca-guest/arm-cca.c
similarity index 85%
rename from drivers/virt/coco/arm-cca-guest/arm-cca-guest.c
rename to drivers/virt/coco/arm-cca-guest/arm-cca.c
index 0c9ea24a200c..dc96171791db 100644
--- a/drivers/virt/coco/arm-cca-guest/arm-cca-guest.c
+++ b/drivers/virt/coco/arm-cca-guest/arm-cca.c
@@ -3,6 +3,7 @@
  * Copyright (C) 2023 ARM Ltd.
  */
 
+#include <linux/auxiliary_bus.h>
 #include <linux/arm-smccc.h>
 #include <linux/cc_platform.h>
 #include <linux/kernel.h>
@@ -181,52 +182,50 @@ static int arm_cca_report_new(struct tsm_report *report, void *data)
 	return ret;
 }
 
-static const struct tsm_report_ops arm_cca_tsm_ops = {
+static const struct tsm_report_ops arm_cca_tsm_report_ops = {
 	.name = KBUILD_MODNAME,
 	.report_new = arm_cca_report_new,
 };
 
-/**
- * arm_cca_guest_init - Register with the Trusted Security Module (TSM)
- * interface.
- *
- * Return:
- * * %0        - Registered successfully with the TSM interface.
- * * %-ENODEV  - The execution context is not an Arm Realm.
- * * %-EBUSY   - Already registered.
- */
-static int __init arm_cca_guest_init(void)
+static void unregister_cca_tsm_report(void *data)
+{
+	tsm_report_unregister(&arm_cca_tsm_report_ops);
+}
+
+static int cca_devsec_tsm_probe(struct auxiliary_device *adev,
+				const struct auxiliary_device_id *id)
 {
 	int ret;
 
 	if (!is_realm_world())
 		return -ENODEV;
 
-	ret = tsm_report_register(&arm_cca_tsm_ops, NULL);
-	if (ret < 0)
+	ret = tsm_report_register(&arm_cca_tsm_report_ops, NULL);
+	if (ret < 0) {
 		pr_err("Error %d registering with TSM\n", ret);
+		return ret;
+	}
 
-	return ret;
-}
-module_init(arm_cca_guest_init);
+	ret = devm_add_action_or_reset(&adev->dev, unregister_cca_tsm_report, NULL);
+	if (ret < 0) {
+		pr_err("Error %d registering devm action\n", ret);
+		return ret;
+	}
 
-/**
- * arm_cca_guest_exit - unregister with the Trusted Security Module (TSM)
- * interface.
- */
-static void __exit arm_cca_guest_exit(void)
-{
-	tsm_report_unregister(&arm_cca_tsm_ops);
+	return 0;
 }
-module_exit(arm_cca_guest_exit);
 
-/* modalias, so userspace can autoload this module when RSI is available */
-static const struct platform_device_id arm_cca_match[] __maybe_unused = {
-	{ RSI_PDEV_NAME, 0},
-	{ }
+static const struct auxiliary_device_id cca_devsec_tsm_id_table[] = {
+	{ .name =  KBUILD_MODNAME "." RSI_DEV_NAME },
+	{}
 };
+MODULE_DEVICE_TABLE(auxiliary, cca_devsec_tsm_id_table);
 
-MODULE_DEVICE_TABLE(platform, arm_cca_match);
+static struct auxiliary_driver cca_devsec_tsm_driver = {
+	.probe = cca_devsec_tsm_probe,
+	.id_table = cca_devsec_tsm_id_table,
+};
+module_auxiliary_driver(cca_devsec_tsm_driver);
 MODULE_AUTHOR("Sami Mujawar <sami.mujawar@arm.com>");
 MODULE_DESCRIPTION("Arm CCA Guest TSM Driver");
 MODULE_LICENSE("GPL");

---

## [4] Aneesh Kumar K.V (Arm) — 2025-10-27
*Subject: [PATCH RESEND v2 03/12] coco: guest: arm64: Drop dummy RSI platform device stub*

The SMCCC firmware driver now creates the `arm-smccc` platform device
and also creates the CCA auxiliary devices once the RSI ABI is
discovered. This makes the arch-specific arm64_create_dummy_rsi_dev()
helper redundant. Remove the arm-cca-dev platform device registration
and let the SMCCC probe manage the RSI device.

systemd match on platform:arm-cca-dev for confidential vm detection [1].
Losing the platform device registration can break that. Keeping this
removal in its own change makes it easy to revert if that regression
blocks the rollout.

[1] https://lore.kernel.org/all/4a7d84b2-2ec4-4773-a2d5-7b63d5c683cf@arm.com

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/kernel/rsi.c | 15 ---------------
 1 file changed, 15 deletions(-)

diff --git a/arch/arm64/kernel/rsi.c b/arch/arm64/kernel/rsi.c
index 5d711942e543..1b716d18b80e 100644
--- a/arch/arm64/kernel/rsi.c
+++ b/arch/arm64/kernel/rsi.c
@@ -158,18 +158,3 @@ void __init arm64_rsi_init(void)
 
 	static_branch_enable(&rsi_present);
 }
-
-static struct platform_device rsi_dev = {
-	.name = "arm-cca-dev",
-	.id = PLATFORM_DEVID_NONE
-};
-
-static int __init arm64_create_dummy_rsi_dev(void)
-{
-	if (is_realm_world() &&
-	    platform_device_register(&rsi_dev))
-		pr_err("failed to register rsi platform device\n");
-	return 0;
-}
-
-arch_initcall(arm64_create_dummy_rsi_dev)

---

## [5] Aneesh Kumar K.V (Arm) — 2025-10-27
*Subject: [PATCH RESEND v2 04/12] coco: host: arm64: Add host TSM callback and IDE stream allocation support*

Register the TSM callback when the DA feature is supported by KVM.

This driver handles IDE stream setup for both the root port and PCIe
endpoints. Root port IDE stream enablement itself is managed by RMM.

In addition, the driver registers `pci_tsm_ops` with the TSM subsystem.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rmi_smc.h         |   2 +
 drivers/firmware/smccc/smccc.c           |  19 +++
 drivers/virt/coco/Kconfig                |   2 +
 drivers/virt/coco/Makefile               |   1 +
 drivers/virt/coco/arm-cca-host/Kconfig   |  19 +++
 drivers/virt/coco/arm-cca-host/Makefile  |   5 +
 drivers/virt/coco/arm-cca-host/arm-cca.c | 192 +++++++++++++++++++++++
 drivers/virt/coco/arm-cca-host/rmi-da.h  |  41 +++++
 8 files changed, 281 insertions(+)
 create mode 100644 drivers/virt/coco/arm-cca-host/Kconfig
 create mode 100644 drivers/virt/coco/arm-cca-host/Makefile
 create mode 100644 drivers/virt/coco/arm-cca-host/arm-cca.c
 create mode 100644 drivers/virt/coco/arm-cca-host/rmi-da.h

diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
index 2ea657a87402..fe1c91ffc0ab 100644
--- a/arch/arm64/include/asm/rmi_smc.h
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -12,6 +12,8 @@
 
 #include <linux/arm-smccc.h>
 
+#define RMI_DEV_NAME "arm-rmi-dev"
+
 #define SMC_RMI_CALL(func)				\
 	ARM_SMCCC_CALL_VAL(ARM_SMCCC_FAST_CALL,		\
 			   ARM_SMCCC_SMC_64,		\
diff --git a/drivers/firmware/smccc/smccc.c b/drivers/firmware/smccc/smccc.c
index 3dbf0d067cc5..9cabe750533c 100644
--- a/drivers/firmware/smccc/smccc.c
+++ b/drivers/firmware/smccc/smccc.c
@@ -15,6 +15,7 @@
 #include <asm/archrandom.h>
 #ifdef CONFIG_ARM64
 #include <asm/rsi_cmds.h>
+#include <asm/rmi_smc.h>
 #endif
 
 static u32 smccc_version = ARM_SMCCC_VERSION_1_0;
@@ -99,10 +100,27 @@ static void __init register_rsi_device(struct platform_device *pdev)
 					"arm_cca_guest", RSI_DEV_NAME, NULL, 0);
 
 }
+
+static void __init register_rmi_device(struct platform_device *pdev)
+{
+	struct arm_smccc_res res;
+	unsigned long host_version = RMI_ABI_VERSION(RMI_ABI_MAJOR_VERSION,
+						     RMI_ABI_MINOR_VERSION);
+
+	arm_smccc_1_1_invoke(SMC_RMI_VERSION, host_version, &res);
+	if (res.a0 == RMI_SUCCESS)
+		__devm_auxiliary_device_create(&pdev->dev,
+					"arm_cca_host", RMI_DEV_NAME, NULL, 0);
+}
 #else
 static void __init register_rsi_device(struct platform_device *pdev)
 {
 
+}
+
+static void __init register_rmi_device(struct platform_device *pdev)
+{
+
 }
 #endif
 
@@ -120,6 +138,7 @@ static int __init smccc_devices_init(void)
 		 * the required SMCCC function IDs at a supported revision.
 		 */
 		register_rsi_device(pdev);
+		register_rmi_device(pdev);
 	}
 
 	if (smccc_trng_available) {
diff --git a/drivers/virt/coco/Kconfig b/drivers/virt/coco/Kconfig
index bb0c6d6ddcc8..65b284c59b96 100644
--- a/drivers/virt/coco/Kconfig
+++ b/drivers/virt/coco/Kconfig
@@ -15,5 +15,7 @@ source "drivers/virt/coco/arm-cca-guest/Kconfig"
 
 source "drivers/virt/coco/guest/Kconfig"
 
+source "drivers/virt/coco/arm-cca-host/Kconfig"
+
 config TSM
 	bool
diff --git a/drivers/virt/coco/Makefile b/drivers/virt/coco/Makefile
index cb52021912b3..c06b66041a49 100644
--- a/drivers/virt/coco/Makefile
+++ b/drivers/virt/coco/Makefile
@@ -9,3 +9,4 @@ obj-$(CONFIG_INTEL_TDX_GUEST)	+= tdx-guest/
 obj-$(CONFIG_ARM_CCA_GUEST)	+= arm-cca-guest/
 obj-$(CONFIG_TSM) 		+= tsm-core.o
 obj-$(CONFIG_TSM_GUEST)		+= guest/
+obj-$(CONFIG_ARM_CCA_HOST)	+= arm-cca-host/
diff --git a/drivers/virt/coco/arm-cca-host/Kconfig b/drivers/virt/coco/arm-cca-host/Kconfig
new file mode 100644
index 000000000000..1febd316fb77
--- /dev/null
+++ b/drivers/virt/coco/arm-cca-host/Kconfig
@@ -0,0 +1,19 @@
+# SPDX-License-Identifier: GPL-2.0-only
+#
+# TSM (TEE Security Manager) host drivers
+#
+config ARM_CCA_HOST
+	tristate "Arm CCA Host driver"
+	depends on ARM64
+	depends on PCI_TSM
+	depends on KVM
+	select TSM
+	select AUXILIARY_BUS
+
+	help
+	  ARM CCA RMM firmware is the trusted runtime that enforces memory
+	  isolation and security for confidential computing on ARM. This driver
+	  provides the interface for communicating with RMM to support secure
+	  device assignment.
+
+	  If you choose 'M' here, this module will be called arm-cca-host.
diff --git a/drivers/virt/coco/arm-cca-host/Makefile b/drivers/virt/coco/arm-cca-host/Makefile
new file mode 100644
index 000000000000..ad353b07e95a
--- /dev/null
+++ b/drivers/virt/coco/arm-cca-host/Makefile
@@ -0,0 +1,5 @@
+# SPDX-License-Identifier: GPL-2.0-only
+#
+obj-$(CONFIG_ARM_CCA_HOST) += arm-cca-host.o
+
+arm-cca-host-$(CONFIG_TSM) +=  arm-cca.o
diff --git a/drivers/virt/coco/arm-cca-host/arm-cca.c b/drivers/virt/coco/arm-cca-host/arm-cca.c
new file mode 100644
index 000000000000..18e5bf6adea4
--- /dev/null
+++ b/drivers/virt/coco/arm-cca-host/arm-cca.c
@@ -0,0 +1,192 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/*
+ * Copyright (C) 2025 ARM Ltd.
+ */
+
+#include <linux/auxiliary_bus.h>
+#include <linux/pci-tsm.h>
+#include <linux/pci-ide.h>
+#include <linux/module.h>
+#include <linux/pci.h>
+#include <linux/tsm.h>
+#include <linux/vmalloc.h>
+#include <linux/cleanup.h>
+#include <linux/kvm_host.h>
+
+#include "rmi-da.h"
+
+/* Total number of stream id supported at root port level */
+#define MAX_STREAM_ID	256
+
+
+static struct pci_tsm *cca_tsm_pci_probe(struct tsm_dev *tsm_dev, struct pci_dev *pdev)
+{
+	int rc;
+
+	if (!is_pci_tsm_pf0(pdev)) {
+		struct cca_host_fn_dsc *fn_dsc __free(kfree) =
+			kzalloc(sizeof(*fn_dsc), GFP_KERNEL);
+
+		if (!fn_dsc)
+			return NULL;
+
+		rc = pci_tsm_link_constructor(pdev, &fn_dsc->pci, tsm_dev);
+		if (rc)
+			return NULL;
+
+		return &no_free_ptr(fn_dsc)->pci;
+	}
+
+	if (!pdev->ide_cap)
+		return NULL;
+
+	struct cca_host_pf0_dsc *pf0_dsc __free(kfree) =
+					kzalloc(sizeof(*pf0_dsc), GFP_KERNEL);
+	if (!pf0_dsc)
+		return NULL;
+
+	rc = pci_tsm_pf0_constructor(pdev, &pf0_dsc->pci, tsm_dev);
+	if (rc)
+		return NULL;
+
+	pci_dbg(pdev, "tsm enabled\n");
+	return &no_free_ptr(pf0_dsc)->pci.base_tsm;
+}
+
+static void cca_tsm_pci_remove(struct pci_tsm *tsm)
+{
+	struct pci_dev *pdev = tsm->pdev;
+
+	if (is_pci_tsm_pf0(pdev)) {
+		struct cca_host_pf0_dsc *pf0_dsc = to_cca_pf0_dsc(pdev);
+
+		pci_tsm_pf0_destructor(&pf0_dsc->pci);
+		kfree(pf0_dsc);
+	} else {
+		struct cca_host_fn_dsc *fn_dsc = to_cca_fn_dsc(pdev);
+
+		kfree(fn_dsc);
+		return;
+	}
+}
+
+/* For now global for simplicity. Protected by pci_tsm_rwsem */
+static DECLARE_BITMAP(cca_stream_ids, MAX_STREAM_ID);
+
+static int cca_tsm_connect(struct pci_dev *pdev)
+{
+	struct pci_dev *rp = pcie_find_root_port(pdev);
+	struct cca_host_pf0_dsc *pf0_dsc;
+	struct pci_ide *ide;
+	int rc, stream_id;
+
+	/* Only function 0 supports connect in host */
+	if (WARN_ON(!is_pci_tsm_pf0(pdev)))
+		return -EIO;
+
+	pf0_dsc = to_cca_pf0_dsc(pdev);
+	/* Allocate stream id */
+	stream_id = find_first_zero_bit(cca_stream_ids, MAX_STREAM_ID);
+	if (stream_id == MAX_STREAM_ID)
+		return -EBUSY;
+	set_bit(stream_id, cca_stream_ids);
+
+	ide = pci_ide_stream_alloc(pdev);
+	if (!ide) {
+		rc = -ENOMEM;
+		goto err_stream_alloc;
+	}
+
+	pf0_dsc->sel_stream = ide;
+	ide->stream_id = stream_id;
+	rc = pci_ide_stream_register(ide);
+	if (rc)
+		goto err_stream;
+
+	pci_ide_stream_setup(pdev, ide);
+	pci_ide_stream_setup(rp, ide);
+
+	rc = tsm_ide_stream_register(ide);
+	if (rc)
+		goto err_tsm;
+
+	/*
+	 * Once ide is setup, enable the stream at the endpoint
+	 * Root port will be done by RMM
+	 */
+	pci_ide_stream_enable(pdev, ide);
+	return 0;
+
+err_tsm:
+	pci_ide_stream_teardown(rp, ide);
+	pci_ide_stream_teardown(pdev, ide);
+	pci_ide_stream_unregister(ide);
+err_stream:
+	pci_ide_stream_free(ide);
+err_stream_alloc:
+	clear_bit(stream_id, cca_stream_ids);
+
+	return rc;
+}
+
+static void cca_tsm_disconnect(struct pci_dev *pdev)
+{
+	int stream_id;
+	struct pci_ide *ide;
+	struct cca_host_pf0_dsc *pf0_dsc;
+
+	pf0_dsc = to_cca_pf0_dsc(pdev);
+	if (!pf0_dsc)
+		return;
+
+	ide = pf0_dsc->sel_stream;
+	stream_id = ide->stream_id;
+	pf0_dsc->sel_stream = NULL;
+
+	pci_ide_stream_release(ide);
+	clear_bit(stream_id, cca_stream_ids);
+}
+
+static struct pci_tsm_ops cca_link_pci_ops = {
+	.probe = cca_tsm_pci_probe,
+	.remove = cca_tsm_pci_remove,
+	.connect = cca_tsm_connect,
+	.disconnect = cca_tsm_disconnect,
+};
+
+static void cca_link_tsm_remove(void *tsm_dev)
+{
+	tsm_unregister(tsm_dev);
+}
+
+static int cca_link_tsm_probe(struct auxiliary_device *adev,
+			      const struct auxiliary_device_id *id)
+{
+	if (kvm_has_da_feature()) {
+		struct tsm_dev *tsm_dev;
+
+		tsm_dev = tsm_register(&adev->dev, &cca_link_pci_ops);
+		if (IS_ERR(tsm_dev))
+			return PTR_ERR(tsm_dev);
+
+		return devm_add_action_or_reset(&adev->dev,
+					cca_link_tsm_remove, tsm_dev);
+	}
+	return -ENODEV;
+}
+
+static const struct auxiliary_device_id cca_link_tsm_id_table[] = {
+	{ .name =  KBUILD_MODNAME "." RMI_DEV_NAME },
+	{}
+};
+MODULE_DEVICE_TABLE(auxiliary, cca_link_tsm_id_table);
+
+static struct auxiliary_driver cca_link_tsm_driver = {
+	.probe = cca_link_tsm_probe,
+	.id_table = cca_link_tsm_id_table,
+};
+module_auxiliary_driver(cca_link_tsm_driver);
+MODULE_IMPORT_NS("PCI_IDE");
+MODULE_AUTHOR("Aneesh Kumar <aneesh.kumar@kernel.org>");
+MODULE_DESCRIPTION("ARM CCA Host TSM driver");
+MODULE_LICENSE("GPL");
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.h b/drivers/virt/coco/arm-cca-host/rmi-da.h
new file mode 100644
index 000000000000..01dfb42cd39e
--- /dev/null
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.h
@@ -0,0 +1,41 @@
+/* SPDX-License-Identifier: GPL-2.0-only */
+/*
+ * Copyright (C) 2025 ARM Ltd.
+ */
+
+#ifndef _VIRT_COCO_RMM_DA_H_
+#define _VIRT_COCO_RMM_DA_H_
+
+#include <linux/pci.h>
+#include <linux/pci-ide.h>
+#include <linux/pci-tsm.h>
+#include <asm/rmi_smc.h>
+
+/* dsc = device security context */
+struct cca_host_pf0_dsc {
+	struct pci_tsm_pf0 pci;
+	struct pci_ide *sel_stream;
+};
+
+struct cca_host_fn_dsc {
+	struct pci_tsm pci;
+};
+
+static inline struct cca_host_pf0_dsc *to_cca_pf0_dsc(struct pci_dev *pdev)
+{
+	struct pci_tsm *tsm = pdev->tsm;
+
+	if (!tsm || pdev->is_virtfn || !is_pci_tsm_pf0(pdev))
+		return NULL;
+
+	return container_of(tsm, struct cca_host_pf0_dsc, pci.base_tsm);
+}
+
+static inline struct cca_host_fn_dsc *to_cca_fn_dsc(struct pci_dev *pdev)
+{
+	struct pci_tsm *tsm = pdev->tsm;
+
+	return container_of(tsm, struct cca_host_fn_dsc, pci);
+}
+
+#endif

---

## [6] Aneesh Kumar K.V (Arm) — 2025-10-27
*Subject: [PATCH RESEND v2 05/12] coco: host: arm64: Build and register RMM pdev descriptors*

Add the SMCCC plumbing for RMI_PDEV_AUX_COUNT, RMI_PDEV_CREATE, and
RMI_PDEV_GET_STATE, describe the pdev state enum/flags in rmi_smc.h,
and extend the PF0 descriptor so we can hold the RMM-side pdev handle
plus its auxiliary granules.

Implement pdev_create() to delegate backing pages, populate the pdev
parameters from the device's RID, ECAM window, IDE stream, and
non-coherent address ranges, and invoke RMI_PDEV_CREATE. The helper
keeps track of the allocated/assigned granules and unwinds them on
failure, so the host driver can reliably establish the pdev channel
before kicking off further IDE/TSM setup.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rmi_cmds.h       |  31 ++++++
 arch/arm64/include/asm/rmi_smc.h        |  94 +++++++++++++++-
 drivers/virt/coco/arm-cca-host/Makefile |   2 +-
 drivers/virt/coco/arm-cca-host/rmi-da.c | 141 ++++++++++++++++++++++++
 drivers/virt/coco/arm-cca-host/rmi-da.h |   5 +
 5 files changed, 271 insertions(+), 2 deletions(-)
 create mode 100644 drivers/virt/coco/arm-cca-host/rmi-da.c

diff --git a/arch/arm64/include/asm/rmi_cmds.h b/arch/arm64/include/asm/rmi_cmds.h
index ef53147c1984..4547ce0901a6 100644
--- a/arch/arm64/include/asm/rmi_cmds.h
+++ b/arch/arm64/include/asm/rmi_cmds.h
@@ -505,4 +505,35 @@ static inline int rmi_rtt_unmap_unprotected(unsigned long rd,
 	return res.a0;
 }
 
+static inline unsigned long rmi_pdev_aux_count(unsigned long flags, u64 *aux_count)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_PDEV_AUX_COUNT, flags, &res);
+
+	*aux_count = res.a1;
+	return res.a0;
+}
+
+static inline unsigned long rmi_pdev_create(unsigned long pdev_phys,
+					    unsigned long pdev_params_phys)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_PDEV_CREATE,
+			     pdev_phys, pdev_params_phys, &res);
+
+	return res.a0;
+}
+
+static inline unsigned long rmi_pdev_get_state(unsigned long pdev_phys, enum rmi_pdev_state *state)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_PDEV_GET_STATE, pdev_phys, &res);
+
+	*state = res.a1;
+	return res.a0;
+}
+
 #endif /* __ASM_RMI_CMDS_H */
diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
index fe1c91ffc0ab..10f87a18f09a 100644
--- a/arch/arm64/include/asm/rmi_smc.h
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -26,7 +26,7 @@
 #define SMC_RMI_DATA_CREATE		SMC_RMI_CALL(0x0153)
 #define SMC_RMI_DATA_CREATE_UNKNOWN	SMC_RMI_CALL(0x0154)
 #define SMC_RMI_DATA_DESTROY		SMC_RMI_CALL(0x0155)
-
+#define SMC_RMI_PDEV_AUX_COUNT		SMC_RMI_CALL(0x0156)
 #define SMC_RMI_REALM_ACTIVATE		SMC_RMI_CALL(0x0157)
 #define SMC_RMI_REALM_CREATE		SMC_RMI_CALL(0x0158)
 #define SMC_RMI_REALM_DESTROY		SMC_RMI_CALL(0x0159)
@@ -47,6 +47,9 @@
 #define SMC_RMI_RTT_INIT_RIPAS		SMC_RMI_CALL(0x0168)
 #define SMC_RMI_RTT_SET_RIPAS		SMC_RMI_CALL(0x0169)
 
+#define SMC_RMI_PDEV_CREATE             SMC_RMI_CALL(0x0176)
+#define SMC_RMI_PDEV_GET_STATE		SMC_RMI_CALL(0x0178)
+
 #define RMI_ABI_MAJOR_VERSION	1
 #define RMI_ABI_MINOR_VERSION	0
 
@@ -269,4 +272,93 @@ struct rec_run {
 	struct rec_exit exit;
 };
 
+enum rmi_pdev_state {
+	RMI_PDEV_NEW,
+	RMI_PDEV_NEEDS_KEY,
+	RMI_PDEV_HAS_KEY,
+	RMI_PDEV_READY,
+	RMI_PDEV_IDE_RESETTING,
+	RMI_PDEV_COMMUNICATING,
+	RMI_PDEV_STOPPING,
+	RMI_PDEV_STOPPED,
+	RMI_PDEV_ERROR,
+};
+
+#define MAX_PDEV_AUX_GRANULES	32
+#define MAX_IOCOH_ADDR_RANGE	16
+#define MAX_FCOH_ADDR_RANGE	4
+
+#define RMI_PDEV_FLAGS_SPDM		BIT(0)
+#define RMI_PDEV_FLAGS_NCOH_IDE		BIT(1)
+#define RMI_PDEV_FLAGS_NCOH_ADDR	BIT(2)
+#define RMI_PDEV_FLAGS_COH_IDE		BIT(3)
+#define RMI_PDEV_FLAGS_COH_ADDR		BIT(4)
+#define RMI_PDEV_FLAGS_P2P		BIT(5)
+#define RMI_PDEV_FLAGS_COMP_TRUST	BIT(6)
+#define RMI_PDEV_FLAGS_CATEGORY		GENMASK(8, 7)
+
+#define RMI_PDEV_CMEM_CXL_CATEGORY	BIT(7)
+
+#define RMI_HASH_SHA_256	0
+#define RMI_HASH_SHA_512	1
+
+struct rmi_pdev_addr_range {
+	u64 base;
+	u64 top;
+};
+
+struct rmi_pdev_params {
+	union {
+		struct {
+			u64 flags;
+			u64 pdev_id;
+			union {
+				u8 segment_id;
+				u64 padding0;
+			};
+			u64 ecam_addr;
+			union {
+				u16 root_id;
+				u64 padding1;
+			};
+			u64 cert_id;
+			union {
+				u16 rid_base;
+				u64 padding2;
+			};
+			union {
+				u16 rid_top;
+				u64 padding3;
+			};
+			union {
+				u8 hash_algo;
+				u64 padding4;
+			};
+			u64 num_aux;
+			u64 ncoh_ide_sid;
+			u64 ncoh_num_addr_range;
+			u64 coh_num_addr_range;
+		};
+		u8 padding5[0x100];
+	};
+
+	union { /* 0x100 */
+		u64 aux_granule[MAX_PDEV_AUX_GRANULES];
+		u8 padding6[0x100];
+	};
+
+	union { /* 0x200 */
+		struct {
+			struct rmi_pdev_addr_range ncoh_addr_range[MAX_IOCOH_ADDR_RANGE];
+		};
+		u8 padding7[0x100];
+	};
+	union { /* 0x300 */
+		struct {
+			struct rmi_pdev_addr_range coh_addr_range[MAX_FCOH_ADDR_RANGE];
+		};
+		u8 padding8[0x100];
+	};
+};
+
 #endif /* __ASM_RMI_SMC_H */
diff --git a/drivers/virt/coco/arm-cca-host/Makefile b/drivers/virt/coco/arm-cca-host/Makefile
index ad353b07e95a..a5694a3a7983 100644
--- a/drivers/virt/coco/arm-cca-host/Makefile
+++ b/drivers/virt/coco/arm-cca-host/Makefile
@@ -2,4 +2,4 @@
 #
 obj-$(CONFIG_ARM_CCA_HOST) += arm-cca-host.o
 
-arm-cca-host-$(CONFIG_TSM) +=  arm-cca.o
+arm-cca-host-$(CONFIG_TSM) +=  arm-cca.o rmi-da.o
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.c b/drivers/virt/coco/arm-cca-host/rmi-da.c
new file mode 100644
index 000000000000..390b8f05c7cf
--- /dev/null
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.c
@@ -0,0 +1,141 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/*
+ * Copyright (C) 2025 ARM Ltd.
+ */
+
+#include <linux/pci.h>
+#include <linux/pci-ecam.h>
+#include <asm/rmi_cmds.h>
+
+#include "rmi-da.h"
+
+static int pci_ide_aassoc_register_to_pdev_addr(struct rmi_pdev_addr_range *pdev_addr,
+						unsigned int naddr, struct pci_ide_partner *partner)
+{
+	pdev_addr[0].base = partner->mem_assoc.start;
+	pdev_addr[0].top  = partner->mem_assoc.end + 1;
+	naddr--;
+
+	if (!naddr)
+		return 1;
+
+	pdev_addr[1].base = partner->pref_assoc.start;
+	pdev_addr[1].top  = partner->pref_assoc.end + 1;
+
+	return 2;
+}
+
+static void free_aux_pages(int cnt, void *aux[])
+{
+	int ret;
+
+	while (cnt--) {
+		ret = rmi_granule_undelegate(virt_to_phys(aux[cnt]));
+		if (!ret)
+			free_page((unsigned long)aux[cnt]);
+	}
+}
+
+static int init_pdev_params(struct pci_dev *pdev, struct rmi_pdev_params *params)
+{
+	int rid, ret, i;
+	phys_addr_t aux_phys;
+	struct pci_config_window *cfg = pdev->bus->sysdata;
+	struct cca_host_pf0_dsc *pf0_dsc = to_cca_pf0_dsc(pdev);
+	struct pci_ide *ide = pf0_dsc->sel_stream;
+
+	/* assign the ep device with RMM */
+	rid = pci_dev_id(pdev);
+	params->pdev_id = rid;
+	/* slot number for certificate chain */
+	params->cert_id = 0;
+	/* io coherent spdm/ide and non p2p */
+	params->flags = RMI_PDEV_FLAGS_SPDM | RMI_PDEV_FLAGS_NCOH_IDE |
+			RMI_PDEV_FLAGS_NCOH_ADDR;
+	params->ncoh_ide_sid = ide->stream_id;
+	params->hash_algo = RMI_HASH_SHA_256;
+	/* use the rid and MMIO resources of the end point pdev */
+	params->rid_base = rid;
+	params->rid_top = params->rid_base + 1;
+	params->ecam_addr = cfg->res.start;
+	params->root_id = pci_dev_id(pcie_find_root_port(pdev));
+
+	params->ncoh_num_addr_range = pci_ide_aassoc_register_to_pdev_addr(params->ncoh_addr_range,
+								ARRAY_SIZE(params->ncoh_addr_range),
+								&ide->partner[PCI_IDE_RP]);
+
+	rmi_pdev_aux_count(params->flags, &params->num_aux);
+	pf0_dsc->num_aux = params->num_aux;
+	for (i = 0; i < params->num_aux; i++) {
+		void *aux =  (void *)__get_free_page(GFP_KERNEL);
+
+		if (!aux) {
+			ret = -ENOMEM;
+			goto err_free_aux;
+		}
+
+		aux_phys = virt_to_phys(aux);
+		if (rmi_granule_delegate(aux_phys)) {
+			ret = -ENXIO;
+			free_page((unsigned long)aux);
+			goto err_free_aux;
+		}
+		params->aux_granule[i] = aux_phys;
+		pf0_dsc->aux[i] = aux;
+	}
+	return 0;
+
+err_free_aux:
+	free_aux_pages(i, pf0_dsc->aux);
+	return ret;
+}
+
+int pdev_create(struct pci_dev *pci_dev)
+{
+	int ret;
+	void *rmm_pdev;
+	bool should_free = true;
+	phys_addr_t rmm_pdev_phys;
+	struct rmi_pdev_params *params;
+	struct cca_host_pf0_dsc *pf0_dsc = to_cca_pf0_dsc(pci_dev);
+
+	rmm_pdev = (void *)get_zeroed_page(GFP_KERNEL);
+	if (!rmm_pdev)
+		return -ENOMEM;
+
+	rmm_pdev_phys = virt_to_phys(rmm_pdev);
+	if (rmi_granule_delegate(rmm_pdev_phys)) {
+		ret = -ENXIO;
+		goto err_granule_delegate;
+	}
+
+	params = (struct rmi_pdev_params *)get_zeroed_page(GFP_KERNEL);
+	if (!params) {
+		ret = -ENOMEM;
+		goto err_param_alloc;
+	}
+
+	ret = init_pdev_params(pci_dev, params);
+	if (ret)
+		goto err_init_pdev_params;
+
+	ret = rmi_pdev_create(rmm_pdev_phys, virt_to_phys(params));
+	if (ret)
+		goto err_pdev_create;
+
+	pf0_dsc->rmm_pdev = rmm_pdev;
+	free_page((unsigned long)params);
+	return 0;
+
+err_pdev_create:
+	free_aux_pages(pf0_dsc->num_aux, pf0_dsc->aux);
+err_init_pdev_params:
+	free_page((unsigned long)params);
+err_param_alloc:
+	if (rmi_granule_undelegate(rmm_pdev_phys))
+		should_free = false;
+err_granule_delegate:
+	if (should_free)
+		free_page((unsigned long)rmm_pdev);
+	return ret;
+}
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.h b/drivers/virt/coco/arm-cca-host/rmi-da.h
index 01dfb42cd39e..6764bf8d98ce 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.h
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.h
@@ -15,6 +15,10 @@
 struct cca_host_pf0_dsc {
 	struct pci_tsm_pf0 pci;
 	struct pci_ide *sel_stream;
+
+	void *rmm_pdev;
+	int num_aux;
+	void *aux[MAX_PDEV_AUX_GRANULES];
 };
 
 struct cca_host_fn_dsc {
@@ -38,4 +42,5 @@ static inline struct cca_host_fn_dsc *to_cca_fn_dsc(struct pci_dev *pdev)
 	return container_of(tsm, struct cca_host_fn_dsc, pci);
 }
 
+int pdev_create(struct pci_dev *pdev);
 #endif

---

## [7] Aneesh Kumar K.V (Arm) — 2025-10-27
*Subject: [PATCH RESEND v2 06/12] coco: host: arm64: Add RMM device communication helpers*

- add SMCCC IDs/wrappers for RMI_PDEV_COMMUNICATE/RMI_PDEV_ABORT
- describe the RMM device-communication ABI (struct rmi_dev_comm_*,
  cache flags, protocol/object IDs, busy error code)
- track per-PF0 communication state (buffers, workqueue, cache metadata) and
  serialize access behind object_lock
- plumb a DOE/SPDM worker (pdev_communicate_work) plus shared helpers that
  submit the SMCCC call, cache multi-part responses, and handle retries/abort
- hook the new helpers into the physical function connect path so IDE
  setup can drive the device to the expected state

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rmi_cmds.h        |  20 ++
 arch/arm64/include/asm/rmi_smc.h         |  63 ++++++
 drivers/virt/coco/arm-cca-host/arm-cca.c |  50 +++++
 drivers/virt/coco/arm-cca-host/rmi-da.c  | 273 +++++++++++++++++++++++
 drivers/virt/coco/arm-cca-host/rmi-da.h  |  63 ++++++
 5 files changed, 469 insertions(+)

diff --git a/arch/arm64/include/asm/rmi_cmds.h b/arch/arm64/include/asm/rmi_cmds.h
index 4547ce0901a6..b86bf15afcda 100644
--- a/arch/arm64/include/asm/rmi_cmds.h
+++ b/arch/arm64/include/asm/rmi_cmds.h
@@ -536,4 +536,24 @@ static inline unsigned long rmi_pdev_get_state(unsigned long pdev_phys, enum rmi
 	return res.a0;
 }
 
+static inline unsigned long rmi_pdev_communicate(unsigned long pdev_phys,
+						 unsigned long pdev_comm_data_phys)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_PDEV_COMMUNICATE,
+			     pdev_phys, pdev_comm_data_phys, &res);
+
+	return res.a0;
+}
+
+static inline unsigned long rmi_pdev_abort(unsigned long pdev_phys)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_PDEV_ABORT, pdev_phys, &res);
+
+	return res.a0;
+}
+
 #endif /* __ASM_RMI_CMDS_H */
diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
index 10f87a18f09a..53e46e24c921 100644
--- a/arch/arm64/include/asm/rmi_smc.h
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -47,6 +47,8 @@
 #define SMC_RMI_RTT_INIT_RIPAS		SMC_RMI_CALL(0x0168)
 #define SMC_RMI_RTT_SET_RIPAS		SMC_RMI_CALL(0x0169)
 
+#define SMC_RMI_PDEV_ABORT		SMC_RMI_CALL(0x0174)
+#define SMC_RMI_PDEV_COMMUNICATE        SMC_RMI_CALL(0x0175)
 #define SMC_RMI_PDEV_CREATE             SMC_RMI_CALL(0x0176)
 #define SMC_RMI_PDEV_GET_STATE		SMC_RMI_CALL(0x0178)
 
@@ -69,6 +71,7 @@
 #define RMI_ERROR_REALM		2
 #define RMI_ERROR_REC		3
 #define RMI_ERROR_RTT		4
+#define RMI_BUSY		10
 
 enum rmi_ripas {
 	RMI_EMPTY = 0,
@@ -361,4 +364,64 @@ struct rmi_pdev_params {
 	};
 };
 
+#define RMI_DEV_COMM_EXIT_CACHE_REQ	BIT(0)
+#define RMI_DEV_COMM_EXIT_CACHE_RSP	BIT(1)
+#define RMI_DEV_COMM_EXIT_SEND		BIT(2)
+#define RMI_DEV_COMM_EXIT_WAIT		BIT(3)
+#define RMI_DEV_COMM_EXIT_RSP_RESET	BIT(4)
+#define RMI_DEV_COMM_EXIT_MULTI		BIT(5)
+
+#define RMI_DEV_COMM_NONE	0
+#define RMI_DEV_COMM_RESPONSE	1
+#define RMI_DEV_COMM_ERROR	2
+
+#define RMI_PROTOCOL_SPDM		0
+#define RMI_PROTOCOL_SECURE_SPDM	1
+
+#define RMI_DEV_VCA			0
+#define RMI_DEV_CERTIFICATE		1
+#define RMI_DEV_MEASUREMENTS		2
+#define RMI_DEV_INTERFACE_REPORT	3
+
+struct rmi_dev_comm_enter {
+	union {
+		u8 status;
+		u64 padding0;
+	};
+	u64 req_addr;
+	u64 resp_addr;
+	u64 resp_len;
+};
+
+struct rmi_dev_comm_exit {
+	u64 flags;
+	u64 req_cache_offset;
+	u64 req_cache_len;
+	u64 rsp_cache_offset;
+	u64 rsp_cache_len;
+	union {
+		u8 cache_obj_id;
+		u64 padding0;
+	};
+
+	union {
+		u8 protocol;
+		u64 padding1;
+	};
+	u64 req_delay;
+	u64 req_len;
+	u64 rsp_timeout;
+};
+
+struct rmi_dev_comm_data {
+	union { /* 0x0 */
+		struct rmi_dev_comm_enter enter;
+		u8 padding0[0x800];
+	};
+	union { /* 0x800 */
+		struct rmi_dev_comm_exit exit;
+		u8 padding1[0x800];
+	};
+};
+
 #endif /* __ASM_RMI_SMC_H */
diff --git a/drivers/virt/coco/arm-cca-host/arm-cca.c b/drivers/virt/coco/arm-cca-host/arm-cca.c
index 18e5bf6adea4..e79f05fee516 100644
--- a/drivers/virt/coco/arm-cca-host/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-host/arm-cca.c
@@ -48,6 +48,7 @@ static struct pci_tsm *cca_tsm_pci_probe(struct tsm_dev *tsm_dev, struct pci_dev
 	rc = pci_tsm_pf0_constructor(pdev, &pf0_dsc->pci, tsm_dev);
 	if (rc)
 		return NULL;
+	mutex_init(&pf0_dsc->object_lock);
 
 	pci_dbg(pdev, "tsm enabled\n");
 	return &no_free_ptr(pf0_dsc)->pci.base_tsm;
@@ -70,6 +71,55 @@ static void cca_tsm_pci_remove(struct pci_tsm *tsm)
 	}
 }
 
+static __maybe_unused int init_dev_communication_buffers(struct pci_dev *pdev,
+							 struct cca_host_comm_data *comm_data)
+{
+	int ret = -ENOMEM;
+
+	comm_data->io_params = (struct rmi_dev_comm_data *)get_zeroed_page(GFP_KERNEL);
+	if (!comm_data->io_params)
+		goto err_out;
+
+	comm_data->rsp_buff = (void *)__get_free_page(GFP_KERNEL);
+	if (!comm_data->rsp_buff)
+		goto err_res_buff;
+
+	comm_data->req_buff = (void *)__get_free_page(GFP_KERNEL);
+	if (!comm_data->req_buff)
+		goto err_req_buff;
+
+	comm_data->work_queue = alloc_ordered_workqueue("%s %s DEV_COMM", 0,
+						dev_bus_name(&pdev->dev),
+						pci_name(pdev));
+	if (!comm_data->work_queue)
+		goto err_work_queue;
+
+	comm_data->io_params->enter.status = RMI_DEV_COMM_NONE;
+	comm_data->io_params->enter.resp_addr = virt_to_phys(comm_data->rsp_buff);
+	comm_data->io_params->enter.req_addr  = virt_to_phys(comm_data->req_buff);
+	comm_data->io_params->enter.resp_len = 0;
+
+	return 0;
+
+err_work_queue:
+	free_page((unsigned long)comm_data->req_buff);
+err_req_buff:
+	free_page((unsigned long)comm_data->rsp_buff);
+err_res_buff:
+	free_page((unsigned long)comm_data->io_params);
+err_out:
+	return ret;
+}
+
+static inline void free_dev_communication_buffers(struct cca_host_comm_data *comm_data)
+{
+	destroy_workqueue(comm_data->work_queue);
+
+	free_page((unsigned long)comm_data->req_buff);
+	free_page((unsigned long)comm_data->rsp_buff);
+	free_page((unsigned long)comm_data->io_params);
+}
+
 /* For now global for simplicity. Protected by pci_tsm_rwsem */
 static DECLARE_BITMAP(cca_stream_ids, MAX_STREAM_ID);
 
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.c b/drivers/virt/coco/arm-cca-host/rmi-da.c
index 390b8f05c7cf..592abe0dd252 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.c
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.c
@@ -5,6 +5,8 @@
 
 #include <linux/pci.h>
 #include <linux/pci-ecam.h>
+#include <linux/pci-doe.h>
+#include <linux/delay.h>
 #include <asm/rmi_cmds.h>
 
 #include "rmi-da.h"
@@ -139,3 +141,274 @@ int pdev_create(struct pci_dev *pci_dev)
 		free_page((unsigned long)rmm_pdev);
 	return ret;
 }
+
+static int doe_send_req_resp(struct pci_tsm *tsm)
+{
+	int ret, data_obj_type;
+	struct cca_host_comm_data *comm_data = to_cca_comm_data(tsm->pdev);
+	struct rmi_dev_comm_exit *io_exit = &comm_data->io_params->exit;
+	u8 protocol = io_exit->protocol;
+
+	if (protocol == RMI_PROTOCOL_SPDM)
+		data_obj_type = PCI_DOE_FEATURE_CMA;
+	else if (protocol == RMI_PROTOCOL_SECURE_SPDM)
+		data_obj_type = PCI_DOE_FEATURE_SSESSION;
+	else
+		return -EINVAL;
+
+	/* delay the send */
+	if (io_exit->req_delay)
+		fsleep(io_exit->req_delay);
+
+	ret = pci_tsm_doe_transfer(tsm->dsm_dev, data_obj_type,
+				   comm_data->req_buff, io_exit->req_len,
+				   comm_data->rsp_buff, PAGE_SIZE);
+	return ret;
+}
+
+static inline bool pending_dev_communicate(struct rmi_dev_comm_exit *io_exit)
+{
+	bool pending = io_exit->flags & (RMI_DEV_COMM_EXIT_CACHE_REQ |
+					 RMI_DEV_COMM_EXIT_CACHE_RSP |
+					 RMI_DEV_COMM_EXIT_SEND |
+					 RMI_DEV_COMM_EXIT_WAIT |
+					 RMI_DEV_COMM_EXIT_MULTI);
+	return pending;
+}
+
+static int ___do_dev_communicate(enum dev_comm_type type, struct pci_tsm *tsm)
+{
+	int ret, nbytes, cp_len;
+	struct cache_object **cache_objp, *cache_obj;
+	struct cca_host_pf0_dsc *pf0_dsc = to_cca_pf0_dsc(tsm->dsm_dev);
+	struct cca_host_comm_data *comm_data = to_cca_comm_data(tsm->pdev);
+	struct rmi_dev_comm_enter *io_enter = &comm_data->io_params->enter;
+	struct rmi_dev_comm_exit *io_exit = &comm_data->io_params->exit;
+
+redo_communicate:
+
+	if (type == PDEV_COMMUNICATE)
+		ret = rmi_pdev_communicate(virt_to_phys(pf0_dsc->rmm_pdev),
+					   virt_to_phys(comm_data->io_params));
+	else
+		ret = RMI_ERROR_INPUT;
+	if (ret != RMI_SUCCESS) {
+		if (ret == RMI_BUSY)
+			return -EBUSY;
+		return -ENXIO;
+	}
+
+	if (io_exit->flags & RMI_DEV_COMM_EXIT_CACHE_REQ ||
+	    io_exit->flags & RMI_DEV_COMM_EXIT_CACHE_RSP) {
+
+		switch (io_exit->cache_obj_id) {
+		case RMI_DEV_VCA:
+			cache_objp = &pf0_dsc->vca;
+			break;
+		case RMI_DEV_CERTIFICATE:
+			cache_objp = &pf0_dsc->cert_chain.cache;
+			break;
+		default:
+			return -EINVAL;
+		}
+		cache_obj = *cache_objp;
+	}
+
+	if (io_exit->flags & RMI_DEV_COMM_EXIT_CACHE_REQ)
+		cp_len = io_exit->req_cache_len;
+	else
+		cp_len = io_exit->rsp_cache_len;
+
+	/* response and request len should be <= SZ_4k */
+	if (cp_len > CACHE_CHUNK_SIZE)
+		return -EINVAL;
+
+	if (io_exit->flags & RMI_DEV_COMM_EXIT_CACHE_REQ ||
+	    io_exit->flags & RMI_DEV_COMM_EXIT_CACHE_RSP) {
+		int cache_remaining;
+		struct cache_object *new_obj;
+
+		/* new allocation */
+		if (!cache_obj) {
+			cache_obj = kvmalloc(struct_size(cache_obj, buf, CACHE_CHUNK_SIZE),
+					     GFP_KERNEL);
+			if (!cache_obj)
+				return -ENOMEM;
+
+			cache_obj->size = CACHE_CHUNK_SIZE;
+			cache_obj->offset = 0;
+			*cache_objp = cache_obj;
+		}
+
+		cache_remaining = cache_obj->size - cache_obj->offset;
+		if (cp_len > cache_remaining) {
+
+			if (cache_obj->size + CACHE_CHUNK_SIZE > MAX_CACHE_OBJ_SIZE)
+				return -EINVAL;
+
+			new_obj = kvmalloc(struct_size(cache_obj, buf,
+						       cache_obj->size + CACHE_CHUNK_SIZE),
+					   GFP_KERNEL);
+			if (!new_obj)
+				return -ENOMEM;
+			memcpy(new_obj, cache_obj, struct_size(cache_obj, buf, cache_obj->size));
+			new_obj->size = cache_obj->size + CACHE_CHUNK_SIZE;
+			*cache_objp = new_obj;
+			kvfree(cache_obj);
+		}
+
+		/* cache object can change above. */
+		cache_obj = *cache_objp;
+	}
+
+
+	if (io_exit->flags & RMI_DEV_COMM_EXIT_CACHE_REQ) {
+		memcpy(cache_obj->buf + cache_obj->offset,
+		       (comm_data->req_buff + io_exit->req_cache_offset), io_exit->req_cache_len);
+		cache_obj->offset += io_exit->req_cache_len;
+	}
+
+	if (io_exit->flags & RMI_DEV_COMM_EXIT_CACHE_RSP) {
+		memcpy(cache_obj->buf + cache_obj->offset,
+		       (comm_data->rsp_buff + io_exit->rsp_cache_offset), io_exit->rsp_cache_len);
+		cache_obj->offset += io_exit->rsp_cache_len;
+	}
+
+	/*
+	 * wait for last packet request from RMM.
+	 * We should not find this because our device communication is synchronous
+	 */
+	if (io_exit->flags & RMI_DEV_COMM_EXIT_WAIT)
+		return -ENXIO;
+
+	/* next packet to send */
+	if (io_exit->flags & RMI_DEV_COMM_EXIT_SEND) {
+		nbytes = doe_send_req_resp(tsm);
+		if (nbytes < 0) {
+			/* report error back to RMM */
+			io_enter->status = RMI_DEV_COMM_ERROR;
+		} else {
+			/* send response back to RMM */
+			io_enter->resp_len = nbytes;
+			io_enter->status = RMI_DEV_COMM_RESPONSE;
+		}
+	} else {
+		/* no data transmitted => no data received */
+		io_enter->resp_len = 0;
+		io_enter->status = RMI_DEV_COMM_NONE;
+	}
+
+	if (pending_dev_communicate(io_exit))
+		goto redo_communicate;
+
+	return 0;
+}
+
+static int __do_dev_communicate(enum dev_comm_type type,
+				struct pci_tsm *tsm, unsigned long error_state)
+{
+	int ret;
+	int state;
+	struct rmi_dev_comm_enter *io_enter;
+	struct cca_host_pf0_dsc *pf0_dsc = to_cca_pf0_dsc(tsm->dsm_dev);
+
+	io_enter = &pf0_dsc->comm_data.io_params->enter;
+	io_enter->resp_len = 0;
+	io_enter->status = RMI_DEV_COMM_NONE;
+
+	ret = ___do_dev_communicate(type, tsm);
+	if (ret) {
+		if (type == PDEV_COMMUNICATE)
+			rmi_pdev_abort(virt_to_phys(pf0_dsc->rmm_pdev));
+
+		state = error_state;
+	} else {
+		/*
+		 * Some device communication error will transition the
+		 * device to error state. Report that.
+		 */
+		if (type == PDEV_COMMUNICATE)
+			ret = rmi_pdev_get_state(virt_to_phys(pf0_dsc->rmm_pdev),
+						 (enum rmi_pdev_state *)&state);
+		if (ret)
+			state = error_state;
+	}
+
+	if (state == error_state)
+		pci_err(tsm->pdev, "device communication error\n");
+
+	return state;
+}
+
+static int do_dev_communicate(enum dev_comm_type type, struct pci_tsm *tsm,
+			      unsigned long target_state,
+			      unsigned long error_state)
+{
+	int state;
+
+	do {
+		state = __do_dev_communicate(type, tsm, error_state);
+
+		if (state == target_state || state == error_state)
+			break;
+	} while (1);
+
+	return state;
+}
+
+static int do_pdev_communicate(struct pci_tsm *tsm, enum rmi_pdev_state target_state)
+{
+	return do_dev_communicate(PDEV_COMMUNICATE, tsm, target_state, RMI_PDEV_ERROR);
+}
+
+void pdev_communicate_work(struct work_struct *work)
+{
+	unsigned long state;
+	struct pci_tsm *tsm;
+	struct dev_comm_work *setup_work;
+	struct cca_host_pf0_dsc *pf0_dsc;
+
+	setup_work = container_of(work, struct dev_comm_work, work);
+	tsm = setup_work->tsm;
+	pf0_dsc = to_cca_pf0_dsc(tsm->dsm_dev);
+
+	guard(mutex)(&pf0_dsc->object_lock);
+	state = do_pdev_communicate(tsm, setup_work->target_state);
+	WARN_ON(state != setup_work->target_state);
+
+	complete(&setup_work->complete);
+}
+
+static int submit_pdev_comm_work(struct pci_dev *pdev, int target_state)
+{
+	int ret;
+	enum rmi_pdev_state state;
+	struct dev_comm_work comm_work;
+	struct cca_host_pf0_dsc *pf0_dsc = to_cca_pf0_dsc(pdev);
+	struct cca_host_comm_data *comm_data = to_cca_comm_data(pdev);
+
+	INIT_WORK_ONSTACK(&comm_work.work, pdev_communicate_work);
+	init_completion(&comm_work.complete);
+	comm_work.tsm = pdev->tsm;
+	comm_work.target_state = target_state;
+
+	queue_work(comm_data->work_queue, &comm_work.work);
+
+	wait_for_completion(&comm_work.complete);
+	destroy_work_on_stack(&comm_work.work);
+
+	/* check if we reached target state */
+	ret = rmi_pdev_get_state(virt_to_phys(pf0_dsc->rmm_pdev), &state);
+	if (ret)
+		return ret;
+
+	if (state != target_state)
+		/* no specific error for this */
+		return -1;
+	return 0;
+}
+
+int pdev_ide_setup(struct pci_dev *pdev)
+{
+	return submit_pdev_comm_work(pdev, RMI_PDEV_NEEDS_KEY);
+}
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.h b/drivers/virt/coco/arm-cca-host/rmi-da.h
index 6764bf8d98ce..1d513e0b74d9 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.h
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.h
@@ -9,22 +9,68 @@
 #include <linux/pci.h>
 #include <linux/pci-ide.h>
 #include <linux/pci-tsm.h>
+#include <linux/sizes.h>
 #include <asm/rmi_smc.h>
 
+#define MAX_CACHE_OBJ_SIZE	SZ_16M
+#define CACHE_CHUNK_SIZE	SZ_4K
+struct cache_object {
+	int size;
+	int offset;
+	u8 buf[] __counted_by(size);
+};
+
+struct dev_comm_work {
+	struct pci_tsm *tsm;
+	int target_state;
+	struct work_struct work;
+	struct completion complete;
+};
+
+struct cca_host_comm_data {
+	void *rsp_buff;
+	void *req_buff;
+	struct rmi_dev_comm_data *io_params;
+	/*
+	 * Only one device communication request can be active at
+	 * a time. This limitation comes from using the DOE mailbox
+	 * at the pdev level. Requests such as get_measurements may
+	 * span multiple mailbox messages, which must not be
+	 * interleaved with other SPDM requests.
+	 */
+	struct workqueue_struct *work_queue;
+};
+
 /* dsc = device security context */
 struct cca_host_pf0_dsc {
+	struct cca_host_comm_data comm_data;
 	struct pci_tsm_pf0 pci;
 	struct pci_ide *sel_stream;
 
 	void *rmm_pdev;
 	int num_aux;
 	void *aux[MAX_PDEV_AUX_GRANULES];
+
+	struct mutex object_lock;
+	struct {
+		struct cache_object *cache;
+
+		void *public_key;
+		size_t public_key_size;
+
+		bool valid;
+	} cert_chain;
+	struct cache_object *vca;
 };
 
 struct cca_host_fn_dsc {
 	struct pci_tsm pci;
 };
 
+enum dev_comm_type {
+	PDEV_COMMUNICATE = 0x1,
+};
+
 static inline struct cca_host_pf0_dsc *to_cca_pf0_dsc(struct pci_dev *pdev)
 {
 	struct pci_tsm *tsm = pdev->tsm;
@@ -42,5 +88,22 @@ static inline struct cca_host_fn_dsc *to_cca_fn_dsc(struct pci_dev *pdev)
 	return container_of(tsm, struct cca_host_fn_dsc, pci);
 }
 
+static inline struct cca_host_comm_data *to_cca_comm_data(struct pci_dev *pdev)
+{
+	struct cca_host_pf0_dsc *pf0_dsc;
+
+	pf0_dsc = to_cca_pf0_dsc(pdev);
+	if (pf0_dsc)
+		return &pf0_dsc->comm_data;
+
+	pf0_dsc = to_cca_pf0_dsc(pdev->tsm->dsm_dev);
+	if (pf0_dsc)
+		return &pf0_dsc->comm_data;
+
+	return NULL;
+}
+
 int pdev_create(struct pci_dev *pdev);
+void pdev_communicate_work(struct work_struct *work);
+int pdev_ide_setup(struct pci_dev *pdev);
 #endif

---

## [8] Aneesh Kumar K.V (Arm) — 2025-10-27
*Subject: [PATCH RESEND v2 07/12] coco: host: arm64: Add helper to stop and tear down an RMM pdev*

- describe the RMI_PDEV_STOP/RMI_PDEV_DESTROY SMC IDs and provide
  wrappers in rmi_cmds.h
- implement pdev_stop_and_destroy() so the host driver stops the pdev,
  waits for it to reach RMI_PDEV_STOPPED, destroys it, frees auxiliary
  granules, and drops the delegated page

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rmi_cmds.h       | 18 +++++++++++++++
 arch/arm64/include/asm/rmi_smc.h        |  2 ++
 drivers/virt/coco/arm-cca-host/rmi-da.c | 30 +++++++++++++++++++++++++
 drivers/virt/coco/arm-cca-host/rmi-da.h |  1 +
 4 files changed, 51 insertions(+)

diff --git a/arch/arm64/include/asm/rmi_cmds.h b/arch/arm64/include/asm/rmi_cmds.h
index b86bf15afcda..f10a0dcaa308 100644
--- a/arch/arm64/include/asm/rmi_cmds.h
+++ b/arch/arm64/include/asm/rmi_cmds.h
@@ -556,4 +556,22 @@ static inline unsigned long rmi_pdev_abort(unsigned long pdev_phys)
 	return res.a0;
 }
 
+static inline unsigned long rmi_pdev_stop(unsigned long pdev_phys)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_PDEV_STOP, pdev_phys, &res);
+
+	return res.a0;
+}
+
+static inline unsigned long rmi_pdev_destroy(unsigned long pdev_phys)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_PDEV_DESTROY, pdev_phys, &res);
+
+	return res.a0;
+}
+
 #endif /* __ASM_RMI_CMDS_H */
diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
index 53e46e24c921..6eb6f7e4b77f 100644
--- a/arch/arm64/include/asm/rmi_smc.h
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -50,7 +50,9 @@
 #define SMC_RMI_PDEV_ABORT		SMC_RMI_CALL(0x0174)
 #define SMC_RMI_PDEV_COMMUNICATE        SMC_RMI_CALL(0x0175)
 #define SMC_RMI_PDEV_CREATE             SMC_RMI_CALL(0x0176)
+#define SMC_RMI_PDEV_DESTROY		SMC_RMI_CALL(0x0177)
 #define SMC_RMI_PDEV_GET_STATE		SMC_RMI_CALL(0x0178)
+#define SMC_RMI_PDEV_STOP		SMC_RMI_CALL(0x017c)
 
 #define RMI_ABI_MAJOR_VERSION	1
 #define RMI_ABI_MINOR_VERSION	0
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.c b/drivers/virt/coco/arm-cca-host/rmi-da.c
index 592abe0dd252..644609618a7a 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.c
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.c
@@ -412,3 +412,33 @@ int pdev_ide_setup(struct pci_dev *pdev)
 {
 	return submit_pdev_comm_work(pdev, RMI_PDEV_NEEDS_KEY);
 }
+
+void pdev_stop_and_destroy(struct pci_dev *pdev)
+{
+	unsigned long ret;
+	struct cca_host_pf0_dsc *pf0_dsc = to_cca_pf0_dsc(pdev);
+	phys_addr_t rmm_pdev_phys = virt_to_phys(pf0_dsc->rmm_pdev);
+
+	ret = rmi_pdev_stop(rmm_pdev_phys);
+	if (WARN_ON(ret != RMI_SUCCESS))
+		return;
+
+	submit_pdev_comm_work(pdev, RMI_PDEV_STOPPED);
+
+	ret = rmi_pdev_destroy(rmm_pdev_phys);
+	if (WARN_ON(ret != RMI_SUCCESS))
+		return;
+
+	kfree(pf0_dsc->cert_chain.public_key);
+	kvfree(pf0_dsc->cert_chain.cache);
+	kvfree(pf0_dsc->vca);
+	pf0_dsc->cert_chain.cache = NULL;
+	pf0_dsc->vca = NULL;
+
+	/* Free the aux granules */
+	free_aux_pages(pf0_dsc->num_aux, pf0_dsc->aux);
+	pf0_dsc->num_aux = 0;
+	if (!rmi_granule_undelegate(rmm_pdev_phys))
+		free_page((unsigned long)pf0_dsc->rmm_pdev);
+	pf0_dsc->rmm_pdev = NULL;
+}
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.h b/drivers/virt/coco/arm-cca-host/rmi-da.h
index 1d513e0b74d9..e556ccecc1cb 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.h
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.h
@@ -104,6 +104,7 @@ static inline struct cca_host_comm_data *to_cca_comm_data(struct pci_dev *pdev)
 }
 
 int pdev_create(struct pci_dev *pdev);
+void pdev_stop_and_destroy(struct pci_dev *pdev);
 void pdev_communicate_work(struct work_struct *work);
 int pdev_ide_setup(struct pci_dev *pdev);
 #endif

---

## [9] Aneesh Kumar K.V (Arm) — 2025-10-27
*Subject: [PATCH RESEND v2 08/12] coco: host: arm64: Instantiate RMM pdev during device connect*

An RMM pdev object represents a communication channel between the RMM
and a physical device, for example a PCIe device. With the required
helpers now in place, update the connect callback to create an RMM pdev
object.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 drivers/virt/coco/arm-cca-host/arm-cca.c | 23 +++++++++++++++++++++--
 1 file changed, 21 insertions(+), 2 deletions(-)

diff --git a/drivers/virt/coco/arm-cca-host/arm-cca.c b/drivers/virt/coco/arm-cca-host/arm-cca.c
index e79f05fee516..8eaf8749e59d 100644
--- a/drivers/virt/coco/arm-cca-host/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-host/arm-cca.c
@@ -71,8 +71,8 @@ static void cca_tsm_pci_remove(struct pci_tsm *tsm)
 	}
 }
 
-static __maybe_unused int init_dev_communication_buffers(struct pci_dev *pdev,
-							 struct cca_host_comm_data *comm_data)
+static int init_dev_communication_buffers(struct pci_dev *pdev,
+					  struct cca_host_comm_data *comm_data)
 {
 	int ret = -ENOMEM;
 
@@ -160,6 +160,16 @@ static int cca_tsm_connect(struct pci_dev *pdev)
 	if (rc)
 		goto err_tsm;
 
+	rc = init_dev_communication_buffers(pdev, &pf0_dsc->comm_data);
+	if (rc)
+		goto err_comm_buff;
+	rc = pdev_create(pdev);
+	if (rc)
+		goto err_pdev_create;
+
+	rc = pdev_ide_setup(pdev);
+	if (rc)
+		goto err_ide_setup;
 	/*
 	 * Once ide is setup, enable the stream at the endpoint
 	 * Root port will be done by RMM
@@ -167,6 +177,12 @@ static int cca_tsm_connect(struct pci_dev *pdev)
 	pci_ide_stream_enable(pdev, ide);
 	return 0;
 
+err_ide_setup:
+	pdev_stop_and_destroy(pdev);
+err_pdev_create:
+	free_dev_communication_buffers(&pf0_dsc->comm_data);
+err_comm_buff:
+	tsm_ide_stream_unregister(ide);
 err_tsm:
 	pci_ide_stream_teardown(rp, ide);
 	pci_ide_stream_teardown(pdev, ide);
@@ -193,6 +209,9 @@ static void cca_tsm_disconnect(struct pci_dev *pdev)
 	stream_id = ide->stream_id;
 	pf0_dsc->sel_stream = NULL;
 
+	pdev_stop_and_destroy(pdev);
+	free_dev_communication_buffers(&pf0_dsc->comm_data);
+
 	pci_ide_stream_release(ide);
 	clear_bit(stream_id, cca_stream_ids);
 }

---

## [10] Aneesh Kumar K.V (Arm) — 2025-10-27
*Subject: [PATCH RESEND v2 09/12] X.509: Make certificate parser public*

From: Lukas Wunner <lukas@wunner.de>

The upcoming support for PCI device authentication with CMA-SPDM
(PCIe r6.1 sec 6.31) requires validating the Subject Alternative Name
in X.509 certificates.

High-level functions for X.509 parsing such as key_create_or_update()
throw away the internal, low-level struct x509_certificate after
extracting the struct public_key and public_key_signature from it.
The Subject Alternative Name is thus inaccessible when using those
functions.

Afford CMA-SPDM access to the Subject Alternative Name by making struct
x509_certificate public, together with the functions for parsing an
X.509 certificate into such a struct and freeing such a struct.

The private header file x509_parser.h previously included <linux/time.h>
for the definition of time64_t.  That definition was since moved to
<linux/time64.h> by commit 361a3bf00582 ("time64: Add time64.h header
and define struct timespec64"), so adjust the #include directive as part
of the move to the new public header file <keys/x509-parser.h>.

No functional change intended.

Signed-off-by: Lukas Wunner <lukas@wunner.de>
Reviewed-by: Dan Williams <dan.j.williams@intel.com>
Reviewed-by: Ilpo Järvinen <ilpo.jarvinen@linux.intel.com>
Reviewed-by: Jonathan Cameron <Jonathan.Cameron@huawei.com>
---
 crypto/asymmetric_keys/x509_parser.h | 40 +--------------------
 include/keys/x509-parser.h           | 53 ++++++++++++++++++++++++++++
 2 files changed, 54 insertions(+), 39 deletions(-)
 create mode 100644 include/keys/x509-parser.h

diff --git a/crypto/asymmetric_keys/x509_parser.h b/crypto/asymmetric_keys/x509_parser.h
index 0688c222806b..39f1521b773d 100644
--- a/crypto/asymmetric_keys/x509_parser.h
+++ b/crypto/asymmetric_keys/x509_parser.h
@@ -5,49 +5,11 @@
  * Written by David Howells (dhowells@redhat.com)
  */
 
-#include <linux/cleanup.h>
-#include <linux/time.h>
-#include <crypto/public_key.h>
-#include <keys/asymmetric-type.h>
-
-struct x509_certificate {
-	struct x509_certificate *next;
-	struct x509_certificate *signer;	/* Certificate that signed this one */
-	struct public_key *pub;			/* Public key details */
-	struct public_key_signature *sig;	/* Signature parameters */
-	char		*issuer;		/* Name of certificate issuer */
-	char		*subject;		/* Name of certificate subject */
-	struct asymmetric_key_id *id;		/* Issuer + Serial number */
-	struct asymmetric_key_id *skid;		/* Subject + subjectKeyId (optional) */
-	time64_t	valid_from;
-	time64_t	valid_to;
-	const void	*tbs;			/* Signed data */
-	unsigned	tbs_size;		/* Size of signed data */
-	unsigned	raw_sig_size;		/* Size of signature */
-	const void	*raw_sig;		/* Signature data */
-	const void	*raw_serial;		/* Raw serial number in ASN.1 */
-	unsigned	raw_serial_size;
-	unsigned	raw_issuer_size;
-	const void	*raw_issuer;		/* Raw issuer name in ASN.1 */
-	const void	*raw_subject;		/* Raw subject name in ASN.1 */
-	unsigned	raw_subject_size;
-	unsigned	raw_skid_size;
-	const void	*raw_skid;		/* Raw subjectKeyId in ASN.1 */
-	unsigned	index;
-	bool		seen;			/* Infinite recursion prevention */
-	bool		verified;
-	bool		self_signed;		/* T if self-signed (check unsupported_sig too) */
-	bool		unsupported_sig;	/* T if signature uses unsupported crypto */
-	bool		blacklisted;
-};
+#include <keys/x509-parser.h>
 
 /*
  * x509_cert_parser.c
  */
-extern void x509_free_certificate(struct x509_certificate *cert);
-DEFINE_FREE(x509_free_certificate, struct x509_certificate *,
-	    if (!IS_ERR(_T)) x509_free_certificate(_T))
-extern struct x509_certificate *x509_cert_parse(const void *data, size_t datalen);
 extern int x509_decode_time(time64_t *_t,  size_t hdrlen,
 			    unsigned char tag,
 			    const unsigned char *value, size_t vlen);
diff --git a/include/keys/x509-parser.h b/include/keys/x509-parser.h
new file mode 100644
index 000000000000..37436a5c7526
--- /dev/null
+++ b/include/keys/x509-parser.h
@@ -0,0 +1,53 @@
+/* SPDX-License-Identifier: GPL-2.0-or-later */
+/* X.509 certificate parser
+ *
+ * Copyright (C) 2012 Red Hat, Inc. All Rights Reserved.
+ * Written by David Howells (dhowells@redhat.com)
+ */
+
+#ifndef _KEYS_X509_PARSER_H
+#define _KEYS_X509_PARSER_H
+
+#include <crypto/public_key.h>
+#include <keys/asymmetric-type.h>
+#include <linux/cleanup.h>
+#include <linux/time64.h>
+
+struct x509_certificate {
+	struct x509_certificate *next;
+	struct x509_certificate *signer;	/* Certificate that signed this one */
+	struct public_key *pub;			/* Public key details */
+	struct public_key_signature *sig;	/* Signature parameters */
+	char		*issuer;		/* Name of certificate issuer */
+	char		*subject;		/* Name of certificate subject */
+	struct asymmetric_key_id *id;		/* Issuer + Serial number */
+	struct asymmetric_key_id *skid;		/* Subject + subjectKeyId (optional) */
+	time64_t	valid_from;
+	time64_t	valid_to;
+	const void	*tbs;			/* Signed data */
+	unsigned	tbs_size;		/* Size of signed data */
+	unsigned	raw_sig_size;		/* Size of signature */
+	const void	*raw_sig;		/* Signature data */
+	const void	*raw_serial;		/* Raw serial number in ASN.1 */
+	unsigned	raw_serial_size;
+	unsigned	raw_issuer_size;
+	const void	*raw_issuer;		/* Raw issuer name in ASN.1 */
+	const void	*raw_subject;		/* Raw subject name in ASN.1 */
+	unsigned	raw_subject_size;
+	unsigned	raw_skid_size;
+	const void	*raw_skid;		/* Raw subjectKeyId in ASN.1 */
+	unsigned	index;
+	bool		seen;			/* Infinite recursion prevention */
+	bool		verified;
+	bool		self_signed;		/* T if self-signed (check unsupported_sig too) */
+	bool		unsupported_sig;	/* T if signature uses unsupported crypto */
+	bool		blacklisted;
+};
+
+struct x509_certificate *x509_cert_parse(const void *data, size_t datalen);
+void x509_free_certificate(struct x509_certificate *cert);
+
+DEFINE_FREE(x509_free_certificate, struct x509_certificate *,
+	    if (!IS_ERR(_T)) x509_free_certificate(_T))
+
+#endif /* _KEYS_X509_PARSER_H */

---

## [11] Aneesh Kumar K.V (Arm) — 2025-10-27
*Subject: [PATCH RESEND v2 10/12] X.509: Parse Subject Alternative Name in certificates*

From: Lukas Wunner <lukas@wunner.de>

The upcoming support for PCI device authentication with CMA-SPDM
(PCIe r6.1 sec 6.31) requires validating the Subject Alternative Name
in X.509 certificates.

Store a pointer to the Subject Alternative Name upon parsing for
consumption by CMA-SPDM.

Signed-off-by: Lukas Wunner <lukas@wunner.de>
Reviewed-by: Wilfred Mallawa <wilfred.mallawa@wdc.com>
Reviewed-by: Ilpo Järvinen <ilpo.jarvinen@linux.intel.com>
Reviewed-by: Jonathan Cameron <Jonathan.Cameron@huawei.com>
Acked-by: Dan Williams <dan.j.williams@intel.com>
---
 crypto/asymmetric_keys/x509_cert_parser.c | 9 +++++++++
 include/keys/x509-parser.h                | 2 ++
 2 files changed, 11 insertions(+)

diff --git a/crypto/asymmetric_keys/x509_cert_parser.c b/crypto/asymmetric_keys/x509_cert_parser.c
index 8df3fa60a44f..5942679f125a 100644
--- a/crypto/asymmetric_keys/x509_cert_parser.c
+++ b/crypto/asymmetric_keys/x509_cert_parser.c
@@ -571,6 +571,15 @@ int x509_process_extension(void *context, size_t hdrlen,
 		return 0;
 	}
 
+	if (ctx->last_oid == OID_subjectAltName) {
+		if (ctx->cert->raw_san)
+			return -EBADMSG;
+
+		ctx->cert->raw_san = v;
+		ctx->cert->raw_san_size = vlen;
+		return 0;
+	}
+
 	if (ctx->last_oid == OID_keyUsage) {
 		/*
 		 * Get hold of the keyUsage bit string
diff --git a/include/keys/x509-parser.h b/include/keys/x509-parser.h
index 37436a5c7526..8e450befe3b9 100644
--- a/include/keys/x509-parser.h
+++ b/include/keys/x509-parser.h
@@ -36,6 +36,8 @@ struct x509_certificate {
 	unsigned	raw_subject_size;
 	unsigned	raw_skid_size;
 	const void	*raw_skid;		/* Raw subjectKeyId in ASN.1 */
+	const void	*raw_san;		/* Raw subjectAltName in ASN.1 */
+	unsigned	raw_san_size;
 	unsigned	index;
 	bool		seen;			/* Infinite recursion prevention */
 	bool		verified;

---

## [12] Aneesh Kumar K.V (Arm) — 2025-10-27
*Subject: [PATCH RESEND v2 11/12] X.509: Move certificate length retrieval into new helper*

From: Lukas Wunner <lukas@wunner.de>

The upcoming in-kernel SPDM library (Security Protocol and Data Model,
https://www.dmtf.org/dsp/DSP0274) needs to retrieve the length from
ASN.1 DER-encoded X.509 certificates.

Such code already exists in x509_load_certificate_list(), so move it
into a new helper for reuse by SPDM.

Export the helper so that SPDM can be tristate.  (Some upcoming users of
the SPDM libray may be modular, such as SCSI and ATA.)

No functional change intended.

Signed-off-by: Lukas Wunner <lukas@wunner.de>
Reviewed-by: Dan Williams <dan.j.williams@intel.com>
Reviewed-by: Jonathan Cameron <Jonathan.Cameron@huawei.com>
---
 crypto/asymmetric_keys/x509_loader.c | 38 +++++++++++++++++++---------
 include/keys/asymmetric-type.h       |  2 ++
 2 files changed, 28 insertions(+), 12 deletions(-)

diff --git a/crypto/asymmetric_keys/x509_loader.c b/crypto/asymmetric_keys/x509_loader.c
index a41741326998..25ff027fad1d 100644
--- a/crypto/asymmetric_keys/x509_loader.c
+++ b/crypto/asymmetric_keys/x509_loader.c
@@ -4,28 +4,42 @@
 #include <linux/key.h>
 #include <keys/asymmetric-type.h>
 
+ssize_t x509_get_certificate_length(const u8 *p, unsigned long buflen)
+{
+	ssize_t plen;
+
+	/* Each cert begins with an ASN.1 SEQUENCE tag and must be more
+	 * than 256 bytes in size.
+	 */
+	if (buflen < 4)
+		return -EINVAL;
+
+	if (p[0] != 0x30 &&
+	    p[1] != 0x82)
+		return -EINVAL;
+
+	plen = (p[2] << 8) | p[3];
+	plen += 4;
+	if (plen > buflen)
+		return -EINVAL;
+
+	return plen;
+}
+EXPORT_SYMBOL_GPL(x509_get_certificate_length);
+
 int x509_load_certificate_list(const u8 cert_list[],
 			       const unsigned long list_size,
 			       const struct key *keyring)
 {
 	key_ref_t key;
 	const u8 *p, *end;
-	size_t plen;
+	ssize_t plen;
 
 	p = cert_list;
 	end = p + list_size;
 	while (p < end) {
-		/* Each cert begins with an ASN.1 SEQUENCE tag and must be more
-		 * than 256 bytes in size.
-		 */
-		if (end - p < 4)
-			goto dodgy_cert;
-		if (p[0] != 0x30 &&
-		    p[1] != 0x82)
-			goto dodgy_cert;
-		plen = (p[2] << 8) | p[3];
-		plen += 4;
-		if (plen > end - p)
+		plen = x509_get_certificate_length(p, end - p);
+		if (plen < 0)
 			goto dodgy_cert;
 
 		key = key_create_or_update(make_key_ref(keyring, 1),
diff --git a/include/keys/asymmetric-type.h b/include/keys/asymmetric-type.h
index 69a13e1e5b2e..e2af07fec3c6 100644
--- a/include/keys/asymmetric-type.h
+++ b/include/keys/asymmetric-type.h
@@ -84,6 +84,8 @@ extern struct key *find_asymmetric_key(struct key *keyring,
 				       const struct asymmetric_key_id *id_2,
 				       bool partial);
 
+ssize_t x509_get_certificate_length(const u8 *p, unsigned long buflen);
+
 int x509_load_certificate_list(const u8 cert_list[], const unsigned long list_size,
 			       const struct key *keyring);

---

## [13] Aneesh Kumar K.V (Arm) — 2025-10-27
*Subject: [PATCH RESEND v2 12/12] coco: host: arm64: Register device public key with RMM*

- Introduce the SMC_RMI_PDEV_SET_PUBKEY helper and the associated struct
rmi_public_key_params so the host can hand the device’s public key to
the RMM.

- Parse the certificate chain cached during IDE setup, extract the final
certificate’s public key, and recognise RSA-3072, ECDSA-P256, and
ECDSA-P384 keys before calling into the RMM.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rmi_cmds.h       |   9 ++
 arch/arm64/include/asm/rmi_smc.h        |  18 +++
 drivers/virt/coco/arm-cca-host/Kconfig  |   4 +
 drivers/virt/coco/arm-cca-host/rmi-da.c | 166 +++++++++++++++++++++++-
 drivers/virt/coco/arm-cca-host/rmi-da.h |   1 +
 5 files changed, 197 insertions(+), 1 deletion(-)

diff --git a/arch/arm64/include/asm/rmi_cmds.h b/arch/arm64/include/asm/rmi_cmds.h
index f10a0dcaa308..339bea517760 100644
--- a/arch/arm64/include/asm/rmi_cmds.h
+++ b/arch/arm64/include/asm/rmi_cmds.h
@@ -574,4 +574,13 @@ static inline unsigned long rmi_pdev_destroy(unsigned long pdev_phys)
 	return res.a0;
 }
 
+static inline unsigned long rmi_pdev_set_pubkey(unsigned long pdev_phys, unsigned long key_phys)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_PDEV_SET_PUBKEY, pdev_phys, key_phys, &res);
+
+	return res.a0;
+}
+
 #endif /* __ASM_RMI_CMDS_H */
diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
index 6eb6f7e4b77f..1f46e13b92a4 100644
--- a/arch/arm64/include/asm/rmi_smc.h
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -52,6 +52,7 @@
 #define SMC_RMI_PDEV_CREATE             SMC_RMI_CALL(0x0176)
 #define SMC_RMI_PDEV_DESTROY		SMC_RMI_CALL(0x0177)
 #define SMC_RMI_PDEV_GET_STATE		SMC_RMI_CALL(0x0178)
+#define SMC_RMI_PDEV_SET_PUBKEY		SMC_RMI_CALL(0x017b)
 #define SMC_RMI_PDEV_STOP		SMC_RMI_CALL(0x017c)
 
 #define RMI_ABI_MAJOR_VERSION	1
@@ -426,4 +427,21 @@ struct rmi_dev_comm_data {
 	};
 };
 
+#define RMI_SIG_RSASSA_3072	0
+#define RMI_SIG_ECDSA_P256	1
+#define RMI_SIG_ECDSA_P384	2
+
+struct rmi_public_key_params {
+	union {
+		struct {
+			u8 public_key[1024];
+			u8 metadata[1024];
+			u64 public_key_len;
+			u64 metadata_len;
+			u8 rmi_signature_algorithm;
+		} __packed;
+		u8 padding[0x1000];
+	};
+};
+
 #endif /* __ASM_RMI_SMC_H */
diff --git a/drivers/virt/coco/arm-cca-host/Kconfig b/drivers/virt/coco/arm-cca-host/Kconfig
index 1febd316fb77..efa66e960ad5 100644
--- a/drivers/virt/coco/arm-cca-host/Kconfig
+++ b/drivers/virt/coco/arm-cca-host/Kconfig
@@ -7,8 +7,12 @@ config ARM_CCA_HOST
 	depends on ARM64
 	depends on PCI_TSM
 	depends on KVM
+	select KEYS
+	select X509_CERTIFICATE_PARSER
 	select TSM
 	select AUXILIARY_BUS
+	select CRYPTO_ECDSA
+	select CRYPTO_RSA
 
 	help
 	  ARM CCA RMM firmware is the trusted runtime that enforces memory
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.c b/drivers/virt/coco/arm-cca-host/rmi-da.c
index 644609618a7a..c9780ca64c17 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.c
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.c
@@ -8,6 +8,9 @@
 #include <linux/pci-doe.h>
 #include <linux/delay.h>
 #include <asm/rmi_cmds.h>
+#include <crypto/internal/rsa.h>
+#include <keys/asymmetric-type.h>
+#include <keys/x509-parser.h>
 
 #include "rmi-da.h"
 
@@ -361,6 +364,146 @@ static int do_pdev_communicate(struct pci_tsm *tsm, enum rmi_pdev_state target_s
 	return do_dev_communicate(PDEV_COMMUNICATE, tsm, target_state, RMI_PDEV_ERROR);
 }
 
+static int parse_certificate_chain(struct pci_tsm *tsm)
+{
+	struct cca_host_pf0_dsc *pf0_dsc;
+	unsigned int chain_size;
+	unsigned int offset = 0;
+	u8 *chain_data;
+
+	pf0_dsc = to_cca_pf0_dsc(tsm->pdev);
+
+	/* If device communication didn't results in certificate caching. */
+	if (!pf0_dsc->cert_chain.cache || !pf0_dsc->cert_chain.cache->offset)
+		return -EINVAL;
+
+	chain_size = pf0_dsc->cert_chain.cache->offset;
+	chain_data = pf0_dsc->cert_chain.cache->buf;
+
+	while (offset < chain_size) {
+		ssize_t cert_len =
+			x509_get_certificate_length(chain_data + offset,
+						    chain_size - offset);
+		if (cert_len < 0)
+			return cert_len;
+
+		struct x509_certificate *cert __free(x509_free_certificate) =
+			x509_cert_parse(chain_data + offset, cert_len);
+
+		if (IS_ERR(cert)) {
+			pci_warn(tsm->pdev, "parsing of certificate chain not successful\n");
+			return PTR_ERR(cert);
+		}
+
+		/* The key in the last cert in the chain is used */
+		if (offset + cert_len == chain_size) {
+			pf0_dsc->cert_chain.public_key = kzalloc(cert->pub->keylen, GFP_KERNEL);
+			if (!pf0_dsc->cert_chain.public_key)
+				return -ENOMEM;
+
+			if (!strcmp("ecdsa-nist-p256", cert->pub->pkey_algo)) {
+				pf0_dsc->rmi_signature_algorithm = RMI_SIG_ECDSA_P256;
+			} else if (!strcmp("ecdsa-nist-p384", cert->pub->pkey_algo)) {
+				pf0_dsc->rmi_signature_algorithm = RMI_SIG_ECDSA_P384;
+			} else if (!strcmp("rsa", cert->pub->pkey_algo)) {
+				pf0_dsc->rmi_signature_algorithm = RMI_SIG_RSASSA_3072;
+			} else {
+				kfree(pf0_dsc->cert_chain.public_key);
+				pf0_dsc->cert_chain.public_key = NULL;
+				return -ENXIO;
+			}
+			memcpy(pf0_dsc->cert_chain.public_key, cert->pub->key, cert->pub->keylen);
+			pf0_dsc->cert_chain.public_key_size = cert->pub->keylen;
+		}
+
+		offset += cert_len;
+	}
+
+	pf0_dsc->cert_chain.valid = true;
+	return 0;
+}
+
+DEFINE_FREE(free_page, unsigned long, if (_T) free_page(_T))
+static int pdev_set_public_key(struct pci_tsm *tsm)
+{
+	unsigned long expected_key_len;
+	struct cca_host_pf0_dsc *pf0_dsc;
+	int ret;
+
+	pf0_dsc = to_cca_pf0_dsc(tsm->pdev);
+	/* Check that all the necessary information was captured from communication */
+	if (!pf0_dsc->cert_chain.valid)
+		return -EINVAL;
+
+	struct rmi_public_key_params *key_params __free(free_page) =
+		(struct rmi_public_key_params *)get_zeroed_page(GFP_KERNEL);
+	if (!key_params)
+		return -ENOMEM;
+
+	key_params->rmi_signature_algorithm = pf0_dsc->rmi_signature_algorithm;
+
+	switch (key_params->rmi_signature_algorithm) {
+	case RMI_SIG_ECDSA_P384:
+	{
+		expected_key_len = 97;
+
+		if (pf0_dsc->cert_chain.public_key_size != expected_key_len)
+			return -EINVAL;
+
+		key_params->public_key_len = pf0_dsc->cert_chain.public_key_size;
+		memcpy(key_params->public_key,
+		       pf0_dsc->cert_chain.public_key,
+		       pf0_dsc->cert_chain.public_key_size);
+		key_params->metadata_len = 0;
+		break;
+	}
+	case RMI_SIG_ECDSA_P256:
+	{
+		expected_key_len = 65;
+
+		if (pf0_dsc->cert_chain.public_key_size != expected_key_len)
+			return -EINVAL;
+
+		key_params->public_key_len = pf0_dsc->cert_chain.public_key_size;
+		memcpy(key_params->public_key,
+		       pf0_dsc->cert_chain.public_key,
+		       pf0_dsc->cert_chain.public_key_size);
+		key_params->metadata_len = 0;
+		break;
+	}
+	case RMI_SIG_RSASSA_3072:
+	{
+		struct rsa_key rsa_key = {0};
+
+		expected_key_len = 385;
+		int ret_rsa_parse = rsa_parse_pub_key(&rsa_key,
+						      pf0_dsc->cert_chain.public_key,
+						      pf0_dsc->cert_chain.public_key_size);
+		/* This also checks the key_len */
+		if (ret_rsa_parse)
+			return ret_rsa_parse;
+		/*
+		 * exponent is usually 65537 (size = 24bits) but in rare cases
+		 * the size can be as large as the modulus
+		 */
+		if (rsa_key.e_sz > expected_key_len)
+			return -EINVAL;
+
+		key_params->public_key_len = rsa_key.n_sz;
+		key_params->metadata_len = rsa_key.e_sz;
+		memcpy(key_params->public_key, rsa_key.n, rsa_key.n_sz);
+		memcpy(key_params->metadata, rsa_key.e, rsa_key.e_sz);
+		break;
+	}
+	default:
+		return -EINVAL;
+	}
+
+	ret = rmi_pdev_set_pubkey(virt_to_phys(pf0_dsc->rmm_pdev),
+				  virt_to_phys(key_params));
+	return ret;
+}
+
 void pdev_communicate_work(struct work_struct *work)
 {
 	unsigned long state;
@@ -410,7 +553,28 @@ static int submit_pdev_comm_work(struct pci_dev *pdev, int target_state)
 
 int pdev_ide_setup(struct pci_dev *pdev)
 {
-	return submit_pdev_comm_work(pdev, RMI_PDEV_NEEDS_KEY);
+	int ret;
+
+	ret = submit_pdev_comm_work(pdev, RMI_PDEV_NEEDS_KEY);
+	if (ret)
+		return ret;
+	/*
+	 * we now have certificate chain in dsm->cert_chain. Parse
+	 * that and set the pubkey.
+	 */
+	ret = parse_certificate_chain(pdev->tsm);
+	if (ret)
+		return ret;
+
+	ret = pdev_set_public_key(pdev->tsm);
+	if (ret)
+		return ret;
+
+	ret = submit_pdev_comm_work(pdev, RMI_PDEV_READY);
+	if (ret)
+		return ret;
+
+	return 0;
 }
 
 void pdev_stop_and_destroy(struct pci_dev *pdev)
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.h b/drivers/virt/coco/arm-cca-host/rmi-da.h
index e556ccecc1cb..f1a840b6d4fb 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.h
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.h
@@ -51,6 +51,7 @@ struct cca_host_pf0_dsc {
 	int num_aux;
 	void *aux[MAX_PDEV_AUX_GRANULES];
 
+	uint8_t rmi_signature_algorithm;
 	struct mutex object_lock;
 	struct {
 		struct cache_object *cache;

---

## [14] Jonathan Cameron — 2025-10-29
*Subject: Re: [PATCH RESEND v2 01/12] KVM: arm64: RMI: Export
 kvm_has_da_feature*

On Mon, 27 Oct 2025 15:25:51 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

Hi Aneesh,

Great to see this support - this review might be a little superficial as
I think it's first time I've looked at this and I'll be getting my head around
it whilst reviewing.

Small process thing:
Always include a stand alone description in here.  Some git clients
don't put the patch title near the commit text. Add something like

Export kvm_has_da_feature() for use in later patches.

> This will be used in later patches
Patch title made me think this was exporting something that already existed.
Probably better to say  Add kvm_has_da_feature() helper for use in later patches
or something like that.

> 
> Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>

Guess you want to be updating Reserved as seems bit 42 isn't any more.

>  
>  #define RMI_REALM_PARAM_FLAG_LPA2		BIT(0)

---

## [15] Jonathan Cameron — 2025-10-29
*Subject: Re: [PATCH RESEND v2 02/12] firmware: smccc: coco: Manage arm-smccc
 platform device and CCA auxiliary drivers*

On Mon, 27 Oct 2025 15:25:52 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> Make the SMCCC driver responsible for registering the arm-smccc platform
> device and after confirming the relevant SMCCC function IDs, create

> diff --git a/drivers/firmware/smccc/Kconfig b/drivers/firmware/smccc/Kconfig
> index 15e7466179a6..2b6984757241 100644

I'm not keen on seeing ifdefs in a file where it isn't already local style.
This is probably better done with a second c file, appropriate header
and Kconfig / Makefile magic to control whether it is built.

> +static void __init register_rsi_device(struct platform_device *pdev)
> +{
Better to have error case out of line.
	if (ret != RSI_SUCCESS)
		return;

	__devm_auxiliary_device_create(

It's both more natural for reviewers of the code and makes it easier to stick
other things after this code later if that makes sense.

> +		__devm_auxiliary_device_create(&pdev->dev,
> +					"arm_cca_guest", RSI_DEV_NAME, NULL, 0);

> diff --git a/drivers/virt/coco/arm-cca-guest/arm-cca-guest.c b/drivers/virt/coco/arm-cca-guest/arm-cca.c
> similarity index 85%


> +static int cca_devsec_tsm_probe(struct auxiliary_device *adev,
> +				const struct auxiliary_device_id *id)

We have a device, so maybe flip to dev_err() or better yet

		return dev_err_probe(&adev->dev, ret, "Error registering with TSM\n");

That's convenient to use in a probe() even if the deferral bits are relevant and
it prints a nice string for the ret.

> +		return ret;
> +	}

 return dev_err_probe() here as well.


> +		return ret;

---

## [16] Jonathan Cameron — 2025-10-29
*Subject: Re: [PATCH RESEND v2 03/12] coco: guest: arm64: Drop dummy RSI
 platform device stub*

On Mon, 27 Oct 2025 15:25:53 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> The SMCCC firmware driver now creates the `arm-smccc` platform device
> and also creates the CCA auxiliary devices once the RSI ABI is
Fair enough keeping it separate for now I guess.
Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>

(and I see from that thread I did look at the RFC but clearly forgot all
 about it :( )
> ---
>  arch/arm64/kernel/rsi.c | 15 ---------------

---

## [17] Jonathan Cameron — 2025-10-29
*Subject: Re: [PATCH RESEND v2 04/12] coco: host: arm64: Add host TSM
 callback and IDE stream allocation support*

On Mon, 27 Oct 2025 15:25:54 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> Register the TSM callback when the DA feature is supported by KVM.
> 
Minor stuff inline.

> diff --git a/drivers/firmware/smccc/smccc.c b/drivers/firmware/smccc/smccc.c
> index 3dbf0d067cc5..9cabe750533c 100644

Same comment as before applies. I'd split this to a separate c file and stub
in a header.

> diff --git a/drivers/virt/coco/arm-cca-host/arm-cca.c b/drivers/virt/coco/arm-cca-host/arm-cca.c
> new file mode 100644

Not sure why this indent. I'd go with more consistent choice of just one tab.

	struct cca_host_pf0_dsc *pf0_dsc __free(kfree) =
		kzalloc(sizeof(*pf0_dsc), GFP_KERNEL);

> +	if (!pf0_dsc)
> +		return NULL;
Maybe something else come in in later patches, but for now this return
is unnecessary.
		kfree(to_cca_fn_dsc(pdev));
doesn't loose much if anything wrt to readability.

> +	}
> +}
as below, I'd have
	pf0_dsc->sel_stream = NULL;
here

> +	pci_ide_stream_free(ide);
> +err_stream_alloc:
You go through this dance to unset these in disconnect but
not if we get a failure in connect.  Whilst it might be fine
it looks a little odd so I'd clear pf0_dsc->sel_stream in the
error path of connect.

> +
> +	pci_ide_stream_release(ide);
This helper is a bit irritating as the clearly of pf0_dsc->sel_stream,
if it were in precise opposite of the connect path would occur mid way
through that function.  Ah well, looks safe enough to be out of order
just trickier to review.

> +	clear_bit(stream_id, cca_stream_ids);
> +}

> +static int cca_link_tsm_probe(struct auxiliary_device *adev,
> +			      const struct auxiliary_device_id *id)
Unless you expect to see something else after this, I'd flip logic

	struct tsm_dev *tsm_dev;

	if (!kvm_has_da_feature())
		return -ENODEV;

	tsm_dev = tsm_register(&adev->dev, &cca_link_pci_ops);
	if (IS_ERR(tsm_dev))
		return PTR_ERR(tsm_dev);

	return devm_add_action_or_reset(&adev->dev, cca_link_tsm_remove,
					tsm_dev);

Here reduces indent and keeps that 'error path' out of line property
that really helps me at least visually parse code.

> +		struct tsm_dev *tsm_dev;
> +

---

## [18] Jason Gunthorpe — 2025-10-29
*Subject: Re: [PATCH RESEND v2 12/12] coco: host: arm64: Register device
 public key with RMM*

On Mon, Oct 27, 2025 at 03:26:02PM +0530, Aneesh Kumar K.V (Arm) wrote:

> +DEFINE_FREE(free_page, unsigned long, if (_T) free_page(_T))

Please put these sorts of things in their proper headers

Jason

---

## [19] Jonathan Cameron — 2025-10-29
*Subject: Re: [PATCH RESEND v2 05/12] coco: host: arm64: Build and register
 RMM pdev descriptors*

On Mon, 27 Oct 2025 15:25:55 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> Add the SMCCC plumbing for RMI_PDEV_AUX_COUNT, RMI_PDEV_CREATE, and
> RMI_PDEV_GET_STATE, describe the pdev state enum/flags in rmi_smc.h,
Hi Aneesh

A few things inline.

J
> ---
>  arch/arm64/include/asm/rmi_cmds.h       |  31 ++++++

> diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
> index fe1c91ffc0ab..10f87a18f09a 100644

I'd avoid the white space change. If it makes sense push it to the KVM series
that I guess this was introduced in.

> +#define SMC_RMI_PDEV_AUX_COUNT		SMC_RMI_CALL(0x0156)

>  #define RMI_ABI_MAJOR_VERSION	1
>  #define RMI_ABI_MINOR_VERSION	0

> +
> +#define MAX_PDEV_AUX_GRANULES	32

This smells like it's the value 1 in the RMI_PDEV_FLAGS_CATEGORY field?
If so don't use a bit definition like this. Instead a suitably named field value definition.
e.g. #define RMI_PDEV_FLAGS_CATEGORY_CXL 1


> diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.c b/drivers/virt/coco/arm-cca-host/rmi-da.c
> new file mode 100644

> +
> +static int init_pdev_params(struct pci_dev *pdev, struct rmi_pdev_params *params)
I'd format as:
	params->ncoh_num_addr_range =
		pci_ide_aassoc_register_to_pdev_addr(params->ncoh_addr_range,
						     ARRAY_SIZE(params->ncoh_addr_range),
						     &ide->partner[PCI_IDE_RP]);

> +
> +	rmi_pdev_aux_count(params->flags, &params->num_aux);
One space only before cast.

> +
> +		if (!aux) {

> diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.h b/drivers/virt/coco/arm-cca-host/rmi-da.h
> index 01dfb42cd39e..6764bf8d98ce 100644

>  struct cca_host_fn_dsc {
> @@ -38,4 +42,5 @@ static inline struct cca_host_fn_dsc *to_cca_fn_dsc(struct pci_dev *pdev)
That is a very generic name to find in a header, even one buried deep in drivers.
I'd prefix it with somethin more specific rmi_pdev_create() or something like that.

>  #endif

---

## [20] Jonathan Cameron — 2025-10-29
*Subject: Re: [PATCH RESEND v2 06/12] coco: host: arm64: Add RMM device
 communication helpers*

On Mon, 27 Oct 2025 15:25:56 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> - add SMCCC IDs/wrappers for RMI_PDEV_COMMUNICATE/RMI_PDEV_ABORT
> - describe the RMM device-communication ABI (struct rmi_dev_comm_*,

Hi Aneesh,

Comments inline.

> diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.c b/drivers/virt/coco/arm-cca-host/rmi-da.c
> index 390b8f05c7cf..592abe0dd252 100644

> +
> +static int doe_send_req_resp(struct pci_tsm *tsm)

	return pci_tsm_doe_transfer()

> +}
> +

Treat this separately for simpler code (assuming you don't have other code that
makes this more complex in later patches).

	if (type != PDEV_COMMUNICATE)
		return -ENXIO;

	ret = rmi_pdev_communicate(virt_to_phys(pf0_dsc->rmm_pdev),
				   virt_to_phys(comm_data->io_params));
	if (ret != RMI...

> +	if (ret != RMI_SUCCESS) {
> +		if (ret == RMI_BUSY)

Is kvrealloc()? Would avoid need for explicit memcpy / freeing of old object.

> +			if (!new_obj)
> +				return -ENOMEM;

Think up a more meaningful name.  Counting _ doesn't make for readable code.

> +	if (ret) {
> +		if (type == PDEV_COMMUNICATE)
Whilst not strictly needed I'd do this as:

		if (type == PDEV_COMMUNICATE) {
			ret = rmi_pdev_get_state(virt_to_phys(pf0_dsc->rmm_pdev),
						 (enum rmi_pdev_state *)&state);
			if (ret)
				state = error_state;
		}

Just to make it clear that reg check is just on the output of the call above.
If we didn't make that call it is definitely zero but nice not to have
to reason about it.


> +	}
> +

Might as well return rather than break;

> +	} while (1);
> +

> +void pdev_communicate_work(struct work_struct *work)
> +{
Could combine these 3 with declarations for shorter code without much
change to readability.

> +
> +	guard(mutex)(&pf0_dsc->object_lock);


> diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.h b/drivers/virt/coco/arm-cca-host/rmi-da.h
> index 6764bf8d98ce..1d513e0b74d9 100644

> +struct cca_host_comm_data {
> +	void *rsp_buff;

wrap comments to 80 chars. This is around 70ish

> +	 * a time. This limitation comes from using the DOE mailbox
> +	 * at the pdev level. Requests such as get_measurements may

There are a enough slightly non obvious things in here like
this vca that I think this structure would benefit from full kernel-doc.

>  };

---

## [21] Jonathan Cameron — 2025-10-29
*Subject: Re: [PATCH RESEND v2 07/12] coco: host: arm64: Add helper to stop
 and tear down an RMM pdev*

On Mon, 27 Oct 2025 15:25:57 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

Repeat the main bit of the title here.

> - describe the RMI_PDEV_STOP/RMI_PDEV_DESTROY SMC IDs and provide
>   wrappers in rmi_cmds.h
Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>

---

## [22] Jonathan Cameron — 2025-10-29
*Subject: Re: [PATCH RESEND v2 08/12] coco: host: arm64: Instantiate RMM pdev
 during device connect*

On Mon, 27 Oct 2025 15:25:58 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> An RMM pdev object represents a communication channel between the RMM
> and a physical device, for example a PCIe device. With the required
Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>

---

## [23] Jonathan Cameron — 2025-10-29
*Subject: Re: [PATCH RESEND v2 12/12] coco: host: arm64: Register device
 public key with RMM*

On Mon, 27 Oct 2025 15:26:02 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> - Introduce the SMC_RMI_PDEV_SET_PUBKEY helper and the associated struct
> rmi_public_key_params so the host can hand the device’s public key to

Various comments inline.

Overall this patch set seems to be coming together nicely to me.

Jonathan

> diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.c b/drivers/virt/coco/arm-cca-host/rmi-da.c
> index 644609618a7a..c9780ca64c17 100644
I'd use a local variable for this + __free(kfree)
Then assign with no_free_ptr()
> +			if (!pf0_dsc->cert_chain.public_key)
> +				return -ENOMEM;
Set it only when succeeded (local variable until then). 
> +				return -ENXIO;
> +			}
I think at this point we know we are at end of cert chain?  Break would make that obvious.

> +		}
> +

Fully agree with Jason on this one. If it make sense
belongs in appropriate header.
I'm a bit bothered by types though as the parameter is IIRC an unsigned long.

Might need some wrappers to deal with casting.  To me feels likely
to be controversial so pitch it separately from this series.

If you want a define free here create a local helper function tightly
scoped to the type you use it for below.

Or just wrap up the guts of the code in a helper function and
unconditionally free it the old fashioned way.


> +static int pdev_set_public_key(struct pci_tsm *tsm)
> +{
That feels like it should be a define somewhere.
> +
> +		if (pf0_dsc->cert_chain.public_key_size != expected_key_len)
Same with this constant.

> +
> +		if (pf0_dsc->cert_chain.public_key_size != expected_key_len)
And this one ;)
> +		int ret_rsa_parse = rsa_parse_pub_key(&rsa_key,
> +						      pf0_dsc->cert_chain.public_key,
Don't mix declarations and code except for cleanup.h stuff.

> +		/* This also checks the key_len */
> +		if (ret_rsa_parse)

return rmi_pdev_set_pubkey();

> +}
> +

Wrap at 80 chars. This is a bit short.

> +	 * that and set the pubkey.
> +	 */

	return submit_pdev_comm_work(...)

>  }

---

## [24] Aneesh Kumar K.V — 2025-10-30
*Subject: Re: [PATCH RESEND v2 05/12] coco: host: arm64: Build and register
 RMM pdev descriptors*

Jonathan Cameron <jonathan.cameron@huawei.com> writes:

> On Mon, 27 Oct 2025 15:25:55 +0530
> "Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

...

>>  
>> +int pdev_create(struct pci_dev *pdev);

May be I can call this cca_pdev_create, because rmi_pdev_create()
already exist.

-aneesh

---

## [25] Aneesh Kumar K.V — 2025-10-30
*Subject: Re: [PATCH RESEND v2 06/12] coco: host: arm64: Add RMM device
 communication helpers*

Jonathan Cameron <jonathan.cameron@huawei.com> writes:
...

>> +		/*
>> +		 * Some device communication error will transition the

Some of this is because follow up patch adds more details there. In this case.

		/*
		 * Some device communication error will transition the
		 * device to error state. Report that.
		 */
		if (type == PDEV_COMMUNICATE)
			ret = rmi_pdev_get_state(virt_to_phys(pf0_dsc->rmm_pdev),
						 (enum rmi_pdev_state *)&state);
		else
			ret = rmi_vdev_get_state(virt_to_phys(host_tdi->rmm_vdev),
						 (enum rmi_vdev_state *)&state);
		if (ret)
			state = error_state;



>
>> +	}

-aneesh

---

## [26] Jonathan Cameron — 2025-10-30
*Subject: Re: [PATCH RESEND v2 05/12] coco: host: arm64: Build and register
 RMM pdev descriptors*

On Thu, 30 Oct 2025 14:14:43 +0530
Aneesh Kumar K.V <aneesh.kumar@kernel.org> wrote:

> Jonathan Cameron <jonathan.cameron@huawei.com> writes:
> 
Sure. Anything reasonable is fine for this.

J
> 
> -aneesh

---

## [27] Jonathan Cameron — 2025-10-30
*Subject: Re: [PATCH RESEND v2 06/12] coco: host: arm64: Add RMM device
 communication helpers*

On Thu, 30 Oct 2025 14:48:20 +0530
Aneesh Kumar K.V <aneesh.kumar@kernel.org> wrote:

> Jonathan Cameron <jonathan.cameron@huawei.com> writes:
> ...
Ah fair enough I missed that.

J
> 
>

---

## [28] Aneesh Kumar K.V — 2025-10-30
*Subject: Re: [PATCH RESEND v2 06/12] coco: host: arm64: Add RMM device
 communication helpers*

Jonathan Cameron <jonathan.cameron@huawei.com> writes:

> On Mon, 27 Oct 2025 15:25:56 +0530
> "Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

...

>> +void pdev_communicate_work(struct work_struct *work)
>> +{

Not sure about this.

 static void pdev_communicate_work(struct work_struct *work)
 {
 	unsigned long state;
-	struct pci_tsm *tsm;
-	struct dev_comm_work *setup_work;
-	struct cca_host_pf0_dsc *pf0_dsc;
-
-	setup_work = container_of(work, struct dev_comm_work, work);
-	tsm = setup_work->tsm;
-	pf0_dsc = to_cca_pf0_dsc(tsm->dsm_dev);
+	struct dev_comm_work *setup_work = container_of(work,
+							struct dev_comm_work,
+							work);
+	struct pci_tsm *tsm = setup_work->tsm;
+	struct cca_host_pf0_dsc *pf0_dsc = to_cca_pf0_dsc(tsm->dsm_dev);
 
 	guard(mutex)(&pf0_dsc->object_lock);
 	state = do_pdev_communicate(tsm, setup_work->target_state);

>> +
>> +	guard(mutex)(&pf0_dsc->object_lock);

-aneesh

---

## [29] Aneesh Kumar K.V — 2025-10-30
*Subject: Re: [PATCH RESEND v2 06/12] coco: host: arm64: Add RMM device
 communication helpers*

Jonathan Cameron <jonathan.cameron@huawei.com> writes:

> On Mon, 27 Oct 2025 15:25:56 +0530
> "Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

...

>> +static int __do_dev_communicate(enum dev_comm_type type,
>> +				struct pci_tsm *tsm, unsigned long error_state)

I am not sure about this. What do you think?

modified   drivers/virt/coco/arm-cca-host/rmi-da.c
@@ -188,7 +188,7 @@ static inline gfp_t cache_obj_id_to_gfp_flags(u8 cache_obj_id)
 	return GFP_KERNEL_ACCOUNT;
 }
 
-static int ___do_dev_communicate(enum dev_comm_type type, struct pci_tsm *tsm)
+static int __do_dev_communicate(enum dev_comm_type type, struct pci_tsm *tsm)
 {
 	gfp_t cache_alloc_flags;
 	int ret, nbytes, cp_len;
@@ -319,7 +319,7 @@ static int ___do_dev_communicate(enum dev_comm_type type, struct pci_tsm *tsm)
 	return 0;
 }
 
-static int __do_dev_communicate(enum dev_comm_type type,
+static int do_dev_communicate(enum dev_comm_type type,
 				struct pci_tsm *tsm, unsigned long error_state)
 {
 	int ret;
@@ -331,7 +331,7 @@ static int __do_dev_communicate(enum dev_comm_type type,
 	io_enter->resp_len = 0;
 	io_enter->status = RMI_DEV_COMM_NONE;
 
-	ret = ___do_dev_communicate(type, tsm);
+	ret = __do_dev_communicate(type, tsm);
 	if (ret) {
 		if (type == PDEV_COMMUNICATE)
 			rmi_pdev_abort(virt_to_phys(pf0_dsc->rmm_pdev));
@@ -355,14 +355,14 @@ static int __do_dev_communicate(enum dev_comm_type type,
 	return state;
 }
 
-static int do_dev_communicate(enum dev_comm_type type, struct pci_tsm *tsm,
-			      unsigned long target_state,
-			      unsigned long error_state)
+static int move_dev_to_state(enum dev_comm_type type, struct pci_tsm *tsm,
+			     unsigned long target_state,
+			     unsigned long error_state)
 {
 	int state;
 
 	do {
-		state = __do_dev_communicate(type, tsm, error_state);
+		state = do_dev_communicate(type, tsm, error_state);
 
 		if (state == target_state || state == error_state)
 			return state;
@@ -374,7 +374,7 @@ static int do_dev_communicate(enum dev_comm_type type, struct pci_tsm *tsm,
 
 static int do_pdev_communicate(struct pci_tsm *tsm, enum rmi_pdev_state target_state)
 {
-	return do_dev_communicate(PDEV_COMMUNICATE, tsm, target_state, RMI_PDEV_ERROR);
+	return move_dev_to_state(PDEV_COMMUNICATE, tsm, target_state, RMI_PDEV_ERROR);
 }
 
 static int parse_certificate_chain(struct pci_tsm *tsm)




-aneesh

---

## [30] Jonathan Cameron — 2025-10-30
*Subject: Re: [PATCH RESEND v2 06/12] coco: host: arm64: Add RMM device
 communication helpers*

On Thu, 30 Oct 2025 19:34:51 +0530
"Aneesh Kumar K.V" <aneesh.kumar@kernel.org> wrote:

> Jonathan Cameron <jonathan.cameron@huawei.com> writes:
> 
I'd wrap it a bit differently.  

	struct dev_comm_work *setup_work =
		container_of(work, struct dev_comm_work, work);
	struct pci_tsm *tsm = setup_work->tsm;
	struct cca_host_pf0_dsc *pf0_dsc = to_cca_pf0_dsc(tsm->dsm_dev);

Entirely up to you. Hence the could part of the comment.

Jonathan

---

## [31] Jonathan Cameron — 2025-10-30
*Subject: Re: [PATCH RESEND v2 06/12] coco: host: arm64: Add RMM device
 communication helpers*

On Thu, 30 Oct 2025 21:50:22 +0530
"Aneesh Kumar K.V" <aneesh.kumar@kernel.org> wrote:

> Jonathan Cameron <jonathan.cameron@huawei.com> writes:
> 

Naming is always tricky.  Not sure why this name is appropriate given it's definitely
still related to dev_communicate.

Maybe just squash do_dev_communicate and __do_dev_coummnicate.
Slightly long lines will be the result but not too bad.
I haven't checked what it ends up as after the whole series though
so maybe it doesn't work out.

static int do_dev_communicate(enum dev_comm_type type, struct pci_tsm *tsm,
			      unsigned long target_state,
			      unsigned long error_state)
{
	

	do {
		int state, ret;
		struct rmi_dev_comm_enter *io_enter;
		struct cca_host_pf0_dsc *pf0_dsc = to_cca_pf0_dsc(tsm->dsm_dev);

		io_enter = &pf0_dsc->comm_data.io_params->enter;
		io_enter->resp_len = 0;
		io_enter->status = RMI_DEV_COMM_NONE;

		ret = ___do_dev_communicate(type, tsm);
//renamed

		if (ret) {
			if (type == PDEV_COMMUNICATE)
				rmi_pdev_abort(virt_to_phys(pf0_dsc->rmm_pdev));

			state = error_state;
		} else {
			/*
			 * Some device communication error will transition the
			 * device to error state. Report that.
			 */
			if (type == PDEV_COMMUNICATE)
				ret = rmi_pdev_get_state(virt_to_phys(pf0_dsc->rmm_pdev),
							 (enum rmi_pdev_state *)&state);
			if (ret)
				state = error_state;
		}
	
		if (state == error_state) {
			pci_err(tsm->pdev, "device communication error\n");
			return state;
		}
		if (state == target_state)
			return state;
	} while (1);
}
Jonathan

> +			     unsigned long target_state,
> +			     unsigned long error_state)

---

## [32] Aneesh Kumar K.V — 2025-10-31
*Subject: Re: [PATCH RESEND v2 06/12] coco: host: arm64: Add RMM device
 communication helpers*

Jonathan Cameron <jonathan.cameron@huawei.com> writes:

> On Thu, 30 Oct 2025 21:50:22 +0530
> "Aneesh Kumar K.V" <aneesh.kumar@kernel.org> wrote:

I need the existing __do_dev_communicate for a followup patch where the
device communication won't loop till state transition.

Something like 

void vdev_fetch_object_work(struct work_struct *work)
{
	int state;
	struct pci_tsm *tsm;
	struct cca_host_pf0_dsc *pf0_dsc;
	struct dev_comm_work *setup_work;
	struct rmi_dev_comm_enter *io_enter;

	setup_work = container_of(work, struct dev_comm_work, work);
	tsm = setup_work->tsm;
	pf0_dsc = to_cca_pf0_dsc(tsm->dsm_dev);

	io_enter = &pf0_dsc->comm_data.io_params->enter;
	io_enter->resp_len = 0;
	io_enter->status = RMI_DEV_COMM_NONE;

	guard(mutex)(&pf0_dsc->object_lock);

	*setup_work->cache_offset = 0;
	memset(setup_work->cache_buf, 0, setup_work->cache_size);
	state = __do_dev_communicate(VDEV_COMMUNICATE, tsm, RMI_VDEV_ERROR);
	/* return status through dev_comm_work.cache_cache */
	if (state == RMI_VDEV_ERROR)
		setup_work->cache_size = 0;

	complete(&setup_work->complete);
}

Considering current usage is loop till we reach a specific target state,
how abou the below?

modified   drivers/virt/coco/arm-cca-host/rmi-da.c
@@ -188,7 +188,7 @@ static inline gfp_t cache_obj_id_to_gfp_flags(u8 cache_obj_id)
 	return GFP_KERNEL_ACCOUNT;
 }
 
-static int ___do_dev_communicate(enum dev_comm_type type, struct pci_tsm *tsm)
+static int _do_dev_communicate(enum dev_comm_type type, struct pci_tsm *tsm)
 {
 	gfp_t cache_alloc_flags;
 	int ret, nbytes, cp_len;
@@ -319,7 +319,7 @@ static int ___do_dev_communicate(enum dev_comm_type type, struct pci_tsm *tsm)
 	return 0;
 }
 
-static int __do_dev_communicate(enum dev_comm_type type,
+static int do_dev_communicate(enum dev_comm_type type,
 				struct pci_tsm *tsm, unsigned long error_state)
 {
 	int ret;
@@ -331,7 +331,7 @@ static int __do_dev_communicate(enum dev_comm_type type,
 	io_enter->resp_len = 0;
 	io_enter->status = RMI_DEV_COMM_NONE;
 
-	ret = ___do_dev_communicate(type, tsm);
+	ret = _do_dev_communicate(type, tsm);
 	if (ret) {
 		if (type == PDEV_COMMUNICATE)
 			rmi_pdev_abort(virt_to_phys(pf0_dsc->rmm_pdev));
@@ -355,14 +355,14 @@ static int __do_dev_communicate(enum dev_comm_type type,
 	return state;
 }
 
-static int do_dev_communicate(enum dev_comm_type type, struct pci_tsm *tsm,
+static int wait_for_dev_state(enum dev_comm_type type, struct pci_tsm *tsm,
 			      unsigned long target_state,
 			      unsigned long error_state)
 {
 	int state;
 
 	do {
-		state = __do_dev_communicate(type, tsm, error_state);
+		state = do_dev_communicate(type, tsm, error_state);
 
 		if (state == target_state || state == error_state)
 			return state;
@@ -372,9 +372,9 @@ static int do_dev_communicate(enum dev_comm_type type, struct pci_tsm *tsm,
 	return error_state;
 }
 
-static int do_pdev_communicate(struct pci_tsm *tsm, enum rmi_pdev_state target_state)
+static int wait_for_pdev_state(struct pci_tsm *tsm, enum rmi_pdev_state target_state)
 {
-	return do_dev_communicate(PDEV_COMMUNICATE, tsm, target_state, RMI_PDEV_ERROR);
+	return wait_for_dev_state(PDEV_COMMUNICATE, tsm, target_state, RMI_PDEV_ERROR);
 }
 
 static int parse_certificate_chain(struct pci_tsm *tsm)
@@ -497,7 +497,7 @@ static int pdev_set_public_key(struct pci_tsm *tsm)
 				   virt_to_phys(key_params));
 }
 
-static void pdev_communicate_work(struct work_struct *work)
+static void pdev_state_transition_workfn(struct work_struct *work)
 {
 	unsigned long state;
 	struct pci_tsm *tsm;
@@ -509,13 +509,13 @@ static void pdev_communicate_work(struct work_struct *work)
 	pf0_dsc = to_cca_pf0_dsc(tsm->dsm_dev);
 
 	guard(mutex)(&pf0_dsc->object_lock);
-	state = do_pdev_communicate(tsm, setup_work->target_state);
+	state = wait_for_pdev_state(tsm, setup_work->target_state);
 	WARN_ON(state != setup_work->target_state);
 
 	complete(&setup_work->complete);
 }
 
-static int submit_pdev_comm_work(struct pci_dev *pdev, int target_state)
+static int submit_pdev_state_transition_work(struct pci_dev *pdev, int target_state)
 {
 	int ret;
 	enum rmi_pdev_state state;
@@ -523,7 +523,7 @@ static int submit_pdev_comm_work(struct pci_dev *pdev, int target_state)
 	struct cca_host_pf0_dsc *pf0_dsc = to_cca_pf0_dsc(pdev);
 	struct cca_host_comm_data *comm_data = to_cca_comm_data(pdev);
 
-	INIT_WORK_ONSTACK(&comm_work.work, pdev_communicate_work);
+	INIT_WORK_ONSTACK(&comm_work.work, pdev_state_transition_workfn);
 	init_completion(&comm_work.complete);
 	comm_work.tsm = pdev->tsm;
 	comm_work.target_state = target_state;
@@ -548,7 +548,7 @@ int cca_pdev_ide_setup(struct pci_dev *pdev)
 {
 	int ret;
 
-	ret = submit_pdev_comm_work(pdev, RMI_PDEV_NEEDS_KEY);
+	ret = submit_pdev_state_transition_work(pdev, RMI_PDEV_NEEDS_KEY);
 	if (ret)
 		return ret;
 	/*
@@ -563,7 +563,7 @@ int cca_pdev_ide_setup(struct pci_dev *pdev)
 	if (ret)
 		return ret;
 
-	return submit_pdev_comm_work(pdev, RMI_PDEV_READY);
+	return submit_pdev_state_transition_work(pdev, RMI_PDEV_READY);
 }
 
 void cca_pdev_stop_and_destroy(struct pci_dev *pdev)
@@ -576,7 +576,7 @@ void cca_pdev_stop_and_destroy(struct pci_dev *pdev)
 	if (WARN_ON(ret != RMI_SUCCESS))
 		return;
 
-	submit_pdev_comm_work(pdev, RMI_PDEV_STOPPED);
+	submit_pdev_state_transition_work(pdev, RMI_PDEV_STOPPED);
 
 	ret = rmi_pdev_destroy(rmm_pdev_phys);
 	if (WARN_ON(ret != RMI_SUCCESS))




-aneesh

---

## [33] Jonathan Cameron — 2025-10-31
*Subject: Re: [PATCH RESEND v2 06/12] coco: host: arm64: Add RMM device
 communication helpers*

On Fri, 31 Oct 2025 13:34:33 +0530
"Aneesh Kumar K.V" <aneesh.kumar@kernel.org> wrote:

> Jonathan Cameron <jonathan.cameron@huawei.com> writes:
> 

Ah. I'd missed that. Fair enough.


> -static int __do_dev_communicate(enum dev_comm_type type,
> +static int do_dev_communicate(enum dev_comm_type type,
This name conveys what the wrapper adds to the inner call but neglects that inner bit.

do_dev_communicate_and_wait_for_xxx or
do_dev_communicate_synchronous()  // maybe - it's approximately a synchronous wrapper of async operation.
Or something along those lines perhaps?


>  			      unsigned long target_state,
>  			      unsigned long error_state)

---

## [34] Aneesh Kumar K.V — 2026-01-06
*Subject: Re: [PATCH RESEND v2 02/12] firmware: smccc: coco: Manage arm-smccc
 platform device and CCA auxiliary drivers*

Hi Mark,

"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> writes:

> Make the SMCCC driver responsible for registering the arm-smccc platform
> device and after confirming the relevant SMCCC function IDs, create

Just a gentle ping on this patch — any feedback would be much appreciated.

-aneesh

---
