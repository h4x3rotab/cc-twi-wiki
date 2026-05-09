---
title: 'Enlightened vTPM support for SVSM on SEV-SNP'
date: 2025-04-03
last_reply: 2025-04-10
message_count: 30
participants: ['Stefano Garzarella', 'Jarkko Sakkinen', 'Dionna Amalie Glaze', 'Borislav Petkov', 'James Bottomley', 'Tom Lendacky']
---

## [1] Stefano Garzarella — 2025-04-03

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

v5 -> v6
- Removed the `locality` field (set to 0) and the FIXME comment [Jarkko]
- Added Tom's R-b on patch 4

v4 -> v5: https://lore.kernel.org/linux-integrity/20250331103900.92701-1-sgarzare@redhat.com/
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
 drivers/char/tpm/tpm_svsm.c | 128 +++++++++++++++++++++++++++++++
 drivers/char/tpm/Kconfig    |  10 +++
 drivers/char/tpm/Makefile   |   1 +
 6 files changed, 364 insertions(+)
 create mode 100644 include/linux/tpm_svsm.h
 create mode 100644 drivers/char/tpm/tpm_svsm.c

---

## [2] Stefano Garzarella — 2025-04-03
*Subject: [PATCH v6 1/4] x86/sev: add SVSM vTPM probe/send_command functions*

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

## [3] Stefano Garzarella — 2025-04-03
*Subject: [PATCH v6 2/4] svsm: add header with SVSM_VTPM_CMD helpers*

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

## [4] Stefano Garzarella — 2025-04-03
*Subject: [PATCH v6 3/4] tpm: add SNP SVSM vTPM driver*

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
v6:
- removed the `locality` field (set to 0) and the FIXME comment [Jarkko]
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
 drivers/char/tpm/tpm_svsm.c | 128 ++++++++++++++++++++++++++++++++++++
 drivers/char/tpm/Kconfig    |  10 +++
 drivers/char/tpm/Makefile   |   1 +
 3 files changed, 139 insertions(+)
 create mode 100644 drivers/char/tpm/tpm_svsm.c

diff --git a/drivers/char/tpm/tpm_svsm.c b/drivers/char/tpm/tpm_svsm.c
new file mode 100644
index 000000000000..b9242c9eab87
--- /dev/null
+++ b/drivers/char/tpm/tpm_svsm.c
@@ -0,0 +1,128 @@
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
+};
+
+static int tpm_svsm_send(struct tpm_chip *chip, u8 *buf, size_t len)
+{
+	struct tpm_svsm_priv *priv = dev_get_drvdata(&chip->dev);
+	int ret;
+
+	ret = svsm_vtpm_cmd_request_fill(priv->buffer, 0, buf, len);
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

## [5] Stefano Garzarella — 2025-04-03
*Subject: [PATCH v6 4/4] x86/sev: register tpm-svsm platform device*

From: Stefano Garzarella <sgarzare@redhat.com>

SNP platform can provide a vTPM device emulated by SVSM.

The "tpm-svsm" device can be handled by the platform driver added
by the previous commit in drivers/char/tpm/tpm_svsm.c

Register the device unconditionally. The support check (e.g. SVSM, cmd)
is in snp_svsm_vtpm_probe(), keeping all logic in one place.
This function is called during the driver's probe along with other
setup tasks like memory allocation.

Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>
Signed-off-by: Stefano Garzarella <sgarzare@redhat.com>
---
v6:
- added Tom's R-b
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

## [6] Jarkko Sakkinen — 2025-04-03
*Subject: Re: [PATCH v6 3/4] tpm: add SNP SVSM vTPM driver*

On Thu, Apr 03, 2025 at 12:09:41PM +0200, Stefano Garzarella wrote:
> From: Stefano Garzarella <sgarzare@redhat.com>
> 

Reviewed-by: Jarkko Sakkinen <jarkko@kernel.org>

BR, Jarkko

---

## [7] Jarkko Sakkinen — 2025-04-03
*Subject: Re: [PATCH v6 4/4] x86/sev: register tpm-svsm platform device*

On Thu, Apr 03, 2025 at 12:09:42PM +0200, Stefano Garzarella wrote:
> From: Stefano Garzarella <sgarzare@redhat.com>
> 

Reviewed-by: Jarkko Sakkinen <jarkko@kernel.org>

BR, Jarkko

---

## [8] Dionna Amalie Glaze — 2025-04-04
*Subject: Re: [PATCH v6 3/4] tpm: add SNP SVSM vTPM driver*

On Thu, Apr 3, 2025 at 3:10 AM Stefano Garzarella <sgarzare@redhat.com> wrote:
>
> From: Stefano Garzarella <sgarzare@redhat.com>

Our testing is showing that tpm2_probe is hitting a null pointer deref
in tpm_transmit.


> +       if (err)
> +               return err;


--
-Dionna Glaze, PhD, CISSP, CCSP (she/her)

---

## [9] Stefano Garzarella — 2025-04-04
*Subject: Re: [PATCH v6 3/4] tpm: add SNP SVSM vTPM driver*

On Fri, 4 Apr 2025 at 19:32, Dionna Amalie Glaze <dionnaglaze@google.com> wrote:
>
> On Thu, Apr 3, 2025 at 3:10 AM Stefano Garzarella <sgarzare@redhat.com> wrote:

Next time, please share a backtrace.

BTW I suspect you're not using Linus' tree, so be sure to backport
also commit 980a573621ea ("tpm: Make
chip->{status,cancel,req_canceled} opt").

Without that, you will have a null ptr dereference since .status() is
NULL from v5 of this series (as specified in the changelog).

Stefano

---

## [10] Dionna Amalie Glaze — 2025-04-04
*Subject: Re: [PATCH v6 3/4] tpm: add SNP SVSM vTPM driver*

On Fri, Apr 4, 2025 at 11:37 AM Stefano Garzarella <sgarzare@redhat.com> wrote:
>
> On Fri, 4 Apr 2025 at 19:32, Dionna Amalie Glaze <dionnaglaze@google.com> wrote:

Right, my bad.
>
> BTW I suspect you're not using Linus' tree, so be sure to backport

Thanks, I missed that detail. Will report back.
>
> Stefano

>


--
-Dionna Glaze, PhD, CISSP, CCSP (she/her)

---

## [11] Borislav Petkov — 2025-04-07
*Subject: Re: [PATCH v6 0/4] Enlightened vTPM support for SVSM on SEV-SNP*

On Thu, Apr 03, 2025 at 12:09:38PM +0200, Stefano Garzarella wrote:
> Stefano Garzarella (4):
>   x86/sev: add SVSM vTPM probe/send_command functions

Jarrko,

should I take the whole bunch through the tip tree?

No point in splitting between two trees...

Thx.

---

## [12] Jarkko Sakkinen — 2025-04-07
*Subject: Re: [PATCH v6 0/4] Enlightened vTPM support for SVSM on SEV-SNP*

On Mon, Apr 07, 2025 at 03:46:43PM +0200, Borislav Petkov wrote:
> On Thu, Apr 03, 2025 at 12:09:38PM +0200, Stefano Garzarella wrote:
> > Stefano Garzarella (4):

It's cleanly separated and does not even touch any shared headers,
so I don't see any issues on doing that. I.e., I'm with it :-)

> 
> Thx.

BR, Jarkko

---

## [13] Borislav Petkov — 2025-04-08
*Subject: Re: [PATCH v6 4/4] x86/sev: register tpm-svsm platform device*

On Thu, Apr 03, 2025 at 12:09:42PM +0200, Stefano Garzarella wrote:
> @@ -2697,6 +2702,9 @@ static int __init snp_init_platform_device(void)
>  	if (platform_device_register(&sev_guest_device))

So I don't understand the design here:

You've exported the probe function - snp_svsm_vtpm_probe() - and you're
calling it in tpm_svsm_probe().

So why aren't you registering the platform device there too but are doing this
unconditional strange thing here?

---

## [14] Stefano Garzarella — 2025-04-08
*Subject: Re: [PATCH v6 4/4] x86/sev: register tpm-svsm platform device*

On Tue, Apr 08, 2025 at 01:00:12PM +0200, Borislav Petkov wrote:
>On Thu, Apr 03, 2025 at 12:09:42PM +0200, Stefano Garzarella wrote:
>> @@ -2697,6 +2702,9 @@ static int __init snp_init_platform_device(void)

We discussed a bit on v3, but I'm open to change it:
https://lore.kernel.org/linux-integrity/nrn4ur66lz2ocbkkjl2bgiex3xbp552szerfhalsaefunqxf7p@ki7xf66zrf6u/

  I tried to keep the logic of whether or not the driver is needed all in 
  the tpm_svsm_probe()/snp_svsm_vtpm_probe() (where I check for SVSM).
  If you prefer to move some pieces here, though, I'm open.

Thanks,
Stefano

---

## [15] Borislav Petkov — 2025-04-08
*Subject: Re: [PATCH v6 4/4] x86/sev: register tpm-svsm platform device*

On Tue, Apr 08, 2025 at 01:08:36PM +0200, Stefano Garzarella wrote:
> We discussed a bit on v3, but I'm open to change it:
> https://lore.kernel.org/linux-integrity/nrn4ur66lz2ocbkkjl2bgiex3xbp552szerfhalsaefunqxf7p@ki7xf66zrf6u/

Yes please.

It doesn't make a whole lotta sense right now to register a TPM platform
driver at one place without even knowing you're running with an SVSM inside
the guest blob or not.

The usual approach is to register upon a successful detection.

Thx.

---

## [16] Stefano Garzarella — 2025-04-08
*Subject: Re: [PATCH v6 4/4] x86/sev: register tpm-svsm platform device*

On Tue, Apr 08, 2025 at 01:28:20PM +0200, Borislav Petkov wrote:
>On Tue, Apr 08, 2025 at 01:08:36PM +0200, Stefano Garzarella wrote:
>> We discussed a bit on v3, but I'm open to change it:

I see, so IIUC I can just apply the following change to this patch and 
avoid to export snp_svsm_vtpm_probe() at all, right?

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index acbd9bc526b1..fa83e6c7f990 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -2702,8 +2702,10 @@ static int __init snp_init_platform_device(void)
         if (platform_device_register(&sev_guest_device))
                 return -ENODEV;
  
-       if (platform_device_register(&tpm_svsm_device))
-               return -ENODEV;
+       if (snp_svsm_vtpm_probe()) {
+               if (platform_device_register(&tpm_svsm_device))
+                       return -ENODEV;
+       }
  
         pr_info("SNP guest platform device initialized.\n");
         return 0;

Thanks,
Stefano

---

## [17] Stefano Garzarella — 2025-04-09
*Subject: Re: [PATCH v6 3/4] tpm: add SNP SVSM vTPM driver*

On Thu, 3 Apr 2025 at 21:05, Jarkko Sakkinen <jarkko@kernel.org> wrote:
>
> On Thu, Apr 03, 2025 at 12:09:41PM +0200, Stefano Garzarella wrote:

In the next version I'm moving the snp_svsm_vtpm_probe() call from
here to sev core where the device is registered.
See https://lore.kernel.org/linux-integrity/o2u7p3wb64lcc4sziunr274hyubkgmspzdjcvihbpzkw6mkvpo@sjq3vi4y2qfl/

Do I carry your R-b for this patch (and patch 4) or would you rather
take a look at v7?

Thanks,
Stefano

---

## [18] Stefano Garzarella — 2025-04-09
*Subject: Re: [PATCH v6 3/4] tpm: add SNP SVSM vTPM driver*

On Fri, 4 Apr 2025 at 20:59, Dionna Amalie Glaze <dionnaglaze@google.com> wrote:
>
> On Fri, Apr 4, 2025 at 11:37 AM Stefano Garzarella <sgarzare@redhat.com> wrote:

I'm preparing v7, is your issue solved or do we need to investigate
better before sending a v7?

Thanks,
Stefano

---

## [19] Borislav Petkov — 2025-04-09
*Subject: Re: [PATCH v6 4/4] x86/sev: register tpm-svsm platform device*

On Tue, Apr 08, 2025 at 01:54:07PM +0200, Stefano Garzarella wrote:
> I see, so IIUC I can just apply the following change to this patch and avoid
> to export snp_svsm_vtpm_probe() at all, right?

No, this should go in tpm_svsm_probe().

---

## [20] Stefano Garzarella — 2025-04-09
*Subject: Re: [PATCH v6 4/4] x86/sev: register tpm-svsm platform device*

On Wed, 9 Apr 2025 at 12:21, Borislav Petkov <bp@alien8.de> wrote:
>
> On Tue, Apr 08, 2025 at 01:54:07PM +0200, Stefano Garzarella wrote:

Sorry, maybe I missed something.

tpm_svsm.c registers the driver with module_platform_driver_probe().

Someone (the platform I guess) has to register the device by calling
platform_device_register(), as we already do for example for
sev_guest.

If we move platform_device_register() to tpm_svsm_probe() how will the
probe be invoked?

Thanks,
Stefano

---

## [21] Borislav Petkov — 2025-04-09
*Subject: Re: [PATCH v6 4/4] x86/sev: register tpm-svsm platform device*

On Wed, Apr 09, 2025 at 12:43:01PM +0200, Stefano Garzarella wrote:
> Sorry, maybe I missed something.
> 

Maybe that platform device thing is the wrong approach. Why does the core code
need to register some dummy platform device in the first place? Why can't
drivers/char/tpm/tpm_svsm.c probe and init without it?

---

## [22] James Bottomley — 2025-04-09
*Subject: Re: [PATCH v6 4/4] x86/sev: register tpm-svsm platform device*

On Wed, 2025-04-09 at 13:31 +0200, Borislav Petkov wrote:
> On Wed, Apr 09, 2025 at 12:43:01PM +0200, Stefano Garzarella wrote:
> > Sorry, maybe I missed something.

Because of the way driver and device matching works in Linux.  We have
to have a struct device because that sits at the he heart of the TPM
driver binding.  If we have a struct device, it has to sit on a bus
(because that's the Linux design) and if we don't have a bus then we
have to use a platform device (or, now, we could use a struct device on
the faux bus).  Busses can be either physical (PCI, GSC, ...) and
abstract (virtio, xen, scsi, ...), so it's not impossible, if the SVSM
has more than one device, that it should have it's own SVSM bus which
we could then act a bit like the virtio bus and the SVSM vTPM struct
device could sit on this (the TPM subsystem, like most driver
subsystems, doesn't care about busses, it only cares that the abstract
bus device id matching works).

Regards,

James

---

## [23] Jarkko Sakkinen — 2025-04-09
*Subject: Re: [PATCH v6 3/4] tpm: add SNP SVSM vTPM driver*

On Wed, Apr 09, 2025 at 11:43:55AM +0200, Stefano Garzarella wrote:
> On Thu, 3 Apr 2025 at 21:05, Jarkko Sakkinen <jarkko@kernel.org> wrote:
> >

I'm fine with it. I'm sure that Boris et al make the complains if/when
required :-) This whole process has been going on smoothly overall, and
all my concerns have been addressed.

> 
> Thanks,

BR, Jarkko

---

## [24] Stefano Garzarella — 2025-04-09
*Subject: Re: [PATCH v6 4/4] x86/sev: register tpm-svsm platform device*

On Wed, 9 Apr 2025 at 14:22, James Bottomley
<James.Bottomley@hansenpartnership.com> wrote:
>
> On Wed, 2025-04-09 at 13:31 +0200, Borislav Petkov wrote:

I tried to look at faux bus, but IIUC, it doesn't fit. I mean, we
could use it if we had a driver here in sev/core.c, but using a
separate module for the tpm-svsm driver, how do we get the module to
load when we find out that the device is there?

In short, my question: how do we load the module automatically when we
discover the device?

faux seems more useful to me when there's no need to discover the
device, but loading the module itself starts everything. If, on the
other hand, we want to have it load when we discover it, we have to
either have a bus or have core code that registers a platform_device
that will then be recognized by the driver in a separate module.

> Busses can be either physical (PCI, GSC, ...) and
> abstract (virtio, xen, scsi, ...), so it's not impossible, if the SVSM

Yes, I'm also looking at introducing a svsm bus as we've already
discussed, but that's going to take some time.

In the end though, platform_device is not that bad IMO. The tpm-svsm
is really a device provided by the (virtual) platform, so doing some
sort of discovery of the bus in sev/core.c and registering the device
if discovered might be a compromise for now until we develop the bus.

If you agree, I'll move all the discovery here in sev/core.c as I
suggested earlier, so that when we get the bus we'll move this code
somehow into the bus.
@Borsilav @James WDYT?

Thanks,
Stefano

---

## [25] Tom Lendacky — 2025-04-09
*Subject: Re: [PATCH v6 4/4] x86/sev: register tpm-svsm platform device*

On 4/9/25 06:31, Borislav Petkov wrote:
> On Wed, Apr 09, 2025 at 12:43:01PM +0200, Stefano Garzarella wrote:
>> Sorry, maybe I missed something.

I think the platform device is the right approach (just like we do for the
sev-guest driver), but I think we should only register the device if an
SVSM is present. Then let the vTPM driver probe routine check if the SVSM
vTPM support is present.

So the vTPM driver wouldn't change, just snp_init_platform_device():

	if (snp_vmpl && platform_device_register(&tpm_svsm_device))

Looking at the message that is issued after, maybe it should read
"devices" now.

Thanks,
Tom

>

---

## [26] Stefano Garzarella — 2025-04-09
*Subject: Re: [PATCH v6 4/4] x86/sev: register tpm-svsm platform device*

On Wed, 9 Apr 2025 at 18:08, Tom Lendacky <thomas.lendacky@amd.com> wrote:
>
> On 4/9/25 06:31, Borislav Petkov wrote:

I see, agree.

>
> So the vTPM driver wouldn't change, just snp_init_platform_device():

I can do if we agree on that.

>
> Looking at the message that is issued after, maybe it should read

Good catch, I'll update the pr_info() message!

Thanks,
Stefano

---

## [27] Borislav Petkov — 2025-04-09
*Subject: Re: [PATCH v6 4/4] x86/sev: register tpm-svsm platform device*

On Wed, Apr 09, 2025 at 08:22:37AM -0400, James Bottomley wrote:
> Because of the way driver and device matching works in Linux.  We have
> to have a struct device because that sits at the he heart of the TPM

Thanks for elaborating!

> (or, now, we could use a struct device on the faux bus).  Busses can be
> either physical (PCI, GSC, ...) and abstract (virtio, xen, scsi, ...), so

I guess we should keep this in mind. Depending on what else needs to talk to
the SVSM in the future...

Thx.

---

## [28] Borislav Petkov — 2025-04-09
*Subject: Re: [PATCH v6 4/4] x86/sev: register tpm-svsm platform device*

On Wed, Apr 09, 2025 at 11:07:49AM -0500, Tom Lendacky wrote:
> So the vTPM driver wouldn't change, just snp_init_platform_device():
> 

So this basically says that the SVSM is always sporting a vTPM emulation. But
you can build the cocont-svsm thing without it AFAICT.

So I'm guessing Stefano's suggestion here might make more sense:

https://lore.kernel.org/r/o2u7p3wb64lcc4sziunr274hyubkgmspzdjcvihbpzkw6mkvpo@sjq3vi4y2qfl

considering it all...

---

## [29] Tom Lendacky — 2025-04-09
*Subject: Re: [PATCH v6 4/4] x86/sev: register tpm-svsm platform device*

On 4/9/25 13:45, Borislav Petkov wrote:
> On Wed, Apr 09, 2025 at 11:07:49AM -0500, Tom Lendacky wrote:
>> So the vTPM driver wouldn't change, just snp_init_platform_device():

That way works for me, too.

Thanks,
Tom


>

---

## [30] Stefano Garzarella — 2025-04-10
*Subject: Re: [PATCH v6 4/4] x86/sev: register tpm-svsm platform device*

On Wed, Apr 09, 2025 at 02:16:40PM -0500, Tom Lendacky wrote:
>On 4/9/25 13:45, Borislav Petkov wrote:
>> On Wed, Apr 09, 2025 at 11:07:49AM -0500, Tom Lendacky wrote:

Okay, it looks like we have an agreement! I'll apply that and send v7.

Thanks,
Stefano

---
