---
title: 'x86/virt/tdx: Print TDX module version to dmesg'
date: 2026-01-09
last_reply: 2026-02-09
message_count: 20
participants: ['Vishal Verma', 'Edgecombe, Rick P', 'Huang, Kai', 'Xiaoyao Li', 'Binbin Wu', 'Kiryl Shutsemau', 'Dave Hansen', 'Xu Yilun', 'Tony Lindgren']
---

## [1] Vishal Verma — 2026-01-09

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
Changes in v2:
- Collect review tags (Kiryl, Rick)
- Reword commit messages for clarity (Rick)
- Move the version print get_tdx_sys_info() (Kiryl, Dave)
- Link to v1: https://patch.msgid.link/20260107-tdx_print_module_version-v1-0-822baa56762d@intel.com

---
Chao Gao (1):
      x86/virt/tdx: Retrieve TDX module version

Vishal Verma (1):
      x86/virt/tdx: Print TDX module version during init

 arch/x86/include/asm/tdx_global_metadata.h  |  7 +++++++
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c | 22 ++++++++++++++++++++++
 2 files changed, 29 insertions(+)
---
base-commit: 9ace4753a5202b02191d54e9fdf7f9e3d02b85eb
change-id: 20260107-tdx_print_module_version-e4ca7edc2022

Best regards,
--  
Vishal Verma <vishal.l.verma@intel.com>

---

## [2] Vishal Verma — 2026-01-09
*Subject: [PATCH v2 1/2] x86/virt/tdx: Retrieve TDX module version*

From: Chao Gao <chao.gao@intel.com>

Each TDX module has several bits of metadata about which specific TDX
module it is. The primary bit of info is the version, which has an x.y.z
format. These represent the major version, minor version, and update
version respectively. Knowing the running TDX Module version is valuable
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
Link: https://lore.kernel.org/kvm/CABgObfYXUxqQV_FoxKjC8U3t5DnyM45nz5DpTxYZv2x_uFK_Kw@mail.gmail.com/ # [1]
Link: https://lore.kernel.org/all/1e7bcbad-eb26-44b7-97ca-88ab53467212@intel.com/ # [2]
Cc: Rick Edgecombe <rick.p.edgecombe@intel.com>
Cc: Kai Huang <kai.huang@intel.com>
Cc: Dave Hansen <dave.hansen@linux.intel.com>
Cc: Dan Williams <dan.j.williams@intel.com>
Reviewed-by: Kiryl Shutsemau <kas@kernel.org>
Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Signed-off-by: Vishal Verma <vishal.l.verma@intel.com>
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

## [3] Vishal Verma — 2026-01-09
*Subject: [PATCH v2 2/2] x86/virt/tdx: Print TDX module version during init*

It is useful to print the TDX module version in dmesg logs. This is
currently the only way to determine the module version from the host. It
also creates a record for any future problems being investigated. This
was also requested in [1].

Include the version in the log messages during init, e.g.:

  virt/tdx: TDX module version: 1.5.24
  virt/tdx: 1034220 KB allocated for PAMT
  virt/tdx: module initialized

Print the version in get_tdx_sys_info(), right after the version
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
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c | 6 ++++++
 1 file changed, 6 insertions(+)

diff --git a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
index 0454124803f3..4c9917a9c2c3 100644
--- a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
+++ b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
@@ -105,6 +105,12 @@ static int get_tdx_sys_info(struct tdx_sys_info *sysinfo)
 	int ret = 0;
 
 	ret = ret ?: get_tdx_sys_info_version(&sysinfo->version);
+
+	pr_info("Module version: %u.%u.%02u\n",
+		sysinfo->version.major_version,
+		sysinfo->version.minor_version,
+		sysinfo->version.update_version);
+
 	ret = ret ?: get_tdx_sys_info_features(&sysinfo->features);
 	ret = ret ?: get_tdx_sys_info_tdmr(&sysinfo->tdmr);
 	ret = ret ?: get_tdx_sys_info_td_ctrl(&sysinfo->td_ctrl);

---

## [4] Edgecombe, Rick P — 2026-01-09
*Subject: Re: [PATCH v2 2/2] x86/virt/tdx: Print TDX module version during init*

On Fri, 2026-01-09 at 12:14 -0700, Vishal Verma wrote:
> It is useful to print the TDX module version in dmesg logs. This is
> currently the only way to determine the module version from the host. It

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>

---

## [5] Huang, Kai — 2026-01-11
*Subject: Re: [PATCH v2 0/2] x86/virt/tdx: Print TDX module version to dmesg*

On Fri, 2026-01-09 at 12:14 -0700, Verma, Vishal L wrote:
> === Problem & Solution ===
> 

Big thanks for picking this up:

Reviewed-by: Kai Huang <kai.huang@intel.com>

---

## [6] Xiaoyao Li — 2026-01-12
*Subject: Re: [PATCH v2 1/2] x86/virt/tdx: Retrieve TDX module version*

On 1/10/2026 3:14 AM, Vishal Verma wrote:
> From: Chao Gao <chao.gao@intel.com>
> 

Though one nit below,

Reviewed-by: Xiaoyao Li <xiaoyao.li@intel.com>

> ---
>   arch/x86/include/asm/tdx_global_metadata.h  |  7 +++++++

Nit, not sure if better to move major_version before minor_version.

and ...

> +static int get_tdx_sys_info_version(struct tdx_sys_info_version *sysinfo_version)
> +{

... I know it's because minor_version has the least field ID among the 
three. But the order of the field IDs doesn't stand for the order of the 
reading. Reading the middle part y of x.y.z as first step looks a bit odd.

---

## [7] Xiaoyao Li — 2026-01-12
*Subject: Re: [PATCH v2 2/2] x86/virt/tdx: Print TDX module version during init*

On 1/10/2026 3:14 AM, Vishal Verma wrote:
> It is useful to print the TDX module version in dmesg logs. This is
> currently the only way to determine the module version from the host. It

Reviewed-by: Xiaoyao Li <xiaoyao.li@intel.com>

> Cc: Chao Gao <chao.gao@intel.com>
> Cc: Rick Edgecombe <rick.p.edgecombe@intel.com>

---

## [8] Binbin Wu — 2026-01-12
*Subject: Re: [PATCH v2 1/2] x86/virt/tdx: Retrieve TDX module version*

On 1/10/2026 3:14 AM, Vishal Verma wrote:
> From: Chao Gao <chao.gao@intel.com>
> 

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

> 
> Signed-off-by: Chao Gao <chao.gao@intel.com>

---

## [9] Binbin Wu — 2026-01-12
*Subject: Re: [PATCH v2 2/2] x86/virt/tdx: Print TDX module version during init*

On 1/10/2026 3:14 AM, Vishal Verma wrote:
> It is useful to print the TDX module version in dmesg logs. This is
> currently the only way to determine the module version from the host. It

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

One nit below.

> 
> Signed-off-by: Vishal Verma <vishal.l.verma@intel.com>

Nit:

There is a mismatch b/t the change log and the code.

The printed message will be 
    virt/tdx: Module version: x.x.xx
instead of the format in the change log
    virt/tdx: TDX module version: x.x.xx


>  	ret = ret ?: get_tdx_sys_info_features(&sysinfo->features);
>  	ret = ret ?: get_tdx_sys_info_tdmr(&sysinfo->tdmr);

---

## [10] Kiryl Shutsemau — 2026-01-12
*Subject: Re: [PATCH v2 2/2] x86/virt/tdx: Print TDX module version during init*

On Fri, Jan 09, 2026 at 12:14:31PM -0700, Vishal Verma wrote:
> It is useful to print the TDX module version in dmesg logs. This is
> currently the only way to determine the module version from the host. It

Reviewed-by: Kiryl Shutsemau <kas@kernel.org>

---

## [11] Dave Hansen — 2026-01-12
*Subject: Re: [PATCH v2 1/2] x86/virt/tdx: Retrieve TDX module version*

On 1/11/26 18:25, Xiaoyao Li wrote:
> ... I know it's because minor_version has the least field ID among the
> three. But the order of the field IDs doesn't stand for the order of the

I wouldn't sweat it either way. Reading 4, 3, 5 would also look odd. I'm
fine with it as-is in the patch.

---

## [12] Xu Yilun — 2026-01-13
*Subject: Re: [PATCH v2 1/2] x86/virt/tdx: Retrieve TDX module version*

On Mon, Jan 12, 2026 at 06:56:58AM -0800, Dave Hansen wrote:
> On 1/11/26 18:25, Xiaoyao Li wrote:
> > ... I know it's because minor_version has the least field ID among the

I prefer 3, 4, 5. The field IDs are not human readable hex magic so
should take extra care when copying from excel file to C file manually,
A different list order would make the code adding & reviewing even
harder.
>

---

## [13] Xiaoyao Li — 2026-01-13
*Subject: Re: [PATCH v2 1/2] x86/virt/tdx: Retrieve TDX module version*

On 1/13/2026 10:56 AM, Xu Yilun wrote:
> On Mon, Jan 12, 2026 at 06:56:58AM -0800, Dave Hansen wrote:
>> On 1/11/26 18:25, Xiaoyao Li wrote:

I guess eventually we will introduce MACROs for these magic numbers to 
make the code more readable given that the decision is no longer 
auto-generate the code by the script? Though I'm not sure when that will 
happen.

---

## [14] Tony Lindgren — 2026-01-19
*Subject: Re: [PATCH v2 1/2] x86/virt/tdx: Retrieve TDX module version*

On Fri, Jan 09, 2026 at 12:14:30PM -0700, Vishal Verma wrote:
> From: Chao Gao <chao.gao@intel.com>
> 

This is great to have for debugging, if not too late:

Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>

---

## [15] Tony Lindgren — 2026-01-19
*Subject: Re: [PATCH v2 2/2] x86/virt/tdx: Print TDX module version during init*

On Fri, Jan 09, 2026 at 12:14:31PM -0700, Vishal Verma wrote:
> It is useful to print the TDX module version in dmesg logs. This is
> currently the only way to determine the module version from the host. It

Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>

---

## [16] Verma, Vishal L — 2026-02-05
*Subject: Re: [PATCH v2 0/2] x86/virt/tdx: Print TDX module version to dmesg*

On Fri, 2026-01-09 at 12:14 -0700, Vishal Verma wrote:
> === Problem & Solution ===
> 

Hi Kiryl, just wanted to check on the plan for this, I didn't see it
merged in tip.git x86/tdx (or any other tip branch). Were you planning
to take it through x86/tdx? Can I help with anything to move it along?

Thank you,
Vishal

---

## [17] Kiryl Shutsemau — 2026-02-06
*Subject: Re: [PATCH v2 0/2] x86/virt/tdx: Print TDX module version to dmesg*

On Thu, Feb 05, 2026 at 07:05:39PM +0000, Verma, Vishal L wrote:
> On Fri, 2026-01-09 at 12:14 -0700, Vishal Verma wrote:
> > === Problem & Solution ===

I guess it has to wait after the merge window at this point.

Dave, could you queue this after -rc1 is tagged?

---

## [18] Dave Hansen — 2026-02-06
*Subject: Re: [PATCH v2 0/2] x86/virt/tdx: Print TDX module version to dmesg*

On 2/6/26 03:39, Kiryl Shutsemau wrote:
>> Hi Kiryl, just wanted to check on the plan for this, I didn't see it
>> merged in tip.git x86/tdx (or any other tip branch). Were you planning

Sure.

Is there any other TDX stuff that needs to get picked up at the same
time that's been languishing?

---

## [19] Edgecombe, Rick P — 2026-02-06
*Subject: Re: [PATCH v2 0/2] x86/virt/tdx: Print TDX module version to dmesg*

On Fri, 2026-02-06 at 07:10 -0800, Dave Hansen wrote:
> Is there any other TDX stuff that needs to get picked up at the same
> time that's been languishing?

Xiaoyao is going to send a rebase of this after RC1:
https://lore.kernel.org/kvm/20250715091312.563773-1-xiaoyao.li@intel.com/

It has pretty wide agreement, and ack's from the KVM side. Also, we have
internal branches that are carrying forms of it. So if we merge it now we can
have less dependencies later.

---

## [20] Kiryl Shutsemau — 2026-02-09
*Subject: Re: [PATCH v2 0/2] x86/virt/tdx: Print TDX module version to dmesg*

On Fri, Feb 06, 2026 at 07:10:58AM -0800, Dave Hansen wrote:
> On 2/6/26 03:39, Kiryl Shutsemau wrote:
> >> Hi Kiryl, just wanted to check on the plan for this, I didn't see it

Nothing on my side.

---
