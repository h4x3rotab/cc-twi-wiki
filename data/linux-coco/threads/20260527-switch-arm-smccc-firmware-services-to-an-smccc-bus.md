---
title: 'Switch Arm SMCCC firmware services to an SMCCC bus'
date: 2026-05-27
last_reply: 2026-05-27
message_count: 5
participants: ['Aneesh Kumar K.V (Arm)']
---

## [1] Aneesh Kumar K.V (Arm) — 2026-05-27

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

This series adds an Arm SMCCC bus for services discovered through the SMCCC
firmware interface. The bus provides SMCCC device and driver registration
helpers, name-based matching, uevent modalias generation, and a sysfs modalias
attribute. SMCCC service drivers can use MODULE_DEVICE_TABLE(arm_smccc, ...)
to emit arm_smccc:<name> aliases, allowing userspace to autoload service
drivers when the SMCCC core registers matching firmware-service devices.

The series then moves SMCCC TRNG and the Arm CCA guest RSI service off the
platform bus. When the SMCCC core discovers the corresponding firmware
service, it registers an arm-smccc device for that service. The hwrng
arm_smccc_trng driver and the Arm CCA guest TSM provider are converted to
SMCCC drivers that bind to those discovered devices.

The old arm-cca-dev platform device has also been used by userspace as a Realm
guest indicator. Removing it without a replacement would leave userspace
depending on an internal driver-binding device. This series therefore adds
/sys/firmware/cca/realm_guest as a stable, architecture-provided ABI for
detecting whether the kernel is running as an Arm CCA Realm guest, and then
removes the dummy arm-cca-dev platform-device registration.

Changes from v5:
https://lore.kernel.org/all/20260514094030.42495-1-aneesh.kumar@kernel.org
* Replace the arm-smccc platform-device plus auxiliary-child model with a
  dedicated Arm SMCCC bus.
* Add SMCCC module alias support so SMCCC service drivers can use
  MODULE_DEVICE_TABLE(arm_smccc, ...) and autoload through arm_smccc:<name>
  aliases.
* Convert smccc_trng from a platform driver to an SMCCC driver.
* Convert the Arm CCA guest TSM provider from the arm-cca-dev platform device
  to an SMCCC driver bound to the discovered RSI service.
* Add /sys/firmware/cca/realm_guest before removing the old arm-cca-dev dummy
  platform device.

Changes from v4:
https://lore.kernel.org/all/20260427061615.905018-1-aneesh.kumar@kernel.org
* Add /sys/firmware/cca/realm_guest for detecting realm guest
* Convert smccc_trng to auxiliary device from platform device

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


Aneesh Kumar K.V (Arm) (4):
  firmware: smccc: Add an Arm SMCCC bus
  firmware: hwrng: arm_smccc_trng: Register as an SMCCC device
  firmware: smccc: arm-cca-guest: Bind the TSM provider to an SMCCC
    device
  coco: guest: arm64: Replace dummy CCA device with sysfs ABI

 Documentation/ABI/testing/sysfs-firmware-cca  |  10 +
 arch/arm64/include/asm/rsi.h                  |   2 +-
 arch/arm64/kernel/rsi.c                       |  39 +++-
 drivers/char/hw_random/arm_smccc_trng.c       |  26 +--
 drivers/firmware/smccc/Makefile               |   4 +
 drivers/firmware/smccc/rmm.c                  |  25 +++
 drivers/firmware/smccc/rmm.h                  |  17 ++
 drivers/firmware/smccc/smccc.c                | 178 +++++++++++++++++-
 drivers/virt/coco/arm-cca-guest/Kconfig       |   1 +
 drivers/virt/coco/arm-cca-guest/Makefile      |   2 +
 .../{arm-cca-guest.c => arm-cca.c}            |  60 +++---
 include/linux/arm-smccc-bus.h                 |  49 +++++
 include/linux/mod_devicetable.h               |  13 ++
 scripts/mod/devicetable-offsets.c             |   3 +
 scripts/mod/file2alias.c                      |   8 +
 15 files changed, 378 insertions(+), 59 deletions(-)
 create mode 100644 Documentation/ABI/testing/sysfs-firmware-cca
 create mode 100644 drivers/firmware/smccc/rmm.c
 create mode 100644 drivers/firmware/smccc/rmm.h
 rename drivers/virt/coco/arm-cca-guest/{arm-cca-guest.c => arm-cca.c} (85%)
 create mode 100644 include/linux/arm-smccc-bus.h


base-commit: 50897c955902c93ae71c38698abb910525ebdc89

---

## [2] Aneesh Kumar K.V (Arm) — 2026-05-27
*Subject: [PATCH v6 1/4] firmware: smccc: Add an Arm SMCCC bus*

SMCCC-discovered firmware services are currently represented by separate
platform devices, such as smccc_trng and arm-cca-dev. Those devices do not
represent independent DT/ACPI-described platform resources; they are
features of the SMCCC firmware interface.

Add an Arm SMCCC bus for services discovered through the SMCCC firmware
interface. The bus provides SMCCC device and driver registration helpers,
name-based matching, modalias generation, and a sysfs modalias attribute so
SMCCC service drivers can bind to discovered firmware services and autoload
as modules.

Follow-up changes can then register SMCCC firmware services as arm-smccc
devices instead of creating independent per-feature platform devices.

Based on arm_ffa code

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 drivers/firmware/smccc/smccc.c    | 158 ++++++++++++++++++++++++++++++
 include/linux/arm-smccc-bus.h     |  49 +++++++++
 include/linux/mod_devicetable.h   |  13 +++
 scripts/mod/devicetable-offsets.c |   3 +
 scripts/mod/file2alias.c          |   8 ++
 5 files changed, 231 insertions(+)
 create mode 100644 include/linux/arm-smccc-bus.h

diff --git a/drivers/firmware/smccc/smccc.c b/drivers/firmware/smccc/smccc.c
index bdee057db2fd..695c920a8087 100644
--- a/drivers/firmware/smccc/smccc.c
+++ b/drivers/firmware/smccc/smccc.c
@@ -10,10 +10,15 @@
 #include <linux/arm-smccc.h>
 #include <linux/kernel.h>
 #include <linux/platform_device.h>
+#include <linux/arm-smccc-bus.h>
+#include <linux/idr.h>
+#include <linux/slab.h>
+
 #include <asm/archrandom.h>
 
 static u32 smccc_version = ARM_SMCCC_VERSION_1_0;
 static enum arm_smccc_conduit smccc_conduit = SMCCC_CONDUIT_NONE;
+static DEFINE_IDA(arm_smccc_bus_id);
 
 bool __ro_after_init smccc_trng_available = false;
 s32 __ro_after_init smccc_soc_id_version = SMCCC_RET_NOT_SUPPORTED;
@@ -81,6 +86,159 @@ bool arm_smccc_hypervisor_has_uuid(const uuid_t *hyp_uuid)
 }
 EXPORT_SYMBOL_GPL(arm_smccc_hypervisor_has_uuid);
 
+static int arm_smccc_bus_match(struct device *dev,
+		const struct device_driver *drv)
+{
+	const struct arm_smccc_device_id *id_table;
+	struct arm_smccc_device *smccc_dev = to_arm_smccc_device(dev);
+
+	id_table = to_arm_smccc_driver(drv)->id_table;
+	if (!id_table)
+		return 0;
+
+	while (id_table->name[0]) {
+		if (!strcmp(smccc_dev->name, id_table->name))
+			return 1;
+		id_table++;
+	}
+
+	return 0;
+}
+
+static int arm_smccc_bus_probe(struct device *dev)
+{
+	struct arm_smccc_driver *smccc_drv = to_arm_smccc_driver(dev->driver);
+
+	return smccc_drv->probe(to_arm_smccc_device(dev));
+}
+
+static void arm_smccc_bus_remove(struct device *dev)
+{
+	struct arm_smccc_driver *smcc_drv = to_arm_smccc_driver(dev->driver);
+
+	if (smcc_drv->remove)
+		smcc_drv->remove(to_arm_smccc_device(dev));
+}
+
+static int arm_smccc_bus_uevent(const struct device *dev,
+		struct kobj_uevent_env *env)
+{
+	const struct arm_smccc_device *smccc_dev = to_arm_smccc_device(dev);
+
+	return add_uevent_var(env, "MODALIAS=" ARM_SMCCC_MODULE_PREFIX "%s",
+			      smccc_dev->name);
+}
+
+static ssize_t modalias_show(struct device *dev,
+		struct device_attribute *attr, char *buf)
+{
+	struct arm_smccc_device *smccc_dev = to_arm_smccc_device(dev);
+
+	return sysfs_emit(buf, ARM_SMCCC_MODULE_PREFIX "%s\n", smccc_dev->name);
+}
+static DEVICE_ATTR_RO(modalias);
+
+static struct attribute *arm_smccc_device_attrs[] = {
+	&dev_attr_modalias.attr,
+	NULL,
+};
+ATTRIBUTE_GROUPS(arm_smccc_device);
+
+const struct bus_type arm_smccc_bus_type = {
+	.name = "arm_smccc",
+	.match = arm_smccc_bus_match,
+	.probe = arm_smccc_bus_probe,
+	.remove = arm_smccc_bus_remove,
+	.uevent = arm_smccc_bus_uevent,
+	.dev_groups = arm_smccc_device_groups,
+};
+EXPORT_SYMBOL_GPL(arm_smccc_bus_type);
+
+int arm_smccc_driver_register(struct arm_smccc_driver *driver,
+		struct module *owner, const char *mod_name)
+{
+	if (!driver->probe)
+		return -EINVAL;
+
+	driver->driver.bus = &arm_smccc_bus_type;
+	driver->driver.name = driver->name;
+	driver->driver.owner = owner;
+	driver->driver.mod_name = mod_name;
+
+	return driver_register(&driver->driver);
+}
+EXPORT_SYMBOL_GPL(arm_smccc_driver_register);
+
+void arm_smccc_driver_unregister(struct arm_smccc_driver *driver)
+{
+	driver_unregister(&driver->driver);
+}
+EXPORT_SYMBOL_GPL(arm_smccc_driver_unregister);
+
+static void arm_smccc_release_device(struct device *dev)
+{
+	struct arm_smccc_device *smccc_dev = to_arm_smccc_device(dev);
+
+	ida_free(&arm_smccc_bus_id, smccc_dev->id);
+	kfree(smccc_dev);
+}
+
+struct arm_smccc_device *arm_smccc_device_register(const char *name)
+{
+	struct arm_smccc_device *smccc_dev;
+	int id, ret;
+
+	id = ida_alloc_min(&arm_smccc_bus_id, 1, GFP_KERNEL);
+	if (id < 0)
+		return ERR_PTR(id);
+
+	smccc_dev = kzalloc_obj(*smccc_dev);
+	if (!smccc_dev) {
+		ida_free(&arm_smccc_bus_id, id);
+		return ERR_PTR(-ENOMEM);
+	}
+
+	smccc_dev->id = id;
+	if (strscpy(smccc_dev->name, name) < 0) {
+		kfree(smccc_dev);
+		ida_free(&arm_smccc_bus_id, id);
+		return ERR_PTR(-EINVAL);
+	}
+	smccc_dev->dev.bus = &arm_smccc_bus_type;
+	smccc_dev->dev.release = arm_smccc_release_device;
+
+	ret = dev_set_name(&smccc_dev->dev, "%s-%d", smccc_dev->name, id);
+	if (ret) {
+		kfree(smccc_dev);
+		ida_free(&arm_smccc_bus_id, id);
+		return ERR_PTR(ret);
+	}
+
+	ret = device_register(&smccc_dev->dev);
+	if (ret) {
+		put_device(&smccc_dev->dev);
+		return ERR_PTR(ret);
+	}
+
+	return smccc_dev;
+}
+EXPORT_SYMBOL_GPL(arm_smccc_device_register);
+
+void arm_smccc_device_unregister(struct arm_smccc_device *smccc_dev)
+{
+	if (!smccc_dev)
+		return;
+
+	device_unregister(&smccc_dev->dev);
+}
+EXPORT_SYMBOL_GPL(arm_smccc_device_unregister);
+
+static int __init arm_smccc_bus_init(void)
+{
+	return bus_register(&arm_smccc_bus_type);
+}
+subsys_initcall(arm_smccc_bus_init);
+
 static int __init smccc_devices_init(void)
 {
 	struct platform_device *pdev;
diff --git a/include/linux/arm-smccc-bus.h b/include/linux/arm-smccc-bus.h
new file mode 100644
index 000000000000..188891441e57
--- /dev/null
+++ b/include/linux/arm-smccc-bus.h
@@ -0,0 +1,49 @@
+/* SPDX-License-Identifier: GPL-2.0-only */
+/*
+ * Copyright (C) 2026 Arm Limited
+ */
+#ifndef __LINUX_ARM_SMCCC_BUS_H
+#define __LINUX_ARM_SMCCC_BUS_H
+
+#include <linux/device.h>
+#include <linux/mod_devicetable.h>
+#include <linux/module.h>
+
+struct arm_smccc_device {
+	int id;
+	char name[ARM_SMCCC_NAME_SIZE];
+	struct device dev;
+};
+
+#define to_arm_smccc_device(d) container_of(d, struct arm_smccc_device, dev)
+
+struct arm_smccc_driver {
+	const char *name;
+	int (*probe)(struct arm_smccc_device *sdev);
+	void (*remove)(struct arm_smccc_device *sdev);
+	const struct arm_smccc_device_id *id_table;
+
+	struct device_driver driver;
+};
+
+#define to_arm_smccc_driver(d) \
+	container_of_const(d, struct arm_smccc_driver, driver)
+
+int arm_smccc_driver_register(struct arm_smccc_driver *driver,
+		struct module *owner, const char *mod_name);
+void arm_smccc_driver_unregister(struct arm_smccc_driver *driver);
+struct arm_smccc_device *arm_smccc_device_register(const char *name);
+void arm_smccc_device_unregister(struct arm_smccc_device *smcc_dev);
+
+#define arm_smccc_register(driver) \
+	arm_smccc_driver_register(driver, THIS_MODULE, KBUILD_MODNAME)
+#define arm_smccc_unregister(driver) \
+	arm_smccc_driver_unregister(driver)
+
+#define module_arm_smccc_driver(__arm_smccc_driver) \
+	module_driver(__arm_smccc_driver, arm_smccc_register, \
+		      arm_smccc_unregister)
+
+extern const struct bus_type arm_smccc_bus_type;
+
+#endif /* __LINUX_ARM_SMCCC_BUS_H */
diff --git a/include/linux/mod_devicetable.h b/include/linux/mod_devicetable.h
index 23ff24080dfd..c9cee8c5a0b2 100644
--- a/include/linux/mod_devicetable.h
+++ b/include/linux/mod_devicetable.h
@@ -876,6 +876,19 @@ struct auxiliary_device_id {
 	kernel_ulong_t driver_data;
 };
 
+#define ARM_SMCCC_NAME_SIZE 40
+#define ARM_SMCCC_MODULE_PREFIX "arm_smccc:"
+
+/**
+ * struct arm_smccc_device_id - Arm SMCCC bus device identifier
+ * @name: SMCCC device name
+ * @driver_data: driver data
+ */
+struct arm_smccc_device_id {
+	char name[ARM_SMCCC_NAME_SIZE];
+	kernel_ulong_t driver_data;
+};
+
 /* Surface System Aggregator Module */
 
 #define SSAM_MATCH_TARGET	0x1
diff --git a/scripts/mod/devicetable-offsets.c b/scripts/mod/devicetable-offsets.c
index b4178c42d08f..a485011ff137 100644
--- a/scripts/mod/devicetable-offsets.c
+++ b/scripts/mod/devicetable-offsets.c
@@ -254,6 +254,9 @@ int main(void)
 	DEVID(auxiliary_device_id);
 	DEVID_FIELD(auxiliary_device_id, name);
 
+	DEVID(arm_smccc_device_id);
+	DEVID_FIELD(arm_smccc_device_id, name);
+
 	DEVID(ssam_device_id);
 	DEVID_FIELD(ssam_device_id, match_flags);
 	DEVID_FIELD(ssam_device_id, domain);
diff --git a/scripts/mod/file2alias.c b/scripts/mod/file2alias.c
index 4e99393a35f1..0ce4fb049711 100644
--- a/scripts/mod/file2alias.c
+++ b/scripts/mod/file2alias.c
@@ -1296,6 +1296,13 @@ static void do_auxiliary_entry(struct module *mod, void *symval)
 	module_alias_printf(mod, false, AUXILIARY_MODULE_PREFIX "%s", *name);
 }
 
+static void do_arm_smccc_entry(struct module *mod, void *symval)
+{
+	DEF_FIELD_ADDR(symval, arm_smccc_device_id, name);
+
+	module_alias_printf(mod, false, ARM_SMCCC_MODULE_PREFIX "%s", *name);
+}
+
 /*
  * Looks like: ssam:dNcNtNiNfN
  *
@@ -1466,6 +1473,7 @@ static const struct devtable devtable[] = {
 	{"mhi", SIZE_mhi_device_id, do_mhi_entry},
 	{"mhi_ep", SIZE_mhi_device_id, do_mhi_ep_entry},
 	{"auxiliary", SIZE_auxiliary_device_id, do_auxiliary_entry},
+	{"arm_smccc", SIZE_arm_smccc_device_id, do_arm_smccc_entry},
 	{"ssam", SIZE_ssam_device_id, do_ssam_entry},
 	{"dfl", SIZE_dfl_device_id, do_dfl_entry},
 	{"ishtp", SIZE_ishtp_device_id, do_ishtp_entry},

---

## [3] Aneesh Kumar K.V (Arm) — 2026-05-27
*Subject: [PATCH v6 2/4] firmware: hwrng: arm_smccc_trng: Register as an SMCCC device*

The SMCCC TRNG interface is a firmware-provided SMCCC service rather than a
standalone platform device. Now that the SMCCC core has an SMCCC bus,
create an arm-smccc-trng device for the discovered TRNG service and convert
the hwrng driver to an SMCCC driver.

The SMCCC id table preserves module autoloading for systems where the TRNG
driver is built as a module.

The sysfs device path changes from the old smccc_trng platform-device path
to an arm-smccc device path. No known userspace dependency on the old path
was found; a Debian Code Search lookup for the existing platform-device
name/path did not find any users.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 drivers/char/hw_random/arm_smccc_trng.c | 26 ++++++++++++++-----------
 drivers/firmware/smccc/smccc.c          | 14 ++++++-------
 2 files changed, 21 insertions(+), 19 deletions(-)

diff --git a/drivers/char/hw_random/arm_smccc_trng.c b/drivers/char/hw_random/arm_smccc_trng.c
index dcb8e7f37f25..d273e6fc7129 100644
--- a/drivers/char/hw_random/arm_smccc_trng.c
+++ b/drivers/char/hw_random/arm_smccc_trng.c
@@ -16,8 +16,8 @@
 #include <linux/device.h>
 #include <linux/hw_random.h>
 #include <linux/module.h>
-#include <linux/platform_device.h>
 #include <linux/arm-smccc.h>
+#include <linux/arm-smccc-bus.h>
 
 #ifdef CONFIG_ARM64
 #define ARM_SMCCC_TRNG_RND	ARM_SMCCC_TRNG_RND64
@@ -94,29 +94,33 @@ static int smccc_trng_read(struct hwrng *rng, void *data, size_t max, bool wait)
 	return copied;
 }
 
-static int smccc_trng_probe(struct platform_device *pdev)
+static int smccc_trng_probe(struct arm_smccc_device *sdev)
 {
 	struct hwrng *trng;
 
-	trng = devm_kzalloc(&pdev->dev, sizeof(*trng), GFP_KERNEL);
+	trng = devm_kzalloc(&sdev->dev, sizeof(*trng), GFP_KERNEL);
 	if (!trng)
 		return -ENOMEM;
 
 	trng->name = "smccc_trng";
 	trng->read = smccc_trng_read;
 
-	return devm_hwrng_register(&pdev->dev, trng);
+	return devm_hwrng_register(&sdev->dev, trng);
 }
 
-static struct platform_driver smccc_trng_driver = {
-	.driver = {
-		.name		= "smccc_trng",
-	},
-	.probe		= smccc_trng_probe,
+static const struct arm_smccc_device_id smccc_trng_id_table[] = {
+	{ .name = "arm-smccc-trng" },
+	{}
 };
-module_platform_driver(smccc_trng_driver);
+MODULE_DEVICE_TABLE(arm_smccc, smccc_trng_id_table);
+
+static struct arm_smccc_driver smccc_trng_driver = {
+	.name	  = KBUILD_MODNAME,
+	.probe	  = smccc_trng_probe,
+	.id_table = smccc_trng_id_table,
+};
+module_arm_smccc_driver(smccc_trng_driver);
 
-MODULE_ALIAS("platform:smccc_trng");
 MODULE_AUTHOR("Andre Przywara");
 MODULE_DESCRIPTION("Arm SMCCC TRNG firmware interface support");
 MODULE_LICENSE("GPL");
diff --git a/drivers/firmware/smccc/smccc.c b/drivers/firmware/smccc/smccc.c
index 695c920a8087..6d260354d0f9 100644
--- a/drivers/firmware/smccc/smccc.c
+++ b/drivers/firmware/smccc/smccc.c
@@ -9,7 +9,6 @@
 #include <linux/init.h>
 #include <linux/arm-smccc.h>
 #include <linux/kernel.h>
-#include <linux/platform_device.h>
 #include <linux/arm-smccc-bus.h>
 #include <linux/idr.h>
 #include <linux/slab.h>
@@ -241,14 +240,13 @@ subsys_initcall(arm_smccc_bus_init);
 
 static int __init smccc_devices_init(void)
 {
-	struct platform_device *pdev;
-
 	if (smccc_trng_available) {
-		pdev = platform_device_register_simple("smccc_trng", -1,
-						       NULL, 0);
-		if (IS_ERR(pdev))
-			pr_err("smccc_trng: could not register device: %ld\n",
-			       PTR_ERR(pdev));
+		struct arm_smccc_device *sdev;
+
+		sdev = arm_smccc_device_register("arm-smccc-trng");
+		if (IS_ERR(sdev))
+			pr_err("arm-smccc-trng: could not register device: %ld\n",
+			       PTR_ERR(sdev));
 	}
 
 	return 0;

---

## [4] Aneesh Kumar K.V (Arm) — 2026-05-27
*Subject: [PATCH v6 3/4] firmware: smccc: arm-cca-guest: Bind the TSM provider to an SMCCC device*

The Arm CCA guest TSM provider currently binds through the arm-cca-dev
platform device. Like arm-smccc-trng, this device is not an independent
platform resource; it is a software representation of the RSI firmware
service discovered through SMCCC.

Move RSI discovery into the SMCCC firmware driver. When the SMCCC conduit
is SMC and the RSI ABI version check succeeds, create an arm-rsi-dev SMCCC
device. Convert the Arm CCA guest TSM provider to an SMCCC driver so it
binds to that discovered RSI service and keeps module autoloading through
the SMCCC device id table.

Keep the old arm-cca-dev platform-device registration for now. Userspace
has used that device as a Realm-guest indicator, so removing it is left to
a follow-up patch that adds a replacement sysfs ABI.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rsi.h                  |  2 +-
 arch/arm64/kernel/rsi.c                       |  2 +-
 drivers/firmware/smccc/Makefile               |  4 ++
 drivers/firmware/smccc/rmm.c                  | 25 ++++++++
 drivers/firmware/smccc/rmm.h                  | 17 ++++++
 drivers/firmware/smccc/smccc.c                |  8 +++
 drivers/virt/coco/arm-cca-guest/Kconfig       |  1 +
 drivers/virt/coco/arm-cca-guest/Makefile      |  2 +
 .../{arm-cca-guest.c => arm-cca.c}            | 60 +++++++++----------
 9 files changed, 89 insertions(+), 32 deletions(-)
 create mode 100644 drivers/firmware/smccc/rmm.c
 create mode 100644 drivers/firmware/smccc/rmm.h
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
index 92160f2e57ff..da440f71bb64 100644
--- a/arch/arm64/kernel/rsi.c
+++ b/arch/arm64/kernel/rsi.c
@@ -161,7 +161,7 @@ void __init arm64_rsi_init(void)
 }
 
 static struct platform_device rsi_dev = {
-	.name = RSI_PDEV_NAME,
+	.name = "arm-cca-dev",
 	.id = PLATFORM_DEVID_NONE
 };
 
diff --git a/drivers/firmware/smccc/Makefile b/drivers/firmware/smccc/Makefile
index 40d19144a860..33c850aaff4d 100644
--- a/drivers/firmware/smccc/Makefile
+++ b/drivers/firmware/smccc/Makefile
@@ -2,3 +2,7 @@
 #
 obj-$(CONFIG_HAVE_ARM_SMCCC_DISCOVERY)	+= smccc.o kvm_guest.o
 obj-$(CONFIG_ARM_SMCCC_SOC_ID)	+= soc_id.o
+
+ifeq ($(CONFIG_HAVE_ARM_SMCCC_DISCOVERY),y)
+obj-$(CONFIG_ARM64) += rmm.o
+endif
diff --git a/drivers/firmware/smccc/rmm.c b/drivers/firmware/smccc/rmm.c
new file mode 100644
index 000000000000..d572f47e955c
--- /dev/null
+++ b/drivers/firmware/smccc/rmm.c
@@ -0,0 +1,25 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/*
+ * Copyright (C) 2026 Arm Limited
+ */
+
+#include <linux/arm-smccc-bus.h>
+#include <linux/err.h>
+#include <linux/printk.h>
+
+#include "rmm.h"
+
+void __init register_rsi_device(void)
+{
+	unsigned long ret;
+
+	if (arm_smccc_1_1_get_conduit() != SMCCC_CONDUIT_SMC)
+		return;
+
+	ret = rsi_request_version(RSI_ABI_VERSION, NULL, NULL);
+	if (ret != RSI_SUCCESS)
+		return;
+
+	if (IS_ERR(arm_smccc_device_register(RSI_DEV_NAME)))
+		pr_err("%s: could not register device\n", RSI_DEV_NAME);
+}
diff --git a/drivers/firmware/smccc/rmm.h b/drivers/firmware/smccc/rmm.h
new file mode 100644
index 000000000000..627098e2ae1f
--- /dev/null
+++ b/drivers/firmware/smccc/rmm.h
@@ -0,0 +1,17 @@
+/* SPDX-License-Identifier: GPL-2.0 */
+#ifndef _SMCCC_RMM_H
+#define _SMCCC_RMM_H
+
+#include <linux/init.h>
+
+#ifdef CONFIG_ARM64
+#include <linux/arm-smccc-bus.h>
+#include <asm/rsi_cmds.h>
+void __init register_rsi_device(void);
+#else
+
+static inline void __init register_rsi_device(void)
+{
+}
+#endif
+#endif
diff --git a/drivers/firmware/smccc/smccc.c b/drivers/firmware/smccc/smccc.c
index 6d260354d0f9..888e7f1d6f86 100644
--- a/drivers/firmware/smccc/smccc.c
+++ b/drivers/firmware/smccc/smccc.c
@@ -15,6 +15,8 @@
 
 #include <asm/archrandom.h>
 
+#include "rmm.h"
+
 static u32 smccc_version = ARM_SMCCC_VERSION_1_0;
 static enum arm_smccc_conduit smccc_conduit = SMCCC_CONDUIT_NONE;
 static DEFINE_IDA(arm_smccc_bus_id);
@@ -240,6 +242,12 @@ subsys_initcall(arm_smccc_bus_init);
 
 static int __init smccc_devices_init(void)
 {
+	/*
+	 * Register the RMI and RSI devices only when firmware exposes
+	 * the required SMCCC function IDs at a supported revision.
+	 */
+	register_rsi_device();
+
 	if (smccc_trng_available) {
 		struct arm_smccc_device *sdev;
 
diff --git a/drivers/virt/coco/arm-cca-guest/Kconfig b/drivers/virt/coco/arm-cca-guest/Kconfig
index 3f0f013f03f1..ad7538750c5a 100644
--- a/drivers/virt/coco/arm-cca-guest/Kconfig
+++ b/drivers/virt/coco/arm-cca-guest/Kconfig
@@ -1,6 +1,7 @@
 config ARM_CCA_GUEST
 	tristate "Arm CCA Guest driver"
 	depends on ARM64
+	depends on HAVE_ARM_SMCCC_DISCOVERY
 	select TSM_REPORTS
 	help
 	  The driver provides userspace interface to request and
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
index 66d00b6ceb78..8d5a09bd772a 100644
--- a/drivers/virt/coco/arm-cca-guest/arm-cca-guest.c
+++ b/drivers/virt/coco/arm-cca-guest/arm-cca.c
@@ -4,6 +4,7 @@
  */
 
 #include <linux/arm-smccc.h>
+#include <linux/arm-smccc-bus.h>
 #include <linux/cc_platform.h>
 #include <linux/kernel.h>
 #include <linux/mod_devicetable.h>
@@ -182,52 +183,51 @@ static int arm_cca_report_new(struct tsm_report *report, void *data)
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
+static int cca_tsm_probe(struct arm_smccc_device *sdev)
 {
 	int ret;
 
 	if (!is_realm_world())
 		return -ENODEV;
 
-	ret = tsm_report_register(&arm_cca_tsm_ops, NULL);
-	if (ret < 0)
-		pr_err("Error %d registering with TSM\n", ret);
+	ret = tsm_report_register(&arm_cca_tsm_report_ops, NULL);
+	if (ret < 0) {
+		dev_err_probe(&sdev->dev, ret, "Error registering with TSM\n");
+		return ret;
+	}
 
-	return ret;
-}
-module_init(arm_cca_guest_init);
+	ret = devm_add_action_or_reset(&sdev->dev, unregister_cca_tsm_report,
+				       NULL);
+	if (ret < 0) {
+		dev_err_probe(&sdev->dev, ret, "Error registering devm action\n");
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
+static const struct arm_smccc_device_id cca_tsm_id_table[] = {
+	{ .name = RSI_DEV_NAME },
+	{}
 };
+MODULE_DEVICE_TABLE(arm_smccc, cca_tsm_id_table);
 
-MODULE_DEVICE_TABLE(platform, arm_cca_match);
+static struct arm_smccc_driver cca_tsm_driver = {
+	.name = KBUILD_MODNAME,
+	.probe = cca_tsm_probe,
+	.id_table = cca_tsm_id_table,
+};
+module_arm_smccc_driver(cca_tsm_driver);
 MODULE_AUTHOR("Sami Mujawar <sami.mujawar@arm.com>");
 MODULE_DESCRIPTION("Arm CCA Guest TSM Driver");
 MODULE_LICENSE("GPL");

---

## [5] Aneesh Kumar K.V (Arm) — 2026-05-27
*Subject: [PATCH v6 4/4] coco: guest: arm64: Replace dummy CCA device with sysfs ABI*

The SMCCC firmware driver now creates the arm-smccc platform device and
instantiates the CCA RSI auxiliary devices once the RSI ABI is discovered.
The arm64-specific arm-cca-dev platform device stub is therefore no longer
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
index da440f71bb64..a333029ddf08 100644
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
