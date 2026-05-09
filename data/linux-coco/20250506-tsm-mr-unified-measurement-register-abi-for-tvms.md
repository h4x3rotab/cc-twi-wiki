---
title: 'tsm-mr: Unified Measurement Register ABI for TVMs'
date: 2025-05-06
last_reply: 2025-05-06
message_count: 8
participants: ['Cedric Xing']
---

## [1] Cedric Xing — 2025-05-06

NOTE: This patch series introduces the Measurement Register (MR) ABI, and
is a continuation of the RFC series on the same topic [1].

Introduce the CONFIG_TSM_MEASUREMENTS helper library (tsm-mr) as a
cross-vendor transport schema to allow TVM (TEE VM) guest drivers to export
CC (Confidential Compute) architecture-specific MRs (Measurement Registers)
as sysfs attributes/files. Enable applications to read, write/extend MRs
like regular files, supporting various usages such as configuration
verification (e.g., verify a TVM's configuration against digests stored in
static/immutable MRs like MRCONFIGID on TDX or HOSTDATA on SEV) and runtime
measurements (e.g., extend the measurement of a container image to an RTMR
before running it).

Patches included in this series:

- Patch 1 adds the tsm-mr library to help TVM guest drivers exposing MRs as
  sysfs attributes.
- Patch 2 provides a sample module demonstrating the usage of the new
  tsm-mr library.
- The remaining patches update the TDX guest driver to expose TDX MRs with
  the help of the tsm-mr library.

[1]: https://lore.kernel.org/linux-coco/20241210-tsm-rtmr-v3-0-5997d4dbda73@intel.com/

---
Changes in v6:
- tsm-mr: Rename MR root directory name to "measurements" for improved
  clarity.
- tsm-mr: Drop @mr from the parameter list of tsm_measurements.refresh().
- tsm-mr-sample: Remove redundant debug messages following the introduction
  of tracepoints.
- tdx-guest: Split and refactor changes into 3 separate commits for easier
  review.
- Add collected "Acked-by" tags to respective commits.
- Link to v5: https://lore.kernel.org/r/20250424-tdx-rtmr-v5-0-4fe28ddf85d4@intel.com

Changes in v5:
- tsm-mr: Fix typo in MAINTAINERS.
- tsm-mr-sample: Fix Kconfig dependencies by adding `select VIRT_DRIVERS`.
- Link to v4: https://lore.kernel.org/r/20250414-tdx-rtmr-v4-0-7edfa8d98716@intel.com

Changes in v4:
- tsm-mr: Add details to ABI doc.
- tsm-mr: Add driver-api doc.
- tsm-mr: Add tracepoints.
- tsm-mr: Use the constant string "mr" as the group/directory name for MR
  sysfs attributes.
- x86/tdx: Revise error codes returned by tdx_mcall_* functions.
- tdx-guest: Merge all TDREPORT code paths into a common function.
- Link to v3: https://lore.kernel.org/r/20250407-tdx-rtmr-v3-0-54f17bc65228@intel.com

Changes in v3:
- tsm-mr: Separate measurement support (tsm-mr) from the original tsm
  source code. Modules depending on tsm-mr should `select TSM_MEASUREMENTS`
  in Kconfig. (Dan Williams)
- tsm-mr: Revise tsm-mr APIs to allow callers to decide where to host the
  MR attributes in sysfs.
- tsm-mr: Drop TSM_MR_F_EXTENSIBLE and route all "write" requests to the CC
  guest driver, which decides how to handle writes (e.g., by extending the
  buffer on input to the specified MR).
- tsm-mr: Update the naming pattern for MR attributes from
  MRNAME/HASH/digest to MRNAME:HASH.
- tsm-mr: Drop TSM_MR_MAXBANKS kernel config.
- x86/tdx: Return -EBUSY from tdx_mcall_get_report0 on TDCALL_OPERAND_BUSY
  error.
- tdx-guest: Move MR attributes from /sys/kernel/tsm/tdx/ to
  /sys/class/misc/tdx_guest/ because MR names are architecture-specific, so
  their attributes should reside in an architecture-specific location.
- tdx-guest: Remove hash from `mrconfigid`, `mrowner`, `mrownerconfig`.
- tdx-guest: Remove `servtd_hash`, `report0`, and `reportdata`.
- Link to v2: https://lore.kernel.org/r/20250223-tdx-rtmr-v2-0-f2d85b0a5f94@intel.com

Changes in v2:
- Added TSM_MR_MAXBANKS Kconfig option
- Updated Kconfig dependency for TSM_REPORTS
- Updated comments in include/linux/tsm.h
- Updated drivers/virt/coco/tdx-guest/tdx-guest.c to use `IS_BUILTIN()` for
  determining if static buffer addresses can be converted to GPAs by
  `virt_to_phys()`
- Renamed function `tdx_mcall_rtmr_extend()` -> `tdx_mcall_extend_rtmr()`
- Link to v1: https://lore.kernel.org/r/20250212-tdx-rtmr-v1-0-9795dc49e132@intel.com

---
Cedric Xing (7):
      tsm-mr: Add TVM Measurement Register support
      tsm-mr: Add tsm-mr sample code
      x86/tdx: Add tdx_mcall_extend_rtmr() interface
      x86/tdx: tdx_mcall_get_report0: Return -EBUSY on TDCALL_OPERAND_BUSY error
      virt: tdx-guest: Expose TDX MRs as sysfs attributes
      virt: tdx-guest: Refactor and streamline TDREPORT generation
      virt: tdx-guest: Transition to scoped_cond_guard for mutex operations

 .../testing/sysfs-devices-virtual-misc-tdx_guest   |  63 ++++++
 Documentation/driver-api/coco/index.rst            |  12 +
 .../driver-api/coco/measurement-registers.rst      |  12 +
 Documentation/driver-api/index.rst                 |   1 +
 MAINTAINERS                                        |   7 +-
 arch/x86/coco/tdx/tdx.c                            |  50 +++-
 arch/x86/include/asm/shared/tdx.h                  |   1 +
 arch/x86/include/asm/tdx.h                         |   2 +
 drivers/virt/coco/Kconfig                          |   5 +
 drivers/virt/coco/Makefile                         |   1 +
 drivers/virt/coco/tdx-guest/Kconfig                |   1 +
 drivers/virt/coco/tdx-guest/tdx-guest.c            | 251 ++++++++++++++-------
 drivers/virt/coco/tsm-mr.c                         | 248 ++++++++++++++++++++
 include/linux/tsm-mr.h                             |  89 ++++++++
 include/trace/events/tsm_mr.h                      |  80 +++++++
 samples/Kconfig                                    |  11 +
 samples/Makefile                                   |   1 +
 samples/tsm-mr/Makefile                            |   2 +
 samples/tsm-mr/tsm_mr_sample.c                     | 131 +++++++++++
 19 files changed, 881 insertions(+), 87 deletions(-)
---
base-commit: 92a09c47464d040866cf2b4cd052bc60555185fb
change-id: 20250209-tdx-rtmr-255479667146

Best regards,

---

## [2] Cedric Xing — 2025-05-06
*Subject: [PATCH v6 1/7] tsm-mr: Add TVM Measurement Register support*

Introduce new TSM Measurement helper library (tsm-mr) for TVM guest drivers
to expose MRs (Measurement Registers) as sysfs attributes, with Crypto
Agility support.

Add the following new APIs (see include/linux/tsm-mr.h for details):

- tsm_mr_create_attribute_group(): Take on input a `struct
  tsm_measurements` instance, which includes one `struct
  tsm_measurement_register` per MR with properties like `TSM_MR_F_READABLE`
  and `TSM_MR_F_WRITABLE`, to determine the supported operations and create
  the sysfs attributes accordingly. On success, return a `struct
  attribute_group` instance that will typically be included by the guest
  driver into `miscdevice.groups` before calling misc_register().

- tsm_mr_free_attribute_group(): Free the memory allocated to the attrubute
  group returned by tsm_mr_create_attribute_group().

tsm_mr_create_attribute_group() creates one attribute for each MR, with
names following this pattern:

        MRNAME[:HASH]

- MRNAME - Placeholder for the MR name, as specified by
  `tsm_measurement_register.mr_name`.
- :HASH - Optional suffix indicating the hash algorithm associated with
  this MR, as specified by `tsm_measurement_register.mr_hash`.

Support Crypto Agility by allowing multiple definitions of the same MR
(i.e., with the same `mr_name`) with distinct HASH algorithms.

NOTE: Crypto Agility, introduced in TPM 2.0, allows new hash algorithms to
be introduced without breaking compatibility with applications using older
algorithms. CC architectures may face the same challenge in the future,
needing new hashes for security while retaining compatibility with older
hashes, hence the need for Crypto Agility.

Signed-off-by: Cedric Xing <cedric.xing@intel.com>
Reviewed-by: Dan Williams <dan.j.williams@intel.com>
Acked-by: Dionna Amalie Glaze <dionnaglaze@google.com>
---
 Documentation/driver-api/coco/index.rst            |  12 +
 .../driver-api/coco/measurement-registers.rst      |  12 +
 Documentation/driver-api/index.rst                 |   1 +
 MAINTAINERS                                        |   5 +-
 drivers/virt/coco/Kconfig                          |   5 +
 drivers/virt/coco/Makefile                         |   1 +
 drivers/virt/coco/tsm-mr.c                         | 248 +++++++++++++++++++++
 include/linux/tsm-mr.h                             |  89 ++++++++
 include/trace/events/tsm_mr.h                      |  80 +++++++
 9 files changed, 451 insertions(+), 2 deletions(-)

diff --git a/Documentation/driver-api/coco/index.rst b/Documentation/driver-api/coco/index.rst
new file mode 100644
index 0000000000000000000000000000000000000000..af9f08ca0cfd3ef920c49fa48b620cd4a0afb7f3
--- /dev/null
+++ b/Documentation/driver-api/coco/index.rst
@@ -0,0 +1,12 @@
+.. SPDX-License-Identifier: GPL-2.0
+
+======================
+Confidential Computing
+======================
+
+.. toctree::
+   :maxdepth: 1
+
+   measurement-registers
+
+.. only::  subproject and html
diff --git a/Documentation/driver-api/coco/measurement-registers.rst b/Documentation/driver-api/coco/measurement-registers.rst
new file mode 100644
index 0000000000000000000000000000000000000000..cef85945a9a74849dfec4fdc709bc72d4a595356
--- /dev/null
+++ b/Documentation/driver-api/coco/measurement-registers.rst
@@ -0,0 +1,12 @@
+.. SPDX-License-Identifier: GPL-2.0
+.. include:: <isonum.txt>
+
+=====================
+Measurement Registers
+=====================
+
+.. kernel-doc:: include/linux/tsm-mr.h
+   :internal:
+
+.. kernel-doc:: drivers/virt/coco/tsm-mr.c
+   :export:
diff --git a/Documentation/driver-api/index.rst b/Documentation/driver-api/index.rst
index 16e2c4ec3c010bd751c94978b6c8ae1fc7cb205d..3e2a270bd82826cd78ffc6f18214fdbde151a36a 100644
--- a/Documentation/driver-api/index.rst
+++ b/Documentation/driver-api/index.rst
@@ -81,6 +81,7 @@ Subsystem-specific APIs
    acpi/index
    backlight/lp855x-driver.rst
    clk
+   coco/index
    console
    crypto/index
    dmaengine/index
diff --git a/MAINTAINERS b/MAINTAINERS
index 69511c3b2b76fb7090a2a550f4c59a7daf188493..5d36823d26b28797c1186e7df1eb4d2da612f51c 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -24648,8 +24648,9 @@ M:	Dan Williams <dan.j.williams@intel.com>
 L:	linux-coco@lists.linux.dev
 S:	Maintained
 F:	Documentation/ABI/testing/configfs-tsm
-F:	drivers/virt/coco/tsm.c
-F:	include/linux/tsm.h
+F:	Documentation/driver-api/coco/
+F:	drivers/virt/coco/tsm*.c
+F:	include/linux/tsm*.h
 
 TRUSTED SERVICES TEE DRIVER
 M:	Balint Dobszay <balint.dobszay@arm.com>
diff --git a/drivers/virt/coco/Kconfig b/drivers/virt/coco/Kconfig
index ff869d883d954b809939e1b2aaf412d80d2263a9..737106d5dcbce5127c68a003a67c7aa5d3a0b653 100644
--- a/drivers/virt/coco/Kconfig
+++ b/drivers/virt/coco/Kconfig
@@ -7,6 +7,11 @@ config TSM_REPORTS
 	select CONFIGFS_FS
 	tristate
 
+config TSM_MEASUREMENTS
+	select CRYPTO_HASH_INFO
+	select CRYPTO
+	bool
+
 source "drivers/virt/coco/efi_secret/Kconfig"
 
 source "drivers/virt/coco/pkvm-guest/Kconfig"
diff --git a/drivers/virt/coco/Makefile b/drivers/virt/coco/Makefile
index c3d07cfc087ecf004d0ed4e50755c8557e8c01b2..eb6ec5c1d2e17427ebf83891c57cc723b8c8d660 100644
--- a/drivers/virt/coco/Makefile
+++ b/drivers/virt/coco/Makefile
@@ -3,6 +3,7 @@
 # Confidential computing related collateral
 #
 obj-$(CONFIG_TSM_REPORTS)	+= tsm.o
+obj-$(CONFIG_TSM_MEASUREMENTS)	+= tsm-mr.o
 obj-$(CONFIG_EFI_SECRET)	+= efi_secret/
 obj-$(CONFIG_ARM_PKVM_GUEST)	+= pkvm-guest/
 obj-$(CONFIG_SEV_GUEST)		+= sev-guest/
diff --git a/drivers/virt/coco/tsm-mr.c b/drivers/virt/coco/tsm-mr.c
new file mode 100644
index 0000000000000000000000000000000000000000..d75b08548292e5c8ad424a1198c28b52a88d4f83
--- /dev/null
+++ b/drivers/virt/coco/tsm-mr.c
@@ -0,0 +1,248 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/* Copyright(c) 2024-2025 Intel Corporation. All rights reserved. */
+
+#define pr_fmt(fmt) KBUILD_MODNAME ": " fmt
+
+#include <linux/module.h>
+#include <linux/slab.h>
+#include <linux/sysfs.h>
+
+#define CREATE_TRACE_POINTS
+#include <trace/events/tsm_mr.h>
+
+/*
+ * struct tm_context - contains everything necessary to implement sysfs
+ * attributes for MRs.
+ * @rwsem: protects the MR cache from concurrent access.
+ * @agrp: contains all MR attributes created by tsm_mr_create_attribute_group().
+ * @tm: input to tsm_mr_create_attribute_group() containing MR definitions/ops.
+ * @in_sync: %true if MR cache is up-to-date.
+ * @mrs: array of &struct bin_attribute, one for each MR.
+ *
+ * This internal structure contains everything needed to implement
+ * tm_digest_read() and tm_digest_write().
+ *
+ * Given tm->refresh() is potentially expensive, tm_digest_read() caches MR
+ * values and calls tm->refresh() only when necessary. Only live MRs (i.e., with
+ * %TSM_MR_F_LIVE set) can trigger tm->refresh(), while others are assumed to
+ * retain their values from the last tm->write(). @in_sync tracks if there have
+ * been tm->write() calls since the last tm->refresh(). That is, tm->refresh()
+ * will be called only when a live MR is being read and the cache is stale
+ * (@in_sync is %false).
+ *
+ * tm_digest_write() sets @in_sync to %false and calls tm->write(), whose
+ * semantics is arch and MR specific. Most (if not all) writable MRs support the
+ * extension semantics (i.e., tm->write() extends the input buffer into the MR).
+ */
+struct tm_context {
+	struct rw_semaphore rwsem;
+	struct attribute_group agrp;
+	const struct tsm_measurements *tm;
+	bool in_sync;
+	struct bin_attribute mrs[];
+};
+
+static ssize_t tm_digest_read(struct file *filp, struct kobject *kobj,
+			      const struct bin_attribute *attr, char *buffer,
+			      loff_t off, size_t count)
+{
+	struct tm_context *ctx;
+	const struct tsm_measurement_register *mr;
+	int rc;
+
+	ctx = attr->private;
+	rc = down_read_interruptible(&ctx->rwsem);
+	if (rc)
+		return rc;
+
+	mr = &ctx->tm->mrs[attr - ctx->mrs];
+
+	/*
+	 * @ctx->in_sync indicates if the MR cache is stale. It is a global
+	 * instead of a per-MR flag for simplicity, as most (if not all) archs
+	 * allow reading all MRs in oneshot.
+	 *
+	 * ctx->refresh() is necessary only for LIVE MRs, while others retain
+	 * their values from their respective last ctx->write().
+	 */
+	if ((mr->mr_flags & TSM_MR_F_LIVE) && !ctx->in_sync) {
+		up_read(&ctx->rwsem);
+
+		rc = down_write_killable(&ctx->rwsem);
+		if (rc)
+			return rc;
+
+		if (!ctx->in_sync) {
+			rc = ctx->tm->refresh(ctx->tm);
+			ctx->in_sync = !rc;
+			trace_tsm_mr_refresh(mr, rc);
+		}
+
+		downgrade_write(&ctx->rwsem);
+	}
+
+	memcpy(buffer, mr->mr_value + off, count);
+	trace_tsm_mr_read(mr);
+
+	up_read(&ctx->rwsem);
+	return rc ?: count;
+}
+
+static ssize_t tm_digest_write(struct file *filp, struct kobject *kobj,
+			       const struct bin_attribute *attr, char *buffer,
+			       loff_t off, size_t count)
+{
+	struct tm_context *ctx;
+	const struct tsm_measurement_register *mr;
+	ssize_t rc;
+
+	/* partial writes are not supported */
+	if (off != 0 || count != attr->size)
+		return -EINVAL;
+
+	ctx = attr->private;
+	mr = &ctx->tm->mrs[attr - ctx->mrs];
+
+	rc = down_write_killable(&ctx->rwsem);
+	if (rc)
+		return rc;
+
+	rc = ctx->tm->write(ctx->tm, mr, buffer);
+
+	/* mark MR cache stale */
+	if (!rc) {
+		ctx->in_sync = false;
+		trace_tsm_mr_write(mr, buffer);
+	}
+
+	up_write(&ctx->rwsem);
+	return rc ?: count;
+}
+
+/**
+ * tsm_mr_create_attribute_group() - creates an attribute group for measurement
+ * registers (MRs)
+ * @tm: pointer to &struct tsm_measurements containing the MR definitions.
+ *
+ * This function creates attributes corresponding to the MR definitions
+ * provided by @tm->mrs.
+ *
+ * The created attributes will reference @tm and its members. The caller must
+ * not free @tm until after tsm_mr_free_attribute_group() is called.
+ *
+ * Context: Process context. May sleep due to memory allocation.
+ *
+ * Return:
+ * * On success, the pointer to a an attribute group is returned; otherwise
+ * * %-EINVAL - Invalid MR definitions.
+ * * %-ENOMEM - Out of memory.
+ */
+const struct attribute_group *
+tsm_mr_create_attribute_group(const struct tsm_measurements *tm)
+{
+	size_t nlen;
+
+	if (!tm || !tm->mrs)
+		return ERR_PTR(-EINVAL);
+
+	/* aggregated length of all MR names */
+	nlen = 0;
+	for (size_t i = 0; i < tm->nr_mrs; ++i) {
+		if ((tm->mrs[i].mr_flags & TSM_MR_F_LIVE) && !tm->refresh)
+			return ERR_PTR(-EINVAL);
+
+		if ((tm->mrs[i].mr_flags & TSM_MR_F_WRITABLE) && !tm->write)
+			return ERR_PTR(-EINVAL);
+
+		if (!tm->mrs[i].mr_name)
+			return ERR_PTR(-EINVAL);
+
+		if (tm->mrs[i].mr_flags & TSM_MR_F_NOHASH)
+			continue;
+
+		if (tm->mrs[i].mr_hash >= HASH_ALGO__LAST)
+			return ERR_PTR(-EINVAL);
+
+		/* MR sysfs attribute names have the form of MRNAME:HASH */
+		nlen += strlen(tm->mrs[i].mr_name) + 1 +
+			strlen(hash_algo_name[tm->mrs[i].mr_hash]) + 1;
+	}
+
+	/*
+	 * @bas and the MR name strings are combined into a single allocation
+	 * so that we don't have to free MR names one-by-one in
+	 * tsm_mr_free_attribute_group()
+	 */
+	struct bin_attribute **bas __free(kfree) =
+		kzalloc(sizeof(*bas) * (tm->nr_mrs + 1) + nlen, GFP_KERNEL);
+	struct tm_context *ctx __free(kfree) =
+		kzalloc(struct_size(ctx, mrs, tm->nr_mrs), GFP_KERNEL);
+	char *name, *end;
+
+	if (!ctx || !bas)
+		return ERR_PTR(-ENOMEM);
+
+	/* @bas is followed immediately by MR name strings */
+	name = (char *)&bas[tm->nr_mrs + 1];
+	end = name + nlen;
+
+	for (size_t i = 0; i < tm->nr_mrs; ++i) {
+		bas[i] = &ctx->mrs[i];
+		sysfs_bin_attr_init(bas[i]);
+
+		if (tm->mrs[i].mr_flags & TSM_MR_F_NOHASH)
+			bas[i]->attr.name = tm->mrs[i].mr_name;
+		else if (name < end) {
+			bas[i]->attr.name = name;
+			name += snprintf(name, end - name, "%s:%s",
+					 tm->mrs[i].mr_name,
+					 hash_algo_name[tm->mrs[i].mr_hash]);
+			++name;
+		} else
+			return ERR_PTR(-EINVAL);
+
+		/* check for duplicated MR definitions */
+		for (size_t j = 0; j < i; ++j)
+			if (!strcmp(bas[i]->attr.name, bas[j]->attr.name))
+				return ERR_PTR(-EINVAL);
+
+		if (tm->mrs[i].mr_flags & TSM_MR_F_READABLE) {
+			bas[i]->attr.mode |= 0444;
+			bas[i]->read_new = tm_digest_read;
+		}
+
+		if (tm->mrs[i].mr_flags & TSM_MR_F_WRITABLE) {
+			bas[i]->attr.mode |= 0200;
+			bas[i]->write_new = tm_digest_write;
+		}
+
+		bas[i]->size = tm->mrs[i].mr_size;
+		bas[i]->private = ctx;
+	}
+
+	if (name != end)
+		return ERR_PTR(-EINVAL);
+
+	init_rwsem(&ctx->rwsem);
+	ctx->agrp.name = "measurements";
+	ctx->agrp.bin_attrs = no_free_ptr(bas);
+	ctx->tm = tm;
+	return &no_free_ptr(ctx)->agrp;
+}
+EXPORT_SYMBOL_GPL(tsm_mr_create_attribute_group);
+
+/**
+ * tsm_mr_free_attribute_group() - frees the attribute group returned by
+ * tsm_mr_create_attribute_group()
+ * @attr_grp: attribute group returned by tsm_mr_create_attribute_group()
+ *
+ * Context: Process context.
+ */
+void tsm_mr_free_attribute_group(const struct attribute_group *attr_grp)
+{
+	if (!IS_ERR_OR_NULL(attr_grp)) {
+		kfree(attr_grp->bin_attrs);
+		kfree(container_of(attr_grp, struct tm_context, agrp));
+	}
+}
+EXPORT_SYMBOL_GPL(tsm_mr_free_attribute_group);
diff --git a/include/linux/tsm-mr.h b/include/linux/tsm-mr.h
new file mode 100644
index 0000000000000000000000000000000000000000..50a521f4ac972d1c279e391d0c77df686d3009be
--- /dev/null
+++ b/include/linux/tsm-mr.h
@@ -0,0 +1,89 @@
+/* SPDX-License-Identifier: GPL-2.0 */
+
+#ifndef __TSM_MR_H
+#define __TSM_MR_H
+
+#include <crypto/hash_info.h>
+
+/**
+ * struct tsm_measurement_register - describes an architectural measurement
+ * register (MR)
+ * @mr_name: name of the MR
+ * @mr_value: buffer containing the current value of the MR
+ * @mr_size: size of the MR - typically the digest size of @mr_hash
+ * @mr_flags: bitwise OR of one or more flags, detailed below
+ * @mr_hash: optional hash identifier defined in include/uapi/linux/hash_info.h.
+ *
+ * A CC guest driver encloses an array of this structure in struct
+ * tsm_measurements to detail the measurement facility supported by the
+ * underlying CC hardware.
+ *
+ * @mr_name and @mr_value must stay valid until this structure is no longer in
+ * use.
+ *
+ * @mr_flags is the bitwise-OR of zero or more of the flags below.
+ *
+ * * %TSM_MR_F_READABLE - the sysfs attribute corresponding to this MR is readable.
+ * * %TSM_MR_F_WRITABLE - the sysfs attribute corresponding to this MR is writable.
+ *   The semantics is typically to extend the MR but could vary depending on the
+ *   architecture and the MR.
+ * * %TSM_MR_F_LIVE - this MR's value may differ from the last value written, so
+ *   must be read back from the underlying CC hardware/firmware.
+ * * %TSM_MR_F_RTMR - bitwise-OR of %TSM_MR_F_LIVE and %TSM_MR_F_WRITABLE.
+ * * %TSM_MR_F_NOHASH - this MR does NOT have an associated hash algorithm.
+ *   @mr_hash will be ignored when this flag is set.
+ */
+struct tsm_measurement_register {
+	const char *mr_name;
+	void *mr_value;
+	u32 mr_size;
+	u32 mr_flags;
+	enum hash_algo mr_hash;
+};
+
+#define TSM_MR_F_NOHASH 1
+#define TSM_MR_F_WRITABLE 2
+#define TSM_MR_F_READABLE 4
+#define TSM_MR_F_LIVE 8
+#define TSM_MR_F_RTMR (TSM_MR_F_LIVE | TSM_MR_F_WRITABLE)
+
+#define TSM_MR_(mr, hash)                              \
+	.mr_name = #mr, .mr_size = hash##_DIGEST_SIZE, \
+	.mr_hash = HASH_ALGO_##hash, .mr_flags = TSM_MR_F_READABLE
+
+/**
+ * struct tsm_measurements - defines the CC architecture specific measurement
+ * facility and methods for updating measurement registers (MRs)
+ * @mrs: Array of MR definitions.
+ * @nr_mrs: Number of elements in @mrs.
+ * @refresh: Callback function to load/sync all MRs from TVM hardware/firmware
+ *           into the kernel cache.
+ * @write: Callback function to write to the MR specified by the parameter @mr.
+ *         Typically, writing to an MR extends the input buffer to that MR.
+ *
+ * The @refresh callback is invoked when an MR with %TSM_MR_F_LIVE set is being
+ * read and the cache is stale. It must reload all MRs with %TSM_MR_F_LIVE set.
+ * The function parameter @tm is a pointer pointing back to this structure.
+ *
+ * The @write callback is invoked whenever an MR is being written. It takes two
+ * additional parameters besides @tm:
+ *
+ * * @mr - points to the MR (an element of @tm->mrs) being written.
+ * * @data - contains the bytes to write and whose size is @mr->mr_size.
+ *
+ * Both @refresh and @write should return 0 on success and an appropriate error
+ * code on failure.
+ */
+struct tsm_measurements {
+	const struct tsm_measurement_register *mrs;
+	size_t nr_mrs;
+	int (*refresh)(const struct tsm_measurements *tm);
+	int (*write)(const struct tsm_measurements *tm,
+		     const struct tsm_measurement_register *mr, const u8 *data);
+};
+
+const struct attribute_group *
+tsm_mr_create_attribute_group(const struct tsm_measurements *tm);
+void tsm_mr_free_attribute_group(const struct attribute_group *attr_grp);
+
+#endif
diff --git a/include/trace/events/tsm_mr.h b/include/trace/events/tsm_mr.h
new file mode 100644
index 0000000000000000000000000000000000000000..f40de4ad3e2d74eef4b38c0f117b817b90e4acf6
--- /dev/null
+++ b/include/trace/events/tsm_mr.h
@@ -0,0 +1,80 @@
+/* SPDX-License-Identifier: GPL-2.0 */
+#undef TRACE_SYSTEM
+#define TRACE_SYSTEM tsm_mr
+
+#if !defined(_TRACE_TSM_MR_H) || defined(TRACE_HEADER_MULTI_READ)
+#define _TRACE_TSM_MR_H
+
+#include <linux/tracepoint.h>
+#include <linux/tsm-mr.h>
+
+TRACE_EVENT(tsm_mr_read,
+
+	TP_PROTO(const struct tsm_measurement_register *mr),
+
+	TP_ARGS(mr),
+
+	TP_STRUCT__entry(
+		__string(mr, mr->mr_name)
+		__string(hash, mr->mr_flags & TSM_MR_F_NOHASH ?
+			 "data" : hash_algo_name[mr->mr_hash])
+		__dynamic_array(u8, d, mr->mr_size)
+	),
+
+	TP_fast_assign(
+		__assign_str(mr);
+		__assign_str(hash);
+		memcpy(__get_dynamic_array(d), mr->mr_value, __get_dynamic_array_len(d));
+	),
+
+	TP_printk("[%s] %s:%s", __get_str(mr), __get_str(hash),
+		  __print_hex_str(__get_dynamic_array(d), __get_dynamic_array_len(d)))
+);
+
+TRACE_EVENT(tsm_mr_refresh,
+
+	TP_PROTO(const struct tsm_measurement_register *mr, int rc),
+
+	TP_ARGS(mr, rc),
+
+	TP_STRUCT__entry(
+		__string(mr, mr->mr_name)
+		__field(int, rc)
+	),
+
+	TP_fast_assign(
+		__assign_str(mr);
+		__entry->rc = rc;
+	),
+
+	TP_printk("[%s] %s:%d", __get_str(mr),
+		  __entry->rc ? "failed" : "succeeded", __entry->rc)
+);
+
+TRACE_EVENT(tsm_mr_write,
+
+	TP_PROTO(const struct tsm_measurement_register *mr, const u8 *data),
+
+	TP_ARGS(mr, data),
+
+	TP_STRUCT__entry(
+		__string(mr, mr->mr_name)
+		__string(hash, mr->mr_flags & TSM_MR_F_NOHASH ?
+			 "data" : hash_algo_name[mr->mr_hash])
+		__dynamic_array(u8, d, mr->mr_size)
+	),
+
+	TP_fast_assign(
+		__assign_str(mr);
+		__assign_str(hash);
+		memcpy(__get_dynamic_array(d), data, __get_dynamic_array_len(d));
+	),
+
+	TP_printk("[%s] %s:%s", __get_str(mr), __get_str(hash),
+		  __print_hex_str(__get_dynamic_array(d), __get_dynamic_array_len(d)))
+);
+
+#endif
+
+/* This part must be outside protection */
+#include <trace/define_trace.h>

---

## [3] Cedric Xing — 2025-05-06
*Subject: [PATCH v6 2/7] tsm-mr: Add tsm-mr sample code*

This sample kernel module demonstrates how to make MRs accessible to user
mode through the tsm-mr library.

Once loaded, this module registers a `miscdevice` that host a set of
emulated measurement registers as shown in the directory tree below.

/sys/class/misc/tsm_mr_sample
└── measurements
    ├── config_mr
    ├── report_digest:sha512
    ├── rtmr0:sha256
    ├── rtmr1:sha384
    ├── rtmr_crypto_agile:sha256
    ├── rtmr_crypto_agile:sha384
    └── static_mr:sha384

Among the MRs in this example:

- `config_mr` demonstrates a hashless MR, like MRCONFIGID in Intel TDX or
  HOSTDATA in AMD SEV.
- `static_mr` demonstrates a static MR. The suffix `:sha384` indicates its
  value is a sha384 digest.
- `rtmr0` is an RTMR with `TSM_MR_F_WRITABLE` **cleared**, preventing
  direct extensions; as a result, the attribute `rtmr0:sha256` is
  read-only.
- `rtmr1` is an RTMR with `TSM_MR_F_WRITABLE` **set**, permitting direct
  extensions; thus, the attribute `rtmr1:sha384` is writable.
- `rtmr_crypto_agile` demonstrates a "single" MR that supports multiple
  hash algorithms. Each supported algorithm has a corresponding digest,
  usually referred to as a "bank" in TCG terminology. In this specific
  sample, the 2 banks are aliased to `rtmr0` and `rtmr1`, respectively.
- `report_digest` contains the digest of the internal report structure
  living in this sample module's memory. It is to demonstrate the use of
  the `TSM_MR_F_LIVE` flag. Its value changes each time an RTMR is
  extended.

Signed-off-by: Cedric Xing <cedric.xing@intel.com>
Reviewed-by: Dan Williams <dan.j.williams@intel.com>
Acked-by: Dionna Amalie Glaze <dionnaglaze@google.com>
---
 MAINTAINERS                    |   1 +
 samples/Kconfig                |  11 ++++
 samples/Makefile               |   1 +
 samples/tsm-mr/Makefile        |   2 +
 samples/tsm-mr/tsm_mr_sample.c | 131 +++++++++++++++++++++++++++++++++++++++++
 5 files changed, 146 insertions(+)

diff --git a/MAINTAINERS b/MAINTAINERS
index 5d36823d26b28797c1186e7df1eb4d2da612f51c..8bf8a818bce5225bd5e2a18685893efa5a9c5650 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -24651,6 +24651,7 @@ F:	Documentation/ABI/testing/configfs-tsm
 F:	Documentation/driver-api/coco/
 F:	drivers/virt/coco/tsm*.c
 F:	include/linux/tsm*.h
+F:	samples/tsm/
 
 TRUSTED SERVICES TEE DRIVER
 M:	Balint Dobszay <balint.dobszay@arm.com>
diff --git a/samples/Kconfig b/samples/Kconfig
index 09011be2391a925bb31b1cf6e6a979599fed30f4..6ade17cb16b441965f0a19d87ddf766c8ee3922c 100644
--- a/samples/Kconfig
+++ b/samples/Kconfig
@@ -184,6 +184,17 @@ config SAMPLE_TIMER
 	bool "Timer sample"
 	depends on CC_CAN_LINK && HEADERS_INSTALL
 
+config SAMPLE_TSM_MR
+	tristate "TSM measurement sample"
+	select TSM_MEASUREMENTS
+	select VIRT_DRIVERS
+	help
+	  Build a sample module that emulates MRs (Measurement Registers) and
+	  exposes them to user mode applications through the TSM sysfs
+	  interface (/sys/class/misc/tsm_mr_sample/emulated_mr/).
+
+	  The module name will be tsm-mr-sample when built as a module.
+
 config SAMPLE_UHID
 	bool "UHID sample"
 	depends on CC_CAN_LINK && HEADERS_INSTALL
diff --git a/samples/Makefile b/samples/Makefile
index bf6e6fca5410b1b374a287269c24f96de8bb2800..c95bac31851c2cafbbbef3ad8e36bea752e411ea 100644
--- a/samples/Makefile
+++ b/samples/Makefile
@@ -43,3 +43,4 @@ obj-$(CONFIG_SAMPLES_RUST)		+= rust/
 obj-$(CONFIG_SAMPLE_DAMON_WSSE)		+= damon/
 obj-$(CONFIG_SAMPLE_DAMON_PRCL)		+= damon/
 obj-$(CONFIG_SAMPLE_HUNG_TASK)		+= hung_task/
+obj-$(CONFIG_SAMPLE_TSM_MR)		+= tsm-mr/
diff --git a/samples/tsm-mr/Makefile b/samples/tsm-mr/Makefile
new file mode 100644
index 0000000000000000000000000000000000000000..587c3947b3a750f124e1fbb4bcffbd30108609b2
--- /dev/null
+++ b/samples/tsm-mr/Makefile
@@ -0,0 +1,2 @@
+# SPDX-License-Identifier: GPL-2.0-only
+obj-$(CONFIG_SAMPLE_TSM_MR) += tsm_mr_sample.o
diff --git a/samples/tsm-mr/tsm_mr_sample.c b/samples/tsm-mr/tsm_mr_sample.c
new file mode 100644
index 0000000000000000000000000000000000000000..f3e16301de402389a259f376e77acb96c9560506
--- /dev/null
+++ b/samples/tsm-mr/tsm_mr_sample.c
@@ -0,0 +1,131 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/* Copyright(c) 2024-2005 Intel Corporation. All rights reserved. */
+
+#define pr_fmt(x) KBUILD_MODNAME ": " x
+
+#include <linux/module.h>
+#include <linux/tsm-mr.h>
+#include <linux/miscdevice.h>
+#include <crypto/hash.h>
+
+struct {
+	u8 static_mr[SHA384_DIGEST_SIZE];
+	u8 config_mr[SHA512_DIGEST_SIZE];
+	u8 rtmr0[SHA256_DIGEST_SIZE];
+	u8 rtmr1[SHA384_DIGEST_SIZE];
+	u8 report_digest[SHA512_DIGEST_SIZE];
+} sample_report = {
+	.static_mr = "static_mr",
+	.config_mr = "config_mr",
+	.rtmr0 = "rtmr0",
+	.rtmr1 = "rtmr1",
+};
+
+static int sample_report_refresh(const struct tsm_measurements *tm)
+{
+	struct crypto_shash *tfm;
+	int rc;
+
+	tfm = crypto_alloc_shash(hash_algo_name[HASH_ALGO_SHA512], 0, 0);
+	if (IS_ERR(tfm)) {
+		pr_err("crypto_alloc_shash failed: %ld\n", PTR_ERR(tfm));
+		return PTR_ERR(tfm);
+	}
+
+	rc = crypto_shash_tfm_digest(tfm, (u8 *)&sample_report,
+				     offsetof(typeof(sample_report),
+					      report_digest),
+				     sample_report.report_digest);
+	crypto_free_shash(tfm);
+	if (rc)
+		pr_err("crypto_shash_tfm_digest failed: %d\n", rc);
+	return rc;
+}
+
+static int sample_report_extend_mr(const struct tsm_measurements *tm,
+				   const struct tsm_measurement_register *mr,
+				   const u8 *data)
+{
+	SHASH_DESC_ON_STACK(desc, 0);
+	int rc;
+
+	desc->tfm = crypto_alloc_shash(hash_algo_name[mr->mr_hash], 0, 0);
+	if (IS_ERR(desc->tfm)) {
+		pr_err("crypto_alloc_shash failed: %ld\n", PTR_ERR(desc->tfm));
+		return PTR_ERR(desc->tfm);
+	}
+
+	rc = crypto_shash_init(desc);
+	if (!rc)
+		rc = crypto_shash_update(desc, mr->mr_value, mr->mr_size);
+	if (!rc)
+		rc = crypto_shash_finup(desc, data, mr->mr_size, mr->mr_value);
+	crypto_free_shash(desc->tfm);
+	if (rc)
+		pr_err("SHA calculation failed: %d\n", rc);
+	return rc;
+}
+
+#define MR_(mr, hash) .mr_value = &sample_report.mr, TSM_MR_(mr, hash)
+static const struct tsm_measurement_register sample_mrs[] = {
+	/* static MR, read-only */
+	{ MR_(static_mr, SHA384) },
+	/* config MR, read-only */
+	{ MR_(config_mr, SHA512) | TSM_MR_F_NOHASH },
+	/* RTMR, direct extension prohibited */
+	{ MR_(rtmr0, SHA256) | TSM_MR_F_LIVE },
+	/* RTMR, direct extension allowed */
+	{ MR_(rtmr1, SHA384) | TSM_MR_F_RTMR },
+	/* RTMR, crypto agile, alaised to rtmr0 and rtmr1, respectively */
+	{ .mr_value = &sample_report.rtmr0,
+	  TSM_MR_(rtmr_crypto_agile, SHA256) | TSM_MR_F_RTMR },
+	{ .mr_value = &sample_report.rtmr1,
+	  TSM_MR_(rtmr_crypto_agile, SHA384) | TSM_MR_F_RTMR },
+	/* sha512 digest of the whole structure */
+	{ MR_(report_digest, SHA512) | TSM_MR_F_LIVE },
+};
+#undef MR_
+
+static struct tsm_measurements sample_tm = {
+	.mrs = sample_mrs,
+	.nr_mrs = ARRAY_SIZE(sample_mrs),
+	.refresh = sample_report_refresh,
+	.write = sample_report_extend_mr,
+};
+
+static const struct attribute_group *sample_groups[] = {
+	NULL,
+	NULL,
+};
+
+static struct miscdevice sample_misc_dev = {
+	.name = KBUILD_MODNAME,
+	.minor = MISC_DYNAMIC_MINOR,
+	.groups = sample_groups,
+};
+
+static int __init tsm_mr_sample_init(void)
+{
+	int rc;
+
+	sample_groups[0] = tsm_mr_create_attribute_group(&sample_tm);
+	if (IS_ERR(sample_groups[0]))
+		return PTR_ERR(sample_groups[0]);
+
+	rc = misc_register(&sample_misc_dev);
+	if (rc)
+		tsm_mr_free_attribute_group(sample_groups[0]);
+	return rc;
+}
+
+static void __exit tsm_mr_sample_exit(void)
+{
+	misc_deregister(&sample_misc_dev);
+	tsm_mr_free_attribute_group(sample_groups[0]);
+}
+
+module_init(tsm_mr_sample_init);
+module_exit(tsm_mr_sample_exit);
+
+MODULE_LICENSE("GPL");
+MODULE_DESCRIPTION("Sample module using tsm-mr to expose emulated MRs");

---

## [4] Cedric Xing — 2025-05-06
*Subject: [PATCH v6 3/7] x86/tdx: Add tdx_mcall_extend_rtmr() interface*

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

Co-developed-by: Kuppuswamy Sathyanarayanan <sathyanarayanan.kuppuswamy@linux.intel.com>
Signed-off-by: Kuppuswamy Sathyanarayanan <sathyanarayanan.kuppuswamy@linux.intel.com>
Signed-off-by: Cedric Xing <cedric.xing@intel.com>
Acked-by: Dionna Amalie Glaze <dionnaglaze@google.com>
Acked-by: Dave Hansen <dave.hansen@linux.intel.com>
---
 arch/x86/coco/tdx/tdx.c           | 37 +++++++++++++++++++++++++++++++++++++
 arch/x86/include/asm/shared/tdx.h |  1 +
 arch/x86/include/asm/tdx.h        |  2 ++
 3 files changed, 40 insertions(+)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index edab6d6049bedfb8b7cb2cbb57ab0a670bb6a6c6..0b6804d2a5e14d3ccbee5d19ad8ae6674527fb2f 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -36,6 +36,7 @@
 /* TDX Module call error codes */
 #define TDCALL_RETURN_CODE(a)	((a) >> 32)
 #define TDCALL_INVALID_OPERAND	0xc0000100
+#define TDCALL_OPERAND_BUSY	0x80000200
 
 #define TDREPORT_SUBTYPE_0	0
 
@@ -136,6 +137,42 @@ int tdx_mcall_get_report0(u8 *reportdata, u8 *tdreport)
 }
 EXPORT_SYMBOL_GPL(tdx_mcall_get_report0);
 
+/**
+ * tdx_mcall_extend_rtmr() - Wrapper to extend RTMR registers using
+ *			     TDG.MR.RTMR.EXTEND TDCALL.
+ * @index: Index of RTMR register to be extended.
+ * @data: Address of the input buffer with RTMR register extend data.
+ *
+ * Refer to section titled "TDG.MR.RTMR.EXTEND leaf" in the TDX Module v1.0
+ * specification for more information on TDG.MR.RTMR.EXTEND TDCALL.
+ *
+ * It is used in the TDX guest driver module to allow user to extend the RTMR
+ * registers.
+ *
+ * Return 0 on success, -ENXIO for invalid operands, -EBUSY for busy operation,
+ * or -EIO on other TDCALL failures.
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
+			return -ENXIO;
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
index a28ff6b141458b57e0bb333646328ea302678d3a..738f583f65cb00a12494b027a5b41347734b044e 100644
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
index 4a1922ec80cf76ffb9662d0dd34eb02a7c66b4d4..12d17f3ca3016a1bfeb37f07d82721331826fd96 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -64,6 +64,8 @@ bool tdx_early_handle_ve(struct pt_regs *regs);
 
 int tdx_mcall_get_report0(u8 *reportdata, u8 *tdreport);
 
+int tdx_mcall_extend_rtmr(u8 index, u8 *data);
+
 u64 tdx_hcall_get_quote(u8 *buf, size_t size);
 
 void __init tdx_dump_attributes(u64 td_attr);

---

## [5] Cedric Xing — 2025-05-06
*Subject: [PATCH v6 4/7] x86/tdx: tdx_mcall_get_report0: Return -EBUSY on
 TDCALL_OPERAND_BUSY error*

Return `-EBUSY` from tdx_mcall_get_report0() when `TDG.MR.REPORT` returns
`TDCALL_OPERAND_BUSY`. This enables the caller to retry obtaining a
TDREPORT later if another VCPU is extending an RTMR concurrently.

Signed-off-by: Cedric Xing <cedric.xing@intel.com>
Acked-by: Dionna Amalie Glaze <dionnaglaze@google.com>
Acked-by: Dave Hansen <dave.hansen@linux.intel.com>
---
 arch/x86/coco/tdx/tdx.c | 13 ++++++++-----
 1 file changed, 8 insertions(+), 5 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 0b6804d2a5e14d3ccbee5d19ad8ae6674527fb2f..7b2833705d475a8c0c0e8393685f923c5fd58945 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -110,12 +110,13 @@ static inline u64 tdg_vm_wr(u64 field, u64 value, u64 mask)
  *              REPORTDATA to be included into TDREPORT.
  * @tdreport: Address of the output buffer to store TDREPORT.
  *
- * Refer to section titled "TDG.MR.REPORT leaf" in the TDX Module
- * v1.0 specification for more information on TDG.MR.REPORT TDCALL.
+ * Refer to section titled "TDG.MR.REPORT leaf" in the TDX Module v1.0
+ * specification for more information on TDG.MR.REPORT TDCALL.
+ *
  * It is used in the TDX guest driver module to get the TDREPORT0.
  *
- * Return 0 on success, -EINVAL for invalid operands, or -EIO on
- * other TDCALL failures.
+ * Return 0 on success, -ENXIO for invalid operands, -EBUSY for busy operation,
+ * or -EIO on other TDCALL failures.
  */
 int tdx_mcall_get_report0(u8 *reportdata, u8 *tdreport)
 {
@@ -129,7 +130,9 @@ int tdx_mcall_get_report0(u8 *reportdata, u8 *tdreport)
 	ret = __tdcall(TDG_MR_REPORT, &args);
 	if (ret) {
 		if (TDCALL_RETURN_CODE(ret) == TDCALL_INVALID_OPERAND)
-			return -EINVAL;
+			return -ENXIO;
+		else if (TDCALL_RETURN_CODE(ret) == TDCALL_OPERAND_BUSY)
+			return -EBUSY;
 		return -EIO;
 	}

---

## [6] Cedric Xing — 2025-05-06
*Subject: [PATCH v6 5/7] virt: tdx-guest: Expose TDX MRs as sysfs attributes*

Expose the most commonly used TDX MRs (Measurement Registers) as sysfs
attributes. Use the ioctl() interface of /dev/tdx_guest to request a full
TDREPORT for access to other TD measurements.

Directory structure of TDX MRs inside a TDVM is as follows:

/sys/class/misc/tdx_guest
└── measurements
    ├── mrconfigid
    ├── mrowner
    ├── mrownerconfig
    ├── mrtd:sha384
    ├── rtmr0:sha384
    ├── rtmr1:sha384
    ├── rtmr2:sha384
    └── rtmr3:sha384

Read the file/attribute to retrieve the current value of an MR. Write to
the file/attribute (if writable) to extend the corresponding RTMR. Refer to
Documentation/ABI/testing/sysfs-devices-virtual-misc-tdx_guest for more
information.

Signed-off-by: Cedric Xing <cedric.xing@intel.com>
Acked-by: Dionna Amalie Glaze <dionnaglaze@google.com>
---
 .../testing/sysfs-devices-virtual-misc-tdx_guest   |  63 +++++++++
 MAINTAINERS                                        |   1 +
 drivers/virt/coco/tdx-guest/Kconfig                |   1 +
 drivers/virt/coco/tdx-guest/tdx-guest.c            | 151 ++++++++++++++++++++-
 4 files changed, 214 insertions(+), 2 deletions(-)

diff --git a/Documentation/ABI/testing/sysfs-devices-virtual-misc-tdx_guest b/Documentation/ABI/testing/sysfs-devices-virtual-misc-tdx_guest
new file mode 100644
index 0000000000000000000000000000000000000000..8fca56c8c9dfe6abfad4148c91dfb50e35806b82
--- /dev/null
+++ b/Documentation/ABI/testing/sysfs-devices-virtual-misc-tdx_guest
@@ -0,0 +1,63 @@
+What:		/sys/devices/virtual/misc/tdx_guest/measurements/MRNAME[:HASH]
+Date:		April, 2025
+KernelVersion:	v6.16
+Contact:	linux-coco@lists.linux.dev
+Description:
+		Value of a TDX measurement register (MR). MRNAME and HASH above
+		are placeholders. The optional suffix :HASH is used for MRs
+		that have associated hash algorithms. See below for a complete
+		list of TDX MRs exposed via sysfs. Refer to Intel TDX Module
+		ABI Specification for the definition of TDREPORT and the full
+		list of TDX measurements.
+
+		Intel TDX Module ABI Specification can be found at:
+		https://www.intel.com/content/www/us/en/developer/tools/trust-domain-extensions/documentation.html#architecture
+
+		See also:
+		https://docs.kernel.org/driver-api/coco/measurement-registers.html
+
+What:		/sys/devices/virtual/misc/tdx_guest/measurements/mrconfigid
+Date:		April, 2025
+KernelVersion:	v6.16
+Contact:	linux-coco@lists.linux.dev
+Description:
+		(RO) MRCONFIGID - 48-byte immutable storage typically used for
+		software-defined ID for non-owner-defined configuration of the
+		guest TD – e.g., run-time or OS configuration.
+
+What:		/sys/devices/virtual/misc/tdx_guest/measurements/mrowner
+Date:		April, 2025
+KernelVersion:	v6.16
+Contact:	linux-coco@lists.linux.dev
+Description:
+		(RO) MROWNER - 48-byte immutable storage typically used for
+		software-defined ID for the guest TD’s owner.
+
+What:		/sys/devices/virtual/misc/tdx_guest/measurements/mrownerconfig
+Date:		April, 2025
+KernelVersion:	v6.16
+Contact:	linux-coco@lists.linux.dev
+Description:
+		(RO) MROWNERCONFIG - 48-byte immutable storage typically used
+		for software-defined ID for owner-defined configuration of the
+		guest TD – e.g., specific to the workload rather than the
+		run-time or OS.
+
+What:		/sys/devices/virtual/misc/tdx_guest/measurements/mrtd:sha384
+Date:		April, 2025
+KernelVersion:	v6.16
+Contact:	linux-coco@lists.linux.dev
+Description:
+		(RO) MRTD - Measurement of the initial contents of the TD.
+
+What:		/sys/devices/virtual/misc/tdx_guest/measurements/rtmr[0123]:sha384
+Date:		April, 2025
+KernelVersion:	v6.16
+Contact:	linux-coco@lists.linux.dev
+Description:
+		(RW) RTMR[0123] - 4 Run-Time extendable Measurement Registers.
+		Read from any of these returns the current value of the
+		corresponding RTMR. Write extends the written buffer to the
+		RTMR. All writes must start at offset 0 and be 48 bytes in
+		size. Partial writes will result in EINVAL returned by the
+		write() syscall.
diff --git a/MAINTAINERS b/MAINTAINERS
index 8bf8a818bce5225bd5e2a18685893efa5a9c5650..912e16ace0b4affec1e84b5c78060db7e58d9243 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -26321,6 +26321,7 @@ L:	x86@kernel.org
 L:	linux-coco@lists.linux.dev
 S:	Supported
 T:	git git://git.kernel.org/pub/scm/linux/kernel/git/tip/tip.git x86/tdx
+F:	Documentation/ABI/testing/sysfs-devices-virtual-misc-tdx_guest
 F:	arch/x86/boot/compressed/tdx*
 F:	arch/x86/coco/tdx/
 F:	arch/x86/include/asm/shared/tdx.h
diff --git a/drivers/virt/coco/tdx-guest/Kconfig b/drivers/virt/coco/tdx-guest/Kconfig
index 22dd59e194315a754472b510465af35a9f8c3b27..dbbdc14383b132616490dfed8be571190b657096 100644
--- a/drivers/virt/coco/tdx-guest/Kconfig
+++ b/drivers/virt/coco/tdx-guest/Kconfig
@@ -2,6 +2,7 @@ config TDX_GUEST_DRIVER
 	tristate "TDX Guest driver"
 	depends on INTEL_TDX_GUEST
 	select TSM_REPORTS
+	select TSM_MEASUREMENTS
 	help
 	  The driver provides userspace interface to communicate with
 	  the TDX module to request the TDX guest details like attestation
diff --git a/drivers/virt/coco/tdx-guest/tdx-guest.c b/drivers/virt/coco/tdx-guest/tdx-guest.c
index 224e7dde9cdee877fd587d2fc974f2ccc7481d0f..452520ad1b32341405cae63a9cea02fdf8baf9b9 100644
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
@@ -15,14 +17,146 @@
 #include <linux/set_memory.h>
 #include <linux/io.h>
 #include <linux/delay.h>
+#include <linux/sockptr.h>
 #include <linux/tsm.h>
-#include <linux/sizes.h>
+#include <linux/tsm-mr.h>
 
 #include <uapi/linux/tdx-guest.h>
 
 #include <asm/cpu_device_id.h>
 #include <asm/tdx.h>
 
+/* TDREPORT buffer */
+static u8 *tdx_report_buf;
+
+/* Lock to serialize TDG.MR.REPORT and TDG.MR.RTMR.EXTEND TDCALLs */
+static DEFINE_MUTEX(mr_lock);
+
+/* TDREPORT fields */
+enum {
+	TDREPORT_reportdata = 128,
+	TDREPORT_tee_tcb_info = 256,
+	TDREPORT_tdinfo = TDREPORT_tee_tcb_info + 256,
+	TDREPORT_attributes = TDREPORT_tdinfo,
+	TDREPORT_xfam = TDREPORT_attributes + sizeof(u64),
+	TDREPORT_mrtd = TDREPORT_xfam + sizeof(u64),
+	TDREPORT_mrconfigid = TDREPORT_mrtd + SHA384_DIGEST_SIZE,
+	TDREPORT_mrowner = TDREPORT_mrconfigid + SHA384_DIGEST_SIZE,
+	TDREPORT_mrownerconfig = TDREPORT_mrowner + SHA384_DIGEST_SIZE,
+	TDREPORT_rtmr0 = TDREPORT_mrownerconfig + SHA384_DIGEST_SIZE,
+	TDREPORT_rtmr1 = TDREPORT_rtmr0 + SHA384_DIGEST_SIZE,
+	TDREPORT_rtmr2 = TDREPORT_rtmr1 + SHA384_DIGEST_SIZE,
+	TDREPORT_rtmr3 = TDREPORT_rtmr2 + SHA384_DIGEST_SIZE,
+	TDREPORT_servtd_hash = TDREPORT_rtmr3 + SHA384_DIGEST_SIZE,
+};
+
+static int tdx_do_report(sockptr_t data, sockptr_t tdreport)
+{
+	scoped_cond_guard(mutex_intr, return -EINTR, &mr_lock) {
+		u8 *reportdata = tdx_report_buf + TDREPORT_reportdata;
+		int ret;
+
+		if (!sockptr_is_null(data) &&
+		    copy_from_sockptr(reportdata, data, TDX_REPORTDATA_LEN))
+			return -EFAULT;
+
+		ret = tdx_mcall_get_report0(reportdata, tdx_report_buf);
+		if (WARN_ONCE(ret, "tdx_mcall_get_report0() failed: %d", ret))
+			return ret;
+
+		if (!sockptr_is_null(tdreport) &&
+		    copy_to_sockptr(tdreport, tdx_report_buf, TDX_REPORT_LEN))
+			return -EFAULT;
+	}
+	return 0;
+}
+
+static int tdx_do_extend(u8 mr_ind, const u8 *data)
+{
+	scoped_cond_guard(mutex_intr, return -EINTR, &mr_lock) {
+		/*
+		 * TDX requires @extend_buf to be 64-byte aligned.
+		 * It's safe to use REPORTDATA buffer for that purpose because
+		 * tdx_mr_report/extend_lock() are mutually exclusive.
+		 */
+		u8 *extend_buf = tdx_report_buf + TDREPORT_reportdata;
+		int ret;
+
+		memcpy(extend_buf, data, SHA384_DIGEST_SIZE);
+
+		ret = tdx_mcall_extend_rtmr(mr_ind, extend_buf);
+		if (WARN_ONCE(ret, "tdx_mcall_extend_rtmr(%u) failed: %d", mr_ind, ret))
+			return ret;
+	}
+	return 0;
+}
+
+#define TDX_MR_(r) .mr_value = (void *)TDREPORT_##r, TSM_MR_(r, SHA384)
+static struct tsm_measurement_register tdx_mrs[] = {
+	{ TDX_MR_(rtmr0) | TSM_MR_F_RTMR },
+	{ TDX_MR_(rtmr1) | TSM_MR_F_RTMR },
+	{ TDX_MR_(rtmr2) | TSM_MR_F_RTMR },
+	{ TDX_MR_(rtmr3) | TSM_MR_F_RTMR },
+	{ TDX_MR_(mrtd) },
+	{ TDX_MR_(mrconfigid) | TSM_MR_F_NOHASH },
+	{ TDX_MR_(mrowner) | TSM_MR_F_NOHASH },
+	{ TDX_MR_(mrownerconfig) | TSM_MR_F_NOHASH },
+};
+#undef TDX_MR_
+
+static int tdx_mr_refresh(const struct tsm_measurements *tm)
+{
+	return tdx_do_report(KERNEL_SOCKPTR(NULL), KERNEL_SOCKPTR(NULL));
+}
+
+static int tdx_mr_extend(const struct tsm_measurements *tm,
+			 const struct tsm_measurement_register *mr,
+			 const u8 *data)
+{
+	return tdx_do_extend(mr - tm->mrs, data);
+}
+
+static struct tsm_measurements tdx_measurements = {
+	.mrs = tdx_mrs,
+	.nr_mrs = ARRAY_SIZE(tdx_mrs),
+	.refresh = tdx_mr_refresh,
+	.write = tdx_mr_extend,
+};
+
+static const struct attribute_group *tdx_mr_init(void)
+{
+	const struct attribute_group *g;
+	int rc;
+
+	u8 *buf __free(kfree) = kzalloc(TDX_REPORT_LEN, GFP_KERNEL);
+	if (!buf)
+		return ERR_PTR(-ENOMEM);
+
+	tdx_report_buf = buf;
+	rc = tdx_mr_refresh(&tdx_measurements);
+	if (rc)
+		return ERR_PTR(rc);
+
+	/*
+	 * @mr_value was initialized with the offset only, while the base
+	 * address is being added here.
+	 */
+	for (size_t i = 0; i < ARRAY_SIZE(tdx_mrs); ++i)
+		*(long *)&tdx_mrs[i].mr_value += (long)buf;
+
+	g = tsm_mr_create_attribute_group(&tdx_measurements);
+	if (!IS_ERR(g))
+		tdx_report_buf = no_free_ptr(buf);
+
+	return g;
+}
+
+static void tdx_mr_deinit(const struct attribute_group *mr_grp)
+{
+	tsm_mr_free_attribute_group(mr_grp);
+	kfree(tdx_report_buf);
+}
+
 /*
  * Intel's SGX QE implementation generally uses Quote size less
  * than 8K (2K Quote data + ~5K of certificate blob).
@@ -285,10 +419,16 @@ static const struct file_operations tdx_guest_fops = {
 	.unlocked_ioctl = tdx_guest_ioctl,
 };
 
+static const struct attribute_group *tdx_attr_groups[] = {
+	NULL, /* measurements */
+	NULL
+};
+
 static struct miscdevice tdx_misc_dev = {
 	.name = KBUILD_MODNAME,
 	.minor = MISC_DYNAMIC_MINOR,
 	.fops = &tdx_guest_fops,
+	.groups = tdx_attr_groups,
 };
 
 static const struct x86_cpu_id tdx_guest_ids[] = {
@@ -311,9 +451,13 @@ static int __init tdx_guest_init(void)
 	if (!x86_match_cpu(tdx_guest_ids))
 		return -ENODEV;
 
+	tdx_attr_groups[0] = tdx_mr_init();
+	if (IS_ERR(tdx_attr_groups[0]))
+		return PTR_ERR(tdx_attr_groups[0]);
+
 	ret = misc_register(&tdx_misc_dev);
 	if (ret)
-		return ret;
+		goto deinit_mr;
 
 	quote_data = alloc_quote_buf();
 	if (!quote_data) {
@@ -332,6 +476,8 @@ static int __init tdx_guest_init(void)
 	free_quote_buf(quote_data);
 free_misc:
 	misc_deregister(&tdx_misc_dev);
+deinit_mr:
+	tdx_mr_deinit(tdx_attr_groups[0]);
 
 	return ret;
 }
@@ -339,6 +485,7 @@ module_init(tdx_guest_init);
 
 static void __exit tdx_guest_exit(void)
 {
+	tdx_mr_deinit(tdx_attr_groups[0]);
 	tsm_unregister(&tdx_tsm_ops);
 	free_quote_buf(quote_data);
 	misc_deregister(&tdx_misc_dev);

---

## [7] Cedric Xing — 2025-05-06
*Subject: [PATCH v6 6/7] virt: tdx-guest: Refactor and streamline TDREPORT
 generation*

Consolidate instances (code segments) of TDREPORT generation to improve
readability and maintainability, by refactoring each instance into invoking
a unified subroutine throughout the TDX guest driver. Implement proper
locking around TDG.MR.REPORT and TDG.MR.RTMR.EXTEND to avoid race inside
the TDX module. Preallocate TDREPORT buffer to reduce overhead in
subsequent TDREPORT generation.

Signed-off-by: Cedric Xing <cedric.xing@intel.com>
Acked-by: Dionna Amalie Glaze <dionnaglaze@google.com>
---
 drivers/virt/coco/tdx-guest/tdx-guest.c | 63 ++++-----------------------------
 1 file changed, 7 insertions(+), 56 deletions(-)

diff --git a/drivers/virt/coco/tdx-guest/tdx-guest.c b/drivers/virt/coco/tdx-guest/tdx-guest.c
index 452520ad1b32341405cae63a9cea02fdf8baf9b9..e94fed82839e767cb803cafb3f69fec7a7de6364 100644
--- a/drivers/virt/coco/tdx-guest/tdx-guest.c
+++ b/drivers/virt/coco/tdx-guest/tdx-guest.c
@@ -202,37 +202,8 @@ static u32 getquote_timeout = 30;
 
 static long tdx_get_report0(struct tdx_report_req __user *req)
 {
-	u8 *reportdata, *tdreport;
-	long ret;
-
-	reportdata = kmalloc(TDX_REPORTDATA_LEN, GFP_KERNEL);
-	if (!reportdata)
-		return -ENOMEM;
-
-	tdreport = kzalloc(TDX_REPORT_LEN, GFP_KERNEL);
-	if (!tdreport) {
-		ret = -ENOMEM;
-		goto out;
-	}
-
-	if (copy_from_user(reportdata, req->reportdata, TDX_REPORTDATA_LEN)) {
-		ret = -EFAULT;
-		goto out;
-	}
-
-	/* Generate TDREPORT0 using "TDG.MR.REPORT" TDCALL */
-	ret = tdx_mcall_get_report0(reportdata, tdreport);
-	if (ret)
-		goto out;
-
-	if (copy_to_user(req->tdreport, tdreport, TDX_REPORT_LEN))
-		ret = -EFAULT;
-
-out:
-	kfree(reportdata);
-	kfree(tdreport);
-
-	return ret;
+	return tdx_do_report(USER_SOCKPTR(req->reportdata),
+			     USER_SOCKPTR(req->tdreport));
 }
 
 static void free_quote_buf(void *buf)
@@ -293,7 +264,7 @@ static int wait_for_quote_completion(struct tdx_quote_buf *quote_buf, u32 timeou
 
 static int tdx_report_new(struct tsm_report *report, void *data)
 {
-	u8 *buf, *reportdata = NULL, *tdreport = NULL;
+	u8 *buf;
 	struct tdx_quote_buf *quote_buf = quote_data;
 	struct tsm_desc *desc = &report->desc;
 	int ret;
@@ -318,34 +289,16 @@ static int tdx_report_new(struct tsm_report *report, void *data)
 		goto done;
 	}
 
-	reportdata = kmalloc(TDX_REPORTDATA_LEN, GFP_KERNEL);
-	if (!reportdata) {
-		ret = -ENOMEM;
-		goto done;
-	}
-
-	tdreport = kzalloc(TDX_REPORT_LEN, GFP_KERNEL);
-	if (!tdreport) {
-		ret = -ENOMEM;
-		goto done;
-	}
-
-	memcpy(reportdata, desc->inblob, desc->inblob_len);
-
-	/* Generate TDREPORT0 using "TDG.MR.REPORT" TDCALL */
-	ret = tdx_mcall_get_report0(reportdata, tdreport);
-	if (ret) {
-		pr_err("GetReport call failed\n");
-		goto done;
-	}
-
 	memset(quote_data, 0, GET_QUOTE_BUF_SIZE);
 
 	/* Update Quote buffer header */
 	quote_buf->version = GET_QUOTE_CMD_VER;
 	quote_buf->in_len = TDX_REPORT_LEN;
 
-	memcpy(quote_buf->data, tdreport, TDX_REPORT_LEN);
+	ret = tdx_do_report(KERNEL_SOCKPTR(desc->inblob),
+			    KERNEL_SOCKPTR(quote_buf->data));
+	if (ret)
+		goto done;
 
 	err = tdx_hcall_get_quote(quote_data, GET_QUOTE_BUF_SIZE);
 	if (err) {
@@ -375,8 +328,6 @@ static int tdx_report_new(struct tsm_report *report, void *data)
 	 */
 done:
 	mutex_unlock(&quote_lock);
-	kfree(reportdata);
-	kfree(tdreport);
 
 	return ret;
 }

---

## [8] Cedric Xing — 2025-05-06
*Subject: [PATCH v6 7/7] virt: tdx-guest: Transition to scoped_cond_guard
 for mutex operations*

Replace mutex_lock_interruptible()/mutex_unlock() with scoped_cond_guard to
enhance code readability and maintainability.

Signed-off-by: Cedric Xing <cedric.xing@intel.com>
Acked-by: Dionna Amalie Glaze <dionnaglaze@google.com>
---
 drivers/virt/coco/tdx-guest/tdx-guest.c | 39 ++++++++++++++-------------------
 1 file changed, 16 insertions(+), 23 deletions(-)

diff --git a/drivers/virt/coco/tdx-guest/tdx-guest.c b/drivers/virt/coco/tdx-guest/tdx-guest.c
index e94fed82839e767cb803cafb3f69fec7a7de6364..5d74f652b8bd16835f06e8f27c986c5c5747e1b0 100644
--- a/drivers/virt/coco/tdx-guest/tdx-guest.c
+++ b/drivers/virt/coco/tdx-guest/tdx-guest.c
@@ -262,7 +262,7 @@ static int wait_for_quote_completion(struct tdx_quote_buf *quote_buf, u32 timeou
 	return (i == timeout) ? -ETIMEDOUT : 0;
 }
 
-static int tdx_report_new(struct tsm_report *report, void *data)
+static int tdx_report_new_locked(struct tsm_report *report, void *data)
 {
 	u8 *buf;
 	struct tdx_quote_buf *quote_buf = quote_data;
@@ -270,24 +270,16 @@ static int tdx_report_new(struct tsm_report *report, void *data)
 	int ret;
 	u64 err;
 
-	/* TODO: switch to guard(mutex_intr) */
-	if (mutex_lock_interruptible(&quote_lock))
-		return -EINTR;
-
 	/*
 	 * If the previous request is timedout or interrupted, and the
 	 * Quote buf status is still in GET_QUOTE_IN_FLIGHT (owned by
 	 * VMM), don't permit any new request.
 	 */
-	if (quote_buf->status == GET_QUOTE_IN_FLIGHT) {
-		ret = -EBUSY;
-		goto done;
-	}
+	if (quote_buf->status == GET_QUOTE_IN_FLIGHT)
+		return -EBUSY;
 
-	if (desc->inblob_len != TDX_REPORTDATA_LEN) {
-		ret = -EINVAL;
-		goto done;
-	}
+	if (desc->inblob_len != TDX_REPORTDATA_LEN)
+		return -EINVAL;
 
 	memset(quote_data, 0, GET_QUOTE_BUF_SIZE);
 
@@ -298,26 +290,23 @@ static int tdx_report_new(struct tsm_report *report, void *data)
 	ret = tdx_do_report(KERNEL_SOCKPTR(desc->inblob),
 			    KERNEL_SOCKPTR(quote_buf->data));
 	if (ret)
-		goto done;
+		return ret;
 
 	err = tdx_hcall_get_quote(quote_data, GET_QUOTE_BUF_SIZE);
 	if (err) {
 		pr_err("GetQuote hypercall failed, status:%llx\n", err);
-		ret = -EIO;
-		goto done;
+		return -EIO;
 	}
 
 	ret = wait_for_quote_completion(quote_buf, getquote_timeout);
 	if (ret) {
 		pr_err("GetQuote request timedout\n");
-		goto done;
+		return ret;
 	}
 
 	buf = kvmemdup(quote_buf->data, quote_buf->out_len, GFP_KERNEL);
-	if (!buf) {
-		ret = -ENOMEM;
-		goto done;
-	}
+	if (!buf)
+		return -ENOMEM;
 
 	report->outblob = buf;
 	report->outblob_len = quote_buf->out_len;
@@ -326,12 +315,16 @@ static int tdx_report_new(struct tsm_report *report, void *data)
 	 * TODO: parse the PEM-formatted cert chain out of the quote buffer when
 	 * provided
 	 */
-done:
-	mutex_unlock(&quote_lock);
 
 	return ret;
 }
 
+static int tdx_report_new(struct tsm_report *report, void *data)
+{
+	scoped_cond_guard(mutex_intr, return -EINTR, &quote_lock)
+		return tdx_report_new_locked(report, data);
+}
+
 static bool tdx_report_attr_visible(int n)
 {
 	switch (n) {

---
