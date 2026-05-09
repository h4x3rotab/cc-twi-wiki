---
title: '[GIT PULL] Trusted Security Manager (TSM) updates for 6.16'
date: 2025-05-29
last_reply: 2025-05-29
message_count: 5
participants: ['dan.j.williams@intel.com', 'Linus Torvalds', 'pr-tracker-bot@kernel.org']
---

## [1] dan.j.williams@intel.com — 2025-05-29

Hi Linus, please pull from:

  git://git.kernel.org/pub/scm/linux/kernel/git/devsec/tsm tags/tsm-for-6.16

...to receive shared infrastructure updates for confidential computing.
The last time you pulled from tsm.git was back in v6.7 for the
configfs-tsm-report mechanism (5e2cb28dd7e1 ("Merge tag
'tsm-for-6.7'...")). The tree has now moved to a shared devsec/tsm.git
repo. Going forward additional shared infrastructure is anticipated for
the assignment of PCI devices to confidential guests, "PCI Device
Security (devsec)".

This has all appeared in linux-next for a couple weeks and identified
some issues in my merge commit over the rename. All resolved now, with
no new reports to my knowledge.

---

The following changes since commit 92a09c47464d040866cf2b4cd052bc60555185fb:

  Linux 6.15-rc5 (2025-05-04 13:55:04 -0700)

are available in the Git repository at:

  git://git.kernel.org/pub/scm/linux/kernel/git/devsec/tsm tags/tsm-for-6.16

for you to fetch changes up to 9d948b8804096d940022b1a3c483a5beb8b46574:

  Merge branch 'for-6.16/tsm-mr' into tsm-next (2025-05-13 11:28:25 -0700)

----------------------------------------------------------------
tsm for 6.16

- Add a general sysfs scheme for publishing "Measurement" values
  provided by the architecture's TEE Security Manager. Use it to publish
  TDX "Runtime Measurement Registers" ("RTMRs") that either maintain a
  hash of stored values (similar to a TPM PCR) or provide statically
  provisioned data.  These measurements are validated by a relying party.

- Reorganize the drivers/virt/coco/ directory for "host" and "guest"
  shared infrastructure.

- Fix a configfs-tsm-report unregister bug

- With CONFIG_TSM_MEASUREMENTS joining CONFIG_TSM_REPORTS and in
  anticipation of more shared "TSM" infrastructure arriving, rename the
  maintainer entry to "TRUSTED SECURITY MODULE (TSM) INFRASTRUCTURE".

----------------------------------------------------------------
Cedric Xing (9):
      tsm-mr: Add TVM Measurement Register support
      tsm-mr: Add tsm-mr sample code
      x86/tdx: Add tdx_mcall_extend_rtmr() interface
      x86/tdx: tdx_mcall_get_report0: Return -EBUSY on TDCALL_OPERAND_BUSY error
      virt: tdx-guest: Expose TDX MRs as sysfs attributes
      virt: tdx-guest: Refactor and streamline TDREPORT generation
      virt: tdx-guest: Transition to scoped_cond_guard for mutex operations
      sample/tsm-mr: Fix missing static for sample_report
      tsm-mr: Fix init breakage after bin_attrs constification by scoping non-const pointers to init phase

Dan Williams (6):
      configfs-tsm: Namespace TSM report symbols
      coco/guest: Move shared guest CC infrastructure to drivers/virt/coco/guest/
      configfs-tsm-report: Fix NULL dereference of tsm_ops
      Merge branch 'for-6.16/tsm' into tsm-next
      Merge branch 'for-6.16/tsm-mr' into tsm-next
      Merge branch 'for-6.16/tsm-mr' into tsm-next

 .../testing/{configfs-tsm => configfs-tsm-report}  |   0
 .../testing/sysfs-devices-virtual-misc-tdx_guest   |  63 +++++
 Documentation/driver-api/coco/index.rst            |  12 +
 .../driver-api/coco/measurement-registers.rst      |  12 +
 Documentation/driver-api/index.rst                 |   1 +
 MAINTAINERS                                        |  11 +-
 arch/x86/coco/tdx/tdx.c                            |  50 +++-
 arch/x86/include/asm/shared/tdx.h                  |   1 +
 arch/x86/include/asm/tdx.h                         |   2 +
 drivers/virt/coco/Kconfig                          |   6 +-
 drivers/virt/coco/Makefile                         |   2 +-
 drivers/virt/coco/arm-cca-guest/arm-cca-guest.c    |   8 +-
 drivers/virt/coco/guest/Kconfig                    |  17 ++
 drivers/virt/coco/guest/Makefile                   |   4 +
 drivers/virt/coco/{tsm.c => guest/report.c}        |  63 +++--
 drivers/virt/coco/guest/tsm-mr.c                   | 251 ++++++++++++++++++++
 drivers/virt/coco/sev-guest/sev-guest.c            |  12 +-
 drivers/virt/coco/tdx-guest/Kconfig                |   1 +
 drivers/virt/coco/tdx-guest/tdx-guest.c            | 259 ++++++++++++++-------
 include/linux/tsm-mr.h                             |  89 +++++++
 include/linux/tsm.h                                |  22 +-
 include/trace/events/tsm_mr.h                      |  80 +++++++
 samples/Kconfig                                    |  11 +
 samples/Makefile                                   |   1 +
 samples/tsm-mr/Makefile                            |   2 +
 samples/tsm-mr/tsm_mr_sample.c                     | 131 +++++++++++
 26 files changed, 974 insertions(+), 137 deletions(-)
 rename Documentation/ABI/testing/{configfs-tsm => configfs-tsm-report} (100%)
 create mode 100644 Documentation/ABI/testing/sysfs-devices-virtual-misc-tdx_guest
 create mode 100644 Documentation/driver-api/coco/index.rst
 create mode 100644 Documentation/driver-api/coco/measurement-registers.rst
 create mode 100644 drivers/virt/coco/guest/Kconfig
 create mode 100644 drivers/virt/coco/guest/Makefile
 rename drivers/virt/coco/{tsm.c => guest/report.c} (89%)
 create mode 100644 drivers/virt/coco/guest/tsm-mr.c
 create mode 100644 include/linux/tsm-mr.h
 create mode 100644 include/trace/events/tsm_mr.h
 create mode 100644 samples/tsm-mr/Makefile
 create mode 100644 samples/tsm-mr/tsm_mr_sample.c

---

## [2] dan.j.williams@intel.com — 2025-05-29
*Subject: Re: [GIT PULL] Trusted Security Manager (TSM) updates for 6.16*

dan.j.williams@ wrote:
> Hi Linus, please pull from:
> 
[..]
> ----------------------------------------------------------------
> tsm for 6.16

Note that I meant to include tags that arrived after I cut the branch.
This work is:

Tested-by: Mikko Ylinen <mikko.ylinen@linux.intel.com>
https://lore.kernel.org/linux-coco/aCWoPWMjg9rX2qPl@himmelriiki/

---

## [3] Linus Torvalds — 2025-05-29
*Subject: Re: [GIT PULL] Trusted Security Manager (TSM) updates for 6.16*

On Thu, 29 May 2025 at 17:59, <dan.j.williams@intel.com> wrote:
>
> ...to receive shared infrastructure updates for confidential computing.

Do we have a sane name for this? The pull request calls it "TSM" and
writes it out as "trusted security manager", your intro calls it
"shared infrastructure updates for confidential computing", and the
MAINTAINER entry calls it "trusted security module" (note the
different word for the 'M').

Making things even worse, Intel also uses "TSM", but in Intel docs,
the "T" stands not for "Trusted", but for "TEE", which in turn is a
recursive TLA meaning "Trusted Execution Environment".

Yes, I've complained about odd TLA's before, but TSM really takes the
odd to a new level.

I've pulled this, and I've used "TSM" in the pull message, but I
really think this TLA disease needs to end.

Let's have a rule that TLA's are ok _only_ for things that

 (a) go back at least four decades

 (b) have a basically unambiguous meaning in the industry (let's
ignore IBM that made up their own naming)

 (c) when you google them, they give relevant results

So, for example, talking about a "TLB" entry is ok by all three rules,
and a TTY is similarly not a bad word.

"TSM" fulfills _none_ of these.

Please? I know you work for Intel and you probably signed some
paperwork saying that a certain percentage of words you use have to be
TLA's, but please ... We can do better.

              Linus

---

## [4] pr-tracker-bot@kernel.org — 2025-05-30
*Subject: Re: [GIT PULL] Trusted Security Manager (TSM) updates for 6.16*

The pull request you sent on Thu, 29 May 2025 17:59:14 -0700:

> git://git.kernel.org/pub/scm/linux/kernel/git/devsec/tsm tags/tsm-for-6.16

has been merged into torvalds/linux.git:
https://git.kernel.org/torvalds/c/ae5ec8adb8ec9c2aa916f853737c101faa87e5ba

Thank you!

---

## [5] Dan Williams — 2025-05-29
*Subject: Re: [GIT PULL] Trusted Security Manager (TSM) updates for 6.16*

Linus Torvalds wrote:
> On Thu, 29 May 2025 at 17:59, <dan.j.williams@intel.com> wrote:
> >

Intel TLA disease is real.

Also, it is funny, in a sad way, because some of these patches
originated in a series where I spend some paragraphs explaining the
absolute silliness of the acronym soup in this space [1], but then here
failed to respect that "TSM" continues to be close to useless as search
engines fail to find it.

I note that "TSM" is used in the new "security protocol" sections of the
PCIe specification. However, that specification being a members-only
accessible document does not help at all with the discoverability
problem.

Suffice to say "TSM" is the term the PCIe specifications ascribes to all
of the various architecture specific firmware/firmware-ish modules
(Intel TDX, AMD SEV, RISC-V COVE, ARM CCA...) that can touch the "secure
world" of the platform. I.e. setup confidential memory MMU or IOMMU
ptes, and talk the PCIe protocols to setup link encryption between host
bridges and Endpoints.

...but unless and until that becomes wider knowledge I agree that it
should be spelled out with references to where the heck it comes from
and quick reminder of what it is [2].

[1]: https://lore.kernel.org/all/173343739517.1074769.13134786548545925484.stgit@dwillia2-xfh.jf.intel.com/

[2]: PCIe r6.2 Section 11:
     "The TEE Security Manager (TSM) is a logical entity in a host that
      is in the Trusted Computing Base (TCB) for a Trusted Execution
      Environment Virtual Machine (TVM) and enforces security policies
      on the host."

---
