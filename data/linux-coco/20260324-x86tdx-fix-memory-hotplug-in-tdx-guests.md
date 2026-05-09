---
title: 'x86/tdx: Fix memory hotplug in TDX guests'
date: 2026-03-24
last_reply: 2026-04-10
message_count: 27
participants: ['Marc-André Lureau', 'Edgecombe, Rick P', 'Paolo Bonzini', 'Chenyi Qiang', 'Yan Zhao', 'David Hildenbrand (Arm)', 'Kiryl Shutsemau', 'Pratik R. Sampat', 'Reshetova, Elena', 'Duan, Zhenzhong']
---

## [1] Marc-André Lureau — 2026-03-24

In TDX guests, hotplugged memory (e.g., via virtio-mem) must be accepted
via TDG.MEM.PAGE.ACCEPT before use. The first access to an unaccepted
page triggers a fatal "SEPT entry in PENDING state" EPT violation and
KVM terminates the guest.

This was discovered while testing virtio-mem resize with TDX guests.
The associated QEMU virtio-mem + TDX patch series is under review at:
https://patchew.org/QEMU/20260226140001.3622334-1-marcandre.lureau@redhat.com/

The fix has two parts:

1. Handle TDG.MEM.PAGE.ACCEPT "success-with-warning" returns for pages
   that are already in MAPPED state (e.g., after offline/re-online
   cycles), instead of treating them as fatal errors.

2. Register a MEM_GOING_ONLINE memory hotplug notifier that calls
   tdx_accept_memory() before pages are freed to the buddy allocator.
   The TDCALL transparently triggers KVM-side page augmentation (AUG)
   followed by acceptance, avoiding the fatal EPT violation path.

The solution was suggested by Claude Code (Anthropic) and has been
tested with virtio-mem hot-add on a TDX guest. I did my best to review
the produced code and comments. Apologies if the agent did hallucinate.
Let me know if I need to check or correct something.

Thanks,

Signed-off-by: Marc-André Lureau <marcandre.lureau@redhat.com>
---
Marc-André Lureau (2):
      x86/tdx: Handle TDG.MEM.PAGE.ACCEPT success-with-warning returns
      x86/tdx: Accept hotplugged memory before online

 arch/x86/coco/tdx/tdx-shared.c |  2 +-
 arch/x86/coco/tdx/tdx.c        | 38 ++++++++++++++++++++++++++++++++++++++
 2 files changed, 39 insertions(+), 1 deletion(-)
---
base-commit: c369299895a591d96745d6492d4888259b004a9e
change-id: 20260324-tdx-hotplug-fixes-644d009dad63

Best regards,

---

## [2] Marc-André Lureau — 2026-03-24
*Subject: [PATCH 1/2] x86/tdx: Handle TDG.MEM.PAGE.ACCEPT
 success-with-warning returns*

try_accept_one() treats any non-zero return from __tdcall() as a
failure. However, per the TDX Module Base Spec (Table SEPT Walk Cases),
TDG.MEM.PAGE.ACCEPT returns a non-zero status code with bit 63 clear
when the target page is already in MAPPED state (i.e., already
accepted). This is a "success-with-warning" -- the page is usable and no
action is needed.

Check only bit 63 (TDX_ERROR) to distinguish real errors from
success-with-warning returns, rather than treating all non-zero values
as failures.

Assisted-by: Claude:claude-opus-4-6
Signed-off-by: Marc-André Lureau <marcandre.lureau@redhat.com>
---
 arch/x86/coco/tdx/tdx-shared.c | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)

diff --git a/arch/x86/coco/tdx/tdx-shared.c b/arch/x86/coco/tdx/tdx-shared.c
index 1655aa56a0a51..24983601a2ded 100644
--- a/arch/x86/coco/tdx/tdx-shared.c
+++ b/arch/x86/coco/tdx/tdx-shared.c
@@ -35,7 +35,7 @@ static unsigned long try_accept_one(phys_addr_t start, unsigned long len,
 	}
 
 	args.rcx = start | page_size;
-	if (__tdcall(TDG_MEM_PAGE_ACCEPT, &args))
+	if (__tdcall(TDG_MEM_PAGE_ACCEPT, &args) & TDX_ERROR)
 		return 0;
 
 	return accept_size;

---

## [3] Marc-André Lureau — 2026-03-24
*Subject: [PATCH 2/2] x86/tdx: Accept hotplugged memory before online*

In TDX guests, hotplugged memory (e.g., via virtio-mem) is never
accepted before use. The first access triggers a fatal "SEPT entry in
PENDING state" EPT violation and KVM terminates the guest.

Fix this by registering a MEM_GOING_ONLINE memory hotplug notifier that
calls tdx_accept_memory() for the range being onlined.

The notifier returns NOTIFY_BAD on acceptance failure, preventing the
memory from going online.

Assisted-by: Claude:claude-opus-4-6
Reported-by: Chenyi Qiang <chenyi.qiang@intel.com>
Signed-off-by: Marc-André Lureau <marcandre.lureau@redhat.com>
---
 arch/x86/coco/tdx/tdx.c | 38 ++++++++++++++++++++++++++++++++++++++
 1 file changed, 38 insertions(+)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 7b2833705d475..89f90bc303258 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -8,6 +8,7 @@
 #include <linux/export.h>
 #include <linux/io.h>
 #include <linux/kexec.h>
+#include <linux/memory.h>
 #include <asm/coco.h>
 #include <asm/tdx.h>
 #include <asm/vmx.h>
@@ -1194,3 +1195,40 @@ void __init tdx_early_init(void)
 
 	tdx_announce();
 }
+
+#ifdef CONFIG_MEMORY_HOTPLUG
+static int tdx_guest_memory_notifier(struct notifier_block *nb,
+				     unsigned long action, void *v)
+{
+	struct memory_notify *mn = v;
+	phys_addr_t start, end;
+
+	if (action != MEM_GOING_ONLINE)
+		return NOTIFY_OK;
+
+	start = PFN_PHYS(mn->start_pfn);
+	end = start + PFN_PHYS(mn->nr_pages);
+
+	if (!tdx_accept_memory(start, end)) {
+		pr_err("Failed to accept memory [0x%llx, 0x%llx)\n",
+		       (unsigned long long)start,
+		       (unsigned long long)end);
+		return NOTIFY_BAD;
+	}
+
+	return NOTIFY_OK;
+}
+
+static struct notifier_block tdx_guest_memory_nb = {
+	.notifier_call = tdx_guest_memory_notifier,
+};
+
+static int __init tdx_guest_memory_init(void)
+{
+	if (!cpu_feature_enabled(X86_FEATURE_TDX_GUEST))
+		return 0;
+
+	return register_memory_notifier(&tdx_guest_memory_nb);
+}
+core_initcall(tdx_guest_memory_init);
+#endif

---

## [4] Edgecombe, Rick P — 2026-03-24
*Subject: Re: [PATCH 1/2] x86/tdx: Handle TDG.MEM.PAGE.ACCEPT
 success-with-warning returns*

On Tue, 2026-03-24 at 19:21 +0400, Marc-André Lureau wrote:
> try_accept_one() treats any non-zero return from __tdcall() as a
> failure. However, per the TDX Module Base Spec (Table SEPT Walk Cases),

Hmm. Accepting private memory is a security sensitive operation, so I think it
is probably bad to silently hide the detection of re-accepting.

For example, if the kernel accepts a page and sets some values in it, the VMM
could reset the data to zero by re-adding the page and letting the second accept
zero it. It allows the VMM to have some limited ability to mess with guest data.
If we detect a re-accept we should probably warn on it actually.

Not sure on if the specific case in this series is problematic, but this patch
changes the behavior generally.

---

## [5] Edgecombe, Rick P — 2026-03-24
*Subject: Re: [PATCH 2/2] x86/tdx: Accept hotplugged memory before online*

On Tue, 2026-03-24 at 19:21 +0400, Marc-André Lureau wrote:
> In TDX guests, hotplugged memory (e.g., via virtio-mem) is never
> accepted before use. The first access triggers a fatal "SEPT entry in

Does this depend on patch 1 somehow?

---

## [6] Marc-André Lureau — 2026-03-25
*Subject: Re: [PATCH 2/2] x86/tdx: Accept hotplugged memory before online*

Hi

On Wed, Mar 25, 2026 at 2:04 AM Edgecombe, Rick P
<rick.p.edgecombe@intel.com> wrote:
>
> On Tue, 2026-03-24 at 19:21 +0400, Marc-André Lureau wrote:

Yes, if I plug, unplug and plug again I get this without PATCH 1:
[root@rhel10-server ~]# [ 5707.392231] virtio_mem virtio5: plugged
size: 0x80000000
[ 5707.395583] virtio_mem virtio5: requested size: 0x0

[root@rhel10-server ~]# [ 5714.648501] virtio_mem virtio5: plugged
size: 0x2e00000
[ 5714.651808] virtio_mem virtio5: requested size: 0x80000000
[ 5714.676296] tdx: Failed to accept memory [0x108000000, 0x110000000)
[ 5714.683980] tdx: Failed to accept memory [0x110000000, 0x118000000)
[ 5714.686997] tdx: Failed to accept memory [0x140000000, 0x148000000)
[ 5714.689989] tdx: Failed to accept memory [0x128000000, 0x130000000)
[ 5714.694981] tdx: Failed to accept memory [0x148000000, 0x150000000)
[ 5714.704064] tdx: Failed to accept memory [0x138000000, 0x140000000)
[ 5714.710144] tdx: Failed to accept memory [0x118000000, 0x120000000)
[ 5714.722532] tdx: Failed to accept memory [0x130000000, 0x138000000)

My understanding is that QEMU should eventually unplug the memory and
PUNCH_HOLE then KVM should TDH.MEM.PAGE.REMOVE, but that doesn't seem
to happen. Is this strictly required? According to the specification,
it may not be.

---

## [7] Edgecombe, Rick P — 2026-03-25
*Subject: Re: [PATCH 2/2] x86/tdx: Accept hotplugged memory before online*

On Wed, 2026-03-25 at 14:29 +0400, Marc-André Lureau wrote:
> > Does this depend on patch 1 somehow?
> 

Ah, I see now! So the problem is not that the kernel is accidentally
re-accepting the memory. It's that host userspace is not actually
removing the memory during unplug. Hmm. Why not fix userspace then? If
the memory is unplugged it should not be usable anymore by the guest.
If it is still accessible then it seems kind of like a bug, no?

And! This totally justifies the warning. If the error is ignored, the
guest would think the memory is zeroed, but it could have old data in
it. It's exactly the kind of tricks a VMM could play to attack the
guest.

Another option could be to perform a TDG.MEM.PAGE.RELEASE TDCALL from
the guest when it unplugs the memory, to put it in an unaccepted state.
This would be more robust to buggy VMM behavior. But working around
buggy VM behavior would need a high bar.

---

## [8] Paolo Bonzini — 2026-03-26
*Subject: Re: [PATCH 2/2] x86/tdx: Accept hotplugged memory before online*

Il mer 25 mar 2026, 18:21 Edgecombe, Rick P
<rick.p.edgecombe@intel.com> ha scritto:
>
> Ah, I see now! So the problem is not that the kernel is accidentally

Wouldn't it actually be a very low bar? Just from these two paragraphs
of yours, it's clear that the line between buggy and malicious is
fine, in fact I think userspace should not care at all about removing
the memory. Only the guest cares about acceptance state.

Doing a RELEASE TDCALL seems more robust and not hard.

Paolo

---

## [9] Edgecombe, Rick P — 2026-03-26
*Subject: Re: [PATCH 2/2] x86/tdx: Accept hotplugged memory before online*

Hi Paolo!

On Thu, 2026-03-26 at 19:25 +0100, Paolo Bonzini wrote:
> > Another option could be to perform a TDG.MEM.PAGE.RELEASE TDCALL from
> > the guest when it unplugs the memory, to put it in an unaccepted state.

I mean I guess the contract is a bit fuzzy. The reason why I was thinking it was
a host userspace bug is because the conventional bare metal behavior of
unplugging memory should be that it is no longer accessible, right? If the guest
could still use the unplugged memory, it could be surprising for userspace and
the guest. Also, ideally I'd think the behavior wouldn't cover up guest bugs
where it tried to keep using the memory. So forgetting about TDX, isn't it
better behavior in general for unplugging memory, to actually pull it from the
guest? Did I look at that wrong?

As for the bar to change the guest, I was first imagining it would be the size
of the accept memory plumbing. Which was not a small effort and has had a steady
stream of bugs to squash where the accept was missed.

But I didn't actually POC anything to check the scope so maybe that was a bit
hasty. Should we do a POC? But considering the scope, I wonder if SNP has the
same problem.

---

## [10] Chenyi Qiang — 2026-03-27
*Subject: Re: [PATCH 2/2] x86/tdx: Accept hotplugged memory before online*

On 3/25/2026 6:29 PM, Marc-André Lureau wrote:
> Hi
> 

I guess it doesn't happen because virtio-mem in QEMU only PUNCH_HOLE the
shared memory by ram_block_discard_range() but it doesn't touch the private
memory which should be discarded by ram_block_discard_guest_memfd_range().

Is this strictly required? According to the specification,
> it may not be.
>

---

## [11] Yan Zhao — 2026-03-27
*Subject: Re: [PATCH 2/2] x86/tdx: Accept hotplugged memory before online*

On Tue, Mar 24, 2026 at 07:21:48PM +0400, Marc-Andr� Lureau wrote:
> In TDX guests, hotplugged memory (e.g., via virtio-mem) is never
> accepted before use. The first access triggers a fatal "SEPT entry in
If I read the code correctly,

online_pages
  1. memory_notify(MEM_GOING_ONLINE, &mem_arg);
  2. online_pages_range(pfn, nr_pages); 
       (*online_page_callback)(page, order);
          generic_online_page
	      __free_pages_core(page, order, MEMINIT_HOTPLUG);

In __free_pages_core(), there's accept_memory() already:

    if (page_contains_unaccepted(page, order)) {
          if (order == MAX_PAGE_ORDER && __free_unaccepted(page))
               return;

         accept_memory(page_to_phys(page), PAGE_SIZE << order);
    }

__free_unaccepted() also adds the pages to the unaccepted_pages list, so
cond_accept_memory() will accept the memory later:

So, is it because the virtio mem sets online_page_callback to
virtio_mem_online_page_cb, which doesn't invoke __free_pages_core() properly?

Or am I missing something that makes the memory notifier approach necessary?

Thanks
Yan

> +core_initcall(tdx_guest_memory_init);
> +#endif

---

## [12] David Hildenbrand (Arm) — 2026-03-27
*Subject: Re: [PATCH 2/2] x86/tdx: Accept hotplugged memory before online*

On 3/27/26 04:05, Chenyi Qiang wrote:
> 
> 

So far nobody specified how virtio-mem should behave in a CoCo environment.

I assume that we need enhancements on the driver and the device side.

In Linux, we should not be accepting memory during memory
onlining/offlining through notifiers, as we might only hot(un)plug parts
of a memory block etc.

We need some explicit calls into the core before we hand hotplugged
memory to the core, and before we hand back unplugged memory to the device.

In QEMU, I would similarly assume that we might have to perform some
additional work when converting memory blocks. *maybe* that would just
be done by the guest that converts memory from private to shared before
unplug etc.

---

## [13] Marc-André Lureau — 2026-03-30
*Subject: Re: [PATCH 2/2] x86/tdx: Accept hotplugged memory before online*

Hi

On Fri, Mar 27, 2026 at 1:09 PM Yan Zhao <yan.y.zhao@intel.com> wrote:
>
> On Tue, Mar 24, 2026 at 07:21:48PM +0400, Marc-André Lureau wrote:

virtio-mem doesn't modify efi_unaccepted_memory bitmap (populated by
TDVF code when the VM is started)

---

## [14] Kiryl Shutsemau — 2026-03-30
*Subject: Re: [PATCH 2/2] x86/tdx: Accept hotplugged memory before online*

On Thu, Mar 26, 2026 at 08:40:06PM +0000, Edgecombe, Rick P wrote:
> Hi Paolo!
> 

Doing RELEASE will be required with TDX Connect in the picture.
Otherwise userspace wouldn't be able to pull the memory out of TD.
So, let's do it and drop the first patch.

We can suggest that userspace actually remove the memory, but I don't
think it should be part of the contract. Userspace might have a reasons
to keep the memory around.

---

## [15] Pratik R. Sampat — 2026-03-30
*Subject: Re: [PATCH 2/2] x86/tdx: Accept hotplugged memory before online*

On 3/26/26 4:40 PM, Edgecombe, Rick P wrote:
> Hi Paolo!
> 

SNP likely has an analogous issue too.
Failing to switch states on remove will cause that RMP entry to remain
validated. A malicious hypervisor could then remap this GPA to another HPA
which would put this in the Guest-Invalid state. On re-hotplug if we ignore
errors suggested by Patch 1 (in our case that'd be PVALIDATE_FAIL_NOUPDATE
error likely), we could have two RMP entries for the same GPA and both being
validated. This is dangerous because hypervisor could swap these at will.

Would it not be better to have this information in the unaccepted bitmap which
we could explicitly query to accept/unaccept?

For ACPI hardware-style hotplug I was working with the UEFI side on a POC to
reflect SRAT hotplug windows in UEFI_UNACCEPTED_MEMORY using
EFI_MEMORY_HOT_PLUGGABLE attribute and working to modify that spec. I’m less
sure what this description for virtio-mem would look like and if it'd be
possible to do this early-boot.

Thanks,
--Pratik

---

## [16] Edgecombe, Rick P — 2026-04-01
*Subject: Re: [PATCH 2/2] x86/tdx: Accept hotplugged memory before online*

On Mon, 2026-03-30 at 11:10 -0400, Pratik R. Sampat wrote:
> SNP likely has an analogous issue too.
> Failing to switch states on remove will cause that RMP entry to

Oh, I was just wondering if we could just zero the page on accept
failure for the case of already accepted. Handle the issue internally
and actually go back to something like patch 1. Will it work for SNP?

> 
> Would it not be better to have this information in the unaccepted

It makes me think about shared memory too. Should the unplug event also
signal the host to reset the memory to private? If the VMM is actually
not adjusting the guest mapping for a unplug/re-plug then the memory
would come back as shared.

But it really starts to feel like work the host should be doing.

> 
> For ACPI hardware-style hotplug I was working with the UEFI side on a

---

## [17] Edgecombe, Rick P — 2026-04-01
*Subject: Re: [PATCH 2/2] x86/tdx: Accept hotplugged memory before online*

On Wed, 2026-04-01 at 08:39 -0700, Edgecombe, Rick P wrote:
> > Would it not be better to have this information in the unaccepted
> > bitmap which we could explicitly query to accept/unaccept?

Although if memory was able to be unplugged, the Linux guest would have
reset the memory to private when it was done with the memory. But from
a interface perspective, it seems weird to require the guest to signal
this because private/shared state is ultimately controlled by the host.
Unlike accept state where the guest gets some say.

---

## [18] Reshetova, Elena — 2026-04-02
*Subject: RE: [PATCH 2/2] x86/tdx: Accept hotplugged memory before online*

> On Mon, 2026-03-30 at 11:10 -0400, Pratik R. Sampat wrote:
> > SNP likely has an analogous issue too.

I don't know about SNP, but if you are proposing to zero the page on
double acceptance, this is not great from security pov. It creates a
predictable behaviour primitive for the host to zero any data inside
the confidential guest and it can be misused (think of zeroing out a
page containing a cryptographic key).

---

## [19] Edgecombe, Rick P — 2026-04-02
*Subject: Re: [PATCH 2/2] x86/tdx: Accept hotplugged memory before online*

On Thu, 2026-04-02 at 08:18 +0000, Reshetova, Elena wrote:
> > Oh, I was just wondering if we could just zero the page on accept
> > failure for the case of already accepted. Handle the issue

Accept does zero the memory already. So the guest side operation is
doing an operation that says "make this memory usable in an known state
of zeros". And the operation complies. What is the difference?

>  It creates a
> predictable behaviour primitive for the host to zero any data inside

If the host can trigger an accept somehow in the guest (via something
like this or other issue), then the host can also remove, then AUG the
page from the S-EPT. This will result in a normal accept which also
zeros the page.

So the part about whether a triggered accept succeeds or returns an
already accepted error is already under the control of the host. I.e.,
if we don't have the zeroing behavior, the host can already cause the
page to get zeroed. So I don't think anything is regressed. Both come
down to how careful the guest is about what it accepts.

---

## [20] Reshetova, Elena — 2026-04-03
*Subject: RE: [PATCH 2/2] x86/tdx: Accept hotplugged memory before online*

> On Thu, 2026-04-02 at 08:18 +0000, Reshetova, Elena wrote:
> > > Oh, I was just wondering if we could just zero the page on accept

The difference is that you do it in a re-accept case. 

> 
> >  It creates a

Yes, that's why the guest currently does not allow accepting a page that
has already been accepted.  
> 
> So the part about whether a triggered accept succeeds or returns an

Yes, and my point is that we should not allow guest to freely double
accepting ever. 
For any use case that requires releasing memory and accepting it back,
it should be explicit action by the guest to track that memory has been
"released" (under correct and safe conditions) and then it is ok to accept
it back (even if it doesnt mean physically accepting it) and in this case it
is ok (and even strongly desired) to zero the page to simulate the normal
accept behaviour.

---

## [21] Edgecombe, Rick P — 2026-04-03
*Subject: Re: [PATCH 2/2] x86/tdx: Accept hotplugged memory before online*

On Fri, 2026-04-03 at 10:37 +0000, Reshetova, Elena wrote:
> > > > So the part about whether a triggered accept succeeds or returns an
> > > > already accepted error is already under the control of the host. > >

Hmm, it doesn't seem like you engaged with my point. Or at least I'm not
following what is exposed?

So I'm going to assume you agree that this procedure would not open up any
specific new capabilities for the host that don't exist today. And instead you
are just saying that the guest should have infrastructure to not double accept
memory in the first place.

But the problem here is not that the guest losing track of the accept state
actually. It is that the guest relies on the host to actually zap the S-EPT
before re-plugging memory at the same physical address space. So the guest is
tracking that the memory is released correctly. Better tracking will not help.
It relies on host behavior to not hit a double accept.

TDX connect will use this "unaccept" seamcall, so I asked Zhenzhong (Cced) how
much of what we need for that solution will just get added for TDX connect
anyway. It seems like we should make sure the same solution will work for both
SNP and TDX and keep the options open at this stage.

---

## [22] Reshetova, Elena — 2026-04-08
*Subject: RE: [PATCH 2/2] x86/tdx: Accept hotplugged memory before online*

> On Fri, 2026-04-03 at 10:37 +0000, Reshetova, Elena wrote:
> > > > > So the part about whether a triggered accept succeeds or returns an

Sorry, if I have been confusing. 

> 
> So I'm going to assume you agree that this procedure would not open up any

Yes, exactly this. 

> 
> But the problem here is not that the guest losing track of the accept state

I see the problem better now. Then I think the correct behaviour is for the
guest to keep tracking of accepted and released memory and then allow
to double accept iff the memory that it has tracked as being accepted and 
explicitly released. This way there should not be a possibility for the host to
misuse this for an arbitrary memory page.

Best Regards,
Elena.

---

## [23] Pratik R. Sampat — 2026-04-08
*Subject: Re: [PATCH 2/2] x86/tdx: Accept hotplugged memory before online*

>>
>> So I'm going to assume you agree that this procedure would not open up any

Thanks, I was a bit confused by that too. This clears it up.

> 
>>

This makes sense to me. For SNP, it is the guest that performs the pvalidate
rescind + RMP state change operation, so having this kind of tracking should
work well for all of us.

That said, adding to the unaccepted bitmap isn't entirely trivial. The bitmap
is allocated as a flexible array rather than a pointer, and changing that could
break kexec [1]. It might be worth maintaining a separate table to track
unaccepted hotplug memory instead.

[1]: https://lore.kernel.org/all/m3l6gcjmbabudtnqwv6w67t7iz2mpmbjyrpnmiq5k2iyargn5d@nyf2zzxx7yme/

Thanks,
Pratik

---

## [24] Duan, Zhenzhong — 2026-04-09
*Subject: RE: [PATCH 2/2] x86/tdx: Accept hotplugged memory before online*

>-----Original Message-----
>From: Edgecombe, Rick P <rick.p.edgecombe@intel.com>

For that solution, analog to hotplug, TDX Connect needs a hot-unplug handler to
use "release" seamcall to unaccept private memory before unplug, that's it. But
if the zapping S-EPT will not happen in host, I think this "release" seamcall is also
unnecessary for TDX Connect.

I also have a silly question which I looked over this thread and didn't find answer.
Do we have to support private memory hotplug, what benefit we get to support it?
If we only allow shared memory plug/unplug to TD, then we don't need this series.
Guest decides to convert shared memory to private after plug and do the opposite before unplug.
This works for both TDX connect and memory unplug as memory release is implicitly triggered
in memory convert.

Thanks
Zhenzhong

---

## [25] Marc-André Lureau — 2026-04-09
*Subject: Re: [PATCH 2/2] x86/tdx: Accept hotplugged memory before online*

Hi

On Thu, Apr 9, 2026 at 5:36 AM Duan, Zhenzhong <zhenzhong.duan@intel.com> wrote:
>
>

I did some successful experiments with modified QEMU & kernel, this
seems to work.

On virtio-mem plug, set_memory_encrypted() makes the memory private +
accepted. On unplug, make it return to shared with
set_memory_decrypted(). QEMU handles REQ_UNPLUG and can punch both
shared & guest_memfd planes (which will TDH.MEM.PAGE.REMOVE).
Re-plugging also works fine.

The virtio spec should probably be updated to explicitly define the
shared state on unplug and the private state on plug, driven by the
guest/driver. Those are KVM memory attributes, I suppose this is
generic enough.

---

## [26] Duan, Zhenzhong — 2026-04-10
*Subject: RE: [PATCH 2/2] x86/tdx: Accept hotplugged memory before online*

>-----Original Message-----
>From: Marc-André Lureau <marcandre.lureau@redhat.com>

Good to see, thanks for verifying.

>
>On virtio-mem plug, set_memory_encrypted() makes the memory private +

If guest called set_memory_decrypted() on unplug, QEMU punching
guest_memfd in REQ_UNPLUG is unnecessary as it's already taken during
memory convert. So just to confirm, you want QEMU to take cover the case
when guest failed on set_memory_decrypted() or never called it?

>
>The virtio spec should probably be updated to explicitly define the

Yes.

Thanks
Zhenzhong

---

## [27] David Hildenbrand (Arm) — 2026-04-10
*Subject: Re: [PATCH 2/2] x86/tdx: Accept hotplugged memory before online*

On 4/10/26 03:05, Duan, Zhenzhong wrote:
> 
> 

Once we have in-place conversion with guest_memfd, the punching will be
required, though.

---
