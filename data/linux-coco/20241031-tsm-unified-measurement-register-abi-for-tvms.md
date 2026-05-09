---
title: 'tsm: Unified Measurement Register ABI for TVMs'
date: 2024-10-31
last_reply: 2024-11-12
message_count: 11
participants: ['Cedric Xing', 'Alexey Kardashevskiy', 'James Bottomley', 'Mikko Ylinen']
---

## [1] Cedric Xing — 2024-10-31

NOTE: This patch series introduces the Measurement Register (MR) ABI, and is
largely a continuation of Samuel Ortiz’s previous work on the RTMR ABI [1].

This patch series adds a unified interface to TSM core for confidential
computing (CC) guest drivers to provide access to measurement registers (MRs),
which are essential for relying parties (RPs) to verify the integrity of the
computing environment. The interface is structured around
`struct tsm_measurement`, which holds an array of
`struct tsm_measurement_register` and includes operations for reading and
updating MRs.

The MRs come in two varieties: static and runtime. Static MRs are determined at
the TEE VM (TVM) build time and capture the initial memory image or the
configuration/policy specified by the TVM's owner. In contrast, Runtime MRs
(RTMRs) start with known values, such as all zeros, at TVM build time and are
extended with measurements of loaded code, data, configuration, or executed
actions by the TVM guest during runtime.

Each `struct tsm_measurement_register` features a `mr_flags` member that
indicates the MR's properties. Static MRs are typically marked as read-only
with only the `TSM_MR_F_R` flag set, while RTMRs are marked as extensible with
the `TSM_MR_F_X` flag. Patch 2 adds a sample module to demonstrate how to
define and implement MRs.

MRs are made accessible to applications through a directory tree (rooted at
/sys/kernel/tsm). An MR could be presented as either a file containing its
value, or a directory containing elements like `digest` and `hash_algo`. By
default, an MR will be presented as a directory unless `TSM_MR_F_F` is set in
`mr_flags`.

[1]: https://patchwork.kernel.org/project/linux-integrity/cover/20240128212532.2754325-1-sameo@rivosinc.com/

Signed-off-by: Cedric Xing <cedric.xing@intel.com>
---
Changes in v2:
- Separated TSM MR code in a new file: `tsm-mr.c`.
- Removed RTMR event logging due to the lack of agreement on the log format.
- Default presentation of each MR as a directory, with the option to request an
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

 drivers/virt/coco/Kconfig               |   3 +-
 drivers/virt/coco/Makefile              |   2 +
 drivers/virt/coco/{tsm.c => tsm-core.c} |  26 ++-
 drivers/virt/coco/tsm-mr.c              | 374 ++++++++++++++++++++++++++++++++
 include/linux/tsm.h                     |  63 ++++++
 samples/Kconfig                         |   4 +
 samples/Makefile                        |   1 +
 samples/tsm/Makefile                    |   2 +
 samples/tsm/measurement-example.c       | 117 ++++++++++
 9 files changed, 581 insertions(+), 11 deletions(-)
---
base-commit: 81983758430957d9a5cb3333fe324fd70cf63e7e
change-id: 20240904-tsm-rtmr-7a45859d2a96

Best regards,

---

## [2] Cedric Xing — 2024-10-31
*Subject: [PATCH RFC v2 1/2] tsm: Add TVM Measurement Register Support*

This commit extends the TSM core with support for CC measurement registers
(MRs).

The newly added APIs are:

- `tsm_register_measurement(struct tsm_measurement *)`
  This function allows a CC guest driver to register a set of measurement
  registers with the TSM core.
- `tsm_unregister_measurement(struct tsm_measurement *)`:
  This function enables a CC guest driver to unregister a previously registered
  set of measurement registers.

`struct tsm_measurement` has been defined to encapsulate the details of
CC-specific MRs. It includes an array of `struct tsm_measurement_register`s and
provides operations for reading and updating these registers. For a
comprehensive understanding of the structure and its usage, refer to the
detailed comments added in `include/linux/tsm.h`.

Upon successful registration of a measurement provider, the TSM core exposes
the MRs through a directory tree in the sysfs filesystem. The root of this tree
is located at `/sys/kernel/tsm/<MR provider>/`, with `<MR provider>` being the
name of the measurement provider. Each MR is made accessible as either a
file or a directory, named after the MR itself. In the former case, the file
content is the MR value, while in the latter case there will be two files in
the directory: `digest` and `hash_algo`. The purpose and content of these files
are self-explanatory.

Signed-off-by: Cedric Xing <cedric.xing@intel.com>
---
 drivers/virt/coco/Kconfig               |   3 +-
 drivers/virt/coco/Makefile              |   2 +
 drivers/virt/coco/{tsm.c => tsm-core.c} |  26 ++-
 drivers/virt/coco/tsm-mr.c              | 374 ++++++++++++++++++++++++++++++++
 4 files changed, 394 insertions(+), 11 deletions(-)

diff --git a/drivers/virt/coco/Kconfig b/drivers/virt/coco/Kconfig
index d9ff676bf48d..0609622cbcb9 100644
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
index b69c30c1c720..8192d78dff61 100644
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
similarity index 95%
rename from drivers/virt/coco/tsm.c
rename to drivers/virt/coco/tsm-core.c
index 9432d4e303f1..92e961f21507 100644
--- a/drivers/virt/coco/tsm.c
+++ b/drivers/virt/coco/tsm-core.c
@@ -1,8 +1,6 @@
 // SPDX-License-Identifier: GPL-2.0-only
 /* Copyright(c) 2023 Intel Corporation. All rights reserved. */
 
-#define pr_fmt(fmt) KBUILD_MODNAME ": " fmt
-
 #include <linux/tsm.h>
 #include <linux/err.h>
 #include <linux/slab.h>
@@ -166,8 +164,9 @@ static ssize_t tsm_report_service_guid_store(struct config_item *cfg,
 }
 CONFIGFS_ATTR_WO(tsm_report_, service_guid);
 
-static ssize_t tsm_report_service_manifest_version_store(struct config_item *cfg,
-							 const char *buf, size_t len)
+static ssize_t
+tsm_report_service_manifest_version_store(struct config_item *cfg,
+					  const char *buf, size_t len)
 {
 	struct tsm_report *report = to_tsm_report(cfg);
 	unsigned int val;
@@ -187,8 +186,8 @@ static ssize_t tsm_report_service_manifest_version_store(struct config_item *cfg
 }
 CONFIGFS_ATTR_WO(tsm_report_, service_manifest_version);
 
-static ssize_t tsm_report_inblob_write(struct config_item *cfg,
-				       const void *buf, size_t count)
+static ssize_t tsm_report_inblob_write(struct config_item *cfg, const void *buf,
+				       size_t count)
 {
 	struct tsm_report *report = to_tsm_report(cfg);
 	int rc;
@@ -341,7 +340,8 @@ static struct configfs_attribute *tsm_report_attrs[] = {
 	[TSM_REPORT_PRIVLEVEL_FLOOR] = &tsm_report_attr_privlevel_floor,
 	[TSM_REPORT_SERVICE_PROVIDER] = &tsm_report_attr_service_provider,
 	[TSM_REPORT_SERVICE_GUID] = &tsm_report_attr_service_guid,
-	[TSM_REPORT_SERVICE_MANIFEST_VER] = &tsm_report_attr_service_manifest_version,
+	[TSM_REPORT_SERVICE_MANIFEST_VER] =
+		&tsm_report_attr_service_manifest_version,
 	NULL,
 };
 
@@ -383,7 +383,8 @@ static bool tsm_report_is_visible(struct config_item *item,
 }
 
 static bool tsm_report_is_bin_visible(struct config_item *item,
-				      struct configfs_bin_attribute *attr, int n)
+				      struct configfs_bin_attribute *attr,
+				      int n)
 {
 	guard(rwsem_read)(&tsm_rwsem);
 	if (!provider.ops)
@@ -478,6 +479,9 @@ EXPORT_SYMBOL_GPL(tsm_unregister);
 
 static struct config_group *tsm_report_group;
 
+extern int tsm_mr_init(void);
+extern void tsm_mr_exit(void);
+
 static int __init tsm_init(void)
 {
 	struct config_group *root = &tsm_configfs.su_group;
@@ -497,16 +501,18 @@ static int __init tsm_init(void)
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
 module_exit(tsm_exit);
 
 MODULE_LICENSE("GPL");
-MODULE_DESCRIPTION("Provide Trusted Security Module attestation reports via configfs");
+MODULE_DESCRIPTION(
+	"Provide Trusted Security Module attestation reports via configfs");
diff --git a/drivers/virt/coco/tsm-mr.c b/drivers/virt/coco/tsm-mr.c
new file mode 100644
index 000000000000..a84e923a7782
--- /dev/null
+++ b/drivers/virt/coco/tsm-mr.c
@@ -0,0 +1,374 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/* Copyright(c) 2024 Intel Corporation. All rights reserved. */
+
+#include <linux/tsm.h>
+#include <linux/shmem_fs.h>
+#include <linux/ctype.h>
+#include <crypto/hash_info.h>
+#include <crypto/hash.h>
+
+int tsm_mr_init(void);
+void tsm_mr_exit(void);
+
+enum _mrdir_bin_attr_index {
+	_MRDIR_BA_DIGEST,
+	_MRDIR_BA__COUNT,
+};
+
+struct _mrdir {
+	struct kobject kobj;
+	struct bin_attribute battrs[_MRDIR_BA__COUNT];
+};
+
+struct _mr_provider {
+	struct kset kset;
+	struct rw_semaphore rwsem;
+	struct bin_attribute *mrfiles;
+	struct tsm_measurement *tmr;
+	bool in_sync;
+};
+
+static inline const struct tsm_measurement_register *
+_mrdir_mr(const struct _mrdir *mrd)
+{
+	return (struct tsm_measurement_register *)mrd->battrs[_MRDIR_BA_DIGEST]
+		.private;
+}
+
+static inline struct _mr_provider *
+_mr_to_provider(const struct tsm_measurement_register *mr, struct kobject *kobj)
+{
+	if (mr->mr_flags & TSM_MR_F_F)
+		return container_of(kobj, struct _mr_provider, kset.kobj);
+	else
+		return container_of(kobj->kset, struct _mr_provider, kset);
+}
+
+static inline int _call_refresh(struct _mr_provider *pvd,
+				const struct tsm_measurement_register *mr)
+{
+	int rc = pvd->tmr->refresh(pvd->tmr, mr);
+	if (rc)
+		pr_warn(KBUILD_MODNAME ": %s.extend(%s) failed %d\n",
+			kobject_name(&pvd->kset.kobj), mr->mr_name, rc);
+	return rc;
+}
+
+static inline int _call_extend(struct _mr_provider *pvd,
+			       const struct tsm_measurement_register *mr,
+			       const u8 *data)
+{
+	int rc = pvd->tmr->extend(pvd->tmr, mr, data);
+	if (rc)
+		pr_warn(KBUILD_MODNAME ": %s.extend(%s) failed %d\n",
+			kobject_name(&pvd->kset.kobj), mr->mr_name, rc);
+	return rc;
+}
+
+static ssize_t hash_algo_show(struct kobject *kobj, struct kobj_attribute *attr,
+			      char *page)
+{
+	struct _mrdir *mrd;
+	mrd = container_of(kobj, typeof(*mrd), kobj);
+	return sysfs_emit(page, "%s", hash_algo_name[_mrdir_mr(mrd)->mr_hash]);
+}
+
+static ssize_t _mr_read(struct file *filp, struct kobject *kobj,
+			struct bin_attribute *attr, char *page, loff_t off,
+			size_t count)
+{
+	const struct tsm_measurement_register *mr;
+	struct _mr_provider *pvd;
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
+	BUG_ON(mr->mr_size != attr->size);
+
+	pvd = _mr_to_provider(mr, kobj);
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
+			rc = _call_refresh(pvd, mr);
+			pvd->in_sync = !rc;
+		}
+
+		downgrade_write(&pvd->rwsem);
+	}
+
+	if (!rc)
+		memcpy(page, mr->mr_value + off, count);
+	else
+		pr_debug(KBUILD_MODNAME ": %s.refresh(%s)=%d\n",
+			 kobject_name(&pvd->kset.kobj), mr->mr_name, rc);
+
+	up_read(&pvd->rwsem);
+	return rc ?: count;
+}
+
+static ssize_t _mr_write(struct file *filp, struct kobject *kobj,
+			 struct bin_attribute *attr, char *page, loff_t off,
+			 size_t count)
+{
+	const struct tsm_measurement_register *mr;
+	struct _mr_provider *pvd;
+	ssize_t rc;
+
+	if (off != 0 || count != attr->size)
+		return -EINVAL;
+
+	mr = (typeof(mr))attr->private;
+	BUG_ON(mr->mr_size != attr->size);
+
+	pvd = _mr_to_provider(mr, kobj);
+	rc = down_write_killable(&pvd->rwsem);
+	if (rc)
+		return rc;
+
+	if (mr->mr_flags & TSM_MR_F_X)
+		rc = _call_extend(pvd, mr, page);
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
+static void _mrdir_release(struct kobject *kobj)
+{
+	struct _mrdir *mrd;
+	mrd = container_of(kobj, typeof(*mrd), kobj);
+	pr_debug("%s(%s)\n", __func__, kobject_name(kobj));
+	kfree(mrd);
+}
+
+static struct kobj_type _mrdir_ktype = {
+	.release = _mrdir_release,
+	.sysfs_ops = &kobj_sysfs_ops,
+};
+
+static struct _mrdir *_mrdir_create(const struct tsm_measurement_register *mr,
+				    struct _mr_provider *pvd)
+{
+	struct _mrdir *mrd __free(kfree);
+	int rc;
+
+	BUG_ON(mr->mr_flags & TSM_MR_F_F);
+	mrd = kzalloc(sizeof(*mrd), GFP_KERNEL);
+	if (!mrd)
+		return ERR_PTR(-ENOMEM);
+
+	sysfs_bin_attr_init(&mrd->battrs[_MRDIR_BA_DIGEST]);
+	mrd->battrs[_MRDIR_BA_DIGEST].attr.name = "digest";
+	if (mr->mr_flags & TSM_MR_F_W)
+		mrd->battrs[_MRDIR_BA_DIGEST].attr.mode |= S_IWUSR | S_IWGRP;
+	if (mr->mr_flags & TSM_MR_F_R)
+		mrd->battrs[_MRDIR_BA_DIGEST].attr.mode |= S_IRUGO;
+
+	mrd->battrs[_MRDIR_BA_DIGEST].size = mr->mr_size;
+	mrd->battrs[_MRDIR_BA_DIGEST].read = _mr_read;
+	mrd->battrs[_MRDIR_BA_DIGEST].write = _mr_write;
+	mrd->battrs[_MRDIR_BA_DIGEST].private = (void *)mr;
+
+	mrd->kobj.kset = &pvd->kset;
+	rc = kobject_init_and_add(&mrd->kobj, &_mrdir_ktype, NULL, "%s",
+				  mr->mr_name);
+	if (rc)
+		return ERR_PTR(rc);
+
+	return_ptr(mrd);
+}
+
+static void _mr_provider_release(struct kobject *kobj)
+{
+	struct _mr_provider *pvd;
+	pvd = container_of(kobj, typeof(*pvd), kset.kobj);
+	pr_debug("%s(%s)\n", __func__, kobject_name(kobj));
+	BUG_ON(!list_empty(&pvd->kset.list));
+	kfree(pvd->mrfiles);
+	kfree(pvd);
+}
+
+static struct kobj_type _mr_provider_ktype = {
+	.release = _mr_provider_release,
+	.sysfs_ops = &kobj_sysfs_ops,
+};
+
+static struct kset *_sysfs_tsm;
+
+static struct _mr_provider *_mr_provider_create(struct tsm_measurement *tmr)
+{
+	struct _mr_provider *pvd __free(kfree);
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
+	pvd->kset.kobj.kset = _sysfs_tsm;
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
+DEFINE_FREE(_unregister_measurement, struct _mr_provider *,
+	    if (!IS_ERR_OR_NULL(_T)) tsm_unregister_measurement(_T->tmr));
+
+int tsm_register_measurement(struct tsm_measurement *tmr)
+{
+	static struct kobj_attribute _attr_hash = __ATTR_RO(hash_algo);
+
+	struct _mr_provider *pvd __free(_unregister_measurement);
+	int rc, nr;
+
+	pvd = _mr_provider_create(tmr);
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
+		struct _mrdir *mrd = _mrdir_create(&tmr->mrs[i], pvd);
+		if (IS_ERR(mrd))
+			return PTR_ERR(mrd);
+
+		struct attribute *attrs[] = {
+			&_attr_hash.attr,
+			NULL,
+		};
+		struct bin_attribute *battrs[_MRDIR_BA__COUNT + 1] = {};
+		for (int j = 0; j < _MRDIR_BA__COUNT; ++j)
+			battrs[j] = &mrd->battrs[j];
+		struct attribute_group agrp = {
+			.attrs = attrs,
+			.bin_attrs = battrs,
+		};
+		rc = sysfs_create_group(&mrd->kobj, &agrp);
+		if (rc)
+			return rc;
+	}
+
+	if (nr > 0) {
+		struct bin_attribute *mrfiles __free(kfree);
+		struct bin_attribute **battrs __free(kfree);
+
+		mrfiles = kcalloc(sizeof(*mrfiles), nr, GFP_KERNEL);
+		battrs = kcalloc(sizeof(*battrs), nr + 1, GFP_KERNEL);
+		if (!battrs || !mrfiles)
+			return -ENOMEM;
+
+		for (int i = 0, j = 0; tmr->mrs[i].mr_name; ++i) {
+			if (!(tmr->mrs[i].mr_flags & TSM_MR_F_F))
+				continue;
+
+			mrfiles[j].attr.name = tmr->mrs[i].mr_name;
+			mrfiles[j].read = _mr_read;
+			mrfiles[j].write = _mr_write;
+			mrfiles[j].size = tmr->mrs[i].mr_size;
+			mrfiles[j].private = (void *)&tmr->mrs[i];
+			if (tmr->mrs[i].mr_flags & TSM_MR_F_R)
+				mrfiles[j].attr.mode |= S_IRUGO;
+			if (tmr->mrs[i].mr_flags & TSM_MR_F_W)
+				mrfiles[j].attr.mode |= S_IWUSR | S_IWGRP;
+
+			battrs[j] = &mrfiles[j];
+			++j;
+
+			BUG_ON(j > nr);
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
+	pvd = NULL;
+	return 0;
+}
+EXPORT_SYMBOL_GPL(tsm_register_measurement);
+
+static void _kset_put_children(struct kset *kset)
+{
+	struct kobject *p, *n;
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
+	struct kobject *kobj = kset_find_obj(_sysfs_tsm, tmr->name);
+	if (!kobj)
+		return -ENOENT;
+
+	struct _mr_provider *pvd = container_of(kobj, typeof(*pvd), kset.kobj);
+	BUG_ON(pvd->tmr != tmr);
+
+	_kset_put_children(&pvd->kset);
+	kset_unregister(&pvd->kset);
+	kobject_put(kobj);
+	return 0;
+}
+EXPORT_SYMBOL_GPL(tsm_unregister_measurement);
+
+int tsm_mr_init(void)
+{
+	_sysfs_tsm = kset_create_and_add("tsm", NULL, kernel_kobj);
+	if (!_sysfs_tsm)
+		return -ENOMEM;
+	return 0;
+}
+
+void tsm_mr_exit(void)
+{
+	kset_unregister(_sysfs_tsm);
+}
+
+MODULE_LICENSE("GPL");
+MODULE_DESCRIPTION("Provide Trusted Security Module measurements via sysfs");

---

## [3] Cedric Xing — 2024-10-31
*Subject: [PATCH RFC v2 2/2] tsm: Add TVM Measurement Sample Code*

This sample kernel module demonstrates how to make MRs accessible to user mode
through TSM.

Once loaded, this module registers a virtual measurement provider with the TSM
core and will result in the directory tree below.

/sys/kernel/tsm/
└── measurement-example
    ├── config_mr
    │   ├── digest
    │   └── hash_algo
    ├── full_report
    ├── report_digest
    │   ├── digest
    │   └── hash_algo
    ├── rtmr0
    │   ├── digest
    │   └── hash_algo
    ├── rtmr1
    │   ├── digest
    │   └── hash_algo
    ├── static_mr
    │   ├── digest
    │   └── hash_algo
    └── user_data
        ├── digest
        └── hash_algo

Among the MRs in this example:

- `static_mr` and `config_mr` are static MRs.
- `full_report` illustrates that a complete architecture-dependent attestation
  report structure (for instance, the `TDREPORT` structure in Intel TDX) can be
  presented as an MR. It also demonstrates exposing measurements in a file.
- `rtmr0` is an RTMR with `TSM_MR_F_W` **cleared**, preventing direct
  extensions; as a result, `rtmr0/digest` is read-only.
- `rtmr1` is an RTMR with `TSM_MR_F_W` **set**, permitting direct extensions;
  thus, `rtmr1/digest` is writable.
- `user_data` represents the data provided by the software to be incorporated
  into the attestation report. Writing to this MR and then reading from
  `full_report` effectively triggers a request for an attestation report from
  the underlying CC hardware.
- `report_digest` serves as an example MR to demonstrate the use of the
  `TSM_MR_F_L` flag.

See comments in `samples/tsm/measurement-example.c` for more details.

Signed-off-by: Cedric Xing <cedric.xing@intel.com>
---
 include/linux/tsm.h               |  63 ++++++++++++++++++++
 samples/Kconfig                   |   4 ++
 samples/Makefile                  |   1 +
 samples/tsm/Makefile              |   2 +
 samples/tsm/measurement-example.c | 117 ++++++++++++++++++++++++++++++++++++++
 5 files changed, 187 insertions(+)

diff --git a/include/linux/tsm.h b/include/linux/tsm.h
index 11b0c525be30..291259fc85fc 100644
--- a/include/linux/tsm.h
+++ b/include/linux/tsm.h
@@ -5,6 +5,7 @@
 #include <linux/sizes.h>
 #include <linux/types.h>
 #include <linux/uuid.h>
+#include <uapi/linux/hash_info.h>
 
 #define TSM_INBLOB_MAX 64
 #define TSM_OUTBLOB_MAX SZ_32K
@@ -109,4 +110,66 @@ struct tsm_ops {
 
 int tsm_register(const struct tsm_ops *ops, void *priv);
 int tsm_unregister(const struct tsm_ops *ops);
+
+/**
+ * struct tsm_measurement_register - describes an architectural measurement
+ *                                   register (MR)
+ * @mr_name: name of the MR
+ * @mr_value: buffer containing the current value of the MR
+ * @mr_size: size of the MR - typically the digest size of @mr_hash
+ * @mr_flags: bitwise OR of flags defined in enum tsm_measurement_register_flag
+ * @mr_hash: optional hash identifier defined in include/uapi/linux/hash_info.h
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
+#define TSM_MR_(mr, hash)                              \
+	.mr_name = #mr, .mr_size = hash##_DIGEST_SIZE, \
+	.mr_hash = HASH_ALGO_##hash, .mr_flags = TSM_MR_F_R
+
+/**
+ * struct tsm_measurement - define CC specific MRs and methods for updating
+ *                          them
+ * @name: name of the measurement provider
+ * @mrs: array of MR definitions ending with mr_name set to %NULL
+ * @refresh: invoked to update the specified MR
+ * @extend: invoked to extend the specified MR with mr_size bytes
+ */
+struct tsm_measurement {
+	const char *name;
+	const struct tsm_measurement_register *mrs;
+	int (*refresh)(struct tsm_measurement *,
+		       const struct tsm_measurement_register *);
+	int (*extend)(struct tsm_measurement *,
+		      const struct tsm_measurement_register *, const u8 *);
+};
+
+int tsm_register_measurement(struct tsm_measurement *);
+int tsm_unregister_measurement(struct tsm_measurement *);
+
 #endif /* __TSM_H */
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
index 000000000000..3abd67d3e569
--- /dev/null
+++ b/samples/tsm/measurement-example.c
@@ -0,0 +1,117 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/* Copyright(c) 2024 Intel Corporation. All rights reserved. */
+
+#include <linux/module.h>
+#include <linux/tsm.h>
+#include <crypto/hash_info.h>
+#include <crypto/hash.h>
+
+struct __aligned(16)
+{
+	u8 static_mr[SHA384_DIGEST_SIZE];
+	u8 config_mr[SHA512_DIGEST_SIZE];
+	u8 rtmr0[SHA256_DIGEST_SIZE];
+	u8 rtmr1[SHA384_DIGEST_SIZE];
+	u8 user_data[SHA512_DIGEST_SIZE];
+	u8 report_digest[SHA512_DIGEST_SIZE];
+}
+example_report = {
+	.static_mr = "static_mr",
+	.config_mr = "config_mr",
+	.rtmr0 = "rtmr0",
+	.rtmr1 = "rtmr1",
+	.user_data = "user_data",
+};
+
+DEFINE_FREE(shash, struct crypto_shash *,
+	    if (!IS_ERR(_T)) crypto_free_shash(_T));
+
+static int _refresh_report(struct tsm_measurement *tmr,
+			   const struct tsm_measurement_register *mr)
+{
+	pr_debug(KBUILD_MODNAME ": %s(%s,%s)\n", __func__, tmr->name,
+		 mr->mr_name);
+	struct crypto_shash *tfm __free(shash) =
+		crypto_alloc_shash(hash_algo_name[HASH_ALGO_SHA512], 0, 0);
+	if (IS_ERR(tfm))
+		return PTR_ERR(tfm);
+	return crypto_shash_tfm_digest(tfm, (u8 *)&example_report,
+				       offsetof(typeof(example_report),
+						report_digest),
+				       example_report.report_digest);
+}
+
+static int _extend_mr(struct tsm_measurement *tmr,
+		      const struct tsm_measurement_register *mr, const u8 *data)
+{
+	SHASH_DESC_ON_STACK(desc, 0);
+	int rc;
+
+	pr_debug(KBUILD_MODNAME ": %s(%s,%s)\n", __func__, tmr->name,
+		 mr->mr_name);
+
+	desc->tfm = crypto_alloc_shash(hash_algo_name[mr->mr_hash], 0, 0);
+	if (IS_ERR(desc->tfm))
+		return PTR_ERR(desc->tfm);
+
+	BUG_ON(crypto_shash_digestsize(desc->tfm) != mr->mr_size);
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
+	/* the entire report can be considered as a LIVE MR */
+	{ "full_report", &example_report, sizeof(example_report),
+	  TSM_MR_F_LIVE | TSM_MR_F_F },
+	/* static MR, read-only */
+	{ MR_(static_mr, SHA384) },
+	/* config MR, read-only */
+	{ MR_(config_mr, SHA512) },
+	/* RTMR, direct extension prohibited */
+	{ MR_(rtmr0, SHA256) | TSM_MR_F_RTMR },
+	/* RTMR, direct extension allowed */
+	{ MR_(rtmr1, SHA384) | TSM_MR_F_RTMR | TSM_MR_F_W },
+	/* most CC archs allow including user data in attestation */
+	{ MR_(user_data, SHA512) | TSM_MR_F_W },
+	/* LIVE MR example, usually doesn't exist in real CC arch */
+	{ MR_(report_digest, SHA512) | TSM_MR_F_L },
+	/* terminating NULL entry */
+	{}
+};
+#undef MR_
+
+static struct tsm_measurement example_measurement_provider = {
+	.name = "measurement-example",
+	.mrs = example_mrs,
+	.refresh = _refresh_report,
+	.extend = _extend_mr,
+};
+
+static int __init measurement_example_init(void)
+{
+	int rc = tsm_register_measurement(&example_measurement_provider);
+	pr_debug(KBUILD_MODNAME ": tsm_register_measurement(%p)=%d\n",
+		 &example_measurement_provider, rc);
+	return rc;
+}
+
+static void __exit measurement_example_exit(void)
+{
+	int rc = tsm_unregister_measurement(&example_measurement_provider);
+	pr_debug(KBUILD_MODNAME ": tsm_unregister_measurement(%p)=%d\n",
+		 &example_measurement_provider, rc);
+}
+
+module_init(measurement_example_init);
+module_exit(measurement_example_exit);
+
+MODULE_LICENSE("GPL");
+MODULE_DESCRIPTION("Sample tsm_measurement implementation");

---

## [4] Alexey Kardashevskiy — 2024-11-04
*Subject: Re: [PATCH RFC v2 1/2] tsm: Add TVM Measurement Register Support*

On 1/11/24 03:50, Cedric Xing wrote:
> This commit extends the TSM core with support for CC measurement registers
> (MRs).

Why remove it?

>   #include <linux/tsm.h>
>   #include <linux/err.h>

Unrelated change usually goes to a separate preparation patch, otherwise 
too much noise.


>   {
>   	struct tsm_report *report = to_tsm_report(cfg);

Unrelated change here and below.

>   {
>   	struct tsm_report *report = to_tsm_report(cfg);


Seems unrelated.

> diff --git a/drivers/virt/coco/tsm-mr.c b/drivers/virt/coco/tsm-mr.c
> new file mode 100644

These two should go to drivers/virt/coco/tsm-mr.h, along with 
tsm_measurement_register and other TSM_MR_F_*.

> +
> +enum _mrdir_bin_attr_index {

Why do so many things have "_" prefix in this file?

> +	_MRDIR_BA_DIGEST,
> +	_MRDIR_BA__COUNT,

One underscore would do.

> +};
> +

No definition for TSM_MR_F_F (seems to come later in 2/2), how does this 
compile?


> +		return container_of(kobj, struct _mr_provider, kset.kobj);
> +	else

Harsh. These days people do not like even WARN_ON :) None of these 
BUG_ONs seem bad enough to kill the system, dunno.

> +	kfree(pvd->mrfiles);
> +	kfree(pvd);

Extra empty line not needed.

> +	struct _mr_provider *pvd __free(_unregister_measurement);
> +	int rc, nr;

An empty line missing here.

> +		struct attribute_group agrp = {
> +			.attrs = attrs,

Is this needed for __free() machinery?


> +	return 0;
> +}

Empty line missing. scripts/checkpatch.pl should have detected it. Thanks,

> +	if (!kobj)
> +		return -ENOENT;

---

## [5] Alexey Kardashevskiy — 2024-11-04
*Subject: Re: [PATCH RFC v2 2/2] tsm: Add TVM Measurement Sample Code*

On 1/11/24 03:50, Cedric Xing wrote:
> This sample kernel module demonstrates how to make MRs accessible to user mode
> through TSM.

Do we actually need this many nodes? A digest is 64bytes long (or 128 
chars), hash_algo is lot less, "config_mr" could just print 
human-readable 2 lines (one with the algo, one with the digest), just 
like many other things in sysfs. And with one node per MR - no need in 
that suspicios _kset_put_children() (which at least belongs to 
lib/kobject.c). Or more nodes are coming?

(ignore if it's been discussed)

>      ├── full_report
>      ├── report_digest

It looks that /sys/kernel/tsm/full_report is a binary concatenation of 6 
digests, with no hash_algo and no hint which digest is which, hardly a 
"structure". I do understand it is an example though :)



> - `rtmr0` is an RTMR with `TSM_MR_F_W` **cleared**, preventing direct
>    extensions; as a result, `rtmr0/digest` is read-only.

Usually these use hex.

> +	TSM_MR_F_LIVE = TSM_MR_F_L | TSM_MR_F_R,
> +	TSM_MR_F_RTMR = TSM_MR_F_LIVE | TSM_MR_F_X,

Why this alignment?

> +{
> +	u8 static_mr[SHA384_DIGEST_SIZE];

What is indirect extension here? Thanks,

> +	{ MR_(rtmr0, SHA256) | TSM_MR_F_RTMR },
> +	/* RTMR, direct extension allowed */

---

## [6] James Bottomley — 2024-11-04
*Subject: Re: [PATCH RFC v2 2/2] tsm: Add TVM Measurement Sample Code*

On Mon, 2024-11-04 at 19:40 +1100, Alexey Kardashevskiy wrote:
> On 1/11/24 03:50, Cedric Xing wrote:
> > This sample kernel module demonstrates how to make MRs accessible

Actually, that's not supposed to be like anything in sysfs.  Attributes
are supposed to have one value per file:

https://docs.kernel.org/filesystems/sysfs.html#attributes

However, as I keep saying, this structure doesn't support systems, like
the TPM, which can have multiple hashes per measurement register, so I
still think the structure should be

<measurement type>/<pcr number>/<hash>/digest

to allow for that.  I even think even Intel will be forced to use agile
cryptography one day: even if Shor's algorithm isn't realised post
quantum, the hash and curve will have to expand to at least 512 bits
and there's bound to be several candidates plus backwards compatibility
problems.

[...]
> It looks that /sys/kernel/tsm/full_report is a binary concatenation
> of 6 digests, with no hash_algo and no hint which digest is which,

That doesn't sound right: the rtmrs can be extended post launch, so
this should be some type of log of all the post launch measurements to
allow the relying system to examine the events as well as the final
value.

James

---

## [7] Xing, Cedric — 2024-11-04
*Subject: Re: [PATCH RFC v2 1/2] tsm: Add TVM Measurement Register Support*

On 11/3/2024 9:51 PM, Alexey Kardashevskiy wrote:
> On 1/11/24 03:50, Cedric Xing wrote:
>> diff --git a/drivers/virt/coco/tsm.c b/drivers/virt/coco/tsm-core.c
It's not used anywhere...

>>   #include <linux/tsm.h>
>>   #include <linux/err.h>
You are right. I'll capture all the "noise" in a single preparation commit.

>> -MODULE_DESCRIPTION("Provide Trusted Security Module attestation 
>> reports via configfs");
Are you suggesting an edit to the module description or simply 
complaining about unrelated changes in the same commit?

>> diff --git a/drivers/virt/coco/tsm-mr.c b/drivers/virt/coco/tsm-mr.c
>> new file mode 100644
TSM_MR_F_* are part of the module interface and have been defined in 
include/linux/tsm.h

These 2 are internal functions called by the module entry/exit points 
only. Their prototypes appear here merely to avoid the compiler warning.

>> +
>> +enum _mrdir_bin_attr_index {
All "_" prefixed symbols are file local. I should have used a more 
explicit prefix. I'll change this in the next revision.

>> +    _MRDIR_BA_DIGEST,
>> +    _MRDIR_BA__COUNT,
Are you talking about the double "__" in _MRDIR_BA__COUNT? It isn't part 
of the enum logically, so I put an extra "_". A precedence is 
include/uapi/linux/hash_info.h:41 in the existing kernel source.

>> [...]
>> +static void _mr_provider_release(struct kobject *kobj)
This BUG_ON has helped me catch kobject leaks in my code. I don't have 
problem removing it. But is there a guideline on what kinds of 
BUG_ON/WARN_ON should be kept/removed?

>> [...]
>> +int tsm_register_measurement(struct tsm_measurement *tmr)
Thanks for pointing these out!

>> [...]
>> +    pvd = NULL;
Yes. I should have put a comment here.

>> [...]
>> +    struct kobject *kobj = kset_find_obj(_sysfs_tsm, tmr->name);
Will run scripts/checkpatch.pl on the next revision before sending it out.

---

## [8] James Bottomley — 2024-11-04
*Subject: Re: [PATCH RFC v2 1/2] tsm: Add TVM Measurement Register Support*

On Mon, 2024-11-04 at 16:14 -0600, Xing, Cedric wrote:
> On 11/3/2024 9:51 PM, Alexey Kardashevskiy wrote:
> > On 1/11/24 03:50, Cedric Xing wrote:

Yes, it is; it's used in this line, which the patch doesn't appear to
remove:

int tsm_register(const struct tsm_ops *ops, void *priv)
{
	const struct tsm_ops *conflict;

	guard(rwsem_write)(&tsm_rwsem);
	conflict = provider.ops;
	if (conflict) {
		pr_err("\"%s\" ops already registered\n", conflict->name);
                ^^^^^^^

James

---

## [9] Xing, Cedric — 2024-11-04
*Subject: Re: [PATCH RFC v2 1/2] tsm: Add TVM Measurement Register Support*

On 11/4/2024 4:22 PM, James Bottomley wrote:
> On Mon, 2024-11-04 at 16:14 -0600, Xing, Cedric wrote:
>> On 11/3/2024 9:51 PM, Alexey Kardashevskiy wrote:
Now I remember. I had been seeing the module name somehow got printed 
twice in the log, so I removed it. Probably something wrong with my 
build env. I'll add that back. Thanks for pointing this out!

---

## [10] Alexey Kardashevskiy — 2024-11-05
*Subject: Re: [PATCH RFC v2 1/2] tsm: Add TVM Measurement Register Support*

On 5/11/24 09:14, Xing, Cedric wrote:
> On 11/3/2024 9:51 PM, Alexey Kardashevskiy wrote:
>> On 1/11/24 03:50, Cedric Xing wrote:


I am not even sure we want necessarily all of this changed, we can have 
100 char lines now.

> 
>>> -MODULE_DESCRIPTION("Provide Trusted Security Module attestation 

The unrelated change complain.

> 
>>> diff --git a/drivers/virt/coco/tsm-mr.c b/drivers/virt/coco/tsm-mr.c

I do not think you need any prefix here (just mark those "static"), and 
"mr" is there already anyway, imho more than enough.


>>> +    _MRDIR_BA_DIGEST,
>>> +    _MRDIR_BA__COUNT,

okay :)

>>> [...]
>>> +static void _mr_provider_release(struct kobject *kobj)

Sounds like only hardware faults are okay-ish to be guarded with BUG_ON.

https://www.kernel.org/doc/html/latest/process/deprecated.html#bug-and-bug-on

WARN_ON is considered as bad as many use panic_on_oops. Thanks,


>>> [...]
>>> +int tsm_register_measurement(struct tsm_measurement *tmr)

---

## [11] Mikko Ylinen — 2024-11-12
*Subject: Re: [PATCH RFC v2 0/2] tsm: Unified Measurement Register ABI for TVMs*

On Thu, Oct 31, 2024 at 11:50:39AM -0500, Cedric Xing wrote:
> NOTE: This patch series introduces the Measurement Register (MR) ABI, and is
> largely a continuation of Samuel Ortiz’s previous work on the RTMR ABI [1].

I think we also need think about the user ABI here. While there's a use
case for user components (running in a CVM) to read and evaluate the static parts
of the report, exposing them in a vendor agnostic way can be difficult.

Is it justified for the kernel parse the report details and make them available
or would it be enough to let users to parse TSM Reports @outblob based on @provider
info for the parts they are interested?

On the runtime measurement registers, [1] took the approach where only a generic
transport (same thinking as with TSM Reports) was provided and the proposed user
ABI was only the digest with a pre-configured target register index without any
vendor specifics.

> `struct tsm_measurement`, which holds an array of
> `struct tsm_measurement_register` and includes operations for reading and

---
