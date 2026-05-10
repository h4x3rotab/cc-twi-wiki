---
title: '[GIT PULL] PCIe Link Encryption and Device Authentication'
date: 2025-12-05
last_reply: 2025-12-08
message_count: 6
participants: ['dan.j.williams@intel.com', 'pr-tracker-bot@kernel.org', 'Linus Torvalds', 'Joerg Roedel', 'Alexey Kardashevskiy']
---

## [1] dan.j.williams@intel.com — 2025-12-05

Hi Linus, please pull from:

  git://git.kernel.org/pub/scm/linux/kernel/git/devsec/tsm tags/tsm-for-6.19

...to receive new PCI infrastructure and one architecture implementation
for PCIe link encryption establishment via platform firmware services.

This work is the result of multiple vendors coming to consensus on some
core infrastructure (thanks Alexey, Yilun, and Aneesh!), and three
vendor implementations, although only one is included in this pull. The
PCI core changes have an ack from Bjorn, the crypto/ccp/ changes have an
ack from Tom, and the iommu/amd/ changes have an ack from Joerg. It has
all appeared in linux-next with a small conflict reported by Stephen [1]
(I agree with his resolution), and some late build fixes for odd configs
reported by the 0day robot. A recent small fix from Dan Carpenter [2], I
expect Tom to pick up for post-rc1.

[1]: http://lore.kernel.org/20251201125039.36b9f37d@canb.auug.org.au
[2]: http://lore.kernel.org/aTLEVmFVGWn-Czkc@stanley.mountain

PCIe link encryption is made possible by the soup of acronyms mentioned
in the shortlog below. Link Integrity and Data Encryption (IDE) is a
protocol for installing keys in the transmitter and receiver at each end
of a link. That protocol is transported over Data Object Exchange (DOE)
mailboxes using PCI configuration requests.

The aspect that makes this a "platform firmware service" is that the key
provisioning and protocol is coordinated through a Trusted Execution
Envrionment (TEE) Security Manager (TSM). That is either firmware
running in a coprocessor (AMD SEV-TIO), or quasi-hypervisor software
(Intel TDX Connect / ARM CCA) running in a protected CPU mode.

Now, the only reason to ask a TSM to run this protocol and install the
keys rather than have a Linux driver do the same is so that later, a
confidential VM can ask the TSM directly "can you certify this device?".
That precludes host Linux from provisioning its own keys, because host
Linux is outside the trust domain for the VM. It also turns out that all
architectures, save for one, do not publish a mechanism for an OS to
establish keys in the root port. So "TSM-established link encryption" is
the only cross-architecture path for this capability for the foreseeable
future.

Acceptance of this pull request unblocks the other arch implementations
to follow in v6.20/v7.0, once they clear some other dependencies, and it
unblocks the next phase of work to implement the end-to-end flow of
confidential device assignment. The PCIe specification calls this
end-to-end flow Trusted Execution Environment (TEE) Device Interface
Security Protocol (TDISP).

In the meantime, Linux gets a link encryption facility which has
practical benefits along the same lines as memory encryption. It
authenticates devices via certificates and may protect against
interposer attacks trying to capture clear-text PCIe traffic.

The ongoing work is tracked in the tsm.git#staging branch [2]. A rough
map of next steps is maintained in this "Maturity Map" document [3].

[2]: https://git.kernel.org/pub/scm/linux/kernel/git/devsec/tsm.git/log/?h=staging
[3]: https://git.kernel.org/pub/scm/linux/kernel/git/devsec/tsm.git/tree/Documentation/driver-api/pci/tsm.rst?h=staging

---

The following changes since commit 6146a0f1dfae5d37442a9ddcba012add260bceb0:

  Linux 6.18-rc4 (2025-11-02 11:28:02 -0800)

are available in the Git repository at:

  git://git.kernel.org/pub/scm/linux/kernel/git/devsec/tsm tags/tsm-for-6.19

for you to fetch changes up to 7dfbe9a6751973c17138ddc0d33deff5f5f35b94:

  crypto/ccp: Fix CONFIG_PCI=n build (2025-12-04 18:14:08 -0800)

----------------------------------------------------------------
tsm for 6.19

- Introduce the PCI/TSM core for the coordination of device
  authentication, link encryption and establishment (IDE), and later
  management of the device security operational states (TDISP). Notify
  the new TSM core layer of PCI device arrival and departure.

- Add a low level TSM driver for the link encryption establishment
  capabilities of the AMD SEV-TIO architecture.

- Add a library of helpers TSM drivers to use for IDE establishment and
  the DOE transport.

- Add skeleton support for 'bind' and 'guest_request' operations in
  support of TDISP.

----------------------------------------------------------------
Alexey Kardashevskiy (4):
      ccp: Make snp_reclaim_pages and __sev_do_cmd_locked public
      psp-sev: Assign numbers to all status codes and add new
      iommu/amd: Report SEV-TIO support
      crypto/ccp: Implement SEV-TIO PCIe IDE (phase1)

Dan Williams (17):
      coco/tsm: Introduce a core device for TEE Security Managers
      PCI/IDE: Enumerate Selective Stream IDE capabilities
      PCI: Introduce pci_walk_bus_reverse(), for_each_pci_dev_reverse()
      PCI/TSM: Establish Secure Sessions and Link Encryption
      PCI: Add PCIe Device 3 Extended Capability enumeration
      PCI: Establish document for PCI host bridge sysfs attributes
      PCI/IDE: Add IDE establishment helpers
      PCI/IDE: Report available IDE streams
      PCI/TSM: Report active IDE streams
      drivers/virt: Drop VIRT_DRIVERS build dependency
      PCI/TSM: Drop stub for pci_tsm_doe_transfer()
      resource: Introduce resource_assigned() for discerning active resources
      PCI/IDE: Initialize an ID for all IDE streams
      PCI/TSM: Add pci_tsm_bind() helper for instantiating TDIs
      PCI/TSM: Add pci_tsm_guest_req() for managing TDIs
      PCI/TSM: Add 'dsm' and 'bound' attributes for dependent functions
      crypto/ccp: Fix CONFIG_PCI=n build

Nathan Chancellor (1):
      virt: Fix Kconfig warning when selecting TSM without VIRT_DRIVERS

Xu Yilun (1):
      PCI/IDE: Add Address Association Register setup for downstream MMIO

 Documentation/ABI/testing/sysfs-bus-pci            |  81 ++
 Documentation/ABI/testing/sysfs-class-tsm          |  19 +
 .../ABI/testing/sysfs-devices-pci-host-bridge      |  45 ++
 Documentation/driver-api/pci/index.rst             |   1 +
 Documentation/driver-api/pci/tsm.rst               |  21 +
 MAINTAINERS                                        |   7 +-
 drivers/Makefile                                   |   2 +-
 drivers/base/bus.c                                 |  38 +
 drivers/crypto/ccp/Kconfig                         |   1 +
 drivers/crypto/ccp/Makefile                        |   4 +
 drivers/crypto/ccp/sev-dev-tio.c                   | 864 ++++++++++++++++++++
 drivers/crypto/ccp/sev-dev-tio.h                   | 123 +++
 drivers/crypto/ccp/sev-dev-tsm.c                   | 405 ++++++++++
 drivers/crypto/ccp/sev-dev.c                       |  66 +-
 drivers/crypto/ccp/sev-dev.h                       |  11 +
 drivers/iommu/amd/amd_iommu_types.h                |   1 +
 drivers/iommu/amd/init.c                           |   9 +
 drivers/pci/Kconfig                                |  18 +
 drivers/pci/Makefile                               |   2 +
 drivers/pci/bus.c                                  |  39 +
 drivers/pci/doe.c                                  |   2 -
 drivers/pci/ide.c                                  | 815 +++++++++++++++++++
 drivers/pci/pci-sysfs.c                            |   4 +
 drivers/pci/pci.h                                  |  21 +
 drivers/pci/probe.c                                |  31 +-
 drivers/pci/remove.c                               |   7 +
 drivers/pci/search.c                               |  62 +-
 drivers/pci/tsm.c                                  | 900 +++++++++++++++++++++
 drivers/virt/Kconfig                               |   4 +-
 drivers/virt/coco/Kconfig                          |   5 +
 drivers/virt/coco/Makefile                         |   1 +
 drivers/virt/coco/tsm-core.c                       | 163 ++++
 include/linux/amd-iommu.h                          |   2 +
 include/linux/device/bus.h                         |   3 +
 include/linux/ioport.h                             |   9 +
 include/linux/pci-doe.h                            |   4 +
 include/linux/pci-ide.h                            | 119 +++
 include/linux/pci-tsm.h                            | 243 ++++++
 include/linux/pci.h                                |  34 +
 include/linux/psp-sev.h                            |  17 +-
 include/linux/tsm.h                                |  17 +
 include/uapi/linux/pci_regs.h                      |  89 ++
 include/uapi/linux/psp-sev.h                       |  66 +-
 43 files changed, 4323 insertions(+), 52 deletions(-)
 create mode 100644 Documentation/ABI/testing/sysfs-class-tsm
 create mode 100644 Documentation/ABI/testing/sysfs-devices-pci-host-bridge
 create mode 100644 Documentation/driver-api/pci/tsm.rst
 create mode 100644 drivers/crypto/ccp/sev-dev-tio.c
 create mode 100644 drivers/crypto/ccp/sev-dev-tio.h
 create mode 100644 drivers/crypto/ccp/sev-dev-tsm.c
 create mode 100644 drivers/pci/ide.c
 create mode 100644 drivers/pci/tsm.c
 create mode 100644 drivers/virt/coco/tsm-core.c
 create mode 100644 include/linux/pci-ide.h
 create mode 100644 include/linux/pci-tsm.h

---

## [2] pr-tracker-bot@kernel.org — 2025-12-06
*Subject: Re: [GIT PULL] PCIe Link Encryption and Device Authentication*

The pull request you sent on Fri, 5 Dec 2025 19:08:17 -0800:

> git://git.kernel.org/pub/scm/linux/kernel/git/devsec/tsm tags/tsm-for-6.19

has been merged into torvalds/linux.git:
https://git.kernel.org/torvalds/c/249872f53d64441690927853e9d3af36394802d5

Thank you!

---

## [3] Linus Torvalds — 2025-12-06
*Subject: Re: [GIT PULL] PCIe Link Encryption and Device Authentication*

On Fri, 5 Dec 2025 at 19:08, <dan.j.williams@intel.com> wrote:
>
> Alexey Kardashevskiy (4):

Bah, I've merged this and pushed things out, because my allmodconfig
build was fine.

But more testing shows that this is broken.

The amd_iommu_sev_tio_supported() function is only defined for
CONFIG_KVM_AMD_SEV, but the <linux/amd-iommu.h> header put it inside
the CONFIG_AMD_IOMMU config option block.

So if you have AMD_IOMMU enabled without KVM_AMD_SEV you end up with a
broken build:

   ERROR: modpost: "amd_iommu_sev_tio_supported"
[drivers/crypto/ccp/ccp.ko] undefined!
   make[2]: *** [scripts/Makefile.modpost:147: Module.symvers] Error 1

I've pushed out a minimal fix that seems to work for me.

Please check - and be more careful. This is _not_ some kind of odd config.

              Linus

---

## [4] dan.j.williams@intel.com — 2025-12-06
*Subject: Re: [GIT PULL] PCIe Link Encryption and Device Authentication*

Linus Torvalds wrote:
[..]
> So if you have AMD_IOMMU enabled without KVM_AMD_SEV you end up with a
> broken build:

Ack, and ugh, sorry about that. Your:

    5e5ea7f61610 iommu/amd: fix SEV-TIO support reporting

Looks good to me, and agree that SEV disabled should be a reasonable
default for folks that have not enabled it previously.

---

## [5] Joerg Roedel — 2025-12-07
*Subject: Re: [GIT PULL] PCIe Link Encryption and Device Authentication*

Hi Linus,

On Sat, Dec 06, 2025 at 11:21:15AM -0800, Linus Torvalds wrote:
> I've pushed out a minimal fix that seems to work for me.
> 

The patch looks good, thanks for fixing this.

Regards,

	Joerg

---

## [6] Alexey Kardashevskiy — 2025-12-08
*Subject: Re: [GIT PULL] PCIe Link Encryption and Device Authentication*

On 7/12/25 06:21, Linus Torvalds wrote:
> On Fri, 5 Dec 2025 at 19:08, <dan.j.williams@intel.com> wrote:
>>


thanks for fixing this and apologies for the late bugs! buuut...

... how do you find these in the first place, just by random configs? It would miss a lot. Dependencies are so freaking complicated (with all these "select" and "depends on" which auto enable/disable options) so trying them all is going to take years :-/ Any advice? Thanks,


> 
>                Linus

---
