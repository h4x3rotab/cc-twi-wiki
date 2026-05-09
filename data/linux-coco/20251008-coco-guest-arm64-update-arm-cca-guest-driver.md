---
title: 'coco: guest: arm64: Update ARM CCA guest driver'
date: 2025-10-08
last_reply: 2025-10-10
message_count: 8
participants: ['Aneesh Kumar K.V (Arm)', 'Jonathan Cameron', 'dan.j.williams@intel.com', 'Jeremy Linton', 'kernel test robot']
---

## [1] Aneesh Kumar K.V (Arm) — 2025-10-08

Make preparatory updates to the ARM CCA guest driver:

 - Switch from using a platform device to a faux device (based on
   feedback in [1])
 - Rename the device from `arm-cca-dev` to `arm-rsi-dev`, so that the
   host driver can register an equivalent `arm-rmi-dev`

These changes are purely structural and introduce no new functionality.
Subsequent patches will extend this driver to add guest device
assignment support.

[1] https://lore.kernel.org/all/2025073035-bulginess-rematch-b92e@gregkh

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
NOTE:
This patch is sent early outside the patchseries to avoid userspace from
depending on the presence of the newly introduced platform device.
The platform device was added in v6.14-rc1. 

 arch/arm64/include/asm/rsi.h                  |  2 +-
 arch/arm64/kernel/rsi.c                       | 15 -----
 drivers/virt/coco/arm-cca-guest/Makefile      |  3 +
 .../{arm-cca-guest.c => arm-cca.c}            | 65 +++++++++++--------
 4 files changed, 41 insertions(+), 44 deletions(-)
 rename drivers/virt/coco/arm-cca-guest/{arm-cca-guest.c => arm-cca.c} (85%)

diff --git a/arch/arm64/include/asm/rsi.h b/arch/arm64/include/asm/rsi.h
index b42aeac05340..26ef6143562b 100644
--- a/arch/arm64/include/asm/rsi.h
+++ b/arch/arm64/include/asm/rsi.h
@@ -10,7 +10,7 @@
 #include <linux/jump_label.h>
 #include <asm/rsi_cmds.h>
 
-#define RSI_PDEV_NAME "arm-cca-dev"
+#define RSI_DEV_NAME "arm-rsi-dev"
 
 DECLARE_STATIC_KEY_FALSE(rsi_present);
 
diff --git a/arch/arm64/kernel/rsi.c b/arch/arm64/kernel/rsi.c
index ce4778141ec7..569ef08750e5 100644
--- a/arch/arm64/kernel/rsi.c
+++ b/arch/arm64/kernel/rsi.c
@@ -140,18 +140,3 @@ void __init arm64_rsi_init(void)
 
 	static_branch_enable(&rsi_present);
 }
-
-static struct platform_device rsi_dev = {
-	.name = RSI_PDEV_NAME,
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
diff --git a/drivers/virt/coco/arm-cca-guest/Makefile b/drivers/virt/coco/arm-cca-guest/Makefile
index 69eeba08e98a..609462ea9438 100644
--- a/drivers/virt/coco/arm-cca-guest/Makefile
+++ b/drivers/virt/coco/arm-cca-guest/Makefile
@@ -1,2 +1,5 @@
 # SPDX-License-Identifier: GPL-2.0-only
+#
 obj-$(CONFIG_ARM_CCA_GUEST) += arm-cca-guest.o
+
+arm-cca-guest-$(CONFIG_TSM) +=  arm-cca.o
diff --git a/drivers/virt/coco/arm-cca-guest/arm-cca-guest.c b/drivers/virt/coco/arm-cca-guest/arm-cca.c
similarity index 85%
rename from drivers/virt/coco/arm-cca-guest/arm-cca-guest.c
rename to drivers/virt/coco/arm-cca-guest/arm-cca.c
index 0c9ea24a200c..89d9e7f8eb5d 100644
--- a/drivers/virt/coco/arm-cca-guest/arm-cca-guest.c
+++ b/drivers/virt/coco/arm-cca-guest/arm-cca.c
@@ -1,8 +1,9 @@
 // SPDX-License-Identifier: GPL-2.0-only
 /*
- * Copyright (C) 2023 ARM Ltd.
+ * Copyright (C) 2025 ARM Ltd.
  */
 
+#include <linux/device/faux.h>
 #include <linux/arm-smccc.h>
 #include <linux/cc_platform.h>
 #include <linux/kernel.h>
@@ -181,52 +182,60 @@ static int arm_cca_report_new(struct tsm_report *report, void *data)
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
+static int cca_tsm_probe(struct faux_device *fdev)
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
+
+	ret = devm_add_action_or_reset(&fdev->dev, unregister_cca_tsm_report, NULL);
+	if (ret < 0) {
+		pr_err("Error %d registering devm action\n", ret);
+		unregister_cca_tsm_report(NULL);
+		return ret;
+	}
 
 	return ret;
 }
-module_init(arm_cca_guest_init);
 
-/**
- * arm_cca_guest_exit - unregister with the Trusted Security Module (TSM)
- * interface.
- */
-static void __exit arm_cca_guest_exit(void)
+static struct faux_device *cca_tsm;
+
+static const struct faux_device_ops cca_device_ops = {
+	.probe = cca_tsm_probe,
+};
+
+static int __init cca_tsm_init(void)
 {
-	tsm_report_unregister(&arm_cca_tsm_ops);
+	cca_tsm = faux_device_create(RSI_DEV_NAME, NULL, &cca_device_ops);
+	if (!cca_tsm)
+		return -ENOMEM;
+	return 0;
 }
-module_exit(arm_cca_guest_exit);
+module_init(cca_tsm_init);
 
-/* modalias, so userspace can autoload this module when RSI is available */
-static const struct platform_device_id arm_cca_match[] __maybe_unused = {
-	{ RSI_PDEV_NAME, 0},
-	{ }
-};
+static void __exit cca_tsm_exit(void)
+{
+	faux_device_destroy(cca_tsm);
+}
+module_exit(cca_tsm_exit);
 
-MODULE_DEVICE_TABLE(platform, arm_cca_match);
 MODULE_AUTHOR("Sami Mujawar <sami.mujawar@arm.com>");
 MODULE_DESCRIPTION("Arm CCA Guest TSM Driver");
 MODULE_LICENSE("GPL");

---

## [2] Aneesh Kumar K.V — 2025-10-09
*Subject: Re: [PATCH] coco: guest: arm64: Update ARM CCA guest driver*

"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> writes:

> Make preparatory updates to the ARM CCA guest driver:
>

I noticed that, this will break autoloading of the driver. 

> Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
> ---

---

## [3] Jonathan Cameron — 2025-10-09
*Subject: Re: [PATCH] coco: guest: arm64: Update ARM CCA guest driver*

On Wed,  8 Oct 2025 18:57:58 +0530
"Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> wrote:

> Make preparatory updates to the ARM CCA guest driver:
> 

Slight preference for:
Link: https://lore.kernel.org/all/2025073035-bulginess-rematch-b92e@gregkh #1
> Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
> ---

A few trivial things inline. With those in mind.
Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>

> diff --git a/drivers/virt/coco/arm-cca-guest/Makefile b/drivers/virt/coco/arm-cca-guest/Makefile
> index 69eeba08e98a..609462ea9438 100644

Unrelated change. I'd drop it.

>  obj-$(CONFIG_ARM_CCA_GUEST) += arm-cca-guest.o
> +

extra space after = seems a bit odd.

> diff --git a/drivers/virt/coco/arm-cca-guest/arm-cca-guest.c b/drivers/virt/coco/arm-cca-guest/arm-cca.c
> similarity index 85%

I'd expect a date range rather than updating copyright for whole file
like this. The untouched bit will still be 2023 era code.

>   */

> +static int cca_tsm_probe(struct faux_device *fdev)
>  {

I believe (not checked today) that devm_add_action_or_reset() can only fail
with -ENOMEM due to an allocation failure and we generally don't print
extra error messages if that happens.
So I would drop this pr_err.

> +		unregister_cca_tsm_report(NULL);
> +		return ret;

---

## [4] Jonathan Cameron — 2025-10-09
*Subject: Re: [PATCH] coco: guest: arm64: Update ARM CCA guest driver*

On Thu, 09 Oct 2025 12:43:49 +0530
Aneesh Kumar K.V <aneesh.kumar@kernel.org> wrote:

> "Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org> writes:
> 

Ah indeed.  You'd need to arrange for the arch code to call the init()
directly (possibly arch_initcall() as before or maybe directly from
arm64_rsi_init), which makes it tricky to do in a module as there
is nothing to kick off module autoloading. You could kick that off
explicitly but that's a bit ugly.

Jonathan

---

## [5] dan.j.williams@intel.com — 2025-10-09
*Subject: Re: [PATCH] coco: guest: arm64: Update ARM CCA guest driver*

Jonathan Cameron wrote:
> On Thu, 09 Oct 2025 12:43:49 +0530
> Aneesh Kumar K.V <aneesh.kumar@kernel.org> wrote:

Does ARM64 not have the equivalent of MODULE_DEVICE_TABLE(x86cpu, ...)?

---

## [6] Jeremy Linton — 2025-10-10
*Subject: Re: [PATCH] coco: guest: arm64: Update ARM CCA guest driver*

Hi,

Hi,

On 10/9/25 9:24 PM, dan.j.williams@intel.com wrote:
> Jonathan Cameron wrote:
>> On Thu, 09 Oct 2025 12:43:49 +0530

No, it doesn't. There is a hwcap based method, but that requires 
allocating a hwcap.

---

## [7] kernel test robot — 2025-10-10
*Subject: Re: [PATCH] coco: guest: arm64: Update ARM CCA guest driver*

Hi Aneesh,

kernel test robot noticed the following build errors:

[auto build test ERROR on arm64/for-next/core]
[also build test ERROR on arm/for-next arm/fixes kvmarm/next soc/for-next linus/master v6.17 next-20251009]
[If your patch is applied to the wrong git tree, kindly drop us a note.
And when submitting patch, we suggest to use '--base' as documented in
https://git-scm.com/docs/git-format-patch#_base_tree_information]

url:    https://github.com/intel-lab-lkp/linux/commits/Aneesh-Kumar-K-V-Arm/coco-guest-arm64-Update-ARM-CCA-guest-driver/20251009-203207
base:   https://git.kernel.org/pub/scm/linux/kernel/git/arm64/linux.git for-next/core
patch link:    https://lore.kernel.org/r/20251008132758.784275-1-aneesh.kumar%40kernel.org
patch subject: [PATCH] coco: guest: arm64: Update ARM CCA guest driver
config: arm64-allmodconfig (https://download.01.org/0day-ci/archive/20251010/202510102121.hLzgHTck-lkp@intel.com/config)
compiler: clang version 19.1.7 (https://github.com/llvm/llvm-project cd708029e0b2869e80abe31ddb175f7c35361f90)
reproduce (this is a W=1 build): (https://download.01.org/0day-ci/archive/20251010/202510102121.hLzgHTck-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202510102121.hLzgHTck-lkp@intel.com/

All errors (new ones prefixed by >>):

>> ld.lld: error: cannot open drivers/virt/coco/arm-cca-guest/: Is a directory

---

## [8] Jeremy Linton — 2025-10-10
*Subject: Re: [PATCH] coco: guest: arm64: Update ARM CCA guest driver*

On 10/8/25 8:27 AM, Aneesh Kumar K.V (Arm) wrote:
> Make preparatory updates to the ARM CCA guest driver:
> 


At this point, changing the platform device name also breaks systemd's 
confidential vm detection, because its using this device name as the 
first step.


> 
>   arch/arm64/include/asm/rsi.h                  |  2 +-

---
