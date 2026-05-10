---
title: 'crypto/ccp: Fixes for PCI IDE'
date: 2026-01-23
last_reply: 2026-01-30
message_count: 9
participants: ['Alexey Kardashevskiy', 'Tom Lendacky', 'dan.j.williams@intel.com']
---

## [1] Alexey Kardashevskiy — 2026-01-23

A couple of fixes for bugs discovered recently as we got more of
these devices and tested more configurations with multiple devices
on same and different bridges.


This is based on sha1
0499add8efd7 Paolo Bonzini Merge tag 'kvm-x86-fixes-6.19-rc1' of htts://github.com/kvm-x86/linux into HEAD

Please comment. Thanks.



Alexey Kardashevskiy (2):
  crypto/ccp: Use PCI bridge defaults for IDE
  crypto/ccp: Allow multiple streams on the same root bridge

 drivers/crypto/ccp/sev-dev-tsm.c | 15 +--------------
 1 file changed, 1 insertion(+), 14 deletions(-)

---

## [2] Alexey Kardashevskiy — 2026-01-23
*Subject: [PATCH kernel 1/2] crypto/ccp: Use PCI bridge defaults for IDE*

The current number of streams in AMD TSM is 1 which is too little,
the core uses 255. Also, even if the module parameter is increased,
calling pci_ide_set_nr_streams() second time triggers WARN_ON.

Simplify the code by sticking to the PCI core defaults.

Fixes: 4be423572da1 ("crypto/ccp: Implement SEV-TIO PCIe IDE (phase1)")
Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---
 drivers/crypto/ccp/sev-dev-tsm.c | 12 ------------
 1 file changed, 12 deletions(-)

diff --git a/drivers/crypto/ccp/sev-dev-tsm.c b/drivers/crypto/ccp/sev-dev-tsm.c
index ea29cd5d0ff9..7407b77c2ef2 100644
--- a/drivers/crypto/ccp/sev-dev-tsm.c
+++ b/drivers/crypto/ccp/sev-dev-tsm.c
@@ -19,12 +19,6 @@
 
 MODULE_IMPORT_NS("PCI_IDE");
 
-#define TIO_DEFAULT_NR_IDE_STREAMS	1
-
-static uint nr_ide_streams = TIO_DEFAULT_NR_IDE_STREAMS;
-module_param_named(ide_nr, nr_ide_streams, uint, 0644);
-MODULE_PARM_DESC(ide_nr, "Set the maximum number of IDE streams per PHB");
-
 #define dev_to_sp(dev)		((struct sp_device *)dev_get_drvdata(dev))
 #define dev_to_psp(dev)		((struct psp_device *)(dev_to_sp(dev)->psp_data))
 #define dev_to_sev(dev)		((struct sev_device *)(dev_to_psp(dev)->sev_data))
@@ -193,7 +187,6 @@ static void streams_teardown(struct pci_ide **ide)
 static int stream_alloc(struct pci_dev *pdev, struct pci_ide **ide,
 			unsigned int tc)
 {
-	struct pci_dev *rp = pcie_find_root_port(pdev);
 	struct pci_ide *ide1;
 
 	if (ide[tc]) {
@@ -201,11 +194,6 @@ static int stream_alloc(struct pci_dev *pdev, struct pci_ide **ide,
 		return -EBUSY;
 	}
 
-	/* FIXME: find a better way */
-	if (nr_ide_streams != TIO_DEFAULT_NR_IDE_STREAMS)
-		pci_notice(pdev, "Enable non-default %d streams", nr_ide_streams);
-	pci_ide_set_nr_streams(to_pci_host_bridge(rp->bus->bridge), nr_ide_streams);
-
 	ide1 = pci_ide_stream_alloc(pdev);
 	if (!ide1)
 		return -EFAULT;

---

## [3] Alexey Kardashevskiy — 2026-01-23
*Subject: [PATCH kernel 2/2] crypto/ccp: Allow multiple streams on the same root bridge*

IDE stream IDs are responsibility of a platform and in some cases TSM
allocates the numbers. AMD SEV TIO though leaves it to the host OS.
Mistakenly stream ID is hard coded to be the same as a traffic class.

Use the host bridge stream index for a newly allocated stream ID.

Fixes: 4be423572da1 ("crypto/ccp: Implement SEV-TIO PCIe IDE (phase1)")
Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---
 drivers/crypto/ccp/sev-dev-tsm.c | 3 +--
 1 file changed, 1 insertion(+), 2 deletions(-)

diff --git a/drivers/crypto/ccp/sev-dev-tsm.c b/drivers/crypto/ccp/sev-dev-tsm.c
index 7407b77c2ef2..40d02adaf3f6 100644
--- a/drivers/crypto/ccp/sev-dev-tsm.c
+++ b/drivers/crypto/ccp/sev-dev-tsm.c
@@ -198,8 +198,7 @@ static int stream_alloc(struct pci_dev *pdev, struct pci_ide **ide,
 	if (!ide1)
 		return -EFAULT;
 
-	/* Blindly assign streamid=0 to TC=0, and so on */
-	ide1->stream_id = tc;
+	ide1->stream_id = ide1->host_bridge_stream;
 
 	ide[tc] = ide1;

---

## [4] Tom Lendacky — 2026-01-23
*Subject: Re: [PATCH kernel 0/2] crypto/ccp: Fixes for PCI IDE*

On 1/22/26 23:30, Alexey Kardashevskiy wrote:
> A couple of fixes for bugs discovered recently as we got more of
> these devices and tested more configurations with multiple devices

You might want to send a patch that adds you as a maintainer of the SEV
TIO files/support, too.

Acked-by: Tom Lendacky <thomas.lendacky@amd.com>

> 
>

---

## [5] dan.j.williams@intel.com — 2026-01-23
*Subject: Re: [PATCH kernel 1/2] crypto/ccp: Use PCI bridge defaults for IDE*

Alexey Kardashevskiy wrote:
> The current number of streams in AMD TSM is 1 which is too little,
> the core uses 255. Also, even if the module parameter is increased,

Yes, happy to see any reduction in ABI surface, especially module
parameters.

Acked-by: Dan Williams <dan.j.williams@intel.com>

---

## [6] dan.j.williams@intel.com — 2026-01-23
*Subject: Re: [PATCH kernel 2/2] crypto/ccp: Allow multiple streams on the same
 root bridge*

Alexey Kardashevskiy wrote:
> IDE stream IDs are responsibility of a platform and in some cases TSM
> allocates the numbers. AMD SEV TIO though leaves it to the host OS.

I scratched my head at this comment, but now realize that you are saying
the existing code used the local @tc, not that the hardware stream ID is
in any way related to traffic class, right?

It would help to detail what the end user visible effects of this bug
are. The TSM framework does not allow for multiple streams per PF, so I
wonder what scenario is being fixed?

Lastly, are you expecting tsm.git#fixes to pick this up? I am assuming
that this goes through crypto.git and tsm.git can just stay focused on
core fixes.

---

## [7] Alexey Kardashevskiy — 2026-01-26
*Subject: Re: [PATCH kernel 2/2] crypto/ccp: Allow multiple streams on the same
 root bridge*

On 24/1/26 09:59, dan.j.williams@intel.com wrote:
> Alexey Kardashevskiy wrote:
>> IDE stream IDs are responsibility of a platform and in some cases TSM

When I did that in the first place, I also wanted to try different traffic classes so I just took a shortcut here.

> It would help to detail what the end user visible effects of this bug
> are. The TSM framework does not allow for multiple streams per PF, so I

There is no way in the current upstream code to specify this TC so the only visible effect is that 2 devices under the same bridge can work now, previously the second device would fail to allocate a stream.

> Lastly, are you expecting tsm.git#fixes to pick this up? I am assuming
> that this goes through crypto.git and tsm.git can just stay focused on

I was kinda hoping that Tom acks these (as he did) and you could take them. Thanks,

---

## [8] dan.j.williams@intel.com — 2026-01-26
*Subject: Re: [PATCH kernel 2/2] crypto/ccp: Allow multiple streams on the same
 root bridge*

Alexey Kardashevskiy wrote:
> On 24/1/26 09:59, dan.j.williams@intel.com wrote:
> > Alexey Kardashevskiy wrote:

Ok, so can you refresh the changelog to call out the user visible
effects?  Something like:

---
With SEV-TIO the low-level TSM driver is responsible for allocating a
Stream ID. The Stream ID needs to be unique within each IDE partner
port. Fix the Stream ID selection to reuse the host bridge stream
resource id which is a pool of 256 ids per host bridge on AMD platforms.
Otherwise, only one device per-host bridge can establish Selective
Stream IDE.
---

Send a v2, and I will pick it up.

---

## [9] Alexey Kardashevskiy — 2026-01-30
*Subject: Re: [PATCH kernel 2/2] crypto/ccp: Allow multiple streams on the same
 root bridge*

On 27/1/26 17:59, dan.j.williams@intel.com wrote:
> Alexey Kardashevskiy wrote:
>> On 24/1/26 09:59, dan.j.williams@intel.com wrote:

Please squash it in the v1, if possible.

Acked-by: Alexey Kardashevskiy <aik@amd.com>

thanks!

ps sorry missed that on time, I do suck at multitasking :(

---
