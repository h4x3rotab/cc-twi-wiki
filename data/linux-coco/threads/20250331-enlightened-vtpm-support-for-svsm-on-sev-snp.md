---
title: 'Enlightened vTPM support for SVSM on SEV-SNP'
date: 2025-03-31
last_reply: 2025-04-01
message_count: 16
participants: ['Stefano Garzarella', 'Tom Lendacky', 'Jarkko Sakkinen', 'Dionna Amalie Glaze', 'James Bottomley']
---

## [1] Stefano Garzarella — 2025-03-31

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

v4 -> v5
- Added stubs when !CONFIG_AMD_MEM_ENCRYPT [Dionna]
- Added Jarkko's R-b on patches 1 and 2
- Removed cancel/status/req_* ops after rebase on master that cotains
  commit 980a573621ea ("tpm: Make chip->{status,cancel,req_canceled} opt")

v3 -> v4: https://lore.kernel.org/linux-integrity/20250324104653.138663-1-sgarzare@redhat.com/
- Added more documentation around public API [Jarkko]
- Simplified TPM_SEND_COMMAND check [Tom/Jarkko]
- Renamed header in tpm_svsm.h so it will fall under TPM DEVICE DRIVER
  section [Borislav, Jarkko]
- Fixed several comments to improve svsm_vtpm_ helpers and structures [Jarkko]
- Moved "asm" includes after the "linux" includes [Tom]
- Allocated buffer used in the driver separately [Tom/Jarkko/Jason]
- Explained better why we register tpm-svsm device anyway in the commit message

v2 RFC -> v3: https://lore.kernel.org/linux-integrity/20250311094225.35129-1-sgarzare@redhat.com/
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

 arch/x86/include/asm/sev.h  |   9 +++
 include/linux/tpm_svsm.h    | 149 ++++++++++++++++++++++++++++++++++++
 arch/x86/coco/sev/core.c    |  67 ++++++++++++++++
 drivers/char/tpm/tpm_svsm.c | 135 ++++++++++++++++++++++++++++++++
 drivers/char/tpm/Kconfig    |  10 +++
 drivers/char/tpm/Makefile   |   1 +
 6 files changed, 371 insertions(+)
 create mode 100644 include/linux/tpm_svsm.h
 create mode 100644 drivers/char/tpm/tpm_svsm.c

---

## [2] Stefano Garzarella — 2025-03-31
*Subject: [PATCH v5 1/4] x86/sev: add SVSM vTPM probe/send_command functions*

From: Stefano Garzarella <sgarzare@redhat.com>

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
Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>
Reviewed-by: Jarkko Sakkinen <jarkko@kernel.org>
Signed-off-by: Stefano Garzarella <sgarzare@redhat.com>
---
v5:
- added stubs when !CONFIG_AMD_MEM_ENCRYPT [Dionna]
- added Jarkko's R-b
v4:
- added Tom's R-b
- added functions documentation [Jarkko]
- simplified TPM_SEND_COMMAND check [Tom/Jarkko]
v3:
- removed link to the spec because those URLs are unstable [Borislav]
- squashed "x86/sev: add SVSM call macros for the vTPM protocol" patch
  in this one [Borislav]
- slimmed down snp_svsm_vtpm_probe() [Borislav]
- removed features check and any print related [Tom]
---
 arch/x86/include/asm/sev.h |  9 ++++++
 arch/x86/coco/sev/core.c   | 59 ++++++++++++++++++++++++++++++++++++++
 2 files changed, 68 insertions(+)

diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index ba7999f66abe..ba7a0a327afb 100644
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
 
@@ -524,6 +531,8 @@ static inline struct snp_msg_desc *snp_msg_alloc(void) { return NULL; }
 static inline void snp_msg_free(struct snp_msg_desc *mdesc) { }
 static inline int snp_send_guest_request(struct snp_msg_desc *mdesc, struct snp_guest_req *req,
 					 struct snp_guest_request_ioctl *rio) { return -ENODEV; }
+static inline bool snp_svsm_vtpm_probe(void) { return false; }
+static inline int snp_svsm_vtpm_send_command(u8 *buffer) { return -ENODEV; }
 static inline void __init snp_secure_tsc_prepare(void) { }
 static inline void __init snp_secure_tsc_init(void) { }
 
diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index b0c1a7a57497..efb43c9d3d30 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -2625,6 +2625,65 @@ static int snp_issue_guest_request(struct snp_guest_req *req, struct snp_req_dat
 	return ret;
 }
 
+/**
+ * snp_svsm_vtpm_probe() - Probe if SVSM provides a vTPM device
+ *
+ * This function checks that there is SVSM and that it supports at least
+ * TPM_SEND_COMMAND which is the only request we use so far.
+ *
+ * Return: true if the platform provides a vTPM SVSM device, false otherwise.
+ */
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
+	return call.rcx_out & BIT_ULL(8);
+}
+EXPORT_SYMBOL_GPL(snp_svsm_vtpm_probe);
+
+/**
+ * snp_svsm_vtpm_send_command() - execute a vTPM operation on SVSM
+ * @buffer: A buffer used to both send the command and receive the response.
+ *
+ * This function executes a SVSM_VTPM_CMD call as defined by
+ * "Secure VM Service Module for SEV-SNP Guests" Publication # 58019 Revision: 1.00
+ *
+ * All command request/response buffers have a common structure as specified by
+ * the following table:
+ *     Byte      Size       In/Out    Description
+ *     Offset    (Bytes)
+ *     0x000     4          In        Platform command
+ *                          Out       Platform command response size
+ *
+ * Each command can build upon this common request/response structure to create
+ * a structure specific to the command.
+ * See include/linux/tpm_svsm.h for more details.
+ *
+ * Return: 0 on success, -errno on failure
+ */
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

## [3] Stefano Garzarella — 2025-03-31
*Subject: [PATCH v5 2/4] svsm: add header with SVSM_VTPM_CMD helpers*

From: Stefano Garzarella <sgarzare@redhat.com>

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
Reviewed-by: Jarkko Sakkinen <jarkko@kernel.org>
Signed-off-by: Stefano Garzarella <sgarzare@redhat.com>
---
v5:
- added Jarkko's R-b
v4:
- used svsm_vtpm_ prefix consistently [Jarkko]
- removed __packed where not needed [Jarkko]
- expanded headers to avoid obfuscation [Jarkko]
- used `buf` instead of `inbuf`/`outbuf` [Jarkko]
- added more documentation quoting the specification
- removed TPM_* macros since we only use TPM_SEND_COMMAND in one place
  and don't want dependencies on external headers, but put the value
  directly as specified in the AMD SVSM specification
- header renamed in tpm_svsm.h so it will fall under TPM DEVICE DRIVER
  section [Borislav, Jarkko]
v3:
- renamed header and prefix to make clear it's related to the SVSM vTPM
  protocol
- renamed fill/parse functions [Tom]
- removed link to the spec because those URLs are unstable [Borislav]
---
 include/linux/tpm_svsm.h | 149 +++++++++++++++++++++++++++++++++++++++
 1 file changed, 149 insertions(+)
 create mode 100644 include/linux/tpm_svsm.h

diff --git a/include/linux/tpm_svsm.h b/include/linux/tpm_svsm.h
new file mode 100644
index 000000000000..38e341f9761a
--- /dev/null
+++ b/include/linux/tpm_svsm.h
@@ -0,0 +1,149 @@
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
+#ifndef _TPM_SVSM_H_
+#define _TPM_SVSM_H_
+
+#include <linux/errno.h>
+#include <linux/string.h>
+#include <linux/types.h>
+
+#define SVSM_VTPM_MAX_BUFFER		4096 /* max req/resp buffer size */
+
+/**
+ * struct svsm_vtpm_request - Generic request for single word command
+ * @cmd:	The command to send
+ *
+ * Defined by AMD SVSM spec [1] in section "8.2 SVSM_VTPM_CMD Call" -
+ * Table 15: vTPM Common Request/Response Structure
+ *     Byte      Size       In/Out    Description
+ *     Offset    (Bytes)
+ *     0x000     4          In        Platform command
+ *                          Out       Platform command response size
+ */
+struct svsm_vtpm_request {
+	u32 cmd;
+};
+
+/**
+ * struct svsm_vtpm_response - Generic response
+ * @size:	The response size (zero if nothing follows)
+ *
+ * Defined by AMD SVSM spec [1] in section "8.2 SVSM_VTPM_CMD Call" -
+ * Table 15: vTPM Common Request/Response Structure
+ *     Byte      Size       In/Out    Description
+ *     Offset    (Bytes)
+ *     0x000     4          In        Platform command
+ *                          Out       Platform command response size
+ *
+ * Note: most TCG Simulator commands simply return zero here with no indication
+ * of success or failure.
+ */
+struct svsm_vtpm_response {
+	u32 size;
+};
+
+/**
+ * struct svsm_vtpm_cmd_request - Structure for a TPM_SEND_COMMAND request
+ * @cmd:	The command to send (must be TPM_SEND_COMMAND)
+ * @locality:	The locality
+ * @buf_size:	The size of the input buffer following
+ * @buf:	A buffer of size buf_size
+ *
+ * Defined by AMD SVSM spec [1] in section "8.2 SVSM_VTPM_CMD Call" -
+ * Table 16: TPM_SEND_COMMAND Request Structure
+ *     Byte      Size       Meaning
+ *     Offset    (Bytes)
+ *     0x000     4          Platform command (8)
+ *     0x004     1          Locality (must-be-0)
+ *     0x005     4          TPM Command size (in bytes)
+ *     0x009     Variable   TPM Command
+ *
+ * Note: the TCG Simulator expects @buf_size to be equal to the size of the
+ * specific TPM command, otherwise an TPM_RC_COMMAND_SIZE error is returned.
+ */
+struct svsm_vtpm_cmd_request {
+	u32 cmd;
+	u8 locality;
+	u32 buf_size;
+	u8 buf[];
+} __packed;
+
+/**
+ * struct svsm_vtpm_cmd_response - Structure for a TPM_SEND_COMMAND response
+ * @buf_size:	The size of the output buffer following
+ * @buf:	A buffer of size buf_size
+ *
+ * Defined by AMD SVSM spec [1] in section "8.2 SVSM_VTPM_CMD Call" -
+ * Table 17: TPM_SEND_COMMAND Response Structure
+ *     Byte      Size       Meaning
+ *     Offset    (Bytes)
+ *     0x000     4          Response size (in bytes)
+ *     0x004     Variable   Response
+ */
+struct svsm_vtpm_cmd_response {
+	u32 buf_size;
+	u8 buf[];
+};
+
+/**
+ * svsm_vtpm_cmd_request_fill() - Fill a TPM_SEND_COMMAND request to be sent to SVSM
+ * @req: The struct svsm_vtpm_cmd_request to fill
+ * @locality: The locality
+ * @buf: The buffer from where to copy the payload of the command
+ * @len: The size of the buffer
+ *
+ * Return: 0 on success, negative error code on failure.
+ */
+static inline int
+svsm_vtpm_cmd_request_fill(struct svsm_vtpm_cmd_request *req, u8 locality,
+			   const u8 *buf, size_t len)
+{
+	if (len > SVSM_VTPM_MAX_BUFFER - sizeof(*req))
+		return -EINVAL;
+
+	req->cmd = 8; /* TPM_SEND_COMMAND */
+	req->locality = locality;
+	req->buf_size = len;
+
+	memcpy(req->buf, buf, len);
+
+	return 0;
+}
+
+/**
+ * svsm_vtpm_cmd_response_parse() - Parse a TPM_SEND_COMMAND response received from SVSM
+ * @resp: The struct svsm_vtpm_cmd_response to parse
+ * @buf: The buffer where to copy the response
+ * @len: The size of the buffer
+ *
+ * Return: buffer size filled with the response on success, negative error
+ * code on failure.
+ */
+static inline int
+svsm_vtpm_cmd_response_parse(const struct svsm_vtpm_cmd_response *resp, u8 *buf,
+			     size_t len)
+{
+	if (len < resp->buf_size)
+		return -E2BIG;
+
+	if (resp->buf_size > SVSM_VTPM_MAX_BUFFER - sizeof(*resp))
+		return -EINVAL;  // Invalid response from the platform TPM
+
+	memcpy(buf, resp->buf, resp->buf_size);
+
+	return resp->buf_size;
+}
+
+#endif /* _TPM_SVSM_H_ */

---

## [4] Stefano Garzarella — 2025-03-31
*Subject: [PATCH v5 3/4] tpm: add SNP SVSM vTPM driver*

From: Stefano Garzarella <sgarzare@redhat.com>

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
v5:
- removed cancel/status/req_* ops after rebase on master that cotains
  commit 980a573621ea ("tpm: Make chip->{status,cancel,req_canceled} opt")
v4:
- moved "asm" includes after the "linux" includes [Tom]
- allocated buffer separately [Tom/Jarkko/Jason]
v3:
- removed send_recv() ops and followed the ftpm driver implementing .status,
  .req_complete_mask, .req_complete_val, etc. [Jarkko]
- removed link to the spec because those URLs are unstable [Borislav]
---
 drivers/char/tpm/tpm_svsm.c | 135 ++++++++++++++++++++++++++++++++++++
 drivers/char/tpm/Kconfig    |  10 +++
 drivers/char/tpm/Makefile   |   1 +
 3 files changed, 146 insertions(+)
 create mode 100644 drivers/char/tpm/tpm_svsm.c

diff --git a/drivers/char/tpm/tpm_svsm.c b/drivers/char/tpm/tpm_svsm.c
new file mode 100644
index 000000000000..04c532421ff2
--- /dev/null
+++ b/drivers/char/tpm/tpm_svsm.c
@@ -0,0 +1,135 @@
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
+#include <linux/module.h>
+#include <linux/kernel.h>
+#include <linux/platform_device.h>
+#include <linux/tpm_svsm.h>
+
+#include <asm/sev.h>
+
+#include "tpm.h"
+
+struct tpm_svsm_priv {
+	void *buffer;
+	u8 locality;
+};
+
+static int tpm_svsm_send(struct tpm_chip *chip, u8 *buf, size_t len)
+{
+	struct tpm_svsm_priv *priv = dev_get_drvdata(&chip->dev);
+	int ret;
+
+	ret = svsm_vtpm_cmd_request_fill(priv->buffer, priv->locality, buf, len);
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
+	return svsm_vtpm_cmd_response_parse(priv->buffer, buf, len);
+}
+
+static struct tpm_class_ops tpm_chip_ops = {
+	.flags = TPM_OPS_AUTO_STARTUP,
+	.recv = tpm_svsm_recv,
+	.send = tpm_svsm_send,
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
+	 * The maximum buffer supported is one page (see SVSM_VTPM_MAX_BUFFER
+	 * in tpm_svsm.h).
+	 */
+	priv->buffer = (void *)devm_get_free_pages(dev, GFP_KERNEL, 0);
+	if (!priv->buffer)
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
index fe4f3a609934..dddd702b2454 100644
--- a/drivers/char/tpm/Kconfig
+++ b/drivers/char/tpm/Kconfig
@@ -234,5 +234,15 @@ config TCG_FTPM_TEE
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
index 2b004df8c04b..9de1b3ea34a9 100644
--- a/drivers/char/tpm/Makefile
+++ b/drivers/char/tpm/Makefile
@@ -45,3 +45,4 @@ obj-$(CONFIG_TCG_CRB) += tpm_crb.o
 obj-$(CONFIG_TCG_ARM_CRB_FFA) += tpm_crb_ffa.o
 obj-$(CONFIG_TCG_VTPM_PROXY) += tpm_vtpm_proxy.o
 obj-$(CONFIG_TCG_FTPM_TEE) += tpm_ftpm_tee.o
+obj-$(CONFIG_TCG_SVSM) += tpm_svsm.o

---

## [5] Stefano Garzarella — 2025-03-31
*Subject: [PATCH v5 4/4] x86/sev: register tpm-svsm platform device*

From: Stefano Garzarella <sgarzare@redhat.com>

SNP platform can provide a vTPM device emulated by SVSM.

The "tpm-svsm" device can be handled by the platform driver added
by the previous commit in drivers/char/tpm/tpm_svsm.c

Register the device unconditionally. The support check (e.g. SVSM, cmd)
is in snp_svsm_vtpm_probe(), keeping all logic in one place.
This function is called during the driver's probe along with other
setup tasks like memory allocation.

Signed-off-by: Stefano Garzarella <sgarzare@redhat.com>
---
v4:
- explained better why we register it anyway in the commit message
---
 arch/x86/coco/sev/core.c | 8 ++++++++
 1 file changed, 8 insertions(+)

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index efb43c9d3d30..acbd9bc526b1 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -2689,6 +2689,11 @@ static struct platform_device sev_guest_device = {
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
@@ -2697,6 +2702,9 @@ static int __init snp_init_platform_device(void)
 	if (platform_device_register(&sev_guest_device))
 		return -ENODEV;
 
+	if (platform_device_register(&tpm_svsm_device))
+		return -ENODEV;
+
 	pr_info("SNP guest platform device initialized.\n");
 	return 0;
 }

---

## [6] Tom Lendacky — 2025-03-31
*Subject: Re: [PATCH v5 4/4] x86/sev: register tpm-svsm platform device*

On 3/31/25 05:38, Stefano Garzarella wrote:
> From: Stefano Garzarella <sgarzare@redhat.com>
> 

Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>

> ---
> v4:

---

## [7] Jarkko Sakkinen — 2025-03-31
*Subject: Re: [PATCH v5 3/4] tpm: add SNP SVSM vTPM driver*

On Mon, Mar 31, 2025 at 12:38:56PM +0200, Stefano Garzarella wrote:
> From: Stefano Garzarella <sgarzare@redhat.com>
> 

I don't think we want FIXME's to mainline. Instead, don't declare the
field at all if you don't use it. Just pass zero to *_request_fill().

Maybe "not have the field" is even a better reminder than a random fixme
comment?

> +
> +	chip = tpmm_chip_alloc(dev, &tpm_chip_ops);

BR, Jarkko

---

## [8] Dionna Amalie Glaze — 2025-03-31
*Subject: Re: [PATCH v5 3/4] tpm: add SNP SVSM vTPM driver*

On Mon, Mar 31, 2025 at 10:34 AM Jarkko Sakkinen <jarkko@kernel.org> wrote:
>
> On Mon, Mar 31, 2025 at 12:38:56PM +0200, Stefano Garzarella wrote:

I might be unclear on how I should be testing this, but I do see
/dev/tpm0 and /dev/tpmrm0 when I build with CONFIG_TCG_SVSM=y, but I
don't see the event log in securityfs. What am I missing?

> > +
> > +MODULE_DESCRIPTION("SNP SVSM vTPM Driver");

---

## [9] James Bottomley — 2025-03-31
*Subject: Re: [PATCH v5 3/4] tpm: add SNP SVSM vTPM driver*

On Mon, 2025-03-31 at 13:56 -0700, Dionna Amalie Glaze wrote:
[...]
> I might be unclear on how I should be testing this, but I do see
> /dev/tpm0 and /dev/tpmrm0 when I build with CONFIG_TCG_SVSM=y, but I

The vtpm driver for EDK2/OVMF I suspect ... without that the UEFI won't
lay down and event log for the kernel to pick up.

Regards,

James

---

## [10] Dionna Amalie Glaze — 2025-03-31
*Subject: Re: [PATCH v5 3/4] tpm: add SNP SVSM vTPM driver*

On Mon, Mar 31, 2025 at 2:26 PM James Bottomley
<James.Bottomley@hansenpartnership.com> wrote:
>
> On Mon, 2025-03-31 at 13:56 -0700, Dionna Amalie Glaze wrote:

This test is with Oliver's PR https://github.com/tianocore/edk2/pull/6527

>
> Regards,

---

## [11] James Bottomley — 2025-03-31
*Subject: Re: [PATCH v5 3/4] tpm: add SNP SVSM vTPM driver*

On Mon, 2025-03-31 at 15:23 -0700, Dionna Amalie Glaze wrote:
> On Mon, Mar 31, 2025 at 2:26 PM James Bottomley
> <James.Bottomley@hansenpartnership.com> wrote:

Well, since the event log is searched for in tpm_chip_register(), I
really don't think it can be the kernel driver.  Best guess is there's
something wrong with that patch set (or the vTPM didn't activate in
OVMF for some reason).

Regards,

James

---

## [12] Stefano Garzarella — 2025-04-01
*Subject: Re: [PATCH v5 3/4] tpm: add SNP SVSM vTPM driver*

On Tue, 1 Apr 2025 at 00:59, James Bottomley <James.Bottomley@hansenpartnership.com> wrote:
>
> On Mon, 2025-03-31 at 15:23 -0700, Dionna Amalie Glaze wrote:

Yep, I also think it should be something in edk2.

I'm using edk2 from https://github.com/coconut-svsm/edk2/pull/62 which 
should contain the commits from that PR + a fix not yet merged upstream.

I'm building it with:
build -a X64 -b DEBUG -t GCC5 -DTPM2_ENABLE \
  --pcd PcdUninstallMemAttrProtocol=TRUE -p OvmfPkg/OvmfPkgX64.dsc

And in Linux I see the devices and the event log:

# ls /dev/tpm*
/dev/tpm0  /dev/tpmrm0

# ls /sys/kernel/security/tpm0/
binary_bios_measurements

# tpm2_eventlog /sys/kernel/security/tpm0/binary_bios_measurements
---
version: 1
events:
- EventNum: 0
  PCRIndex: 0
  EventType: EV_NO_ACTION
  Digest: "0000000000000000000000000000000000000000"
  EventSize: 37
...

If I remove `-DTPM2_ENABLE` when building edk2, I can still see the 
/dev/tpm* devices (of course), but I can't see the event log anymore.
And also most PCRs are 0 (unlike when I have tpm driver enabled in 
edk2).

Thanks,
Stefano

---

## [13] Stefano Garzarella — 2025-04-01
*Subject: Re: [PATCH v5 3/4] tpm: add SNP SVSM vTPM driver*

On Mon, Mar 31, 2025 at 08:34:42PM +0300, Jarkko Sakkinen wrote:
>On Mon, Mar 31, 2025 at 12:38:56PM +0200, Stefano Garzarella wrote:
>> From: Stefano Garzarella <sgarzare@redhat.com>

Yeah, I had thought the same, but then I left it that way because it was 
there from the first RFC and I saw several FIXME in the codebase, but I 
agree with you, I'll remove the field completely in v6.

That said, `struct tpm_svsm_priv` with this change will only contain the 
pointer to the buffer, does it make sense to have that structure (maybe 
for the future it's easier to add new fields), or do I remove it and use 
dev_set_drvdata() to store the pointer to the buffer directly?

Thanks,
Stefano

---

## [14] Jarkko Sakkinen — 2025-04-01
*Subject: Re: [PATCH v5 3/4] tpm: add SNP SVSM vTPM driver*

On Tue, Apr 01, 2025 at 11:08:49AM +0200, Stefano Garzarella wrote:
> On Mon, Mar 31, 2025 at 08:34:42PM +0300, Jarkko Sakkinen wrote:
> > On Mon, Mar 31, 2025 at 12:38:56PM +0200, Stefano Garzarella wrote:

I'll put it like this: I would not NAK this for having a struct with
a single field. Either way works for me. 

> 
> Thanks,

BR, Jarkko

---

## [15] Dionna Amalie Glaze — 2025-04-01
*Subject: Re: [PATCH v5 1/4] x86/sev: add SVSM vTPM probe/send_command functions*

On Mon, Mar 31, 2025 at 3:39 AM Stefano Garzarella <sgarzare@redhat.com> wrote:
>
> From: Stefano Garzarella <sgarzare@redhat.com>

How do we prevent this from causing scheduler problems when the TPM
service decides to take a really long time?
I removed the create_ek_2048 operation at boot in favor of lazily
creating it on first use.

This attest protocol uses tpm_send_command under the hood and
demonstrates the problem.
When I use this for CreatePrimary for an RSA 2048 key, the vCPU goes
out to lunch

[ 3356.509143] Sending NMI from CPU 1 to CPUs 0:
[ 2503.241673] NMI backtrace for cpu 0
[ 2503.241673] CPU: 0 PID: 462 Comm: cat Not tainted 6.6.84 #1
[ 2503.241673] Hardware name: Google Google Compute Engine/Google
Compute Engine, BIOS Google 01/01/2011
[ 2503.241673] RIP: 0010:svsm_perform_call_protocol+0x1ee/0x310
[ 2503.241673] Code: c2 48 c1 ea 20 b9 30 01 01 c0 0f 30 48 8b 3b 48
8b 43 08 48 8b 4b 10 48 8b 53 18 4c 8b 43 20 4c 8b 4b 28 c6 07
01 f3 0f 01 d9 <48> 8b 3b 45 31 d2 44 86 17 48 89 43 30 48 89 4b 38 48
89 53 40 4c
[ 2503.241673] RSP: 0018:ffffc90000f93ba8 EFLAGS: 00000012
[ 2503.241673] RAX: 0000000080000000 RBX: ffffc90000f93c98 RCX:
000000013ffe8008
[ 2503.241673] RDX: ffffffffffffffff RSI: ffff88813ffe9000 RDI:
ffff88813ffe8000
[ 2503.241673] RBP: ffffc90000f93bf8 R08: ffffffffffffffff R09:
0000000000000000
[ 2503.241673] R10: 0000000000000000 R11: 0000000080000000 R12:
0000000080000018
[ 2503.241673] R13: ffff88813ffe93f0 R14: 00000000ffffffea R15:
ffff8881bffe9000
[ 2503.241673] FS:  00007d3490351800(0000) GS:ffff88813bc00000(0000)
knlGS:0000000000000000
[ 2503.241673] CS:  0010 DS: 0000 ES: 0000 CR0: 0000000080050033
[ 2503.241673] CR2: 00007d349032f000 CR3: 00080001012d8003 CR4:
0000000000770ef0
[ 2503.241673] PKRU: 55555554
[ 2503.241673] Call Trace:
[ 2503.241673]  <NMI>
[ 2503.241673]  ? nmi_cpu_backtrace+0xe2/0x110
[ 2503.241673]  ? nmi_cpu_backtrace_handler+0x15/0x20
[ 2503.241673]  ? nmi_handle+0x7f/0x140
[ 2503.241673]  ? svsm_perform_call_protocol+0x1ee/0x310
[ 2503.241673]  ? default_do_nmi+0x46/0x100
[ 2503.241673]  ? exc_nmi+0x111/0x190
[ 2503.241673]  ? end_repeat_nmi+0x16/0x67
[ 2503.241673]  ? svsm_perform_call_protocol+0x1ee/0x310
[ 2503.241673]  ? svsm_perform_call_protocol+0x1ee/0x310
[ 2503.241673]  ? svsm_perform_call_protocol+0x1ee/0x310
[ 2503.241673]  </NMI>
[ 2503.241673]  <TASK>
[ 2503.241673]  snp_issue_svsm_attest_req+0xa7/0xf0
[ 2503.241673]  sev_report_new+0x58e/0xb20
[ 2503.241673]  ? srso_alias_return_thunk+0x5/0xfbef5
[ 2503.241673]  tsm_report_read+0x153/0x330
[ 2503.241673]  configfs_bin_read_iter+0xbf/0x200
[ 2503.241673]  ? srso_alias_return_thunk+0x5/0xfbef5
[ 2503.241673]  vfs_read+0x25e/0x2f0
[ 2503.241673]  ksys_read+0x75/0xe0
[ 2503.241673]  do_syscall_64+0x46/0xb0
[ 2503.241673]  entry_SYSCALL_64_after_hwframe+0x78/0xe2
[ 2503.241673] RIP: 0033:0x7d348ff281cd
[ 2503.241673] Code: 31 c0 e9 d6 fe ff ff 55 48 8d 3d a6 0a 0a 00 48
89 e5 e8 c6 1c 02 00 66 0f 1f 44 00 00 80 3d 31 62 0d 00 00 74
17 31 c0 0f 05 <48> 3d 00 f0 ff ff 77 53 c3 66 2e 0f 1f 84 00 00 00 00
00 55 48 89
[ 2503.241673] RSP: 002b:00007ffc71e50a88 EFLAGS: 00000246 ORIG_RAX:
0000000000000000
[ 2503.241673] RAX: ffffffffffffffda RBX: 00007d3490330000 RCX:
00007d348ff281cd
[ 2503.241673] RDX: 0000000000020000 RSI: 00007d3490330000 RDI:
0000000000000003
[ 2503.241673] RBP: 00007ffc71e50ab0 R08: 00007d349032f010 R09:
0000000000000000
[ 2503.241673] R10: 0000000000000022 R11: 0000000000000246 R12:
0000000000020000
[ 2503.241673] R13: 0000000000000000 R14: 0000000000000003 R15:
0000000000020000
[ 2503.241673]  </TASK>


Which doesn't seem like behavior we want, nor is it something I have
any idea how we solve with the synchronous SVSM call model.

>  static struct platform_device sev_guest_device = {
>         .name           = "sev-guest",

---

## [16] Dionna Amalie Glaze — 2025-04-01
*Subject: Re: [PATCH v5 1/4] x86/sev: add SVSM vTPM probe/send_command functions*

On Tue, Apr 1, 2025 at 9:13 PM Dionna Amalie Glaze
<dionnaglaze@google.com> wrote:
>
> On Mon, Mar 31, 2025 at 3:39 AM Stefano Garzarella <sgarzare@redhat.com> wrote:

Disregard this error. I was providing the wrong command. I don't
experience any such hang now.

>
> Which doesn't seem like behavior we want, nor is it something I have

---
