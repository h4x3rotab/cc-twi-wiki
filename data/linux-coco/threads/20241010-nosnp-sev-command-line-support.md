---
title: 'nosnp sev command line support'
date: 2024-10-10
last_reply: 2024-10-12
message_count: 10
participants: ['Pavan Kumar Paluri', 'Borislav Petkov', 'Tom Lendacky']
---

## [1] Pavan Kumar Paluri — 2024-10-10

Provide "nosnp" boot option via "sev=nosnp" kernel command line to
prevent SEV-SNP [1] capable host kernel from enabling SEV-SNP and
initializing Reverse Map Table (RMP)

Setting 'nosnp' avoids the RMP check overhead in memory accesses when
users do not want to run SEV-SNP guests.

On providing sev=nosnp via kernel command line:
cat /sys/module/kvm_amd/parameters/sev_snp should be "N".

The patchset is based on tip/master.

Reference:
[1] https://www.amd.com/content/dam/amd/en/documents/processor-tech-docs/programmer-references/24593.pdf

Changelog:
=========
v5:
  * Update cover-letter and Documentation to include information on why
    nosnp command line option is required (Dave Hansen)
  * Remove <asm/cache.h> stray header introduced in the previous
    versions because of __read_mostly attribute that is now moved into
    virt/svm/cmdline.c
  * Link: https://lore.kernel.org/all/20240930231102.123403-1-papaluri@amd.com/

v4:
  * Move __read_mostly attribute to place where sev_cfg is declared (Tom)
  * Link: https://lore.kernel.org/all/20240922033626.29038-1-papaluri@amd.com/

Pavan Kumar Paluri (2):
  x86, KVM:SVM: Move sev specific parsing into arch/x86/virt/svm
  x86 KVM:SVM: Provide "nosnp" boot option for sev kernel command line

 .../arch/x86/x86_64/boot-options.rst          |  5 +++
 arch/x86/coco/sev/core.c                      | 44 -------------------
 arch/x86/include/asm/sev-common.h             | 27 ++++++++++++
 arch/x86/virt/svm/Makefile                    |  1 +
 arch/x86/virt/svm/cmdline.c                   | 39 ++++++++++++++++
 5 files changed, 72 insertions(+), 44 deletions(-)
 create mode 100644 arch/x86/virt/svm/cmdline.c


base-commit: 00d91979d23c88d3f50870e22fc9cec3f5e26a2a

---

## [2] Pavan Kumar Paluri — 2024-10-10
*Subject: [PATCH v6 1/2] x86, KVM:SVM: Move sev specific parsing into arch/x86/virt/svm*

Move SEV specific kernel command line option parsing support from
arch/x86/coco/sev/core.c to arch/x86/virt/svm/cmdline.c so that both
host and guest related SEV command line options can be supported.

No functional changes intended.

Signed-off-by: Pavan Kumar Paluri <papaluri@amd.com>
Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>
---
 arch/x86/coco/sev/core.c          | 44 -------------------------------
 arch/x86/include/asm/sev-common.h | 27 +++++++++++++++++++
 arch/x86/virt/svm/Makefile        |  1 +
 arch/x86/virt/svm/cmdline.c       | 32 ++++++++++++++++++++++
 4 files changed, 60 insertions(+), 44 deletions(-)
 create mode 100644 arch/x86/virt/svm/cmdline.c

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index de1df0cb45da..ff19e805e7a1 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -141,33 +141,6 @@ static DEFINE_PER_CPU(struct sev_es_save_area *, sev_vmsa);
 static DEFINE_PER_CPU(struct svsm_ca *, svsm_caa);
 static DEFINE_PER_CPU(u64, svsm_caa_pa);
 
-struct sev_config {
-	__u64 debug		: 1,
-
-	      /*
-	       * Indicates when the per-CPU GHCB has been created and registered
-	       * and thus can be used by the BSP instead of the early boot GHCB.
-	       *
-	       * For APs, the per-CPU GHCB is created before they are started
-	       * and registered upon startup, so this flag can be used globally
-	       * for the BSP and APs.
-	       */
-	      ghcbs_initialized	: 1,
-
-	      /*
-	       * Indicates when the per-CPU SVSM CA is to be used instead of the
-	       * boot SVSM CA.
-	       *
-	       * For APs, the per-CPU SVSM CA is created as part of the AP
-	       * bringup, so this flag can be used globally for the BSP and APs.
-	       */
-	      use_cas		: 1,
-
-	      __reserved	: 61;
-};
-
-static struct sev_config sev_cfg __read_mostly;
-
 static __always_inline bool on_vc_stack(struct pt_regs *regs)
 {
 	unsigned long sp = regs->sp;
@@ -2374,23 +2347,6 @@ static int __init report_snp_info(void)
 }
 arch_initcall(report_snp_info);
 
-static int __init init_sev_config(char *str)
-{
-	char *s;
-
-	while ((s = strsep(&str, ","))) {
-		if (!strcmp(s, "debug")) {
-			sev_cfg.debug = true;
-			continue;
-		}
-
-		pr_info("SEV command-line option '%s' was not recognized\n", s);
-	}
-
-	return 1;
-}
-__setup("sev=", init_sev_config);
-
 static void update_attest_input(struct svsm_call *call, struct svsm_attest_call *input)
 {
 	/* If (new) lengths have been returned, propagate them up */
diff --git a/arch/x86/include/asm/sev-common.h b/arch/x86/include/asm/sev-common.h
index 98726c2b04f8..50f5666938c0 100644
--- a/arch/x86/include/asm/sev-common.h
+++ b/arch/x86/include/asm/sev-common.h
@@ -220,4 +220,31 @@ struct snp_psc_desc {
 #define GHCB_ERR_INVALID_INPUT		5
 #define GHCB_ERR_INVALID_EVENT		6
 
+struct sev_config {
+	__u64 debug		: 1,
+
+	      /*
+	       * Indicates when the per-CPU GHCB has been created and registered
+	       * and thus can be used by the BSP instead of the early boot GHCB.
+	       *
+	       * For APs, the per-CPU GHCB is created before they are started
+	       * and registered upon startup, so this flag can be used globally
+	       * for the BSP and APs.
+	       */
+	      ghcbs_initialized	: 1,
+
+	      /*
+	       * Indicates when the per-CPU SVSM CA is to be used instead of the
+	       * boot SVSM CA.
+	       *
+	       * For APs, the per-CPU SVSM CA is created as part of the AP
+	       * bringup, so this flag can be used globally for the BSP and APs.
+	       */
+	      use_cas		: 1,
+
+	      __reserved	: 61;
+};
+
+extern struct sev_config sev_cfg;
+
 #endif
diff --git a/arch/x86/virt/svm/Makefile b/arch/x86/virt/svm/Makefile
index ef2a31bdcc70..eca6d71355fa 100644
--- a/arch/x86/virt/svm/Makefile
+++ b/arch/x86/virt/svm/Makefile
@@ -1,3 +1,4 @@
 # SPDX-License-Identifier: GPL-2.0
 
 obj-$(CONFIG_KVM_AMD_SEV) += sev.o
+obj-$(CONFIG_CPU_SUP_AMD) += cmdline.o
diff --git a/arch/x86/virt/svm/cmdline.c b/arch/x86/virt/svm/cmdline.c
new file mode 100644
index 000000000000..9640507342e0
--- /dev/null
+++ b/arch/x86/virt/svm/cmdline.c
@@ -0,0 +1,32 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/*
+ * AMD SVM-SEV command line parsing support
+ *
+ * Copyright (C) 2023 - 2024 Advanced Micro Devices, Inc.
+ *
+ * Author: Michael Roth <michael.roth@amd.com>
+ */
+
+#include <linux/string.h>
+#include <linux/printk.h>
+
+#include <asm/sev-common.h>
+
+struct sev_config sev_cfg __read_mostly;
+
+static int __init init_sev_config(char *str)
+{
+	char *s;
+
+	while ((s = strsep(&str, ","))) {
+		if (!strcmp(s, "debug")) {
+			sev_cfg.debug = true;
+			continue;
+		}
+
+		pr_info("SEV command-line option '%s' was not recognized\n", s);
+	}
+
+	return 1;
+}
+__setup("sev=", init_sev_config);

---

## [3] Pavan Kumar Paluri — 2024-10-10
*Subject: [PATCH v6 2/2] x86 KVM:SVM: Provide "nosnp" boot option for sev kernel command line*

Provide a "nosnp" kernel command line option to prevent enabling of the
RMP and SEV-SNP features in the host/hypervisor. Not initializing the
RMP removes system overhead associated with RMP checks.

Co-developed-by: Eric Van Tassell <Eric.VanTassell@amd.com>
Signed-off-by: Eric Van Tassell <Eric.VanTassell@amd.com>
Signed-off-by: Pavan Kumar Paluri <papaluri@amd.com>
Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>
---
 Documentation/arch/x86/x86_64/boot-options.rst | 5 +++++
 arch/x86/virt/svm/cmdline.c                    | 7 +++++++
 2 files changed, 12 insertions(+)

diff --git a/Documentation/arch/x86/x86_64/boot-options.rst b/Documentation/arch/x86/x86_64/boot-options.rst
index 98d4805f0823..d69e3cfbdba5 100644
--- a/Documentation/arch/x86/x86_64/boot-options.rst
+++ b/Documentation/arch/x86/x86_64/boot-options.rst
@@ -305,3 +305,8 @@ The available options are:
 
    debug
      Enable debug messages.
+
+   nosnp
+     Do not enable SEV-SNP (applies to host/hypervisor only). Setting
+     'nosnp' avoids the RMP check overhead in memory accesses when
+     users do not want to run SEV-SNP guests.
diff --git a/arch/x86/virt/svm/cmdline.c b/arch/x86/virt/svm/cmdline.c
index 9640507342e0..313415d6f53f 100644
--- a/arch/x86/virt/svm/cmdline.c
+++ b/arch/x86/virt/svm/cmdline.c
@@ -11,6 +11,7 @@
 #include <linux/printk.h>
 
 #include <asm/sev-common.h>
+#include <asm/cpufeature.h>
 
 struct sev_config sev_cfg __read_mostly;
 
@@ -24,6 +25,12 @@ static int __init init_sev_config(char *str)
 			continue;
 		}
 
+		if (!strcmp(s, "nosnp")) {
+			setup_clear_cpu_cap(X86_FEATURE_SEV_SNP);
+			cc_platform_clear(CC_ATTR_HOST_SEV_SNP);
+			continue;
+		}
+
 		pr_info("SEV command-line option '%s' was not recognized\n", s);
 	}

---

## [4] Borislav Petkov — 2024-10-11
*Subject: Re: [PATCH v6 1/2] x86, KVM:SVM: Move sev specific parsing into
 arch/x86/virt/svm*

On Thu, Oct 10, 2024 at 07:14:54AM -0500, Pavan Kumar Paluri wrote:
> Move SEV specific kernel command line option parsing support from
> arch/x86/coco/sev/core.c to arch/x86/virt/svm/cmdline.c so that both

make[5]: *** No rule to make target 'arch/x86/virt/svm/cmdline.o', needed by 'arch/x86/virt/svm/built-in.a'.  Stop.
make[5]: *** Waiting for unfinished jobs....
make[4]: *** [scripts/Makefile.build:478: arch/x86/virt/svm] Error 2
make[3]: *** [scripts/Makefile.build:478: arch/x86/virt] Error 2
make[3]: *** Waiting for unfinished jobs....
make[2]: *** [scripts/Makefile.build:478: arch/x86] Error 2
make[2]: *** Waiting for unfinished jobs....
make[1]: *** [/mnt/kernel/kernel/linux/Makefile:1936: .] Error 2
make: *** [Makefile:224: __sub-make] Error 2

$ ls arch/x86/virt/svm/cmdline.c
ls: cannot access 'arch/x86/virt/svm/cmdline.c': No such file or directory

Looks like you forgot to git add cmdline.c before committing.

---

## [5] Tom Lendacky — 2024-10-11
*Subject: Re: [PATCH v6 1/2] x86, KVM:SVM: Move sev specific parsing into
 arch/x86/virt/svm*

On 10/11/24 11:21, Borislav Petkov wrote:
> On Thu, Oct 10, 2024 at 07:14:54AM -0500, Pavan Kumar Paluri wrote:
>> Move SEV specific kernel command line option parsing support from

But the patch includes the new file, so how can that be?

Thanks,
Tom

>

---

## [6] Borislav Petkov — 2024-10-11
*Subject: Re: [PATCH v6 1/2] x86, KVM:SVM: Move sev specific parsing into
 arch/x86/virt/svm*

On Fri, Oct 11, 2024 at 11:35:40AM -0500, Tom Lendacky wrote:
> But the patch includes the new file, so how can that be?

Ah, wrong error, sorry.

This is his error:

arch/x86/virt/svm/cmdline.c:15:27: error: expected ‘=’, ‘,’, ‘;’, ‘asm’ or ‘__attribute__’ before ‘__read_mostly’
   15 | struct sev_config sev_cfg __read_mostly;
      |                           ^~~~~~~~~~~~~
make[5]: *** [scripts/Makefile.build:229: arch/x86/virt/svm/cmdline.o] Error 1
make[4]: *** [scripts/Makefile.build:478: arch/x86/virt/svm] Error 2
make[3]: *** [scripts/Makefile.build:478: arch/x86/virt] Error 2
make[3]: *** Waiting for unfinished jobs....
make[2]: *** [scripts/Makefile.build:478: arch/x86] Error 2
make[2]: *** Waiting for unfinished jobs....
make[1]: *** [/mnt/kernel/kernel/2nd/linux/Makefile:1936: .] Error 2
make: *** [Makefile:224: __sub-make] Error 2

---

## [7] Tom Lendacky — 2024-10-11
*Subject: Re: [PATCH v6 1/2] x86, KVM:SVM: Move sev specific parsing into
 arch/x86/virt/svm*

On 10/11/24 11:48, Borislav Petkov wrote:
> On Fri, Oct 11, 2024 at 11:35:40AM -0500, Tom Lendacky wrote:
>> But the patch includes the new file, so how can that be?

Ah, that makes more sense. Looks like he's missing the include for
linux/cache.h

Thanks,
Tom

>

---

## [8] Borislav Petkov — 2024-10-11
*Subject: Re: [PATCH v6 1/2] x86, KVM:SVM: Move sev specific parsing into
 arch/x86/virt/svm*

On Fri, Oct 11, 2024 at 11:55:14AM -0500, Tom Lendacky wrote:
> Ah, that makes more sense. Looks like he's missing the include for
> linux/cache.h 

"Changelog:
=========
v5:
...
  * Remove <asm/cache.h> stray header introduced in the previous
    versions because of __read_mostly attribute that is now moved into
    virt/svm/cmdline.c"

---

## [9] Paluri, PavanKumar — 2024-10-11
*Subject: Re: [PATCH v6 1/2] x86, KVM:SVM: Move sev specific parsing into
 arch/x86/virt/svm*

Hello Boris,

On 10/11/2024 11:59 AM, Borislav Petkov wrote:
> On Fri, Oct 11, 2024 at 11:55:14AM -0500, Tom Lendacky wrote:
>> Ah, that makes more sense. Looks like he's missing the include for

Yes, I am very sorry. I should have done a progressive build, which
could have helped me in spotting this issue.

This changelog points at removing <asm/cache.h> from
arch/x86/include/asm/sev-common.h (where __read_mostly was previously
present) and forgot to include this header to where it is now relocated
to. I will address this. On building the patchset (1 and 2 together), I
do not see the error, so this should have occurred on just building
Patch #1.

Thanks for the review.
Pavan

---

## [10] Borislav Petkov — 2024-10-12
*Subject: Re: [PATCH v6 1/2] x86, KVM:SVM: Move sev specific parsing into
 arch/x86/virt/svm*

On Fri, Oct 11, 2024 at 12:08:34PM -0500, Paluri, PavanKumar wrote:
> On building the patchset (1 and 2 together), I do not see the error, so this
> should have occurred on just building Patch #1.

You always, *always* must build-test each patch. 

Imagine someone is bisecting the kernel and bisection lands at your patch
which doesn't even build...

We can't have that.

---
