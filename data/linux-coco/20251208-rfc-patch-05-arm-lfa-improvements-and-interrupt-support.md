---
title: '[RFC PATCH 0/5] Arm LFA: Improvements and interrupt support'
date: 2025-12-08
last_reply: 2026-01-20
message_count: 22
participants: ['Vedashree Vidwans', 'Sudeep Holla', 'Matt Ochs', 'Andre Przywara', 'Salman Nabi']
---

## [1] Vedashree Vidwans — 2025-12-08

Hello,

The patches update the proposed Arm Live Firmware Activation (LFA)
kernel driver [1] to incorporate review feedback [2] and refine the
activation flow while remaining aligned with the LFA specification
DEN0147 [3] and the SMCCC 1.2 calling convention. The series keeps
the existing functionality but restructures and extends it to improve
robustness, reviewability, and future extensibility.​

The SMCCC usage in the driver is updated to consistently use the
SMCCC 1.2 register-based calling convention, consolidating arguments
and results into a single struct to reduce stack usage and simplify
the SMC interface. The patches also split the original changes into
focused pieces and document the device node bindings in the commit
messages, making it easier to follow and validate the implementation
against the specification.​

The kernel driver is registered as a platform driver in accordence to
the LFA device defined by the specification [3]. The driver now extends
interface for interrupt-based enablement of LFA. During LFA, the
interrupt
thread refreshes firmware component details after each activation step
and iterates over all activable components until no further activation
is pending, matching the spec’s allowance for component detail changes
after activation. This ensures that sysfs exposure of LFA components
remains consistent with the authoritative information provided by the
secure firmware.​

The handling of CPU rendezvous is adjusted so that the kernel now
honors the rendezvous policy chosen by the firmware, instead of
unconditionally forcing a rendezvous. This reflects experience with
existing firmware deployments where mandatory rendezvous is not
required, while still allowing the firmware to request it when
needed.​

Thank you,
Veda

[1] https://lore.kernel.org/lkml/20250926123145.268728-1-salman.nabi@arm.com/
[2] https://lkml.org/lkml/2025/10/8/980
[3] https://developer.arm.com/documentation/den0147/latest/

Vedashree Vidwans (5):
  firmware: smccc: LFA: use smcc 1.2
  firmware: smccc: LFA: refactor
  firmware: smccc: add timeout, touch wdt
  firmware: smccc: register as platform driver
  firmware: smccc: lfa: refresh fw details

 drivers/firmware/smccc/Kconfig  |   3 +-
 drivers/firmware/smccc/lfa_fw.c | 478 +++++++++++++++++++++++++-------
 2 files changed, 380 insertions(+), 101 deletions(-)

---

## [2] Vedashree Vidwans — 2025-12-08
*Subject: [RFC PATCH 1/5] firmware: smccc: LFA: use smcc 1.2*

Update driver to use SMCCC 1.2+ version as mentioned in the LFA spec.

Signed-off-by: Vedashree Vidwans <vvidwans@nvidia.com>
---
 drivers/firmware/smccc/lfa_fw.c | 102 ++++++++++++++++++++------------
 1 file changed, 65 insertions(+), 37 deletions(-)

diff --git a/drivers/firmware/smccc/lfa_fw.c b/drivers/firmware/smccc/lfa_fw.c
index 1f333237271d..bdde14b66606 100644
--- a/drivers/firmware/smccc/lfa_fw.c
+++ b/drivers/firmware/smccc/lfa_fw.c
@@ -117,32 +117,38 @@ static struct kobject *lfa_dir;
 
 static int get_nr_lfa_components(void)
 {
-	struct arm_smccc_res res = { 0 };
+	struct arm_smccc_1_2_regs reg = { 0 };
 
-	arm_smccc_1_1_invoke(LFA_1_0_FN_GET_INFO, 0x0, &res);
-	if (res.a0 != LFA_SUCCESS)
-		return res.a0;
+	reg.a0 = LFA_1_0_FN_GET_INFO;
+	reg.a1 = 0; /* lfa_info_selector = 0 */
 
-	return res.a1;
+	arm_smccc_1_2_invoke(&reg, &reg);
+	if (reg.a0 != LFA_SUCCESS)
+		return reg.a0;
+
+	return reg.a1;
 }
 
 static int call_lfa_activate(void *data)
 {
 	struct image_props *attrs = data;
-	struct arm_smccc_res res = { 0 };
+	struct arm_smccc_1_2_regs args = { 0 };
+	struct arm_smccc_1_2_regs res = { 0 };
+
+	args.a0 = LFA_1_0_FN_ACTIVATE;
+	args.a1 = attrs->fw_seq_id; /* fw_seq_id under consideration */
+	/*
+	 * As we do not support updates requiring a CPU reset (yet),
+	 * we pass 0 in args.a3 and args.a4, holding the entry point and context
+	 * ID respectively.
+	 * We want to force CPU rendezvous if either cpu_rendezvous or
+	 * cpu_rendezvous_forced is set. The flag value is flipped as
+	 * it is called skip_cpu_rendezvous in the spec.
+	 */
+	args.a2 = !(attrs->cpu_rendezvous_forced || attrs->cpu_rendezvous);
 
 	do {
-		/*
-		 * As we do not support updates requiring a CPU reset (yet),
-		 * we pass 0 in x3 and x4, holding the entry point and context
-		 * ID respectively.
-		 * We want to force CPU rendezvous if either cpu_rendezvous or
-		 * cpu_rendezvous_forced is set. The flag value is flipped as
-		 * it is called skip_cpu_rendezvous in the spec.
-		 */
-		arm_smccc_1_1_invoke(LFA_1_0_FN_ACTIVATE, attrs->fw_seq_id,
-			!(attrs->cpu_rendezvous_forced || attrs->cpu_rendezvous),
-			0, 0, &res);
+		arm_smccc_1_2_invoke(&args, &res);
 	} while (res.a0 == 0 && res.a1 == 1);
 
 	return res.a0;
@@ -150,7 +156,8 @@ static int call_lfa_activate(void *data)
 
 static int activate_fw_image(struct image_props *attrs)
 {
-	struct arm_smccc_res res = { 0 };
+	struct arm_smccc_1_2_regs args = { 0 };
+	struct arm_smccc_1_2_regs res = { 0 };
 	int ret;
 
 	/*
@@ -159,8 +166,10 @@ static int activate_fw_image(struct image_props *attrs)
 	 * LFA_PRIME/ACTIVATE will need to be called again.
 	 * res.a1 will become 0 once the prime/activate process completes.
 	 */
+	args.a0 = LFA_1_0_FN_PRIME;
+	args.a1 = attrs->fw_seq_id; /* fw_seq_id under consideration */
 	do {
-		arm_smccc_1_1_invoke(LFA_1_0_FN_PRIME, attrs->fw_seq_id, &res);
+		arm_smccc_1_2_invoke(&args, &res);
 		if (res.a0 != LFA_SUCCESS) {
 			pr_err("LFA_PRIME failed: %s\n",
 				lfa_error_strings[-res.a0]);
@@ -211,15 +220,17 @@ static ssize_t activation_pending_show(struct kobject *kobj,
 {
 	struct image_props *attrs = container_of(attr, struct image_props,
 					 image_attrs[LFA_ATTR_ACT_PENDING]);
-	struct arm_smccc_res res = { 0 };
+	struct arm_smccc_1_2_regs reg = { 0 };
 
 	/*
 	 * Activation pending status can change anytime thus we need to update
 	 * and return its current value
 	 */
-	arm_smccc_1_1_invoke(LFA_1_0_FN_GET_INVENTORY, attrs->fw_seq_id, &res);
-	if (res.a0 == LFA_SUCCESS)
-		attrs->activation_pending = !!(res.a3 & BIT(1));
+	reg.a0 = LFA_1_0_FN_GET_INVENTORY;
+	reg.a1 = attrs->fw_seq_id;
+	arm_smccc_1_2_invoke(&reg, &reg);
+	if (reg.a0 == LFA_SUCCESS)
+		attrs->activation_pending = !!(reg.a3 & BIT(1));
 
 	return sysfs_emit(buf, "%d\n", attrs->activation_pending);
 }
@@ -298,21 +309,23 @@ static ssize_t cancel_store(struct kobject *kobj, struct kobj_attribute *attr,
 {
 	struct image_props *attrs = container_of(attr, struct image_props,
 						 image_attrs[LFA_ATTR_CANCEL]);
-	struct arm_smccc_res res = { 0 };
+	struct arm_smccc_1_2_regs reg = { 0 };
 
-	arm_smccc_1_1_invoke(LFA_1_0_FN_CANCEL, attrs->fw_seq_id, &res);
+	reg.a0 = LFA_1_0_FN_CANCEL;
+	reg.a1 = attrs->fw_seq_id;
+	arm_smccc_1_2_invoke(&reg, &reg);
 
 	/*
 	 * When firmware activation is called with "skip_cpu_rendezvous=1",
 	 * LFA_CANCEL can fail with LFA_BUSY if the activation could not be
 	 * cancelled.
 	 */
-	if (res.a0 == LFA_SUCCESS) {
+	if (reg.a0 == LFA_SUCCESS) {
 		pr_info("Activation cancelled for image %s\n",
 			attrs->image_name);
 	} else {
 		pr_err("Firmware activation could not be cancelled: %s\n",
-		       lfa_error_strings[-res.a0]);
+		       lfa_error_strings[-reg.a0]);
 		return -EINVAL;
 	}
 
@@ -395,21 +408,24 @@ static int create_fw_inventory(char *fw_uuid, int seq_id, u32 image_flags)
 
 static int create_fw_images_tree(void)
 {
-	struct arm_smccc_res res = { 0 };
+	struct arm_smccc_1_2_regs reg = { 0 };
 	struct uuid_regs image_uuid;
 	char image_id_str[40];
 	int ret, num_of_components;
 
 	num_of_components = get_nr_lfa_components();
+
 	for (int i = 0; i < num_of_components; i++) {
-		arm_smccc_1_1_invoke(LFA_1_0_FN_GET_INVENTORY, i, &res);
-		if (res.a0 == LFA_SUCCESS) {
-			image_uuid.uuid_lo = res.a1;
-			image_uuid.uuid_hi = res.a2;
+		reg.a0 = LFA_1_0_FN_GET_INVENTORY;
+		reg.a1 = i; /* fw_seq_id under consideration */
+		arm_smccc_1_2_invoke(&reg, &reg);
+		if (reg.a0 == LFA_SUCCESS) {
+			image_uuid.uuid_lo = reg.a1;
+			image_uuid.uuid_hi = reg.a2;
 
 			snprintf(image_id_str, sizeof(image_id_str), "%pUb",
 				 &image_uuid);
-			ret = create_fw_inventory(image_id_str, i, res.a3);
+			ret = create_fw_inventory(image_id_str, i, reg.a3);
 			if (ret)
 				return ret;
 		}
@@ -420,17 +436,29 @@ static int create_fw_images_tree(void)
 
 static int __init lfa_init(void)
 {
-	struct arm_smccc_res res = { 0 };
+	struct arm_smccc_1_2_regs reg = { 0 };
 	int err;
 
-	arm_smccc_1_1_invoke(LFA_1_0_FN_GET_VERSION, &res);
-	if (res.a0 == -LFA_NOT_SUPPORTED) {
+	/* LFA requires SMCCC version >= 1.2 */
+	if (arm_smccc_get_version() < ARM_SMCCC_VERSION_1_2) {
+		pr_err("Not supported with SMCCC version %u", arm_smccc_get_version());
+		return -ENODEV;
+	}
+
+	if (arm_smccc_1_1_get_conduit() == SMCCC_CONDUIT_NONE) {
+		pr_err("Invalid SMCCC conduit");
+		return -ENODEV;
+	}
+
+	reg.a0 = LFA_1_0_FN_GET_VERSION;
+	arm_smccc_1_2_invoke(&reg, &reg);
+	if (reg.a0 == -LFA_NOT_SUPPORTED) {
 		pr_err("Arm Live Firmware activation(LFA): no firmware agent found\n");
 		return -ENODEV;
 	}
 
 	pr_info("Arm Live Firmware Activation (LFA): detected v%ld.%ld\n",
-		res.a0 >> 16, res.a0 & 0xffff);
+		reg.a0 >> 16, reg.a0 & 0xffff);
 
 	lfa_dir = kobject_create_and_add("lfa", firmware_kobj);
 	if (!lfa_dir)

---

## [3] Vedashree Vidwans — 2025-12-08
*Subject: [RFC PATCH 2/5] firmware: smccc: LFA: refactor*

- Refactor LFA CANCEL logic into independent lfa_cancel() function.
- Use FW UUID as image_name for images not known by the driver.
- Move may_reset_cpu check to activate_fw_image(). This keeps all the
functionality within a function.

Signed-off-by: Vedashree Vidwans <vvidwans@nvidia.com>
---
 drivers/firmware/smccc/lfa_fw.c | 64 ++++++++++++++++++++-------------
 1 file changed, 40 insertions(+), 24 deletions(-)

diff --git a/drivers/firmware/smccc/lfa_fw.c b/drivers/firmware/smccc/lfa_fw.c
index bdde14b66606..df8b65324413 100644
--- a/drivers/firmware/smccc/lfa_fw.c
+++ b/drivers/firmware/smccc/lfa_fw.c
@@ -129,6 +129,31 @@ static int get_nr_lfa_components(void)
 	return reg.a1;
 }
 
+static int lfa_cancel(struct image_props *attrs)
+{
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
 static int call_lfa_activate(void *data)
 {
 	struct image_props *attrs = data;
@@ -160,6 +185,11 @@ static int activate_fw_image(struct image_props *attrs)
 	struct arm_smccc_1_2_regs res = { 0 };
 	int ret;
 
+	if (attrs->may_reset_cpu) {
+		pr_err("CPU reset not supported by kernel driver\n");
+		return -EINVAL;
+	}
+
 	/*
 	 * LFA_PRIME/ACTIVATE will return 1 in res.a1 if the firmware
 	 * priming/activation is still in progress. In that case
@@ -284,12 +314,6 @@ static ssize_t activate_store(struct kobject *kobj, struct kobj_attribute *attr,
 					 image_attrs[LFA_ATTR_ACTIVATE]);
 	int ret;
 
-	if (attrs->may_reset_cpu) {
-		pr_err("Firmware component requires unsupported CPU reset\n");
-
-		return -EINVAL;
-	}
-
 	ret = activate_fw_image(attrs);
 	if (ret) {
 		pr_err("Firmware activation failed: %s\n",
@@ -309,25 +333,11 @@ static ssize_t cancel_store(struct kobject *kobj, struct kobj_attribute *attr,
 {
 	struct image_props *attrs = container_of(attr, struct image_props,
 						 image_attrs[LFA_ATTR_CANCEL]);
-	struct arm_smccc_1_2_regs reg = { 0 };
-
-	reg.a0 = LFA_1_0_FN_CANCEL;
-	reg.a1 = attrs->fw_seq_id;
-	arm_smccc_1_2_invoke(&reg, &reg);
+	int ret;
 
-	/*
-	 * When firmware activation is called with "skip_cpu_rendezvous=1",
-	 * LFA_CANCEL can fail with LFA_BUSY if the activation could not be
-	 * cancelled.
-	 */
-	if (reg.a0 == LFA_SUCCESS) {
-		pr_info("Activation cancelled for image %s\n",
-			attrs->image_name);
-	} else {
-		pr_err("Firmware activation could not be cancelled: %s\n",
-		       lfa_error_strings[-reg.a0]);
-		return -EINVAL;
-	}
+	ret = lfa_cancel(attrs);
+	if (ret != 0)
+		return ret;
 
 	return count;
 }
@@ -367,6 +377,8 @@ static int create_fw_inventory(char *fw_uuid, int seq_id, u32 image_flags)
 	for (int i = 0; i < ARRAY_SIZE(fw_images_uuids); i++) {
 		if (!strcmp(fw_images_uuids[i].uuid, fw_uuid))
 			image_name = fw_images_uuids[i].name;
+		else
+			image_name = fw_uuid;
 	}
 
 	attrs->image_dir = kobject_create_and_add(fw_uuid, lfa_dir);
@@ -414,6 +426,10 @@ static int create_fw_images_tree(void)
 	int ret, num_of_components;
 
 	num_of_components = get_nr_lfa_components();
+	if (num_of_components <= 0) {
+		pr_err("Error getting number of LFA components");
+		return -ENODEV;
+	}
 
 	for (int i = 0; i < num_of_components; i++) {
 		reg.a0 = LFA_1_0_FN_GET_INVENTORY;

---

## [4] Vedashree Vidwans — 2025-12-08
*Subject: [RFC PATCH 3/5] firmware: smccc: add timeout, touch wdt*

Enhance PRIME/ACTIVATION functions to touch watchdog and implement
timeout mechanism. This update ensures that any potential hangs are
detected promptly and that the LFA process is allocated sufficient
execution time before the watchdog timer expires. These changes improve
overall system reliability by reducing the risk of undetected process
stalls and unexpected watchdog resets.

Signed-off-by: Vedashree Vidwans <vvidwans@nvidia.com>
---
 drivers/firmware/smccc/lfa_fw.c | 74 +++++++++++++++++++++++++++++----
 1 file changed, 67 insertions(+), 7 deletions(-)

diff --git a/drivers/firmware/smccc/lfa_fw.c b/drivers/firmware/smccc/lfa_fw.c
index df8b65324413..0e420cefa260 100644
--- a/drivers/firmware/smccc/lfa_fw.c
+++ b/drivers/firmware/smccc/lfa_fw.c
@@ -16,6 +16,9 @@
 #include <linux/uuid.h>
 #include <linux/array_size.h>
 #include <linux/list.h>
+#include <linux/nmi.h>
+#include <linux/ktime.h>
+#include <linux/delay.h>
 
 #define LFA_ERROR_STRING(name) \
 	[name] = #name
@@ -34,6 +37,18 @@
 #define LFA_1_0_FN_ACTIVATE		LFA_1_0_FN(5)
 #define LFA_1_0_FN_CANCEL		LFA_1_0_FN(6)
 
+/* CALL_AGAIN flags (returned by SMC) */
+#define LFA_PRIME_CALL_AGAIN		BIT(0)
+#define LFA_ACTIVATE_CALL_AGAIN		BIT(0)
+
+/* Prime loop limits, TODO: tune after testing */
+#define LFA_PRIME_BUDGET_US		30000000	/* 30s cap */
+#define LFA_PRIME_POLL_DELAY_US		10		/* 10us between polls */
+
+/* Activation loop limits, TODO: tune after testing */
+#define LFA_ACTIVATE_BUDGET_US		20000000	/* 20s cap */
+#define LFA_ACTIVATE_POLL_DELAY_US	10		/* 10us between polls */
+
 /* LFA return values */
 #define LFA_SUCCESS			0
 #define LFA_NOT_SUPPORTED		1
@@ -159,6 +174,8 @@ static int call_lfa_activate(void *data)
 	struct image_props *attrs = data;
 	struct arm_smccc_1_2_regs args = { 0 };
 	struct arm_smccc_1_2_regs res = { 0 };
+	ktime_t end = ktime_add_us(ktime_get(), LFA_ACTIVATE_BUDGET_US);
+	int ret;
 
 	args.a0 = LFA_1_0_FN_ACTIVATE;
 	args.a1 = attrs->fw_seq_id; /* fw_seq_id under consideration */
@@ -172,9 +189,34 @@ static int call_lfa_activate(void *data)
 	 */
 	args.a2 = !(attrs->cpu_rendezvous_forced || attrs->cpu_rendezvous);
 
-	do {
+	for (;;) {
+		/* Touch watchdog, ACTIVATE shouldn't take longer than watchdog_thresh */
+		touch_nmi_watchdog();
 		arm_smccc_1_2_invoke(&args, &res);
-	} while (res.a0 == 0 && res.a1 == 1);
+
+		if ((long)res.a0 < 0) {
+			pr_err("ACTIVATE for image %s failed: %s",
+				attrs->image_name, lfa_error_strings[-res.a0]);
+			return res.a0;
+		}
+
+		/* SMC returned with success */
+		if (!(res.a1 & LFA_ACTIVATE_CALL_AGAIN))
+			break; /* ACTIVATE successful */
+
+		/* SMC returned with call_again flag set */
+		if (ktime_before(ktime_get(), end)) {
+			udelay(LFA_ACTIVATE_POLL_DELAY_US);
+			continue;
+		}
+
+		pr_err("ACTIVATE timed out for image %s", attrs->image_name);
+		ret = lfa_cancel(attrs);
+		if (ret == 0)
+			return -ETIMEDOUT;
+		else
+			return ret;
+	}
 
 	return res.a0;
 }
@@ -183,6 +225,7 @@ static int activate_fw_image(struct image_props *attrs)
 {
 	struct arm_smccc_1_2_regs args = { 0 };
 	struct arm_smccc_1_2_regs res = { 0 };
+	ktime_t end = ktime_add_us(ktime_get(), LFA_PRIME_BUDGET_US);
 	int ret;
 
 	if (attrs->may_reset_cpu) {
@@ -198,15 +241,32 @@ static int activate_fw_image(struct image_props *attrs)
 	 */
 	args.a0 = LFA_1_0_FN_PRIME;
 	args.a1 = attrs->fw_seq_id; /* fw_seq_id under consideration */
-	do {
+	for (;;) {
+		/* Touch watchdog, PRIME shouldn't take longer than watchdog_thresh */
+		touch_nmi_watchdog();
 		arm_smccc_1_2_invoke(&args, &res);
-		if (res.a0 != LFA_SUCCESS) {
-			pr_err("LFA_PRIME failed: %s\n",
-				lfa_error_strings[-res.a0]);
 
+		if ((long)res.a0 < 0) {
+			pr_err("LFA_PRIME for image %s failed: %s\n",
+				attrs->image_name, lfa_error_strings[-res.a0]);
 			return res.a0;
 		}
-	} while (res.a1 == 1);
+		if (!(res.a1 & LFA_PRIME_CALL_AGAIN))
+			break; /* PRIME successful */
+
+		/* SMC returned with call_again flag set */
+		if (ktime_before(ktime_get(), end)) {
+			udelay(LFA_PRIME_POLL_DELAY_US);
+			continue;
+		}
+
+		pr_err("PRIME timed out for image %s", attrs->image_name);
+		ret = lfa_cancel(attrs);
+		if (ret == 0)
+			return -ETIMEDOUT;
+		else
+			return ret;
+	}
 
 	if (attrs->cpu_rendezvous_forced || attrs->cpu_rendezvous)
 		ret = stop_machine(call_lfa_activate, attrs, cpu_online_mask);

---

## [5] Vedashree Vidwans — 2025-12-08
*Subject: [RFC PATCH 4/5] firmware: smccc: register as platform driver*

- Update driver to be in-built kernel module. This will ensure driver is
installed in kernel and would not require any user intervention.
- Register the LFA driver as a platform driver corresponding to
'armhf000' device. The driver will be invoked when the device is
detected on a platform.
- Add functionality to register LFA interrupt in the driver probe().
This LFA IRQ number will be retrived from the LFA device node.
- On IRQ, driver will query FW component details and trigger activation
of capable and pending FW component. The driver will loop to update FW
component details after every successful FW component activation.
- Mutex synchronization is implemented to avoid concurrent LFA updates
through interrupt and sysfs interfaces.

Device node snippet from LFA spec[1]:
fwu0 {
    compatible = "arm,armhf000";
    memory-region = <&fwu_payload>;
    interrupt-parent = <&ic>;
    interrupts = <0 100 1>; // SPI, Interrupt #100, Edge Rising
};

[1] https://developer.arm.com/documentation/den0147/latest/

Signed-off-by: Vedashree Vidwans <vvidwans@nvidia.com>
---
 drivers/firmware/smccc/Kconfig  |   3 +-
 drivers/firmware/smccc/lfa_fw.c | 124 +++++++++++++++++++++++++++++++-
 2 files changed, 125 insertions(+), 2 deletions(-)

diff --git a/drivers/firmware/smccc/Kconfig b/drivers/firmware/smccc/Kconfig
index 48b98c14f770..c21be43fbfed 100644
--- a/drivers/firmware/smccc/Kconfig
+++ b/drivers/firmware/smccc/Kconfig
@@ -25,8 +25,9 @@ config ARM_SMCCC_SOC_ID
 	  platforms providing some sysfs information about the SoC variant.
 
 config ARM_LFA
-	tristate "Arm Live Firmware activation support"
+	bool "Arm Live Firmware activation support"
 	depends on HAVE_ARM_SMCCC_DISCOVERY
+	default y
 	help
 	  Include support for triggering Live Firmware Activation, which
 	  allows to upgrade certain firmware components without a reboot.
diff --git a/drivers/firmware/smccc/lfa_fw.c b/drivers/firmware/smccc/lfa_fw.c
index 0e420cefa260..24916fc53420 100644
--- a/drivers/firmware/smccc/lfa_fw.c
+++ b/drivers/firmware/smccc/lfa_fw.c
@@ -19,7 +19,12 @@
 #include <linux/nmi.h>
 #include <linux/ktime.h>
 #include <linux/delay.h>
+#include <linux/platform_device.h>
+#include <linux/acpi.h>
+#include <linux/interrupt.h>
+#include <linux/mutex.h>
 
+#define DRIVER_NAME	"ARM_LFA"
 #define LFA_ERROR_STRING(name) \
 	[name] = #name
 #undef pr_fmt
@@ -129,6 +134,7 @@ static const struct fw_image_uuid {
 };
 
 static struct kobject *lfa_dir;
+static DEFINE_MUTEX(lfa_lock);
 
 static int get_nr_lfa_components(void)
 {
@@ -374,17 +380,23 @@ static ssize_t activate_store(struct kobject *kobj, struct kobj_attribute *attr,
 					 image_attrs[LFA_ATTR_ACTIVATE]);
 	int ret;
 
+	if (!mutex_trylock(&lfa_lock)) {
+		pr_err("Mutex locked, try again");
+		return -EAGAIN;
+	}
+
 	ret = activate_fw_image(attrs);
 	if (ret) {
 		pr_err("Firmware activation failed: %s\n",
 			lfa_error_strings[-ret]);
-
+		mutex_unlock(&lfa_lock);
 		return -ECANCELED;
 	}
 
 	pr_info("Firmware activation succeeded\n");
 
 	/* TODO: refresh image flags here*/
+	mutex_unlock(&lfa_lock);
 	return count;
 }
 
@@ -510,6 +522,106 @@ static int create_fw_images_tree(void)
 	return 0;
 }
 
+static irqreturn_t lfa_irq_thread(int irq, void *data)
+{
+	struct image_props *attrs = NULL;
+	int ret;
+	int num_of_components, curr_component;
+
+	mutex_lock(&lfa_lock);
+
+	/*
+	 * As per LFA spec, after activation of a component, the caller
+	 * is expected to re-enumerate the component states (using
+	 * LFA_GET_INFO then LFA_GET_INVENTORY).
+	 * Hence we need an unconditional loop.
+	 */
+
+	do {
+		/* TODO: refresh image flags here */
+		/* If refresh fails goto exit_unlock */
+
+		/* Initialize counters to track list traversal  */
+		num_of_components = get_nr_lfa_components();
+		curr_component = 0;
+
+		/* Execute PRIME and ACTIVATE for activable FW component */
+		list_for_each_entry(attrs, &lfa_fw_images, image_node) {
+			curr_component++;
+			if ((!attrs->activation_capable) || (!attrs->activation_pending)) {
+				/* LFA not applicable for this FW component */
+				continue;
+			}
+
+			ret = activate_fw_image(attrs);
+			if (ret) {
+				pr_err("Firmware %s activation failed: %s\n",
+					attrs->image_name, lfa_error_strings[-ret]);
+				goto exit_unlock;
+			}
+
+			pr_info("Firmware %s activation succeeded", attrs->image_name);
+			/* Refresh FW component details */
+			break;
+		}
+	} while (curr_component < num_of_components);
+
+	/* TODO: refresh image flags here */
+	/* If refresh fails goto exit_unlock */
+
+exit_unlock:
+	mutex_unlock(&lfa_lock);
+	return IRQ_HANDLED;
+}
+
+static int __init lfa_probe(struct platform_device *pdev)
+{
+	int err;
+	unsigned int irq;
+
+	err = platform_get_irq_byname_optional(pdev, "fw-store-updated-interrupt");
+	if (err < 0)
+		err = platform_get_irq(pdev, 0);
+	if (err < 0) {
+		pr_err("Interrupt not found, functionality will be unavailable.");
+
+		/* Bail out without failing the driver. */
+		return 0;
+	}
+	irq = err;
+
+	err = request_threaded_irq(irq, NULL, lfa_irq_thread, IRQF_ONESHOT, DRIVER_NAME, NULL);
+	if (err != 0) {
+		pr_err("Interrupt setup failed, functionality will be unavailable.");
+
+		/* Bail out without failing the driver. */
+		return 0;
+	}
+
+	return 0;
+}
+
+static const struct of_device_id lfa_of_ids[] = {
+	{ .compatible = "arm,armhf000", },
+	{ },
+};
+MODULE_DEVICE_TABLE(of, lfa_of_ids);
+
+static const struct acpi_device_id lfa_acpi_ids[] = {
+	{"ARMHF000"},
+	{},
+};
+MODULE_DEVICE_TABLE(acpi, lfa_acpi_ids);
+
+static struct platform_driver lfa_driver = {
+	.probe = lfa_probe,
+	.driver = {
+		.name = DRIVER_NAME,
+		.of_match_table = lfa_of_ids,
+		.acpi_match_table = ACPI_PTR(lfa_acpi_ids),
+	},
+};
+
 static int __init lfa_init(void)
 {
 	struct arm_smccc_1_2_regs reg = { 0 };
@@ -536,22 +648,32 @@ static int __init lfa_init(void)
 	pr_info("Arm Live Firmware Activation (LFA): detected v%ld.%ld\n",
 		reg.a0 >> 16, reg.a0 & 0xffff);
 
+	err = platform_driver_register(&lfa_driver);
+	if (err < 0)
+		pr_err("Platform driver register failed");
+
 	lfa_dir = kobject_create_and_add("lfa", firmware_kobj);
 	if (!lfa_dir)
 		return -ENOMEM;
 
+	mutex_lock(&lfa_lock);
 	err = create_fw_images_tree();
 	if (err != 0)
 		kobject_put(lfa_dir);
 
+	mutex_unlock(&lfa_lock);
 	return err;
 }
 module_init(lfa_init);
 
 static void __exit lfa_exit(void)
 {
+	mutex_lock(&lfa_lock);
 	clean_fw_images_tree();
+	mutex_unlock(&lfa_lock);
+
 	kobject_put(lfa_dir);
+	platform_driver_unregister(&lfa_driver);
 }
 module_exit(lfa_exit);

---

## [6] Vedashree Vidwans — 2025-12-08
*Subject: [RFC PATCH 5/5] firmware: smccc: lfa: refresh fw details*

FW image details are querried with a SMC call. Currently, these FW
details are added as nodes in a linked list. This patch updates the
FW node creation and update functions. Now the linked list is updated
based on the current value of num_lfa_components.
As per spec [1], FW inventory is updated after each activation.

[1] https://developer.arm.com/documentation/den0147/latest/

Signed-off-by: Vedashree Vidwans <vvidwans@nvidia.com>
---
 drivers/firmware/smccc/lfa_fw.c | 148 +++++++++++++++++++++-----------
 1 file changed, 100 insertions(+), 48 deletions(-)

diff --git a/drivers/firmware/smccc/lfa_fw.c b/drivers/firmware/smccc/lfa_fw.c
index 24916fc53420..334090708405 100644
--- a/drivers/firmware/smccc/lfa_fw.c
+++ b/drivers/firmware/smccc/lfa_fw.c
@@ -133,6 +133,7 @@ static const struct fw_image_uuid {
 	},
 };
 
+static int update_fw_images_tree(void);
 static struct kobject *lfa_dir;
 static DEFINE_MUTEX(lfa_lock);
 
@@ -282,17 +283,6 @@ static int activate_fw_image(struct image_props *attrs)
 	return ret;
 }
 
-static void set_image_flags(struct image_props *attrs, int seq_id,
-			    u32 image_flags)
-{
-	attrs->fw_seq_id = seq_id;
-	attrs->activation_capable = !!(image_flags & BIT(0));
-	attrs->activation_pending = !!(image_flags & BIT(1));
-	attrs->may_reset_cpu = !!(image_flags & BIT(2));
-	/* cpu_rendezvous_optional bit has inverse logic in the spec */
-	attrs->cpu_rendezvous = !(image_flags & BIT(3));
-}
-
 static ssize_t name_show(struct kobject *kobj, struct kobj_attribute *attr,
 			 char *buf)
 {
@@ -395,7 +385,9 @@ static ssize_t activate_store(struct kobject *kobj, struct kobj_attribute *attr,
 
 	pr_info("Firmware activation succeeded\n");
 
-	/* TODO: refresh image flags here*/
+	ret = update_fw_images_tree();
+	if (ret)
+		pr_err("Failed to update FW images tree");
 	mutex_unlock(&lfa_lock);
 	return count;
 }
@@ -425,20 +417,41 @@ static struct kobj_attribute image_attrs_group[LFA_ATTR_NR_IMAGES] = {
 	[LFA_ATTR_CANCEL]		= __ATTR_WO(cancel)
 };
 
+static void delete_fw_image_node(struct image_props *attrs)
+{
+	int i;
+
+	for (i = 0; i < LFA_ATTR_NR_IMAGES; i++)
+		sysfs_remove_file(attrs->image_dir, &attrs->image_attrs[i].attr);
+
+	kobject_put(attrs->image_dir);
+	attrs->image_dir = NULL;
+	list_del(&attrs->image_node);
+	kfree(attrs);
+}
+
 static void clean_fw_images_tree(void)
 {
 	struct image_props *attrs, *tmp;
 
-	list_for_each_entry_safe(attrs, tmp, &lfa_fw_images, image_node) {
-		kobject_put(attrs->image_dir);
-		list_del(&attrs->image_node);
-		kfree(attrs);
-	}
+	list_for_each_entry_safe(attrs, tmp, &lfa_fw_images, image_node)
+		delete_fw_image_node(attrs);
+}
+
+static void update_fw_image_node(struct image_props *attrs, int seq_id,
+			    char *fw_uuid, u32 image_flags)
+{
+	attrs->fw_seq_id = seq_id;
+	attrs->image_name = fw_uuid;
+	attrs->activation_capable = !!(image_flags & BIT(0));
+	attrs->activation_pending = !!(image_flags & BIT(1));
+	attrs->may_reset_cpu = !!(image_flags & BIT(2));
+	/* cpu_rendezvous_optional bit has inverse logic in the spec */
+	attrs->cpu_rendezvous = !(image_flags & BIT(3));
 }
 
-static int create_fw_inventory(char *fw_uuid, int seq_id, u32 image_flags)
+static int create_fw_image_node(int seq_id, char *fw_uuid, u32 image_flags)
 {
-	const char *image_name = "(unknown)";
 	struct image_props *attrs;
 	int ret;
 
@@ -446,21 +459,12 @@ static int create_fw_inventory(char *fw_uuid, int seq_id, u32 image_flags)
 	if (!attrs)
 		return -ENOMEM;
 
-	for (int i = 0; i < ARRAY_SIZE(fw_images_uuids); i++) {
-		if (!strcmp(fw_images_uuids[i].uuid, fw_uuid))
-			image_name = fw_images_uuids[i].name;
-		else
-			image_name = fw_uuid;
-	}
-
 	attrs->image_dir = kobject_create_and_add(fw_uuid, lfa_dir);
 	if (!attrs->image_dir)
 		return -ENOMEM;
 
-	INIT_LIST_HEAD(&attrs->image_node);
-	attrs->image_name = image_name;
-	attrs->cpu_rendezvous_forced = 1;
-	set_image_flags(attrs, seq_id, image_flags);
+	/* Update FW attributes */
+	update_fw_image_node(attrs, seq_id, fw_uuid, image_flags);
 
 	/*
 	 * The attributes for each sysfs file are constant (handler functions,
@@ -485,17 +489,19 @@ static int create_fw_inventory(char *fw_uuid, int seq_id, u32 image_flags)
 			return ret;
 		}
 	}
-	list_add(&attrs->image_node, &lfa_fw_images);
+	list_add_tail(&attrs->image_node, &lfa_fw_images);
 
 	return ret;
 }
 
-static int create_fw_images_tree(void)
+static int update_fw_images_tree(void)
 {
 	struct arm_smccc_1_2_regs reg = { 0 };
 	struct uuid_regs image_uuid;
+	struct image_props *attrs, *tmp;
 	char image_id_str[40];
 	int ret, num_of_components;
+	int node_idx = 0;
 
 	num_of_components = get_nr_lfa_components();
 	if (num_of_components <= 0) {
@@ -503,22 +509,67 @@ static int create_fw_images_tree(void)
 		return -ENODEV;
 	}
 
-	for (int i = 0; i < num_of_components; i++) {
-		reg.a0 = LFA_1_0_FN_GET_INVENTORY;
-		reg.a1 = i; /* fw_seq_id under consideration */
-		arm_smccc_1_2_invoke(&reg, &reg);
-		if (reg.a0 == LFA_SUCCESS) {
+	/*
+	 * Pass 1:
+	 *    For nodes < num_of_components, update fw_image_node
+	 *    For nodes >= num_of_components, delete
+	 */
+	list_for_each_entry_safe(attrs, tmp, &lfa_fw_images, image_node) {
+		if (attrs->fw_seq_id < num_of_components) {
+			/* Update this FW image node */
+
+			/* Get FW details */
+			reg.a0 = LFA_1_0_FN_GET_INVENTORY;
+			reg.a1 = attrs->fw_seq_id;
+			arm_smccc_1_2_invoke(&reg, &reg);
+
+			if (reg.a0 != LFA_SUCCESS)
+				return -EINVAL;
+
+			/* Build image name with UUID */
 			image_uuid.uuid_lo = reg.a1;
 			image_uuid.uuid_hi = reg.a2;
+			snprintf(image_id_str, sizeof(image_id_str), "%pUb", &image_uuid);
 
-			snprintf(image_id_str, sizeof(image_id_str), "%pUb",
-				 &image_uuid);
-			ret = create_fw_inventory(image_id_str, i, reg.a3);
-			if (ret)
-				return ret;
+			if (strcmp(attrs->image_name, image_id_str)) {
+				/* UUID doesn't match previous UUID for given FW, not expected */
+				pr_err("FW seq id %u: Previous UUID %s doesn't match current %s",
+					attrs->fw_seq_id, attrs->image_name, image_id_str);
+				return -EINVAL;
+			}
+
+			/* Update FW attributes */
+			update_fw_image_node(attrs, attrs->fw_seq_id, image_id_str, reg.a3);
+			node_idx++;
+		} else {
+			/* This node is beyond valid FW components list */
+			delete_fw_image_node(attrs);
 		}
 	}
 
+	/*
+	 * Pass 2:
+	 *    If current FW components number is more than previous list, add new component nodes.
+	 */
+	for (node_idx; node_idx < num_of_components; node_idx++) {
+		/* Get FW details */
+		reg.a0 = LFA_1_0_FN_GET_INVENTORY;
+		reg.a1 = node_idx;
+		arm_smccc_1_2_invoke(&reg, &reg);
+
+		if (reg.a0 != LFA_SUCCESS)
+			return -EINVAL;
+
+		/* Build image name with UUID */
+		image_uuid.uuid_lo = reg.a1;
+		image_uuid.uuid_hi = reg.a2;
+		snprintf(image_id_str, sizeof(image_id_str), "%pUb", &image_uuid);
+
+		ret = create_fw_image_node(node_idx, image_id_str, reg.a3);
+		if (ret)
+			return ret;
+	}
+
 	return 0;
 }
 
@@ -538,8 +589,9 @@ static irqreturn_t lfa_irq_thread(int irq, void *data)
 	 */
 
 	do {
-		/* TODO: refresh image flags here */
-		/* If refresh fails goto exit_unlock */
+		ret = update_fw_images_tree();
+		if (ret)
+			goto exit_unlock;
 
 		/* Initialize counters to track list traversal  */
 		num_of_components = get_nr_lfa_components();
@@ -561,13 +613,13 @@ static irqreturn_t lfa_irq_thread(int irq, void *data)
 			}
 
 			pr_info("Firmware %s activation succeeded", attrs->image_name);
-			/* Refresh FW component details */
 			break;
 		}
 	} while (curr_component < num_of_components);
 
-	/* TODO: refresh image flags here */
-	/* If refresh fails goto exit_unlock */
+	ret = update_fw_images_tree();
+	if (ret)
+		goto exit_unlock;
 
 exit_unlock:
 	mutex_unlock(&lfa_lock);
@@ -657,7 +709,7 @@ static int __init lfa_init(void)
 		return -ENOMEM;
 
 	mutex_lock(&lfa_lock);
-	err = create_fw_images_tree();
+	err = update_fw_images_tree();
 	if (err != 0)
 		kobject_put(lfa_dir);

---

## [7] Sudeep Holla — 2025-12-09
*Subject: Re: [RFC PATCH 0/5] Arm LFA: Improvements and interrupt support*

On Mon, Dec 08, 2025 at 10:13:10PM +0000, Vedashree Vidwans wrote:
> Hello,
> 

Same comment as before[1], looks like the feedback got ignored or missed.

---

## [8] Sudeep Holla — 2025-12-09
*Subject: Re: [RFC PATCH 1/5] firmware: smccc: LFA: use smcc 1.2*

On Mon, Dec 08, 2025 at 10:13:11PM +0000, Vedashree Vidwans wrote:
> Update driver to use SMCCC 1.2+ version as mentioned in the LFA spec.
> 

I would prefer if you work with Salman Nabi and get this incorporated
in the original patch by providing this as a review feedback.

There is no point in having this independent of the original patch as it
is not yet merged.

---

## [9] Sudeep Holla — 2025-12-09
*Subject: Re: [RFC PATCH 4/5] firmware: smccc: register as platform driver*

On Mon, Dec 08, 2025 at 10:13:14PM +0000, Vedashree Vidwans wrote:
> - Update driver to be in-built kernel module. This will ensure driver is
> installed in kernel and would not require any user intervention.

This will be gone in the latest beta of LFA, so please discuss and get
an agreement for the LFA device tree bindings.

We don't just use ACPI HID as devicetree compatibles. There are more
aligned with ACPI CID IIUC but I don't expect you to use ACPI CID just to
match DT compatible as ACPI HID will be defined for LFA.

> [1] https://developer.arm.com/documentation/den0147/latest/
> 

Nice, "fw-store-updated-interrupt" is not even mentioned in the example DT
node above, let alone proper DT bindings.

---

## [10] Matt Ochs — 2025-12-12
*Subject: Re: [RFC PATCH 4/5] firmware: smccc: register as platform driver*

> On Dec 8, 2025, at 16:13, Vedashree Vidwans <vvidwans@nvidia.com> wrote:
> 
...
> +
> +static int __init lfa_probe(struct platform_device *pdev)

WARNING: modpost: vmlinux: section mismatch in reference: lfa_driver+0x0 (section: .data) -> lfa_probe (section: .init.text)

__init is not needed here, please remove.

---

## [11] Matt Ochs — 2025-12-12
*Subject: Re: [RFC PATCH 5/5] firmware: smccc: lfa: refresh fw details*

> On Dec 8, 2025, at 16:13, Vedashree Vidwans <vvidwans@nvidia.com> wrote:
> 
...
> + /*
> + * Pass 2:

drivers/firmware/smccc/lfa_fw.c: In function ‘update_fw_images_tree’:
drivers/firmware/smccc/lfa_fw.c:554:9: warning: statement with no effect [-Wunused-value]
  554 |         for (node_idx; node_idx < num_of_components; node_idx++) {
      |         ^~~

Please drop “node_idx” from the initializer statement.

---

## [12] Vedashree Vidwans — 2025-12-18
*Subject: Re: [RFC PATCH 5/5] firmware: smccc: lfa: refresh fw details*

On 12/12/25 07:37, Matt Ochs wrote:
>> On Dec 8, 2025, at 16:13, Vedashree Vidwans <vvidwans@nvidia.com> wrote:
>>
Thank you, I will include this change in next update.

Veda

---

## [13] Vedashree Vidwans — 2025-12-18
*Subject: Re: [RFC PATCH 4/5] firmware: smccc: register as platform driver*

On 12/12/25 07:31, Matt Ochs wrote:
>> On Dec 8, 2025, at 16:13, Vedashree Vidwans <vvidwans@nvidia.com> wrote:
>>

Thank you, I will include this change in next update.

Veda

---

## [14] Vedashree Vidwans — 2025-12-19
*Subject: Re: [RFC PATCH 4/5] firmware: smccc: register as platform driver*

On 12/9/25 03:47, Sudeep Holla wrote:
> On Mon, Dec 08, 2025 at 10:13:14PM +0000, Vedashree Vidwans wrote:
>> - Update driver to be in-built kernel module. This will ensure driver is
Thank you for your comment.
Sorry I haven't completely understood the concern here. I am using the 
ACPI HID and device node compatible string provided by the LFA spec.
Please find below ACPI and device tree node from the spec for reference.
In case the LFA spec is updated, I will revise the driver implementation.

LFA spec: https://developer.arm.com/documentation/den0147/latest/

ACPI node:
DefinitionBlock ("", "SSDT", 2, "XXXXXX", "XXXXXXXX", 1) {
     Scope (\_SB)
     {
         Device (FWU0) {
             Name (_HID, "ARMHF000") // Arm HAFW DSDT table identifier.
             Name (_CRS, ResourceTemplate () {

                 // Payload buffer description.
                 QWordMemory (,
                     ,
                     MinFixed,
                     MaxFixed,
                     NonCacheable,
                     ReadWrite,
                     0x0,
                     0x2000, // base PA of payload buffer
                     0x2FFF, // top PA of payload buffer
                     0,
                     0x1000, // payload buffer length
                     ,
                     ,
                 )

                 // Interrupt signaling the updated Live Activation Store.
                 Interrupt(,
                     Edge, // Interrupt type (or interrupt mode)
                     ActiveHigh, // Interrupt level
                     ,
                     ,
                     ,
                 ) {100} // Note that this is an example interrupt.
                     // The interrupt ID is defined per-platform.
             })

             // _DSD -- Holds map between field names and objects within 
the _CRS
             Name (_DSD, Package () {
                 ToUUID ("daffd814-6eba-4d8c-8a91-bc9bbf4aa30") ,
                 Package() {
                     // Contains a set of packages of 2 entries each,
                     // the second entry is an index into the _CRS.
                     Package (2) {"payload-buffer", 1},
                     Package (2) {"fw-store-updated-interrupt", 2},
                 },
             })
         }
     }
}

Device Tree node:
/dts-v1/;
/ {
     #address-cells = <2>;
     #size-cells = <2>;
     ic: interrupt-controller@2f000000 {
         compatible = "arm,gic-v3";
         #interrupt-cells = <3>;
         #address-cells = <2>;
         #size-cells = <2>;
         interrupt-controller;
         reg = <0x0 0x2f000000 0x0 0x10000>,
               <0x0 0x2f100000 0x0 0x200000>;
     };

     reserved-memory {
         #address-cells = <2>;
         #size-cells = <2>;
         ranges;
         fwu_payload: fwu_payload@2000 {
             reg = <0x0 0x2000 0x0 0x1000>;
             no-map;
         };
     };

     soc {
         #address-cells = <2>;
         #size-cells = <2>;
         ranges;
         fwu0 {
             compatible = "arm,armhf000";
             memory-region = <&fwu_payload>;
             interrupt-parent = <&ic>;
             interrupts = <0 100 1>; // SPI, Interrupt #100, Edge Rising
         };
     };
};

>> [1] https://developer.arm.com/documentation/den0147/latest/
>>
Thank you for pointing this out. The DT binding would have to be updated 
to below or the driver will fall back to platform_get_irq().

fwu0 {
     compatible = "arm,armhf000";
     memory-region = <&fwu_payload>;
     interrupt-parent = <&ic>;
     interrupts = <0 100 1>; // SPI, Interrupt #100, Edge Rising
     interrupt-names = "fw-store-updated-interrupt";
};

Regards,
Veda

---

## [15] Vedashree Vidwans — 2025-12-19
*Subject: Re: [RFC PATCH 0/5] Arm LFA: Improvements and interrupt support*

On 12/9/25 03:39, Sudeep Holla wrote:
> On Mon, Dec 08, 2025 at 10:13:10PM +0000, Vedashree Vidwans wrote:
>> Hello,

Thank you for your comment.
I did include DT binding in commit message of the patch. Please let me 
know if there's anything else I can elaborate.

Regards,
Veda

---

## [16] Vedashree Vidwans — 2025-12-19
*Subject: Re: [RFC PATCH 1/5] firmware: smccc: LFA: use smcc 1.2*

On 12/9/25 03:42, Sudeep Holla wrote:
> On Mon, Dec 08, 2025 at 10:13:11PM +0000, Vedashree Vidwans wrote:
>> Update driver to use SMCCC 1.2+ version as mentioned in the LFA spec.

Thank you for the suggestion.

Hi Salman,
Could we come up with a strategy to combine the LFA driver patches? I 
have been working on this recently and I would be happy to revise all 
the patches so that we are followiing the specification from the start.

Please let me know if you think of any other approach.

Regards,
Veda

---

## [17] Sudeep Holla — 2025-12-19
*Subject: Re: [RFC PATCH 0/5] Arm LFA: Improvements and interrupt support*

On Fri, Dec 19, 2025 at 12:38:39AM -0800, Vedashree Vidwans wrote:
> 
> 

Sure. I meant I don't see any patch titled "dt-bindings: firmware: Add LFA...."
or something similar. I also checked the delta for the files under
Documentation/devicetree/bindings/ to rule out the possibility that the
patch title may not be following the DT binding upstreaming process.

---

## [18] Sudeep Holla — 2025-12-19
*Subject: Re: [RFC PATCH 1/5] firmware: smccc: LFA: use smcc 1.2*

On Fri, Dec 19, 2025 at 12:47:52AM -0800, Vedashree Vidwans wrote:
> 
> 

Ideally, you should comment directly on the original submission, outlining the
specific changes you would like to see - just as you would when reviewing a
patch. This helps document your requests clearly and allows the author to
address them and post a revised version, ensuring that all changes are
properly tracked on the mailing list.

---

## [19] Sudeep Holla — 2025-12-19
*Subject: Re: [RFC PATCH 4/5] firmware: smccc: register as platform driver*

On Fri, Dec 19, 2025 at 12:26:30AM -0800, Vedashree Vidwans wrote:
> 
> On 12/9/25 03:47, Sudeep Holla wrote:

Yes I know, but take a look at updated specification please [1].

> Please find below ACPI and device tree node from the spec for reference.

Yes they are obsolete as they no longer align with the latest specification.

> In case the LFA spec is updated, I will revise the driver implementation.

Indeed, that is the expectation. That's exactly what I meant.

---

## [20] Andre Przywara — 2026-01-13
*Subject: Re: [RFC PATCH 0/5] Arm LFA: Improvements and interrupt support*

Hi Vedashree,

thanks for your efforts on this, and sorry for the delay on our side. We 
were hold up by a combination of spec changes and non-overlapping holidays.

On 08/12/2025 22:13, Vedashree Vidwans wrote:
> Hello,
> 

I would propose we change that approach a bit. We have updated and 
improved the driver internally, but were waiting for the new version of 
the spec (BET1) to be released, which happened some weeks ago. Salman 
will send out a new version of the driver in the next few days. Anything 
that is a bug (like the omission of the SMCCC v1.2 interface) will be 
addressed there, as there is no point to merge with a known buggy base 
patch. Also we will incorporate the changes we made so far, including 
adjustments for the new spec version.

Anything that can be added as independent patches should be done so, I 
think for instance the interrupt support is such a candidate. Ideally 
you can rebase your series on the changed base patch once this has been 
posted.
For other things like the platform driver introduction we can use your 
series here as a discussion base, as it allows us to reason and discuss 
this easier than by looking at a from-scratch patch.

Does this make sense?

Also please note that the DT and ACPI part has changed in the latest 
version of the spec. I will send a DT binding patch ASAP, to get this 
part out of the way.

Cheers,
Andre


 > > The SMCCC usage in the driver is updated to consistently use the
> SMCCC 1.2 register-based calling convention, consolidating arguments
> and results into a single struct to reduce stack usage and simplify

---

## [21] Salman Nabi — 2026-01-19
*Subject: Re: [RFC PATCH 5/5] firmware: smccc: lfa: refresh fw details*

Hi Veda,

First of all sorry for the delay in responding back to you. You may have already seen my patch submission, following the RFC, here: https://lore.kernel.org/all/20260119122729.287522-2-salman.nabi@arm.com/

I have incorporated all the bug fixes and code refactor/cleanup suggestions from the RFC. It also includes changes to the LFA spec, mainly current and pending firmware version retrieval. I did not include your work and am hoping you would submit follow-up patches to include the updated ACPI table, IRQ handling, and platform driver registration etc.

I would also like to point a few issues here, this would also act as additional justification to some of the code changes I have introduced, for example, a work_queue() for updating firmware images from the activate_store handler.

On 12/8/25 22:13, Vedashree Vidwans wrote:
> FW image details are querried with a SMC call. Currently, these FW
> details are added as nodes in a linked list. This patch updates the

Part of the firmware images update process, there is a potential of a firmware component and its attributes being deleted following activation. The to-be-removed component could very well be the one where the activate call has been triggered from. This results in a deadlock as removing a sysfs attribute from within its _store handler results in kernfs to wait for the in-flight store() operation to finish before it can remove itself.

To cater for this scenario in my patch I am differing the firmware images update process, triggered from the _store handler, to a workqueue().

> +	if (ret)
> +		pr_err("Failed to update FW images tree");
We introduced a C struct "fw_image_uuid" to provide names for each firmware component in the LFA driver rather than using the UUID for a name which is non-intuitive. If UUIDs are desired for comparison then "attrs->image_dir->name" could be used.
> +	attrs->activation_capable = !!(image_flags & BIT(0));
> +	attrs->activation_pending = !!(image_flags & BIT(1));
attrs->image_name is supposed to be the name of the firmware image e.g. "TF-RMM" and not the UUID. If we need to compare the UUIDs I think we should use the specified firmware's directory name instead.
> +				/* UUID doesn't match previous UUID for given FW, not expected */

This is an expected behavior per the LFA spec. For example, firmware seq_ids get scrambled following an activation, the firmware image with seq_id 0 before activation has now a seq_id 1 following the activation in the LFA agent. When you attempt to request information for the firmware image using its old seq_id stored in the driver, the UUIDs would not match and thus the driver would bail out. We can't bail out for an expected behavior.

Just to confirm, my recent submission includes work on update of firmware images list following an activation.

Many thanks,
Salman

> +				pr_err("FW seq id %u: Previous UUID %s doesn't match current %s",
> +					attrs->fw_seq_id, attrs->image_name, image_id_str);

---

## [22] Salman Nabi — 2026-01-20
*Subject: Re: [RFC PATCH 4/5] firmware: smccc: register as platform driver*

Hi Veda,

On 12/8/25 22:13, Vedashree Vidwans wrote:
> - Update driver to be in-built kernel module. This will ensure driver is
> installed in kernel and would not require any user intervention.
I think the LFA driver is a strong candidate for a module rather than built-in only. If it ever needs to be built-in, we can always set its default state to "y". Kernel best practices prefer using tristate because it provides flexibility, unless the code cannot be modularized, for example, when it must run before the module loader is available.

Just an FYI, for built-in code the driver will need to be refactored, for example, the __exit call will need to be removed and the __init call will need to be changed, see here: https://lkml.org/lkml/2015/5/10/125


Many thanks,
Salman

>  	depends on HAVE_ARM_SMCCC_DISCOVERY
> +	default y

---
