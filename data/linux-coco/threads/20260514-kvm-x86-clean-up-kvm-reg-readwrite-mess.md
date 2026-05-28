---
title: 'KVM: x86: Clean up kvm_<reg>_{read,write}() mess'
date: 2026-05-14
last_reply: 2026-05-21
message_count: 51
participants: ['Sean Christopherson', 'Yosry Ahmed', 'Binbin Wu', 'David Woodhouse', 'Huang, Kai']
---

## [1] Sean Christopherson — 2026-05-14

Add proper, explicit "raw" versions of kvm_<reg>_{read,write}(), along
with "e" versions (for hardcoded 32-bit accesses), and convert the
existing kvm_<reg>_{read,write}() APIs into mode-aware variants.

This was prompted by commit 435741a4e766 ("KVM: SVM: Properly check RAX
on #GP intercept of SVM instructions"), where using kvm_rax_read() to
get EAX/RAX would have (*very* surprisingly) been wrong as it's actually
a "raw" variant that doesn't truncate accesses when the guest is in 32-bit
mode.

Aside from my dislike of inconsistent APIs, I really want to avoid carrying
code that's subtly relying on using kvm_register_read(...) when accessing a
hardcoded register.

Fix a handful of minor warts along the way.

Oh, and introduce regs.{c,h}, which just a "minor" addendum.  Yosry pointed
out that moving _more_ code into x86.h was rather gross (especially since the
code split was super arbitrary), and it turns out that create regs.{c,h} isn't
all that hard.  In the future, I think we can also add msr.{c,h}, so I very
deliberately didn't include that functionality in regs.{c,h}.

v2:
 - Collect tags. [Yosry, Kai
 - Fix some truly egregious goofs. [Binbin]
 - Rename kvm_cache_regs.h => regs.h, add regs.c. [Yosry, though he'll
   probably yell at me for saying this was his suggestion :-) ]
 - Drop superfluous casting/masking of e*x() usage. [Kai]

v1: https://lore.kernel.org/all/20260409235622.2052730-1-seanjc@google.com

Sean Christopherson (15):
  KVM: SVM: Truncate INVLPGA address in compatibility mode
  KVM: x86/xen: Bug the VM if 32-bit KVM observes a 64-bit mode
    hypercall
  KVM: x86/xen: Don't truncate RAX when handling hypercall from
    protected guest
  KVM: VMX: Read 32-bit GPR values for ENCLS instructions outside of
    64-bit mode
  KVM: x86: Trace hypercall register *after* truncating values for
    32-bit
  KVM: x86: Rename kvm_cache_regs.h => regs.h
  KVM: x86: Move inlined CR and DR helpers from x86.h to regs.h
  KVM: x86: Add mode-aware versions of kvm_<reg>_{read,write}() helpers
  KVM: x86: Drop non-raw kvm_<reg>_write() helpers
  KVM: nSVM: Use kvm_rax_read() now that it's mode-aware
  Revert "KVM: VMX: Read 32-bit GPR values for ENCLS instructions
    outside of 64-bit mode"
  KVM: x86: Harden is_64_bit_hypercall() against bugs on 32-bit kernels
  KVM: x86: Move update_cr8_intercept() to lapic.c
  KVM: x86: Move kvm_pv_async_pf_enabled() to x86.h (as an inline)
  KVM: x86: Move the bulk of register specific code from x86.c to regs.c

 arch/x86/include/asm/kvm_host.h           |   2 -
 arch/x86/kvm/Makefile                     |   4 +-
 arch/x86/kvm/cpuid.c                      |  12 +-
 arch/x86/kvm/emulate.c                    |   2 +-
 arch/x86/kvm/hyperv.c                     |  21 +-
 arch/x86/kvm/hyperv.h                     |   4 +-
 arch/x86/kvm/lapic.c                      |  28 +-
 arch/x86/kvm/lapic.h                      |   1 +
 arch/x86/kvm/mmu.h                        |   2 +-
 arch/x86/kvm/mmu/mmu.c                    |   2 +-
 arch/x86/kvm/regs.c                       | 829 +++++++++++++++++++
 arch/x86/kvm/{kvm_cache_regs.h => regs.h} | 203 ++++-
 arch/x86/kvm/smm.c                        |   2 +-
 arch/x86/kvm/svm/nested.c                 |   8 +-
 arch/x86/kvm/svm/svm.c                    |  19 +-
 arch/x86/kvm/svm/svm.h                    |   2 +-
 arch/x86/kvm/vmx/nested.c                 |   8 +-
 arch/x86/kvm/vmx/nested.h                 |   2 +-
 arch/x86/kvm/vmx/sgx.c                    |   6 +-
 arch/x86/kvm/vmx/tdx.c                    |  18 +-
 arch/x86/kvm/vmx/vmx.c                    |   2 +-
 arch/x86/kvm/vmx/vmx.h                    |   2 +-
 arch/x86/kvm/x86.c                        | 935 +---------------------
 arch/x86/kvm/x86.h                        | 116 +--
 arch/x86/kvm/xen.c                        |  39 +-
 25 files changed, 1162 insertions(+), 1107 deletions(-)
 create mode 100644 arch/x86/kvm/regs.c
 rename arch/x86/kvm/{kvm_cache_regs.h => regs.h} (58%)


base-commit: a9512a611bd030088f13477258d1f8103cceaa40

---

## [2] Sean Christopherson — 2026-05-14
*Subject: [PATCH v2 01/15] KVM: SVM: Truncate INVLPGA address in compatibility mode*

Check for full 64-bit mode, not just long mode, when truncating the
virtual address as part of INVLPGA emulation.  Compatibility mode doesn't
support 64-bit addressing.

Note, the FIXME still applies, e.g. if the guest deliberately targeted
EAX while in 64-bit via an address size override.  That flaw isn't worth
fixing as it would require decoding the code stream, which would open a
an entirely different can of worms, and in practice no sane guest would
shove garbage into RAX[63:32] and execute INVLPGA.

Note #2, VMSAVE, VMLOAD, and VMRUN all suffer from the same architectural
flaw of not providing the full linear address in a VMCB exit information
field, because, quoting the APM verbatim:

  the linear address is available directly from the guest rAX register

(VMSAVE, VMLOAD, and VMRUN take a physical address, but they're behavior
with respect to rAX is otherwise identical).

Fixes: bc9eff67fc35 ("KVM: SVM: Use default rAX size for INVLPGA emulation")
Reviewed-by: Yosry Ahmed <yosry@kernel.org>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/svm/svm.c | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)

diff --git a/arch/x86/kvm/svm/svm.c b/arch/x86/kvm/svm/svm.c
index e74fcde6155e..4ad87f8df392 100644
--- a/arch/x86/kvm/svm/svm.c
+++ b/arch/x86/kvm/svm/svm.c
@@ -2415,7 +2415,7 @@ static int invlpga_interception(struct kvm_vcpu *vcpu)
 		return 1;
 
 	/* FIXME: Handle an address size prefix. */
-	if (!is_long_mode(vcpu))
+	if (!is_64_bit_mode(vcpu))
 		gva = (u32)gva;
 
 	trace_kvm_invlpga(to_svm(vcpu)->vmcb->save.rip, asid, gva);

---

## [3] Sean Christopherson — 2026-05-14
*Subject: [PATCH v2 02/15] KVM: x86/xen: Bug the VM if 32-bit KVM observes a
 64-bit mode hypercall*

Bug the VM if 32-bit KVM attempts to handle a 64-bit hypercall, primarily
so that a future change to set "input" in mode-specific code doesn't
trigger a false positive warn=>error:

  arch/x86/kvm/xen.c:1687:6: error: variable 'input' is used uninitialized
                                    whenever 'if' condition is false [-Werror,-Wsometimes-uninitialized]
   1687 |         if (!longmode) {
        |             ^~~~~~~~~
  arch/x86/kvm/xen.c:1708:31: note: uninitialized use occurs here
   1708 |         trace_kvm_xen_hypercall(cpl, input, params[0], params[1], params[2],
        |                                      ^~~~~
  x86/kvm/xen.c:1687:2: note: remove the 'if' if its condition is always true
   1687 |         if (!longmode) {
        |         ^~~~~~~~~~~~~~
  arch/x86/kvm/xen.c:1677:11: note: initialize the variable 'input' to silence this warning
   1677 |         u64 input, params[6], r = -ENOSYS;
        |                  ^
  1 error generated.

Note, params[] also has the same flaw, but -Wsometimes-uninitialized
doesn't seem to be enforced for arrays, presumably because it's difficult
to avoid false positives on specific entries.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/xen.c | 7 +++++--
 1 file changed, 5 insertions(+), 2 deletions(-)

diff --git a/arch/x86/kvm/xen.c b/arch/x86/kvm/xen.c
index 91fd3673c09a..6d9be74bb673 100644
--- a/arch/x86/kvm/xen.c
+++ b/arch/x86/kvm/xen.c
@@ -1694,16 +1694,19 @@ int kvm_xen_hypercall(struct kvm_vcpu *vcpu)
 		params[4] = (u32)kvm_rdi_read(vcpu);
 		params[5] = (u32)kvm_rbp_read(vcpu);
 	}
-#ifdef CONFIG_X86_64
 	else {
+#ifdef CONFIG_X86_64
 		params[0] = (u64)kvm_rdi_read(vcpu);
 		params[1] = (u64)kvm_rsi_read(vcpu);
 		params[2] = (u64)kvm_rdx_read(vcpu);
 		params[3] = (u64)kvm_r10_read(vcpu);
 		params[4] = (u64)kvm_r8_read(vcpu);
 		params[5] = (u64)kvm_r9_read(vcpu);
-	}
+#else
+		KVM_BUG_ON(1, vcpu->kvm);
+		return -EIO;
 #endif
+	}
 	cpl = kvm_x86_call(get_cpl)(vcpu);
 	trace_kvm_xen_hypercall(cpl, input, params[0], params[1], params[2],
 				params[3], params[4], params[5]);

---

## [4] Sean Christopherson — 2026-05-14
*Subject: [PATCH v2 03/15] KVM: x86/xen: Don't truncate RAX when handling
 hypercall from protected guest*

Don't truncate RAX when handling a Xen hypercall for a guest with protected
state, as KVM's ABI is to assume the guest is in 64-bit for such cases
(the guest leaving garbage in 63:32 after a transition to 32-bit mode is
far less likely than 63:32 being necessary to complete the hypercall).

Fixes: b5aead0064f3 ("KVM: x86: Assume a 64-bit hypercall for guests with protected state")
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/xen.c | 6 +++---
 1 file changed, 3 insertions(+), 3 deletions(-)

diff --git a/arch/x86/kvm/xen.c b/arch/x86/kvm/xen.c
index 6d9be74bb673..895095dc684e 100644
--- a/arch/x86/kvm/xen.c
+++ b/arch/x86/kvm/xen.c
@@ -1678,15 +1678,14 @@ int kvm_xen_hypercall(struct kvm_vcpu *vcpu)
 	bool handled = false;
 	u8 cpl;
 
-	input = (u64)kvm_register_read(vcpu, VCPU_REGS_RAX);
-
 	/* Hyper-V hypercalls get bit 31 set in EAX */
-	if ((input & 0x80000000) &&
+	if ((kvm_rax_read(vcpu) & 0x80000000) &&
 	    kvm_hv_hypercall_enabled(vcpu))
 		return kvm_hv_hypercall(vcpu);
 
 	longmode = is_64_bit_hypercall(vcpu);
 	if (!longmode) {
+		input = (u32)kvm_rax_read(vcpu);
 		params[0] = (u32)kvm_rbx_read(vcpu);
 		params[1] = (u32)kvm_rcx_read(vcpu);
 		params[2] = (u32)kvm_rdx_read(vcpu);
@@ -1696,6 +1695,7 @@ int kvm_xen_hypercall(struct kvm_vcpu *vcpu)
 	}
 	else {
 #ifdef CONFIG_X86_64
+		input = (u64)kvm_rax_read(vcpu);
 		params[0] = (u64)kvm_rdi_read(vcpu);
 		params[1] = (u64)kvm_rsi_read(vcpu);
 		params[2] = (u64)kvm_rdx_read(vcpu);

---

## [5] Sean Christopherson — 2026-05-14
*Subject: [PATCH v2 04/15] KVM: VMX: Read 32-bit GPR values for ENCLS
 instructions outside of 64-bit mode*

When getting register values for ENCLS emulation, use kvm_register_read()
instead of kvm_<reg>_read() so that bits 63:32 of the register are dropped
if the guest is in 32-bit mode.

Note, the misleading/surprising behavior of kvm_<reg>_read() being "raw"
variants under the hood will be addressed once all non-benign bugs are
fixed.

Fixes: 70210c044b4e ("KVM: VMX: Add SGX ENCLS[ECREATE] handler to enforce CPUID restrictions")
Fixes: b6f084ca5538 ("KVM: VMX: Add ENCLS[EINIT] handler to support SGX Launch Control (LC)")
Acked-by: Kai Huang <kai.huang@intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/vmx/sgx.c | 10 +++++-----
 1 file changed, 5 insertions(+), 5 deletions(-)

diff --git a/arch/x86/kvm/vmx/sgx.c b/arch/x86/kvm/vmx/sgx.c
index df1d0cf76947..4c61fc33f764 100644
--- a/arch/x86/kvm/vmx/sgx.c
+++ b/arch/x86/kvm/vmx/sgx.c
@@ -225,8 +225,8 @@ static int handle_encls_ecreate(struct kvm_vcpu *vcpu)
 	struct x86_exception ex;
 	int r;
 
-	if (sgx_get_encls_gva(vcpu, kvm_rbx_read(vcpu), 32, 32, &pageinfo_gva) ||
-	    sgx_get_encls_gva(vcpu, kvm_rcx_read(vcpu), 4096, 4096, &secs_gva))
+	if (sgx_get_encls_gva(vcpu, kvm_register_read(vcpu, VCPU_REGS_RBX), 32, 32, &pageinfo_gva) ||
+	    sgx_get_encls_gva(vcpu, kvm_register_read(vcpu, VCPU_REGS_RCX), 4096, 4096, &secs_gva))
 		return 1;
 
 	/*
@@ -302,9 +302,9 @@ static int handle_encls_einit(struct kvm_vcpu *vcpu)
 	gpa_t sig_gpa, secs_gpa, token_gpa;
 	int ret, trapnr;
 
-	if (sgx_get_encls_gva(vcpu, kvm_rbx_read(vcpu), 1808, 4096, &sig_gva) ||
-	    sgx_get_encls_gva(vcpu, kvm_rcx_read(vcpu), 4096, 4096, &secs_gva) ||
-	    sgx_get_encls_gva(vcpu, kvm_rdx_read(vcpu), 304, 512, &token_gva))
+	if (sgx_get_encls_gva(vcpu, kvm_register_read(vcpu, VCPU_REGS_RBX), 1808, 4096, &sig_gva) ||
+	    sgx_get_encls_gva(vcpu, kvm_register_read(vcpu, VCPU_REGS_RCX), 4096, 4096, &secs_gva) ||
+	    sgx_get_encls_gva(vcpu, kvm_register_read(vcpu, VCPU_REGS_RDX), 304, 512, &token_gva))
 		return 1;
 
 	/*

---

## [6] Sean Christopherson — 2026-05-14
*Subject: [PATCH v2 05/15] KVM: x86: Trace hypercall register *after*
 truncating values for 32-bit*

When tracing hypercalls, invoke the tracepoint *after* truncating the
register values for 32-bit guests so as not to record unused garbage (in
the extremely unlikely scenario that the guest left garbage in a register
after transitioning from 64-bit mode to 32-bit mode).

Fixes: 229456fc34b1 ("KVM: convert custom marker based tracing to event traces")
Reviewed-by: Yosry Ahmed <yosry@kernel.org>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/x86.c | 4 ++--
 1 file changed, 2 insertions(+), 2 deletions(-)

diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index 209eae67ab18..23b3957b9ae0 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -10430,8 +10430,6 @@ int ____kvm_emulate_hypercall(struct kvm_vcpu *vcpu, int cpl,
 
 	++vcpu->stat.hypercalls;
 
-	trace_kvm_hypercall(nr, a0, a1, a2, a3);
-
 	if (!op_64_bit) {
 		nr &= 0xFFFFFFFF;
 		a0 &= 0xFFFFFFFF;
@@ -10440,6 +10438,8 @@ int ____kvm_emulate_hypercall(struct kvm_vcpu *vcpu, int cpl,
 		a3 &= 0xFFFFFFFF;
 	}
 
+	trace_kvm_hypercall(nr, a0, a1, a2, a3);
+
 	if (cpl) {
 		ret = -KVM_EPERM;
 		goto out;

---

## [7] Sean Christopherson — 2026-05-14
*Subject: [PATCH v2 06/15] KVM: x86: Rename kvm_cache_regs.h => regs.h*

Rename kvm_cache_regs.h to simply regs.h, as the "cache" nomenclature is
already a lie (the file deals with state/registers that aren't cached per
se), and so that more code/functionality can be landed in the header
without making it a truly horrible misnomer.

Deliberately drop the kvm_ prefix/namespace to align with other "local"
headers, and to further differentiate regs.h from the public/global
arch/x86/include/asm/kvm_vcpu_regs.h, which sadly needs to stay in asm/
so that the number of registers can be referenced by kvm_vcpu_arch.

No functional change intended.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/emulate.c                    | 2 +-
 arch/x86/kvm/lapic.c                      | 2 +-
 arch/x86/kvm/mmu.h                        | 2 +-
 arch/x86/kvm/mmu/mmu.c                    | 2 +-
 arch/x86/kvm/{kvm_cache_regs.h => regs.h} | 4 ++--
 arch/x86/kvm/smm.c                        | 2 +-
 arch/x86/kvm/svm/svm.c                    | 2 +-
 arch/x86/kvm/svm/svm.h                    | 2 +-
 arch/x86/kvm/vmx/nested.h                 | 2 +-
 arch/x86/kvm/vmx/sgx.c                    | 2 +-
 arch/x86/kvm/vmx/vmx.c                    | 2 +-
 arch/x86/kvm/vmx/vmx.h                    | 2 +-
 arch/x86/kvm/x86.c                        | 2 +-
 arch/x86/kvm/x86.h                        | 2 +-
 14 files changed, 15 insertions(+), 15 deletions(-)
 rename arch/x86/kvm/{kvm_cache_regs.h => regs.h} (99%)

diff --git a/arch/x86/kvm/emulate.c b/arch/x86/kvm/emulate.c
index 8013dccb3110..6e64761f64b1 100644
--- a/arch/x86/kvm/emulate.c
+++ b/arch/x86/kvm/emulate.c
@@ -20,7 +20,7 @@
 #define pr_fmt(fmt) KBUILD_MODNAME ": " fmt
 
 #include <linux/kvm_host.h>
-#include "kvm_cache_regs.h"
+#include "regs.h"
 #include "kvm_emulate.h"
 #include <linux/stringify.h>
 #include <asm/debugreg.h>
diff --git a/arch/x86/kvm/lapic.c b/arch/x86/kvm/lapic.c
index 4078e624ca66..d8dbfb107bfb 100644
--- a/arch/x86/kvm/lapic.c
+++ b/arch/x86/kvm/lapic.c
@@ -37,7 +37,7 @@
 #include <asm/delay.h>
 #include <linux/atomic.h>
 #include <linux/jump_label.h>
-#include "kvm_cache_regs.h"
+#include "regs.h"
 #include "irq.h"
 #include "ioapic.h"
 #include "trace.h"
diff --git a/arch/x86/kvm/mmu.h b/arch/x86/kvm/mmu.h
index ddf4e467c071..e1bb663ebbd5 100644
--- a/arch/x86/kvm/mmu.h
+++ b/arch/x86/kvm/mmu.h
@@ -3,7 +3,7 @@
 #define __KVM_X86_MMU_H
 
 #include <linux/kvm_host.h>
-#include "kvm_cache_regs.h"
+#include "regs.h"
 #include "x86.h"
 #include "cpuid.h"
 
diff --git a/arch/x86/kvm/mmu/mmu.c b/arch/x86/kvm/mmu/mmu.c
index c87c26bf4149..b8f2edf2cfeb 100644
--- a/arch/x86/kvm/mmu/mmu.c
+++ b/arch/x86/kvm/mmu/mmu.c
@@ -22,7 +22,7 @@
 #include "mmu_internal.h"
 #include "tdp_mmu.h"
 #include "x86.h"
-#include "kvm_cache_regs.h"
+#include "regs.h"
 #include "smm.h"
 #include "kvm_emulate.h"
 #include "page_track.h"
diff --git a/arch/x86/kvm/kvm_cache_regs.h b/arch/x86/kvm/regs.h
similarity index 99%
rename from arch/x86/kvm/kvm_cache_regs.h
rename to arch/x86/kvm/regs.h
index 2ae492ad6412..4440f3992fce 100644
--- a/arch/x86/kvm/kvm_cache_regs.h
+++ b/arch/x86/kvm/regs.h
@@ -1,6 +1,6 @@
 /* SPDX-License-Identifier: GPL-2.0 */
-#ifndef ASM_KVM_CACHE_REGS_H
-#define ASM_KVM_CACHE_REGS_H
+#ifndef ARCH_X86_KVM_REGS_H
+#define ARCH_X86_KVM_REGS_H
 
 #include <linux/kvm_host.h>
 
diff --git a/arch/x86/kvm/smm.c b/arch/x86/kvm/smm.c
index f623c5986119..a446487bdd5c 100644
--- a/arch/x86/kvm/smm.c
+++ b/arch/x86/kvm/smm.c
@@ -3,7 +3,7 @@
 
 #include <linux/kvm_host.h>
 #include "x86.h"
-#include "kvm_cache_regs.h"
+#include "regs.h"
 #include "kvm_emulate.h"
 #include "smm.h"
 #include "cpuid.h"
diff --git a/arch/x86/kvm/svm/svm.c b/arch/x86/kvm/svm/svm.c
index 4ad87f8df392..be775d285ce7 100644
--- a/arch/x86/kvm/svm/svm.c
+++ b/arch/x86/kvm/svm/svm.c
@@ -4,7 +4,7 @@
 
 #include "irq.h"
 #include "mmu.h"
-#include "kvm_cache_regs.h"
+#include "regs.h"
 #include "x86.h"
 #include "smm.h"
 #include "cpuid.h"
diff --git a/arch/x86/kvm/svm/svm.h b/arch/x86/kvm/svm/svm.h
index 2b6733dffd76..b8c7f4535691 100644
--- a/arch/x86/kvm/svm/svm.h
+++ b/arch/x86/kvm/svm/svm.h
@@ -23,7 +23,7 @@
 #include <asm/sev-common.h>
 
 #include "cpuid.h"
-#include "kvm_cache_regs.h"
+#include "regs.h"
 #include "x86.h"
 
 /*
diff --git a/arch/x86/kvm/vmx/nested.h b/arch/x86/kvm/vmx/nested.h
index 213a448104af..6d6cd5904ddf 100644
--- a/arch/x86/kvm/vmx/nested.h
+++ b/arch/x86/kvm/vmx/nested.h
@@ -2,7 +2,7 @@
 #ifndef __KVM_X86_VMX_NESTED_H
 #define __KVM_X86_VMX_NESTED_H
 
-#include "kvm_cache_regs.h"
+#include "regs.h"
 #include "hyperv.h"
 #include "vmcs12.h"
 #include "vmx.h"
diff --git a/arch/x86/kvm/vmx/sgx.c b/arch/x86/kvm/vmx/sgx.c
index 4c61fc33f764..66c315554b46 100644
--- a/arch/x86/kvm/vmx/sgx.c
+++ b/arch/x86/kvm/vmx/sgx.c
@@ -6,7 +6,7 @@
 #include <asm/sgx.h>
 
 #include "x86.h"
-#include "kvm_cache_regs.h"
+#include "regs.h"
 #include "nested.h"
 #include "sgx.h"
 #include "vmx.h"
diff --git a/arch/x86/kvm/vmx/vmx.c b/arch/x86/kvm/vmx/vmx.c
index b02d176800f8..67bc6edfd856 100644
--- a/arch/x86/kvm/vmx/vmx.c
+++ b/arch/x86/kvm/vmx/vmx.c
@@ -59,7 +59,7 @@
 #include "hyperv.h"
 #include "kvm_onhyperv.h"
 #include "irq.h"
-#include "kvm_cache_regs.h"
+#include "regs.h"
 #include "lapic.h"
 #include "mmu.h"
 #include "nested.h"
diff --git a/arch/x86/kvm/vmx/vmx.h b/arch/x86/kvm/vmx/vmx.h
index daedf663c0a9..de9de0d2016c 100644
--- a/arch/x86/kvm/vmx/vmx.h
+++ b/arch/x86/kvm/vmx/vmx.h
@@ -10,7 +10,7 @@
 #include <asm/posted_intr.h>
 
 #include "capabilities.h"
-#include "../kvm_cache_regs.h"
+#include "../regs.h"
 #include "pmu_intel.h"
 #include "vmcs.h"
 #include "vmx_ops.h"
diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index 23b3957b9ae0..ab13aed2cbd0 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -23,7 +23,7 @@
 #include "mmu.h"
 #include "i8254.h"
 #include "tss.h"
-#include "kvm_cache_regs.h"
+#include "regs.h"
 #include "kvm_emulate.h"
 #include "mmu/page_track.h"
 #include "x86.h"
diff --git a/arch/x86/kvm/x86.h b/arch/x86/kvm/x86.h
index 38a905fa86de..2bbecc83ecc2 100644
--- a/arch/x86/kvm/x86.h
+++ b/arch/x86/kvm/x86.h
@@ -6,7 +6,7 @@
 #include <asm/fpu/xstate.h>
 #include <asm/mce.h>
 #include <asm/pvclock.h>
-#include "kvm_cache_regs.h"
+#include "regs.h"
 #include "kvm_emulate.h"
 #include "cpuid.h"

---

## [8] Sean Christopherson — 2026-05-14
*Subject: [PATCH v2 07/15] KVM: x86: Move inlined CR and DR helpers from x86.h
 to regs.h*

Move inlined Control Register and Debug Register helpers from x86.h to the
aptly named regs.h, to help trim down x86.h (and x86.c in the future).

Move select EFER functionality, but leave behind all other MSR handling,
There is more than enough MSR code to carve out msr.{c,h} in the future.
Give EFER special treatment as it's an "MSR" in name only, e.g. it's has
far more in common with CR4 than it does with any MSR.

No functional change intended.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/regs.h | 108 ++++++++++++++++++++++++++++++++++++++++++--
 arch/x86/kvm/x86.h  | 102 -----------------------------------------
 2 files changed, 105 insertions(+), 105 deletions(-)

diff --git a/arch/x86/kvm/regs.h b/arch/x86/kvm/regs.h
index 4440f3992fce..ecc66b577e82 100644
--- a/arch/x86/kvm/regs.h
+++ b/arch/x86/kvm/regs.h
@@ -16,6 +16,37 @@
 
 static_assert(!(KVM_POSSIBLE_CR0_GUEST_BITS & X86_CR0_PDPTR_BITS));
 
+static inline bool is_long_mode(struct kvm_vcpu *vcpu)
+{
+#ifdef CONFIG_X86_64
+	return !!(vcpu->arch.efer & EFER_LMA);
+#else
+	return false;
+#endif
+}
+
+static inline bool is_64_bit_mode(struct kvm_vcpu *vcpu)
+{
+	int cs_db, cs_l;
+
+	WARN_ON_ONCE(vcpu->arch.guest_state_protected);
+
+	if (!is_long_mode(vcpu))
+		return false;
+	kvm_x86_call(get_cs_db_l_bits)(vcpu, &cs_db, &cs_l);
+	return cs_l;
+}
+
+static inline bool is_64_bit_hypercall(struct kvm_vcpu *vcpu)
+{
+	/*
+	 * If running with protected guest state, the CS register is not
+	 * accessible. The hypercall register values will have had to been
+	 * provided in 64-bit mode, so assume the guest is in 64-bit.
+	 */
+	return vcpu->arch.guest_state_protected || is_64_bit_mode(vcpu);
+}
+
 #define BUILD_KVM_GPR_ACCESSORS(lname, uname)				      \
 static __always_inline unsigned long kvm_##lname##_read(struct kvm_vcpu *vcpu)\
 {									      \
@@ -177,6 +208,12 @@ static inline void kvm_rsp_write(struct kvm_vcpu *vcpu, unsigned long val)
 	kvm_register_write_raw(vcpu, VCPU_REGS_RSP, val);
 }
 
+static inline u64 kvm_read_edx_eax(struct kvm_vcpu *vcpu)
+{
+	return (kvm_rax_read(vcpu) & -1u)
+		| ((u64)(kvm_rdx_read(vcpu) & -1u) << 32);
+}
+
 static inline u64 kvm_pdptr_read(struct kvm_vcpu *vcpu, int index)
 {
 	might_sleep();  /* on svm */
@@ -243,10 +280,75 @@ static inline ulong kvm_read_cr4(struct kvm_vcpu *vcpu)
 	return kvm_read_cr4_bits(vcpu, ~0UL);
 }
 
-static inline u64 kvm_read_edx_eax(struct kvm_vcpu *vcpu)
+static inline bool __kvm_is_valid_cr4(struct kvm_vcpu *vcpu, unsigned long cr4)
 {
-	return (kvm_rax_read(vcpu) & -1u)
-		| ((u64)(kvm_rdx_read(vcpu) & -1u) << 32);
+	return !(cr4 & vcpu->arch.cr4_guest_rsvd_bits);
+}
+
+#define __cr4_reserved_bits(__cpu_has, __c)             \
+({                                                      \
+	u64 __reserved_bits = CR4_RESERVED_BITS;        \
+                                                        \
+	if (!__cpu_has(__c, X86_FEATURE_XSAVE))         \
+		__reserved_bits |= X86_CR4_OSXSAVE;     \
+	if (!__cpu_has(__c, X86_FEATURE_SMEP))          \
+		__reserved_bits |= X86_CR4_SMEP;        \
+	if (!__cpu_has(__c, X86_FEATURE_SMAP))          \
+		__reserved_bits |= X86_CR4_SMAP;        \
+	if (!__cpu_has(__c, X86_FEATURE_FSGSBASE))      \
+		__reserved_bits |= X86_CR4_FSGSBASE;    \
+	if (!__cpu_has(__c, X86_FEATURE_PKU))           \
+		__reserved_bits |= X86_CR4_PKE;         \
+	if (!__cpu_has(__c, X86_FEATURE_LA57))          \
+		__reserved_bits |= X86_CR4_LA57;        \
+	if (!__cpu_has(__c, X86_FEATURE_UMIP))          \
+		__reserved_bits |= X86_CR4_UMIP;        \
+	if (!__cpu_has(__c, X86_FEATURE_VMX))           \
+		__reserved_bits |= X86_CR4_VMXE;        \
+	if (!__cpu_has(__c, X86_FEATURE_PCID))          \
+		__reserved_bits |= X86_CR4_PCIDE;       \
+	if (!__cpu_has(__c, X86_FEATURE_LAM))           \
+		__reserved_bits |= X86_CR4_LAM_SUP;     \
+	if (!__cpu_has(__c, X86_FEATURE_SHSTK) &&       \
+	    !__cpu_has(__c, X86_FEATURE_IBT))           \
+		__reserved_bits |= X86_CR4_CET;         \
+	__reserved_bits;                                \
+})
+
+static inline bool is_protmode(struct kvm_vcpu *vcpu)
+{
+	return kvm_is_cr0_bit_set(vcpu, X86_CR0_PE);
+}
+
+static inline bool is_pae(struct kvm_vcpu *vcpu)
+{
+	return kvm_is_cr4_bit_set(vcpu, X86_CR4_PAE);
+}
+
+static inline bool is_pse(struct kvm_vcpu *vcpu)
+{
+	return kvm_is_cr4_bit_set(vcpu, X86_CR4_PSE);
+}
+
+static inline bool is_paging(struct kvm_vcpu *vcpu)
+{
+	return likely(kvm_is_cr0_bit_set(vcpu, X86_CR0_PG));
+}
+
+static inline bool is_pae_paging(struct kvm_vcpu *vcpu)
+{
+	return !is_long_mode(vcpu) && is_pae(vcpu) && is_paging(vcpu);
+}
+
+static inline bool kvm_dr7_valid(u64 data)
+{
+	/* Bits [63:32] are reserved */
+	return !(data >> 32);
+}
+static inline bool kvm_dr6_valid(u64 data)
+{
+	/* Bits [63:32] are reserved */
+	return !(data >> 32);
 }
 
 static inline void enter_guest_mode(struct kvm_vcpu *vcpu)
diff --git a/arch/x86/kvm/x86.h b/arch/x86/kvm/x86.h
index 2bbecc83ecc2..16d1c3c1a2d9 100644
--- a/arch/x86/kvm/x86.h
+++ b/arch/x86/kvm/x86.h
@@ -243,42 +243,6 @@ static inline bool kvm_exception_is_soft(unsigned int nr)
 	return (nr == BP_VECTOR) || (nr == OF_VECTOR);
 }
 
-static inline bool is_protmode(struct kvm_vcpu *vcpu)
-{
-	return kvm_is_cr0_bit_set(vcpu, X86_CR0_PE);
-}
-
-static inline bool is_long_mode(struct kvm_vcpu *vcpu)
-{
-#ifdef CONFIG_X86_64
-	return !!(vcpu->arch.efer & EFER_LMA);
-#else
-	return false;
-#endif
-}
-
-static inline bool is_64_bit_mode(struct kvm_vcpu *vcpu)
-{
-	int cs_db, cs_l;
-
-	WARN_ON_ONCE(vcpu->arch.guest_state_protected);
-
-	if (!is_long_mode(vcpu))
-		return false;
-	kvm_x86_call(get_cs_db_l_bits)(vcpu, &cs_db, &cs_l);
-	return cs_l;
-}
-
-static inline bool is_64_bit_hypercall(struct kvm_vcpu *vcpu)
-{
-	/*
-	 * If running with protected guest state, the CS register is not
-	 * accessible. The hypercall register values will have had to been
-	 * provided in 64-bit mode, so assume the guest is in 64-bit.
-	 */
-	return vcpu->arch.guest_state_protected || is_64_bit_mode(vcpu);
-}
-
 static inline bool x86_exception_has_error_code(unsigned int vector)
 {
 	static u32 exception_has_error_code = BIT(DF_VECTOR) | BIT(TS_VECTOR) |
@@ -293,26 +257,6 @@ static inline bool mmu_is_nested(struct kvm_vcpu *vcpu)
 	return vcpu->arch.walk_mmu == &vcpu->arch.nested_mmu;
 }
 
-static inline bool is_pae(struct kvm_vcpu *vcpu)
-{
-	return kvm_is_cr4_bit_set(vcpu, X86_CR4_PAE);
-}
-
-static inline bool is_pse(struct kvm_vcpu *vcpu)
-{
-	return kvm_is_cr4_bit_set(vcpu, X86_CR4_PSE);
-}
-
-static inline bool is_paging(struct kvm_vcpu *vcpu)
-{
-	return likely(kvm_is_cr0_bit_set(vcpu, X86_CR0_PG));
-}
-
-static inline bool is_pae_paging(struct kvm_vcpu *vcpu)
-{
-	return !is_long_mode(vcpu) && is_pae(vcpu) && is_paging(vcpu);
-}
-
 static inline u8 vcpu_virt_addr_bits(struct kvm_vcpu *vcpu)
 {
 	return kvm_is_cr4_bit_set(vcpu, X86_CR4_LA57) ? 57 : 48;
@@ -630,17 +574,6 @@ static inline bool kvm_pat_valid(u64 data)
 	return (data | ((data & 0x0202020202020202ull) << 1)) == data;
 }
 
-static inline bool kvm_dr7_valid(u64 data)
-{
-	/* Bits [63:32] are reserved */
-	return !(data >> 32);
-}
-static inline bool kvm_dr6_valid(u64 data)
-{
-	/* Bits [63:32] are reserved */
-	return !(data >> 32);
-}
-
 /*
  * Trigger machine check on the host. We assume all the MSRs are already set up
  * by the CPU and that we still run on the same CPU as the MCE occurred on.
@@ -687,41 +620,6 @@ enum kvm_msr_access {
 #define  KVM_MSR_RET_UNSUPPORTED	2
 #define  KVM_MSR_RET_FILTERED		3
 
-static inline bool __kvm_is_valid_cr4(struct kvm_vcpu *vcpu, unsigned long cr4)
-{
-	return !(cr4 & vcpu->arch.cr4_guest_rsvd_bits);
-}
-
-#define __cr4_reserved_bits(__cpu_has, __c)             \
-({                                                      \
-	u64 __reserved_bits = CR4_RESERVED_BITS;        \
-                                                        \
-	if (!__cpu_has(__c, X86_FEATURE_XSAVE))         \
-		__reserved_bits |= X86_CR4_OSXSAVE;     \
-	if (!__cpu_has(__c, X86_FEATURE_SMEP))          \
-		__reserved_bits |= X86_CR4_SMEP;        \
-	if (!__cpu_has(__c, X86_FEATURE_SMAP))          \
-		__reserved_bits |= X86_CR4_SMAP;        \
-	if (!__cpu_has(__c, X86_FEATURE_FSGSBASE))      \
-		__reserved_bits |= X86_CR4_FSGSBASE;    \
-	if (!__cpu_has(__c, X86_FEATURE_PKU))           \
-		__reserved_bits |= X86_CR4_PKE;         \
-	if (!__cpu_has(__c, X86_FEATURE_LA57))          \
-		__reserved_bits |= X86_CR4_LA57;        \
-	if (!__cpu_has(__c, X86_FEATURE_UMIP))          \
-		__reserved_bits |= X86_CR4_UMIP;        \
-	if (!__cpu_has(__c, X86_FEATURE_VMX))           \
-		__reserved_bits |= X86_CR4_VMXE;        \
-	if (!__cpu_has(__c, X86_FEATURE_PCID))          \
-		__reserved_bits |= X86_CR4_PCIDE;       \
-	if (!__cpu_has(__c, X86_FEATURE_LAM))           \
-		__reserved_bits |= X86_CR4_LAM_SUP;     \
-	if (!__cpu_has(__c, X86_FEATURE_SHSTK) &&       \
-	    !__cpu_has(__c, X86_FEATURE_IBT))           \
-		__reserved_bits |= X86_CR4_CET;         \
-	__reserved_bits;                                \
-})
-
 int kvm_sev_es_mmio(struct kvm_vcpu *vcpu, bool is_write, gpa_t gpa,
 		    unsigned int bytes, void *data);
 int kvm_sev_es_string_io(struct kvm_vcpu *vcpu, unsigned int size,

---

## [9] Sean Christopherson — 2026-05-14
*Subject: [PATCH v2 08/15] KVM: x86: Add mode-aware versions of
 kvm_<reg>_{read,write}() helpers*

Make kvm_<reg>_{read,write}() mode-aware (where the value is truncated to
32 bits if the vCPU isn't in 64-bit mode), and convert all the intentional
"raw" accesses to kvm_<reg>_{read,write}_raw() versions.  To avoid
confusion and bikeshedding over whether or not explicit 32-bit accesses
should use the "raw" or mode-aware variants, add and use "e" versions, e.g.
for things like RDMSR, WRMSR, and CPUID, where the instruction uses only
only bits 31:0, regardless of mode.

No functional change intended (all use of "e" versions is for cases where
the value is already truncated due to bouncing through a u32).

Cc: Binbin Wu <binbin.wu@linux.intel.com>
Cc: Kai Huang <kai.huang@intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/cpuid.c      |  12 ++--
 arch/x86/kvm/hyperv.c     |  21 +++----
 arch/x86/kvm/hyperv.h     |   4 +-
 arch/x86/kvm/regs.h       |  80 +++++++++++++++++--------
 arch/x86/kvm/svm/nested.c |   6 +-
 arch/x86/kvm/svm/svm.c    |  13 ++--
 arch/x86/kvm/vmx/nested.c |   8 +--
 arch/x86/kvm/vmx/sgx.c    |   4 +-
 arch/x86/kvm/vmx/tdx.c    |  18 +++---
 arch/x86/kvm/x86.c        | 121 +++++++++++++++++++-------------------
 arch/x86/kvm/x86.h        |   8 +--
 arch/x86/kvm/xen.c        |  32 +++++-----
 12 files changed, 173 insertions(+), 154 deletions(-)

diff --git a/arch/x86/kvm/cpuid.c b/arch/x86/kvm/cpuid.c
index e69156b54cff..fe765f1c3b15 100644
--- a/arch/x86/kvm/cpuid.c
+++ b/arch/x86/kvm/cpuid.c
@@ -2165,13 +2165,13 @@ int kvm_emulate_cpuid(struct kvm_vcpu *vcpu)
 	    !kvm_require_cpl(vcpu, 0))
 		return 1;
 
-	eax = kvm_rax_read(vcpu);
-	ecx = kvm_rcx_read(vcpu);
+	eax = kvm_eax_read(vcpu);
+	ecx = kvm_ecx_read(vcpu);
 	kvm_cpuid(vcpu, &eax, &ebx, &ecx, &edx, false);
-	kvm_rax_write(vcpu, eax);
-	kvm_rbx_write(vcpu, ebx);
-	kvm_rcx_write(vcpu, ecx);
-	kvm_rdx_write(vcpu, edx);
+	kvm_eax_write(vcpu, eax);
+	kvm_ebx_write(vcpu, ebx);
+	kvm_ecx_write(vcpu, ecx);
+	kvm_edx_write(vcpu, edx);
 	return kvm_skip_emulated_instruction(vcpu);
 }
 EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_emulate_cpuid);
diff --git a/arch/x86/kvm/hyperv.c b/arch/x86/kvm/hyperv.c
index 015c6947b462..3551af9a9453 100644
--- a/arch/x86/kvm/hyperv.c
+++ b/arch/x86/kvm/hyperv.c
@@ -2377,10 +2377,10 @@ static void kvm_hv_hypercall_set_result(struct kvm_vcpu *vcpu, u64 result)
 
 	longmode = is_64_bit_hypercall(vcpu);
 	if (longmode)
-		kvm_rax_write(vcpu, result);
+		kvm_rax_write_raw(vcpu, result);
 	else {
-		kvm_rdx_write(vcpu, result >> 32);
-		kvm_rax_write(vcpu, result & 0xffffffff);
+		kvm_edx_write(vcpu, result >> 32);
+		kvm_eax_write(vcpu, result);
 	}
 }
 
@@ -2544,18 +2544,15 @@ int kvm_hv_hypercall(struct kvm_vcpu *vcpu)
 
 #ifdef CONFIG_X86_64
 	if (is_64_bit_hypercall(vcpu)) {
-		hc.param = kvm_rcx_read(vcpu);
-		hc.ingpa = kvm_rdx_read(vcpu);
-		hc.outgpa = kvm_r8_read(vcpu);
+		hc.param = kvm_rcx_read_raw(vcpu);
+		hc.ingpa = kvm_rdx_read_raw(vcpu);
+		hc.outgpa = kvm_r8_read_raw(vcpu);
 	} else
 #endif
 	{
-		hc.param = ((u64)kvm_rdx_read(vcpu) << 32) |
-			    (kvm_rax_read(vcpu) & 0xffffffff);
-		hc.ingpa = ((u64)kvm_rbx_read(vcpu) << 32) |
-			    (kvm_rcx_read(vcpu) & 0xffffffff);
-		hc.outgpa = ((u64)kvm_rdi_read(vcpu) << 32) |
-			     (kvm_rsi_read(vcpu) & 0xffffffff);
+		hc.param = ((u64)kvm_edx_read(vcpu) << 32) | kvm_eax_read(vcpu);
+		hc.ingpa = ((u64)kvm_ebx_read(vcpu) << 32) | kvm_ecx_read(vcpu);
+		hc.outgpa = ((u64)kvm_edi_read(vcpu) << 32) | kvm_esi_read(vcpu);
 	}
 
 	hc.code = hc.param & 0xffff;
diff --git a/arch/x86/kvm/hyperv.h b/arch/x86/kvm/hyperv.h
index 6301f79fcbae..65e89ed65349 100644
--- a/arch/x86/kvm/hyperv.h
+++ b/arch/x86/kvm/hyperv.h
@@ -232,8 +232,8 @@ static inline bool kvm_hv_is_tlb_flush_hcall(struct kvm_vcpu *vcpu)
 	if (!hv_vcpu)
 		return false;
 
-	code = is_64_bit_hypercall(vcpu) ? kvm_rcx_read(vcpu) :
-					   kvm_rax_read(vcpu);
+	code = is_64_bit_hypercall(vcpu) ? kvm_rcx_read_raw(vcpu) :
+					   kvm_eax_read(vcpu);
 
 	return (code == HVCALL_FLUSH_VIRTUAL_ADDRESS_SPACE ||
 		code == HVCALL_FLUSH_VIRTUAL_ADDRESS_LIST ||
diff --git a/arch/x86/kvm/regs.h b/arch/x86/kvm/regs.h
index ecc66b577e82..b28e71caed25 100644
--- a/arch/x86/kvm/regs.h
+++ b/arch/x86/kvm/regs.h
@@ -47,32 +47,61 @@ static inline bool is_64_bit_hypercall(struct kvm_vcpu *vcpu)
 	return vcpu->arch.guest_state_protected || is_64_bit_mode(vcpu);
 }
 
-#define BUILD_KVM_GPR_ACCESSORS(lname, uname)				      \
-static __always_inline unsigned long kvm_##lname##_read(struct kvm_vcpu *vcpu)\
-{									      \
-	return vcpu->arch.regs[VCPU_REGS_##uname];			      \
-}									      \
-static __always_inline void kvm_##lname##_write(struct kvm_vcpu *vcpu,	      \
-						unsigned long val)	      \
-{									      \
-	vcpu->arch.regs[VCPU_REGS_##uname] = val;			      \
+static __always_inline unsigned long kvm_reg_mode_mask(struct kvm_vcpu *vcpu)
+{
+#ifdef CONFIG_X86_64
+	return is_64_bit_mode(vcpu) ? GENMASK(63, 0) : GENMASK(31, 0);
+#else
+	return GENMASK(31, 0);
+#endif
+}
+
+#define __BUILD_KVM_GPR_ACCESSORS(lname, uname)						\
+static __always_inline unsigned long kvm_##lname##_read(struct kvm_vcpu *vcpu)		\
+{											\
+	return vcpu->arch.regs[VCPU_REGS_##uname] & kvm_reg_mode_mask(vcpu);		\
+}											\
+static __always_inline void kvm_##lname##_write(struct kvm_vcpu *vcpu,			\
+						unsigned long val)			\
+{											\
+	vcpu->arch.regs[VCPU_REGS_##uname] = val & kvm_reg_mode_mask(vcpu);		\
+}											\
+static __always_inline unsigned long kvm_##lname##_read_raw(struct kvm_vcpu *vcpu)	\
+{											\
+	return vcpu->arch.regs[VCPU_REGS_##uname];					\
+}											\
+static __always_inline void kvm_##lname##_write_raw(struct kvm_vcpu *vcpu,		\
+						    unsigned long val)			\
+{											\
+	vcpu->arch.regs[VCPU_REGS_##uname] = val;					\
 }
-BUILD_KVM_GPR_ACCESSORS(rax, RAX)
-BUILD_KVM_GPR_ACCESSORS(rbx, RBX)
-BUILD_KVM_GPR_ACCESSORS(rcx, RCX)
-BUILD_KVM_GPR_ACCESSORS(rdx, RDX)
-BUILD_KVM_GPR_ACCESSORS(rbp, RBP)
-BUILD_KVM_GPR_ACCESSORS(rsi, RSI)
-BUILD_KVM_GPR_ACCESSORS(rdi, RDI)
+#define BUILD_KVM_GPR_ACCESSORS(lname, uname)						\
+static __always_inline u32 kvm_e##lname##_read(struct kvm_vcpu *vcpu)			\
+{											\
+	return vcpu->arch.regs[VCPU_REGS_##uname];					\
+}											\
+static __always_inline void kvm_e##lname##_write(struct kvm_vcpu *vcpu, u32 val)	\
+{											\
+	vcpu->arch.regs[VCPU_REGS_##uname] = val;					\
+}											\
+__BUILD_KVM_GPR_ACCESSORS(r##lname, uname)
+
+BUILD_KVM_GPR_ACCESSORS(ax, RAX)
+BUILD_KVM_GPR_ACCESSORS(bx, RBX)
+BUILD_KVM_GPR_ACCESSORS(cx, RCX)
+BUILD_KVM_GPR_ACCESSORS(dx, RDX)
+BUILD_KVM_GPR_ACCESSORS(bp, RBP)
+BUILD_KVM_GPR_ACCESSORS(si, RSI)
+BUILD_KVM_GPR_ACCESSORS(di, RDI)
 #ifdef CONFIG_X86_64
-BUILD_KVM_GPR_ACCESSORS(r8,  R8)
-BUILD_KVM_GPR_ACCESSORS(r9,  R9)
-BUILD_KVM_GPR_ACCESSORS(r10, R10)
-BUILD_KVM_GPR_ACCESSORS(r11, R11)
-BUILD_KVM_GPR_ACCESSORS(r12, R12)
-BUILD_KVM_GPR_ACCESSORS(r13, R13)
-BUILD_KVM_GPR_ACCESSORS(r14, R14)
-BUILD_KVM_GPR_ACCESSORS(r15, R15)
+__BUILD_KVM_GPR_ACCESSORS(r8,  R8)
+__BUILD_KVM_GPR_ACCESSORS(r9,  R9)
+__BUILD_KVM_GPR_ACCESSORS(r10, R10)
+__BUILD_KVM_GPR_ACCESSORS(r11, R11)
+__BUILD_KVM_GPR_ACCESSORS(r12, R12)
+__BUILD_KVM_GPR_ACCESSORS(r13, R13)
+__BUILD_KVM_GPR_ACCESSORS(r14, R14)
+__BUILD_KVM_GPR_ACCESSORS(r15, R15)
 #endif
 
 /*
@@ -210,8 +239,7 @@ static inline void kvm_rsp_write(struct kvm_vcpu *vcpu, unsigned long val)
 
 static inline u64 kvm_read_edx_eax(struct kvm_vcpu *vcpu)
 {
-	return (kvm_rax_read(vcpu) & -1u)
-		| ((u64)(kvm_rdx_read(vcpu) & -1u) << 32);
+	return kvm_eax_read(vcpu) | (u64)(kvm_edx_read(vcpu)) << 32;
 }
 
 static inline u64 kvm_pdptr_read(struct kvm_vcpu *vcpu, int index)
diff --git a/arch/x86/kvm/svm/nested.c b/arch/x86/kvm/svm/nested.c
index 4ef9bc6a553f..7b2d804ef2b0 100644
--- a/arch/x86/kvm/svm/nested.c
+++ b/arch/x86/kvm/svm/nested.c
@@ -778,7 +778,7 @@ static void nested_vmcb02_prepare_save(struct vcpu_svm *svm)
 
 	svm->vcpu.arch.cr2 = save->cr2;
 
-	kvm_rax_write(vcpu, save->rax);
+	kvm_rax_write_raw(vcpu, save->rax);
 	kvm_rsp_write(vcpu, save->rsp);
 	kvm_rip_write(vcpu, save->rip);
 
@@ -1244,7 +1244,7 @@ static int nested_svm_vmexit_update_vmcb12(struct kvm_vcpu *vcpu)
 	vmcb12->save.rflags = kvm_get_rflags(vcpu);
 	vmcb12->save.rip    = kvm_rip_read(vcpu);
 	vmcb12->save.rsp    = kvm_rsp_read(vcpu);
-	vmcb12->save.rax    = kvm_rax_read(vcpu);
+	vmcb12->save.rax    = kvm_rax_read_raw(vcpu);
 	vmcb12->save.dr7    = vmcb02->save.dr7;
 	vmcb12->save.dr6    = svm->vcpu.arch.dr6;
 	vmcb12->save.cpl    = vmcb02->save.cpl;
@@ -1394,7 +1394,7 @@ void nested_svm_vmexit(struct vcpu_svm *svm)
 	svm_set_efer(vcpu, vmcb01->save.efer);
 	svm_set_cr0(vcpu, vmcb01->save.cr0 | X86_CR0_PE);
 	svm_set_cr4(vcpu, vmcb01->save.cr4);
-	kvm_rax_write(vcpu, vmcb01->save.rax);
+	kvm_rax_write_raw(vcpu, vmcb01->save.rax);
 	kvm_rsp_write(vcpu, vmcb01->save.rsp);
 	kvm_rip_write(vcpu, vmcb01->save.rip);
 
diff --git a/arch/x86/kvm/svm/svm.c b/arch/x86/kvm/svm/svm.c
index be775d285ce7..02fb9560c26e 100644
--- a/arch/x86/kvm/svm/svm.c
+++ b/arch/x86/kvm/svm/svm.c
@@ -2408,15 +2408,12 @@ static int clgi_interception(struct kvm_vcpu *vcpu)
 
 static int invlpga_interception(struct kvm_vcpu *vcpu)
 {
-	gva_t gva = kvm_rax_read(vcpu);
-	u32 asid = kvm_rcx_read(vcpu);
-
-	if (nested_svm_check_permissions(vcpu))
-		return 1;
-
 	/* FIXME: Handle an address size prefix. */
-	if (!is_64_bit_mode(vcpu))
-		gva = (u32)gva;
+	gva_t gva = kvm_rax_read(vcpu);
+	u32 asid = kvm_ecx_read(vcpu);
+
+	if (nested_svm_check_permissions(vcpu))
+		return 1;
 
 	trace_kvm_invlpga(to_svm(vcpu)->vmcb->save.rip, asid, gva);
 
diff --git a/arch/x86/kvm/vmx/nested.c b/arch/x86/kvm/vmx/nested.c
index 4690a4d23709..20d75bf0a455 100644
--- a/arch/x86/kvm/vmx/nested.c
+++ b/arch/x86/kvm/vmx/nested.c
@@ -6148,7 +6148,7 @@ static int handle_invvpid(struct kvm_vcpu *vcpu)
 static int nested_vmx_eptp_switching(struct kvm_vcpu *vcpu,
 				     struct vmcs12 *vmcs12)
 {
-	u32 index = kvm_rcx_read(vcpu);
+	u32 index = kvm_ecx_read(vcpu);
 	u64 new_eptp;
 
 	if (WARN_ON_ONCE(!nested_cpu_has_ept(vmcs12)))
@@ -6182,7 +6182,7 @@ static int handle_vmfunc(struct kvm_vcpu *vcpu)
 {
 	struct vcpu_vmx *vmx = to_vmx(vcpu);
 	struct vmcs12 *vmcs12;
-	u32 function = kvm_rax_read(vcpu);
+	u32 function = kvm_eax_read(vcpu);
 
 	/*
 	 * VMFUNC should never execute cleanly while L1 is active; KVM supports
@@ -6304,7 +6304,7 @@ static bool nested_vmx_exit_handled_msr(struct kvm_vcpu *vcpu,
 	    exit_reason.basic == EXIT_REASON_MSR_WRITE_IMM)
 		msr_index = vmx_get_exit_qual(vcpu);
 	else
-		msr_index = kvm_rcx_read(vcpu);
+		msr_index = kvm_ecx_read(vcpu);
 
 	/*
 	 * The MSR_BITMAP page is divided into four 1024-byte bitmaps,
@@ -6414,7 +6414,7 @@ static bool nested_vmx_exit_handled_encls(struct kvm_vcpu *vcpu,
 	    !nested_cpu_has2(vmcs12, SECONDARY_EXEC_ENCLS_EXITING))
 		return false;
 
-	encls_leaf = kvm_rax_read(vcpu);
+	encls_leaf = kvm_eax_read(vcpu);
 	if (encls_leaf > 62)
 		encls_leaf = 63;
 	return vmcs12->encls_exiting_bitmap & BIT_ULL(encls_leaf);
diff --git a/arch/x86/kvm/vmx/sgx.c b/arch/x86/kvm/vmx/sgx.c
index 66c315554b46..2f5a1c58f3c5 100644
--- a/arch/x86/kvm/vmx/sgx.c
+++ b/arch/x86/kvm/vmx/sgx.c
@@ -352,7 +352,7 @@ static int handle_encls_einit(struct kvm_vcpu *vcpu)
 		rflags &= ~X86_EFLAGS_ZF;
 	vmx_set_rflags(vcpu, rflags);
 
-	kvm_rax_write(vcpu, ret);
+	kvm_eax_write(vcpu, ret);
 	return kvm_skip_emulated_instruction(vcpu);
 }
 
@@ -380,7 +380,7 @@ static inline bool sgx_enabled_in_guest_bios(struct kvm_vcpu *vcpu)
 
 int handle_encls(struct kvm_vcpu *vcpu)
 {
-	u32 leaf = (u32)kvm_rax_read(vcpu);
+	u32 leaf = kvm_eax_read(vcpu);
 
 	if (!enable_sgx || !guest_cpu_cap_has(vcpu, X86_FEATURE_SGX) ||
 	    !guest_cpu_cap_has(vcpu, X86_FEATURE_SGX1)) {
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index f97bcf580e6d..ec88b58e2b27 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1163,11 +1163,11 @@ static int complete_hypercall_exit(struct kvm_vcpu *vcpu)
 
 static int tdx_emulate_vmcall(struct kvm_vcpu *vcpu)
 {
-	kvm_rax_write(vcpu, to_tdx(vcpu)->vp_enter_args.r10);
-	kvm_rbx_write(vcpu, to_tdx(vcpu)->vp_enter_args.r11);
-	kvm_rcx_write(vcpu, to_tdx(vcpu)->vp_enter_args.r12);
-	kvm_rdx_write(vcpu, to_tdx(vcpu)->vp_enter_args.r13);
-	kvm_rsi_write(vcpu, to_tdx(vcpu)->vp_enter_args.r14);
+	kvm_rax_write_raw(vcpu, to_tdx(vcpu)->vp_enter_args.r10);
+	kvm_rbx_write_raw(vcpu, to_tdx(vcpu)->vp_enter_args.r11);
+	kvm_rcx_write_raw(vcpu, to_tdx(vcpu)->vp_enter_args.r12);
+	kvm_rdx_write_raw(vcpu, to_tdx(vcpu)->vp_enter_args.r13);
+	kvm_rsi_write_raw(vcpu, to_tdx(vcpu)->vp_enter_args.r14);
 
 	return __kvm_emulate_hypercall(vcpu, 0, complete_hypercall_exit);
 }
@@ -2028,12 +2028,12 @@ int tdx_handle_exit(struct kvm_vcpu *vcpu, fastpath_t fastpath)
 	case EXIT_REASON_IO_INSTRUCTION:
 		return tdx_emulate_io(vcpu);
 	case EXIT_REASON_MSR_READ:
-		kvm_rcx_write(vcpu, tdx->vp_enter_args.r12);
+		kvm_ecx_write(vcpu, tdx->vp_enter_args.r12);
 		return kvm_emulate_rdmsr(vcpu);
 	case EXIT_REASON_MSR_WRITE:
-		kvm_rcx_write(vcpu, tdx->vp_enter_args.r12);
-		kvm_rax_write(vcpu, tdx->vp_enter_args.r13 & -1u);
-		kvm_rdx_write(vcpu, tdx->vp_enter_args.r13 >> 32);
+		kvm_ecx_write(vcpu, tdx->vp_enter_args.r12);
+		kvm_eax_write(vcpu, tdx->vp_enter_args.r13);
+		kvm_edx_write(vcpu, tdx->vp_enter_args.r13 >> 32);
 		return kvm_emulate_wrmsr(vcpu);
 	case EXIT_REASON_EPT_MISCONFIG:
 		return tdx_emulate_mmio(vcpu);
diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index ab13aed2cbd0..b958521bc81f 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -1319,7 +1319,7 @@ int kvm_emulate_xsetbv(struct kvm_vcpu *vcpu)
 {
 	/* Note, #UD due to CR4.OSXSAVE=0 has priority over the intercept. */
 	if (kvm_x86_call(get_cpl)(vcpu) != 0 ||
-	    __kvm_set_xcr(vcpu, kvm_rcx_read(vcpu), kvm_read_edx_eax(vcpu))) {
+	    __kvm_set_xcr(vcpu, kvm_ecx_read(vcpu), kvm_read_edx_eax(vcpu))) {
 		kvm_inject_gp(vcpu, 0);
 		return 1;
 	}
@@ -1608,7 +1608,7 @@ EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_get_dr);
 
 int kvm_emulate_rdpmc(struct kvm_vcpu *vcpu)
 {
-	u32 pmc = kvm_rcx_read(vcpu);
+	u32 pmc = kvm_ecx_read(vcpu);
 	u64 data;
 
 	if (kvm_pmu_rdpmc(vcpu, pmc, &data)) {
@@ -1616,8 +1616,8 @@ int kvm_emulate_rdpmc(struct kvm_vcpu *vcpu)
 		return 1;
 	}
 
-	kvm_rax_write(vcpu, (u32)data);
-	kvm_rdx_write(vcpu, data >> 32);
+	kvm_eax_write(vcpu, data);
+	kvm_edx_write(vcpu, data >> 32);
 	return kvm_skip_emulated_instruction(vcpu);
 }
 EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_emulate_rdpmc);
@@ -2064,8 +2064,8 @@ EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_emulate_msr_write);
 static void complete_userspace_rdmsr(struct kvm_vcpu *vcpu)
 {
 	if (!vcpu->run->msr.error) {
-		kvm_rax_write(vcpu, (u32)vcpu->run->msr.data);
-		kvm_rdx_write(vcpu, vcpu->run->msr.data >> 32);
+		kvm_eax_write(vcpu, vcpu->run->msr.data);
+		kvm_edx_write(vcpu, vcpu->run->msr.data >> 32);
 	}
 }
 
@@ -2146,8 +2146,8 @@ static int __kvm_emulate_rdmsr(struct kvm_vcpu *vcpu, u32 msr, int reg,
 		trace_kvm_msr_read(msr, data);
 
 		if (reg < 0) {
-			kvm_rax_write(vcpu, data & -1u);
-			kvm_rdx_write(vcpu, (data >> 32) & -1u);
+			kvm_eax_write(vcpu, data);
+			kvm_edx_write(vcpu, data >> 32);
 		} else {
 			kvm_register_write(vcpu, reg, data);
 		}
@@ -2164,7 +2164,7 @@ static int __kvm_emulate_rdmsr(struct kvm_vcpu *vcpu, u32 msr, int reg,
 
 int kvm_emulate_rdmsr(struct kvm_vcpu *vcpu)
 {
-	return __kvm_emulate_rdmsr(vcpu, kvm_rcx_read(vcpu), -1,
+	return __kvm_emulate_rdmsr(vcpu, kvm_ecx_read(vcpu), -1,
 				   complete_fast_rdmsr);
 }
 EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_emulate_rdmsr);
@@ -2200,7 +2200,7 @@ static int __kvm_emulate_wrmsr(struct kvm_vcpu *vcpu, u32 msr, u64 data)
 
 int kvm_emulate_wrmsr(struct kvm_vcpu *vcpu)
 {
-	return __kvm_emulate_wrmsr(vcpu, kvm_rcx_read(vcpu),
+	return __kvm_emulate_wrmsr(vcpu, kvm_ecx_read(vcpu),
 				   kvm_read_edx_eax(vcpu));
 }
 EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_emulate_wrmsr);
@@ -2310,7 +2310,7 @@ static fastpath_t __handle_fastpath_wrmsr(struct kvm_vcpu *vcpu, u32 msr, u64 da
 
 fastpath_t handle_fastpath_wrmsr(struct kvm_vcpu *vcpu)
 {
-	return __handle_fastpath_wrmsr(vcpu, kvm_rcx_read(vcpu),
+	return __handle_fastpath_wrmsr(vcpu, kvm_ecx_read(vcpu),
 				       kvm_read_edx_eax(vcpu));
 }
 EXPORT_SYMBOL_FOR_KVM_INTERNAL(handle_fastpath_wrmsr);
@@ -9691,7 +9691,7 @@ static int complete_fast_pio_out(struct kvm_vcpu *vcpu)
 static int kvm_fast_pio_out(struct kvm_vcpu *vcpu, int size,
 			    unsigned short port)
 {
-	unsigned long val = kvm_rax_read(vcpu);
+	unsigned long val = kvm_rax_read_raw(vcpu);
 	int ret = emulator_pio_out(vcpu, size, port, &val, 1);
 
 	if (ret)
@@ -9727,10 +9727,10 @@ static int complete_fast_pio_in(struct kvm_vcpu *vcpu)
 	}
 
 	/* For size less than 4 we merge, else we zero extend */
-	val = (vcpu->arch.pio.size < 4) ? kvm_rax_read(vcpu) : 0;
+	val = (vcpu->arch.pio.size < 4) ? kvm_rax_read_raw(vcpu) : 0;
 
 	complete_emulator_pio_in(vcpu, &val);
-	kvm_rax_write(vcpu, val);
+	kvm_rax_write_raw(vcpu, val);
 
 	return kvm_skip_emulated_instruction(vcpu);
 }
@@ -9742,11 +9742,11 @@ static int kvm_fast_pio_in(struct kvm_vcpu *vcpu, int size,
 	int ret;
 
 	/* For size less than 4 we merge, else we zero extend */
-	val = (size < 4) ? kvm_rax_read(vcpu) : 0;
+	val = (size < 4) ? kvm_rax_read_raw(vcpu) : 0;
 
 	ret = emulator_pio_in(vcpu, size, port, &val, 1);
 	if (ret) {
-		kvm_rax_write(vcpu, val);
+		kvm_rax_write_raw(vcpu, val);
 		return ret;
 	}
 
@@ -10413,29 +10413,30 @@ static int complete_hypercall_exit(struct kvm_vcpu *vcpu)
 
 	if (!is_64_bit_hypercall(vcpu))
 		ret = (u32)ret;
-	kvm_rax_write(vcpu, ret);
+	kvm_rax_write_raw(vcpu, ret);
 	return kvm_skip_emulated_instruction(vcpu);
 }
 
 int ____kvm_emulate_hypercall(struct kvm_vcpu *vcpu, int cpl,
 			      int (*complete_hypercall)(struct kvm_vcpu *))
 {
-	unsigned long ret;
-	unsigned long nr = kvm_rax_read(vcpu);
-	unsigned long a0 = kvm_rbx_read(vcpu);
-	unsigned long a1 = kvm_rcx_read(vcpu);
-	unsigned long a2 = kvm_rdx_read(vcpu);
-	unsigned long a3 = kvm_rsi_read(vcpu);
 	int op_64_bit = is_64_bit_hypercall(vcpu);
+	unsigned long ret, nr, a0, a1, a2, a3;
 
 	++vcpu->stat.hypercalls;
 
-	if (!op_64_bit) {
-		nr &= 0xFFFFFFFF;
-		a0 &= 0xFFFFFFFF;
-		a1 &= 0xFFFFFFFF;
-		a2 &= 0xFFFFFFFF;
-		a3 &= 0xFFFFFFFF;
+	if (op_64_bit) {
+		nr = kvm_rax_read_raw(vcpu);
+		a0 = kvm_rbx_read_raw(vcpu);
+		a1 = kvm_rcx_read_raw(vcpu);
+		a2 = kvm_rdx_read_raw(vcpu);
+		a3 = kvm_rsi_read_raw(vcpu);
+	} else {
+		nr = kvm_eax_read(vcpu);
+		a0 = kvm_ebx_read(vcpu);
+		a1 = kvm_ecx_read(vcpu);
+		a2 = kvm_edx_read(vcpu);
+		a3 = kvm_esi_read(vcpu);
 	}
 
 	trace_kvm_hypercall(nr, a0, a1, a2, a3);
@@ -12133,23 +12134,23 @@ static void __get_regs(struct kvm_vcpu *vcpu, struct kvm_regs *regs)
 		emulator_writeback_register_cache(vcpu->arch.emulate_ctxt);
 		vcpu->arch.emulate_regs_need_sync_to_vcpu = false;
 	}
-	regs->rax = kvm_rax_read(vcpu);
-	regs->rbx = kvm_rbx_read(vcpu);
-	regs->rcx = kvm_rcx_read(vcpu);
-	regs->rdx = kvm_rdx_read(vcpu);
-	regs->rsi = kvm_rsi_read(vcpu);
-	regs->rdi = kvm_rdi_read(vcpu);
+	regs->rax = kvm_rax_read_raw(vcpu);
+	regs->rbx = kvm_rbx_read_raw(vcpu);
+	regs->rcx = kvm_rcx_read_raw(vcpu);
+	regs->rdx = kvm_rdx_read_raw(vcpu);
+	regs->rsi = kvm_rsi_read_raw(vcpu);
+	regs->rdi = kvm_rdi_read_raw(vcpu);
 	regs->rsp = kvm_rsp_read(vcpu);
-	regs->rbp = kvm_rbp_read(vcpu);
+	regs->rbp = kvm_rbp_read_raw(vcpu);
 #ifdef CONFIG_X86_64
-	regs->r8 = kvm_r8_read(vcpu);
-	regs->r9 = kvm_r9_read(vcpu);
-	regs->r10 = kvm_r10_read(vcpu);
-	regs->r11 = kvm_r11_read(vcpu);
-	regs->r12 = kvm_r12_read(vcpu);
-	regs->r13 = kvm_r13_read(vcpu);
-	regs->r14 = kvm_r14_read(vcpu);
-	regs->r15 = kvm_r15_read(vcpu);
+	regs->r8 = kvm_r8_read_raw(vcpu);
+	regs->r9 = kvm_r9_read_raw(vcpu);
+	regs->r10 = kvm_r10_read_raw(vcpu);
+	regs->r11 = kvm_r11_read_raw(vcpu);
+	regs->r12 = kvm_r12_read_raw(vcpu);
+	regs->r13 = kvm_r13_read_raw(vcpu);
+	regs->r14 = kvm_r14_read_raw(vcpu);
+	regs->r15 = kvm_r15_read_raw(vcpu);
 #endif
 
 	regs->rip = kvm_rip_read(vcpu);
@@ -12173,23 +12174,23 @@ static void __set_regs(struct kvm_vcpu *vcpu, struct kvm_regs *regs)
 	vcpu->arch.emulate_regs_need_sync_from_vcpu = true;
 	vcpu->arch.emulate_regs_need_sync_to_vcpu = false;
 
-	kvm_rax_write(vcpu, regs->rax);
-	kvm_rbx_write(vcpu, regs->rbx);
-	kvm_rcx_write(vcpu, regs->rcx);
-	kvm_rdx_write(vcpu, regs->rdx);
-	kvm_rsi_write(vcpu, regs->rsi);
-	kvm_rdi_write(vcpu, regs->rdi);
+	kvm_rax_write_raw(vcpu, regs->rax);
+	kvm_rbx_write_raw(vcpu, regs->rbx);
+	kvm_rcx_write_raw(vcpu, regs->rcx);
+	kvm_rdx_write_raw(vcpu, regs->rdx);
+	kvm_rsi_write_raw(vcpu, regs->rsi);
+	kvm_rdi_write_raw(vcpu, regs->rdi);
 	kvm_rsp_write(vcpu, regs->rsp);
-	kvm_rbp_write(vcpu, regs->rbp);
+	kvm_rbp_write_raw(vcpu, regs->rbp);
 #ifdef CONFIG_X86_64
-	kvm_r8_write(vcpu, regs->r8);
-	kvm_r9_write(vcpu, regs->r9);
-	kvm_r10_write(vcpu, regs->r10);
-	kvm_r11_write(vcpu, regs->r11);
-	kvm_r12_write(vcpu, regs->r12);
-	kvm_r13_write(vcpu, regs->r13);
-	kvm_r14_write(vcpu, regs->r14);
-	kvm_r15_write(vcpu, regs->r15);
+	kvm_r8_write_raw(vcpu, regs->r8);
+	kvm_r9_write_raw(vcpu, regs->r9);
+	kvm_r10_write_raw(vcpu, regs->r10);
+	kvm_r11_write_raw(vcpu, regs->r11);
+	kvm_r12_write_raw(vcpu, regs->r12);
+	kvm_r13_write_raw(vcpu, regs->r13);
+	kvm_r14_write_raw(vcpu, regs->r14);
+	kvm_r15_write_raw(vcpu, regs->r15);
 #endif
 
 	kvm_rip_write(vcpu, regs->rip);
@@ -13092,7 +13093,7 @@ void kvm_vcpu_reset(struct kvm_vcpu *vcpu, bool init_event)
 	 * on RESET.  But, go through the motions in case that's ever remedied.
 	 */
 	cpuid_0x1 = kvm_find_cpuid_entry(vcpu, 1);
-	kvm_rdx_write(vcpu, cpuid_0x1 ? cpuid_0x1->eax : 0x600);
+	kvm_edx_write(vcpu, cpuid_0x1 ? cpuid_0x1->eax : 0x600);
 
 	kvm_x86_call(vcpu_reset)(vcpu, init_event);
 
diff --git a/arch/x86/kvm/x86.h b/arch/x86/kvm/x86.h
index 16d1c3c1a2d9..bd4423e82b02 100644
--- a/arch/x86/kvm/x86.h
+++ b/arch/x86/kvm/x86.h
@@ -367,17 +367,13 @@ static inline bool vcpu_match_mmio_gpa(struct kvm_vcpu *vcpu, gpa_t gpa)
 
 static inline unsigned long kvm_register_read(struct kvm_vcpu *vcpu, int reg)
 {
-	unsigned long val = kvm_register_read_raw(vcpu, reg);
-
-	return is_64_bit_mode(vcpu) ? val : (u32)val;
+	return kvm_register_read_raw(vcpu, reg) & kvm_reg_mode_mask(vcpu);
 }
 
 static inline void kvm_register_write(struct kvm_vcpu *vcpu,
 				       int reg, unsigned long val)
 {
-	if (!is_64_bit_mode(vcpu))
-		val = (u32)val;
-	return kvm_register_write_raw(vcpu, reg, val);
+	return kvm_register_write_raw(vcpu, reg, val & kvm_reg_mode_mask(vcpu));
 }
 
 static inline bool kvm_check_has_quirk(struct kvm *kvm, u64 quirk)
diff --git a/arch/x86/kvm/xen.c b/arch/x86/kvm/xen.c
index 895095dc684e..694b31c1fcc9 100644
--- a/arch/x86/kvm/xen.c
+++ b/arch/x86/kvm/xen.c
@@ -1408,7 +1408,7 @@ int kvm_xen_hvm_config(struct kvm *kvm, struct kvm_xen_hvm_config *xhc)
 
 static int kvm_xen_hypercall_set_result(struct kvm_vcpu *vcpu, u64 result)
 {
-	kvm_rax_write(vcpu, result);
+	kvm_rax_write_raw(vcpu, result);
 	return kvm_skip_emulated_instruction(vcpu);
 }
 
@@ -1679,29 +1679,29 @@ int kvm_xen_hypercall(struct kvm_vcpu *vcpu)
 	u8 cpl;
 
 	/* Hyper-V hypercalls get bit 31 set in EAX */
-	if ((kvm_rax_read(vcpu) & 0x80000000) &&
+	if ((kvm_rax_read_raw(vcpu) & 0x80000000) &&
 	    kvm_hv_hypercall_enabled(vcpu))
 		return kvm_hv_hypercall(vcpu);
 
 	longmode = is_64_bit_hypercall(vcpu);
 	if (!longmode) {
-		input = (u32)kvm_rax_read(vcpu);
-		params[0] = (u32)kvm_rbx_read(vcpu);
-		params[1] = (u32)kvm_rcx_read(vcpu);
-		params[2] = (u32)kvm_rdx_read(vcpu);
-		params[3] = (u32)kvm_rsi_read(vcpu);
-		params[4] = (u32)kvm_rdi_read(vcpu);
-		params[5] = (u32)kvm_rbp_read(vcpu);
+		input = kvm_eax_read(vcpu);
+		params[0] = kvm_ebx_read(vcpu);
+		params[1] = kvm_ecx_read(vcpu);
+		params[2] = kvm_edx_read(vcpu);
+		params[3] = kvm_esi_read(vcpu);
+		params[4] = kvm_edi_read(vcpu);
+		params[5] = kvm_ebp_read(vcpu);
 	}
 	else {
 #ifdef CONFIG_X86_64
-		input = (u64)kvm_rax_read(vcpu);
-		params[0] = (u64)kvm_rdi_read(vcpu);
-		params[1] = (u64)kvm_rsi_read(vcpu);
-		params[2] = (u64)kvm_rdx_read(vcpu);
-		params[3] = (u64)kvm_r10_read(vcpu);
-		params[4] = (u64)kvm_r8_read(vcpu);
-		params[5] = (u64)kvm_r9_read(vcpu);
+		input = (u64)kvm_rax_read_raw(vcpu);
+		params[0] = (u64)kvm_rdi_read_raw(vcpu);
+		params[1] = (u64)kvm_rsi_read_raw(vcpu);
+		params[2] = (u64)kvm_rdx_read_raw(vcpu);
+		params[3] = (u64)kvm_r10_read_raw(vcpu);
+		params[4] = (u64)kvm_r8_read_raw(vcpu);
+		params[5] = (u64)kvm_r9_read_raw(vcpu);
 #else
 		KVM_BUG_ON(1, vcpu->kvm);
 		return -EIO;

---

## [10] Sean Christopherson — 2026-05-14
*Subject: [PATCH v2 09/15] KVM: x86: Drop non-raw kvm_<reg>_write() helpers*

Drop the non-raw, mode-aware kvm_<reg>_write() helpers as there is no
usage in KVM, and in all likelihood there will never be usage in KVM as
use of hardcoded registers in instructions is uncommon, and *modifying*
hardcoded registers is practically unheard of.  While there are a few
instructions that modify registers in mode-aware ways, e.g. REP string
and some ENCLS varieties, the odds of KVM needing to emulate such
instructions (outside of the fully emulator) are vanishingly small.

Drop kvm_<reg>_write() to prevent incorrect usage; _if_ a new instruction
comes along that needs to modify a hardcoded register, this can be
reverted.

No functional change intended.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/regs.h | 5 -----
 1 file changed, 5 deletions(-)

diff --git a/arch/x86/kvm/regs.h b/arch/x86/kvm/regs.h
index b28e71caed25..52bed14f43e3 100644
--- a/arch/x86/kvm/regs.h
+++ b/arch/x86/kvm/regs.h
@@ -61,11 +61,6 @@ static __always_inline unsigned long kvm_##lname##_read(struct kvm_vcpu *vcpu)
 {											\
 	return vcpu->arch.regs[VCPU_REGS_##uname] & kvm_reg_mode_mask(vcpu);		\
 }											\
-static __always_inline void kvm_##lname##_write(struct kvm_vcpu *vcpu,			\
-						unsigned long val)			\
-{											\
-	vcpu->arch.regs[VCPU_REGS_##uname] = val & kvm_reg_mode_mask(vcpu);		\
-}											\
 static __always_inline unsigned long kvm_##lname##_read_raw(struct kvm_vcpu *vcpu)	\
 {											\
 	return vcpu->arch.regs[VCPU_REGS_##uname];					\

---

## [11] Sean Christopherson — 2026-05-14
*Subject: [PATCH v2 10/15] KVM: nSVM: Use kvm_rax_read() now that it's mode-aware*

Now that kvm_rax_read() truncates the output value to 32 bits if the
vCPU isn't in 64-bit mode, use it instead of the more verbose (and very
technically slower) kvm_register_read().

Note!  VMLOAD, VMSAVE, and VMRUN emulation are still technically buggy,
as they can use EAX (versus RAX) in 64-bit mode via an operand size
prefix.  Don't bother trying to handle that case, as it would require
decoding the code stream, which would open an entirely different can of
worms, and in practice no sane guest would shove garbage into RAX[63:32]
and then execute VMLOAD/VMSAVE/VMRUN with just EAX.

No functional change intended.

Cc: Yosry Ahmed <yosry@kernel.org>
Reviewed-by: Yosry Ahmed <yosry@kernel.org>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/svm/nested.c | 2 +-
 arch/x86/kvm/svm/svm.c    | 4 ++--
 2 files changed, 3 insertions(+), 3 deletions(-)

diff --git a/arch/x86/kvm/svm/nested.c b/arch/x86/kvm/svm/nested.c
index 7b2d804ef2b0..4b1259eecec5 100644
--- a/arch/x86/kvm/svm/nested.c
+++ b/arch/x86/kvm/svm/nested.c
@@ -1119,7 +1119,7 @@ int nested_svm_vmrun(struct kvm_vcpu *vcpu)
 	if (WARN_ON_ONCE(!svm->nested.initialized))
 		return -EINVAL;
 
-	vmcb12_gpa = kvm_register_read(vcpu, VCPU_REGS_RAX);
+	vmcb12_gpa = kvm_rax_read(vcpu);
 	if (!page_address_valid(vcpu, vmcb12_gpa)) {
 		kvm_inject_gp(vcpu, 0);
 		return 1;
diff --git a/arch/x86/kvm/svm/svm.c b/arch/x86/kvm/svm/svm.c
index 02fb9560c26e..6379c389d811 100644
--- a/arch/x86/kvm/svm/svm.c
+++ b/arch/x86/kvm/svm/svm.c
@@ -2217,7 +2217,7 @@ static int intr_interception(struct kvm_vcpu *vcpu)
 
 static int vmload_vmsave_interception(struct kvm_vcpu *vcpu, bool vmload)
 {
-	u64 vmcb12_gpa = kvm_register_read(vcpu, VCPU_REGS_RAX);
+	u64 vmcb12_gpa = kvm_rax_read(vcpu);
 	struct vcpu_svm *svm = to_svm(vcpu);
 	struct vmcb *vmcb12;
 	struct kvm_host_map map;
@@ -2325,7 +2325,7 @@ static int gp_interception(struct kvm_vcpu *vcpu)
 		if (nested_svm_check_permissions(vcpu))
 			return 1;
 
-		if (!page_address_valid(vcpu, kvm_register_read(vcpu, VCPU_REGS_RAX)))
+		if (!page_address_valid(vcpu, kvm_rax_read(vcpu)))
 			goto reinject;
 
 		/*

---

## [12] Sean Christopherson — 2026-05-14
*Subject: [PATCH v2 11/15] Revert "KVM: VMX: Read 32-bit GPR values for ENCLS
 instructions outside of 64-bit mode"*

Now that kvm_<reg>_read() are mode aware, i.e. are functionally equivalent
to kvm_register_read(), revert aback to the less verbose versions.

No functional change intended.

This reverts commit 60919eccf6764c71cef31a1afeaa1a36b8e5ab85.

Acked-by: Kai Huang <kai.huang@intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/vmx/sgx.c | 10 +++++-----
 1 file changed, 5 insertions(+), 5 deletions(-)

diff --git a/arch/x86/kvm/vmx/sgx.c b/arch/x86/kvm/vmx/sgx.c
index 2f5a1c58f3c5..876dc2814108 100644
--- a/arch/x86/kvm/vmx/sgx.c
+++ b/arch/x86/kvm/vmx/sgx.c
@@ -225,8 +225,8 @@ static int handle_encls_ecreate(struct kvm_vcpu *vcpu)
 	struct x86_exception ex;
 	int r;
 
-	if (sgx_get_encls_gva(vcpu, kvm_register_read(vcpu, VCPU_REGS_RBX), 32, 32, &pageinfo_gva) ||
-	    sgx_get_encls_gva(vcpu, kvm_register_read(vcpu, VCPU_REGS_RCX), 4096, 4096, &secs_gva))
+	if (sgx_get_encls_gva(vcpu, kvm_rbx_read(vcpu), 32, 32, &pageinfo_gva) ||
+	    sgx_get_encls_gva(vcpu, kvm_rcx_read(vcpu), 4096, 4096, &secs_gva))
 		return 1;
 
 	/*
@@ -302,9 +302,9 @@ static int handle_encls_einit(struct kvm_vcpu *vcpu)
 	gpa_t sig_gpa, secs_gpa, token_gpa;
 	int ret, trapnr;
 
-	if (sgx_get_encls_gva(vcpu, kvm_register_read(vcpu, VCPU_REGS_RBX), 1808, 4096, &sig_gva) ||
-	    sgx_get_encls_gva(vcpu, kvm_register_read(vcpu, VCPU_REGS_RCX), 4096, 4096, &secs_gva) ||
-	    sgx_get_encls_gva(vcpu, kvm_register_read(vcpu, VCPU_REGS_RDX), 304, 512, &token_gva))
+	if (sgx_get_encls_gva(vcpu, kvm_rbx_read(vcpu), 1808, 4096, &sig_gva) ||
+	    sgx_get_encls_gva(vcpu, kvm_rcx_read(vcpu), 4096, 4096, &secs_gva) ||
+	    sgx_get_encls_gva(vcpu, kvm_rdx_read(vcpu), 304, 512, &token_gva))
 		return 1;
 
 	/*

---

## [13] Sean Christopherson — 2026-05-14
*Subject: [PATCH v2 12/15] KVM: x86: Harden is_64_bit_hypercall() against bugs
 on 32-bit kernels*

Unconditionally return %false for is_64_bit_hypercall() on 32-bit kernels
to guard against incorrectly setting guest_state_protected, and because
in a (very) hypothetical world where 32-bit KVM supports protected guests,
assuming a hypercall was made in 64-bit mode is flat out wrong.

Reviewed-by: Kai Huang <kai.huang@intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/regs.h | 4 ++++
 1 file changed, 4 insertions(+)

diff --git a/arch/x86/kvm/regs.h b/arch/x86/kvm/regs.h
index 52bed14f43e3..d4d2a47a4968 100644
--- a/arch/x86/kvm/regs.h
+++ b/arch/x86/kvm/regs.h
@@ -39,12 +39,16 @@ static inline bool is_64_bit_mode(struct kvm_vcpu *vcpu)
 
 static inline bool is_64_bit_hypercall(struct kvm_vcpu *vcpu)
 {
+#ifdef CONFIG_X86_64
 	/*
 	 * If running with protected guest state, the CS register is not
 	 * accessible. The hypercall register values will have had to been
 	 * provided in 64-bit mode, so assume the guest is in 64-bit.
 	 */
 	return vcpu->arch.guest_state_protected || is_64_bit_mode(vcpu);
+#else
+	return false;
+#endif
 }
 
 static __always_inline unsigned long kvm_reg_mode_mask(struct kvm_vcpu *vcpu)

---

## [14] Sean Christopherson — 2026-05-14
*Subject: [PATCH v2 13/15] KVM: x86: Move update_cr8_intercept() to lapic.c*

Move update_cr8_intercept() to lapic.c so that it's globally visible
in anticipation of extracting most of the register-specific code out of
x86.c and into a new compilation unit.  Opportunistically prefix the
helper kvm_lapic_ to make its role/scope more obvious.

No functional change intended.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/lapic.c | 26 ++++++++++++++++++++++++++
 arch/x86/kvm/lapic.h |  1 +
 arch/x86/kvm/x86.c   | 34 +++-------------------------------
 3 files changed, 30 insertions(+), 31 deletions(-)

diff --git a/arch/x86/kvm/lapic.c b/arch/x86/kvm/lapic.c
index d8dbfb107bfb..27cca31308bd 100644
--- a/arch/x86/kvm/lapic.c
+++ b/arch/x86/kvm/lapic.c
@@ -2744,6 +2744,32 @@ u64 kvm_lapic_get_cr8(struct kvm_vcpu *vcpu)
 	return (tpr & 0xf0) >> 4;
 }
 
+void kvm_lapic_update_cr8_intercept(struct kvm_vcpu *vcpu)
+{
+	int max_irr, tpr;
+
+	if (!kvm_x86_ops.update_cr8_intercept)
+		return;
+
+	if (!lapic_in_kernel(vcpu))
+		return;
+
+	if (vcpu->arch.apic->apicv_active)
+		return;
+
+	if (!vcpu->arch.apic->vapic_addr)
+		max_irr = kvm_lapic_find_highest_irr(vcpu);
+	else
+		max_irr = -1;
+
+	if (max_irr != -1)
+		max_irr >>= 4;
+
+	tpr = kvm_lapic_get_cr8(vcpu);
+
+	kvm_x86_call(update_cr8_intercept)(vcpu, tpr, max_irr);
+}
+
 static void __kvm_apic_set_base(struct kvm_vcpu *vcpu, u64 value)
 {
 	u64 old_value = vcpu->arch.apic_base;
diff --git a/arch/x86/kvm/lapic.h b/arch/x86/kvm/lapic.h
index 274885af4ebc..533581d06151 100644
--- a/arch/x86/kvm/lapic.h
+++ b/arch/x86/kvm/lapic.h
@@ -100,6 +100,7 @@ int kvm_apic_accept_events(struct kvm_vcpu *vcpu);
 void kvm_lapic_reset(struct kvm_vcpu *vcpu, bool init_event);
 u64 kvm_lapic_get_cr8(struct kvm_vcpu *vcpu);
 void kvm_lapic_set_tpr(struct kvm_vcpu *vcpu, unsigned long cr8);
+void kvm_lapic_update_cr8_intercept(struct kvm_vcpu *vcpu);
 void kvm_lapic_set_eoi(struct kvm_vcpu *vcpu);
 void kvm_apic_set_version(struct kvm_vcpu *vcpu);
 void kvm_apic_after_set_mcg_cap(struct kvm_vcpu *vcpu);
diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index b958521bc81f..1113a31978dd 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -128,7 +128,6 @@ static u64 __read_mostly efer_reserved_bits = ~((u64)EFER_SCE);
 				    KVM_X2APIC_ENABLE_SUPPRESS_EOI_BROADCAST	| \
 				    KVM_X2APIC_DISABLE_SUPPRESS_EOI_BROADCAST)
 
-static void update_cr8_intercept(struct kvm_vcpu *vcpu);
 static void process_nmi(struct kvm_vcpu *vcpu);
 static void __kvm_set_rflags(struct kvm_vcpu *vcpu, unsigned long rflags);
 static void store_regs(struct kvm_vcpu *vcpu);
@@ -5342,7 +5341,7 @@ static int kvm_vcpu_ioctl_set_lapic(struct kvm_vcpu *vcpu,
 	r = kvm_apic_set_state(vcpu, s);
 	if (r)
 		return r;
-	update_cr8_intercept(vcpu);
+	kvm_lapic_update_cr8_intercept(vcpu);
 
 	return 0;
 }
@@ -10583,33 +10582,6 @@ static void post_kvm_run_save(struct kvm_vcpu *vcpu)
 		kvm_run->flags |= KVM_RUN_X86_GUEST_MODE;
 }
 
-static void update_cr8_intercept(struct kvm_vcpu *vcpu)
-{
-	int max_irr, tpr;
-
-	if (!kvm_x86_ops.update_cr8_intercept)
-		return;
-
-	if (!lapic_in_kernel(vcpu))
-		return;
-
-	if (vcpu->arch.apic->apicv_active)
-		return;
-
-	if (!vcpu->arch.apic->vapic_addr)
-		max_irr = kvm_lapic_find_highest_irr(vcpu);
-	else
-		max_irr = -1;
-
-	if (max_irr != -1)
-		max_irr >>= 4;
-
-	tpr = kvm_lapic_get_cr8(vcpu);
-
-	kvm_x86_call(update_cr8_intercept)(vcpu, tpr, max_irr);
-}
-
-
 int kvm_check_nested_events(struct kvm_vcpu *vcpu)
 {
 	if (kvm_test_request(KVM_REQ_TRIPLE_FAULT, vcpu)) {
@@ -11350,7 +11322,7 @@ static int vcpu_enter_guest(struct kvm_vcpu *vcpu)
 			kvm_x86_call(enable_irq_window)(vcpu);
 
 		if (kvm_lapic_enabled(vcpu)) {
-			update_cr8_intercept(vcpu);
+			kvm_lapic_update_cr8_intercept(vcpu);
 			kvm_lapic_sync_to_vapic(vcpu);
 		}
 	}
@@ -12496,7 +12468,7 @@ static int __set_sregs_common(struct kvm_vcpu *vcpu, struct kvm_sregs *sregs,
 	kvm_set_segment(vcpu, &sregs->tr, VCPU_SREG_TR);
 	kvm_set_segment(vcpu, &sregs->ldt, VCPU_SREG_LDTR);
 
-	update_cr8_intercept(vcpu);
+	kvm_lapic_update_cr8_intercept(vcpu);
 
 	/* Older userspace won't unhalt the vcpu on reset. */
 	if (kvm_vcpu_is_bsp(vcpu) && kvm_rip_read(vcpu) == 0xfff0 &&

---

## [15] Sean Christopherson — 2026-05-14
*Subject: [PATCH v2 14/15] KVM: x86: Move kvm_pv_async_pf_enabled() to x86.h
 (as an inline)*

Move kvm_pv_async_pf_enabled() in anticipation of extracting the majority
of register specific code out of x86.c.

No functional change intended.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/x86.c | 12 ------------
 arch/x86/kvm/x86.h | 12 ++++++++++++
 2 files changed, 12 insertions(+), 12 deletions(-)

diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index 1113a31978dd..e664e874973b 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -1042,18 +1042,6 @@ bool kvm_require_dr(struct kvm_vcpu *vcpu, int dr)
 }
 EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_require_dr);
 
-static bool __kvm_pv_async_pf_enabled(u64 data)
-{
-	u64 mask = KVM_ASYNC_PF_ENABLED | KVM_ASYNC_PF_DELIVERY_AS_INT;
-
-	return (data & mask) == mask;
-}
-
-static bool kvm_pv_async_pf_enabled(struct kvm_vcpu *vcpu)
-{
-	return __kvm_pv_async_pf_enabled(vcpu->arch.apf.msr_en_val);
-}
-
 static inline u64 pdptr_rsvd_bits(struct kvm_vcpu *vcpu)
 {
 	return vcpu->arch.reserved_gpa_bits | rsvd_bits(5, 8) | rsvd_bits(1, 2);
diff --git a/arch/x86/kvm/x86.h b/arch/x86/kvm/x86.h
index bd4423e82b02..185062a26924 100644
--- a/arch/x86/kvm/x86.h
+++ b/arch/x86/kvm/x86.h
@@ -570,6 +570,18 @@ static inline bool kvm_pat_valid(u64 data)
 	return (data | ((data & 0x0202020202020202ull) << 1)) == data;
 }
 
+static inline bool __kvm_pv_async_pf_enabled(u64 data)
+{
+	u64 mask = KVM_ASYNC_PF_ENABLED | KVM_ASYNC_PF_DELIVERY_AS_INT;
+
+	return (data & mask) == mask;
+}
+
+static inline bool kvm_pv_async_pf_enabled(struct kvm_vcpu *vcpu)
+{
+	return __kvm_pv_async_pf_enabled(vcpu->arch.apf.msr_en_val);
+}
+
 /*
  * Trigger machine check on the host. We assume all the MSRs are already set up
  * by the CPU and that we still run on the same CPU as the MCE occurred on.

---

## [16] Sean Christopherson — 2026-05-14
*Subject: [PATCH v2 15/15] KVM: x86: Move the bulk of register specific code
 from x86.c to regs.c*

Introduce regs.c, and move the vast majority of register specific code out
of x86.c and into regs.c.  Deliberately leave behind MSR code (except for
EFER, which can hardly be called an MSR), as KVM's MSR support is complex
enough to warrant its own compilation unit, and doesn't have much in common
with the other register code.

No functional change intended.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/kvm_host.h |   2 -
 arch/x86/kvm/Makefile           |   4 +-
 arch/x86/kvm/regs.c             | 829 ++++++++++++++++++++++++++++++++
 arch/x86/kvm/regs.h             |  16 +
 arch/x86/kvm/x86.c              | 824 +------------------------------
 arch/x86/kvm/x86.h              |   2 +
 6 files changed, 856 insertions(+), 821 deletions(-)
 create mode 100644 arch/x86/kvm/regs.c

diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h
index 271bdd109a98..5e24987b2a94 100644
--- a/arch/x86/include/asm/kvm_host.h
+++ b/arch/x86/include/asm/kvm_host.h
@@ -2326,8 +2326,6 @@ static inline int __kvm_irq_line_state(unsigned long *irq_state,
 void kvm_inject_nmi(struct kvm_vcpu *vcpu);
 int kvm_get_nr_pending_nmis(struct kvm_vcpu *vcpu);
 
-void kvm_update_dr7(struct kvm_vcpu *vcpu);
-
 bool __kvm_mmu_unprotect_gfn_and_retry(struct kvm_vcpu *vcpu, gpa_t cr2_or_gpa,
 				       bool always_retry);
 
diff --git a/arch/x86/kvm/Makefile b/arch/x86/kvm/Makefile
index 77337c37324b..f39c311fd756 100644
--- a/arch/x86/kvm/Makefile
+++ b/arch/x86/kvm/Makefile
@@ -5,8 +5,8 @@ ccflags-$(CONFIG_KVM_WERROR) += -Werror
 
 include $(srctree)/virt/kvm/Makefile.kvm
 
-kvm-y			+= x86.o emulate.o irq.o lapic.o cpuid.o pmu.o mtrr.o \
-			   debugfs.o mmu/mmu.o mmu/page_track.o mmu/spte.o
+kvm-y			+= x86.o emulate.o irq.o lapic.o cpuid.o pmu.o regs.o \
+			   mtrr.o debugfs.o mmu/mmu.o mmu/page_track.o mmu/spte.o
 
 kvm-$(CONFIG_X86_64) += mmu/tdp_iter.o mmu/tdp_mmu.o
 kvm-$(CONFIG_KVM_IOAPIC) += i8259.o i8254.o ioapic.o
diff --git a/arch/x86/kvm/regs.c b/arch/x86/kvm/regs.c
new file mode 100644
index 000000000000..ee8a97c31d78
--- /dev/null
+++ b/arch/x86/kvm/regs.c
@@ -0,0 +1,829 @@
+// SPDX-License-Identifier: GPL-2.0-only
+#include <linux/kvm_host.h>
+
+#include "lapic.h"
+#include "mmu.h"
+#include "regs.h"
+
+static void __get_regs(struct kvm_vcpu *vcpu, struct kvm_regs *regs)
+{
+	if (vcpu->arch.emulate_regs_need_sync_to_vcpu) {
+		/*
+		 * We are here if userspace calls get_regs() in the middle of
+		 * instruction emulation. Registers state needs to be copied
+		 * back from emulation context to vcpu. Userspace shouldn't do
+		 * that usually, but some bad designed PV devices (vmware
+		 * backdoor interface) need this to work
+		 */
+		emulator_writeback_register_cache(vcpu->arch.emulate_ctxt);
+		vcpu->arch.emulate_regs_need_sync_to_vcpu = false;
+	}
+	regs->rax = kvm_rax_read_raw(vcpu);
+	regs->rbx = kvm_rbx_read_raw(vcpu);
+	regs->rcx = kvm_rcx_read_raw(vcpu);
+	regs->rdx = kvm_rdx_read_raw(vcpu);
+	regs->rsi = kvm_rsi_read_raw(vcpu);
+	regs->rdi = kvm_rdi_read_raw(vcpu);
+	regs->rsp = kvm_rsp_read(vcpu);
+	regs->rbp = kvm_rbp_read_raw(vcpu);
+#ifdef CONFIG_X86_64
+	regs->r8 = kvm_r8_read_raw(vcpu);
+	regs->r9 = kvm_r9_read_raw(vcpu);
+	regs->r10 = kvm_r10_read_raw(vcpu);
+	regs->r11 = kvm_r11_read_raw(vcpu);
+	regs->r12 = kvm_r12_read_raw(vcpu);
+	regs->r13 = kvm_r13_read_raw(vcpu);
+	regs->r14 = kvm_r14_read_raw(vcpu);
+	regs->r15 = kvm_r15_read_raw(vcpu);
+#endif
+
+	regs->rip = kvm_rip_read(vcpu);
+	regs->rflags = kvm_get_rflags(vcpu);
+}
+
+int kvm_arch_vcpu_ioctl_get_regs(struct kvm_vcpu *vcpu, struct kvm_regs *regs)
+{
+	if (vcpu->kvm->arch.has_protected_state &&
+	    vcpu->arch.guest_state_protected)
+		return -EINVAL;
+
+	vcpu_load(vcpu);
+	__get_regs(vcpu, regs);
+	vcpu_put(vcpu);
+	return 0;
+}
+
+static void __set_regs(struct kvm_vcpu *vcpu, struct kvm_regs *regs)
+{
+	vcpu->arch.emulate_regs_need_sync_from_vcpu = true;
+	vcpu->arch.emulate_regs_need_sync_to_vcpu = false;
+
+	kvm_rax_write_raw(vcpu, regs->rax);
+	kvm_rbx_write_raw(vcpu, regs->rbx);
+	kvm_rcx_write_raw(vcpu, regs->rcx);
+	kvm_rdx_write_raw(vcpu, regs->rdx);
+	kvm_rsi_write_raw(vcpu, regs->rsi);
+	kvm_rdi_write_raw(vcpu, regs->rdi);
+	kvm_rsp_write(vcpu, regs->rsp);
+	kvm_rbp_write_raw(vcpu, regs->rbp);
+#ifdef CONFIG_X86_64
+	kvm_r8_write_raw(vcpu, regs->r8);
+	kvm_r9_write_raw(vcpu, regs->r9);
+	kvm_r10_write_raw(vcpu, regs->r10);
+	kvm_r11_write_raw(vcpu, regs->r11);
+	kvm_r12_write_raw(vcpu, regs->r12);
+	kvm_r13_write_raw(vcpu, regs->r13);
+	kvm_r14_write_raw(vcpu, regs->r14);
+	kvm_r15_write_raw(vcpu, regs->r15);
+#endif
+
+	kvm_rip_write(vcpu, regs->rip);
+	kvm_set_rflags(vcpu, regs->rflags | X86_EFLAGS_FIXED);
+
+	vcpu->arch.exception.pending = false;
+	vcpu->arch.exception_vmexit.pending = false;
+
+	kvm_make_request(KVM_REQ_EVENT, vcpu);
+}
+
+int kvm_arch_vcpu_ioctl_set_regs(struct kvm_vcpu *vcpu, struct kvm_regs *regs)
+{
+	if (vcpu->kvm->arch.has_protected_state &&
+	    vcpu->arch.guest_state_protected)
+		return -EINVAL;
+
+	vcpu_load(vcpu);
+	__set_regs(vcpu, regs);
+	vcpu_put(vcpu);
+	return 0;
+}
+
+static inline u64 pdptr_rsvd_bits(struct kvm_vcpu *vcpu)
+{
+	return vcpu->arch.reserved_gpa_bits | rsvd_bits(5, 8) | rsvd_bits(1, 2);
+}
+
+/*
+ * Load the pae pdptrs.  Return 1 if they are all valid, 0 otherwise.
+ */
+int load_pdptrs(struct kvm_vcpu *vcpu, unsigned long cr3)
+{
+	struct kvm_mmu *mmu = vcpu->arch.walk_mmu;
+	gfn_t pdpt_gfn = cr3 >> PAGE_SHIFT;
+	gpa_t real_gpa;
+	int i;
+	int ret;
+	u64 pdpte[ARRAY_SIZE(mmu->pdptrs)];
+
+	/*
+	 * If the MMU is nested, CR3 holds an L2 GPA and needs to be translated
+	 * to an L1 GPA.
+	 */
+	real_gpa = kvm_translate_gpa(vcpu, mmu, gfn_to_gpa(pdpt_gfn),
+				     PFERR_USER_MASK | PFERR_WRITE_MASK |
+				     PFERR_GUEST_PAGE_MASK, NULL, 0);
+	if (real_gpa == INVALID_GPA)
+		return 0;
+
+	/* Note the offset, PDPTRs are 32 byte aligned when using PAE paging. */
+	ret = kvm_vcpu_read_guest_page(vcpu, gpa_to_gfn(real_gpa), pdpte,
+				       cr3 & GENMASK(11, 5), sizeof(pdpte));
+	if (ret < 0)
+		return 0;
+
+	for (i = 0; i < ARRAY_SIZE(pdpte); ++i) {
+		if ((pdpte[i] & PT_PRESENT_MASK) &&
+		    (pdpte[i] & pdptr_rsvd_bits(vcpu))) {
+			return 0;
+		}
+	}
+
+	/*
+	 * Marking VCPU_REG_PDPTR dirty doesn't work for !tdp_enabled.
+	 * Shadow page roots need to be reconstructed instead.
+	 */
+	if (!tdp_enabled && memcmp(mmu->pdptrs, pdpte, sizeof(mmu->pdptrs)))
+		kvm_mmu_free_roots(vcpu->kvm, mmu, KVM_MMU_ROOT_CURRENT);
+
+	memcpy(mmu->pdptrs, pdpte, sizeof(mmu->pdptrs));
+	kvm_register_mark_dirty(vcpu, VCPU_REG_PDPTR);
+	kvm_make_request(KVM_REQ_LOAD_MMU_PGD, vcpu);
+	vcpu->arch.pdptrs_from_userspace = false;
+
+	return 1;
+}
+EXPORT_SYMBOL_FOR_KVM_INTERNAL(load_pdptrs);
+
+static bool kvm_is_valid_cr0(struct kvm_vcpu *vcpu, unsigned long cr0)
+{
+#ifdef CONFIG_X86_64
+	if (cr0 & 0xffffffff00000000UL)
+		return false;
+#endif
+
+	if ((cr0 & X86_CR0_NW) && !(cr0 & X86_CR0_CD))
+		return false;
+
+	if ((cr0 & X86_CR0_PG) && !(cr0 & X86_CR0_PE))
+		return false;
+
+	return kvm_x86_call(is_valid_cr0)(vcpu, cr0);
+}
+
+void kvm_post_set_cr0(struct kvm_vcpu *vcpu, unsigned long old_cr0, unsigned long cr0)
+{
+	/*
+	 * CR0.WP is incorporated into the MMU role, but only for non-nested,
+	 * indirect shadow MMUs.  If paging is disabled, no updates are needed
+	 * as there are no permission bits to emulate.  If TDP is enabled, the
+	 * MMU's metadata needs to be updated, e.g. so that emulating guest
+	 * translations does the right thing, but there's no need to unload the
+	 * root as CR0.WP doesn't affect SPTEs.
+	 */
+	if ((cr0 ^ old_cr0) == X86_CR0_WP) {
+		if (!(cr0 & X86_CR0_PG))
+			return;
+
+		if (tdp_enabled) {
+			kvm_init_mmu(vcpu);
+			return;
+		}
+	}
+
+	if ((cr0 ^ old_cr0) & X86_CR0_PG) {
+		/*
+		 * Clearing CR0.PG is defined to flush the TLB from the guest's
+		 * perspective.
+		 */
+		if (!(cr0 & X86_CR0_PG))
+			kvm_make_request(KVM_REQ_TLB_FLUSH_GUEST, vcpu);
+		/*
+		 * Check for async #PF completion events when enabling paging,
+		 * as the vCPU may have previously encountered async #PFs (it's
+		 * entirely legal for the guest to toggle paging on/off without
+		 * waiting for the async #PF queue to drain).
+		 */
+		else if (kvm_pv_async_pf_enabled(vcpu))
+			kvm_make_request(KVM_REQ_APF_READY, vcpu);
+	}
+
+	if ((cr0 ^ old_cr0) & KVM_MMU_CR0_ROLE_BITS)
+		kvm_mmu_reset_context(vcpu);
+}
+EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_post_set_cr0);
+
+int kvm_set_cr0(struct kvm_vcpu *vcpu, unsigned long cr0)
+{
+	unsigned long old_cr0 = kvm_read_cr0(vcpu);
+
+	if (!kvm_is_valid_cr0(vcpu, cr0))
+		return 1;
+
+	cr0 |= X86_CR0_ET;
+
+	/* Write to CR0 reserved bits are ignored, even on Intel. */
+	cr0 &= ~CR0_RESERVED_BITS;
+
+#ifdef CONFIG_X86_64
+	if ((vcpu->arch.efer & EFER_LME) && !is_paging(vcpu) &&
+	    (cr0 & X86_CR0_PG)) {
+		int cs_db, cs_l;
+
+		if (!is_pae(vcpu))
+			return 1;
+		kvm_x86_call(get_cs_db_l_bits)(vcpu, &cs_db, &cs_l);
+		if (cs_l)
+			return 1;
+	}
+#endif
+	if (!(vcpu->arch.efer & EFER_LME) && (cr0 & X86_CR0_PG) &&
+	    is_pae(vcpu) && ((cr0 ^ old_cr0) & X86_CR0_PDPTR_BITS) &&
+	    !load_pdptrs(vcpu, kvm_read_cr3(vcpu)))
+		return 1;
+
+	if (!(cr0 & X86_CR0_PG) &&
+	    (is_64_bit_mode(vcpu) || kvm_is_cr4_bit_set(vcpu, X86_CR4_PCIDE)))
+		return 1;
+
+	if (!(cr0 & X86_CR0_WP) && kvm_is_cr4_bit_set(vcpu, X86_CR4_CET))
+		return 1;
+
+	kvm_x86_call(set_cr0)(vcpu, cr0);
+
+	kvm_post_set_cr0(vcpu, old_cr0, cr0);
+
+	return 0;
+}
+EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_set_cr0);
+
+void kvm_lmsw(struct kvm_vcpu *vcpu, unsigned long msw)
+{
+	(void)kvm_set_cr0(vcpu, kvm_read_cr0_bits(vcpu, ~0x0eul) | (msw & 0x0f));
+}
+EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_lmsw);
+
+int kvm_set_cr3(struct kvm_vcpu *vcpu, unsigned long cr3)
+{
+	bool skip_tlb_flush = false;
+	unsigned long pcid = 0;
+#ifdef CONFIG_X86_64
+	if (kvm_is_cr4_bit_set(vcpu, X86_CR4_PCIDE)) {
+		skip_tlb_flush = cr3 & X86_CR3_PCID_NOFLUSH;
+		cr3 &= ~X86_CR3_PCID_NOFLUSH;
+		pcid = cr3 & X86_CR3_PCID_MASK;
+	}
+#endif
+
+	/* PDPTRs are always reloaded for PAE paging. */
+	if (cr3 == kvm_read_cr3(vcpu) && !is_pae_paging(vcpu))
+		goto handle_tlb_flush;
+
+	/*
+	 * Do not condition the GPA check on long mode, this helper is used to
+	 * stuff CR3, e.g. for RSM emulation, and there is no guarantee that
+	 * the current vCPU mode is accurate.
+	 */
+	if (!kvm_vcpu_is_legal_cr3(vcpu, cr3))
+		return 1;
+
+	if (is_pae_paging(vcpu) && !load_pdptrs(vcpu, cr3))
+		return 1;
+
+	if (cr3 != kvm_read_cr3(vcpu))
+		kvm_mmu_new_pgd(vcpu, cr3);
+
+	vcpu->arch.cr3 = cr3;
+	kvm_register_mark_dirty(vcpu, VCPU_REG_CR3);
+	/* Do not call post_set_cr3, we do not get here for confidential guests.  */
+
+handle_tlb_flush:
+	/*
+	 * A load of CR3 that flushes the TLB flushes only the current PCID,
+	 * even if PCID is disabled, in which case PCID=0 is flushed.  It's a
+	 * moot point in the end because _disabling_ PCID will flush all PCIDs,
+	 * and it's impossible to use a non-zero PCID when PCID is disabled,
+	 * i.e. only PCID=0 can be relevant.
+	 */
+	if (!skip_tlb_flush)
+		kvm_invalidate_pcid(vcpu, pcid);
+
+	return 0;
+}
+EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_set_cr3);
+
+static bool kvm_is_valid_cr4(struct kvm_vcpu *vcpu, unsigned long cr4)
+{
+	return __kvm_is_valid_cr4(vcpu, cr4) &&
+	       kvm_x86_call(is_valid_cr4)(vcpu, cr4);
+}
+
+void kvm_post_set_cr4(struct kvm_vcpu *vcpu, unsigned long old_cr4, unsigned long cr4)
+{
+	if ((cr4 ^ old_cr4) & KVM_MMU_CR4_ROLE_BITS)
+		kvm_mmu_reset_context(vcpu);
+
+	/*
+	 * If CR4.PCIDE is changed 0 -> 1, there is no need to flush the TLB
+	 * according to the SDM; however, stale prev_roots could be reused
+	 * incorrectly in the future after a MOV to CR3 with NOFLUSH=1, so we
+	 * free them all.  This is *not* a superset of KVM_REQ_TLB_FLUSH_GUEST
+	 * or KVM_REQ_TLB_FLUSH_CURRENT, because the hardware TLB is not flushed,
+	 * so fall through.
+	 */
+	if (!tdp_enabled &&
+	    (cr4 & X86_CR4_PCIDE) && !(old_cr4 & X86_CR4_PCIDE))
+		kvm_mmu_unload(vcpu);
+
+	/*
+	 * The TLB has to be flushed for all PCIDs if any of the following
+	 * (architecturally required) changes happen:
+	 * - CR4.PCIDE is changed from 1 to 0
+	 * - CR4.PGE is toggled
+	 *
+	 * This is a superset of KVM_REQ_TLB_FLUSH_CURRENT.
+	 */
+	if (((cr4 ^ old_cr4) & X86_CR4_PGE) ||
+	    (!(cr4 & X86_CR4_PCIDE) && (old_cr4 & X86_CR4_PCIDE)))
+		kvm_make_request(KVM_REQ_TLB_FLUSH_GUEST, vcpu);
+
+	/*
+	 * The TLB has to be flushed for the current PCID if any of the
+	 * following (architecturally required) changes happen:
+	 * - CR4.SMEP is changed from 0 to 1
+	 * - CR4.PAE is toggled
+	 */
+	else if (((cr4 ^ old_cr4) & X86_CR4_PAE) ||
+		 ((cr4 & X86_CR4_SMEP) && !(old_cr4 & X86_CR4_SMEP)))
+		kvm_make_request(KVM_REQ_TLB_FLUSH_CURRENT, vcpu);
+
+}
+EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_post_set_cr4);
+
+int kvm_set_cr4(struct kvm_vcpu *vcpu, unsigned long cr4)
+{
+	unsigned long old_cr4 = kvm_read_cr4(vcpu);
+
+	if (!kvm_is_valid_cr4(vcpu, cr4))
+		return 1;
+
+	if (is_long_mode(vcpu)) {
+		if (!(cr4 & X86_CR4_PAE))
+			return 1;
+		if ((cr4 ^ old_cr4) & X86_CR4_LA57)
+			return 1;
+	} else if (is_paging(vcpu) && (cr4 & X86_CR4_PAE)
+		   && ((cr4 ^ old_cr4) & X86_CR4_PDPTR_BITS)
+		   && !load_pdptrs(vcpu, kvm_read_cr3(vcpu)))
+		return 1;
+
+	if ((cr4 & X86_CR4_PCIDE) && !(old_cr4 & X86_CR4_PCIDE)) {
+		/* PCID can not be enabled when cr3[11:0]!=000H or EFER.LMA=0 */
+		if ((kvm_read_cr3(vcpu) & X86_CR3_PCID_MASK) || !is_long_mode(vcpu))
+			return 1;
+	}
+
+	if ((cr4 & X86_CR4_CET) && !kvm_is_cr0_bit_set(vcpu, X86_CR0_WP))
+		return 1;
+
+	kvm_x86_call(set_cr4)(vcpu, cr4);
+
+	kvm_post_set_cr4(vcpu, old_cr4, cr4);
+
+	return 0;
+}
+EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_set_cr4);
+
+int kvm_set_cr8(struct kvm_vcpu *vcpu, unsigned long cr8)
+{
+	if (cr8 & CR8_RESERVED_BITS)
+		return 1;
+	if (lapic_in_kernel(vcpu))
+		kvm_lapic_set_tpr(vcpu, cr8);
+	else
+		vcpu->arch.cr8 = cr8;
+	return 0;
+}
+EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_set_cr8);
+
+unsigned long kvm_get_cr8(struct kvm_vcpu *vcpu)
+{
+	if (lapic_in_kernel(vcpu))
+		return kvm_lapic_get_cr8(vcpu);
+	else
+		return vcpu->arch.cr8;
+}
+EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_get_cr8);
+
+static void __get_sregs_common(struct kvm_vcpu *vcpu, struct kvm_sregs *sregs)
+{
+	struct desc_ptr dt;
+
+	if (vcpu->arch.guest_state_protected)
+		goto skip_protected_regs;
+
+	kvm_handle_exception_payload_quirk(vcpu);
+
+	kvm_get_segment(vcpu, &sregs->cs, VCPU_SREG_CS);
+	kvm_get_segment(vcpu, &sregs->ds, VCPU_SREG_DS);
+	kvm_get_segment(vcpu, &sregs->es, VCPU_SREG_ES);
+	kvm_get_segment(vcpu, &sregs->fs, VCPU_SREG_FS);
+	kvm_get_segment(vcpu, &sregs->gs, VCPU_SREG_GS);
+	kvm_get_segment(vcpu, &sregs->ss, VCPU_SREG_SS);
+
+	kvm_get_segment(vcpu, &sregs->tr, VCPU_SREG_TR);
+	kvm_get_segment(vcpu, &sregs->ldt, VCPU_SREG_LDTR);
+
+	kvm_x86_call(get_idt)(vcpu, &dt);
+	sregs->idt.limit = dt.size;
+	sregs->idt.base = dt.address;
+	kvm_x86_call(get_gdt)(vcpu, &dt);
+	sregs->gdt.limit = dt.size;
+	sregs->gdt.base = dt.address;
+
+	sregs->cr2 = vcpu->arch.cr2;
+	sregs->cr3 = kvm_read_cr3(vcpu);
+
+skip_protected_regs:
+	sregs->cr0 = kvm_read_cr0(vcpu);
+	sregs->cr4 = kvm_read_cr4(vcpu);
+	sregs->cr8 = kvm_get_cr8(vcpu);
+	sregs->efer = vcpu->arch.efer;
+	sregs->apic_base = vcpu->arch.apic_base;
+}
+
+static void __get_sregs(struct kvm_vcpu *vcpu, struct kvm_sregs *sregs)
+{
+	__get_sregs_common(vcpu, sregs);
+
+	if (vcpu->arch.guest_state_protected)
+		return;
+
+	if (vcpu->arch.interrupt.injected && !vcpu->arch.interrupt.soft)
+		set_bit(vcpu->arch.interrupt.nr,
+			(unsigned long *)sregs->interrupt_bitmap);
+}
+
+int kvm_arch_vcpu_ioctl_get_sregs(struct kvm_vcpu *vcpu,
+				  struct kvm_sregs *sregs)
+{
+	if (vcpu->kvm->arch.has_protected_state &&
+	    vcpu->arch.guest_state_protected)
+		return -EINVAL;
+
+	vcpu_load(vcpu);
+	__get_sregs(vcpu, sregs);
+	vcpu_put(vcpu);
+	return 0;
+}
+
+void kvm_x86_vcpu_ioctl_get_sregs2(struct kvm_vcpu *vcpu,
+				   struct kvm_sregs2 *sregs2)
+{
+	int i;
+
+	__get_sregs_common(vcpu, (struct kvm_sregs *)sregs2);
+
+	if (vcpu->arch.guest_state_protected)
+		return;
+
+	if (is_pae_paging(vcpu)) {
+		kvm_vcpu_srcu_read_lock(vcpu);
+		for (i = 0 ; i < 4 ; i++)
+			sregs2->pdptrs[i] = kvm_pdptr_read(vcpu, i);
+		sregs2->flags |= KVM_SREGS2_FLAGS_PDPTRS_VALID;
+		kvm_vcpu_srcu_read_unlock(vcpu);
+	}
+}
+
+static bool kvm_is_valid_sregs(struct kvm_vcpu *vcpu, struct kvm_sregs *sregs)
+{
+	if ((sregs->efer & EFER_LME) && (sregs->cr0 & X86_CR0_PG)) {
+		/*
+		 * When EFER.LME and CR0.PG are set, the processor is in
+		 * 64-bit mode (though maybe in a 32-bit code segment).
+		 * CR4.PAE and EFER.LMA must be set.
+		 */
+		if (!(sregs->cr4 & X86_CR4_PAE) || !(sregs->efer & EFER_LMA))
+			return false;
+		if (!kvm_vcpu_is_legal_cr3(vcpu, sregs->cr3))
+			return false;
+	} else {
+		/*
+		 * Not in 64-bit mode: EFER.LMA is clear and the code
+		 * segment cannot be 64-bit.
+		 */
+		if (sregs->efer & EFER_LMA || sregs->cs.l)
+			return false;
+	}
+
+	return kvm_is_valid_cr4(vcpu, sregs->cr4) &&
+	       kvm_is_valid_cr0(vcpu, sregs->cr0);
+}
+
+static int __set_sregs_common(struct kvm_vcpu *vcpu, struct kvm_sregs *sregs,
+			      int *mmu_reset_needed, bool update_pdptrs)
+{
+	int idx;
+	struct desc_ptr dt;
+
+	if (!kvm_is_valid_sregs(vcpu, sregs))
+		return -EINVAL;
+
+	if (kvm_apic_set_base(vcpu, sregs->apic_base, true))
+		return -EINVAL;
+
+	if (vcpu->arch.guest_state_protected)
+		return 0;
+
+	dt.size = sregs->idt.limit;
+	dt.address = sregs->idt.base;
+	kvm_x86_call(set_idt)(vcpu, &dt);
+	dt.size = sregs->gdt.limit;
+	dt.address = sregs->gdt.base;
+	kvm_x86_call(set_gdt)(vcpu, &dt);
+
+	vcpu->arch.cr2 = sregs->cr2;
+	*mmu_reset_needed |= kvm_read_cr3(vcpu) != sregs->cr3;
+	vcpu->arch.cr3 = sregs->cr3;
+	kvm_register_mark_dirty(vcpu, VCPU_REG_CR3);
+	kvm_x86_call(post_set_cr3)(vcpu, sregs->cr3);
+
+	kvm_set_cr8(vcpu, sregs->cr8);
+
+	*mmu_reset_needed |= vcpu->arch.efer != sregs->efer;
+	kvm_x86_call(set_efer)(vcpu, sregs->efer);
+
+	*mmu_reset_needed |= kvm_read_cr0(vcpu) != sregs->cr0;
+	kvm_x86_call(set_cr0)(vcpu, sregs->cr0);
+
+	*mmu_reset_needed |= kvm_read_cr4(vcpu) != sregs->cr4;
+	kvm_x86_call(set_cr4)(vcpu, sregs->cr4);
+
+	if (update_pdptrs) {
+		idx = srcu_read_lock(&vcpu->kvm->srcu);
+		if (is_pae_paging(vcpu)) {
+			load_pdptrs(vcpu, kvm_read_cr3(vcpu));
+			*mmu_reset_needed = 1;
+		}
+		srcu_read_unlock(&vcpu->kvm->srcu, idx);
+	}
+
+	kvm_set_segment(vcpu, &sregs->cs, VCPU_SREG_CS);
+	kvm_set_segment(vcpu, &sregs->ds, VCPU_SREG_DS);
+	kvm_set_segment(vcpu, &sregs->es, VCPU_SREG_ES);
+	kvm_set_segment(vcpu, &sregs->fs, VCPU_SREG_FS);
+	kvm_set_segment(vcpu, &sregs->gs, VCPU_SREG_GS);
+	kvm_set_segment(vcpu, &sregs->ss, VCPU_SREG_SS);
+
+	kvm_set_segment(vcpu, &sregs->tr, VCPU_SREG_TR);
+	kvm_set_segment(vcpu, &sregs->ldt, VCPU_SREG_LDTR);
+
+	kvm_lapic_update_cr8_intercept(vcpu);
+
+	/* Older userspace won't unhalt the vcpu on reset. */
+	if (kvm_vcpu_is_bsp(vcpu) && kvm_rip_read(vcpu) == 0xfff0 &&
+	    sregs->cs.selector == 0xf000 && sregs->cs.base == 0xffff0000 &&
+	    !is_protmode(vcpu))
+		kvm_set_mp_state(vcpu, KVM_MP_STATE_RUNNABLE);
+
+	return 0;
+}
+
+static int __set_sregs(struct kvm_vcpu *vcpu, struct kvm_sregs *sregs)
+{
+	int pending_vec, max_bits;
+	int mmu_reset_needed = 0;
+	int ret = __set_sregs_common(vcpu, sregs, &mmu_reset_needed, true);
+
+	if (ret)
+		return ret;
+
+	if (mmu_reset_needed) {
+		kvm_mmu_reset_context(vcpu);
+		kvm_make_request(KVM_REQ_TLB_FLUSH_GUEST, vcpu);
+	}
+
+	max_bits = KVM_NR_INTERRUPTS;
+	pending_vec = find_first_bit(
+		(const unsigned long *)sregs->interrupt_bitmap, max_bits);
+
+	if (pending_vec < max_bits) {
+		kvm_queue_interrupt(vcpu, pending_vec, false);
+		pr_debug("Set back pending irq %d\n", pending_vec);
+		kvm_make_request(KVM_REQ_EVENT, vcpu);
+	}
+	return 0;
+}
+
+int kvm_arch_vcpu_ioctl_set_sregs(struct kvm_vcpu *vcpu,
+				  struct kvm_sregs *sregs)
+{
+	int ret;
+
+	if (vcpu->kvm->arch.has_protected_state &&
+	    vcpu->arch.guest_state_protected)
+		return -EINVAL;
+
+	vcpu_load(vcpu);
+	ret = __set_sregs(vcpu, sregs);
+	vcpu_put(vcpu);
+	return ret;
+}
+
+int kvm_x86_vcpu_ioctl_set_sregs2(struct kvm_vcpu *vcpu,
+				  struct kvm_sregs2 *sregs2)
+{
+	int mmu_reset_needed = 0;
+	bool valid_pdptrs = sregs2->flags & KVM_SREGS2_FLAGS_PDPTRS_VALID;
+	bool pae = (sregs2->cr0 & X86_CR0_PG) && (sregs2->cr4 & X86_CR4_PAE) &&
+		!(sregs2->efer & EFER_LMA);
+	int i, ret;
+
+	if (sregs2->flags & ~KVM_SREGS2_FLAGS_PDPTRS_VALID)
+		return -EINVAL;
+
+	if (valid_pdptrs && (!pae || vcpu->arch.guest_state_protected))
+		return -EINVAL;
+
+	ret = __set_sregs_common(vcpu, (struct kvm_sregs *)sregs2,
+				 &mmu_reset_needed, !valid_pdptrs);
+	if (ret)
+		return ret;
+
+	if (valid_pdptrs) {
+		for (i = 0; i < 4 ; i++)
+			kvm_pdptr_write(vcpu, i, sregs2->pdptrs[i]);
+
+		kvm_register_mark_dirty(vcpu, VCPU_REG_PDPTR);
+		mmu_reset_needed = 1;
+		vcpu->arch.pdptrs_from_userspace = true;
+	}
+	if (mmu_reset_needed) {
+		kvm_mmu_reset_context(vcpu);
+		kvm_make_request(KVM_REQ_TLB_FLUSH_GUEST, vcpu);
+	}
+	return 0;
+}
+
+void kvm_run_get_regs(struct kvm_vcpu *vcpu)
+{
+	BUILD_BUG_ON(sizeof(struct kvm_sync_regs) > SYNC_REGS_SIZE_BYTES);
+
+	if (vcpu->run->kvm_valid_regs & KVM_SYNC_X86_REGS)
+		__get_regs(vcpu, &vcpu->run->s.regs.regs);
+
+	if (vcpu->run->kvm_valid_regs & KVM_SYNC_X86_SREGS)
+		__get_sregs(vcpu, &vcpu->run->s.regs.sregs);
+}
+
+int kvm_run_set_regs(struct kvm_vcpu *vcpu)
+{
+	if (vcpu->run->kvm_dirty_regs & KVM_SYNC_X86_REGS) {
+		__set_regs(vcpu, &vcpu->run->s.regs.regs);
+		vcpu->run->kvm_dirty_regs &= ~KVM_SYNC_X86_REGS;
+	}
+
+	if (vcpu->run->kvm_dirty_regs & KVM_SYNC_X86_SREGS) {
+		struct kvm_sregs sregs = vcpu->run->s.regs.sregs;
+
+		if (__set_sregs(vcpu, &sregs))
+			return -EINVAL;
+
+		vcpu->run->kvm_dirty_regs &= ~KVM_SYNC_X86_SREGS;
+	}
+
+	return 0;
+}
+
+void kvm_update_dr0123(struct kvm_vcpu *vcpu)
+{
+	int i;
+
+	if (!(vcpu->guest_debug & KVM_GUESTDBG_USE_HW_BP)) {
+		for (i = 0; i < KVM_NR_DB_REGS; i++)
+			vcpu->arch.eff_db[i] = vcpu->arch.db[i];
+	}
+}
+
+void kvm_update_dr7(struct kvm_vcpu *vcpu)
+{
+	unsigned long dr7;
+
+	if (vcpu->guest_debug & KVM_GUESTDBG_USE_HW_BP)
+		dr7 = vcpu->arch.guest_debug_dr7;
+	else
+		dr7 = vcpu->arch.dr7;
+	kvm_x86_call(set_dr7)(vcpu, dr7);
+	vcpu->arch.switch_db_regs &= ~KVM_DEBUGREG_BP_ENABLED;
+	if (dr7 & DR7_BP_EN_MASK)
+		vcpu->arch.switch_db_regs |= KVM_DEBUGREG_BP_ENABLED;
+}
+EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_update_dr7);
+
+static u64 kvm_dr6_fixed(struct kvm_vcpu *vcpu)
+{
+	u64 fixed = DR6_FIXED_1;
+
+	if (!guest_cpu_cap_has(vcpu, X86_FEATURE_RTM))
+		fixed |= DR6_RTM;
+
+	if (!guest_cpu_cap_has(vcpu, X86_FEATURE_BUS_LOCK_DETECT))
+		fixed |= DR6_BUS_LOCK;
+	return fixed;
+}
+
+int kvm_set_dr(struct kvm_vcpu *vcpu, int dr, unsigned long val)
+{
+	size_t size = ARRAY_SIZE(vcpu->arch.db);
+
+	switch (dr) {
+	case 0 ... 3:
+		vcpu->arch.db[array_index_nospec(dr, size)] = val;
+		if (!(vcpu->guest_debug & KVM_GUESTDBG_USE_HW_BP))
+			vcpu->arch.eff_db[dr] = val;
+		break;
+	case 4:
+	case 6:
+		if (!kvm_dr6_valid(val))
+			return 1; /* #GP */
+		vcpu->arch.dr6 = (val & DR6_VOLATILE) | kvm_dr6_fixed(vcpu);
+		break;
+	case 5:
+	default: /* 7 */
+		if (!kvm_dr7_valid(val))
+			return 1; /* #GP */
+		vcpu->arch.dr7 = (val & DR7_VOLATILE) | DR7_FIXED_1;
+		kvm_update_dr7(vcpu);
+		break;
+	}
+
+	return 0;
+}
+EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_set_dr);
+
+unsigned long kvm_get_dr(struct kvm_vcpu *vcpu, int dr)
+{
+	size_t size = ARRAY_SIZE(vcpu->arch.db);
+
+	switch (dr) {
+	case 0 ... 3:
+		return vcpu->arch.db[array_index_nospec(dr, size)];
+	case 4:
+	case 6:
+		return vcpu->arch.dr6;
+	case 5:
+	default: /* 7 */
+		return vcpu->arch.dr7;
+	}
+}
+EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_get_dr);
+
+int kvm_vcpu_ioctl_x86_get_debugregs(struct kvm_vcpu *vcpu,
+				     struct kvm_debugregs *dbgregs)
+{
+	unsigned int i;
+
+	if (vcpu->kvm->arch.has_protected_state &&
+	    vcpu->arch.guest_state_protected)
+		return -EINVAL;
+
+	kvm_handle_exception_payload_quirk(vcpu);
+
+	memset(dbgregs, 0, sizeof(*dbgregs));
+
+	BUILD_BUG_ON(ARRAY_SIZE(vcpu->arch.db) != ARRAY_SIZE(dbgregs->db));
+	for (i = 0; i < ARRAY_SIZE(vcpu->arch.db); i++)
+		dbgregs->db[i] = vcpu->arch.db[i];
+
+	dbgregs->dr6 = vcpu->arch.dr6;
+	dbgregs->dr7 = vcpu->arch.dr7;
+	return 0;
+}
+
+int kvm_vcpu_ioctl_x86_set_debugregs(struct kvm_vcpu *vcpu,
+				     struct kvm_debugregs *dbgregs)
+{
+	unsigned int i;
+
+	if (vcpu->kvm->arch.has_protected_state &&
+	    vcpu->arch.guest_state_protected)
+		return -EINVAL;
+
+	if (dbgregs->flags)
+		return -EINVAL;
+
+	if (!kvm_dr6_valid(dbgregs->dr6))
+		return -EINVAL;
+	if (!kvm_dr7_valid(dbgregs->dr7))
+		return -EINVAL;
+
+	for (i = 0; i < ARRAY_SIZE(vcpu->arch.db); i++)
+		vcpu->arch.db[i] = dbgregs->db[i];
+
+	kvm_update_dr0123(vcpu);
+	vcpu->arch.dr6 = dbgregs->dr6;
+	vcpu->arch.dr7 = dbgregs->dr7;
+	kvm_update_dr7(vcpu);
+
+	return 0;
+}
diff --git a/arch/x86/kvm/regs.h b/arch/x86/kvm/regs.h
index d4d2a47a4968..875a1b66d67a 100644
--- a/arch/x86/kvm/regs.h
+++ b/arch/x86/kvm/regs.h
@@ -401,4 +401,20 @@ static inline bool is_guest_mode(struct kvm_vcpu *vcpu)
 	return vcpu->arch.hflags & HF_GUEST_MASK;
 }
 
+void kvm_x86_vcpu_ioctl_get_sregs2(struct kvm_vcpu *vcpu,
+				   struct kvm_sregs2 *sregs2);
+int kvm_x86_vcpu_ioctl_set_sregs2(struct kvm_vcpu *vcpu,
+				  struct kvm_sregs2 *sregs2);
+
+void kvm_run_get_regs(struct kvm_vcpu *vcpu);
+int kvm_run_set_regs(struct kvm_vcpu *vcpu);
+
+void kvm_update_dr0123(struct kvm_vcpu *vcpu);
+void kvm_update_dr7(struct kvm_vcpu *vcpu);
+int kvm_vcpu_ioctl_x86_get_debugregs(struct kvm_vcpu *vcpu,
+				     struct kvm_debugregs *dbgregs);
+int kvm_vcpu_ioctl_x86_set_debugregs(struct kvm_vcpu *vcpu,
+				     struct kvm_debugregs *dbgregs);
+
+
 #endif
diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index e664e874973b..4ba1e329ac68 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -134,9 +134,6 @@ static void store_regs(struct kvm_vcpu *vcpu);
 static int sync_regs(struct kvm_vcpu *vcpu);
 static int kvm_vcpu_do_singlestep(struct kvm_vcpu *vcpu);
 
-static int __set_sregs2(struct kvm_vcpu *vcpu, struct kvm_sregs2 *sregs2);
-static void __get_sregs2(struct kvm_vcpu *vcpu, struct kvm_sregs2 *sregs2);
-
 static DEFINE_MUTEX(vendor_module_lock);
 static void kvm_load_guest_fpu(struct kvm_vcpu *vcpu);
 static void kvm_put_guest_fpu(struct kvm_vcpu *vcpu);
@@ -1042,170 +1039,6 @@ bool kvm_require_dr(struct kvm_vcpu *vcpu, int dr)
 }
 EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_require_dr);
 
-static inline u64 pdptr_rsvd_bits(struct kvm_vcpu *vcpu)
-{
-	return vcpu->arch.reserved_gpa_bits | rsvd_bits(5, 8) | rsvd_bits(1, 2);
-}
-
-/*
- * Load the pae pdptrs.  Return 1 if they are all valid, 0 otherwise.
- */
-int load_pdptrs(struct kvm_vcpu *vcpu, unsigned long cr3)
-{
-	struct kvm_mmu *mmu = vcpu->arch.walk_mmu;
-	gfn_t pdpt_gfn = cr3 >> PAGE_SHIFT;
-	gpa_t real_gpa;
-	int i;
-	int ret;
-	u64 pdpte[ARRAY_SIZE(mmu->pdptrs)];
-
-	/*
-	 * If the MMU is nested, CR3 holds an L2 GPA and needs to be translated
-	 * to an L1 GPA.
-	 */
-	real_gpa = kvm_translate_gpa(vcpu, mmu, gfn_to_gpa(pdpt_gfn),
-				     PFERR_USER_MASK | PFERR_WRITE_MASK |
-				     PFERR_GUEST_PAGE_MASK, NULL, 0);
-	if (real_gpa == INVALID_GPA)
-		return 0;
-
-	/* Note the offset, PDPTRs are 32 byte aligned when using PAE paging. */
-	ret = kvm_vcpu_read_guest_page(vcpu, gpa_to_gfn(real_gpa), pdpte,
-				       cr3 & GENMASK(11, 5), sizeof(pdpte));
-	if (ret < 0)
-		return 0;
-
-	for (i = 0; i < ARRAY_SIZE(pdpte); ++i) {
-		if ((pdpte[i] & PT_PRESENT_MASK) &&
-		    (pdpte[i] & pdptr_rsvd_bits(vcpu))) {
-			return 0;
-		}
-	}
-
-	/*
-	 * Marking VCPU_REG_PDPTR dirty doesn't work for !tdp_enabled.
-	 * Shadow page roots need to be reconstructed instead.
-	 */
-	if (!tdp_enabled && memcmp(mmu->pdptrs, pdpte, sizeof(mmu->pdptrs)))
-		kvm_mmu_free_roots(vcpu->kvm, mmu, KVM_MMU_ROOT_CURRENT);
-
-	memcpy(mmu->pdptrs, pdpte, sizeof(mmu->pdptrs));
-	kvm_register_mark_dirty(vcpu, VCPU_REG_PDPTR);
-	kvm_make_request(KVM_REQ_LOAD_MMU_PGD, vcpu);
-	vcpu->arch.pdptrs_from_userspace = false;
-
-	return 1;
-}
-EXPORT_SYMBOL_FOR_KVM_INTERNAL(load_pdptrs);
-
-static bool kvm_is_valid_cr0(struct kvm_vcpu *vcpu, unsigned long cr0)
-{
-#ifdef CONFIG_X86_64
-	if (cr0 & 0xffffffff00000000UL)
-		return false;
-#endif
-
-	if ((cr0 & X86_CR0_NW) && !(cr0 & X86_CR0_CD))
-		return false;
-
-	if ((cr0 & X86_CR0_PG) && !(cr0 & X86_CR0_PE))
-		return false;
-
-	return kvm_x86_call(is_valid_cr0)(vcpu, cr0);
-}
-
-void kvm_post_set_cr0(struct kvm_vcpu *vcpu, unsigned long old_cr0, unsigned long cr0)
-{
-	/*
-	 * CR0.WP is incorporated into the MMU role, but only for non-nested,
-	 * indirect shadow MMUs.  If paging is disabled, no updates are needed
-	 * as there are no permission bits to emulate.  If TDP is enabled, the
-	 * MMU's metadata needs to be updated, e.g. so that emulating guest
-	 * translations does the right thing, but there's no need to unload the
-	 * root as CR0.WP doesn't affect SPTEs.
-	 */
-	if ((cr0 ^ old_cr0) == X86_CR0_WP) {
-		if (!(cr0 & X86_CR0_PG))
-			return;
-
-		if (tdp_enabled) {
-			kvm_init_mmu(vcpu);
-			return;
-		}
-	}
-
-	if ((cr0 ^ old_cr0) & X86_CR0_PG) {
-		/*
-		 * Clearing CR0.PG is defined to flush the TLB from the guest's
-		 * perspective.
-		 */
-		if (!(cr0 & X86_CR0_PG))
-			kvm_make_request(KVM_REQ_TLB_FLUSH_GUEST, vcpu);
-		/*
-		 * Check for async #PF completion events when enabling paging,
-		 * as the vCPU may have previously encountered async #PFs (it's
-		 * entirely legal for the guest to toggle paging on/off without
-		 * waiting for the async #PF queue to drain).
-		 */
-		else if (kvm_pv_async_pf_enabled(vcpu))
-			kvm_make_request(KVM_REQ_APF_READY, vcpu);
-	}
-
-	if ((cr0 ^ old_cr0) & KVM_MMU_CR0_ROLE_BITS)
-		kvm_mmu_reset_context(vcpu);
-}
-EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_post_set_cr0);
-
-int kvm_set_cr0(struct kvm_vcpu *vcpu, unsigned long cr0)
-{
-	unsigned long old_cr0 = kvm_read_cr0(vcpu);
-
-	if (!kvm_is_valid_cr0(vcpu, cr0))
-		return 1;
-
-	cr0 |= X86_CR0_ET;
-
-	/* Write to CR0 reserved bits are ignored, even on Intel. */
-	cr0 &= ~CR0_RESERVED_BITS;
-
-#ifdef CONFIG_X86_64
-	if ((vcpu->arch.efer & EFER_LME) && !is_paging(vcpu) &&
-	    (cr0 & X86_CR0_PG)) {
-		int cs_db, cs_l;
-
-		if (!is_pae(vcpu))
-			return 1;
-		kvm_x86_call(get_cs_db_l_bits)(vcpu, &cs_db, &cs_l);
-		if (cs_l)
-			return 1;
-	}
-#endif
-	if (!(vcpu->arch.efer & EFER_LME) && (cr0 & X86_CR0_PG) &&
-	    is_pae(vcpu) && ((cr0 ^ old_cr0) & X86_CR0_PDPTR_BITS) &&
-	    !load_pdptrs(vcpu, kvm_read_cr3(vcpu)))
-		return 1;
-
-	if (!(cr0 & X86_CR0_PG) &&
-	    (is_64_bit_mode(vcpu) || kvm_is_cr4_bit_set(vcpu, X86_CR4_PCIDE)))
-		return 1;
-
-	if (!(cr0 & X86_CR0_WP) && kvm_is_cr4_bit_set(vcpu, X86_CR4_CET))
-		return 1;
-
-	kvm_x86_call(set_cr0)(vcpu, cr0);
-
-	kvm_post_set_cr0(vcpu, old_cr0, cr0);
-
-	return 0;
-}
-EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_set_cr0);
-
-void kvm_lmsw(struct kvm_vcpu *vcpu, unsigned long msw)
-{
-	(void)kvm_set_cr0(vcpu, kvm_read_cr0_bits(vcpu, ~0x0eul) | (msw & 0x0f));
-}
-EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_lmsw);
-
 static void kvm_load_xfeatures(struct kvm_vcpu *vcpu, bool load_guest)
 {
 	if (vcpu->arch.guest_state_protected)
@@ -1315,89 +1148,7 @@ int kvm_emulate_xsetbv(struct kvm_vcpu *vcpu)
 }
 EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_emulate_xsetbv);
 
-static bool kvm_is_valid_cr4(struct kvm_vcpu *vcpu, unsigned long cr4)
-{
-	return __kvm_is_valid_cr4(vcpu, cr4) &&
-	       kvm_x86_call(is_valid_cr4)(vcpu, cr4);
-}
-
-void kvm_post_set_cr4(struct kvm_vcpu *vcpu, unsigned long old_cr4, unsigned long cr4)
-{
-	if ((cr4 ^ old_cr4) & KVM_MMU_CR4_ROLE_BITS)
-		kvm_mmu_reset_context(vcpu);
-
-	/*
-	 * If CR4.PCIDE is changed 0 -> 1, there is no need to flush the TLB
-	 * according to the SDM; however, stale prev_roots could be reused
-	 * incorrectly in the future after a MOV to CR3 with NOFLUSH=1, so we
-	 * free them all.  This is *not* a superset of KVM_REQ_TLB_FLUSH_GUEST
-	 * or KVM_REQ_TLB_FLUSH_CURRENT, because the hardware TLB is not flushed,
-	 * so fall through.
-	 */
-	if (!tdp_enabled &&
-	    (cr4 & X86_CR4_PCIDE) && !(old_cr4 & X86_CR4_PCIDE))
-		kvm_mmu_unload(vcpu);
-
-	/*
-	 * The TLB has to be flushed for all PCIDs if any of the following
-	 * (architecturally required) changes happen:
-	 * - CR4.PCIDE is changed from 1 to 0
-	 * - CR4.PGE is toggled
-	 *
-	 * This is a superset of KVM_REQ_TLB_FLUSH_CURRENT.
-	 */
-	if (((cr4 ^ old_cr4) & X86_CR4_PGE) ||
-	    (!(cr4 & X86_CR4_PCIDE) && (old_cr4 & X86_CR4_PCIDE)))
-		kvm_make_request(KVM_REQ_TLB_FLUSH_GUEST, vcpu);
-
-	/*
-	 * The TLB has to be flushed for the current PCID if any of the
-	 * following (architecturally required) changes happen:
-	 * - CR4.SMEP is changed from 0 to 1
-	 * - CR4.PAE is toggled
-	 */
-	else if (((cr4 ^ old_cr4) & X86_CR4_PAE) ||
-		 ((cr4 & X86_CR4_SMEP) && !(old_cr4 & X86_CR4_SMEP)))
-		kvm_make_request(KVM_REQ_TLB_FLUSH_CURRENT, vcpu);
-
-}
-EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_post_set_cr4);
-
-int kvm_set_cr4(struct kvm_vcpu *vcpu, unsigned long cr4)
-{
-	unsigned long old_cr4 = kvm_read_cr4(vcpu);
-
-	if (!kvm_is_valid_cr4(vcpu, cr4))
-		return 1;
-
-	if (is_long_mode(vcpu)) {
-		if (!(cr4 & X86_CR4_PAE))
-			return 1;
-		if ((cr4 ^ old_cr4) & X86_CR4_LA57)
-			return 1;
-	} else if (is_paging(vcpu) && (cr4 & X86_CR4_PAE)
-		   && ((cr4 ^ old_cr4) & X86_CR4_PDPTR_BITS)
-		   && !load_pdptrs(vcpu, kvm_read_cr3(vcpu)))
-		return 1;
-
-	if ((cr4 & X86_CR4_PCIDE) && !(old_cr4 & X86_CR4_PCIDE)) {
-		/* PCID can not be enabled when cr3[11:0]!=000H or EFER.LMA=0 */
-		if ((kvm_read_cr3(vcpu) & X86_CR3_PCID_MASK) || !is_long_mode(vcpu))
-			return 1;
-	}
-
-	if ((cr4 & X86_CR4_CET) && !kvm_is_cr0_bit_set(vcpu, X86_CR0_WP))
-		return 1;
-
-	kvm_x86_call(set_cr4)(vcpu, cr4);
-
-	kvm_post_set_cr4(vcpu, old_cr4, cr4);
-
-	return 0;
-}
-EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_set_cr4);
-
-static void kvm_invalidate_pcid(struct kvm_vcpu *vcpu, unsigned long pcid)
+void kvm_invalidate_pcid(struct kvm_vcpu *vcpu, unsigned long pcid)
 {
 	struct kvm_mmu *mmu = vcpu->arch.mmu;
 	unsigned long roots_to_free = 0;
@@ -1440,159 +1191,6 @@ static void kvm_invalidate_pcid(struct kvm_vcpu *vcpu, unsigned long pcid)
 	kvm_mmu_free_roots(vcpu->kvm, mmu, roots_to_free);
 }
 
-int kvm_set_cr3(struct kvm_vcpu *vcpu, unsigned long cr3)
-{
-	bool skip_tlb_flush = false;
-	unsigned long pcid = 0;
-#ifdef CONFIG_X86_64
-	if (kvm_is_cr4_bit_set(vcpu, X86_CR4_PCIDE)) {
-		skip_tlb_flush = cr3 & X86_CR3_PCID_NOFLUSH;
-		cr3 &= ~X86_CR3_PCID_NOFLUSH;
-		pcid = cr3 & X86_CR3_PCID_MASK;
-	}
-#endif
-
-	/* PDPTRs are always reloaded for PAE paging. */
-	if (cr3 == kvm_read_cr3(vcpu) && !is_pae_paging(vcpu))
-		goto handle_tlb_flush;
-
-	/*
-	 * Do not condition the GPA check on long mode, this helper is used to
-	 * stuff CR3, e.g. for RSM emulation, and there is no guarantee that
-	 * the current vCPU mode is accurate.
-	 */
-	if (!kvm_vcpu_is_legal_cr3(vcpu, cr3))
-		return 1;
-
-	if (is_pae_paging(vcpu) && !load_pdptrs(vcpu, cr3))
-		return 1;
-
-	if (cr3 != kvm_read_cr3(vcpu))
-		kvm_mmu_new_pgd(vcpu, cr3);
-
-	vcpu->arch.cr3 = cr3;
-	kvm_register_mark_dirty(vcpu, VCPU_REG_CR3);
-	/* Do not call post_set_cr3, we do not get here for confidential guests.  */
-
-handle_tlb_flush:
-	/*
-	 * A load of CR3 that flushes the TLB flushes only the current PCID,
-	 * even if PCID is disabled, in which case PCID=0 is flushed.  It's a
-	 * moot point in the end because _disabling_ PCID will flush all PCIDs,
-	 * and it's impossible to use a non-zero PCID when PCID is disabled,
-	 * i.e. only PCID=0 can be relevant.
-	 */
-	if (!skip_tlb_flush)
-		kvm_invalidate_pcid(vcpu, pcid);
-
-	return 0;
-}
-EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_set_cr3);
-
-int kvm_set_cr8(struct kvm_vcpu *vcpu, unsigned long cr8)
-{
-	if (cr8 & CR8_RESERVED_BITS)
-		return 1;
-	if (lapic_in_kernel(vcpu))
-		kvm_lapic_set_tpr(vcpu, cr8);
-	else
-		vcpu->arch.cr8 = cr8;
-	return 0;
-}
-EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_set_cr8);
-
-unsigned long kvm_get_cr8(struct kvm_vcpu *vcpu)
-{
-	if (lapic_in_kernel(vcpu))
-		return kvm_lapic_get_cr8(vcpu);
-	else
-		return vcpu->arch.cr8;
-}
-EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_get_cr8);
-
-static void kvm_update_dr0123(struct kvm_vcpu *vcpu)
-{
-	int i;
-
-	if (!(vcpu->guest_debug & KVM_GUESTDBG_USE_HW_BP)) {
-		for (i = 0; i < KVM_NR_DB_REGS; i++)
-			vcpu->arch.eff_db[i] = vcpu->arch.db[i];
-	}
-}
-
-void kvm_update_dr7(struct kvm_vcpu *vcpu)
-{
-	unsigned long dr7;
-
-	if (vcpu->guest_debug & KVM_GUESTDBG_USE_HW_BP)
-		dr7 = vcpu->arch.guest_debug_dr7;
-	else
-		dr7 = vcpu->arch.dr7;
-	kvm_x86_call(set_dr7)(vcpu, dr7);
-	vcpu->arch.switch_db_regs &= ~KVM_DEBUGREG_BP_ENABLED;
-	if (dr7 & DR7_BP_EN_MASK)
-		vcpu->arch.switch_db_regs |= KVM_DEBUGREG_BP_ENABLED;
-}
-EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_update_dr7);
-
-static u64 kvm_dr6_fixed(struct kvm_vcpu *vcpu)
-{
-	u64 fixed = DR6_FIXED_1;
-
-	if (!guest_cpu_cap_has(vcpu, X86_FEATURE_RTM))
-		fixed |= DR6_RTM;
-
-	if (!guest_cpu_cap_has(vcpu, X86_FEATURE_BUS_LOCK_DETECT))
-		fixed |= DR6_BUS_LOCK;
-	return fixed;
-}
-
-int kvm_set_dr(struct kvm_vcpu *vcpu, int dr, unsigned long val)
-{
-	size_t size = ARRAY_SIZE(vcpu->arch.db);
-
-	switch (dr) {
-	case 0 ... 3:
-		vcpu->arch.db[array_index_nospec(dr, size)] = val;
-		if (!(vcpu->guest_debug & KVM_GUESTDBG_USE_HW_BP))
-			vcpu->arch.eff_db[dr] = val;
-		break;
-	case 4:
-	case 6:
-		if (!kvm_dr6_valid(val))
-			return 1; /* #GP */
-		vcpu->arch.dr6 = (val & DR6_VOLATILE) | kvm_dr6_fixed(vcpu);
-		break;
-	case 5:
-	default: /* 7 */
-		if (!kvm_dr7_valid(val))
-			return 1; /* #GP */
-		vcpu->arch.dr7 = (val & DR7_VOLATILE) | DR7_FIXED_1;
-		kvm_update_dr7(vcpu);
-		break;
-	}
-
-	return 0;
-}
-EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_set_dr);
-
-unsigned long kvm_get_dr(struct kvm_vcpu *vcpu, int dr)
-{
-	size_t size = ARRAY_SIZE(vcpu->arch.db);
-
-	switch (dr) {
-	case 0 ... 3:
-		return vcpu->arch.db[array_index_nospec(dr, size)];
-	case 4:
-	case 6:
-		return vcpu->arch.dr6;
-	case 5:
-	default: /* 7 */
-		return vcpu->arch.dr7;
-	}
-}
-EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_get_dr);
-
 int kvm_emulate_rdpmc(struct kvm_vcpu *vcpu)
 {
 	u32 pmc = kvm_ecx_read(vcpu);
@@ -5544,7 +5142,7 @@ static struct kvm_queued_exception *kvm_get_exception_to_save(struct kvm_vcpu *v
 	return &vcpu->arch.exception;
 }
 
-static void kvm_handle_exception_payload_quirk(struct kvm_vcpu *vcpu)
+void kvm_handle_exception_payload_quirk(struct kvm_vcpu *vcpu)
 {
 	struct kvm_queued_exception *ex = kvm_get_exception_to_save(vcpu);
 
@@ -5748,57 +5346,6 @@ static int kvm_vcpu_ioctl_x86_set_vcpu_events(struct kvm_vcpu *vcpu,
 	return 0;
 }
 
-static int kvm_vcpu_ioctl_x86_get_debugregs(struct kvm_vcpu *vcpu,
-					    struct kvm_debugregs *dbgregs)
-{
-	unsigned int i;
-
-	if (vcpu->kvm->arch.has_protected_state &&
-	    vcpu->arch.guest_state_protected)
-		return -EINVAL;
-
-	kvm_handle_exception_payload_quirk(vcpu);
-
-	memset(dbgregs, 0, sizeof(*dbgregs));
-
-	BUILD_BUG_ON(ARRAY_SIZE(vcpu->arch.db) != ARRAY_SIZE(dbgregs->db));
-	for (i = 0; i < ARRAY_SIZE(vcpu->arch.db); i++)
-		dbgregs->db[i] = vcpu->arch.db[i];
-
-	dbgregs->dr6 = vcpu->arch.dr6;
-	dbgregs->dr7 = vcpu->arch.dr7;
-	return 0;
-}
-
-static int kvm_vcpu_ioctl_x86_set_debugregs(struct kvm_vcpu *vcpu,
-					    struct kvm_debugregs *dbgregs)
-{
-	unsigned int i;
-
-	if (vcpu->kvm->arch.has_protected_state &&
-	    vcpu->arch.guest_state_protected)
-		return -EINVAL;
-
-	if (dbgregs->flags)
-		return -EINVAL;
-
-	if (!kvm_dr6_valid(dbgregs->dr6))
-		return -EINVAL;
-	if (!kvm_dr7_valid(dbgregs->dr7))
-		return -EINVAL;
-
-	for (i = 0; i < ARRAY_SIZE(vcpu->arch.db); i++)
-		vcpu->arch.db[i] = dbgregs->db[i];
-
-	kvm_update_dr0123(vcpu);
-	vcpu->arch.dr6 = dbgregs->dr6;
-	vcpu->arch.dr7 = dbgregs->dr7;
-	kvm_update_dr7(vcpu);
-
-	return 0;
-}
-
-
 static int kvm_vcpu_ioctl_x86_get_xsave2(struct kvm_vcpu *vcpu,
 					 u8 *state, unsigned int size)
 {
@@ -6635,7 +6182,7 @@ long kvm_arch_vcpu_ioctl(struct file *filp,
 		r = -ENOMEM;
 		if (!u.sregs2)
 			goto out;
-		__get_sregs2(vcpu, u.sregs2);
+		kvm_x86_vcpu_ioctl_get_sregs2(vcpu, u.sregs2);
 		r = -EFAULT;
 		if (copy_to_user(argp, u.sregs2, sizeof(struct kvm_sregs2)))
 			goto out;
@@ -6654,7 +6201,7 @@ long kvm_arch_vcpu_ioctl(struct file *filp,
 			u.sregs2 = NULL;
 			goto out;
 		}
-		r = __set_sregs2(vcpu, u.sregs2);
+		r = kvm_x86_vcpu_ioctl_set_sregs2(vcpu, u.sregs2);
 		break;
 	}
 	case KVM_HAS_DEVICE_ATTR:
@@ -12081,179 +11628,6 @@ int kvm_arch_vcpu_ioctl_run(struct kvm_vcpu *vcpu)
 	return r;
 }
 
-static void __get_regs(struct kvm_vcpu *vcpu, struct kvm_regs *regs)
-{
-	if (vcpu->arch.emulate_regs_need_sync_to_vcpu) {
-		/*
-		 * We are here if userspace calls get_regs() in the middle of
-		 * instruction emulation. Registers state needs to be copied
-		 * back from emulation context to vcpu. Userspace shouldn't do
-		 * that usually, but some bad designed PV devices (vmware
-		 * backdoor interface) need this to work
-		 */
-		emulator_writeback_register_cache(vcpu->arch.emulate_ctxt);
-		vcpu->arch.emulate_regs_need_sync_to_vcpu = false;
-	}
-	regs->rax = kvm_rax_read_raw(vcpu);
-	regs->rbx = kvm_rbx_read_raw(vcpu);
-	regs->rcx = kvm_rcx_read_raw(vcpu);
-	regs->rdx = kvm_rdx_read_raw(vcpu);
-	regs->rsi = kvm_rsi_read_raw(vcpu);
-	regs->rdi = kvm_rdi_read_raw(vcpu);
-	regs->rsp = kvm_rsp_read(vcpu);
-	regs->rbp = kvm_rbp_read_raw(vcpu);
-#ifdef CONFIG_X86_64
-	regs->r8 = kvm_r8_read_raw(vcpu);
-	regs->r9 = kvm_r9_read_raw(vcpu);
-	regs->r10 = kvm_r10_read_raw(vcpu);
-	regs->r11 = kvm_r11_read_raw(vcpu);
-	regs->r12 = kvm_r12_read_raw(vcpu);
-	regs->r13 = kvm_r13_read_raw(vcpu);
-	regs->r14 = kvm_r14_read_raw(vcpu);
-	regs->r15 = kvm_r15_read_raw(vcpu);
-#endif
-
-	regs->rip = kvm_rip_read(vcpu);
-	regs->rflags = kvm_get_rflags(vcpu);
-}
-
-int kvm_arch_vcpu_ioctl_get_regs(struct kvm_vcpu *vcpu, struct kvm_regs *regs)
-{
-	if (vcpu->kvm->arch.has_protected_state &&
-	    vcpu->arch.guest_state_protected)
-		return -EINVAL;
-
-	vcpu_load(vcpu);
-	__get_regs(vcpu, regs);
-	vcpu_put(vcpu);
-	return 0;
-}
-
-static void __set_regs(struct kvm_vcpu *vcpu, struct kvm_regs *regs)
-{
-	vcpu->arch.emulate_regs_need_sync_from_vcpu = true;
-	vcpu->arch.emulate_regs_need_sync_to_vcpu = false;
-
-	kvm_rax_write_raw(vcpu, regs->rax);
-	kvm_rbx_write_raw(vcpu, regs->rbx);
-	kvm_rcx_write_raw(vcpu, regs->rcx);
-	kvm_rdx_write_raw(vcpu, regs->rdx);
-	kvm_rsi_write_raw(vcpu, regs->rsi);
-	kvm_rdi_write_raw(vcpu, regs->rdi);
-	kvm_rsp_write(vcpu, regs->rsp);
-	kvm_rbp_write_raw(vcpu, regs->rbp);
-#ifdef CONFIG_X86_64
-	kvm_r8_write_raw(vcpu, regs->r8);
-	kvm_r9_write_raw(vcpu, regs->r9);
-	kvm_r10_write_raw(vcpu, regs->r10);
-	kvm_r11_write_raw(vcpu, regs->r11);
-	kvm_r12_write_raw(vcpu, regs->r12);
-	kvm_r13_write_raw(vcpu, regs->r13);
-	kvm_r14_write_raw(vcpu, regs->r14);
-	kvm_r15_write_raw(vcpu, regs->r15);
-#endif
-
-	kvm_rip_write(vcpu, regs->rip);
-	kvm_set_rflags(vcpu, regs->rflags | X86_EFLAGS_FIXED);
-
-	vcpu->arch.exception.pending = false;
-	vcpu->arch.exception_vmexit.pending = false;
-
-	kvm_make_request(KVM_REQ_EVENT, vcpu);
-}
-
-int kvm_arch_vcpu_ioctl_set_regs(struct kvm_vcpu *vcpu, struct kvm_regs *regs)
-{
-	if (vcpu->kvm->arch.has_protected_state &&
-	    vcpu->arch.guest_state_protected)
-		return -EINVAL;
-
-	vcpu_load(vcpu);
-	__set_regs(vcpu, regs);
-	vcpu_put(vcpu);
-	return 0;
-}
-
-static void __get_sregs_common(struct kvm_vcpu *vcpu, struct kvm_sregs *sregs)
-{
-	struct desc_ptr dt;
-
-	if (vcpu->arch.guest_state_protected)
-		goto skip_protected_regs;
-
-	kvm_handle_exception_payload_quirk(vcpu);
-
-	kvm_get_segment(vcpu, &sregs->cs, VCPU_SREG_CS);
-	kvm_get_segment(vcpu, &sregs->ds, VCPU_SREG_DS);
-	kvm_get_segment(vcpu, &sregs->es, VCPU_SREG_ES);
-	kvm_get_segment(vcpu, &sregs->fs, VCPU_SREG_FS);
-	kvm_get_segment(vcpu, &sregs->gs, VCPU_SREG_GS);
-	kvm_get_segment(vcpu, &sregs->ss, VCPU_SREG_SS);
-
-	kvm_get_segment(vcpu, &sregs->tr, VCPU_SREG_TR);
-	kvm_get_segment(vcpu, &sregs->ldt, VCPU_SREG_LDTR);
-
-	kvm_x86_call(get_idt)(vcpu, &dt);
-	sregs->idt.limit = dt.size;
-	sregs->idt.base = dt.address;
-	kvm_x86_call(get_gdt)(vcpu, &dt);
-	sregs->gdt.limit = dt.size;
-	sregs->gdt.base = dt.address;
-
-	sregs->cr2 = vcpu->arch.cr2;
-	sregs->cr3 = kvm_read_cr3(vcpu);
-
-skip_protected_regs:
-	sregs->cr0 = kvm_read_cr0(vcpu);
-	sregs->cr4 = kvm_read_cr4(vcpu);
-	sregs->cr8 = kvm_get_cr8(vcpu);
-	sregs->efer = vcpu->arch.efer;
-	sregs->apic_base = vcpu->arch.apic_base;
-}
-
-static void __get_sregs(struct kvm_vcpu *vcpu, struct kvm_sregs *sregs)
-{
-	__get_sregs_common(vcpu, sregs);
-
-	if (vcpu->arch.guest_state_protected)
-		return;
-
-	if (vcpu->arch.interrupt.injected && !vcpu->arch.interrupt.soft)
-		set_bit(vcpu->arch.interrupt.nr,
-			(unsigned long *)sregs->interrupt_bitmap);
-}
-
-static void __get_sregs2(struct kvm_vcpu *vcpu, struct kvm_sregs2 *sregs2)
-{
-	int i;
-
-	__get_sregs_common(vcpu, (struct kvm_sregs *)sregs2);
-
-	if (vcpu->arch.guest_state_protected)
-		return;
-
-	if (is_pae_paging(vcpu)) {
-		kvm_vcpu_srcu_read_lock(vcpu);
-		for (i = 0 ; i < 4 ; i++)
-			sregs2->pdptrs[i] = kvm_pdptr_read(vcpu, i);
-		sregs2->flags |= KVM_SREGS2_FLAGS_PDPTRS_VALID;
-		kvm_vcpu_srcu_read_unlock(vcpu);
-	}
-}
-
-int kvm_arch_vcpu_ioctl_get_sregs(struct kvm_vcpu *vcpu,
-				  struct kvm_sregs *sregs)
-{
-	if (vcpu->kvm->arch.has_protected_state &&
-	    vcpu->arch.guest_state_protected)
-		return -EINVAL;
-
-	vcpu_load(vcpu);
-	__get_sregs(vcpu, sregs);
-	vcpu_put(vcpu);
-	return 0;
-}
-
 int kvm_arch_vcpu_ioctl_get_mpstate(struct kvm_vcpu *vcpu,
 				    struct kvm_mp_state *mp_state)
 {
@@ -12373,175 +11747,6 @@ int kvm_task_switch(struct kvm_vcpu *vcpu, u16 tss_selector, int idt_index,
 }
 EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_task_switch);
 
-static bool kvm_is_valid_sregs(struct kvm_vcpu *vcpu, struct kvm_sregs *sregs)
-{
-	if ((sregs->efer & EFER_LME) && (sregs->cr0 & X86_CR0_PG)) {
-		/*
-		 * When EFER.LME and CR0.PG are set, the processor is in
-		 * 64-bit mode (though maybe in a 32-bit code segment).
-		 * CR4.PAE and EFER.LMA must be set.
-		 */
-		if (!(sregs->cr4 & X86_CR4_PAE) || !(sregs->efer & EFER_LMA))
-			return false;
-		if (!kvm_vcpu_is_legal_cr3(vcpu, sregs->cr3))
-			return false;
-	} else {
-		/*
-		 * Not in 64-bit mode: EFER.LMA is clear and the code
-		 * segment cannot be 64-bit.
-		 */
-		if (sregs->efer & EFER_LMA || sregs->cs.l)
-			return false;
-	}
-
-	return kvm_is_valid_cr4(vcpu, sregs->cr4) &&
-	       kvm_is_valid_cr0(vcpu, sregs->cr0);
-}
-
-static int __set_sregs_common(struct kvm_vcpu *vcpu, struct kvm_sregs *sregs,
-		int *mmu_reset_needed, bool update_pdptrs)
-{
-	int idx;
-	struct desc_ptr dt;
-
-	if (!kvm_is_valid_sregs(vcpu, sregs))
-		return -EINVAL;
-
-	if (kvm_apic_set_base(vcpu, sregs->apic_base, true))
-		return -EINVAL;
-
-	if (vcpu->arch.guest_state_protected)
-		return 0;
-
-	dt.size = sregs->idt.limit;
-	dt.address = sregs->idt.base;
-	kvm_x86_call(set_idt)(vcpu, &dt);
-	dt.size = sregs->gdt.limit;
-	dt.address = sregs->gdt.base;
-	kvm_x86_call(set_gdt)(vcpu, &dt);
-
-	vcpu->arch.cr2 = sregs->cr2;
-	*mmu_reset_needed |= kvm_read_cr3(vcpu) != sregs->cr3;
-	vcpu->arch.cr3 = sregs->cr3;
-	kvm_register_mark_dirty(vcpu, VCPU_REG_CR3);
-	kvm_x86_call(post_set_cr3)(vcpu, sregs->cr3);
-
-	kvm_set_cr8(vcpu, sregs->cr8);
-
-	*mmu_reset_needed |= vcpu->arch.efer != sregs->efer;
-	kvm_x86_call(set_efer)(vcpu, sregs->efer);
-
-	*mmu_reset_needed |= kvm_read_cr0(vcpu) != sregs->cr0;
-	kvm_x86_call(set_cr0)(vcpu, sregs->cr0);
-
-	*mmu_reset_needed |= kvm_read_cr4(vcpu) != sregs->cr4;
-	kvm_x86_call(set_cr4)(vcpu, sregs->cr4);
-
-	if (update_pdptrs) {
-		idx = srcu_read_lock(&vcpu->kvm->srcu);
-		if (is_pae_paging(vcpu)) {
-			load_pdptrs(vcpu, kvm_read_cr3(vcpu));
-			*mmu_reset_needed = 1;
-		}
-		srcu_read_unlock(&vcpu->kvm->srcu, idx);
-	}
-
-	kvm_set_segment(vcpu, &sregs->cs, VCPU_SREG_CS);
-	kvm_set_segment(vcpu, &sregs->ds, VCPU_SREG_DS);
-	kvm_set_segment(vcpu, &sregs->es, VCPU_SREG_ES);
-	kvm_set_segment(vcpu, &sregs->fs, VCPU_SREG_FS);
-	kvm_set_segment(vcpu, &sregs->gs, VCPU_SREG_GS);
-	kvm_set_segment(vcpu, &sregs->ss, VCPU_SREG_SS);
-
-	kvm_set_segment(vcpu, &sregs->tr, VCPU_SREG_TR);
-	kvm_set_segment(vcpu, &sregs->ldt, VCPU_SREG_LDTR);
-
-	kvm_lapic_update_cr8_intercept(vcpu);
-
-	/* Older userspace won't unhalt the vcpu on reset. */
-	if (kvm_vcpu_is_bsp(vcpu) && kvm_rip_read(vcpu) == 0xfff0 &&
-	    sregs->cs.selector == 0xf000 && sregs->cs.base == 0xffff0000 &&
-	    !is_protmode(vcpu))
-		kvm_set_mp_state(vcpu, KVM_MP_STATE_RUNNABLE);
-
-	return 0;
-}
-
-static int __set_sregs(struct kvm_vcpu *vcpu, struct kvm_sregs *sregs)
-{
-	int pending_vec, max_bits;
-	int mmu_reset_needed = 0;
-	int ret = __set_sregs_common(vcpu, sregs, &mmu_reset_needed, true);
-
-	if (ret)
-		return ret;
-
-	if (mmu_reset_needed) {
-		kvm_mmu_reset_context(vcpu);
-		kvm_make_request(KVM_REQ_TLB_FLUSH_GUEST, vcpu);
-	}
-
-	max_bits = KVM_NR_INTERRUPTS;
-	pending_vec = find_first_bit(
-		(const unsigned long *)sregs->interrupt_bitmap, max_bits);
-
-	if (pending_vec < max_bits) {
-		kvm_queue_interrupt(vcpu, pending_vec, false);
-		pr_debug("Set back pending irq %d\n", pending_vec);
-		kvm_make_request(KVM_REQ_EVENT, vcpu);
-	}
-	return 0;
-}
-
-static int __set_sregs2(struct kvm_vcpu *vcpu, struct kvm_sregs2 *sregs2)
-{
-	int mmu_reset_needed = 0;
-	bool valid_pdptrs = sregs2->flags & KVM_SREGS2_FLAGS_PDPTRS_VALID;
-	bool pae = (sregs2->cr0 & X86_CR0_PG) && (sregs2->cr4 & X86_CR4_PAE) &&
-		!(sregs2->efer & EFER_LMA);
-	int i, ret;
-
-	if (sregs2->flags & ~KVM_SREGS2_FLAGS_PDPTRS_VALID)
-		return -EINVAL;
-
-	if (valid_pdptrs && (!pae || vcpu->arch.guest_state_protected))
-		return -EINVAL;
-
-	ret = __set_sregs_common(vcpu, (struct kvm_sregs *)sregs2,
-				 &mmu_reset_needed, !valid_pdptrs);
-	if (ret)
-		return ret;
-
-	if (valid_pdptrs) {
-		for (i = 0; i < 4 ; i++)
-			kvm_pdptr_write(vcpu, i, sregs2->pdptrs[i]);
-
-		kvm_register_mark_dirty(vcpu, VCPU_REG_PDPTR);
-		mmu_reset_needed = 1;
-		vcpu->arch.pdptrs_from_userspace = true;
-	}
-	if (mmu_reset_needed) {
-		kvm_mmu_reset_context(vcpu);
-		kvm_make_request(KVM_REQ_TLB_FLUSH_GUEST, vcpu);
-	}
-	return 0;
-}
-
-int kvm_arch_vcpu_ioctl_set_sregs(struct kvm_vcpu *vcpu,
-				  struct kvm_sregs *sregs)
-{
-	int ret;
-
-	if (vcpu->kvm->arch.has_protected_state &&
-	    vcpu->arch.guest_state_protected)
-		return -EINVAL;
-
-	vcpu_load(vcpu);
-	ret = __set_sregs(vcpu, sregs);
-	vcpu_put(vcpu);
-	return ret;
-}
-
 static void kvm_arch_vcpu_guestdbg_update_apicv_inhibit(struct kvm *kvm)
 {
 	bool set = false;
@@ -12699,11 +11904,7 @@ static void store_regs(struct kvm_vcpu *vcpu)
 {
 	BUILD_BUG_ON(sizeof(struct kvm_sync_regs) > SYNC_REGS_SIZE_BYTES);
 
-	if (vcpu->run->kvm_valid_regs & KVM_SYNC_X86_REGS)
-		__get_regs(vcpu, &vcpu->run->s.regs.regs);
-
-	if (vcpu->run->kvm_valid_regs & KVM_SYNC_X86_SREGS)
-		__get_sregs(vcpu, &vcpu->run->s.regs.sregs);
+	kvm_run_get_regs(vcpu);
 
 	if (vcpu->run->kvm_valid_regs & KVM_SYNC_X86_EVENTS)
 		kvm_vcpu_ioctl_x86_get_vcpu_events(
@@ -12712,19 +11913,8 @@ static void store_regs(struct kvm_vcpu *vcpu)
 
 static int sync_regs(struct kvm_vcpu *vcpu)
 {
-	if (vcpu->run->kvm_dirty_regs & KVM_SYNC_X86_REGS) {
-		__set_regs(vcpu, &vcpu->run->s.regs.regs);
-		vcpu->run->kvm_dirty_regs &= ~KVM_SYNC_X86_REGS;
-	}
-
-	if (vcpu->run->kvm_dirty_regs & KVM_SYNC_X86_SREGS) {
-		struct kvm_sregs sregs = vcpu->run->s.regs.sregs;
-
-		if (__set_sregs(vcpu, &sregs))
-			return -EINVAL;
-
-		vcpu->run->kvm_dirty_regs &= ~KVM_SYNC_X86_SREGS;
-	}
+	if (kvm_run_set_regs(vcpu))
+		return -EINVAL;
 
 	if (vcpu->run->kvm_dirty_regs & KVM_SYNC_X86_EVENTS) {
 		struct kvm_vcpu_events events = vcpu->run->s.regs.events;
diff --git a/arch/x86/kvm/x86.h b/arch/x86/kvm/x86.h
index 185062a26924..fd55cd031b1c 100644
--- a/arch/x86/kvm/x86.h
+++ b/arch/x86/kvm/x86.h
@@ -414,6 +414,7 @@ int handle_ud(struct kvm_vcpu *vcpu);
 
 void kvm_deliver_exception_payload(struct kvm_vcpu *vcpu,
 				   struct kvm_queued_exception *ex);
+void kvm_handle_exception_payload_quirk(struct kvm_vcpu *vcpu);
 
 int kvm_mtrr_set_msr(struct kvm_vcpu *vcpu, u32 msr, u64 data);
 int kvm_mtrr_get_msr(struct kvm_vcpu *vcpu, u32 msr, u64 *pdata);
@@ -604,6 +605,7 @@ static inline void kvm_machine_check(void)
 int kvm_spec_ctrl_test_value(u64 value);
 int kvm_handle_memory_failure(struct kvm_vcpu *vcpu, int r,
 			      struct x86_exception *e);
+void kvm_invalidate_pcid(struct kvm_vcpu *vcpu, unsigned long pcid);
 int kvm_handle_invpcid(struct kvm_vcpu *vcpu, unsigned long type, gva_t gva);
 bool kvm_msr_allowed(struct kvm_vcpu *vcpu, u32 index, u32 type);

---

## [17] Yosry Ahmed — 2026-05-14
*Subject: Re: [PATCH v2 06/15] KVM: x86: Rename kvm_cache_regs.h => regs.h*

On Thu, May 14, 2026 at 2:54 PM Sean Christopherson <seanjc@google.com> wrote:
>
> Rename kvm_cache_regs.h to simply regs.h, as the "cache" nomenclature is

Reviewed-by: Yosry Ahmed <yosry@kernel.org>

---

## [18] Yosry Ahmed — 2026-05-14
*Subject: Re: [PATCH v2 07/15] KVM: x86: Move inlined CR and DR helpers from
 x86.h to regs.h*

On Thu, May 14, 2026 at 2:54 PM Sean Christopherson <seanjc@google.com> wrote:
>
> Move inlined Control Register and Debug Register helpers from x86.h to the

This is really stretching the meaning of 'regs', but it's not that
much worse than 'x86'..

Reviewed-by: Yosry Ahmed <yosry@kernel.org>

---

## [19] Yosry Ahmed — 2026-05-14
*Subject: Re: [PATCH v2 00/15] KVM: x86: Clean up kvm_<reg>_{read,write}() mess*

On Thu, May 14, 2026 at 2:54 PM Sean Christopherson <seanjc@google.com> wrote:
>
> Add proper, explicit "raw" versions of kvm_<reg>_{read,write}(), along

This is kinda sorta the opposite of what I suggested, but sure :P

---

## [20] Binbin Wu — 2026-05-15
*Subject: Re: [PATCH v2 01/15] KVM: SVM: Truncate INVLPGA address in
 compatibility mode*

On 5/15/2026 5:53 AM, Sean Christopherson wrote:
> Check for full 64-bit mode, not just long mode, when truncating the
> virtual address as part of INVLPGA emulation.  Compatibility mode doesn't
                                                                        ^
an extra 'a'

> an entirely different can of worms, and in practice no sane guest would
> shove garbage into RAX[63:32] and execute INVLPGA.
                                                              ^
                                                          their      > with respect to rAX is otherwise identical).
> 
> Fixes: bc9eff67fc35 ("KVM: SVM: Use default rAX size for INVLPGA emulation")

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

> ---
>  arch/x86/kvm/svm/svm.c | 2 +-

---

## [21] Binbin Wu — 2026-05-15
*Subject: Re: [PATCH v2 02/15] KVM: x86/xen: Bug the VM if 32-bit KVM observes
 a 64-bit mode hypercall*

On 5/15/2026 5:53 AM, Sean Christopherson wrote:
> Bug the VM if 32-bit KVM attempts to handle a 64-bit hypercall, primarily
> so that a future change to set "input" in mode-specific code doesn't

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

> ---
>  arch/x86/kvm/xen.c | 7 +++++--

---

## [22] Binbin Wu — 2026-05-15
*Subject: Re: [PATCH v2 03/15] KVM: x86/xen: Don't truncate RAX when handling
 hypercall from protected guest*

On 5/15/2026 5:53 AM, Sean Christopherson wrote:
> Don't truncate RAX when handling a Xen hypercall for a guest with protected
> state, as KVM's ABI is to assume the guest is in 64-bit for such cases

The patch looks good to me, but one question below.

> ---
>  arch/x86/kvm/xen.c | 6 +++---

Is the variable name misleading?
If the vcpu is in compatible mode (when guest state is not protected),
it's in long mode, but the code goes to !longmode path.

>  	if (!longmode) {
> +		input = (u32)kvm_rax_read(vcpu);

---

## [23] Binbin Wu — 2026-05-15
*Subject: Re: [PATCH v2 04/15] KVM: VMX: Read 32-bit GPR values for ENCLS
 instructions outside of 64-bit mode*

On 5/15/2026 5:53 AM, Sean Christopherson wrote:
> When getting register values for ENCLS emulation, use kvm_register_read()
> instead of kvm_<reg>_read() so that bits 63:32 of the register are dropped

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

> ---
>  arch/x86/kvm/vmx/sgx.c | 10 +++++-----

---

## [24] Binbin Wu — 2026-05-15
*Subject: Re: [PATCH v2 05/15] KVM: x86: Trace hypercall register *after*
 truncating values for 32-bit*

On 5/15/2026 5:53 AM, Sean Christopherson wrote:
> When tracing hypercalls, invoke the tracepoint *after* truncating the
> register values for 32-bit guests so as not to record unused garbage (in

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

> ---
>  arch/x86/kvm/x86.c | 4 ++--

---

## [25] Binbin Wu — 2026-05-15
*Subject: Re: [PATCH v2 06/15] KVM: x86: Rename kvm_cache_regs.h => regs.h*

On 5/15/2026 5:53 AM, Sean Christopherson wrote:
> Rename kvm_cache_regs.h to simply regs.h, as the "cache" nomenclature is
> already a lie (the file deals with state/registers that aren't cached per

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

---

## [26] Binbin Wu — 2026-05-15
*Subject: Re: [PATCH v2 07/15] KVM: x86: Move inlined CR and DR helpers from
 x86.h to regs.h*

On 5/15/2026 5:53 AM, Sean Christopherson wrote:
> Move inlined Control Register and Debug Register helpers from x86.h to the
> aptly named regs.h, to help trim down x86.h (and x86.c in the future).
                                                                    ^
                                                                   it

> far more in common with CR4 than it does with any MSR.
> 

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

Nit: The shortlog doesn't cover EFER.

---

## [27] Binbin Wu — 2026-05-15
*Subject: Re: [PATCH v2 08/15] KVM: x86: Add mode-aware versions of
 kvm_<reg>_{read,write}() helpers*

On 5/15/2026 5:53 AM, Sean Christopherson wrote:
> Make kvm_<reg>_{read,write}() mode-aware (where the value is truncated to
> 32 bits if the vCPU isn't in 64-bit mode), and convert all the intentional
   ^
  double "only"

> 
> No functional change intended (all use of "e" versions is for cases where
Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

---

## [28] Binbin Wu — 2026-05-15
*Subject: Re: [PATCH v2 09/15] KVM: x86: Drop non-raw kvm_<reg>_write() helpers*

On 5/15/2026 5:53 AM, Sean Christopherson wrote:
> Drop the non-raw, mode-aware kvm_<reg>_write() helpers as there is no
> usage in KVM, and in all likelihood there will never be usage in KVM as

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

> ---
>  arch/x86/kvm/regs.h | 5 -----

---

## [29] Binbin Wu — 2026-05-15
*Subject: Re: [PATCH v2 11/15] Revert "KVM: VMX: Read 32-bit GPR values for
 ENCLS instructions outside of 64-bit mode"*

On 5/15/2026 5:53 AM, Sean Christopherson wrote:
> Now that kvm_<reg>_read() are mode aware, i.e. are functionally equivalent
> to kvm_register_read(), revert aback to the less verbose versions.

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

> ---
>  arch/x86/kvm/vmx/sgx.c | 10 +++++-----

---

## [30] Binbin Wu — 2026-05-15
*Subject: Re: [PATCH v2 12/15] KVM: x86: Harden is_64_bit_hypercall() against
 bugs on 32-bit kernels*

On 5/15/2026 5:53 AM, Sean Christopherson wrote:
> Unconditionally return %false for is_64_bit_hypercall() on 32-bit kernels
> to guard against incorrectly setting guest_state_protected, and because

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

> ---
>  arch/x86/kvm/regs.h | 4 ++++

---

## [31] Sean Christopherson — 2026-05-15
*Subject: Re: [PATCH v2 03/15] KVM: x86/xen: Don't truncate RAX when handling
 hypercall from protected guest*

On Fri, May 15, 2026, Binbin Wu wrote:
> 
> 

It most definitely is.  However, @longmode is passed around quite a few locations
in xen.c, and so I don't want to opportunistically fix this one variable.  Though
I'm definitely not opposed to a separate patch to rename them all to is_64bit or
something.

> If the vcpu is in compatible mode (when guest state is not protected),
> it's in long mode, but the code goes to !longmode path.

---

## [32] Binbin Wu — 2026-05-18
*Subject: Re: [PATCH v2 03/15] KVM: x86/xen: Don't truncate RAX when handling
 hypercall from protected guest*

On 5/15/2026 8:55 PM, Sean Christopherson wrote:
> On Fri, May 15, 2026, Binbin Wu wrote:
>>

OK, I can do it.

> 
>> If the vcpu is in compatible mode (when guest state is not protected),

---

## [33] David Woodhouse — 2026-05-18
*Subject: Re: [PATCH v2 03/15] KVM: x86/xen: Don't truncate RAX when handling
 hypercall from protected guest*

On Mon, 2026-05-18 at 10:19 +0800, Binbin Wu wrote:
>  
> > > >   	longmode = is_64_bit_hypercall(vcpu);

This one (as shown above) is clearly indicating whether this particular
vCPU is in 64-bit mode for this particular hypercall. Changing that to
is_64bit makes sense.

However, there is a separate overall mode for the VM, which is stored
in 'kvm->arch.xen.long_mode' and accessed by userspace using the
KVM_XEN_ATTR_TYPE_LONG_MODE attribute. It affects the datatypes used by
shared memory data structures, and is also latched by the kernel when
the guest writes the MSR for the hypercall page. That one should
probably keep its name.

---

## [34] Binbin Wu — 2026-05-18
*Subject: Re: [PATCH v2 03/15] KVM: x86/xen: Don't truncate RAX when handling
 hypercall from protected guest*

On 5/18/2026 3:15 PM, David Woodhouse wrote:
> On Mon, 2026-05-18 at 10:19 +0800, Binbin Wu wrote:
>>  

For this one, I think the current KVM code is consistent.
The format is determined by EFER.LMA, whether the guest is running in 64 bit or
compatible mode doesn't change the ABI.

struct compat_shared_info is used only when the guest is running natively in a
32-bit build.

> 
>

---

## [35] David Woodhouse — 2026-05-18
*Subject: Re: [PATCH v2 03/15] KVM: x86/xen: Don't truncate RAX when handling
 hypercall from protected guest*

On Mon, 2026-05-18 at 17:43 +0800, Binbin Wu wrote:
> 
> 

Agreed. For the hypercall case you're looking at, switching the name to
is_64bit makes sense.

> struct compat_shared_info is used only when the guest is running natively in a
> 32-bit build.

The struct compat_shared_info is also used in !kvm->arch.xen.long_mode
on a 64-bit host, as that's what means the guest is considered to be a
32-bit guest.

It's somewhat orthogonal from whether any given vCPU is making any
given hypercall while in 64-bit mode. The 'long_mode' is *latched* at
certain specific times which are defined by Xen's historical behaviour.

I'm suggesting that you clean up longmode→is_64bit for the *hypercalls*
but leave 'long_mode' as is.

---

## [36] Binbin Wu — 2026-05-18
*Subject: Re: [PATCH v2 03/15] KVM: x86/xen: Don't truncate RAX when handling
 hypercall from protected guest*

On 5/18/2026 5:50 PM, David Woodhouse wrote:
> On Mon, 2026-05-18 at 17:43 +0800, Binbin Wu wrote:
>>

Yes, will only do it for is_64_bit_hypercall().

>

---

## [37] Huang, Kai — 2026-05-18
*Subject: Re: [PATCH v2 08/15] KVM: x86: Add mode-aware versions of
 kvm_<reg>_{read,write}() helpers*

> @@ -10413,29 +10413,30 @@ static int complete_hypercall_exit(struct kvm_vcpu *vcpu)
>  

Nit:  AFAICT if we use kvm_rax_write(vcpu, ret) instead of the "raw" version
here, we can then remove the

	if (!is_64_bit_hypercall(vcpu))
		ret = (u32)ret;

But I saw in your next patch you are going to remove the non-raw write helpers.

---

## [38] Sean Christopherson — 2026-05-18
*Subject: Re: [PATCH v2 08/15] KVM: x86: Add mode-aware versions of
 kvm_<reg>_{read,write}() helpers*

On Mon, May 18, 2026, Kai Huang wrote:
> 
> > @@ -10413,29 +10413,30 @@ static int complete_hypercall_exit(struct kvm_vcpu *vcpu)

No, because sneakily, is_64_bit_hypercall() != is_64_bit_mode(vcpu).  And because
we also need to avoid calling is_64_bit_mode().  If we use kvm_rax_write(), then
the unpacked code will be:

	WARN_ON_ONCE(vcpu->arch.guest_state_protected);

	if (is_long_mode(vcpu))
		kvm_x86_call(get_cs_db_l_bits)(vcpu, &cs_db, &cs_l);
	else
		cs_l = 0;

	if (cs_l)
		vcpu->arch.regs[VCPU_REGS_RAX] = ret;
	else	
		vcpu->arch.regs[VCPU_REGS_RAX] = (u32)ret;

whereas the (correct) behavior here is:

	if (vcpu->arch.guest_state_protected)
		cs_l = 1;
	else if (is_long_mode(vcpu))
		kvm_x86_call(get_cs_db_l_bits)(vcpu, &cs_db, &cs_l);
	else
		cs_l = 0;

	if (cs_l)
		vcpu->arch.regs[VCPU_REGS_RAX] = ret;
	else	
		vcpu->arch.regs[VCPU_REGS_RAX] = (u32)ret;

I.e. using the non-raw version will trigger the WARN_ON_ONCE(), and will incorrectly
truncate "ret" whenever cs_l is stale (which might be always?).

---

## [39] Huang, Kai — 2026-05-18
*Subject: Re: [PATCH v2 08/15] KVM: x86: Add mode-aware versions of
 kvm_<reg>_{read,write}() helpers*

On Mon, 2026-05-18 at 13:51 -0700, Sean Christopherson wrote:
> On Mon, May 18, 2026, Kai Huang wrote:
> > 

Oh I missed this :-(  sorry for the noise.

---

## [40] Huang, Kai — 2026-05-18
*Subject: Re: [PATCH v2 08/15] KVM: x86: Add mode-aware versions of
 kvm_<reg>_{read,write}() helpers*

On Mon, 2026-05-18 at 13:51 -0700, Sean Christopherson wrote:
> On Mon, May 18, 2026, Kai Huang wrote:
> > 

FWIW, I sanity tested that booting/destroying both TD and VMX guests worked
fine.  I have no environment to test SVM and Xen related parts, though.

---

## [41] Huang, Kai — 2026-05-19
*Subject: Re: [PATCH v2 15/15] KVM: x86: Move the bulk of register specific
 code from x86.c to regs.c*

> +void kvm_run_get_regs(struct kvm_vcpu *vcpu)
> +{

[...]

> @@ -12699,11 +11904,7 @@ static void store_regs(struct kvm_vcpu *vcpu)
>  {

Nit:

Do you think 'kvm_run_sync_regs()' is better than 'kvm_run_set_regs()'?

Because I think "sync" reflects better that vcpu->run->kvm_dirty_regs is cleared
after the "set" operation.

>  
>  	if (vcpu->run->kvm_dirty_regs & KVM_SYNC_X86_EVENTS) {

Also, I wonder whether it's better to add a helper for events so sync_regs() and
store_regs() can be simplified to:

static int sync_regs(struct kvm_vcpu *vcpu)
{
	if (kvm_run_sync_regs(vcpu))
		return -EINVAL;
	return kvm_run_sync_events(vcpu);
}

static void store_regs(struct kvm_vcpu *vcpu)
{
	kvm_run_get_regs(vcpu);
	kvm_run_get_events(vcpu);
}

And maybe 'kvm_run_get_regs()' could be 'kvm_run_store_regs()' too , so that the
store_regs() could be:

static void store_regs(struct kvm_vcpu *vcpu)
{
	kvm_run_store_regs(vcpu);
	kvm_run_store_events(vcpu);
}

> diff --git a/arch/x86/kvm/x86.h b/arch/x86/kvm/x86.h
> index 185062a26924..fd55cd031b1c 100644

If I read correct, this is because "regs.c" calls kvm_invalidate_pcid() but you
want to keep it in x86.c.  But it seems the "x86.h" isn't included by "regs.c"
directly but via other headers ("mmu.h" does include "x86.h").

Should the "regs.c" include "x86.h" directly?

Btw, I am a bit confused the relationship between "x86.h" and other headers like
"mmu.h" and the new "regs.h".  That is, headers like "mmu.h" include "x86.h",
but headers like "regs.h" do not (instead, "x86.h" includes them).

---

## [42] Sean Christopherson — 2026-05-19
*Subject: Re: [PATCH v2 15/15] KVM: x86: Move the bulk of register specific
 code from x86.c to regs.c*

On Tue, May 19, 2026, Kai Huang wrote:
> > @@ -12712,19 +11913,8 @@ static void store_regs(struct kvm_vcpu *vcpu)
> >  

The problem I have with "sync" is that it doesn't communicate the direction of
the sync.  What about kvm_run_sync_regs_{to,from}_user()?

> >  
> >  	if (vcpu->run->kvm_dirty_regs & KVM_SYNC_X86_EVENTS) {

{store,sync}_regs() look pretty, but IMO the overall code is uglier because we
end up with super small helpers that have one caller, e.g.

  static void kvm_run_sync_events_to_user(struct kvm_vcpu *vcpu)
  {
	if (vcpu->run->kvm_valid_regs & KVM_SYNC_X86_EVENTS)
		kvm_vcpu_ioctl_x86_get_vcpu_events(vcpu, &vcpu->run->s.regs.events);
  }

  static void store_regs(struct kvm_vcpu *vcpu)
  {
	BUILD_BUG_ON(sizeof(struct kvm_sync_regs) > SYNC_REGS_SIZE_BYTES);

	kvm_run_sync_regs_to_user(vcpu);
	kvm_run_sync_events_to_user(vcpu);
  }

For me, the extra "jump" is undesirable, but it allows burying __{g,s}et_{s,}regs()
in regs.c, and so is a net positive for registers.  But for events, it's pure
overhead.

> > diff --git a/arch/x86/kvm/x86.h b/arch/x86/kvm/x86.h
> > index 185062a26924..fd55cd031b1c 100644

Oh, yeah, I just goofed that.

> Btw, I am a bit confused the relationship between "x86.h" and other headers like
> "mmu.h" and the new "regs.h".  That is, headers like "mmu.h" include "x86.h",

Heh, don't look for a theme/plan, because there isn't one.  Over the years, x86.h
and x86.c became dumping grounds for everything that didn't have an obvious home,
and so there aren't real "rules".

Hmm, though looking at all of this again, I think we're actually quite close to
having somewhat sane rules.  Over the past few years, I've tried multiple times
to move what I felt should be KVM-internal structures from asm/kvm_host.h to x86.h,
and I've failed miserably every time because inevitably even the most innocuous
struct manages to have usage that leads to cyclical header dependencies and/or is
used by arch-neutral KVM code.

I think it's probably time to admit I've been looking at the asm/kvm_host.h vs.
x86.h split all wrong, i.e. finally give up on moving structures out of kvm_host.h,
and do the exact opposite: commit to using kvm_host.h to define and declare widely
used structures.

Because literally the only reason that x86.h doesn't include mmu.h is that mmu.h
references struct kvm_host, which is currently defined in x86.h.  If we "fix"
that, then (a) we can make x86.h the "central" include everyone expects it to be,
and (b) it can be the start of a cleanup of asm/kvm_host.h and a big step towards
defining maintainable "rules" for what goes where.  E.g. there are a pile of
functional declarations in asm/kvm_host.h that can live elsewhere; if we trim
those down, then the rules become:

  - asm/kvm_host.h holds "common" structure definitions and associated key global
    variables, and things that are referenced by arch-neutral KVM.
  - <area>.{c,h} holds relevant declarations and definitions.
  - x86.{c,h} is the kitchen sink for everything else.

E.g. this compiles for at least one config:

---
 arch/x86/include/asm/kvm_host.h | 50 ++++++++++++++++++++++++----
 arch/x86/kvm/mmu.h              | 20 +++++++----
 arch/x86/kvm/x86.h              | 59 ++++-----------------------------
 3 files changed, 64 insertions(+), 65 deletions(-)

diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h
index 5e24987b2a94..67ba8bf22469 100644
--- a/arch/x86/include/asm/kvm_host.h
+++ b/arch/x86/include/asm/kvm_host.h
@@ -313,6 +313,50 @@ enum x86_intercept_stage;
 struct kvm_kernel_irqfd;
 struct kvm_kernel_irq_routing_entry;
 
+struct kvm_caps {
+	/* control of guest tsc rate supported? */
+	bool has_tsc_control;
+	/* maximum supported tsc_khz for guests */
+	u32  max_guest_tsc_khz;
+	/* number of bits of the fractional part of the TSC scaling ratio */
+	u8   tsc_scaling_ratio_frac_bits;
+	/* maximum allowed value of TSC scaling ratio */
+	u64  max_tsc_scaling_ratio;
+	/* 1ull << kvm_caps.tsc_scaling_ratio_frac_bits */
+	u64  default_tsc_scaling_ratio;
+	/* bus lock detection supported? */
+	bool has_bus_lock_exit;
+	/* notify VM exit supported? */
+	bool has_notify_vmexit;
+	/* bit mask of VM types */
+	u32 supported_vm_types;
+
+	u64 supported_mce_cap;
+	u64 supported_xcr0;
+	u64 supported_xss;
+	u64 supported_perf_cap;
+
+	u64 supported_quirks;
+	u64 inapplicable_quirks;
+};
+extern struct kvm_caps kvm_caps;
+
+struct kvm_host_values {
+	/*
+	 * The host's raw MAXPHYADDR, i.e. the number of non-reserved physical
+	 * address bits irrespective of features that repurpose legal bits,
+	 * e.g. MKTME.
+	 */
+	u8 maxphyaddr;
+
+	u64 efer;
+	u64 xcr0;
+	u64 xss;
+	u64 s_cet;
+	u64 arch_capabilities;
+};
+extern struct kvm_host_values kvm_host;
+
 /*
  * kvm_mmu_page_role tracks the properties of a shadow page (where shadow page
  * also includes TDP pages) to determine whether or not a page can be used in
@@ -2056,10 +2100,6 @@ struct kvm_arch_async_pf {
 	u64 error_code;
 };
 
-extern u32 __read_mostly kvm_nr_uret_msrs;
-extern bool __read_mostly allow_smaller_maxphyaddr;
-extern bool __read_mostly enable_apicv;
-extern bool __read_mostly enable_ipiv;
 extern bool __read_mostly enable_device_posted_irqs;
 extern struct kvm_x86_ops kvm_x86_ops;
 
@@ -2151,8 +2191,6 @@ void kvm_zap_gfn_range(struct kvm *kvm, gfn_t gfn_start, gfn_t gfn_end);
 
 int load_pdptrs(struct kvm_vcpu *vcpu, unsigned long cr3);
 
-extern bool tdp_enabled;
-
 u64 vcpu_tsc_khz(struct kvm_vcpu *vcpu);
 
 /*
diff --git a/arch/x86/kvm/mmu.h b/arch/x86/kvm/mmu.h
index e1bb663ebbd5..d841a4f486d1 100644
--- a/arch/x86/kvm/mmu.h
+++ b/arch/x86/kvm/mmu.h
@@ -4,9 +4,14 @@
 
 #include <linux/kvm_host.h>
 #include "regs.h"
-#include "x86.h"
 #include "cpuid.h"
 
+extern bool tdp_enabled;
+#ifdef CONFIG_X86_64
+extern bool tdp_mmu_enabled;
+#else
+#define tdp_mmu_enabled false
+#endif
 extern bool __read_mostly enable_mmio_caching;
 
 #define PT_WRITABLE_SHIFT 1
@@ -261,14 +266,10 @@ static inline bool kvm_shadow_root_allocated(struct kvm *kvm)
 	return smp_load_acquire(&kvm->arch.shadow_root_allocated);
 }
 
-#ifdef CONFIG_X86_64
-extern bool tdp_mmu_enabled;
-#else
-#define tdp_mmu_enabled false
-#endif
-
 int kvm_tdp_mmu_map_private_pfn(struct kvm_vcpu *vcpu, gfn_t gfn, kvm_pfn_t pfn);
 
+bool kvm_mmu_is_mappable_memslot(const struct kvm_memory_slot *slot);
+
 static inline bool kvm_memslots_have_rmaps(struct kvm *kvm)
 {
 	return !tdp_mmu_enabled || kvm_shadow_root_allocated(kvm);
@@ -300,6 +301,11 @@ static inline void kvm_update_page_stats(struct kvm *kvm, int level, int count)
 	atomic64_add(count, &kvm->stat.pages[level - 1]);
 }
 
+static inline bool mmu_is_nested(struct kvm_vcpu *vcpu)
+{
+	return vcpu->arch.walk_mmu == &vcpu->arch.nested_mmu;
+}
+
 static inline gpa_t kvm_translate_gpa(struct kvm_vcpu *vcpu,
 				      struct kvm_mmu *mmu,
 				      gpa_t gpa, u64 access,
diff --git a/arch/x86/kvm/x86.h b/arch/x86/kvm/x86.h
index fd55cd031b1c..40c6f4c54f8e 100644
--- a/arch/x86/kvm/x86.h
+++ b/arch/x86/kvm/x86.h
@@ -6,53 +6,19 @@
 #include <asm/fpu/xstate.h>
 #include <asm/mce.h>
 #include <asm/pvclock.h>
+#include "mmu.h"
 #include "regs.h"
 #include "kvm_emulate.h"
 #include "cpuid.h"
 
 #define KVM_MAX_MCE_BANKS 32
 
-struct kvm_caps {
-	/* control of guest tsc rate supported? */
-	bool has_tsc_control;
-	/* maximum supported tsc_khz for guests */
-	u32  max_guest_tsc_khz;
-	/* number of bits of the fractional part of the TSC scaling ratio */
-	u8   tsc_scaling_ratio_frac_bits;
-	/* maximum allowed value of TSC scaling ratio */
-	u64  max_tsc_scaling_ratio;
-	/* 1ull << kvm_caps.tsc_scaling_ratio_frac_bits */
-	u64  default_tsc_scaling_ratio;
-	/* bus lock detection supported? */
-	bool has_bus_lock_exit;
-	/* notify VM exit supported? */
-	bool has_notify_vmexit;
-	/* bit mask of VM types */
-	u32 supported_vm_types;
-
-	u64 supported_mce_cap;
-	u64 supported_xcr0;
-	u64 supported_xss;
-	u64 supported_perf_cap;
-
-	u64 supported_quirks;
-	u64 inapplicable_quirks;
-};
-
-struct kvm_host_values {
-	/*
-	 * The host's raw MAXPHYADDR, i.e. the number of non-reserved physical
-	 * address bits irrespective of features that repurpose legal bits,
-	 * e.g. MKTME.
-	 */
-	u8 maxphyaddr;
-
-	u64 efer;
-	u64 xcr0;
-	u64 xss;
-	u64 s_cet;
-	u64 arch_capabilities;
-};
+extern u32 __read_mostly kvm_nr_uret_msrs;
+extern bool __read_mostly allow_smaller_maxphyaddr;
+extern bool __read_mostly enable_apicv;
+extern bool __read_mostly enable_ipiv;
+extern bool enable_pmu;
+extern bool enable_mediated_pmu;
 
 void kvm_spurious_fault(void);
 
@@ -252,11 +218,6 @@ static inline bool x86_exception_has_error_code(unsigned int vector)
 	return (1U << vector) & exception_has_error_code;
 }
 
-static inline bool mmu_is_nested(struct kvm_vcpu *vcpu)
-{
-	return vcpu->arch.walk_mmu == &vcpu->arch.nested_mmu;
-}
-
 static inline u8 vcpu_virt_addr_bits(struct kvm_vcpu *vcpu)
 {
 	return kvm_is_cr4_bit_set(vcpu, X86_CR4_LA57) ? 57 : 48;
@@ -428,12 +389,6 @@ fastpath_t handle_fastpath_wrmsr_imm(struct kvm_vcpu *vcpu, u32 msr, int reg);
 fastpath_t handle_fastpath_hlt(struct kvm_vcpu *vcpu);
 fastpath_t handle_fastpath_invd(struct kvm_vcpu *vcpu);
 
-extern struct kvm_caps kvm_caps;
-extern struct kvm_host_values kvm_host;
-
-extern bool enable_pmu;
-extern bool enable_mediated_pmu;
-
 void kvm_setup_xss_caps(void);
 
 /*

base-commit: b99808a11a42edc2cecced7adf57c2ac231bdb68
--

---

## [43] Huang, Kai — 2026-05-20
*Subject: Re: [PATCH v2 15/15] KVM: x86: Move the bulk of register specific
 code from x86.c to regs.c*

On Tue, 2026-05-19 at 08:04 -0700, Sean Christopherson wrote:
> On Tue, May 19, 2026, Kai Huang wrote:
> > > @@ -12712,19 +11913,8 @@ static void store_regs(struct kvm_vcpu *vcpu)

Yeah that's better to me too.

> 
> > >  

Sure.

Just wondering is it possible we might want to move events handling to some
other C file since you are cleanup x86.c?  But we can deal with this when it
happens.

> 
> > > diff --git a/arch/x86/kvm/x86.h b/arch/x86/kvm/x86.h

My guess too.

> 
> Hmm, though looking at all of this again, I think we're actually quite close to

The problem is some other kernel code includes <linux/kvm_host.h> (which in turn
includes <asm/kvm_host.h>) but the KVM internal structures have nothing to do
with them.

E.g., some drivers are using <linux/kvm_host.h>:

#$ grep kvm_host.h drivers/ -Rn
drivers/vfio/pci/vfio_pci_zdev.c:14:#include <linux/kvm_host.h>
drivers/vfio/vfio_main.c:20:#include <linux/kvm_host.h>
drivers/firmware/arm_sdei.c:19:#include <linux/kvm_host.h>
drivers/hwtracing/coresight/coresight-trbe.c:20:#include <linux/kvm_host.h>
drivers/hwtracing/coresight/coresight-etm4x-core.c:10:#include
<linux/kvm_host.h>
drivers/s390/crypto/vfio_ap_ops.c:17:#include <linux/kvm_host.h>
drivers/s390/crypto/vfio_ap_private.h:20:#include <linux/kvm_host.h>

But looking at them, AFAICT what they need is only some structure declarations
(e.g., 'struct kvm;') for type safety (plus some function declarations), but
don't actually need to see the actual structure.

For x86, AFAICT there's (only) "arch/x86/events/intel/core.c" actually uses the
'struct kvm_pmu', though.  I haven't checked other ARCHs whether there's cases
actually need to use any structure.

> 
> I think it's probably time to admit I've been looking at the asm/kvm_host.h vs.

If the structure(s) are only used within arch/x86/kvm/, it doesn't seem right to
define them in asm/kvm_host.h?

> 
> Because literally the only reason that x86.h doesn't include mmu.h is that mmu.h

Yes. But I wouldn't worry about this too much since it's a small thing we can
always find a way to fix.  E.g., we can move kvm_mmu_max_gfn() out of "mmu.h"
(with a renaming perhaps).

> If we "fix"
> that, then (a) we can make x86.h the "central" include everyone expects it to be,

It's a bit weird the arch-neutral KVM code needs to reference variables in
asm/kvm_host.h, and I am afraid the "common" structure definitions will
effectively be a lot of structures only used by arch/x86/kvm/.  

Which isn't necessarily a bad thing, from the perspective we might finally clean
this up by a giant move.

E.g., <linux/kvm_types.h> is already used by other kernel components where they
don't need <linux/kvm_host.h>.  Ideally, maybe eventually we can use
<linux/kvm_types.h> and <asm/kvm_types.h> for things needed by other kernel
components, or keep <linux/kvm_host.h> and <asm/kvm_host.h> minimal after moving
majority things to some KVM internal headers.

E.g., maybe:

  virt/kvm/include/kvm_host.h
  arch/x86/kvm/kvm_host.h (can even be merged to x86.h)

I think the problem is "struct kvm_arch" and "struct kvm_vcpu_arch", that they
are not a pointer but a fully embedded structure in "struct kvm" and "struct
kvm_vcpu" respectively.  That caused that you need to keep the actual structure
definition of "struct kvm_arch" and "kvm_vcpu_arch" in asm/kvm_host.h, which in
turns makes a lot of structures only used by arch/x86/kvm/ need to stay in
asm/kvm_host.h.

I am not sure whether there's a mandatory requirement that "struct kvm_arch" and
"struct kvm_vcpu_arch" must be fully embedded, and it would be kinda painful to
covert to a pointer (e.g., there's kvm_x86_ops::vm_size), but perhaps that is
also an option to consider?

>   - <area>.{c,h} holds relevant declarations and definitions.
>   - x86.{c,h} is the kitchen sink for everything else.

Yeah the two are reasonable to me.

---

## [44] Sean Christopherson — 2026-05-19
*Subject: Re: [PATCH v2 15/15] KVM: x86: Move the bulk of register specific
 code from x86.c to regs.c*

On Wed, May 20, 2026, Kai Huang wrote:
> On Tue, 2026-05-19 at 08:04 -0700, Sean Christopherson wrote:
> > On Tue, May 19, 2026, Kai Huang wrote:

Events are a hard one.  There's a decent amount of code, but not _so_ much that
it's a no-brainer to move them out of x86.c.  And there's no super clear cut
boundary, e.g. events can mean exceptions, INIT+SIPI, IRQs, APIC stuff, etc.,
several of which already have substantial amounts of code outside of x86.c.

> > Hmm, though looking at all of this again, I think we're actually quite close to
> > having somewhat sane rules.  Over the past few years, I've tried multiple times

Ya.

> For x86, AFAICT there's (only) "arch/x86/events/intel/core.c" actually uses the
> 'struct kvm_pmu', though.

I have a patch to fix that :-)

https://lore.kernel.org/all/20260508231353.406465-7-seanjc@google.com

> I haven't checked other ARCHs whether there's cases actually need to use any
> structure.

PPC, arm64, and IIRC s390 all have assets defined by KVM that are consumed by
the kernel at-large.  E.g. because KVM for arm64 can't be built as a module, the
kernel calls directly into KVM during boot.  IIRC, PPC has similar code.

A few years ago (wow, time flies), I was able to hide KVM internals, using #ifdef
shenanigans to deal with cases where non-KVM really truly needed to get at things
defined in kvm_host.h

https://lore.kernel.org/all/20230916003118.2540661-27-seanjc@google.com

More recently, I tried to standardize KVM arch=>common includes[1], to help pave
the way to splitting up kvm_host.h, but then s390's crazy arm64 support killed
that (at least for now).

[1] https://lore.kernel.org/all/20250611001042.170501-1-seanjc@google.com
[2] https://lore.kernel.org/all/20260428160527.1378085-1-seiden@linux.ibm.com

> > I think it's probably time to admit I've been looking at the asm/kvm_host.h vs.
> > x86.h split all wrong, i.e. finally give up on moving structures out of kvm_host.h,

The problem is that anything that feeds into kvm_vcpu_arch needs to be visible
to virt/kvm.  And burying kvm_x86_ops in arch/kvm/x86 would mean one-liners like
kvm_arch_vcpu_blocking() couldn't be inlined.

I've looked at this far too many times :-)

> > Because literally the only reason that x86.h doesn't include mmu.h is that mmu.h
> > references struct kvm_host, which is currently defined in x86.h.  

I hacked on moving more stuff out of x86.{c,h} and kvm_host.h.  The diff stats
are quite promising :-)

 arch/x86/include/asm/kvm_host.h           |  444 ++-------------
 arch/x86/kvm/x86.c                        | 3784 +++-----------------------------------------------------------------------------------------------------------------------
 arch/x86/kvm/x86.h                        |  474 ++++++++--------

> > If we "fix"
> > that, then (a) we can make x86.h the "central" include everyone expects it to be,

The idea I had in the past, and where I was going with things before s390's love
for arm64 came along, was to add a kvm_arch.h in arch/<arch>/kvm, and have virt/kvm
include _that_ instead of kvm_host.h.  That way we don't need to make any fundamental
changes to structures, but we can still significantly cut down on what's exposed
via kvm_host.h.  At some point I'll try to take another look; it's really the
s390+arm64 combo that's problematic :-/

---

## [45] Huang, Kai — 2026-05-20
*Subject: Re: [PATCH v2 15/15] KVM: x86: Move the bulk of register specific
 code from x86.c to regs.c*

On Tue, 2026-05-19 at 18:25 -0700, Sean Christopherson wrote:
> On Wed, May 20, 2026, Kai Huang wrote:
> > On Tue, 2026-05-19 at 08:04 -0700, Sean Christopherson wrote:

Yes agreed.

> 
> > > Hmm, though looking at all of this again, I think we're actually quite close to

Oh great!

> 
> > I haven't checked other ARCHs whether there's cases actually need to use any

Oh I never thought from this perspective (thanks for the info):

  --
  Hiding KVM details for all architectures will, in the very distant future, 
  allow loading a new (or old) KVM module without needing to rebuild and reboot 
  the entire kernel, or to even allow loading and running multiple versions of 
  KVM simultaneously on a single host.
  --

> 
> More recently, I tried to standardize KVM arch=>common includes[1], to help pave

:-)

> 
> > > I think it's probably time to admit I've been looking at the asm/kvm_host.h vs.

Yeah that's the problem.

> And burying kvm_x86_ops in arch/kvm/x86 would mean one-liners like
> kvm_arch_vcpu_blocking() couldn't be inlined.

Oh right, sad but acceptable tradeoff I guess.

> 
> I've looked at this far too many times :-)

Indeed!

> > > If we "fix"
> > > that, then (a) we can make x86.h the "central" include everyone expects it to be,

Not sure whether there's other code doing so? :-)

> That way we don't need to make any fundamental
> changes to structures, but we can still significantly cut down on what's exposed

Yeah.

I saw below from you in [1]:

  --
  We've explore several alternatives to the #ifdef __KVM__ approach, and
  they all sucked, hard.  What I really wanted (and still want) to do, is to
  bury the bulk of kvm_host.h (and other KVM headers) in virt/kvm, but every
  attempt to do that ended in flames.  Even with the __KVM__ guards in place,
  each architecture's kvm_host.h is too intertwined with the common kvm_host.h,
  and trying to extract small-ish pieces just doesn't work (each patch
  inevitably snowballed into a gigantic beast).

  The other idea we considered (which I thought of, and feel dirty for even
  proposing it internally), is to move all headers under virt/kvm, add
  virt/kvm/include to the global header path, and then have KVM x86 omit
  virt/kvm/include when configured to hide KVM internals.  I hate this idea
  because it sets a bad precedent, and requires a lot of file movement
  without providing any benefit to other architectures.  E.g. I hope that
  guarding KVM internals with #ifdef __KVM__ will allow us to slowly clean
  things up so that some day KVM only exposes a handful of APIs to the rest
  of the kernel (probably a pipe dream).
  --

I haven't looked into details of your #ifdef __KVM__ approach yet, but seems you
don't quite like moving KVM internal staff to virt/kvm/include/ ?

But if we want to hide KVM internal structures, I don't see any other options
except virt/kvm/include/ is the place to go?

Btw, have you considered reverting the inclusion of "strut kvm" and "struct
kvm_arch" (and the vcpu structure), i.e., to make "struct kvm_arch" include
"struct kvm"?  I don't have any clue of whether it is feasible or how much
effort it needs, though -- it's just something came to mind when replying.

[1]: https://lore.kernel.org/all/20230916003118.2540661-1-seanjc@google.com/

> At some point I'll try to take another look; it's really the
> s390+arm64 combo that's problematic :-/

If you want, I can take a look.  I think I'll have bandwidth in near feature.

Given you have tried multiple times so I am not sure what I can achieve, though.

Anyway, seems "allow loading a new (or old) KVM module without needing to
rebuild and reboot the entire kernel" is a good reason to do this.

---

## [46] Binbin Wu — 2026-05-20
*Subject: Re: [PATCH v2 03/15] KVM: x86/xen: Don't truncate RAX when handling
 hypercall from protected guest*

On 5/18/2026 5:55 PM, Binbin Wu wrote:
> 
> 

I still have a point of confusion.

I noticed a behavioral mismatch between KVM and Xen regarding when they switch
to the standard/compat shared info.
- In Xen: The 32-bit shared info structure is latched if the current vCPU is
  not in 64-bit mode:
  hvm_latch_shinfo_size
      d->arch.has_32bit_shinfo = hvm_guest_x86_mode(current) != X86_MODE_64BIT

- In KVM: It evaluates is_long_mode(vcpu) instead. E.g.,
  kvm_xen_write_hypercall_page
      bool lm = is_long_mode(vcpu);
      ...
      kvm->arch.xen.long_mode = lm;

In theory, these two checks could differ when the guest kernel is running in
a 32-bit compatibility mode. However, I believe this mismatch is fine in
practice for two reasons:
- Mainstream 64-bit OSes don't run in compatibility mode for kernel code after
  the early init.
- By default, HVM guests cannot issue hypercalls from userspace. The only one
  exception HVMOP_guest_request_vm_event is not related to the share info.

So the vCPU will never be in compatibility mode when a related hypercall occurs.
In this specific operational context, evaluating is_long_mode() yields the
exact same functional outcome as checking for 64-bit execution mode. Am I
missing anything here?


>>
>> Agreed. For the hypercall case you're looking at, switching the name to

---

## [47] David Woodhouse — 2026-05-20
*Subject: Re: [PATCH v2 03/15] KVM: x86/xen: Don't truncate RAX when handling
 hypercall from protected guest*

On Wed, 2026-05-20 at 13:02 +0800, Binbin Wu wrote:
> > > > For this one, I think the current KVM code is consistent.
> > > > The format is determined by EFER.LMA, whether the guest is running in 64 bit or

Nice catch. That should probably use is_64_bit_hypercall() too, yes?

> In theory, these two checks could differ when the guest kernel is running in
> a 32-bit compatibility mode. However, I believe this mismatch is fine in

Although... some of the early init does involve 32-bit mode and it
wouldn't be impossible for the guest to build the hypercall page from
32-bit mode during startup.

> - By default, HVM guests cannot issue hypercalls from userspace. The only one
>   exception HVMOP_guest_request_vm_event is not related to the share info.

A third reason: This is only one of *two* places where the guest mode
gets latched. The guest's mode is also latched when it sets the
HVM_PARAM_CALLBACK_IRQ parameter. When running under KVM, the VMM
handles this and tells the kernel via the KVM_XEN_ATTR_TYPE_LONG_MODE
attribute.

So even if it doesn't latch correctly when setting the hypercall page,
it will later.

And Linux at least will set KVM_PARAM_CALLBACK_IRQ even if it isn't
using it, in xen_set_upcall_vector() with a comment saying 'Trick
toolstack to think we are enlightened'.

> So the vCPU will never be in compatibility mode when a related hypercall occurs.
> In this specific operational context, evaluating is_long_mode() yields the

I think you're right. We have thus far launched about 5 billion Xen
guests with this, and I've never heard any report about guests latching
the wrong mode. And there are a *lot* of random home-grown and network
appliance operating systems out there, and basic things like event
channels would fail to work if the shared_info was in the wrong mode.

That said, I would not be averse to fixing it. We could just use
is_64_bit_hypercall() in kvm_xen_write_hypercall_page(), right?

Or at the very least a comment saying that it *should* be doing so, but
that we're too nervous to change it now?

---

## [48] David Woodhouse — 2026-05-20
*Subject: Re: [PATCH v2 03/15] KVM: x86/xen: Don't truncate RAX when handling
 hypercall from protected guest*

On Thu, 2026-05-14 at 14:53 -0700, Sean Christopherson wrote:
> Don't truncate RAX when handling a Xen hypercall for a guest with protected
> state, as KVM's ABI is to assume the guest is in 64-bit for such cases

The latter isn't likely either. RAX is the system call number, and
those numbers are only in double digits; it'll be a while before we
need more than 8 bits for those, let alone 32 :)

But sure, as a cleanup it makes sense. Thanks.

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>

> Fixes: b5aead0064f3 ("KVM: x86: Assume a 64-bit hypercall for guests with protected state")
> Signed-off-by: Sean Christopherson <seanjc@google.com>

---

## [49] Sean Christopherson — 2026-05-20
*Subject: Re: [PATCH v2 15/15] KVM: x86: Move the bulk of register specific
 code from x86.c to regs.c*

On Wed, May 20, 2026, Kai Huang wrote:
> On Tue, 2026-05-19 at 18:25 -0700, Sean Christopherson wrote:
> > On Wed, May 20, 2026, Kai Huang wrote:

Not for arch code, which is the trickiest bit to handle.

> But if we want to hide KVM internal structures, I don't see any other options
> except virt/kvm/include/ is the place to go?

arch/$(ARCH)/kvm/kvm_arch.h is the obvious approach.  Code in virt/kvm can reach
arch/$(ARCH)/kvm, we just need to add it to the include path.  That's why I was
working on unifying the include definitions.

> Btw, have you considered reverting the inclusion of "strut kvm" and "struct
> kvm_arch" (and the vcpu structure), i.e., to make "struct kvm_arch" include

Consolidating includes and creating arch/$(ARCH)/kvm/kvm_arch.h should be more
doable, what has failed spectacularly over and over is effectively trying to hide
most of asm/kvm_host.h, which sounds *really* stupid when I phrase it that way :-)

> Anyway, seems "allow loading a new (or old) KVM module without needing to
> rebuild and reboot the entire kernel" is a good reason to do this.

Note, we've scrapped upstreaming multi-KVM, and I don't see it ever getting accepted
upstream, as live update is far superior, e.g. isn't limited to just KVM, doesn't
have the same orchestration or testing problems, etc.

And FWIW, today, you _can_ reload a new (or old) KVM module without rebuilding
the kernel or rebooting the host, it's just that you can't modify certain structures.

---

## [50] Huang, Kai — 2026-05-20
*Subject: Re: [PATCH v2 15/15] KVM: x86: Move the bulk of register specific
 code from x86.c to regs.c*

On Wed, 2026-05-20 at 11:11 -0700, Sean Christopherson wrote:
> On Wed, May 20, 2026, Kai Huang wrote:
> > On Tue, 2026-05-19 at 18:25 -0700, Sean Christopherson wrote:

Yeah, for asm/kvm_host.h.

But if I am still following you we still need a place for linux/kvm_host.h, for
which I thought virt/kvm/include/ would be the place at first glance.

> 
> > Btw, have you considered reverting the inclusion of "strut kvm" and "struct

Right.

> what has failed spectacularly over and over is effectively trying to hide
> most of asm/kvm_host.h, which sounds *really* stupid when I phrase it that way :-)

I see :-)

> 
> > Anyway, seems "allow loading a new (or old) KVM module without needing to

Right.

---

## [51] Sean Christopherson — 2026-05-21
*Subject: Re: [PATCH v2 15/15] KVM: x86: Move the bulk of register specific
 code from x86.c to regs.c*

On Wed, May 20, 2026, Kai Huang wrote:
> On Wed, 2026-05-20 at 11:11 -0700, Sean Christopherson wrote:
> > On Wed, May 20, 2026, Kai Huang wrote:

Oh, yes, the KVM-internal pieces of linuy/kvm_host.h would live in virt/kvm.

---
