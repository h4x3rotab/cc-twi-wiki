---
title: '[RFC PATCH 0/3] Arm LFA: Improvements and interrupt support'
date: 2025-10-08
last_reply: 2025-10-14
message_count: 14
participants: ['Vedashree Vidwans', 'Sudeep Holla', 'Salman Nabi', 'Andre Przywara']
---

## [1] Vedashree Vidwans — 2025-10-08

Hello,

These patches update the proposed Arm Live Firmware Activation (LFA)
kernel driver [2] introducing several enhancements and improvements as
outlined below:

SMCCC version 1.2 or later;
As per the specification [1], use SMC 1.2 to invoke ABI implemented
by the LFA Agent.

Interrupt-Based Enablement Support:
The patch extends the proposed LFA kernel driver to support
interrupt-based enablement, as described in the specification [1].
An interrupt thread function will query available firmware details
and trigger activation of qualified firmware components. This approach
allows the driver to respond more efficiently to hardware events and
improves overall firmware management.

Mutex Synchronization:
To prevent concurrent firmware updates by interrupt and sysfs
interfaces, mutex synchronization methods have been implemented.
This ensures that firmware operations are serialized, maintaining data
integrity and preventing race conditions during the update process.

Polling and Timeout Enhancements in PRIME / ACTIVATE Stages:
The patch introduces polling mechanisms and timeout controls during the
PRIME / ACTIVATE stages of firmware activation. The driver now
periodically polls with a delay to check the status. Additionally,
overall timeouts for PRIME / ACTIVATE have been implemented to guarantee
that the process completes within expected time limits. The initial
timeout values are deliberately set to be generous, and further tuning
will be performed after thorough testing.

PRIME / ACTIVATE FW components:
Interrupt-based LFA allows OS to trigger LFA for all activable FW
components. Initially, FW components are primed then activated
successively. The later patch modifies the PRIME / ACTIVATE stage
to prime all activable FW components followed by activation of each
FW component. This minimizes the time with combination of old and new
FW components co-exist.

Thank you,
Veda

[1] https://developer.arm.com/documentation/den0147/latest/
[2] https://lore.kernel.org/lkml/20250926123145.268728-1-salman.nabi@arm.com/

Vedashree Vidwans (3):
  firmware: smccc: LFA: use smcc 1.2
  firmware: smccc: LFA: refactor, add device node support
  firmware: smccc: LFA: modify activation approach

 drivers/firmware/smccc/lfa_fw.c | 429 +++++++++++++++++++++++++++-----
 1 file changed, 372 insertions(+), 57 deletions(-)

---

## [2] Vedashree Vidwans — 2025-10-08
*Subject: [RFC PATCH 1/3] firmware: smccc: LFA: use smcc 1.2*

Update driver to use SMCCC 1.2+ version as mentioned in the LFA spec.

Signed-off-by: Vedashree Vidwans <vvidwans@nvidia.com>
---
 drivers/firmware/smccc/lfa_fw.c | 80 +++++++++++++++++++++++----------
 1 file changed, 56 insertions(+), 24 deletions(-)

diff --git a/drivers/firmware/smccc/lfa_fw.c b/drivers/firmware/smccc/lfa_fw.c
index 1f333237271d8..49f7feb6a211b 100644
--- a/drivers/firmware/smccc/lfa_fw.c
+++ b/drivers/firmware/smccc/lfa_fw.c
@@ -117,9 +117,13 @@ static struct kobject *lfa_dir;
 
 static int get_nr_lfa_components(void)
 {
-	struct arm_smccc_res res = { 0 };
+	struct arm_smccc_1_2_regs args = { 0 };
+	struct arm_smccc_1_2_regs res = { 0 };
 
-	arm_smccc_1_1_invoke(LFA_1_0_FN_GET_INFO, 0x0, &res);
+	args.a0 = LFA_1_0_FN_GET_INFO;
+	args.a1 = 0; /* lfa_info_selector = 0 */
+
+	arm_smccc_1_2_invoke(&args, &res);
 	if (res.a0 != LFA_SUCCESS)
 		return res.a0;
 
@@ -129,20 +133,23 @@ static int get_nr_lfa_components(void)
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
@@ -150,7 +157,8 @@ static int call_lfa_activate(void *data)
 
 static int activate_fw_image(struct image_props *attrs)
 {
-	struct arm_smccc_res res = { 0 };
+	struct arm_smccc_1_2_regs args = { 0 };
+	struct arm_smccc_1_2_regs res = { 0 };
 	int ret;
 
 	/*
@@ -159,8 +167,10 @@ static int activate_fw_image(struct image_props *attrs)
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
@@ -211,13 +221,16 @@ static ssize_t activation_pending_show(struct kobject *kobj,
 {
 	struct image_props *attrs = container_of(attr, struct image_props,
 					 image_attrs[LFA_ATTR_ACT_PENDING]);
-	struct arm_smccc_res res = { 0 };
+	struct arm_smccc_1_2_regs args = { 0 };
+	struct arm_smccc_1_2_regs res = { 0 };
 
 	/*
 	 * Activation pending status can change anytime thus we need to update
 	 * and return its current value
 	 */
-	arm_smccc_1_1_invoke(LFA_1_0_FN_GET_INVENTORY, attrs->fw_seq_id, &res);
+	args.a0 = LFA_1_0_FN_GET_INVENTORY;
+	args.a1 = attrs->fw_seq_id;
+	arm_smccc_1_2_invoke(&args, &res);
 	if (res.a0 == LFA_SUCCESS)
 		attrs->activation_pending = !!(res.a3 & BIT(1));
 
@@ -298,9 +311,12 @@ static ssize_t cancel_store(struct kobject *kobj, struct kobj_attribute *attr,
 {
 	struct image_props *attrs = container_of(attr, struct image_props,
 						 image_attrs[LFA_ATTR_CANCEL]);
-	struct arm_smccc_res res = { 0 };
+	struct arm_smccc_1_2_regs args = { 0 };
+	struct arm_smccc_1_2_regs res = { 0 };
 
-	arm_smccc_1_1_invoke(LFA_1_0_FN_CANCEL, attrs->fw_seq_id, &res);
+	args.a0 = LFA_1_0_FN_CANCEL;
+	args.a1 = attrs->fw_seq_id;
+	arm_smccc_1_2_invoke(&args, &res);
 
 	/*
 	 * When firmware activation is called with "skip_cpu_rendezvous=1",
@@ -395,14 +411,17 @@ static int create_fw_inventory(char *fw_uuid, int seq_id, u32 image_flags)
 
 static int create_fw_images_tree(void)
 {
-	struct arm_smccc_res res = { 0 };
+	struct arm_smccc_1_2_regs args = { 0 };
+	struct arm_smccc_1_2_regs res = { 0 };
 	struct uuid_regs image_uuid;
 	char image_id_str[40];
 	int ret, num_of_components;
 
 	num_of_components = get_nr_lfa_components();
+	args.a0 = LFA_1_0_FN_GET_INVENTORY;
 	for (int i = 0; i < num_of_components; i++) {
-		arm_smccc_1_1_invoke(LFA_1_0_FN_GET_INVENTORY, i, &res);
+		args.a1 = i; /* fw_seq_id under consideration */
+		arm_smccc_1_2_invoke(&args, &res);
 		if (res.a0 == LFA_SUCCESS) {
 			image_uuid.uuid_lo = res.a1;
 			image_uuid.uuid_hi = res.a2;
@@ -420,10 +439,23 @@ static int create_fw_images_tree(void)
 
 static int __init lfa_init(void)
 {
-	struct arm_smccc_res res = { 0 };
+	struct arm_smccc_1_2_regs args = { 0 };
+	struct arm_smccc_1_2_regs res = { 0 };
 	int err;
 
-	arm_smccc_1_1_invoke(LFA_1_0_FN_GET_VERSION, &res);
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
+	args.a0 = LFA_1_0_FN_GET_VERSION;
+	arm_smccc_1_2_invoke(&args, &res);
 	if (res.a0 == -LFA_NOT_SUPPORTED) {
 		pr_err("Arm Live Firmware activation(LFA): no firmware agent found\n");
 		return -ENODEV;

---

## [3] Vedashree Vidwans — 2025-10-08
*Subject: [RFC PATCH 2/3] firmware: smccc: LFA: refactor, add device node support*

- Add support for LFA device node in the kernel driver. Implement
probe() to register LFA interrupt and threaded interrupt service
function.
- CPUs will be rendezvoused during activation.
- On IRQ, driver will query FW components then triggers activation of
capable and pending components.
- Mutex synchronization is implemented to avoid concurrent LFA updates
through interrupt and sysfs interfaces.
- Refactor LFA CANCEL logic into independent lfa_cancel() function.
- Enhance PRIME/ACTIVATION functions to touch watchdog and implement
timeouts.

Signed-off-by: Vedashree Vidwans <vvidwans@nvidia.com>
---
 drivers/firmware/smccc/lfa_fw.c | 299 ++++++++++++++++++++++++++++----
 1 file changed, 262 insertions(+), 37 deletions(-)

diff --git a/drivers/firmware/smccc/lfa_fw.c b/drivers/firmware/smccc/lfa_fw.c
index 49f7feb6a211b..b36b8d7457c30 100644
--- a/drivers/firmware/smccc/lfa_fw.c
+++ b/drivers/firmware/smccc/lfa_fw.c
@@ -16,7 +16,15 @@
 #include <linux/uuid.h>
 #include <linux/array_size.h>
 #include <linux/list.h>
-
+#include <linux/interrupt.h>
+#include <linux/platform_device.h>
+#include <linux/acpi.h>
+#include <linux/nmi.h>
+#include <linux/ktime.h>
+#include <linux/delay.h>
+#include <linux/mutex.h>
+
+#define DRIVER_NAME	"ARM_LFA"
 #define LFA_ERROR_STRING(name) \
 	[name] = #name
 #undef pr_fmt
@@ -34,6 +42,18 @@
 #define LFA_1_0_FN_ACTIVATE		LFA_1_0_FN(5)
 #define LFA_1_0_FN_CANCEL		LFA_1_0_FN(6)
 
+/* CALL_AGAIN flags (returned in res.a1[0]) */
+#define LFA_PRIME_CALL_AGAIN		BIT(0)
+#define LFA_ACTIVATE_CALL_AGAIN		BIT(0)
+
+/* Prime loop limits, TODO: tune after testing */
+#define LFA_PRIME_BUDGET_US		30000000 /* 30s cap */
+#define LFA_PRIME_POLL_DELAY_US		10       /* 10us between polls */
+
+/* Activation loop limits, TODO: tune after testing */
+#define LFA_ACTIVATE_BUDGET_US		20000000 /* 20s cap */
+#define LFA_ACTIVATE_POLL_DELAY_US	10       /* 10us between polls */
+
 /* LFA return values */
 #define LFA_SUCCESS			0
 #define LFA_NOT_SUPPORTED		1
@@ -114,8 +134,9 @@ static const struct fw_image_uuid {
 };
 
 static struct kobject *lfa_dir;
+static DEFINE_MUTEX(lfa_lock);
 
-static int get_nr_lfa_components(void)
+static unsigned long get_nr_lfa_components(void)
 {
 	struct arm_smccc_1_2_regs args = { 0 };
 	struct arm_smccc_1_2_regs res = { 0 };
@@ -130,11 +151,40 @@ static int get_nr_lfa_components(void)
 	return res.a1;
 }
 
+static int lfa_cancel(void *data)
+{
+	struct image_props *attrs = data;
+	struct arm_smccc_1_2_regs args = { 0 };
+	struct arm_smccc_1_2_regs res = { 0 };
+
+	args.a0 = LFA_1_0_FN_CANCEL;
+	args.a1 = attrs->fw_seq_id;
+	arm_smccc_1_2_invoke(&args, &res);
+
+	/*
+	 * When firmware activation is called with "skip_cpu_rendezvous=1",
+	 * LFA_CANCEL can fail with LFA_BUSY if the activation could not be
+	 * cancelled.
+	 */
+	if (res.a0 == LFA_SUCCESS) {
+		pr_info("Activation cancelled for image %s",
+			attrs->image_name);
+	} else {
+		pr_err("Firmware activation could not be cancelled: %ld",
+		       (long)res.a0);
+		return -EIO;
+	}
+
+	return res.a0;
+}
+
 static int call_lfa_activate(void *data)
 {
 	struct image_props *attrs = data;
 	struct arm_smccc_1_2_regs args = { 0 };
 	struct arm_smccc_1_2_regs res = { 0 };
+	ktime_t end = ktime_add_us(ktime_get(), LFA_ACTIVATE_BUDGET_US);
+	int ret;
 
 	args.a0 = LFA_1_0_FN_ACTIVATE;
 	args.a1 = attrs->fw_seq_id; /* fw_seq_id under consideration */
@@ -148,9 +198,32 @@ static int call_lfa_activate(void *data)
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
@@ -159,8 +232,24 @@ static int activate_fw_image(struct image_props *attrs)
 {
 	struct arm_smccc_1_2_regs args = { 0 };
 	struct arm_smccc_1_2_regs res = { 0 };
+	ktime_t end = ktime_add_us(ktime_get(), LFA_PRIME_BUDGET_US);
 	int ret;
 
+	if (attrs->may_reset_cpu) {
+		pr_err("Firmware component requires unsupported CPU reset");
+		return -EINVAL;
+	}
+
+	/*
+	 * We want to force CPU rendezvous if either cpu_rendezvous or
+	 * cpu_rendezvous_forced is set. The flag value is flipped as
+	 * it is called skip_cpu_rendezvous in the spec.
+	 */
+	if (!(attrs->cpu_rendezvous_forced || attrs->cpu_rendezvous)) {
+		pr_warn("CPU rendezvous is expected to be selected.");
+		return -EAGAIN;
+	}
+
 	/*
 	 * LFA_PRIME/ACTIVATE will return 1 in res.a1 if the firmware
 	 * priming/activation is still in progress. In that case
@@ -169,20 +258,36 @@ static int activate_fw_image(struct image_props *attrs)
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
 
-	if (attrs->cpu_rendezvous_forced || attrs->cpu_rendezvous)
-		ret = stop_machine(call_lfa_activate, attrs, cpu_online_mask);
-	else
-		ret = call_lfa_activate(attrs);
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
+
+	ret = stop_machine(call_lfa_activate, attrs, cpu_online_mask);
+	if (ret != 0)
+		return lfa_cancel(attrs);
 
 	return ret;
 }
@@ -286,23 +391,23 @@ static ssize_t activate_store(struct kobject *kobj, struct kobj_attribute *attr,
 					 image_attrs[LFA_ATTR_ACTIVATE]);
 	int ret;
 
-	if (attrs->may_reset_cpu) {
-		pr_err("Firmware component requires unsupported CPU reset\n");
-
-		return -EINVAL;
+	if (!mutex_trylock(&lfa_lock)) {
+		pr_err("Mutex locked, try again");
+		return -EAGAIN;
 	}
 
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
 
@@ -311,26 +416,11 @@ static ssize_t cancel_store(struct kobject *kobj, struct kobj_attribute *attr,
 {
 	struct image_props *attrs = container_of(attr, struct image_props,
 						 image_attrs[LFA_ATTR_CANCEL]);
-	struct arm_smccc_1_2_regs args = { 0 };
-	struct arm_smccc_1_2_regs res = { 0 };
-
-	args.a0 = LFA_1_0_FN_CANCEL;
-	args.a1 = attrs->fw_seq_id;
-	arm_smccc_1_2_invoke(&args, &res);
+	int ret;
 
-	/*
-	 * When firmware activation is called with "skip_cpu_rendezvous=1",
-	 * LFA_CANCEL can fail with LFA_BUSY if the activation could not be
-	 * cancelled.
-	 */
-	if (res.a0 == LFA_SUCCESS) {
-		pr_info("Activation cancelled for image %s\n",
-			attrs->image_name);
-	} else {
-		pr_err("Firmware activation could not be cancelled: %s\n",
-		       lfa_error_strings[-res.a0]);
-		return -EINVAL;
-	}
+	ret = lfa_cancel(attrs);
+	if (ret != 0)
+		return ret;
 
 	return count;
 }
@@ -418,6 +508,11 @@ static int create_fw_images_tree(void)
 	int ret, num_of_components;
 
 	num_of_components = get_nr_lfa_components();
+	if (num_of_components <= 0) {
+		pr_err("Error getting number of LFA components");
+		return -ENODEV;
+	}
+
 	args.a0 = LFA_1_0_FN_GET_INVENTORY;
 	for (int i = 0; i < num_of_components; i++) {
 		args.a1 = i; /* fw_seq_id under consideration */
@@ -437,6 +532,125 @@ static int create_fw_images_tree(void)
 	return 0;
 }
 
+static int refresh_fw_images_tree(void)
+{
+	int ret;
+	/*
+	 * Ideally, this function should invoke the GET_INVENTORY SMC
+	 * for each firmware image and update the corresponding details
+	 * in the firmware image tree node.
+	 * There are several edge cases to consider:
+	 *    - The number of firmware components may change.
+	 *    - The mapping between firmware sequence IDs and
+	 *      firmware image UUIDs may be modified.
+	 * As a result, it is possible that the firmware image tree nodes
+	 * will require updates. Additionally, GET_INVENTORY SMC provides
+	 * all current and revised information. Therefore, retaining the
+	 * existing fw_images_tree data is not justified. Reconstructing
+	 * the firmware images tree will simplify the code and keep data
+	 * up-to-date.
+	 */
+	// Clean current inventory details
+	clean_fw_images_tree();
+
+	// Update new inventory details
+	ret = create_fw_images_tree();
+	if (ret != 0)
+		kobject_put(lfa_dir);
+
+	return ret;
+}
+
+static irqreturn_t lfa_irq_thread(int irq, void *data)
+{
+	struct image_props *attrs = NULL;
+	int ret;
+
+	mutex_lock(&lfa_lock);
+
+	// Update new inventory details
+	ret = refresh_fw_images_tree();
+	if (ret != 0)
+		goto exit_unlock;
+
+	/*
+	 * Execute PRIME and ACTIVATE for each FW component
+	 * Start from first FW component
+	 */
+	list_for_each_entry(attrs, &lfa_fw_images, image_node) {
+		if ((!attrs->activation_capable) || (!attrs->activation_pending)) {
+			/* LFA not applicable for this FW component, continue to next component */
+			continue;
+		}
+
+		ret = activate_fw_image(attrs);
+		if (ret) {
+			pr_err("Firmware %s activation failed: %s\n",
+				attrs->image_name, lfa_error_strings[-ret]);
+			goto exit_unlock;
+		}
+
+		pr_info("Firmware %s activation succeeded", attrs->image_name);
+	}
+
+	// Update new inventory details
+	ret = refresh_fw_images_tree();
+	if (ret != 0)
+		goto exit_unlock;
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
 	struct arm_smccc_1_2_regs args = { 0 };
@@ -464,22 +678,33 @@ static int __init lfa_init(void)
 	pr_info("Arm Live Firmware Activation (LFA): detected v%ld.%ld\n",
 		res.a0 >> 16, res.a0 & 0xffff);
 
+	err = platform_driver_register(&lfa_driver);
+	if (err < 0)
+		pr_err("Platform driver register failed");
+
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

## [4] Vedashree Vidwans — 2025-10-08
*Subject: [RFC PATCH 3/3] firmware: smccc: LFA: modify activation approach*

Currently, on a LFA IRQ, all activable firmware components are primed
activated sequentially. Modify the approach to prime all firmware
components followed by activation of all components sequentially. This
approach will minimize the time where old and new firmware component
images co-exist.

Signed-off-by: Vedashree Vidwans <vvidwans@nvidia.com>
---
 drivers/firmware/smccc/lfa_fw.c | 74 +++++++++++++++++++++++++++++----
 1 file changed, 66 insertions(+), 8 deletions(-)

diff --git a/drivers/firmware/smccc/lfa_fw.c b/drivers/firmware/smccc/lfa_fw.c
index b36b8d7457c30..dead2282cd04b 100644
--- a/drivers/firmware/smccc/lfa_fw.c
+++ b/drivers/firmware/smccc/lfa_fw.c
@@ -46,6 +46,10 @@
 #define LFA_PRIME_CALL_AGAIN		BIT(0)
 #define LFA_ACTIVATE_CALL_AGAIN		BIT(0)
 
+/* PRIME COMPLETE status */
+#define LFA_PRIME_COMPLETE_FALSE	false
+#define LFA_PRIME_COMPLETE_TRUE		true
+
 /* Prime loop limits, TODO: tune after testing */
 #define LFA_PRIME_BUDGET_US		30000000 /* 30s cap */
 #define LFA_PRIME_POLL_DELAY_US		10       /* 10us between polls */
@@ -104,6 +108,7 @@ struct image_props {
 	bool may_reset_cpu;
 	bool cpu_rendezvous;
 	bool cpu_rendezvous_forced;
+	bool prime_complete;
 	struct kobject *image_dir;
 	struct kobj_attribute image_attrs[LFA_ATTR_NR_IMAGES];
 };
@@ -229,6 +234,27 @@ static int call_lfa_activate(void *data)
 }
 
 static int activate_fw_image(struct image_props *attrs)
+{
+	int ret;
+
+	/*
+	 * We want to force CPU rendezvous if either cpu_rendezvous or
+	 * cpu_rendezvous_forced is set. The flag value is flipped as
+	 * it is called skip_cpu_rendezvous in the spec.
+	 */
+	if (!(attrs->cpu_rendezvous_forced || attrs->cpu_rendezvous)) {
+		pr_warn("CPU rendezvous is expected to be selected.");
+		return -EAGAIN;
+	}
+
+	ret = stop_machine(call_lfa_activate, attrs, cpu_online_mask);
+	if (ret != 0)
+		return lfa_cancel(attrs);
+
+	return ret;
+}
+
+static int prime_fw_image(struct image_props *attrs)
 {
 	struct arm_smccc_1_2_regs args = { 0 };
 	struct arm_smccc_1_2_regs res = { 0 };
@@ -285,10 +311,6 @@ static int activate_fw_image(struct image_props *attrs)
 			return ret;
 	}
 
-	ret = stop_machine(call_lfa_activate, attrs, cpu_online_mask);
-	if (ret != 0)
-		return lfa_cancel(attrs);
-
 	return ret;
 }
 
@@ -396,6 +418,17 @@ static ssize_t activate_store(struct kobject *kobj, struct kobj_attribute *attr,
 		return -EAGAIN;
 	}
 
+	ret = prime_fw_image(attrs);
+	if (ret) {
+		pr_err("Firmware prime failed: %s\n",
+			lfa_error_strings[-ret]);
+		mutex_unlock(&lfa_lock);
+		return -ECANCELED;
+	}
+
+	/* Update prime complete status */
+	attrs->prime_complete = LFA_PRIME_COMPLETE_TRUE;
+
 	ret = activate_fw_image(attrs);
 	if (ret) {
 		pr_err("Firmware activation failed: %s\n",
@@ -469,6 +502,8 @@ static int create_fw_inventory(char *fw_uuid, int seq_id, u32 image_flags)
 	INIT_LIST_HEAD(&attrs->image_node);
 	attrs->image_name = image_name;
 	attrs->cpu_rendezvous_forced = 1;
+	/* Reset prime complete status */
+	attrs->prime_complete = LFA_PRIME_COMPLETE_FALSE;
 	set_image_flags(attrs, seq_id, image_flags);
 
 	/*
@@ -573,16 +608,39 @@ static irqreturn_t lfa_irq_thread(int irq, void *data)
 	if (ret != 0)
 		goto exit_unlock;
 
-	/*
-	 * Execute PRIME and ACTIVATE for each FW component
-	 * Start from first FW component
-	 */
+	/* Execute PRIME for all FW components */
 	list_for_each_entry(attrs, &lfa_fw_images, image_node) {
 		if ((!attrs->activation_capable) || (!attrs->activation_pending)) {
 			/* LFA not applicable for this FW component, continue to next component */
 			continue;
 		}
 
+		ret = prime_fw_image(attrs);
+		if (ret) {
+			pr_err("Firmware %s prime failed: %s\n",
+				attrs->image_name, lfa_error_strings[-ret]);
+			goto exit_unlock;
+		}
+
+		/* Update prime complete status */
+		attrs->prime_complete = LFA_PRIME_COMPLETE_TRUE;
+	}
+
+	/* Execute ACTIVATE for all FW components */
+	list_for_each_entry(attrs, &lfa_fw_images, image_node) {
+		if ((!attrs->activation_capable) || (!attrs->activation_pending)) {
+			/* LFA not applicable for this FW component, continue to next component */
+			continue;
+		}
+
+		if (!attrs->prime_complete) {
+			/*
+			 * ACTIVATE not applicable for this FW component,
+			 * continue to next component
+			 */
+			continue;
+		}
+
 		ret = activate_fw_image(attrs);
 		if (ret) {
 			pr_err("Firmware %s activation failed: %s\n",

---

## [5] Sudeep Holla — 2025-10-09
*Subject: Re: [RFC PATCH 2/3] firmware: smccc: LFA: refactor, add device node
 support*

On Wed, Oct 08, 2025 at 07:09:06PM +0000, Vedashree Vidwans wrote:
> - Add support for LFA device node in the kernel driver. Implement
> probe() to register LFA interrupt and threaded interrupt service

I was expecting to the devicetree binding based on $subject but no.
So this patch can't be reviewed without one.

---

## [6] Salman Nabi — 2025-10-10
*Subject: Re: [RFC PATCH 2/3] firmware: smccc: LFA: refactor, add device node
 support*

Hi Vedashree,

Thank you for sending those pathces over. I just have a few comments.

On 10/8/25 20:09, Vedashree Vidwans wrote:
> - Add support for LFA device node in the kernel driver. Implement
> probe() to register LFA interrupt and threaded interrupt service

The purpose of cpu_rendezvous_forced was to allow firmware components, that dont
require cpu rendezvous, bypass kernel's conservative approach of always requiring
cpu_rendezvous. This was per the feedback on the first LFA RFC patch. If we are
happy forcing cpu rendezvou than I don't see the point of cpu_rendezvous_forced
switch.

> +
>  	/*

This isn't an optimal approach to updating the firmware components. Removing a
directory that a user is currently looking at will still linger around as its
ref count won't get 0. Also, an attribute read/write operation during an
activation for example, reading the activation pending flag will result in
the mutex lock waiting to acquire the lock which will keep the attribute file
around. Trying to remove said object may result in unpredictable behaviour.
We have a WIP patch that is supposed to refresh the data i.e. firmware images
attributes and seq_ids, instead of deleting the objects and re-creating them.
Only firmware images that are removed from the LFA agent following an
activation would be removed.

> +
> +	// Update new inventory details

mutex_lock() can sleep and is unsafe in an interrupt context, mutex_trylock()
doesn't sleep but is still considered illegal in an interrupt context as
mutex_unlock() can still sleep.

> +
> +	// Update new inventory details

According to the LFA specification IIRC the firmware images and their seq_ids
may change following an activation, not after an update that is pending an
activation. Thus the refresh should happen soon after an activation only.

Kind Regards
Salman

> +	if (ret != 0)
> +		goto exit_unlock;

---

## [7] Andre Przywara — 2025-10-11
*Subject: Re: [RFC PATCH 1/3] firmware: smccc: LFA: use smcc 1.2*

On Wed, 8 Oct 2025 19:09:05 +0000
Vedashree Vidwans <vvidwans@nvidia.com> wrote:

Hi Vedashree,

> Update driver to use SMCCC 1.2+ version as mentioned in the LFA spec.

ah, right, good catch, one call is using x4, so this must be the v1.2
calling convention.

Just one small thing below...

> Signed-off-by: Vedashree Vidwans <vvidwans@nvidia.com>
> ---

>  
> -	arm_smccc_1_1_invoke(LFA_1_0_FN_GET_INFO, 0x0, &res);

I wonder if we can share the same struct for both request and reply?
	arm_smccc_1_2_invoke(&args, &args);

Looks like a lot of stack space used for just a few registers.
Same for the other occasions where we just do the smc once.

Cheers,
Andre.

>  	if (res.a0 != LFA_SUCCESS)
>  		return res.a0;

---

## [8] Andre Przywara — 2025-10-11
*Subject: Re: [RFC PATCH 2/3] firmware: smccc: LFA: refactor, add device node
 support*

On Wed, 8 Oct 2025 19:09:06 +0000
Vedashree Vidwans <vvidwans@nvidia.com> wrote:

Hi Vedashree,

thanks for sharing this code, that's much appreciated! I wonder whether
it's possible to split this patch up, as it's doing multiple things at
once, and it's harder to follow, review and comment on.
The bullet points below basically give away how to split this: first do
the refactors and fixes, then add each feature, in a separate patch.

Just one general comment for now ...

> - Add support for LFA device node in the kernel driver. Implement

That "device node" put me off a bit, do you mean you register a platform
device, to connect this to that ACPI node?
I wonder if we can use this new faux device instead of a platform
device, since it's not a real device? Or maybe even query the ACPI or
DT nodes without a device at all, like using of_find_compatible_node()
or something?

Cheers,
Andre

> probe() to register LFA interrupt and threaded interrupt service
> function.

---

## [9] Vedashree Vidwans — 2025-10-13
*Subject: Re: [RFC PATCH 2/3] firmware: smccc: LFA: refactor, add device node
 support*

On 10/9/25 01:13, Sudeep Holla wrote:
> External email: Use caution opening links or attachments
> 

Thank you for your comments, I will include the devicetree binding
in the next iteration.

Regards,
Veda

---

## [10] Vedashree Vidwans — 2025-10-13
*Subject: Re: [RFC PATCH 2/3] firmware: smccc: LFA: refactor, add device node
 support*

On 10/10/25 10:35, Salman Nabi wrote:
> External email: Use caution opening links or attachments
> 
For current situation, enforcing CPU rendezvous appears to be the most 
practical approach for our usecase. I agree that cpu_rendezvous_forced 
switch is redundant but it enforces the situation that kernel can handle.
 From my perspective, it is challenging for kernel driver to reliably 
determine whether any process will use services from the firmware that's 
being updated. We should revisit whether the switch is necessary in the 
future, especially based on requirements, feedback and validation data. >> +
>>        /*
>>         * LFA_PRIME/ACTIVATE will return 1 in res.a1 if the firmware
Okay, I understand.
I will add a placeholder to refresh the fw_images_tree() to unblock rest 
of the changes. I will hold back to use your implementation and/or 
brainstorm more approaches in parallel.>> +
>> +     // Update new inventory details
>> +     ret = create_fw_images_tree();
The lfa_irq_thread() is a thread_fn passed to request_threaded_irq(). 
 From what I understand, thread_fn runs in a process context as a kernel 
thread and therefore can use sleeping locks such as mutex_lock(), 
wait_event() and msleep().>> +
>> +     // Update new inventory details
>> +     ret = refresh_fw_images_tree();
Thank you for pointing that out. If I understand the spec correctly, it 
is possible that number of components can change after an activation and 
so we would have to refresh complete fw_images_tree.
So the flow I would follow for activation is:
1. Get inventory for all FW components
2. PRIME-ACTIVATE first activable component in the list.
3. Go to 1, until no component is pending activation.

Regards,
Veda>> +     if (ret != 0)
>> +             goto exit_unlock;
>> +

---

## [11] Vedashree Vidwans — 2025-10-13
*Subject: Re: [RFC PATCH 1/3] firmware: smccc: LFA: use smcc 1.2*

On 10/10/25 17:02, Andre Przywara wrote:
> External email: Use caution opening links or attachments
> 
Thank you for the suggestion.
Yes, I think using same struct for arguments and results should work.

Regards,
Veda>>        if (res.a0 != LFA_SUCCESS)
>>                return res.a0;
>>

---

## [12] Vedashree Vidwans — 2025-10-13
*Subject: Re: [RFC PATCH 2/3] firmware: smccc: LFA: refactor, add device node
 support*

On 10/10/25 17:03, Andre Przywara wrote:
> On Wed, 8 Oct 2025 19:09:06 +0000
> Vedashree Vidwans <vvidwans@nvidia.com> wrote:
I understand, let me split the patches in next iteration.> Just one 
general comment for now ...
> 
>> - Add support for LFA device node in the kernel driver. Implement
I haven't completely understood your suggestion/question about using a 
faux device. But here is some context.
This patch registers the driver as a platform driver corresponding to 
device "arm,armhf000".
As the spec recommends, we would have a "arm,armhf000" node in 
devicetree with appropriate interrupt and payload information.
The OS will invoke this driver when it finds corresponding device.
Could you please elaborate/add details for your question?

Regards,
Veda>> probe() to register LFA interrupt and threaded interrupt service
>> function.
>> - CPUs will be rendezvoused during activation.

---

## [13] Andre Przywara — 2025-10-14
*Subject: Re: [RFC PATCH 2/3] firmware: smccc: LFA: refactor, add device node
 support*

On Mon, 13 Oct 2025 13:47:33 -0700
Vedashree Vidwans <vvidwans@nvidia.com> wrote:

Hi Veda,

> On 10/10/25 10:35, Salman Nabi wrote:
> > External email: Use caution opening links or attachments

I completely agree that using the CPU rendezvous is the safest option from
the kernel side, but we also got feedback that it's not acceptable to
enforce this for *every* firmware component, as gathering hundreds of
cores just for updating some board controller firmware that does not
provide a kernel interface is not helpful.
Hence we deliberately introduced the cpu_rendezvous_forced file, which
defaults to 1, so out of the box you get the CPU rendezvous behaviour. But
it allows a system administrator to opt out of the rendezvous, just for
this particular firmware component, based on knowledge that the kernel
will be fine. It's kind of a "I know what I am doing" switch, so it's the
admin's responsibility when they screw up the machine in the process.

Cheers,
Andre

>> +
> >>        /*

---

## [14] Salman Nabi — 2025-10-14
*Subject: Re: [RFC PATCH 2/3] firmware: smccc: LFA: refactor, add device node
 support*

Hi Veda,

On 10/13/25 21:47, Vedashree Vidwans wrote:
> On 10/10/25 10:35, Salman Nabi wrote:
>> External email: Use caution opening links or attachments

[...]

>>> +
>>> +     /*

[...]

>>>
>>> +static int refresh_fw_images_tree(void)

Ah I understand, thanks for clarifying that for me.

>>> +     // Update new inventory details
>>> +     ret = refresh_fw_images_tree();

That's a good point, I guess requesting the inventory is how we would get new
information for example, changes to the activation_pending flag.
Just one question, what happens in the event of an activation failure, would
we go into an infinite loop as we try to activate an activation failing
component? I do not know what plans are in place for failed activation via
for example, a BMC interrupt.

Many thanks,
Salman

> Regards,
> Veda>> +     if (ret != 0)

---
