---
title: 'Arm Live Firmware Activation (LFA) support'
date: 2026-01-19
last_reply: 2026-03-13
message_count: 18
participants: ['Salman Nabi', 'kernel test robot', 'Andre Przywara', 'Vedashree Vidwans', 'Trilok Soni', 'Nirmoy Das']
---

## [1] Salman Nabi — 2026-01-19

Hi reviewers,

(This is a follow-up to the Live Firmware Activation work that was
submitted for RFC [1]).

This patch introduces a Linux kernel driver implementing the Arm Live
Firmware Activation (LFA) specification [2]. LFA enables the activation
of updated firmware components without requiring a system reboot,
reducing downtime in environments such as data centers and hyperscale
systems.

Unlike firmware update process (which may use tools like fwupd), LFA
focuses solely on the activation of an already updated firmware
component, that is pending activation, without a system reboot. This
capability helps maintain service availability and minimize operational
disruption.

Key features of the driver:
* Detects LFA support in system firmware (EL3).
* Lists all firmware components that support live activation.
* Exposes component attributes (e.g., activation capability, and
  activation pending) via sysfs under /sys/firmware/lfa/.
* Provides interfaces to:
  - Trigger activation of an updated firmware component.
  - Cancel an ongoing activation if required.

This work is conceptually similar to Intel’s Platform Firmware Runtime
Update and telemetry (PFRUT) [3] and TDX module updates [4], but
targets Arm platforms. The driver has been used to successfully activate
a Realm Management Monitor (RMM) firmware image in a controlled test
environment. RMM is analogous to Intel’s TDX module.

There is effort on similar work from the OCP [5]. Future work may
include integration with utilities like fwupd to automatically select
the appropriate driver, based on platform architecture, for Live/Runtime
firmware updates.

Note: The ACPI tables are described in the spec. The Device Tree
bindings are currently work-in-progress, and a follow up patch will soon
be submitted that will add the DT bindings to the driver.

Summary of changes since rfc:
- Updated SMCCC version 1.1 to 1.2 per the LFA specification requirement.
- Changed "image_props" array to a linked list to support the dynamic
  removal and addition of firmware images.
- Added code to refresh firmware images following a successful activation.
- Added a work_queue to handle the removal of firmware image attribute
  from it's respective kobject "_store" handle.
- Refactored prime and activate into separate functions.
- Kernel config for LFA now defaults to "y" i.e. included by default.
- Added individual kernel attribute files removal when removing the
  respective kobjects using kobject_put().
- mutex_lock added to activate_fw_image() and prime_fw_image() calls.
- Renamed create_fw_inventory to update_fw_image_node.
- Renamed create_fw_images_tree to update_fw_images_tree.
- Added two more attributes due to specs update from bet0 to bet1:
  current_version: For retrieval of the current firmware's version info.
  pending_version: For retrieval of the pending firmware's version info.
- Minor changes such as, improved firmware image names, and code comments.
- do...while loops refactored to for(;;) loops.

Best regards,
Salman Nabi

[1] https://lore.kernel.org/all/20250625142722.1911172-2-andre.przywara@arm.com/
[2] https://developer.arm.com/documentation/den0147/latest/
[3] https://lore.kernel.org/all/cover.1631025237.git.yu.c.chen@intel.com/
[4] https://lore.kernel.org/all/20250523095322.88774-1-chao.gao@intel.com/
[5] https://www.opencompute.org/documents/hyperscale-cpu-impactless-firmware-updates-requirements-specification-v0-7-9-29-2025-pdf

Salman Nabi (1):
  firmware: smccc: add support for Live Firmware Activation (LFA)

 drivers/firmware/smccc/Kconfig  |   8 +
 drivers/firmware/smccc/Makefile |   1 +
 drivers/firmware/smccc/lfa_fw.c | 668 ++++++++++++++++++++++++++++++++
 3 files changed, 677 insertions(+)
 create mode 100644 drivers/firmware/smccc/lfa_fw.c

---

## [2] Salman Nabi — 2026-01-19
*Subject: [PATCH 1/1] firmware: smccc: add support for Live Firmware Activation (LFA)*

The Arm Live Firmware Activation (LFA) is a specification [1] to describe
activating firmware components without a reboot. Those components
(like TF-A's BL31, EDK-II, TF-RMM, secure paylods) would be updated the
usual way: via fwupd, FF-A or other secure storage methods, or via some
IMPDEF Out-Of-Bound method. The user can then activate this new firmware,
at system runtime, without requiring a reboot.
The specification covers the SMCCC interface to list and query available
components and eventually trigger the activation.

Add a new directory under /sys/firmware to present firmware components
capable of live activation. Each of them is a directory under lfa/,
and is identified via its GUID. The activation will be triggered by echoing
"1" into the "activate" file:
==========================================
/sys/firmware/lfa # ls -l . 6c*
.:
total 0
drwxr-xr-x    2 0 0         0 Jan 19 11:33 47d4086d-4cfe-9846-9b95-2950cbbd5a00
drwxr-xr-x    2 0 0         0 Jan 19 11:33 6c0762a6-12f2-4b56-92cb-ba8f633606d9
drwxr-xr-x    2 0 0         0 Jan 19 11:33 d6d0eea7-fcea-d54b-9782-9934f234b6e4

6c0762a6-12f2-4b56-92cb-ba8f633606d9:
total 0
--w-------    1 0        0             4096 Jan 19 11:33 activate
-r--r--r--    1 0        0             4096 Jan 19 11:33 activation_capable
-r--r--r--    1 0        0             4096 Jan 19 11:33 activation_pending
--w-------    1 0        0             4096 Jan 19 11:33 cancel
-r--r--r--    1 0        0             4096 Jan 19 11:33 cpu_rendezvous
-r--r--r--    1 0        0             4096 Jan 19 11:33 current_version
-rw-r--r--    1 0        0             4096 Jan 19 11:33 force_cpu_rendezvous
-r--r--r--    1 0        0             4096 Jan 19 11:33 may_reset_cpu
-r--r--r--    1 0        0             4096 Jan 19 11:33 name
-r--r--r--    1 0        0             4096 Jan 19 11:33 pending_version
/sys/firmware/lfa/6c0762a6-12f2-4b56-92cb-ba8f633606d9 # grep . *
grep: activate: Permission denied
activation_capable:1
activation_pending:1
grep: cancel: Permission denied
cpu_rendezvous:1
current_version:0.0
force_cpu_rendezvous:1
may_reset_cpu:0
name:TF-RMM
pending_version:0.0
/sys/firmware/lfa/6c0762a6-12f2-4b56-92cb-ba8f633606d9 # echo 1 > activate
[ 2825.797871] Arm LFA: firmware activation succeeded.
/sys/firmware/lfa/6c0762a6-12f2-4b56-92cb-ba8f633606d9 #
==========================================

[1] https://developer.arm.com/documentation/den0147/latest/

Signed-off-by: Salman Nabi <salman.nabi@arm.com>
---
 drivers/firmware/smccc/Kconfig  |   8 +
 drivers/firmware/smccc/Makefile |   1 +
 drivers/firmware/smccc/lfa_fw.c | 668 ++++++++++++++++++++++++++++++++
 3 files changed, 677 insertions(+)
 create mode 100644 drivers/firmware/smccc/lfa_fw.c

diff --git a/drivers/firmware/smccc/Kconfig b/drivers/firmware/smccc/Kconfig
index 15e7466179a6..ff7ca49486b0 100644
--- a/drivers/firmware/smccc/Kconfig
+++ b/drivers/firmware/smccc/Kconfig
@@ -23,3 +23,11 @@ config ARM_SMCCC_SOC_ID
 	help
 	  Include support for the SoC bus on the ARM SMCCC firmware based
 	  platforms providing some sysfs information about the SoC variant.
+
+config ARM_LFA
+	tristate "Arm Live Firmware activation support"
+	depends on HAVE_ARM_SMCCC_DISCOVERY
+	default y
+	help
+	  Include support for triggering Live Firmware Activation, which
+	  allows to upgrade certain firmware components without a reboot.
diff --git a/drivers/firmware/smccc/Makefile b/drivers/firmware/smccc/Makefile
index 40d19144a860..a6dd01558a94 100644
--- a/drivers/firmware/smccc/Makefile
+++ b/drivers/firmware/smccc/Makefile
@@ -2,3 +2,4 @@
 #
 obj-$(CONFIG_HAVE_ARM_SMCCC_DISCOVERY)	+= smccc.o kvm_guest.o
 obj-$(CONFIG_ARM_SMCCC_SOC_ID)	+= soc_id.o
+obj-$(CONFIG_ARM_LFA) += lfa_fw.o
diff --git a/drivers/firmware/smccc/lfa_fw.c b/drivers/firmware/smccc/lfa_fw.c
new file mode 100644
index 000000000000..ce54049b7190
--- /dev/null
+++ b/drivers/firmware/smccc/lfa_fw.c
@@ -0,0 +1,668 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/*
+ * Copyright (C) 2025 Arm Limited
+ */
+
+#include <linux/fs.h>
+#include <linux/init.h>
+#include <linux/kobject.h>
+#include <linux/module.h>
+#include <linux/stop_machine.h>
+#include <linux/string.h>
+#include <linux/sysfs.h>
+#include <linux/arm-smccc.h>
+#include <linux/psci.h>
+#include <uapi/linux/psci.h>
+#include <linux/uuid.h>
+#include <linux/array_size.h>
+#include <linux/list.h>
+#include <linux/mutex.h>
+
+#undef pr_fmt
+#define pr_fmt(fmt) "Arm LFA: " fmt
+
+/* LFA v1.0b0 specification */
+#define LFA_1_0_FN_BASE			0xc40002e0
+#define LFA_1_0_FN(n)			(LFA_1_0_FN_BASE + (n))
+
+#define LFA_1_0_FN_GET_VERSION		LFA_1_0_FN(0)
+#define LFA_1_0_FN_CHECK_FEATURE	LFA_1_0_FN(1)
+#define LFA_1_0_FN_GET_INFO		LFA_1_0_FN(2)
+#define LFA_1_0_FN_GET_INVENTORY	LFA_1_0_FN(3)
+#define LFA_1_0_FN_PRIME		LFA_1_0_FN(4)
+#define LFA_1_0_FN_ACTIVATE		LFA_1_0_FN(5)
+#define LFA_1_0_FN_CANCEL		LFA_1_0_FN(6)
+
+/* CALL_AGAIN flags (returned by SMC) */
+#define LFA_PRIME_CALL_AGAIN		BIT(0)
+#define LFA_ACTIVATE_CALL_AGAIN		BIT(0)
+
+/* LFA return values */
+#define LFA_SUCCESS			0
+#define LFA_NOT_SUPPORTED		1
+#define LFA_BUSY			2
+#define LFA_AUTH_ERROR			3
+#define LFA_NO_MEMORY			4
+#define LFA_CRITICAL_ERROR		5
+#define LFA_DEVICE_ERROR		6
+#define LFA_WRONG_STATE			7
+#define LFA_INVALID_PARAMETERS		8
+#define LFA_COMPONENT_WRONG_STATE	9
+#define LFA_INVALID_ADDRESS		10
+#define LFA_ACTIVATION_FAILED		11
+
+#define LFA_ERROR_STRING(name) \
+	[name] = #name
+
+static const char * const lfa_error_strings[] = {
+	LFA_ERROR_STRING(LFA_SUCCESS),
+	LFA_ERROR_STRING(LFA_NOT_SUPPORTED),
+	LFA_ERROR_STRING(LFA_BUSY),
+	LFA_ERROR_STRING(LFA_AUTH_ERROR),
+	LFA_ERROR_STRING(LFA_NO_MEMORY),
+	LFA_ERROR_STRING(LFA_CRITICAL_ERROR),
+	LFA_ERROR_STRING(LFA_DEVICE_ERROR),
+	LFA_ERROR_STRING(LFA_WRONG_STATE),
+	LFA_ERROR_STRING(LFA_INVALID_PARAMETERS),
+	LFA_ERROR_STRING(LFA_COMPONENT_WRONG_STATE),
+	LFA_ERROR_STRING(LFA_INVALID_ADDRESS),
+	LFA_ERROR_STRING(LFA_ACTIVATION_FAILED)
+};
+
+enum image_attr_names {
+	LFA_ATTR_NAME,
+	LFA_ATTR_CURRENT_VERSION,
+	LFA_ATTR_PENDING_VERSION,
+	LFA_ATTR_ACT_CAPABLE,
+	LFA_ATTR_ACT_PENDING,
+	LFA_ATTR_MAY_RESET_CPU,
+	LFA_ATTR_CPU_RENDEZVOUS,
+	LFA_ATTR_FORCE_CPU_RENDEZVOUS,
+	LFA_ATTR_ACTIVATE,
+	LFA_ATTR_CANCEL,
+	LFA_ATTR_NR_IMAGES
+};
+
+struct image_props {
+	struct list_head image_node;
+	const char *image_name;
+	int fw_seq_id;
+	u64 current_version;
+	u64 pending_version;
+	bool activation_capable;
+	bool activation_pending;
+	bool may_reset_cpu;
+	bool cpu_rendezvous;
+	bool cpu_rendezvous_forced;
+	struct kobject *image_dir;
+	struct kobj_attribute image_attrs[LFA_ATTR_NR_IMAGES];
+};
+static LIST_HEAD(lfa_fw_images);
+
+/* A UUID split over two 64-bit registers */
+struct uuid_regs {
+	u64 uuid_lo;
+	u64 uuid_hi;
+};
+
+static const struct fw_image_uuid {
+	const char *name;
+	const char *uuid;
+} fw_images_uuids[] = {
+	{
+		.name = "TF-A BL31 runtime",
+		.uuid = "47d4086d-4cfe-9846-9b95-2950cbbd5a00",
+	},
+	{
+		.name = "BL33 non-secure payload",
+		.uuid = "d6d0eea7-fcea-d54b-9782-9934f234b6e4",
+	},
+	{
+		.name = "TF-RMM",
+		.uuid = "6c0762a6-12f2-4b56-92cb-ba8f633606d9",
+	},
+};
+
+static struct kobject *lfa_dir;
+static DEFINE_MUTEX(lfa_lock);
+static struct workqueue_struct *fw_images_update_wq;
+static struct work_struct fw_images_update_work;
+
+static int update_fw_images_tree(void);
+
+static void delete_fw_image_node(struct image_props *attrs)
+{
+	int i;
+
+	for (i = 0; i < LFA_ATTR_NR_IMAGES; i++)
+		sysfs_remove_file(attrs->image_dir, &attrs->image_attrs[i].attr);
+
+	kobject_put(attrs->image_dir);
+	list_del(&attrs->image_node);
+	kfree(attrs);
+}
+
+static void remove_invalid_fw_images(struct work_struct *work)
+{
+	struct image_props *attrs, *tmp;
+
+	mutex_lock(&lfa_lock);
+
+	/*
+	 * Remove firmware images including directories that are no longer
+	 * present in the LFA agent after updating the existing ones.
+	 */
+	list_for_each_entry_safe(attrs, tmp, &lfa_fw_images, image_node) {
+		if (attrs->fw_seq_id == -1)
+			delete_fw_image_node(attrs);
+	}
+
+	mutex_unlock(&lfa_lock);
+}
+
+static void set_image_flags(struct image_props *attrs, int seq_id,
+			    u32 image_flags, u64 reg_current_ver,
+			    u64 reg_pending_ver)
+{
+	attrs->fw_seq_id = seq_id;
+	attrs->current_version = reg_current_ver;
+	attrs->pending_version = reg_pending_ver;
+	attrs->activation_capable = !!(image_flags & BIT(0));
+	attrs->activation_pending = !!(image_flags & BIT(1));
+	attrs->may_reset_cpu = !!(image_flags & BIT(2));
+	/* cpu_rendezvous_optional bit has inverse logic in the spec */
+	attrs->cpu_rendezvous = !(image_flags & BIT(3));
+}
+
+static unsigned long get_nr_lfa_components(void)
+{
+	struct arm_smccc_1_2_regs reg = { 0 };
+
+	reg.a0 = LFA_1_0_FN_GET_INFO;
+	reg.a1 = 0; /* lfa_info_selector = 0 */
+
+	arm_smccc_1_2_invoke(&reg, &reg);
+	if (reg.a0 != LFA_SUCCESS)
+		return reg.a0;
+
+	return reg.a1;
+}
+
+static int lfa_cancel(void *data)
+{
+	struct image_props *attrs = data;
+	struct arm_smccc_1_2_regs reg = { 0 };
+
+	reg.a0 = LFA_1_0_FN_CANCEL;
+	reg.a1 = attrs->fw_seq_id;
+	arm_smccc_1_2_invoke(&reg, &reg);
+
+	/*
+	 * When firmware activation is called with "skip_cpu_rendezvous=1",
+	 * LFA_CANCEL can fail with LFA_BUSY if the activation could not be
+	 * cancelled.
+	 */
+	if (reg.a0 == LFA_SUCCESS) {
+		pr_info("Activation cancelled for image %s\n",
+			attrs->image_name);
+	} else {
+		pr_err("Firmware activation could not be cancelled: %s\n",
+		       lfa_error_strings[-reg.a0]);
+		return -EINVAL;
+	}
+
+	return reg.a0;
+}
+
+static int call_lfa_activate(void *data)
+{
+	struct image_props *attrs = data;
+	struct arm_smccc_1_2_regs reg = { 0 };
+
+	reg.a0 = LFA_1_0_FN_ACTIVATE;
+	reg.a1 = attrs->fw_seq_id; /* fw_seq_id under consideration */
+	/*
+	 * As we do not support updates requiring a CPU reset (yet),
+	 * we pass 0 in reg.a3 and reg.a4, holding the entry point and context
+	 * ID respectively.
+	 * cpu_rendezvous_forced is set by the administrator, via sysfs,
+	 * cpu_rendezvous is dictated by each firmware component.
+	 */
+	reg.a2 = !(attrs->cpu_rendezvous_forced || attrs->cpu_rendezvous);
+
+	for (;;) {
+		arm_smccc_1_2_invoke(&reg, &reg);
+
+		if ((long)reg.a0 < 0) {
+			pr_err("ACTIVATE for image %s failed: %s\n",
+				attrs->image_name, lfa_error_strings[-reg.a0]);
+			return reg.a0;
+		}
+		if (!(reg.a1 & LFA_ACTIVATE_CALL_AGAIN))
+			break; /* ACTIVATE successful */
+	}
+
+	return reg.a0;
+}
+
+static int activate_fw_image(struct image_props *attrs)
+{
+	int ret;
+
+	mutex_lock(&lfa_lock);
+	if (attrs->cpu_rendezvous_forced || attrs->cpu_rendezvous)
+		ret = stop_machine(call_lfa_activate, attrs, cpu_online_mask);
+	else
+		ret = call_lfa_activate(attrs);
+
+	if (ret != 0) {
+		mutex_unlock(&lfa_lock);
+		return lfa_cancel(attrs);
+	}
+
+	/*
+	 * Invalidate fw_seq_ids (-1) for all images as the seq_ids and the
+	 * number of firmware images in the LFA agent may change after a
+	 * successful activation attempt. Negate all image flags as well.
+	 */
+	attrs = NULL;
+	list_for_each_entry(attrs, &lfa_fw_images, image_node) {
+		set_image_flags(attrs, -1, 0b1000, 0, 0);
+	}
+
+	update_fw_images_tree();
+
+	/*
+	 * Removing non-valid image directories at the end of an activation.
+	 * We can't remove the sysfs attributes while in the respective
+	 * _store() handler, so have to postpone the list removal to a
+	 * workqueue.
+	 */
+	INIT_WORK(&fw_images_update_work, remove_invalid_fw_images);
+	queue_work(fw_images_update_wq, &fw_images_update_work);
+	mutex_unlock(&lfa_lock);
+
+	return ret;
+}
+
+static int prime_fw_image(struct image_props *attrs)
+{
+	struct arm_smccc_1_2_regs reg = { 0 };
+	int ret;
+
+	mutex_lock(&lfa_lock);
+	/* Avoid SMC calls on invalid firmware images */
+	if (attrs->fw_seq_id == -1) {
+		pr_err("Arm LFA: Invalid firmware sequence id\n");
+		mutex_unlock(&lfa_lock);
+
+		return -ENODEV;
+	}
+
+	if (attrs->may_reset_cpu) {
+		pr_err("CPU reset not supported by kernel driver\n");
+		mutex_unlock(&lfa_lock);
+
+		return -EINVAL;
+	}
+
+	/*
+	 * LFA_PRIME/ACTIVATE will return 1 in reg.a1 if the firmware
+	 * priming/activation is still in progress. In that case
+	 * LFA_PRIME/ACTIVATE will need to be called again.
+	 * reg.a1 will become 0 once the prime/activate process completes.
+	 */
+	reg.a0 = LFA_1_0_FN_PRIME;
+	reg.a1 = attrs->fw_seq_id; /* fw_seq_id under consideration */
+	for (;;) {
+		arm_smccc_1_2_invoke(&reg, &reg);
+
+		if ((long)reg.a0 < 0) {
+			pr_err("LFA_PRIME for image %s failed: %s\n",
+				attrs->image_name, lfa_error_strings[-reg.a0]);
+			mutex_unlock(&lfa_lock);
+
+			return reg.a0;
+		}
+		if (!(reg.a1 & LFA_PRIME_CALL_AGAIN)) {
+			ret = 0;
+			break; /* PRIME successful */
+		}
+	}
+
+	mutex_unlock(&lfa_lock);
+	return ret;
+}
+
+static ssize_t name_show(struct kobject *kobj, struct kobj_attribute *attr,
+			 char *buf)
+{
+	struct image_props *attrs = container_of(attr, struct image_props,
+						 image_attrs[LFA_ATTR_NAME]);
+
+	return sysfs_emit(buf, "%s\n", attrs->image_name);
+}
+
+static ssize_t activation_capable_show(struct kobject *kobj,
+				       struct kobj_attribute *attr, char *buf)
+{
+	struct image_props *attrs = container_of(attr, struct image_props,
+					 image_attrs[LFA_ATTR_ACT_CAPABLE]);
+
+	return sysfs_emit(buf, "%d\n", attrs->activation_capable);
+}
+
+static ssize_t activation_pending_show(struct kobject *kobj,
+				       struct kobj_attribute *attr, char *buf)
+{
+	struct image_props *attrs = container_of(attr, struct image_props,
+					 image_attrs[LFA_ATTR_ACT_PENDING]);
+	struct arm_smccc_1_2_regs reg = { 0 };
+
+	/*
+	 * Activation pending status can change anytime thus we need to update
+	 * and return its current value
+	 */
+	reg.a0 = LFA_1_0_FN_GET_INVENTORY;
+	reg.a1 = attrs->fw_seq_id;
+	arm_smccc_1_2_invoke(&reg, &reg);
+	if (reg.a0 == LFA_SUCCESS)
+		attrs->activation_pending = !!(reg.a3 & BIT(1));
+
+	return sysfs_emit(buf, "%d\n", attrs->activation_pending);
+}
+
+static ssize_t may_reset_cpu_show(struct kobject *kobj,
+				  struct kobj_attribute *attr, char *buf)
+{
+	struct image_props *attrs = container_of(attr, struct image_props,
+					 image_attrs[LFA_ATTR_MAY_RESET_CPU]);
+
+	return sysfs_emit(buf, "%d\n", attrs->may_reset_cpu);
+}
+
+static ssize_t cpu_rendezvous_show(struct kobject *kobj,
+				   struct kobj_attribute *attr, char *buf)
+{
+	struct image_props *attrs = container_of(attr, struct image_props,
+					 image_attrs[LFA_ATTR_CPU_RENDEZVOUS]);
+
+	return sysfs_emit(buf, "%d\n", attrs->cpu_rendezvous);
+}
+
+static ssize_t force_cpu_rendezvous_store(struct kobject *kobj,
+					  struct kobj_attribute *attr,
+					  const char *buf, size_t count)
+{
+	struct image_props *attrs = container_of(attr, struct image_props,
+				image_attrs[LFA_ATTR_FORCE_CPU_RENDEZVOUS]);
+	int ret;
+
+	ret = kstrtobool(buf, &attrs->cpu_rendezvous_forced);
+	if (ret)
+		return ret;
+
+	return count;
+}
+
+static ssize_t force_cpu_rendezvous_show(struct kobject *kobj,
+					 struct kobj_attribute *attr, char *buf)
+{
+	struct image_props *attrs = container_of(attr, struct image_props,
+				image_attrs[LFA_ATTR_FORCE_CPU_RENDEZVOUS]);
+
+	return sysfs_emit(buf, "%d\n", attrs->cpu_rendezvous_forced);
+}
+
+static ssize_t current_version_show(struct kobject *kobj,
+				    struct kobj_attribute *attr, char *buf)
+{
+	struct image_props *attrs = container_of(attr, struct image_props,
+				image_attrs[LFA_ATTR_CURRENT_VERSION]);
+	u32 maj, min;
+
+	maj = attrs->current_version >> 32;
+	min = attrs->current_version & 0xffffffff;
+	return sysfs_emit(buf, "%u.%u\n", maj, min);
+}
+
+static ssize_t pending_version_show(struct kobject *kobj,
+				    struct kobj_attribute *attr, char *buf)
+{
+	struct image_props *attrs = container_of(attr, struct image_props,
+					 image_attrs[LFA_ATTR_ACT_PENDING]);
+	struct arm_smccc_1_2_regs reg = { 0 };
+	u32 maj, min;
+
+	/*
+	 * Similar to activation pending, this value can change following an
+	 * update, we need to retrieve fresh info instead of stale information.
+	 */
+	reg.a0 = LFA_1_0_FN_GET_INVENTORY;
+	reg.a1 = attrs->fw_seq_id;
+	arm_smccc_1_2_invoke(&reg, &reg);
+	if (reg.a0 == LFA_SUCCESS) {
+		if (reg.a5 != 0 && attrs->activation_pending)
+		{
+			attrs->pending_version = reg.a5;
+			maj = reg.a5 >> 32;
+			min = reg.a5 & 0xffffffff;
+		}
+	}
+
+	return sysfs_emit(buf, "%u.%u\n", maj, min);
+}
+
+static ssize_t activate_store(struct kobject *kobj, struct kobj_attribute *attr,
+			      const char *buf, size_t count)
+{
+	struct image_props *attrs = container_of(attr, struct image_props,
+					 image_attrs[LFA_ATTR_ACTIVATE]);
+	int ret;
+
+	ret = prime_fw_image(attrs);
+	if (ret) {
+		pr_err("Firmware prime failed: %s\n",
+			lfa_error_strings[-ret]);
+		return -ECANCELED;
+	}
+
+	ret = activate_fw_image(attrs);
+	if (ret) {
+		pr_err("Firmware activation failed: %s\n",
+			lfa_error_strings[-ret]);
+		return -ECANCELED;
+	}
+
+	pr_info("Firmware activation succeeded\n");
+
+	return count;
+}
+
+static ssize_t cancel_store(struct kobject *kobj, struct kobj_attribute *attr,
+			    const char *buf, size_t count)
+{
+	struct image_props *attrs = container_of(attr, struct image_props,
+						 image_attrs[LFA_ATTR_CANCEL]);
+	int ret;
+
+	ret = lfa_cancel(attrs);
+	if (ret != 0)
+		return ret;
+
+	return count;
+}
+
+static struct kobj_attribute image_attrs_group[LFA_ATTR_NR_IMAGES] = {
+	[LFA_ATTR_NAME]			= __ATTR_RO(name),
+	[LFA_ATTR_CURRENT_VERSION]	= __ATTR_RO(current_version),
+	[LFA_ATTR_PENDING_VERSION]	= __ATTR_RO(pending_version),
+	[LFA_ATTR_ACT_CAPABLE]		= __ATTR_RO(activation_capable),
+	[LFA_ATTR_ACT_PENDING]		= __ATTR_RO(activation_pending),
+	[LFA_ATTR_MAY_RESET_CPU]	= __ATTR_RO(may_reset_cpu),
+	[LFA_ATTR_CPU_RENDEZVOUS]	= __ATTR_RO(cpu_rendezvous),
+	[LFA_ATTR_FORCE_CPU_RENDEZVOUS]	= __ATTR_RW(force_cpu_rendezvous),
+	[LFA_ATTR_ACTIVATE]		= __ATTR_WO(activate),
+	[LFA_ATTR_CANCEL]		= __ATTR_WO(cancel)
+};
+
+static void clean_fw_images_tree(void)
+{
+	struct image_props *attrs, *tmp;
+
+	list_for_each_entry_safe(attrs, tmp, &lfa_fw_images, image_node)
+		delete_fw_image_node(attrs);
+}
+
+static int update_fw_image_node(char *fw_uuid, int seq_id,
+					  u32 image_flags, u64 reg_current_ver,
+					  u64 reg_pending_ver)
+{
+	const char *image_name = "(unknown)";
+	struct image_props *attrs;
+	int ret;
+
+	/*
+	 * If a fw_image is already in the images list then we just update
+	 * its flags and seq_id instead of trying to recreate it.
+	 */
+	list_for_each_entry(attrs, &lfa_fw_images, image_node) {
+		if (!strcmp(attrs->image_dir->name, fw_uuid)) {
+			set_image_flags(attrs, seq_id, image_flags,
+					reg_current_ver, reg_pending_ver);
+			return 0;
+		}
+	}
+
+	attrs = kzalloc(sizeof(*attrs), GFP_KERNEL);
+	if (!attrs)
+		return -ENOMEM;
+
+	for (int i = 0; i < ARRAY_SIZE(fw_images_uuids); i++) {
+		if (!strcmp(fw_images_uuids[i].uuid, fw_uuid))
+			image_name = fw_images_uuids[i].name;
+	}
+
+	attrs->image_dir = kobject_create_and_add(fw_uuid, lfa_dir);
+	if (!attrs->image_dir)
+		return -ENOMEM;
+
+	INIT_LIST_HEAD(&attrs->image_node);
+	attrs->image_name = image_name;
+	attrs->cpu_rendezvous_forced = 1;
+	set_image_flags(attrs, seq_id, image_flags, reg_current_ver,
+			reg_pending_ver);
+
+	/*
+	 * The attributes for each sysfs file are constant (handler functions,
+	 * name and permissions are the same within each directory), but we
+	 * need a per-directory copy regardless, to get a unique handle
+	 * for each directory, so that container_of can do its magic.
+	 * Also this requires an explicit sysfs_attr_init(), since it's a new
+	 * copy, to make LOCKDEP happy.
+	 */
+	memcpy(attrs->image_attrs, image_attrs_group,
+	       sizeof(attrs->image_attrs));
+	for (int i = 0; i < LFA_ATTR_NR_IMAGES; i++) {
+		struct attribute *attr = &attrs->image_attrs[i].attr;
+
+		sysfs_attr_init(attr);
+		ret = sysfs_create_file(attrs->image_dir, attr);
+		if (ret) {
+			pr_err("creating sysfs file for uuid %s: %d\n",
+			       fw_uuid, ret);
+			clean_fw_images_tree();
+
+			return ret;
+		}
+	}
+	list_add(&attrs->image_node, &lfa_fw_images);
+
+	return ret;
+}
+
+static int update_fw_images_tree(void)
+{
+	struct arm_smccc_1_2_regs reg = { 0 };
+	struct uuid_regs image_uuid;
+	char image_id_str[40];
+	int ret, num_of_components;
+
+	num_of_components = get_nr_lfa_components();
+	if (num_of_components <= 0) {
+		pr_err("Error getting number of LFA components\n");
+		return -ENODEV;
+	}
+
+	for (int i = 0; i < num_of_components; i++) {
+		reg.a0 = LFA_1_0_FN_GET_INVENTORY;
+		reg.a1 = i; /* fw_seq_id under consideration */
+		arm_smccc_1_2_invoke(&reg, &reg);
+		if (reg.a0 == LFA_SUCCESS) {
+			image_uuid.uuid_lo = reg.a1;
+			image_uuid.uuid_hi = reg.a2;
+
+			snprintf(image_id_str, sizeof(image_id_str), "%pUb",
+				 &image_uuid);
+			ret = update_fw_image_node(image_id_str, i,
+							reg.a3, reg.a4, reg.a5);
+			if (ret)
+				return ret;
+		}
+	}
+
+	return 0;
+}
+
+static int __init lfa_init(void)
+{
+	struct arm_smccc_1_2_regs reg = { 0 };
+	int err;
+
+	reg.a0 = LFA_1_0_FN_GET_VERSION;
+	arm_smccc_1_2_invoke(&reg, &reg);
+	if (reg.a0 == -LFA_NOT_SUPPORTED) {
+		pr_info("Live Firmware activation: no firmware agent found\n");
+		return -ENODEV;
+	}
+
+	fw_images_update_wq = alloc_workqueue("fw_images_update_wq",
+					     WQ_UNBOUND | WQ_MEM_RECLAIM, 1);
+	if (!fw_images_update_wq) {
+		pr_err("Live Firmware Activation: Failed to allocate workqueue.\n");
+
+		return -ENOMEM;
+	}
+
+	pr_info("Live Firmware Activation: detected v%ld.%ld\n",
+		reg.a0 >> 16, reg.a0 & 0xffff);
+
+	lfa_dir = kobject_create_and_add("lfa", firmware_kobj);
+	if (!lfa_dir)
+		return -ENOMEM;
+
+	mutex_lock(&lfa_lock);
+	err = update_fw_images_tree();
+	if (err != 0)
+		kobject_put(lfa_dir);
+
+	mutex_unlock(&lfa_lock);
+	return err;
+}
+module_init(lfa_init);
+
+static void __exit lfa_exit(void)
+{
+	flush_workqueue(fw_images_update_wq);
+	destroy_workqueue(fw_images_update_wq);
+
+	mutex_lock(&lfa_lock);
+	clean_fw_images_tree();
+	mutex_unlock(&lfa_lock);
+
+	kobject_put(lfa_dir);
+}
+module_exit(lfa_exit);
+
+MODULE_DESCRIPTION("ARM Live Firmware Activation (LFA)");
+MODULE_LICENSE("GPL");

---

## [3] kernel test robot — 2026-01-20
*Subject: Re: [PATCH 1/1] firmware: smccc: add support for Live Firmware
 Activation (LFA)*

Hi Salman,

kernel test robot noticed the following build warnings:

[auto build test WARNING on soc/for-next]
[also build test WARNING on linus/master v6.19-rc6 next-20260116]
[If your patch is applied to the wrong git tree, kindly drop us a note.
And when submitting patch, we suggest to use '--base' as documented in
https://git-scm.com/docs/git-format-patch#_base_tree_information]

url:    https://github.com/intel-lab-lkp/linux/commits/Salman-Nabi/firmware-smccc-add-support-for-Live-Firmware-Activation-LFA/20260119-203221
base:   https://git.kernel.org/pub/scm/linux/kernel/git/soc/soc.git for-next
patch link:    https://lore.kernel.org/r/20260119122729.287522-2-salman.nabi%40arm.com
patch subject: [PATCH 1/1] firmware: smccc: add support for Live Firmware Activation (LFA)
config: arm-sp7021_defconfig (https://download.01.org/0day-ci/archive/20260120/202601200007.GVZIjoCx-lkp@intel.com/config)
compiler: arm-linux-gnueabi-gcc (GCC) 15.2.0
reproduce (this is a W=1 build): (https://download.01.org/0day-ci/archive/20260120/202601200007.GVZIjoCx-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202601200007.GVZIjoCx-lkp@intel.com/

All warnings (new ones prefixed by >>):

   drivers/firmware/smccc/lfa_fw.c: In function 'get_nr_lfa_components':
   drivers/firmware/smccc/lfa_fw.c:179:16: error: variable 'reg' has initializer but incomplete type
     179 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                ^~~~~~~~~~~~~~~~~~
>> drivers/firmware/smccc/lfa_fw.c:179:43: warning: excess elements in struct initializer
     179 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                                           ^
   drivers/firmware/smccc/lfa_fw.c:179:43: note: (near initialization for 'reg')
   drivers/firmware/smccc/lfa_fw.c:179:35: error: storage size of 'reg' isn't known
     179 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                                   ^~~
   drivers/firmware/smccc/lfa_fw.c:184:9: error: implicit declaration of function 'arm_smccc_1_2_invoke'; did you mean 'arm_smccc_1_1_invoke'? [-Wimplicit-function-declaration]
     184 |         arm_smccc_1_2_invoke(&reg, &reg);
         |         ^~~~~~~~~~~~~~~~~~~~
         |         arm_smccc_1_1_invoke
>> drivers/firmware/smccc/lfa_fw.c:179:35: warning: unused variable 'reg' [-Wunused-variable]
     179 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                                   ^~~
   drivers/firmware/smccc/lfa_fw.c: In function 'lfa_cancel':
   drivers/firmware/smccc/lfa_fw.c:194:16: error: variable 'reg' has initializer but incomplete type
     194 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                ^~~~~~~~~~~~~~~~~~
   drivers/firmware/smccc/lfa_fw.c:194:43: warning: excess elements in struct initializer
     194 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                                           ^
   drivers/firmware/smccc/lfa_fw.c:194:43: note: (near initialization for 'reg')
   drivers/firmware/smccc/lfa_fw.c:194:35: error: storage size of 'reg' isn't known
     194 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                                   ^~~
   drivers/firmware/smccc/lfa_fw.c:194:35: warning: unused variable 'reg' [-Wunused-variable]
   drivers/firmware/smccc/lfa_fw.c: In function 'call_lfa_activate':
   drivers/firmware/smccc/lfa_fw.c:220:16: error: variable 'reg' has initializer but incomplete type
     220 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                ^~~~~~~~~~~~~~~~~~
   drivers/firmware/smccc/lfa_fw.c:220:43: warning: excess elements in struct initializer
     220 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                                           ^
   drivers/firmware/smccc/lfa_fw.c:220:43: note: (near initialization for 'reg')
   drivers/firmware/smccc/lfa_fw.c:220:35: error: storage size of 'reg' isn't known
     220 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                                   ^~~
   drivers/firmware/smccc/lfa_fw.c:220:35: warning: unused variable 'reg' [-Wunused-variable]
   drivers/firmware/smccc/lfa_fw.c: In function 'prime_fw_image':
   drivers/firmware/smccc/lfa_fw.c:290:16: error: variable 'reg' has initializer but incomplete type
     290 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                ^~~~~~~~~~~~~~~~~~
   drivers/firmware/smccc/lfa_fw.c:290:43: warning: excess elements in struct initializer
     290 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                                           ^
   drivers/firmware/smccc/lfa_fw.c:290:43: note: (near initialization for 'reg')
   drivers/firmware/smccc/lfa_fw.c:290:35: error: storage size of 'reg' isn't known
     290 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                                   ^~~
   drivers/firmware/smccc/lfa_fw.c:290:35: warning: unused variable 'reg' [-Wunused-variable]
   drivers/firmware/smccc/lfa_fw.c: In function 'activation_pending_show':
   drivers/firmware/smccc/lfa_fw.c:360:16: error: variable 'reg' has initializer but incomplete type
     360 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                ^~~~~~~~~~~~~~~~~~
   drivers/firmware/smccc/lfa_fw.c:360:43: warning: excess elements in struct initializer
     360 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                                           ^
   drivers/firmware/smccc/lfa_fw.c:360:43: note: (near initialization for 'reg')
   drivers/firmware/smccc/lfa_fw.c:360:35: error: storage size of 'reg' isn't known
     360 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                                   ^~~
   drivers/firmware/smccc/lfa_fw.c:360:35: warning: unused variable 'reg' [-Wunused-variable]
   drivers/firmware/smccc/lfa_fw.c: In function 'pending_version_show':
   drivers/firmware/smccc/lfa_fw.c:434:16: error: variable 'reg' has initializer but incomplete type
     434 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                ^~~~~~~~~~~~~~~~~~
   drivers/firmware/smccc/lfa_fw.c:434:43: warning: excess elements in struct initializer
     434 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                                           ^
   drivers/firmware/smccc/lfa_fw.c:434:43: note: (near initialization for 'reg')
   drivers/firmware/smccc/lfa_fw.c:434:35: error: storage size of 'reg' isn't known
     434 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                                   ^~~
   drivers/firmware/smccc/lfa_fw.c:434:35: warning: unused variable 'reg' [-Wunused-variable]
   drivers/firmware/smccc/lfa_fw.c: In function 'update_fw_images_tree':
   drivers/firmware/smccc/lfa_fw.c:586:16: error: variable 'reg' has initializer but incomplete type
     586 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                ^~~~~~~~~~~~~~~~~~
   drivers/firmware/smccc/lfa_fw.c:586:43: warning: excess elements in struct initializer
     586 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                                           ^
   drivers/firmware/smccc/lfa_fw.c:586:43: note: (near initialization for 'reg')
   drivers/firmware/smccc/lfa_fw.c:586:35: error: storage size of 'reg' isn't known
     586 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                                   ^~~
   drivers/firmware/smccc/lfa_fw.c:586:35: warning: unused variable 'reg' [-Wunused-variable]
   drivers/firmware/smccc/lfa_fw.c: In function 'lfa_init':
   drivers/firmware/smccc/lfa_fw.c:619:16: error: variable 'reg' has initializer but incomplete type
     619 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                ^~~~~~~~~~~~~~~~~~
   drivers/firmware/smccc/lfa_fw.c:619:43: warning: excess elements in struct initializer
     619 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                                           ^
   drivers/firmware/smccc/lfa_fw.c:619:43: note: (near initialization for 'reg')
   drivers/firmware/smccc/lfa_fw.c:619:35: error: storage size of 'reg' isn't known
     619 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                                   ^~~
   drivers/firmware/smccc/lfa_fw.c:619:35: warning: unused variable 'reg' [-Wunused-variable]


vim +179 drivers/firmware/smccc/lfa_fw.c

   176	
   177	static unsigned long get_nr_lfa_components(void)
   178	{
 > 179		struct arm_smccc_1_2_regs reg = { 0 };
   180	
   181		reg.a0 = LFA_1_0_FN_GET_INFO;
   182		reg.a1 = 0; /* lfa_info_selector = 0 */
   183	
   184		arm_smccc_1_2_invoke(&reg, &reg);
   185		if (reg.a0 != LFA_SUCCESS)
   186			return reg.a0;
   187	
   188		return reg.a1;
   189	}
   190

---

## [4] Andre Przywara — 2026-01-19
*Subject: Re: [PATCH 1/1] firmware: smccc: add support for Live Firmware
 Activation (LFA)*

Hi,

On 19/01/2026 16:29, kernel test robot wrote:
> Hi Salman,
> 

Ah, yes, arm_smccc_1_2_regs is only defined for arm64. We rely on v1.2, 
and the LFA spec actually means that this means AArch64 only right at 
the beginning (chapter 2).
So we need an additional dependency on ARM64 in the Kconfig entry.

Cheers,
Andre



>       179 |         struct arm_smccc_1_2_regs reg = { 0 };
>           |                                           ^

---

## [5] kernel test robot — 2026-01-20
*Subject: Re: [PATCH 1/1] firmware: smccc: add support for Live Firmware
 Activation (LFA)*

Hi Salman,

kernel test robot noticed the following build errors:

[auto build test ERROR on soc/for-next]
[also build test ERROR on linus/master v6.19-rc6 next-20260116]
[If your patch is applied to the wrong git tree, kindly drop us a note.
And when submitting patch, we suggest to use '--base' as documented in
https://git-scm.com/docs/git-format-patch#_base_tree_information]

url:    https://github.com/intel-lab-lkp/linux/commits/Salman-Nabi/firmware-smccc-add-support-for-Live-Firmware-Activation-LFA/20260119-203221
base:   https://git.kernel.org/pub/scm/linux/kernel/git/soc/soc.git for-next
patch link:    https://lore.kernel.org/r/20260119122729.287522-2-salman.nabi%40arm.com
patch subject: [PATCH 1/1] firmware: smccc: add support for Live Firmware Activation (LFA)
config: arm-sp7021_defconfig (https://download.01.org/0day-ci/archive/20260120/202601200225.cTYuYwRI-lkp@intel.com/config)
compiler: arm-linux-gnueabi-gcc (GCC) 15.2.0
reproduce (this is a W=1 build): (https://download.01.org/0day-ci/archive/20260120/202601200225.cTYuYwRI-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202601200225.cTYuYwRI-lkp@intel.com/

All errors (new ones prefixed by >>):

   drivers/firmware/smccc/lfa_fw.c: In function 'get_nr_lfa_components':
>> drivers/firmware/smccc/lfa_fw.c:179:16: error: variable 'reg' has initializer but incomplete type
     179 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                ^~~~~~~~~~~~~~~~~~
   drivers/firmware/smccc/lfa_fw.c:179:43: warning: excess elements in struct initializer
     179 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                                           ^
   drivers/firmware/smccc/lfa_fw.c:179:43: note: (near initialization for 'reg')
>> drivers/firmware/smccc/lfa_fw.c:179:35: error: storage size of 'reg' isn't known
     179 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                                   ^~~
>> drivers/firmware/smccc/lfa_fw.c:184:9: error: implicit declaration of function 'arm_smccc_1_2_invoke'; did you mean 'arm_smccc_1_1_invoke'? [-Wimplicit-function-declaration]
     184 |         arm_smccc_1_2_invoke(&reg, &reg);
         |         ^~~~~~~~~~~~~~~~~~~~
         |         arm_smccc_1_1_invoke
   drivers/firmware/smccc/lfa_fw.c:179:35: warning: unused variable 'reg' [-Wunused-variable]
     179 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                                   ^~~
   drivers/firmware/smccc/lfa_fw.c: In function 'lfa_cancel':
   drivers/firmware/smccc/lfa_fw.c:194:16: error: variable 'reg' has initializer but incomplete type
     194 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                ^~~~~~~~~~~~~~~~~~
   drivers/firmware/smccc/lfa_fw.c:194:43: warning: excess elements in struct initializer
     194 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                                           ^
   drivers/firmware/smccc/lfa_fw.c:194:43: note: (near initialization for 'reg')
   drivers/firmware/smccc/lfa_fw.c:194:35: error: storage size of 'reg' isn't known
     194 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                                   ^~~
   drivers/firmware/smccc/lfa_fw.c:194:35: warning: unused variable 'reg' [-Wunused-variable]
   drivers/firmware/smccc/lfa_fw.c: In function 'call_lfa_activate':
   drivers/firmware/smccc/lfa_fw.c:220:16: error: variable 'reg' has initializer but incomplete type
     220 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                ^~~~~~~~~~~~~~~~~~
   drivers/firmware/smccc/lfa_fw.c:220:43: warning: excess elements in struct initializer
     220 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                                           ^
   drivers/firmware/smccc/lfa_fw.c:220:43: note: (near initialization for 'reg')
   drivers/firmware/smccc/lfa_fw.c:220:35: error: storage size of 'reg' isn't known
     220 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                                   ^~~
   drivers/firmware/smccc/lfa_fw.c:220:35: warning: unused variable 'reg' [-Wunused-variable]
   drivers/firmware/smccc/lfa_fw.c: In function 'prime_fw_image':
   drivers/firmware/smccc/lfa_fw.c:290:16: error: variable 'reg' has initializer but incomplete type
     290 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                ^~~~~~~~~~~~~~~~~~
   drivers/firmware/smccc/lfa_fw.c:290:43: warning: excess elements in struct initializer
     290 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                                           ^
   drivers/firmware/smccc/lfa_fw.c:290:43: note: (near initialization for 'reg')
   drivers/firmware/smccc/lfa_fw.c:290:35: error: storage size of 'reg' isn't known
     290 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                                   ^~~
   drivers/firmware/smccc/lfa_fw.c:290:35: warning: unused variable 'reg' [-Wunused-variable]
   drivers/firmware/smccc/lfa_fw.c: In function 'activation_pending_show':
   drivers/firmware/smccc/lfa_fw.c:360:16: error: variable 'reg' has initializer but incomplete type
     360 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                ^~~~~~~~~~~~~~~~~~
   drivers/firmware/smccc/lfa_fw.c:360:43: warning: excess elements in struct initializer
     360 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                                           ^
   drivers/firmware/smccc/lfa_fw.c:360:43: note: (near initialization for 'reg')
   drivers/firmware/smccc/lfa_fw.c:360:35: error: storage size of 'reg' isn't known
     360 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                                   ^~~
   drivers/firmware/smccc/lfa_fw.c:360:35: warning: unused variable 'reg' [-Wunused-variable]
   drivers/firmware/smccc/lfa_fw.c: In function 'pending_version_show':
   drivers/firmware/smccc/lfa_fw.c:434:16: error: variable 'reg' has initializer but incomplete type
     434 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                ^~~~~~~~~~~~~~~~~~
   drivers/firmware/smccc/lfa_fw.c:434:43: warning: excess elements in struct initializer
     434 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                                           ^
   drivers/firmware/smccc/lfa_fw.c:434:43: note: (near initialization for 'reg')
   drivers/firmware/smccc/lfa_fw.c:434:35: error: storage size of 'reg' isn't known
     434 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                                   ^~~
   drivers/firmware/smccc/lfa_fw.c:434:35: warning: unused variable 'reg' [-Wunused-variable]
   drivers/firmware/smccc/lfa_fw.c: In function 'update_fw_images_tree':
   drivers/firmware/smccc/lfa_fw.c:586:16: error: variable 'reg' has initializer but incomplete type
     586 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                ^~~~~~~~~~~~~~~~~~
   drivers/firmware/smccc/lfa_fw.c:586:43: warning: excess elements in struct initializer
     586 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                                           ^
   drivers/firmware/smccc/lfa_fw.c:586:43: note: (near initialization for 'reg')
   drivers/firmware/smccc/lfa_fw.c:586:35: error: storage size of 'reg' isn't known
     586 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                                   ^~~
   drivers/firmware/smccc/lfa_fw.c:586:35: warning: unused variable 'reg' [-Wunused-variable]
   drivers/firmware/smccc/lfa_fw.c: In function 'lfa_init':
   drivers/firmware/smccc/lfa_fw.c:619:16: error: variable 'reg' has initializer but incomplete type
     619 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                ^~~~~~~~~~~~~~~~~~
   drivers/firmware/smccc/lfa_fw.c:619:43: warning: excess elements in struct initializer
     619 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                                           ^
   drivers/firmware/smccc/lfa_fw.c:619:43: note: (near initialization for 'reg')
   drivers/firmware/smccc/lfa_fw.c:619:35: error: storage size of 'reg' isn't known
     619 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                                   ^~~
   drivers/firmware/smccc/lfa_fw.c:619:35: warning: unused variable 'reg' [-Wunused-variable]


vim +/reg +179 drivers/firmware/smccc/lfa_fw.c

   176	
   177	static unsigned long get_nr_lfa_components(void)
   178	{
 > 179		struct arm_smccc_1_2_regs reg = { 0 };
   180	
   181		reg.a0 = LFA_1_0_FN_GET_INFO;
   182		reg.a1 = 0; /* lfa_info_selector = 0 */
   183	
 > 184		arm_smccc_1_2_invoke(&reg, &reg);
   185		if (reg.a0 != LFA_SUCCESS)
   186			return reg.a0;
   187	
   188		return reg.a1;
   189	}
   190

---

## [6] kernel test robot — 2026-01-20
*Subject: Re: [PATCH 1/1] firmware: smccc: add support for Live Firmware
 Activation (LFA)*

Hi Salman,

kernel test robot noticed the following build errors:

[auto build test ERROR on soc/for-next]
[also build test ERROR on linus/master v6.19-rc6 next-20260116]
[If your patch is applied to the wrong git tree, kindly drop us a note.
And when submitting patch, we suggest to use '--base' as documented in
https://git-scm.com/docs/git-format-patch#_base_tree_information]

url:    https://github.com/intel-lab-lkp/linux/commits/Salman-Nabi/firmware-smccc-add-support-for-Live-Firmware-Activation-LFA/20260119-203221
base:   https://git.kernel.org/pub/scm/linux/kernel/git/soc/soc.git for-next
patch link:    https://lore.kernel.org/r/20260119122729.287522-2-salman.nabi%40arm.com
patch subject: [PATCH 1/1] firmware: smccc: add support for Live Firmware Activation (LFA)
config: arm-defconfig (https://download.01.org/0day-ci/archive/20260120/202601200543.EKFOBfnW-lkp@intel.com/config)
compiler: clang version 22.0.0git (https://github.com/llvm/llvm-project 9b8addffa70cee5b2acc5454712d9cf78ce45710)
reproduce (this is a W=1 build): (https://download.01.org/0day-ci/archive/20260120/202601200543.EKFOBfnW-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202601200543.EKFOBfnW-lkp@intel.com/

All errors (new ones prefixed by >>):

>> drivers/firmware/smccc/lfa_fw.c:179:28: error: variable has incomplete type 'struct arm_smccc_1_2_regs'
     179 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                                   ^
   drivers/firmware/smccc/lfa_fw.c:179:9: note: forward declaration of 'struct arm_smccc_1_2_regs'
     179 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                ^
>> drivers/firmware/smccc/lfa_fw.c:184:2: error: call to undeclared function 'arm_smccc_1_2_invoke'; ISO C99 and later do not support implicit function declarations [-Wimplicit-function-declaration]
     184 |         arm_smccc_1_2_invoke(&reg, &reg);
         |         ^
   drivers/firmware/smccc/lfa_fw.c:194:28: error: variable has incomplete type 'struct arm_smccc_1_2_regs'
     194 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                                   ^
   drivers/firmware/smccc/lfa_fw.c:194:9: note: forward declaration of 'struct arm_smccc_1_2_regs'
     194 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                ^
   drivers/firmware/smccc/lfa_fw.c:198:2: error: call to undeclared function 'arm_smccc_1_2_invoke'; ISO C99 and later do not support implicit function declarations [-Wimplicit-function-declaration]
     198 |         arm_smccc_1_2_invoke(&reg, &reg);
         |         ^
   drivers/firmware/smccc/lfa_fw.c:220:28: error: variable has incomplete type 'struct arm_smccc_1_2_regs'
     220 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                                   ^
   drivers/firmware/smccc/lfa_fw.c:220:9: note: forward declaration of 'struct arm_smccc_1_2_regs'
     220 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                ^
   drivers/firmware/smccc/lfa_fw.c:234:3: error: call to undeclared function 'arm_smccc_1_2_invoke'; ISO C99 and later do not support implicit function declarations [-Wimplicit-function-declaration]
     234 |                 arm_smccc_1_2_invoke(&reg, &reg);
         |                 ^
   drivers/firmware/smccc/lfa_fw.c:290:28: error: variable has incomplete type 'struct arm_smccc_1_2_regs'
     290 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                                   ^
   drivers/firmware/smccc/lfa_fw.c:290:9: note: forward declaration of 'struct arm_smccc_1_2_regs'
     290 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                ^
   drivers/firmware/smccc/lfa_fw.c:318:3: error: call to undeclared function 'arm_smccc_1_2_invoke'; ISO C99 and later do not support implicit function declarations [-Wimplicit-function-declaration]
     318 |                 arm_smccc_1_2_invoke(&reg, &reg);
         |                 ^
   drivers/firmware/smccc/lfa_fw.c:360:28: error: variable has incomplete type 'struct arm_smccc_1_2_regs'
     360 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                                   ^
   drivers/firmware/smccc/lfa_fw.c:360:9: note: forward declaration of 'struct arm_smccc_1_2_regs'
     360 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                ^
   drivers/firmware/smccc/lfa_fw.c:368:2: error: call to undeclared function 'arm_smccc_1_2_invoke'; ISO C99 and later do not support implicit function declarations [-Wimplicit-function-declaration]
     368 |         arm_smccc_1_2_invoke(&reg, &reg);
         |         ^
   drivers/firmware/smccc/lfa_fw.c:434:28: error: variable has incomplete type 'struct arm_smccc_1_2_regs'
     434 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                                   ^
   drivers/firmware/smccc/lfa_fw.c:434:9: note: forward declaration of 'struct arm_smccc_1_2_regs'
     434 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                ^
   drivers/firmware/smccc/lfa_fw.c:443:2: error: call to undeclared function 'arm_smccc_1_2_invoke'; ISO C99 and later do not support implicit function declarations [-Wimplicit-function-declaration]
     443 |         arm_smccc_1_2_invoke(&reg, &reg);
         |         ^
   drivers/firmware/smccc/lfa_fw.c:586:28: error: variable has incomplete type 'struct arm_smccc_1_2_regs'
     586 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                                   ^
   drivers/firmware/smccc/lfa_fw.c:586:9: note: forward declaration of 'struct arm_smccc_1_2_regs'
     586 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                ^
   drivers/firmware/smccc/lfa_fw.c:600:3: error: call to undeclared function 'arm_smccc_1_2_invoke'; ISO C99 and later do not support implicit function declarations [-Wimplicit-function-declaration]
     600 |                 arm_smccc_1_2_invoke(&reg, &reg);
         |                 ^
   drivers/firmware/smccc/lfa_fw.c:619:28: error: variable has incomplete type 'struct arm_smccc_1_2_regs'
     619 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                                   ^
   drivers/firmware/smccc/lfa_fw.c:619:9: note: forward declaration of 'struct arm_smccc_1_2_regs'
     619 |         struct arm_smccc_1_2_regs reg = { 0 };
         |                ^
   drivers/firmware/smccc/lfa_fw.c:623:2: error: call to undeclared function 'arm_smccc_1_2_invoke'; ISO C99 and later do not support implicit function declarations [-Wimplicit-function-declaration]
     623 |         arm_smccc_1_2_invoke(&reg, &reg);
         |         ^
   16 errors generated.


vim +179 drivers/firmware/smccc/lfa_fw.c

   176	
   177	static unsigned long get_nr_lfa_components(void)
   178	{
 > 179		struct arm_smccc_1_2_regs reg = { 0 };
   180	
   181		reg.a0 = LFA_1_0_FN_GET_INFO;
   182		reg.a1 = 0; /* lfa_info_selector = 0 */
   183	
 > 184		arm_smccc_1_2_invoke(&reg, &reg);
   185		if (reg.a0 != LFA_SUCCESS)
   186			return reg.a0;
   187	
   188		return reg.a1;
   189	}
   190

---

## [7] Vedashree Vidwans — 2026-01-27
*Subject: Re: [PATCH 1/1] firmware: smccc: add support for Live Firmware
 Activation (LFA)*

Hello,

On 1/19/26 04:27, Salman Nabi wrote:
> The Arm Live Firmware Activation (LFA) is a specification [1] to describe
> activating firmware components without a reboot. Those components
The implementation uses same 'struct arm_smccc_1_2_regs reg' as
input and output for arm_smccc_1_2_invoke(). Here, reg.a0 (function ID), 
reg.a1 (fw_seq_id) and reg.a2 (cpu rendezvous) are initialized once 
before the loop and arm_smccc_1_2_invoke() overwrites the whole register 
set on every iteration. That means inputs (a0, a1, a2) can be clobbered 
between loop iterations unless reassigned each time.
Suggestion: Re-initialize input members of reg on each loop iteration or 
use a separate 'struct arm_smccc_1_2_regs' for output to avoid input 
corruption.
> +
> +	return reg.a0;
Similar comment to call_lfa_activate(). Suggestion to either re-assign 
'struct arm_smccc_1_2_regs' input values on each loop iteration or use a 
separate 'struct arm_smccc_1_2_regs' for output to avoid input 
corruption between loop iterations. This matches the intended 
'CALL_AGAIN' protocal while keeping the inputs stable across retries.
> +
> +	mutex_unlock(&lfa_lock);
The introduction of separate 'ret' cariable does not appear necessary 
for functional correctness. The SMCCC status is conveyed via reg.a0 on 
each iteration, so returning reg.a0 should preserve existing behavior.
If 'ret' must be kept, consider initializing it to 0 at declaration 
time. That avoids setting ret = 0 inside 'PRIME successful' path and 
leads to simpler control flow.
> +}
> +
I would recommend using fw_uuid as the image_name when UUID is not
found in fw_images_uuids[], currently the driver assigns 'unknown'
in such case.
There is a valid possibility that platform-specific FW images, not
listed in fw_images_uuids[], are used by LFA agent for live FW
activation. In such scenarios, falling back to 'unknown' would lose
important information especially when errors surface in
call_lfa_activate(). Using UUID directly would indicate which
image failed or behaved unexpectedly.

Thank you,
Veda
> +
> +	attrs->image_dir = kobject_create_and_add(fw_uuid, lfa_dir);

---

## [8] Andre Przywara — 2026-01-29
*Subject: Re: [PATCH 1/1] firmware: smccc: add support for Live Firmware
 Activation (LFA)*

Hi Vedashree,

many thanks for having a look!

On 1/28/26 00:01, Vedashree Vidwans wrote:
> Hello,
> 

[ ... ]

>>   drivers/firmware/smccc/Kconfig  |   8 +
>>   drivers/firmware/smccc/Makefile |   1 +
[ ... ]
>> diff --git a/drivers/firmware/smccc/lfa_fw.c b/drivers/firmware/smccc/ 
>> lfa_fw.c

[ ... ]

>> +
>> +static int call_lfa_activate(void *data)

Ah, that's a good point and indeed a bug, thanks for spotting this! Will 
fix it.

>> +
>> +    return reg.a0;

Indeed, good catch.

>> +
>> +    mutex_unlock(&lfa_lock);

Right, looks like a leftover from a previous version, it's indeed not 
needed.

>> +}
>> +

Well, I think if you want to identify an image clearly, you always have 
to use the UUID, as shown by the directory name. The "name" sysfs file 
is there just for convenience, to make this easier for *users* when 
dealing with well-known firmware image. As you rightly said, we can 
never guarantee that the kernel knows a certain UUID, and it wouldn't be 
necessary for proper operation at all.
So I was expecting this name to be only used by reporting scripts or 
such. But indeed some "unknown" string is a bit fragile as a placeholder 
name, I was wondering if we should just provide an empty string in this 
case? This would allow scripts to detect this special case reliably and 
provide their own rendering then.
Does this make sense?

Cheers,
Andre

> Thank you,
> Veda

---

## [9] Vedashree Vidwans — 2026-01-30
*Subject: Re: [PATCH 1/1] firmware: smccc: add support for Live Firmware
 Activation (LFA)*

Hi Andre,

On 1/29/26 09:26, Andre Przywara wrote:
> Hi Vedashree,
> 
Thank you for teh clarification, this helps. I agree that UUID is the 
canonical identifier and that 'name' sysfs file is mainly for user 
convenience.
One concern I have is around error reporting. For example, if 
call_lfa_activate() fails, the kernel prints:
ACTIVATE for image <name_string> failed: LFA_BUSY

If the 'name_string' is "unknown" or an empty string, the error message 
doesn't indicate which firmware component failed activation, especially 
on system with multiple LFA-capable FW images.
In such cases, having meaningful fallback identifier is helpful for 
debugging. Using UUID in the error log would help identify which FW 
image encountered the failure. This avoids ambiguity and makes error 
triage much easier, especially when platform-specific firmware images 
are not listed in fw_images_uuids[] but are still valid LFA components.
So eitehr of the following would solve the issue:
1. Use fw_uuid as the fallback image_name
2. Update error print in call_lfa_activate() and prime_fw_image() to use 
UUID instead of image_name.

Best,
Veda
> 
> Cheers,

---

## [10] Andre Przywara — 2026-01-30
*Subject: Re: [PATCH 1/1] firmware: smccc: add support for Live Firmware
 Activation (LFA)*

Hi,

On 1/30/26 20:29, Vedashree Vidwans wrote:
> Hi Andre,
> 

[ .... ]
>>>> +
>>>> +    for (int i = 0; i < ARRAY_SIZE(fw_images_uuids); i++) {

Yes, that's a good point.

> In such cases, having meaningful fallback identifier is helpful for 
> debugging. Using UUID in the error log would help identify which FW 

I'd say number 2 is better. And if we leave the name char* as NULL or an 
empty string, then this is also easy to detect in the code, and we can 
print the UUID instead. If we do this more than once, then this could be 
nicely hidden in a function.

Thanks,
Andre


> Best,
> Veda

---

## [11] Trilok Soni — 2026-01-30
*Subject: Re: [PATCH 1/1] firmware: smccc: add support for Live Firmware
 Activation (LFA)*

On 1/19/2026 4:27 AM, Salman Nabi wrote:
> The Arm Live Firmware Activation (LFA) is a specification [1] to describe
> activating firmware components without a reboot. Those components

Can you please explain or add a note on why we don't have name of the firmware
as the directory name and why you have selected GUID as top-level
directory name? 

---Trilok Soni

---

## [12] Salman Nabi — 2026-02-02
*Subject: Re: [PATCH 1/1] firmware: smccc: add support for Live Firmware
 Activation (LFA)*

Hi Trilok,

On 1/31/26 01:35, Trilok Soni wrote:
> On 1/19/2026 4:27 AM, Salman Nabi wrote:
>> The Arm Live Firmware Activation (LFA) is a specification [1] to describe


We obtain the GUIDs of firmware components from the LFA agent in TF-A, which does not provide their names. For convenience, we have added a C structure in the driver to associate each firmware GUID with its corresponding name. Because new firmware components may be supported in the LFA agent before their GUID-to-name mapping is added to the driver, we avoid using the firmware name as the directory (kobject) name.

Additionally, sysfs requires directory names to be unique among siblings. Since GUIDs are inherently unique, they provide a convenient, collision-free choice for directory names.


>
> ---Trilok Soni


Many thanks,

Salman

---

## [13] Trilok Soni — 2026-02-05
*Subject: Re: [PATCH 1/1] firmware: smccc: add support for Live Firmware
 Activation (LFA)*

On 2/2/2026 7:52 AM, Salman Nabi wrote:
> Hi Trilok,
> 

s/paylods/payloads

>>> usual way: via fwupd, FF-A or other secure storage methods, or via some
>>> IMPDEF Out-Of-Bound method. The user can then activate this new firmware,


Thank you for the explanation. Please add these details in the commit text. 

---Trilok Soni

---

## [14] Vedashree Vidwans — 2026-02-10
*Subject: Re: [PATCH 1/1] firmware: smccc: add support for Live Firmware
 Activation (LFA)*

Hello,

I have tested this change on Nvidia server platform using Linux kernel 
6.16. My testing was done on the final integrated version, which 
includes a platform driver interface built on top of this patch. I will 
be posting the platform driver patch to LKML separately.
The final driver has been validated on target platform, except for the 
sysfs interface which was not excercised during testing.

Tested-by: Vedashree Vidwans <vvidwans@nvidia.com>

Best,
Veda

On 1/19/26 04:27, Salman Nabi wrote:
> The Arm Live Firmware Activation (LFA) is a specification [1] to describe
> activating firmware components without a reboot. Those components

---

## [15] Andre Przywara — 2026-02-20
*Subject: Re: [PATCH 1/1] firmware: smccc: add support for Live Firmware
 Activation (LFA)*

On Mon, 19 Jan 2026 12:27:29 +0000
Salman Nabi <salman.nabi@arm.com> wrote:

Hey,

for the records: while working on improving the patch and during internal
review, we found some bugs and issues in there. I will mark them below for
the benefit of others. I will send a v2 after -rc1, with those things
fixed and some improvements, and will include Vedashree's patches, so
that we have everything in one series.

> The Arm Live Firmware Activation (LFA) is a specification [1] to describe
> activating firmware components without a reboot. Those components

As the kernel test robot correctly pointed out, this only works on ARM64.
SMCCC v1.2 is only defined for AArch64, and the LFA spec documents
actually explicitly mentions AArch64-only at the beginning.

> +	default y
> +	help

This misses <linux/workqueue.h>. We get it via other includes, but better
list it here explicitly.

> +
> +#undef pr_fmt

We should not let an externally provided value (the return value in a0) to
index an array. Future (or rogue?) versions of an LFA agent could use
higher error numbers, so the value must be checked before being used as an
index.

> +			return reg.a0;
> +		}

This should be LFA_ATTR_PENDING_VERSION as the index.

> +	struct arm_smccc_1_2_regs reg = { 0 };
> +	u32 maj, min;

This leaves maj and min uninitialised, if either the call failed or the
image is not pending or doesn't provide a new version.
Could be fixed by calling sysfs_emit() in the "if" clause, then returning,
and outputting some fallback version number otherwise.

> +
> +	return sysfs_emit(buf, "%u.%u\n", maj, min);

that leaks attrs, allocated above

> +
> +	INIT_LIST_HEAD(&attrs->image_node);

That leaks the workqueue created above.

> +
> +	mutex_lock(&lfa_lock);

... and also here.

Cheers,
Andre

> +
> +	mutex_unlock(&lfa_lock);

---

## [16] Trilok Soni — 2026-02-20
*Subject: Re: [PATCH 1/1] firmware: smccc: add support for Live Firmware
 Activation (LFA)*

On 2/20/2026 9:39 AM, Andre Przywara wrote:
> On Mon, 19 Jan 2026 12:27:29 +0000
> Salman Nabi <salman.nabi@arm.com> wrote:


Thank you for the update. How to test these patches outside of NVIDIA devices?
Is it possible to test them on the QEMU or FVP? Any instructions on doing
these tests will be helpful w/ the virtual platforms. 

---Trilok Soni

---

## [17] Nirmoy Das — 2026-03-13
*Subject: Re: [PATCH 1/1] firmware: smccc: add support for Live Firmware
 Activation (LFA)*

Hi Salman and Andre,


We found an bug while testing LFA. See below:

On 19.01.26 14:27, Salman Nabi wrote:
> The Arm Live Firmware Activation (LFA) is a specification [1] to describe
> activating firmware components without a reboot. Those components


This can get invoke multiple times so re-initializing a work item that 
may already be queued or running

is unsafe. This should be moved to lfa_init() so it is only called once. 
I suggest:

diff --git a/drivers/firmware/smccc/lfa_fw.c 
b/drivers/firmware/smccc/lfa_fw.c
index 90727a66e49a5..135358113104c 100644
--- a/drivers/firmware/smccc/lfa_fw.c
+++ b/drivers/firmware/smccc/lfa_fw.c
@@ -653,7 +653,6 @@ static int update_fw_images_tree(void)
          * _store() handler, so have to postpone the list removal to a
          * workqueue.
          */
-       INIT_WORK(&fw_images_update_work, remove_invalid_fw_images);
         queue_work(fw_images_update_wq, &fw_images_update_work);

         return 0;
@@ -680,7 +679,7 @@ static void lfa_notify_handler(acpi_handle handle, 
u32 event, void *data)
          * of all activable and pending images.
          */
         do {
-               /* Reset activable image flag */
+               flush_workqueue(fw_images_update_wq);
                 found_activable_image = false;
                 list_for_each_entry(attrs, &lfa_fw_images, image_node) {
                         if (attrs->fw_seq_id == -1)
@@ -782,6 +781,8 @@ static int __init lfa_init(void)
                 return -ENOMEM;
         }

+       INIT_WORK(&fw_images_update_work, remove_invalid_fw_images);
+
         pr_info("Live Firmware Activation: detected v%ld.%ld\n",
                 reg.a0 >> 16, reg.a0 & 0xffff);


Regards,

Nirmoy

> +	queue_work(fw_images_update_wq, &fw_images_update_work);
> +	mutex_unlock(&lfa_lock);

---

## [18] Andre Przywara — 2026-03-13
*Subject: Re: [PATCH 1/1] firmware: smccc: add support for Live Firmware
 Activation (LFA)*

Hi Nirmoy,

On 3/13/26 10:46, Nirmoy Das wrote:
> Hi Salman and Andre,
> 

[ .... ]

>> +
>> +    update_fw_images_tree();

Ah, good point, thanks for spotting and reporting. Will fold this into 
the next post!

Cheers,
Andre

> 
> diff --git a/drivers/firmware/smccc/lfa_fw.c b/drivers/firmware/smccc/

---
