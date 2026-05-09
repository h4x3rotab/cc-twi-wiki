---
title: 'tsm: Unified Measurement Register ABI for TVMs'
date: 2024-12-10
last_reply: 2024-12-10
message_count: 3
participants: ['Cedric Xing']
---

## [1] Cedric Xing — 2024-12-10

NOTE: This patch series introduces the Measurement Register (MR) ABI, and
is largely a continuation of Samuel Ortiz’s previous work on the RTMR ABI
[1].

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
and implement MRs in a CC guest driver.

MRs are made accessible to applications through a directory tree (rooted at
`/sys/kernel/tsm`). An MR could be presented as either a file containing
its value, or a directory containing the file `digest` under a subdirectory
of the same name as the hash algorithm. By default, an MR will be presented
as a directory unless `TSM_MR_F_F` is set in `mr_flags`.

[1]: https://patchwork.kernel.org/project/linux-integrity/cover/20240128212532.2754325-1-sameo@rivosinc.com/

Signed-off-by: Cedric Xing <cedric.xing@intel.com>
---
Changes in v3:
- Added *Crypto Agility* support, see patch 1
- Fixed style issues in both commit messages and code
- Fixed incorrect assignment of files to commits
- Link to v2: https://lore.kernel.org/r/20241031-tsm-rtmr-v2-0-1a6762795911@intel.com

Changes in v2:
- Separated TSM MR code in a new file: `tsm-mr.c`.
- Removed RTMR event logging due to the lack of agreement on the log
  format.
- Default presentation of each MR as a directory, with the option to
  request an
  MR as a file using `TSM_MR_F_F`.
- Reduced verbosity: Renamed `struct tsm_measurement_provider` to `struct
  tsm_measurement`, and `tsm_(un)register_measurement_provider` to
  `tsm_(un)register_measurement`.
- Added `MODULE_DESCRIPTION` for measurement-sample.
- Fixed several compiler warnings on 32-bit builds.
- Link to v1: https://lore.kernel.org/r/20240907-tsm-rtmr-v1-0-12fc4d43d4e7@intel.com

---
Cedric Xing (2):
      tsm: Add TVM Measurement Register Support
      tsm: Add TVM Measurement Sample Code

 MAINTAINERS                             |   3 +-
 drivers/virt/coco/Kconfig               |   3 +-
 drivers/virt/coco/Makefile              |   2 +
 drivers/virt/coco/{tsm.c => tsm-core.c} |   6 +-
 drivers/virt/coco/tsm-mr.c              | 376 ++++++++++++++++++++++++++++++++
 include/linux/tsm.h                     |  64 ++++++
 samples/Kconfig                         |   4 +
 samples/Makefile                        |   1 +
 samples/tsm/Makefile                    |   2 +
 samples/tsm/measurement-example.c       | 113 ++++++++++
 10 files changed, 571 insertions(+), 3 deletions(-)
---
base-commit: fac04efc5c793dccbd07e2d59af9f90b7fc0dca4
change-id: 20240904-tsm-rtmr-7a45859d2a96

Best regards,

---

## [2] Cedric Xing — 2024-12-10
*Subject: [PATCH RFC v3 1/2] tsm: Add TVM Measurement Register Support*

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
 MAINTAINERS                             |   2 +-
 drivers/virt/coco/Kconfig               |   3 +-
 drivers/virt/coco/Makefile              |   2 +
 drivers/virt/coco/{tsm.c => tsm-core.c} |   6 +-
 drivers/virt/coco/tsm-mr.c              | 376 ++++++++++++++++++++++++++++++++
 include/linux/tsm.h                     |  64 ++++++
 6 files changed, 450 insertions(+), 3 deletions(-)

diff --git a/MAINTAINERS b/MAINTAINERS
index 17daa9ee9384..4c833fa9e388 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -23846,7 +23846,7 @@ M:	Dan Williams <dan.j.williams@intel.com>
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
index 000000000000..499d2aa1e6c7
--- /dev/null
+++ b/drivers/virt/coco/tsm-mr.c
@@ -0,0 +1,376 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/* Copyright(c) 2024 Intel Corporation. All rights reserved. */
+
+#define pr_fmt(fmt) KBUILD_MODNAME ": " fmt
+
+#include <crypto/hash.h>
+#include <crypto/hash_info.h>
+#include <linux/ctype.h>
+#include <linux/shmem_fs.h>
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
+		pr_warn("%s.extend(%s) failed %d\n", kobject_name(&pvd->kset.kobj), mr->mr_name,
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
+	else
+		pr_debug("%s.refresh(%s)=%d\n", kobject_name(&pvd->kset.kobj), mr->mr_name, rc);
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
+	pr_debug("%s(%s)\n", __func__, kobject_name(kobj));
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
+	pr_debug("%s(%s)\n", __func__, kobject_name(kobj));
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
+	// set pvd to NULL or it will be freed due to __free(kfree)
+	pvd = NULL;
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

## [3] Cedric Xing — 2024-12-10
*Subject: [PATCH RFC v3 2/2] tsm: Add TVM Measurement Sample Code*

This sample kernel module demonstrates how to make MRs accessible to user
mode through TSM.

Once loaded, this module registers a virtual measurement provider with the
TSM core and will result in the directory tree below.

/sys/kernel/tsm
└── measurement-example
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

More details can be found in `samples/tsm/measurement-example.c`.

Signed-off-by: Cedric Xing <cedric.xing@intel.com>
---
 MAINTAINERS                       |   1 +
 samples/Kconfig                   |   4 ++
 samples/Makefile                  |   1 +
 samples/tsm/Makefile              |   2 +
 samples/tsm/measurement-example.c | 113 ++++++++++++++++++++++++++++++++++++++
 5 files changed, 121 insertions(+)

diff --git a/MAINTAINERS b/MAINTAINERS
index 4c833fa9e388..a4074cea0f16 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -23848,6 +23848,7 @@ S:	Maintained
 F:	Documentation/ABI/testing/configfs-tsm
 F:	drivers/virt/coco/tsm*.c
 F:	include/linux/tsm.h
+F:	samples/tsm/*
 
 TRUSTED SERVICES TEE DRIVER
 M:	Balint Dobszay <balint.dobszay@arm.com>
diff --git a/samples/Kconfig b/samples/Kconfig
index b288d9991d27..8159d3ca6487 100644
--- a/samples/Kconfig
+++ b/samples/Kconfig
@@ -184,6 +184,10 @@ config SAMPLE_TIMER
 	bool "Timer sample"
 	depends on CC_CAN_LINK && HEADERS_INSTALL
 
+config SAMPLE_TSM
+	tristate "TSM measurement sample"
+	depends on TSM_REPORTS
+
 config SAMPLE_UHID
 	bool "UHID sample"
 	depends on CC_CAN_LINK && HEADERS_INSTALL
diff --git a/samples/Makefile b/samples/Makefile
index b85fa64390c5..891f5c12cd39 100644
--- a/samples/Makefile
+++ b/samples/Makefile
@@ -39,3 +39,4 @@ obj-$(CONFIG_SAMPLE_KMEMLEAK)		+= kmemleak/
 obj-$(CONFIG_SAMPLE_CORESIGHT_SYSCFG)	+= coresight/
 obj-$(CONFIG_SAMPLE_FPROBE)		+= fprobe/
 obj-$(CONFIG_SAMPLES_RUST)		+= rust/
+obj-$(CONFIG_SAMPLE_TSM)		+= tsm/
diff --git a/samples/tsm/Makefile b/samples/tsm/Makefile
new file mode 100644
index 000000000000..3969a59221e9
--- /dev/null
+++ b/samples/tsm/Makefile
@@ -0,0 +1,2 @@
+# SPDX-License-Identifier: GPL-2.0-only
+obj-$(CONFIG_SAMPLE_TSM) += measurement-example.o
diff --git a/samples/tsm/measurement-example.c b/samples/tsm/measurement-example.c
new file mode 100644
index 000000000000..c5d6f44211dc
--- /dev/null
+++ b/samples/tsm/measurement-example.c
@@ -0,0 +1,113 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/* Copyright(c) 2024 Intel Corporation. All rights reserved. */
+
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
+} example_report = {
+	.static_mr = "static_mr",
+	.config_mr = "config_mr",
+	.rtmr0 = "rtmr0",
+	.rtmr1 = "rtmr1",
+	.user_data = "user_data",
+};
+
+DEFINE_FREE(shash, struct crypto_shash *, if (!IS_ERR(_T)) crypto_free_shash(_T));
+
+static int example_report_refresh(struct tsm_measurement *tmr,
+				  const struct tsm_measurement_register *mr)
+{
+	pr_debug("%s(%s,%s)\n", __func__, tmr->name, mr->mr_name);
+	struct crypto_shash *tfm __free(shash) =
+		crypto_alloc_shash(hash_algo_name[HASH_ALGO_SHA512], 0, 0);
+	if (IS_ERR(tfm))
+		return PTR_ERR(tfm);
+	return crypto_shash_tfm_digest(tfm, (u8 *)&example_report,
+				       offsetof(typeof(example_report), report_digest),
+				       example_report.report_digest);
+}
+
+static int example_report_extend_mr(struct tsm_measurement *tmr,
+				    const struct tsm_measurement_register *mr, const u8 *data)
+{
+	SHASH_DESC_ON_STACK(desc, 0);
+	int rc;
+
+	pr_debug("%s(%s,%s)\n", __func__, tmr->name, mr->mr_name);
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
+#define MR_(mr, hash) .mr_value = &example_report.mr, TSM_MR_(mr, hash)
+static const struct tsm_measurement_register example_mrs[] = {
+	/* static MR, read-only */
+	{ MR_(static_mr, SHA384) },
+	/* config MR, read-only */
+	{ MR_(config_mr, SHA512) },
+	/* RTMR, direct extension prohibited */
+	{ MR_(rtmr0, SHA256) | TSM_MR_F_RTMR },
+	/* RTMR, direct extension allowed */
+	{ MR_(rtmr1, SHA384) | TSM_MR_F_RTMR | TSM_MR_F_W },
+	/* RTMR, crypto agile, alaised to rtmr0 and rtmr1, respectively */
+	{ .mr_value = &example_report.rtmr0,
+	  TSM_MR_(rtmr_crypto_agile, SHA256) | TSM_MR_F_RTMR | TSM_MR_F_W },
+	{ .mr_value = &example_report.rtmr1,
+	  TSM_MR_(rtmr_crypto_agile, SHA384) | TSM_MR_F_RTMR | TSM_MR_F_W },
+	/* most CC archs allow including user data in attestation */
+	{ MR_(report_digest, SHA512) | TSM_MR_F_L },
+	/* terminating NULL entry */
+	{}
+};
+#undef MR_
+
+static struct tsm_measurement example_measurement_provider = {
+	.name = "measurement-example",
+	.mrs = example_mrs,
+	.refresh = example_report_refresh,
+	.extend = example_report_extend_mr,
+};
+
+static int __init measurement_example_init(void)
+{
+	int rc;
+
+	rc = tsm_register_measurement(&example_measurement_provider);
+	pr_debug("tsm_register_measurement(%p)=%d\n", &example_measurement_provider, rc);
+	return rc;
+}
+
+static void __exit measurement_example_exit(void)
+{
+	int rc;
+
+	rc = tsm_unregister_measurement(&example_measurement_provider);
+	pr_debug("tsm_unregister_measurement(%p)=%d\n", &example_measurement_provider, rc);
+}
+
+module_init(measurement_example_init);
+module_exit(measurement_example_exit);
+
+MODULE_LICENSE("GPL");
+MODULE_DESCRIPTION("Sample tsm_measurement implementation");

---
