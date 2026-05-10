---
title: 'x86/tdx: Generate SIGBUS on userspace MMIO'
date: 2024-05-28
last_reply: 2024-06-12
message_count: 9
participants: ['Kirill A. Shutemov', 'Dave Hansen', 'Chris Oo', 'Jeremi Piotrowski']
---

## [1] Kirill A. Shutemov — 2024-05-28

Currently, attempting to perform MMIO from userspace in a TDX guest
leads to a warning about an unexpected #VE and SIGSEGV being delivered
to the process.

Enlightened userspace may choose to handle MMIO on their own if the
kernel does not emulate it.

Handle the EPT_VIOLATION exit reason for userspace and deliver SIGBUS
instead of SIGSEGV. SIGBUS is more appropriate for the MMIO situation.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>

v2:
  - Rebased;
  - Fix grammar;
---
 arch/x86/coco/tdx/tdx.c | 19 ++++++++++++++-----
 1 file changed, 14 insertions(+), 5 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index c1cb90369915..d2aa93cebf5a 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -7,6 +7,7 @@
 #include <linux/cpufeature.h>
 #include <linux/export.h>
 #include <linux/io.h>
+#include <linux/sched/signal.h>
 #include <asm/coco.h>
 #include <asm/tdx.h>
 #include <asm/vmx.h>
@@ -630,6 +631,11 @@ void tdx_get_ve_info(struct ve_info *ve)
 	ve->instr_info  = upper_32_bits(args.r10);
 }
 
+static inline bool is_private_gpa(u64 gpa)
+{
+	return gpa == cc_mkenc(gpa);
+}
+
 /*
  * Handle the user initiated #VE.
  *
@@ -641,17 +647,20 @@ static int virt_exception_user(struct pt_regs *regs, struct ve_info *ve)
 	switch (ve->exit_reason) {
 	case EXIT_REASON_CPUID:
 		return handle_cpuid(regs, ve);
+	case EXIT_REASON_EPT_VIOLATION:
+		if (is_private_gpa(ve->gpa))
+			panic("Unexpected EPT-violation on private memory.");
+
+		force_sig_fault(SIGBUS, BUS_ADRERR, (void __user *)ve->gla);
+
+		/* Return 0 to avoid incrementing RIP */
+		return 0;
 	default:
 		pr_warn("Unexpected #VE: %lld\n", ve->exit_reason);
 		return -EIO;
 	}
 }
 
-static inline bool is_private_gpa(u64 gpa)
-{
-	return gpa == cc_mkenc(gpa);
-}
-
 /*
  * Handle the kernel #VE.
  *

---

## [2] Kirill A. Shutemov — 2024-06-10
*Subject: Re: [PATCH] x86/tdx: Generate SIGBUS on userspace MMIO*

On Tue, May 28, 2024 at 01:09:19PM +0300, Kirill A. Shutemov wrote:
> Currently, attempting to perform MMIO from userspace in a TDX guest
> leads to a warning about an unexpected #VE and SIGSEGV being delivered

Any feedback?

---

## [3] Dave Hansen — 2024-06-10
*Subject: Re: [PATCH] x86/tdx: Generate SIGBUS on userspace MMIO*

On 5/28/24 03:09, Kirill A. Shutemov wrote:
> Currently, attempting to perform MMIO from userspace in a TDX guest
> leads to a warning about an unexpected #VE and SIGSEGV being delivered

Does it _always_ result in a #VE?  Or is this only when guests mmap()
something like from a driver and the host doesn't back the shared memory?

> Enlightened userspace may choose to handle MMIO on their own if the
> kernel does not emulate it.

Is any userspace _actually_ doing this?  Sure, SIGBUS is more
appropriate but in practice unprepared userspace crashes either way.

> @@ -641,17 +647,20 @@ static int virt_exception_user(struct pt_regs *regs, struct ve_info *ve)
>  	switch (ve->exit_reason) {

This _really_ needs a comment, probably even a helper function where you
can actually explain what is going on.

I could barely remember what this is for today.  There's no hope for me
in a couple of years.

Just thinking through the possibilities here:

Private=> Private      	: no #VE
Private=> Anything else	: fatal shutdown
Shared => Shared	: no #VE
Shared => Private	: #VE (end up here)
Shared => !Present      : #VE (end up here)

So I think you're trying to differentiate between the last 2 cases.
"Shared => !Present" is the normal case where today the VM wants to
generate a VMEXIT.  We'll probably get these from setups where somebody
is trying to do good ol' device emulation but in TDX.

"Shared => Private" is an actual kernel bug.  Why panic() though?  Do we
*know* the system is unstable at this point?  Why not just dump an
error, send a fatal signal, and move on?

---

## [4] Kirill A. Shutemov — 2024-06-10
*Subject: Re: [PATCH] x86/tdx: Generate SIGBUS on userspace MMIO*

On Mon, Jun 10, 2024 at 06:55:56AM -0700, Dave Hansen wrote:
> On 5/28/24 03:09, Kirill A. Shutemov wrote:
> > Currently, attempting to perform MMIO from userspace in a TDX guest

See below.

> > Enlightened userspace may choose to handle MMIO on their own if the
> > kernel does not emulate it.

Microsoft folks have plans to do this. I don't know if any current code
handles SIGBUS this way.

> > @@ -641,17 +647,20 @@ static int virt_exception_user(struct pt_regs *regs, struct ve_info *ve)
> >  	switch (ve->exit_reason) {

Are you talking about page state vs. page mapping here?

It is wrong frame to think about it.

We get here as result of EPT violation. Either shared or secret EPT.
So we don't have an present EPT entry for the page or allowed permissions
doesn't match the access.

The is_private_gpa() check catches cases when private EPT doesn't have a
valid entry for page accessed via private mapping: page is not accepted or
removed by VMM. This case is only reachable for debug-TD. In for non-debug
TD it leads to unrecoverable TD exit. The same story as for kernel
addresses.

Normal shared memory doesn't cause #VE even if the memory was not
converted to shared explicitly. On the first access to a page via shared
mapping VMM will allocate a new page and fill EPT[*]. Except for GPA
ranges dedicated for MMIO. For these VMM will not fill EPT and it causes
#VE which interpreted as MMIO access.

Note that only emulated devices require such mechanism to get MMIO
working. For device passthrough, device MMIO range mapped directly into
the guest and handled transparently for the guest kernel.

Does it make sense?

[*] I don't like this implicit conversion to shared. I would prefer #VE
here too, but it is what we have.

---

## [5] Dave Hansen — 2024-06-11
*Subject: Re: [PATCH] x86/tdx: Generate SIGBUS on userspace MMIO*

On 6/10/24 06:55, Dave Hansen wrote:
>> Enlightened userspace may choose to handle MMIO on their own if the
>> kernel does not emulate it.

I also can't help but wonder if there's a better way to do this.

Just thinking out loud.... Ideally, we'd reject creating a potentially
troublesome VMA at mmap() time.  That's way better than, for instance,
panic()'ing at some random place in the middle of program execution.

But I guess that's likely not possible because someone could be doing a
VM_MIXEDMAP VMA that only has normal private pages and never _actually_
needs or has a shared page mapped.

I'd still love to know what actual kernel drivers and actual userspace
would be involved in this whole dance.  It's still way too theoretical
for me.

---

## [6] Chris Oo — 2024-06-11
*Subject: RE: [EXTERNAL] Re: [PATCH] x86/tdx: Generate SIGBUS on userspace MMIO*

We have a usecase where we have device drivers in usermode using vfio that mmap regions of the address space to access device BARs. In this case, when the #VE handler cannot emulate mmio on behalf of usermode, we need the SIGBUS to know if we should retry the attempt via doing a write via the vfio file descriptor. 

We don't want to have every mmio go through the vfio file descriptor, because for pages that are actually backed by physical device's BAR we won't take a #VE and introduce a bunch of extra path length, but only if the host has chosen to emulate some page in that BAR. We also don't have any way of knowing which pages will cause a #VE because there's no way for the guest to query which pages the host has chosen to emulate accesses on. 

Chris

-----Original Message-----
From: Dave Hansen <dave.hansen@intel.com> 
Sent: Tuesday, June 11, 2024 9:16 AM
To: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>; Dave Hansen <dave.hansen@linux.intel.com>; Thomas Gleixner <tglx@linutronix.de>; Ingo Molnar <mingo@redhat.com>; Borislav Petkov <bp@alien8.de>; x86@kernel.org; H. Peter Anvin <hpa@zytor.com>
Cc: linux-coco@lists.linux.dev; linux-kernel@vger.kernel.org; Chris Oo <cho@microsoft.com>; Dexuan Cui <decui@microsoft.com>; John Starks <John.Starks@microsoft.com>
Subject: [EXTERNAL] Re: [PATCH] x86/tdx: Generate SIGBUS on userspace MMIO

[Some people who received this message don't often get email from dave.hansen@intel.com. Learn why this is important at https://aka.ms/LearnAboutSenderIdentification ]

On 6/10/24 06:55, Dave Hansen wrote:
>> Enlightened userspace may choose to handle MMIO on their own if the 
>> kernel does not emulate it.

I also can't help but wonder if there's a better way to do this.

Just thinking out loud.... Ideally, we'd reject creating a potentially troublesome VMA at mmap() time.  That's way better than, for instance, panic()'ing at some random place in the middle of program execution.

But I guess that's likely not possible because someone could be doing a VM_MIXEDMAP VMA that only has normal private pages and never _actually_ needs or has a shared page mapped.

I'd still love to know what actual kernel drivers and actual userspace would be involved in this whole dance.  It's still way too theoretical for me.

---

## [7] Jeremi Piotrowski — 2024-06-11
*Subject: Re: [EXTERNAL] Re: [PATCH] x86/tdx: Generate SIGBUS on userspace MMIO*

On 11/06/2024 19:17, Chris Oo wrote:
> We have a usecase where we have device drivers in usermode using vfio that mmap regions of the address space to access device BARs. In this case, when the #VE handler cannot emulate mmio on behalf of usermode, we need the SIGBUS to know if we should retry the attempt via doing a write via the vfio file descriptor. 
> 

Is there a reason we can't fix the handler to do the #VE->mmio emulation for userspace too, so that this scenario
works just like outside of a CVM?

---

## [8] Kirill A. Shutemov — 2024-06-12
*Subject: Re: [EXTERNAL] Re: [PATCH] x86/tdx: Generate SIGBUS on userspace MMIO*

On Tue, Jun 11, 2024 at 07:25:27PM +0200, Jeremi Piotrowski wrote:
> Is there a reason we can't fix the handler to do the #VE->mmio emulation
> for userspace too, so that this scenario works just like outside of a

We are looking into it. It requires some groundwork to properly understand
risks of wider attack surface. I think we will get there, but it will take time.

---

## [9] Kirill A. Shutemov — 2024-06-12
*Subject: Re: [PATCH] x86/tdx: Generate SIGBUS on userspace MMIO*

On Tue, Jun 11, 2024 at 09:16:13AM -0700, Dave Hansen wrote:
> On 6/10/24 06:55, Dave Hansen wrote:
> >> Enlightened userspace may choose to handle MMIO on their own if the

I am not sure I follow.

panic() is only for catastrophic cases: VMM pulled memory from under us or
we mapped unaccepted memory into userspace. It should never happen.

We have the same check is_private_gpa() in virt_exception_kernel().

---
