---
title: 'tsm: Unified Measurement Register ABI for TVMs'
date: 2024-09-07
last_reply: 2024-10-24
message_count: 36
participants: ['Cedric Xing', 'Alexander Graf', 'Jeff Johnson', 'Jean-Philippe Brucker', 'James Bottomley', 'Qinkun Bao', 'Dan Williams', 'Christophe de Dinechin', 'Mikko Ylinen']
---

## [1] Cedric Xing — 2024-09-07

NOTE: This patch series introduces the Measurement Register (MR) ABI, and is
largely a continuation of Samuel Ortiz’s previous work on the RTMR ABI [1].

This patch series adds a unified interface to TSM core for confidential
computing (CC) guest drivers to provide access to measurement registers (MRs),
which are essential for relying parties (RPs) to verify the integrity of the
computing environment. The interface is structured around
`struct tsm_measurement_provider`, which holds an array of
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
the `TSM_MR_F_X` flag. For examples of defining and implementing MRs, refer to
Patch 3.

MRs are made accessible to applications through a directory tree, where static
MRs are represented as files and RTMRs as directories containing elements like
`digest` and `hash_algo`. Although the current root of this directory tree is
`/sys/kernel/tsm/`, other potential locations include configfs
(`/sys/kernel/config/tsm/`) and securityfs (`/sys/kernel/security/tsm/`). This
RFC (Request for Comments) series seeks feedback on the interfaces, with the
directory tree's location being a secondary concern. Further details can be
found in Patch 1.

Patch 2 introduces event log support for RTMRs, addressing the fact that the
standalone values of RTMRs, which represent the cumulative digests of
sequential events, are not fully informative on their own.

[1]: https://patchwork.kernel.org/project/linux-integrity/cover/20240128212532.2754325-1-sameo@rivosinc.com/

Signed-off-by: Cedric Xing <cedric.xing@intel.com>
---
Cedric Xing (3):
      tsm: Add TVM Measurement Register Support
      tsm: Add RTMR event logging
      tsm: Add TVM Measurement Sample Code

 drivers/virt/coco/Kconfig         |   4 +-
 drivers/virt/coco/tsm.c           | 598 +++++++++++++++++++++++++++++++++++++-
 include/linux/tsm.h               |  62 ++++
 samples/Kconfig                   |   4 +
 samples/Makefile                  |   1 +
 samples/tsm/Makefile              |   2 +
 samples/tsm/measurement-example.c | 116 ++++++++
 7 files changed, 777 insertions(+), 10 deletions(-)
---
base-commit: 431c1646e1f86b949fa3685efc50b660a364c2b6
change-id: 20240904-tsm-rtmr-7a45859d2a96

Best regards,

---

## [2] Cedric Xing — 2024-09-07
*Subject: [PATCH RFC 1/3] tsm: Add TVM Measurement Register Support*

This commit extends the TSM core with support for CC measurement registers
(MRs).

The newly added APIs are:

- `tsm_register_measurement_provider(struct tsm_measurement_provider *)`
  This function allows a CC guest driver to register a set of measurement
  registers with the TSM core.
- `tsm_unregister_measurement_provider(struct tsm_measurement_provider *)`:
  This function enables a CC guest driver to unregister a previously registered
  set of measurement registers.

The `struct tsm_measurement_provider` has been defined to encapsulate the
details of CC-specific MRs. It includes an array of
`struct tsm_measurement_register`s and provides operations for reading and
updating these registers. For a comprehensive understanding of the structure
and its usage, refer to the detailed comments added in `include/linux/tsm.h`.

Upon successful registration of a measurement provider, the TSM core exposes
the MRs through a directory tree in the sysfs filesystem. The root of this tree
is located at `/sys/kernel/tsm/<MR provider>/`, with `<MR provider>` being the
name of the measurement provider. Each static MR is made accessible as a
read-only file, named after the MR itself. Runtime MRs (RTMRs) are represented
as directories named after the RTMR, containing two files: `digest` and
`hash_algo`. The purpose and content of these files are self-explanatory.

Signed-off-by: Cedric Xing <cedric.xing@intel.com>
---
 drivers/virt/coco/Kconfig |   4 +-
 drivers/virt/coco/tsm.c   | 390 ++++++++++++++++++++++++++++++++++++++++++++--
 include/linux/tsm.h       |  62 ++++++++
 3 files changed, 446 insertions(+), 10 deletions(-)

diff --git a/drivers/virt/coco/Kconfig b/drivers/virt/coco/Kconfig
index 87d142c1f932..0ce23c8d5854 100644
--- a/drivers/virt/coco/Kconfig
+++ b/drivers/virt/coco/Kconfig
@@ -5,7 +5,9 @@
 
 config TSM_REPORTS
 	select CONFIGFS_FS
-	tristate
+	select SYSFS
+	select CRYPTO_HASH_INFO
+	tristate "Trusted Security Module (TSM) sysfs/configfs support"
 
 source "drivers/virt/coco/efi_secret/Kconfig"
 
diff --git a/drivers/virt/coco/tsm.c b/drivers/virt/coco/tsm.c
index 9432d4e303f1..e83143f22fad 100644
--- a/drivers/virt/coco/tsm.c
+++ b/drivers/virt/coco/tsm.c
@@ -1,8 +1,6 @@
 // SPDX-License-Identifier: GPL-2.0-only
 /* Copyright(c) 2023 Intel Corporation. All rights reserved. */
 
-#define pr_fmt(fmt) KBUILD_MODNAME ": " fmt
-
 #include <linux/tsm.h>
 #include <linux/err.h>
 #include <linux/slab.h>
@@ -11,6 +9,8 @@
 #include <linux/module.h>
 #include <linux/cleanup.h>
 #include <linux/configfs.h>
+#include <crypto/hash_info.h>
+#include <crypto/hash.h>
 
 static struct tsm_provider {
 	const struct tsm_ops *ops;
@@ -166,8 +166,9 @@ static ssize_t tsm_report_service_guid_store(struct config_item *cfg,
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
@@ -187,8 +188,8 @@ static ssize_t tsm_report_service_manifest_version_store(struct config_item *cfg
 }
 CONFIGFS_ATTR_WO(tsm_report_, service_manifest_version);
 
-static ssize_t tsm_report_inblob_write(struct config_item *cfg,
-				       const void *buf, size_t count)
+static ssize_t tsm_report_inblob_write(struct config_item *cfg, const void *buf,
+				       size_t count)
 {
 	struct tsm_report *report = to_tsm_report(cfg);
 	int rc;
@@ -341,7 +342,8 @@ static struct configfs_attribute *tsm_report_attrs[] = {
 	[TSM_REPORT_PRIVLEVEL_FLOOR] = &tsm_report_attr_privlevel_floor,
 	[TSM_REPORT_SERVICE_PROVIDER] = &tsm_report_attr_service_provider,
 	[TSM_REPORT_SERVICE_GUID] = &tsm_report_attr_service_guid,
-	[TSM_REPORT_SERVICE_MANIFEST_VER] = &tsm_report_attr_service_manifest_version,
+	[TSM_REPORT_SERVICE_MANIFEST_VER] =
+		&tsm_report_attr_service_manifest_version,
 	NULL,
 };
 
@@ -383,7 +385,8 @@ static bool tsm_report_is_visible(struct config_item *item,
 }
 
 static bool tsm_report_is_bin_visible(struct config_item *item,
-				      struct configfs_bin_attribute *attr, int n)
+				      struct configfs_bin_attribute *attr,
+				      int n)
 {
 	guard(rwsem_read)(&tsm_rwsem);
 	if (!provider.ops)
@@ -476,7 +479,370 @@ int tsm_unregister(const struct tsm_ops *ops)
 }
 EXPORT_SYMBOL_GPL(tsm_unregister);
 
+enum _rtmr_bin_attr_index {
+	_RTMR_BATTR_DIGEST,
+	_RTMR_BATTR__COUNT,
+};
+
+struct _rtmr {
+	struct kobject kobj;
+	struct bin_attribute battrs[_RTMR_BATTR__COUNT];
+};
+
+struct _mr_provider {
+	struct kset kset;
+	struct rw_semaphore rwsem;
+	struct bin_attribute *static_mrs;
+	struct tsm_measurement_provider *provider;
+	bool in_sync;
+};
+
+static inline const struct tsm_measurement_register *
+_rtmr_mr(const struct _rtmr *rtmr)
+{
+	return (struct tsm_measurement_register *)rtmr
+		->battrs[_RTMR_BATTR_DIGEST]
+		.private;
+}
+
+static inline struct _mr_provider *
+_mr_to_group(const struct tsm_measurement_register *mr, struct kobject *kobj)
+{
+	if (!(mr->mr_flags & TSM_MR_F_X))
+		return container_of(kobj, struct _mr_provider, kset.kobj);
+	else
+		return container_of(kobj->kset, struct _mr_provider, kset);
+}
+
+static inline int _call_refresh(struct _mr_provider *pvd,
+				const struct tsm_measurement_register *mr)
+{
+	int rc = pvd->provider->refresh(pvd->provider, mr);
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
+	int rc = pvd->provider->extend(pvd->provider, mr, data);
+	if (rc)
+		pr_warn(KBUILD_MODNAME ": %s.extend(%s) failed %d\n",
+			kobject_name(&pvd->kset.kobj), mr->mr_name, rc);
+	return rc;
+}
+
+static ssize_t hash_algo_show(struct kobject *kobj, struct kobj_attribute *attr,
+			      char *page)
+{
+	struct _rtmr *rtmr;
+	rtmr = container_of(kobj, typeof(*rtmr), kobj);
+	return sysfs_emit(page, "%s", hash_algo_name[_rtmr_mr(rtmr)->mr_hash]);
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
+	pvd = _mr_to_group(mr, kobj);
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
+		pr_debug(KBUILD_MODNAME ": refresh(%s,%s)=%d\n",
+			 kobject_name(&pvd->kset.kobj), mr->mr_name, rc);
+
+	up_read(&pvd->rwsem);
+	return rc ?: count;
+}
+
+static inline size_t snprint_hex(char *sbuf, size_t size, const u8 *data,
+				 size_t len)
+{
+	size_t ret = 0;
+	for (size_t i = 0; i < len; ++i)
+		ret += snprintf(sbuf + ret, size - ret, "%02x", data[i]);
+	return ret;
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
+	pvd = _mr_to_group(mr, kobj);
+	rc = down_write_killable(&pvd->rwsem);
+	if (rc)
+		return rc;
+
+	if (mr->mr_flags & TSM_MR_F_X)
+		rc = pvd->provider->extend(pvd->provider, mr, (u8 *)page);
+	else {
+		BUG_ON(!(mr->mr_flags & TSM_MR_F_W));
+		memcpy(mr->mr_value, page, count);
+	}
+
+	if (!rc)
+		pvd->in_sync = false;
+	else
+		pr_warn(KBUILD_MODNAME ": extending %s/%s failed with %ld\n",
+			kobject_name(&pvd->kset.kobj), mr->mr_name, rc);
+
+	up_write(&pvd->rwsem);
+	return rc ?: count;
+}
+
+static void _rtmr_release(struct kobject *kobj)
+{
+	struct _rtmr *rtmr;
+	rtmr = container_of(kobj, typeof(*rtmr), kobj);
+	pr_debug("%s(%s)\n", __func__, kobject_name(kobj));
+	kfree(rtmr);
+}
+
+static struct kobj_type _rtmr_ktype = {
+	.release = _rtmr_release,
+	.sysfs_ops = &kobj_sysfs_ops,
+};
+
+static struct _rtmr *_rtmr_create(const struct tsm_measurement_register *mr,
+				  struct _mr_provider *pvd)
+{
+	struct _rtmr *rtmr __free(kfree);
+	int rc;
+
+	BUG_ON(!(mr->mr_flags & TSM_MR_F_X));
+	rtmr = kzalloc(sizeof(*rtmr), GFP_KERNEL);
+	if (!rtmr)
+		return ERR_PTR(-ENOMEM);
+
+	sysfs_bin_attr_init(&rtmr->battrs[_RTMR_BATTR_DIGEST]);
+	rtmr->battrs[_RTMR_BATTR_DIGEST].attr.name = "digest";
+	if (mr->mr_flags & TSM_MR_F_W)
+	rtmr->battrs[_RTMR_BATTR_DIGEST].attr.mode |= S_IWUSR;
+	if (mr->mr_flags & TSM_MR_F_R)
+		rtmr->battrs[_RTMR_BATTR_DIGEST].attr.mode |= S_IRUGO;
+
+	rtmr->battrs[_RTMR_BATTR_DIGEST].size = mr->mr_size;
+	rtmr->battrs[_RTMR_BATTR_DIGEST].read = _mr_read;
+	rtmr->battrs[_RTMR_BATTR_DIGEST].write = _mr_write;
+	rtmr->battrs[_RTMR_BATTR_DIGEST].private = (void *)mr;
+
+	rtmr->kobj.kset = &pvd->kset;
+	rc = kobject_init_and_add(&rtmr->kobj, &_rtmr_ktype, NULL, "%s",
+				  mr->mr_name);
+	if (rc)
+		return ERR_PTR(rc);
+
+	return_ptr(rtmr);
+}
+
+static void _mr_provider_release(struct kobject *kobj)
+{
+	struct _mr_provider *pvd;
+	pvd = container_of(kobj, typeof(*pvd), kset.kobj);
+	pr_debug("%s(%s)\n", __func__, kobject_name(kobj));
+	BUG_ON(!list_empty(&pvd->kset.list));
+	kfree(pvd->static_mrs);
+	kfree(pvd);
+}
+
+static struct kobj_type _mr_provider_ktype = {
+	.release = _mr_provider_release,
+	.sysfs_ops = &kobj_sysfs_ops,
+};
+
 static struct config_group *tsm_report_group;
+static struct kset *_sysfs_tsm;
+
+static struct _mr_provider *
+_mr_provider_create(struct tsm_measurement_provider *tpvd)
+{
+	struct _mr_provider *pvd __free(kfree);
+	int rc;
+
+	pvd = kzalloc(sizeof(*pvd), GFP_KERNEL);
+	if (!pvd)
+		return ERR_PTR(-ENOMEM);
+
+	if (!tpvd->name || !tpvd->mrs || !tpvd->refresh || !tpvd->extend)
+		return ERR_PTR(-EINVAL);
+
+	rc = kobject_set_name(&pvd->kset.kobj, "%s", tpvd->name);
+	if (rc)
+		return ERR_PTR(rc);
+
+	pvd->kset.kobj.kset = _sysfs_tsm;
+	pvd->kset.kobj.ktype = &_mr_provider_ktype;
+	pvd->provider = tpvd;
+
+	rc = kset_register(&pvd->kset);
+	if (rc)
+		return ERR_PTR(rc);
+
+	return_ptr(pvd);
+}
+
+DEFINE_FREE(_unregister_measurement_provider, struct _mr_provider *,
+	    if (!IS_ERR_OR_NULL(_T))
+		    tsm_unregister_measurement_provider(_T->provider));
+
+int tsm_register_measurement_provider(struct tsm_measurement_provider *tpvd)
+{
+	static struct kobj_attribute _attr_hash = __ATTR_RO(hash_algo);
+
+	struct _mr_provider *pvd __free(_unregister_measurement_provider);
+	int rc, nr;
+
+	pvd = _mr_provider_create(tpvd);
+	if (IS_ERR(pvd))
+		return PTR_ERR(pvd);
+
+	nr = 0;
+	for (int i = 0; tpvd->mrs[i].mr_name; ++i) {
+		if (!(tpvd->mrs[i].mr_flags & TSM_MR_F_X)) {
+			++nr;
+			continue;
+		}
+
+		struct _rtmr *rtmr = _rtmr_create(&tpvd->mrs[i], pvd);
+		if (IS_ERR(rtmr))
+			return PTR_ERR(rtmr);
+
+		struct attribute *attrs[] = {
+			&_attr_hash.attr,
+			NULL,
+		};
+		struct bin_attribute
+			*battrs[_RTMR_BATTR__COUNT + 1] = {};
+		for (int j = 0; j < _RTMR_BATTR__COUNT; ++j)
+			battrs[j] = &rtmr->battrs[j];
+		struct attribute_group agrp = {
+			.attrs = attrs,
+			.bin_attrs = battrs,
+		};
+		rc = sysfs_create_group(&rtmr->kobj, &agrp);
+		if (rc)
+			return rc;
+	}
+
+	if (nr > 0) {
+		struct bin_attribute *static_mrs __free(kfree);
+		struct bin_attribute **battrs __free(kfree);
+
+		static_mrs = kcalloc(sizeof(*static_mrs), nr, GFP_KERNEL);
+		battrs = kcalloc(sizeof(*battrs), nr + 1, GFP_KERNEL);
+		if (!battrs || !static_mrs)
+			return -ENOMEM;
+
+		for (int i = 0, j = 0; tpvd->mrs[i].mr_name; ++i) {
+			if (tpvd->mrs[i].mr_flags & TSM_MR_F_X)
+				continue;
+
+			static_mrs[j].attr.name = tpvd->mrs[i].mr_name;
+			if (tpvd->mrs[i].mr_flags & TSM_MR_F_R) {
+				static_mrs[j].attr.mode |= S_IRUGO;
+				static_mrs[j].read = _mr_read;
+			}
+			if (tpvd->mrs[i].mr_flags & TSM_MR_F_W) {
+				static_mrs[j].attr.mode |= S_IWUSR;
+				static_mrs[j].write = _mr_write;
+			}
+			static_mrs[j].size = tpvd->mrs[i].mr_size;
+			static_mrs[j].private = (void *)&tpvd->mrs[i];
+
+			battrs[j] = &static_mrs[j];
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
+		pvd->static_mrs = no_free_ptr(static_mrs);
+	}
+
+	pvd = NULL;
+	return 0;
+}
+EXPORT_SYMBOL_GPL(tsm_register_measurement_provider);
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
+int tsm_unregister_measurement_provider(struct tsm_measurement_provider *tpvd)
+{
+	struct kobject *kobj = kset_find_obj(_sysfs_tsm, tpvd->name);
+	if (!kobj)
+		return -ENOENT;
+
+	struct _mr_provider *pvd = container_of(kobj, typeof(*pvd), kset.kobj);
+	BUG_ON(pvd->provider != tpvd);
+
+	_kset_put_children(&pvd->kset);
+	kset_unregister(&pvd->kset);
+	kobject_put(kobj);
+	return 0;
+}
+EXPORT_SYMBOL_GPL(tsm_unregister_measurement_provider);
 
 static int __init tsm_init(void)
 {
@@ -497,16 +863,22 @@ static int __init tsm_init(void)
 	}
 	tsm_report_group = tsm;
 
+	_sysfs_tsm = kset_create_and_add("tsm", NULL, kernel_kobj);
+	if (!_sysfs_tsm)
+		return -ENOMEM;
+
 	return 0;
 }
 module_init(tsm_init);
 
 static void __exit tsm_exit(void)
 {
+	kset_unregister(_sysfs_tsm);
 	configfs_unregister_default_group(tsm_report_group);
 	configfs_unregister_subsystem(&tsm_configfs);
 }
 module_exit(tsm_exit);
 
 MODULE_LICENSE("GPL");
-MODULE_DESCRIPTION("Provide Trusted Security Module attestation reports via configfs");
+MODULE_DESCRIPTION(
+	"Provide Trusted Security Module attestation reports via configfs");
diff --git a/include/linux/tsm.h b/include/linux/tsm.h
index 11b0c525be30..9fd7a2f0208e 100644
--- a/include/linux/tsm.h
+++ b/include/linux/tsm.h
@@ -5,6 +5,7 @@
 #include <linux/sizes.h>
 #include <linux/types.h>
 #include <linux/uuid.h>
+#include <uapi/linux/hash_info.h>
 
 #define TSM_INBLOB_MAX 64
 #define TSM_OUTBLOB_MAX SZ_32K
@@ -109,4 +110,65 @@ struct tsm_ops {
 
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
+ * @TSM_MR_F_X: this MR is extensible, should be set for RTMRs
+ * @TSM_MR_F_W: this MR is writable, should be set if direct extension to an
+ *              RTMR is allowed
+ * @TSM_MR_F_R: this MR is readable. All MRs should have this flag set
+ * @TSM_MR_F_L: this MR is live - writes to other MRs may change this MR
+ * @TSM_MR_F_LIVE: shorthand for L (live) and R (readable)
+ * @TSM_MR_F_RTMR: shorthand for LIVE and X (extensible)
+ */
+enum tsm_measurement_register_flag {
+	TSM_MR_F_X = 1,
+	TSM_MR_F_W = 2,
+	TSM_MR_F_R = 4,
+	TSM_MR_F_L = 8,
+	TSM_MR_F_LIVE = TSM_MR_F_L | TSM_MR_F_R,
+	TSM_MR_F_RTMR = TSM_MR_F_LIVE | TSM_MR_F_X,
+};
+
+#define TSM_MR_(h, f) .mr_size = h##_DIGEST_SIZE, .mr_flags = (f)
+#define TSM_MR(h) TSM_MR_(h, TSM_MR_F_R)
+#define TSM_RTMR(h) TSM_MR_(h, TSM_MR_F_RTMR), .mr_hash = HASH_ALGO_##h
+
+/**
+ * struct tsm_measurement_provider - define CC specific MRs and methods for
+ *                                   updating them
+ * @name: name of the measurement provider
+ * @mrs: array of MR definitions ending with mr_name set to %NULL
+ * @refresh: invoked to update the specified MR
+ * @extend: invoked to extend the specified MR with mr_size bytes
+ */
+struct tsm_measurement_provider {
+	const char *name;
+	const struct tsm_measurement_register *mrs;
+	int (*refresh)(struct tsm_measurement_provider *,
+		       const struct tsm_measurement_register *);
+	int (*extend)(struct tsm_measurement_provider *,
+		      const struct tsm_measurement_register *, const u8 *);
+};
+
+int tsm_register_measurement_provider(struct tsm_measurement_provider *);
+int tsm_unregister_measurement_provider(struct tsm_measurement_provider *);
+
 #endif /* __TSM_H */

---

## [3] Cedric Xing — 2024-09-07
*Subject: [PATCH RFC 2/3] tsm: Add RTMR event logging*

An RTMR typically accumulates measurements from multiple software components,
making its value alone less informative without an accompanying log.

The log format design distinguishes between the meaning (semantics) of events
and their storage.

- **Storage**: Specifies how to delineate and hash event records, allowing the
  kernel to accurately maintain logs without interpreting their contents.
- **Semantics**: The internal structure and meaning of records, defined by the
  agreements between applications and verifiers, are not processed by the
  kernel.

Event Log Format:

- Records are lines ending with `\n`.
- Each record (line) is hashed in its entirety (excluding the trailing `\n`)
  and extended to the RTMR.
- The log for an RTMR is stored at
  `/sys/kernel/tsm/<MR group name>/<RTMR name>/event_log` and consists of these
  delineated records.
- Lines that are empty (containing only `\n`) or start with `#` are skipped
  (not hashed or extended).

This patch adds two more files to every RTMR directory:

- `event_log`: A read-only file containing the full event log.
- `append_log`: A write-only file for appending new event records to the log.
  Records will be processed (hashed/extended) according to the format described
  above. Multiple records can be appended in a single write, provided their
  total size doesn't exceed the size limit (PAGE_SIZE). Partial records are not
  permitted - the last line written will always be treated as complete, even if
  not terminated by `\n`.

Special Event Records/Lines:

- A line starting with `SYNC` captures the RTMR value prior to the inclusion of
  that line, providing verifiers with the starting value of the RTMR. This line
  must be hashed/extended to prevent front-end log truncation.
- A line beginning with `# .EXTEND` indicates a direct extension to the RTMR by
  writing to `digest`. The remainder of the line specifies the value extended.
  Direct extensions cause the log to become out of sync; therefore, a `SYNC`
  line will be automatically generated at the next `append_event` write.

Signed-off-by: Cedric Xing <cedric.xing@intel.com>
---
 drivers/virt/coco/tsm.c | 230 +++++++++++++++++++++++++++++++++++++++++++++---
 1 file changed, 219 insertions(+), 11 deletions(-)

diff --git a/drivers/virt/coco/tsm.c b/drivers/virt/coco/tsm.c
index e83143f22fad..28a10330912c 100644
--- a/drivers/virt/coco/tsm.c
+++ b/drivers/virt/coco/tsm.c
@@ -9,6 +9,7 @@
 #include <linux/module.h>
 #include <linux/cleanup.h>
 #include <linux/configfs.h>
+#include <linux/ctype.h>
 #include <crypto/hash_info.h>
 #include <crypto/hash.h>
 
@@ -481,12 +482,14 @@ EXPORT_SYMBOL_GPL(tsm_unregister);
 
 enum _rtmr_bin_attr_index {
 	_RTMR_BATTR_DIGEST,
+	_RTMR_BATTR_LOG,
 	_RTMR_BATTR__COUNT,
 };
 
 struct _rtmr {
 	struct kobject kobj;
 	struct bin_attribute battrs[_RTMR_BATTR__COUNT];
+	bool log_in_sync;
 };
 
 struct _mr_provider {
@@ -505,8 +508,40 @@ _rtmr_mr(const struct _rtmr *rtmr)
 		.private;
 }
 
+static inline char *_rtmr_log(const struct _rtmr *rtmr)
+{
+	return (char *)rtmr->battrs[_RTMR_BATTR_LOG].private;
+}
+
+static inline size_t _rtmr_log_size(const struct _rtmr *rtmr)
+{
+	return rtmr->battrs[_RTMR_BATTR_LOG].size;
+}
+
+static inline void _rtmr_log_set_buf(struct _rtmr *rtmr, char *log)
+{
+	rtmr->battrs[_RTMR_BATTR_LOG].private = log;
+}
+
+static inline void _rtmr_log_inc_size(struct _rtmr *rtmr, size_t size)
+{
+	rtmr->battrs[_RTMR_BATTR_LOG].size += size;
+}
+
+static inline int _rtmr_log_update_attribute(struct _rtmr *rtmr)
+{
+	struct bin_attribute *attrs_to_update[] = {
+		&rtmr->battrs[_RTMR_BATTR_LOG],
+		NULL,
+	};
+	struct attribute_group agrp = {
+		.bin_attrs = attrs_to_update,
+	};
+	return sysfs_update_group(&rtmr->kobj, &agrp);
+}
+
 static inline struct _mr_provider *
-_mr_to_group(const struct tsm_measurement_register *mr, struct kobject *kobj)
+_mr_to_provider(const struct tsm_measurement_register *mr, struct kobject *kobj)
 {
 	if (!(mr->mr_flags & TSM_MR_F_X))
 		return container_of(kobj, struct _mr_provider, kset.kobj);
@@ -561,7 +596,7 @@ static ssize_t _mr_read(struct file *filp, struct kobject *kobj,
 	mr = (typeof(mr))attr->private;
 	BUG_ON(mr->mr_size != attr->size);
 
-	pvd = _mr_to_group(mr, kobj);
+	pvd = _mr_to_provider(mr, kobj);
 	rc = down_read_interruptible(&pvd->rwsem);
 	if (rc)
 		return rc;
@@ -591,9 +626,66 @@ static ssize_t _mr_read(struct file *filp, struct kobject *kobj,
 	return rc ?: count;
 }
 
-static inline size_t snprint_hex(char *sbuf, size_t size, const u8 *data,
+#define _EVENTLOG_GRANULARITY HPAGE_SIZE
+
+static ssize_t _log_extend_line(struct _rtmr *rtmr, const char *line,
+				const char *end, int newlines,
+				struct crypto_shash *tfm)
+{
+	struct _mr_provider *pvd;
+	pvd = container_of(rtmr->kobj.kset, typeof(*pvd), kset);
+	lockdep_assert_held_write(&pvd->rwsem);
+
+	BUG_ON(line > end);
+
+	while (line < end && isspace(line[0]))
+		++line;
+	while (line < end && isspace(end[-1]))
+		--end;
+	if (line == end)
+		return 0;
+
+	ssize_t count = end - line;
+	char *log = _rtmr_log(rtmr);
+	size_t needed = _rtmr_log_size(rtmr) + count + newlines;
+	if (ksize(log) < needed) {
+		log = krealloc(log,
+			       ALIGN(needed + _EVENTLOG_GRANULARITY / 2,
+				     _EVENTLOG_GRANULARITY),
+			       GFP_KERNEL);
+		if (!log)
+			return -ENOMEM;
+
+		_rtmr_log_set_buf(rtmr, log);
+	}
+
+	log += _rtmr_log_size(rtmr);
+	for (int i = 0; i < newlines; ++i)
+		*log++ = '\n';
+
+	if (*line != '#') {
+		u8 digest[SHA512_DIGEST_SIZE];
+		BUG_ON(tfm == NULL);
+		BUG_ON(sizeof(digest) < crypto_shash_digestsize(tfm));
+
+		int rc = crypto_shash_tfm_digest(tfm, line, count, digest);
+		if (!rc)
+			rc = _call_extend(pvd, _rtmr_mr(rtmr), digest);
+		if (rc)
+			return rc;
+	}
+
+	memcpy(log, line, count);
+	log[count] = '\n';
+	_rtmr_log_inc_size(rtmr, count += newlines + 1);
+
+	return _rtmr_log_update_attribute(rtmr) ?: count;
+}
+
+static inline size_t snprint_hex(char *sbuf, ssize_t size, const u8 *data,
 				 size_t len)
 {
+	BUG_ON(size < len * 2);
 	size_t ret = 0;
 	for (size_t i = 0; i < len; ++i)
 		ret += snprintf(sbuf + ret, size - ret, "%02x", data[i]);
@@ -614,15 +706,26 @@ static ssize_t _mr_write(struct file *filp, struct kobject *kobj,
 	mr = (typeof(mr))attr->private;
 	BUG_ON(mr->mr_size != attr->size);
 
-	pvd = _mr_to_group(mr, kobj);
+	pvd = _mr_to_provider(mr, kobj);
 	rc = down_write_killable(&pvd->rwsem);
 	if (rc)
 		return rc;
 
-	if (mr->mr_flags & TSM_MR_F_X)
-		rc = pvd->provider->extend(pvd->provider, mr, (u8 *)page);
-	else {
-		BUG_ON(!(mr->mr_flags & TSM_MR_F_W));
+	if (mr->mr_flags & TSM_MR_F_X) {
+		struct _rtmr *rtmr;
+		rtmr = container_of(kobj, typeof(*rtmr), kobj);
+
+		char ext_line[0x100] = "# .EXTEND ";
+		size_t len = strnlen(ext_line, sizeof(ext_line));
+		len += snprint_hex(ext_line + len, sizeof(ext_line) - len, page,
+				   count);
+		rc = _log_extend_line(rtmr, ext_line, ext_line + len,
+				      rtmr->log_in_sync, NULL);
+		if (!IS_ERR_VALUE(rc))
+			rc = _call_extend(pvd, mr, page);
+		if (!rc)
+			rtmr->log_in_sync = false;
+	} else {
 		memcpy(mr->mr_value, page, count);
 	}
 
@@ -636,11 +739,110 @@ static ssize_t _mr_write(struct file *filp, struct kobject *kobj,
 	return rc ?: count;
 }
 
+static ssize_t _log_read(struct file *filp, struct kobject *kobj,
+			 struct bin_attribute *attr, char *page, loff_t off,
+			 size_t count)
+{
+	struct _mr_provider *pvd;
+	int rc;
+
+	if (unlikely(off < 0))
+		return -EINVAL;
+
+	if (unlikely(off > attr->size))
+		return 0;
+
+	count = min(count, attr->size - off);
+	if (likely(count > 0)) {
+		pvd = container_of(kobj->kset, typeof(*pvd), kset);
+		rc = down_read_interruptible(&pvd->rwsem);
+		if (rc)
+			return rc;
+
+		memcpy(page, (char *)attr->private + off, count);
+
+		up_read(&pvd->rwsem);
+	}
+
+	return count;
+}
+
+static ssize_t _log_extend(struct _rtmr *rtmr, const char *page, size_t count,
+			   struct crypto_shash *tfm)
+{
+	ssize_t rc = 0, sz = 0;
+	for (size_t i = 0; i < count && !IS_ERR_VALUE(rc);) {
+		size_t j;
+		for (j = i; j < count && (page[j] != '\n' && page[j] != '\r');)
+			++j;
+
+		rc = _log_extend_line(rtmr, &page[i], &page[j], sz == 0, tfm);
+		sz += rc;
+
+		for (i = j; i < count && (page[i] == '\n' || page[i] == '\r');)
+			++i;
+	}
+
+	return IS_ERR_VALUE(rc) ? rc : sz;
+}
+
+DEFINE_FREE(shash, struct crypto_shash *,
+	    if (!IS_ERR(_T)) crypto_free_shash(_T));
+
+static ssize_t append_event_store(struct kobject *kobj,
+				  struct kobj_attribute *attr, const char *page,
+				  size_t count)
+{
+	struct _rtmr *rtmr;
+	rtmr = container_of(kobj, typeof(*rtmr), kobj);
+
+	const struct tsm_measurement_register *mr;
+	mr = _rtmr_mr(rtmr);
+
+	struct crypto_shash *tfm __free(shash) =
+		crypto_alloc_shash(hash_algo_name[mr->mr_hash], 0, 0);
+	if (IS_ERR(tfm))
+		return PTR_ERR(tfm);
+
+	struct _mr_provider *pvd;
+	pvd = container_of(kobj->kset, typeof(*pvd), kset);
+
+	ssize_t rc = down_write_killable(&pvd->rwsem);
+	if (rc)
+		return rc;
+
+	if (!rtmr->log_in_sync) {
+		if (mr->mr_flags & TSM_MR_F_L)
+			rc = _call_refresh(pvd, mr);
+
+		if (!IS_ERR_VALUE(rc)) {
+			char sync[0x100] = "SYNC ";
+			strncat(sync, hash_algo_name[mr->mr_hash],
+				sizeof(sync));
+			size_t len = strnlen(sync, sizeof(sync));
+			sync[len++] = '/';
+			len += snprint_hex(sync + len, sizeof(sync) - len,
+					   mr->mr_value, mr->mr_size);
+			rc = _log_extend_line(rtmr, sync, sync + len,
+					      _rtmr_log_size(rtmr) > 0, tfm);
+		}
+	}
+
+	if (!IS_ERR_VALUE(rc)) {
+		rtmr->log_in_sync = true;
+		rc = _log_extend(rtmr, page, count, tfm);
+	}
+
+	up_write(&pvd->rwsem);
+	return IS_ERR_VALUE(rc) ? rc : count;
+}
+
 static void _rtmr_release(struct kobject *kobj)
 {
 	struct _rtmr *rtmr;
 	rtmr = container_of(kobj, typeof(*rtmr), kobj);
 	pr_debug("%s(%s)\n", __func__, kobject_name(kobj));
+	kfree(_rtmr_log(rtmr));
 	kfree(rtmr);
 }
 
@@ -663,7 +865,7 @@ static struct _rtmr *_rtmr_create(const struct tsm_measurement_register *mr,
 	sysfs_bin_attr_init(&rtmr->battrs[_RTMR_BATTR_DIGEST]);
 	rtmr->battrs[_RTMR_BATTR_DIGEST].attr.name = "digest";
 	if (mr->mr_flags & TSM_MR_F_W)
-	rtmr->battrs[_RTMR_BATTR_DIGEST].attr.mode |= S_IWUSR;
+		rtmr->battrs[_RTMR_BATTR_DIGEST].attr.mode |= S_IWUSR;
 	if (mr->mr_flags & TSM_MR_F_R)
 		rtmr->battrs[_RTMR_BATTR_DIGEST].attr.mode |= S_IRUGO;
 
@@ -672,6 +874,11 @@ static struct _rtmr *_rtmr_create(const struct tsm_measurement_register *mr,
 	rtmr->battrs[_RTMR_BATTR_DIGEST].write = _mr_write;
 	rtmr->battrs[_RTMR_BATTR_DIGEST].private = (void *)mr;
 
+	sysfs_bin_attr_init(&rtmr->battrs[_RTMR_BATTR_LOG]);
+	rtmr->battrs[_RTMR_BATTR_LOG].attr.name = "event_log";
+	rtmr->battrs[_RTMR_BATTR_LOG].attr.mode = S_IRUGO;
+	rtmr->battrs[_RTMR_BATTR_LOG].read = _log_read;
+
 	rtmr->kobj.kset = &pvd->kset;
 	rc = kobject_init_and_add(&rtmr->kobj, &_rtmr_ktype, NULL, "%s",
 				  mr->mr_name);
@@ -734,6 +941,7 @@ DEFINE_FREE(_unregister_measurement_provider, struct _mr_provider *,
 int tsm_register_measurement_provider(struct tsm_measurement_provider *tpvd)
 {
 	static struct kobj_attribute _attr_hash = __ATTR_RO(hash_algo);
+	static struct kobj_attribute _attr_append = __ATTR_WO(append_event);
 
 	struct _mr_provider *pvd __free(_unregister_measurement_provider);
 	int rc, nr;
@@ -754,11 +962,11 @@ int tsm_register_measurement_provider(struct tsm_measurement_provider *tpvd)
 			return PTR_ERR(rtmr);
 
 		struct attribute *attrs[] = {
+			&_attr_append.attr,
 			&_attr_hash.attr,
 			NULL,
 		};
-		struct bin_attribute
-			*battrs[_RTMR_BATTR__COUNT + 1] = {};
+		struct bin_attribute *battrs[_RTMR_BATTR__COUNT + 1] = {};
 		for (int j = 0; j < _RTMR_BATTR__COUNT; ++j)
 			battrs[j] = &rtmr->battrs[j];
 		struct attribute_group agrp = {

---

## [4] Cedric Xing — 2024-09-07
*Subject: [PATCH RFC 3/3] tsm: Add TVM Measurement Sample Code*

This sample kernel module demonstrates how to make MRs accessible to user mode
through TSM.

Once loaded, this module registers a virtual measurement provider with the TSM
core and will result in the directory tree below.

/sys/kernel/tsm/
└── measurement-example
    ├── config_mr
    ├── full_report
    ├── report_digest
    ├── rtmr0
    │   ├── append_event
    │   ├── digest
    │   ├── event_log
    │   └── hash_algo
    ├── rtmr1
    │   ├── append_event
    │   ├── digest
    │   ├── event_log
    │   └── hash_algo
    ├── static_mr
    └── user_data

Among the MRs in this example:

- `static_mr` and `config_mr` are static MRs.
- `full_report` illustrates that a complete architecture-dependent attestation
  report structure (for instance, the `TDREPORT` structure in Intel TDX) can be
  presented as an MR.
- `user_data` represents the data provided by the software to be incorporated
  into the attestation report. Writing to this MR and then reading from
  `full_report` effectively triggers a request for an attestation report from
  the underlying CC hardware.
- `report_digest` serves as an example MR to demonstrate the use of the
  `TSM_MR_F_L` flag.
- `rtmr0` is an RTMR with `TSM_MR_F_W` **cleared**, preventing direct
  extensions; as a result, `rtmr0/digest` is read-only, and the sole method to
  extend this RTMR is by writing to `rtmr0/append_event`.
- `rtmr1` is an RTMR with `TSM_MR_F_W` **set**, permitting direct extensions;
  thus, `rtmr1/digest` is writable.

See comments in `samples/tsm/measurement-example.c` for more details.

Signed-off-by: Cedric Xing <cedric.xing@intel.com>
---
 samples/Kconfig                   |   4 ++
 samples/Makefile                  |   1 +
 samples/tsm/Makefile              |   2 +
 samples/tsm/measurement-example.c | 116 ++++++++++++++++++++++++++++++++++++++
 4 files changed, 123 insertions(+)

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
index 000000000000..b10bda4ba1ee
--- /dev/null
+++ b/samples/tsm/measurement-example.c
@@ -0,0 +1,116 @@
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
+	.static_mr = "STATIC MR",
+	.config_mr = "CONFIG MR",
+};
+
+DEFINE_FREE(shash, struct crypto_shash *,
+	    if (!IS_ERR(_T)) crypto_free_shash(_T));
+
+static int _refresh_report(struct tsm_measurement_provider *pvd,
+			   const struct tsm_measurement_register *mr)
+{
+	pr_debug(KBUILD_MODNAME ": %s(%s,%s)\n", __func__, pvd->name,
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
+static int _extend_mr(struct tsm_measurement_provider *pvd,
+		      const struct tsm_measurement_register *mr, const u8 *data)
+{
+	SHASH_DESC_ON_STACK(desc, 0);
+	int rc;
+
+	pr_debug(KBUILD_MODNAME ": %s(%s,%s)\n", __func__, pvd->name,
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
+#define MR_(mr) #mr, &example_report.mr, sizeof(example_report.mr), TSM_MR_F_R
+static const struct tsm_measurement_register example_mrs[] = {
+	/* the entire report can be considered as a LIVE MR */
+	{ "full_report", &example_report, sizeof(example_report),
+	  TSM_MR_F_LIVE },
+	/* static MR, read-only */
+	{ MR_(static_mr) },
+	/* config MR, read-only */
+	{ MR_(config_mr) },
+	/* RTMR, direct extension prohibited */
+	{ MR_(rtmr0) | TSM_MR_F_RTMR, HASH_ALGO_SHA256 },
+	/* RTMR, direct extension allowed */
+	{ MR_(rtmr1) | TSM_MR_F_RTMR | TSM_MR_F_W, HASH_ALGO_SHA384 },
+	/* most CC archs allow including user data in attestation */
+	{ MR_(user_data) | TSM_MR_F_W },
+	/* LIVE MR example, usually doesn't exist in real CC arch */
+	{ MR_(report_digest) | TSM_MR_F_L },
+	/* terminating NULL entry */
+	{}
+};
+#undef MR_
+
+static struct tsm_measurement_provider example_measurement_provider = {
+	.name = "measurement-example",
+	.mrs = example_mrs,
+	.refresh = _refresh_report,
+	.extend = _extend_mr,
+};
+
+static int __init measurement_example_init(void)
+{
+	int rc = tsm_register_measurement_provider(
+		&example_measurement_provider);
+	pr_debug(KBUILD_MODNAME ": tsm_register_measurement_provider(%p)=%d\n",
+		 &example_measurement_provider, rc);
+	return rc;
+}
+
+static void __exit measurement_example_exit(void)
+{
+	int rc = tsm_unregister_measurement_provider(
+		&example_measurement_provider);
+	pr_debug(KBUILD_MODNAME
+		 ": tsm_unregister_measurement_provider(%p)=%d\n",
+		 &example_measurement_provider, rc);
+}
+
+module_init(measurement_example_init);
+module_exit(measurement_example_exit);
+
+MODULE_LICENSE("GPL");

---

## [5] Alexander Graf — 2024-09-08
*Subject: Re: [PATCH RFC 0/3] tsm: Unified Measurement Register ABI for TVMs*

Hey Cedric,

On 08.09.24 06:56, Cedric Xing wrote:
> NOTE: This patch series introduces the Measurement Register (MR) ABI, and is
> largely a continuation of Samuel Ortiz’s previous work on the RTMR ABI [1].


Is there a particular reason to treat runtime and static measurements 
separately? In Nitro Enclaves (which I still need to add tsm integration 
for), both are simply NSM PCRs. "Static" measurements get locked by the 
initial boot code. "Runtime" measurements can get locked by guest code 
later in the boot process. But technically, both are the same type of 
measurement.

In fact, other attributes like an additional "hash_algo" to the 
measurement itself can be useful in general. If the underlying 
infrastructure allows for a generic event log mechanism, having that 
easily available here is useful too.

So I don't really understand why we would treat static and runtime 
measurements differently. Can't we just make all of them directories and 
indicate whether they are (im-)mutable via a file?


Alex




Amazon Web Services Development Center Germany GmbH
Krausenstr. 38
10117 Berlin
Geschaeftsfuehrung: Christian Schlaeger, Jonathan Weiss
Eingetragen am Amtsgericht Charlottenburg unter HRB 257764 B
Sitz: Berlin
Ust-ID: DE 365 538 597

---

## [6] Xing, Cedric — 2024-09-09
*Subject: Re: [PATCH RFC 0/3] tsm: Unified Measurement Register ABI for TVMs*

Hi Alex,

Thanks for you comments!

On 9/8/2024 12:37 PM, Alexander Graf wrote:
> Hey Cedric,
> 
My apologies for the confusion! They are in fact treated in the same way 
from the CC guest driver's perspective.

Here I meant to describe that static and runtime MRs have different 
properties (like "locked" as you mentioned) so in order to treat them in 
the same way, we'd have to define the properties in code (i.e., `enum 
tsm_measurement_register_flag` in include/linux/tsm.h).

> In fact, other attributes like an additional "hash_algo" to the 
> measurement itself can be useful in general. If the underlying 
`hash_algo` is indeed a member of `struct tsm_measurement_register`.

> So I don't really understand why we would treat static and runtime 
> measurements differently. Can't we just make all of them directories and 
Distinguishing them in the user interface makes enumeration of RTMRs 
easier. Also, there are RTMR specific artifacts that static MRs don't 
have. The most obvious is the `event_log`. `hash_algo` is less obvious 
but it is in fact applicable to RTMRs only (the only thing that a static 
MR has is its value). Adding those to static MRs would confuse users.

-Cedric

---

## [7] Jeff Johnson — 2024-09-09
*Subject: Re: [PATCH RFC 3/3] tsm: Add TVM Measurement Sample Code*

On 9/7/24 21:56, Cedric Xing wrote:
...
> +module_init(measurement_example_init);
> +module_exit(measurement_example_exit);

Missing MODULE_DESCRIPTION()

Since commit 1fffe7a34c89 ("script: modpost: emit a warning when the
description is missing"), a module without a MODULE_DESCRIPTION() will
result in a warning when built with make W=1. Recently, multiple
developers have been eradicating these warnings treewide, and very few
are left, so please don't introduce a new one :)

---

## [8] Xing, Cedric — 2024-09-09
*Subject: Re: [PATCH RFC 3/3] tsm: Add TVM Measurement Sample Code*

On 9/9/2024 10:14 AM, Jeff Johnson wrote:
> On 9/7/24 21:56, Cedric Xing wrote:
> ...

Thanks! This will be fixed in the next version of the series.

---

## [9] Alexander Graf — 2024-09-10
*Subject: Re: [PATCH RFC 0/3] tsm: Unified Measurement Register ABI for TVMs*

On 09.09.24 16:55, Xing, Cedric wrote:
> Hi Alex,
>


I'm not worried about the driver's perspective to be honest; I'm much 
more interested in the user space ABI and to ensure it's consistent and 
flexible :).


> Here I meant to describe that static and runtime MRs have different
> properties (like "locked" as you mentioned) so in order to treat them in


I think that this statement is looking too much at the problem with TDX 
glasses on. Conceptually, measurements can happen at any time by any 
component and then get locked going forward. Let's look a bit at what 
different solutions do:

TDX

static - special registers that get written by the secure module and are 
locked at launch (?); SHA256? No event log; order defined by platform.
dynamic - special registers that are mutable at runtime

SEV-SNP

static - launch digest generated by ASP at launch time using a SEV-SNP 
specific algorithm. No event log; order defined by platform.
dynamic - not specified, would be implemented by an SVSM

Nitro Enclaves

static - PCR0-15 get calculated and then locked by the boot loader. 
SHA384. No event log; mechanics to reproduce are defined in docs.
dynamic - PCR16-31 are up for customer use and can be locked at any 
later stage. SHA384. Event log is undefined and up to customer code.


All static calculations are based on some algorithm. Yes, the algorithm 
isn't necessarily a standard digest, but they can all have a name. I can 
also absolutely see how any of the solutions above gain event log 
support for static or dynamic measurements. At the end of the day, an 
event log for static measurements is just a matter of writing it out at 
launch time.

So what I'm trying to say is: In the user space ABI (file system 
layout), please treat static and dynamic registers identically. There 
really is no difference between them apart from the fact that some are 
read-only and others are read-write.


Alex




Amazon Web Services Development Center Germany GmbH
Krausenstr. 38
10117 Berlin
Geschaeftsfuehrung: Christian Schlaeger, Jonathan Weiss
Eingetragen am Amtsgericht Charlottenburg unter HRB 257764 B
Sitz: Berlin
Ust-ID: DE 365 538 597

---

## [10] Jean-Philippe Brucker — 2024-09-10
*Subject: Re: [PATCH RFC 0/3] tsm: Unified Measurement Register ABI for TVMs*

Hi Cedric,

On Sat, Sep 07, 2024 at 11:56:18PM -0500, Cedric Xing wrote:
> Patch 2 introduces event log support for RTMRs, addressing the fact that the
> standalone values of RTMRs, which represent the cumulative digests of

Would each event_log include the events that firmware wrote before Linux?
I'm wondering how this coexists with /sys/firmware/acpi/tables/data/CCEL.
Maybe something like: CCEL only contains pre-Linux events. The TSM driver
parses CCEL (using a format specific to the arch, for example TCG2),
separates the events by MR and produces event_log files in
/sys/kernel/tsm/, possibly in a different format like CEL-TLV. Is that
what you envision for TDX?

I ask because I've been looking into this interface for Arm CCA, and
having unified event logs available somewhere in /sys/kernel/confg/tsm
would be very convenient for users (avoids having to parse and convert
different /sys/firmware interfaces along with Linux event logs). I would
have put a single event_log in /sys/kernel/config/tsm/report/ but
splitting it by MR should work too.

As Alex I believe we need more similarity between the interfaces of static
and runtime measurements, because verifiers may benefit from an event log
of static measurements. For example Arm could have a configuration like
this:

  struct tsm_measurement_register arm_cca_mrs[] = {
	{ MR_(rim) | TSM_MR_F_R | TSM_MR_F_LOG, HA },
  	{ MR_(rem0) | TSM_MR_F_R | TSM_MR_F_X | TSM_MR_F_LOG, HA },
  	...
  	{ MR_(rem3) | TSM_MR_F_R | TSM_MR_F_X | TSM_MR_F_LOG, HA },
  };

Here rim is a static measurement of the initial VM state, impossible to
extend but could have an event log. rem0-3 are runtime measurements,
extensible by firmware and then Linux. None of the digests can be written
directly, only extended and read with calls to the upper layer. The tree
would be:

  /sys/kernel/config/tsm/
  ├── rim
  │   ├── digest
  │   ├── event_log
  │   └── hash_algo
  ├── rem0
  │   ├── digest
  │   ├── append_event
  │   ├── event_log
  │   └── hash_algo
  ... 
  ├── rem3
  │   ├── digest
  │   ├── append_event
  │   ├── event_log
  │   └── hash_algo
  └── report/$name
      ├── inblob
      └── outblob

Thanks,
Jean

---

## [11] Xing, Cedric — 2024-09-10
*Subject: Re: [PATCH RFC 0/3] tsm: Unified Measurement Register ABI for TVMs*

On 9/10/2024 2:47 AM, Alexander Graf wrote:
> On 09.09.24 16:55, Xing, Cedric wrote:
>> Distinguishing them in the user interface makes enumeration of RTMRs
You are absolute right that all MRs are the same thing, and that's why 
they are modeled in the same way at the CC guest driver level. In fact, 
if a CC guest wants to expose all MRs in their own dirs, it could set 
`TSM_MR_F_X` for all MRs and returns an error from `extend` for 
static/non-extensible ones. For example, PCR0~31 may all be exposed this 
way on Nitro. I hope this addresses your concerns.

---

## [12] Xing, Cedric — 2024-09-10
*Subject: Re: [PATCH RFC 0/3] tsm: Unified Measurement Register ABI for TVMs*

On 9/10/2024 12:09 PM, Jean-Philippe Brucker wrote:
> Hi Cedric,
> 
No. The log format proposed here is textual and incompatible with TCG2 
log format.

The proposed log format is based on the CoCo event log - 
https://github.com/confidential-containers/guest-components/issues/495.

> I'm wondering how this coexists with /sys/firmware/acpi/tables/data/CCEL.
The proposed log will take over after booting to Linux. The `SYNC` line 
in the log captures the RTMR value before it, which can be used to 
verify CCEL left off by the virtual firmware.

> Maybe something like: CCEL only contains pre-Linux events. The TSM driver
> parses CCEL (using a format specific to the arch, for example TCG2),
CCEL will be pre-Linux only. Given the proposed format is incompatible 
with TCG2 format, I don't think those 2 logs will be merged. But if we 
get any success in this new log format, we may influence the UEFI/OVMF 
community to adopt this new format in future.

We have evaluated both TCG2 and CEL formats but arrived in this new 
format because we'd like to support ALL applications. And the only sane 
way I could figure out is to separate the log into 2 layers - an 
application specific semantics layer (a contract between the application 
and the verifier), and an application agnostic storage layer 
(implemented by the kernel). The common problem of TCG2 and CEL is that 
the event/content tag/type dictates which part of the event data/content 
to hash, meaning the kernel must understand an event record before 
hashing it. And that has prevented an application agnostic storage design.

Anyway, this new log can be encapsulated in both CEL-JSON (like what 
systemd is doing today) and TCG2 (using the EV_ACTION event type) 
formats. Please see the CoCo issue (link given above) for more details.

> I ask because I've been looking into this interface for Arm CCA, and
> having unified event logs available somewhere in /sys/kernel/confg/tsm
We have considered one global log vs. per-MR logs. In fact, a global log 
is equivalent to the concatenation of all per-MR logs. We've adopted the 
per-MR approach to keep the log optional - i.e., an RTMR can be extended 
directly (by writing to its `digest` attribute) without a log.

With regard to the location of the MR tree, we picked sysfs because the 
MRs (and associated logs) are global and fit more into the semantics of 
sysfs than configfs. Dan W. and I are also considering moving both 
report/ and measurement/ trees into securityfs. It'll be highly 
appreciated if you (and Alex, and everyone) can share your insights.

> As Alex I believe we need more similarity between the interfaces of static
> and runtime measurements, because verifiers may benefit from an event log
I see. The desired/missing feature here I think is to allow a CC guest 
driver to supply an "initial log". I can define a LOG bit, which if set, 
will make the MR its own dir with `hash_algo` and `event_log`. And if X 
is also set, then `append_event` will appear as well. Does this sound 
like what Alex and you are looking for?

-Cedric

---

## [13] Alexander Graf — 2024-09-11
*Subject: Re: [PATCH RFC 0/3] tsm: Unified Measurement Register ABI for TVMs*

On 11.09.24 06:01, Xing, Cedric wrote:
>
> On 9/10/2024 12:09 PM, Jean-Philippe Brucker wrote:


I don't understand why we want to have 2 separate representations for a 
"measurement object": flat file as well as directory. Could you please 
elaborate on the rationale why you think it would be desirable to have a 
non-directory representation at all? I feel like I'm missing something :)

What if for example next-next-gen SEV-SNP suddenly gains event log 
support for its launch digest? We would create needless churn on user 
space to dynamically determine whether it should read things as 
directory or as file. Or even worse: Newer kernels would simply always 
set the LOG bit and we suddenly break the user space ABI for existing 
environments that run on current-gen SEV-SNP.


Alex




Amazon Web Services Development Center Germany GmbH
Krausenstr. 38
10117 Berlin
Geschaeftsfuehrung: Christian Schlaeger, Jonathan Weiss
Eingetragen am Amtsgericht Charlottenburg unter HRB 257764 B
Sitz: Berlin
Ust-ID: DE 365 538 597

---

## [14] James Bottomley — 2024-09-11
*Subject: Re: [PATCH RFC 0/3] tsm: Unified Measurement Register ABI for TVMs*

On Tue, 2024-09-10 at 23:01 -0500, Xing, Cedric wrote:
> On 9/10/2024 12:09 PM, Jean-Philippe Brucker wrote:
> > Hi Cedric,

Given that AMD is planning to use the SVSM-vTPM for post launch
measurements, not supporting TPMs in any form would make this Intel
only on x86 and thus not very "unified".  Microsoft also tends to do
attestations partly via the vTPM in its L1 openHCL component (even for
TDX) and thus would also have difficulty adopting this proposal.

Regards,

James

---

## [15] Qinkun Bao — 2024-09-11
*Subject: Re: [PATCH RFC 0/3] tsm: Unified Measurement Register ABI for TVMs*

On Wed, Sep 11, 2024 at 8:06 PM James Bottomley
<James.Bottomley@hansenpartnership.com> wrote:
>
> On Tue, 2024-09-10 at 23:01 -0500, Xing, Cedric wrote:

Hi James,

I don't think the patch should be blocked for not supporting the
SVSM-vTPM and it is not an Intel only patch.

1. Not everyone prefers the SVSM-vTPM as it lacks the persistent
storage and does not comply with TCG's TPM specifications. TPM is not
just about the measurement.
Sealing and unsealing data is also a critical functionality for TPM.
Treating thenSVSM-vTPM as a TPM misleads users and disrupts existing
software based on TPMs.
The SVSM-vTPM is not TPM. Just like Javascript is not Java.

2. If our goal is to measure the boot chain and post-launch, the RTMR
is an effective and straightforward method.
We already support RTMR for TDX. For SNP, simulating the RTMRs in SVSM
is very simple while implementing the SVSM-vTPM needs a lot of changes.
The SVSM-vTPM significantly expands the TCB while offering limited
security value enhancements
compared to the RTMR.

3. RTMR as a technology has been adopted widely. It is not an Intel
only technology. The TDX CVMs on Google Cloud already support RTMRs.
The TDX CVMs [1] on
Alibaba Cloud supports RTMR as well. In terms of the attestation verifiers,
the token from Intel ITA [2] and Microsoft Attestation Service [3]
indicate they support RTMRs. The Ubuntu image [4] from Canonical
enables RTMR by default.

Link:
[1] https://www.alibabacloud.com/help/en/ecs/user-guide/build-a-tdx-confidential-computing-environment
[2] https://docs.trustauthority.intel.com/main/restapi/attestation-v2.html
[3] https://learn.microsoft.com/en-us/azure/attestation/attestation-token-examples
[4] https://ubuntu.com/blog/deploy-confidential-computing-intel-tdx-ubuntu-2404

Thanks,
Qinkun

---

## [16] James Bottomley — 2024-09-11
*Subject: Re: [PATCH RFC 0/3] tsm: Unified Measurement Register ABI for TVMs*

On Wed, 2024-09-11 at 21:46 +0800, Qinkun Bao wrote:
> On Wed, Sep 11, 2024 at 8:06 PM James Bottomley
> <James.Bottomley@hansenpartnership.com> wrote:

Actually, I'm not objecting to the patch not supporting the TPM, I'm
objecting to design choices, like the log, that make it much harder to
add TPM support later.  Realistically if you want a universal
measurement ABI, it has to work for physical systems as well, which
means TPM or DICE, since RTMR is a bit non-standard.

> 1. Not everyone prefers the SVSM-vTPM as it lacks the persistent
> storage and does not comply with TCG's TPM specifications. TPM is not

I think you'll find an ephemeral TPM is TCG compliant: the NV is
actually an additional profile in the TCG specifications.

> Sealing and unsealing data is also a critical functionality for TPM.
> Treating thenSVSM-vTPM as a TPM misleads users and disrupts existing

I've already explained several times how sealing and unsealing can be
done with an ephemeral TPM. I'm not going to get into prejudices about
naming.

> 2. If our goal is to measure the boot chain and post-launch, the RTMR
> is an effective and straightforward method. We already support RTMR

in the upstream, the vTPM is already done.  There's no current pull
request for RTMR emulation.

> The SVSM-vTPM significantly expands the TCB while offering limited
> security value enhancements compared to the RTMR.

So would every other feature on the coconut roadmap.

> 3. RTMR as a technology has been adopted widely. It is not an Intel
> only technology. The TDX CVMs on Google Cloud already support RTMRs.

So you think Intel should abandon its work on ephemeral vTPMs for TDX?

Regards,

James

---

## [17] Dan Williams — 2024-09-11
*Subject: Re: [PATCH RFC 0/3] tsm: Unified Measurement Register ABI for TVMs*

James Bottomley wrote:
> On Tue, 2024-09-10 at 23:01 -0500, Xing, Cedric wrote:
> > On 9/10/2024 12:09 PM, Jean-Philippe Brucker wrote:

When I reviewed this with Cedric before hand I had been convinced that
this need not immediately trigger the "TPM vs RTMR" debate. Cedric can
jump in here where I get this wrong, but the thought is that once we
have this native RTMR interface with a cross-RTMR-vendor (Intel, RISCV,
ARM) common event-log it can be used to build virtual RTMRs / vTPM for
applications to use. In other words, use something like vtpm_proxy to
provide TPM services to applications, but proxy those those events to
this native RTMR backend.

---

## [18] Dan Williams — 2024-09-11
*Subject: Re: [PATCH RFC 0/3] tsm: Unified Measurement Register ABI for TVMs*

Xing, Cedric wrote:
[..]
> With regard to the location of the MR tree, we picked sysfs because the 
> MRs (and associated logs) are global and fit more into the semantics of 

I would only expect this new measurement interface is suitable for
considering securityfs. The tsm_report uAPI is already baked and has a
need for the multi-instance support of configfs.

The rationale for RTMR measurements in securityfs is because the IMA
measurement uAPI already lives there. So it is more about following
precedent for co-locating a new ASCII RTMR measurement log in the same
filesystem that provides ima/ascii_runtime_measurements.

A multi-instance interface for virtual RTMRs might be suitable to live
in configfs alongside reports/, and use this native singleton log as a
backend.

---

## [19] Xing, Cedric — 2024-09-11
*Subject: Re: [PATCH RFC 0/3] tsm: Unified Measurement Register ABI for TVMs*

Hi James,

I would like to clarify that, even though the log format is incompatible 
with the existing TCG2 log format, nothing prevents TPM PCRs from being 
exposed through the TSM measurement framework.

Please note that the existing event types in the TCG2 log format are 
predominantly BIOS/firmware-oriented, which seldom makes sense for 
applications in OS runtime. Consequently, most application-specific 
events have to come under the EV_EVENT_TAG umbrella, which is 
essentially arbitrary binary data with no specific format. Thus, I don't 
see much value in continuing the TCG2 log into OS runtime IMHO.

The proposed log format aims to provide a framework for unambiguous 
hashing while allowing application-defined events. Its primary design 
objective is to enable application-agnostic kernel/verifier to 
hash/verify logs without understanding the event records, allowing 
application-specific appraisers to be built on top (i.e., 
semantics/storage separation). Both TCG2 and CEL formats rely on 
event/content type to dictate what part of event data to hash, making 
semantics/storage separation impossible. Therefore, this proposed log 
format cannot accommodate entries from TCG2 or CEL logs due to that 
design conflict. However, entries of this log can easily be encapsulated 
in TCG2 (as EV_ACTION entries) or CEL-JSON (a new content type string 
needs to be defined, like what systemd is doing today) logs.

-Cedric

On 9/11/2024 9:10 AM, James Bottomley wrote:
> On Wed, 2024-09-11 at 21:46 +0800, Qinkun Bao wrote:
>> On Wed, Sep 11, 2024 at 8:06 PM James Bottomley

---

## [20] Jean-Philippe Brucker — 2024-09-12
*Subject: Re: [PATCH RFC 0/3] tsm: Unified Measurement Register ABI for TVMs*

On Tue, Sep 10, 2024 at 11:01:59PM -0500, Xing, Cedric wrote:
> On 9/10/2024 12:09 PM, Jean-Philippe Brucker wrote:
> > Hi Cedric,

Thank you for the explanation. In our case I'm guessing we'd then have a
userspace library to:

1. read the CCEL (from multiple FW interfaces unfortunately: ACPI,
   devicetree, maybe EFI)
2. read each event_log from your proposed interface
3. collate everything into a single log, using eg. CEL-CBOR, and send it
   to the verifier.

There may be some value in having the kernel TSM module do all of this,
but userspace seems like the right place for this sort of complexity,
especially the log format conversion.

> 
> > I ask because I've been looking into this interface for Arm CCA, and

I agree with Dan about keeping report/ in configfs. It would be nice to
have both in the same place, but no strong opinion.

> 
> > As Alex I believe we need more similarity between the interfaces of static

Yes, although that would only be necessary if this new interface is able
to include the pre-Linux events in the log, otherwise the event_log for
static measurements here wouldn't contain anything.

If firmware events aren't included in this new interface, then presenting
static measurements doesn't seem useful for Arm CCA, since by definition
they can't be extended. In my example I added 'digest' files only because
our interface allows to read them directly from the upper layer, but the
normal way to obtain digests is through /sys/kernel/config/tsm/report/,
where outblob contains all digests, signed by the platform. So for CCA the
tree would look more like:

    /sys/kernel/config/tsm/
    ├── rem0
    │   ├── append_event
    │   ├── event_log
    │   └── hash_algo
    ...
    ├── rem3
    │   ├── append_event
    │   ├── event_log
    │   └── hash_algo
    └── report/$name
        ├── inblob
        └── outblob

But I understand other archs could have a use for presenting the static
measurements here, in which case presenting them in their own dir with a
fine-grained selection of files like you suggest below would make sense.

Thanks,
Jean

> I can define a LOG bit, which if set,
> will make the MR its own dir with `hash_algo` and `event_log`. And if X is

---

## [21] Christophe de Dinechin — 2024-09-12
*Subject: Re: [PATCH RFC 0/3] tsm: Unified Measurement Register ABI for TVMs*

> On 10 Sep 2024, at 19:09, Jean-Philippe Brucker <jean-philippe@linaro.org> wrote:
> 

It’s nice to have a similar structure between ARM and x86, but how does
user space know what each register holds? For example, say that I want
a digest of the initial VM state, of the boot configuration, of the
command line, or of the firmware, where do I get that? When using a TPM,
there are conventions on which PCR stores which particular piece of
information.

Is the idea to defer that to user space, or should we also have some
symlinks exposing this or that specific register when it exists under
a common, platform-agnostic name? e.g. on ARM you would have

/sys/kernel/config/tsm/initial_vm_state -> ./rim

It looks to me like this could simplify the writing of user-space
attestation agents, for example. But then, maybe I’m too optimistic
and such agents would always be platform-dependent anyway.

One data point is that about one year ago, CoCo has already split the
platform dependencies away in their attestation stack, at the time
mostly to cover differences between AMD and Intel.

> 
> Thanks,

Cheers,
Christophe de Dinechin (https://c3d.github.io)
Freedom Covenant (https://github.com/c3d/freedom-covenant)
Theory of Incomplete Measurements (https://c3d.github.io/TIM)

---

## [22] Jean-Philippe Brucker — 2024-09-12
*Subject: Re: [PATCH RFC 0/3] tsm: Unified Measurement Register ABI for TVMs*

On Thu, Sep 12, 2024 at 12:03:05PM +0200, Christophe de Dinechin wrote:
> It’s nice to have a similar structure between ARM and x86, but how does
> user space know what each register holds? For example, say that I want

It's early days for Arm and this is still something we need to formalize.
The initial VM state always goes in the RIM (~MRTD) and REM[0-3] (~RTMR)
contain runtime measurements. TDX already defined a correspondence between
PCR and RTMR in UEFI:

https://uefi.org/specs/UEFI/2.10/38_Confidential_Computing.html#intel-trust-domain-extension

  TPM PCR Index | TDX-measurement register
   ---------------------------------------
  0             |   MRTD
  1, 7          |   RTMR[0]
  2~6           |   RTMR[1]
  8~15          |   RTMR[2]


It would make sense for Arm to follow the same convention. This way, FW
knows where to put new measurements. And extending this mapping, remaining
PCRs could for example all go in RTMR[3].

Verifiers and other consumers don't need to know any of these conventions,
they can just read the event log to know where each component was measured.

> Is the idea to defer that to user space, or should we also have some
> symlinks exposing this or that specific register when it exists under

I agree, it may be useful to have a single platform-agnostic link for
generic applications that need to extend measurements. For example one
RTMR could be picked by the TSM driver:

/sys/kernel/config/tsm/extend_measurement -> ./rtmr3

I'm not sure it's useful to provide a shortcut to initial_vm_state
however, because as I understand it an attestation agent just wants to
bundle all digests and send them to a verifier, something already provided
in a platform-agnostic way by configfs-tsm report/

Thanks,
Jean

> 
> One data point is that about one year ago, CoCo has already split the

---

## [23] James Bottomley — 2024-09-12
*Subject: Re: [PATCH RFC 0/3] tsm: Unified Measurement Register ABI for TVMs*

On Wed, 2024-09-11 at 22:23 -0500, Xing, Cedric wrote:
> Hi James,
> 

Well, the PCRs are already exposed through 

/sys/class/tpm/tpm0/pcr-<algo>/<n>

but they don't have much meaning without the log.

> Please note that the existing event types in the TCG2 log format are 
> predominantly BIOS/firmware-oriented, which seldom makes sense for 

And the IMA log, which is runtime and isn't TCG2?

> The proposed log format aims to provide a framework for unambiguous 
> hashing while allowing application-defined events. Its primary design

But that's my complaint.  This specification:

   - Records are lines ending with `\n`.
   - Each record (line) is hashed in its entirety (excluding the
   trailing `\n`) and extended to the RTMR.
   - The log for an RTMR is stored at
   `/sys/kernel/tsm/<MR group name>/<RTMR name>/event_log` and consists
   of these delineated records.
   - Lines that are empty (containing only `\n`) or start with `#` are
   skipped (not hashed or extended).
   
Is completely incompatible with pretty much every current log format. 
Given you have fairly elaborate decorations for the register formats,
what's the problem with simply having a decoration for the log format? 
That way you can use the above incompatible log for your purpose but this
framework can support existing logs and expand to future ones as they come
along.  All this would mean initially to the code is adding the decoration
file (easy) and ensuring that append_event is handled by a log format
specific component, allowing for expansion.

James

---

## [24] James Bottomley — 2024-09-12
*Subject: Re: [PATCH RFC 3/3] tsm: Add TVM Measurement Sample Code*

On Sat, 2024-09-07 at 23:56 -0500, Cedric Xing wrote:
> This sample kernel module demonstrates how to make MRs accessible to
> user mode

I'm not sure this is the best structure to apply to logs with multiple
banks (hash algorithms).  There needs to be a way to get the same
registers measurement for each bank, but the log should sit above that
(appending should extend all active banks)

How about

/sys/kernel/tsm/
└──<measurement type>
   ├──reg0
   │   ├── <log format>
   │   │   ├── append_event
   │   │   └── event_log
   │   ├── <hash algo>  
   │  ...  └── digest
   ...

That way it supports multiple log formats (would be the job of the log
extender to ensure compatibility) and multiple banks.

James

---

## [25] Xing, Cedric — 2024-09-12
*Subject: Re: [PATCH RFC 0/3] tsm: Unified Measurement Register ABI for TVMs*

On 9/11/2024 1:56 AM, Alexander Graf wrote:
> 
> On 11.09.24 06:01, Xing, Cedric wrote:
The intention is to make a cleaner user interface. Generally, the flat 
files contain information ready to be consumed by applications, while 
those in directories are less ready - e.g., the log may have to be 
parsed to extract the measurements of interest. In the case of TDX, 
MRCONFIGID, MROWNER, and MROWNERCONFIG are essentially 3 arbitrary 
48-byte values and would be more straightforward to be presented as 3 files.

The necessity for a log associated with any MR arises from the need to 
"share" the MR - i.e., there are more measurements than MRs and there's 
a need for those measurements to be assessed/processed individually. 
Rather than asking individual applications to parse a log, it'd be 
desirable for CC guest drivers to "unpack" the log into a set of 
"artificial" MRs consumable by applications. E.g., if a standardized 
method for conveying boot time configuration/policies to CVMs were 
established to be an array of "artificial" CCR0..CCRn (Cvm Config 
Register), a potential implementation could be to store the array within 
some static MR's log to be extracted then exposed by the CC guest driver 
as a set of flat files. This example of course doesn't mandate flat 
files. It simply showcases that there are both simple values and more 
complex data in the "measurement tree", and the idea here is to offer an 
option to differentiate them (wherever/whenever the CC guest driver sees 
fit), with the intention to simplify navigation for users and/or 
application developers.

> What if for example next-next-gen SEV-SNP suddenly gains event log 
> support for its launch digest? We would create needless churn on user 
This is a great point! I'd say, if the log was on the product road map, 
the CC guest driver should opt for a directory on day 1. Otherwise, I'd 
expect an MR name change with such a semantic shift, and the CC guest 
driver could then extract the "old" digest from the log per the original 
semantics, and present it under its original name.

Finally, I don't mean to force flat files for static MRs (I once did, 
but Jean and you have me convinced :)). It will be just an option.

-Cedric

---

## [26] Xing, Cedric — 2024-09-12
*Subject: Re: [PATCH RFC 0/3] tsm: Unified Measurement Register ABI for TVMs*

On 9/12/2024 7:15 AM, James Bottomley wrote:
> On Wed, 2024-09-11 at 22:23 -0500, Xing, Cedric wrote:
>> Hi James,
TPM predates TSM so has an existing implementation for sure.

> /sys/class/tpm/tpm0/pcr-<algo>/<n>
> 
Consolidating PCRs under TSM is not a requirement. But if it's 
desirable, it could be done. When it comes to the log, the assumption 
here is that we will switch log format after TSM takes over. The preboot 
log can stay where it is today. Yeah, it would be kinda ugly without a 
unified log, but the separation of semantics/storage is more important, 
because otherwise it will be very difficult to enable new applications.

>> Please note that the existing event types in the TCG2 log format are
>> predominantly BIOS/firmware-oriented, which seldom makes sense for
By "TCG2", I refer to the TPM PC client profile that defines the EV_* 
event types. I could be very wrong but I thought IMA content/event types 
had not been defined until CEL came along. Though both TCG2 and CEL were 
designed to be extensible, adding new event/content types would require 
revising the specs, which is a very high bar for new applications, and 
is one of the major reasons for introducing this new log format.

Regarding the IMA log, there are several options to integrate it into 
the TSM framework:

One straight forward option is to dedicate a RTMR for IMA use. This 
series allows off-log extension so nothing else (except mapping the PCR 
to the dedicated RTMR) needs changes.

The second option is to change IMA to use the new log format proposed 
here. Of course, it'd require more changes than the first option - I 
don't believe many people would like it at the moment.

The third option is "virtual measurement". We can define a virtual MR - 
say "mr_ima", to replace the current PCR. Then we back mr_ima by a real 
RTMR by logging the value extended to mr_ima. That is: when mr_ima is 
extended by value XYZ, an entry like "mr_ima extend <hash_algo>/XYZ" is 
logged to some native RTMR. Later on, the verifier can replay the RTMR 
log to calculate an mr_ima value that matches the IMA's log. This is 
actually an example of sharing an RTMR among multiple arbitrary 
applications. Events from different applications can be distinguished by 
the prefix ("mr_ima" in this example), and a layered verifier can be 
built - the bottom CC-specific layer verifies the integrity of the log 
without understanding IMA, then the top (CC-agnostic) layer verifies the 
IMA log using calculated "mr_ima" value by the bottom layer.

>> The proposed log format aims to provide a framework for unambiguous
>> hashing while allowing application-defined events. Its primary design

Unfortunately this is true, because this log format has different design 
objectives than pretty much all existing log formats. Another notable 
difference is this ABI is log oriented, vs. most existing log formats 
are digest oriented. A log oriented design allows applications to 
generate identical logs regardless of the underlying CC arch.

> Given you have fairly elaborate decorations for the register formats,
> what's the problem with simply having a decoration for the log format?
Using CEL terms, ELCD (Event Log Critical Data) could be easily 
encapsulated in both TCG2 and CEL, but ELID (Event Log Informative Data 
- i.e., lines starting with '#') is not. One use of ELID is to support 
off-log extension, designed to help migrating existing applications. The 
`SYNC` lines (necessary after off-log extensions, see Patch 2 for 
details) would also require special treatments from the verifier. 
Therefore, converting this log to a TCG2 or CEL log is NOT always 
doable. It'll be better to convert log format only when needed (and 
before any off-log extensions have been done).

-Cedric

---

## [27] Alexander Graf — 2024-09-13
*Subject: Re: [PATCH RFC 0/3] tsm: Unified Measurement Register ABI for TVMs*

On 12.09.24 17:43, Xing, Cedric wrote:
>
> On 9/11/2024 1:56 AM, Alexander Graf wrote:


I don't follow your argumentation line. Let's look at the SEV-SNP launch 
digest. It calculates its "launch digest" hash based on

* Initial page hashes
* Initial VMSA state for vCPUs

Today that means that when you spawn a VM with multiple vCPUs, your 
launch digest differs. With an event log, SNP could give you individual 
operations that make up the launch digest so you can validate

* memory content is what I want
* vCPU0 state is what I want
* vCPUn state is what I want

while staying completely flexible to the number of initial vCPUs.


Another example: Nitro Enclaves PCRs [1]. While we try hard to not 
conflate too many fields into a single PCR, we some times still do. PCR1 
for example contains kernel as well as "first initramfs". Maybe you want 
to actually have different policies on each of those. Maybe you want to 
allow 5 different kernels and 3 different "initial initramfs version" in 
any permutation.

Again, you would need an event log to get that.

So even when what we call "boot measurements" are only consumed as final 
hashes today, there could absolutely be value in an event log for them. 
Since you are proposing a generic mechanism to expose registers + logs, 
I still fail to see why we would treat boot measurements different from 
runtime measurements.


>
>> What if for example next-next-gen SEV-SNP suddenly gains event log


The great thing about product road maps is that they keep changing. 
You're building a generic ABI for user space here that should be able to 
be flexible enough to survive for the next 10-20 years. You can't assume 
you know everything already.


> expect an MR name change with such a semantic shift, and the CC guest


There is no semantic shift. In the SNP case, we'd still be talking about 
the exact same launch digest, just that now we would also learn sub-hash 
information.


> driver could then extract the "old" digest from the log per the original
> semantics, and present it under its original name.


I think even allowing flat files in a world where you already identified 
multiple uses for a directory structure for objects of similar semantic 
is just a bad idea and will lead to pain down the road :)


Alex

[1] https://docs.aws.amazon.com/enclaves/latest/user/set-up-attestation.html





Amazon Web Services Development Center Germany GmbH
Krausenstr. 38
10117 Berlin
Geschaeftsfuehrung: Christian Schlaeger, Jonathan Weiss
Eingetragen am Amtsgericht Charlottenburg unter HRB 257764 B
Sitz: Berlin
Ust-ID: DE 365 538 597

---

## [28] James Bottomley — 2024-09-13
*Subject: Re: [PATCH RFC 0/3] tsm: Unified Measurement Register ABI for TVMs*

On Thu, 2024-09-12 at 14:00 -0500, Xing, Cedric wrote:
> On 9/12/2024 7:15 AM, James Bottomley wrote:
> > On Wed, 2024-09-11 at 22:23 -0500, Xing, Cedric wrote:

As I keep saying I'm not expecting you to do it.  However, it will be a
requirement for consolidating AMD SNP under this using the SVSM-vTPM,
so I do expect someone will do it.

>  But if it's desirable, it could be done. When it comes to the log,
> the assumption here is that we will switch log format after TSM takes

I really don't think you'd want to do that because it creates a bigger
mess for all the tools if you keep using the same PCRs because now they
have to know where the log switches and how to change the extensions. 
There's no tool today that can do this.


> > > Please note that the existing event types in the TCG2 log format
> > > are predominantly BIOS/firmware-oriented, which seldom makes

The IMA log has always been defined in 

Documentation/security/IMA-templates

Even before CEL tried to add it as a format.

>  Though both TCG2 and CEL were designed to be extensible, adding new
> event/content types would require revising the specs, which is a very

I don't see how that would help:  From the IMA point of view there's no
practical difference between extending a PCR and extending a RTMR (it's
the same mathematical operation).  The difference is how you get the
quote and verify the log matches it.

I do note that since the whole problem boils down to the different
quoting mechanism between TPM and RTMR, it is entirely possible, since
the Quoting Enclave is all in software, for them to produce a TPM quote
even for RTMR measurements that could be verified against some external
key.  That way all the IMA tools would just work for RTMRs (which would
seem to me to be a much easier way of getting them to work with RTMRs).
It's always baffled me why Intel is so adamant that every existing
measurement tool and pathway should be rewritten for the RTMR approach
instead of simply being compatible enough to get existing tools to work
with RTMRs.  You can still keep the current RTMR quote format and the
certificate chain, simply add the ability to produce a signature that
matches the usual TPM quote.  Since a quote is only a signature over a
public key, the tools would work and the only difference is how you
confirm the certificate chain.

> The second option is to change IMA to use the new log format proposed
> here. Of course, it'd require more changes than the first option - I 

I think that's true, yes.  And that's precisely the problem with this
proposal: you're completely pejorative about log format but know that
no-one is going to change to the format you're trying to mandate.

> The third option is "virtual measurement". We can define a virtual MR
> - 

But this sounds even worse.  You're adding an extra layer and an extra
logging tool simply to verify the PCR/RTMR quote and then after that
you need to us IMA tools to verify the log.

James

---

## [29] James Bottomley — 2024-09-13
*Subject: Re: [PATCH RFC 0/3] tsm: Unified Measurement Register ABI for TVMs*

On Thu, 2024-09-12 at 14:00 -0500, Xing, Cedric wrote:
> On 9/12/2024 7:15 AM, James Bottomley wrote:
> > On Wed, 2024-09-11 at 22:23 -0500, Xing, Cedric wrote:
[...]
> > > The proposed log format aims to provide a framework for
> > > unambiguous hashing while allowing application-defined events.

So you're saying in order to get this to work successfully you have to
design a better log.  I'm afraid I now have to quote xkcd 927 to you:

https://xkcd.com/927/

> > Given you have fairly elaborate decorations for the register
> > formats, what's the problem with simply having a decoration for the

You seem to be hung up on requiring a single log format.  That horse
left the stable decades ago and isn't coming back (the CEL attempt to
corral it was ultimately not successful).  I'm saying we accept that
fact and simply expose and extend logs in whatever format they exist in
today without forcing them to change.  I proposed a mechanism for doing
that here:

https://lore.kernel.org/linux-coco/86e6659bc8dd135491dc34bdb247caf05d8d2ad8.camel@HansenPartnership.com/

Which seems like it would work with pretty much every current
measurement tool (with minor modifications to change a few paths) and
even allow you to add your new log format if you insist.

Regards,

James

---

## [30] Xing, Cedric — 2024-09-13
*Subject: Re: [PATCH RFC 0/3] tsm: Unified Measurement Register ABI for TVMs*

On 9/12/2024 5:03 AM, Christophe de Dinechin wrote:
> 
> 

But if we dig deeper, a conventions will be difficult to establish 
because different users/tenants/applications have different needs in 
passing configurations/policies (or additional whatever). A more generic 
model is to allow upper layer software to specify arbitrary number of 
measurements in the form of name/value pairs. For example, say `rim` is 
the only static MR on Arm but the tenant wants to pass in a policy file 
along with the tenant's public key. We could put the following 2 lines 
into rim's log (more like a manifest because the MR is static):

	kernel.org/tsm/static_mr mr_policy <policy digest>
	kernel.org/tsm/static_mr mr_pubkey <public key digest>

Then, assuming Arm CCA guest driver also understands the log format 
above, it would create 2 virtual/pseudo-MRs, namely `mr_policy` and 
`mr_pubkey`, to expose those digests to applications.

Then say, if the tenant wants the same application to run on Intel TDX, 
whose MRTD doesn't support the same semantics as rim, MROWNERCONFIG 
could be used instead - the same log entries but for MROWNERCONFIG this 
time. The TDX guest would then create the same `mr_policy` and 
`mr_pubkey` for those same applications to consume. Please note that 
those applications are CC arch agnostic (at source level).

During attestation/verification, the verifier is supposed to consist of 
a buttom (CC arch specific) layer and a top (CC arch agnostic) layer. 
The bottom would verify the integrity of the log using different MRs 
(rim on Arm CCA or MROWNERCONFIG on Intel TDX), then the top layer would 
extract and verify `mr_policy`/`mr_pubkey` against the reference values 
set forth by the tenant.

> It looks to me like this could simplify the writing of user-space
> attestation agents, for example. But then, maybe I’m too optimistic
I believe portable (CC arch agnostic) applications can be done, but 
there's still some way to go.

-Cedric

---

## [31] Xing, Cedric — 2024-09-14
*Subject: Re: [PATCH RFC 3/3] tsm: Add TVM Measurement Sample Code*

On 9/12/2024 7:28 AM, James Bottomley wrote:
> On Sat, 2024-09-07 at 23:56 -0500, Cedric Xing wrote:
>> This sample kernel module demonstrates how to make MRs accessible to
I have considered this before. But I'm not sure how to (define/describe 
criteria to) match an MR with its log format. Also, MRs are arch 
dependent and may also vary from gen to gen. I'm afraid this might bring 
in more chaos than order.

-Cedric

---

## [32] James Bottomley — 2024-09-14
*Subject: Re: [PATCH RFC 3/3] tsm: Add TVM Measurement Sample Code*

On Sat, 2024-09-14 at 11:36 -0500, Xing, Cedric wrote:
> On 9/12/2024 7:28 AM, James Bottomley wrote:
> > On Sat, 2024-09-07 at 23:56 -0500, Cedric Xing wrote:

This is already defined for every existing log format ... why would you
have to define it again?

>  Also, MRs are arch dependent and may also vary from gen to gen. I'm
> afraid this might bring in more chaos than order.

I think I understand this. All measurement registers are simply
equivalent to PCRs in terms of the mathematical definition of how they
extend.  Exactly what measurements go into a PCR and how they are
logged is defined in various standards.  The TCG ones are fairly fixed
now, but if Intel wants to keep redefining the way its measurements
work, the logical thing to do is tie this to a version number and make
measuring the version the first log entry so the tools know how to
differentiate.

James

---

## [33] Xing, Cedric — 2024-09-14
*Subject: Re: [PATCH RFC 0/3] tsm: Unified Measurement Register ABI for TVMs*

On 9/13/2024 7:55 AM, James Bottomley wrote:
> On Thu, 2024-09-12 at 14:00 -0500, Xing, Cedric wrote:
>> By "TCG2", I refer to the TPM PC client profile that defines the EV_*
We are on the same page. The TCG PC client profile spec didn't define 
IMA specific events. So IMA invented its own, and then was included into 
CEL.

>>   Though both TCG2 and CEL were designed to be extensible, adding new
>> event/content types would require revising the specs, which is a very
There's significant difference in the trust model betweem TPM and CC 
TEEs. Specifically, in the TPM case the CRTM (usually the BIOS boot 
block) is simply trusted, while in the case of CC TEEs the CRTM (pretty 
much equivalent to the initial memory image) is measured. Additionally, 
TPM is soldered to a physical platform while TEEs can be migrated from 
platform to platform. Moreover, certain TEE implementations, like Intel 
TDX, rely on additional modules for security (e.g., TDX module, SEAM 
loader ACM, microcode), and some of those can be updated without 
rebooting (i.e., without tearing down TDs). Therefore, a "full" TD quote 
(which is still a work in progress) will have to convey more evidence 
than the current TPM quote format can possibly accommodate. That is, 
even if the Quoting Enclave (or Quoting TD in future) can sign a TPM 
quote (e.g., by striping off everything other than RTMRs), an 
attestation service would still have to verify/appraise other evidence 
conveyed outside of the TPM quote to establish trust in the TPM quote. I 
believe there are similar problems in other CC archs/implementations.

>> The second option is to change IMA to use the new log format proposed
>> here. Of course, it'd require more changes than the first option - I
I'm not trying to mandate the format. I presented this option briefly to 
show that I had considered all possibilities. Also, see my response to 
your comment on the 3rd option below.

>> The third option is "virtual measurement". We can define a virtual MR
>> -
We are facing a challenge similar to what the TCP/IP stack solved many 
years ago. Think of it like this: the IMA log is the "application 
layer", where the actual data resides. The specific record syntax/format 
in the example (i.e., "ima_mr extend <hash_algo>/XYZ") acts like TCP, 
with `mr_ima` being a "TCP port". The rules introduced in this series 
for identifying event record boundaries and hashing, serve as the "link 
layer" to provide data integrity. The ultimate objective of this 
"layered measurement/attestation stack" is to allow multiple 
applications to share the same physical RTMR without interfering with 
each other.

Just as the TCP/IP stack requires different layers to handle various 
aspects of data communication, this approach do require additional 
tools, especially on the "attestation service" side. Given that we are 
just laying the groundwork, I believe the first option will have the 
least impact to existing s/w and will suffice for now.

-Cedric

---

## [34] Xing, Cedric — 2024-09-14
*Subject: Re: [PATCH RFC 3/3] tsm: Add TVM Measurement Sample Code*

On 9/14/2024 12:10 PM, James Bottomley wrote:
> On Sat, 2024-09-14 at 11:36 -0500, Xing, Cedric wrote:
>> I have considered this before. But I'm not sure how to
I’m not sure if I understand this correctly. Are you suggesting we 
continue using the event definitions from the existing TCG specs with 
just a simple RTMR-to-PCR map? That’s exactly the issue we’re trying to 
address. The current specs don’t cover new applications. For example, 
how to describe the event of launching a container measured to a 
specific SHA-256 digest in CoCo? Defining new event types would require 
revising the specs, which is a high barrier for most applications. While 
TPM has been widely adopted, its use has been mostly limited to pre-boot 
scenarios. The lack of OS applications leveraging TPM is partly due to 
this limitation IMHO.

---

## [35] Xing, Cedric — 2024-09-15
*Subject: Re: [PATCH RFC 0/3] tsm: Unified Measurement Register ABI for TVMs*

On 9/13/2024 7:58 AM, James Bottomley wrote:
> On Thu, 2024-09-12 at 14:00 -0500, Xing, Cedric wrote:
>> Unfortunately this is true, because this log format has different
I read that long time ago. Really a great article!

Am I defining a new log format? Well, yes and no. I hope my response to 
another email from you could be helpful.

My intention is to separate semantics from storage of logs. So yes, I'm 
defining a new format for storing event records. But no, I'm not trying 
to impose any specific semantics. In fact, with the shared storage 
layer, we will be able to support a diverse range of semantics from 
various applications with just a single RTMR.

>> Using CEL terms, ELCD (Event Log Critical Data) could be easily
>> encapsulated in both TCG2 and CEL, but ELID (Event Log Informative

Can't agree more.

Therefore, to allow even more log formats (semantics), a common storage 
layer is desired to allow event records of different semantics to be 
mixed and separated at the same time. This is like a filesystem, on 
which data from different applications are mixed (on the block device) 
but still separated (at the file level).

-Cedric

---

## [36] Mikko Ylinen — 2024-10-24
*Subject: Re: [PATCH RFC 3/3] tsm: Add TVM Measurement Sample Code*

On Sat, Sep 14, 2024 at 01:10:33PM -0400, James Bottomley wrote:
> On Sat, 2024-09-14 at 11:36 -0500, Xing, Cedric wrote:
> 

Given this, would it be reasonable to go back to the digest based
input ABI idea where user space would use the TSM provider specifc
hash algo to prepare the input? The kernel eventlog for each MR (or
some notification mechanism to user space) would be provided just to
keep the digest ordering. Apps would map their inputs to that digest
list when doing attestation (in whatever format they choose).

On that note, we have the CCC kernel SIG call again Friday this week. If
we get enough people interested in this topic on the call, we could
brainstorm this a bit further.

-- Regards, Mikko

---
