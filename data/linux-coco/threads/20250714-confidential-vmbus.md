---
title: 'Confidential VMBus'
date: 2025-07-14
last_reply: 2025-08-25
message_count: 50
participants: ['Roman Kisel', 'kernel test robot', 'Michael Kelley', 'Tianyu Lan', 'dan.j.williams@intel.com']
---

## [1] Roman Kisel — 2025-07-14

Hello all,

This is the 4th version of the patch series, and the full changelog
is at the end of the cover letter. At the top, I'd like to express my
gratitude and appreciation to Alok, Jon, Michael and Randy for
their tremendous help with this version. This is also my first time
adding to Documentation, and thanks to folks' kind advice, I actually
built the Documentation after fixing the issues they pointed out, and
that was a true joy reading the rendered book having added something
to the knowledge treasure trove that the Documentation is.

This version also includes a fix for an existing issue that Michael
noticed. Most of the issues found in the 3rd version were rather 
straightforward to fix. I added comments for the rest in the code
to justify the trade-offs. I fixed my spellchecker setup, and hoping
not to let spelling errors get through as much as before.

TLDR; is that these patches are for the Hyper-V guests, and the patches
allow to keep data flowing from physical devices into the guests encrypted
at the CPU level so that neither the root/host partition nor the hypervisor
can access the data being processed (they only "see" the encrypted/garbled
data). The changes are backward compatible with older systems, and their
full potential is realized on hardware that supports memory encryption.

These features also require running a paravisor, such as
OpenVMM (https://github.com/microsoft/openvmm) used in Azure. Another
implementation of the functionality available in this patch set is
available in the Hyper-V UEFI: https://github.com/microsoft/mu_msvm.

Once folks approve the changes, distro's might want to pick these up to
provide the users running workloads in Azure with these features.

A more detailed description of the patches follows.

The guests running on Hyper-V can be confidential where the memory and the
register content are encrypted, provided that the hardware supports that
(currently support AMD SEV-SNP and Intel TDX is implemented) and the guest
is capable of using these features. The confidential guests cannot be
introspected by the host nor the hypervisor without the guest sharing the
memory contents upon doing which the memory is decrypted.

In the confidential guests, neither the host nor the hypervisor need to be
trusted, and the guests processing sensitive data can take advantage of that.

Not trusting the host and the hypervisor (removing them from the Trusted
Computing Base aka TCB) necessitates that the method of communication
between the host and the guest be changed. Here is the data flow for a
conventional and the confidential VMBus connections (`C` stands for the
client or VSC, `S` for the server or VSP, the `DEVICE` is a physical one,
might be with multiple virtual functions):

1. Without the paravisor the devices are connected to the host, and the
host provides the device emulation or translation to the guest:

  +---- GUEST ----+       +----- DEVICE ----+        +----- HOST -----+
  |               |       |                 |        |                |
  |               |       |                 |        |                |
  |               |       |                 ==========                |
  |               |       |                 |        |                |
  |               |       |                 |        |                |
  |               |       |                 |        |                |
  +----- C -------+       +-----------------+        +------- S ------+
         ||                                                   ||
         ||                                                   ||
  +------||------------------ VMBus --------------------------||------+
  |                     Interrupts, MMIO                              |
  +-------------------------------------------------------------------+

2. With the paravisor, the devices are connected to the paravisor, and
the paravisor provides the device emulation or translation to the guest.
The guest doesn't communicate with the host directly, and the guest
communicates with the paravisor via the VMBus. The host is not trusted
in this model, and the paravisor is trusted:

  +---- GUEST --------------- VTL0 ------+               +-- DEVICE --+
  |                                      |               |            |
  | +- PARAVISOR --------- VTL2 -----+   |               |            |
  | |     +-- VMBus Relay ------+    ====+================            |
  | |     |   Interrupts, MMIO  |    |   |               |            |
  | |     +-------- S ----------+    |   |               +------------+
  | |               ||               |   |
  | +---------+     ||               |   |
  | |  Linux  |     ||    OpenHCL    |   |
  | |  kernel |     ||               |   |
  | +---- C --+-----||---------------+   |
  |       ||        ||                   |
  +-------++------- C -------------------+               +------------+
          ||                                             |    HOST    |
          ||                                             +---- S -----+
  +-------||----------------- VMBus ---------------------------||-----+
  |                     Interrupts, MMIO                              |
  +-------------------------------------------------------------------+

Note that in the second case the guest doesn't need to share the memory
with the host as it communicates only with the paravisor within their
partition boundary. That is precisely the raison d'etre and the value
proposition of this patch series: equip the confidential guest to use
private (encrypted) memory and rely on the paravisor when this is
available to be more secure.

An implementation of the VMBus relay that offers the Confidential VMBus
channels is available in the OpenVMM project as a part of the OpenHCL
paravisor. Please refer to

  * https://openvmm.dev/, and
  * https://github.com/microsoft/openvmm

for more information about the OpenHCL paravisor. A VMBus client
that can work with the Confidential VMBus is available in the
open-source Hyper-V UEFI: https://github.com/microsoft/mu_msvm.

I'd like to thank the following people for their help with this
patch series:

* Dexuan for help with validation and the fruitful discussions,
* Easwar for reviewing the refactoring of the page allocating and
  freeing in `hv.c`,
* John and Sven for the design,
* Mike for helping to avoid pitfalls when dealing with the GFP flags,
* Sven for blazing the trail and implementing the design in few
  codebases.

I made sure to validate the patch series on

    {TrustedLaunch(x86_64), OpenHCL} x
    {SNP(x86_64), TDX(x86_64), No hardware isolation, No paravisor} x
    {VMBus 5.0, VMBus 6.0} x
    {arm64, x86_64}.

[V4]
    - Rebased the patch series on top of the latest hyperv-next branch,
      applying changes as needed.

    - Fixed typos and clarifications all around the patch series.
    - Added clarifications in the patch 7 for `ms_hyperv.paravisor_present && !vmbus_is_confidential()`
      and using hypercalls vs SNP or TDX specific protocols.
      **Thank you, Alok!**

    - Trim the Documentation changes to 80 columns.
      **Thank you, Randy!**

    - Make sure adhere to the RST format, actually built the PDF docs
      and made sure the layout was correct.
    **Thank you, Jon!**

    - Better section order in Documentation.
    - Fixed the commit descriptions where suggested.
    - Moved EOI/EOM signaling for the confidential VMBus to the specialized function.
    - Removed the unused `cpu` parameters.
    - Clarified comments in the `hv_per_cpu_context` struct
    - Explicitly test for NULL and only call `iounmap()` if non-NULL instead of
      using `munmap()`.
    - Don't deallocate SynIC pages in the CPU online and offline paths.
    - Made sure the post page needs to be allocated for the future.
    - Added comments to describe trade-offs.
    **Thank you, Michael!**

[V3] https://lore.kernel.org/linux-hyperv/20250604004341.7194-1-romank@linux.microsoft.com/
    - The patch series is rebased on top of the latest hyperv-next branch.
    - Reworked the "wiring" diagram in the cover letter, added links to the
      OpenVMM project and the OpenHCL paravisor.

    - More precise wording in the comments and clearer code.
    **Thank you, Alok!**

    - Reworked the documentation patch.
    - Split the patchset into much more granular patches.
    - Various fixes and improvements throughout the patch series.
    **Thank you, Michael!**

[V2] https://lore.kernel.org/linux-hyperv/20250511230758.160674-1-romank@linux.microsoft.com/
    - The patch series is rebased on top of the latest hyperv-next branch.
  
    - Better wording in the commit messages and the Documentation.
    **Thank you, Alok and Wei!**

    - Removed the patches 5 and 6 concerning turning bounce buffering off from
      the previous version of the patch series as they were found to be
      architecturally unsound. The value proposition of the patch series is not
      diminished by this removal: these patches were an optimization and only for
      the storage (for the simplicity sake) but not for the network. These changes
      might be proposed in the future again after revolving the issues.
    ** Thanks you, Christoph, Dexuan, Dan, Michael, James, Robin! **

[V1] https://lore.kernel.org/linux-hyperv/20250409000835.285105-1-romank@linux.microsoft.com/

Roman Kisel (16):
  Documentation: hyperv: Confidential VMBus
  drivers: hv: VMBus protocol version 6.0
  arch: hyperv: Get/set SynIC synth.registers via paravisor
  arch/x86: mshyperv: Trap on access for some synthetic MSRs
  Drivers: hv: Rename fields for SynIC message and event pages
  Drivers: hv: Allocate the paravisor SynIC pages when required
  Drivers: hv: Post messages through the confidential VMBus if available
  Drivers: hv: remove stale comment
  Drivers: hv: Check message and event pages for non-NULL before
    iounmap()
  Drivers: hv: Rename the SynIC enable and disable routines
  Drivers: hv: Functions for setting up and tearing down the paravisor
    SynIC
  Drivers: hv: Allocate encrypted buffers when requested
  Drivers: hv: Free msginfo when the buffer fails to decrypt
  Drivers: hv: Support confidential VMBus channels
  Drivers: hv: Support establishing the confidential VMBus connection
  Drivers: hv: Set the default VMBus version to 6.0

 Documentation/virt/hyperv/coco.rst | 140 +++++++++-
 arch/x86/kernel/cpu/mshyperv.c     |  56 +++-
 drivers/hv/channel.c               |  81 ++++--
 drivers/hv/channel_mgmt.c          |  27 +-
 drivers/hv/connection.c            |   6 +-
 drivers/hv/hv.c                    | 431 +++++++++++++++++++++--------
 drivers/hv/hv_common.c             |  13 +
 drivers/hv/hyperv_vmbus.h          |  29 +-
 drivers/hv/mshv_root.h             |   2 +-
 drivers/hv/mshv_synic.c            |   6 +-
 drivers/hv/ring_buffer.c           |   5 +-
 drivers/hv/vmbus_drv.c             | 207 +++++++++-----
 include/asm-generic/mshyperv.h     |  76 ++---
 include/linux/hyperv.h             |  69 +++--
 14 files changed, 859 insertions(+), 289 deletions(-)


base-commit: d9016a249be5316ec2476f9947356711e70a16ec

---

## [2] Roman Kisel — 2025-07-14
*Subject: [PATCH hyperv-next v4 01/16] Documentation: hyperv: Confidential VMBus*

Define what the confidential VMBus is and describe what advantages
it offers on the capable hardware.

Signed-off-by: Roman Kisel <romank@linux.microsoft.com>
Reviewed-by: Alok Tiwari <alok.a.tiwari@oracle.com>
---
 Documentation/virt/hyperv/coco.rst | 140 ++++++++++++++++++++++++++++-
 1 file changed, 139 insertions(+), 1 deletion(-)

diff --git a/Documentation/virt/hyperv/coco.rst b/Documentation/virt/hyperv/coco.rst
index c15d6fe34b4e..e8515acfe306 100644
--- a/Documentation/virt/hyperv/coco.rst
+++ b/Documentation/virt/hyperv/coco.rst
@@ -178,7 +178,7 @@ These Hyper-V and VMBus memory pages are marked as decrypted:
 
 * VMBus monitor pages
 
-* Synthetic interrupt controller (synic) related pages (unless supplied by
+* Synthetic interrupt controller (SynIC) related pages (unless supplied by
   the paravisor)
 
 * Per-cpu hypercall input and output pages (unless running with a paravisor)
@@ -232,6 +232,144 @@ with arguments explicitly describing the access. See
 _hv_pcifront_read_config() and _hv_pcifront_write_config() and the
 "use_calls" flag indicating to use hypercalls.
 
+Confidential VMBus
+------------------
+The confidential VMBus enables the confidential guest not to interact with
+the untrusted host partition and the untrusted hypervisor. Instead, the guest
+relies on the trusted paravisor to communicate with the devices processing
+sensitive data. The hardware (SNP or TDX) encrypts the guest memory and the
+register state while measuring the paravisor image using the platform security
+processor to ensure trusted and confidential computing.
+
+Confidential VMBus provides a secure communication channel between the guest
+and the paravisor, ensuring that sensitive data is protected from hypervisor-
+level access through memory encryption and register state isolation.
+
+Confidential VMBus is an extension of Confidential Computing (CoCo) VMs
+(a.k.a. "Isolated" VMs in Hyper-V terminology). Without Confidential VMBus,
+guest VMBus device drivers (the "VSC"s in VMBus terminology) communicate
+with VMBus servers (the VSPs) running on the Hyper-V host. The
+communication must be through memory that has been decrypted so the
+host can access it. With Confidential VMBus, one or more of the VSPs reside
+in the trusted paravisor layer in the guest VM. Since the paravisor layer also
+operates in encrypted memory, the memory used for communication with
+such VSPs does not need to be decrypted and thereby exposed to the
+Hyper-V host. The paravisor is responsible for communicating securely
+with the Hyper-V host as necessary.
+
+The data won't ever leave the VM when a device is attached to VTL2, and the
+device supports encrypted memory. Therefore, neither the host partition nor the
+hypervisor can access the data being processed at all. The guest needs to
+establish a VMBus connection only with the paravisor for the channels that
+process sensitive data, and the paravisor abstracts the details of
+communicating with the specific devices away providing the guest with the
+well-established VSP (Virtual Service Provider) interface that has had support
+in the Hyper-V drivers for a decade.
+
+In the case the device does not support encrypted memory, the paravisor
+provides bounce-buffering, and although the data is not encrypted, the backing
+pages aren't mapped into the host partition through SLAT. While not impossible,
+it becomes much more difficult for the host partition to exfiltrate the data
+than it would be with a conventional VMBus connection where the host partition
+has direct access to the memory used for communication.
+
+Here is the data flow for a conventional VMBus connection (`C` stands for the
+client or VSC, `S` for the server or VSP, the `DEVICE` is a physical one, might
+be with multiple virtual functions)::
+
+  +---- GUEST ----+       +----- DEVICE ----+        +----- HOST -----+
+  |               |       |                 |        |                |
+  |               |       |                 |        |                |
+  |               |       |                 ==========                |
+  |               |       |                 |        |                |
+  |               |       |                 |        |                |
+  |               |       |                 |        |                |
+  +----- C -------+       +-----------------+        +------- S ------+
+         ||                                                   ||
+         ||                                                   ||
+  +------||------------------ VMBus --------------------------||------+
+  |                     Interrupts, MMIO                              |
+  +-------------------------------------------------------------------+
+
+and the Confidential VMBus connection::
+
+  +---- GUEST --------------- VTL0 ------+               +-- DEVICE --+
+  |                                      |               |            |
+  | +- PARAVISOR --------- VTL2 -----+   |               |            |
+  | |     +-- VMBus Relay ------+    ====+================            |
+  | |     |   Interrupts, MMIO  |    |   |               |            |
+  | |     +-------- S ----------+    |   |               +------------+
+  | |               ||               |   |
+  | +---------+     ||               |   |
+  | |  Linux  |     ||    OpenHCL    |   |
+  | |  kernel |     ||               |   |
+  | +---- C --+-----||---------------+   |
+  |       ||        ||                   |
+  +-------++------- C -------------------+               +------------+
+          ||                                             |    HOST    |
+          ||                                             +---- S -----+
+  +-------||----------------- VMBus ---------------------------||-----+
+  |                     Interrupts, MMIO                              |
+  +-------------------------------------------------------------------+
+
+An implementation of the VMBus relay that offers the Confidential VMBus
+channels is available in the OpenVMM project as a part of the OpenHCL
+paravisor. Please refer to
+
+  * https://openvmm.dev/, and
+  * https://github.com/microsoft/openvmm
+
+for more information about the OpenHCL paravisor.
+
+A guest that is running with a paravisor must determine at runtime if
+Confidential VMBus is supported by the current paravisor. It does so by
+first trying to establish a Confidential VMBus connection with the paravisor
+usingstandard mechanisms where the memory remains encrypted. If this succeeds,
+then the guest can proceed to use Confidential VMBus. If it fails, then the
+guest must fallback to establishing a non-Confidential VMBus connection with
+the Hyper-V host.
+
+Confidential VMBus is a characteristic of the VMBus connection as a whole,
+and of each VMBus channel that is created. When a Confidential VMBus
+connection is established, the paravisor provides the guest the message-passing
+path that is used for VMBus device creation and deletion, and it provides a
+per-CPU synthetic interrupt controller (SynIC) just like the SynIC that is
+offered by the Hyper-V host. Each VMBus device that is offered to the guest
+indicates the degree to which it participates in Confidential VMBus. The offer
+indicates if the device uses encrypted ring buffers, and if the device uses
+encrypted memory for DMA that is done outside the ring buffer. These settings
+may be different for different devices using the same Confidential VMBus
+connection.
+
+Although these settings are separate, in practice it'll always be encrypted
+ring buffer only, or both encrypted ring buffer and external data. If a channel
+is offered by the paravisor with confidential VMBus, the ring buffer can always
+be encrypted since it's strictly for communication between the VTL2 paravisor
+and the VTL0 guest. However, other memory regions are often used for e.g. DMA,
+so they need to be accessible by the underlying hardware, and must be
+unencrypted (unless the device supports encrypted memory). Currently, there are
+not any VSPs in OpenHCL that support encrypted external memory, but future
+versions are expected to enable this capability.
+
+Because some devices on a Confidential VMBus may require decrypted ring buffers
+and DMA transfers, the guest must interact with two SynICs -- the one provided
+by the paravisor and the one provided by the Hyper-V host when Confidential
+VMBus is not offered. Interrupts are always signaled by the paravisor SynIC,
+but the guest must check for messages and for channel interrupts on both SynICs.
+
+In the case of a confidential VMBus, regular SynIC access by the guest is
+intercepted by the paravisor (this includes various MSRs such as the SIMP and
+SIEFP, as well as hypercalls like HvPostMessage and HvSignalEvent). If the
+guest actually wants to communicate with the hypervisor, it has to use special
+mechanisms (GHCB page on SNP, or tdcall on TDX). Messages can be of either
+kind: with confidential VMBus, messages use the paravisor SynIC, and if the
+guest chose to communicate directly to the hypervisor, they use the hypervisor
+SynIC. For interrupt signaling, some channels may be running on the host
+(non-confidential, using the VMBus relay) and use the hypervisor SynIC, and
+some on the paravisor and use its SynIC. The RelIDs are coordinated by the
+OpenHCL VMBus server and are guaranteed to be unique regardless of whether
+the channel originated on the host or the paravisor.
+
 load_unaligned_zeropad()
 ------------------------
 When transitioning memory between encrypted and decrypted, the caller of

---

## [3] Roman Kisel — 2025-07-14
*Subject: [PATCH hyperv-next v4 02/16] drivers: hv: VMBus protocol version 6.0*

The confidential VMBus is supported starting from the protocol
version 6.0 onwards.

Update the relevant definitions, and provide a function that returns
whether VMBus is confidential or not. No functional changes.

Signed-off-by: Roman Kisel <romank@linux.microsoft.com>
Reviewed-by: Alok Tiwari <alok.a.tiwari@oracle.com>
---
 drivers/hv/vmbus_drv.c         | 12 ++++++
 include/asm-generic/mshyperv.h |  1 +
 include/linux/hyperv.h         | 69 ++++++++++++++++++++++++----------
 3 files changed, 63 insertions(+), 19 deletions(-)

diff --git a/drivers/hv/vmbus_drv.c b/drivers/hv/vmbus_drv.c
index 33b524b4eb5e..698c86c4ef03 100644
--- a/drivers/hv/vmbus_drv.c
+++ b/drivers/hv/vmbus_drv.c
@@ -56,6 +56,18 @@ static long __percpu *vmbus_evt;
 int vmbus_irq;
 int vmbus_interrupt;
 
+/*
+ * If the Confidential VMBus is used, the data on the "wire" is not
+ * visible to either the host or the hypervisor.
+ */
+static bool is_confidential;
+
+bool vmbus_is_confidential(void)
+{
+	return is_confidential;
+}
+EXPORT_SYMBOL_GPL(vmbus_is_confidential);
+
 /*
  * The panic notifier below is responsible solely for unloading the
  * vmbus connection, which is necessary in a panic event.
diff --git a/include/asm-generic/mshyperv.h b/include/asm-generic/mshyperv.h
index a729b77983fa..9722934a8332 100644
--- a/include/asm-generic/mshyperv.h
+++ b/include/asm-generic/mshyperv.h
@@ -373,6 +373,7 @@ static inline int hv_call_create_vp(int node, u64 partition_id, u32 vp_index, u3
 	return -EOPNOTSUPP;
 }
 #endif /* CONFIG_MSHV_ROOT */
+bool vmbus_is_confidential(void);
 
 #if IS_ENABLED(CONFIG_HYPERV_VTL_MODE)
 u8 __init get_vtl(void);
diff --git a/include/linux/hyperv.h b/include/linux/hyperv.h
index a59c5c3e95fb..a1820fabbfc0 100644
--- a/include/linux/hyperv.h
+++ b/include/linux/hyperv.h
@@ -265,16 +265,18 @@ static inline u32 hv_get_avail_to_write_percent(
  * Linux kernel.
  */
 
-#define VERSION_WS2008  ((0 << 16) | (13))
-#define VERSION_WIN7    ((1 << 16) | (1))
-#define VERSION_WIN8    ((2 << 16) | (4))
-#define VERSION_WIN8_1    ((3 << 16) | (0))
-#define VERSION_WIN10 ((4 << 16) | (0))
-#define VERSION_WIN10_V4_1 ((4 << 16) | (1))
-#define VERSION_WIN10_V5 ((5 << 16) | (0))
-#define VERSION_WIN10_V5_1 ((5 << 16) | (1))
-#define VERSION_WIN10_V5_2 ((5 << 16) | (2))
-#define VERSION_WIN10_V5_3 ((5 << 16) | (3))
+#define VMBUS_MAKE_VERSION(MAJ, MIN)	((((u32)MAJ) << 16) | (MIN))
+#define VERSION_WS2008					VMBUS_MAKE_VERSION(0, 13)
+#define VERSION_WIN7					VMBUS_MAKE_VERSION(1, 1)
+#define VERSION_WIN8					VMBUS_MAKE_VERSION(2, 4)
+#define VERSION_WIN8_1					VMBUS_MAKE_VERSION(3, 0)
+#define VERSION_WIN10					VMBUS_MAKE_VERSION(4, 0)
+#define VERSION_WIN10_V4_1				VMBUS_MAKE_VERSION(4, 1)
+#define VERSION_WIN10_V5				VMBUS_MAKE_VERSION(5, 0)
+#define VERSION_WIN10_V5_1				VMBUS_MAKE_VERSION(5, 1)
+#define VERSION_WIN10_V5_2				VMBUS_MAKE_VERSION(5, 2)
+#define VERSION_WIN10_V5_3				VMBUS_MAKE_VERSION(5, 3)
+#define VERSION_WIN10_V6_0				VMBUS_MAKE_VERSION(6, 0)
 
 /* Make maximum size of pipe payload of 16K */
 #define MAX_PIPE_DATA_PAYLOAD		(sizeof(u8) * 16384)
@@ -335,14 +337,22 @@ struct vmbus_channel_offer {
 } __packed;
 
 /* Server Flags */
-#define VMBUS_CHANNEL_ENUMERATE_DEVICE_INTERFACE	1
-#define VMBUS_CHANNEL_SERVER_SUPPORTS_TRANSFER_PAGES	2
-#define VMBUS_CHANNEL_SERVER_SUPPORTS_GPADLS		4
-#define VMBUS_CHANNEL_NAMED_PIPE_MODE			0x10
-#define VMBUS_CHANNEL_LOOPBACK_OFFER			0x100
-#define VMBUS_CHANNEL_PARENT_OFFER			0x200
-#define VMBUS_CHANNEL_REQUEST_MONITORED_NOTIFICATION	0x400
-#define VMBUS_CHANNEL_TLNPI_PROVIDER_OFFER		0x2000
+#define VMBUS_CHANNEL_ENUMERATE_DEVICE_INTERFACE		0x0001
+/*
+ * This flag indicates that the channel is offered by the paravisor, and must
+ * use encrypted memory for the channel ring buffer.
+ */
+#define VMBUS_CHANNEL_CONFIDENTIAL_RING_BUFFER			0x0002
+/*
+ * This flag indicates that the channel is offered by the paravisor, and must
+ * use encrypted memory for GPA direct packets and additional GPADLs.
+ */
+#define VMBUS_CHANNEL_CONFIDENTIAL_EXTERNAL_MEMORY		0x0004
+#define VMBUS_CHANNEL_NAMED_PIPE_MODE					0x0010
+#define VMBUS_CHANNEL_LOOPBACK_OFFER					0x0100
+#define VMBUS_CHANNEL_PARENT_OFFER						0x0200
+#define VMBUS_CHANNEL_REQUEST_MONITORED_NOTIFICATION	0x0400
+#define VMBUS_CHANNEL_TLNPI_PROVIDER_OFFER				0x2000
 
 struct vmpacket_descriptor {
 	u16 type;
@@ -621,6 +631,12 @@ struct vmbus_channel_relid_released {
 	u32 child_relid;
 } __packed;
 
+/*
+ * Used by the paravisor only, means that the encrypted ring buffers and
+ * the encrypted external memory are supported
+ */
+#define VMBUS_FEATURE_FLAG_CONFIDENTIAL_CHANNELS	0x10
+
 struct vmbus_channel_initiate_contact {
 	struct vmbus_channel_message_header header;
 	u32 vmbus_version_requested;
@@ -630,7 +646,8 @@ struct vmbus_channel_initiate_contact {
 		struct {
 			u8	msg_sint;
 			u8	msg_vtl;
-			u8	reserved[6];
+			u8	reserved[2];
+			u32 feature_flags; /* VMBus version 6.0 */
 		};
 	};
 	u64 monitor_page1;
@@ -1008,6 +1025,10 @@ struct vmbus_channel {
 
 	/* boolean to control visibility of sysfs for ring buffer */
 	bool ring_sysfs_visible;
+	/* The ring buffer is encrypted */
+	bool co_ring_buffer;
+	/* The external memory is encrypted */
+	bool co_external_memory;
 };
 
 #define lock_requestor(channel, flags)					\
@@ -1032,6 +1053,16 @@ u64 vmbus_request_addr_match(struct vmbus_channel *channel, u64 trans_id,
 			     u64 rqst_addr);
 u64 vmbus_request_addr(struct vmbus_channel *channel, u64 trans_id);
 
+static inline bool is_co_ring_buffer(const struct vmbus_channel_offer_channel *o)
+{
+	return !!(o->offer.chn_flags & VMBUS_CHANNEL_CONFIDENTIAL_RING_BUFFER);
+}
+
+static inline bool is_co_external_memory(const struct vmbus_channel_offer_channel *o)
+{
+	return !!(o->offer.chn_flags & VMBUS_CHANNEL_CONFIDENTIAL_EXTERNAL_MEMORY);
+}
+
 static inline bool is_hvsock_offer(const struct vmbus_channel_offer_channel *o)
 {
 	return !!(o->offer.chn_flags & VMBUS_CHANNEL_TLNPI_PROVIDER_OFFER);

---

## [4] Roman Kisel — 2025-07-14
*Subject: [PATCH hyperv-next v4 03/16] arch: hyperv: Get/set SynIC synth.registers via paravisor*

The existing Hyper-V wrappers for getting and setting MSRs are
hv_get/set_msr(). Via hv_get/set_non_nested_msr(), they detect
when running in a CoCo VM with a paravisor, and use the TDX or
SNP guest-host communication protocol to bypass the paravisor
and go directly to the host hypervisor for SynIC MSRs. The "set"
function also implements the required special handling for the
SINT MSRs.

But in some Confidential VMBus cases, the guest wants to talk only
with the paravisor. To accomplish this, provide new functions for
accessing SynICs that always do direct accesses (i.e., not via
TDX or SNP GHCB), which will go to the paravisor. The mirroring
of the existing "set" function is also not needed. These functions
should be used only in the specific Confidential VMBus cases that
require them.

Provide functions that allow manipulating the SynIC registers
through the paravisor.

Signed-off-by: Roman Kisel <romank@linux.microsoft.com>
Reviewed-by: Alok Tiwari <alok.a.tiwari@oracle.com>
---
 arch/x86/kernel/cpu/mshyperv.c | 39 ++++++++++++++++++
 drivers/hv/hv_common.c         | 13 ++++++
 include/asm-generic/mshyperv.h | 75 ++++++++++++++++++----------------
 3 files changed, 92 insertions(+), 35 deletions(-)

diff --git a/arch/x86/kernel/cpu/mshyperv.c b/arch/x86/kernel/cpu/mshyperv.c
index c78f860419d6..07c60231d0d8 100644
--- a/arch/x86/kernel/cpu/mshyperv.c
+++ b/arch/x86/kernel/cpu/mshyperv.c
@@ -90,6 +90,45 @@ void hv_set_non_nested_msr(unsigned int reg, u64 value)
 }
 EXPORT_SYMBOL_GPL(hv_set_non_nested_msr);
 
+/*
+ * Attempt to get the SynIC register value from the paravisor.
+ *
+ * Not all paravisors support reading SynIC registers, so this function
+ * may fail. The register for the SynIC of the running CPU is accessed.
+ *
+ * Writes the SynIC register value into the memory pointed by val,
+ * and ~0ULL is on failure.
+ *
+ * Returns -ENODEV if the MSR is not a SynIC register, or another error
+ * code if getting the MSR fails (meaning the paravisor doesn't support
+ * relaying VMBus communucations).
+ */
+int hv_para_get_synic_register(unsigned int reg, u64 *val)
+{
+	if (!hv_is_synic_msr(reg))
+		return -ENODEV;
+	return native_read_msr_safe(reg, val);
+}
+
+/*
+ * Attempt to set the SynIC register value with the paravisor.
+ *
+ * Not all paravisors support setting SynIC registers, so this function
+ * may fail. The register for the SynIC of the running CPU is accessed.
+ *
+ * Sets the register to the value supplied.
+ *
+ * Returns: -ENODEV if the MSR is not a SynIC register, or another error
+ * code if writing to the MSR fails (meaning the paravisor doesn't support
+ * relaying VMBus communucations).
+ */
+int hv_para_set_synic_register(unsigned int reg, u64 val)
+{
+	if (!hv_is_synic_msr(reg))
+		return -ENODEV;
+	return native_write_msr_safe(reg, val);
+}
+
 u64 hv_get_msr(unsigned int reg)
 {
 	if (hv_nested)
diff --git a/drivers/hv/hv_common.c b/drivers/hv/hv_common.c
index 49898d10faff..a179ea482cb1 100644
--- a/drivers/hv/hv_common.c
+++ b/drivers/hv/hv_common.c
@@ -716,6 +716,19 @@ u64 __weak hv_tdx_hypercall(u64 control, u64 param1, u64 param2)
 }
 EXPORT_SYMBOL_GPL(hv_tdx_hypercall);
 
+int __weak hv_para_get_synic_register(unsigned int reg, u64 *val)
+{
+	*val = ~0ULL;
+	return -ENODEV;
+}
+EXPORT_SYMBOL_GPL(hv_para_get_synic_register);
+
+int __weak hv_para_set_synic_register(unsigned int reg, u64 val)
+{
+	return -ENODEV;
+}
+EXPORT_SYMBOL_GPL(hv_para_set_synic_register);
+
 void hv_identify_partition_type(void)
 {
 	/* Assume guest role */
diff --git a/include/asm-generic/mshyperv.h b/include/asm-generic/mshyperv.h
index 9722934a8332..9447558f425b 100644
--- a/include/asm-generic/mshyperv.h
+++ b/include/asm-generic/mshyperv.h
@@ -162,41 +162,6 @@ static inline u64 hv_generate_guest_id(u64 kernel_version)
 	return guest_id;
 }
 
-/* Free the message slot and signal end-of-message if required */
-static inline void vmbus_signal_eom(struct hv_message *msg, u32 old_msg_type)
-{
-	/*
-	 * On crash we're reading some other CPU's message page and we need
-	 * to be careful: this other CPU may already had cleared the header
-	 * and the host may already had delivered some other message there.
-	 * In case we blindly write msg->header.message_type we're going
-	 * to lose it. We can still lose a message of the same type but
-	 * we count on the fact that there can only be one
-	 * CHANNELMSG_UNLOAD_RESPONSE and we don't care about other messages
-	 * on crash.
-	 */
-	if (cmpxchg(&msg->header.message_type, old_msg_type,
-		    HVMSG_NONE) != old_msg_type)
-		return;
-
-	/*
-	 * The cmxchg() above does an implicit memory barrier to
-	 * ensure the write to MessageType (ie set to
-	 * HVMSG_NONE) happens before we read the
-	 * MessagePending and EOMing. Otherwise, the EOMing
-	 * will not deliver any more messages since there is
-	 * no empty slot
-	 */
-	if (msg->header.message_flags.msg_pending) {
-		/*
-		 * This will cause message queue rescan to
-		 * possibly deliver another msg from the
-		 * hypervisor
-		 */
-		hv_set_msr(HV_MSR_EOM, 0);
-	}
-}
-
 int hv_get_hypervisor_version(union hv_hypervisor_version_info *info);
 
 void hv_setup_vmbus_handler(void (*handler)(void));
@@ -333,6 +298,8 @@ bool hv_is_isolation_supported(void);
 bool hv_isolation_type_snp(void);
 u64 hv_ghcb_hypercall(u64 control, void *input, void *output, u32 input_size);
 u64 hv_tdx_hypercall(u64 control, u64 param1, u64 param2);
+int hv_para_get_synic_register(unsigned int reg, u64 *val);
+int hv_para_set_synic_register(unsigned int reg, u64 val);
 void hyperv_cleanup(void);
 bool hv_query_ext_cap(u64 cap_query);
 void hv_setup_dma_ops(struct device *dev, bool coherent);
@@ -375,6 +342,44 @@ static inline int hv_call_create_vp(int node, u64 partition_id, u32 vp_index, u3
 #endif /* CONFIG_MSHV_ROOT */
 bool vmbus_is_confidential(void);
 
+/* Free the message slot and signal end-of-message if required */
+static inline void vmbus_signal_eom(struct hv_message *msg, u32 old_msg_type)
+{
+	/*
+	 * On crash we're reading some other CPU's message page and we need
+	 * to be careful: this other CPU may already had cleared the header
+	 * and the host may already had delivered some other message there.
+	 * In case we blindly write msg->header.message_type we're going
+	 * to lose it. We can still lose a message of the same type but
+	 * we count on the fact that there can only be one
+	 * CHANNELMSG_UNLOAD_RESPONSE and we don't care about other messages
+	 * on crash.
+	 */
+	if (cmpxchg(&msg->header.message_type, old_msg_type,
+		    HVMSG_NONE) != old_msg_type)
+		return;
+
+	/*
+	 * The cmxchg() above does an implicit memory barrier to
+	 * ensure the write to MessageType (ie set to
+	 * HVMSG_NONE) happens before we read the
+	 * MessagePending and EOMing. Otherwise, the EOMing
+	 * will not deliver any more messages since there is
+	 * no empty slot
+	 */
+	if (msg->header.message_flags.msg_pending) {
+		/*
+		 * This will cause message queue rescan to
+		 * possibly deliver another msg from the
+		 * hypervisor
+		 */
+		if (vmbus_is_confidential())
+			hv_para_set_synic_register(HV_MSR_EOM, 0);
+		else
+			hv_set_msr(HV_MSR_EOM, 0);
+	}
+}
+
 #if IS_ENABLED(CONFIG_HYPERV_VTL_MODE)
 u8 __init get_vtl(void);
 #else

---

## [5] Roman Kisel — 2025-07-14
*Subject: [PATCH hyperv-next v4 04/16] arch/x86: mshyperv: Trap on access for some synthetic MSRs*

hv_set_non_nested_msr() has special handling for SINT MSRs
when a paravisor is present. In addition to updating the MSR on the
host, the mirror MSR in the paravisor is updated, including with the
proxy bit. But with Confidential VMBus, the proxy bit must not be
used, so add a special case to skip it.

Update the hv_set_non_nested_msr() function as well as
vmbus_signal_eom() to trap on access for some synthetic MSRs.

Signed-off-by: Roman Kisel <romank@linux.microsoft.com>
Reviewed-by: Alok Tiwari <alok.a.tiwari@oracle.com>
---
 arch/x86/kernel/cpu/mshyperv.c | 17 +++++++++++++----
 1 file changed, 13 insertions(+), 4 deletions(-)

diff --git a/arch/x86/kernel/cpu/mshyperv.c b/arch/x86/kernel/cpu/mshyperv.c
index 07c60231d0d8..6c5a0a779c02 100644
--- a/arch/x86/kernel/cpu/mshyperv.c
+++ b/arch/x86/kernel/cpu/mshyperv.c
@@ -28,6 +28,7 @@
 #include <asm/apic.h>
 #include <asm/timer.h>
 #include <asm/reboot.h>
+#include <asm/msr.h>
 #include <asm/nmi.h>
 #include <clocksource/hyperv_timer.h>
 #include <asm/msr.h>
@@ -79,13 +80,21 @@ EXPORT_SYMBOL_GPL(hv_get_non_nested_msr);
 void hv_set_non_nested_msr(unsigned int reg, u64 value)
 {
 	if (hv_is_synic_msr(reg) && ms_hyperv.paravisor_present) {
+		/* The hypervisor will get the intercept. */
 		hv_ivm_msr_write(reg, value);
 
-		/* Write proxy bit via wrmsl instruction */
-		if (hv_is_sint_msr(reg))
-			wrmsrq(reg, value | 1 << 20);
+		if (hv_is_sint_msr(reg)) {
+			/*
+			 * Write proxy bit in the case of non-confidential VMBus.
+			 * Using wrmsrq instruction so the following goes to the paravisor.
+			 */
+			u32 proxy = vmbus_is_confidential() ? 0 : 1;
+
+			value |= (proxy << 20);
+			native_wrmsrq(reg, value);
+		}
 	} else {
-		wrmsrq(reg, value);
+		native_wrmsrq(reg, value);
 	}
 }
 EXPORT_SYMBOL_GPL(hv_set_non_nested_msr);

---

## [6] Roman Kisel — 2025-07-14
*Subject: [PATCH hyperv-next v4 05/16] Drivers: hv: Rename fields for SynIC message and event pages*

Confidential VMBus requires interacting with two SynICs -- one
provided by the host hypervisor, and one provided by the paravisor.
Each SynIC requires its own message and event pages.

Rename the existing host-accessible SynIC message and event pages
with the "hyp_" prefix to clearly distinguish them from the paravisor
ones. The field name is also changed in mshv_root.* for consistency.

No functional changes.

Signed-off-by: Roman Kisel <romank@linux.microsoft.com>
---
 drivers/hv/channel_mgmt.c |  6 ++--
 drivers/hv/hv.c           | 66 +++++++++++++++++++--------------------
 drivers/hv/hyperv_vmbus.h |  4 +--
 drivers/hv/mshv_root.h    |  2 +-
 drivers/hv/mshv_synic.c   |  6 ++--
 drivers/hv/vmbus_drv.c    |  6 ++--
 6 files changed, 45 insertions(+), 45 deletions(-)

diff --git a/drivers/hv/channel_mgmt.c b/drivers/hv/channel_mgmt.c
index 6e084c207414..6f87220e2ca3 100644
--- a/drivers/hv/channel_mgmt.c
+++ b/drivers/hv/channel_mgmt.c
@@ -843,14 +843,14 @@ static void vmbus_wait_for_unload(void)
 				= per_cpu_ptr(hv_context.cpu_context, cpu);
 
 			/*
-			 * In a CoCo VM the synic_message_page is not allocated
+			 * In a CoCo VM the hyp_synic_message_page is not allocated
 			 * in hv_synic_alloc(). Instead it is set/cleared in
 			 * hv_synic_enable_regs() and hv_synic_disable_regs()
 			 * such that it is set only when the CPU is online. If
 			 * not all present CPUs are online, the message page
 			 * might be NULL, so skip such CPUs.
 			 */
-			page_addr = hv_cpu->synic_message_page;
+			page_addr = hv_cpu->hyp_synic_message_page;
 			if (!page_addr)
 				continue;
 
@@ -891,7 +891,7 @@ static void vmbus_wait_for_unload(void)
 		struct hv_per_cpu_context *hv_cpu
 			= per_cpu_ptr(hv_context.cpu_context, cpu);
 
-		page_addr = hv_cpu->synic_message_page;
+		page_addr = hv_cpu->hyp_synic_message_page;
 		if (!page_addr)
 			continue;
 
diff --git a/drivers/hv/hv.c b/drivers/hv/hv.c
index 308c8f279df8..964b9102477d 100644
--- a/drivers/hv/hv.c
+++ b/drivers/hv/hv.c
@@ -145,20 +145,20 @@ int hv_synic_alloc(void)
 		 * Skip these pages allocation here.
 		 */
 		if (!ms_hyperv.paravisor_present && !hv_root_partition()) {
-			hv_cpu->synic_message_page =
+			hv_cpu->hyp_synic_message_page =
 				(void *)get_zeroed_page(GFP_ATOMIC);
-			if (!hv_cpu->synic_message_page) {
+			if (!hv_cpu->hyp_synic_message_page) {
 				pr_err("Unable to allocate SYNIC message page\n");
 				goto err;
 			}
 
-			hv_cpu->synic_event_page =
+			hv_cpu->hyp_synic_event_page =
 				(void *)get_zeroed_page(GFP_ATOMIC);
-			if (!hv_cpu->synic_event_page) {
+			if (!hv_cpu->hyp_synic_event_page) {
 				pr_err("Unable to allocate SYNIC event page\n");
 
-				free_page((unsigned long)hv_cpu->synic_message_page);
-				hv_cpu->synic_message_page = NULL;
+				free_page((unsigned long)hv_cpu->hyp_synic_message_page);
+				hv_cpu->hyp_synic_message_page = NULL;
 				goto err;
 			}
 		}
@@ -166,30 +166,30 @@ int hv_synic_alloc(void)
 		if (!ms_hyperv.paravisor_present &&
 		    (hv_isolation_type_snp() || hv_isolation_type_tdx())) {
 			ret = set_memory_decrypted((unsigned long)
-				hv_cpu->synic_message_page, 1);
+				hv_cpu->hyp_synic_message_page, 1);
 			if (ret) {
 				pr_err("Failed to decrypt SYNIC msg page: %d\n", ret);
-				hv_cpu->synic_message_page = NULL;
+				hv_cpu->hyp_synic_message_page = NULL;
 
 				/*
 				 * Free the event page here so that hv_synic_free()
 				 * won't later try to re-encrypt it.
 				 */
-				free_page((unsigned long)hv_cpu->synic_event_page);
-				hv_cpu->synic_event_page = NULL;
+				free_page((unsigned long)hv_cpu->hyp_synic_event_page);
+				hv_cpu->hyp_synic_event_page = NULL;
 				goto err;
 			}
 
 			ret = set_memory_decrypted((unsigned long)
-				hv_cpu->synic_event_page, 1);
+				hv_cpu->hyp_synic_event_page, 1);
 			if (ret) {
 				pr_err("Failed to decrypt SYNIC event page: %d\n", ret);
-				hv_cpu->synic_event_page = NULL;
+				hv_cpu->hyp_synic_event_page = NULL;
 				goto err;
 			}
 
-			memset(hv_cpu->synic_message_page, 0, PAGE_SIZE);
-			memset(hv_cpu->synic_event_page, 0, PAGE_SIZE);
+			memset(hv_cpu->hyp_synic_message_page, 0, PAGE_SIZE);
+			memset(hv_cpu->hyp_synic_event_page, 0, PAGE_SIZE);
 		}
 	}
 
@@ -225,28 +225,28 @@ void hv_synic_free(void)
 
 		if (!ms_hyperv.paravisor_present &&
 		    (hv_isolation_type_snp() || hv_isolation_type_tdx())) {
-			if (hv_cpu->synic_message_page) {
+			if (hv_cpu->hyp_synic_message_page) {
 				ret = set_memory_encrypted((unsigned long)
-					hv_cpu->synic_message_page, 1);
+					hv_cpu->hyp_synic_message_page, 1);
 				if (ret) {
 					pr_err("Failed to encrypt SYNIC msg page: %d\n", ret);
-					hv_cpu->synic_message_page = NULL;
+					hv_cpu->hyp_synic_message_page = NULL;
 				}
 			}
 
-			if (hv_cpu->synic_event_page) {
+			if (hv_cpu->hyp_synic_event_page) {
 				ret = set_memory_encrypted((unsigned long)
-					hv_cpu->synic_event_page, 1);
+					hv_cpu->hyp_synic_event_page, 1);
 				if (ret) {
 					pr_err("Failed to encrypt SYNIC event page: %d\n", ret);
-					hv_cpu->synic_event_page = NULL;
+					hv_cpu->hyp_synic_event_page = NULL;
 				}
 			}
 		}
 
 		free_page((unsigned long)hv_cpu->post_msg_page);
-		free_page((unsigned long)hv_cpu->synic_event_page);
-		free_page((unsigned long)hv_cpu->synic_message_page);
+		free_page((unsigned long)hv_cpu->hyp_synic_event_page);
+		free_page((unsigned long)hv_cpu->hyp_synic_message_page);
 	}
 
 	kfree(hv_context.hv_numa_map);
@@ -276,12 +276,12 @@ void hv_synic_enable_regs(unsigned int cpu)
 		/* Mask out vTOM bit. ioremap_cache() maps decrypted */
 		u64 base = (simp.base_simp_gpa << HV_HYP_PAGE_SHIFT) &
 				~ms_hyperv.shared_gpa_boundary;
-		hv_cpu->synic_message_page =
+		hv_cpu->hyp_synic_message_page =
 			(void *)ioremap_cache(base, HV_HYP_PAGE_SIZE);
-		if (!hv_cpu->synic_message_page)
+		if (!hv_cpu->hyp_synic_message_page)
 			pr_err("Fail to map synic message page.\n");
 	} else {
-		simp.base_simp_gpa = virt_to_phys(hv_cpu->synic_message_page)
+		simp.base_simp_gpa = virt_to_phys(hv_cpu->hyp_synic_message_page)
 			>> HV_HYP_PAGE_SHIFT;
 	}
 
@@ -295,12 +295,12 @@ void hv_synic_enable_regs(unsigned int cpu)
 		/* Mask out vTOM bit. ioremap_cache() maps decrypted */
 		u64 base = (siefp.base_siefp_gpa << HV_HYP_PAGE_SHIFT) &
 				~ms_hyperv.shared_gpa_boundary;
-		hv_cpu->synic_event_page =
+		hv_cpu->hyp_synic_event_page =
 			(void *)ioremap_cache(base, HV_HYP_PAGE_SIZE);
-		if (!hv_cpu->synic_event_page)
+		if (!hv_cpu->hyp_synic_event_page)
 			pr_err("Fail to map synic event page.\n");
 	} else {
-		siefp.base_siefp_gpa = virt_to_phys(hv_cpu->synic_event_page)
+		siefp.base_siefp_gpa = virt_to_phys(hv_cpu->hyp_synic_event_page)
 			>> HV_HYP_PAGE_SHIFT;
 	}
 
@@ -358,8 +358,8 @@ void hv_synic_disable_regs(unsigned int cpu)
 	 */
 	simp.simp_enabled = 0;
 	if (ms_hyperv.paravisor_present || hv_root_partition()) {
-		iounmap(hv_cpu->synic_message_page);
-		hv_cpu->synic_message_page = NULL;
+		iounmap(hv_cpu->hyp_synic_message_page);
+		hv_cpu->hyp_synic_message_page = NULL;
 	} else {
 		simp.base_simp_gpa = 0;
 	}
@@ -370,8 +370,8 @@ void hv_synic_disable_regs(unsigned int cpu)
 	siefp.siefp_enabled = 0;
 
 	if (ms_hyperv.paravisor_present || hv_root_partition()) {
-		iounmap(hv_cpu->synic_event_page);
-		hv_cpu->synic_event_page = NULL;
+		iounmap(hv_cpu->hyp_synic_event_page);
+		hv_cpu->hyp_synic_event_page = NULL;
 	} else {
 		siefp.base_siefp_gpa = 0;
 	}
@@ -401,7 +401,7 @@ static bool hv_synic_event_pending(void)
 {
 	struct hv_per_cpu_context *hv_cpu = this_cpu_ptr(hv_context.cpu_context);
 	union hv_synic_event_flags *event =
-		(union hv_synic_event_flags *)hv_cpu->synic_event_page + VMBUS_MESSAGE_SINT;
+		(union hv_synic_event_flags *)hv_cpu->hyp_synic_event_page + VMBUS_MESSAGE_SINT;
 	unsigned long *recv_int_page = event->flags; /* assumes VMBus version >= VERSION_WIN8 */
 	bool pending;
 	u32 relid;
diff --git a/drivers/hv/hyperv_vmbus.h b/drivers/hv/hyperv_vmbus.h
index 0b450e53161e..fc3cdb26ff1a 100644
--- a/drivers/hv/hyperv_vmbus.h
+++ b/drivers/hv/hyperv_vmbus.h
@@ -120,8 +120,8 @@ enum {
  * Per cpu state for channel handling
  */
 struct hv_per_cpu_context {
-	void *synic_message_page;
-	void *synic_event_page;
+	void *hyp_synic_message_page;
+	void *hyp_synic_event_page;
 
 	/*
 	 * The page is only used in hv_post_message() for a TDX VM (with the
diff --git a/drivers/hv/mshv_root.h b/drivers/hv/mshv_root.h
index e3931b0f1269..db6b42db2fdc 100644
--- a/drivers/hv/mshv_root.h
+++ b/drivers/hv/mshv_root.h
@@ -169,7 +169,7 @@ struct mshv_girq_routing_table {
 };
 
 struct hv_synic_pages {
-	struct hv_message_page *synic_message_page;
+	struct hv_message_page *hyp_synic_message_page;
 	struct hv_synic_event_flags_page *synic_event_flags_page;
 	struct hv_synic_event_ring_page *synic_event_ring_page;
 };
diff --git a/drivers/hv/mshv_synic.c b/drivers/hv/mshv_synic.c
index e6b6381b7c36..f8b0337cdc82 100644
--- a/drivers/hv/mshv_synic.c
+++ b/drivers/hv/mshv_synic.c
@@ -394,7 +394,7 @@ mshv_intercept_isr(struct hv_message *msg)
 void mshv_isr(void)
 {
 	struct hv_synic_pages *spages = this_cpu_ptr(mshv_root.synic_pages);
-	struct hv_message_page **msg_page = &spages->synic_message_page;
+	struct hv_message_page **msg_page = &spages->hyp_synic_message_page;
 	struct hv_message *msg;
 	bool handled;
 
@@ -456,7 +456,7 @@ int mshv_synic_init(unsigned int cpu)
 #endif
 	union hv_synic_scontrol sctrl;
 	struct hv_synic_pages *spages = this_cpu_ptr(mshv_root.synic_pages);
-	struct hv_message_page **msg_page = &spages->synic_message_page;
+	struct hv_message_page **msg_page = &spages->hyp_synic_message_page;
 	struct hv_synic_event_flags_page **event_flags_page =
 			&spages->synic_event_flags_page;
 	struct hv_synic_event_ring_page **event_ring_page =
@@ -550,7 +550,7 @@ int mshv_synic_cleanup(unsigned int cpu)
 	union hv_synic_sirbp sirbp;
 	union hv_synic_scontrol sctrl;
 	struct hv_synic_pages *spages = this_cpu_ptr(mshv_root.synic_pages);
-	struct hv_message_page **msg_page = &spages->synic_message_page;
+	struct hv_message_page **msg_page = &spages->hyp_synic_message_page;
 	struct hv_synic_event_flags_page **event_flags_page =
 		&spages->synic_event_flags_page;
 	struct hv_synic_event_ring_page **event_ring_page =
diff --git a/drivers/hv/vmbus_drv.c b/drivers/hv/vmbus_drv.c
index 698c86c4ef03..72940a64b0b6 100644
--- a/drivers/hv/vmbus_drv.c
+++ b/drivers/hv/vmbus_drv.c
@@ -1060,7 +1060,7 @@ static void vmbus_onmessage_work(struct work_struct *work)
 void vmbus_on_msg_dpc(unsigned long data)
 {
 	struct hv_per_cpu_context *hv_cpu = (void *)data;
-	void *page_addr = hv_cpu->synic_message_page;
+	void *page_addr = hv_cpu->hyp_synic_message_page;
 	struct hv_message msg_copy, *msg = (struct hv_message *)page_addr +
 				  VMBUS_MESSAGE_SINT;
 	struct vmbus_channel_message_header *hdr;
@@ -1244,7 +1244,7 @@ static void vmbus_chan_sched(struct hv_per_cpu_context *hv_cpu)
 	 * The event page can be directly checked to get the id of
 	 * the channel that has the interrupt pending.
 	 */
-	void *page_addr = hv_cpu->synic_event_page;
+	void *page_addr = hv_cpu->hyp_synic_event_page;
 	union hv_synic_event_flags *event
 		= (union hv_synic_event_flags *)page_addr +
 					 VMBUS_MESSAGE_SINT;
@@ -1327,7 +1327,7 @@ static void vmbus_isr(void)
 
 	vmbus_chan_sched(hv_cpu);
 
-	page_addr = hv_cpu->synic_message_page;
+	page_addr = hv_cpu->hyp_synic_message_page;
 	msg = (struct hv_message *)page_addr + VMBUS_MESSAGE_SINT;
 
 	/* Check if there are actual msgs to be processed */

---

## [7] Roman Kisel — 2025-07-14
*Subject: [PATCH hyperv-next v4 06/16] Drivers: hv: Allocate the paravisor SynIC pages when required*

Confidential VMBus requires interacting with two SynICs -- one
provided by the host hypervisor, and one provided by the paravisor.
Each SynIC requires its own message and event pages.

Refactor and extend the existing code to add allocating and freeing
the message and event pages for the paravisor SynIC when it is
present.

Signed-off-by: Roman Kisel <romank@linux.microsoft.com>
---
 drivers/hv/hv.c           | 184 +++++++++++++++++++-------------------
 drivers/hv/hyperv_vmbus.h |  18 ++++
 2 files changed, 112 insertions(+), 90 deletions(-)

diff --git a/drivers/hv/hv.c b/drivers/hv/hv.c
index 964b9102477d..e9ee0177d765 100644
--- a/drivers/hv/hv.c
+++ b/drivers/hv/hv.c
@@ -94,10 +94,70 @@ int hv_post_message(union hv_connection_id connection_id,
 	return hv_result(status);
 }
 
+static int hv_alloc_page(void **page, bool decrypt, const char *note)
+{
+	int ret = 0;
+
+	/*
+	 * After the page changes its encryption status, its contents might
+	 * appear scrambled on some hardware. Thus `get_zeroed_page` would
+	 * zero the page out in vain, so do that explicitly exactly once.
+	 *
+	 * By default, the page is allocated encrypted in a CoCo VM.
+	 */
+	*page = (void *)__get_free_page(GFP_KERNEL);
+	if (!*page)
+		return -ENOMEM;
+
+	if (decrypt)
+		ret = set_memory_decrypted((unsigned long)*page, 1);
+	if (ret)
+		goto failed;
+
+	memset(*page, 0, PAGE_SIZE);
+	return 0;
+
+failed:
+	/*
+	 * Report the failure but don't put the page back on the free list as
+	 * its encryption status is unknown.
+	 */
+	pr_err("allocation failed for %s page, error %d, decrypted %d\n",
+		note, ret, decrypt);
+	*page = NULL;
+	return ret;
+}
+
+static int hv_free_page(void **page, bool encrypt, const char *note)
+{
+	int ret = 0;
+
+	if (!*page)
+		return 0;
+
+	if (encrypt)
+		ret = set_memory_encrypted((unsigned long)*page, 1);
+
+	/*
+	 * In the case of the failure, the page is leaked. Something is wrong,
+	 * prefer to lose the page with the unknown encryption status and stay afloat.
+	 */
+	if (ret) {
+		pr_err("deallocation failed for %s page, error %d, encrypt %d\n",
+			note, ret, encrypt);
+	} else
+		free_page((unsigned long)*page);
+
+	*page = NULL;
+
+	return ret;
+}
+
 int hv_synic_alloc(void)
 {
 	int cpu, ret = -ENOMEM;
 	struct hv_per_cpu_context *hv_cpu;
+	const bool decrypt = !vmbus_is_confidential();
 
 	/*
 	 * First, zero all per-cpu memory areas so hv_synic_free() can
@@ -123,73 +183,37 @@ int hv_synic_alloc(void)
 			     vmbus_on_msg_dpc, (unsigned long)hv_cpu);
 
 		if (ms_hyperv.paravisor_present && hv_isolation_type_tdx()) {
-			hv_cpu->post_msg_page = (void *)get_zeroed_page(GFP_ATOMIC);
-			if (!hv_cpu->post_msg_page) {
-				pr_err("Unable to allocate post msg page\n");
+			ret = hv_alloc_page(&hv_cpu->post_msg_page,
+				decrypt, "post msg");
+			if (ret)
 				goto err;
-			}
-
-			ret = set_memory_decrypted((unsigned long)hv_cpu->post_msg_page, 1);
-			if (ret) {
-				pr_err("Failed to decrypt post msg page: %d\n", ret);
-				/* Just leak the page, as it's unsafe to free the page. */
-				hv_cpu->post_msg_page = NULL;
-				goto err;
-			}
-
-			memset(hv_cpu->post_msg_page, 0, PAGE_SIZE);
 		}
 
 		/*
-		 * Synic message and event pages are allocated by paravisor.
-		 * Skip these pages allocation here.
+		 * If these SynIC pages are not allocated, SIEF and SIM pages
+		 * are configured using what the root partition or the paravisor
+		 * provides upon reading the SIEFP and SIMP registers.
 		 */
 		if (!ms_hyperv.paravisor_present && !hv_root_partition()) {
-			hv_cpu->hyp_synic_message_page =
-				(void *)get_zeroed_page(GFP_ATOMIC);
-			if (!hv_cpu->hyp_synic_message_page) {
-				pr_err("Unable to allocate SYNIC message page\n");
+			ret = hv_alloc_page(&hv_cpu->hyp_synic_message_page,
+				decrypt, "hypervisor SynIC msg");
+			if (ret)
 				goto err;
-			}
-
-			hv_cpu->hyp_synic_event_page =
-				(void *)get_zeroed_page(GFP_ATOMIC);
-			if (!hv_cpu->hyp_synic_event_page) {
-				pr_err("Unable to allocate SYNIC event page\n");
-
-				free_page((unsigned long)hv_cpu->hyp_synic_message_page);
-				hv_cpu->hyp_synic_message_page = NULL;
+			ret = hv_alloc_page(&hv_cpu->hyp_synic_event_page,
+				decrypt, "hypervisor SynIC event");
+			if (ret)
 				goto err;
-			}
 		}
 
-		if (!ms_hyperv.paravisor_present &&
-		    (hv_isolation_type_snp() || hv_isolation_type_tdx())) {
-			ret = set_memory_decrypted((unsigned long)
-				hv_cpu->hyp_synic_message_page, 1);
-			if (ret) {
-				pr_err("Failed to decrypt SYNIC msg page: %d\n", ret);
-				hv_cpu->hyp_synic_message_page = NULL;
-
-				/*
-				 * Free the event page here so that hv_synic_free()
-				 * won't later try to re-encrypt it.
-				 */
-				free_page((unsigned long)hv_cpu->hyp_synic_event_page);
-				hv_cpu->hyp_synic_event_page = NULL;
+		if (vmbus_is_confidential()) {
+			ret = hv_alloc_page(&hv_cpu->para_synic_message_page,
+				false, "paravisor SynIC msg");
+			if (ret)
 				goto err;
-			}
-
-			ret = set_memory_decrypted((unsigned long)
-				hv_cpu->hyp_synic_event_page, 1);
-			if (ret) {
-				pr_err("Failed to decrypt SYNIC event page: %d\n", ret);
-				hv_cpu->hyp_synic_event_page = NULL;
+			ret = hv_alloc_page(&hv_cpu->para_synic_event_page,
+				false, "paravisor SynIC event");
+			if (ret)
 				goto err;
-			}
-
-			memset(hv_cpu->hyp_synic_message_page, 0, PAGE_SIZE);
-			memset(hv_cpu->hyp_synic_event_page, 0, PAGE_SIZE);
 		}
 	}
 
@@ -205,48 +229,28 @@ int hv_synic_alloc(void)
 
 void hv_synic_free(void)
 {
-	int cpu, ret;
+	int cpu;
+	const bool encrypt = !vmbus_is_confidential();
 
 	for_each_present_cpu(cpu) {
 		struct hv_per_cpu_context *hv_cpu =
 			per_cpu_ptr(hv_context.cpu_context, cpu);
 
-		/* It's better to leak the page if the encryption fails. */
-		if (ms_hyperv.paravisor_present && hv_isolation_type_tdx()) {
-			if (hv_cpu->post_msg_page) {
-				ret = set_memory_encrypted((unsigned long)
-					hv_cpu->post_msg_page, 1);
-				if (ret) {
-					pr_err("Failed to encrypt post msg page: %d\n", ret);
-					hv_cpu->post_msg_page = NULL;
-				}
-			}
+		if (ms_hyperv.paravisor_present && hv_isolation_type_tdx())
+			hv_free_page(&hv_cpu->post_msg_page,
+				encrypt, "post msg");
+		if (!ms_hyperv.paravisor_present && !hv_root_partition()) {
+			hv_free_page(&hv_cpu->hyp_synic_event_page,
+				encrypt, "hypervisor SynIC event");
+			hv_free_page(&hv_cpu->hyp_synic_message_page,
+				encrypt, "hypervisor SynIC msg");
 		}
-
-		if (!ms_hyperv.paravisor_present &&
-		    (hv_isolation_type_snp() || hv_isolation_type_tdx())) {
-			if (hv_cpu->hyp_synic_message_page) {
-				ret = set_memory_encrypted((unsigned long)
-					hv_cpu->hyp_synic_message_page, 1);
-				if (ret) {
-					pr_err("Failed to encrypt SYNIC msg page: %d\n", ret);
-					hv_cpu->hyp_synic_message_page = NULL;
-				}
-			}
-
-			if (hv_cpu->hyp_synic_event_page) {
-				ret = set_memory_encrypted((unsigned long)
-					hv_cpu->hyp_synic_event_page, 1);
-				if (ret) {
-					pr_err("Failed to encrypt SYNIC event page: %d\n", ret);
-					hv_cpu->hyp_synic_event_page = NULL;
-				}
-			}
+		if (vmbus_is_confidential()) {
+			hv_free_page(&hv_cpu->para_synic_event_page,
+				false, "paravisor SynIC event");
+			hv_free_page(&hv_cpu->para_synic_message_page,
+				false, "paravisor SynIC msg");
 		}
-
-		free_page((unsigned long)hv_cpu->post_msg_page);
-		free_page((unsigned long)hv_cpu->hyp_synic_event_page);
-		free_page((unsigned long)hv_cpu->hyp_synic_message_page);
 	}
 
 	kfree(hv_context.hv_numa_map);
diff --git a/drivers/hv/hyperv_vmbus.h b/drivers/hv/hyperv_vmbus.h
index fc3cdb26ff1a..16b5cf1bca19 100644
--- a/drivers/hv/hyperv_vmbus.h
+++ b/drivers/hv/hyperv_vmbus.h
@@ -120,8 +120,26 @@ enum {
  * Per cpu state for channel handling
  */
 struct hv_per_cpu_context {
+	/*
+	 * SynIC pages for communicating with the host.
+	 *
+	 * These pages are accessible to the host partition and the hypervisor.
+	 * They may be used for exchanging data with the host partition and the
+	 * hypervisor even when they aren't trusted yet the guest partition
+	 * must be prepared to handle the malicious behavior.
+	 */
 	void *hyp_synic_message_page;
 	void *hyp_synic_event_page;
+	/*
+	 * SynIC pages for communicating with the paravisor.
+	 *
+	 * These pages may be accessed from within the guest partition only in
+	 * CoCo VMs. Neither the host partition nor the hypervisor can access
+	 * these pages in that case; they are used for exchanging data with the
+	 * paravisor.
+	 */
+	void *para_synic_message_page;
+	void *para_synic_event_page;
 
 	/*
 	 * The page is only used in hv_post_message() for a TDX VM (with the

---

## [8] Roman Kisel — 2025-07-14
*Subject: [PATCH hyperv-next v4 07/16] Drivers: hv: Post messages through the confidential VMBus if available*

When the confidential VMBus is available, the guest should post
messages to the paravisor.

Update hv_post_message() to post messages to the paravisor rather than
through GHCB or TD calls.

Signed-off-by: Roman Kisel <romank@linux.microsoft.com>
---
 drivers/hv/hv.c | 11 ++++++++++-
 1 file changed, 10 insertions(+), 1 deletion(-)

diff --git a/drivers/hv/hv.c b/drivers/hv/hv.c
index e9ee0177d765..816f8a14ff63 100644
--- a/drivers/hv/hv.c
+++ b/drivers/hv/hv.c
@@ -74,7 +74,11 @@ int hv_post_message(union hv_connection_id connection_id,
 	aligned_msg->payload_size = payload_size;
 	memcpy((void *)aligned_msg->payload, payload, payload_size);
 
-	if (ms_hyperv.paravisor_present) {
+	if (ms_hyperv.paravisor_present && !vmbus_is_confidential()) {
+		/*
+		 * If the VMBus isn't confidential, use the CoCo-specific
+		 * mechanism to communicate with the hypervisor.
+		 */
 		if (hv_isolation_type_tdx())
 			status = hv_tdx_hypercall(HVCALL_POST_MESSAGE,
 						  virt_to_phys(aligned_msg), 0);
@@ -85,6 +89,11 @@ int hv_post_message(union hv_connection_id connection_id,
 		else
 			status = HV_STATUS_INVALID_PARAMETER;
 	} else {
+		/*
+		 * If there is no paravisor, this will go to the hypervisor.
+		 * In the Confidential VMBus case, there is the paravisor
+		 * to which this will trap.
+		 */
 		status = hv_do_hypercall(HVCALL_POST_MESSAGE,
 					 aligned_msg, NULL);
 	}

---

## [9] Roman Kisel — 2025-07-14
*Subject: [PATCH hyperv-next v4 08/16] Drivers: hv: remove stale comment*

The comment about the x2v shim is ancient and long since incorrect.

Remove the incorrect comment.

Signed-off-by: Roman Kisel <romank@linux.microsoft.com>
---
 drivers/hv/hv.c | 6 +-----
 1 file changed, 1 insertion(+), 5 deletions(-)

diff --git a/drivers/hv/hv.c b/drivers/hv/hv.c
index 816f8a14ff63..820711e954d1 100644
--- a/drivers/hv/hv.c
+++ b/drivers/hv/hv.c
@@ -266,11 +266,7 @@ void hv_synic_free(void)
 }
 
 /*
- * hv_synic_init - Initialize the Synthetic Interrupt Controller.
- *
- * If it is already initialized by another entity (ie x2v shim), we need to
- * retrieve the initialized message and event pages.  Otherwise, we create and
- * initialize the message and event pages.
+ * hv_synic_enable_regs - Initialize the Synthetic Interrupt Controller.
  */
 void hv_synic_enable_regs(unsigned int cpu)
 {

---

## [10] Roman Kisel — 2025-07-14
*Subject: [PATCH hyperv-next v4 09/16] Drivers: hv: Check message and event pages for non-NULL before iounmap()*

It might happen that some hyp SynIC pages aren't allocated.

Check for that and only then call iounmap().

Signed-off-by: Roman Kisel <romank@linux.microsoft.com>
---
 drivers/hv/hv.c | 12 ++++++++----
 1 file changed, 8 insertions(+), 4 deletions(-)

diff --git a/drivers/hv/hv.c b/drivers/hv/hv.c
index 820711e954d1..a8669843c56e 100644
--- a/drivers/hv/hv.c
+++ b/drivers/hv/hv.c
@@ -367,8 +367,10 @@ void hv_synic_disable_regs(unsigned int cpu)
 	 */
 	simp.simp_enabled = 0;
 	if (ms_hyperv.paravisor_present || hv_root_partition()) {
-		iounmap(hv_cpu->hyp_synic_message_page);
-		hv_cpu->hyp_synic_message_page = NULL;
+		if (hv_cpu->hyp_synic_message_page) {
+			iounmap(hv_cpu->hyp_synic_message_page);
+			hv_cpu->hyp_synic_message_page = NULL;
+		}
 	} else {
 		simp.base_simp_gpa = 0;
 	}
@@ -379,8 +381,10 @@ void hv_synic_disable_regs(unsigned int cpu)
 	siefp.siefp_enabled = 0;
 
 	if (ms_hyperv.paravisor_present || hv_root_partition()) {
-		iounmap(hv_cpu->hyp_synic_event_page);
-		hv_cpu->hyp_synic_event_page = NULL;
+		if (hv_cpu->hyp_synic_event_page) {
+			iounmap(hv_cpu->hyp_synic_event_page);
+			hv_cpu->hyp_synic_event_page = NULL;
+		}
 	} else {
 		siefp.base_siefp_gpa = 0;
 	}

---

## [11] Roman Kisel — 2025-07-14
*Subject: [PATCH hyperv-next v4 10/16] Drivers: hv: Rename the SynIC enable and disable routines*

The confidential VMBus requires support for the both hypervisor
facing SynIC and the paravisor one.

Rename the functions that enable and disable SynIC with the
hypervisor. No functional changes.

Signed-off-by: Roman Kisel <romank@linux.microsoft.com>
---
 drivers/hv/channel_mgmt.c |  2 +-
 drivers/hv/hv.c           | 11 ++++++-----
 drivers/hv/hyperv_vmbus.h |  4 ++--
 drivers/hv/vmbus_drv.c    |  6 +++---
 4 files changed, 12 insertions(+), 11 deletions(-)

diff --git a/drivers/hv/channel_mgmt.c b/drivers/hv/channel_mgmt.c
index 6f87220e2ca3..ca2fe10c110a 100644
--- a/drivers/hv/channel_mgmt.c
+++ b/drivers/hv/channel_mgmt.c
@@ -845,7 +845,7 @@ static void vmbus_wait_for_unload(void)
 			/*
 			 * In a CoCo VM the hyp_synic_message_page is not allocated
 			 * in hv_synic_alloc(). Instead it is set/cleared in
-			 * hv_synic_enable_regs() and hv_synic_disable_regs()
+			 * hv_hyp_synic_enable_regs() and hv_hyp_synic_disable_regs()
 			 * such that it is set only when the CPU is online. If
 			 * not all present CPUs are online, the message page
 			 * might be NULL, so skip such CPUs.
diff --git a/drivers/hv/hv.c b/drivers/hv/hv.c
index a8669843c56e..94a81bb3c8c7 100644
--- a/drivers/hv/hv.c
+++ b/drivers/hv/hv.c
@@ -266,9 +266,10 @@ void hv_synic_free(void)
 }
 
 /*
- * hv_synic_enable_regs - Initialize the Synthetic Interrupt Controller.
+ * hv_hyp_synic_enable_regs - Initialize the Synthetic Interrupt Controller
+ * with the hypervisor.
  */
-void hv_synic_enable_regs(unsigned int cpu)
+void hv_hyp_synic_enable_regs(unsigned int cpu)
 {
 	struct hv_per_cpu_context *hv_cpu =
 		per_cpu_ptr(hv_context.cpu_context, cpu);
@@ -334,14 +335,14 @@ void hv_synic_enable_regs(unsigned int cpu)
 
 int hv_synic_init(unsigned int cpu)
 {
-	hv_synic_enable_regs(cpu);
+	hv_hyp_synic_enable_regs(cpu);
 
 	hv_stimer_legacy_init(cpu, VMBUS_MESSAGE_SINT);
 
 	return 0;
 }
 
-void hv_synic_disable_regs(unsigned int cpu)
+void hv_hyp_synic_disable_regs(unsigned int cpu)
 {
 	struct hv_per_cpu_context *hv_cpu =
 		per_cpu_ptr(hv_context.cpu_context, cpu);
@@ -528,7 +529,7 @@ int hv_synic_cleanup(unsigned int cpu)
 always_cleanup:
 	hv_stimer_legacy_cleanup(cpu);
 
-	hv_synic_disable_regs(cpu);
+	hv_hyp_synic_disable_regs(cpu);
 
 	return ret;
 }
diff --git a/drivers/hv/hyperv_vmbus.h b/drivers/hv/hyperv_vmbus.h
index 16b5cf1bca19..2873703d08a9 100644
--- a/drivers/hv/hyperv_vmbus.h
+++ b/drivers/hv/hyperv_vmbus.h
@@ -189,10 +189,10 @@ extern int hv_synic_alloc(void);
 
 extern void hv_synic_free(void);
 
-extern void hv_synic_enable_regs(unsigned int cpu);
+extern void hv_hyp_synic_enable_regs(unsigned int cpu);
 extern int hv_synic_init(unsigned int cpu);
 
-extern void hv_synic_disable_regs(unsigned int cpu);
+extern void hv_hyp_synic_disable_regs(unsigned int cpu);
 extern int hv_synic_cleanup(unsigned int cpu);
 
 /* Interface */
diff --git a/drivers/hv/vmbus_drv.c b/drivers/hv/vmbus_drv.c
index 72940a64b0b6..13aca5abc7d8 100644
--- a/drivers/hv/vmbus_drv.c
+++ b/drivers/hv/vmbus_drv.c
@@ -2809,7 +2809,7 @@ static void hv_crash_handler(struct pt_regs *regs)
 	 */
 	cpu = smp_processor_id();
 	hv_stimer_cleanup(cpu);
-	hv_synic_disable_regs(cpu);
+	hv_hyp_synic_disable_regs(cpu);
 };
 
 static int hv_synic_suspend(void)
@@ -2834,14 +2834,14 @@ static int hv_synic_suspend(void)
 	 * interrupts-disabled context.
 	 */
 
-	hv_synic_disable_regs(0);
+	hv_hyp_synic_disable_regs(0);
 
 	return 0;
 }
 
 static void hv_synic_resume(void)
 {
-	hv_synic_enable_regs(0);
+	hv_hyp_synic_enable_regs(0);
 
 	/*
 	 * Note: we don't need to call hv_stimer_init(0), because the timer

---

## [12] Roman Kisel — 2025-07-14
*Subject: [PATCH hyperv-next v4 11/16] Drivers: hv: Functions for setting up and tearing down the paravisor SynIC*

The confidential VMBus runs with the paravisor SynIC and requires
configuring it with the paravisor.

Add the functions for configuring the paravisor SynIC. Update
overall SynIC initialization logic to initialize the SynIC if it
is present. Finally, break out SynIC interrupt enable/disable
code into separate functions so that SynIC interrupts can be
enabled or disabled via the paravisor instead of the hypervisor
if the paravisor SynIC is present.

Signed-off-by: Roman Kisel <romank@linux.microsoft.com>
---
 drivers/hv/hv.c | 197 +++++++++++++++++++++++++++++++++++++++++++++---
 1 file changed, 185 insertions(+), 12 deletions(-)

diff --git a/drivers/hv/hv.c b/drivers/hv/hv.c
index 94a81bb3c8c7..9d85d5e62968 100644
--- a/drivers/hv/hv.c
+++ b/drivers/hv/hv.c
@@ -276,9 +276,8 @@ void hv_hyp_synic_enable_regs(unsigned int cpu)
 	union hv_synic_simp simp;
 	union hv_synic_siefp siefp;
 	union hv_synic_sint shared_sint;
-	union hv_synic_scontrol sctrl;
 
-	/* Setup the Synic's message page */
+	/* Setup the Synic's message page with the hypervisor. */
 	simp.as_uint64 = hv_get_msr(HV_MSR_SIMP);
 	simp.simp_enabled = 1;
 
@@ -297,7 +296,7 @@ void hv_hyp_synic_enable_regs(unsigned int cpu)
 
 	hv_set_msr(HV_MSR_SIMP, simp.as_uint64);
 
-	/* Setup the Synic's event page */
+	/* Setup the Synic's event page with the hypervisor. */
 	siefp.as_uint64 = hv_get_msr(HV_MSR_SIEFP);
 	siefp.siefp_enabled = 1;
 
@@ -325,6 +324,11 @@ void hv_hyp_synic_enable_regs(unsigned int cpu)
 	shared_sint.masked = false;
 	shared_sint.auto_eoi = hv_recommend_using_aeoi();
 	hv_set_msr(HV_MSR_SINT0 + VMBUS_MESSAGE_SINT, shared_sint.as_uint64);
+}
+
+static void hv_hyp_synic_enable_interrupts(void)
+{
+	union hv_synic_scontrol sctrl;
 
 	/* Enable the global synic bit */
 	sctrl.as_uint64 = hv_get_msr(HV_MSR_SCONTROL);
@@ -333,13 +337,100 @@ void hv_hyp_synic_enable_regs(unsigned int cpu)
 	hv_set_msr(HV_MSR_SCONTROL, sctrl.as_uint64);
 }
 
+/*
+ * The paravisor might not support proxying SynIC, and this
+ * function may fail.
+ */
+static int hv_para_synic_enable_regs(unsigned int cpu)
+{
+	int err;
+	union hv_synic_simp simp;
+	union hv_synic_siefp siefp;
+	struct hv_per_cpu_context *hv_cpu
+		= per_cpu_ptr(hv_context.cpu_context, cpu);
+
+	/* Setup the Synic's message page with the paravisor. */
+	err = hv_para_get_synic_register(HV_MSR_SIMP, &simp.as_uint64);
+	if (err)
+		return err;
+	simp.simp_enabled = 1;
+	simp.base_simp_gpa = virt_to_phys(hv_cpu->para_synic_message_page)
+			>> HV_HYP_PAGE_SHIFT;
+	err = hv_para_set_synic_register(HV_MSR_SIMP, simp.as_uint64);
+	if (err)
+		return err;
+
+	/* Setup the Synic's event page with the paravisor. */
+	err = hv_para_get_synic_register(HV_MSR_SIEFP, &siefp.as_uint64);
+	if (err)
+		return err;
+	siefp.siefp_enabled = 1;
+	siefp.base_siefp_gpa = virt_to_phys(hv_cpu->para_synic_event_page)
+			>> HV_HYP_PAGE_SHIFT;
+	return hv_para_set_synic_register(HV_MSR_SIEFP, siefp.as_uint64);
+}
+
+static int hv_para_synic_enable_interrupts(void)
+{
+	union hv_synic_scontrol sctrl;
+	int err;
+
+	/* Enable the global synic bit */
+	err = hv_para_get_synic_register(HV_MSR_SCONTROL, &sctrl.as_uint64);
+	if (err)
+		return err;
+	sctrl.enable = 1;
+
+	return hv_para_set_synic_register(HV_MSR_SCONTROL, sctrl.as_uint64);
+}
+
 int hv_synic_init(unsigned int cpu)
 {
+	int err;
+
+	/*
+	 * The paravisor may not support the confidential VMBus,
+	 * check on that first.
+	 */
+	if (vmbus_is_confidential()) {
+		err = hv_para_synic_enable_regs(cpu);
+		if (err)
+			goto fail;
+	}
+
+	/*
+	 * The SINT is set in hv_hyperv_synic_enable_regs() by calling
+	 * hv_set_msr(). hv_set_msr() in turn has special case code for the
+	 * SINT MSRs that write to the hypervisor version of the MSR *and*
+	 * the paravisor version of the MSR (but *without* the proxy bit when
+	 * VMBus is confidential). Then the code above enables interrupts
+	 * via the paravisor if VMBus is confidential, and otherwise via the
+	 * hypervisor.
+	 */
+
 	hv_hyp_synic_enable_regs(cpu);
+	if (vmbus_is_confidential()) {
+		err = hv_para_synic_enable_interrupts();
+		if (err)
+			goto fail;
+	} else
+		hv_hyp_synic_enable_interrupts();
 
 	hv_stimer_legacy_init(cpu, VMBUS_MESSAGE_SINT);
 
 	return 0;
+
+fail:
+	/*
+	 * The failure may only come from enabling the paravisor SynIC.
+	 * That in turn means that the confidential VMBus cannot be used
+	 * which is not an error: the setup will be re-tried with the
+	 * non-confidential VMBus.
+	 *
+	 * We also don't bother attempting to reset the paravisor registers
+	 * as something isn't working there anyway.
+	 */
+	return err;
 }
 
 void hv_hyp_synic_disable_regs(unsigned int cpu)
@@ -349,7 +440,6 @@ void hv_hyp_synic_disable_regs(unsigned int cpu)
 	union hv_synic_sint shared_sint;
 	union hv_synic_simp simp;
 	union hv_synic_siefp siefp;
-	union hv_synic_scontrol sctrl;
 
 	shared_sint.as_uint64 = hv_get_msr(HV_MSR_SINT0 + VMBUS_MESSAGE_SINT);
 
@@ -361,7 +451,7 @@ void hv_hyp_synic_disable_regs(unsigned int cpu)
 
 	simp.as_uint64 = hv_get_msr(HV_MSR_SIMP);
 	/*
-	 * In Isolation VM, sim and sief pages are allocated by
+	 * In Isolation VM, simp and sief pages are allocated by
 	 * paravisor. These pages also will be used by kdump
 	 * kernel. So just reset enable bit here and keep page
 	 * addresses.
@@ -391,14 +481,64 @@ void hv_hyp_synic_disable_regs(unsigned int cpu)
 	}
 
 	hv_set_msr(HV_MSR_SIEFP, siefp.as_uint64);
+}
+
+static void hv_hyp_synic_disable_interrupts(void)
+{
+	union hv_synic_scontrol sctrl;
 
 	/* Disable the global synic bit */
 	sctrl.as_uint64 = hv_get_msr(HV_MSR_SCONTROL);
 	sctrl.enable = 0;
 	hv_set_msr(HV_MSR_SCONTROL, sctrl.as_uint64);
+}
 
-	if (vmbus_irq != -1)
-		disable_percpu_irq(vmbus_irq);
+static void hv_para_synic_disable_regs(unsigned int cpu)
+{
+	/*
+	 * When a get/set register error is encountered, the function
+	 * returns as the paravisor may not support these registers.
+	 */
+	int err;
+	union hv_synic_simp simp;
+	union hv_synic_siefp siefp;
+
+	/*
+	 * Don't deallocate memory here as the function is called on
+	 * CPU online and offline operations. The guest will find
+	 * itself without means of communication when resumed.
+	 */
+
+	/* Disable SynIC's message page in the paravisor. */
+	err = hv_para_get_synic_register(HV_MSR_SIMP, &simp.as_uint64);
+	if (err)
+		return;
+	simp.simp_enabled = 0;
+
+	err = hv_para_set_synic_register(HV_MSR_SIMP, simp.as_uint64);
+	if (err)
+		return;
+
+	/* Disable SynIC's event page in the paravisor. */
+	err = hv_para_get_synic_register(HV_MSR_SIEFP, &siefp.as_uint64);
+	if (err)
+		return;
+	siefp.siefp_enabled = 0;
+
+	hv_para_set_synic_register(HV_MSR_SIEFP, siefp.as_uint64);
+}
+
+static void hv_para_synic_disable_interrupts(void)
+{
+	union hv_synic_scontrol sctrl;
+	int err;
+
+	/* Disable the global synic bit */
+	err = hv_para_get_synic_register(HV_MSR_SCONTROL, &sctrl.as_uint64);
+	if (err)
+		return;
+	sctrl.enable = 0;
+	hv_para_set_synic_register(HV_MSR_SCONTROL, sctrl.as_uint64);
 }
 
 #define HV_MAX_TRIES 3
@@ -411,16 +551,18 @@ void hv_hyp_synic_disable_regs(unsigned int cpu)
  * that the normal interrupt handling mechanism will find and process the channel interrupt
  * "very soon", and in the process clear the bit.
  */
-static bool hv_synic_event_pending(void)
+static bool __hv_synic_event_pending(union hv_synic_event_flags *event, int sint)
 {
-	struct hv_per_cpu_context *hv_cpu = this_cpu_ptr(hv_context.cpu_context);
-	union hv_synic_event_flags *event =
-		(union hv_synic_event_flags *)hv_cpu->hyp_synic_event_page + VMBUS_MESSAGE_SINT;
-	unsigned long *recv_int_page = event->flags; /* assumes VMBus version >= VERSION_WIN8 */
+	unsigned long *recv_int_page;
 	bool pending;
 	u32 relid;
 	int tries = 0;
 
+	if (!event)
+		return false;
+
+	event += sint;
+	recv_int_page = event->flags; /* assumes VMBus version >= VERSION_WIN8 */
 retry:
 	pending = false;
 	for_each_set_bit(relid, recv_int_page, HV_EVENT_FLAGS_COUNT) {
@@ -437,6 +579,17 @@ static bool hv_synic_event_pending(void)
 	return pending;
 }
 
+static bool hv_synic_event_pending(void)
+{
+	struct hv_per_cpu_context *hv_cpu = this_cpu_ptr(hv_context.cpu_context);
+	union hv_synic_event_flags *hyp_synic_event_page = hv_cpu->hyp_synic_event_page;
+	union hv_synic_event_flags *para_synic_event_page = hv_cpu->para_synic_event_page;
+
+	return
+		__hv_synic_event_pending(hyp_synic_event_page, VMBUS_MESSAGE_SINT) ||
+		__hv_synic_event_pending(para_synic_event_page, VMBUS_MESSAGE_SINT);
+}
+
 static int hv_pick_new_cpu(struct vmbus_channel *channel)
 {
 	int ret = -EBUSY;
@@ -529,7 +682,27 @@ int hv_synic_cleanup(unsigned int cpu)
 always_cleanup:
 	hv_stimer_legacy_cleanup(cpu);
 
+	/*
+	 * First, disable the event and message pages
+	 * used for communicating with the host, and then
+	 * disable the host interrupts if VMBus is not
+	 * confidential.
+	 */
 	hv_hyp_synic_disable_regs(cpu);
+	if (!vmbus_is_confidential())
+		hv_hyp_synic_disable_interrupts();
+
+	/*
+	 * Perform the same steps for the Confidential VMBus.
+	 * The sequencing provides the gurantee that no data
+	 * may be posted for processing before disabling interrupts.
+	 */
+	if (vmbus_is_confidential()) {
+		hv_para_synic_disable_regs(cpu);
+		hv_para_synic_disable_interrupts();
+	}
+	if (vmbus_irq != -1)
+		disable_percpu_irq(vmbus_irq);
 
 	return ret;
 }

---

## [13] Roman Kisel — 2025-07-14
*Subject: [PATCH hyperv-next v4 12/16] Drivers: hv: Allocate encrypted buffers when requested*

Confidential VMBus is built around using buffers not shared with
the host.

Support allocating encrypted buffers when requested.

Signed-off-by: Roman Kisel <romank@linux.microsoft.com>
---
 drivers/hv/channel.c      | 49 +++++++++++++++++++++++----------------
 drivers/hv/hyperv_vmbus.h |  3 ++-
 drivers/hv/ring_buffer.c  |  5 ++--
 3 files changed, 34 insertions(+), 23 deletions(-)

diff --git a/drivers/hv/channel.c b/drivers/hv/channel.c
index 35f26fa1ffe7..051eeba800f2 100644
--- a/drivers/hv/channel.c
+++ b/drivers/hv/channel.c
@@ -443,20 +443,23 @@ static int __vmbus_establish_gpadl(struct vmbus_channel *channel,
 		return ret;
 	}
 
-	/*
-	 * Set the "decrypted" flag to true for the set_memory_decrypted()
-	 * success case. In the failure case, the encryption state of the
-	 * memory is unknown. Leave "decrypted" as true to ensure the
-	 * memory will be leaked instead of going back on the free list.
-	 */
-	gpadl->decrypted = true;
-	ret = set_memory_decrypted((unsigned long)kbuffer,
-				   PFN_UP(size));
-	if (ret) {
-		dev_warn(&channel->device_obj->device,
-			 "Failed to set host visibility for new GPADL %d.\n",
-			 ret);
-		return ret;
+	gpadl->decrypted = !((channel->co_external_memory && type == HV_GPADL_BUFFER) ||
+		(channel->co_ring_buffer && type == HV_GPADL_RING));
+	if (gpadl->decrypted) {
+		/*
+		 * The "decrypted" flag being true assumes that set_memory_decrypted() succeeds.
+		 * But if it fails, the encryption state of the memory is unknown. In that case,
+		 * leave "decrypted" as true to ensure the memory is leaked instead of going back
+		 * on the free list.
+		 */
+		ret = set_memory_decrypted((unsigned long)kbuffer,
+					PFN_UP(size));
+		if (ret) {
+			dev_warn(&channel->device_obj->device,
+				"Failed to set host visibility for new GPADL %d.\n",
+				ret);
+			return ret;
+		}
 	}
 
 	init_completion(&msginfo->waitevent);
@@ -544,8 +547,10 @@ static int __vmbus_establish_gpadl(struct vmbus_channel *channel,
 		 * left as true so the memory is leaked instead of being
 		 * put back on the free list.
 		 */
-		if (!set_memory_encrypted((unsigned long)kbuffer, PFN_UP(size)))
-			gpadl->decrypted = false;
+		if (gpadl->decrypted) {
+			if (!set_memory_encrypted((unsigned long)kbuffer, PFN_UP(size)))
+				gpadl->decrypted = false;
+		}
 	}
 
 	return ret;
@@ -676,12 +681,13 @@ static int __vmbus_open(struct vmbus_channel *newchannel,
 		goto error_clean_ring;
 
 	err = hv_ringbuffer_init(&newchannel->outbound,
-				 page, send_pages, 0);
+				 page, send_pages, 0, newchannel->co_ring_buffer);
 	if (err)
 		goto error_free_gpadl;
 
 	err = hv_ringbuffer_init(&newchannel->inbound, &page[send_pages],
-				 recv_pages, newchannel->max_pkt_size);
+				 recv_pages, newchannel->max_pkt_size,
+				 newchannel->co_ring_buffer);
 	if (err)
 		goto error_free_gpadl;
 
@@ -862,8 +868,11 @@ int vmbus_teardown_gpadl(struct vmbus_channel *channel, struct vmbus_gpadl *gpad
 
 	kfree(info);
 
-	ret = set_memory_encrypted((unsigned long)gpadl->buffer,
-				   PFN_UP(gpadl->size));
+	if (gpadl->decrypted)
+		ret = set_memory_encrypted((unsigned long)gpadl->buffer,
+					PFN_UP(gpadl->size));
+	else
+		ret = 0;
 	if (ret)
 		pr_warn("Fail to set mem host visibility in GPADL teardown %d.\n", ret);
 
diff --git a/drivers/hv/hyperv_vmbus.h b/drivers/hv/hyperv_vmbus.h
index 2873703d08a9..beae68a70939 100644
--- a/drivers/hv/hyperv_vmbus.h
+++ b/drivers/hv/hyperv_vmbus.h
@@ -200,7 +200,8 @@ extern int hv_synic_cleanup(unsigned int cpu);
 void hv_ringbuffer_pre_init(struct vmbus_channel *channel);
 
 int hv_ringbuffer_init(struct hv_ring_buffer_info *ring_info,
-		       struct page *pages, u32 pagecnt, u32 max_pkt_size);
+		       struct page *pages, u32 pagecnt, u32 max_pkt_size,
+			   bool confidential);
 
 void hv_ringbuffer_cleanup(struct hv_ring_buffer_info *ring_info);
 
diff --git a/drivers/hv/ring_buffer.c b/drivers/hv/ring_buffer.c
index 3c9b02471760..05c2cd42fc75 100644
--- a/drivers/hv/ring_buffer.c
+++ b/drivers/hv/ring_buffer.c
@@ -183,7 +183,8 @@ void hv_ringbuffer_pre_init(struct vmbus_channel *channel)
 
 /* Initialize the ring buffer. */
 int hv_ringbuffer_init(struct hv_ring_buffer_info *ring_info,
-		       struct page *pages, u32 page_cnt, u32 max_pkt_size)
+		       struct page *pages, u32 page_cnt, u32 max_pkt_size,
+			   bool confidential)
 {
 	struct page **pages_wraparound;
 	int i;
@@ -207,7 +208,7 @@ int hv_ringbuffer_init(struct hv_ring_buffer_info *ring_info,
 
 	ring_info->ring_buffer = (struct hv_ring_buffer *)
 		vmap(pages_wraparound, page_cnt * 2 - 1, VM_MAP,
-			pgprot_decrypted(PAGE_KERNEL));
+			confidential ? PAGE_KERNEL : pgprot_decrypted(PAGE_KERNEL));
 
 	kfree(pages_wraparound);
 	if (!ring_info->ring_buffer)

---

## [14] Roman Kisel — 2025-07-14
*Subject: [PATCH hyperv-next v4 13/16] Drivers: hv: Free msginfo when the buffer fails to decrypt*

The early failure path in __vmbus_establish_gpadl() doesn't deallocate
msginfo if the buffer fails to decrypt.

Fix the leak by breaking out the cleanup code into a separate function
and calling it where required.

Fixes: d4dccf353db80 ("Drivers: hv: vmbus: Mark vmbus ring buffer visible to host in Isolation VM")
Reported-by: Michael Kelly <mkhlinux@outlook.com>
Closes: https://lore.kernel.org/linux-hyperv/SN6PR02MB41573796F9787F67E0E97049D472A@SN6PR02MB4157.namprd02.prod.outlook.com
Signed-off-by: Roman Kisel <romank@linux.microsoft.com>
---
 drivers/hv/channel.c | 32 ++++++++++++++++++++++----------
 1 file changed, 22 insertions(+), 10 deletions(-)

diff --git a/drivers/hv/channel.c b/drivers/hv/channel.c
index 051eeba800f2..0eb300b940db 100644
--- a/drivers/hv/channel.c
+++ b/drivers/hv/channel.c
@@ -409,6 +409,25 @@ static int create_gpadl_header(enum hv_gpadl_type type, void *kbuffer,
 	return 0;
 }
 
+static void vmbus_free_channel_msginfo(struct vmbus_channel_msginfo *msginfo)
+{
+	unsigned long flags;
+	struct vmbus_channel_msginfo *submsginfo, *tmp;
+
+	if (!msginfo)
+		return;
+
+	spin_lock_irqsave(&vmbus_connection.channelmsg_lock, flags);
+	list_del(&msginfo->msglistentry);
+	spin_unlock_irqrestore(&vmbus_connection.channelmsg_lock, flags);
+	list_for_each_entry_safe(submsginfo, tmp, &msginfo->submsglist,
+				 msglistentry) {
+		kfree(submsginfo);
+	}
+
+	kfree(msginfo);
+}
+
 /*
  * __vmbus_establish_gpadl - Establish a GPADL for a buffer or ringbuffer
  *
@@ -428,7 +447,7 @@ static int __vmbus_establish_gpadl(struct vmbus_channel *channel,
 	struct vmbus_channel_gpadl_header *gpadlmsg;
 	struct vmbus_channel_gpadl_body *gpadl_body;
 	struct vmbus_channel_msginfo *msginfo = NULL;
-	struct vmbus_channel_msginfo *submsginfo, *tmp;
+	struct vmbus_channel_msginfo *submsginfo;
 	struct list_head *curr;
 	u32 next_gpadl_handle;
 	unsigned long flags;
@@ -458,6 +477,7 @@ static int __vmbus_establish_gpadl(struct vmbus_channel *channel,
 			dev_warn(&channel->device_obj->device,
 				"Failed to set host visibility for new GPADL %d.\n",
 				ret);
+			vmbus_free_channel_msginfo(msginfo);
 			return ret;
 		}
 	}
@@ -531,15 +551,7 @@ static int __vmbus_establish_gpadl(struct vmbus_channel *channel,
 
 
 cleanup:
-	spin_lock_irqsave(&vmbus_connection.channelmsg_lock, flags);
-	list_del(&msginfo->msglistentry);
-	spin_unlock_irqrestore(&vmbus_connection.channelmsg_lock, flags);
-	list_for_each_entry_safe(submsginfo, tmp, &msginfo->submsglist,
-				 msglistentry) {
-		kfree(submsginfo);
-	}
-
-	kfree(msginfo);
+	vmbus_free_channel_msginfo(msginfo);
 
 	if (ret) {
 		/*

---

## [15] Roman Kisel — 2025-07-14
*Subject: [PATCH hyperv-next v4 14/16] Drivers: hv: Support confidential VMBus channels*

To make use of Confidential VMBus channels, initialize the
co_ring_buffers and co_external_memory fields of the channel
structure.

Advertise support upon negotiating the version and compute
values for those fields and initialize them.

Signed-off-by: Roman Kisel <romank@linux.microsoft.com>
---
 drivers/hv/channel_mgmt.c | 19 +++++++++++++++++++
 drivers/hv/connection.c   |  3 +++
 2 files changed, 22 insertions(+)

diff --git a/drivers/hv/channel_mgmt.c b/drivers/hv/channel_mgmt.c
index ca2fe10c110a..6ae44eab1626 100644
--- a/drivers/hv/channel_mgmt.c
+++ b/drivers/hv/channel_mgmt.c
@@ -1021,6 +1021,7 @@ static void vmbus_onoffer(struct vmbus_channel_message_header *hdr)
 	struct vmbus_channel_offer_channel *offer;
 	struct vmbus_channel *oldchannel, *newchannel;
 	size_t offer_sz;
+	bool co_ring_buffer, co_external_memory;
 
 	offer = (struct vmbus_channel_offer_channel *)hdr;
 
@@ -1033,6 +1034,22 @@ static void vmbus_onoffer(struct vmbus_channel_message_header *hdr)
 		return;
 	}
 
+	co_ring_buffer = is_co_ring_buffer(offer);
+	co_external_memory = is_co_external_memory(offer);
+	if (!co_ring_buffer && co_external_memory) {
+		pr_err("Invalid offer relid=%d: the ring buffer isn't encrypted\n",
+			offer->child_relid);
+		return;
+	}
+	if (co_ring_buffer || co_external_memory) {
+		if (vmbus_proto_version < VERSION_WIN10_V6_0 || !vmbus_is_confidential()) {
+			pr_err("Invalid offer relid=%d: no support for confidential VMBus\n",
+				offer->child_relid);
+			atomic_dec(&vmbus_connection.offer_in_progress);
+			return;
+		}
+	}
+
 	oldchannel = find_primary_channel_by_offer(offer);
 
 	if (oldchannel != NULL) {
@@ -1111,6 +1128,8 @@ static void vmbus_onoffer(struct vmbus_channel_message_header *hdr)
 		pr_err("Unable to allocate channel object\n");
 		return;
 	}
+	newchannel->co_ring_buffer = co_ring_buffer;
+	newchannel->co_external_memory = co_external_memory;
 
 	vmbus_setup_channel_state(newchannel, offer);
 
diff --git a/drivers/hv/connection.c b/drivers/hv/connection.c
index be490c598785..eeb472019d69 100644
--- a/drivers/hv/connection.c
+++ b/drivers/hv/connection.c
@@ -105,6 +105,9 @@ int vmbus_negotiate_version(struct vmbus_channel_msginfo *msginfo, u32 version)
 		vmbus_connection.msg_conn_id = VMBUS_MESSAGE_CONNECTION_ID;
 	}
 
+	if (vmbus_is_confidential() && version >= VERSION_WIN10_V6_0)
+		msg->feature_flags = VMBUS_FEATURE_FLAG_CONFIDENTIAL_CHANNELS;
+
 	/*
 	 * shared_gpa_boundary is zero in non-SNP VMs, so it's safe to always
 	 * bitwise OR it

---

## [16] Roman Kisel — 2025-07-14
*Subject: [PATCH hyperv-next v4 15/16] Drivers: hv: Support establishing the confidential VMBus connection*

To establish the confidential VMBus connection the CoCo VM guest
first attempts to connect to the VMBus server run by the paravisor.
If that fails, the guest falls back to the non-confidential VMBus.

Implement that in the VMBus driver initialization.

Signed-off-by: Roman Kisel <romank@linux.microsoft.com>
---
 drivers/hv/vmbus_drv.c | 189 ++++++++++++++++++++++++++++-------------
 1 file changed, 130 insertions(+), 59 deletions(-)

diff --git a/drivers/hv/vmbus_drv.c b/drivers/hv/vmbus_drv.c
index 13aca5abc7d8..53be3157e22c 100644
--- a/drivers/hv/vmbus_drv.c
+++ b/drivers/hv/vmbus_drv.c
@@ -1057,12 +1057,9 @@ static void vmbus_onmessage_work(struct work_struct *work)
 	kfree(ctx);
 }
 
-void vmbus_on_msg_dpc(unsigned long data)
+static void __vmbus_on_msg_dpc(void *message_page_addr)
 {
-	struct hv_per_cpu_context *hv_cpu = (void *)data;
-	void *page_addr = hv_cpu->hyp_synic_message_page;
-	struct hv_message msg_copy, *msg = (struct hv_message *)page_addr +
-				  VMBUS_MESSAGE_SINT;
+	struct hv_message msg_copy, *msg;
 	struct vmbus_channel_message_header *hdr;
 	enum vmbus_channel_message_type msgtype;
 	const struct vmbus_channel_message_table_entry *entry;
@@ -1070,6 +1067,10 @@ void vmbus_on_msg_dpc(unsigned long data)
 	__u8 payload_size;
 	u32 message_type;
 
+	if (!message_page_addr)
+		return;
+	msg = (struct hv_message *)message_page_addr + VMBUS_MESSAGE_SINT;
+
 	/*
 	 * 'enum vmbus_channel_message_type' is supposed to always be 'u32' as
 	 * it is being used in 'struct vmbus_channel_message_header' definition
@@ -1195,6 +1196,14 @@ void vmbus_on_msg_dpc(unsigned long data)
 	vmbus_signal_eom(msg, message_type);
 }
 
+void vmbus_on_msg_dpc(unsigned long data)
+{
+	struct hv_per_cpu_context *hv_cpu = (void *)data;
+
+	__vmbus_on_msg_dpc(hv_cpu->hyp_synic_message_page);
+	__vmbus_on_msg_dpc(hv_cpu->para_synic_message_page);
+}
+
 #ifdef CONFIG_PM_SLEEP
 /*
  * Fake RESCIND_CHANNEL messages to clean up hv_sock channels by force for
@@ -1233,21 +1242,19 @@ static void vmbus_force_channel_rescinded(struct vmbus_channel *channel)
 #endif /* CONFIG_PM_SLEEP */
 
 /*
- * Schedule all channels with events pending
+ * Schedule all channels with events pending.
+ * The event page can be directly checked to get the id of
+ * the channel that has the interrupt pending.
  */
-static void vmbus_chan_sched(struct hv_per_cpu_context *hv_cpu)
+static void vmbus_chan_sched(void *event_page_addr)
 {
 	unsigned long *recv_int_page;
 	u32 maxbits, relid;
+	union hv_synic_event_flags *event;
 
-	/*
-	 * The event page can be directly checked to get the id of
-	 * the channel that has the interrupt pending.
-	 */
-	void *page_addr = hv_cpu->hyp_synic_event_page;
-	union hv_synic_event_flags *event
-		= (union hv_synic_event_flags *)page_addr +
-					 VMBUS_MESSAGE_SINT;
+	if (!event_page_addr)
+		return;
+	event = (union hv_synic_event_flags *)event_page_addr + VMBUS_MESSAGE_SINT;
 
 	maxbits = HV_EVENT_FLAGS_COUNT;
 	recv_int_page = event->flags;
@@ -1255,6 +1262,11 @@ static void vmbus_chan_sched(struct hv_per_cpu_context *hv_cpu)
 	if (unlikely(!recv_int_page))
 		return;
 
+	/*
+	 * Suggested-by: Michael Kelley <mhklinux@outlook.com>
+	 * One possible optimization would be to keep track of the largest relID that's in use,
+	 * and only scan up to that relID.
+	 */
 	for_each_set_bit(relid, recv_int_page, maxbits) {
 		void (*callback_fn)(void *context);
 		struct vmbus_channel *channel;
@@ -1318,26 +1330,35 @@ static void vmbus_chan_sched(struct hv_per_cpu_context *hv_cpu)
 	}
 }
 
-static void vmbus_isr(void)
+static void vmbus_message_sched(struct hv_per_cpu_context *hv_cpu, void *message_page_addr)
 {
-	struct hv_per_cpu_context *hv_cpu
-		= this_cpu_ptr(hv_context.cpu_context);
-	void *page_addr;
 	struct hv_message *msg;
 
-	vmbus_chan_sched(hv_cpu);
-
-	page_addr = hv_cpu->hyp_synic_message_page;
-	msg = (struct hv_message *)page_addr + VMBUS_MESSAGE_SINT;
+	if (!message_page_addr)
+		return;
+	msg = (struct hv_message *)message_page_addr + VMBUS_MESSAGE_SINT;
 
 	/* Check if there are actual msgs to be processed */
 	if (msg->header.message_type != HVMSG_NONE) {
 		if (msg->header.message_type == HVMSG_TIMER_EXPIRED) {
 			hv_stimer0_isr();
 			vmbus_signal_eom(msg, HVMSG_TIMER_EXPIRED);
-		} else
+		} else {
 			tasklet_schedule(&hv_cpu->msg_dpc);
+		}
 	}
+}
+
+static void vmbus_isr(void)
+{
+	struct hv_per_cpu_context *hv_cpu
+		= this_cpu_ptr(hv_context.cpu_context);
+
+	vmbus_chan_sched(hv_cpu->hyp_synic_event_page);
+	vmbus_chan_sched(hv_cpu->para_synic_event_page);
+
+	vmbus_message_sched(hv_cpu, hv_cpu->hyp_synic_message_page);
+	vmbus_message_sched(hv_cpu, hv_cpu->para_synic_message_page);
 
 	add_interrupt_randomness(vmbus_interrupt);
 }
@@ -1355,6 +1376,59 @@ static void vmbus_percpu_work(struct work_struct *work)
 	hv_synic_init(cpu);
 }
 
+static int vmbus_alloc_synic_and_connect(void)
+{
+	int ret, cpu;
+	struct work_struct __percpu *works;
+	int hyperv_cpuhp_online;
+
+	ret = hv_synic_alloc();
+	if (ret < 0)
+		goto err_alloc;
+
+	works = alloc_percpu(struct work_struct);
+	if (!works) {
+		ret = -ENOMEM;
+		goto err_alloc;
+	}
+
+	/*
+	 * Initialize the per-cpu interrupt state and stimer state.
+	 * Then connect to the host.
+	 */
+	cpus_read_lock();
+	for_each_online_cpu(cpu) {
+		struct work_struct *work = per_cpu_ptr(works, cpu);
+
+		INIT_WORK(work, vmbus_percpu_work);
+		schedule_work_on(cpu, work);
+	}
+
+	for_each_online_cpu(cpu)
+		flush_work(per_cpu_ptr(works, cpu));
+
+	/* Register the callbacks for possible CPU online/offline'ing */
+	ret = cpuhp_setup_state_nocalls_cpuslocked(CPUHP_AP_ONLINE_DYN, "hyperv/vmbus:online",
+						   hv_synic_init, hv_synic_cleanup);
+	cpus_read_unlock();
+	free_percpu(works);
+	if (ret < 0)
+		goto err_alloc;
+	hyperv_cpuhp_online = ret;
+
+	ret = vmbus_connect();
+	if (ret)
+		goto err_connect;
+	return 0;
+
+err_connect:
+	cpuhp_remove_state(hyperv_cpuhp_online);
+	return -ENODEV;
+err_alloc:
+	hv_synic_free();
+	return -ENOMEM;
+}
+
 /*
  * vmbus_bus_init -Main vmbus driver initialization routine.
  *
@@ -1365,8 +1439,7 @@ static void vmbus_percpu_work(struct work_struct *work)
  */
 static int vmbus_bus_init(void)
 {
-	int ret, cpu;
-	struct work_struct __percpu *works;
+	int ret;
 
 	ret = hv_init();
 	if (ret != 0) {
@@ -1401,41 +1474,42 @@ static int vmbus_bus_init(void)
 		}
 	}
 
-	ret = hv_synic_alloc();
-	if (ret)
-		goto err_alloc;
-
-	works = alloc_percpu(struct work_struct);
-	if (!works) {
-		ret = -ENOMEM;
-		goto err_alloc;
-	}
-
 	/*
-	 * Initialize the per-cpu interrupt state and stimer state.
-	 * Then connect to the host.
+	 * Attempt to establish the confidential VMBus connection first if this VM is
+	 * a hardware confidential VM, and the paravisor is present.
+	 *
+	 * All scenarios here are:
+	 *	1. No paravisor,
+	 *  2. Paravisor without VMBus relay, no hardware isolation,
+	 *  3. Paravisor without VMBus relay, with hardware isolation,
+	 *  4. Paravisor with VMBus relay, no hardware isolation,
+	 *  5. Paravisor with VMBus relay, with hardware isolation.
+	 *
+	 * In the cloud, scenarios 1, 4, 5 are most common, and outside the cloud,
+	 * scenario 1 should be the most common at the moment. Detecting of the Confidential
+	 * VMBus support below takes that into account running `vmbus_alloc_synic_and_connect()`
+	 * only once (barring any faults not related to VMBus) in these cases. That is true
+	 * for the scenario 2, too, albeit it might be not as feature-rich as 1, 4, 5.
+	 *
+	 * However, the code will be doing much more work in scenario 3 where it will have to
+	 * first initialize lots of structures for every CPU only to likely tear them down later
+	 * and start again, now without attempting to use Confidential VMBus, thus taking a
+	 * performance hit. Such systems are rather uncomoon today, don't support more than
+	 * ~300 CPUs, and are rarely used with many dozens of CPUs. As the time goes on, that
+	 * will be even less common. Hence, the preference is to not specialize the code for
+	 * that scenario.
 	 */
-	cpus_read_lock();
-	for_each_online_cpu(cpu) {
-		struct work_struct *work = per_cpu_ptr(works, cpu);
+	ret = -ENODEV;
+	if (ms_hyperv.paravisor_present && (hv_isolation_type_tdx() || hv_isolation_type_snp())) {
+		is_confidential = true;
+		ret = vmbus_alloc_synic_and_connect();
+		is_confidential = !ret;
 
-		INIT_WORK(work, vmbus_percpu_work);
-		schedule_work_on(cpu, work);
+		pr_info("VMBus is confidential: %d\n", is_confidential);
 	}
 
-	for_each_online_cpu(cpu)
-		flush_work(per_cpu_ptr(works, cpu));
-
-	/* Register the callbacks for possible CPU online/offline'ing */
-	ret = cpuhp_setup_state_nocalls_cpuslocked(CPUHP_AP_ONLINE_DYN, "hyperv/vmbus:online",
-						   hv_synic_init, hv_synic_cleanup);
-	cpus_read_unlock();
-	free_percpu(works);
-	if (ret < 0)
-		goto err_alloc;
-	hyperv_cpuhp_online = ret;
-
-	ret = vmbus_connect();
+	if (!is_confidential)
+		ret = vmbus_alloc_synic_and_connect();
 	if (ret)
 		goto err_connect;
 
@@ -1451,9 +1525,6 @@ static int vmbus_bus_init(void)
 	return 0;
 
 err_connect:
-	cpuhp_remove_state(hyperv_cpuhp_online);
-err_alloc:
-	hv_synic_free();
 	if (vmbus_irq == -1) {
 		hv_remove_vmbus_handler();
 	} else {

---

## [17] Roman Kisel — 2025-07-14
*Subject: [PATCH hyperv-next v4 16/16] Drivers: hv: Set the default VMBus version to 6.0*

The confidential VMBus is supported by the protocol version
6.0 onwards.

Attempt to establish the VMBus 6.0 connection thus enabling
the confidential VMBus features when available.

Signed-off-by: Roman Kisel <romank@linux.microsoft.com>
---
 drivers/hv/connection.c | 3 ++-
 1 file changed, 2 insertions(+), 1 deletion(-)

diff --git a/drivers/hv/connection.c b/drivers/hv/connection.c
index eeb472019d69..7cd43463f969 100644
--- a/drivers/hv/connection.c
+++ b/drivers/hv/connection.c
@@ -51,6 +51,7 @@ EXPORT_SYMBOL_GPL(vmbus_proto_version);
  * Linux guests and are not listed.
  */
 static __u32 vmbus_versions[] = {
+	VERSION_WIN10_V6_0,
 	VERSION_WIN10_V5_3,
 	VERSION_WIN10_V5_2,
 	VERSION_WIN10_V5_1,
@@ -65,7 +66,7 @@ static __u32 vmbus_versions[] = {
  * Maximal VMBus protocol version guests can negotiate.  Useful to cap the
  * VMBus version for testing and debugging purpose.
  */
-static uint max_version = VERSION_WIN10_V5_3;
+static uint max_version = VERSION_WIN10_V6_0;
 
 module_param(max_version, uint, S_IRUGO);
 MODULE_PARM_DESC(max_version,

---

## [18] kernel test robot — 2025-07-15
*Subject: Re: [PATCH hyperv-next v4 03/16] arch: hyperv: Get/set SynIC
 synth.registers via paravisor*

Hi Roman,

kernel test robot noticed the following build errors:

[auto build test ERROR on d9016a249be5316ec2476f9947356711e70a16ec]

url:    https://github.com/intel-lab-lkp/linux/commits/Roman-Kisel/Documentation-hyperv-Confidential-VMBus/20250715-062125
base:   d9016a249be5316ec2476f9947356711e70a16ec
patch link:    https://lore.kernel.org/r/20250714221545.5615-4-romank%40linux.microsoft.com
patch subject: [PATCH hyperv-next v4 03/16] arch: hyperv: Get/set SynIC synth.registers via paravisor
config: i386-buildonly-randconfig-005-20250715 (https://download.01.org/0day-ci/archive/20250715/202507152017.8UNXIbRJ-lkp@intel.com/config)
compiler: clang version 20.1.8 (https://github.com/llvm/llvm-project 87f0227cb60147a26a1eeb4fb06e3b505e9c7261)
reproduce (this is a W=1 build): (https://download.01.org/0day-ci/archive/20250715/202507152017.8UNXIbRJ-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202507152017.8UNXIbRJ-lkp@intel.com/

All errors (new ones prefixed by >>):

   In file included from arch/x86/kvm/vmx/main.c:5:
   In file included from arch/x86/kvm/vmx/vmx.h:16:
   In file included from arch/x86/kvm/vmx/vmx_ops.h:9:
   In file included from arch/x86/kvm/vmx/vmx_onhyperv.h:7:
   In file included from arch/x86/include/asm/mshyperv.h:345:
>> include/asm-generic/mshyperv.h:377:4: error: call to undeclared function 'hv_para_set_synic_register'; ISO C99 and later do not support implicit function declarations [-Wimplicit-function-declaration]
     377 |                         hv_para_set_synic_register(HV_MSR_EOM, 0);
         |                         ^
   1 error generated.
--
   In file included from arch/x86/kvm/svm/hyperv.c:7:
   In file included from arch/x86/kvm/svm/hyperv.h:9:
   In file included from arch/x86/include/asm/mshyperv.h:345:
>> include/asm-generic/mshyperv.h:377:4: error: call to undeclared function 'hv_para_set_synic_register'; ISO C99 and later do not support implicit function declarations [-Wimplicit-function-declaration]
     377 |                         hv_para_set_synic_register(HV_MSR_EOM, 0);
         |                         ^
   In file included from arch/x86/kvm/svm/hyperv.c:7:
   In file included from arch/x86/kvm/svm/hyperv.h:11:
   In file included from arch/x86/kvm/svm/../hyperv.h:24:
   In file included from include/linux/kvm_host.h:11:
   include/linux/signal.h:98:11: warning: array index 3 is past the end of the array (that has type 'unsigned long[2]') [-Warray-bounds]
      98 |                 return (set->sig[3] | set->sig[2] |
         |                         ^        ~
   arch/x86/include/asm/signal.h:24:2: note: array 'sig' declared here
      24 |         unsigned long sig[_NSIG_WORDS];
         |         ^
   In file included from arch/x86/kvm/svm/hyperv.c:7:
   In file included from arch/x86/kvm/svm/hyperv.h:11:
   In file included from arch/x86/kvm/svm/../hyperv.h:24:
   In file included from include/linux/kvm_host.h:11:
   include/linux/signal.h:98:25: warning: array index 2 is past the end of the array (that has type 'unsigned long[2]') [-Warray-bounds]
      98 |                 return (set->sig[3] | set->sig[2] |
         |                                       ^        ~
   arch/x86/include/asm/signal.h:24:2: note: array 'sig' declared here
      24 |         unsigned long sig[_NSIG_WORDS];
         |         ^
   In file included from arch/x86/kvm/svm/hyperv.c:7:
   In file included from arch/x86/kvm/svm/hyperv.h:11:
   In file included from arch/x86/kvm/svm/../hyperv.h:24:
   In file included from include/linux/kvm_host.h:11:
   include/linux/signal.h:114:11: warning: array index 3 is past the end of the array (that has type 'const unsigned long[2]') [-Warray-bounds]
     114 |                 return  (set1->sig[3] == set2->sig[3]) &&
         |                          ^         ~
   arch/x86/include/asm/signal.h:24:2: note: array 'sig' declared here
      24 |         unsigned long sig[_NSIG_WORDS];
         |         ^
   In file included from arch/x86/kvm/svm/hyperv.c:7:
   In file included from arch/x86/kvm/svm/hyperv.h:11:
   In file included from arch/x86/kvm/svm/../hyperv.h:24:
   In file included from include/linux/kvm_host.h:11:
   include/linux/signal.h:114:27: warning: array index 3 is past the end of the array (that has type 'const unsigned long[2]') [-Warray-bounds]
     114 |                 return  (set1->sig[3] == set2->sig[3]) &&
         |                                          ^         ~
   arch/x86/include/asm/signal.h:24:2: note: array 'sig' declared here
      24 |         unsigned long sig[_NSIG_WORDS];
         |         ^
   In file included from arch/x86/kvm/svm/hyperv.c:7:
   In file included from arch/x86/kvm/svm/hyperv.h:11:
   In file included from arch/x86/kvm/svm/../hyperv.h:24:
   In file included from include/linux/kvm_host.h:11:
   include/linux/signal.h:115:5: warning: array index 2 is past the end of the array (that has type 'const unsigned long[2]') [-Warray-bounds]
     115 |                         (set1->sig[2] == set2->sig[2]) &&
         |                          ^         ~
   arch/x86/include/asm/signal.h:24:2: note: array 'sig' declared here
      24 |         unsigned long sig[_NSIG_WORDS];
         |         ^
   In file included from arch/x86/kvm/svm/hyperv.c:7:
   In file included from arch/x86/kvm/svm/hyperv.h:11:
   In file included from arch/x86/kvm/svm/../hyperv.h:24:
   In file included from include/linux/kvm_host.h:11:
   include/linux/signal.h:115:21: warning: array index 2 is past the end of the array (that has type 'const unsigned long[2]') [-Warray-bounds]
     115 |                         (set1->sig[2] == set2->sig[2]) &&
         |                                          ^         ~
   arch/x86/include/asm/signal.h:24:2: note: array 'sig' declared here
      24 |         unsigned long sig[_NSIG_WORDS];
         |         ^
   In file included from arch/x86/kvm/svm/hyperv.c:7:
   In file included from arch/x86/kvm/svm/hyperv.h:11:
   In file included from arch/x86/kvm/svm/../hyperv.h:24:
   In file included from include/linux/kvm_host.h:11:
   include/linux/signal.h:157:1: warning: array index 3 is past the end of the array (that has type 'const unsigned long[2]') [-Warray-bounds]
     157 | _SIG_SET_BINOP(sigorsets, _sig_or)
         | ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
   include/linux/signal.h:138:8: note: expanded from macro '_SIG_SET_BINOP'
     138 |                 a3 = a->sig[3]; a2 = a->sig[2];                         \
         |                      ^      ~
   arch/x86/include/asm/signal.h:24:2: note: array 'sig' declared here
      24 |         unsigned long sig[_NSIG_WORDS];
         |         ^
   In file included from arch/x86/kvm/svm/hyperv.c:7:
   In file included from arch/x86/kvm/svm/hyperv.h:11:
   In file included from arch/x86/kvm/svm/../hyperv.h:24:
   In file included from include/linux/kvm_host.h:11:
   include/linux/signal.h:157:1: warning: array index 2 is past the end of the array (that has type 'const unsigned long[2]') [-Warray-bounds]
     157 | _SIG_SET_BINOP(sigorsets, _sig_or)
         | ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
   include/linux/signal.h:138:24: note: expanded from macro '_SIG_SET_BINOP'
     138 |                 a3 = a->sig[3]; a2 = a->sig[2];                         \
         |                                      ^      ~
   arch/x86/include/asm/signal.h:24:2: note: array 'sig' declared here
      24 |         unsigned long sig[_NSIG_WORDS];
         |         ^
   In file included from arch/x86/kvm/svm/hyperv.c:7:
   In file included from arch/x86/kvm/svm/hyperv.h:11:
   In file included from arch/x86/kvm/svm/../hyperv.h:24:
   In file included from include/linux/kvm_host.h:11:
   include/linux/signal.h:157:1: warning: array index 3 is past the end of the array (that has type 'const unsigned long[2]') [-Warray-bounds]
     157 | _SIG_SET_BINOP(sigorsets, _sig_or)
         | ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
   include/linux/signal.h:139:8: note: expanded from macro '_SIG_SET_BINOP'
     139 |                 b3 = b->sig[3]; b2 = b->sig[2];                         \
         |                      ^      ~
   arch/x86/include/asm/signal.h:24:2: note: array 'sig' declared here
      24 |         unsigned long sig[_NSIG_WORDS];


vim +/hv_para_set_synic_register +377 include/asm-generic/mshyperv.h

   344	
   345	/* Free the message slot and signal end-of-message if required */
   346	static inline void vmbus_signal_eom(struct hv_message *msg, u32 old_msg_type)
   347	{
   348		/*
   349		 * On crash we're reading some other CPU's message page and we need
   350		 * to be careful: this other CPU may already had cleared the header
   351		 * and the host may already had delivered some other message there.
   352		 * In case we blindly write msg->header.message_type we're going
   353		 * to lose it. We can still lose a message of the same type but
   354		 * we count on the fact that there can only be one
   355		 * CHANNELMSG_UNLOAD_RESPONSE and we don't care about other messages
   356		 * on crash.
   357		 */
   358		if (cmpxchg(&msg->header.message_type, old_msg_type,
   359			    HVMSG_NONE) != old_msg_type)
   360			return;
   361	
   362		/*
   363		 * The cmxchg() above does an implicit memory barrier to
   364		 * ensure the write to MessageType (ie set to
   365		 * HVMSG_NONE) happens before we read the
   366		 * MessagePending and EOMing. Otherwise, the EOMing
   367		 * will not deliver any more messages since there is
   368		 * no empty slot
   369		 */
   370		if (msg->header.message_flags.msg_pending) {
   371			/*
   372			 * This will cause message queue rescan to
   373			 * possibly deliver another msg from the
   374			 * hypervisor
   375			 */
   376			if (vmbus_is_confidential())
 > 377				hv_para_set_synic_register(HV_MSR_EOM, 0);
   378			else
   379				hv_set_msr(HV_MSR_EOM, 0);
   380		}
   381	}
   382

---

## [19] kernel test robot — 2025-07-16
*Subject: Re: [PATCH hyperv-next v4 04/16] arch/x86: mshyperv: Trap on access
 for some synthetic MSRs*

Hi Roman,

kernel test robot noticed the following build errors:

[auto build test ERROR on d9016a249be5316ec2476f9947356711e70a16ec]

url:    https://github.com/intel-lab-lkp/linux/commits/Roman-Kisel/Documentation-hyperv-Confidential-VMBus/20250715-062125
base:   d9016a249be5316ec2476f9947356711e70a16ec
patch link:    https://lore.kernel.org/r/20250714221545.5615-5-romank%40linux.microsoft.com
patch subject: [PATCH hyperv-next v4 04/16] arch/x86: mshyperv: Trap on access for some synthetic MSRs
config: x86_64-buildonly-randconfig-002-20250715 (https://download.01.org/0day-ci/archive/20250716/202507160105.yQ34bnKl-lkp@intel.com/config)
compiler: gcc-12 (Debian 12.2.0-14+deb12u1) 12.2.0
reproduce (this is a W=1 build): (https://download.01.org/0day-ci/archive/20250716/202507160105.yQ34bnKl-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202507160105.yQ34bnKl-lkp@intel.com/

All errors (new ones prefixed by >>):

   ld: vmlinux.o: in function `hv_set_non_nested_msr':
>> arch/x86/kernel/cpu/mshyperv.c:91: undefined reference to `vmbus_is_confidential'


vim +91 arch/x86/kernel/cpu/mshyperv.c

    79	
    80	void hv_set_non_nested_msr(unsigned int reg, u64 value)
    81	{
    82		if (hv_is_synic_msr(reg) && ms_hyperv.paravisor_present) {
    83			/* The hypervisor will get the intercept. */
    84			hv_ivm_msr_write(reg, value);
    85	
    86			if (hv_is_sint_msr(reg)) {
    87				/*
    88				 * Write proxy bit in the case of non-confidential VMBus.
    89				 * Using wrmsrq instruction so the following goes to the paravisor.
    90				 */
  > 91				u32 proxy = vmbus_is_confidential() ? 0 : 1;
    92	
    93				value |= (proxy << 20);
    94				native_wrmsrq(reg, value);
    95			}
    96		} else {
    97			native_wrmsrq(reg, value);
    98		}
    99	}
   100	EXPORT_SYMBOL_GPL(hv_set_non_nested_msr);
   101

---

## [20] kernel test robot — 2025-07-16
*Subject: Re: [PATCH hyperv-next v4 05/16] Drivers: hv: Rename fields for
 SynIC message and event pages*

Hi Roman,

kernel test robot noticed the following build warnings:

[auto build test WARNING on d9016a249be5316ec2476f9947356711e70a16ec]

url:    https://github.com/intel-lab-lkp/linux/commits/Roman-Kisel/Documentation-hyperv-Confidential-VMBus/20250715-062125
base:   d9016a249be5316ec2476f9947356711e70a16ec
patch link:    https://lore.kernel.org/r/20250714221545.5615-6-romank%40linux.microsoft.com
patch subject: [PATCH hyperv-next v4 05/16] Drivers: hv: Rename fields for SynIC message and event pages
config: i386-randconfig-061-20250715 (https://download.01.org/0day-ci/archive/20250716/202507160553.amoW6Ty0-lkp@intel.com/config)
compiler: gcc-12 (Debian 12.2.0-14+deb12u1) 12.2.0
reproduce (this is a W=1 build): (https://download.01.org/0day-ci/archive/20250716/202507160553.amoW6Ty0-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202507160553.amoW6Ty0-lkp@intel.com/

sparse warnings: (new ones prefixed by >>)
   drivers/hv/hv.c:280:26: sparse: sparse: cast removes address space '__iomem' of expression
   drivers/hv/hv.c:299:26: sparse: sparse: cast removes address space '__iomem' of expression
>> drivers/hv/hv.c:361:31: sparse: sparse: incorrect type in argument 1 (different address spaces) @@     expected void volatile [noderef] __iomem *addr @@     got void *hyp_synic_message_page @@
   drivers/hv/hv.c:361:31: sparse:     expected void volatile [noderef] __iomem *addr
   drivers/hv/hv.c:361:31: sparse:     got void *hyp_synic_message_page
>> drivers/hv/hv.c:373:31: sparse: sparse: incorrect type in argument 1 (different address spaces) @@     expected void volatile [noderef] __iomem *addr @@     got void *hyp_synic_event_page @@
   drivers/hv/hv.c:373:31: sparse:     expected void volatile [noderef] __iomem *addr
   drivers/hv/hv.c:373:31: sparse:     got void *hyp_synic_event_page

vim +361 drivers/hv/hv.c

   334	
   335	void hv_synic_disable_regs(unsigned int cpu)
   336	{
   337		struct hv_per_cpu_context *hv_cpu =
   338			per_cpu_ptr(hv_context.cpu_context, cpu);
   339		union hv_synic_sint shared_sint;
   340		union hv_synic_simp simp;
   341		union hv_synic_siefp siefp;
   342		union hv_synic_scontrol sctrl;
   343	
   344		shared_sint.as_uint64 = hv_get_msr(HV_MSR_SINT0 + VMBUS_MESSAGE_SINT);
   345	
   346		shared_sint.masked = 1;
   347	
   348		/* Need to correctly cleanup in the case of SMP!!! */
   349		/* Disable the interrupt */
   350		hv_set_msr(HV_MSR_SINT0 + VMBUS_MESSAGE_SINT, shared_sint.as_uint64);
   351	
   352		simp.as_uint64 = hv_get_msr(HV_MSR_SIMP);
   353		/*
   354		 * In Isolation VM, sim and sief pages are allocated by
   355		 * paravisor. These pages also will be used by kdump
   356		 * kernel. So just reset enable bit here and keep page
   357		 * addresses.
   358		 */
   359		simp.simp_enabled = 0;
   360		if (ms_hyperv.paravisor_present || hv_root_partition()) {
 > 361			iounmap(hv_cpu->hyp_synic_message_page);
   362			hv_cpu->hyp_synic_message_page = NULL;
   363		} else {
   364			simp.base_simp_gpa = 0;
   365		}
   366	
   367		hv_set_msr(HV_MSR_SIMP, simp.as_uint64);
   368	
   369		siefp.as_uint64 = hv_get_msr(HV_MSR_SIEFP);
   370		siefp.siefp_enabled = 0;
   371	
   372		if (ms_hyperv.paravisor_present || hv_root_partition()) {
 > 373			iounmap(hv_cpu->hyp_synic_event_page);
   374			hv_cpu->hyp_synic_event_page = NULL;
   375		} else {
   376			siefp.base_siefp_gpa = 0;
   377		}
   378	
   379		hv_set_msr(HV_MSR_SIEFP, siefp.as_uint64);
   380	
   381		/* Disable the global synic bit */
   382		sctrl.as_uint64 = hv_get_msr(HV_MSR_SCONTROL);
   383		sctrl.enable = 0;
   384		hv_set_msr(HV_MSR_SCONTROL, sctrl.as_uint64);
   385	
   386		if (vmbus_irq != -1)
   387			disable_percpu_irq(vmbus_irq);
   388	}
   389

---

## [21] Michael Kelley — 2025-07-22
*Subject: RE: [PATCH hyperv-next v4 01/16] Documentation: hyperv: Confidential
 VMBus*

From: Roman Kisel <romank@linux.microsoft.com> Sent: Monday, July 14, 2025 3:16 PM
> 
> Define what the confidential VMBus is and describe what advantages

Overall, this version looks good. I'm good with the overall
characterization of the scenarios where Confidential VMBus is
beneficial, and with the overview of how it works.

I've noted one nit below. But otherwise,
Reviewed-by: Michael Kelley <mhklinux@outlook.com>

> ---
>  Documentation/virt/hyperv/coco.rst | 140 ++++++++++++++++++++++++++++-

[snip]

> +
> +The data won't ever leave the VM when a device is attached to VTL2, and the

Two things:

1) At face value, saying "the data won't ever leave the VM" is counter to what I/O
is supposed to be doing -- the data leaves the VM to go to the device! I guess the
wording here struck me as funny. :-)

2) Being more precise about "attached to VTL2" would be helpful. This specifically
means a vPCI device assigned to VTL2.

I'd suggest something like:

The data is transferred directly between the VM and a vPCI device (a.k.a. a PCI
pass-thru device) that is directly assigned to VTL2 and that supports encrypted
memory. In such a case, neither the host partition nor the hypervisor has any
access to the data.

You could even include a link to the documentation topic on Hyper-V vPCI devices.

> +device supports encrypted memory. Therefore, neither the host partition nor the
> +hypervisor can access the data being processed at all. The guest needs to

---

## [22] Michael Kelley — 2025-07-22
*Subject: RE: [PATCH hyperv-next v4 02/16] drivers: hv: VMBus protocol version
 6.0*

From: Roman Kisel <romank@linux.microsoft.com> Sent: Monday, July 14, 2025 3:16 PM
> 
> The confidential VMBus is supported starting from the protocol

Reviewed-by: Michael Kelley <mhklinux@outlook.com>

> ---
>  drivers/hv/vmbus_drv.c         | 12 ++++++

---

## [23] Michael Kelley — 2025-07-22
*Subject: RE: [PATCH hyperv-next v4 03/16] arch: hyperv: Get/set SynIC
 synth.registers via paravisor*

From: Roman Kisel <romank@linux.microsoft.com> Sent: Monday, July 14, 2025 3:16 PM
> 
> The existing Hyper-V wrappers for getting and setting MSRs are

This last paragraph seems to be a leftover from a previous
version of the commit message. I think it can be deleted since
the second paragraph now covers the topic.

> 
> Signed-off-by: Roman Kisel <romank@linux.microsoft.com>

As reported by the kernel test robot, this function call is generating an
error because there's no declaration for hv_para_set_synic_register()
when built with !CONFIG_HYPERV.

One solution is to add a stub higher up in this source code file in
the existing !CONFIG_HYPERV section.

But a better solution might be move vmbus_signal_eom() out of this
file entirely and put it in drivers/hv/hyperv_vmbus.h. Then no stub
for !CONFIG_HYPERV is needed. vmbus_signal_eom() is very much
a VMBus function, and it's only called from vmbus_wait_for_unload(),
__vmbus_on_msg_dpc(), and vmbus_message_sched().

The file asm-generic/mshyperv.h should be focused on the Hyper-V
interface, not on VMBus, so it's not clear to me why vmbus_signal_eom()
is in asm-generic/mshyperv.h in the first place. There's no reason to expose
vmbus_signal_eom() to code that needs definitions related to Hyper-V,
such as the x86 MTRR code or the Hyper-V emulation code in KVM
(which is where the kernel test robot detected the error). Note that
drivers/hv/hyperv_vmbus.h will need to add #include <asm/mshyperv.h>
in order for the move to work.

I've tested build with CONFIG_HYPERV and !CONFIG_HYPERV on
x86 and on arm64, and the proposed move seems to work OK.

Sorry my suggestion in v3 of your patch set to handle HV_MSR_EOM
here in vmbus_signal_eom() turned out to be more complicated than
I originally contemplated. :-(

> +		else
> +			hv_set_msr(HV_MSR_EOM, 0);

---

## [24] Michael Kelley — 2025-07-22
*Subject: RE: [PATCH hyperv-next v4 04/16] arch/x86: mshyperv: Trap on access
 for some synthetic MSRs*

From: Roman Kisel <romank@linux.microsoft.com> Sent: Monday, July 14, 2025 3:16 PM
> 
> hv_set_non_nested_msr() has special handling for SINT MSRs

This paragraph looks like a leftover from the previous version of
the commit message.  vmbus_signal_eom() is not touched in this
patch.

> 
> Signed-off-by: Roman Kisel <romank@linux.microsoft.com>

The kernel test robot is rightly complaining about vmbus_is_confidential()
being used here. vmbus_is_confidential() comes from vmbus_drv.c, which
is built as a module when CONFIG_HYPERV=m. But this code is always
built-in, and built-in code can't directly refer to functions in a module.
Logically, the layering is wrong because vmbus_is_confidential() is
obviously a VMBus concept, while mshyperv.c only deals with Hyper-V
and knows nothing about VMBus. Your v3 patch series has the same
problem, but evidently the kernel test robot didn't notice the issue,
and I didn't notice it either my v3 review.

The best solution is probably to define a 32-bit "proxy bit" value here
in mshyperv.c. hv_set_non_nested_msr() would always OR in that
value before the call to native_wrmsrq() below. Wherever VMBus code
changes the value of is_confidential, it must also call an EXPORTed
function here in mshyperv.c to set or clear the value of "proxy bit".
Overall, it's a bit messy, but I don't see a better solution.

> +
> +			value |= (proxy << 20);

---

## [25] Michael Kelley — 2025-07-22
*Subject: RE: [PATCH hyperv-next v4 05/16] Drivers: hv: Rename fields for SynIC
 message and event pages*

From: Roman Kisel <romank@linux.microsoft.com> Sent: Monday, July 14, 2025 3:16 PM
> 
> Confidential VMBus requires interacting with two SynICs -- one

Reviewed-by: Michael Kelley <mhklinux@outlook.com>

> ---
>  drivers/hv/channel_mgmt.c |  6 ++--

---

## [26] Michael Kelley — 2025-07-22
*Subject: RE: [PATCH hyperv-next v4 06/16] Drivers: hv: Allocate the paravisor
 SynIC pages when required*

From: Roman Kisel <romank@linux.microsoft.com> Sent: Monday, July 14, 2025 3:16 PM
> 
> Confidential VMBus requires interacting with two SynICs -- one

Modulo a nit called out below,
Reviewed-by: Michael Kelley <mhklinux@outlook.com>

> ---
>  drivers/hv/hv.c           | 184 +++++++++++++++++++-------------------

Nit: The braces here are unnecessary.

> +		free_page((unsigned long)*page);
> +

---

## [27] Michael Kelley — 2025-07-22
*Subject: RE: [PATCH hyperv-next v4 07/16] Drivers: hv: Post messages through
 the confidential VMBus if available*

From: Roman Kisel <romank@linux.microsoft.com> Sent: Monday, July 14, 2025 3:16 PM
> 
> When the confidential VMBus is available, the guest should post

Reviewed-by: Michael Kelley <mhklinux@outlook.com>

> ---
>  drivers/hv/hv.c | 11 ++++++++++-

---

## [28] Michael Kelley — 2025-07-22
*Subject: RE: [PATCH hyperv-next v4 08/16] Drivers: hv: remove stale comment*

From: Roman Kisel <romank@linux.microsoft.com> Sent: Monday, July 14, 2025 3:16 PM
> 
> The comment about the x2v shim is ancient and long since incorrect.

Reviewed-by: Michael Kelley <mhklinux@outlook.com>

---

## [29] Michael Kelley — 2025-07-22
*Subject: RE: [PATCH hyperv-next v4 09/16] Drivers: hv: Check message and event
 pages for non-NULL before iounmap()*

From: Roman Kisel <romank@linux.microsoft.com> Sent: Monday, July 14, 2025 3:16 PM
> 
> It might happen that some hyp SynIC pages aren't allocated.

Reviewed-by: Michael Kelley <mhklinux@outlook.com>

---

## [30] Michael Kelley — 2025-07-22
*Subject: RE: [PATCH hyperv-next v4 10/16] Drivers: hv: Rename the SynIC enable
 and disable routines*

From: Roman Kisel <romank@linux.microsoft.com> Sent: Monday, July 14, 2025 3:16 PM
> 
> The confidential VMBus requires support for the both hypervisor

Reviewed-by: Michael Kelley <mhklinux@outlook.com>

> ---
>  drivers/hv/channel_mgmt.c |  2 +-

---

## [31] Michael Kelley — 2025-07-22
*Subject: RE: [PATCH hyperv-next v4 11/16] Drivers: hv: Functions for setting
 up and tearing down the paravisor SynIC*

From: Roman Kisel <romank@linux.microsoft.com> Sent: Monday, July 14, 2025 3:16 PM
> 
> The confidential VMBus runs with the paravisor SynIC and requires

See some comments below about the comments in the code.
Those notwithstanding,
Reviewed-by: Michael Kelley <mhklinux@outlook.com>

> ---
>  drivers/hv/hv.c | 197 +++++++++++++++++++++++++++++++++++++++++++++---

s/hv_hyperv_synic_enable_regs/hv_hyp_synic_enable_regs/

> +	 * hv_set_msr(). hv_set_msr() in turn has special case code for the
> +	 * SINT MSRs that write to the hypervisor version of the MSR *and*

This reference to "the code above" is wrong. It's actually the code below.
Perhaps just do "Then enable interrupts via the paravisor ...." as a new
paragraph in the comment.

> +	 * via the paravisor if VMBus is confidential, and otherwise via the
> +	 * hypervisor.

This comment feels unnecessary because deallocating memory in
this function should not be an expectation. Lacking that expectation,
there's no reason to explain why it is not done. Looking at the larger
context, the paired function hv_para_synic_enable_regs() doesn't
allocate memory, and the parallel function hv_hyp_synic_disable_regs()
also doesn't do memory deallocation. FWIW, the first sentence of the
comment is slightly inaccurate because the function is called only
when a CPU goes offline. But I would remove the comment entirely
so as to not imply that it's reasonable to expect the deallocation
should be done here.

CPU offlining is not the justification for why deallocation is not done
here. In my comments on v3 of this patch, my intent was to use CPU
offlining just as an example of why deallocating here would break
things. The deallocation is already properly done in hv_synic_free().

> +
> +	/* Disable SynIC's message page in the paravisor. */

s/gurantee/guarantee/

> +	 * may be posted for processing before disabling interrupts.
> +	 */

---

## [32] Michael Kelley — 2025-07-22
*Subject: RE: [PATCH hyperv-next v4 12/16] Drivers: hv: Allocate encrypted
 buffers when requested*

From: Roman Kisel <romank@linux.microsoft.com> Sent: Monday, July 14, 2025 3:16 PM
> 
> Confidential VMBus is built around using buffers not shared with

Reviewed-by: Michael Kelley <mhklinux@outlook.com>

> ---
>  drivers/hv/channel.c      | 49 +++++++++++++++++++++++----------------

---

## [33] Michael Kelley — 2025-07-22
*Subject: RE: [PATCH hyperv-next v4 13/16] Drivers: hv: Free msginfo when the
 buffer fails to decrypt*

From: Roman Kisel <romank@linux.microsoft.com> Sent: Monday, July 14, 2025 3:16 PM
> 
> The early failure path in __vmbus_establish_gpadl() doesn't deallocate

s/Kelly/Kelley/

> Closes: https://lore.kernel.org/linux-hyperv/SN6PR02MB41573796F9787F67E0E97049D472A@SN6PR02MB4157.namprd02.prod.outlook.com/ 
> Signed-off-by: Roman Kisel <romank@linux.microsoft.com>

I don't think this works. At this point, msginfo has not been added to the global
vmbus_connection.chn_msg_list.  vmbus_free_channel_msginfo() will try to
remove it from that list using list_del(), and will fault on a NULL pointer.

>  			return ret;
>  		}

---

## [34] Michael Kelley — 2025-07-22
*Subject: RE: [PATCH hyperv-next v4 14/16] Drivers: hv: Support confidential
 VMBus channels*

From: Roman Kisel <romank@linux.microsoft.com> Sent: Monday, July 14, 2025 3:16 PM
> 
> To make use of Confidential VMBus channels, initialize the

Reviewed-by: Michael Kelley <mhklinux@outlook.com>

> ---
>  drivers/hv/channel_mgmt.c | 19 +++++++++++++++++++

---

## [35] Michael Kelley — 2025-07-22
*Subject: RE: [PATCH hyperv-next v4 15/16] Drivers: hv: Support establishing
 the confidential VMBus connection*

From: Roman Kisel <romank@linux.microsoft.com> Sent: Monday, July 14, 2025 3:16 PM
> 
> To establish the confidential VMBus connection the CoCo VM guest

See some spelling/formatting nits below, plus a comment about
your 5 scenarios. Those notwithstanding,
Reviewed-by: Michael Kelley <mhklinux@outlook.com>

> ---
>  drivers/hv/vmbus_drv.c | 189 ++++++++++++++++++++++++++++-------------

Inconsistent indentation.

Also, isn't there a "No paravisor, with hardware isolation" scenario? We've
called this "fully enlightened guest" in the past, and code has gone into the
kernel to at least partially support this. The scenario is supported by the
hardware and by Linux guests on other hypervisors. But I'm unsure of the
status on Hyper-V.

> +	 *  2. Paravisor without VMBus relay, no hardware isolation,
> +	 *  3. Paravisor without VMBus relay, with hardware isolation,

s/uncomoon/uncommon/

> +	 * ~300 CPUs, and are rarely used with many dozens of CPUs. As the time goes on, that
> +	 * will be even less common. Hence, the preference is to not specialize the code for

---

## [36] Michael Kelley — 2025-07-22
*Subject: RE: [PATCH hyperv-next v4 16/16] Drivers: hv: Set the default VMBus
 version to 6.0*

From: Roman Kisel <romank@linux.microsoft.com> Sent: Monday, July 14, 2025 3:16 PM
> 
> The confidential VMBus is supported by the protocol version

Reviewed-by: Michael Kelley <mhklinux@outlook.com>

---

## [37] Tianyu Lan — 2025-07-25
*Subject: Re: [PATCH hyperv-next v4 04/16] arch/x86: mshyperv: Trap on access
 for some synthetic MSRs*

On Tue, Jul 15, 2025 at 6:16 AM Roman Kisel <romank@linux.microsoft.com> wrote:
>
> hv_set_non_nested_msr() has special handling for SINT MSRs

Reviewed-by: Tianyu Lan <tiala@microsoft.com>

---

## [38] Tianyu Lan — 2025-07-25
*Subject: Re: [PATCH hyperv-next v4 05/16] Drivers: hv: Rename fields for SynIC
 message and event pages*

On Tue, Jul 15, 2025 at 6:18 AM Roman Kisel <romank@linux.microsoft.com> wrote:
>
> Confidential VMBus requires interacting with two SynICs -- one

Reviewed-by: Tianyu Lan <tiala@microsoft.com>

---

## [39] Tianyu Lan — 2025-07-25
*Subject: Re: [PATCH hyperv-next v4 06/16] Drivers: hv: Allocate the paravisor
 SynIC pages when required*

On Tue, Jul 15, 2025 at 6:16 AM Roman Kisel <romank@linux.microsoft.com> wrote:
>
> Confidential VMBus requires interacting with two SynICs -- one

Reviewed-by: Tianyu Lan <tiala@microsoft.com>

---

## [40] Tianyu Lan — 2025-07-25
*Subject: Re: [PATCH hyperv-next v4 07/16] Drivers: hv: Post messages through
 the confidential VMBus if available*

On Tue, Jul 15, 2025 at 6:16 AM Roman Kisel <romank@linux.microsoft.com> wrote:
>
> When the confidential VMBus is available, the guest should post

Reviewed-by: Tianyu Lan <tiala@microsoft.com>

---

## [41] Tianyu Lan — 2025-07-25
*Subject: Re: [PATCH hyperv-next v4 08/16] Drivers: hv: remove stale comment*

On Tue, Jul 15, 2025 at 6:16 AM Roman Kisel <romank@linux.microsoft.com> wrote:
>
> The comment about the x2v shim is ancient and long since incorrect.

Reviewed-by: Tianyu Lan <tiala@microsoft.com>

---

## [42] Tianyu Lan — 2025-07-25
*Subject: Re: [PATCH hyperv-next v4 09/16] Drivers: hv: Check message and event
 pages for non-NULL before iounmap()*

On Tue, Jul 15, 2025 at 6:16 AM Roman Kisel <romank@linux.microsoft.com> wrote:
>
> It might happen that some hyp SynIC pages aren't allocated.

Reviewed-by: Tianyu Lan <tiala@microsoft.com>

---

## [43] Tianyu Lan — 2025-07-25
*Subject: Re: [PATCH hyperv-next v4 10/16] Drivers: hv: Rename the SynIC enable
 and disable routines*

On Tue, Jul 15, 2025 at 6:16 AM Roman Kisel <romank@linux.microsoft.com> wrote:
>
> The confidential VMBus requires support for the both hypervisor

Reviewed-by: Tianyu Lan <tiala@microsoft.com>

---

## [44] Tianyu Lan — 2025-07-25
*Subject: Re: [PATCH hyperv-next v4 12/16] Drivers: hv: Allocate encrypted
 buffers when requested*

On Tue, Jul 15, 2025 at 6:28 AM Roman Kisel <romank@linux.microsoft.com> wrote:
>
> Confidential VMBus is built around using buffers not shared with

Reviewed-by: Tianyu Lan <tiala@microsoft.com>

>  drivers/hv/channel.c      | 49 +++++++++++++++++++++++----------------
>  drivers/hv/hyperv_vmbus.h |  3 ++-

---

## [45] dan.j.williams@intel.com — 2025-08-19
*Subject: Re: [PATCH hyperv-next v4 15/16] Drivers: hv: Support establishing
 the confidential VMBus connection*

Roman Kisel wrote:
> To establish the confidential VMBus connection the CoCo VM guest
> first attempts to connect to the VMBus server run by the paravisor.
[..]
> @@ -1401,41 +1474,42 @@ static int vmbus_bus_init(void)
>  		}

I read this blurb looking for answers to my question below, no luck, and
left further wondering what is the comment trying to convey to future
maintenance?

>  	 */
> -	cpus_read_lock();

In comparison to PCIe TDISP where there is an explicit validation step
of cryptographic evidence that the platform is what it claims to be, I
am missing the same for this.

I would expect something like a paravisor signed golden measurement with
a certificate that can be built-in to the kernel to validate that "yes,
in addition to the platform claims that can be emulated, this bus
enumeration is signed by an authority this kernel image trusts."

My motivation for commenting here is for alignment purposes with the
PCIe TDISP enabling and wider concerns about accepting other devices for
private operation. Specifically, I want to align on a shared
representation in the device-core (struct device) to communicate that a
device is either on a bus that has been accepted for private operation
(confidential-vmbus today, potentially signed-ACPI-devices tomorrow), or
is a device that has been individually accepted for private operation
(PCIe TDISP). In both cases there needs to be either a golden
measurement mechanism built-in, or a userspace acceptance dependency in
the flow.

Otherwise what mitigates a guest conveying secrets to a device that is
merely emulating a trusted bus/device?

---

## [46] Roman Kisel — 2025-08-25
*Subject: Re: [PATCH hyperv-next v4 15/16] Drivers: hv: Support establishing the confidential VMBus connection*

[...]
>> +	 *
>> +	 * All scenarios here are:

The intention was to enumerate scenarios in which the driver executes
this code to document what to expect of the conditional statement

| if (ms_hyperv.paravisor_present && (hv_isolation_type_tdx() || hv_isolation_type_snp()))

[...]

> In comparison to PCIe TDISP where there is an explicit validation step
> of cryptographic evidence that the platform is what it claims to be, I

This doesn't replace TDISP, I'll do a better job of supplementing the code changes
with documentation and comments! Any suggestions are greatly appreciated.

A fully-enlightened Linux guest could just use TDISP once support for that is available
in the Linux kernel. Before it is, the non-fully enlightened Linux guests (they can only deal
with accepting memory and sharing memory with the host) could rely on the paravisor to talk
to such devices. The TDISP device will be connected to the paravisor, and the paravisor will
provide the paravirtualized storage and network over the VMBus channels to the Linux guest.

The patch set is a building block for building a confidential I/O path for the non-fully
enlightened Linux guests. It would be great to have the Linux storage and network stack not
to share pages with the host (and not bounce-buffer) if the storage and network are
paravirtualized && use the Confidential VMBus. In the first version of the patchset I had
patches for that, yet that was considered too naive to be merged in the main line kernel so
I dropped them. But even without that, this patch series protects the control plane and the
data plane from the host with the exception of the pages the guest might use for bounce-buffering
although it could've avoided that in this case.

I mentioned that the paravisor will be handling the TDISP device for such guests.
As folks might know, we use the OpenHCL paravisor which is a Linux kernel with the VTL
mode patches we've been upstreaming (links to the repos are in the cover letter), and
the OpenVMM running in the user land. The question would be if TDISP isn't available
in the Linux kernel, how one would get it working in the OpenHCL paravisor that itself
runs Linux? The SEV guest device in the paravisor kernel is being extended to handle
TIO. Once TDISP support is available in the mainline kernel, the paravisor will switch
to using the mainline implementation.

> I would expect something like a paravisor signed golden measurement with
> a certificate that can be built-in to the kernel to validate that "yes,

---

## [47] Roman Kisel — 2025-08-25
*Subject: Re: [PATCH hyperv-next v4 15/16] Drivers: hv: Support establishing the confidential VMBus connection*

[...]
>> +	 *
>> +	 * All scenarios here are:

The intention was to enumerate scenarios in which the driver executes
this code to document what to expect of the conditional statement

| if (ms_hyperv.paravisor_present && (hv_isolation_type_tdx() || hv_isolation_type_snp()))

[...]

> In comparison to PCIe TDISP where there is an explicit validation step
> of cryptographic evidence that the platform is what it claims to be, I

This doesn't replace TDISP, I'll do a better job of supplementing the code changes
with documentation and comments! Any suggestions are greatly appreciated.

A fully-enlightened Linux guest could just use TDISP once support for that is available
in the Linux kernel. Before it is, the non-fully enlightened Linux guests (they can only deal
with accepting memory and sharing memory with the host) could rely on the paravisor to talk
to such devices. The TDISP device will be connected to the paravisor, and the paravisor will
provide the paravirtualized storage and network over the VMBus channels to the Linux guest.

The patch set is a building block for building a confidential I/O path for the non-fully
enlightened Linux guests. It would be great to have the Linux storage and network stack not
to share pages with the host (and not bounce-buffer) if the storage and network are
paravirtualized && use the Confidential VMBus. In the first version of the patchset I had
patches for that, yet that was considered too naive to be merged in the main line kernel so
I dropped them. But even without that, this patch series protects the control plane and the
data plane from the host with the exception of the pages the guest might use for bounce-buffering
although it could've avoided that in this case.

I mentioned that the paravisor will be handling the TDISP device for such guests.
As folks might know, we use the OpenHCL paravisor which is a Linux kernel with the VTL
mode patches we've been upstreaming (links to the repos are in the cover letter), and
the OpenVMM running in the user land. The question would be if TDISP isn't available
in the Linux kernel, how one would get it working in the OpenHCL paravisor that itself
runs Linux? The SEV guest device in the paravisor kernel is being extended to handle
TIO. Once TDISP support is available in the mainline kernel, the paravisor will switch
to using the mainline implementation.

> I would expect something like a paravisor signed golden measurement with
> a certificate that can be built-in to the kernel to validate that "yes,

---

## [48] dan.j.williams@intel.com — 2025-08-25
*Subject: Re: [PATCH hyperv-next v4 15/16] Drivers: hv: Support establishing
 the confidential VMBus connection*

Roman Kisel wrote:
[..]
> This doesn't replace TDISP, I'll do a better job of supplementing the code changes
> with documentation and comments! Any suggestions are greatly appreciated.

No, I am not asking for documentation and comments and I am asking how
any of the security claims are validated by this partially enabled L2
guest?

> A fully-enlightened Linux guest could just use TDISP once support for that is available
> in the Linux kernel. Before it is, the non-fully enlightened Linux guests (they can only deal

Yes, that is understood, again that is not the question.

> The patch set is a building block for building a confidential I/O path for the non-fully
> enlightened Linux guests. It would be great to have the Linux storage and network stack not

The question is what protects against the paravisor lying about its
identity? If the L2 guest is partially aware that a paravisor is
providing confidentiality then it needs some interaction with a relying
party to say "yes, this paravisor is indeed what it claims to be". Is
that some indicator passed over an established / trusted channel that I
overlooked?

> I mentioned that the paravisor will be handling the TDISP device for such guests.
> As folks might know, we use the OpenHCL paravisor which is a Linux kernel with the VTL

Either the L2 is unenlightened and has all its mapping attempts trapped
and redirected to be encrypted, or the L2 is partially enlightened and
at a minimum validates the identity of the paravisor.

---

## [49] Roman Kisel — 2025-08-25
*Subject: Re: [PATCH hyperv-next v4 15/16] Drivers: hv: Support establishing
 the confidential VMBus connection*

On 8/25/2025 4:00 PM, dan.j.williams@intel.com wrote:
> Roman Kisel wrote:
> [..]

As the guest is partially enabled, it relies on the trusted paravaisor
which is fully enabled wrt running in a hardware isolated VM. The
paravisor image is measured, there is attestation flow, and the hardware
validates the paravisor image.

[...]

>> The patch set is a building block for building a confidential I/O path for the non-fully
>> enlightened Linux guests. It would be great to have the Linux storage and network stack not

Trying to understand the question, thinking out loud. The paravisor is
running within the same GPA space as the guest, the host/hv cannot
access the CPU context and the memory assigned to the paravisor and the
guest until they share the pages, the paravisor is measured and goes
through attestation. From that, the customer has the control over the
chain of trust. They can rebuild the paravisor if they wish to do so.

>> I mentioned that the paravisor will be handling the TDISP device for such guests.
>> As folks might know, we use the OpenHCL paravisor which is a Linux kernel with the VTL

---

## [50] dan.j.williams@intel.com — 2025-08-25
*Subject: Re: [PATCH hyperv-next v4 15/16] Drivers: hv: Support establishing
 the confidential VMBus connection*

Roman Kisel wrote:
[..]
> Trying to understand the question, thinking out loud. The paravisor is
> running within the same GPA space as the guest, the host/hv cannot

Ah, that is the detail I was missing the paravisor is provided by the
tenant so it could be measured by secure boot or similar mechanism the
tenant uses to measure the kernel and/or initrd image.

I also now realize this is not trying to enable device drivers other
than existing VMBUS drivers that do not need to have explicit knowledge
that the transport channel is now encrypted.

So, carry on, sorry for the noise. TDISP is trying to solve a wholly
different problem in its support for unmodified drivers without
something like a VMBUS abstraction to secure the communication channel.

---
