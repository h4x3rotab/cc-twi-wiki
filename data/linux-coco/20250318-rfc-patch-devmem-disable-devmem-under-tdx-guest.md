---
title: '[RFC PATCH] /dev/mem: Disable /dev/mem under TDX guest'
date: 2025-03-18
last_reply: 2025-03-28
message_count: 14
participants: ['Nikolay Borisov', 'Juergen Gross', 'Kirill A. Shutemov', 'Dave Hansen', 'Dan Williams']
---

## [1] Nikolay Borisov — 2025-03-18

If a piece of memory is read from /dev/mem that falls outside of the
System Ram region i.e bios data region the kernel creates a shared
mapping via xlate_dev_mem_ptr() (this behavior was introduced by
9aa6ea69852c ("x86/tdx: Make pages shared in ioremap()"). This results
in a region having both a shared and a private mapping.

Subsequent accesses to this region via the private mapping induce a
SEPT violation and a crash of the VMM. In this particular case the
scenario was a userspace process reading something from the bios data
area at address 0x497 which creates a shared mapping, and a followup
reboot accessing __va(0x472) which access pfn 0 via the private mapping
causing mayhem.

Fix this by simply forbidding access to /dev/mem when running as an TDX
guest.

Signed-off-by: Nikolay Borisov <nik.borisov@suse.com>
---

Sending this now to hopefully spur up discussion as to how to handle the described
scenario. This was hit on the GCP cloud and was causing their hypervisor to crash.

I guess the most pressing question is what will be the most sensible approach to
eliminate such situations happening in the future:

1. Should we forbid getting a descriptor to /dev/mem (this patch)
2. Skip creating /dev/mem altogether3
3. Possibly tinker with internals of ioremap to ensure that no memory which is
backed by kvm memslots is remapped as shared.
4. Eliminate the access to 0x472 from the x86 reboot path, after all we don't
really have a proper bios at that address.
5. Something else ?

 arch/x86/coco/tdx/tdx.c  | 4 ++++
 drivers/char/mem.c       | 3 +++
 include/linux/security.h | 6 ++++++
 3 files changed, 13 insertions(+)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 32809a06dab4..615e8a300fc7 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -40,6 +40,8 @@

 static atomic_long_t nr_shared;

+bool devmem_disabled = false;
+
 /* Called from __tdx_hypercall() for unrecoverable failure */
 noinstr void __noreturn __tdx_hypercall_failed(void)
 {
@@ -1063,6 +1065,8 @@ void __init tdx_early_init(void)

 	setup_force_cpu_cap(X86_FEATURE_TDX_GUEST);

+	devmem_disabled = true;
+
 	/* TSC is the only reliable clock in TDX guest */
 	setup_force_cpu_cap(X86_FEATURE_TSC_RELIABLE);

diff --git a/drivers/char/mem.c b/drivers/char/mem.c
index 169eed162a7f..8778d46216f2 100644
--- a/drivers/char/mem.c
+++ b/drivers/char/mem.c
@@ -616,6 +616,9 @@ static int open_port(struct inode *inode, struct file *filp)
 	if (iminor(inode) != DEVMEM_MINOR)
 		return 0;

+	if (devmem_disabled)
+		return -EINVAL;
+
 	/*
 	 * Use a unified address space to have a single point to manage
 	 * revocations when drivers want to take over a /dev/mem mapped
diff --git a/include/linux/security.h b/include/linux/security.h
index 980b6c207cad..1757f683a09d 100644
--- a/include/linux/security.h
+++ b/include/linux/security.h
@@ -265,6 +265,12 @@ struct request_sock;
 #define LSM_UNSAFE_PTRACE	2
 #define LSM_UNSAFE_NO_NEW_PRIVS	4

+#ifdef CONFIG_INTEL_TDX_GUEST
+extern bool devmem_disabled;
+#else
+#define devmem_disabled 0
+#endif
+
 #ifdef CONFIG_MMU
 extern int mmap_min_addr_handler(const struct ctl_table *table, int write,
 				 void *buffer, size_t *lenp, loff_t *ppos);
--
2.43.0

---

## [2] Juergen Gross — 2025-03-18
*Subject: Re: [RFC PATCH] /dev/mem: Disable /dev/mem under TDX guest*

On 18.03.25 12:36, Nikolay Borisov wrote:
> If a piece of memory is read from /dev/mem that falls outside of the
> System Ram region i.e bios data region the kernel creates a shared

I think a crash of the VMM must be avoided, otherwise we have a security
issue due to one TDX guest being able to DoS the complete host.

I'd rather crash the guest for which the SEPT violation was detected (is
this possible? If not, don't allow it to run any longer maybe?)


Juergen

---

## [3] Nikolay Borisov — 2025-03-18
*Subject: Re: [RFC PATCH] /dev/mem: Disable /dev/mem under TDX guest*

On 18.03.25 г. 13:53 ч., Juergen Gross wrote:
> On 18.03.25 12:36, Nikolay Borisov wrote:
>> If a piece of memory is read from /dev/mem that falls outside of the

I agree with this, however this particular crash I haven't been able to 
reproduce locally but was something that came up in the GCP environment. 
So I'd like for someone from google to chime in.

> 
> I'd rather crash the guest for which the SEPT violation was detected (is
 > >
> Juergen

---

## [4] Kirill A. Shutemov — 2025-03-18
*Subject: Re: [RFC PATCH] /dev/mem: Disable /dev/mem under TDX guest*

On Tue, Mar 18, 2025 at 01:36:04PM +0200, Nikolay Borisov wrote:
> If a piece of memory is read from /dev/mem that falls outside of the
> System Ram region i.e bios data region the kernel creates a shared

Crash of VMM or TD termination? If VMM crashes in this case, it has to be
fixed.

> In this particular case the
> scenario was a userspace process reading something from the bios data

I think it should lead to unrecoverable EPT-violation, but not VMM crash.

> Fix this by simply forbidding access to /dev/mem when running as an TDX
> guest.

I think we need to think wider. What about applying a subset of LOCKDOWN_*
in all coco guests by default. Many of them are relevant for the guest security.

---

## [5] Nikolay Borisov — 2025-03-18
*Subject: Re: [RFC PATCH] /dev/mem: Disable /dev/mem under TDX guest*

On 18.03.25 г. 14:23 ч., Kirill A. Shutemov wrote:
> On Tue, Mar 18, 2025 at 01:36:04PM +0200, Nikolay Borisov wrote:
>> If a piece of memory is read from /dev/mem that falls outside of the

Went back through the bug reports and it seems this causes a SEPT 
violation inside the guest, which crashes, and is then re-created by 
GCP. So it would seem this causes an SEPT violation, rather than a VMM 
crash, my bad for mixing up the symptoms.

> 
>> In this particular case the

<nod> You are correct.

> 
>> Fix this by simply forbidding access to /dev/mem when running as an TDX

How do you envision this to work, by introducing another 
CONFIG_LOCK_DOWN_KERNEL_FORCE_COCO or some such ? Will it be opt-in or 
mandatory?

Should we decide to follow the lockdown route this means the owner of 
the coco guest will have the ability to disable it and a misbehaving 
userspace process will still be able to induce an EPT violation.


>

---

## [6] Kirill A. Shutemov — 2025-03-18
*Subject: Re: [RFC PATCH] /dev/mem: Disable /dev/mem under TDX guest*

On Tue, Mar 18, 2025 at 02:53:34PM +0200, Nikolay Borisov wrote:
> > I think we need to think wider. What about applying a subset of LOCKDOWN_*
> > in all coco guests by default. Many of them are relevant for the guest security.

I think cc_platform_has(CC_ATTR_xxx) should enabled some subset of
LOCKDOWN_*. No need in new config options.

> Should we decide to follow the lockdown route this means the owner of the
> coco guest will have the ability to disable it and a misbehaving userspace

Sure. It can shoot itself in the foot.

---

## [7] Nikolay Borisov — 2025-03-18
*Subject: Re: [RFC PATCH] /dev/mem: Disable /dev/mem under TDX guest*

On 18.03.25 г. 15:27 ч., Kirill A. Shutemov wrote:
> On Tue, Mar 18, 2025 at 02:53:34PM +0200, Nikolay Borisov wrote:
>>> I think we need to think wider. What about applying a subset of LOCKDOWN_*

Care to suggest which ones should be included? The way lockdown works at 
the moment is that it only supports 2 levels (check lock_kernel_down() 
and lockdown_is_locked_down()) at which you can lockdown - INTEGRITY_MAX 
and CONFIDENTIALITY_MAX,  where each level includes everything below it. 
So by choosing integrity max you get:

     19         LOCKDOWN_MODULE_SIGNATURE, 

     18         LOCKDOWN_DEV_MEM, 

     17         LOCKDOWN_EFI_TEST, 

     16         LOCKDOWN_KEXEC, 

     15         LOCKDOWN_HIBERNATION, 

     14         LOCKDOWN_PCI_ACCESS, 

     13         LOCKDOWN_IOPORT, 

     12         LOCKDOWN_MSR, 

     11         LOCKDOWN_ACPI_TABLES, 

     10         LOCKDOWN_DEVICE_TREE, 

      9         LOCKDOWN_PCMCIA_CIS, 

      8         LOCKDOWN_TIOCSSERIAL, 

      7         LOCKDOWN_MODULE_PARAMETERS, 

      6         LOCKDOWN_MMIOTRACE, 

      5         LOCKDOWN_DEBUGFS, 

      4         LOCKDOWN_XMON_WR, 

      3         LOCKDOWN_BPF_WRITE_USER, 

      2         LOCKDOWN_DBG_WRITE_KERNEL, 

      1         LOCKDOWN_RTAS_ERROR_INJECTION,

Given this if we for example choose to lockdown the kernel for DEV_MEM, 
we'll also get the MODULE_SIGNATURE lockdown as well. I find this 
somewhat inflexible as we might have to rejuggle the current ordering.

> 
>> Should we decide to follow the lockdown route this means the owner of the

---

## [8] Dave Hansen — 2025-03-18
*Subject: Re: [RFC PATCH] /dev/mem: Disable /dev/mem under TDX guest*

On 3/18/25 04:36, Nikolay Borisov wrote:
> 1. Should we forbid getting a descriptor to /dev/mem (this patch)
> 2. Skip creating /dev/mem altogether3

Like Kirill mentioned, it would be nice to leverage the existing hooks:

        if (!capable(CAP_SYS_RAWIO))
                return -EPERM;

        rc = security_locked_down(LOCKDOWN_DEV_MEM);
        if (rc)
                return rc;

Lockdown seems like a decent fit. We'd also ideally check
lockdown_is_locked_down() in x86 code and spew epithets if someone is
booting a CoCo guest without lockdown.

> 3. Possibly tinker with internals of ioremap to ensure that no memory which is
> backed by kvm memslots is remapped as shared.

It's not just memslots, though. It's any TDX private memory which
includes stuff the TDX module uses like the PAMT or SEPT pages.

---

## [9] Nikolay Borisov — 2025-03-18
*Subject: Re: [RFC PATCH] /dev/mem: Disable /dev/mem under TDX guest*

On 18.03.25 г. 16:48 ч., Dave Hansen wrote:
> On 3/18/25 04:36, Nikolay Borisov wrote:
>> 1. Should we forbid getting a descriptor to /dev/mem (this patch)

How about something along those lines to warn when a CoCo guest is run 
but lockdown is not enabled:

diff --git a/arch/x86/coco/core.c b/arch/x86/coco/core.c
index 9a0ddda3aa69..e34f6c0f9269 100644
--- a/arch/x86/coco/core.c
+++ b/arch/x86/coco/core.c
@@ -10,6 +10,7 @@

  #include <linux/export.h>
  #include <linux/cc_platform.h>
+#include <linux/security.h>
  #include <linux/string.h>
  #include <linux/random.h>

@@ -206,6 +207,25 @@ void cc_platform_set(enum cc_attr attr)
         }
  }

+static int __init cc_lockdown_warn(void)
+{
+       if (!cc_platform_has(CC_ATTR_GUEST_MEM_ENCRYPT))
+               return 0;
+
+       /* Not a CoCo guest */
+       if (!cpu_feature_enabled(X86_FEATURE_TDX_GUEST) ||
+           cc_platform_has(CC_ATTR_HOST_SEV_SNP))
+               return 0;
+
+
+       if (!security_locked_down(LOCKDOWN_DEV_MEM))
+               pr_warn("CoCo guest running with kernel lockdown 
disabled\n");
+
+       return 0;
+}
+late_initcall(cc_lockdown_warn);

---

## [10] Dan Williams — 2025-03-18
*Subject: Re: [RFC PATCH] /dev/mem: Disable /dev/mem under TDX guest*

Nikolay Borisov wrote:
> If a piece of memory is read from /dev/mem that falls outside of the
> System Ram region i.e bios data region the kernel creates a shared

It seems unfortunate that the kernel is allowing conflicting mappings of
the same pfn. Is this not just a track_pfn_remap() bug report? In other
words, whatever established the conflicting private mapping failed to do
a memtype_reserve() with the encryption setting such that
track_pfn_remap() could find it and enforce a consistent mapping.

Otherwise, kernel_lockdown also disables useful mechanisms like debugfs,
and feels like it does not solve the underlying problem. Not all
ioremap() callers in the kernel are aware of a potential
ioremap_encrypted() dependendency.

> 4. Eliminate the access to 0x472 from the x86 reboot path, after all we don't
> really have a proper bios at that address.

---

## [11] Kirill A. Shutemov — 2025-03-20
*Subject: Re: [RFC PATCH] /dev/mem: Disable /dev/mem under TDX guest*

On Tue, Mar 18, 2025 at 04:21:21PM +0200, Nikolay Borisov wrote:
> 
> 

Urgh.. I thought we track the lockdown level for each feature separately,
but it is lockdown depth instead :/

Maybe it is worth reworking internals to have bitmap of lockdown features?
It will allow us to pick and choose features to lockdown.

---

## [12] Nikolay Borisov — 2025-03-24
*Subject: Re: [RFC PATCH] /dev/mem: Disable /dev/mem under TDX guest*

On 18.03.25 г. 21:06 ч., Dan Williams wrote:
> Nikolay Borisov wrote:
>> If a piece of memory is read from /dev/mem that falls outside of the

I'm not an expert into this, but looking at the code it seems 
memtype_reserve deals with the memory type w.r.t PAT/MTRR i.e the 
cacheability of the memory, not whether the mapping is consistent w.r.t 
to other, arbitrary attributes.

> 
> Otherwise, kernel_lockdown also disables useful mechanisms like debugfs,

---

## [13] Dan Williams — 2025-03-25
*Subject: Re: [RFC PATCH] /dev/mem: Disable /dev/mem under TDX guest*

Nikolay Borisov wrote:
[..]
> > It seems unfortunate that the kernel is allowing conflicting mappings of
> > the same pfn. Is this not just a track_pfn_remap() bug report? In other

Right, but the observation is that "something" decides to map that first
page of memory as private and then xlate_dev_mem_ptr() fails to maintain
consistent mapping.

So memtype_reserve() is indeed an awkward place to carry this
information and overkill for this particular bug.

However, something like the following is more appropriate than saying
/dev/mem is outright forbidden for guests.

diff --git a/arch/x86/mm/ioremap.c b/arch/x86/mm/ioremap.c
index 38ff7791a9c7..4a7a5fc83039 100644
--- a/arch/x86/mm/ioremap.c
+++ b/arch/x86/mm/ioremap.c
@@ -122,6 +122,10 @@ static void __ioremap_check_other(resource_size_t addr, struct ioremap_desc *des
                return;
        }
 
+       /* Ensure BIOS data (see devmem_is_allowed()) is consistently mapped */
+       if (PHYS_PFN(addr) < 256)
+               desc->flags |= IORES_MAP_ENCRYPTED;
+
        if (!IS_ENABLED(CONFIG_EFI))
                return;
 
...because if the guest image wants to trust root why enforce piecemeal
lockdown semantics?

---

## [14] Nikolay Borisov — 2025-03-28
*Subject: Re: [RFC PATCH] /dev/mem: Disable /dev/mem under TDX guest*

On 25.03.25 г. 20:16 ч., Dan Williams wrote:
> Nikolay Borisov wrote:
> [..]


This fixes the issue as now the remapped address and the direct mapping 
are identical.

Tested-by: Nikolay Borisov <nik.borisov@suse.com>

Would you care to send a proper patch ?

---
