---
title: 'tsm-mr: Unified Measurement Register ABI for TVMs'
date: 2025-04-24
last_reply: 2025-05-01
message_count: 12
participants: ['Cedric Xing', 'Dave Hansen', 'Dan Williams']
---

## [1] Cedric Xing — 2025-04-24

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

Signed-off-by: Cedric Xing <cedric.xing@intel.com>
---
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
Cedric Xing (5):
      tsm-mr: Add TVM Measurement Register support
      tsm-mr: Add tsm-mr sample code
      x86/tdx: Add tdx_mcall_extend_rtmr() interface
      x86/tdx: tdx_mcall_get_report0: Return -EBUSY on TDCALL_OPERAND_BUSY error
      virt: tdx-guest: Expose TDX MRs as sysfs attributes

 .../testing/sysfs-devices-virtual-misc-tdx_guest   |  60 +++++
 Documentation/driver-api/coco/index.rst            |  12 +
 .../driver-api/coco/measurement-registers.rst      |  12 +
 Documentation/driver-api/index.rst                 |   1 +
 MAINTAINERS                                        |   6 +-
 arch/x86/coco/tdx/tdx.c                            |  50 +++-
 arch/x86/include/asm/shared/tdx.h                  |   1 +
 arch/x86/include/asm/tdx.h                         |   2 +
 drivers/virt/coco/Kconfig                          |   5 +
 drivers/virt/coco/Makefile                         |   1 +
 drivers/virt/coco/tdx-guest/Kconfig                |   1 +
 drivers/virt/coco/tdx-guest/tdx-guest.c            | 291 +++++++++++++--------
 drivers/virt/coco/tsm-mr.c                         | 247 +++++++++++++++++
 include/linux/tsm-mr.h                             |  94 +++++++
 include/trace/events/tsm_mr.h                      |  80 ++++++
 samples/Kconfig                                    |  11 +
 samples/Makefile                                   |   1 +
 samples/tsm-mr/Makefile                            |   2 +
 samples/tsm-mr/tsm_mr_sample.c                     | 137 ++++++++++
 19 files changed, 904 insertions(+), 110 deletions(-)
---
base-commit: 9c32cda43eb78f78c73aee4aa344b777714e259b
change-id: 20250209-tdx-rtmr-255479667146

Best regards,

---

## [2] Cedric Xing — 2025-04-24
*Subject: [PATCH v5 1/5] tsm-mr: Add TVM Measurement Register support*

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
---
 Documentation/driver-api/coco/index.rst            |  12 +
 .../driver-api/coco/measurement-registers.rst      |  12 +
 Documentation/driver-api/index.rst                 |   1 +
 MAINTAINERS                                        |   4 +-
 drivers/virt/coco/Kconfig                          |   5 +
 drivers/virt/coco/Makefile                         |   1 +
 drivers/virt/coco/tsm-mr.c                         | 247 +++++++++++++++++++++
 include/linux/tsm-mr.h                             |  94 ++++++++
 include/trace/events/tsm_mr.h                      |  80 +++++++
 9 files changed, 454 insertions(+), 2 deletions(-)

diff --git a/Documentation/driver-api/coco/index.rst b/Documentation/driver-api/coco/index.rst
new file mode 100644
index 000000000000..af9f08ca0cfd
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
index 000000000000..cef85945a9a7
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
index 16e2c4ec3c01..3e2a270bd828 100644
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
index fa1e04e87d1d..1d1426af3a68 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -24616,8 +24616,8 @@ M:	Dan Williams <dan.j.williams@intel.com>
 L:	linux-coco@lists.linux.dev
 S:	Maintained
 F:	Documentation/ABI/testing/configfs-tsm
-F:	drivers/virt/coco/tsm.c
-F:	include/linux/tsm.h
+F:	drivers/virt/coco/tsm*.c
+F:	include/linux/tsm*.h
 
 TRUSTED SERVICES TEE DRIVER
 M:	Balint Dobszay <balint.dobszay@arm.com>
diff --git a/drivers/virt/coco/Kconfig b/drivers/virt/coco/Kconfig
index ff869d883d95..737106d5dcbc 100644
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
index c3d07cfc087e..eb6ec5c1d2e1 100644
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
index 000000000000..adc32328018e
--- /dev/null
+++ b/drivers/virt/coco/tsm-mr.c
@@ -0,0 +1,247 @@
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
+			rc = ctx->tm->refresh(ctx->tm, mr);
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
+	trace_tsm_mr_write(mr, buffer);
+
+	rc = down_write_killable(&ctx->rwsem);
+	if (rc)
+		return rc;
+
+	rc = ctx->tm->write(ctx->tm, mr, buffer);
+
+	/* mark MR cache stale */
+	if (!rc)
+		ctx->in_sync = false;
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
+	ctx->agrp.name = "mr";
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
index 000000000000..3d4576849885
--- /dev/null
+++ b/include/linux/tsm-mr.h
@@ -0,0 +1,94 @@
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
+ * @refresh takes two parameters:
+ *
+ * * @tm - points back to this structure.
+ * * @mr - points to the MR (an element of @mrs) being read (hence triggered
+ *   this callback).
+ *
+ * Note that @refresh is invoked only when an MR with %TSM_MR_F_LIVE set is
+ * being read and the cache is stale. However, @refresh must reload not only
+ * the MR being read (@mr) but also all MRs with %TSM_MR_F_LIVE set.
+ *
+ * @write takes an additional parameter besides @tm and @mr:
+ *
+ * * @data - contains the bytes to write and whose size is @mr->mr_size.
+ *
+ * Both @refresh and @write should return 0 on success and an appropriate error
+ * code on failure.
+ */
+struct tsm_measurements {
+	const struct tsm_measurement_register *mrs;
+	size_t nr_mrs;
+	int (*refresh)(const struct tsm_measurements *tm,
+		       const struct tsm_measurement_register *mr);
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
index 000000000000..f40de4ad3e2d
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

## [3] Cedric Xing — 2025-04-24
*Subject: [PATCH v5 2/5] tsm-mr: Add tsm-mr sample code*

This sample kernel module demonstrates how to make MRs accessible to user
mode through the tsm-mr library.

Once loaded, this module registers a `miscdevice` that host a set of
emulated measurement registers as shown in the directory tree below.

/sys/class/misc/tsm_mr_sample
└── mr
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
---
 MAINTAINERS                    |   1 +
 samples/Kconfig                |  11 ++++
 samples/Makefile               |   1 +
 samples/tsm-mr/Makefile        |   2 +
 samples/tsm-mr/tsm_mr_sample.c | 137 +++++++++++++++++++++++++++++++++++++++++
 5 files changed, 152 insertions(+)

diff --git a/MAINTAINERS b/MAINTAINERS
index 1d1426af3a68..fd5bbf78ec8b 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -24618,6 +24618,7 @@ S:	Maintained
 F:	Documentation/ABI/testing/configfs-tsm
 F:	drivers/virt/coco/tsm*.c
 F:	include/linux/tsm*.h
+F:	samples/tsm/*
 
 TRUSTED SERVICES TEE DRIVER
 M:	Balint Dobszay <balint.dobszay@arm.com>
diff --git a/samples/Kconfig b/samples/Kconfig
index 09011be2391a..6ade17cb16b4 100644
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
index bf6e6fca5410..c95bac31851c 100644
--- a/samples/Makefile
+++ b/samples/Makefile
@@ -43,3 +43,4 @@ obj-$(CONFIG_SAMPLES_RUST)		+= rust/
 obj-$(CONFIG_SAMPLE_DAMON_WSSE)		+= damon/
 obj-$(CONFIG_SAMPLE_DAMON_PRCL)		+= damon/
 obj-$(CONFIG_SAMPLE_HUNG_TASK)		+= hung_task/
+obj-$(CONFIG_SAMPLE_TSM_MR)		+= tsm-mr/
diff --git a/samples/tsm-mr/Makefile b/samples/tsm-mr/Makefile
new file mode 100644
index 000000000000..587c3947b3a7
--- /dev/null
+++ b/samples/tsm-mr/Makefile
@@ -0,0 +1,2 @@
+# SPDX-License-Identifier: GPL-2.0-only
+obj-$(CONFIG_SAMPLE_TSM_MR) += tsm_mr_sample.o
diff --git a/samples/tsm-mr/tsm_mr_sample.c b/samples/tsm-mr/tsm_mr_sample.c
new file mode 100644
index 000000000000..3ee35d87d275
--- /dev/null
+++ b/samples/tsm-mr/tsm_mr_sample.c
@@ -0,0 +1,137 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/* Copyright(c) 2024 Intel Corporation. All rights reserved. */
+
+#define DEBUG
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
+static int sample_report_refresh(const struct tsm_measurements *tm,
+				 const struct tsm_measurement_register *mr)
+{
+	struct crypto_shash *tfm;
+	int rc;
+
+	pr_debug("%s(%s) is called\n", __func__, mr ? mr->mr_name : "<nil>");
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
+	pr_debug("%s(%s) is called\n", __func__, mr->mr_name);
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

## [4] Cedric Xing — 2025-04-24
*Subject: [PATCH v5 3/5] x86/tdx: Add tdx_mcall_extend_rtmr() interface*

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
 arch/x86/coco/tdx/tdx.c           | 37 +++++++++++++++++++++++++++++++++++++
 arch/x86/include/asm/shared/tdx.h |  1 +
 arch/x86/include/asm/tdx.h        |  2 ++
 3 files changed, 40 insertions(+)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index edab6d6049be..0b6804d2a5e1 100644
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
index a28ff6b14145..738f583f65cb 100644
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
index 4a1922ec80cf..12d17f3ca301 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -64,6 +64,8 @@ bool tdx_early_handle_ve(struct pt_regs *regs);
 
 int tdx_mcall_get_report0(u8 *reportdata, u8 *tdreport);
 
+int tdx_mcall_extend_rtmr(u8 index, u8 *data);
+
 u64 tdx_hcall_get_quote(u8 *buf, size_t size);
 
 void __init tdx_dump_attributes(u64 td_attr);

---

## [5] Cedric Xing — 2025-04-24
*Subject: [PATCH v5 4/5] x86/tdx: tdx_mcall_get_report0: Return -EBUSY on
 TDCALL_OPERAND_BUSY error*

Return `-EBUSY` from tdx_mcall_get_report0() when `TDG.MR.REPORT` returns
`TDCALL_OPERAND_BUSY`. This enables the caller to retry obtaining a
TDREPORT later if another VCPU is extending an RTMR concurrently.

Signed-off-by: Cedric Xing <cedric.xing@intel.com>
---
 arch/x86/coco/tdx/tdx.c | 13 ++++++++-----
 1 file changed, 8 insertions(+), 5 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 0b6804d2a5e1..7b2833705d47 100644
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

## [6] Cedric Xing — 2025-04-24
*Subject: [PATCH v5 5/5] virt: tdx-guest: Expose TDX MRs as sysfs attributes*

Expose the most commonly used TDX MRs (Measurement Registers) as sysfs
attributes. Use the ioctl() interface of /dev/tdx_guest to request a full
TDREPORT for access to other TD measurements.

Directory structure of TDX MRs inside a TDVM is as follows:

/sys/class/misc/tdx_guest
└── mr
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
---
 .../testing/sysfs-devices-virtual-misc-tdx_guest   |  60 +++++
 MAINTAINERS                                        |   1 +
 drivers/virt/coco/tdx-guest/Kconfig                |   1 +
 drivers/virt/coco/tdx-guest/tdx-guest.c            | 291 +++++++++++++--------
 4 files changed, 250 insertions(+), 103 deletions(-)

diff --git a/Documentation/ABI/testing/sysfs-devices-virtual-misc-tdx_guest b/Documentation/ABI/testing/sysfs-devices-virtual-misc-tdx_guest
new file mode 100644
index 000000000000..fb7b27ae0b74
--- /dev/null
+++ b/Documentation/ABI/testing/sysfs-devices-virtual-misc-tdx_guest
@@ -0,0 +1,60 @@
+What:		/sys/devices/virtual/misc/tdx_guest/mr/MRNAME[:HASH]
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
+What:		/sys/devices/virtual/misc/tdx_guest/mr/mrconfigid
+Date:		April, 2025
+KernelVersion:	v6.16
+Contact:	linux-coco@lists.linux.dev
+Description:
+		(RO) MRCONFIGID - 48-byte immutable storage typically used for
+		software-defined ID for non-owner-defined configuration of the
+		guest TD – e.g., run-time or OS configuration.
+
+What:		/sys/devices/virtual/misc/tdx_guest/mr/mrowner
+Date:		April, 2025
+KernelVersion:	v6.16
+Contact:	linux-coco@lists.linux.dev
+Description:
+		(RO) MROWNER - 48-byte immutable storage typically used for
+		software-defined ID for the guest TD’s owner.
+
+What:		/sys/devices/virtual/misc/tdx_guest/mr/mrownerconfig
+Date:		April, 2025
+KernelVersion:	v6.16
+Contact:	linux-coco@lists.linux.dev
+Description:
+		(RO) MROWNERCONFIG - 48-byte immutable storage typically used
+		for software-defined ID for owner-defined configuration of the
+		guest TD – e.g., specific to the workload rather than the
+		run-time or OS.
+
+What:		/sys/devices/virtual/misc/tdx_guest/mr/mrtd:sha384
+Date:		April, 2025
+KernelVersion:	v6.16
+Contact:	linux-coco@lists.linux.dev
+Description:
+		(RO) MRTD - Measurement of the initial contents of the TD.
+
+What:		/sys/devices/virtual/misc/tdx_guest/mr/rtmr[0123]:sha384
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
index fd5bbf78ec8b..3afbf6c310a7 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -26284,6 +26284,7 @@ L:	x86@kernel.org
 L:	linux-coco@lists.linux.dev
 S:	Supported
 T:	git git://git.kernel.org/pub/scm/linux/kernel/git/tip/tip.git x86/tdx
+F:	Documentation/ABI/testing/sysfs-devices-virtual-misc-tdx_guest
 F:	arch/x86/boot/compressed/tdx*
 F:	arch/x86/coco/tdx/
 F:	arch/x86/include/asm/shared/tdx.h
diff --git a/drivers/virt/coco/tdx-guest/Kconfig b/drivers/virt/coco/tdx-guest/Kconfig
index 22dd59e19431..dbbdc14383b1 100644
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
index 224e7dde9cde..e76810d89e0b 100644
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
@@ -15,8 +17,9 @@
 #include <linux/set_memory.h>
 #include <linux/io.h>
 #include <linux/delay.h>
+#include <linux/sockptr.h>
 #include <linux/tsm.h>
-#include <linux/sizes.h>
+#include <linux/tsm-mr.h>
 
 #include <uapi/linux/tdx-guest.h>
 
@@ -66,39 +69,144 @@ static DEFINE_MUTEX(quote_lock);
  */
 static u32 getquote_timeout = 30;
 
-static long tdx_get_report0(struct tdx_report_req __user *req)
+/* Buffers for TDREPORT and RTMR extension */
+static u8 *tdx_report_buf, *tdx_extend_buf;
+
+/* Lock to serialize TDG.MR.REPORT & TDG.MR.RTMR.EXTEND requests */
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
+static inline int tdx_mr_report_locked(sockptr_t data, sockptr_t tdreport)
 {
-	u8 *reportdata, *tdreport;
-	long ret;
+	scoped_cond_guard(mutex_intr, return -EINTR, &mr_lock) {
+		u8 *p = tdx_report_buf + TDREPORT_reportdata;
+		int ret;
 
-	reportdata = kmalloc(TDX_REPORTDATA_LEN, GFP_KERNEL);
-	if (!reportdata)
-		return -ENOMEM;
+		if (!sockptr_is_null(data) &&
+		    copy_from_sockptr(p, data, TDX_REPORTDATA_LEN))
+			return -EFAULT;
 
-	tdreport = kzalloc(TDX_REPORT_LEN, GFP_KERNEL);
-	if (!tdreport) {
-		ret = -ENOMEM;
-		goto out;
+		ret = tdx_mcall_get_report0(p, tdx_report_buf);
+		if (WARN(ret, "tdx_mcall_get_report0() failed: %d", ret))
+			return ret;
+
+		if (!sockptr_is_null(tdreport) &&
+		    copy_to_sockptr(tdreport, tdx_report_buf, TDX_REPORT_LEN))
+			return -EFAULT;
 	}
+	return 0;
+}
 
-	if (copy_from_user(reportdata, req->reportdata, TDX_REPORTDATA_LEN)) {
-		ret = -EFAULT;
-		goto out;
+static inline int tdx_mr_extend_locked(ptrdiff_t mr_ind, const u8 *data)
+{
+	scoped_cond_guard(mutex_intr, return -EINTR, &mr_lock) {
+		int ret;
+
+		memcpy(tdx_extend_buf, data, SHA384_DIGEST_SIZE);
+
+		ret = tdx_mcall_extend_rtmr(mr_ind, tdx_extend_buf);
+		if (WARN(ret, "tdx_mcall_extend_rtmr(%ld) failed: %d", mr_ind, ret))
+			return ret;
 	}
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
+static int tdx_mr_refresh(const struct tsm_measurements *tm,
+			  const struct tsm_measurement_register *mr)
+{
+	return tdx_mr_report_locked(KERNEL_SOCKPTR(NULL), KERNEL_SOCKPTR(NULL));
+}
 
-	/* Generate TDREPORT0 using "TDG.MR.REPORT" TDCALL */
-	ret = tdx_mcall_get_report0(reportdata, tdreport);
+static int tdx_mr_extend(const struct tsm_measurements *tm,
+			 const struct tsm_measurement_register *mr,
+			 const u8 *data)
+{
+	return tdx_mr_extend_locked(mr - tm->mrs, data);
+}
+
+static struct tsm_measurements tdx_measurements = {
+	.mrs = tdx_mrs,
+	.nr_mrs = ARRAY_SIZE(tdx_mrs),
+	.refresh = tdx_mr_refresh,
+	.write = tdx_mr_extend,
+};
+
+/* attribute groups of tdx_misc_dev */
+static const struct attribute_group *tdx_attr_groups[] = {
+	NULL,
+	NULL,
+};
+
+static int tdx_mr_init(void)
+{
+	int ret;
+
+	u8 *report_buf __free(kfree) = kzalloc(TDX_REPORT_LEN, GFP_KERNEL);
+
+	/* TDG.MR.RTMR.EXTEND requires 64-byte aligned input */
+	u8 *extend_buf __free(kfree) = kmalloc(64, GFP_KERNEL);
+
+	if (!report_buf || !extend_buf)
+		return -ENOMEM;
+
+	tdx_report_buf = report_buf;
+	ret = tdx_mr_refresh(&tdx_measurements, NULL);
 	if (ret)
-		goto out;
+		return ret;
 
-	if (copy_to_user(req->tdreport, tdreport, TDX_REPORT_LEN))
-		ret = -EFAULT;
+	for (size_t i = 0; i < ARRAY_SIZE(tdx_mrs); ++i)
+		*(long *)&tdx_mrs[i].mr_value += (long)report_buf;
 
-out:
-	kfree(reportdata);
-	kfree(tdreport);
+	tdx_attr_groups[0] = tsm_mr_create_attribute_group(&tdx_measurements);
+	if (IS_ERR(tdx_attr_groups[0]))
+		return PTR_ERR(tdx_attr_groups[0]);
 
-	return ret;
+	tdx_report_buf = no_free_ptr(report_buf);
+	tdx_extend_buf = no_free_ptr(extend_buf);
+	return 0;
+}
+
+static void tdx_mr_deinit(void)
+{
+	tsm_mr_free_attribute_group(tdx_attr_groups[0]);
+	kfree(tdx_extend_buf);
+	kfree(tdx_report_buf);
+}
+
+static long tdx_get_report0(struct tdx_report_req __user *req)
+{
+	return tdx_mr_report_locked(USER_SOCKPTR(req->reportdata),
+				    USER_SOCKPTR(req->tdreport));
 }
 
 static void free_quote_buf(void *buf)
@@ -159,91 +267,60 @@ static int wait_for_quote_completion(struct tdx_quote_buf *quote_buf, u32 timeou
 
 static int tdx_report_new(struct tsm_report *report, void *data)
 {
-	u8 *buf, *reportdata = NULL, *tdreport = NULL;
+	u8 *buf;
 	struct tdx_quote_buf *quote_buf = quote_data;
 	struct tsm_desc *desc = &report->desc;
 	int ret;
 	u64 err;
 
-	/* TODO: switch to guard(mutex_intr) */
-	if (mutex_lock_interruptible(&quote_lock))
-		return -EINTR;
-
-	/*
-	 * If the previous request is timedout or interrupted, and the
-	 * Quote buf status is still in GET_QUOTE_IN_FLIGHT (owned by
-	 * VMM), don't permit any new request.
-	 */
-	if (quote_buf->status == GET_QUOTE_IN_FLIGHT) {
-		ret = -EBUSY;
-		goto done;
-	}
-
-	if (desc->inblob_len != TDX_REPORTDATA_LEN) {
-		ret = -EINVAL;
-		goto done;
-	}
-
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
+	scoped_cond_guard(mutex_intr, ret = -EINTR, &quote_lock) {
+		/*
+		 * If the previous request is timedout or interrupted, and the
+		 * Quote buf status is still in GET_QUOTE_IN_FLIGHT (owned by
+		 * VMM), don't permit any new request.
+		 */
+		if (quote_buf->status == GET_QUOTE_IN_FLIGHT)
+			return -EBUSY;
+
+		if (desc->inblob_len != TDX_REPORTDATA_LEN)
+			return -EINVAL;
+
+		memset(quote_data, 0, GET_QUOTE_BUF_SIZE);
+
+		/* Update Quote buffer header */
+		quote_buf->version = GET_QUOTE_CMD_VER;
+		quote_buf->in_len = TDX_REPORT_LEN;
+
+		/* Generate TDREPORT0 using "TDG.MR.REPORT" TDCALL */
+		ret = tdx_mr_report_locked(KERNEL_SOCKPTR(desc->inblob),
+					   KERNEL_SOCKPTR(quote_buf->data));
+		if (ret)
+			break;
+
+		err = tdx_hcall_get_quote(quote_data, GET_QUOTE_BUF_SIZE);
+		if (err) {
+			pr_err("GetQuote hypercall failed, status:%llx\n", err);
+			return -EIO;
+		}
+
+		ret = wait_for_quote_completion(quote_buf, getquote_timeout);
+		if (ret) {
+			pr_err("GetQuote request timedout\n");
+			break;
+		}
+
+		buf = kvmemdup(quote_buf->data, quote_buf->out_len, GFP_KERNEL);
+		if (!buf)
+			return -ENOMEM;
+
+		report->outblob = buf;
+		report->outblob_len = quote_buf->out_len;
+
+		/*
+		 * TODO: parse the PEM-formatted cert chain out of the quote
+		 * buffer when provided
+		 */
 	}
-
-	memset(quote_data, 0, GET_QUOTE_BUF_SIZE);
-
-	/* Update Quote buffer header */
-	quote_buf->version = GET_QUOTE_CMD_VER;
-	quote_buf->in_len = TDX_REPORT_LEN;
-
-	memcpy(quote_buf->data, tdreport, TDX_REPORT_LEN);
-
-	err = tdx_hcall_get_quote(quote_data, GET_QUOTE_BUF_SIZE);
-	if (err) {
-		pr_err("GetQuote hypercall failed, status:%llx\n", err);
-		ret = -EIO;
-		goto done;
-	}
-
-	ret = wait_for_quote_completion(quote_buf, getquote_timeout);
-	if (ret) {
-		pr_err("GetQuote request timedout\n");
-		goto done;
-	}
-
-	buf = kvmemdup(quote_buf->data, quote_buf->out_len, GFP_KERNEL);
-	if (!buf) {
-		ret = -ENOMEM;
-		goto done;
-	}
-
-	report->outblob = buf;
-	report->outblob_len = quote_buf->out_len;
-
-	/*
-	 * TODO: parse the PEM-formatted cert chain out of the quote buffer when
-	 * provided
-	 */
-done:
-	mutex_unlock(&quote_lock);
-	kfree(reportdata);
-	kfree(tdreport);
-
 	return ret;
 }
 
@@ -289,6 +366,7 @@ static struct miscdevice tdx_misc_dev = {
 	.name = KBUILD_MODNAME,
 	.minor = MISC_DYNAMIC_MINOR,
 	.fops = &tdx_guest_fops,
+	.groups = tdx_attr_groups,
 };
 
 static const struct x86_cpu_id tdx_guest_ids[] = {
@@ -311,10 +389,14 @@ static int __init tdx_guest_init(void)
 	if (!x86_match_cpu(tdx_guest_ids))
 		return -ENODEV;
 
-	ret = misc_register(&tdx_misc_dev);
+	ret = tdx_mr_init();
 	if (ret)
 		return ret;
 
+	ret = misc_register(&tdx_misc_dev);
+	if (ret)
+		goto free_tsm_mr;
+
 	quote_data = alloc_quote_buf();
 	if (!quote_data) {
 		pr_err("Failed to allocate Quote buffer\n");
@@ -332,6 +414,8 @@ static int __init tdx_guest_init(void)
 	free_quote_buf(quote_data);
 free_misc:
 	misc_deregister(&tdx_misc_dev);
+free_tsm_mr:
+	tdx_mr_deinit();
 
 	return ret;
 }
@@ -342,6 +426,7 @@ static void __exit tdx_guest_exit(void)
 	tsm_unregister(&tdx_tsm_ops);
 	free_quote_buf(quote_data);
 	misc_deregister(&tdx_misc_dev);
+	tdx_mr_deinit();
 }
 module_exit(tdx_guest_exit);

---

## [7] Dave Hansen — 2025-05-01
*Subject: Re: [PATCH v5 3/5] x86/tdx: Add tdx_mcall_extend_rtmr() interface*

On 4/24/25 13:12, Cedric Xing wrote:
> The TDX guest exposes one MRTD (Build-time Measurement Register) and four
> RTMR (Run-time Measurement Register) registers to record the build and boot

Thank you for revising the changelogs to make the underlying purpose of
this series more clear.

Acked-by: Dave Hansen <dave.hansen@linux.intel.com>

---

## [8] Dave Hansen — 2025-05-01
*Subject: Re: [PATCH v5 4/5] x86/tdx: tdx_mcall_get_report0: Return -EBUSY on
 TDCALL_OPERAND_BUSY error*

On 4/24/25 13:12, Cedric Xing wrote:
> Return `-EBUSY` from tdx_mcall_get_report0() when `TDG.MR.REPORT` returns
> `TDCALL_OPERAND_BUSY`. This enables the caller to retry obtaining a
I would appreciate if someone can go back and look at centralizing the
TDX error code => errno conversions. But that doesn't need to happen now.

Acked-by: Dave Hansen <dave.hansen@linux.intel.com>

---

## [9] Dave Hansen — 2025-05-01
*Subject: Re: [PATCH v5 3/5] x86/tdx: Add tdx_mcall_extend_rtmr() interface*

On 4/24/25 13:12, Cedric Xing wrote:
> +	ret = __tdcall(TDG_MR_RTMR_EXTEND, &args);
> +	if (ret) {
This a pretty ugly switch statement. ;)

I assume there are more of these around, but it would be _nice_ if these
could eventually look like:

	...
	err = __tdcall(...);

	return tdx_err_to_errno(err);

---

## [10] Dan Williams — 2025-05-01
*Subject: Re: [PATCH v5 1/5] tsm-mr: Add TVM Measurement Register support*

Cedric Xing wrote:
> Introduce new TSM Measurement helper library (tsm-mr) for TVM guest drivers
> to expose MRs (Measurement Registers) as sysfs attributes, with Crypto

Looking good, some minor fixups below.

> ---
>  Documentation/driver-api/coco/index.rst            |  12 +

Should also add Documentation/driver-api/coco/ here.

>  
>  TRUSTED SERVICES TEE DRIVER

I would have expected the trace to be emitted after the write succeeds,
otherwise this tracepoint is "may have written" vs "write".

> +
> +	rc = down_write_killable(&ctx->rwsem);

...also, putting the trace here means the trace event is known to be
ordered by the rwsem.

[..]

Other than the above you can add:

Reviewed-by: Dan Williams <dan.j.williams@intel.com>

---

## [11] Dan Williams — 2025-05-01
*Subject: Re: [PATCH v5 2/5] tsm-mr: Add tsm-mr sample code*

Cedric Xing wrote:
> This sample kernel module demonstrates how to make MRs accessible to user
> mode through the tsm-mr library.

2024-2025

> +
> +#define DEBUG

No need for this. Either the person trying out this sample driver will
define DEBUG at compile time, manually add this line, or otherwise use
dynamic-debug to enable the pr_debug() statements when loading the
module.

If you put #define DEBUG directly in the file then pr_debug() just
becomes printk() which defeats the purpose.

> +#define pr_fmt(x) KBUILD_MODNAME ": " x
> +

With dynamic-debug the function name can be enabled, so no need to
include that in the debug statement.

See "Decorator flags add to the message-prefix" in
Documentation/admin-guide/dynamic-debug-howto.rst.

Other than that this looks good to me:

Reviewed-by: Dan Williams <dan.j.williams@intel.com>

---

## [12] Dan Williams — 2025-05-01
*Subject: Re: [PATCH v5 5/5] virt: tdx-guest: Expose TDX MRs as sysfs
 attributes*

Cedric Xing wrote:
> Expose the most commonly used TDX MRs (Measurement Registers) as sysfs
> attributes. Use the ioctl() interface of /dev/tdx_guest to request a full

I missed this on patch1, but I am still not a fan of this attribute
directory being called "mr". Please make it "measurement_registers" or
"measurements" to remove ambiguity.

> +Date:		April, 2025
> +KernelVersion:	v6.16

Documentation indeed looks better now. I had also been wanting this ABI
documentation to refer to a generic description of how
measurement-register sysfs files behave. I think you can achieve that
simply with a link back to the generated driver-api kdoc:

https://docs.kernel.org/driver-api/coco/measurement-registers.html

Of course, that link will start resolving once this is upstream.

[..]
> diff --git a/MAINTAINERS b/MAINTAINERS
> index fd5bbf78ec8b..3afbf6c310a7 100644

Why a new @mr_lock when @quote_lock exists? Are they not protecting the
same things?

> +		u8 *p = tdx_report_buf + TDREPORT_reportdata;
> +		int ret;

Ok, the above hunk is an example that this patch is doing too much at
once and making the conversion unnecessarily difficult to follow.

There are 3 separate topics in this patch that deserve to be split into
3 patches:

1) Convert tdx_guest to cleanup helpers

   Now, I do not personally like the fact that conversion to
   scoped_cond_guard() causes a bunch of code to be re-indented, that is
   messy. One alternative to scoped_cond_guard() that I have been
   considering based on feedback Linus gave when that helper was
   introduced is instead do something like this:
   
   DEFINE_FREE(mutex_intr_release, struct mutex, if (_T) mutex_unlock(_T))
   static struct mutex *mutex_intr_acquire(struct mutex *lock)
   {
   	if (mutex_lock_interruptible(lock))
   		return lock;
   	return NULL;
   }
   
   ...then you can do:
   
   struct mutex *lock __free(mutex_intr_release) = mutex_intr_acquire(&mr_lock);
   
   Where that allows you to not need to re-indent the whole function.
   
   If the lock has limited scope within a function then just move that bit
   to a helper function rather than re-indent existing code.

2) Conversion to sockptr. Prepare the report retrieval code to
   alternatively store into kernel or user buffers.

3) RTMR support on top of that converted / cleaned-up base. This will be
   much easier to read withtout the re-indentation mess and other unrelated code
   movement. Just a clean feature addition patch.

---
