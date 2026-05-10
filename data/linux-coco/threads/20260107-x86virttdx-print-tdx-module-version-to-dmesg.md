---
title: 'x86/virt/tdx: Print TDX module version to dmesg'
date: 2026-01-07
last_reply: 2026-01-08
message_count: 12
participants: ['Vishal Verma', 'Kiryl Shutsemau', 'Edgecombe, Rick P', 'Dave Hansen']
---

## [1] Vishal Verma — 2026-01-07

=== Problem & Solution ===

Currently, there is neither an ABI, nor any other way to determine from
the host system, what version of the TDX module is running. A sysfs ABI
for this has been proposed in [1], but it may need additional discussion.

Many/most TDX developers already carry patches like this in their
development branches. It can be tricky to know which TDX module is
actually loaded on a system, and so this functionality has been needed
regularly for development and processing bug reports. Hence, it is
prudent to break out the patches to retrieve and print the TDX module
version, as those parts are very straightforward, and get some level of
debugability and traceability for TDX host systems.

=== Dependencies ===

None. This is based on v6.19-rc4, and applies cleanly to tip.git.

=== Patch details ===

Patch 1 is a prerequisite that adds the infrastructure to retrieve the
TDX module version from its global metadata. This was originally posted in [2].

Patch 2 is based on a patch from Kai Huang [3], and prints the version to
dmesg during init.

=== Testing ===

This has passed the usual suite of tests, including successful 0day
builds, KVM Unit tests, KVM selftests, a TD creation smoke test, and
selected KVM tests from the Avocado test suite.

[1]: https://lore.kernel.org/all/20260105074350.98564-1-chao.gao@intel.com/
[2]: https://lore.kernel.org/all/20260105074350.98564-2-chao.gao@intel.com/
[3]: https://lore.kernel.org/all/57eaa1b17429315f8b5207774307f3c1dd40cf37.1730118186.git.kai.huang@intel.com/

Signed-off-by: Vishal Verma <vishal.l.verma@intel.com>
---
Chao Gao (1):
      x86/virt/tdx: Retrieve TDX module version

Vishal Verma (1):
      x86/virt/tdx: Print TDX module version during init

 arch/x86/include/asm/tdx_global_metadata.h  |  7 +++++++
 arch/x86/virt/vmx/tdx/tdx.c                 |  5 +++++
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c | 16 ++++++++++++++++
 3 files changed, 28 insertions(+)
---
base-commit: 9ace4753a5202b02191d54e9fdf7f9e3d02b85eb
change-id: 20260107-tdx_print_module_version-e4ca7edc2022

Best regards,
--  
Vishal Verma <vishal.l.verma@intel.com>

---

## [2] Vishal Verma — 2026-01-07
*Subject: [PATCH 1/2] x86/virt/tdx: Retrieve TDX module version*

From: Chao Gao <chao.gao@intel.com>

Each TDX module has several bits of metadata about which specific TDX
module it is. The primary bit of info is the version, which has an x.y.z
format, where x represents the major version, y the minor version, and z
the update version. Knowing the running TDX Module version is valuable
for bug reporting and debugging. Note that the module does expose other
pieces of version-related metadata, such as build number and date. Those
aren't retrieved for now, that can be added if needed in the future.

Retrieve the TDX Module version using the existing metadata reading
interface. Later changes will expose this information. The metadata
reading interfaces have existed for quite some time, so this will work
with older versions of the TDX module as well - i.e. this isn't a new
interface.

As a side note, the global metadata reading code was originally set up
to be auto-generated from a JSON definition [1]. However, later [2] this
was found to be unsustainable, and the autogeneration approach was
dropped in favor of just manually adding fields as needed (e.g. as in
this patch).

Signed-off-by: Chao Gao <chao.gao@intel.com>
Signed-off-by: Vishal Verma <vishal.l.verma@intel.com>
Cc: Rick Edgecombe <rick.p.edgecombe@intel.com>
Cc: Kai Huang <kai.huang@intel.com>
Cc: Dave Hansen <dave.hansen@linux.intel.com>
Cc: Dan Williams <dan.j.williams@intel.com>
Link: https://lore.kernel.org/kvm/CABgObfYXUxqQV_FoxKjC8U3t5DnyM45nz5DpTxYZv2x_uFK_Kw@mail.gmail.com/ # [1]
Link: https://lore.kernel.org/all/1e7bcbad-eb26-44b7-97ca-88ab53467212@intel.com/ # [2]
---
 arch/x86/include/asm/tdx_global_metadata.h  |  7 +++++++
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c | 16 ++++++++++++++++
 2 files changed, 23 insertions(+)

diff --git a/arch/x86/include/asm/tdx_global_metadata.h b/arch/x86/include/asm/tdx_global_metadata.h
index 060a2ad744bff..40689c8dc67eb 100644
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
index 13ad2663488b1..0454124803f36 100644
--- a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
+++ b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
@@ -7,6 +7,21 @@
  * Include this file to other C file instead.
  */
 
+static int get_tdx_sys_info_version(struct tdx_sys_info_version *sysinfo_version)
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
 static int get_tdx_sys_info_features(struct tdx_sys_info_features *sysinfo_features)
 {
 	int ret = 0;
@@ -89,6 +104,7 @@ static int get_tdx_sys_info(struct tdx_sys_info *sysinfo)
 {
 	int ret = 0;
 
+	ret = ret ?: get_tdx_sys_info_version(&sysinfo->version);
 	ret = ret ?: get_tdx_sys_info_features(&sysinfo->features);
 	ret = ret ?: get_tdx_sys_info_tdmr(&sysinfo->tdmr);
 	ret = ret ?: get_tdx_sys_info_td_ctrl(&sysinfo->td_ctrl);

---

## [3] Vishal Verma — 2026-01-07
*Subject: [PATCH 2/2] x86/virt/tdx: Print TDX module version during init*

It is useful to print the TDX module version in dmesg logs. This allows
for a quick spot check for whether the correct/expected TDX module is
being loaded, and also creates a record for any future problems being
investigated. This was also requested in [1].

Include the version in the log messages during init, e.g.:

  virt/tdx: TDX module version: 1.5.24
  virt/tdx: 1034220 KB allocated for PAMT
  virt/tdx: module initialized

..followed by remaining TDX initialization messages (or errors).

Print the version early in init_tdx_module(), right after the global
metadata is read, which makes it available even if there are subsequent
initialization failures.

Based on a patch by Kai Huang <kai.huang@intel.com> [2]

Signed-off-by: Vishal Verma <vishal.l.verma@intel.com>
Reviewed-by: Chao Gao <chao.gao@intel.com>
Cc: Chao Gao <chao.gao@intel.com>
Cc: Rick Edgecombe <rick.p.edgecombe@intel.com>
Cc: Kai Huang <kai.huang@intel.com>
Cc: Dave Hansen <dave.hansen@linux.intel.com>
Cc: Dan Williams <dan.j.williams@intel.com>
Link: https://lore.kernel.org/all/CAGtprH8eXwi-TcH2+-Fo5YdbEwGmgLBh9ggcDvd6N=bsKEJ_WQ@mail.gmail.com/ # [1]
Link: https://lore.kernel.org/all/6b5553756f56a8e3222bfc36d0bdb3e5192137b7.1731318868.git.kai.huang@intel.com # [2]
---
 arch/x86/virt/vmx/tdx/tdx.c | 5 +++++
 1 file changed, 5 insertions(+)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 5ce4ebe99774..fba00ddc11f1 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1084,6 +1084,11 @@ static int init_tdx_module(void)
 	if (ret)
 		return ret;
 
+	pr_info("Module version: %u.%u.%02u\n",
+		tdx_sysinfo.version.major_version,
+		tdx_sysinfo.version.minor_version,
+		tdx_sysinfo.version.update_version);
+
 	/* Check whether the kernel can support this module */
 	ret = check_features(&tdx_sysinfo);
 	if (ret)

---

## [4] Kiryl Shutsemau — 2026-01-08
*Subject: Re: [PATCH 1/2] x86/virt/tdx: Retrieve TDX module version*

On Wed, Jan 07, 2026 at 05:31:28PM -0700, Vishal Verma wrote:
> From: Chao Gao <chao.gao@intel.com>
> 

Creates a 2 byte hole. Just enough to squeeze INTERNAL_VERSION there.
Just saying :P

But patch looks good to me:

Reviewed-by: Kiryl Shutsemau <kas@kernel.org>

---

## [5] Kiryl Shutsemau — 2026-01-08
*Subject: Re: [PATCH 2/2] x86/virt/tdx: Print TDX module version during init*

On Wed, Jan 07, 2026 at 05:31:29PM -0700, Vishal Verma wrote:
> It is useful to print the TDX module version in dmesg logs. This allows
> for a quick spot check for whether the correct/expected TDX module is

One thing to note that if metadata read fails, we will not get there.

The daisy chaining we use for metadata read makes it fragile. Some
metadata fields are version/feature dependant, like you can see in DPAMT
case.

It can be useful to dump version information, even if get_tdx_sys_info()
fails. Version info is likely to be valid on failure.

---

## [6] Verma, Vishal L — 2026-01-08
*Subject: Re: [PATCH 2/2] x86/virt/tdx: Print TDX module version during init*

On Thu, 2026-01-08 at 10:50 +0000, Kiryl Shutsemau wrote:
> On Wed, Jan 07, 2026 at 05:31:29PM -0700, Vishal Verma wrote:
> > It is useful to print the TDX module version in dmesg logs. This allows

Good point, maybe something like this to print it as soon as it is
retrieved?

---3<---

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index fba00ddc11f1..5ce4ebe99774 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1084,11 +1084,6 @@ static int init_tdx_module(void)
        if (ret)
                return ret;
 
-       pr_info("Module version: %u.%u.%02u\n",
-               tdx_sysinfo.version.major_version,
-               tdx_sysinfo.version.minor_version,
-               tdx_sysinfo.version.update_version);
-
        /* Check whether the kernel can support this module */
        ret = check_features(&tdx_sysinfo);
        if (ret)
diff --git a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
index 0454124803f3..4c9917a9c2c3 100644
--- a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
+++ b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
@@ -105,6 +105,12 @@ static int get_tdx_sys_info(struct tdx_sys_info *sysinfo)
        int ret = 0;
 
        ret = ret ?: get_tdx_sys_info_version(&sysinfo->version);
+
+       pr_info("Module version: %u.%u.%02u\n",
+               sysinfo->version.major_version,
+               sysinfo->version.minor_version,
+               sysinfo->version.update_version);
+
        ret = ret ?: get_tdx_sys_info_features(&sysinfo->features);
        ret = ret ?: get_tdx_sys_info_tdmr(&sysinfo->tdmr);
        ret = ret ?: get_tdx_sys_info_td_ctrl(&sysinfo->td_ctrl);

---

## [7] Edgecombe, Rick P — 2026-01-08
*Subject: Re: [PATCH 1/2] x86/virt/tdx: Retrieve TDX module version*

On Wed, 2026-01-07 at 17:31 -0700, Vishal Verma wrote:
> From: Chao Gao <chao.gao@intel.com>
> 


> The primary bit of info is the version, which has an x.y.z
> format, where x represents the major version, y the minor version, and z

A bit of a run-on sentence.

>  Knowing the running TDX Module version is valuable
> for bug reporting and debugging. Note that the module does expose other

Code looks good to me.

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>

---

## [8] Edgecombe, Rick P — 2026-01-08
*Subject: Re: [PATCH 2/2] x86/virt/tdx: Print TDX module version during init*

On Thu, 2026-01-08 at 18:39 +0000, Verma, Vishal L wrote:
> > It can be useful to dump version information, even if get_tdx_sys_info()
> > fails. Version info is likely to be valid on failure.

It's awkward because it doesn't check if get_tdx_sys_info_version() fails, even
the though the rest of the code handles this case. I'd just leave it. Let's keep
this as simple as possible, because anything here will be a huge upgrade.

---

## [9] Edgecombe, Rick P — 2026-01-08
*Subject: Re: [PATCH 2/2] x86/virt/tdx: Print TDX module version during init*

On Wed, 2026-01-07 at 17:31 -0700, Vishal Verma wrote:
> It is useful to print the TDX module version in dmesg logs. This allows
> for a quick spot check for whether the correct/expected TDX module is

It is more then a spot check, it's the only way to know which version is loaded.

>  This was also requested in [1].
> 

The TDX initialization errors would be before "module initialized", right?

> 
> Print the version early in init_tdx_module(), right after the global

---

## [10] Verma, Vishal L — 2026-01-08
*Subject: Re: [PATCH 2/2] x86/virt/tdx: Print TDX module version during init*

On Thu, 2026-01-08 at 20:20 +0000, Edgecombe, Rick P wrote:
> On Thu, 2026-01-08 at 18:39 +0000, Verma, Vishal L wrote:
> > > It can be useful to dump version information, even if get_tdx_sys_info()


I considered gating it on 'ret', but making it unconditional also
provides us an indirect hint as to which field failed to retrieve.

Do you mean leave it as in stick to printing only after
get_tdx_sys_info()?

---

## [11] Verma, Vishal L — 2026-01-08
*Subject: Re: [PATCH 2/2] x86/virt/tdx: Print TDX module version during init*

On Thu, 2026-01-08 at 20:24 +0000, Edgecombe, Rick P wrote:
> On Wed, 2026-01-07 at 17:31 -0700, Vishal Verma wrote:
> > It is useful to print the TDX module version in dmesg logs. This allows

I'll update to:

   It is useful to print the TDX module version in dmesg logs. This is
   currently the only way to determine the module version from the host. It
   also creates a record for...

> 
> >  This was also requested in [1].

Yep, I think this whole line can just be removed to avoid confusion.

---

## [12] Dave Hansen — 2026-01-08
*Subject: Re: [PATCH 2/2] x86/virt/tdx: Print TDX module version during init*

On 1/8/26 10:39, Verma, Vishal L wrote:
>         ret = ret ?: get_tdx_sys_info_version(&sysinfo->version);
> +

This is wonky, but it's also fine.

If we can't even get the module version, we have pretty big problems on
our hands Seeing "Module version: 0.0.00" is a nice indication. It'll
almost certainly be followed by a bunch of other nasty messages, so one
wonky message before them will be a drop in the bucket.

---
