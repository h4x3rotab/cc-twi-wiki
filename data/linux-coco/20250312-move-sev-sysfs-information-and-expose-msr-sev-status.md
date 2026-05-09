---
title: 'Move SEV sysfs information and expose MSR_SEV_STATUS'
date: 2025-03-12
last_reply: 2025-03-12
message_count: 13
participants: ['Joerg Roedel', 'Tom Lendacky', 'Joerg Roedel', 'Dave Hansen', 'Liam Merwick']
---

## [1] Joerg Roedel — 2025-03-12

From: Joerg Roedel <jroedel@suse.de>

Hi,

these changes move the SEV sysfs directory to /sys/hypervisor/ as
discussed on the mailing-list[1] and add an attribute to expose the
raw value of the SEV_STATUS MSR.

For compatibility reasons a symlink is created at the old location of
the directory to link the new location.

Regards,

	Joerg

[1] https://lore.kernel.org/lkml/20250311110748.GCZ9AZhPYYAz-MXErv@fat_crate.local/

Joerg Roedel (2):
  x86/coco/sev: Move SEV SYSFS group to /sys/hypervisor/
  x86/sev: Make SEV_STATUS available via SYSFS

 .../ABI/testing/sysfs-devices-system-cpu      | 11 ++-----
 Documentation/ABI/testing/sysfs-hypervisor    | 15 ++++++++++
 arch/x86/Kconfig                              |  1 +
 arch/x86/coco/sev/core.c                      | 30 +++++++++++++++----
 4 files changed, 42 insertions(+), 15 deletions(-)
 create mode 100644 Documentation/ABI/testing/sysfs-hypervisor

---

## [2] Joerg Roedel — 2025-03-12
*Subject: [PATCH 1/2] x86/coco/sev: Move SEV SYSFS group to /sys/hypervisor/*

From: Joerg Roedel <jroedel@suse.de>

Move the SYSFS information about SEV to the /sys/hypervisor/ directory and link
to it from the old location. The /sys/hypervisor/ hierarchy makes more
sense for this information, as it is only relevant in a virtualized
environment and contains values influenced by the hypervisor.

Signed-off-by: Joerg Roedel <jroedel@suse.de>
---
 .../ABI/testing/sysfs-devices-system-cpu      | 11 ++--------
 Documentation/ABI/testing/sysfs-hypervisor    | 10 +++++++++
 arch/x86/Kconfig                              |  1 +
 arch/x86/coco/sev/core.c                      | 21 +++++++++++++------
 4 files changed, 28 insertions(+), 15 deletions(-)
 create mode 100644 Documentation/ABI/testing/sysfs-hypervisor

diff --git a/Documentation/ABI/testing/sysfs-devices-system-cpu b/Documentation/ABI/testing/sysfs-devices-system-cpu
index 206079d3bd5b..f056c401a550 100644
--- a/Documentation/ABI/testing/sysfs-devices-system-cpu
+++ b/Documentation/ABI/testing/sysfs-devices-system-cpu
@@ -607,16 +607,9 @@ Description:	Umwait control
 			  Low order two bits must be zero.
 
 What:		/sys/devices/system/cpu/sev
-		/sys/devices/system/cpu/sev/vmpl
 Date:		May 2024
-Contact:	Linux kernel mailing list <linux-kernel@vger.kernel.org>
-Description:	Secure Encrypted Virtualization (SEV) information
-
-		This directory is only present when running as an SEV-SNP guest.
-
-		vmpl: Reports the Virtual Machine Privilege Level (VMPL) at which
-		      the SEV-SNP guest is running.
-
+Description:	This symbolic link to /sys/hypervisor/sev/ is only present when
+		running as an SEV-SNP guest.
 
 What:		/sys/devices/system/cpu/svm
 Date:		August 2019
diff --git a/Documentation/ABI/testing/sysfs-hypervisor b/Documentation/ABI/testing/sysfs-hypervisor
new file mode 100644
index 000000000000..aca8b02c878c
--- /dev/null
+++ b/Documentation/ABI/testing/sysfs-hypervisor
@@ -0,0 +1,10 @@
+What:		/sys/devices/system/cpu/sev
+		/sys/devices/system/cpu/sev/vmpl
+Date:		May 2024
+Contact:	Linux kernel mailing list <linux-kernel@vger.kernel.org>
+Description:	Secure Encrypted Virtualization (SEV) information
+
+		This directory is only present when running as an SEV-SNP guest.
+
+		vmpl: Reports the Virtual Machine Privilege Level (VMPL) at which
+		      the SEV-SNP guest is running.
diff --git a/arch/x86/Kconfig b/arch/x86/Kconfig
index 1665ebaba251..5b717f6ccbbb 100644
--- a/arch/x86/Kconfig
+++ b/arch/x86/Kconfig
@@ -1497,6 +1497,7 @@ config AMD_MEM_ENCRYPT
 	select X86_MEM_ENCRYPT
 	select UNACCEPTED_MEMORY
 	select CRYPTO_LIB_AESGCM
+	select SYS_HYPERVISOR
 	help
 	  Say yes to enable support for the encryption of system memory.
 	  This requires an AMD processor that supports Secure Memory
diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index 96c7bc698e6b..51a04a19449b 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -2698,12 +2698,10 @@ static int __init sev_sysfs_init(void)
 	if (!cc_platform_has(CC_ATTR_GUEST_SEV_SNP))
 		return -ENODEV;
 
-	dev_root = bus_get_dev_root(&cpu_subsys);
-	if (!dev_root)
-		return -ENODEV;
-
-	sev_kobj = kobject_create_and_add("sev", &dev_root->kobj);
-	put_device(dev_root);
+	/*
+	 * Create /sys/hypervisor/sev/ with attributes
+	 */
+	sev_kobj = kobject_create_and_add("sev", hypervisor_kobj);
 
 	if (!sev_kobj)
 		return -ENOMEM;
@@ -2712,6 +2710,17 @@ static int __init sev_sysfs_init(void)
 	if (ret)
 		kobject_put(sev_kobj);
 
+	/*
+	 * Link from /sys/devices/system/cpu/sev to /sys/hypervisor/sev/ for
+	 * compatibility reasons.
+	 */
+	dev_root = bus_get_dev_root(&cpu_subsys);
+	if (!dev_root)
+		return -ENODEV;
+
+	ret = compat_only_sysfs_link_entry_to_kobj(&dev_root->kobj, hypervisor_kobj, "sev", NULL);
+	put_device(dev_root);
+
 	return ret;
 }
 arch_initcall(sev_sysfs_init);

---

## [3] Joerg Roedel — 2025-03-12
*Subject: [PATCH 2/2] x86/sev: Make SEV_STATUS available via SYSFS*

From: Joerg Roedel <jroedel@suse.de>

Current user-space tooling which needs access to the SEV_STATUS MSR is
using the MSR module. The use of this module poses a security risk in
any trusted execution environment and is generally discouraged.

Instead, provide an file in SYSFS in the /sys/hypervisor/sev/
directory to provide the value of the SEV_STATUS MSR to user-space.

Signed-off-by: Joerg Roedel <jroedel@suse.de>
---
 Documentation/ABI/testing/sysfs-hypervisor | 5 +++++
 arch/x86/coco/sev/core.c                   | 9 +++++++++
 2 files changed, 14 insertions(+)

diff --git a/Documentation/ABI/testing/sysfs-hypervisor b/Documentation/ABI/testing/sysfs-hypervisor
index aca8b02c878c..54c80899c19c 100644
--- a/Documentation/ABI/testing/sysfs-hypervisor
+++ b/Documentation/ABI/testing/sysfs-hypervisor
@@ -1,5 +1,6 @@
 What:		/sys/devices/system/cpu/sev
 		/sys/devices/system/cpu/sev/vmpl
+		/sys/devices/system/cpu/sev/sev_status
 Date:		May 2024
 Contact:	Linux kernel mailing list <linux-kernel@vger.kernel.org>
 Description:	Secure Encrypted Virtualization (SEV) information
@@ -8,3 +9,7 @@ Description:	Secure Encrypted Virtualization (SEV) information
 
 		vmpl: Reports the Virtual Machine Privilege Level (VMPL) at which
 		      the SEV-SNP guest is running.
+
+		sev_status: Reports the value of the SEV_STATUS MSR which
+		            enumerates the enabled features of an SEV-SNP
+			    environment.
diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index 51a04a19449b..3e834ce9badc 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -2678,10 +2678,19 @@ static ssize_t vmpl_show(struct kobject *kobj,
 	return sysfs_emit(buf, "%d\n", snp_vmpl);
 }
 
+static ssize_t sev_status_show(struct kobject *kobj,
+			       struct kobj_attribute *attr, char *buf)
+{
+	return sysfs_emit(buf, "%llx\n", sev_status);
+}
+
 static struct kobj_attribute vmpl_attr = __ATTR_RO(vmpl);
+static struct kobj_attribute sev_status_attr = __ATTR_RO(sev_status);
+
 
 static struct attribute *vmpl_attrs[] = {
 	&vmpl_attr.attr,
+	&sev_status_attr.attr,
 	NULL
 };

---

## [4] Tom Lendacky — 2025-03-12
*Subject: Re: [PATCH 2/2] x86/sev: Make SEV_STATUS available via SYSFS*

On 3/12/25 09:41, Joerg Roedel wrote:
> From: Joerg Roedel <jroedel@suse.de>
> 

Should it be prefixed with '0x'? That would make use of functions like
atoi() and strtol() easier.

Thanks,
Tom

> +}
> +

---

## [5] Joerg Roedel — 2025-03-12
*Subject: Re: [PATCH 2/2] x86/sev: Make SEV_STATUS available via SYSFS*

Hi Tom,

On Wed, Mar 12, 2025 at 09:46:45AM -0500, Tom Lendacky wrote:
> On 3/12/25 09:41, Joerg Roedel wrote:
> > +static ssize_t sev_status_show(struct kobject *kobj,

Yes, it probably should. Currently I see just a '7' in the file, which
gives no clue about the used base. I will change that in the next
version.

Regards,

---

## [6] Dave Hansen — 2025-03-12
*Subject: Re: [PATCH 2/2] x86/sev: Make SEV_STATUS available via SYSFS*

On 3/12/25 07:41, Joerg Roedel wrote:
> +static ssize_t sev_status_show(struct kobject *kobj,
> +			       struct kobj_attribute *attr, char *buf)

Do we really want to just plumb the raw MSR out to userspace? Users
would still need to parse the thing, so it's not _really_ human readable.

---

## [7] Joerg Roedel — 2025-03-12
*Subject: Re: [PATCH 2/2] x86/sev: Make SEV_STATUS available via SYSFS*

Hi Dave,

On Wed, Mar 12, 2025 at 07:57:31AM -0700, Dave Hansen wrote:
> Do we really want to just plumb the raw MSR out to userspace? Users
> would still need to parse the thing, so it's not _really_ human readable.

I agree that this is not really human readable. On the other side SYSFS
is more an interface targeted for tools than optimized for human
readability (see the one-datum-per-file rule).

The actual use-case (and the reason for these patches) of the sev_status
file is to provide a better and more secure interface than /dev/msr to a
tool named snpguest.

A human readable form of this can be added as well, if needed. There is
already a line in dmesg with the decoded features.

Regards,

---

## [8] Tom Lendacky — 2025-03-12
*Subject: Re: [PATCH 1/2] x86/coco/sev: Move SEV SYSFS group to
 /sys/hypervisor/*

On 3/12/25 09:41, Joerg Roedel wrote:
> From: Joerg Roedel <jroedel@suse.de>
> 

One minor nit below, otherwise:

Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>

> ---
>  .../ABI/testing/sysfs-devices-system-cpu      | 11 ++--------

Shouldn't these be /sys/hypervisor/sev ?

Thanks,
Tom

> +Date:		May 2024
> +Contact:	Linux kernel mailing list <linux-kernel@vger.kernel.org>

---

## [9] Joerg Roedel — 2025-03-12
*Subject: Re: [PATCH 1/2] x86/coco/sev: Move SEV SYSFS group to
 /sys/hypervisor/*

On Wed, Mar 12, 2025 at 10:11:55AM -0500, Tom Lendacky wrote:
> On 3/12/25 09:41, Joerg Roedel wrote:
> > @@ -0,0 +1,10 @@

Yes, copy&paste error on my side, thanks for point that out.

Regards,

	Joerg

---

## [10] Liam Merwick — 2025-03-12
*Subject: Re: [PATCH 1/2] x86/coco/sev: Move SEV SYSFS group to
 /sys/hypervisor/*

On 12/03/2025 14:41, Joerg Roedel wrote:
> From: Joerg Roedel <jroedel@suse.de>
> 

one suggestion below but either way,

Reviewed-by: Liam Merwick <liam.merwick@oracle.com>

> ---
>   .../ABI/testing/sysfs-devices-system-cpu      | 11 ++--------

Given hypervisor_kobj is created elsewhere, and the caller of 
hypervisor_init() doesn't check for ENOMEM, would it be worth
adding a check here that it exists before using it?

>   
>   	if (!sev_kobj)

---

## [11] Joerg Roedel — 2025-03-12
*Subject: Re: [PATCH 1/2] x86/coco/sev: Move SEV SYSFS group to
 /sys/hypervisor/*

On Wed, Mar 12, 2025 at 03:32:04PM +0000, Liam Merwick wrote:
> one suggestion below but either way,
> 

Thanks!

> > +	sev_kobj = kobject_create_and_add("sev", hypervisor_kobj);
> 

Hmm, dunno, I guess it would make things slightly more robust. On the
other side all existing users of this object already assume a successful
initialization.

Regards,

	Joerg

---

## [12] Dave Hansen — 2025-03-12
*Subject: Re: [PATCH 2/2] x86/sev: Make SEV_STATUS available via SYSFS*

On 3/12/25 08:07, Joerg Roedel wrote:
> Hi Dave,
> 

Right, but I think it's also intended to be independent and not
*require* tools to make sense of the output. A raw MSR requires tooling
or someone sitting there with the hardware docs to make sense of it.

That's why we have things like:

	/sys/kernel/mm/transparent_hugepage/enabled

that tell you:

	[always] madvise never

as opposed to the old style in:

	/proc/sys/vm/zone_reclaim_mode

which require you to go read the docs and figure out what 0/1/2 mean.

> The actual use-case (and the reason for these patches) of the sev_status
> file is to provide a better and more secure interface than /dev/msr to a

Let's draw this out to its natural conclusion. There are also a bunch of
TDX attributes that tell you about the capabilities of the VM and the
TDX module.

Should we have:

	/sys/devices/system/cpu/tdx/tdx_attributes

which just dumps out the raw register values that come back from the
TDCALL? Then we'll go write a tdxguest tool to parse those values.

---

## [13] Joerg Roedel — 2025-03-12
*Subject: Re: [PATCH 2/2] x86/sev: Make SEV_STATUS available via SYSFS*

On Wed, Mar 12, 2025 at 09:04:14AM -0700, Dave Hansen wrote:
> Let's draw this out to its natural conclusion. There are also a bunch of
> TDX attributes that tell you about the capabilities of the VM and the

If I remember correctly the goal of the VirTEE project (where the
snpguest tool lives) is to come up with a combined teeguest tool. This
will serve as a vendor- and architecture-independent frontend for the
various kernel interfaces for confidential computing (configfs-tsm,
sysfs-attributes, ...).

So yes, my expectation is that this tool will understand the raw values
returned from the TDCALL, as long as they are architectural.

But let me think a bit more about a solution that takes care of the
tooling and the human requirements.

Regards,

	Joerg

---
