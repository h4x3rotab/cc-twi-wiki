---
title: 'Arm LFA: timeout and ACPI platform driver support'
date: 2026-02-10
last_reply: 2026-02-24
message_count: 6
participants: ['Vedashree Vidwans', 'Trilok Soni', 'Andre Przywara']
---

## [1] Vedashree Vidwans — 2026-02-10

Hello,

(This is an updated version of the [RFC PATCH 0/5] Arm LFA: Improvements
and interrupt support [1], which builds on top of the latest [PATCH 0/1]
Arm Live Firmware activation (LFA) support [2].)

The latest LFA specification [3] updates the interface requirements for
ACPI-based platforms to use the ACPI Notify() signal, and
device-tree-based interface is unspecified. This series focuses on
reworking the LFA driver as an ACPI-backed platform driver, using ACPI
Notify() instead of a dedicated interrupt handler. The LFA core behavior
and sysfs layout remain as implemented by the base driver.

This series contains two incremental changes:
 1. Add a timeout and watchdog touch during LFA operations, to make the
driver more robust in cases where firmware-side prime/activation phases
take longer than expected. 
 2. Register the LFA implementation as a platform driver, layering a
platform driver interface on top of the existing LFA core logic so the
functionality can be instantiated via a platform device. 

Note:
This posting focuses on architectural and implementation improvements
for the LFA driver itself. It assumes that the bugs and issues raised
during review of the original "[PATCH 0/1] Arm Live Firmware activation
(LFA) support” [2] will be addressed directly by the author in that base
series. Once those fixes are in place, this series is intended to layer
on top cleanly.

Testing:
The final integrated driver (base LFA + these additions) has been tested
on Nvidia server platform with Linux kernel v6.16. The sysfs interface
was not exercised as part of this testing. 

Regards,
Veda

[1] https://lore.kernel.org/linux-arm-kernel/20251208221319.1524888-1-vvidwans@nvidia.com/
[2] https://lore.kernel.org/linux-arm-kernel/20260119122729.287522-2-salman.nabi@arm.com/
[3] https://developer.arm.com/documentation/den0147/latest/

Vedashree Vidwans (2):
  firmware: smccc: add timeout, touch wdt
  firmware: smccc: register as platform driver

 drivers/firmware/smccc/lfa_fw.c | 193 ++++++++++++++++++++++++++++----
 1 file changed, 174 insertions(+), 19 deletions(-)

---

## [2] Vedashree Vidwans — 2026-02-10
*Subject: [PATCH 1/2] firmware: smccc: add timeout, touch wdt*

Enhance PRIME/ACTIVATION functions to touch watchdog and implement
timeout mechanism. This update ensures that any potential hangs are
detected promptly and that the LFA process is allocated sufficient
execution time before the watchdog timer expires. These changes improve
overall system reliability by reducing the risk of undetected process
stalls and unexpected watchdog resets.

Signed-off-by: Vedashree Vidwans <vvidwans@nvidia.com>
---
 drivers/firmware/smccc/lfa_fw.c | 40 +++++++++++++++++++++++++++++++++
 1 file changed, 40 insertions(+)

diff --git a/drivers/firmware/smccc/lfa_fw.c b/drivers/firmware/smccc/lfa_fw.c
index da6b54fe1685..b0ace6fc8dac 100644
--- a/drivers/firmware/smccc/lfa_fw.c
+++ b/drivers/firmware/smccc/lfa_fw.c
@@ -17,6 +17,9 @@
 #include <linux/array_size.h>
 #include <linux/list.h>
 #include <linux/mutex.h>
+#include <linux/nmi.h>
+#include <linux/ktime.h>
+#include <linux/delay.h>
 
 #undef pr_fmt
 #define pr_fmt(fmt) "Arm LFA: " fmt
@@ -37,6 +40,14 @@
 #define LFA_PRIME_CALL_AGAIN		BIT(0)
 #define LFA_ACTIVATE_CALL_AGAIN		BIT(0)
 
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
@@ -219,6 +230,7 @@ static int call_lfa_activate(void *data)
 	struct image_props *attrs = data;
 	struct arm_smccc_1_2_regs args = { 0 };
 	struct arm_smccc_1_2_regs res = { 0 };
+	ktime_t end = ktime_add_us(ktime_get(), LFA_ACTIVATE_BUDGET_US);
 
 	args.a0 = LFA_1_0_FN_ACTIVATE;
 	args.a1 = attrs->fw_seq_id; /* fw_seq_id under consideration */
@@ -232,6 +244,8 @@ static int call_lfa_activate(void *data)
 	args.a2 = !(attrs->cpu_rendezvous_forced || attrs->cpu_rendezvous);
 
 	for (;;) {
+		/* Touch watchdog, ACTIVATE shouldn't take longer than watchdog_thresh */
+		touch_nmi_watchdog();
 		arm_smccc_1_2_invoke(&args, &res);
 
 		if ((long)res.a0 < 0) {
@@ -241,6 +255,15 @@ static int call_lfa_activate(void *data)
 		}
 		if (!(res.a1 & LFA_ACTIVATE_CALL_AGAIN))
 			break; /* ACTIVATE successful */
+
+		/* SMC returned with call_again flag set */
+		if (ktime_before(ktime_get(), end)) {
+			udelay(LFA_ACTIVATE_POLL_DELAY_US);
+			continue;
+		}
+
+		pr_err("ACTIVATE for image %s timed out", attrs->image_name);
+		return -ETIMEDOUT;
 	}
 
 	return res.a0;
@@ -290,6 +313,7 @@ static int prime_fw_image(struct image_props *attrs)
 {
 	struct arm_smccc_1_2_regs args = { 0 };
 	struct arm_smccc_1_2_regs res = { 0 };
+	ktime_t end = ktime_add_us(ktime_get(), LFA_PRIME_BUDGET_US);
 	int ret;
 
 	mutex_lock(&lfa_lock);
@@ -317,6 +341,8 @@ static int prime_fw_image(struct image_props *attrs)
 	args.a0 = LFA_1_0_FN_PRIME;
 	args.a1 = attrs->fw_seq_id; /* fw_seq_id under consideration */
 	for (;;) {
+		/* Touch watchdog, PRIME shouldn't take longer than watchdog_thresh */
+		touch_nmi_watchdog();
 		arm_smccc_1_2_invoke(&args, &res);
 
 		if ((long)res.a0 < 0) {
@@ -328,6 +354,20 @@ static int prime_fw_image(struct image_props *attrs)
 		}
 		if (!(res.a1 & LFA_PRIME_CALL_AGAIN))
 			break; /* PRIME successful */
+
+		/* SMC returned with call_again flag set */
+		if (ktime_before(ktime_get(), end)) {
+			udelay(LFA_PRIME_POLL_DELAY_US);
+			continue;
+		}
+
+		pr_err("LFA_PRIME for image %s timed out", attrs->image_name);
+		mutex_unlock(&lfa_lock);
+
+		ret = lfa_cancel(attrs);
+		if (ret != 0)
+			return ret;
+		return -ETIMEDOUT;
 	}
 
 	mutex_unlock(&lfa_lock);

---

## [3] Vedashree Vidwans — 2026-02-10
*Subject: [PATCH 2/2] firmware: smccc: register as platform driver*

- Register the LFA driver as a platform driver corresponding to
'arml0003' ACPI device. The driver will be invoked when the device is
detected on a platform. NOTE: current functionality only available for
ACPI configuration.
- Add functionality to register ACPI notify handler for LFA in the
driver probe().
- When notify handler is invoked, driver will query latest FW component
details and trigger activation of capable and pending FW component in a
loop until all FWs are activated.

ACPI node snippet from LFA spec[1]:
Device (LFA0) {
   Name (_HID, "ARML0003")
   Name (_UID, 0)
}

[1] https://developer.arm.com/documentation/den0147/latest/

Signed-off-by: Vedashree Vidwans <vvidwans@nvidia.com>
---
 drivers/firmware/smccc/lfa_fw.c | 153 ++++++++++++++++++++++++++++----
 1 file changed, 134 insertions(+), 19 deletions(-)

diff --git a/drivers/firmware/smccc/lfa_fw.c b/drivers/firmware/smccc/lfa_fw.c
index b0ace6fc8dac..042de937bf83 100644
--- a/drivers/firmware/smccc/lfa_fw.c
+++ b/drivers/firmware/smccc/lfa_fw.c
@@ -20,7 +20,10 @@
 #include <linux/nmi.h>
 #include <linux/ktime.h>
 #include <linux/delay.h>
+#include <linux/acpi.h>
+#include <linux/platform_device.h>
 
+#define DRIVER_NAME	"ARM_LFA"
 #undef pr_fmt
 #define pr_fmt(fmt) "Arm LFA: " fmt
 
@@ -284,26 +287,7 @@ static int activate_fw_image(struct image_props *attrs)
 		return lfa_cancel(attrs);
 	}
 
-	/*
-	 * Invalidate fw_seq_ids (-1) for all images as the seq_ids and the
-	 * number of firmware images in the LFA agent may change after a
-	 * successful activation attempt. Negate all image flags as well.
-	 */
-	attrs = NULL;
-	list_for_each_entry(attrs, &lfa_fw_images, image_node) {
-		set_image_flags(attrs, -1, 0b1000, 0, 0);
-	}
-
 	update_fw_images_tree();
-
-	/*
-	 * Removing non-valid image directories at the end of an activation.
-	 * We can't remove the sysfs attributes while in the respective
-	 * _store() handler, so have to postpone the list removal to a
-	 * workqueue.
-	 */
-	INIT_WORK(&fw_images_update_work, remove_invalid_fw_images);
-	queue_work(fw_images_update_wq, &fw_images_update_work);
 	mutex_unlock(&lfa_lock);
 
 	return ret;
@@ -627,6 +611,7 @@ static int update_fw_images_tree(void)
 {
 	struct arm_smccc_1_2_regs reg = { 0 };
 	struct uuid_regs image_uuid;
+	struct image_props *attrs;
 	char image_id_str[40];
 	int ret, num_of_components;
 
@@ -636,6 +621,15 @@ static int update_fw_images_tree(void)
 		return -ENODEV;
 	}
 
+	/*
+	 * Invalidate fw_seq_ids (-1) for all images as the seq_ids and the
+	 * number of firmware images in the LFA agent may change after a
+	 * successful activation attempt. Negate all image flags as well.
+	 */
+	list_for_each_entry(attrs, &lfa_fw_images, image_node) {
+		set_image_flags(attrs, -1, 0b1000, 0, 0);
+	}
+
 	for (int i = 0; i < num_of_components; i++) {
 		reg.a0 = LFA_1_0_FN_GET_INVENTORY;
 		reg.a1 = i; /* fw_seq_id under consideration */
@@ -653,9 +647,121 @@ static int update_fw_images_tree(void)
 		}
 	}
 
+	/*
+	 * Removing non-valid image directories at the end of an activation.
+	 * We can't remove the sysfs attributes while in the respective
+	 * _store() handler, so have to postpone the list removal to a
+	 * workqueue.
+	 */
+	INIT_WORK(&fw_images_update_work, remove_invalid_fw_images);
+	queue_work(fw_images_update_wq, &fw_images_update_work);
+
+	return 0;
+}
+
+#if defined(CONFIG_ACPI)
+static void lfa_notify_handler(acpi_handle handle, u32 event, void *data)
+{
+	struct image_props *attrs = NULL;
+	int ret;
+	bool found_activable_image = false;
+
+	/* Get latest FW inventory */
+	mutex_lock(&lfa_lock);
+	ret = update_fw_images_tree();
+	mutex_unlock(&lfa_lock);
+	if (ret != 0) {
+		pr_err("FW images tree update failed");
+		return;
+	}
+
+	/*
+	 * Go through all FW images in a loop and trigger activation
+	 * of all activable and pending images.
+	 */
+	do {
+		/* Reset activable image flag */
+		found_activable_image = false;
+		list_for_each_entry(attrs, &lfa_fw_images, image_node) {
+			if (attrs->fw_seq_id == -1)
+				continue; /* Invalid FW component */
+
+			if ((!attrs->activation_capable) || (!attrs->activation_pending))
+				continue; /* FW component is not activable */
+
+			/*
+			 * Found an image that is activable.
+			 * As the FW images tree is revised after activation, it is
+			 * not ideal to invoke activation from inside
+			 * list_for_each_entry() loop.
+			 * So, set the flasg and exit loop.
+			 */
+			found_activable_image = true;
+			break;
+		}
+
+		if (found_activable_image) {
+			ret = prime_fw_image(attrs);
+			if (ret) {
+				pr_err("Firmware prime failed: %s\n",
+					lfa_error_strings[-ret]);
+				return;
+			}
+
+			ret = activate_fw_image(attrs);
+			if (ret) {
+				pr_err("Firmware activation failed: %s\n",
+					lfa_error_strings[-ret]);
+				return;
+			}
+
+			pr_info("Firmware %s activation succeeded", attrs->image_name);
+		}
+	} while (found_activable_image);
+}
+
+static int lfa_probe(struct platform_device *pdev)
+{
+	acpi_status status;
+	acpi_handle handle = ACPI_HANDLE(&pdev->dev);
+
+	if (!handle)
+		return -ENODEV;
+
+	/* Register notify handler that indicates if LFA updates are available */
+	status = acpi_install_notify_handler(handle,
+		ACPI_DEVICE_NOTIFY, lfa_notify_handler, pdev);
+	if (ACPI_FAILURE(status))
+		return -EIO;
+
 	return 0;
 }
 
+static void lfa_remove(struct platform_device *pdev)
+{
+	acpi_handle handle = ACPI_HANDLE(&pdev->dev);
+
+	if (handle)
+		acpi_remove_notify_handler(handle,
+			ACPI_DEVICE_NOTIFY, lfa_notify_handler);
+}
+
+static const struct acpi_device_id lfa_acpi_ids[] = {
+	{"ARML0003"},
+	{},
+};
+MODULE_DEVICE_TABLE(acpi, lfa_acpi_ids);
+
+static struct platform_driver lfa_driver = {
+	.probe = lfa_probe,
+	.remove = lfa_remove,
+	.driver = {
+		.name = DRIVER_NAME,
+		.acpi_match_table = ACPI_PTR(lfa_acpi_ids),
+	},
+};
+#endif
+
 static int __init lfa_init(void)
 {
 	struct arm_smccc_1_2_regs reg = { 0 };
@@ -679,6 +785,12 @@ static int __init lfa_init(void)
 	pr_info("Live Firmware Activation: detected v%ld.%ld\n",
 		reg.a0 >> 16, reg.a0 & 0xffff);
 
+#if defined(CONFIG_ACPI)
+	err = platform_driver_register(&lfa_driver);
+	if (err < 0)
+		pr_err("Platform driver register failed");
+#endif
+
 	lfa_dir = kobject_create_and_add("lfa", firmware_kobj);
 	if (!lfa_dir)
 		return -ENOMEM;
@@ -703,6 +815,9 @@ static void __exit lfa_exit(void)
 	mutex_unlock(&lfa_lock);
 
 	kobject_put(lfa_dir);
+#if defined(CONFIG_ACPI)
+	platform_driver_unregister(&lfa_driver);
+#endif
 }
 module_exit(lfa_exit);

---

## [4] Trilok Soni — 2026-02-10
*Subject: Re: [PATCH 1/2] firmware: smccc: add timeout, touch wdt*

On 2/10/2026 2:40 PM, Vedashree Vidwans wrote:
> Enhance PRIME/ACTIVATION functions to touch watchdog and implement
> timeout mechanism. This update ensures that any potential hangs are

Do you want to keep this TODO? Your patches are not marked as RFC. 

> +#define LFA_PRIME_BUDGET_US		30000000	/* 30s cap */
> +#define LFA_PRIME_POLL_DELAY_US		10		/* 10us between polls */

Are these values going to be tunable from the userspace or kernel module parameters? 

> +
> +/* Activation loop limits, TODO: tune after testing */

Ditto.

> +#define LFA_ACTIVATE_BUDGET_US		20000000	/* 20s cap */
> +#define LFA_ACTIVATE_POLL_DELAY_US	10		/* 10us between polls */
...

---Trilok Soni

---

## [5] Vedashree Vidwans — 2026-02-10
*Subject: Re: [PATCH 1/2] firmware: smccc: add timeout, touch wdt*

On 2/10/26 15:10, Trilok Soni wrote:
> On 2/10/2026 2:40 PM, Vedashree Vidwans wrote:
>> Enhance PRIME/ACTIVATION functions to touch watchdog and implement

Thanks for pointing this out.

The "TODO: tune after testing" comment was left in by mistake; it should 
not have been included in a non‑RFC posting.

Regarding tunability: the current series uses fixed values, but I agree 
it would be useful to make these configurable. Adding module parameter 
to adjust the timeout values would make it easier to tune them for 
different platforms and workloads.

I’ll address both of these points in the next revision of the series.

Veda

---

## [6] Andre Przywara — 2026-02-24
*Subject: Re: [PATCH 1/2] firmware: smccc: add timeout, touch wdt*

Hi Veda,

On 2/10/26 23:40, Vedashree Vidwans wrote:
> Enhance PRIME/ACTIVATION functions to touch watchdog and implement
> timeout mechanism. This update ensures that any potential hangs are

Many thanks for that, I think it's a very good idea to take care of the 
watchdog and to avoid an infinite loop in the AGAIN case.
I have some comments about some details below ....

> Signed-off-by: Vedashree Vidwans <vvidwans@nvidia.com>
> ---

I don't think we should wait here at all, and definitely not with 
udelay: https://docs.kernel.org/timers/delay_sleep_functions.html

Instead we should move the "call again" (and timeout) mechanism out of 
this function, into activate_fw_image(), so that we exit the 
stop_machine(). Otherwise we would still block everything. Doing it 
there, where we should be preemptible, would give the kernel a chance to 
do some housekeeping. If there is nothing for the kernel to do, then I 
think it's fine to immediately call lfa_activate() again, after a 
cond_resched(), for instance.

> +			continue;
> +		}

same comment here, please no udelay().
This should also avoid the discussion about the exact values of the 
sleep periods.
I'd just have one generous timeout (a few seconds, basically what your 
BUDGET values do above), to avoid looping forever in case of a firmware 
bug, for instance.

Cheers,
Andre

> +			continue;
> +		}

---
