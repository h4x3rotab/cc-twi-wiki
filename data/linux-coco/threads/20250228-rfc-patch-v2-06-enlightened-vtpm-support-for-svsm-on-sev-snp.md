---
title: '[RFC PATCH v2 0/6] Enlightened vTPM support for SVSM on SEV-SNP'
date: 2025-02-28
last_reply: 2025-03-10
message_count: 45
participants: ['Stefano Garzarella', 'Jason Gunthorpe', 'Jarkko Sakkinen', 'Dionna Amalie Glaze', 'Tom Lendacky', 'Borislav Petkov']
---

## [1] Stefano Garzarella — 2025-02-28

I put RFC back in because we haven't yet decided if this is the best
approach to support SVSM vTPM, but I really like to receive feedbacks
especially from the maintainer/reviewers of the TPM subsystem, to see if
this approach is acceptable.

Also James, Claudio, I left some questions for you in patches 2 and 4,
since I reused your code, but I changed the context quite a bit, so for
now I reset the author and added C-o-b, but I'm not sure it's okay for you.

As requested, I try to add more context:

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

The first two patches add public APIs to use AMD SVSM vTPM.
They use SVSM_VTPM_QUERY call to probe for the vTPM device and
SVSM_VTPM_CMD call to execute vTPM operations as defined in the
AMD SVSM spec [3].

The third patch add a new send_recv() tpm_class_ops callback as suggested
by Jason to be used with devices that do not support interrupts and provide
a single operation to send the command and receive the response on the same
buffer.

The fourth patch adds an interface to talk to emulated devices via the TCG
reference implementation and then used by the fifth patch to implement the
SVSM vTPM driver. The sixth patch simply registers the platform device.

Since all SEV-SNP dependencies are now upstream, this series can be
applied directly to the Linus' tree.

These patches were tested in an AMD SEV-SNP guest running:
- a recent version of Coconut SVSM [4] containing an ephemeral vTPM
- a PoC [5] containing a stateful vTPM used for sealing/unsealing a LUKS key

Changelog:

v1 -> v2 RFC
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

Stefano Garzarella (6):
  x86/sev: add SVSM call macros for the vTPM protocol
  x86/sev: add SVSM vTPM probe/send_command functions
  tpm: add send_recv() ops in tpm_class_ops
  tpm: add interface to interact with devices based on TCG Simulator
  tpm: add SNP SVSM vTPM driver
  x86/sev: register tpm-svsm platform device

 arch/x86/include/asm/sev.h       |   7 ++
 include/linux/tpm.h              |   2 +
 include/linux/tpm_tcgsim.h       | 136 +++++++++++++++++++++++++++++++
 arch/x86/coco/sev/core.c         |  55 +++++++++++++
 drivers/char/tpm/tpm-interface.c |   8 +-
 drivers/char/tpm/tpm_svsm.c      | 120 +++++++++++++++++++++++++++
 drivers/char/tpm/Kconfig         |  10 +++
 drivers/char/tpm/Makefile        |   1 +
 8 files changed, 338 insertions(+), 1 deletion(-)
 create mode 100644 include/linux/tpm_tcgsim.h
 create mode 100644 drivers/char/tpm/tpm_svsm.c


base-commit: ac9c34d1e45a4c25174ced4fc0cfc33ff3ed08c7
prerequisite-patch-id: 46b3bb004bd044863a404b15d704b0ab5cb3adf3
prerequisite-patch-id: 6448736bc6cd561e6ddc10d21f43952a585c5657
prerequisite-patch-id: 9dd308a4f5a115129c6c1b403083651ade63a3de
prerequisite-patch-id: 0a97c8378dbe85c3547a39ecb008190b84c7e797
prerequisite-patch-id: 776de0155dee63ac4ad062e30c97ba09c2d3da83
prerequisite-patch-id: e0f8dda234962608edc6226074c8f1b177a9e8eb
prerequisite-patch-id: 9d957abb4542e6d5968b638b8e593e287a3018db
prerequisite-patch-id: 8e8a0d9828e2b76a80a749b99f88da395c831877
prerequisite-patch-id: 2549a12c40bca1c4f984abf247a1223348676c62
prerequisite-patch-id: 4f16ae35dae2290ebe784c8bb173922d85e3d1bb
prerequisite-patch-id: 12c769f55c189894f9e4a81978e8c3cbb0cf344b
prerequisite-patch-id: 4dae8c09727f2d9ba2eb49c274d04621b9651410
prerequisite-patch-id: e96507d220ebb1e6f32c6d8551eb5bc10d9b2d6f
prerequisite-patch-id: 3bc6b3c406f5ce6ca862ef62e8483fafc4b4ec88
prerequisite-patch-id: 57a35b09322e2cb4cffa6612b7c3384523c6235d
prerequisite-patch-id: db039fb5a3137ef06c3483840ded33f144f94acf
prerequisite-patch-id: 23b6c2faacb3d81ad087c569ea959b5862b0bb87
prerequisite-patch-id: 8e5d5fa9bc52f32532ca9723db5bcab0386e850d
prerequisite-patch-id: 7a6a804bc82fb058ee67392e6e468ae27023ae29
prerequisite-patch-id: ff86959f0d768eae5336288912823035f77609f9
prerequisite-patch-id: c3ebb29e9b269792ce0a7b46b657422777106d34
prerequisite-patch-id: f5e3de6141e5637587010201301d9d72cd97890a
prerequisite-patch-id: aded4f4affa33b2b9cf3247196280dd1d293a058
prerequisite-patch-id: 9b2acb5e0e86ebb7c4a61499e5f429393692e370
prerequisite-patch-id: cb08f24e1fd645370f6bb82ba0886aa0aff83bbf
prerequisite-patch-id: 2f41ac08e7779c81fd8f101c8796e1613a81739c
prerequisite-patch-id: cf8b634831df57eb9db1a68642934844d28d528c
prerequisite-patch-id: 914c0f3b919369a63759101879ea37728706cca7
prerequisite-patch-id: 8d3e72411f2a3bd3c8ba3b5551b92ab177689d62
prerequisite-patch-id: 26b64e4869e65950cb4760a37fa2ba991d771c28
prerequisite-patch-id: 1859575bea729b23e4936e8ef875a9de0bfc70ea
prerequisite-patch-id: f494c8149085ecbc106fa7335aed94d31c02d7c0
prerequisite-patch-id: 40b847f228570992cfbbba8f23b15172df9ab52e
prerequisite-patch-id: f78efee71866139b424e27b803bee565742f8a59
prerequisite-patch-id: cda7b586a4ddbbe74bb4c4fc009d8abad8d4d8c8
prerequisite-patch-id: 6862c1fea0d7449595527d981e9b5b7b02869a14
prerequisite-patch-id: f5fb751bf87f37baef653ed4b377c5921eee01fc
prerequisite-patch-id: 8cf70f391bea57332e1213c6e886763f2bc041b0
prerequisite-patch-id: 384a60f2f5ddff6455dd7a0855583acc941b3f34
prerequisite-patch-id: 40db4cf493393f9144098482eade1fa86af02d4d
prerequisite-patch-id: 9cedf11607dc4cfca44ab5309444889bd4659b23
prerequisite-patch-id: 93d8536a3f2c81978b73d322b3e479aafadcb672
prerequisite-patch-id: 5f9c2f1b1e7d896c49b1b45a148f19b40b887248
prerequisite-patch-id: 86a2350095820314ff778c848669419975886370
prerequisite-patch-id: eabfaf40df547e88d3afe7cf5aa644fd23baa611
prerequisite-patch-id: 60aaecfd948b2cd54cbf1db649789170f9883002
prerequisite-patch-id: 161a1c31a55741b14613fcea7818746482bc7633
prerequisite-patch-id: 4be263ce33796df2b89b11a4bba1f1505840b970
prerequisite-patch-id: 85a0fc5a0963f2794ad148d33b23e8a6a7bf4209
prerequisite-patch-id: df6f925e58999583d8f26f4c6956c7e68d1a3ac5
prerequisite-patch-id: 7a817e7b23e1583e23dee2235be954cbdce6ef52
prerequisite-patch-id: 580827936003011c14917c4c2ebf302d1aaac3cb
prerequisite-patch-id: b4730418ea0df499c0bbebcf4d891bd32dbbcadb
prerequisite-patch-id: dc8277acf8a53927ef1ef35cc5e00753f2aa403f
prerequisite-patch-id: 9e3a142dee392a0ecbcc12784ccd83a709393085
prerequisite-patch-id: ccfb87f2935ec4d801f77def75803cfb8fdc3284
prerequisite-patch-id: c84ff30a6f578b641b7d9fc2c1a4a04925046c07
prerequisite-patch-id: 5bcce2542b9969633e0629f81be10dbb8bd692f6
prerequisite-patch-id: b0410e17e89b77719d801f6a86e367f9cda6524d
prerequisite-patch-id: 6809f0f4f5a657b6c6c69d548f8e5585b4aa3bd8
prerequisite-patch-id: f347001242aa07e52b27b4aac3bd51e2a9ccd969
prerequisite-patch-id: 2604b8e195ad9ad8cfa896e09d7d87c7114ad050
prerequisite-patch-id: 82625989e67c3c0a42f37f6148f108955330a3c8
prerequisite-patch-id: d7a34ae135becb97eeacaf6039295ed9c394cb26
prerequisite-patch-id: 3afe6b2a2fde5e713601b0df5d50435d40a3bb37
prerequisite-patch-id: 09aa6359e40fc4658db4581301a782e53c174d4d
prerequisite-patch-id: 3f833b1be3fb9890617802e28fa19e7383bb0d2f
prerequisite-patch-id: 509339bee2ca8da4bc851e29079a15ff81ec0c7b
prerequisite-patch-id: aa00b8e789f29936d2006cbdb14ba221a355d8ee
prerequisite-patch-id: 520064842ff26fb20a47399602ad2c1dab5895dc
prerequisite-patch-id: ffc71ff6ba4ff6aa165613420c94c2fb502083b4
prerequisite-patch-id: f53ec70257559bbd20d3d70426ebf32be55ee1fc
prerequisite-patch-id: 63f833233f2f563950f62e3ae0e738420e41e6bf
prerequisite-patch-id: a497894b0fe12ec4c52ecc6d1403c08d014f138b
prerequisite-patch-id: 0d38ff6d0fdb057d83749721c06d7e04156d53ce
prerequisite-patch-id: 2388b49b66051dc3120eca75d663dce059ce5eca
prerequisite-patch-id: 520f30d4408e1878d798cb4189c2496f63898147
prerequisite-patch-id: e675f425948372b45c2edc04fd050be960a551e9
prerequisite-patch-id: 0aa98f774107e4591a2afc12ba6be883c1a34e73
prerequisite-patch-id: b00b1f4a4213f6a58fc074088f414198d2eeabaf
prerequisite-patch-id: 17098f00d571080ebce81e0720ad4d9fb9aac64e
prerequisite-patch-id: dc2c08a314fc2bd9ffe05c9ff0bc8442079062fb
prerequisite-patch-id: d87f4aeeb50fffb2458018e8280e70d7bbaad859
prerequisite-patch-id: 6b5e2e247b92dbb307b67e2bdbc6558328119755
prerequisite-patch-id: 11889a6cee65fc3a250381045c120b39060158fb
prerequisite-patch-id: 6f3013bb99b7747c54488395d0ac815e5beec7f3
prerequisite-patch-id: 8fb5d94c890967f11c626e5a26aa50a7e87a0689
prerequisite-patch-id: f753b6aa34bbe6675a810aa7e9f5a46bd6f8f3f8
prerequisite-patch-id: 23e13c044f53fddead4c4e7906d1fd3d36f4a38b
prerequisite-patch-id: 671f9588d17aebb0cc3dd824df196dc5b11ddc82
prerequisite-patch-id: 820a1403805a5892a8cc524960a28c64f9c9141d
prerequisite-patch-id: 92c96e640574d9351f22854a926f3252047e2366
prerequisite-patch-id: 0842ca6be6e6f1516797be8445eef3db6da9191b
prerequisite-patch-id: 5e713ef45b4467792deed932f3c88cc28c65a87f
prerequisite-patch-id: 018699af6673b5e68f91b15f851085febe645de6
prerequisite-patch-id: 5a2726fd0f676d19f9acea73521ba303fa9097ad
prerequisite-patch-id: c9a993ef4a6ba2f497aff0c790fe68b6da1ff53b
prerequisite-patch-id: 536149fa9ba99fc70926409b736c6c5383f7896b
prerequisite-patch-id: 0c9a37733251c55d7e12cdf68403b5e5e0f424ef
prerequisite-patch-id: 2df5ee9c2ccd3a87f0dcd1b8b6c0e31899b8c095
prerequisite-patch-id: e6d17eea6658913932b1fc7bd4860a86d670b360
prerequisite-patch-id: 96ae72d3ad07fbc884a733d39e7f67b2f26be24a
prerequisite-patch-id: d6165a80a726f18e2d807b935e3a9778aaf39b69
prerequisite-patch-id: dd32309c586ea3322992a866b5b53aff74111dd5
prerequisite-patch-id: 3a98988c76cc915f621135bf0835951dc33022af
prerequisite-patch-id: ea9d299351cf85a2705ac042cd9a73a90f3bef86
prerequisite-patch-id: ee8f1635bb0961f027355d23bf28bf14bf945cf8
prerequisite-patch-id: c4619dd03f29f1b52694dbffb2d474c519a8cc71
prerequisite-patch-id: 1f6e4e43695fc8a9ba08962e8f6eb4113b24a6c0
prerequisite-patch-id: e01e23c6bcc7d5441aa58f3b7b92324d0dd261f3
prerequisite-patch-id: bede20cdd06b49f7f597feafaffec54f78bd545a
prerequisite-patch-id: acefd770d66151a76d2d9a0c24acfd8298cbf01c
prerequisite-patch-id: 25deaeae53c6ccde2dab5992032e0b0076e8ff75
prerequisite-patch-id: 3fb34ce6400e2ad5c181c8d74d8a868cef98f642
prerequisite-patch-id: ce7b927531beaaf400f212f4ea9278793e0e02be
prerequisite-patch-id: 4974f215f056d8c69066ed7dafc53c665f773bd8
prerequisite-patch-id: fd2d88bdc268b146f4c1c8b77f22f1306735365d
prerequisite-patch-id: 5410bd3eaa7b3cbf851cca45739e4f90563611ee
prerequisite-patch-id: 51602abbab6a2f787672464a0dc675a7a3a479ce
prerequisite-patch-id: 51b3769fcd6e6f646434e0892880d706ec51db8c
prerequisite-patch-id: 99586bd8c136330bae2cf184cadd6825ab9f30b6
prerequisite-patch-id: c1d59f2a4e0d37ac6d1a03fcf3754dd142df0a30

---

## [2] Stefano Garzarella — 2025-02-28
*Subject: [RFC PATCH v2 1/6] x86/sev: add SVSM call macros for the vTPM protocol*

Add macros for SVSM_VTPM_QUERY and SVSM_VTPM_CMD calls as defined
in the "Secure VM Service Module for SEV-SNP Guests"
Publication # 58019 Revision: 1.00

Link: https://www.amd.com/content/dam/amd/en/documents/epyc-technical-docs/specifications/58019.pdf
Signed-off-by: Stefano Garzarella <sgarzare@redhat.com>
---
 arch/x86/include/asm/sev.h | 4 ++++
 1 file changed, 4 insertions(+)

diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index 1581246491b5..f6ebf4492606 100644
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

---

## [3] Stefano Garzarella — 2025-02-28
*Subject: [RFC PATCH v2 2/6] x86/sev: add SVSM vTPM probe/send_command functions*

Add two new functions to probe and send commands to the SVSM vTPM.
They leverage the two calls defined by the AMD SVSM specification
for the vTPM protocol: SVSM_VTPM_QUERY and SVSM_VTPM_CMD.

Expose these functions to be used by other modules such as a tpm
driver.

Co-developed-by: James Bottomley <James.Bottomley@HansenPartnership.com>
Signed-off-by: James Bottomley <James.Bottomley@HansenPartnership.com>
Co-developed-by: Claudio Carvalho <cclaudio@linux.ibm.com>
Signed-off-by: Claudio Carvalho <cclaudio@linux.ibm.com>
Signed-off-by: Stefano Garzarella <sgarzare@redhat.com>
---
James, Claudio are you fine with the Cdb, Sob?
The code is pretty much similar to what was in the initial RFC, but I
changed the context for that I reset the author but added C-o-b.
Please, let me know if this is okay or if I need to do anything
else (reset the author, etc.)
---
 arch/x86/include/asm/sev.h |  3 +++
 arch/x86/coco/sev/core.c   | 47 ++++++++++++++++++++++++++++++++++++++
 2 files changed, 50 insertions(+)

diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index f6ebf4492606..e379bcdddf07 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -485,6 +485,9 @@ void snp_msg_free(struct snp_msg_desc *mdesc);
 int snp_send_guest_request(struct snp_msg_desc *mdesc, struct snp_guest_req *req,
 			   struct snp_guest_request_ioctl *rio);
 
+bool snp_svsm_vtpm_probe(void);
+int snp_svsm_vtpm_send_command(u8 *buffer);
+
 void __init snp_secure_tsc_prepare(void);
 void __init snp_secure_tsc_init(void);
 
diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index 82492efc5d94..4158e447d645 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -2628,6 +2628,53 @@ static int snp_issue_guest_request(struct snp_guest_req *req, struct snp_req_dat
 	return ret;
 }
 
+bool snp_svsm_vtpm_probe(void)
+{
+	struct svsm_call call = {};
+	u64 send_cmd_mask = 0;
+	u64 platform_cmds;
+	u64 features;
+	int ret;
+
+	/* The vTPM device is available only if we have a SVSM */
+	if (!snp_vmpl)
+		return false;
+
+	call.caa = svsm_get_caa();
+	call.rax = SVSM_VTPM_CALL(SVSM_VTPM_QUERY);
+
+	ret = svsm_perform_call_protocol(&call);
+
+	if (ret != SVSM_SUCCESS)
+		return false;
+
+	features = call.rdx_out;
+	platform_cmds = call.rcx_out;
+
+	/* No feature supported, it should be zero */
+	if (features)
+		pr_warn("SNP SVSM vTPM unsupported features: 0x%llx\n",
+			features);
+
+	/* TPM_SEND_COMMAND - platform command 8 */
+	send_cmd_mask = 1 << 8;
+
+	return (platform_cmds & send_cmd_mask) == send_cmd_mask;
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

## [4] Stefano Garzarella — 2025-02-28
*Subject: [RFC PATCH v2 3/6] tpm: add send_recv() ops in tpm_class_ops*

Some devices do not support interrupts and provide a single operation
to send the command and receive the response on the same buffer.

To support this scenario, a driver could set TPM_CHIP_FLAG_IRQ in the
chip's flags to get recv() to be called immediately after send() in
tpm_try_transmit().

Instead of abusing TPM_CHIP_FLAG_IRQ, introduce a new callback
send_recv(). If that callback is defined, it is called in
tpm_try_transmit() to send the command and receive the response on
the same buffer in a single call.

Suggested-by: Jason Gunthorpe <jgg@ziepe.ca>
Signed-off-by: Stefano Garzarella <sgarzare@redhat.com>
---
 include/linux/tpm.h              | 2 ++
 drivers/char/tpm/tpm-interface.c | 8 +++++++-
 2 files changed, 9 insertions(+), 1 deletion(-)

diff --git a/include/linux/tpm.h b/include/linux/tpm.h
index 20a40ade8030..2ede8e0592d3 100644
--- a/include/linux/tpm.h
+++ b/include/linux/tpm.h
@@ -88,6 +88,8 @@ struct tpm_class_ops {
 	bool (*req_canceled)(struct tpm_chip *chip, u8 status);
 	int (*recv) (struct tpm_chip *chip, u8 *buf, size_t len);
 	int (*send) (struct tpm_chip *chip, u8 *buf, size_t len);
+	int (*send_recv)(struct tpm_chip *chip, u8 *buf, size_t buf_len,
+			 size_t to_send);
 	void (*cancel) (struct tpm_chip *chip);
 	u8 (*status) (struct tpm_chip *chip);
 	void (*update_timeouts)(struct tpm_chip *chip,
diff --git a/drivers/char/tpm/tpm-interface.c b/drivers/char/tpm/tpm-interface.c
index b1daa0d7b341..4f92b0477696 100644
--- a/drivers/char/tpm/tpm-interface.c
+++ b/drivers/char/tpm/tpm-interface.c
@@ -82,6 +82,9 @@ static ssize_t tpm_try_transmit(struct tpm_chip *chip, void *buf, size_t bufsiz)
 		return -E2BIG;
 	}
 
+	if (chip->ops->send_recv)
+		goto out_recv;
+
 	rc = chip->ops->send(chip, buf, count);
 	if (rc < 0) {
 		if (rc != -EPIPE)
@@ -123,7 +126,10 @@ static ssize_t tpm_try_transmit(struct tpm_chip *chip, void *buf, size_t bufsiz)
 	return -ETIME;
 
 out_recv:
-	len = chip->ops->recv(chip, buf, bufsiz);
+	if (chip->ops->send_recv)
+		len = chip->ops->send_recv(chip, buf, bufsiz, count);
+	else
+		len = chip->ops->recv(chip, buf, bufsiz);
 	if (len < 0) {
 		rc = len;
 		dev_err(&chip->dev, "tpm_transmit: tpm_recv: error %d\n", rc);

---

## [5] Stefano Garzarella — 2025-02-28
*Subject: [RFC PATCH v2 4/6] tpm: add interface to interact with devices based on TCG Simulator*

This is primarily designed to support an enlightened driver for the
AMD SVSM based vTPM, but it could be used by any TPM driver which
communicates with a TPM device implemented through the TCG TPM reference
implementation (https://github.com/TrustedComputingGroup/TPM)

Co-developed-by: James Bottomley <James.Bottomley@HansenPartnership.com>
Signed-off-by: James Bottomley <James.Bottomley@HansenPartnership.com>
Co-developed-by: Claudio Carvalho <cclaudio@linux.ibm.com>
Signed-off-by: Claudio Carvalho <cclaudio@linux.ibm.com>
Signed-off-by: Stefano Garzarella <sgarzare@redhat.com>
---
James, Claudio are you fine with the Cdb, Sob?
The code is based to what was in the initial RFC, but I removed the
tpm_platform module, moved some code in the header, changed some names,
etc.
For these reasons I reset the author but added C-o-b.
Please, let me know if this is okay or if I need to do anything
else (reset the author, etc.)
---
 include/linux/tpm_tcgsim.h | 136 +++++++++++++++++++++++++++++++++++++
 1 file changed, 136 insertions(+)
 create mode 100644 include/linux/tpm_tcgsim.h

diff --git a/include/linux/tpm_tcgsim.h b/include/linux/tpm_tcgsim.h
new file mode 100644
index 000000000000..bd5b123c393b
--- /dev/null
+++ b/include/linux/tpm_tcgsim.h
@@ -0,0 +1,136 @@
+/* SPDX-License-Identifier: GPL-2.0-only */
+/*
+ * Copyright (C) 2023 James.Bottomley@HansenPartnership.com
+ * Copyright (C) 2025 Red Hat, Inc. All Rights Reserved.
+ *
+ * Generic interface usable by TPM drivers interacting with devices
+ * implemented through the TCG Simulator.
+ */
+#ifndef _TPM_TCGSIM_H_
+#define _TPM_TCGSIM_H_
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
+#define TPM_TCGSIM_MAX_BUFFER		4096 /* max req/resp buffer size */
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
+ * tpm_tcgsim_fill_send_cmd() - fill a struct tpm_send_cmd_req to be sent to the
+ * TCG Simulator.
+ * @req: The struct tpm_send_cmd_req to fill
+ * @locality: The locality
+ * @buf: The buffer from where to copy the payload of the command
+ * @len: The size of the buffer
+ *
+ * Return: 0 on success, negative error code on failure.
+ */
+static inline int
+tpm_tcgsim_fill_send_cmd(struct tpm_send_cmd_req *req, u8 locality,
+			 const u8 *buf, size_t len)
+{
+	if (len > TPM_TCGSIM_MAX_BUFFER - sizeof(*req))
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
+ * tpm_tcgsim_parse_send_cmd() - Parse a struct tpm_send_cmd_resp received from
+ * the TCG Simulator
+ * @resp: The struct tpm_send_cmd_resp to parse
+ * @buf: The buffer where to copy the response
+ * @len: The size of the buffer
+ *
+ * Return: buffer size filled with the response on success, negative error
+ * code on failure.
+ */
+static inline int
+tpm_tcgsim_parse_send_cmd(const struct tpm_send_cmd_resp *resp, u8 *buf,
+			  size_t len)
+{
+	if (len < resp->hdr.size)
+		return -E2BIG;
+
+	if (resp->hdr.size > TPM_TCGSIM_MAX_BUFFER - sizeof(*resp))
+		return -EINVAL;  // Invalid response from the platform TPM
+
+	memcpy(buf, resp->outbuf, resp->hdr.size);
+
+	return resp->hdr.size;
+}
+
+#endif /* _TPM_TCGSIM_H_ */

---

## [6] Stefano Garzarella — 2025-02-28
*Subject: [RFC PATCH v2 6/6] x86/sev: register tpm-svsm platform device*

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
index 4158e447d645..7e91fae7d43a 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -2680,6 +2680,11 @@ static struct platform_device sev_guest_device = {
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
@@ -2688,6 +2693,9 @@ static int __init snp_init_platform_device(void)
 	if (platform_device_register(&sev_guest_device))
 		return -ENODEV;
 
+	if (platform_device_register(&tpm_svsm_device))
+		return -ENODEV;
+
 	pr_info("SNP guest platform device initialized.\n");
 	return 0;
 }

---

## [7] Jason Gunthorpe — 2025-02-28
*Subject: Re: [RFC PATCH v2 5/6] tpm: add SNP SVSM vTPM driver*

On Fri, Feb 28, 2025 at 06:07:19PM +0100, Stefano Garzarella wrote:
> +/*
> + * tpm_svsm_remove() lives in .exit.text. For drivers registered via

??? Is that really true? I didn't know that

I thought you could unbind anything using /sys/../unbind?

Jason

---

## [8] Jason Gunthorpe — 2025-02-28
*Subject: Re: [RFC PATCH v2 0/6] Enlightened vTPM support for SVSM on SEV-SNP*

On Fri, Feb 28, 2025 at 06:07:14PM +0100, Stefano Garzarella wrote:
> I put RFC back in because we haven't yet decided if this is the best
> approach to support SVSM vTPM, but I really like to receive feedbacks

I didn't look in high detail, but the overall shape is what I was
thinking about in our previous conversations. Very little TPM code is
under arch/, we have a nice simplifying helper in the core code, and
you have a tidy platform device to tie it all together.

Jason

---

## [9] Jarkko Sakkinen — 2025-03-01
*Subject: Re: [RFC PATCH v2 3/6] tpm: add send_recv() ops in tpm_class_ops*

On Fri, Feb 28, 2025 at 06:07:17PM +0100, Stefano Garzarella wrote:
> +	int (*send_recv)(struct tpm_chip *chip, u8 *buf, size_t buf_len,
> +			 size_t to_send);

Please describe the meaning and purpose of to_send.

BR, Jarkko

---

## [10] Jarkko Sakkinen — 2025-03-01
*Subject: Re: [RFC PATCH v2 4/6] tpm: add interface to interact with devices
 based on TCG Simulator*

On Fri, Feb 28, 2025 at 06:07:18PM +0100, Stefano Garzarella wrote:
> This is primarily designed to support an enlightened driver for the

The commit message is half-way cut.

I.e. it lacks the explanation of "this".

> AMD SVSM based vTPM, but it could be used by any TPM driver which
> communicates with a TPM device implemented through the TCG TPM reference

We should not be dependent on any out-of-tree headers.

> + */
> +

This commit got me lost tbh.

BR, Jarkko

---

## [11] Jarkko Sakkinen — 2025-03-01
*Subject: Re: [RFC PATCH v2 5/6] tpm: add SNP SVSM vTPM driver*

On Fri, Feb 28, 2025 at 06:07:19PM +0100, Stefano Garzarella wrote:
> Add driver for the vTPM defined by the AMD SVSM spec [1].
> 

Why? Please don't.

> 
> The device cannot be hot-plugged/unplugged as it is emulated by the

OK, so this is like ARM's driver architecture using SMC, and I think
tpm_ftpm_tee is probably one great reflection for this overall. Is this
correct analysis, or not?

BR, Jarkko

---

## [12] Dionna Amalie Glaze — 2025-02-28
*Subject: Re: [RFC PATCH v2 5/6] tpm: add SNP SVSM vTPM driver*

On Fri, Feb 28, 2025 at 5:51 PM Jarkko Sakkinen <jarkko@kernel.org> wrote:
>
> On Fri, Feb 28, 2025 at 06:07:19PM +0100, Stefano Garzarella wrote:

Using ftpm is really obtuse, at least with my attempt
https://github.com/deeglaze/amdese-linux/tree/svsmftpm
I don't really know how to cleanly bind the platform_driver to the one device.
I don't think that this is any way better than what this patch series proposes.

>
> BR, Jarkko

---

## [13] Tom Lendacky — 2025-03-03
*Subject: Re: [RFC PATCH v2 3/6] tpm: add send_recv() ops in tpm_class_ops*

On 2/28/25 11:07, Stefano Garzarella wrote:
> Some devices do not support interrupts and provide a single operation
> to send the command and receive the response on the same buffer.

It might look a bit cleaner if you issue the send_recv() call here and
then jump to a new label after the recv() call just before 'len' is checked.

Thanks,
Tom

> +
>  	rc = chip->ops->send(chip, buf, count);

---

## [14] Tom Lendacky — 2025-03-03
*Subject: Re: [RFC PATCH v2 4/6] tpm: add interface to interact with devices
 based on TCG Simulator*

On 2/28/25 11:07, Stefano Garzarella wrote:
> This is primarily designed to support an enlightened driver for the
> AMD SVSM based vTPM, but it could be used by any TPM driver which

This is a confusing name... would tpm_tcgsim_parse_cmd_resp() be a
better name?

Thanks,
Tom

> +{
> +	if (len < resp->hdr.size)

---

## [15] Stefano Garzarella — 2025-03-03
*Subject: Re: [RFC PATCH v2 5/6] tpm: add SNP SVSM vTPM driver*

On Fri, Feb 28, 2025 at 08:28:19PM -0400, Jason Gunthorpe wrote:
>On Fri, Feb 28, 2025 at 06:07:19PM +0100, Stefano Garzarella wrote:
>> +/*

I initially followed drivers/virt/coco/sev-guest/sev-guest.c to figure 
out how to clean a driver registered with 
module_platform_driver_probe(), then I saw that pattern with the same 
comment is used in several other drivers.

>
>I thought you could unbind anything using /sys/../unbind?

I can't see `unbind` for this driver:

   $ ls /sys/bus/platform/drivers/tpm-svsm/
   module	tpm-svsm  uevent

While I can see it for example for others like fw_cfg:

   $ ls /sys/bus/platform/drivers/fw_cfg
   bind  module  QEMU0002:00  uevent  unbind

BTW I can unload the `tpm-svsm` module. Loading it again will cause 
issues if I don't have a remove function that calls 
tpm_chip_unregister().

Thanks,
Stefano

---

## [16] Stefano Garzarella — 2025-03-03
*Subject: Re: [RFC PATCH v2 0/6] Enlightened vTPM support for SVSM on SEV-SNP*

On Fri, Feb 28, 2025 at 08:30:09PM -0400, Jason Gunthorpe wrote:
>On Fri, Feb 28, 2025 at 06:07:14PM +0100, Stefano Garzarella wrote:
>> I put RFC back in because we haven't yet decided if this is the best

Thank you so much for taking a look and confirming that I understood 
your suggestions correctly!

Stefano

---

## [17] Stefano Garzarella — 2025-03-03
*Subject: Re: [RFC PATCH v2 3/6] tpm: add send_recv() ops in tpm_class_ops*

On Sat, Mar 01, 2025 at 03:45:10AM +0200, Jarkko Sakkinen wrote:
>On Fri, Feb 28, 2025 at 06:07:17PM +0100, Stefano Garzarella wrote:
>> +	int (*send_recv)(struct tpm_chip *chip, u8 *buf, size_t buf_len,

Sure, I'll add in the commit description.

Should I add documentation in the code as well?

The other callbacks don't have that, but if you think it's useful we can 
start with that, I mean something like this:

	/**
	 * send_recv() - send the command and receive the response on the same
	 * buffer in a single call.
	 *
	 * @chip: The TPM chip
	 * @buf: A buffer used to both send the command and receive the response
	 * @buf_len: The size of the buffer
	 * @to_send: Number of bytes in the buffer to send
	 *
	 * Return: number of received bytes on success, negative error code on
	 *         failure.
	 */
	int (*send_recv)(struct tpm_chip *chip, u8 *buf, size_t buf_len,
			 size_t to_send);

Thanks,
Stefano

---

## [18] Stefano Garzarella — 2025-03-03
*Subject: Re: [RFC PATCH v2 4/6] tpm: add interface to interact with devices
 based on TCG Simulator*

On Sat, Mar 01, 2025 at 03:48:35AM +0200, Jarkko Sakkinen wrote:
>On Fri, Feb 28, 2025 at 06:07:18PM +0100, Stefano Garzarella wrote:
>> This is primarily designed to support an enlightened driver for the

Yes, sorry, I rephrased James' previous commit description, but I admit 
it didn't come out clear.

I meant to say that "this" new header contains useful functions for 
creating commands and parsing responses in those drivers where vTPM 
devices are implemented via the TCG TPM reference implementation.

>
>> AMD SVSM based vTPM, but it could be used by any TPM driver which

We might see that header as a specification of how to communicate with 
the device.

What do you suggest we do in this case?

>
>> + */

The vTPM device is emulated through the simulator of the TCG reference 
implementation, so to communicate with it we have to send commands 
following the specified format.

This header is intended to add code that could also be reused by other 
drivers where the device follows this format. As James mentioned, 
Microsoft has something similar for OpenHCL and may reuse this header in 
the future.

If you think it is too much, I can include these things for now in 
tpm-svsm.c and when we have another driver we will pull them out.

Thanks,
Stefano

---

## [19] Stefano Garzarella — 2025-03-03
*Subject: Re: [RFC PATCH v2 5/6] tpm: add SNP SVSM vTPM driver*

On Sat, Mar 01, 2025 at 03:51:46AM +0200, Jarkko Sakkinen wrote:
>On Fri, Feb 28, 2025 at 06:07:19PM +0100, Stefano Garzarella wrote:
>> Add driver for the vTPM defined by the AMD SVSM spec [1].

You mean it's better not to have the external header and have all the 
functions here to prepare commands and parse responses?

As I mentioned, I did this because there may be other future drivers 
that could use it to talk to emulated devices in the same way, that is, 
through the TCG TPM reference implementation,

>
>>

I just took a closer look at what ARM SMC is, and yes, it looks like a 
correct analysis.

Dionna took a look at reusing ftpm and already replied with her 
analysis, better to continue in that thread the discussion on eventually 
reusing ftpm.

Thanks,
Stefano

---

## [20] Stefano Garzarella — 2025-03-03
*Subject: Re: [RFC PATCH v2 3/6] tpm: add send_recv() ops in tpm_class_ops*

On Mon, Mar 03, 2025 at 08:06:43AM -0600, Tom Lendacky wrote:
>On 2/28/25 11:07, Stefano Garzarella wrote:
>> Some devices do not support interrupts and provide a single operation

Yep, I see, I was undecided to avoid adding a new label and just have 
out_recv which in future cases always handles the send_recv() case.
But maybe I overthought, I will do as you suggest.

Thanks,
Stefano

>
>Thanks,

---

## [21] Stefano Garzarella — 2025-03-03
*Subject: Re: [RFC PATCH v2 4/6] tpm: add interface to interact with devices
 based on TCG Simulator*

On Mon, Mar 03, 2025 at 08:28:45AM -0600, Tom Lendacky wrote:
>On 2/28/25 11:07, Stefano Garzarella wrote:
>> This is primarily designed to support an enlightened driver for the

Ack, and we can rename also the other in tpm_tcgsim_fill_cmd_req().

Thanks,
Stefano

---

## [22] Jason Gunthorpe — 2025-03-03
*Subject: Re: [RFC PATCH v2 5/6] tpm: add SNP SVSM vTPM driver*

On Mon, Mar 03, 2025 at 05:19:05PM +0100, Stefano Garzarella wrote:
> On Fri, Feb 28, 2025 at 08:28:19PM -0400, Jason Gunthorpe wrote:
> > On Fri, Feb 28, 2025 at 06:07:19PM +0100, Stefano Garzarella wrote:

Wow, I didn't know that could be done

> BTW I can unload the `tpm-svsm` module.

Unload the module and implicitly unbound the driver

But not manually unbind the driver?? Huh? That seems pretty wrong..

> Loading it again will cause issues if I don't have a remove function
> that calls tpm_chip_unregister().

You definately need the remove function call doing what you have, it
is just surprising to me that there is a case where you can statically
know it is not callable..

Jason

---

## [23] Stefano Garzarella — 2025-03-04
*Subject: Re: [RFC PATCH v2 4/6] tpm: add interface to interact with devices
 based on TCG Simulator*

On Sat, Mar 01, 2025 at 03:48:35AM +0200, Jarkko Sakkinen wrote:
>On Fri, Feb 28, 2025 at 06:07:18PM +0100, Stefano Garzarella wrote:
>> This is primarily designed to support an enlightened driver for the

Now I understand why you got lost, my bad!
I checked further and these structures seem to be specific to the vTPM 
protocol defined by AMD SVSM specification and independent of TCG TPM 
(unless reusing some definitions like TPM_SEND_COMMAND).

At this point I think it is best to remove this header (or move in 
x86/sev) and move this rewrap to x86/sev to avoid confusion.

I'll do in v3, sorry for the confusion.

Stefano

---

## [24] Jarkko Sakkinen — 2025-03-04
*Subject: Re: [RFC PATCH v2 3/6] tpm: add send_recv() ops in tpm_class_ops*

On Mon, 2025-03-03 at 17:21 +0100, Stefano Garzarella wrote:
> On Sat, Mar 01, 2025 at 03:45:10AM +0200, Jarkko Sakkinen wrote:
> > On Fri, Feb 28, 2025 at 06:07:17PM +0100, Stefano Garzarella wrote:

It's always a command, right? So better be more concerete than
"to_send", e.g. "cmd_len".

I'd do instead:

if (!chip->send)
	goto out_recv;

And change recv into:

int (*recv)(struct tpm_chip *chip, u8 *buf, size_t buf_len,
	    cmd_len);

Those who don't need the last parameter, can ignore it.

This also reduces meaningless possible states for the ops structure
such as "send_recv and send or recv defined", i.e. makes it overall
more mutually exclusive.


> 
> Should I add documentation in the code as well?

I would not document in callback level as their implementation is not global.
This is probably stance also taken by file_operations, vm_ops and many other
places with "ops" structure.

> 
> Thanks,

BR, Jarkko

---

## [25] Jarkko Sakkinen — 2025-03-04
*Subject: Re: [RFC PATCH v2 4/6] tpm: add interface to interact with devices
 based on TCG Simulator*

On Tue, Mar 04, 2025 at 04:23:51PM +0100, Stefano Garzarella wrote:
> > This commit got me lost tbh.
> 

No need for apologies, just merely reporting what I do or do not
understand with brutal honesty ;-)

> I checked further and these structures seem to be specific to the vTPM
> protocol defined by AMD SVSM specification and independent of TCG TPM

Yeah, I do agree. We can commit to SVSM specification because that
is the target of this driver anyhow (not Microsoft simulator) :-)

> 
> I'll do in v3, sorry for the confusion.

Absolutely, np.

> 
> Stefano

BR, Jarkko

---

## [26] Jarkko Sakkinen — 2025-03-04
*Subject: Re: [RFC PATCH v2 5/6] tpm: add SNP SVSM vTPM driver*

On Mon, Mar 03, 2025 at 05:46:16PM +0100, Stefano Garzarella wrote:
> On Sat, Mar 01, 2025 at 03:51:46AM +0200, Jarkko Sakkinen wrote:
> > On Fri, Feb 28, 2025 at 06:07:19PM +0100, Stefano Garzarella wrote:

Sorry about harsh comment. I think we discussed this (MS simulator
caused confusion). Anchor this to SVSM spec and we're fine.

BR, Jarkko

---

## [27] Jarkko Sakkinen — 2025-03-04
*Subject: Re: [RFC PATCH v2 3/6] tpm: add send_recv() ops in tpm_class_ops*

On Tue, Mar 04, 2025 at 06:56:02PM +0200, Jarkko Sakkinen wrote:
> On Mon, 2025-03-03 at 17:21 +0100, Stefano Garzarella wrote:
> > On Sat, Mar 01, 2025 at 03:45:10AM +0200, Jarkko Sakkinen wrote:

I think I went here over the top, and *if* we need a new callback
putting send_recv would be fine. Only thing I'd take from this is to
rename to_len as cmd_len.

However, I don't think there are strong enough reasons to add complexity
to the callback interface with the basis of this single driver. You
should deal with this internally inside the driver instead.

So do something along the lines of, e.g.:

1. Create dummy send() copying the command to internal
   buffer.
2. Create ->status() returning zero, and set req_complete_mask and
   req_complete_val to zero.
3. Performan transaction in recv().

How you split send_recv() between send() and recv() is up to you. This
was merely showing that we don't need send_recv() desperately.

BR, Jarkko

---

## [28] Stefano Garzarella — 2025-03-05
*Subject: Re: [RFC PATCH v2 3/6] tpm: add send_recv() ops in tpm_class_ops*

On Tue, Mar 04, 2025 at 10:21:55PM +0200, Jarkko Sakkinen wrote:
>On Tue, Mar 04, 2025 at 06:56:02PM +0200, Jarkko Sakkinen wrote:
>> On Mon, 2025-03-03 at 17:21 +0100, Stefano Garzarella wrote:

Right!

>>
>> I'd do instead:

Got it.

>
>However, I don't think there are strong enough reasons to add complexity

We did something similar in v1 [1], but instead of your point 2, we just 
set `chip->flags |= TPM_CHIP_FLAG_IRQ;` in the probe() after we 
allocated the chip.

Jason suggested the send_recv() ops [2], which I liked, but if you 
prefer to avoid that, I can restore what we did in v1 and replace the 
TPM_CHIP_FLAG_IRQ hack with your point 2 (or use TPM_CHIP_FLAG_IRQ if 
you think it is fine).

@Jarkko, @Jason, I don't have a strong preference about it, so your 
choice :-)

Thanks,
Stefano

[1] https://lore.kernel.org/linux-integrity/20241210143423.101774-2-sgarzare@redhat.com/
[2] https://lore.kernel.org/linux-integrity/CAGxU2F51EoqDqi6By6eBa7qT+VT006DJ9+V-PANQ6GQrwVWt_Q@mail.gmail.com/

---

## [29] Stefano Garzarella — 2025-03-05
*Subject: Re: [RFC PATCH v2 5/6] tpm: add SNP SVSM vTPM driver*

On Tue, Mar 04, 2025 at 07:27:30PM +0200, Jarkko Sakkinen wrote:
>On Mon, Mar 03, 2025 at 05:46:16PM +0100, Stefano Garzarella wrote:
>> On Sat, Mar 01, 2025 at 03:51:46AM +0200, Jarkko Sakkinen wrote:

Yeah, I think we are now aligned, I will try to fix in the next version!

Thanks,
Stefano

---

## [30] Jason Gunthorpe — 2025-03-05
*Subject: Re: [RFC PATCH v2 3/6] tpm: add send_recv() ops in tpm_class_ops*

On Wed, Mar 05, 2025 at 10:04:25AM +0100, Stefano Garzarella wrote:
> Jason suggested the send_recv() ops [2], which I liked, but if you prefer to
> avoid that, I can restore what we did in v1 and replace the

I think it is a pretty notable simplification for the driver as it
does not need to implement send, status, req_canceled and more ops.

Given the small LOC on the core side I'd call that simplification a
win..

Jason

---

## [31] Jarkko Sakkinen — 2025-03-06
*Subject: Re: [RFC PATCH v2 3/6] tpm: add send_recv() ops in tpm_class_ops*

On Wed, Mar 05, 2025 at 03:02:29PM -0400, Jason Gunthorpe wrote:
> On Wed, Mar 05, 2025 at 10:04:25AM +0100, Stefano Garzarella wrote:
> > Jason suggested the send_recv() ops [2], which I liked, but if you prefer to

I'm sorry to disagree with you on this but adding a callback for
one leaf driver is not what I would call "a win" :-)

I mean, it's either a minor twist in

1. "the framework code" which affects in a way all other leaf drivers.
   At bare minimum it adds a tiny bit of complexity to the callback
   interface and a tiny bit of accumulated maintenance cost.
2. in the leaf driver

So I'd really would want to keep that tiny bit of extra complexity
localized.

> 
> Jason

BR, Jarkko

---

## [32] Jarkko Sakkinen — 2025-03-07
*Subject: Re: [RFC PATCH v2 3/6] tpm: add send_recv() ops in tpm_class_ops*

On Wed, Mar 05, 2025 at 10:04:25AM +0100, Stefano Garzarella wrote:
> On Tue, Mar 04, 2025 at 10:21:55PM +0200, Jarkko Sakkinen wrote:
> > On Tue, Mar 04, 2025 at 06:56:02PM +0200, Jarkko Sakkinen wrote:

I'd say, unless you have actual identified blocker, please go with
a driver where the complexity is managed within the driver.

> 
> Thanks,


BR, Jarkko

---

## [33] Stefano Garzarella — 2025-03-07
*Subject: Re: [RFC PATCH v2 3/6] tpm: add send_recv() ops in tpm_class_ops*

On Thu, Mar 06, 2025 at 11:52:46PM +0200, Jarkko Sakkinen wrote:
>On Wed, Mar 05, 2025 at 03:02:29PM -0400, Jason Gunthorpe wrote:
>> On Wed, Mar 05, 2025 at 10:04:25AM +0100, Stefano Garzarella wrote:

IIUC in the ftpm driver (tpm_ftpm_tee.c) we could also use send_recv() 
and save a memcpy() to a temporally buffer (pvt_data->resp_buf) and also 
that 4k buffer allocated with the private data of the driver.

BTW if you agree, for now I'll do something similar of what we do in the 
ftpm driver (which would be what Jarkko recommended - status() returns 
0, .req_complete_mask = 0, .req_complete_val = 0) and we can discuss 
send_recv() in a new series where I can include changes for the ftpm 
driver too, to see whether it makes sense or not.

WDYT?

Thanks,
Stefano

>
>I mean, it's either a minor twist in

---

## [34] Stefano Garzarella — 2025-03-07
*Subject: Re: [RFC PATCH v2 3/6] tpm: add send_recv() ops in tpm_class_ops*

On Fri, Mar 07, 2025 at 12:15:34AM +0200, Jarkko Sakkinen wrote:
>On Wed, Mar 05, 2025 at 10:04:25AM +0100, Stefano Garzarella wrote:
>> On Tue, Mar 04, 2025 at 10:21:55PM +0200, Jarkko Sakkinen wrote:

Yep, got it ;-)

Thanks,
Stefano

---

## [35] Jarkko Sakkinen — 2025-03-07
*Subject: Re: [RFC PATCH v2 3/6] tpm: add send_recv() ops in tpm_class_ops*

On Fri, Mar 07, 2025 at 04:37:12PM +0100, Stefano Garzarella wrote:
> On Thu, Mar 06, 2025 at 11:52:46PM +0200, Jarkko Sakkinen wrote:
> > On Wed, Mar 05, 2025 at 03:02:29PM -0400, Jason Gunthorpe wrote:

Yeah, that would work. Althought not related to this callback interface
per se, also tpm-dev-common.c is one example (in a way).

> 
> Thanks,

BR, Jarkko

---

## [36] Borislav Petkov — 2025-03-10
*Subject: Re: [RFC PATCH v2 1/6] x86/sev: add SVSM call macros for the vTPM
 protocol*

On Fri, Feb 28, 2025 at 06:07:15PM +0100, Stefano Garzarella wrote:
> Add macros for SVSM_VTPM_QUERY and SVSM_VTPM_CMD calls as defined
> in the "Secure VM Service Module for SEV-SNP Guests"

Those URLs are unstable - simply naming the document properly in the commit
message so that a search engine can find it is enough.

> Signed-off-by: Stefano Garzarella <sgarzare@redhat.com>
> ---

Merge this patch with the patch where those are used - no need for a separate
patch.

Thx.

---

## [37] Borislav Petkov — 2025-03-10
*Subject: Re: [RFC PATCH v2 2/6] x86/sev: add SVSM vTPM probe/send_command
 functions*

On Fri, Feb 28, 2025 at 06:07:16PM +0100, Stefano Garzarella wrote:
> +bool snp_svsm_vtpm_probe(void)
> +{

s/if we have a SVSM/if an SVSM is present/

> +	if (!snp_vmpl)
> +		return false;


^ Superfluous newline.

> +	if (ret != SVSM_SUCCESS)
> +		return false;

So

	return false;

here?

> +
> +	/* TPM_SEND_COMMAND - platform command 8 */

	BIT_ULL(8);

> +
> +	return (platform_cmds & send_cmd_mask) == send_cmd_mask;

In any case, you can zap all those local vars, use comments instead and slim
down the function, diff ontop:

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index 3902af4b1385..6d7e97c1f567 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -2631,12 +2631,9 @@ static int snp_issue_guest_request(struct snp_guest_req *req, struct snp_req_dat
 bool snp_svsm_vtpm_probe(void)
 {
 	struct svsm_call call = {};
-	u64 send_cmd_mask = 0;
-	u64 platform_cmds;
-	u64 features;
 	int ret;
 
-	/* The vTPM device is available only if we have a SVSM */
+	/* The vTPM device is available only if a SVSM is present */
 	if (!snp_vmpl)
 		return false;
 
@@ -2644,22 +2641,17 @@ bool snp_svsm_vtpm_probe(void)
 	call.rax = SVSM_VTPM_CALL(SVSM_VTPM_QUERY);
 
 	ret = svsm_perform_call_protocol(&call);
-
 	if (ret != SVSM_SUCCESS)
 		return false;
 
-	features = call.rdx_out;
-	platform_cmds = call.rcx_out;
-
 	/* No feature supported, it should be zero */
-	if (features)
-		pr_warn("SNP SVSM vTPM unsupported features: 0x%llx\n",
-			features);
-
-	/* TPM_SEND_COMMAND - platform command 8 */
-	send_cmd_mask = 1 << 8;
+	if (call.rdx_out) {
+		pr_warn("SNP SVSM vTPM unsupported features: 0x%llx\n", call.rdx_out);
+		return false;
+	}
 
-	return (platform_cmds & send_cmd_mask) == send_cmd_mask;
+	/* Check platform commands is TPM_SEND_COMMAND - platform command 8 */
+	return (call.rcx_out & BIT_ULL(8)) == BIT_ULL(8);
 }
 EXPORT_SYMBOL_GPL(snp_svsm_vtpm_probe);

---

## [38] Stefano Garzarella — 2025-03-10
*Subject: Re: [RFC PATCH v2 1/6] x86/sev: add SVSM call macros for the vTPM
 protocol*

On Mon, Mar 10, 2025 at 12:08:34PM +0100, Borislav Petkov wrote:
>On Fri, Feb 28, 2025 at 06:07:15PM +0100, Stefano Garzarella wrote:
>> Add macros for SVSM_VTPM_QUERY and SVSM_VTPM_CMD calls as defined

Ack, I'll do it all over the place in this series (commit descriptions, 
code comment blocks, etc.).

>
>> Signed-off-by: Stefano Garzarella <sgarzare@redhat.com>

Yeah, it is left over from v1 when I had added this patch over James' 
patches, but now I agree that it no longer makes sense since I have 
reworked almost every patch in this series. I'm going to incorporate 
them!

Thanks,
Stefano

---

## [39] Stefano Garzarella — 2025-03-10
*Subject: Re: [RFC PATCH v2 2/6] x86/sev: add SVSM vTPM probe/send_command
 functions*

On Mon, Mar 10, 2025 at 12:30:06PM +0100, Borislav Petkov wrote:
>On Fri, Feb 28, 2025 at 06:07:16PM +0100, Stefano Garzarella wrote:
>> +bool snp_svsm_vtpm_probe(void)

In v1 we had that, but Tom Lendacky suggested to remove it:
https://lore.kernel.org/linux-integrity/4valfkw7wtx3fpdv2qbymzggcu7mp4mhkd65j5q7zncs2dzorc@jjjevuwfchgl/

IIUC the features are supposed to be additive, so Tom's point was to 
avoid that in the future SVSM will supports new features and this driver 
stops working, when it could, just without using the new features.

I added a warning just to be aware of new features, but I can remove it.

>
>> +

Thanks for the diff, I'll apply it except, for now, the return in the 
feature check which is still not clear to me (I think I get Tom's point, 
but I would like confirmation from both of you).

Thanks,
Stefano

>
>diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c

---

## [40] Tom Lendacky — 2025-03-10
*Subject: Re: [RFC PATCH v2 2/6] x86/sev: add SVSM vTPM probe/send_command
 functions*

On 3/10/25 07:46, Stefano Garzarella wrote:
> On Mon, Mar 10, 2025 at 12:30:06PM +0100, Borislav Petkov wrote:
>> On Fri, Feb 28, 2025 at 06:07:16PM +0100, Stefano Garzarella wrote:

I don't think anything needs to be checked or printed. If you want to do
anything, just issue a pr_info() with the features value (and maybe the
platform_cmds value, too). Issuing a pr_warn() here would be like
issuing a pr_warn() for a new CPUID value that the current kernel
doesn't know about.

Thanks,
Tom

> 
>>

---

## [41] Borislav Petkov — 2025-03-10
*Subject: Re: [RFC PATCH v2 2/6] x86/sev: add SVSM vTPM probe/send_command
 functions*

On Mon, Mar 10, 2025 at 08:27:37AM -0500, Tom Lendacky wrote:
> I don't think anything needs to be checked or printed.

Yes.

> If you want to do anything, just issue a pr_info() with the features value
> (and maybe the platform_cmds value, too). Issuing a pr_warn() here would be

I still don't get the need to print anything. Why?

---

## [42] Tom Lendacky — 2025-03-10
*Subject: Re: [RFC PATCH v2 2/6] x86/sev: add SVSM vTPM probe/send_command
 functions*

On 3/10/25 08:51, Borislav Petkov wrote:
> On Mon, Mar 10, 2025 at 08:27:37AM -0500, Tom Lendacky wrote:
>> I don't think anything needs to be checked or printed.

It isn't needed. It's similar to "device" information/capabilities.
Maybe pr_debug() then? But I'm also fine with not printing anything.

Thanks,
Tom

>

---

## [43] Stefano Garzarella — 2025-03-10
*Subject: Re: [RFC PATCH v2 2/6] x86/sev: add SVSM vTPM probe/send_command
 functions*

On Mon, Mar 10, 2025 at 02:51:33PM +0100, Borislav Petkov wrote:
>On Mon, Mar 10, 2025 at 08:27:37AM -0500, Tom Lendacky wrote:
>> I don't think anything needs to be checked or printed.

Ack, I removed the check and the print.

@Boris I also removed `ret` to continue the slimming, so the end
result should be this:

bool snp_svsm_vtpm_probe(void)
{
	struct svsm_call call = {};

	/* The vTPM device is available only if a SVSM is present */
	if (!snp_vmpl)
		return false;

	call.caa = svsm_get_caa();
	call.rax = SVSM_VTPM_CALL(SVSM_VTPM_QUERY);

	if (svsm_perform_call_protocol(&call))
		return false;

	/* Check platform commands contains TPM_SEND_COMMAND - platform command 8 */
	return (call.rcx_out & BIT_ULL(8)) == BIT_ULL(8);
}

Quite nice, thanks for the review!
Stefano

---

## [44] Borislav Petkov — 2025-03-10
*Subject: Re: [RFC PATCH v2 2/6] x86/sev: add SVSM vTPM probe/send_command
 functions*

On Mon, Mar 10, 2025 at 08:56:53AM -0500, Tom Lendacky wrote:
> It isn't needed. It's similar to "device" information/capabilities.
> Maybe pr_debug() then? But I'm also fine with not printing anything.

Yap, nothing it is then.

If the need arises, then we can debate :)

---

## [45] Borislav Petkov — 2025-03-10
*Subject: Re: [RFC PATCH v2 2/6] x86/sev: add SVSM vTPM probe/send_command
 functions*

On Mon, Mar 10, 2025 at 02:59:44PM +0100, Stefano Garzarella wrote:
> On Mon, Mar 10, 2025 at 02:51:33PM +0100, Borislav Petkov wrote:
> > On Mon, Mar 10, 2025 at 08:27:37AM -0500, Tom Lendacky wrote:

Thanks, looks clean to me. :)

---
