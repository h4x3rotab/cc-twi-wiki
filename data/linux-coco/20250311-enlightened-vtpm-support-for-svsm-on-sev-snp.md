---
title: 'Enlightened vTPM support for SVSM on SEV-SNP'
date: 2025-03-11
last_reply: 2025-03-24
message_count: 33
participants: ['Stefano Garzarella', 'Jarkko Sakkinen', 'Tom Lendacky', 'Jason Gunthorpe', 'Borislav Petkov']
---

## [1] Stefano Garzarella — 2025-03-11

AMD SEV-SNP defined a new mechanism for adding privileged levels (VMPLs)
in the context of a Confidential VM. These levels can be used to run the
guest OS at a lower privilege level than a Secure VM Service Module (SVSM).
In this way SVSM can be used to emulate those devices (such as TPM) that
cannot be delegated to an untrusted host.

The guest OS can talk to SVSM using a specific calling convention and
instructions (a kind of system call/hyper call) and request services such
as TPM emulation.

The main goal of this series is to add a driver for the vTPM defined by
the AMD SVSM spec [3]. The specification defines a protocol that a
SEV-SNP guest OS (running on VMPL >= 1) can use to discover and talk to
a vTPM emulated by the SVSM in the guest context, but at a more
privileged level (VMPL0).

This series is based on the RFC sent by James last year [1].
In the meantime, the patches have been maintained and tested in the
Coconut Linux fork [2] along with the work to support the vTPM
emulation in Coconut SVSM.

The first patch adds public APIs to use AMD SVSM vTPM. They use
SVSM_VTPM_QUERY call to probe for the vTPM device and SVSM_VTPM_CMD call
to execute vTPM operations as defined in the AMD SVSM spec [3].
The second patch adds an interface with helpers for the SVSM_VTPM_CMD calls
used by the vTPM protocol defined by the AMD SVSM spec and then used by the
third patch to implement the SVSM vTPM driver. The fourth patch simply
registers the platform device.

Since all SEV-SNP dependencies are now upstream, this series can be
applied directly to the Linus' tree.

These patches were tested in an AMD SEV-SNP guest running:
- a recent version of Coconut SVSM [4] containing an ephemeral vTPM
- a PoC [5] containing a stateful vTPM used for sealing/unsealing a LUKS key

Changelog:

v2 RFC -> v3
- Removed send_recv() ops and followed the ftpm driver implementing .status,
  .req_complete_mask, .req_complete_val, etc. [Jarkko]
  As we agreed, I will send another series with that patch to continue the
  discussion along with the changes in this driver and ftpm driver.
- Renamed fill/parse functions [Tom]
- Renamed helpers header and prefix to make clear it's related to the
  SVSM vTPM protocol and not to the TCG TPM Simulator
- Slimmed down snp_svsm_vtpm_probe() [Borislav]
- Removed link to the spec because those URLs are unstable [Borislav]
- Removed features check and any print related [Tom]
- Squashed "x86/sev: add SVSM call macros for the vTPM protocol" patch
  with the next one [Borislav]

v1 -> v2 RFC: https://lore.kernel.org/linux-integrity/20250228170720.144739-1-sgarzare@redhat.com/
- Added send_recv() tpm_class_ops callback
- Removed the intermediate tpm_platform.ko driver
- Renamed tpm_platform.h to tpm_tcgsim.h and included some API to fill
  TPM_SEND_COMMAND requests and parse responses from a device emulated using
  the TCG Simulatore reference implementation
- Added public API in x86/sev usable to discover and talk with the SVSM vTPM
- Added the tpm-svsm platform driver in driver/char/tpm/
- Fixed some SVSM TPM related issues (resp_size as u32, don't fail on
  features !=0, s/VTPM/vTPM)

v0 RFC -> v1: https://lore.kernel.org/linux-integrity/20241210143423.101774-1-sgarzare@redhat.com/
- Used SVSM_VTPM_QUERY to probe the TPM as Tom Lendacky suggested
- Changed references/links to TCG TPM repo since in the last year MS
  donated the reference TPM implementation to the TCG.
- Addressed Dov Murik's comments:
  https://lore.kernel.org/all/f7d0bd07-ba1b-894e-5e39-15fb1817bc8b@linux.ibm.com/
- Added a new patch with SVSM call macros for the vTPM protocol, following
  what we already have for SVSM_CORE and SVSM_ATTEST
- Rebased on v6.13-rc2

Thanks,
Stefano

[1] https://lore.kernel.org/all/acb06bc7f329dfee21afa1b2ff080fe29b799021.camel@linux.ibm.com/
[2] https://github.com/coconut-svsm/linux/tree/svsm
[3] "Secure VM Service Module for SEV-SNP Guests"
    Publication # 58019 Revision: 1.00
    https://www.amd.com/content/dam/amd/en/documents/epyc-technical-docs/specifications/58019.pdf
[4] https://github.com/coconut-svsm/svsm/commit/6522c67e1e414f192a6f014b122ca8a1066e3bf5
[5] https://github.com/stefano-garzarella/snp-svsm-vtpm

Stefano Garzarella (4):
  x86/sev: add SVSM vTPM probe/send_command functions
  svsm: add header with SVSM_VTPM_CMD helpers
  tpm: add SNP SVSM vTPM driver
  x86/sev: register tpm-svsm platform device

 arch/x86/include/asm/sev.h  |   7 ++
 include/linux/svsm_vtpm.h   | 141 ++++++++++++++++++++++++++++++++++
 arch/x86/coco/sev/core.c    |  39 ++++++++++
 drivers/char/tpm/tpm_svsm.c | 148 ++++++++++++++++++++++++++++++++++++
 drivers/char/tpm/Kconfig    |  10 +++
 drivers/char/tpm/Makefile   |   1 +
 6 files changed, 346 insertions(+)
 create mode 100644 include/linux/svsm_vtpm.h
 create mode 100644 drivers/char/tpm/tpm_svsm.c

---

## [2] Stefano Garzarella — 2025-03-11
*Subject: [PATCH v3 1/4] x86/sev: add SVSM vTPM probe/send_command functions*

Add two new functions to probe and send commands to the SVSM vTPM.
They leverage the two calls defined by the AMD SVSM specification [1]
for the vTPM protocol: SVSM_VTPM_QUERY and SVSM_VTPM_CMD.

Expose these functions to be used by other modules such as a tpm
driver.

[1] "Secure VM Service Module for SEV-SNP Guests"
    Publication # 58019 Revision: 1.00

Co-developed-by: James Bottomley <James.Bottomley@HansenPartnership.com>
Signed-off-by: James Bottomley <James.Bottomley@HansenPartnership.com>
Co-developed-by: Claudio Carvalho <cclaudio@linux.ibm.com>
Signed-off-by: Claudio Carvalho <cclaudio@linux.ibm.com>
Signed-off-by: Stefano Garzarella <sgarzare@redhat.com>
---
v3:
- removed link to the spec because those URLs are unstable [Borislav]
- squashed "x86/sev: add SVSM call macros for the vTPM protocol" patch
  in this one [Borislav]
- slimmed down snp_svsm_vtpm_probe() [Borislav]
- removed features check and any print related [Tom]
---
 arch/x86/include/asm/sev.h |  7 +++++++
 arch/x86/coco/sev/core.c   | 31 +++++++++++++++++++++++++++++++
 2 files changed, 38 insertions(+)

diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index ba7999f66abe..09471d058ce5 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -384,6 +384,10 @@ struct svsm_call {
 #define SVSM_ATTEST_SERVICES		0
 #define SVSM_ATTEST_SINGLE_SERVICE	1
 
+#define SVSM_VTPM_CALL(x)		((2ULL << 32) | (x))
+#define SVSM_VTPM_QUERY			0
+#define SVSM_VTPM_CMD			1
+
 #ifdef CONFIG_AMD_MEM_ENCRYPT
 
 extern u8 snp_vmpl;
@@ -481,6 +485,9 @@ void snp_msg_free(struct snp_msg_desc *mdesc);
 int snp_send_guest_request(struct snp_msg_desc *mdesc, struct snp_guest_req *req,
 			   struct snp_guest_request_ioctl *rio);
 
+bool snp_svsm_vtpm_probe(void);
+int snp_svsm_vtpm_send_command(u8 *buffer);
+
 void __init snp_secure_tsc_prepare(void);
 void __init snp_secure_tsc_init(void);
 
diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index 96c7bc698e6b..2166bdff88b7 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -2628,6 +2628,37 @@ static int snp_issue_guest_request(struct snp_guest_req *req, struct snp_req_dat
 	return ret;
 }
 
+bool snp_svsm_vtpm_probe(void)
+{
+	struct svsm_call call = {};
+
+	/* The vTPM device is available only if a SVSM is present */
+	if (!snp_vmpl)
+		return false;
+
+	call.caa = svsm_get_caa();
+	call.rax = SVSM_VTPM_CALL(SVSM_VTPM_QUERY);
+
+	if (svsm_perform_call_protocol(&call))
+		return false;
+
+	/* Check platform commands contains TPM_SEND_COMMAND - platform command 8 */
+	return (call.rcx_out & BIT_ULL(8)) == BIT_ULL(8);
+}
+EXPORT_SYMBOL_GPL(snp_svsm_vtpm_probe);
+
+int snp_svsm_vtpm_send_command(u8 *buffer)
+{
+	struct svsm_call call = {};
+
+	call.caa = svsm_get_caa();
+	call.rax = SVSM_VTPM_CALL(SVSM_VTPM_CMD);
+	call.rcx = __pa(buffer);
+
+	return svsm_perform_call_protocol(&call);
+}
+EXPORT_SYMBOL_GPL(snp_svsm_vtpm_send_command);
+
 static struct platform_device sev_guest_device = {
 	.name		= "sev-guest",
 	.id		= -1,

---

## [3] Stefano Garzarella — 2025-03-11
*Subject: [PATCH v3 2/4] svsm: add header with SVSM_VTPM_CMD helpers*

Helpers for the SVSM_VTPM_CMD calls used by the vTPM protocol defined by
the AMD SVSM spec [1].

The vTPM protocol follows the Official TPM 2.0 Reference Implementation
(originally by Microsoft, now part of the TCG) simulator protocol.

[1] "Secure VM Service Module for SEV-SNP Guests"
    Publication # 58019 Revision: 1.00

Co-developed-by: James Bottomley <James.Bottomley@HansenPartnership.com>
Signed-off-by: James Bottomley <James.Bottomley@HansenPartnership.com>
Co-developed-by: Claudio Carvalho <cclaudio@linux.ibm.com>
Signed-off-by: Claudio Carvalho <cclaudio@linux.ibm.com>
Signed-off-by: Stefano Garzarella <sgarzare@redhat.com>
---
v3:
- renamed header and prefix to make clear it's related to the SVSM vTPM
  protocol
- renamed fill/parse functions [Tom]
- removed link to the spec because those URLs are unstable [Borislav]
---
 include/linux/svsm_vtpm.h | 141 ++++++++++++++++++++++++++++++++++++++
 1 file changed, 141 insertions(+)
 create mode 100644 include/linux/svsm_vtpm.h

diff --git a/include/linux/svsm_vtpm.h b/include/linux/svsm_vtpm.h
new file mode 100644
index 000000000000..2ce9b1cb827e
--- /dev/null
+++ b/include/linux/svsm_vtpm.h
@@ -0,0 +1,141 @@
+/* SPDX-License-Identifier: GPL-2.0-only */
+/*
+ * Copyright (C) 2023 James.Bottomley@HansenPartnership.com
+ * Copyright (C) 2025 Red Hat, Inc. All Rights Reserved.
+ *
+ * Helpers for the SVSM_VTPM_CMD calls used by the vTPM protocol defined by the
+ * AMD SVSM spec [1].
+ *
+ * The vTPM protocol follows the Official TPM 2.0 Reference Implementation
+ * (originally by Microsoft, now part of the TCG) simulator protocol.
+ *
+ * [1] "Secure VM Service Module for SEV-SNP Guests"
+ *     Publication # 58019 Revision: 1.00
+ */
+#ifndef _SVSM_VTPM_H_
+#define _SVSM_VTPM_H_
+
+#include <linux/errno.h>
+#include <linux/string.h>
+#include <linux/types.h>
+
+/*
+ * The current TCG Simulator TPM commands we support.  The complete list is
+ * in the TcpTpmProtocol header:
+ *
+ * https://github.com/TrustedComputingGroup/TPM/blob/main/TPMCmd/Simulator/include/TpmTcpProtocol.h
+ */
+
+#define TPM_SEND_COMMAND		8
+#define TPM_SIGNAL_CANCEL_ON		9
+#define TPM_SIGNAL_CANCEL_OFF		10
+/*
+ * Any platform specific commands should be placed here and should start
+ * at 0x8000 to avoid clashes with the TCG Simulator protocol.  They should
+ * follow the same self describing buffer format below.
+ */
+
+#define SVSM_VTPM_MAX_BUFFER		4096 /* max req/resp buffer size */
+
+/**
+ * struct tpm_req - generic request header for single word command
+ *
+ * @cmd:	The command to send
+ */
+struct tpm_req {
+	u32 cmd;
+} __packed;
+
+/**
+ * struct tpm_resp - generic response header
+ *
+ * @size:	The response size (zero if nothing follows)
+ *
+ * Note: most TCG Simulator commands simply return zero here with no indication
+ * of success or failure.
+ */
+struct tpm_resp {
+	u32 size;
+} __packed;
+
+/**
+ * struct tpm_send_cmd_req - Structure for a TPM_SEND_COMMAND request
+ *
+ * @hdr:	The request header whit the command (must be TPM_SEND_COMMAND)
+ * @locality:	The locality
+ * @inbuf_size:	The size of the input buffer following
+ * @inbuf:	A buffer of size inbuf_size
+ *
+ * Note that TCG Simulator expects @inbuf_size to be equal to the size of the
+ * specific TPM command, otherwise an TPM_RC_COMMAND_SIZE error is
+ * returned.
+ */
+struct tpm_send_cmd_req {
+	struct tpm_req hdr;
+	u8 locality;
+	u32 inbuf_size;
+	u8 inbuf[];
+} __packed;
+
+/**
+ * struct tpm_send_cmd_req - Structure for a TPM_SEND_COMMAND response
+ *
+ * @hdr:	The response header whit the following size
+ * @outbuf:	A buffer of size hdr.size
+ */
+struct tpm_send_cmd_resp {
+	struct tpm_resp hdr;
+	u8 outbuf[];
+} __packed;
+
+/**
+ * svsm_vtpm_fill_cmd_req() - fill a struct tpm_send_cmd_req to be sent to SVSM
+ * @req: The struct tpm_send_cmd_req to fill
+ * @locality: The locality
+ * @buf: The buffer from where to copy the payload of the command
+ * @len: The size of the buffer
+ *
+ * Return: 0 on success, negative error code on failure.
+ */
+static inline int
+svsm_vtpm_fill_cmd_req(struct tpm_send_cmd_req *req, u8 locality,
+		       const u8 *buf, size_t len)
+{
+	if (len > SVSM_VTPM_MAX_BUFFER - sizeof(*req))
+		return -EINVAL;
+
+	req->hdr.cmd = TPM_SEND_COMMAND;
+	req->locality = locality;
+	req->inbuf_size = len;
+
+	memcpy(req->inbuf, buf, len);
+
+	return 0;
+}
+
+/**
+ * svsm_vtpm_parse_cmd_resp() - Parse a struct tpm_send_cmd_resp received from
+ * SVSM
+ * @resp: The struct tpm_send_cmd_resp to parse
+ * @buf: The buffer where to copy the response
+ * @len: The size of the buffer
+ *
+ * Return: buffer size filled with the response on success, negative error
+ * code on failure.
+ */
+static inline int
+svsm_vtpm_parse_cmd_resp(const struct tpm_send_cmd_resp *resp, u8 *buf,
+			 size_t len)
+{
+	if (len < resp->hdr.size)
+		return -E2BIG;
+
+	if (resp->hdr.size > SVSM_VTPM_MAX_BUFFER - sizeof(*resp))
+		return -EINVAL;  // Invalid response from the platform TPM
+
+	memcpy(buf, resp->outbuf, resp->hdr.size);
+
+	return resp->hdr.size;
+}
+
+#endif /* _SVSM_VTPM_H_ */

---

## [4] Stefano Garzarella — 2025-03-11
*Subject: [PATCH v3 3/4] tpm: add SNP SVSM vTPM driver*

Add driver for the vTPM defined by the AMD SVSM spec [1].

The specification defines a protocol that a SEV-SNP guest OS can use to
discover and talk to a vTPM emulated by the Secure VM Service Module (SVSM)
in the guest context, but at a more privileged level (VMPL0).

The new tpm-svsm platform driver uses two functions exposed by x86/sev
to verify that the device is actually emulated by the platform and to
send commands and receive responses.

The device cannot be hot-plugged/unplugged as it is emulated by the
platform, so we can use module_platform_driver_probe(). The probe
function will only check whether in the current runtime configuration,
SVSM is present and provides a vTPM.

This device does not support interrupts and sends responses to commands
synchronously. In order to have .recv() called just after .send() in
tpm_try_transmit(), the .status() callback returns 0, and both
.req_complete_mask and .req_complete_val are set to 0.

[1] "Secure VM Service Module for SEV-SNP Guests"
    Publication # 58019 Revision: 1.00

Signed-off-by: Stefano Garzarella <sgarzare@redhat.com>
---
v3:
- removed send_recv() ops and followed the ftpm driver implementing .status,
  .req_complete_mask, .req_complete_val, etc. [Jarkko]
- removed link to the spec because those URLs are unstable [Borislav]
---
 drivers/char/tpm/tpm_svsm.c | 148 ++++++++++++++++++++++++++++++++++++
 drivers/char/tpm/Kconfig    |  10 +++
 drivers/char/tpm/Makefile   |   1 +
 3 files changed, 159 insertions(+)
 create mode 100644 drivers/char/tpm/tpm_svsm.c

diff --git a/drivers/char/tpm/tpm_svsm.c b/drivers/char/tpm/tpm_svsm.c
new file mode 100644
index 000000000000..5540d0227eed
--- /dev/null
+++ b/drivers/char/tpm/tpm_svsm.c
@@ -0,0 +1,148 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/*
+ * Copyright (C) 2025 Red Hat, Inc. All Rights Reserved.
+ *
+ * Driver for the vTPM defined by the AMD SVSM spec [1].
+ *
+ * The specification defines a protocol that a SEV-SNP guest OS can use to
+ * discover and talk to a vTPM emulated by the Secure VM Service Module (SVSM)
+ * in the guest context, but at a more privileged level (usually VMPL0).
+ *
+ * [1] "Secure VM Service Module for SEV-SNP Guests"
+ *     Publication # 58019 Revision: 1.00
+ */
+
+#include <asm/sev.h>
+#include <linux/module.h>
+#include <linux/kernel.h>
+#include <linux/platform_device.h>
+#include <linux/svsm_vtpm.h>
+
+#include "tpm.h"
+
+struct tpm_svsm_priv {
+	u8 buffer[SVSM_VTPM_MAX_BUFFER];
+	u8 locality;
+};
+
+static int tpm_svsm_send(struct tpm_chip *chip, u8 *buf, size_t len)
+{
+	struct tpm_svsm_priv *priv = dev_get_drvdata(&chip->dev);
+	int ret;
+
+	ret = svsm_vtpm_fill_cmd_req((struct tpm_send_cmd_req *)priv->buffer,
+				     priv->locality, buf, len);
+	if (ret)
+		return ret;
+
+	/*
+	 * The SVSM call uses the same buffer for the command and for the
+	 * response, so after this call, the buffer will contain the response
+	 * that can be used by .recv() op.
+	 */
+	return snp_svsm_vtpm_send_command(priv->buffer);
+}
+
+static int tpm_svsm_recv(struct tpm_chip *chip, u8 *buf, size_t len)
+{
+	struct tpm_svsm_priv *priv = dev_get_drvdata(&chip->dev);
+
+	/*
+	 * The internal buffer contains the response after we send the command
+	 * to SVSM.
+	 */
+	return svsm_vtpm_parse_cmd_resp((struct tpm_send_cmd_resp *)priv->buffer,
+					buf, len);
+}
+
+static void tpm_svsm_cancel(struct tpm_chip *chip)
+{
+	/* not supported */
+}
+
+static u8 tpm_svsm_status(struct tpm_chip *chip)
+{
+	return 0;
+}
+
+static bool tpm_svsm_req_canceled(struct tpm_chip *chip, u8 status)
+{
+	return false;
+}
+
+static struct tpm_class_ops tpm_chip_ops = {
+	.flags = TPM_OPS_AUTO_STARTUP,
+	.recv = tpm_svsm_recv,
+	.send = tpm_svsm_send,
+	.cancel = tpm_svsm_cancel,
+	.status = tpm_svsm_status,
+	.req_complete_mask = 0,
+	.req_complete_val = 0,
+	.req_canceled = tpm_svsm_req_canceled,
+};
+
+static int __init tpm_svsm_probe(struct platform_device *pdev)
+{
+	struct device *dev = &pdev->dev;
+	struct tpm_svsm_priv *priv;
+	struct tpm_chip *chip;
+	int err;
+
+	if (!snp_svsm_vtpm_probe())
+		return -ENODEV;
+
+	priv = devm_kmalloc(dev, sizeof(*priv), GFP_KERNEL);
+	if (!priv)
+		return -ENOMEM;
+
+	/*
+	 * FIXME: before implementing locality we need to agree what it means
+	 * for the SNP SVSM vTPM
+	 */
+	priv->locality = 0;
+
+	chip = tpmm_chip_alloc(dev, &tpm_chip_ops);
+	if (IS_ERR(chip))
+		return PTR_ERR(chip);
+
+	dev_set_drvdata(&chip->dev, priv);
+
+	err = tpm2_probe(chip);
+	if (err)
+		return err;
+
+	err = tpm_chip_register(chip);
+	if (err)
+		return err;
+
+	dev_info(dev, "SNP SVSM vTPM %s device\n",
+		 (chip->flags & TPM_CHIP_FLAG_TPM2) ? "2.0" : "1.2");
+
+	return 0;
+}
+
+static void __exit tpm_svsm_remove(struct platform_device *pdev)
+{
+	struct tpm_chip *chip = platform_get_drvdata(pdev);
+
+	tpm_chip_unregister(chip);
+}
+
+/*
+ * tpm_svsm_remove() lives in .exit.text. For drivers registered via
+ * module_platform_driver_probe() this is ok because they cannot get unbound
+ * at runtime. So mark the driver struct with __refdata to prevent modpost
+ * triggering a section mismatch warning.
+ */
+static struct platform_driver tpm_svsm_driver __refdata = {
+	.remove = __exit_p(tpm_svsm_remove),
+	.driver = {
+		.name = "tpm-svsm",
+	},
+};
+
+module_platform_driver_probe(tpm_svsm_driver, tpm_svsm_probe);
+
+MODULE_DESCRIPTION("SNP SVSM vTPM Driver");
+MODULE_LICENSE("GPL");
+MODULE_ALIAS("platform:tpm-svsm");
diff --git a/drivers/char/tpm/Kconfig b/drivers/char/tpm/Kconfig
index 0fc9a510e059..fc3f1d10d31d 100644
--- a/drivers/char/tpm/Kconfig
+++ b/drivers/char/tpm/Kconfig
@@ -225,5 +225,15 @@ config TCG_FTPM_TEE
 	help
 	  This driver proxies for firmware TPM running in TEE.
 
+config TCG_SVSM
+	tristate "SNP SVSM vTPM interface"
+	depends on AMD_MEM_ENCRYPT
+	help
+	  This is a driver for the AMD SVSM vTPM protocol that a SEV-SNP guest
+	  OS can use to discover and talk to a vTPM emulated by the Secure VM
+	  Service Module (SVSM) in the guest context, but at a more privileged
+	  level (usually VMPL0).  To compile this driver as a module, choose M
+	  here; the module will be called tpm_svsm.
+
 source "drivers/char/tpm/st33zp24/Kconfig"
 endif # TCG_TPM
diff --git a/drivers/char/tpm/Makefile b/drivers/char/tpm/Makefile
index 9bb142c75243..52d9d80a0f56 100644
--- a/drivers/char/tpm/Makefile
+++ b/drivers/char/tpm/Makefile
@@ -44,3 +44,4 @@ obj-$(CONFIG_TCG_XEN) += xen-tpmfront.o
 obj-$(CONFIG_TCG_CRB) += tpm_crb.o
 obj-$(CONFIG_TCG_VTPM_PROXY) += tpm_vtpm_proxy.o
 obj-$(CONFIG_TCG_FTPM_TEE) += tpm_ftpm_tee.o
+obj-$(CONFIG_TCG_SVSM) += tpm_svsm.o

---

## [5] Stefano Garzarella — 2025-03-11
*Subject: [PATCH v3 4/4] x86/sev: register tpm-svsm platform device*

SNP platform can provide a vTPM device emulated by SVSM.

The "tpm-svsm" device can be handled by the platform driver added
by the previous commit in drivers/char/tpm/tpm_svsm.c

The driver will call snp_svsm_vtpm_probe() to check if SVSM is
present and if it's support the vTPM protocol.

Signed-off-by: Stefano Garzarella <sgarzare@redhat.com>
---
 arch/x86/coco/sev/core.c | 8 ++++++++
 1 file changed, 8 insertions(+)

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index 2166bdff88b7..a2383457889e 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -2664,6 +2664,11 @@ static struct platform_device sev_guest_device = {
 	.id		= -1,
 };
 
+static struct platform_device tpm_svsm_device = {
+	.name		= "tpm-svsm",
+	.id		= -1,
+};
+
 static int __init snp_init_platform_device(void)
 {
 	if (!cc_platform_has(CC_ATTR_GUEST_SEV_SNP))
@@ -2672,6 +2677,9 @@ static int __init snp_init_platform_device(void)
 	if (platform_device_register(&sev_guest_device))
 		return -ENODEV;
 
+	if (platform_device_register(&tpm_svsm_device))
+		return -ENODEV;
+
 	pr_info("SNP guest platform device initialized.\n");
 	return 0;
 }

---

## [6] Jarkko Sakkinen — 2025-03-11
*Subject: Re: [PATCH v3 1/4] x86/sev: add SVSM vTPM probe/send_command
 functions*

On Tue, Mar 11, 2025 at 10:42:22AM +0100, Stefano Garzarella wrote:
> Add two new functions to probe and send commands to the SVSM vTPM.
> They leverage the two calls defined by the AMD SVSM specification [1]

Since this is an exported symbol, it'd be a good practice document
snp_svsm_vtpm_probe().

> +bool snp_svsm_vtpm_probe(void)
> +{

I supposed CAA is some kind of shared memory area for host and VM?

> +
> +	if (svsm_perform_call_protocol(&call))

Ditto.

> +int snp_svsm_vtpm_send_command(u8 *buffer)
> +{

That said, these are rather self-documenting (i.e, nice and clean).

BR, Jarkko

---

## [7] Jarkko Sakkinen — 2025-03-11
*Subject: Re: [PATCH v3 2/4] svsm: add header with SVSM_VTPM_CMD helpers*

On Tue, Mar 11, 2025 at 10:42:23AM +0100, Stefano Garzarella wrote:
> Helpers for the SVSM_VTPM_CMD calls used by the vTPM protocol defined by
> the AMD SVSM spec [1].

Across the board below data structures: I'd svsm_vtpm_ prefix them.
The rational is quite practical: it would easier to grep them later
on.

> +/**
> + * struct tpm_req - generic request header for single word command

__packed is useless here.

> +
> +/**

Ditto.

> +
> +/**

Useless nesting that makes this obfuscated: you can just as well put
that single field here, i.e.

	u32 cmd;

> +	u8 locality;
> +	u32 inbuf_size;

Why not just buf?

> +} __packed;

Since we don't care about TCG Simulator compatibility I'd expect that
these are ordered in a way that they align nicely. E.g.,

struct svsm_vtpm_request {
	u32 command;
	u16 locality;
	u16 buffer_size;
	u8 buffer[];
};

64k should enough for any possible TPM command.

> +
> +/**

Why this does not have size? Here also __packed is useless even with the
pre-existing layout, and something like svsm_tpm_response would be a
factor more reasonable name.

> +
> +/**

> + * @req: The struct tpm_send_cmd_req to fill
> + * @locality: The locality

svsm_vtpm_fill_request()

> +{
> +	if (len > SVSM_VTPM_MAX_BUFFER - sizeof(*req))

svsm_vtpm_parse_response()

> +{
> +	if (len < resp->hdr.size)

BR, Jarkko

---

## [8] Stefano Garzarella — 2025-03-12
*Subject: Re: [PATCH v3 1/4] x86/sev: add SVSM vTPM probe/send_command
 functions*

On Tue, Mar 11, 2025 at 11:56:23AM +0200, Jarkko Sakkinen wrote:
>On Tue, Mar 11, 2025 at 10:42:22AM +0100, Stefano Garzarella wrote:
>> Add two new functions to probe and send commands to the SVSM vTPM.

Yes, you are right, since the others were not documented, I had not 
added it, but I agree with you, I'll do in v4.

>
>> +bool snp_svsm_vtpm_probe(void)

Not with the host, but with SVSM, which is the firmware running in the 
guest, but at a higher privilege level (VMPL) than the kernel, where, 
for example, the vTPM is emulated.

BTW, yep it is a shared memory defined by the SVSM calling convention.
 From AMD SVSM specification:

   5 Calling Convention

     Each call to the SVSM conveys data through a combination of the
     SVSM Calling Area (whose address was first configured through the
     SVSM_CAA field of the secrets page) and registers. Use of the
     Calling Area is necessary for the SVSM to detect the difference
     between a call that was issued by the guest and a spurious
     invocation by a poorly behaved host. Registers are used for all
     other parameters.
     The initially configured SVSM Calling Area is a page of memory that
     lies outside the initial SVSM memory range and has not had its VMPL
     permissions restricted in any way. The address is guaranteed to be
     aligned to a 4 KB boundary, so the remainder of the page may be used
     by the guest for memory-based parameter passing if desired.
     The contents of the Calling Area are described in the following
     table:

     Table 2: Calling Area
     Byte      Size     Name                Description
     Offset

     0x000     1 byte   SVSM_CALL_PENDING   Indicates whether a call has
                                            been requested by the guest
                                            (0=no call requested, 1=call
                                            requested).
     0x001     1 byte   SVSM_MEM_AVAILABLE  Free memory is available to
                                            be withdrawn.
     0x002     6 byte                       Reserved. The SVSM is not
                                            required to verify that
                                            these bytes are 0.

>
>> +

Ack.

>
>> +int snp_svsm_vtpm_send_command(u8 *buffer)

Thanks for the review!
Stefano

---

## [9] Stefano Garzarella — 2025-03-12
*Subject: Re: [PATCH v3 2/4] svsm: add header with SVSM_VTPM_CMD helpers*

On Tue, Mar 11, 2025 at 12:07:55PM +0200, Jarkko Sakkinen wrote:
>On Tue, Mar 11, 2025 at 10:42:23AM +0100, Stefano Garzarella wrote:
>> Helpers for the SVSM_VTPM_CMD calls used by the vTPM protocol defined by

I see, I'll fix in v4.

>
>> +/**

Ack, for both.

>
>> +

Yep, I see. I'll remove tpm_req and tpm_resp since for now we support
only TPM_SEND_COMMAND, if in the future we will support other requests
we can think of re-introduce them if needed.

>
>> +	u8 locality;

I can change in `buf` and `size`.

>
>> +} __packed;

Maybe I should add in the documentation that this structure is defined
by the AMD SVSM spec.

This is where request and response for TPM_SEND_COMMAND are defined:

   8.2.1 TPM_SEND_COMMAND
     Execute a TPM command and return the results.

     For TPM_SEND_COMMAND, platform command 8, the request buffer is
     specified according to the format of the following table.

     Table 16: TPM_SEND_COMMAND Request Structure

     Byte      Size         Meaning
     Offset    (Bytes)
     0x000     4            Platform command (8)
     0x004     1            Locality (must-be-0)
     0x005     4            TPM Command size (in bytes)
     0x009     Variable     TPM Command

     The response buffer is specified according to the format of the
     following table.

     Table 17: TPM_SEND_COMMAND Response Structure

     Byte      Size         Meaning
     Offset    (Bytes)
     0x000     4            Response size (in bytes)
     0x004     Variable     Response

>
>struct svsm_vtpm_request {

Because it's "obfuscated" as you pointed out in the request :-)
The size is in the header, but I'll fix with something like this:

struct svsm_tpm_response {
     u32 size;
     u8 outbuf[];
} __packed;

>
>> +

About the naming, I added "cmd" because in the future we can support
also other requests/responses different from TPM_SEND_COMMAND, like
TPM_SIGNAL_HASH_DATA, TPM_REMOTE_HANDSHAKE, TPM_SET_ALTERNATIVE_RESULT
as specified in the AMD SVSM spec.

For now it's true that we support only TPM_SEND_COMMAND, so I can avoid
`cmd`, but if we will need to support the other requests in the future,
we may need to differentiate them.

Would be okay to have svsm_vtpm_cmd_[request|response], 
svsm_vtpm_fill_cmd_request(), svsm_vtpm_parse_cmd_response() ?
Or do you prefer to avoid "_cmd_"?
Not a strong opinion on my side.

Thanks,
Stefano

>
>> +{

---

## [10] Jarkko Sakkinen — 2025-03-14
*Subject: Re: [PATCH v3 1/4] x86/sev: add SVSM vTPM probe/send_command
 functions*

On Wed, Mar 12, 2025 at 11:56:06AM +0100, Stefano Garzarella wrote:
> On Tue, Mar 11, 2025 at 11:56:23AM +0200, Jarkko Sakkinen wrote:
> > On Tue, Mar 11, 2025 at 10:42:22AM +0100, Stefano Garzarella wrote:

Sure, don't worry about it! Let's just cycle this enough rounds that
it fits well...

> Stefano

BR, Jarkko

---

## [11] Tom Lendacky — 2025-03-14
*Subject: Re: [PATCH v3 1/4] x86/sev: add SVSM vTPM probe/send_command
 functions*

On 3/11/25 04:42, Stefano Garzarella wrote:
> Add two new functions to probe and send commands to the SVSM vTPM.
> They leverage the two calls defined by the AMD SVSM specification [1]

One minor nit below, otherwise:

Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>

> ---
> v3:

It's a bool function, so this could simplified to just:

	return call.rcx_out & BIT_ULL(8);

Thanks,
Tom

> +}
> +EXPORT_SYMBOL_GPL(snp_svsm_vtpm_probe);

---

## [12] Tom Lendacky — 2025-03-14
*Subject: Re: [PATCH v3 3/4] tpm: add SNP SVSM vTPM driver*

On 3/11/25 04:42, Stefano Garzarella wrote:
> Add driver for the vTPM defined by the AMD SVSM spec [1].
> 

Typically the "asm" includes are after the "linux" includes and separated
from each other by a blank line.

> +#include <linux/module.h>
> +#include <linux/kernel.h>

I'm wondering if the buffer shouldn't be a pointer to a page of memory
that is a page allocation. This ensures it is always page-aligned in case
the tpm_svsm_priv structure is ever modified.

As it is, the kmalloc() allocation will be page-aligned because of the
size, but it might be safer, dunno, your call.

Thanks,
Tom

> +
> +static int tpm_svsm_send(struct tpm_chip *chip, u8 *buf, size_t len)

---

## [13] Tom Lendacky — 2025-03-14
*Subject: Re: [PATCH v3 4/4] x86/sev: register tpm-svsm platform device*

On 3/11/25 04:42, Stefano Garzarella wrote:
> SNP platform can provide a vTPM device emulated by SVSM.
> 

You could avoid registering the device if an SVSM isn't present. Not sure
if that is desirable or not.

Thanks,
Tom

>  	pr_info("SNP guest platform device initialized.\n");
>  	return 0;

---

## [14] Jarkko Sakkinen — 2025-03-17
*Subject: Re: [PATCH v3 4/4] x86/sev: register tpm-svsm platform device*

On Fri, Mar 14, 2025 at 11:56:31AM -0500, Tom Lendacky wrote:
> On 3/11/25 04:42, Stefano Garzarella wrote:
> > SNP platform can provide a vTPM device emulated by SVSM.

Is there any use for the device if an SVSM isn't present? :-)

I'd judge it based on that...

> 
> Thanks,

BR, Jarkko

---

## [15] Jarkko Sakkinen — 2025-03-17
*Subject: Re: [PATCH v3 1/4] x86/sev: add SVSM vTPM probe/send_command
 functions*

On Fri, Mar 14, 2025 at 10:27:07AM -0500, Tom Lendacky wrote:
> On 3/11/25 04:42, Stefano Garzarella wrote:
> > Add two new functions to probe and send commands to the SVSM vTPM.

Or perhaps even just "call.rcx_out & 0x100". I don't think BIT_ULL()
here brings much additional clarity or anything useful...


> 
> Thanks,

BR, Jarkko

---

## [16] Jarkko Sakkinen — 2025-03-17
*Subject: Re: [PATCH v3 3/4] tpm: add SNP SVSM vTPM driver*

On Fri, Mar 14, 2025 at 11:48:11AM -0500, Tom Lendacky wrote:
> On 3/11/25 04:42, Stefano Garzarella wrote:
> > Add driver for the vTPM defined by the AMD SVSM spec [1].

This was good catch. There's actually two issues here:

1. SVSM_VTPM_MAX_BUFFER is same as page size.
2. SVSM_VTPM_MAX_BUFFER is IMHO defined in wrong patch 2/4.

So this constant would be needed, it should be appeneded in this patch,
not in 2/4 because it has direct effect on implementation of the driver.

I'd personally support the idea of removing this constant altogether
and use alloc_page() (i.e., same as you suggested).

kmalloc() does do the "right thing here but it is still extra
unnecessary layer of random stuff on top...

> 
> Thanks,

BR, Jarkko

---

## [17] Stefano Garzarella — 2025-03-18
*Subject: Re: [PATCH v3 1/4] x86/sev: add SVSM vTPM probe/send_command
 functions*

On Mon, Mar 17, 2025 at 03:36:26PM +0200, Jarkko Sakkinen wrote:
>On Fri, Mar 14, 2025 at 10:27:07AM -0500, Tom Lendacky wrote:
>> On 3/11/25 04:42, Stefano Garzarella wrote:

Thanks!

>>
>> > ---

Sure.

>
>Or perhaps even just "call.rcx_out & 0x100". I don't think BIT_ULL()

I can do that, I slightly prefer BIT_ULL() macro, but I don't have a 
strong opinion on my side.
@Borislav since you suggested it, WDYT?

Thanks,
Stefano

---

## [18] Stefano Garzarella — 2025-03-18
*Subject: Re: [PATCH v3 3/4] tpm: add SNP SVSM vTPM driver*

On Mon, Mar 17, 2025 at 03:43:18PM +0200, Jarkko Sakkinen wrote:
>On Fri, Mar 14, 2025 at 11:48:11AM -0500, Tom Lendacky wrote:
>> On 3/11/25 04:42, Stefano Garzarella wrote:

Yep, I already fixed it in v4, since I found that issue while
backporting this patch to CentOS 9.

>>
>> > +#include <linux/module.h>

@Tom Should that buffer really page aligned?

I couldn't find anything in the specification. IIRC edk2 also doesn't
allocate it aligned, and the code in SVSM already handles the case when
this is not aligned.

So if it is to be aligned to the pages, we should reinforce it in SVSM
(spec/code) and also fix edk2.

Or was yours a suggestion for performance/optimization?

>>
>> As it is, the kmalloc() allocation will be page-aligned because of the

I put it in patch 2 because IIUC it should be part of the SVSM
specification (the size, not the alignment).

>
>So this constant would be needed, it should be appeneded in this patch,

Do you think it's necessary, even though alignment is not required?
(I'm still not clear if it's a requirement, see above)

>
>kmalloc() does do the "right thing here but it is still extra

Yes, if it has to be aligned I completely agree. I would like to use
devm_ functions to keep the driver simple. Do you think
devm_get_free_pages() might be a good alternative to alloc_page()?

Thanks,
Stefano

---

## [19] Stefano Garzarella — 2025-03-18
*Subject: Re: [PATCH v3 4/4] x86/sev: register tpm-svsm platform device*

On Mon, Mar 17, 2025 at 03:34:10PM +0200, Jarkko Sakkinen wrote:
>On Fri, Mar 14, 2025 at 11:56:31AM -0500, Tom Lendacky wrote:
>> On 3/11/25 04:42, Stefano Garzarella wrote:

I tried to keep the logic of whether or not the driver is needed all in 
the tpm_svsm_probe()/snp_svsm_vtpm_probe() (where I check for SVSM).
If you prefer to move some pieces here, though, I'm open.

Thanks,
Stefano

---

## [20] Tom Lendacky — 2025-03-18
*Subject: Re: [PATCH v3 3/4] tpm: add SNP SVSM vTPM driver*

On 3/18/25 05:38, Stefano Garzarella wrote:
> On Mon, Mar 17, 2025 at 03:43:18PM +0200, Jarkko Sakkinen wrote:
>> On Fri, Mar 14, 2025 at 11:48:11AM -0500, Tom Lendacky wrote:

No reason other than the size of the buffer is the size of a page.
Allocating a page provides a page that is dedicated to the buffer for
the SVSM. To me it just makes sense to keep it separate from any driver
related data. Just a suggestion, not a requirement, and no need to
update the spec.

Thanks,
Tom

> 
>>>

---

## [21] Stefano Garzarella — 2025-03-18
*Subject: Re: [PATCH v3 3/4] tpm: add SNP SVSM vTPM driver*

On Tue, Mar 18, 2025 at 09:54:31AM -0500, Tom Lendacky wrote:
>On 3/18/25 05:38, Stefano Garzarella wrote:
>> On Mon, Mar 17, 2025 at 03:43:18PM +0200, Jarkko Sakkinen wrote:

I see, thanks for the clarification!
I saw that with devm_get_free_pages() I can easily allocate a 
resource-managed page, so I'll do that in v4.

Thanks,
Stefano

>
>Thanks,

---

## [22] Jason Gunthorpe — 2025-03-19
*Subject: Re: [PATCH v3 3/4] tpm: add SNP SVSM vTPM driver*

On Tue, Mar 18, 2025 at 05:18:53PM +0100, Stefano Garzarella wrote:

> I see, thanks for the clarification!
> I saw that with devm_get_free_pages() I can easily allocate a

As a general note you should just use kmalloc these days, even for
PAGE_SIZE. It is efficient and OK.

Having a struct that is PAGE_SIZE+1 is not efficient and will waste
a page of memory. That should be avoided ..

Jason

---

## [23] Stefano Garzarella — 2025-03-20
*Subject: Re: [PATCH v3 3/4] tpm: add SNP SVSM vTPM driver*

On Wed, Mar 19, 2025 at 08:44:22PM -0300, Jason Gunthorpe wrote:
>On Tue, Mar 18, 2025 at 05:18:53PM +0100, Stefano Garzarella wrote:
>

Thanks for sharing!

I think I'll stay with devm_get_free_pages() just because if it's
page aligned (with kmalloc I'm not sure if I have a way to ensure it), 
it can be a bitter faster for SVSM to map/unmap it on every command.

>
>Having a struct that is PAGE_SIZE+1 is not efficient and will waste

Got it, I will definitely split the buffer allocation from the priv.

Thanks,
Stefano

---

## [24] Jarkko Sakkinen — 2025-03-20
*Subject: Re: [PATCH v3 3/4] tpm: add SNP SVSM vTPM driver*

On Tue, Mar 18, 2025 at 11:38:54AM +0100, Stefano Garzarella wrote:
> On Mon, Mar 17, 2025 at 03:43:18PM +0200, Jarkko Sakkinen wrote:
> >On Fri, Mar 14, 2025 at 11:48:11AM -0500, Tom Lendacky wrote:

If the question is whether I would NAK based on using kzalloc(). Likely
not but still using page allocator would be more lean :-)

> 
> >

Yes, I think it could be used here.

> 
> Thanks,

BR, Jarkko

---

## [25] Jarkko Sakkinen — 2025-03-20
*Subject: Re: [PATCH v3 3/4] tpm: add SNP SVSM vTPM driver*

On Wed, Mar 19, 2025 at 08:44:22PM -0300, Jason Gunthorpe wrote:
> On Tue, Mar 18, 2025 at 05:18:53PM +0100, Stefano Garzarella wrote:
> 

Yeah, kzalloc() takes care of this magic. As said, kzalloc() vs
alloc_page() is not an existential question for this patch set :-)

I just would personally use alloc_page(). If nothing else, it does
have some super cosmetic benefits e.g., thinner call stack (when
needing to debug deep, which sometimes happens).

> 
> Jason

BR, Jarkko

---

## [26] Jarkko Sakkinen — 2025-03-20
*Subject: Re: [PATCH v3 4/4] x86/sev: register tpm-svsm platform device*

On Tue, Mar 18, 2025 at 11:44:05AM +0100, Stefano Garzarella wrote:
> On Mon, Mar 17, 2025 at 03:34:10PM +0200, Jarkko Sakkinen wrote:
> > On Fri, Mar 14, 2025 at 11:56:31AM -0500, Tom Lendacky wrote:

OK good point, thanks! Let's look the update as a whole and not touch
on this. There's already quite a few pieces moving. Ignore this for
the moment :-)

> 
> Thanks,

BR, Jarkko

---

## [27] Jarkko Sakkinen — 2025-03-20
*Subject: Re: [PATCH v3 1/4] x86/sev: add SVSM vTPM probe/send_command
 functions*

On Tue, Mar 18, 2025 at 11:07:57AM +0100, Stefano Garzarella wrote:
> On Mon, Mar 17, 2025 at 03:36:26PM +0200, Jarkko Sakkinen wrote:
> > On Fri, Mar 14, 2025 at 10:27:07AM -0500, Tom Lendacky wrote:

Either goes for me. Sorry for nitpicking that :-) The first comment
stil applies.

> 
> Thanks,

BR, Jarkko

---

## [28] Borislav Petkov — 2025-03-20
*Subject: Re: [PATCH v3 1/4] x86/sev: add SVSM vTPM probe/send_command
 functions*

On Thu, Mar 20, 2025 at 05:03:09PM +0200, Jarkko Sakkinen wrote:
> > I can do that, I slightly prefer BIT_ULL() macro, but I don't have a strong
> > opinion on my side.

Bit 8 is a lot better than 0x100.

Let's give a better example:

0x0000000008000000

or

BIT_ULL(27)

:-)

While I'm here: I'm guessing I'll route patches 1 and 4 through tip once
they're ready to go and give Jarkko an immutable branch he can base the other
two ontop.

Agreed?

Thx.

---

## [29] Jarkko Sakkinen — 2025-03-20
*Subject: Re: [PATCH v3 1/4] x86/sev: add SVSM vTPM probe/send_command
 functions*

On Thu, Mar 20, 2025 at 06:16:19PM +0100, Borislav Petkov wrote:
> On Thu, Mar 20, 2025 at 05:03:09PM +0200, Jarkko Sakkinen wrote:
> > > I can do that, I slightly prefer BIT_ULL() macro, but I don't have a strong

Sure, I'm fine with using BIT_ULL() :-)

> 
> While I'm here: I'm guessing I'll route patches 1 and 4 through tip once

Works for me.

> 
> Thx.

BR, Jarkko

---

## [30] Stefano Garzarella — 2025-03-21
*Subject: Re: [PATCH v3 1/4] x86/sev: add SVSM vTPM probe/send_command
 functions*

On Thu, Mar 20, 2025 at 07:30:43PM +0200, Jarkko Sakkinen wrote:
>On Thu, Mar 20, 2025 at 06:16:19PM +0100, Borislav Petkov wrote:
>> On Thu, Mar 20, 2025 at 05:03:09PM +0200, Jarkko Sakkinen wrote:

Yeah, we all agree :-)

>
>>

Just a note, patch 2 adds `include/linux/svsm_vtpm.h`, that file is 
basically a translation of the AMD SVSM specification into structures 
and functions used to communicate with SVSM in the way it is defined by 
the specification.

I realized that the file does not fall under any section of MAINTAINERS.
How do you suggest we proceed?

Should we create an SVSM section to maintain it, including the TPM 
driver and future other drivers,etc.?

Or include it in other sections? Which one in this case?

I'm willing to help both as a sub-maintainer and reviewer of course, but 
I would like your advice.

Thanks,
Stefano

---

## [31] Borislav Petkov — 2025-03-21
*Subject: Re: [PATCH v3 1/4] x86/sev: add SVSM vTPM probe/send_command
 functions*

On Fri, Mar 21, 2025 at 10:01:17AM +0100, Stefano Garzarella wrote:
> Just a note, patch 2 adds `include/linux/svsm_vtpm.h`, that file is
> basically a translation of the AMD SVSM specification into structures and

This all belongs to the TPM drivers, right?

I.e., drivers/char/tpm/

So I guess add that header to the TPM DEVICE DRIVER section if the gents there
are fine with it...

---

## [32] Jarkko Sakkinen — 2025-03-22
*Subject: Re: [PATCH v3 1/4] x86/sev: add SVSM vTPM probe/send_command
 functions*

On Fri, Mar 21, 2025 at 11:05:20PM +0100, Borislav Petkov wrote:
> On Fri, Mar 21, 2025 at 10:01:17AM +0100, Stefano Garzarella wrote:
> > Just a note, patch 2 adds `include/linux/svsm_vtpm.h`, that file is

It's fine for me but I'd suggest to rename the header as "tpm_svsm.h".
Then this will already provide coverage:

https://web.git.kernel.org/pub/scm/linux/kernel/git/jarkko/linux-tpmdd.git/commit/?id=a2fbcecc7027944a2ce447d4dd72725c5822321f


> 
> -- 

BR, Jarkko

---

## [33] Stefano Garzarella — 2025-03-24
*Subject: Re: [PATCH v3 1/4] x86/sev: add SVSM vTPM probe/send_command functions*

On Sat, Mar 22, 2025 at 10:17:03PM +0200, Jarkko Sakkinen wrote:
>On Fri, Mar 21, 2025 at 11:05:20PM +0100, Borislav Petkov wrote:
>> On Fri, Mar 21, 2025 at 10:01:17AM +0100, Stefano Garzarella wrote:

For now yes, we may have other devices in the future, but we can think
about that later.

>>
>> I.e., drivers/char/tpm/

Great, I'll rename it and send v4.

Thanks,
Stefano

---
