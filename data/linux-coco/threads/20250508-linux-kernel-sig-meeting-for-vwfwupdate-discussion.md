---
title: 'Linux kernel SIG meeting for vwfwupdate discussion'
date: 2025-05-08
last_reply: 2025-06-25
message_count: 12
participants: ['Dionna Amalie Glaze', 'Dan Middleton', 'Ani Sinha', 'Alexander Graf', 'Gerd Hoffmann']
---

## [1] Dionna Amalie Glaze — 2025-05-08

Thanks everyone who could attend the CCC Linux Kernel SIG meeting
about FUKI and specifically the firmware replacement mechanism.
Please +cc any participants I missed.

Meeting minutes:
* the concept from its initial version that was Qemu-specific and used
specially-named FwCfg files to direct CVM context reconstruction with
a different ROM.
* the viewpoint of generalizing that interface to be an IGVM-based
firmware loading instruction in order to reduce the interface's
interpretation requirements to keep focused on an emerging standard.
* the usefulness of "single artifact" VM template distribution, such
that the firmware can be disk-image specific and not need extra
orchestration to lead to VM construction.
* constraints of the different VMM providers, namely
   + AWS does not have access to guest resources. A disk can only be
read by a guest VM.
   + Azure doesn't have this constraint and does not want to build a
stage 1 VM just to tear it down to boot a stage 2 VM every cold reset.
It's far more preferable for the host to have the option to determine
if an IGVM will be requested to load, in which case it should be
loaded directly without VM construction.
   + GCP emulates Qemu devices and could implement the FUKI interface,
but would prefer to use mechanisms that are standardized through
professional bodies like the UEFI forum. Faster boots without VM
reconstruction are also highly desirable.

Jon requested for Alex to give some more design consideration into a
mechanism that would satisfy both AWS and Azure's constraints.

Alex suggested the framework of a solution: mount the guest image,
search the boot partition for a specially named IGVM file, and launch
that instead of the CSP's firmware.
(Dionna notes outside of the meeting that this has the danger of being
an unsound optimization of directly loading the disk image under the
CSP firmware for FUKI application to load the IGVM due to no
requirement that the FUKI application load that specific IGVM file)

I look forward to our further discussion on how to provide a more
trustworthy Confidential Computing experience in the Cloud for our
customers :)

On Wed, May 7, 2025 at 4:04 PM Steve Rutherford <srutherford@google.com> wrote:
>
> Heads up, this meeting is tomorrow, May 8th at 9AM PDT (6PM CEST), if

---

## [2] Dan Middleton — 2025-05-12

The recording is now available:
https://www.youtube.com/watch?v=bio5BGhjui4

Additional Minutes:
https://docs.google.com/document/d/18D820gyt2xe84Jy6dGXgrNThApoozcekDzvIlK2_bd4/edit?tab=t.0#heading=h.4qh5zyiozbow 


Really interesting discussion.
Great that the discussion could be recruited on short notice.
Sounds like follow-up might be over a thread here, with those not
subscribed to linux-coco added directly.

Keep in mind that the next SIG session is available and you can not only
show pictures there, but can gesture and point to the same things to
clarify.. I don't understand this stage, this widget, this format.

Thanks,
Dan

On 5/8/25 12:29 PM, Dionna Amalie Glaze wrote:
> Thanks everyone who could attend the CCC Linux Kernel SIG meeting
> about FUKI and specifically the firmware replacement mechanism.

---

## [3] Ani Sinha — 2025-05-16

Is there any interest in sending a joint proposal in the upcoming KVM Forum based on the updated, latest incarnation of the idea? We can send a proposal now (deadline is June 9th I believe) and then work on the details in the subsequent weeks. I think we should be able to solidify the specifics of the hypervisor interface. When we presented this idea last year in the KVM forum, it was quite a bit fuzzy and we did not explore the IGVM angle at depth. 
So in my opinion, it will be a much better talk this time particularly with everyone (all major hyperscalers) showing interest on this.

Thanks
Ani
 

> On 12 May 2025, at 9:51 PM, Dan Middleton <dan.middleton@linux.intel.com> wrote:
>

---

## [4] Alexander Graf — 2025-05-16

Hey Ani,

We already presented concepts last year. If we want to preserve 
credibility, this year we need to show a solution that's either merged 
or almost merged upstream and ready to use.

Alex

On 16.05.25 08:02, Ani Sinha wrote:
> Is there any interest in sending a joint proposal in the upcoming KVM Forum based on the updated, latest incarnation of the idea? We can send a proposal now (deadline is June 9th I believe) and then work on the details in the subsequent weeks. I think we should be able to solidify the specifics of the hypervisor interface. When we presented this idea last year in the KVM forum, it was quite a bit fuzzy and we did not explore the IGVM angle at depth.
> So in my opinion, it will be a much better talk this time particularly with everyone (all major hyperscalers) showing interest on this.



Amazon Web Services Development Center Germany GmbH
Tamara-Danz-Str. 13
10243 Berlin
Geschaeftsfuehrung: Christian Schlaeger, Jonathan Weiss
Eingetragen am Amtsgericht Charlottenburg unter HRB 257764 B
Sitz: Berlin
Ust-ID: DE 365 538 597

---

## [5] Ani Sinha — 2025-05-19

> On 16 May 2025, at 2:55 PM, Alexander Graf <graf@amazon.com> wrote:
> 

Hmm ok I think it will be hard to get anything merged before the deadline on June 9th. 

> 
> Alex

---

## [6] Alexander Graf — 2025-05-19

On 19.05.25 10:37, Ani Sinha wrote:
>> On 16 May 2025, at 2:55 PM, Alexander Graf <graf@amazon.com> wrote:
>>


It doesn't have to be merged on the 9th, but it should have a realistic 
avenue to be merged by September 4th :).


Alex




Amazon Web Services Development Center Germany GmbH
Tamara-Danz-Str. 13
10243 Berlin
Geschaeftsfuehrung: Christian Schlaeger, Jonathan Weiss
Eingetragen am Amtsgericht Charlottenburg unter HRB 257764 B
Sitz: Berlin
Ust-ID: DE 365 538 597

---

## [7] Ani Sinha — 2025-05-20

> On 19 May 2025, at 4:55 PM, Alexander Graf <graf@amazon.com> wrote:
> 

One blocker in this path is that IGVM support has not yet been merged into QEMU. I know Roy (now at MSFT) is working on it and I pinged him today in the mailing list.

---

## [8] Dionna Amalie Glaze — 2025-06-23

Hey all, I've been looking into the least friction-y way to make an
IGVM readable from disk without having to add a complex device driver
to the VMM.
If the FUKI application chooses to read the firmware from disk instead
of having the binary embedded, then we can insist that there exists a
GPT partition on the same device as the ESP with IGVM partition type
(let's say GUID C647E858-C402-4D1E-9497-95FF0A4B4465) that's the
simplest filesystem format ever: "1FILE FS", 4 bytes of file size in
little endian, followed by a contiguous representation of the IGVM
file. If you want to change your firmware, create a new partition with
this type and delete the old one. It's a simple enough file system to
propose a DXE driver to OVMF for the FUKI application to use existing
EFI protocols to read the file.

There's the matter of reading the GPT sector and finding the IGVM
partition, then reading the file in the single file filesystem, all
using some method of reading the block device that has mounted the
disk image already that the VMM would have to mess with. The block
device access depends on VMM architecture that I couldn't really
comment on other than folks could probably make it work for Google's
VMM. It'd need to do some funky continuation passing style for the I/O
threads to string together the block read requests, but it shouldn't
be too terrible.






On Tue, May 20, 2025 at 7:41 AM Ani Sinha <anisinha@redhat.com> wrote:
>
>


--
-Dionna Glaze, PhD, CISSP, CCSP (she/her)

---

## [9] Gerd Hoffmann — 2025-06-24

On Mon, Jun 23, 2025 at 10:08:16AM -0700, Dionna Amalie Glaze wrote:
> Hey all, I've been looking into the least friction-y way to make an
> IGVM readable from disk without having to add a complex device driver

Well.  That assumes that the VMM host can access guest storage.  Which
is according to alex not possible with aws nitro, and also for qemu this
is not guaranteed (although it is possible in many typical
configurations).

So, with that in mind the envisioned workflow for the FUKI boot is this:

 (1) first stage boots, firmware loads guest application from disk
     and runs it.  The application is expected to typically be a linux
     UKI, with either the firmware embedded, or loaded via systemd-stub
     add-on.

 (2) The systemd stub (the code which runs first when loading an UKI)
     will figure whenever a firmware update is needed.  If so it will
     invoke the firmware update process, otherwise launch the linux
     kernel.

 (3) The firmware update will pass both the firmware (as igvm file) and
     the UKI (efi binary) to the hypervisor for the second stage launch.
     For passing the UKI there are multiple options:
       (a) original design idea is to simply pass on all memory pages in
           'shared' state from stage1 to stage2, so the guest can use
           that to pass the UKI to the next stage.
       (b) alternatively the firmware igvm could be modified on-the-fly
           to carry both firmware and UKI.  See also
           https://github.com/microsoft/igvm/issues/91

 (4) hypervisor re-creates the sev-snp context and launches the igvm
     file passed from the guest.  The second stage firmware can go
     launch the UKI passed from stage1 directly, there is no need to
     go though storage/network setup again, which should speed up the
     second stage launch.  IIRC that detail was not mentioned/discussed
     in the call last month.

The vmfwupdate device has been designed to solve the "pass firmware and
UKI from stage1 to stage2" problem.

There are a number of options we can consider moving forward:

 (a) Instead of making the vmfwupdate device the common API we could
     create an EFI protocol instead.  So the vmfwupdate device would
     effectively become an implementation detail for (probably) qemu and
     aws, and GCE + Azure can choose to do something else instead, for
     example store the igvm on some standard location on guest disk
     where their hypervisor can find it.

 (b) Caching.  Allow the hypervisor to cache the initial state for the
     second launch, so going through the whole process is needed only
     after firmware and/or kernel updates.  With that added the guest
     obviously needs some way to invalidate the cache.

take care,
  Gerd

---

## [10] Dionna Amalie Glaze — 2025-06-24

On Tue, Jun 24, 2025 at 5:18 AM Gerd Hoffmann <kraxel@redhat.com> wrote:
>
> Well.  That assumes that the VMM host can access guest storage.  Which

I understand. It's not out of the box particularly easy to get as a
VMM feature in Vanadium either, but most things are possible with
software changes. You just have to be willing to support that use
case.

>
> So, with that in mind the envisioned workflow for the FUKI boot is this:

I would love this to be standardized so that the IGVM specification
can fall under the UEFI forum's governance.
Jon said the CCC was inappropriate as an owner, so what about the UEFI forum?
This would match the FAT32 spec snapshotting that the spec did for the ESP FS.

The upgradable format would lag behind the launchable format due to
the specification and publication cycle
of the forum, but it would be a good place for better discussion of
cross-platform issues.

It allows Intel to better shift their TDVF launch instructions out of
GUID table parsing and into a shared
format. It would protect the IP risk of depending on a Microsoft-owned
format—as well-intentioned the inventors
are as professionals, there's always the risk of higher forces
asserting ownership rights for unpopular changes.
Google approved collaboration on the IGVM repository not without hesitation.

>      So the vmfwupdate device would
>      effectively become an implementation detail for (probably) qemu and

If the protocol implementation writes to the volume as part of its
implementation, the location doesn't need to be standard, right?
Certainly I would prefer the location be standard so that any update
to the location outside of the EFI protocol has the same behavior on
all platforms,
but that won't be the same behavior for platforms that don't
communicate with the disk at all. Hmm

>
>  (b) Caching.  Allow the hypervisor to cache the initial state for the

I imagine you mean device state and just swap out the VM context. I
thought that was already the plan. The main issue is the VM context
launch cost itself, which is multiple seconds, which is not great for
VM creation performance.

>
> take care,
--
-Dionna Glaze, PhD, CISSP, CCSP (she/her)

---

## [11] Ani Sinha — 2025-06-25

On Mon, Jun 23, 2025 at 10:38 PM Dionna Amalie Glaze
<dionnaglaze@google.com> wrote:
>
> Hey all, I've been looking into the least friction-y way to make an

Ok so let me get this clear. We are talking about not embedding the
IGVM in a UKI but putting it directly on the disk right?
If this is true, I am not sure what additional problem it solves since
for azure, the issue was that they did not want to have a two stage
boot process. So they wanted to go directly to stage 2 with the IGVM
extracted from the guest disk. If I understand correctly.

 then we can insist that there exists a
> GPT partition on the same device as the ESP with IGVM partition type
> (let's say GUID C647E858-C402-4D1E-9497-95FF0A4B4465) that's the

---

## [12] Gerd Hoffmann — 2025-06-25

Hi,

> >      So the vmfwupdate device would
> >      effectively become an implementation detail for (probably) qemu and

Correct.

> Certainly I would prefer the location be standard so that any update
> to the location outside of the EFI protocol has the same behavior on

Yes, I agree it makes sense to standardize the location too.

I think this is something for google and azure to sort out, you know
your hypervisor implementations best and know what is possible and/or
desirable in terms of the VMM accessing guest storage.

The GPT partition idea looks sensible to me, except that I would make
the size field 64bit.

> >  (b) Caching.  Allow the hypervisor to cache the initial state for the
> >      second launch, so going through the whole process is needed only

I mean the igvm the first stage has passed to the hypervisor.

The hypervisor can choose to cache and reuse that igvm to skip the first
stage as long as the igvm is considered valid.

> I thought that was already the plan.

Well, when storing the second stage igvm on the guest disk the caching
comes (almost) for free, so yes, that is a natural consideration.

For the vmfwupdate case caching is a bit more complicated.

take care,
  Gerd

---
