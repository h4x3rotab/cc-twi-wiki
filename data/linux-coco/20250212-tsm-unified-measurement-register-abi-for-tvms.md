---
title: 'tsm: Unified Measurement Register ABI for TVMs'
date: 2025-02-12
last_reply: 2025-05-01
message_count: 42
participants: ['Cedric Xing', 'Dave Hansen', 'kernel test robot', 'Huang, Kai', 'Sathyanarayanan Kuppuswamy', 'Mikko Ylinen', 'Dan Middleton', 'Dionna Amalie Glaze', 'James Bottomley', 'Dan Williams']
---

## [1] Cedric Xing — 2025-02-12

NOTE: This patch series introduces the Measurement Register (MR) ABI, and
is a continuation of the RFC series on the same topic [1].

This patch series adds a unified interface to TSM core for confidential
computing (CC) guest drivers to provide access to measurement registers
(MRs), which are essential for relying parties (RPs) to verify the
integrity of the computing environment. The interface is structured around
`struct tsm_measurement`, which holds an array of `struct
tsm_measurement_register` and includes operations for reading and updating
MRs.

Each `struct tsm_measurement_register` features a `mr_flags` member that
indicates the MR's properties, such as *Readable* (`TSM_MR_F_R`),
*Extensible* (`TSM_MR_F_X`), etc. Please refer to Patch 1 in this series
for more details. Patch 2 adds a sample module to demonstrate how to define
and implement MRs in a CC guest driver. The last patches add TDX MR support
to the TDX Guest driver.

MRs are made accessible to applications through a directory tree (rooted at
`/sys/kernel/tsm`). An MR could be presented as either a file containing
its value, or a directory containing the file `digest` under a subdirectory
of the same name as the hash algorithm. By default, an MR will be presented
as a directory unless `TSM_MR_F_F` is set in `mr_flags`.

[1]: https://lore.kernel.org/linux-coco/20241210-tsm-rtmr-v3-0-5997d4dbda73@intel.com/

Signed-off-by: Cedric Xing <cedric.xing@intel.com>
---
Cedric Xing (3):
      tsm: Add TVM Measurement Register support
      tsm: Add TSM measurement sample code
      x86/tdx: Expose TDX MRs through TSM sysfs interface

Kuppuswamy Sathyanarayanan (1):
      x86/tdx: Add tdx_mcall_rtmr_extend() interface

 Documentation/ABI/testing/sysfs-kernel-tsm |  20 ++
 MAINTAINERS                                |   3 +-
 arch/x86/coco/tdx/tdx.c                    |  36 +++
 arch/x86/include/asm/shared/tdx.h          |   1 +
 arch/x86/include/asm/tdx.h                 |   2 +
 drivers/virt/coco/Kconfig                  |   3 +-
 drivers/virt/coco/Makefile                 |   2 +
 drivers/virt/coco/tdx-guest/Kconfig        |  15 ++
 drivers/virt/coco/tdx-guest/tdx-guest.c    | 119 +++++++++
 drivers/virt/coco/{tsm.c => tsm-core.c}    |   6 +-
 drivers/virt/coco/tsm-mr.c                 | 375 +++++++++++++++++++++++++++++
 include/linux/tsm.h                        |  64 +++++
 samples/Kconfig                            |  10 +
 samples/Makefile                           |   1 +
 samples/tsm/Makefile                       |   2 +
 samples/tsm/tsm_mr_sample.c                | 107 ++++++++
 16 files changed, 763 insertions(+), 3 deletions(-)
---
base-commit: a64dcfb451e254085a7daee5fe51bf22959d52d3
change-id: 20250209-tdx-rtmr-255479667146

Best regards,

---

## [2] Cedric Xing — 2025-02-12
*Subject: [PATCH 1/4] tsm: Add TVM Measurement Register support*

This commit extends the TSM core with support for CC measurement registers
(MRs).

The newly added APIs are:

- `tsm_register_measurement(struct tsm_measurement *)`: This API allows a
  CC guest driver to register a set of measurement registers with the TSM
  core.
- `tsm_unregister_measurement(struct tsm_measurement *)`: This API enables
  a CC guest driver to unregister a previously registered set of
  measurement registers.

`struct tsm_measurement` has been defined to encapsulate the details of
CC-specific MRs. It includes an array of `struct tsm_measurement_register`s
and provides operations for reading and updating these registers. For a
comprehensive understanding of the structure and its usage, refer to the
detailed comments in `include/linux/tsm.h`.

Upon successful registration of a measurement provider, the TSM core
exposes the MRs through a directory tree in the sysfs filesystem. The root
of this tree is located at `/sys/kernel/tsm/MR_PROVIDER/`, where
`MR_PROVIDER` is the name of the measurement provider (as specified by
`struct tsm_measurement::name`). Each MR is made accessible as either a
file or a directory of the specified name (i.e.,
`tsm_measurement_register::mr_name`). In the former case, the file content
is the MR value; while in the latter case `HASH_ALG/digest` under the MR
directory contains the MR value, where `HASH_ALG` specifies the hash
algorithm (e.g., sha256, sha384, etc.) used by this MR.

*Crypto Agility* is supported as a set of independent MRs that share a
common name. These MRs will be merged into a single MR directory and each
will be represented by its respective `HASH_ALG/digest` file. Note that
`tsm_measurement_register::mr_hash` must be distinct or the behavior is
undefined.

Signed-off-by: Cedric Xing <cedric.xing@intel.com>
---
 Documentation/ABI/testing/sysfs-kernel-tsm |  20 ++
 MAINTAINERS                                |   2 +-
 drivers/virt/coco/Kconfig                  |   3 +-
 drivers/virt/coco/Makefile                 |   2 +
 drivers/virt/coco/{tsm.c => tsm-core.c}    |   6 +-
 drivers/virt/coco/tsm-mr.c                 | 375 +++++++++++++++++++++++++++++
 include/linux/tsm.h                        |  64 +++++
 7 files changed, 469 insertions(+), 3 deletions(-)

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
index 25c86f47353d..c129fccd3d5a 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -24098,7 +24098,7 @@ M:	Dan Williams <dan.j.williams@intel.com>
 L:	linux-coco@lists.linux.dev
 S:	Maintained
 F:	Documentation/ABI/testing/configfs-tsm
-F:	drivers/virt/coco/tsm.c
+F:	drivers/virt/coco/tsm*.c
 F:	include/linux/tsm.h
 
 TRUSTED SERVICES TEE DRIVER
diff --git a/drivers/virt/coco/Kconfig b/drivers/virt/coco/Kconfig
index ff869d883d95..6f3c0831680b 100644
--- a/drivers/virt/coco/Kconfig
+++ b/drivers/virt/coco/Kconfig
@@ -5,7 +5,8 @@
 
 config TSM_REPORTS
 	select CONFIGFS_FS
-	tristate
+	select CRYPTO_HASH_INFO
+	tristate "Trusted Security Module (TSM) sysfs/configfs support"
 
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
index 000000000000..8d26e952da6b
--- /dev/null
+++ b/drivers/virt/coco/tsm-mr.c
@@ -0,0 +1,375 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/* Copyright(c) 2024-2025 Intel Corporation. All rights reserved. */
+
+#define pr_fmt(fmt) KBUILD_MODNAME ": " fmt
+
+#include <crypto/hash.h>
+#include <crypto/hash_info.h>
+#include <linux/kobject.h>
+#include <linux/module.h>
+#include <linux/tsm.h>
+
+int tsm_mr_init(void);
+void tsm_mr_exit(void);
+
+enum tmr_dir_battr_index {
+	TMR_DIR_BA_DIGEST,
+	TMR_DIR_BA__COUNT,
+
+	TMR_DIR__ALGO_MAX = 4,
+};
+
+struct tmr_dir {
+	struct kobject kobj;
+	struct bin_attribute battrs[TMR_DIR__ALGO_MAX][TMR_DIR_BA__COUNT];
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
+			       char *page, loff_t off, size_t count)
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
+	mr = (typeof(mr))attr->private;
+	pvd = tmr_mr_to_provider(mr, kobj);
+	rc = down_read_interruptible(&pvd->rwsem);
+	if (rc)
+		return rc;
+
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
+		memcpy(page, mr->mr_value + off, count);
+
+	up_read(&pvd->rwsem);
+	return rc ?: count;
+}
+
+static ssize_t tmr_digest_write(struct file *filp, struct kobject *kobj, struct bin_attribute *attr,
+				char *page, loff_t off, size_t count)
+{
+	const struct tsm_measurement_register *mr;
+	struct tmr_provider *pvd;
+	ssize_t rc;
+
+	if (off != 0 || count != attr->size)
+		return -EINVAL;
+
+	mr = (typeof(mr))attr->private;
+	pvd = tmr_mr_to_provider(mr, kobj);
+	rc = down_write_killable(&pvd->rwsem);
+	if (rc)
+		return rc;
+
+	if (mr->mr_flags & TSM_MR_F_X)
+		rc = tmr_call_extend(pvd, mr, page);
+	else
+		memcpy(mr->mr_value, page, count);
+
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
+		if (++mrd->algo >= TMR_DIR__ALGO_MAX) {
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
+		if (IS_ERR(mrd))
+			return PTR_ERR(mrd);
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
index 11b0c525be30..624a7b62b85d 100644
--- a/include/linux/tsm.h
+++ b/include/linux/tsm.h
@@ -5,6 +5,7 @@
 #include <linux/sizes.h>
 #include <linux/types.h>
 #include <linux/uuid.h>
+#include <uapi/linux/hash_info.h>
 
 #define TSM_INBLOB_MAX 64
 #define TSM_OUTBLOB_MAX SZ_32K
@@ -109,4 +110,67 @@ struct tsm_ops {
 
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
+ * @TSM_MR_F_X: this MR supports the extension semantics on write
+ * @TSM_MR_F_W: this MR is writable
+ * @TSM_MR_F_R: this MR is readable. This should typically be set
+ * @TSM_MR_F_L: this MR is live - writes to other MRs may change this MR
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
+ * @refresh: invoked to update the specified MR
+ * @extend: invoked to extend the specified MR with mr_size bytes
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

## [3] Cedric Xing — 2025-02-12
*Subject: [PATCH 2/4] tsm: Add TSM measurement sample code*

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
  extensions; as a result, `rtmr0/sha256/digest` is read-only.
- `rtmr1` is an RTMR with `TSM_MR_F_W` **set**, permitting direct
  extensions; thus, `rtmr1/sha384/digest` is writable.
- `rtmr_crypto_agile` demonstrates a "single" MR that supports multiple
  hash algorithms. Each supported algorithm has a corresponding digest,
  usually referred to as a "bank" in TCG terminology. In this specific
  sample, the 2 banks are aliased to `rtmr0` and `rtmr1`, respectively.
- `report_digest` contains the digest of the internal report structure
  living in this sample module's memory. It is to demonstrate the use of
  the `TSM_MR_F_L` flag. Its value changes each time an RTMR is extended.

More details can be found in `samples/tsm/tsm_mr_sample.c`.

Signed-off-by: Cedric Xing <cedric.xing@intel.com>
---
 MAINTAINERS                 |   1 +
 samples/Kconfig             |  10 +++++
 samples/Makefile            |   1 +
 samples/tsm/Makefile        |   2 +
 samples/tsm/tsm_mr_sample.c | 107 ++++++++++++++++++++++++++++++++++++++++++++
 5 files changed, 121 insertions(+)

diff --git a/MAINTAINERS b/MAINTAINERS
index c129fccd3d5a..56d0d7fee91a 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -24100,6 +24100,7 @@ S:	Maintained
 F:	Documentation/ABI/testing/configfs-tsm
 F:	drivers/virt/coco/tsm*.c
 F:	include/linux/tsm.h
+F:	samples/tsm/*
 
 TRUSTED SERVICES TEE DRIVER
 M:	Balint Dobszay <balint.dobszay@arm.com>
diff --git a/samples/Kconfig b/samples/Kconfig
index 820e00b2ed68..abbfd9547923 100644
--- a/samples/Kconfig
+++ b/samples/Kconfig
@@ -184,6 +184,16 @@ config SAMPLE_TIMER
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

## [4] Cedric Xing — 2025-02-12
*Subject: [PATCH 3/4] x86/tdx: Add tdx_mcall_rtmr_extend() interface*

From: Kuppuswamy Sathyanarayanan <sathyanarayanan.kuppuswamy@linux.intel.com>

The TDX guest exposes one MRTD (Build-time Measurement Register) and
three RTMR (Run-time Measurement Register) registers to record the
build and boot measurements of a virtual machine (VM). These registers
are similar to PCR (Platform Configuration Register) registers in the
TPM (Trusted Platform Module) space. This measurement data is used to
implement security features like attestation and trusted boot.

To facilitate updating the RTMR registers, the TDX module provides
support for the `TDG.MR.RTMR.EXTEND` TDCALL which can be used to
securely extend the RTMR registers.

Add helper function to update RTMR registers. It will be used by the
TDX guest driver in enabling RTMR extension support.

Signed-off-by: Kuppuswamy Sathyanarayanan <sathyanarayanan.kuppuswamy@linux.intel.com>
---
 arch/x86/coco/tdx/tdx.c           | 36 ++++++++++++++++++++++++++++++++++++
 arch/x86/include/asm/shared/tdx.h |  1 +
 arch/x86/include/asm/tdx.h        |  2 ++
 3 files changed, 39 insertions(+)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 32809a06dab4..9267fffecbef 100644
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
+ * tdx_mcall_rtmr_extend() - Wrapper to extend RTMR registers using
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
+int tdx_mcall_rtmr_extend(u8 index, u8 *data)
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
+EXPORT_SYMBOL_GPL(tdx_mcall_rtmr_extend);
+
 /**
  * tdx_hcall_get_quote() - Wrapper to request TD Quote using GetQuote
  *                         hypercall.
diff --git a/arch/x86/include/asm/shared/tdx.h b/arch/x86/include/asm/shared/tdx.h
index fcbbef484a78..7b95c3113e79 100644
--- a/arch/x86/include/asm/shared/tdx.h
+++ b/arch/x86/include/asm/shared/tdx.h
@@ -12,6 +12,7 @@
 
 /* TDX module Call Leaf IDs */
 #define TDG_VP_VMCALL			0
+#define TDG_MR_RTMR_EXTEND		2
 #define TDG_VP_INFO			1
 #define TDG_VP_VEINFO_GET		3
 #define TDG_MR_REPORT			4
diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index b4b16dafd55e..6c73ab759223 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -64,6 +64,8 @@ bool tdx_early_handle_ve(struct pt_regs *regs);
 
 int tdx_mcall_get_report0(u8 *reportdata, u8 *tdreport);
 
+int tdx_mcall_rtmr_extend(u8 index, u8 *data);
+
 u64 tdx_hcall_get_quote(u8 *buf, size_t size);
 
 void __init tdx_dump_attributes(u64 td_attr);

---

## [5] Cedric Xing — 2025-02-12
*Subject: [PATCH 4/4] x86/tdx: Expose TDX MRs through TSM sysfs interface*

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
enabled/disabled by setting CONFIG_TDX_GUEST_DRIVER_TSM_REPORT to Y/n.

Signed-off-by: Cedric Xing <cedric.xing@intel.com>
---
 drivers/virt/coco/tdx-guest/Kconfig     |  15 ++++
 drivers/virt/coco/tdx-guest/tdx-guest.c | 119 ++++++++++++++++++++++++++++++++
 2 files changed, 134 insertions(+)

diff --git a/drivers/virt/coco/tdx-guest/Kconfig b/drivers/virt/coco/tdx-guest/Kconfig
index 22dd59e19431..effadcfd9918 100644
--- a/drivers/virt/coco/tdx-guest/Kconfig
+++ b/drivers/virt/coco/tdx-guest/Kconfig
@@ -9,3 +9,18 @@ config TDX_GUEST_DRIVER
 
 	  To compile this driver as module, choose M here. The module will
 	  be called tdx-guest.
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
index 224e7dde9cde..c95aa17e728c 100644
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
@@ -304,6 +308,114 @@ static const struct tsm_ops tdx_tsm_ops = {
 	.report_bin_attr_visible = tdx_report_bin_attr_visible,
 };
 
+enum {
+	TDREPORT_reportdata = 128,
+	TDREPORT_tdinfo = 512,
+	TDREPORT_mrtd = TDREPORT_tdinfo + 16,
+	TDREPORT_mrconfigid = TDREPORT_mrtd + 48,
+	TDREPORT_mrowner = TDREPORT_mrconfigid + 48,
+	TDREPORT_mrownerconfig = TDREPORT_mrowner + 48,
+	TDREPORT_rtmr0 = TDREPORT_mrownerconfig + 48,
+	TDREPORT_rtmr1 = TDREPORT_rtmr0 + 48,
+	TDREPORT_rtmr2 = TDREPORT_rtmr1 + 48,
+	TDREPORT_rtmr3 = TDREPORT_rtmr2 + 48,
+	TDREPORT_servtd_hash = TDREPORT_rtmr3 + 48,
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
+#ifdef CONFIG_TDX_GUEST_DRIVER_TSM_REPORT
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
+	if (virt_addr_valid(tdx_mr_report))
+		tdreport = tdx_mr_report;
+	else {
+		tdreport = kmalloc(sizeof(tdx_mr_report), GFP_KERNEL);
+		if (!tdreport)
+			return -ENOMEM;
+
+		reportdata = memcpy(tdreport + TDREPORT_reportdata, reportdata,
+				    TDX_REPORTDATA_LEN);
+	}
+
+	ret = tdx_mcall_get_report0(reportdata, tdreport);
+	if (ret)
+		pr_err("GetReport call failed\n");
+
+	if (tdreport != tdx_mr_report) {
+		memcpy(tdx_mr_report, tdreport, sizeof(tdx_mr_report));
+		kfree(tdreport);
+	}
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
+	if (virt_addr_valid(data))
+		buf = (u8 *)data;
+	else {
+		buf = kmalloc(64, GFP_KERNEL);
+		if (!buf)
+			return -ENOMEM;
+
+		memcpy(buf, data, mr->mr_size);
+	}
+
+	ret = tdx_mcall_rtmr_extend((u8)(mr - tmr->mrs), buf);
+	if (ret)
+		pr_err("Extending RTMR%ld failed\n", mr - tmr->mrs);
+
+	if (buf != data)
+		kfree(buf);
+
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
@@ -326,8 +438,14 @@ static int __init tdx_guest_init(void)
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
@@ -339,6 +457,7 @@ module_init(tdx_guest_init);
 
 static void __exit tdx_guest_exit(void)
 {
+	tsm_unregister_measurement(&tdx_measurement);
 	tsm_unregister(&tdx_tsm_ops);
 	free_quote_buf(quote_data);
 	misc_deregister(&tdx_misc_dev);

---

## [6] Dave Hansen — 2025-02-12
*Subject: Re: [PATCH 0/4] tsm: Unified Measurement Register ABI for TVMs*

On 2/12/25 18:23, Cedric Xing wrote:
> NOTE: This patch series introduces the Measurement Register (MR) ABI, and
> is a continuation of the RFC series on the same topic [1].

Hi Cedric,

Could you please explain how the benefits of this series are helpful to
end users?

---

## [7] Xing, Cedric — 2025-02-13
*Subject: Re: [PATCH 0/4] tsm: Unified Measurement Register ABI for TVMs*

On 2/12/2025 10:50 PM, Dave Hansen wrote:
> On 2/12/25 18:23, Cedric Xing wrote:
>> NOTE: This patch series introduces the Measurement Register (MR) ABI, and

This series exposes MRs as sysfs attributes, allowing end users to 
access them effortlessly without needing to write any code. This 
simplifies the process of debugging and diagnosing measurement-related 
issues. Additionally, it makes the CC architecture more intuitive for 
newcomers.

---

## [8] Dave Hansen — 2025-02-13
*Subject: Re: [PATCH 0/4] tsm: Unified Measurement Register ABI for TVMs*

On 2/13/25 08:21, Xing, Cedric wrote:
> On 2/12/2025 10:50 PM, Dave Hansen wrote:
>> On 2/12/25 18:23, Cedric Xing wrote:

Wait a sec, so there's already ABI for manipulating these? This just
adds a parallel sysfs interface to the existing ABI?

Also, you're saying that users don't need to write any code, but then
provide... sample code. That's unexpected.

Oh, and you seem to have forgotten to attach the sysfs ABI documentation
patch to the series. You did write the required documentation, right? ;)

---

## [9] Xing, Cedric — 2025-02-13
*Subject: Re: [PATCH 0/4] tsm: Unified Measurement Register ABI for TVMs*

On 2/13/2025 10:58 AM, Dave Hansen wrote:
> On 2/13/25 08:21, Xing, Cedric wrote:
>> On 2/12/2025 10:50 PM, Dave Hansen wrote:
No, this is new. There's no existing ABI for accessing measurement 
registers from within a TVM (TEE VM). Currently, on TDX for example, 
reading TDX measurement registers (MRs) must be done by getting a TD 
quote. And there's no way to extend any RTMRs. Therefore, it would be 
much easier end users to debug/diagnose measurement related issues 
(which would almost always require reading MRs) with this patch.

> Also, you're saying that users don't need to write any code, but then
> provide... sample code. That's unexpected.
The sample code is to demo how to expose MRs from a CC guest driver, but 
not for end users to access those MRs.

> Oh, and you seem to have forgotten to attach the sysfs ABI documentation
> patch to the series. You did write the required documentation, right? ;)
Documentation/ABI/testing/sysfs-kernel-tsm (new file added by patch 1) 
contains a description on the attributes added by the patch.

---

## [10] Dave Hansen — 2025-02-13
*Subject: Re: [PATCH 0/4] tsm: Unified Measurement Register ABI for TVMs*

On 2/13/25 13:50, Xing, Cedric wrote:
> On 2/13/2025 10:58 AM, Dave Hansen wrote:
...
>> Wait a sec, so there's already ABI for manipulating these? This just
>> adds a parallel sysfs interface to the existing ABI?

Ok, that makes sense.

But if this is for debug, wouldn't these belong better in debugfs? Do we
really want to maintain this interface forever? There's no shame in debugfs.

>> Also, you're saying that users don't need to write any code, but then
>> provide... sample code. That's unexpected.

Whoops! I went looking for it but I'm blind, evidently. Thanks for
pointing it out.

---

## [11] kernel test robot — 2025-02-14
*Subject: Re: [PATCH 1/4] tsm: Add TVM Measurement Register support*

Hi Cedric,

kernel test robot noticed the following build warnings:

[auto build test WARNING on a64dcfb451e254085a7daee5fe51bf22959d52d3]

url:    https://github.com/intel-lab-lkp/linux/commits/Cedric-Xing/tsm-Add-TVM-Measurement-Register-support/20250213-102639
base:   a64dcfb451e254085a7daee5fe51bf22959d52d3
patch link:    https://lore.kernel.org/r/20250212-tdx-rtmr-v1-1-9795dc49e132%40intel.com
patch subject: [PATCH 1/4] tsm: Add TVM Measurement Register support
config: nios2-kismet-CONFIG_CRYPTO_HASH_INFO-CONFIG_TSM_REPORTS-0-0 (https://download.01.org/0day-ci/archive/20250214/202502140854.9CZ1xPmC-lkp@intel.com/config)
reproduce: (https://download.01.org/0day-ci/archive/20250214/202502140854.9CZ1xPmC-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202502140854.9CZ1xPmC-lkp@intel.com/

kismet warnings: (new ones prefixed by >>)
>> kismet: WARNING: unmet direct dependencies detected for CRYPTO_HASH_INFO when selected by TSM_REPORTS
   WARNING: unmet direct dependencies detected for CRYPTO_HASH_INFO
     Depends on [n]: CRYPTO [=n]
     Selected by [y]:
     - TSM_REPORTS [=y] && VIRT_DRIVERS [=y]

---

## [12] Xing, Cedric — 2025-02-14
*Subject: Re: [PATCH 0/4] tsm: Unified Measurement Register ABI for TVMs*

On 2/13/2025 5:19 PM, Dave Hansen wrote:
> On 2/13/25 13:50, Xing, Cedric wrote:
>> On 2/13/2025 10:58 AM, Dave Hansen wrote:
There are many other (more important/significant) uses besides debugging.

For example, any applications that make use of runtime measurements must 
extend RTMRs, and this interface provides that exact functionality.

Another example, a policy may be associated with a TD (e.g., CoCo) by 
storing its digest in MRCONFIGID, so that the policy could be verified 
against its digest at runtime. This interface allows applications to 
read MRCONFIGID.

---

## [13] Dave Hansen — 2025-02-14
*Subject: Re: [PATCH 0/4] tsm: Unified Measurement Register ABI for TVMs*

On 2/14/25 08:19, Xing, Cedric wrote:
>> But if this is for debug, wouldn't these belong better in debugfs? Do we
>> really want to maintain this interface forever? There's no shame in

The attestation world is horrifically complicated, and I don't
understand the details at _all_. You're going to have to explain this
one to me like I'm five.

Could you also explain how this is different from the hardware and
virtual TPMs and why this doesn't fit into that existing framework? How
are TVMs novel? What justifies all this new stuff?

---

## [14] Xing, Cedric — 2025-02-14
*Subject: Re: [PATCH 0/4] tsm: Unified Measurement Register ABI for TVMs*

On 2/14/2025 10:26 AM, Dave Hansen wrote:
> On 2/14/25 08:19, Xing, Cedric wrote:
>>> But if this is for debug, wouldn't these belong better in debugfs? Do we
TVM (TEE VM) is a broad term referring to encrypted/protected VMs on 
various confidential computing (CC) architectures, such as AMD SEV, Arm 
CCA, Intel TDX, etc. Each of these architectures includes hardware 
components for storing software measurements, known as measurement 
registers (MRs). This patch series aims to provide the necessary 
functionality for applications that need to access these MRs.

There are no real/hardware TPMs but only virtual ones in TVMs. Virtual 
TPMs can be built upon the native MRs provided by the underlying CC 
architectures.

If you need more detailed information, I'd be happy to discuss it 
further offline to avoid cluttering the mailing list.

---

## [15] Huang, Kai — 2025-02-17
*Subject: Re: [PATCH 1/4] tsm: Add TVM Measurement Register support*

Hi Cedric,

[...]

> +static ssize_t tmr_digest_read(struct file *filp, struct kobject *kobj, struct bin_attribute *attr,
> +			       char *page, loff_t off, size_t count)

Better to rename 'page' to 'buffer'?

Since page normally implies 4KB alignment but I don't see we need the 
alignment here.

> +{
> +	const struct tsm_measurement_register *mr;

The logic around using pvd->in_sync is kinda complicated.  MR operations 
seem like a classic reader/writer contention problem and I am not sure 
why pvd->in_sync is needed.  Could you help to clarify?

[...]

> +
> +/**

Why a MR can be written w/o being extended?  What is the use case of this?

> + * @TSM_MR_F_R: this MR is readable. This should typically be set
> + * @TSM_MR_F_L: this MR is live - writes to other MRs may change this MR

Why one MR can be changed by writing to other MRs?

> + * @TSM_MR_F_F: present this MR as a file (instead of a directory)
> + * @TSM_MR_F_LIVE: shorthand for L (live) and R (readable)

I am not sure whether we need so many flags.  To me seems like we only need:

  - TSM_MR_ENABLED:  The MR has been initialized with a certain algo.
  - TSM_MR_UNLOCKED: The MR is writable and any write will extend it.
  - TSM_MR_LOCKED:   The MR is locked and finalized.

The TSM_MR_ENABLED may not be needed either, but I think it's better to 
have it so that the kernel can reject both read/write from userspace.

> +
> +#define TSM_MR_(mr, hash)                                                           \

 From the description above, I don't quite follow what does ->refresh() 
do exactly.  Could you clarify why we need it?

---

## [16] Huang, Kai — 2025-02-17
*Subject: Re: [PATCH 3/4] x86/tdx: Add tdx_mcall_rtmr_extend() interface*

> @@ -135,6 +136,41 @@ int tdx_mcall_get_report0(u8 *reportdata, u8 *tdreport)
>   }

Nit:  I would prefer to name it as tdx_mcall_extend_rtmr() since this 
matches the existing tdx_mcall_get_report0() (and tdx_hcall_get_quote()) 
better.  But no strong opinion.

---

## [17] Huang, Kai — 2025-02-17
*Subject: Re: [PATCH 1/4] tsm: Add TVM Measurement Register support*

On Mon, 2025-02-17 at 13:17 +1300, Huang, Kai wrote:
> Hi Cedric,
> 

[...]

> > 
> > +#define TSM_MR_(mr, hash)                                                           \

After reading patch 4, I figured out the purpose of the pvd->in_sync and the
refresh() myself:

Each call of ->extend() will update the value of the MR, but only in the
hardware/firmware.  The MR value maintained by the kernel is unchanged so it
will be out-of-date after the ->extend().  Therefore the kernel needs to keep
them synced first when userspace reads the MR, using the ->refresh().

It's also feasible to always sync/refresh after each extend(), eliminating the
pvd->in_sync logic completely, but it's not desired -- because the sync
operation talks to the hardware/firmware thus could be time-consuming, and we in
general only needs to sync before reading the value to the userspace.  E.g.,
this saves a lot of sync operation if userspace extends the MR multi-times with
large chunk of data and then reads the final value once.

So the pvd->in_sync logic seems useful to me, but I think it would be better to
a comment to explain this in both tmr_digest_read() and tmr_digest_write(). 
E.g., something like below before the code which checks pvd->in_sync in the
tmr_digest_read()?

	/*
	 * Each write-and-extend to the MR will update the MR, but only in
	 * TSM hardware/firmware, leaving the MR value maintained by the kernel
	 * out-of-date.  Sync MR value in TSM hardware/firmware to the kernel 
	 * before returning to the userspace in this case.
	 */
	if ((mr->mr_flags & TSM_MR_F_L) && !pvd->in_sync) {
		...

The description of the refresh() callback is also not clear to me.  Perhaps
something like below?

	/*
	 * ...
	 * @refresh: sync MR value in TSM hardware/firmware to the kernel
buffer
	 * ...
	 */

---

## [18] Xing, Cedric — 2025-02-17
*Subject: Re: [PATCH 1/4] tsm: Add TVM Measurement Register support*

Hi Kai,

On 2/16/2025 6:17 PM, Huang, Kai wrote:
> Hi Cedric,
> 

'page' was used here to imply the size of the buffer cannot exceed a 
page (which is the current behavior of the kernel). But I agree with you 
and will make the changes.

[...]

> The logic around using pvd->in_sync is kinda complicated.  MR operations 
> seem like a classic reader/writer contention problem and I am not sure 
If in_sync is true, then "refresh()" will NOT be invoked on reads from 
"live" MRs.

For example, on TDX, if an RTMR has NOT been extended since the last 
read, then the next read will return the cached copy of the RTMR value - 
i.e., saving a "refresh()" call (which must issue TDCALL[TDG.MR.REPORT] 
to reread all MRs and can be slow).

> [...]
> 

This is because "write" may not be the only way to extend an RTMR. For 
example, the current ABI proposed by this patch can be considered "MR 
centric", meaning it's the application that takes care of what to hash, 
using what algorithm, and which RTMR to extend. However, theoretically, 
applications should only be concerned the integrity of some sequence of 
events (the event log). Therefore, there could be a "log centric" ABI 
that allows applications to integrity-protect its logs in a CC-arch 
agnostic manner. And if that's the case, RTMRs may be marked RO ("X w/o 
W") to prevent direct extension.

The use of "W w/o X" is to support pseudo-MRs. For example, `reportdata` 
is such a pseudo-MR that is W but not X. So an application can request a 
TDREPORT by a write to `reportdata` followed by a read from `report0`.

>> + * @TSM_MR_F_R: this MR is readable. This should typically be set
>> + * @TSM_MR_F_L: this MR is live - writes to other MRs may change this MR

Good catch! I'll fix the comment.

>> + * @TSM_MR_F_F: present this MR as a file (instead of a directory)
>> + * @TSM_MR_F_LIVE: shorthand for L (live) and R (readable)

W/X are independent and both necessary (see my previous explanation on 
"X w/o W" and "W w/o X").

I'm not sure if there are non-readable MRs. But theoretically, 
applications inside a TVM (CC guest) may not need to read any MR values. 
Therefore, there could be CC archs (in future) that do not support 
reading all MRs within a guest. And because of that, I decided to keep R 
as an independent bit.

L is to indicate an MR's value may not match its last write.

F is for CC guest to expose (pseudo) MRs that may not have an associated 
hash algorithm (e.g., `report0` on TDX).

LOCKED/UNLOCKED, from attestation perspective, is NOT a functional but a 
verifiable security property, which is usually implemented by extending 
a special token to the RTMR.

> The TSM_MR_ENABLED may not be needed either, but I think it's better to 
> have it so that the kernel can reject both read/write from userspace.
I'm not sure what a "disabled" MR is and its implication from 
attestation perspective.

>> +
>> +#define TSM_MR_(mr, 

I'll fix the comment.

Basically, refresh() brings all cached MR values up to date. The 
parameter `mr` indicate which MR that has triggered the refresh. On TDX, 
the 1st read after a write to any RTMR will trigger refresh() to reread 
all MRs by TDG.MR.REPORT, while subsequent reads will simply return the 
cached values until the next write to any RTMRs.

-Cedric

---

## [19] Xing, Cedric — 2025-02-17
*Subject: Re: [PATCH 3/4] x86/tdx: Add tdx_mcall_rtmr_extend() interface*

On 2/16/2025 6:40 PM, Huang, Kai wrote:
> 
>> @@ -135,6 +136,41 @@ int tdx_mcall_get_report0(u8 *reportdata, u8 
This actually my preference too!

Sathy, what do you think?

---

## [20] Sathyanarayanan Kuppuswamy — 2025-02-17
*Subject: Re: [PATCH 3/4] x86/tdx: Add tdx_mcall_rtmr_extend() interface*

On 2/17/25 12:58 PM, Xing, Cedric wrote:
> On 2/16/2025 6:40 PM, Huang, Kai wrote:
>>

I have used rtmr_extend() to match with TDCALL name. But I am fine with 
tdx_mcall_extend_rtmr(). We can use it.

---

## [21] Sathyanarayanan Kuppuswamy — 2025-02-17
*Subject: Re: [PATCH 1/4] tsm: Add TVM Measurement Register support*

Hi Cedric,

On 2/12/25 6:23 PM, Cedric Xing wrote:
> This commit extends the TSM core with support for CC measurement registers
> (MRs).

May be include some info on when a MR can be just a file (like an example)

> is the MR value; while in the latter case `HASH_ALG/digest` under the MR
> directory contains the MR value, where `HASH_ALG` specifies the hash

is this required/supported in any of the existing CC providers?

By sharing a common name, you mean internally there will be distinct
registers for every crypto algo supported?

>
> Signed-off-by: Cedric Xing <cedric.xing@intel.com>

Any reason for not using fixed name for registers (like mr[0-n])? May be it
will help if user space use a generic code across vendors.

> +Date:		February 2025
> +Contact:	Cedric Xing <cedric.xing@intel.com>.

IMO, sysfs/configfs part is not required in the title.

>   
>   source "drivers/virt/coco/efi_secret/Kconfig"

Why not use single underscore uniformly?

> +
> +	TMR_DIR__ALGO_MAX = 4,

Since this is not related to attribute index, why not use #define?

> +};
> +

I think you don't need to cast it.

> +	pvd = tmr_mr_to_provider(mr, kobj);
> +	rc = down_read_interruptible(&pvd->rwsem);

Since this path is only taken if in_sync is false, do you need to check 
again?

> +			rc = tmr_call_refresh(pvd, mr);
> +			pvd->in_sync = !rc;

Since this attribute reflects register value, personally I think "value" 
is more clear
than "digest". But it is fine either way.

> +	if (mr->mr_flags & TSM_MR_F_W)
> +		mrd->battrs[mrd->algo][TMR_DIR_BA_DIGEST].attr.mode |= S_IWUSR | S_IWGRP;

Why not add this condition at the top before allocation?

> +
> +	rc = kobject_set_name(&pvd->kset.kobj, "%s", tmr->name);

Why not use _E? Before reading the help text, I thought _X is for execute.

> + * @TSM_MR_F_W: this MR is writable
> + * @TSM_MR_F_R: this MR is readable. This should typically be set

It is not clear why you want to differentiate between write and extension.
Please add some help text related to it.

> +	TSM_MR_F_R = 4,
> +	TSM_MR_F_L = 8,

---

## [22] Sathyanarayanan Kuppuswamy — 2025-02-17
*Subject: Re: [PATCH 0/4] tsm: Unified Measurement Register ABI for TVMs*

On 2/12/25 6:23 PM, Cedric Xing wrote:
> NOTE: This patch series introduces the Measurement Register (MR) ABI, and
> is a continuation of the RFC series on the same topic [1].

I recommend adding information about possible use cases and how end
users might use it here.

> `struct tsm_measurement`, which holds an array of `struct
> tsm_measurement_register` and includes operations for reading and updating

I know that this patch set does not support event log extension for RTMR 
extend.
May be you can add some info about why we cannot support it now and any 
issues
with not supporting it now.

> Signed-off-by: Cedric Xing<cedric.xing@intel.com>
> ---

---

## [23] Huang, Kai — 2025-02-18
*Subject: Re: [PATCH 1/4] tsm: Add TVM Measurement Register support*

> > > +/**
> > > + * enum tsm_measurement_register_flag - properties of an MR

[...]

> However, theoretically, 
> applications should only be concerned the integrity of some sequence of 

I agree "log centric" ABI could be useful.  I don't know a lot of the format of
"event log", but I am thinking that making sure "integrity of some sequence of
events" may not be good enough -- we actually need to make sure "integrity of
each component" that get involved in those events.

E.g., a guest wants to load some particular kernel module during boot and wants
to make sure the correct one gets loaded.  Userspace can trigger an event of
"loading that module" and get this *event log* verified.  But w/o getting the
kernel module binary itself measured as part of this step, we cannot really be
sure whether this step is compromised or not.  In this case, the userspace may
still need to (write and) extend the MR(s).

> And if that's the case, RTMRs may be marked RO ("X w/o 
> W") to prevent direct extension.

Sorry I don't quite follow why RO is enough for "log centric" ABI.  Could you
elaborate a bit?

> 
> The use of "W w/o X" is to support pseudo-MRs. For example, `reportdata` 

I am a little bit confused.  This series is about exposing "measurement
registers" to userspace, so I thought there should be at least some
"measurement" get involved for any entry that is report to userspace.

'reportdata' is more like the nonce embedded to the attestation report, and it
doesn't involve any measurement.

I can see why you want to expose 'reportdata' to userspace, but calling
'reportdata' as measurement register seems unfit.

> 
> > > + * @TSM_MR_F_R: this MR is readable. This should typically be set

[...]

> 
> L is to indicate an MR's value may not match its last write.

"L" doesn't seem to be able to reflect the MR value is out-of-sync. :-)

What does it stand for?

> 
> F is for CC guest to expose (pseudo) MRs that may not have an associated 

OK.  But my thinking is such MR actually isn't MR at all.

> 
> LOCKED/UNLOCKED, from attestation perspective, is NOT a functional but a 

I was thinking from the perspective that userspace may only be interested in one
particular MR.  If that MR is not used, I suppose it should have default value
0.  But I was thinking that "refusing userspace to read" may be better than
"returning 0 to userspace" for a particular MR, if it is not used.

But from attestation's perspective, I tend to agree with you that "disabled MR"
may not be helpful.  We need to send the whole attestation report to the
verifier anyway and the verifier should only care about whether the MR values in
the report matches what the verifier knows.

> 
> > > +

Thanks.

> 
> Basically, refresh() brings all cached MR values up to date. The 

Yeah.  I also think adding some comments around the code using pvd->in_sync
would be helpful, as I mentioned in another reply.

---

## [24] Mikko Ylinen — 2025-02-18
*Subject: Re: [PATCH 0/4] tsm: Unified Measurement Register ABI for TVMs*

On Thu, Feb 13, 2025 at 03:50:19PM -0600, Xing, Cedric wrote:
> On 2/13/2025 10:58 AM, Dave Hansen wrote:
> > On 2/13/25 08:21, Xing, Cedric wrote:

TD reports *are* available through the tdx_guest ioctl so there's overlap
with the suggested reportdata/report0 entries at least. Since configfs-tsm
provides the generic transport for TVM reports, the best option to make report0
available is through configfs-tsm reports.

The use case on MRCONFIGID mentioned later in this thread does not depend
on this series. It's easy for the user-space to interprete the full report
to find MRCONFIGID or any other register value (the same is true for HOSTDATA
on SNP).

The question here is whether there's any real benefit for the kernel to
expose the provider specific report details through sysfs or could we focus on
the RTMR extend capability only.

---

## [25] Dan Middleton — 2025-02-18
*Subject: Re: [PATCH 0/4] tsm: Unified Measurement Register ABI for TVMs*

On 2/14/25 3:59 PM, Xing, Cedric wrote:
> On 2/14/2025 10:26 AM, Dave Hansen wrote:
>> On 2/14/25 08:19, Xing, Cedric wrote:
Hi Dave,

Let me try to add more plain language usages.

This ABI lets applications extend events after boot such that they can be
part of the hardware-based attestation.

One common reason is to _identify the workload_ running in the VM.
Typically a VM attestation tells you that you booted to a clean state.
It is much more valuable to a Relying Party to know that they are 
interacting
with a trusted application / workload.
Projects like CNCF Confidential Containers [1] and Attested Containers
[2] would like to do this.

More generally, Relying Parties can track the state of an application in
the attestation. Auctions are common examples of stateful flows where it
can be meaningful to, e.g., attest that a bid arrived before or after the
close of an auction.

[1] 
https://github.com/confidential-containers/guest-components/blob/main/attestation-agent/attester/src/tdx/rtmr.rs
[2] https://github.com/intel/acon

Thanks,
Dan Middleton

---

## [26] Dave Hansen — 2025-02-18
*Subject: Re: [PATCH 0/4] tsm: Unified Measurement Register ABI for TVMs*

On 2/18/25 08:25, Dan Middleton wrote:
> One common reason is to _identify the workload_ running in the VM.
> Typically a VM attestation tells you that you booted to a clean state.

That's a _bit_ of a different story than the series author mentioned here:


https://lore.kernel.org/all/be7e3c9d-208a-4bda-b8cf-9119f3e0c4ce@intel.com/

It would be great to see a solid, consistent story about what the
purpose of this series is when v2 is posted. As always, it would be even
better if it was obvious that this is not tied to one vendor or one
architecture.

If there are actual end users who care about this, it would be great to
see their acks on it as well.

---

## [27] Xing, Cedric — 2025-02-18
*Subject: Re: [PATCH 1/4] tsm: Add TVM Measurement Register support*

On 2/18/2025 3:14 AM, Huang, Kai wrote:
> 
>>>> +/**
By "some sequence of events", I was talking from the perspective of an 
application. Different applications will generate independent sequences 
of events and because different CC archs offer different types and 
numbers of MRs that use different hash algorithms, what we need is a SW 
arch that can "pack" those sequences into something that can be 
integrity-protected by the HW resource from the underlying CC arch, then 
"unpack" it back to independent sequences to be verified/appraised by 
potentially independent entities. The "log centric" ABI will be part of 
such an architecture. This is too big a topic to solve by this patch. 
For now, what matters is just not to create roadblocks.

> E.g., a guest wants to load some particular kernel module during boot and wants
> to make sure the correct one gets loaded.  Userspace can trigger an event of
By the term "event", it usually implies accompanying "event data", which 
could be/contain the measurements of the kernel modules.

You are talking about actual uses of RTMRs and this patch aims to enable 
those exact uses. :-)

>> And if that's the case, RTMRs may be marked RO ("X w/o
>> W") to prevent direct extension.
My apologies for the confusion again! R/W controls the file permissions 
of the sysfs attributes, while X is the semantics of the MR. Clearing W 
prevents direct "write" to the attribute (by user mode) but doesn't 
prevent the MR from being extended through other interfaces. It isn't 
obvious in this patch because the "log centric" ABI has been taken out. 
It was originally proposed in 
https://lore.kernel.org/all/20240907-tsm-rtmr-v1-0-12fc4d43d4e7@intel.com/

>>
>> The use of "W w/o X" is to support pseudo-MRs. For example, `reportdata`
Glad that you see why! I called it a pseudo-MR but there could be better 
names. The intention of this patch is to create a sysfs tree that offers 
all measurement related functionalities to user mode applications. 
`reportdata` plays a role here because it usually carries the digest of 
something that the guest wants to attest to.

>>
>>>> + * @TSM_MR_F_R: this MR is readable. This should typically be set
L stands for Live. It indicates to the TSM MR core that the value of the 
MR is different than the last value written, hence should issue 
refresh() to read the value back from HW (instead of using the cached 
value obtained from the last write).

>>
>> F is for CC guest to expose (pseudo) MRs that may not have an associated
Besides Measurement Register, MR can also stand for MeasuRement. Not to 
debate what MR stands for, but this patch aims to capture/expose all 
measurement related functionalities. `report0` offers less understood 
yet important info beyond measurement registers, such as CPUSVN and 
measurements of the TDX module, so is considered within the scope.

>>
>> LOCKED/UNLOCKED, from attestation perspective, is NOT a functional but a
I'd try not to predict what applications need but focus on what the HW 
offers. HW features are usually motivated by specific usages, but their 
actual uses are usually way beyond.

Moreover, the traditional Linux file ownership/permissions can satisfy 
this need very easily.

> But from attestation's perspective, I tend to agree with you that "disabled MR"
> may not be helpful.  We need to send the whole attestation report to the

---

## [28] Dionna Amalie Glaze — 2025-02-18
*Subject: Re: [PATCH 0/4] tsm: Unified Measurement Register ABI for TVMs*

On Tue, Feb 18, 2025 at 8:57 AM Dave Hansen <dave.hansen@intel.com> wrote:
>
> On 2/18/25 08:25, Dan Middleton wrote:

We would like to have this for Google Confidential Space and Kubernetes Engine.

Acked-by: Dionna Glaze <dionnaglaze@google.com>

---

## [29] Dave Hansen — 2025-02-18
*Subject: Re: [PATCH 0/4] tsm: Unified Measurement Register ABI for TVMs*

On 2/18/25 15:57, Dionna Amalie Glaze wrote:
>> If there are actual end users who care about this, it would be great to
>> see their acks on it as well.

Great! Thanks for chiming in. Can you talk for a second, though, about
why this is useful and how you plan to use it? Is it for debugging?

---

## [30] Dionna Amalie Glaze — 2025-02-18
*Subject: Re: [PATCH 0/4] tsm: Unified Measurement Register ABI for TVMs*

On Tue, Feb 18, 2025 at 4:41 PM Dave Hansen <dave.hansen@intel.com> wrote:
>
> On 2/18/25 15:57, Dionna Amalie Glaze wrote:

Confidential space on SEV depends on the hypervisor-provided vTPM to
provide remotely attestable quotes of its PCRs, and the corresponding
event logs.
https://github.com/google/go-tpm-tools/blob/main/launcher/agent/agent.go#L97

On TDX and ARM CCA (maybe RISC-V CoVE someday), we don't want to have
to depend on the vTPM.
There are runtime measurement registers and the CCEL.
When we have a sysfs interface to extend these registers, it makes the
user space evidence manager's life easier.
When Dan Williams forced the issue about configfs-tsm, we were told
that it is bad for the kernel to have many platform-specific
interfaces for attestation operations.
This patch series is a way to unify behind the tsm.

As for the ability to read the registers through sysfs instead of just
extend-on-write, that's not something Confidential Space depends on
specifically.
Our attestation policies are evaluated in a verification service
rather than on-node.

For on-node policy evaluation, for instance in kubectl, there is a
benefit to being able to generically read measurement registers that
have been extended generically to execute policy that a certain action
if a measurement register isn't an exact expected value.
This is not far-fetched, since it is used for confidential containers,
and is being discussed for kubernetes engine as a way to poison an
instance when an ssh session is terminated for a human operator.

To have that same capability without a generic read interface, we need
to stuff kubectl with quote parsers of every attestation technology.

Hope that helps.

---

## [31] Xing, Cedric — 2025-02-18
*Subject: Re: [PATCH 0/4] tsm: Unified Measurement Register ABI for TVMs*

On 2/18/2025 8:49 AM, Mikko Ylinen wrote:
> On Thu, Feb 13, 2025 at 03:50:19PM -0600, Xing, Cedric wrote:
>> On 2/13/2025 10:58 AM, Dave Hansen wrote:
Given the purpose of TSM, I once thought this TDX_CMD_GET_REPORT0 ioctl 
of /dev/tdx_guest had been deprecated but I was wrong.

However, unlocked_ioctl is the only fops remaining on /dev/tdx_guest and 
TDX_CMD_GET_REPORT0 is the only command supported. It might soon be time 
to deprecate this interface.

> The use case on MRCONFIGID mentioned later in this thread does not depend
> on this series. It's easy for the user-space to interprete the full report
Yes, parsing the full report will always be an option. But reading 
static MRs like MRCONDFIGID or HOSTDATA from sysfs attributes will be 
way more convenient.

Additionally, this sysfs interface is more friendly to newcomers, as 
everyone can tell what MRs are available from the directory tree 
structure, rather than studying processor manuals.

> The question here is whether there's any real benefit for the kernel to
> expose the provider specific report details through sysfs or could we focus on
Again, parsing the full report is always an alternative for reading any 
MRs from the underlying arch. But it's much more convenient to read them 
from files, which I believe is a REAL benefit.

Or can we flip the question around and ask: is there any real benefit 
NOT to allow reading MRs as files and force users and applications to go 
through an arch specific IOCTL interface?

---

## [32] Huang, Kai — 2025-02-19
*Subject: Re: [PATCH 0/4] tsm: Unified Measurement Register ABI for TVMs*

On Tue, 2025-02-18 at 22:04 -0600, Xing, Cedric wrote:
> On 2/18/2025 8:49 AM, Mikko Ylinen wrote:
> > On Thu, Feb 13, 2025 at 03:50:19PM -0600, Xing, Cedric wrote:

I agree.

> 
> > The use case on MRCONFIGID mentioned later in this thread does not depend

But, theoretically, you cannot really trust what your read from the kernel for
such *single field*, because to truly get verified you will need to get the full
report anyway.

> 
> Additionally, this sysfs interface is more friendly to newcomers, as 

As above, I am not convinced that *reading* MRs alone is that useful.  What you
need is a unified way to *extend* those MRs.

And yeah I agree extending arch-specific IOCTL to support extending any runtime
MR isn't a good idea.

---

## [33] James Bottomley — 2025-02-19
*Subject: Re: [PATCH 0/4] tsm: Unified Measurement Register ABI for TVMs*

On Tue, 2025-02-18 at 19:21 -0800, Dionna Amalie Glaze wrote:
> On Tue, Feb 18, 2025 at 4:41 PM Dave Hansen <dave.hansen@intel.com>
> wrote:

I still don't get why one of the goals seems to be to artificially
separate AMD Confidential Computing from Intel (and now Arm and RISC-
V).

> There are runtime measurement registers and the CCEL.
> When we have a sysfs interface to extend these registers, it makes

You say "unify behind", but this proposal doesn't include AMD and it
could easily.  All these RTMR systems are simply subsets of a TPM
functionality with non-standard (and different between each of them)
quoting mechanisms.  The only real substantive difference between RTMR
systems and TPM2 is the lack of algorithm agility.  If everyone is
determined to repeat the mistakes of history, TPM2 can easily be
exposed with a pejorative algorithm, so it could fit into this
structure with whatever the chosen hash is and definitely should be so
the interface can really become a universal one applying to both Intel
*and* AMD.

The only real argument against adding a TPM that I've seen is that it
potentially expands the use beyond confidential VMs, which, in an
interface claiming to be universal, I think is actually a good thing. 
There are many non-CC use cases that would really like a non-repudiable
logging system.

Just on algorithm agility, could I make one more plea to add it to the
API before it's set in stone.  You might think sha384 will last
forever, but then that's what the TPM1 makers thought of sha1 and that
design decision hasn't been well supported by history.  The proposal is
here:

https://lore.kernel.org/linux-coco/86e6659bc8dd135491dc34bdb247caf05d8d2ad8.camel@HansenPartnership.com/

Worst case is I'm wrong and you're right and we have an additional
directory in the configfs tree (and you never get to see my tiktok I
told you so dance).  But if I'm right, we've got algorithm agility
(especially if post-quantum has some impact on hashes that hasn't been
foreseen) built in from the get go instead of having to be welded on
after the fact when we run into problems.

All I need at this stage is crypto agility in the configfs ABI.  I can
add vTPM code to that without anyone at Intel having to worry about it.

Regards,

James

---

## [34] Mikko Ylinen — 2025-02-19
*Subject: Re: [PATCH 0/4] tsm: Unified Measurement Register ABI for TVMs*

On Tue, Feb 18, 2025 at 10:04:19PM -0600, Xing, Cedric wrote:
> On 2/18/2025 8:49 AM, Mikko Ylinen wrote:
> > On Thu, Feb 13, 2025 at 03:50:19PM -0600, Xing, Cedric wrote:

Once an alternative is available but it's still in use because of this 
use case (i.e., read registers from a TD report). AFAUI, SEV has its
reports available through configfs-tsm reports so it'd be a good fit here too.

Obviously, if the registers get exposed through this series, the use case
can be covered but full TD report is still good to keep available.

> 
> > The use case on MRCONFIGID mentioned later in this thread does not depend

FWIW, I'm not thinking about IOCTLs here but configfs-tsm reports: a
single read gives you all registers as specified by the report without
having to add anything to the kernel ABI.

---

## [35] Dan Middleton — 2025-02-19
*Subject: Re: [PATCH 0/4] tsm: Unified Measurement Register ABI for TVMs*

On 2/19/25 7:29 AM, James Bottomley wrote:
> On Tue, 2025-02-18 at 19:21 -0800, Dionna Amalie Glaze wrote:
>> On Tue, Feb 18, 2025 at 4:41 PM Dave Hansen <dave.hansen@intel.com>
  > The only real argument against adding a TPM that I've seen is that it
> potentially expands the use beyond confidential VMs, which, in an
> interface claiming to be universal, I think is actually a good thing.

Hi James,
This isn't excluding AMD. AMD just happens not to have a feature common 
to the other architectures.
Intel TDX, Arm CCA, and RISC-V COVE all provide architectural 
measurement registers. SEV happens not to have these today but should 
they in the future, they can draft off of the work here.
Might also be worth remembering the original author of the series 
represented RISC-V COVE.

While someone can emulate a TPM using the architectural measurement 
registers as a backing store, they don't have to. Certainly it's also 
possible to provide a vTPM in a protected region of memory, but that 
shouldn't block the legitimate interests of using the architectural 
features of TDX, CCA, and COVE.

> Just on algorithm agility, could I make one more plea to add it to the
> API before it's set in stone.  You might think sha384 will last

This was helpful feedback. Cedric incorporated it into v3 of the RFC series:

https://lore.kernel.org/linux-coco/20241210-tsm-rtmr-v3-2-5997d4dbda73@intel.com/

We thought your silence on v3 meant you were happy with that feature. 
Lots of threads to track though so also not surprised if you didn't see 
it, or possible we misinterpreted your feedback.

It is retained in this patch set:
https://lore.kernel.org/linux-coco/20250212-tdx-rtmr-v1-2-9795dc49e132@intel.com/


> Worst case is I'm wrong and you're right and we have an additional
> directory in the configfs tree (and you never get to see my tiktok I

Now I have something to look forward to today. :-D

> But if I'm right, we've got algorithm agility
> (especially if post-quantum has some impact on hashes that hasn't been

Thanks,
Dan Middleton

---

## [36] James Bottomley — 2025-02-19
*Subject: Re: [PATCH 0/4] tsm: Unified Measurement Register ABI for TVMs*

On Wed, 2025-02-19 at 09:24 -0600, Dan Middleton wrote:
> 
> 

Calling them "architectural" (implying via hardware) doesn't really
deflect from the fact that for everyone some pieces are going to be
software (or in this case SVSM) provided ... it shouldn't matter where
they're located.

>  SEV happens not to have these today

As I said, the vTPM is fully equivalent to a RTMR system, it's just
implemented in software.

>  but should they in the future, they can draft off of the work here.
> Might also be worth remembering the original author of the series 

What I still don't get is this.  The difference between RTMRs and the
subset of TPM functionality that also provides it is non-existent. 
It's like a distinction without a difference.  If the SVSM authors had
written for a pure RTMR implementation (just usng a CRB API) would that
have made a difference?

> > Just on algorithm agility, could I make one more plea to add it to
> > the API before it's set in stone.  You might think sha384 will last

Heh, OK, you got me there.  After the negative reaction to the above
proposal and nothing changing in v2 I did stop reading the patch sets
...

Regards,

James

---

## [37] Xing, Cedric — 2025-02-19
*Subject: Re: [PATCH 0/4] tsm: Unified Measurement Register ABI for TVMs*

Hi James,

On 2/19/2025 2:53 PM, James Bottomley wrote:
> On Wed, 2025-02-19 at 09:24 -0600, Dan Middleton wrote:
>>
This series does support crypto algo agility per your comments to the 
RFC version this same series. The 2nd patch contains a sample showing 
how to add multiple algorithms (banks) to the same MR.

It isn't limited to CC either. Any kernel module can expose arbitrary 
MRs, real or virtual, through this interface. Again, the sample code in 
the 2nd patch shows how to, and it's quite straight forward.

>> Hi James,
>> This isn't excluding AMD. AMD just happens not to have a feature
As said above, nothing will prevent a vTPM (based on SVSM or anything 
else) driver from exposing any PCRs through the interface defined by 
this series.

>>   SEV happens not to have these today
> 
Agreed. Again, nothing will prevent a vTPM driver from exposing PCRs 
through this interface.

>>   but should they in the future, they can draft off of the work here.
>> Might also be worth remembering the original author of the series
To be precise, RTMRs serve the purpose of RTM (Root of Trust for 
Measurement). The TPM PCRs serve the same purpose. But neither is a 
complete RTM. Per TPM spec, RTM also includes the BIOS boot block (CRTM) 
because the TPM device doesn't have access to processor memory or the 
flash device where BIOS resides. In the case of TVMs, there are static 
MRs that capture the measurements of the initial memory image, which is 
equivalent to the CRTM but measured.

This series models the full RTM (static + runtime MRs), which isn't 
fully covered by the existing TPM framework. But again, nothing will 
prevent the driver of a TPM, real or virtual, from exposing PCRs through 
this series.

>>> Just on algorithm agility, could I make one more plea to add it to
>>> the API before it's set in stone.  You might think sha384 will last
Glad that you see it now!

-Cedric

---

## [38] Dan Williams — 2025-02-19
*Subject: Re: [PATCH 0/4] tsm: Unified Measurement Register ABI for TVMs*

James Bottomley wrote:
[..]
> What I still don't get is this.  The difference between RTMRs and the
> subset of TPM functionality that also provides it is non-existent. 

That is an interesting hypothetical, "would things be different if the
authors, that were forced by SEV-SNP architectural necessity to push
runtime measurement functionality into an SVSM layer exclusively, had
considered that some architectures would include runtime measurement
functionality in the CVM technology directly?". I do not think it helps
because that presupposes that vTPM for these other architectures already
exists.

When I look at the proposed solutions for TDX-vTPM based on service VMs
and other complications brought on by architectural differences between
TDX and SEV-SNP, and compare that to a potential vTPM that wraps RTMR I
see a net reduction in complexity. In other words, a path to a
cross-architecture RTMR-backed vTPM without requiring SVSM and
approximation of the VMPL mechanism. It follows that userspace, not the
kernel, needs to wrap architectural RTMR differences to build that vTPM.

So to me the question is less "RTMR vs TPM" and more about vTPM
implementation choice where RTMR-backed and SVSM-based vTPM solutions
are not mutually exclusive.

For the kernel this mean leaking architecture specific RTMR details into
its ABI and punting the vTPM interface problem to userspace. It also
means that software, in some cases, could forgo vTPM and use raw RTMR.
However, I do not think that ultimately fragments the ecosystem. TPM
momentum and portability concerns limits how far raw RTMR usage will
extend, but in the meantime for use cases that "don't want to have to
depend on the vTPM", like the one Dionna mentioned, are enabled.

If those use case ultimately melt away and transition to vTPM (whether
RTMR backed or SVSM backed), great. If those use cases persist then that
is also a useful system evolution signal from the ecosystem.

---

## [39] Xing, Cedric — 2025-02-19
*Subject: Re: [PATCH 1/4] tsm: Add TVM Measurement Register support*

On 2/17/2025 7:10 PM, Sathyanarayanan Kuppuswamy wrote:
> Hi Cedric,
> 
Will do.

>> is the MR value; while in the latter case `HASH_ALG/digest` under the MR
>> directory contains the MR value, where `HASH_ALG` specifies the hash
This is explicitly requested by James Bottomley. And yes, an MR with >1 
algo is in fact a collection of independent MRs, even though they are 
referred to as the "banks" of the same MR in TCG/TPM spec.

>>
>> Signed-off-by: Cedric Xing <cedric.xing@intel.com>
The names of MRs identify the hardware resources, while the semantics of 
an MR (e.g., whose measurements it contains) is defined by applications. 
A good design should separate those two to allow applications to connect 
them as needed. For example, say all loadable modules must be measured 
before being loaded, and shall be measured/extended to rtmrX on arch A 
and to rtmrY on arch B, respectively. A portable implementation could 
always extend to "rtmrModule", which would be a symlink pointing to 
either rtmrX or rtmrY depending on the underlying arch. On the contrary, 
extending to the same mr[z] is equivalent to forcing z == X == Y, which 
_breaks_ portability as different archs tend to have different number of 
RTMRs.

One more thing worth noting here is: different archs may choose 
different hash algorithms for RTMRs, and that forces applications to be 
arch aware. The solution will be a "log centric" ABI that we don't have yet.

>> +Date:        February 2025
>> +Contact:    Cedric Xing <cedric.xing@intel.com>.
Ok. I'll take it out.

>>   source "drivers/virt/coco/efi_secret/Kconfig"
>> diff --git a/drivers/virt/coco/Makefile b/drivers/virt/coco/Makefile
DIGEST is a bin attribute while _COUNT is the _count_ of bin attributes. 
If w/o the underscore, COUNT would look like another bin attribute.

>> +
>> +    TMR_DIR__ALGO_MAX = 4,
Now I'm thinking of making it a CONFIG option, default to 4.

>> +};
>> +
Thanks! I'll remove it.

>> +    pvd = tmr_mr_to_provider(mr, kobj);
>> +    rc = down_read_interruptible(&pvd->rwsem);
Yes, because in_sync could be set to true between up_read and 
down_write_killable above.

>> +            rc = tmr_call_refresh(pvd, mr);
>> +            pvd->in_sync = !rc;
This attribute shows up only when its parent dir is a hash algo name 
(e.g., "sha384"). So "digest" I believe is more appropriate to refer to 
the result of the hash.

>> +    if (mr->mr_flags & TSM_MR_F_W)
>> +        mrd->battrs[mrd->algo][TMR_DIR_BA_DIGEST].attr.mode |= 
Because a few bytes can be saved this way (by not initializing pvd). The 
difference (in performance) will only be on the error path, which we 
don't care.

>> +
>> +    rc = kobject_set_name(&pvd->kset.kobj, "%s", tmr->name);
I was thinking of HTTP and X.509, all extensions are marked by "x".

Anyone else having a preference on _E vs. _X?

>> + * @TSM_MR_F_W: this MR is writable
>> + * @TSM_MR_F_R: this MR is readable. This should typically be set
R/W is for controlling the file permission of the MR, while X is the 
semantics of the MR. I'll try to clarify.

>> +    TSM_MR_F_R = 4,
>> +    TSM_MR_F_L = 8,

---

## [40] Xing, Cedric — 2025-02-19
*Subject: Re: [PATCH 0/4] tsm: Unified Measurement Register ABI for TVMs*

On 2/19/2025 5:31 AM, Huang, Kai wrote:
> On Tue, 2025-02-18 at 22:04 -0600, Xing, Cedric wrote:
>> On 2/18/2025 8:49 AM, Mikko Ylinen wrote:
Not exactly. Whatever the kernel extracts from a report deemed 
trustworthy by the kernel itself is implicitly trusted by any 
application having the kernel in its TCB. And in fact, every application 
has the kernel in its TCB. Therefore, MRCONFIGID or HOSTDATA read from 
sysfs can be trusted/used directly by any applications.

>>
>> Additionally, this sysfs interface is more friendly to newcomers, as
See my response above.

> And yeah I agree extending arch-specific IOCTL to support extending any runtime
> MR isn't a good idea.

---

## [41] Xing, Cedric — 2025-02-19
*Subject: Re: [PATCH 0/4] tsm: Unified Measurement Register ABI for TVMs*

On 2/19/2025 8:03 AM, Mikko Ylinen wrote:
> On Tue, Feb 18, 2025 at 10:04:19PM -0600, Xing, Cedric wrote:
>> On 2/18/2025 8:49 AM, Mikko Ylinen wrote:
I think every CC arch should have a presence in configfs-tsm for 
generating remotely verifiable reports. This patch series offers 
read/extend functionality to MRs. The overlap here is that any reports 
should include the values of all MRs. However, obtaining a report may 
not be the only way to read MRs. For example, TPM supports commands for 
reading PCRs without attesting to their values. The read functionality 
is definitely a convenience to applications, and helps performance, and 
can also help educating developers. The configfs-tsm report interface 
will work for sure but I don't how it could be as a good fit as this 
sysfs interface.

> Obviously, if the registers get exposed through this series, the use case
> can be covered but full TD report is still good to keep available.
With this series, the full TD report can be requested by writing to 
`reportdata` followed by reading from `report0`.

>>
>>> The use case on MRCONFIGID mentioned later in this thread does not depend
Guess through configfs-tsm you'd have to select the service provider 
first. In contrast, it'd take only a single read from `report0` to get 
the full report through this series. Moreover, it is table driven, so 
these `report0`/`reportdata` attributes add ZERO code and take only 2 
table entries (<100 bytes) to implement on TDX. I'm not sure if adding a 
local report provider to configfs-tsm can be any simpler.

---

## [42] Dan Williams — 2025-05-01
*Subject: Re: [PATCH 0/4] tsm: Unified Measurement Register ABI for TVMs*

Dionna Amalie Glaze wrote:
> On Tue, Feb 18, 2025 at 8:57 AM Dave Hansen <dave.hansen@intel.com> wrote:
> >

Safe to assume I can carry this ack forward to the latest iteration [1]?
This is as I look get this into linux-next shortly.

[1]: http://lore.kernel.org/20250424-tdx-rtmr-v5-0-4fe28ddf85d4@intel.com

---
