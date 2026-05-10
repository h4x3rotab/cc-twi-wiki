---
title: '[GIT PULL] Trusted Security Manager (PCIe TSM) Update for 7.1'
date: 2026-04-26
last_reply: 2026-04-26
message_count: 3
participants: ['Dan Williams', 'Linus Torvalds', 'pr-tracker-bot@kernel.org']
---

## [1] Dan Williams — 2026-04-26

Hi Linus, please pull from:

  git://git.kernel.org/pub/scm/linux/kernel/git/devsec/tsm tags/tsm-for-7.1

...to receive a small update for the TSM core. It is arguably a fix and
coming in late as I have been offline the past few weeks.

Recall that you asked for searchable help with the TLA disease last time
[1]. "PCIe TSM" turns up useful results.

The other motivation for sending this one-patch pull request is to test
that you have my key with updated email.

This has been in linux-next for a while with no reported issues.

[1]: http://lore.kernel.org/CAHk-=whjvmBiZ=oMnR-R9rqzEPnGCaU7dNLkY1RHXwjRCAR5YQ@mail.gmail.com

--

The following changes since commit f338e77383789c0cae23ca3d48adcc5e9e137e3c:

  Linux 7.0-rc4 (2026-03-15 13:52:05 -0700)

are available in the Git repository at:

  git://git.kernel.org/pub/scm/linux/kernel/git/devsec/tsm tags/tsm-for-7.1

for you to fetch changes up to 3177779ae17db4c66c851f799505fb95c7530c03:

  virt: coco: change tsm_class to a const struct (2026-04-02 15:45:18 -0700)

----------------------------------------------------------------
tsm for 7.1

- Drop class_create() for the "tsm" class

----------------------------------------------------------------
Jori Koolstra (1):
      virt: coco: change tsm_class to a const struct

 drivers/virt/coco/tsm-core.c | 19 +++++++++----------
 1 file changed, 9 insertions(+), 10 deletions(-)

---

## [2] Linus Torvalds — 2026-04-26
*Subject: Re: [GIT PULL] Trusted Security Manager (PCIe TSM) Update for 7.1*

On Sun, 26 Apr 2026 at 09:11, Dan Williams <djbw@kernel.org> wrote:
>
> The other motivation for sending this one-patch pull request is to test

I didn't, but honestly, I don't match key issuer ID's or the email
address the pull is sent from anyway.

So I just want the signature to be valid, and from a key I know.

And it all verified with the old key, just with a

  issuer "djbw@kernel.org" does not match any User ID

warning.

I wouldn't have cared - or noticed - had you not mentioned it.

But I did update the key so the issuer warning is gone too.

         Linus

---

## [3] pr-tracker-bot@kernel.org — 2026-04-26
*Subject: Re: [GIT PULL] Trusted Security Manager (PCIe TSM) Update for 7.1*

The pull request you sent on Sun, 26 Apr 2026 09:11:12 -0700:

> git://git.kernel.org/pub/scm/linux/kernel/git/devsec/tsm tags/tsm-for-7.1

has been merged into torvalds/linux.git:
https://git.kernel.org/torvalds/c/20b64cf8705a0f6268bb9a320eb6b4c425f3ec6c

Thank you!

---
