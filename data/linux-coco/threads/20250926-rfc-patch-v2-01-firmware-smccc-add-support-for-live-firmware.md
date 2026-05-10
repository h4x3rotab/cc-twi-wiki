---
title: '[RFC PATCH v2 0/1] firmware: smccc: Add support for Live Firmware Activation (LFA)'
date: 2025-09-26
last_reply: 2025-12-23
message_count: 3
participants: ['Salman Nabi', 'Vedashree Vidwans']
---

## [1] Salman Nabi — 2025-09-26

Hi,

This patch addresses some feedback from the previous RFC, and fixes and
improves some shortcomings discovered during internal review:
There is now a new sysfs file to waive the kernel's CPU rendezvous
requirement, if administrators are sure that the firmware's brief downtime
has no effect on the kernel's drivers. Also the firmware images are now
handled in a linked list, as this provides more flexibility for upcoming
changes. For more details, see the original cover letter, the changelog
below and the patch's commit message. We are still looking for feedback,
also from other architectures, on the best userland interface.

=====================================================================

this is a proposal for a driver for the Arm Live Firmware Activation (LFA)
specification[1]. LFA provides an interface to allow "activating" firmware
updates without a reboot.
In contrast to Intel's TDX [2] approach (which seems only concerned about
some confidential computing related firmware blob), and even OCP's
"impactless" updates[3], the Arm approach just lists a number of
"activatable" firmware images, and does not limit their scope. In
particular those updates can (and will) be for firmware bits used by the
application processors (which OCP seems to rule out), including runtime
secure firmware (TF-A/BL31), confidential compute firmware, and
potentially even UEFI runtime firmware.
Initially we have the whole chain demoing the Arm Confidential Computing
firmware (RMM) update, which is conceptually the same as Intel's TDX
proposal.

So our design approach is to create a directory under /sys/firmware, and
just list all images there, as directories named by their GUID.
Then the properties of each image can be queried and the activation
triggered by the sysfs files inside each directory. For details see the
commit message of the patch.
This is admittedly a somewhat raw interface, though even in that form
it's good enough for testing. Eventually I would expect some fwupd
plugin to wrap this nicely for any admins or end users.

The purpose of this RFC is to get some feedback on the feasibility of
this interface, and to understand how this would relate to the other two
approaches (TDX + OCP "impactless" updates).

- Are GUID named directories under /sys/firmware/lfa a good idea?
- Shall all three approaches be unified under a common kernel/userland
  sysfs interface? Or can we live with separate interfaces, given the
  different scopes, and unify this in userland, for instance via fwupd
  plugins?

=====================================================================

v1...v2:
 - added forcce_cpu_rendezvous hook for skipping cpu rendezvous for
   firmware components that supports it.
 - changed the static firmware images array with a dynamic linked list.
 - the activation pending flag is retrieved directly from the lfa agent
   for an up-to-date information.
 - added a mapping of LFA error codes to human-readable strings.
 - kernel error codes changed to more appropriate ones
 - comment fix in call_lfa_activate()
 - the "bitfields" name in variables has been refactored to an
   appropriate "image_flags".
 - change image_flags variable datatype to u32 from an int


Many thanks
Salman Nabi

Salman Nabi (1):
  firmware: smccc: Add support for Live Firmware Activation (LFA)

 drivers/firmware/smccc/Kconfig  |   7 +
 drivers/firmware/smccc/Makefile |   1 +
 drivers/firmware/smccc/lfa_fw.c | 455 ++++++++++++++++++++++++++++++++
 3 files changed, 463 insertions(+)
 create mode 100644 drivers/firmware/smccc/lfa_fw.c

---

## [2] Salman Nabi — 2025-09-26
*Subject: [RFC PATCH v2 1/1] firmware: smccc: Add support for Live Firmware Activation (LFA)*

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
"1" into the "activate" file. The other files reflect the status of the
firmware image, as reported by the LFA agent, and described in the LFA
spec.

"force_cpu_rendezvous" is a boolean flag that controls the CPU rendezvous
behaviour. Normally when activating a firmware the kernel will gather all
CPUs to avoid them calling firmware services during the activation. As
this is disruptive and might not be necessary, depending on the nature of
the firmware, setting this flag to 0 will let the kernel skip the
stop_machine() call for the activation.

==========================================
/sys/firmware/lfa # ls -l . 6c*
.:
total 0
drwxr-xr-x    2 0 0         0 May 30 13:31 47d4086d-4cfe-9846-9b95-2950cbbd5a00
drwxr-xr-x    2 0 0         0 May 30 13:31 6c0762a6-12f2-4b56-92cb-ba8f633606d9
drwxr-xr-x    2 0 0         0 May 30 13:31 d6d0eea7-fcea-d54b-9782-9934f234b6e4

6c0762a6-12f2-4b56-92cb-ba8f633606d9:
total 0
--w-------    1 0        0             4096 May 30 13:31 activate
-r--r--r--    1 0        0             4096 May 30 13:31 activation_capable
-r--r--r--    1 0        0             4096 May 30 13:31 activation_pending
--w-------    1 0        0             4096 May 30 13:31 cancel
-r--r--r--    1 0        0             4096 May 30 13:31 cpu_rendezvous
-rw-r--r--    1 0        0             4096 May 30 13:31 force_cpu_rendezvous
-r--r--r--    1 0        0             4096 May 30 13:31 may_reset_cpu
-r--r--r--    1 0        0             4096 May 30 13:31 name
/sys/firmware/lfa/6c0762a6-12f2-4b56-92cb-ba8f633606d9 # grep . *
grep: activate: Permission denied
activation_capable:1
activation_pending:1
grep: cancel: Permission denied
cpu_rendezvous:1
force_cpu_rendezvous:1
may_reset_cpu:0
name:rmm
/sys/firmware/lfa/6c0762a6-12f2-4b56-92cb-ba8f633606d9 # echo 1 > activate
[ 2825.797871] Arm LFA: firmware activation succeeded.
/sys/firmware/lfa/6c0762a6-12f2-4b56-92cb-ba8f633606d9 #
==========================================

[1] https://developer.arm.com/documentation/den0147/latest/

Signed-off-by: Salman Nabi <salman.nabi@arm.com>
[Andre: add actual activation routine, cleanups]
Signed-off-by: Andre Przywara <andre.przywara@arm.com>
---
 drivers/firmware/smccc/Kconfig  |   7 +
 drivers/firmware/smccc/Makefile |   1 +
 drivers/firmware/smccc/lfa_fw.c | 455 ++++++++++++++++++++++++++++++++
 3 files changed, 463 insertions(+)
 create mode 100644 drivers/firmware/smccc/lfa_fw.c

diff --git a/drivers/firmware/smccc/Kconfig b/drivers/firmware/smccc/Kconfig
index 15e7466179a6..48b98c14f770 100644
--- a/drivers/firmware/smccc/Kconfig
+++ b/drivers/firmware/smccc/Kconfig
@@ -23,3 +23,10 @@ config ARM_SMCCC_SOC_ID
 	help
 	  Include support for the SoC bus on the ARM SMCCC firmware based
 	  platforms providing some sysfs information about the SoC variant.
+
+config ARM_LFA
+	tristate "Arm Live Firmware activation support"
+	depends on HAVE_ARM_SMCCC_DISCOVERY
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
index 000000000000..1f333237271d
--- /dev/null
+++ b/drivers/firmware/smccc/lfa_fw.c
@@ -0,0 +1,455 @@
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
+
+#define LFA_ERROR_STRING(name) \
+	[name] = #name
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
+		.name = "BL31 runtime",
+		.uuid = "47d4086d-4cfe-9846-9b95-2950cbbd5a00",
+	},
+	{
+		.name = "BL33 non-secure payload",
+		.uuid = "d6d0eea7-fcea-d54b-9782-9934f234b6e4",
+	},
+	{
+		.name = "RMM",
+		.uuid = "6c0762a6-12f2-4b56-92cb-ba8f633606d9",
+	},
+};
+
+static struct kobject *lfa_dir;
+
+static int get_nr_lfa_components(void)
+{
+	struct arm_smccc_res res = { 0 };
+
+	arm_smccc_1_1_invoke(LFA_1_0_FN_GET_INFO, 0x0, &res);
+	if (res.a0 != LFA_SUCCESS)
+		return res.a0;
+
+	return res.a1;
+}
+
+static int call_lfa_activate(void *data)
+{
+	struct image_props *attrs = data;
+	struct arm_smccc_res res = { 0 };
+
+	do {
+		/*
+		 * As we do not support updates requiring a CPU reset (yet),
+		 * we pass 0 in x3 and x4, holding the entry point and context
+		 * ID respectively.
+		 * We want to force CPU rendezvous if either cpu_rendezvous or
+		 * cpu_rendezvous_forced is set. The flag value is flipped as
+		 * it is called skip_cpu_rendezvous in the spec.
+		 */
+		arm_smccc_1_1_invoke(LFA_1_0_FN_ACTIVATE, attrs->fw_seq_id,
+			!(attrs->cpu_rendezvous_forced || attrs->cpu_rendezvous),
+			0, 0, &res);
+	} while (res.a0 == 0 && res.a1 == 1);
+
+	return res.a0;
+}
+
+static int activate_fw_image(struct image_props *attrs)
+{
+	struct arm_smccc_res res = { 0 };
+	int ret;
+
+	/*
+	 * LFA_PRIME/ACTIVATE will return 1 in res.a1 if the firmware
+	 * priming/activation is still in progress. In that case
+	 * LFA_PRIME/ACTIVATE will need to be called again.
+	 * res.a1 will become 0 once the prime/activate process completes.
+	 */
+	do {
+		arm_smccc_1_1_invoke(LFA_1_0_FN_PRIME, attrs->fw_seq_id, &res);
+		if (res.a0 != LFA_SUCCESS) {
+			pr_err("LFA_PRIME failed: %s\n",
+				lfa_error_strings[-res.a0]);
+
+			return res.a0;
+		}
+	} while (res.a1 == 1);
+
+	if (attrs->cpu_rendezvous_forced || attrs->cpu_rendezvous)
+		ret = stop_machine(call_lfa_activate, attrs, cpu_online_mask);
+	else
+		ret = call_lfa_activate(attrs);
+
+	return ret;
+}
+
+static void set_image_flags(struct image_props *attrs, int seq_id,
+			    u32 image_flags)
+{
+	attrs->fw_seq_id = seq_id;
+	attrs->activation_capable = !!(image_flags & BIT(0));
+	attrs->activation_pending = !!(image_flags & BIT(1));
+	attrs->may_reset_cpu = !!(image_flags & BIT(2));
+	/* cpu_rendezvous_optional bit has inverse logic in the spec */
+	attrs->cpu_rendezvous = !(image_flags & BIT(3));
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
+	struct arm_smccc_res res = { 0 };
+
+	/*
+	 * Activation pending status can change anytime thus we need to update
+	 * and return its current value
+	 */
+	arm_smccc_1_1_invoke(LFA_1_0_FN_GET_INVENTORY, attrs->fw_seq_id, &res);
+	if (res.a0 == LFA_SUCCESS)
+		attrs->activation_pending = !!(res.a3 & BIT(1));
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
+static ssize_t activate_store(struct kobject *kobj, struct kobj_attribute *attr,
+			      const char *buf, size_t count)
+{
+	struct image_props *attrs = container_of(attr, struct image_props,
+					 image_attrs[LFA_ATTR_ACTIVATE]);
+	int ret;
+
+	if (attrs->may_reset_cpu) {
+		pr_err("Firmware component requires unsupported CPU reset\n");
+
+		return -EINVAL;
+	}
+
+	ret = activate_fw_image(attrs);
+	if (ret) {
+		pr_err("Firmware activation failed: %s\n",
+			lfa_error_strings[-ret]);
+
+		return -ECANCELED;
+	}
+
+	pr_info("Firmware activation succeeded\n");
+
+	/* TODO: refresh image flags here*/
+	return count;
+}
+
+static ssize_t cancel_store(struct kobject *kobj, struct kobj_attribute *attr,
+			    const char *buf, size_t count)
+{
+	struct image_props *attrs = container_of(attr, struct image_props,
+						 image_attrs[LFA_ATTR_CANCEL]);
+	struct arm_smccc_res res = { 0 };
+
+	arm_smccc_1_1_invoke(LFA_1_0_FN_CANCEL, attrs->fw_seq_id, &res);
+
+	/*
+	 * When firmware activation is called with "skip_cpu_rendezvous=1",
+	 * LFA_CANCEL can fail with LFA_BUSY if the activation could not be
+	 * cancelled.
+	 */
+	if (res.a0 == LFA_SUCCESS) {
+		pr_info("Activation cancelled for image %s\n",
+			attrs->image_name);
+	} else {
+		pr_err("Firmware activation could not be cancelled: %s\n",
+		       lfa_error_strings[-res.a0]);
+		return -EINVAL;
+	}
+
+	return count;
+}
+
+static struct kobj_attribute image_attrs_group[LFA_ATTR_NR_IMAGES] = {
+	[LFA_ATTR_NAME]			= __ATTR_RO(name),
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
+	list_for_each_entry_safe(attrs, tmp, &lfa_fw_images, image_node) {
+		kobject_put(attrs->image_dir);
+		list_del(&attrs->image_node);
+		kfree(attrs);
+	}
+}
+
+static int create_fw_inventory(char *fw_uuid, int seq_id, u32 image_flags)
+{
+	const char *image_name = "(unknown)";
+	struct image_props *attrs;
+	int ret;
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
+	set_image_flags(attrs, seq_id, image_flags);
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
+static int create_fw_images_tree(void)
+{
+	struct arm_smccc_res res = { 0 };
+	struct uuid_regs image_uuid;
+	char image_id_str[40];
+	int ret, num_of_components;
+
+	num_of_components = get_nr_lfa_components();
+	for (int i = 0; i < num_of_components; i++) {
+		arm_smccc_1_1_invoke(LFA_1_0_FN_GET_INVENTORY, i, &res);
+		if (res.a0 == LFA_SUCCESS) {
+			image_uuid.uuid_lo = res.a1;
+			image_uuid.uuid_hi = res.a2;
+
+			snprintf(image_id_str, sizeof(image_id_str), "%pUb",
+				 &image_uuid);
+			ret = create_fw_inventory(image_id_str, i, res.a3);
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
+	struct arm_smccc_res res = { 0 };
+	int err;
+
+	arm_smccc_1_1_invoke(LFA_1_0_FN_GET_VERSION, &res);
+	if (res.a0 == -LFA_NOT_SUPPORTED) {
+		pr_err("Arm Live Firmware activation(LFA): no firmware agent found\n");
+		return -ENODEV;
+	}
+
+	pr_info("Arm Live Firmware Activation (LFA): detected v%ld.%ld\n",
+		res.a0 >> 16, res.a0 & 0xffff);
+
+	lfa_dir = kobject_create_and_add("lfa", firmware_kobj);
+	if (!lfa_dir)
+		return -ENOMEM;
+
+	err = create_fw_images_tree();
+	if (err != 0)
+		kobject_put(lfa_dir);
+
+	return err;
+}
+module_init(lfa_init);
+
+static void __exit lfa_exit(void)
+{
+	clean_fw_images_tree();
+	kobject_put(lfa_dir);
+}
+module_exit(lfa_exit);
+
+MODULE_DESCRIPTION("ARM Live Firmware Activation (LFA)");
+MODULE_LICENSE("GPL");

---

## [3] Vedashree Vidwans — 2025-12-23
*Subject: Re: [RFC PATCH v2 0/1] firmware: smccc: Add support for Live Firmware Activation (LFA)*

Hello Salman,

Thank you for the patch. As you might know, I am implementing the
interrupt interface for LFA driver. The LFA usecase I am working
with will validate both interrupt and sysfs interfaces of the LFA
driver. Hence, I would like to extend the driver posted here with
required changes. Please find the extended driver patches posted
at [1].
While working on this code, I realized that LFA driver should
use SMCCC 1.2+ version as per the LFA specification. And I have
included a patch to upgrade SMCCC version in the code.
As the initial LFA driver in this thread isn't merged yet, I would
like to request modification to this original patch based on
a review comment on my patch series.

Could we please come up with a strategy to incorporate the changes?
We are aiming to merge LFA patches to Linux kernel as soon as
possible. Since I am actively working on this driver, I will be
happy to revise the initial patch(with authors intact) and post
a fresh series for review.

Regards,
Veda

[1] https://lore.kernel.org/linux-arm-kernel/20251208221319.1524888-1-vvidwans@nvidia.com/

---
