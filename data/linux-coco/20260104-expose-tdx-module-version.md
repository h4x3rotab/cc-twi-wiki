---
title: 'Expose TDX Module version'
date: 2026-01-04
last_reply: 2026-01-07
message_count: 18
participants: ['Chao Gao', 'Kiryl Shutsemau', 'Dave Hansen', 'Nikolay Borisov', 'dan.j.williams@intel.com']
---

## [1] Chao Gao — 2026-01-04

Hi reviewers,

This series is quite straightforward and I believe it's well-polished.
Please consider providing your ack tags. However, since it depends on
two other series (listed below), please review those dependencies first if
you haven't already.

Changes in v2:
 - Print TDX Module version in demsg (Vishal)
 - Remove all descriptions about autogeneration (Rick)
 - Fix typos (Kai)
 - Stick with TDH.SYS.RD (Dave/Yilun)
 - Rebase onto Sean's VMXON v2 series

=== Problem & Solution === 

Currently, there is no user interface to get the TDX Module version.
However, in bug reporting or analysis scenarios, the first question
normally asked is which TDX Module version is on your system, to determine
if this is a known issue or a new regression.

To address this issue, this series exposes the TDX Module version as
sysfs attributes of the tdx_host device [*] and also prints it in dmesg
to keep a record.


=== Dependency ===

This series has two dependencies:

 1. Have TDX handle VMXON during bringup
    https://lore.kernel.org/kvm/20251206011054.494190-1-seanjc@google.com/#t
 2. TDX host virtual device (the first patch in the series below)
    https://lore.kernel.org/kvm/20251117022311.2443900-2-yilun.xu@linux.intel.com/

For your convenience, both dependencies and the series are also
available at

https://github.com/gaochaointel/linux-dev/tree/tdx-module-version-v2


Chao Gao (2):
  x86/virt/tdx: Retrieve TDX Module version
  coco/tdx-host: Expose TDX Module version

Vishal Verma (1):
  x86/virt/tdx: Print TDX Module version during init

 .../ABI/testing/sysfs-devices-faux-tdx-host   |  6 +++++
 arch/x86/include/asm/tdx_global_metadata.h    |  7 +++++
 arch/x86/virt/vmx/tdx/tdx.c                   |  9 +++++++
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c   | 16 ++++++++++++
 drivers/virt/coco/tdx-host/tdx-host.c         | 26 ++++++++++++++++++-
 5 files changed, 63 insertions(+), 1 deletion(-)
 create mode 100644 Documentation/ABI/testing/sysfs-devices-faux-tdx-host

---

## [2] Chao Gao — 2026-01-04
*Subject: [PATCH v2 1/3] x86/virt/tdx: Retrieve TDX Module version*

Each TDX Module is associated with a version in the x.y.z format, where x
represents the major version, y the minor version, and z the update
version. Knowing the running TDX Module version is valuable for bug
reporting and debugging.

Retrieve the TDX Module version using the existing metadata reading
interface, in preparation for exposing it to userspace via sysfs.

Signed-off-by: Chao Gao <chao.gao@intel.com>
---
v2:
 - Remove all descriptions about autogeneration (Rick)
 - TDH.SYS.RDALL isn't worth the code churn. So, stick with TDH.SYS.RD
 (Dave/Yilun)

 arch/x86/include/asm/tdx_global_metadata.h  |  7 +++++++
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c | 16 ++++++++++++++++
 2 files changed, 23 insertions(+)

diff --git a/arch/x86/include/asm/tdx_global_metadata.h b/arch/x86/include/asm/tdx_global_metadata.h
index 060a2ad744bf..40689c8dc67e 100644
--- a/arch/x86/include/asm/tdx_global_metadata.h
+++ b/arch/x86/include/asm/tdx_global_metadata.h
@@ -5,6 +5,12 @@
 
 #include <linux/types.h>
 
+struct tdx_sys_info_version {
+	u16 minor_version;
+	u16 major_version;
+	u16 update_version;
+};
+
 struct tdx_sys_info_features {
 	u64 tdx_features0;
 };
@@ -35,6 +41,7 @@ struct tdx_sys_info_td_conf {
 };
 
 struct tdx_sys_info {
+	struct tdx_sys_info_version version;
 	struct tdx_sys_info_features features;
 	struct tdx_sys_info_tdmr tdmr;
 	struct tdx_sys_info_td_ctrl td_ctrl;
diff --git a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
index 360963bc9328..85ab17b36c81 100644
--- a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
+++ b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
@@ -7,6 +7,21 @@
  * Include this file to other C file instead.
  */
 
+static __init int get_tdx_sys_info_version(struct tdx_sys_info_version *sysinfo_version)
+{
+	int ret = 0;
+	u64 val;
+
+	if (!ret && !(ret = read_sys_metadata_field(0x0800000100000003, &val)))
+		sysinfo_version->minor_version = val;
+	if (!ret && !(ret = read_sys_metadata_field(0x0800000100000004, &val)))
+		sysinfo_version->major_version = val;
+	if (!ret && !(ret = read_sys_metadata_field(0x0800000100000005, &val)))
+		sysinfo_version->update_version = val;
+
+	return ret;
+}
+
 static __init int get_tdx_sys_info_features(struct tdx_sys_info_features *sysinfo_features)
 {
 	int ret = 0;
@@ -89,6 +104,7 @@ static __init int get_tdx_sys_info(struct tdx_sys_info *sysinfo)
 {
 	int ret = 0;
 
+	ret = ret ?: get_tdx_sys_info_version(&sysinfo->version);
 	ret = ret ?: get_tdx_sys_info_features(&sysinfo->features);
 	ret = ret ?: get_tdx_sys_info_tdmr(&sysinfo->tdmr);
 	ret = ret ?: get_tdx_sys_info_td_ctrl(&sysinfo->td_ctrl);

---

## [3] Chao Gao — 2026-01-04
*Subject: [PATCH v2 2/3] coco/tdx-host: Expose TDX Module version*

Currently there is no way to know the TDX Module version from the
userspace. Such information is always helpful for bug reporting or
debugging.

With the tdx-host device in place, expose the TDX Module version as
a device attribute via sysfs.

Signed-off-by: Chao Gao <chao.gao@intel.com>
---
v2: 
 - No need to update MAINTAINERS to include sysfs-devices-faux-tdx-host
   explicitly (Kirill)

 .../ABI/testing/sysfs-devices-faux-tdx-host   |  6 +++++
 drivers/virt/coco/tdx-host/tdx-host.c         | 26 ++++++++++++++++++-
 2 files changed, 31 insertions(+), 1 deletion(-)
 create mode 100644 Documentation/ABI/testing/sysfs-devices-faux-tdx-host

diff --git a/Documentation/ABI/testing/sysfs-devices-faux-tdx-host b/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
new file mode 100644
index 000000000000..35ef21f53c2e
--- /dev/null
+++ b/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
@@ -0,0 +1,6 @@
+What:		/sys/devices/faux/tdx_host/version
+Contact:	linux-coco@lists.linux.dev
+Description:	(RO) Report the version of the loaded TDX Module. The TDX Module
+		version is formatted as x.y.z, where "x" is the major version,
+		"y" is the minor version and "z" is the update version. Versions
+		are used for bug reporting, TD-Preserving updates and etc.
diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
index ced1c980dc6f..2883c6638faf 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -9,6 +9,7 @@
 #include <linux/mod_devicetable.h>
 #include <linux/device/faux.h>
 #include <asm/cpu_device_id.h>
+#include <asm/tdx.h>
 
 static const struct x86_cpu_id tdx_host_ids[] = {
 	X86_MATCH_FEATURE(X86_FEATURE_TDX_HOST_PLATFORM, NULL),
@@ -18,12 +19,35 @@ MODULE_DEVICE_TABLE(x86cpu, tdx_host_ids);
 
 static struct faux_device *fdev;
 
+static ssize_t version_show(struct device *dev, struct device_attribute *attr,
+			    char *buf)
+{
+	const struct tdx_sys_info *tdx_sysinfo = tdx_get_sysinfo();
+	const struct tdx_sys_info_version *ver;
+
+	if (!tdx_sysinfo)
+		return -ENXIO;
+
+	ver = &tdx_sysinfo->version;
+
+	return sysfs_emit(buf, "%u.%u.%02u\n", ver->major_version,
+					       ver->minor_version,
+					       ver->update_version);
+}
+static DEVICE_ATTR_RO(version);
+
+static struct attribute *tdx_host_attrs[] = {
+	&dev_attr_version.attr,
+	NULL,
+};
+ATTRIBUTE_GROUPS(tdx_host);
+
 static int __init tdx_host_init(void)
 {
 	if (!x86_match_cpu(tdx_host_ids))
 		return -ENODEV;
 
-	fdev = faux_device_create(KBUILD_MODNAME, NULL, NULL);
+	fdev = faux_device_create_with_groups(KBUILD_MODNAME, NULL, NULL, tdx_host_groups);
 	if (!fdev)
 		return -ENODEV;

---

## [4] Chao Gao — 2026-01-04
*Subject: [PATCH v2 3/3] x86/virt/tdx: Print TDX Module version during init*

From: Vishal Verma <vishal.l.verma@intel.com>

Alongside exposing the TDX Module version via sysfs, it is useful to
have a record of it in dmesg logs. This allows for a quick spot check
for whether the correct/expected TDX module is being loaded, and also
creates a record for any future problems being investigated. This was
also requested in [1].

The log message will look like:

  virt/tdx: TDX-Module version: 1.5.24

Print this early in init_tdx_module(), right after the global metadata
is read, which makes it available even if there are subsequent
initialization failures.

Based on a patch by Kai Huang <kai.huang@intel.com> [2]

[ Chao: s/TDX module/TDX-Module in the log message
        tag print_module_version() as __init ]
Signed-off-by: Vishal Verma <vishal.l.verma@intel.com>
Signed-off-by: Chao Gao <chao.gao@intel.com>
Cc: Rick Edgecombe <rick.p.edgecombe@intel.com>
Cc: Kai Huang <kai.huang@intel.com>
Link: https://lore.kernel.org/all/CAGtprH8eXwi-TcH2+-Fo5YdbEwGmgLBh9ggcDvd6N=bsKEJ_WQ@mail.gmail.com/ # [1]
Link: https://lore.kernel.org/all/6b5553756f56a8e3222bfc36d0bdb3e5192137b7.1731318868.git.kai.huang@intel.com # [2]
---
v2
 - new

 arch/x86/virt/vmx/tdx/tdx.c | 9 +++++++++
 1 file changed, 9 insertions(+)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index ef77135ec373..3282dce5003b 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -352,6 +352,13 @@ static __init int read_sys_metadata_field(u64 field_id, u64 *data)
 
 #include "tdx_global_metadata.c"
 
+static __init void print_module_version(struct tdx_sys_info_version *version)
+{
+	pr_info("TDX-Module version: %u.%u.%02u\n",
+		version->major_version, version->minor_version,
+		version->update_version);
+}
+
 static __init int check_features(struct tdx_sys_info *sysinfo)
 {
 	u64 tdx_features0 = sysinfo->features.tdx_features0;
@@ -1158,6 +1165,8 @@ static __init int init_tdx_module(void)
 	if (ret)
 		return ret;
 
+	print_module_version(&tdx_sysinfo.version);
+
 	/* Check whether the kernel can support this module */
 	ret = check_features(&tdx_sysinfo);
 	if (ret)

---

## [5] Kiryl Shutsemau — 2026-01-05
*Subject: Re: [PATCH v2 0/3] Expose TDX Module version*

On Sun, Jan 04, 2026 at 11:43:43PM -0800, Chao Gao wrote:
> Hi reviewers,
> 

The version information is also useful for the guest. Maybe we should
provide consistent interface for both sides?

---

## [6] Dave Hansen — 2026-01-05
*Subject: Re: [PATCH v2 0/3] Expose TDX Module version*

On 1/5/26 02:38, Kiryl Shutsemau wrote:
>> To address this issue, this series exposes the TDX Module version as
>> sysfs attributes of the tdx_host device [*] and also prints it in dmesg

Could you elaborate a bit on what constitutes consistency here?

Do you mean simply ensuring that the TDX module version _is_ exposed on
both hosts and guests, like in:

	/sys/devices/faux/tdx_host/version

and (making this one up):

	/sys/devices/faux/tdx_guest/version

Note the "host" vs. "guest"   ^^^^^

Or, that the TDX module version be exposed in the *same* ABI in both
host and guest, like:

	/sys/devices/faux/tdx/version

Generally, I find myself really wanting to know how this fits into the
larger picture. Using this "faux" device really seems novel and
TDX-specific. Should it be?

What are other CPU vendors doing for this? SEV? CCA? S390? How are their
firmware versions exposed? What about other things in the Intel world
like CPU microcode or the billion other chunks of firmware? How about
hypervisors? Do they expose their versions to guests with an explicit
ABI? Are those exposed to userspace?

For instance, I hear a lot of talk about updating the TDX module. But is
this interface consistent with doing updates? Long term, I was hoping
that TDX firmware could get treated like any other blob of modern
firmware and have fwupd manage it, so I asked:

	https://chatgpt.com/share/695be06c-3d40-8012-97c9-2089fc33cbb3

My read on your approach here is that our new LLM overlords might
consider it the "last resort".

---

## [7] Kiryl Shutsemau — 2026-01-05
*Subject: Re: [PATCH v2 0/3] Expose TDX Module version*

On Mon, Jan 05, 2026 at 08:04:21AM -0800, Dave Hansen wrote:
> On 1/5/26 02:38, Kiryl Shutsemau wrote:
> >> To address this issue, this series exposes the TDX Module version as

I am not sure. It depends on what will be in these directories besides
the version. We might want to dump TDX features too, they are common for
host and guest. But there are going to be guest/td specific things (like
attributes or TD CTLS) and stuff that is only relevant for the host.

Maybe it is better to keep them separate, but with the common scheme. It
will keep door open for nested TDs (not partitioning) if they ever happen.
It might require two directories in the same environment.

I also wounder if it is possible to share code of this metadata retrieval
between guest and host. It should be doable.

> Generally, I find myself really wanting to know how this fits into the
> larger picture. Using this "faux" device really seems novel and

My first thought was that it should be under /sys/hypervisor/, no?

So far hypervisor_kobj only used by Xen and S390.

> For instance, I hear a lot of talk about updating the TDX module. But is
> this interface consistent with doing updates? Long term, I was hoping

---

## [8] Dave Hansen — 2026-01-05
*Subject: Re: [PATCH v2 0/3] Expose TDX Module version*

On 1/5/26 09:04, Kiryl Shutsemau wrote:
>> What are other CPU vendors doing for this? SEV? CCA? S390? How are their
>> firmware versions exposed? What about other things in the Intel world

As with everything else around TDX, it's not clear to me. The TDX module
is a new middle ground between the hypervisor and CPU. It's literally
there to arbitrate between the trusted CPU world and the untrusted
hypervisor world.

It's messy because there was (previously) no component there. It's new
space. We could (theoretically) a Linux guest running under Xen the
hypervisor using TDX. So we can't trivially just take over
/sys/hypervisor for TDX.

It's equally valid to sit here and claim that the TDX module is CPU
microcode. Sure, there's source code for it, but only Intel can bless
it, a version of it is loaded by the BIOS and can be updated by the OS.
It's not _super_ different conceptually than SGX XuCode.

The main thing that makes the TDX module _not_ CPU microcode is that
it's managed completely separately and there's almost no connection
between this:

	/sys/devices/system/cpu/cpu*/microcode/version

and the TDX module version.

Since there's a dearth of discussion of this topic in the changelog or
cover letter, my working assumption is that Chao did not consider any of
this before posting.

---

## [9] Kiryl Shutsemau — 2026-01-05
*Subject: Re: [PATCH v2 0/3] Expose TDX Module version*

On Mon, Jan 05, 2026 at 09:19:07AM -0800, Dave Hansen wrote:
> On 1/5/26 09:04, Kiryl Shutsemau wrote:
> >> What are other CPU vendors doing for this? SEV? CCA? S390? How are their

The TDX module has absorbed some functionality that was traditionally
provided by the hypervisor. Treating it as a hypervisor is a valid
option. But, yeah, I agree that it is not an exact match.

> It's messy because there was (previously) no component there. It's new
> space. We could (theoretically) a Linux guest running under Xen the

Note that Xen uses /sys/hypervisor/xen, so there's no conflict, we can
have both xen and tdx_whatever there.

---

## [10] Chao Gao — 2026-01-06
*Subject: Re: [PATCH v2 0/3] Expose TDX Module version*

On Mon, Jan 05, 2026 at 10:38:19AM +0000, Kiryl Shutsemau wrote:
>On Sun, Jan 04, 2026 at 11:43:43PM -0800, Chao Gao wrote:
>> Hi reviewers,

Note that only the Major and Minor versions (like 1.5 or 2.0) are available to
the guest; the TDX Module doesn't allow guests to read the update version.
Given this limitation, exposing version information to guests isn't
particularly useful.

And in my opinion, exposing version information to guests is also unnecessary
since the module version can already be read from the host with this series.
In debugging scenarios, I'm not sure why the TDX module would be so special
that guests should know its version but not other host information, such as
host kernel version, microcode version, etc. None of these are exposed to guest
kernel (not to mention guest userspace).

---

## [11] Nikolay Borisov — 2026-01-06
*Subject: Re: [PATCH v2 0/3] Expose TDX Module version*

On 6.01.26 г. 8:47 ч., Chao Gao wrote:
> On Mon, Jan 05, 2026 at 10:38:19AM +0000, Kiryl Shutsemau wrote:
>> On Sun, Jan 04, 2026 at 11:43:43PM -0800, Chao Gao wrote:

Just my 2 cents  on the topic:

One thing which comes to mind is that the information to be provided to 
the guest should ideally come from the hypervisor, for debugging 
purposes at least, i.e via some sort of hypercall. The security model of 
TDX is to ascertain information about the host via the attestation 
mechanism, no? So I'd argue that the version information provided to the 
guest is of no importance

---

## [12] Chao Gao — 2026-01-06
*Subject: Re: [PATCH v2 0/3] Expose TDX Module version*

>Generally, I find myself really wanting to know how this fits into the
>larger picture. Using this "faux" device really seems novel and

First I don't think we should expose TDX module version or hypervisor
version to guests. See my reply to Kirill.

Let me connect all the dots to explain why we use a "faux" device and expose
version information as device attributes.

Why add a device
================

SEV [1] employs a PCI device while CCA [2] adds a platform device. So, we add a
"virtual" device to represent TDX firmware. As illustrated in [3], the device
actually serves multiple purposes:

"""
Create a virtual device not only to align with other implementations but
also to make it easier to

 - expose metadata (e.g., TDX module version, seamldr version etc) to
   the userspace as device attributes

 - implement firmware uploader APIs which are tied to a device. This is
   needed to support TDX module runtime updates

 - enable TDX Connect which will share a common infrastructure with other
   platform implementations. In the TDX Connect context, every
   architecture has a TSM, represented by a PCIe or virtual device. The
   new "tdx_host" device will serve the TSM role.
"""

[1]: drivers/crypto/ccp/sev-dev.c
[2]: https://lore.kernel.org/all/20251208221319.1524888-5-vvidwans@nvidia.com/
[3]: https://lore.kernel.org/all/20251117022311.2443900-2-yilun.xu@linux.intel.com/

faux vs "virtual" device
========================

We previously implemented a virtual TDX device under /sys/devices/virtual/ but
it required creating a stub bus. As suggested by Dan, we switched to a faux
device to avoid this requirement.

The previous virtual device implementation was at:
https://lore.kernel.org/kvm/20250523095322.88774-5-chao.gao@intel.com/

As you can see from #LoC, the current tdx-host faux implementation is much
simpler:

before:

 arch/x86/virt/vmx/tdx/tdx.c | 75 +++++++++++++++++++++++++++++++++++++
 1 file changed, 75 insertions(+)

vs.

now: 

 drivers/virt/coco/Kconfig             |  2 ++
 drivers/virt/coco/tdx-host/Kconfig    | 10 +++++++
 drivers/virt/coco/Makefile            |  1 +
 drivers/virt/coco/tdx-host/Makefile   |  1 +
 drivers/virt/coco/tdx-host/tdx-host.c | 41 +++++++++++++++++++++++++++
 5 files changed, 55 insertions(+)


Why expose version to userspace
===============================

SEV doesn't expose its API version (which I assume is the counterpart of TDX
module version, since it doesn't have a firmware version concept) to userspace
but only prints it in dmesg.

TDX Module version is exposed to userspace because:

1. For debugging purposes, the version will be available to userspace even if
   dmesg logs are cleared. Like microcode version, it's printed in dmesg and
   also readable from CPU virtual device attributes.

2. A userspace tool needs to read the current module version to select
   compatible module versions for updates. This is a unique requirement of TDX.

Why expose version as device attribute
======================================

Once we have a virtual device to represent TDX firmware, using device
attributes is the natural choice. microcode version is exposed in a similar
way.

>
>For instance, I hear a lot of talk about updating the TDX module. But is

TDX module updates implement the firmware_upload API [*], just like NVMe firmware
updates and FPGA firmware updates. This results in them exposing similar uABIs
to userspace. If NVMe firmware or FPGA firmware can be supported by fwupd, it
shouldn't be difficult to have fwupd manage TDX modules as well.

[*]: https://docs.kernel.org/driver-api/firmware/fw_upload.html

>
>	https://chatgpt.com/share/695be06c-3d40-8012-97c9-2089fc33cbb3

The "last resort" in the above link refers to ACPI tables or WMI methods. But
IIUC, my approach here is the most common approach for non-UEFI firmware -
"sysfs devices", i.e.,

 : Kernel dev takeaway
 :  - Make it a proper kernel device
 :  - Expose a stable firmware version attribute
 :  - Expose a way to trigger update (even if it’s just “write blob, reboot”)

Is there anything I misunderstood?

---

## [13] Kiryl Shutsemau — 2026-01-06
*Subject: Re: [PATCH v2 0/3] Expose TDX Module version*

On Tue, Jan 06, 2026 at 02:47:57PM +0800, Chao Gao wrote:
> On Mon, Jan 05, 2026 at 10:38:19AM +0000, Kiryl Shutsemau wrote:
> >On Sun, Jan 04, 2026 at 11:43:43PM -0800, Chao Gao wrote:

Ughh. I didn't realize this info is not available to the guest. This is
unnecessary strict. Isn't it derivable from measurement report anyway?

> And in my opinion, exposing version information to guests is also unnecessary
> since the module version can already be read from the host with this series.

I already dump attributes and TD CTLS on guest boot, because it is
useful for debug. Version and features can also be useful for reports
from the field. Reported may not have access to hypervisor. Or it would
require additional round trip to get this info from reported.

---

## [14] Chao Gao — 2026-01-06
*Subject: Re: [PATCH v2 0/3] Expose TDX Module version*

On Tue, Jan 06, 2026 at 11:19:46AM +0000, Kiryl Shutsemau wrote:
>On Tue, Jan 06, 2026 at 02:47:57PM +0800, Chao Gao wrote:
>> On Mon, Jan 05, 2026 at 10:38:19AM +0000, Kiryl Shutsemau wrote:

Measurement report only has SVNs. it doesn't contain the TDX module version
directly AFAIK. But yes, I think the module version could be derived from the
TDX MODULE measurement (MRSEAM) of the TEE_TCB_INFO struct.

>
>> And in my opinion, exposing version information to guests is also unnecessary

I would say a bug report likely requires other host information - CPU model,
microcode version, and kernel version if the TDX module version is needed.
This means we'd need that "round trip" regardless, unless we provide all this
data directly to the guest.

I do think exposing features within the guest would help with debugging. But,
this raises implementation questions that need careful consideration - do we
just expose the raw feature bitmasks or create human-readable names for each
feature? And it looks like an ongoing discussion [*] may intersect with this
topic. So, I prefer to handle it in a separate series. 

*: https://lore.kernel.org/all/4c8524e5-b3e1-4113-a4e3-d3615465d9a8@intel.com/

---

## [15] Dave Hansen — 2026-01-06
*Subject: Re: [PATCH v2 0/3] Expose TDX Module version*

On 1/6/26 02:23, Chao Gao wrote:
> First I don't think we should expose TDX module version or hypervisor
> version to guests. See my reply to Kirill.

I just read it. It didn't provide any insight. For now, it's a plain old
NAK on the new ABI. The water is too muddied.

I'm still open to dumping something to dmesg though.

---

## [16] dan.j.williams@intel.com — 2026-01-06
*Subject: Re: [PATCH v2 0/3] Expose TDX Module version*

Chao Gao wrote:
[..]
> And in my opinion, exposing version information to guests is also unnecessary
> since the module version can already be read from the host with this series.

Agree, and note that the guest already has full launch attestation
details available via the common
Documentation/ABI/testing/configfs-tsm-report transport.

I assume the primary need for version information is debug, but if you
are debugging a guest problem might as well get the entire launch
attestation with the version of "all the things" included.

---

## [17] dan.j.williams@intel.com — 2026-01-07
*Subject: Re: [PATCH v2 0/3] Expose TDX Module version*

Dave Hansen wrote:
[..]
> Since there's a dearth of discussion of this topic in the changelog or
> cover letter, my working assumption is that Chao did not consider any of

Unfortunately that is incorrect, harsh, but somewhat forgivable because
features like TDX module update and the PCI device security stuff
stretch the boundaries of what tip.git historically needed to worry
about.

For example, the equivalent on the SNP side goes through
drivers/crypto/ccp/ which sometimes Boris takes changes through tip.git,
but many other commits, for features like "update device firmware" and
"PCI device security", go through crypto.git and now tsm.git. Case in
point, nobody in tip.git land had cause to even glance at commits like:

    2e424c33d8e7 crypto: ccp - Add support for displaying PSP firmware versions

I do not know where your specific objection lies so I am going to start
from the beginning summarizing all the discussions had around this to
date, some off list, some on list [1]. Chao has been involved in those
from the beginning and threw a fair share of consideration logs into the
fire.

The main problem for TDX with respect to the considered features of:

- sysfs to display some module metadata
- sysfs to mediate module update
- device + driver to coordinate PCI device security 

Is that TDX does not come with a device enumeration. It has no ACPI
description, it only has CPUID. Note, that at least puts TDX in a more
comfortable position than ARM which is also struggling with the "where
do we hang a useful device abstraction for this software pseudo
hypervisor thingy that controls confidential computing".

For sake of argument, I assume you have no fundamental objection to
module version information in sysfs in general? I.e. is the question
more on the where and how for TDX sysfs?

Note that back in March of last year there was this nak from me on the
proposal for something like a custom crafted /sys/hypervisor hierarchy
[2]. I still hold the same position today that all these archs are to
have widely different ways to enumerate their capabilities.  Anything
implementation specific should hang off an implementation specific
device. Everything else that is cross-arch should create a shared class
device. We now have that "shared class device" upstream via
tsm_register() [3].

For TDX the question is what is the best path to create a device
abstraction for a technology that does not come with a PCI device nor a
firmware enumerated platform device. The faux device infrastructure was
purpose built for cases like this. Now, faux device arrived in February
after I had sent out my original "tdx_subsys" proposal in January [1].
While I found the /sys/devices/faux path prefix somewhat unsavory
compared to /sys/devices/virtual, the implementation does exactly what
is needed and avoids the abuses of /sys/devices/platform that would
usually result from cases like this.

It turns out ARM is strongly recommended to go the faux device route as
well [4], so if you have other ideas here you have some work ahead to
undo some standing consensus.

As for which patch set should introduce this new device, I am in favor
of following Chao's lead here. Land the least controversial of all
possible TDX module metadata to publish in sysfs, a version string.
This simple infrastructure unblocks the path for the module update and
PCI device security features. Those add more attributes, a fw_upload
instance, and an idiomatic driver model for the tail of TDX features
that are more suitable for driver enabling than core-x86 enabling.

Yes, you were not directly copied on any of the references I have below,
yes you are free to have an opinion on proposals you are not copied.
However, going forward I would like to negotiate some working model
similar to the tip.git relationship to drivers/crypto/ccp/, and work on
how to avoid surprises like this in the future.

[1]: Earliest on list concept of needing device infrastructure for TDX
features: http://lore.kernel.org/170660662589.224441.11503798303914595072.stgit@dwillia2-xfh.jf.intel.com
[2]: http://lore.kernel.org/67d4bee77313a_12e31294c7@dwillia2-xfh.jf.intel.com.notmuch
[3]: http://lore.kernel.org/20251031212902.2256310-2-dan.j.williams@intel.com
[4]: http://lore.kernel.org/2025073035-bulginess-rematch-b92e@gregkh

---

## [18] Dave Hansen — 2026-01-07
*Subject: Re: [PATCH v2 0/3] Expose TDX Module version*

On 1/7/26 13:34, dan.j.williams@intel.com wrote:
> For sake of argument, I assume you have no fundamental objection to
> module version information in sysfs in general? I.e. is the question

For reference, and so the next poster can write an excellent and focused
changelog wherever this goes, the context I was yearning for in the
changelog was:

1. AMD has a PCI device for the PSP for SEV which provides an existing
   place to hang their equivalent metadata. TDX has no PCI device.
2. ARM CCA will likely have a faux device (although it isn't obvious if
   they have a need to export version information there)
3. The TDX faux device will drive TDX module updates. The version number
   is obviously deeply important to entities doing updates.

So, no, I don't have a fundamental objection to having TDX module
version information in sysfs. But, in the context of this series, I
don't see any incremental value for doing it in addition to dmesg _now_.
If the module updater userspace needs it, then I'd rather defer the
sysfs export (and faux device creation) until the time that there's an
actual concrete user.

---
