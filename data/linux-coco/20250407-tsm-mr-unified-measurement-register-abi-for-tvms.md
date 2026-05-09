---
title: 'tsm-mr: Unified Measurement Register ABI for TVMs'
date: 2025-04-07
last_reply: 2025-04-11
message_count: 15
participants: ['Cedric Xing', 'Dan Williams', 'kernel test robot']
---

## [1] Cedric Xing — 2025-04-07

NOTE: This patch series introduces the Measurement Register (MR) ABI, and
is a continuation of the RFC series on the same topic [1].

Introduce the CONFIG_TSM_MEASUREMENTS helper library (tsm-mr) as a
cross-vendor transport schema to allow TVM (TEE VM) guest drives to export
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
Changes in v3:
- tsm-mr: Separate measurement support (tsm-mr) from the original tsm
  source code. Modules depending on tsm-mr should `select TSM_MEASUREMENTS`
  in Kconfig.
- tsm-mr: Revise tsm-mr APIs to allow callers to decide where to host the
  MR attributes in sysfs.
- tsm-mr: Drop TSM_MR_F_EXTENSIBLE and route all "write" requests to the CC
  guest driver, which would decide how to handle writes (e.g., as extension
  to the specified MR).
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

 .../sysfs-devices-virtual-misc-tdx_guest-mr        |  48 +++++
 MAINTAINERS                                        |   6 +-
 arch/x86/coco/tdx/tdx.c                            |  42 ++++-
 arch/x86/include/asm/shared/tdx.h                  |   1 +
 arch/x86/include/asm/tdx.h                         |   2 +
 drivers/virt/coco/Kconfig                          |   5 +
 drivers/virt/coco/Makefile                         |   1 +
 drivers/virt/coco/tdx-guest/Kconfig                |   1 +
 drivers/virt/coco/tdx-guest/tdx-guest.c            | 169 ++++++++++++++++-
 drivers/virt/coco/tsm-mr.c                         | 209 +++++++++++++++++++++
 include/linux/tsm-mr.h                             |  93 +++++++++
 samples/Kconfig                                    |  10 +
 samples/Makefile                                   |   1 +
 samples/tsm-mr/Makefile                            |   2 +
 samples/tsm-mr/tsm_mr_sample.c                     | 138 ++++++++++++++
 15 files changed, 722 insertions(+), 6 deletions(-)
---
base-commit: 0af2f6be1b4281385b618cb86ad946eded089ac8
change-id: 20250209-tdx-rtmr-255479667146

Best regards,

---

## [2] Cedric Xing — 2025-04-07
*Subject: [PATCH v3 1/5] tsm-mr: Add TVM Measurement Register support*

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
 MAINTAINERS                |   4 +-
 drivers/virt/coco/Kconfig  |   5 ++
 drivers/virt/coco/Makefile |   1 +
 drivers/virt/coco/tsm-mr.c | 209 +++++++++++++++++++++++++++++++++++++++++++++
 include/linux/tsm-mr.h     |  93 ++++++++++++++++++++
 5 files changed, 310 insertions(+), 2 deletions(-)

diff --git a/MAINTAINERS b/MAINTAINERS
index 96b827049501..df3aada3ada6 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -24558,8 +24558,8 @@ M:	Dan Williams <dan.j.williams@intel.com>
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
index 000000000000..695ac28530e3
--- /dev/null
+++ b/drivers/virt/coco/tsm-mr.c
@@ -0,0 +1,209 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/* Copyright(c) 2024-2025 Intel Corporation. All rights reserved. */
+
+#define pr_fmt(fmt) KBUILD_MODNAME ": " fmt
+
+#include <linux/module.h>
+#include <linux/slab.h>
+#include <linux/sysfs.h>
+#include <linux/tsm-mr.h>
+
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
+	/*
+	 * @ctx->in_sync indicates if any MRs have been written since the last
+	 * ctx->refresh() call. When @ctx->in_sync is false, ctx->refresh() is
+	 * necessary to sync the cached values of all live MRs (i.e., with
+	 * %TSM_MR_F_LIVE set) with the underlying hardware.
+	 */
+	mr = &ctx->tm->mrs[attr - ctx->mrs];
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
+		}
+
+		downgrade_write(&ctx->rwsem);
+	}
+
+	memcpy(buffer, mr->mr_value + off, count);
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
+	/* reset @ctx->in_sync to refresh LIVE MRs on next read */
+	if (!rc)
+		ctx->in_sync = false;
+
+	up_write(&ctx->rwsem);
+	return rc ?: count;
+}
+
+/**
+ * tsm_mr_create_attribute_group() - creates an attribute group for measurement
+ * registers
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
+const struct attribute_group *__must_check
+tsm_mr_create_attribute_group(const struct tsm_measurements *tm)
+{
+	if (!tm->mrs)
+		return ERR_PTR(-EINVAL);
+
+	/* aggregated length of all MR names */
+	size_t nlen = 0;
+
+	for (size_t i = 0; i < tm->nr_mrs; ++i) {
+		if ((tm->mrs[i].mr_flags & TSM_MR_F_LIVE) && !tm->refresh)
+			return ERR_PTR(-EINVAL);
+
+		if ((tm->mrs[i].mr_flags & TSM_MR_F_WRITABLE) && !tm->write)
+			return ERR_PTR(-EINVAL);
+
+		if (tm->mrs[i].mr_flags & TSM_MR_F_NOHASH)
+			continue;
+
+		if (WARN_ON(tm->mrs[i].mr_hash >= HASH_ALGO__LAST))
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
+			bas[i]->attr.mode |= 0220;
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
+	ctx->agrp.name = tm->name;
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
+	kfree(attr_grp->bin_attrs);
+	kfree(container_of(attr_grp, struct tm_context, agrp));
+}
+EXPORT_SYMBOL_GPL(tsm_mr_free_attribute_group);
diff --git a/include/linux/tsm-mr.h b/include/linux/tsm-mr.h
new file mode 100644
index 000000000000..94a14d48a012
--- /dev/null
+++ b/include/linux/tsm-mr.h
@@ -0,0 +1,93 @@
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
+ * struct tsm_measurements - Defines the CC-specific measurement facility and
+ * methods for updating measurement registers (MRs).
+ * @name: Optional parent directory name.
+ * @mrs: Array of MR definitions.
+ * @nr_mrs: Number of elements in @mrs.
+ * @refresh: Callback function to load/sync all MRs from TVM hardware/firmware
+ *           into the kernel cache.
+ * @write: Callback function to write to the MR specified by the parameter @mr.
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
+	const char *name;
+	const struct tsm_measurement_register *mrs __counted_by(nr_mrs);
+	size_t nr_mrs;
+	int (*refresh)(const struct tsm_measurements *tm,
+		       const struct tsm_measurement_register *mr);
+	int (*write)(const struct tsm_measurements *tm,
+		     const struct tsm_measurement_register *mr, const u8 *data);
+};
+
+const struct attribute_group *__must_check
+tsm_mr_create_attribute_group(const struct tsm_measurements *tm);
+void tsm_mr_free_attribute_group(const struct attribute_group *attr_grp);
+
+#endif

---

## [3] Cedric Xing — 2025-04-07
*Subject: [PATCH v3 2/5] tsm-mr: Add tsm-mr sample code*

This sample kernel module demonstrates how to make MRs accessible to user
mode through the tsm-mr library.

Once loaded, this module registers a `miscdevice` that host a set of
emulated measurement registers as shown in the directory tree below.

/sys/class/misc/tsm_mr_sample
└── emulated_mr
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
 samples/Kconfig                |  10 +++
 samples/Makefile               |   1 +
 samples/tsm-mr/Makefile        |   2 +
 samples/tsm-mr/tsm_mr_sample.c | 138 +++++++++++++++++++++++++++++++++++++++++
 5 files changed, 152 insertions(+)

diff --git a/MAINTAINERS b/MAINTAINERS
index df3aada3ada6..b210ac3389a7 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -24560,6 +24560,7 @@ S:	Maintained
 F:	Documentation/ABI/testing/configfs-tsm
 F:	drivers/virt/coco/tsm*.c
 F:	include/linux/tsm*.h
+F:	samples/tsm/*
 
 TRUSTED SERVICES TEE DRIVER
 M:	Balint Dobszay <balint.dobszay@arm.com>
diff --git a/samples/Kconfig b/samples/Kconfig
index 09011be2391a..828bc4bebde8 100644
--- a/samples/Kconfig
+++ b/samples/Kconfig
@@ -184,6 +184,16 @@ config SAMPLE_TIMER
 	bool "Timer sample"
 	depends on CC_CAN_LINK && HEADERS_INSTALL
 
+config SAMPLE_TSM_MR
+	tristate "TSM measurement sample"
+	select TSM_MEASUREMENTS
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
index 000000000000..163f0f56e165
--- /dev/null
+++ b/samples/tsm-mr/tsm_mr_sample.c
@@ -0,0 +1,138 @@
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
+static const struct tsm_measurement_register emulated_mrs[] = {
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
+static struct tsm_measurements emulated_mr = {
+	.name = "emulated_mr",
+	.mrs = emulated_mrs,
+	.nr_mrs = ARRAY_SIZE(emulated_mrs),
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
+	sample_groups[0] = tsm_mr_create_attribute_group(&emulated_mr);
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

## [4] Cedric Xing — 2025-04-07
*Subject: [PATCH v3 3/5] x86/tdx: Add tdx_mcall_extend_rtmr() interface*

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
index edab6d6049be..b042ca74bcd3 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -36,6 +36,7 @@
 /* TDX Module call error codes */
 #define TDCALL_RETURN_CODE(a)	((a) >> 32)
 #define TDCALL_INVALID_OPERAND	0xc0000100
+#define TDCALL_OPERAND_BUSY	0x80000200
 
 #define TDREPORT_SUBTYPE_0	0
 
@@ -136,6 +137,41 @@ int tdx_mcall_get_report0(u8 *reportdata, u8 *tdreport)
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

## [5] Cedric Xing — 2025-04-07
*Subject: [PATCH v3 4/5] x86/tdx: tdx_mcall_get_report0: Return -EBUSY on
 TDCALL_OPERAND_BUSY error*

Return `-EBUSY` from tdx_mcall_get_report0() when `TDG.MR.REPORT` returns
`TDCALL_OPERAND_BUSY`. This enables the caller to retry obtaining a
TDREPORT later if another VCPU is extending an RTMR concurrently.

Signed-off-by: Cedric Xing <cedric.xing@intel.com>
---
 arch/x86/coco/tdx/tdx.c | 6 ++++--
 1 file changed, 4 insertions(+), 2 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index b042ca74bcd3..c94e0061fe53 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -114,8 +114,8 @@ static inline u64 tdg_vm_wr(u64 field, u64 value, u64 mask)
  * v1.0 specification for more information on TDG.MR.REPORT TDCALL.
  * It is used in the TDX guest driver module to get the TDREPORT0.
  *
- * Return 0 on success, -EINVAL for invalid operands, or -EIO on
- * other TDCALL failures.
+ * Return 0 on success, -EINVAL for invalid operands, -EBUSY for busy
+ * operation or -EIO on other TDCALL failures.
  */
 int tdx_mcall_get_report0(u8 *reportdata, u8 *tdreport)
 {
@@ -130,6 +130,8 @@ int tdx_mcall_get_report0(u8 *reportdata, u8 *tdreport)
 	if (ret) {
 		if (TDCALL_RETURN_CODE(ret) == TDCALL_INVALID_OPERAND)
 			return -EINVAL;
+		else if (TDCALL_RETURN_CODE(ret) == TDCALL_OPERAND_BUSY)
+			return -EBUSY;
 		return -EIO;
 	}

---

## [6] Cedric Xing — 2025-04-07
*Subject: [PATCH v3 5/5] virt: tdx-guest: Expose TDX MRs as sysfs attributes*

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
Documentation/ABI/testing/sysfs-devices-virtual-misc-tdx_guest-mr for more
information.

Signed-off-by: Cedric Xing <cedric.xing@intel.com>
---
 .../sysfs-devices-virtual-misc-tdx_guest-mr        |  48 ++++++
 MAINTAINERS                                        |   1 +
 drivers/virt/coco/tdx-guest/Kconfig                |   1 +
 drivers/virt/coco/tdx-guest/tdx-guest.c            | 169 ++++++++++++++++++++-
 4 files changed, 217 insertions(+), 2 deletions(-)

diff --git a/Documentation/ABI/testing/sysfs-devices-virtual-misc-tdx_guest-mr b/Documentation/ABI/testing/sysfs-devices-virtual-misc-tdx_guest-mr
new file mode 100644
index 000000000000..682b2973737a
--- /dev/null
+++ b/Documentation/ABI/testing/sysfs-devices-virtual-misc-tdx_guest-mr
@@ -0,0 +1,48 @@
+What:		/sys/devices/virtual/misc/tdx_guest/mr/MRNAME[:HASH]
+Date:		April, 2025
+KernelVersion:	v6.16
+Contact:	linux-coco@lists.linux.dev
+Description:
+		Value of a TDX measurement register (MR). MRNAME and HASH above
+		are placeholders. The optional suffix :HASH is used for MRs
+		that have associated hash algorithms. See below for a complete
+		list of TDX MRs exposed via sysfs. Comprehensive information is
+		available at https://intel.com/tdx
+
+What:		/sys/devices/virtual/misc/tdx_guest/mr/mrconfigid
+Date:		April, 2025
+KernelVersion:	v6.16
+Contact:	cedric.xing@intel.com
+Description:
+		(RO) Value of MRCONFIGID - immutable storage for SW use.
+
+What:		/sys/devices/virtual/misc/tdx_guest/mr/mrowner
+Date:		April, 2025
+KernelVersion:	v6.16
+Contact:	cedric.xing@intel.com
+Description:
+		(RO) Value of MROWNER - immutable storage for SW use.
+
+What:		/sys/devices/virtual/misc/tdx_guest/mr/mrownerconfig
+Date:		April, 2025
+KernelVersion:	v6.16
+Contact:	cedric.xing@intel.com
+Description:
+		(RO) Value of MROWNERCONFIG - immutable storage for SW use.
+
+What:		/sys/devices/virtual/misc/tdx_guest/mr/mrtd:sha384
+Date:		April, 2025
+KernelVersion:	v6.16
+Contact:	cedric.xing@intel.com
+Description:
+		(RO) Value of MRTD - the measurement of the initial memory
+		image of the current TD.
+
+What:		/sys/devices/virtual/misc/tdx_guest/mr/rtmr[0123]:sha384
+Date:		April, 2025
+KernelVersion:	v6.16
+Contact:	cedric.xing@intel.com
+Description:
+		(RW) Read returns the current value of the RTMR. Write extends
+		the written buffer to the RTMR. All writes must start at offset
+		0 and be 48 bytes in size. Partial writes are not supported.
diff --git a/MAINTAINERS b/MAINTAINERS
index b210ac3389a7..c702f456643a 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -26226,6 +26226,7 @@ L:	x86@kernel.org
 L:	linux-coco@lists.linux.dev
 S:	Supported
 T:	git git://git.kernel.org/pub/scm/linux/kernel/git/tip/tip.git x86/tdx
+F:	Documentation/ABI/testing/sysfs-devices-virtual-misc-tdx_guest-mr
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
index 224e7dde9cde..1160f861c027 100644
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
@@ -16,7 +18,7 @@
 #include <linux/io.h>
 #include <linux/delay.h>
 #include <linux/tsm.h>
-#include <linux/sizes.h>
+#include <linux/tsm-mr.h>
 
 #include <uapi/linux/tdx-guest.h>
 
@@ -86,8 +88,14 @@ static long tdx_get_report0(struct tdx_report_req __user *req)
 		goto out;
 	}
 
+	if (mutex_lock_interruptible(&quote_lock)) {
+		ret = -EINTR;
+		goto out;
+	}
+
 	/* Generate TDREPORT0 using "TDG.MR.REPORT" TDCALL */
 	ret = tdx_mcall_get_report0(reportdata, tdreport);
+	mutex_unlock(&quote_lock);
 	if (ret)
 		goto out;
 
@@ -285,10 +293,16 @@ static const struct file_operations tdx_guest_fops = {
 	.unlocked_ioctl = tdx_guest_ioctl,
 };
 
+static const struct attribute_group *tdx_attr_groups[] = {
+	NULL,
+	NULL,
+};
+
 static struct miscdevice tdx_misc_dev = {
 	.name = KBUILD_MODNAME,
 	.minor = MISC_DYNAMIC_MINOR,
 	.fops = &tdx_guest_fops,
+	.groups = tdx_attr_groups,
 };
 
 static const struct x86_cpu_id tdx_guest_ids[] = {
@@ -304,6 +318,144 @@ static const struct tsm_ops tdx_tsm_ops = {
 	.report_bin_attr_visible = tdx_report_bin_attr_visible,
 };
 
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
+static u8 tdx_mr_report[TDX_REPORT_LEN] __aligned(TDX_REPORT_LEN);
+
+#define TDX_MR_(r) .mr_value = tdx_mr_report + TDREPORT_##r, TSM_MR_(r, SHA384)
+static const struct tsm_measurement_register tdx_mrs[] = {
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
+static int tdx_mr_try_refresh(void)
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
+	if (IS_BUILTIN(CONFIG_TDX_GUEST_DRIVER))
+		tdreport = tdx_mr_report;
+	else {
+		/* TDREPORT buffer must be naturally aligned */
+		tdreport = kmalloc(__alignof(tdx_mr_report), GFP_KERNEL);
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
+	if (!IS_BUILTIN(CONFIG_TDX_GUEST_DRIVER)) {
+		if (!ret)
+			memcpy(tdx_mr_report, tdreport, sizeof(tdx_mr_report));
+		kfree(tdreport);
+	}
+
+	return ret;
+}
+
+static int tdx_mr_refresh(const struct tsm_measurements *tm,
+			  const struct tsm_measurement_register *mr)
+{
+	int ret = -EINTR;
+
+	if (!mutex_lock_interruptible(&quote_lock)) {
+		ret = tdx_mr_try_refresh();
+		mutex_unlock(&quote_lock);
+
+		WARN_ON(ret);
+	}
+	return ret;
+}
+
+static int tdx_mr_try_extend(ptrdiff_t mr_ind, const u8 *data)
+{
+#if IS_BUILTIN(CONFIG_TDX_GUEST_DRIVER)
+	/*
+	 * TDG.MR.RTMR.EXTEND takes the GPA of a 64-byte aligned buffer on
+	 * input. virt_to_phys() works on static buffers only if the current
+	 * module is built-in.
+	 */
+	static u8 buf[SHA384_DIGEST_SIZE] __aligned(64);
+#else
+	/*
+	 * Otherwise, kmalloc() must be used to allocate the 64-byte aligned
+	 * input buffer.
+	 */
+	u8 *buf __free(kfree) = kmalloc(64, GFP_KERNEL);
+	if (!buf)
+		return -ENOMEM;
+#endif
+
+	int ret;
+
+	memcpy(buf, data, SHA384_DIGEST_SIZE);
+
+	ret = tdx_mcall_extend_rtmr((u8)mr_ind, buf);
+	if (ret)
+		pr_err("Extending RTMR%ld failed\n", mr_ind);
+
+	return ret;
+}
+
+static int tdx_mr_extend(const struct tsm_measurements *tm,
+			 const struct tsm_measurement_register *mr,
+			 const u8 *data)
+{
+	int ret = -EINTR;
+
+	if (!mutex_lock_interruptible(&quote_lock)) {
+		ret = tdx_mr_try_extend(mr - tm->mrs, data);
+		mutex_unlock(&quote_lock);
+
+		WARN_ON(ret);
+	}
+	return ret;
+}
+
+static struct tsm_measurements tdx_measurements = {
+	.name = "mr",
+	.mrs = tdx_mrs,
+	.nr_mrs = ARRAY_SIZE(tdx_mrs),
+	.refresh = tdx_mr_refresh,
+	.write = tdx_mr_extend,
+};
+
 static int __init tdx_guest_init(void)
 {
 	int ret;
@@ -311,9 +463,19 @@ static int __init tdx_guest_init(void)
 	if (!x86_match_cpu(tdx_guest_ids))
 		return -ENODEV;
 
+	ret = tdx_mr_try_refresh();
+	if (ret) {
+		pr_err("Failed to read MRs: %d\n", ret);
+		return ret;
+	}
+
+	tdx_attr_groups[0] = tsm_mr_create_attribute_group(&tdx_measurements);
+	if (IS_ERR(tdx_attr_groups[0]))
+		return PTR_ERR(tdx_attr_groups[0]);
+
 	ret = misc_register(&tdx_misc_dev);
 	if (ret)
-		return ret;
+		goto free_tsm_mr;
 
 	quote_data = alloc_quote_buf();
 	if (!quote_data) {
@@ -332,6 +494,8 @@ static int __init tdx_guest_init(void)
 	free_quote_buf(quote_data);
 free_misc:
 	misc_deregister(&tdx_misc_dev);
+free_tsm_mr:
+	tsm_mr_free_attribute_group(tdx_attr_groups[0]);
 
 	return ret;
 }
@@ -342,6 +506,7 @@ static void __exit tdx_guest_exit(void)
 	tsm_unregister(&tdx_tsm_ops);
 	free_quote_buf(quote_data);
 	misc_deregister(&tdx_misc_dev);
+	tsm_mr_free_attribute_group(tdx_attr_groups[0]);
 }
 module_exit(tdx_guest_exit);

---

## [7] Dan Williams — 2025-04-08
*Subject: Re: [PATCH v3 0/5] tsm-mr: Unified Measurement Register ABI for TVMs*

Cedric Xing wrote:
> NOTE: This patch series introduces the Measurement Register (MR) ABI, and
> is a continuation of the RFC series on the same topic [1].

s/drives/drivers like tdx-guest/

> CC (Confidential Compute) architecture-specific MRs (Measurement Registers)
> as sysfs attributes/files. Enable applications to read, write/extend MRs

What I do not see in this cover letter or patch1 is a brief summary of
the major assumptions contributing to the design for folks that have not
been closely following the threads. To me those are:

- Measurement registers are an architecture specific building block to
  enable attestation of system state. That can either be a vTPM
  application, or raw application direct use/extension of measurement
  values.

- By the nature of needing to expose architecture specific values the
  names and numbers of these measurements registers are not amenable to
  a shared transport mechanism like configs-tsm-reports, but the common
  operations are amenable to a shared library driven by a provided 'struct
  tsm_measurements' template.

> Patches included in this series:
> 

It helps to note who gave the feedback leading to changes. Besides the
small courtesy of credit it also helps to speed conflict resolution
(blame) when the parties are aware of each other. So for v4 please note
changes like this:

---
Changes in v3:
- tsm-mr: Separate measurement support (tsm-mr) from the original tsm
  source code. Modules depending on tsm-mr should `select TSM_MEASUREMENTS`
  in Kconfig. (Dan)
[..]
---

Lastly it helps to declare what you expect to happen with these patches.
At a minimum these need an x86 ack. For upstream merge these can either
go through the tip tree, or I can take them through devsec.git with
other "TSM" work. Absent someone hollering, devsec.git is my
expectation.

---

## [8] Dan Williams — 2025-04-08
*Subject: Re: [PATCH v3 1/5] tsm-mr: Add TVM Measurement Register support*

Cedric Xing wrote:
> Introduce new TSM Measurement helper library (tsm-mr) for TVM guest drivers
> to expose MRs (Measurement Registers) as sysfs attributes, with Crypto

Given that this defines a shared ABI scheme for "measurement registers"
lets add a Documentation/ entry for those shared mechanics that per-arch
implementations can reference from their Documentation/ABI/ entry.

"Documentation/driver-api/measurement-registers.rst" seems suitable, and
that can pull in the kernel-doc commentary from tsm-mr.[ch]. Here's a
template to get that started:

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

> ---
>  MAINTAINERS                |   4 +-

I note that the pending proposals for TEE I/O suggests splitting
drivers/virt/coco/ into drivers/virt/coco/{host,guest} [1] [2] [3].

[1]: http://lore.kernel.org/174107246021.1288555.7203769833791489618.stgit@dwillia2-xfh.jf.intel.com
[2]: http://lore.kernel.org/20250218111017.491719-8-aik@amd.com
[3]: http://lore.kernel.org/20250218111017.491719-17-aik@amd.com

So if I take this through devsec.git I will get that rename queued and
ask you to rebase on top of that.

>  5 files changed, 310 insertions(+), 2 deletions(-)
> 

Code comments should add to the understanding of the code, not simply
restate the code in prose. So I would replace this comment with some
non-obvious insight to aid future maintenance, something like:

/*
 * Note that the typical read path for MRs is via an attestation report,
 * this is why the ->write() path does not automatically ->refresh()
 * invalidated data for TSM_MR_LIVE registers. The use case for reading
 * back a individual hash-extending-write to an MR is for debug not
 * attestation. 
 */

...at least an explanation like that would have helped me understand the
locking and caching model of this implementation.


> +	mr = &ctx->tm->mrs[attr - ctx->mrs];
> +	if ((mr->mr_flags & TSM_MR_F_LIVE) && !ctx->in_sync) {

There needs to be explicit ABI and driver-api documentation here for what are the
allowed error codes that ->write() can return so as not to be confused
with EINVAL or EINTR arising from user error or interrupt.

> +
> +	/* reset @ctx->in_sync to refresh LIVE MRs on next read */

No need to mark this function as __must_check. That attribute is
typically reserved for core-apis.

> +tsm_mr_create_attribute_group(const struct tsm_measurements *tm)
> +{

If you're going to check for !tm->mrs, might as well also check for !tm.

> +
> +	/* aggregated length of all MR names */

Typically the only exceptions for not declaring variables at the top of
a function are for "for ()" loops and scope-based cleanup.

> +
> +	for (size_t i = 0; i < tm->nr_mrs; ++i) {

Why potentially crash the kernel here? EINVAL should be sufficient.

> +			return ERR_PTR(-EINVAL);
> +

I looked for a helper macro for a "buffer at the end of a structure",
but could not immediately find one. It feels like something Linux should
already have.

> +	end = name + nlen;
> +

Typical expectation for writable attributes is 0200.

> +			bas[i]->write_new = tm_digest_write;
> +		}

Related to the removal of __must_check add safety here for cases where
someone passes in an ERR_PTR():

	if (IS_ERR_OR_NULL(attr_grp)
		return;

This also makes the function amenable to scope-based cleanup.

> +	kfree(attr_grp->bin_attrs);
> +	kfree(container_of(attr_grp, struct tm_context, agrp));

Maybe use the word "extend" somewhere in this description for clarity.

> + * * %TSM_MR_F_RTMR - bitwise-OR of %TSM_MR_F_LIVE and %TSM_MR_F_WRITABLE.
> + * * %TSM_MR_F_NOHASH - this MR does NOT have an associated hash algorithm.

I had assumed that __counted_by() is only for inline flexible arrays,
not out-of-line dynamically allocated arrays. Are you sure this does
what you expect?

> +	size_t nr_mrs;
> +	int (*refresh)(const struct tsm_measurements *tm,

---

## [9] kernel test robot — 2025-04-09
*Subject: Re: [PATCH v3 2/5] tsm-mr: Add tsm-mr sample code*

Hi Cedric,

kernel test robot noticed the following build errors:

[auto build test ERROR on 0af2f6be1b4281385b618cb86ad946eded089ac8]

url:    https://github.com/intel-lab-lkp/linux/commits/Cedric-Xing/tsm-mr-Add-TVM-Measurement-Register-support/20250408-032813
base:   0af2f6be1b4281385b618cb86ad946eded089ac8
patch link:    https://lore.kernel.org/r/20250407-tdx-rtmr-v3-2-54f17bc65228%40intel.com
patch subject: [PATCH v3 2/5] tsm-mr: Add tsm-mr sample code
config: x86_64-allyesconfig (https://download.01.org/0day-ci/archive/20250409/202504090703.LtAt1UZI-lkp@intel.com/config)
compiler: clang version 20.1.2 (https://github.com/llvm/llvm-project 58df0ef89dd64126512e4ee27b4ac3fd8ddf6247)
reproduce (this is a W=1 build): (https://download.01.org/0day-ci/archive/20250409/202504090703.LtAt1UZI-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202504090703.LtAt1UZI-lkp@intel.com/

All errors (new ones prefixed by >>):

   In file included from samples/tsm-mr/tsm_mr_sample.c:8:
>> include/linux/tsm-mr.h:81:58: error: use of undeclared identifier 'nr_mrs'
      81 |         const struct tsm_measurement_register *mrs __counted_by(nr_mrs);
         |                                                                 ^
   1 error generated.


vim +/nr_mrs +81 include/linux/tsm-mr.h

b6f2f446f66ff9 Cedric Xing 2025-04-07  47  
b6f2f446f66ff9 Cedric Xing 2025-04-07  48  #define TSM_MR_(mr, hash)                              \
b6f2f446f66ff9 Cedric Xing 2025-04-07  49  	.mr_name = #mr, .mr_size = hash##_DIGEST_SIZE, \
b6f2f446f66ff9 Cedric Xing 2025-04-07  50  	.mr_hash = HASH_ALGO_##hash, .mr_flags = TSM_MR_F_READABLE
b6f2f446f66ff9 Cedric Xing 2025-04-07  51  
b6f2f446f66ff9 Cedric Xing 2025-04-07  52  /**
b6f2f446f66ff9 Cedric Xing 2025-04-07  53   * struct tsm_measurements - Defines the CC-specific measurement facility and
b6f2f446f66ff9 Cedric Xing 2025-04-07  54   * methods for updating measurement registers (MRs).
b6f2f446f66ff9 Cedric Xing 2025-04-07  55   * @name: Optional parent directory name.
b6f2f446f66ff9 Cedric Xing 2025-04-07  56   * @mrs: Array of MR definitions.
b6f2f446f66ff9 Cedric Xing 2025-04-07  57   * @nr_mrs: Number of elements in @mrs.
b6f2f446f66ff9 Cedric Xing 2025-04-07  58   * @refresh: Callback function to load/sync all MRs from TVM hardware/firmware
b6f2f446f66ff9 Cedric Xing 2025-04-07  59   *           into the kernel cache.
b6f2f446f66ff9 Cedric Xing 2025-04-07  60   * @write: Callback function to write to the MR specified by the parameter @mr.
b6f2f446f66ff9 Cedric Xing 2025-04-07  61   *
b6f2f446f66ff9 Cedric Xing 2025-04-07  62   * @refresh takes two parameters:
b6f2f446f66ff9 Cedric Xing 2025-04-07  63   *
b6f2f446f66ff9 Cedric Xing 2025-04-07  64   * * @tm - points back to this structure.
b6f2f446f66ff9 Cedric Xing 2025-04-07  65   * * @mr - points to the MR (an element of @mrs) being read (hence triggered
b6f2f446f66ff9 Cedric Xing 2025-04-07  66   *   this callback).
b6f2f446f66ff9 Cedric Xing 2025-04-07  67   *
b6f2f446f66ff9 Cedric Xing 2025-04-07  68   * Note that @refresh is invoked only when an MR with %TSM_MR_F_LIVE set is
b6f2f446f66ff9 Cedric Xing 2025-04-07  69   * being read and the cache is stale. However, @refresh must reload not only
b6f2f446f66ff9 Cedric Xing 2025-04-07  70   * the MR being read (@mr) but also all MRs with %TSM_MR_F_LIVE set.
b6f2f446f66ff9 Cedric Xing 2025-04-07  71   *
b6f2f446f66ff9 Cedric Xing 2025-04-07  72   * @write takes an additional parameter besides @tm and @mr:
b6f2f446f66ff9 Cedric Xing 2025-04-07  73   *
b6f2f446f66ff9 Cedric Xing 2025-04-07  74   * * @data - contains the bytes to write and whose size is @mr->mr_size.
b6f2f446f66ff9 Cedric Xing 2025-04-07  75   *
b6f2f446f66ff9 Cedric Xing 2025-04-07  76   * Both @refresh and @write should return 0 on success and an appropriate error
b6f2f446f66ff9 Cedric Xing 2025-04-07  77   * code on failure.
b6f2f446f66ff9 Cedric Xing 2025-04-07  78   */
b6f2f446f66ff9 Cedric Xing 2025-04-07  79  struct tsm_measurements {
b6f2f446f66ff9 Cedric Xing 2025-04-07  80  	const char *name;
b6f2f446f66ff9 Cedric Xing 2025-04-07 @81  	const struct tsm_measurement_register *mrs __counted_by(nr_mrs);
b6f2f446f66ff9 Cedric Xing 2025-04-07  82  	size_t nr_mrs;
b6f2f446f66ff9 Cedric Xing 2025-04-07  83  	int (*refresh)(const struct tsm_measurements *tm,
b6f2f446f66ff9 Cedric Xing 2025-04-07  84  		       const struct tsm_measurement_register *mr);
b6f2f446f66ff9 Cedric Xing 2025-04-07  85  	int (*write)(const struct tsm_measurements *tm,
b6f2f446f66ff9 Cedric Xing 2025-04-07  86  		     const struct tsm_measurement_register *mr, const u8 *data);
b6f2f446f66ff9 Cedric Xing 2025-04-07  87  };
b6f2f446f66ff9 Cedric Xing 2025-04-07  88

---

## [10] Dan Williams — 2025-04-08
*Subject: Re: [PATCH v3 2/5] tsm-mr: Add tsm-mr sample code*

Cedric Xing wrote:
> This sample kernel module demonstrates how to make MRs accessible to user
> mode through the tsm-mr library.
[..]
> +static struct tsm_measurements emulated_mr = {
> +	.name = "emulated_mr",

I think the convention should be that all consumers use a common name
for this common ABI, similar to a sysfs-class. So, I would say set the
name to "measurement_registers" inside tsm_mr_create_attribute_group(),
and make the "custom name" or "no-name" case an isolated corner case.

Other than that, thanks for taking the time to build this sample it
makes the reviewing the implementation easier and allows for some ABI
testing.

---

## [11] Dan Williams — 2025-04-08
*Subject: Re: [PATCH v3 3/5] x86/tdx: Add tdx_mcall_extend_rtmr() interface*

Cedric Xing wrote:
> The TDX guest exposes one MRTD (Build-time Measurement Register) and four
> RTMR (Run-time Measurement Register) registers to record the build and boot

Typically Signed-off-by without Co-developed-by means that the patch was
submitted upstream be Sathya, so did you also intend to add a
Co-developed-by or should this solo tag just be Reviewed-by?

> Signed-off-by: Cedric Xing <cedric.xing@intel.com>
> ---

Here is where the ABI documentation can help to make sure that userspace
can tell the difference between userspace bugs, kernel bugs, or TDX
internal errors. So perhaps translate this EINVAL to 
ENXIO in tsm-mr.c. Otherwise, this patch looks good to me:

Reviewed-by: Dan Williams <dan.j.williams@intel.com>

[..]

---

## [12] Dan Williams — 2025-04-08
*Subject: Re: [PATCH v3 4/5] x86/tdx: tdx_mcall_get_report0: Return -EBUSY on
 TDCALL_OPERAND_BUSY error*

Cedric Xing wrote:
> Return `-EBUSY` from tdx_mcall_get_report0() when `TDG.MR.REPORT` returns
> `TDCALL_OPERAND_BUSY`. This enables the caller to retry obtaining a

Can this not be prevented by proper locking? Otherwise this type of
collision sounds like a kernel bug, not something that should escape to
userspace.

I.e. userspace can not reasonably know when it is safe to retry, so take
locks to ensure forward progress.

---

## [13] Xing, Cedric — 2025-04-10
*Subject: Re: [PATCH v3 1/5] tsm-mr: Add TVM Measurement Register support*

On 4/8/2025 7:27 PM, Dan Williams wrote:
> Cedric Xing wrote:
[...]

>> ---
>>   MAINTAINERS                |   4 +-
No problem.

[...]

>> +	/*
>> +	 * @ctx->in_sync indicates if any MRs have been written since the last
The reasoning behind this involves not only ->refresh() and ->write() 
but also LIVE and ->in_sync. Generally, both ->refresh() and ->write() 
could be expensive so we are trying to do only the minimum. I'll add 
comments to the definition of this context structure.

[...]

>> +static ssize_t tm_digest_write(struct file *filp, struct kobject *kobj,
>> +			       const struct bin_attribute *attr, char *buffer,
I understand your point. But different CC archs may have arch specific 
reasons for failures. It'd be hard to whitelist all the allowed errors; 
while blacklisting EINVAL may make more sense, as users have no control 
over the input (hence cannot provide invalid input) to arch specific 
write/extend functions. I'll add to the description of ->write() in its 
kernel-doc comments.

[...]

>> +/**
>> + * tsm_mr_create_attribute_group() - creates an attribute group for measurement
Will remove.

>> +tsm_mr_create_attribute_group(const struct tsm_measurements *tm)
>> +{
Good catch! Will change.

>> +
>> +	/* aggregated length of all MR names */
Will move it to the top.

>> +
>> +	for (size_t i = 0; i < tm->nr_mrs; ++i) {
Agreed! Will change.

>> +			return ERR_PTR(-EINVAL);
>> +
Given a pointer some_struct_p, the end of it will be (some_struct_p + 1) 
or &some_struct_p[1]. It'd be more readable to be wrapped by a macro for 
sure.

>> +	end = name + nlen;
>> +
Will change.

[...]

>> +/**
>> + * tsm_mr_free_attribute_group() - frees the attribute group returned by
Will change.

[...]

>> +/**
>> + * struct tsm_measurement_register - describes an architectural measurement
Will clarify.

[...]

>> +struct tsm_measurements {
>> +	const char *name;
Thanks for pointing this out! I misunderstood __counted_by, and will 
remove it.

-Cedric

---

## [14] Xing, Cedric — 2025-04-11
*Subject: Re: [PATCH v3 4/5] x86/tdx: tdx_mcall_get_report0: Return -EBUSY on
 TDCALL_OPERAND_BUSY error*

On 4/9/2025 12:13 AM, Dan Williams wrote:
> Cedric Xing wrote:
>> Return `-EBUSY` from tdx_mcall_get_report0() when `TDG.MR.REPORT` returns
Yes, -EBUSY should never happen with proper locking, which however is 
implemented in the upper layer.

Similarly, -EINVAL will also indicate a kernel bug but is left for the 
upper layer to handle.

> I.e. userspace can not reasonably know when it is safe to retry, so take
> locks to ensure forward progress.
tdx-guest does WARN() on errors. There are no other users of this 
function currently. Returning an error, however, will allow different 
error handling in the future (e.g., retry instead of WARN on -EBUSY).

---

## [15] Xing, Cedric — 2025-04-11
*Subject: Re: [PATCH v3 3/5] x86/tdx: Add tdx_mcall_extend_rtmr() interface*

On 4/9/2025 12:10 AM, Dan Williams wrote:
> Cedric Xing wrote:
>> The TDX guest exposes one MRTD (Build-time Measurement Register) and four
I did modify slightly this commit from Sathya. I could be wrong but was 
told that "Signed-off-by:" was necessary to certify I had the authority 
to submit this patch. scripts/checkpatch.py complained about the 
co-existence of "Co-developed-by" and "Signed-off-by". So I had to keep 
the "Signed-off-by" tag only.

>> Signed-off-by: Cedric Xing <cedric.xing@intel.com>
>> ---
Agreed. I'll change -EINVAL to -ENXIO as this would be due to the 
inability to convert VA to GPA.

> [..]

---
