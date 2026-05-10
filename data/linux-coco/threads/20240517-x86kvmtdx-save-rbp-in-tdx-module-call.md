---
title: 'x86/kvm/tdx: Save %rbp in TDX_MODULE_CALL'
date: 2024-05-17
last_reply: 2024-05-24
message_count: 24
participants: ['Juergen Gross', 'Kirill A. Shutemov', 'Dave Hansen', 'Sean Christopherson', 'Huang, Kai']
---

## [1] Juergen Gross — 2024-05-17

While testing TDX host support patches, a crash of the host has been
observed a few instructions after doing a seamcall. Reason was a
clobbered %rbp (set to 0), which occurred in spite of the TDX module
offering the feature NOT to modify %rbp across TDX module calls.

In order not having to build the host kernel with CONFIG_FRAME_POINTER,
save %rbp across a seamcall/tdcall.

Signed-off-by: Juergen Gross <jgross@suse.com>
---
 arch/x86/virt/vmx/tdx/tdxcall.S | 7 +++++++
 1 file changed, 7 insertions(+)

diff --git a/arch/x86/virt/vmx/tdx/tdxcall.S b/arch/x86/virt/vmx/tdx/tdxcall.S
index 016a2a1ec1d6..68728acf0d3a 100644
--- a/arch/x86/virt/vmx/tdx/tdxcall.S
+++ b/arch/x86/virt/vmx/tdx/tdxcall.S
@@ -44,6 +44,10 @@
  */
 .macro TDX_MODULE_CALL host:req ret=0 saved=0
 	FRAME_BEGIN
+#ifndef CONFIG_FRAME_POINTER
+	/* Buggy firmware sometimes clobbers %rbp, so save it. */
+	pushq	%rbp
+#endif
 
 	/* Move Leaf ID to RAX */
 	mov %rdi, %rax
@@ -187,6 +191,9 @@
 	popq	%rbx
 .endif	/* \saved */
 
+#ifndef CONFIG_FRAME_POINTER
+	popq	%rbp
+#endif
 	FRAME_END
 	RET

---

## [2] Kirill A. Shutemov — 2024-05-17
*Subject: Re: [PATCH] x86/kvm/tdx: Save %rbp in TDX_MODULE_CALL*

On Fri, May 17, 2024 at 02:14:50PM +0200, Juergen Gross wrote:
> While testing TDX host support patches, a crash of the host has been
> observed a few instructions after doing a seamcall. Reason was a

There's a feature in TDX module 1.5 that prevents RBP modification across
TDH.VP.ENTER SEAMCALL. See NO_RBP_MOD in TDX Module 1.5 ABI spec.

I think it has to be enabled for all TDs and TDX modules that don't
support it need to be rejected.

---

## [3] Juergen Gross — 2024-05-17
*Subject: Re: [PATCH] x86/kvm/tdx: Save %rbp in TDX_MODULE_CALL*

On 17.05.24 15:55, Kirill A. Shutemov wrote:
> On Fri, May 17, 2024 at 02:14:50PM +0200, Juergen Gross wrote:
>> While testing TDX host support patches, a crash of the host has been

Yes, I know. I'm using the patch series:

   [PATCH v19 000/130] KVM TDX basic feature support

which I think does exactly that (see setup_tdparams() and tdx_module_setup()).

Nevertheless the clobbering happened, and saving/restoring %rbp made the
issue to go away. I suspect there is a path left still clobbering %rbp.

I was testing on an Emerald Rapids system:

# lscpu
Architecture:             x86_64
   CPU op-mode(s):         32-bit, 64-bit
   Address sizes:          47 bits physical, 57 bits virtual
   Byte Order:             Little Endian
CPU(s):                   256
   On-line CPU(s) list:    0-255
Vendor ID:                GenuineIntel
   BIOS Vendor ID:         Intel(R) Corporation
   Model name:             INTEL(R) XEON(R) PLATINUM 8592+
     BIOS Model name:      INTEL(R) XEON(R) PLATINUM 8592+  CPU @ 1.9GHz
     BIOS CPU family:      179
     CPU family:           6
     Model:                207
     Thread(s) per core:   2
     Core(s) per socket:   64
     Socket(s):            2
     Stepping:             2
...

BIOS version as printed during boot:

[    0.000000] DMI: Intel Corporation D50DNP/D50DNP, BIOS 
SE5C7411.86B.9535.D04.2312270518 12/27/2023


Juergen

---

## [4] Kirill A. Shutemov — 2024-05-17
*Subject: Re: [PATCH] x86/kvm/tdx: Save %rbp in TDX_MODULE_CALL*

On Fri, May 17, 2024 at 04:08:03PM +0200, Juergen Gross wrote:
> On 17.05.24 15:55, Kirill A. Shutemov wrote:
> > On Fri, May 17, 2024 at 02:14:50PM +0200, Juergen Gross wrote:

Looks like the check is broken:

https://lore.kernel.org/all/46mh5hinsv5mup2x7jv4iu2floxmajo2igrxb3haru3cgjukbg@v44nspjozm4h/

> Nevertheless the clobbering happened, and saving/restoring %rbp made the
> issue to go away. I suspect there is a path left still clobbering %rbp.

What is your TDX module version? My guess is that NOM_RBP_MOD is not
supported by it and given that the check is broken nobody enforces it.

---

## [5] Kirill A. Shutemov — 2024-05-17
*Subject: Re: [PATCH] x86/kvm/tdx: Save %rbp in TDX_MODULE_CALL*

On Fri, May 17, 2024 at 05:39:51PM +0300, Kirill A. Shutemov wrote:
> On Fri, May 17, 2024 at 04:08:03PM +0200, Juergen Gross wrote:
> > On 17.05.24 15:55, Kirill A. Shutemov wrote:

Err.. I think I confused myself. Please ignore.

---

## [6] Juergen Gross — 2024-05-17
*Subject: Re: [PATCH] x86/kvm/tdx: Save %rbp in TDX_MODULE_CALL*

On 17.05.24 16:39, Kirill A. Shutemov wrote:
> On Fri, May 17, 2024 at 04:08:03PM +0200, Juergen Gross wrote:
>> On 17.05.24 15:55, Kirill A. Shutemov wrote:

Just another data point: Before using this machine I was testing on
another one with older firmware. That one really didn't support NOM_RBP_MOD
and I needed to build the kernel with CONFIG_FRAME_POINTER enabled to get
past the check you are mentioning above.


Juergen

---

## [7] Dave Hansen — 2024-05-17
*Subject: Re: [PATCH] x86/kvm/tdx: Save %rbp in TDX_MODULE_CALL*

On 5/17/24 07:44, Juergen Gross wrote:
> Just another data point: Before using this machine I was testing on
> another one with older firmware. That one really didn't support NOM_RBP_MOD

For all intents and purposes, the modules that intentionally clobber RBP
don't support Linux. If buggy modules are accidentally clobbering RBP,
we can debate how much the kernel should bend over to accommodate them,
but my preference would be to ignore them.

I'd much rather put a deny list in the kernel than try to tolerate RBP
clobbering universally.

---

## [8] Jürgen Groß — 2024-05-17
*Subject: Re: [PATCH] x86/kvm/tdx: Save %rbp in TDX_MODULE_CALL*

On 17.05.24 17:16, Dave Hansen wrote:
> On 5/17/24 07:44, Juergen Gross wrote:
>> Just another data point: Before using this machine I was testing on

Would you be fine with adding a new X86_FEATURE (or BUG?) allowing to switch
RBP save/restore via ALTERNATIVE, controlled by a command line option?

Or maybe by adding a new CONFIG_TDX_MODULE_CAN_CLOBBER_RBP (probably using
a shorter name) option?

TBH I'm slightly puzzled that the firmware I'm using could make it outside
Intel. I'm fearing this might happen again.


Juergen

---

## [9] Dave Hansen — 2024-05-17
*Subject: Re: [PATCH] x86/kvm/tdx: Save %rbp in TDX_MODULE_CALL*

On 5/17/24 08:27, Jürgen Groß wrote:
> On 17.05.24 17:16, Dave Hansen wrote:
>> On 5/17/24 07:44, Juergen Gross wrote:

As a last resort maybe.

> TBH I'm slightly puzzled that the firmware I'm using could make it
> outside Intel. I'm fearing this might happen again.

You're puzzled that the firmware is either old buggy or both? Huh.

Intel ships all kinds of crazy pre-production stuff as development
platforms. Let's make sure we know what you've got before we go tearing
up mainline for it.

Because if the options are:

 1. Maintain code in mainline until the day I die^Wretire

or

 2. Get Jürgen a BIOS update so he stops sending patches

... it's kinda an easy choice. ;)

---

## [10] Juergen Gross — 2024-05-17
*Subject: Re: [PATCH] x86/kvm/tdx: Save %rbp in TDX_MODULE_CALL*

On 17.05.24 17:43, Dave Hansen wrote:
> On 5/17/24 08:27, Jürgen Groß wrote:
>> On 17.05.24 17:16, Dave Hansen wrote:

:-)

Is the BIOS version printed at boot enough to see what I have?

[    0.000000] DMI: Intel Corporation D50DNP/D50DNP, BIOS 
SE5C7411.86B.9535.D04.2312270518 12/27/2023


Juergen

---

## [11] Dave Hansen — 2024-05-17
*Subject: Re: [PATCH] x86/kvm/tdx: Save %rbp in TDX_MODULE_CALL*

On 5/17/24 08:48, Juergen Gross wrote:
> Is the BIOS version printed at boot enough to see what I have?
> 

I honestly don't know.

What we actually need is the TDX module version. I'm not sure how
tightly tied the TDX module is to the BIOS version. I suspect that
they're actually completely independent.

Once we have the specific TDX module version, we can go ask the folks
who write it if there were any RBP clobbering bugs.

---

## [12] Juergen Gross — 2024-05-17
*Subject: Re: [PATCH] x86/kvm/tdx: Save %rbp in TDX_MODULE_CALL*

On 17.05.24 17:52, Dave Hansen wrote:
> On 5/17/24 08:48, Juergen Gross wrote:
>> Is the BIOS version printed at boot enough to see what I have?

Okay, how to get the TDX module version?


Juergen

---

## [13] Sean Christopherson — 2024-05-17
*Subject: Re: [PATCH] x86/kvm/tdx: Save %rbp in TDX_MODULE_CALL*

On Fri, May 17, 2024, Kirill A. Shutemov wrote:
> On Fri, May 17, 2024 at 02:14:50PM +0200, Juergen Gross wrote:
> > While testing TDX host support patches, a crash of the host has been

LOL, "feature".  How was clobbering RBP not treated as a bug?  I'm party joking,
but also quite serious.  Unless I'm missing something, the guest ABI changes
based on whether or not NO_RBP_MOD is enabled, as a TDVMCALL that was previously
valid would now fail if the guest attempts to expose RBP to the host.

The whole point of Intel defining a guest-host ABI is to allow interoperability
between hypervisors and guests.  Allowing the hypervisor to arbitrarily change the
ABI is asinine.

> I think it has to be enabled for all TDs and TDX modules that don't
> support it need to be rejected.

Yes, because as above, IIUC it's a breaking change for the guest ABI.

---

## [14] Dave Hansen — 2024-05-17
*Subject: Re: [PATCH] x86/kvm/tdx: Save %rbp in TDX_MODULE_CALL*

On 5/17/24 09:12, Sean Christopherson wrote:
>> There's a feature in TDX module 1.5 that prevents RBP modification across
>> TDH.VP.ENTER SEAMCALL. See NO_RBP_MOD in TDX Module 1.5 ABI spec.

I'm on the same page.  It would have been far simpler for all involved
to retroactively say that modifying RBP is against the rules and any
module that does it is buggy. Get a new module if yours is buggy.

I _believe_ the intent was to support guest/host combinations that used
RBP for whatever reason.  But I'm not sure such a combination exists or
ever existed in practice.

---

## [15] Dave Hansen — 2024-05-17
*Subject: Re: [PATCH] x86/kvm/tdx: Save %rbp in TDX_MODULE_CALL*

On 5/17/24 08:58, Juergen Gross wrote:
> On 17.05.24 17:52, Dave Hansen wrote:
...
>> Once we have the specific TDX module version, we can go ask the folks
>> who write it if there were any RBP clobbering bugs.

You need something like this:

> https://lore.kernel.org/all/20231012134136.1310650-1-yi.sun@intel.com/

... and yeah, this needs to be upstream.

---

## [16] Kirill A. Shutemov — 2024-05-17
*Subject: Re: [PATCH] x86/kvm/tdx: Save %rbp in TDX_MODULE_CALL*

On Fri, May 17, 2024 at 09:34:56AM -0700, Dave Hansen wrote:
> On 5/17/24 09:12, Sean Christopherson wrote:
> >> There's a feature in TDX module 1.5 that prevents RBP modification across

There's a bug in EDK2. It specifies RBP in mask of registers to pass to
VMM. NO_RBP_MOD breaks it :/

---

## [17] Huang, Kai — 2024-05-20
*Subject: Re: [PATCH] x86/kvm/tdx: Save %rbp in TDX_MODULE_CALL*

On Fri, 2024-05-17 at 09:48 -0700, Dave Hansen wrote:
> On 5/17/24 08:58, Juergen Gross wrote:
> > On 17.05.24 17:52, Dave Hansen wrote:

This one prints TDX version info in the TDX guest, but not host.

The attached diff prints the TDX version (something like below) during
module initialization, and should meet Juergen's needs for temporary use:

[  113.543538] virt/tdx: module verson: major 1, minor 5, internal 0

> 
> .. and yeah, this needs to be upstream.

From this thread I think it makes sense to add code to the TDX host code
to print the TDX version during module initialization.  I'll start to work
on this.

One thing is from the spec TDX has "4 versions": major, minor, update,
internal.  They are all 16-bit, and the overall version can be written in:

	<Major>.<Minor>.<Update>.<Internal>, e.g., 1.5.05.01

(see TDX module 1.5 API spec, section 3.3.2 "TDX Module Version".)

The attached diff only prints major, minor and internal, but leaves the
update out because I believe it is for module runtime update (yet to
confirm).

Given there are 4 versions, I think it makes sense to implement reading
them based on this patchset ...

https://lore.kernel.org/kvm/6940c326-bfca-4c67-badf-ab5c086bf492@intel.com/T/

... which extends the global metadata reading code to support any
arbitrary struct and all element sizes (although all 4 versions are 16-
bit)?

---

## [18] Jürgen Groß — 2024-05-23
*Subject: Re: [PATCH] x86/kvm/tdx: Save %rbp in TDX_MODULE_CALL*

On 20.05.24 13:54, Huang, Kai wrote:
> On Fri, 2024-05-17 at 09:48 -0700, Dave Hansen wrote:
>> On 5/17/24 08:58, Juergen Gross wrote:

With that I got:

[   29.328484] virt/tdx: module verson: major 1, minor 5, internal 0


Juergen

---

## [19] Huang, Kai — 2024-05-23
*Subject: Re: [PATCH] x86/kvm/tdx: Save %rbp in TDX_MODULE_CALL*

On Thu, 2024-05-23 at 07:56 +0200, Jürgen Groß wrote:
> On 20.05.24 13:54, Huang, Kai wrote:
> > On Fri, 2024-05-17 at 09:48 -0700, Dave Hansen wrote:

Let me check TDX module guys on this and get back to you.

---

## [20] Huang, Kai — 2024-05-23
*Subject: Re: [PATCH] x86/kvm/tdx: Save %rbp in TDX_MODULE_CALL*

On Thu, 2024-05-23 at 10:30 +0000, Huang, Kai wrote:
> On Thu, 2024-05-23 at 07:56 +0200, Jürgen Groß wrote:
> > On 20.05.24 13:54, Huang, Kai wrote:

Hi Jurgen,

I was told the module starting with "1.5.06." has NO_RBP_MOD support.

And I think I was wrong about the <update> part of the version, and we
need that to determine the third part of the module version.

I was also told the 1.5.06 module hasn't been released to public yet, so I
guess your module doesn't support it.

I did another patch (attached) to check NO_RBP_MOD and reject module
initialization if it is not supported, and print out module version:

[  146.566641] virt/tdx: NO_RBP_MOD feature is not supported
[  146.572797] virt/tdx: module verson: 1.5.0.0
[  146.577731] virt/tdx: module initialization failed (-22)

You can have another try to verify at your side, if that helps.

---

## [21] Jürgen Groß — 2024-05-23
*Subject: Re: [PATCH] x86/kvm/tdx: Save %rbp in TDX_MODULE_CALL*

On 23.05.24 14:26, Huang, Kai wrote:
> On Thu, 2024-05-23 at 10:30 +0000, Huang, Kai wrote:
>> On Thu, 2024-05-23 at 07:56 +0200, Jürgen Groß wrote:

[   29.362806] virt/tdx: 4071192 KB allocated for PAMT
[   29.362828] virt/tdx: module verson: 1.5.1.0
[   29.362830] virt/tdx: module initialized


Juergen

---

## [22] Huang, Kai — 2024-05-24
*Subject: Re: [PATCH] x86/kvm/tdx: Save %rbp in TDX_MODULE_CALL*

On 24/05/2024 12:43 am, Jürgen Groß wrote:
> On 23.05.24 14:26, Huang, Kai wrote:
>> On Thu, 2024-05-23 at 10:30 +0000, Huang, Kai wrote:

Seems your module supports NO_RBP_MOD.

This feature is per-VM and also requires to be explicitly opt-in when 
creating the guest.  Could you check in your code whether the 
setup_tdparams() function has below code?

	td_params->exec_controls = TDX_CONTROL_FLAG_NO_RBP_MOD;

---

## [23] Huang, Kai — 2024-05-24
*Subject: Re: [PATCH] x86/kvm/tdx: Save %rbp in TDX_MODULE_CALL*

On 24/05/2024 10:34 am, Huang, Kai wrote:
> 
> 

Oh from another thread I saw you mentioned you have the above code 
enabled.  So from host's perspective the TD should have enabled this 
feature.

It's possible it is a TDX module bug if you are not able to see this 
flag in the guest using the way Kirill replied.

---

## [24] Jürgen Groß — 2024-05-24
*Subject: Re: [PATCH] x86/kvm/tdx: Save %rbp in TDX_MODULE_CALL*

On 24.05.24 00:34, Huang, Kai wrote:
> 
> 

I can confirm that it does have that.


Juergen

---
