---
title: '[GIT PULL] PCIe Link Encryption fixes for 6.19'
date: 2026-02-04
last_reply: 2026-02-04
message_count: 2
participants: ['dan.j.williams@intel.com', 'pr-tracker-bot@kernel.org']
---

## [1] dan.j.williams@intel.com — 2026-02-04

Hi Linus, please pull from:

  git://git.kernel.org/pub/scm/linux/kernel/git/devsec/tsm tags/tsm-fixes-for-6.19

...to receive a small collection of fixes for 6.19. The largest change
is reverting part of an ABI that never shipped in a released kernel
(Documentation/ABI/testing/sysfs-class-tsm). The fix / replacement for
that is too large to squeeze in at this late date. The rest is a
collection of small fixups summarized in the tag message.

It has appeared in linux-next with no reports at last check.

Given the tsm.git tree merged the PCIe Link Encryption support for the
AMD "ccp" driver, Alexey asked that the fixes also go through the
tsm.git with an ack from Tom. Bjorn acked taking ide.c fixes through
tsm.git as well.

---

The following changes since commit 24d479d26b25bce5faea3ddd9fa8f3a6c3129ea7:

  Linux 6.19-rc6 (2026-01-18 15:42:45 -0800)

are available in the Git repository at:

  git://git.kernel.org/pub/scm/linux/kernel/git/devsec/tsm tags/tsm-fixes-for-6.19

for you to fetch changes up to c2012263047689e495e81c96d7d5b0586299578d:

  crypto/ccp: Allow multiple streams on the same root bridge (2026-01-30 14:27:53 -0800)

----------------------------------------------------------------
tsm fixes for 6.19

- Fix multiple streams per host bridge for SEV-TIO

- Drop the TSM ABI for reporting IDE streams (to be replaced)

- Fix virtual function enumeration

- Fix reserved stream ID initialization

- Fix unused variable compiler warning

----------------------------------------------------------------
Alexey Kardashevskiy (2):
      crypto/ccp: Use PCI bridge defaults for IDE
      crypto/ccp: Allow multiple streams on the same root bridge

Dan Williams (1):
      Revert "PCI/TSM: Report active IDE streams"

Li Ming (2):
      PCI/IDE: Fix off by one error calculating VF RID range
      PCI/IDE: Fix reading a wrong reg for unused sel stream initialization

Thomas Weißschuh (1):
      coco/tsm: Remove unused variable tsm_rwsem

 Documentation/ABI/testing/sysfs-class-tsm | 10 ----------
 drivers/crypto/ccp/sev-dev-tsm.c          | 15 +--------------
 drivers/pci/ide.c                         | 10 +++-------
 drivers/virt/coco/tsm-core.c              | 30 ------------------------------
 include/linux/pci-ide.h                   |  4 +---
 include/linux/tsm.h                       |  3 ---
 6 files changed, 5 insertions(+), 67 deletions(-)

---

## [2] pr-tracker-bot@kernel.org — 2026-02-04
*Subject: Re: [GIT PULL] PCIe Link Encryption fixes for 6.19*

The pull request you sent on Wed, 4 Feb 2026 13:42:18 -0800:

> git://git.kernel.org/pub/scm/linux/kernel/git/devsec/tsm tags/tsm-fixes-for-6.19

has been merged into torvalds/linux.git:
https://git.kernel.org/torvalds/c/f14faaf3a1fb3b9e4cf2e56269711fb85fba9458

Thank you!

---
