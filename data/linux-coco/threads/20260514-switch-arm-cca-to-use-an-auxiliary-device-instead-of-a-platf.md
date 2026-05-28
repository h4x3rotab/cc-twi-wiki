---
title: 'Switch Arm CCA to use an auxiliary device instead of a platform device'
date: 2026-05-14
last_reply: 2026-05-20
message_count: 22
participants: ['Aneesh Kumar K.V (Arm)', 'Greg KH', 'Suzuki K Poulose', 'Sudeep Holla', 'Catalin Marinas']
---

## [1] Aneesh Kumar K.V (Arm) — 2026-05-14

As discussed here:
https://lore.kernel.org/all/20250728135216.48084-12-aneesh.kumar@kernel.org

The general feedback was that a platform device should not be used when
there is no underlying platform resource to represent. The existing CCA
support uses a platform device solely to anchor the TSM interface in the
device hierarchy, which is not an appropriate use of a platform device.
Use an auxiliary device instead to track CCA support.

The TSM framework uses the device abstraction to provide cross-architecture
TSM and TEE I/O functionality, including enumerating available platform TEE
I/O capabilities and provisioning connections between the platform TSM and
device DSMs.

For the CCA platform, the resulting device hierarchy appears as follows.
Note that the auxiliary device is still parented by the arm-smccc platform
device, so the sysfs path remains under /devices/platform/arm-smccc/:

$ cd /sys/class/tsm/
$ ls -al
total 0
drwxr-xr-x    2 root     root             0 Jan  1 00:02 .
drwxr-xr-x   23 root     root             0 Jan  1 00:00 ..
lrwxrwxrwx    1 root     root             0 Jan  1 00:03 tsm0 -> ../../devices/platform/arm-smccc/arm_cca_guest.arm-rsi-dev.0/tsm/tsm0
$

Changes from v4:
https://lore.kernel.org/all/20260427061615.905018-1-aneesh.kumar@kernel.org
* Add /sys/firmware/cca/realm_guest for detecting realm guest
* Convert smccc-trng to auxiliary device from platform device

Changes from v3:
https://lore.kernel.org/all/20260309100507.2303361-1-aneesh.kumar@kernel.org
* Rebased onto the latest kernel
* Drop pr_fmt() from drivers/firmware/smccc/rmm.c

Cc: Catalin Marinas <catalin.marinas@arm.com>
Cc: Greg KH <gregkh@linuxfoundation.org>
Cc: Jeremy Linton <jeremy.linton@arm.com>
Cc: Jonathan Cameron <jic23@kernel.org>
Cc: Lorenzo Pieralisi <lpieralisi@kernel.org>
Cc: Mark Rutland <mark.rutland@arm.com>
Cc: Sudeep Holla <sudeep.holla@arm.com>
Cc: Will Deacon <will@kernel.org>
Cc: Steven Price <steven.price@arm.com>
Cc: Suzuki K Poulose <Suzuki.Poulose@arm.com>

Aneesh Kumar K.V (Arm) (3):
  firmware: smccc: coco: Manage arm-smccc platform device and CCA
    auxiliary drivers
  hwrng: arm_smccc_trng: Register as an auxiliary device
  coco: guest: arm64: Replace dummy CCA device with sysfs ABI

 Documentation/ABI/testing/sysfs-firmware-cca  | 10 ++++
 arch/arm64/include/asm/rsi.h                  |  2 +-
 arch/arm64/kernel/rsi.c                       | 39 ++++++++----
 drivers/char/hw_random/arm_smccc_trng.c       | 25 ++++----
 drivers/firmware/smccc/Kconfig                |  1 +
 drivers/firmware/smccc/Makefile               |  1 +
 drivers/firmware/smccc/rmm.c                  | 24 ++++++++
 drivers/firmware/smccc/rmm.h                  | 17 ++++++
 drivers/firmware/smccc/smccc.c                | 29 +++++++--
 drivers/virt/coco/arm-cca-guest/Kconfig       |  1 +
 drivers/virt/coco/arm-cca-guest/Makefile      |  2 +
 .../{arm-cca-guest.c => arm-cca.c}            | 59 +++++++++----------
 12 files changed, 153 insertions(+), 57 deletions(-)
 create mode 100644 Documentation/ABI/testing/sysfs-firmware-cca
 create mode 100644 drivers/firmware/smccc/rmm.c
 create mode 100644 drivers/firmware/smccc/rmm.h
 rename drivers/virt/coco/arm-cca-guest/{arm-cca-guest.c => arm-cca.c} (84%)

---

## [2] Aneesh Kumar K.V (Arm) — 2026-05-14
*Subject: [PATCH v5 1/3] firmware: smccc: coco: Manage arm-smccc platform device and CCA auxiliary drivers*

Make the SMCCC driver responsible for registering the arm-smccc platform
device and after confirming the relevant SMCCC function IDs, create
the arm_cca_guest auxiliary device.

Also update the arm-cca-guest driver to use the auxiliary device
interface instead of the platform device (arm-cca-dev). The removal of
the platform device registration will follow in a subsequent patch,
allowing this change to be applied without immediately breaking existing
userspace dependencies [1].

[1] https://lore.kernel.org/all/4a7d84b2-2ec4-4773-a2d5-7b63d5c683cf@arm.com

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rsi.h                  |  2 +-
 arch/arm64/kernel/rsi.c                       |  2 +-
 drivers/firmware/smccc/Kconfig                |  1 +
 drivers/firmware/smccc/Makefile               |  1 +
 drivers/firmware/smccc/rmm.c                  | 24 ++++++++
 drivers/firmware/smccc/rmm.h                  | 17 ++++++
 drivers/firmware/smccc/smccc.c                | 17 ++++++
 drivers/virt/coco/arm-cca-guest/Kconfig       |  1 +
 drivers/virt/coco/arm-cca-guest/Makefile      |  2 +
 .../{arm-cca-guest.c => arm-cca.c}            | 59 +++++++++----------
 10 files changed, 94 insertions(+), 32 deletions(-)
 create mode 100644 drivers/firmware/smccc/rmm.c
 create mode 100644 drivers/firmware/smccc/rmm.h
 rename drivers/virt/coco/arm-cca-guest/{arm-cca-guest.c => arm-cca.c} (84%)

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
index 9e846ce4ef9c..8380e5ba88d2 100644
--- a/arch/arm64/kernel/rsi.c
+++ b/arch/arm64/kernel/rsi.c
@@ -161,7 +161,7 @@ void __init arm64_rsi_init(void)
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
diff --git a/drivers/firmware/smccc/Makefile b/drivers/firmware/smccc/Makefile
index 40d19144a860..146dc3c03c20 100644
--- a/drivers/firmware/smccc/Makefile
+++ b/drivers/firmware/smccc/Makefile
@@ -2,3 +2,4 @@
 #
 obj-$(CONFIG_HAVE_ARM_SMCCC_DISCOVERY)	+= smccc.o kvm_guest.o
 obj-$(CONFIG_ARM_SMCCC_SOC_ID)	+= soc_id.o
+obj-$(CONFIG_ARM64) += rmm.o
diff --git a/drivers/firmware/smccc/rmm.c b/drivers/firmware/smccc/rmm.c
new file mode 100644
index 000000000000..728338cb5a22
--- /dev/null
+++ b/drivers/firmware/smccc/rmm.c
@@ -0,0 +1,24 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/*
+ * Copyright (C) 2026 Arm Limited
+ */
+
+#include <linux/auxiliary_bus.h>
+
+#include "rmm.h"
+
+void __init register_rsi_device(struct platform_device *pdev)
+{
+	unsigned long ret;
+	unsigned long ver_lower, ver_higher;
+
+	if (arm_smccc_1_1_get_conduit() != SMCCC_CONDUIT_SMC)
+		return;
+
+	ret = rsi_request_version(RSI_ABI_VERSION, &ver_lower, &ver_higher);
+	if (ret != RSI_SUCCESS)
+		return;
+
+	__devm_auxiliary_device_create(&pdev->dev,
+				       "arm_cca_guest", RSI_DEV_NAME, NULL, 0);
+}
diff --git a/drivers/firmware/smccc/rmm.h b/drivers/firmware/smccc/rmm.h
new file mode 100644
index 000000000000..a47a650d4f51
--- /dev/null
+++ b/drivers/firmware/smccc/rmm.h
@@ -0,0 +1,17 @@
+/* SPDX-License-Identifier: GPL-2.0 */
+#ifndef _SMCCC_RMM_H
+#define _SMCCC_RMM_H
+
+#include <linux/platform_device.h>
+
+#ifdef CONFIG_ARM64
+#include <asm/rsi_cmds.h>
+void __init register_rsi_device(struct platform_device *pdev);
+#else
+
+static void __init register_rsi_device(struct platform_device *pdev)
+{
+
+}
+#endif
+#endif
diff --git a/drivers/firmware/smccc/smccc.c b/drivers/firmware/smccc/smccc.c
index bdee057db2fd..eb077b9aa6da 100644
--- a/drivers/firmware/smccc/smccc.c
+++ b/drivers/firmware/smccc/smccc.c
@@ -12,6 +12,8 @@
 #include <linux/platform_device.h>
 #include <asm/archrandom.h>
 
+#include "rmm.h"
+
 static u32 smccc_version = ARM_SMCCC_VERSION_1_0;
 static enum arm_smccc_conduit smccc_conduit = SMCCC_CONDUIT_NONE;
 
@@ -85,6 +87,21 @@ static int __init smccc_devices_init(void)
 {
 	struct platform_device *pdev;
 
+	if (smccc_conduit == SMCCC_CONDUIT_NONE)
+		return 0;
+
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
similarity index 84%
rename from drivers/virt/coco/arm-cca-guest/arm-cca-guest.c
rename to drivers/virt/coco/arm-cca-guest/arm-cca.c
index 0c9ea24a200c..7daada072cc0 100644
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
+		const struct auxiliary_device_id *id)
 {
 	int ret;
 
 	if (!is_realm_world())
 		return -ENODEV;
 
-	ret = tsm_report_register(&arm_cca_tsm_ops, NULL);
-	if (ret < 0)
-		pr_err("Error %d registering with TSM\n", ret);
+	ret = tsm_report_register(&arm_cca_tsm_report_ops, NULL);
+	if (ret < 0) {
+		dev_err_probe(&adev->dev, ret, "Error registering with TSM\n");
+		return ret;
+	}
 
-	return ret;
-}
-module_init(arm_cca_guest_init);
+	ret = devm_add_action_or_reset(&adev->dev, unregister_cca_tsm_report, NULL);
+	if (ret < 0) {
+		dev_err_probe(&adev->dev, ret, "Error registering devm action\n");
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

## [3] Aneesh Kumar K.V (Arm) — 2026-05-14
*Subject: [PATCH v5 2/3] hwrng: arm_smccc_trng: Register as an auxiliary device*

The SMCCC TRNG interface is a firmware-provided function rather than a
standalone platform device. Register it as an auxiliary device under the
arm-smccc platform device and convert the hwrng driver to an auxiliary
driver.

This keeps the TRNG device tied to the SMCCC core device while preserving
module autoloading through the auxiliary device ID table.

The conversion changes the device path from the old platform device path,
but no userspace dependency on that path was found. This was confirmed with
a Debian Code Search lookup for the existing platform device name/path.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 drivers/char/hw_random/arm_smccc_trng.c | 25 ++++++++++++++-----------
 drivers/firmware/smccc/smccc.c          | 24 +++++++++++++-----------
 2 files changed, 27 insertions(+), 22 deletions(-)

diff --git a/drivers/char/hw_random/arm_smccc_trng.c b/drivers/char/hw_random/arm_smccc_trng.c
index dcb8e7f37f25..5d56fcbcefa0 100644
--- a/drivers/char/hw_random/arm_smccc_trng.c
+++ b/drivers/char/hw_random/arm_smccc_trng.c
@@ -16,7 +16,7 @@
 #include <linux/device.h>
 #include <linux/hw_random.h>
 #include <linux/module.h>
-#include <linux/platform_device.h>
+#include <linux/auxiliary_bus.h>
 #include <linux/arm-smccc.h>
 
 #ifdef CONFIG_ARM64
@@ -94,29 +94,32 @@ static int smccc_trng_read(struct hwrng *rng, void *data, size_t max, bool wait)
 	return copied;
 }
 
-static int smccc_trng_probe(struct platform_device *pdev)
+static int smccc_trng_probe(struct auxiliary_device *adev,
+		const struct auxiliary_device_id *id)
 {
 	struct hwrng *trng;
 
-	trng = devm_kzalloc(&pdev->dev, sizeof(*trng), GFP_KERNEL);
+	trng = devm_kzalloc(&adev->dev, sizeof(*trng), GFP_KERNEL);
 	if (!trng)
 		return -ENOMEM;
 
 	trng->name = "smccc_trng";
 	trng->read = smccc_trng_read;
 
-	return devm_hwrng_register(&pdev->dev, trng);
+	return devm_hwrng_register(&adev->dev, trng);
 }
 
-static struct platform_driver smccc_trng_driver = {
-	.driver = {
-		.name		= "smccc_trng",
-	},
-	.probe		= smccc_trng_probe,
+static const struct auxiliary_device_id smccc_trng_id_table[] = {
+	{ .name =  KBUILD_MODNAME ".smccc_trng" },
+	{}
 };
-module_platform_driver(smccc_trng_driver);
+MODULE_DEVICE_TABLE(auxiliary, smccc_trng_id_table);
 
-MODULE_ALIAS("platform:smccc_trng");
+static struct auxiliary_driver smccc_trng_driver = {
+	.probe	  = smccc_trng_probe,
+	.id_table = smccc_trng_id_table,
+};
+module_auxiliary_driver(smccc_trng_driver);
 MODULE_AUTHOR("Andre Przywara");
 MODULE_DESCRIPTION("Arm SMCCC TRNG firmware interface support");
 MODULE_LICENSE("GPL");
diff --git a/drivers/firmware/smccc/smccc.c b/drivers/firmware/smccc/smccc.c
index eb077b9aa6da..49ac8172def4 100644
--- a/drivers/firmware/smccc/smccc.c
+++ b/drivers/firmware/smccc/smccc.c
@@ -10,6 +10,7 @@
 #include <linux/arm-smccc.h>
 #include <linux/kernel.h>
 #include <linux/platform_device.h>
+#include <linux/auxiliary_bus.h>
 #include <asm/archrandom.h>
 
 #include "rmm.h"
@@ -94,20 +95,21 @@ static int __init smccc_devices_init(void)
 					PLATFORM_DEVID_NONE, NULL, 0);
 	if (IS_ERR(pdev)) {
 		pr_err("arm-smccc: could not register device: %ld\n", PTR_ERR(pdev));
-	} else {
-		/*
-		 * Register the RMI and RSI devices only when firmware exposes
-		 * the required SMCCC function IDs at a supported revision.
-		 */
-		register_rsi_device(pdev);
+		return 0;
 	}
+	/*
+	 * Register the RMI and RSI devices only when firmware exposes
+	 * the required SMCCC function IDs at a supported revision.
+	 */
+	register_rsi_device(pdev);
 
 	if (smccc_trng_available) {
-		pdev = platform_device_register_simple("smccc_trng", -1,
-						       NULL, 0);
-		if (IS_ERR(pdev))
-			pr_err("smccc_trng: could not register device: %ld\n",
-			       PTR_ERR(pdev));
+		struct auxiliary_device *adev;
+
+		adev = __devm_auxiliary_device_create(&pdev->dev,
+					"arm_smccc_trng", "smccc_trng", NULL, 0);
+		if (!adev)
+			pr_err("smccc_trng: could not register device\n");
 	}
 
 	return 0;

---

## [4] Aneesh Kumar K.V (Arm) — 2026-05-14
*Subject: [PATCH v5 3/3] coco: guest: arm64: Replace dummy CCA device with sysfs ABI*

The SMCCC firmware driver now creates the arm-smccc platform device and
instantiates the CCA auxiliary devices once the RSI ABI is discovered. The
arm64-specific arm-cca-dev platform device stub is therefore no longer
needed.

However, userspace has used the arm-cca-dev platform device to detect Arm
CCA Realm guests [1]. Removing it without a replacement would break that
detection and would also leave userspace depending on kernel device-model
details.

Add /sys/firmware/cca/realm_guest as a stable, architecture-provided ABI
for detecting whether the kernel is running as an Arm CCA Realm guest. The
file returns 1 in Realm world and 0 otherwise, similar to the existing s390
/sys/firmware/uv/prot_virt_guest interface for protected virtualization
guests.

Remove the dummy arm-cca-dev registration now that userspace has a
dedicated CCA Realm guest indicator, and document the new ABI in
Documentation/ABI/testing/sysfs-firmware-cca.

[1] https://lore.kernel.org/all/4a7d84b2-2ec4-4773-a2d5-7b63d5c683cf@arm.com

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 Documentation/ABI/testing/sysfs-firmware-cca | 10 +++++
 arch/arm64/kernel/rsi.c                      | 39 +++++++++++++++-----
 2 files changed, 39 insertions(+), 10 deletions(-)
 create mode 100644 Documentation/ABI/testing/sysfs-firmware-cca

diff --git a/Documentation/ABI/testing/sysfs-firmware-cca b/Documentation/ABI/testing/sysfs-firmware-cca
new file mode 100644
index 000000000000..bf177d636b92
--- /dev/null
+++ b/Documentation/ABI/testing/sysfs-firmware-cca
@@ -0,0 +1,10 @@
+What:		/sys/firmware/cca/realm_guest
+Date:		May 2026
+Contact:	Linux ARM Kernel Mailing list <linux-arm-kernel@lists.infradead.org>
+Description:	Read-only. Indicates whether the kernel is running as an
+		Arm Confidential Compute Architecture (CCA) Realm guest.
+
+		The value is one of:
+
+		0: the kernel is not running as a Realm guest
+		1: the kernel is running as a Realm guest
diff --git a/arch/arm64/kernel/rsi.c b/arch/arm64/kernel/rsi.c
index 8380e5ba88d2..a3e9b3bb5679 100644
--- a/arch/arm64/kernel/rsi.c
+++ b/arch/arm64/kernel/rsi.c
@@ -9,6 +9,8 @@
 #include <linux/swiotlb.h>
 #include <linux/cc_platform.h>
 #include <linux/platform_device.h>
+#include <linux/kobject.h>
+#include <linux/sysfs.h>
 
 #include <asm/io.h>
 #include <asm/mem_encrypt.h>
@@ -16,6 +18,7 @@
 #include <asm/rsi.h>
 
 static struct realm_config config;
+static struct kobject *cca_kobj;
 
 unsigned long prot_ns_shared;
 EXPORT_SYMBOL(prot_ns_shared);
@@ -160,17 +163,33 @@ void __init arm64_rsi_init(void)
 	static_branch_enable(&rsi_present);
 }
 
-static struct platform_device rsi_dev = {
-	.name = "arm-cca-dev",
-	.id = PLATFORM_DEVID_NONE
+static ssize_t cca_is_realm_guest(struct kobject *kobj,
+		struct kobj_attribute *attr, char *buf)
+{
+	return sysfs_emit(buf, "%d\n", is_realm_world());
+}
+
+static struct kobj_attribute cca_realm_guest =
+	__ATTR(realm_guest, 0444, cca_is_realm_guest, NULL);
+
+static const struct attribute *cca_realm_attrs[] = {
+	&cca_realm_guest.attr,
+	NULL,
 };
 
-static int __init arm64_create_dummy_rsi_dev(void)
+static int __init realm_sysfs_init(void)
 {
-	if (is_realm_world() &&
-	    platform_device_register(&rsi_dev))
-		pr_err("failed to register rsi platform device\n");
-	return 0;
-}
+	int ret;
+
+	cca_kobj = kobject_create_and_add("cca", firmware_kobj);
+	if (!cca_kobj)
+		return -ENOMEM;
 
-arch_initcall(arm64_create_dummy_rsi_dev)
+	ret = sysfs_create_files(cca_kobj, cca_realm_attrs);
+	if (!ret)
+		return 0;
+
+	kobject_put(cca_kobj);
+	return ret;
+}
+device_initcall(realm_sysfs_init);

---

## [5] Greg KH — 2026-05-14
*Subject: Re: [PATCH v5 0/3] Switch Arm CCA to use an auxiliary device instead
 of a platform device*

On Thu, May 14, 2026 at 03:10:27PM +0530, Aneesh Kumar K.V (Arm) wrote:
> As discussed here:
> https://lore.kernel.org/all/20250728135216.48084-12-aneesh.kumar@kernel.org

Why an aux device?  If this has no platform resources, please use the
faux bus support instead, that is what it is there for.  aux devices are
used when you are sharing a real resource among different "child"
drivers, and need some way to coordinate that sharing.  If you have no
resources, there's nothing to share, so no need for the complexity that
aux gives you, just use faux instead.

thanks,

greg k-h

---

## [6] Aneesh Kumar K.V — 2026-05-14
*Subject: Re: [PATCH v5 0/3] Switch Arm CCA to use an auxiliary device
 instead of a platform device*

Greg KH <gregkh@linuxfoundation.org> writes:

> On Thu, May 14, 2026 at 03:10:27PM +0530, Aneesh Kumar K.V (Arm) wrote:
>> As discussed here:

We did discuss between faux an auxiliary devices early here
https://lore.kernel.org/all/20251010135922.GC3833649@ziepe.ca

To summarize auxiliary device was choosen so that we can do module
autoloading.

-aneesh

---

## [7] Suzuki K Poulose — 2026-05-14
*Subject: Re: [PATCH v5 1/3] firmware: smccc: coco: Manage arm-smccc platform
 device and CCA auxiliary drivers*

Hi Aneesh

On 14/05/2026 10:40, Aneesh Kumar K.V (Arm) wrote:
> Make the SMCCC driver responsible for registering the arm-smccc platform
> device and after confirming the relevant SMCCC function IDs, create

There are a few changes squashed in to this patch. Please could we
split the patch in the following order ?

1. Add platform device for arm-smccc
2. Move TRNG to Auxilliary Device - (Even though it is a later patch, 
move it before the RSI changes)
3. Move RSI dev as Auxilliary
4. Add the firmware sysfs ABI.

That way, first two could be merged while we figure out (3) and (4)


> Also update the arm-cca-guest driver to use the auxiliary device
> interface instead of the platform device (arm-cca-dev). The removal of

super minor nit: While I understand you plan to use this for DEV SEC TSM
in the future, could we retain the generic TSM name usage ?

> +		const struct auxiliary_device_id *id)
>   {

same as above, s/devsec_// ?

Suzuki


> +	{ .name =  KBUILD_MODNAME "." RSI_DEV_NAME },
> +	{}

---

## [8] Greg KH — 2026-05-14
*Subject: Re: [PATCH v5 0/3] Switch Arm CCA to use an auxiliary device instead
 of a platform device*

On Thu, May 14, 2026 at 04:21:48PM +0530, Aneesh Kumar K.V wrote:
> Greg KH <gregkh@linuxfoundation.org> writes:
> 

That's not a valid reason to use the aux driver, sorry.  If you have
hardware that triggers an auto-module-load, then this is really a
hardware driver.  If it is a "virtual" driver like this, then you need
to explicitly load it on your own.  Don't abuse apis for reasons that
they are not designed for.

thanks,

greg k-h

---

## [9] Sudeep Holla — 2026-05-14
*Subject: Re: [PATCH v5 1/3] firmware: smccc: coco: Manage arm-smccc platform
 device and CCA auxiliary drivers*

On Thu, May 14, 2026 at 12:04:13PM +0100, Suzuki K Poulose wrote:
> Hi Aneesh
> 

I had similar thoughts but I didn't get into forming a reply, now I can keep
it small, thanks for that 😉.

> Please could we split the patch in the following order ?
> 

I agree with the logical split of functionality above.

> That way, first two could be merged while we figure out (3) and (4)
> 

I disagree with this though. We don't want to merge this unless (3) is
agreed. There is no point in doing that unless we agree the approach for
RSI as well.

---

## [10] Greg KH — 2026-05-14
*Subject: Re: [PATCH v5 1/3] firmware: smccc: coco: Manage arm-smccc platform
 device and CCA auxiliary drivers*

On Thu, May 14, 2026 at 12:04:13PM +0100, Suzuki K Poulose wrote:
> Hi Aneesh
> 

Do not make any more "fake" platform devices please.

> 2. Move TRNG to Auxilliary Device - (Even though it is a later patch, move
> it before the RSI changes)

No, move it to the faux api please.

thanks,

greg k-h

---

## [11] Catalin Marinas — 2026-05-14
*Subject: Re: [PATCH v5 1/3] firmware: smccc: coco: Manage arm-smccc platform
 device and CCA auxiliary drivers*

On Thu, May 14, 2026 at 02:55:48PM +0200, Greg Kroah-Hartman wrote:
> On Thu, May 14, 2026 at 12:04:13PM +0100, Suzuki K Poulose wrote:
> > On 14/05/2026 10:40, Aneesh Kumar K.V (Arm) wrote:

So should we end up with:

  /sys/devices/faux/arm-smccc/
    smccc_trng/
    arm-rsi-dev/
      tsm/tsm0

  /sys/class/tsm/tsm0
    -> ../../devices/faux/arm-smccc/arm-rsi-dev/tsm/tsm0

  /sys/firmware/cca/
    realm_guest

---

## [12] Catalin Marinas — 2026-05-14
*Subject: Re: [PATCH v5 1/3] firmware: smccc: coco: Manage arm-smccc platform
 device and CCA auxiliary drivers*

On Thu, May 14, 2026 at 03:10:28PM +0530, Aneesh Kumar K.V (Arm) wrote:
> diff --git a/drivers/firmware/smccc/rmm.h b/drivers/firmware/smccc/rmm.h
> new file mode 100644

Nit: static inline here (I think Sashiko mentioned it on a previous
version.

> +{
> +

And unnecessary empty line between curly braces.

Just these notpicks for now. Suzuki and Sudeep already covered the
splitting of this patch and we need to agree on the sysfs hierarchy.

---

## [13] Greg KH — 2026-05-14
*Subject: Re: [PATCH v5 1/3] firmware: smccc: coco: Manage arm-smccc platform
 device and CCA auxiliary drivers*

On Thu, May 14, 2026 at 02:19:19PM +0100, Catalin Marinas wrote:
> On Thu, May 14, 2026 at 02:55:48PM +0200, Greg Kroah-Hartman wrote:
> > On Thu, May 14, 2026 at 12:04:13PM +0100, Suzuki K Poulose wrote:

What types are these child devices?  Also faux ones?

If so, great.

thanks,

greg k-h

---

## [14] Catalin Marinas — 2026-05-14
*Subject: Re: [PATCH v5 1/3] firmware: smccc: coco: Manage arm-smccc platform
 device and CCA auxiliary drivers*

On Thu, May 14, 2026 at 03:25:34PM +0200, Greg Kroah-Hartman wrote:
> On Thu, May 14, 2026 at 02:19:19PM +0100, Catalin Marinas wrote:
> > On Thu, May 14, 2026 at 02:55:48PM +0200, Greg Kroah-Hartman wrote:

They'd also be faux devices with this structure (in practice they are
firmware interfaces that may be backed by some hardware like in the TRNG
case, though not directly accessible to Linux).

---

## [15] Greg KH — 2026-05-14
*Subject: Re: [PATCH v5 1/3] firmware: smccc: coco: Manage arm-smccc platform
 device and CCA auxiliary drivers*

On Thu, May 14, 2026 at 02:46:11PM +0100, Catalin Marinas wrote:
> On Thu, May 14, 2026 at 03:25:34PM +0200, Greg Kroah-Hartman wrote:
> > On Thu, May 14, 2026 at 02:19:19PM +0100, Catalin Marinas wrote:

Great, seems sane to me!

---

## [16] Aneesh Kumar K.V — 2026-05-14
*Subject: Re: [PATCH v5 1/3] firmware: smccc: coco: Manage arm-smccc platform
 device and CCA auxiliary drivers*

Greg KH <gregkh@linuxfoundation.org> writes:

> On Thu, May 14, 2026 at 12:04:13PM +0100, Suzuki K Poulose wrote:
>> Hi Aneesh


Maybe I was not complete in my previous reply. I did not want to repeat
the entire thread, so I quoted the lore link for more details.

1. We have platform firmware-provided SMCCC interfaces. Based on the
support/availability of these function IDs, we want to load multiple
drivers.
2. This patch series adds a platform device to represent the
firmware-provided SMCCC resource.
3. Different SMCCC ranges are now represented as auxiliary devices.
4. Different subsystems, such as TSM, can autoload their backend drivers
based on the availability of these SMCCC ranges, which are now
represented as auxiliary devices.

You had agreed to all of this in the previous discussion here:
https://lore.kernel.org/all/2025101516-handbook-hyphen-62ec@gregkh

-aneesh

---

## [17] Aneesh Kumar K.V — 2026-05-14
*Subject: Re: [PATCH v5 1/3] firmware: smccc: coco: Manage arm-smccc platform
 device and CCA auxiliary drivers*

Catalin Marinas <catalin.marinas@arm.com> writes:

> On Thu, May 14, 2026 at 02:55:48PM +0200, Greg Kroah-Hartman wrote:
>> On Thu, May 14, 2026 at 12:04:13PM +0100, Suzuki K Poulose wrote:

But we need the ability to autoload different TSM backend drivers based
on the support/availability of these SMCCC function-id ranges. faux
device don't support that.

-aneesh

---

## [18] Catalin Marinas — 2026-05-14
*Subject: Re: [PATCH v5 1/3] firmware: smccc: coco: Manage arm-smccc platform
 device and CCA auxiliary drivers*

On Thu, May 14, 2026 at 08:08:01PM +0530, Aneesh Kumar K.V wrote:
> Catalin Marinas <catalin.marinas@arm.com> writes:
> > On Thu, May 14, 2026 at 02:55:48PM +0200, Greg Kroah-Hartman wrote:

It breaks this but can we not have some systemd rule that checks
/sys/firmware/cca/realm_guest and modprobes arm_cca_guest?

Alternatively, we could do a request_module("arm_cca_guest") if
RSI is available when we check it in smccc_devices_init(). Or make it
even fancier with a request_module("arm-smccc-service-...") (some ID
range while arm-cca-guest.c has a corresponding MODULE_ALIAS() for that
SMCCC range.

---

## [19] Greg KH — 2026-05-14
*Subject: Re: [PATCH v5 1/3] firmware: smccc: coco: Manage arm-smccc platform
 device and CCA auxiliary drivers*

On Thu, May 14, 2026 at 08:08:01PM +0530, Aneesh Kumar K.V wrote:
> Catalin Marinas <catalin.marinas@arm.com> writes:
> 

If you really need to "autoload" things, then do it like any other
normal bus or class does this, and send the proper uevents as needed.
Don't abuse the auxbus code for this please!

thanks,

greg k-h

---

## [20] Greg KH — 2026-05-14
*Subject: Re: [PATCH v5 1/3] firmware: smccc: coco: Manage arm-smccc platform
 device and CCA auxiliary drivers*

On Thu, May 14, 2026 at 08:07:27PM +0530, Aneesh Kumar K.V wrote:
> Greg KH <gregkh@linuxfoundation.org> writes:
> 

Then why did someone say "this is a fake platform device with no actual
resources"?  That's what I was triggering off of.

Again, if you have actual platform resources, GREAT, use a platform
device and aux.  If you do not, then do NOT use a platform device.

totally confused,

greg k-h

---

## [21] Aneesh Kumar K.V — 2026-05-18
*Subject: Re: [PATCH v5 1/3] firmware: smccc: coco: Manage arm-smccc platform
 device and CCA auxiliary drivers*

Greg KH <gregkh@linuxfoundation.org> writes:

> On Thu, May 14, 2026 at 08:07:27PM +0530, Aneesh Kumar K.V wrote:
>> Greg KH <gregkh@linuxfoundation.org> writes:

I have now rewritten the cover letter as below. Let me know if this
helps.

Switch Arm SMCCC firmware services to auxiliary devices

As discussed here:
https://lore.kernel.org/all/20250728135216.48084-12-aneesh.kumar@kernel.org

The earlier CCA guest support used an arm-cca-dev platform device as a pure
software anchor for the TSM class device. That platform device did not
correspond to a DT/ACPI described device, MMIO range, interrupt, or other
platform resource; it existed only to make the CCA guest driver bind and to
place the resulting TSM device in the driver model. The same pattern also
exists for smccc_trng. Creating separate platform devices for such
SMCCC-discovered features is misleading, because those features are not
independent platform devices.

This series changes the model so that there is a single arm-smccc platform
device representing the SMCCC firmware interface itself. The firmware
interface, including its discoverable SMCCC function space, is the
resource: after PSCI/SMCCC conduit discovery, the kernel can query SMCCC
function IDs and determine whether optional firmware services are present.
Services such as SMCCC TRNG and Realm Services Interface (RSI) are
therefore represented as children of the arm-smccc device, and are created
only when the required SMCCC function IDs and ABI checks succeed.

The child devices use the auxiliary bus deliberately: they are intended to
bind independent feature drivers, not just to provide a driverless object for
sysfs or other class-device anchoring. They are firmware-provided functions
of the parent SMCCC interface that are consumed by separate kernel drivers
in different subsystems, such as hwrng and virt/coco/TSM. Those drivers
need normal driver-core matching, probe/remove lifetime, and module
autoloading based on the discovered firmware feature. The auxiliary bus
provides a MODALIAS and id-table based binding model for that case, while
keeping the feature drivers off the platform bus. A faux device was
considered, but not used because it is suited for simple software objects
that do not need independent bus/driver binding. The faux bus has no
feature-driver id-table or MODALIAS matching, so it would not preserve the
module-autoload flow that the current platform-device based users rely on.

In other words, the parent arm-smccc device represents the firmware
resource exposed through the SMCCC conduit, and each auxiliary child
represents one discovered firmware service of that parent. This removes the
unnecessary per-feature platform devices while retaining automatic loading
and independent subsystem drivers for the SMCCC services.

The TSM framework uses the device abstraction to provide cross-architecture
TSM and TEE I/O functionality, including enumerating available platform TEE
I/O capabilities and provisioning connections between the platform TSM and
device DSMs.  For Arm CCA, the RSI auxiliary device continues to provide the
device anchor used by the CCA guest TSM provider.

For the CCA platform, the resulting device hierarchy appears as follows.
Note that the auxiliary device is parented by the arm-smccc platform device,
so the sysfs path remains under /devices/platform/arm-smccc/:

$ cd /sys/class/tsm/
$ ls -al
total 0
drwxr-xr-x    2 root     root             0 Jan  1 00:02 .
drwxr-xr-x   23 root     root             0 Jan  1 00:00 ..
lrwxrwxrwx    1 root     root             0 Jan  1 00:03 tsm0 -> ../../devices/platform/arm-smccc/arm_cca_guest.arm-rsi-dev.0/tsm/tsm0
$

The series also replaces the old arm-cca-dev userspace-visible dummy device
with /sys/firmware/cca/realm_guest for detecting whether the kernel is
running in a Realm.  This keeps the guest-state ABI under /sys/firmware and
separates it from the internal driver-binding device used by the CCA guest
TSM provider.


-aneesh

---

## [22] Aneesh Kumar K.V — 2026-05-20
*Subject: Re: [PATCH v5 1/3] firmware: smccc: coco: Manage arm-smccc platform
 device and CCA auxiliary drivers*

Hi Greg,

Aneesh Kumar K.V <aneesh.kumar@kernel.org> writes:

> Greg KH <gregkh@linuxfoundation.org> writes:
>

Gentle ping, could you let me know if the updated cover letter helps
clarify the confusion regarding the platform-device usage here?

-aneesh

---
