---
title: '[RFC PATCH v1 0/3] Export TDX module information via SYSFS'
date: 2025-03-14
last_reply: 2025-03-19
message_count: 9
participants: ['Alexey Gladkov', 'Dan Williams', 'Kirill A . Shutemov']
---

## [1] Alexey Gladkov — 2025-03-14

From: "Alexey Gladkov (Intel)" <legion@kernel.org>

TD-Preserving updates depend on a userspace tool to select the appropriate
module to load. To facilitate this decision-making process, expose the
necessary information to userspace.

Also TDX module information (version, supported features, etc) is crucial for
bug reporting. For this purpose, it makes sense to have a consistent structure
for host and guest information in sysfs.

As already discussed [1] in the mailing list for tdx used the directory
/sys/hypervisor/tdx.

[1] https://lore.kernel.org/lkml/20250311110748.GCZ9AZhPYYAz-MXErv@fat_crate.local/


Alexey Gladkov (Intel) (3):
  x86/tdx: Make TDX metadata available via SYSFS
  x86/tdx: Make TDX metadata available on guest via SYSFS
  docs: ABI: testing: Add documentation about TDX

 .../ABI/testing/sysfs-hypervisor-tdx          | 50 ++++++++++
 arch/x86/Kconfig                              |  2 +
 arch/x86/coco/tdx/tdx.c                       | 92 +++++++++++++++++++
 arch/x86/include/asm/shared/tdx.h             |  2 +
 arch/x86/include/asm/tdx.h                    | 12 +++
 arch/x86/virt/vmx/tdx/tdx.c                   | 74 +++++++++++++++
 6 files changed, 232 insertions(+)
 create mode 100644 Documentation/ABI/testing/sysfs-hypervisor-tdx

---

## [2] Alexey Gladkov — 2025-03-14
*Subject: [RFC PATCH v1 1/3] x86/tdx: Make TDX metadata available via SYSFS*

From: "Alexey Gladkov (Intel)" <legion@kernel.org>

Expose the TDX module information to userspace. The version information
is valuable for debugging, as knowing the exact module version can help
reproduce TDX-related issues.

Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---
 arch/x86/Kconfig                  |  1 +
 arch/x86/include/asm/shared/tdx.h |  2 +
 arch/x86/include/asm/tdx.h        | 12 +++++
 arch/x86/virt/vmx/tdx/tdx.c       | 74 +++++++++++++++++++++++++++++++
 4 files changed, 89 insertions(+)

diff --git a/arch/x86/Kconfig b/arch/x86/Kconfig
index be2c311f5118..516f3539d0c7 100644
--- a/arch/x86/Kconfig
+++ b/arch/x86/Kconfig
@@ -1986,6 +1986,7 @@ config INTEL_TDX_HOST
 	depends on CONTIG_ALLOC
 	depends on !KEXEC_CORE
 	depends on X86_MCE
+	select SYS_HYPERVISOR
 	help
 	  Intel Trust Domain Extensions (TDX) protects guest VMs from malicious
 	  host and certain physical attacks.  This option enables necessary TDX
diff --git a/arch/x86/include/asm/shared/tdx.h b/arch/x86/include/asm/shared/tdx.h
index 606d93a1cbac..92ee9dfb21e7 100644
--- a/arch/x86/include/asm/shared/tdx.h
+++ b/arch/x86/include/asm/shared/tdx.h
@@ -18,6 +18,8 @@
 #define TDG_MEM_PAGE_ACCEPT		6
 #define TDG_VM_RD			7
 #define TDG_VM_WR			8
+/* TDG_SYS_RD is available since TDX module version 1.5 and later. */
+#define TDG_SYS_RD			11
 
 /* TDX attributes */
 #define TDX_ATTR_DEBUG_BIT		0
diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index e6b003fe7f5e..95d748bc8464 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -31,6 +31,18 @@
 #define TDX_SUCCESS		0ULL
 #define TDX_RND_NO_ENTROPY	0x8000020300000000ULL
 
+/*
+ * TDX metadata base field id, used by TDCALL TDG.SYS.RD
+ * See TDX ABI Spec Global Metadata Fields
+ */
+#define TDX_SYS_MINOR_FID		0x0800000100000003ULL
+#define TDX_SYS_MAJOR_FID		0x0800000100000004ULL
+#define TDX_SYS_UPDATE_FID		0x0800000100000005ULL
+#define TDX_SYS_INTERNAL_FID		0x0800000100000006ULL
+#define TDX_SYS_BUILD_DATE_FID		0x8800000200000001ULL
+#define TDX_SYS_BUILD_NUM_FID		0x8800000100000002ULL
+#define TDX_SYS_FEATURES0_FID		0x0A00000300000008ULL
+
 #ifndef __ASSEMBLY__
 
 #include <uapi/asm/mce.h>
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index f5e2a937c1e7..89378e2a1f66 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1869,3 +1869,77 @@ u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, struct page *page)
 	return seamcall(TDH_PHYMEM_PAGE_WBINVD, &args);
 }
 EXPORT_SYMBOL_GPL(tdh_phymem_page_wbinvd_hkid);
+
+#ifdef CONFIG_SYSFS
+#define TDX_SYSFS_ATTR(_field, _name, fmt)				\
+static ssize_t _name ## _show(						\
+	struct kobject *kobj, struct kobj_attribute *attr, char *buf)	\
+{									\
+	u64 value = 0;							\
+	read_sys_metadata_field(_field, &value);			\
+	return sprintf(buf, fmt, value);				\
+}									\
+static struct kobj_attribute _name ## _attr = __ATTR_RO(_name)
+
+TDX_SYSFS_ATTR(TDX_SYS_MINOR_FID, minor, "%lld\n");
+TDX_SYSFS_ATTR(TDX_SYS_MAJOR_FID, major, "%lld\n");
+TDX_SYSFS_ATTR(TDX_SYS_UPDATE_FID, update, "%lld\n");
+TDX_SYSFS_ATTR(TDX_SYS_BUILD_NUM_FID, build_num, "%lld\n");
+TDX_SYSFS_ATTR(TDX_SYS_BUILD_DATE_FID, build_date, "%lld\n");
+TDX_SYSFS_ATTR(TDX_SYS_FEATURES0_FID, features0, "%llx\n");
+
+static struct attribute *version_attrs[] = {
+	&minor_attr.attr,
+	&major_attr.attr,
+	&update_attr.attr,
+	NULL,
+};
+
+static const struct attribute_group version_attr_group = {
+	.name = "version",
+	.attrs = version_attrs,
+};
+
+static struct attribute *properties_attrs[] = {
+	&build_num_attr.attr,
+	&build_date_attr.attr,
+	&features0_attr.attr,
+	NULL,
+};
+
+static const struct attribute_group properties_attr_group = {
+	.name = "properties",
+	.attrs = properties_attrs,
+};
+
+__init static int tdh_sysfs_init(void)
+{
+	struct kobject *tdx_kobj;
+	int ret;
+
+	if (!hypervisor_kobj)
+		return -ENOMEM;
+
+	tdx_kobj = kobject_create_and_add("tdx", hypervisor_kobj);
+
+	if (!tdx_kobj)
+		return -ENOMEM;
+
+	ret = sysfs_create_group(tdx_kobj, &version_attr_group);
+	if (ret)
+		pr_err("sysfs exporting tdx module version failed %d\n", ret);
+
+	if (!ret) {
+		ret = sysfs_create_group(tdx_kobj, &properties_attr_group);
+		if (ret)
+			pr_err("sysfs exporting tdx module features failed %d\n", ret);
+	}
+
+	if (ret)
+		kobject_put(tdx_kobj);
+
+	return ret;
+}
+
+arch_initcall(tdh_sysfs_init);
+#endif // CONFIG_SYSFS

---

## [3] Alexey Gladkov — 2025-03-14
*Subject: [RFC PATCH v1 2/3] x86/tdx: Make TDX metadata available on guest via SYSFS*

From: "Alexey Gladkov (Intel)" <legion@kernel.org>

Expose information about the TDX module to guest-side. TDX module
information (version, supported features, etc) is crucial for bug
reporting.

Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---
 arch/x86/Kconfig        |  1 +
 arch/x86/coco/tdx/tdx.c | 92 +++++++++++++++++++++++++++++++++++++++++
 2 files changed, 93 insertions(+)

diff --git a/arch/x86/Kconfig b/arch/x86/Kconfig
index 516f3539d0c7..60f482edb1af 100644
--- a/arch/x86/Kconfig
+++ b/arch/x86/Kconfig
@@ -906,6 +906,7 @@ config INTEL_TDX_GUEST
 	select X86_MEM_ENCRYPT
 	select X86_MCE
 	select UNACCEPTED_MEMORY
+	select SYS_HYPERVISOR
 	help
 	  Support running as a guest under Intel TDX.  Without this support,
 	  the guest kernel can not boot or run under TDX.
diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 32809a06dab4..86108735aaf1 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -8,6 +8,7 @@
 #include <linux/export.h>
 #include <linux/io.h>
 #include <linux/kexec.h>
+#include <linux/kobject.h>
 #include <asm/coco.h>
 #include <asm/tdx.h>
 #include <asm/vmx.h>
@@ -1051,6 +1052,97 @@ static __init void tdx_announce(void)
 	tdx_dump_td_ctls(controls);
 }
 
+#ifdef CONFIG_SYSFS
+static u64 tdx_read_sys_metadata_field(u64 field_id, u64 *data)
+{
+	struct tdx_module_args args = {};
+	u64 ret;
+
+	/*
+	 * TDH.SYS.RD -- reads one global metadata field
+	 *  - RDX (in): the field to read
+	 *  - R8 (out): the field data
+	 */
+	args.rdx = field_id;
+	ret = __tdcall_ret(TDG_SYS_RD, &args);
+
+	if (ret) {
+		pr_err("failed reading TDX field %llx, return %llx\n", field_id, ret);
+		return ret;
+	}
+
+	*data = args.r8;
+
+	return 0;
+}
+
+#define TDX_SYSFS_ATTR(_field, _name, fmt)				\
+static ssize_t _name ## _show(						\
+	struct kobject *kobj, struct kobj_attribute *attr, char *buf)	\
+{									\
+	u64 value = 0;							\
+	tdx_read_sys_metadata_field(_field, &value);			\
+	return sprintf(buf, fmt, value);				\
+}									\
+static struct kobj_attribute _name ## _attr = __ATTR_RO(_name)
+
+TDX_SYSFS_ATTR(TDX_SYS_MINOR_FID, minor, "%lld\n");
+TDX_SYSFS_ATTR(TDX_SYS_MAJOR_FID, major, "%lld\n");
+TDX_SYSFS_ATTR(TDX_SYS_FEATURES0_FID, features0, "%llx\n");
+
+static struct attribute *version_attrs[] = {
+	&minor_attr.attr,
+	&major_attr.attr,
+	NULL,
+};
+
+static const struct attribute_group version_attr_group = {
+	.name = "version",
+	.attrs = version_attrs,
+};
+
+static struct attribute *properties_attrs[] = {
+	&features0_attr.attr,
+	NULL,
+};
+
+static const struct attribute_group properties_attr_group = {
+	.name = "properties",
+	.attrs = properties_attrs,
+};
+
+static int tdx_sysfs_init(void)
+{
+	struct kobject *tdx_kobj;
+	int ret;
+
+	if (!hypervisor_kobj)
+		return -ENOMEM;
+
+	tdx_kobj = kobject_create_and_add("tdx", hypervisor_kobj);
+
+	if (!tdx_kobj)
+		return -ENOMEM;
+
+	ret = sysfs_create_group(tdx_kobj, &version_attr_group);
+	if (ret)
+		pr_err("sysfs exporting tdx module version failed %d\n", ret);
+
+	if (!ret) {
+		ret = sysfs_create_group(tdx_kobj, &properties_attr_group);
+		if (ret)
+			pr_err("sysfs exporting tdx module properties failed %d\n", ret);
+	}
+
+	if (ret)
+		kobject_put(tdx_kobj);
+
+	return ret;
+}
+
+arch_initcall(tdx_sysfs_init);
+#endif // CONFIG_SYSFS
+
 void __init tdx_early_init(void)
 {
 	u64 cc_mask;

---

## [4] Alexey Gladkov — 2025-03-14
*Subject: [RFC PATCH v1 3/3] docs: ABI: testing: Add documentation about TDX*

From: "Alexey Gladkov (Intel)" <legion@kernel.org>

Document the new testing ABI of TDX module. Currently, there is no
reliable user interface within the guest as well as on the host system.

Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---
 .../ABI/testing/sysfs-hypervisor-tdx          | 50 +++++++++++++++++++
 1 file changed, 50 insertions(+)
 create mode 100644 Documentation/ABI/testing/sysfs-hypervisor-tdx

diff --git a/Documentation/ABI/testing/sysfs-hypervisor-tdx b/Documentation/ABI/testing/sysfs-hypervisor-tdx
new file mode 100644
index 000000000000..5ee33cdc59ef
--- /dev/null
+++ b/Documentation/ABI/testing/sysfs-hypervisor-tdx
@@ -0,0 +1,50 @@
+What:		/sys/hypervisor/tdx/version/major
+Date:		March 2025
+KernelVersion:	v6.15
+Contact:	linux-coco@lists.linux.dev
+Description:	(RO) Report the major version of the loaded TDX module.
+
+What:		/sys/hypervisor/tdx/version/minor
+Date:		March 2025
+KernelVersion:	v6.15
+Contact:	linux-coco@lists.linux.dev
+Description:	(RO) Report the major version of the loaded TDX module.
+
+What:		/sys/hypervisor/tdx/version/update
+Date:		March 2025
+KernelVersion:	v6.15
+Contact:	linux-coco@lists.linux.dev
+Description:	(RO) Report the update version of the loaded TDX module.
+		Not available on the guest side.
+
+What:		/sys/hypervisor/tdx/properties/build_num
+Date:		March 2025
+KernelVersion:	v6.15
+Contact:	linux-coco@lists.linux.dev
+Description:	(RO) Reports the build number of the loaded TDX module.
+		Not available on the guest side.
+
+What:		/sys/hypervisor/tdx/properties/build_date
+Date:		March 2025
+KernelVersion:	v6.15
+Contact:	linux-coco@lists.linux.dev
+Description:	(RO) Reports the build data of loaded TDX module in yyyymmdd
+		BCD format (each digit occupies 4 bits).
+		Not available on the guest side.
+
+What:		/sys/hypervisor/tdx/properties/features0
+Date:		March 2025
+KernelVersion:	v6.15
+Contact:	linux-coco@lists.linux.dev
+Description:	(RO) Reports the features supported by the loaded TDX module in
+		hex format. Enumerates TDX features:
+
+			=========   ===================================
+			Bit 0       TD Migration
+			Bit 1       TD Preserving
+			Bit 2       Service TD
+			Bit 3       TDG.VP.RD/WR
+			Bit 4       Relaxed mem management concurrency
+			Bits 63:5   Reserved, set to 0
+			=========   ===================================
+

---

## [5] Dan Williams — 2025-03-14
*Subject: Re: [RFC PATCH v1 1/3] x86/tdx: Make TDX metadata available via SYSFS*

Alexey Gladkov wrote:
> From: "Alexey Gladkov (Intel)" <legion@kernel.org>
> 

So this "/sys/hypervisor" proposal is clearly unaware of some other
discussions that have been happening around sysfs ABI for TEE Security
Managers like the PSP or TDX Module [1]. That PCI/TSM series discusses
the motivation for a bus/class + device model, not just raw hand-crafted
kobjects.

My other concern for hand-crafted kobjects is that it also destroys the
relationship with other existing objects. A /sys/hypervisor/$technology
is awkward when ABI like Documentation/ABI/testing/sysfs-driver-ccp
already exists.

So, no, I am not on board with this proposal. There are already patches
in flight to have TDX create a 'struct device' object that plays a
similar role as the PSP device object. For any potential common
attributes across vendors the proposal is that be handled via a typical
sysfs class device construction that links back to the $technology
device. That "tsm" class device is present in the PCI/TSM series [1].

[1]: http://lore.kernel.org/174107245357.1288555.10863541957822891561.stgit@dwillia2-xfh.jf.intel.com

---

## [6] Kirill A . Shutemov — 2025-03-17
*Subject: Re: [RFC PATCH v1 1/3] x86/tdx: Make TDX metadata available via SYSFS*

On Fri, Mar 14, 2025 at 04:42:31PM -0700, Dan Williams wrote:
> Alexey Gladkov wrote:
> > From: "Alexey Gladkov (Intel)" <legion@kernel.org>

Dan, could you elaborate on what is actual proposal? I am not sure I
understand what 'struct device' can have info on TDX module version be
attached to it.

---

## [7] Dan Williams — 2025-03-17
*Subject: Re: [RFC PATCH v1 1/3] x86/tdx: Make TDX metadata available via SYSFS*

Kirill A . Shutemov wrote:
> On Fri, Mar 14, 2025 at 04:42:31PM -0700, Dan Williams wrote:
> > Alexey Gladkov wrote:
[..]
> > > +__init static int tdh_sysfs_init(void)
> > > +{

Confused, you do not understand that devices can have sysfs attributes?

Documentation/ABI/testing/sysfs-driver-ccp describes a device object and
sysfs attributes for SEV-SNP firmware status.

For TDX, the proposal is to create virtual device to stand in for the
lack of a PCI device that fills the same role as AMD PSP.

With the expectation that all TSM technolgies (SEV-SNP, TDX, CCA, etc)
register a device, udev rules can trigger off a common class device
uevent. That proposal is detailed here [1]:

[1]: http://lore.kernel.org/174107247268.1288555.9365605713564715054.stgit@dwillia2-xfh.jf.intel.com

---

## [8] Kirill A . Shutemov — 2025-03-18
*Subject: Re: [RFC PATCH v1 1/3] x86/tdx: Make TDX metadata available via SYSFS*

On Mon, Mar 17, 2025 at 06:35:35PM -0700, Dan Williams wrote:
> Kirill A . Shutemov wrote:
> > On Fri, Mar 14, 2025 at 04:42:31PM -0700, Dan Williams wrote:

I didn't understand what device it would be in TDX case.

> Documentation/ABI/testing/sysfs-driver-ccp describes a device object and
> sysfs attributes for SEV-SNP firmware status.

Okay, I got it.

Do you see a problem having the same interface for both host and guest?
We obviously need indication what level we are running on.

> With the expectation that all TSM technolgies (SEV-SNP, TDX, CCA, etc)
> register a device, udev rules can trigger off a common class device

Joerg, what do you think? How does it fit your ideas for SEV-SNP?

---

## [9] Dan Williams — 2025-03-19
*Subject: Re: [RFC PATCH v1 1/3] x86/tdx: Make TDX metadata available via SYSFS*

Kirill A . Shutemov wrote:
[..]
> > > Dan, could you elaborate on what is actual proposal? I am not sure I
> > > understand what 'struct device' can have info on TDX module version be

Oh, *which* device, now I understand the disconnect.

> > Documentation/ABI/testing/sysfs-driver-ccp describes a device object and
> > sysfs attributes for SEV-SNP firmware status.

While I see no problem with /sys/devices/virtual/tdx appearing in both
host and guest, that needs to be reconciled with the fact that both
SEV-SNP and TDX created misc devices in the guest.

As for conveying level, the configs-tsm (soon to be renamed
configs-tsm-report) ABI already conveys the level for SEV-SNP if you are
talking about VMPL. 

> > With the expectation that all TSM technolgies (SEV-SNP, TDX, CCA, etc)
> > register a device, udev rules can trigger off a common class device

As I noted, both technologies currently register guest misc devices, so
natural place for some simple guest side vendor-specific sysfs
attributes would be via the @groups property of 'struct miscdevice'.
Otherwise, the proposal for cross-vendor TSM sysfs interface is via a
/sys/class/tsm device. For now I only have patches for the host side of
that for generically conveying which PCI devices are consuming link
encryption resources in the platform TSM.

---
