---
title: 'KVM: TDX: Set SIGNIFCANT_INDEX flag for supported CPUIDs'
date: 2026-02-23
last_reply: 2026-02-25
message_count: 12
participants: ['Changyuan Lyu', 'Edgecombe, Rick P', 'Binbin Wu', 'Sean Christopherson']
---

## [1] Changyuan Lyu — 2026-02-23

Set the KVM_CPUID_FLAG_SIGNIFCANT_INDEX flag in the kvm_cpuid_entry2
structures returned by KVM_TDX_CAPABILITIES if the CPUID is indexed.
This ensures consistency with the CPUID entries returned by
KVM_GET_SUPPORTED_CPUID.

Additionally, add a WARN_ON_ONCE() to verify that the TDX module's
reported entries align with KVM's expectations regarding indexed
CPUID functions.

Suggested-by: Sean Christopherson <seanjc@google.com>
Signed-off-by: Changyuan Lyu <changyuanl@google.com>
---
 arch/x86/kvm/vmx/tdx.c | 8 +++++++-
 1 file changed, 7 insertions(+), 1 deletion(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 2d7a4d52ccfb4..0c524f9a94a6c 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -172,9 +172,15 @@ static void td_init_cpuid_entry2(struct kvm_cpuid_entry2 *entry, unsigned char i
 	entry->ecx = (u32)td_conf->cpuid_config_values[idx][1];
 	entry->edx = td_conf->cpuid_config_values[idx][1] >> 32;
 
-	if (entry->index == KVM_TDX_CPUID_NO_SUBLEAF)
+	if (entry->index == KVM_TDX_CPUID_NO_SUBLEAF) {
 		entry->index = 0;
+		entry->flags &= ~KVM_CPUID_FLAG_SIGNIFCANT_INDEX;
+	} else {
+		entry->flags |= KVM_CPUID_FLAG_SIGNIFCANT_INDEX;
+	}
 
+	WARN_ON_ONCE(cpuid_function_is_indexed(entry->function) !=
+		     !!(entry->flags & KVM_CPUID_FLAG_SIGNIFCANT_INDEX));
 	/*
 	 * The TDX module doesn't allow configuring the guest phys addr bits
 	 * (EAX[23:16]).  However, KVM uses it as an interface to the userspace

---

## [2] Edgecombe, Rick P — 2026-02-24
*Subject: Re: [PATCH] KVM: TDX: Set SIGNIFCANT_INDEX flag for supported CPUIDs*

+binbin

On Mon, 2026-02-23 at 13:43 -0800, Changyuan Lyu wrote:
> Set the KVM_CPUID_FLAG_SIGNIFCANT_INDEX flag in the kvm_cpuid_entry2
> structures returned by KVM_TDX_CAPABILITIES if the CPUID is indexed.

There are two callers of this. One is already zeroed, and the other has
stack garbage in flags. But that second caller doesn't look at the
flags so it is harmless. Maybe it would be simpler and clearer to just
zero init the entry struct in that caller. Then you don't need to clear
it here. Or alternatively set flags to zero above, and then add
KVM_CPUID_FLAG_SIGNIFCANT_INDEX if needed. Rather than manipulating a
single bit in a field of garbage, which seems weird.

> +	} else {
> +		entry->flags |= KVM_CPUID_FLAG_SIGNIFCANT_INDEX;

It warns on leaf 0x23 for me. Is it intentional?

This warning kind of begs the question of how how much consistency
there should be between KVM_TDX_CAPABILITIES and
KVM_GET_SUPPORTED_CPUID. There was quite a bit of debate on this and in
the end we moved forward with a solution that did the bare minimum
consistency checking.

We actually have been looking at some potential TDX module changes to
fix the deficiencies from not enforcing the consistency. But didn't
consider this pattern. Can you explain more about the failure mode?  

>  	/*
>  	 * The TDX module doesn't allow configuring the guest phys

---

## [3] Binbin Wu — 2026-02-24
*Subject: Re: [PATCH] KVM: TDX: Set SIGNIFCANT_INDEX flag for supported CPUIDs*

On 2/24/2026 9:57 AM, Edgecombe, Rick P wrote:
> +binbin
> 

I guess because the list in cpuid_function_is_indexed() is hard-coded
and 0x23 is not added into the list yet.

It's fine for existing KVM code because cpuid_function_is_indexed() is
only used to check that if a CPUID entry is queried without index, it
shouldn't be included in the indexed list.

But adding the consistency check here would cause compatibility issue.
Generally, if a new CPUID indexed function is added for some new CPU and
the TDX module reports it, KVM versions without the CPUID function in
the list will trigger the warning.


> 
> This warning kind of begs the question of how how much consistency

---

## [4] Sean Christopherson — 2026-02-24
*Subject: Re: [PATCH] KVM: TDX: Set SIGNIFCANT_INDEX flag for supported CPUIDs*

On Tue, Feb 24, 2026, Binbin Wu wrote:
> On 2/24/2026 9:57 AM, Edgecombe, Rick P wrote:
> >> diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c

+1, td_init_cpuid_entry2() should initialize flags to '0' and then set
KVM_CPUID_FLAG_SIGNIFCANT_INDEX as appropriate.

> >> +	} else {
> >> +		entry->flags |= KVM_CPUID_FLAG_SIGNIFCANT_INDEX;

Yeah, I was anticipating that we'd run afoul of leaves that aren't known to
the kernel.  FWIW, it looks like 0x24 is also indexed.

> It's fine for existing KVM code because cpuid_function_is_indexed() is
> only used to check that if a CPUID entry is queried without index, it

IMO, that's a good thing and working as intended.  WARNs aren't inherently evil.
While the goal is to be WARN-free, in this case triggering the WARN if the TDX
Module is updated (or new silicon arrives) is desirable, because it alerts us to
that new behavior, so that we can go update KVM.

But we should "fix" 0x23 and 0x24 before landing this patch.

---

## [5] Edgecombe, Rick P — 2026-02-24
*Subject: Re: [PATCH] KVM: TDX: Set SIGNIFCANT_INDEX flag for supported CPUIDs*

On Tue, 2026-02-24 at 08:03 -0800, Sean Christopherson wrote:
> > But adding the consistency check here would cause compatibility issue.
> > Generally, if a new CPUID indexed function is added for some new CPU and

Would we backport those changes then? I would usually think that if the TDX
module updates in such a way that triggers a warning in the kernel then it's a
TDX module bug.

I'm still not clear on the impact of this one, but assuming it's not too
serious, could we discuss the WIP CPUID bit TDX arch stuff in PUCK before doing
the change?

We were initially focusing on the problem of CPUID bits that affect host state,
but then recently were discussing how many other categories of potential
problems we should worry about at this point. So it would be good to understand
the impact here.

If this warn is a trend towards doubling back on the initial decision to expose
the CPUID interface to userspace, which I think is still doable and worth
considering as an alternative, then this also affects how we would want the TDX
module changes to work.

---

## [6] Sean Christopherson — 2026-02-24
*Subject: Re: [PATCH] KVM: TDX: Set SIGNIFCANT_INDEX flag for supported CPUIDs*

On Tue, Feb 24, 2026, Rick P Edgecombe wrote:
> On Tue, 2026-02-24 at 08:03 -0800, Sean Christopherson wrote:
> > > But adding the consistency check here would cause compatibility issue.

To stable@?  No, I don't think see any reason to do that.

> I'm still not clear on the impact of this one, but assuming it's not too
> serious, could we discuss the WIP CPUID bit TDX arch stuff in PUCK before doing

Sure, I don't see a rush on the patch.

> We were initially focusing on the problem of CPUID bits that affect host state,
> but then recently were discussing how many other categories of potential

Maybe I'm missing something, but I think you're reading into the WARN waaaay too
much.  I suggested it purely as a paranoid guard against the TDX Module doing
something bizarre and/or the kernel fat-fingering a CPUID function.  I.e. there's
no ulterior motive here, unless maybe Changyuan is planning world domination or
something. :-D

> which I think is still doable and worth considering as an alternative, then
> this also affects how we would want the TDX module changes to work.

---

## [7] Changyuan Lyu — 2026-02-24
*Subject: Re: [PATCH] KVM: TDX: Set SIGNIFCANT_INDEX flag for supported CPUIDs*

Hi Rick!

On Tue, 24 Feb 2026 01:57:46 +0000, Edgecombe, Rick P wrote:
> On Mon, 2026-02-23 at 13:43 -0800, Changyuan Lyu wrote:
> > [...]

Thanks for the suggestion. I agree that initializing entry->flags to 0 at
the start of td_init_cpuid_entry2() is much cleaner.

> > +	} else {
> > +		entry->flags |= KVM_CPUID_FLAG_SIGNIFCANT_INDEX;

Leaf 0x23 is not in the list of cpuid_function_is_indexed.
Thanks Binbin for the explanation!

> This warning kind of begs the question of how how much consistency
> there should be between KVM_TDX_CAPABILITIES and

The main purpose of this patch was to make the KVM_TDX_GET_CPUID API
more intuitive from userspace VMM's perspective.
Since both KVM_TDX_CAPABILITIES and KVM_GET_SUPPORTED_CPUID return
struct kvm_cpuid_entry2, I expected the semantic of the flag in both APIs
to be the same, as I didn't find any special notes to the contrary in the
TDX documentation Documentation/virt/kvm/x86/intel-tdx.rst .

> >  	/*
> >  	 * The TDX module doesn't allow configuring the guest phys

Regarding the WARN_ON_ONCE, I understand it touches on the larger
consistency and compatibility questions that require more discussion
as you and Sean mentioned. Since I am new to TDX and lack the full context
on those prior debates, I removed the WARN_ON_ONCE check and focus only on
the KVM_CPUID_FLAG_SIGNIFCANT_INDEX consistency fix, which was the core of
this patch.

Best,
Changyuan

-----------------------

From 18b967b718911c09872c3717d8ab083fa59c4a70 Mon Sep 17 00:00:00 2001
From: Changyuan Lyu <changyuanl@google.com>
Date: Fri, 20 Feb 2026 09:55:28 -0800
Subject: [PATCH] KVM: TDX: Set SIGNIFCANT_INDEX flag for supported CPUIDs

Set the KVM_CPUID_FLAG_SIGNIFCANT_INDEX flag in the kvm_cpuid_entry2
structures returned by KVM_TDX_CAPABILITIES if the CPUID is indexed.
This ensures consistency with the CPUID entries returned by
KVM_GET_SUPPORTED_CPUID.

Suggested-by: Sean Christopherson <seanjc@google.com>
Signed-off-by: Changyuan Lyu <changyuanl@google.com>
---
 arch/x86/kvm/vmx/tdx.c | 4 ++++
 1 file changed, 4 insertions(+)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 2d7a4d52ccfb4..1c039eab2f3d8 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -167,6 +167,7 @@ static void td_init_cpuid_entry2(struct kvm_cpuid_entry2 *entry, unsigned char i

 	entry->function = (u32)td_conf->cpuid_config_leaves[idx];
 	entry->index = td_conf->cpuid_config_leaves[idx] >> 32;
+	entry->flags = 0;
 	entry->eax = (u32)td_conf->cpuid_config_values[idx][0];
 	entry->ebx = td_conf->cpuid_config_values[idx][0] >> 32;
 	entry->ecx = (u32)td_conf->cpuid_config_values[idx][1];
@@ -174,6 +175,9 @@ static void td_init_cpuid_entry2(struct kvm_cpuid_entry2 *entry, unsigned char i

 	if (entry->index == KVM_TDX_CPUID_NO_SUBLEAF)
 		entry->index = 0;
+	else
+		entry->flags |= KVM_CPUID_FLAG_SIGNIFCANT_INDEX;
+

 	/*
 	 * The TDX module doesn't allow configuring the guest phys addr bits
--
2.53.0.414.gf7e9f6c205-goog

---

## [8] Edgecombe, Rick P — 2026-02-24
*Subject: Re: [PATCH] KVM: TDX: Set SIGNIFCANT_INDEX flag for supported CPUIDs*

On Tue, 2026-02-24 at 12:42 -0800, Sean Christopherson wrote:
> > I'm still not clear on the impact of this one, but assuming it's not too
> > serious, could we discuss the WIP CPUID bit TDX arch stuff in PUCK before

Should we try for tomorrow or next week?

> 
> > We were initially focusing on the problem of CPUID bits that affect host

Heh, well we are already seeing new CPUID bits that cause problems. Not
suspecting any secret motives, but more trying to glean something on your
thinking. Will be easier to discuss the topic.

> 
> > which I think is still doable and worth considering as an alternative, then

---

## [9] Binbin Wu — 2026-02-25
*Subject: Re: [PATCH] KVM: TDX: Set SIGNIFCANT_INDEX flag for supported CPUIDs*

On 2/25/2026 12:03 AM, Sean Christopherson wrote:
> 
>>>> +	} else {

0x24 is there already.

---

## [10] Binbin Wu — 2026-02-25
*Subject: Re: [PATCH] KVM: TDX: Set SIGNIFCANT_INDEX flag for supported CPUIDs*

On 2/25/2026 12:03 AM, Sean Christopherson wrote:
> On Tue, Feb 24, 2026, Binbin Wu wrote:
>> On 2/24/2026 9:57 AM, Edgecombe, Rick P wrote:

So it effectively leverages the TDX module's interface to retrieve the hardware
information to validate the hard-coded list.

Do we need to consider the panic_on_warn case? I guess the option will not be
enabled in a production environment?

> 
> But we should "fix" 0x23 and 0x24 before landing this patch.

---

## [11] Sean Christopherson — 2026-02-25
*Subject: Re: [PATCH] KVM: TDX: Set SIGNIFCANT_INDEX flag for supported CPUIDs*

On Wed, Feb 25, 2026, Binbin Wu wrote:
> Do we need to consider the panic_on_warn case? I guess the option will not be
> enabled in a production environment?

Nope.  That's even explicitly called out in Documentation/process/coding-style.rst:

  Do not worry about panic_on_warn users
  **************************************
  
  A few more words about panic_on_warn: Remember that ``panic_on_warn`` is an
  available kernel option, and that many users set this option. This is why
  there is a "Do not WARN lightly" writeup, above. However, the existence of
  panic_on_warn users is not a valid reason to avoid the judicious use
  WARN*(). That is because, whoever enables panic_on_warn has explicitly
  asked the kernel to crash if a WARN*() fires, and such users must be
  prepared to deal with the consequences of a system that is somewhat more
  likely to crash.

---

## [12] Binbin Wu — 2026-02-25
*Subject: Re: [PATCH] KVM: TDX: Set SIGNIFCANT_INDEX flag for supported CPUIDs*

On 2/25/2026 9:59 PM, Sean Christopherson wrote:
> On Wed, Feb 25, 2026, Binbin Wu wrote:
>> Do we need to consider the panic_on_warn case? I guess the option will not be

Thanks for the info, and sorry for not checking it before asking the question.

> 
>   Do not worry about panic_on_warn users

---
