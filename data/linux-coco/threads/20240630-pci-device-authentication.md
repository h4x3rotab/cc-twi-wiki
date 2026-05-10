---
title: 'PCI device authentication'
date: 2024-06-30
last_reply: 2025-02-12
message_count: 86
participants: ['Lukas Wunner', 'Jeff Johnson', 'Herbert Xu', 'Greg Kroah-Hartman', 'Alexey Kardashevskiy', 'Dan Williams', 'Alistair Francis', 'Damien Le Moal', 'Kees Cook', 'Jason Gunthorpe', 'Jonathan Cameron']
---

## [1] Lukas Wunner — 2024-06-30

PCI device authentication v2

Authenticate PCI devices with CMA-SPDM (PCIe r6.2 sec 6.31) and
expose the result in sysfs.

Five big changes since v1 (and many smaller ones, full list at end):

* Certificates presented by a device are now exposed in sysfs
  (new patch 12).

* Per James Bottomley's request at Plumbers, a log of signatures
  received from a device is exposed in sysfs (new patches 13-18),
  allowing for re-verification by remote attestation services.
  Comments welcome whether the proposed ABI makes sense.

* Per Damien Le Moal's request at Plumbers, sysfs attributes are
  now implemented in the SPDM library instead of in the PCI core.
  Thereby, ATA and SCSI will be able to re-use them seamlessly.

* I've dropped a controversial patch to grant guests exclusive control
  of authentication of passed-through devices (old patch 12 in v1).
  People were more interested in granting the TSM exclusive control
  instead of the guest.  Dan Williams is driving an effort to negotiate
  SPDM control between kernel and TSM.

* The SPDM library (in patch 7) has undergone significant changes
  to enable the above-mentioned sysfs exposure of certificates and
  signatures:  It retrieves and caches all certificates from a device
  and collects all exchanged SPDM messages in a transcript buffer.
  To ease future maintenance, the code has been split into multiple
  files in lib/spdm/.


Link to v1 and subsequent Plumbers discussion:
https://lore.kernel.org/all/cover.1695921656.git.lukas@wunner.de/
https://lpc.events/event/17/contributions/1558/

How to test with qemu:
https://github.com/twilfredo/qemu-spdm-emulation-guide


Changes v1 -> v2:

* [PATCH 01/18] X.509: Make certificate parser public
  * Add include guard #ifndef + #define to <keys/x509-parser.h> (Ilpo).

* [PATCH 02/18] X.509: Parse Subject Alternative Name in certificates
  * Return -EBADMSG instead of -EINVAL on duplicate Subject Alternative
    Name, drop error message for consistency with existing code.

* [PATCH 03/18] X.509: Move certificate length retrieval into new helper
  * Use ssize_t instead of int (Ilpo).
  * Amend commit message to explain why the helper is exported (Dan).

* [PATCH 06/18] crypto: ecdsa - Support P1363 signature encoding
  * Use idiomatic &buffer[keylen] notation.
  * Rebase on NIST P521 curve support introduced with v6.10-rc1

* [PATCH 07/18] spdm: Introduce library to authenticate devices
  New features:
  * In preparation for exposure of certificate chains in sysfs, retrieve
    the certificates from *all* populated slots instead of stopping on
    the first valid slot.  Cache certificate chains in struct spdm_state.
  * Collect all exchanged messages of an authentication sequence in a
    transcript buffer for exposure in sysfs.  Compute hash over this
    transcript rather than peacemeal over each exchanged message.
  * Support NIST P521 curve introduced with v6.10-rc1.
  Bugs:
  * Amend spdm_validate_cert_chain() to cope with zero length chain.
  * Print correct error code returned from x509_cert_parse().
  * Emit error if there are no common supported algorithms.
  * Implicitly this causes an error if responder selects algorithms
    not supported by requester during NEGOTIATE_ALGORITHMS exchange,
    previously this was silently ignored (Jonathan).
  * Refine checks of Basic Constraints and Key Usage certificate fields.
  * Add code comment explaining those checks (Jonathan).
  Usability:
  * Log informational message on successful authentication (Tomi Sarvela).
  Style:
  * Split spdm_requester.c into spdm.h, core.c and req-authenticate.c.
  * Use __counted_by() in struct spdm_get_version_rsp (Ilpo).
  * Return ssize_t instead of int from spdm_transport (Ilpo).
  * Downcase hex characters, vertically align SPDM_REQ macro (Ilpo).
  * Upcase spdm_error_code enum, vertically align it (Ilpo).
  * Return -ECONNRESET instead of -ERESTART from spdm_err() (Ilpo).
  * Access versions with le16_to_cpu() instead of get_unaligned_le16()
    in spdm_get_version() because __packed attribute already implies
    byte-wise access (Ilpo).
  * Add code comment in spdm_start_hash() that shash and desc
    allocations are freed by spdm_reset(), thus seemingly leaked (Ilpo).
  * Rename "s" and "h" members of struct spdm_state to "sig_len" and
    "hash_len" for clarity (Ilpo).
  * Use FIELD_GET() in spdm_create_combined_prefix() for clarity (Ilpo).
  * Add SPDM_NONCE_SZ macro (Ilpo).
  * Reorder error path of spdm_authenticate() for symmetry (Jonathan).
  * Fix indentation of Kconfig entry (Jonathan).
  * Annotate capabilities introduced with SPDM 1.1 (Jonathan).
  * Annotate algorithms introduced with SPDM 1.2 (Jonathan).
  * Annotate errors introduced with SPDM 1.1 and 1.2 (Jonathan).
  * Amend algorithm #ifdef's to avoid trailing "|" (Jonathan).
  * Add code comment explaining that some SPDM messages are enlarged
    by fields added in new SPDM versions whereas others use reserved
    space for new fields (Jonathan).
  * Refine code comments on various fields in SPDM messages (Jonathan).
  * Duplicate spdm_get_capabilities_reqrsp into separate structs (Jonathan).
  * Document SupportedAlgorithms field at end of spdm_get_capabilities_rsp,
    introduced with SPDM 1.3 (Jonathan).
  * Use offsetofend() rather than offsetof() to set SPDM message size
    based on SPDM version (Jonathan).
  * Use cleanup.h to unwind heap allocations (Jonathan).
  * In spdm_verify_signature(), change code comment to refer to "SPDM 1.0
    and 1.1" instead of "Until SPDM 1.1" (Jonathan).
  * Use namespace "SPDM" for exported symbols (Jonathan).
  * Drop __spdm_exchange().
  * In spdm_exchange(), do not return an error on truncation of
    spdm_header so that callers can take care of it.
  * Rename "SPDM_CAPS" macro to "SPDM_REQ_CAPS" to prepare for later
    addition of responder support.
  * Rename "SPDM_MIN_CAPS" macro to "SPDM_RSP_MIN_CAPS" and
    rename "responder_caps" member of struct spdm_state to "rsp_caps".
  * Rename "SPDM_REQUESTER" Kconfig symbol to "SPDM".  There is actually
    no clear-cut separation between requester and responder code because
    mutual authentication will require the responder to invoke requester
    functions.
  * Rename "slot_mask" member of struct spdm_state to "provisioned_slots"
    to follow SPDM 1.3 spec language.

* [PATCH 08/18] PCI/CMA: Authenticate devices on enumeration
  * In pci_cma_init(), check whether pci_cma_keyring is an ERR_PTR
    rather than checking whether it's NULL.  keyring_alloc() never
    returns NULL.
  * On failure to allocate keyring, emit "PCI: " and ".cma" as part of
    error message for clarity (Bjorn).
  * Drop superfluous curly braces around two if-blocks (Jonathan, Bjorn).
  * Add code comment explaining why spdm_state is kept despite initial
    authentication failure (Jonathan).
  * Rename PCI_DOE_PROTOCOL_CMA to PCI_DOE_FEATURE_CMA for DOE r1.1
    compliance.

* [PATCH 09/18] PCI/CMA: Validate Subject Alternative Name in certificates
  * Amend commit message with note on Reference Integrity Manifest (Jonathan).
  * Amend commit message and code comment with note on PCIe r6.2 changes.
  * Add SPDX identifer and IETF copyright to cma.asn1 per section 4 of:
    https://trustee.ietf.org/documents/trust-legal-provisions/tlp-5/
  * Pass slot number to ->validate() callback and emit it in error messages.
  * Move all of cma-x509.c into cma.c (Bjorn).

* [PATCH 10/18] PCI/CMA: Reauthenticate devices on reset and resume
  * Drop "cma_capable" bit in struct pci_dev and instead check whether
    "spdm_state" is a NULL pointer.  Only difference:  Devices which
    didn't support the minimum set of capabilities on enumeration
    are now attempted to be reauthenticated.  The rationale being that
    they may have gained new capabilities due to a runtime firmware update.
  * Add kernel-doc for pci_cma_reauthenticate().

* [PATCH 11/18] PCI/CMA: Expose in sysfs whether devices are authenticated
  * Change write semantics of sysfs attribute such that reauthentication
    is triggered by writing "re" (instead of an arbitrary string).
    This allows adding other commands down the road.
  * Move sysfs attribute from PCI core to SPDM library for reuse by other
    bus types such as SCSI/ATA (Damien).
  * If DOE or CMA initialization fails, set pci_dev->spdm_state to ERR_PTR
    instead of using additional boolean flags.
  * Amend commit message to mention downgrade attack prevention (Ilpo,
    Jonathan).
  * Amend ABI documentation to mention reauthentication after downloading
    firmware to an FPGA device.

* [PATCH 12/18 to 18/18] are new in v2


Jonathan Cameron (2):
  spdm: Introduce library to authenticate devices
  PCI/CMA: Authenticate devices on enumeration

Lukas Wunner (16):
  X.509: Make certificate parser public
  X.509: Parse Subject Alternative Name in certificates
  X.509: Move certificate length retrieval into new helper
  certs: Create blacklist keyring earlier
  crypto: akcipher - Support more than one signature encoding
  crypto: ecdsa - Support P1363 signature encoding
  PCI/CMA: Validate Subject Alternative Name in certificates
  PCI/CMA: Reauthenticate devices on reset and resume
  PCI/CMA: Expose in sysfs whether devices are authenticated
  PCI/CMA: Expose certificates in sysfs
  sysfs: Allow bin_attributes to be added to groups
  sysfs: Allow symlinks to be added between sibling groups
  PCI/CMA: Expose a log of received signatures in sysfs
  spdm: Limit memory consumed by log of received signatures
  spdm: Authenticate devices despite invalid certificate chain
  spdm: Allow control of next requester nonce through sysfs

 Documentation/ABI/testing/sysfs-devices-spdm | 247 ++++++
 Documentation/admin-guide/sysctl/index.rst   |   2 +
 Documentation/admin-guide/sysctl/spdm.rst    |  33 +
 MAINTAINERS                                  |  14 +
 certs/blacklist.c                            |   4 +-
 crypto/akcipher.c                            |   2 +-
 crypto/asymmetric_keys/public_key.c          |  44 +-
 crypto/asymmetric_keys/x509_cert_parser.c    |   9 +
 crypto/asymmetric_keys/x509_loader.c         |  38 +-
 crypto/asymmetric_keys/x509_parser.h         |  40 +-
 crypto/ecdsa.c                               |  18 +-
 crypto/internal.h                            |   1 +
 crypto/rsa-pkcs1pad.c                        |  11 +-
 crypto/sig.c                                 |   6 +-
 crypto/testmgr.c                             |   8 +-
 crypto/testmgr.h                             |  20 +
 drivers/pci/Kconfig                          |  13 +
 drivers/pci/Makefile                         |   4 +
 drivers/pci/cma.asn1                         |  41 +
 drivers/pci/cma.c                            | 247 ++++++
 drivers/pci/doe.c                            |   5 +-
 drivers/pci/pci-driver.c                     |   1 +
 drivers/pci/pci-sysfs.c                      |   5 +
 drivers/pci/pci.c                            |  12 +-
 drivers/pci/pci.h                            |  17 +
 drivers/pci/pcie/err.c                       |   3 +
 drivers/pci/probe.c                          |   3 +
 drivers/pci/remove.c                         |   1 +
 fs/sysfs/file.c                              |  69 +-
 fs/sysfs/group.c                             |  33 +
 include/crypto/akcipher.h                    |  10 +-
 include/crypto/sig.h                         |   6 +-
 include/keys/asymmetric-type.h               |   2 +
 include/keys/x509-parser.h                   |  55 ++
 include/linux/kernfs.h                       |   2 +
 include/linux/oid_registry.h                 |   3 +
 include/linux/pci-doe.h                      |   4 +
 include/linux/pci.h                          |  16 +
 include/linux/spdm.h                         |  46 ++
 include/linux/sysfs.h                        |  29 +
 lib/Kconfig                                  |  15 +
 lib/Makefile                                 |   2 +
 lib/spdm/Makefile                            |  11 +
 lib/spdm/core.c                              | 442 +++++++++++
 lib/spdm/req-authenticate.c                  | 765 +++++++++++++++++++
 lib/spdm/req-sysfs.c                         | 619 +++++++++++++++
 lib/spdm/spdm.h                              | 560 ++++++++++++++
 47 files changed, 3436 insertions(+), 102 deletions(-)
 create mode 100644 Documentation/ABI/testing/sysfs-devices-spdm
 create mode 100644 Documentation/admin-guide/sysctl/spdm.rst
 create mode 100644 drivers/pci/cma.asn1
 create mode 100644 drivers/pci/cma.c
 create mode 100644 include/keys/x509-parser.h
 create mode 100644 include/linux/spdm.h
 create mode 100644 lib/spdm/Makefile
 create mode 100644 lib/spdm/core.c
 create mode 100644 lib/spdm/req-authenticate.c
 create mode 100644 lib/spdm/req-sysfs.c
 create mode 100644 lib/spdm/spdm.h

---

## [2] Lukas Wunner — 2024-06-30
*Subject: [PATCH v2 01/18] X.509: Make certificate parser public*

The upcoming support for PCI device authentication with CMA-SPDM
(PCIe r6.1 sec 6.31) requires validating the Subject Alternative Name
in X.509 certificates.

High-level functions for X.509 parsing such as key_create_or_update()
throw away the internal, low-level struct x509_certificate after
extracting the struct public_key and public_key_signature from it.
The Subject Alternative Name is thus inaccessible when using those
functions.

Afford CMA-SPDM access to the Subject Alternative Name by making struct
x509_certificate public, together with the functions for parsing an
X.509 certificate into such a struct and freeing such a struct.

The private header file x509_parser.h previously included <linux/time.h>
for the definition of time64_t.  That definition was since moved to
<linux/time64.h> by commit 361a3bf00582 ("time64: Add time64.h header
and define struct timespec64"), so adjust the #include directive as part
of the move to the new public header file <keys/x509-parser.h>.

No functional change intended.

Signed-off-by: Lukas Wunner <lukas@wunner.de>
Reviewed-by: Dan Williams <dan.j.williams@intel.com>
Reviewed-by: Ilpo Järvinen <ilpo.jarvinen@linux.intel.com>
Reviewed-by: Jonathan Cameron <Jonathan.Cameron@huawei.com>
---
 crypto/asymmetric_keys/x509_parser.h | 40 +--------------------
 include/keys/x509-parser.h           | 53 ++++++++++++++++++++++++++++
 2 files changed, 54 insertions(+), 39 deletions(-)
 create mode 100644 include/keys/x509-parser.h

diff --git a/crypto/asymmetric_keys/x509_parser.h b/crypto/asymmetric_keys/x509_parser.h
index 0688c222806b..39f1521b773d 100644
--- a/crypto/asymmetric_keys/x509_parser.h
+++ b/crypto/asymmetric_keys/x509_parser.h
@@ -5,49 +5,11 @@
  * Written by David Howells (dhowells@redhat.com)
  */
 
-#include <linux/cleanup.h>
-#include <linux/time.h>
-#include <crypto/public_key.h>
-#include <keys/asymmetric-type.h>
-
-struct x509_certificate {
-	struct x509_certificate *next;
-	struct x509_certificate *signer;	/* Certificate that signed this one */
-	struct public_key *pub;			/* Public key details */
-	struct public_key_signature *sig;	/* Signature parameters */
-	char		*issuer;		/* Name of certificate issuer */
-	char		*subject;		/* Name of certificate subject */
-	struct asymmetric_key_id *id;		/* Issuer + Serial number */
-	struct asymmetric_key_id *skid;		/* Subject + subjectKeyId (optional) */
-	time64_t	valid_from;
-	time64_t	valid_to;
-	const void	*tbs;			/* Signed data */
-	unsigned	tbs_size;		/* Size of signed data */
-	unsigned	raw_sig_size;		/* Size of signature */
-	const void	*raw_sig;		/* Signature data */
-	const void	*raw_serial;		/* Raw serial number in ASN.1 */
-	unsigned	raw_serial_size;
-	unsigned	raw_issuer_size;
-	const void	*raw_issuer;		/* Raw issuer name in ASN.1 */
-	const void	*raw_subject;		/* Raw subject name in ASN.1 */
-	unsigned	raw_subject_size;
-	unsigned	raw_skid_size;
-	const void	*raw_skid;		/* Raw subjectKeyId in ASN.1 */
-	unsigned	index;
-	bool		seen;			/* Infinite recursion prevention */
-	bool		verified;
-	bool		self_signed;		/* T if self-signed (check unsupported_sig too) */
-	bool		unsupported_sig;	/* T if signature uses unsupported crypto */
-	bool		blacklisted;
-};
+#include <keys/x509-parser.h>
 
 /*
  * x509_cert_parser.c
  */
-extern void x509_free_certificate(struct x509_certificate *cert);
-DEFINE_FREE(x509_free_certificate, struct x509_certificate *,
-	    if (!IS_ERR(_T)) x509_free_certificate(_T))
-extern struct x509_certificate *x509_cert_parse(const void *data, size_t datalen);
 extern int x509_decode_time(time64_t *_t,  size_t hdrlen,
 			    unsigned char tag,
 			    const unsigned char *value, size_t vlen);
diff --git a/include/keys/x509-parser.h b/include/keys/x509-parser.h
new file mode 100644
index 000000000000..37436a5c7526
--- /dev/null
+++ b/include/keys/x509-parser.h
@@ -0,0 +1,53 @@
+/* SPDX-License-Identifier: GPL-2.0-or-later */
+/* X.509 certificate parser
+ *
+ * Copyright (C) 2012 Red Hat, Inc. All Rights Reserved.
+ * Written by David Howells (dhowells@redhat.com)
+ */
+
+#ifndef _KEYS_X509_PARSER_H
+#define _KEYS_X509_PARSER_H
+
+#include <crypto/public_key.h>
+#include <keys/asymmetric-type.h>
+#include <linux/cleanup.h>
+#include <linux/time64.h>
+
+struct x509_certificate {
+	struct x509_certificate *next;
+	struct x509_certificate *signer;	/* Certificate that signed this one */
+	struct public_key *pub;			/* Public key details */
+	struct public_key_signature *sig;	/* Signature parameters */
+	char		*issuer;		/* Name of certificate issuer */
+	char		*subject;		/* Name of certificate subject */
+	struct asymmetric_key_id *id;		/* Issuer + Serial number */
+	struct asymmetric_key_id *skid;		/* Subject + subjectKeyId (optional) */
+	time64_t	valid_from;
+	time64_t	valid_to;
+	const void	*tbs;			/* Signed data */
+	unsigned	tbs_size;		/* Size of signed data */
+	unsigned	raw_sig_size;		/* Size of signature */
+	const void	*raw_sig;		/* Signature data */
+	const void	*raw_serial;		/* Raw serial number in ASN.1 */
+	unsigned	raw_serial_size;
+	unsigned	raw_issuer_size;
+	const void	*raw_issuer;		/* Raw issuer name in ASN.1 */
+	const void	*raw_subject;		/* Raw subject name in ASN.1 */
+	unsigned	raw_subject_size;
+	unsigned	raw_skid_size;
+	const void	*raw_skid;		/* Raw subjectKeyId in ASN.1 */
+	unsigned	index;
+	bool		seen;			/* Infinite recursion prevention */
+	bool		verified;
+	bool		self_signed;		/* T if self-signed (check unsupported_sig too) */
+	bool		unsupported_sig;	/* T if signature uses unsupported crypto */
+	bool		blacklisted;
+};
+
+struct x509_certificate *x509_cert_parse(const void *data, size_t datalen);
+void x509_free_certificate(struct x509_certificate *cert);
+
+DEFINE_FREE(x509_free_certificate, struct x509_certificate *,
+	    if (!IS_ERR(_T)) x509_free_certificate(_T))
+
+#endif /* _KEYS_X509_PARSER_H */

---

## [3] Lukas Wunner — 2024-06-30
*Subject: [PATCH v2 02/18] X.509: Parse Subject Alternative Name in
 certificates*

The upcoming support for PCI device authentication with CMA-SPDM
(PCIe r6.1 sec 6.31) requires validating the Subject Alternative Name
in X.509 certificates.

Store a pointer to the Subject Alternative Name upon parsing for
consumption by CMA-SPDM.

Signed-off-by: Lukas Wunner <lukas@wunner.de>
Reviewed-by: Wilfred Mallawa <wilfred.mallawa@wdc.com>
Reviewed-by: Ilpo Järvinen <ilpo.jarvinen@linux.intel.com>
Reviewed-by: Jonathan Cameron <Jonathan.Cameron@huawei.com>
Acked-by: Dan Williams <dan.j.williams@intel.com>
---
 crypto/asymmetric_keys/x509_cert_parser.c | 9 +++++++++
 include/keys/x509-parser.h                | 2 ++
 2 files changed, 11 insertions(+)

diff --git a/crypto/asymmetric_keys/x509_cert_parser.c b/crypto/asymmetric_keys/x509_cert_parser.c
index 25cc4273472f..92314e4854f1 100644
--- a/crypto/asymmetric_keys/x509_cert_parser.c
+++ b/crypto/asymmetric_keys/x509_cert_parser.c
@@ -588,6 +588,15 @@ int x509_process_extension(void *context, size_t hdrlen,
 		return 0;
 	}
 
+	if (ctx->last_oid == OID_subjectAltName) {
+		if (ctx->cert->raw_san)
+			return -EBADMSG;
+
+		ctx->cert->raw_san = v;
+		ctx->cert->raw_san_size = vlen;
+		return 0;
+	}
+
 	if (ctx->last_oid == OID_keyUsage) {
 		/*
 		 * Get hold of the keyUsage bit string
diff --git a/include/keys/x509-parser.h b/include/keys/x509-parser.h
index 37436a5c7526..8e450befe3b9 100644
--- a/include/keys/x509-parser.h
+++ b/include/keys/x509-parser.h
@@ -36,6 +36,8 @@ struct x509_certificate {
 	unsigned	raw_subject_size;
 	unsigned	raw_skid_size;
 	const void	*raw_skid;		/* Raw subjectKeyId in ASN.1 */
+	const void	*raw_san;		/* Raw subjectAltName in ASN.1 */
+	unsigned	raw_san_size;
 	unsigned	index;
 	bool		seen;			/* Infinite recursion prevention */
 	bool		verified;

---

## [4] Lukas Wunner — 2024-06-30
*Subject: [PATCH v2 03/18] X.509: Move certificate length retrieval into new
 helper*

The upcoming in-kernel SPDM library (Security Protocol and Data Model,
https://www.dmtf.org/dsp/DSP0274) needs to retrieve the length from
ASN.1 DER-encoded X.509 certificates.

Such code already exists in x509_load_certificate_list(), so move it
into a new helper for reuse by SPDM.

Export the helper so that SPDM can be tristate.  (Some upcoming users of
the SPDM libray may be modular, such as SCSI and ATA.)

No functional change intended.

Signed-off-by: Lukas Wunner <lukas@wunner.de>
Reviewed-by: Dan Williams <dan.j.williams@intel.com>
Reviewed-by: Jonathan Cameron <Jonathan.Cameron@huawei.com>
---
 crypto/asymmetric_keys/x509_loader.c | 38 +++++++++++++++++++---------
 include/keys/asymmetric-type.h       |  2 ++
 2 files changed, 28 insertions(+), 12 deletions(-)

diff --git a/crypto/asymmetric_keys/x509_loader.c b/crypto/asymmetric_keys/x509_loader.c
index a41741326998..25ff027fad1d 100644
--- a/crypto/asymmetric_keys/x509_loader.c
+++ b/crypto/asymmetric_keys/x509_loader.c
@@ -4,28 +4,42 @@
 #include <linux/key.h>
 #include <keys/asymmetric-type.h>
 
+ssize_t x509_get_certificate_length(const u8 *p, unsigned long buflen)
+{
+	ssize_t plen;
+
+	/* Each cert begins with an ASN.1 SEQUENCE tag and must be more
+	 * than 256 bytes in size.
+	 */
+	if (buflen < 4)
+		return -EINVAL;
+
+	if (p[0] != 0x30 &&
+	    p[1] != 0x82)
+		return -EINVAL;
+
+	plen = (p[2] << 8) | p[3];
+	plen += 4;
+	if (plen > buflen)
+		return -EINVAL;
+
+	return plen;
+}
+EXPORT_SYMBOL_GPL(x509_get_certificate_length);
+
 int x509_load_certificate_list(const u8 cert_list[],
 			       const unsigned long list_size,
 			       const struct key *keyring)
 {
 	key_ref_t key;
 	const u8 *p, *end;
-	size_t plen;
+	ssize_t plen;
 
 	p = cert_list;
 	end = p + list_size;
 	while (p < end) {
-		/* Each cert begins with an ASN.1 SEQUENCE tag and must be more
-		 * than 256 bytes in size.
-		 */
-		if (end - p < 4)
-			goto dodgy_cert;
-		if (p[0] != 0x30 &&
-		    p[1] != 0x82)
-			goto dodgy_cert;
-		plen = (p[2] << 8) | p[3];
-		plen += 4;
-		if (plen > end - p)
+		plen = x509_get_certificate_length(p, end - p);
+		if (plen < 0)
 			goto dodgy_cert;
 
 		key = key_create_or_update(make_key_ref(keyring, 1),
diff --git a/include/keys/asymmetric-type.h b/include/keys/asymmetric-type.h
index 69a13e1e5b2e..e2af07fec3c6 100644
--- a/include/keys/asymmetric-type.h
+++ b/include/keys/asymmetric-type.h
@@ -84,6 +84,8 @@ extern struct key *find_asymmetric_key(struct key *keyring,
 				       const struct asymmetric_key_id *id_2,
 				       bool partial);
 
+ssize_t x509_get_certificate_length(const u8 *p, unsigned long buflen);
+
 int x509_load_certificate_list(const u8 cert_list[], const unsigned long list_size,
 			       const struct key *keyring);

---

## [5] Lukas Wunner — 2024-06-30
*Subject: [PATCH v2 04/18] certs: Create blacklist keyring earlier*

The upcoming support for PCI device authentication with CMA-SPDM
(PCIe r6.2 sec 6.31) requires parsing X.509 certificates upon
device enumeration, which happens in a subsys_initcall().

Parsing X.509 certificates accesses the blacklist keyring:
x509_cert_parse()
  x509_get_sig_params()
    is_hash_blacklisted()
      keyring_search()

So far the keyring is created much later in a device_initcall().  Avoid
a NULL pointer dereference on access to the keyring by creating it one
initcall level earlier than PCI device enumeration, i.e. in an
arch_initcall().

Signed-off-by: Lukas Wunner <lukas@wunner.de>
Reviewed-by: Dan Williams <dan.j.williams@intel.com>
Reviewed-by: Wilfred Mallawa <wilfred.mallawa@wdc.com>
Reviewed-by: Alistair Francis <alistair.francis@wdc.com>
Reviewed-by: Ilpo Järvinen <ilpo.jarvinen@linux.intel.com>
Reviewed-by: Jonathan Cameron <Jonathan.Cameron@huawei.com>
---
 certs/blacklist.c | 4 ++--
 1 file changed, 2 insertions(+), 2 deletions(-)

diff --git a/certs/blacklist.c b/certs/blacklist.c
index 675dd7a8f07a..34185415d451 100644
--- a/certs/blacklist.c
+++ b/certs/blacklist.c
@@ -311,7 +311,7 @@ static int restrict_link_for_blacklist(struct key *dest_keyring,
  * Initialise the blacklist
  *
  * The blacklist_init() function is registered as an initcall via
- * device_initcall().  As a result if the blacklist_init() function fails for
+ * arch_initcall().  As a result if the blacklist_init() function fails for
  * any reason the kernel continues to execute.  While cleanly returning -ENODEV
  * could be acceptable for some non-critical kernel parts, if the blacklist
  * keyring fails to load it defeats the certificate/key based deny list for
@@ -356,7 +356,7 @@ static int __init blacklist_init(void)
 /*
  * Must be initialised before we try and load the keys into the keyring.
  */
-device_initcall(blacklist_init);
+arch_initcall(blacklist_init);
 
 #ifdef CONFIG_SYSTEM_REVOCATION_LIST
 /*

---

## [6] Lukas Wunner — 2024-06-30
*Subject: [PATCH v2 05/18] crypto: akcipher - Support more than one signature
 encoding*

Currently only a single default signature encoding is supported per
akcipher.

A subsequent commit will allow a second encoding for ecdsa, namely P1363
alternatively to X9.62.

To accommodate for that, amend struct akcipher_request and struct
crypto_akcipher_sync_data to store the desired signature encoding for
verify and sign ops.

Amend akcipher_request_set_crypt(), crypto_sig_verify() and
crypto_sig_sign() with an additional parameter which specifies the
desired signature encoding.  Adjust all callers.

Signed-off-by: Lukas Wunner <lukas@wunner.de>
Reviewed-by: Jonathan Cameron <Jonathan.Cameron@huawei.com>
---
 crypto/akcipher.c                   |  2 +-
 crypto/asymmetric_keys/public_key.c |  4 ++--
 crypto/internal.h                   |  1 +
 crypto/rsa-pkcs1pad.c               | 11 +++++++----
 crypto/sig.c                        |  6 ++++--
 crypto/testmgr.c                    |  8 +++++---
 crypto/testmgr.h                    |  1 +
 include/crypto/akcipher.h           | 10 +++++++++-
 include/crypto/sig.h                |  6 ++++--
 9 files changed, 34 insertions(+), 15 deletions(-)

diff --git a/crypto/akcipher.c b/crypto/akcipher.c
index e0ff5f4dda6d..785848590606 100644
--- a/crypto/akcipher.c
+++ b/crypto/akcipher.c
@@ -190,7 +190,7 @@ int crypto_akcipher_sync_prep(struct crypto_akcipher_sync_data *data)
 	sg = &data->sg;
 	sg_init_one(sg, buf, mlen);
 	akcipher_request_set_crypt(req, sg, data->dst ? sg : NULL,
-				   data->slen, data->dlen);
+				   data->slen, data->dlen, data->enc);
 
 	crypto_init_wait(&data->cwait);
 	akcipher_request_set_callback(req, CRYPTO_TFM_REQ_MAY_SLEEP,
diff --git a/crypto/asymmetric_keys/public_key.c b/crypto/asymmetric_keys/public_key.c
index 3474fb34ded9..00f70835359f 100644
--- a/crypto/asymmetric_keys/public_key.c
+++ b/crypto/asymmetric_keys/public_key.c
@@ -368,7 +368,7 @@ static int software_key_eds_op(struct kernel_pkey_params *params,
 		if (!issig)
 			break;
 		ret = crypto_sig_sign(sig, in, params->in_len,
-				      out, params->out_len);
+				      out, params->out_len, params->encoding);
 		break;
 	default:
 		BUG();
@@ -452,7 +452,7 @@ int public_key_verify_signature(const struct public_key *pkey,
 		goto error_free_key;
 
 	ret = crypto_sig_verify(tfm, sig->s, sig->s_size,
-				sig->digest, sig->digest_size);
+				sig->digest, sig->digest_size, sig->encoding);
 
 error_free_key:
 	kfree_sensitive(key);
diff --git a/crypto/internal.h b/crypto/internal.h
index 63e59240d5fb..268315b13ccd 100644
--- a/crypto/internal.h
+++ b/crypto/internal.h
@@ -41,6 +41,7 @@ struct crypto_akcipher_sync_data {
 	void *dst;
 	unsigned int slen;
 	unsigned int dlen;
+	const char *enc;
 
 	struct akcipher_request *req;
 	struct crypto_wait cwait;
diff --git a/crypto/rsa-pkcs1pad.c b/crypto/rsa-pkcs1pad.c
index cd501195f34a..c8aa68511849 100644
--- a/crypto/rsa-pkcs1pad.c
+++ b/crypto/rsa-pkcs1pad.c
@@ -285,7 +285,8 @@ static int pkcs1pad_encrypt(struct akcipher_request *req)
 
 	/* Reuse output buffer */
 	akcipher_request_set_crypt(&req_ctx->child_req, req_ctx->in_sg,
-				   req->dst, ctx->key_size - 1, req->dst_len);
+				   req->dst, ctx->key_size - 1, req->dst_len,
+				   NULL);
 
 	err = crypto_akcipher_encrypt(&req_ctx->child_req);
 	if (err != -EINPROGRESS && err != -EBUSY)
@@ -385,7 +386,7 @@ static int pkcs1pad_decrypt(struct akcipher_request *req)
 	/* Reuse input buffer, output to a new buffer */
 	akcipher_request_set_crypt(&req_ctx->child_req, req->src,
 				   req_ctx->out_sg, req->src_len,
-				   ctx->key_size);
+				   ctx->key_size, NULL);
 
 	err = crypto_akcipher_decrypt(&req_ctx->child_req);
 	if (err != -EINPROGRESS && err != -EBUSY)
@@ -442,7 +443,8 @@ static int pkcs1pad_sign(struct akcipher_request *req)
 
 	/* Reuse output buffer */
 	akcipher_request_set_crypt(&req_ctx->child_req, req_ctx->in_sg,
-				   req->dst, ctx->key_size - 1, req->dst_len);
+				   req->dst, ctx->key_size - 1, req->dst_len,
+				   req->enc);
 
 	err = crypto_akcipher_decrypt(&req_ctx->child_req);
 	if (err != -EINPROGRESS && err != -EBUSY)
@@ -574,7 +576,8 @@ static int pkcs1pad_verify(struct akcipher_request *req)
 
 	/* Reuse input buffer, output to a new buffer */
 	akcipher_request_set_crypt(&req_ctx->child_req, req->src,
-				   req_ctx->out_sg, sig_size, ctx->key_size);
+				   req_ctx->out_sg, sig_size, ctx->key_size,
+				   req->enc);
 
 	err = crypto_akcipher_encrypt(&req_ctx->child_req);
 	if (err != -EINPROGRESS && err != -EBUSY)
diff --git a/crypto/sig.c b/crypto/sig.c
index 7645bedf3a1f..79f6d4e92447 100644
--- a/crypto/sig.c
+++ b/crypto/sig.c
@@ -76,7 +76,7 @@ EXPORT_SYMBOL_GPL(crypto_sig_maxsize);
 
 int crypto_sig_sign(struct crypto_sig *tfm,
 		    const void *src, unsigned int slen,
-		    void *dst, unsigned int dlen)
+		    void *dst, unsigned int dlen, const char *enc)
 {
 	struct crypto_akcipher **ctx = crypto_sig_ctx(tfm);
 	struct crypto_akcipher_sync_data data = {
@@ -85,6 +85,7 @@ int crypto_sig_sign(struct crypto_sig *tfm,
 		.dst = dst,
 		.slen = slen,
 		.dlen = dlen,
+		.enc = enc,
 	};
 
 	return crypto_akcipher_sync_prep(&data) ?:
@@ -95,7 +96,7 @@ EXPORT_SYMBOL_GPL(crypto_sig_sign);
 
 int crypto_sig_verify(struct crypto_sig *tfm,
 		      const void *src, unsigned int slen,
-		      const void *digest, unsigned int dlen)
+		      const void *digest, unsigned int dlen, const char *enc)
 {
 	struct crypto_akcipher **ctx = crypto_sig_ctx(tfm);
 	struct crypto_akcipher_sync_data data = {
@@ -103,6 +104,7 @@ int crypto_sig_verify(struct crypto_sig *tfm,
 		.src = src,
 		.slen = slen,
 		.dlen = dlen,
+		.enc = enc,
 	};
 	int err;
 
diff --git a/crypto/testmgr.c b/crypto/testmgr.c
index 00f5a6cf341a..20148c8b25a0 100644
--- a/crypto/testmgr.c
+++ b/crypto/testmgr.c
@@ -4150,11 +4150,12 @@ static int test_akcipher_one(struct crypto_akcipher *tfm,
 			goto free_all;
 		memcpy(xbuf[1], c, c_size);
 		sg_set_buf(&src_tab[2], xbuf[1], c_size);
-		akcipher_request_set_crypt(req, src_tab, NULL, m_size, c_size);
+		akcipher_request_set_crypt(req, src_tab, NULL, m_size, c_size,
+					   vecs->enc);
 	} else {
 		sg_init_one(&dst, outbuf_enc, out_len_max);
 		akcipher_request_set_crypt(req, src_tab, &dst, m_size,
-					   out_len_max);
+					   out_len_max, NULL);
 	}
 	akcipher_request_set_callback(req, CRYPTO_TFM_REQ_MAY_BACKLOG,
 				      crypto_req_done, &wait);
@@ -4213,7 +4214,8 @@ static int test_akcipher_one(struct crypto_akcipher *tfm,
 	sg_init_one(&src, xbuf[0], c_size);
 	sg_init_one(&dst, outbuf_dec, out_len_max);
 	crypto_init_wait(&wait);
-	akcipher_request_set_crypt(req, &src, &dst, c_size, out_len_max);
+	akcipher_request_set_crypt(req, &src, &dst, c_size, out_len_max,
+				   vecs->enc);
 
 	err = crypto_wait_req(vecs->siggen_sigver_test ?
 			      /* Run asymmetric signature generation */
diff --git a/crypto/testmgr.h b/crypto/testmgr.h
index 5350cfd9d325..7e34e3f871a3 100644
--- a/crypto/testmgr.h
+++ b/crypto/testmgr.h
@@ -153,6 +153,7 @@ struct akcipher_testvec {
 	const unsigned char *params;
 	const unsigned char *m;
 	const unsigned char *c;
+	const char *enc;
 	unsigned int key_len;
 	unsigned int param_len;
 	unsigned int m_size;
diff --git a/include/crypto/akcipher.h b/include/crypto/akcipher.h
index 18a10cad07aa..2c2bc19d657f 100644
--- a/include/crypto/akcipher.h
+++ b/include/crypto/akcipher.h
@@ -30,6 +30,8 @@
  *		In case of error where the dst sgl size was insufficient,
  *		it will be updated to the size required for the operation.
  *		For verify op this is size of digest part in @src.
+ * @enc:	For verify op it's the encoding of the signature part of @src.
+ *		For sign op it's the encoding of the signature in @dst.
  * @__ctx:	Start of private context data
  */
 struct akcipher_request {
@@ -38,6 +40,7 @@ struct akcipher_request {
 	struct scatterlist *dst;
 	unsigned int src_len;
 	unsigned int dst_len;
+	const char *enc;
 	void *__ctx[] CRYPTO_MINALIGN_ATTR;
 };
 
@@ -247,17 +250,22 @@ static inline void akcipher_request_set_callback(struct akcipher_request *req,
  * @src_len:	size of the src input scatter list to be processed
  * @dst_len:	size of the dst output scatter list or size of signature
  *		portion in @src for verify op
+ * @enc:	encoding of signature portion in @src for verify op,
+ *		encoding of signature in @dst for sign op,
+ *		NULL for encrypt and decrypt op
  */
 static inline void akcipher_request_set_crypt(struct akcipher_request *req,
 					      struct scatterlist *src,
 					      struct scatterlist *dst,
 					      unsigned int src_len,
-					      unsigned int dst_len)
+					      unsigned int dst_len,
+					      const char *enc)
 {
 	req->src = src;
 	req->dst = dst;
 	req->src_len = src_len;
 	req->dst_len = dst_len;
+	req->enc = enc;
 }
 
 /**
diff --git a/include/crypto/sig.h b/include/crypto/sig.h
index d25186bb2be3..4081029ecc97 100644
--- a/include/crypto/sig.h
+++ b/include/crypto/sig.h
@@ -81,12 +81,13 @@ int crypto_sig_maxsize(struct crypto_sig *tfm);
  * @slen:	source length
  * @dst:	destination obuffer
  * @dlen:	destination length
+ * @enc:	signature encoding
  *
  * Return: zero on success; error code in case of error
  */
 int crypto_sig_sign(struct crypto_sig *tfm,
 		    const void *src, unsigned int slen,
-		    void *dst, unsigned int dlen);
+		    void *dst, unsigned int dlen, const char *enc);
 
 /**
  * crypto_sig_verify() - Invoke signature verification
@@ -99,12 +100,13 @@ int crypto_sig_sign(struct crypto_sig *tfm,
  * @slen:	source length
  * @digest:	digest
  * @dlen:	digest length
+ * @enc:	signature encoding
  *
  * Return: zero on verification success; error code in case of error.
  */
 int crypto_sig_verify(struct crypto_sig *tfm,
 		      const void *src, unsigned int slen,
-		      const void *digest, unsigned int dlen);
+		      const void *digest, unsigned int dlen, const char *enc);
 
 /**
  * crypto_sig_set_pubkey() - Invoke set public key operation

---

## [7] Lukas Wunner — 2024-06-30
*Subject: [PATCH v2 06/18] crypto: ecdsa - Support P1363 signature encoding*

Alternatively to the X9.62 encoding of ecdsa signatures, which uses
ASN.1 and is already supported by the kernel, there's another common
encoding called P1363.  It stores r and s as the concatenation of two
big endian, unsigned integers.  The name originates from IEEE P1363.

The Security Protocol and Data Model (SPDM) specification prescribes
that ecdsa signatures are encoded according to P1363:

   "For ECDSA signatures, excluding SM2, in SPDM, the signature shall be
    the concatenation of r and s.  The size of r shall be the size of
    the selected curve.  Likewise, the size of s shall be the size of
    the selected curve.  See BaseAsymAlgo in NEGOTIATE_ALGORITHMS for
    the size of r and s.  The byte order for r and s shall be in big
    endian order.  When placing ECDSA signatures into an SPDM signature
    field, r shall come first followed by s."

    (SPDM 1.2.1 margin no 44,
    https://www.dmtf.org/sites/default/files/standards/documents/DSP0274_1.2.1.pdf)

A subsequent commit introduces an SPDM library to enable PCI device
authentication, so add support for P1363 ecdsa signature verification.

Signed-off-by: Lukas Wunner <lukas@wunner.de>
Reviewed-by: Jonathan Cameron <Jonathan.Cameron@huawei.com>
---
 crypto/asymmetric_keys/public_key.c | 40 +++++++++++++++++------------
 crypto/ecdsa.c                      | 18 ++++++++++---
 crypto/testmgr.h                    | 19 ++++++++++++++
 3 files changed, 58 insertions(+), 19 deletions(-)

diff --git a/crypto/asymmetric_keys/public_key.c b/crypto/asymmetric_keys/public_key.c
index 00f70835359f..9a6f030a5847 100644
--- a/crypto/asymmetric_keys/public_key.c
+++ b/crypto/asymmetric_keys/public_key.c
@@ -104,7 +104,8 @@ software_key_determine_akcipher(const struct public_key *pkey,
 			return -EINVAL;
 		*sig = false;
 	} else if (strncmp(pkey->pkey_algo, "ecdsa", 5) == 0) {
-		if (strcmp(encoding, "x962") != 0)
+		if (strcmp(encoding, "x962") != 0 &&
+		    strcmp(encoding, "p1363") != 0)
 			return -EINVAL;
 		/*
 		 * ECDSA signatures are taken over a raw hash, so they don't
@@ -234,7 +235,6 @@ static int software_key_query(const struct kernel_pkey_params *params,
 	info->key_size = len * 8;
 
 	if (strncmp(pkey->pkey_algo, "ecdsa", 5) == 0) {
-		int slen = len;
 		/*
 		 * ECDSA key sizes are much smaller than RSA, and thus could
 		 * operate on (hashed) inputs that are larger than key size.
@@ -246,21 +246,29 @@ static int software_key_query(const struct kernel_pkey_params *params,
 
 		/*
 		 * Verify takes ECDSA-Sig (described in RFC 5480) as input,
-		 * which is actually 2 'key_size'-bit integers encoded in
-		 * ASN.1.  Account for the ASN.1 encoding overhead here.
-		 *
-		 * NIST P192/256/384 may prepend a '0' to a coordinate to
-		 * indicate a positive integer. NIST P521 never needs it.
+		 * which is actually 2 'key_size'-bit integers.
 		 */
-		if (strcmp(pkey->pkey_algo, "ecdsa-nist-p521") != 0)
-			slen += 1;
-		/* Length of encoding the x & y coordinates */
-		slen = 2 * (slen + 2);
-		/*
-		 * If coordinate encoding takes at least 128 bytes then an
-		 * additional byte for length encoding is needed.
-		 */
-		info->max_sig_size = 1 + (slen >= 128) + 1 + slen;
+		if (strcmp(params->encoding, "x962") == 0) {
+			int slen = len;
+
+			/*
+			 * Account for the ASN.1 encoding overhead here.
+			 *
+			 * NIST P192/256/384 may prepend a '0' to a coordinate
+			 * to indicate a positive integer. NIST P521 does not.
+			 */
+			if (strcmp(pkey->pkey_algo, "ecdsa-nist-p521") != 0)
+				slen += 1;
+			/* Length of encoding the x & y coordinates */
+			slen = 2 * (slen + 2);
+			/*
+			 * If coordinate encoding takes at least 128 bytes then
+			 * an additional byte for length encoding is needed.
+			 */
+			info->max_sig_size = 1 + (slen >= 128) + 1 + slen;
+		} else if (strcmp(params->encoding, "p1363") == 0) {
+			info->max_sig_size = 2 * len;
+		}
 	} else {
 		info->max_data_size = len;
 		info->max_sig_size = len;
diff --git a/crypto/ecdsa.c b/crypto/ecdsa.c
index 258fffbf623d..8d412dec917f 100644
--- a/crypto/ecdsa.c
+++ b/crypto/ecdsa.c
@@ -139,6 +139,7 @@ static int ecdsa_verify(struct akcipher_request *req)
 	struct crypto_akcipher *tfm = crypto_akcipher_reqtfm(req);
 	struct ecc_ctx *ctx = akcipher_tfm_ctx(tfm);
 	size_t bufsize = ctx->curve->g.ndigits * sizeof(u64);
+	size_t keylen = DIV_ROUND_UP(ctx->curve->nbits, 8);
 	struct ecdsa_signature_ctx sig_ctx = {
 		.curve = ctx->curve,
 	};
@@ -159,10 +160,21 @@ static int ecdsa_verify(struct akcipher_request *req)
 		sg_nents_for_len(req->src, req->src_len + req->dst_len),
 		buffer, req->src_len + req->dst_len, 0);
 
-	ret = asn1_ber_decoder(&ecdsasignature_decoder, &sig_ctx,
-			       buffer, req->src_len);
-	if (ret < 0)
+	if (strcmp(req->enc, "x962") == 0) {
+		ret = asn1_ber_decoder(&ecdsasignature_decoder, &sig_ctx,
+				       buffer, req->src_len);
+		if (ret < 0)
+			goto error;
+	} else if (strcmp(req->enc, "p1363") == 0 &&
+		   req->src_len == 2 * keylen) {
+		ecc_digits_from_bytes(buffer, keylen, sig_ctx.r,
+				      ctx->curve->g.ndigits);
+		ecc_digits_from_bytes(&buffer[keylen], keylen, sig_ctx.s,
+				      ctx->curve->g.ndigits);
+	} else {
+		ret = -EINVAL;
 		goto error;
+	}
 
 	/* if the hash is shorter then we will add leading zeros to fit to ndigits */
 	diff = bufsize - req->dst_len;
diff --git a/crypto/testmgr.h b/crypto/testmgr.h
index 7e34e3f871a3..6c9eb401ad20 100644
--- a/crypto/testmgr.h
+++ b/crypto/testmgr.h
@@ -674,6 +674,7 @@ static const struct akcipher_testvec ecdsa_nist_p192_tv_template[] = {
 	"\x68\x01\x9d\xba\xce\x83\x08\xef\x95\x52\x7b\xa0\x0f\xe4\x18\x86"
 	"\x80\x6f\xa5\x79\x77\xda\xd0",
 	.c_size = 55,
+	.enc = "x962",
 	.public_key_vec = true,
 	.siggen_sigver_test = true,
 	}, {
@@ -698,6 +699,7 @@ static const struct akcipher_testvec ecdsa_nist_p192_tv_template[] = {
 	"\x4f\x53\x75\xc8\x02\x48\xeb\xc3\x92\x0f\x1e\x72\xee\xc4\xa3\xe3"
 	"\x5c\x99\xdb\x92\x5b\x36",
 	.c_size = 54,
+	.enc = "x962",
 	.public_key_vec = true,
 	.siggen_sigver_test = true,
 	}, {
@@ -722,6 +724,7 @@ static const struct akcipher_testvec ecdsa_nist_p192_tv_template[] = {
 	"\x69\x43\xfd\x48\x19\x86\xcf\x32\xdd\x41\x74\x6a\x51\xc7\xd9\x7d"
 	"\x3a\x97\xd9\xcd\x1a\x6a\x49",
 	.c_size = 55,
+	.enc = "x962",
 	.public_key_vec = true,
 	.siggen_sigver_test = true,
 	}, {
@@ -747,6 +750,7 @@ static const struct akcipher_testvec ecdsa_nist_p192_tv_template[] = {
 	"\xbc\x5a\x1f\x82\x96\x61\xd7\xd1\x01\x77\x44\x5d\x53\xa4\x7c\x93"
 	"\x12\x3b\x3b\x28\xfb\x6d\xe1",
 	.c_size = 55,
+	.enc = "x962",
 	.public_key_vec = true,
 	.siggen_sigver_test = true,
 	}, {
@@ -773,6 +777,7 @@ static const struct akcipher_testvec ecdsa_nist_p192_tv_template[] = {
 	"\xb4\x22\x9a\x98\x73\x3c\x83\xa9\x14\x2a\x5e\xf5\xe5\xfb\x72\x28"
 	"\x6a\xdf\x97\xfd\x82\x76\x24",
 	.c_size = 55,
+	.enc = "x962",
 	.public_key_vec = true,
 	.siggen_sigver_test = true,
 	},
@@ -803,6 +808,7 @@ static const struct akcipher_testvec ecdsa_nist_p256_tv_template[] = {
 	"\x8a\xfa\x54\x93\x29\xa7\x70\x86\xf1\x03\x03\xf3\x3b\xe2\x73\xf7"
 	"\xfb\x9d\x8b\xde\xd4\x8d\x6f\xad",
 	.c_size = 72,
+	.enc = "x962",
 	.public_key_vec = true,
 	.siggen_sigver_test = true,
 	}, {
@@ -829,6 +835,7 @@ static const struct akcipher_testvec ecdsa_nist_p256_tv_template[] = {
 	"\x4a\x77\x22\xec\xc8\x66\xbf\x50\x05\x58\x39\x0e\x26\x92\xce\xd5"
 	"\x2e\x8b\xde\x5a\x04\x0e",
 	.c_size = 70,
+	.enc = "x962",
 	.public_key_vec = true,
 	.siggen_sigver_test = true,
 	}, {
@@ -855,6 +862,7 @@ static const struct akcipher_testvec ecdsa_nist_p256_tv_template[] = {
 	"\xa9\x81\xac\x4a\x50\xd0\x91\x0a\x6e\x1b\xc4\xaf\xe1\x83\xc3\x4f"
 	"\x2a\x65\x35\x23\xe3\x1d\xfa",
 	.c_size = 71,
+	.enc = "x962",
 	.public_key_vec = true,
 	.siggen_sigver_test = true,
 	}, {
@@ -882,6 +890,7 @@ static const struct akcipher_testvec ecdsa_nist_p256_tv_template[] = {
 	"\x19\xfb\x5f\x92\xf4\xc9\x23\x37\x69\xf4\x3b\x4f\x47\xcf\x9b\x16"
 	"\xc0\x60\x11\x92\xdc\x17\x89\x12",
 	.c_size = 72,
+	.enc = "x962",
 	.public_key_vec = true,
 	.siggen_sigver_test = true,
 	}, {
@@ -910,6 +919,7 @@ static const struct akcipher_testvec ecdsa_nist_p256_tv_template[] = {
 	"\x00\xdd\xab\xd4\xc0\x2b\xe6\x5c\xad\xc3\x78\x1c\xc2\xc1\x19\x76"
 	"\x31\x79\x4a\xe9\x81\x6a\xee",
 	.c_size = 71,
+	.enc = "x962",
 	.public_key_vec = true,
 	.siggen_sigver_test = true,
 	},
@@ -944,6 +954,7 @@ static const struct akcipher_testvec ecdsa_nist_p384_tv_template[] = {
 	"\x74\xa0\x0f\xbf\xaf\xc3\x36\x76\x4a\xa1\x59\xf1\x1c\xa4\x58\x26"
 	"\x79\x12\x2a\xb7\xc5\x15\x92\xc5",
 	.c_size = 104,
+	.enc = "x962",
 	.public_key_vec = true,
 	.siggen_sigver_test = true,
 	}, {
@@ -974,6 +985,7 @@ static const struct akcipher_testvec ecdsa_nist_p384_tv_template[] = {
 	"\x4d\xd0\xc6\x6e\xb0\xe9\xfc\x14\x9f\x19\xd0\x42\x8b\x93\xc2\x11"
 	"\x88\x2b\x82\x26\x5e\x1c\xda\xfb",
 	.c_size = 104,
+	.enc = "x962",
 	.public_key_vec = true,
 	.siggen_sigver_test = true,
 	}, {
@@ -1004,6 +1016,7 @@ static const struct akcipher_testvec ecdsa_nist_p384_tv_template[] = {
 	"\xc0\x75\x3e\x23\x5e\x36\x4f\x8d\xde\x1e\x93\x8d\x95\xbb\x10\x0e"
 	"\xf4\x1f\x39\xca\x4d\x43",
 	.c_size = 102,
+	.enc = "x962",
 	.public_key_vec = true,
 	.siggen_sigver_test = true,
 	}, {
@@ -1035,6 +1048,7 @@ static const struct akcipher_testvec ecdsa_nist_p384_tv_template[] = {
 	"\x44\x92\x8c\x86\x99\x65\xb3\x97\x96\x17\x04\xc9\x05\x77\xf1\x8e"
 	"\xab\x8d\x4e\xde\xe6\x6d\x9b\x66",
 	.c_size = 104,
+	.enc = "x962",
 	.public_key_vec = true,
 	.siggen_sigver_test = true,
 	}, {
@@ -1067,6 +1081,7 @@ static const struct akcipher_testvec ecdsa_nist_p384_tv_template[] = {
 	"\x5f\x8d\x7a\xf9\xfb\x34\xe4\x8b\x80\xa5\xb6\xda\x2c\x4e\x45\xcf"
 	"\x3c\x93\xff\x50\x5d",
 	.c_size = 101,
+	.enc = "x962",
 	.public_key_vec = true,
 	.siggen_sigver_test = true,
 	},
@@ -1105,6 +1120,7 @@ static const struct akcipher_testvec ecdsa_nist_p521_tv_template[] = {
 	"\x9f\x0e\x64\xcc\xc4\xe8\x43\xd9\x0e\x1c\xad\x22\xda\x82\x00\x35"
 	"\xa3\x50\xb1\xa5\x98\x92\x2a\xa5\x52",
 	.c_size = 137,
+	.enc = "x962",
 	.public_key_vec = true,
 	.siggen_sigver_test = true,
 	},
@@ -1140,6 +1156,7 @@ static const struct akcipher_testvec ecdsa_nist_p521_tv_template[] = {
 	"\x36\x1a\x31\x03\x42\x02\x5f\x50\xf0\xa2\x0d\x1c\x57\x56\x8f\x12"
 	"\xb7\x1d\x91\x55\x38\xb6\xf6\x34\x65\xc7\xbd",
 	.c_size = 139,
+	.enc = "x962",
 	.public_key_vec = true,
 	.siggen_sigver_test = true,
 	},
@@ -1176,6 +1193,7 @@ static const struct akcipher_testvec ecdsa_nist_p521_tv_template[] = {
 	"\xdb\x8a\x0d\x6a\xc3\xf3\x7a\xd1\xfa\xe7\xa7\xe5\x5a\x94\x56\xcf"
 	"\x8f\xb4\x22\xc6\x4f\xab\x2b\x62\xc1\x42\xb1",
 	.c_size = 139,
+	.enc = "x962",
 	.public_key_vec = true,
 	.siggen_sigver_test = true,
 	},
@@ -1213,6 +1231,7 @@ static const struct akcipher_testvec ecdsa_nist_p521_tv_template[] = {
 	"\xc0\xcb\xaa\x00\x55\xbb\x6a\xb4\x73\x00\xd2\x72\x74\x13\x63\x39"
 	"\xa6\xe5\x25\x46\x1e\x77\x44\x78\xe0\xd1\x04",
 	.c_size = 139,
+	.enc = "x962",
 	.public_key_vec = true,
 	.siggen_sigver_test = true,
 	},

---

## [8] Lukas Wunner — 2024-06-30
*Subject: [PATCH v2 07/18] spdm: Introduce library to authenticate devices*

From: Jonathan Cameron <Jonathan.Cameron@huawei.com>

The Security Protocol and Data Model (SPDM) allows for device
authentication, measurement, key exchange and encrypted sessions.

SPDM was conceived by the Distributed Management Task Force (DMTF).
Its specification defines a request/response protocol spoken between
host and attached devices over a variety of transports:

  https://www.dmtf.org/dsp/DSP0274

This implementation supports SPDM 1.0 through 1.3 (the latest version).
It is designed to be transport-agnostic as the kernel already supports
four different SPDM-capable transports:

* PCIe Data Object Exchange, which is a mailbox in PCI config space
  (PCIe r6.2 sec 6.30, drivers/pci/doe.c)
* Management Component Transport Protocol
  (MCTP, Documentation/networking/mctp.rst)
* TCP/IP (in draft stage)
  https://www.dmtf.org/sites/default/files/standards/documents/DSP0287_1.0.0WIP99.pdf
* SCSI and ATA (in draft stage)
  "SECURITY PROTOCOL IN/OUT" and "TRUSTED SEND/RECEIVE" commands

Use cases for SPDM include, but are not limited to:

* PCIe Component Measurement and Authentication (PCIe r6.2 sec 6.31)
* Compute Express Link (CXL r3.0 sec 14.11.6)
* Open Compute Project (Attestation of System Components v1.0)
  https://www.opencompute.org/documents/attestation-v1-0-20201104-pdf
* Open Compute Project (Datacenter NVMe SSD Specification v2.0)
  https://www.opencompute.org/documents/datacenter-nvme-ssd-specification-v2-0r21-pdf

The initial focus of this implementation is enabling PCIe CMA device
authentication.  As such, only a subset of the SPDM specification is
contained herein, namely the request/response sequence GET_VERSION,
GET_CAPABILITIES, NEGOTIATE_ALGORITHMS, GET_DIGESTS, GET_CERTIFICATE
and CHALLENGE.

This sequence first negotiates the SPDM protocol version, capabilities
and algorithms with the device.  It then retrieves the up to eight
certificate chains which may be provisioned on the device.  Finally it
performs challenge-response authentication with the device using one of
those eight certificate chains and the algorithms negotiated before.
The challenge-response authentication comprises computing a hash over
all exchanged messages to detect modification by a man-in-the-middle
or media error.  The hash is then signed with the device's private key
and the resulting signature is verified by the kernel using the device's
public key from the certificate chain.  Nonces are included in the
message sequence to protect against replay attacks.

A simple API is provided for subsystems wishing to authenticate devices:
spdm_create(), spdm_authenticate() (can be called repeatedly for
reauthentication) and spdm_destroy().  Certificates presented by devices
are validated against an in-kernel keyring of trusted root certificates.
A pointer to the keyring is passed to spdm_create().

The set of supported cryptographic algorithms is limited to those
declared mandatory in PCIe r6.2 sec 6.31.3.  Adding more algorithms
is straightforward as long as the crypto subsystem supports them.

Future commits will extend this implementation with support for
measurement, key exchange and encrypted sessions.

So far, only the SPDM requester role is implemented.  Care was taken to
allow for effortless addition of the responder role at a later stage.
This could be needed for a PCIe host bridge operating in endpoint mode.
The responder role will be able to reuse struct definitions and helpers
such as spdm_create_combined_prefix().

Credits:  Jonathan wrote a proof-of-concept of this SPDM implementation.
Lukas reworked it for upstream.

Signed-off-by: Jonathan Cameron <Jonathan.Cameron@huawei.com>
Co-developed-by: Lukas Wunner <lukas@wunner.de>
Signed-off-by: Lukas Wunner <lukas@wunner.de>
---
 MAINTAINERS                 |  11 +
 include/linux/spdm.h        |  33 ++
 lib/Kconfig                 |  15 +
 lib/Makefile                |   2 +
 lib/spdm/Makefile           |  10 +
 lib/spdm/core.c             | 425 ++++++++++++++++++++++
 lib/spdm/req-authenticate.c | 704 ++++++++++++++++++++++++++++++++++++
 lib/spdm/spdm.h             | 520 ++++++++++++++++++++++++++
 8 files changed, 1720 insertions(+)
 create mode 100644 include/linux/spdm.h
 create mode 100644 lib/spdm/Makefile
 create mode 100644 lib/spdm/core.c
 create mode 100644 lib/spdm/req-authenticate.c
 create mode 100644 lib/spdm/spdm.h

diff --git a/MAINTAINERS b/MAINTAINERS
index d6c90161c7bf..dbe16eea8818 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -20145,6 +20145,17 @@ M:	Security Officers <security@kernel.org>
 S:	Supported
 F:	Documentation/process/security-bugs.rst
 
+SECURITY PROTOCOL AND DATA MODEL (SPDM)
+M:	Jonathan Cameron <jic23@kernel.org>
+M:	Lukas Wunner <lukas@wunner.de>
+L:	linux-coco@lists.linux.dev
+L:	linux-cxl@vger.kernel.org
+L:	linux-pci@vger.kernel.org
+S:	Maintained
+T:	git git://git.kernel.org/pub/scm/linux/kernel/git/devsec/spdm.git
+F:	include/linux/spdm.h
+F:	lib/spdm/
+
 SECURITY SUBSYSTEM
 M:	Paul Moore <paul@paul-moore.com>
 M:	James Morris <jmorris@namei.org>
diff --git a/include/linux/spdm.h b/include/linux/spdm.h
new file mode 100644
index 000000000000..0da7340020c4
--- /dev/null
+++ b/include/linux/spdm.h
@@ -0,0 +1,33 @@
+/* SPDX-License-Identifier: GPL-2.0 */
+/*
+ * DMTF Security Protocol and Data Model (SPDM)
+ * https://www.dmtf.org/dsp/DSP0274
+ *
+ * Copyright (C) 2021-22 Huawei
+ *     Jonathan Cameron <Jonathan.Cameron@huawei.com>
+ *
+ * Copyright (C) 2022-24 Intel Corporation
+ */
+
+#ifndef _SPDM_H_
+#define _SPDM_H_
+
+#include <linux/types.h>
+
+struct key;
+struct device;
+struct spdm_state;
+
+typedef ssize_t (spdm_transport)(void *priv, struct device *dev,
+				 const void *request, size_t request_sz,
+				 void *response, size_t response_sz);
+
+struct spdm_state *spdm_create(struct device *dev, spdm_transport *transport,
+			       void *transport_priv, u32 transport_sz,
+			       struct key *keyring);
+
+int spdm_authenticate(struct spdm_state *spdm_state);
+
+void spdm_destroy(struct spdm_state *spdm_state);
+
+#endif
diff --git a/lib/Kconfig b/lib/Kconfig
index d33a268bc256..9011fa32af45 100644
--- a/lib/Kconfig
+++ b/lib/Kconfig
@@ -782,3 +782,18 @@ config POLYNOMIAL
 
 config FIRMWARE_TABLE
 	bool
+
+config SPDM
+	tristate
+	select CRYPTO
+	select KEYS
+	select ASYMMETRIC_KEY_TYPE
+	select ASYMMETRIC_PUBLIC_KEY_SUBTYPE
+	select X509_CERTIFICATE_PARSER
+	help
+	  The Security Protocol and Data Model (SPDM) allows for device
+	  authentication, measurement, key exchange and encrypted sessions.
+
+	  Crypto algorithms negotiated with SPDM are limited to those enabled
+	  in .config.  Drivers selecting SPDM therefore need to also select
+	  any algorithms they deem mandatory.
diff --git a/lib/Makefile b/lib/Makefile
index 3b1769045651..b2ef14d1fa71 100644
--- a/lib/Makefile
+++ b/lib/Makefile
@@ -301,6 +301,8 @@ obj-$(CONFIG_PERCPU_TEST) += percpu_test.o
 obj-$(CONFIG_ASN1) += asn1_decoder.o
 obj-$(CONFIG_ASN1_ENCODER) += asn1_encoder.o
 
+obj-$(CONFIG_SPDM) += spdm/
+
 obj-$(CONFIG_FONT_SUPPORT) += fonts/
 
 hostprogs	:= gen_crc32table
diff --git a/lib/spdm/Makefile b/lib/spdm/Makefile
new file mode 100644
index 000000000000..f579cc898dbc
--- /dev/null
+++ b/lib/spdm/Makefile
@@ -0,0 +1,10 @@
+# SPDX-License-Identifier: GPL-2.0
+#
+# DMTF Security Protocol and Data Model (SPDM)
+# https://www.dmtf.org/dsp/DSP0274
+#
+# Copyright (C) 2024 Intel Corporation
+
+obj-$(CONFIG_SPDM) += spdm.o
+
+spdm-y := core.o req-authenticate.o
diff --git a/lib/spdm/core.c b/lib/spdm/core.c
new file mode 100644
index 000000000000..f06402f6d127
--- /dev/null
+++ b/lib/spdm/core.c
@@ -0,0 +1,425 @@
+// SPDX-License-Identifier: GPL-2.0
+/*
+ * DMTF Security Protocol and Data Model (SPDM)
+ * https://www.dmtf.org/dsp/DSP0274
+ *
+ * Core routines for message exchange, message transcript,
+ * signature verification and session state lifecycle
+ *
+ * Copyright (C) 2021-22 Huawei
+ *     Jonathan Cameron <Jonathan.Cameron@huawei.com>
+ *
+ * Copyright (C) 2022-24 Intel Corporation
+ */
+
+#include "spdm.h"
+
+#include <linux/dev_printk.h>
+#include <linux/module.h>
+
+#include <crypto/hash.h>
+#include <crypto/public_key.h>
+
+static int spdm_err(struct device *dev, struct spdm_error_rsp *rsp)
+{
+	switch (rsp->error_code) {
+	case SPDM_INVALID_REQUEST:
+		dev_err(dev, "Invalid request\n");
+		return -EINVAL;
+	case SPDM_INVALID_SESSION:
+		if (rsp->version == 0x11) {
+			dev_err(dev, "Invalid session %#x\n", rsp->error_data);
+			return -EINVAL;
+		}
+		break;
+	case SPDM_BUSY:
+		dev_err(dev, "Busy\n");
+		return -EBUSY;
+	case SPDM_UNEXPECTED_REQUEST:
+		dev_err(dev, "Unexpected request\n");
+		return -EINVAL;
+	case SPDM_UNSPECIFIED:
+		dev_err(dev, "Unspecified error\n");
+		return -EINVAL;
+	case SPDM_DECRYPT_ERROR:
+		dev_err(dev, "Decrypt error\n");
+		return -EIO;
+	case SPDM_UNSUPPORTED_REQUEST:
+		dev_err(dev, "Unsupported request %#x\n", rsp->error_data);
+		return -EINVAL;
+	case SPDM_REQUEST_IN_FLIGHT:
+		dev_err(dev, "Request in flight\n");
+		return -EINVAL;
+	case SPDM_INVALID_RESPONSE_CODE:
+		dev_err(dev, "Invalid response code\n");
+		return -EINVAL;
+	case SPDM_SESSION_LIMIT_EXCEEDED:
+		dev_err(dev, "Session limit exceeded\n");
+		return -EBUSY;
+	case SPDM_SESSION_REQUIRED:
+		dev_err(dev, "Session required\n");
+		return -EINVAL;
+	case SPDM_RESET_REQUIRED:
+		dev_err(dev, "Reset required\n");
+		return -ECONNRESET;
+	case SPDM_RESPONSE_TOO_LARGE:
+		dev_err(dev, "Response too large\n");
+		return -EINVAL;
+	case SPDM_REQUEST_TOO_LARGE:
+		dev_err(dev, "Request too large\n");
+		return -EINVAL;
+	case SPDM_LARGE_RESPONSE:
+		dev_err(dev, "Large response\n");
+		return -EMSGSIZE;
+	case SPDM_MESSAGE_LOST:
+		dev_err(dev, "Message lost\n");
+		return -EIO;
+	case SPDM_INVALID_POLICY:
+		dev_err(dev, "Invalid policy\n");
+		return -EINVAL;
+	case SPDM_VERSION_MISMATCH:
+		dev_err(dev, "Version mismatch\n");
+		return -EINVAL;
+	case SPDM_RESPONSE_NOT_READY:
+		dev_err(dev, "Response not ready\n");
+		return -EINPROGRESS;
+	case SPDM_REQUEST_RESYNCH:
+		dev_err(dev, "Request resynchronization\n");
+		return -ECONNRESET;
+	case SPDM_OPERATION_FAILED:
+		dev_err(dev, "Operation failed\n");
+		return -EINVAL;
+	case SPDM_NO_PENDING_REQUESTS:
+		return -ENOENT;
+	case SPDM_VENDOR_DEFINED_ERROR:
+		dev_err(dev, "Vendor defined error\n");
+		return -EINVAL;
+	}
+
+	dev_err(dev, "Undefined error %#x\n", rsp->error_code);
+	return -EINVAL;
+}
+
+/**
+ * spdm_exchange() - Perform SPDM message exchange with device
+ *
+ * @spdm_state: SPDM session state
+ * @req: Request message
+ * @req_sz: Size of @req
+ * @rsp: Response message
+ * @rsp_sz: Size of @rsp
+ *
+ * Send the request @req to the device via the @transport in @spdm_state and
+ * receive the response into @rsp, respecting the maximum buffer size @rsp_sz.
+ * The request version is automatically populated.
+ *
+ * Return response size on success or a negative errno.  Response size may be
+ * less than @rsp_sz and the caller is responsible for checking that.  It may
+ * also be more than expected (though never more than @rsp_sz), e.g. if the
+ * transport receives only dword-sized chunks.
+ */
+ssize_t spdm_exchange(struct spdm_state *spdm_state,
+		      void *req, size_t req_sz, void *rsp, size_t rsp_sz)
+{
+	struct spdm_header *request = req;
+	struct spdm_header *response = rsp;
+	ssize_t rc, length;
+
+	if (req_sz < sizeof(struct spdm_header) ||
+	    rsp_sz < sizeof(struct spdm_header))
+		return -EINVAL;
+
+	request->version = spdm_state->version;
+
+	rc = spdm_state->transport(spdm_state->transport_priv, spdm_state->dev,
+				   req, req_sz, rsp, rsp_sz);
+	if (rc < 0)
+		return rc;
+
+	length = rc;
+	if (length < sizeof(struct spdm_header))
+		return length; /* Truncated response is handled by callers */
+
+	if (response->code == SPDM_ERROR)
+		return spdm_err(spdm_state->dev, (struct spdm_error_rsp *)rsp);
+
+	if (response->code != (request->code & ~SPDM_REQ)) {
+		dev_err(spdm_state->dev,
+			"Response code %#x does not match request code %#x\n",
+			response->code, request->code);
+		return -EPROTO;
+	}
+
+	return length;
+}
+
+/**
+ * spdm_alloc_transcript() - Allocate transcript buffer
+ *
+ * @spdm_state: SPDM session state
+ *
+ * Allocate a buffer to accommodate the concatenation of all SPDM messages
+ * exchanged during an authentication sequence.  Used to verify the signature,
+ * as it is computed over the hashed transcript.
+ *
+ * Transcript size is initially one page.  It grows by additional pages as
+ * needed.  Minimum size of an authentication sequence is 1k (only one slot
+ * occupied, only one ECC P256 certificate in chain, SHA 256 hash selected).
+ * Maximum can be several MBytes.  Between 4k and 64k is probably typical.
+ *
+ * Return 0 on success or a negative errno.
+ */
+int spdm_alloc_transcript(struct spdm_state *spdm_state)
+{
+	spdm_state->transcript = kvmalloc(PAGE_SIZE, GFP_KERNEL);
+	if (!spdm_state->transcript)
+		return -ENOMEM;
+
+	spdm_state->transcript_end = spdm_state->transcript;
+	spdm_state->transcript_max = PAGE_SIZE;
+
+	return 0;
+}
+
+/**
+ * spdm_free_transcript() - Free transcript buffer
+ *
+ * @spdm_state: SPDM session state
+ *
+ * Free the transcript buffer after performing authentication.  Reset the
+ * pointer to the current end of transcript as well as the allocation size.
+ */
+void spdm_free_transcript(struct spdm_state *spdm_state)
+{
+	kvfree(spdm_state->transcript);
+	spdm_state->transcript_end = NULL;
+	spdm_state->transcript_max = 0;
+}
+
+/**
+ * spdm_append_transcript() - Append a message to transcript buffer
+ *
+ * @spdm_state: SPDM session state
+ * @msg: SPDM message
+ * @msg_sz: Size of @msg
+ *
+ * Append an SPDM message to the transcript after reception or transmission.
+ * Reallocate a larger transcript buffer if the message exceeds its current
+ * allocation size.
+ *
+ * If the message to be appended is known to fit into the allocation size,
+ * it may be directly received into or transmitted from the transcript buffer
+ * instead of calling this function:  Simply use the @transcript_end pointer in
+ * struct spdm_state as the position to store the message, then advance the
+ * pointer by the message size.
+ *
+ * Return 0 on success or a negative errno.
+ */
+int spdm_append_transcript(struct spdm_state *spdm_state,
+			   const void *msg, size_t msg_sz)
+{
+	size_t transcript_sz = spdm_state->transcript_end -
+			       spdm_state->transcript;
+
+	if (transcript_sz + msg_sz > spdm_state->transcript_max) {
+		size_t new_sz = round_up(transcript_sz + msg_sz, PAGE_SIZE);
+		void *new = kvrealloc(spdm_state->transcript,
+				      spdm_state->transcript_max,
+				      new_sz, GFP_KERNEL);
+		if (!new)
+			return -ENOMEM;
+
+		spdm_state->transcript = new;
+		spdm_state->transcript_end = new + transcript_sz;
+		spdm_state->transcript_max = new_sz;
+	}
+
+	memcpy(spdm_state->transcript_end, msg, msg_sz);
+	spdm_state->transcript_end += msg_sz;
+
+	return 0;
+}
+
+/**
+ * spdm_create_combined_prefix() - Create combined_spdm_prefix for a hash
+ *
+ * @version: SPDM version negotiated during GET_VERSION exchange
+ * @spdm_context: SPDM context of signature generation (or verification)
+ * @buf: Buffer to receive combined_spdm_prefix (100 bytes)
+ *
+ * From SPDM 1.2, a hash is prefixed with the SPDM version and context before
+ * a signature is generated (or verified) over the resulting concatenation
+ * (SPDM 1.2.0 section 15).  Create that prefix.
+ */
+void spdm_create_combined_prefix(u8 version, const char *spdm_context,
+				 void *buf)
+{
+	u8 major = FIELD_GET(0xf0, version);
+	u8 minor = FIELD_GET(0x0f, version);
+	size_t len = strlen(spdm_context);
+	int rc, zero_pad;
+
+	rc = snprintf(buf, SPDM_PREFIX_SZ + 1,
+		      "dmtf-spdm-v%hhx.%hhx.*dmtf-spdm-v%hhx.%hhx.*"
+		      "dmtf-spdm-v%hhx.%hhx.*dmtf-spdm-v%hhx.%hhx.*",
+		      major, minor, major, minor, major, minor, major, minor);
+	WARN_ON(rc != SPDM_PREFIX_SZ);
+
+	zero_pad = SPDM_COMBINED_PREFIX_SZ - SPDM_PREFIX_SZ - 1 - len;
+	WARN_ON(zero_pad < 0);
+
+	memset(buf + SPDM_PREFIX_SZ + 1, 0, zero_pad);
+	memcpy(buf + SPDM_PREFIX_SZ + 1 + zero_pad, spdm_context, len);
+}
+
+/**
+ * spdm_verify_signature() - Verify signature against leaf key
+ *
+ * @spdm_state: SPDM session state
+ * @spdm_context: SPDM context (used to create combined_spdm_prefix)
+ *
+ * Implementation of the abstract SPDMSignatureVerify() function described in
+ * SPDM 1.2.0 section 16:  Compute the hash over @spdm_state->transcript and
+ * verify that the signature at the end of the transcript was generated by
+ * @spdm_state->leaf_key.  Hashing the entire transcript allows detection
+ * of message modification by a man-in-the-middle or media error.
+ *
+ * Return 0 on success or a negative errno.
+ */
+int spdm_verify_signature(struct spdm_state *spdm_state,
+			  const char *spdm_context)
+{
+	struct public_key_signature sig = {
+		.s = spdm_state->transcript_end - spdm_state->sig_len,
+		.s_size = spdm_state->sig_len,
+		.encoding = spdm_state->base_asym_enc,
+		.hash_algo = spdm_state->base_hash_alg_name,
+	};
+	u8 *mhash __free(kfree) = NULL;
+	u8 *m __free(kfree);
+	int rc;
+
+	m = kmalloc(SPDM_COMBINED_PREFIX_SZ + spdm_state->hash_len, GFP_KERNEL);
+	if (!m)
+		return -ENOMEM;
+
+	/* Hash the transcript (sans trailing signature) */
+	rc = crypto_shash_digest(spdm_state->desc, spdm_state->transcript,
+				 (void *)sig.s - spdm_state->transcript,
+				 m + SPDM_COMBINED_PREFIX_SZ);
+	if (rc)
+		return rc;
+
+	if (spdm_state->version <= 0x11) {
+		/*
+		 * SPDM 1.0 and 1.1 compute the signature only over the hash
+		 * (SPDM 1.0.0 section 4.9.2.7).
+		 */
+		sig.digest = m + SPDM_COMBINED_PREFIX_SZ;
+		sig.digest_size = spdm_state->hash_len;
+	} else {
+		/*
+		 * From SPDM 1.2, the hash is prefixed with spdm_context before
+		 * computing the signature over the resulting message M
+		 * (SPDM 1.2.0 sec 15).
+		 */
+		spdm_create_combined_prefix(spdm_state->version, spdm_context,
+					    m);
+
+		/*
+		 * RSA and ECDSA algorithms require that M is hashed once more.
+		 * EdDSA and SM2 algorithms omit that step.
+		 * The switch statement prepares for their introduction.
+		 */
+		switch (spdm_state->base_asym_alg) {
+		default:
+			mhash = kmalloc(spdm_state->hash_len, GFP_KERNEL);
+			if (!mhash)
+				return -ENOMEM;
+
+			rc = crypto_shash_digest(spdm_state->desc, m,
+				SPDM_COMBINED_PREFIX_SZ + spdm_state->hash_len,
+				mhash);
+			if (rc)
+				return rc;
+
+			sig.digest = mhash;
+			sig.digest_size = spdm_state->hash_len;
+			break;
+		}
+	}
+
+	return public_key_verify_signature(spdm_state->leaf_key, &sig);
+}
+
+/**
+ * spdm_reset() - Free cryptographic data structures
+ *
+ * @spdm_state: SPDM session state
+ *
+ * Free cryptographic data structures when an SPDM session is destroyed or
+ * when the device is reauthenticated.
+ */
+void spdm_reset(struct spdm_state *spdm_state)
+{
+	public_key_free(spdm_state->leaf_key);
+	spdm_state->leaf_key = NULL;
+
+	kfree(spdm_state->desc);
+	spdm_state->desc = NULL;
+
+	crypto_free_shash(spdm_state->shash);
+	spdm_state->shash = NULL;
+}
+
+/**
+ * spdm_create() - Allocate SPDM session
+ *
+ * @dev: Responder device
+ * @transport: Transport function to perform one message exchange
+ * @transport_priv: Transport private data
+ * @transport_sz: Maximum message size the transport is capable of (in bytes)
+ * @keyring: Trusted root certificates
+ *
+ * Return a pointer to the allocated SPDM session state or NULL on error.
+ */
+struct spdm_state *spdm_create(struct device *dev, spdm_transport *transport,
+			       void *transport_priv, u32 transport_sz,
+			       struct key *keyring)
+{
+	struct spdm_state *spdm_state = kzalloc(sizeof(*spdm_state), GFP_KERNEL);
+
+	if (!spdm_state)
+		return NULL;
+
+	spdm_state->dev = dev;
+	spdm_state->transport = transport;
+	spdm_state->transport_priv = transport_priv;
+	spdm_state->transport_sz = transport_sz;
+	spdm_state->root_keyring = keyring;
+
+	mutex_init(&spdm_state->lock);
+
+	return spdm_state;
+}
+EXPORT_SYMBOL_GPL(spdm_create);
+
+/**
+ * spdm_destroy() - Destroy SPDM session
+ *
+ * @spdm_state: SPDM session state
+ */
+void spdm_destroy(struct spdm_state *spdm_state)
+{
+	u8 slot;
+
+	for_each_set_bit(slot, &spdm_state->provisioned_slots, SPDM_SLOTS)
+		kvfree(spdm_state->slot[slot]);
+
+	spdm_reset(spdm_state);
+	mutex_destroy(&spdm_state->lock);
+	kfree(spdm_state);
+}
+EXPORT_SYMBOL_GPL(spdm_destroy);
+
+MODULE_LICENSE("GPL");
diff --git a/lib/spdm/req-authenticate.c b/lib/spdm/req-authenticate.c
new file mode 100644
index 000000000000..51fdb88f519b
--- /dev/null
+++ b/lib/spdm/req-authenticate.c
@@ -0,0 +1,704 @@
+// SPDX-License-Identifier: GPL-2.0
+/*
+ * DMTF Security Protocol and Data Model (SPDM)
+ * https://www.dmtf.org/dsp/DSP0274
+ *
+ * Requester role: Authenticate a device
+ *
+ * Copyright (C) 2021-22 Huawei
+ *     Jonathan Cameron <Jonathan.Cameron@huawei.com>
+ *
+ * Copyright (C) 2022-24 Intel Corporation
+ */
+
+#include "spdm.h"
+
+#include <linux/dev_printk.h>
+#include <linux/key.h>
+#include <linux/random.h>
+
+#include <asm/unaligned.h>
+#include <crypto/hash.h>
+#include <crypto/hash_info.h>
+#include <keys/asymmetric-type.h>
+#include <keys/x509-parser.h>
+
+/* SPDM 1.2.0 margin no 359 and 803 */
+static const char *spdm_context = "responder-challenge_auth signing";
+
+/*
+ * All SPDM messages exchanged during an authentication sequence up to and
+ * including GET_DIGESTS fit into a single page, hence are stored in the
+ * transcript without bounds checking.  Only subsequent GET_CERTIFICATE
+ * and CHALLENGE exchanges may exceed one page.
+ */
+static_assert(PAGE_SIZE >=
+	sizeof(struct spdm_get_version_req) +
+	struct_size_t(struct spdm_get_version_rsp,
+		      version_number_entries, 255) +
+	sizeof(struct spdm_get_capabilities_req) +
+	sizeof(struct spdm_get_capabilities_rsp) +
+	sizeof(struct spdm_negotiate_algs_req) +
+	sizeof(struct spdm_negotiate_algs_rsp) +
+	sizeof(struct spdm_req_alg_struct) * 2 * SPDM_MAX_REQ_ALG_STRUCT +
+	sizeof(struct spdm_get_digests_req) +
+	struct_size_t(struct spdm_get_digests_rsp,
+		      digests, SPDM_SLOTS * SHA512_DIGEST_SIZE));
+
+static int spdm_get_version(struct spdm_state *spdm_state)
+{
+	struct spdm_get_version_req *req = spdm_state->transcript;
+	struct spdm_get_version_rsp *rsp;
+	bool foundver = false;
+	int rc, length, i;
+
+	spdm_state->version = 0x10;
+
+	*req = (struct spdm_get_version_req) {
+		.code = SPDM_GET_VERSION,
+	};
+
+	rsp = spdm_state->transcript_end += sizeof(*req);
+
+	rc = spdm_exchange(spdm_state, req, sizeof(*req), rsp,
+			   struct_size(rsp, version_number_entries, 255));
+	if (rc < 0)
+		return rc;
+
+	length = rc;
+	if (length < sizeof(*rsp) ||
+	    length < struct_size(rsp, version_number_entries,
+				 rsp->version_number_entry_count)) {
+		dev_err(spdm_state->dev, "Truncated version response\n");
+		return -EIO;
+	}
+
+	spdm_state->transcript_end +=
+		     struct_size(rsp, version_number_entries,
+				 rsp->version_number_entry_count);
+
+	for (i = 0; i < rsp->version_number_entry_count; i++) {
+		u8 ver = le16_to_cpu(rsp->version_number_entries[i]) >> 8;
+
+		if (ver >= spdm_state->version && ver <= SPDM_MAX_VER) {
+			spdm_state->version = ver;
+			foundver = true;
+		}
+	}
+	if (!foundver) {
+		dev_err(spdm_state->dev, "No common supported version\n");
+		return -EPROTO;
+	}
+
+	return 0;
+}
+
+static int spdm_get_capabilities(struct spdm_state *spdm_state)
+{
+	struct spdm_get_capabilities_req *req = spdm_state->transcript_end;
+	struct spdm_get_capabilities_rsp *rsp;
+	size_t req_sz, rsp_sz;
+	int rc, length;
+
+	*req = (struct spdm_get_capabilities_req) {
+		.code = SPDM_GET_CAPABILITIES,
+		.ctexponent = SPDM_CTEXPONENT,
+		.flags = cpu_to_le32(SPDM_REQ_CAPS),
+	};
+
+	if (spdm_state->version == 0x10) {
+		req_sz = offsetofend(typeof(*req), param2);
+		rsp_sz = offsetofend(typeof(*rsp), flags);
+	} else if (spdm_state->version == 0x11) {
+		req_sz = offsetofend(typeof(*req), flags);
+		rsp_sz = offsetofend(typeof(*rsp), flags);
+	} else {
+		req_sz = sizeof(*req);
+		rsp_sz = sizeof(*rsp);
+		req->data_transfer_size = cpu_to_le32(spdm_state->transport_sz);
+		req->max_spdm_msg_size = cpu_to_le32(spdm_state->transport_sz);
+	}
+
+	rsp = spdm_state->transcript_end += req_sz;
+
+	rc = spdm_exchange(spdm_state, req, req_sz, rsp, rsp_sz);
+	if (rc < 0)
+		return rc;
+
+	length = rc;
+	if (length < rsp_sz) {
+		dev_err(spdm_state->dev, "Truncated capabilities response\n");
+		return -EIO;
+	}
+
+	spdm_state->transcript_end += rsp_sz;
+
+	spdm_state->rsp_caps = le32_to_cpu(rsp->flags);
+	if ((spdm_state->rsp_caps & SPDM_RSP_MIN_CAPS) != SPDM_RSP_MIN_CAPS)
+		return -EPROTONOSUPPORT;
+
+	if (spdm_state->version >= 0x12) {
+		u32 data_transfer_size = le32_to_cpu(rsp->data_transfer_size);
+		if (data_transfer_size < SPDM_MIN_DATA_TRANSFER_SIZE) {
+			dev_err(spdm_state->dev,
+				"Malformed capabilities response\n");
+			return -EPROTO;
+		}
+		spdm_state->transport_sz = min(spdm_state->transport_sz,
+					       data_transfer_size);
+	}
+
+	return 0;
+}
+
+static int spdm_parse_algs(struct spdm_state *spdm_state)
+{
+	switch (spdm_state->base_asym_alg) {
+	case SPDM_ASYM_RSASSA_2048:
+		spdm_state->sig_len = 256;
+		spdm_state->base_asym_enc = "pkcs1";
+		break;
+	case SPDM_ASYM_RSASSA_3072:
+		spdm_state->sig_len = 384;
+		spdm_state->base_asym_enc = "pkcs1";
+		break;
+	case SPDM_ASYM_RSASSA_4096:
+		spdm_state->sig_len = 512;
+		spdm_state->base_asym_enc = "pkcs1";
+		break;
+	case SPDM_ASYM_ECDSA_ECC_NIST_P256:
+		spdm_state->sig_len = 64;
+		spdm_state->base_asym_enc = "p1363";
+		break;
+	case SPDM_ASYM_ECDSA_ECC_NIST_P384:
+		spdm_state->sig_len = 96;
+		spdm_state->base_asym_enc = "p1363";
+		break;
+	case SPDM_ASYM_ECDSA_ECC_NIST_P521:
+		spdm_state->sig_len = 132;
+		spdm_state->base_asym_enc = "p1363";
+		break;
+	default:
+		dev_err(spdm_state->dev, "Unknown asym algorithm\n");
+		return -EINVAL;
+	}
+
+	switch (spdm_state->base_hash_alg) {
+	case SPDM_HASH_SHA_256:
+		spdm_state->base_hash_alg_name = "sha256";
+		break;
+	case SPDM_HASH_SHA_384:
+		spdm_state->base_hash_alg_name = "sha384";
+		break;
+	case SPDM_HASH_SHA_512:
+		spdm_state->base_hash_alg_name = "sha512";
+		break;
+	default:
+		dev_err(spdm_state->dev, "Unknown hash algorithm\n");
+		return -EINVAL;
+	}
+
+	/*
+	 * shash and desc allocations are reused for subsequent measurement
+	 * retrieval, hence are not freed until spdm_reset().
+	 */
+	spdm_state->shash = crypto_alloc_shash(spdm_state->base_hash_alg_name,
+					       0, 0);
+	if (!spdm_state->shash)
+		return -ENOMEM;
+
+	spdm_state->desc = kzalloc(sizeof(*spdm_state->desc) +
+				   crypto_shash_descsize(spdm_state->shash),
+				   GFP_KERNEL);
+	if (!spdm_state->desc)
+		return -ENOMEM;
+
+	spdm_state->desc->tfm = spdm_state->shash;
+
+	/* Used frequently to compute offsets, so cache H */
+	spdm_state->hash_len = crypto_shash_digestsize(spdm_state->shash);
+
+	return crypto_shash_init(spdm_state->desc);
+}
+
+static int spdm_negotiate_algs(struct spdm_state *spdm_state)
+{
+	struct spdm_negotiate_algs_req *req = spdm_state->transcript_end;
+	struct spdm_negotiate_algs_rsp *rsp;
+	struct spdm_req_alg_struct *req_alg_struct;
+	size_t req_sz = sizeof(*req);
+	size_t rsp_sz = sizeof(*rsp);
+	int rc, length;
+
+	/* Request length shall be <= 128 bytes (SPDM 1.1.0 margin no 185) */
+	BUILD_BUG_ON(req_sz > 128);
+
+	*req = (struct spdm_negotiate_algs_req) {
+		.code = SPDM_NEGOTIATE_ALGS,
+		.length = cpu_to_le16(req_sz),
+		.base_asym_algo = cpu_to_le32(SPDM_ASYM_ALGOS),
+		.base_hash_algo = cpu_to_le32(SPDM_HASH_ALGOS),
+	};
+
+	rsp = spdm_state->transcript_end += req_sz;
+
+	rc = spdm_exchange(spdm_state, req, req_sz, rsp, rsp_sz);
+	if (rc < 0)
+		return rc;
+
+	length = rc;
+	if (length < sizeof(*rsp) ||
+	    length < sizeof(*rsp) + rsp->param1 * sizeof(*req_alg_struct)) {
+		dev_err(spdm_state->dev, "Truncated algorithms response\n");
+		return -EIO;
+	}
+
+	/*
+	 * If request contained a ReqAlgStruct not supported by responder,
+	 * the corresponding RespAlgStruct may be omitted in response.
+	 * Calculate the actual (possibly shorter) response length:
+	 */
+	spdm_state->transcript_end +=
+		     sizeof(*rsp) + rsp->param1 * sizeof(*req_alg_struct);
+
+	spdm_state->base_asym_alg = le32_to_cpu(rsp->base_asym_sel);
+	spdm_state->base_hash_alg = le32_to_cpu(rsp->base_hash_sel);
+
+	if ((spdm_state->base_asym_alg & SPDM_ASYM_ALGOS) == 0 ||
+	    (spdm_state->base_hash_alg & SPDM_HASH_ALGOS) == 0) {
+		dev_err(spdm_state->dev, "No common supported algorithms\n");
+		return -EPROTO;
+	}
+
+	/* Responder shall select exactly 1 alg (SPDM 1.0.0 table 14) */
+	if (hweight32(spdm_state->base_asym_alg) != 1 ||
+	    hweight32(spdm_state->base_hash_alg) != 1 ||
+	    rsp->ext_asym_sel_count != 0 ||
+	    rsp->ext_hash_sel_count != 0 ||
+	    rsp->param1 > req->param1) {
+		dev_err(spdm_state->dev, "Malformed algorithms response\n");
+		return -EPROTO;
+	}
+
+	return spdm_parse_algs(spdm_state);
+}
+
+static int spdm_get_digests(struct spdm_state *spdm_state)
+{
+	struct spdm_get_digests_req *req = spdm_state->transcript_end;
+	struct spdm_get_digests_rsp *rsp;
+	unsigned long deprovisioned_slots;
+	int rc, length;
+	size_t rsp_sz;
+	u8 slot;
+
+	*req = (struct spdm_get_digests_req) {
+		.code = SPDM_GET_DIGESTS,
+	};
+
+	rsp = spdm_state->transcript_end += sizeof(*req);
+
+	/*
+	 * Assume all 8 slots are populated.  We know the hash length (and thus
+	 * the response size) because the responder only returns digests for
+	 * the hash algorithm selected during the NEGOTIATE_ALGORITHMS exchange
+	 * (SPDM 1.1.2 margin no 206).
+	 */
+	rsp_sz = sizeof(*rsp) + SPDM_SLOTS * spdm_state->hash_len;
+
+	rc = spdm_exchange(spdm_state, req, sizeof(*req), rsp, rsp_sz);
+	if (rc < 0)
+		return rc;
+
+	length = rc;
+	if (length < sizeof(*rsp) ||
+	    length < sizeof(*rsp) + hweight8(rsp->param2) *
+				    spdm_state->hash_len) {
+		dev_err(spdm_state->dev, "Truncated digests response\n");
+		return -EIO;
+	}
+
+	spdm_state->transcript_end += sizeof(*rsp) + hweight8(rsp->param2) *
+						     spdm_state->hash_len;
+
+	deprovisioned_slots = spdm_state->provisioned_slots & ~rsp->param2;
+	for_each_set_bit(slot, &deprovisioned_slots, SPDM_SLOTS) {
+		kvfree(spdm_state->slot[slot]);
+		spdm_state->slot_sz[slot] = 0;
+		spdm_state->slot[slot] = NULL;
+	}
+
+	/*
+	 * Authentication-capable endpoints must carry at least 1 cert chain
+	 * (SPDM 1.0.0 section 4.9.2.1).
+	 */
+	spdm_state->provisioned_slots = rsp->param2;
+	if (!spdm_state->provisioned_slots) {
+		dev_err(spdm_state->dev, "No certificates provisioned\n");
+		return -EPROTO;
+	}
+
+	return 0;
+}
+
+static int spdm_get_certificate(struct spdm_state *spdm_state, u8 slot)
+{
+	struct spdm_cert_chain *certs __free(kvfree) = NULL;
+	struct spdm_get_certificate_rsp *rsp __free(kvfree);
+	struct spdm_get_certificate_req req = {
+		.code = SPDM_GET_CERTIFICATE,
+		.param1 = slot,
+	};
+	size_t rsp_sz, total_length, header_length;
+	u16 remainder_length = 0xffff;
+	u16 portion_length;
+	u16 offset = 0;
+	int rc, length;
+
+	/*
+	 * It is legal for the responder to send more bytes than requested.
+	 * (Note the "should" in SPDM 1.0.0 table 19.)  If we allocate a
+	 * too small buffer, we can't calculate the hash over the (truncated)
+	 * response.  Only choice is thus to allocate the maximum possible 64k.
+	 */
+	rsp_sz = min_t(u32, sizeof(*rsp) + 0xffff, spdm_state->transport_sz);
+	rsp = kvmalloc(rsp_sz, GFP_KERNEL);
+	if (!rsp)
+		return -ENOMEM;
+
+	do {
+		/*
+		 * If transport_sz is sufficiently large, first request will be
+		 * for offset 0 and length 0xffff, which means entire cert
+		 * chain (SPDM 1.0.0 table 18).
+		 */
+		req.offset = cpu_to_le16(offset);
+		req.length = cpu_to_le16(min_t(size_t, remainder_length,
+					       rsp_sz - sizeof(*rsp)));
+
+		rc = spdm_exchange(spdm_state, &req, sizeof(req), rsp, rsp_sz);
+		if (rc < 0)
+			return rc;
+
+		length = rc;
+		if (length < sizeof(*rsp) ||
+		    length < sizeof(*rsp) + le16_to_cpu(rsp->portion_length)) {
+			dev_err(spdm_state->dev,
+				"Truncated certificate response\n");
+			return -EIO;
+		}
+
+		portion_length = le16_to_cpu(rsp->portion_length);
+		remainder_length = le16_to_cpu(rsp->remainder_length);
+
+		rc = spdm_append_transcript(spdm_state, &req, sizeof(req));
+		if (rc)
+			return rc;
+
+		rc = spdm_append_transcript(spdm_state, rsp,
+					    sizeof(*rsp) + portion_length);
+		if (rc)
+			return rc;
+
+		/*
+		 * On first response we learn total length of cert chain.
+		 * Should portion_length + remainder_length exceed 0xffff,
+		 * the min() ensures that the malformed check triggers below.
+		 */
+		if (!certs) {
+			total_length = min(portion_length + remainder_length,
+					   0xffff);
+			certs = kvmalloc(total_length, GFP_KERNEL);
+			if (!certs)
+				return -ENOMEM;
+		}
+
+		if (!portion_length ||
+		    (rsp->param1 & 0xf) != slot ||
+		    offset + portion_length + remainder_length != total_length)
+		{
+			dev_err(spdm_state->dev,
+				"Malformed certificate response\n");
+			return -EPROTO;
+		}
+
+		memcpy((u8 *)certs + offset, rsp->cert_chain, portion_length);
+		offset += portion_length;
+	} while (remainder_length > 0);
+
+	header_length = sizeof(struct spdm_cert_chain) + spdm_state->hash_len;
+
+	if (total_length < header_length ||
+	    total_length != le16_to_cpu(certs->length)) {
+		dev_err(spdm_state->dev,
+			"Malformed certificate chain in slot %u\n", slot);
+		return -EPROTO;
+	}
+
+	kvfree(spdm_state->slot[slot]);
+	spdm_state->slot_sz[slot] = total_length;
+	spdm_state->slot[slot] = no_free_ptr(certs);
+
+	return 0;
+}
+
+static int spdm_validate_cert_chain(struct spdm_state *spdm_state, u8 slot)
+{
+	struct x509_certificate *cert __free(x509_free_certificate) = NULL;
+	struct x509_certificate *prev __free(x509_free_certificate) = NULL;
+	size_t header_length, total_length;
+	bool is_leaf_cert;
+	size_t offset = 0;
+	struct key *key;
+	int rc, length;
+	u8 *certs;
+
+	header_length = sizeof(struct spdm_cert_chain) + spdm_state->hash_len;
+	total_length = spdm_state->slot_sz[slot] - header_length;
+	certs = (u8 *)spdm_state->slot[slot] + header_length;
+
+	do {
+		rc = x509_get_certificate_length(certs + offset,
+						 total_length - offset);
+		if (rc < 0) {
+			dev_err(spdm_state->dev, "Invalid certificate length "
+				"at slot %u offset %zu\n", slot, offset);
+			return rc;
+		}
+
+		length = rc;
+		is_leaf_cert = offset + length == total_length;
+
+		cert = x509_cert_parse(certs + offset, length);
+		if (IS_ERR(cert)) {
+			dev_err(spdm_state->dev, "Certificate parse error %pe "
+				"at slot %u offset %zu\n", cert, slot, offset);
+			return PTR_ERR(cert);
+		}
+		if (cert->unsupported_sig) {
+			dev_err(spdm_state->dev, "Unsupported signature "
+				"at slot %u offset %zu\n", slot, offset);
+			return -EKEYREJECTED;
+		}
+		if (cert->blacklisted)
+			return -EKEYREJECTED;
+
+		/*
+		 * Basic Constraints CA value shall be false for leaf cert,
+		 * true for intermediate and root certs (SPDM 1.3.0 table 42).
+		 * Key Usage bit for digital signature shall be set, except
+		 * for GenericCert in slot > 0 (SPDM 1.3.0 margin no 354).
+		 * KeyCertSign bit must be 0 for non-CA (RFC 5280 sec 4.2.1.9).
+		 */
+		if ((is_leaf_cert ==
+		     test_bit(KEY_EFLAG_CA, &cert->pub->key_eflags)) ||
+		    (is_leaf_cert && slot == 0 &&
+		     !test_bit(KEY_EFLAG_DIGITALSIG, &cert->pub->key_eflags)) ||
+		    (is_leaf_cert &&
+		     test_bit(KEY_EFLAG_KEYCERTSIGN, &cert->pub->key_eflags))) {
+			dev_err(spdm_state->dev, "Malformed certificate "
+				"at slot %u offset %zu\n", slot, offset);
+			return -EKEYREJECTED;
+		}
+
+		if (!prev) {
+			/* First cert in chain, check against root_keyring */
+			key = find_asymmetric_key(spdm_state->root_keyring,
+						  cert->sig->auth_ids[0],
+						  cert->sig->auth_ids[1],
+						  cert->sig->auth_ids[2],
+						  false);
+			if (IS_ERR(key)) {
+				dev_info(spdm_state->dev, "Root certificate "
+					 "of slot %u not found in %s "
+					 "keyring: %s\n", slot,
+					 spdm_state->root_keyring->description,
+					 cert->issuer);
+				return PTR_ERR(key);
+			}
+
+			rc = verify_signature(key, cert->sig);
+			key_put(key);
+		} else {
+			/* Subsequent cert in chain, check against previous */
+			rc = public_key_verify_signature(prev->pub, cert->sig);
+		}
+
+		if (rc) {
+			dev_err(spdm_state->dev, "Signature validation error "
+				"%d at slot %u offset %zu\n", rc, slot, offset);
+			return rc;
+		}
+
+		x509_free_certificate(prev);
+		prev = cert;
+		cert = ERR_PTR(-ENOKEY);
+
+		offset += length;
+	} while (offset < total_length);
+
+	/* Steal pub pointer ahead of x509_free_certificate() */
+	spdm_state->leaf_key = prev->pub;
+	prev->pub = NULL;
+
+	return 0;
+}
+
+/**
+ * spdm_challenge_rsp_sz() - Calculate CHALLENGE_AUTH response size
+ *
+ * @spdm_state: SPDM session state
+ * @rsp: CHALLENGE_AUTH response (optional)
+ *
+ * A CHALLENGE_AUTH response contains multiple variable-length fields
+ * as well as optional fields.  This helper eases calculating its size.
+ *
+ * If @rsp is %NULL, assume the maximum OpaqueDataLength of 1024 bytes
+ * (SPDM 1.0.0 table 21).  Otherwise read OpaqueDataLength from @rsp.
+ * OpaqueDataLength can only be > 0 for SPDM 1.0 and 1.1, as they lack
+ * the OtherParamsSupport field in the NEGOTIATE_ALGORITHMS request.
+ * For SPDM 1.2+, we do not offer any Opaque Data Formats in that field,
+ * which forces OpaqueDataLength to 0 (SPDM 1.2.0 margin no 261).
+ */
+static size_t spdm_challenge_rsp_sz(struct spdm_state *spdm_state,
+				    struct spdm_challenge_rsp *rsp)
+{
+	size_t  size  = sizeof(*rsp)		/* Header */
+		      + spdm_state->hash_len	/* CertChainHash */
+		      + SPDM_NONCE_SZ;		/* Nonce */
+
+	if (rsp)
+		/* May be unaligned if hash algorithm has odd length */
+		size += get_unaligned_le16((u8 *)rsp + size);
+	else
+		size += SPDM_MAX_OPAQUE_DATA;	/* OpaqueData */
+
+	size += 2;				/* OpaqueDataLength */
+
+	if (spdm_state->version >= 0x13)
+		size += 8;			/* RequesterContext */
+
+	return  size  + spdm_state->sig_len;	/* Signature */
+}
+
+static int spdm_challenge(struct spdm_state *spdm_state, u8 slot)
+{
+	struct spdm_challenge_rsp *rsp __free(kfree);
+	struct spdm_challenge_req req = {
+		.code = SPDM_CHALLENGE,
+		.param1 = slot,
+		.param2 = 0, /* No measurement summary hash */
+	};
+	size_t req_sz, rsp_sz, rsp_sz_max;
+	int rc, length;
+
+	get_random_bytes(&req.nonce, sizeof(req.nonce));
+
+	if (spdm_state->version <= 0x12)
+		req_sz = offsetofend(typeof(req), nonce);
+	else
+		req_sz = sizeof(req);
+
+	rsp_sz_max = spdm_challenge_rsp_sz(spdm_state, NULL);
+	rsp = kzalloc(rsp_sz_max, GFP_KERNEL);
+	if (!rsp)
+		return -ENOMEM;
+
+	rc = spdm_exchange(spdm_state, &req, req_sz, rsp, rsp_sz_max);
+	if (rc < 0)
+		return rc;
+
+	length = rc;
+	rsp_sz = spdm_challenge_rsp_sz(spdm_state, rsp);
+	if (length < rsp_sz) {
+		dev_err(spdm_state->dev, "Truncated challenge_auth response\n");
+		return -EIO;
+	}
+
+	rc = spdm_append_transcript(spdm_state, &req, req_sz);
+	if (rc)
+		return rc;
+
+	rc = spdm_append_transcript(spdm_state, rsp, rsp_sz);
+	if (rc)
+		return rc;
+
+	/* Verify signature at end of transcript against leaf key */
+	rc = spdm_verify_signature(spdm_state, spdm_context);
+	if (rc)
+		dev_err(spdm_state->dev,
+			"Cannot verify challenge_auth signature: %d\n", rc);
+	else
+		dev_info(spdm_state->dev,
+			 "Authenticated with certificate slot %u\n", slot);
+
+	return rc;
+}
+
+/**
+ * spdm_authenticate() - Authenticate device
+ *
+ * @spdm_state: SPDM session state
+ *
+ * Authenticate a device through a sequence of GET_VERSION, GET_CAPABILITIES,
+ * NEGOTIATE_ALGORITHMS, GET_DIGESTS, GET_CERTIFICATE and CHALLENGE exchanges.
+ *
+ * Perform internal locking to serialize multiple concurrent invocations.
+ * Can be called repeatedly for reauthentication.
+ *
+ * Return 0 on success or a negative errno.  In particular, -EPROTONOSUPPORT
+ * indicates authentication is not supported by the device.
+ */
+int spdm_authenticate(struct spdm_state *spdm_state)
+{
+	u8 slot;
+	int rc;
+
+	mutex_lock(&spdm_state->lock);
+	spdm_reset(spdm_state);
+
+	rc = spdm_alloc_transcript(spdm_state);
+	if (rc)
+		goto unlock;
+
+	rc = spdm_get_version(spdm_state);
+	if (rc)
+		goto unlock;
+
+	rc = spdm_get_capabilities(spdm_state);
+	if (rc)
+		goto unlock;
+
+	rc = spdm_negotiate_algs(spdm_state);
+	if (rc)
+		goto unlock;
+
+	rc = spdm_get_digests(spdm_state);
+	if (rc)
+		goto unlock;
+
+	for_each_set_bit(slot, &spdm_state->provisioned_slots, SPDM_SLOTS) {
+		rc = spdm_get_certificate(spdm_state, slot);
+		if (rc)
+			goto unlock;
+	}
+
+	for_each_set_bit(slot, &spdm_state->provisioned_slots, SPDM_SLOTS) {
+		rc = spdm_validate_cert_chain(spdm_state, slot);
+		if (rc == 0)
+			break;
+	}
+	if (rc)
+		goto unlock;
+
+	rc = spdm_challenge(spdm_state, slot);
+
+unlock:
+	if (rc)
+		spdm_reset(spdm_state);
+	spdm_state->authenticated = !rc;
+	spdm_free_transcript(spdm_state);
+	mutex_unlock(&spdm_state->lock);
+	return rc;
+}
+EXPORT_SYMBOL_GPL(spdm_authenticate);
diff --git a/lib/spdm/spdm.h b/lib/spdm/spdm.h
new file mode 100644
index 000000000000..3a104959ad53
--- /dev/null
+++ b/lib/spdm/spdm.h
@@ -0,0 +1,520 @@
+/* SPDX-License-Identifier: GPL-2.0 */
+/*
+ * DMTF Security Protocol and Data Model (SPDM)
+ * https://www.dmtf.org/dsp/DSP0274
+ *
+ * Copyright (C) 2021-22 Huawei
+ *     Jonathan Cameron <Jonathan.Cameron@huawei.com>
+ *
+ * Copyright (C) 2022-24 Intel Corporation
+ */
+
+#ifndef _LIB_SPDM_H_
+#define _LIB_SPDM_H_
+
+#undef  DEFAULT_SYMBOL_NAMESPACE
+#define DEFAULT_SYMBOL_NAMESPACE SPDM
+
+#define dev_fmt(fmt) "SPDM: " fmt
+
+#include <linux/bitfield.h>
+#include <linux/mutex.h>
+#include <linux/spdm.h>
+
+/* SPDM versions supported by this implementation */
+#define SPDM_MIN_VER 0x10
+#define SPDM_MAX_VER 0x13
+
+/* SPDM capabilities (SPDM 1.1.0 margin no 177, 178) */
+#define SPDM_CACHE_CAP			BIT(0)		/* 1.0 resp only */
+#define SPDM_CERT_CAP			BIT(1)		/* 1.0 */
+#define SPDM_CHAL_CAP			BIT(2)		/* 1.0 */
+#define SPDM_MEAS_CAP_MASK		GENMASK(4, 3)	/* 1.0 resp only */
+#define   SPDM_MEAS_CAP_NO		0		/* 1.0 resp only */
+#define   SPDM_MEAS_CAP_MEAS		1		/* 1.0 resp only */
+#define   SPDM_MEAS_CAP_MEAS_SIG	2		/* 1.0 resp only */
+#define SPDM_MEAS_FRESH_CAP		BIT(5)		/* 1.0 resp only */
+#define SPDM_ENCRYPT_CAP		BIT(6)		/* 1.1 */
+#define SPDM_MAC_CAP			BIT(7)		/* 1.1 */
+#define SPDM_MUT_AUTH_CAP		BIT(8)		/* 1.1 */
+#define SPDM_KEY_EX_CAP			BIT(9)		/* 1.1 */
+#define SPDM_PSK_CAP_MASK		GENMASK(11, 10)	/* 1.1 */
+#define   SPDM_PSK_CAP_NO		0		/* 1.1 */
+#define   SPDM_PSK_CAP_PSK		1		/* 1.1 */
+#define   SPDM_PSK_CAP_PSK_CTX		2		/* 1.1 resp only */
+#define SPDM_ENCAP_CAP			BIT(12)		/* 1.1 */
+#define SPDM_HBEAT_CAP			BIT(13)		/* 1.1 */
+#define SPDM_KEY_UPD_CAP		BIT(14)		/* 1.1 */
+#define SPDM_HANDSHAKE_ITC_CAP		BIT(15)		/* 1.1 */
+#define SPDM_PUB_KEY_ID_CAP		BIT(16)		/* 1.1 */
+#define SPDM_CHUNK_CAP			BIT(17)		/* 1.2 */
+#define SPDM_ALIAS_CERT_CAP		BIT(18)		/* 1.2 resp only */
+#define SPDM_SET_CERT_CAP		BIT(19)		/* 1.2 resp only */
+#define SPDM_CSR_CAP			BIT(20)		/* 1.2 resp only */
+#define SPDM_CERT_INST_RESET_CAP	BIT(21)		/* 1.2 resp only */
+#define SPDM_EP_INFO_CAP_MASK		GENMASK(23, 22) /* 1.3 */
+#define   SPDM_EP_INFO_CAP_NO		0		/* 1.3 */
+#define   SPDM_EP_INFO_CAP_RSP		1		/* 1.3 */
+#define   SPDM_EP_INFO_CAP_RSP_SIG	2		/* 1.3 */
+#define SPDM_MEL_CAP			BIT(24)		/* 1.3 resp only */
+#define SPDM_EVENT_CAP			BIT(25)		/* 1.3 */
+#define SPDM_MULTI_KEY_CAP_MASK		GENMASK(27, 26)	/* 1.3 */
+#define   SPDM_MULTI_KEY_CAP_NO		0		/* 1.3 */
+#define   SPDM_MULTI_KEY_CAP_ONLY	1		/* 1.3 */
+#define   SPDM_MULTI_KEY_CAP_SEL	2		/* 1.3 */
+#define SPDM_GET_KEY_PAIR_INFO_CAP	BIT(28)		/* 1.3 resp only */
+#define SPDM_SET_KEY_PAIR_INFO_CAP	BIT(29)		/* 1.3 resp only */
+
+/* SPDM capabilities supported by this implementation */
+#define SPDM_REQ_CAPS			(SPDM_CERT_CAP | SPDM_CHAL_CAP)
+
+/* SPDM capabilities required from responders */
+#define SPDM_RSP_MIN_CAPS		(SPDM_CERT_CAP | SPDM_CHAL_CAP)
+
+/*
+ * SPDM cryptographic timeout of this implementation:
+ * Assume calculations may take up to 1 sec on a busy machine, which equals
+ * roughly 1 << 20.  That's within the limits mandated for responders by CMA
+ * (1 << 23 usec, PCIe r6.2 sec 6.31.3) and DOE (1 sec, PCIe r6.2 sec 6.30.2).
+ * Used in GET_CAPABILITIES exchange.
+ */
+#define SPDM_CTEXPONENT			20
+
+/* SPDM asymmetric key signature algorithms (SPDM 1.0.0 table 13) */
+#define SPDM_ASYM_RSASSA_2048		BIT(0)		/* 1.0 */
+#define SPDM_ASYM_RSAPSS_2048		BIT(1)		/* 1.0 */
+#define SPDM_ASYM_RSASSA_3072		BIT(2)		/* 1.0 */
+#define SPDM_ASYM_RSAPSS_3072		BIT(3)		/* 1.0 */
+#define SPDM_ASYM_ECDSA_ECC_NIST_P256	BIT(4)		/* 1.0 */
+#define SPDM_ASYM_RSASSA_4096		BIT(5)		/* 1.0 */
+#define SPDM_ASYM_RSAPSS_4096		BIT(6)		/* 1.0 */
+#define SPDM_ASYM_ECDSA_ECC_NIST_P384	BIT(7)		/* 1.0 */
+#define SPDM_ASYM_ECDSA_ECC_NIST_P521	BIT(8)		/* 1.0 */
+#define SPDM_ASYM_SM2_ECC_SM2_P256	BIT(9)		/* 1.2 */
+#define SPDM_ASYM_EDDSA_ED25519		BIT(10)		/* 1.2 */
+#define SPDM_ASYM_EDDSA_ED448		BIT(11)		/* 1.2 */
+
+/* SPDM hash algorithms (SPDM 1.0.0 table 13) */
+#define SPDM_HASH_SHA_256		BIT(0)		/* 1.0 */
+#define SPDM_HASH_SHA_384		BIT(1)		/* 1.0 */
+#define SPDM_HASH_SHA_512		BIT(2)		/* 1.0 */
+#define SPDM_HASH_SHA3_256		BIT(3)		/* 1.0 */
+#define SPDM_HASH_SHA3_384		BIT(4)		/* 1.0 */
+#define SPDM_HASH_SHA3_512		BIT(5)		/* 1.0 */
+#define SPDM_HASH_SM3_256		BIT(6)		/* 1.2 */
+
+#if IS_ENABLED(CONFIG_CRYPTO_RSA)
+#define SPDM_ASYM_RSA			SPDM_ASYM_RSASSA_2048 |		\
+					SPDM_ASYM_RSASSA_3072 |		\
+					SPDM_ASYM_RSASSA_4096
+#else
+#define SPDM_ASYM_RSA			0
+#endif
+
+#if IS_ENABLED(CONFIG_CRYPTO_ECDSA)
+#define SPDM_ASYM_ECDSA			SPDM_ASYM_ECDSA_ECC_NIST_P256 |	\
+					SPDM_ASYM_ECDSA_ECC_NIST_P384 | \
+					SPDM_ASYM_ECDSA_ECC_NIST_P521
+#else
+#define SPDM_ASYM_ECDSA			0
+#endif
+
+#if IS_ENABLED(CONFIG_CRYPTO_SHA256)
+#define SPDM_HASH_SHA2_256		SPDM_HASH_SHA_256
+#else
+#define SPDM_HASH_SHA2_256		0
+#endif
+
+#if IS_ENABLED(CONFIG_CRYPTO_SHA512)
+#define SPDM_HASH_SHA2_384_512		SPDM_HASH_SHA_384 |		\
+					SPDM_HASH_SHA_512
+#else
+#define SPDM_HASH_SHA2_384_512		0
+#endif
+
+/* SPDM algorithms supported by this implementation */
+#define SPDM_ASYM_ALGOS		       (SPDM_ASYM_RSA |			\
+					SPDM_ASYM_ECDSA)
+
+#define SPDM_HASH_ALGOS		       (SPDM_HASH_SHA2_256 |		\
+					SPDM_HASH_SHA2_384_512)
+
+/*
+ * Common header shared by all messages.
+ * Note that the meaning of param1 and param2 is message dependent.
+ */
+struct spdm_header {
+	u8 version;
+	u8 code;  /* RequestResponseCode */
+	u8 param1;
+	u8 param2;
+} __packed;
+
+#define SPDM_REQ	 0x80
+#define SPDM_GET_VERSION 0x84
+
+struct spdm_get_version_req {
+	u8 version;
+	u8 code;
+	u8 param1;
+	u8 param2;
+} __packed;
+
+struct spdm_get_version_rsp {
+	u8 version;
+	u8 code;
+	u8 param1;
+	u8 param2;
+
+	u8 reserved;
+	u8 version_number_entry_count;
+	__le16 version_number_entries[] __counted_by(version_number_entry_count);
+} __packed;
+
+#define SPDM_GET_CAPABILITIES 0xe1
+#define SPDM_MIN_DATA_TRANSFER_SIZE 42 /* SPDM 1.2.0 margin no 226 */
+
+/*
+ * Newer SPDM versions insert fields at the end of messages (enlarging them)
+ * or use reserved space for new fields (leaving message size unchanged).
+ */
+struct spdm_get_capabilities_req {
+	u8 version;
+	u8 code;
+	u8 param1;
+	u8 param2;
+	/* End of SPDM 1.0 structure */
+
+	u8 reserved1;					/* 1.1 */
+	u8 ctexponent;					/* 1.1 */
+	u16 reserved2;					/* 1.1 */
+	__le32 flags;					/* 1.1 */
+	/* End of SPDM 1.1 structure */
+
+	__le32 data_transfer_size;			/* 1.2 */
+	__le32 max_spdm_msg_size;			/* 1.2 */
+} __packed;
+
+struct spdm_get_capabilities_rsp {
+	u8 version;
+	u8 code;
+	u8 param1;
+	u8 param2;
+
+	u8 reserved1;
+	u8 ctexponent;
+	u16 reserved2;
+	__le32 flags;
+	/* End of SPDM 1.0 structure */
+
+	__le32 data_transfer_size;			/* 1.2 */
+	__le32 max_spdm_msg_size;			/* 1.2 */
+	/* End of SPDM 1.2 structure */
+
+	/*
+	 * Additional optional fields at end of this structure:
+	 * - SupportedAlgorithms: variable size		 * 1.3 *
+	 */
+} __packed;
+
+#define SPDM_NEGOTIATE_ALGS 0xe3
+
+struct spdm_negotiate_algs_req {
+	u8 version;
+	u8 code;
+	u8 param1; /* Number of ReqAlgStruct entries at end */
+	u8 param2;
+
+	__le16 length;
+	u8 measurement_specification;
+	u8 other_params_support;			/* 1.2 */
+
+	__le32 base_asym_algo;
+	__le32 base_hash_algo;
+
+	u8 reserved1[12];
+	u8 ext_asym_count;
+	u8 ext_hash_count;
+	u8 reserved2;
+	u8 mel_specification;				/* 1.3 */
+
+	/*
+	 * Additional optional fields at end of this structure:
+	 * - ExtAsym: 4 bytes * ext_asym_count
+	 * - ExtHash: 4 bytes * ext_hash_count
+	 * - ReqAlgStruct: variable size * param1	 * 1.1 *
+	 */
+} __packed;
+
+struct spdm_negotiate_algs_rsp {
+	u8 version;
+	u8 code;
+	u8 param1; /* Number of RespAlgStruct entries at end */
+	u8 param2;
+
+	__le16 length;
+	u8 measurement_specification_sel;
+	u8 other_params_sel;				/* 1.2 */
+
+	__le32 measurement_hash_algo;
+	__le32 base_asym_sel;
+	__le32 base_hash_sel;
+
+	u8 reserved1[11];
+	u8 mel_specification_sel;			/* 1.3 */
+	u8 ext_asym_sel_count; /* Either 0 or 1 */
+	u8 ext_hash_sel_count; /* Either 0 or 1 */
+	u8 reserved2[2];
+
+	/*
+	 * Additional optional fields at end of this structure:
+	 * - ExtAsym: 4 bytes * ext_asym_count
+	 * - ExtHash: 4 bytes * ext_hash_count
+	 * - RespAlgStruct: variable size * param1	 * 1.1 *
+	 */
+} __packed;
+
+/* Maximum number of ReqAlgStructs sent by this implementation */
+#define SPDM_MAX_REQ_ALG_STRUCT 0
+
+struct spdm_req_alg_struct {
+	u8 alg_type;
+	u8 alg_count; /* 0x2K where K is number of alg_external entries */
+	__le16 alg_supported; /* Size is in alg_count[7:4], always 2 */
+	__le32 alg_external[];
+} __packed;
+
+#define SPDM_GET_DIGESTS 0x81
+
+struct spdm_get_digests_req {
+	u8 version;
+	u8 code;
+	u8 param1; /* Reserved */
+	u8 param2; /* Reserved */
+} __packed;
+
+struct spdm_get_digests_rsp {
+	u8 version;
+	u8 code;
+	u8 param1; /* SupportedSlotMask */		/* 1.3 */
+	u8 param2; /* ProvisionedSlotMask */
+	u8 digests[]; /* Hash of struct spdm_cert_chain for each slot */
+	/* End of SPDM 1.2 (and earlier) structure */
+
+	/*
+	 * Additional optional fields at end of this structure:
+	 * (omitted as long as we do not advertise MULTI_KEY_CAP)
+	 * - KeyPairID: 1 byte for each slot		 * 1.3 *
+	 * - CertificateInfo: 1 byte for each slot	 * 1.3 *
+	 * - KeyUsageMask: 2 bytes for each slot	 * 1.3 *
+	 */
+} __packed;
+
+#define SPDM_GET_CERTIFICATE 0x82
+#define SPDM_SLOTS 8 /* SPDM 1.0.0 section 4.9.2.1 */
+
+struct spdm_get_certificate_req {
+	u8 version;
+	u8 code;
+	u8 param1; /* Slot number 0..7 */
+	u8 param2; /* SlotSizeRequested */		/* 1.3 */
+	__le16 offset;
+	__le16 length;
+} __packed;
+
+struct spdm_get_certificate_rsp {
+	u8 version;
+	u8 code;
+	u8 param1; /* Slot number 0..7 */
+	u8 param2; /* CertificateInfo */		/* 1.3 */
+	__le16 portion_length;
+	__le16 remainder_length;
+	u8 cert_chain[]; /* PortionLength long */
+} __packed;
+
+struct spdm_cert_chain {
+	__le16 length;
+	u8 reserved[2];
+	/*
+	 * Additional fields at end of this structure:
+	 * - RootHash: Digest of Root Certificate
+	 * - Certificates: Chain of ASN.1 DER-encoded X.509 v3 certificates
+	 */
+} __packed;
+
+#define SPDM_CHALLENGE 0x83
+#define SPDM_NONCE_SZ 32 /* SPDM 1.0.0 table 20 */
+#define SPDM_PREFIX_SZ 64 /* SPDM 1.2.0 margin no 803 */
+#define SPDM_COMBINED_PREFIX_SZ 100 /* SPDM 1.2.0 margin no 806 */
+#define SPDM_MAX_OPAQUE_DATA 1024 /* SPDM 1.0.0 table 21 */
+
+struct spdm_challenge_req {
+	u8 version;
+	u8 code;
+	u8 param1; /* Slot number 0..7 */
+	u8 param2; /* MeasurementSummaryHash type */
+	u8 nonce[SPDM_NONCE_SZ];
+	/* End of SPDM 1.2 (and earlier) structure */
+
+	u8 context[8];					/* 1.3 */
+} __packed;
+
+struct spdm_challenge_rsp {
+	u8 version;
+	u8 code;
+	u8 param1; /* Slot number 0..7 */
+	u8 param2; /* Slot mask */
+	/*
+	 * Additional fields at end of this structure:
+	 * - CertChainHash: Hash of struct spdm_cert_chain for selected slot
+	 * - Nonce: 32 bytes long
+	 * - MeasurementSummaryHash: Optional hash of selected measurements
+	 * - OpaqueDataLength: 2 bytes long
+	 * - OpaqueData: Up to 1024 bytes long
+	 * - RequesterContext: 8 bytes long		 * 1.3 *
+	 *   (inserted, moves Signature field)
+	 * - Signature
+	 */
+} __packed;
+
+#define SPDM_ERROR 0x7f
+
+enum spdm_error_code {
+	SPDM_INVALID_REQUEST		= 0x01,		/* 1.0 */
+	SPDM_INVALID_SESSION		= 0x02,		/* 1.1 only */
+	SPDM_BUSY			= 0x03,		/* 1.0 */
+	SPDM_UNEXPECTED_REQUEST		= 0x04,		/* 1.0 */
+	SPDM_UNSPECIFIED		= 0x05,		/* 1.0 */
+	SPDM_DECRYPT_ERROR		= 0x06,		/* 1.1 */
+	SPDM_UNSUPPORTED_REQUEST	= 0x07,		/* 1.0 */
+	SPDM_REQUEST_IN_FLIGHT		= 0x08,		/* 1.1 */
+	SPDM_INVALID_RESPONSE_CODE	= 0x09,		/* 1.1 */
+	SPDM_SESSION_LIMIT_EXCEEDED	= 0x0a,		/* 1.1 */
+	SPDM_SESSION_REQUIRED		= 0x0b,		/* 1.2 */
+	SPDM_RESET_REQUIRED		= 0x0c,		/* 1.2 */
+	SPDM_RESPONSE_TOO_LARGE		= 0x0d,		/* 1.2 */
+	SPDM_REQUEST_TOO_LARGE		= 0x0e,		/* 1.2 */
+	SPDM_LARGE_RESPONSE		= 0x0f,		/* 1.2 */
+	SPDM_MESSAGE_LOST		= 0x10,		/* 1.2 */
+	SPDM_INVALID_POLICY		= 0x11,		/* 1.3 */
+	SPDM_VERSION_MISMATCH		= 0x41,		/* 1.0 */
+	SPDM_RESPONSE_NOT_READY		= 0x42,		/* 1.0 */
+	SPDM_REQUEST_RESYNCH		= 0x43,		/* 1.0 */
+	SPDM_OPERATION_FAILED		= 0x44,		/* 1.3 */
+	SPDM_NO_PENDING_REQUESTS	= 0x45,		/* 1.3 */
+	SPDM_VENDOR_DEFINED_ERROR	= 0xff,		/* 1.0 */
+};
+
+struct spdm_error_rsp {
+	u8 version;
+	u8 code;
+	enum spdm_error_code error_code:8;
+	u8 error_data;
+
+	u8 extended_error_data[];
+} __packed;
+
+/**
+ * struct spdm_state - SPDM session state
+ *
+ * @dev: Responder device.  Used for error reporting and passed to @transport.
+ * @lock: Serializes multiple concurrent spdm_authenticate() calls.
+ * @authenticated: Whether device was authenticated successfully.
+ * @dev: Responder device.  Used for error reporting and passed to @transport.
+ * @transport: Transport function to perform one message exchange.
+ * @transport_priv: Transport private data.
+ * @transport_sz: Maximum message size the transport is capable of (in bytes).
+ *	Used as DataTransferSize in GET_CAPABILITIES exchange.
+ * @version: Maximum common supported version of requester and responder.
+ *	Negotiated during GET_VERSION exchange.
+ * @rsp_caps: Cached capabilities of responder.
+ *	Received during GET_CAPABILITIES exchange.
+ * @base_asym_alg: Asymmetric key algorithm for signature verification of
+ *	CHALLENGE_AUTH messages.
+ *	Selected by responder during NEGOTIATE_ALGORITHMS exchange.
+ * @base_hash_alg: Hash algorithm for signature verification of
+ *	CHALLENGE_AUTH messages.
+ *	Selected by responder during NEGOTIATE_ALGORITHMS exchange.
+ * @provisioned_slots: Bitmask of responder's provisioned certificate slots.
+ *	Received during GET_DIGESTS exchange.
+ * @base_asym_enc: Human-readable name of @base_asym_alg's signature encoding.
+ *	Passed to crypto subsystem when calling verify_signature().
+ * @sig_len: Signature length of @base_asym_alg (in bytes).
+ *	S or SigLen in SPDM specification.
+ * @base_hash_alg_name: Human-readable name of @base_hash_alg.
+ *	Passed to crypto subsystem when calling crypto_alloc_shash() and
+ *	verify_signature().
+ * @shash: Synchronous hash handle for @base_hash_alg computation.
+ * @desc: Synchronous hash context for @base_hash_alg computation.
+ * @hash_len: Hash length of @base_hash_alg (in bytes).
+ *	H in SPDM specification.
+ * @slot: Certificate chain in each of the 8 slots.  NULL pointer if a slot is
+ *	not populated.  Prefixed by the 4 + H header per SPDM 1.0.0 table 15.
+ * @slot_sz: Certificate chain size (in bytes).
+ * @leaf_key: Public key portion of leaf certificate against which to check
+ *	responder's signatures.
+ * @root_keyring: Keyring against which to check the first certificate in
+ *	responder's certificate chain.
+ * @transcript: Concatenation of all SPDM messages exchanged during an
+ *	authentication sequence.  Used to verify the signature, as it is
+ *	computed over the hashed transcript.
+ * @transcript_end: Pointer into the @transcript buffer.  Marks the current
+ *	end of transcript.  If another message is transmitted, it is appended
+ *	at this position.
+ * @transcript_max: Allocation size of @transcript.  Multiple of PAGE_SIZE.
+ */
+struct spdm_state {
+	struct device *dev;
+	struct mutex lock;
+	unsigned int authenticated:1;
+
+	/* Transport */
+	spdm_transport *transport;
+	void *transport_priv;
+	u32 transport_sz;
+
+	/* Negotiated state */
+	u8 version;
+	u32 rsp_caps;
+	u32 base_asym_alg;
+	u32 base_hash_alg;
+	unsigned long provisioned_slots;
+
+	/* Signature algorithm */
+	const char *base_asym_enc;
+	size_t sig_len;
+
+	/* Hash algorithm */
+	const char *base_hash_alg_name;
+	struct crypto_shash *shash;
+	struct shash_desc *desc;
+	size_t hash_len;
+
+	/* Certificates */
+	struct spdm_cert_chain *slot[SPDM_SLOTS];
+	size_t slot_sz[SPDM_SLOTS];
+	struct public_key *leaf_key;
+	struct key *root_keyring;
+
+	/* Transcript */
+	void *transcript;
+	void *transcript_end;
+	size_t transcript_max;
+};
+
+ssize_t spdm_exchange(struct spdm_state *spdm_state,
+		      void *req, size_t req_sz, void *rsp, size_t rsp_sz);
+
+int spdm_alloc_transcript(struct spdm_state *spdm_state);
+void spdm_free_transcript(struct spdm_state *spdm_state);
+int spdm_append_transcript(struct spdm_state *spdm_state,
+			   const void *msg, size_t msg_sz);
+
+void spdm_create_combined_prefix(u8 version, const char *spdm_context,
+				 void *buf);
+int spdm_verify_signature(struct spdm_state *spdm_state,
+			  const char *spdm_context);
+
+void spdm_reset(struct spdm_state *spdm_state);
+
+#endif /* _LIB_SPDM_H_ */

---

## [9] Lukas Wunner — 2024-06-30
*Subject: [PATCH v2 08/18] PCI/CMA: Authenticate devices on enumeration*

From: Jonathan Cameron <Jonathan.Cameron@huawei.com>

Component Measurement and Authentication (CMA, PCIe r6.2 sec 6.31)
allows for measurement and authentication of PCIe devices.  It is
based on the Security Protocol and Data Model specification (SPDM,
https://www.dmtf.org/dsp/DSP0274).

CMA-SPDM in turn forms the basis for Integrity and Data Encryption
(IDE, PCIe r6.2 sec 6.33) because the key material used by IDE is
transmitted over a CMA-SPDM session.

As a first step, authenticate CMA-capable devices on enumeration.
A subsequent commit will expose the result in sysfs.

When allocating SPDM session state with spdm_create(), the maximum SPDM
message length needs to be passed.  Make the PCI_DOE_MAX_LENGTH macro
public and calculate the maximum payload length from it.

Credits:  Jonathan wrote a proof-of-concept of this CMA implementation.
Lukas reworked it for upstream.  Wilfred contributed fixes for issues
discovered during testing.

Signed-off-by: Jonathan Cameron <Jonathan.Cameron@huawei.com>
Co-developed-by: Wilfred Mallawa <wilfred.mallawa@wdc.com>
Signed-off-by: Wilfred Mallawa <wilfred.mallawa@wdc.com>
Co-developed-by: Lukas Wunner <lukas@wunner.de>
Signed-off-by: Lukas Wunner <lukas@wunner.de>
---
 MAINTAINERS             |   1 +
 drivers/pci/Kconfig     |  13 ++++++
 drivers/pci/Makefile    |   2 +
 drivers/pci/cma.c       | 100 ++++++++++++++++++++++++++++++++++++++++
 drivers/pci/doe.c       |   3 --
 drivers/pci/pci.h       |   8 ++++
 drivers/pci/probe.c     |   1 +
 drivers/pci/remove.c    |   1 +
 include/linux/pci-doe.h |   4 ++
 include/linux/pci.h     |   4 ++
 10 files changed, 134 insertions(+), 3 deletions(-)
 create mode 100644 drivers/pci/cma.c

diff --git a/MAINTAINERS b/MAINTAINERS
index dbe16eea8818..9aad3350da16 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -20153,6 +20153,7 @@ L:	linux-cxl@vger.kernel.org
 L:	linux-pci@vger.kernel.org
 S:	Maintained
 T:	git git://git.kernel.org/pub/scm/linux/kernel/git/devsec/spdm.git
+F:	drivers/pci/cma*
 F:	include/linux/spdm.h
 F:	lib/spdm/
 
diff --git a/drivers/pci/Kconfig b/drivers/pci/Kconfig
index d35001589d88..f656211d707a 100644
--- a/drivers/pci/Kconfig
+++ b/drivers/pci/Kconfig
@@ -121,6 +121,19 @@ config XEN_PCIDEV_FRONTEND
 config PCI_ATS
 	bool
 
+config PCI_CMA
+	bool "Component Measurement and Authentication (CMA-SPDM)"
+	select CRYPTO_ECDSA
+	select CRYPTO_RSA
+	select CRYPTO_SHA256
+	select CRYPTO_SHA512
+	select PCI_DOE
+	select SPDM
+	help
+	  Authenticate devices on enumeration per PCIe r6.2 sec 6.31.
+	  A PCI DOE mailbox is used as transport for DMTF SPDM based
+	  authentication, measurement and secure channel establishment.
+
 config PCI_DOE
 	bool
 
diff --git a/drivers/pci/Makefile b/drivers/pci/Makefile
index 175302036890..6bcfeb698961 100644
--- a/drivers/pci/Makefile
+++ b/drivers/pci/Makefile
@@ -35,6 +35,8 @@ obj-$(CONFIG_VGA_ARB)		+= vgaarb.o
 obj-$(CONFIG_PCI_DOE)		+= doe.o
 obj-$(CONFIG_PCI_DYNAMIC_OF_NODES) += of_property.o
 
+obj-$(CONFIG_PCI_CMA)		+= cma.o
+
 # Endpoint library must be initialized before its users
 obj-$(CONFIG_PCI_ENDPOINT)	+= endpoint/
 
diff --git a/drivers/pci/cma.c b/drivers/pci/cma.c
new file mode 100644
index 000000000000..275338b95640
--- /dev/null
+++ b/drivers/pci/cma.c
@@ -0,0 +1,100 @@
+// SPDX-License-Identifier: GPL-2.0
+/*
+ * Component Measurement and Authentication (CMA-SPDM, PCIe r6.2 sec 6.31)
+ *
+ * Copyright (C) 2021 Huawei
+ *     Jonathan Cameron <Jonathan.Cameron@huawei.com>
+ *
+ * Copyright (C) 2022-24 Intel Corporation
+ */
+
+#define dev_fmt(fmt) "CMA: " fmt
+
+#include <linux/pci.h>
+#include <linux/pci-doe.h>
+#include <linux/pm_runtime.h>
+#include <linux/spdm.h>
+
+#include "pci.h"
+
+/* Keyring that userspace can poke certs into */
+static struct key *pci_cma_keyring;
+
+#define PCI_DOE_FEATURE_CMA 1
+
+static ssize_t pci_doe_transport(void *priv, struct device *dev,
+				 const void *request, size_t request_sz,
+				 void *response, size_t response_sz)
+{
+	struct pci_doe_mb *doe = priv;
+	ssize_t rc;
+
+	/*
+	 * CMA-SPDM operation in non-D0 states is optional (PCIe r6.2
+	 * sec 6.31.3).  The spec does not define a way to determine
+	 * if it's supported, so resume to D0 unconditionally.
+	 */
+	rc = pm_runtime_resume_and_get(dev);
+	if (rc)
+		return rc;
+
+	rc = pci_doe(doe, PCI_VENDOR_ID_PCI_SIG, PCI_DOE_FEATURE_CMA,
+		     request, request_sz, response, response_sz);
+
+	pm_runtime_put(dev);
+
+	return rc;
+}
+
+void pci_cma_init(struct pci_dev *pdev)
+{
+	struct pci_doe_mb *doe;
+
+	if (IS_ERR(pci_cma_keyring))
+		return;
+
+	if (!pci_is_pcie(pdev))
+		return;
+
+	doe = pci_find_doe_mailbox(pdev, PCI_VENDOR_ID_PCI_SIG,
+				   PCI_DOE_FEATURE_CMA);
+	if (!doe)
+		return;
+
+	pdev->spdm_state = spdm_create(&pdev->dev, pci_doe_transport, doe,
+				       PCI_DOE_MAX_PAYLOAD, pci_cma_keyring);
+	if (!pdev->spdm_state)
+		return;
+
+	/*
+	 * Keep spdm_state allocated even if initial authentication fails
+	 * to allow for provisioning of certificates and reauthentication.
+	 */
+	spdm_authenticate(pdev->spdm_state);
+}
+
+void pci_cma_destroy(struct pci_dev *pdev)
+{
+	if (!pdev->spdm_state)
+		return;
+
+	spdm_destroy(pdev->spdm_state);
+}
+
+__init static int pci_cma_keyring_init(void)
+{
+	pci_cma_keyring = keyring_alloc(".cma", KUIDT_INIT(0), KGIDT_INIT(0),
+					current_cred(),
+					(KEY_POS_ALL & ~KEY_POS_SETATTR) |
+					KEY_USR_VIEW | KEY_USR_READ |
+					KEY_USR_WRITE | KEY_USR_SEARCH,
+					KEY_ALLOC_NOT_IN_QUOTA |
+					KEY_ALLOC_SET_KEEP, NULL, NULL);
+	if (IS_ERR(pci_cma_keyring)) {
+		pr_err("PCI: Could not allocate .cma keyring\n");
+		return PTR_ERR(pci_cma_keyring);
+	}
+
+	return 0;
+}
+arch_initcall(pci_cma_keyring_init);
diff --git a/drivers/pci/doe.c b/drivers/pci/doe.c
index 652d63df9d22..34bb8f232799 100644
--- a/drivers/pci/doe.c
+++ b/drivers/pci/doe.c
@@ -31,9 +31,6 @@
 #define PCI_DOE_FLAG_CANCEL	0
 #define PCI_DOE_FLAG_DEAD	1
 
-/* Max data object length is 2^18 dwords */
-#define PCI_DOE_MAX_LENGTH	(1 << 18)
-
 /**
  * struct pci_doe_mb - State for a single DOE mailbox
  *
diff --git a/drivers/pci/pci.h b/drivers/pci/pci.h
index fd44565c4756..fc90845caf83 100644
--- a/drivers/pci/pci.h
+++ b/drivers/pci/pci.h
@@ -333,6 +333,14 @@ static inline void pci_doe_destroy(struct pci_dev *pdev) { }
 static inline void pci_doe_disconnected(struct pci_dev *pdev) { }
 #endif
 
+#ifdef CONFIG_PCI_CMA
+void pci_cma_init(struct pci_dev *pdev);
+void pci_cma_destroy(struct pci_dev *pdev);
+#else
+static inline void pci_cma_init(struct pci_dev *pdev) { }
+static inline void pci_cma_destroy(struct pci_dev *pdev) { }
+#endif
+
 /**
  * pci_dev_set_io_state - Set the new error state if possible.
  *
diff --git a/drivers/pci/probe.c b/drivers/pci/probe.c
index 8e696e547565..5297f9a08ca2 100644
--- a/drivers/pci/probe.c
+++ b/drivers/pci/probe.c
@@ -2484,6 +2484,7 @@ static void pci_init_capabilities(struct pci_dev *dev)
 	pci_dpc_init(dev);		/* Downstream Port Containment */
 	pci_rcec_init(dev);		/* Root Complex Event Collector */
 	pci_doe_init(dev);		/* Data Object Exchange */
+	pci_cma_init(dev);		/* Component Measurement & Auth */
 
 	pcie_report_downtraining(dev);
 	pci_init_reset_methods(dev);
diff --git a/drivers/pci/remove.c b/drivers/pci/remove.c
index d749ea8250d6..f009ac578997 100644
--- a/drivers/pci/remove.c
+++ b/drivers/pci/remove.c
@@ -39,6 +39,7 @@ static void pci_destroy_dev(struct pci_dev *dev)
 	list_del(&dev->bus_list);
 	up_write(&pci_bus_sem);
 
+	pci_cma_destroy(dev);
 	pci_doe_destroy(dev);
 	pcie_aspm_exit_link_state(dev);
 	pci_bridge_d3_update(dev);
diff --git a/include/linux/pci-doe.h b/include/linux/pci-doe.h
index 1f14aed4354b..0d3d7656c456 100644
--- a/include/linux/pci-doe.h
+++ b/include/linux/pci-doe.h
@@ -15,6 +15,10 @@
 
 struct pci_doe_mb;
 
+/* Max data object length is 2^18 dwords (including 2 dwords for header) */
+#define PCI_DOE_MAX_LENGTH	(1 << 18)
+#define PCI_DOE_MAX_PAYLOAD	((PCI_DOE_MAX_LENGTH - 2) * sizeof(u32))
+
 struct pci_doe_mb *pci_find_doe_mailbox(struct pci_dev *pdev, u16 vendor,
 					u8 type);
 
diff --git a/include/linux/pci.h b/include/linux/pci.h
index fb004fd4e889..cb2a0be57196 100644
--- a/include/linux/pci.h
+++ b/include/linux/pci.h
@@ -39,6 +39,7 @@
 #include <linux/io.h>
 #include <linux/resource_ext.h>
 #include <linux/msi_api.h>
+#include <linux/spdm.h>
 #include <uapi/linux/pci.h>
 
 #include <linux/pci_ids.h>
@@ -517,6 +518,9 @@ struct pci_dev {
 #endif
 #ifdef CONFIG_PCI_DOE
 	struct xarray	doe_mbs;	/* Data Object Exchange mailboxes */
+#endif
+#ifdef CONFIG_PCI_CMA
+	struct spdm_state *spdm_state;	/* Security Protocol and Data Model */
 #endif
 	u16		acs_cap;	/* ACS Capability offset */
 	phys_addr_t	rom;		/* Physical address if not from BAR */

---

## [10] Lukas Wunner — 2024-06-30
*Subject: [PATCH v2 09/18] PCI/CMA: Validate Subject Alternative Name in
 certificates*

PCIe r6.1 sec 6.31.3 stipulates requirements for Leaf Certificates
presented by devices, in particular the presence of a Subject Alternative
Name which encodes the Vendor ID, Device ID, Device Serial Number, etc.

This prevents a mismatch between the device identity in Config Space and
the certificate.  A device cannot misappropriate a certificate from a
different device without also spoofing Config Space.  As a corollary,
it cannot dupe an arbitrary driver into binding to it.  Only drivers
which bind to the device identity in the Subject Alternative Name work
(PCIe r6.1 sec 6.31 "Implementation Note: Overview of Threat Model").

The Subject Alternative Name is signed, hence constitutes a signed copy
of a Config Space portion.  It's the same concept as web certificates
which contain a set of domain names in the Subject Alternative Name for
identity verification.

Parse the Subject Alternative Name using a small ASN.1 module and
validate its contents.  The theory of operation is explained in a
comment at the top of the newly inserted code.

This functionality is introduced in a separate commit on top of basic
CMA-SPDM support to split the code into digestible, reviewable chunks.

The CMA OID added here is taken from the official OID Repository
(it's not documented in the PCIe Base Spec):
https://oid-rep.orange-labs.fr/get/2.23.147

Side notes:

* PCIe r6.2 removes the spec language on the Subject Alternative Name.
  It still "requires the leaf certificate to include the information
  typically used by system software for device driver binding", but no
  longer specifies how that information is encoded into the certificate.

  According to the editor of the PCIe Base Spec and the author of the
  CMA 1.1 ECN (which caused this change), FPGA cards which mutate their
  device identity at runtime (due to a firmware update) were thought as
  unable to satisfy the previous spec language.  The Protocol Working
  Group could not agree on a better solution and therefore dropped the
  spec language entirely.  They acknowledge that the requirement is now
  under-spec'd.  Because products already exist which adhere to the
  Subject Alternative Name requirement per PCIe r6.1 sec 6.31.3, they
  recommended to "push through" and use it as the de facto standard.

  The FPGA concerns are easily overcome by reauthenticating the device
  after a firmware update, either via sysfs or pci_cma_reauthenticate()
  (added by a subsequent commit).

* PCIe r6.1 sec 6.31.3 strongly recommends to verify that "the
  information provided in the Subject Alternative Name entry is signed
  by the vendor indicated by the Vendor ID."  In other words, the root
  certificate on pci_cma_keyring which signs the device's certificate
  chain must have been created for a particular Vendor ID.

  Unfortunately the spec neglects to define how the Vendor ID shall be
  encoded into the root certificate.  So the recommendation cannot be
  implemented at this point and it is thus possible that a vendor signs
  device certificates of a different vendor.

* Instead of a Subject Alternative Name, Leaf Certificates may include
  "a Reference Integrity Manifest, e.g., see Trusted Computing Group" or
  "a pointer to a location where such a Reference Integrity Manifest can
  be obtained" (PCIe r6.1 sec 6.31.3).

  A Reference Integrity Manifest contains "golden" measurements which
  can be compared to actual measurements retrieved from a device.
  It serves a different purpose than the Subject Alternative Name,
  hence it is unclear why the spec says only either of them is necessary.
  It is also unclear how a Reference Integrity Manifest shall be encoded
  into a certificate.

  Hence ignore the Reference Integrity Manifest requirement.

Signed-off-by: Lukas Wunner <lukas@wunner.de>
Reviewed-by: Jonathan Cameron <Jonathan.Cameron@huawei.com> # except ASN.1
---
 drivers/pci/Makefile         |   4 +-
 drivers/pci/cma.asn1         |  41 ++++++++++++
 drivers/pci/cma.c            | 124 ++++++++++++++++++++++++++++++++++-
 include/linux/oid_registry.h |   3 +
 include/linux/spdm.h         |   6 +-
 lib/spdm/core.c              |   5 +-
 lib/spdm/req-authenticate.c  |   6 ++
 lib/spdm/spdm.h              |   2 +
 8 files changed, 187 insertions(+), 4 deletions(-)
 create mode 100644 drivers/pci/cma.asn1

diff --git a/drivers/pci/Makefile b/drivers/pci/Makefile
index 6bcfeb698961..5921a0d56104 100644
--- a/drivers/pci/Makefile
+++ b/drivers/pci/Makefile
@@ -35,7 +35,9 @@ obj-$(CONFIG_VGA_ARB)		+= vgaarb.o
 obj-$(CONFIG_PCI_DOE)		+= doe.o
 obj-$(CONFIG_PCI_DYNAMIC_OF_NODES) += of_property.o
 
-obj-$(CONFIG_PCI_CMA)		+= cma.o
+obj-$(CONFIG_PCI_CMA)		+= cma.o cma.asn1.o
+$(obj)/cma.o:			$(obj)/cma.asn1.h
+$(obj)/cma.asn1.o:		$(obj)/cma.asn1.c $(obj)/cma.asn1.h
 
 # Endpoint library must be initialized before its users
 obj-$(CONFIG_PCI_ENDPOINT)	+= endpoint/
diff --git a/drivers/pci/cma.asn1 b/drivers/pci/cma.asn1
new file mode 100644
index 000000000000..da41421d4085
--- /dev/null
+++ b/drivers/pci/cma.asn1
@@ -0,0 +1,41 @@
+-- SPDX-License-Identifier: BSD-3-Clause
+--
+-- Component Measurement and Authentication (CMA-SPDM, PCIe r6.1 sec 6.31.3)
+-- X.509 Subject Alternative Name (RFC 5280 sec 4.2.1.6)
+--
+-- Copyright (C) 2008 IETF Trust and the persons identified as authors
+-- of the code
+--
+-- https://www.rfc-editor.org/rfc/rfc5280#section-4.2.1.6
+--
+-- The ASN.1 module in RFC 5280 appendix A.1 uses EXPLICIT TAGS whereas the one
+-- in appendix A.2 uses IMPLICIT TAGS.  The kernel's simplified asn1_compiler.c
+-- always uses EXPLICIT TAGS, hence this ASN.1 module differs from RFC 5280 in
+-- that it adds IMPLICIT to definitions from appendix A.2 (such as GeneralName)
+-- and omits EXPLICIT in those definitions.
+
+SubjectAltName ::= GeneralNames
+
+GeneralNames ::= SEQUENCE OF GeneralName
+
+GeneralName ::= CHOICE {
+	otherName			[0] IMPLICIT OtherName,
+	rfc822Name			[1] IMPLICIT IA5String,
+	dNSName				[2] IMPLICIT IA5String,
+	x400Address			[3] ANY,
+	directoryName			[4] ANY,
+	ediPartyName			[5] IMPLICIT EDIPartyName,
+	uniformResourceIdentifier	[6] IMPLICIT IA5String,
+	iPAddress			[7] IMPLICIT OCTET STRING,
+	registeredID			[8] IMPLICIT OBJECT IDENTIFIER
+	}
+
+OtherName ::= SEQUENCE {
+	type-id			OBJECT IDENTIFIER ({ pci_cma_note_oid }),
+	value			[0] ANY ({ pci_cma_note_san })
+	}
+
+EDIPartyName ::= SEQUENCE {
+	nameAssigner		[0] ANY OPTIONAL,
+	partyName		[1] ANY
+	}
diff --git a/drivers/pci/cma.c b/drivers/pci/cma.c
index 275338b95640..e974d489c7a2 100644
--- a/drivers/pci/cma.c
+++ b/drivers/pci/cma.c
@@ -10,16 +10,137 @@
 
 #define dev_fmt(fmt) "CMA: " fmt
 
+#include <keys/x509-parser.h>
+#include <linux/asn1_decoder.h>
+#include <linux/oid_registry.h>
 #include <linux/pci.h>
 #include <linux/pci-doe.h>
 #include <linux/pm_runtime.h>
 #include <linux/spdm.h>
 
+#include "cma.asn1.h"
 #include "pci.h"
 
 /* Keyring that userspace can poke certs into */
 static struct key *pci_cma_keyring;
 
+/*
+ * The spdm_requester.c library calls pci_cma_validate() to check requirements
+ * for Leaf Certificates per PCIe r6.1 sec 6.31.3.
+ *
+ * pci_cma_validate() parses the Subject Alternative Name using the ASN.1
+ * module cma.asn1, which calls pci_cma_note_oid() and pci_cma_note_san()
+ * to compare an OtherName against the expected name.
+ *
+ * The expected name is constructed beforehand by pci_cma_construct_san().
+ *
+ * PCIe r6.2 drops the Subject Alternative Name spec language, even though
+ * it continues to require "the leaf certificate to include the information
+ * typically used by system software for device driver binding".  Use the
+ * Subject Alternative Name per PCIe r6.1 for lack of a replacement and
+ * because it is the de facto standard among existing products.
+ */
+#define CMA_NAME_MAX sizeof("Vendor=1234:Device=1234:CC=123456:"	  \
+			    "REV=12:SSVID=1234:SSID=1234:1234567890123456")
+
+struct pci_cma_x509_context {
+	struct pci_dev *pdev;
+	u8 slot;
+	enum OID last_oid;
+	char expected_name[CMA_NAME_MAX];
+	unsigned int expected_len;
+	unsigned int found:1;
+};
+
+int pci_cma_note_oid(void *context, size_t hdrlen, unsigned char tag,
+		     const void *value, size_t vlen)
+{
+	struct pci_cma_x509_context *ctx = context;
+
+	ctx->last_oid = look_up_OID(value, vlen);
+
+	return 0;
+}
+
+int pci_cma_note_san(void *context, size_t hdrlen, unsigned char tag,
+		     const void *value, size_t vlen)
+{
+	struct pci_cma_x509_context *ctx = context;
+
+	/* These aren't the drOIDs we're looking for. */
+	if (ctx->last_oid != OID_CMA)
+		return 0;
+
+	if (tag != ASN1_UTF8STR ||
+	    vlen != ctx->expected_len ||
+	    memcmp(value, ctx->expected_name, vlen) != 0) {
+		pci_err(ctx->pdev, "Leaf certificate of slot %u "
+			"has invalid Subject Alternative Name\n", ctx->slot);
+		return -EINVAL;
+	}
+
+	ctx->found = true;
+
+	return 0;
+}
+
+static unsigned int pci_cma_construct_san(struct pci_dev *pdev, char *name)
+{
+	unsigned int len;
+	u64 serial;
+
+	len = snprintf(name, CMA_NAME_MAX,
+		       "Vendor=%04hx:Device=%04hx:CC=%06x:REV=%02hhx",
+		       pdev->vendor, pdev->device, pdev->class, pdev->revision);
+
+	if (pdev->hdr_type == PCI_HEADER_TYPE_NORMAL)
+		len += snprintf(name + len, CMA_NAME_MAX - len,
+				":SSVID=%04hx:SSID=%04hx",
+				pdev->subsystem_vendor, pdev->subsystem_device);
+
+	serial = pci_get_dsn(pdev);
+	if (serial)
+		len += snprintf(name + len, CMA_NAME_MAX - len,
+				":%016llx", serial);
+
+	return len;
+}
+
+static int pci_cma_validate(struct device *dev, u8 slot,
+			    struct x509_certificate *leaf_cert)
+{
+	struct pci_dev *pdev = to_pci_dev(dev);
+	struct pci_cma_x509_context ctx;
+	int ret;
+
+	if (!leaf_cert->raw_san) {
+		pci_err(pdev, "Leaf certificate of slot %u "
+			"has no Subject Alternative Name\n", slot);
+		return -EINVAL;
+	}
+
+	ctx.pdev = pdev;
+	ctx.slot = slot;
+	ctx.found = false;
+	ctx.expected_len = pci_cma_construct_san(pdev, ctx.expected_name);
+
+	ret = asn1_ber_decoder(&cma_decoder, &ctx, leaf_cert->raw_san,
+			       leaf_cert->raw_san_size);
+	if (ret == -EBADMSG || ret == -EMSGSIZE)
+		pci_err(pdev, "Leaf certificate of slot %u "
+			"has malformed Subject Alternative Name\n", slot);
+	if (ret < 0)
+		return ret;
+
+	if (!ctx.found) {
+		pci_err(pdev, "Leaf certificate of slot %u "
+			"has no OtherName with CMA OID\n", slot);
+		return -EINVAL;
+	}
+
+	return 0;
+}
+
 #define PCI_DOE_FEATURE_CMA 1
 
 static ssize_t pci_doe_transport(void *priv, struct device *dev,
@@ -62,7 +183,8 @@ void pci_cma_init(struct pci_dev *pdev)
 		return;
 
 	pdev->spdm_state = spdm_create(&pdev->dev, pci_doe_transport, doe,
-				       PCI_DOE_MAX_PAYLOAD, pci_cma_keyring);
+				       PCI_DOE_MAX_PAYLOAD, pci_cma_keyring,
+				       pci_cma_validate);
 	if (!pdev->spdm_state)
 		return;
 
diff --git a/include/linux/oid_registry.h b/include/linux/oid_registry.h
index 6f9242259edc..44679f0a3fd6 100644
--- a/include/linux/oid_registry.h
+++ b/include/linux/oid_registry.h
@@ -145,6 +145,9 @@ enum OID {
 	OID_id_rsassa_pkcs1_v1_5_with_sha3_384, /* 2.16.840.1.101.3.4.3.15 */
 	OID_id_rsassa_pkcs1_v1_5_with_sha3_512, /* 2.16.840.1.101.3.4.3.16 */
 
+	/* PCI */
+	OID_CMA,			/* 2.23.147 */
+
 	OID__NR
 };
 
diff --git a/include/linux/spdm.h b/include/linux/spdm.h
index 0da7340020c4..568c68b17f1f 100644
--- a/include/linux/spdm.h
+++ b/include/linux/spdm.h
@@ -17,14 +17,18 @@
 struct key;
 struct device;
 struct spdm_state;
+struct x509_certificate;
 
 typedef ssize_t (spdm_transport)(void *priv, struct device *dev,
 				 const void *request, size_t request_sz,
 				 void *response, size_t response_sz);
 
+typedef int (spdm_validate)(struct device *dev, u8 slot,
+			    struct x509_certificate *leaf_cert);
+
 struct spdm_state *spdm_create(struct device *dev, spdm_transport *transport,
 			       void *transport_priv, u32 transport_sz,
-			       struct key *keyring);
+			       struct key *keyring, spdm_validate *validate);
 
 int spdm_authenticate(struct spdm_state *spdm_state);
 
diff --git a/lib/spdm/core.c b/lib/spdm/core.c
index f06402f6d127..be063b4fe73b 100644
--- a/lib/spdm/core.c
+++ b/lib/spdm/core.c
@@ -380,12 +380,14 @@ void spdm_reset(struct spdm_state *spdm_state)
  * @transport_priv: Transport private data
  * @transport_sz: Maximum message size the transport is capable of (in bytes)
  * @keyring: Trusted root certificates
+ * @validate: Function to validate additional leaf certificate requirements
+ *	(optional, may be %NULL)
  *
  * Return a pointer to the allocated SPDM session state or NULL on error.
  */
 struct spdm_state *spdm_create(struct device *dev, spdm_transport *transport,
 			       void *transport_priv, u32 transport_sz,
-			       struct key *keyring)
+			       struct key *keyring, spdm_validate *validate)
 {
 	struct spdm_state *spdm_state = kzalloc(sizeof(*spdm_state), GFP_KERNEL);
 
@@ -397,6 +399,7 @@ struct spdm_state *spdm_create(struct device *dev, spdm_transport *transport,
 	spdm_state->transport_priv = transport_priv;
 	spdm_state->transport_sz = transport_sz;
 	spdm_state->root_keyring = keyring;
+	spdm_state->validate = validate;
 
 	mutex_init(&spdm_state->lock);
 
diff --git a/lib/spdm/req-authenticate.c b/lib/spdm/req-authenticate.c
index 51fdb88f519b..90f7a7f2629c 100644
--- a/lib/spdm/req-authenticate.c
+++ b/lib/spdm/req-authenticate.c
@@ -537,6 +537,12 @@ static int spdm_validate_cert_chain(struct spdm_state *spdm_state, u8 slot)
 		offset += length;
 	} while (offset < total_length);
 
+	if (spdm_state->validate) {
+		rc = spdm_state->validate(spdm_state->dev, slot, prev);
+		if (rc)
+			return rc;
+	}
+
 	/* Steal pub pointer ahead of x509_free_certificate() */
 	spdm_state->leaf_key = prev->pub;
 	prev->pub = NULL;
diff --git a/lib/spdm/spdm.h b/lib/spdm/spdm.h
index 3a104959ad53..0e3bb6e18d91 100644
--- a/lib/spdm/spdm.h
+++ b/lib/spdm/spdm.h
@@ -455,6 +455,7 @@ struct spdm_error_rsp {
  *	responder's signatures.
  * @root_keyring: Keyring against which to check the first certificate in
  *	responder's certificate chain.
+ * @validate: Function to validate additional leaf certificate requirements.
  * @transcript: Concatenation of all SPDM messages exchanged during an
  *	authentication sequence.  Used to verify the signature, as it is
  *	computed over the hashed transcript.
@@ -495,6 +496,7 @@ struct spdm_state {
 	size_t slot_sz[SPDM_SLOTS];
 	struct public_key *leaf_key;
 	struct key *root_keyring;
+	spdm_validate *validate;
 
 	/* Transcript */
 	void *transcript;

---

## [11] Lukas Wunner — 2024-06-30
*Subject: [PATCH v2 10/18] PCI/CMA: Reauthenticate devices on reset and resume*

CMA-SPDM state is lost when a device undergoes a Conventional Reset.
(But not a Function Level Reset, PCIe r6.2 sec 6.6.2.)  A D3cold to D0
transition implies a Conventional Reset (PCIe r6.2 sec 5.8).

Thus, reauthenticate devices on resume from D3cold and on recovery from
a Secondary Bus Reset or DPC-induced Hot Reset.

The requirement to reauthenticate devices on resume from system sleep
(and in the future reestablish IDE encryption) is the reason why SPDM
needs to be in-kernel:  During ->resume_noirq, which is the first phase
after system sleep, the PCI core walks down the hierarchy, puts each
device in D0, restores its config space and invokes the driver's
->resume_noirq callback.  The driver is afforded the right to access the
device already during this phase.

To retain this usage model in the face of authentication and encryption,
CMA-SPDM reauthentication and IDE reestablishment must happen during the
->resume_noirq phase, before the driver's first access to the device.
The driver is thus afforded seamless authenticated and encrypted access
until the last moment before suspend and from the first moment after
resume.

During the ->resume_noirq phase, device interrupts are not yet enabled.
It is thus impossible to defer CMA-SPDM reauthentication to a user space
component on an attached disk or on the network, making an in-kernel
SPDM implementation mandatory.

The same catch-22 exists on recovery from a Conventional Reset:  A user
space SPDM implementation might live on a device which underwent reset,
rendering its execution impossible.

Signed-off-by: Lukas Wunner <lukas@wunner.de>
---
 drivers/pci/cma.c        | 15 +++++++++++++++
 drivers/pci/pci-driver.c |  1 +
 drivers/pci/pci.c        | 12 ++++++++++--
 drivers/pci/pci.h        |  2 ++
 drivers/pci/pcie/err.c   |  3 +++
 5 files changed, 31 insertions(+), 2 deletions(-)

diff --git a/drivers/pci/cma.c b/drivers/pci/cma.c
index e974d489c7a2..f2c435b04b92 100644
--- a/drivers/pci/cma.c
+++ b/drivers/pci/cma.c
@@ -195,6 +195,21 @@ void pci_cma_init(struct pci_dev *pdev)
 	spdm_authenticate(pdev->spdm_state);
 }
 
+/**
+ * pci_cma_reauthenticate() - Perform CMA-SPDM authentication again
+ * @pdev: Device to reauthenticate
+ *
+ * Can be called by drivers after device identity has mutated,
+ * e.g. after downloading firmware to an FPGA device.
+ */
+void pci_cma_reauthenticate(struct pci_dev *pdev)
+{
+	if (!pdev->spdm_state)
+		return;
+
+	spdm_authenticate(pdev->spdm_state);
+}
+
 void pci_cma_destroy(struct pci_dev *pdev)
 {
 	if (!pdev->spdm_state)
diff --git a/drivers/pci/pci-driver.c b/drivers/pci/pci-driver.c
index af2996d0d17f..89571f94debc 100644
--- a/drivers/pci/pci-driver.c
+++ b/drivers/pci/pci-driver.c
@@ -566,6 +566,7 @@ static void pci_pm_default_resume_early(struct pci_dev *pci_dev)
 	pci_pm_power_up_and_verify_state(pci_dev);
 	pci_restore_state(pci_dev);
 	pci_pme_restore(pci_dev);
+	pci_cma_reauthenticate(pci_dev);
 }
 
 static void pci_pm_bridge_power_up_actions(struct pci_dev *pci_dev)
diff --git a/drivers/pci/pci.c b/drivers/pci/pci.c
index 59e0949fb079..2a8063e7f2e0 100644
--- a/drivers/pci/pci.c
+++ b/drivers/pci/pci.c
@@ -4980,8 +4980,16 @@ static int pci_reset_bus_function(struct pci_dev *dev, bool probe)
 
 	rc = pci_dev_reset_slot_function(dev, probe);
 	if (rc != -ENOTTY)
-		return rc;
-	return pci_parent_bus_reset(dev, probe);
+		goto done;
+
+	rc = pci_parent_bus_reset(dev, probe);
+
+done:
+	/* CMA-SPDM state is lost upon a Conventional Reset */
+	if (!probe)
+		pci_cma_reauthenticate(dev);
+
+	return rc;
 }
 
 static int cxl_reset_bus_function(struct pci_dev *dev, bool probe)
diff --git a/drivers/pci/pci.h b/drivers/pci/pci.h
index fc90845caf83..b4c2ce5fd070 100644
--- a/drivers/pci/pci.h
+++ b/drivers/pci/pci.h
@@ -336,9 +336,11 @@ static inline void pci_doe_disconnected(struct pci_dev *pdev) { }
 #ifdef CONFIG_PCI_CMA
 void pci_cma_init(struct pci_dev *pdev);
 void pci_cma_destroy(struct pci_dev *pdev);
+void pci_cma_reauthenticate(struct pci_dev *pdev);
 #else
 static inline void pci_cma_init(struct pci_dev *pdev) { }
 static inline void pci_cma_destroy(struct pci_dev *pdev) { }
+static inline void pci_cma_reauthenticate(struct pci_dev *pdev) { }
 #endif
 
 /**
diff --git a/drivers/pci/pcie/err.c b/drivers/pci/pcie/err.c
index 31090770fffc..0028582f0590 100644
--- a/drivers/pci/pcie/err.c
+++ b/drivers/pci/pcie/err.c
@@ -133,6 +133,9 @@ static int report_slot_reset(struct pci_dev *dev, void *data)
 	pci_ers_result_t vote, *result = data;
 	const struct pci_error_handlers *err_handler;
 
+	/* CMA-SPDM state is lost upon a Conventional Reset */
+	pci_cma_reauthenticate(dev);
+
 	device_lock(&dev->dev);
 	pdrv = dev->driver;
 	if (!pdrv || !pdrv->err_handler || !pdrv->err_handler->slot_reset)

---

## [12] Lukas Wunner — 2024-06-30
*Subject: [PATCH v2 11/18] PCI/CMA: Expose in sysfs whether devices are
 authenticated*

The PCI core has just been amended to authenticate CMA-capable devices
on enumeration and store the result in an "authenticated" bit in struct
pci_dev->spdm_state.

Expose the bit to user space through an eponymous sysfs attribute.

Allow user space to trigger reauthentication (e.g. after it has updated
the CMA keyring) by writing to the sysfs attribute.

Implement the attribute in the SPDM library so that other bus types
besides PCI may take advantage of it.  They just need to add
spdm_attr_group to the attribute groups of their devices and amend the
dev_to_spdm_state() helper which retrieves the spdm_state for a given
device.

The helper may return an ERR_PTR if it couldn't be determined whether
SPDM is supported by the device.  The sysfs attribute is visible in that
case but returns an error on access.  This prevents downgrade attacks
where an attacker disturbs memory allocation or DOE communication
in order to create the appearance that SPDM is unsupported.

Subject to further discussion, a future commit might add a user-defined
policy to forbid driver binding to devices which failed authentication,
similar to the "authorized" attribute for USB.

Alternatively, authentication success might be signaled to user space
through a uevent, whereupon it may bind a (blacklisted) driver.
A uevent signaling authentication failure might similarly cause user
space to unbind or outright remove the potentially malicious device.

Traffic from devices which failed authentication could also be filtered
through ACS I/O Request Blocking Enable (PCIe r6.2 sec 7.7.11.3) or
through Link Disable (PCIe r6.2 sec 7.5.3.7).  Unlike an IOMMU, that
will not only protect the host, but also prevent malicious peer-to-peer
traffic to other devices.

Signed-off-by: Lukas Wunner <lukas@wunner.de>
---
 Documentation/ABI/testing/sysfs-devices-spdm | 31 +++++++
 MAINTAINERS                                  |  1 +
 drivers/pci/cma.c                            | 12 ++-
 drivers/pci/doe.c                            |  2 +
 drivers/pci/pci-sysfs.c                      |  3 +
 drivers/pci/pci.h                            |  5 ++
 include/linux/pci.h                          | 12 +++
 include/linux/spdm.h                         |  2 +
 lib/spdm/Makefile                            |  1 +
 lib/spdm/req-sysfs.c                         | 95 ++++++++++++++++++++
 lib/spdm/spdm.h                              |  1 +
 11 files changed, 161 insertions(+), 4 deletions(-)
 create mode 100644 Documentation/ABI/testing/sysfs-devices-spdm
 create mode 100644 lib/spdm/req-sysfs.c

diff --git a/Documentation/ABI/testing/sysfs-devices-spdm b/Documentation/ABI/testing/sysfs-devices-spdm
new file mode 100644
index 000000000000..2d6e5d513231
--- /dev/null
+++ b/Documentation/ABI/testing/sysfs-devices-spdm
@@ -0,0 +1,31 @@
+What:		/sys/devices/.../authenticated
+Date:		June 2024
+Contact:	Lukas Wunner <lukas@wunner.de>
+Description:
+		This file contains 1 if the device authenticated successfully
+		with SPDM (Security Protocol and Data Model).  It contains 0 if
+		the device failed authentication (and may thus be malicious).
+
+		Writing "re" to this file causes reauthentication.
+		That may be opportune after updating the device keyring.
+		The device keyring of the PCI bus is named ".cma"
+		(Component Measurement and Authentication).
+
+		Reauthentication may also be necessary after device identity
+		has mutated, e.g. after downloading firmware to an FPGA device.
+
+		The file is not visible if authentication is unsupported
+		by the device.
+
+		If the kernel could not determine whether authentication is
+		supported because memory was low or communication with the
+		device was not working, the file is visible but accessing it
+		fails with error code ENOTTY.
+
+		This prevents downgrade attacks where an attacker consumes
+		memory or disturbs communication in order to create the
+		appearance that a device does not support authentication.
+
+		The reason why authentication support could not be determined
+		is apparent from "dmesg".  To re-probe authentication support
+		of PCI devices, exercise the "remove" and "rescan" attributes.
diff --git a/MAINTAINERS b/MAINTAINERS
index 9aad3350da16..1ed5817e698c 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -20153,6 +20153,7 @@ L:	linux-cxl@vger.kernel.org
 L:	linux-pci@vger.kernel.org
 S:	Maintained
 T:	git git://git.kernel.org/pub/scm/linux/kernel/git/devsec/spdm.git
+F:	Documentation/ABI/testing/sysfs-devices-spdm
 F:	drivers/pci/cma*
 F:	include/linux/spdm.h
 F:	lib/spdm/
diff --git a/drivers/pci/cma.c b/drivers/pci/cma.c
index f2c435b04b92..59558714f143 100644
--- a/drivers/pci/cma.c
+++ b/drivers/pci/cma.c
@@ -171,8 +171,10 @@ void pci_cma_init(struct pci_dev *pdev)
 {
 	struct pci_doe_mb *doe;
 
-	if (IS_ERR(pci_cma_keyring))
+	if (IS_ERR(pci_cma_keyring)) {
+		pdev->spdm_state = ERR_PTR(-ENOTTY);
 		return;
+	}
 
 	if (!pci_is_pcie(pdev))
 		return;
@@ -185,8 +187,10 @@ void pci_cma_init(struct pci_dev *pdev)
 	pdev->spdm_state = spdm_create(&pdev->dev, pci_doe_transport, doe,
 				       PCI_DOE_MAX_PAYLOAD, pci_cma_keyring,
 				       pci_cma_validate);
-	if (!pdev->spdm_state)
+	if (!pdev->spdm_state) {
+		pdev->spdm_state = ERR_PTR(-ENOTTY);
 		return;
+	}
 
 	/*
 	 * Keep spdm_state allocated even if initial authentication fails
@@ -204,7 +208,7 @@ void pci_cma_init(struct pci_dev *pdev)
  */
 void pci_cma_reauthenticate(struct pci_dev *pdev)
 {
-	if (!pdev->spdm_state)
+	if (IS_ERR_OR_NULL(pdev->spdm_state))
 		return;
 
 	spdm_authenticate(pdev->spdm_state);
@@ -212,7 +216,7 @@ void pci_cma_reauthenticate(struct pci_dev *pdev)
 
 void pci_cma_destroy(struct pci_dev *pdev)
 {
-	if (!pdev->spdm_state)
+	if (IS_ERR_OR_NULL(pdev->spdm_state))
 		return;
 
 	spdm_destroy(pdev->spdm_state);
diff --git a/drivers/pci/doe.c b/drivers/pci/doe.c
index 34bb8f232799..0f94c4ed719e 100644
--- a/drivers/pci/doe.c
+++ b/drivers/pci/doe.c
@@ -694,6 +694,7 @@ void pci_doe_init(struct pci_dev *pdev)
 		if (IS_ERR(doe_mb)) {
 			pci_err(pdev, "[%x] failed to create mailbox: %ld\n",
 				offset, PTR_ERR(doe_mb));
+			pci_cma_disable(pdev);
 			continue;
 		}
 
@@ -702,6 +703,7 @@ void pci_doe_init(struct pci_dev *pdev)
 			pci_err(pdev, "[%x] failed to insert mailbox: %d\n",
 				offset, rc);
 			pci_doe_destroy_mb(doe_mb);
+			pci_cma_disable(pdev);
 		}
 	}
 }
diff --git a/drivers/pci/pci-sysfs.c b/drivers/pci/pci-sysfs.c
index 40cfa716392f..d9e467cbec6e 100644
--- a/drivers/pci/pci-sysfs.c
+++ b/drivers/pci/pci-sysfs.c
@@ -1661,6 +1661,9 @@ const struct attribute_group *pci_dev_attr_groups[] = {
 #endif
 #ifdef CONFIG_PCIEASPM
 	&aspm_ctrl_attr_group,
+#endif
+#ifdef CONFIG_PCI_CMA
+	&spdm_attr_group,
 #endif
 	NULL,
 };
diff --git a/drivers/pci/pci.h b/drivers/pci/pci.h
index b4c2ce5fd070..0041d39ca089 100644
--- a/drivers/pci/pci.h
+++ b/drivers/pci/pci.h
@@ -337,10 +337,15 @@ static inline void pci_doe_disconnected(struct pci_dev *pdev) { }
 void pci_cma_init(struct pci_dev *pdev);
 void pci_cma_destroy(struct pci_dev *pdev);
 void pci_cma_reauthenticate(struct pci_dev *pdev);
+static inline void pci_cma_disable(struct pci_dev *pdev)
+{
+	pdev->spdm_state = ERR_PTR(-ENOTTY);
+}
 #else
 static inline void pci_cma_init(struct pci_dev *pdev) { }
 static inline void pci_cma_destroy(struct pci_dev *pdev) { }
 static inline void pci_cma_reauthenticate(struct pci_dev *pdev) { }
+static inline void pci_cma_disable(struct pci_dev *pdev) { }
 #endif
 
 /**
diff --git a/include/linux/pci.h b/include/linux/pci.h
index cb2a0be57196..c29e9a196540 100644
--- a/include/linux/pci.h
+++ b/include/linux/pci.h
@@ -2674,6 +2674,18 @@ static inline bool pci_is_thunderbolt_attached(struct pci_dev *pdev)
 void pci_uevent_ers(struct pci_dev *pdev, enum  pci_ers_result err_type);
 #endif
 
+#ifdef CONFIG_PCI_CMA
+static inline struct spdm_state *pci_dev_to_spdm_state(struct pci_dev *pdev)
+{
+	return pdev->spdm_state;
+}
+#else
+static inline struct spdm_state *pci_dev_to_spdm_state(struct pci_dev *pdev)
+{
+	return NULL;
+}
+#endif
+
 #include <linux/dma-mapping.h>
 
 #define pci_printk(level, pdev, fmt, arg...) \
diff --git a/include/linux/spdm.h b/include/linux/spdm.h
index 568c68b17f1f..9835a3202a0e 100644
--- a/include/linux/spdm.h
+++ b/include/linux/spdm.h
@@ -34,4 +34,6 @@ int spdm_authenticate(struct spdm_state *spdm_state);
 
 void spdm_destroy(struct spdm_state *spdm_state);
 
+extern const struct attribute_group spdm_attr_group;
+
 #endif
diff --git a/lib/spdm/Makefile b/lib/spdm/Makefile
index f579cc898dbc..edd4a3cc3f5c 100644
--- a/lib/spdm/Makefile
+++ b/lib/spdm/Makefile
@@ -8,3 +8,4 @@
 obj-$(CONFIG_SPDM) += spdm.o
 
 spdm-y := core.o req-authenticate.o
+spdm-$(CONFIG_SYSFS) += req-sysfs.o
diff --git a/lib/spdm/req-sysfs.c b/lib/spdm/req-sysfs.c
new file mode 100644
index 000000000000..9bbed7abc153
--- /dev/null
+++ b/lib/spdm/req-sysfs.c
@@ -0,0 +1,95 @@
+// SPDX-License-Identifier: GPL-2.0
+/*
+ * DMTF Security Protocol and Data Model (SPDM)
+ * https://www.dmtf.org/dsp/DSP0274
+ *
+ * Requester role: sysfs interface
+ *
+ * Copyright (C) 2023-24 Intel Corporation
+ */
+
+#include "spdm.h"
+
+#include <linux/pci.h>
+
+/**
+ * dev_to_spdm_state() - Retrieve SPDM session state for given device
+ *
+ * @dev: Responder device
+ *
+ * Returns a pointer to the device's SPDM session state,
+ *	   %NULL if the device doesn't have one or
+ *	   %ERR_PTR if it couldn't be determined whether SPDM is supported.
+ *
+ * In the %ERR_PTR case, attributes are visible but return an error on access.
+ * This prevents downgrade attacks where an attacker disturbs memory allocation
+ * or communication with the device in order to create the appearance that SPDM
+ * is unsupported.  E.g. with PCI devices, the attacker may foil CMA or DOE
+ * initialization by simply hogging memory.
+ */
+static struct spdm_state *dev_to_spdm_state(struct device *dev)
+{
+	if (dev_is_pci(dev))
+		return pci_dev_to_spdm_state(to_pci_dev(dev));
+
+	/* Insert mappers for further bus types here. */
+
+	return NULL;
+}
+
+/* authenticated attribute */
+
+static umode_t spdm_attrs_are_visible(struct kobject *kobj,
+				      struct attribute *a, int n)
+{
+	struct device *dev = kobj_to_dev(kobj);
+	struct spdm_state *spdm_state = dev_to_spdm_state(dev);
+
+	if (!spdm_state)
+		return SYSFS_GROUP_INVISIBLE;
+
+	return a->mode;
+}
+
+static ssize_t authenticated_store(struct device *dev,
+				   struct device_attribute *attr,
+				   const char *buf, size_t count)
+{
+	struct spdm_state *spdm_state = dev_to_spdm_state(dev);
+	int rc;
+
+	if (IS_ERR(spdm_state))
+		return PTR_ERR(spdm_state);
+
+	if (sysfs_streq(buf, "re")) {
+		rc = spdm_authenticate(spdm_state);
+		if (rc)
+			return rc;
+	} else {
+		return -EINVAL;
+	}
+
+	return count;
+}
+
+static ssize_t authenticated_show(struct device *dev,
+				  struct device_attribute *attr, char *buf)
+{
+	struct spdm_state *spdm_state = dev_to_spdm_state(dev);
+
+	if (IS_ERR(spdm_state))
+		return PTR_ERR(spdm_state);
+
+	return sysfs_emit(buf, "%u\n", spdm_state->authenticated);
+}
+static DEVICE_ATTR_RW(authenticated);
+
+static struct attribute *spdm_attrs[] = {
+	&dev_attr_authenticated.attr,
+	NULL
+};
+
+const struct attribute_group spdm_attr_group = {
+	.attrs = spdm_attrs,
+	.is_visible = spdm_attrs_are_visible,
+};
diff --git a/lib/spdm/spdm.h b/lib/spdm/spdm.h
index 0e3bb6e18d91..0992b2bc3942 100644
--- a/lib/spdm/spdm.h
+++ b/lib/spdm/spdm.h
@@ -418,6 +418,7 @@ struct spdm_error_rsp {
  * struct spdm_state - SPDM session state
  *
  * @dev: Responder device.  Used for error reporting and passed to @transport.
+ *	Attributes in sysfs appear below this device's directory.
  * @lock: Serializes multiple concurrent spdm_authenticate() calls.
  * @authenticated: Whether device was authenticated successfully.
  * @dev: Responder device.  Used for error reporting and passed to @transport.

---

## [13] Lukas Wunner — 2024-06-30
*Subject: [PATCH v2 12/18] PCI/CMA: Expose certificates in sysfs*

The kernel already caches certificate chains retrieved from a device
upon authentication.  Expose them in "slot[0-7]" files in sysfs for
examination by user space.

As noted in the ABI documentation, the "slot[0-7]" files always have a
file size of 65535 bytes (the maximum size of a certificate chain per
SPDM 1.0.0 table 18), even if the certificate chain in the slot is
actually smaller.  Although it would be possible to use the certifiate
chain's actual size as the file size, doing so would require a separate
struct attribute_group for each device, which would occupy additional
memory.

Slots are visible in sysfs even if they're currently unprovisioned
because a future commit will add support for certificate provisioning
by writing to the "slot[0-7]" files.

Signed-off-by: Lukas Wunner <lukas@wunner.de>
---
 Documentation/ABI/testing/sysfs-devices-spdm | 49 ++++++++++++
 drivers/pci/pci-sysfs.c                      |  1 +
 include/linux/spdm.h                         |  1 +
 lib/spdm/req-authenticate.c                  | 30 +++++++-
 lib/spdm/req-sysfs.c                         | 80 ++++++++++++++++++++
 lib/spdm/spdm.h                              |  3 +
 6 files changed, 163 insertions(+), 1 deletion(-)

diff --git a/Documentation/ABI/testing/sysfs-devices-spdm b/Documentation/ABI/testing/sysfs-devices-spdm
index 2d6e5d513231..ed61405770d6 100644
--- a/Documentation/ABI/testing/sysfs-devices-spdm
+++ b/Documentation/ABI/testing/sysfs-devices-spdm
@@ -29,3 +29,52 @@ Description:
 		The reason why authentication support could not be determined
 		is apparent from "dmesg".  To re-probe authentication support
 		of PCI devices, exercise the "remove" and "rescan" attributes.
+
+
+What:		/sys/devices/.../certificates/
+What:		/sys/devices/.../certificates/slot[0-7]
+Date:		June 2024
+Contact:	Lukas Wunner <lukas@wunner.de>
+Description:
+		The "certificates" directory provides access to the certificate
+		chains contained in the up to 8 slots of a device.
+
+		A certificate chain is the concatenation of one or more ASN.1
+		DER-encoded X.509 v3 certificates (SPDM 1.0.0 sec 4.9.2.1).
+		It can be examined as follows::
+
+		 # openssl storeutl -text certificates/slot0
+
+		A common use case is to add the first certificate in a chain
+		to the keyring of trusted root certificates (".cma" in this
+		example) after comparing its fingerprint to the one provided
+		by the device manufacturer::
+
+		 # openssl x509 -in certificates/slot0 -fingerprint -nocert
+		 # openssl x509 -in certificates/slot0 -outform DER | \
+		   keyctl padd asymmetric "" %:.cma
+		 # echo re > authenticated
+
+		The file size of each slot is always 65535 bytes (the maximum
+		size of a certificate chain per SPDM 1.0.0 table 18), even if
+		the certificate chain in the slot is actually smaller.
+
+		Unprovisioned slots are represented as empty files.
+
+		Unsupported slots (introduced by SPDM 1.3 margin no 366) are
+		not visible.  If the device only supports SPDM version 1.2 or
+		earlier, all 8 slots are assumed to be supported and therefore
+		visible.
+
+		The kernel learns which slots are supported when authenticating
+		the device for the first time.  Hence, no slots are visible
+		until at least one authentication attempt has been performed.
+
+		SPDM doesn't support on-demand retrieval of certificate chains,
+		so the kernel caches them when (re-)authenticating the device.
+		SPDM allows provisioning slots behind the kernel's back by
+		sending a SET_CERTIFICATE request through a different transport
+		(e.g. via MCTP from a Baseboard Management Controller).
+		SPDM does not specify how to notify the kernel of such events,
+		so unless reauthentication is manually initiated to update the
+		kernel's cache, the "slot[0-7]" files may contain stale data.
diff --git a/drivers/pci/pci-sysfs.c b/drivers/pci/pci-sysfs.c
index d9e467cbec6e..a85388211104 100644
--- a/drivers/pci/pci-sysfs.c
+++ b/drivers/pci/pci-sysfs.c
@@ -1664,6 +1664,7 @@ const struct attribute_group *pci_dev_attr_groups[] = {
 #endif
 #ifdef CONFIG_PCI_CMA
 	&spdm_attr_group,
+	&spdm_certificates_group,
 #endif
 	NULL,
 };
diff --git a/include/linux/spdm.h b/include/linux/spdm.h
index 9835a3202a0e..97c7d4feab76 100644
--- a/include/linux/spdm.h
+++ b/include/linux/spdm.h
@@ -35,5 +35,6 @@ int spdm_authenticate(struct spdm_state *spdm_state);
 void spdm_destroy(struct spdm_state *spdm_state);
 
 extern const struct attribute_group spdm_attr_group;
+extern const struct attribute_group spdm_certificates_group;
 
 #endif
diff --git a/lib/spdm/req-authenticate.c b/lib/spdm/req-authenticate.c
index 90f7a7f2629c..1f701d07ad46 100644
--- a/lib/spdm/req-authenticate.c
+++ b/lib/spdm/req-authenticate.c
@@ -14,6 +14,7 @@
 #include "spdm.h"
 
 #include <linux/dev_printk.h>
+#include <linux/device.h>
 #include <linux/key.h>
 #include <linux/random.h>
 
@@ -288,9 +289,9 @@ static int spdm_get_digests(struct spdm_state *spdm_state)
 	struct spdm_get_digests_req *req = spdm_state->transcript_end;
 	struct spdm_get_digests_rsp *rsp;
 	unsigned long deprovisioned_slots;
+	u8 slot, supported_slots;
 	int rc, length;
 	size_t rsp_sz;
-	u8 slot;
 
 	*req = (struct spdm_get_digests_req) {
 		.code = SPDM_GET_DIGESTS,
@@ -338,6 +339,33 @@ static int spdm_get_digests(struct spdm_state *spdm_state)
 		return -EPROTO;
 	}
 
+	/*
+	 * If a bit is set in ProvisionedSlotMask, the corresponding bit in
+	 * SupportedSlotMask shall also be set (SPDM 1.3.0 table 35).
+	 */
+	if (spdm_state->version >= 0x13 && rsp->param2 & ~rsp->param1) {
+		dev_err(spdm_state->dev, "Malformed digests response\n");
+		return -EPROTO;
+	}
+
+	if (spdm_state->version >= 0x13)
+		supported_slots = rsp->param1;
+	else
+		supported_slots = GENMASK(7, 0);
+
+	if (spdm_state->supported_slots != supported_slots) {
+		spdm_state->supported_slots = supported_slots;
+
+		if (device_is_registered(spdm_state->dev)) {
+			rc = sysfs_update_group(&spdm_state->dev->kobj,
+						&spdm_certificates_group);
+			if (rc)
+				dev_err(spdm_state->dev,
+					"Cannot update certificates in sysfs: "
+					"%d\n", rc);
+		}
+	}
+
 	return 0;
 }
 
diff --git a/lib/spdm/req-sysfs.c b/lib/spdm/req-sysfs.c
index 9bbed7abc153..afba3c5a2e8f 100644
--- a/lib/spdm/req-sysfs.c
+++ b/lib/spdm/req-sysfs.c
@@ -93,3 +93,83 @@ const struct attribute_group spdm_attr_group = {
 	.attrs = spdm_attrs,
 	.is_visible = spdm_attrs_are_visible,
 };
+
+/* certificates attributes */
+
+static umode_t spdm_certificates_are_visible(struct kobject *kobj,
+					     struct bin_attribute *a, int n)
+{
+	struct device *dev = kobj_to_dev(kobj);
+	struct spdm_state *spdm_state = dev_to_spdm_state(dev);
+	u8 slot = a->attr.name[4] - '0';
+
+	if (IS_ERR_OR_NULL(spdm_state))
+		return SYSFS_GROUP_INVISIBLE;
+
+	if (!(spdm_state->supported_slots & BIT(slot)))
+		return 0;
+
+	return a->attr.mode;
+}
+
+static ssize_t spdm_cert_read(struct file *file, struct kobject *kobj,
+			      struct bin_attribute *a, char *buf, loff_t off,
+			      size_t count)
+{
+	struct device *dev = kobj_to_dev(kobj);
+	struct spdm_state *spdm_state = dev_to_spdm_state(dev);
+	u8 slot = a->attr.name[4] - '0';
+	size_t header_size, cert_size;
+
+	/*
+	 * Serialize with spdm_authenticate() as it may change hash_len,
+	 * slot_sz[] and slot[] members in struct spdm_state.
+	 */
+	guard(mutex)(&spdm_state->lock);
+
+	/*
+	 * slot[] is prefixed by the 4 + H header per SPDM 1.0.0 table 15.
+	 * The header is not exposed to user space, only the certificates are.
+	 */
+	header_size = sizeof(struct spdm_cert_chain) + spdm_state->hash_len;
+	cert_size = spdm_state->slot_sz[slot] - header_size;
+
+	if (!spdm_state->slot[slot])
+		return 0;
+	if (!count)
+		return 0;
+	if (off > cert_size)
+		return 0;
+	if (off + count > cert_size)
+		count = cert_size - off;
+
+	memcpy(buf, (u8 *)spdm_state->slot[slot] + header_size + off, count);
+	return count;
+}
+
+static BIN_ATTR(slot0, 0444, spdm_cert_read, NULL, 0xffff);
+static BIN_ATTR(slot1, 0444, spdm_cert_read, NULL, 0xffff);
+static BIN_ATTR(slot2, 0444, spdm_cert_read, NULL, 0xffff);
+static BIN_ATTR(slot3, 0444, spdm_cert_read, NULL, 0xffff);
+static BIN_ATTR(slot4, 0444, spdm_cert_read, NULL, 0xffff);
+static BIN_ATTR(slot5, 0444, spdm_cert_read, NULL, 0xffff);
+static BIN_ATTR(slot6, 0444, spdm_cert_read, NULL, 0xffff);
+static BIN_ATTR(slot7, 0444, spdm_cert_read, NULL, 0xffff);
+
+static struct bin_attribute *spdm_certificates_bin_attrs[] = {
+	&bin_attr_slot0,
+	&bin_attr_slot1,
+	&bin_attr_slot2,
+	&bin_attr_slot3,
+	&bin_attr_slot4,
+	&bin_attr_slot5,
+	&bin_attr_slot6,
+	&bin_attr_slot7,
+	NULL
+};
+
+const struct attribute_group spdm_certificates_group = {
+	.name = "certificates",
+	.bin_attrs = spdm_certificates_bin_attrs,
+	.is_bin_visible = spdm_certificates_are_visible,
+};
diff --git a/lib/spdm/spdm.h b/lib/spdm/spdm.h
index 0992b2bc3942..6c426b2be372 100644
--- a/lib/spdm/spdm.h
+++ b/lib/spdm/spdm.h
@@ -436,6 +436,8 @@ struct spdm_error_rsp {
  * @base_hash_alg: Hash algorithm for signature verification of
  *	CHALLENGE_AUTH messages.
  *	Selected by responder during NEGOTIATE_ALGORITHMS exchange.
+ * @supported_slots: Bitmask of responder's supported certificate slots.
+ *	Received during GET_DIGESTS exchange (from SPDM 1.3).
  * @provisioned_slots: Bitmask of responder's provisioned certificate slots.
  *	Received during GET_DIGESTS exchange.
  * @base_asym_enc: Human-readable name of @base_asym_alg's signature encoding.
@@ -480,6 +482,7 @@ struct spdm_state {
 	u32 rsp_caps;
 	u32 base_asym_alg;
 	u32 base_hash_alg;
+	unsigned long supported_slots;
 	unsigned long provisioned_slots;
 
 	/* Signature algorithm */

---

## [14] Lukas Wunner — 2024-06-30
*Subject: [PATCH v2 13/18] sysfs: Allow bin_attributes to be added to groups*

Commit dfa87c824a9a ("sysfs: allow attributes to be added to groups")
introduced dynamic addition of sysfs attributes to groups.

Allow the same for bin_attributes, in support of a subsequent commit
which adds various bin_attributes every time a PCI device is
authenticated.

Addition of bin_attributes to groups differs from regular attributes in
that different kernfs_ops are selected by sysfs_add_bin_file_mode_ns()
vis-à-vis sysfs_add_file_mode_ns().

So call either of those two functions from sysfs_add_file_to_group()
based on an additional boolean parameter and add two wrapper functions,
one for bin_attributes and another for regular attributes.

Removal of bin_attributes from groups does not require a differentiation
for bin_attributes and can use the same code path as regular attributes.

Signed-off-by: Lukas Wunner <lukas@wunner.de>
Cc: Alan Stern <stern@rowland.harvard.edu>
---
 fs/sysfs/file.c       | 69 ++++++++++++++++++++++++++++++++++++-------
 include/linux/sysfs.h | 19 ++++++++++++
 2 files changed, 78 insertions(+), 10 deletions(-)

diff --git a/fs/sysfs/file.c b/fs/sysfs/file.c
index d1995e2d6c94..9268232781b5 100644
--- a/fs/sysfs/file.c
+++ b/fs/sysfs/file.c
@@ -383,14 +383,14 @@ int sysfs_create_files(struct kobject *kobj, const struct attribute * const *ptr
 }
 EXPORT_SYMBOL_GPL(sysfs_create_files);
 
-/**
- * sysfs_add_file_to_group - add an attribute file to a pre-existing group.
- * @kobj: object we're acting for.
- * @attr: attribute descriptor.
- * @group: group name.
- */
-int sysfs_add_file_to_group(struct kobject *kobj,
-		const struct attribute *attr, const char *group)
+static const struct bin_attribute *to_bin_attr(const struct attribute *attr)
+{
+	return container_of(attr, struct bin_attribute, attr);
+}
+
+static int __sysfs_add_file_to_group(struct kobject *kobj,
+				     const struct attribute *attr,
+				     const char *group, bool is_bin_attr)
 {
 	struct kernfs_node *parent;
 	kuid_t uid;
@@ -408,14 +408,49 @@ int sysfs_add_file_to_group(struct kobject *kobj,
 		return -ENOENT;
 
 	kobject_get_ownership(kobj, &uid, &gid);
-	error = sysfs_add_file_mode_ns(parent, attr, attr->mode, uid, gid,
-				       NULL);
+	if (is_bin_attr)
+		error = sysfs_add_bin_file_mode_ns(parent, to_bin_attr(attr),
+						   attr->mode, uid, gid, NULL);
+	else
+		error = sysfs_add_file_mode_ns(parent, attr,
+					       attr->mode, uid, gid, NULL);
 	kernfs_put(parent);
 
 	return error;
 }
+
+/**
+ * sysfs_add_file_to_group - add an attribute file to a pre-existing group.
+ * @kobj: object we're acting for.
+ * @attr: attribute descriptor.
+ * @group: group name.
+ *
+ * Returns 0 on success or error code on failure.
+ */
+int sysfs_add_file_to_group(struct kobject *kobj,
+			    const struct attribute *attr,
+			    const char *group)
+{
+	return __sysfs_add_file_to_group(kobj, attr, group, false);
+}
 EXPORT_SYMBOL_GPL(sysfs_add_file_to_group);
 
+/**
+ * sysfs_add_bin_file_to_group - add bin_attribute file to pre-existing group.
+ * @kobj: object we're acting for.
+ * @attr: attribute descriptor.
+ * @group: group name.
+ *
+ * Returns 0 on success or error code on failure.
+ */
+int sysfs_add_bin_file_to_group(struct kobject *kobj,
+				const struct bin_attribute *attr,
+				const char *group)
+{
+	return __sysfs_add_file_to_group(kobj, &attr->attr, group, true);
+}
+EXPORT_SYMBOL_GPL(sysfs_add_bin_file_to_group);
+
 /**
  * sysfs_chmod_file - update the modified mode value on an object attribute.
  * @kobj: object we're acting for.
@@ -565,6 +600,20 @@ void sysfs_remove_file_from_group(struct kobject *kobj,
 }
 EXPORT_SYMBOL_GPL(sysfs_remove_file_from_group);
 
+/**
+ * sysfs_remove_bin_file_from_group - remove bin_attribute file from group.
+ * @kobj: object we're acting for.
+ * @attr: attribute descriptor.
+ * @group: group name.
+ */
+void sysfs_remove_bin_file_from_group(struct kobject *kobj,
+				      const struct bin_attribute *attr,
+				      const char *group)
+{
+	sysfs_remove_file_from_group(kobj, &attr->attr, group);
+}
+EXPORT_SYMBOL_GPL(sysfs_remove_bin_file_from_group);
+
 /**
  *	sysfs_create_bin_file - create binary file for object.
  *	@kobj:	object.
diff --git a/include/linux/sysfs.h b/include/linux/sysfs.h
index a7d725fbf739..aff1d81e8971 100644
--- a/include/linux/sysfs.h
+++ b/include/linux/sysfs.h
@@ -451,6 +451,12 @@ int sysfs_add_file_to_group(struct kobject *kobj,
 			const struct attribute *attr, const char *group);
 void sysfs_remove_file_from_group(struct kobject *kobj,
 			const struct attribute *attr, const char *group);
+int sysfs_add_bin_file_to_group(struct kobject *kobj,
+				const struct bin_attribute *attr,
+				const char *group);
+void sysfs_remove_bin_file_from_group(struct kobject *kobj,
+				      const struct bin_attribute *attr,
+				      const char *group);
 int sysfs_merge_group(struct kobject *kobj,
 		       const struct attribute_group *grp);
 void sysfs_unmerge_group(struct kobject *kobj,
@@ -660,6 +666,19 @@ static inline void sysfs_remove_file_from_group(struct kobject *kobj,
 {
 }
 
+static inline int sysfs_add_bin_file_to_group(struct kobject *kobj,
+					      const struct bin_attribute *attr,
+					      const char *group)
+{
+	return 0;
+}
+
+static inline void sysfs_remove_bin_file_from_group(struct kobject *kobj,
+					      const struct bin_attribute *attr,
+					      const char *group)
+{
+}
+
 static inline int sysfs_merge_group(struct kobject *kobj,
 		       const struct attribute_group *grp)
 {

---

## [15] Lukas Wunner — 2024-06-30
*Subject: [PATCH v2 14/18] sysfs: Allow symlinks to be added between sibling
 groups*

A subsequent commit has the need to create a symlink from an attribute
in a first group to an attribute in a second group.  Both groups belong
to the same kobject.

More specifically, each signature received from an authentication-
capable device is going to be represented by a file in the first group
and shall be accompanied by a symlink pointing to the certificate slot
in the second group which was used to generate the signature (a device
may have multiple certificate slots and each is represented by a
separate file in the second group):

/sys/devices/.../signatures/0_certificate_chain -> .../certificates/slot0

There is already a sysfs_add_link_to_group() helper to add a symlink to
a group which points to another kobject, but this isn't what's needed
here.

So add a new function to add a symlink among sibling groups of the same
kobject.

The existing sysfs_add_link_to_group() helper goes through a locking
dance of acquiring sysfs_symlink_target_lock in order to acquire a
reference on the target kobject.  That's unnecessary for the present
use case as the link itself and its target reside below the same
kobject.

To simplify error handling in the newly introduced function, add a
DEFINE_FREE() clause for kernfs_put().

Signed-off-by: Lukas Wunner <lukas@wunner.de>
---
 fs/sysfs/group.c       | 33 +++++++++++++++++++++++++++++++++
 include/linux/kernfs.h |  2 ++
 include/linux/sysfs.h  | 10 ++++++++++
 3 files changed, 45 insertions(+)

diff --git a/fs/sysfs/group.c b/fs/sysfs/group.c
index d22ad67a0f32..0cb52c9b9e19 100644
--- a/fs/sysfs/group.c
+++ b/fs/sysfs/group.c
@@ -445,6 +445,39 @@ void sysfs_remove_link_from_group(struct kobject *kobj, const char *group_name,
 }
 EXPORT_SYMBOL_GPL(sysfs_remove_link_from_group);
 
+/**
+ * sysfs_add_link_to_sibling_group - add a symlink to a sibling attribute group.
+ * @kobj:	The kobject containing the groups.
+ * @link_grp:	The name of the group in which to create the symlink.
+ * @link:	The name of the symlink to create.
+ * @target_grp:	The name of the target group.
+ * @target:	The name of the target attribute.
+ *
+ * Returns 0 on success or error code on failure.
+ */
+int sysfs_add_link_to_sibling_group(struct kobject *kobj,
+				    const char *link_grp, const char *link,
+				    const char *target_grp, const char *target)
+{
+	struct kernfs_node *target_grp_kn __free(kernfs_put),
+			   *target_kn __free(kernfs_put) = NULL,
+			   *link_grp_kn __free(kernfs_put) = NULL;
+
+	target_grp_kn = kernfs_find_and_get(kobj->sd, target_grp);
+	if (!target_grp_kn)
+		return -ENOENT;
+
+	target_kn = kernfs_find_and_get(target_grp_kn, target);
+	if (!target_kn)
+		return -ENOENT;
+
+	link_grp_kn = kernfs_find_and_get(kobj->sd, link_grp);
+	if (!link_grp_kn)
+		return -ENOENT;
+
+	return PTR_ERR_OR_ZERO(kernfs_create_link(link_grp_kn, link, target_kn));
+}
+
 /**
  * compat_only_sysfs_link_entry_to_kobj - add a symlink to a kobject pointing
  * to a group or an attribute
diff --git a/include/linux/kernfs.h b/include/linux/kernfs.h
index 87c79d076d6d..d5726d070dba 100644
--- a/include/linux/kernfs.h
+++ b/include/linux/kernfs.h
@@ -407,6 +407,8 @@ struct kernfs_node *kernfs_walk_and_get_ns(struct kernfs_node *parent,
 void kernfs_get(struct kernfs_node *kn);
 void kernfs_put(struct kernfs_node *kn);
 
+DEFINE_FREE(kernfs_put, struct kernfs_node *, if (_T) kernfs_put(_T))
+
 struct kernfs_node *kernfs_node_from_dentry(struct dentry *dentry);
 struct kernfs_root *kernfs_root_from_sb(struct super_block *sb);
 struct inode *kernfs_get_inode(struct super_block *sb, struct kernfs_node *kn);
diff --git a/include/linux/sysfs.h b/include/linux/sysfs.h
index aff1d81e8971..6f970832bd36 100644
--- a/include/linux/sysfs.h
+++ b/include/linux/sysfs.h
@@ -465,6 +465,9 @@ int sysfs_add_link_to_group(struct kobject *kobj, const char *group_name,
 			    struct kobject *target, const char *link_name);
 void sysfs_remove_link_from_group(struct kobject *kobj, const char *group_name,
 				  const char *link_name);
+int sysfs_add_link_to_sibling_group(struct kobject *kobj,
+				    const char *link_grp, const char *link,
+				    const char *target_grp, const char *target);
 int compat_only_sysfs_link_entry_to_kobj(struct kobject *kobj,
 					 struct kobject *target_kobj,
 					 const char *target_name,
@@ -702,6 +705,13 @@ static inline void sysfs_remove_link_from_group(struct kobject *kobj,
 {
 }
 
+static inline int sysfs_add_link_to_sibling_group(struct kobject *kobj,
+		const char *link_grp, const char *link,
+		const char *target_grp, const char *target)
+{
+	return 0;
+}
+
 static inline int compat_only_sysfs_link_entry_to_kobj(struct kobject *kobj,
 						       struct kobject *target_kobj,
 						       const char *target_name,

---

## [16] Lukas Wunner — 2024-06-30
*Subject: [PATCH v2 15/18] PCI/CMA: Expose a log of received signatures in
 sysfs*

When authenticating a device with CMA-SPDM, the kernel verifies the
challenge-response received from the device, but otherwise keeps it to
itself.

James Bottomley contends that's not good enough because user space or a
remote attestation service may want to re-verify the challenge-response:
Either because it mistrusts the kernel or because the kernel is unaware
of policy constraints that user space or the remote attestation service
want to apply.

Facilitate such use cases by exposing a log in sysfs which consists of
several files for each challenge-response event.  The files are prefixed
with a monotonically increasing number, starting at 0:

/sys/devices/.../signatures/0_signature
/sys/devices/.../signatures/0_transcript
/sys/devices/.../signatures/0_requester_nonce
/sys/devices/.../signatures/0_responder_nonce
/sys/devices/.../signatures/0_hash_algorithm
/sys/devices/.../signatures/0_combined_spdm_prefix
/sys/devices/.../signatures/0_certificate_chain
/sys/devices/.../signatures/0_type

The 0_signature is computed over the 0_transcript (a concatenation of
all SPDM messages exchanged with the device).

To verify the signature, 0_transcript is hashed with 0_hash_algorithm
(e.g. "sha384") and prefixed by 0_combined_spdm_prefix.

The public key to verify the signature against is the leaf certificate
contained in 0_certificate_chain.

The nonces chosen by requester and responder are exposed as separate
attributes to ease verification of their freshness.  They're already
contained in the transcript but their offsets within the transcript are
variable, so user space would otherwise have to parse the SPDM messages
in the transcript to find the nonces.

The type attribute contains the event type:  Currently it is always
"responder-challenge_auth signing".  In the future it may also contain
"responder-measurements signing".

This custom log format was chosen for lack of a better alternative.
Although the TCG PFP Specification defines DEVICE_SECURITY_EVENT_DATA
structures, those structures do not store the transcript (which can be
a few kBytes or up to several MBytes in size).  They do store nonces,
hence at least allow for verification of nonce freshness.  But without
the transcript, user space cannot verify the signature:

https://trustedcomputinggroup.org/resource/pc-client-specific-platform-firmware-profile-specification/

Exposing the transcript as an attribute of its own has the benefit that
it can directly be fed into a protocol dissector for debugging purposes
(think Wireshark).

Signed-off-by: Lukas Wunner <lukas@wunner.de>
Cc: James Bottomley <James.Bottomley@HansenPartnership.com>
Cc: Jérôme Glisse <jglisse@google.com>
Cc: Jason Gunthorpe <jgg@nvidia.com>
---
 Documentation/ABI/testing/sysfs-devices-spdm | 118 +++++++
 drivers/pci/cma.c                            |   6 +
 drivers/pci/pci-sysfs.c                      |   1 +
 drivers/pci/pci.h                            |   2 +
 drivers/pci/probe.c                          |   2 +
 include/linux/spdm.h                         |   6 +
 lib/spdm/core.c                              |   2 +
 lib/spdm/req-authenticate.c                  |   9 +-
 lib/spdm/req-sysfs.c                         | 333 +++++++++++++++++++
 lib/spdm/spdm.h                              |  20 ++
 10 files changed, 498 insertions(+), 1 deletion(-)

diff --git a/Documentation/ABI/testing/sysfs-devices-spdm b/Documentation/ABI/testing/sysfs-devices-spdm
index ed61405770d6..ae7b3f701ded 100644
--- a/Documentation/ABI/testing/sysfs-devices-spdm
+++ b/Documentation/ABI/testing/sysfs-devices-spdm
@@ -78,3 +78,121 @@ Description:
 		SPDM does not specify how to notify the kernel of such events,
 		so unless reauthentication is manually initiated to update the
 		kernel's cache, the "slot[0-7]" files may contain stale data.
+
+
+What:		/sys/devices/.../signatures/
+What:		/sys/devices/.../signatures/[0-9]*_signature
+What:		/sys/devices/.../signatures/[0-9]*_transcript
+What:		/sys/devices/.../signatures/[0-9]*_hash_algorithm
+What:		/sys/devices/.../signatures/[0-9]*_combined_spdm_prefix
+What:		/sys/devices/.../signatures/[0-9]*_certificate_chain
+Date:		June 2024
+Contact:	Lukas Wunner <lukas@wunner.de>
+Description:
+		The "signatures" directory contains a log of signatures
+		received from the device to allow for their re-verification.
+		It is meant for remote attestation services which do not trust
+		the kernel to have verified the signatures correctly or which
+		want to apply policy constraints of their own.
+
+		Each signature is exposed as a separate file.  The filename
+		is prefixed with a monotonically increasing, unsigned, 32 bit
+		number, starting at 0.
+
+		The signature is computed over the "transcript" file, which is
+		a concatenation of all SPDM messages exchanged with the device.
+		SPDM 1.2 and newer hash the transcript with "hash_algorithm"
+		and prepend the "combined_spdm_prefix" before computing the
+		signature (SPDM 1.2.0 sec 15).  For SPDM 1.0 and 1.1, that step
+		is omitted and "combined_spdm_prefix" is an empty file.
+
+		The signature is verified against the leaf certificate in the
+		"certificate_chain".  To save memory, "certificate_chain" is
+		a symbolic link to the slot used for signature generation.
+		If the slot has since been provisioned with a different
+		certificate chain, verification of the signature will fail.
+
+		In bash syntax, the signature is verified as follows::
+
+		 # number of signature to verify
+		 num=0
+
+		 # split certificate chain into individual certificates
+		 openssl storeutl -text ${num}_certificate_chain | \
+		     csplit -z -f /tmp/cert - '/^[0-9]*: Certificate$/' '{*}'
+
+		 # extract public key from leaf certificate
+		 leaf_cert=$(\ls /tmp/cert?? | tail -1)
+		 openssl x509 -pubkey -in ${leaf_cert} -out ${leaf_cert}.pub
+
+		 # verify signature
+		 if [ \! -s ${num}_combined_spdm_prefix ] ; then
+		     # SPDM 1.0 and 1.1
+		     openssl dgst -$(cat ${num}_hash_algorithm) \
+		         -signature ${num}_signature -verify ${leaf_cert}.pub \
+		         ${num}_transcript
+		 else
+		     # SPDM 1.2 and newer
+		     openssl dgst -$(cat ${num}_hash_algorithm) \
+		         -binary -out /tmp/transcript_hashed ${num}_transcript
+		     openssl dgst -$(cat ${num}_hash_algorithm) \
+		         -signature ${num}_signature -verify ${leaf_cert}.pub \
+		         ${num}_combined_spdm_prefix /tmp/transcript_hashed
+		 fi
+
+		Note: The above works for RSA signatures, but not for ECDSA.
+		SPDM encodes ECDSA signatures in P1363 format (concatenation of
+		two raw integers), whereas openssl only supports X9.62 format
+		(ASN.1 DER sequence of two integers).  There is no command line
+		utility to convert between the two formats, but most popular
+		crypto libraries offer conversion routines:
+
+		| https://github.com/java-crypto/cross_platform_crypto/blob/main/docs/ecdsa_signature_conversion.md
+
+		The "transcript" file can be fed to a protocol dissector to
+		examine the SPDM messages it contains:
+
+		| https://github.com/th-duvanel/spdm-wid
+		| https://github.com/jyao1/wireshark-spdm
+		| https://github.com/DMTF/spdm-dump
+
+		Note:  To ease signature verification, the "transcript" file
+		does not contain the trailing signature.  However the signature
+		is part of the final CHALLENGE_AUTH message, so the protocol
+		dissector needs to be fed the concatenation of "transcript"
+		and "signature".
+
+
+What:		/sys/devices/.../signatures/[0-9]*_type
+Date:		June 2024
+Contact:	Lukas Wunner <lukas@wunner.de>
+Description:
+		This file contains the type of event that led to signature
+		generation.  It is one of (sans quotes):
+
+		"responder-challenge_auth signing"
+
+
+What:		/sys/devices/.../signatures/[0-9]*_requester_nonce
+What:		/sys/devices/.../signatures/[0-9]*_responder_nonce
+Date:		June 2024
+Contact:	Lukas Wunner <lukas@wunner.de>
+Description:
+		These files contain the 32 byte nonce chosen by requester and
+		responder.  They allow remote attestation services to verify
+		freshness (uniqueness) of the nonces.  Nonces used more than
+		once can be identified with::
+
+		 # hexdump -e '32/1 "%02x" "\n"' [0-9]*_nonce | sort | \
+		   uniq -c | grep -v '^      1'
+
+		Remote attestation services may also want to verify that the
+		entropy of the nonces is acceptable::
+
+		 # ent 0_requester_nonce
+
+		Note:  The nonces are also contained in the "transcript", but
+		their offsets within the transcript are variable.  It would be
+		necessary to parse the SPDM messages in the transcript to find
+		and extract the nonces, which is cumbersome.  That's why they
+		are exposed as separate files.
diff --git a/drivers/pci/cma.c b/drivers/pci/cma.c
index 59558714f143..e5d9ab5d646e 100644
--- a/drivers/pci/cma.c
+++ b/drivers/pci/cma.c
@@ -199,6 +199,12 @@ void pci_cma_init(struct pci_dev *pdev)
 	spdm_authenticate(pdev->spdm_state);
 }
 
+void pci_cma_publish(struct pci_dev *pdev)
+{
+	if (!IS_ERR_OR_NULL(pdev->spdm_state))
+		spdm_publish_log(pdev->spdm_state);
+}
+
 /**
  * pci_cma_reauthenticate() - Perform CMA-SPDM authentication again
  * @pdev: Device to reauthenticate
diff --git a/drivers/pci/pci-sysfs.c b/drivers/pci/pci-sysfs.c
index a85388211104..bf019371ef9a 100644
--- a/drivers/pci/pci-sysfs.c
+++ b/drivers/pci/pci-sysfs.c
@@ -1665,6 +1665,7 @@ const struct attribute_group *pci_dev_attr_groups[] = {
 #ifdef CONFIG_PCI_CMA
 	&spdm_attr_group,
 	&spdm_certificates_group,
+	&spdm_signatures_group,
 #endif
 	NULL,
 };
diff --git a/drivers/pci/pci.h b/drivers/pci/pci.h
index 0041d39ca089..452cbfcc0ca0 100644
--- a/drivers/pci/pci.h
+++ b/drivers/pci/pci.h
@@ -336,6 +336,7 @@ static inline void pci_doe_disconnected(struct pci_dev *pdev) { }
 #ifdef CONFIG_PCI_CMA
 void pci_cma_init(struct pci_dev *pdev);
 void pci_cma_destroy(struct pci_dev *pdev);
+void pci_cma_publish(struct pci_dev *pdev);
 void pci_cma_reauthenticate(struct pci_dev *pdev);
 static inline void pci_cma_disable(struct pci_dev *pdev)
 {
@@ -344,6 +345,7 @@ static inline void pci_cma_disable(struct pci_dev *pdev)
 #else
 static inline void pci_cma_init(struct pci_dev *pdev) { }
 static inline void pci_cma_destroy(struct pci_dev *pdev) { }
+static inline void pci_cma_publish(struct pci_dev *pdev) { }
 static inline void pci_cma_reauthenticate(struct pci_dev *pdev) { }
 static inline void pci_cma_disable(struct pci_dev *pdev) { }
 #endif
diff --git a/drivers/pci/probe.c b/drivers/pci/probe.c
index 5297f9a08ca2..0493fc44da13 100644
--- a/drivers/pci/probe.c
+++ b/drivers/pci/probe.c
@@ -2583,6 +2583,8 @@ void pci_device_add(struct pci_dev *dev, struct pci_bus *bus)
 	dev->match_driver = false;
 	ret = device_add(&dev->dev);
 	WARN_ON(ret < 0);
+
+	pci_cma_publish(dev);
 }
 
 struct pci_dev *pci_scan_single_device(struct pci_bus *bus, int devfn)
diff --git a/include/linux/spdm.h b/include/linux/spdm.h
index 97c7d4feab76..cc8aa8f77368 100644
--- a/include/linux/spdm.h
+++ b/include/linux/spdm.h
@@ -34,7 +34,13 @@ int spdm_authenticate(struct spdm_state *spdm_state);
 
 void spdm_destroy(struct spdm_state *spdm_state);
 
+#ifdef CONFIG_SYSFS
 extern const struct attribute_group spdm_attr_group;
 extern const struct attribute_group spdm_certificates_group;
+extern const struct attribute_group spdm_signatures_group;
+void spdm_publish_log(struct spdm_state *spdm_state);
+#else
+static inline void spdm_publish_log(struct spdm_state *spdm_state) { }
+#endif
 
 #endif
diff --git a/lib/spdm/core.c b/lib/spdm/core.c
index be063b4fe73b..d962a1344760 100644
--- a/lib/spdm/core.c
+++ b/lib/spdm/core.c
@@ -402,6 +402,7 @@ struct spdm_state *spdm_create(struct device *dev, spdm_transport *transport,
 	spdm_state->validate = validate;
 
 	mutex_init(&spdm_state->lock);
+	INIT_LIST_HEAD(&spdm_state->log);
 
 	return spdm_state;
 }
@@ -420,6 +421,7 @@ void spdm_destroy(struct spdm_state *spdm_state)
 		kvfree(spdm_state->slot[slot]);
 
 	spdm_reset(spdm_state);
+	spdm_destroy_log(spdm_state);
 	mutex_destroy(&spdm_state->lock);
 	kfree(spdm_state);
 }
diff --git a/lib/spdm/req-authenticate.c b/lib/spdm/req-authenticate.c
index 1f701d07ad46..0c74dc0e5cf4 100644
--- a/lib/spdm/req-authenticate.c
+++ b/lib/spdm/req-authenticate.c
@@ -617,13 +617,13 @@ static size_t spdm_challenge_rsp_sz(struct spdm_state *spdm_state,
 
 static int spdm_challenge(struct spdm_state *spdm_state, u8 slot)
 {
+	size_t req_sz, rsp_sz, rsp_sz_max, req_nonce_off, rsp_nonce_off;
 	struct spdm_challenge_rsp *rsp __free(kfree);
 	struct spdm_challenge_req req = {
 		.code = SPDM_CHALLENGE,
 		.param1 = slot,
 		.param2 = 0, /* No measurement summary hash */
 	};
-	size_t req_sz, rsp_sz, rsp_sz_max;
 	int rc, length;
 
 	get_random_bytes(&req.nonce, sizeof(req.nonce));
@@ -649,10 +649,14 @@ static int spdm_challenge(struct spdm_state *spdm_state, u8 slot)
 		return -EIO;
 	}
 
+	req_nonce_off = spdm_state->transcript_end - spdm_state->transcript +
+			offsetof(typeof(req), nonce);
 	rc = spdm_append_transcript(spdm_state, &req, req_sz);
 	if (rc)
 		return rc;
 
+	rsp_nonce_off = spdm_state->transcript_end - spdm_state->transcript +
+			sizeof(*rsp) + spdm_state->hash_len;
 	rc = spdm_append_transcript(spdm_state, rsp, rsp_sz);
 	if (rc)
 		return rc;
@@ -666,6 +670,9 @@ static int spdm_challenge(struct spdm_state *spdm_state, u8 slot)
 		dev_info(spdm_state->dev,
 			 "Authenticated with certificate slot %u\n", slot);
 
+	spdm_create_log_entry(spdm_state, spdm_context, slot,
+			      req_nonce_off, rsp_nonce_off);
+
 	return rc;
 }
 
diff --git a/lib/spdm/req-sysfs.c b/lib/spdm/req-sysfs.c
index afba3c5a2e8f..d3c4ca7dbbaa 100644
--- a/lib/spdm/req-sysfs.c
+++ b/lib/spdm/req-sysfs.c
@@ -173,3 +173,336 @@ const struct attribute_group spdm_certificates_group = {
 	.bin_attrs = spdm_certificates_bin_attrs,
 	.is_bin_visible = spdm_certificates_are_visible,
 };
+
+/* signatures attributes */
+
+static struct bin_attribute *spdm_signatures_bin_attrs[] = {
+	NULL
+};
+
+const struct attribute_group spdm_signatures_group = {
+	.name = "signatures",
+	.bin_attrs = spdm_signatures_bin_attrs,
+};
+
+/**
+ * struct spdm_log_entry - log entry representing one received SPDM signature
+ *
+ * @list: List node.  Added to the @log list in struct spdm_state.
+ * @sig: sysfs attribute of received signature (located at end of transcript).
+ * @req_nonce: sysfs attribute of requester nonce (located within transcript).
+ * @rsp_nonce: sysfs attribute of responder nonce (located within transcript).
+ * @transcript: sysfs attribute of transcript (concatenation of all SPDM
+ *	messages exchanged during an authentication sequence) sans trailing
+ *	signature (to simplify signature verification by user space).
+ * @combined_prefix: sysfs attribute of combined_spdm_prefix
+ *	(SPDM 1.2.0 margin no 806, needed to verify signature).
+ * @spdm_context: sysfs attribute of spdm_context
+ *	(SPDM 1.2.0 margin no 803, needed to create combined_spdm_prefix).
+ * @hash_alg: sysfs attribute of hash algorithm (needed to verify signature).
+ * @sig_name: Name of @sig attribute (with prepended signature counter).
+ * @req_nonce_name: Name of @req_nonce attribute.
+ * @rsp_nonce_name: Name of @rsp_nonce attribute.
+ * @transcript_name: Name of @transcript attribute.
+ * @combined_prefix_name: Name of @combined_prefix attribute.
+ * @spdm_context_name: Name of @spdm_context attribute.
+ * @hash_alg_name: Name of @hash_alg attribute.
+ * @counter: Signature counter (needed to create certificate_chain symlink).
+ * @version: Negotiated SPDM version
+ *	(SPDM 1.2.0 margin no 803, needed to create combined_spdm_prefix).
+ * @slot: Slot which was used to generate the signature
+ *	(needed to create certificate_chain symlink).
+ */
+struct spdm_log_entry {
+	struct list_head list;
+	struct bin_attribute sig;
+	struct bin_attribute req_nonce;
+	struct bin_attribute rsp_nonce;
+	struct bin_attribute transcript;
+	struct bin_attribute combined_prefix;
+	struct dev_ext_attribute spdm_context;
+	struct dev_ext_attribute hash_alg;
+	char sig_name[sizeof(__stringify(UINT_MAX) "_signature")];
+	char req_nonce_name[sizeof(__stringify(UINT_MAX) "_requester_nonce")];
+	char rsp_nonce_name[sizeof(__stringify(UINT_MAX) "_responder_nonce")];
+	char transcript_name[sizeof(__stringify(UINT_MAX) "_transcript")];
+	char combined_prefix_name[sizeof(__stringify(UINT_MAX) "_combined_spdm_prefix")];
+	char spdm_context_name[sizeof(__stringify(UINT_MAX) "_type")];
+	char hash_alg_name[sizeof(__stringify(UINT_MAX) "_hash_algorithm")];
+	u32 counter;
+	u8 version;
+	u8 slot;
+};
+
+static void spdm_unpublish_log_entry(struct kobject *kobj,
+				     struct spdm_log_entry *log)
+{
+	const char *group = spdm_signatures_group.name;
+
+	sysfs_remove_bin_file_from_group(kobj, &log->sig, group);
+	sysfs_remove_bin_file_from_group(kobj, &log->req_nonce, group);
+	sysfs_remove_bin_file_from_group(kobj, &log->rsp_nonce, group);
+	sysfs_remove_bin_file_from_group(kobj, &log->transcript, group);
+	sysfs_remove_bin_file_from_group(kobj, &log->combined_prefix, group);
+	sysfs_remove_file_from_group(kobj, &log->spdm_context.attr.attr, group);
+	sysfs_remove_file_from_group(kobj, &log->hash_alg.attr.attr, group);
+
+	char cert_chain[sizeof(__stringify(UINT_MAX) "_certificate_chain")];
+	snprintf(cert_chain, sizeof(cert_chain), "%u_certificate_chain",
+		 log->counter);
+
+	sysfs_remove_link_from_group(kobj, group, cert_chain);
+}
+
+static void spdm_publish_log_entry(struct kobject *kobj,
+				   struct spdm_log_entry *log)
+{
+	const char *group = spdm_signatures_group.name;
+	int rc;
+
+	rc = sysfs_add_bin_file_to_group(kobj, &log->sig, group);
+	if (rc)
+		goto err;
+
+	rc = sysfs_add_bin_file_to_group(kobj, &log->req_nonce, group);
+	if (rc)
+		goto err;
+
+	rc = sysfs_add_bin_file_to_group(kobj, &log->rsp_nonce, group);
+	if (rc)
+		goto err;
+
+	rc = sysfs_add_bin_file_to_group(kobj, &log->transcript, group);
+	if (rc)
+		goto err;
+
+	rc = sysfs_add_bin_file_to_group(kobj, &log->combined_prefix, group);
+	if (rc)
+		goto err;
+
+	rc = sysfs_add_file_to_group(kobj, &log->spdm_context.attr.attr, group);
+	if (rc)
+		goto err;
+
+	rc = sysfs_add_file_to_group(kobj, &log->hash_alg.attr.attr, group);
+	if (rc)
+		goto err;
+
+	char cert_chain[sizeof(__stringify(UINT_MAX) "_certificate_chain")];
+	snprintf(cert_chain, sizeof(cert_chain), "%u_certificate_chain",
+		 log->counter);
+
+	char slot[sizeof("slot0")];
+	snprintf(slot, sizeof(slot), "slot%hhu", log->slot);
+
+	rc = sysfs_add_link_to_sibling_group(kobj, group, cert_chain,
+					     spdm_certificates_group.name,
+					     slot);
+	if (rc)
+		goto err;
+
+	return;
+
+err:
+	dev_err(kobj_to_dev(kobj),
+		"Failed to publish signature log entry in sysfs: %d\n", rc);
+	spdm_unpublish_log_entry(kobj, log);
+}
+
+static ssize_t spdm_read_combined_prefix(struct file *file,
+					 struct kobject *kobj,
+					 struct bin_attribute *attr,
+					 char *buf, loff_t off, size_t count)
+{
+	struct spdm_log_entry *log = attr->private;
+
+	/*
+	 * SPDM 1.0 and 1.1 do not add a combined prefix to the hash
+	 * before computing the signature, so return an empty file.
+	 */
+	if (log->version <= 0x11)
+		return 0;
+
+	void *tmp __free(kfree) = kmalloc(SPDM_COMBINED_PREFIX_SZ, GFP_KERNEL);
+	if (!tmp)
+		return -ENOMEM;
+
+	spdm_create_combined_prefix(log->version, log->spdm_context.var, tmp);
+	memcpy(buf, tmp + off, count);
+	return count;
+}
+
+static void spdm_destroy_log_entry(struct spdm_log_entry *log)
+{
+	list_del(&log->list);
+	kvfree(log->transcript.private);
+	kfree(log);
+}
+
+/**
+ * spdm_create_log_entry() - Allocate log entry for one received SPDM signature
+ *
+ * @spdm_state: SPDM session state
+ * @spdm_context: SPDM context (needed to create combined_spdm_prefix)
+ * @slot: Slot which was used to generate the signature
+ *	(needed to create certificate_chain symlink)
+ * @req_nonce_off: Requester nonce offset within the transcript
+ * @rsp_nonce_off: Responder nonce offset within the transcript
+ *
+ * Allocate and populate a struct spdm_log_entry upon device authentication.
+ * Publish it in sysfs if the device has already been registered through
+ * device_add().
+ */
+void spdm_create_log_entry(struct spdm_state *spdm_state,
+			   const char *spdm_context, u8 slot,
+			   size_t req_nonce_off, size_t rsp_nonce_off)
+{
+	struct spdm_log_entry *log = kmalloc(sizeof(*log), GFP_KERNEL);
+	if (!log)
+		return;
+
+	*log = (struct spdm_log_entry) {
+		.slot		   = slot,
+		.version	   = spdm_state->version,
+		.counter	   = spdm_state->log_counter,
+		.list		   = LIST_HEAD_INIT(log->list),
+
+		.sig = {
+			.attr.name = log->sig_name,
+			.attr.mode = 0444,
+			.read	   = sysfs_bin_attr_simple_read,
+			.private   = spdm_state->transcript_end -
+				     spdm_state->sig_len,
+			.size	   = spdm_state->sig_len },
+
+		.req_nonce = {
+			.attr.name = log->req_nonce_name,
+			.attr.mode = 0444,
+			.read	   = sysfs_bin_attr_simple_read,
+			.private   = spdm_state->transcript + req_nonce_off,
+			.size	   = SPDM_NONCE_SZ },
+
+		.rsp_nonce = {
+			.attr.name = log->rsp_nonce_name,
+			.attr.mode = 0444,
+			.read	   = sysfs_bin_attr_simple_read,
+			.private   = spdm_state->transcript + rsp_nonce_off,
+			.size	   = SPDM_NONCE_SZ },
+
+		.transcript = {
+			.attr.name = log->transcript_name,
+			.attr.mode = 0444,
+			.read	   = sysfs_bin_attr_simple_read,
+			.private   = spdm_state->transcript,
+			.size	   = spdm_state->transcript_end -
+				     spdm_state->transcript -
+				     spdm_state->sig_len },
+
+		.combined_prefix = {
+			.attr.name = log->combined_prefix_name,
+			.attr.mode = 0444,
+			.read	   = spdm_read_combined_prefix,
+			.private   = log,
+			.size	   = spdm_state->version <= 0x11 ? 0 :
+				     SPDM_COMBINED_PREFIX_SZ },
+
+		.spdm_context = {
+			.attr.attr.name = log->spdm_context_name,
+			.attr.attr.mode = 0444,
+			.attr.show = device_show_string,
+			.var	   = (char *)spdm_context },
+
+		.hash_alg = {
+			.attr.attr.name = log->hash_alg_name,
+			.attr.attr.mode = 0444,
+			.attr.show = device_show_string,
+			.var	   = (char *)spdm_state->base_hash_alg_name },
+	};
+
+	snprintf(log->sig_name, sizeof(log->sig_name),
+		 "%u_signature", spdm_state->log_counter);
+	snprintf(log->req_nonce_name, sizeof(log->req_nonce_name),
+		 "%u_requester_nonce", spdm_state->log_counter);
+	snprintf(log->rsp_nonce_name, sizeof(log->rsp_nonce_name),
+		 "%u_responder_nonce", spdm_state->log_counter);
+	snprintf(log->transcript_name, sizeof(log->transcript_name),
+		 "%u_transcript", spdm_state->log_counter);
+	snprintf(log->combined_prefix_name, sizeof(log->combined_prefix_name),
+		 "%u_combined_spdm_prefix", spdm_state->log_counter);
+	snprintf(log->spdm_context_name, sizeof(log->spdm_context_name),
+		 "%u_type", spdm_state->log_counter);
+	snprintf(log->hash_alg_name, sizeof(log->hash_alg_name),
+		 "%u_hash_algorithm", spdm_state->log_counter);
+
+	sysfs_bin_attr_init(&log->sig);
+	sysfs_bin_attr_init(&log->req_nonce);
+	sysfs_bin_attr_init(&log->rsp_nonce);
+	sysfs_bin_attr_init(&log->transcript);
+	sysfs_bin_attr_init(&log->combined_prefix);
+	sysfs_attr_init(&log->spdm_context.attr.attr);
+	sysfs_attr_init(&log->hash_alg.attr.attr);
+
+	list_add_tail(&log->list, &spdm_state->log);
+	spdm_state->log_counter++;
+
+	/* Steal transcript pointer ahead of spdm_free_transcript() */
+	spdm_state->transcript = NULL;
+
+	if (device_is_registered(spdm_state->dev))
+		spdm_publish_log_entry(&spdm_state->dev->kobj, log);
+}
+
+/**
+ * spdm_publish_log() - Publish log of received SPDM signatures in sysfs
+ *
+ * @spdm_state: SPDM session state
+ *
+ * sysfs attributes representing received SPDM signatures are not static,
+ * but created dynamically upon authentication.  If a device was authenticated
+ * before it became visible in sysfs, the attributes could not be created.
+ * This function retroactively creates those attributes in sysfs after the
+ * device has become visible through device_add().
+ */
+void spdm_publish_log(struct spdm_state *spdm_state)
+{
+	struct kobject *kobj = &spdm_state->dev->kobj;
+	struct kernfs_node *grp_kn __free(kernfs_put);
+	struct spdm_log_entry *log;
+
+	grp_kn = kernfs_find_and_get(kobj->sd, spdm_signatures_group.name);
+	if (WARN_ON(!grp_kn))
+		return;
+
+	mutex_lock(&spdm_state->lock);
+	list_for_each_entry(log, &spdm_state->log, list) {
+		struct kernfs_node *sig_kn __free(kernfs_put);
+
+		/*
+		 * Skip over log entries created in-between device_add() and
+		 * spdm_publish_log() as they've already been published.
+		 */
+		sig_kn = kernfs_find_and_get(grp_kn, log->sig_name);
+		if (sig_kn)
+			continue;
+
+		spdm_publish_log_entry(kobj, log);
+	}
+	mutex_unlock(&spdm_state->lock);
+}
+EXPORT_SYMBOL_GPL(spdm_publish_log);
+
+/**
+ * spdm_destroy_log() - Destroy log of received SPDM signatures
+ *
+ * @spdm_state: SPDM session state
+ *
+ * Be sure to unregister the device through device_del() beforehand,
+ * which implicitly unpublishes the log in sysfs.
+ */
+void spdm_destroy_log(struct spdm_state *spdm_state)
+{
+	struct spdm_log_entry *log, *tmp;
+
+	list_for_each_entry_safe(log, tmp, &spdm_state->log, list)
+		spdm_destroy_log_entry(log);
+}
diff --git a/lib/spdm/spdm.h b/lib/spdm/spdm.h
index 6c426b2be372..a63c2922af5d 100644
--- a/lib/spdm/spdm.h
+++ b/lib/spdm/spdm.h
@@ -466,6 +466,10 @@ struct spdm_error_rsp {
  *	end of transcript.  If another message is transmitted, it is appended
  *	at this position.
  * @transcript_max: Allocation size of @transcript.  Multiple of PAGE_SIZE.
+ * @log: Linked list of past authentication events.  Each list entry is of type
+ *	struct spdm_log_entry and is exposed as several files in sysfs.
+ * @log_counter: Number of generated log entries so far.  Will be prefixed to
+ *	the sysfs files of the next generated log entry.
  */
 struct spdm_state {
 	struct device *dev;
@@ -506,6 +510,10 @@ struct spdm_state {
 	void *transcript;
 	void *transcript_end;
 	size_t transcript_max;
+
+	/* Signatures Log */
+	struct list_head log;
+	u32 log_counter;
 };
 
 ssize_t spdm_exchange(struct spdm_state *spdm_state,
@@ -523,4 +531,16 @@ int spdm_verify_signature(struct spdm_state *spdm_state,
 
 void spdm_reset(struct spdm_state *spdm_state);
 
+#ifdef CONFIG_SYSFS
+void spdm_create_log_entry(struct spdm_state *spdm_state,
+			   const char *spdm_context, u8 slot,
+			   size_t req_nonce_off, size_t rsp_nonce_off);
+void spdm_destroy_log(struct spdm_state *spdm_state);
+#else
+static inline void spdm_create_log_entry(struct spdm_state *spdm_state,
+			   const char *spdm_context, u8 slot,
+			   size_t req_nonce_off, size_t rsp_nonce_off) { }
+static inline void spdm_destroy_log(struct spdm_state *spdm_state) { }
+#endif
+
 #endif /* _LIB_SPDM_H_ */

---

## [17] Lukas Wunner — 2024-06-30
*Subject: [PATCH v2 16/18] spdm: Limit memory consumed by log of received
 signatures*

The SPDM library has just been amended to keep a log of received
signatures and expose it in sysfs.

Limit the log's memory footprint subject to a sysctl parameter.  Purge
old signatures when adding a new signature which causes the limit to be
exceeded.  Likewise purge old signatures when the sysctl parameter is
reduced.

The latter requires keeping a list of all struct spdm_state and
protecting it with a mutex.  It will come in handy when further global
sysctl parameters are added to the SPDM library.  Unfortunately an
xarray is not a better option in this case as the xarray-integrated
xa_lock() is a spinlock but purging signatures from sysfs may sleep
(due to kernfs_rwsem).

This functionality is introduced in a separate commit on top of basic
signature exposure to split the code into digestible, reviewable chunks.

Signed-off-by: Lukas Wunner <lukas@wunner.de>
---
 Documentation/ABI/testing/sysfs-devices-spdm | 15 ++++
 Documentation/admin-guide/sysctl/index.rst   |  2 +
 Documentation/admin-guide/sysctl/spdm.rst    | 33 ++++++++
 MAINTAINERS                                  |  1 +
 lib/spdm/core.c                              | 11 +++
 lib/spdm/req-sysfs.c                         | 80 +++++++++++++++++++-
 lib/spdm/spdm.h                              | 10 +++
 7 files changed, 150 insertions(+), 2 deletions(-)
 create mode 100644 Documentation/admin-guide/sysctl/spdm.rst

diff --git a/Documentation/ABI/testing/sysfs-devices-spdm b/Documentation/ABI/testing/sysfs-devices-spdm
index ae7b3f701ded..8d8ee01672e1 100644
--- a/Documentation/ABI/testing/sysfs-devices-spdm
+++ b/Documentation/ABI/testing/sysfs-devices-spdm
@@ -162,6 +162,21 @@ Description:
 		dissector needs to be fed the concatenation of "transcript"
 		and "signature".
 
+		Because the number prefixed to the filenames is 32 bit, it
+		wraps around to 0 after 4,294,967,295 signatures.  The kernel
+		avoids filename collisions on wraparound by purging old files,
+		subject to the limit set by "sysctl spdm.max_signatures_size"
+		(which defaults to 16 MiB).  It is advisable to regularly save
+		backups on non-volatile storage to retain access to signatures
+		that have been purged (or across reboots)::
+
+		 # tar -u -h -f /path/to/signatures.tar signatures/
+
+		The ctime of each file is the reception time of the signature.
+		However if the signature was received before the device became
+		registered in sysfs, the ctime is the registration time of the
+		device.
+
 
 What:		/sys/devices/.../signatures/[0-9]*_type
 Date:		June 2024
diff --git a/Documentation/admin-guide/sysctl/index.rst b/Documentation/admin-guide/sysctl/index.rst
index 03346f98c7b9..3b48f0039069 100644
--- a/Documentation/admin-guide/sysctl/index.rst
+++ b/Documentation/admin-guide/sysctl/index.rst
@@ -76,6 +76,7 @@ kernel/		global kernel info / tuning
 net/		networking stuff, for documentation look in:
 		<Documentation/networking/>
 proc/		<empty>
+spdm/		Security Protocol and Data Model (SPDM)
 sunrpc/		SUN Remote Procedure Call (NFS)
 vm/		memory management tuning
 		buffer and cache management
@@ -93,6 +94,7 @@ really like to hear about it :-)
    fs
    kernel
    net
+   spdm
    sunrpc
    user
    vm
diff --git a/Documentation/admin-guide/sysctl/spdm.rst b/Documentation/admin-guide/sysctl/spdm.rst
new file mode 100644
index 000000000000..0f3846c83cd4
--- /dev/null
+++ b/Documentation/admin-guide/sysctl/spdm.rst
@@ -0,0 +1,33 @@
+.. SPDX-License-Identifier: GPL-2.0
+
+=================================
+Documentation for /proc/sys/spdm/
+=================================
+
+Copyright (C) 2024 Intel Corporation
+
+This directory allows tuning Security Protocol and Data Model (SPDM)
+parameters.  SPDM enables device authentication, measurement, key
+exchange and encrypted sessions.
+
+max_signatures_size
+===================
+
+Maximum amount of memory occupied by the log of signatures (per device,
+in bytes, 16 MiB by default).
+
+The log is meant for re-verification of signatures by remote attestation
+services which do not trust the kernel to have verified the signatures
+correctly or which want to apply policy constraints of their own.
+A signature is computed over the transcript (a concatenation of all
+SPDM messages exchanged with the device during an authentication
+sequence).  The transcript can be a few kBytes or up to several MBytes
+in size, hence this parameter prevents the log from consuming too much
+memory.
+
+The kernel always stores the most recent signature in the log even if it
+exceeds ``max_signatures_size``.  Additionally as many older signatures
+are kept in the log as this limit allows.
+
+If you reduce the limit, signatures are purged immediately to free up
+memory.
diff --git a/MAINTAINERS b/MAINTAINERS
index 1ed5817e698c..41f35bbb8f1a 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -20154,6 +20154,7 @@ L:	linux-pci@vger.kernel.org
 S:	Maintained
 T:	git git://git.kernel.org/pub/scm/linux/kernel/git/devsec/spdm.git
 F:	Documentation/ABI/testing/sysfs-devices-spdm
+F:	Documentation/admin-guide/sysctl/spdm.rst
 F:	drivers/pci/cma*
 F:	include/linux/spdm.h
 F:	lib/spdm/
diff --git a/lib/spdm/core.c b/lib/spdm/core.c
index d962a1344760..b6a46bdbb2f9 100644
--- a/lib/spdm/core.c
+++ b/lib/spdm/core.c
@@ -20,6 +20,9 @@
 #include <crypto/hash.h>
 #include <crypto/public_key.h>
 
+LIST_HEAD(spdm_state_list); /* list of all struct spdm_state */
+DEFINE_MUTEX(spdm_state_mutex); /* protects spdm_state_list */
+
 static int spdm_err(struct device *dev, struct spdm_error_rsp *rsp)
 {
 	switch (rsp->error_code) {
@@ -404,6 +407,10 @@ struct spdm_state *spdm_create(struct device *dev, spdm_transport *transport,
 	mutex_init(&spdm_state->lock);
 	INIT_LIST_HEAD(&spdm_state->log);
 
+	mutex_lock(&spdm_state_mutex);
+	list_add_tail(&spdm_state->list, &spdm_state_list);
+	mutex_unlock(&spdm_state_mutex);
+
 	return spdm_state;
 }
 EXPORT_SYMBOL_GPL(spdm_create);
@@ -417,6 +424,10 @@ void spdm_destroy(struct spdm_state *spdm_state)
 {
 	u8 slot;
 
+	mutex_lock(&spdm_state_mutex);
+	list_del(&spdm_state->list);
+	mutex_unlock(&spdm_state_mutex);
+
 	for_each_set_bit(slot, &spdm_state->provisioned_slots, SPDM_SLOTS)
 		kvfree(spdm_state->slot[slot]);
 
diff --git a/lib/spdm/req-sysfs.c b/lib/spdm/req-sysfs.c
index d3c4ca7dbbaa..c782054f8e18 100644
--- a/lib/spdm/req-sysfs.c
+++ b/lib/spdm/req-sysfs.c
@@ -185,6 +185,8 @@ const struct attribute_group spdm_signatures_group = {
 	.bin_attrs = spdm_signatures_bin_attrs,
 };
 
+static unsigned int spdm_max_log_sz = SZ_16M; /* per device */
+
 /**
  * struct spdm_log_entry - log entry representing one received SPDM signature
  *
@@ -332,13 +334,31 @@ static ssize_t spdm_read_combined_prefix(struct file *file,
 	return count;
 }
 
-static void spdm_destroy_log_entry(struct spdm_log_entry *log)
+static void spdm_destroy_log_entry(struct spdm_state *spdm_state,
+				   struct spdm_log_entry *log)
 {
+	spdm_state->log_sz -= log->transcript.size + log->sig.size +
+			      sizeof(*log);
+
 	list_del(&log->list);
 	kvfree(log->transcript.private);
 	kfree(log);
 }
 
+static void spdm_shrink_log(struct spdm_state *spdm_state)
+{
+	while (spdm_state->log_sz > spdm_max_log_sz &&
+	       !list_is_singular(&spdm_state->log)) {
+		struct spdm_log_entry *log =
+			list_first_entry(&spdm_state->log, typeof(*log), list);
+
+		if (device_is_registered(spdm_state->dev))
+			spdm_unpublish_log_entry(&spdm_state->dev->kobj, log);
+
+		spdm_destroy_log_entry(spdm_state, log);
+	}
+}
+
 /**
  * spdm_create_log_entry() - Allocate log entry for one received SPDM signature
  *
@@ -444,6 +464,11 @@ void spdm_create_log_entry(struct spdm_state *spdm_state,
 
 	list_add_tail(&log->list, &spdm_state->log);
 	spdm_state->log_counter++;
+	spdm_state->log_sz += log->transcript.size + log->sig.size +
+			      sizeof(*log);
+
+	/* Purge oldest log entries if max log size is exceeded */
+	spdm_shrink_log(spdm_state);
 
 	/* Steal transcript pointer ahead of spdm_free_transcript() */
 	spdm_state->transcript = NULL;
@@ -504,5 +529,56 @@ void spdm_destroy_log(struct spdm_state *spdm_state)
 	struct spdm_log_entry *log, *tmp;
 
 	list_for_each_entry_safe(log, tmp, &spdm_state->log, list)
-		spdm_destroy_log_entry(log);
+		spdm_destroy_log_entry(spdm_state, log);
+}
+
+#ifdef CONFIG_SYSCTL
+static int proc_max_log_sz(struct ctl_table *table, int write,
+			   void *buffer, size_t *lenp, loff_t *ppos)
+{
+	unsigned int old_max_log_sz = spdm_max_log_sz;
+	struct spdm_state *spdm_state;
+	int rc;
+
+	rc = proc_douintvec_minmax(table, write, buffer, lenp, ppos);
+	if (rc)
+		return rc;
+
+	/* Purge oldest log entries if max log size has been reduced */
+	if (write && spdm_max_log_sz < old_max_log_sz) {
+		mutex_lock(&spdm_state_mutex);
+		list_for_each_entry(spdm_state, &spdm_state_list, list) {
+			mutex_lock(&spdm_state->lock);
+			spdm_shrink_log(spdm_state);
+			mutex_unlock(&spdm_state->lock);
+		}
+		mutex_unlock(&spdm_state_mutex);
+	}
+
+	return 0;
+}
+
+static struct ctl_table spdm_ctl_table[] = {
+	{
+		.procname	= "max_signatures_size",
+		.data		= &spdm_max_log_sz,
+		.maxlen		= sizeof(spdm_max_log_sz),
+		.mode		= 0644,
+		.proc_handler	= proc_max_log_sz,
+		.extra1		= SYSCTL_ZERO,
+				  /*
+				   * 2 GiB limit avoids filename collision on
+				   * wraparound of unsigned 32-bit log_counter
+				   */
+		.extra2		= SYSCTL_INT_MAX,
+	},
+	{ }
+};
+
+static int __init spdm_init(void)
+{
+	register_sysctl_init("spdm", spdm_ctl_table);
+	return 0;
 }
+fs_initcall(spdm_init);
+#endif /* CONFIG_SYSCTL */
diff --git a/lib/spdm/spdm.h b/lib/spdm/spdm.h
index a63c2922af5d..448107c92db7 100644
--- a/lib/spdm/spdm.h
+++ b/lib/spdm/spdm.h
@@ -420,6 +420,8 @@ struct spdm_error_rsp {
  * @dev: Responder device.  Used for error reporting and passed to @transport.
  *	Attributes in sysfs appear below this device's directory.
  * @lock: Serializes multiple concurrent spdm_authenticate() calls.
+ * @list: List node.  Added to spdm_state_list.  Used to iterate over all
+ *	SPDM-capable devices when a global sysctl parameter is changed.
  * @authenticated: Whether device was authenticated successfully.
  * @dev: Responder device.  Used for error reporting and passed to @transport.
  * @transport: Transport function to perform one message exchange.
@@ -468,12 +470,16 @@ struct spdm_error_rsp {
  * @transcript_max: Allocation size of @transcript.  Multiple of PAGE_SIZE.
  * @log: Linked list of past authentication events.  Each list entry is of type
  *	struct spdm_log_entry and is exposed as several files in sysfs.
+ * @log_sz: Memory occupied by @log (in bytes) to enforce the limit set by
+ *	spdm_max_log_sz.  Includes, for every entry, the struct spdm_log_entry
+ *	itself and the transcript with trailing signature.
  * @log_counter: Number of generated log entries so far.  Will be prefixed to
  *	the sysfs files of the next generated log entry.
  */
 struct spdm_state {
 	struct device *dev;
 	struct mutex lock;
+	struct list_head list;
 	unsigned int authenticated:1;
 
 	/* Transport */
@@ -513,9 +519,13 @@ struct spdm_state {
 
 	/* Signatures Log */
 	struct list_head log;
+	size_t log_sz;
 	u32 log_counter;
 };
 
+extern struct list_head spdm_state_list;
+extern struct mutex spdm_state_mutex;
+
 ssize_t spdm_exchange(struct spdm_state *spdm_state,
 		      void *req, size_t req_sz, void *rsp, size_t rsp_sz);

---

## [18] Lukas Wunner — 2024-06-30
*Subject: [PATCH v2 17/18] spdm: Authenticate devices despite invalid
 certificate chain*

The SPDM library has just been amended to keep a log of received
signatures from a device and expose it in sysfs.

Currently challenge-response authentication with a device is only
performed if one of its up to 8 certificate chains is considered valid
by the kernel.

Valid means several things:

* That the certificate chain adheres to requirements in the SPDM
  specification (e.g. each certificate in the chain is signed by the
  preceding certificate),
* that the certificate chain adheres to requirements in other
  specifications such as PCIe r6.1 sec 6.31.3,
* that the first certificate in the chain is signed by a trusted root
  certificate on the kernel's keyring
* or that none of the certificates in the chain is on the kernel's
  blacklist_keyring.

User space should be given the chance to make up its own mind on the
validity of a certificate chain and the signature generated with it.
So if none of the 8 certificate chains is considered valid by the
kernel, pick one of them and perform challenge-response authentication
with it for the sole purpose of exposing a signature to user space.

Do not verify that signature because if the kernel considers the
certificate chain invalid, the signature implicitly is as well.

Arbitrarily select the certificate chain in the first provisioned slot
(which is normally slot 0) for such "for user space only" authentication
attempts.

Signed-off-by: Lukas Wunner <lukas@wunner.de>
---
I'd like to know whether people actually find this feature useful.
The patch is somewhat tentative and I may drop it if there is no interest,
so comments welcome!

 Documentation/ABI/testing/sysfs-devices-spdm |  5 +++
 lib/spdm/req-authenticate.c                  | 38 +++++++++++++-------
 2 files changed, 31 insertions(+), 12 deletions(-)

diff --git a/Documentation/ABI/testing/sysfs-devices-spdm b/Documentation/ABI/testing/sysfs-devices-spdm
index 8d8ee01672e1..5ce34ce10b9c 100644
--- a/Documentation/ABI/testing/sysfs-devices-spdm
+++ b/Documentation/ABI/testing/sysfs-devices-spdm
@@ -162,6 +162,11 @@ Description:
 		dissector needs to be fed the concatenation of "transcript"
 		and "signature".
 
+		Signatures are added to the log even if the kernel was unable
+		to verify them (e.g. due to a missing trusted root certificate
+		or forged signature).  Thereby, remote attestation services
+		may make up their own mind on the signature's validity.
+
 		Because the number prefixed to the filenames is 32 bit, it
 		wraps around to 0 after 4,294,967,295 signatures.  The kernel
 		avoids filename collisions on wraparound by purging old files,
diff --git a/lib/spdm/req-authenticate.c b/lib/spdm/req-authenticate.c
index 0c74dc0e5cf4..7c977f5835c1 100644
--- a/lib/spdm/req-authenticate.c
+++ b/lib/spdm/req-authenticate.c
@@ -615,7 +615,7 @@ static size_t spdm_challenge_rsp_sz(struct spdm_state *spdm_state,
 	return  size  + spdm_state->sig_len;	/* Signature */
 }
 
-static int spdm_challenge(struct spdm_state *spdm_state, u8 slot)
+static int spdm_challenge(struct spdm_state *spdm_state, u8 slot, bool verify)
 {
 	size_t req_sz, rsp_sz, rsp_sz_max, req_nonce_off, rsp_nonce_off;
 	struct spdm_challenge_rsp *rsp __free(kfree);
@@ -661,14 +661,19 @@ static int spdm_challenge(struct spdm_state *spdm_state, u8 slot)
 	if (rc)
 		return rc;
 
-	/* Verify signature at end of transcript against leaf key */
-	rc = spdm_verify_signature(spdm_state, spdm_context);
-	if (rc)
-		dev_err(spdm_state->dev,
-			"Cannot verify challenge_auth signature: %d\n", rc);
-	else
-		dev_info(spdm_state->dev,
-			 "Authenticated with certificate slot %u\n", slot);
+	rc = -EKEYREJECTED;
+	if (verify) {
+		/* Verify signature at end of transcript against leaf key */
+		rc = spdm_verify_signature(spdm_state, spdm_context);
+		if (rc)
+			dev_err(spdm_state->dev,
+				"Cannot verify challenge_auth signature: %d\n",
+				rc);
+		else
+			dev_info(spdm_state->dev,
+				 "Authenticated with certificate slot %u\n",
+				 slot);
+	}
 
 	spdm_create_log_entry(spdm_state, spdm_context, slot,
 			      req_nonce_off, rsp_nonce_off);
@@ -692,6 +697,7 @@ static int spdm_challenge(struct spdm_state *spdm_state, u8 slot)
  */
 int spdm_authenticate(struct spdm_state *spdm_state)
 {
+	bool verify = false;
 	u8 slot;
 	int rc;
 
@@ -726,13 +732,21 @@ int spdm_authenticate(struct spdm_state *spdm_state)
 
 	for_each_set_bit(slot, &spdm_state->provisioned_slots, SPDM_SLOTS) {
 		rc = spdm_validate_cert_chain(spdm_state, slot);
-		if (rc == 0)
+		if (rc == 0) {
+			verify = true;
 			break;
+		}
 	}
+
+	/*
+	 * If no cert chain validates, perform challenge-response with
+	 * arbitrary slot to be able to expose a signature in sysfs
+	 * about which user space can make up its own mind.
+	 */
 	if (rc)
-		goto unlock;
+		slot = __ffs(spdm_state->provisioned_slots);
 
-	rc = spdm_challenge(spdm_state, slot);
+	rc = spdm_challenge(spdm_state, slot, verify);
 
 unlock:
 	if (rc)

---

## [19] Lukas Wunner — 2024-06-30
*Subject: [PATCH v2 18/18] spdm: Allow control of next requester nonce through
 sysfs*

Remote attestation services may mistrust the kernel to always use a
fresh nonce for SPDM authentication.

So allow user space to set the next requester nonce by writing to a
sysfs attribute.

Signed-off-by: Lukas Wunner <lukas@wunner.de>
Cc: James Bottomley <James.Bottomley@HansenPartnership.com>
Cc: Jérôme Glisse <jglisse@google.com>
Cc: Jason Gunthorpe <jgg@nvidia.com>
---
 Documentation/ABI/testing/sysfs-devices-spdm | 29 ++++++++++++++++
 lib/spdm/core.c                              |  1 +
 lib/spdm/req-authenticate.c                  |  8 ++++-
 lib/spdm/req-sysfs.c                         | 35 ++++++++++++++++++++
 lib/spdm/spdm.h                              |  4 +++
 5 files changed, 76 insertions(+), 1 deletion(-)

diff --git a/Documentation/ABI/testing/sysfs-devices-spdm b/Documentation/ABI/testing/sysfs-devices-spdm
index 5ce34ce10b9c..d315b47b4af0 100644
--- a/Documentation/ABI/testing/sysfs-devices-spdm
+++ b/Documentation/ABI/testing/sysfs-devices-spdm
@@ -216,3 +216,32 @@ Description:
 		necessary to parse the SPDM messages in the transcript to find
 		and extract the nonces, which is cumbersome.  That's why they
 		are exposed as separate files.
+
+
+What:		/sys/devices/.../signatures/next_requester_nonce
+Date:		June 2024
+Contact:	Lukas Wunner <lukas@wunner.de>
+Description:
+		If you do not trust the kernel to always use a fresh nonce,
+		write 32 bytes to this file to set the requester nonce used
+		in the next SPDM authentication sequence.
+
+		Meant for remote attestation services.  You are responsible
+		for providing a nonce with sufficient entropy.  The kernel
+		only uses the nonce once, so provide a new one every time
+		you reauthenticate the device.  If you do not provide a
+		nonce, the kernel generates a random one.
+
+		After the nonce has been consumed, it becomes readable as
+		the newest [0-9]*_requester_nonce, which proves its usage::
+
+		 # dd if=/dev/random bs=32 count=1 | \
+		   tee signatures/next_requester_nonce | hexdump
+		 0000000 e0 77 91 54 bd 56 99 c2 ea 4f 0b 1a 7f ba 6e 59
+		 0000010 8f ee f6 b2 26 82 58 34 9e e5 8c 8a 31 58 29 7e
+
+		 # echo re > authenticated
+
+		 # hexdump $(\ls -t signatures/[0-9]*_requester_nonce | head -1)
+		 0000000 e0 77 91 54 bd 56 99 c2 ea 4f 0b 1a 7f ba 6e 59
+		 0000010 8f ee f6 b2 26 82 58 34 9e e5 8c 8a 31 58 29 7e
diff --git a/lib/spdm/core.c b/lib/spdm/core.c
index b6a46bdbb2f9..7371adb7a52f 100644
--- a/lib/spdm/core.c
+++ b/lib/spdm/core.c
@@ -434,6 +434,7 @@ void spdm_destroy(struct spdm_state *spdm_state)
 	spdm_reset(spdm_state);
 	spdm_destroy_log(spdm_state);
 	mutex_destroy(&spdm_state->lock);
+	kfree(spdm_state->next_nonce);
 	kfree(spdm_state);
 }
 EXPORT_SYMBOL_GPL(spdm_destroy);
diff --git a/lib/spdm/req-authenticate.c b/lib/spdm/req-authenticate.c
index 7c977f5835c1..489fc88de74d 100644
--- a/lib/spdm/req-authenticate.c
+++ b/lib/spdm/req-authenticate.c
@@ -626,7 +626,13 @@ static int spdm_challenge(struct spdm_state *spdm_state, u8 slot, bool verify)
 	};
 	int rc, length;
 
-	get_random_bytes(&req.nonce, sizeof(req.nonce));
+	if (spdm_state->next_nonce) {
+		memcpy(&req.nonce, spdm_state->next_nonce, sizeof(req.nonce));
+		kfree(spdm_state->next_nonce);
+		spdm_state->next_nonce = NULL;
+	} else {
+		get_random_bytes(&req.nonce, sizeof(req.nonce));
+	}
 
 	if (spdm_state->version <= 0x12)
 		req_sz = offsetofend(typeof(req), nonce);
diff --git a/lib/spdm/req-sysfs.c b/lib/spdm/req-sysfs.c
index c782054f8e18..232d4a00a510 100644
--- a/lib/spdm/req-sysfs.c
+++ b/lib/spdm/req-sysfs.c
@@ -176,13 +176,48 @@ const struct attribute_group spdm_certificates_group = {
 
 /* signatures attributes */
 
+static umode_t spdm_signatures_are_visible(struct kobject *kobj,
+					   struct bin_attribute *a, int n)
+{
+	struct device *dev = kobj_to_dev(kobj);
+	struct spdm_state *spdm_state = dev_to_spdm_state(dev);
+
+	if (IS_ERR_OR_NULL(spdm_state))
+		return SYSFS_GROUP_INVISIBLE;
+
+	return a->attr.mode;
+}
+
+static ssize_t next_requester_nonce_write(struct file *file,
+					  struct kobject *kobj,
+					  struct bin_attribute *attr,
+					  char *buf, loff_t off, size_t count)
+{
+	struct device *dev = kobj_to_dev(kobj);
+	struct spdm_state *spdm_state = dev_to_spdm_state(dev);
+
+	guard(mutex)(&spdm_state->lock);
+
+	if (!spdm_state->next_nonce) {
+		spdm_state->next_nonce = kmalloc(SPDM_NONCE_SZ, GFP_KERNEL);
+		if (!spdm_state->next_nonce)
+			return -ENOMEM;
+	}
+
+	memcpy(spdm_state->next_nonce + off, buf, count);
+	return count;
+}
+static BIN_ATTR_WO(next_requester_nonce, SPDM_NONCE_SZ);
+
 static struct bin_attribute *spdm_signatures_bin_attrs[] = {
+	&bin_attr_next_requester_nonce,
 	NULL
 };
 
 const struct attribute_group spdm_signatures_group = {
 	.name = "signatures",
 	.bin_attrs = spdm_signatures_bin_attrs,
+	.is_bin_visible = spdm_signatures_are_visible,
 };
 
 static unsigned int spdm_max_log_sz = SZ_16M; /* per device */
diff --git a/lib/spdm/spdm.h b/lib/spdm/spdm.h
index 448107c92db7..aa36aa55e718 100644
--- a/lib/spdm/spdm.h
+++ b/lib/spdm/spdm.h
@@ -475,6 +475,9 @@ struct spdm_error_rsp {
  *	itself and the transcript with trailing signature.
  * @log_counter: Number of generated log entries so far.  Will be prefixed to
  *	the sysfs files of the next generated log entry.
+ * @next_nonce: Requester nonce to be used for the next authentication
+ *	sequence.  Populated from user space through sysfs.
+ *	If user space does not provide a nonce, the kernel uses a random one.
  */
 struct spdm_state {
 	struct device *dev;
@@ -521,6 +524,7 @@ struct spdm_state {
 	struct list_head log;
 	size_t log_sz;
 	u32 log_counter;
+	u8 *next_nonce;
 };
 
 extern struct list_head spdm_state_list;

---

## [20] Jeff Johnson — 2024-06-30
*Subject: Re: [PATCH v2 07/18] spdm: Introduce library to authenticate devices*

On 6/30/24 12:42, Lukas Wunner wrote:
> From: Jonathan Cameron <Jonathan.Cameron@huawei.com>
> 
...
> diff --git a/lib/spdm/core.c b/lib/spdm/core.c
> new file mode 100644
...
> +EXPORT_SYMBOL_GPL(spdm_destroy);
> +

missing MODULE_DESCRIPTION()
this will generate a warning when built as a module with make W=1

---

## [21] Herbert Xu — 2024-07-01
*Subject: Re: [PATCH v2 06/18] crypto: ecdsa - Support P1363 signature encoding*

On Sun, Jun 30, 2024 at 09:41:00PM +0200, Lukas Wunner wrote:
>
> diff --git a/crypto/ecdsa.c b/crypto/ecdsa.c

This should be implemented as a template.  Change ecdsa to use a
"raw" encoding for r/s and then implement x962 and p1363 as templates
which converts their respective encodings to the raw one.  You
would then use "x962(ecdsa-nist-XXX)" or "p1363(ecdsa-nist-XXX)"
to pick the encoding.

Cheers,

---

## [22] Greg Kroah-Hartman — 2024-07-04
*Subject: Re: [PATCH v2 13/18] sysfs: Allow bin_attributes to be added to
 groups*

On Sun, Jun 30, 2024 at 09:48:00PM +0200, Lukas Wunner wrote:
> Commit dfa87c824a9a ("sysfs: allow attributes to be added to groups")
> introduced dynamic addition of sysfs attributes to groups.

Acked-by: Greg Kroah-Hartman <gregkh@linuxfoundation.org>

---

## [23] Greg Kroah-Hartman — 2024-07-04
*Subject: Re: [PATCH v2 14/18] sysfs: Allow symlinks to be added between
 sibling groups*

On Sun, Jun 30, 2024 at 09:49:00PM +0200, Lukas Wunner wrote:
> A subsequent commit has the need to create a symlink from an attribute
> in a first group to an attribute in a second group.  Both groups belong

Nice!

> 
> Signed-off-by: Lukas Wunner <lukas@wunner.de>

Acked-by: Greg Kroah-Hartman <gregkh@linuxfoundation.org>

---

## [24] Alexey Kardashevskiy — 2024-07-08
*Subject: Re: [PATCH v2 00/18] PCI device authentication*

On 1/7/24 05:35, Lukas Wunner wrote:
> PCI device authentication v2
> 


What is it based on?
I am using https://github.com/l1k/linux.git branch cma_v2 for now but 
wonder if that's the right one. Thanks,

> 
> Five big changes since v1 (and many smaller ones, full list at end):

---

## [25] Alexey Kardashevskiy — 2024-07-08
*Subject: Re: [PATCH v2 07/18] spdm: Introduce library to authenticate devices*

On 1/7/24 05:42, Lukas Wunner wrote:
> From: Jonathan Cameron <Jonathan.Cameron@huawei.com>
> 

= and += in one statament just hurts to read but ok :)

> +
> +	rc = spdm_exchange(spdm_state, req, req_sz, rsp, rsp_sz);

rsp_sz is 36 bytes here. And spdm_exchange() cannot return more than 36 
because this is how pci_doe() works...

> +	if (rc < 0)
> +		return rc;

... but here you expect more than 36 as realistically rsp->param1 > 0.
How was this tested and what do I miss here? Thanks,



> +		return -EIO;
> +	}

---

## [26] Lukas Wunner — 2024-07-08
*Subject: Re: [PATCH v2 07/18] spdm: Introduce library to authenticate devices*

On Mon, Jul 08, 2024 at 07:57:02PM +1000, Alexey Kardashevskiy wrote:
> > +	rc = spdm_exchange(spdm_state, req, req_sz, rsp, rsp_sz);
> 

I assume you tested this patch set against a libspdm responder
and got a "Truncated algorithms response" error.

The short answer is, it's a bug in libspdm and the issue should
go away once you update libspdm to version 3.1.0 or newer.

If you need to stay at an older version, consider cherry-picking
libspdm commits 941f0ae0d24e ("libspdm_rsp_algorithms: fixup spec
conformance") and 065fb17b74c7 ("responder: negotiate algorithms
conformance").

The bug was found and fixed by Wilfred Mallawa when testing the
in-kernel SPDM implementation against libspdm:

https://github.com/l1k/linux/issues/3
https://github.com/DMTF/libspdm/pull/2341
https://github.com/DMTF/libspdm/issues/2344
https://github.com/DMTF/libspdm/pull/2353

Problem is, most SPDM-enabled products right now are based on
libspdm (the DMTF reference implementation) and thus are bug-by-bug
compatible.  However such a software monoculture is dangerous and
having a from-scratch kernel implementation has already proven useful
to identify issues like this which otherwise wouldn't have been noticed.

The in-kernel SPDM implementation currently doesn't send any
ReqAlgStructs and per the spec, the responder isn't supposed to
send any RespAlgStructs which the requester didn't ask for.
Yet libspdm always sent a hardcoded array of RespAlgStructs.

So the *reference* implementation wasn't conforming to the spec. :(

Thanks,

Lukas

---

## [27] Lukas Wunner — 2024-07-08
*Subject: Re: [PATCH v2 00/18] PCI device authentication*

On Mon, Jul 08, 2024 at 07:47:51PM +1000, Alexey Kardashevskiy wrote:
> On 1/7/24 05:35, Lukas Wunner wrote:
> > PCI device authentication v2

This series is based on v6.10-rc1.

I also successfully cherry-picked the patches onto v6.10-rc6 and
linux-next 20240628 (no merge conflicts and no issues reported by 0-day).

Older kernels than v6.10-rc1 won't work because they're missing
ecdsa-nist-p521 support as well as a few preparatory sysfs patches
of mine that went into v6.10-rc1.


> I am using https://github.com/l1k/linux.git branch cma_v2 for now but wonder
> if that's the right one.

Yes that's fine.

There's now also a kernel.org repository with a testing branch:

https://git.kernel.org/pub/scm/linux/kernel/git/devsec/spdm.git/

Future maintenance of the SPDM library is intended to be happening
in that repo.  I assumed that Bjorn may not be keen on having to
deal with SPDM patches forever, so creating a dedicated repo seemed
to make sense.

Most patches in this series with a "PCI/CMA: " subject actually
only change very few lines in the PCI core.  The bulk of the changes
is in the SPDM library instead.  I used that subject merely to
highlight that at least an ack from Bjorn is required.  The only
patches containing PCI core changes to speak of are patches 8, 9, 10.

The devsec group (short for Device Security Alphabet Soup) currently
only contains the spdm.git repo.  Going forward, further repos may be
added below the devsec umbrella, such as tsm.git to deal with a
vendor-neutral interface between kernel and Trusted Security Module.

Thanks,

Lukas

---

## [28] Alexey Kardashevskiy — 2024-07-09
*Subject: Re: [PATCH v2 07/18] spdm: Introduce library to authenticate devices*

On 8/7/24 22:54, Lukas Wunner wrote:
> On Mon, Jul 08, 2024 at 07:57:02PM +1000, Alexey Kardashevskiy wrote:
>>> +	rc = spdm_exchange(spdm_state, req, req_sz, rsp, rsp_sz);

It is against a device with libspdm in its firmware, likely to be older 
than 3.1.0.

> The short answer is, it's a bug in libspdm and the issue should
> go away once you update libspdm to version 3.1.0 or newer.

Easier to hack lib/spdm/req-authenticate.c just to see how far I can get 
with my device, now it is "Malformed certificate at slot 0 offset 0". It 
is just a bit inconvenient that CMA is not a module and requires the 
system reboot after every change.

> If you need to stay at an older version, consider cherry-picking
> libspdm commits 941f0ae0d24e ("libspdm_rsp_algorithms: fixup spec

True and a bit hilarious :)

> The in-kernel SPDM implementation currently doesn't send any
> ReqAlgStructs and per the spec, the responder isn't supposed to

Uff, I see. So it should probably be "Malformed algorithms response" 
(where param1 is actually checked) than "Truncated algorithms response", 
a minor detail though. Thanks for the explanation.

> So the *reference* implementation wasn't conforming to the spec. :(
>

---

## [29] Dan Williams — 2024-07-08
*Subject: Re: [PATCH v2 07/18] spdm: Introduce library to authenticate devices*

Lukas Wunner wrote:
> From: Jonathan Cameron <Jonathan.Cameron@huawei.com>
> 

Nice changelog.

> 
> Credits:  Jonathan wrote a proof-of-concept of this SPDM implementation.

I only have some quibbles below, but the broad strokes look good to me.

> 
> diff --git a/MAINTAINERS b/MAINTAINERS

This approach to error singnaling looks unprecedented, and not in a good
way. I like the idea of a SPDM-error-code to errno converter, and
separate SPDM-error-code to error string, but not an SPDM-error-code to
errno conversion that has a log emitting side effect.

Would this not emit ambiguous messages like:

    cxl_pci 0000:35:00.0: Unexpected request

How does I know that error message is from CXL SPDM functionality and
not some other part of the driver?

What if the SPDM authentication is optional, how does the consumer of
this library avoid log spam? What about rate limiting?

Did you consider leaving all error logging to the caller?

I have less problem if these all become dev_dbg() or tracepoints, but
dev_err() seems awkward.

> +{
> +	switch (rsp->error_code) {

What's the locking assumption with this public function? I see that the
internal to this file usages wrap it in the state lock. Should that
assumption be codified with a:

lockdep_assert_held(&spdm_state->lock)

?

Or can this function be marked static?

> +
> +	if (req_sz < sizeof(struct spdm_header) ||

Similar locking context with public functions concern, but also the
cleverness of why it is ok to not set ->transcript to NULL that really
only hold true if spdm_append_transcript() and and
spdm_free_transcript() are guaranteed to be serialized.

> +}
> +

Does this need a dynamic runtime check?

> +
> +	zero_pad = SPDM_COMBINED_PREFIX_SZ - SPDM_PREFIX_SZ - 1 - len;


Worth crashing the system here for panic_on_warn folks?

> +
> +	memset(buf + SPDM_PREFIX_SZ + 1, 0, zero_pad);

I am not a fan of forward declared scoped-based resource management
variables [1], although PeterZ never responded to those suggestions.

[1]: http://lore.kernel.org/171175585714.2192972.12661675876300167762.stgit@dwillia2-xfh.jf.intel.com

> +	if (!m)
> +		return -ENOMEM;
[..]
> +/**
> + * spdm_authenticate() - Authenticate device

The above looks like it is asking for an __spdm_authenticate helper.

int spdm_authenticate(struct spdm_state *spdm_state)
{
	guard(mutex)(&spdm_state->lock);
	rc = __spdm_authenticate(spdm_state);
	if (rc)
		spdm_reset(spdm_state);
	spdm_state->authenticated = !rc;
	spdm_free_transcript(spdm_state);
	return rc;
}

Otherwise, looks good to me.

---

## [30] Lukas Wunner — 2024-07-09
*Subject: Re: [PATCH v2 07/18] spdm: Introduce library to authenticate devices*

On Tue, Jul 09, 2024 at 10:45:27AM +1000, Alexey Kardashevskiy wrote:
> On 8/7/24 22:54, Lukas Wunner wrote:
> > The short answer is, it's a bug in libspdm and the issue should

In that case all (up to 8) certificate chains should have been retrieved
and are available for examination in the certificates/ directory in sysfs
(below the PCI device's directory).

You can use ordinary openssl tooling to examine the certificates and
see what's wrong with them, see the ABI documentation in patch [12/18]
for examples:

https://lore.kernel.org/all/e42905e3e5f1d5be39355e833fefc349acb0b03c.1719771133.git.lukas@wunner.de/

The "Malformed certificate at slot 0 offset 0" message means that the
first certificate in the chain in slot 0 does not comply with
requirements set forth in the SPDM spec.  (E.g. Basic Constraints CA
value shall be false for leaf cert, true for intermediate and root certs
per SPDM 1.3.0 table 42.)

The expectation is that vendors will test their devices and fix issues
like this, so that end users never see those messages.

The error message is emitted by spdm_validate_cert_chain().
The implementation calls that to identify a certificate chain which is
considered valid by the kernel.  The first one found is used for
challenge-response authentication.  If none is found valid, the kernel
will try to perform challenge-response authentication with the first
*provisioned* slot, regardless of its validity.  That is done to
expose a signature in sysfs about which user space can make up its
own mind, see patch [17/18]:

https://lore.kernel.org/all/dff8bcb091a3123e1c7c685f8149595e39bbdb8f.1719771133.git.lukas@wunner.de/

So despite the error message you should see a signature with full SPDM
transcript and other ancillary data in the signatures/ directory in sysfs.

Not sure yet whether that feature (exposing a signature despite
cert chains' invalidity from the kernel POV) makes sense.
We can also discuss adding ABI which allows user space to force
challenge-response with a specific slot, or to declare a specific
slot valid.

Thanks,

Lukas

---

## [31] Jeff Johnson — 2024-07-09
*Subject: Re: [PATCH v2 07/18] spdm: Introduce library to authenticate devices*

On 6/30/24 12:42, Lukas Wunner wrote:
...
> diff --git a/lib/spdm/core.c b/lib/spdm/core.c
> new file mode 100644
...
> +
> +MODULE_LICENSE("GPL");

This is missing a MODULE_DESCRIPTION().

Building a module without a MODULE_DESCRIPTION() will result in a 
warning when building with make W=1.

---

## [32] Dan Williams — 2024-07-09
*Subject: Re: [PATCH v2 08/18] PCI/CMA: Authenticate devices on enumeration*

Lukas Wunner wrote:
> From: Jonathan Cameron <Jonathan.Cameron@huawei.com>
> 

What is driving the requirement for CMA to be built-in?

All of the use cases I know about to date are built around userspace
policy auditing devices after the fact. Certainly a deployment could
choose to build it in, but it is a significant amount of infrastructure
that could tolerate late loading.

PCI TSM will be late loaded, so it is already the case that depending on
the authentication mechanism chosen (native, or TSM) the system needs to
be prepared for late / dynamic authentication.

---

## [33] Lukas Wunner — 2024-07-09
*Subject: Re: [PATCH v2 08/18] PCI/CMA: Authenticate devices on enumeration*

On Tue, Jul 09, 2024 at 11:10:57AM -0700, Dan Williams wrote:
> Lukas Wunner wrote:
> > --- a/drivers/pci/Kconfig

There is no way to auto-load modules needed for certain PCI features.
We'd have to call request_module() on PCI bus enumeration when
encountering devices with specific PCI features.  But what do we do
if module loading fails?  The PCI bus is enumerated in a subsys_initcall,
when neither the root filesystem has been mounted nor run_init_process()
has been called.  So any PCI core modules would have to be in the initrd.
What if they aren't?  Kernel panic?  That question seems particularly
pertinent for a security feature like CMA.

So we've made PCI core features non-modular by default.
In seven cases we even switched from tristate to bool because building
as modules turned out not to be working properly:

82280f7af729 ("PCI: shpchp: Convert SHPC to be builtin only")
a4959d8c1eaa ("PCI: Remove DPC tristate module option")
774104399459 ("PCI: Convert ioapic to be builtin only, not modular")
67f43f38eeb3 ("s390/pci/hotplug: convert to be builtin only")
c10cc483bf3f ("PCI: pciehp: Convert pciehp to be builtin only, not modular")
7cd29f4b22be ("PCI: hotplug: Convert to be builtin only, not modular")
6037a803b05e ("PCI: acpiphp: Convert acpiphp to be builtin only, not modular")

There has not been a single case where we switched from bool to tristate,
with the exception of PCI_IOAPIC with commit b95a7bd70046, but that was
subsequently reverted back to bool with the above-listed 774104399459.


> All of the use cases I know about to date are built around userspace
> policy auditing devices after the fact.

I think we should also support use cases where user space sets a policy
(e.g. not to bind devices to a driver unless they authenticate) and lets
the kernel do the rest (i.e. autonomously authenticate devices based on
a set of trusted root certificates).  User space does not *have* to be
the one auditing each device on a case-by-case basis, although I do see
the usefulness of such scenarios and am open to supporting them.  In fact
this v2 takes a step in that direction by exposing signatures received
from the device to user space and doing so even if the kernel cannot
validate the device's certificate chains as well-formed and trusted.

In other words, I'm trying to support both:  Fully autonomous in-kernel
authentication of certificates, but also allowing user space to make a
decision if it wants to.  It's simply not clear to me at the moment
what the use cases will be.  I can very well imagine that, say,
ChromeBooks will want to authenticate Thunderbolt-attached PCI devices
based on a keyring of trusted vendor certificates.  The fully autonomous
in-kernel authentication caters to such a use case.  I don't want to
preclude such use cases just because Confidential Computing in the
cloud happens to be the buzzword du jour.

Thanks,

Lukas

---

## [34] Dan Williams — 2024-07-09
*Subject: Re: [PATCH v2 08/18] PCI/CMA: Authenticate devices on enumeration*

Lukas Wunner wrote:
> On Tue, Jul 09, 2024 at 11:10:57AM -0700, Dan Williams wrote:
> > Lukas Wunner wrote:

TSM is taking the approach of dynamically adjusting the visibility of
TSM attributes when the platform TSM driver registers with the PCI core.
It is forced to do this because a TSM controller may itself be a PCI
that needs a driver to load before the PCI core attributes are usable.

For native functionality, yes, it would indeed take synthetic device to
play the same role.

> We'd have to call request_module() on PCI bus enumeration when
> encountering devices with specific PCI features.  But what do we do

Non-authenticated operation is the status quo. CMA is a building block
to other security features. Nothing currently cares about CMA being
established before a driver loads and it is not clear that now is the
time to for the kernel to paint itself into a corner to make that
guarantee.

> So we've made PCI core features non-modular by default.
> In seven cases we even switched from tristate to bool because building

That's good history that I was not aware, thanks for that.

However, most of those seem to be knock-on effects of:

https://lore.kernel.org/all/20121207062454.11051.12739.stgit@amt.stowe/

...where init order constraints between ACPI and PCI functionality led
to modules not being viable. The DPC one does not fit that model, but
DPC is small enough and entangled with AER to not really justify it
being a standalone module.

> > All of the use cases I know about to date are built around userspace
> > policy auditing devices after the fact.

Userspace validation of authentication and measurement is separate from
whether the functionality is built-in or not.

> In other words, I'm trying to support both:  Fully autonomous in-kernel
> authentication of certificates, but also allowing user space to make a

I think you are conflating automatic authentication and built-in
functionality. There are counter examples of security features like
encrypted root filesystems built on top of module drivers.

What I am trying to avoid is CMA setting unnecessary expectations that
can not be duplicated by TSM like "all authentication capable PCI
devices will be authenticated prior to driver attach".

Now, might there be a reason for native TSM and CMA to diverge on this
policy / capability in the future, maybe? It certainly is not here
today.

> preclude such use cases just because Confidential Computing in the
> cloud happens to be the buzzword du jour.

As if CMA is somehow not part of the "buzzword du jour" of Confidential
Computing?

---

## [35] Alistair Francis — 2024-07-10
*Subject: Re: [PATCH v2 01/18] X.509: Make certificate parser public*

On Sun, 2024-06-30 at 21:36 +0200, Lukas Wunner wrote:
> The upcoming support for PCI device authentication with CMA-SPDM
> (PCIe r6.1 sec 6.31) requires validating the Subject Alternative Name

Reviewed-by: Alistair Francis <alistair.francis@wdc.com>

Alistair

> ---
>  crypto/asymmetric_keys/x509_parser.h | 40 +--------------------

---

## [36] Alistair Francis — 2024-07-10
*Subject: Re: [PATCH v2 02/18] X.509: Parse Subject Alternative Name in
 certificates*

On Sun, 2024-06-30 at 21:37 +0200, Lukas Wunner wrote:
> The upcoming support for PCI device authentication with CMA-SPDM
> (PCIe r6.1 sec 6.31) requires validating the Subject Alternative Name

Reviewed-by: Alistair Francis <alistair.francis@wdc.com>

Alistair

> ---
>  crypto/asymmetric_keys/x509_cert_parser.c | 9 +++++++++

---

## [37] Alistair Francis — 2024-07-10
*Subject: Re: [PATCH v2 03/18] X.509: Move certificate length retrieval into
 new helper*

On Sun, 2024-06-30 at 21:38 +0200, Lukas Wunner wrote:
> The upcoming in-kernel SPDM library (Security Protocol and Data
> Model,

Reviewed-by: Alistair Francis <alistair.francis@wdc.com>

Alistair

> ---
>  crypto/asymmetric_keys/x509_loader.c | 38 +++++++++++++++++++-------

---

## [38] Alistair Francis — 2024-07-10
*Subject: Re: [PATCH v2 04/18] certs: Create blacklist keyring earlier*

On Sun, 2024-06-30 at 21:39 +0200, Lukas Wunner wrote:
> The upcoming support for PCI device authentication with CMA-SPDM
> (PCIe r6.2 sec 6.31) requires parsing X.509 certificates upon

Reviewed-by: Alistair Francis <alistair.francis@wdc.com>

Alistair

> ---
>  certs/blacklist.c | 4 ++--

---

## [39] Alistair Francis — 2024-07-10
*Subject: Re: [PATCH v2 10/18] PCI/CMA: Reauthenticate devices on reset and
 resume*

On Sun, 2024-06-30 at 21:45 +0200, Lukas Wunner wrote:
> CMA-SPDM state is lost when a device undergoes a Conventional Reset.
> (But not a Function Level Reset, PCIe r6.2 sec 6.6.2.)  A D3cold to

Reviewed-by: Alistair Francis <alistair.francis@wdc.com>

Alistair

> ---
>  drivers/pci/cma.c        | 15 +++++++++++++++

---

## [40] Dan Williams — 2024-07-10
*Subject: Re: [PATCH v2 09/18] PCI/CMA: Validate Subject Alternative Name in
 certificates*

Lukas Wunner wrote:
> PCIe r6.1 sec 6.31.3 stipulates requirements for Leaf Certificates
> presented by devices, in particular the presence of a Subject Alternative

I think this analysis is sufficient to justify the Linux requirement for
Subject-Alternative-Name. I agree that it seems odd that an FPGA that
changes its id also does not have a way to provision an updated
certificate at the same time. Like I would expect if the new bitstream
is signed then it can also deploy an updated certificate in the same
bitstream.

Unless and until commericial devices arrive that violate the expectation
with no way to update the certificate would Linux need a workaround, and
even then it would appear to be an explicit quirk.

I can see debug scenarios where it would be useful to relax this
requirement, but that can be achieved with local hacks, no need pressing
need to ship that debug facility upstream.

Acked-by: Dan Williams <dan.j.williams@intel.com>

...don't feel comfortable offering a reviewed-by on ASN parsing.

---

## [41] Dan Williams — 2024-07-10
*Subject: Re: [PATCH v2 10/18] PCI/CMA: Reauthenticate devices on reset and
 resume*

Lukas Wunner wrote:
> CMA-SPDM state is lost when a device undergoes a Conventional Reset.
> (But not a Function Level Reset, PCIe r6.2 sec 6.6.2.)  A D3cold to D0

TSM "connect" state also needs to be managed over reset, so stay tuned
for some collaboration here.

> needs to be in-kernel:  During ->resume_noirq, which is the first phase
> after system sleep, the PCI core walks down the hierarchy, puts each

I agree that CMA should be in kernel, it's not clear that authentication
needs to be automatic, and certainly not in a way that a driver can not
opt-out of.

What if a use case cares about resume time latency?  What if a driver
knows that authentication is only needed later in the resume flow? Seems
presumptious for the core to assume it knows best when authentication
needs to happen.

At a minimum I think pci_cma_reauthenticate() should do something like:

/* not previously authenticated skip authentication */
if (!spdm_state->authenticated)
	return;

...so that spdm capable devices can opt-out of automatic reauthentication.

---

## [42] Lukas Wunner — 2024-07-11
*Subject: Re: [PATCH v2 08/18] PCI/CMA: Authenticate devices on enumeration*

On Tue, Jul 09, 2024 at 04:31:30PM -0700, Dan Williams wrote:
> Non-authenticated operation is the status quo. CMA is a building block
> to other security features.

That's not quite correct:  Products exist which support CMA but neither
IDE nor TDISP.  CMA is not just a building block for IDE or TDISP,
but is useful on its own merits.

> Nothing currently cares about CMA being
> established before a driver loads and it is not clear that now is the

The PCI core initializes all of the device's capabilities upon enumeration.
CMA is no different than any of the other capabilities.

Chromebooks and many Linux distributions prevent driver binding to
Thunderbolt-attached devices unless they're authorized by the user.
I fully expect that vendors will want to additionally take advantage
of authentication.  I don't want to wait for Windows or macOS to go
ahead and add automatic authentication, then follow in their footsteps.
I want Linux to lead the way here, so yes, absolutely, that's the corner
I want the kernel to paint itself in, no less.

> I think you are conflating automatic authentication and built-in
> functionality. There are counter examples of security features like

Encrypted root filesystems are mounted after all initcall levels have run
and user space has been launched.  At that point it's possible to invoke
request_module().  But request_module() cannot be invoked from a
subsys_initcall(), which is when device capabilities are enumerated.

TSM can be a module because it's geared towards the passthrough use case
and passthrough only happens when user space is up and running.

> What I am trying to avoid is CMA setting unnecessary expectations that
> can not be duplicated by TSM like "all authentication capable PCI

I don't want to artificially cripple CMA in order to achieve only a
lowest common denominator with TSM.  Both, native CMA and TSM-driven
authentication have their respective use cases and (dis)advantages.
Should we try to strive for commonalities in the ABI?  Of course!
But not at the expense of reducing functionality.

> I agree that CMA should be in kernel, it's not clear that authentication
> needs to be automatic, and certainly not in a way that a driver can not

If there is a need to opt out, that feature can be retrofitted easily.
But systems need to be "secure by default":
https://en.wikipedia.org/wiki/Secure_by_default

> What if a use case cares about resume time latency?

Resume is parallelized (see dpm_noirq_resume_devices()), so the latency
is bounded by the time to authenticate a single device.

Unfortunately boot-time enumeration of the PCI bus is not parallelized
for historic reasons, we may indeed have to look into that.

> What if a driver
> knows that authentication is only needed later in the resume flow?

If authentication is not possible in the ->resume_noirq phase because
the driver needs to perform some initialization steps, it can just call
on the PCI core to reauthenticate the device after those steps.

The declaration of pci_cma_reauthenticate() can be moved from
drivers/pci/pci.h to include/linux/pci.h once that need arrives.

> At a minimum I think pci_cma_reauthenticate() should do something like:
> 

Unfortunately that doesn't work:

A device may have been reset due to a firmware update which adds
CMA support.  Or the keyring of trusted root certificates may have
been missing the certificate for authenticating the device, but the
certificate has since been added.  Or the device came back from reset
with a different certificate chain.  Or it was hot-replaced with a
CMA-capable one...

Thanks,

Lukas

---

## [43] Dan Williams — 2024-07-11
*Subject: Re: [PATCH v2 08/18] PCI/CMA: Authenticate devices on enumeration*

Lukas Wunner wrote:
> On Tue, Jul 09, 2024 at 04:31:30PM -0700, Dan Williams wrote:
> > Non-authenticated operation is the status quo. CMA is a building block

Agree it is useful. The use case of signed device inventory at a CSP,
that I understand storage vendors are interested, does not demand
aggressive forced authentication of all PCI devices in early init. As far
as I understand the non PCI-CMA consumers of lib/spdm/ are going to be
drivers possibly built as modules.

> > Nothing currently cares about CMA being
> > established before a driver loads and it is not clear that now is the

Init, sure.

> CMA is no different than any of the other capabilities.

It is a dynamic command protocol with a state machine, the state is free
to transition post-init.

> Chromebooks and many Linux distributions prevent driver binding to
> Thunderbolt-attached devices unless they're authorized by the user.

Look, if someone wants to build an aggressive policy they can, just set
the tristate option to 'Y'. It's the "all or nothing forced kernel
policy" that is awkward.

> > I think you are conflating automatic authentication and built-in
> > functionality. There are counter examples of security features like

Again, this is conflating the init mechanism from the state transition.
TSM will also be initialized at subsys_initcall() level.

> TSM can be a module because it's geared towards the passthrough use case
> and passthrough only happens when user space is up and running.

Yes, and no. TSM is going to be the only mechanism to enable IDE on
multiple platforms. I can imagine hyper-vigilant use cases that want to
deploy a policy of delaying driver probing until IDE is established
*and* wanting that to happen without loadable modules. That should be
possible with CONFIG_PCI_TSM=y and some EPROBE_DEFER dance with the
low-level TSM driver.

At no point is the TSM driver forcing IDE to be enabled on all devices
just because it is there. It remains an optional policy of the distro.

> > What I am trying to avoid is CMA setting unnecessary expectations that
> > can not be duplicated by TSM like "all authentication capable PCI

Hold on, "cripple"!? Just because the authenticated state might be
delayed due to distro policy?

> in order to achieve only a
> lowest common denominator with TSM.  Both, native CMA and TSM-driven

No mechanism is injured. This is only a question of optionality in
policy.

> > I agree that CMA should be in kernel, it's not clear that authentication
> > needs to be automatic, and certainly not in a way that a driver can not

Now, *that* is true, and that is what keeps me from outright NAKing this
approach.

I see no justification for the hard coded aggressive default policy, but
I will defer to Bjorn on whether this goes in as is with a plan to fix
it later, or fix it now.

> But systems need to be "secure by default":
> https://en.wikipedia.org/wiki/Secure_by_default

That's policy. Distros manage questions of security vs
user-friendliness, and I continue to have user friendliness concerns
relative to the security value that PCI-CMA offers.

> > What if a use case cares about resume time latency?
> 

As far as I understand that can still be on the order of seconds, and
pathological cases that could be longer. So the choice is wait to see
who screams, or plan for non-ideal devices. The worst case is distros
start shipping CONFIG_PCI_CMA=n because it causes too many problems,

> Unfortunately boot-time enumeration of the PCI bus is not parallelized
> for historic reasons, we may indeed have to look into that.

Yeah, driver probing is async though, so if initial authentication moves
to be done in or around pci_enable_device() then it achieves async init
while also allowing for drivers to not be exposed to unauthenticated
devices.

> > What if a driver
> > knows that authentication is only needed later in the resume flow?

Up to Bjorn whether to pull that thread now or not.

> > At a minimum I think pci_cma_reauthenticate() should do something like:
> > 

All of these are mitigated by pushing authentication management to
drivers. "Just re-authenticate" makes the latency problem worse. How bad
is that latency problem in practice? I do not know.

---

## [44] Damien Le Moal — 2024-07-12
*Subject: Re: [PATCH v2 08/18] PCI/CMA: Authenticate devices on enumeration*

On 7/12/24 02:50, Dan Williams wrote:
> Lukas Wunner wrote:
>> On Tue, Jul 09, 2024 at 04:31:30PM -0700, Dan Williams wrote:

Yes, and they already are: SCSI/ATA and NVMe command transport for SPDM is being
defined (SPDM-over-storage using the SECURITY IN/OUT for SCSI and SECURITY
SEND/RECV commands for NVMe). Authentication of such storage device will require
the device driver to be loaded first and the device to be scanned and probed to
discover this feature. So SPDM authentication in this case would not even happen
early in the device initialization process as we will need the device to already
be functional to issue the security commands.

For PCIe/DOE devices (which could be PCIe NVMe devices not using
SPDM-over-storage), I do not see why we cannot also do the authentication from
the device driver context. As you suggested, pci_enable_device() context could
be the right place to do that, if the device driver opts-in (and that can be
driven by distro config).

This would result in all calls to lib/spdm authentication for all devices to
happen at the same timing, i.e. device driver initialization, whenever that
happens (at boot with kernel built-in or modules loaded later).

This approach would also likely facilitate handling re-authentication on resume
since that also involves the device driver, at least for the SPDM-over-storage
case (e.g. OPAL device locking/unlocking for SCSI already has code to be
suspend/resume aware).

---

## [45] Alistair Francis — 2024-07-12
*Subject: Re: [PATCH v2 13/18] sysfs: Allow bin_attributes to be added to
 groups*

On Sun, 2024-06-30 at 21:48 +0200, Lukas Wunner wrote:
> Commit dfa87c824a9a ("sysfs: allow attributes to be added to groups")
> introduced dynamic addition of sysfs attributes to groups.

Reviewed-by: Alistair Francis <alistair.francis@wdc.com>

Alistair

> ---
>  fs/sysfs/file.c       | 69 ++++++++++++++++++++++++++++++++++++-----

---

## [46] Lukas Wunner — 2024-07-14
*Subject: Re: [PATCH v2 08/18] PCI/CMA: Authenticate devices on enumeration*

[cc += Kees Cook, Jann Horn; start of thread:
https://lore.kernel.org/all/6d4361f13a942efc4b4d33d22e56b564c4362328.1719771133.git.lukas@wunner.de/
]

On Thu, Jul 11, 2024 at 10:50:28AM -0700, Dan Williams wrote:
> Lukas Wunner wrote:
> > Resume is parallelized (see dpm_noirq_resume_devices()), so the latency

I'm seeing 150 msec to authenticate a PCI device if the signature can't be
verified (e.g. due to missing trusted root certificate) and 400 msec if
the signature *is* verified.  This varies depending on beefiness of CPU,
algorithm selection, key length and number of provisioned slots.

But I've never seen this take "on the order of seconds", I assume that's
a misunderstanding.

vmlinux size grows by 12.752 bytes with CONFIG_PCI_CMA=y on x86_64.
The feature is disabled by default.


> All of these are mitigated by pushing authentication management to
> drivers.

Device authentication can't be pushed to drivers.  It must be done
*before* driver binding:

Drivers are bound based on identity information in config space
(such as Vendor ID or Device ID).  A malicious device could spoof
identity information in config space to force binding to a specific
(CMA-unaware) driver.

The certificate contains the signed Vendor ID and Device ID of the
device.  By validating the certificate and the signature presented
by the device, its identity can be ascertained by the PCI core
before a driver (the right one) starts accessing it.


> I see no justification for the hard coded aggressive default policy

I think that just preventing driver binding if a device fails
authentication may not be good enough.  If a device is truly
malicious, perhaps we should firewall it off.  I'm worried about
a device laterally attacking other devices through P2PDMA or
sending malformed TLPs upstream to the root complex. 

In patch [11/18], I'm suggesting:

   "Traffic from devices which failed authentication could also be
    filtered through ACS I/O Request Blocking Enable (PCIe r6.2 sec
    7.7.11.3) or through Link Disable (PCIe r6.2 sec 7.5.3.7)."

To firewall off malicious devices, authentication should happen early on.
The system shouldn't be exposed to those devices any longer than necessary.
That's one reason why this patch set performs mandatory authentication
already on enumeration:  So that we're able to catch malicious devices
as early as possible.

Patch [08/18] inserts pci_cma_init() at the end of pci_init_capabilities()
because CMA depends on DOE.  We may want to move DOE and CMA init
further up in the function to authenticate the device even before
enumerating any of its other capabilities.

It's probably too early to decide which actions to take if a device fails
authentication, whether to offer a variety of actions (only prevent driver
binding) or just stick to the harshest one (firewall off the device),
when to perform those actions and which knobs to offer to users for
controlling policy and overriding actions.  We may need more real-world
experience before we can make those decisions and we may need to ask
security folks such as Kees Cook and Jann Horn for their perspective.

This patch set merely exposes to user space whether a device passed
authentication or not.  For that alone, it would indeed be sufficient
to authenticate asynchronously -- or delay authentication until the
sysfs attribute is accessed.

But I wanted to keep the option open to firewall off devices early on.
And placing pci_cma_init() in pci_init_capabilities() felt natural
because it's where all the other device capabilities are enumerated
and initialized.

Thanks,

Lukas

---

## [47] Kees Cook — 2024-07-15
*Subject: Re: [PATCH v2 08/18] PCI/CMA: Authenticate devices on enumeration*

On Sun, Jul 14, 2024 at 10:42:41AM +0200, Lukas Wunner wrote:
> It's probably too early to decide which actions to take if a device fails
> authentication, whether to offer a variety of actions (only prevent driver

I don't know PCI internals well enough to have any actionable opinion on
many of the aspects of this thread, but I can try to give my perspective
on the mitigation behavior at least.

My main observation is that the CC threat model of "we can't trust what
is attached to the bus" is an extremely high bar, and is not the common
threat model for most deployments.

As such, it seems like any associated behaviors need to defer to common
deployments. It may just be as simple as making it a Kconfig option. That
said, the best practice for such specialized behaviors is actually best
put behind a static branch so that distros can able a given feature
without making it on by default. (e.g. see the randomize_kstack_offset
boot param[1].) Given the "module or builtin" question, I would expect
this will end up being strictly a Kconfig, though.

Anyway, following the threat model, it doesn't seem like half measures
make any sense. If the threat model is "we cannot trust bus members" and
authentication is being used to establish trust, then anything else must
be explicitly excluded. If this can only be done via the described
firewalling, then that really does seem to be the right choice.

Now given what a high bar it is to not trust the bus, there are a lot of
attack methodologies that likely need to be examined. For example, the
bus has a different lifetime than the kernel, so it may be possible that
members are attacking each other/the CPU/DMA etc, before Linux has even
started running. If that can't be mitigated, then it doesn't matter what
Linux is doing.

This is why I've kind of tried to stay out of CC discussions: the threat
models can be extremely hard to wrangle, and much of it depends on
hardware design. :) I have enough to worry about just trying to protect
the kernel from userspace. ;)

-Kees

[1] https://docs.kernel.org/admin-guide/kernel-parameters.html?highlight=randomize_kstack_offset

---

## [48] Jason Gunthorpe — 2024-07-15
*Subject: Re: [PATCH v2 08/18] PCI/CMA: Authenticate devices on enumeration*

On Mon, Jul 15, 2024 at 10:21:48AM -0700, Kees Cook wrote:

> Anyway, following the threat model, it doesn't seem like half measures
> make any sense. If the threat model is "we cannot trust bus members" and

There is supposed to be a state machine here, devices start up at VM
time 0 unable to DMA to secure guest memory under any conditions. This
property must be enforced by the trusted platform.

Further the trusted plaform is supposed to prevent "replacement"
attacks, so once the VM says it trusts a device it cannot be replaced
with something else.
 
When the guest decides it would like the device to reach secure memory
the trusted platform is part of making that happen.

From a kernel and lifecycle perspective we need a bunch of new options
for PCI devices that should be triggered after userspace has had a
look at the device.

 - A device is just forbidden from anything using it
 - A device used only with untrusted memory
 - A device is usable with trusted memory

IMHO this determination needs to be made before the device driver is
bound.

The kernel will self-accept a bunch of platform devices, but something
like the boot volume's device will need something to go look and
approve it.

Today the kernel self-approves untrusted devices, but this is perhaps
not a great idea in the long run.

It is definately not a good idea for trusted devices.

Jason

---

## [49] Dan Williams — 2024-07-15
*Subject: Re: [PATCH v2 08/18] PCI/CMA: Authenticate devices on enumeration*

Lukas Wunner wrote:
> [cc += Kees Cook, Jann Horn; start of thread:
> https://lore.kernel.org/all/6d4361f13a942efc4b4d33d22e56b564c4362328.1719771133.git.lukas@wunner.de/

That worry came from an offlist discussion around handling AEAD limits
for IDE. If IDE is going to go into an error state when the AEAD limit
is reached then software needs to prepared for the worst case time to
re-establish that session and that worst case DOE transfers take
1-second.

That said, a device that takes one-second per DOE message is likely
broken for other reasons, so lets hope that authentication latency does
not become a problem in practice.

[..]
> > All of these are mitigated by pushing authentication management to
> > drivers.

Allowing for it to be possible before driver binding is a good idea,
mandating it is the issue. Mechanism vs policy.

> Drivers are bound based on identity information in config space
> (such as Vendor ID or Device ID).  A malicious device could spoof

Yes, and mitigating that depends on the threat model. For example,
unauthenticated devices talking to public memory is outside the TDISP
threat model. It is private memory that needs end-to-end protection.

> The certificate contains the signed Vendor ID and Device ID of the
> device.  By validating the certificate and the signature presented

Again that is a policy option dependent on the threat model.

> To firewall off malicious devices, authentication should happen early on.
> The system shouldn't be exposed to those devices any longer than necessary.

We keep talking past each other.

I am not disagreeing with the possibility of deploying the strictest
imaginable policy around CMA. Instead, I am looking for CMA to consider
optionality in policy given the TDISP threat model, and the known
"secure CSP device inventory" use cases. Neither of those are mandating
that CMA classify all non-authenticated devices as malicious.

Going further, there is a reason that CMA is only a building block of
TDISP. If the threat model is "malicious device implementation" then the
threat mitigation needs to consider spoofed MMIO. That's where IDE and
private MMIO come into play. Sure, CMA is a hurdle to make it more
difficult to carry out a malicious device implementation attack, but do
not oversell the protection it affords relative to all the other steps
needed to protect confidential memory.

[..]
> This patch set merely exposes to user space whether a device passed
> authentication or not.  For that alone, it would indeed be sufficient

Yes, lets build that as an *option*, and step back from CONFIG_PCI_CMA
implying an "unauthenticated == malicious" policy. Given the TDISP
threat model allows for unauthenticated devices to freely access public
memory, my contention is that Linux policy should start with how to
protect private (confidential) memory and then grow to cross-device
attack and bare metal device policy.

In other words, "hardware enforced confidential memory" is the new
concept that makes Linux reconsider its stance towards devices. If there
is no confidential memory to protect, does the mere presence of CMA mean
that Linux upends its device-driver model?

---

## [50] Dan Williams — 2024-07-15
*Subject: Re: [PATCH v2 08/18] PCI/CMA: Authenticate devices on enumeration*

Kees Cook wrote:
> On Sun, Jul 14, 2024 at 10:42:41AM +0200, Lukas Wunner wrote:
> > It's probably too early to decide which actions to take if a device fails

This is where the discussion jumps off into details and needs more
precision. Mere authentication, PCI CMA, does not establish trust in the
device. Authentication only tells you that the device provided a
certificate that matched a value read from config-space. That device's
config-space can be spoofed and / or the MMIO registers that the driver
thinks it is talking to can be spoofed. So establishing trust in the
*bus* requires PCI TDISP.

> Now given what a high bar it is to not trust the bus, there are a lot of
> attack methodologies that likely need to be examined. For example, the

Right, PCI TDISP considers this, PCI CMA does not.

> This is why I've kind of tried to stay out of CC discussions: the threat
> models can be extremely hard to wrangle, and much of it depends on

Yes, I am trying to find a path that allows for incrementally enabling
these security technologies while not overselling the value, and not
completely invalidating the Linux device driver model as "step1".

Even with PCI TDISP, and the end-to-end trust that the PCI interface is
the one you expect, a lot can happen once traffic crosses the
bus-to-device interface.

---

## [51] Dan Williams — 2024-07-15
*Subject: Re: [PATCH v2 08/18] PCI/CMA: Authenticate devices on enumeration*

Jason Gunthorpe wrote:
> On Mon, Jul 15, 2024 at 10:21:48AM -0700, Kees Cook wrote:
> 

Yes, and it depends on the device. Some devices should be filtered
early, some devices need to be operated against untrusted memory just
to get to the point where they can complete the acceptance flow into the
TCB.

The motivation for the security policy is "there is trusted memory to
protect". Absent trusted memory, the status quo for the device-driver
model applies.

> The kernel will self-accept a bunch of platform devices, but something
> like the boot volume's device will need something to go look and

Right, I think the capability to "forbid devices to protect trusted
memory" can one day be deployed in the absence of any trusted memory to
protect. I am just not convinced that needs to be the task on day1 to
assert "mere authentication exists, all devices are malicious now even
in the absence of trusted memory".

---

## [52] Jason Gunthorpe — 2024-07-15
*Subject: Re: [PATCH v2 08/18] PCI/CMA: Authenticate devices on enumeration*

On Mon, Jul 15, 2024 at 01:36:32PM -0700, Dan Williams wrote:
> Jason Gunthorpe wrote:
> > On Mon, Jul 15, 2024 at 10:21:48AM -0700, Kees Cook wrote:

Operating a device with both trusted and untrusted iommu
configurations is complex to manage and depends on how the trusted
iommu HW works.

> The motivation for the security policy is "there is trusted memory to
> protect". Absent trusted memory, the status quo for the device-driver

From what I can see on some platforms/configurations if the device is
trusted capable then it MUST only issue trusted DMA as that is the
only IO translation that will work.

Meaning the decision to operate a device as trusted or not really has
to be done before any driver is probed and probably needs to involve
the iommu layer to try and do something about this mess in some way.

I have yet to see a complete plan for how these details should work :)

And I only know in detail how the iommu works for one platform, not
the others, so I don't know how prevalent these concerns are..

Jason

---

## [53] Damien Le Moal — 2024-07-16
*Subject: Re: [PATCH v2 08/18] PCI/CMA: Authenticate devices on enumeration*

On 7/16/24 07:02, Jason Gunthorpe wrote:
> On Mon, Jul 15, 2024 at 01:36:32PM -0700, Dan Williams wrote:
>> Jason Gunthorpe wrote:

As I commented already, for storage device using SPDM-over-storage (scsi/ata and
nvme devices), the device authentication requires the device driver since we
need a gendisk and request queue to be able to issue the commands transporting
SPDM messages. So this is applicable only to PCI devices.

Of note though is that in the case of SCSI/ATA storage, the device (the HDD or
SSD) is not the one doing DMA directly to the host/guest memory. That is the
adapter (the HBA). So we could ask ourselves if it makes sense to authenticate
storage devices without the HBA being authenticated first.

And for PCI nvme devices that can support SPDM either through either PCI DOE or
SPDM-over-storage (SECURITY SEND/RECV commands), then I guess we need some
special handling/config to allow (or not) SPDM-over-storage authentication as
that will require the device driver to be loaded and to execute some commands
before authentication can happen.

> I have yet to see a complete plan for how these details should work :)
>

---

## [54] Dan Williams — 2024-07-15
*Subject: Re: [PATCH v2 08/18] PCI/CMA: Authenticate devices on enumeration*

Jason Gunthorpe wrote:
> On Mon, Jul 15, 2024 at 01:36:32PM -0700, Dan Williams wrote:
> > Jason Gunthorpe wrote:

Yes, especially if there are ongoing memory conversions.

> > The motivation for the security policy is "there is trusted memory to
> > protect". Absent trusted memory, the status quo for the device-driver

Given that PCI defines that devices can fall out of "trusted capable"
mode that implies there needs to be an error recovery path. For at least
the platforms I am looking at (SEV, TDX, COVE) a "convert device to
private operation" step is a possibility after the TVM is already
running. Are you implying that this platform in question would need to
shutdown the TVM and start over if, for example, the encrypted link
state bounced?

Or maybe device capability conversions are effectively "replug" events
on such a host?

> Meaning the decision to operate a device as trusted or not really has
> to be done before any driver is probed and probably needs to involve

Yes, userspace needs to be able to deploy device-attestation policy
prior to driver attach.

> I have yet to see a complete plan for how these details should work :)

There are so many details that I find myself needing to land basic
infrastructure upstream to bound the possibility space.

> And I only know in detail how the iommu works for one platform, not
> the others, so I don't know how prevalent these concerns are..

I think it is an important concern. Even if there is a dynamic "convert
device to private" capability, there is a question about what happens to
ongoing page conversions. Simultaneous untrusted / trusted memory access
may end up being something devices want, but not all host platforms can
offer.

---

## [55] Jason Gunthorpe — 2024-07-15
*Subject: Re: [PATCH v2 08/18] PCI/CMA: Authenticate devices on enumeration*

On Tue, Jul 16, 2024 at 07:17:55AM +0900, Damien Le Moal wrote:

> Of note though is that in the case of SCSI/ATA storage, the device
> (the HDD or SSD) is not the one doing DMA directly to the host/guest

For sure, you have to have all parts of the equation
authenticated before you can turn on access to trusted memory.

Is there some way these non DOE messages channel bind the attestation
they return to the PCI TDISP encryption keys?

What is the sequence you are after?

> And for PCI nvme devices that can support SPDM either through either
> PCI DOE or SPDM-over-storage (SECURITY SEND/RECV commands), then I

I'm not sure those commands make sense in a PCI context? They make
more sense to me in a NVMe over Network scenario where you could have
the attestation bind a TLS secret..

Still, my remarks from before stand, it looks like it is going to be
complex to flip a device from non-trusted to trusted.

Jason

---

## [56] Jason Gunthorpe — 2024-07-15
*Subject: Re: [PATCH v2 08/18] PCI/CMA: Authenticate devices on enumeration*

On Mon, Jul 15, 2024 at 03:50:28PM -0700, Dan Williams wrote:
> > > The motivation for the security policy is "there is trusted memory to
> > > protect". Absent trusted memory, the status quo for the device-driver

Sure, but this not the issue, if you stop being trusted you have to
immediately stop doing all DMA and the VM has to restore things back
to trusted before starting the DMAs again. Basically I'd expect you
have to FLR the device and start from scratch as an error recovery.

> For at least the platforms I am looking at (SEV, TDX, COVE) a
> "convert device to private operation" step is a possibility after

That's fine, too

The issue is the DMA. When you have a trusted vIOMMU present in the VM
things get complex.

At least one platform splits the IOMMU in half and PCIE TLP bit T=0
and T=1 target totally different translation.

So from a Linux VM perspective we have a PCI device with an IOMMU,
except that IOMMU flips into IDENTITY if T=0 is used.

From a driver model and DMA API this is totally nutzo :)

Being able to flip from trusted/untrusted and keep IOMMU/DMA/etc
unaffected requires that the vIOMMU can always walk the same IO page
tables stored in trusted VM memory, regardless if the device sends a
T=0/1 TLP.

IOW the secure trusted vIOMMU must be able to support non-trusted
devices as well.

So.. How many platforms actually did that? And how many said that only
T=1 goes the secure VIOMMU and T=0 goes to the hypervisor?

This is all much simpler if you don't have a trusted vIOMMU :)

> > And I only know in detail how the iommu works for one platform, not
> > the others, so I don't know how prevalent these concerns are..

Maybe, but that answer will probably be unsatisfying to people who are
building HW that assumes this works. :)

Jason

---

## [57] Damien Le Moal — 2024-07-16
*Subject: Re: [PATCH v2 08/18] PCI/CMA: Authenticate devices on enumeration*

On 7/16/24 08:03, Jason Gunthorpe wrote:
> On Tue, Jul 16, 2024 at 07:17:55AM +0900, Damien Le Moal wrote:
> 

For the scsi/ata case, at least initially, I think the use case will be only
device authentication to ensure that the storage device is genuine (not
counterfeit), has a good FW, and has not been tempered with and not the
confidential VM case.

> What is the sequence you are after?

The above as a first use case. For the confidential VM case, I think the HBA
needs to be involved as that is the one doing the DMA. But to be frank, I have
not spent time thinking about that use case at all.

>> And for PCI nvme devices that can support SPDM either through either
>> PCI DOE or SPDM-over-storage (SECURITY SEND/RECV commands), then I

100% agree, but I can foresee PCI NVMe device vendors adding SPDM support
"cheaply" using these commands since that can be implemented as a FW change
while adding DOE would be a controller HW change... So at least initially, it
may be safer to simply not support the NVMe SPDM-over-storage case, or at least
not support it for trusted platform/confidential VMs and only allow it for
storage authentication (in addition to the usual encryption, OPAL locking etc).

> Still, my remarks from before stand, it looks like it is going to be
> complex to flip a device from non-trusted to trusted.

Indeed, and we may need to have different ways of doing that given the different
transport and use cases.

---

## [58] Dan Williams — 2024-07-15
*Subject: Re: [PATCH v2 08/18] PCI/CMA: Authenticate devices on enumeration*

Jason Gunthorpe wrote:
> On Mon, Jul 15, 2024 at 03:50:28PM -0700, Dan Williams wrote:
> > > > The motivation for the security policy is "there is trusted memory to

I am not aware of an IOMMU implementation that does anything different
than that.

> So from a Linux VM perspective we have a PCI device with an IOMMU,
> except that IOMMU flips into IDENTITY if T=0 is used.

"Keep IOMMU/DMA/etc unaffected" is the hard part. To start I think the
assigned device needs to go through some violence to transition security
states and should likely assume that any untrusted memory is
inaccessible once the device is converted to private operation.

Once it falls out of private operation it needs some recovery to get its
untrusted mappings repaired / restored.

Implementations that want something more complicated than that, like
interleave T=0 and T=1 traffic, need to demonstrate how that is possible
given the iommufd maintainer declares it, *checks notes*, "totally
nutzo".

> IOW the secure trusted vIOMMU must be able to support non-trusted
> devices as well.

The complexity of the v1 implementation needs to be tamed first, then we
can start tilting at the higher order windmills.

---

## [59] Jason Gunthorpe — 2024-07-15
*Subject: Re: [PATCH v2 08/18] PCI/CMA: Authenticate devices on enumeration*

On Tue, Jul 16, 2024 at 08:26:55AM +0900, Damien Le Moal wrote:
> On 7/16/24 08:03, Jason Gunthorpe wrote:
> > On Tue, Jul 16, 2024 at 07:17:55AM +0900, Damien Le Moal wrote:

Oh, I see, that is something quite different then.

In that case you probably want to approve the storage device before
allowing read/write on the block device which is a quite a different
gate than the confidential VM people are talking about.

It is the equivalent we are talking about here about approving the PCI
device before allowing an OS driver to use it.

> 100% agree, but I can foresee PCI NVMe device vendors adding SPDM support
> "cheaply" using these commands since that can be implemented as a FW change

Yeah, probably.

Without a way to bind the NVMe SPDM support to the TDISP it doesn't
seem useful to me for CC cases.

Something like command based SPDM seems more useful to load an OPAL
media encryption secret or something like that - though you can't use
it to exclude an interposer attack so I wonder if it really matters..

> > Still, my remarks from before stand, it looks like it is going to be
> > complex to flip a device from non-trusted to trusted.

To be clear there are definately different sorts of trusted/untrusted
here

For CC VMs and TDISP trusted/untrusted means the device is allowed to
DMA to secure memory.

For storage trusted/untrusted may mean the drive is allowed to get a
media encryption secret, or have it's media accessed.

I think they are very different targets

Jason

---

## [60] Jason Gunthorpe — 2024-07-15
*Subject: Re: [PATCH v2 08/18] PCI/CMA: Authenticate devices on enumeration*

On Mon, Jul 15, 2024 at 04:37:01PM -0700, Dan Williams wrote:
> > So from a Linux VM perspective we have a PCI device with an IOMMU,
> > except that IOMMU flips into IDENTITY if T=0 is used.

Yes, but that is not just "unaffected" but it is implying that there
is state in the VM's iommu layer too. If T=0 goes to a different
translation then the DMA API must change behavior while a driver is
bound, which is not something we do today.

> Implementations that want something more complicated than that, like
> interleave T=0 and T=1 traffic, need to demonstrate how that is possible

Oh we can make the iommufd side work out, it is the VM's kernel that
is going to be trouble :)

Even in the simpler case of no-interleave but the same driver will
start with T=0 and change to T=1 is pretty complex:

 dma_addr1 = dma_map()   <== Must return a bypass address because T=0
 goto_t_1()              <== Now dma_addr1 stops being usable
 dma_addr2 = dma_map()   <== Must return a translated address through the vIOMMU
 dma_unmap(dma_addr1)    <== Well now you've done it. Your kernel explodes.

Maybe the "violance" is we have to unbind the PCI driver and rebind it
to get the goto_t_1() effect..

Changing the underlying behavior of the DMA API "in flight" while a
driver is bound seems really dangerous.

My point is if we start baking in the assumption that drivers can do
things like the above without addressing how the VIOMMU integration
works we are going to have a *huge mess* to try and introduce VIOMMU
down the road.

I'd be happy if V1 forbade the above entirely.

Jason

---

## [61] Damien Le Moal — 2024-07-16
*Subject: Re: [PATCH v2 08/18] PCI/CMA: Authenticate devices on enumeration*

On 7/16/24 08:42, Jason Gunthorpe wrote:
> On Tue, Jul 16, 2024 at 08:26:55AM +0900, Damien Le Moal wrote:
>> On 7/16/24 08:03, Jason Gunthorpe wrote:

Yes, that likely would not work at all anyway as the driver needs to start
probing the device before authentication can happen, meaning that DMA needs to
be working before we can authenticate. So unless device probing is changed to
use untrusted memory for probing, that would not work anyway.

> 
> Something like command based SPDM seems more useful to load an OPAL

Initially, we can certainly treat them like that. But eventually, we may need
something more as CC VMs access to storage has to be trusted too and so will
require both HBA and the device to be trusted. For the TDISP handling, I am
however not sure how that should looks like (is it the HBA or the storage device
secrets that are used, both ?). As I said, I have not spent any time yet
thinking about that use case.

---

## [62] Jason Gunthorpe — 2024-07-15
*Subject: Re: [PATCH v2 08/18] PCI/CMA: Authenticate devices on enumeration*

On Tue, Jul 16, 2024 at 08:57:14AM +0900, Damien Le Moal wrote:

> Initially, we can certainly treat them like that. But eventually, we
> may need something more as CC VMs access to storage has to be

My guess for CC VM's is you do both.

From a big picture a CC TVM is going to want encrypted storage,
otherwise it doesn't really make any sense.

If the TVM does the encryption with the CPU then we don't really need to
attest the storage or PCI at all, bounce the encrypted data into
untrusted memory and then CPU copy it while crypting it. This
minimizes the amount of stuff you have to trust.

If the TVM would like to have the storage device do the encryption
with something like OPAL then:
 - Attest and trust the PCI function, this lets you load the HBA driver
 - Attest and trust the "media"
 - Use the media attestation to load an encrypted copy of the media
   key from the secure keyserver into the drive

The split view of "media" and PCI function seems appropriate. The
keyserver should only release keys to media that has the correct
attested ID, while a controller may have many different media attached
to it.

Attesting the controller is probably not enough to release the keys?

Jason

---

## [63] Dan Williams — 2024-07-15
*Subject: Re: [PATCH v2 08/18] PCI/CMA: Authenticate devices on enumeration*

Jason Gunthorpe wrote:
[..]
> If the TVM would like to have the storage device do the encryption
> with something like OPAL then:

Right, I think key release is going to be based on measurement of the
entire VM and accepted device topology state.

Also, if the storage volume itself is accessed through dm-{crypt,verity}
it is not clear that the storage controller needs be attested to ensure
confidentiality of those transfers.

---

## [64] Dan Williams — 2024-07-15
*Subject: Re: [PATCH v2 08/18] PCI/CMA: Authenticate devices on enumeration*

Jason Gunthorpe wrote:
> On Mon, Jul 15, 2024 at 04:37:01PM -0700, Dan Williams wrote:
> > > So from a Linux VM perspective we have a PCI device with an IOMMU,

Agree.

> My point is if we start baking in the assumption that drivers can do
> things like the above without addressing how the VIOMMU integration

Yes, I think the requirement to go through rebind to cross the
untrusted/trusted boundary gives enough simplification to get started.

It also occurs to me that complex devices / drivers that really want
mixed T=0 and T=1 traffic from one PF can ingest the complexity without
burdening the Linux DMA API and IOMMU layers. Provide 2 assignable VFs
instead of 1 and do software driver-to-driver communication between
those trusted and untrusted drivers.

---

## [65] Dan Williams — 2024-07-17
*Subject: Re: [PATCH v2 11/18] PCI/CMA: Expose in sysfs whether devices are
 authenticated*

Lukas Wunner wrote:
> The PCI core has just been amended to authenticate CMA-capable devices
> on enumeration and store the result in an "authenticated" bit in struct

I'd drop the "(and may thus be malicious)", because passing SPDM is not
nearly enough to establish trust in the device interface, only the SPDM
mailbox. Also, unless PCI CMA becomes mandated in the PCI spec, or a
major operating system, I expect a limited set of devices do the work to
implement CMA. It is too early to declare that unauthenticated devices
are malicious, they are simply unauthenticated.

[..]
> diff --git a/lib/spdm/req-sysfs.c b/lib/spdm/req-sysfs.c
> new file mode 100644

This looks ok to me, but it does strike me that maybe
DEFINE_SIMPLE_SYSFS_GROUP_VISIBLE() should be deleted and replaced by a
recommendation to open-code returning SYSFS_GROUP_INVISIBLE as you have
done here.

Other than those small comments:

Reviewed-by: Dan Williams <dan.j.williams@intel.com>

---

## [66] Dan Williams — 2024-07-17
*Subject: Re: [PATCH v2 12/18] PCI/CMA: Expose certificates in sysfs*

Lukas Wunner wrote:
> The kernel already caches certificate chains retrieved from a device
> upon authentication.  Expose them in "slot[0-7]" files in sysfs for


> diff --git a/drivers/pci/pci-sysfs.c b/drivers/pci/pci-sysfs.c
> index d9e467cbec6e..a85388211104 100644

This is clever, but the @n parameter already conveys the index.

> +
> +	if (IS_ERR_OR_NULL(spdm_state))

Similar comment on cleverness, I will note that the way this is
typically handled is something like this which is just slightly less
error prone if someone in the future changes the naming scheme.

#define CERT_ATTR(n) \
static ssize_t slot##n##_show(struct file *file, struct kobject *kobj, \
                              struct bin_attribute *a, char *buf, loff_t off, \
                              size_t count) \
{ \
	return spdm_cert_read(kobj_to_dev(kobj), buf, off, count, (n)); \
} \
static BIN_ATTR_RO(slot##n);

---

## [67] Jonathan Cameron — 2024-07-18
*Subject: Re: [PATCH v2 03/18] X.509: Move certificate length retrieval into
 new helper*

On Sun, 30 Jun 2024 21:38:00 +0200
Lukas Wunner <lukas@wunner.de> wrote:

> The upcoming in-kernel SPDM library (Security Protocol and Data Model,
> https://www.dmtf.org/dsp/DSP0274) needs to retrieve the length from
Rereading some of these early patches to try and get my head back into
what is going on here..

Passing comments inline, but given you are just moving the code
rather than writing it for the first time I don't mind keeping it as
things stand.

> ---
>  crypto/asymmetric_keys/x509_loader.c | 38 +++++++++++++++++++---------

Not sure readability would be hurt significantly by putting that on one line.

> +		return -EINVAL;
> +

get_unaligned_be16() perhaps

> +	plen += 4;
It's kind of obvious, but maybe a comment no why +4 would be good.
> +	if (plen > buflen)
> +		return -EINVAL;

---

## [68] Jonathan Cameron — 2024-07-18
*Subject: Re: [PATCH v2 07/18] spdm: Introduce library to authenticate
 devices*

On Mon, 8 Jul 2024 22:09:47 -0700
Dan Williams <dan.j.williams@intel.com> wrote:

> Lukas Wunner wrote:
> > From: Jonathan Cameron <Jonathan.Cameron@huawei.com>

That's fair.  Using a common static const array of structs with string
and error code would also make this pair more readable by concentrating
the error code in one place.

> 
> Would this not emit ambiguous messages like:

Problem there is that we've typically lost information because
of conversion to a smaller set of errno.

> 
> I have less problem if these all become dev_dbg() or tracepoints, but

dev_dbg() seems like an easy solution to me.  Maybe add tracepoints
later...

> 
> > +{
Seems reasonable to scatter those around.

> 
> ?
Not without collapsing the various files into one.
> 
> > +

...

> > +
> > +/**

If there is any concurrency risk things have gone very very wrong.
However maybe it's worth adding locking/markings just to make that clear.
Any contention will make the transcript garbage but nothing
stops us making that explicit rather that relying on callers doing
the right thing.

> 
> > +}

> > +/**
> > + * spdm_verify_signature() - Verify signature against leaf key
Agreed this is better as
	u8 *m __free(kfree) =
		kmalloc(SPDM_COMBINED_PREFIX_SZ + spdm_state->hash_len, GFP_KERNEL);

> > +	if (!m)
> > +		return -ENOMEM;
and
			u8 *mhash __free(kfree) =
				kmalloc(spdm_state->hash_len, GFP_KERNEL);

With added bonus that the scope is reduced for this one.
You probably want to add explicit scope though with {} around the case block
so it's more obvious what the scope is.


> > +			mhash = kmalloc(spdm_state->hash_len, GFP_KERNEL);
> > +			if (!mhash)

---

## [69] Jonathan Cameron — 2024-07-18
*Subject: Re: [PATCH v2 07/18] spdm: Introduce library to authenticate
 devices*

On Sun, 30 Jun 2024 21:42:00 +0200
Lukas Wunner <lukas@wunner.de> wrote:

> From: Jonathan Cameron <Jonathan.Cameron@huawei.com>
> 
They published a 1.3.1 since you sent this (1st July).

Given it happened to be the version I have to hand I'll review against
that.

A few minor things inline.


> diff --git a/lib/spdm/req-authenticate.c b/lib/spdm/req-authenticate.c
> new file mode 100644


> +static int spdm_validate_cert_chain(struct spdm_state *spdm_state, u8 slot)
> +{

I'd steal that pointer with no_free_ptr()

> +		cert = ERR_PTR(-ENOKEY);

I think this is clearer as NULL which you will get from no_free_ptr()


> +
> +		offset += length;

> +/**
> + * spdm_challenge_rsp_sz() - Calculate CHALLENGE_AUTH response size

Odd spacing.  Personally I'd not bother trying to align things other
than maybe the comments.


> +}
> +

Pull the declaration down here so we don't have fragility that
an error check might be added before here.
I'm lazy so not digging out the reference but Linus came down
clearly in favor of just using inline declarations to put the
constructor and destructor together.

> +	if (!rsp)
> +		return -ENOMEM;
It's probably overly paranoid but we could check some fields in the
response such as the slot..

> +	length = rc;
> +	rsp_sz = spdm_challenge_rsp_sz(spdm_state, rsp);

I never understood if you were actually allowed to do this without starting
the whole set again. Is there an example of multiple cert requesting
in the spec?  I vaguely recall poking our specification folk on this and
they couldn't give a clear answer so suggested doing whole sequence again
so the transcript matches the ones in the spec.

Logically I'd like it to work this way (and I assume libspdm does) but
I'd really like a reference or other argument for why...
The GET_CERTIFICATE / GET_CERTIFICATE_RESPONSE can definitely be multiple
messages to deal with large cert chains, but can we start again with a new
slot and still have the transcript updated correctly?

> +		rc = spdm_get_certificate(spdm_state, slot);
> +		if (rc)

Dan suggested a nice cleanup for this to avoid the
goto dance.

> +	return rc;
> +}



> diff --git a/lib/spdm/spdm.h b/lib/spdm/spdm.h
> new file mode 100644

Some of these 1.2 only entries are non obvious from the 1.3.1 spec.
This one for instance is in the change log as a 1.3.0 addition

> +#define SPDM_EP_INFO_CAP_MASK		GENMASK(23, 22) /* 1.3 */
> +#define   SPDM_EP_INFO_CAP_NO		0		/* 1.3 */


...

> +
> +#define SPDM_GET_CAPABILITIES 0xe1

Maybe should be consistent for resered fields in using u8 []
Doesn't matter much though.

> +	__le32 flags;					/* 1.1 */
> +	/* End of SPDM 1.1 structure */

As above.

> +	__le32 flags;
> +	/* End of SPDM 1.0 structure */


> +#define SPDM_CHALLENGE 0x83
> +#define SPDM_NONCE_SZ 32 /* SPDM 1.0.0 table 20 */
If we are matching the spec, oddly the response to a challenge request
is a challenge auth response.  Who knows why...

> +	u8 version;
> +	u8 code;

Do we want to add comment on Basic MutAuthrReq (deprecated) bit 7?
Might in theory bite us at somepoint.

> +	u8 param2; /* Slot mask */
> +	/*

> +/**
> + * struct spdm_state - SPDM session state
Two dev entries.

Make sure to run the kernel-doc script over the files to catch these little
dos issues.

...

> + */
> +struct spdm_state {

---

## [70] Jonathan Cameron — 2024-07-18
*Subject: Re: [PATCH v2 10/18] PCI/CMA: Reauthenticate devices on reset and
 resume*

On Wed, 10 Jul 2024 16:23:00 -0700
Dan Williams <dan.j.williams@intel.com> wrote:

> Lukas Wunner wrote:
> > CMA-SPDM state is lost when a device undergoes a Conventional Reset.

Feels like a policy question - maybe a static key (as Kees suggested for
the other question).  By all means default to on, but a latency sensitive
setup might opt out?  Or specific driver opt out might be an option
if we are allowing a driver managed flow (and the policy allows drivers
to opt out - we definitely want a policy option that doesn't allow
drivers to be part of the decision and indeed does what we have here).

Hope someone writes a nice guide to any policy choices that come out of
this.  Maybe the policy hooks don't belong in a first patch set though
as this one in particular is a performance optimization.

> 
> At a minimum I think pci_cma_reauthenticate() should do something like:

This seems reasonable as only possibility of change is that it can now
authenticate (maybe the reset was a firmware update...) and if we accepted
it before then no loss of security in not checking.  Userspace can then poke
the reauthenticate and reload the driver if relevant (maybe more functionality
will be enabled.)



Note the whole always try to authenticate first was outcome of one of the LPC
BoFs (2 years ago?).

Jonathan


>

---

## [71] Jonathan Cameron — 2024-07-18
*Subject: Re: [PATCH v2 11/18] PCI/CMA: Expose in sysfs whether devices are
 authenticated*

On Sun, 30 Jun 2024 21:46:00 +0200
Lukas Wunner <lukas@wunner.de> wrote:

> The PCI core has just been amended to authenticate CMA-capable devices
> on enumeration and store the result in an "authenticated" bit in struct

One question on a bit of error path cleanup that I can't immediately see
the reason for.

> diff --git a/drivers/pci/doe.c b/drivers/pci/doe.c
> index 34bb8f232799..0f94c4ed719e 100644

Why?  pci_cma_init() is currently called after pci_doe_init() so I don't
see why we need to disable here.  If we want a default of disabled, do that
before calling pci_doe_init() rather than in the error paths

1) Set default to disabled.
2) pci_doe_init()
3) pci_cma_init() - now not disabled.


>  			continue;
>  		}

---

## [72] Jonathan Cameron — 2024-07-18
*Subject: Re: [PATCH v2 12/18] PCI/CMA: Expose certificates in sysfs*

> >  
> > diff --git a/lib/spdm/req-sysfs.c b/lib/spdm/req-sysfs.c

That's still fragile. I'd use a container structure so that we can
get the number directly from container_of() and appropriate field
in the container structure.

> 
> > +

Or augment the attribute by sticking it in a container structure with the slot
number as data and use container_of().  Either path works fine and avoids the
fragility issue of using the naming.

>

---

## [73] Jonathan Cameron — 2024-07-18
*Subject: Re: [PATCH v2 12/18] PCI/CMA: Expose certificates in sysfs*

On Sun, 30 Jun 2024 21:47:00 +0200
Lukas Wunner <lukas@wunner.de> wrote:

> The kernel already caches certificate chains retrieved from a device
> upon authentication.  Expose them in "slot[0-7]" files in sysfs for
One trivial thing in addition to discussion in Dan's review thread.

Jonathan

> diff --git a/lib/spdm/req-authenticate.c b/lib/spdm/req-authenticate.c
> index 90f7a7f2629c..1f701d07ad46 100644

Move that to earlier patch.

---

## [74] Jonathan Cameron — 2024-07-18
*Subject: Re: [PATCH v2 13/18] sysfs: Allow bin_attributes to be added to
 groups*

On Sun, 30 Jun 2024 21:48:00 +0200
Lukas Wunner <lukas@wunner.de> wrote:

> Commit dfa87c824a9a ("sysfs: allow attributes to be added to groups")
> introduced dynamic addition of sysfs attributes to groups.
Reviewed-by: Jonathan Cameron <Jonathan.Cameron@huawei.com>

---

## [75] Jonathan Cameron — 2024-07-18
*Subject: Re: [PATCH v2 14/18] sysfs: Allow symlinks to be added between
 sibling groups*

On Sun, 30 Jun 2024 21:49:00 +0200
Lukas Wunner <lukas@wunner.de> wrote:

> A subsequent commit has the need to create a symlink from an attribute
> in a first group to an attribute in a second group.  Both groups belong

Nice in general. A few minor comments inline.


> ---
>  fs/sysfs/group.c       | 33 +++++++++++++++++++++++++++++++++

> + * @kobj:	The kobject containing the groups.
> + * @link_grp:	The name of the group in which to create the symlink.

Maybe should go with the link_name naming used in sysfs_add_link_to group.

> + * @target_grp:	The name of the target group.
> + * @target:	The name of the target attribute.

Maybe just define these when used (similar to earlier reviews)
rather than in one clump up here.  Given they are all doing the same
thing maybe it's not worth the effort though.


> +
> +	target_grp_kn = kernfs_find_and_get(kobj->sd, target_grp);

---

## [76] Jonathan Cameron — 2024-07-18
*Subject: Re: [PATCH v2 15/18] PCI/CMA: Expose a log of received signatures
 in sysfs*

On Sun, 30 Jun 2024 21:50:00 +0200
Lukas Wunner <lukas@wunner.de> wrote:

> When authenticating a device with CMA-SPDM, the kernel verifies the
> challenge-response received from the device, but otherwise keeps it to

Nice - particularly the thorough ABI docs.  A few trivial comments inline.
Reviewed-by: Jonathan Cameron <Jonathan.Cameron@huawei.com>


> +/**
> + * spdm_create_log_entry() - Allocate log entry for one received SPDM signature

We might set other bin_attr callbacks sometime in future, so I would
add the trailing comma and move the }, to the next line for these.

> +
> +		.req_nonce = {

Sanity check for roll over maybe? 

> +
> +	/* Steal transcript pointer ahead of spdm_free_transcript() */

As in previous reviews I'd keep constructor with destructor by declaring
these inline.

> +	struct spdm_log_entry *log;
> +

guard() perhaps.

> +	list_for_each_entry(log, &spdm_state->log, list) {
> +		struct kernfs_node *sig_kn __free(kernfs_put);

---

## [77] Jonathan Cameron — 2024-07-18
*Subject: Re: [PATCH v2 16/18] spdm: Limit memory consumed by log of received
 signatures*

On Sun, 30 Jun 2024 21:51:00 +0200
Lukas Wunner <lukas@wunner.de> wrote:

> The SPDM library has just been amended to keep a log of received
> signatures and expose it in sysfs.
Ah. This avoids potential problem in previous patch. Fair enough no need
to check the counter for overflow as long as it's not feasible to set that
sysctl high enough that we still get a collision.

LGTM 
Reviewed-by: Jonathan Cameron <Jonathan.Cameron@huawei.com>

---

## [78] Jonathan Cameron — 2024-07-18
*Subject: Re: [PATCH v2 17/18] spdm: Authenticate devices despite invalid
 certificate chain*

On Sun, 30 Jun 2024 21:52:00 +0200
Lukas Wunner <lukas@wunner.de> wrote:

> The SPDM library has just been amended to keep a log of received
> signatures from a device and expose it in sysfs.

That "or" seems odd..  Should it be "and"?

> 
> User space should be given the chance to make up its own mind on the
Code looks fine, but I'm also interested in whether this is useful
to anyone.  It's not something I care about currently.

Jonathan

---

## [79] Jonathan Cameron — 2024-07-18
*Subject: Re: [PATCH v2 18/18] spdm: Allow control of next requester nonce
 through sysfs*

On Sun, 30 Jun 2024 21:53:00 +0200
Lukas Wunner <lukas@wunner.de> wrote:

> Remote attestation services may mistrust the kernel to always use a
> fresh nonce for SPDM authentication.
Why is the group visibility callback in this patch?


Otherwise looks fine to me,

Jonathan


> ---
>  Documentation/ABI/testing/sysfs-devices-spdm | 29 ++++++++++++++++

---

## [80] Alexey Kardashevskiy — 2024-07-22
*Subject: Re: [PATCH v2 08/18] PCI/CMA: Authenticate devices on enumeration*

On 16/7/24 09:55, Jason Gunthorpe wrote:
> On Mon, Jul 15, 2024 at 04:37:01PM -0700, Dan Williams wrote:
>>> So from a Linux VM perspective we have a PCI device with an IOMMU,

(uff, quite a thread, I am catching up)

Why flipping?

If there is vIOMMU, then the driver in the VM can decide whether it 
wants private or shared memory for DMA, pass that new flag to dma_map() 
and 1) have DMA memory allocated from the private pool (== no page state 
changes) and 2) have C-bit set in the vIOMMU page table (which is in the 
VM memory).

It is without vIOMMU when flipping is sort of a problem but the driver 
in the VM can decide on type of DMA, talk to the TSM and only then 
enable DMA (==bus master) but by then the things in the HV are settled 
so we are ok.

Talking to the TSM does not really require DMA but even if it did, we 
could enable untrusted DMA, do this attestation step, then disable DMA, 
tell the HV/TSM to switch DMA to secure and enable DMA, all in the 
driver's probe().

> Changing the underlying behavior of the DMA API "in flight" while a
> driver is bound seems really dangerous.

Hard to imagine why would a driver want this :)

> My point is if we start baking in the assumption that drivers can do
> things like the above without addressing how the VIOMMU integration

My V1 says "all IOVA below X are private and above - shared" (which is a 
hw knob in absence of vIOMMU) and I set the X to all '1's just to mark 
it all private.

> 
> Jason

---

## [81] Jason Gunthorpe — 2024-07-22
*Subject: Re: [PATCH v2 08/18] PCI/CMA: Authenticate devices on enumeration*

On Mon, Jul 22, 2024 at 08:19:23PM +1000, Alexey Kardashevskiy wrote:

> If there is vIOMMU, then the driver in the VM can decide whether it wants
> private or shared memory for DMA, pass that new flag to dma_map() and 1)

Not all HW supports a flow like that.

> My V1 says "all IOVA below X are private and above - shared" (which is a hw
> knob in absence of vIOMMU) and I set the X to all '1's just to mark it all

Is that portable to other implementations?

Jason

---

## [82] Alexey Kardashevskiy — 2024-07-23
*Subject: Re: [PATCH v2 08/18] PCI/CMA: Authenticate devices on enumeration*

On 22/7/24 22:06, Jason Gunthorpe wrote:
> On Mon, Jul 22, 2024 at 08:19:23PM +1000, Alexey Kardashevskiy wrote:
> 

Fair point but still, under what imaginary circumstance a driver could 
decide to flip T=0/1 when up and running?


>> My V1 says "all IOVA below X are private and above - shared" (which is a hw
>> knob in absence of vIOMMU) and I set the X to all '1's just to mark it all

Well, when used as a big knob - 0 or the max (== flip private/shared), 
then yes :)

---

## [83] Jason Gunthorpe — 2024-07-23
*Subject: Re: [PATCH v2 08/18] PCI/CMA: Authenticate devices on enumeration*

On Tue, Jul 23, 2024 at 02:26:23PM +1000, Alexey Kardashevskiy wrote:
> 
> 

It seems some people are thinking they need to do T=0 stuff before
doing device attestation.

But that wasn't my point, the issue is that the translation is
different depending on T=0/1. On those implementations T=0 means "all
shared memory with no vIOMMU" and T=1 means "all memory with a
vIOMMU".

This is quite different from "the VM can decide whether it wants
private or shared memory", because it kind of can't. The entire device
is either T=0/1 and that is that.

Jason

---

## [84] Lukas Wunner — 2024-07-29
*Subject: Re: [PATCH v2 06/18] crypto: ecdsa - Support P1363 signature encoding*

On Mon, Jul 01, 2024 at 08:10:16AM +1000, Herbert Xu wrote:
> This should be implemented as a template.  Change ecdsa to use a
> "raw" encoding for r/s and then implement x962 and p1363 as templates

Understood, thank you for pointing me in the right direction.

I've just submitted a separate series for templatizing ecdsa
signature decoding:

https://lore.kernel.org/r/cover.1722260176.git.lukas@wunner.de/

Please let me know if this is what you had in mind.

Thanks!

Lukas

---

## [85] Alexey Kardashevskiy — 2025-02-11
*Subject: Re: [PATCH v2 00/18] PCI device authentication*

On 8/7/24 23:35, Lukas Wunner wrote:
> On Mon, Jul 08, 2024 at 07:47:51PM +1000, Alexey Kardashevskiy wrote:
>> On 1/7/24 05:35, Lukas Wunner wrote:


Has any further development happened since then? I am asking as I have 
the CMA-v2 in my TSM exercise tree (to catch conflicts, etc) but I do 
not see any change in your github or kernel.org/devsec since v2 and that 
v2 does not merge nicely with the current upstream. Thanks,



> Most patches in this series with a "PCI/CMA: " subject actually
> only change very few lines in the PCI core.  The bulk of the changes

---

## [86] Lukas Wunner — 2025-02-12
*Subject: Re: [PATCH v2 00/18] PCI device authentication*

On Tue, Feb 11, 2025 at 12:30:21PM +1100, Alexey Kardashevskiy wrote:
> > > On 1/7/24 05:35, Lukas Wunner wrote:
> > > > PCI device authentication v2

Please find a rebase of v2 on v6.14-rc2 on this branch:

https://github.com/l1k/linux/commits/doe

A portion of the crypto patches that were part of v2 have landed in v6.13.
So the rebased version has shrunk.

There was a bit of fallout caused by the upstreamed crypto patches
and dealing with that kept me occupied during the v6.13 cycle.
However I'm now back working on the PCI/CMA patches,
specifically the migration to netlink for retrieval of signatures
and measurements as discussed at Plumbers.

Thanks,

Lukas

---
