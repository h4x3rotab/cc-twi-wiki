---
title: 'Annotate arguments of memtostr/strtomem with __nonstring'
date: 2025-02-06
last_reply: 2025-02-12
message_count: 17
participants: ['Kees Cook', 'Dave Hansen', 'Andy Shevchenko', 'Kirill A. Shutemov', 'Martin K. Petersen']
---

## [1] Kees Cook — 2025-02-06

Hi,

The memtostr*() and strtomem*() helpers are designed to move between C
strings (NUL-terminated) and byte arrays (that may just be zero padded and
may not be NUL-terminated). The "nonstring" attribute is used to annotated
these kinds of byte arrays, and we can validate the annotation on the
arguments of the helpers. Add the the infrastructure to do this, and
then update all the places where these annotations are currently missing.

-Kees

Kees Cook (10):
  scsi: mptfusion: Mark device strings as nonstring
  scsi: mpi3mr: Mark device strings as nonstring
  scsi: mpt3sas: Mark device strings as nonstring
  scsi: qla2xxx: Mark device strings as nonstring
  string: kunit: Mark nonstring test strings as __nonstring
  x86/tdx: Mark message.str as nonstring
  uapi: stddef.h: Introduce __kernel_nonstring
  nilfs2: Mark on-disk strings as nonstring
  compiler.h: Introduce __must_be_noncstr()
  string.h: Validate memtostr*()/strtomem*() arguments more carefully

 arch/x86/coco/tdx/tdx.c                  |  2 +-
 drivers/message/fusion/mptsas.c          |  8 ++++----
 drivers/scsi/mpi3mr/mpi3mr_transport.c   |  8 ++++----
 drivers/scsi/mpt3sas/mpi/mpi2_cnfg.h     |  2 +-
 drivers/scsi/mpt3sas/mpt3sas_transport.c |  8 ++++----
 drivers/scsi/qla2xxx/qla_mr.h            |  4 ++--
 include/linux/compiler.h                 | 18 +++++++++++++++++-
 include/linux/string.h                   | 16 ++++++++++++----
 include/uapi/linux/nilfs2_ondisk.h       |  3 ++-
 include/uapi/linux/stddef.h              |  6 ++++++
 lib/string_kunit.c                       |  4 ++--
 11 files changed, 55 insertions(+), 24 deletions(-)

---

## [2] Kees Cook — 2025-02-06
*Subject: [PATCH 01/10] scsi: mptfusion: Mark device strings as nonstring*

In preparation for memtostr*() checking that its source is marked as
nonstring, annotate the device strings accordingly.

Signed-off-by: Kees Cook <kees@kernel.org>
---
Cc: Sathya Prakash <sathya.prakash@broadcom.com>
Cc: Sreekanth Reddy <sreekanth.reddy@broadcom.com>
Cc: Suganath Prabu Subramani <suganath-prabu.subramani@broadcom.com>
Cc: MPT-FusionLinux.pdl@broadcom.com
Cc: linux-scsi@vger.kernel.org
---
 drivers/message/fusion/mptsas.c | 8 ++++----
 1 file changed, 4 insertions(+), 4 deletions(-)

diff --git a/drivers/message/fusion/mptsas.c b/drivers/message/fusion/mptsas.c
index d0549a4daf76..9e3a823ca4eb 100644
--- a/drivers/message/fusion/mptsas.c
+++ b/drivers/message/fusion/mptsas.c
@@ -2834,10 +2834,10 @@ struct rep_manu_reply{
 	u8 sas_format:1;
 	u8 reserved1:7;
 	u8 reserved2[3];
-	u8 vendor_id[SAS_EXPANDER_VENDOR_ID_LEN];
-	u8 product_id[SAS_EXPANDER_PRODUCT_ID_LEN];
-	u8 product_rev[SAS_EXPANDER_PRODUCT_REV_LEN];
-	u8 component_vendor_id[SAS_EXPANDER_COMPONENT_VENDOR_ID_LEN];
+	u8 vendor_id[SAS_EXPANDER_VENDOR_ID_LEN] __nonstring;
+	u8 product_id[SAS_EXPANDER_PRODUCT_ID_LEN] __nonstring;
+	u8 product_rev[SAS_EXPANDER_PRODUCT_REV_LEN] __nonstring;
+	u8 component_vendor_id[SAS_EXPANDER_COMPONENT_VENDOR_ID_LEN] __nonstring;
 	u16 component_id;
 	u8 component_revision_id;
 	u8 reserved3;

---

## [3] Kees Cook — 2025-02-06
*Subject: [PATCH 02/10] scsi: mpi3mr: Mark device strings as nonstring*

In preparation for memtostr*() checking that its source is marked as
nonstring, annotate the device strings accordingly.

Signed-off-by: Kees Cook <kees@kernel.org>
---
Cc: Sathya Prakash Veerichetty <sathya.prakash@broadcom.com>
Cc: Kashyap Desai <kashyap.desai@broadcom.com>
Cc: Sumit Saxena <sumit.saxena@broadcom.com>
Cc: Sreekanth Reddy <sreekanth.reddy@broadcom.com>
Cc: "James E.J. Bottomley" <James.Bottomley@HansenPartnership.com>
Cc: "Martin K. Petersen" <martin.petersen@oracle.com>
Cc: mpi3mr-linuxdrv.pdl@broadcom.com
Cc: linux-scsi@vger.kernel.org
---
 drivers/scsi/mpi3mr/mpi3mr_transport.c | 8 ++++----
 1 file changed, 4 insertions(+), 4 deletions(-)

diff --git a/drivers/scsi/mpi3mr/mpi3mr_transport.c b/drivers/scsi/mpi3mr/mpi3mr_transport.c
index 0ba9e6a6a13c..c8d6ced5640e 100644
--- a/drivers/scsi/mpi3mr/mpi3mr_transport.c
+++ b/drivers/scsi/mpi3mr/mpi3mr_transport.c
@@ -105,10 +105,10 @@ struct rep_manu_reply {
 	u8 reserved0[2];
 	u8 sas_format;
 	u8 reserved2[3];
-	u8 vendor_id[SAS_EXPANDER_VENDOR_ID_LEN];
-	u8 product_id[SAS_EXPANDER_PRODUCT_ID_LEN];
-	u8 product_rev[SAS_EXPANDER_PRODUCT_REV_LEN];
-	u8 component_vendor_id[SAS_EXPANDER_COMPONENT_VENDOR_ID_LEN];
+	u8 vendor_id[SAS_EXPANDER_VENDOR_ID_LEN] __nonstring;
+	u8 product_id[SAS_EXPANDER_PRODUCT_ID_LEN] __nonstring;
+	u8 product_rev[SAS_EXPANDER_PRODUCT_REV_LEN] __nonstring;
+	u8 component_vendor_id[SAS_EXPANDER_COMPONENT_VENDOR_ID_LEN] __nonstring;
 	u16 component_id;
 	u8 component_revision_id;
 	u8 reserved3;

---

## [4] Kees Cook — 2025-02-06
*Subject: [PATCH 03/10] scsi: mpt3sas: Mark device strings as nonstring*

In preparation for memtostr*() checking that its source is marked as
nonstring, annotate the device strings accordingly.

Signed-off-by: Kees Cook <kees@kernel.org>
---
Cc: Sathya Prakash <sathya.prakash@broadcom.com>
Cc: Sreekanth Reddy <sreekanth.reddy@broadcom.com>
Cc: Suganath Prabu Subramani <suganath-prabu.subramani@broadcom.com>
Cc: "James E.J. Bottomley" <James.Bottomley@HansenPartnership.com>
Cc: "Martin K. Petersen" <martin.petersen@oracle.com>
Cc: MPT-FusionLinux.pdl@broadcom.com
Cc: linux-scsi@vger.kernel.org
---
 drivers/scsi/mpt3sas/mpi/mpi2_cnfg.h     | 2 +-
 drivers/scsi/mpt3sas/mpt3sas_transport.c | 8 ++++----
 2 files changed, 5 insertions(+), 5 deletions(-)

diff --git a/drivers/scsi/mpt3sas/mpi/mpi2_cnfg.h b/drivers/scsi/mpt3sas/mpi/mpi2_cnfg.h
index 587f7d248219..d123d3b740e1 100644
--- a/drivers/scsi/mpt3sas/mpi/mpi2_cnfg.h
+++ b/drivers/scsi/mpt3sas/mpi/mpi2_cnfg.h
@@ -606,7 +606,7 @@ typedef struct _MPI2_CONFIG_REPLY {
 
 typedef struct _MPI2_CONFIG_PAGE_MAN_0 {
 	MPI2_CONFIG_PAGE_HEADER Header;                     /*0x00 */
-	U8                      ChipName[16];               /*0x04 */
+	U8                      ChipName[16] __nonstring;   /*0x04 */
 	U8                      ChipRevision[8];            /*0x14 */
 	U8                      BoardName[16];              /*0x1C */
 	U8                      BoardAssembly[16];          /*0x2C */
diff --git a/drivers/scsi/mpt3sas/mpt3sas_transport.c b/drivers/scsi/mpt3sas/mpt3sas_transport.c
index d84413b77d84..dc74ebc6405a 100644
--- a/drivers/scsi/mpt3sas/mpt3sas_transport.c
+++ b/drivers/scsi/mpt3sas/mpt3sas_transport.c
@@ -328,10 +328,10 @@ struct rep_manu_reply {
 	u8 reserved0[2];
 	u8 sas_format;
 	u8 reserved2[3];
-	u8 vendor_id[SAS_EXPANDER_VENDOR_ID_LEN];
-	u8 product_id[SAS_EXPANDER_PRODUCT_ID_LEN];
-	u8 product_rev[SAS_EXPANDER_PRODUCT_REV_LEN];
-	u8 component_vendor_id[SAS_EXPANDER_COMPONENT_VENDOR_ID_LEN];
+	u8 vendor_id[SAS_EXPANDER_VENDOR_ID_LEN] __nonstring;
+	u8 product_id[SAS_EXPANDER_PRODUCT_ID_LEN] __nonstring;
+	u8 product_rev[SAS_EXPANDER_PRODUCT_REV_LEN] __nonstring;
+	u8 component_vendor_id[SAS_EXPANDER_COMPONENT_VENDOR_ID_LEN] __nonstring;
 	u16 component_id;
 	u8 component_revision_id;
 	u8 reserved3;

---

## [5] Kees Cook — 2025-02-06
*Subject: [PATCH 04/10] scsi: qla2xxx: Mark device strings as nonstring*

In preparation for memtostr*() checking that its source is marked as
nonstring, annotate the device strings accordingly.

Signed-off-by: Kees Cook <kees@kernel.org>
---
Cc: Nilesh Javali <njavali@marvell.com>
Cc: GR-QLogic-Storage-Upstream@marvell.com
Cc: "James E.J. Bottomley" <James.Bottomley@HansenPartnership.com>
Cc: "Martin K. Petersen" <martin.petersen@oracle.com>
Cc: linux-scsi@vger.kernel.org
---
 drivers/scsi/qla2xxx/qla_mr.h | 4 ++--
 1 file changed, 2 insertions(+), 2 deletions(-)

diff --git a/drivers/scsi/qla2xxx/qla_mr.h b/drivers/scsi/qla2xxx/qla_mr.h
index 4f63aff333db..3a2bd953a976 100644
--- a/drivers/scsi/qla2xxx/qla_mr.h
+++ b/drivers/scsi/qla2xxx/qla_mr.h
@@ -282,8 +282,8 @@ struct register_host_info {
 #define QLAFX00_TGT_NODE_LIST_SIZE (sizeof(uint32_t) * 32)
 
 struct config_info_data {
-	uint8_t		model_num[16];
-	uint8_t		model_description[80];
+	uint8_t		model_num[16] __nonstring;
+	uint8_t		model_description[80] __nonstring;
 	uint8_t		reserved0[160];
 	uint8_t		symbolic_name[64];
 	uint8_t		serial_num[32];

---

## [6] Kees Cook — 2025-02-06
*Subject: [PATCH 05/10] string: kunit: Mark nonstring test strings as __nonstring*

In preparation for strtomem*() checking that its destination is a
__nonstring, annotate "nonstring" and "nonstring_small" variables
accordingly.

Signed-off-by: Kees Cook <kees@kernel.org>
---
Cc: Andy Shevchenko <andy@kernel.org>
Cc: Andrew Morton <akpm@linux-foundation.org>
Cc: linux-hardening@vger.kernel.org
---
 lib/string_kunit.c | 4 ++--
 1 file changed, 2 insertions(+), 2 deletions(-)

diff --git a/lib/string_kunit.c b/lib/string_kunit.c
index c919e3293da6..0ed7448a26d3 100644
--- a/lib/string_kunit.c
+++ b/lib/string_kunit.c
@@ -579,8 +579,8 @@ static void string_test_strtomem(struct kunit *test)
 
 static void string_test_memtostr(struct kunit *test)
 {
-	char nonstring[7] = { 'a', 'b', 'c', 'd', 'e', 'f', 'g' };
-	char nonstring_small[3] = { 'a', 'b', 'c' };
+	char nonstring[7] __nonstring = { 'a', 'b', 'c', 'd', 'e', 'f', 'g' };
+	char nonstring_small[3] __nonstring = { 'a', 'b', 'c' };
 	char dest[sizeof(nonstring) + 1];
 
 	/* Copy in a non-NUL-terminated string into exactly right-sized dest. */

---

## [7] Kees Cook — 2025-02-06
*Subject: [PATCH 06/10] x86/tdx: Mark message.str as nonstring*

In preparation for strtomem*() checking that its destination is a
nonstring, annotate message.str accordingly.

Signed-off-by: Kees Cook <kees@kernel.org>
---
Cc: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>
Cc: Dave Hansen <dave.hansen@linux.intel.com>
Cc: Thomas Gleixner <tglx@linutronix.de>
Cc: Ingo Molnar <mingo@redhat.com>
Cc: Borislav Petkov <bp@alien8.de>
Cc: x86@kernel.org
Cc: "H. Peter Anvin" <hpa@zytor.com>
Cc: linux-coco@lists.linux.dev
---
 arch/x86/coco/tdx/tdx.c | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 0d9b090b4880..977ab1ffa3fe 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -170,7 +170,7 @@ static void __noreturn tdx_panic(const char *msg)
 		/* Define register order according to the GHCI */
 		struct { u64 r14, r15, rbx, rdi, rsi, r8, r9, rdx; };
 
-		char str[64];
+		char str[64] __nonstring;
 	} message;
 
 	/* VMM assumes '\0' in byte 65, if the message took all 64 bytes */

---

## [8] Kees Cook — 2025-02-06
*Subject: [PATCH 07/10] uapi: stddef.h: Introduce __kernel_nonstring*

In order to annotate byte arrays in UAPI that are not C strings (i.e.
they may not be NUL terminated), the "nonstring" attribute is needed.
However, we can't expose this to userspace as it is compiler version
specific.

Signed-off-by: Kees Cook <kees@kernel.org>
---
Cc: Alexey Dobriyan <adobriyan@gmail.com>
Cc: Sven Eckelmann <sven@narfation.org>
Cc: Tadeusz Struk <tadeusz.struk@linaro.org>
Cc: Erick Archer <erick.archer@outlook.com>
Cc: Dmitry Antipov <dmantipov@yandex.ru>
---
 include/uapi/linux/stddef.h | 6 ++++++
 1 file changed, 6 insertions(+)

diff --git a/include/uapi/linux/stddef.h b/include/uapi/linux/stddef.h
index 58154117d9b0..0e7d289b7c2e 100644
--- a/include/uapi/linux/stddef.h
+++ b/include/uapi/linux/stddef.h
@@ -63,4 +63,10 @@
 #define __counted_by_be(m)
 #endif
 
+#ifdef __KERNEL__
+#define __kernel_nonstring	__nonstring
+#else
+#define __kernel_nonstring
+#endif
+
 #endif /* _UAPI_LINUX_STDDEF_H */

---

## [9] Kees Cook — 2025-02-06
*Subject: [PATCH 08/10] nilfs2: Mark on-disk strings as nonstring*

In preparation for memtostr*() checking that its source is marked as
nonstring, annotate the device strings accordingly using the new UAPI
alias for the "nonstring" attribute.

Signed-off-by: Kees Cook <kees@kernel.org>
---
Cc: Ryusuke Konishi <konishi.ryusuke@gmail.com>
Cc: linux-nilfs@vger.kernel.org
---
 include/uapi/linux/nilfs2_ondisk.h | 3 ++-
 1 file changed, 2 insertions(+), 1 deletion(-)

diff --git a/include/uapi/linux/nilfs2_ondisk.h b/include/uapi/linux/nilfs2_ondisk.h
index c23f91ae5fe8..3196cc44a002 100644
--- a/include/uapi/linux/nilfs2_ondisk.h
+++ b/include/uapi/linux/nilfs2_ondisk.h
@@ -188,7 +188,8 @@ struct nilfs_super_block {
 	__le16	s_segment_usage_size;	/* Size of a segment usage */
 
 /*98*/	__u8	s_uuid[16];		/* 128-bit uuid for volume */
-/*A8*/	char	s_volume_name[80];	/* volume name */
+/*A8*/	char	s_volume_name[80]	/* volume name */
+			__kernel_nonstring;
 
 /*F8*/	__le32  s_c_interval;           /* Commit interval of segment */
 	__le32  s_c_block_max;          /*

---

## [10] Kees Cook — 2025-02-06
*Subject: [PATCH 09/10] compiler.h: Introduce __must_be_noncstr()*

In preparation for adding more type checking to the memtostr/strtomem*()
helpers, introduce the ability to check for the "nonstring" attribute.
This is the reverse of what was added to strscpy*() in commit 559048d156ff
("string: Check for "nonstring" attribute on strscpy() arguments").

Signed-off-by: Kees Cook <kees@kernel.org>
---
 include/linux/compiler.h | 18 +++++++++++++++++-
 1 file changed, 17 insertions(+), 1 deletion(-)

diff --git a/include/linux/compiler.h b/include/linux/compiler.h
index 1c0688319435..c89070a2f964 100644
--- a/include/linux/compiler.h
+++ b/include/linux/compiler.h
@@ -229,9 +229,25 @@ void ftrace_likely_update(struct ftrace_likely_data *f, int val,
 #define __must_be_byte_array(a)	__BUILD_BUG_ON_ZERO_MSG(!__is_byte_array(a), \
 							"must be byte array")
 
+/*
+ * If the "nonstring" attribute isn't available, we have to return true
+ * so the __must_*() checks pass when "nonstring" isn't supported.
+ */
+#if __has_attribute(__nonstring__)
+#define __is_cstr(a)		(!__annotated(a, nonstring))
+#define __is_noncstr(a)		(__annotated(a, nonstring))
+#else
+#define __is_cstr(a)		(true)
+#define __is_noncstr(a)		(true)
+#endif
+
 /* Require C Strings (i.e. NUL-terminated) lack the "nonstring" attribute. */
 #define __must_be_cstr(p) \
-	__BUILD_BUG_ON_ZERO_MSG(__annotated(p, nonstring), "must be cstr (NUL-terminated)")
+	__BUILD_BUG_ON_ZERO_MSG(!__is_cstr(p), \
+				"must be C-string (NUL-terminated)")
+#define __must_be_noncstr(p) \
+	__BUILD_BUG_ON_ZERO_MSG(!__is_noncstr(p), \
+				"must be non-C-string (not NUL-terminated)")
 
 #endif /* __KERNEL__ */

---

## [11] Kees Cook — 2025-02-06
*Subject: [PATCH 10/10] string.h: Validate memtostr*()/strtomem*() arguments more carefully*

Since these functions handle moving between C strings and non-C strings,
they should check for the appropriate presence/lack of the nonstring
attribute on arguments.

Signed-off-by: Kees Cook <kees@kernel.org>
---
Cc: Andy Shevchenko <andy@kernel.org>
Cc: linux-hardening@vger.kernel.org
---
 include/linux/string.h | 16 ++++++++++++----
 1 file changed, 12 insertions(+), 4 deletions(-)

diff --git a/include/linux/string.h b/include/linux/string.h
index fc5ae145bd78..26491a2f8010 100644
--- a/include/linux/string.h
+++ b/include/linux/string.h
@@ -412,8 +412,10 @@ void memcpy_and_pad(void *dest, size_t dest_len, const void *src, size_t count,
  */
 #define strtomem_pad(dest, src, pad)	do {				\
 	const size_t _dest_len = __must_be_byte_array(dest) +		\
+				 __must_be_noncstr(dest) +		\
 				 ARRAY_SIZE(dest);			\
-	const size_t _src_len = __builtin_object_size(src, 1);		\
+	const size_t _src_len = __must_be_cstr(src) +			\
+				__builtin_object_size(src, 1);		\
 									\
 	BUILD_BUG_ON(!__builtin_constant_p(_dest_len) ||		\
 		     _dest_len == (size_t)-1);				\
@@ -436,8 +438,10 @@ void memcpy_and_pad(void *dest, size_t dest_len, const void *src, size_t count,
  */
 #define strtomem(dest, src)	do {					\
 	const size_t _dest_len = __must_be_byte_array(dest) +		\
+				 __must_be_noncstr(dest) +		\
 				 ARRAY_SIZE(dest);			\
-	const size_t _src_len = __builtin_object_size(src, 1);		\
+	const size_t _src_len = __must_be_cstr(src) +			\
+				__builtin_object_size(src, 1);		\
 									\
 	BUILD_BUG_ON(!__builtin_constant_p(_dest_len) ||		\
 		     _dest_len == (size_t)-1);				\
@@ -456,8 +460,10 @@ void memcpy_and_pad(void *dest, size_t dest_len, const void *src, size_t count,
  */
 #define memtostr(dest, src)	do {					\
 	const size_t _dest_len = __must_be_byte_array(dest) +		\
+				 __must_be_cstr(dest) +			\
 				 ARRAY_SIZE(dest);			\
-	const size_t _src_len = __builtin_object_size(src, 1);		\
+	const size_t _src_len = __must_be_noncstr(src) +		\
+				__builtin_object_size(src, 1);		\
 	const size_t _src_chars = strnlen(src, _src_len);		\
 	const size_t _copy_len = min(_dest_len - 1, _src_chars);	\
 									\
@@ -482,8 +488,10 @@ void memcpy_and_pad(void *dest, size_t dest_len, const void *src, size_t count,
  */
 #define memtostr_pad(dest, src)		do {				\
 	const size_t _dest_len = __must_be_byte_array(dest) +		\
+				 __must_be_cstr(dest) +			\
 				 ARRAY_SIZE(dest);			\
-	const size_t _src_len = __builtin_object_size(src, 1);		\
+	const size_t _src_len = __must_be_noncstr(src) +		\
+				__builtin_object_size(src, 1);		\
 	const size_t _src_chars = strnlen(src, _src_len);		\
 	const size_t _copy_len = min(_dest_len - 1, _src_chars);	\
 									\

---

## [12] Dave Hansen — 2025-02-06
*Subject: Re: [PATCH 06/10] x86/tdx: Mark message.str as nonstring*

On 2/6/25 17:00, Kees Cook wrote:
> +++ b/arch/x86/coco/tdx/tdx.c
> @@ -170,7 +170,7 @@ static void __noreturn tdx_panic(const char *msg)

So, the patch itself makes sense. But it does end up looking kinda
funky. We call it a "str"ing and then annotate it as not a string.

It doesn't have to be done in this patch, but it does seem like we
should probably not be using 'char' and also shouldn't call it anything
close to "string". Maybe:

	u8 message[64] __nonstring;

In any case, feel free to carry the annotation in your tree:

Acked-by: Dave Hansen <dave.hansen@linux.intel.com>

---

## [13] Kees Cook — 2025-02-06
*Subject: Re: [PATCH 06/10] x86/tdx: Mark message.str as nonstring*

On Thu, Feb 06, 2025 at 05:12:11PM -0800, Dave Hansen wrote:
> On 2/6/25 17:00, Kees Cook wrote:
> > +++ b/arch/x86/coco/tdx/tdx.c

Yeah, this is true all over the place. It's a string, just not a
NUL-terminated string: *sob*

> It doesn't have to be done in this patch, but it does seem like we
> should probably not be using 'char' and also shouldn't call it anything

message.message ;)

message.chars?
message.bytes?

> In any case, feel free to carry the annotation in your tree:
> 

Thanks!

-Kees

---

## [14] Andy Shevchenko — 2025-02-07
*Subject: Re: [PATCH 06/10] x86/tdx: Mark message.str as nonstring*

On Fri, Feb 7, 2025 at 4:37 AM Kees Cook <kees@kernel.org> wrote:
> On Thu, Feb 06, 2025 at 05:12:11PM -0800, Dave Hansen wrote:
> > On 2/6/25 17:00, Kees Cook wrote:

...

> > So, the patch itself makes sense. But it does end up looking kinda
> > funky. We call it a "str"ing and then annotate it as not a string.

Maybe call it respectively, e.g., __nontermstr ?

---

## [15] Kees Cook — 2025-02-08
*Subject: Re: [PATCH 06/10] x86/tdx: Mark message.str as nonstring*

On Fri, Feb 07, 2025 at 02:09:12PM +0200, Andy Shevchenko wrote:
> On Fri, Feb 7, 2025 at 4:37 AM Kees Cook <kees@kernel.org> wrote:
> > On Thu, Feb 06, 2025 at 05:12:11PM -0800, Dave Hansen wrote:

I don't want to change its name from the GCC attribute. I think that's
just asking more more confusion.

---

## [16] Kirill A. Shutemov — 2025-02-10
*Subject: Re: [PATCH 06/10] x86/tdx: Mark message.str as nonstring*

On Thu, Feb 06, 2025 at 06:37:27PM -0800, Kees Cook wrote:
> On Thu, Feb 06, 2025 at 05:12:11PM -0800, Dave Hansen wrote:
> > On 2/6/25 17:00, Kees Cook wrote:

.bytes sounds good to me.

Anyway:

Acked-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>

---

## [17] Martin K. Petersen — 2025-02-12
*Subject: Re: [PATCH 00/10] Annotate arguments of memtostr/strtomem with
 __nonstring*

Kees,

> The memtostr*() and strtomem*() helpers are designed to move between C
> strings (NUL-terminated) and byte arrays (that may just be zero padded

Reviewed-by: Martin K. Petersen <martin.petersen@oracle.com> # SCSI

---
