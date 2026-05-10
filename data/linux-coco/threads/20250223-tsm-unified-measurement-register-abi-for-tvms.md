---
title: 'tsm: Unified Measurement Register ABI for TVMs'
date: 2025-02-23
last_reply: 2025-03-19
message_count: 15
participants: ['Cedric Xing', 'Jianxiong Gao', 'Huang, Kai', 'Sathyanarayanan Kuppuswamy', 'James Bottomley', 'Dionna Amalie Glaze']
---

## [1] Cedric Xing — 2025-02-23

NOTE: This patch series introduces the Measurement Register (MR) ABI, and
is a continuation of the RFC series on the same topic [1].

This patch series adds a unified interface to the TSM core, allowing TVM
(TEE VM) guest drivers to expose measurement registers (MRs) as attributes
(files) in sysfs. With this interface, applications can read and write
(extend) MRs like regular files, enabling usages like configuration
verification (e.g., verifying a TVM's configuration against digests stored
in static/immutable MRs like MRCONFIGID on TDX or HOSTDATA on SEV) and
runtime measurements (e.g., extending the measurement of a container image
to an RTMR before running it).

Patches included in this series:

- Patch 1 adds TSM APIs for TVM guest drivers to register/expose MRs
  through sysfs.
- Patch 2 provides a sample module demonstrating the usage of the new TSM
  APIs.
- The remaining patches update the TDX guest driver to expose TDX MRs
  through the new TSM APIs.

[1]: https://lore.kernel.org/linux-coco/20241210-tsm-rtmr-v3-0-5997d4dbda73@intel.com/

Signed-off-by: Cedric Xing <cedric.xing@intel.com>
---
Changes in v2:
- Added TSM_MR_MAXBANKS Kconfig option
- Updated Kconfig dependency for TSM_REPORTS
- Updated comments in include/linux/tsm.h
- Updated drivers/virt/coco/tsm-mr.c to use `IS_BUILTIN()` for determining
  if static buffer addresses can be converted to GPAs by `virt_to_phys()`
- Renamed function `tdx_mcall_rtmr_extend()` -> `tdx_mcall_extend_rtmr()`
- Link to v1: https://lore.kernel.org/r/20250212-tdx-rtmr-v1-0-9795dc49e132@intel.com

---
Cedric Xing (4):
      tsm: Add TVM Measurement Register support
      tsm: Add TSM measurement sample code
      x86/tdx: Add tdx_mcall_extend_rtmr() interface
      x86/tdx: Expose TDX MRs through TSM sysfs interface

 Documentation/ABI/testing/sysfs-kernel-tsm |  20 ++
 MAINTAINERS                                |   3 +-
 arch/x86/coco/tdx/tdx.c                    |  36 +++
 arch/x86/include/asm/shared/tdx.h          |   1 +
 arch/x86/include/asm/tdx.h                 |   2 +
 drivers/virt/coco/Kconfig                  |  17 +-
 drivers/virt/coco/Makefile                 |   2 +
 drivers/virt/coco/tdx-guest/Kconfig        |  24 +-
 drivers/virt/coco/tdx-guest/tdx-guest.c    | 115 +++++++++
 drivers/virt/coco/{tsm.c => tsm-core.c}    |   6 +-
 drivers/virt/coco/tsm-mr.c                 | 383 +++++++++++++++++++++++++++++
 include/linux/tsm.h                        |  65 +++++
 samples/Kconfig                            |  13 +
 samples/Makefile                           |   1 +
 samples/tsm/Makefile                       |   2 +
 samples/tsm/tsm_mr_sample.c                | 107 ++++++++
 16 files changed, 789 insertions(+), 8 deletions(-)
---
base-commit: d082ecbc71e9e0bf49883ee4afd435a77a5101b6
change-id: 20250209-tdx-rtmr-255479667146

Best regards,

---

## [2] Cedric Xing — 2025-02-23
*Subject: [PATCH v2 1/4] tsm: Add TVM Measurement Register support*

Add new TSM APIs for TVM guest drivers to register and expose measurement
registers (MRs) as sysfs attributes (files).

New TSM APIs:

- `tsm_register_measurement(struct tsm_measurement *)`: Register a set of
  MRs with the TSM core.
- `tsm_unregister_measurement(struct tsm_measurement *)`: Unregister a
  previously registered set of MRs.

These APIs are centered around `struct tsm_measurement`, which includes an
array of `struct tsm_measurement_register`s with properties
(`tsm_measurement_register::mr_flags`) like *Readable* (`TSM_MR_F_R`) and
*Extensible* (`TSM_MR_F_X`). For details, see include/linux/tsm.h.

Upon successful registration, the TSM core exposes MRs in sysfs at
/sys/kernel/tsm/MR_PROVIDER/, where MR_PROVIDER is the measurement
provider's name (`tsm_measurement::name`). Each MR is accessible either as
a file (/sys/kernel/tsm/MR_PROVIDER/MR_NAME contains the MR value) or a
directory (/sys/kernel/tsm/MR_PROVIDER/MR_NAME/HASH/digest contains the MR
value) depending on whether `TSM_MR_F_F` is set or cleared (in
`tsm_measurement_register::mr_flags`). MR_NAME is the name
(`tsm_measurement_register::mr_name`) of the MR, while HASH is the hash
algorithm (`tsm_measurement_register::mr_hash`) name in the latter case.

*Crypto Agility* is supported by merging independent MRs with a common name
into a single directory, each represented by its HASH/digest file. Note
that HASH must be distinct or behavior is undefined.

Signed-off-by: Cedric Xing <cedric.xing@intel.com>
---
 Documentation/ABI/testing/sysfs-kernel-tsm |  20 ++
 MAINTAINERS                                |   2 +-
 drivers/virt/coco/Kconfig                  |  17 +-
 drivers/virt/coco/Makefile                 |   2 +
 drivers/virt/coco/{tsm.c => tsm-core.c}    |   6 +-
 drivers/virt/coco/tsm-mr.c                 | 383 +++++++++++++++++++++++++++++
 include/linux/tsm.h                        |  65 +++++
 7 files changed, 492 insertions(+), 3 deletions(-)

diff --git a/Documentation/ABI/testing/sysfs-kernel-tsm b/Documentation/ABI/testing/sysfs-kernel-tsm
new file mode 100644
index 000000000000..99735cf4da5c
--- /dev/null
+++ b/Documentation/ABI/testing/sysfs-kernel-tsm
@@ -0,0 +1,20 @@
+What:		/sys/kernel/tsm/<measurement_provider>/<register>
+Date:		February 2025
+Contact:	Cedric Xing <cedric.xing@intel.com>.
+Description:
+		This file contains the value of the measurement register
+		<register>. Depending on the CC architecture, this file may be
+		writable, in which case the value written will be the new value
+		of <register>. Each write must start at the beginning and be of
+		the same size as the file. Partial writes are not permitted.
+
+What:		/sys/kernel/tsm/<measurement_provider>/<register>/<hash>/digest
+Date:		February 2025
+Contact:	Cedric Xing <cedric.xing@intel.com>.
+Description:
+		This file contains the value of the measurement register
+		<register>. Depending on the CC architecture, this file may be
+		writable, in which case any value written may be extended to
+		<register> using <hash>. Each write must start at the beginning
+		and be of the same size as the file. Partial writes are not
+		permitted.
diff --git a/MAINTAINERS b/MAINTAINERS
index 4ff26fa94895..a5eef4c7234c 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -24104,7 +24104,7 @@ M:	Dan Williams <dan.j.williams@intel.com>
 L:	linux-coco@lists.linux.dev
 S:	Maintained
 F:	Documentation/ABI/testing/configfs-tsm
-F:	drivers/virt/coco/tsm.c
+F:	drivers/virt/coco/tsm*.c
 F:	include/linux/tsm.h
 
 TRUSTED SERVICES TEE DRIVER
diff --git a/drivers/virt/coco/Kconfig b/drivers/virt/coco/Kconfig
index ff869d883d95..3fa38fd731b9 100644
--- a/drivers/virt/coco/Kconfig
+++ b/drivers/virt/coco/Kconfig
@@ -5,7 +5,22 @@
 
 config TSM_REPORTS
 	select CONFIGFS_FS
-	tristate
+	select CRYPTO_HASH_INFO
+	select CRYPTO
+	tristate "Trusted Security Module (TSM) support"
+
+if TSM_REPORTS
+
+config TSM_MR_MAXBANKS
+	int "Max number of banks of Measurement Registers"
+	range 1 8
+	default 1
+	help
+	  A "bank" is a group of MRs that use the same hash algorithm. This
+	  option specifies the maximal number of banks each Measurement
+	  Register (MR) can support.
+
+endif
 
 source "drivers/virt/coco/efi_secret/Kconfig"
 
diff --git a/drivers/virt/coco/Makefile b/drivers/virt/coco/Makefile
index c3d07cfc087e..4b108d8df1bd 100644
--- a/drivers/virt/coco/Makefile
+++ b/drivers/virt/coco/Makefile
@@ -2,6 +2,8 @@
 #
 # Confidential computing related collateral
 #
+tsm-y				+= tsm-core.o tsm-mr.o
+
 obj-$(CONFIG_TSM_REPORTS)	+= tsm.o
 obj-$(CONFIG_EFI_SECRET)	+= efi_secret/
 obj-$(CONFIG_ARM_PKVM_GUEST)	+= pkvm-guest/
diff --git a/drivers/virt/coco/tsm.c b/drivers/virt/coco/tsm-core.c
similarity index 99%
rename from drivers/virt/coco/tsm.c
rename to drivers/virt/coco/tsm-core.c
index 9432d4e303f1..ab5269db9c13 100644
--- a/drivers/virt/coco/tsm.c
+++ b/drivers/virt/coco/tsm-core.c
@@ -476,6 +476,9 @@ int tsm_unregister(const struct tsm_ops *ops)
 }
 EXPORT_SYMBOL_GPL(tsm_unregister);
 
+int tsm_mr_init(void);
+void tsm_mr_exit(void);
+
 static struct config_group *tsm_report_group;
 
 static int __init tsm_init(void)
@@ -497,12 +500,13 @@ static int __init tsm_init(void)
 	}
 	tsm_report_group = tsm;
 
-	return 0;
+	return tsm_mr_init();
 }
 module_init(tsm_init);
 
 static void __exit tsm_exit(void)
 {
+	tsm_mr_exit();
 	configfs_unregister_default_group(tsm_report_group);
 	configfs_unregister_subsystem(&tsm_configfs);
 }
diff --git a/drivers/virt/coco/tsm-mr.c b/drivers/virt/coco/tsm-mr.c
new file mode 100644
index 000000000000..8a96b2a78869
--- /dev/null
+++ b/drivers/virt/coco/tsm-mr.c
@@ -0,0 +1,383 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/* Copyright(c) 2024-2025 Intel Corporation. All rights reserved. */
+
+#define pr_fmt(fmt) KBUILD_MODNAME ": " fmt
+
+#include <crypto/hash_info.h>
+#include <linux/kobject.h>
+#include <linux/module.h>
+#include <linux/slab.h>
+#include <linux/tsm.h>
+
+int tsm_mr_init(void);
+void tsm_mr_exit(void);
+
+enum tmr_dir_battr_index {
+	TMR_DIR_BA_DIGEST,
+	TMR_DIR_BA__COUNT,
+};
+
+struct tmr_dir {
+	struct kobject kobj;
+	struct bin_attribute battrs[CONFIG_TSM_MR_MAXBANKS][TMR_DIR_BA__COUNT];
+	int algo;
+};
+
+struct tmr_provider {
+	struct kset kset;
+	struct rw_semaphore rwsem;
+	struct bin_attribute *mrfiles;
+	struct tsm_measurement *tmr;
+	bool in_sync;
+};
+
+static inline struct tmr_provider *tmr_mr_to_provider(const struct tsm_measurement_register *mr,
+						      struct kobject *kobj)
+{
+	if (mr->mr_flags & TSM_MR_F_F)
+		return container_of(kobj, struct tmr_provider, kset.kobj);
+	else
+		return container_of(kobj->kset, struct tmr_provider, kset);
+}
+
+static inline int tmr_call_refresh(struct tmr_provider *pvd,
+				   const struct tsm_measurement_register *mr)
+{
+	int rc;
+
+	rc = pvd->tmr->refresh(pvd->tmr, mr);
+	if (rc)
+		pr_warn("%s.refresh(%s) failed %d\n", kobject_name(&pvd->kset.kobj), mr->mr_name,
+			rc);
+	return rc;
+}
+
+static inline int tmr_call_extend(struct tmr_provider *pvd,
+				  const struct tsm_measurement_register *mr, const u8 *data)
+{
+	int rc;
+
+	rc = pvd->tmr->extend(pvd->tmr, mr, data);
+	if (rc)
+		pr_warn("%s.extend(%s) failed %d\n", kobject_name(&pvd->kset.kobj), mr->mr_name,
+			rc);
+	return rc;
+}
+
+static ssize_t tmr_digest_read(struct file *filp, struct kobject *kobj, struct bin_attribute *attr,
+			       char *buffer, loff_t off, size_t count)
+{
+	const struct tsm_measurement_register *mr;
+	struct tmr_provider *pvd;
+	int rc;
+
+	if (off < 0 || off > attr->size)
+		return -EINVAL;
+
+	count = min(count, attr->size - (size_t)off);
+	if (!count)
+		return count;
+
+	mr = attr->private;
+	pvd = tmr_mr_to_provider(mr, kobj);
+	rc = down_read_interruptible(&pvd->rwsem);
+	if (rc)
+		return rc;
+
+	/*
+	 * pvd->in_sync indicates if any MRs have been written/extended since the last
+	 * pvd->refresh() call. When pvd->in_sync is false, pvd->refresh() is necessary to sync the
+	 * cached values of all live (L) MRs with the underlying hardware.
+	 */
+	if ((mr->mr_flags & TSM_MR_F_L) && !pvd->in_sync) {
+		up_read(&pvd->rwsem);
+
+		rc = down_write_killable(&pvd->rwsem);
+		if (rc)
+			return rc;
+
+		if (!pvd->in_sync) {
+			rc = tmr_call_refresh(pvd, mr);
+			pvd->in_sync = !rc;
+		}
+
+		downgrade_write(&pvd->rwsem);
+	}
+
+	if (!rc)
+		memcpy(buffer, mr->mr_value + off, count);
+
+	up_read(&pvd->rwsem);
+	return rc ?: count;
+}
+
+static ssize_t tmr_digest_write(struct file *filp, struct kobject *kobj, struct bin_attribute *attr,
+				char *buffer, loff_t off, size_t count)
+{
+	const struct tsm_measurement_register *mr;
+	struct tmr_provider *pvd;
+	ssize_t rc;
+
+	if (off != 0 || count != attr->size)
+		return -EINVAL;
+
+	mr = attr->private;
+	pvd = tmr_mr_to_provider(mr, kobj);
+	rc = down_write_killable(&pvd->rwsem);
+	if (rc)
+		return rc;
+
+	if (mr->mr_flags & TSM_MR_F_X)
+		rc = tmr_call_extend(pvd, mr, buffer);
+	else
+		memcpy(mr->mr_value, buffer, count);
+
+	// clear pvd->in_sync so the next read from any live (L) MR will trigger pvd->refresh()
+	if (!rc)
+		pvd->in_sync = false;
+
+	up_write(&pvd->rwsem);
+	return rc ?: count;
+}
+
+static void tmr_dir_release(struct kobject *kobj)
+{
+	struct tmr_dir *mrd;
+
+	mrd = container_of(kobj, typeof(*mrd), kobj);
+	kfree(mrd);
+}
+
+static const struct kobj_type tmr_dir_ktype = {
+	.release = tmr_dir_release,
+	.sysfs_ops = &kobj_sysfs_ops,
+};
+
+static struct tmr_dir *tmr_dir_create(const struct tsm_measurement_register *mr,
+				      struct tmr_provider *pvd)
+{
+	struct kobject *kobj;
+	struct tmr_dir *mrd;
+
+	kobj = kset_find_obj(&pvd->kset, mr->mr_name);
+	if (kobj) {
+		mrd = container_of(kobj, typeof(*mrd), kobj);
+		kobject_put(kobj);
+		if (++mrd->algo >= CONFIG_TSM_MR_MAXBANKS) {
+			--mrd->algo;
+			return ERR_PTR(-ENOSPC);
+		}
+	} else {
+		int rc;
+
+		mrd = kzalloc(sizeof(*mrd), GFP_KERNEL);
+		if (!mrd)
+			return ERR_PTR(-ENOMEM);
+
+		mrd->kobj.kset = &pvd->kset;
+		rc = kobject_init_and_add(&mrd->kobj, &tmr_dir_ktype, NULL, "%s", mr->mr_name);
+		if (rc) {
+			kfree(mrd);
+			return ERR_PTR(rc);
+		}
+	}
+
+	sysfs_bin_attr_init(&mrd->battrs[mrd->algo][TMR_DIR_BA_DIGEST]);
+	mrd->battrs[mrd->algo][TMR_DIR_BA_DIGEST].attr.name = "digest";
+	if (mr->mr_flags & TSM_MR_F_W)
+		mrd->battrs[mrd->algo][TMR_DIR_BA_DIGEST].attr.mode |= S_IWUSR | S_IWGRP;
+	if (mr->mr_flags & TSM_MR_F_R)
+		mrd->battrs[mrd->algo][TMR_DIR_BA_DIGEST].attr.mode |= S_IRUGO;
+
+	mrd->battrs[mrd->algo][TMR_DIR_BA_DIGEST].size = mr->mr_size;
+	mrd->battrs[mrd->algo][TMR_DIR_BA_DIGEST].read = tmr_digest_read;
+	mrd->battrs[mrd->algo][TMR_DIR_BA_DIGEST].write = tmr_digest_write;
+	mrd->battrs[mrd->algo][TMR_DIR_BA_DIGEST].private = (void *)mr;
+
+	return mrd;
+}
+
+static void tmr_provider_release(struct kobject *kobj)
+{
+	struct tmr_provider *pvd;
+
+	pvd = container_of(kobj, typeof(*pvd), kset.kobj);
+	if (!WARN_ON(!list_empty(&pvd->kset.list))) {
+		kfree(pvd->mrfiles);
+		kfree(pvd);
+	}
+}
+
+static const struct kobj_type _mr_provider_ktype = {
+	.release = tmr_provider_release,
+	.sysfs_ops = &kobj_sysfs_ops,
+};
+
+static struct kset *tmr_sysfs_root;
+
+static struct tmr_provider *tmr_provider_create(struct tsm_measurement *tmr)
+{
+	struct tmr_provider *pvd __free(kfree);
+	int rc;
+
+	pvd = kzalloc(sizeof(*pvd), GFP_KERNEL);
+	if (!pvd)
+		return ERR_PTR(-ENOMEM);
+
+	if (!tmr->name || !tmr->mrs || !tmr->refresh || !tmr->extend)
+		return ERR_PTR(-EINVAL);
+
+	rc = kobject_set_name(&pvd->kset.kobj, "%s", tmr->name);
+	if (rc)
+		return ERR_PTR(rc);
+
+	pvd->kset.kobj.kset = tmr_sysfs_root;
+	pvd->kset.kobj.ktype = &_mr_provider_ktype;
+	pvd->tmr = tmr;
+
+	init_rwsem(&pvd->rwsem);
+
+	rc = kset_register(&pvd->kset);
+	if (rc)
+		return ERR_PTR(rc);
+
+	return_ptr(pvd);
+}
+
+DEFINE_FREE(_unregister_measurement, struct tmr_provider *,
+	    if (!IS_ERR_OR_NULL(_T)) tsm_unregister_measurement(_T->tmr));
+
+int tsm_register_measurement(struct tsm_measurement *tmr)
+{
+	struct tmr_provider *pvd __free(_unregister_measurement);
+	int rc, nr;
+
+	pvd = tmr_provider_create(tmr);
+	if (IS_ERR(pvd))
+		return PTR_ERR(pvd);
+
+	nr = 0;
+	for (int i = 0; tmr->mrs[i].mr_name; ++i) {
+		// flat files are counted and skipped
+		if (tmr->mrs[i].mr_flags & TSM_MR_F_F) {
+			++nr;
+			continue;
+		}
+
+		struct tmr_dir *mrd;
+		struct bin_attribute *battrs[TMR_DIR_BA__COUNT + 1] = {};
+		struct attribute_group agrp = {
+			.name = hash_algo_name[tmr->mrs[i].mr_hash],
+			.bin_attrs = battrs,
+		};
+
+		mrd = tmr_dir_create(&tmr->mrs[i], pvd);
+		if (IS_ERR(mrd)) {
+			if (WARN_ONCE(PTR_ERR(mrd) == -ENOSPC, "too many banks"))
+				continue;
+
+			return PTR_ERR(mrd);
+		}
+
+		for (int j = 0; j < TMR_DIR_BA__COUNT; ++j)
+			battrs[j] = &mrd->battrs[mrd->algo][j];
+
+		rc = sysfs_create_group(&mrd->kobj, &agrp);
+		if (rc)
+			return rc;
+	}
+
+	if (nr > 0) {
+		struct bin_attribute *mrfiles __free(kfree);
+		struct bin_attribute **battrs __free(kfree);
+
+		mrfiles = kcalloc(nr, sizeof(*mrfiles), GFP_KERNEL);
+		battrs = kcalloc(nr + 1, sizeof(*battrs), GFP_KERNEL);
+		if (!battrs || !mrfiles)
+			return -ENOMEM;
+
+		for (int i = 0, j = 0; tmr->mrs[i].mr_name; ++i) {
+			if (!(tmr->mrs[i].mr_flags & TSM_MR_F_F))
+				continue;
+
+			mrfiles[j].attr.name = tmr->mrs[i].mr_name;
+			mrfiles[j].read = tmr_digest_read;
+			mrfiles[j].write = tmr_digest_write;
+			mrfiles[j].size = tmr->mrs[i].mr_size;
+			mrfiles[j].private = (void *)&tmr->mrs[i];
+			if (tmr->mrs[i].mr_flags & TSM_MR_F_R)
+				mrfiles[j].attr.mode |= S_IRUGO;
+			if (tmr->mrs[i].mr_flags & TSM_MR_F_W)
+				mrfiles[j].attr.mode |= S_IWUSR | S_IWGRP;
+
+			battrs[j] = &mrfiles[j];
+			++j;
+		}
+
+		struct attribute_group agrp = {
+			.bin_attrs = battrs,
+		};
+		rc = sysfs_create_group(&pvd->kset.kobj, &agrp);
+		if (rc)
+			return rc;
+
+		pvd->mrfiles = no_free_ptr(mrfiles);
+	}
+
+	// initial refresh of MRs
+	rc = tmr_call_refresh(pvd, NULL);
+	pvd->in_sync = !rc;
+
+	pvd = NULL; // to avoid being freed automatically
+	return 0;
+}
+EXPORT_SYMBOL_GPL(tsm_register_measurement);
+
+static void tmr_put_children(struct kset *kset)
+{
+	struct kobject *p, *n;
+
+	spin_lock(&kset->list_lock);
+	list_for_each_entry_safe(p, n, &kset->list, entry) {
+		spin_unlock(&kset->list_lock);
+		kobject_put(p);
+		spin_lock(&kset->list_lock);
+	}
+	spin_unlock(&kset->list_lock);
+}
+
+int tsm_unregister_measurement(struct tsm_measurement *tmr)
+{
+	struct kobject *kobj;
+	struct tmr_provider *pvd;
+
+	kobj = kset_find_obj(tmr_sysfs_root, tmr->name);
+	if (!kobj)
+		return -ENOENT;
+
+	pvd = container_of(kobj, typeof(*pvd), kset.kobj);
+	if (pvd->tmr != tmr)
+		return -EINVAL;
+
+	tmr_put_children(&pvd->kset);
+	kset_unregister(&pvd->kset);
+	kobject_put(kobj);
+	return 0;
+}
+EXPORT_SYMBOL_GPL(tsm_unregister_measurement);
+
+int tsm_mr_init(void)
+{
+	tmr_sysfs_root = kset_create_and_add("tsm", NULL, kernel_kobj);
+	if (!tmr_sysfs_root)
+		return -ENOMEM;
+	return 0;
+}
+
+void tsm_mr_exit(void)
+{
+	kset_unregister(tmr_sysfs_root);
+}
+
+MODULE_LICENSE("GPL");
+MODULE_DESCRIPTION("Provide Trusted Security Module measurements via sysfs");
diff --git a/include/linux/tsm.h b/include/linux/tsm.h
index 11b0c525be30..312965d45001 100644
--- a/include/linux/tsm.h
+++ b/include/linux/tsm.h
@@ -5,6 +5,7 @@
 #include <linux/sizes.h>
 #include <linux/types.h>
 #include <linux/uuid.h>
+#include <uapi/linux/hash_info.h>
 
 #define TSM_INBLOB_MAX 64
 #define TSM_OUTBLOB_MAX SZ_32K
@@ -109,4 +110,68 @@ struct tsm_ops {
 
 int tsm_register(const struct tsm_ops *ops, void *priv);
 int tsm_unregister(const struct tsm_ops *ops);
+
+/**
+ * struct tsm_measurement_register - describes an architectural measurement register (MR)
+ * @mr_name: name of the MR
+ * @mr_value: buffer containing the current value of the MR
+ * @mr_size: size of the MR - typically the digest size of @mr_hash
+ * @mr_flags: bitwise OR of flags defined in enum tsm_measurement_register_flag
+ * @mr_hash: optional hash identifier defined in include/uapi/linux/hash_info.h
+ *
+ * A CC guest driver provides this structure to detail the measurement facility supported by the
+ * underlying CC hardware. After registration via `tsm_register_measurement`, the CC guest driver
+ * must retain this structure until it is unregistered using `tsm_unregister_measurement`.
+ */
+struct tsm_measurement_register {
+	const char *mr_name;
+	void *mr_value;
+	u32 mr_size;
+	u32 mr_flags;
+	enum hash_algo mr_hash;
+};
+
+/**
+ * enum tsm_measurement_register_flag - properties of an MR
+ * @TSM_MR_F_X: this MR supports the extension semantics
+ * @TSM_MR_F_W: the sysfs attribute corresponding to this MR is writable
+ * @TSM_MR_F_R: the sysfs attribute corresponding to this MR is readable
+ * @TSM_MR_F_L: this MR is live - the current value may differ from the last value written so must
+ *              be loaded back from TVM hardware/firmware on read
+ * @TSM_MR_F_F: present this MR as a file (instead of a directory)
+ * @TSM_MR_F_LIVE: shorthand for L (live) and R (readable)
+ * @TSM_MR_F_RTMR: shorthand for LIVE and X (extensible)
+ */
+enum tsm_measurement_register_flag {
+	TSM_MR_F_X = 1,
+	TSM_MR_F_W = 2,
+	TSM_MR_F_R = 4,
+	TSM_MR_F_L = 8,
+	TSM_MR_F_F = 16,
+	TSM_MR_F_LIVE = TSM_MR_F_L | TSM_MR_F_R,
+	TSM_MR_F_RTMR = TSM_MR_F_LIVE | TSM_MR_F_X,
+};
+
+#define TSM_MR_(mr, hash)                                                           \
+	.mr_name = #mr, .mr_size = hash##_DIGEST_SIZE, .mr_hash = HASH_ALGO_##hash, \
+	.mr_flags = TSM_MR_F_R
+
+/**
+ * struct tsm_measurement - define CC specific MRs and methods for updating them
+ * @name: name of the measurement provider
+ * @mrs: array of MR definitions ending with mr_name set to %NULL
+ * @refresh: sync/reload MR values in TVM hardware/firmware into the kernel buffers
+ * @extend: extend the specified MR with mr->mr_size bytes stored in mr->mr_value
+ */
+struct tsm_measurement {
+	const char *name;
+	const struct tsm_measurement_register *mrs;
+	int (*refresh)(struct tsm_measurement *tmr, const struct tsm_measurement_register *mr);
+	int (*extend)(struct tsm_measurement *tmr, const struct tsm_measurement_register *mr,
+		      const u8 *data);
+};
+
+int tsm_register_measurement(struct tsm_measurement *tmr);
+int tsm_unregister_measurement(struct tsm_measurement *tmr);
+
 #endif /* __TSM_H */

---

## [3] Cedric Xing — 2025-02-23
*Subject: [PATCH v2 2/4] tsm: Add TSM measurement sample code*

This sample kernel module demonstrates how to make MRs accessible to user
mode through TSM.

Once loaded, this module registers a virtual measurement provider with the
TSM core and will result in the directory tree below.

/sys/kernel/tsm/
└── tsm_mr_sample
    ├── config_mr
    │   └── sha512
    │       └── digest
    ├── report_digest
    │   └── sha512
    │       └── digest
    ├── rtmr0
    │   └── sha256
    │       └── digest
    ├── rtmr1
    │   └── sha384
    │       └── digest
    ├── rtmr_crypto_agile
    │   ├── sha256
    │   │   └── digest
    │   └── sha384
    │       └── digest
    └── static_mr
        └── sha384
            └── digest

Among the MRs in this example:

- `static_mr` and `config_mr` are *Readonly* (static) MRs.
- `rtmr0` is an RTMR with `TSM_MR_F_W` **cleared**, preventing direct
  extensions; as a result, the attribute rtmr0/sha256/digest is read-only.
- `rtmr1` is an RTMR with `TSM_MR_F_W` **set**, permitting direct
  extensions; thus, the attribute rtmr1/sha384/digest is writable.
- `rtmr_crypto_agile` demonstrates a "single" MR that supports multiple
  hash algorithms. Each supported algorithm has a corresponding digest,
  usually referred to as a "bank" in TCG terminology. In this specific
  sample, the 2 banks are aliased to `rtmr0` and `rtmr1`, respectively.
- `report_digest` contains the digest of the internal report structure
  living in this sample module's memory. It is to demonstrate the use of
  the `TSM_MR_F_L` flag. Its value changes each time an RTMR is extended.

More details are available in samples/tsm/tsm_mr_sample.c.

Signed-off-by: Cedric Xing <cedric.xing@intel.com>
---
 MAINTAINERS                 |   1 +
 samples/Kconfig             |  13 ++++++
 samples/Makefile            |   1 +
 samples/tsm/Makefile        |   2 +
 samples/tsm/tsm_mr_sample.c | 107 ++++++++++++++++++++++++++++++++++++++++++++
 5 files changed, 124 insertions(+)

diff --git a/MAINTAINERS b/MAINTAINERS
index a5eef4c7234c..1d4232f5269e 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -24106,6 +24106,7 @@ S:	Maintained
 F:	Documentation/ABI/testing/configfs-tsm
 F:	drivers/virt/coco/tsm*.c
 F:	include/linux/tsm.h
+F:	samples/tsm/*
 
 TRUSTED SERVICES TEE DRIVER
 M:	Balint Dobszay <balint.dobszay@arm.com>
diff --git a/samples/Kconfig b/samples/Kconfig
index 820e00b2ed68..0b4592581648 100644
--- a/samples/Kconfig
+++ b/samples/Kconfig
@@ -184,6 +184,19 @@ config SAMPLE_TIMER
 	bool "Timer sample"
 	depends on CC_CAN_LINK && HEADERS_INSTALL
 
+config SAMPLE_TSM_MR
+	tristate "TSM measurement sample"
+	depends on TSM_REPORTS
+	help
+	  Build a sample module that emulates MRs (Measurement Registers) and
+	  exposes them to user mode applications through the TSM sysfs
+	  interface (/sys/kernel/tsm/tsm_mr_sample/).
+
+	  The module name will be tsm-mr-sample when built as a module.
+
+	  Note: TSM_MR_MAXBANKS must be at least 2 for this sample to work
+	  properly.
+
 config SAMPLE_UHID
 	bool "UHID sample"
 	depends on CC_CAN_LINK && HEADERS_INSTALL
diff --git a/samples/Makefile b/samples/Makefile
index f24cd0d72dd0..c4b6dcc81df6 100644
--- a/samples/Makefile
+++ b/samples/Makefile
@@ -42,3 +42,4 @@ obj-$(CONFIG_SAMPLE_FPROBE)		+= fprobe/
 obj-$(CONFIG_SAMPLES_RUST)		+= rust/
 obj-$(CONFIG_SAMPLE_DAMON_WSSE)		+= damon/
 obj-$(CONFIG_SAMPLE_DAMON_PRCL)		+= damon/
+obj-$(CONFIG_SAMPLE_TSM_MR)		+= tsm/
diff --git a/samples/tsm/Makefile b/samples/tsm/Makefile
new file mode 100644
index 000000000000..587c3947b3a7
--- /dev/null
+++ b/samples/tsm/Makefile
@@ -0,0 +1,2 @@
+# SPDX-License-Identifier: GPL-2.0-only
+obj-$(CONFIG_SAMPLE_TSM_MR) += tsm_mr_sample.o
diff --git a/samples/tsm/tsm_mr_sample.c b/samples/tsm/tsm_mr_sample.c
new file mode 100644
index 000000000000..4c2c6cde36e1
--- /dev/null
+++ b/samples/tsm/tsm_mr_sample.c
@@ -0,0 +1,107 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/* Copyright(c) 2024 Intel Corporation. All rights reserved. */
+
+#define DEBUG
+#define pr_fmt(x) KBUILD_MODNAME ": " x
+
+#include <linux/module.h>
+#include <linux/tsm.h>
+#include <crypto/hash_info.h>
+#include <crypto/hash.h>
+
+struct {
+	u8 static_mr[SHA384_DIGEST_SIZE];
+	u8 config_mr[SHA512_DIGEST_SIZE];
+	u8 rtmr0[SHA256_DIGEST_SIZE];
+	u8 rtmr1[SHA384_DIGEST_SIZE];
+	u8 user_data[SHA512_DIGEST_SIZE];
+	u8 report_digest[SHA512_DIGEST_SIZE];
+} sample_report = {
+	.static_mr = "static_mr",
+	.config_mr = "config_mr",
+	.rtmr0 = "rtmr0",
+	.rtmr1 = "rtmr1",
+	.user_data = "user_data",
+};
+
+DEFINE_FREE(shash, struct crypto_shash *, if (!IS_ERR(_T)) crypto_free_shash(_T));
+
+static int sample_report_refresh(struct tsm_measurement *tmr,
+				 const struct tsm_measurement_register *mr)
+{
+	pr_debug("%s(%s,%s) is called\n", __func__, tmr->name, mr ? mr->mr_name : "<nil>");
+	struct crypto_shash *tfm __free(shash) =
+		crypto_alloc_shash(hash_algo_name[HASH_ALGO_SHA512], 0, 0);
+	if (IS_ERR(tfm))
+		return PTR_ERR(tfm);
+	return crypto_shash_tfm_digest(tfm, (u8 *)&sample_report,
+				       offsetof(typeof(sample_report), report_digest),
+				       sample_report.report_digest);
+}
+
+static int sample_report_extend_mr(struct tsm_measurement *tmr,
+				   const struct tsm_measurement_register *mr, const u8 *data)
+{
+	SHASH_DESC_ON_STACK(desc, 0);
+	int rc;
+
+	pr_debug("%s(%s,%s) is called\n", __func__, tmr->name, mr->mr_name);
+
+	desc->tfm = crypto_alloc_shash(hash_algo_name[mr->mr_hash], 0, 0);
+	if (IS_ERR(desc->tfm))
+		return PTR_ERR(desc->tfm);
+
+	rc = crypto_shash_init(desc);
+	if (!rc)
+		rc = crypto_shash_update(desc, mr->mr_value, mr->mr_size);
+	if (!rc)
+		rc = crypto_shash_finup(desc, data, mr->mr_size, mr->mr_value);
+
+	crypto_free_shash(desc->tfm);
+	return rc;
+}
+
+#define MR_(mr, hash) .mr_value = &sample_report.mr, TSM_MR_(mr, hash)
+static const struct tsm_measurement_register sample_mrs[] = {
+	/* static MR, read-only */
+	{ MR_(static_mr, SHA384) },
+	/* config MR, read-only */
+	{ MR_(config_mr, SHA512) },
+	/* RTMR, direct extension prohibited */
+	{ MR_(rtmr0, SHA256) | TSM_MR_F_RTMR },
+	/* RTMR, direct extension allowed */
+	{ MR_(rtmr1, SHA384) | TSM_MR_F_RTMR | TSM_MR_F_W },
+	/* RTMR, crypto agile, alaised to rtmr0 and rtmr1, respectively */
+	{ .mr_value = &sample_report.rtmr0,
+	  TSM_MR_(rtmr_crypto_agile, SHA256) | TSM_MR_F_RTMR | TSM_MR_F_W },
+	{ .mr_value = &sample_report.rtmr1,
+	  TSM_MR_(rtmr_crypto_agile, SHA384) | TSM_MR_F_RTMR | TSM_MR_F_W },
+	/* most CC archs allow including user data in attestation */
+	{ MR_(report_digest, SHA512) | TSM_MR_F_L },
+	/* terminating NULL entry */
+	{}
+};
+#undef MR_
+
+static struct tsm_measurement sample_mr_provider = {
+	.name = KBUILD_MODNAME,
+	.mrs = sample_mrs,
+	.refresh = sample_report_refresh,
+	.extend = sample_report_extend_mr,
+};
+
+static int __init tsm_mr_sample_init(void)
+{
+	return tsm_register_measurement(&sample_mr_provider);
+}
+
+static void __exit tsm_mr_sample_exit(void)
+{
+	tsm_unregister_measurement(&sample_mr_provider);
+}
+
+module_init(tsm_mr_sample_init);
+module_exit(tsm_mr_sample_exit);
+
+MODULE_LICENSE("GPL");
+MODULE_DESCRIPTION("Sample tsm_measurement implementation");

---

## [4] Cedric Xing — 2025-02-23
*Subject: [PATCH v2 3/4] x86/tdx: Add tdx_mcall_extend_rtmr() interface*

The TDX guest exposes one MRTD (Build-time Measurement Register) and four
RTMR (Run-time Measurement Register) registers to record the build and boot
measurements of a virtual machine (VM). These registers are similar to PCR
(Platform Configuration Register) registers in the TPM (Trusted Platform
Module) space. This measurement data is used to implement security features
like attestation and trusted boot.

To facilitate updating the RTMR registers, the TDX module provides support
for the `TDG.MR.RTMR.EXTEND` TDCALL which can be used to securely extend
the RTMR registers.

Add helper function to update RTMR registers. It will be used by the TDX
guest driver in enabling RTMR extension support.

Signed-off-by: Kuppuswamy Sathyanarayanan <sathyanarayanan.kuppuswamy@linux.intel.com>
Signed-off-by: Cedric Xing <cedric.xing@intel.com>
---
 arch/x86/coco/tdx/tdx.c           | 36 ++++++++++++++++++++++++++++++++++++
 arch/x86/include/asm/shared/tdx.h |  1 +
 arch/x86/include/asm/tdx.h        |  2 ++
 3 files changed, 39 insertions(+)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 32809a06dab4..f88e249e339a 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -35,6 +35,7 @@
 /* TDX Module call error codes */
 #define TDCALL_RETURN_CODE(a)	((a) >> 32)
 #define TDCALL_INVALID_OPERAND	0xc0000100
+#define TDCALL_OPERAND_BUSY	0x80000200
 
 #define TDREPORT_SUBTYPE_0	0
 
@@ -135,6 +136,41 @@ int tdx_mcall_get_report0(u8 *reportdata, u8 *tdreport)
 }
 EXPORT_SYMBOL_GPL(tdx_mcall_get_report0);
 
+/**
+ * tdx_mcall_extend_rtmr() - Wrapper to extend RTMR registers using
+ *			     TDG.MR.RTMR.EXTEND TDCALL.
+ * @index: Index of RTMR register to be extended.
+ * @data: Address of the input buffer with RTMR register extend data.
+ *
+ * Refer to section titled "TDG.MR.RTMR.EXTEND leaf" in the TDX Module
+ * v1.0 specification for more information on TDG.MR.RTMR.EXTEND TDCALL.
+ * It is used in the TDX guest driver module to allow user extend the
+ * RTMR registers (index > 1).
+ *
+ * Return 0 on success, -EINVAL for invalid operands, -EBUSY for busy
+ * operation or -EIO on other TDCALL failures.
+ */
+int tdx_mcall_extend_rtmr(u8 index, u8 *data)
+{
+	struct tdx_module_args args = {
+		.rcx = virt_to_phys(data),
+		.rdx = index,
+	};
+	u64 ret;
+
+	ret = __tdcall(TDG_MR_RTMR_EXTEND, &args);
+	if (ret) {
+		if (TDCALL_RETURN_CODE(ret) == TDCALL_INVALID_OPERAND)
+			return -EINVAL;
+		if (TDCALL_RETURN_CODE(ret) == TDCALL_OPERAND_BUSY)
+			return -EBUSY;
+		return -EIO;
+	}
+
+	return 0;
+}
+EXPORT_SYMBOL_GPL(tdx_mcall_extend_rtmr);
+
 /**
  * tdx_hcall_get_quote() - Wrapper to request TD Quote using GetQuote
  *                         hypercall.
diff --git a/arch/x86/include/asm/shared/tdx.h b/arch/x86/include/asm/shared/tdx.h
index fcbbef484a78..d0760c6160cc 100644
--- a/arch/x86/include/asm/shared/tdx.h
+++ b/arch/x86/include/asm/shared/tdx.h
@@ -13,6 +13,7 @@
 /* TDX module Call Leaf IDs */
 #define TDG_VP_VMCALL			0
 #define TDG_VP_INFO			1
+#define TDG_MR_RTMR_EXTEND		2
 #define TDG_VP_VEINFO_GET		3
 #define TDG_MR_REPORT			4
 #define TDG_MEM_PAGE_ACCEPT		6
diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index b4b16dafd55e..6b98d7dc5207 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -64,6 +64,8 @@ bool tdx_early_handle_ve(struct pt_regs *regs);
 
 int tdx_mcall_get_report0(u8 *reportdata, u8 *tdreport);
 
+int tdx_mcall_extend_rtmr(u8 index, u8 *data);
+
 u64 tdx_hcall_get_quote(u8 *buf, size_t size);
 
 void __init tdx_dump_attributes(u64 td_attr);

---

## [5] Cedric Xing — 2025-02-23
*Subject: [PATCH v2 4/4] x86/tdx: Expose TDX MRs through TSM sysfs interface*

TDX MRs are made accessible to user mode as files (attributes) in sysfs.

Below shows the directory structure of TDX MRs inside a TDVM.

/sys/kernel/tsm
└── tdx
    ├── mrconfigid
    │   └── sha384
    │       └── digest
    ├── mrowner
    │   └── sha384
    │       └── digest
    ├── mrownerconfig
    │   └── sha384
    │       └── digest
    ├── mrtd
    │   └── sha384
    │       └── digest
    ├── report0
    ├── reportdata
    ├── rtmr0
    │   └── sha384
    │       └── digest
    ├── rtmr1
    │   └── sha384
    │       └── digest
    ├── rtmr2
    │   └── sha384
    │       └── digest
    ├── rtmr3
    │   └── sha384
    │       └── digest
    └── servtd_hash
        └── sha384
            └── digest

The digest attribute/file of each MR contains the MR's current value.

Writing to the digest attribute/file of an RTMR extends the written value
to that RTMR.

The report0 and reportdata attributes offer a simple interface for user
mode applications to request TDREPORTs. These 2 attributes can be
enabled/disabled by setting TDX_GUEST_DRIVER_TSM_REPORT to Y/n.

Signed-off-by: Cedric Xing <cedric.xing@intel.com>
---
 drivers/virt/coco/tdx-guest/Kconfig     |  24 +++++--
 drivers/virt/coco/tdx-guest/tdx-guest.c | 115 ++++++++++++++++++++++++++++++++
 2 files changed, 134 insertions(+), 5 deletions(-)

diff --git a/drivers/virt/coco/tdx-guest/Kconfig b/drivers/virt/coco/tdx-guest/Kconfig
index 22dd59e19431..a1c5e8fdd511 100644
--- a/drivers/virt/coco/tdx-guest/Kconfig
+++ b/drivers/virt/coco/tdx-guest/Kconfig
@@ -3,9 +3,23 @@ config TDX_GUEST_DRIVER
 	depends on INTEL_TDX_GUEST
 	select TSM_REPORTS
 	help
-	  The driver provides userspace interface to communicate with
-	  the TDX module to request the TDX guest details like attestation
-	  report.
+	  The driver provides userspace interface to communicate with the TDX
+	  module to request the TDX guest details like attestation report.
 
-	  To compile this driver as module, choose M here. The module will
-	  be called tdx-guest.
+	  To compile this driver as module, choose M here. The module will be
+	  called tdx-guest.
+
+if TDX_GUEST_DRIVER
+
+config TDX_GUEST_DRIVER_TSM_REPORT
+	bool "tdx-guest: Enable TSM raw TDREPORT interface"
+	default y
+	help
+	  This option adds 2 files, namely report0 and reportdata, to the TSM
+	  sysfs directory tree (/sys/kernel/tsm/tdx/).
+
+	  To request a TDREPORT, set REPORTDATA by writing to
+	  /sys/kernel/tsm/tdx/reportdata, then read
+	  /sys/kernel/tsm/tdx/report0.
+
+endif
diff --git a/drivers/virt/coco/tdx-guest/tdx-guest.c b/drivers/virt/coco/tdx-guest/tdx-guest.c
index 224e7dde9cde..a31fe2098901 100644
--- a/drivers/virt/coco/tdx-guest/tdx-guest.c
+++ b/drivers/virt/coco/tdx-guest/tdx-guest.c
@@ -5,6 +5,8 @@
  * Copyright (C) 2022 Intel Corporation
  */
 
+#define pr_fmt(fmt)			KBUILD_MODNAME ": " fmt
+
 #include <linux/kernel.h>
 #include <linux/miscdevice.h>
 #include <linux/mm.h>
@@ -18,6 +20,8 @@
 #include <linux/tsm.h>
 #include <linux/sizes.h>
 
+#include <crypto/hash_info.h>
+
 #include <uapi/linux/tdx-guest.h>
 
 #include <asm/cpu_device_id.h>
@@ -304,6 +308,110 @@ static const struct tsm_ops tdx_tsm_ops = {
 	.report_bin_attr_visible = tdx_report_bin_attr_visible,
 };
 
+enum {
+	TDREPORT_MRSIZE = SHA384_DIGEST_SIZE,
+
+	TDREPORT_reportdata = 128,
+	TDREPORT_tdinfo = 512,
+	TDREPORT_mrtd = TDREPORT_tdinfo + 16,
+	TDREPORT_mrconfigid = TDREPORT_mrtd + TDREPORT_MRSIZE,
+	TDREPORT_mrowner = TDREPORT_mrconfigid + TDREPORT_MRSIZE,
+	TDREPORT_mrownerconfig = TDREPORT_mrowner + TDREPORT_MRSIZE,
+	TDREPORT_rtmr0 = TDREPORT_mrownerconfig + TDREPORT_MRSIZE,
+	TDREPORT_rtmr1 = TDREPORT_rtmr0 + TDREPORT_MRSIZE,
+	TDREPORT_rtmr2 = TDREPORT_rtmr1 + TDREPORT_MRSIZE,
+	TDREPORT_rtmr3 = TDREPORT_rtmr2 + TDREPORT_MRSIZE,
+	TDREPORT_servtd_hash = TDREPORT_rtmr3 + TDREPORT_MRSIZE,
+};
+
+static u8 tdx_mr_report[TDX_REPORT_LEN] __aligned(TDX_REPORT_LEN);
+
+#define TDX_MR_(r)	.mr_value = tdx_mr_report + TDREPORT_##r, TSM_MR_(r, SHA384)
+static const struct tsm_measurement_register tdx_mrs[] = {
+	{ TDX_MR_(rtmr0) | TSM_MR_F_RTMR | TSM_MR_F_W },
+	{ TDX_MR_(rtmr1) | TSM_MR_F_RTMR | TSM_MR_F_W },
+	{ TDX_MR_(rtmr2) | TSM_MR_F_RTMR | TSM_MR_F_W },
+	{ TDX_MR_(rtmr3) | TSM_MR_F_RTMR | TSM_MR_F_W },
+	{ TDX_MR_(mrtd) },
+	{ TDX_MR_(mrconfigid) },
+	{ TDX_MR_(mrowner) },
+	{ TDX_MR_(mrownerconfig) },
+	{ TDX_MR_(servtd_hash) },
+#if IS_ENABLED(CONFIG_TDX_GUEST_DRIVER_TSM_REPORT)
+	{ .mr_value = tdx_mr_report, .mr_size = sizeof(tdx_mr_report),
+	  .mr_name = "report0", .mr_flags = TSM_MR_F_LIVE | TSM_MR_F_F },
+	{ .mr_value = tdx_mr_report + TDREPORT_reportdata,
+	  TSM_MR_(reportdata, SHA512) | TSM_MR_F_W | TSM_MR_F_F },
+#endif
+	{}
+};
+#undef TDX_MR_
+
+static int tdx_mr_refresh(struct tsm_measurement *tmr,
+			  const struct tsm_measurement_register *mr)
+{
+	u8 *reportdata, *tdreport;
+	int ret;
+
+	reportdata = tdx_mr_report + TDREPORT_reportdata;
+
+	/*
+	 * TDCALL requires a GPA as input. Depending on whether this module is
+	 * built as a built-in (Y) or a module (M), tdx_mr_report may or may
+	 * not be converted to a GPA using virt_to_phys. If not, a directly
+	 * mapped buffer must be allocated using kmalloc and used as an
+	 * intermediary.
+	 */
+#if IS_BUILTIN(CONFIG_TDX_GUEST_DRIVER)
+	tdreport = tdx_mr_report;
+#else
+	tdreport = kmalloc(sizeof(tdx_mr_report), GFP_KERNEL);
+	if (!tdreport)
+		return -ENOMEM;
+
+	reportdata = memcpy(tdreport + TDREPORT_reportdata, reportdata,
+			    TDX_REPORTDATA_LEN);
+#endif
+
+	ret = tdx_mcall_get_report0(reportdata, tdreport);
+	if (ret)
+		pr_err("GetReport call failed\n");
+
+#if !IS_BUILTIN(CONFIG_TDX_GUEST_DRIVER)
+	memcpy(tdx_mr_report, tdreport, sizeof(tdx_mr_report));
+	kfree(tdreport);
+#endif
+
+	return ret;
+}
+
+static int tdx_mr_extend(struct tsm_measurement *tmr,
+			 const struct tsm_measurement_register *mr, const u8 *data)
+{
+	u8 *buf;
+	int ret;
+
+	buf = kmalloc(64, GFP_KERNEL);
+	if (!buf)
+		return -ENOMEM;
+
+	memcpy(buf, data, TDREPORT_MRSIZE);
+
+	ret = tdx_mcall_extend_rtmr((u8)(mr - tmr->mrs), buf);
+	if (ret)
+		pr_err("Extending RTMR%ld failed\n", mr - tmr->mrs);
+
+	kfree(buf);
+	return ret;
+}
+
+static struct tsm_measurement tdx_measurement = {
+	.name = "tdx",
+	.mrs = tdx_mrs,
+	.refresh = tdx_mr_refresh,
+	.extend = tdx_mr_extend,
+};
+
 static int __init tdx_guest_init(void)
 {
 	int ret;
@@ -326,8 +434,14 @@ static int __init tdx_guest_init(void)
 	if (ret)
 		goto free_quote;
 
+	ret = tsm_register_measurement(&tdx_measurement);
+	if (ret)
+		goto unregister_tsm;
+
 	return 0;
 
+unregister_tsm:
+	tsm_unregister(&tdx_tsm_ops);
 free_quote:
 	free_quote_buf(quote_data);
 free_misc:
@@ -339,6 +453,7 @@ module_init(tdx_guest_init);
 
 static void __exit tdx_guest_exit(void)
 {
+	tsm_unregister_measurement(&tdx_measurement);
 	tsm_unregister(&tdx_tsm_ops);
 	free_quote_buf(quote_data);
 	misc_deregister(&tdx_misc_dev);

---

## [6] Jianxiong Gao — 2025-02-27
*Subject: Re: [PATCH v2 0/4] tsm: Unified Measurement Register ABI for TVMs*

On Sun, Feb 23, 2025 at 7:23 PM Cedric Xing <cedric.xing@intel.com> wrote:
>
> NOTE: This patch series introduces the Measurement Register (MR) ABI, and
Tested-by: Jianxiong Gao <jxgao@google.com>
I have verified that the patchset works on Google Cloud.

---

## [7] Huang, Kai — 2025-03-06
*Subject: Re: [PATCH v2 1/4] tsm: Add TVM Measurement Register support*

On Sun, 2025-02-23 at 21:20 -0600, Cedric Xing wrote:
> Add new TSM APIs for TVM guest drivers to register and expose measurement
> registers (MRs) as sysfs attributes (files).

Hi Cedric,

The current TSM is done in configfs, but not sysfs.  The reason, quoted from
commit 70e6f7e2b9857 ("configfs-tsm: Introduce a shared ABI for attestation
reports"), is:

    Review of previous iterations of this interface identified that there is
    a need to scale report generation for multiple container environments
    [2]. Configfs enables a model where each container can bind mount one or
    more report generation item instances. Still, within a container only a
    single thread can be manipulating a given configuration instance at a
    time. A 'generation' count is provided to detect conflicts between
    multiple threads racing to configure a report instance.

And the link [2] (where you can find the relevant discussion) is:

http://lore.kernel.org/r/57f3a05e-8fcd-4656-beea-56bb8365ae64@linux.microsoft.com

Could you elaborate why do you choose to expose MRs via sysfs rather than
configfs?  Is the above reason not valid anymore?


> 
> New TSM APIs:

Nit:

We can see those details from the code.  Personally I think you don't need to
describe them again in the changelog.  It would be more helpful if you could put
more _why_ here.

E.g., Wwhat is userspace's requirement/flow that involves reading/extending
those MRs?  An example is even better.

> 
> Upon successful registration, the TSM core exposes MRs in sysfs at

Please correct me if I am wrong: in my understanding, the purpose is to provide
a "unified ABI for usrspace" for MRs, but not just some common infrastructure in
the kernel to support exposing MRs, right?

Configfs-tsm provides consistent names for all attributes for all vendors:
'inblob', 'outblob', 'generation', 'provider' etc, so it provides a unified ABI
for userspace.

But here actually each vendor will have its own directory.  E.g., for TDX we
have:

	/sys/kernel/tsm/tdx/...

And the actual MRs under the vendor-specific directory are completely vendor-
specific.  E.g., as shown in the last patch, for TDX we have: mrconfigid,
mrowner etc.  And for other vendors they are free to register MRs on their own.

Could you elaborate how userspace is supposed to use those MRs in a common way?
 
Or this is not the purpose?

> 
> *Crypto Agility* is supported by merging independent MRs with a common name

Ditto.  I think it would be more helpful if you can provide _why_ we need to
support crypto agility rather than _how_ is it implemented, which can be seen
from the actual code.  Once merged, the _why_ will be helpful when some random
guy in the future tries to git blame and figure out the story behind.

---

## [8] Xing, Cedric — 2025-03-12
*Subject: Re: [PATCH v2 1/4] tsm: Add TVM Measurement Register support*

Hi Kai,

Thanks for your comments and my apologies for my late response!

On 3/5/2025 7:20 PM, Huang, Kai wrote:
> On Sun, 2025-02-23 at 21:20 -0600, Cedric Xing wrote:
>> Add new TSM APIs for TVM guest drivers to register and expose measurement
The key difference between MRs and reports/quotes is the lack of 
context. Reports/quotes benefit from having a separate context for each 
container, ensuring they don't interfere with each other. However, MRs 
are global, and creating separate contexts would be confusing since 
changes/extensions to MRs by one container will always be visible to others.

Below is TDX specific:

Report0/reportdata is an exception, as report0 serves as a comprehensive 
list of all measurements rather than a container-specific report. 
reportdata provides an easy way to request a report if inter-container 
race isn't a concern for your application.

I can see the confusion here though (both Mikko and you raised the same 
concern). I can (1) take away reportdata but leave report0 as it; or (2) 
take away reportdata and break down report0 into tee_tcb_info and tdinfo 
(and strip off report_mac_struct) so user can still have a comprehensive 
list of MRs; or (3) take away report0/reportdata altogether. Which one 
do you think is the most reasonable? In all cases, I'll incorporate 
Mikko's patch into this series to allow per-container TDREPORT under 
configfs.

> 
>>
Did I describe them in the changelog? I'm not sure...

> E.g., Wwhat is userspace's requirement/flow that involves reading/extending
> those MRs?  An example is even better.
The intention of exposing MRs as files is to make it obvious to users 
how to read/extend MRs. But from your feedback I can tell it isn't 
obvious enough and I'll update the commit message in the next revision.

>>
>> Upon successful registration, the TSM core exposes MRs in sysfs at
"attestation reports" in this configfs context refers to opaque blobs 
consumed by external parties, while the guest acts as the "wire" for 
transporting the reports.

> But here actually each vendor will have its own directory.  E.g., for TDX we
> have:
In contrast, MRs (especially extensible/RT MRs) are consumed by the 
guest itself. They are vendor specific because they are _indeed_ vendor 
specific. The intention is to unlock access to all of them for user 
mode. The semantics (i.e., which MR stores what measurement) is 
application specific and will be assigned by the application.

> Could you elaborate how userspace is supposed to use those MRs in a common way?
>   
Sure. For example, CoCo may require storing container measurements into 
an RTMR. Then, a potential implementation could extend those 
measurements to an "RTMR file" named "container_mr", which could be a 
symlink pointing to different RTMRs on different archs.

Of course, we are hand-waiving the potential difference in the 
number/naming of the MRs and the hash algorithms they use in the example 
above.

Generally, as shown in the example above, common names (e.g., 
"container_mr") don't provide common semantics (e.g., different hash, or 
different measurements may be extended to the same or different MRs on 
different archs), so we avoid using them. A full solution would require 
a log-oriented ABI and a virtual measurement stack. We're laying the 
groundwork for this today.

>>
>> *Crypto Agility* is supported by merging independent MRs with a common name
The reason for crypto agility is to allow introducing new hash 
algorithms without sacrificing compatibility. It's a lessen learned from 
the TPM 1.x to 2.x transition. I thought it was obvious, but will add 
clarification in the next revision.

-Cedric

---

## [9] Huang, Kai — 2025-03-12
*Subject: Re: [PATCH v2 1/4] tsm: Add TVM Measurement Register support*

On Wed, 2025-03-12 at 13:26 -0500, Xing, Cedric wrote:
> Hi Kai,
> 

Thanks for replying back!

> 
> On 3/5/2025 7:20 PM, Huang, Kai wrote:

This makes sense.  Could you put those into the changelog?

I still have a slight concern (more like a question) though:

From attestation's point of view, ultimately, those MRs serves the same purpose
as the static ones -- to be included in a verifiable attestation report to
provide trustiness.  I think in most use cases the runtime MRs will be just
extended once at early stage, e.g., during system boots (since they are global
as you mentioned above).  And after that, they will just be read by applications
(e.g., containers).

So the question is whether do we see any requirement for containers to *read*
those MRs independently w/o the full report? From attestation's point of view, I
don't think there is, because those MRs alone are not verifiable.  But I am not
sure in your mind whether there's other use cases in which providing MRs for
read in configfs-tsm would be helpful?

> 
> Below is TDX specific:

I don't quite follow what's the value of leaving report0 w/o reportdata.

> or (2) 
> take away reportdata and break down report0 into tee_tcb_info and tdinfo 

Ditto. W/o reportdata, what value are you going to fill into the report0?

I think the confusion is _why_ do you want to provide the full report0 via
sysfs?  Is it for local verification, presumably?  In which case, probably you
don't need to care about the reportdata?

I can understand the purpose of exporting runtime MRs, I can even understand
(sort of) the purpose of exporting other files like 'mrowner' etc, but I am not
sure the purpose of exporting report0.

> or (3) take away report0/reportdata altogether. Which one 
> do you think is the most reasonable? 

3) Seems more reasonable to me, but I am not certain because I don't fully
understand the purpose (use case).

> In all cases, I'll incorporate 
> Mikko's patch into this series to allow per-container TDREPORT under 

Sorry I might have missed, where can I find this patch?

> 
> > 

I think it is still valid question that whether we need to make those MRs
consistent for all vendors for the purpose of providing a unified ABI to
userspace.

IIUC, Dan has been wanting unified ABIs around attestation.  It would be great
if Dan can provide guidance here.

> 
> > > 

I interpret this as there's no requirement for containers to *read* those MRs
independently via configfs-tsm. :-)

> 
> > But here actually each vendor will have its own directory.  E.g., for TDX we

Yeah agreed.  But eventually they are for attestation, right?

> They are vendor specific because they are _indeed_ vendor 
> specific. The intention is to unlock access to all of them for user 

Agreed.

> The semantics (i.e., which MR stores what measurement) is 
> application specific and will be assigned by the application.

This doesn't mean the kernel shouldn't provide a unified ABI to userspace
AFAICT.

> 
> > Could you elaborate how userspace is supposed to use those MRs in a common way?

OK.

> 
> Of course, we are hand-waiving the potential difference in the 

I think the number is fine.  E.g., in the above case, the application could have
a policy to map a given container measurement to one RTMR (e.g., container0 ->
rtmr0 and so on).

And I am not sure why hash algorithm matters?  If needed, there could be a
policy to query the hash algorithm for a given RTMR and feed extended data based
on the algo in each loop.

> 
> Generally, as shown in the example above, common names (e.g., 

As above, I don't think I am convinced that a unified ABI doesn't work, or isn't
necessary.

Again, no blocker from me, but I am hoping Dan can provide guidance here.

> 
> > > 

Thanks.

It will be definitely useful for newbies like me :-)

> 
> -Cedric

---

## [10] Xing, Cedric — 2025-03-17
*Subject: Re: [PATCH v2 1/4] tsm: Add TVM Measurement Register support*

On 3/12/2025 6:11 PM, Huang, Kai wrote:
[...]	
>> The key difference between MRs and reports/quotes is the lack of
>> context. Reports/quotes benefit from having a separate context for each
MRs have been under sysfs since the first version of the RFC patch. I'm 
not sure which changelog to put it in.

> I still have a slight concern (more like a question) though:
> 
There are applications that require reading/extending RTMRs way past 
boot. For example, a container runtime may extend the path of the 
executable started inside an existing container, the container can then 
read the RTMR back to determine if there have been additional processes 
started by the user since its entrypoint.

> So the question is whether do we see any requirement for containers to *read*
> those MRs independently w/o the full report? From attestation's point of view, I
MRs, when read inside the guest, are considered trusted, as the guest 
trusts both the attestation environment (e.g., the TDX module) and the 
underlying communication channel. And there are applications like the 
example above that read RTMRs inside the guest. Please also note that 
reading MRs are very useful in debugging/diagnoses too. Just like 
"tainted kernel" messages, they aren't necessary but are very helpful. 
As another reference, TPM also provides TPM_PCR_Read command.

>>
>> Below is TDX specific:
The intention is to allow access to _all_ measurements of a TD. There 
are measurement items not exposed to sysfs, such as MRSIGNERSEAM, 
CPUSVN, etc. They are not exposed individually because their uses are 
really rare/limited. Leaving a report0 here will allow users to examine 
their values when needed. REPORTDATA will be hard-coded to 0.

In other words, report0 here serves as a "container" for all TD 
measurements. It isn't meant to be used in local attestation. Its name 
"report0" merely suggests the its format follows the TDREPORT v0 
definition in the SDM (so people know how to interpret it).

>> or (2)
>> take away reportdata and break down report0 into tee_tcb_info and tdinfo
I can see the confusion from your comments. Guess neither (1) nor (2) is 
a good option.

>> or (3) take away report0/reportdata altogether. Which one
>> do you think is the most reasonable?
Mikko's patch is at 
https://gist.github.com/mythi/1c54fdb143c961146453261c725cd485

I'll incorporate it into the next revision.

[...]
> I think it is still valid question that whether we need to make those MRs
> consistent for all vendors for the purpose of providing a unified ABI to
Yes, Dan and I had discussed this long ago. Just a bit clarification 
here, this ABI is mainly measurement but not for attestation.

Given the lack of unified HW from different vendors, there cannot be a 
low level unified ABI. A higher level ABI (with HW specifics abstracted 
away) was once proposed - i.e., the log oriented ABI. But it turned out 
difficult to agree upon a log format. Anyway, the abstraction doesn't 
have to be done in kernel mode, as long as MRs are made accessible to 
user mode. This patch is laying the groundwork for that.

[...]
>>> Please correct me if I am wrong: in my understanding, the purpose is to provide
>>> a "unified ABI for usrspace" for MRs, but not just some common infrastructure in
Yes and no. Containers have the need to read MRs, but doesn't have (the 
need) to verify them (and the credentials backing them). It is a 
separate question whether to read MRs via sysfs or configfs. The 
structure of configfs-tsm is optimized for usages that doesn't require 
parsing/interpreting the quotes from within the guest, while The 
structure of sysfs-tsm is optimized for the opposite.

Please note that, at least in the case of TDX, quotes have a lot bigger 
TCB than TDREPORTs, so shouldn't be used unless TDREPORTs cannot serve 
the same purpose.

>>
>>> But here actually each vendor will have its own directory.  E.g., for TDX we
No. From the perspective of this ABI, MRs are "mainly" for measurement. 
By "mainly", I mean there are MRs like MRCONFIGID on TDX and HOSTDATA on 
SEV, that are simply immutable storage. They are needed by applications 
for verifying, for example, security policies that must be enforced. Do 
you see the need for reading them now?

>> They are vendor specific because they are _indeed_ vendor
>> specific. The intention is to unlock access to all of them for user
A log oriented ABI was once proposed, but we failed to reach an 
agreement on the log format. Moreover, this may be a problem better 
solved in user space.

>>
>>> Could you elaborate how userspace is supposed to use those MRs in a common way?
The existence of a "mapping policy" implies the application is aware of 
the underlying HW, meaning the application cannot work on new HW 
released after the application.

"Querying hash algorithm" will work only if the application is aware 
(and carries the implementation) of the hash. This was how crypto 
agility got introduced into TPM2.0, as old applications can't understand 
new hash algos.

IMHO, what's really required by applications/attesters is the ability to 
log "events" (e.g., a container signed by a specific authority has been 
loaded/started), while what's required by verifiers/appraisers is the 
ability to verify those "events". Neither party has the need to 
understand the HW specifics (number/names of MRs and hash algos). 
Therefore, an ideal solution should be log oriented: Applications append 
"events" to logs while verifiers extract "events" from logs, with the HW 
specifics encapsulated in a separate "bottom layer". This ABI is part of 
that "bottom layer", upon which the rest of the stack can be built out 
in user space.

>>
>> Generally, as shown in the example above, common names (e.g.,
Please see above.

> Again, no blocker from me, but I am hoping Dan can provide guidance here.
> 
[...]

-Cedric

---

## [11] Sathyanarayanan Kuppuswamy — 2025-03-17
*Subject: Re: [PATCH v2 0/4] tsm: Unified Measurement Register ABI for TVMs*

Hi Cedric,

On 2/23/25 7:20 PM, Cedric Xing wrote:
> NOTE: This patch series introduces the Measurement Register (MR) ABI, and
> is a continuation of the RFC series on the same topic [1].

Any comment on the missing event log support? Extending the measurements
without logging the event should break the tractability feature. Can you add
info about why it is ok to just add extension support for now?


>
> [1]: https://lore.kernel.org/linux-coco/20241210-tsm-rtmr-v3-0-5997d4dbda73@intel.com/

---

## [12] Xing, Cedric — 2025-03-17
*Subject: Re: [PATCH v2 0/4] tsm: Unified Measurement Register ABI for TVMs*

On 3/17/2025 6:15 PM, Sathyanarayanan Kuppuswamy wrote:
[...]
> Any comment on the missing event log support? Extending the measurements
> without logging the event should break the tractability feature. Can you 
The event log support was once proposed and discussed. Please see 
https://lore.kernel.org/all/20240907-tsm-rtmr-v1-0-12fc4d43d4e7@intel.com/ 
for details. In short, it's difficult to define a log format that fits 
all applications, and luckily it doesn't have to be solved in kernel 
mode, so we leave it out for now.

---

## [13] James Bottomley — 2025-03-18
*Subject: Re: [PATCH v2 0/4] tsm: Unified Measurement Register ABI for TVMs*

On Mon, 2025-03-17 at 22:48 -0500, Xing, Cedric wrote:
> On 3/17/2025 6:15 PM, Sathyanarayanan Kuppuswamy wrote:
> [...]

I also think the interface doesn't have much utility without a log (at
least the ability to write part).  However, I think the problem is the
quest for a single universal log.  If you just allow the reflected
consumers to use their own log format (and identify that format
somewhere in the filesystem) it still all works.  This would mean that
plugging in IMA becomes simple and it would obviously just use the IMA
log format.

From a non-repudiable record point of view there are definite reasons
why mutually distrusting subsystems would want their own PCR and log
anyway (so they can do separated replay), so I think supporting
multiple logs is definitely a requirement.  If we have multiple logs,
there's not much of a problem with multiple formats.

> and luckily it doesn't have to be solved in kernel  mode, so we leave
> it out for now.

The problem, that will be hard to do a pure userspace solution for, is
that adding a log entry and extending the PCR should be as close to
atomic as you can get them.

Regards,

James

---

## [14] Huang, Kai — 2025-03-19
*Subject: Re: [PATCH v2 1/4] tsm: Add TVM Measurement Register support*

On Mon, 2025-03-17 at 17:49 -0500, Xing, Cedric wrote:
> On 3/12/2025 6:11 PM, Huang, Kai wrote:
> [...]	

I was thinking to put the reason(s) of choosing sysfs over configfs-tsm to the
changelog of this patch, as I had impression the ABI to expose MRs is also for
attestation or at least attestation related.

[...]

> > I think it is still valid question that whether we need to make those MRs
> > consistent for all vendors for the purpose of providing a unified ABI to

Ok as long as Dan is fine.

> A higher level ABI (with HW specifics abstracted 
> away) was once proposed - i.e., the log oriented ABI. But it turned out 

Thanks for the info.

Maybe it's also worth to put this into the changelog of this patch too, so that
readers can at least know why we didn't choose to unify the ABI.

> 
> [...]

I think we can also parse the quote from the configfs-tsm if apps want, or we
can also introduce new configfs-tsm attributes for individual MRs if needed. 
But I think the key reason we choose sysfs for MRs is they are platform global
while configfs-tsm fits per-application more.

> 
> Please note that, at least in the case of TDX, quotes have a lot bigger 

I think another concern is the Quote format may not be stable (e.g., for those
signed by different QEs), i.e., the location of the TDREPORT in the Quote may be
different.  Right?

> 
> > > 

I wish we can have a more common name rather than "Measurement Registers", but
we are already here. :-)

> They are needed by applications 
> for verifying, for example, security policies that must be enforced. 

I appreciate if youy could elaborate a little bit?  E.g., reading MRCNOFIGID
could be used for enforcing what kinda security policy?

> Do 
> you see the need for reading them now?

No.

> 
> > > They are vendor specific because they are _indeed_ vendor

Yeah thanks for the explanation.  As long as Dan is fine with this "bottom
layer" all good :-)

Thanks again for the detailed reply!

---

## [15] Dionna Amalie Glaze — 2025-03-19
*Subject: Re: [PATCH v2 1/4] tsm: Add TVM Measurement Register support*

On Wed, Mar 19, 2025 at 4:29 AM Huang, Kai <kai.huang@intel.com> wrote:
>
> On Mon, 2025-03-17 at 17:49 -0500, Xing, Cedric wrote:

The IETF RATS working group has proposed a general measurement type of
"integrity registers" in the CoRIM draft spec to accommodate PCRs and
RTMRs.
/shrug

>
> > They are needed by applications

---
