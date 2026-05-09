---
title: '[GIT PULL] Confidential Computing: Attestation Updates for 7.0'
date: 2026-02-14
last_reply: 2026-02-15
message_count: 2
participants: ['dan.j.williams@intel.com', 'pr-tracker-bot@kernel.org']
---

## [1] dan.j.williams@intel.com — 2026-02-14

Hi Linus, please pull from:

  git://git.kernel.org/pub/scm/linux/kernel/git/devsec/tsm tags/tsm-for-7.0

...to receive a couple updates to the maximum buffer sizes supported for
the configfs-tsm-reports interface. Recall this interface is a common
transport that conveys the varied architecture specific launch
attestation reports for confidential VMs. 

They have appeared in linux-next with no known reports.

---

The following changes since commit 18f7fcd5e69a04df57b563360b88be72471d6b62:

  Linux 6.19-rc8 (2026-02-01 14:01:13 -0800)

are available in the Git repository at:

  git://git.kernel.org/pub/scm/linux/kernel/git/devsec/tsm tags/tsm-for-7.0

for you to fetch changes up to 43185067c6fd55b548ecb648a69d9569fcf622b5:

  configfs-tsm-report: tdx_guest: Increase Quote buffer size to 128KB (2026-02-10 18:24:09 -0800)

----------------------------------------------------------------
tsm for 7.0

- Prepare the configfs-tsm-reports interface for passing larger
  attestation evidence blobs for "Device Identifier Composition Engine"
  (DICE) and Post Quantum Crypto (PQC).

- Update the tdx-guest driver for DICE evidence (larger certificate
  chains and the CBOR Web Token schema).

----------------------------------------------------------------
Kuppuswamy Sathyanarayanan (3):
      configfs-tsm-report: Document size limits for outblob attributes
      configfs-tsm-report: Increase TSM_REPORT_OUTBLOB_MAX to 16MB
      configfs-tsm-report: tdx_guest: Increase Quote buffer size to 128KB

 Documentation/ABI/testing/configfs-tsm-report | 16 ++++++++++++++++
 drivers/virt/coco/tdx-guest/tdx-guest.c       |  4 +++-
 include/linux/tsm.h                           |  2 +-
 3 files changed, 20 insertions(+), 2 deletions(-)

---

## [2] pr-tracker-bot@kernel.org — 2026-02-15
*Subject: Re: [GIT PULL] Confidential Computing: Attestation Updates for 7.0*

The pull request you sent on Sat, 14 Feb 2026 18:07:34 -0800:

> git://git.kernel.org/pub/scm/linux/kernel/git/devsec/tsm tags/tsm-for-7.0

has been merged into torvalds/linux.git:
https://git.kernel.org/torvalds/c/c4f414becb6ac9c71ea80dd8b28478d357c62bb7

Thank you!

---
