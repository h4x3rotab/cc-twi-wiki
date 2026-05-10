---
title: '[PATCH 0/2] Allow individual features to be locked down'
date: 2025-05-12
last_reply: 2025-05-13
message_count: 4
participants: ['Dan Williams', 'Paul Moore', 'Nikolay Borisov']
---

## [1] Dan Williams — 2025-05-12

Dan Williams wrote:
> Paul Moore wrote:
> > On Fri, Mar 21, 2025 at 6:24 AM Nikolay Borisov <nik.borisov@suse.com> wrote:

Just wanted to circle back here and repair the damage I caused to the
momentum of this "lockdown feature bitmap" proposal. It turns out that
devmem maintainers are not looking to add yet more arch-specific hacks
[1].

    "Restricting /dev/mem further is a good idea, but it would be nice
     if that could be done without adding yet another special case."

security_locked_down() is already plumbed into all the places that
confidential VMs may need to manage userspace access to confidential /
private memory.

I considered registering a new "coco-LSM" to hook
security_locked_down(), but that immediately raises the next question of
how does userspace discover what is currently locked_down. So just teach
the native lockdown LSM how to be more fine-grained rather than
complicate the situation with a new LSM.

[1]: http://lore.kernel.org/0bdb1876-0cb3-4632-910b-2dc191902e3e@app.fastmail.com

---

## [2] Paul Moore — 2025-05-12

On Mon, May 12, 2025 at 5:41 PM Dan Williams <dan.j.williams@intel.com> wrote:
> Dan Williams wrote:
> > Paul Moore wrote:

Historically Linus has bristled at LSMs with alternative
security_locked_down() implementations/security-models, therefore I'd
probably give a nod to refining the existing Lockdown approach over a
new LSM.

Related update, there are new Lockdown maintainers coming, there is
just an issue of sorting out some email addresses first.  Hopefully
we'll see something on-list soon.

---

## [3] Nikolay Borisov — 2025-05-13

On 5/13/25 01:01, Paul Moore wrote:
> On Mon, May 12, 2025 at 5:41 PM Dan Williams <dan.j.williams@intel.com> wrote:
>> Dan Williams wrote:


So I guess the most sensible way forward will be to resend these 2 
patches after the new maintainer has been officially announced?

---

## [4] Paul Moore — 2025-05-13

On Tue, May 13, 2025 at 7:10 AM Nikolay Borisov <nik.borisov@suse.com> wrote:
> On 5/13/25 01:01, Paul Moore wrote:
> > On Mon, May 12, 2025 at 5:41 PM Dan Williams <dan.j.williams@intel.com> wrote:

Possibly, or at least bump the thread to get it some fresh attention.

---
